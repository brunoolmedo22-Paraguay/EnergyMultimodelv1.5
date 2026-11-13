"""UI-REDESIGN-01 — navegação, etapas do experimento e identidade visual da Planta.

1. A barra lateral troca o grupo «Console V1.6» (Simulação/Resultados V1.6) pelo grupo «Bancadas»: as cinco bancadas
   abrem pela MESMA ação dos antigos botões «ABRIR …» (``energy_source``); as vistas antigas continuam existindo (URL).
2. «Etapas do experimento» é um fluxo contínuo: cada etapa INTEIRA é o botão existente (mesma chave e rótulo acessível),
   com os MESMOS estados de antes; «próxima» = primeira etapa não concluída.
3. A Planta reutiliza os ícones e as cores do Gestor (``static/inventory.js`` e ``static/kit.css``), sem cópia.

Só apresentação e navegação: nada aqui chama o motor nem grava dados.
"""
from __future__ import annotations

import json
import os
import re
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

import piso3db_util as P  # noqa: E402
from seeds2.ui import shell  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
STATIC = RAIZ / "seeds2" / "ui" / "static"
NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}


# =========================================================================================== 1. barra lateral: Bancadas
class BarraLateralBancadasTest(unittest.TestCase):
    def test_console_v16_sai_e_as_cinco_bancadas_entram_no_lugar(self):
        it = shell.sidebar_items(view="operacao", tab=None, is_open=True, commissioned=True)
        ids = [i["id"] for i in it]
        self.assertFalse({"simulacao", "resultados"} & set(ids))
        self.assertFalse(any((i.get("grupo") or "") == "Console V1.6" for i in it))
        banc = [i for i in it if i["grupo"] == "Bancadas"]
        self.assertEqual([i["id"] for i in banc], ["bancada_solar", "bancada_wind", "bancada_battery", "bancada_h2", "bancada_thermal"])
        self.assertEqual([i["rotulo"] for i in banc], ["Solar", "Eólica", "Bateria", "H₂ / PEMFC", "Térmica"])
        self.assertEqual([i["acao"] for i in banc], [{"type": "bancada", "fonte": f} for f in ("solar", "wind", "battery", "h2", "thermal")])
        self.assertEqual([i["icone"] for i in banc], ["k:pv", "k:wind", "k:battery", "k:pemfc", "k:thermal"])   # ícones do Gestor
        self.assertEqual(ids.index("bancada_solar"), ids.index("arquivo") + 1)            # no lugar do antigo console
        self.assertEqual(ids[-1], "alcance")
        # o mesmo conjunto dos botões das bancadas (home.BENCHES), na mesma ordem
        from seeds2.ui import home
        self.assertEqual([(f, r) for f, r, _k in shell.BANCADAS], list(home.BENCHES))
        # sem microrrede e no comissionamento nada muda
        self.assertEqual([i["id"] for i in shell.sidebar_items(view="gestor", tab=None, is_open=False, commissioned=False)],
                         ["catalogo", "arquivo", "alcance"])
        self.assertEqual([i["id"] for i in shell.sidebar_items(view="comissionamento", tab=None, is_open=True, commissioned=False)],
                         ["catalogo", "comissionamento", "alcance"])
        # as vistas antigas continuam roteáveis (compatibilidade de URL e da navegação clássica), só não estão na navegação
        self.assertIn("simulacao", shell.VIEWS)
        self.assertIn("resultados", shell.VIEWS)

    @unittest.skipIf(AppTest is None, "Streamlit não instalado")
    def test_acao_bancada_abre_a_mesma_tela_dos_botoes(self):
        roteiro = ("import streamlit as st\nfrom seeds2.ui import shell\n"
                   "st.session_state['seeds_sidebar'] = {'action': ACAO}\nshell._on_sidebar()\n"
                   "st.write(repr((st.session_state.get('energy_source'), st.session_state.get('current_page'))))\n")
        casos = [({"type": "bancada", "fonte": "solar"}, ("solar", "Visão geral")),
                 ({"type": "bancada", "fonte": "wind"}, ("wind", None)), ({"type": "bancada", "fonte": "battery"}, ("battery", None)),
                 ({"type": "bancada", "fonte": "h2"}, ("h2", None)), ({"type": "bancada", "fonte": "thermal"}, ("thermal", None)),
                 ({"type": "bancada", "fonte": "mix"}, (None, None)),            # fonte fora das cinco: ignorada
                 ({"type": "bancada", "fonte": "simulacao"}, (None, None))]
        for acao, esperado in casos:
            app = AppTest.from_string(roteiro.replace("ACAO", repr(acao)), default_timeout=60)
            app.run()
            self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
            self.assertEqual(app.markdown[0].value, repr(esperado), acao)

    def test_icones_da_barra_sao_os_do_gestor(self):
        js = (STATIC / "trama" / "sidebar.js").read_text(encoding="utf-8")
        self.assertIn("ICONES_GESTOR", js)
        self.assertIn('"data-acao": it.acao.type', js)
        self.assertNotIn("simulacao: \"M5 4l14 8", js.split("const ICO_SB")[0])      # nenhum ícone antigo usado pelas bancadas


