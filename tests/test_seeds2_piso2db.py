"""Piso 2D-B — Relatórios científicos, Excel e figuras (domínio, sem interface; ver ``test_seeds2_piso2db_app.py``).

Cobre: contrato de leitura unificado (rodada local × estudo arquivado), PDF de rodada concluída local e arquivada,
igualdade de indicadores e identificadores entre as origens, PDF diagnóstico de rodadas falha/interrompida sem
resultados fictícios, Excel completo (todas as colunas das entradas, do despacho e dos modelos; precisão bit a bit;
timestamps e fusos; ausentes ≠ zero; texto nunca vira fórmula), figuras PNG/SVG válidas e ZIP com manifesto e hashes,
recusa de dados corrompidos/ausentes, nomes/conteúdos maliciosos, exportação SEM chamar o motor e SEM alterar rodadas,
cenários ou estudos, instalação limpa sem a microrrede original, combinações de fontes (sem bateria, sem PEMFC, sem FV)
e — prova científica — rodada real exportada, importada numa instalação LIMPA e documentada com o motor sabotado.

Dados: inventário fictício equivalente à configuração padrão V1.6 e perfis de referência da própria V1.6.
"""
from __future__ import annotations

import copy
import io
import json
import math
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from hashlib import sha256
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader

import orchestrator_runtime as RT
from ems_integration import despacho
from seeds2.archive import exporter
from seeds2.archive.store import ArchiveStore
from seeds2.archive.view import StudyView
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.operation import runner
from seeds2.operation import strategy as SG
from seeds2.report import dossier as D
from seeds2.report import figures as FG
from seeds2.report import run_pdf as RP
from seeds2.report import xlsx as X
from seeds2.ui import report_exports as RX
from seeds2_fixtures import v16_equivalent_config
from test_seeds2_piso2c import ready
from test_seeds2_piso2da import _dump, build_study

RAIZ = Path(__file__).resolve().parents[1]
EVIL_SCN = '=HYPERLINK("http://evil")<b>negrito</b><script>alert(1)</script>/../..\\x\x07'
EVIL_MG = 'Evil <i>&amp;</i> ../../etc/passwd @SUM(1)'


def _sabotage():
    """Motor e modelos substituídos por exceções: qualquer chamada falha o teste."""
    boom = AssertionError("o motor/modelos NÃO podem ser chamados por um exportador")
    return [mock.patch.object(RT, "run_optimizer", side_effect=boom),
            mock.patch.object(RT, "build_exchange_package", side_effect=boom),
            mock.patch.object(RT, "_simulate_solar", side_effect=boom),
            mock.patch.object(RT, "_simulate_wind", side_effect=boom),
            mock.patch.object(RT, "series_dataframe", side_effect=boom),
            mock.patch.object(despacho, "relatorio", side_effect=boom),
            mock.patch.object(runner, "submit", side_effect=boom)]


class _Sab:
    def __enter__(self):
        self.p = _sabotage()
        for x in self.p:
            x.start()

    def __exit__(self, *a):
        for x in self.p:
            x.stop()


def _pdf_text(data: bytes) -> str:
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)


def _archive_dump(arch: ArchiveStore) -> dict:
    con = sqlite3.connect(f"file:{Path(arch.path)}?mode=ro", uri=True)
    try:
        tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]
        return {t: con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tabs}
    finally:
        con.close()


def _make(reg, mg_name, *, drop=(), **kw):
    cfg = v16_equivalent_config(mg_name)
    cfg["equipment"] = [e for e in cfg["equipment"] if e["kind"] not in drop]
    if "battery" in drop:
        cfg["run_conditions"]["battery_soc0_pct"] = {}
    reg.create(cfg, origin="commissioning")
    st = reg.open(cfg["installation"]["uid"])
    sc = ready(st, **kw)
    run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
    assert run.state == "concluida", run.error
    return st, run


class _Fixture:
    """Origem (uma vez por módulo): estudo completo (concluída REAL, falha, interrompida) exportado + variantes."""
    _done = None

    @classmethod
    def get(cls):
        if cls._done is None:
            tmp = tempfile.TemporaryDirectory()
            reg = MicrogridRegistry(tmp.name)
            cfg = v16_equivalent_config("Industrial A")
            reg.create(cfg, origin="commissioning")
            st = reg.open(cfg["installation"]["uid"])
            info = build_study(st)
            pkg, _ = exporter.export_bytes(st, info["scenario_uid"])
            var = {
                "sem_bateria": _make(reg, "Sem bateria", drop=("battery",)),
                "sem_pemfc": _make(reg, "Sem PEMFC", drop=("pemfc",)),
                "sem_fv": _make(reg, "Sem FV", drop=("pv",), climate=False),
                "malicioso": _make(reg, EVIL_MG, name=EVIL_SCN),
                "sem_fuso": _make(reg, "Sem fuso", demand_tz=None, climate_tz=None, mission_tz=None,
                                  clock=SG.UNDECLARED_CLOCK),
            }
            cls._done = (tmp, reg, st, info, pkg, var)
        return cls._done


