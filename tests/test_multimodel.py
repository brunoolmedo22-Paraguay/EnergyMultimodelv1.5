from __future__ import annotations

from io import StringIO
import unittest

import numpy as np
import pandas as pd

from config.pv_database import MODULE_DB, get_module
from simulation.multimodel import (
    DEFAULT_EXPORT_COLUMNS,
    MODEL_NOCT,
    MODEL_SDM,
    MODEL_SIMPLE,
    build_export_dataframe,
    build_synthetic_profile,
    compute_model_kpis,
    prepare_uploaded_profile,
    run_all_models,
    simulate_irradiance_model,
    simulate_noct_efficiency_model,
    simulate_sdm_model,
)
from simulation.solver import extract_sdm_params
from visualization.multimodel_plots import plot_difference_to_reference


def constant_profile(g: float = 1000.0, tamb: float | None = 25.0) -> pd.DataFrame:
    index = pd.date_range("2026-03-21 12:00:00", periods=120, freq="1min", name="timestamp")
    data = {"G": np.full(120, g, dtype=float)}
    data["Tamb"] = np.full(120, np.nan if tamb is None else tamb, dtype=float)
    return pd.DataFrame(data, index=index)


class MultiModelPhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = get_module("CS7L-580MS")
        cls.module.sdm, cls.report = extract_sdm_params(cls.module.stc)

    def test_sdm_extraction_converges(self):
        self.assertTrue(self.report.success)
        self.assertLess(self.report.cost, 1e-6)

    def test_linear_model_matches_nameplate_at_stc_irradiance(self):
        result = simulate_irradiance_model(
            self.module, constant_profile(), n_series=2, n_parallel=3
        )
        expected = self.module.stc.p_nom * 6
        np.testing.assert_allclose(result["P_array"], expected, rtol=0, atol=1e-10)

    def test_noct_model_applies_datasheet_thermal_derating(self):
        result = simulate_noct_efficiency_model(
            self.module, constant_profile(), n_series=2, n_parallel=3
        )
        expected_tc = 25.0 + (self.module.stc.noct - 20.0) / 800.0 * 1000.0
        self.assertAlmostEqual(float(result["Tc"].iloc[0]), expected_tc, places=10)
        self.assertLess(float(result["P_array"].iloc[0]), self.module.stc.p_nom * 6)

    def test_sdm_runs_complete_120_minute_window(self):
        result = simulate_sdm_model(
            self.module, constant_profile(g=800.0, tamb=28.0), n_series=2, n_parallel=3
        )
        self.assertEqual(len(result), 120)
        self.assertTrue((result["P_array"] > 0).all())
        self.assertIn("Vmp_array", result.columns)
        self.assertIn("Imp_array", result.columns)

    def test_missing_temperature_keeps_simple_model_available(self):
        results, statuses = run_all_models(
            self.module, constant_profile(g=700.0, tamb=None), n_series=2, n_parallel=3
        )
        self.assertEqual(set(results), {MODEL_SIMPLE})
        self.assertTrue(statuses[MODEL_SIMPLE].available)
        self.assertFalse(statuses[MODEL_NOCT].available)
        self.assertFalse(statuses[MODEL_SDM].available)

    def test_kpis_and_export_are_consistent(self):
        result = simulate_irradiance_model(
            self.module, constant_profile(g=500.0), n_series=2, n_parallel=3
        )
        kpi = compute_model_kpis(result, self.module)
        expected_power = self.module.stc.p_nom * 0.5 * 6
        expected_energy = expected_power * 2.0 / 1000.0
        self.assertAlmostEqual(kpi["energy_kWh"], expected_energy, places=10)
        export = build_export_dataframe(result, DEFAULT_EXPORT_COLUMNS)
        self.assertEqual(export.columns.tolist(), ["timestamp", "potencia_gerada_W"])
        self.assertEqual(len(export), 120)


