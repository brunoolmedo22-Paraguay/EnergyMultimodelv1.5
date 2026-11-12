"""Piso 3D-B na interface (AppTest): a página REAL da rodada V2 monta o marco Trama e desenha a Partitura sem solver nem
modelos; a vista clássica continua INTEIRA na página, recolhida num expansor identificado (decisão do responsável no
3D-B3); trocar de rodada e reabrir numa sessão nova sem solver; estudo arquivado; rodadas V1.6 não passam pela Partitura."""
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
            # a vista clássica continua inteira na página, recolhida por padrão num expansor IDENTIFICADO
            classica = [e for e in app.expander if e.label.startswith("Vista clássica")]
            self.assertEqual(len(classica), 1)
            self.assertFalse(classica[0].proto.expanded)
            self.assertIn("tabelas completas", classica[0].label)
            self.assertIn("Motor V2 experimental", txt)                # o aviso científico continua visível, fora do expansor
            self.assertIn("Custo REALIZADO", txt)
            self.assertIn("Critério de aceitação", txt)
            self.assertTrue(any(e.label.startswith("✓ Evidência verificada") for e in app.expander))
            self.assertGreaterEqual(len(app.get("plotly_chart")), 2)
            # tabelas originais, descargas e procedência continuam dentro da vista clássica
            self.assertTrue(any(e.label.startswith("Intervalos aplicados") for e in classica[0].expander))
            self.assertTrue(any(e.label.startswith("Procedência da rodada") for e in classica[0].expander))
            self.assertGreaterEqual(len(classica[0].get("download_button")), 1)
            self.assertGreaterEqual(len(classica[0].get("plotly_chart")), 2)
            app.run()                                                    # rerun: o marco em cache é reutilizado
            self.assertIs(next(iter(app.session_state["op_v2_frame"].values())), frame)

    @unittest.skipUnless(U.SOLVER, "Pyomo/HiGHS não instalados")
    def test_trocar_de_rodada_e_reabrir_em_sessao_nova_sem_solver(self):
        """Duas rodadas da MESMA microrrede: a sessão troca de uma para a outra (um marco por rodada, sem mistura) e uma
        sessão NOVA, sem solver, reconstrói exatamente o mesmo marco a partir dos dados gravados."""
        from seeds2.microgrid.registry import MicrogridRegistry

        uid, st, r1 = U.missao_24h(self.dir, "Microrrede duas rodadas 3D-B")
        sc2 = U.U.criar_cenario_v2(st, nome="Segunda rodada", soc0=100.0, demanda_kW=7.0)
        r2 = U.X.submit(st, sc2.scenario_uid, sc2.version, U.X.new_request_id(), background=False)
        self.assertEqual(r2.state, "concluida", r2.error)
        with mock.patch.object(X, "submit", side_effect=AssertionError("motor chamado ao reabrir")), \
                mock.patch.dict(sys.modules, {"pyomo": None, "highspy": None}):
            app = self.session(uid, "rodada", query={"run": r1.run_uid})
            f1 = app.session_state["op_v2_frame"][(r1.run_uid, "local")]
            app.session_state["op_run_uid"] = r2.run_uid                 # o que «ABRIR» faz na lista de rodadas
            app.run()
            self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
            frames = app.session_state["op_v2_frame"]
            self.assertEqual(set(frames), {(r1.run_uid, "local"), (r2.run_uid, "local")})
            f2 = frames[(r2.run_uid, "local")]
            self.assertIs(frames[(r1.run_uid, "local")], f1)
            self.assertNotEqual(f1["hash"], f2["hash"])
            self.assertEqual((f1["rodada"]["K"], f2["rodada"]["K"]), (24, 12))
            self.assertEqual(f2["rodada"]["cenario"], "Segunda rodada")
            self.assertEqual(f2["resumo"]["custo_realizado_total_R"], r2.summary["mission"]["custo_realizado_total_R"])
            app.session_state["op_run_uid"] = r1.run_uid                 # voltar: o marco da primeira é o mesmo objeto
            app.run()
            self.assertIs(app.session_state["op_v2_frame"][(r1.run_uid, "local")], f1)
            # sessão NOVA (outro navegador/dia), ainda sem solver: mesmo marco, bit a bit
            nova = self.session(uid, "rodada", query={"run": r1.run_uid})
            g1 = nova.session_state["op_v2_frame"][(r1.run_uid, "local")]
            self.assertIsNot(g1, f1)
            self.assertEqual(g1, f1)
            self.assertEqual(TF.montar(MicrogridRegistry(self.dir).open(uid), r1)["intervalos"], f1["intervalos"])

    @unittest.skipUnless(U.SOLVER, "Pyomo/HiGHS não instalados")
    def test_estudo_arquivado_desenha_a_partitura_e_mantem_a_vista_classica(self):
        from seeds2.archive import exporter
        from seeds2.archive.store import ArchiveStore

        uid, st, run = U.missao_24h(self.dir, "Microrrede estudo 3D-B")
        pacote, _ = exporter.export_bytes(st, run.scenario_uid)
        outra = tempfile.mkdtemp(dir=self.dir)
        study = ArchiveStore(outra).import_package(pacote).study
        os.environ["SEEDS2_DATA_DIR"] = outra
        try:
            with mock.patch.object(X, "submit", side_effect=AssertionError("motor chamado no estudo")), \
                    mock.patch.dict(sys.modules, {"pyomo": None, "highspy": None}):
                ar = AppTest.from_file(str(APP_PATH), default_timeout=240)
                ar.query_params.update({"view": "arquivo", "tab": "estudo", "study": study.archive_uid, "srun": run.run_uid})
                ar.run()
                self.assertEqual(len(ar.exception), 0, [e.value for e in ar.exception])
                frames = ar.session_state["op_v2_frame"]
                self.assertEqual(list(frames), [(run.run_uid, study.archive_uid)])
                f = frames[(run.run_uid, study.archive_uid)]
                self.assertTrue(f["verificacao"]["ok"])
                self.assertEqual(f["intervalos"], TF.montar(st, run)["intervalos"])      # arquivo ≡ origem, bit a bit
                classica = [e for e in ar.expander if e.label.startswith("Vista clássica")]
                self.assertEqual(len(classica), 1)
                self.assertFalse(classica[0].proto.expanded)
                self.assertGreaterEqual(len(classica[0].get("plotly_chart")), 2)
        finally:
            os.environ["SEEDS2_DATA_DIR"] = self.dir

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
        self.assertFalse(any(e.label.startswith("Vista clássica") for e in app.expander))
        self.assertGreaterEqual(len(app.get("plotly_chart")), 1)


if __name__ == "__main__":
    unittest.main()
