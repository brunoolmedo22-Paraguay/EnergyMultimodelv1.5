"""Refinamento do Piso 1 (domínio): FV hierárquica, derivadas de datasheet, bateria por datasheet, curvas
eólicas, importação ModelLab, balanço lógico, backups v2 e MIGRAÇÕES a partir de dados v1 reais.

Fixtures v1 (``tests/fixtures``) foram geradas pelo código do main ANTES desta missão.
"""
from __future__ import annotations

import copy
import io
import json
import shutil
import sqlite3
import tempfile
import unittest
import zipfile
from hashlib import sha256
from pathlib import Path

import numpy as np

from config.pv_database import MODULE_DB
from config.wind_turbine_database import TURBINE_DB
from seeds2.microgrid import adapter as A
from seeds2.microgrid import config as C
from seeds2.microgrid.derived import battery_derived, pv_array_kWp, pv_array_nominal, pv_plant_summary
from seeds2.microgrid.migrations import MigrationError, migrate_document
from seeds2.microgrid.modellab import ImportRejected, canonical_sha256, imported_record, parse_modellab_file
from seeds2.microgrid.references import wind_curve
from seeds2.microgrid.store import MIGRATIONS, MicrogridStore, StoreError
from seeds2_fixtures import FIXTURES, V1_BACKUP, V1_CONFIG, battery_params, module_array, pv_plant, v16_equivalent_config

PROFILE = json.loads((FIXTURES / "modellab_profile_v020.json").read_text(encoding="utf-8"))


def modellab_package(n_devices: int = 1, *, tamper: bool = False, rated_W: float | None = 1200.0) -> bytes:
    """Pacote no formato REAL de ``export_project`` do PEMFC ModelLab v0.5 (records + manifest canônico)."""
    recs = {}
    for i in range(n_devices):
        did = f"dev_{i:04d}aaaa"
        recs[f"device:{did}"] = {
            "id": did, "name": f"Stack de laboratório {i + 1}", "manufacturer": "Fabricante X", "model": "LT-1k",
            "technology": "PEMFC de baixa temperatura", "configuration": "refrigerado a ar", "n_cells": 41,
            "n_cells_origin": "ASUMIDO", "active_area_cm2": 232.0, "active_area_origin": "ASUMIDO",
            "rated_power_W": rated_W, "nominal_voltage_V": None, "nominal_current_A": None,
            "datasheet_reference": "", "notes": "", "provenance": "Criado no PEMFC ModelLab.",
            "active_calibration_id": f"cal_{i:04d}bbbb", "archived": False, "created_utc": "2026-10-26T13:00:00Z",
            "updated_utc": "2026-10-26T13:00:00Z", "rev": 1}
        recs[f"calibration:cal_{i:04d}bbbb"] = {
            "id": f"cal_{i:04d}bbbb", "device_id": did, "draft_id": None, "profile": PROFILE, "data_key": "d" * 64,
            "config_key": "c" * 64, "origin": "ejecutada", "label": "Calibração OTEKON", "app_version": "0.5.0",
            "created_utc": "2026-10-26T13:11:48Z", "content_sha256": "e" * 64}
    original = b"j_A_cm2,V\n0.1,0.9\n"
    manifest = {"schema": "pemfc-modellab/workspace", "schema_version": "1.0.0", "app_version": "0.5.0",
                "created_utc": "2026-10-26T14:00:00Z", "device_ids": sorted(r["id"] for k, r in recs.items() if k.startswith("device:")),
                "records": {k: canonical_sha256(v) for k, v in recs.items()},
                "blobs": {sha256(original).hexdigest(): {"name": "curva.csv", "size": len(original)}}}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for key, val in sorted(recs.items()):
            kind, rid = key.split(":", 1)
            body = dict(val)
            if tamper and kind == "device":
                body["rated_power_W"] = 99999.0
            z.writestr(f"records/{kind}/{rid}.json", json.dumps(body, ensure_ascii=False, indent=1, sort_keys=True))
        z.writestr(f"blobs/{sha256(original).hexdigest()}", original)
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True))
    return buf.getvalue()


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.dir = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()