def setUpModule():
    _Fixture.get()


class _Base(unittest.TestCase):
    def setUp(self):
        self.src_tmp, self.reg, self.store, self.info, self.pkg, self.var = _Fixture.get()
        self.done = self.info["done"]
        self._tmp = tempfile.TemporaryDirectory()
        self.dest = self._tmp.name                       # instalação LIMPA (sem microrredes)
        self.archive = ArchiveStore(self.dest)
        self.archive_uid = self.archive.import_package(self.pkg).study.archive_uid

    def tearDown(self):
        self._tmp.cleanup()

    def view(self) -> StudyView:
        return StudyView(ArchiveStore(self.dest), self.archive_uid)


# =========================================================================== contrato unificado
class ContratoTest(_Base):
    def test_identidade_e_impressoes_digitais_iguais_nas_duas_origens(self):
        loc = D.load(self.store, self.done.run_uid)
        arc = D.load(self.view(), self.done.run_uid)
        self.assertEqual((loc.kind, arc.kind), (D.LOCAL, D.ARCHIVED))
        self.assertEqual(loc.identity(), arc.identity())
        idt = arc.identity()
        self.assertEqual(idt["microgrid_uid"], self.store.load().config["installation"]["uid"])
        self.assertEqual(idt["microgrid_name"], "Industrial A")
        self.assertEqual(idt["scenario_fingerprint"], self.done.scenario_fingerprint)
        self.assertEqual(idt["config_fingerprint"], self.done.config_fingerprint)
        self.assertEqual(idt["microgrid_incarnation"], self.done.incarnation)
        self.assertEqual(loc.scenario, arc.scenario)                                # documento EXATO da versão executada
        self.assertEqual(loc.inventory, arc.inventory)                              # revisão de referência do estudo
        self.assertEqual(arc.archive["archive_uid"], self.archive_uid)

    def test_indicadores_iguais_e_iguais_ao_resumo_persistido(self):
        a = D.indicators(D.load(self.store, self.done.run_uid))
        b = D.indicators(D.load(self.view(), self.done.run_uid))
        self.assertEqual(a, b)
        s = self.done.summary
        by = {i.key: i.value for i in a}
        for k in ("custo_total_rs", "energia_demanda_kWh", "energia_atendida_kWh", "energia_nao_atendida_kWh",
                  "energia_excedente_kWh", "energia_solar_kWh", "h2_kg", "passos_inviaveis", "tempo_otimizador_s"):
            self.assertEqual(by[k], s[k], k)                                         # valor EXATO, sem recálculo
        self.assertEqual(by["soc_final.bateria"], s["soc_final"]["bateria"])
        self.assertAlmostEqual(by["custo_total_rs"], 88.3190884544543, places=10)   # = rodada de referência V1.6

    def test_rodada_em_execucao_e_inexistente_recusadas(self):
        with self.assertRaises(D.DossierError):
            D.load(self.store, "f" * 32)
        run = self.done
        with mock.patch.object(self.store, "get_run", return_value=type(run)(**{**run.__dict__, "state": "em_execucao"})):
            with self.assertRaisesRegex(D.DossierError, "em execução"):
                D.load(self.store, run.run_uid)


