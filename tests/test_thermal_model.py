from pathlib import Path

import numpy as np

from config.thermal_database import LOCAL_GENERATOR, THERMAL_PLANT, CVU_PRESETS
from models.thermal_model import (
    ThermalConfig,
    ThermalInputMapping,
    detect_thermal_columns,
    evaluate_thermal_dispatch,
    prepare_thermal_profile,
    read_thermal_csv,
)

ROOT = Path(__file__).resolve().parents[1]
PLANT = ROOT / "Dados_exemplo" / "perfil_termico_usina_exemplo_30min.csv"
LOCAL = ROOT / "Dados_exemplo" / "perfil_gerador_local_exemplo_5min.csv"


def _load(path):
    raw = read_thermal_csv(path)
    d = detect_thermal_columns(raw.columns)
    mapping = ThermalInputMapping(d["timestamp"], d["power_requested"], d.get("inflexibility"))
    return prepare_thermal_profile(raw, mapping)


def test_cvu_presets_are_positive():
    assert "Óleo diesel" in CVU_PRESETS
    assert all(v["cvu_rs_mwh"] > 0 for v in CVU_PRESETS.values())


def test_plant_example_has_expected_duration_and_detects_violations():
    profile = _load(PLANT)
    cfg = ThermalConfig(
        dynamic=THERMAL_PLANT,
        pmax_mw=300.0,
        cvu_rs_mwh=400.0,
        constant_inflexibility_mw=80.0,
        use_profile_inflexibility=True,
    )
    result, k = evaluate_thermal_dispatch(profile, cfg)
    assert abs(k["duration_hours"] - 48.0) < 1e-9
    assert k["violations_inflexibility"] > 0
    assert k["violations_pmax"] > 0
    assert k["energy_delivered_mwh"] > 0
    assert np.isclose(k["variable_cost_rs"], k["energy_delivered_mwh"] * 400.0)
    assert result["power_delivered_mw"].max() <= 300.0 + 1e-9


def test_plant_below_inflexibility_is_raised_for_delivery_and_costed():
    profile = _load(PLANT).iloc[:1].copy()
    profile["power_requested_mw"] = 50.0
    profile["inflexibility_input_mw"] = 80.0
    profile["interval_hours"] = 0.5
    profile.attrs["timestep_minutes"] = 30.0
    cfg = ThermalConfig(THERMAL_PLANT, 300.0, 500.0, 80.0, True)
    result, k = evaluate_thermal_dispatch(profile, cfg)
    assert result.iloc[0]["violation_below_inflexibility"]
    assert np.isclose(result.iloc[0]["power_delivered_mw"], 80.0)
    assert np.isclose(k["energy_delivered_mwh"], 40.0)
    assert np.isclose(k["variable_cost_rs"], 20000.0)
    assert np.isclose(k["cost_to_restore_inflexibility_rs"], 7500.0)


def test_local_generator_counts_starts_and_unserved_energy():
    profile = _load(LOCAL)
    cfg = ThermalConfig(
        dynamic=LOCAL_GENERATOR,
        pmax_mw=0.5,
        cvu_rs_mwh=1000.0,
        startup_cost_rs=75.0,
    )
    result, k = evaluate_thermal_dispatch(profile, cfg)
    assert k["start_count"] == 3
    assert np.isclose(k["startup_cost_rs"], 225.0)
    assert k["energy_unmet_mwh"] > 0  # example has 0.52/0.55 MW above Pmax
    assert result["power_delivered_mw"].max() <= 0.5 + 1e-9
    assert np.isclose(k["total_cost_rs"], k["variable_cost_rs"] + 225.0)


def test_local_generator_25_minute_event_cost_formula():
    profile = _load(LOCAL).iloc[36:41].copy().reset_index(drop=True)
    profile.attrs["timestep_minutes"] = 5.0
    profile.attrs["duration_hours"] = 25/60
    cfg = ThermalConfig(LOCAL_GENERATOR, 0.5, 1200.0, startup_cost_rs=100.0)
    _, k = evaluate_thermal_dispatch(profile, cfg)
    expected_energy = profile["power_requested_mw"].sum() * (5/60)
    assert np.isclose(k["energy_delivered_mwh"], expected_energy)
    assert k["start_count"] == 1
    assert np.isclose(k["total_cost_rs"], expected_energy * 1200.0 + 100.0)


def test_plant_ramp_violation_is_flagged_without_silent_dispatch_rewrite():
    raw = read_thermal_csv(PLANT).iloc[:3].copy()
    raw["power_requested_mw"] = [50.0, 250.0, 250.0]
    raw["inflexibility_mw"] = [0.0, 0.0, 0.0]
    d = detect_thermal_columns(raw.columns)
    profile = prepare_thermal_profile(raw, ThermalInputMapping(d["timestamp"], d["power_requested"], d["inflexibility"]))
    cfg = ThermalConfig(
        dynamic=THERMAL_PLANT,
        pmax_mw=300.0,
        cvu_rs_mwh=400.0,
        ramp_up_mw_min=5.0,  # em 30 min admite +150 MW; pedido sobe +200 MW
        ramp_down_mw_min=5.0,
    )
    result, k = evaluate_thermal_dispatch(profile, cfg)
    assert k["violations_ramp_up"] == 1
    assert result.iloc[1]["violation_ramp_up"]
    # V1.1 avalia o programa; não inventa uma nova curva de despacho por ramp-clipping.
    assert np.isclose(result.iloc[1]["power_delivered_mw"], 250.0)