# ======================================================================= FV hierárquica
class FotovoltaicaTest(unittest.TestCase):
    def test_valores_stc_por_arranjo_homogeneo(self):                     # aceitação 6
        for ref in ("CS7L-590MS", "CS6P-250P", "CS3W-450MS"):
            s = MODULE_DB[ref]["stc"]
            nom = pv_array_nominal(module_array(reference=ref, ns=14, np_=3))
            self.assertAlmostEqual(nom["P_STC_kW"], s["p_nom"] * 14 * 3 / 1000.0)
            self.assertAlmostEqual(nom["Voc_V"], s["v_oc"] * 14)
            self.assertAlmostEqual(nom["Isc_A"], s["i_sc"] * 3)
            self.assertAlmostEqual(nom["Vmp_V"], s["v_mp"] * 14)
            self.assertAlmostEqual(nom["Imp_A"], s["i_mp"] * 3)
            self.assertEqual(nom["n_modules"], 42)
            self.assertIn("STC", nom["assumptions"])
        self.assertIsNone(pv_array_nominal(C.new_array("incompleto", mode="modulo", reference="CS7L-590MS")))

    def test_usina_com_arranjos_de_modulos_diferentes(self):              # aceitação 5 e 8
        plant = pv_plant("Usina telhado", module_array("Arranjo 01", "CS7L-590MS", 14, 3),
                         module_array("Arranjo 02", "CS3W-450MS", 16, 2),
                         C.new_array("Arranjo 03", mode="declarado", declared_kWp=12.5, declared_source="placa do inversor"))
        self.assertEqual(C.errors(C.equipment_issues(plant)), [])
        s = pv_plant_summary(plant)
        self.assertEqual(s["n_arrays"], 3)
        self.assertAlmostEqual(s["computed_kWp"], (590 * 42 + 450 * 32) / 1000.0)
        self.assertAlmostEqual(s["declared_kWp"], 12.5)
        self.assertAlmostEqual(s["total_kWp"], s["computed_kWp"] + 12.5)
        self.assertEqual(s["n_modules"], 42 + 32)                         # quantidade de módulos ≠ de arranjos
        for k in ("Voc_V", "Isc_A", "Vmp_V", "Imp_A"):                    # sem agregação elétrica entre arranjos
            self.assertNotIn(k, s)
        cfg = v16_equivalent_config()
        cfg["equipment"] = [e for e in cfg["equipment"] if e["kind"] != "pv"]
        C.add_equipment(cfg, plant)
        plan = A.build_plan(cfg)
        st = {m.name: (m.status, m.parent) for m in plan.mappings if m.kind == "pv"}
        self.assertEqual(st["Usina telhado · Arranjo 01"], (A.INCOMPATIBLE, plant["id"]))
        self.assertEqual(st["Usina telhado · Arranjo 02"][0], A.INCOMPATIBLE)
        self.assertEqual(st["Usina telhado · Arranjo 03"][0], A.INCOMPATIBLE)
        self.assertFalse(plan.spec["solar"]["active"])                     # sem média entre módulos diferentes
        self.assertAlmostEqual(plan.pv_installed_kWp, s["total_kWp"])
        self.assertEqual(plan.pv_represented_kWp, 0.0)

    def test_arranjo_por_potencia_declarada_nao_inventa_modulo(self):    # aceitação 7
        arr = C.new_array("Arranjo legado", mode="declarado", declared_kWp=30.0, declared_source="projeto as-built")
        self.assertEqual(C.array_missing(arr), [])
        self.assertIsNone(arr["reference"])
        self.assertIsNone(arr["n_series"])
        self.assertIsNone(arr["n_parallel"])
        self.assertIsNone(pv_array_nominal(arr))
        self.assertEqual(pv_array_kWp(arr), (30.0, "declarada"))
        cfg = v16_equivalent_config()
        C.add_equipment(cfg, pv_plant("Usina antiga", arr))
        plan = A.build_plan(cfg)
        m = next(m for m in plan.mappings if m.id == arr["id"])
        self.assertEqual(m.status, A.INCOMPATIBLE)
        self.assertIn("potência nominal declarada", m.reason)
        self.assertTrue(plan.spec["solar"]["active"])                       # os arranjos homogêneos seguem
        self.assertAlmostEqual(plan.pv_represented_kWp, 11.8)
        self.assertAlmostEqual(plan.pv_installed_kWp, 41.8)
        self.assertTrue(plan.needs_ack)

    def test_arranjos_homogeneos_de_usinas_diferentes_sao_agregados(self):
        cfg = v16_equivalent_config()
        plan = A.build_plan(cfg)
        self.assertEqual(plan.spec["solar"]["n_parallel"], 10)
        self.assertEqual({m.parent for m in plan.mappings if m.kind == "pv"}, {e["id"] for e in cfg["equipment"] if e["kind"] == "pv"})

    def test_sujeira_padrao_zero_e_marcada(self):                         # aceitação 9
        a = C.new_array("Arranjo 01", mode="modulo", reference="CS7L-590MS", n_series=2, n_parallel=5)
        self.assertEqual(a["soiling_pct"], 0.0)
        self.assertTrue(a["soiling_default"])
        self.assertEqual(C.array_missing(a), [])                          # pode avançar sem preencher
        b = C.new_array("Arranjo 02", mode="modulo", reference="CS7L-590MS", n_series=2, n_parallel=5, soiling_pct=3.0)
        self.assertFalse(b["soiling_default"])
        bad = C.new_array("x", soiling_pct=100.0)
        self.assertTrue(C.errors(C.array_issues(bad, "a")))


