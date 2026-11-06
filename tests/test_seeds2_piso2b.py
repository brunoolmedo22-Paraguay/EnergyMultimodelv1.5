"""Piso 2B — Previsões e Dados: fontes (manual, CSV, sintético, referência), normalização, unidades, validações
temporais e físicas, representação canônica e persistência (blobs na mesma transação do cenário, versões
imutáveis, conflito, isolamento, integridade, reinício). Sem interface (ver ``test_seeds2_piso2b_app.py``).

Todos os dados são SINTÉTICOS gerados aqui ou conjuntos de referência já versionados no software.
"""
from __future__ import annotations

import copy
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from seeds2.microgrid import adapter as A
from seeds2.microgrid import config as C
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.microgrid.store import MicrogridStore, ScenarioConflictError, StoreError
from seeds2.operation import contracts
from seeds2.operation import forecast_sources as FS
from seeds2.operation import forecasts as F
from seeds2.operation import initialization as I
from seeds2.operation import scenarios as S
from seeds2.operation import service
from seeds2_fixtures import v16_equivalent_config

RAIZ = Path(__file__).resolve().parents[1]


def _wind_cfg(name: str = "Microrrede FV + eólica") -> dict:
    cfg = v16_equivalent_config(name)
    C.add_equipment(cfg, C.new_equipment("wind", "Aerogerador", tag="WT-01", params={"reference": "EWT DW61-1MW", "count": 1}))
    return cfg


def _ref(cfg: dict | None = None) -> dict:
    cfg = cfg or v16_equivalent_config()
    return S.inventory_reference(cfg, 1, "a" * 64)


def _csv(text: str) -> bytes:
    return text.encode("utf-8")


def _demand_csv(n: int = 121, start: str = "2026-09-01 10:00", step_min: int = 1, sep: str = ";", decimal: str = ",",
                offset: str = "", header: str = "P_kW") -> tuple[bytes, np.ndarray]:
    t = pd.date_range(start, periods=n, freq=f"{step_min}min")
    p = np.round(140 + 25 * np.sin(np.arange(n) / 12.0), 2)
    rows = [f"timestamp{sep}{header}"]
    for x, v in zip(t, p):
        rows.append(f"{x:%Y-%m-%dT%H:%M:%S}{offset}{sep}{str(v).replace('.', decimal)}")
    return _csv("\n".join(rows) + "\n"), p


def _climate_frame(n: int = 37, start: str = "2026-09-01 08:00", step_min: int = 10) -> pd.DataFrame:
    t = pd.date_range(start, periods=n, freq=f"{step_min}min")
    h = t.hour + t.minute / 60
    return pd.DataFrame({"timestamp": t.strftime("%Y-%m-%d %H:%M"),
                         "GHI_W_m2": np.round(np.clip(900 * np.sin(np.pi * (h - 6) / 12), 0, None), 1),
                         "temperature_C": np.round(24 + 4 * np.sin(np.pi * (h - 9) / 12), 2),
                         "wind_speed_mps": np.round(7 + np.sin(np.arange(n) / 4), 2),
                         "wind_direction_deg": np.round((350 + 5 * np.arange(n)) % 360, 1),
                         "pressure_hPa": 1012.0, "humidity_pct": 70.0})


def _confirm(mapping: dict) -> dict:
    """Confirma as unidades canônicas das colunas cuja unidade não foi detectada (ação explícita do usuário)."""
    m = copy.deepcopy(mapping)
    for k, v in m["columns"].items():
        v["unit"] = v["unit"] or F.VARIABLES[k].unit
    return m


def _csv_cand(data: bytes, slot: str, ref: dict, *, mapping: dict | None = None, provenance: str = "nao_declarado",
              name: str = "dados.csv") -> F.Candidate:
    insp = FS.inspect_csv(data, name, slot)
    assert insp.ok, insp.errors
    return FS.csv_candidate(insp, slot, mapping or _confirm(insp.suggestion), inventory_ref=ref, provenance=provenance)


def _codes(c: F.Candidate, level: str | None = None) -> set[str]:
    return {f.code for f in c.analysis.findings if level is None or f.level == level}


def _blob_reader(c: F.Candidate):
    return lambda h: c.blobs[h][0]


# =========================================================================== fontes
class PerfilManualTest(unittest.TestCase):
    def test_tabela_regular_valores_colados_e_validacao(self):
        ref = _ref()
        tbl = FS.regular_table(("demand_kW",), "2026-09-01 08:00", 60, 120)
        self.assertEqual(len(tbl), 120)
        self.assertTrue(tbl["demand_kW"].isna().all())                       # nada presumido (vazio, não zero)
        vals, bad = FS.parse_pasted("\n".join(f"{100 + i},5" for i in range(120)))
        self.assertEqual(bad, [])
        self.assertEqual(vals[:2], [100.5, 101.5])                             # vírgula = decimal
        tbl["demand_kW"] = vals
        c = FS.manual_candidate(tbl, "demand", timezone="America/Sao_Paulo", inventory_ref=ref, provenance="medido",
                                construction={"start": "2026-09-01 08:00", "step_min": 1, "points": 120})
        self.assertTrue(c.ok, c.analysis.findings)
        e = c.entry
        self.assertEqual((e["source_type"], e["provenance"], e["n_points"], e["step_s"], e["regular"], e["timezone"]),
                         ("manual", "medido", 120, 60.0, True, "America/Sao_Paulo"))
        self.assertEqual((e["t0"], e["t_end"], e["horizon_s"]), ("2026-09-01T08:00:00", "2026-09-01T09:59:00", 7140.0))
        df = F.from_csv_bytes(c.blobs[e["data"]][0])
        np.testing.assert_array_equal(df["demand_kW"].to_numpy(), np.array(vals))
        self.assertEqual(FS.rederive(e, _blob_reader(c))[0], True)
        self.assertEqual(contracts.forecast_errors({"demand": e}), [])
        self.assertEqual(F.entry_errors("demand", e), [])

    def test_ausentes_linhas_vazias_e_instantes_invalidos(self):
        ref = _ref()
        tbl = FS.regular_table(("demand_kW",), "2026-09-01 08:00", 60, 5, {"demand_kW": [10, None, 30, 40, 50]})
        tbl = pd.concat([tbl, pd.DataFrame({"timestamp": pd.to_datetime([None]),          # linha vazia: ignorada
                                            "demand_kW": pd.array([None], dtype="Float64")})], ignore_index=True)
        c = FS.manual_candidate(tbl, "demand", timezone=None, inventory_ref=ref, provenance="nao_declarado")
        self.assertFalse(c.ok)                                                 # ausente em variável obrigatória
        self.assertIn("ausentes", _codes(c, I.ERROR))
        tbl = pd.DataFrame({"timestamp": pd.to_datetime(["2026-09-01 08:00", "2026-09-01 08:01", "2026-09-01 08:02", None]),
                            "demand_kW": [10.0, 20.0, 30.0, 40.0]})                    # último valor sem instante
        c = FS.manual_candidate(tbl, "demand", timezone=None, inventory_ref=ref, provenance="nao_declarado")
        self.assertIn("timestamp_invalido", _codes(c, I.ERROR))
        vals, bad = FS.parse_pasted("1;2;abc;-")
        self.assertEqual((vals, bad), ([1.0, 2.0, None, None], ["abc"]))


