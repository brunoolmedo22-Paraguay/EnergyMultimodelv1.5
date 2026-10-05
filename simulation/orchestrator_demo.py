"""Synthetic orchestration engine used to prototype the future optimizer UI.

This module is deliberately independent from the final optimizer.  It creates a
physically coherent, deterministic 24 h scenario so the Streamlit interface can
be designed and tested before the optimization code is integrated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

import numpy as np
import pandas as pd


SOURCE_LABELS = {
    "solar": "Solar",
    "wind": "Eólica",
    "battery": "Bateria",
    "h2": "H₂ / PEMFC",
    "thermal": "Térmica",
}


@dataclass(frozen=True)
class DemoConfig:
    horizon_hours: int = 24
    timestep_minutes: int = 15
    demand_scale: float = 1.0
    demand_profile: str = "Operação balanceada"
    initial_soc_pct: float = 70.0
    battery_capacity_kwh: float = 180.0
    battery_charge_max_kw: float = 38.0
    battery_discharge_max_kw: float = 48.0
    battery_soc_min_pct: float = 20.0
    battery_soc_max_pct: float = 95.0
    h2_max_kw: float = 50.0
    thermal_max_kw: float = 85.0
    thermal_ramp_kw_per_step: float = 24.0
    active_solar: bool = True
    active_wind: bool = True
    active_battery: bool = True
    active_h2: bool = True
    active_thermal: bool = True
    battery_preservation: float = 0.35
    h2_preservation: float = 0.45
    thermal_cost: float = 0.75


def _gaussian(hours: np.ndarray, center: float, width: float, amplitude: float) -> np.ndarray:
    return amplitude * np.exp(-0.5 * ((hours - center) / width) ** 2)


def make_demand_curve(
    start_date: date | pd.Timestamp | None = None,
    *,
    timestep_minutes: int = 15,
    profile: str = "Operação balanceada",
    scale: float = 1.0,
) -> pd.DataFrame:
    """Create a deterministic demand profile in kW."""
    start = pd.Timestamp(start_date or "2026-09-28").normalize()
    periods = int(round(24 * 60 / timestep_minutes))
    idx = pd.date_range(start, periods=periods, freq=f"{timestep_minutes}min")
    h = idx.hour.to_numpy(dtype=float) + idx.minute.to_numpy(dtype=float) / 60.0

    if profile == "Pico noturno":
        demand = 47 + _gaussian(h, 8.0, 1.6, 25) + _gaussian(h, 19.2, 1.75, 68)
    elif profile == "Carga quase constante":
        demand = 72 + _gaussian(h, 13.0, 4.5, 11) + _gaussian(h, 19.0, 2.4, 9)
    elif profile == "Dois picos":
        demand = 48 + _gaussian(h, 8.0, 1.45, 48) + _gaussian(h, 18.6, 1.65, 58)
    else:
        demand = (
            49
            + _gaussian(h, 7.8, 1.6, 30)
            + _gaussian(h, 13.2, 2.7, 19)
            + _gaussian(h, 19.0, 1.7, 56)
        )

    # Small deterministic intra-day variation: enough to make the prototype
    # feel operational without introducing randomness between reruns.
    demand += 2.7 * np.sin(2 * np.pi * (h - 0.7) / 3.8) + 1.3 * np.sin(2 * np.pi * h / 1.9)
    demand = np.maximum(demand * float(scale), 12.0)
    return pd.DataFrame({"timestamp": idx, "P_demanda_kW": demand})


def _renewable_profiles(index: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    h = index.hour.to_numpy(dtype=float) + index.minute.to_numpy(dtype=float) / 60.0

    solar_shape = np.zeros_like(h)
    daytime = (h >= 5.8) & (h <= 18.3)
    solar_shape[daytime] = np.sin(np.pi * (h[daytime] - 5.8) / 12.5) ** 1.65
    cloud = 0.93 - 0.09 * np.exp(-0.5 * ((h - 12.9) / 0.75) ** 2) + 0.035 * np.sin(2 * np.pi * h / 2.7)
    solar = np.maximum(0.0, 112.0 * solar_shape * cloud)

    wind = 31.0 + 10.0 * np.sin(2 * np.pi * (h + 1.4) / 8.3) + 5.5 * np.sin(2 * np.pi * h / 3.1)
    wind += 5.0 * np.exp(-0.5 * ((h - 3.5) / 1.8) ** 2)
    wind = np.clip(wind, 8.0, 54.0)
    return solar, wind


def _dispatch_order(cfg: DemoConfig) -> list[str]:
    penalties = {
        "battery": 0.45 + 2.2 * float(cfg.battery_preservation),
        "h2": 0.65 + 2.0 * float(cfg.h2_preservation),
        "thermal": 0.90 + 2.4 * float(cfg.thermal_cost),
    }
    active = {
        "battery": cfg.active_battery,
        "h2": cfg.active_h2,
        "thermal": cfg.active_thermal,
    }
    return sorted((s for s in penalties if active[s]), key=lambda s: penalties[s])


def run_demo_optimizer(
    demand: pd.DataFrame,
    config: DemoConfig | Mapping[str, object] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Dispatch synthetic sources against *demand* and return results + summary."""
    if config is None:
        cfg = DemoConfig()
    elif isinstance(config, DemoConfig):
        cfg = config
    else:
        known = {field: config[field] for field in DemoConfig.__dataclass_fields__ if field in config}
        cfg = DemoConfig(**known)

    if "timestamp" not in demand.columns or "P_demanda_kW" not in demand.columns:
        raise ValueError("A curva de carga deve conter timestamp e P_demanda_kW.")

    work = demand[["timestamp", "P_demanda_kW"]].copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"])
    work = work.sort_values("timestamp").reset_index(drop=True)
    if len(work) < 2:
        dt_h = cfg.timestep_minutes / 60.0
    else:
        dt_h = max((work.loc[1, "timestamp"] - work.loc[0, "timestamp"]).total_seconds() / 3600.0, 1 / 60)

    solar_av, wind_av = _renewable_profiles(pd.DatetimeIndex(work["timestamp"]))
    if not cfg.active_solar:
        solar_av *= 0.0
    if not cfg.active_wind:
        wind_av *= 0.0

    n = len(work)
    out = work.copy()
    out["P_solar_disponivel_kW"] = solar_av
    out["P_eolica_disponivel_kW"] = wind_av
    out["P_solar_kW"] = solar_av
    out["P_eolica_kW"] = wind_av
    out["P_bateria_kW"] = 0.0
    out["P_H2_kW"] = 0.0
    out["P_termica_kW"] = 0.0
    out["P_excedente_kW"] = 0.0
    out["P_nao_atendida_kW"] = 0.0
    out["SOC_bateria_pct"] = np.nan
    out["H2_consumo_kg"] = 0.0
    out["H2_acumulado_kg"] = 0.0
    out["P_bateria_solicitada_kW"] = 0.0
    out["P_H2_solicitada_kW"] = 0.0
    out["P_termica_solicitada_kW"] = 0.0

    soc_kwh = cfg.battery_capacity_kwh * cfg.initial_soc_pct / 100.0
    soc_min_kwh = cfg.battery_capacity_kwh * cfg.battery_soc_min_pct / 100.0
    soc_max_kwh = cfg.battery_capacity_kwh * cfg.battery_soc_max_pct / 100.0
    eta_c = 0.95
    eta_d = 0.94
    thermal_prev = 0.0
    h2_total = 0.0
    order = _dispatch_order(cfg)

    for i in range(n):
        demand_kw = float(out.at[i, "P_demanda_kW"])
        renewable_kw = float(solar_av[i] + wind_av[i])
        residual = demand_kw - renewable_kw

        if residual < 0.0 and cfg.active_battery:
            surplus = -residual
            energy_room = max(0.0, soc_max_kwh - soc_kwh)
            charge_limit_energy = energy_room / max(dt_h * eta_c, 1e-9)
            p_charge = min(surplus, cfg.battery_charge_max_kw, charge_limit_energy)
            out.at[i, "P_bateria_kW"] = -p_charge
            out.at[i, "P_bateria_solicitada_kW"] = -p_charge
            soc_kwh += p_charge * dt_h * eta_c
            residual += p_charge

        if residual > 1e-9:
            for source in order:
                if residual <= 1e-9:
                    break
                if source == "battery":
                    energy_available = max(0.0, soc_kwh - soc_min_kwh)
                    p_energy_limit = energy_available * eta_d / max(dt_h, 1e-9)
                    p = min(residual, cfg.battery_discharge_max_kw, p_energy_limit)
                    out.at[i, "P_bateria_solicitada_kW"] = p
                    out.at[i, "P_bateria_kW"] = p
                    soc_kwh -= (p / eta_d) * dt_h
                elif source == "h2":
                    p = min(residual, cfg.h2_max_kw)
                    out.at[i, "P_H2_solicitada_kW"] = p
                    out.at[i, "P_H2_kW"] = p
                    h2_step = p * dt_h * 0.060
                    out.at[i, "H2_consumo_kg"] = h2_step
                    h2_total += h2_step
                else:
                    lower = max(0.0, thermal_prev - cfg.thermal_ramp_kw_per_step)
                    upper = min(cfg.thermal_max_kw, thermal_prev + cfg.thermal_ramp_kw_per_step)
                    target = min(residual, cfg.thermal_max_kw)
                    p = float(np.clip(target, lower, upper))
                    out.at[i, "P_termica_solicitada_kW"] = target
                    out.at[i, "P_termica_kW"] = p
                    thermal_prev = p
                residual -= p

        # If the thermal plant was not dispatched, it can ramp down rather than
        # disappear instantaneously.  We do not force minimum generation here;
        # the final optimizer will own that detailed constraint.
        if out.at[i, "P_termica_kW"] == 0.0 and thermal_prev > 0.0:
            thermal_prev = max(0.0, thermal_prev - cfg.thermal_ramp_kw_per_step)

        if residual < -1e-9:
            out.at[i, "P_excedente_kW"] = -residual
        elif residual > 1e-9:
            out.at[i, "P_nao_atendida_kW"] = residual

        out.at[i, "SOC_bateria_pct"] = 100.0 * soc_kwh / cfg.battery_capacity_kwh
        out.at[i, "H2_acumulado_kg"] = h2_total

    out["P_geracao_total_kW"] = (
        out["P_solar_kW"]
        + out["P_eolica_kW"]
        + out["P_bateria_kW"].clip(lower=0)
        + out["P_H2_kW"]
        + out["P_termica_kW"]
    )
    out["P_bateria_carga_kW"] = (-out["P_bateria_kW"]).clip(lower=0)
    out["P_bateria_descarga_kW"] = out["P_bateria_kW"].clip(lower=0)
    out["P_balanco_kW"] = (
        out["P_geracao_total_kW"] - out["P_bateria_carga_kW"] - out["P_demanda_kW"] - out["P_excedente_kW"]
    )

    energy = lambda col: float(out[col].sum() * dt_h)
    demand_energy = energy("P_demanda_kW")
    renewable_energy = energy("P_solar_kW") + energy("P_eolica_kW")
    renewable_used_energy = max(0.0, renewable_energy - energy("P_excedente_kW"))
    supplied_energy = max(0.0, demand_energy - energy("P_nao_atendida_kW"))
    summary = {
        "dt_h": dt_h,
        "demand_energy_kwh": demand_energy,
        "peak_demand_kw": float(out["P_demanda_kW"].max()),
        "average_demand_kw": float(out["P_demanda_kW"].mean()),
        "load_factor_pct": float(100 * out["P_demanda_kW"].mean() / out["P_demanda_kW"].max()),
        "solar_energy_kwh": energy("P_solar_kW"),
        "wind_energy_kwh": energy("P_eolica_kW"),
        "battery_discharge_kwh": energy("P_bateria_descarga_kW"),
        "battery_charge_kwh": energy("P_bateria_carga_kW"),
        "h2_energy_kwh": energy("P_H2_kW"),
        "thermal_energy_kwh": energy("P_termica_kW"),
        "excess_energy_kwh": energy("P_excedente_kW"),
        "unserved_energy_kwh": energy("P_nao_atendida_kW"),
        "renewable_share_pct": 100.0 * min(renewable_used_energy, supplied_energy) / max(supplied_energy, 1e-9),
        "final_soc_pct": float(out["SOC_bateria_pct"].iloc[-1]),
        "min_soc_pct": float(out["SOC_bateria_pct"].min()),
        "h2_consumed_kg": float(out["H2_consumo_kg"].sum()),
        "dispatch_order": order,
        "status": "ÓTIMO · DEMO" if energy("P_nao_atendida_kW") < 1e-6 else "VIÁVEL COM DÉFICIT · DEMO",
        "solve_time_s": 0.18,
        "objective_value": float(0.14 * energy("P_bateria_descarga_kW") + 0.32 * energy("P_H2_kW") + 0.58 * energy("P_termica_kW") + 25 * energy("P_nao_atendida_kW")),
    }
    return out, summary


