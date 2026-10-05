from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from ems_integration import ponte
from ems_integration.contrato import CurvaEmpirica, Fonte
from ems_integration.despacho import (CfgDespacho, Idx, candidatos_config, custo_lote, despacho, grad_custo,
                                      relatorio, restricoes_lineares)
from ems_integration.executor import executar_pacote
from ems_integration.fontes import ler_serie

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

RAIZ = Path(__file__).resolve().parents[1]


def _fc(nt, n_unid=3):
    curva = CurvaEmpirica(np.array([5.0, 25.0, 50.0]), np.array([0.075, 0.055, 0.062]), 25.0)
    return Fonte(nome="fc", tipo="geracao", n_unid=n_unid, n_ini=n_unid, dn_max=1,
                 P_max_unid_kW=np.full(nt, 50.0), P_min_unid_kW=np.full(nt, 5.0), curva=curva,
                 qtd_fisica_unidade="kg_H2", ramp_kW_min=30.0, eta=0.97)


def _bat(nt, soc0=0.6):
    return Fonte(nome="bateria", tipo="armazenamento", P_max_unid_kW=np.full(nt, 100.0),
                 P_min_unid_kW=np.full(nt, -60.0), eta=0.96, eta_carga=0.99, eta_descarga=0.99, E_kWh=50.0,
                 SOC_ini=soc0, SOC_min=0.2, SOC_max=0.9, SOC_alvo=soc0, c_deg_rs_kWh=0.08)


class LeituraSerieTest(unittest.TestCase):
    def test_metodos_e_nan_fora_da_janela(self):
        df = pd.DataFrame({"v": [0.0, 10.0, 20.0]})
        tn = np.array([0.0, 2.0, 4.0])
        t = np.array([-1.0, 0.0, 1.0, 3.0, 4.0, 5.0])
        lin = ler_serie(df, "v", "kW", tn, t, "linear")
        prev = ler_serie(df, "v", "kW", tn, t, "previous")
        np.testing.assert_allclose(lin[1:5], [0, 5, 15, 20])
        np.testing.assert_allclose(prev[1:5], [0, 0, 10, 20])
        self.assertTrue(np.isnan(lin[0]) and np.isnan(lin[-1]) and np.isnan(prev[-1]))

    def test_conversao_de_unidade(self):
        df = pd.DataFrame({"p": [1000.0, 2000.0]})
        np.testing.assert_allclose(ler_serie(df, "p", "W", [0, 1], [0, 1], "linear"), [1.0, 2.0])
        np.testing.assert_allclose(ler_serie(df, "p", "MW", [0, 1], [0, 1], "linear"), [1e6, 2e6])


