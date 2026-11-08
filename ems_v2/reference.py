"""Cálculo algébrico de REFERÊNCIA (aritmética racional exata, ``fractions.Fraction``).

Implementa somente o que a ordem executiva 3A autoriza: energia por intervalos (M01), recorrência de energia BESS
(M07, sem recorte), renovável v1.1 (M03-v1.1 + KPIs de indisponibilidade/curtailment e custo ``c^curt E^curt,oper``,
adenda B01), avaliação da PWL sintética (M15/M16 num ponto dado) e massas de H2 por intervalo. NÃO é solver:
recebe valores já escolhidos e devolve a consequência matemática. NÃO escreve objetivo Pyomo.

Independência (condição A da fiscalização): este módulo usa racionais exatos e laços explícitos; o auditor
(``ems_v2.audit``) usa ponto flutuante, segundos e busca binária, e NÃO importa este módulo. Os testes comparam
ambos com resultados ANALÍTICOS literais dos documentos (nunca um com o outro como oráculo).
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

from .units import exato

Numero = float | int | Fraction | str


class ForaDoDominio(ValueError):
    """Ponto fora do domínio declarado (p. ex. ON abaixo de P_min, ou OFF com potência)."""


def _vec(xs: Sequence[Numero], nome: str) -> list[Fraction]:
    v = [exato(x) for x in xs]
    if any(x < 0 for x in v):
        raise ValueError(f"{nome}: valores negativos não são admitidos.")
    return v


def horas(delta_min: Numero) -> Fraction:
    d = exato(delta_min)
    if d <= 0:
        raise ValueError("Δ deve ser > 0.")
    return d / 60


def energia_kWh(potencias_kW: Sequence[Numero], delta_min: Numero) -> Fraction:
    """Σ_t P_t · Δ/60 sobre os N intervalos recebidos (o instante terminal não é integrado)."""
    return sum((exato(p) for p in potencias_kW), Fraction(0)) * horas(delta_min)


def trajetoria_energia_bess(e0_kWh: Numero, p_carga_kW: Sequence[Numero], p_descarga_kW: Sequence[Numero],
                            eta_c: Numero, eta_d: Numero, delta_min: Numero, alpha: Numero = 1) -> tuple[Fraction, ...]:
    """M07: e_{t+1} = α e_t + h (η^c P^c_t − P^d_t / η^d). Devolve os N+1 estados. Sem recorte; sem julgamento de
    factibilidade (limites são verificados pelo auditor/contrato)."""
    pc, pd = _vec(p_carga_kW, "P_carga"), _vec(p_descarga_kW, "P_descarga")
    if len(pc) != len(pd):
        raise ValueError("P_carga e P_descarga com comprimentos distintos.")
    ec, ed, a, h = exato(eta_c), exato(eta_d), exato(alpha), horas(delta_min)
    if not (0 < ec <= 1 and 0 < ed <= 1):
        raise ValueError("Eficiências exigem (0, 1].")
    if not (0 < a <= 1):
        raise ValueError("α exige (0, 1].")
    e = [exato(e0_kWh)]
    for c, d in zip(pc, pd):
        e.append(a * e[-1] + h * (ec * c - d / ed))
    return tuple(e)


@dataclass(frozen=True)
class ResultadoRenovavel:
    A_utilizavel_kW: tuple[Fraction, ...]
    C_oper_kW: tuple[Fraction, ...]
    E_indisp_kWh: Fraction
    E_curt_oper_kWh: Fraction
    custo_curt_oper_R: Fraction


def renovavel_v11(A_pot_kW: Sequence[Numero], a: Sequence[int], P_usada_kW: Sequence[Numero], delta_min: Numero,
                  c_curt_R_kWh: Numero) -> ResultadoRenovavel:
    """M03-v1.1 e KPIs B01: A_util = a·A_pot; C_oper = A_util − P_usada; E_indisp = h Σ(1−a)A_pot;
    E_curt,oper = h Σ C_oper; custo = c^curt · E_curt,oper. Indisponibilidade NUNCA entra no custo."""
    A, P = _vec(A_pot_kW, "A_pot"), _vec(P_usada_kW, "P_usada")
    if not (len(A) == len(P) == len(a)):
        raise ValueError("Comprimentos distintos.")
    if any(x not in (0, 1) or isinstance(x, bool) for x in a):
        raise ValueError("Disponibilidade binária exigida (a ∈ {0, 1}).")
    h, c = horas(delta_min), exato(c_curt_R_kWh)
    if c < 0:
        raise ValueError("c^curt negativo.")
    Au = tuple(Fraction(ai) * Ai for ai, Ai in zip(a, A))
    C = []
    for t, (au, p) in enumerate(zip(Au, P)):
        if p > au:
            raise ForaDoDominio(f"t={t}: P_usada {p} > A_utilizável {au} (energia inexistente).")
        C.append(au - p)
    E_ind = h * sum(((1 - Fraction(ai)) * Ai for ai, Ai in zip(a, A)), Fraction(0))
    E_cur = h * sum(C, Fraction(0))
    return ResultadoRenovavel(Au, tuple(C), E_ind, E_cur, c * E_cur)


def vazao_pwl(vertices: Sequence[tuple[Numero, Numero]], p_kW: Numero, ligado: bool) -> Fraction:
    """Avalia a interpolante PWL (M15/M16) num ponto. OFF ⇒ exige p = 0 e devolve q = 0. ON ⇒ exige p no domínio
    [P_0, P_último] (sem segmento entre (0, 0) e P_min)."""
    p = exato(p_kW)
    if not ligado:
        if p != 0:
            raise ForaDoDominio(f"OFF exige p = 0; recebido {p}.")
        return Fraction(0)
    V = [(exato(P), exato(Q)) for P, Q in vertices]
    if p < V[0][0] or p > V[-1][0]:
        raise ForaDoDominio(f"ON em p = {p} kW fora do domínio [{V[0][0]}, {V[-1][0]}] kW.")
    for (P0, Q0), (P1, Q1) in zip(V, V[1:]):
        if P0 <= p <= P1:
            return Q0 + (Q1 - Q0) * (p - P0) / (P1 - P0)
    raise ForaDoDominio("Vértices não crescentes.")  # inalcançável com curva validada


def massa_h2_kg(q_kg_h: Numero, delta_min: Numero) -> Fraction:
    """Parte operacional de M17/B05-instantânea: h · q [kg/intervalo] (eventos NÃO incluídos)."""
    return exato(q_kg_h) * horas(delta_min)


def massa_modo_kg(q_modo_kg_h: Numero, duracao_min: Numero) -> Fraction:
    """B05 (multimodo, referência B05A): massa = q^mode × duração; sem somar m^SU do mesmo arranque."""
    return exato(q_modo_kg_h) * horas(duracao_min)


__all__ = ["ForaDoDominio", "ResultadoRenovavel", "energia_kWh", "horas", "massa_h2_kg", "massa_modo_kg",
           "renovavel_v11", "trajetoria_energia_bess", "vazao_pwl"]
