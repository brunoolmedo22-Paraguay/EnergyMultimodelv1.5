"""Modelo DINÂMICO da PEMFC aplicado às decisões do EMS V2 — Piso 3D-A2-H (sem reescrever equações).

Separação explícita:

* modelo ESTACIONÁRIO (``curva_h2``): potência, corrente, eficiência e H₂ suprido → curva PWL do MILP;
* modelo DINÂMICO (``h2_pemfc.Equivalent65kWHorizonDynamicModel``): estados OFF/STARTUP/IDLE/RUN/SHUTDOWN/FAULT_LIMITED,
  partida/parada temporizadas, rampas do manual, IDLE mínimo e potência efetivamente entregue.

O modelo dinâmico avalia sempre a resposta estática nas condições PADRÃO do modelo (``solve_requested_power`` sem
argumentos). ``_PotenciaNasCondicoes`` é só um ADAPTADOR: a mesma classe do modelo, com as condições físicas DECLARADAS
fixadas em toda chamada — nenhuma equação é duplicada. Todos os parâmetros dinâmicos (IDLE, rampas, durações de partida e
parada, limiar de partida fria) são LIDOS da configuração do modelo, nunca redigitados aqui.

**Semântica da massa de H₂ por evento (adenda B05, variante instantânea — auditoria do PR #23, ponto A).** O MILP
contabiliza, por unidade e intervalo k, ``M_EMS,k = q̂(p_k)·Δ·u_k + m_SU·y_k + m_SD·z_k`` (y = partida, z = parada no
início de k). A abstração instantânea JÁ conta ``q̂(p_k)·Δ`` no intervalo de partida inteiro; por isso ``m_SU``/``m_SD`` são
massas ADICIONAIS em relação a essa contabilidade, definidas pela integração TEMPORAL do modelo dinâmico:

* ``δ_SU(p) = ∫ q_din(intervalo com partida em p) dt − ∫ q_din(mesmo intervalo em regime em p) dt``;
* ``δ_SD(p) = ∫ q_din(intervalo após a parada a partir de p) dt − 0`` (em regime desligado o consumo é nulo).

Como o MILP usa UMA constante por evento, adota-se ``m = max(0, máx_p δ(p))`` sobre uma malha do domínio
[P_mín, P_máx]: a massa total nunca é SUBESTIMADA pelo termo de evento e a superestimação é limitada por
``m − mín_p δ(p)`` (registrada). Não há dupla contagem: o consumo durante STARTUP já está em ``∫ q_din`` e a contabilidade
instantânea já o cobre (δ_SU < 0 em todo o domínio do modelo nominal ⇒ m_SU = 0); a rampa de descida e a sequência de
SHUTDOWN ocorrem no intervalo DESLIGADO, onde a contabilidade instantânea é zero ⇒ m_SD > 0.

Usos: (1) massas por evento acima; (2) análise transitória A PRIORI (pior caso de partida, parada e rampas no domínio, no
Δ declarado) que o preflight usa para BLOQUEAR configurações incompatíveis; (3) verificação A POSTERIORI das consignas
aplicadas (energia solicitada × entregue, H₂ do EMS × H₂ do modelo dinâmico, estados e limitações) com tolerâncias
EXPLÍCITAS. A verificação não altera o despacho nem a planta algébrica.
"""
from __future__ import annotations

import copy
import math
from functools import lru_cache

import numpy as np
import pandas as pd

from .curva_h2 import CondicoesPEMFC