class NucleoDespachoTest(unittest.TestCase):
    def test_vizinhanca_de_configuracoes(self):
        fontes = [_fc(5, 4), _bat(5)]
        combos, custo = candidatos_config(fontes, np.array([2, 1]), 64, set())
        self.assertEqual(sorted(combos[:, 0].tolist()), [1, 2, 3])
        self.assertTrue(np.all(combos[:, 1] == 1))

    def test_restricoes_lineares_batem_com_balanco_e_soc(self):
        fontes = [_fc(3), _bat(3)]
        cfg = CfgDespacho(S_base=150.0, N=3)
        ix = Idx(3, fontes)
        rng = np.random.default_rng(1)
        x = rng.random(ix.n_total) * 0.3
        Pl = np.array([0.5, 0.6, 0.4])
        lin = restricoes_lineares(fontes, ix, cfg, np.array([0.0, 0.6]), np.zeros(2), Pl, np.array([3, 1]))
        S = cfg.S_base
        Pfc, Pd, Pc = x[ix.fonte[0]] * S, x[ix.fonte[1]] * S, x[ix.carga[1]] * S
        barra = 0.97 * Pfc + 0.96 * Pd + Pc / 0.96 + x[ix.s_def] * S - x[ix.s_exc] * S
        np.testing.assert_allclose(lin.A_eq @ x, barra)
        np.testing.assert_allclose(lin.b_eq, Pl * S)

    def test_gradiente_do_custo(self):
        from scipy.optimize import check_grad
        fontes = [_fc(3), _bat(3)]
        cfg = CfgDespacho(S_base=150.0, N=3)
        ix = Idx(3, fontes)
        h, n = np.arange(3), np.array([3, 1])
        x = np.random.default_rng(2).random(ix.n_total) * 0.4
        x[ix.carga[1]] *= -1
        erro = check_grad(lambda v: custo_lote(v[None], fontes, ix, cfg, h, n)[0],
                          lambda v: grad_custo(v, fontes, ix, cfg, h, n), x)
        self.assertLess(erro, 1e-5)

    def _rodar(self, algoritmo, **kw):
        nt = 25
        carga = 90 + 40 * np.sin(np.linspace(0, 3, nt))
        fontes = [_fc(nt), _bat(nt)]
        cfg = CfgDespacho(S_base=150.0, algoritmo=algoritmo, seed=0, **kw)
        res = despacho(fontes, carga, cfg)
        return res, relatorio(res, fontes, cfg), fontes

    def test_despacho_atende_carga_e_respeita_limites(self):
        for alg in (0, 1, 2, 3):
            with self.subTest(alg=alg):
                res, rel, fontes = self._rodar(alg)
                kv = res["k_validos"]
                self.assertLess(rel["energia_nao_atendida_kWh"], 1e-4)
                self.assertAlmostEqual(float(np.sum(rel["pct_atendimento"])), 100.0, places=6)
                n = res["n_unid"][:kv, 0]
                self.assertTrue(np.all((n >= 0) & (n <= 3)))
                self.assertTrue(np.all(np.abs(np.diff(np.r_[3, n])) <= 1))       # dn_max = 1
                P = res["P_kW"][:kv, 0]
                self.assertTrue(np.all(P <= n * 50 + 1e-6) and np.all(P >= n * 5 - 1e-6))
                soc = res["SOC"][:kv, 1]
                self.assertTrue(np.all((soc >= 0.2 - 1e-6) & (soc <= 0.9 + 1e-6)))
                self.assertGreater(rel["consumo_fisico"]["fc"]["valor"], 0)
                self.assertEqual(res["n_inviaveis"], 0)
                self.assertLess(res["simultaneo_max_kW"], 1e-3)

    def test_meta_penalizada_reduz_violacao_da_metaheuristica(self):
        orig, _, _ = self._rodar(2)
        pen, _, _ = self._rodar(2, meta_penalizada=True)
        kv = orig["k_validos"]
        self.assertLess(np.nanmedian(pen["viol_meta"][:kv]), np.nanmedian(orig["viol_meta"][:kv]))

    def test_custo_total_inclui_hidrogenio(self):
        res, rel, _ = self._rodar(0)
        self.assertAlmostEqual(res["custo_total_rs"], float(np.sum(rel["custo_por_fonte_rs"])), delta=1e-6)


