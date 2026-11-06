"""Piso 2B — Previsões e Dados na interface (AppTest): abertura pelo Centro de Operação, perfis manual / CSV /
sintético / referência, pré-visualização gráfica com os dados corretos, separação entre perfil salvo e entrada
pendente, gravação como nova versão, reabertura em nova sessão, CSV malformado, unidade não confirmada, conflito
entre sessões com o pendente preservado, troca de microrrede, blob corrompido e Inicialização sem regressão.

O AppTest não executa JavaScript nem desenha os gráficos: verifica-se a ESPECIFICAÇÃO Plotly enviada ao navegador
(dados, eixos, títulos). O desenho real, zoom e tablet são verificados no E2E (``tools/e2e/e2e_piso2b_previsoes.js``).
"""
from __future__ import annotations

import copy
import json
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

if AppTest is not None:
    from apptest_utils import APP_PATH, botao, continuar

from seeds2.microgrid import config as C
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.operation import forecasts as F
from seeds2.operation import service
from seeds2_fixtures import v16_equivalent_config

NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}
FAKE = ("EXECUTAR", "RODAR", "OTIMIZAR", "ESTRATÉGIA", "ESTRATEGIA", "GERAR PREVIS", "INICIAR OPERA")


def _ok(tc, app):
    tc.assertEqual(len(app.exception), 0, [e.value for e in app.exception])


def _html(app) -> str:
    return "\n".join(h.proto.body for h in app.get("html"))


def _by_key(items, key: str):
    return next(w for w in items if w.key == key)


def _by_suffix(items, suffix: str):
    return next(w for w in items if (w.key or "").endswith(suffix))


def _charts(app) -> list[dict]:
    return [json.loads(c.proto.spec) for c in app.get("plotly_chart")]


def _chart(app, title_part: str) -> dict:
    for spec in _charts(app):
        if title_part in spec["layout"]["title"]["text"]:
            return spec
    raise AssertionError(f"Gráfico {title_part!r} ausente: {[s['layout']['title']['text'][:80] for s in _charts(app)]}")


def _ys(spec: dict, name_part: str) -> list[float]:
    tr = next(t for t in spec["data"] if name_part in t.get("name", ""))
    return [y for y in tr["y"] if y is not None]


def _climate_csv(n: int = 13) -> bytes:
    t = pd.date_range("2026-09-01 08:00", periods=n, freq="10min")
    h = t.hour + t.minute / 60
    df = pd.DataFrame({"timestamp": t.strftime("%Y-%m-%d %H:%M"), "GHI": np.round(900 * np.sin(np.pi * (h - 6) / 12), 1),
                       "temperatura_C": np.round(24 + 0.1 * np.arange(n), 2)})
    return df.to_csv(index=False).encode()


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

    def make(self, name: str) -> str:
        cfg = v16_equivalent_config(name)
        MicrogridRegistry(self.dir).create(cfg)
        return cfg["installation"]["uid"]

    def store(self, uid: str):
        return MicrogridRegistry(self.dir).open(uid)

    def session(self, uid: str, tab: str | None = "previsoes", timeout: float = 120) -> AppTest:
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=timeout)
        app.session_state["mg_active_uid"] = uid
        app.session_state["seeds_route"] = {"view": "operacao", "tab": tab}
        app.run()
        _ok(self, app)
        return app

    def with_scenario(self, name: str = "MG") -> tuple[str, str]:
        uid = self.make(name)
        sc = service.create(self.store(uid), name="Cenário de previsões")
        return uid, sc.scenario_uid

    def tab(self, app: AppTest, slot: str) -> AppTest:
        """Seleciona a aba (estado da chave ``opw_fc_tab``, como o clique do usuário)."""
        from seeds2.ui.forecasts_ui import TAB_KEY, TAB_LABELS

        app.session_state[TAB_KEY] = TAB_LABELS[slot]
        app.run()
        _ok(self, app)
        return app

    def source(self, app: AppTest, slot: str, src: str) -> AppTest:
        if slot == "climate" and not any(r.key == "opw_fc_src_climate" for r in app.radio):
            app = self.tab(app, slot)
        _by_key(app.radio, f"opw_fc_src_{slot}").set_value(src).run()
        _ok(self, app)
        return app

    def incorporate(self, app: AppTest, slot: str) -> AppTest:
        b = _by_key(app.button, f"opw_fc_inc_{slot}")
        self.assertFalse(b.disabled)
        b.click().run()
        _ok(self, app)
        return continuar(app, 120)

    def save(self, app: AppTest) -> AppTest:
        b = _by_key(app.button, "op_save")
        self.assertFalse(b.disabled)
        b.click().run()
        _ok(self, app)
        return continuar(app, 120)


