"""Runtime unificado Energy MultiModel -> EMS.

Esta camada é a integração real entre a interface principal e o núcleo EMS.
Não contém UI: recebe a carga, a configuração dos modelos e a configuração do
otimizador, executa os modelos físicos necessários, monta o contrato de troca e
roda o despacho de Marília. As páginas do Orchestrator consomem o mesmo estado.
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np
import pandas as pd

from config.pv_database import get_module
from config.thermal_database import LOCAL_GENERATOR
from config.wind_turbine_database import get_turbine
from ems_integration import ponte
from ems_integration.executor import executar_pacote, validar_fc_dinamico
from models.battery_model import BATTERY_TREMBLAY
from models.thermal_model import ThermalConfig
from models.wind_model import WindInputMapping, prepare_wind_profile, run_wind_model
from simulation.mix_engine import align_climate_to_operation, detect_climate_columns, prepare_climate
from simulation.multimodel import simulate_noct_efficiency_model

PASSO_VALIDACAO_S = 10.0

ALGORITMOS = {
    "GWO · Grey Wolf Optimizer": 2,
    "NGO · Northern Goshawk Optimization": 3,
    "GA · Algoritmo genético": 1,
    "Só SQP (sem metaheurística)": 0,
}


def default_model_spec() -> dict[str, Any]:
    """Configuração central inicial. Nada aqui é um resultado sintético do EMS."""
    return {
        "solar": {
            "active": True,
            "module_key": "CS7L-590MS",
            "n_series": 2,
            "n_parallel": 10,
            "soiling_losses_pct": 0.0,
        },
        "wind": {
            "active": False,
            "turbine_key": "EWT DW61-1MW",
            "turbine_count": 1,
            "apply_grid_loss": False,
        },
        "fc": {
            "active": True,
            "N_fc": 4,
            "base": "entregue",
        },
        "battery": {
            "active": True,
            "model": BATTERY_TREMBLAY,
            "key": "liion_3p3v_2p3ah",
            "Ns": 200,
            "Np": 132,
            "soc0": 0.60,
            "soc_min": 0.20,
            "soc_max": 0.90,
            "c_desc": 1.0,
            "c_carga": 0.5,
        },
        "thermal": {
            "active": False,
            "pmax_kW": 80.0,
            "pmin_kW": 20.0,
            "cvu": 1100.0,
            "ramp": 20.0,
            "partida": 50.0,
        },
        "climate": {
            "source": "Sintético diário",
        },
    }


def default_optimizer_config() -> dict[str, Any]:
    return {
        "algoritmo": 2,
        "N": 3,
        "seed": 0,
        "meta_penalizada": False,
        "validar": False,
        "soc_alvo_tol": 0.05,
        "econ": {
            "preco_H2_rs_kg": 25.0,
            "c_deg_bateria_rs_kWh": 0.08,
            "pen_deficit_rs_kWh": 50.0,
            "pen_excesso_rs_kWh": 0.5,
        },
        "eta_conv": {
            "eta_dc1": 0.97,
            "eta_dc2": 0.96,
            "eta_dc": 0.97,
        },
    }


def load_timestamps(carga: ponte.PerfilCarga) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(carga.t0 + pd.to_timedelta(carga.t_min, unit="min"), name="timestamp")


def synthetic_climate(carga: ponte.PerfilCarga) -> pd.DataFrame:
    """Clima diário simples para demonstrar o encadeamento sem esconder sua origem.

    Ele só é usado quando o usuário seleciona explicitamente "Sintético diário".
    O perfil respeita o horário real da missão, de forma que uma missão noturna
    tenha GHI zero em vez de receber uma curva solar arbitrária de 2 h.
    """
    ts = load_timestamps(carga)
    hour = ts.hour.to_numpy(dtype=float) + ts.minute.to_numpy(dtype=float) / 60.0
    sun = np.sin(np.pi * (hour - 6.0) / 12.0)
    ghi = 850.0 * np.clip(sun, 0.0, None) ** 1.25
    temp = 25.0 + 5.5 * np.sin(2 * np.pi * (hour - 8.0) / 24.0)
    wind = 6.5 + 1.2 * np.sin(2 * np.pi * (hour + 1.5) / 8.0) + 0.45 * np.sin(np.arange(len(ts)) / 7.0)
    wind = np.maximum(wind, 0.2)
    direction = (110.0 + 22.0 * np.sin(np.arange(len(ts)) / 18.0)) % 360.0
    pressure = 1009.0 + 1.8 * np.cos(np.arange(len(ts)) / 30.0)
    humidity = np.clip(67.0 - 10.0 * np.sin(2 * np.pi * (hour - 7.0) / 24.0), 35.0, 95.0)
    return pd.DataFrame({
        "timestamp": ts,
        "GHI_W_m2": ghi,
        "temperature_C": temp,
        "wind_speed_mps": wind,
        "wind_direction_deg": direction,
        "pressure_hPa": pressure,
        "humidity_pct": humidity,
    })


def climate_from_csv(raw: pd.DataFrame, carga: ponte.PerfilCarga, *, solar: bool, wind: bool) -> pd.DataFrame:
    """Normaliza um CSV climático e o alinha à grade temporal da missão."""
    enabled = {"solar": bool(solar), "wind": bool(wind)}
    detected = detect_climate_columns(raw.columns)
    climate = prepare_climate(raw, detected, enabled)
    operation_ts = pd.Series(load_timestamps(carga))
    return align_climate_to_operation(climate, operation_ts)


def _thermal_cfg(spec: Mapping[str, Any]) -> ThermalConfig:
    ramp = float(spec.get("ramp", 0.0)) / 1000.0 if float(spec.get("ramp", 0.0)) > 0 else None
    return ThermalConfig(
        dynamic=LOCAL_GENERATOR,
        pmax_mw=float(spec.get("pmax_kW", 80.0)) / 1000.0,
        cvu_rs_mwh=float(spec.get("cvu", 1100.0)),
        pmin_technical_mw=float(spec.get("pmin_kW", 20.0)) / 1000.0,
        ramp_up_mw_min=ramp,
        ramp_down_mw_min=ramp,
        startup_cost_rs=float(spec.get("partida", 50.0)),
    )


def _simulate_solar(carga: ponte.PerfilCarga, climate: pd.DataFrame, spec: Mapping[str, Any]) -> pd.DataFrame:
    module = get_module(str(spec["module_key"]))
    profile = pd.DataFrame(
        {
            "G": climate["GHI_W_m2"].to_numpy(dtype=float),
            "Tamb": climate["temperature_C"].to_numpy(dtype=float),
        },
        index=load_timestamps(carga),
    )
    return simulate_noct_efficiency_model(
        module,
        profile,
        n_series=int(spec.get("n_series", 2)),
        n_parallel=int(spec.get("n_parallel", 10)),
        soiling_losses=float(spec.get("soiling_losses_pct", 0.0)) / 100.0,
        noct=None,
    )


def _simulate_wind(carga: ponte.PerfilCarga, climate: pd.DataFrame, spec: Mapping[str, Any]) -> tuple[pd.DataFrame, dict]:
    raw = pd.DataFrame({
        "timestamp": load_timestamps(carga),
        "wind_speed": climate["wind_speed_mps"],
        "wind_direction": climate["wind_direction_deg"],
        "temperature": climate["temperature_C"],
        "pressure": climate["pressure_hPa"],
        "humidity": climate["humidity_pct"],
    })
    profile = prepare_wind_profile(
        raw,
        WindInputMapping("timestamp", "wind_speed", "wind_direction", "temperature", "pressure", "humidity"),
    )
    result, kpis, density = run_wind_model(
        profile,
        str(spec["turbine_key"]),
        int(spec.get("turbine_count", 1)),
        bool(spec.get("apply_grid_loss", False)),
    )
    meta = dict(kpis)
    meta["mean_air_density_kg_m3"] = density.mean_kg_m3
    return result, meta


def build_exchange_package(
    carga: ponte.PerfilCarga,
    model_spec: Mapping[str, Any],
    optimizer_cfg: Mapping[str, Any],
    *,
    climate_raw: pd.DataFrame | None = None,
    destino: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Executa os modelos ativos e monta o pacote que o EMS consome.

    Retorna o diretório do pacote e um dicionário com as saídas físicas usadas
    pelo otimizador. Assim Resultados dos Modelos e o solver leem a MESMA rodada.
    """
    t0, dur = carga.t0, carga.duracao_min
    tabelas: dict[str, pd.DataFrame] = {}
    outputs: dict[str, Any] = {}
    notes: list[str] = []
    options: dict[str, Any] = {}

    fc_spec = model_spec.get("fc", {})
    bat_spec = model_spec.get("battery", {})
    th_spec = model_spec.get("thermal", {})
    solar_spec = model_spec.get("solar", {})
    wind_spec = model_spec.get("wind", {})

    if bool(fc_spec.get("active")):
        fc = ponte.caracterizar_fc(t0, dur)
        tabelas["fc"] = fc
        outputs["fc_characterization"] = fc
        options["fc_base_potencia"] = str(fc_spec.get("base", "entregue"))
        n_fc = int(fc_spec.get("N_fc", 4))
    else:
        n_fc = 1

    if bool(bat_spec.get("active")):
        bat, E = ponte.caracterizar_bateria(
            t0, dur,
            str(bat_spec.get("model", BATTERY_TREMBLAY)),
            bat_spec.get("key"),
            int(bat_spec.get("Ns", 200)),
            int(bat_spec.get("Np", 132)),
            float(bat_spec.get("soc0", 0.60)),
            float(bat_spec.get("c_desc", 1.0)),
            float(bat_spec.get("c_carga", 0.5)),
        )
        soc0 = float(bat["soc_percent"].iloc[0]) / 100.0
        soc_min = float(bat_spec.get("soc_min", 0.20))
        soc_max = float(bat_spec.get("soc_max", 0.90))
        if not soc_min <= soc0 <= soc_max:
            raise ValueError(f"SOC inicial da bateria ({soc0:.0%}) fora da faixa [{soc_min:.0%}, {soc_max:.0%}].")
        tabelas["bateria"] = bat
        outputs["battery_characterization"] = bat
        outputs["battery_energy_kWh"] = float(E)
        options.update(bateria_E_kWh=float(E), bateria_SOC_min=soc_min, bateria_SOC_max=soc_max)

    if bool(th_spec.get("active")):
        cfg = _thermal_cfg(th_spec)
        term = ponte.disponibilidade_termica(t0, dur, cfg)
        tabelas["termica"] = term
        outputs["thermal_availability"] = term
        options.update(ponte.opcoes_termica(cfg))

    if not tabelas:
        raise ValueError("Ative pelo menos uma fonte despachável: H₂/PEMFC, bateria ou térmica.")

    need_climate = bool(solar_spec.get("active")) or bool(wind_spec.get("active"))
    climate: pd.DataFrame | None = None
    if need_climate:
        source = str(model_spec.get("climate", {}).get("source", "Sintético diário"))
        if source == "CSV climático":
            if climate_raw is None:
                raise ValueError("Solar/eólica ativa com 'CSV climático': carregue o arquivo na página Modelos.")
            climate = climate_from_csv(
                climate_raw,
                carga,
                solar=bool(solar_spec.get("active")),
                wind=bool(wind_spec.get("active")),
            )
            notes.append("Clima: CSV do usuário alinhado à missão.")
        else:
            climate = synthetic_climate(carga)
            notes.append("Clima: perfil sintético diário explicitamente selecionado na página Modelos.")
        outputs["climate"] = climate

    pv_ems: pd.DataFrame | None = None
    if bool(solar_spec.get("active")):
        assert climate is not None
        solar = _simulate_solar(carga, climate, solar_spec)
        outputs["solar"] = solar
        pv_ems, _ = ponte.pv_de_solar(solar, t0, dur, False)

    eol_ems: pd.DataFrame | None = None
    if bool(wind_spec.get("active")):
        assert climate is not None
        wind, wind_meta = _simulate_wind(carga, climate, wind_spec)
        outputs["wind"] = wind
        outputs["wind_kpis"] = wind_meta
        eol_ems, _ = ponte.eolica_de_modulo(wind, t0, dur, False)

    config = {
        "tag": carga.descricao,
        "N_fc": n_fc,
        "Ts_s": 60,
        "N": int(optimizer_cfg.get("N", 3)),
        "algoritmo": int(optimizer_cfg.get("algoritmo", 2)),
        "meta_penalizada": bool(optimizer_cfg.get("meta_penalizada", False)),
        "seed": int(optimizer_cfg.get("seed", 0)),
        "soc_alvo_tol": float(optimizer_cfg.get("soc_alvo_tol", 0.05)),
        "econ": dict(optimizer_cfg.get("econ", {})),
        "eta_conv": dict(optimizer_cfg.get("eta_conv", {})),
        "opcoes_fontes": options,
        "pv_P_rated_kWp": float(pv_ems["P_kW"].max()) + 1.0 if pv_ems is not None else None,
        "notas": notes,
    }
    path = ponte.escrever_pacote(carga, tabelas, pv_ems, config, destino=destino, eolica=eol_ems)
    outputs["package_dir"] = str(path)
    outputs["notes"] = notes
    return path, outputs


