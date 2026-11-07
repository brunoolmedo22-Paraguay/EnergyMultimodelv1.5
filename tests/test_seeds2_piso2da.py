"""Piso 2D-A — Arquivo Científico Portátil (domínio, sem interface; ver ``test_seeds2_piso2da_app.py``).

Cobre: exportação completa (cenário sem rodadas, várias versões, várias rodadas concluídas/falhas/interrompidas,
manifestos e documentos com o texto EXATO da origem, inventário de referência, previsões normalizadas e originais,
séries completas do EMS), verificação de integridade (SHA-256 e tamanho de todos os recursos, recurso corrompido,
recurso ausente, relações), segurança do importador (Zip Slip, caminhos absolutos, links, duplicatas, executáveis,
JSON aninhado, bombas ZIP, limites, versões e formatos incompatíveis), importação atômica numa instalação limpa
(reinício em novo processo, rollback em erro e em processo morto), duplicatas e colisões de identidade, isolamento entre
microrredes, preservação dos cenários/rodadas originais e — prova científica — uma rodada REAL do Piso 2C exportada,
importada noutra instalação e reaberta com os mesmos valores, sem recomputação (otimizador sabotado).

Dados: inventário fictício equivalente à configuração padrão V1.6 e perfis de referência da própria V1.6.
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
from hashlib import sha256
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

import orchestrator_runtime as RT
from seeds2.archive import exporter
from seeds2.archive import format as FMT
from seeds2.archive import service as AS
from seeds2.archive.store import ArchiveError, ArchiveStore, StudyRejected
from seeds2.archive.view import StudyView
from seeds2.microgrid import config as C
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.operation import forecast_sources as FS
from seeds2.operation import forecasts as F
from seeds2.operation import runner
from seeds2.operation import service
from seeds2.operation import strategy as SG
from seeds2_fixtures import v16_equivalent_config
from test_seeds2_piso2c import edit, mission_load, ready

RAIZ = Path(__file__).resolve().parents[1]


# =========================================================================== construção do estudo de origem
def _csv_demand_entry(ref: dict) -> F.Candidate:
    """Previsão de demanda vinda de um CSV IMPORTADO (para provar a preservação do arquivo original)."""
    carga = mission_load(30)
    ts = carga.t0 + pd.to_timedelta(carga.t_min, unit="min")
    text = "data_hora;demanda_kW\n" + "".join(f"{t:%Y-%m-%d %H:%M};{str(round(v, 3)).replace('.', ',')}\n"
                                                for t, v in zip(ts, carga.P_kW))
    insp = FS.inspect_csv(text.encode("utf-8"), "medicao_demanda.csv", "demand")
    assert insp.ok, insp.errors
    m = copy.deepcopy(insp.suggestion)
    for k, v in m["columns"].items():
        v["unit"] = v["unit"] or F.VARIABLES[k].unit
    c = FS.csv_candidate(insp, "demand", m, inventory_ref=ref, provenance="nao_declarado")
    assert c.ok, [f.message for f in c.analysis.findings if f.level == "erro"]
    return c


def build_study(store) -> dict:
    """Cenário com 4 versões e 3 rodadas (concluída REAL, falha, interrompida) + um cenário sem rodadas."""
    out: dict = {}
    sc = ready(store, name="Alta demanda")                              # v1 (criação) + v2 (completo)
    out["done"] = runner.submit(store, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
    assert out["done"].state == "concluida"
    sc3 = edit(store, sc, lambda d: d["ems_strategy"].update(seed=7), note="semente 7")       # v3
    with mock.patch.object(RT, "run_optimizer", side_effect=RuntimeError("solver sabotado no teste")):
        out["failed"] = runner.submit(store, sc3.scenario_uid, sc3.version, runner.new_request_id(), background=False)
    assert out["failed"].state == "falhou"
    with mock.patch.object(runner, "_execute", lambda *a, **k: None):  # processo "morre" antes de executar
        r = runner.submit(store, sc3.scenario_uid, sc3.version, runner.new_request_id(), background=True)
        runner.wait(r.run_uid, 10)
    runner.recover(store)
    out["interrupted"] = store.get_run(r.run_uid)
    assert out["interrupted"].state == "interrompida"
    cand = _csv_demand_entry(sc3.document["inventory_ref"])

    def _csv(d):
        d["forecasts"]["demand"] = cand.entry
    doc = copy.deepcopy(sc3.document)
    _csv(doc)
    out["v4"] = service.save(store, doc, sc3.version, note="demanda medida (CSV)", new_blobs=cand.blobs)
    out["scenario_uid"] = sc.scenario_uid
    out["csv_original"] = cand.entry["blob"]
    out["empty"] = service.create(store, name="Sem rodadas", description="cenário recém-criado")
    return out


def _dump(store) -> dict:
    """Estado LÓGICO completo de cenários e rodadas (para provar que nada mudou)."""
    with store.snapshot() as snap:
        con = snap._con
        return {t: [tuple(r) for r in con.execute(f"SELECT * FROM {t} ORDER BY 1, 2").fetchall()]
                for t in ("scenarios", "scenario_versions", "scenario_runs", "scenario_run_data", "revisions", "blobs")}


def _rezip(data: bytes, mutate) -> bytes:
    """Reescreve um pacote aplicando ``mutate(dict nome → bytes)`` (o manifesto não é recalculado)."""
    zin = zipfile.ZipFile(io.BytesIO(data))
    files = {i.filename: zin.read(i) for i in zin.infolist()}
    mutate(files)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in files.items():
            z.writestr(n, b)
    return buf.getvalue()


def _resign(files: dict) -> None:
    """Recalcula o manifesto (SHA-256/tamanho) — simula um pacote internamente coerente porém adulterado."""
    m = json.loads(files["manifest.json"])
    for p in list(m["resources"]):
        if p not in files:
            del m["resources"][p]
    for p, b in files.items():
        if p != "manifest.json":
            r = m["resources"].setdefault(p, {"media_type": FMT.expected_media_type(p) or "text/csv", "role": "x"})
            r.update(sha256=sha256(b).hexdigest(), size=len(b))
    files["manifest.json"] = json.dumps(m).encode()


class _Fixture:
    """Instalação de origem (uma vez por módulo): microrrede A com o estudo + microrrede B (isolamento)."""
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
            data, man = exporter.export_bytes(st, info["scenario_uid"])
            cls._done = (tmp, reg, st, info, data, man)
        return cls._done


def setUpModule():
    _Fixture.get()


class _Base(unittest.TestCase):
    def setUp(self):
        self.src_tmp, self.reg, self.store, self.info, self.pkg, self.man = _Fixture.get()
        self._tmp = tempfile.TemporaryDirectory()
        self.dest = self._tmp.name
        self.archive = ArchiveStore(self.dest)

    def tearDown(self):
        self._tmp.cleanup()


# =========================================================================== exportação
class ExportacaoTest(_Base):
    def test_cenario_sem_rodadas(self):
        data, man = exporter.export_bytes(self.store, self.info["empty"].scenario_uid)
        rep = FMT.inspect(data)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(rep.summary["versions"], 1)
        self.assertEqual(rep.summary["runs"], 0)
        self.assertEqual(man["study"]["runs"], [])
        res = self.archive.import_package(data)
        self.assertEqual(StudyView(self.archive, res.study.archive_uid).list_runs(), [])

    def test_varias_versoes_e_varias_rodadas_com_estados_originais(self):
        st = self.man["study"]
        self.assertEqual(st["versions"], [1, 2, 3, 4])
        self.assertEqual(st["counts"]["runs_by_state"], {"concluida": 1, "falhou": 1, "interrompida": 1})
        self.assertEqual(set(st["runs"]), {self.info[k].run_uid for k in ("done", "failed", "interrupted")})
        res = self.archive.import_package(self.pkg)
        v = StudyView(self.archive, res.study.archive_uid)
        for key in ("done", "failed", "interrupted"):
            orig = self.store.get_run(self.info[key].run_uid)
            got = v.get_run(orig.run_uid)
            self.assertEqual(got.state, orig.state)                        # nenhuma falha vira concluída
            self.assertEqual(got.error, orig.error)
            self.assertEqual(got.summary, orig.summary)
            self.assertEqual(got.outcome, orig.outcome)
            self.assertEqual(got.data, orig.data)
            if key != "done":
                self.assertEqual(got.data, {})                             # nenhum resultado inventado
                self.assertIsNone(got.summary)

    def test_manifestos_e_documentos_com_texto_exato_da_origem(self):
        z = zipfile.ZipFile(io.BytesIO(self.pkg))
        with self.store.snapshot() as snap:
            for r in snap.run_rows(self.info["scenario_uid"]):
                self.assertEqual(z.read(f"runs/{r['run_uid']}/manifest.json").decode(), r["manifest"])
                for n in ("outcome", "summary", "error"):
                    if r[n] is not None:
                        self.assertEqual(z.read(f"runs/{r['run_uid']}/{n}.json").decode(), r[n])
            for v in snap.scenario_versions(self.info["scenario_uid"]):
                self.assertEqual(z.read(FMT.version_path(v["version"], True)).decode(), v["document"])
                self.assertEqual(C.fingerprint(json.loads(v["document"])), v["fingerprint"])

    def test_inventario_de_referencia_preservado(self):
        z = zipfile.ZipFile(io.BytesIO(self.pkg))
        rev = self.info["v4"].base_revision
        with self.store.snapshot() as snap:
            row = snap.revision_row(rev)
        self.assertEqual(z.read(FMT.revision_path(rev, True)).decode(), row["document"])
        meta = json.loads(z.read(FMT.revision_path(rev)))
        self.assertEqual(meta["fingerprint"], row["fingerprint"])
        cat = json.loads(z.read("inventory/catalog_references.json"))
        self.assertIn("battery", cat["references"])                       # referência de catálogo citada pelos bancos
        self.assertIn("pv", cat["references"])

    def test_previsoes_normalizadas_e_originais_preservadas(self):
        z = zipfile.ZipFile(io.BytesIO(self.pkg))
        doc = self.info["v4"].document
        dem = doc["forecasts"]["demand"]
        for h in (dem["data"], dem["blob"]):
            self.assertEqual(z.read(f"forecasts/blobs/{h}"), self.store.get_blob(h))
            self.assertEqual(sha256(z.read(f"forecasts/blobs/{h}")).hexdigest(), h)
        meta = self.man["resources"][f"forecasts/blobs/{dem['blob']}"]
        self.assertEqual(meta["original_name"], "medicao_demanda.csv")
        self.assertEqual(meta["media_type"], "text/csv")
        # versões antigas: as séries de então também estão (nada recortado nem trocado)
        for v in (2, 3):
            fc = self.store.get_scenario(self.info["scenario_uid"], v).document["forecasts"]
            for e in fc.values():
                self.assertIn(f"forecasts/blobs/{e['data']}", self.man["resources"])

    def test_series_completas_do_ems_preservadas(self):
        z = zipfile.ZipFile(io.BytesIO(self.pkg))
        run = self.info["done"]
        self.assertGreaterEqual(len(run.data), 6)
        for name, d in run.data.items():
            raw = z.read(f"runs/{run.run_uid}/data/{name}")
            self.assertEqual(raw, self.store.run_data(run.run_uid, name))
            self.assertEqual(sha256(raw).hexdigest(), d["sha256"])

    def test_exportacao_nao_altera_cenarios_nem_rodadas_e_rodadas_continuam_imutaveis(self):
        before = _dump(self.store)
        exporter.export_bytes(self.store, self.info["scenario_uid"])
        self.assertEqual(_dump(self.store), before)
        con = sqlite3.connect(self.store.path)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                con.execute("UPDATE scenario_runs SET summary = '{}' WHERE run_uid = ?", (self.info["done"].run_uid,))
            with self.assertRaises(sqlite3.DatabaseError):
                con.execute("DELETE FROM scenario_versions")
        finally:
            con.close()

    def test_rodada_em_execucao_impede_exportacao(self):
        sc = self.store.get_scenario(self.info["scenario_uid"])
        with mock.patch.object(runner, "_execute", lambda *a, **k: None):
            r = runner.submit(self.store, sc.scenario_uid, 2, runner.new_request_id(), background=False)
        try:
            self.assertEqual(r.state, "em_execucao")
            with self.assertRaises(exporter.ExportError):
                exporter.export_bytes(self.store, sc.scenario_uid)
        finally:
            runner.recover(self.store)
            self.assertEqual(self.store.get_run(r.run_uid).state, "interrompida")
            _Fixture._done = None                                          # o estudo da origem mudou: recriar

    def test_exportacao_em_arquivo_publicada_atomicamente(self):
        dest = Path(self.dest) / f"x{FMT.SUFFIX}"
        res = exporter.export_to_file(self.store, self.info["scenario_uid"], dest)
        self.assertTrue(dest.is_file())
        self.assertFalse(dest.with_name(dest.name + ".part").exists())
        self.assertEqual(res.package_sha256, FMT.package_digest(dest))
        with self.assertRaises(Exception):
            exporter.export_to_file(self.store, "f" * 32, Path(self.dest) / f"y{FMT.SUFFIX}")
        self.assertEqual(sorted(p.name for p in Path(self.dest).glob("y*")), [])


# =========================================================================== verificação de integridade
class IntegridadeTest(_Base):
    def test_todos_os_recursos_tem_sha256_e_tamanho_conferidos(self):
        rep = FMT.inspect(self.pkg)
        self.assertTrue(rep.ok, rep.errors)
        z = zipfile.ZipFile(io.BytesIO(self.pkg))
        names = {i.filename for i in z.infolist()} - {"manifest.json"}
        self.assertEqual(names, set(self.man["resources"]))
        for p, r in self.man["resources"].items():
            b = z.read(p)
            self.assertEqual((sha256(b).hexdigest(), len(b)), (r["sha256"], r["size"]))
        self.assertIn("não é uma assinatura digital", FMT.INTEGRITY_NOTE.lower().replace("Não", "não"))

    def test_recurso_corrompido_detectado(self):
        name = f"runs/{self.info['done'].run_uid}/data/saidas/despacho_ems.csv"
        bad = _rezip(self.pkg, lambda f: f.__setitem__(name, f[name].replace(b"1", b"2", 1)))
        rep = FMT.inspect(bad)
        self.assertFalse(rep.ok)
        self.assertTrue(any("SHA-256" in e and "despacho_ems" in e for e in rep.errors), rep.errors)
        with self.assertRaises(StudyRejected):
            self.archive.import_package(bad)
        self.assertEqual(self.archive.list_studies(), [])

    def test_corrupcao_coerente_com_manifesto_recalculado_ainda_detectada(self):
        """Um documento alterado com o manifesto recalculado continua recusado pela impressão digital."""
        p = FMT.version_path(2, True)

        def mut(f):
            d = json.loads(f[p])
            d["ems_strategy"]["N"] = 9
            f[p] = C.canonical_json(d).encode()
            _resign(f)
        rep = FMT.inspect(_rezip(self.pkg, mut))
        self.assertFalse(rep.ok)
        self.assertTrue(any("impressão digital" in e for e in rep.errors), rep.errors)

    def test_arquivo_obrigatorio_faltante_detectado(self):
        rev = self.info["v4"].base_revision
        for victim in (FMT.revision_path(rev, True), f"forecasts/blobs/{self.info['csv_original']}",
                       f"runs/{self.info['done'].run_uid}/manifest.json"):
            with self.subTest(victim=victim):
                rep = FMT.inspect(_rezip(self.pkg, lambda f: f.pop(victim)))
                self.assertFalse(rep.ok)
                self.assertTrue(any("ausente" in e for e in rep.errors), rep.errors)
                # mesmo removido também do manifesto: a dependência continua obrigatória
                def mut(f):
                    f.pop(victim)
                    _resign(f)
                rep = FMT.inspect(_rezip(self.pkg, mut))
                self.assertFalse(rep.ok, victim)

    def test_relacoes_inconsistentes_detectadas(self):
        ru = self.info["done"].run_uid

        def mut(f):
            row = json.loads(f[f"runs/{ru}/run.json"])
            row["scenario_version"] = 3                     # aponta para outra versão (impressão digital diferente)
            f[f"runs/{ru}/run.json"] = json.dumps(row).encode()
            _resign(f)
        rep = FMT.inspect(_rezip(self.pkg, mut))
        self.assertFalse(rep.ok)
        self.assertTrue(any(ru[:8] in e for e in rep.errors), rep.errors)

        def mut2(f):                                         # rodada falha com "resultados" inventados
            r2 = self.info["failed"].run_uid
            f[f"runs/{r2}/data/saidas/despacho_ems.csv"] = b"a,b\n1,2\n"
            row = json.loads(f[f"runs/{r2}/run.json"])
            row["data"] = {"saidas/despacho_ems.csv": {"sha256": sha256(b"a,b\n1,2\n").hexdigest(), "size": 8,
                                                         "media_type": "text/csv"}}
            f[f"runs/{r2}/run.json"] = json.dumps(row).encode()
            _resign(f)
        rep = FMT.inspect(_rezip(self.pkg, mut2))
        self.assertFalse(rep.ok)
        self.assertTrue(any("não concluída com dados" in e for e in rep.errors), rep.errors)


# =========================================================================== C-03: relações históricas completas
def _jmut(path: str, fn):
    """Mutação de um JSON do pacote + manifesto recalculado (recursos íntegros, hashes coerentes, relação contraditória)."""
    def mut(f):
        obj = json.loads(f[path])
        fn(obj)
        f[path] = json.dumps(obj).encode()
        _resign(f)
    return mut


def _mmut(fn):
    """Mutação do próprio manifesto (ex.: índice de dependências), sem tocar nos recursos."""
    def mut(f):
        m = json.loads(f["manifest.json"])
        fn(m)
        f["manifest.json"] = json.dumps(m).encode()
    return mut


class RelacoesC03Test(_Base):
    """Auditoria C-03: identidade das rodadas e grafo de dependências contrastados com os recursos verificados."""

    def _bad(self, mutate, fragment: str) -> None:
        rep = FMT.inspect(_rezip(self.pkg, mutate))
        self.assertFalse(rep.ok, "pacote contraditório aceito")
        self.assertTrue(any(fragment in e for e in rep.errors), rep.errors)
        with self.assertRaises(StudyRejected):
            self.archive.import_package(_rezip(self.pkg, mutate))
        self.assertEqual(self.archive.list_studies(), [])

    def _good(self, mutate) -> None:
        rep = FMT.inspect(_rezip(self.pkg, mutate))
        self.assertTrue(rep.ok, rep.errors)

    @property
    def ru(self) -> str:
        return self.info["done"].run_uid

    def test_pacote_autentico_continua_aceito_e_dependencias_reconstruidas(self):
        rep = FMT.inspect(self.pkg)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(set(self.man["dependencies"]["runs"]), set(self.man["study"]["runs"]))
        self._good(lambda f: None)                                         # reempacotar sem mudanças: aceito

    def test_1_rodada_atribuida_a_outra_microrrede(self):
        self._bad(_jmut(f"runs/{self.ru}/run.json", lambda r: r.update(microgrid_uid="c" * 32)), "outra microrrede")

    def test_2_incarnacao_contraditoria_quando_ambas_declaradas(self):
        self.assertIsNotNone(self.man["study"]["origin"]["microgrid_incarnation"])
        self._bad(_jmut(f"runs/{self.ru}/run.json", lambda r: r.update(incarnation="d" * 32)), "incarnação")
        self._bad(_jmut(f"runs/{self.ru}/manifest.json",
                        lambda m: m["reference"].update(microgrid_incarnation="d" * 32)), "incarnação")

    def test_incarnacao_nao_registrada_em_dados_herdados_nao_e_conflito(self):
        def legacy(f):
            for ru in self.man["study"]["runs"]:
                r = json.loads(f[f"runs/{ru}/run.json"])
                r["incarnation"] = None
                f[f"runs/{ru}/run.json"] = json.dumps(r).encode()
                mm = json.loads(f[f"runs/{ru}/manifest.json"])
                mm["reference"]["microgrid_incarnation"] = None
                f[f"runs/{ru}/manifest.json"] = json.dumps(mm).encode()
            _resign(f)
        self._good(legacy)                                                 # None = não registrado: aceito

        def no_origin(f):
            m = json.loads(f["manifest.json"])
            m["study"]["origin"]["microgrid_incarnation"] = None
            f["manifest.json"] = json.dumps(m).encode()
        self._good(no_origin)

    def test_3_revisao_ou_impressao_do_manifesto_da_rodada_diferente_do_registro(self):
        self._bad(_jmut(f"runs/{self.ru}/manifest.json", lambda m: m["reference"].update(config_revision=2)),
                  "config_revision")
        self._bad(_jmut(f"runs/{self.ru}/manifest.json", lambda m: m["reference"].update(config_fingerprint="e" * 64)),
                  "config_fingerprint")
        # registro e manifesto coerentes entre si, mas a revisão difere da referenciada pela versão executada

        def both(f):
            for path in (f"runs/{self.ru}/run.json",):
                r = json.loads(f[path])
                r["config_fingerprint"] = "e" * 64
                f[path] = json.dumps(r).encode()
            mm = json.loads(f[f"runs/{self.ru}/manifest.json"])
            mm["reference"]["config_fingerprint"] = "e" * 64
            f[f"runs/{self.ru}/manifest.json"] = json.dumps(mm).encode()
            _resign(f)
        self._bad(both, "revisão do inventário")

    def test_4_referencia_de_cenario_contraditoria(self):
        self._bad(_jmut(f"runs/{self.ru}/manifest.json", lambda m: m["reference"].update(microgrid_uid="c" * 32)),
                  "outra microrrede")
        self._bad(_jmut(f"runs/{self.ru}/manifest.json", lambda m: m["reference"].update(scenario_uid="f" * 32)),
                  "scenario_uid")
        self._bad(_jmut(f"runs/{self.ru}/manifest.json", lambda m: m["reference"].update(scenario_version=3)),
                  "scenario_version")

    def test_5_dependencia_de_versao_aponta_para_outra_revisao(self):
        """Estudo com DUAS revisões reais do inventário: a dependência da versão rebaseada é trocada pela outra."""
        tmp = tempfile.TemporaryDirectory()
        try:
            reg = MicrogridRegistry(tmp.name)
            cfg = v16_equivalent_config("Duas revisões")
            reg.create(cfg, origin="commissioning")
            st = reg.open(cfg["installation"]["uid"])
            sc = ready(st, name="Rebaseado")
            cur = st.load()
            c2 = copy.deepcopy(cur.config)
            c2["equipment"][0]["name"] = "Arranjo renomeado"
            st.save(c2, cur.revision)
            sc3 = service.rebase(st, sc.scenario_uid, sc.version)
            pkg, man = exporter.export_bytes(st, sc.scenario_uid)
        finally:
            tmp.cleanup()
        self.assertEqual(man["study"]["inventory_revisions"], [1, 2])
        self.assertTrue(FMT.inspect(pkg).ok)
        v = str(sc3.version)
        self.assertEqual(man["dependencies"]["versions"][v]["inventory_revision"], FMT.revision_path(2, True))
        bad = _rezip(pkg, _mmut(lambda m: m["dependencies"]["versions"][v].update(
            inventory_revision=FMT.revision_path(1, True))))
        rep = FMT.inspect(bad)
        self.assertFalse(rep.ok)
        self.assertTrue(any(f"versions/{v} alterada" in e for e in rep.errors), rep.errors)

    def test_6_dependencia_aponta_para_blob_diferente(self):
        other = f"forecasts/blobs/{self.info['csv_original']}"            # blob existente, mas de outra versão
        self._bad(_mmut(lambda m: m["dependencies"]["versions"]["2"]["forecasts"].__setitem__(0, other)),
                  "versions/2 alterada")
        self._bad(_mmut(lambda m: m["dependencies"]["inventory_revisions"]["1"]["blobs"].append(other)),
                  "inventory_revisions/1 alterada")

    def test_7_dependencia_de_rodada_omite_ou_acrescenta_arquivo(self):
        ru, other = self.ru, self.info["failed"].run_uid
        self._bad(_mmut(lambda m: m["dependencies"]["runs"][ru]["files"].pop()), f"runs/{ru[:40]} alterada")
        self._bad(_mmut(lambda m: m["dependencies"]["runs"][ru]["files"].append(f"runs/{other}/run.json")),
                  f"runs/{ru[:40]} alterada")
        self._bad(_mmut(lambda m: m["dependencies"]["runs"][ru].update(scenario_version=FMT.version_path(3, True))),
                  "alterada")
        self._bad(_mmut(lambda m: m["dependencies"]["runs"].__setitem__("a" * 32, {"files": []})), "inexistente")
        self._bad(_mmut(lambda m: m["dependencies"]["versions"].pop("1")), "versions/1 ausente")
        self._bad(_mmut(lambda m: m.pop("dependencies")), "dependências ausente")


# =========================================================================== segurança do importador
def _zip(entries: list[tuple], **kw) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for e in entries:
            if isinstance(e[0], zipfile.ZipInfo):
                z.writestr(e[0], e[1])
            else:
                z.writestr(e[0], e[1])
    return buf.getvalue()


class SegurancaTest(_Base):
    def _rejected(self, data: bytes, fragment: str) -> None:
        rep = FMT.inspect(data)
        self.assertFalse(rep.ok)
        self.assertTrue(any(fragment.lower() in e.lower() for e in rep.errors), rep.errors)
        with self.assertRaises(StudyRejected):
            self.archive.import_package(data)
        self.assertEqual(self.archive.list_studies(), [])

    def test_zip_slip_caminhos_absolutos_e_inesperados(self):
        man = self.pkg and zipfile.ZipFile(io.BytesIO(self.pkg)).read("manifest.json")
        for evil in ("../../etc/passwd", "/etc/passwd", "runs/../../x.json", "C:\\evil.json", "forecasts/blobs/../../a",
                     "scenario/versions/v000001.json/", "notas.txt", "runs/" + "a" * 32 + "/data/../../x.csv",
                     "runs/" + "a" * 32 + "/data/.hidden.csv", "script.py"):
            with self.subTest(evil=evil):
                self._rejected(_zip([("manifest.json", man), (evil, b"{}")]), "não permitidas")

    def test_link_simbolico_e_entrada_duplicada(self):
        man = zipfile.ZipFile(io.BytesIO(self.pkg)).read("manifest.json")
        info = zipfile.ZipInfo("scenario/scenario.json")
        info.external_attr = (0o120777 << 16)
        self._rejected(_zip([("manifest.json", man), (info, b"/etc/passwd")]), "link simbólico")
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dup = _zip([("manifest.json", man), ("scenario/scenario.json", b"{}"), ("scenario/scenario.json", b"{}")])
        self._rejected(dup, "duplicadas")
        self._rejected(_zip([("manifest.json", man), ("Scenario/Scenario.json", b"{}"), ("scenario/scenario.json", b"{}")]),
                       "")

    def test_conteudo_executavel_recusado(self):
        p = "inventory/catalog_references.json"

        def mut(f):
            f[p] = b"\x7fELF\x02\x01\x01" + b"\x00" * 64
            _resign(f)
        self._rejected(_rezip(self.pkg, mut), "executável")

        def pe(f):
            f[p] = b"MZ\x90\x00\x03" + b"\x00" * 64                 # cabeçalho PE (Windows)
            _resign(f)
        self._rejected(_rezip(self.pkg, pe), "executável")
        self.assertFalse(FMT._executable(b"MZ_kW;demanda\n"))           # CSV cujo cabeçalho começa por "MZ": aceito

    def test_json_invalido_aninhado_ou_com_chave_duplicada(self):
        for payload, frag in ((b"{" * 5000, "json"), (b'{"a": 1, "a": 2}', "duplicada"),
                              (b"[" * 150 + b"]" * 150, "aninhado"), (b"\xff\xfe", "json")):
            with self.subTest(frag=frag):
                self._rejected(_zip([("manifest.json", payload)]), frag)

    def test_bomba_zip_e_limites(self):
        man = zipfile.ZipFile(io.BytesIO(self.pkg)).read("manifest.json")
        info = zipfile.ZipInfo("inventory/blobs/" + "0" * 64)
        info.compress_type = zipfile.ZIP_DEFLATED
        self._rejected(_zip([("manifest.json", man), (info, b"\0" * (8 * 1024 * 1024))]), "bomba")
        with mock.patch.object(FMT, "MAX_TOTAL_UNCOMPRESSED", 64 * 1024):
            self._rejected(self.pkg, "limite total")
        with mock.patch.object(FMT, "MAX_PACKAGE_BYTES", 1024):
            self._rejected(self.pkg, "grande demais")
        with mock.patch.object(FMT, "MAX_ENTRIES", 5):
            self._rejected(self.pkg, "entradas demais")
        with mock.patch.object(FMT, "MAX_ENTRY_BYTES", 1024):
            self._rejected(self.pkg, "tamanho permitido")

    def test_formatos_e_versoes_incompativeis(self):
        def fv(v):
            def mut(f):
                m = json.loads(f["manifest.json"])
                m["format_version"] = v
                f["manifest.json"] = json.dumps(m).encode()
            return mut
        self._rejected(_rezip(self.pkg, fv(2)), "mais novo")
        self._rejected(_rezip(self.pkg, fv("1")), "versão do formato")
        backup = self.store.export_backup()
        self._rejected(backup, "")                         # backup da microrrede ≠ arquivo científico
        self.assertFalse(FMT.inspect(backup).ok)
        self._rejected(b"isto nao e um zip", "zip válido")
        self._rejected(_zip([("scenario/scenario.json", b"{}")]), "manifest.json")

    def test_nada_e_extraido_no_diretorio_de_dados(self):
        before = sorted(str(p.relative_to(self.dest)) for p in Path(self.dest).rglob("*"))
        self.archive.import_package(self.pkg)
        after = sorted(str(p.relative_to(self.dest)) for p in Path(self.dest).rglob("*"))
        self.assertTrue(all(p.startswith("scientific_archive") for p in after), after)
        self.assertFalse(any(p.endswith((".csv", ".json")) for p in after), after)
        self.assertLessEqual(set(before), set(after))


# =========================================================================== importação, identidade e persistência
class ImportacaoTest(_Base):
    def test_instalacao_limpa_reabre_em_novo_processo_sem_executar_o_ems(self):
        res = self.archive.import_package(self.pkg)
        self.assertTrue(res.created)
        self.assertEqual(sorted(os.listdir(self.dest)), ["scientific_archive"])   # nenhuma microrrede criada
        code = (
            "import sys, json\n"
            "import orchestrator_runtime as RT\n"
            "def boom(*a, **k): raise SystemExit('OTIMIZADOR CHAMADO')\n"
            "RT.run_optimizer = boom; RT.build_exchange_package = boom\n"
            "from seeds2.archive.store import ArchiveStore\n"
            "from seeds2.archive.view import StudyView\n"
            f"a = ArchiveStore({self.dest!r})\n"
            "s = a.list_studies()[0]\n"
            "v = StudyView(a, s.archive_uid)\n"
            "ok, probs = a.verify(s.archive_uid)\n"
            "out = {'ok': ok, 'uid': s.archive_uid, 'runs': {}}\n"
            "for r in v.list_runs():\n"
            "    out['runs'][r.run_uid] = {'state': r.state, 'summary': r.summary,\n"
            "        'data': {n: __import__('hashlib').sha256(v.run_data(r.run_uid, n)).hexdigest() for n in r.data}}\n"
            "print(json.dumps(out))\n")
        env = {**os.environ, "PYTHONPATH": str(RAIZ), "PYTHONDONTWRITEBYTECODE": "1"}
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(RAIZ), env=env, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertTrue(out["ok"])
        self.assertEqual(out["uid"], res.study.archive_uid)
        done = self.info["done"]
        self.assertEqual(out["runs"][done.run_uid]["summary"], done.summary)
        self.assertEqual(out["runs"][done.run_uid]["data"], {n: d["sha256"] for n, d in done.data.items()})

    def test_identidade_de_origem_e_identidade_local_distintas(self):
        res = self.archive.import_package(self.pkg, context={"microgrid_uid": "b" * 32, "name": "Destino"})
        s = res.study
        o = self.man["study"]["origin"]
        self.assertNotEqual(s.archive_uid, o["scenario_uid"])
        self.assertEqual((s.origin_microgrid_uid, s.origin_scenario_uid, s.origin_microgrid_name),
                         (o["microgrid_uid"], o["scenario_uid"], "Industrial A"))
        self.assertEqual(s.origin_incarnation, self.store.incarnation or s.origin_incarnation)
        self.assertEqual(s.context_microgrid_uid, "b" * 32)
        v = StudyView(self.archive, s.archive_uid)
        run = v.get_run(self.info["done"].run_uid)
        self.assertEqual(run.microgrid_uid, o["microgrid_uid"])                     # atribuída à origem
        self.assertEqual(run.manifest, self.info["done"].manifest)                   # manifesto intocado
        self.assertEqual(v.version_meta(2)["fingerprint"], self.store.get_scenario(self.info["scenario_uid"], 2).fingerprint)
        self.assertEqual(s.manifest_text, zipfile.ZipFile(io.BytesIO(self.pkg)).read("manifest.json").decode())

    def test_reimportar_o_mesmo_arquivo(self):
        a = self.archive.import_package(self.pkg)
        b = self.archive.import_package(self.pkg)
        self.assertFalse(b.created)
        self.assertEqual(b.study.archive_uid, a.study.archive_uid)
        self.assertEqual(len(self.archive.list_studies()), 1)
        c = self.archive.import_package(self.pkg, on_duplicate="copy")
        self.assertTrue(c.created)
        self.assertEqual(c.study.copy_of, a.study.archive_uid)
        self.assertNotEqual(c.study.archive_uid, a.study.archive_uid)
        self.assertEqual(c.study.origin_scenario_uid, a.study.origin_scenario_uid)
        # nova exportação do mesmo conteúdo (outra data) = mesmo conteúdo (reconhecido)
        again, _ = exporter.export_bytes(self.store, self.info["scenario_uid"])
        self.assertEqual(FMT.inspect(again).content_id, a.study.content_id)
        self.assertFalse(self.archive.import_package(again).created)
        self.assertTrue(self.archive.verify(c.study.archive_uid)[0])

    def test_dois_estudos_com_identificadores_de_origem_coincidentes(self):
        first = self.archive.import_package(self.pkg)
        # mesmo cenário de origem, conteúdo diferente (nova versão gravada depois da 1ª exportação)
        tmp = tempfile.TemporaryDirectory()
        try:
            reg = MicrogridRegistry(tmp.name)
            cfg = v16_equivalent_config("Industrial A")
            reg.create(cfg, origin="commissioning")
            st = reg.open(cfg["installation"]["uid"])
            sc = ready(st, name="Alta demanda")
            data1, _ = exporter.export_bytes(st, sc.scenario_uid)
            edit(st, sc, lambda d: d.update(description="ajuste"))
            data2, _ = exporter.export_bytes(st, sc.scenario_uid)
        finally:
            tmp.cleanup()
        r1, r2 = self.archive.import_package(data1), self.archive.import_package(data2)
        self.assertTrue(r1.created and r2.created)
        self.assertEqual(r1.study.origin_scenario_uid, r2.study.origin_scenario_uid)
        self.assertNotEqual(r1.study.archive_uid, r2.study.archive_uid)
        self.assertEqual((r1.study.n_versions, r2.study.n_versions), (2, 3))
        self.assertEqual(len(self.archive.find_by_origin(r1.study.origin_scenario_uid)), 2)
        self.assertEqual(self.archive.get_study(first.study.archive_uid).n_runs, 3)     # nada sobrescrito

    def test_estudo_arquivado_e_somente_leitura(self):
        s = self.archive.import_package(self.pkg).study
        con = sqlite3.connect(self.archive.path)
        try:
            for sql in ("UPDATE studies SET scenario_name = 'x'", "DELETE FROM studies",
                        "UPDATE study_resources SET sha256 = 'x'", "DELETE FROM study_resources",
                        "UPDATE archive_blobs SET size = 0", "DELETE FROM archive_blobs"):
                with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                    con.execute(sql)
        finally:
            con.close()
        self.assertTrue(self.archive.verify(s.archive_uid)[0])

    def test_corrupcao_no_arquivo_local_detectada_na_leitura(self):
        s = self.archive.import_package(self.pkg).study
        con = sqlite3.connect(self.archive.path)
        try:
            con.execute("DROP TRIGGER archive_blobs_immutable_u")              # simula dano no disco
            h = next(r["sha256"] for r in self.archive.resources(s.archive_uid) if r["path"].endswith("despacho_ems.csv"))
            con.execute("UPDATE archive_blobs SET content = zeroblob(10), encoding = 'identity' WHERE sha256 = ?", (h,))
            con.commit()
        finally:
            con.close()
        ok, problems = self.archive.verify(s.archive_uid)
        self.assertFalse(ok)
        self.assertTrue(any("despacho_ems" in p for p in problems), problems)
        with self.assertRaises(ArchiveError):
            StudyView(self.archive, s.archive_uid).run_data(self.info["done"].run_uid, "saidas/despacho_ems.csv")

    def test_banco_do_arquivo_mais_novo_e_recusado_sem_alteracao(self):
        con = sqlite3.connect(self.archive.path)
        con.execute("PRAGMA user_version = 99")
        con.close()
        digest = sha256(self.archive.path.read_bytes()).hexdigest()
        with self.assertRaises(ArchiveError):
            ArchiveStore(self.dest)
        self.assertEqual(sha256(self.archive.path.read_bytes()).hexdigest(), digest)


class AtomicidadeTest(_Base):
    def test_erro_durante_a_importacao_desfaz_tudo(self):
        calls = {"n": 0}
        orig = ArchiveStore._insert_resource

        def flaky(con, *a, **k):
            calls["n"] += 1
            if calls["n"] == 7:
                raise sqlite3.OperationalError("disco cheio (simulado)")
            return orig(con, *a, **k)
        with mock.patch.object(ArchiveStore, "_insert_resource", staticmethod(flaky)):
            with self.assertRaises(ArchiveError):
                self.archive.import_package(self.pkg)
        con = sqlite3.connect(self.archive.path)
        try:
            self.assertEqual([con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                              for t in ("studies", "study_resources", "archive_blobs")], [0, 0, 0])
        finally:
            con.close()
        self.assertTrue(self.archive.import_package(self.pkg).created)            # repetir funciona

    def test_arquivo_alterado_entre_inspecao_e_importacao(self):
        rep = FMT.inspect(self.pkg)
        other, _ = exporter.export_bytes(self.store, self.info["empty"].scenario_uid)
        with self.assertRaises(ArchiveError):
            self.archive.import_package(other, expected_content_id=rep.content_id)
        self.assertEqual(self.archive.list_studies(), [])

    def test_processo_morto_no_meio_da_importacao(self):
        pkg = Path(self.dest) / f"estudo{FMT.SUFFIX}"
        pkg.write_bytes(self.pkg)
        code = (
            "import os\n"
            "from seeds2.archive.store import ArchiveStore\n"
            "orig = ArchiveStore._insert_resource\n"
            "n = [0]\n"
            "def die(con, *a, **k):\n"
            "    n[0] += 1\n"
            "    if n[0] == 12: os._exit(9)\n"
            "    return orig(con, *a, **k)\n"
            "ArchiveStore._insert_resource = staticmethod(die)\n"
            f"ArchiveStore({self.dest!r}).import_package({str(pkg)!r})\n")
        env = {**os.environ, "PYTHONPATH": str(RAIZ), "PYTHONDONTWRITEBYTECODE": "1"}
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(RAIZ), env=env, timeout=120)
        self.assertEqual(p.returncode, 9, p.stderr[-2000:])
        a = ArchiveStore(self.dest)
        self.assertEqual(a.list_studies(), [])
        con = sqlite3.connect(a.path)
        try:
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(con.execute("SELECT COUNT(*) FROM archive_blobs").fetchone()[0], 0)
        finally:
            con.close()
        res = a.import_package(pkg)
        self.assertTrue(res.created)
        self.assertTrue(a.verify(res.study.archive_uid)[0])


class IsolamentoTest(_Base):
    def test_importar_e_arquivar_nao_tocam_microrredes(self):
        reg = MicrogridRegistry(self.dest)
        cfg = v16_equivalent_config("Destino B")
        reg.create(cfg, origin="commissioning")
        dst = reg.open(cfg["installation"]["uid"])
        service.create(dst, name="Cenário local de B")
        before = (_dump(dst), sha256(dst.path.read_bytes()).hexdigest(), dst.load().revision,
                  sha256(reg.path.read_bytes()).hexdigest())
        res = self.archive.import_package(self.pkg, context={"microgrid_uid": cfg["installation"]["uid"],
                                                             "incarnation": dst.incarnation, "name": "Destino B"})
        after = (_dump(dst), sha256(dst.path.read_bytes()).hexdigest(), dst.load().revision,
                 sha256(reg.path.read_bytes()).hexdigest())
        self.assertEqual(after, before)                                   # inventário, cenários e rodadas intactos
        self.assertEqual([s.name for s in dst.list_scenarios()], ["Cenário local de B"])
        self.assertEqual(dst.list_runs(), [])
        self.assertEqual(len(reg.entries()), 1)                            # nenhuma microrrede criada/restaurada
        self.assertEqual(res.study.context_microgrid_uid, cfg["installation"]["uid"])
        # a origem também fica intacta ao arquivar localmente
        src_before = _dump(self.store)
        loc = AS.archive_scenario(self.store, self.archive, self.info["scenario_uid"])
        self.assertFalse(loc.created)                                     # mesmo conteúdo já arquivado
        self.assertEqual(_dump(self.store), src_before)

    def test_estudo_sobrevive_a_exclusao_da_microrrede_de_contexto(self):
        reg = MicrogridRegistry(self.dest)
        cfg = v16_equivalent_config("Contexto")
        reg.create(cfg, origin="commissioning")
        s = AS.archive_scenario(self.store, self.archive, self.info["empty"].scenario_uid,
                                context={"microgrid_uid": cfg["installation"]["uid"]}).study
        reg.delete(cfg["installation"]["uid"], expected_incarnation=reg.get(cfg["installation"]["uid"]).incarnation)
        self.assertEqual(reg.entries(), [])
        self.assertEqual(self.archive.get_study(s.archive_uid).acquisition, "arquivado")
        self.assertTrue(self.archive.verify(s.archive_uid)[0])


# =========================================================================== prova científica (rodada real)
class ProvaCientificaTest(_Base):
    def test_rodada_real_exportada_importada_e_reaberta_sem_recomputacao(self):
        done = self.info["done"]
        out0 = runner.load_csv(self.store, done.run_uid, "saidas/despacho_ems.csv")
        inp0 = runner.load_csv(self.store, done.run_uid, "entradas/missao.csv")
        res = self.archive.import_package(self.pkg)
        with mock.patch.object(RT, "run_optimizer", side_effect=AssertionError("o otimizador NÃO pode ser chamado")), \
                mock.patch.object(RT, "build_exchange_package", side_effect=AssertionError("modelos NÃO podem rodar")):
            v = StudyView(ArchiveStore(self.dest), res.study.archive_uid)          # "reiniciado": nova instância
            run = v.get_run(done.run_uid)
            out = runner.load_csv(v, run.run_uid, "saidas/despacho_ems.csv")
            inp = runner.load_csv(v, run.run_uid, "entradas/missao.csv")
            for e in v.version_document(2)["forecasts"].values():
                F.load(e, v.get_blob)
        s0, s = done.summary, run.summary
        self.assertEqual(s["custo_total_rs"], s0["custo_total_rs"])                 # custo
        self.assertAlmostEqual(s["custo_total_rs"], 88.3190884544543, places=10)   # = rodada 2C de referência (V1.6)
        for k in ("energia_demanda_kWh", "energia_atendida_kWh", "energia_nao_atendida_kWh", "energia_solar_kWh",
                  "energia_por_fonte_kWh", "soc_final", "h2_kg", "custo_por_fonte_rs"):
            self.assertEqual(s[k], s0[k], k)                                         # energia, SOC, H₂
        pd.testing.assert_frame_equal(out, out0, check_exact=True)                   # potências por fonte, SOC, timestamps
        pd.testing.assert_frame_equal(inp, inp0, check_exact=True)
        for col in [c for c in out.columns if c.startswith("P_") or c.startswith("SOC_")] + ["h2_kg"]:
            np.testing.assert_array_equal(out[col].to_numpy(), out0[col].to_numpy())
        self.assertEqual(list(out["timestamp_utc"]), list(out0["timestamp_utc"]))
        self.assertEqual((run.run_uid, run.scenario_uid, run.microgrid_uid, run.scenario_fingerprint),
                         (done.run_uid, done.scenario_uid, done.microgrid_uid, done.scenario_fingerprint))
        self.assertEqual({n: d["sha256"] for n, d in run.data.items()}, {n: d["sha256"] for n, d in done.data.items()})
        self.assertEqual(run.manifest["software"]["science"], done.manifest["software"]["science"])

    def test_ems_v16_inalterado(self):
        """O motor V1.6 e o código científico não foram tocados: a impressão digital científica gravada pela rodada
        de origem é a do código atual, e uma nova execução da mesma versão reproduz o custo."""
        self.assertEqual(self.info["done"].manifest["software"]["science"]["sha256"], runner.science_fingerprint()["sha256"])
        pf = runner.prepare(self.store, self.info["scenario_uid"], 2)
        self.assertTrue(pf.ok)
        r = runner.submit(self.store, self.info["scenario_uid"], 2, runner.new_request_id(), background=False)
        try:
            self.assertEqual(r.summary["custo_total_rs"], self.info["done"].summary["custo_total_rs"])
        finally:
            _Fixture._done = None                                                    # a origem ganhou uma rodada


if __name__ == "__main__":
    unittest.main()
