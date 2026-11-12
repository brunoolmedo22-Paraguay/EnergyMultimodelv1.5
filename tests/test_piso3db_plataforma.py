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
        at = shell.sidebar_items(view="operacao", tab="caderno", is_open=True, commissioned=True)     # B2-C: Caderno
        self.assertEqual([i["id"] for i in at if i["atual"]], ["caderno"])
        for tab in ("inicializacao", "previsoes", "estrategia", "execucao"):                          # B2-D: Folha = as 4 etapas
            at = shell.sidebar_items(view="operacao", tab=tab, is_open=True, commissioned=True)
            self.assertEqual([i["id"] for i in at if i["atual"]], ["folha"])
        at = shell.sidebar_items(view="operacao", tab="rodada", is_open=True, commissioned=True)
        self.assertEqual([i["id"] for i in at if i["atual"]], ["operacao"])
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


# ============================================================================= B2-B Catálogo · B2-C Caderno · B2-D Folha
class CatalogoCadernoFolhaTest(unittest.TestCase):
    """Sobre microrredes do catálogo em diretório temporário: tudo é LIDO do armazenamento; nada é gravado."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        os.environ["SEEDS2_DATA_DIR"] = self.dir

    def tearDown(self):
        self._tmp.cleanup()

    def _microrrede(self, cfg):
        from seeds2.microgrid.registry import MicrogridRegistry

        MicrogridRegistry(self.dir).create(cfg)
        return MicrogridRegistry(self.dir).open(cfg["installation"]["uid"])

    def test_catalogo_assinatura_e_ensaios_vem_do_inventario_e_do_armazenamento(self):
        from seeds2.microgrid.registry import card_summary
        from seeds2.ui import gestor

        st = self._microrrede(P.H.config_pemfc("Catálogo híbrido (teste)", fv=True, eolica=True))
        s = card_summary(st.load())
        s["ensaios"] = gestor._ensaios(st, st.load().config)
        self.assertEqual((s["ensaios"]["cenarios"], s["ensaios"]["rodadas"], s["ensaios"]["conectada"]), (0, {}, True))
        self.assertGreater(s["ensaios"]["pemfc_kW"], 0)
        self.assertEqual(gestor._ensaios_txt(s["ensaios"]), "Ensaios: 0 cenário(s) · nenhuma rodada")
        sig = gestor._assinatura(s)
        self.assertEqual(sig.count('class="gs-m"'), 3)                     # FV, eólica e PEMFC presentes
        self.assertIn("gs-b", sig)
        self.assertIn("gs-pcc", sig)
        self.assertNotIn("<svg", sig)                                      # o st.html remove SVG: a assinatura é HTML/CSS
        so_bat = self._microrrede(P.U.config_bateria("Catálogo isolado (teste)", modo="isolada"))
        s2 = card_summary(so_bat.load())
        s2["ensaios"] = gestor._ensaios(so_bat, so_bat.load().config)
        sig2 = gestor._assinatura(s2)
        self.assertEqual((sig2.count('class="gs-m"'), "gs-pcc" in sig2), (0, False))     # nada é desenhado para o que não existe
        self.assertIn("isolada", sig2)
        self.assertIn("sem geração registrada", sig2)
        self.assertEqual(gestor._ensaios_txt(None), "Ensaios: não disponível")
        html = gestor._card_html(type("E", (), {"uid": s["uid"], "origin": "commissioning"})(), s)
        for texto in ("gc-sig", "Ensaios: 0 cenário(s)", "gc-kpis", "Comissionamento concluído"):      # o cartão anterior continua inteiro
            self.assertIn(texto, html)

    @unittest.skipUnless(P.SOLVER, "Pyomo/HiGHS não instalados")
    def test_caderno_lista_cenarios_e_rodadas_desta_microrrede_sem_gravar(self):
        from seeds2.ui import caderno_ui, gestor

        uid, st, run = P.missao_24h(self.dir, "Caderno (teste)")
        sc2 = P.U.criar_cenario_v2(st, nome="Cenário sem rodadas", com_estrategia=False)          # motor por omissão = V1.6
        _uid2, st2, run2 = P.missao_passo_30(self.dir, "Outra microrrede (teste)")
        antes = (st.load().fingerprint, [r.run_uid for r in st.list_runs()], [(s.scenario_uid, s.version) for s in st.list_scenarios()])
        d = caderno_ui.dados(st, ativo=run.scenario_uid)
        self.assertEqual([r["uid"] for r in d["rodadas"]], [run.run_uid])                     # nada da outra microrrede
        self.assertNotIn(run2.run_uid, [r["uid"] for r in d["rodadas"]])
        r = d["rodadas"][0]
        self.assertEqual((r["motor"], r["estado"], r["estado_rotulo"], r["versao"], r["revisao"], r["cenario_existe"]),
                         ("V2", "concluida", "Concluída", run.scenario_version, run.config_revision, True))
        self.assertEqual(r["dados"], len(run.data))
        self.assertIn("custo realizado R$", r["resultado"])
        cen = {c["uid"]: c for c in d["cenarios"]}
        self.assertEqual(set(cen), {run.scenario_uid, sc2.scenario_uid})
        self.assertEqual((cen[run.scenario_uid]["motor"], cen[run.scenario_uid]["rodadas"], cen[run.scenario_uid]["atual"]), ("V2", {"concluida": 1}, True))
        self.assertEqual((cen[sc2.scenario_uid]["motor"], cen[sc2.scenario_uid]["rodadas"], cen[sc2.scenario_uid]["atual"]), ("V1.6", {}, False))
        self.assertEqual(d["estudos"], [])                                                    # sem Arquivo: nada é criado
        self.assertFalse((Path(self.dir) / "scientific_archive").exists())
        self.assertEqual(gestor._ensaios_txt(gestor._ensaios(st, st.load().config)), "Ensaios: 2 cenário(s) · 1 concluída(s)")
        depois = (st.load().fingerprint, [x.run_uid for x in st.list_runs()], [(x.scenario_uid, x.version) for x in st.list_scenarios()])
        self.assertEqual(antes, depois)

    @unittest.skipUnless(P.SOLVER, "Pyomo/HiGHS não instalados")
    def test_folha_usa_os_mesmos_estados_das_etapas_e_nao_muda_o_cenario(self):
        from seeds2.operation import scenarios as S
        from seeds2.ui import execution_ui, folha_ui

        _uid, st, run = P.missao_24h(self.dir, "Folha (teste)")
        cur = st.get_scenario(run.scenario_uid)
        doc = copy.deepcopy(cur.document)
        d = folha_ui.dados(st, cur, doc, "estrategia", dirty=False)
        self.assertEqual([x["id"] for x in d["secoes"]], ["inicializacao", "previsoes", "estrategia", "execucao"])
        self.assertEqual([x["id"] for x in d["secoes"] if x["atual"]], ["estrategia"])
        rd = S.readiness(doc, S.findings(doc), None)
        sec = {x["id"]: x for x in d["secoes"]}
        self.assertEqual(sec["inicializacao"]["estado"], rd["stages"]["inicializacao"][1])
        self.assertEqual(sec["previsoes"]["estado"], rd["stages"]["previsoes"][1])
        self.assertEqual(sec["estrategia"]["estado"], S.strategy_status(doc)[1])
        self.assertEqual(sec["execucao"]["estado"], execution_ui.stage_state(st, cur)[1])
        self.assertEqual((d["cenario"]["versao"], d["rodadas"], d["alterado"]), (cur.version, 1, False))
        self.assertIn("V2", d["cenario"]["motor"])
        self.assertEqual(doc, cur.document)                                                   # o cabeçalho não toca o documento
        self.assertEqual(st.get_scenario(run.scenario_uid).version, cur.version)


@unittest.skipUnless(P.NODE, "Node.js não instalado")
class CadernoEFolhaNoNavegadorTest(unittest.TestCase):
    CAD = {"cenarios": [{"uid": "sc1", "nome": "Dia útil", "versao": 3, "motor": "V2", "atualizado": "12/11 10:00", "revisao": 1, "rodadas": {"concluida": 2, "interrompida": 1}, "atual": True},
                        {"uid": "sc2", "nome": "Padrão V1.6", "versao": 1, "motor": "V1.6", "atualizado": "11/11 09:00", "revisao": 1, "rodadas": {}, "atual": False}],
           "rodadas": [{"uid": "a" * 32, "cenario_uid": "sc1", "cenario": "Dia útil", "versao": 3, "motor": "V2", "estado": "concluida", "estado_rotulo": "Concluída", "tom": "ok",
                        "criada": "12/11 10:01", "finalizada": "12/11 10:02", "revisao": 1, "resultado": "V2 · custo realizado R$ 277,53", "dados": 13, "cenario_existe": True},
                       {"uid": "b" * 32, "cenario_uid": "sc1", "cenario": "Dia útil", "versao": 2, "motor": "V2", "estado": "interrompida", "estado_rotulo": "Interrompida", "tom": "w",
                        "criada": "12/11 09:01", "finalizada": "12/11 09:02", "revisao": 1, "resultado": "", "dados": 0, "cenario_existe": True},
                       {"uid": "c" * 32, "cenario_uid": "sc9", "cenario": "Removido", "versao": 1, "motor": "V1.6", "estado": "concluida", "estado_rotulo": "Concluída", "tom": "ok",
                        "criada": "10/11 09:01", "finalizada": "10/11 09:02", "revisao": 1, "resultado": "R$ 10,00", "dados": 9, "cenario_existe": False}],
           "estudos": [{"uid": "e" * 32, "nome": "Estudo de teste", "origem": "Outra", "versoes": 2, "rodadas": 1, "verificado": True, "content_id": "0123456789abcdef", "desta": False, "importado": "12/11"}],
           "rotulos": {"concluida": "Concluída", "interrompida": "Interrompida", "falhou": "Falhou", "em_execucao": "Em execução", "preparada": "Preparada"},
           "microrrede": {"nome": "Teste", "revisao": 1}}

    def test_filtro_puro_das_rodadas(self):
        r = P.node("const R = F.rodadas, f = api.filtrarRodadas; return [f(R, {}).length, f(R, { motor: 'V2' }).length, f(R, { motor: 'V1.6' }).map((x) => x.uid[0]), "
                   "f(R, { estado: 'concluida' }).length, f(R, { motor: 'V2', estado: 'concluida' }).length, f(R, { cenario: 'sc1' }).length, api.contarRodadas(R)];",
                   self.CAD, componente="caderno", puros="filtrarRodadas, contarRodadas")
        self.assertEqual(r, [3, 2, ["c"], 2, 1, 2, {"concluida": 2, "interrompida": 1}])

    @unittest.skipUnless(P.navegador_disponivel(), "Chromium/Playwright (Node) não instalados")
    def test_caderno_filtra_no_navegador_e_devolve_as_acoes(self):
        linhas = "[...document.querySelectorAll('.pt.caderno tr[data-run]')].map((t) => t.dataset.run[0] + ':' + t.dataset.motor + ':' + t.dataset.estado)"
        passos = [["avaliar", "todas", linhas], ["clicar", '.pt.caderno [data-f="motor:V1.6"]'], ["avaliar", "v16", linhas], ["clicar", '.pt.caderno [data-f="motor:"]'],
                  ["clicar", '.pt.caderno [data-f="estado:interrompida"]'], ["avaliar", "interrompidas", linhas], ["clicar", '.pt.caderno [data-f="estado:"]'],
                  ["clicar", '.pt.caderno tr[data-run^="a"] .cd-abrir'], ["clicar", '.pt.caderno [data-sc="sc2"] .cd-folha'], ["clicar", ".pt.caderno .cd-estudo"],
                  ["avaliar", "acoes", "window.__acoes.map((a) => [a.type, a.run || a.sc || a.study, a.tab || null])"], ["texto", "t"]]
        r = P.bancada({"caderno": self.CAD}, passos=passos, componente="caderno")["caderno"]
        self.assertEqual(r["erros"], [])
        v = r["vistas"]
        self.assertEqual(v["todas"], ["a:V2:concluida", "b:V2:interrompida", "c:V1.6:concluida"])
        self.assertEqual(v["v16"], ["c:V1.6:concluida"])
        self.assertEqual(v["interrompidas"], ["b:V2:interrompida"])
        self.assertEqual(v["acoes"], [["abrir_rodada", "a" * 32, None], ["abrir_cenario", "sc2", "inicializacao"], ["abrir_estudo", "e" * 32, None]])
        for texto in ("Removido · v1 (cenário removido)", "V2 · custo realizado R$ 277,53", "Diagnóstico", "Rodadas: 2 concluída · 1 interrompida", "content_id 0123456789abcdef"):
            self.assertIn(texto, v["t"])
        vazio = {"cenarios": [], "rodadas": [], "estudos": [], "rotulos": self.CAD["rotulos"], "microrrede": {"nome": "Vazia", "revisao": 1}}
        r = P.bancada({"vazio": vazio}, passos=[["texto", "t"]], componente="caderno")["vazio"]
        self.assertEqual(r["erros"], [])
        for texto in ("Nenhum cenário", "Nenhuma rodada", "Nenhum estudo arquivado"):
            self.assertIn(texto, r["vistas"]["t"])

    @unittest.skipUnless(P.navegador_disponivel(), "Chromium/Playwright (Node) não instalados")
    def test_folha_indice_das_secoes_e_navegacao(self):
        folha = {"cenario": {"uid": "sc1", "nome": "Dia útil", "versao": 3, "motor": "V2 · MILP–MPC hierárquico (experimental)", "revisao": 1},
                 "secoes": [{"id": "inicializacao", "n": "01", "titulo": "Estado inicial", "tom": "ok", "estado": "Definida", "detalhe": "", "atual": False},
                            {"id": "previsoes", "n": "02", "titulo": "Previsões", "tom": "w", "estado": "Incompletas", "detalhe": "", "atual": True},
                            {"id": "estrategia", "n": "03", "titulo": "Motor e estratégia", "tom": "b", "estado": "Com erros", "detalhe": "", "atual": False},
                            {"id": "execucao", "n": "04", "titulo": "Missão e execução", "tom": "", "estado": "Indisponível", "detalhe": "", "atual": False}],
                 "constatacoes": {"erro": 0, "aviso": 2, "pendente": 1, "incompleto": 0}, "alterado": True, "rodadas": 3}
        passos = [["texto", "t"], ["avaliar", "atual", "[...document.querySelectorAll('.pt.folha .fl-sec[aria-current=\"step\"]')].map((b) => b.dataset.sec)"],
                  ["clicar", '.pt.folha .fl-sec[data-sec="previsoes"]'], ["clicar", '.pt.folha .fl-sec[data-sec="execucao"]'],
                  ["avaliar", "acoes", "window.__acoes.map((a) => [a.type, a.view, a.tab])"]]
        r = P.bancada({"folha": folha}, passos=passos, componente="folha")["folha"]
        self.assertEqual(r["erros"], [])
        v = r["vistas"]
        self.assertEqual(v["atual"], ["previsoes"])
        self.assertEqual(v["acoes"], [["nav", "operacao", "execucao"]])                # a seção atual não navega para si mesma
        for texto in ("Folha de ensaio", "Dia útil", "versão 3", "alterações não salvas", "2 aviso(s)", "1 pendência(s) do motor", "3 rodada(s) deste cenário"):
            self.assertIn(texto, v["t"])
        self.assertNotIn("erro(s)", v["t"])                                            # contagem zero não é mostrada


if __name__ == "__main__":
    unittest.main()
