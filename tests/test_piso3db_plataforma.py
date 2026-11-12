"""Piso 3D-B2 — integração visual da plataforma (navegação e páginas na linguagem Partitura).

B2-A: barra lateral. Os destinos espelham a navegação existente (nada é retirado da barra superior) e são decididos pelo
shell; o componente só navega. Aqui: a tabela de destinos por contexto, o retorno do componente e os estáticos. O
comportamento no navegador (trilho, expansão por hover/foco, barra inferior no celular, estabilidade em reruns) é coberto
por ``tools/e2e/e2e_piso3db_plataforma.js``.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest
except Exception:  # noqa: BLE001
    AppTest = None

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from seeds2.ui import shell  # noqa: E402

ESTATICO = RAIZ / "seeds2" / "ui" / "static" / "trama"


def _ids(itens):
    return [i["id"] for i in itens]


class DestinosDaBarraLateralTest(unittest.TestCase):
    def test_sem_microrrede_so_catalogo_arquivo_e_documentacao(self):
        it = shell.sidebar_items(view="gestor", tab=None, is_open=False, commissioned=False)
        self.assertEqual(_ids(it), ["catalogo", "arquivo", "alcance"])
        self.assertEqual([i["id"] for i in it if i["atual"]], ["catalogo"])
        self.assertEqual(it[0]["acao"], {"type": "nav", "view": "gestor", "tab": None})
        it = shell.sidebar_items(view="arquivo", tab=None, is_open=False, commissioned=False)
        self.assertEqual([i["id"] for i in it if i["atual"]], ["arquivo"])

    def test_em_comissionamento_o_catalogo_troca_de_microrrede(self):
        it = shell.sidebar_items(view="comissionamento", tab=None, is_open=True, commissioned=False)
        self.assertEqual(_ids(it), ["catalogo", "comissionamento", "alcance"])
        self.assertEqual(it[0]["acao"], {"type": "switch"})           # nunca navega para o Gestor com a microrrede aberta
        self.assertEqual([i["id"] for i in it if i["atual"]], ["comissionamento"])

    def test_microrrede_comissionada_espelha_toda_a_navegacao_existente(self):
        it = shell.sidebar_items(view="operacao", tab=None, is_open=True, commissioned=True)
        destinos = {i["acao"].get("view") for i in it if i["acao"]["type"] == "nav"}
        # nenhum destino da barra superior desaparece
        self.assertLessEqual({v for v, _t, _g in shell.NAV_ACTIVE} | {v for v, _t in shell.NAV_DOCS}, destinos)
        self.assertEqual(it[0]["acao"], {"type": "switch"})
        self.assertEqual([i["id"] for i in it if i["atual"]], ["operacao"])
        at = shell.sidebar_items(view="operacao", tab="planta", is_open=True, commissioned=True)      # B2-B: Planta
        self.assertEqual([i["id"] for i in at if i["atual"]], ["planta"])
        self.assertEqual(next(i for i in at if i["id"] == "planta")["acao"], {"type": "nav", "view": "operacao", "tab": "planta"})
        for tab in ("arquivo", "estudo"):                               # o Arquivo vive no Centro de Operação
            at = shell.sidebar_items(view="operacao", tab=tab, is_open=True, commissioned=True)
            self.assertEqual([i["id"] for i in at if i["atual"]], ["arquivo"])
        for view in ("gestao", "simulacao", "resultados", "alcance"):
            at = shell.sidebar_items(view=view, tab=None, is_open=True, commissioned=True)
            self.assertEqual([i["id"] for i in at if i["atual"]], [view])
        self.assertTrue(all(i["acao"]["view"] in shell.VIEWS for i in it if i["acao"]["type"] == "nav"))
        self.assertGreaterEqual(sum(1 for i in it if i["movel"]), 3)    # a barra inferior do celular tem o essencial

    @unittest.skipIf(AppTest is None, "Streamlit não instalado")
    def test_retorno_do_componente_navega_ou_pede_a_troca(self):
        roteiro = ("import streamlit as st\nfrom seeds2.ui import shell\n"
                   "st.session_state['seeds_sidebar'] = {'action': ACAO}\nshell._on_sidebar()\n"
                   "st.write(repr((shell.route()['view'], shell.route().get('tab'), st.session_state.get(shell.SWITCH_KEY))))\n")
        casos = [({"type": "nav", "view": "gestao", "tab": None}, ("gestao", None, None)),
                 ({"type": "nav", "view": "operacao", "tab": "arquivo"}, ("operacao", "arquivo", None)),
                 ({"type": "nav", "view": "nao_existe", "tab": None}, ("gestor", None, None)),      # destino inválido cai no Gestor
                 ({"type": "switch"}, ("gestor", None, True))]
        for acao, esperado in casos:
            app = AppTest.from_string(roteiro.replace("ACAO", repr(acao)), default_timeout=60)
            app.run()
            self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
            self.assertEqual(app.markdown[0].value, repr(esperado), acao)


class EstaticosDaPlataformaTest(unittest.TestCase):
    def test_barra_lateral_sem_recursos_externos_e_com_todos_os_icones(self):
        js = (ESTATICO / "sidebar.js").read_text(encoding="utf-8")
        self.assertNotRegex(js, r"https?://")
        icones = set(re.findall(r"^\s*(\w+): \"M", js, flags=re.M)) | set(re.findall(r", (\w+): \"M", js))
        for contexto in ((False, False), (True, False), (True, True)):
            for i in shell.sidebar_items(view="operacao", tab=None, is_open=contexto[0], commissioned=contexto[1]):
                self.assertIn(i["icone"], icones, i["id"])
        css = (ESTATICO / "trama.css").read_text(encoding="utf-8")
        self.assertIn(".pt.sb", css)
        self.assertIn("@media (max-width: 760px)", css)                 # barra inferior em telas estreitas

    def test_tema_neutro_da_partitura_sem_alterar_as_cores_dos_dados(self):
        cfg = (RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('backgroundColor = "#F4F4F2"', cfg)
        self.assertIn('backgroundColor = "#0F0F0F"', cfg)
        # as cores categóricas dos gráficos nativos (dados) são as mesmas de antes do 3D-B2
        self.assertIn('chartCategoricalColors = ["#0E7C86", "#2F6FED", "#E0891E", "#7A4FD1", "#D1495B", "#3C9D5D", "#5B6B7C"]', cfg)


# ============================================================================================ B2-B · Planta
import copy  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402

sys.path.insert(0, str(RAIZ / "tests"))

import piso3db_util as P  # noqa: E402

PUROS_PLANTA = "modeloPlanta, kwTxt, estadoTxt"


def _planta_sintetica(*, rodada: bool = True, bancos: int = 2, fv_arranjos: int = 2, pemfc_unidades: int = 2) -> dict:
    """Dados da Planta como ``planta_ui`` os entrega (FICTÍCIOS, de teste): 1 usina FV com N arranjos, 2 aerogeradores,
    N bancos, 1 registro PEMFC com N unidades, 1 térmica desabilitada."""
    K = 4
    nos = [{"uid": "eq-fv", "tipo": "fv", "nome": "Usina FV", "tag": "FV-01", "habilitado": True, "resumo": "10,0 kWp", "detalhes": [["Arranjos", str(fv_arranjos)]],
            "uids": [f"arr-{n}" for n in range(1, fv_arranjos + 1)], "prefixo": None},
           {"uid": "eq-wt1", "tipo": "wt", "nome": "Aerogerador 1", "tag": "", "habilitado": True, "resumo": "275 kW", "detalhes": [], "uids": ["eq-wt1"], "prefixo": None},
           {"uid": "eq-wt2", "tipo": "wt", "nome": "Aerogerador 2", "tag": "", "habilitado": True, "resumo": "275 kW", "detalhes": [], "uids": ["eq-wt2"], "prefixo": None},
           {"uid": "eq-fc", "tipo": "fc", "nome": "PEMFC", "tag": "FC-01", "habilitado": True, "resumo": "50 kW", "detalhes": [], "uids": ["eq-fc"], "prefixo": "eq-fc#"},
           {"uid": "eq-term", "tipo": "term", "nome": "Gerador a diesel", "tag": "", "habilitado": False, "resumo": "100 kW", "detalhes": [], "uids": ["eq-term"], "prefixo": None}]
    nos += [{"uid": f"eq-bat{n}", "tipo": "bat", "nome": f"Banco {n}", "tag": f"BAT-0{n}", "habilitado": True, "resumo": "20 kWh", "detalhes": [],
             "uids": [f"eq-bat{n}"], "prefixo": None} for n in range(1, bancos + 1)]
    d = {"microrrede": {"uid": "m" * 32, "nome": "Planta de teste", "revisao": 3, "modo": "Conectada à rede"}, "nos": nos,
         "demanda": {"origem": "teste"}, "pcc": {"conectada": True}, "rodadas": [], "escolhida": "", "rodada": None, "rodada_indisponivel": False}
    if rodada:
        series = {f"arr-{n}": {"p": [1.0 * n] * K, "pot": [2.0 * n] * K} for n in range(1, fv_arranjos + 1)}
        series |= {"eq-wt1": {"p": [8.0] * K, "pot": [10.0] * K}, "eq-wt2": {"p": [0.0] * K, "pot": [0.0] * K}}
        series |= {(f"eq-fc#{n}" if pemfc_unidades > 1 else "eq-fc"): {"p": [10.0] * K, "u": [1.0] * K, "q": [0.6] * K} for n in range(1, pemfc_unidades + 1)}
        series |= {f"eq-bat{n}": {"pd": [0.0, 2.0, 0.0, 0.0], "pc": [3.0, 0.0, 0.0, 0.0], "e": [10.0, 13.0, 11.0, 11.0, 11.0]} for n in range(1, bancos + 1)}
        d["rodada"] = {"uid": "r" * 32, "cenario": "Cenário de teste", "versao": 2, "K": K, "delta_min": 60.0, "revisao": 3, "hash": "h",
                       "local": [f"2026-01-01T{h:02d}:00:00" for h in range(K + 1)], "series": series,
                       "demanda": {"realizada": [30.0] * K, "atendida": [30.0] * K},
                       "pcc": {"conectado": True, "imp": [5.0, 0.0, 5.0, 5.0], "exp": [0.0, 1.0, 0.0, 0.0], "tarifa": [0.5] * K}}
        d["rodadas"], d["escolhida"] = [{"uid": "r" * 32, "rotulo": "Cenário de teste · v2"}], "r" * 32
    return d


@unittest.skipUnless(P.NODE, "Node.js não instalado")
class ModeloDaPlantaTest(unittest.TestCase):
    def _m(self, d, extra="null"):
        return P.node(f"const M = api.modeloPlanta(F); return {{ nos: M.nos.map((n) => ({{ uid: n.uid, tipo: n.tipo, ids: n.ids, participa: n.participa, p: n.p, e: n.e }})), "
                      f"cima: M.cima.map((n) => n.uid), baixo: M.baixo.map((n) => n.uid), rot: M.rot, K: M.K, x: {extra} }};", d, componente="planta", puros=PUROS_PLANTA)

    def test_um_no_por_equipamento_com_identidade_por_uid(self):
        r = self._m(_planta_sintetica())
        self.assertEqual(r["cima"], ["eq-fv", "eq-wt1", "eq-wt2", "eq-fc", "eq-term"])       # o que injeta, acima
        self.assertEqual(r["baixo"], ["eq-bat1", "eq-bat2", "demanda", "PCC"])                  # armazena/consome/rede, abaixo
        nos = {n["uid"]: n for n in r["nos"]}
        self.assertEqual(nos["eq-fv"]["ids"], ["arr-1", "arr-2"])
        self.assertEqual(nos["eq-fv"]["p"], [3.0] * 4)                                          # 1 + 2 kW dos dois arranjos
        self.assertEqual((nos["eq-wt1"]["p"], nos["eq-wt2"]["p"]), ([8.0] * 4, [0.0] * 4))      # dois aerogeradores, cada um o seu
        self.assertEqual(sorted(nos["eq-fc"]["ids"]), ["eq-fc#1", "eq-fc#2"])                   # unidades do MESMO registro
        self.assertEqual(nos["eq-fc"]["p"], [20.0] * 4)
        self.assertEqual(nos["eq-bat1"]["p"], [-3.0, 2.0, 0.0, 0.0])                            # descarga − carga (líquido)
        self.assertEqual(nos["eq-bat2"]["e"], [10.0, 13.0, 11.0, 11.0, 11.0])
        self.assertEqual(nos["PCC"]["p"], [5.0, -1.0, 5.0, 5.0])
        self.assertEqual(nos["demanda"]["p"], [30.0] * 4)
        self.assertEqual((nos["eq-term"]["participa"], nos["eq-term"]["p"]), (False, "__undefined__"))   # não participou ≠ zero
        self.assertEqual(r["rot"][:2], ["00h", "01h"])

    def test_pemfc_de_uma_unidade_usa_o_uid_do_registro(self):
        nos = {n["uid"]: n for n in self._m(_planta_sintetica(pemfc_unidades=1))["nos"]}
        self.assertEqual((nos["eq-fc"]["ids"], nos["eq-fc"]["p"]), (["eq-fc"], [10.0] * 4))

    def test_sem_rodada_so_o_inventario_e_nenhum_valor(self):
        r = self._m(_planta_sintetica(rodada=False))
        self.assertEqual(r["K"], 0)
        self.assertTrue(all(n["p"] == "__undefined__" and not n["participa"] for n in r["nos"]))
        self.assertIn("PCC", r["baixo"])                                                        # conexão vem do inventário

    def test_inventario_vazio_e_microrrede_isolada(self):
        d = _planta_sintetica(rodada=False)
        d["nos"], d["pcc"] = [], {"conectada": False}
        r = self._m(d)
        self.assertEqual((r["cima"], r["baixo"]), ([], ["demanda"]))                            # sem PCC: a rede não é desenhada

    def test_dado_ausente_na_rodada_e_nd_nunca_zero(self):
        d = _planta_sintetica()
        d["rodada"]["series"]["arr-2"]["p"] = None                  # um arranjo sem série ⇒ a usina é N/D (não «1 kW»)
        d["rodada"]["series"]["eq-wt1"]["p"][2] = None
        d["rodada"]["series"]["eq-bat1"]["pc"] = None
        d["rodada"]["pcc"]["imp"] = None
        nos = {n["uid"]: n for n in self._m(d)["nos"]}
        self.assertIsNone(nos["eq-fv"]["p"])
        self.assertEqual(nos["eq-wt1"]["p"], [8.0, 8.0, None, 8.0])
        self.assertIsNone(nos["eq-bat1"]["p"])
        self.assertIsNone(nos["PCC"]["p"])
        txt = P.node("const M = api.modeloPlanta(F), n = Object.fromEntries(M.nos.map((x) => [x.uid, x])); return [api.kwTxt(n['eq-fv'], 0), api.kwTxt(n['eq-wt1'], 2), "
                     "api.kwTxt(n['eq-wt2'], 0), api.kwTxt(n['eq-term'], 0), api.kwTxt(n['eq-bat2'], 0), api.estadoTxt(n['eq-term'], 0), api.estadoTxt(n['eq-bat2'], 0)];",
                     d, componente="planta", puros=PUROS_PLANTA)
        self.assertEqual(txt, ["N/D", "N/D", "0,0 kW", "—", "−3,0 kW", "desabilitado no inventário", "10 → 13 kWh · carga"])


@unittest.skipUnless(P.navegador_disponivel(), "Chromium/Playwright (Node) não instalados")
class PlantaNoNavegadorTest(unittest.TestCase):
    def test_hover_selecao_instante_painel_por_uid_e_inventario_vazio(self):
        vazio = _planta_sintetica(rodada=False)
        vazio["nos"] = []
        sel = "document.querySelector('.pt.planta .col').textContent.replace(/\\s+/g, ' ')"
        passos = [["avaliar", "nos", "[...document.querySelectorAll('.pt.planta .node')].map((n) => n.dataset.uid)"],
                  ["mover", 0, 0], ["avaliar", "pop0", "document.querySelector('.pt.planta .pop').hidden"],
                  ["avaliar", "hover", "(document.querySelector('.pt.planta .node[data-uid=\"eq-wt1\"]').dispatchEvent(new PointerEvent('pointerenter')), "
                                       "[document.querySelector('.pt.planta .pop').hidden, document.querySelector('.pt.planta .pop').textContent, "
                                       "document.querySelectorAll('.pt.planta .node.off').length])"],
                  ["avaliar", "sai", "(document.querySelector('.pt.planta .node[data-uid=\"eq-wt1\"]').dispatchEvent(new PointerEvent('pointerleave')), document.querySelector('.pt.planta .pop').hidden)"],
                  ["clicar", '.pt.planta .node[data-uid="eq-bat2"]'], ["avaliar", "sel", sel],
                  ["avaliar", "instante", "(() => { const s = document.querySelector('.pt.planta .pl-t'); s.value = 1; s.dispatchEvent(new Event('input')); "
                                          "return [document.querySelector('.pt.planta .pl-inst').textContent, document.querySelector('.pt.planta .node[data-uid=\"eq-bat2\"] .pw').textContent]; })()"],
                  ["clicar", ".pt.planta .pl-abrir"], ["avaliar", "acoes", "window.__acoes"],
                  ["avaliar", "estado_partitura", "JSON.parse(sessionStorage.getItem('seeds2.partitura.' + 'r'.repeat(32)))"],
                  ["avaliar", "setas", "document.querySelectorAll('.pt.planta svg marker, .pt.planta svg animate, .pt.planta svg animateMotion').length"]]
        r = P.bancada({"planta": _planta_sintetica()}, passos=passos, componente="planta")["planta"]
        self.assertEqual(r["erros"], [])
        v = r["vistas"]
        self.assertEqual(v["nos"], ["eq-fv", "eq-wt1", "eq-wt2", "eq-fc", "eq-term", "eq-bat1", "eq-bat2", "demanda", "PCC"])
        self.assertTrue(v["pop0"])
        self.assertFalse(v["hover"][0])
        self.assertIn("Aerogerador 1", v["hover"][1])
        self.assertIn("8,0 kW", v["hover"][1])
        self.assertEqual(v["hover"][2], 8)                                  # os outros 8 nós recuam
        self.assertTrue(v["sai"])
        self.assertIn("Banco 2", v["sel"])
        self.assertIn("eq-bat2", v["sel"])
        self.assertEqual(v["instante"], ["01h–02h", "2,0 kW"])
        self.assertEqual([(a["type"], a.get("run")) for a in v["acoes"]], [("abrir_rodada", "r" * 32)])
        self.assertEqual((v["estado_partitura"]["ex"], v["estado_partitura"]["uid"], v["estado_partitura"]["cur"], v["estado_partitura"]["pin"]),
                         ("bat", {"bat": "eq-bat2"}, 1, True))                  # o painel abre no UID e no instante escolhidos
        self.assertEqual(v["setas"], 0)                                     # nenhuma seta nem animação de fluxo nas ligações
        r = P.bancada({"vazio": vazio}, passos=[["avaliar", "nos", "[...document.querySelectorAll('.pt.planta .node')].map((n) => n.dataset.uid)"],
                                                 ["texto", "t"]], componente="planta")["vazio"]
        self.assertEqual(r["erros"], [])
        self.assertEqual(r["vistas"]["nos"], ["demanda", "PCC"])
        self.assertIn("Inventário sem equipamentos", r["vistas"]["t"])
        self.assertIn("Sem rodada V2 concluída", r["vistas"]["t"])


class PlantaSobreOInventarioRealTest(unittest.TestCase):
    """``planta_ui`` sobre microrredes do catálogo (diretório temporário): inventário real, vários equipamentos por
    tecnologia, e os valores gravados de uma rodada V2 (com solver)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["SEEDS2_DATA_DIR"] = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_nos_do_inventario_sem_inventar_nada(self):
        from seeds2.microgrid import config as C
        from seeds2.microgrid.registry import MicrogridRegistry
        from seeds2.ui import planta_ui

        cfg = P.H.config_pemfc("Planta real (teste)", quantidade=2, fv=True, eolica=True)
        C.add_equipment(cfg, C.new_equipment("battery", "Banco 02", tag="BAT-02", params={"energy_kWh": None}))    # sem energia declarada
        MicrogridRegistry(self._tmp.name).create(cfg)
        saved = MicrogridRegistry(self._tmp.name).open(cfg["installation"]["uid"]).load()
        d = planta_ui.dados_do_inventario(saved)
        self.assertEqual(sorted(n["uid"] for n in d["nos"]), sorted(e["id"] for e in cfg["equipment"]))
        tipos = [n["tipo"] for n in d["nos"]]
        self.assertEqual((tipos.count("bat"), tipos.count("fv"), tipos.count("wt"), tipos.count("fc")), (2, 1, 1, 1))
        fv = next(n for n in d["nos"] if n["tipo"] == "fv")
        self.assertEqual(fv["uids"], [a["id"] for a in next(e for e in cfg["equipment"] if e["kind"] == "pv")["arrays"]])
        fc = next(n for n in d["nos"] if n["tipo"] == "fc")
        self.assertEqual(fc["prefixo"], fc["uid"] + "#")
        self.assertIn(["Unidades", "2"], fc["detalhes"])
        b2 = next(n for n in d["nos"] if n["nome"] == "Banco 02")
        self.assertEqual(b2["resumo"], "não declarado")                    # valor desconhecido fica «não declarado»
        self.assertTrue(d["pcc"]["conectada"])
        vazio = copy.deepcopy(saved.config)
        vazio["equipment"] = []
        self.assertEqual(planta_ui.dados_do_inventario(type("S", (), {"config": vazio, "revision": 1})())["nos"], [])

    @unittest.skipUnless(P.SOLVER, "Pyomo/HiGHS não instalados")
    def test_valores_da_rodada_sao_os_gravados_por_uid(self):
        from integracao_v2 import registro as RG
        from seeds2.ui import planta_ui

        _uid, st, run = P.missao_dois_bancos(self._tmp.name)
        d = planta_ui.dados_da_rodada(st, run)
        it, fr = RG.ler_csv(st, run, RG.N_INTERVALOS), RG.ler_csv(st, run, RG.N_FRONTEIRAS)
        bancos = [u for u in d["series"] if "pd" in d["series"][u]]
        self.assertEqual(len(bancos), 2)
        for u in bancos:
            self.assertEqual(d["series"][u]["pd"], it[f"{u}|P_d_kW"].tolist())
            self.assertEqual(d["series"][u]["e"], fr[f"{u}|energia_kWh"].tolist())
        self.assertEqual(d["demanda"]["realizada"], it["demanda_realizada_kW"].tolist())
        self.assertEqual(d["pcc"]["imp"], it["pcc_importacao_realizada_kW"].tolist())
        self.assertEqual((d["uid"], d["K"]), (run.run_uid, len(it)))
        dados = planta_ui.dados_do_inventario(st.load())
        dados["rodada"] = d
        if P.NODE:                                                         # inventário real × rodada real: cada banco no seu nó
            nos = {n["uid"]: n for n in P.node("return api.modeloPlanta(F).nos.map((n) => ({ uid: n.uid, tipo: n.tipo, ids: n.ids, p: n.p }));",
                                                dados, componente="planta", puros=PUROS_PLANTA)}
            for u in bancos:
                self.assertEqual(nos[u]["ids"], [u])
                self.assertEqual(nos[u]["p"], (it[f"{u}|P_d_kW"] - it[f"{u}|P_c_kW"]).tolist())


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class PlantaNaAplicacaoTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["SEEDS2_DATA_DIR"] = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _abrir(self, uid):
        app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=240)
        app.session_state["mg_active_uid"] = uid
        app.session_state["seeds_route"] = {"view": "operacao", "tab": "planta"}
        app.run()
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        return app

    def test_planta_sem_rodada_mostra_so_o_inventario(self):
        from seeds2.microgrid.registry import MicrogridRegistry

        cfg = P.U.config_bateria("Planta sem rodada (teste)")
        MicrogridRegistry(self._tmp.name).create(cfg)
        app = self._abrir(cfg["installation"]["uid"])
        self.assertTrue(any("Planta · Planta sem rodada (teste)" in str(h.value) for h in app.get("html")))
        self.assertNotIn("pl_run_uid", app.session_state)                # nenhuma rodada escolhida, nada lido
        self.assertEqual(app.session_state["pl_cache"], {})
        self.assertEqual(len(MicrogridRegistry(self._tmp.name).open(cfg["installation"]["uid"]).list_runs()), 0)

    @unittest.skipUnless(P.SOLVER, "Pyomo/HiGHS não instalados")
    def test_planta_le_a_rodada_concluida_sem_solver_e_sem_gravar(self):
        from unittest import mock

        from integracao_v2 import execucao as X

        uid, st, run = P.missao_24h(self._tmp.name, "Planta com rodada (teste)")
        antes = st.load().fingerprint
        with mock.patch.object(X, "submit", side_effect=AssertionError("motor chamado pela Planta")), \
                mock.patch.dict(sys.modules, {"pyomo": None, "highspy": None}):
            app = self._abrir(uid)
            dados = app.session_state["pl_cache"][run.run_uid]
            self.assertEqual((dados["uid"], dados["K"]), (run.run_uid, 24))
            app.session_state["pl_run_uid"] = ""                          # «Só o inventário (sem rodada)»
            app.run()
            self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        self.assertEqual(st.load().fingerprint, antes)                    # a Planta não altera o inventário
        self.assertEqual([r.run_uid for r in st.list_runs()], [run.run_uid])


if __name__ == "__main__":
    unittest.main()