# =========================================================================== PDF
class PdfTest(_Base):
    def test_pdf_rodada_local_concluida(self):
        name, data, mime, _, _ = RX.generate(self.store, self.done.run_uid, "pdf")
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertTrue(name.endswith(".pdf") and "/" not in name)
        rd = PdfReader(io.BytesIO(data))
        self.assertGreaterEqual(len(rd.pages), 8)
        txt = _pdf_text(data)
        for t in ("Relatório de Simulação de Microrrede".upper(), "Industrial A", "Alta demanda", self.done.run_uid,
                  self.done.microgrid_uid, self.done.scenario_uid, self.done.scenario_fingerprint,
                  self.done.config_fingerprint, self.done.incarnation, "Resumo executivo", "Configuração da microrrede",
                  "Condições iniciais", "Previsões e dados de entrada", "Estratégia e metodologia computacional",
                  "Resultados energéticos", "Armazenamento e hidrogênio", "Discussão técnica",
                  "Procedência científica e rastreabilidade", "Limitações", "Rodada local", "R$ 88,32", "88,3191",
                  "NÃO é uma nova execução do EMS", self.done.manifest["software"]["science"]["sha256"]):
            self.assertIn(t, txt, t)
        for n, idx in self.done.data.items():
            self.assertIn(idx["sha256"], txt, n)                                     # hashes dos dados persistidos
        self.assertNotIn("globalmente ótimo", txt)
        self.assertIn("não implica otimalidade global", txt)
        self.assertEqual(rd.metadata.get("/Subject"), f"Rodada {self.done.run_uid}")

    def test_pdf_rodada_arquivada_identica_em_conteudo_cientifico(self):
        with _Sab():
            _, data, *_ = RX.generate(self.view(), self.done.run_uid, "pdf")
        txt = _pdf_text(data)
        self.assertIn("Estudo arquivado", txt)
        self.assertIn("produzidos na instalação de ORIGEM", txt)
        self.assertIn(self.archive_uid, txt)
        _, loc, *_ = RX.generate(self.store, self.done.run_uid, "pdf")
        ltxt = _pdf_text(loc)
        for t in ("R$ 88,32", "65,4847", "3,4997", "55,0 %", self.done.run_uid, self.done.microgrid_uid,
                  self.done.scenario_fingerprint, self.done.config_fingerprint, self.done.incarnation):
            self.assertIn(t, txt, t)
            self.assertIn(t, ltxt, t)

    def test_graficos_com_eixos_e_unidades_no_pdf(self):
        _, data, *_ = RX.generate(self.store, self.done.run_uid, "pdf")
        txt = _pdf_text(data)                                                         # figuras VETORIAIS: texto extraível
        for t in ("Demanda e potência por fonte", "Potência (kW)", "Estado de carga (%)", "H₂ (kg)",
                  "Data e hora (fuso da missão)", "SOC mín. efetivo", "Figura 1.", "Figura 6."):
            self.assertIn(t, txt, t)

    def test_pdf_diagnostico_de_rodadas_nao_concluidas_sem_resultados(self):
        for key in ("failed", "interrupted"):
            run = self.info[key]
            name, data, *_ = RX.generate(self.view(), run.run_uid, "pdf")
            self.assertTrue(name.startswith("seeds2_diagnostico_"))
            txt = _pdf_text(data)
            self.assertIn("RELATÓRIO DIAGNÓSTICO", txt.upper())
            self.assertIn("Diagnóstico da rodada", txt)
            self.assertIn(run.run_uid, txt)
            for absent in ("Resultados energéticos", "Resumo executivo", "Figura 1", "Custo total", "Armazenamento e "
                           "hidrogênio", "Relatório de Simulação"):
                self.assertNotIn(absent, txt, (key, absent))
        txt = _pdf_text(RX.generate(self.view(), self.info["failed"].run_uid, "pdf")[1])
        self.assertIn("solver sabotado no teste", txt)                               # erro registrado, não inventado


# =========================================================================== Excel
def _wb(data: bytes):
    return load_workbook(io.BytesIO(data))


def _csv_cells(raw: bytes) -> tuple[list[str], list[list[str]]]:
    import csv

    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
    return rows[0], rows[1:]


