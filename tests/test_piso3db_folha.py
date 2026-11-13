"""Folha de Ensaio — finalização da Partitura V2 (três colunas, subseções da estratégia V2, régua dos horizontes,
prontidão) e o estado «alterações não salvas» (abrir e percorrer não cria alteração falsa; edição real continua detectada).

Sem solver: o preflight V2 da seção 04 BLOQUEIA (solver ausente) e nada é executado. Navegador real:
``tools/e2e/e2e_piso3db_plataforma.js`` (fase 3 de ``tools/e2e/run_piso3db.sh``).
"""
from __future__ import annotations

import copy
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
    from apptest_utils import APP_PATH

import piso3da_util as U  # noqa: E402
import piso3db_util as P  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import ui as V2UI  # noqa: E402
from seeds2.microgrid import config as C  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.operation import service as SV  # noqa: E402

NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}
SECOES = ("inicializacao", "previsoes", "estrategia", "execucao")


# ============================================================================================ dados (sem navegador)
class ReguaESubsecoesTest(unittest.TestCase):
    def _doc(self, malha=None, dur=720):
        cfg = U.config_bateria("Régua (teste)")
        with tempfile.TemporaryDirectory() as d:
            MicrogridRegistry(d).create(cfg)
            st = MicrogridRegistry(d).open(cfg["installation"]["uid"])
            doc = copy.deepcopy(SV.create(st, name="r").document)
        doc[E.CHAVE_MOTOR] = E.MOTOR_V2
        doc[E.CHAVE_BLOCO] = U.bloco_h2(doc)
        if malha is not None:
            doc[E.CHAVE_BLOCO]["malha"] = malha
        doc["mission"] = None if dur is None else {"start": "2026-01-01T00:00:00", "timezone": "UTC", "duration_min": dur}
        return doc

    def test_regua_so_com_valores_declarados(self):
        r = V2UI.regua_dados(self._doc({"delta_min": 60, "N": 3, "m": 1, "H_L": 10}))
        self.assertEqual((r["delta_min"], r["N"], r["m"], r["H_L"], r["duracao_min"], r["K"], r["faltam"]), (60, 3, 1, 10, 720, 12, []))
        self.assertTrue(all(ok for _t, ok, _d in r["relacoes"]), r["relacoes"])
        self.assertEqual(len(r["relacoes"]), 5)
        # ausentes ⇒ N/D (nada é inferido) e as relações que dependem deles não são mostradas
        r = V2UI.regua_dados(self._doc({"delta_min": 60, "N": None, "m": 1, "H_L": None}, dur=None))
        self.assertEqual((r["N"], r["H_L"], r["duracao_min"], r["K"]), (None, None, None, None))
        self.assertEqual(r["faltam"], ["horizonte curto N", "horizonte longo H_L", "duração da missão (seção 04)"])
        self.assertEqual(r["relacoes"], [])
        # duração não múltipla de Δ: K_M não existe; a relação do preflight aparece como violada
        r = V2UI.regua_dados(self._doc({"delta_min": 60, "N": 3, "m": 4, "H_L": 2}, dur=90))
        self.assertIsNone(r["K"])
        rel = {t: ok for t, ok, _d in r["relacoes"]}
        self.assertEqual(rel, {"Duração da missão múltipla de Δ": False, "1 ≤ m ≤ N": False, "H_L > N": False})
        # tipos inválidos não viram números
        r = V2UI.regua_dados(self._doc({"delta_min": True, "N": -3, "m": 1.5, "H_L": "10"}))
        self.assertEqual((r["delta_min"], r["N"], r["m"], r["H_L"]), (None, None, None, None))
        self.assertEqual(r["terminal"], "janela reduzida")                      # política FIXA da integração (montagem.FIXOS)

    def test_subsecoes_contam_exatamente_as_pendencias_da_estrategia(self):
        doc = self._doc()
        doc[E.CHAVE_BLOCO] = E.novo_bloco(doc)                                   # declaração em branco
        subs = V2UI.subsecoes_estrategia(doc)
        self.assertEqual([s["id"] for s in subs], ["motor", "malha", "demanda", "baterias", "pcc", "planejador", "solver", "revisao"])
        self.assertEqual([s["n"] for s in subs], [f"03.{i}" for i in range(1, 9)])
        self.assertEqual(sum(s["pend"] for s in subs), len(E.pendencias(doc[E.CHAVE_BLOCO], doc)))
        self.assertGreater(next(s for s in subs if s["id"] == "malha")["pend"], 0)
        doc[E.CHAVE_BLOCO] = U.bloco_h2(doc)                                     # declaração completa
        self.assertEqual({s["pend"] for s in V2UI.subsecoes_estrategia(doc)}, {0})
        doc[E.CHAVE_BLOCO]["malha"]["N"] = "seis"                                # erro estrutural: pendências não calculadas
        self.assertEqual({s["pend"] for s in V2UI.subsecoes_estrategia(doc)}, {None})
        doc.pop(E.CHAVE_BLOCO)
        self.assertEqual([s["id"] for s in V2UI.subsecoes_estrategia(doc)], ["motor"])


