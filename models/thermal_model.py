"""Modelo operacional-econômico térmico V1.2.

Duas dinâmicas compartilham o mesmo contrato de entrada:

1) Usina termelétrica de grande porte: avalia despacho solicitado contra inflexibilidade,
   potência máxima, mínimo técnico e rampas opcionais. O custo é calculado
   sobre a potência efetivamente considerada para cumprimento contratual,
   limitada pela capacidade disponível.

2) Pequena unidade geradora: representa um recurso rápido de backup. Não possui
   inflexibilidade por padrão; entrega até Pmax, contabiliza energia não atendida,
   custo variável e custo fixo de cada partida.

A V1.2 não modela caldeira, ciclo termodinâmico, heat-rate, minimum up/down time
ou dinâmica eletromecânica detalhada.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from config.thermal_database import LOCAL_GENERATOR, THERMAL_PLANT

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": (
        "timestamp", "datetime", "date_time", "data_hora", "datahora", "fecha_hora",
        "fecha", "data", "tempo", "time",
    ),
    "power_requested": (
        "power_requested_mw", "requested_power_mw", "dispatch_mw", "despacho_mw",
        "potencia_solicitada_mw", "potência_solicitada_mw", "potencia_mw",
        "demanda_termica_mw", "demanda_mw", "power_mw",
    ),
    "inflexibility": (
        "inflexibility_mw", "inflexibilidade_mw", "inflex_mw", "must_run_mw",
        "minimum_contract_mw", "potencia_inflexivel_mw", "potência_inflexível_mw",
    ),
}


@dataclass(frozen=True)
class ThermalInputMapping:
    timestamp: str
    power_requested: str
    inflexibility: str | None = None


@dataclass(frozen=True)
class ThermalConfig:
    dynamic: str
    pmax_mw: float
    cvu_rs_mwh: float
    constant_inflexibility_mw: float = 0.0
    use_profile_inflexibility: bool = True
    pmin_technical_mw: float = 0.0
    ramp_up_mw_min: float | None = None
    ramp_down_mw_min: float | None = None
    startup_cost_rs: float = 0.0

    def validate(self) -> None:
        if self.dynamic not in {THERMAL_PLANT, LOCAL_GENERATOR}:
            raise ValueError("Dinâmica térmica inválida")
        if self.pmax_mw <= 0:
            raise ValueError("Potência máxima deve ser maior que zero")
        if self.cvu_rs_mwh < 0:
            raise ValueError("CVU não pode ser negativo")
        if self.constant_inflexibility_mw < 0:
            raise ValueError("Inflexibilidade não pode ser negativa")
        if self.pmin_technical_mw < 0:
            raise ValueError("Potência mínima técnica não pode ser negativa")
        if self.pmin_technical_mw > self.pmax_mw:
            raise ValueError("Potência mínima técnica não pode superar Pmax")
        if self.dynamic == THERMAL_PLANT and self.constant_inflexibility_mw > self.pmax_mw:
            # A curva do arquivo pode superar Pmax e será reportada como violação,
            # mas um valor constante configurado acima de Pmax é erro de configuração.
            raise ValueError("Inflexibilidade constante não pode superar Pmax")
        for name, value in (("rampa de subida", self.ramp_up_mw_min), ("rampa de descida", self.ramp_down_mw_min)):
            if value is not None and value <= 0:
                raise ValueError(f"{name.capitalize()} deve ser positiva")
        if self.startup_cost_rs < 0:
            raise ValueError("Custo de partida não pode ser negativo")


def _normalize_name(value: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return "_".join(text.strip().lower().replace("/", "_").replace("-", "_").split())


def detect_thermal_columns(columns: Iterable[str]) -> dict[str, str | None]:
    normalized = {_normalize_name(col): col for col in columns}
    out: dict[str, str | None] = {}
    for semantic, aliases in COLUMN_ALIASES.items():
        found = None
        for alias in aliases:
            if _normalize_name(alias) in normalized:
                found = normalized[_normalize_name(alias)]
                break
        out[semantic] = found
    return out


def _decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def read_thermal_csv(source) -> pd.DataFrame:
    if isinstance(source, (str, Path)):
        raw = Path(source).read_bytes()
    elif isinstance(source, bytes):
        raw = source
    elif hasattr(source, "getvalue"):
        raw = source.getvalue()
    elif hasattr(source, "read"):
        raw = source.read()
    else:
        raise TypeError("Fonte CSV não suportada")

    text = _decode_bytes(raw)
    try:
        return pd.read_csv(StringIO(text), sep=None, engine="python")
    except Exception:
        for sep in (";", ",", "\t"):
            try:
                frame = pd.read_csv(StringIO(text), sep=sep)
                if len(frame.columns) > 1:
                    return frame
            except Exception:
                pass
    raise ValueError("Não foi possível interpretar o arquivo CSV")


def _to_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return pd.to_numeric(
        series.astype(str).str.strip().str.replace(" ", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )


def prepare_thermal_profile(raw: pd.DataFrame, mapping: ThermalInputMapping) -> pd.DataFrame:
    if mapping.timestamp not in raw.columns or mapping.power_requested not in raw.columns:
        raise ValueError("Timestamp e potência solicitada são obrigatórios")

    out = pd.DataFrame()
    out["timestamp"] = pd.to_datetime(raw[mapping.timestamp], errors="coerce", dayfirst=False)
    out["power_requested_mw"] = _to_numeric(raw[mapping.power_requested])
    if mapping.inflexibility and mapping.inflexibility in raw.columns:
        out["inflexibility_input_mw"] = _to_numeric(raw[mapping.inflexibility])
    else:
        out["inflexibility_input_mw"] = np.nan

    out = out.dropna(subset=["timestamp", "power_requested_mw"]).copy()
    out = out.sort_values("timestamp").drop_duplicates(subset="timestamp", keep="last").reset_index(drop=True)
    if out.empty:
        raise ValueError("O arquivo não contém timestamp + potência solicitada válidos")
    if (out["power_requested_mw"] < 0).any():
        raise ValueError("Potência solicitada negativa encontrada")

    # Cada linha representa o intervalo até o timestamp seguinte. Para a última,
    # usa-se a mediana dos intervalos positivos. Isso preserva arquivos irregulares.
    next_ts = out["timestamp"].shift(-1)
    interval_h = (next_ts - out["timestamp"]).dt.total_seconds() / 3600.0
    positive = interval_h[interval_h > 0]
    typical_h = float(positive.median()) if not positive.empty else 1.0
    interval_h.iloc[-1] = typical_h
    bad = (~np.isfinite(interval_h)) | (interval_h <= 0)
    interval_h.loc[bad] = typical_h
    out["interval_hours"] = interval_h.astype(float)

    out.attrs["timestep_hours"] = typical_h
    out.attrs["timestep_minutes"] = typical_h * 60.0
    out.attrs["duration_hours"] = float(out["interval_hours"].sum())
    return out


def _count_starts(on: np.ndarray) -> np.ndarray:
    prev = np.r_[False, on[:-1]]
    return on & ~prev


def _ramp_flags(target: np.ndarray, timestamps: pd.Series, up: float | None, down: float | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(target)
    rate = np.full(n, np.nan, dtype=float)
    up_violation = np.zeros(n, dtype=bool)
    down_violation = np.zeros(n, dtype=bool)
    if n < 2:
        return rate, up_violation, down_violation

    delta_min = timestamps.diff().dt.total_seconds().to_numpy(dtype=float) / 60.0
    delta_p = np.r_[np.nan, np.diff(target)]
    valid = np.isfinite(delta_min) & (delta_min > 0)
    rate[valid] = delta_p[valid] / delta_min[valid]
    if up is not None:
        up_violation[valid] = rate[valid] > float(up) + 1e-9
    if down is not None:
        down_violation[valid] = rate[valid] < -float(down) - 1e-9
    return rate, up_violation, down_violation


def evaluate_thermal_dispatch(profile: pd.DataFrame, config: ThermalConfig) -> tuple[pd.DataFrame, dict]:
    config.validate()
    out = profile.copy()
    requested = out["power_requested_mw"].to_numpy(dtype=float)
    interval_h = out["interval_hours"].to_numpy(dtype=float)

    if config.dynamic == THERMAL_PLANT:
        if config.use_profile_inflexibility:
            inflex = out["inflexibility_input_mw"].to_numpy(dtype=float)
            inflex = np.where(np.isfinite(inflex), inflex, config.constant_inflexibility_mw)
        else:
            inflex = np.full(len(out), config.constant_inflexibility_mw, dtype=float)
        inflex = np.maximum(inflex, 0.0)
    else:
        inflex = np.zeros(len(out), dtype=float)

    contractual_target = np.maximum(requested, inflex)
    below_inflex = requested + 1e-9 < inflex
    above_pmax = contractual_target > config.pmax_mw + 1e-9

    # Mínimo técnico só é avaliado quando há solicitação positiva e o target
    # contratual não está naturalmente acima dele.
    on_requested = requested > 1e-9
    below_pmin = (
        (config.pmin_technical_mw > 0)
        & on_requested
        & (requested + 1e-9 < config.pmin_technical_mw)
    )

    delivered = np.minimum(contractual_target, config.pmax_mw)
    unmet = np.maximum(contractual_target - delivered, 0.0)
    inflex_adjustment = np.maximum(inflex - requested, 0.0)

    ramp_rate, ramp_up_violation, ramp_down_violation = _ramp_flags(
        contractual_target,
        out["timestamp"],
        config.ramp_up_mw_min if config.dynamic == THERMAL_PLANT else None,
        config.ramp_down_mw_min if config.dynamic == THERMAL_PLANT else None,
    )

    # Para gerador local, a potência solicitada é a necessidade do cliente.
    # A entrega real é limitada a Pmax; não existe must-run/inflexibilidade.
    if config.dynamic == LOCAL_GENERATOR:
        delivered = np.minimum(requested, config.pmax_mw)
        contractual_target = requested.copy()
        above_pmax = requested > config.pmax_mw + 1e-9
        unmet = np.maximum(requested - delivered, 0.0)
        below_inflex[:] = False
        below_pmin = np.zeros(len(out), dtype=bool)
        ramp_up_violation[:] = False
        ramp_down_violation[:] = False
        ramp_rate[:] = np.nan

    energy_requested = requested * interval_h
    energy_delivered = delivered * interval_h
    energy_unmet = unmet * interval_h
    energy_inflex = np.minimum(inflex, delivered) * interval_h
    energy_flexible = np.maximum(delivered - inflex, 0.0) * interval_h
    variable_cost = energy_delivered * config.cvu_rs_mwh

    on = delivered > 1e-9
    starts = _count_starts(on)
    startup_cost = starts.astype(float) * (config.startup_cost_rs if config.dynamic == LOCAL_GENERATOR else 0.0)
    total_cost_interval = variable_cost + startup_cost
    cumulative_cost = np.cumsum(total_cost_interval)

    out["inflexibility_mw"] = inflex
    out["contractual_target_mw"] = contractual_target
    out["power_delivered_mw"] = delivered
    out["power_unmet_mw"] = unmet
    out["inflexibility_adjustment_mw"] = inflex_adjustment
    out["ramp_rate_mw_min"] = ramp_rate
    out["violation_below_inflexibility"] = below_inflex
    out["violation_above_pmax"] = above_pmax
    out["violation_below_pmin"] = below_pmin
    out["violation_ramp_up"] = ramp_up_violation
    out["violation_ramp_down"] = ramp_down_violation
    out["start_event"] = starts
    out["energy_requested_mwh"] = energy_requested
    out["energy_delivered_mwh"] = energy_delivered
    out["energy_unmet_mwh"] = energy_unmet
    out["energy_inflexible_mwh"] = energy_inflex
    out["energy_flexible_mwh"] = energy_flexible
    out["variable_cost_rs"] = variable_cost
    out["startup_cost_rs"] = startup_cost
    out["total_cost_rs"] = total_cost_interval
    out["cumulative_cost_rs"] = cumulative_cost

    duration_h = float(interval_h.sum())
    energy_delivered_total = float(energy_delivered.sum())
    variable_cost_total = float(variable_cost.sum())
    startup_cost_total = float(startup_cost.sum())
    total_cost = variable_cost_total + startup_cost_total
    capacity_factor = energy_delivered_total / (config.pmax_mw * duration_h) if duration_h > 0 else 0.0

    kpis = {
        "dynamic": config.dynamic,
        "duration_hours": duration_h,
        "timestep_minutes": float(profile.attrs.get("timestep_minutes", np.nan)),
        "pmax_mw": float(config.pmax_mw),
        "cvu_rs_mwh": float(config.cvu_rs_mwh),
        "energy_requested_mwh": float(energy_requested.sum()),
        "energy_delivered_mwh": energy_delivered_total,
        "energy_unmet_mwh": float(energy_unmet.sum()),
        "energy_inflexible_mwh": float(energy_inflex.sum()),
        "energy_flexible_mwh": float(energy_flexible.sum()),
        "inflexibility_adjustment_mwh": float((inflex_adjustment * interval_h).sum()),
        "variable_cost_rs": variable_cost_total,
        "startup_cost_rs": startup_cost_total,
        "total_cost_rs": total_cost,
        "effective_cost_rs_mwh": total_cost / energy_delivered_total if energy_delivered_total > 0 else 0.0,
        "capacity_factor_period": float(capacity_factor),
        "max_requested_mw": float(np.max(requested)) if len(requested) else 0.0,
        "max_delivered_mw": float(np.max(delivered)) if len(delivered) else 0.0,
        "operating_hours": float(interval_h[on].sum()),
        "start_count": int(starts.sum()),
        "violations_inflexibility": int(below_inflex.sum()),
        "violations_pmax": int(above_pmax.sum()),
        "violations_pmin": int(below_pmin.sum()),
        "violations_ramp_up": int(ramp_up_violation.sum()),
        "violations_ramp_down": int(ramp_down_violation.sum()),
        "total_violations": int(
            below_inflex.sum() + above_pmax.sum() + below_pmin.sum() + ramp_up_violation.sum() + ramp_down_violation.sum()
        ),
        "cost_to_restore_inflexibility_rs": float((inflex_adjustment * interval_h).sum() * config.cvu_rs_mwh),
    }
    out.attrs.update(profile.attrs)
    out.attrs["thermal_config"] = config
    return out, kpis


def violations_dataframe(result: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for _, row in result.iterrows():
        ts = row["timestamp"]
        if bool(row["violation_below_inflexibility"]):
            rows.append({
                "timestamp": ts,
                "tipo": "Abaixo da inflexibilidade",
                "solicitado_mw": row["power_requested_mw"],
                "limite_mw": row["inflexibility_mw"],
                "desvio_mw": row["inflexibility_mw"] - row["power_requested_mw"],
            })
        if bool(row["violation_above_pmax"]):
            rows.append({
                "timestamp": ts,
                "tipo": "Acima de Pmax",
                "solicitado_mw": row["contractual_target_mw"],
                "limite_mw": result.attrs.get("thermal_config").pmax_mw if result.attrs.get("thermal_config") else np.nan,
                "desvio_mw": row["power_unmet_mw"],
            })
        if bool(row["violation_below_pmin"]):
            cfg = result.attrs.get("thermal_config")
            rows.append({
                "timestamp": ts,
                "tipo": "Abaixo do mínimo técnico",
                "solicitado_mw": row["power_requested_mw"],
                "limite_mw": cfg.pmin_technical_mw if cfg else np.nan,
                "desvio_mw": (cfg.pmin_technical_mw - row["power_requested_mw"]) if cfg else np.nan,
            })
        if bool(row["violation_ramp_up"]):
            cfg = result.attrs.get("thermal_config")
            rows.append({
                "timestamp": ts,
                "tipo": "Rampa de subida",
                "solicitado_mw": row["ramp_rate_mw_min"],
                "limite_mw": cfg.ramp_up_mw_min if cfg else np.nan,
                "desvio_mw": row["ramp_rate_mw_min"] - (cfg.ramp_up_mw_min if cfg and cfg.ramp_up_mw_min else 0),
            })
        if bool(row["violation_ramp_down"]):
            cfg = result.attrs.get("thermal_config")
            rows.append({
                "timestamp": ts,
                "tipo": "Rampa de descida",
                "solicitado_mw": row["ramp_rate_mw_min"],
                "limite_mw": -(cfg.ramp_down_mw_min if cfg and cfg.ramp_down_mw_min else 0),
                "desvio_mw": abs(row["ramp_rate_mw_min"]) - (cfg.ramp_down_mw_min if cfg and cfg.ramp_down_mw_min else 0),
            })
    return pd.DataFrame(rows)


def export_thermal_dataframe(result: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "timestamp", "interval_hours", "power_requested_mw", "inflexibility_mw",
        "contractual_target_mw", "power_delivered_mw", "power_unmet_mw",
        "ramp_rate_mw_min", "start_event", "energy_delivered_mwh", "energy_unmet_mwh",
        "variable_cost_rs", "startup_cost_rs", "total_cost_rs", "cumulative_cost_rs",
        "violation_below_inflexibility", "violation_above_pmax", "violation_below_pmin",
        "violation_ramp_up", "violation_ramp_down",
    ]
    return result[[c for c in cols if c in result.columns]].copy()