class ExcelTest(_Base):
    @classmethod
    def setUpClass(cls):
        _, cls.store_, cls.info_ = _Fixture.get()[1], _Fixture.get()[2], _Fixture.get()[3]
        cls.res = X.build_workbook(D.load(cls.store_, cls.info_["done"].run_uid))
        cls.wb = _wb(cls.res.data)

    def _sheet_frame(self, name: str) -> pd.DataFrame:
        return pd.read_excel(io.BytesIO(self.res.data), sheet_name=name)

    def test_folhas_e_todas_as_colunas_de_entradas_despacho_e_modelos(self):
        names = self.wb.sheetnames
        for s in ("00 Índice", "01 Identificação", "02 Indicadores", "03 Equipamentos", "04 Condições iniciais",
                  "05 Estratégia EMS", "06 Entradas", "07 Despacho EMS", "08 Previsão demanda", "08 Previsão clima",
                  "10 Procedência", "11 Dicionário de dados"):
            self.assertIn(s, names)
        d = D.load(self.store_, self.info_["done"].run_uid)
        for sheet, data in (("06 Entradas", D.CSV_INPUTS), ("07 Despacho EMS", D.CSV_OUTPUTS)):
            head, rows = _csv_cells(d.raw(data))
            ws = self.wb[sheet]
            self.assertEqual([c.value for c in ws[1]], head)                           # cabeçalho = nomes EXATOS
            self.assertEqual(ws.max_row - 1, len(rows))
        models = d.model_tables()
        self.assertGreaterEqual(len(models), 3)
        for m in models:
            stem = m[len("modelos/"):-4]
            sheet = next(n for n in names if n.startswith("09 ") and stem.startswith(n[3:].rstrip()))
            head, rows = _csv_cells(d.raw(m))
            ws = self.wb[sheet]
            self.assertEqual([c.value for c in ws[1]], head, m)
            self.assertEqual(ws.max_row - 1, len(rows), m)
        dic = self._sheet_frame("11 Dicionário de dados")
        out = d.outputs()
        self.assertEqual(set(dic[dic["folha"] == "07 Despacho EMS"]["coluna"]), set(out.columns))

    def test_precisao_numerica_bit_a_bit(self):
        """Cada número do Excel é o MESMO double do CSV persistido (texto do CSV → float, sem tolerância)."""
        d = D.load(self.store_, self.info_["done"].run_uid)
        checked = 0
        for sheet, data in (("06 Entradas", D.CSV_INPUTS), ("07 Despacho EMS", D.CSV_OUTPUTS),
                            *[(n, m) for m in d.model_tables() for n in self.wb.sheetnames
                              if n.startswith("09 ") and m[8:-4].startswith(n[3:])]):
            head, rows = _csv_cells(d.raw(data))
            ws = self.wb[sheet]
            for r, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
                for j, v in enumerate(row):
                    txt = rows[r][j]
                    if head[j].startswith("timestamp"):
                        continue
                    try:
                        f = float(txt)
                    except ValueError:
                        self.assertEqual("" if v is None else str(v), txt, (sheet, head[j]))   # texto preservado
                        continue
                    if txt == "":
                        self.assertIsNone(v)
                    elif math.isnan(f):
                        self.assertIsNone(v, "NaN deve ser célula vazia, nunca zero")
                    elif isinstance(v, bool):
                        self.assertEqual(float(v), f)
                    else:
                        self.assertEqual(float(v).hex(), f.hex(), (sheet, head[j], r))   # igualdade de BITS
                    checked += 1
        self.assertGreater(checked, 5000)
        ind = self._sheet_frame("02 Indicadores")
        cost = ind[ind["chave"] == "custo_total_rs"]["valor"].iloc[0]
        self.assertEqual(float(cost).hex(), self.info_["done"].summary["custo_total_rs"].hex())

    def test_escritor_numerico_casos_extremos(self):
        b = X._Book()
        ws = b.wb.create_sheet("t")
        vals = [0.1 + 0.2, 1 / 3, 5e-324, 1.7976931348623157e308, -0.0, 2.0 ** 53, 123456789.12345679, 1e-15]
        ws.append([b.number(ws, v) for v in vals] + [b.number(ws, float("nan")), b.number(ws, float("inf")),
                                                       b.number(ws, 2 ** 60), b.number(ws, True)])
        buf = io.BytesIO()
        b.wb.save(buf)
        row = next(load_workbook(io.BytesIO(buf.getvalue()))["t"].iter_rows(values_only=True))
        for v, w in zip(vals, row):
            self.assertEqual(float(w).hex(), float(v).hex())
        self.assertIsNone(row[len(vals)])                                             # NaN → vazio
        self.assertEqual(row[len(vals) + 1], "inf")
        self.assertEqual(row[len(vals) + 2], str(2 ** 60))                            # > 2^53 → texto (sem perda)
        self.assertIs(row[len(vals) + 3], True)
        self.assertEqual((b.stats.nan, b.stats.inf, b.stats.big_int), (1, 1, 1))

    def test_timestamps_e_fusos(self):
        d = D.load(self.store_, self.info_["done"].run_uid)
        out = d.outputs()
        ws = self.wb["07 Despacho EMS"]
        head = [c.value for c in ws[1]]
        for col in ("timestamp_utc", "timestamp_local", "timestamp_runtime"):
            j = head.index(col)
            cells = [r[j] for r in ws.iter_rows(min_row=2)]
            self.assertTrue(all(c.is_date and c.number_format == X.DATETIME_FMT for c in cells), col)
            self.assertEqual([c.value.strftime("%Y-%m-%dT%H:%M:%S") for c in cells],
                             [s.rstrip("Z") for s in out[col]], col)
            self.assertIsNotNone(ws[1][j].comment)
        dic = self._sheet_frame("11 Dicionário de dados")
        ref = dict(zip(dic[dic["folha"] == "07 Despacho EMS"]["coluna"], dic[dic["folha"] == "07 Despacho EMS"]["referência temporal"]))
        self.assertEqual(ref["timestamp_utc"], "UTC")
        self.assertIn("America/Sao_Paulo", ref["timestamp_local"])
        # missão SEM fuso declarado: nunca rotulada como UTC
        st, run = _Fixture.get()[5]["sem_fuso"]
        res = X.build_workbook(D.load(st, run.run_uid))
        dic = pd.read_excel(io.BytesIO(res.data), sheet_name="11 Dicionário de dados")
        refs = set(dic[(dic["folha"] == "07 Despacho EMS") & dic["coluna"].str.startswith("timestamp_")]["referência temporal"])
        self.assertTrue(all("não declarado" in r for r in refs if r != "grade uniforme do runtime (início no relógio local)"), refs)
        self.assertNotIn("UTC", refs)

    def test_ausentes_nunca_viram_zero(self):
        d = D.load(self.store_, self.info_["done"].run_uid)
        for m in d.model_tables():
            df = d.table(m)
            if df.isna().any().any():
                sheet = next(n for n in self.wb.sheetnames if n.startswith("09 ") and m[8:-4].startswith(n[3:]))
                xl = self._sheet_frame(sheet)
                self.assertEqual(int(xl.isna().sum().sum()), int(df.isna().sum().sum()), m)
        self.assertTrue(any("célula VAZIA" in w for w in self.res.warnings))

    def test_indicadores_excel_iguais_entre_origens(self):
        a = X.build_workbook(D.load(self.store_, self.info_["done"].run_uid))
        with _Sab():
            b = X.build_workbook(D.load(self.view(), self.info_["done"].run_uid))
        fa = pd.read_excel(io.BytesIO(a.data), sheet_name="02 Indicadores")
        fb = pd.read_excel(io.BytesIO(b.data), sheet_name="02 Indicadores")
        pd.testing.assert_frame_equal(fa, fb)
        for s in ("06 Entradas", "07 Despacho EMS"):
            pd.testing.assert_frame_equal(pd.read_excel(io.BytesIO(a.data), sheet_name=s),
                                          pd.read_excel(io.BytesIO(b.data), sheet_name=s), check_exact=True)
        idb = pd.read_excel(io.BytesIO(b.data), sheet_name="01 Identificação", header=2)
        vals = set(map(str, idb.iloc[:, 1].dropna()))
        for v in (self.info_["done"].run_uid, self.info_["done"].microgrid_uid, self.info_["done"].scenario_fingerprint,
                  self.info_["done"].config_fingerprint, self.archive_uid):
            self.assertIn(v, vals)

    def test_diagnostico_excel_sem_series_de_resultado(self):
        res = X.build_workbook(D.load(self.view(), self.info["failed"].run_uid))
        names = _wb(res.data).sheetnames
        self.assertIn("02 Diagnóstico", names)
        for s in ("02 Indicadores", "06 Entradas", "07 Despacho EMS"):
            self.assertNotIn(s, names)

    def test_limite_de_linhas_divide_explicitamente_e_limite_de_celulas_recusa(self):
        d = D.load(self.store_, self.info_["done"].run_uid)
        with mock.patch.object(X, "DATA_ROWS_PER_SHEET", 10):
            res = X.build_workbook(d)
        names = _wb(res.data).sheetnames
        parts = [n for n in names if n.startswith("07 Despacho EMS p")]
        self.assertEqual(len(parts), 4)                                               # 31 linhas → 4 partes de ≤ 10
        total = sum(pd.read_excel(io.BytesIO(res.data), sheet_name=p).shape[0] for p in parts)
        self.assertEqual(total, len(d.outputs()))                                     # nenhuma linha omitida
        self.assertTrue(any("divididas em 4 folhas" in w for w in res.warnings))
        with mock.patch.object(X, "MAX_CELLS", 100):
            with self.assertRaisesRegex(X.WorkbookLimitError, "seeds2study"):
                X.build_workbook(d)