# =========================================================================================== identidade reutilizada do Gestor
@unittest.skipUnless(P.NODE, "Node.js não instalado")
class IdentidadeDoGestorTest(unittest.TestCase):
    def test_icones_e_cores_sao_extraidos_sem_copia(self):
        from seeds2.ui import trama

        inv = (STATIC / "inventory.js").read_text(encoding="utf-8")
        tp = (STATIC / "techpicker.js").read_text(encoding="utf-8")
        avaliar = lambda fonte, nome: json.loads(P.subprocess.run(  # noqa: E731
            [P.NODE, "-e", fonte + f"\nconsole.log(JSON.stringify({nome}));"], capture_output=True, text=True, check=True).stdout)
        bloco = lambda src: re.search(r"const ICONS = \{.*?\n\};", src, re.S).group(0)  # noqa: E731
        g = avaliar(trama.icones_gestor_js(), "ICONES_GESTOR")
        self.assertEqual(g, avaliar(bloco(inv), "ICONS"))                                  # = Gestor (inventário)
        self.assertEqual(g, avaliar(bloco(tp), "ICONS"))                                   # = seletor de tecnologia
        self.assertEqual(set(g), {"pv", "wind", "battery", "pemfc", "thermal"})
        kit = (STATIC / "kit.css").read_text(encoding="utf-8")
        css = trama.tokens_gestor_css()
        for k in ("pv", "wind", "battery", "pemfc", "thermal", "load"):
            cor = re.search(rf"--k-{k}:\s*(#[0-9A-Fa-f]+);", kit).group(1)
            self.assertIn(f"--k-{k}: {cor};", css)
        self.assertTrue(css.startswith(".pt {"))                                           # escopo dos componentes Partitura


# =========================================================================================== 3. Planta
class PlantaIdentidadeTest(unittest.TestCase):
    @unittest.skipUnless(P.NODE and P.navegador_disponivel(), "Chromium/Playwright (Node) não instalados")
    def test_nos_com_icone_em_circulo_cor_do_gestor_e_interacao_preservada(self):
        from test_piso3db_plataforma import _planta_sintetica

        passos = [["avaliar", "nos", "[...document.querySelectorAll('.pt.planta .node')].map((n) => [n.dataset.uid, n.dataset.tipo, "
                   "n.querySelectorAll('.ico svg').length, n.querySelectorAll('.ico circle.ico-fundo').length, n.style.getPropertyValue('--k'), "
                   "getComputedStyle(n.querySelector('.ico')).color, n.querySelector('text.tp').textContent])"],
                  ["avaliar", "setas", "document.querySelectorAll('.pt.planta svg marker, .pt.planta svg animate, .pt.planta svg animateMotion').length"],
                  ["avaliar", "pinos", "document.querySelectorAll('.pt.planta .node .pino').length"],
                  ["clicar", '.pt.planta .node[data-uid="eq-fc"]'], ["avaliar", "sel", "document.querySelector('.pt.planta .col').textContent"],
                  ["avaliar", "aria", "document.querySelector('.pt.planta .node[data-uid=\"eq-fv\"]').getAttribute('aria-label')"]]
        r = P.bancada({"planta": _planta_sintetica()}, passos=passos, componente="planta")["planta"]
        self.assertEqual(r["erros"], [])
        v = r["vistas"]
        nos = {n[0]: n for n in v["nos"]}
        self.assertEqual(set(nos), {"eq-fv", "eq-wt1", "eq-wt2", "eq-fc", "eq-term", "eq-bat1", "eq-bat2", "demanda", "PCC"})
        for uid, (_u, _t, n_svg, n_circ, _k, _c, _tp) in nos.items():
            self.assertEqual((n_svg, n_circ), (1, 1), uid)                 # um ícone num círculo claro por nó
        cores = {"fv": "var(--k-pv)", "wt": "var(--k-wind)", "fc": "var(--k-pemfc)", "term": "var(--k-thermal)",
                 "bat": "var(--k-battery)", "dem": "var(--k-load)"}
        for uid, (_u, tipo, *_r, kvar, _cor, _tp) in nos.items():
            if tipo in cores:
                self.assertEqual(kvar, cores[tipo], uid)                   # a cor da tecnologia é a do Gestor
        rgb = {"fv": "rgb(224, 137, 30)", "wt": "rgb(47, 111, 237)", "bat": "rgb(60, 157, 93)", "fc": "rgb(14, 124, 134)"}
        for uid, (_u, tipo, *_r, cor, _tp) in nos.items():
            if tipo in rgb:
                self.assertEqual(cor, rgb[tipo], uid)                      # tokens de kit.css realmente aplicados
        self.assertTrue(nos["eq-fv"][6].startswith("SOLAR"))
        self.assertTrue(nos["demanda"][6].startswith("DEMANDA"))
        self.assertEqual(v["setas"], 0)                                     # sem setas nem animação de fluxo
        self.assertEqual(v["pinos"], 9)                                     # cada nó liga ao barramento num ponto
        self.assertIn("selecionado", v["sel"])
        self.assertIn("Solar fotovoltaica", v["aria"])

    def test_icones_proprios_so_para_demanda_e_pcc(self):
        js = (STATIC / "trama" / "planta.js").read_text(encoding="utf-8")
        self.assertIn("ICONES_GESTOR", js)
        for k in ("pv", "wind", "battery", "pemfc", "thermal"):
            self.assertNotIn(f"\n  {k}: `<svg", js)                         # nenhuma cópia dos ícones do Gestor
        self.assertIn("dem: `<svg", js)
        self.assertIn("grid: `<svg", js)


