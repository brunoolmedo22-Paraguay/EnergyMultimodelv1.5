"""Caderno de Ensaios — finalização da Partitura V2: indicadores científicos PERSISTIDOS por rodada (V1.6 × V2, N/D ×
não aplicável) e o comparador de duas rodadas (diferenças só quando válidas, condições experimentais conferidas,
comparação temporal só com a mesma malha — nada alinhado nem interpolado). Tudo a partir dos registros gravados.
"""
from __future__ import annotations

import copy
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import piso3db_util as P  # noqa: E402
from seeds2.ui import caderno_ui as CD  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None


def _csv(inicios, custo, imp, dem) -> bytes:
    linhas = ["intervalo,inicio_utc,demanda_realizada_kW,pcc_importacao_realizada_kW,custo_realizado_acumulado_R"]
    linhas += [f"{i},{t},{d},{p},{c}" for i, (t, c, p, d) in enumerate(zip(inicios, custo, imp, dem))]
    return ("\n".join(linhas) + "\n").encode()


def _v2(uid, *, custo=100.0, imp=40.0, delta=60, K=3, inicio="2026-01-01T00:00:00+00:00", estado="concluida", pemfc=True,
        versao=1, cenario="sc1", N=2, m=1, H_L=3, serie_custo=None):
    inst = [f"2026-01-01T{h:02d}:00:00+00:00" for h in range(0, K * delta // 60, delta // 60)] if delta % 60 == 0 else \
        [f"2026-01-01T00:{k * delta:02d}:00+00:00" for k in range(K)]
    mission = {"missao_completa": estado == "concluida", "custo_realizado_parcial": False, "custo_realizado_total_R": custo,
               "energia_importada_kWh": imp, "energia_exportada_kWh": 0.0, "energia_demanda_kWh": 90.0,
               "energia_nao_atendida_kWh": 0.0, "pcc_modo": "conectado", "janelas": K, "formulacao": "v1.1-3C-4",
               "pemfc": {"eq-fc": {"massa_h2_kg": 1.25}} if pemfc else {},
               "sinal_valor_futuro": {"valido": 2, "degradado_sem_valor_futuro": 1, "degradado_referencia": 0, "sem_coordenacao": 0}}
    man = {"engine": {"id": "milp_mpc_v1", "data_version": 3, "formulations": {"hierarquia": "v1.1-3C-4"}},
           "scenario": {"name": "Dia útil"}, "strategy": {"malha": {"delta_min": delta, "N": N, "m": m, "H_L": H_L}, "pcc": {"modo": "conectado"}},
           "mission": {"delta_min": delta, "N": N, "m": m, "H_L": H_L, "intervals": K, "step_s": delta * 60, "start_utc": inicio,
                       "duration_min": delta * K}}
    run = SimpleNamespace(run_uid=uid, scenario_uid=cenario, scenario_version=versao, config_revision=1, state=estado, manifest=man,
                          summary={"engine": "milp_mpc_v1", "mission": mission if estado == "concluida" else {},
                                   "execution": {"auditoria_integral_aprovada": True, "aceitacao": {"classificacao": "algebrica_aprovada"}}},
                          data={"v2/intervalos.csv": {}, "v2/auditoria.json": {}}, created_at="2026-11-12T10:00:00+00:00",
                          finished_at="2026-11-12T10:00:30+00:00")
    run._csv = _csv(inst, serie_custo or [custo / K * (k + 1) for k in range(K)], [imp / K] * K, [30.0] * K)
    return run


def _v16(uid, *, custo=88.3):
    return SimpleNamespace(run_uid=uid, scenario_uid="sc2", scenario_version=1, config_revision=1, state="concluida",
                           manifest={"engine": {"id": "legacy_v16"}, "scenario": {"name": "Padrão V1.6"},
                                     "mission": {"duration_min": 30, "n_steps": 31, "start_utc": "2026-01-01 00:00:00", "step_s": 60}},
                           summary={"N": 3, "Ts_s": 60.0, "custo_total_rs": custo, "energia_demanda_kWh": 65.4,
                                    "energia_nao_atendida_kWh": 0.0, "h2_kg": 3.5},
                           data={"saidas/despacho_ems.csv": {}}, created_at="2026-11-12T09:00:00+00:00", finished_at="2026-11-12T09:01:00+00:00")


class _Store:
    def __init__(self, *runs):
        self.runs = {r.run_uid: r for r in runs}

    def get_run(self, uid):
        return self.runs[uid]

    def run_data(self, uid, name):
        assert name == "v2/intervalos.csv"
        return self.runs[uid]._csv


class IndicadoresTest(unittest.TestCase):
    def test_v2_le_so_o_resumo_persistido(self):
        x = CD.indicadores(_v2("a" * 32))
        self.assertEqual((x["motor"], x["delta_min"], x["N"], x["m"], x["H_L"], x["pcc"]), ("V2", 60.0, 2, 1, 3, "conectado"))
        self.assertEqual((x["custo"], x["custo_natureza"], x["energia_importada_kWh"], x["h2_kg"]), (100.0, "custo_realizado_v2", 40.0, 1.25))
        self.assertEqual(x["sinal"], {"valido": 2, "degradado": 1, "sem_coordenacao": 0, "janelas": 3})
        self.assertEqual((x["auditoria"], x["dados"], x["duracao_exec_s"], x["inicio_utc"]), (True, 2, 30.0, "2026-01-01T00:00:00Z"))
        self.assertEqual(CD.indicadores(_v2("b" * 32, pemfc=False))["h2_kg"], "na")      # resumo registra PEMFC vazio
        y = CD.indicadores(_v2("c" * 32, estado="interrompida"))                        # nenhum custo de missão parcial
        self.assertEqual((y["custo"], y["energia_importada_kWh"], y["h2_kg"], y["sinal"], y["auditoria"]), (None, None, None, None, None))

    def test_v16_sem_metricas_do_ems_v2(self):
        x = CD.indicadores(_v16("d" * 32))
        self.assertEqual((x["motor"], x["N"], x["m"], x["H_L"], x["pcc"], x["sinal"]), ("V1.6", 3, "na", "na", "na", "na"))
        self.assertEqual((x["custo"], x["custo_natureza"], x["h2_kg"], x["energia_importada_kWh"]), (88.3, "funcao_objetivo_v16", 3.5, None))
        self.assertEqual(x["inicio_utc"], "2026-01-01T00:00:00Z")

    def test_resumo_ilegivel_nao_impede_a_listagem(self):
        r = _v2("e" * 32)
        r.summary = {"mission": "lixo"}
        self.assertIsNone(CD._ind_seguro(r).get("custo"))
        r.manifest = None
        r.summary = 7
        self.assertIn("motor", CD._ind_seguro(r))


class CompararTest(unittest.TestCase):
    def _linha(self, c, k):
        return next(l for l in c["linhas"] if l["chave"] == k)

    def test_mesma_malha_diferencas_e_series_sem_interpolacao(self):
        a, b = _v2("a" * 32, custo=100.0, imp=40.0), _v2("b" * 32, custo=90.0, imp=0.0, versao=2)
        c = CD.comparar(_Store(a, b), a.run_uid, b.run_uid)
        cu = self._linha(c, "custo")
        self.assertEqual((cu["a"], cu["b"], cu["dif_abs"], cu["dif_rel"]), (100.0, 90.0, -10.0, -0.1))
        im = self._linha(c, "energia_importada_kWh")
        self.assertEqual((im["dif_abs"], im["dif_rel"]), (-40.0, -1.0))
        h2 = self._linha(c, "h2_kg")
        self.assertEqual((h2["dif_abs"], h2["dif_rel"]), (0.0, 0.0))
        self.assertTrue(c["temporal"]["ok"])
        self.assertEqual([s["chave"] for s in c["temporal"]["series"]], ["custo_realizado_acumulado_R", "pcc_importacao_realizada_kW", "demanda_realizada_kW"])
        self.assertEqual(c["temporal"]["series"][0]["a"], [100 / 3, 200 / 3, 100.0])
        self.assertEqual(len(c["temporal"]["instantes"]), 3)
        dif = [x["item"] for x in c["condicoes"] if not x["igual"]]
        self.assertEqual(dif, ["Versão do cenário"])
        self.assertTrue(any("NÃO equivalentes (Versão do cenário)" in t for t in c["advertencias"]))
        self.assertEqual([l["chave"] for l in c["linhas"]][-2:], ["sinal", "auditoria"])

    def test_malhas_diferentes_nao_sao_alinhadas(self):
        a, b = _v2("a" * 32, delta=60, K=3), _v2("b" * 32, delta=30, K=6)
        c = CD.comparar(_Store(a, b), a.run_uid, b.run_uid)
        self.assertFalse(c["temporal"]["ok"])
        self.assertIn("malhas temporais diferentes", c["temporal"]["motivo"])
        self.assertIn("nenhuma série é alinhada nem interpolada", c["temporal"]["motivo"])
        self.assertIsNotNone(self._linha(c, "custo")["dif_abs"])                         # totais do mesmo motor: calculados, com aviso
        self.assertIn("Passo Δ [min]", [x["item"] for x in c["condicoes"] if not x["igual"]])

    def test_motores_diferentes_sem_diferencas(self):
        a, b = _v2("a" * 32), _v16("d" * 32)
        c = CD.comparar(_Store(a, b), a.run_uid, b.run_uid)
        for k in ("custo", "energia_demanda_kWh", "h2_kg"):
            l = self._linha(c, k)
            self.assertIsNone(l["dif_abs"])
            self.assertIn("motores diferentes", l["nota"])
        self.assertIn("custo realizado (V2)", self._linha(c, "custo")["rotulo"])
        self.assertIn("função objetivo (V1.6)", self._linha(c, "custo")["rotulo"])
        self.assertEqual(self._linha(c, "energia_importada_kWh")["b"], None)             # N/D, nunca zero
        self.assertFalse(c["temporal"]["ok"])
        self.assertTrue(c["advertencias"][0].startswith("Motores diferentes"))
        self.assertNotIn("sinal", [l["chave"] for l in c["linhas"]])
        self.assertIsNotNone(self._linha(c, "duracao_exec_s")["dif_abs"])                # tempo de relógio: mesma grandeza

    def test_relativa_indefinida_com_a_zero_e_interrompida(self):
        a, b = _v2("a" * 32, imp=0.0), _v2("b" * 32, imp=5.0)
        l = self._linha(CD.comparar(_Store(a, b), a.run_uid, b.run_uid), "energia_importada_kWh")
        self.assertEqual((l["dif_abs"], l["dif_rel"], l["nota"]), (5.0, None, "diferença relativa indefinida (A = 0)"))
        a, b = _v2("a" * 32), _v2("b" * 32, estado="interrompida")
        c = CD.comparar(_Store(a, b), a.run_uid, b.run_uid)
        self.assertIsNone(self._linha(c, "custo")["b"])
        self.assertFalse(c["temporal"]["ok"])
        self.assertTrue(any("CONCLUÍDAS" in t for t in c["advertencias"]))


@unittest.skipUnless(P.NODE, "Node.js não instalado")
class CelulasPurasTest(unittest.TestCase):
    def test_celulas_do_caderno(self):
        v2 = {"ind": CD.indicadores(_v2("a" * 32))}
        v16 = {"ind": CD.indicadores(_v16("d" * 32))}
        r = P.node("return [api.celulasInd(Fs[0]), api.celulasInd(Fs[1]), api.celulasInd({}), api.celulasInd({ ind: { erro: 'x' } }), "
                   "api.difTxt({ dif_abs: -10, dif_rel: -0.1 }), api.difTxt({ dif_abs: 5, dif_rel: null }), api.difTxt({ dif_abs: null })];",
                   v2, v16, componente="caderno", puros="celulasInd, difTxt")
        self.assertEqual(r[0], {"malha": "Δ 60 min · N 2 · m 1 · H_L 3", "pcc": "conectado", "custo": "realizado R$ 100,00", "imp": "40,0 kWh",
                                "h2": "1,250 kg", "sinal": "2 válido(s) / 3 janela(s) · 1 degradado(s)", "integ": "auditoria aprovada · 2 arq."})
        self.assertEqual(r[1], {"malha": "60 s · N 3", "pcc": "não aplicável", "custo": "f. objetivo R$ 88,30", "imp": "N/D", "h2": "3,500 kg",
                                "sinal": "não aplicável", "integ": "1 arq."})
        self.assertEqual(r[2]["malha"], "N/D")
        self.assertEqual(r[3]["integ"], "resumo ilegível")
        self.assertEqual(r[4:], ["-10,00 (-10,0 %)", "+5,00", "—"])


@unittest.skipUnless(P.NODE and P.navegador_disponivel(), "Chromium/Playwright (Node) não instalados")
class ComparadorNoNavegadorTest(unittest.TestCase):
    def test_comparador_desenha_e_devolve_as_acoes(self):
        a, b = _v2("a" * 32, custo=100.0), _v2("b" * 32, custo=90.0, versao=2)
        cmp_ = CD.comparar(_Store(a, b), a.run_uid, b.run_uid)
        cmp_["sel"] = [a.run_uid, b.run_uid]
        lin = lambda r: {"uid": r.run_uid, "cenario_uid": r.scenario_uid, "cenario": "Dia útil", "versao": r.scenario_version, "motor": "V2",  # noqa: E731
                         "estado": "concluida", "estado_rotulo": "Concluída", "tom": "ok", "criada": "", "finalizada": "", "revisao": 1,
                         "resultado": "", "dados": 2, "cenario_existe": True, "ind": CD.indicadores(r)}
        d = {"cenarios": [], "rodadas": [lin(a), lin(b)], "estudos": [], "rotulos": {"concluida": "Concluída"}, "microrrede": {"nome": "T", "revisao": 1},
             "comparacao": cmp_}
        sem = dict(d, comparacao=None)
        sem["rodadas"] = [lin(a), lin(b), dict(lin(a), uid="c" * 32)]
        r = P.bancada({"cmp": d}, passos=[["texto", "t"], ["avaliar", "n", "document.querySelectorAll('.pt.caderno .cd-graf path.cd-la').length"],
                                          ["clicar", ".pt.caderno .cd-abrir-b"], ["avaliar", "acoes", "window.__acoes.map((x) => [x.type, x.run])"]],
                      componente="caderno")["cmp"]
        self.assertEqual(r["erros"], [])
        self.assertEqual(r["vistas"]["n"], 3)
        self.assertEqual(r["vistas"]["acoes"], [["abrir_rodada", "b" * 32]])
        for t in ("Comparar rodadas", "Rodada A · V2", "Versão do cenário", "difere", "-10,00 (-10,0 %)", "Comparação temporal · mesma malha",
                  "Custo realizado acumulado [R$]", "Δ 60 min · N 2 · m 1 · H_L 3", "auditoria aprovada"):
            self.assertIn(t, r["vistas"]["t"])
        selecionar = ("const s = document.querySelectorAll('.pt.caderno .cd-sel'); s[0].value = 'a'.repeat(32); s[0].dispatchEvent(new Event('change'));"
                      "s[1].value = 'c'.repeat(32); s[1].dispatchEvent(new Event('change')); 1")
        r = P.bancada({"sem": sem}, passos=[["texto", "t"], ["avaliar", "_", selecionar], ["clicar", ".pt.caderno .cd-comparar"],
                                            ["avaliar", "acoes", "window.__acoes.map((x) => [x.type, x.a, x.b])"]], componente="caderno")["sem"]
        self.assertEqual(r["erros"], [])
        self.assertEqual(r["vistas"]["acoes"], [["comparar", "a" * 32, "c" * 32]])
        self.assertIn("Escolha as rodadas A e B", r["vistas"]["t"])


@unittest.skipUnless(P.SOLVER and AppTest is not None, "Pyomo/HiGHS ou Streamlit não instalados")
class ComparacaoRealTest(unittest.TestCase):
    """Duas rodadas REAIS (HiGHS) da mesma versão do cenário: comparação pelos registros gravados, sem solver na leitura."""

    def test_duas_rodadas_reais_da_mesma_versao(self):
        from integracao_v2 import execucao as X

        with tempfile.TemporaryDirectory() as d:
            _uid, st, run = P.missao_hibrida(d, "Comparação (teste)")
            cur = st.get_scenario(run.scenario_uid)
            run2 = X.submit(st, cur.scenario_uid, cur.version, X.new_request_id(), background=False)
            self.assertEqual(run2.state, "concluida")
            antes = copy.deepcopy([(r.run_uid, r.state, r.summary) for r in st.list_runs()])
            with mock.patch("integracao_v2.execucao.submit", side_effect=AssertionError("motor chamado")), \
                    mock.patch.dict(sys.modules, {"pyomo": None, "highspy": None}):
                c = CD.comparar(st, run.run_uid, run2.run_uid)
            self.assertEqual([x["item"] for x in c["condicoes"] if not x["igual"]], [])
            self.assertEqual(c["advertencias"], [])
            cu = next(l for l in c["linhas"] if l["chave"] == "custo")
            self.assertEqual(cu["a"], run.summary["mission"]["custo_realizado_total_R"])
            self.assertEqual(cu["b"], run2.summary["mission"]["custo_realizado_total_R"])
            self.assertTrue(c["temporal"]["ok"])
            import pandas as pd
            df = pd.read_csv(io.BytesIO(st.run_data(run.run_uid, "v2/intervalos.csv")))
            s0 = c["temporal"]["series"][0]
            self.assertEqual(s0["a"], [float(v) for v in df["custo_realizado_acumulado_R"]])
            self.assertEqual(c["temporal"]["instantes"], [str(v) for v in df["inicio_utc"]])
            self.assertEqual(antes, [(r.run_uid, r.state, r.summary) for r in st.list_runs()])   # nada gravado

    def test_caderno_ignora_selecao_de_outra_microrrede(self):
        from apptest_utils import APP_PATH

        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"SEEDS2_DATA_DIR": d}):
            uid, st, run = P.missao_hibrida(d, "Caderno (teste)")
            app = AppTest.from_file(str(APP_PATH), default_timeout=240)
            app.session_state["mg_active_uid"] = uid
            app.session_state["seeds_route"] = {"view": "operacao", "tab": "caderno"}
            app.session_state[CD.CMP_KEY] = (run.run_uid, "f" * 32)                 # B não pertence a esta microrrede
            app.run()
            self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
            data = CD.dados(st)
            self.assertEqual(data["rodadas"][0]["ind"]["custo"], run.summary["mission"]["custo_realizado_total_R"])


if __name__ == "__main__":
    unittest.main()