# ======================================================================= eólica
class EolicaTest(unittest.TestCase):
    def test_curvas_vem_exclusivamente_dos_dados_originais(self):        # aceitação 10
        for key, entry in TURBINE_DB.items():
            c = wind_curve(key)
            self.assertEqual(c["points"], [(float(v), float(p)) for v, p in entry["curve"]["points"]], key)
            self.assertEqual(c["digitized"], entry["curve"]["source_type"] != "manufacturer_table")
            self.assertTrue(c["source_label"])
        self.assertFalse(wind_curve("Nordex N117/2400")["digitized"])
        self.assertTrue(wind_curve("EWT DW61-1MW")["digitized"])
        self.assertIn("não é medição certificada", wind_curve("EWT DW61-1MW")["source_label"])
        self.assertIsNone(wind_curve("Inexistente"))


# ======================================================================= bateria
class BateriaTest(unittest.TestCase):
    def test_banco_com_dados_nominais_sem_soc_inicial(self):              # aceitação 11
        eq = C.new_equipment("battery", "Banco BESS", params={"manufacturer": "Fabricante Y", "chemistry": "li_lfp",
                                                              "energy_kWh": 100.0, "voltage_V": 512.0, "power_kW": 50.0})
        self.assertEqual(C.errors(C.equipment_issues(eq)), [])
        self.assertNotIn("soc0_pct", eq["params"])
        self.assertTrue(C.battery_physically_registered(eq))
        self.assertFalse(C.battery_model_parametrized(eq))
        self.assertAlmostEqual(C.battery_energy_kWh(eq), 100.0)
        cfg = v16_equivalent_config()
        C.add_equipment(cfg, eq)
        m = next(m for m in A.build_plan(cfg).mappings if m.id == eq["id"])
        self.assertEqual(m.status, A.INCOMPLETE)                          # registrado, não simulável
        self.assertIn("Células em série", m.reason)

    def test_limites_soc_padrao_editaveis(self):                          # aceitação 12
        eq = C.new_equipment("battery", "Banco")
        self.assertEqual((eq["params"]["soc_min_pct"], eq["params"]["soc_max_pct"]), (20.0, 80.0))
        self.assertEqual(eq["params"]["soc_limits_source"], "sugerido")
        C.update_equipment({"equipment": [eq], "run_conditions": {}}, eq["id"],
                           params={"soc_min_pct": 10.0, "soc_max_pct": 95.0, "soc_limits_source": "fabricante"})
        self.assertEqual((eq["params"]["soc_min_pct"], eq["params"]["soc_max_pct"]), (10.0, 95.0))
        self.assertEqual(C.errors(C.equipment_issues(eq)), [])

    def test_taxa_c_derivada_somente_com_dados_suficientes(self):        # aceitação 13
        d = battery_derived({"energy_kWh": 100.0})
        self.assertIsNone(d["c_discharge"][0])                            # energia sozinha não define taxa C
        self.assertIsNone(d["c_charge"][0])
        d = battery_derived({"capacity_Ah": 200.0, "i_discharge_max_A": 100.0, "i_charge_max_A": 40.0})
        self.assertEqual(d["c_discharge"], (0.5, "derivada", "C = I_máx/Q"))
        self.assertEqual(d["c_charge"], (0.2, "derivada", "C = I_máx/Q"))
        d = battery_derived({"capacity_Ah": 200.0, "c_discharge_max": 1.0, "i_discharge_max_A": 100.0})
        self.assertEqual(d["c_discharge"][1], "declarada")
        self.assertTrue(any("difere de I_máx/Q" in w for w in d["warnings"]))   # contradição não é silenciosa
        d = battery_derived({"energy_kWh": 100.0, "voltage_V": 500.0, "capacity_Ah": 400.0})
        self.assertTrue(any("Energia declarada" in w for w in d["warnings"]))
        d = battery_derived({"voltage_V": 48.0, "capacity_Ah": 100.0})
        self.assertEqual(d["energy_kWh"], (4.8, "derivada", "E = V·Q/1000"))

    def test_soc_inicial_e_condicao_da_rodada(self):
        cfg = v16_equivalent_config()
        b = next(e for e in cfg["equipment"] if e["kind"] == "battery")
        cfg["run_conditions"]["battery_soc0_pct"].pop(b["id"])
        plan = A.build_plan(cfg)
        self.assertEqual(next(m for m in plan.mappings if m.id == b["id"]).status, A.INCOMPLETE)
        cfg["run_conditions"]["battery_soc0_pct"][b["id"]] = 95.0         # fora de [20, 90]
        self.assertIn("fora dos limites", next(m for m in A.build_plan(cfg).mappings if m.id == b["id"]).reason)
        cfg["run_conditions"]["battery_soc0_pct"][b["id"]] = 60.0
        plan = A.build_plan(cfg)
        self.assertEqual(plan.spec["battery"]["soc0"], 0.6)
        self.assertEqual(plan.provenance()["run_conditions"]["battery_soc0_pct"][b["id"]], 60.0)


