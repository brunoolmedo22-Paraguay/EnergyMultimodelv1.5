"""UI-RESULTADOS-02 — visualizações científicas da rodada V2 e relatório PDF visual.

Cobre as cinco melhorias pedidas pelo responsável:

1. tarifa de decisão como CURVA ESCALONADA (importação × remuneração de exportação; «não aplicável» só com evidência);
2. demanda TOTAL como referência nos gráficos de potência das fontes (e atendida, havendo déficit);
3. aba «Carga líquida» no explorador da Operação (demanda − renováveis APROVEITADAS; compensação; fechamento = resíduo);
4. lente «Visão Geral» (KPIs selados × derivados, energia por fonte, participação, balanço, participação temporal) — a
   abertura de uma rodada continua em Operação;
5. relatório PDF desenhado pela PRÓPRIA Partitura (missão completa, independente do zoom), conferido e diagramado no
   servidor sem recalcular nada.

Camadas: funções puras em Node (sem navegador); componente REAL num navegador de bancada (``tools/e2e/bancada_piso3db``);
composição do PDF em Python a partir do pacote desenhado; rodadas REAIS (HiGHS) de topologias diferentes; o exemplo C4
(Solar + Bateria + Rede) restaurado da instantânea versionada, sem alterar sua evidência; e o painel na interface (AppTest).
"""
from __future__ import annotations

import copy
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import piso3db_util as P  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from integracao_v2 import relatorio_visual as RV  # noqa: E402
from integracao_v2 import svg_pdf as SVG  # noqa: E402
from integracao_v2 import trama_frame as TF  # noqa: E402
from seeds2.report import dossier as D  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
EXEMPLOS = RAIZ / "seeds2" / "exemplos"
PUROS = P.PUROS + ", cargaLiquida, visaoGeral, mudancasTarifa, tarifaExportacao, LENTES, TIPOS"
NAV = bool(P.NODE) and P.navegador_disponivel()
ND = "__undefined__"


def node(corpo, *marcos):
    return P.node(corpo, *marcos, puros=PUROS)


def marco_completo(**kw) -> dict:
    """Marco SINTÉTICO de teste com os resumos por recurso preenchidos (o de ``piso3db_util`` deixa FV e PEMFC sem resumo,
    para os testes de N/D)."""
    f = P.marco_sintetico(**kw)
    for r in f["renovaveis"].values():
        r["resumo"] = {**r["resumo"], "energia_aproveitada_kWh": float(sum(r["P_R_kW"])), "energia_vertida_kWh": float(sum(r["vertimento_kW"]))}
    for g in f["pemfc"].values():
        g["resumo"] = {"energia_kWh": float(sum(g["p_kW"]))}
    f["hash"] += "|completo"
    return f


def gerar_pacote(frame: dict, passos_antes: list | None = None) -> tuple[dict, list]:
    """Pacote do relatório desenhado pelo componente REAL no navegador de bancada (``__pt.relatorio``)."""
    passos = list(passos_antes or []) + [["avaliar", "pacote", "document.querySelector('.pt.partitura').__pt.relatorio()"]]
    r = P.bancada({"r": frame}, passos=passos)["r"]
    return r["vistas"]["pacote"], r["erros"]


def c4_restaurado(pasta: str):
    """Restaura o exemplo C4 (instantânea versionada) num catálogo TEMPORÁRIO e devolve (store, rodadas concluídas)."""
    from seeds2.microgrid import exemplos
    from seeds2.microgrid.registry import MicrogridRegistry

    reg = MicrogridRegistry(pasta)
    rel = exemplos.garantir(reg, EXEMPLOS)
    if not rel.restaurados and not rel.presentes:
        raise unittest.SkipTest(f"exemplo C4 indisponível: {rel.falhas}")
    uid = next(e.uid for e in reg.entries())
    st = reg.open(uid)
    return st, [r for r in st.list_runs() if r.state == "concluida"]