@unittest.skipUnless(P.NODE, "Node.js não instalado")
class ReguaPuraTest(unittest.TestCase):
    def test_janelas_mpc_da_regua(self):
        r = P.node("return [api.janelasRegua({ K: 12, N: 3, m: 1 }).length, api.janelasRegua({ K: 12, N: 3, m: 1 }).slice(-2), "
                   "api.janelasRegua({ K: 24, N: 6, m: 2 }).length, api.janelasRegua({ K: 5, N: 3, m: 2 }), "
                   "api.janelasRegua({ K: null, N: 3, m: 1 }), api.janelasRegua({ K: 12, N: 3 }), api.durTxt(90), api.durTxt(null)];",
                   {}, componente="folha", puros="janelasRegua, durTxt")
        self.assertEqual(r[0], 12)
        self.assertEqual(r[1], [{"j": 10, "ini": 10, "apl": 1, "fim": 12, "reduzida": True}, {"j": 11, "ini": 11, "apl": 1, "fim": 12, "reduzida": True}])
        self.assertEqual(r[2], 12)
        self.assertEqual(r[3], [{"j": 0, "ini": 0, "apl": 2, "fim": 3, "reduzida": False}, {"j": 1, "ini": 2, "apl": 2, "fim": 5, "reduzida": False},
                                {"j": 2, "ini": 4, "apl": 1, "fim": 5, "reduzida": True}])
        self.assertEqual((r[4], r[5]), ([], []))                                 # sem K ou m: nenhuma janela inventada
        self.assertEqual((r[6], r[7]), ("1 h 30 min", "N/D"))