# =========================================================================== figuras
class FigurasTest(_Base):
    @classmethod
    def setUpClass(cls):
        st, info = _Fixture.get()[2], _Fixture.get()[3]
        cls.d = D.load(st, info["done"].run_uid)
        cls.specs = FG.run_figures(cls.d)

    def test_catalogo_minimo_com_eixos_e_unidades(self):
        keys = [s.key for s in self.specs]
        for k in ("01_demanda_potencia_por_fonte", "02_estado_de_carga_bateria", "03_hidrogenio_acumulado",
                  "04_entradas_da_missao", "05_previsao_demanda", "06_previsao_clima"):
            self.assertIn(k, keys)
        for s in self.specs:
            lay = s.plotly.layout
            ytitles = [lay[k].title.text for k in lay if k.startswith("yaxis") and lay[k].title.text]
            self.assertTrue(ytitles, s.key)
            self.assertTrue(all(any(u in y for u in ("kW", "%", "kg", "W/m²", "°C", "m/s", "°", "hPa")) for y in ytitles), (s.key, ytitles))
            self.assertTrue(s.units and s.description)

    def test_png_valido_300_dpi_fundo_branco(self):
        b = FG.render(self.specs[0], "png")
        im = Image.open(io.BytesIO(b))
        im.load()
        self.assertEqual(im.format, "PNG")
        self.assertGreaterEqual(im.size[0], 1900)                                     # 170 mm a 300 dpi
        self.assertAlmostEqual(im.info["dpi"][0], 300, delta=1)
        self.assertEqual(im.convert("RGB").getpixel((3, 3)), (255, 255, 255))

    def test_svg_vetorial_valido(self):
        for s in self.specs:
            b = FG.render(s, "svg")
            root = ET.fromstring(b)
            self.assertTrue(root.tag.endswith("svg"))
            ns = "{http://www.w3.org/2000/svg}"
            self.assertGreater(len(root.findall(f".//{ns}path")), 20, s.key)
            self.assertEqual(root.findall(f".//{ns}image"), [], "SVG não pode embutir imagem rasterizada")
            self.assertNotIn(b"<script", b.lower())
            self.assertEqual(b, FG.render(s, "svg"))                                  # determinístico

    def test_zip_de_figuras_manifesto_e_hashes(self):
        data, man = FG.figures_zip(self.d)
        zf = zipfile.ZipFile(io.BytesIO(data))
        names = zf.namelist()
        self.assertIn("manifest.json", names)
        self.assertIn("LEIA-ME.txt", names)
        m = json.loads(zf.read("manifest.json"))
        self.assertEqual(m, json.loads(json.dumps(man)))
        self.assertEqual(m["format"], "seeds2-figures")
        self.assertEqual(m["experiment"]["run_uid"], self.d.run_uid)
        self.assertEqual(m["experiment"]["scenario_fingerprint"], self.d.run.scenario_fingerprint)
        self.assertEqual(m["generator"]["app_version"], D.APP_VERSION)
        files = {e["file"] for e in m["figures"]}
        self.assertEqual(files, {n for n in names if n.startswith("figuras/")})
        self.assertEqual(len(files), 2 * len(self.specs))
        for e in m["figures"]:
            self.assertEqual(sha256(zf.read(e["file"])).hexdigest(), e["sha256"])
            self.assertTrue(e["units"] and e["description"] and e["title"])
            for src in e["data_sources"]:
                if src["kind"] == "dado_da_rodada":
                    self.assertEqual(src["sha256"], self.d.run.data[src["name"]]["sha256"])
        for n in names:
            self.assertFalse(n.startswith("/") or ".." in n)
        self.assertNotIn(b"seeds2-study", zf.read("manifest.json"))                   # não é o pacote científico

    def test_rodada_nao_concluida_sem_figuras(self):
        d = D.load(StudyView(self.archive, self.archive_uid), self.info["failed"].run_uid)
        self.assertEqual(FG.run_figures(d), [])
        with self.assertRaises(FG.FigureError):
            FG.figures_zip(d)