# ====================================================================================== 1–4 · funções derivadas (Node)
@unittest.skipUnless(P.NODE, "Node.js não instalado")
class DerivadasTest(unittest.TestCase):
    def setUp(self):
        self.f = P.marco_sintetico()

    def test_lentes_visao_geral_por_ultimo_e_carga_liquida_no_explorador(self):
        r = node("const M = api.modelo(F); return { lentes: api.LENTES.map((l) => l[0]), ord: M.ord, liq: api.TIPOS.liq.n };", self.f)
        self.assertEqual(r["lentes"], ["operacao", "decisao", "economia", "evidencia", "visao"])
        self.assertEqual(r["ord"][-3:], ["dem", "liq", "eco"])
        self.assertEqual(r["liq"], "Carga líquida")

    def test_tarifa_de_exportacao_so_e_nao_aplicavel_com_evidencia(self):
        casos = {}
        for nome, sentidos, serie, modo in (("so_imp", "somente_importacao", None, "conectado"),
                                            ("exporta_vazia", "importacao_e_exportacao", [None] * 6, "conectado"),
                                            ("sem_declaracao", None, None, "conectado"),
                                            ("gravada", "somente_importacao", [0.2] * 6, "conectado"),
                                            ("isolada", "somente_importacao", None, "isolado_declarado")):
            g = copy.deepcopy(self.f)
            g["pcc"]["sentidos"], g["pcc"]["modo"] = sentidos, modo
            if serie is not None:
                g["intervalos"]["tarifa_exportacao_decisao_R_kWh"] = serie
            casos[nome] = g
        r = node("return Fs.map((G) => api.tarifaExportacao(G));", *casos.values())
        self.assertEqual(dict(zip(casos, r)), {"so_imp": ND, "exporta_vazia": None, "sem_declaracao": None,
                                               "gravada": [0.2] * 6, "isolada": ND})

    def test_mudancas_tarifarias_sem_interpolacao(self):
        r = node("return [api.mudancasTarifa([0.44, 0.44, 1.94, 1.94, 0.44]), api.mudancasTarifa([1, null, 1, 2]), api.mudancasTarifa(null)];", self.f)
        self.assertEqual(r, [[0, 2, 4], [0, 2, 3], []])                    # ausente interrompe o período

    def test_carga_liquida_definicao_negativa_fechamento_e_sem_dupla_contagem(self):
        g = copy.deepcopy(self.f)
        K = g["rodada"]["K"]
        # intervalo 3: renováveis aproveitadas acima da demanda (excedente) — exportação e carga absorvem o excedente
        for u in ("eq-wt1", "eq-wt2"):
            g["renovaveis"][u]["P_R_kW"][3] = 30.0
        g["intervalos"]["pcc_exportacao_realizada_kW"][3] = 20.0
        r = node("const M = api.modelo(F), C = api.cargaLiquida(M); return { liq: C.liq, comp: C.comp, fech: C.fech, eLiq: C.eLiq, ePos: C.ePos, eNeg: C.eNeg, nNeg: C.nNeg, termos: C.termos, soma: C.somaTermos };", g)
        I = g["intervalos"]
        ren = [sum(g["renovaveis"][u]["P_R_kW"][i] for u in g["renovaveis"]) for i in range(K)]   # cada UID uma vez
        liq = [I["demanda_realizada_kW"][i] - ren[i] for i in range(K)]
        self.assertEqual(r["liq"], liq)
        self.assertLess(r["liq"][3], 0)                                    # negativa preservada (excedente renovável)
        comp = [g["baterias"]["eq-bat1"]["P_d_kW"][i] + g["pemfc"]["eq-fc#1"]["p_kW"][i] + I["pcc_importacao_realizada_kW"][i]
                + I["demanda_nao_atendida_kW"][i] - g["baterias"]["eq-bat1"]["P_c_kW"][i] - I["pcc_exportacao_realizada_kW"][i] for i in range(K)]
        self.assertEqual(r["comp"], comp)
        self.assertEqual(r["fech"], [comp[i] - liq[i] for i in range(K)])
        self.assertEqual(r["nNeg"], 1)
        self.assertAlmostEqual(r["ePos"] + r["eNeg"], r["eLiq"], places=12)
        self.assertEqual([t[1] for t in r["termos"]], ["Descarga da bateria", "PEMFC", "Importação da rede", "Demanda não atendida",
                                                       "Carga da bateria", "Exportação"])

    def test_carga_liquida_sem_renovaveis_e_dado_ausente(self):
        g = copy.deepcopy(self.f)
        g["recursos"]["fv"], g["recursos"]["wt"] = [], []
        h = copy.deepcopy(self.f)
        h["renovaveis"]["arr-fv1"]["P_R_kW"] = None                           # série não persistida
        r = node("return Fs.map((G) => { const C = api.cargaLiquida(api.modelo(G)); return { liq: C.liq, ren: C.ren === undefined ? 'nao_aplicavel' : C.ren, eLiq: C.eLiq }; });", g, h)
        self.assertEqual(r[0]["liq"], g["intervalos"]["demanda_realizada_kW"])   # sem renováveis: carga líquida = demanda
        self.assertEqual(r[0]["ren"], "nao_aplicavel")
        self.assertEqual((r[1]["liq"], r[1]["eLiq"]), ([None] * 6, None))       # ausente nunca vira zero

    def test_visao_geral_prioriza_selados_rotula_derivados_e_nao_conta_bateria_como_primaria(self):
        g = copy.deepcopy(self.f)
        for u in g["renovaveis"]:
            g["renovaveis"][u]["resumo"].update({"energia_aproveitada_kWh": sum(g["renovaveis"][u]["P_R_kW"]),
                                                 "energia_vertida_kWh": sum(g["renovaveis"][u]["vertimento_kW"])})
        g["pemfc"]["eq-fc#1"]["resumo"] = {"energia_kWh": 60.0}
        sel = copy.deepcopy(g)
        sel["resumo"]["indicadores_selados"] = {"E_renovavel_usada_kWh": 119.5, "E_bess_carga_kWh": 0.0, "E_bess_descarga_kWh": 6.0,
                                                "E_geracao_kWh": 60.0, "E_curtailment_kWh": 24.0}
        iso = P.marco_sintetico(conectado=False)
        r = node("return Fs.map((G) => api.visaoGeral(G, api.modelo(G)));", g, sel, iso)
        v0, v1, v2 = (x["v"] for x in r)
        self.assertEqual((v0["ren"]["o"], v1["ren"]["o"]), ("derivado", "selado"))
        self.assertEqual((v0["ren"]["v"], v1["ren"]["v"]), (120.0, 119.5))       # o selado tem prioridade sobre a soma derivada
        self.assertEqual((v1["batD"]["o"], v1["fc"]["o"]), ("selado", "selado"))
        self.assertEqual(v0["custoKwh"]["o"], "derivado")
        self.assertAlmostEqual(v0["custoKwh"]["v"], g["resumo"]["custo_realizado_total_R"] / g["resumo"]["energia_atendida_kWh"])
        fat = {f[0]: f[2] for f in r[0]["fatias"]}
        self.assertEqual(set(fat), {"fv", "wt", "bat", "fc", "grid"})            # injeções; carga e exportação ficam nas saídas
        self.assertAlmostEqual(v0["inj"]["v"], sum(fat.values()))
        self.assertAlmostEqual(v0["partRen"]["v"], 100 * (fat["fv"] + fat["wt"]) / v0["inj"]["v"])   # descarga não é renovável
        self.assertEqual([s[0] for s in r[0]["saidas"]], ["dem", "bat", "grid"])
        self.assertAlmostEqual(v0["fech"]["v"], v0["inj"]["v"] - v0["sai"]["v"])
        self.assertEqual((v2["imp"]["v"], v2["pmax"]["v"], v2["uPico"]["v"]), (ND, ND, ND))   # isolada: PCC não aplicável