# Tolerâncias DECLARADAS da coerência despacho (MILP, abstração instantânea) × resposta dinâmica, por intervalo. As
# parcelas absolutas são POTÊNCIA/VAZÃO MÉDIAS no intervalo (escalam com Δ; em Δ = 60 min valem 0,5 kWh e 0,02 kg).
TOLERANCIAS = {
    "energia_rel": 0.02,              # |E_entregue − E_solicitada| <= 2 % de E_solicitada …
    "potencia_media_abs_kW": 0.5,     # … ou <= 0,5 kW × Δ (intervalos de baixa energia)
    "h2_rel": 0.02,                   # |m_H₂ dinâmico − m_H₂ do EMS| <= 2 % de m_H₂ do EMS …
    "vazao_media_abs_kg_h": 0.02,     # … ou <= 0,02 kg/h × Δ
    "justificativa": "Limiares de ENGENHARIA da abstração instantânea (não incerteza experimental): a partida quente e as "
                     "rampas do manual duram segundos e, em Δ = 60 min, deslocam < 1 % da energia do intervalo. As parcelas "
                     "absolutas são médias por unidade de tempo para não afrouxar a tolerância em Δ curtos. Fora delas a "
                     "consigna é declarada NÃO coerente com a dinâmica (nunca \"fisicamente executável\").",
}
PRE_CONDICIONAMENTO_S = 900       # unidade inicialmente ON: 15 min a P_0 antes de τ₀ (estado RUN estabelecido)
MARGEM_TRANSITORIO_S = 60.0       # folga após o fim teórico do transitório (regime confirmado dentro da janela)
PONTOS_MALHA = 9                  # malha de P em [P_mín, P_máx] da análise transitória


def _modelos():
    from h2_pemfc import Equivalent65kWHorizonDynamicModel, Equivalent65kWHorizonPowerRequestModel
    return Equivalent65kWHorizonDynamicModel, Equivalent65kWHorizonPowerRequestModel


@lru_cache(maxsize=16)
def modelo_dinamico(cond: CondicoesPEMFC):
    Din, PR = _modelos()

    class _PotenciaNasCondicoes(PR):
        """Mesma classe do modelo; só fixa as condições DECLARADAS quando o chamador não as informa. As respostas estáticas
        já resolvidas são REUTILIZADAS por potência solicitada (a resposta de cada potência é independente das demais e
        determinística nas condições fixadas): só evita repetir o brentq do modelo — nenhum valor é aproximado."""
        _memo = None

        def analyze_operational_branch(self, *a, **k):
            return super().analyze_operational_branch(**{**cond.kwargs(), **k})

        def solve_requested_power(self, requested_power_kW, *a, **k):
            if a or k:
                return super().solve_requested_power(requested_power_kW, *a, **{**cond.kwargs(), **k})
            x = np.atleast_1d(np.asarray(requested_power_kW, dtype=float))
            tab = self._memo
            novos = np.unique(x) if tab is None else np.setdiff1d(np.unique(x), tab.index.to_numpy())
            if novos.size:
                df = super().solve_requested_power(novos, **cond.kwargs())
                df.index = novos
                tab = df if tab is None else pd.concat([tab, df]).sort_index()
                self._memo = tab
            return tab.loc[x].reset_index(drop=True)
    return Din(static_model=_PotenciaNasCondicoes())


def parametros_dinamicos(cond: CondicoesPEMFC, t_amb_C: float) -> dict:
    """Parâmetros do modelo dinâmico efetivos na temperatura ambiente declarada (lidos do modelo)."""
    m = modelo_dinamico(cond)
    c = m.configuration
    fria = not (t_amb_C > c.cold_temperature_threshold_C)
    return {"idle_kW": float(c.idle_power_kW), "rampa_subida_kW_s": float(c.ramp_up_kW_s),
            "rampa_descida_kW_s": float(c.ramp_down_kW_s),
            "partida_s": float(m._startup_duration_s(float(t_amb_C))), "parada_s": float(m._shutdown_duration_s(float(t_amb_C))),
            "partida_fria": bool(fria), "limiar_partida_fria_C": float(c.cold_temperature_threshold_C),
            "rampa_max_kW_min": 60.0 * min(float(c.ramp_up_kW_s), float(c.ramp_down_kW_s))}


def tolerancia_energia_kWh(e_req: float, delta_s: float, tol: dict | None = None) -> float:
    t = tol or TOLERANCIAS
    return max(t["energia_rel"] * abs(e_req), t["potencia_media_abs_kW"] * delta_s / 3600.0)


def tolerancia_h2_kg(m_ems: float, delta_s: float, tol: dict | None = None) -> float:
    t = tol or TOLERANCIAS
    return max(t["h2_rel"] * abs(m_ems), t["vazao_media_abs_kg_h"] * delta_s / 3600.0)


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
    lo = np.maximum(ts[:-1], a)
    hi = np.minimum(ts[1:], b)
    dur = np.where(hi > lo, (hi - lo) / np.timedelta64(1, "s"), 0.0).astype(float)
    return float(math.fsum(v[:-1] * dur)) / 3600.0


