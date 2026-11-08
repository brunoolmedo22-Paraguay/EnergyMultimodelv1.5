"""Preflight científico da ponte (3C-0 §3.5) — verificação ANTES de qualquer futura execução do EMS V2.

Agrega, sem relaxar nenhuma regra, as verificações dos contratos (inventário, cenário, coerência cenário ×
microrrede, definição temporal, previsões, realização, separação previsão × realização, matriz de parâmetros,
projeção para a entrada canônica 3A com ``validar_entrada``) e acrescenta:

* referências UID inexistentes (séries, compromisso) e recursos indisponíveis comandados;
* restrições/termos incompatíveis com os equipamentos disponíveis;
* dados SINTÉTICOS fora de contexto de ensaio (erro em ``operacional``; advertência rotulada em ``ensaio``).

Resultado ``RelatorioPreflightEMS``: itens estruturados com área, código, caminho, mensagem e severidade
``bloqueante`` (erro/pendente), ``advertencia`` (aviso) ou ``aceitavel`` (verificação realizada sem constatação).
Determinístico e com SHA-256. Nenhum valor de respaldo é usado para "passar".
"""
from __future__ import annotations

from dataclasses import dataclass

from ..diagnostics import Constatacao, aviso, erro
from ..provenance import Procedencia
from .canonico import sha256
from .cenario import (CenarioEMS, ConjuntoPrevisao, DefinicaoTemporal, Realizacao, coerencia_cenario_inventario,
                      validar_cenario, validar_definicao_temporal, validar_previsao, validar_realizacao,
                      validar_separacao)
from .inventario import InventarioMicrorrede, recursos_ems, validar_inventario
from .projecao import PoliticasDeclaradas, ResultadoProjecao, montar_entrada
from .requisitos import CONTEXTOS, constatacoes as constatacoes_matriz, matriz_parametros

SEVERIDADES = {"bloqueante": "Impede a execução", "advertencia": "Registrada; não impede",
               "aceitavel": "Verificação realizada sem constatação"}
AREAS = {"inventario": "Inventário da microrrede", "parametros": "Parâmetros obrigatórios",
         "cenario": "Cenário e coerência com a microrrede", "tempo": "Malha temporal N/N+1 e horizontes",
         "previsoes": "Previsões disponíveis ao controlador", "realizacao": "Realização do entorno",
         "separacao": "Separação previsão × realização", "referencias": "Referências UID",
         "restricoes": "Restrições × equipamentos disponíveis", "sinteticos": "Dados sintéticos × contexto",
         "contrato": "Entrada canônica 3A/3B-P (validar_entrada)"}
_NIVEL = {"erro": "bloqueante", "pendente": "bloqueante", "aviso": "advertencia"}
TERMO_RECURSO = {"throughput_bess": "armazenamento", "combustivel_h2": "pemfc", "curtailment_operacional": "renovavel",
                 "geracao_termica": "termica"}


@dataclass(frozen=True)
class ItemPreflight:
    area: str
    codigo: str
    caminho: str
    mensagem: str
    severidade: str
    nivel_origem: str               # erro | pendente | aviso | ok


@dataclass(frozen=True)
class RelatorioPreflightEMS:
    microrrede_uid: str
    cenario_uid: str
    contexto: str
    itens: tuple[ItemPreflight, ...]

    @property
    def aceito(self) -> bool:
        return not any(i.severidade == "bloqueante" for i in self.itens)

    def codigos(self, severidade: str | None = None) -> set[str]:
        return {i.codigo for i in self.itens if severidade is None or i.severidade == severidade}

    def por_area(self, area: str) -> tuple[ItemPreflight, ...]:
        return tuple(i for i in self.itens if i.area == area)

    def texto(self) -> str:
        linhas = [f"Preflight EMS V2 (3C-0) — microrrede {self.microrrede_uid} · cenário {self.cenario_uid} · "
                  f"contexto {self.contexto}: {'ACEITO' if self.aceito else 'BLOQUEADO'}"]
        for sev in ("bloqueante", "advertencia", "aceitavel"):
            itens = [i for i in self.itens if i.severidade == sev]
            if itens:
                linhas.append(f"[{sev.upper()}] {len(itens)}")
                linhas += [f"  - {AREAS[i.area]} · {i.codigo} · {i.caminho}: {i.mensagem}" for i in itens]
        return "\n".join(linhas)