def run_optimizer(
    package_dir: Path,
    optimizer_cfg: Mapping[str, Any],
    *,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    r = executar_pacote(package_dir, progresso=progress, sobrescrever={"algoritmo": int(optimizer_cfg.get("algoritmo", 2))})
    val = None
    if bool(optimizer_cfg.get("validar", False)) and "fc" in r["nomes"]:
        try:
            val = validar_fc_dinamico(r, passo_s=PASSO_VALIDACAO_S)
        except Exception as exc:
            r.setdefault("avisos", []).append(f"Validação dinâmica falhou: {exc}")
    return r, val


def series_dataframe(r: Mapping[str, Any]) -> pd.DataFrame:
    kv = int(r["k_validos"])
    df = pd.DataFrame({
        "timestamp": r["t0"] + pd.to_timedelta(r["t_min"][:kv], unit="min"),
        "t_min": r["t_min"][:kv],
        "P_carga_kW": r["P_load_kW"][:kv],
        "P_solar_kW": r["P_pv_kW"][:kv],
        "P_eolica_kW": r["P_eol_kW"][:kv],
        "P_renovavel_vertida_kW": r["P_renov_vertida_kW"][:kv],
        "P_carga_liquida_kW": r["P_load_liq_kW"][:kv],
    })
    for j, nome in enumerate(r["nomes"]):
        df[f"P_{nome}_kW"] = r["P_kW"][:kv, j]
        df[f"P_{nome}_meta_kW"] = r["P_meta_kW"][:kv, j]
        if r["tipos"][j] == "armazenamento":
            df[f"SOC_{nome}"] = r["SOC"][:kv, j]
        else:
            df[f"n_{nome}"] = r["n_unid"][:kv, j]
    df["deficit_kW"] = r["deficit_kW"][:kv]
    df["excesso_despachavel_kW"] = r["excesso_kW"][:kv]
    df["h2_kg"] = r["rel"]["h2_kg_passo"][:kv]
    df["custo_rs"] = r["custo_rs"][:kv]
    df["J_meta_rs"] = r["J_meta"][:kv]
    df["J_refino_rs"] = r["J_ref"][:kv]
    df["violacao_meta"] = r["viol_meta"][:kv]
    return df


def model_dispatch_dataframe(r: Mapping[str, Any], source: str) -> pd.DataFrame:
    """Série que o usuário vê em Resultados dos Modelos: exatamente a rodada EMS."""
    kv = int(r["k_validos"])
    ts = r["t0"] + pd.to_timedelta(r["t_min"][:kv], unit="min")
    base = pd.DataFrame({"timestamp": ts})
    if source == "solar":
        base["Disponível [kW]"] = r["eta_pv"] * r["P_pv_kW"][:kv]
        total_ren = r["eta_pv"] * r["P_pv_kW"][:kv] + r["eta_eol"] * r["P_eol_kW"][:kv]
        used = r["P_load_kW"][:kv] - r["P_load_liq_kW"][:kv]
        frac = np.divide(r["eta_pv"] * r["P_pv_kW"][:kv], total_ren, out=np.zeros(kv), where=total_ren > 1e-12)
        base["Usado no atendimento [kW]"] = used * frac
        base["Vertido renovável [kW]"] = np.maximum(base["Disponível [kW]"] - base["Usado no atendimento [kW]"], 0.0)
        return base
    if source == "wind":
        base["Disponível [kW]"] = r["eta_eol"] * r["P_eol_kW"][:kv]
        total_ren = r["eta_pv"] * r["P_pv_kW"][:kv] + r["eta_eol"] * r["P_eol_kW"][:kv]
        used = r["P_load_kW"][:kv] - r["P_load_liq_kW"][:kv]
        frac = np.divide(r["eta_eol"] * r["P_eol_kW"][:kv], total_ren, out=np.zeros(kv), where=total_ren > 1e-12)
        base["Usado no atendimento [kW]"] = used * frac
        base["Vertido renovável [kW]"] = np.maximum(base["Disponível [kW]"] - base["Usado no atendimento [kW]"], 0.0)
        return base

    name = {"h2": "fc", "battery": "bateria", "thermal": "termica"}[source]
    if name not in r["nomes"]:
        return base
    j = r["nomes"].index(name)
    base["Despacho [kW]"] = r["P_kW"][:kv, j]
    if name == "fc":
        base["Stacks ligados"] = r["n_unid"][:kv, j]
        base["H₂ no passo [kg]"] = r["rel"]["h2_kg_passo"][:kv]
        base["H₂ acumulado [kg]"] = np.cumsum(r["rel"]["h2_kg_passo"][:kv])
    elif name == "bateria":
        base["SOC [%]"] = 100.0 * r["SOC"][:kv, j]
    elif name == "termica":
        base["Unidades ligadas"] = r["n_unid"][:kv, j]
        base["Rampa [kW/passo]"] = np.r_[0.0, np.diff(r["P_kW"][:kv, j])]
    return base


def active_source_labels(spec: Mapping[str, Any]) -> list[str]:
    mapping = [("solar", "Solar"), ("wind", "Eólica"), ("battery", "Bateria"), ("fc", "H₂ / PEMFC"), ("thermal", "Térmica")]
    return [label for key, label in mapping if bool(spec.get(key, {}).get("active"))]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def export_bundle(
    carga: ponte.PerfilCarga,
    model_spec: Mapping[str, Any],
    optimizer_cfg: Mapping[str, Any],
    item: Mapping[str, Any],
    model_outputs: Mapping[str, Any] | None = None,
) -> bytes:
    """Pacote auditável da ÚNICA rodada integrada."""
    r = item["resultado"]
    series = series_dataframe(r)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("01_carga.csv", carga.df().to_csv(index=False, sep=";", decimal=",", float_format="%.6f"))
        zf.writestr("02_despacho_ems.csv", series.to_csv(index=False, sep=";", decimal=",", float_format="%.6f"))
        zf.writestr("03_modelos_config.json", json.dumps(_json_safe(model_spec), indent=2, ensure_ascii=False))
        zf.writestr("04_otimizador_config.json", json.dumps(_json_safe(optimizer_cfg), indent=2, ensure_ascii=False))
        resumo = {
            "algoritmo": r["algoritmo"],
            "carga": r["carga_descricao"],
            "k_validos": int(r["k_validos"]),
            "N": int(r["N"]),
            "custo_total_rs": float(r["rel"]["custo_total_rs"]),
            "energia_nao_atendida_kWh": float(r["rel"]["energia_nao_atendida_kWh"]),
            "energia_vertida_kWh": float(r["rel"]["energia_vertida_kWh"]),
            "avisos": list(r.get("avisos", [])),
            "quando": item.get("quando"),
        }
        zf.writestr("05_resumo_execucao.json", json.dumps(_json_safe(resumo), indent=2, ensure_ascii=False))
        if item.get("validacao") is not None:
            zf.writestr("06_validacao_pemfc.json", json.dumps(_json_safe(item["validacao"]), indent=2, ensure_ascii=False))
        if model_outputs:
            for key, value in model_outputs.items():
                if isinstance(value, pd.DataFrame):
                    zf.writestr(f"modelos/{key}.csv", value.to_csv(index=False, sep=";", decimal=",", float_format="%.6f"))
    return buf.getvalue()


__all__ = [
    "ALGORITMOS", "PASSO_VALIDACAO_S", "active_source_labels", "build_exchange_package",
    "default_model_spec", "default_optimizer_config", "export_bundle", "load_timestamps",
    "model_dispatch_dataframe", "run_optimizer", "series_dataframe", "synthetic_climate",
]