class PontePlataformaTest(unittest.TestCase):
    """Pipeline real: modelos da plataforma → pacote de troca → EMS."""

    @classmethod
    def setUpClass(cls):
        base = ponte.carga_walkforward("Ideal", "Normal", 12)
        cls.carga = ponte.recortar(base, 0, 20)
        t0, dur = cls.carga.t0, cls.carga.duracao_min
        cls.fc = ponte.caracterizar_fc(t0, dur)
        cls.bat, cls.E = ponte.caracterizar_bateria(t0, dur, "tremblay", "liion_3p3v_2p3ah", 200, 132, 0.6)
        from config.thermal_database import LOCAL_GENERATOR
        from models.thermal_model import ThermalConfig
        cls.term_cfg = ThermalConfig(dynamic=LOCAL_GENERATOR, pmax_mw=0.08, cvu_rs_mwh=1100.0,
                                     pmin_technical_mw=0.02, ramp_up_mw_min=0.02, ramp_down_mw_min=0.02,
                                     startup_cost_rs=50.0)
        cls.term = ponte.disponibilidade_termica(t0, dur, cls.term_cfg)

    def test_caracterizacao_cobre_missao_sem_fault(self):
        dur = (pd.to_datetime(self.fc.timestamp).iloc[-1] - pd.to_datetime(self.fc.timestamp).iloc[0]).total_seconds() / 60
        self.assertGreaterEqual(dur, self.carga.duracao_min)
        self.assertNotIn("FAULT_LIMITED", set(self.fc.state))
        self.assertTrue((self.bat.current_A > 0).any() and (self.bat.current_A < 0).any())
        self.assertAlmostEqual(self.E, 200.376, places=2)

    def test_pacote_e_execucao(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"N_fc": 4, "N": 3, "algoritmo": 2, "seed": 0,
                   "opcoes_fontes": {"fc_base_potencia": "entregue", "bateria_E_kWh": self.E,
                                     "bateria_SOC_min": 0.2, "bateria_SOC_max": 0.9,
                                     **ponte.opcoes_termica(self.term_cfg)}}
            pasta = ponte.escrever_pacote(self.carga, {"fc": self.fc, "bateria": self.bat, "termica": self.term},
                                          None, cfg, destino=Path(d) / "p")
            C = json.loads((pasta / "ems_config.json").read_text(encoding="utf-8"))
            self.assertEqual(C["opcoes_fontes"]["fontes"], ["termica", "fc", "bateria"])
            lido = pd.read_csv(pasta / "bateria.csv")
            self.assertTrue(set(lido.limit_flag.unique()) <= {0, 1})
            r = executar_pacote(pasta)
        self.assertEqual(r["nomes"], ["termica", "fc", "bateria"])
        self.assertEqual(r["k_validos"], len(self.carga.P_kW))  # cobre até o último passo
        self.assertLess(r["rel"]["energia_nao_atendida_kWh"], 1e-3)
        self.assertAlmostEqual(float(r["P_max_unid_kW"][:, 1].max()), 50.0, places=3)   # base 'entregue'
        self.assertAlmostEqual(float(r["eta"][1]), 1.0, places=12)  # potência entregue já é líquida
        self.assertTrue(np.isfinite(r["fontes_meta"]["bateria"]["Rint"]))
        # a térmica sem rampa/CVU no CSV recebe os da ThermalConfig (não fica gratuita nem travada)
        self.assertTrue(any("CVU da plataforma" in l or "rampa" in l for l in r["log"]))

    def test_eolica_e_solar_sao_descontadas_antes_da_otimizacao(self):
        ts = pd.to_datetime(self.fc.timestamp).iloc[0] + pd.to_timedelta(np.arange(0, 25), unit="min")
        eol = pd.DataFrame({"timestamp": ts, "power_net_kw": np.full(ts.size, 40.0)})
        pv = pd.DataFrame({"t_min": np.arange(0, 25.0), "P_kW": np.full(25, 20.0)})
        with tempfile.TemporaryDirectory() as d:
            cfg = {"N_fc": 4, "N": 3, "algoritmo": 0, "pv_P_rated_kWp": 50.0,
                   "opcoes_fontes": {"fc_base_potencia": "entregue", "bateria_E_kWh": self.E,
                                     "bateria_SOC_min": 0.2, "bateria_SOC_max": 0.9}}
            pasta = ponte.escrever_pacote(self.carga, {"fc": self.fc, "bateria": self.bat}, pv, cfg,
                                          destino=Path(d) / "p", eolica=eol)
            r = executar_pacote(pasta)
        self.assertNotIn("eolica", r["nomes"])                                # não é variável de decisão
        esperado = np.maximum(self.carga.P_kW - 0.97 * 20.0 - 40.0, 0)
        np.testing.assert_allclose(r["P_load_liq_kW"], esperado, atol=1e-9)
        from visualization.ems_plots import energias_barramento
        E = energias_barramento(r)
        self.assertIn("eolica", E)
        self.assertIn("pv", E)
        self.assertAlmostEqual(E["eolica"] / E["pv"], 40.0 / (0.97 * 20.0), places=6)

    def test_alinhamento_tolera_serie_que_comeca_um_passo_depois(self):
        ts = pd.date_range("2026-03-21 12:01", periods=120, freq="1min")
        out, msg = ponte.alinhar_horario(pd.DataFrame({"timestamp": ts, "v": 0.0}),
                                         pd.Timestamp("2026-09-05 12:00"), 120)
        self.assertEqual(len(out), 120, msg)

    def test_alinhamento_por_horario(self):
        ts = pd.date_range("2026-09-01 00:00", periods=48, freq="30min")
        df = pd.DataFrame({"timestamp": ts, "v": np.arange(48)})
        out, _ = ponte.alinhar_horario(df, pd.Timestamp("2026-09-05 08:00"), 120)
        self.assertEqual(pd.to_datetime(out.timestamp).iloc[0], pd.Timestamp("2026-09-01 08:00"))


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class EMSAppSmokeTest(unittest.TestCase):
    def test_landing_tem_ems_e_pagina_de_configuracao_abre(self):
        app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=60).run()
        self.assertIn("OTIMIZAR DESPACHO →", [b.label for b in app.button])
        next(b for b in app.button if b.label == "OTIMIZAR DESPACHO →").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["energy_source"], "ems")
        next(b for b in app.button if b.label == "Configuração").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn("Metaheurística", [r.label for r in app.radio])

    def test_execucao_completa_pela_interface(self):
        app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=240).run()
        next(b for b in app.button if b.label == "OTIMIZAR DESPACHO →").click().run()
        next(b for b in app.button if b.label == "Configuração").click().run()
        next(b for b in app.button if b.label.startswith("▶ CALCULAR MODELOS")).click().run()
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        self.assertEqual(len(app.error), 0, [e.value for e in app.error])
        self.assertEqual(app.session_state["ems_page"], "Otimização")
        labels = [m.label for m in app.metric]
        for esperado in ("H₂ consumido", "SOC final bateria", "Stacks ligados", "ΔJ mediano (meta − refino)"):
            self.assertIn(esperado, labels)
        self.assertGreaterEqual(len(app.get("plotly_chart")), 6)
        for pagina in ("Comparação", "Exportação"):
            next(b for b in app.button if b.label == pagina).click().run()
            self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
