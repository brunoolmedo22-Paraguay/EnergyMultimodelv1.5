"""Piso 2D-B na interface (AppTest): EXPORTAR RELATÓRIO PDF / DADOS EXCEL / FIGURAS na rodada local (Piso 2C) e na
rodada de um estudo arquivado (Piso 2D-A) numa instalação limpa, com o motor sabotado; documentos produzidos só sob
demanda; diagnóstico para rodada falha (sem figuras); estudo corrompido → erro legível sem documento.
"""
from __future__ import annotations

import io
import os
import sqlite3
import tempfile
import unittest
import zipfile
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

if AppTest is not None:
    from apptest_utils import APP_PATH

import orchestrator_runtime as RT
from seeds2.archive import exporter
from seeds2.archive.store import ArchiveStore
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.operation import runner
from seeds2_fixtures import v16_equivalent_config
from test_seeds2_piso2c import ready
from test_seeds2_piso2da import _dump

NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}
LABELS = ("EXPORTAR RELATÓRIO PDF", "EXPORTAR DADOS EXCEL", "EXPORTAR FIGURAS")


def _ok(tc, app):
    tc.assertEqual(len(app.exception), 0, [e.value for e in app.exception])


def _btn(app, label):
    return next(b for b in app.button if b.label == label)


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

    def engine_off(self):
        ps = [mock.patch.object(RT, "run_optimizer", side_effect=AssertionError("run_optimizer chamado")),
              mock.patch.object(RT, "build_exchange_package", side_effect=AssertionError("build_exchange_package chamado")),
              mock.patch.object(runner, "submit", side_effect=AssertionError("submit chamado"))]
        for p in ps:
            p.start()
            self.addCleanup(p.stop)

    def app(self, *, state: dict | None = None, query: dict | None = None) -> AppTest:
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=240)
        for k, v in (state or {}).items():
            app.session_state[k] = v
        for k, v in (query or {}).items():
            app.query_params[k] = v
        app.run()
        _ok(self, app)
        return app

    def click(self, app, label) -> AppTest:
        _btn(app, label).click().run()
        _ok(self, app)
        return app

    def assert_docs(self, app, run_uid: str, *, figures: bool = True):
        pdf = app.session_state[f"rx_{run_uid}_pdf"]
        self.assertTrue(pdf[1].startswith(b"%PDF"))
        self.assertTrue(pdf[0].endswith(".pdf"))
        xl = app.session_state[f"rx_{run_uid}_xlsx"]
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(xl[1])))
        if figures:
            fig = app.session_state[f"rx_{run_uid}_fig"]
            names = zipfile.ZipFile(io.BytesIO(fig[1])).namelist()
            self.assertIn("manifest.json", names)
            self.assertTrue(any(n.endswith(".svg") for n in names) and any(n.endswith(".png") for n in names))
        labels = [b.label for b in app.get("download_button")]
        self.assertIn("BAIXAR RELATÓRIO PDF", labels)
        self.assertIn("BAIXAR DADOS EXCEL", labels)
        if figures:
            self.assertIn("BAIXAR FIGURAS (PNG + SVG)", labels)