def _q_regime(cond: CondicoesPEMFC, p_kW) -> np.ndarray:
    """Vazão de H₂ suprido em REGIME na potência p (a mesma resposta estática que o modelo dinâmico usa em RUN)."""
    df = modelo_dinamico(cond).static_model.solve_requested_power(np.asarray(p_kW, dtype=float))
    return df["hydrogen_supplied_kg_h"].to_numpy(dtype=float)


def _janela(res, t0, a_s, b_s):
    a, b = t0 + pd.Timedelta(seconds=a_s), t0 + pd.Timedelta(seconds=b_s)
    return _integral(res, "hydrogen_supplied_kg_h", a, b), _integral(res, "P_FC_delivered_kW", a, b)


@lru_cache(maxsize=32)
def _analise(cond: CondicoesPEMFC, t_amb_C: float, p_min_kW: float, p_max_kW: float) -> dict:
    par = parametros_dinamicos(cond, t_amb_C)
    sub, des, idle = par["rampa_subida_kW_s"], par["rampa_descida_kW_s"], par["idle_kW"]
    grade = [float(x) for x in np.linspace(p_min_kW, p_max_kW, PONTOS_MALHA)]
    t_su = par["partida_s"] + max(0.0, p_max_kW - idle) / sub + MARGEM_TRANSITORIO_S       # janela da partida
    t_sd = par["parada_s"] + p_max_kW / des + MARGEM_TRANSITORIO_S                        # janela da parada
    t_rp = (p_max_kW - p_min_kW) / min(sub, des) + MARGEM_TRANSITORIO_S                   # janela de uma rampa
    qss = dict(zip(grade, _q_regime(cond, grade)))
    linhas = []
    for p in grade:
        res, t0 = _simular(cond, [0.0, t_su], [p, 0.0], [True, False], t_amb_C)                       # partida em 0
        m_su, e_su = _janela(res, t0, 0.0, t_su)
        t_d = t_su                                                                                   # já em regime
        res, t0 = _simular(cond, [0.0, t_d, t_d + t_sd], [p, 0.0, 0.0], [True, False, False], t_amb_C)  # parada em t_d
        m_sd, e_sd = _janela(res, t0, t_d, t_d + t_sd)
        h = t_su / 3600.0
        linhas.append({"p_kW": p, "q_regime_kg_h": float(qss[p]),
                       "delta_m_partida_kg": m_su - float(qss[p]) * h, "delta_E_partida_kWh": e_su - p * h,
                       "m_parada_kg": m_sd, "E_parada_kWh": e_sd})
    rampas = []
    for pa, pb in ((p_min_kW, p_max_kW), (p_max_kW, p_min_kW)):
        res, t0 = _simular(cond, [0.0, t_su, t_su + t_rp], [pa, pb, 0.0], [True, True, False], t_amb_C)
        m_r, e_r = _janela(res, t0, t_su, t_su + t_rp)
        qb = float(_q_regime(cond, [pb])[0])
        h = t_rp / 3600.0
        rampas.append({"de_kW": pa, "para_kW": pb, "delta_m_kg": m_r - qb * h, "delta_E_kWh": e_r - pb * h,
                       "q_regime_destino_kg_h": qb})
    dsu = [x["delta_m_partida_kg"] for x in linhas]
    msd = [x["m_parada_kg"] for x in linhas]
    m_su, m_sd = max(0.0, max(dsu)), max(0.0, max(msd))
    return {"parametros_modelo_dinamico": par, "malha_p_kW": grade, "pontos": linhas, "rampas": rampas,
            "janelas_s": {"partida": t_su, "parada": t_sd, "rampa": t_rp},
            "m_partida_kg": m_su, "m_parada_kg": m_sd,
            "superestimacao_max_partida_kg": m_su - min(dsu), "superestimacao_max_parada_kg": m_sd - min(msd),
            "temperatura_ambiente_C": float(t_amb_C), "p_min_kW": float(p_min_kW), "p_max_kW": float(p_max_kW),
            "semantica": "m = massa ADICIONAL do evento em relação à contabilidade instantânea q̂(p)·Δ do MILP: "
                         "δ_SU(p) = ∫q_din(intervalo com partida) − ∫q_din(mesmo intervalo em regime); δ_SD(p) = "
                         "∫q_din(intervalo após a parada) − 0; constante por evento m = max(0, máx_p δ(p)) na malha de P "
                         "(nunca subestima a massa total; superestimação limitada e registrada).",
            "metodo": "∫ hydrogen_supplied_kg_h dt do Equivalent65kWHorizonDynamicModel (condições declaradas por "
                      "adaptador; passo interno 1 s), janela que contém todo o transitório + 60 s de regime"}


