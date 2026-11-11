"""Piso 3D-A2-R na interface (AppTest): declarações de renováveis VAZIAS na etapa 03, preflight V2 que explica o
potencial derivado (ou o bloqueio) na etapa 04, execução real de uma microrrede FV + eólica + bateria + PCC e reabertura
em sessão NOVA com os modelos físicos, o runner e o solver sabotados.

O AppTest não executa JavaScript: gráficos pela especificação Plotly. Navegador real: ``tools/e2e/e2e_piso3da2r.js``.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
if AppTest is not None:
    from apptest_utils import APP_PATH, botao, continuar

import piso3da2r_util as R  # noqa: E402
from ems_v2.milp.ambiente import verificar_ambiente  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import execucao as X  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.operation import runner  # noqa: E402
from seeds2.operation import service as SV  # noqa: E402

SOLVER = bool(verificar_ambiente().get("disponivel"))
NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}
VENTO_H = [2.0, 3.0, 9.0, 10.0, 11.0, 12.0, 12.0, 10.0, 4.0, 3.0, 2.5, 2.0]


def _ok(tc, app):
    tc.assertEqual(len(app.exception), 0, [e.value for e in app.exception])


def _texts(app) -> str:
    parts = ["\n".join(h.proto.body for h in app.get("html"))] + [c.value for c in app.caption] + \
            [w.value for w in app.warning] + [e.value for e in app.error] + [m.value for m in app.markdown]
    return "\n".join(parts).replace("\\", "")


def _clima(doc):
    return R.clima_tabela(doc, {"ghi_W_m2": [0, 0, 0, 0, 0, 0, 100, 350, 600, 800, 950, 1000],
                                "temperature_C": [20, 20, 20, 21, 21, 22, 23, 25, 27, 29, 30, 31],
                                "wind_speed_m_s": VENTO_H})


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        self._env = mock.patch.dict(os.environ, NO_ADMIN)
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def make(self, **kw):
        cfg = R.config_hibrida("Microrrede UI 3D-A2-R", **kw)
        MicrogridRegistry(self.dir).create(cfg)
        uid = cfg["installation"]["uid"]
        return uid, MicrogridRegistry(self.dir).open(uid)

    def session(self, uid, tab=None, view="operacao", query=None):
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=180)
        if uid:
            app.session_state["mg_active_uid"] = uid
            app.session_state["seeds_route"] = {"view": view, "tab": tab}
        for k, v in (query or {}).items():
            app.query_params[k] = v
        app.run()
        _ok(self, app)
        return app


class EstrategiaRenovaveisTest(_Base):
    def test_declaracoes_de_renovaveis_comecam_vazias(self):
        uid, st = self.make()
        sc = SV.create(st, name="Cenário híbrido de interface")
        app = self.session(uid, "estrategia")
        radio = next(r for r in app.radio if (r.key or "").endswith("_motor"))
        radio.set_value(E.MOTOR_V2).run()
        app = continuar(app, 120)
        botao(app, "CRIAR DECLARAÇÃO DA ESTRATÉGIA V2 (CAMPOS EM BRANCO)").click().run()
        app = continuar(app, 120)
        _ok(self, app)
        txt = _texts(app)
        self.assertIn("Renováveis: clima previsto e declarações por equipamento", txt)
        self.assertIn("MODELOS FÍSICOS do SEEDS2", txt)
        eta = [n for n in app.number_input if (n.key or "").endswith("_eta")]
        self.assertEqual(len(eta), 1)
        self.assertIsNone(eta[0].value)                                     # nenhum parâmetro físico pré-preenchido
        rho = [s for s in app.selectbox if (s.key or "").endswith("_rho")]
        self.assertTrue(rho and rho[0].value is None)
        self.assertIn("clima.semantica", txt)
        botao(app, "SALVAR CENÁRIO").click().run()
        b = st.get_scenario(sc.scenario_uid).document[E.CHAVE_BLOCO]
        ids = R.ids(st.get_scenario(sc.scenario_uid).document)
        self.assertEqual(b["format_version"], 2)
        self.assertIsNone(b["renovaveis"][ids["fv"]]["eta_conversao_barramento"])
        self.assertIsNone(b["renovaveis"][ids["eolica"]]["hipotese_densidade"])


class ExecucaoRenovaveisTest(_Base):
    def test_curva_nao_habilitada_bloqueia_com_explicacao(self):
        uid, st = self.make(fv=False, turbina=R.TURBINA_ANALISE)
        R.criar_cenario_hibrido(st, clima=_clima)
        app = self.session(uid, "execucao")
        txt = _texts(app)
        self.assertIn("NÃO pode ser executado pelo motor V2", txt)
        self.assertIn("ANÁLISE de pontos", txt)
        b = next(x for x in app.button if x.label.startswith("▶ EXECUTAR MISSÃO V2"))
        self.assertTrue(b.disabled)
        self.assertEqual(st.list_runs(), [])

    @unittest.skipUnless(SOLVER, "Pyomo/HiGHS não instalados (pip install -r requirements-ems_v2.txt)")
    def test_executar_hibrida_e_reabrir_sem_modelos_nem_otimizador(self):
        uid, st = self.make()
        R.criar_cenario_hibrido(st, demanda_kW=40.0, clima=_clima)
        app = self.session(uid, "execucao")
        txt = _texts(app)
        self.assertIn("Apto para o motor V2", txt)
        self.assertIn("Modelo FV 2", txt)
        self.assertIn("Curva do catálogo", txt)
        next(x for x in app.button if x.label.startswith("▶ EXECUTAR MISSÃO V2")).click().run()
        _ok(self, app)
        runs = st.list_runs()
        self.assertEqual(len(runs), 1)
        self.assertTrue(runner.wait(runs[0].run_uid, 300))
        run = st.get_run(runs[0].run_uid)
        self.assertEqual(run.state, "concluida", run.error)
        falha = AssertionError("motor ou modelo físico chamado ao reabrir")
        with mock.patch.object(X, "submit", side_effect=falha), mock.patch.object(X, "_executar", side_effect=falha), \
                mock.patch("integracao_v2.montagem.construir_missao", side_effect=falha), \
                mock.patch("integracao_v2.renovaveis.derivar_fv", side_effect=falha), \
                mock.patch("integracao_v2.renovaveis.derivar_eolica", side_effect=falha), \
                mock.patch("simulation.multimodel.simulate_noct_efficiency_model", side_effect=falha), \
                mock.patch("models.wind_model.run_wind_model", side_effect=falha), \
                mock.patch.dict(sys.modules, {"pyomo": None, "highspy": None}):
            rv = self.session(uid, "rodada", query={"run": run.run_uid})
            txt = _texts(rv)
            self.assertIn("Custo REALIZADO", txt)
            self.assertIn("Renovável (UID)", txt)
            self.assertIn("Fotovoltaica", txt)
            self.assertIn("Eólica", txt)
            self.assertTrue(any(e.label.startswith("✓ Evidência verificada") for e in rv.expander))
            specs = [json.loads(c.proto.spec) for c in rv.get("plotly_chart")]
            ren = next(s for s in specs if "Potencial renovável por UID" in s["layout"]["title"]["text"])
            nomes = [t["name"] for t in ren["data"]]
            self.assertTrue(any(n.startswith("Vertida ") for n in nomes) and any(n.startswith("Aproveitada ") for n in nomes))
            pot = next(s for s in specs if "Demanda × atendimento" in s["layout"]["title"]["text"])
            self.assertTrue(any(t["name"].startswith("Renovável ") for t in pot["data"]))
            self.assertEqual(len(rv.get("download_button")), len(RG.OBRIGATORIOS) + 1)     # + v2/renovaveis.json
        self.assertEqual(len(st.list_runs()), 1)