@unittest.skipUnless(P.NODE and P.navegador_disponivel(), "Chromium/Playwright (Node) não instalados")
class FolhaNoNavegadorTest(unittest.TestCase):
    SECS = [{"id": "inicializacao", "n": "01", "titulo": "Estado inicial", "tom": "ok", "estado": "Definida", "detalhe": "", "atual": False},
            {"id": "previsoes", "n": "02", "titulo": "Previsões", "tom": "ok", "estado": "Definidas", "detalhe": "", "atual": False},
            {"id": "estrategia", "n": "03", "titulo": "Motor e estratégia", "tom": "w", "estado": "Incompleta", "detalhe": "4 declaração(ões) ausente(s)", "atual": True},
            {"id": "execucao", "n": "04", "titulo": "Missão e execução", "tom": "b", "estado": "Não executável (V2)", "detalhe": "2 bloqueio(s)", "atual": False}]

    def test_indice_com_subsecoes_prontidao_e_regua(self):
        ind = {"cenario": {"uid": "sc1", "nome": "Dia útil", "versao": 4, "motor": "V2 · MILP–MPC hierárquico (experimental)", "revisao": 2},
               "secoes": self.SECS, "subsecoes": [{"id": "motor", "n": "03.1", "titulo": "Motor de execução", "pend": 0},
                                                  {"id": "malha", "n": "03.2", "titulo": "Malha temporal e horizontes", "pend": 3},
                                                  {"id": "pcc", "n": "03.3", "titulo": "Rede, PCC e objetivo", "pend": None}],
               "constatacoes": {"erro": 0, "aviso": 0, "pendente": 0, "incompleto": 0}, "alterado": False, "rodadas": 1}
        pron = {"parte": "prontidao", "tab": "estrategia", "versao": 4, "alterado": True, "secoes": self.SECS, "constatacoes": {},
                "pendencias": [{"id": "malha", "n": "03.2", "titulo": "Malha temporal e horizontes", "pend": 3}],
                "executavel": False, "motivo": "há alterações não salvas", "ativa": None,
                "ultima": {"uid": "r" * 32, "estado": "concluida", "versao": 3, "quando": "2026-11-12 10:00"}, "rodadas": 1}
        regua = {"parte": "regua", "regua": {"delta_min": 60, "N": 6, "m": 2, "H_L": 12, "duracao_min": 1440, "K": 24, "faltam": [],
                                             "relacoes": [["1 ≤ m ≤ N", True, "m = 2, N = 6"], ["H_L > N", True, ""]],
                                             "terminal": "janela reduzida", "cobertura": "reduzido ao fim da missao"}}
        vazia = {"parte": "regua", "regua": {"delta_min": 60, "N": None, "m": 1, "H_L": None, "duracao_min": None, "K": None,
                                             "faltam": ["horizonte curto N", "horizonte longo H_L", "duração da missão (seção 04)"], "relacoes": []}}
        acoes = "window.__acoes.map((a) => [a.type, a.tab || a.run || null])"
        r = P.bancada({"ind": ind}, passos=[["texto", "t"], ["avaliar", "subs", "[...document.querySelectorAll('.pt.folha .fl-subl')].map((b) => b.dataset.sub + ':' + b.textContent)"],
                                            ["clicar", '.pt.folha .fl-subl[data-sub="malha"]'], ["clicar", '.pt.folha .fl-sec[data-sec="execucao"]'],
                                            ["avaliar", "acoes", acoes]], componente="folha")["ind"]
        self.assertEqual(r["erros"], [])
        self.assertEqual(r["vistas"]["subs"], ["motor:03.1Motor de execução✓", "malha:03.2Malha temporal e horizontes3", "pcc:03.3Rede, PCC e objetivo"])
        self.assertEqual(r["vistas"]["acoes"], [["nav", "execucao"]])           # subseção só rola a página (sem rerun)
        self.assertIn("versão salva", r["vistas"]["t"])
        r = P.bancada({"pron": pron}, passos=[["texto", "t"], ["clicar", ".pt.folha .fl-ir04"], ["clicar", ".pt.folha .fl-ult"], ["avaliar", "acoes", acoes]],
                      componente="folha")["pron"]
        self.assertEqual(r["erros"], [])
        self.assertEqual(r["vistas"]["acoes"], [["nav", "execucao"], ["abrir_rodada", "r" * 32]])
        for t in ("Prontidão do ensaio", "Alterações não salvas", "versão salva v4", "Execução indisponível", "há alterações não salvas",
                  "03 · Motor e estratégia", "4 declaração(ões) ausente(s)", "Declarações ausentes (estratégia V2)", "Última rodada · v3 · concluida"):
            self.assertIn(t, r["vistas"]["t"])
        self.assertNotIn("EXECUTAR", r["vistas"]["t"].upper().replace("PRONTO PARA EXECUTAR", ""))   # nenhum botão de executar aqui
        r = P.bancada({"regua": regua, "vazia": vazia}, passos=[["texto", "t"], ["avaliar", "n", "document.querySelectorAll('.pt.folha .fl-rsvg rect.fl-ra').length"]],
                      componente="folha")
        self.assertEqual(r["regua"]["erros"], [])
        self.assertEqual(r["regua"]["vistas"]["n"], 4)                          # 3 primeiras janelas + a última (12 no total)
        for t in ("Janelas MPC", "12", "K_M = 24", "8 janela(s) intermediária(s)", "reduzida: 2 < N", "✓ H_L > N", "24 h"):
            self.assertIn(t, r["regua"]["vistas"]["t"])
        self.assertIn("Régua incompleta — não declarado(s): horizonte curto N, horizonte longo H_L, duração da missão (seção 04)", r["vazia"]["vistas"]["t"])
        self.assertIn("N/D", r["vazia"]["vistas"]["t"])
        self.assertEqual(r["vazia"]["vistas"]["n"], 0)