class InputContractTests(unittest.TestCase):
    def test_synthetic_profile_supports_a_full_day(self):
        profile = build_synthetic_profile(
            start="2026-03-21 00:00:00",
            irradiance_profile="Irradiância perfeita",
            season="Verano",
            duration_minutes=1440,
        )
        self.assertEqual(len(profile), 1440)
        self.assertEqual(profile.attrs["duration_minutes"], 1440)
        self.assertEqual(profile.index.min(), pd.Timestamp("2026-03-21 00:00:00"))
        self.assertEqual(profile.index.max(), pd.Timestamp("2026-03-21 23:59:00"))

    def test_perfect_irradiance_is_a_smooth_single_peak_curve(self):
        profile = build_synthetic_profile(
            start="2026-03-21 00:00:00",
            irradiance_profile="Irradiância perfeita",
            season="Verano",
            duration_minutes=1440,
            g_peak=1000.0,
        )
        daylight = profile.loc[profile["G"] > 0, "G"].to_numpy(dtype=float)
        peak = int(np.argmax(daylight))
        self.assertGreater(len(daylight), 600)
        self.assertTrue((np.diff(daylight[: peak + 1]) >= -1e-9).all())
        self.assertTrue((np.diff(daylight[peak:]) <= 1e-9).all())
        self.assertAlmostEqual(float(daylight.max()), 1000.0, places=8)

    def test_csv_without_temperature_is_valid_for_degraded_mode(self):
        index = pd.date_range("2026-03-21 06:01:00", periods=120, freq="1min")
        raw = pd.DataFrame({"timestamp": index, "GHI": np.linspace(0, 800, 120)})
        profile = prepare_uploaded_profile(
            raw,
            timestamp_col="timestamp",
            irradiance_col="GHI",
            temperature_col=None,
        )
        self.assertEqual(len(profile), 120)
        self.assertTrue(profile["Tamb"].isna().all())
        self.assertFalse(profile.attrs["temperature_available"])

    def test_csv_must_have_120_consecutive_minutes(self):
        index = pd.date_range("2026-03-21 06:01:00", periods=119, freq="1min")
        raw = pd.DataFrame({"timestamp": index, "GHI": np.linspace(0, 800, 119)})
        with self.assertRaises(ValueError):
            prepare_uploaded_profile(
                raw,
                timestamp_col="timestamp",
                irradiance_col="GHI",
                temperature_col=None,
            )

    def test_all_catalog_modules_supply_the_three_shared_datasheet_inputs(self):
        for key in MODULE_DB:
            with self.subTest(module=key):
                module = get_module(key)
                self.assertGreater(module.stc.p_nom, 0)
                self.assertGreater(module.stc.area, 0)
                self.assertGreater(module.stc.noct, 20)
                self.assertLess(module.stc.gamma_pmax_pct, 0)

    def test_sdm_parameters_converge_for_every_catalog_module(self):
        for key in MODULE_DB:
            with self.subTest(module=key):
                module = get_module(key)
                _, report = extract_sdm_params(module.stc)
                self.assertTrue(report.success)
                self.assertLess(report.cost, 1e-6)


class ComparisonReferenceTests(unittest.TestCase):
    def test_relative_power_difference_uses_the_selected_reference(self):
        index = pd.date_range("2026-03-21 12:00:00", periods=3, freq="1min")
        results = {
            MODEL_SIMPLE: pd.DataFrame({"P_array": [100.0, 200.0, 0.0]}, index=index),
            MODEL_NOCT: pd.DataFrame({"P_array": [110.0, 180.0, 5.0]}, index=index),
            MODEL_SDM: pd.DataFrame({"P_array": [90.0, 220.0, 7.0]}, index=index),
        }
        figure = plot_difference_to_reference(results, MODEL_SIMPLE)
        self.assertIsNotNone(figure)
        traces = {trace.name: np.asarray(trace.y, dtype=float) for trace in figure.data}
        np.testing.assert_allclose(
            traces["Modelo 2 · NOCT + eficiência"][:2],
            [10.0, -10.0],
            atol=1e-12,
        )
        np.testing.assert_allclose(
            traces["Modelo 3 · Single Diode Model"][:2],
            [-10.0, 10.0],
            atol=1e-12,
        )
        self.assertTrue(np.isnan(traces["Modelo 2 · NOCT + eficiência"][2]))
        self.assertIn("Irradiância", figure.layout.yaxis.title.text)


if __name__ == "__main__":
    unittest.main()