# ====================================================================================== 1–5 · componente no navegador
@unittest.skipUnless(NAV, "Chromium/Playwright (Node) não instalados")
class InterfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = marco_completo(K=12)
        q = "document.querySelector('.pt.partitura')"
        cls.svgk = lambda sel, k: f"[...document.querySelectorAll('{sel} svg.trama [data-k=\"{k}\"]')].length"
        passos = [["avaliar", "lente0", f"{q}.dataset.lenteAtiva"],
                  ["lente", "visao"], ["avaliar", "visao", f"{q}.textContent.replace(/\\s+/g, ' ')"],
                  ["avaliar", "kpis", "[...document.querySelectorAll('.pt .kpi')].map((k) => k.dataset.kpi)"],
                  ["avaliar", "visao_svgs", "[...document.querySelectorAll('.pt .vg svg.trama')].map((s) => s.getAttribute('aria-label'))"],
                  ["avaliar", "areas", "document.querySelectorAll('.pt .vg svg.trama path[data-k]').length"],
                  ["lente", "economia"], ["avaliar", "tar_eco", cls.svgk(".pt .stage", "tar")],
                  ["avaliar", "tar_eco_d", "[...document.querySelectorAll('.pt .stage svg.trama path[data-k=\"tar\"]')].map((p) => p.getAttribute('d'))"],
                  ["lente", "operacao"], ["avaliar", "tar_op", cls.svgk(".pt .stage", "tar")], ["avaliar", "dem_op", cls.svgk(".pt .stage", "demref")],
                  ["clicar", ".status .pill"]]
        for nome in ("Solar", "Eólica", "Bateria", "PEMFC", "Rede", "Carga", "Carga líquida", "Custos"):
            passos += [["clicar", f'.dtools [role="tab"] >> text="{nome}"'],
                       ["avaliar", "dem:" + nome, cls.svgk(".pt .dlg", "demref")], ["avaliar", "tar:" + nome, cls.svgk(".pt .dlg", "tar")],
                       ["avaliar", "txt:" + nome, "document.querySelector('.pt .dlg .dbody').textContent.replace(/\\s+/g, ' ')"],
                       ["avaliar", "leg:" + nome, "[...document.querySelectorAll('.pt .dlg .chead .leg')].map((l) => l.textContent.trim())"]]
        passos += [["tecla", "Escape"],
                   # sessão guardada na lente Visão Geral → ao REABRIR a rodada, Operação; Economia continua restaurada
                   ["lente", "visao"], ["recarregar"], ["avaliar", "reaberta_visao", f"{q}.dataset.lenteAtiva"],
                   ["lente", "economia"], ["recarregar"], ["avaliar", "reaberta_eco", f"{q}.dataset.lenteAtiva"]]
        cls.r = P.bancada({"s": cls.f}, passos=passos)["s"]
        cls.v = cls.r["vistas"]

    def test_sem_erros_de_pagina(self):
        self.assertEqual(self.r["erros"], [])

    def test_abertura_em_operacao_e_visao_geral_nunca_restaurada(self):
        self.assertEqual(self.v["lente0"], "operacao")
        self.assertEqual(self.v["reaberta_visao"], "operacao")
        self.assertEqual(self.v["reaberta_eco"], "economia")                # o comportamento anterior das outras lentes continua

    def test_tarifa_como_curva_escalonada_em_todas_as_vistas(self):
        self.assertGreaterEqual(self.v["tar_op"], 1)
        self.assertGreaterEqual(self.v["tar_eco"], 1)
        for nome in ("Bateria", "Rede", "Custos"):
            self.assertGreaterEqual(self.v["tar:" + nome], 1, nome)
        for d in self.v["tar_eco_d"]:
            self.assertRegex(d, r"^M[\d.]+,[\d.]+H")                       # degrau: horizontal em cada intervalo
            self.assertNotIn("C", d)                                        # sem curvas (nenhuma interpolação)
        for nome in ("Solar", "Eólica", "PEMFC", "Carga", "Carga líquida"):
            self.assertEqual(self.v["tar:" + nome], 0, nome)                # tarifa só onde a interface a mostrava

    def test_demanda_de_referencia_so_nos_graficos_de_potencia_das_fontes(self):
        for nome in ("Solar", "Eólica", "Bateria", "PEMFC", "Rede"):
            self.assertEqual(self.v["dem:" + nome], 1, nome)                # uma linha, no gráfico de potência
            self.assertIn("demanda total", self.v["leg:" + nome], nome)
        for nome in ("Carga", "Carga líquida", "Custos"):
            self.assertEqual(self.v["dem:" + nome], 0, nome)
        self.assertEqual(self.v["dem_op"], 0)                               # as raias compactas da Operação não mudaram

    def test_aba_carga_liquida(self):
        t = self.v["txt:Carga líquida"]
        for trecho in ("Demanda total × carga líquida", "Compensação da carga líquida", "Fechamento do balanço",
                       "Balanço da carga líquida", "= carga líquida", "renováveis efetivamente aproveitadas"):
            self.assertIn(trecho, t)
        self.assertIn("kWh de carga líquida", t)
        self.assertNotIn("N/D", t)

    def test_visao_geral(self):
        self.assertEqual(self.v["kpis"], ["dem", "at", "ens", "custo", "custokwh", "ren", "pcc"])
        self.assertEqual(self.v["visao_svgs"], ["Energia por fonte", "Participação energética nas injeções", "Balanço energético da missão",
                                                "Participação temporal do suprimento"])
        self.assertGreater(self.v["areas"], 6)
        for trecho in ("SELADO", "DERIVADO", "Denominador:", "Σ injeções", "não é geração primária", "Indicadores complementares",
                       "Auditoria independente da missão", "Utilização do PCC"):
            self.assertIn(trecho.lower(), self.v["visao"].lower())


