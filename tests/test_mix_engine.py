import numpy as np
import pandas as pd

from config.pv_database import MODULE_DB
from config.thermal_database import LOCAL_GENERATOR
from config.wind_turbine_database import TURBINE_DB
from models.battery_model import BATTERY_2RC
from simulation.mix_engine import (
    SOURCE_ORDER,
    align_climate_to_operation,
    build_example_inputs,
    default_export_columns,
    detect_climate_columns,
    detect_operation_columns,
    run_mix,
)


def test_climate_is_interpolated_to_operation_timeline():
    operation = pd.date_range("2026-01-01 12:00", periods=11, freq="1min")
    climate = pd.DataFrame(
        {
            "timestamp": [operation[0], operation[-1]],
            "GHI_W_m2": [0.0, 1000.0],
            "temperature_C": [20.0, 30.0],
            "wind_speed_mps": [5.0, 10.0],
            "pressure_hPa": [1000.0, 1010.0],
            "humidity_pct": [50.0, 60.0],
            "wind_direction_deg": [350.0, 10.0],
        }
    )
    aligned = align_climate_to_operation(climate, pd.Series(operation))
    assert len(aligned) == len(operation)
    assert np.isclose(aligned.loc[5, "GHI_W_m2"], 500.0)
    # A interpolação angular deve atravessar 0°, e não 180°.
    assert min(abs(aligned.loc[5, "wind_direction_deg"]), abs(aligned.loc[5, "wind_direction_deg"] - 360.0)) < 1e-6


def test_mix_runs_existing_models_and_returns_master_timeline():
    operation, climate = build_example_inputs()
    operation = operation.iloc[:31].copy()
    climate = climate[climate["timestamp"] <= operation["timestamp"].max()].copy()

    enabled = {src: True for src in SOURCE_ORDER}
    config = {
        "solar": {
            "module_key": "CS7L-580MS" if "CS7L-580MS" in MODULE_DB else list(MODULE_DB)[0],
            "n_series": 2,
            "n_parallel": 3,
            "soiling_losses_pct": 0.0,
        },
        "wind": {"turbine_key": list(TURBINE_DB)[0], "turbine_count": 1, "apply_grid_loss": False},
        "thermal": {"dynamic": LOCAL_GENERATOR, "pmax_mw": 0.08, "cvu_rs_mwh": 900.0, "startup_cost_rs": 0.0},
        "battery": {
            "model_id": BATTERY_2RC,
            "n_series": 120,
            "n_parallel": 50,
            "initial_soc": 0.9,
            "integration_step_s": 10.0,
            "power_iterations": 2,
        },
        "h2": {"integration_step_s": 10.0},
    }
    result = run_mix(
        operation,
        climate,
        operation_mapping=detect_operation_columns(operation.columns),
        climate_mapping=detect_climate_columns(climate.columns),
        enabled_sources=enabled,
        config=config,
    )
    df = result.dataframe
    assert len(df) == len(operation)
    assert df["timestamp"].tolist() == operation["timestamp"].tolist()
    assert {"P_solar_kW", "P_wind_kW", "P_thermal_delivered_kW", "P_battery_delivered_kW", "P_H2_delivered_kW"} <= set(df.columns)
    assert np.allclose(df["P_total_generated_kW"], df["P_renewable_kW"] + df["P_dispatchable_kW"])
    assert "source_results" not in df.columns
    assert len(result.source_results["h2"]) > len(df)  # dinâmica interna preservada separadamente
    assert "timestamp" in default_export_columns(df)


def test_mix_without_total_demand_does_not_invent_balance():
    operation, climate = build_example_inputs()
    operation = operation.iloc[:21].drop(columns=["P_demanda_total_kW"])
    climate = climate[climate["timestamp"] <= operation["timestamp"].max()].copy()
    enabled = {src: src == "solar" for src in SOURCE_ORDER}
    mapping = detect_operation_columns(operation.columns)
    config = {
        "solar": {
            "module_key": "CS7L-580MS" if "CS7L-580MS" in MODULE_DB else list(MODULE_DB)[0],
            "n_series": 2,
            "n_parallel": 3,
            "soiling_losses_pct": 0.0,
        }
    }
    result = run_mix(
        operation,
        climate,
        operation_mapping=mapping,
        climate_mapping=detect_climate_columns(climate.columns),
        enabled_sources=enabled,
        config=config,
    )
    assert result.dataframe["P_demand_kW"].isna().all()
    assert result.dataframe["P_balance_kW"].isna().all()
    assert result.dataframe["curtailment_required"].eq(False).all()
    assert any("Demanda total não informada" in msg for msg in result.messages)


def test_disabled_sources_are_ignored_even_when_csv_contains_their_columns():
    operation, climate = build_example_inputs()
    operation = operation.iloc[:21].copy()
    climate = climate[climate["timestamp"] <= operation["timestamp"].max()].copy()

    # A coluna existe, mas deve ser completamente ignorada porque Térmica está OFF.
    operation["P_termica_requested_kW"] = "IGNORAR"
    enabled = {src: src == "solar" for src in SOURCE_ORDER}
    config = {
        "solar": {
            "module_key": "CS7L-580MS" if "CS7L-580MS" in MODULE_DB else list(MODULE_DB)[0],
            "n_series": 2,
            "n_parallel": 3,
            "soiling_losses_pct": 0.0,
        }
    }
    result = run_mix(
        operation,
        climate,
        operation_mapping=detect_operation_columns(operation.columns),
        climate_mapping=detect_climate_columns(climate.columns),
        enabled_sources=enabled,
        config=config,
    )

    df = result.dataframe
    assert df["P_thermal_requested_kW"].eq(0.0).all()
    assert df["P_thermal_delivered_kW"].eq(0.0).all()
    assert "thermal" not in result.source_results
    assert any("Térmica" in msg and "desativado" in msg for msg in result.messages)
    assert any("Eólica" in msg and "desativado" in msg for msg in result.messages)
    assert "P_thermal_requested_kW" not in default_export_columns(df)