def analise_transitoria(cond: CondicoesPEMFC, t_amb_C: float, p_min_kW: float, p_max_kW: float) -> dict:
    """Pior caso de partida, parada e rampas no domínio [P_mín, P_máx] (cópia; o resultado em cache não é exposto)."""
    return copy.deepcopy(_analise(cond, float(t_amb_C), float(p_min_kW), float(p_max_kW)))


def massas_eventos(cond: CondicoesPEMFC, t_amb_C: float, p_min_kW: float, p_max_kW: float) -> dict:
    """m_SU / m_SD [kg/evento] ADICIONAIS (semântica no docstring do módulo) + a análise que as sustenta."""
    a = analise_transitoria(cond, t_amb_C, p_min_kW, p_max_kW)
    return {"m_partida_kg": a["m_partida_kg"], "m_parada_kg": a["m_parada_kg"],
            "superestimacao_max_partida_kg": a["superestimacao_max_partida_kg"],
            "superestimacao_max_parada_kg": a["superestimacao_max_parada_kg"],
            "duracao_partida_s": a["parametros_modelo_dinamico"]["partida_s"],
            "duracao_parada_s": a["parametros_modelo_dinamico"]["parada_s"],
            "temperatura_ambiente_C": a["temperatura_ambiente_C"], "semantica": a["semantica"], "metodo": a["metodo"],
            "analise": a}


def admissibilidade(analise: dict, curva, delta_s: float, abstracao: str) -> list[dict]:
    """Incompatibilidades A PRIORI da abstração do MILP com o modelo dinâmico, no Δ declarado (lista vazia = admissível).

    Para cada P da malha: intervalo de PARTIDA (energia entregue × p·Δ; H₂ q̂(p)·Δ + m_SU × dinâmico), intervalo após a
    PARADA (energia entregue × 0; m_SD × dinâmico) e as RAMPAS P_mín ↔ P_máx em operação contínua. Com
    ``transicoes_bloqueadas`` só as rampas se aplicam (não há partida/parada na missão)."""
    out = []
    h = delta_s / 3600.0
    jan = analise["janelas_s"]
    transita = abstracao == "instantanea_unidade_quente"
    precisa = max([jan["rampa"]] + ([jan["partida"], jan["parada"]] if transita else [])) - MARGEM_TRANSITORIO_S
    if delta_s < precisa:
        out.append({"caso": "delta_menor_que_o_transitorio", "p_kW": None, "desvio": precisa, "tolerancia": delta_s,
                    "grandeza": "s", "texto": f"Δ = {delta_s:g} s menor que o transitório do modelo dinâmico "
                                              f"({precisa:.0f} s): a abstração não cabe no intervalo."})
        return out
    m_su, m_sd = analise["m_partida_kg"], analise["m_parada_kg"]
    if transita:
        for x in analise["pontos"]:
            p, qss = x["p_kW"], x["q_regime_kg_h"]
            e_req = p * h
            dE = abs(x["delta_E_partida_kWh"])
            if dE > tolerancia_energia_kWh(e_req, delta_s):
                out.append({"caso": "partida", "p_kW": p, "grandeza": "energia_kWh", "desvio": dE,
                            "tolerancia": tolerancia_energia_kWh(e_req, delta_s)})
            m_ems = float(curva.q_pwl([p])[0]) * h + m_su
            m_din = qss * h + x["delta_m_partida_kg"]
            if abs(m_ems - m_din) > tolerancia_h2_kg(m_ems, delta_s):
                out.append({"caso": "partida", "p_kW": p, "grandeza": "h2_kg", "desvio": abs(m_ems - m_din),
                            "tolerancia": tolerancia_h2_kg(m_ems, delta_s)})
            if x["E_parada_kWh"] > tolerancia_energia_kWh(0.0, delta_s):
                out.append({"caso": "parada", "p_kW": p, "grandeza": "energia_kWh", "desvio": x["E_parada_kWh"],
                            "tolerancia": tolerancia_energia_kWh(0.0, delta_s)})
            if abs(m_sd - x["m_parada_kg"]) > tolerancia_h2_kg(m_sd, delta_s):
                out.append({"caso": "parada", "p_kW": p, "grandeza": "h2_kg", "desvio": abs(m_sd - x["m_parada_kg"]),
                            "tolerancia": tolerancia_h2_kg(m_sd, delta_s)})
    for r in analise["rampas"]:
        e_req = r["para_kW"] * h
        if abs(r["delta_E_kWh"]) > tolerancia_energia_kWh(e_req, delta_s):
            out.append({"caso": "rampa", "p_kW": r["para_kW"], "grandeza": "energia_kWh", "desvio": abs(r["delta_E_kWh"]),
                        "tolerancia": tolerancia_energia_kWh(e_req, delta_s)})
        m_ems = float(curva.q_pwl([r["para_kW"]])[0]) * h
        m_din = r["q_regime_destino_kg_h"] * h + r["delta_m_kg"]
        if abs(m_ems - m_din) > tolerancia_h2_kg(m_ems, delta_s):
            out.append({"caso": "rampa", "p_kW": r["para_kW"], "grandeza": "h2_kg", "desvio": abs(m_ems - m_din),
                        "tolerancia": tolerancia_h2_kg(m_ems, delta_s)})
    return out


