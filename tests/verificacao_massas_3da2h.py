"""Verificação INDEPENDENTE das massas ADICIONAIS por evento (Piso 3D-A2-H; decisão do responsável no PR #23, item 3A).

O preflight escolhe m_SU/m_SD = máx(0, máx_p δ(p)) numa malha de 9 potências (``pemfc_dinamica.analise_transitoria``,
janelas curtas). Uma malha discreta não prova, sozinha, que a constante é conservadora entre os pontos. Esta verificação
NÃO reutiliza aquela rotina:

* simula intervalos COMPLETOS de Δ (padrão 60 min) em SEQUÊNCIAS longas e contínuas do modelo dinâmico (cada partida a
  partir de OFF, cada parada a partir de RUN estabelecido, cada rampa a partir do regime do intervalo anterior);
* integra ∫ q dt e ∫ P dt com uma implementação PRÓPRIA (retenção de ordem zero vetorizada, sem ``_integral``);
* compara, intervalo a intervalo, a massa CONTABILIZADA pelo EMS (q̂(p)·Δ·u + m_SU·y + m_SD·z — a contabilidade do
  MILP) com a massa do modelo dinâmico, numa malha DENSA de potências (passo 0,5 kW: partidas e paradas) e de pares
  (passo 2,5 kW: rampas em operação contínua), em várias configurações físicas ADMISSÍVEIS.

Uso como roteiro: ``python tests/verificacao_massas_3da2h.py <saida.json>`` (todas as configurações). O teste
``tests/test_piso3da2h_verificacao_massas.py`` roda a configuração nominal numa malha um pouco menos densa.
Nenhuma massa é inventada: tudo vem do modelo dinâmico e da curva certificada.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integracao_v2 import curva_h2 as CH  # noqa: E402
from integracao_v2 import pemfc_dinamica as DY  # noqa: E402

# Configurações físicas ADMISSÍVEIS (partida quente, P_min >= IDLE, rampa no limite do modelo): a nominal + condições de
# generalização (que NÃO foram usadas para escolher os limiares B04) + variações de P_min e T_amb.
CONFIGURACOES = (
    {"nome": "nominal", "cond": (353.15, 140.0, 120.0, 101.325), "p_min": 10.0, "t_amb": 25.0},
    {"nome": "nominal_pmin15", "cond": (353.15, 140.0, 120.0, 101.325), "p_min": 15.0, "t_amb": 25.0},
    {"nome": "stack_333K", "cond": (333.15, 140.0, 120.0, 101.325), "p_min": 10.0, "t_amb": 25.0},
    {"nome": "stack_358K_tamb6", "cond": (358.15, 140.0, 120.0, 101.325), "p_min": 10.0, "t_amb": 6.0},
    {"nome": "pressao_baixa_pmin12", "cond": (353.15, 120.0, 100.0, 95.0), "p_min": 12.0, "t_amb": 25.0},
    {"nome": "stack_348K_tamb40", "cond": (348.15, 130.0, 110.0, 100.0), "p_min": 10.0, "t_amb": 40.0},
)


def _integrais(res: pd.DataFrame, t0: pd.Timestamp, delta_s: float, n: int):
    """∫ q dt [kg] e ∫ P dt [kWh] por intervalo [t0 + iΔ, t0 + (i+1)Δ) — retenção de ordem zero, vetorizada."""
    t = (pd.to_datetime(res["timestamp"]) - t0).dt.total_seconds().to_numpy()
    q = res["hydrogen_supplied_kg_h"].to_numpy(dtype=float)
    p = res["P_FC_delivered_kW"].to_numpy(dtype=float)
    dt = np.diff(t)
    idx = np.floor(t[:-1] / delta_s + 1e-12).astype(int)        # intervalo de cada segmento (o passo interno divide Δ)
    m = np.bincount(idx, weights=q[:-1] * dt, minlength=n)[:n] / 3600.0
    e = np.bincount(idx, weights=p[:-1] * dt, minlength=n)[:n] / 3600.0
    return m, e


def _simular_sequencia(cond, t_amb, potencias, habilitado, delta_s):
    t0 = pd.Timestamp("2000-01-01T00:00:00")
    n = len(potencias)
    prof = pd.DataFrame({"timestamp": [t0 + pd.Timedelta(seconds=delta_s * i) for i in range(n + 1)],
                         "P_FC_requested_kW": [float(x) for x in potencias] + [0.0],
                         "FC_enable": [bool(x) for x in habilitado] + [False], "T_ambient_C": float(t_amb)})
    res = DY.modelo_dinamico(cond).simulate_profile(prof)
    return _integrais(res, t0, delta_s, n)


def verificar_configuracao(cfg: dict, *, passo_eventos_kW: float = 0.5, passo_rampas_kW: float = 2.5,
                           delta_s: float = 3600.0) -> dict:
    cond = CH.CondicoesPEMFC(*cfg["cond"])
    curva = CH.obter_curva(cond, cfg["p_min"])
    p_min, p_max = curva.p_min_kW, curva.p_max_kW
    mev = DY.massas_eventos(cond, cfg["t_amb"], p_min, p_max)
    m_su, m_sd = mev["m_partida_kg"], mev["m_parada_kg"]
    adm = DY.admissibilidade(mev["analise"], curva, delta_s, "instantanea_unidade_quente")
    h = delta_s / 3600.0
    t_ini = time.perf_counter()
    # ---- partidas e paradas: [OFF] → [ON em p] → [OFF] … (o intervalo ON tem a partida; o OFF seguinte, a parada)
    grade = np.unique(np.concatenate([np.arange(p_min, p_max, passo_eventos_kW), [p_max]]))
    pot, hab = [0.0], [False]
    for p in grade:
        pot += [float(p), 0.0]
        hab += [True, False]
    m, e = _simular_sequencia(cond, cfg["t_amb"], pot, hab, delta_s)
    eventos = []
    for k, p in enumerate(grade):
        i_on, i_off = 1 + 2 * k, 2 + 2 * k
        q_hat = float(curva.q_pwl([p])[0])
        eventos.append({"p_kW": float(p),
                        "partida_ems_kg": q_hat * h + m_su, "partida_din_kg": float(m[i_on]),
                        "partida_E_req_kWh": float(p) * h, "partida_E_din_kWh": float(e[i_on]),
                        "parada_ems_kg": m_sd, "parada_din_kg": float(m[i_off]), "parada_E_din_kWh": float(e[i_off])})
    # ---- rampas em operação contínua: sequência ON que percorre todos os pares ordenados (p_a → p_b), p_a ≠ p_b
    gr = np.unique(np.concatenate([np.arange(p_min, p_max, passo_rampas_kW), [p_max]]))
    seq = []
    for a in gr:
        for b in gr:
            if a != b:
                seq += [float(a), float(b)]
    pot, hab = [float(seq[0])] + seq, [True] * (len(seq) + 1)            # 1º intervalo: estabelece o regime
    m, e = _simular_sequencia(cond, cfg["t_amb"], pot, hab, delta_s)
    rampas = []
    for i in range(2, len(pot)):                                          # cada intervalo i é a rampa pot[i-1] → pot[i]
        a, b = pot[i - 1], pot[i]
        if a == b:
            continue
        rampas.append({"de_kW": a, "para_kW": b, "ems_kg": float(curva.q_pwl([b])[0]) * h, "din_kg": float(m[i]),
                       "E_req_kWh": b * h, "E_din_kWh": float(e[i])})
    dur = time.perf_counter() - t_ini

    def pior(xs, ems, din, ref):
        r = [(x[ems] - x[din], x) for x in xs]
        rmin, xmin = min(r, key=lambda t: t[0])
        return {"residuo_min_kg": rmin, "caso": {k: v for k, v in xmin.items()},
                "subestimacao_max_kg": max(0.0, -rmin), "subestimacao_max_rel": max(0.0, -rmin) / xmin[ref]
                if xmin[ref] > 0 else None, "superestimacao_max_kg": max(t[0] for t in r),
                "casos_com_subestimacao": sum(1 for t in r if t[0] < -1e-12)}
    return {"configuracao": cfg, "p_min_kW": p_min, "p_max_kW": p_max, "delta_s": delta_s,
            "m_partida_kg": m_su, "m_parada_kg": m_sd, "admissivel_a_priori": not adm, "violacoes_a_priori": adm,
            "n_partidas": len(eventos), "n_paradas": len(eventos), "n_rampas": len(rampas),
            "passo_eventos_kW": passo_eventos_kW, "passo_rampas_kW": passo_rampas_kW,
            "partida": pior(eventos, "partida_ems_kg", "partida_din_kg", "partida_din_kg"),
            "parada": pior(eventos, "parada_ems_kg", "parada_din_kg", "parada_din_kg"),
            "rampa_subida": pior([r for r in rampas if r["para_kW"] > r["de_kW"]], "ems_kg", "din_kg", "din_kg"),
            "rampa_descida": pior([r for r in rampas if r["para_kW"] < r["de_kW"]], "ems_kg", "din_kg", "din_kg"),
            "energia_partida_deficit_max_kWh": max(x["partida_E_req_kWh"] - x["partida_E_din_kWh"] for x in eventos),
            "energia_parada_excesso_max_kWh": max(x["parada_E_din_kWh"] for x in eventos),
            "energia_rampa_desvio_max_kWh": max(abs(r["E_din_kWh"] - r["E_req_kWh"]) for r in rampas),
            "segundos": dur}


def main(saida: str | None = None) -> dict:
    out = {"formato": "seeds2-3da2h-verificacao-massas", "versao": 1,
           "metodo": __doc__.strip().splitlines()[0], "configuracoes": []}
    for cfg in CONFIGURACOES:
        r = verificar_configuracao(cfg)
        out["configuracoes"].append(r)
        print(f"{cfg['nome']:24s} m_SU={r['m_partida_kg']:.6f} m_SD={r['m_parada_kg']:.6f} admissível={r['admissivel_a_priori']}"
              f" | partida subest.={r['partida']['subestimacao_max_kg']:.2e} parada subest.={r['parada']['subestimacao_max_kg']:.2e}"
              f" | rampa↑ subest.={r['rampa_subida']['subestimacao_max_kg']:.2e} rampa↓ subest.="
              f"{r['rampa_descida']['subestimacao_max_kg']:.4g} kg ({100 * (r['rampa_descida']['subestimacao_max_rel'] or 0):.3f} %)"
              f" | {r['n_partidas']}+{r['n_paradas']}+{r['n_rampas']} casos, {r['segundos']:.0f} s", flush=True)
    if saida:
        Path(saida).write_text(json.dumps(out, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
