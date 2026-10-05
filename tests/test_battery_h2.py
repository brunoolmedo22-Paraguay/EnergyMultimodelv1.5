from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from h2_pemfc import Equivalent65kWHorizonDynamicModel
from h2_pemfc.ems_input import build_example_ems_profile, prepare_ems_profile
from models import battery_model as battery_model_module
from models.numerics import trapezoid_integral
from models.battery_model import (
    battery_kpis,
    build_battery_example,
    simulate_2rc,
    simulate_tremblay,
)


class BatteryModelTests(unittest.TestCase):
    def test_tremblay_discharge_reduces_soc(self):
        ts = pd.date_range("2026-09-14 08:00:00", periods=61, freq="1s")
        profile = pd.DataFrame({"timestamp": ts, "current_A": np.full(len(ts), 2.3)})
        result = simulate_tremblay(
            profile,
            battery_key="liion_3p3v_2p3ah",
            n_series=4,
            n_parallel=1,
            initial_soc=1.0,
        )
        self.assertLess(result["soc"].iloc[-1], result["soc"].iloc[0])
        self.assertTrue((result["voltage_V"] > 0).all())
        self.assertTrue((result["power_W"] > 0).all())

    def test_2rc_rest_keeps_soc_constant(self):
        ts = pd.date_range("2026-09-14 08:00:00", periods=31, freq="1s")
        profile = pd.DataFrame({"timestamp": ts, "current_A": np.zeros(len(ts))})
        result = simulate_2rc(profile, n_series=12, n_parallel=4, initial_soc=0.8)
        np.testing.assert_allclose(result["soc"], 0.8, atol=1e-12)
        np.testing.assert_allclose(result["power_W"], 0.0, atol=1e-12)

    def test_example_kpis_are_finite(self):
        result = simulate_2rc(build_battery_example(), n_series=12, n_parallel=4, initial_soc=0.9)
        kpis = battery_kpis(result)
        self.assertGreater(kpis["energy_discharge_Wh"], 0)
        self.assertGreater(kpis["energy_charge_Wh"], 0)
        self.assertTrue(all(np.isfinite(v) for v in kpis.values()))


class H2ModelTests(unittest.TestCase):
    def test_pemfc_example_returns_power_and_hydrogen(self):
        model = Equivalent65kWHorizonDynamicModel()
        prepared = prepare_ems_profile(build_example_ems_profile(), dynamic_model=model)
        result = model.simulate_profile(prepared.profile, internal_time_step_s=10.0)
        self.assertGreater(len(result), len(prepared.profile))
        self.assertGreater(result["P_FC_delivered_kW"].max(), 0)
        self.assertGreater(result["hydrogen_supplied_kg_h"].max(), 0)
        self.assertTrue(np.isfinite(result["V_stack_V"]).all())


class NumPyCompatibilityTests(unittest.TestCase):
    def test_integrators_work_when_numpy_trapz_is_absent(self):
        # Reproduz o ambiente do Streamlit Cloud com NumPy 2.5+, que removeu np.trapz.
        had_trapz = hasattr(np, "trapz")
        saved_trapz = getattr(np, "trapz", None)
        if had_trapz:
            delattr(np, "trapz")
        try:
            ts = pd.Series(pd.date_range("2026-09-14 08:00:00", periods=3, freq="1h"))
            x_h = (ts - ts.iloc[0]).dt.total_seconds().to_numpy(dtype=float) / 3600.0
            self.assertAlmostEqual(trapezoid_integral(np.array([0.0, 10.0, 10.0]), x_h), 15.0, places=9)
            discharge, charge = battery_model_module._integrate_energy_wh(
                np.array([100.0, -100.0, 100.0]), ts
            )
            self.assertAlmostEqual(discharge, 100.0, places=9)
            self.assertAlmostEqual(charge, 100.0, places=9)
        finally:
            if had_trapz:
                setattr(np, "trapz", saved_trapz)


if __name__ == "__main__":
    unittest.main()