def verificar_despacho(cond: CondicoesPEMFC, curva, t_amb_C: float, delta_s: int, u, p, ligado0: bool, p0_kW: float,
                       massas: tuple[float, float] = (0.0, 0.0)) -> dict:
    """Avalia as consignas APLICADAS de UMA unidade (u_g ∈ {0,1}, p_g [kW] por intervalo) com o modelo dinâmico.

    H₂ do EMS por intervalo = exatamente a contabilidade do MILP: q̂(p)·Δ·u + m_SU·y + m_SD·z (``massas`` = (m_SU, m_SD))."""
    K = len(u)
    pre = PRE_CONDICIONAMENTO_S if ligado0 else 0
    tempos = ([0.0] if ligado0 else []) + [pre + delta_s * g for g in range(K)] + [pre + delta_s * K]
    pot = ([p0_kW] if ligado0 else []) + [float(p[g]) if u[g] > 0.5 else 0.0 for g in range(K)] + [0.0]
    hab = ([True] if ligado0 else []) + [bool(u[g] > 0.5) for g in range(K)] + [False]
    res, t0 = _simular(cond, tempos, pot, hab, t_amb_C)
    m_su, m_sd = (float(massas[0]), float(massas[1]))
    ts = pd.to_datetime(res["timestamp"])
    linhas, incoerencias = [], []
    ant = bool(ligado0)
    for g in range(K):
        a = t0 + pd.Timedelta(seconds=pre + delta_s * g)
        b = a + pd.Timedelta(seconds=delta_s)
        h = delta_s / 3600.0
        on = bool(u[g] > 0.5)
        y, z = (on and not ant), (ant and not on)
        e_req = (float(p[g]) if on else 0.0) * h
        e_del = _integral(res, "P_FC_delivered_kW", a, b)
        m_dyn = _integral(res, "hydrogen_supplied_kg_h", a, b)
        m_ems = (float(curva.q_pwl([p[g]])[0]) * h if on else 0.0) + m_su * y + m_sd * z
        seg = res[(ts >= a) & (ts < b)]
        estados = sorted(set(seg["state"].astype(str)))
        lim = sorted({r for x in seg["limitation_reason"].astype(str) for r in x.split("|") if r and r != "NONE"})
        tol_e, tol_m = tolerancia_energia_kWh(e_req, delta_s), tolerancia_h2_kg(m_ems, delta_s)
        ok_e = abs(e_del - e_req) <= tol_e
        ok_m = abs(m_dyn - m_ems) <= tol_m
        evento = "partida" if y else "parada" if z else ("ligada" if on else "desligada")
        if not ok_e:
            incoerencias.append({"intervalo": g, "evento": evento, "criterio": "energia", "desvio": e_del - e_req,
                                 "tolerancia": tol_e})
        if not ok_m:
            incoerencias.append({"intervalo": g, "evento": evento, "criterio": "h2", "desvio": m_dyn - m_ems,
                                 "tolerancia": tol_m})
        linhas.append({"intervalo": g, "u": int(on), "evento": evento, "p_solicitada_kW": float(p[g]) if on else 0.0,
                       "p_entregue_media_kW": e_del / h, "energia_solicitada_kWh": e_req, "energia_entregue_kWh": e_del,
                       "deficit_kWh": max(0.0, e_req - e_del), "excesso_kWh": max(0.0, e_del - e_req),
                       "h2_modelo_dinamico_kg": m_dyn, "h2_ems_kg": m_ems, "tolerancia_energia_kWh": tol_e,
                       "tolerancia_h2_kg": tol_m, "estados": estados, "limitacoes": lim,
                       "coerente_energia": bool(ok_e), "coerente_h2": bool(ok_m)})
        ant = on
    return {"intervalos": linhas, "coerente": not incoerencias, "incoerencias": incoerencias,
            "energia_solicitada_kWh": math.fsum(x["energia_solicitada_kWh"] for x in linhas),
            "energia_entregue_kWh": math.fsum(x["energia_entregue_kWh"] for x in linhas),
            "h2_modelo_dinamico_kg": math.fsum(x["h2_modelo_dinamico_kg"] for x in linhas),
            "h2_ems_kg": math.fsum(x["h2_ems_kg"] for x in linhas),
            # o H₂ do EMS NÃO é cota superior global: rampas de DESCIDA em operação contínua consomem mais, no modelo
            # dinâmico, do que a abstração instantânea conta (verificação densa, decisão do PR #23 item 3A)
            **subestimacao_h2(linhas),
            "massas_eventos_kg": {"partida": m_su, "parada": m_sd},
            "pre_condicionamento_s": pre, "temperatura_ambiente_C": float(t_amb_C), "delta_s": float(delta_s)}