class ImportacaoCSVTest(unittest.TestCase):
    def test_csv_de_demanda_com_fuso_virgula_decimal_e_original_preservado(self):
        ref = _ref()
        data, p = _demand_csv(offset="-03:00")
        c = _csv_cand(data, "demand", ref, name="demanda.csv")
        self.assertTrue(c.ok, c.analysis.findings)
        e = c.entry
        self.assertEqual((e["timezone"], e["timezone_source"]), ("UTC-03:00", "arquivo"))
        self.assertEqual(e["t0"], "2026-09-01T10:00:00")                       # relógio de parede do fuso do arquivo
        self.assertNotIn("fuso_nao_declarado", _codes(c))
        df = F.from_csv_bytes(c.blobs[e["data"]][0])
        np.testing.assert_array_equal(df["demand_kW"].to_numpy(), p)
        self.assertEqual(c.blobs[e["blob"]][0], data)                          # arquivo ORIGINAL byte a byte
        self.assertNotEqual(e["blob"], e["data"])
        self.assertEqual(e["mapping"]["columns"], {"demand_kW": {"column": "P_kW", "unit": "kW"}})
        self.assertEqual(e["params"]["sha256"], e["blob"])
        ok, msg = FS.rederive(e, _blob_reader(c))
        self.assertTrue(ok, msg)

    def test_variaveis_meteorologicas_e_conjunto_compartilhado(self):
        ref = _ref(_wind_cfg())
        reqs = F.climate_requirements(ref)
        self.assertEqual([k for k, r in reqs.items() if r["required"]], ["ghi_W_m2", "temperature_C", "wind_speed_m_s"])
        self.assertEqual(reqs["temperature_C"]["techs"], ["pv", "wind"])       # compartilhada por FV e eólica
        df = _climate_frame()
        c = _csv_cand(df.to_csv(index=False).encode(), "climate", ref)
        self.assertTrue(c.ok, c.analysis.findings)
        self.assertEqual(c.entry["variables"], list(F.SLOT_VARIABLES["climate"]))
        self.assertIn("grade_ems", _codes(c, I.PENDING))                       # 10 min ≠ grade de 1 min do EMS
        # só FV: variáveis do vento continuam registradas, mas sinalizadas como sem uso
        c2 = _csv_cand(df.to_csv(index=False).encode(), "climate", _ref())
        self.assertIn("variavel_sem_uso", _codes(c2, I.WARNING))
        # sem GHI: série válida, mas incompleta para a FV (não é erro; a prontidão acusa)
        c3 = _csv_cand(df.drop(columns=["GHI_W_m2"]).to_csv(index=False).encode(), "climate", ref)
        self.assertTrue(c3.ok)
        self.assertIn("obrigatoria_ausente", _codes(c3, I.INCOMPLETE))
        # sem renováveis habilitadas: nada é exigido
        cfg = v16_equivalent_config()
        for eq in cfg["equipment"]:
            if eq["kind"] == "pv":
                eq["enabled"] = False
        self.assertEqual(F.climate_requirements(_ref(cfg)), {})
        self.assertEqual(F.required_variables("climate", _ref(cfg)), ())

    def test_deteccao_e_mapeamento_de_colunas(self):
        ins = FS.inspect_csv(_csv("timestamp;GHI;Tamb\n2026-03-21 12:01:00;976,8;29,9\n2026-03-21 12:02:00;984,0;30,0\n"),
                             "solar.csv", "climate")
        self.assertTrue(ins.ok)
        self.assertEqual(ins.suggestion["time_column"], "timestamp")
        self.assertEqual({k: v["column"] for k, v in ins.suggestion["columns"].items()},
                         {"ghi_W_m2": "GHI", "temperature_C": "Tamb"})
        self.assertEqual(ins.detected_units, {"ghi_W_m2": None, "temperature_C": None})     # sem unidade no cabeçalho
        # unidade não confirmada → erro explícito; confirmada → válida
        c = FS.csv_candidate(ins, "climate", ins.suggestion, inventory_ref=_ref(), provenance="nao_declarado")
        self.assertIn("unidade_nao_confirmada", _codes(c, I.ERROR))
        c = FS.csv_candidate(ins, "climate", _confirm(ins.suggestion), inventory_ref=_ref(), provenance="nao_declarado")
        self.assertTrue(c.ok)
        np.testing.assert_array_equal(c.df["ghi_W_m2"].to_numpy(), [976.8, 984.0])
        # demanda: aliases do MIX e palavras-chave da ponte V1.6; unidades no cabeçalho
        for header, unit in (("P_demanda_total_kW", "kW"), ("Potencia_W", "W"), ("carga_MW", "MW"), ("load", None)):
            ins = FS.inspect_csv(_csv(f"data_hora,{header}\n2026-01-01 00:00,1\n2026-01-01 00:01,2\n"), "d.csv", "demand")
            self.assertEqual(ins.suggestion["columns"]["demand_kW"], {"column": header, "unit": unit}, header)
            self.assertEqual(ins.suggestion["time_column"], "data_hora")
        # tempo relativo (como os CSVs COPEL): exige o instante inicial explícito
        data = _csv("t_min,P_kW\n0,10\n1,11\n2,12\n")
        ins = FS.inspect_csv(data, "rel.csv", "demand")
        self.assertEqual((ins.suggestion["time_mode"], ins.suggestion["relative_unit"]), ("relativo", "min"))
        c = FS.csv_candidate(ins, "demand", ins.suggestion, inventory_ref=_ref(), provenance="nao_declarado")
        self.assertIn("sem_referencia", _codes(c, I.ERROR))
        m = dict(ins.suggestion, t0="2026-09-01 06:00")
        c = FS.csv_candidate(ins, "demand", m, inventory_ref=_ref(), provenance="nao_declarado")
        self.assertTrue(c.ok)
        self.assertEqual((c.entry["t0"], c.entry["t_end"]), ("2026-09-01T06:00:00", "2026-09-01T06:02:00"))

    def test_unidades_convertidas_e_registradas(self):
        ref = _ref(_wind_cfg())
        cases = {"demand_kW": [("W", 1500.0, 1.5), ("MW", 0.2, 200.0), ("kW", 3.0, 3.0)],
                 "ghi_W_m2": [("kW/m²", 0.8, 800.0)],
                 "temperature_C": [("K", 300.15, 27.0), ("°F", 212.0, 100.0)],
                 "wind_speed_m_s": [("km/h", 36.0, 10.0), ("nó (kn)", 10.0, 5.144444444444445)],
                 "pressure_hPa": [("Pa", 101325.0, 1013.25), ("kPa", 101.3, 1013.0), ("mbar", 1000.0, 1000.0)],
                 "humidity_pct": [("fração (0–1)", 0.65, 65.0)]}
        for var, rows in cases.items():
            for unit, raw, expected in rows:
                self.assertAlmostEqual(float(F.convert(var, np.array([raw]), unit)[0]), expected, places=9, msg=(var, unit))
        self.assertEqual(F.detect_unit("pressure_hPa", "pressure_Pa"), "Pa")
        self.assertEqual(F.detect_unit("temperature_C", "temp_K"), "K")
        self.assertIsNone(F.detect_unit("ghi_W_m2", "GHI"))
        data = _csv("timestamp,P_W\n2026-01-01 00:00,1500\n2026-01-01 00:01,2500\n")
        c = _csv_cand(data, "demand", ref)
        np.testing.assert_allclose(c.df["demand_kW"].to_numpy(), [1.5, 2.5])
        self.assertTrue(any("convertida para kW" in t for t in c.entry["transforms"]))


