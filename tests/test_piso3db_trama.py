"""Piso 3D-B0 — marco de dados Trama: lê a evidência PERSISTIDA de uma rodada V2 real e a reproduz sem alterar nada.

* valores do marco = valores gravados (bit a bit), por UID; intervalos (N) × fronteiras (N + 1) separados;
* ausente vira ``None`` (N/D na interface), nunca zero;
* montagem sem solver, sem modelos físicos e sem gravar; rodada não concluída ou de outro motor é recusada;
* o modelo de vista do navegador (JavaScript, executado em Node) agrega exatamente as colunas gravadas.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import piso3db_util as U  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from integracao_v2 import trama_frame as TF  # noqa: E402

ESTATICO = RAIZ / "seeds2" / "ui" / "static" / "trama"
NODE = shutil.which("node")


def _lista(serie) -> list:
    return [None if pd.isna(x) else float(x) for x in serie.tolist()]


class ColunaTest(unittest.TestCase):
    def test_ausente_e_nan_viram_none_e_nunca_zero(self):
        df = pd.DataFrame({"a": [1.5, float("nan"), 0.0], "t": ["x", None, "z"]})
        self.assertIsNone(TF._col(df, "nao_existe"))                    # coluna não persistida ⇒ N/D
        self.assertEqual(TF._col(df, "a"), [1.5, None, 0.0])            # NaN ⇒ None; zero gravado continua zero
        self.assertEqual(TF._col(df, "t"), ["x", None, "z"])
        self.assertIsNone(TF._v(float("inf")))

    def test_recusa_rodada_nao_concluida_ou_de_outro_motor(self):
        v2 = {"engine": {"id": "milp_mpc_v1"}}
        for run in (SimpleNamespace(manifest=v2, state="interrompida"), SimpleNamespace(manifest=v2, state="falhou"),
                    SimpleNamespace(manifest={"engine": {"id": "legacy_v16"}}, state="concluida"),
                    SimpleNamespace(manifest=None, state="concluida")):
            with self.assertRaises(RG.IntegridadeV2Error):
                TF.montar(None, run)


@unittest.skipUnless(U.SOLVER, "Pyomo/HiGHS não instalados")
class MarcoDeRodadaRealTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.uid, cls.st, cls.rodada = U.missao_hibrida(cls._tmp.name)
        cls.it = RG.ler_csv(cls.st, cls.rodada, RG.N_INTERVALOS)
        cls.fr = RG.ler_csv(cls.st, cls.rodada, RG.N_FRONTEIRAS)
        cls.frame = TF.montar(cls.st, cls.rodada, verificacao=RG.verificar(cls.st, cls.rodada))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_valores_do_marco_sao_os_gravados_bit_a_bit(self):
        f, it, fr = self.frame, self.it, self.fr
        self.assertEqual((f["formato"], f["versao"]), (TF.FORMATO, TF.VERSAO))
        self.assertEqual(f["rodada"]["K"], len(it))
        for chave in ("demanda_prevista_kW", "demanda_realizada_kW", "demanda_nao_atendida_kW", "demanda_atendida_kW",
                      "pcc_importacao_programada_kW", "pcc_importacao_realizada_kW", "tarifa_importacao_decisao_R_kWh",
                      "custo_importacao_R", "custo_realizado_intervalo_R", "custo_realizado_acumulado_R",
                      "residuo_balanco_kW"):
            self.assertEqual(f["intervalos"][chave], _lista(it[chave]), chave)
        self.assertEqual(len(f["fronteiras"]["utc"]), len(it) + 1)                    # N intervalos, N + 1 fronteiras
        for tipo, grandezas in (("renovaveis", {"P_R_kW": "P_R_kW", "A_utilizavel_kW": "A_utilizavel_kW",
                                                "vertimento_kW": "vertimento_kW"}),
                                ("baterias", {"P_c_kW": "P_c_kW", "P_d_kW": "P_d_kW"}),
                                ("pemfc", {"p_kW": "p_kW", "q_h2_kg_h": "q_h2_kg_h", "m_h2_kg": "m_h2_kg",
                                           "custo_h2_R": "custo_h2_R"})):
            self.assertTrue(f[tipo])
            for uid, rec in f[tipo].items():
                for campo, col in grandezas.items():
                    self.assertEqual(rec[campo], _lista(it[f"{uid}|{col}"]), (uid, col))
        for uid, rec in f["baterias"].items():
            self.assertEqual(rec["energia_kWh"], _lista(fr[f"{uid}|energia_kWh"]))    # estado de fronteira, N + 1 pontos
            self.assertEqual(len(rec["energia_kWh"]), len(rec["P_d_kW"]) + 1)

    def test_identidade_por_uid_e_resumo_selado(self):
        f, s = self.frame, self.rodada.summary["mission"]
        self.assertEqual({r["uid"] for r in f["recursos"]["bat"]}, set(s["baterias"]))
        self.assertEqual({r["uid"] for k in ("fv", "wt") for r in f["recursos"][k]}, set(s["renovaveis"]))
        self.assertEqual({r["uid"] for r in f["recursos"]["fc"]}, set(s["pemfc"]))
        self.assertEqual(f["resumo"]["custo_realizado_total_R"], s["custo_realizado_total_R"])
        self.assertEqual(f["resumo"]["componentes_R"], s["custo_realizado_componentes_R"])
        self.assertEqual(f["rodada"]["uid"], self.rodada.run_uid)
        self.assertTrue(f["verificacao"]["ok"])
        self.assertEqual(f["pcc"]["limite_importacao_kW"], 25.0)                      # declaração do cenário, no manifesto

    def test_curva_certificado_e_dinamica_vem_dos_arquivos_gravados(self):
        doc = RG.ler_json(self.st, self.rodada, RG.N_PEMFC)
        din = RG.ler_json(self.st, self.rodada, RG.N_PEMFC_DIN)
        for uid, rec in self.frame["pemfc"].items():
            reg = doc["registros"][uid.split("#")[0]]
            self.assertEqual(rec["curva"]["P_kW"], reg["curva"]["ajuste"]["P_kW"])               # sem decimação
            self.assertEqual(rec["curva"]["q_suprido_kg_h"], reg["curva"]["ajuste"]["q_suprido_kg_h"])
            self.assertEqual(rec["curva"]["vertices"], reg["certificado_b04"]["vertices"])
            self.assertEqual(rec["curva"]["b04"]["criterios"], reg["curva"]["b04"]["criterios"])
            self.assertEqual([x["p_entregue_media_kW"] for x in rec["dinamica"]["intervalos"]],
                             [x["p_entregue_media_kW"] for x in din["unidades"][uid]["intervalos"]])

    def test_hash_estavel_json_estrito_e_nenhuma_gravacao(self):
        antes = {n: d["sha256"] for n, d in self.st.get_run(self.rodada.run_uid).data.items()}
        outro = TF.montar(self.st, self.rodada, verificacao=RG.verificar(self.st, self.rodada))
        self.assertEqual(outro["hash"], self.frame["hash"])
        json.dumps(self.frame, allow_nan=False)                                        # nenhum NaN/Infinity chega ao navegador
        self.assertEqual({n: d["sha256"] for n, d in self.st.get_run(self.rodada.run_uid).data.items()}, antes)

    def test_montagem_sem_solver_nem_modelos(self):
        falha = AssertionError("modelo/curva/motor chamado ao montar o marco")
        with mock.patch("integracao_v2.execucao.submit", side_effect=falha), \
                mock.patch("integracao_v2.curva_h2.obter_curva", side_effect=falha), \
                mock.patch("integracao_v2.pemfc_dinamica.verificar_despacho", side_effect=falha), \
                mock.patch("integracao_v2.montagem.construir_missao", side_effect=falha), \
                mock.patch.dict(sys.modules, {"pyomo": None, "highspy": None}):
            self.assertEqual(TF.montar(self.st, self.rodada)["rodada"]["K"], len(self.it))

    @unittest.skipUnless(NODE, "Node.js não instalado")
    def test_modelo_de_vista_do_navegador_agrega_as_colunas_gravadas(self):
        harness = (
            "const fs = require('fs');"
            f"const src = fs.readFileSync({json.dumps(str(ESTATICO / 'trama.js'))}, 'utf8') + '\\n' + "
            f"fs.readFileSync({json.dumps(str(ESTATICO / 'partitura.js'))}, 'utf8').replace('export default function', 'function __componente');"
            "const api = new Function(src + '\\nreturn { modelo, teto, acum, soma };')();"
            "const F = JSON.parse(fs.readFileSync(process.argv[1], 'utf8')), M = api.modelo(F), s = api.soma;"
            "console.log(JSON.stringify({ K: M.K, ord: M.ord, rot: M.rot.slice(0, 3), n_rot: M.rot.length, wtP: s(M.A.wtP), fvP: s(M.A.fvP),"
            " pd: s(M.A.pd), pc: s(M.A.pc), fcP: s(M.A.fcP), impR: s(M.A.impR), fr: M.A.fr, teto: [api.teto(0), api.teto(37), api.teto(120)],"
            " acum: api.acum([1, null, 2]), janelas: M.jan.length, validas: M.jan.filter((w) => w.ok).length }));")
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "frame.json"
            arq.write_text(json.dumps(self.frame, allow_nan=False), encoding="utf-8")
            r = subprocess.run([NODE, "-e", harness, str(arq)], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        js, f, it = json.loads(r.stdout), self.frame, self.it
        self.assertEqual(js["K"], len(it))
        self.assertEqual(js["n_rot"], len(it) + 1)
        self.assertEqual(js["ord"], ["fv", "wt", "bat", "fc", "grid", "dem", "eco"])
        tot = lambda uids, col: math.fsum(float(it[f"{u}|{col}"].sum()) for u in uids)  # noqa: E731
        uids = lambda k: [r["uid"] for r in f["recursos"][k]]  # noqa: E731
        for chave, valor in (("wtP", tot(uids("wt"), "P_R_kW")), ("fvP", tot(uids("fv"), "P_R_kW")),
                             ("pd", tot(uids("bat"), "P_d_kW")), ("pc", tot(uids("bat"), "P_c_kW")),
                             ("fcP", tot(uids("fc"), "p_kW")), ("impR", float(it["pcc_importacao_realizada_kW"].sum()))):
            self.assertTrue(math.isclose(js[chave], valor, rel_tol=1e-12, abs_tol=1e-9), (chave, js[chave], valor))
        self.assertEqual(js["fr"], list(f["baterias"][uids("bat")[0]]["energia_kWh"]))  # um banco: soma = o próprio estado
        self.assertEqual(js["acum"], [0, 1, 1, 3])
        self.assertEqual(js["teto"][0], 1)
        self.assertGreaterEqual(js["teto"][1], 37)
        s = self.rodada.summary["mission"]
        self.assertEqual(js["janelas"], s["janelas"])
        self.assertEqual(js["validas"], (s.get("sinal_valor_futuro") or {}).get("valido"))


if __name__ == "__main__":
    unittest.main()