class PrevisoesNavegacaoTest(_Base):
    def test_etapa_previsoes_aberta_pelo_centro_sem_controles_ficticios(self):
        uid, _ = self.with_scenario()
        app = self.session(uid, tab=None)
        self.assertIn("ABRIR PREVISÕES", [b.label for b in app.button])
        botao(app, "ABRIR PREVISÕES").click().run()
        _ok(self, app)
        app = continuar(app, 120)
        self.assertEqual(app.session_state["seeds_route"], {"view": "operacao", "tab": "previsoes"})
        self.assertEqual([t.label for t in app.tabs], ["Demanda elétrica (kW)", "Clima — variáveis meteorológicas"])
        labels = [b.label.upper() for b in app.button]
        self.assertFalse([l for l in labels if any(f in l for f in FAKE)], labels)
        html = _html(app)
        self.assertIn("Previsões e Dados", html)
        self.assertIn("ainda não é executado", "\n".join(m.value for m in app.markdown) + html)
        app = self.tab(app, "climate")
        html = _html(app)
        self.assertIn("Irradiância global horizontal (GHI)", html)              # variáveis da FV instalada
        self.assertNotIn("Velocidade do vento</td>", html)                     # sem eólica: não é pedida
        self.assertIn("Solar fotovoltaica: Arranjo FV 1, Arranjo FV 2", html)
        # etapas futuras continuam sem controles no painel
        app = self.session(uid, tab=None)
        self.assertGreaterEqual(_html(app).count("Não implementado"), 2)