# ============================================================================================ interface (AppTest)
@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class AlteracoesNaoSalvasTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        self._env = mock.patch.dict(os.environ, NO_ADMIN)
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def _microrrede(self):
        cfg = U.config_bateria("Folha 3D-B (teste)")
        MicrogridRegistry(self.dir).create(cfg)
        uid = cfg["installation"]["uid"]
        return uid, MicrogridRegistry(self.dir).open(uid)

    def _sessao(self, uid, sc, tab):
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=240)
        app.session_state["mg_active_uid"] = uid
        app.session_state["seeds_route"] = {"view": "operacao", "tab": tab}
        app.query_params["sc"] = sc
        app.run()
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        return app

    @staticmethod
    def _sujo(app) -> bool:
        from seeds2.ui import operation_center as OC
        return OC._fp_edicao(app.session_state["op_work"]) != app.session_state["op_base_fp"]

    def _inteiros(self, doc):
        """Números gravados como INTEIROS onde os campos da interface são reais (caso relatado na auditoria)."""
        eid = U.bateria_id(doc)
        doc["initialization"]["equipment"][eid]["soc0_pct"] = 100
        b = doc[E.CHAVE_BLOCO]
        b["solver"]["time_limit_s"] = 60
        b["pcc"]["limite_importacao_kW"] = 50
        b["baterias"][eid].update(p_carga_barramento_kW=5, p_descarga_barramento_kW=10, eta_carga=1, eta_descarga=1)

    def test_abrir_e_percorrer_as_quatro_secoes_nao_cria_alteracao_falsa(self):
        uid, st = self._microrrede()
        sc = U.criar_cenario_v2(st, mutar=self._inteiros)
        antes = (sc.version, sc.fingerprint)
        coagido = False
        for tab in SECOES:
            app = self._sessao(uid, sc.scenario_uid, tab)
            self.assertFalse(self._sujo(app), tab)
            coagido |= C.fingerprint(app.session_state["op_work"]) != sc.fingerprint
            op_save = next(b for b in app.button if b.key == "op_save")
            self.assertTrue(op_save.disabled, tab)                               # nada a salvar: só se abriu a seção
        self.assertTrue(coagido)        # os campos reais apresentaram 60 → 60.0 etc.; sem a correção haveria alteração falsa
        cur = st.get_scenario(sc.scenario_uid)
        self.assertEqual((cur.version, cur.fingerprint), antes)                 # nada foi gravado

    def test_alteracao_real_continua_detectada_e_bloqueia_a_execucao(self):
        uid, st = self._microrrede()
        sc = U.criar_cenario_v2(st, mutar=self._inteiros)
        app = self._sessao(uid, sc.scenario_uid, "estrategia")
        n = next(w for w in app.number_input if (w.key or "").endswith("_v2_N"))
        n.set_value(int(n.value) + 1).run()
        self.assertTrue(self._sujo(app))
        self.assertFalse(next(b for b in app.button if b.key == "op_save").disabled)
        # a mesma edição vista na prontidão: execução indisponível pela razão do botão da seção 04
        from seeds2.ui import folha_ui
        cur = st.get_scenario(sc.scenario_uid)
        doc = app.session_state["op_work"]
        with mock.patch("seeds2.ui.execution_ui.stage_state", return_value=("ok", "Pronto para executar (V2)", "")):
            d = folha_ui.dados(st, cur, doc, "estrategia", dirty=True)
            p = folha_ui.prontidao(st, cur, doc, d, dirty=True)
            self.assertEqual((p["executavel"], p["motivo"]), (False, "há alterações não salvas"))
            d = folha_ui.dados(st, cur, cur.document, "estrategia", dirty=False)
            self.assertTrue(folha_ui.prontidao(st, cur, cur.document, d, dirty=False)["executavel"])
        with mock.patch("seeds2.ui.execution_ui.stage_state", return_value=("bad", "Não executável (V2)", "1 bloqueio(s)")):
            d = folha_ui.dados(st, cur, cur.document, "estrategia", dirty=False)
            self.assertEqual(folha_ui.prontidao(st, cur, cur.document, d, dirty=False)["motivo"], "o preflight V2 tem bloqueios")
        # texto e opção também contam como alteração (não só números)
        app = self._sessao(uid, sc.scenario_uid, "estrategia")
        t = next(w for w in app.text_input if (w.key or "").endswith("_v2_gj"))
        t.set_value(t.value + " (revisado)").run()
        self.assertTrue(self._sujo(app))
        self.assertEqual(st.get_scenario(sc.scenario_uid).version, sc.version)

    def test_cenario_v16_tambem_e_percorrido_sem_alteracao_falsa(self):
        uid, st = self._microrrede()
        sc = SV.create(st, name="Cenário V1.6")
        for tab in SECOES:
            app = self._sessao(uid, sc.scenario_uid, tab)
            self.assertFalse(self._sujo(app), tab)
        self.assertEqual(st.get_scenario(sc.scenario_uid).version, sc.version)

    def test_subsecoes_ancoradas_na_pagina_e_folha_em_colunas(self):
        uid, st = self._microrrede()
        sc = U.criar_cenario_v2(st)
        app = self._sessao(uid, sc.scenario_uid, "estrategia")
        html = "\n".join(h.proto.body for h in app.get("html"))
        ancoras = [x.split('"')[0] for x in html.split('data-fl-sub="')[1:]]
        self.assertEqual(ancoras, [s["id"] for s in V2UI.subsecoes_estrategia(app.session_state["op_work"])])
        self.assertIn("Estratégia EMS · motor V2 experimental", html)           # o cartão da etapa continua (vira cabeçalho)
        self.assertIn("st-key-fl_col_secao", html)                               # estilos das colunas da Folha presentes
        self.assertTrue(any(b.key == "op_back_sg" for b in app.button))          # «← Centro de Operação» preservado