class SinteticoTest(unittest.TestCase):
    P = {"t0": "2026-09-01 00:00", "step_s": 300, "duration_s": 86400, "base_kW": 60,
         "peaks": [{"hour": 12, "width_h": 2, "kW": 80}, {"hour": 19, "width_h": 1.5, "kW": 50}], "noise_pct": 5, "seed": 11}

    def test_determinismo_semente_e_procedencia(self):
        ref = _ref()
        a = FS.synthetic_candidate("demanda_diaria", self.P, timezone=None, inventory_ref=ref)
        b = FS.synthetic_candidate("demanda_diaria", dict(self.P), timezone=None, inventory_ref=ref)
        c = FS.synthetic_candidate("demanda_diaria", {**self.P, "seed": 12}, timezone=None, inventory_ref=ref)
        self.assertTrue(a.ok and b.ok and c.ok)
        self.assertEqual(a.entry["data"], b.entry["data"])                    # mesma semente → mesma série (SHA-256)
        self.assertNotEqual(a.entry["data"], c.entry["data"])                 # outra semente → outra série
        self.assertEqual((a.entry["source_type"], a.entry["provenance"]), ("sintetico", "sintetico"))
        self.assertEqual((a.entry["params"]["generator"], a.entry["params"]["generator_version"], a.entry["params"]["seed"]),
                         ("demanda_diaria", FS.GENERATOR_VERSION, 11))
        self.assertTrue(FS.rederive(a.entry, _blob_reader(a))[0])
        bad = copy.deepcopy(a.entry)
        bad["provenance"] = "medido"                                          # sintético nunca é medido
        self.assertTrue(contracts.forecast_errors({"demand": bad}))
        self.assertTrue(F.entry_errors("demand", bad))
        # demais geradores: constantes e tramos determinísticos sem ruído
        k = FS.synthetic_candidate("demanda_constante", {"t0": "2026-09-01 08:00", "step_s": 60, "duration_s": 7200,
                                                          "value_kW": 120}, timezone=None, inventory_ref=ref)
        self.assertTrue((k.df["demand_kW"] == 120).all())
        self.assertEqual(k.entry["n_points"], 121)
        self.assertAlmostEqual(k.entry["stats"]["demand_kW"]["energy_kWh"], 240.0)       # 120 kW × 2 h
        t = FS.synthetic_candidate("demanda_tramos", {"t0": "2026-09-01 00:00", "step_s": 3600, "duration_s": 86400,
                                                      "blocks": [[0, 80], [8, 150], [18, 200], [22, 90]]},
                                   timezone=None, inventory_ref=ref)
        got = dict(zip(t.df["timestamp"].dt.hour, t.df["demand_kW"]))
        self.assertEqual((got[7], got[8], got[17], got[18], got[23]), (80.0, 150.0, 150.0, 200.0, 90.0))
        cl = FS.synthetic_candidate("clima_simples", {"t0": "2026-09-01 00:00", "step_s": 600, "duration_s": 86400,
                                                      "variables": ["ghi_W_m2", "temperature_C"], "sunrise_h": 6,
                                                      "sunset_h": 18, "ghi_peak_W_m2": 900, "t_min_C": 18, "t_max_C": 30},
                                    timezone="UTC", inventory_ref=ref)
        self.assertTrue(cl.ok)
        night = cl.df[(cl.df["timestamp"].dt.hour < 6) | (cl.df["timestamp"].dt.hour >= 18)]
        self.assertTrue((night["ghi_W_m2"] == 0).all())
        self.assertAlmostEqual(cl.df["ghi_W_m2"].max(), 900.0)
        self.assertEqual(cl.entry["provenance"], "sintetico")
        bad = FS.synthetic_candidate("clima_simples", {"t0": "2026-09-01", "step_s": 600, "duration_s": 3600,
                                                       "variables": ["ghi_W_m2"], "sunrise_h": 18, "sunset_h": 6,
                                                       "ghi_peak_W_m2": 900}, timezone=None, inventory_ref=ref)
        self.assertFalse(bad.ok)