# ====================================================================================== 5 · relatório (pacote + PDF)
@unittest.skipUnless(NAV, "Chromium/Playwright (Node) não instalados")
class RelatorioC4Test(unittest.TestCase):
    """Caso de regressão: o exemplo C4 — Carga CT-046 · Solar + Bateria + Rede (96 intervalos de 15 min), sem alterar a
    evidência (restaurado da instantânea versionada num diretório temporário; só leitura)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.st, runs = c4_restaurado(cls._tmp.name)
        cls.rodada = runs[0]
        cls.data_antes = {n: d["sha256"] for n, d in cls.rodada.data.items()}
        cls.f = TF.montar(cls.st, cls.rodada, verificacao=RG.verificar(cls.st, cls.rodada))
        q = "document.querySelector('.pt.partitura')"
        cnt = "Object.fromEntries(['grid','fv','bat','dem','tar','tarmuda','tarval'].map((k) => [k, document.querySelectorAll('.pt .stage svg.trama [data-k=\"' + k + '\"]').length]))"
        # a tela fica AMPLIADA (6 h) e na lente Economia antes do relatório: o PDF tem de trazer a missão completa
        jan = "document.querySelector('.pt .stage svg.trama').getAttribute('data-janela')"
        antes = [["avaliar", "tela_tudo", cnt], ["clicar", '.pt .stage .seg button >> text="6 h"'], ["avaliar", "janela_6h", jan],
                 ["lente", "economia"]]
        passos = antes + [["avaliar", "pacote", f"{q}.__pt.relatorio()"], ["avaliar", "lente_depois", f"{q}.dataset.lenteAtiva"],
                          ["avaliar", "zoom_depois", "JSON.parse(sessionStorage.getItem('seeds2.partitura.' + window.__F.rodada.uid) || '{}').zoom"]]
        cls.b = P.bancada({"c4": cls.f}, passos=passos)["c4"]
        cls.pac = cls.b["vistas"]["pacote"]
        cls.nome, cls.pdf, cls.info = RV.pdf(cls.st, cls.rodada.run_uid, cls.pac)
        from pypdf import PdfReader

        cls.paginas = [p.extract_text() or "" for p in PdfReader(io.BytesIO(cls.pdf)).pages]
        cls.texto = "\n".join(cls.paginas)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def secao(self, sid):
        return next(s for s in self.pac["secoes"] if s["id"] == sid)

    def test_sem_erros_e_estado_da_tela_preservado(self):
        self.assertEqual(self.b["erros"], [])
        self.assertEqual(self.b["vistas"]["lente_depois"], "economia")          # gerar o relatório não muda a tela
        self.assertNotIn(self.b["vistas"]["zoom_depois"], (0, None))

    def test_pacote_identificado_pelo_hash_do_marco_e_com_todas_as_secoes_e_fontes(self):
        self.assertEqual((self.pac["formato"], self.pac["rodada"], self.pac["hash"]), (RV.FORMATO, self.rodada.run_uid, self.f["hash"]))
        self.assertEqual([s["id"] for s in self.pac["secoes"]], ["operacao", "fontes", "visao", "decisao", "economia", "evidencia"])
        subs = [s["id"] for s in self.secao("fontes")["subsecoes"]]
        esperado = [f"fv:{r['uid']}" for r in self.f["recursos"]["fv"]] + [f"bat:{r['uid']}" for r in self.f["recursos"]["bat"]] \
            + ["grid:grid", "dem:dem", "liq:liq"]
        self.assertEqual(subs, esperado)                                         # toda fonte, todo UID, na ordem do explorador

    def test_missao_completa_independente_do_zoom_e_mesmo_desenho_da_tela(self):
        principal = self.secao("operacao")["blocos"][1]
        cont = {k: len(re.findall(rf'data-k="{k}"', principal["svg"])) for k in self.b["vistas"]["tela_tudo"]}
        self.assertEqual(cont, self.b["vistas"]["tela_tudo"])                   # = tela com a missão inteira
        self.assertIn("janela ampliada", self.b["vistas"]["janela_6h"])         # (a tela estava recortada em 6 h)
        self.assertIn(">00:00<", principal["svg"])
        self.assertIn(">23:45<", principal["svg"])
        self.assertEqual(cont["tarmuda"], 2)                                     # 18:00 e 21:00: dois inícios de período
        self.assertIn(">1,94<", principal["svg"])

    def test_pdf_gerado_paginado_e_com_as_secoes_da_pagina_de_resultados(self):
        self.assertTrue(self.pdf.startswith(b"%PDF") and self.nome.startswith("seeds2_relatorio_C4_"))
        self.assertTrue(self.nome.endswith(f"_v{self.rodada.scenario_version}_{self.rodada.run_uid[:8]}.pdf"))
        self.assertEqual(self.info["paginas"], len(self.paginas))
        self.assertGreaterEqual(len(self.paginas), 30)
        self.assertIn("SEEDS2", self.paginas[0])
        self.assertIn("RELATÓRIO CIENTÍFICO DA RODADA", self.paginas[0])
        self.assertIn(self.rodada.run_uid, self.paginas[0])
        self.assertIn("DADOS SINTÉTICOS DE ENSAIO", self.paginas[0])
        self.assertIn("Sumário", self.paginas[1])
        for titulo in ("01 · Operação", "02 · Visão Geral", "03 · Decisão", "04 · Economia", "05 · Evidência", "Carga líquida",
                       "Rede / PCC", "Bateria", "Solar fotovoltaica", "Participação temporal do suprimento", "Balanço energético da missão",
                       "Tapete de decisões", "Sinal de valor futuro", "Economia da missão", "Arquivos da evidência",
                       "Configuração da microrrede", "Condições iniciais", "Advertências do preflight", "Discussão factual",
                       "Limitações científicas e convenções"):
            self.assertIn(titulo, self.texto, titulo)
        self.assertIn(f"Página {len(self.paginas)} de {len(self.paginas)}", self.paginas[-1])
        self.assertNotIn("↗", self.texto)
        custo = f"{self.rodada.summary['mission']['custo_realizado_total_R']:.2f}".replace(".", ",")
        self.assertIn(custo, self.texto)

    def test_evidencia_original_intacta(self):
        depois = self.st.get_run(self.rodada.run_uid)
        self.assertEqual({n: d["sha256"] for n, d in depois.data.items()}, self.data_antes)
        self.assertTrue(RG.verificar(self.st, depois).ok)

    def test_pacote_adulterado_ou_de_outra_rodada_e_recusado(self):
        ruim = copy.deepcopy(self.pac)
        ruim["hash"] = "0" * 64
        with self.assertRaises(D.DossierIntegrityError):
            RV.pdf(self.st, self.rodada.run_uid, ruim)
        outro = copy.deepcopy(self.pac)
        outro["rodada"] = "f" * 32
        with self.assertRaises(RV.PacoteInvalido):
            RV.pdf(self.st, self.rodada.run_uid, outro)
        mal = copy.deepcopy(self.pac)
        mal["secoes"][0]["blocos"][1]["svg"] = mal["secoes"][0]["blocos"][1]["svg"].replace("<g", "<image href=\"x.png\"/><g", 1)
        with self.assertRaises(SVG.SvgInvalido):
            RV.pdf(self.st, self.rodada.run_uid, mal)

    def test_composicao_sem_solver_nem_modelos(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "pacote.json"
            arq.write_text(json.dumps(self.pac), encoding="utf-8")
            cod = ("import sys, json; sys.modules['pyomo'] = None; sys.modules['highspy'] = None\n"
                   "from seeds2.microgrid.registry import MicrogridRegistry\nfrom integracao_v2 import relatorio_visual as RV\n"
                   f"st = MicrogridRegistry({self._tmp.name!r}).open({self.rodada.microgrid_uid!r})\n"
                   f"n, b, i = RV.pdf(st, {self.rodada.run_uid!r}, open({str(arq)!r}).read())\n"
                   "ruins = [m for m in sys.modules if m.split('.')[0] in ('pyomo', 'highspy', 'h2_pemfc', 'simulation', 'ems_integration', 'streamlit') and sys.modules[m]]\n"
                   "print(json.dumps({'paginas': i['paginas'], 'ruins': ruins}))")
            r = subprocess.run([sys.executable, "-c", cod], cwd=RAIZ, capture_output=True, text=True, timeout=600,
                               env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        res = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(res["ruins"], [])
        self.assertEqual(res["paginas"], len(self.paginas))

    def test_visao_geral_do_pdf_com_os_valores_selados(self):
        kp = {k["t"]: k for k in self.secao("visao")["blocos"][0]["itens"]}
        m = self.rodada.summary["mission"]
        self.assertEqual(kp["Energia demandada"]["v"], f"{m['energia_demanda_kWh']:,.1f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.assertEqual(kp["Energia demandada"]["o"], "selado")
        self.assertEqual(kp["Custo médio por kWh atendido"]["o"], "derivado")
        self.assertNotIn("N/D", json.dumps(self.secao("visao")["blocos"][0], ensure_ascii=False))


# ====================================================================================== topologias reais (HiGHS)
@unittest.skipUnless(NAV and P.SOLVER, "Pyomo/HiGHS ou Chromium/Playwright não instalados")
class TopologiasTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        d = cls._tmp.name
        cls.casos = {}
        for nome, fn in (("hibrida", P.missao_hibrida), ("dois_bancos", P.missao_dois_bancos), ("isolada", P.missao_isolada),
                         ("duas_pemfc", P.missao_duas_pemfc)):
            _uid, st, run = fn(d, f"UI-RESULTADOS-02 {nome}")
            f = P.marco(st, run)
            pac, erros = gerar_pacote(f)
            nome_pdf, pdf, info = RV.pdf(st, run.run_uid, pac)
            cls.casos[nome] = (st, run, f, pac, erros, pdf, info)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_cada_topologia_gera_o_relatorio_com_todas_as_fontes_sem_erros(self):
        for nome, (_st, _run, f, pac, erros, pdf, info) in self.casos.items():
            with self.subTest(nome):
                self.assertEqual(erros, [])
                self.assertTrue(pdf.startswith(b"%PDF") and info["paginas"] >= 10)
                subs = {s["id"].split(":")[0] + ":" + s["id"].split(":")[1] for s in next(s for s in pac["secoes"] if s["id"] == "fontes")["subsecoes"]}
                esperado = {f"{k}:{r['uid']}" for k in ("fv", "wt", "bat", "fc") for r in f["recursos"][k]} | {"dem:dem", "liq:liq"} \
                    | ({"grid:grid"} if f["pcc"]["modo"] == "conectado" else set())
                self.assertEqual(subs, esperado)

    def test_tarifa_so_com_pcc_conectado(self):
        for nome, (_st, _run, f, pac, *_r) in self.casos.items():
            with self.subTest(nome):
                op = next(s for s in pac["secoes"] if s["id"] == "operacao")["blocos"][1]["svg"]
                self.assertEqual('data-k="tar"' in op, f["pcc"]["modo"] == "conectado")

    def test_pemfc_tem_as_tres_vistas_e_a_curva_vetorial(self):
        _st, _run, f, pac, *_r = self.casos["hibrida"]
        sub = next(s for s in next(s for s in pac["secoes"] if s["id"] == "fontes")["subsecoes"] if s["id"].startswith("fc:"))
        titulos = [b.get("titulo", "") for b in sub["blocos"] if b.get("tipo") == "figura"]
        self.assertTrue(any(t.startswith("Operação") for t in titulos))
        self.assertTrue(any("Curva característica q(P)" in t for t in titulos))
        self.assertTrue(any(t.startswith("Verificação dinâmica") for t in titulos))


# ====================================================================================== SVG restrito (sem navegador)
class SvgRestritoTest(unittest.TestCase):
    OK = ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40" viewBox="0 0 100 40"><defs><clipPath id="c"><rect x="0" y="0" width="90" height="40"/></clipPath></defs>'
          '<g clip-path="url(#c)"><rect x="1" y="1" width="20" height="10" rx="2" fill="#7a63e0" fill-opacity="0.5" data-hatch="#ffffff" data-hatch-w="2" data-hatch-p="5"/>'
          '<path d="M0,0H10V10A5,5 0 0,1 20,10Z" fill="#c98a00" stroke="#171717" stroke-width="1" stroke-dasharray="4 3"/>'
          '<polyline points="0,0 10,10 20,0" fill="none" stroke="#171717" stroke-width="2"/><circle cx="5" cy="5" r="2" fill="#171717"/>'
          '<line x1="0" y1="0" x2="10" y2="0" stroke="#d9534a" stroke-width="1"/></g>'
          '<text x="50" y="20" fill="#171717" font-size="11" font-weight="700" text-anchor="middle" data-w="20">Σ H₂ ≤ −0,5 ✓</text></svg>')

    def test_vocabulario_admitido_e_desenhado(self):
        from reportlab.pdfgen import canvas

        from seeds2.report import run_pdf as RP

        RP._fonts()
        fig = SVG.FiguraSVG(self.OK, 200)
        self.assertEqual((fig.width, fig.height), (200, 80))
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(300, 120))
        fig.wrapOn(c, 300, 120)
        fig.drawOn(c, 10, 10)
        c.save()
        self.assertTrue(buf.getvalue().startswith(b"%PDF"))

    def test_entrada_nao_confiavel_recusada(self):
        for ruim in ('<!DOCTYPE svg [<!ENTITY x "y">]><svg width="1" height="1"/>', '<svg width="1" height="1"><script>x</script></svg>',
                     '<svg width="1" height="1"><image href="a.png"/></svg>', '<svg width="1" height="1"><foreignObject/></svg>',
                     '<svg width="1" height="1"><rect width="1" height="1" fill="red"/></svg>', '<svg width="1" height="1"><ellipse/></svg>',
                     '<svg width="nan" height="1"/>', "<html/>", "<svg " + "x" * (SVG.MAX_BYTES + 1)):
            with self.subTest(ruim[:40]):
                with self.assertRaises(SVG.SvgInvalido):
                    fig = SVG.FiguraSVG(ruim, 100)
                    from reportlab.pdfgen import canvas
                    c = canvas.Canvas(io.BytesIO())
                    fig.drawOn(c, 0, 0)

    def test_validacao_do_pacote(self):
        base = {"formato": RV.FORMATO, "versao": RV.VERSAO, "rodada": "r", "hash": "h", "secoes": [{"id": "operacao", "blocos": []}]}
        self.assertEqual(RV.validar(base, run_uid="r", frame_hash="h")["secoes"], 1)
        for mut, exc in ((lambda p: p.update(formato="x"), RV.PacoteInvalido), (lambda p: p.update(rodada="s"), RV.PacoteInvalido),
                         (lambda p: p.update(hash="z"), D.DossierIntegrityError), (lambda p: p.update(secoes=[]), RV.PacoteInvalido),
                         (lambda p: p.update(secoes=[{"id": "x"}]), RV.PacoteInvalido),
                         (lambda p: p.update(secoes=[{"id": "operacao"}, {"id": "operacao"}]), RV.PacoteInvalido),
                         (lambda p: p.update(secoes=[{"id": "operacao", "blocos": [{}] * (RV.MAX_BLOCOS + 1)}]), RV.PacoteInvalido)):
            p = copy.deepcopy(base)
            mut(p)
            with self.assertRaises(exc):
                RV.validar(p, run_uid="r", frame_hash="h")
        with self.assertRaises(RV.PacoteInvalido):
            RV.ler_pacote("{" * 10)
        with self.assertRaises(RV.PacoteInvalido):
            RV.ler_pacote(b"x" * (RV.MAX_PACOTE + 1))


# ====================================================================================== interface (AppTest)
try:
    from streamlit.testing.v1 import AppTest
except Exception:  # noqa: BLE001
    AppTest = None


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class PainelExportacoesTest(unittest.TestCase):
    """Página REAL da rodada C4: o painel tem os MESMOS três botões; o PDF é pedido à Partitura (estado «pedido» nos dados
    do componente); o pacote desenhado vira o download no painel; Excel e figuras continuam com os geradores de antes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.st, runs = c4_restaurado(self._tmp.name)
        self.rodada = runs[0]
        self._env = os.environ.get("SEEDS2_DATA_DIR")
        os.environ["SEEDS2_DATA_DIR"] = self._tmp.name

    def tearDown(self):
        os.environ["SEEDS2_DATA_DIR"] = self._env or ""
        self._tmp.cleanup()

    def abrir(self):
        app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=300)
        app.session_state["mg_active_uid"] = self.rodada.microgrid_uid
        app.session_state["seeds_route"] = {"view": "operacao", "tab": "rodada"}
        app.query_params["run"] = self.rodada.run_uid
        app.run()
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        return app

    def test_pedido_pela_interface_e_download_do_pacote_desenhado(self):
        import integracao_v2.ui as V2UI
        from seeds2.ui import report_exports as RX

        app = self.abrir()
        rotulos = [b.label for b in app.button]
        for r in ("GERAR RELATÓRIO PDF", "BAIXAR TODAS AS FIGURAS (ZIP)", "EXPORTAR TABELAS EXCEL (.xlsx)"):
            self.assertIn(r, rotulos)
        bt = next(b for b in app.button if b.label == "GERAR RELATÓRIO PDF")
        bt.click().run()
        est = app.session_state[V2UI.REL_ESTADO][self.rodada.run_uid]
        self.assertEqual(est["estado"], "pedido")
        self.assertTrue(est["pedido"].startswith("painel-"))
        self.assertIn("Preparando o relatório PDF", "\n".join(i.value for i in app.info))
        self.assertFalse(app.session_state[V2UI.REL_ESTADO][self.rodada.run_uid].get("nome"))
        # o servidor diagrama um pacote: com hash errado, recusa explícita e nenhum documento
        est2, item = V2UI.gerar_relatorio(self.st, self.rodada, {"formato": RV.FORMATO, "versao": 1, "rodada": self.rodada.run_uid,
                                                               "hash": "0" * 64, "secoes": [{"id": "operacao", "blocos": []}]})
        self.assertEqual((est2["estado"], item), ("erro", None))
        self.assertIn("Geração recusada", est2["msg"])
        self.assertFalse(app.session_state[RX._key(self.rodada.run_uid, "pdf")] if RX._key(self.rodada.run_uid, "pdf") in app.session_state else None)


if __name__ == "__main__":
    unittest.main()
