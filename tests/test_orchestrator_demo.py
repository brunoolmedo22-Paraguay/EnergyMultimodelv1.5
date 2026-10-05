import unittest

from simulation.orchestrator_demo import DemoConfig, make_demand_curve, run_demo_optimizer


class OrchestratorDemoTests(unittest.TestCase):
    def test_default_scenario_is_deterministic_and_balanced(self):
        demand = make_demand_curve()
        result1, summary1 = run_demo_optimizer(demand, DemoConfig())
        result2, summary2 = run_demo_optimizer(demand, DemoConfig())
        self.assertEqual(len(result1), 96)
        self.assertTrue(result1.equals(result2))
        self.assertAlmostEqual(summary1["demand_energy_kwh"], summary2["demand_energy_kwh"])
        self.assertGreater(summary1["renewable_share_pct"], 0)
        self.assertGreaterEqual(result1["SOC_bateria_pct"].min(), 19.999)
        self.assertGreaterEqual(summary1["unserved_energy_kwh"], 0)

    def test_disabling_solar_removes_solar_generation(self):
        demand = make_demand_curve()
        result, _ = run_demo_optimizer(demand, DemoConfig(active_solar=False))
        self.assertAlmostEqual(float(result["P_solar_kW"].sum()), 0.0)


if __name__ == "__main__":
    unittest.main()
