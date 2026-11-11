"""Preflight V2 (Piso 3D-A) — verificação científica EXPLÍCITA e independente do preflight V1.6.

O preflight do Piso 2C (``seeds2.operation.preflight``) reproduz o contrato do EMS V1.6 (agregação por tecnologia, grade
fixa de 60 s, estado inicial por equivalência). Nada disso vale para o motor ``milp_mpc_v1``; copiar esses pressupostos
seria um defeito científico. Este módulo:

1. verifica a versão SALVA do cenário (estrutura, incarnação, revisão do inventário referenciada e sua impressão digital);
2. exige a seleção EXPLÍCITA do motor V2 e a estratégia ``milp_mpc`` sem erros e SEM declarações ausentes;
3. classifica cada equipamento POR UID: representável × excluído (indisponível no cenário) × BLOQUEANTE (não representável
   — PEMFC sem curva certificada/commitment, térmica sem M19; FV/eólica incompletas ou sem clima suficiente). Desde o
   Piso 3D-A2-R, FV (por arranjo) e eólica (por registro) corretamente parametrizadas são representáveis: o potencial no
   barramento é derivado pelos modelos físicos do SEEDS2 (``integracao_v2.renovaveis``) a partir do clima previsto;
4. monta o inventário efetivo, a malha N/N+1, as séries (previsão × realização separadas) e as políticas declaradas;
5. executa, SEM relaxar nada, o preflight da ponte 3C-0/3C-1 (``ems_v2.ponte.preflight.preflight_ems_v2``, finalidade
   ``otimizacao``) e as validações 3C-3/3C-2/3C-4 (construção do controlador hierárquico, sem resolver);
6. verifica o ambiente do solver (Pyomo/HiGHS): ausente ⇒ bloqueio explicado — NUNCA há recaída para o motor V1.6.

Qualquer item ``erro`` ⇒ ``ok = False`` ⇒ nenhuma rodada é aberta. O relatório (itens + matriz
fonte → transformação → validação → registro → vista + relatório da ponte) é gravado no manifesto de cada rodada.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from ems_v2.diagnostics import ContratoInvalido
from ems_v2.hierarquia.contrato import hash_configuracao_planejador
from ems_v2.milp.ambiente import verificar_ambiente
from ems_v2.ponte import cenario as CN
from ems_v2.ponte import inventario as IV
from ems_v2.ponte.preflight import AREAS as AREAS_PONTE, hash_preflight, preflight_ems_v2
from ems_v2.ponte_seeds2 import leitor as L
from ems_v2.provenance import Procedencia
from ems_v2.rede.contrato import hash_entrada_3c3, validar_entrada_3c3
from ems_v2.rede.mpc import hash_configuracao_rede
from ems_v2.timegrid import ler_instante_utc

from seeds2.microgrid.references import KIND_LABELS
from seeds2.operation import forecasts as F
from seeds2.operation import mission as M
from seeds2.operation import scenarios as S
from seeds2.operation import strategy as SG

from . import estrategia as E
from . import montagem as MT
from . import curva_h2 as CH
from . import renovaveis as RN

OK, INFO, WARNING, ERROR = "ok", "info", "aviso", "erro"
LEVEL_LABELS = {OK: "Verificado", INFO: "Informação", WARNING: "Advertência (não bloqueia)",
                ERROR: "Bloqueio (impede a execução)"}
AREA_LABELS = {
    "cenario": "Cenário", "inventario": "Inventário de referência", "motor": "Motor selecionado",
    "estrategia": "Estratégia MILP–MPC", "dispositivos": "Equipamentos por UID", "parametros": "Parâmetros declarados",
    "tempo": "Malha temporal", "previsoes": "Previsão disponível ao decidir", "realizacao": "Realização simulada",
    "causalidade": "Separação previsão × realização", "pcc": "PCC e tarifas", "ponte": "Ponte científica 3C-0/3C-1",
    "contrato": "Contratos 3C-3 / MPC / 3C-4", "solver": "Solver Pyomo/HiGHS", "escopo": "Alcance científico",
    "renovaveis": "Potencial renovável (modelos físicos do SEEDS2)",
    "pemfc": "PEMFC / H₂ (curva do modelo físico, certificação B04, commitment)",
}
NAO_REPRESENTAVEL = {
    "termica": "o custo de geração térmica (M19 / CVU) NÃO está implementado no núcleo 3C-4: uma térmica despachável "
               "produziria conclusões econômicas sem custo de combustível",
}
ESCOPO = ("Simulação OFFLINE de laço fechado, ALGÉBRICA, em contexto de ENSAIO: o controlador decide com a previsão "
          "declarada e uma planta algébrica realiza cada intervalo. Não é controle de equipamentos, telemetria SCADA, "
          "validação física nem fatura real.")


@dataclass(frozen=True)
class Item:
    level: str
    area: str
    message: str
    eq_id: str | None = None
    code: str | None = None

    def as_dict(self) -> dict:
        return {"level": self.level, "area": self.area, "message": self.message, "eq_id": self.eq_id, "code": self.code}


@dataclass
class PreflightV2:
    scenario: Any
    items: list[Item] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)
    represented: list[dict] = field(default_factory=list)
    matriz: list[dict] = field(default_factory=list)
    montagem: MT.Montagem | None = None
    ponte: dict | None = None
    ambiente: dict = field(default_factory=dict)
    config_revision: int | None = None
    config_fingerprint: str | None = None
    drift: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.montagem is not None and self.montagem.modelo is not None \
            and not any(i.level == ERROR for i in self.items)

    def add(self, level: str, area: str, message: str, eq_id: str | None = None, code: str | None = None) -> None:
        it = Item(level, area, message, eq_id, code)
        if it not in self.items:
            self.items.append(it)

    def count(self, level: str) -> int:
        return sum(1 for i in self.items if i.level == level)

    def engine_inputs(self) -> dict:
        """O que efetivamente chega ao motor (exibido antes de executar e gravado no manifesto)."""
        mt = self.montagem
        if mt is None:
            return {}
        t = mt.tempo
        extra = {}
        if mt.renovaveis:
            h = t.delta_s / 3600.0
            extra = {"renovaveis": [{"uid": d.uid, "registro": d.registro, "tecnologia": d.tecnologia, "nome": d.nome,
                                     "modelo": d.modelo, "pico_kW": max(d.potencia_kW),
                                     "energia_potencial_kWh": d.energia_kWh(h)} for d in mt.renovaveis],
                     "clima": None if mt.clima is None else mt.clima.doc()}
        return {**extra, "grid": {"start_utc": t.inicio_utc, "start_wall": t.inicio_local, "timezone": t.fuso,
                         "delta_min": t.delta_min, "step_s": t.delta_s, "intervals": t.K, "frontiers": t.K + 1,
                         "duration_min": t.delta_min * t.K, "end_utc": t.instante(t.K), "N": t.N, "m": t.m, "H_L": t.H_L},
                "fixed": dict(MT.FIXOS), "matriz": [dict(r) for r in self.matriz], "hashes": dict(mt.hashes),
                "uids": {"demanda": MT.UID_DEMANDA, "pcc": MT.UID_PCC, "medidor_importacao": MT.UID_MED_IMP,
                         "medidor_exportacao": MT.UID_MED_EXP, "provedor": MT.ID_PROVEDOR, "planta": MT.ID_PLANTA},
                "tarifas_R_kWh": {k: list(v) for k, v in mt.tarifas.items()}}

    def report(self) -> dict:
        return {"ok": self.ok, "engine": E.MOTOR_V2, "items": [i.as_dict() for i in self.items],
                "excluded": [dict(x) for x in self.excluded], "represented": [dict(x) for x in self.represented],
                "drift": list(self.drift), "bridge": self.ponte, "solver_environment": dict(self.ambiente),
                "scope": ESCOPO, "counts": {lv: self.count(lv) for lv in (OK, INFO, WARNING, ERROR)}}


# ====================================================================== utilidades
def _fmt(v) -> str:
    return f"{v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)


def _proc_txt(p: Procedencia | None) -> str:
    if p is None:
        return "sem procedência"
    return f"{p.tipo} · {p.fonte}" + (f" · {p.referencia}" if p.referencia else "")


def _linha(dado: str, uid: str, valor, unidade: str, fonte: str, transformacao: str, validacao: str, registro: str,
           vista: str) -> dict:
    return {"dado": dado, "uid": uid, "valor": valor, "unidade": unidade, "fonte": fonte, "transformacao": transformacao,
            "validacao": validacao, "registro": registro, "vista": vista}


def _par_linha(dado: str, uid: str, par, validacao: str, registro: str, vista: str) -> dict:
    trans = "nenhuma (valor declarado na unidade canônica)"
    if getattr(par, "transformacoes", ()):
        trans = "; ".join(f"{t.etapa}: {t.descricao}" for t in par.transformacoes) + \
                f" (bruto {par.valor_bruto!r} {par.unidade_bruta})"
    elif par.procedencia is not None and par.procedencia.observacoes and "×" in par.procedencia.observacoes:
        trans = par.procedencia.observacoes
    return _linha(dado, uid, par.valor, par.unidade, _proc_txt(par.procedencia), trans, validacao, registro, vista)


# ====================================================================== preflight
def preparar(store, stored) -> PreflightV2:
    """Preflight V2 sobre uma versão GRAVADA (``StoredScenario``) do cenário. Somente leitura."""
    pf = PreflightV2(scenario=stored)
    doc = stored.document
    pf.add(INFO, "escopo", ESCOPO)
    # ---- 1. documento do cenário
    errs = S.structural_errors(doc)
    for slot, entry in (doc.get("forecasts") or {}).items() if not errs else ():
        errs += F.entry_errors(slot, entry)
    for e in errs:
        pf.add(ERROR, "cenario", e)
    if errs:
        return pf
    mg = doc.get("microgrid") or {}
    if store.incarnation is not None and mg.get("incarnation") not in (None, store.incarnation):
        pf.add(ERROR, "cenario", "O cenário foi definido para outra incarnação desta microrrede.")
        return pf
    # ---- 2. motor e estratégia
    if E.motor_selecionado(doc) != E.MOTOR_V2:
        pf.add(ERROR, "motor", "Este cenário NÃO seleciona o motor V2: a execução MILP–MPC exige a seleção explícita "
                               f"'{E.MOTOR_V2}' na etapa 03 (nenhum motor é trocado em silêncio).")
        return pf
    pf.add(OK, "motor", f"Motor selecionado explicitamente na versão v{stored.version}: {E.MOTORES[E.MOTOR_V2]}.")
    bloco = doc.get(E.CHAVE_BLOCO)
    if bloco is None:
        pf.add(ERROR, "estrategia", "Estratégia MILP–MPC não definida (etapa 03): sem ela nada chega ao motor V2.")
        return pf
    for e in E.erros_estruturais(bloco, doc):
        pf.add(ERROR, "estrategia", e)
    if pf.count(ERROR):
        return pf
    if bloco["contexto"] != "ensaio":
        pf.add(ERROR, "estrategia", E.CONTEXTO_NAO_SUPORTADO)
        return pf
    pend = E.pendencias(bloco, doc)
    for cam, msg in pend:
        pf.add(ERROR, "estrategia", f"Não declarado — {msg} [{E.CHAVE_BLOCO}.{cam}]", code="nao_declarado")
    # ---- 3. revisão do inventário de referência (imutável)
    ref = doc["inventory_ref"]
    try:
        rev = store.get_revision(int(ref["config_revision"]))
    except Exception as exc:                                     # noqa: BLE001 — mensagem apresentável
        pf.add(ERROR, "inventario", f"Revisão {ref['config_revision']} do inventário indisponível: {exc}")
        return pf
    if rev.fingerprint != ref["config_fingerprint"]:
        pf.add(ERROR, "inventario", "A revisão do inventário referenciada não corresponde à impressão digital do cenário.")
        return pf
    pf.config_revision, pf.config_fingerprint = rev.revision, rev.fingerprint
    saved = store.load()
    if saved is not None:
        d = S.drift(doc, saved.config, saved.revision)
        if d.stale:
            pf.drift = d.describe(doc, saved.config)
            pf.add(WARNING, "inventario", f"O inventário atual (revisão {saved.revision}) mudou desde a revisão "
                   f"{rev.revision} de referência ({'; '.join(pf.drift[:4])}). A execução usa a revisão {rev.revision} "
                   "(a do cenário); atualize a referência no Centro de Operação para usar o inventário atual.")
        else:
            pf.add(OK, "inventario", f"Inventário de referência: revisão {rev.revision} "
                   + ("(atual)." if d.same_revision else f"(equivalente à revisão atual {saved.revision})."))
    try:
        inv = L.inventario_de_documento(rev.config, revisao=rev.revision, impressao_config=rev.fingerprint,
                                        incarnacao=store.incarnation)
        cen = L.cenario_de_versao(stored)
    except Exception as exc:                                     # noqa: BLE001 — leitura da ponte: nunca falha silenciosa
        pf.add(ERROR, "inventario", f"A ponte 3C-0 não conseguiu ler o inventário/cenário: {type(exc).__name__}: {exc}")
        return pf
    # ---- 4. equipamentos por UID
    excl = _classificar(pf, inv, cen, doc, bloco)
    # ---- 5. topologia declarada × modo do PCC
    _topologia(pf, inv, bloco)
    # ---- 6. malha temporal e séries
    tempo = _tempo(pf, doc, bloco)
    if pf.count(ERROR) or tempo is None:
        return pf
    series = _series(pf, store, stored, doc, bloco, tempo, inv, excl)
    if pf.count(ERROR) or series is None:
        return pf
    prev_kw, real_kw, tabela, verdade, fonte_verdade, prev_nucleo, real_nucleo = series
    renov = _renovaveis(pf, store, stored, doc, bloco, tempo, rev.config, excl)
    if pf.count(ERROR) or renov is None:
        return pf
    tabela, verdade, prev_nucleo, real_nucleo = _com_renovaveis(renov, tabela, verdade, prev_nucleo, real_nucleo, tempo,
                                                                stored)
    pem = _pemfc(pf, bloco, inv, stored)
    if pf.count(ERROR) or pem is None:
        return pf
    tabela, verdade, prev_nucleo, real_nucleo = _com_disponibilidade_geradores(
        [u for x in pf.represented if x["kind"] == "pemfc" for u in x["uids"]], tabela, verdade, prev_nucleo, real_nucleo,
        tempo, stored, bloco)
    # ---- 7. inventário efetivo e projeção pela ponte (sem relaxação)
    inv_ef = MT.inventario_efetivo(inv, bloco, stored, excl)
    proc_pol = MT.proc_declarada(bloco["declarante"], "declarante", stored)
    pol = MT.politicas(bloco, proc_pol, com_geradores=bool(pem))
    sem = [t for t in ("combustivel_h2", "eventos") if t in bloco["objetivo"]["termos"] and not pem]
    if sem:
        pf.add(INFO, "estrategia", f"Termo(s) {', '.join(sem)} declarado(s), mas nenhuma PEMFC participa desta missão "
               "(indisponível ou ausente): não aplicado(s) ao objetivo desta rodada.")
    mont = MT.Montagem(tempo, inv, inv_ef, cen, pf.excluded, pf.represented, prev_kw, real_kw, tabela, verdade,
                       fonte_verdade, pol, proc_politicas=proc_pol)
    derivs, clima = renov
    mont.renovaveis, mont.clima = list(derivs), clima
    mont.bases = {d.uid: "antes_da_disponibilidade" for d in derivs}
    mont.pemfc = pem
    pf.montagem = mont
    try:
        decl = MT.declaracao_commitment(inv_ef, cen, proc_pol, bloco, stored)
        rel, proj = preflight_ems_v2(inv_ef, cen, CN.DefinicaoTemporal(tempo.malha_modelo()), prev_nucleo, real_nucleo, pol,
                                     contexto="ensaio", finalidade="otimizacao", commitment_3c1=decl,
                                     curvas_h2={u: x["curva_pwl"] for u, x in pem.items()} or None,
                                     massas_h2_eventos={u: x["massas_pwl"] for u, x in pem.items()} or None)
    except ContratoInvalido as exc:
        for c in exc.constatacoes:
            pf.add(ERROR, "ponte", f"{c.codigo} · {c.caminho}: {c.mensagem}", code=c.codigo)
        return pf
    _itens_ponte(pf, rel)
    pf.ponte = {"apto_para_otimizacao": bool(rel.apto_para_otimizacao), "contexto": rel.contexto,
                "finalidade": rel.finalidade, "sha256": hash_preflight(rel), "texto": rel.texto(),
                "contagens": {s: sum(1 for i in rel.itens if i.severidade == s)
                              for s in ("bloqueante", "advertencia", "aceitavel")}}
    if not rel.apto_para_otimizacao or proj is None or proj.entrada is None:
        return pf
    mont.nucleo = proj.entrada
    # ---- 8. PCC, tarifas, MPC, planejador (contratos 3C-3 / 3C-2 / 3C-4)
    try:
        modelo, pol_aj, cfg_rede, tarifas = MT.rede(mont.nucleo, bloco, tempo, inv.identidade.uid, stored)
        for c in validar_entrada_3c3(modelo).constatacoes:
            pf.add(ERROR if c.severidade in ("erro", "pendente") else WARNING, "pcc",
                   f"{c.codigo} · {c.caminho}: {c.mensagem}", code=c.codigo)
        if pf.count(ERROR):
            return pf
        mont.modelo, mont.politica_ajuste, mont.configuracao_rede, mont.tarifas = modelo, pol_aj, cfg_rede, tarifas
        mont.configuracao_planejador = MT.configuracao_planejador(bloco, tempo, proc_pol)
        mont.solver = MT.configuracao_solver(bloco)
        MT.construir_missao(mont, "0" * 32, stored)        # valida 3C-2/3C-3/3C-4 SEM resolver (identidade provisória)
    except ContratoInvalido as exc:
        mont.modelo = None
        for c in exc.constatacoes:
            pf.add(ERROR if c.severidade in ("erro", "pendente") else WARNING, "contrato",
                   f"{c.codigo} · {c.caminho}: {c.mensagem}", code=c.codigo)
        return pf
    mont.hashes = {"inventario_ems_efetivo": IV.hash_inventario(inv_ef), "cenario_ems": CN.hash_cenario(cen),
                   "modelo_rede_3c3": hash_entrada_3c3(modelo), "configuracao_rede": hash_configuracao_rede(cfg_rede),
                   "configuracao_planejador": hash_configuracao_planejador(mont.configuracao_planejador),
                   "preflight_ponte": pf.ponte["sha256"]}
    if mont.renovaveis:
        mont.doc_renovaveis = RN.documento(mont.renovaveis, mont.clima, _realizacao_renovavel(), tempo.delta_s)
        mont.hashes["renovaveis"] = RN.sha_documento(mont.doc_renovaveis)
    if mont.pemfc:
        mont.doc_pemfc = documento_pemfc(mont.pemfc)
        mont.hashes["pemfc"] = RN.sha_documento(mont.doc_pemfc)
    pf.add(OK, "contrato", f"Entrada 3C-3 aceita (modo {modelo.pcc.modo}); configuração do MPC (Δ = {tempo.delta_min} min, "
           f"N = {tempo.N}, m = {tempo.m}, K_M = {tempo.K}) e do planejador (H_L = {tempo.H_L}, sinal "
           f"'{bloco['planejador']['tipo_sinal']}', degradação '{bloco['planejador']['degradacao']}') aceitas pelo "
           "controlador hierárquico 3C-4.")
    _matriz(pf, mont, bloco, doc)
    # ---- 9. solver (último: tudo acima é verificável sem ele)
    pf.ambiente = verificar_ambiente()
    if not pf.ambiente.get("disponivel"):
        pf.add(ERROR, "solver", "Pyomo/HiGHS indisponíveis neste servidor ("
               + str(pf.ambiente.get("erro") or "dependências opcionais não instaladas")
               + "). A rodada V2 NÃO é executada e o motor V1.6 nunca é usado como substituto. Instalação: "
                 "pip install -r requirements-ems_v2.txt.", code="solver_indisponivel")
    else:
        v = pf.ambiente.get("versoes") or {}
        pf.add(OK, "solver", f"Pyomo {v.get('pyomo')} + highspy {v.get('highspy')} (HiGHS {pf.ambiente.get('versao_highs')}) "
               "disponíveis" + (f"; versões diferentes das fixadas: {pf.ambiente.get('divergencias')}"
                                if pf.ambiente.get("divergencias") else " (versões fixadas)") + ".")
        if pf.ambiente.get("divergencias"):
            pf.add(WARNING, "solver", f"Versões do solver diferentes das fixadas em requirements-ems_v2.txt "
                   f"({pf.ambiente['divergencias']}): os resultados podem diferir dos ensaios auditados.")
    return pf


# ====================================================================== etapas
def _estado(doc: dict, eq_id: str) -> dict:
    return ((doc.get("initialization") or {}).get("equipment") or {}).get(eq_id) or {}


def _classificar(pf: PreflightV2, inv, cen, doc: dict, bloco: dict) -> set[str]:
    """Representável × excluído × bloqueante, POR UID. Devolve os UIDs de registro excluídos (indisponíveis)."""
    excl: set[str] = set()
    refs = (doc.get("inventory_ref") or {}).get("equipment") or {}
    for d in inv.dispositivos:
        if d.pai is not None:
            continue                                   # arranjos seguem a usina (o SEEDS2 declara a disponibilidade por registro)
        nome = d.nome or d.uid
        rot = KIND_LABELS.get((refs.get(d.uid) or {}).get("kind"), d.tipo)
        if not d.habilitado:
            pf.add(INFO, "dispositivos", f"{nome} ({rot}): desabilitado no inventário — não faz parte da operação.", d.uid)
            continue
        if _estado(doc, d.uid).get("availability") == "indisponivel":
            excl.add(d.uid)
            pf.excluded.append({"id": d.uid, "name": nome, "kind": (refs.get(d.uid) or {}).get("kind"),
                                "reason": "Indisponível no cenário: fora do modelo desta missão (equivale a a = 0 em todos "
                                          "os intervalos; inventário inalterado)."})
            pf.add(INFO, "dispositivos", f"{nome} ({rot}) declarado indisponível no cenário: excluído SOMENTE desta missão "
                   "(nenhuma potência; inventário permanente intocado).", d.uid)
            continue
        if d.tipo == "bateria":
            if d.uid not in bloco["baterias"]:
                pf.add(ERROR, "dispositivos", f"{nome} (banco {d.uid}): sem declarações V2 na estratégia (eficiências, "
                       "potências no barramento, hipótese de autodescarga). Nenhum valor é presumido.", d.uid)
            else:
                pf.represented.append({"id": d.uid, "name": nome, "kind": "battery", "papel": "armazenamento (M06–M08)"})
            continue
        if d.tipo in ("pv_usina", "eolica"):
            kind = "pv" if d.tipo == "pv_usina" else "wind"
            decl = (bloco.get("renovaveis") or {}).get(d.uid) if bloco["format_version"] >= 2 else None
            if decl is None:
                if bloco["format_version"] >= 2:
                    pf.add(ERROR, "dispositivos", f"{nome} ({rot}): sem declarações V2 na estratégia (conversão para o "
                           "barramento / hipótese de densidade e procedência). Nenhum valor é presumido.", d.uid)
                continue                               # formato 1: pendência 'renovaveis' já listada
            uids = [x.uid for x in inv.dispositivos if x.pai == d.uid] if kind == "pv" else [d.uid]
            pf.represented.append({"id": d.uid, "name": nome, "kind": kind, "uids": uids,
                                   "papel": "renovável (M03-v1.1) — potencial pelo modelo físico do SEEDS2"})
            continue
        if d.tipo == "pemfc":
            decl = (bloco.get("pemfc") or {}).get(d.uid) if bloco["format_version"] >= 3 else None
            if decl is None:
                if bloco["format_version"] >= 3:
                    pf.add(ERROR, "dispositivos", f"{nome} ({rot}): sem declarações V2 na estratégia (condições físicas, "
                           "P_min, rampa, permanências, abstração, estados por unidade, preço do H₂). Nenhum valor é "
                           "presumido.", d.uid)
                continue                               # formato < 3: pendência 'pemfc' já listada
            pf.represented.append({"id": d.uid, "name": nome, "kind": "pemfc", "uids": [str(r) for r in IV.recursos_ems(d)],
                                   "papel": "gerador despachável (M10, M14–M16; commitment 3C-1 por unidade)"})
            continue
        chave = d.tipo
        pf.add(ERROR, "dispositivos", f"{nome} ({rot}) está habilitado e disponível, mas NÃO é representável pelo motor V2 "
               f"no Piso 3D-A: {NAO_REPRESENTAVEL[chave]}. Um equipamento disponível nunca é omitido em silêncio: "
               "declare-o indisponível neste cenário (exclusão só desta missão) ou aguarde o piso correspondente.",
               d.uid, code="nao_representavel_3da")
    n = sum(1 for x in pf.represented if x["kind"] == "battery")
    nr = sum(1 for x in pf.represented if x["kind"] in ("pv", "wind"))
    if n > 2:
        pf.add(ERROR, "dispositivos", f"{n} bancos disponíveis: o sinal de valor futuro PWL do 3C-4 suporta até 2 bancos "
                                      "(dimensão declarada do planejador).")
    if not pf.count(ERROR):
        pf.add(OK, "dispositivos", f"{n} banco(s) representável(is) por UID; "
               + (f"{nr} equipamento(s) renovável(is) com potencial a derivar pelo modelo físico; " if nr else "")
               + f"{len(excl)} equipamento(s) excluído(s) desta missão; nenhum equipamento disponível fora do modelo.")
    return excl


def _topologia(pf: PreflightV2, inv, bloco: dict) -> None:
    modo_inst, modo_pcc = inv.modo_operacao, bloco["pcc"]["modo"]
    if modo_pcc is None:
        return                                         # já constatado como não declarado
    rot = {"isolada": "isolada (off-grid)", "conectada": "conectada à rede",
           "conectada_ilhamento": "conectada com ilhamento declarado"}.get(modo_inst)
    if rot is None:
        pf.add(ERROR, "pcc", f"Modo operativo da instalação não declarado no inventário ({modo_inst!r}): nenhuma topologia "
                             "é presumida. Declare-o em Gestão da Microrrede.")
        return
    coerente = {"isolada": ("isolado_declarado",), "conectada": ("conectado",),
                "conectada_ilhamento": ("conectado", "isolado_declarado")}[modo_inst]
    if modo_pcc not in coerente:
        pf.add(ERROR, "pcc", f"A instalação está declarada {rot}, mas a estratégia declara o PCC '{modo_pcc}': incoerente. "
                             "A operação isolada de uma instalação conectada exige capacidade de ilhamento declarada no "
                             "inventário; uma instalação isolada não tem PCC.")
    else:
        pf.add(OK, "pcc", f"Instalação {rot}; PCC declarado '{modo_pcc}' (coerente com o inventário).")


def _tempo(pf: PreflightV2, doc: dict, bloco: dict) -> MT.Tempo | None:
    m, mis = bloco["malha"], doc.get("mission")
    if mis is None:
        pf.add(ERROR, "tempo", "Janela da missão não definida (etapa 04: início e duração).")
        return None
    for e in SG.mission_errors(mis):
        pf.add(ERROR, "tempo", e)
    if any(m[k] is None for k in ("delta_min", "N", "m", "H_L")) or SG.mission_errors(mis):
        return None
    tz = mis.get("timezone")
    if not tz:
        pf.add(ERROR, "tempo", "A missão não declara fuso horário: os instantes UTC da malha ficam indeterminados (o "
                               "contrato 3A exige instantes com fuso explícito).")
        return None
    wall = pd.Timestamp(str(mis["start"]))
    s_utc, bad = M.wall_to_utc(pd.Series([wall]), tz)
    if bad.any():
        pf.add(ERROR, "tempo", f"Início {wall:%d/%m/%Y %H:%M} ambíguo ou inexistente no fuso {tz} (mudança de horário).")
        return None
    delta, dur = int(m["delta_min"]), int(mis["duration_min"])
    if dur % delta:
        pf.add(ERROR, "tempo", f"Duração da missão ({dur} min) não é múltiplo inteiro de Δ = {delta} min: não existe "
                               "último intervalo curto implícito.")
        return None
    K = dur // delta
    N, mm, HL = int(m["N"]), int(m["m"]), int(m["H_L"])
    if K > E.LIMITES["intervalos_missao"]:
        pf.add(ERROR, "tempo", f"Missão com {K} intervalos (> {E.LIMITES['intervalos_missao']}): fora do orçamento "
                               "computacional verificado do planejador (B3C4-05).")
    if mm > N:
        pf.add(ERROR, "tempo", f"m = {mm} > N = {N}: exigido 1 <= m <= N.")
    if HL <= N:
        pf.add(ERROR, "tempo", f"H_L = {HL} <= N = {N}: o horizonte longo deve ser MAIOR que o curto (H_L > N).")
    if HL > K:
        pf.add(ERROR, "tempo", f"H_L = {HL} intervalos > K_M = {K}: a previsão declarada cobre só a missão (H_f = K_M·Δ); "
                               "nenhuma previsão pós-missão é extrapolada.")
    if pf.count(ERROR):
        return None
    t = MT.Tempo(MT.utc_iso(float(s_utc[0])), delta, K, N, mm, HL, tz, wall.strftime("%Y-%m-%dT%H:%M:%S"))
    pf.add(OK, "tempo", f"τ₀ = {t.inicio_utc} ({wall:%d/%m/%Y %H:%M} {tz}); Δ = {delta} min; K_M = {K} intervalos de decisão "
           f"e {K + 1} fronteiras de estado; horizonte curto N = {N}, bloco aplicado m = {mm}, horizonte longo H_L = {HL}.")
    return t


def _series(pf: PreflightV2, store, stored, doc: dict, bloco: dict, t: MT.Tempo, inv, excl: set[str]):
    entry = (doc.get("forecasts") or {}).get("demand")
    d = bloco["demanda"]
    if not entry:
        pf.add(ERROR, "previsoes", "Previsão de demanda ausente no cenário (etapa 02).")
        return None
    if not entry.get("timezone"):
        pf.add(ERROR, "previsoes", "A série de demanda não declara fuso horário: instantes UTC indeterminados.")
        return None
    if entry.get("provenance") not in ("medido", "sintetico", "referencia"):
        pf.add(ERROR, "previsoes", "Procedência da previsão de demanda não declarada: uma procedência 'não declarada' não "
                                   "sustenta valores numéricos no contrato do motor (declare-a na etapa 02).")
        return None
    try:
        s = M.load_series("demand", entry, store.get_blob)
    except F.ForecastDataError as exc:
        pf.add(ERROR, "previsoes", f"Série de demanda indisponível ou corrompida: {exc}")
        return None
    t0 = datetime.fromisoformat(t.inicio_utc).timestamp()
    alvo = t0 + t.delta_s * np.arange(t.K)
    idx = np.searchsorted(s.t_utc, alvo)
    ok = (idx < len(s.t_utc))
    ok[ok] &= np.abs(s.t_utc[idx[ok]] - alvo[ok]) < 1e-6
    if not ok.all():
        falt = int((~ok).sum())
        pf.add(ERROR, "previsoes", f"A série de demanda não tem amostra em {falt} de {t.K} início(s) de intervalo da malha "
               f"(Δ = {t.delta_min} min a partir de τ₀; passo da série {entry.get('step_s')!r} s). O motor V2 não reamostra "
               "nem interpola: alinhe o início da missão a um instante da série e use Δ igual ao passo da série.")
        return None
    # Semântica declarada: o valor em t é a média de [t, t + passo). Todo passo usado (inclusive o do ÚLTIMO intervalo)
    # tem de ser exatamente Δ; no fim da série vale o passo típico registrado na entrada.
    passo = np.diff(s.t_utc[idx[0]: min(idx[-1] + 2, len(s.t_utc))])
    tipico = entry.get("step_s")
    fim_da_serie = idx[-1] + 1 >= len(s.t_utc)
    if (np.abs(passo - t.delta_s) > 1e-6).any() or (fim_da_serie and not (
            isinstance(tipico, (int, float)) and abs(float(tipico) - t.delta_s) < 1e-6)):
        pf.add(ERROR, "previsoes", f"A série de demanda tem passo diferente de Δ = {t.delta_min} min dentro da missão "
               "(amostras intermediárias): com a semântica declarada 'média do intervalo [t, t + passo)', usar Δ maior que "
               "o passo exigiria agregação — não é feita. Declare Δ igual ao passo da série.")
        return None
    vals = s.df["demand_kW"].to_numpy(dtype=float)[idx]
    if not np.isfinite(vals).all() or (vals < 0).any():
        pf.add(ERROR, "previsoes", "Demanda ausente (lacuna) ou negativa em intervalos da missão: ausente nunca vira zero.")
        return None
    emis = d["emissao_utc"]
    if ler_instante_utc(emis, "e")[0] > ler_instante_utc(t.inicio_utc, "t")[0]:
        pf.add(ERROR, "causalidade", f"A previsão de demanda foi declarada EMITIDA em {emis}, depois do início da missão "
               f"({t.inicio_utc}): informação futura — execução bloqueada.", code="previsao_nao_causal")
        return None
    prev = tuple(float(v) for v in vals)
    p_prev = Procedencia(entry["provenance"],
                         f"SEEDS2 · cenário {stored.scenario_uid} v{stored.version} · previsão de demanda "
                         f"({entry.get('label') or entry.get('source_type')})", "forecasts.demand", sha256=entry["data"],
                         observacoes=f"semântica DECLARADA na estratégia: média do intervalo [t, t + Δ); emissão declarada "
                                     f"{emis}; fuso da série {entry['timezone']}; tabela declarada antecipadamente")
    pf.add(OK, "previsoes", f"Previsão de demanda: {t.K} médias de intervalo alinhadas à malha (sem reamostragem), "
           f"{_fmt(min(prev))}–{_fmt(max(prev))} kW; origem '{entry.get('source_type')}' / procedência "
           f"'{entry['provenance']}'; emissão declarada {emis} (anterior a τ₀).")
    # ---- realização simulada (objeto, fonte e procedência PRÓPRIOS; nunca entregue ao provedor)
    r = bloco["realizacao"]
    if r["tipo"] == "serie_declarada":
        if len(r["demanda_kW"]) != t.K:
            pf.add(ERROR, "realizacao", f"A realização declarada tem {len(r['demanda_kW'])} valor(es); a missão tem {t.K} "
                                        "intervalos (um valor por intervalo, sem extrapolação).")
            return None
        real = tuple(float(v) for v in r["demanda_kW"])
    else:
        real = tuple(prev)
    fonte_real = f"{str(r['procedencia']['fonte']).strip()} — realização SIMULADA entregue só à planta algébrica 3D-A"
    p_real = Procedencia("sintetico", fonte_real, f"{E.CHAVE_BLOCO}.realizacao", sha256=stored.fingerprint,
                         observacoes=E.REALIZACOES[r["tipo"]])
    if fonte_real == p_prev.fonte:
        pf.add(ERROR, "causalidade", "A fonte declarada da realização coincide com a da previsão: o provedor de previsão "
                                     "não seria independente da verdade do simulador.")
        return None
    dif = sum(1 for a, b in zip(prev, real) if a != b)
    pf.add(OK if dif else WARNING, "realizacao",
           (f"Realização simulada declarada: difere da previsão em {dif} de {t.K} intervalo(s)." if dif else
            "Realização simulada IGUAL à previsão declarada: simulação sem erro de previsão (não é oráculo — o controlador "
            "recebe só a previsão; a coincidência é registrada como advertência da ponte)."))
    pf.add(OK, "causalidade", "Previsão (provedor de tabela declarada) e realização (planta algébrica) são objetos e fontes "
                              "distintos; o MPC verifica em cada janela o vínculo ao instantâneo informacional K6 e recusa "
                              "um provedor que aponte a fonte de verdade.")
    # ---- disponibilidades (estáticas do cenário) e tabela do provedor
    um = [1.0] * t.K
    tabela = {(MT.UID_DEMANDA, "potencia"): MT.serie("potencia", t, prev, p_prev, emis)}
    v_series = [CN.SerieRecurso(MT.UID_DEMANDA, "potencia", MT.serie("potencia", t, real, p_real, None))]
    for b in pf.represented:
        if b["kind"] != "battery":
            continue                                   # renováveis: potencial e disponibilidade em ``_com_renovaveis``
        uid = b["id"]
        p_a = Procedencia("declarado_seeds2", f"SEEDS2 · cenário {stored.scenario_uid} v{stored.version}",
                          f"initialization.equipment[{uid}].availability", sha256=stored.fingerprint,
                          observacoes="Série constante a = 1 derivada da disponibilidade ESTÁTICA do cenário (disponível) "
                                      "— transformação da integração 3D-A")
        tabela[(uid, "disponibilidade")] = MT.serie("disponibilidade", t, um, p_a, emis)
        v_series.append(CN.SerieRecurso(uid, "disponibilidade", MT.serie("disponibilidade", t, um, p_real, None)))
    prev_nucleo = CN.ConjuntoPrevisao(f"prev-modelo-{stored.scenario_uid[:8]}-v{stored.version}", emis,
                                      tuple(CN.SerieRecurso(u, g, x) for (u, g), x in sorted(tabela.items())), p_prev)
    real_nucleo = CN.Realizacao(f"syn-realizacao-{stored.scenario_uid[:8]}-v{stored.version}", "sintetica",
                                tuple(sorted(v_series, key=lambda x: (x.uid, x.grandeza))), p_real)
    verdade = real_nucleo
    if bloco["pcc"]["modo"] == "conectado":
        p_pcc = MT.proc_declarada(bloco["pcc"]["procedencia"], "pcc", stored) \
            if E.procedencia_declarada(bloco["pcc"]["procedencia"]) else p_prev
        tabela[(MT.UID_PCC, "disponibilidade")] = MT.serie("disponibilidade", t, um, p_pcc,
                                                           bloco["pcc"]["tarifa_emissao_utc"] or emis)
        v_series.append(CN.SerieRecurso(MT.UID_PCC, "disponibilidade", MT.serie("disponibilidade", t, um, p_real, None)))
        verdade = CN.Realizacao(real_nucleo.realizacao_uid, "sintetica",
                                tuple(sorted(v_series, key=lambda x: (x.uid, x.grandeza))), p_real)
        c = bloco["pcc"]
        for k, rot in (("tarifa_importacao_R_kWh", "importação"), ("tarifa_exportacao_R_kWh", "exportação")):
            if c[k] is not None and len(c[k]) != t.K:
                pf.add(ERROR, "pcc", f"A tarifa de {rot} tem {len(c[k])} valor(es); a missão tem {t.K} intervalos (um preço "
                                     "por intervalo; nenhum rateio nem repetição implícita).")
        te = c["tarifa_emissao_utc"]
        if te is not None and ler_instante_utc(te, "e")[0] > ler_instante_utc(t.inicio_utc, "t")[0]:
            pf.add(ERROR, "causalidade", f"Tarifa de decisão emitida em {te}, depois do início da missão: preço futuro na "
                                         "decisão — execução bloqueada.", code="tarifa_nao_causal")
        if pf.count(ERROR):
            return None
    return prev, real, tabela, verdade, fonte_real, prev_nucleo, real_nucleo


def _realizacao_renovavel() -> dict:
    return {"tipo": "igual_a_previsao",
            "descricao": "Potencial REALIZADO = potencial previsto (mesmo modelo físico sobre o mesmo clima): a simulação não "
                         "tem erro de previsão renovável. Previsão e realização continuam objetos e fontes separados (o "
                         "controlador recebe só a previsão; a planta só a realização)."}


def _renovaveis(pf: PreflightV2, store, stored, doc: dict, bloco: dict, t: MT.Tempo, config: dict, excl: set[str]):
    """Potencial renovável por UID derivado pelos modelos físicos sobre a previsão climática. ``None`` ⇒ bloqueio."""
    reps = [x for x in pf.represented if x["kind"] in ("pv", "wind")]
    if not reps:
        return [], None
    cl = bloco["clima"]
    entry = (doc.get("forecasts") or {}).get("climate")
    if not entry:
        pf.add(ERROR, "previsoes", f"Previsão CLIMÁTICA ausente no cenário (etapa 02): {len(reps)} equipamento(s) renovável(is) "
               "participa(m) da missão e o potencial exige o clima previsto. Nenhum perfil substituto é usado.")
        return None
    if not entry.get("timezone"):
        pf.add(ERROR, "previsoes", "A série climática não declara fuso horário: instantes UTC indeterminados.")
        return None
    if entry.get("provenance") not in ("medido", "sintetico", "referencia"):
        pf.add(ERROR, "previsoes", "Procedência da previsão climática não declarada (etapa 02).")
        return None
    obrig: set = set()
    opc: set = set()
    for x in reps:
        if x["kind"] == "pv":
            obrig |= set(RN.VARIAVEIS_FV)
        else:
            obrig |= set(RN.VARIAVEIS_EOL)
            if bloco["renovaveis"][x["id"]]["hipotese_densidade"] == "calculada_do_clima_previsto":
                obrig |= {"temperature_C", "pressure_hPa"}
                opc |= {"humidity_pct"}
    try:
        s = M.load_series("climate", entry, store.get_blob)
    except F.ForecastDataError as exc:
        pf.add(ERROR, "previsoes", f"Série climática indisponível ou corrompida: {exc}")
        return None
    emis = cl["emissao_utc"]
    if ler_instante_utc(emis, "e")[0] > ler_instante_utc(t.inicio_utc, "t")[0]:
        pf.add(ERROR, "causalidade", f"A previsão CLIMÁTICA foi declarada EMITIDA em {emis}, depois do início da missão "
               f"({t.inicio_utc}): informação futura — execução bloqueada.", code="previsao_nao_causal")
        return None
    t0 = datetime.fromisoformat(t.inicio_utc).timestamp()
    try:
        clima = RN.alinhar_clima(s, entry, t0, t.delta_s, t.K, obrig, opc, cl["semantica"], emis)
    except RN.DerivacaoInvalida as exc:
        pf.add(ERROR, "previsoes", f"Previsão climática insuficiente para o potencial renovável: {exc}",
               code="clima_insuficiente")
        return None
    pf.add(OK, "previsoes", f"Previsão climática: {t.K} × {clima.n} subamostra(s) nos instantes EXATOS da série (passo "
           f"{clima.passo_s:g} s; variáveis {', '.join(sorted(obrig))}); origem '{entry.get('source_type')}' / procedência "
           f"'{entry['provenance']}'; emissão declarada {emis} (anterior a τ₀); semântica declarada '{cl['semantica']}'.")
    if clima.n == 1:
        pf.add(WARNING, "renovaveis", "Uma única amostra climática por intervalo: o potencial médio do intervalo é P(clima) "
               "na amostra (aproximação declarada; modelos não lineares).")
    eqs = {e["id"]: e for e in config.get("equipment", [])}
    derivs = []
    for x in reps:
        eq, decl = eqs.get(x["id"]), bloco["renovaveis"][x["id"]]
        try:
            if eq is None:
                raise RN.DerivacaoInvalida("registro ausente da revisão do inventário referenciada.")
            if x["kind"] == "pv":
                ds = RN.derivar_fv(eq, float(decl["eta_conversao_barramento"]), clima, t.K)
            else:
                ds = [RN.derivar_eolica(eq, decl["hipotese_densidade"], clima, t.K)]
        except RN.DerivacaoInvalida as exc:
            pf.add(ERROR, "renovaveis", f"{x['name']}: {exc}", x["id"], code="renovavel_nao_derivavel")
            continue
        except Exception as exc:                       # noqa: BLE001 — modelo físico: falha nunca silenciosa
            pf.add(ERROR, "renovaveis", f"{x['name']}: o modelo físico falhou ({type(exc).__name__}: {str(exc)[:200]}).",
                   x["id"], code="renovavel_nao_derivavel")
            continue
        if sorted(d.uid for d in ds) != sorted(x["uids"]):
            pf.add(ERROR, "renovaveis", f"{x['name']}: os recursos derivados {sorted(d.uid for d in ds)} não coincidem com "
                   f"os da ponte 3C-0 {sorted(x['uids'])}.", x["id"])
            continue
        h = t.delta_s / 3600.0
        for d in ds:
            pf.add(OK, "renovaveis", f"{d.nome} ({d.uid}): {d.rotulo_modelo} — {t.K} médias de intervalo no barramento, pico "
                   f"{max(d.potencia_kW):.4g} kW, energia potencial {d.energia_kWh(h):.5g} kWh (disponível ≠ despachada: "
                   "o vertimento é decidido pelo EMS).", x["id"])
        derivs += ds
    if pf.count(ERROR):
        return None
    pf.add(WARNING, "realizacao", _realizacao_renovavel()["descricao"])
    return derivs, clima


def _com_renovaveis(renov, tabela: dict, verdade, prev_nucleo, real_nucleo, t: MT.Tempo, stored):
    """Acrescenta potencial e disponibilidade de cada recurso renovável à previsão (provedor) e à realização (planta)."""
    derivs, clima = renov
    if not derivs:
        return tabela, verdade, prev_nucleo, real_nucleo
    ent, um = clima.entrada, [1.0] * t.K
    tabela = dict(tabela)
    bases = {}
    vs, vr, vp = list(verdade.series), list(real_nucleo.series), list(prev_nucleo.series)
    p_real = verdade.procedencia
    for d in derivs:
        p_prev = Procedencia(ent["provenance"], f"SEEDS2 · cenário {stored.scenario_uid} v{stored.version} · potencial "
                             f"'{d.tecnologia}' derivado por {d.modelo} sobre a previsão climática "
                             f"({ent.get('label') or ent.get('source_type')})", f"forecasts.climate → {d.uid}",
                             sha256=ent["data"], observacoes=f"{RN.REGRA_AGREGACAO}; {d.hipoteses[0]}; emissão declarada "
                                                             f"{clima.emissao_utc}; tabela declarada antecipadamente")
        p_a = Procedencia("declarado_seeds2", f"SEEDS2 · cenário {stored.scenario_uid} v{stored.version}",
                          f"initialization.equipment[{d.registro}].availability", sha256=stored.fingerprint,
                          observacoes="Série constante a = 1 derivada da disponibilidade ESTÁTICA do cenário (disponível)")
        tabela[(d.uid, "potencia")] = MT.serie("potencia", t, d.potencia_kW, p_prev, clima.emissao_utc)
        tabela[(d.uid, "disponibilidade")] = MT.serie("disponibilidade", t, um, p_a, clima.emissao_utc)
        bases[d.uid] = "antes_da_disponibilidade"
        vp.append(CN.SerieRecurso(d.uid, "potencia", tabela[(d.uid, "potencia")], "antes_da_disponibilidade"))
        vp.append(CN.SerieRecurso(d.uid, "disponibilidade", tabela[(d.uid, "disponibilidade")]))
        for lista in (vs, vr):
            lista.append(CN.SerieRecurso(d.uid, "potencia", MT.serie("potencia", t, d.potencia_kW, p_real, None)))
            lista.append(CN.SerieRecurso(d.uid, "disponibilidade", MT.serie("disponibilidade", t, um, p_real, None)))
    def ordem(xs):
        return tuple(sorted(xs, key=lambda x: (x.uid, x.grandeza)))
    prev = CN.ConjuntoPrevisao(prev_nucleo.conjunto_uid, prev_nucleo.emissao_utc, ordem(vp), prev_nucleo.procedencia)
    return (tabela, CN.Realizacao(verdade.realizacao_uid, verdade.natureza, ordem(vs), verdade.procedencia), prev,
            CN.Realizacao(real_nucleo.realizacao_uid, real_nucleo.natureza, ordem(vr), real_nucleo.procedencia))


def _pemfc(pf: PreflightV2, bloco: dict, inv, stored) -> dict | None:
    """Curva q(P) do MODELO FÍSICO por registro PEMFC (gerada UMA vez por configuração física), reverificada contra o
    modelo, certificada (B04) e registrada no contrato. ``None`` ⇒ bloqueio."""
    from ems_v2 import contracts as K
    reps = [x for x in pf.represented if x["kind"] == "pemfc"]
    out: dict = {}
    disp = {d.uid: d for d in inv.dispositivos}
    for x in reps:
        decl = bloco["pemfc"][x["id"]]
        c = decl["condicoes"]
        cond = CH.CondicoesPEMFC(c["temperatura_stack_K"], c["pressao_anodo_kPag"], c["pressao_catodo_kPag"],
                                 c["pressao_ambiente_kPa"])
        d = disp[x["id"]]
        if d.modelo.referencia != CH.PERFIL_MODELO:
            pf.add(ERROR, "pemfc", f"{x['name']}: perfil {d.modelo.referencia!r} — a curva só é derivável do perfil "
                   f"{CH.PERFIL_MODELO} (modelo físico do SEEDS2).", x["id"], code="pemfc_perfil_nao_suportado")
            continue
        pmax_inv = next((v.numero for v in d.valores if v.chave == "p_max_liquida_unidade_kW"), None)
        n0 = CH.GERACOES["n"]
        try:
            curva = CH.obter_curva(cond, decl["p_min_kW"], p_max_limite_kW=pmax_inv)
        except CH.CurvaInvalida as exc:
            pf.add(ERROR, "pemfc", f"{x['name']}: {exc}", x["id"], code="pemfc_curva_invalida")
            continue
        falhas = CH.verificar_contra_modelo(curva.doc())
        if falhas:
            pf.add(ERROR, "pemfc", f"{x['name']}: dados da curva não reproduzem o modelo ({'; '.join(falhas)}).", x["id"],
                   code="pemfc_curva_divergente_do_modelo")
            continue
        cert = CH.certificado_b04(curva)
        h, cs = K.registrar_certificado_b04(cert)
        b04 = curva.b04
        reuso = "REUTILIZADA (mesma impressão digital)" if CH.GERACOES["n"] == n0 else "gerada agora"
        pf.add(OK, "pemfc", f"{x['name']}: curva q(P) do modelo físico {reuso} — impressão {curva.impressao[:12]}…; "
               f"domínio [{curva.p_min_kW:g}, {curva.p_max_kW:.4g}] kW; {len(curva.vertices)} vértices; erro relativo "
               f"máx. {100 * curva.metricas['erro_rel_max']:.3f} %; massa temporal máx. "
               f"{100 * curva.metricas['erro_massa_temporal_rel_max']:.3f} %; política {b04['politica']}.", x["id"])
        bloq = [k for k in cs if k.severidade in ("erro", "pendente")]
        sit_nucleo, _rec = K.situacao_politica_b04(cert.politica)
        if bloq and all(k.severidade == "pendente" and k.codigo == "politica_b04_nao_aprovada" for k in bloq):
            pf.add(ERROR, "pemfc", f"{x['name']}: certificação B04 AGUARDANDO APROVAÇÃO do responsável (política "
                   f"{b04['politica']}, situação registrada no NÚCLEO '{sit_nucleo}'). A curva atende aos limiares "
                   "propostos (critérios recomputados pelo núcleo), mas nenhuma curva derivada do modelo entra no MILP "
                   "sem política aprovada.", x["id"], code="b04_aguardando_aprovacao")
            continue
        if bloq:
            pf.add(ERROR, "pemfc", f"{x['name']}: certificado B04 REPROVADO pelo contrato: "
                   + "; ".join(f"{k.codigo} ({k.mensagem})" for k in bloq[:4]), x["id"], code="b04_reprovada")
            continue
        proc = Procedencia("referencia", "h2_pemfc · modelo físico parametrizado APROXIMADO (escala Horizon VLIIPro50-22)",
                           f"B04:{curva.impressao}", sha256=h,
                           observacoes=f"curva estacionária derivada do modelo; certificado B04 {h[:12]}… VERIFICADO "
                                       "(recomputado); não valida o modelo nem o equipamento")
        from ems_v2.parameters import Parametro
        from . import pemfc_dinamica as DY
        mev = DY.massas_eventos(cond, float(decl["p_min_kW"]), float(decl["temperatura_ambiente_C"]))
        pm = Procedencia("referencia", "h2_pemfc · Equivalent65kWHorizonDynamicModel (modelo dinâmico APROXIMADO)",
                         f"massas por evento · curva {curva.impressao[:12]}", sha256=curva.impressao,
                         observacoes=mev["metodo"])
        massas = (Parametro(float(mev["m_partida_kg"]), "kg", pm), Parametro(float(mev["m_parada_kg"]), "kg", pm))
        out[x["id"]] = {"curva": curva, "certificado": cert, "hash_certificado": h, "condicoes": cond,
                        "massas_eventos": mev, "massas_pwl": massas,
                        "curva_pwl": K.CurvaPWL(tuple(curva.vertices), "real_certificada_b04", proc),
                        "temperatura_ambiente_C": decl["temperatura_ambiente_C"], "declaracao": decl}
        if decl["p_min_kW"] < 10.0 - 1e-9:
            pf.add(WARNING, "pemfc", f"{x['name']}: P_min declarado ({decl['p_min_kW']:g} kW) abaixo da potência de IDLE "
                   "do modelo dinâmico (10 kW, hipótese do manual ≤ 10 kW): consignas menores serão entregues como IDLE "
                   "(excesso registrado na verificação dinâmica).", x["id"])
        if decl["rampa_kW_min"] > 120.0 + 1e-9:
            pf.add(WARNING, "pemfc", f"{x['name']}: rampa declarada ({decl['rampa_kW_min']:g} kW/min) acima da menor rampa "
                   "do manual (2 kW/s = 120 kW/min): o modelo dinâmico limitará a resposta.", x["id"])
        if decl["abstracao"] == "instantanea_unidade_quente":
            pf.add(WARNING, "pemfc", f"{x['name']}: abstração INSTANTÂNEA declarada (D05): o MILP liga/desliga dentro do "
                   "intervalo; a partida física (30 s quente / 600 s fria, IDLE 10 kW, rampas 2/3,5 kW/s) é avaliada a "
                   "posteriori pelo modelo dinâmico — não é validação física.", x["id"])
    if pf.count(ERROR):
        return None
    return out


def _com_disponibilidade_geradores(uids, tabela, verdade, prev_nucleo, real_nucleo, t: MT.Tempo, stored, bloco):
    """Disponibilidade a = 1 POR UNIDADE geradora (disponível no cenário) na previsão do provedor e na realização — a
    mesma condição ESTÁTICA declarada às fontes de disponibilidade da execução (nenhuma herança implícita)."""
    if not uids:
        return tabela, verdade, prev_nucleo, real_nucleo
    um = [1.0] * t.K
    emis = bloco["demanda"]["emissao_utc"]
    tabela = dict(tabela)
    vs, vr, vp = list(verdade.series), list(real_nucleo.series), list(prev_nucleo.series)
    for u in uids:
        p_a = Procedencia("declarado_seeds2", f"SEEDS2 · cenário {stored.scenario_uid} v{stored.version}",
                          f"initialization.equipment[{u.split('#')[0]}].availability", sha256=stored.fingerprint,
                          observacoes="Série a = 1 por UNIDADE derivada da disponibilidade estática do cenário (disponível)")
        tabela[(u, "disponibilidade")] = MT.serie("disponibilidade", t, um, p_a, emis)
        vp.append(CN.SerieRecurso(u, "disponibilidade", tabela[(u, "disponibilidade")]))
        for lista in (vs, vr):
            lista.append(CN.SerieRecurso(u, "disponibilidade", MT.serie("disponibilidade", t, um, verdade.procedencia, None)))
    def ordem(xs):
        return tuple(sorted(xs, key=lambda x: (x.uid, x.grandeza)))
    return (tabela, CN.Realizacao(verdade.realizacao_uid, verdade.natureza, ordem(vs), verdade.procedencia),
            CN.ConjuntoPrevisao(prev_nucleo.conjunto_uid, prev_nucleo.emissao_utc, ordem(vp), prev_nucleo.procedencia),
            CN.Realizacao(real_nucleo.realizacao_uid, real_nucleo.natureza, ordem(vr), real_nucleo.procedencia))


def documento_pemfc(pem: dict) -> dict:
    """Conteúdo de ``v2/pemfc.json``: curva (inicialização, pontos do modelo, vértices, erros, B04) + certificado do
    núcleo por registro PEMFC. Comprometido no manifesto ANTES da execução."""
    from ems_v2.contracts import para_dict
    return {"formato": "seeds2-milp-mpc-pemfc", "versao": 1,
            "registros": {u: {"curva": x["curva"].doc(), "certificado_b04": para_dict(x["certificado"]),
                              "hash_certificado_b04": x["hash_certificado"],
                              "temperatura_ambiente_C": x["temperatura_ambiente_C"],
                              "massas_eventos": {k: (float(v) if isinstance(v, (int, float)) else v)
                                                 for k, v in x["massas_eventos"].items()},
                              "declaracao": x["declaracao"]} for u, x in sorted(pem.items())},
            "nota": "Curva gerada UMA vez por configuração física e reutilizada em toda a missão (planejador e janelas MPC). "
                    "A reabertura re-registra o certificado RECOMPUTANDO os critérios a partir destes dados; nenhum "
                    "modelo é reexecutado."}


def _itens_ponte(pf: PreflightV2, rel) -> None:
    mapa = {"inventario": "ponte", "parametros": "parametros", "cenario": "ponte", "tempo": "tempo",
            "previsoes": "previsoes", "realizacao": "realizacao", "separacao": "causalidade", "referencias": "ponte",
            "restricoes": "ponte", "sinteticos": "ponte", "contrato": "ponte", "politicas": "ponte", "solver": "ponte"}
    sint = 0
    for i in rel.itens:
        if i.codigo == "dado_sintetico_em_ensaio":
            sint += 1
            continue
        nivel = {"bloqueante": ERROR, "advertencia": WARNING, "aceitavel": OK}[i.severidade]
        pf.add(nivel, mapa.get(i.area, "ponte"), f"[ponte 3C-0 · {AREAS_PONTE.get(i.area, i.area)}] "
               + (f"{i.codigo} · {i.caminho}: " if i.severidade != "aceitavel" else "") + i.mensagem, code=i.codigo)
    if sint:
        pf.add(WARNING, "ponte", f"{sint} dado(s) de procedência SINTÉTICA (declarações, previsão ou realização): aceitos "
                                 "somente por ser um ENSAIO rotulado; a rodada fica marcada como sintética e não é estudo "
                                 "físico.", code="dado_sintetico_em_ensaio")


def _matriz(pf: PreflightV2, mont: MT.Montagem, bloco: dict, doc: dict) -> None:
    """Matriz fonte → transformação → validação → registro → vista do que efetivamente chega ao motor."""
    t, e3, mod = mont.tempo, mont.nucleo, mont.modelo
    REG_MODELO, REG_INT, REG_FRONT = "v2/modelo.json", "v2/intervalos.csv", "v2/fronteiras.csv"
    VAL_3A = "contracts.validar_entrada (3A/3B-P) + ponte 3C-0 (matriz de parâmetros)"
    rows = pf.matriz
    dem = e3.base.demandas[0]
    rows.append(_linha("Demanda prevista (disponível ao decidir)", MT.UID_DEMANDA, f"{t.K} valores", "kW",
                       _proc_txt(dem.potencia.procedencia), "alinhamento exato à malha (sem reamostragem); semântica "
                       "declarada: média de intervalo", "validar_serie + alinhar_a_malha + causalidade (emissão <= τ₀); "
                       "vínculo ao instantâneo K6 em cada janela", f"{REG_INT} (demanda_prevista_kW)", "Operação · Respostas"))
    rows.append(_linha("Demanda realizada (simulada)", MT.UID_DEMANDA, f"{t.K} valores", "kW",
                       _proc_txt(mont.verdade.procedencia), E.REALIZACOES[bloco["realizacao"]["tipo"]],
                       "validar_realizacao + separação previsão × realização (3C-0); entregue só à planta",
                       f"{REG_INT} (demanda_realizada_kW)", "Operação"))
    est = {str(s.uid): s for s in e3.base.estados_baterias}
    for b in e3.base.baterias:
        u = str(b.uid)
        for nome, par in (("Capacidade energética C_b", b.capacidade_kWh), ("SOC mínimo s_min", b.soc_min),
                          ("SOC máximo s_max", b.soc_max), ("Eficiência de carga η_c", b.eta_carga),
                          ("Eficiência de descarga η_d", b.eta_descarga), ("Potência máx. de carga (barramento)", b.p_carga_max_kW),
                          ("Potência máx. de descarga (barramento)", b.p_descarga_max_kW)):
            rows.append(_par_linha(nome, u, par, VAL_3A, REG_MODELO, "Parâmetros · Fontes"))
        if b.custo_throughput is not None:
            rows.append(_par_linha("Custo de throughput c_thr", u, b.custo_throughput, VAL_3A, REG_MODELO, "Parâmetros"))
        rows.append(_linha("Hipótese de autodescarga", u, b.hipotese_autodescarga, "", "declarada na estratégia",
                           "nenhuma", VAL_3A, REG_MODELO, "Parâmetros"))
        if u in est:
            rows.append(_par_linha("Energia inicial e₀ (fronteira 0)", u, est[u].energia_kWh,
                                   "limites [s_min·C, s_max·C] (validar_entrada)", f"{REG_FRONT} (fronteira 0)",
                                   "Operação · Diagrama"))
    c = bloco["pcc"]
    fp = _proc_txt(mod.pcc.procedencia)
    rows.append(_linha("PCC — modo e sentidos", MT.UID_PCC, f"{c['modo']} · {c['sentidos']}", "", fp, "nenhuma",
                       "validar_entrada_3c3 + coerência com o modo operativo do inventário", REG_MODELO, "Parâmetros · Diagrama"))
    if mod.conectado:
        for k, rot in (("limite_importacao_kW", "Limite contratado de importação"),
                       ("limite_exportacao_kW", "Limite contratado de exportação")):
            if c[k] is not None:
                rows.append(_linha(rot, MT.UID_PCC, c[k], "kW", fp, f"série constante de {t.K} intervalos",
                                   "validar_entrada_3c3", REG_MODELO, "Parâmetros"))
        for gr, vals in mont.tarifas.items():
            rows.append(_linha(f"Tarifa de {gr} (decisão = liquidação declarada)", MT.UID_PCC,
                               f"{_fmt(min(vals))}–{_fmt(max(vals))}", "R$/kWh", fp + f" · rótulo: {c['rotulo_tarifa']}",
                               "um bloco por intervalo; perfil de liquidação próprio com os mesmos valores",
                               "validar_perfil + seleção causal por emissão em cada τ_k", f"{REG_INT} (tarifa_*)",
                               "Operação · Análise"))
    for d in mont.renovaveis:
        rows.append(_linha(f"Potencial renovável disponível A ({d.tecnologia})", d.uid,
                           f"{t.K} valores · pico {max(d.potencia_kW):.4g}", "kW",
                           f"previsão climática do cenário ({mont.clima.entrada.get('provenance')}) + inventário",
                           f"{d.modelo} por subamostra; {RN.REGRA_AGREGACAO} ({mont.clima.n} por intervalo)"
                           + (f"; × η = {d.parametros['eta_conversao_barramento']:g}" if d.tecnologia == "fv" else ""),
                           "domínio do modelo + cobertura exata do clima + causalidade (emissão <= τ₀) + validar_renovavel "
                           "(3A) + chaves/base da previsão em cada janela (3C-2)", "v2/renovaveis.json + v2/intervalos.csv "
                           f"({d.uid}|A_*)", "Operação · Respostas"))
        rows.append(_linha("Injeção aplicada P_R e vertimento", d.uid, "decisão do EMS", "kW", "MILP 3C-4 + planta 3C-3",
                           "P_R <= a·A (M03-v1.1); vertimento = a·A − P_R", "auditoria integral (renovavel_acima_do_observado)",
                           f"v2/intervalos.csv ({d.uid}|P_R_kW, {d.uid}|vertimento_kW)", "Operação"))
    g = bloco["planejador"]
    fpol = _proc_txt(mont.proc_politicas)
    rows.append(_linha("Malha temporal", "missão", f"Δ = {t.delta_min} min · N = {t.N} · m = {t.m} · K_M = {t.K} · H_L = {t.H_L}",
                       "", fpol, "início da missão convertido para UTC pelo fuso declarado", "validar_malha + "
                       "validar_configuracao_mpc + validar_configuracao_planejador", "manifesto + v2/indice.json",
                       "Parâmetros · Respostas"))
    rows.append(_linha("Termo terminal Φ_L do horizonte longo", "planejador", g["termo_longo"]["tipo"], "R$", fpol,
                       "nenhuma", "validar_termo_declarado", REG_MODELO, "Respostas · Análise"))
    rows.append(_linha("Sinal de valor futuro e degradação", "planejador",
                       f"{g['tipo_sinal']} · {g['politica_atualizacao']} · degradação {g['degradacao']}", "", fpol,
                       "nenhuma", "validar_configuracao_planejador", "v2/sinais.json + v2/janelas.csv", "Respostas"))
    rows.append(_linha("Solver", "HiGHS", f"limite {mont.solver.time_limit_s:g} s · gaps {mont.solver.rel_gap:g}/"
                       f"{mont.solver.abs_gap:g} · threads {mont.solver.threads} · semente {mont.solver.semente}", "",
                       f"declarado na estratégia ({E.ROTULO_REFERENCIA})", "nenhuma", "milp.config.validar_configuracao",
                       "v2/janelas.csv (terminação, gap, tempos)", "Análise"))
    _ = doc


__all__ = ["AREA_LABELS", "ERROR", "ESCOPO", "INFO", "Item", "LEVEL_LABELS", "NAO_REPRESENTAVEL", "OK", "PreflightV2",
           "WARNING", "preparar"]
