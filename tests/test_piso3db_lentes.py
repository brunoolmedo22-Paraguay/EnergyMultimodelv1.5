"""Piso 3D-B3 — lentes Decisão, Economia e Evidência sobre rodadas V2 REAIS (HiGHS) de microrredes fictícias de teste.

* o marco v2 leva às lentes exatamente o que a rodada gravou (planos por janela, coordenações com o sinal de valor
  futuro, auditoria, tabelas originais) — sem solver, sem modelos e sem arredondar;
* duas ou mais unidades do mesmo tipo (dois bancos; duas unidades PEMFC): identidade por UID, somas só no navegador;
* durações e passos diferentes (12 h/60 min, 24 h/60 min com m = 2, 6 h/30 min);
* rodada antiga (contrato de dados v1): campos opcionais ausentes ficam ausentes, nada é inventado;
* janelas sem sinal de valor futuro válido são identificadas, com o motivo gravado;
* no navegador (Chromium, quando instalado): trocar de lente não perde o instante, trocar de rodada não mistura estado.
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import piso3db_util as P  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402

pytestmark = []


def _igual(a, b) -> bool:
    """Valor do marco × valor gravado: mesmo double, ou ambos ausentes."""
    if a is None:
        return b is None or (isinstance(b, float) and math.isnan(b))
    return a == b


@unittest.skipUnless(P.SOLVER, "Pyomo/HiGHS não instalados")
class LentesSobreRodadasReaisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        d = cls._tmp.name
        cls.m = {"hibrida": P.missao_hibrida(d), "bancos": P.missao_dois_bancos(d), "pemfc": P.missao_duas_pemfc(d),
                 "passo30": P.missao_passo_30(d), "dia": P.missao_24h(d), "legado": P.missao_legada_v1(d),
                 "isolada": P.missao_isolada(d)}
        sys.modules.pop("pyomo", None)
        cls.f = {k: P.marco(st, run) for k, (_uid, st, run) in cls.m.items()}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    # ------------------------------------------------------------------------------------------------ marco v2
    def test_planos_por_janela_sao_os_gravados(self):
        for nome in ("hibrida", "bancos", "dia"):
            _uid, st, run = self.m[nome]
            pl, f = RG.ler_csv(st, run, RG.N_PLANOS), self.f[nome]
            self.assertEqual(sum(len(p["intervalo"]) for p in f["planos"]), len(pl))
            self.assertEqual([p["janela"] for p in f["planos"]], sorted(set(float(j) for j in pl["janela"])))
            for p in f["planos"]:
                sub = pl[pl["janela"] == p["janela"]]
                self.assertEqual(p["intervalo"], [float(v) for v in sub["intervalo"]])
                self.assertEqual(p["aplicado"], [float(v) for v in sub["aplicado"]])
                for col, vals in p["series"].items():
                    origem = col if col in sub.columns else "plano:" + col
                    self.assertIn(origem, sub.columns, col)
                    self.assertTrue(all(_igual(a, b) for a, b in zip(vals, sub[origem].tolist(), strict=True)), (nome, col))

    def test_coordenacoes_e_sinal_de_valor_futuro_sao_os_gravados(self):
        _uid, st, run = self.m["hibrida"]
        co, f = RG.ler_json(st, run, RG.N_COORD), self.f["hibrida"]
        regs = co if isinstance(co, list) else co.get("coordenacoes") or co.get("registros")
        self.assertEqual(len(f["coordenacoes"]), len(regs))
        ja = RG.ler_csv(st, run, RG.N_JANELAS)
        for c, w in zip(f["coordenacoes"], f["janelas"], strict=True):
            self.assertEqual((c["janela"], c["k"]), (int(w["j"]), int(w["k"])))
            linha = ja[ja["janela"] == c["janela"]].iloc[0]
            self.assertEqual(c["situacao"], linha["sinal_situacao"])
            if c["sinal"] is None:
                continue
            self.assertEqual(c["sinal"]["qualidade"]["estado"], linha["sinal_qualidade"])
            self.assertEqual(sum(len(m["pontos"]) for m in c["sinal"]["modos"]), int(linha["sinal_pontos"]))
            self.assertEqual(len(c["sinal"]["modos"]), int(linha["sinal_modos"]))
            self.assertEqual(c["sinal"]["indice_fronteira"], int(linha["sinal_fronteira"]))
            if c["sinal"]["qualidade"]["estado"] != "valido":           # ausência de valor futuro = resultado, com motivo
                self.assertTrue(c["sinal"]["qualidade"]["motivo"])
                self.assertIsNone(w["custo_futuro_estimado"])
                self.assertIsNone(c["decomposicao"]["custo_futuro_estimado_R"])
        self.assertTrue(any(w["sinal_qualidade"] != "valido" for w in f["janelas"]))    # R-3 continua visível, não corrigido
        self.assertTrue(any(w["sinal_qualidade"] == "valido" for w in f["janelas"]))

    def test_auditoria_procedencia_e_tabelas_originais(self):
        _uid, st, run = self.m["hibrida"]
        f, au = self.f["hibrida"], RG.ler_json(st, run, RG.N_AUDITORIA)
        self.assertEqual(f["auditoria"]["aceito"], au["aceito"])
        self.assertEqual(f["auditoria"]["verificacoes"], au["verificacoes"])
        self.assertEqual(f["auditoria"]["constatacoes"], len(au.get("constatacoes") or []))
        self.assertEqual(f["procedencia"]["microrrede_uid"], run.manifest["reference"]["microgrid_uid"])
        self.assertEqual(f["procedencia"]["cenario_impressao"], run.manifest["reference"]["scenario_fingerprint"])
        self.assertEqual({n for n, _s, _b in f["arquivos"]}, set(run.data))
        self.assertTrue(all(s == run.data[n]["sha256"] for n, s, _b in f["arquivos"]))
        for nome in (RG.N_INTERVALOS, RG.N_FRONTEIRAS, RG.N_JANELAS, RG.N_PLANOS):
            df, t = RG.ler_csv(st, run, nome), f["tabelas"][nome]
            self.assertEqual(t["colunas"], [str(c) for c in df.columns])
            self.assertEqual(len(t["linhas"]), len(df))
            for c, col in enumerate(df.columns):
                for a, b in zip([lin[c] for lin in t["linhas"]], df[col].tolist(), strict=True):
                    self.assertTrue(_igual(a, b.item() if isinstance(b, np.generic) else b), (nome, col, a, b))
        self.assertEqual(f["limitacoes"], list(RG.LIMITACOES))
        self.assertNotIn("pyomo", sys.modules)

    # ------------------------------------------------------------------------------------- várias unidades por tipo
    def test_dois_bancos_identidade_por_uid_e_soma_so_no_navegador(self):
        _uid, st, run = self.m["bancos"]
        f, fr, it = self.f["bancos"], RG.ler_csv(st, run, RG.N_FRONTEIRAS), RG.ler_csv(st, run, RG.N_INTERVALOS)
        uids = [r["uid"] for r in f["recursos"]["bat"]]
        self.assertEqual(len(uids), 2)
        for u in uids:
            self.assertEqual(f["baterias"][u]["energia_kWh"], fr[f"{u}|energia_kWh"].tolist())
            self.assertEqual(f["baterias"][u]["P_d_kW"], it[f"{u}|P_d_kW"].tolist())
        self.assertEqual(sorted(f["baterias"][u]["resumo"]["capacidade_kWh"] for u in uids), [20.0, 30.0])
        if not P.NODE:
            self.skipTest("Node.js não instalado")
        js = P.node("const M = api.modelo(F); return { fr: M.A.fr, pd: M.A.pd, cap: M.A.cap, p0: api.planoPorTipo(F, F.planos[0]).pd };", f)
        soma = (fr[f"{uids[0]}|energia_kWh"] + fr[f"{uids[1]}|energia_kWh"]).tolist()
        self.assertTrue(all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12) for a, b in zip(js["fr"], soma, strict=True)))
        self.assertEqual(js["cap"], 50.0)
        p0 = f["planos"][0]["series"]
        self.assertTrue(all(math.isclose(a, b + c, abs_tol=1e-12) for a, b, c in zip(js["p0"], p0[f"{uids[0]}|P_d"], p0[f"{uids[1]}|P_d"], strict=True)))
        # o sinal de valor futuro passa a depender de DUAS energias: os pontos gravados trazem as duas coordenadas
        sinais = [c["sinal"] for c in f["coordenacoes"] if c["sinal"]]
        self.assertTrue(sinais and all(s["baterias"] == uids or sorted(s["baterias"]) == sorted(uids) for s in sinais))
        self.assertTrue(all(len(p["energias_kWh"]) == 2 for s in sinais for m in s["modos"] for p in m["pontos"]))

    def test_duas_unidades_pemfc_do_mesmo_registro(self):
        _uid, st, run = self.m["pemfc"]
        f, it = self.f["pemfc"], RG.ler_csv(st, run, RG.N_INTERVALOS)
        uids = [r["uid"] for r in f["recursos"]["fc"]]
        self.assertEqual(len(uids), 2)
        self.assertEqual({u.split("#")[1] for u in uids}, {"1", "2"})
        self.assertEqual(len({u.split("#")[0] for u in uids}), 1)
        for u in uids:
            self.assertEqual(f["pemfc"][u]["p_kW"], it[f"{u}|p_kW"].tolist())
            self.assertIsNotNone(f["pemfc"][u]["curva"])
        self.assertEqual(f["pemfc"][uids[0]]["curva"]["sha_curva"], f["pemfc"][uids[1]]["curva"]["sha_curva"])   # 1 curva por configuração
        if P.NODE:
            js = P.node("return api.modelo(F).A.fcP;", f)
            soma = (it[f"{uids[0]}|p_kW"] + it[f"{uids[1]}|p_kW"]).tolist()
            self.assertTrue(all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(js, soma, strict=True)))

    # ------------------------------------------------------------------------------------------ durações e passos
    def test_duracoes_e_passos_diferentes(self):
        esperado = {"hibrida": (12, 60.0, 12), "passo30": (12, 30.0, 12), "dia": (24, 60.0, 12)}
        for nome, (K, delta, janelas) in esperado.items():
            f = self.f[nome]
            self.assertEqual((f["rodada"]["K"], f["rodada"]["delta_min"], len(f["janelas"])), (K, delta, janelas), nome)
            self.assertEqual(len(f["fronteiras"]["local"]), K + 1)
            self.assertEqual(len(f["intervalos"]["demanda_realizada_kW"]), K)
        self.assertEqual(self.f["passo30"]["fronteiras"]["local"][1][11:16], "00:30")
        self.assertEqual({w["ap"] for w in self.f["dia"]["janelas"]}, {2.0})
        if P.NODE:
            js = P.node("return Fs.map((F) => { const M = api.modelo(F); return [M.K, M.hD, M.rot[1], M.rot.length, M.jan.map((w) => w.ap)]; });",
                        self.f["passo30"], self.f["dia"], self.f["hibrida"])
            self.assertEqual(js[0][:4], [12, 0.5, "00:30", 13])
            self.assertEqual(js[1][:4], [24, 1, "01h", 25])
            self.assertEqual(js[1][4], [2] * 12)
            # energia = potência média × Δ: com Δ = 30 min o throughput derivado usa 0,5 h (nunca 1 h presumida)
            self.assertEqual(js[2][1], 1)

    # ----------------------------------------------------------------------------------------- rodada antiga (v1)
    def test_rodada_do_contrato_v1_sem_campos_opcionais(self):
        _uid, st, run = self.m["legado"]
        f = self.f["legado"]
        self.assertEqual(f["rodada"]["versao_dados"], 1)
        self.assertNotIn(RG.N_RENOV, run.data)
        self.assertNotIn(RG.N_PEMFC, run.data)
        self.assertEqual((f["renovaveis"], f["pemfc"]), ({}, {}))
        self.assertEqual((f["recursos"]["fv"], f["recursos"]["wt"], f["recursos"]["fc"]), ([], [], []))
        self.assertTrue(f["verificacao"]["ok"])
        self.assertEqual(f["resumo"]["custo_realizado_total_R"], run.summary["mission"]["custo_realizado_total_R"])
        self.assertTrue(f["planos"] and f["coordenacoes"])                # o 3D-A já gravava planos e coordenações
        json.dumps(f, allow_nan=False)
        if P.NODE:
            js = P.node("const M = api.modelo(F); return [M.ord, M.A.fcP, M.A.wtP, M.A.cH2, api.balancoDe(M.A, 0).faltam];", f)
            self.assertEqual(js, [["bat", "grid", "dem", "eco"], "__undefined__", "__undefined__", "__undefined__", []])


    # ------------------------------------------------------------------------------------------- microrrede isolada
    def test_microrrede_isolada_rede_nao_aplicavel(self):
        """Sem PCC a rede NÃO participa: não é dado ausente (N/D) nem importação zero inventada no balanço."""
        f = self.f["isolada"]
        self.assertEqual(f["pcc"]["modo"], "isolado_declarado")
        self.assertNotIn("importacao_rede", f["resumo"]["componentes_R"])
        if P.NODE:
            js = P.node("const M = api.modelo(F), b = api.balancoDe(M.A, 0); return [M.ord, M.A.impR, M.A.tar, M.A.cImp, b.inj.map((x) => x[0]), b.faltam, b.total];", f)
            self.assertEqual(js[:4], [["bat", "dem", "eco"], "__undefined__", "__undefined__", "__undefined__"])
            self.assertEqual(js[4:], [["bat"], [], 1.0])


@unittest.skipUnless(P.SOLVER and P.navegador_disponivel(), "Pyomo/HiGHS ou Chromium/Playwright não instalados")
class LentesNoNavegadorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        d = cls._tmp.name
        m = {"bancos": P.missao_dois_bancos(d), "passo30": P.missao_passo_30(d), "legado": P.missao_legada_v1(d),
             "pemfc": P.missao_duas_pemfc(d), "isolada": P.missao_isolada(d)}
        cls.f = {k: P.marco(st, run) for k, (_uid, st, run) in m.items()}
        cls.r = P.bancada(cls.f)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_rodadas_reais_percorrem_lentes_e_paineis_sem_erro(self):
        for nome, res in self.r.items():
            with self.subTest(marco=nome):
                self.assertEqual(res["erros"], [])
                self.assertEqual({k for k in res["vistas"] if k.startswith("lente:")},
                                 {"lente:operacao", "lente:decisao", "lente:economia", "lente:evidencia"})

    def test_selecao_por_uid_com_dois_bancos_e_duas_unidades(self):
        f, v = self.f["bancos"], self.r["bancos"]["vistas"]
        for r in f["recursos"]["bat"]:
            painel = v[f"painel:Bateria:{r['uid']}"]
            cap = f["baterias"][r["uid"]]["resumo"]["capacidade_kWh"]
            self.assertIn(r["uid"], painel)
            self.assertIn(f"Capacidade{cap:.1f} kWh".replace(".", ","), painel)
        a, b = (v[f"painel:Bateria:{r['uid']}"] for r in f["recursos"]["bat"])
        self.assertNotEqual(a, b)
        self.assertIn("soma de 2 bancos (derivado)", v["lente:operacao"])
        # sinal com 2 bancos: sem projeção inventada — tabela dos pontos gravados (ou indisponibilidade declarada)
        self.assertTrue("Sinal com 2 bancos" in v["lente:decisao"] or "Sinal indisponível" in v["lente:decisao"], v["lente:decisao"][:600])
        f, v = self.f["pemfc"], self.r["pemfc"]["vistas"]
        chaves = [k for k in v if k.startswith("painel:PEMFC:")]
        self.assertEqual(len(chaves), 2 * 3)                              # 2 unidades × 3 vistas
        for r in f["recursos"]["fc"]:
            self.assertIn(r["uid"], v[f"painel:PEMFC:{r['uid']}:0"])
            self.assertIn("Certificação B04", v[f"painel:PEMFC:{r['uid']}:1"])
            self.assertIn("não é validação experimental", v[f"painel:PEMFC:{r['uid']}:1"])

    def test_passo_de_30_min_e_rodada_antiga(self):
        v = self.r["passo30"]["vistas"]
        self.assertIn("12 intervalos de 30 min", v["lente:operacao"])
        self.assertIn("00:30", v["lente:operacao"])
        v = self.r["legado"]["vistas"]
        self.assertIn("Contrato de dadosv1", v["lente:evidencia"])
        self.assertEqual(sorted(k.split(":")[1] for k in v if k.startswith("painel:")), ["Bateria", "Carga", "Custos", "Rede"])
        self.assertNotIn("balanço incompleto", v["lente:operacao"])     # recurso inexistente ≠ dado ausente
        v = self.r["isolada"]["vistas"]
        self.assertEqual(sorted(k.split(":")[1] for k in v if k.startswith("painel:")), ["Bateria", "Carga", "Custos"])
        self.assertNotIn("balanço incompleto", v["lente:operacao"])
        self.assertIn("Σ injeção (derivado) = 1,00 kW", v["lente:operacao"])
        self.assertNotIn("Tarifa de decisão", v["lente:economia"])       # sem PCC não há tarifa: omitida, não N/D

    def test_janelas_sem_sinal_valido_sao_explicitas_na_lente_decisao(self):
        f = self.f["bancos"]
        sem = next(w for w in f["janelas"] if w["sinal_qualidade"] != "valido")
        com = next(w for w in f["janelas"] if w["sinal_qualidade"] == "valido")
        sel = 'select[aria-label="Janela de decisão"]'
        r = P.bancada({"bancos": f}, passos=[["lente", "decisao"], ["escolher", sel, str(int(sem["j"]))], ["texto", "sem"],
                                              ["escolher", sel, str(int(com["j"]))], ["texto", "com"], ["lente", "evidencia"], ["texto", "evid"],
                                              ["lente", "economia"], ["texto", "eco"]])["bancos"]
        self.assertEqual(r["erros"], [])
        v = r["vistas"]
        self.assertIn(f"Decisão · janela {int(sem['j'])}sem valor futuro", v["sem"])
        self.assertIn("Custo futuro estimadoN/D", v["sem"])
        self.assertIn("foi tomada sem valor futuro", v["sem"])
        self.assertIn(f"Decisão · janela {int(com['j'])}com valor futuro", v["com"])
        self.assertNotIn("foi tomada sem valor futuro", v["com"])
        n_ok = sum(1 for w in f["janelas"] if w["sinal_qualidade"] == "valido")
        self.assertEqual(v["evid"].count("indisponível"), len(f["janelas"]) - n_ok)
        self.assertIn(f"Decisões com valor futuro{n_ok} de {len(f['janelas'])}", v["eco"])

    def test_trocar_de_lente_nao_perde_o_instante_e_trocar_de_rodada_nao_mistura_estado(self):
        inst = "document.querySelector('.pt-inst').textContent"
        estado = "JSON.parse(sessionStorage.getItem('seeds2.partitura.' + (window.__atual || window.__F).rodada.uid) || '{}')"
        passos = [["clicarEm", ".pt .host svg.trama", [0.62, 0.5]], ["avaliar", "i0", inst]]
        for lente in ("decisao", "economia", "evidencia", "operacao"):
            passos += [["lente", lente], ["avaliar", "i_" + lente, inst]]
        passos += [["lente", "economia"], ["avaliar", "e1", estado],
                   # outra rodada na MESMA página: estado próprio (instante inicial), sem herdar lente nem instante
                   ["avaliar", "troca", "(window.__atual = window.__OUTROS.outra, window.__trocar('outra'), 1)"],
                   ["avaliar", "i_outra", inst], ["avaliar", "lente_outra", "document.querySelector('.pt').dataset.lenteAtiva"],
                   ["avaliar", "titulo_outra", "document.querySelector('.pt h1').textContent"],
                   # de volta à primeira: lente e instante restaurados do estado guardado para ELA
                   ["avaliar", "volta", "(window.__atual = window.__F, window.__trocar(null), 1)"],
                   ["avaliar", "i_volta", inst], ["avaliar", "lente_volta", "document.querySelector('.pt').dataset.lenteAtiva"],
                   # recarregar a página (mesma aba): o contexto da rodada continua
                   ["recarregar"], ["avaliar", "i_recarga", inst], ["avaliar", "lente_recarga", "document.querySelector('.pt').dataset.lenteAtiva"]]
        r = P.bancada({"bancos": self.f["bancos"]}, passos=passos, outros={"outra": self.f["passo30"]})["bancos"]
        self.assertEqual(r["erros"], [])
        v = r["vistas"]
        self.assertIn("fixado", v["i0"])
        self.assertNotIn("00h–01h", v["i0"])                              # o clique escolheu um instante que não é o inicial
        for lente in ("decisao", "economia", "evidencia", "operacao"):
            self.assertEqual(v["i_" + lente], v["i0"], lente)
        self.assertEqual((v["e1"]["lens"], v["e1"]["pin"]), ("economia", True))
        self.assertEqual(v["lente_outra"], "operacao")
        self.assertNotEqual(v["i_outra"], v["i0"])
        self.assertNotIn("fixado", v["i_outra"])
        self.assertEqual(v["titulo_outra"], self.f["passo30"]["rodada"]["cenario"])
        self.assertEqual((v["i_volta"], v["lente_volta"]), (v["i0"], "economia"))
        self.assertEqual((v["i_recarga"], v["lente_recarga"]), (v["i0"], "economia"))


if __name__ == "__main__":
    unittest.main()