class ReferenciaTest(unittest.TestCase):
    def test_reutiliza_as_funcoes_e_dados_da_v16(self):
        import orchestrator_runtime as RT
        from ems_integration import ponte

        ref = _ref()
        wf = FS.reference_candidate("walkforward", {"scenario": "Ideal", "profile": "Normal", "start_hour": 12}, inventory_ref=ref)
        carga = ponte.carga_walkforward("Ideal", "Normal", 12)
        self.assertTrue(wf.ok)
        np.testing.assert_array_equal(wf.df["demand_kW"].to_numpy(), carga.P_kW)
        self.assertEqual(pd.Timestamp(wf.entry["t0"]), carga.t0)
        self.assertEqual((wf.entry["source_type"], wf.entry["provenance"], wf.entry["timezone"]),
                         ("referencia", "referencia", None))
        cp = FS.reference_candidate("copel_b1", {"day": "util", "date": "2026-09-01"}, inventory_ref=ref)
        np.testing.assert_array_equal(cp.df["demand_kW"].to_numpy(), ponte.carga_copel("util", "2026-09-01").P_kW)
        self.assertEqual(cp.entry["n_points"], 1440)                           # dia inteiro: nada recortado a 2 h
        cl = FS.reference_candidate("clima_sintetico_v16", {"t0": "2026-09-01 10:00", "duration_min": 120}, inventory_ref=ref)
        exp = RT.synthetic_climate(ponte.PerfilCarga(np.arange(121, dtype=float), np.zeros(121), pd.Timestamp("2026-09-01 10:00"), ""))
        np.testing.assert_array_equal(cl.df["ghi_W_m2"].to_numpy(), exp["GHI_W_m2"].to_numpy())
        np.testing.assert_array_equal(cl.df["wind_direction_deg"].to_numpy(), exp["wind_direction_deg"].to_numpy())
        self.assertEqual(cl.entry["provenance"], "sintetico")                  # clima de demonstração nunca é medido
        for key in FS.REFERENCES:
            p = {"walkforward": {"scenario": "Ideal", "profile": "Normal", "start_hour": 12},
                 "copel_b1": {"day": "domingo", "date": "2026-09-06"},
                 "clima_sintetico_v16": {"t0": "2026-09-01 06:00", "duration_min": 60}}.get(key, {})
            c = FS.reference_candidate(key, p, inventory_ref=ref)
            self.assertTrue(c.ok, (key, c.analysis.findings))
            self.assertNotEqual(c.entry["provenance"], "medido")
            ok, msg = FS.rederive(c.entry, _blob_reader(c))
            self.assertTrue(ok, (key, msg))
        # arquivo de referência alterado depois da gravação → reprodutibilidade acusada (não silenciosa)
        e = copy.deepcopy(FS.reference_candidate("previsao_solar_12", {}, inventory_ref=ref).entry)
        e["params"]["file_sha256"] = "0" * 64
        self.assertFalse(FS.rederive(e, lambda h: b"")[0])


# =========================================================================== validações
class ValidacaoTemporalTest(unittest.TestCase):
    def _demand(self, rows: list[str], **mapping) -> F.Candidate:
        data = _csv("timestamp,P_kW\n" + "\n".join(rows) + "\n")
        ins = FS.inspect_csv(data, "x.csv", "demand")
        return FS.csv_candidate(ins, "demand", {**ins.suggestion, **mapping}, inventory_ref=_ref(), provenance="nao_declarado")

    def test_duplicados_exigem_tratamento_explicito(self):
        rows = ["2026-01-01 00:00,10", "2026-01-01 00:01,20", "2026-01-01 00:01,40", "2026-01-01 00:02,30"]
        c = self._demand(rows)
        self.assertIn("duplicados", _codes(c, I.ERROR))
        self.assertFalse(c.ok)
        for pol, val in (("primeira", 20.0), ("ultima", 40.0), ("media", 30.0)):
            c = self._demand(rows, duplicates=pol)
            self.assertTrue(c.ok, pol)
            self.assertEqual(c.df["demand_kW"].tolist(), [10.0, val, 30.0])
            self.assertIn("duplicados_tratados", _codes(c, I.WARNING))
            self.assertTrue(any("repetido" in t for t in c.entry["transforms"]))
        # média circular para a direção do vento (350° e 10° → 0°, nunca 180°)
        raw = pd.DataFrame({"t": ["2026-01-01 00:00", "2026-01-01 00:00", "2026-01-01 00:01"], "d": [350.0, 10.0, 20.0]})
        norm = FS.normalize_csv(raw, {"time_column": "t", "duplicates": "media",
                                      "columns": {"wind_direction_deg": {"column": "d", "unit": "°"}}})
        self.assertAlmostEqual(norm.df["wind_direction_deg"].iloc[0] % 360, 0.0, places=9)

    def test_ordem_lacunas_resolucao_e_fuso(self):
        c = self._demand(["2026-01-01 00:02,30", "2026-01-01 00:00,10", "2026-01-01 00:01,20"])
        self.assertTrue(c.ok)
        self.assertEqual(c.df["demand_kW"].tolist(), [10.0, 20.0, 30.0])
        self.assertIn("fora_de_ordem", _codes(c, I.WARNING))
        self.assertIn("fuso_nao_declarado", _codes(c, I.WARNING))
        c = self._demand(["2026-01-01 00:00,10", "2026-01-01 00:01,20", "2026-01-01 00:02,30", "2026-01-01 00:30,40",
                          "2026-01-01 00:31,50"])
        self.assertIn("intervalos_ausentes", _codes(c, I.WARNING))
        self.assertEqual(c.entry["stats"]["demand_kW"]["missing"], 0)
        self.assertEqual(c.entry["n_points"], 5)                               # nada preenchido na lacuna
        self.assertAlmostEqual(c.entry["stats"]["demand_kW"]["energy_kWh"], (15 + 25 + 45) / 60)   # lacuna não integrada
        c = self._demand(["2026-01-01 00:00,10", "2026-01-01 00:01,20", "2026-01-01 00:02:30,30", "2026-01-01 00:03,40"])
        self.assertIn("resolucao_irregular", _codes(c, I.WARNING))
        self.assertFalse(c.entry["regular"])
        c = self._demand(["2026-01-01 00:00,10", "2026-01-01 00:01,20"], timezone="America/Sao_Paulo")
        self.assertEqual((c.entry["timezone"], c.entry["timezone_source"]), ("America/Sao_Paulo", "usuario"))
        self.assertNotIn("fuso_nao_declarado", _codes(c))
        c = self._demand(["2026-01-01 00:00,10", "2026-01-01 00:01,20"], timezone="Marte/Olympus")
        self.assertIn("fuso_invalido", _codes(c, I.ERROR))
        c = self._demand(["2026-01-01T00:00:00-03:00,10", "2026-01-01 00:01,20"])
        self.assertIn("fuso_misto", _codes(c, I.ERROR))
        c = self._demand(["2026-10-18T23:00:00-03:00,10", "2026-10-19T01:00:00-02:00,20"])     # mudança de offset
        self.assertEqual((c.entry["timezone"], c.entry["timezone_source"]), ("UTC", "arquivo_utc"))
        self.assertEqual(c.entry["t0"], "2026-10-19T02:00:00")
        c = self._demand(["03/04/2026 10:00,1", "04/04/2026 10:00,2"])
        self.assertIn("data_ambigua", _codes(c, I.ERROR))
        c = self._demand(["03/04/2026 10:00,1", "04/04/2026 10:00,2"], date_order="dia_mes")
        self.assertEqual(c.entry["t0"], "2026-04-03T10:00:00")
        c = self._demand(["03/04/2026 10:00,1", "04/04/2026 10:00,2"], date_order="mes_dia")
        self.assertEqual(c.entry["t0"], "2026-03-04T10:00:00")
        c = self._demand(["ontem,1", "hoje,2"])
        self.assertIn("timestamp_invalido", _codes(c, I.ERROR))
        c = self._demand(["2026-01-01 00:00,10"])
        self.assertIn("poucos_pontos", _codes(c, I.ERROR))

    def test_ausentes_e_nao_finitos(self):
        c = self._demand(["2026-01-01 00:00,10", "2026-01-01 00:01,", "2026-01-01 00:02,abc", "2026-01-01 00:03,40"])
        self.assertIn("ausentes", _codes(c, I.ERROR))                           # demanda é obrigatória
        c = self._demand(["2026-01-01 00:00,10", "2026-01-01 00:01,inf"])
        self.assertIn("nao_finito", _codes(c, I.ERROR))
        df = _climate_frame(5)
        df.loc[2, "humidity_pct"] = None                                        # opcional → aviso, não erro
        c = _csv_cand(df.to_csv(index=False).encode(), "climate", _ref(_wind_cfg()))
        self.assertTrue(c.ok)
        self.assertIn("ausentes", _codes(c, I.WARNING))
        self.assertTrue(np.isnan(c.df["humidity_pct"].iloc[2]))                 # ausente preservado (não zero)
        text = c.blobs[c.entry["data"]][0].decode().splitlines()[3]
        self.assertTrue(text.endswith(","), text)                               # célula vazia na série canônica
        df.loc[2, "GHI_W_m2"] = None                                            # obrigatória → erro
        c = _csv_cand(df.to_csv(index=False).encode(), "climate", _ref(_wind_cfg()))
        self.assertFalse(c.ok)

    def test_csv_malformados_nao_derrubam_a_interface(self):
        cases = {"vazio": b"", "espacos": b"   \n  \n", "binario": b"\x00\x01\x02PK\x03\x04" * 50,
                 "uma_coluna": b"apenas\n1\n2\n", "so_cabecalho": b"timestamp,P_kW\n",
                 "lixo": "çãõ;;;\n\"aberta;1\n;;;;\n".encode("latin-1"), "colunas_repetidas": b"a,a\n1,2\n3,4\n"}
        for name, data in cases.items():
            ins = FS.inspect_csv(data, f"{name}.csv", "demand")
            self.assertFalse(ins.ok, name)
            self.assertTrue(ins.errors, name)
            c = FS.csv_candidate(ins, "demand", {}, inventory_ref=_ref(), provenance="nao_declarado")
            self.assertFalse(c.ok, name)
        ins = FS.inspect_csv(b"x" * (FS.MAX_CSV_BYTES + 1), "grande.csv", "demand")
        self.assertIn("MB", ins.errors[0])
        # colunas inexistentes/repetidas no mapeamento → erro explicativo
        ins = FS.inspect_csv(_csv("timestamp,P_kW\n2026-01-01 00:00,1\n2026-01-01 00:01,2\n"), "ok.csv", "demand")
        c = FS.csv_candidate(ins, "demand", {**ins.suggestion, "columns": {"demand_kW": {"column": "nao_existe", "unit": "kW"}}},
                             inventory_ref=_ref(), provenance="nao_declarado")
        self.assertIn("coluna_inexistente", _codes(c, I.ERROR))
        c = FS.csv_candidate(ins, "demand", {**ins.suggestion, "time_column": "x"}, inventory_ref=_ref(), provenance="nao_declarado")
        self.assertIn("sem_tempo", _codes(c, I.ERROR))


