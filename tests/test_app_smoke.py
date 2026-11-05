"""Smoke tests da interface V1.6.

Na V1.6 a aplicação abre direto no console unificado (Orchestrator). As
bancadas individuais de cada física ficam na página **Modelos**, no expander
"Bancadas individuais dos modelos", com botões ``ABRIR <FONTE>``.
"""
from __future__ import annotations

import unittest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

if AppTest is not None:
    from apptest_utils import abrir, botao, continuar

PAGINAS_V16 = (
    "▦  Visão Geral",
    "⌁  Módulo de Carga",
    "◈  Modelos",
    "◎  Otimizador",
    "◫  Resultados do Otimizador",
    "▤  Resultados dos Modelos",
    "⇩  Exportar Resultados",
)


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class AppSmokeTest(unittest.TestCase):
    def _open_bench(self, rotulo: str, energy_source: str) -> AppTest:
        """Modelos → Bancadas individuais → ABRIR <rotulo>; retorna a bancada renderizada."""
        app = abrir()
        self.assertEqual(len(app.exception), 0)
        botao(app, "◈  Modelos").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["orchestrator_page"], "Modelos")
        self.assertIn("Bancadas individuais dos modelos · ferramenta avançada", [e.label for e in app.expander])
        botao(app, f"ABRIR {rotulo}").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["energy_source"], energy_source)
        bench = continuar(app)
        self.assertEqual(len(bench.exception), 0, [e.value for e in bench.exception])
        self.assertEqual(bench.session_state["energy_source"], energy_source)
        self.assertIn("← FONTES DE ENERGIA", [b.label for b in bench.button])
        # A bancada substitui o console: a navegação do Orchestrator não é renderizada.
        self.assertNotIn("◎  Otimizador", [b.label for b in bench.button])
        return bench

    def test_main_console_renders(self):
        app = abrir()
        self.assertEqual(len(app.exception), 0)
        labels = [b.label for b in app.button]
        for pagina in PAGINAS_V16:
            self.assertIn(pagina, labels)
        self.assertIsNone(app.session_state["energy_source"])
        self.assertEqual(app.session_state["orchestrator_page"], "Visão Geral")
        # V1.6 não usa mais dados DEMO: sem rodada até o usuário executar o otimizador,
        # mas a carga padrão (walk-forward) já está carregada.
        self.assertIsNone(app.session_state["orq_result_item"])
        self.assertIsNotNone(app.session_state["orq_load"])
        self.assertGreater(len(app.session_state["orq_load"].P_kW), 0)

    def test_models_page_lists_all_benches(self):
        app = abrir()
        botao(app, "◈  Modelos").click().run()
        self.assertEqual(len(app.exception), 0)
        labels = [b.label for b in app.button]
        for rotulo in ("SOLAR", "EÓLICA", "BATERIA", "H₂ / PEMFC", "TÉRMICA"):
            self.assertIn(f"ABRIR {rotulo}", labels)

    def test_solar_module_still_opens(self):
        app = self._open_bench("SOLAR", "solar")
        self.assertEqual(app.session_state["current_page"], "Visão geral")
        self.assertIn("Entrada", [b.label for b in app.button])

    def test_wind_example_runs_end_to_end(self):
        app = self._open_bench("EÓLICA", "wind")

        botao(app, "Simulação").click().run()
        source = next(r for r in app.radio if r.label == "Fonte")
        source.set_value("Exemplo sintético · Ceará").run()
        self.assertEqual(len(app.exception), 0)
        botao(app, "▶ CALCULAR PERFIL EÓLICO").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIsNotNone(app.session_state["wind_result"])
        self.assertEqual(len(app.session_state["wind_result"]), 1008)
        self.assertGreater(app.session_state["wind_kpis"]["energy_gross_kwh"], 0)

        botao(app, "Catálogo de aerogeradores").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertGreaterEqual(len(app.get("plotly_chart")), 1)

    def test_thermal_module_opens(self):
        app = self._open_bench("TÉRMICA", "thermal")
        self.assertIn("Simulação", [b.label for b in app.button])

    def test_battery_module_opens(self):
        app = self._open_bench("BATERIA", "battery")
        self.assertIn("Simulação", [b.label for b in app.button])

    def test_h2_module_opens(self):
        app = self._open_bench("H₂ / PEMFC", "h2")
        self.assertIn("Simulação", [b.label for b in app.button])

    def test_bench_returns_to_console(self):
        app = self._open_bench("EÓLICA", "wind")
        botao(app, "← FONTES DE ENERGIA").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIsNone(app.session_state["energy_source"])
        console = continuar(app)
        self.assertEqual(len(console.exception), 0)
        for pagina in PAGINAS_V16:
            self.assertIn(pagina, [b.label for b in console.button])


if __name__ == "__main__":
    unittest.main()