# ======================================================================= PEMFC / ModelLab
class ModelLabTest(_Tmp):
    def test_pacote_real_valido_e_resumido_com_estado_de_validacao(self):   # aceitação 14
        info = parse_modellab_file(modellab_package(), "Stack_1__dev_0000aaaa.pmldevice.zip")
        self.assertEqual(info["format"], "pmldevice")
        self.assertEqual(info["device"]["manufacturer"], "Fabricante X")
        self.assertEqual(info["device"]["n_cells"], 41)
        cal = info["calibrations"][0]
        self.assertEqual(cal["status_code"], "AJUSTADO_A_CURVA")
        self.assertEqual(cal["validation_status"], "SIN_VALIDACION_INDEPENDIENTE")
        self.assertIn("sem capacidade preditiva", cal["status_label"])
        self.assertEqual(cal["domain"]["temperature_K"], [298.15, 373.15])
        self.assertEqual(info["active_calibration_id"], "cal_0000bbbb")
        self.assertEqual(info["integration_status"], "pendente_integracao")
        prof = parse_modellab_file(json.dumps(PROFILE).encode(), "profile.json")
        self.assertEqual(prof["format"], "profile")
        self.assertEqual(prof["calibrations"][0]["profile_id"], PROFILE["profile_id"])

    def test_pacotes_invalidos_sao_rejeitados(self):
        casos = {"adulterado": modellab_package(tamper=True), "dois dispositivos": modellab_package(2),
                 "não-zip": b"PK\x03\x04lixo", "json qualquer": b'{"a": 1}', "vazio": b"",
                 "perfil sem curva": json.dumps({**PROFILE, "datasets": []}).encode(),
                 "esquema errado": json.dumps({**PROFILE, "schema": "outro"}).encode()}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("manifest.json", json.dumps({"schema": "pemfc-modellab/workspace", "schema_version": "1.0.0", "records": {}}))
            z.writestr("../fora.json", "{}")
        casos["caminho malicioso"] = buf.getvalue()
        for nome, data in casos.items():
            with self.subTest(nome), self.assertRaises(ImportRejected):
                parse_modellab_file(data, "x")

    def test_importado_e_registrado_mas_pendente_de_integracao_e_vai_no_backup(self):
        store = MicrogridStore(self.dir)
        data = modellab_package()
        info = parse_modellab_file(data, "stack.pmldevice.zip")
        h = store.put_blob(data, info["filename"], "application/zip")
        cfg = v16_equivalent_config()
        eq = C.add_equipment(cfg, C.new_equipment("pemfc", "Stack de laboratório", params={
            "reference": C.PEMFC_IMPORT_REF, "quantity": 1}, imported=imported_record(info, h, C.utc_now())))
        self.assertEqual(C.errors(C.validate(cfg)), [])
        self.assertAlmostEqual(C.installed_power_kW(eq), 1.2)
        plan = A.build_plan(cfg)
        m = next(m for m in plan.mappings if m.id == eq["id"])
        self.assertEqual(m.status, A.INCOMPATIBLE)
        self.assertIn("Pendente de integração científica", m.reason)
        self.assertEqual(plan.spec["fc"]["N_fc"], 4)                      # modelo PEMFC existente não substituído
        store.save(cfg, 0)
        backup = store.export_backup()
        with zipfile.ZipFile(io.BytesIO(backup)) as z:
            self.assertIn(f"blobs/{h}", z.namelist())
        with tempfile.TemporaryDirectory() as other:
            dst = MicrogridStore(other)
            r = dst.restore_backup(backup, 0, confirm=True)
            self.assertEqual(dst.get_blob(h), data)                        # pacote original preservado
            self.assertEqual(C.find_equipment(r.config, eq["id"])["imported"]["calibrations"][0]["status_code"],
                             "AJUSTADO_A_CURVA")