class ValidacaoFisicaTest(unittest.TestCase):
    def test_valores_fisicamente_invalidos_sao_recusados(self):
        ref = _ref(_wind_cfg())
        for col, val, code in (("GHI_W_m2", -5.0, "negativo"), ("wind_speed_mps", -1.0, "negativo"),
                               ("humidity_pct", 120.0, "fora_faixa"), ("wind_direction_deg", 400.0, "fora_faixa"),
                               ("pressure_hPa", 0.0, "nao_positivo"), ("temperature_C", -300.0, "abaixo_zero_absoluto")):
            df = _climate_frame(5)
            df.loc[1, col] = val
            c = _csv_cand(df.to_csv(index=False).encode(), "climate", ref)
            self.assertFalse(c.ok, col)
            self.assertIn(code, _codes(c, I.ERROR), col)
            self.assertIsNone(c.entry)                                          # nada incorporável
        data = _csv("timestamp,P_kW\n2026-01-01 00:00,10\n2026-01-01 00:01,-3\n")
        self.assertIn("negativo", _codes(_csv_cand(data, "demand", ref), I.ERROR))
        # plausibilidade: avisos (unidade suspeita), nunca bloqueio
        df = _climate_frame(5)
        df.loc[1, "GHI_W_m2"] = 1450.0
        df["pressure_hPa"] = 101325.0
        c = _csv_cand(df.to_csv(index=False).encode(), "climate", ref)
        self.assertTrue(c.ok)
        self.assertTrue({"acima_constante_solar", "implausivel"} <= _codes(c, I.WARNING))


