"""Piso 2C — Execução EMS e persistência científica (domínio, sem interface; ver ``test_seeds2_piso2c_app.py``).

Cobre: preflight compatível/incompatível (SOC, PEMFC, térmica, disponibilidade, equipamentos não representáveis),
estratégia EMS, janela da missão (fusos, UTC, horário de verão, cobertura, interpolação registrada sem extrapolação,
direção angular), execução REAL de missões compatíveis e comparação numérica com o EMS V1.6, gravação completa,
imutabilidade, reabertura em novo processo sem recalcular, idempotência (sem execução duplicada), falhas do solver,
incompatibilidade descoberta no contrato do motor, interrupção do processo e recuperação, isolamento entre
microrredes, migração v3 → v4 e preservação dos Pisos 1/2A/2B.

Dados: inventário fictício equivalente à configuração padrão V1.6 (``seeds2_fixtures``) e perfis de referência da
própria V1.6 (walk-forward / clima sintético) — nenhum dado de instalação real.
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
from unittest import mock

import numpy as np
import pandas as pd

import orchestrator_runtime as RT
from ems_integration import ponte
from seeds2.microgrid import config as C
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.microgrid.store import (LATEST_DB_VERSION, RunBusyError, ScenarioNotFound, StoreError)
from seeds2.operation import forecast_sources as FS
from seeds2.operation import mission as M
from seeds2.operation import preflight as P
from seeds2.operation import runner
from seeds2.operation import scenarios as S
from seeds2.operation import service
from seeds2.operation import strategy as SG
from seeds2_fixtures import v16_equivalent_config

RAIZ = Path(__file__).resolve().parents[1]
TZ = "America/Sao_Paulo"
DUR = 30


# =========================================================================== construção de cenários executáveis
def mission_load(duration: int = DUR) -> ponte.PerfilCarga:
    return ponte.recortar(ponte.carga_walkforward("Ideal", "Normal", 12), 0, duration)


def demand_candidate(ref: dict, carga: ponte.PerfilCarga, tz: str | None = TZ, step_min: int = 1):
    ts = carga.t0 + pd.to_timedelta(carga.t_min, unit="min")
    tbl = pd.DataFrame({"timestamp": ts, "demand_kW": carga.P_kW}).iloc[::step_min].reset_index(drop=True)
    c = FS.manual_candidate(tbl, "demand", timezone=tz, inventory_ref=ref, provenance="referencia", construction={})
    assert c.ok, [f.message for f in c.analysis.findings if f.level == "erro"]
    return c


def climate_candidate(ref: dict, frame: pd.DataFrame, tz: str | None = TZ):
    c = FS.manual_candidate(frame, "climate", timezone=tz, inventory_ref=ref, provenance="sintetico", construction={})
    assert c.ok, [f.message for f in c.analysis.findings if f.level == "erro"]
    return c


def v16_climate(carga: ponte.PerfilCarga, *, shift_h: float = 0.0, extra: bool = False) -> pd.DataFrame:
    """Clima sintético da V1.6 nos instantes da carga (relógio deslocado de ``shift_h`` horas)."""
    c = RT.synthetic_climate(carga)
    df = pd.DataFrame({"timestamp": pd.to_datetime(c["timestamp"]) + pd.Timedelta(hours=shift_h),
                       "ghi_W_m2": c["GHI_W_m2"], "temperature_C": c["temperature_C"]})
    if extra:
        df["wind_speed_m_s"] = c["wind_speed_mps"]
        df["wind_direction_deg"] = c["wind_direction_deg"]
    return df


def set_states(doc: dict, *, soc=60.0, fc_state="em_operacao", fc_power=0.0, thermal=None) -> None:
    for eid, r in doc["inventory_ref"]["equipment"].items():
        st = doc["initialization"]["equipment"].setdefault(eid, {"availability": "disponivel", "note": ""})
        if r["kind"] == "battery":
            st["soc0_pct"] = soc if not isinstance(soc, dict) else soc[r["name"]]
        elif r["kind"] == "pemfc":
            st.update(state=fc_state, units_on=(r["quantity"] if fc_state != "desligada" else 0),
                      power_kW=(fc_power * r["quantity"] / 4.0 if fc_state != "desligada" else 0.0))
        elif r["kind"] == "thermal":
            st.update(**(thermal or {"state": "desligada", "power_kW": 0.0}))


def ready(store, *, name="Missão", duration=DUR, soc=60.0, fc_state="em_operacao", fc_power=0.0, thermal=None,
          demand_tz=TZ, climate_tz=TZ, mission_tz=TZ, climate_shift_h=0.0, strategy=None, clock=None, climate=True):
    """Cria e GRAVA um cenário completo (estados, previsões, estratégia, janela). Devolve a versão gravada."""
    sc = service.create(store, name=name)
    doc = copy.deepcopy(sc.document)
    set_states(doc, soc=soc, fc_state=fc_state, fc_power=fc_power, thermal=thermal)
    ref = doc["inventory_ref"]
    carga = mission_load(duration)
    dem = demand_candidate(ref, carga, demand_tz)
    blobs = dict(dem.blobs)
    doc["forecasts"] = {"demand": dem.entry}
    if climate:
        cli = climate_candidate(ref, v16_climate(carga, shift_h=climate_shift_h), climate_tz)
        doc["forecasts"]["climate"] = cli.entry
        blobs.update(cli.blobs)
    doc["ems_strategy"] = strategy or SG.default_strategy()
    doc["mission"] = SG.default_mission(carga.t0.strftime("%Y-%m-%dT%H:%M:00"), mission_tz, duration)
    doc["mission"]["undeclared_clock"] = clock
    return service.save(store, doc, sc.version, new_blobs=blobs)


def edit(store, stored, fn, note="edição"):
    doc = copy.deepcopy(stored.document)
    fn(doc)
    return service.save(store, doc, stored.version, note=note)


def levels(pf: P.Preflight, level: str) -> list[str]:
    return [i.message for i in pf.items if i.level == level]


def v16_direct(pf: P.Preflight, carga: ponte.PerfilCarga):
    """A MESMA rodada pelo console V1.6 (clima 'Sintético diário' = os mesmos valores das previsões)."""
    spec = copy.deepcopy(pf.plan.spec)
    spec["climate"]["source"] = "Sintético diário"
    pk, _ = RT.build_exchange_package(carga, spec, pf.optimizer_cfg)
    r, _ = RT.run_optimizer(pk, pf.optimizer_cfg)
    return r


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.reg = MicrogridRegistry(self.dir)

    def tearDown(self):
        self._tmp.cleanup()

    def make(self, name="Microrrede 2C", cfg=None) -> tuple[str, object]:
        cfg = cfg or v16_equivalent_config(name)
        self.reg.create(cfg)
        uid = cfg["installation"]["uid"]
        return uid, self.reg.open(uid)

    def eq(self, store, name):
        return next(e for e in store.load().config["equipment"] if e["name"] == name)

    def add_equipment(self, store, eq):
        cfg = copy.deepcopy(store.load().config)
        C.add_equipment(cfg, eq)
        store.save(cfg, store.load().revision)


def thermal_eq(pmin=20.0, ramp=40.0):
    return C.new_equipment("thermal", "Gerador diesel", tag="TH-01", params={
        "dynamic": "local_generator", "pmax_kW": 80.0, "pmin_kW": pmin, "cvu_rs_MWh": 1100.0, "ramp_kW_min": ramp,
        "startup_cost_rs": 50.0})


# =========================================================================== estratégia
class EstrategiaTest(unittest.TestCase):
    def test_padrao_e_o_do_console_v16_e_faixas_validadas(self):
        s = SG.default_strategy()
        self.assertEqual(SG.strategy_errors(s), [])
        self.assertEqual(SG.optimizer_config(s), RT.default_optimizer_config())    # formato e valores do V1.6
        self.assertEqual(set(SG.ALGORITHMS.values()), set(RT.ALGORITMOS))           # só algoritmos existentes
        self.assertEqual({SG.ALGORITHMS[k]: k for k in SG.ALGORITHMS}, RT.ALGORITMOS)
        for path, bad in (("algorithm", 7), ("N", 0), ("N", 16), ("seed", -1), ("soc_alvo_tol", 0.9),
                          ("objective", "multiobjetivo"), ("N", 3.5)):
            b = copy.deepcopy(s)
            b[path] = bad
            self.assertTrue(SG.strategy_errors(b), path)
        b = copy.deepcopy(s)
        b["econ"]["pen_deficit_rs_kWh"] = 1e9
        self.assertTrue(SG.strategy_errors(b))
        b = copy.deepcopy(s)
        b["pareto"] = True                                                         # nenhum campo fictício
        self.assertTrue(SG.strategy_errors(b))

    def test_estrategia_e_janela_gravadas_na_versao_do_cenario(self):
        reg = MicrogridRegistry(tempfile.mkdtemp())
        cfg = v16_equivalent_config()
        reg.create(cfg)
        st = reg.open(cfg["installation"]["uid"])
        sc = service.create(st, name="Estratégia")
        self.assertIsNone(sc.document["ems_strategy"])
        self.assertIsNone(sc.document["mission"])
        s = SG.default_strategy()
        s.update(algorithm=0, N=5, seed=42)
        v2 = edit(st, sc, lambda d: d.update(ems_strategy=s, mission=SG.default_mission("2026-09-05T12:00:00", TZ, 30)))
        self.assertEqual(st.get_scenario(sc.scenario_uid, 2).document["ems_strategy"], s)
        self.assertIsNone(st.get_scenario(sc.scenario_uid, 1).document["ems_strategy"])     # v1 imutável
        rd = S.readiness(v2.document, S.findings(v2.document), None)
        self.assertEqual(rd["stages"]["estrategia"][:2], ("ok", "Definida"))
        self.assertEqual(rd["stages"]["execucao"][:2], ("info", "Janela definida"))
        bad = copy.deepcopy(v2.document)
        bad["ems_strategy"]["algorithm"] = 9
        with self.assertRaises(S.ScenarioValidationError):
            service.save(st, bad, v2.version)
        bad = copy.deepcopy(v2.document)
        bad["mission"]["start"] = "2026-09-05T12:00:30"                       # fora da grade de 1 min
        with self.assertRaises(S.ScenarioValidationError):
            service.save(st, bad, v2.version)

    def test_documento_antigo_sem_bloco_mission_continua_valido(self):
        reg = MicrogridRegistry(tempfile.mkdtemp())
        cfg = v16_equivalent_config()
        reg.create(cfg)
        st = reg.open(cfg["installation"]["uid"])
        doc = copy.deepcopy(service.create(st, name="Antigo").document)
        doc.pop("mission")                                                     # cenário gravado no Piso 2A/2B
        self.assertEqual(S.structural_errors(doc), [])
        self.assertEqual(S.readiness(doc, S.findings(doc), None)["stages"]["execucao"][:2], ("warn", "Janela não definida"))


# =========================================================================== preflight
class PreflightTest(_Base):
    def test_cenario_compativel_relata_o_que_chega_ao_motor(self):
        _, st = self.make()
        sc = ready(st)
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(pf.ok, levels(pf, P.ERROR))
        spec = pf.plan.spec
        self.assertEqual((spec["fc"]["N_fc"], spec["battery"]["Np"], spec["battery"]["soc0"], spec["solar"]["n_parallel"]),
                         (4, 132, 0.6, 10))
        self.assertEqual(spec["climate"]["source"], "CSV climático")
        ei = pf.engine_inputs()
        self.assertEqual(ei["optimizer_cfg"], RT.default_optimizer_config())
        self.assertEqual((ei["grid"]["step_s"], ei["grid"]["n_steps"]), (60, DUR + 1))
        self.assertEqual(pf.declared["fc"], {"equipment": pf.declared["fc"]["equipment"], "units_on": 4, "N_fc": 4,
                                             "power_kW": 0.0})
        self.assertTrue(any("exatamente o estado inicial do EMS V1.6" in m for m in levels(pf, P.OK)))
        self.assertEqual(pf.excluded, [])
        rep = pf.report()
        self.assertTrue(rep["ok"])
        json.dumps(rep)                                                         # relatório serializável

    def test_soc_fora_da_recomendacao_salva_mas_fora_dos_limites_efetivos_bloqueia(self):
        _, st = self.make()
        sc = ready(st, soc=15.0)                                                # gravar é PERMITIDO (aviso)
        fs = S.findings(sc.document)
        self.assertTrue(any(f.level == "aviso" for f in fs))
        self.assertFalse(any(f.level == "erro" for f in fs))
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertFalse(pf.ok)
        errs = levels(pf, P.ERROR)
        self.assertTrue(any("restrição EFETIVA" in e and "15 %" in e for e in errs), errs)
        with self.assertRaises(runner.PreflightError):
            runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual(st.list_runs(), [])                                    # nada iniciado
        # dentro dos limites efetivos, porém perto do extremo: aviso, não bloqueio
        sc2 = ready(st, soc=88.0, name="SOC alto permitido")
        self.assertTrue(runner.prepare(st, sc2.scenario_uid, sc2.version).ok)

    def test_bancos_com_soc_diferentes_nao_sao_representaveis(self):
        _, st = self.make()
        sc = ready(st, soc={"Banco de baterias 1": 60.0, "Banco de baterias 2": 50.0})
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertFalse(pf.ok)
        self.assertTrue(any("UM único SOC inicial" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))

    def test_pemfc_estados_nao_representaveis(self):
        _, st = self.make()
        for state in ("desligada", "em_partida"):
            sc = ready(st, fc_state=state, fc_power=0.0, name=f"PEMFC {state}")
            pf = runner.prepare(st, sc.scenario_uid, sc.version)
            self.assertFalse(pf.ok, state)
            self.assertTrue(any("n_ini = N_fc" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))
        sc = ready(st, name="Parcial")
        bloco = next(e for e, r in sc.document["inventory_ref"]["equipment"].items() if r["name"] == "Bloco PEMFC A")
        sc = edit(st, sc, lambda d: d["initialization"]["equipment"][bloco].update(units_on=2))
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(any("2 de 3 unidade(s)" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))
        sc = ready(st, fc_power=100.0, name="Potência inicial")                 # > 0: verificação condicionada
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(pf.ok)
        self.assertEqual(len(levels(pf, P.CHECK)), 1)
        self.assertIn({"kind": "ramp", "source": "fc", "p0_kW": 100.0}, pf.checks)

    def test_termica_estados_e_pmin(self):
        _, st = self.make()
        self.add_equipment(st, thermal_eq(pmin=20.0))
        sc = ready(st, thermal={"state": "desligada", "power_kW": 0.0}, name="Térmica desligada, Pmín>0")
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(any("deriva n_ini = 1" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))
        sc = ready(st, thermal={"state": "em_partida", "power_kW": 0.0}, name="Térmica em partida")
        self.assertFalse(runner.prepare(st, sc.scenario_uid, sc.version).ok)
        sc = ready(st, thermal={"state": "em_operacao", "power_kW": 50.0}, name="Térmica em operação")
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(pf.ok, levels(pf, P.ERROR))
        self.assertIn({"kind": "ramp", "source": "termica", "p0_kW": 50.0}, pf.checks)
        # Pmín = 0 → o motor inicia desligada: "desligada" representável, "em operação" não
        _, st2 = self.make("Térmica Pmín 0")
        self.add_equipment(st2, thermal_eq(pmin=0.0))
        sc = ready(st2, thermal={"state": "desligada", "power_kW": 0.0})
        self.assertTrue(runner.prepare(st2, sc.scenario_uid, sc.version).ok)
        sc = ready(st2, thermal={"state": "em_operacao", "power_kW": 30.0}, name="Op")
        pf = runner.prepare(st2, sc.scenario_uid, sc.version)
        self.assertTrue(any("deriva n_ini = 0" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))

    def test_disponibilidade_exclui_somente_da_rodada(self):
        _, st = self.make()
        sc = ready(st)
        before = st.load()
        bat = [e for e, r in sc.document["inventory_ref"]["equipment"].items() if r["kind"] == "battery"]
        fc_b = next(e for e, r in sc.document["inventory_ref"]["equipment"].items() if r["name"] == "Bloco PEMFC B")
        pvs = [e for e, r in sc.document["inventory_ref"]["equipment"].items() if r["kind"] == "pv"]

        def unavailable(d):
            for e in bat + pvs:
                d["initialization"]["equipment"][e]["availability"] = "indisponivel"
            d["initialization"]["equipment"][fc_b].update(availability="indisponivel", state="desligada", units_on=0,
                                                          power_kW=0.0)
        sc2 = edit(st, sc, unavailable)
        pf = runner.prepare(st, sc2.scenario_uid, sc2.version)
        self.assertTrue(pf.ok, levels(pf, P.ERROR))
        spec = pf.plan.spec
        self.assertFalse(spec["battery"]["active"])
        self.assertFalse(spec["solar"]["active"])                              # clima deixa de ser exigido
        self.assertEqual(spec["fc"]["N_fc"], 3)                                 # só o bloco A (agregação exata)
        self.assertEqual(sorted(e["id"] for e in pf.excluded), sorted(bat + pvs + [fc_b]))
        self.assertFalse([v for v in pf.window.resampling.values() if v["slot"] == "climate"])
        after = st.load()
        self.assertEqual((after.revision, after.fingerprint), (before.revision, before.fingerprint))   # inventário intacto
        # nenhuma fonte despachável disponível → bloqueio explícito
        fc_a = next(e for e, r in sc.document["inventory_ref"]["equipment"].items() if r["name"] == "Bloco PEMFC A")
        sc3 = edit(st, sc2, lambda d: d["initialization"]["equipment"][fc_a].update(
            availability="indisponivel", state="desligada", units_on=0, power_kW=0.0))
        pf = runner.prepare(st, sc3.scenario_uid, sc3.version)
        self.assertTrue(any("Nenhuma fonte despachável" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))

    def test_equipamento_nao_representavel_nunca_omitido_em_silencio(self):
        _, st = self.make()
        cfg = copy.deepcopy(st.load().config)
        plant = next(e for e in cfg["equipment"] if e["name"] == "Arranjo FV 1")
        plant["arrays"].append(C.new_array("Declarado", mode="declarado", declared_kWp=3.0))
        st.save(cfg, st.load().revision)
        sc = ready(st)
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertFalse(pf.ok)
        self.assertTrue(any("não pode ser omitido" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))
        # declará-lo indisponível no cenário é uma decisão EXPLÍCITA (usina inteira excluída da rodada)
        sc2 = edit(st, sc, lambda d: d["initialization"]["equipment"][plant["id"]].update(availability="indisponivel"))
        pf = runner.prepare(st, sc2.scenario_uid, sc2.version)
        self.assertTrue(pf.ok, levels(pf, P.ERROR))
        self.assertIn(plant["id"], [e["id"] for e in pf.excluded])

    def test_estrategia_ausente_e_inventario_alterado(self):
        _, st = self.make()
        sc = ready(st)
        sc = edit(st, sc, lambda d: d.update(ems_strategy=None))
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(any("Estratégia EMS não definida" in e for e in levels(pf, P.ERROR)))
        sc = ready(st, name="Deriva")
        cfg = copy.deepcopy(st.load().config)
        cfg["equipment"][0]["arrays"][0]["soiling_pct"] = 3.0
        st.save(cfg, st.load().revision)
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(pf.ok)
        self.assertTrue(any("usa a revisão 1" in w for w in levels(pf, P.WARNING)), levels(pf, P.WARNING))
        self.assertEqual(pf.config_revision, 1)                                 # a revisão DO CENÁRIO, não a atual


# =========================================================================== tempo
class TempoTest(_Base):
    def test_fusos_diferentes_convertidos_para_utc(self):
        _, st = self.make()
        # clima em UTC: os MESMOS instantes físicos aparecem 3 h adiante no relógio (São Paulo = UTC−3, sem DST em 2026)
        sc = ready(st, climate_tz="UTC", climate_shift_h=3.0)
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(pf.ok, levels(pf, P.ERROR))
        carga = mission_load()
        ref = v16_climate(carga)
        np.testing.assert_allclose(pf.window.climate["ghi_W_m2"], ref["ghi_W_m2"].to_numpy(), rtol=0, atol=0)
        self.assertTrue(any("convertidas para UTC" in m for m in levels(pf, P.INFO)))
        self.assertEqual(str(pf.window.start_utc), "2026-09-05 15:00:00")
        # comparação ingênua de relógios (sem conversão) estaria 3 h deslocada → fora da cobertura do clima
        sc2 = ready(st, climate_tz=TZ, climate_shift_h=3.0, name="Mesmo fuso, deslocado")
        pf2 = runner.prepare(st, sc2.scenario_uid, sc2.version)
        self.assertTrue(any("sai da cobertura" in e for e in levels(pf2, P.ERROR)), levels(pf2, P.ERROR))

    def test_fuso_nao_declarado_exige_declaracao_explicita(self):
        _, st = self.make()
        sc = ready(st, demand_tz=None, climate_tz=None, mission_tz=None)
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(any("MESMO relógio" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))
        sc = ready(st, demand_tz=None, climate_tz=None, mission_tz=None, clock=SG.UNDECLARED_CLOCK, name="Declarado")
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(pf.ok, levels(pf, P.ERROR))
        self.assertTrue(any("declaração explícita" in w for w in levels(pf, P.WARNING)))
        sc = ready(st, demand_tz=TZ, climate_tz=None, mission_tz=TZ, name="Misto")
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(any("sem fuso declarado" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))
        sc = ready(st, demand_tz=TZ, climate_tz=TZ, mission_tz=None, name="Missão sem fuso")
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(any("informe o fuso da missão" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))

    def test_sem_cobertura_nunca_extrapola(self):
        _, st = self.make()
        sc = ready(st)
        sc = edit(st, sc, lambda d: d["mission"].update(duration_min=DUR + 5))
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(any("sai da cobertura" in e and "Nada é extrapolado" in e for e in levels(pf, P.ERROR)))
        sc = edit(st, sc, lambda d: d["mission"].update(duration_min=DUR, start="2026-09-05T11:59:00"))
        self.assertFalse(runner.prepare(st, sc.scenario_uid, sc.version).ok)

    def test_interpolacao_registrada_sem_extrapolacao_e_angular(self):
        t = np.array([0.0, 600.0, 1200.0])
        v, info = M.resample(t, np.array([0.0, 10.0, 40.0]), np.arange(0, 1201, 60.0))
        np.testing.assert_allclose(v[:11], np.arange(11.0))                   # linear entre amostras
        self.assertEqual((info["exact"], info["interpolated"]), (3, 18))
        ang, _ = M.resample(t, np.array([350.0, 10.0, 10.0]), np.array([300.0]), angular=True)
        self.assertAlmostEqual(float(ang[0]), 0.0, places=9)                  # pelo menor arco (não 180°)
        gap_t = np.array([0.0, 60.0, 120.0, 600.0, 660.0])
        v, info = M.resample(gap_t, np.ones(5), np.arange(0, 661, 60.0))
        self.assertTrue(np.isnan(v[3:10]).all())                               # dentro da lacuna: AUSENTE, nunca zero
        self.assertEqual(info["missing"], 7)
        v, _ = M.resample(t, np.array([1.0, np.nan, 3.0]), np.array([300.0, 600.0, 900.0]))
        self.assertTrue(np.isnan(v).all())                                     # vizinho ausente

    def test_clima_de_10_min_interpolado_e_registrado_na_rodada(self):
        _, st = self.make()
        sc = service.create(st, name="10 min")
        doc = copy.deepcopy(sc.document)
        set_states(doc)
        carga = mission_load()
        dem = demand_candidate(doc["inventory_ref"], carga)
        clim = v16_climate(carga).iloc[::10].reset_index(drop=True)            # passo de 10 min
        cli = climate_candidate(doc["inventory_ref"], clim)
        doc["forecasts"] = {"demand": dem.entry, "climate": cli.entry}
        doc["ems_strategy"] = SG.default_strategy()
        doc["mission"] = SG.default_mission("2026-09-05T12:00:00", TZ, DUR)
        sc = service.save(st, doc, sc.version, new_blobs={**dem.blobs, **cli.blobs})
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        self.assertTrue(pf.ok, levels(pf, P.ERROR))
        r = pf.window.resampling["ghi_W_m2"]
        self.assertEqual((r["exact"], r["interpolated"], r["original_step_s"]), (4, 27, 600.0))
        self.assertIn("interpolação linear em 27 de 31 instantes, sem extrapolação", r["method"])
        self.assertIn("identidade", pf.window.resampling["demand_kW"]["method"])
        g = pf.window.climate["ghi_W_m2"]
        self.assertAlmostEqual(g[5], (clim["ghi_W_m2"][0] + clim["ghi_W_m2"][1]) / 2, places=9)
        # gravação original intacta (a grade é produto derivado)
        stored = st.get_scenario(sc.scenario_uid, sc.version).document["forecasts"]["climate"]
        self.assertEqual(stored["n_points"], 4)

    def test_horario_de_verao_ambiguo_perto_da_janela_recusado(self):
        ts = pd.Series(pd.date_range("2026-10-25 00:00", "2026-10-25 03:00", freq="15min"))
        t, bad = M.wall_to_utc(ts, "Europe/Lisbon")                            # 01:00–01:59 ocorre duas vezes
        self.assertTrue(bad.any())
        self.assertTrue(np.isnan(t[bad]).all())
        _, bad = M.wall_to_utc(pd.Series(pd.to_datetime(["2026-03-29 01:30"])), "Europe/Lisbon")
        self.assertTrue(bad.all())                                             # inexistente (adiantamento)
        self.assertFalse(M.wall_to_utc(ts, "UTC-03:00")[1].any())             # deslocamento fixo: nunca ambíguo


# =========================================================================== execução real e persistência
class ExecucaoTest(_Base):
    def test_execucao_real_igual_ao_ems_v16_e_gravacao_completa(self):
        _, st = self.make()
        sc = ready(st)
        run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual(run.state, "concluida", run.error)
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        r = v16_direct(pf, mission_load())
        s = run.summary
        self.assertEqual(s["custo_total_rs"], float(r["rel"]["custo_total_rs"]))     # mesmo custo
        out = runner.load_csv(st, run.run_uid, "saidas/despacho_ems.csv")
        for j, nome in enumerate(r["nomes"]):
            np.testing.assert_allclose(out[f"P_{nome}_kW"].to_numpy(), r["P_kW"][:, j], rtol=0, atol=1e-9)
        np.testing.assert_allclose(out["SOC_bateria"].to_numpy(), r["SOC"][:, r["nomes"].index("bateria")], rtol=0, atol=1e-12)
        np.testing.assert_allclose(out["P_carga_kW"].to_numpy(), mission_load().P_kW, rtol=0, atol=0)
        # séries do V1.6 (series_dataframe) todas preservadas + extras
        v16_cols = set(RT.series_dataframe(r).columns) - {"timestamp"}
        self.assertTrue(v16_cols <= set(out.columns), v16_cols - set(out.columns))
        for col in ("timestamp_utc", "timestamp_local", "P_renovavel_disponivel_kW", "custo_partida_rs", "Pmax_unid_fc_kW"):
            self.assertIn(col, out.columns)
        self.assertEqual(out["timestamp_utc"].iloc[0], "2026-09-05T15:00:00Z")
        self.assertEqual(out["timestamp_local"].iloc[0], "2026-09-05T12:00:00")
        inp = runner.load_csv(st, run.run_uid, "entradas/missao.csv")
        self.assertEqual(len(inp), DUR + 1)
        self.assertEqual(set(run.data), {"entradas/missao.csv", "saidas/despacho_ems.csv", "saidas/relatorio_ems.json",
                                         "pacote_troca.zip", "modelos/fc_characterization.csv",
                                         "modelos/battery_characterization.csv", "modelos/climate.csv", "modelos/solar.csv"})
        names = zipfile.ZipFile(io.BytesIO(st.run_data(run.run_uid, "pacote_troca.zip"))).namelist()
        self.assertEqual(sorted(names), ["bateria.csv", "carga.csv", "ems_config.json", "fc.csv", "pv.csv"])
        # indicadores = séries gravadas
        self.assertAlmostEqual(s["energia_demanda_kWh"], out["P_carga_kW"].sum() / 60.0, places=9)
        self.assertAlmostEqual(s["energia_nao_atendida_kWh"], out["deficit_kW"].sum() / 60.0, places=9)
        self.assertAlmostEqual(s["energia_atendida_kWh"], s["energia_demanda_kWh"] - s["energia_nao_atendida_kWh"], places=9)
        self.assertAlmostEqual(s["h2_kg"], out["h2_kg"].sum(), places=9)
        self.assertAlmostEqual(s["custo_total_rs"], out["custo_rs"].sum(), places=6)
        # procedência
        m = run.manifest
        self.assertEqual((m["reference"]["scenario_version"], m["reference"]["config_revision"]), (sc.version, 1))
        self.assertEqual(m["reference"]["microgrid_incarnation"], st.incarnation)
        self.assertEqual(m["strategy"], sc.document["ems_strategy"])
        self.assertEqual(m["forecasts"]["demand"]["data"], sc.document["forecasts"]["demand"]["data"])
        self.assertEqual(len(m["software"]["science"]["sha256"]), 64)
        eff = run.outcome["engine_check"]["effective_initial_state"]
        self.assertEqual((eff["fc"]["n_ini"], eff["bateria"]["SOC_ini"], eff["fc"]["P_prev_kW"]), (4, 0.6, 0.0))
        self.assertTrue(run.outcome["engine_check"]["ok"])

    def test_pemfc_potencia_inicial_rampa_comprovada_ou_execucao_recusada(self):
        _, st = self.make()
        ok = ready(st, fc_power=100.0, name="P0 = 100 kW")       # n_prev heurístico = 2 ≠ {3, 4}: rampa não se aplica
        run = runner.submit(st, ok.scenario_uid, ok.version, runner.new_request_id(), background=False)
        self.assertEqual(run.state, "concluida", run.error)
        self.assertTrue(any("comprovadamente inativa" in i["message"] for i in run.outcome["engine_check"]["items"]))
        bad = ready(st, fc_power=195.0, name="P0 = 195 kW")      # rampa de 144 kW/passo < desvio de 155 kW
        with mock.patch("orchestrator_runtime.run_optimizer", side_effect=AssertionError("otimizador chamado")):
            run = runner.submit(st, bad.scenario_uid, bad.version, runner.new_request_id(), background=False)
        self.assertEqual(run.state, "falhou")
        self.assertEqual(run.error["kind"], "incompatibilidade")
        self.assertIn("otimizador NÃO foi chamado", run.error["message"])
        self.assertEqual(run.data, {})
        self.assertIsNone(run.summary)

    def test_termica_em_operacao_executa_com_rampa_comprovada(self):
        _, st = self.make()
        self.add_equipment(st, thermal_eq(pmin=20.0, ramp=40.0))
        sc = ready(st, thermal={"state": "em_operacao", "power_kW": 50.0})
        run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual(run.state, "concluida", run.error)
        eff = run.outcome["engine_check"]["effective_initial_state"]["termica"]
        self.assertEqual((eff["n_ini"], eff["ramp_kW_min"]), (1, 40.0))
        sc = ready(st, thermal={"state": "em_operacao", "power_kW": 75.0}, name="Rampa ativa")   # 75−20 = 55 > 40
        run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual((run.state, run.error["kind"]), ("falhou", "incompatibilidade"))

    def test_rodada_concluida_e_imutavel_e_versao_historica_preservada(self):
        _, st = self.make()
        sc = ready(st)
        run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        v2 = edit(st, sc, lambda d: d["ems_strategy"].update(seed=7))           # editar o cenário DEPOIS
        self.assertEqual(st.get_run(run.run_uid).scenario_version, sc.version)
        self.assertEqual(st.get_scenario(sc.scenario_uid, sc.version).document["ems_strategy"]["seed"], 0)
        self.assertEqual(v2.version, sc.version + 1)
        with sqlite3.connect(st.path) as con:
            for sql in ("UPDATE scenario_runs SET summary = '{}'", "UPDATE scenario_runs SET state = 'em_execucao'",
                        "DELETE FROM scenario_runs", "UPDATE scenario_run_data SET content = x'00'",
                        "DELETE FROM scenario_run_data"):
                with self.assertRaises(sqlite3.IntegrityError, msg=sql):
                    con.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("INSERT INTO scenario_run_data VALUES (?, 'x', 'y', 'text/plain', 'identity', 1, x'00')",
                            (run.run_uid,))
        with self.assertRaises(StoreError):
            st.finish_run(run.run_uid, runner.OWNER, outcome={}, summary={}, data={})
        run2 = runner.submit(st, v2.scenario_uid, v2.version, runner.new_request_id(), background=False)
        self.assertEqual([r.run_uid for r in st.list_runs(sc.scenario_uid)], [run2.run_uid, run.run_uid])
        self.assertEqual(run2.manifest["strategy"]["seed"], 7)

    def test_sem_execucao_duplicada_por_reenvio_do_mesmo_pedido(self):
        _, st = self.make()
        sc = ready(st)
        req = runner.new_request_id()
        a = runner.submit(st, sc.scenario_uid, sc.version, req, background=False)
        with mock.patch("orchestrator_runtime.run_optimizer", side_effect=AssertionError("executou de novo")):
            b = runner.submit(st, sc.scenario_uid, sc.version, req, background=False)
        self.assertEqual(a.run_uid, b.run_uid)
        self.assertEqual(len(st.list_runs()), 1)

    def test_uma_rodada_ativa_por_microrrede(self):
        _, st = self.make()
        sc = ready(st)
        pf = runner.prepare(st, sc.scenario_uid, sc.version)
        uid = "a" * 32
        runner._LIVE[uid] = None                                               # dono vivo neste processo
        try:
            st.start_run(run_uid=uid, request_id="pedido-ativo-1", scenario_uid=sc.scenario_uid,
                         scenario_version=sc.version, scenario_fingerprint=sc.fingerprint,
                         manifest=runner.build_manifest(pf, uid, "pedido-ativo-1"), owner=runner.OWNER,
                         is_dead=runner.owner_is_dead)
            with self.assertRaises(RunBusyError):
                runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        finally:
            runner._LIVE.pop(uid, None)
        # dono deste processo sem thread viva → recuperado como interrompida, e a nova rodada pode começar
        self.assertEqual(runner.recover(st), [uid])
        self.assertEqual(st.get_run(uid).state, "interrompida")
        self.assertEqual(runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(),
                                       background=False).state, "concluida")

    def test_falha_do_solver_e_dos_modelos_nao_gravam_resultados(self):
        _, st = self.make()
        sc = ready(st)
        with mock.patch("orchestrator_runtime.run_optimizer", side_effect=RuntimeError("Passo 3: nenhuma configuração")):
            run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual((run.state, run.error["kind"], run.error["type"]), ("falhou", "falha", "RuntimeError"))
        self.assertIn("nenhuma configuração", run.error["message"])
        self.assertEqual((run.data, run.summary), ({}, None))
        with mock.patch("orchestrator_runtime.build_exchange_package", side_effect=ValueError("modelo falhou")):
            run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual((run.state, run.error["message"]), ("falhou", "modelo falhou"))
        with mock.patch.object(type(st), "finish_run", side_effect=StoreError("disco cheio")):
            run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual(run.state, "falhou")                                  # nunca 'concluida' sem os dados
        self.assertEqual(run.data, {})

    def test_execucao_em_segundo_plano_com_progresso_real(self):
        _, st = self.make()
        sc = ready(st)
        seen = []
        orig = st.heartbeat_run

        def spy(run_uid, owner, progress):
            seen.append(dict(progress))
            return orig(run_uid, owner, progress)
        with mock.patch.object(st, "heartbeat_run", side_effect=spy):
            run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=True)
            self.assertTrue(runner.wait(run.run_uid, 300))
        self.assertEqual(st.get_run(run.run_uid).state, "concluida")
        phases = [p["phase"] for p in seen]
        self.assertEqual(phases[:3], ["fila", "modelos", "verificacao"])
        steps = [p for p in seen if p["phase"] == "otimizador" and p.get("k")]
        self.assertEqual((steps[-1]["k"], steps[-1]["n"]), (DUR + 1, DUR + 1))  # progresso real do despacho

    def test_reinicio_reabre_resultados_sem_recalcular_e_interrupcao_recuperada(self):
        uid, st = self.make()
        sc = ready(st)
        run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        code = (
            "import sys, json\n"
            "sys.path.insert(0, 'tests')\n"
            "import orchestrator_runtime as RT\n"
            "def boom(*a, **k): raise SystemExit('otimizador chamado ao reabrir')\n"
            "RT.run_optimizer = boom; RT.build_exchange_package = boom\n"
            "from seeds2.microgrid.registry import MicrogridRegistry\n"
            "from seeds2.operation import runner\n"
            "st = MicrogridRegistry(sys.argv[1]).open(sys.argv[2])\n"
            "r = st.get_run(sys.argv[3])\n"
            "out = runner.load_csv(st, r.run_uid, 'saidas/despacho_ems.csv')\n"
            "print(json.dumps({'state': r.state, 'cost': r.summary['custo_total_rs'], 'n': len(out),\n"
            "                  'p': float(out['P_fc_kW'].sum()), 'data': sorted(r.data)}))\n")
        res = subprocess.run([sys.executable, "-c", code, self.dir, uid, run.run_uid], cwd=RAIZ, capture_output=True,
                             text=True, timeout=180, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(res.returncode, 0, res.stderr)
        got = json.loads(res.stdout.strip().splitlines()[-1])
        out = runner.load_csv(st, run.run_uid, "saidas/despacho_ems.csv")
        self.assertEqual(got, {"state": "concluida", "cost": run.summary["custo_total_rs"], "n": len(out),
                               "p": float(out["P_fc_kW"].sum()), "data": sorted(run.data)})
        # processo encerrado no MEIO do despacho (os._exit) → rodada órfã → 'interrompida' na recuperação
        code = (
            "import sys, os\n"
            "sys.path.insert(0, 'tests')\n"
            "import orchestrator_runtime as RT\n"
            "orig = RT.run_optimizer\n"
            "def crash(pk, opt, progress=None):\n"
            "    def p(k, n):\n"
            "        progress(k, n)\n"
            "        if k == 5: os._exit(17)\n"
            "    return orig(pk, opt, progress=p)\n"
            "RT.run_optimizer = crash\n"
            "from seeds2.microgrid.registry import MicrogridRegistry\n"
            "from seeds2.operation import runner\n"
            "st = MicrogridRegistry(sys.argv[1]).open(sys.argv[2])\n"
            "runner.submit(st, sys.argv[3], int(sys.argv[4]), 'pedido-que-cai-01', background=False)\n")
        res = subprocess.run([sys.executable, "-c", code, self.dir, uid, sc.scenario_uid, str(sc.version)], cwd=RAIZ,
                             capture_output=True, text=True, timeout=180, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(res.returncode, 17, res.stderr)
        orphan = next(r for r in st.list_runs() if r.request_id == "pedido-que-cai-01")
        self.assertEqual(orphan.state, "em_execucao")
        self.assertEqual(orphan.progress.get("phase"), "otimizador")
        self.assertEqual(runner.recover(st), [orphan.run_uid])
        again = st.get_run(orphan.run_uid)
        self.assertEqual((again.state, again.error["kind"], again.data, again.summary), ("interrompida", "interrupcao", {}, None))
        self.assertEqual(runner.recover(st), [])                               # idempotente

    def test_isolamento_entre_microrredes(self):
        ua, a = self.make("A")
        ub, b = self.make("B")
        sa = ready(a)
        run = runner.submit(a, sa.scenario_uid, sa.version, runner.new_request_id(), background=False)
        self.assertEqual(b.list_runs(), [])
        with self.assertRaises(StoreError):
            b.get_run(run.run_uid)
        with self.assertRaises(ScenarioNotFound):
            runner.submit(b, sa.scenario_uid, sa.version, runner.new_request_id(), background=False)
        self.assertEqual(run.manifest["reference"]["microgrid_uid"], ua)
        self.assertEqual(b.count_scenario_runs(), {})
        self.assertEqual(a.count_scenario_runs(), {"concluida": 1})

    def test_migracao_v3_para_v4_preserva_cenarios_e_backup_sem_rodadas(self):
        uid, st = self.make()
        sc = ready(st)
        runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        data = st.export_backup()
        self.assertFalse([n for n in zipfile.ZipFile(io.BytesIO(data)).namelist() if "run" in n.lower()])
        tgt = MicrogridRegistry(tempfile.mkdtemp(dir=self.dir))
        new_uid, _ = tgt.import_new(data)
        self.assertEqual(tgt.open(new_uid).list_runs(), [])                     # ZIP (formato 2) não transporta rodadas
        # banco v3 (Piso 2A/2B) → v4
        _, st3 = self.make("Banco v3")
        sc3 = ready(st3)
        with sqlite3.connect(st3.path) as con:
            for t in ("scenario_run_data_open_only", "scenario_run_data_immutable_u", "scenario_run_data_immutable_d",
                      "scenario_runs_final_u", "scenario_runs_identity_u", "scenario_runs_immutable_d"):
                con.execute(f"DROP TRIGGER {t}")
            con.execute("DROP TABLE scenario_run_data")
            con.execute("DROP TABLE scenario_runs")
            con.execute("PRAGMA user_version = 3")
        re = self.reg.open(sc3.microgrid_uid)
        self.assertEqual(re.db_version(), LATEST_DB_VERSION)
        self.assertTrue(re.path.with_name(re.path.name + ".bak-v3").is_file())
        self.assertEqual(re.get_scenario(sc3.scenario_uid).fingerprint, sc3.fingerprint)
        self.assertEqual(runner.submit(re, sc3.scenario_uid, sc3.version, runner.new_request_id(),
                                       background=False).state, "concluida")

    def test_console_v16_inalterado(self):
        """A Simulação V1.6 com a configuração salva continua com o mesmo despacho e custo de referência."""
        _, st = self.make()
        from seeds2.microgrid import adapter as A
        saved = st.load()
        plan = A.build_plan(saved.config, revision=saved.revision, fingerprint=saved.fingerprint)
        carga = A.build_load(plan.load_descriptor, st.get_blob)
        pk, _ = RT.build_exchange_package(carga, plan.spec, RT.default_optimizer_config())
        r, _ = RT.run_optimizer(pk, RT.default_optimizer_config())
        self.assertAlmostEqual(float(r["rel"]["custo_total_rs"]), 417.684638, places=5)


# =========================================================================== correção de auditoria C-02
def _ids(sc, kind=None, name=None):
    eqs = sc.document["inventory_ref"]["equipment"]
    return [e for e, r in eqs.items() if (kind is None or r["kind"] == kind) and (name is None or r["name"] == name)]


class CorrecaoC02IndisponivelTest(_Base):
    """C-02.1 — equipamento declarado indisponível (excluído do despacho) não exige estado inicial que o motor não usa;
    valores declarados continuam validados; disponível com estado incompleto continua bloqueado."""

    def test_bateria_indisponivel_sem_soc_executa_e_fica_fora_do_pacote(self):
        _, st = self.make()
        sc = ready(st)
        bats = _ids(sc, "battery")

        def bats_off(d):
            for e in bats:
                d["initialization"]["equipment"][e].update(availability="indisponivel", soc0_pct=None)
        sc2 = edit(st, sc, bats_off)
        before_inv = st.load()
        before_doc = st.get_scenario(sc2.scenario_uid, sc2.version)
        pf = runner.prepare(st, sc2.scenario_uid, sc2.version)
        self.assertTrue(pf.ok, levels(pf, P.ERROR))
        infos = levels(pf, P.INFO)
        self.assertEqual(sum("NÃO requerido" in m for m in infos), 2, infos)       # informado por banco
        self.assertFalse(pf.plan.spec["battery"]["active"])
        self.assertEqual(sorted(e["id"] for e in pf.excluded), sorted(bats))
        run = runner.submit(st, sc2.scenario_uid, sc2.version, runner.new_request_id(), background=False)
        self.assertEqual(run.state, "concluida", run.error)
        self.assertEqual(run.outcome["effective_engine"]["nomes"], ["fc"])        # bateria fora do contrato do EMS
        names = zipfile.ZipFile(io.BytesIO(st.run_data(run.run_uid, "pacote_troca.zip"))).namelist()
        self.assertNotIn("bateria.csv", names)
        cfg = json.loads(zipfile.ZipFile(io.BytesIO(st.run_data(run.run_uid, "pacote_troca.zip"))).read("ems_config.json"))
        self.assertEqual(cfg["opcoes_fontes"]["fontes"], ["fc"])
        self.assertNotIn("SOC_bateria", runner.load_csv(st, run.run_uid, "saidas/despacho_ems.csv").columns)
        # inventário físico e versão gravada do cenário intactos
        after_inv = st.load()
        self.assertEqual((after_inv.revision, after_inv.fingerprint), (before_inv.revision, before_inv.fingerprint))
        after_doc = st.get_scenario(sc2.scenario_uid, sc2.version)
        self.assertEqual(after_doc.fingerprint, before_doc.fingerprint)
        self.assertIsNone(after_doc.document["initialization"]["equipment"][bats[0]]["soc0_pct"])
        self.assertTrue(all(e["enabled"] for e in after_inv.config["equipment"]))

    def test_bateria_disponivel_sem_soc_continua_bloqueada(self):
        _, st = self.make()
        sc = ready(st)
        bats = _ids(sc, "battery")
        sc2 = edit(st, sc, lambda d: d["initialization"]["equipment"][bats[0]].update(soc0_pct=None))
        pf = runner.prepare(st, sc2.scenario_uid, sc2.version)
        self.assertFalse(pf.ok)
        self.assertTrue(any("não definido" in e and "SOC inicial" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))
        self.assertFalse(any("NÃO requerido" in m for m in levels(pf, P.INFO)))
        with self.assertRaises(runner.PreflightError):
            runner.submit(st, sc2.scenario_uid, sc2.version, runner.new_request_id(), background=False)

    def test_indisponivel_com_estado_contraditorio_mantem_o_erro(self):
        _, st = self.make()
        sc = ready(st)
        fc_b = _ids(sc, name="Bloco PEMFC B")[0]
        # indisponível e EM OPERAÇÃO: incoerente → o Piso 2A recusa gravar; o preflight também recusa o documento
        doc = copy.deepcopy(sc.document)
        doc["initialization"]["equipment"][fc_b].update(availability="indisponivel", state="em_operacao", units_on=1,
                                                       power_kW=0.0)
        with self.assertRaises(S.ScenarioValidationError):
            service.save(st, doc, sc.version)
        stored = st.save_scenario(doc, sc.version, note="gravação direta (documento incoerente)")   # sem a camada 2A
        pf = runner.prepare(st, stored.scenario_uid, stored.version)
        self.assertFalse(pf.ok)
        self.assertTrue(any("indisponível não pode estar 'em operação'" in e for e in levels(pf, P.ERROR)),
                        levels(pf, P.ERROR))

    def test_pemfc_e_termica_indisponiveis_sem_estado_nao_exigem_estado(self):
        _, st = self.make()
        self.add_equipment(st, thermal_eq(pmin=20.0))
        sc = ready(st, thermal={"state": "em_operacao", "power_kW": 50.0})
        fc_b = _ids(sc, name="Bloco PEMFC B")[0]
        th = _ids(sc, "thermal")[0]

        def off(d):
            d["initialization"]["equipment"][fc_b].update(availability="indisponivel", state=None, units_on=None,
                                                         power_kW=None)
            d["initialization"]["equipment"][th].update(availability="indisponivel", state=None, power_kW=None)
        sc2 = edit(st, sc, off)
        pf = runner.prepare(st, sc2.scenario_uid, sc2.version)
        self.assertTrue(pf.ok, levels(pf, P.ERROR))
        self.assertEqual(sum("NÃO requerido" in m for m in levels(pf, P.INFO)), 2)
        self.assertEqual(pf.plan.spec["fc"]["N_fc"], 3)
        self.assertFalse(pf.plan.spec["thermal"]["active"])
        # a mesma PEMFC DISPONÍVEL sem estado: bloqueio mantido
        sc3 = edit(st, sc2, lambda d: d["initialization"]["equipment"][fc_b].update(availability="disponivel"))
        pf = runner.prepare(st, sc3.scenario_uid, sc3.version)
        self.assertTrue(any("Estado operativo inicial não definido" in e for e in levels(pf, P.ERROR)), levels(pf, P.ERROR))


class CorrecaoC02PotenciaInicialTest(_Base):
    """C-02.2 — potência inicial > 0 precisa ser admissível no envelope caracterizado (estado discreto representado)
    ANTES da verificação de rampa; rampa ilimitada não dispensa os limites físicos."""

    def _fonte(self, **kw):
        from ems_integration.contrato import Fonte
        base = dict(nome="fc", tipo="geracao", n_unid=4, n_ini=4, dn_max=1, P_max_unid_kW=np.full(3, 50.0),
                    P_min_unid_kW=np.full(3, 10.0), ramp_kW_min=np.inf)
        base.update(kw)
        return Fonte(**base)

    def test_admissibilidade_independe_da_rampa(self):
        f = self._fonte()
        self.assertEqual(P.ramp_inactive(f, 30.0, 60.0)[0], True)              # rampa ilimitada…
        ok, detail = P.initial_power_admissible(f, 30.0)                      # …mas 30 < 4 × 10 kW
        self.assertFalse(ok)
        self.assertIn("declarada 30 kW; intervalo efetivo [40, 200] kW", detail)
        self.assertFalse(P.initial_power_admissible(f, 201.0)[0])
        self.assertTrue(P.initial_power_admissible(f, 40.0)[0])
        self.assertTrue(P.initial_power_admissible(f, 200.0)[0])
        off = self._fonte(nome="termica", n_unid=1, n_ini=0, dn_max=np.inf, P_min_unid_kW=np.zeros(3))
        self.assertFalse(P.initial_power_admissible(off, 5.0)[0])              # motor desligado: P0 > 0 inadmissível

    def _run(self, st, sc):
        with mock.patch("orchestrator_runtime.run_optimizer", side_effect=AssertionError("otimizador chamado")):
            return runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)

    def test_fora_do_envelope_com_rampa_finita_recusada_antes_do_otimizador(self):
        _, st = self.make()
        sc = ready(st, fc_power=30.0)                                          # 4 unidades × Pmín 10 kW = 40 kW
        self.assertTrue(runner.prepare(st, sc.scenario_uid, sc.version).ok)   # aceito na fase A (verificação condicionada)
        run = self._run(st, sc)
        self.assertEqual((run.state, run.error["kind"]), ("falhou", "incompatibilidade"))
        msgs = [i["message"] for i in run.outcome["engine_check"]["items"]]
        self.assertTrue(any("FORA do envelope efetivo" in m and "intervalo efetivo [40, 200] kW" in m for m in msgs), msgs)
        self.assertFalse(any("rampa do 1º passo" in m for m in msgs))         # rampa nem avaliada
        self.assertEqual((run.data, run.summary), ({}, None))

    def test_fora_do_envelope_com_rampa_ilimitada_recusada(self):
        _, st = self.make()
        sc = ready(st, fc_power=30.0)
        real = P._engine_sources

        def unlimited(pasta):
            fontes, ts = real(pasta)
            for f in fontes:
                if f.nome == "fc":
                    f.ramp_kW_min = np.inf
            return fontes, ts
        with mock.patch.object(P, "_engine_sources", side_effect=unlimited):
            run = self._run(st, sc)
        self.assertEqual((run.state, run.error["kind"]), ("falhou", "incompatibilidade"))
        eff = run.outcome["engine_check"]["effective_initial_state"]["fc"]
        self.assertIsNone(eff["ramp_kW_min"])                                  # rampa ilimitada de fato
        self.assertTrue(any("FORA do envelope" in i["message"] for i in run.outcome["engine_check"]["items"]))

    def test_dentro_do_envelope_rampa_inativa_e_resultado_identico_ao_p0_zero(self):
        _, st = self.make()
        zero = runner.submit(st, ready(st, name="P0 0").scenario_uid, 2, runner.new_request_id(), background=False)
        sc = ready(st, fc_power=100.0, name="P0 100")
        run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual(run.state, "concluida", run.error)
        msgs = [i["message"] for i in run.outcome["engine_check"]["items"]]
        self.assertTrue(any("admissível no envelope efetivo" in m and "intervalo efetivo [40, 200] kW" in m for m in msgs))
        self.assertTrue(any("comprovadamente inativa" in m for m in msgs))
        # problema equivalente → mesmas entradas do motor → mesmo custo e mesmo despacho que P0 = 0
        self.assertEqual(run.summary["custo_total_rs"], zero.summary["custo_total_rs"])
        a = runner.load_csv(st, run.run_uid, "saidas/despacho_ems.csv")
        b = runner.load_csv(st, zero.run_uid, "saidas/despacho_ems.csv")
        np.testing.assert_array_equal(a["P_fc_kW"].to_numpy(), b["P_fc_kW"].to_numpy())

    def test_valida_mas_rampa_restritiva_continua_recusada(self):
        _, st = self.make()
        sc = ready(st, fc_power=195.0)
        run = self._run(st, sc)
        self.assertEqual((run.state, run.error["kind"]), ("falhou", "incompatibilidade"))
        msgs = [i["message"] for i in run.outcome["engine_check"]["items"]]
        self.assertTrue(any("admissível no envelope efetivo" in m for m in msgs))     # 1º limites físicos (ok)…
        self.assertTrue(any("PODERIA restringir" in m for m in msgs))                 # …depois a rampa (recusa)

    def test_termica_sem_rampa_dentro_do_envelope_executa(self):
        _, st = self.make()
        self.add_equipment(st, thermal_eq(pmin=20.0, ramp=None))
        sc = ready(st, thermal={"state": "em_operacao", "power_kW": 50.0})
        run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        self.assertEqual(run.state, "concluida", run.error)
        eff = run.outcome["engine_check"]["effective_initial_state"]["termica"]
        self.assertEqual((eff["n_ini"], eff["ramp_kW_min"]), (1, None))
        msgs = [i["message"] for i in run.outcome["engine_check"]["items"]]
        self.assertTrue(any("Térmica: potência inicial admissível" in m and "[20, 80] kW" in m for m in msgs), msgs)


if __name__ == "__main__":
    unittest.main()