class PrevisoesFluxoTest(_Base):
    def test_demanda_manual_colada_preview_salvar_e_reabrir(self):
        uid, sc = self.with_scenario()
        app = self.session(uid)
        k = "opw_fc_demand_manual"
        _by_key(app.text_input, f"{k}_start").input("2026-09-01 10:00")
        _by_key(app.number_input, f"{k}_n").set_value(6)
        _by_key(app.button, f"{k}_gen").click().run()
        app = continuar(app, 120)
        _ok(self, app)
        self.assertEqual(len(app.session_state["op_fcs_tbl_demand"]), 6)
        _by_key(app.text_area, f"{k}_paste").input("100\n110,5\n120\n150\n130\n125")
        _by_key(app.button, f"{k}_apply").click().run()
        app = continuar(app, 120)
        _ok(self, app)
        spec = _chart(app, "PRÉ-VISUALIZAÇÃO")
        self.assertEqual(_ys(spec, "dados originais"), [100.0, 110.5, 120.0, 150.0, 130.0, 125.0])
        self.assertEqual(spec["layout"]["yaxis"]["title"]["text"], "Potência demandada (kW)")
        self.assertIn("Pendente — não incorporada", _html(app))
        app = self.incorporate(app, "demand")
        self.assertIn("Incorporado nesta sessão — não salvo", _html(app))
        self.assertNotIn("op_fcs_tbl_demand", app.session_state)               # editor limpo após incorporar
        app = self.save(app)
        cur = self.store(uid).get_scenario(sc)
        self.assertEqual(cur.version, 2)
        e = cur.document["forecasts"]["demand"]
        self.assertEqual((e["source_type"], e["n_points"], e["t0"]), ("manual", 6, "2026-09-01T10:00:00"))
        # reabertura numa sessão nova (equivale a fechar e voltar): as mesmas curvas
        app2 = self.session(uid)
        self.assertIn(f"Salvo · v{cur.version}", _html(app2))
        self.assertEqual(_ys(_chart(app2, "perfil do cenário"), "dados originais"), [100.0, 110.5, 120.0, 150.0, 130.0, 125.0])

    def test_csv_climatico_mapeamento_unidade_e_procedencia(self):
        uid, sc = self.with_scenario()
        app = self.session(uid)
        app = self.source(app, "climate", "csv")
        up = next(u for u in app.file_uploader if (u.key or "").startswith("opw_fc_climate_csv_up"))
        data = _climate_csv()
        up.set_value(("clima.csv", data, "text/csv")).run()
        _ok(self, app)
        # GHI/temperatura detectadas; unidade da GHI não está no cabeçalho → precisa ser confirmada
        inc = _by_key(app.button, "opw_fc_inc_climate")
        self.assertTrue(inc.disabled)
        self.assertIn("confirme a unidade", _html(app))
        _by_suffix(app.selectbox, "_u_ghi_W_m2_ghi").set_value("W/m²").run()
        _ok(self, app)
        self.assertFalse(_by_key(app.button, "opw_fc_inc_climate").disabled)
        spec = _chart(app, "PRÉ-VISUALIZAÇÃO")
        self.assertEqual(_ys(spec, "GHI"), [float(x) for x in pd.read_csv(pd.io.common.BytesIO(data))["GHI"]])
        self.assertEqual(spec["layout"]["yaxis"]["title"]["text"], "W/m²")
        self.assertEqual(spec["layout"]["yaxis2"]["title"]["text"], "°C")       # painel próprio por grandeza
        _by_suffix(app.selectbox, "csv_prov").set_value("medido").run()
        app = self.incorporate(app, "climate")
        app = self.save(app)
        e = self.store(uid).get_scenario(sc).document["forecasts"]["climate"]
        self.assertEqual((e["source_type"], e["provenance"], e["variables"]), ("csv", "medido", ["ghi_W_m2", "temperature_C"]))
        self.assertEqual(self.store(uid).get_blob(e["blob"]), data)              # arquivo original preservado
        self.assertEqual(e["mapping"]["columns"]["ghi_W_m2"], {"column": "GHI", "unit": "W/m²"})

    def test_sintetico_e_referencia_pendente_nunca_mostrado_como_atual(self):
        uid, sc = self.with_scenario()
        app = self.session(uid)
        app = self.source(app, "demand", "sintetico")
        _by_key(app.selectbox, "opw_fc_demand_sintetico_gen").set_value("demanda_constante").run()
        _by_key(app.number_input, "opw_fc_demand_sintetico_v").set_value(77.0).run()
        _by_key(app.number_input, "opw_fc_demand_sintetico_dur").set_value(2.0).run()
        _ok(self, app)
        self.assertIn("Perfil SINTÉTICO hipotético", "\n".join(m.value for m in app.markdown) + _html(app))
        app = self.incorporate(app, "demand")
        app = self.save(app)
        self.assertEqual(set(_ys(_chart(app, "perfil do cenário"), "dados originais")), {77.0})
        # nova fonte (referência walk-forward): a pré-visualização mostra a NOVA curva; o atual continua o salvo
        app = self.source(app, "demand", "referencia")
        _by_key(app.selectbox, "opw_fc_demand_referencia_ds").set_value("walkforward").run()
        _ok(self, app)
        self.assertEqual(set(_ys(_chart(app, "perfil do cenário"), "dados originais")), {77.0})
        pv = _ys(_chart(app, "PRÉ-VISUALIZAÇÃO"), "dados originais")
        self.assertNotIn(77.0, pv)
        self.assertIn("não é medição desta instalação", "\n".join(m.value for m in app.markdown) + _html(app))
        self.assertIn("SUBSTITUIR NO CENÁRIO", [b.label for b in app.button])
        app = self.incorporate(app, "demand")
        app = self.save(app)
        hist = self.store(uid).scenario_history(sc)
        self.assertEqual([h["version"] for h in hist], [3, 2, 1])
        self.assertEqual(self.store(uid).get_scenario(sc, 2).document["forecasts"]["demand"]["source_type"], "sintetico")
        e = self.store(uid).get_scenario(sc).document["forecasts"]["demand"]
        self.assertEqual((e["source_type"], e["provenance"]), ("referencia", "referencia"))

    def test_csv_malformado_recusado_sem_excecao(self):
        uid, _ = self.with_scenario()
        app = self.session(uid)
        app = self.source(app, "demand", "csv")
        up = next(u for u in app.file_uploader if (u.key or "").startswith("opw_fc_demand_csv_up"))
        up.set_value(("ruim.csv", b"apenas_uma_coluna\n1\n2\n", "text/csv")).run()
        _ok(self, app)
        self.assertTrue(any("Arquivo recusado" in e.value for e in app.error))
        self.assertTrue(_by_key(app.button, "opw_fc_inc_demand").disabled)     # nada incorporável
        self.assertIn("Bloqueado: há erros nos dados.", [c.value for c in app.caption])
        self.assertEqual(_charts(app), [])                                      # nenhuma curva (nem a anterior)