# ======================================================================= balanço lógico
class BalancoTest(unittest.TestCase):
    def test_sem_acoplamentos_eletricos_ficticios(self):                  # aceitação 15
        cfg = C.new_config("x")
        self.assertNotIn("topology", cfg)
        self.assertEqual(cfg["energy_balance"], {"grid_connection": "nao_declarada"})
        doc = json.dumps(cfg)
        for termo in ("couplings", "bus_kind", "nominal_voltage_V", "load_coupling"):
            self.assertNotIn(termo, doc)


# ======================================================================= backups v2 e migrações
class MigracaoTest(_Tmp):
    def test_documento_v1_real_migra_sem_perdas(self):                    # aceitação 18
        v1 = json.loads(V1_CONFIG.read_text(encoding="utf-8"))
        v2, applied = migrate_document(v1)
        self.assertEqual(C.errors(C.validate(v2)), [])
        self.assertEqual(v2["installation"]["uid"], v1["installation"]["uid"])
        self.assertEqual([e["id"] for e in v2["equipment"]], [e["id"] for e in v1["equipment"]])
        self.assertEqual(v2["installation"]["location"]["address"], v1["installation"]["location"])
        self.assertEqual(v2["installation"]["location"]["latitude"], v1["installation"]["latitude"])
        for old, new in zip(v1["equipment"], v2["equipment"]):
            if old["kind"] == "pv":
                a = new["arrays"][0]
                self.assertEqual((a["reference"], a["n_series"], a["n_parallel"], a["soiling_pct"]),
                                 (old["params"]["reference"], old["params"]["n_series"], old["params"]["n_parallel"],
                                  old["params"]["soiling_pct"]))
                self.assertEqual(a["id"], "arr-" + old["id"][3:])
            if old["kind"] == "battery":
                p = new["params"]
                self.assertEqual((p["model_reference"], p["model_n_series"], p["model_n_parallel"], p["soc_min_pct"],
                                  p["soc_max_pct"], p["c_discharge_max"], p["c_charge_max"]),
                                 (old["params"]["reference"], old["params"]["n_series"], old["params"]["n_parallel"],
                                  old["params"]["soc_min_pct"], old["params"]["soc_max_pct"], old["params"]["c_discharge"],
                                  old["params"]["c_charge"]))
                self.assertNotIn("soc0_pct", p)
                if old["params"]["soc0_pct"] is not None:
                    self.assertEqual(v2["run_conditions"]["battery_soc0_pct"][old["id"]], old["params"]["soc0_pct"])
            if old["kind"] in ("wind", "thermal", "pemfc"):
                self.assertEqual(new["params"], old["params"])
        self.assertEqual(v2["legacy"]["topology_v1"], v1["topology"])     # preservado, não reinterpretado
        self.assertIn("NÃO representa conexões elétricas verificadas", v2["legacy"]["topology_v1_note"])
        self.assertEqual(v2["energy_balance"]["grid_connection"], v1["topology"]["grid_connection"])
        self.assertEqual(v2["demand"], v1["demand"])
        self.assertEqual(applied[0]["from"], 1)
        with self.assertRaises(MigrationError):
            migrate_document({**v1, "schema_version": 9})

    def test_rodada_ems_com_configuracao_migrada_e_equivalente(self):    # aceitação 19
        import orchestrator_runtime as RT

        v1 = json.loads(V1_CONFIG.read_text(encoding="utf-8"))
        store = MicrogridStore(self.dir)
        csv = MicrogridStore(self.dir)  # mesma pasta; blob da demanda vem do backup v1
        rep = store.inspect_backup(V1_BACKUP.read_bytes())
        self.assertTrue(rep.ok, rep.errors)
        store.restore_backup(V1_BACKUP.read_bytes(), 0, confirm=True)
        cfg = store.load().config
        plan = A.build_plan(cfg)
        # Semântica V1.6 do documento v1 (mesmos números): solar 2×10 CS7L, FC 4, bateria 200×132 60/20/90 %, 1C/0,5C,
        # eólica EWT ×1; térmica desabilitada e banco sem dados ficam fora.
        expected = RT.default_model_spec()
        expected["wind"].update(active=True, turbine_key="EWT DW61-1MW", turbine_count=1, apply_grid_loss=False)
        for k in ("solar", "wind", "fc", "battery", "thermal"):
            self.assertEqual(plan.spec[k], expected[k], k)
        carga = A.build_load(plan.load_descriptor, csv.get_blob)
        opt = RT.default_optimizer_config()
        with tempfile.TemporaryDirectory() as p1, tempfile.TemporaryDirectory() as p2:
            r1, _ = RT.run_optimizer(RT.build_exchange_package(carga, plan.spec, opt, destino=Path(p1))[0], opt)
            r2, _ = RT.run_optimizer(RT.build_exchange_package(carga, expected, opt, destino=Path(p2))[0], opt)
        np.testing.assert_allclose(r1["P_kW"], r2["P_kW"])
        self.assertAlmostEqual(r1["rel"]["custo_total_rs"], r2["rel"]["custo_total_rs"])
        self.assertEqual(r1["k_validos"], len(carga.P_kW))

    def test_backup_v1_real_e_restaurado_e_migrado(self):                # aceitação 16 e 18
        store = MicrogridStore(self.dir)
        rep = store.inspect_backup(V1_BACKUP.read_bytes())
        self.assertTrue(rep.ok, rep.errors)
        self.assertTrue(rep.migrated)
        self.assertTrue(any("formato anterior" in w for w in rep.warnings))
        r = store.restore_backup(V1_BACKUP.read_bytes(), 0, confirm=True)
        self.assertEqual(r.config["schema_version"], C.DOC_SCHEMA_VERSION)
        self.assertIn("migrado do formato anterior", store.history()[0]["note"])
        blob = r.config["demand"]["csv"]["blob"]
        self.assertTrue(store.get_blob(blob).startswith(b"t_min,P_kW"))
        data = store.export_backup()                                       # novo backup no formato v2
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            m = json.loads(z.read("manifest.json"))
        self.assertEqual((m["format_version"], m["doc_schema_version"]), (2, 2))
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(MicrogridStore(other).restore_backup(data, 0, confirm=True).fingerprint, r.fingerprint)

    def test_banco_sqlite_v1_e_migrado_preservando_historico(self):      # aceitação 18
        v1 = json.loads(V1_CONFIG.read_text(encoding="utf-8"))
        db = self.dir / "seeds2.db"
        con = sqlite3.connect(db)
        for stmt in MIGRATIONS[0][1]:
            con.execute(stmt)
        con.execute("PRAGMA user_version = 1")
        early = copy.deepcopy(v1)
        early["demand"]["source"], early["demand"]["csv"], early["demand"]["provenance"] = "walkforward", None, "referencia"
        early["demand"]["walkforward"] = {"scenario": "Ideal", "profile": "Normal", "start_hour": 12}
        for rev, doc in ((1, early), (2, early)):
            con.execute("INSERT INTO revisions VALUES (?,?,?,?,?,?,?)", (rev, v1["installation"]["uid"], C.fingerprint(doc),
                                                                         json.dumps(doc), "2026-11-01T00:00:00+00:00", "v1", "edit"))
        con.execute("INSERT INTO microgrid VALUES (1,?,?,?,?,?)", (v1["installation"]["uid"], 2, C.fingerprint(early),
                                                                   json.dumps(early), "2026-11-01T00:00:00+00:00"))
        con.execute("INSERT INTO simulation_runs(created_at, config_revision, config_fingerprint, spec_fingerprint, spec_origin) "
                    "VALUES ('2026-11-01', 2, ?, ?, 'microrrede')", (C.fingerprint(early), "f" * 64))
        con.commit()
        con.close()
        store = MicrogridStore(self.dir)                                   # abre → migra
        self.assertEqual(store.db_version(), MIGRATIONS[-1][0])
        self.assertTrue((self.dir / "seeds2.db.bak-v1").exists())         # cópia do banco anterior
        cur = store.load()
        self.assertEqual(cur.revision, 3)
        self.assertEqual(cur.config["schema_version"], 2)
        self.assertEqual(cur.config["installation"]["uid"], v1["installation"]["uid"])
        self.assertEqual(len(cur.config["equipment"]), len(v1["equipment"]))
        hist = store.history()
        self.assertEqual([h["revision"] for h in hist], [3, 2, 1])
        self.assertEqual(hist[0]["origin"], "migration")
        with sqlite3.connect(db) as c2:
            old = json.loads(c2.execute("SELECT document FROM revisions WHERE revision = 1").fetchone()[0])
        self.assertEqual(old["schema_version"], 1)                         # revisão antiga intacta
        self.assertEqual(store.get_revision(1).config["schema_version"], 2)  # migrada na leitura
        self.assertEqual(store.runs()[0]["config_revision"], 2)            # referência de rodada antiga preservada
        reopened = MicrogridStore(self.dir)                                # idempotente
        self.assertEqual(reopened.load().revision, 3)
        self.assertEqual(A.build_plan(cur.config).spec["battery"]["soc0"], 0.6)

    def test_banco_v1_com_documento_invalido_nao_e_corrompido(self):
        db = self.dir / "seeds2.db"
        con = sqlite3.connect(db)
        for stmt in MIGRATIONS[0][1]:
            con.execute(stmt)
        con.execute("PRAGMA user_version = 1")
        bad = {"schema_version": 1, "installation": "quebrado"}
        con.execute("INSERT INTO microgrid VALUES (1,'u',1,'f',?, 'now')", (json.dumps(bad),))
        con.commit()
        con.close()
        with self.assertRaises(StoreError) as ctx:
            MicrogridStore(self.dir)
        self.assertIn("banco mantido na versão anterior", str(ctx.exception))
        with sqlite3.connect(db) as c2:
            self.assertEqual(c2.execute("PRAGMA user_version").fetchone()[0], 1)   # banco mantido em v1
            self.assertEqual(json.loads(c2.execute("SELECT document FROM microgrid").fetchone()[0]), bad)


