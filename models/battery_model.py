"""Modelos de bateria portados dos protótipos MATLAB fornecidos pelo projeto.

Inclui:
- Tremblay & Dessaint / Shepherd: modelo dinâmico genérico para quatro químicas.
- Circuito equivalente de 2 RC de Zhang et al. (2017) para célula Li-ion 18650 2,35 Ah.

Convenção elétrica comum aos dois modelos:
    corrente positiva  -> descarga (bateria entrega potência)
    corrente negativa  -> carga (bateria absorve potência)

Os modelos de célula são preservados e podem ser escalados para um banco Ns x Np.
A corrente do banco é dividida por Np e a tensão de célula é multiplicada por Ns.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import Iterable

import numpy as np
from models.numerics import trapezoid_integral
import pandas as pd


BATTERY_TREMBLAY = "tremblay"
BATTERY_2RC = "2rc"
BATTERY_MODEL_LABELS = {
    BATTERY_TREMBLAY: "Tremblay–Dessaint / Shepherd",
    BATTERY_2RC: "Circuito equivalente · 2 RC",
}


@dataclass(frozen=True)
class TremblayBattery:
    key: str
    name: str
    chemistry: str
    E0_V: float
    R_ohm: float
    K_V: float
    A_V: float
    B_Ah_inv: float
    Q_Ah: float
    V_nom_V: float


TREMBLAY_BATTERIES: dict[str, TremblayBattery] = {
    "lead_acid_12v_7p2ah": TremblayBattery(
        "lead_acid_12v_7p2ah", "Lead-Acid · 12 V · 7,2 Ah", "lead_acid",
        12.4659, 0.04, 0.047, 0.83, 125.0, 7.2, 12.0,
    ),
    "nicd_1p2v_2p3ah": TremblayBattery(
        "nicd_1p2v_2p3ah", "NiCd · 1,2 V · 2,3 Ah", "nimh_nicd",
        1.2705, 0.003, 0.0037, 0.127, 4.98, 2.3, 1.2,
    ),
    "liion_3p3v_2p3ah": TremblayBattery(
        "liion_3p3v_2p3ah", "Li-Ion · 3,3 V · 2,3 Ah", "li_ion",
        3.366, 0.01, 0.0076, 0.26422, 26.5487, 2.3, 3.3,
    ),
    "nimh_1p2v_6p5ah": TremblayBattery(
        "nimh_1p2v_6p5ah", "NiMH · 1,2 V · 6,5 Ah", "nimh_nicd",
        1.2816, 0.002, 0.0014, 0.111, 2.3077, 6.5, 1.2,
    ),
}


# Zhang et al. 2017 — pontos digitalizados / tabelas do script MATLAB fornecido.
RC_SOC = np.array([0.00, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00])
RC_OCV = np.array([3.465, 3.500, 3.560, 3.620, 3.680, 3.770, 3.780, 3.810, 3.870, 3.920, 4.010, 4.100, 4.180])
RC_R0 = np.array([0.0660, 0.0730, 0.0705, 0.0670, 0.0560, 0.0630, 0.0600, 0.0610, 0.0590, 0.0600, 0.0575, 0.0580, 0.0560])
RC_R1 = np.array([0.0334, 0.0051, 0.0041, 0.0043, 0.0040, 0.0072, 0.0045, 0.0025, 0.0047, 0.0052, 0.0047, 0.0049, 0.0043])
RC_C1 = np.array([0.0442, 1.0871, 1.2881, 1.8020, 1.3375, 2.6151, 3.4769, 1.1805, 1.5090, 1.2954, 0.9950, 1.0819, 2.5064]) * 1e3
RC_R2 = np.array([0.0169, 0.0091, 0.0085, 0.0079, 0.0091, 0.0023, 0.0048, 0.0086, 0.0087, 0.0102, 0.0102, 0.0433, 0.0070])
RC_C2 = np.array([0.3044, 0.6801, 0.7804, 1.0314, 0.7719, 3.5084, 1.4490, 0.5300, 0.6500, 0.5897, 0.4634, 0.8196, 1.3357]) * 1e4
RC_CAPACITY_AH = 2.350
RC_V_NOM_V = 3.7
RC_V_CUT_V = 2.7
_RC_OCV_POLY = np.polyfit(RC_SOC, RC_OCV, 6)


def read_battery_csv(data) -> pd.DataFrame:
    """Lê CSV com detecção simples de separador e decimal."""
    raw = data.getvalue() if hasattr(data, "getvalue") else data
    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig", errors="replace")
    else:
        text = str(raw)
    sample = text[:4000]
    sep = ";" if sample.count(";") > sample.count(",") else ","
    decimal = "," if sep == ";" and any("," in token for token in sample.split("\n")[:5]) else "."
    return pd.read_csv(StringIO(text), sep=sep, decimal=decimal)


def detect_battery_columns(raw: pd.DataFrame) -> tuple[str | None, str | None]:
    lowered = {str(c).strip().lower(): c for c in raw.columns}
    time_candidates = ("timestamp", "datetime", "data_hora", "tempo", "time")
    current_candidates = ("current_a", "corrente_a", "corrente", "current", "i_a", "i")
    tcol = next((lowered[k] for k in time_candidates if k in lowered), None)
    icol = next((lowered[k] for k in current_candidates if k in lowered), None)
    return tcol, icol


def prepare_battery_profile(
    raw: pd.DataFrame,
    timestamp_col: str,
    current_col: str,
) -> pd.DataFrame:
    if raw.empty:
        raise ValueError("O perfil de bateria está vazio.")
    ts = pd.to_datetime(raw[timestamp_col], errors="coerce", format="mixed")
    current = pd.to_numeric(raw[current_col], errors="coerce")
    if ts.isna().any():
        raise ValueError("Há timestamps inválidos no perfil.")
    if current.isna().any() or not np.isfinite(current.to_numpy(dtype=float)).all():
        raise ValueError("A corrente deve conter somente valores numéricos finitos.")
    out = pd.DataFrame({"timestamp": ts, "current_A": current.astype(float)})
    if out["timestamp"].duplicated().any():
        raise ValueError("O perfil não pode conter timestamps duplicados.")
    if not out["timestamp"].is_monotonic_increasing:
        raise ValueError("Os timestamps devem estar em ordem crescente.")
    if len(out) < 2:
        raise ValueError("O perfil precisa de pelo menos dois pontos temporais.")
    delta = out["timestamp"].diff().dt.total_seconds().iloc[1:].to_numpy(dtype=float)
    if (delta <= 0).any() or not np.isfinite(delta).all():
        raise ValueError("O passo temporal deve ser positivo e finito.")
    return out.reset_index(drop=True)


def build_battery_example() -> pd.DataFrame:
    """Perfil curto bidirecional para exercitar descarga, repouso e regeneração."""
    ts = pd.date_range("2026-09-14 08:00:00", periods=61, freq="10s")
    current = np.zeros(len(ts), dtype=float)
    current[1:16] = 2.35
    current[16:22] = 0.0
    current[22:36] = 4.0
    current[36:44] = -1.8
    current[44:51] = 0.0
    current[51:] = 1.2
    return pd.DataFrame({"timestamp": ts, "current_A": current})


def _tremblay_voltage(bat: TremblayBattery, it_Ah: float, i_star_A: float, exp_V: float, current_A: float) -> float:
    eps = 1e-5
    q = bat.Q_Ah
    if current_A >= 0.0:
        denom = max(q - it_Ah, eps)
        pol_voltage = bat.K_V * (q / denom) * it_Ah
        pol_resistance = bat.K_V * (q / denom) * i_star_A
        voltage = bat.E0_V - bat.R_ohm * current_A - pol_voltage - pol_resistance + exp_V
    else:
        denom_v = max(q - it_Ah, eps)
        pol_voltage = bat.K_V * (q / denom_v) * it_Ah
        if bat.chemistry in {"lead_acid", "li_ion"}:
            denom_r = it_Ah - 0.1 * q
        else:
            denom_r = abs(it_Ah) - 0.1 * q
        if abs(denom_r) < eps:
            denom_r = eps if denom_r >= 0 else -eps
        pol_resistance = bat.K_V * (q / denom_r) * i_star_A
        voltage = bat.E0_V - bat.R_ohm * current_A - pol_resistance - pol_voltage + exp_V
    return float(np.clip(voltage, 0.0, 2.0 * bat.E0_V))


def simulate_tremblay(
    profile: pd.DataFrame,
    battery_key: str = "liion_3p3v_2p3ah",
    *,
    n_series: int = 1,
    n_parallel: int = 1,
    initial_soc: float = 1.0,
    filter_tau_s: float = 30.0,
    integration_step_s: float = 1.0,
) -> pd.DataFrame:
    if battery_key not in TREMBLAY_BATTERIES:
        raise KeyError(f"Bateria Tremblay desconhecida: {battery_key}")
    if n_series < 1 or n_parallel < 1:
        raise ValueError("Ns e Np devem ser inteiros positivos.")
    if not 0.0 <= initial_soc <= 1.0:
        raise ValueError("SOC inicial deve estar entre 0 e 1.")
    if filter_tau_s <= 0 or integration_step_s <= 0:
        raise ValueError("As constantes temporais numéricas devem ser positivas.")

    bat = TREMBLAY_BATTERIES[battery_key]
    ts = pd.to_datetime(profile["timestamp"]).reset_index(drop=True)
    bank_current = pd.to_numeric(profile["current_A"], errors="raise").to_numpy(dtype=float)
    cell_current = bank_current / float(n_parallel)
    n = len(profile)

    it_Ah = (1.0 - initial_soc) * bat.Q_Ah
    i_star = 0.0
    exp_v = bat.A_V * np.exp(-bat.B_Ah_inv * it_Ah) if bat.chemistry == "li_ion" else bat.A_V

    records: list[dict[str, float | str | pd.Timestamp | bool]] = []
    previous_ts: pd.Timestamp | None = None
    v_cell = _tremblay_voltage(bat, it_Ah, i_star, exp_v, float(cell_current[0]))

    for k in range(n):
        t = pd.Timestamp(ts.iloc[k])
        dt_total = 0.0 if previous_ts is None else float((t - previous_ts).total_seconds())
        i_cell = float(cell_current[k])

        if previous_ts is not None and dt_total > 0:
            substeps = max(1, int(np.ceil(dt_total / integration_step_s)))
            h = dt_total / substeps
            for _ in range(substeps):
                # Euler explícito do protótipo, preservado com passo interno <= 1 s por padrão.
                i_star = i_star + (h / filter_tau_s) * (i_cell - i_star)
                if bat.chemistry == "li_ion":
                    exp_v = bat.A_V * np.exp(-bat.B_Ah_inv * it_Ah)
                else:
                    target = 0.0 if i_cell >= 0 else bat.A_V
                    d_exp = bat.B_Ah_inv * abs(i_cell) * (-exp_v + target)
                    exp_v = float(np.clip(exp_v + d_exp * h, 0.0, bat.A_V))
                # MATLAB: tensão usa it no início do passo; SOC é atualizado depois.
                v_cell = _tremblay_voltage(bat, it_Ah, i_star, exp_v, i_cell)
                it_Ah += i_cell * h / 3600.0
                it_Ah = float(np.clip(it_Ah, 0.0, bat.Q_Ah))
        elif previous_ts is None:
            v_cell = _tremblay_voltage(bat, it_Ah, i_star, exp_v, i_cell)

        v_bank = v_cell * n_series
        p_bank_w = v_bank * bank_current[k]
        soc = float(np.clip(1.0 - it_Ah / bat.Q_Ah, 0.0, 1.0))
        records.append({
            "timestamp": t,
            "current_A": float(bank_current[k]),
            "cell_current_A": i_cell,
            "cell_voltage_V": v_cell,
            "voltage_V": v_bank,
            "power_W": p_bank_w,
            "soc": soc,
            "soc_percent": soc * 100.0,
            "capacity_withdrawn_Ah_cell": it_Ah,
            "filtered_current_A_cell": i_star,
            "exponential_voltage_V_cell": exp_v,
            "model": BATTERY_MODEL_LABELS[BATTERY_TREMBLAY],
            "limit_flag": bool((soc <= 1e-6 and i_cell > 0) or (soc >= 1 - 1e-6 and i_cell < 0)),
        })
        previous_ts = t

    result = pd.DataFrame.from_records(records)
    result.attrs.update({
        "model_id": BATTERY_TREMBLAY,
        "battery_key": battery_key,
        "battery_name": bat.name,
        "n_series": n_series,
        "n_parallel": n_parallel,
        "integration_step_s": integration_step_s,
        "nominal_energy_Wh": bat.V_nom_V * bat.Q_Ah * n_series * n_parallel,
    })
    return result


def _rc_interp(values: np.ndarray, soc: float) -> float:
    return float(np.interp(np.clip(soc, 0.0, 1.0), RC_SOC, values))


def _rc_ocv(soc: float) -> float:
    return float(np.polyval(_RC_OCV_POLY, np.clip(soc, 0.0, 1.0)))


def simulate_2rc(
    profile: pd.DataFrame,
    *,
    n_series: int = 1,
    n_parallel: int = 1,
    initial_soc: float = 1.0,
    integration_step_s: float = 1.0,
) -> pd.DataFrame:
    if n_series < 1 or n_parallel < 1:
        raise ValueError("Ns e Np devem ser inteiros positivos.")
    if not 0.0 <= initial_soc <= 1.0:
        raise ValueError("SOC inicial deve estar entre 0 e 1.")
    if integration_step_s <= 0:
        raise ValueError("O passo interno deve ser positivo.")

    ts = pd.to_datetime(profile["timestamp"]).reset_index(drop=True)
    bank_current = pd.to_numeric(profile["current_A"], errors="raise").to_numpy(dtype=float)
    cell_current = bank_current / float(n_parallel)
    capacity_As = RC_CAPACITY_AH * 3600.0
    soc = float(initial_soc)
    vc1 = 0.0
    vc2 = 0.0
    previous_ts: pd.Timestamp | None = None
    records: list[dict[str, float | str | pd.Timestamp | bool]] = []
    v_cell = _rc_ocv(soc)

    for k, t_raw in enumerate(ts):
        t = pd.Timestamp(t_raw)
        dt_total = 0.0 if previous_ts is None else float((t - previous_ts).total_seconds())
        i_cell = float(cell_current[k])

        # Parâmetros reportados na amostra final.
        r0 = _rc_interp(RC_R0, soc)
        r1 = _rc_interp(RC_R1, soc)
        c1 = _rc_interp(RC_C1, soc)
        r2 = _rc_interp(RC_R2, soc)
        c2 = _rc_interp(RC_C2, soc)

        if previous_ts is not None and dt_total > 0:
            substeps = max(1, int(np.ceil(dt_total / integration_step_s)))
            h = dt_total / substeps
            for _ in range(substeps):
                r0 = _rc_interp(RC_R0, soc)
                r1 = _rc_interp(RC_R1, soc)
                c1 = _rc_interp(RC_C1, soc)
                r2 = _rc_interp(RC_R2, soc)
                c2 = _rc_interp(RC_C2, soc)
                vc1 = vc1 + h * (i_cell / c1 - vc1 / (r1 * c1))
                vc2 = vc2 + h * (i_cell / c2 - vc2 / (r2 * c2))
                soc = float(np.clip(soc - (i_cell * h) / capacity_As, 0.0, 1.0))
                v_cell = _rc_ocv(soc) - i_cell * r0 - vc1 - vc2
        elif previous_ts is None:
            v_cell = _rc_ocv(soc) - i_cell * r0 - vc1 - vc2

        ocv = _rc_ocv(soc)
        v_bank = v_cell * n_series
        p_bank_w = v_bank * bank_current[k]
        records.append({
            "timestamp": t,
            "current_A": float(bank_current[k]),
            "cell_current_A": i_cell,
            "cell_voltage_V": v_cell,
            "voltage_V": v_bank,
            "power_W": p_bank_w,
            "soc": soc,
            "soc_percent": soc * 100.0,
            "ocv_V_cell": ocv,
            "R0_ohm_cell": r0,
            "R1_ohm_cell": r1,
            "C1_F_cell": c1,
            "R2_ohm_cell": r2,
            "C2_F_cell": c2,
            "V_RC1_V_cell": vc1,
            "V_RC2_V_cell": vc2,
            "model": BATTERY_MODEL_LABELS[BATTERY_2RC],
            "limit_flag": bool((soc <= 1e-6 and i_cell > 0) or (soc >= 1 - 1e-6 and i_cell < 0) or v_cell <= RC_V_CUT_V),
        })
        previous_ts = t

    result = pd.DataFrame.from_records(records)
    result.attrs.update({
        "model_id": BATTERY_2RC,
        "battery_key": "zhang_18650_2350mAh",
        "battery_name": "Li-Ion 18650 · 3,7 V · 2,35 Ah · Zhang 2017",
        "n_series": n_series,
        "n_parallel": n_parallel,
        "integration_step_s": integration_step_s,
        "nominal_energy_Wh": RC_V_NOM_V * RC_CAPACITY_AH * n_series * n_parallel,
    })
    return result


def _integrate_energy_wh(power_w: np.ndarray, timestamps: pd.Series | pd.DatetimeIndex) -> tuple[float, float]:
    ts = pd.to_datetime(timestamps)
    if len(ts) < 2:
        return 0.0, 0.0
    delta = ts - (ts.iloc[0] if isinstance(ts, pd.Series) else ts[0])
    seconds = delta.dt.total_seconds().to_numpy(dtype=float) if isinstance(delta, pd.Series) else delta.total_seconds()
    x_h = np.asarray(seconds, dtype=float) / 3600.0
    discharge = np.maximum(np.asarray(power_w, dtype=float), 0.0)
    charge = np.maximum(-np.asarray(power_w, dtype=float), 0.0)
    return trapezoid_integral(discharge, x_h), trapezoid_integral(charge, x_h)


def battery_kpis(result: pd.DataFrame) -> dict[str, float]:
    discharge_Wh, charge_Wh = _integrate_energy_wh(result["power_W"].to_numpy(dtype=float), result["timestamp"])
    return {
        "energy_discharge_Wh": discharge_Wh,
        "energy_charge_Wh": charge_Wh,
        "net_energy_Wh": discharge_Wh - charge_Wh,
        "soc_initial_percent": float(result["soc_percent"].iloc[0]),
        "soc_final_percent": float(result["soc_percent"].iloc[-1]),
        "soc_min_percent": float(result["soc_percent"].min()),
        "soc_max_percent": float(result["soc_percent"].max()),
        "voltage_min_V": float(result["voltage_V"].min()),
        "voltage_max_V": float(result["voltage_V"].max()),
        "power_discharge_peak_W": float(np.maximum(result["power_W"], 0).max()),
        "power_charge_peak_W": float(np.maximum(-result["power_W"], 0).max()),
        "limit_points": float(result["limit_flag"].sum()),
    }


def export_battery_dataframe(result: pd.DataFrame) -> pd.DataFrame:
    preferred = [
        "timestamp", "current_A", "voltage_V", "power_W", "soc_percent",
        "cell_current_A", "cell_voltage_V", "limit_flag", "model",
        "ocv_V_cell", "V_RC1_V_cell", "V_RC2_V_cell",
        "filtered_current_A_cell", "exponential_voltage_V_cell",
    ]
    return result[[c for c in preferred if c in result.columns]].copy()


__all__ = [
    "BATTERY_2RC", "BATTERY_TREMBLAY", "BATTERY_MODEL_LABELS", "TREMBLAY_BATTERIES",
    "RC_CAPACITY_AH", "RC_V_NOM_V", "RC_V_CUT_V", "read_battery_csv",
    "detect_battery_columns", "prepare_battery_profile", "build_battery_example",
    "simulate_tremblay", "simulate_2rc", "battery_kpis", "export_battery_dataframe",
]