# =========================================================================================== 2. etapas do experimento
@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class EtapasFluxoTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        self._env = mock.patch.dict(os.environ, NO_ADMIN)
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def _app(self, uid, sc=None):
        from apptest_utils import APP_PATH

        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=240)
        app.session_state["mg_active_uid"] = uid
        app.session_state["seeds_route"] = {"view": "operacao", "tab": None}
        if sc:
            app.query_params["sc"] = sc
        app.run()
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        return app

    @staticmethod
    def _etapas(app) -> list[tuple[str, str, str]]:
        html = "\n".join(h.proto.body for h in app.get("html"))
        return re.findall(r'<div class="et" data-etapa="(\w+)" data-tom="(\w+)" data-prox="(\d)">', html), html

    def test_fluxo_com_os_mesmos_estados_e_o_botao_existente_como_alvo(self):
        import piso3da_util as U
        from seeds2.microgrid.registry import MicrogridRegistry
        from seeds2.operation import scenarios as S
        from seeds2.operation import service as SV
        from seeds2.ui import execution_ui

        cfg = U.config_bateria("Etapas (teste)")
        MicrogridRegistry(self.dir).create(cfg)
        uid = cfg["installation"]["uid"]
        st = MicrogridRegistry(self.dir).open(uid)
        sc = SV.create(st, name="Novo")
        app = self._app(uid, sc.scenario_uid)
        etapas, html = self._etapas(app)
        self.assertEqual([e[0] for e in etapas], ["inicializacao", "previsoes", "estrategia", "execucao"])
        doc = app.session_state["op_work"]
        fs = S.findings(doc)
        rd = S.readiness(doc, fs, None)
        esperado = [rd["stages"]["inicializacao"][0], rd["stages"]["previsoes"][0], S.strategy_status(doc)[0],
                    execution_ui.stage_state(st, st.get_scenario(sc.scenario_uid))[0]]
        self.assertEqual([e[1] for e in etapas], esperado)                    # os MESMOS estados de antes
        prox = next(i for i, t in enumerate(esperado) if t != "ok")
        self.assertEqual([e[2] for e in etapas], ["1" if i == prox else "0" for i in range(4)])
        self.assertIn("Não executável", html)                                  # impedimento real visível (sem estratégia)
        botoes = {b.key: b for b in app.button}
        for k, rot in (("op_open_init", "ABRIR INICIALIZAÇÃO"), ("op_open_fc", "ABRIR PREVISÕES"),
                       ("op_open_sg", "ABRIR ESTRATÉGIA EMS"), ("op_open_ex", "ABRIR EXECUÇÃO")):
            self.assertEqual(botoes[k].label, rot)                             # o alvo é o botão existente (mesma chave)
            self.assertFalse(botoes[k].disabled)
        self.assertIn(".st-key-op_etapas", html)
        botoes["op_open_sg"].click().run()
        self.assertEqual(app.session_state["seeds_route"], {"view": "operacao", "tab": "estrategia"})
        self.assertEqual(st.get_scenario(sc.scenario_uid).version, sc.version)   # navegar não grava nada

    def test_sem_cenario_as_etapas_ficam_indisponiveis(self):
        import piso3da_util as U
        from seeds2.microgrid.registry import MicrogridRegistry

        cfg = U.config_bateria("Sem cenário (teste)")
        MicrogridRegistry(self.dir).create(cfg)
        app = self._app(cfg["installation"]["uid"])
        etapas, html = self._etapas(app)
        self.assertEqual([e[1] for e in etapas], ["off"] * 4)
        self.assertEqual([e[2] for e in etapas], ["0"] * 4)
        self.assertTrue(all(b.disabled for b in app.button if b.key in ("op_open_init", "op_open_fc", "op_open_sg", "op_open_ex")))
        self.assertIn("Selecione um cenário", html)
        # bancadas no celular: o bloco existe (escondido no desktop por CSS), com os botões de sempre
        self.assertIn("@media (min-width: 761px) { .st-key-op_bancadas_movel { display: none !important; } }", html)
        self.assertNotIn("Ferramentas V1.6", "\n".join(e.label for e in app.expander))
        self.assertTrue({"home_bench_solar", "home_bench_h2"} <= {b.key for b in app.button})


if __name__ == "__main__":
    unittest.main()
