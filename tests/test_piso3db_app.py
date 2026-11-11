"""Piso 3D-B0 na interface (AppTest): a página REAL da rodada V2 monta o marco Trama e desenha a Partitura sem solver nem
modelos; a vista clássica continua na página; rodadas V1.6 não passam pela Partitura."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except Exception:  # noqa: BLE001
    AppTest = None

sys.path.insert(0, str(Path(__file__).resolve().parent))

import piso3db_util as U  # noqa: E402
from integracao_v2 import execucao as X  # noqa: E402
from integracao_v2 import trama_frame as TF  # noqa: E402

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
NO_ADMIN = {"SEEDS2_ADMIN_PASSWORD": "", "SEEDS2_DEV_MODE": ""}


def _texts(app) -> str:
    out = []
    for kind in ("markdown", "caption", "info", "warning", "error", "success", "html"):
        out += [str(getattr(e, "value", "") or getattr(e, "body", "") or "") for e in app.get(kind)]
    return "\n".join(out)


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class PartituraNaRodadaTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        self._env = mock.patch.dict(os.environ, NO_ADMIN)
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def session(self, uid, tab, query=None):
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=240)
        app.session_state["mg_active_uid"] = uid
        app.session_state["seeds_route"] = {"view": "operacao", "tab": tab}
        for k, v in (query or {}).items():
            app.query_params[k] = v
        app.run()
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        return app

    @unittest.skipUnless(U.SOLVER, "Pyomo/HiGHS não instalados")
    def test_rodada_v2_real_monta_o_marco_e_mantem_a_vista_classica_sem_solver(self):
        uid, st, run = U.missao_hibrida(self.dir, "Microrrede UI 3D-B")
        falha = AssertionError("modelo/curva/motor chamado ao reabrir")
        with mock.patch.object(X, "submit", side_effect=falha), \
                mock.patch("integracao_v2.curva_h2.obter_curva", side_effect=falha), \
                mock.patch("integracao_v2.pemfc_dinamica.verificar_despacho", side_effect=falha), \
                mock.patch("integracao_v2.montagem.construir_missao", side_effect=falha), \
                mock.patch.dict(sys.modules, {"pyomo": None, "highspy": None}):
            app = self.session(uid, "rodada", query={"run": run.run_uid})
            frames = app.session_state["op_v2_frame"]
            self.assertEqual(len(frames), 1)
            frame = next(iter(frames.values()))
            self.assertEqual((frame["formato"], frame["rodada"]["uid"]), (TF.FORMATO, run.run_uid))
            self.assertTrue(frame["verificacao"]["ok"])
            self.assertEqual(frame["resumo"]["custo_realizado_total_R"], run.summary["mission"]["custo_realizado_total_R"])
            # nomes e TAG vêm do inventário de referência da versão do cenário executada
            self.assertEqual({r["nome"] for r in frame["recursos"]["bat"]}, {"Banco 01"})
            self.assertEqual({r["tag"] for r in frame["recursos"]["fc"]}, {"FC-01"})
            txt = _texts(app)
            self.assertIn("Vista clássica", txt)                       # caminho de compatibilidade preservado
            self.assertIn("Custo REALIZADO", txt)
            self.assertIn("Critério de aceitação", txt)
            self.assertTrue(any(e.label.startswith("✓ Evidência verificada") for e in app.expander))
            self.assertGreaterEqual(len(app.get("plotly_chart")), 2)
            app.run()                                                    # rerun: o marco em cache é reutilizado
            self.assertIs(next(iter(app.session_state["op_v2_frame"].values())), frame)

    def test_rodada_v16_nao_passa_pela_partitura(self):
        from seeds2.microgrid.registry import MicrogridRegistry
        from seeds2.operation import runner
        from seeds2_fixtures import v16_equivalent_config
        from test_seeds2_piso2c import ready

        cfg = v16_equivalent_config("Industrial 3D-B (V1.6)")
        MicrogridRegistry(self.dir).create(cfg)
        uid = cfg["installation"]["uid"]
        st = MicrogridRegistry(self.dir).open(uid)
        sc = ready(st, name="Cenário V1.6")
        run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual(run.state, "concluida", run.error)
        app = self.session(uid, "rodada", query={"run": run.run_uid})
        self.assertNotIn("op_v2_frame", app.session_state)
        self.assertNotIn("Vista clássica", _texts(app))
        self.assertGreaterEqual(len(app.get("plotly_chart")), 1)


if __name__ == "__main__":
    unittest.main()
