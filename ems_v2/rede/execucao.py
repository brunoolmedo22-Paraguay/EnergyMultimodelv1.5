"""Execução conectada do perfil 3C-3: intercâmbio PROGRAMADO × REALIZADO, ajuste local do PCC e liquidação.

Só biblioteca padrão. Nenhum tipo 3C-0/3C-1 foi alterado; este módulo acrescenta tipos PRÓPRIOS:

* ``plano_de_resultado_3c3`` — resultado 3C-3 ACEITO → ``PlanoDespacho`` 3C-0 (consignas físicas dos recursos internos;
  ``versao_formulacao = v1.1-3C-3``, ``hash_entrada`` = SHA-256 da entrada 3C-3) + ``PlanoRede3C3`` (intercâmbio
  PROGRAMADO P_imp/P_exp por intervalo, custo de rede PLANEJADO, plano de commitment do núcleo), ligado ao hash do
  plano. Resultado rejeitado ⇒ ``ContratoInvalido`` (nunca vira plano);
* ``PoliticaAjustePCC`` — política EXPLÍCITA (sem padrão) para a resposta realizada:
  - ``tipo``: ``sem_ajuste`` (intercâmbio realizado = programado; qualquer desvio de balanço ⇒ inexequível) ×
    ``ajuste_local_algebrico`` (com as demais consignas já executadas e a demanda OBSERVADA, o intercâmbio líquido é o
    exigido pelo balanço, SÓ se: conexão declarada, PCC disponível no intervalo, sentido permitido, dentro do limite
    contratado e com evidência — observações obrigatórias e, na conciliação, a MEDIÇÃO dos registros do PCC);
  - ``injecao_renovavel``: ``consigna_exata`` (regra 3C-0: consigna > disponível ⇒ inexequível) ×
    ``limitada_pela_disponibilidade`` (P_R_real = min(consigna, disponível observado); a diferença é DESVIO FÍSICO
    registrado — nunca corrigido em silêncio; o excedente além da consigna NÃO é injetado: permanece vertido);
  - ``liquidacao``: ``energia_medida_tarifa_aplicavel`` (referência sintética: h·(c_imp P_imp_real − c_exp P_exp_real)
    com os perfis de LIQUIDAÇÃO) × ``desvio_diferenciado`` (programado aos preços de liquidação + desvio líquido aos
    preços de desvio DECLARADOS);
* ``ExecutorAlgebricoConectado3C3`` — dublê ALGÉBRICO (natureza ``algebrico_referencia``; NÃO é modelo físico nem
  controle primário de frequência): herda TODAS as verificações de commitment do executor 3C-1 (memória, rampas,
  permanências, disponibilidade efetiva por fonte declarada) e substitui o passo de barramento 3C-0 pelo passo
  conectado. Saturação do PCC, sentido proibido, PCC indisponível, isolamento ⇒ falha CLASSIFICADA (inexequível), sem
  importação ilimitada, ENS inventada nem alteração retroativa de bateria/PEMFC;
* ``desvios_intercambio`` / ``contabilidade_realizada_3c3`` — desvio programado × realizado e custos INCORRIDOS
  (contabilidade 3C-1 inalterada + gasto de importação, crédito de exportação e, se declarado, desvio).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import timedelta

from ..audit import Tolerancias
from ..compromisso.contrato import hash_entrada_3c1
from ..compromisso.memoria import garantia
from ..diagnostics import Constatacao, ContratoInvalido, erro
from ..ponte import CONTRATO_VERSAO
from ..ponte.canonico import sha256
from ..ponte.compromisso import (ExecutorAlgebricoCommitment3C1, PlanoCommitment3C1, contabilidade_realizada_3c1)
from ..ponte.execucao import (ConsignaRecurso, EstadoArmazenamento, EstadoGeracao, EstadoMicrorrede, PassoAplicado,
                              PlanoDespacho, TrajetoriaExecutada, TrajetoriaPlanejada, hash_plano, validar_plano)
from ..ponte.registro import ComponenteCusto, CustoRealizado
from ..provenance import Procedencia, validar_procedencia
from ..timegrid import ler_instante_utc
from . import FORMULACAO_3C3
from .contrato import EntradaRede3C3, PerfilTarifario, hash_entrada_3c3, hash_perfil, preco_no_intervalo, \
    validar_perfil, valor_no_intervalo

TIPOS_AJUSTE = {
    "sem_ajuste": "Intercâmbio realizado = programado; qualquer desvio de balanço no intervalo ⇒ inexequível",
    "ajuste_local_algebrico": "Intercâmbio líquido realizado = o exigido pelo balanço com as consignas executadas e a "
                              "demanda/recurso OBSERVADOS, dentro de disponibilidade, sentidos e limites contratados",
}
INJECOES_RENOVAVEL = {
    "consigna_exata": "Regra 3C-0: P_R aplicado = consigna; consigna > disponível observado ⇒ inexequível",
    "limitada_pela_disponibilidade": "P_R_real = min(consigna, disponível observado); a diferença é DESVIO FÍSICO "
                                     "registrado; excedente além da consigna NÃO é injetado (permanece vertido)",
}
LIQUIDACOES = {
    "energia_medida_tarifa_aplicavel": "Referência sintética: h (c_imp P_imp_real − c_exp P_exp_real) com perfis de "
                                       "liquidação (contratual conhecida ou aplicável à liquidação)",
    "desvio_diferenciado": "Programado aos preços de liquidação + desvio líquido (real − programado) aos preços de "
                           "desvio positivo/negativo DECLARADOS",
}
NATUREZAS_LIQUIDACAO = ("contratual_conhecida", "aplicavel_liquidacao")


# ------------------------------------------------------------------------------------------------ política
@dataclass(frozen=True)
class PoliticaAjustePCC:
    tipo: str                                           # TIPOS_AJUSTE
    injecao_renovavel: str                              # INJECOES_RENOVAVEL
    liquidacao: str                                     # LIQUIDACOES
    tarifa_liquidacao_importacao: PerfilTarifario | None
    tarifa_liquidacao_exportacao: PerfilTarifario | None
    tarifa_desvio_positivo: PerfilTarifario | None
    tarifa_desvio_negativo: PerfilTarifario | None
    procedencia: Procedencia | None
    justificativa: str


def hash_politica_ajuste(p: PoliticaAjustePCC) -> str:
    return sha256(p)


def validar_politica_ajuste(p: PoliticaAjustePCC, e: EntradaRede3C3) -> list[Constatacao]:
    if not isinstance(p, PoliticaAjustePCC):
        return [erro("politica_ajuste_invalida", "politica_ajuste", f"Esperada PoliticaAjustePCC; {type(p).__name__}.")]
    out: list[Constatacao] = list(validar_procedencia(p.procedencia, "politica_ajuste.procedencia"))
    if not p.justificativa.strip():
        out.append(erro("politica_ajuste_sem_justificativa", "politica_ajuste.justificativa", "Justificativa exigida."))
    if p.tipo not in TIPOS_AJUSTE:
        out.append(erro("tipo_ajuste_invalido", "politica_ajuste.tipo", f"{p.tipo!r} (sem padrão)."))
    if p.injecao_renovavel not in INJECOES_RENOVAVEL:
        out.append(erro("injecao_renovavel_invalida", "politica_ajuste.injecao_renovavel",
                        f"{p.injecao_renovavel!r} (sem padrão)."))
    if p.liquidacao not in LIQUIDACOES:
        out.append(erro("liquidacao_invalida", "politica_ajuste.liquidacao", f"{p.liquidacao!r} (sem padrão)."))
    tarifas = ("tarifa_liquidacao_importacao", "tarifa_liquidacao_exportacao", "tarifa_desvio_positivo",
               "tarifa_desvio_negativo")
    if not e.conectado:
        if p.tipo != "sem_ajuste":
            out.append(erro("ajuste_em_operacao_isolada", "politica_ajuste.tipo",
                            "Operação isolada: nenhum ajuste do PCC existe (declarar 'sem_ajuste')."))
        for n in tarifas:
            if getattr(p, n) is not None:
                out.append(erro("isolado_com_tarifa", f"politica_ajuste.{n}", "Operação isolada sem liquidação de rede."))
        return out
    cu = e.pcc.contrato_uid

    def perfil(nome, gr, exigido):
        pf = getattr(p, nome)
        if pf is None:
            if exigido:
                out.append(erro("tarifa_liquidacao_ausente", f"politica_ajuste.{nome}",
                                f"Liquidação de {gr} exige perfil declarado (nenhum preço presumido)."))
            return
        if not exigido:
            out.append(erro("tarifa_liquidacao_sem_uso", f"politica_ajuste.{nome}", "Perfil declarado sem uso."))
            return
        c = validar_perfil(pf, f"politica_ajuste.{nome}", grandeza=gr, contrato_uid=cu)
        out.extend(c)
        if not c and pf.natureza not in NATUREZAS_LIQUIDACAO:
            out.append(erro("preco_previsto_na_liquidacao", f"politica_ajuste.{nome}.natureza",
                            f"{pf.natureza!r}: um preço PREVISTO nunca liquida (exigido {NATUREZAS_LIQUIDACAO})."))
    perfil("tarifa_liquidacao_importacao", "importacao", e.importa)
    rem = e.exporta and e.economia.remuneracao_exportacao == "remunerada"
    perfil("tarifa_liquidacao_exportacao", "exportacao", rem)
    dif = p.liquidacao == "desvio_diferenciado"
    perfil("tarifa_desvio_positivo", "desvio_positivo", dif)
    perfil("tarifa_desvio_negativo", "desvio_negativo", dif)
    return out


# ------------------------------------------------------------------------------------------------ plano
@dataclass(frozen=True)
class PlanoRede3C3:
    versao_contrato: int
    perfil: str                                   # FORMULACAO_3C3
    hash_plano: str                               # SHA-256 do PlanoDespacho associado
    hash_entrada_3c3: str
    modo_conexao: str
    pcc_uid: str
    indice_fronteira_inicial: int
    importacao_programada_kW: tuple[float, ...]   # N intervalos
    exportacao_programada_kW: tuple[float, ...]
    custo_rede_planejado_R: dict[str, float]      # termos de rede do OBJETIVO (janela inteira; não é custo incorrido)
    hash_tarifas_decisao: dict[str, str]
    commitment: PlanoCommitment3C1


def hash_plano_rede(p: PlanoRede3C3) -> str:
    return sha256(p)


def plano_de_resultado_3c3(res, e: EntradaRede3C3, *, indice_fronteira_inicial: int = 0
                           ) -> tuple[PlanoDespacho, PlanoRede3C3]:
    if not getattr(res, "aceito", False) or getattr(res, "despacho", None) is None:
        raise ContratoInvalido([erro("plano_de_solucao_nao_aceita", "resultado",
                                     f"Estado {getattr(res, 'estado_despacho', '?')!r}: nenhum plano é criado de solução "
                                     "não aceita (auditoria 3C-3/integridade).")])
    he = hash_entrada_3c3(e)
    if res.hash_entrada != he or getattr(res, "versao_formulacao", None) != FORMULACAO_3C3:
        raise ContratoInvalido([erro("plano_entrada_divergente", "resultado.hash_entrada",
                                     "O resultado não corresponde à entrada 3C-3 fornecida.")])
    desp, m, b = res.despacho, e.base.malha, e.base
    cons: list[ConsignaRecurso] = []
    est: list[TrajetoriaPlanejada] = []
    for uid in sorted(desp.get("renovaveis", {})):
        cons.append(ConsignaRecurso(uid, "P_R", "kW", tuple(desp["renovaveis"][uid]["P_R"])))
    for uid in sorted(desp.get("baterias", {})):
        x = desp["baterias"][uid]
        cons += [ConsignaRecurso(uid, "P_c", "kW", tuple(x["P_c"])), ConsignaRecurso(uid, "P_d", "kW", tuple(x["P_d"]))]
        est.append(TrajetoriaPlanejada(uid, "e", "kWh", tuple(x["e"])))
    for uid in sorted(desp.get("geradores", {})):
        g = desp["geradores"][uid]
        cons += [ConsignaRecurso(uid, "u", "1", tuple(float(round(v)) for v in g["u"])),
                 ConsignaRecurso(uid, "p", "kW", tuple(g["p"]))]
    for uid in sorted(desp.get("demandas", {})):
        cons.append(ConsignaRecurso(uid, "ell", "kW", tuple(desp["demandas"][uid]["ell"])))
    if desp.get("descarte") is not None and b.politica_servico.descarte is not None:
        cons.append(ConsignaRecurso(str(b.politica_servico.descarte.uid), "d", "kW", tuple(desp["descarte"])))
    p = PlanoDespacho(CONTRATO_VERSAO, b.microrrede_uid, b.cenario_uid, he, res.motor_id, res.versao_formulacao,
                      res.classificacao, res.estado_despacho, m.inicio().isoformat(), m.delta_s, m.N,
                      indice_fronteira_inicial, tuple(cons), tuple(est),
                      {k: float(v) for k, v in res.custos_modelo.items()})
    c = validar_plano(p)
    if c:
        raise ContratoInvalido(c)
    mem = tuple(replace(x, indice_fronteira=indice_fronteira_inicial + m.N) for x in res.memoria_terminal)
    gar, obr = garantia(mem)
    hp = hash_plano(p)
    pc = PlanoCommitment3C1(CONTRATO_VERSAO, hp, hash_entrada_3c1(e.compromisso), e.compromisso.politica_permanencia.tipo,
                            gar, mem, dict(obr), dict(res.eventos), res.custos_modelo.get("eventos"))
    ic = res.intercambio or {}
    zeros = tuple(0.0 for _ in range(m.N))
    imp = tuple(max(0.0, float(v)) for v in ic.get("P_imp", zeros))
    exp = tuple(max(0.0, float(v)) for v in ic.get("P_exp", zeros))
    if len(imp) != m.N or len(exp) != m.N or not all(math.isfinite(v) for v in imp + exp):
        raise ContratoInvalido([erro("intercambio_programado_invalido", "resultado.intercambio", "N valores finitos.")])
    pr = PlanoRede3C3(CONTRATO_VERSAO, FORMULACAO_3C3, hp, he, e.pcc.modo, str(e.pcc.uid), indice_fronteira_inicial,
                      imp, exp, {k: float(res.custos_modelo[k]) for k in ("importacao_rede", "exportacao_rede")
                                 if k in res.custos_modelo}, dict(getattr(res, "hash_tarifas", {}) or {}), pc)
    return p, pr


def programa_de_plano(pr: PlanoRede3C3) -> dict[int, tuple[float, float]]:
    """Intercâmbio programado indexado pelo intervalo GLOBAL (fronteira inicial do intervalo)."""
    return {pr.indice_fronteira_inicial + j: (pr.importacao_programada_kW[j], pr.exportacao_programada_kW[j])
            for j in range(len(pr.importacao_programada_kW))}


# ------------------------------------------------------------------------------------------------ executor
@dataclass(frozen=True)
class RegistroPassoPCC:
    """Evidência de UM intervalo executado no PCC (o que foi programado, observado, exigido e efetivamente trocado)."""
    indice_global: int
    disponibilidade_observada: float | None
    importacao_programada_kW: float
    exportacao_programada_kW: float
    liquido_exigido_kW: float                     # pelo balanço com as consignas executadas e o entorno observado
    importacao_realizada_kW: float
    exportacao_realizada_kW: float
    renovavel_consigna_kW: float                  # Σ consignas P_R
    renovavel_efetiva_kW: float                   # Σ P_R efetivamente injetado
    importacao_medida_kW: float | None
    exportacao_medida_kW: float | None
    ajuste: str                                   # "nenhum" | "ajuste_local_algebrico"


class _PassoBarramentoConectado:
    """Substitui o passo 3C-0 (``ExecutorAlgebricoReferencia``) com a mesma álgebra para bancos/geradores/demanda e o
    balanço COM o PCC. Usa só parâmetros DECLARADOS e o entorno OBSERVADO; nada é presumido."""

    def __init__(self, dono: "ExecutorAlgebricoConectado3C3"):
        self.d = dono

    def avancar(self, estado, consignas, entorno, delta_s) -> PassoAplicado:
        d, e = self.d, self.d.e
        b = e.base
        tol, h = d.tol, delta_s / 3600.0
        c: list[Constatacao] = []

        def val(k: str, fonte: dict, nome: str) -> float | None:
            v = fonte.get(k)
            if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                c.append(erro(f"{nome}_ausente", k, f"{nome} ausente para {k}: nada é presumido."))
                return None
            return float(v)
        inicio = estado.instante_utc
        lim_i = valor_no_intervalo(e.pcc.limite_importacao, inicio, delta_s) if e.importa else 0.0
        lim_e = valor_no_intervalo(e.pcc.limite_exportacao, inicio, delta_s) if e.exporta else 0.0
        escala = max([1.0] + [max(float(v) for v in r.potencial.valores) for r in b.renovaveis]
                     + [float(x.p_descarga_max_kW.valor) for x in b.baterias]
                     + [float(g.p_max_kW.valor) for g in b.geradores] + [abs(lim_i or 0.0), abs(lim_e or 0.0)])
        tolP = tol.potencia_abs_kW + tol.potencia_rel_escala * escala
        aplicado = {k: float(v) for k, v in consignas.items()}
        injecao, ren_cmd, ren_ef = 0.0, 0.0, 0.0
        for r in b.renovaveis:
            uid = str(r.uid)
            p = val(f"{uid}|P_R", consignas, "consigna")
            A, a = val(f"{uid}|potencia", entorno, "realizacao"), val(f"{uid}|disponibilidade", entorno, "realizacao")
            if None in (p, A, a):
                continue
            util = A * a if r.base_potencial == "antes_da_disponibilidade" else A
            if p < -tolP:
                c.append(erro("consigna_inexequivel_renovavel", uid, f"P_R = {p} kW < 0."))
                continue
            if d.politica.injecao_renovavel == "consigna_exata" or p <= util + tolP:
                if p > util + tolP:
                    c.append(erro("consigna_inexequivel_renovavel", uid,
                                  f"P_R = {p} kW > {util} kW disponíveis observados (política 'consigna_exata')."))
                ef = p
            else:
                ef = util                         # limitada pela disponibilidade: desvio físico registrado
            aplicado[f"{uid}|P_R"] = ef
            ren_cmd, ren_ef, injecao = ren_cmd + p, ren_ef + ef, injecao + ef
        novos_b = []
        for x in sorted(b.baterias, key=lambda y: str(y.uid)):
            uid = str(x.uid)
            pc, pd = val(f"{uid}|P_c", consignas, "consigna"), val(f"{uid}|P_d", consignas, "consigna")
            st = estado.bateria(uid)
            if st is None:
                c.append(erro("estado_ausente", uid, "Bateria sem estado na fronteira."))
                continue
            if None in (pc, pd):
                continue
            C = float(x.capacidade_kWh.valor)
            if pc < -tolP or pd < -tolP or pc > float(x.p_carga_max_kW.valor) + tolP \
                    or pd > float(x.p_descarga_max_kW.valor) + tolP or min(pc, pd) > tolP:
                c.append(erro("consigna_inexequivel_bateria", uid, f"P_c = {pc}, P_d = {pd} kW fora dos limites M06."))
            alfa = 1.0 if x.hipotese_autodescarga == "nao_modelada_alpha_1" else math.exp(
                -float(x.autodescarga_1_h.valor) * h)
            e1 = alfa * st.energia_kWh + h * (float(x.eta_carga.valor) * pc - pd / float(x.eta_descarga.valor))
            tolE = tol.energia_abs_kWh + tol.energia_rel_capacidade * C
            if not (float(x.soc_min.valor) * C - tolE <= e1 <= float(x.soc_max.valor) * C + tolE):
                c.append(erro("estado_fora_dos_limites", uid, f"e = {e1} kWh fora de [s_min C, s_max C] (sem recorte)."))
            novos_b.append(EstadoArmazenamento(uid, e1))
            injecao += pd - pc
        novos_g = []
        for g in sorted(b.geradores, key=lambda y: str(y.uid)):
            uid = str(g.uid)
            u, p = val(f"{uid}|u", consignas, "consigna"), val(f"{uid}|p", consignas, "consigna")
            st = estado.gerador(uid)
            if st is None or None in (u, p):
                if st is None:
                    c.append(erro("estado_ausente", uid, "Gerador sem estado na fronteira."))
                continue
            lig = u > 0.5
            pmin, pmax = float(g.p_min_kW.valor), float(g.p_max_kW.valor)
            if (lig and not pmin - tolP <= p <= pmax + tolP) or (not lig and abs(p) > tolP):
                c.append(erro("consigna_inexequivel_gerador", uid, f"u = {u}, p = {p} kW fora do domínio M10."))
            mem = None if st.tempo_no_estado_s is None else (st.tempo_no_estado_s + delta_s if lig == st.ligado else delta_s)
            novos_g.append(EstadoGeracao(uid, lig, p, mem))
            injecao += p
        demanda = 0.0
        for dm in b.demandas:
            uid = str(dm.uid)
            L, ell = val(f"{uid}|potencia", entorno, "realizacao"), val(f"{uid}|ell", consignas, "consigna")
            if L is not None and ell is not None:
                demanda += L - ell
        desc = sum(float(v) for k, v in consignas.items() if k.endswith("|d"))
        # ------------------------------------------------ PCC
        pcc = str(e.pcc.uid)
        prog = d.programado(estado, consignas, c)
        a_pcc, dados = None, prog is None
        if e.conectado:
            a_pcc = val(f"{pcc}|disponibilidade", entorno, "realizacao")
            if a_pcc is not None and a_pcc not in (0.0, 1.0):
                c.append(erro("disponibilidade_pcc_realizada_invalida", pcc, f"a = {a_pcc} ∉ {{0, 1}} (não interpretada)."))
                dados = True
            if (e.importa and lim_i is None) or (e.exporta and lim_e is None):
                c.append(erro("limite_pcc_ausente", pcc, f"Limite contratado sem cobertura em {inicio}: nada é presumido."))
        if dados or any(x.codigo.endswith("_ausente") for x in c):
            return PassoAplicado({}, estado, False, tuple(c), "dados")
        exigido = demanda + desc - injecao             # P_net necessário para fechar o balanço observado
        imp_p, exp_p = prog
        if d.politica.tipo == "sem_ajuste" or not e.conectado:
            net = imp_p - exp_p
            if abs(exigido - net) > tolP:
                c.append(erro("balanco_realizado_violado", "M02-3C3",
                              f"Balanço observado exige P_net = {exigido} kW; programado {net} kW e a política "
                              f"{d.politica.tipo!r} não admite ajuste (sem recorte, sem fonte oculta)."))
            imp_r, exp_r, ajuste = imp_p, exp_p, "nenhum"
        else:
            imp_r, exp_r, ajuste = max(0.0, exigido), max(0.0, -exigido), "ajuste_local_algebrico"
        if not e.conectado:
            if max(imp_r, exp_r) > tolP:
                c.append(erro("intercambio_em_operacao_isolada", pcc, "Operação isolada declarada: nenhum intercâmbio."))
        else:
            if a_pcc == 0.0 and max(imp_r, exp_r) > tolP:
                c.append(erro("pcc_indisponivel", pcc, f"Intercâmbio de {imp_r - exp_r} kW exigido com o PCC indisponível."))
            if imp_r > tolP and not e.importa:
                c.append(erro("importacao_proibida", pcc, f"Importação de {imp_r} kW exigida; sentido proibido."))
            if exp_r > tolP and not e.exporta:
                c.append(erro("exportacao_proibida", pcc, f"Exportação de {exp_r} kW exigida; sentido proibido."))
            if e.importa and imp_r > (lim_i or 0.0) + tolP:
                c.append(erro("pcc_saturado_importacao", pcc, f"Importação exigida {imp_r} kW > limite {lim_i} kW."))
            if e.exporta and exp_r > (lim_e or 0.0) + tolP:
                c.append(erro("pcc_saturado_exportacao", pcc, f"Exportação exigida {exp_r} kW > limite {lim_e} kW."))
        mi = me = None
        if d.exigir_medicao and e.conectado:
            mi = val(f"{e.pcc.medidor_importacao_uid}|potencia", entorno, "medicao")
            me = val(f"{e.pcc.medidor_exportacao_uid}|potencia", entorno, "medicao")
            if mi is None or me is None:
                return PassoAplicado({}, estado, False, tuple(c), "dados")
            if abs(mi - imp_r) > tolP or abs(me - exp_r) > tolP:
                c.append(erro("intercambio_medido_divergente", pcc,
                              f"Reconstruído (imp {imp_r}, exp {exp_r}) ≠ medido (imp {mi}, exp {me}) kW."))
        if c:
            return PassoAplicado({}, estado, False, tuple(c), "inexequivel")
        aplicado[f"{pcc}|P_imp"], aplicado[f"{pcc}|P_exp"] = imp_r, exp_r
        k = estado.indice_fronteira + 1
        t1 = ler_instante_utc(estado.instante_utc, "estado")[0] + timedelta(seconds=delta_s)
        d.ultimo = RegistroPassoPCC(estado.indice_fronteira, a_pcc, imp_p, exp_p, exigido, imp_r, exp_r, ren_cmd, ren_ef,
                                    mi, me, ajuste)
        novo = EstadoMicrorrede(estado.microrrede_uid, k, t1.isoformat(), tuple(novos_b), tuple(novos_g))
        return PassoAplicado(dict(sorted(aplicado.items())), novo, True, ())


class ExecutorAlgebricoConectado3C3(ExecutorAlgebricoCommitment3C1):
    """Dublê ALGÉBRICO conectado (NÃO físico; NÃO é controle primário de frequência validado).

    ``programa``: intercâmbio programado por intervalo GLOBAL ``{k: (P_imp, P_exp)}`` (conciliação); na planta, o
    programado vem do próprio comando (``<pcc>|P_imp``/``<pcc>|P_exp``) — se ambos existirem, devem coincidir.
    ``exigir_medicao``: a conciliação exige a MEDIÇÃO dos registros do PCC e a confronta com o intercâmbio reconstruído
    (divergência ⇒ inexequível, classificada como integridade pelo controlador)."""
    natureza = "algebrico_referencia"

    def __init__(self, e: EntradaRede3C3, disponibilidade: dict, politica: PoliticaAjustePCC, *,
                 programa: dict | None = None, exigir_medicao: bool = False, tol: Tolerancias = Tolerancias(),
                 identificador: str = "ref-alg-3C3"):
        c = validar_politica_ajuste(politica, e)
        if exigir_medicao and e.conectado and e.pcc.medidor_importacao_uid is None:
            c.append(erro("medidores_nao_declarados", "pcc.medidores", "Conciliação conectada exige medidores do PCC."))
        if c:
            raise ContratoInvalido(c)
        super().__init__(e.compromisso, disponibilidade, tol, identificador)
        self.e, self.politica = e, politica
        self.programa = dict(programa or {})
        self.exigir_medicao = exigir_medicao
        self._recursos = self._recursos | {str(e.pcc.uid)}
        self._base = _PassoBarramentoConectado(self)
        self.ultimo: RegistroPassoPCC | None = None

    def programado(self, estado, consignas, c: list) -> tuple[float, float] | None:
        pcc = str(self.e.pcc.uid)
        k = estado.indice_fronteira
        cmd = (consignas.get(f"{pcc}|P_imp"), consignas.get(f"{pcc}|P_exp"))
        prg = self.programa.get(k)
        if not self.e.conectado:
            if any(x not in (None, 0, 0.0) for x in cmd) or (prg is not None and any(prg)):
                c.append(erro("intercambio_programado_em_operacao_isolada", pcc, "Programa de intercâmbio em modo isolado."))
            return (0.0, 0.0)
        if None not in cmd:
            if prg is not None and (abs(prg[0] - cmd[0]) > 1e-12 or abs(prg[1] - cmd[1]) > 1e-12):
                c.append(erro("programa_pcc_contraditorio", pcc, "Comando e plano com intercâmbios distintos."))
                return None
            return (float(cmd[0]), float(cmd[1]))
        if prg is None:
            c.append(erro("programa_pcc_ausente", pcc, f"Intercâmbio programado do intervalo k = {k} ausente."))
            return None
        return (float(prg[0]), float(prg[1]))


# ------------------------------------------------------------------------------------------------ desvios
@dataclass(frozen=True)
class DesvioIntercambio:
    indice_global: int
    liquido_programado_kW: float
    liquido_realizado_kW: float
    desvio_kW: float                              # realizado − programado (positivo = importação líquida maior)


def desvios_intercambio(pr: PlanoRede3C3, traj: TrajetoriaExecutada) -> tuple[DesvioIntercambio, ...]:
    out = []
    for p in traj.passos:
        j = p.indice_plano
        prog = pr.importacao_programada_kW[j] - pr.exportacao_programada_kW[j]
        real = p.aplicado.get(f"{pr.pcc_uid}|P_imp", 0.0) - p.aplicado.get(f"{pr.pcc_uid}|P_exp", 0.0)
        out.append(DesvioIntercambio(pr.indice_fronteira_inicial + j, prog, real, real - prog))
    return tuple(out)


# ------------------------------------------------------------------------------------------------ liquidação
@dataclass(frozen=True)
class LiquidacaoPasso:
    indice_global: int
    preco_importacao: float | None
    preco_exportacao: float | None
    preco_desvio_positivo: float | None
    preco_desvio_negativo: float | None
    gasto_importacao_R: float
    receita_exportacao_R: float
    custo_desvio_R: float


@dataclass(frozen=True)
class ContabilidadeRealizada3C3:
    indicadores: dict[str, float]
    custo: CustoRealizado
    eventos_aplicados: dict[str, dict[str, int]]
    h2: tuple
    liquidacao: tuple[LiquidacaoPasso, ...]
    desvios: tuple[DesvioIntercambio, ...]
    hash_tarifas_liquidacao: dict[str, str]


def contabilidade_realizada_3c3(e: EntradaRede3C3, plano: PlanoDespacho, pr: PlanoRede3C3, traj: TrajetoriaExecutada,
                                real, politica: PoliticaAjustePCC) -> ContabilidadeRealizada3C3:
    """Custos INCORRIDOS (intervalos efetivamente aplicados): contabilidade 3C-1 INALTERADA do núcleo (curtailment com
    o P_R EFETIVO, throughput, ENS, H₂ contínuo + eventos aplicados, eventos) + gasto de importação (``importacao_rede``,
    >= 0) + crédito de exportação (``exportacao_rede``, <= 0) + desvio (``desvio_rede``, só ``desvio_diferenciado``),
    com os perfis de LIQUIDAÇÃO da política (nunca os previstos). Valor futuro nunca entra."""
    c1 = contabilidade_realizada_3c1(e.compromisso, plano, traj, real)
    t0 = ler_instante_utc(plano.inicio_utc, "plano")[0]
    h = plano.delta_s / 3600.0
    liq, gi, gr, gd = [], [], [], []
    dif = politica.liquidacao == "desvio_diferenciado"
    rem = e.exporta and e.economia.remuneracao_exportacao == "remunerada"
    ei, ee, ed_p, ed_n, eip, eep = [], [], [], [], [], []
    for p in traj.passos:
        j = p.indice_plano
        ini = (t0 + timedelta(seconds=plano.delta_s * j)).isoformat()
        imp = p.aplicado.get(f"{pr.pcc_uid}|P_imp", 0.0)
        exp = p.aplicado.get(f"{pr.pcc_uid}|P_exp", 0.0)
        ip, xp = pr.importacao_programada_kW[j], pr.exportacao_programada_kW[j]
        ei.append(h * imp)
        ee.append(h * exp)
        eip.append(h * ip)
        eep.append(h * xp)
        dv = (imp - exp) - (ip - xp)
        ed_p.append(h * max(0.0, dv))
        ed_n.append(h * max(0.0, -dv))
        if not e.conectado:
            continue

        def preco(pf, nome):
            if pf is None:
                return None
            v = preco_no_intervalo(pf, ini, plano.delta_s)
            if v is None:
                raise ContratoInvalido([erro("preco_liquidacao_indisponivel", f"politica_ajuste.{nome}",
                                             f"Sem preço de liquidação para o intervalo {ini} (nada é presumido).")])
            return v
        ci = preco(politica.tarifa_liquidacao_importacao, "tarifa_liquidacao_importacao")
        ce = preco(politica.tarifa_liquidacao_exportacao, "tarifa_liquidacao_exportacao") if rem else None
        cdp = preco(politica.tarifa_desvio_positivo, "tarifa_desvio_positivo") if dif else None
        cdn = preco(politica.tarifa_desvio_negativo, "tarifa_desvio_negativo") if dif else None
        bi, bx = (ip, xp) if dif else (imp, exp)
        g_ = h * (ci or 0.0) * bi
        r_ = h * (ce or 0.0) * bx
        d_ = h * ((cdp or 0.0) * max(0.0, dv) - (cdn or 0.0) * max(0.0, -dv)) if dif else 0.0
        gi.append(g_)
        gr.append(r_)
        gd.append(d_)
        liq.append(LiquidacaoPasso(pr.indice_fronteira_inicial + j, ci, ce, cdp, cdn, g_, r_, d_))
    comps = list(c1.custo.componentes)
    n = len(traj.passos)
    if e.importa:
        comps.append(ComponenteCusto("importacao_rede", math.fsum(gi), "realizado",
                                     f"gasto de importação liquidado ({politica.liquidacao}); {n} intervalo(s)"))
    if rem:
        comps.append(ComponenteCusto("exportacao_rede", -math.fsum(gr), "realizado",
                                     f"crédito de exportação liquidado ({politica.liquidacao}); {n} intervalo(s)"))
    if dif and e.conectado:
        comps.append(ComponenteCusto("desvio_rede", math.fsum(gd), "realizado",
                                     "desvio líquido aos preços de desvio declarados"))
    ind = dict(c1.indicadores)
    ind.update({"E_importada_kWh": math.fsum(ei), "E_exportada_kWh": math.fsum(ee),
                "E_importada_programada_kWh": math.fsum(eip), "E_exportada_programada_kWh": math.fsum(eep),
                "E_desvio_positivo_kWh": math.fsum(ed_p), "E_desvio_negativo_kWh": math.fsum(ed_n),
                "gasto_importacao_R": math.fsum(gi), "receita_exportacao_R": math.fsum(gr),
                "custo_desvio_rede_R": math.fsum(gd)})
    ht = {k: hash_perfil(v) for k, v in (("liquidacao_importacao", politica.tarifa_liquidacao_importacao),
                                         ("liquidacao_exportacao", politica.tarifa_liquidacao_exportacao),
                                         ("desvio_positivo", politica.tarifa_desvio_positivo),
                                         ("desvio_negativo", politica.tarifa_desvio_negativo)) if v is not None}
    custo = CustoRealizado(tuple(comps), math.fsum(x.valor_R for x in comps), n)
    return ContabilidadeRealizada3C3(ind, custo, c1.eventos_aplicados, c1.h2, tuple(liq), desvios_intercambio(pr, traj),
                                     ht)


__all__ = ["ContabilidadeRealizada3C3", "DesvioIntercambio", "ExecutorAlgebricoConectado3C3", "INJECOES_RENOVAVEL",
           "LIQUIDACOES", "LiquidacaoPasso", "NATUREZAS_LIQUIDACAO", "PlanoRede3C3", "PoliticaAjustePCC",
           "RegistroPassoPCC", "TIPOS_AJUSTE", "contabilidade_realizada_3c3", "desvios_intercambio",
           "hash_plano_rede", "hash_politica_ajuste", "plano_de_resultado_3c3", "programa_de_plano",
           "validar_politica_ajuste"]