# =========================================================================== integridade e segurança
class IntegridadeTest(_Base):
    def _corrupt_archive(self, path_pred):
        con = sqlite3.connect(ArchiveStore(self.dest).path)
        try:
            rows = con.execute("SELECT r.path, r.sha256 FROM study_resources r WHERE r.archive_uid = ?",
                               (self.archive_uid,)).fetchall()
            target = [h for p, h in rows if path_pred(p)]
            self.assertTrue(target)
            con.execute("DROP TRIGGER archive_blobs_immutable_u")                     # simula dano no disco
            con.execute("UPDATE archive_blobs SET content = ?, encoding = 'identity' WHERE sha256 = ?",
                        (b"adulterado", target[0]))
            con.commit()
        finally:
            con.close()

    def test_estudo_corrompido_nao_gera_documento(self):
        self._corrupt_archive(lambda p: p.endswith("saidas/despacho_ems.csv") and self.done.run_uid in p)
        for kind in ("pdf", "xlsx", "fig"):
            with self.assertRaises(D.DossierIntegrityError, msg=kind):
                RX.generate(self.view(), self.done.run_uid, kind)

    def test_modelo_corrompido_tambem_bloqueia(self):
        self._corrupt_archive(lambda p: "/data/modelos/" in p and self.done.run_uid in p)
        with self.assertRaises(D.DossierIntegrityError):
            D.load(self.view(), self.done.run_uid)

    def test_previsao_corrompida_bloqueia(self):
        self._corrupt_archive(lambda p: p.startswith("forecasts/blobs/"))
        with self.assertRaises(D.DossierError):
            D.load(self.view(), self.done.run_uid)

    def test_dado_local_corrompido_e_manifesto_divergente(self):
        st, run = _Fixture.get()[5]["sem_fuso"]
        with mock.patch.object(st, "run_data", return_value=b"x"):
            with self.assertRaises(D.DossierIntegrityError):
                D.load(st, run.run_uid)
        bad = type(run)(**{**run.__dict__, "manifest": {**run.manifest, "reference": {**run.manifest["reference"],
                                                                                    "scenario_version": 99}}})
        with mock.patch.object(st, "get_run", return_value=bad):
            with self.assertRaisesRegex(D.DossierIntegrityError, "manifesto"):
                D.load(st, run.run_uid)
        bad = type(run)(**{**run.__dict__, "data": {**run.data, "saidas/inexistente.csv":
                                                    {"sha256": "0" * 64, "size": 1, "media_type": "text/csv"}}})
        with mock.patch.object(st, "get_run", return_value=bad):
            with self.assertRaises(D.DossierIntegrityError):
                D.load(st, run.run_uid)

    def test_nomes_e_conteudos_maliciosos(self):
        st, run = _Fixture.get()[5]["malicioso"]
        for kind in ("pdf", "xlsx", "fig"):
            name, data, *_ = RX.generate(st, run.run_uid, kind)
            self.assertRegex(name, r"^[A-Za-z0-9_.]+$")                                # nome de arquivo seguro
            self.assertNotIn("..", name.replace("." + name.rsplit(".", 1)[1], ""))
        txt = _pdf_text(RX.generate(st, run.run_uid, "pdf")[1])
        self.assertIn("<b>negrito</b><script>alert(1)</script>", txt)                  # literal, não interpretado
        self.assertIn("Evil <i>&amp;</i> ../../etc/passwd", txt)
        res = X.build_workbook(D.load(st, run.run_uid))
        wb = _wb(res.data)
        cells = [c for ws in wb.worksheets for row in ws.iter_rows() for c in row if isinstance(c.value, str)]
        evil = [c for c in cells if c.value.startswith("=HYPERLINK")]
        self.assertTrue(evil)
        for c in evil:
            self.assertEqual(c.data_type, "s")                                        # texto, nunca fórmula
            self.assertTrue(c.quotePrefix)
        self.assertFalse(any(c.data_type == "f" for ws in wb.worksheets for row in ws.iter_rows() for c in row))
        with zipfile.ZipFile(io.BytesIO(res.data)) as z:
            self.assertFalse(any(b"<f>" in z.read(n) for n in z.namelist() if n.startswith("xl/worksheets/")))
        self.assertTrue(any("U+FFFD" in w for w in res.warnings))                     # controle \x07 sinalizado
        data, man = FG.figures_zip(D.load(st, run.run_uid))
        self.assertEqual(man["experiment"]["scenario_name"], EVIL_SCN)                 # identidade preservada (JSON)