def build_demo_model_frame(dispatch: pd.DataFrame, model: str) -> pd.DataFrame:
    """Return a model-centric dataframe used by the Resultados dos Modelos page."""
    d = dispatch.copy()
    if model == "solar":
        return pd.DataFrame({
            "timestamp": d["timestamp"],
            "Disponível [kW]": d["P_solar_disponivel_kW"],
            "Entregue [kW]": d["P_solar_kW"],
            "Solicitado [kW]": d["P_solar_disponivel_kW"],
        })
    if model == "wind":
        return pd.DataFrame({
            "timestamp": d["timestamp"],
            "Disponível [kW]": d["P_eolica_disponivel_kW"],
            "Entregue [kW]": d["P_eolica_kW"],
            "Solicitado [kW]": d["P_eolica_disponivel_kW"],
        })
    if model == "battery":
        return pd.DataFrame({
            "timestamp": d["timestamp"],
            "Solicitado [kW]": d["P_bateria_solicitada_kW"],
            "Entregue [kW]": d["P_bateria_kW"],
            "SOC [%]": d["SOC_bateria_pct"],
        })
    if model == "h2":
        return pd.DataFrame({
            "timestamp": d["timestamp"],
            "Solicitado [kW]": d["P_H2_solicitada_kW"],
            "Entregue [kW]": d["P_H2_kW"],
            "H₂ acumulado [kg]": d["H2_acumulado_kg"],
        })
    return pd.DataFrame({
        "timestamp": d["timestamp"],
        "Solicitado [kW]": d["P_termica_solicitada_kW"],
        "Entregue [kW]": d["P_termica_kW"],
        "Rampa [kW/passo]": d["P_termica_kW"].diff().fillna(d["P_termica_kW"]),
    })
