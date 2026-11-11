"""Modelo DINÂMICO da PEMFC aplicado às decisões do EMS V2 — Piso 3D-A2-H (sem reescrever equações).

Separação explícita:

* modelo ESTACIONÁRIO (``curva_h2``): potência, corrente, eficiência e H₂ suprido → curva PWL do MILP;
* modelo DINÂMICO (``h2_pemfc.Equivalent65kWHorizonDynamicModel``): estados OFF/STARTUP/IDLE/RUN/SHUTDOWN/FAULT_LIMITED,
  partida/parada temporizadas, rampas do manual, IDLE mínimo e potência efetivamente entregue.

O modelo dinâmico avalia sempre a resposta estática nas condições PADRÃO do modelo (``solve_requested_power`` sem
argumentos). ``_PotenciaNasCondicoes`` é só um ADAPTADOR: a mesma classe do modelo, com as condições físicas DECLARADAS
fixadas em toda chamada — nenhuma equação é duplicada.

Usos: (1) massas de H₂ por partida/parada (B05, variante instantânea) DERIVADAS do modelo dinâmico; (2) verificação A
POSTERIORI das consignas aplicadas pelo EMS (potência solicitada × entregue, déficit/excesso, H₂ do modelo × H₂ da PWL,
estados e limitações) com tolerâncias EXPLÍCITAS. A verificação não altera o despacho nem a planta algébrica.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pandas as pd

from .curva_h2 import CondicoesPEMFC

# Tolerâncias DECLARADAS da coerência despacho (MILP, abstração instantânea) × resposta dinâmica, por intervalo:
TOLERANCIAS = {
    "energia_rel": 0.02,          # |E_entregue − E_solicitada| <= 2 % de E_solicitada …
    "energia_abs_kWh": 0.5,       # … ou <= 0,5 kWh (intervalos de baixa energia)
    "h2_rel": 0.02,               # |m_H₂ dinâmico − m_H₂ do EMS| <= 2 % de m_H₂ do EMS …
    "h2_abs_kg": 0.02,            # … ou <= 0,02 kg
    "justificativa": "Partida quente de 30 s até IDLE e rampas de 2/3,5 kW/s diferem da abstração instantânea do MILP em "
                     "poucos segundos por evento; num intervalo de Δ = 60 min isso é < 1 % da energia. Acima destas "
                     "tolerâncias a consigna é declarada NÃO coerente com a dinâmica (nunca \"fisicamente executável\").",
}
PRE_CONDICIONAMENTO_S = 900       # unidade inicialmente ON: 15 min a P_0 antes de τ₀ (estado RUN estabelecido)


def _modelos():
    from h2_pemfc import Equivalent65kWHorizonDynamicModel, Equivalent65kWHorizonPowerRequestModel
    return Equivalent65kWHorizonDynamicModel, Equivalent65kWHorizonPowerRequestModel


@lru_cache(maxsize=16)
def modelo_dinamico(cond: CondicoesPEMFC):
    Din, PR = _modelos()

    class _PotenciaNasCondicoes(PR):
        """Mesma classe do modelo; só fixa as condições DECLARADAS quando o chamador não as informa."""
        def analyze_operational_branch(self, *a, **k):
            return super().analyze_operational_branch(**{**cond.kwargs(), **k})

        def solve_requested_power(self, requested_power_kW, *a, **k):
            return super().solve_requested_power(requested_power_kW, **{**cond.kwargs(), **k})
    return Din(static_model=_PotenciaNasCondicoes())


def _simular(cond: CondicoesPEMFC, tempos_s, potencias, habilitado, t_amb_C: float, inicio=None):
    t0 = pd.Timestamp(inicio or "2000-01-01T00:00:00")
    prof = pd.DataFrame({"timestamp": [t0 + pd.Timedelta(seconds=float(x)) for x in tempos_s],
                         "P_FC_requested_kW": [float(x) for x in potencias], "FC_enable": [bool(x) for x in habilitado],
                         "T_ambient_C": float(t_amb_C)})
    res = modelo_dinamico(cond).simulate_profile(prof)
    return res, t0


def _integral(res: pd.DataFrame, col: str, t_ini: pd.Timestamp, t_fim: pd.Timestamp) -> float:
    """∫ col dt [unidade·h] por retenção de ordem zero entre os instantes da malha interna."""
    ts = pd.to_datetime(res["timestamp"]).to_numpy()
    v = res[col].to_numpy(dtype=float)
    a, b = np.datetime64(t_ini), np.datetime64(t_fim)
    tot = 0.0
    for i in range(len(ts) - 1):
        lo, hi = max(ts[i], a), min(ts[i + 1], b)
        if hi > lo:
            tot += v[i] * float((hi - lo) / np.timedelta64(1, "s")) / 3600.0
    return tot


def massas_eventos(cond: CondicoesPEMFC, p_ref_kW: float, t_amb_C: float) -> dict:
    """m_SU / m_SD [kg/evento] DERIVADAS do modelo dinâmico: H₂ suprido durante a sequência STARTUP (até IDLE) e durante
    a sequência SHUTDOWN, a partir/até RUN em ``p_ref_kW``."""
    tempos = [0.0, 60.0, 1800.0, 3600.0, 4200.0]          # desligamento em 3600 s; 10 min para a sequência SHUTDOWN
    res, t0 = _simular(cond, tempos, [0.0, p_ref_kW, p_ref_kW, 0.0, 0.0], [False, True, True, False, False], t_amb_C)
    st = res["state"].astype(str).to_numpy()
    ts = pd.to_datetime(res["timestamp"]).to_numpy()
    q = res["hydrogen_supplied_kg_h"].to_numpy(dtype=float)

    def massa(estado):
        tot = 0.0
        for i in range(len(ts) - 1):
            if st[i] == estado:
                tot += q[i] * float((ts[i + 1] - ts[i]) / np.timedelta64(1, "s")) / 3600.0
        return tot
    dur = lambda e: float(sum((ts[i + 1] - ts[i]) / np.timedelta64(1, "s") for i in range(len(ts) - 1) if st[i] == e))  # noqa: E731
    return {"m_partida_kg": massa("STARTUP"), "m_parada_kg": massa("SHUTDOWN"), "duracao_partida_s": dur("STARTUP"),
            "duracao_parada_s": dur("SHUTDOWN"), "p_referencia_kW": float(p_ref_kW), "temperatura_ambiente_C": float(t_amb_C),
            "metodo": "∫ hydrogen_supplied_kg_h dt nos estados STARTUP/SHUTDOWN do Equivalent65kWHorizonDynamicModel "
                      "(condições declaradas; passo interno 1 s)",
            "nota": "Na abstração instantânea o MILP conta q(p)·Δt no intervalo inteiro E m_SU: os poucos segundos de "
                    "partida são contados duas vezes (conservador)."}


def verificar_despacho(cond: CondicoesPEMFC, curva, t_amb_C: float, delta_s: int, u, p, ligado0: bool, p0_kW: float,
                       ) -> dict:
    """Avalia as consignas APLICADAS de UMA unidade (u_g ∈ {0,1}, p_g [kW] por intervalo) com o modelo dinâmico."""
    K = len(u)
    pre = PRE_CONDICIONAMENTO_S if ligado0 else 0
    tempos = ([0.0] if ligado0 else []) + [pre + delta_s * g for g in range(K)] + [pre + delta_s * K]
    pot = ([p0_kW] if ligado0 else []) + [float(p[g]) if u[g] > 0.5 else 0.0 for g in range(K)] + [0.0]
    hab = ([True] if ligado0 else []) + [bool(u[g] > 0.5) for g in range(K)] + [False]
    res, t0 = _simular(cond, tempos, pot, hab, t_amb_C)
    linhas, coerente = [], True
    for g in range(K):
        a = t0 + pd.Timedelta(seconds=pre + delta_s * g)
        b = a + pd.Timedelta(seconds=delta_s)
        h = delta_s / 3600.0
        e_req = (float(p[g]) if u[g] > 0.5 else 0.0) * h
        e_del = _integral(res, "P_FC_delivered_kW", a, b)
        m_dyn = _integral(res, "hydrogen_supplied_kg_h", a, b)
        m_ems = float(curva.q_pwl([p[g]])[0]) * h if u[g] > 0.5 else 0.0
        seg = res[(pd.to_datetime(res["timestamp"]) >= a) & (pd.to_datetime(res["timestamp"]) < b)]
        estados = sorted(set(seg["state"].astype(str)))
        lim = sorted({r for x in seg["limitation_reason"].astype(str) for r in x.split("|") if r and r != "NONE"})
        ok_e = abs(e_del - e_req) <= max(TOLERANCIAS["energia_rel"] * e_req, TOLERANCIAS["energia_abs_kWh"])
        ok_m = abs(m_dyn - m_ems) <= max(TOLERANCIAS["h2_rel"] * m_ems, TOLERANCIAS["h2_abs_kg"])
        coerente &= ok_e and ok_m
        linhas.append({"intervalo": g, "u": int(u[g] > 0.5), "p_solicitada_kW": float(p[g]) if u[g] > 0.5 else 0.0,
                       "p_entregue_media_kW": e_del / h, "energia_solicitada_kWh": e_req, "energia_entregue_kWh": e_del,
                       "deficit_kWh": max(0.0, e_req - e_del), "excesso_kWh": max(0.0, e_del - e_req),
                       "h2_modelo_dinamico_kg": m_dyn, "h2_ems_pwl_kg": m_ems, "estados": estados, "limitacoes": lim,
                       "coerente_energia": bool(ok_e), "coerente_h2": bool(ok_m)})
    return {"intervalos": linhas, "coerente": bool(coerente),
            "energia_solicitada_kWh": math.fsum(x["energia_solicitada_kWh"] for x in linhas),
            "energia_entregue_kWh": math.fsum(x["energia_entregue_kWh"] for x in linhas),
            "h2_modelo_dinamico_kg": math.fsum(x["h2_modelo_dinamico_kg"] for x in linhas),
            "h2_ems_pwl_kg": math.fsum(x["h2_ems_pwl_kg"] for x in linhas),
            "pre_condicionamento_s": pre, "temperatura_ambiente_C": float(t_amb_C)}


__all__ = ["PRE_CONDICIONAMENTO_S", "TOLERANCIAS", "massas_eventos", "modelo_dinamico", "verificar_despacho"]