class PrevisoesConcorrenciaTest(_Base):
    def test_conflito_preserva_a_entrada_pendente(self):
        uid, sc = self.with_scenario()
        a = self.session(uid)
        a = self.source(a, "demand", "referencia")
        a = self.incorporate(a, "demand")
        pend = copy.deepcopy(a.session_state["op_work"]["forecasts"]["demand"])
        self.assertIn(pend["data"], a.session_state["op_blobs"])
        # outra sessão grava antes (outra demanda)
        b = self.session(uid)
        b = self.source(b, "demand", "sintetico")
        b = self.incorporate(b, "demand")
        b = self.save(b)
        a = continuar(a, 120)
        _by_key(a.button, "op_save").click().run()
        a = continuar(a, 120)
        _ok(self, a)
        self.assertTrue(any("outra sessão" in e.value.lower() or "conflito" in e.value.lower() for e in a.error),
                        [e.value for e in a.error])
        self.assertEqual(a.session_state["op_work"]["forecasts"]["demand"], pend)        # pendente preservado
        self.assertIn(pend["data"], a.session_state["op_blobs"])
        cur = self.store(uid).get_scenario(sc)
        self.assertEqual(cur.version, 2)
        self.assertEqual(cur.document["forecasts"]["demand"]["source_type"], "sintetico")  # vencedor intacto
        with self.assertRaises(Exception):
            self.store(uid).get_blob(pend["data"])                              # nada do perdedor foi gravado


class PrevisoesIsolamentoIntegridadeTest(_Base):
    def test_troca_de_microrrede_limpa_o_estado_e_isola_dados(self):
        ua, sa = self.with_scenario("A")
        ub, sb = self.with_scenario("B")
        app = self.session(ua)
        app = self.source(app, "demand", "referencia")
        app = self.incorporate(app, "demand")
        self.assertTrue(app.session_state["op_blobs"])
        app.session_state["seeds_switch_requested"] = True                     # TROCAR MICRORREDE
        app.run()
        app = continuar(app, 120)
        for k in app.session_state.filtered_state if hasattr(app.session_state, "filtered_state") else []:
            self.assertFalse(str(k).startswith(("op_fcs_", "op_blobs")), k)
        self.assertNotIn("op_blobs", app.session_state)
        appb = self.session(ub)
        self.assertNotIn("Salvo · v", _html(appb).split("Perfil do cenário")[1][:400])
        self.assertEqual(self.store(ub).get_scenario(sb).document["forecasts"], {})
        self.assertEqual(self.store(ua).get_scenario(sa).document["forecasts"], {})    # incorporado ≠ gravado

    def test_blob_corrompido_e_inicializacao_sem_regressao(self):
        uid, sc = self.with_scenario()
        app = self.session(uid)
        app = self.source(app, "demand", "referencia")
        app = self.incorporate(app, "demand")
        app = self.save(app)
        st = self.store(uid)
        cur = st.get_scenario(sc)
        h = cur.document["forecasts"]["demand"]["data"]
        # Inicialização continua funcionando com previsões gravadas: edição de SOC salva nova versão e preserva-as
        app = self.session(uid, tab="inicializacao")
        bat = [e for e, r in cur.document["inventory_ref"]["equipment"].items() if r["kind"] == "battery"]
        next(n for n in app.number_input if n.key and n.key.startswith(f"op_{bat[0]}_") and n.key.endswith("_soc0_pct")).set_value(55.0).run()
        _ok(self, app)
        app = self.save(app)
        cur2 = st.get_scenario(sc)
        self.assertEqual(cur2.version, cur.version + 1)
        self.assertEqual(cur2.document["forecasts"], cur.document["forecasts"])
        self.assertEqual(cur2.document["initialization"]["equipment"][bat[0]]["soc0_pct"], 55.0)
        # corrupção do armazenamento: a página informa, não quebra, e nada é alterado
        with sqlite3.connect(st.path) as con:
            con.execute("UPDATE blobs SET content = ? WHERE sha256 = ?", (b"corrompido", h))
        app = self.session(uid)
        self.assertTrue(any("Não foi possível ler os dados" in e.value for e in app.error), [e.value for e in app.error])
        _by_key(app.button, "opw_fc_chk_demand").click().run()
        _ok(self, app)
        self.assertTrue(any("corrompid" in e.value for e in app.error))
        self.assertEqual(st.get_scenario(sc).version, cur2.version)


if __name__ == "__main__":
    unittest.main()
