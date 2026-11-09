"""Memória operativa do commitment entre janelas (3C-1 §5) — só biblioteca padrão.

A memória de cada unidade numa fronteira k é: estado ON/OFF anterior (``u``), potência anterior (``p``), tempo
transcorrido no estado vigente e obrigação residual de permanência. Nada é reconstruído a partir da potência:

* o tempo no estado na fronteira N de um programa ``u_0..u_{N−1}`` é ``(N − j)·Δ`` se a última transição ocorreu
  no intervalo j, ou ``tempo_inicial + N·Δ`` se não houve transição (``None`` se o tempo inicial não é conhecido);
* a obrigação residual é ``⌈max(0, T_estado − tempo)⌉`` [s] — idêntica, por construção, ao que a restrição M12 de
  uma janela CONTÍNUA imporia (prova em ``docs/ems_v2/FORMULACAO_3C1.md`` §5);
* a garantia de permanência é ``completa_na_janela`` só quando NENHUMA obrigação excede a janela; caso contrário é
  ``residual_vinculante`` (intenção de continuidade registrada — nunca apresentada como garantia cumprida).

``transportar`` produz a memória da janela seguinte a partir da memória inicial e do programa EFETIVAMENTE aplicado
(ou planejado), sem perder obrigações herdadas.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..contracts import UIDRecurso
from ..provenance import Procedencia
from .contrato import EntradaCommitment3C1, MemoriaCommitmentUnidade, obrigacao_derivada_s, tempo_s_exato

GARANTIAS = {"completa_na_janela": "Nenhuma obrigação de permanência excede a janela",
             "residual_vinculante": "Há obrigações que excedem a janela: VINCULANTES para a continuação (não cumpridas "
                                    "na janela)"}


@dataclass(frozen=True)
class MemoriaFronteira:
    """Memória de uma unidade na fronteira global ``indice_fronteira`` (saída do plano ou da execução)."""
    uid: str
    indice_fronteira: int
    ligado: bool
    potencia_kW: float
    tempo_no_estado_s: int | None
    obrigacao_residual_s: int | None
    origem: str                         # "plano" | "execucao" | "declarada"


def _T(e: EntradaCommitment3C1, uid: str, ligado: bool):
    sp = e.unidade(uid)
    return tempo_s_exato(sp.tempo_min_ligado_min if ligado else sp.tempo_min_desligado_min)


def memoria_apos(e: EntradaCommitment3C1, uid: str, u: list[int], p: list[float], *, indice_fronteira_inicial: int = 0,
                 origem: str = "plano") -> MemoriaFronteira:
    """Memória da unidade ``uid`` na fronteira ``len(u)`` (relativa à janela) após aplicar o programa ``u``/``p``."""
    m = e.base.malha
    st = next(s for s in e.base.estados_geradores if str(s.uid) == uid)
    mem = e.memoria(uid)
    u_ant = int(bool(st.ligado))
    n = len(u)
    if n == 0:
        t0 = mem.tempo_no_estado_s if mem is not None else None
        ob = mem.obrigacao_residual_s if mem is not None else None
        return MemoriaFronteira(uid, indice_fronteira_inicial, bool(u_ant), float(st.p_anterior_kW.valor), t0, ob, origem)
    seq = [u_ant] + [int(x) for x in u]
    ultima = max((j for j in range(1, n + 1) if seq[j] != seq[j - 1]), default=None)   # j ↔ intervalo j−1
    if ultima is None:
        t0 = mem.tempo_no_estado_s if mem is not None else None
        tempo = None if t0 is None else t0 + n * m.delta_s
        herdada = None if mem is None or mem.obrigacao_residual_s is None else max(0, mem.obrigacao_residual_s
                                                                                  - n * m.delta_s)
    else:
        tempo = (n - (ultima - 1)) * m.delta_s
        herdada = 0
    lig = bool(seq[-1])
    T = _T(e, uid, lig)
    der = obrigacao_derivada_s(T, tempo) if T is not None else (0 if e.unidade(uid).abstracao_transicao
                                                               == "transicoes_bloqueadas" else None)
    if der is None and herdada is not None and T is None:
        der = herdada
    ob = der if herdada is None or der is None else max(der, herdada)
    return MemoriaFronteira(uid, indice_fronteira_inicial + n, lig, float(p[-1]), tempo, ob, origem)


def memoria_terminal(e: EntradaCommitment3C1, u: dict[str, list[int]], p: dict[str, list[float]], *,
                     indice_fronteira_inicial: int = 0, origem: str = "plano") -> tuple[MemoriaFronteira, ...]:
    return tuple(memoria_apos(e, str(g.uid), u[str(g.uid)], p[str(g.uid)],
                              indice_fronteira_inicial=indice_fronteira_inicial, origem=origem)
                 for g in sorted(e.base.geradores, key=lambda x: str(x.uid)))


def garantia(memorias: tuple[MemoriaFronteira, ...]) -> tuple[str, dict[str, int]]:
    """Classifica a garantia de permanência e devolve as obrigações residuais POSITIVAS por UID (s)."""
    res = {x.uid: x.obrigacao_residual_s for x in memorias if (x.obrigacao_residual_s or 0) > 0}
    return ("residual_vinculante" if res else "completa_na_janela"), res


def para_memoria_entrada(mf: MemoriaFronteira, uid: UIDRecurso, procedencia: Procedencia) -> MemoriaCommitmentUnidade:
    """Memória de fronteira → ``MemoriaCommitmentUnidade`` da janela seguinte (transporte explícito, com procedência)."""
    return MemoriaCommitmentUnidade(uid, mf.tempo_no_estado_s, mf.obrigacao_residual_s, procedencia)


__all__ = ["GARANTIAS", "MemoriaFronteira", "garantia", "memoria_apos", "memoria_terminal", "para_memoria_entrada"]