# ======================================================================= relatório PDF (aceitação 17)
class RelatorioPdfTest(_Tmp):
    @staticmethod
    def _text(pdf: bytes) -> tuple[object, str]:
        from pypdf import PdfReader

        r = PdfReader(io.BytesIO(pdf))
        return r, "\n".join(p.extract_text() for p in r.pages)

    def _build(self, cfg: dict):
        from seeds2.report.pdf import build_report, report_filename

        store = MicrogridStore(self.dir)
        st = store.save(cfg, 0)
        return st, build_report(st, store), report_filename(st.config)

    def test_relatorio_da_configuracao_salva(self):
        st, pdf, fname = self._build(v16_equivalent_config("Microrrede PDF"))
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertTrue(fname.endswith(".pdf") and fname.isascii())
        reader, text = self._text(pdf)
        self.assertGreaterEqual(len(reader.pages), 3)
        self.assertIn("Microrrede PDF", reader.metadata.title)
        for title in ("Resumo executivo", "Identificação e localização", "Inventário técnico", "Fotovoltaica", "Baterias",
                      "Modelo de balanço energético", "Compatibilidade com a simulação", "Demanda e dados",
                      "Rastreabilidade e alcance"):
            self.assertIn(title, text, title)
        # valores exatos do inventário (2 usinas × 10 módulos de 590 Wp; 2 bancos de 200s×66p células 3,3 V/2,3 Ah)
        self.assertIn(st.fingerprint, text)
        self.assertIn("11,8 kWp", text)
        self.assertIn("5,90", text)
        self.assertIn("200,4 kWh", text)
        self.assertIn("Não declarado", text)                           # localização ausente nunca é inventada
        self.assertIn("Configuração ativada", text)
        self.assertNotIn("PRELIMINAR", text)
        for bad in ("None", "nan", "NaN", "null"):
            self.assertNotRegex(text, rf"\b{bad}\b")
        self.assertIn("Não constitui certificação", text)

    def test_relatorio_preliminar_com_eolica(self):
        cfg = v16_equivalent_config("Microrrede preliminar")
        cfg["commissioning"].update(completed=False, step=3, completed_at=None)
        C.add_equipment(cfg, C.new_equipment("wind", "Aerogerador 01", tag="WT-01",
                                             params={"reference": "EWT DW61-1MW", "count": 1}))
        _, pdf, _ = self._build(cfg)
        _, text = self._text(pdf)
        self.assertIn("PRELIMINAR", text)
        self.assertIn("Eólica", text)
        self.assertIn("EWT DW61-1MW", text)
        self.assertIn("digitalizad", text)                              # curva digitalizada é identificada como tal
        for bad in ("None", "nan", "NaN"):
            self.assertNotRegex(text, rf"\b{bad}\b")


