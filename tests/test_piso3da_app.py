"""Piso 3D-A na interface (AppTest): seleção explícita do motor na etapa 03, declaração V2 em branco, preflight V2 que
bloqueia sem executar, execução real em segundo plano, reabertura da rodada em sessão NOVA sem otimizador (local e no
Arquivo Científico) e V1.6 inalterado para cenários que não selecionam o V2.

O AppTest não executa JavaScript: gráficos pela especificação Plotly. Navegador real: ``tools/e2e/e2e_piso3da_v2.js``.
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

import piso3da_util as U  # noqa: E402
from ems_v2.milp.ambiente import verificar_ambiente  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import execucao as X  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from seeds2.archive import exporter  # noqa: E402
from seeds2.archive.store import ArchiveStore  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.operation import runner  # noqa: E402
from seeds2.operation import service as SV  # noqa: E402

SOLVER = bool(verificar_ambiente().get("disponivel"))
NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}


def _ok(tc, app):
    tc.assertEqual(len(app.exception), 0, [e.value for e in app.exception])


def _texts(app) -> str:
    parts = ["\n".join(h.proto.body for h in app.get("html"))] + [c.value for c in app.caption] + \
            [w.value for w in app.warning] + [e.value for e in app.error] + [m.value for m in app.markdown]
    return "\n".join(parts).replace("\\", "")


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
        cfg = U.config_bateria("Microrrede UI 3D-A", **kw)
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


class EstrategiaTest(_Base):
    def test_motor_v16_por_omissao_e_selecao_explicita_do_v2(self):
        uid, st = self.make()
        sc = SV.create(st, name="Cenário de interface")
        app = self.session(uid, "estrategia")
        radio = next(r for r in app.radio if (r.key or "").endswith("_motor"))
        self.assertEqual(radio.value, E.MOTOR_V16)                     # nada muda para quem não escolhe o V2
        self.assertIn("V1.6", _texts(app))
        radio.set_value(E.MOTOR_V2).run()
        app = continuar(app, 120)
        _ok(self, app)
        txt = _texts(app)
        self.assertIn("motor V2 experimental", txt)
        self.assertIn("Simulação OFFLINE", txt)
        botao(app, "CRIAR DECLARAÇÃO DA ESTRATÉGIA V2 (CAMPOS EM BRANCO)").click().run()
        app = continuar(app, 120)
        _ok(self, app)
        txt = _texts(app)
        self.assertIn("declaração(ões) ausente(s)", txt)
        vazios = [n for n in app.number_input if "_b_" in (n.key or "")]
        self.assertTrue(vazios and all(n.value is None for n in vazios))   # nenhum parâmetro físico pré-preenchido
        self.assertEqual(st.get_scenario(sc.scenario_uid).version, sc.version)   # nada gravado sem SALVAR
        botao(app, "SALVAR CENÁRIO").click().run()
        novo = st.get_scenario(sc.scenario_uid)
        self.assertEqual(novo.version, sc.version + 1)
        self.assertEqual(novo.document[E.CHAVE_MOTOR], E.MOTOR_V2)
        b = novo.document[E.CHAVE_BLOCO]
        bid = U.bateria_id(novo.document)
        self.assertTrue(all(b["baterias"][bid][c] is None for c in E.CAMPOS_BATERIA))
        self.assertIsNone(b["pcc"]["modo"])


class ExecucaoTest(_Base):
    def test_preflight_v2_bloqueia_e_nao_executa(self):
        uid, st = self.make()

        def mutar(doc):
            doc[E.CHAVE_BLOCO]["pcc"]["tarifa_importacao_R_kWh"] = None
        U.criar_cenario_v2(st, mutar=mutar)
        app = self.session(uid, "execucao")
        txt = _texts(app)
        self.assertIn("NÃO pode ser executado pelo motor V2", txt)
        self.assertIn("Tarifa de importação não declarada", txt)
        b = next(x for x in app.button if x.label.startswith("▶ EXECUTAR MISSÃO V2"))
        self.assertTrue(b.disabled)
        self.assertFalse(any(x.label.startswith("▶ EXECUTAR CENÁRIO") for x in app.button))   # sem botão do motor V1.6
        self.assertEqual(st.list_runs(), [])

    def test_equipamento_nao_representavel_explicado(self):
        from seeds2.microgrid import config as C
        uid, st = self.make(extras=[C.new_equipment("thermal", "Gerador diesel", tag="TER-01", params={
            "dynamic": "local_generator", "pmax_kW": 60.0, "pmin_kW": 15.0, "cvu_rs_MWh": 1200.0, "startup_cost_rs": 40.0})])
        U.criar_cenario_v2(st)
        txt = _texts(self.session(uid, "execucao"))
        self.assertIn("NÃO é representável pelo motor V2", txt)
        self.assertIn("M19", txt)

    @unittest.skipUnless(SOLVER, "Pyomo/HiGHS não instalados (pip install -r requirements-ems_v2.txt)")
    def test_executar_reabrir_sem_otimizador_e_consultar_no_arquivo(self):
        uid, st = self.make()
        sc = U.criar_cenario_v2(st)
        app = self.session(uid, "execucao")
        txt = _texts(app)
        self.assertIn("Apto para o motor V2", txt)
        self.assertIn("Matriz fonte → transformação → validação → registro → vista (o que chega ao motor)",
                      [e.label for e in app.expander])
        b = next(x for x in app.button if x.label.startswith("▶ EXECUTAR MISSÃO V2"))
        self.assertFalse(b.disabled)
        self.assertIn(f"VERSÃO {sc.version}", b.label)
        b.click().run()
        _ok(self, app)
        runs = st.list_runs()
        self.assertEqual(len(runs), 1)
        self.assertTrue(runner.wait(runs[0].run_uid, 300))
        app = continuar(app, 180)                                       # "recarga": nenhuma rodada nova
        _ok(self, app)
        self.assertEqual(len(st.list_runs()), 1)
        run = st.get_run(runs[0].run_uid)
        self.assertEqual(run.state, "concluida", run.error)
        self.assertIn("custo realizado R$ 50,20", _texts(app))           # histórico rotulado pelo motor
        # ---- reabrir em sessão NOVA: runner, montagem do controlador e solver sabotados
        falha = AssertionError("o motor V2 foi chamado ao reabrir")
        with mock.patch.object(X, "submit", side_effect=falha), mock.patch.object(X, "_executar", side_effect=falha), \
                mock.patch("integracao_v2.montagem.construir_missao", side_effect=falha), \
                mock.patch("orchestrator_runtime.run_optimizer", side_effect=falha), \
                mock.patch.dict(sys.modules, {"pyomo": None, "highspy": None}):
            rv = self.session(uid, "rodada", query={"run": run.run_uid})
            txt = _texts(rv)
            self.assertIn("Rodada · imutável", txt)
            self.assertIn("Motor V2 experimental", txt)
            self.assertIn("R$ 50,20", txt)
            self.assertIn("Custo REALIZADO", txt)
            rotulos = [e.label for e in rv.expander]
            self.assertTrue(any(r.startswith("✓ Evidência verificada") for r in rotulos), rotulos)
            specs = [json.loads(c.proto.spec) for c in rv.get("plotly_chart")]
            pot = next(s for s in specs if "Demanda × atendimento" in s["layout"]["title"]["text"])
            self.assertIn("Importação da rede (realizada)", [t["name"] for t in pot["data"]])
            self.assertEqual(len(rv.get("download_button")), len(RG.OBRIGATORIOS))
            # ---- Arquivo Científico de OUTRA instalação: mesma evidência, sem microrrede local
            pacote, _ = exporter.export_bytes(st, sc.scenario_uid)
            outra = tempfile.mkdtemp(dir=self.dir)
            study = ArchiveStore(outra).import_package(pacote).study
            os.environ["SEEDS2_DATA_DIR"] = outra
            ar = AppTest.from_file(str(APP_PATH), default_timeout=180)
            ar.query_params.update({"view": "arquivo", "tab": "estudo", "study": study.archive_uid, "srun": run.run_uid})
            ar.run()
            _ok(self, ar)
            txt = _texts(ar)
            self.assertIn("R$ 50,20", txt)
            self.assertIn("Motor V2 experimental", txt)
            self.assertTrue(any(e.label.startswith("✓ Evidência verificada") for e in ar.expander))
        self.assertEqual(len(st.list_runs()), 1)
