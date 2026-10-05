"""Orquestrador do modo MIX.

A camada MIX não cria novos modelos físicos. Ela apenas:
- usa o CSV operacional como linha do tempo mestre;
- interpola as condições meteorológicas nessa linha do tempo;
- chama os modelos Solar, Eólico, Térmico, Bateria e H2 já existentes;
- consolida as saídas em um único dataframe de potência.

Convenções elétricas
-------------------
* Solar/eólica: sempre injetam 100 % da potência calculada.
* Bateria: potência solicitada positiva = descarga; negativa = carga.
* Térmica/H2: potência solicitada >= 0.
* O MIX não executa curtailment nem carga automática por excedente: apenas sinaliza.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Mapping
import unicodedata

import numpy as np
import pandas as pd

from config.pv_database import get_module
from config.thermal_database import LOCAL_GENERATOR, THERMAL_PLANT
from config.wind_turbine_database import get_turbine
from h2_pemfc import Equivalent65kWHorizonDynamicModel
from h2_pemfc.ems_input import prepare_ems_profile
from models.battery_model import (
    BATTERY_2RC,
    BATTERY_TREMBLAY,
    RC_V_NOM_V,
    TREMBLAY_BATTERIES,
    simulate_2rc,
    simulate_tremblay,
)
from models.thermal_model import ThermalConfig, evaluate_thermal_dispatch
from models.wind_model import WindInputMapping, prepare_wind_profile, run_wind_model
from simulation.multimodel import simulate_noct_efficiency_model


SOURCE_ORDER = ("solar", "wind", "thermal", "battery", "h2")
SOURCE_LABELS = {
    "solar": "Solar",
    "wind": "Eólica",
    "thermal": "Térmica",
    "battery": "Bateria",
    "h2": "H2 / PEMFC",
}

CLIMATE_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": ("timestamp", "datetime", "data_hora", "datahora", "fecha_hora", "tempo", "time"),
    "ghi": ("ghi", "irradiance", "irradiancia", "irradiancia_w_m2", "radiacao", "radiacao_global", "g"),
    "temperature": ("temperature", "temperature_c", "temperatura", "temperatura_c", "temp", "tamb", "t_amb"),
    "wind_speed": ("wind_speed", "wind_speed_mps", "windspeed", "velocidade_vento", "velocidad_viento", "ws"),
    "wind_direction": ("wind_direction", "wind_direction_deg", "winddirection", "direcao_vento", "direccion_viento", "wd"),
    "pressure": ("pressure", "pressure_hpa", "pressao", "presion", "pressao_hpa", "presion_hpa"),
    "humidity": ("humidity", "humidity_pct", "relative_humidity", "rh", "umidade", "humedad"),
}

OPERATION_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": ("timestamp", "datetime", "data_hora", "datahora", "fecha_hora", "tempo", "time"),
    "demand_total_kw": (
        "p_demanda_total_kw", "demanda_total_kw", "load_kw", "p_load_kw", "demand_kw", "potencia_demanda_kw",
    ),
    "thermal_kw": (
        "p_termica_requested_kw", "p_thermal_requested_kw", "demanda_termica_kw", "thermal_kw", "termica_kw",
    ),
    "battery_kw": (
        "p_bateria_requested_kw", "p_battery_requested_kw", "demanda_bateria_kw", "battery_kw", "bateria_kw",
    ),
    "h2_kw": (
        "p_h2_requested_kw", "p_fc_requested_kw", "demanda_h2_kw", "h2_kw", "pemfc_kw", "fuel_cell_kw",
    ),
}

DEFAULT_EXPORT_COLUMNS = [
    "timestamp",
    "P_demand_kW",
    "P_solar_kW",
    "P_wind_kW",
    "P_thermal_requested_kW",
    "P_thermal_delivered_kW",
    "P_battery_requested_kW",
    "P_battery_delivered_kW",
    "SOC_battery_pct",
    "P_H2_requested_kW",
    "P_H2_delivered_kW",
    "H2_consumption_kg_h",
    "P_total_generated_kW",
    "P_balance_kW",
    "P_excess_kW",
    "P_deficit_kW",
    "curtailment_required",
    "battery_charge_opportunity",
    "mix_recommendation",
]


@dataclass
class MixRunResult:
    dataframe: pd.DataFrame
    source_results: dict[str, pd.DataFrame] = field(default_factory=dict)
    source_kpis: dict[str, dict[str, Any]] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    climate_aligned: pd.DataFrame | None = None
    operation_normalized: pd.DataFrame | None = None


def _normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    chars = []
    for ch in text.strip().lower():
        chars.append(ch if ch.isalnum() else "_")
    return "_".join(filter(None, "".join(chars).split("_")))


def detect_columns(columns, aliases: Mapping[str, tuple[str, ...]]) -> dict[str, str | None]:
    normalized = {_normalize_name(col): str(col) for col in columns}
    out: dict[str, str | None] = {}
    for semantic, candidates in aliases.items():
        out[semantic] = next((normalized[_normalize_name(a)] for a in candidates if _normalize_name(a) in normalized), None)
    return out


def detect_climate_columns(columns) -> dict[str, str | None]:
    return detect_columns(columns, CLIMATE_ALIASES)


def detect_operation_columns(columns) -> dict[str, str | None]:
    return detect_columns(columns, OPERATION_ALIASES)


def detect_disabled_source_inputs(
    operation_raw: pd.DataFrame | None,
    climate_raw: pd.DataFrame | None,
    enabled_sources: Mapping[str, bool],
) -> list[str]:
    """Informa quando os CSVs contêm dados de uma fonte desativada.

    A configuração do MIX sempre prevalece sobre o conteúdo dos arquivos: uma
    fonte desligada não é simulada, mesmo que o CSV traga sua coluna/variável.
    """
    found: dict[str, tuple[str, list[str]]] = {}

    if operation_raw is not None:
        detected = detect_operation_columns(operation_raw.columns)
        for src, semantic in (("thermal", "thermal_kw"), ("battery", "battery_kw"), ("h2", "h2_kw")):
            if enabled_sources.get(src):
                continue
            col = detected.get(semantic)
            if col:
                found[src] = ("CSV operacional", [col])

    if climate_raw is not None:
        detected = detect_climate_columns(climate_raw.columns)
        if not enabled_sources.get("solar") and detected.get("ghi"):
            cols = [detected.get("ghi"), detected.get("temperature")]
            found["solar"] = ("CSV climático", [c for c in cols if c])
        if not enabled_sources.get("wind") and detected.get("wind_speed"):
            cols = [
                detected.get("wind_speed"), detected.get("wind_direction"),
                detected.get("pressure"), detected.get("humidity"),
            ]
            found["wind"] = ("CSV climático", [c for c in cols if c])

    messages: list[str] = []
    for src in SOURCE_ORDER:
        if src not in found:
            continue
        origin, cols = found[src]
        unique_cols = list(dict.fromkeys(cols))
        col_text = ", ".join(f"'{c}'" for c in unique_cols)
        messages.append(
            f"Foi detectada informação de {SOURCE_LABELS[src]} no {origin} ({col_text}), "
            "mas o modelo está desativado e não possui configuração nesta execução. "
            "Revise a página Configuração de fontes se desejar utilizá-lo. "
            "O MIX seguirá sem considerar essa fonte."
        )
    return messages


def _decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_csv_auto(source) -> pd.DataFrame:
    if isinstance(source, (str, Path)):
        raw = Path(source).read_bytes()
    elif isinstance(source, bytes):
        raw = source
    elif hasattr(source, "getvalue"):
        raw = source.getvalue()
    elif hasattr(source, "read"):
        raw = source.read()
    else:
        raise TypeError("Fonte CSV não suportada.")

    text = _decode_bytes(raw)
    try:
        return pd.read_csv(StringIO(text), sep=None, engine="python")
    except Exception:
        for sep in (";", ",", "\t"):
            try:
                df = pd.read_csv(StringIO(text), sep=sep)
                if len(df.columns) > 1:
                    return df
            except Exception:
                pass
    raise ValueError("Não foi possível interpretar o arquivo CSV.")


def _numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return pd.to_numeric(
        series.astype(str).str.strip().str.replace(" ", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )


def _timestamp_series(series: pd.Series, label: str) -> pd.Series:
    out = pd.to_datetime(series.astype(str).str.strip(), errors="coerce")
    if out.isna().any():
        raise ValueError(f"{label}: existem {int(out.isna().sum())} timestamp(s) inválido(s).")
    return out


def prepare_operation(raw: pd.DataFrame, mapping: Mapping[str, str | None], enabled_sources: Mapping[str, bool]) -> pd.DataFrame:
    ts_col = mapping.get("timestamp")
    if not ts_col or ts_col not in raw.columns:
        raise ValueError("O CSV operacional precisa de uma coluna de timestamp.")

    out = pd.DataFrame({"timestamp": _timestamp_series(raw[ts_col], "Operação")})
    semantic_to_target = {
        "demand_total_kw": "P_demand_kW",
        "thermal_kw": "P_thermal_requested_kW",
        "battery_kw": "P_battery_requested_kW",
        "h2_kw": "P_H2_requested_kW",
    }
    semantic_source = {
        "thermal_kw": "thermal",
        "battery_kw": "battery",
        "h2_kw": "h2",
    }
    required = {semantic: bool(enabled_sources.get(src)) for semantic, src in semantic_source.items()}
    for semantic, target in semantic_to_target.items():
        source = semantic_source.get(semantic)
        if source is not None and not enabled_sources.get(source):
            # A configuração é soberana: dados de fonte desligada são ignorados
            # completamente, inclusive se a coluna existir ou contiver valores inválidos.
            out[target] = 0.0
            continue

        col = mapping.get(semantic)
        if col and col in raw.columns:
            values = _numeric(raw[col])
            if values.isna().any():
                raise ValueError(f"Operação: a coluna {col!r} contém valores não numéricos/vazios.")
            out[target] = values.to_numpy(dtype=float)
        elif required.get(semantic, False):
            label = SOURCE_LABELS[semantic_source[semantic]]
            raise ValueError(f"Fonte {label} ativa, mas sua potência solicitada não foi mapeada no CSV operacional.")
        else:
            out[target] = np.nan if semantic == "demand_total_kw" else 0.0

    if (out["P_thermal_requested_kW"].fillna(0) < 0).any():
        raise ValueError("A potência térmica solicitada não pode ser negativa.")
    if (out["P_H2_requested_kW"].fillna(0) < 0).any():
        raise ValueError("A potência H2/PEMFC solicitada não pode ser negativa.")
    if out["P_demand_kW"].notna().any() and (out["P_demand_kW"].dropna() < 0).any():
        raise ValueError("A demanda total não pode ser negativa.")

    if out["timestamp"].duplicated().any():
        out = out.drop_duplicates("timestamp", keep="last")
    out = out.sort_values("timestamp").reset_index(drop=True)
    if len(out) < 2:
        raise ValueError("O CSV operacional deve ter pelo menos dois timestamps.")
    if not out["timestamp"].is_monotonic_increasing:
        raise ValueError("Os timestamps operacionais precisam ser crescentes.")
    return out


def prepare_climate(raw: pd.DataFrame, mapping: Mapping[str, str | None], enabled_sources: Mapping[str, bool]) -> pd.DataFrame:
    ts_col = mapping.get("timestamp")
    if not ts_col or ts_col not in raw.columns:
        raise ValueError("O CSV climático precisa de uma coluna de timestamp.")
    out = pd.DataFrame({"timestamp": _timestamp_series(raw[ts_col], "Clima")})

    fields = {
        "ghi": "GHI_W_m2",
        "temperature": "temperature_C",
        "wind_speed": "wind_speed_mps",
        "wind_direction": "wind_direction_deg",
        "pressure": "pressure_hPa",
        "humidity": "humidity_pct",
    }
    field_enabled = {
        "ghi": bool(enabled_sources.get("solar")),
        "temperature": bool(enabled_sources.get("solar") or enabled_sources.get("wind")),
        "wind_speed": bool(enabled_sources.get("wind")),
        "wind_direction": bool(enabled_sources.get("wind")),
        "pressure": bool(enabled_sources.get("wind")),
        "humidity": bool(enabled_sources.get("wind")),
    }
    for semantic, target in fields.items():
        col = mapping.get(semantic)
        if field_enabled[semantic] and col and col in raw.columns:
            out[target] = _numeric(raw[col]).to_numpy(dtype=float)
        else:
            out[target] = np.nan

    if enabled_sources.get("solar"):
        if out["GHI_W_m2"].isna().any():
            raise ValueError("Solar ativo: GHI é obrigatório em todo o CSV climático.")
        if out["temperature_C"].isna().any():
            raise ValueError("Solar ativo: temperatura ambiente é obrigatória para o modelo NOCT + eficiência.")
        if (out["GHI_W_m2"] < 0).any():
            raise ValueError("GHI não pode ser negativo.")
    if enabled_sources.get("wind"):
        if out["wind_speed_mps"].isna().any():
            raise ValueError("Eólica ativa: velocidade do vento é obrigatória em todo o CSV climático.")
        if (out["wind_speed_mps"] < 0).any():
            raise ValueError("Velocidade do vento não pode ser negativa.")

    out = out.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    if len(out) < 2 and (enabled_sources.get("solar") or enabled_sources.get("wind")):
        raise ValueError("O CSV climático deve ter pelo menos dois timestamps.")
    return out


def _interp_linear(source_ts: np.ndarray, target_ts: np.ndarray, values: np.ndarray) -> np.ndarray:
    valid = np.isfinite(values)
    if not valid.any():
        return np.full(len(target_ts), np.nan, dtype=float)
    if valid.sum() == 1:
        return np.full(len(target_ts), float(values[valid][0]), dtype=float)
    return np.interp(target_ts, source_ts[valid], values[valid])


def align_climate_to_operation(climate: pd.DataFrame, operation_ts: pd.Series) -> pd.DataFrame:
    target = pd.to_datetime(operation_ts).reset_index(drop=True)
    if climate.empty:
        return pd.DataFrame({"timestamp": target})
    cts = pd.to_datetime(climate["timestamp"])
    if target.min() < cts.min() or target.max() > cts.max():
        raise ValueError(
            "O arquivo climático não cobre toda a janela do CSV operacional. "
            "Amplie o período climático para evitar extrapolação fora dos dados fornecidos."
        )

    origin = min(target.min(), cts.min())
    src_x = (cts - origin).dt.total_seconds().to_numpy(dtype=float)
    dst_x = (target - origin).dt.total_seconds().to_numpy(dtype=float)
    out = pd.DataFrame({"timestamp": target})

    for col in ("GHI_W_m2", "temperature_C", "wind_speed_mps", "pressure_hPa", "humidity_pct"):
        values = climate[col].to_numpy(dtype=float) if col in climate else np.full(len(climate), np.nan)
        out[col] = _interp_linear(src_x, dst_x, values)

    # Direção é angular: interpola o ângulo desenrolado para evitar 359° -> 1° passando por 180°.
    if "wind_direction_deg" in climate and np.isfinite(climate["wind_direction_deg"]).any():
        vals = climate["wind_direction_deg"].to_numpy(dtype=float)
        valid = np.isfinite(vals)
        radians = np.unwrap(np.deg2rad(vals[valid]))
        if valid.sum() == 1:
            interp = np.full(len(dst_x), radians[0])
        else:
            interp = np.interp(dst_x, src_x[valid], radians)
        out["wind_direction_deg"] = np.rad2deg(interp) % 360.0
    else:
        out["wind_direction_deg"] = np.nan
    return out


def _step_hours(ts: pd.Series) -> np.ndarray:
    ts = pd.to_datetime(ts).reset_index(drop=True)
    diffs = ts.shift(-1) - ts
    hours = diffs.dt.total_seconds().to_numpy(dtype=float) / 3600.0
    positive = hours[np.isfinite(hours) & (hours > 0)]
    typical = float(np.median(positive)) if len(positive) else 0.0
    if len(hours):
        hours[-1] = typical
    hours[(~np.isfinite(hours)) | (hours <= 0)] = typical
    return hours


def _integrate_step(values: np.ndarray, hours: np.ndarray) -> float:
    return float(np.nansum(np.asarray(values, dtype=float) * np.asarray(hours, dtype=float)))


def _battery_nominal_voltage(model_id: str, battery_key: str | None, n_series: int) -> float:
    if model_id == BATTERY_TREMBLAY:
        key = battery_key or "liion_3p3v_2p3ah"
        return float(TREMBLAY_BATTERIES[key].V_nom_V) * int(n_series)
    return float(RC_V_NOM_V) * int(n_series)


def simulate_battery_power_request(
    timestamps: pd.Series,
    requested_kw: pd.Series,
    *,
    model_id: str,
    battery_key: str | None,
    n_series: int,
    n_parallel: int,
    initial_soc: float,
    integration_step_s: float,
    iterations: int = 4,
) -> pd.DataFrame:
    """Adapta uma consigna de potência ao contrato de corrente dos modelos existentes.

    O adaptador não altera as equações eletroquímicas. Itera somente a corrente de
    entrada I ~= P/V usando a tensão terminal devolvida pelo próprio modelo.
    """
    req_w = pd.to_numeric(requested_kw, errors="raise").to_numpy(dtype=float) * 1000.0
    nominal_v = max(_battery_nominal_voltage(model_id, battery_key, n_series), 0.1)
    current = np.divide(req_w, nominal_v, out=np.zeros_like(req_w), where=np.abs(req_w) > 1e-12)
    result: pd.DataFrame | None = None

    for _ in range(max(1, int(iterations))):
        profile = pd.DataFrame({"timestamp": pd.to_datetime(timestamps), "current_A": current})
        if model_id == BATTERY_TREMBLAY:
            result = simulate_tremblay(
                profile,
                battery_key=battery_key or "liion_3p3v_2p3ah",
                n_series=int(n_series),
                n_parallel=int(n_parallel),
                initial_soc=float(initial_soc),
                integration_step_s=float(integration_step_s),
            )
        elif model_id == BATTERY_2RC:
            result = simulate_2rc(
                profile,
                n_series=int(n_series),
                n_parallel=int(n_parallel),
                initial_soc=float(initial_soc),
                integration_step_s=float(integration_step_s),
            )
        else:
            raise ValueError(f"Modelo de bateria desconhecido: {model_id}")

        voltage = np.maximum(np.abs(result["voltage_V"].to_numpy(dtype=float)), 0.1)
        current = np.divide(req_w, voltage, out=np.zeros_like(req_w), where=np.abs(req_w) > 1e-12)

    assert result is not None
    result = result.copy()
    result["P_battery_requested_kW"] = req_w / 1000.0
    result["P_battery_delivered_kW"] = result["power_W"].to_numpy(dtype=float) / 1000.0
    result["P_battery_error_kW"] = result["P_battery_requested_kW"] - result["P_battery_delivered_kW"]
    return result


def _default_series(df: pd.DataFrame, name: str, value: float = 0.0) -> pd.Series:
    if name in df:
        return pd.to_numeric(df[name], errors="coerce").fillna(value)
    return pd.Series(np.full(len(df), value, dtype=float), index=df.index)


def run_mix(
    operation_raw: pd.DataFrame,
    climate_raw: pd.DataFrame | None,
    *,
    operation_mapping: Mapping[str, str | None],
    climate_mapping: Mapping[str, str | None] | None,
    enabled_sources: Mapping[str, bool],
    config: Mapping[str, Mapping[str, Any]],
) -> MixRunResult:
    if not any(bool(enabled_sources.get(src)) for src in SOURCE_ORDER):
        raise ValueError("Ative pelo menos uma fonte no MIX.")

    messages: list[str] = detect_disabled_source_inputs(operation_raw, climate_raw, enabled_sources)
    operation = prepare_operation(operation_raw, operation_mapping, enabled_sources)
    climate_needed = bool(enabled_sources.get("solar") or enabled_sources.get("wind"))
    if climate_needed:
        if climate_raw is None or climate_mapping is None:
            raise ValueError("Solar/eólica ativa: carregue o CSV climático.")
        climate = prepare_climate(climate_raw, climate_mapping, enabled_sources)
        climate_aligned = align_climate_to_operation(climate, operation["timestamp"])
    else:
        climate_aligned = pd.DataFrame({"timestamp": operation["timestamp"]})

    base = pd.DataFrame({"timestamp": operation["timestamp"]})
    base["P_demand_kW"] = operation["P_demand_kW"].to_numpy(dtype=float)
    source_results: dict[str, pd.DataFrame] = {}
    source_kpis: dict[str, dict[str, Any]] = {}
    step_h = _step_hours(base["timestamp"])

    # Solar: modelo 2 (NOCT + eficiência) fixo no MIX, conforme decisão de projeto.
    if enabled_sources.get("solar"):
        cfg = config.get("solar", {})
        module = get_module(str(cfg["module_key"]))
        profile = pd.DataFrame(
            {
                "G": climate_aligned["GHI_W_m2"].to_numpy(dtype=float),
                "Tamb": climate_aligned["temperature_C"].to_numpy(dtype=float),
            },
            index=pd.DatetimeIndex(base["timestamp"], name="timestamp"),
        )
        result = simulate_noct_efficiency_model(
            module,
            profile,
            n_series=int(cfg.get("n_series", 2)),
            n_parallel=int(cfg.get("n_parallel", 3)),
            soiling_losses=float(cfg.get("soiling_losses_pct", 0.0)) / 100.0,
            noct=float(cfg["noct"]) if cfg.get("noct") is not None else None,
        )
        source_results["solar"] = result
        p_kw = result["P_array"].to_numpy(dtype=float) / 1000.0
        base["P_solar_kW"] = p_kw
        source_kpis["solar"] = {
            "energy_kWh": _integrate_step(p_kw, step_h),
            "peak_kW": float(np.nanmax(p_kw)) if len(p_kw) else 0.0,
            "installed_kWp": float(result.attrs.get("p_nom_array_W", 0.0)) / 1000.0,
            "model": "NOCT + eficiência corrigida por temperatura",
        }
    else:
        base["P_solar_kW"] = 0.0

    # Eólica: curva elétrica do fabricante + correção de densidade já existente.
    if enabled_sources.get("wind"):
        cfg = config.get("wind", {})
        wind_raw = pd.DataFrame(
            {
                "timestamp": base["timestamp"],
                "wind_speed": climate_aligned["wind_speed_mps"],
                "wind_direction": climate_aligned["wind_direction_deg"],
                "temperature": climate_aligned["temperature_C"],
                "pressure": climate_aligned["pressure_hPa"],
                "humidity": climate_aligned["humidity_pct"],
            }
        )
        wind_profile = prepare_wind_profile(
            wind_raw,
            WindInputMapping("timestamp", "wind_speed", "wind_direction", "temperature", "pressure", "humidity"),
        )
        result, kpis, density = run_wind_model(
            wind_profile,
            str(cfg["turbine_key"]),
            int(cfg.get("turbine_count", 1)),
            bool(cfg.get("apply_grid_loss", False)),
        )
        source_results["wind"] = result
        base["P_wind_kW"] = result["power_net_kw"].to_numpy(dtype=float)
        source_kpis["wind"] = dict(kpis)
        source_kpis["wind"]["mean_air_density_kg_m3"] = density.mean_kg_m3
    else:
        base["P_wind_kW"] = 0.0

    # Térmica: entrada do otimizador em kW, modelo existente trabalha em MW.
    if enabled_sources.get("thermal"):
        cfg = config.get("thermal", {})
        th_profile = pd.DataFrame(
            {
                "timestamp": base["timestamp"],
                "power_requested_mw": operation["P_thermal_requested_kW"].to_numpy(dtype=float) / 1000.0,
                "inflexibility_input_mw": np.nan,
                "interval_hours": step_h,
            }
        )
        th_profile.attrs["timestep_hours"] = float(np.median(step_h[step_h > 0])) if np.any(step_h > 0) else 0.0
        th_profile.attrs["timestep_minutes"] = th_profile.attrs["timestep_hours"] * 60.0
        th_cfg = ThermalConfig(
            dynamic=str(cfg.get("dynamic", THERMAL_PLANT)),
            pmax_mw=float(cfg.get("pmax_mw", 1.0)),
            cvu_rs_mwh=float(cfg.get("cvu_rs_mwh", 0.0)),
            constant_inflexibility_mw=float(cfg.get("constant_inflexibility_mw", 0.0)),
            use_profile_inflexibility=False,
            pmin_technical_mw=float(cfg.get("pmin_technical_mw", 0.0)),
            ramp_up_mw_min=float(cfg["ramp_up_mw_min"]) if cfg.get("ramp_up_mw_min") is not None else None,
            ramp_down_mw_min=float(cfg["ramp_down_mw_min"]) if cfg.get("ramp_down_mw_min") is not None else None,
            startup_cost_rs=float(cfg.get("startup_cost_rs", 0.0)),
        )
        result, kpis = evaluate_thermal_dispatch(th_profile, th_cfg)
        source_results["thermal"] = result
        source_kpis["thermal"] = kpis
        base["P_thermal_requested_kW"] = operation["P_thermal_requested_kW"].to_numpy(dtype=float)
        base["P_thermal_delivered_kW"] = result["power_delivered_mw"].to_numpy(dtype=float) * 1000.0
        base["P_thermal_unmet_kW"] = result["power_unmet_mw"].to_numpy(dtype=float) * 1000.0
        base["thermal_total_cost_R$"] = result["cumulative_cost_rs"].to_numpy(dtype=float)
    else:
        base["P_thermal_requested_kW"] = 0.0
        base["P_thermal_delivered_kW"] = 0.0
        base["P_thermal_unmet_kW"] = 0.0
        base["thermal_total_cost_R$"] = 0.0

    # Bateria: adaptador potência -> corrente, preservando os modelos existentes.
    if enabled_sources.get("battery"):
        cfg = config.get("battery", {})
        result = simulate_battery_power_request(
            base["timestamp"],
            operation["P_battery_requested_kW"],
            model_id=str(cfg.get("model_id", BATTERY_2RC)),
            battery_key=cfg.get("battery_key"),
            n_series=int(cfg.get("n_series", 12)),
            n_parallel=int(cfg.get("n_parallel", 4)),
            initial_soc=float(cfg.get("initial_soc", 0.9)),
            integration_step_s=float(cfg.get("integration_step_s", 1.0)),
            iterations=int(cfg.get("power_iterations", 4)),
        )
        source_results["battery"] = result
        base["P_battery_requested_kW"] = result["P_battery_requested_kW"].to_numpy(dtype=float)
        base["P_battery_delivered_kW"] = result["P_battery_delivered_kW"].to_numpy(dtype=float)
        base["P_battery_error_kW"] = result["P_battery_error_kW"].to_numpy(dtype=float)
        base["SOC_battery_pct"] = result["soc_percent"].to_numpy(dtype=float)
        base["battery_voltage_V"] = result["voltage_V"].to_numpy(dtype=float)
        base["battery_current_A"] = result["current_A"].to_numpy(dtype=float)
        base["battery_limit_flag"] = result["limit_flag"].astype(bool).to_numpy()
        source_kpis["battery"] = {
            "soc_initial_pct": float(result["soc_percent"].iloc[0]),
            "soc_final_pct": float(result["soc_percent"].iloc[-1]),
            "soc_min_pct": float(result["soc_percent"].min()),
            "soc_max_pct": float(result["soc_percent"].max()),
            "max_abs_tracking_error_kW": float(np.abs(result["P_battery_error_kW"]).max()),
            "limit_points": int(result["limit_flag"].sum()),
        }
    else:
        base["P_battery_requested_kW"] = 0.0
        base["P_battery_delivered_kW"] = 0.0
        base["P_battery_error_kW"] = 0.0
        base["SOC_battery_pct"] = np.nan
        base["battery_voltage_V"] = np.nan
        base["battery_current_A"] = 0.0
        base["battery_limit_flag"] = False

    # H2 / PEMFC: contrato nativo já recebe potência solicitada em kW.
    if enabled_sources.get("h2"):
        cfg = config.get("h2", {})
        raw_h2 = pd.DataFrame(
            {
                "timestamp": base["timestamp"],
                "P_FC_requested_kW": operation["P_H2_requested_kW"].to_numpy(dtype=float),
            }
        )
        model = Equivalent65kWHorizonDynamicModel()
        prepared = prepare_ems_profile(raw_h2, dynamic_model=model)
        result = model.simulate_profile(prepared.profile, internal_time_step_s=float(cfg.get("integration_step_s", 1.0)))
        source_results["h2"] = result
        # O modelo dinâmico cria pontos internos entre consignas. Para o dataframe
        # consolidado voltamos exatamente aos timestamps mestres do otimizador; o
        # resultado detalhado continua disponível em source_results["h2"].
        result_master = (
            result.assign(timestamp=pd.to_datetime(result["timestamp"]))
            .drop_duplicates("timestamp", keep="last")
            .set_index("timestamp")
            .reindex(pd.DatetimeIndex(base["timestamp"]))
        )
        if result_master["P_FC_delivered_kW"].isna().any():
            raise RuntimeError("A simulação H2 não devolveu todos os timestamps mestres do otimizador.")
        base["P_H2_requested_kW"] = result_master["P_FC_requested_kW"].to_numpy(dtype=float)
        base["P_H2_delivered_kW"] = result_master["P_FC_delivered_kW"].to_numpy(dtype=float)
        base["P_H2_deficit_kW"] = result_master["P_deficit_kW"].to_numpy(dtype=float)
        base["H2_consumption_kg_h"] = result_master["hydrogen_supplied_kg_h"].to_numpy(dtype=float)
        base["H2_efficiency_pct"] = result_master["net_electrical_efficiency_LHV_percent"].to_numpy(dtype=float)
        base["H2_limitation_flag"] = result_master["limitation_flag"].astype(bool).to_numpy()
        source_kpis["h2"] = {
            "energy_requested_kWh": _integrate_step(base["P_H2_requested_kW"].to_numpy(), step_h),
            "energy_delivered_kWh": _integrate_step(base["P_H2_delivered_kW"].to_numpy(), step_h),
            "hydrogen_kg": _integrate_step(base["H2_consumption_kg_h"].to_numpy(), step_h),
            "max_deficit_kW": float(base["P_H2_deficit_kW"].max()),
            "limitation_points": int(base["H2_limitation_flag"].sum()),
        }
    else:
        base["P_H2_requested_kW"] = 0.0
        base["P_H2_delivered_kW"] = 0.0
        base["P_H2_deficit_kW"] = 0.0
        base["H2_consumption_kg_h"] = 0.0
        base["H2_efficiency_pct"] = np.nan
        base["H2_limitation_flag"] = False

    base["P_renewable_kW"] = base["P_solar_kW"] + base["P_wind_kW"]
    base["P_dispatchable_kW"] = (
        base["P_thermal_delivered_kW"] + base["P_battery_delivered_kW"] + base["P_H2_delivered_kW"]
    )
    base["P_total_generated_kW"] = base["P_renewable_kW"] + base["P_dispatchable_kW"]

    has_demand = bool(base["P_demand_kW"].notna().all())
    if has_demand:
        base["P_balance_kW"] = base["P_total_generated_kW"] - base["P_demand_kW"]
        base["P_excess_kW"] = base["P_balance_kW"].clip(lower=0.0)
        base["P_deficit_kW"] = (-base["P_balance_kW"]).clip(lower=0.0)
        base["curtailment_required"] = base["P_excess_kW"] > 1e-6
    else:
        base["P_balance_kW"] = np.nan
        base["P_excess_kW"] = np.nan
        base["P_deficit_kW"] = np.nan
        base["curtailment_required"] = False
        messages.append(
            "Demanda total não informada: os modelos foram executados, mas balanço, déficit, excedente e curtailment não podem ser determinados."
        )

    if enabled_sources.get("battery") and has_demand:
        base["battery_charge_opportunity"] = base["curtailment_required"] & (base["SOC_battery_pct"] < 99.999)
    else:
        base["battery_charge_opportunity"] = False

    recommendations = np.full(len(base), "Operação sem ação adicional do MIX", dtype=object)
    if has_demand:
        recommendations[base["curtailment_required"].to_numpy()] = "Excedente: sinalizar curtailment"
        mask_charge = base["battery_charge_opportunity"].to_numpy(dtype=bool)
        recommendations[mask_charge] = "Excedente: curtailment ou solicitar carga da bateria ao otimizador"
        deficit_mask = base["P_deficit_kW"].to_numpy(dtype=float) > 1e-6
        recommendations[deficit_mask] = "Déficit: revisar proposta de despacho do otimizador"
    base["mix_recommendation"] = recommendations

    if has_demand and base["curtailment_required"].any():
        n = int(base["curtailment_required"].sum())
        peak = float(base["P_excess_kW"].max())
        messages.append(f"Excedente identificado em {n} intervalo(s), pico de {peak:.3f} kW. O MIX apenas sinaliza; não corta renováveis.")
    if base["battery_charge_opportunity"].any():
        messages.append(
            "Há excedente com SOC abaixo de 100 %. O MIX informa a oportunidade de carga, mas somente o otimizador pode emitir uma nova consigna para a bateria."
        )

    base.attrs["step_hours"] = step_h
    base.attrs["enabled_sources"] = dict(enabled_sources)
    base.attrs["has_total_demand"] = has_demand
    return MixRunResult(
        dataframe=base,
        source_results=source_results,
        source_kpis=source_kpis,
        messages=messages,
        climate_aligned=climate_aligned,
        operation_normalized=operation,
    )


def _column_source(column: str) -> str | None:
    low = str(column).lower()
    if "solar" in low:
        return "solar"
    if "wind" in low:
        return "wind"
    if "thermal" in low:
        return "thermal"
    if "battery" in low:
        return "battery"
    if low.startswith("p_h2") or low.startswith("h2_"):
        return "h2"
    return None


def available_export_columns(result: pd.DataFrame) -> list[str]:
    enabled = result.attrs.get("enabled_sources")
    if not isinstance(enabled, Mapping):
        return list(result.columns)
    return [
        col for col in result.columns
        if (src := _column_source(col)) is None or bool(enabled.get(src))
    ]


def default_export_columns(result: pd.DataFrame) -> list[str]:
    available = set(available_export_columns(result))
    return [col for col in DEFAULT_EXPORT_COLUMNS if col in available]


def build_export_dataframe(result: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    selected = [c for c in columns if c in result.columns]
    if not selected:
        raise ValueError("Selecione pelo menos uma coluna para exportar.")
    return result[selected].copy()


def build_example_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gera dois exemplos coerentes: operação a 1 min e clima a 10 min."""
    op_ts = pd.date_range("2026-09-21 10:00:00", periods=121, freq="1min")
    x = np.linspace(0, 1, len(op_ts))
    demand = 145.0 + 18.0 * np.sin(2 * np.pi * x) + 10.0 * (x > 0.68)
    thermal = np.where(x < 0.25, 45.0, np.where(x < 0.72, 28.0, 48.0))
    battery = np.where((x > 0.18) & (x < 0.40), 12.0, np.where((x > 0.52) & (x < 0.63), -10.0, 0.0))
    h2 = np.where(x < 0.45, 22.0, 34.0)
    operation = pd.DataFrame(
        {
            "timestamp": op_ts,
            "P_demanda_total_kW": demand,
            "P_termica_requested_kW": thermal,
            "P_bateria_requested_kW": battery,
            "P_H2_requested_kW": h2,
        }
    )

    cl_ts = pd.date_range(op_ts.min(), op_ts.max(), freq="10min")
    h = np.linspace(-1, 1, len(cl_ts))
    ghi = np.maximum(0.0, 820.0 * (1.0 - 0.42 * h**2))
    temp = 27.0 + 4.0 * np.sin(np.linspace(-0.6, 0.9, len(cl_ts)))
    wind = 7.0 + 1.8 * np.sin(np.linspace(0, 2.2 * np.pi, len(cl_ts)))
    climate = pd.DataFrame(
        {
            "timestamp": cl_ts,
            "GHI": ghi,
            "temperatura_C": temp,
            "wind_speed": wind,
            "wind_direction": (95.0 + np.linspace(0, 45, len(cl_ts))) % 360,
            "pressure_hPa": 1008.0 + 2.0 * np.cos(np.linspace(0, np.pi, len(cl_ts))),
            "humidity_pct": 62.0 - 8.0 * np.sin(np.linspace(0, np.pi, len(cl_ts))),
        }
    )
    return operation, climate