# ======================================================================= geolocalização (aceitação 1–3)
class GeolocalizacaoTest(unittest.TestCase):
    def setUp(self):
        from seeds2.ui.forms import GEO_MESSAGES, geo_result

        self.geo, self.msgs = geo_result, GEO_MESSAGES

    def test_permissao_concedida_mostra_precisao_e_sugere_fuso(self):
        r = self.geo({"type": "geo", "ok": True, "lat": -25.4589123456, "lon": -54.5866, "accuracy": 35.4,
                      "tz": "America/Asuncion"})
        self.assertTrue(r["ok"])
        self.assertEqual((r["lat"], r["lon"]), (-25.458912, -54.5866))
        self.assertEqual(r["accuracy_m"], 35.4)
        self.assertIn("±35 m", r["message"])
        self.assertEqual(r["tz_suggested"], "America/Asuncion")
        # nunca infere cidade, estado ou endereço
        self.assertFalse({"city", "region", "address", "country"} & set(r))

    def test_negada_indisponivel_insegura_e_tempo_esgotado(self):
        for code in ("denied", "unavailable", "insecure", "unsupported", "timeout"):
            r = self.geo({"type": "geo", "ok": False, "code": code, "tz": "UTC"})
            self.assertFalse(r["ok"])
            self.assertEqual(r["message"], self.msgs[code])
            self.assertNotIn("lat", r)
        self.assertEqual(self.geo({"type": "geo", "ok": False, "code": "denied"})["tone"], "bad")
        self.assertIn("negada", self.msgs["denied"])
        self.assertIn("HTTPS", self.msgs["insecure"])

    def test_coordenadas_invalidas_ou_carga_estranha_sao_rejeitadas(self):
        for payload in ({"type": "geo", "ok": True, "lat": 91, "lon": 0},
                        {"type": "geo", "ok": True, "lat": 0, "lon": -181},
                        {"type": "geo", "ok": True, "lat": "10", "lon": 5},
                        {"type": "geo", "ok": True, "lat": True, "lon": 5},
                        {"type": "geo", "ok": False, "code": "<script>"},
                        None, "texto", {"type": "outro"}):
            r = self.geo(payload)
            self.assertFalse(r["ok"], payload)
            self.assertIn(r["message"], self.msgs.values())

    def test_precisao_ausente_ou_negativa_nao_e_inventada(self):
        r = self.geo({"type": "geo", "ok": True, "lat": 1.0, "lon": 2.0, "accuracy": -3})
        self.assertTrue(r["ok"])
        self.assertIsNone(r["accuracy_m"])
        self.assertNotIn("±", r["message"])

    def test_localizacao_e_opcional_e_validada_ao_salvar(self):
        loc = C.new_location()
        self.assertEqual(C.validate_location(loc), [])
        loc.update(latitude=-25.45, longitude=-54.58, timezone="America/Asuncion")
        self.assertEqual(C.validate_location(loc), [])
        loc["latitude"] = 120
        self.assertTrue(C.validate_location(loc))


if __name__ == "__main__":
    unittest.main()
