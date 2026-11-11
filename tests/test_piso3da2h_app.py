"""Piso 3D-A2-H na interface (AppTest): declarações PEMFC vazias na etapa 03, bloqueio B04 explicado na etapa 04 (política
pendente) e rodada híbrida com PEMFC reaberta em sessão NOVA sem modelos nem solver (aprovação B04 SIMULADA no teste).
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

import piso3da2h_util as H  # noqa: E402
import piso3da2r_util as R  # noqa: E402
from ems_v2.milp.ambiente import verificar_ambiente  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import execucao as X  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.operation import service as SV  # noqa: E402

SOLVER = bool(verificar_ambiente().get("disponivel"))
NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}


def _texts(app) -> str:
    parts = ["\n".join(h.proto.body for h in app.get("html"))] + [c.value for c in app.caption] + \
            [w.value for w in app.warning] + [e.value for e in app.error] + [m.value for m in app.markdown]
    return "\n".join(parts).replace("\\", "")


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class PemfcUiTest(unittest.TestCase):
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
        cfg = H.config_pemfc("Microrrede UI 3D-A2-H", **kw)
        MicrogridRegistry(self.dir).create(cfg)
        uid = cfg["installation"]["uid"]
        return uid, MicrogridRegistry(self.dir).open(uid)

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

    def test_declaracoes_pemfc_comecam_vazias(self):
        uid, st = self.make()
        sc = SV.create(st, name="Cenário PEMFC de interface")
        app = self.session(uid, "estrategia")
        next(r for r in app.radio if (r.key or "").endswith("_motor")).set_value(E.MOTOR_V2).run()
        app = continuar(app, 120)
        botao(app, "CRIAR DECLARAÇÃO DA ESTRATÉGIA V2 (CAMPOS EM BRANCO)").click().run()
        app = continuar(app, 120)
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        self.assertIn("PEMFC / H₂: inicialização física e commitment", _texts(app))
        fc = [n for n in app.number_input if "_fc_" in (n.key or "")]
        self.assertTrue(fc and all(n.value is None for n in fc))                 # nada pré-preenchido
        botao(app, "SALVAR CENÁRIO").click().run()
        b = st.get_scenario(sc.scenario_uid).document[E.CHAVE_BLOCO]
        self.assertEqual(b["format_version"], 3)
        x = next(iter(b["pemfc"].values()))
        self.assertIsNone(x["p_min_kW"]) and self.assertIsNone(x["condicoes"]["temperatura_stack_K"])

    def test_execucao_bloqueada_com_politica_pendente(self):
        uid, st = self.make()
        H.criar_cenario_pemfc(st)
        with H.politica_pendente_no_teste():                               # REVOGAÇÃO simulada da aprovação B04
            txt = _texts(self.session(uid, "execucao"))
        self.assertIn("AGUARDANDO APROVAÇÃO", txt)
        self.assertIn("curva q(P) do modelo físico", txt)
        self.assertEqual(st.list_runs(), [])

    @unittest.skipUnless(SOLVER, "Pyomo/HiGHS não instalados")
    def test_rodada_com_pemfc_reaberta_sem_modelos_nem_solver(self):
        uid, st = self.make(fv=True, eolica=True)
        clima = lambda doc: R.clima_tabela(doc, {"ghi_W_m2": [0, 0, 0, 0, 0, 0, 100, 350, 600, 800, 950, 1000],  # noqa: E731
                                                 "temperature_C": [20.0] * 12,
                                                 "wind_speed_m_s": [2, 3, 9, 10, 11, 12, 12, 10, 4, 3, 2.5, 2]})
        sc = H.criar_cenario_pemfc(st, demanda_kW=40.0, renov=True, clima=clima, pemfc_kw={"preco": 10.0},
                                   mutar=lambda doc: doc[E.CHAVE_BLOCO]["pcc"].update(limite_importacao_kW=25.0))
        run = X.submit(st, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
        self.assertEqual(run.state, "concluida", run.error)
        falha = AssertionError("modelo/curva/motor chamado ao reabrir")
        with mock.patch.object(X, "submit", side_effect=falha), \
                mock.patch("integracao_v2.curva_h2.obter_curva", side_effect=falha), \
                mock.patch("integracao_v2.pemfc_dinamica.verificar_despacho", side_effect=falha), \
                mock.patch("integracao_v2.montagem.construir_missao", side_effect=falha), \
                mock.patch.dict(sys.modules, {"pyomo": None, "highspy": None}):
            rv = self.session(uid, "rodada", query={"run": run.run_uid})
            txt = _texts(rv)
            self.assertIn("PEMFC (unidade)", txt)
            self.assertIn("coerente", txt)
            # aceitação SEPARADA (auditoria do PR #23, B): algébrico × dinâmico × físico
            self.assertIn("Critério de aceitação", txt)
            self.assertIn("APROVADO", txt) and self.assertIn("COERENTE", txt)
            self.assertIn("NÃO VALIDADO", txt)
            self.assertNotIn("DINAMICAMENTE INCOERENTE", txt)
            self.assertTrue(any(e.label.startswith("✓ Evidência verificada") for e in rv.expander))
            specs = [json.loads(c.proto.spec) for c in rv.get("plotly_chart")]
            pot = next(s for s in specs if "Demanda × atendimento" in s["layout"]["title"]["text"])
            self.assertTrue(any(t["name"].startswith("PEMFC ") for t in pot["data"]))

    @unittest.skipUnless(SOLVER, "Pyomo/HiGHS não instalados")
    def test_rodada_dinamicamente_incoerente_e_exibida_como_tal(self):
        """Partida fria forçada além do preflight (bloqueio a priori desligado SÓ neste teste): a interface mostra a
        aprovação algébrica separada da INCOERÊNCIA dinâmica e nunca apresenta a rodada como validada."""
        from integracao_v2 import pemfc_dinamica as DY
        uid, st = self.make()
        sc = H.criar_cenario_pemfc(st, demanda_kW=40.0, pemfc_kw={"t_amb": 0.0, "preco": 10.0},
                                   mutar=lambda doc: doc[E.CHAVE_BLOCO]["pcc"].update(limite_importacao_kW=25.0))
        with mock.patch.object(DY, "admissibilidade", return_value=[]):
            run = X.submit(st, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
        self.assertEqual(run.state, "concluida", run.error)
        txt = _texts(self.session(uid, "rodada", query={"run": run.run_uid}))
        self.assertIn("DINAMICAMENTE INCOERENTE", txt)
        self.assertIn("NÃO representa operação executável", txt)
        self.assertIn("INCOERENTE", txt) and self.assertIn("NÃO VALIDADO", txt)