# =========================================================================== pré-visualização
class PreVisualizacaoTest(unittest.TestCase):
    def test_graficos_com_os_dados_corretos(self):
        from seeds2.ui import forecast_charts as CH

        ref = _ref(_wind_cfg())
        data = _csv("timestamp,P_kW\n2026-01-01 00:00,10\n2026-01-01 00:01,20\n2026-01-01 00:02,30\n"
                    "2026-01-01 00:10,40\n2026-01-01 00:11,50\n")
        c = _csv_cand(data, "demand", ref)
        fig = CH.figure("demand", c.df, title="t", subtitle="s")
        tr = fig.data[0]
        self.assertEqual([y for y in tr.y if y is not None], [10.0, 20.0, 30.0, 40.0, 50.0])
        self.assertEqual(sum(1 for y in tr.y if y is None), 1)                  # linha interrompida na lacuna
        self.assertFalse(tr.connectgaps)
        self.assertEqual(fig.layout.yaxis.title.text, "Potência demandada (kW)")
        self.assertEqual(len(fig.layout.shapes), 1)                             # intervalo ausente sombreado
        fig = CH.figure("demand", c.df, title="t", subtitle="s", transformed=True)
        names = [t.name for t in fig.data]
        self.assertTrue(any("transformada" in n for n in names))
        g = next(t for t in fig.data if "transformada" in t.name)
        self.assertTrue(all(y is None for y, x in zip(g.y, g.x) if pd.Timestamp("2026-01-01 00:02") < x < pd.Timestamp("2026-01-01 00:10")))
        # clima: um painel (eixo Y próprio) por grandeza; nenhum eixo secundário
        cc = _csv_cand(_climate_frame(7).to_csv(index=False).encode(), "climate", ref)
        fig = CH.figure("climate", cc.df, title="t", subtitle="s")
        yaxes = [k for k in fig.layout.to_plotly_json() if k.startswith("yaxis")]
        self.assertEqual(len(yaxes), 6)
        self.assertTrue(all(fig.layout[k].overlaying is None for k in yaxes))
        units = [fig.layout[k].title.text for k in sorted(yaxes, key=lambda k: int(k[5:] or 1))]
        self.assertEqual(units, ["W/m²", "°C", "m/s", "°", "hPa", "%"])
        ghi = next(t for t in fig.data if t.name.startswith("GHI"))
        np.testing.assert_array_equal([y for y in ghi.y if y is not None], cc.df["ghi_W_m2"].to_numpy())
        # ausentes ficam marcados, não desenhados como zero
        df = _climate_frame(5)
        df.loc[2, "humidity_pct"] = None
        cm = _csv_cand(df.to_csv(index=False).encode(), "climate", ref)
        fig = CH.figure("climate", cm.df, title="t", subtitle="s")
        self.assertTrue(any(t.name == "Valor ausente" for t in fig.data))
        hum = [t for t in fig.data if t.name.startswith("Umidade")][0]
        self.assertIsNone(hum.y[2])

    def test_grade_transformada_sem_extrapolacao_e_angular(self):
        df = pd.DataFrame({"timestamp": pd.to_datetime(["2026-01-01 00:00:30", "2026-01-01 00:10:30"]),
                           "wind_direction_deg": [350.0, 10.0], "wind_speed_m_s": [5.0, 15.0]})
        g = F.grid_view(df, "wind_direction_deg")
        self.assertEqual(g["timestamp"].iloc[0], pd.Timestamp("2026-01-01 00:01"))     # sem extrapolar antes do 1º ponto
        self.assertEqual(g["timestamp"].iloc[-1], pd.Timestamp("2026-01-01 00:10"))
        mid = g.set_index("timestamp")["wind_direction_deg"]
        self.assertTrue(all((v >= 349.0) or (v <= 11.0) for v in mid))                 # 359° → 1° nunca passa por 180°
        s = F.grid_view(df, "wind_speed_m_s").set_index("timestamp")["wind_speed_m_s"]
        self.assertAlmostEqual(s[pd.Timestamp("2026-01-01 00:05")], 9.5)        # 5 + 10 × 270/600 (linear)
        self.assertTrue(np.all(np.diff(s.to_numpy()) > 0))


# =========================================================================== persistência
class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        os.environ["SEEDS2_DATA_DIR"] = str(self.dir)
        self.reg = MicrogridRegistry(self.dir)

    def tearDown(self):
        self._tmp.cleanup()

    def make(self, name: str = "Microrrede A", cfg: dict | None = None) -> tuple[str, MicrogridStore]:
        cfg = cfg or _wind_cfg(name)
        self.reg.create(cfg, origin="commissioning")
        uid = cfg["installation"]["uid"]
        return uid, self.reg.open(uid)

    @staticmethod
    def with_forecasts(st: MicrogridStore, sc, *cands: F.Candidate) -> tuple[dict, dict]:
        doc = copy.deepcopy(sc.document)
        blobs: dict = {}
        for c in cands:
            assert c.ok, c.analysis.findings
            doc["forecasts"][c.slot] = c.entry
            blobs.update(c.blobs)
        return doc, blobs

    @staticmethod
    def blob_count(st: MicrogridStore) -> int:
        with sqlite3.connect(st.path) as con:
            return con.execute("SELECT COUNT(*) FROM blobs").fetchone()[0]


def _demand_cand(ref: dict, value: float = 120.0, seed: int = 1) -> F.Candidate:
    return FS.synthetic_candidate("demanda_constante", {"t0": "2026-09-01 08:00", "step_s": 60, "duration_s": 7200,
                                                        "value_kW": value, "noise_pct": 2, "seed": seed},
                                  timezone="America/Sao_Paulo", inventory_ref=ref)


def _climate_cand(ref: dict) -> F.Candidate:
    return _csv_cand(_climate_frame().to_csv(index=False).encode(), "climate", ref, name="clima.csv")