# =========================================================================== motor intocado e imutabilidade
class ImutabilidadeTest(_Base):
    def test_exportacoes_sem_motor_e_sem_alterar_rodadas_cenarios_ou_estudos(self):
        before_local = _dump(self.store)
        before_arch = _archive_dump(self.archive)
        with _Sab():
            for src in (self.store, self.view()):
                for run in (self.done, self.info["failed"], self.info["interrupted"]):
                    for kind in ("pdf", "xlsx") + (("fig",) if run.state == "concluida" else ()):
                        RX.generate(src, run.run_uid, kind)
        self.assertEqual(_dump(self.store), before_local)
        self.assertEqual(_archive_dump(ArchiveStore(self.dest)), before_arch)
        r = self.store.get_run(self.done.run_uid)
        self.assertEqual(r.manifest, self.done.manifest)
        self.assertEqual({n: d["sha256"] for n, d in r.data.items()}, {n: d["sha256"] for n, d in self.done.data.items()})
        self.assertEqual(len(self.store.list_runs()), len(self.store.list_runs()))     # nenhuma rodada criada
        ok, problems = ArchiveStore(self.dest).verify(self.archive_uid)
        self.assertTrue(ok, problems)

    def test_camada_de_relatorios_nao_importa_o_motor(self):
        """Em processo novo: gerar os três documentos de um estudo arquivado não carrega o runtime, o EMS nem o motor
        de simulação (não há caminho até o otimizador). As bibliotecas de catálogo (``models``/``h2_pemfc``, usadas
        pelo inventário para valores nominais) já eram carregadas pela consulta do Piso 2D-A e não executam rodadas."""
        code = (
            "import sys, json\n"
            "from seeds2.archive.store import ArchiveStore\nfrom seeds2.archive.view import StudyView\n"
            "from seeds2.ui import report_exports as RX\n"
            f"v = StudyView(ArchiveStore({self.dest!r}), {self.archive_uid!r})\n"
            f"for k in ('pdf','xlsx','fig'): RX.generate(v, {self.done.run_uid!r}, k)\n"
            "bad = [m for m in sys.modules if m.split('.')[0] in ('orchestrator_runtime','ems_integration','simulation')]\n"
            "print(json.dumps(bad))\n")
        env = {**os.environ, "PYTHONPATH": str(RAIZ), "PYTHONDONTWRITEBYTECODE": "1"}
        out = subprocess.run([sys.executable, "-c", code], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=300)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        self.assertEqual(json.loads(out.stdout.strip().splitlines()[-1]), [])

    def test_instalacao_limpa_sem_a_microrrede_original(self):
        self.assertEqual(MicrogridRegistry(self.dest).entries(), [])
        with _Sab():
            for kind in ("pdf", "xlsx", "fig"):
                name, data, *_ = RX.generate(self.view(), self.done.run_uid, kind)
                self.assertGreater(len(data), 1000)
        self.assertEqual(MicrogridRegistry(self.dest).entries(), [])                  # nada criado

    def test_ems_v16_inalterado(self):
        self.assertEqual(self.done.manifest["software"]["science"]["sha256"], runner.science_fingerprint()["sha256"])
        self.assertAlmostEqual(self.done.summary["custo_total_rs"], 88.3190884544543, places=10)


