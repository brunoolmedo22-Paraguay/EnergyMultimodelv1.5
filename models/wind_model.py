"""Modelo energético eólico V1.

Convierte un perfil meteorológico en potencia eléctrica mediante la curva de
potencia del fabricante. La frontera del modelo es deliberadamente eléctrica:
no se vuelven a aplicar eficiencias de rotor/caja/generador sobre una curva de
potencia eléctrica. Opcionalmente se descuenta un 3 % genérico entre la salida
del aerogenerador y el punto de inserción a red.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from typing import BinaryIO, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from config.wind_turbine_database import DEFAULT_REFERENCE_AIR_DENSITY, get_turbine

RD = 287.058  # J/(kg K), aire seco
RV = 461.495  # J/(kg K), vapor de agua
GENERATOR_TO_GRID_GENERIC_LOSS = 0.03

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": (
        "timestamp", "datetime", "date_time", "data_hora", "datahora", "fecha_hora",
        "fecha", "data", "tempo", "time",
    ),
    "wind_speed": (
        "wind_speed", "windspeed", "wind_speed_m_s", "velocidade_vento",
        "velocidade_do_vento", "velocidad_viento", "velocidad_del_viento", "ws",
    ),
    "wind_direction": (
        "wind_direction", "winddirection", "direcao_vento", "direção_vento",
        "direccion_viento", "dirección_viento", "wd",
    ),
    "temperature": (
        "temperature", "temperature_c", "temperatura", "temperatura_c", "temp", "t_amb",
    ),
    "pressure": (
        "pressure", "pressure_hpa", "pressao", "pressão", "presion", "presión",
        "pressao_hpa", "presion_hpa",
    ),
    "humidity": (
        "humidity", "relative_humidity", "rh", "umidade", "umidade_relativa",
        "humedad", "humedad_relativa",
    ),
}


@dataclass(frozen=True)
class WindInputMapping:
    timestamp: str
    wind_speed: str
    wind_direction: str | None = None
    temperature: str | None = None
    pressure: str | None = None
    humidity: str | None = None


@dataclass(frozen=True)
class DensitySummary:
    moist_count: int
    dry_count: int
    reference_count: int
    mean_kg_m3: float

    @property
    def dominant_mode(self) -> str:
        counts = {
            "Ar úmido · P + T + UR": self.moist_count,
            "Ar seco · P + T": self.dry_count,
            "Referência · 1,225 kg/m³": self.reference_count,
        }
        return max(counts, key=counts.get) if sum(counts.values()) else "Sem dados"


def _normalize_name(value: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return "_".join(text.strip().lower().replace("/", "_").replace("-", "_").split())


def detect_columns(columns: Iterable[str]) -> dict[str, str | None]:
    normalized = {_normalize_name(col): col for col in columns}
    detected: dict[str, str | None] = {}
    for semantic, aliases in COLUMN_ALIASES.items():
        found = None
        for alias in aliases:
            key = _normalize_name(alias)
            if key in normalized:
                found = normalized[key]
                break
        detected[semantic] = found
    return detected


def _decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_wind_csv(source) -> pd.DataFrame:
    """Lee CSV con delimitador detectado automáticamente.

    Acepta paths, objetos UploadedFile/BytesIO o bytes. El decimal con coma se
    normaliza posteriormente columna por columna.
    """
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
        # fallback explícito para os separadores mais comuns
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
    clean = (
        series.astype(str)
        .str.strip()
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(clean, errors="coerce")


def prepare_wind_profile(raw: pd.DataFrame, mapping: WindInputMapping) -> pd.DataFrame:
    if mapping.timestamp not in raw.columns or mapping.wind_speed not in raw.columns:
        raise ValueError("Timestamp e velocidade do vento são obrigatórios")

    out = pd.DataFrame()
    out["timestamp"] = pd.to_datetime(raw[mapping.timestamp], errors="coerce", dayfirst=False)
    out["wind_speed_mps"] = _to_numeric(raw[mapping.wind_speed])

    optional = {
        "wind_direction_deg": mapping.wind_direction,
        "temperature_c": mapping.temperature,
        "pressure_input": mapping.pressure,
        "humidity_pct": mapping.humidity,
    }
    for target, source in optional.items():
        out[target] = _to_numeric(raw[source]) if source and source in raw.columns else np.nan

    out = out.dropna(subset=["timestamp", "wind_speed_mps"]).copy()
    out = out.sort_values("timestamp").drop_duplicates(subset="timestamp", keep="last").reset_index(drop=True)
    if out.empty:
        raise ValueError("O arquivo não contém linhas válidas de timestamp + velocidade do vento")
    if (out["wind_speed_mps"] < 0).any():
        raise ValueError("Velocidade do vento negativa encontrada no arquivo")

    # Direção meteorológica em [0, 360)
    out["wind_direction_deg"] = out["wind_direction_deg"] % 360.0

    # Pressão: aceita hPa/mbar ou Pa. Valores atmosféricos > 2000 são tratados como Pa.
    pressure = out["pressure_input"].copy()
    out["pressure_hpa"] = np.where(pressure > 2000.0, pressure / 100.0, pressure)

    # Umidade: aceita 0-1 ou 0-100.
    humidity = out["humidity_pct"].copy()
    finite_h = humidity[np.isfinite(humidity)]
    if not finite_h.empty and finite_h.median() <= 1.2:
        humidity = humidity * 100.0
    out["humidity_pct"] = humidity.clip(lower=0.0, upper=100.0)

    # Passo temporal típico. Cada amostra representa o intervalo até a próxima;
    # a última usa a mediana do arquivo.
    diffs_h = out["timestamp"].diff().dt.total_seconds().div(3600.0)
    positive = diffs_h[diffs_h > 0]
    step_h = float(positive.median()) if not positive.empty else 1.0 / 6.0
    out.attrs["timestep_hours"] = step_h
    out.attrs["timestep_minutes"] = step_h * 60.0
    out.attrs["duration_hours"] = step_h * len(out)
    return out


def _saturation_vapor_pressure_hpa(temp_c: np.ndarray) -> np.ndarray:
    # Buck (sobre água), adequado para a faixa meteorológica deste modelo.
    return 6.1121 * np.exp((18.678 - temp_c / 234.5) * (temp_c / (257.14 + temp_c)))


def calculate_air_density(profile: pd.DataFrame) -> tuple[pd.Series, pd.Series, DensitySummary]:
    t = profile["temperature_c"].to_numpy(dtype=float)
    p = profile["pressure_hpa"].to_numpy(dtype=float)
    rh = profile["humidity_pct"].to_numpy(dtype=float)

    rho = np.full(len(profile), DEFAULT_REFERENCE_AIR_DENSITY, dtype=float)
    mode = np.full(len(profile), "reference", dtype=object)

    valid_pt = np.isfinite(t) & np.isfinite(p) & (p > 100.0)
    valid_rh = valid_pt & np.isfinite(rh)

    # P + T: aire seco
    tk = t[valid_pt] + 273.15
    rho[valid_pt] = (p[valid_pt] * 100.0) / (RD * tk)
    mode[valid_pt] = "dry"

    # P + T + RH: aire húmedo
    if valid_rh.any():
        temp = t[valid_rh]
        pressure_hpa = p[valid_rh]
        es = _saturation_vapor_pressure_hpa(temp)
        pv_hpa = np.clip(rh[valid_rh] / 100.0 * es, 0.0, pressure_hpa * 0.2)
        pd_hpa = pressure_hpa - pv_hpa
        tk2 = temp + 273.15
        rho[valid_rh] = (pd_hpa * 100.0) / (RD * tk2) + (pv_hpa * 100.0) / (RV * tk2)
        mode[valid_rh] = "moist"

    # Filtro prudente contra errores de unidad/entrada. Si un cálculo produce
    # densidad físicamente absurda, vuelve al valor de referencia.
    bad = (~np.isfinite(rho)) | (rho < 0.7) | (rho > 1.5)
    rho[bad] = DEFAULT_REFERENCE_AIR_DENSITY
    mode[bad] = "reference"

    summary = DensitySummary(
        moist_count=int(np.sum(mode == "moist")),
        dry_count=int(np.sum(mode == "dry")),
        reference_count=int(np.sum(mode == "reference")),
        mean_kg_m3=float(np.mean(rho)),
    )
    return pd.Series(rho, index=profile.index, name="air_density_kg_m3"), pd.Series(mode, index=profile.index, name="density_mode"), summary


def _interp_curve(points: Sequence[Sequence[float]], wind_speed: np.ndarray) -> np.ndarray:
    xs = np.asarray([p[0] for p in points], dtype=float)
    ys = np.asarray([p[1] for p in points], dtype=float)
    return np.interp(wind_speed, xs, ys, left=0.0, right=ys[-1])


def _power_from_manufacturer_density_table(entry: Mapping, wind: np.ndarray, rho: np.ndarray) -> np.ndarray:
    density_curves: Mapping[float, Sequence[Sequence[float]]] = entry["curve"]["density_curves"]
    densities = np.asarray(sorted(float(d) for d in density_curves), dtype=float)
    result = np.empty(len(wind), dtype=float)

    for i, (v, r) in enumerate(zip(wind, rho)):
        if r < densities[0] or r > densities[-1]:
            # Fuera del rango tabulado: vuelve a la corrección energética genérica
            ref = float(entry["curve"].get("reference_density_kg_m3", DEFAULT_REFERENCE_AIR_DENSITY))
            veq = float(v) * (max(float(r), 0.01) / ref) ** (1.0 / 3.0)
            result[i] = float(_interp_curve(entry["curve"]["points"], np.asarray([veq]))[0])
            continue

        hi_idx = int(np.searchsorted(densities, r, side="left"))
        if hi_idx == 0:
            lo = hi = densities[0]
        elif hi_idx >= len(densities):
            lo = hi = densities[-1]
        else:
            lo, hi = densities[hi_idx - 1], densities[hi_idx]

        p_lo = float(_interp_curve(density_curves[float(lo)], np.asarray([v]))[0])
        if hi == lo:
            result[i] = p_lo
        else:
            p_hi = float(_interp_curve(density_curves[float(hi)], np.asarray([v]))[0])
            alpha = (r - lo) / (hi - lo)
            result[i] = p_lo + alpha * (p_hi - p_lo)
    return result


def run_wind_model(
    profile: pd.DataFrame,
    turbine_key: str,
    turbine_count: int = 1,
    apply_generic_grid_loss: bool = False,
) -> tuple[pd.DataFrame, dict, DensitySummary]:
    if turbine_count < 1:
        raise ValueError("Quantidade de aerogeradores deve ser >= 1")

    entry = get_turbine(turbine_key)
    spec = entry["spec"]
    curve = entry["curve"]
    rated_kw = float(spec["rated_power_kw"])

    rho_s, density_mode_s, density_summary = calculate_air_density(profile)
    rho = rho_s.to_numpy(dtype=float)
    wind = profile["wind_speed_mps"].to_numpy(dtype=float)

    if curve.get("density_correction") == "manufacturer_density_table" and curve.get("density_curves"):
        p_unit_kw = _power_from_manufacturer_density_table(entry, wind, rho)
        veq = wind.copy()  # a tabela já usa vhub diretamente
        density_method = "Tabela do fabricante por densidade"
    else:
        ref_rho = float(curve.get("reference_density_kg_m3") or DEFAULT_REFERENCE_AIR_DENSITY)
        veq = wind * np.power(np.maximum(rho, 0.01) / ref_rho, 1.0 / 3.0)
        p_unit_kw = _interp_curve(curve["points"], veq)
        density_method = "Velocidade equivalente por densidade"

    # As proteções operacionais são aplicadas à velocidade real no cubo.
    cut_in = spec.get("cut_in_mps")
    cut_out = spec.get("cut_out_mps")
    if cut_in is not None:
        p_unit_kw = np.where(wind < float(cut_in), 0.0, p_unit_kw)
    if cut_out is not None:
        p_unit_kw = np.where(wind >= float(cut_out), 0.0, p_unit_kw)

    p_unit_kw = np.clip(p_unit_kw, 0.0, rated_kw)
    p_gross_kw = p_unit_kw * turbine_count
    loss_factor = 1.0 - GENERATOR_TO_GRID_GENERIC_LOSS if apply_generic_grid_loss else 1.0
    p_net_kw = p_gross_kw * loss_factor

    rotor_area = float(spec["swept_area_m2"]) * turbine_count
    wind_available_kw = 0.5 * rho * rotor_area * np.power(wind, 3.0) / 1000.0
    apparent_eff = np.divide(p_gross_kw, wind_available_kw, out=np.zeros_like(p_gross_kw), where=wind_available_kw > 1e-9)

    result = profile.copy()
    result["air_density_kg_m3"] = rho
    result["density_mode"] = density_mode_s.to_numpy()
    result["equivalent_wind_speed_mps"] = veq
    result["power_unit_kw"] = p_unit_kw
    result["power_gross_kw"] = p_gross_kw
    result["power_net_kw"] = p_net_kw
    result["wind_power_available_kw"] = wind_available_kw
    result["apparent_wind_to_electric_efficiency"] = apparent_eff

    step_h = float(profile.attrs.get("timestep_hours", 1.0 / 6.0))
    duration_h = step_h * len(result)
    installed_kw = rated_kw * turbine_count
    gross_energy = float(np.sum(p_gross_kw) * step_h)
    net_energy = float(np.sum(p_net_kw) * step_h)
    losses_energy = gross_energy - net_energy

    generating = p_gross_kw > max(installed_kw * 0.001, 0.1)
    nominal = p_gross_kw >= installed_kw * 0.99
    below_cut_in = wind < float(cut_in) if cut_in is not None else np.zeros(len(wind), dtype=bool)
    above_cut_out = wind >= float(cut_out) if cut_out is not None else np.zeros(len(wind), dtype=bool)

    def _hours(mask: np.ndarray) -> float:
        return float(np.sum(mask) * step_h)

    kpis = {
        "turbine_key": turbine_key,
        "turbine_count": int(turbine_count),
        "rated_power_unit_kw": rated_kw,
        "installed_power_kw": installed_kw,
        "duration_h": duration_h,
        "timestep_minutes": step_h * 60.0,
        "energy_gross_kwh": gross_energy,
        "energy_net_kwh": net_energy,
        "energy_losses_kwh": losses_energy,
        "capacity_factor_gross": gross_energy / (installed_kw * duration_h) if installed_kw * duration_h > 0 else 0.0,
        "capacity_factor_net": net_energy / (installed_kw * duration_h) if installed_kw * duration_h > 0 else 0.0,
        "equivalent_hours_gross": gross_energy / installed_kw if installed_kw > 0 else 0.0,
        "equivalent_hours_net": net_energy / installed_kw if installed_kw > 0 else 0.0,
        "power_mean_gross_kw": float(np.mean(p_gross_kw)),
        "power_max_gross_kw": float(np.max(p_gross_kw)),
        "power_mean_net_kw": float(np.mean(p_net_kw)),
        "power_max_net_kw": float(np.max(p_net_kw)),
        "wind_mean_mps": float(np.mean(wind)),
        "wind_max_mps": float(np.max(wind)),
        "wind_min_mps": float(np.min(wind)),
        "air_density_mean_kg_m3": float(np.mean(rho)),
        "generating_hours": _hours(generating),
        "below_cut_in_hours": _hours(below_cut_in),
        "nominal_hours": _hours(nominal),
        "above_cut_out_hours": _hours(above_cut_out),
        "generic_grid_loss_applied": bool(apply_generic_grid_loss),
        "generic_grid_loss_fraction": GENERATOR_TO_GRID_GENERIC_LOSS if apply_generic_grid_loss else 0.0,
        "density_correction_method": density_method,
        "cut_out_is_known": cut_out is not None,
    }
    result.attrs.update(profile.attrs)
    result.attrs["turbine_key"] = turbine_key
    result.attrs["turbine_count"] = turbine_count
    result.attrs["generic_grid_loss_applied"] = apply_generic_grid_loss
    return result, kpis, density_summary


def export_wind_dataframe(result: pd.DataFrame) -> pd.DataFrame:
    preferred = [
        "timestamp", "wind_speed_mps", "wind_direction_deg", "temperature_c", "pressure_hpa",
        "humidity_pct", "air_density_kg_m3", "density_mode", "equivalent_wind_speed_mps",
        "power_unit_kw", "power_gross_kw", "power_net_kw", "wind_power_available_kw",
        "apparent_wind_to_electric_efficiency",
    ]
    cols = [c for c in preferred if c in result.columns]
    return result[cols].copy()


__all__ = [
    "GENERATOR_TO_GRID_GENERIC_LOSS",
    "WindInputMapping",
    "DensitySummary",
    "detect_columns",
    "read_wind_csv",
    "prepare_wind_profile",
    "calculate_air_density",
    "run_wind_model",
    "export_wind_dataframe",
]