class PersistenciaTest(_Base):
    def test_gravar_reabrir_e_prontidao(self):
        uid, st = self.make()
        sc = service.create(st, name="Com previsões")
        ref = sc.document["inventory_ref"]
        self.assertEqual(S.readiness(sc.document, S.findings(sc.document), None)["stages"]["previsoes"][:2],
                         ("warn", "Incompletas"))
        dem, cli = _demand_cand(ref), _climate_cand(ref)
        doc, blobs = self.with_forecasts(st, sc, dem, cli)
        n0 = self.blob_count(st)
        res = service.save(st, doc, 1, new_blobs=blobs)
        self.assertEqual(res.version, 2)
        self.assertEqual(self.blob_count(st), n0 + 3)                           # 2 séries + 1 CSV original
        again = MicrogridRegistry(self.dir).open(uid).get_scenario(sc.scenario_uid)
        self.assertEqual(again.document["forecasts"], doc["forecasts"])
        pd.testing.assert_frame_equal(F.load(again.document["forecasts"]["demand"], st.get_blob), dem.df)
        pd.testing.assert_frame_equal(F.load(again.document["forecasts"]["climate"], st.get_blob), cli.df)
        self.assertEqual(st.get_blob(cli.entry["blob"]), _climate_frame().to_csv(index=False).encode())   # original
        for e in again.document["forecasts"].values():
            self.assertTrue(FS.rederive(e, st.get_blob)[0])
        rd = S.readiness(again.document, S.findings(again.document), None)
        self.assertEqual(rd["stages"]["previsoes"][:2], ("ok", "Definidas"))
        self.assertIsNone(rd["executable"])                                     # decidido pelo preflight (Piso 2C)
        self.assertEqual(rd["stages"]["estrategia"][:2], ("warn", "Não definida"))
        self.assertEqual(rd["stages"]["execucao"][:2], ("warn", "Janela não definida"))

    def test_recuperacao_apos_reinicio_em_novo_processo(self):
        uid, st = self.make()
        sc = service.create(st, name="Persistente")
        ref = sc.document["inventory_ref"]
        dem, cli = _demand_cand(ref), _climate_cand(ref)
        doc, blobs = self.with_forecasts(st, sc, dem, cli)
        service.save(st, doc, 1, new_blobs=blobs)
        code = ("import json,sys,hashlib; from seeds2.microgrid.registry import MicrogridRegistry; "
                "from seeds2.operation import forecasts as F, forecast_sources as FS; "
                "s=MicrogridRegistry(sys.argv[1]).open(sys.argv[2]); c=s.list_scenarios()[0]; out={}\n"
                "for k,e in c.document['forecasts'].items():\n"
                "    df=F.load(e,s.get_blob); out[k]=[hashlib.sha256(F.to_csv_bytes(df)).hexdigest(), FS.rederive(e,s.get_blob)[0], len(df)]\n"
                "print(json.dumps([c.version,out]))")
        res = subprocess.run([sys.executable, "-c", code, str(self.dir), uid], cwd=RAIZ, capture_output=True, text=True,
                             env={**os.environ, "PYTHONPATH": str(RAIZ), "PYTHONDONTWRITEBYTECODE": "1"},
                             check=True, timeout=180)
        ver, got = json.loads(res.stdout.strip().splitlines()[-1])
        self.assertEqual(ver, 2)
        self.assertEqual(got, {"demand": [dem.entry["data"], True, 121], "climate": [cli.entry["data"], True, 37]})

    def test_duplicacao_e_versoes_historicas_imutaveis(self):
        uid, st = self.make()
        sc = service.create(st, name="Original")
        ref = sc.document["inventory_ref"]
        a = _demand_cand(ref, 100.0, seed=1)
        doc, blobs = self.with_forecasts(st, sc, a)
        v2 = service.save(st, doc, 1, new_blobs=blobs)
        b = _demand_cand(ref, 200.0, seed=2)
        doc3, blobs3 = self.with_forecasts(st, v2, b)
        v3 = service.save(st, doc3, 2, new_blobs=blobs3)
        self.assertEqual(v3.version, 3)
        old = st.get_scenario(sc.scenario_uid, version=2)                       # versão antiga recupera SUA curva
        self.assertEqual(old.document["forecasts"]["demand"]["data"], a.entry["data"])
        pd.testing.assert_frame_equal(F.load(old.document["forecasts"]["demand"], st.get_blob), a.df)
        pd.testing.assert_frame_equal(F.load(st.get_scenario(sc.scenario_uid).document["forecasts"]["demand"], st.get_blob), b.df)
        with sqlite3.connect(st.path) as con, self.assertRaises(sqlite3.DatabaseError):
            con.execute("UPDATE scenario_versions SET document = '{}' WHERE version = 2")
        # remover a previsão cria nova versão; a anterior e seus dados continuam
        doc4 = copy.deepcopy(v3.document)
        doc4["forecasts"].pop("demand")
        service.save(st, doc4, 3)
        self.assertEqual(st.get_blob(b.entry["data"]), b.blobs[b.entry["data"]][0])
        # duplicação: cópia independente com as mesmas referências verificáveis e linhagem
        dup = service.duplicate(st, sc.scenario_uid, name="Cópia")
        self.assertEqual(dup.document["forecasts"], doc4["forecasts"])
        st_v3 = st.get_scenario(sc.scenario_uid, version=3)
        d3 = S.duplicate(st_v3.document, 3, name="Cópia da v3")
        res = st.create_scenario(d3, origin="duplicate")
        self.assertEqual(res.document["lineage"]["duplicated_from"]["version"], 3)
        pd.testing.assert_frame_equal(F.load(res.document["forecasts"]["demand"], st.get_blob), b.df)

    def test_conflito_entre_sessoes_preserva_pendente_e_nao_grava_blobs(self):
        uid, st = self.make()
        sc = service.create(st, name="Compartilhado")
        ref = sc.document["inventory_ref"]
        s1, s2 = self.reg.open(uid), MicrogridRegistry(self.dir).open(uid)
        d1, b1 = self.with_forecasts(s1, s1.get_scenario(sc.scenario_uid), _demand_cand(ref, 100.0))
        loser = _demand_cand(ref, 300.0, seed=9)
        d2, b2 = self.with_forecasts(s2, s2.get_scenario(sc.scenario_uid), loser)
        service.save(s1, d1, 1, new_blobs=b1)
        n = self.blob_count(st)
        with self.assertRaises(ScenarioConflictError):
            service.save(s2, d2, 1, new_blobs=b2)
        self.assertEqual(self.blob_count(st), n)                                # perdedor não deixou blobs órfãos
        with self.assertRaises(StoreError):
            st.get_blob(loser.entry["data"])
        self.assertEqual(st.get_scenario(sc.scenario_uid).document["forecasts"]["demand"]["data"], d1["forecasts"]["demand"]["data"])
        # a entrada pendente do perdedor continua íntegra e pode ser regravada conscientemente sobre a versão atual
        cur = s2.get_scenario(sc.scenario_uid)
        d2b = copy.deepcopy(cur.document)
        d2b["forecasts"]["demand"] = d2["forecasts"]["demand"]
        self.assertEqual(service.save(s2, d2b, cur.version, new_blobs=b2).version, 3)
        pd.testing.assert_frame_equal(F.load(d2b["forecasts"]["demand"], st.get_blob), loser.df)

    def test_isolamento_entre_microrredes(self):
        ua, sa = self.make("A")
        ub, sb = self.make("B")
        sca, scb = service.create(sa, name="A1"), service.create(sb, name="B1")
        cand = _demand_cand(sca.document["inventory_ref"])
        doc, blobs = self.with_forecasts(sa, sca, cand)
        service.save(sa, doc, 1, new_blobs=blobs)
        # a referência por SHA-256 não "atravessa" para outra microrrede: sem o blob, B recusa
        docb = copy.deepcopy(scb.document)
        docb["forecasts"]["demand"] = copy.deepcopy(cand.entry)
        with self.assertRaises(StoreError):
            service.save(sb, docb, 1)
        self.assertEqual(sb.get_scenario(scb.scenario_uid).version, 1)
        with self.assertRaises(StoreError):
            sb.get_blob(cand.entry["data"])
        with self.assertRaises(F.ForecastDataError):
            F.load(cand.entry, sb.get_blob)

    def test_blobs_inexistentes_corrompidos_e_atomicidade(self):
        uid, st = self.make()
        sc = service.create(st, name="Integridade")
        cand = _demand_cand(sc.document["inventory_ref"])
        doc, blobs = self.with_forecasts(st, sc, cand)
        n = self.blob_count(st)
        with self.assertRaises(StoreError):                                     # documento sem os dados → nada gravado
            service.save(st, doc, 1)
        self.assertEqual((st.get_scenario(sc.scenario_uid).version, self.blob_count(st)), (1, n))
        h = cand.entry["data"]
        with self.assertRaises(StoreError):                                     # conteúdo ≠ SHA-256 declarado
            service.save(st, doc, 1, new_blobs={h: (b"adulterado", {"name": "x"})})
        self.assertEqual((st.get_scenario(sc.scenario_uid).version, self.blob_count(st)), (1, n))
        service.save(st, doc, 1, new_blobs=blobs)
        with sqlite3.connect(st.path) as con:                                   # corrupção no armazenamento
            con.execute("UPDATE blobs SET content = ? WHERE sha256 = ?", (b"timestamp,demand_kW\n", h))
        with self.assertRaises(F.ForecastDataError):
            F.load(st.get_scenario(sc.scenario_uid).document["forecasts"]["demand"], st.get_blob)
        ok, msg = FS.rederive(cand.entry, st.get_blob)
        self.assertFalse(ok)
        # entradas incompletas ou com erros nunca são gravadas
        bad = copy.deepcopy(st.get_scenario(sc.scenario_uid).document)
        bad["forecasts"]["demand"]["quality"]["erro"] = 1
        with self.assertRaises(S.ScenarioValidationError):
            service.save(st, bad, 2)
        bad = copy.deepcopy(st.get_scenario(sc.scenario_uid).document)
        bad["forecasts"]["resources"] = dict(bad["forecasts"]["demand"], slot="resources")
        with self.assertRaises(S.ScenarioValidationError):                      # slot reservado (sem contrato consumidor)
            service.save(st, bad, 2)
        csv_bad = _csv_cand(_demand_csv()[0], "demand", sc.document["inventory_ref"]).entry
        csv_bad = dict(csv_bad, mapping=None)
        bad = copy.deepcopy(st.get_scenario(sc.scenario_uid).document)
        bad["forecasts"]["demand"] = csv_bad
        with self.assertRaises(S.ScenarioValidationError):                      # CSV sem mapeamento não é reproduzível
            service.save(st, bad, 2)

    def test_backup_zip_continua_sem_cenarios_nem_previsoes(self):
        uid, st = self.make()
        sc = service.create(st, name="Fora do ZIP")
        cand = _climate_cand(sc.document["inventory_ref"])
        doc, blobs = self.with_forecasts(st, sc, cand)
        service.save(st, doc, 1, new_blobs=blobs)
        with zipfile.ZipFile(io.BytesIO(st.export_backup())) as zf:
            names = zf.namelist()
            manifest = json.loads(zf.read("manifest.json"))
        self.assertFalse(set(cand.blobs) & set(manifest["blobs"]))               # C-01: formato do backup inalterado
        self.assertFalse(any(h in n for n in names for h in cand.blobs))