# =========================================================================== combinações de fontes
class CombinacoesTest(_Base):
    def _all(self, key):
        st, run = _Fixture.get()[5][key]
        d = D.load(st, run.run_uid)
        keys = [s.key for s in FG.run_figures(d)]
        pdf = _pdf_text(RX.generate(st, run.run_uid, "pdf")[1])
        wb = _wb(RX.generate(st, run.run_uid, "xlsx")[1])
        RX.generate(st, run.run_uid, "fig")
        return d, keys, pdf, wb

    def test_sem_bateria(self):
        d, keys, pdf, wb = self._all("sem_bateria")
        self.assertNotIn("02_estado_de_carga_bateria", keys)
        self.assertIn("03_hidrogenio_acumulado", keys)
        self.assertIn("Sem bateria representada nesta rodada", pdf)
        self.assertFalse(any(c.startswith("SOC_") for c in d.outputs().columns))
        self.assertIn("Tecnologias sem equipamento registrado nesta revisão", pdf)

    def test_sem_pemfc(self):
        d, keys, pdf, wb = self._all("sem_pemfc")
        self.assertNotIn("03_hidrogenio_acumulado", keys)
        self.assertIn("02_estado_de_carga_bateria", keys)
        self.assertIn("Sem consumo de H₂ registrado", pdf)
        ind = {i.key: i.value for i in D.indicators(d)}
        self.assertIsNone(ind["h2_kg"])                                               # não disponível, nunca zero inventado
        self.assertIn("não disponível", pdf)
        self.assertGreater(d.summary["energia_nao_atendida_kWh"], 1.0)               # déficit real registrado
        self.assertIn("Energia não atendida registrada", pdf)

    def test_sem_fv_e_sem_clima(self):
        d, keys, pdf, wb = self._all("sem_fv")
        self.assertNotIn("06_previsao_clima", keys)
        self.assertNotIn("08 Previsão clima", wb.sheetnames)
        self.assertIn("Solar fotovoltaica", pdf)
        self.assertIn("não instalada", pdf)


if __name__ == "__main__":
    unittest.main()