class RodadaLocalTest(_Base):
    def test_exportar_pdf_excel_figuras_da_rodada_local_sem_motor_e_sem_alterar(self):
        reg = MicrogridRegistry(self.dir)
        cfg = v16_equivalent_config("Industrial A")
        reg.create(cfg)
        uid = cfg["installation"]["uid"]
        st = reg.open(uid)
        sc = ready(st, name="Alta demanda")
        run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        before = _dump(st)
        self.engine_off()
        app = self.app(state={"mg_active_uid": uid, "seeds_route": {"view": "operacao", "tab": "rodada"},
                              "op_run_uid": run.run_uid})
        for lb in LABELS:
            self.assertFalse(_btn(app, lb).disabled)
        for k in ("pdf", "xlsx", "fig"):
            self.assertNotIn(f"rx_{run.run_uid}_{k}", app.session_state)                # nada gerado ao abrir
        self.assertIn("Documentos derivados", "\n".join(h.proto.body for h in app.get("html")).replace("<b>", "").replace("</b>", ""))
        for lb in LABELS:
            app = self.click(app, lb)
        self.assert_docs(app, run.run_uid)
        caps = "\n".join(c.value for c in app.caption)                                # C-04.2: precisão explicada
        self.assertIn("15 algarismos significativos", caps)
        self.assertIn(".seeds2study.zip", caps)
        self.assertTrue(any("mais de 15 algarismos" in w.value for w in app.warning))
        self.assertEqual(_dump(st), before)                                            # rodadas/cenários intactos
        self.assertEqual(len(st.list_runs()), 1)

    def test_rodada_falha_so_diagnostico_sem_figuras(self):
        reg = MicrogridRegistry(self.dir)
        cfg = v16_equivalent_config("Industrial A")
        reg.create(cfg)
        uid = cfg["installation"]["uid"]
        st = reg.open(uid)
        sc = ready(st, name="Alta demanda")
        with mock.patch.object(RT, "run_optimizer", side_effect=RuntimeError("solver sabotado")):
            run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual(run.state, "falhou")
        self.engine_off()
        app = self.app(state={"mg_active_uid": uid, "seeds_route": {"view": "operacao", "tab": "rodada"},
                              "op_run_uid": run.run_uid})
        self.assertTrue(_btn(app, "EXPORTAR FIGURAS").disabled)
        app = self.click(app, "EXPORTAR DIAGNÓSTICO PDF")
        name, data, *_ = app.session_state[f"rx_{run.run_uid}_pdf"]
        self.assertTrue(name.startswith("seeds2_diagnostico_"))
        self.assertTrue(data.startswith(b"%PDF"))
        app = self.click(app, "EXPORTAR DIAGNÓSTICO EXCEL")
        self.assertIn(f"rx_{run.run_uid}_xlsx", app.session_state)


class EstudoArquivadoTest(_Base):
    @classmethod
    def setUpClass(cls):
        cls._src = tempfile.TemporaryDirectory()
        reg = MicrogridRegistry(cls._src.name)
        cfg = v16_equivalent_config("Industrial A")
        reg.create(cfg)
        st = reg.open(cfg["installation"]["uid"])
        sc = ready(st, name="Alta demanda")
        cls.run_ = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        cls.pkg, _ = exporter.export_bytes(st, sc.scenario_uid)

    @classmethod
    def tearDownClass(cls):
        cls._src.cleanup()

    def open_study(self) -> tuple[AppTest, str]:
        uid = ArchiveStore(self.dir).import_package(self.pkg).study.archive_uid
        self.engine_off()
        app = self.app(query={"view": "arquivo", "tab": "estudo", "study": uid, "srun": self.run_.run_uid})
        self.assertEqual(MicrogridRegistry(self.dir).entries(), [])                    # instalação limpa
        return app, uid

    def test_exportar_da_rodada_arquivada_em_instalacao_limpa(self):
        app, uid = self.open_study()
        for lb in LABELS:
            app = self.click(app, lb)
        self.assert_docs(app, self.run_.run_uid)
        from pypdf import PdfReader

        txt = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(app.session_state[f"rx_{self.run_.run_uid}_pdf"][1])).pages)
        self.assertIn("Estudo arquivado", txt)
        self.assertIn(uid, txt)
        self.assertIn("R$ 88,32", txt)
        ok, problems = ArchiveStore(self.dir).verify(uid)
        self.assertTrue(ok, problems)

    def test_estudo_corrompido_erro_legivel_sem_documento(self):
        app, uid = self.open_study()
        con = sqlite3.connect(ArchiveStore(self.dir).path)
        h = con.execute("SELECT sha256 FROM study_resources WHERE archive_uid = ? AND path LIKE ?",
                        (uid, f"runs/{self.run_.run_uid}/data/saidas/despacho_ems.csv")).fetchone()[0]
        con.execute("DROP TRIGGER archive_blobs_immutable_u")
        con.execute("UPDATE archive_blobs SET content = ?, encoding = 'identity' WHERE sha256 = ?", (b"x", h))
        con.commit()
        con.close()
        app = self.click(app, "EXPORTAR DADOS EXCEL")
        self.assertNotIn(f"rx_{self.run_.run_uid}_xlsx", app.session_state)
        self.assertTrue(any("Nenhum documento foi gerado" in e.value for e in app.error))


if __name__ == "__main__":
    unittest.main()