class CompatibilidadeTest(_Base):
    def test_inicializacao_inalterada_com_previsoes(self):
        uid, st = self.make()
        sc = service.create(st, name="Init + previsões")
        doc = copy.deepcopy(sc.document)
        bats = [e for e, r in doc["inventory_ref"]["equipment"].items() if r["kind"] == "battery"]
        for e in bats:
            doc["initialization"]["equipment"][e]["soc0_pct"] = 10.0             # aviso (não bloqueio) do Piso 2A
        before = S.findings(doc)
        cand = _demand_cand(doc["inventory_ref"])
        doc["forecasts"]["demand"] = cand.entry
        self.assertEqual(S.findings(doc), before)
        res = service.save(st, doc, 1, new_blobs=cand.blobs)
        self.assertEqual(res.document["initialization"], doc["initialization"])
        self.assertEqual(S.readiness(res.document, S.findings(res.document), None)["stages"]["inicializacao"],
                         S.readiness(sc.document | {"initialization": doc["initialization"]},
                                     before, None)["stages"]["inicializacao"])

    def test_ems_e_configuracao_fisica_inalterados(self):
        """Previsões gravadas no cenário não alteram a configuração física, a especificação V1.6 nem o despacho."""
        import orchestrator_runtime as RT

        uid, st = self.make(cfg=v16_equivalent_config("EMS"))
        saved0 = st.load()
        plan0 = A.build_plan(saved0.config, revision=saved0.revision, fingerprint=saved0.fingerprint)
        sc = service.create(st, name="Previsões não executadas")
        ref = sc.document["inventory_ref"]
        doc, blobs = self.with_forecasts(st, sc, _demand_cand(ref, 999.0), FS.reference_candidate(
            "clima_sintetico_v16", {"t0": "2026-09-01 00:00", "duration_min": 120}, inventory_ref=ref))
        service.save(st, doc, 1, new_blobs=blobs)
        saved1 = st.load()
        self.assertEqual((saved1.revision, saved1.fingerprint, saved1.config), (saved0.revision, saved0.fingerprint, saved0.config))
        plan1 = A.build_plan(saved1.config, revision=saved1.revision, fingerprint=saved1.fingerprint)
        self.assertEqual((plan1.spec, plan1.spec_fingerprint, plan1.load_descriptor, plan1.climate_descriptor),
                         (plan0.spec, plan0.spec_fingerprint, plan0.load_descriptor, plan0.climate_descriptor))
        carga = A.build_load(plan1.load_descriptor, st.get_blob)
        opt = RT.default_optimizer_config()
        with tempfile.TemporaryDirectory() as pkg, tempfile.TemporaryDirectory() as pkg2:
            p1, _ = RT.build_exchange_package(carga, plan1.spec, opt, destino=Path(pkg))
            r1, _ = RT.run_optimizer(p1, opt)
            p2, _ = RT.build_exchange_package(carga, RT.default_model_spec(), opt, destino=Path(pkg2))
            r2, _ = RT.run_optimizer(p2, opt)
        np.testing.assert_array_equal(r1["P_kW"], r2["P_kW"])
        self.assertEqual(r1["rel"]["custo_total_rs"], r2["rel"]["custo_total_rs"])


if __name__ == "__main__":
    unittest.main()
