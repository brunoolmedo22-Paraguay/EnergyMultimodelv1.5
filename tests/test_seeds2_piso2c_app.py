"""Piso 2C — Estratégia EMS e Execução na interface (AppTest): etapas reais no painel, estratégia gravada no cenário
(função objetivo única identificada, sem seletor multiobjetivo), janela da missão, relatório de preparação, bloqueio
de cenário incompatível, execução em segundo plano, ausência de execução duplicada por recarga, reabertura da rodada
em nova sessão SEM chamar o otimizador e exclusão da microrrede com consentimento específico para as rodadas.

O AppTest não executa JavaScript: os gráficos são verificados pela especificação Plotly (dados vindos das séries
gravadas). Desenho real, tablet e reinício do servidor: ``tools/e2e/e2e_piso2c_execucao.js``.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

import numpy as np

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

if AppTest is not None:
    from apptest_utils import APP_PATH, botao, continuar

from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.operation import runner
from seeds2.operation import service
from seeds2.operation import strategy as SG
from seeds2_fixtures import v16_equivalent_config
from test_seeds2_piso2c import DUR, demand_candidate, mission_load, ready, set_states

NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}


def _ok(tc, app):
    tc.assertEqual(len(app.exception), 0, [e.value for e in app.exception])


def _html(app) -> str:
    return "\n".join(h.proto.body for h in app.get("html"))


def _texts(app) -> str:
    parts = [_html(app)] + [c.value for c in app.caption] + [w.value for w in app.warning] + \
            [e.value for e in app.error] + [m.value for m in app.markdown] + [c.label for c in app.checkbox]
    return "\n".join(parts).replace("\\", "")


def _charts(app) -> list[dict]:
    return [json.loads(c.proto.spec) for c in app.get("plotly_chart")]


def _arr(v) -> np.ndarray:
    """Valores de um traço Plotly (o Plotly 6 serializa arrays numpy como ``{dtype, bdata}`` em base64)."""
    if isinstance(v, dict) and "bdata" in v:
        import base64

        return np.frombuffer(base64.b64decode(v["bdata"]), dtype=np.dtype(v["dtype"])).astype(float)
    return np.asarray(v, dtype=float)


def _run_button(app):
    return next(b for b in app.button if b.label.startswith("▶ EXECUTAR CENÁRIO"))


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

    def reg(self) -> MicrogridRegistry:
        return MicrogridRegistry(self.dir)

    def make(self, name: str = "Microrrede UI 2C") -> tuple[str, object]:
        cfg = v16_equivalent_config(name)
        self.reg().create(cfg)
        uid = cfg["installation"]["uid"]
        return uid, self.reg().open(uid)

    def session(self, uid: str | None, tab: str | None = None, view: str = "operacao", extra: dict | None = None,
                query: dict | None = None) -> AppTest:
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=180)
        if uid:
            app.session_state["mg_active_uid"] = uid
            app.session_state["seeds_route"] = {"view": view, "tab": tab}
        for k, v in (extra or {}).items():
            app.session_state[k] = v
        for k, v in (query or {}).items():
            app.query_params[k] = v
        app.run()
        _ok(self, app)
        return app


class PainelTest(_Base):
    def test_quatro_etapas_reais_e_prontidao_pelo_preflight(self):
        uid, st = self.make()
        sc = ready(st)
        app = self.session(uid)
        labels = [b.label for b in app.button]
        for b in ("ABRIR INICIALIZAÇÃO", "ABRIR PREVISÕES", "ABRIR ESTRATÉGIA EMS", "ABRIR EXECUÇÃO"):
            self.assertIn(b, labels)
        self.assertFalse([l for l in labels if "EXECUTAR" in l.upper()], labels)    # executar só dentro da etapa 04
        html = _html(app)
        self.assertIn(f"Pronto para executar (v{sc.version})", html)
        self.assertEqual(html.count("Não implementado"), 0)
        botao(app, "ABRIR EXECUÇÃO").click().run()
        app = continuar(app, 180)
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"]["tab"], "execucao")
        self.assertIn("Cenário — editável", _html(app))
        self.assertIn("Rodada — imutável", _html(app))


class EstrategiaUITest(_Base):
    def test_definir_padrao_salvar_como_nova_versao(self):
        uid, st = self.make()
        sc = service.create(st, name="Sem estratégia")
        app = self.session(uid, "estrategia")
        html = _html(app)
        self.assertIn(SG.OBJECTIVE_LABEL, html)
        self.assertIn("sem seletor multiobjetivo", html)
        self.assertFalse([w for w in list(app.selectbox) + list(app.radio) if "objetivo" in w.label.lower()])
        botao(app, "DEFINIR COM OS VALORES PADRÃO DO MOTOR V1.6").click().run()
        app = continuar(app, 180)
        _ok(self, app)
        radio = next(r for r in app.radio if r.label == "Algoritmo")
        self.assertEqual(radio.options, list(SG.ALGORITHMS.values()))                 # só algoritmos existentes
        radio.set_value(0).run()
        next(n for n in app.number_input if n.label.startswith("Horizonte móvel N")).set_value(5).run()
        botao(app, "SALVAR CENÁRIO").click().run()
        app = continuar(app, 180)
        _ok(self, app)
        saved = st.get_scenario(sc.scenario_uid)
        self.assertEqual(saved.version, 2)
        expected = SG.default_strategy()
        expected.update(algorithm=0, N=5)
        self.assertEqual(saved.document["ems_strategy"], expected)
        self.assertIsNone(st.get_scenario(sc.scenario_uid, 1).document["ems_strategy"])


class ExecucaoUITest(_Base):
    def test_cenario_incompativel_nao_pode_ser_executado(self):
        uid, st = self.make()
        ready(st, soc=15.0)                                                  # gravável, mas fora dos limites efetivos
        app = self.session(uid, "execucao")
        self.assertTrue(_run_button(app).disabled)
        txt = _texts(app)
        self.assertIn("NÃO pode ser executado", txt)
        self.assertIn("restrição EFETIVA", txt)
        self.assertIn("o cenário tem incompatibilidades", txt)
        self.assertEqual(st.list_runs(), [])

    def test_definir_janela_a_partir_do_horizonte_disponivel(self):
        uid, st = self.make()
        sc = service.create(st, name="Sem janela")
        import copy
        doc = copy.deepcopy(sc.document)
        set_states(doc)
        dem = demand_candidate(doc["inventory_ref"], mission_load())
        doc["forecasts"] = {"demand": dem.entry}
        service.save(st, doc, sc.version, new_blobs=dem.blobs)
        app = self.session(uid, "execucao")
        self.assertIn("Horizonte disponível (cobertura comum)", _html(app))
        botao(app, "DEFINIR JANELA DA MISSÃO").click().run()
        app = continuar(app, 180)
        _ok(self, app)
        m = app.session_state["op_work"]["mission"]
        self.assertEqual((m["start"], m["timezone"], m["duration_min"]), ("2026-09-05T12:00:00", "America/Sao_Paulo", DUR))
        self.assertTrue(_run_button(app).disabled)                            # alterações não salvas
        self.assertIn("há alterações não salvas", _texts(app))

    def test_executar_em_segundo_plano_reabrir_sem_recalcular_e_sem_duplicar(self):
        uid, st = self.make()
        sc = ready(st)
        app = self.session(uid, "execucao")
        b = _run_button(app)
        self.assertFalse(b.disabled)
        self.assertIn(f"VERSÃO {sc.version}", b.label)
        b.click().run()
        _ok(self, app)
        runs = st.list_runs()
        self.assertEqual(len(runs), 1)
        self.assertTrue(runner.wait(runs[0].run_uid, 300))
        # "recarga": nova execução do script com o mesmo estado — nenhuma rodada nova
        app = continuar(app, 180)
        _ok(self, app)
        self.assertEqual(len(st.list_runs()), 1)
        run = st.get_run(runs[0].run_uid)
        self.assertEqual(run.state, "concluida", run.error)
        self.assertIn(run.run_uid[:8], _html(app))                            # histórico
        # reabrir a rodada numa sessão NOVA (servidor reiniciado = sem estado em memória), sem chamar o otimizador
        with mock.patch("orchestrator_runtime.run_optimizer", side_effect=AssertionError("otimizador chamado")), \
                mock.patch("orchestrator_runtime.build_exchange_package", side_effect=AssertionError("modelos chamados")):
            rv = self.session(uid, "rodada", query={"run": run.run_uid})
        html = _html(rv)
        self.assertIn("Rodada · imutável", html)
        self.assertIn(f"R$ {run.summary['custo_total_rs']:,.2f}".replace(",", "§").replace(".", ",").replace("§", "."), html)
        self.assertIn("Energia atendida", html)
        self.assertIn("H₂ consumido", html)
        specs = _charts(rv)
        power = next(s for s in specs if "Demanda e potência por fonte" in s["layout"]["title"]["text"])
        out = runner.load_csv(st, run.run_uid, "saidas/despacho_ems.csv")
        dem = next(t for t in power["data"] if t["name"] == "Demanda")
        np.testing.assert_allclose(_arr(dem["y"]), out["P_carga_kW"].to_numpy())
        fc = next(t for t in power["data"] if t["name"] == "H₂ / PEMFC")
        np.testing.assert_allclose(_arr(fc["y"]), out["P_fc_kW"].to_numpy())
        soc = next(s for s in specs if "Estado de carga" in s["layout"]["title"]["text"])
        np.testing.assert_allclose(_arr(soc["data"][0]["y"]), 100 * out["SOC_bateria"].to_numpy())
        self.assertIn("Procedência da rodada (manifesto imutável)", [e.label for e in rv.expander])
        self.assertEqual(len(st.list_runs()), 1)

    def test_edicao_posterior_nao_altera_rodada_e_nova_rodada_usa_nova_versao(self):
        uid, st = self.make()
        sc = ready(st)
        first = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        import copy
        doc = copy.deepcopy(sc.document)
        doc["ems_strategy"]["seed"] = 11
        v2 = service.save(st, doc, sc.version)
        rv = self.session(uid, "rodada", extra={"op_run_uid": first.run_uid})
        self.assertIn(f"esta rodada permanece vinculada à versão {sc.version}", _texts(rv))
        app = self.session(uid, "execucao")
        self.assertIn(f"VERSÃO {v2.version}", _run_button(app).label)

    def test_rodada_falha_mostra_motivo_sem_resultados(self):
        uid, st = self.make()
        sc = ready(st, fc_power=195.0)                                        # rampa ativa no 1º passo
        run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual(run.state, "falhou")
        rv = self.session(uid, "rodada", extra={"op_run_uid": run.run_uid})
        txt = _texts(rv)
        self.assertIn("Rodada falhou", txt)
        self.assertIn("otimizador NÃO foi chamado", txt)
        self.assertEqual(_charts(rv), [])


class ExclusaoComRodadasTest(_Base):
    def test_dialogo_informa_rodadas_e_exige_consentimento_especifico(self):
        uid, st = self.make("Com rodadas")
        sc = ready(st)
        runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        with mock.patch.dict(os.environ, {"SEEDS2_DEV_MODE": "1"}):
            app = self.session(None)
            next(b for b in app.button if b.key == f"g_del_{uid}").click().run()
            _ok(self, app)
            html = _html(app)
            self.assertIn("Rodadas científicas arquivadas (Piso 2C)</td><td><b>1</b>", html)
            txt = _texts(app)
            self.assertIn("1 rodada(s) científica(s) arquivada(s)", txt)
            self.assertIn("rodadas científicas executadas e seus resultados (Piso 2C", txt)
            next(t for t in app.text_input if t.label.startswith("Digite o nome exato")).input("Com rodadas").run()
            next(c for c in app.checkbox if c.label.startswith("Entendo que os 1 cenário(s)")).check().run()
            self.assertTrue(botao(app, "EXCLUIR DEFINITIVAMENTE").disabled)    # cenários confirmados; rodadas não
            ck = next(c for c in app.checkbox if c.label.startswith("Entendo que as 1 rodada(s) científica(s)"))
            ck.check().run()
            self.assertFalse(botao(app, "EXCLUIR DEFINITIVAMENTE").disabled)
            botao(app, "EXCLUIR DEFINITIVAMENTE").click().run()
            _ok(self, app)
        self.assertFalse(self.reg().exists(uid))
        self.assertFalse(self.reg().dir_for(uid).exists())


if __name__ == "__main__":
    unittest.main()
