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


if __name__ == "__main__":
    unittest.main()
