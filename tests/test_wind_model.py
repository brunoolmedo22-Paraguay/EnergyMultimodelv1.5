from pathlib import Path

import numpy as np

from config.wind_turbine_database import TURBINE_DB
from models.wind_model import (
    WindInputMapping,
    calculate_air_density,
    detect_columns,
    prepare_wind_profile,
    read_wind_csv,
    run_wind_model,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "Dados_exemplo" / "perfil_eolico_sintetico_ceara_1_semana_10min.csv"


def _profile():
    raw = read_wind_csv(EXAMPLE)
    d = detect_columns(raw.columns)
    mapping = WindInputMapping(
        d["timestamp"], d["wind_speed"], d["wind_direction"],
        d["temperature"], d["pressure"], d["humidity"],
    )
    return prepare_wind_profile(raw, mapping)


def test_example_is_one_week_at_ten_minutes():
    profile = _profile()
    assert len(profile) == 1008
    assert abs(profile.attrs["timestep_minutes"] - 10.0) < 1e-9
    assert abs(profile.attrs["duration_hours"] - 168.0) < 1e-9


def test_density_uses_moist_air_when_all_variables_exist():
    profile = _profile()
    rho, modes, summary = calculate_air_density(profile)
    assert summary.moist_count == len(profile)
    assert summary.reference_count == 0
    assert 1.10 < rho.mean() < 1.22


def test_all_catalog_turbines_run_and_respect_rated_power():
    profile = _profile()
    for key, entry in TURBINE_DB.items():
        result, kpi, _ = run_wind_model(profile, key, turbine_count=2, apply_generic_grid_loss=False)
        rated_total = entry["spec"]["rated_power_kw"] * 2
        assert len(result) == len(profile)
        assert result["power_gross_kw"].max() <= rated_total * 1.000001
        assert 0 <= kpi["capacity_factor_gross"] <= 1


def test_generic_grid_loss_is_exactly_three_percent():
    profile = _profile()
    gross, kg, _ = run_wind_model(profile, "Nordex N117/2400", 1, False)
    net, kn, _ = run_wind_model(profile, "Nordex N117/2400", 1, True)
    assert np.allclose(net["power_net_kw"], gross["power_gross_kw"] * 0.97)
    assert np.isclose(kn["energy_net_kwh"], kg["energy_gross_kwh"] * 0.97)
    assert np.isclose(kn["capacity_factor_net"], kg["capacity_factor_gross"] * 0.97)


def test_direction_does_not_change_power_in_v1():
    profile = _profile()
    r1, _, _ = run_wind_model(profile, "Vestas V90-3.0 MW", 1, False)
    profile2 = profile.copy()
    profile2["wind_direction_deg"] = (profile2["wind_direction_deg"] + 177.0) % 360
    r2, _, _ = run_wind_model(profile2, "Vestas V90-3.0 MW", 1, False)
    assert np.allclose(r1["power_gross_kw"], r2["power_gross_kw"])