if __name__ == "__main__":
    unittest.main()


# ============================================================================================ barra lateral: Rodada
class BarraLateralRodadaTest(unittest.TestCase):
    def test_destino_rodada_so_com_rodada_desta_microrrede(self):
        from seeds2.ui import shell

        sem = shell.sidebar_items(view="operacao", tab="rodada", is_open=True, commissioned=True)
        self.assertNotIn("rodada", [i["id"] for i in sem])
        self.assertEqual([i["id"] for i in sem if i["atual"]], ["operacao"])           # comportamento anterior preservado
        com = shell.sidebar_items(view="operacao", tab="rodada", is_open=True, commissioned=True, rodada="ab" * 16)
        r = next(i for i in com if i["id"] == "rodada")
        self.assertEqual((r["rotulo"], r["acao"], r["atual"]), ("Rodada · abababab", {"type": "nav", "view": "operacao", "tab": "rodada"}, True))
        self.assertEqual([i["id"] for i in com if i["atual"]], ["rodada"])
        self.assertEqual([i["id"] for i in com][:5], ["catalogo", "planta", "caderno", "folha", "rodada"])
        fora = shell.sidebar_items(view="operacao", tab="caderno", is_open=True, commissioned=True, rodada="ab" * 16)
        self.assertEqual([i["id"] for i in fora if i["atual"]], ["caderno"])
        self.assertNotIn("rodada", [i["id"] for i in shell.sidebar_items(view="gestor", tab=None, is_open=False, commissioned=False, rodada="x" * 32)])

    def test_rodada_da_sessao_confere_a_microrrede_ativa(self):
        from seeds2.microgrid.store import RunNotFound
        from seeds2.ui import shell

        class _St:
            def get_run(self, uid):
                if uid != "ok" * 16:
                    raise RunNotFound(uid)
                return SimpleNamespace(run_uid=uid)

        from types import SimpleNamespace
        for estado, q, esperado in (({"mg_active_uid": "mg", "op_run_uid": "ok" * 16}, {}, "ok" * 16),
                                    ({"mg_active_uid": "mg"}, {"run": "ok" * 16}, "ok" * 16),
                                    ({"mg_active_uid": "mg", "op_run_uid": "zz" * 16}, {}, None),     # de outra microrrede
                                    ({"op_run_uid": "ok" * 16}, {}, None),                           # sem microrrede ativa
                                    ({"mg_active_uid": "mg"}, {}, None)):
            with mock.patch.object(shell.st, "session_state", estado), mock.patch.object(shell.st, "query_params", q), \
                    mock.patch("seeds2.ui.session.store", return_value=_St()):
                self.assertEqual(shell._rodada_da_sessao(), esperado, (estado, q))
