"""UI-FINISH-01 — acabamento de interface e exportações científicas V2.

1. Bancadas na barra lateral também sem microrrede e no comissionamento (uma lista por contexto; mesma ação).
2. Catálogo: cartões recolhidos por padrão (detalhe e ações com ``display: none``; mesmas ações e chaves).
3. Etapa 04 V2: relatório do preflight compacto (mesmos itens) e o ÚNICO botão de executar no cartão de rodada.
4. Modal: o contêiner do componente fica fora do efeito «stale» do Streamlit (causa do piscar do desfoque).
5. Exportar cada gráfico da Partitura: SVG autocontido e PNG 300 ppp, tema claro ou escuro (componente REAL no navegador).
6. Documentos da rodada V2 (PDF, ZIP de figuras, Excel) sobre o dossiê do 2D-B — arquivos reais conferidos contra os dados
   gravados; diagnóstico para rodada não concluída; adulteração recusada; nenhum solver importado.

Navegador real ponta a ponta: ``tools/e2e/run_ui_finish.sh`` (``e2e_ui_finish.js`` + ``check_ui_finish.py``).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "tests")]
if AppTest is not None:
    from apptest_utils import APP_PATH

import piso3da_util as U  # noqa: E402
import piso3db_util as P  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from integracao_v2 import ui as V2UI  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.report import dossier as D  # noqa: E402
from seeds2.ui import gestor, shell  # noqa: E402

NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}
BANC = ["bancada_solar", "bancada_wind", "bancada_battery", "bancada_h2", "bancada_thermal"]


def _html(app) -> str:
    return "\n".join(h.proto.body for h in app.get("html"))


# =========================================================================================== 1. bancadas
class BancadasTest(unittest.TestCase):
    def test_cinco_bancadas_em_todos_os_contextos_sem_duplicar(self):
        for ctx in ((False, False, "gestor"), (False, False, "arquivo"), (True, False, "comissionamento"), (True, True, "operacao")):
            it = shell.sidebar_items(view=ctx[2], tab=None, is_open=ctx[0], commissioned=ctx[1])
            ids = [i["id"] for i in it]
            self.assertEqual([i for i in ids if i.startswith("bancada_")], BANC, ctx)          # mesma ordem, sem duplicar
            banc = [i for i in it if i["id"].startswith("bancada_")]
            self.assertEqual([i["acao"] for i in banc], [{"type": "bancada", "fonte": f} for f, _r, _k in shell.BANCADAS])
            self.assertEqual({i["grupo"] for i in banc}, {"Bancadas"})
            self.assertEqual(ids[-1], "alcance")

    def test_abrir_bancada_nao_depende_da_microrrede(self):
        with mock.patch.object(shell.st, "session_state", {}) as ss:
            self.assertTrue(shell.abrir_bancada("wind"))
            self.assertEqual(ss, {"energy_source": "wind"})                                   # nada da microrrede
            self.assertFalse(shell.abrir_bancada("nuclear"))


# =========================================================================================== 2. catálogo
class CatalogoTest(unittest.TestCase):
    def test_cartao_recolhido_por_padrao_so_com_html_css(self):
        css = gestor.GESTOR_CSS
        for alvo in (".gc-det", '[class*="st-key-mgca_"]'):
            self.assertRegex(css, r'(?s):not\(:has\(\.gc-x\[open\]\)\)[^{]*' + re.escape(alvo) + r'[^{]*\{ display: none !important', alvo)
        self.assertIn("@media (hover: hover)", css)                                   # hover só com mouse
        self.assertIn("@media (hover: none)", css)                                    # toque: só o clique/toque expande
        self.assertIn(':has([class*="st-key-mgca_"] :focus)', css)                   # aberto enquanto o foco está numa ação
        self.assertIn("prefers-reduced-motion", css)
        alt = gestor._alternador("x")
        self.assertIn('<details class="gc-x"><summary class="gc-tg">', alt)           # foco/Enter/Espaço/estado nativos
        self.assertIn("Passe o mouse ou clique para expandir", alt)

    @unittest.skipIf(AppTest is None, "Streamlit não instalado")
    def test_acoes_preservadas_e_escondidas_no_conteiner_do_cartao(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {**NO_ADMIN, "SEEDS2_DATA_DIR": d}):
            cfg = U.config_bateria("Catálogo UI-FINISH (teste)")
            MicrogridRegistry(d).create(cfg)
            uid = cfg["installation"]["uid"]
            app = AppTest.from_file(str(APP_PATH), default_timeout=120)
            app.run()
            self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
            html = _html(app)
            self.assertIn('class="gc-det"', html)
            self.assertIn("Passe o mouse ou clique para expandir", html)
            self.assertIn("1 equipamento(s) · Bateria", html)                       # resumo curto do recolhido
            chaves = {b.key for b in app.button}
            self.assertLessEqual({f"g_open_{uid}", f"g_zip_{uid}", f"g_pdf_{uid}", f"g_del_{uid}"}, chaves)   # mesmas ações
            self.assertEqual(MicrogridRegistry(d).get(uid).uid, uid)                 # nada alterado ao desenhar


# =========================================================================================== 3. etapa 04
def _rep(*itens, ok=None, excl=()):
    it = [{"level": lv, "area": a, "message": m, "eq_id": None, "code": None} for lv, a, m in itens]
    cont = {lv: sum(1 for x in it if x["level"] == lv) for lv in ("ok", "info", "aviso", "erro")}
    return {"ok": ok if ok is not None else not cont["erro"], "items": it, "excluded": list(excl), "counts": cont}


class PreflightCompactoTest(unittest.TestCase):
    def test_resumo_usa_os_mesmos_itens(self):
        rep = _rep(("ok", "motor", "a"), ("ok", "tempo", "b"), ("aviso", "realizacao", "c"), ("erro", "estrategia", "d"),
                   ("erro", "estrategia", "e"), ("info", "escopo", "f"))
        r = V2UI.resumo_preflight(rep)
        self.assertEqual((r["aprovadas"], r["avisos"], r["bloqueios"], r["info"]), (2, 1, 2, 1))
        self.assertEqual(r["areas_bloqueio"], ["Estratégia MILP–MPC"])              # sem repetição
        self.assertFalse(r["ok"])

    def test_bloqueio_com_texto_inteiro_e_orientacao_so_quando_inequivoca(self):
        h = V2UI._item_html({"level": "erro", "area": "estrategia", "message": "Estratégia ausente <x>"}, onde=True)
        self.assertIn("Estratégia ausente &lt;x&gt;", h)
        self.assertIn("03 · Motor e estratégia", h)
        h = V2UI._item_html({"level": "erro", "area": "causalidade", "message": "m"}, onde=True)
        self.assertNotIn("Onde revisar", h)                                          # área ambígua: sem orientação inventada


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class CartaoDeRodadaTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self._env = mock.patch.dict(os.environ, {**NO_ADMIN, "SEEDS2_DATA_DIR": self.dir})
        self._env.start()
        cfg = U.config_bateria("Cartão de rodada (teste)")
        MicrogridRegistry(self.dir).create(cfg)
        self.uid = cfg["installation"]["uid"]
        self.st = MicrogridRegistry(self.dir).open(self.uid)

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def sessao(self, sc):
        app = AppTest.from_file(str(APP_PATH), default_timeout=240)
        app.session_state["mg_active_uid"] = self.uid
        app.session_state["seeds_route"] = {"view": "operacao", "tab": "execucao"}
        app.query_params["sc"] = sc.scenario_uid
        app.run()
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        return app

    def test_bloqueado_um_so_botao_desabilitado_e_bloqueio_visivel(self):
        sc = U.criar_cenario_v2(self.st, com_estrategia=False, mutar=lambda d: d.__setitem__(E.CHAVE_MOTOR, E.MOTOR_V2))
        app = self.sessao(sc)
        bts = [b for b in app.button if b.label.startswith("▶ EXECUTAR MISSÃO V2")]
        self.assertEqual(len(bts), 1)
        self.assertEqual(bts[0].key, "op_ex_run_v2")                                  # o MESMO botão de antes
        self.assertTrue(bts[0].disabled)
        html = _html(app)
        self.assertIn('data-rc="estado" data-tom="b"', html)
        self.assertIn("Execução bloqueada", html)
        self.assertIn('data-pf="bloqueios"', html)                                   # o bloqueio aparece por extenso
        self.assertIn("NÃO pode ser executado pelo motor V2", html)
        self.assertIn('data-rc="aponta"', html)                                       # a seção aponta para o cartão
        self.assertEqual(self.st.list_runs(), [])

    def test_apto_resumo_igual_ao_preflight_e_aprovadas_recolhidas(self):
        sc = U.criar_cenario_v2(self.st)
        app = self.sessao(sc)
        pf = V2UI.PF.preparar(self.st, self.st.get_scenario(sc.scenario_uid))
        r = V2UI.resumo_preflight(pf.report())
        html = _html(app)
        self.assertIn('data-tom="ok"', html)
        self.assertIn(f"<b>{r['aprovadas']}</b>aprovadas", html)
        self.assertIn(f"<b>{r['avisos']}</b>advertências", html)
        self.assertIn(f"Ver {r['aprovadas']} verificações aprovadas", " ".join(e.label for e in app.expander))
        bt = next(b for b in app.button if b.key == "op_ex_run_v2")
        self.assertFalse(bt.disabled)
        self.assertIn(f"VERSÃO {sc.version}", bt.label)


# =========================================================================================== 4. modal
class ModalEstavelTest(unittest.TestCase):
    def test_conteiner_do_modal_fora_do_efeito_stale(self):
        css = V2UI.MODAL_ESTAVEL_CSS
        self.assertIn('.st-key-seeds_execucao[data-stale="true"]', css)
        self.assertIn("transition: none !important", css)
        self.assertIn("opacity: 1 !important", css)
        fonte = (RAIZ / "integracao_v2" / "ui.py").read_text("utf-8")
        a = fonte.index("st.html(MODAL_ESTAVEL_CSS)")
        self.assertLess(a, fonte.index('trama.pagina("execucao"', a))                 # desenhado com o componente


# =========================================================================================== 5. exportar cada gráfico
@unittest.skipUnless(P.NODE, "Node não instalado")
class PngMetadadosTest(unittest.TestCase):
    def test_chunks_png_com_crc_e_300_ppp(self):
        out = P.node("""const ihdr = [137,80,78,71,13,10,26,10, 0,0,0,13, 73,72,68,82, 0,0,0,1,0,0,0,1,8,6,0,0,0, 31,21,196,137];
          const iend = api.pngChunk("IEND", new Uint8Array(0));
          const png = new Uint8Array([...ihdr, ...iend]);
          const m = api.pngMetadados(png, { Title: "Gráfico ç", Software: "SEEDS2" });
          return { iend: Array.from(iend.slice(-4)), tam: m.length, txt: Array.from(m).map((c) => String.fromCharCode(c)).join(""),
                   nome: api.xpNome({ rodada: "abc/../d", titulo: "Bateria · SOC [%]" }, "dark", "png") };""",
                     P.marco_sintetico(), puros="pngChunk, pngMetadados, xpNome")
        self.assertEqual(out["iend"], [0xAE, 0x42, 0x60, 0x82])                       # CRC conhecido do IEND
        self.assertIn("pHYs", out["txt"])
        self.assertIn("TitleGrafico c", out["txt"].replace("\x00", ""))             # tEXt latin-1 sem acentos
        self.assertEqual(out["nome"], "seeds2_abc_d_Bateria_SOC_escuro.png")


@unittest.skipUnless(P.NODE and P.navegador_disponivel(), "Chromium/Playwright (Node) não instalados")
class ExportarGraficoNoNavegadorTest(unittest.TestCase):
    """Componente REAL (bancada): o SVG exportado é autocontido nos dois temas e o PNG tem 300 ppp declarados."""

    def test_svg_e_png_claro_e_escuro(self):
        meta = "({ titulo: 'Gráfico de teste', rodada: 'run-teste', sub: 'identificação', fontes: ['v2/intervalos.csv'], legenda: [{ t: 'Bateria', estilo: 'background-color:var(--s-bat)' }] })"
        passos = [["avaliar", "botoes", "[document.querySelectorAll('.pt .xp-btn').length, document.querySelectorAll('.pt .stage svg.trama').length]"],
                  ["avaliar", "claro", f"svgExport(document.querySelector('.pt .stage svg.trama'), 'light', {meta}).xml"],
                  ["avaliar", "escuro", f"svgExport(document.querySelector('.pt .stage svg.trama'), 'dark', {meta}).xml"],
                  ["avaliar", "png", f"pngExport(document.querySelector('.pt .stage svg.trama'), 'light', {meta}).then((r) => [r.w, r.h, Array.from(r.bytes.slice(0, 120)).map((c) => String.fromCharCode(c)).join('')])"],
                  ["avaliar", "tela", "[document.querySelector('.pt .stage svg.trama').querySelectorAll('.cur').length, document.querySelector('.pt').dataset.theme]"]]
        r = P.bancada({"m": P.marco_sintetico()}, passos=passos)["m"]
        self.assertEqual(r["erros"], [])
        v = r["vistas"]
        self.assertGreaterEqual(v["botoes"][0], v["botoes"][1])                        # cada gráfico tem o seu botão
        for tema in ("claro", "escuro"):
            x = v[tema]
            self.assertTrue(x.startswith("<?xml"), tema)
            for proibido in ("var(--", "class=", "<script", "tabindex"):
                self.assertNotIn(proibido, x, (tema, proibido))
            self.assertIn("<title>Gráfico de teste</title>", x)
            self.assertIn('"formato":"seeds2-grafico"', x)
            self.assertIn("N/D = dado ausente", x)
        num = lambda t: re.findall(r">(-?[\d.,]+)</text>", t)  # noqa: E731
        self.assertEqual(num(v["claro"]), num(v["escuro"]))                            # o tema não muda nenhum número
        self.assertNotEqual(v["claro"], v["escuro"])
        w, h, cab = v["png"]
        self.assertGreater(w, 2000)
        self.assertIn("pHYs", cab)                                                     # 300 ppp declarados
        self.assertGreater(v["tela"][0], 0)                                            # a interface conserva o cursor (só a exportação o tira)


# =========================================================================================== 6. documentos V2
class DossierPorMotorTest(unittest.TestCase):
    def test_lista_v2_e_a_do_registro(self):
        self.assertEqual(D.REQUIRED_CONCLUDED_V2, RG.OBRIGATORIOS)
        self.assertEqual(D.ENGINE_V2, E.MOTOR_V2)

    def test_recusa_cruzada_explicita(self):
        v2 = SimpleNamespace(run=SimpleNamespace(manifest={"engine": {"id": E.MOTOR_V2}}, state="concluida", data={n: {} for n in RG.OBRIGATORIOS}))
        v16 = SimpleNamespace(run=SimpleNamespace(manifest={}, state="concluida", data={n: {} for n in D.REQUIRED_CONCLUDED}))
        with self.assertRaisesRegex(D.DossierError, "motor V2"):
            D.require_complete(v2)                                                    # geradores V1.6 recusam rodada V2
        D.require_complete(v2, engine=E.MOTOR_V2)
        D.require_complete(v16)
        with self.assertRaises(D.DossierError):
            D.require_complete(v16, engine=E.MOTOR_V2)                                # geradores V2 recusam rodada V1.6
        self.assertEqual(D.missing_required(v2.run), [])


@unittest.skipUnless(P.SOLVER, "Pyomo/HiGHS não instalados")
class DocumentosV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from integracao_v2 import execucao as X

        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = cls._tmp.name
        cfg = U.config_bateria("Documentos V2 (teste)")
        MicrogridRegistry(cls.dir).create(cfg)
        cls.st = MicrogridRegistry(cls.dir).open(cfg["installation"]["uid"])
        cls.sc = U.criar_cenario_v2(cls.st, soc0=50.0, horas=12, N=3, H_L=10, tarifa=[0.5] * 8 + [1.5, 1.5] + [0.5] * 2)
        cls.rodada = X.submit(cls.st, cls.sc.scenario_uid, cls.sc.version, X.new_request_id(), background=False)
        assert cls.rodada.state == "concluida", cls.rodada.error

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def gerar(self, kind, source=None, run_uid=None):
        from integracao_v2 import documentos as DOC

        return DOC.gerar(source or self.st, run_uid or self.rodada.run_uid, kind)

    def test_zip_de_figuras_com_hashes_e_fontes_da_rodada(self):
        nome, data, mime, _w, _ = self.gerar("fig")
        self.assertTrue(nome.endswith(".zip") and mime == "application/zip")
        z = zipfile.ZipFile(io.BytesIO(data))
        man = json.loads(z.read("manifest.json"))
        self.assertEqual(man["format"], "seeds2-figures")
        self.assertEqual({e["format"] for e in man["figures"]}, {"png", "svg"})
        for e in man["figures"]:
            b = z.read(e["file"])
            self.assertTrue(b and hashlib.sha256(b).hexdigest() == e["sha256"], e["file"])
            for src in e["data_sources"]:
                self.assertEqual(src["sha256"], self.rodada.data[src["name"]]["sha256"])
        self.assertEqual(set(z.namelist()), {"manifest.json", "LEIA-ME.txt"} | {e["file"] for e in man["figures"]})

    def test_excel_igual_ao_csv_gravado_e_ausente_vazio(self):
        from openpyxl import load_workbook

        _n, data, _m, avisos, _ = self.gerar("xlsx")
        wb = load_workbook(io.BytesIO(data), read_only=True)
        linhas = list(wb["06 Intervalos"].iter_rows(values_only=True))
        texto = list(csv.reader(io.StringIO(self.st.run_data(self.rodada.run_uid, RG.N_INTERVALOS).decode("utf-8"))))
        self.assertEqual(list(linhas[0]), texto[0])
        self.assertEqual(len(linhas), len(texto))
        vazios = 0
        for r, t in zip(linhas[1:], texto[1:]):
            for v, c in zip(r, t):
                if c == "":
                    self.assertIsNone(v)                                               # ausente = célula vazia, nunca zero
                    vazios += 1
                    continue
                try:
                    f = float(c)
                except ValueError:
                    continue
                self.assertEqual(float(v), f, c)                                        # double exato
        self.assertGreater(vazios, 0)
        self.assertTrue(any("VAZIA" in a for a in avisos))
        self.assertIn("02 Indicadores", wb.sheetnames)
        self.assertIn("11 Dicionário de dados", wb.sheetnames)

    def test_pdf_da_rodada_inicio_meio_fim(self):
        from pypdf import PdfReader

        nome, data, *_ = self.gerar("pdf")
        self.assertTrue(nome.startswith("seeds2_relatorio_") and data.startswith(b"%PDF"))
        txt = [p.extract_text() for p in PdfReader(io.BytesIO(data)).pages]
        tudo = "".join(txt)
        self.assertIn(self.rodada.run_uid, tudo)
        self.assertIn("Resultados", tudo)
        self.assertIn("Limitações", txt[-1])
        self.assertIn("SINTÉTICOS", tudo)
        custo = f"{self.rodada.summary['mission']['custo_realizado_total_R']:.2f}".replace(".", ",")
        self.assertIn(custo, tudo)
        self.assertIn("Aceitação física", tudo)                                         # aceitações separadas

    def test_rodada_v16_e_v2_nao_se_misturam(self):
        from seeds2.ui import report_exports as RX

        with self.assertRaisesRegex(D.DossierError, "motor V2"):
            RX.generate(self.st, self.rodada.run_uid, "pdf")

    def test_rodada_interrompida_diagnostico_e_sem_figuras(self):
        from integracao_v2 import execucao as X
        from seeds2.report.figures import FigureError

        sc = U.criar_cenario_v2(self.st, nome="Interrompida (teste)")
        run = X.submit(self.st, sc.scenario_uid, sc.version, X.new_request_id(), background=True)
        V2UI.cancelar(self.st, run.run_uid)
        from seeds2.operation import runner

        runner.wait(run.run_uid, 300)
        if self.st.get_run(run.run_uid).state != "interrompida":
            self.skipTest("a missão concluiu antes do cancelamento")
        nome, data, *_ = self.gerar("pdf", run_uid=run.run_uid)
        self.assertTrue(nome.startswith("seeds2_diagnostico_") and data.startswith(b"%PDF"))
        nome, *_ = self.gerar("xlsx", run_uid=run.run_uid)
        self.assertTrue(nome.startswith("seeds2_diagnostico_"))
        with self.assertRaises(FigureError):
            self.gerar("fig", run_uid=run.run_uid)

    def test_dado_adulterado_e_recusado(self):
        """Um byte alterado num dado gravado (lido por um «armazenamento» adulterado, como nos testes do 3D-A) ⇒ nenhum documento."""
        st = self.st

        class Adulterado:
            def __getattr__(self, nome):
                return getattr(st, nome)

            def run_data(self, uid, nome):
                b = st.run_data(uid, nome)
                return b.replace(b"10.0", b"11.0", 1) if nome == RG.N_INTERVALOS else b
        for kind in ("pdf", "xlsx", "fig"):
            with self.assertRaises(D.DossierIntegrityError, msg=kind):
                self.gerar(kind, source=Adulterado())

    def test_sem_solver_na_geracao(self):
        codigo = ("import sys, json, os; sys.modules['pyomo'] = None; sys.modules['highspy'] = None\n"
                  "from seeds2.microgrid.registry import MicrogridRegistry\nfrom integracao_v2 import documentos as DOC\n"
                  f"st = MicrogridRegistry({self.dir!r}).open({self.rodada.microgrid_uid!r})\n"
                  f"r = [len(DOC.gerar(st, {self.rodada.run_uid!r}, k)[1]) for k in ('pdf', 'xlsx', 'fig')]\n"
                  "print(json.dumps({'tamanhos': r, 'solver': [m for m in ('pyomo.environ', 'highspy') if sys.modules.get(m)]}))")
        out = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, timeout=600,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        res = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertTrue(all(x > 1000 for x in res["tamanhos"]))
        self.assertEqual(res["solver"], [])

    def test_estudo_arquivado_exporta_os_mesmos_dados(self):
        from openpyxl import load_workbook

        from seeds2.archive import service as AS
        from seeds2.archive.store import ArchiveStore
        from seeds2.archive.view import StudyView

        estudo = AS.archive_scenario(self.st, ArchiveStore(self.dir), self.sc.scenario_uid).study
        view = StudyView(ArchiveStore(self.dir), estudo.archive_uid)
        loc = load_workbook(io.BytesIO(self.gerar("xlsx")[1]), read_only=True)
        arq = load_workbook(io.BytesIO(self.gerar("xlsx", source=view)[1]), read_only=True)
        self.assertEqual(list(loc["06 Intervalos"].iter_rows(values_only=True)), list(arq["06 Intervalos"].iter_rows(values_only=True)))


if __name__ == "__main__":
    unittest.main()