def hash_preflight(r: RelatorioPreflightEMS) -> str:
    return sha256(r)


def _procs_sinteticas(inv, cen, prev, real, pol) -> list[str]:
    achados: list[str] = []

    def ver(p: Procedencia | None, onde: str) -> None:
        if p is not None and p.tipo == "sintetico":
            achados.append(onde)
    ver(inv.procedencia, "inventario.procedencia")
    ver(cen.procedencia, "cenario.procedencia")
    for ci in cen.condicoes_iniciais:
        for nome in ("soc", "potencia_kW"):
            par = getattr(ci, nome)
            ver(par.procedencia if par is not None else None, f"cenario.condicoes_iniciais[{ci.uid}].{nome}")
    if prev is not None:
        ver(prev.procedencia, "previsao.procedencia")
        for s in prev.series:
            ver(s.serie.procedencia, f"previsao[{s.uid}:{s.grandeza}]")
    if real is not None:
        if real.natureza == "sintetica":
            achados.append("realizacao.natureza")
        ver(real.procedencia, "realizacao.procedencia")
        for s in real.series:
            ver(s.serie.procedencia, f"realizacao[{s.uid}:{s.grandeza}]")
    if pol is not None:
        ver(pol.procedencia, "politicas.procedencia")
    return achados


def preflight_ems_v2(inv: InventarioMicrorrede, cen: CenarioEMS, dt: DefinicaoTemporal,
                     prev: ConjuntoPrevisao | None = None, real: Realizacao | None = None,
                     pol: PoliticasDeclaradas | None = None, *, contexto: str = "operacional",
                     compromisso: dict | None = None) -> tuple[RelatorioPreflightEMS, ResultadoProjecao | None]:
    if contexto not in CONTEXTOS:
        raise ValueError(f"Contexto desconhecido: {contexto!r}")
    itens: list[ItemPreflight] = []
    vistos: set[tuple[str, str, str]] = set()

    def add(area: str, cs: list[Constatacao] | tuple[Constatacao, ...], ok: str | None = None) -> None:
        novos = 0
        for c in cs:
            chave = (c.codigo, c.caminho, c.severidade)
            if chave in vistos:
                continue
            vistos.add(chave)
            novos += 1
            itens.append(ItemPreflight(area, c.codigo, c.caminho, c.mensagem, _NIVEL[c.severidade], c.severidade))
        if not cs and ok:
            itens.append(ItemPreflight(area, "verificado", area, ok, "aceitavel", "ok"))

    add("inventario", validar_inventario(inv).constatacoes,
        f"{len(inv.dispositivos)} dispositivo(s) da microrrede {inv.identidade.uid} (revisão "
        f"{inv.identidade.revisao_config}), UIDs únicos e procedência por valor.")
    add("cenario", list(validar_cenario(cen).constatacoes) + coerencia_cenario_inventario(cen, inv),
        "Cenário referencia a mesma microrrede, incarnação e inventário físico; condições para todos os habilitados.")
    add("tempo", validar_definicao_temporal(dt),
        f"N = {dt.malha.N} intervalos e N+1 = {dt.malha.N + 1} fronteiras; Δ = {dt.malha.delta_s} s.")
    termos = frozenset(pol.objetivo.termos) if pol is not None else frozenset()
    mat = matriz_parametros(inv, termos=termos, contexto=contexto)
    cm = constatacoes_matriz(mat)
    add("parametros", cm, f"{len(mat.entradas)} requisito(s) classificados sem bloqueio.")
    if prev is None:
        add("previsoes", [erro("previsao_ausente", "previsao", "Nenhum conjunto de previsões para o controlador.")])
    else:
        add("previsoes", validar_previsao(prev, dt), f"{len(prev.series)} série(s) causais cobrindo a janela de controle.")
    if real is None:
        add("realizacao", [aviso("realizacao_nao_fornecida", "realizacao",
                                 "Sem realização: a execução (plano → estado) não pode ser avaliada.")])
    else:
        add("realizacao", validar_realizacao(real, dt), f"{len(real.series)} série(s) cobrindo a missão.")
        if prev is not None:
            add("separacao", validar_separacao(prev, real, dt), "Previsão e realização distintas (ou oráculo declarado).")
    # referências UID
    refs: list[Constatacao] = []
    recursos = {str(r): d for d in inv.dispositivos if d.habilitado for r in recursos_ems(d)}
    uids_dem = {cd.uid for cd in pol.demandas} if pol is not None else set()
    for nome, conj in (("previsao", prev), ("realizacao", real)):
        if conj is None:
            continue
        for s in conj.series:
            alvo = s.uid
            if alvo not in recursos and alvo not in uids_dem and alvo not in inv.uids():
                refs.append(erro("referencia_uid_inexistente", f"{nome}[{s.uid}:{s.grandeza}]",
                                 f"UID {s.uid} não é recurso habilitado desta microrrede nem classe de demanda declarada."))
    if prev is not None and real is not None:
        for s in prev.series:
            if s.grandeza in ("potencia", "disponibilidade") and real.serie(s.uid, s.grandeza) is None:
                refs.append(erro("realizacao_ausente_para_recurso", f"realizacao[{s.uid}:{s.grandeza}]",
                                 "Recurso previsto sem série realizada correspondente."))
    if compromisso is not None:
        gers = {k for k, d in recursos.items() if d.modelo.papel_ems == "gerador"}
        for k, prog in compromisso.items():
            if k not in gers:
                refs.append(erro("compromisso_uid_inexistente", f"compromisso[{k!r}]",
                                 "Programa para UID que não é gerador habilitado desta microrrede."))
                continue
            ci = cen.condicao(recursos[k].uid)
            if ci is not None and ci.disponibilidade == "indisponivel" and any(x == 1 for x in prog):
                refs.append(erro("compromisso_com_indisponibilidade", f"compromisso[{k}]",
                                 "u = 1 para recurso indisponível no cenário."))
    add("referencias", refs, "Todas as referências UID resolvem para recursos desta microrrede.")
    # restrições × equipamentos
    rest: list[Constatacao] = []
    if pol is not None:
        papeis = {d.modelo.papel_ems for d in recursos.values()} | {d.modelo.tecnologia_ems for d in recursos.values()}
        for t in pol.objetivo.termos:
            if t in TERMO_RECURSO and TERMO_RECURSO[t] not in papeis:
                rest.append(erro("termo_sem_recurso", f"politicas.objetivo.termos[{t}]",
                                 f"Termo {t!r} sem nenhum recurso habilitado do tipo {TERMO_RECURSO[t]!r}."))
        if pol.servico.descarte is not None and str(pol.servico.descarte.uid) not in inv.uids():
            # o inventário do Piso 1 não tem tipo "descarte": fora de ensaio, um sumidouro declarado é inexistente
            rest.append((erro if contexto == "operacional" else aviso)(
                "descarte_sem_dispositivo", "politicas.servico.descarte",
                "Descarte declarado sem dispositivo físico no inventário (D03: sem dispositivo, D̄ = 0)."))
    add("restricoes", rest, "Termos e políticas compatíveis com os equipamentos habilitados.")
    sint = _procs_sinteticas(inv, cen, prev, real, pol)
    if contexto == "operacional":
        add("sinteticos", [erro("dado_sintetico_fora_de_ensaio", o, "Dado sintético em contexto operacional.")
                           for o in sint], "Nenhum dado sintético em contexto operacional.")
    else:
        add("sinteticos", [aviso("dado_sintetico_em_ensaio", o, "Dado sintético (ensaio rotulado).") for o in sint],
            "Nenhum dado sintético.")
    proj = None
    if prev is not None and pol is not None:
        proj = montar_entrada(inv, cen, prev, dt, pol, contexto=contexto)
        add("contrato", [c for c in proj.constatacoes if c.codigo != "entrada_de_ensaio"],
            "Entrada canônica montada e aceita por validar_entrada (3A/3B-P).")
    rel = RelatorioPreflightEMS(inv.identidade.uid, cen.cenario_uid, contexto, tuple(itens))
    return rel, proj


__all__ = ["AREAS", "ItemPreflight", "RelatorioPreflightEMS", "SEVERIDADES", "hash_preflight", "preflight_ems_v2"]