def subestimacao_h2(linhas) -> dict:
    """Subestimação do H₂ do EMS frente ao modelo dinâmico, por intervalo (m_din − m_EMS > 0): máximo e total."""
    d = [x["h2_modelo_dinamico_kg"] - x["h2_ems_kg"] for x in linhas]
    pos = [v for v in d if v > 0]
    return {"h2_subestimacao_max_kg": max(pos) if pos else 0.0, "h2_subestimacao_total_kg": math.fsum(pos),
            "intervalos_com_subestimacao_h2": len(pos)}


def reavaliar_coerencia(v: dict, tol: dict | None = None) -> tuple[bool, list[dict]]:
    """Recalcula a coerência de UMA unidade a partir dos números gravados e das tolerâncias GRAVADAS (sem modelo): usado
    na reabertura para que o rótulo de aceitação não possa ser alterado sem que a verificação acuse."""
    delta_s = float(v["delta_s"])
    inc = []
    for x in v["intervalos"]:
        te = tolerancia_energia_kWh(x["energia_solicitada_kWh"], delta_s, tol)
        tm = tolerancia_h2_kg(x["h2_ems_kg"], delta_s, tol)
        if abs(x["energia_entregue_kWh"] - x["energia_solicitada_kWh"]) > te:
            inc.append({"intervalo": x["intervalo"], "criterio": "energia"})
        if abs(x["h2_modelo_dinamico_kg"] - x["h2_ems_kg"]) > tm:
            inc.append({"intervalo": x["intervalo"], "criterio": "h2"})
    return not inc, inc


__all__ = ["MARGEM_TRANSITORIO_S", "PONTOS_MALHA", "PRE_CONDICIONAMENTO_S", "TOLERANCIAS", "admissibilidade",
           "analise_transitoria", "massas_eventos", "modelo_dinamico", "parametros_dinamicos", "reavaliar_coerencia",
           "subestimacao_h2",
           "tolerancia_energia_kWh", "tolerancia_h2_kg", "verificar_despacho"]
