"""Gestor de microrredes (catálogo + um armazenamento por microrrede) — backend, sem Streamlit.

Cobre: catálogo vazio, criação de várias, reabertura em novo processo, ISOLAMENTO (equipamentos, revisões,
blobs, rodadas), exportação/relatório sem abrir a microrrede, importação (nova, cópia independente,
restauração, duplicadas), exclusão definitiva com recuperação de interrupções, caminhos seguros, adoção do
armazenamento anterior ao Gestor (v1 e v2, WAL com leitor aberto, interrupção, concorrência, arquivo
corrompido), compatibilidade com backups formato 1 e 2, proteção da exclusão e rodada EMS real por
microrrede com procedência ligada à identidade.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import numpy as np

from seeds2.microgrid import adapter as A
from seeds2.microgrid import config as C
from seeds2.microgrid import registry as R
from seeds2.microgrid.admin import DeletionPolicy, deletion_policy
from seeds2.microgrid.registry import (LegacyAdoptionError, MicrogridNotFound, MicrogridRegistry, RegistryError,
                                       card_summary)
from seeds2.microgrid.store import IdentityError, MicrogridDeletedError, MicrogridStore, StoreError, backup_filename
from seeds2_fixtures import V1_BACKUP, V1_CONFIG, battery_params, module_array, pv_plant, v16_equivalent_config

RAIZ = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _db_snapshot(store: MicrogridStore) -> dict:
    """Conteúdo LÓGICO completo de um armazenamento (para provar que outra microrrede não o alterou)."""
    con = sqlite3.connect(store.path)
    try:
        return {t: con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()
                for t in ("microgrid", "revisions", "blobs", "simulation_runs")}
    finally:
        con.close()


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.dir = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def reg(self) -> MicrogridRegistry:
        return MicrogridRegistry(self.dir)

    def make(self, reg: MicrogridRegistry, name: str, cfg: dict | None = None) -> str:
        cfg = cfg or v16_equivalent_config(name)
        reg.create(cfg)
        return cfg["installation"]["uid"]


# =========================================================================== catálogo
class CatalogoTest(_Tmp):
    def test_inicio_sem_microrredes(self):                               # requisito 1
        reg = self.reg()
        self.assertEqual(reg.entries(), [])
        self.assertTrue(reg.path.is_file())
        self.assertEqual(list(reg.microgrids_dir.iterdir()), [])
        self.assertFalse((self.dir / "seeds2.db").exists())               # nada é criado automaticamente
        self.assertIsNone(reg.meta("legacy_adoption"))

    def test_criar_varias_e_listar_apos_reinicio_em_novo_processo(self):  # requisitos 2–4
        reg = self.reg()
        uids = [self.make(reg, n) for n in ("Solar residencial", "Híbrida experimental", "Demonstração")]
        self.assertEqual(len(set(uids)), 3)
        for uid in uids:
            d = reg.dir_for(uid)
            self.assertEqual(d.parent, reg.microgrids_dir)
            self.assertTrue((d / "seeds2.db").is_file())
        code = ("import sys; from seeds2.microgrid.registry import MicrogridRegistry as R; r = R(sys.argv[1]); "
                "print('|'.join(sorted(e.uid + ':' + r.open(e.uid).load().config['installation']['name'] for e in r.entries())))")
        out = subprocess.run([sys.executable, "-c", code, str(self.dir)], cwd=RAIZ, capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        listed = dict(x.split(":", 1) for x in out.stdout.strip().split("|"))
        self.assertEqual(set(listed), set(uids))
        self.assertIn("Demonstração", listed.values())

    def test_nomes_repetidos_sao_permitidos_e_distinguidos_pelo_uid(self):
        reg = self.reg()
        a, b = self.make(reg, "Laboratório"), self.make(reg, "Laboratório")
        self.assertNotEqual(a, b)
        self.assertNotEqual(backup_filename(reg.open(a).load().config), backup_filename(reg.open(b).load().config))
        self.assertIn(a[:8], backup_filename(reg.open(a).load().config))

    def test_identidade_duplicada_e_recusada(self):
        reg = self.reg()
        cfg = v16_equivalent_config("X")
        reg.create(cfg)
        with self.assertRaises(RegistryError):
            reg.create(copy.deepcopy(cfg))
        self.assertEqual(len(reg.entries()), 1)

    def test_resumo_do_cartao_distingue_declarado_e_calculado(self):
        reg = self.reg()
        cfg = C.new_config("Usina")
        cfg["installation"].update(nature="comercial", operation_mode="conectada")
        C.add_equipment(cfg, pv_plant("FV", module_array(ns=2, np_=3),
                                      C.new_array("Decl", mode="declarado", declared_kWp=2.2, declared_source="projeto")))
        C.add_equipment(cfg, C.new_equipment("battery", "Banco", params={"energy_kWh": 50.0}))
        reg.create(cfg)
        s = card_summary(reg.open(cfg["installation"]["uid"]).load())
        self.assertAlmostEqual(s["pv_computed_kWp"], 3.54)
        self.assertAlmostEqual(s["pv_declared_kWp"], 2.2)
        self.assertAlmostEqual(s["pv_kWp"], 5.74)
        self.assertIsNone(s["wind_kW"])                                    # nada inventado
        self.assertEqual((s["storage_kWh"], s["storage_basis"]), (50.0, ["declarada"]))
        self.assertEqual(s["state"], "configuracao")
        self.assertEqual(s["ems"][0], "bloqueada")                         # ativação ≠ pronta para simulação
        v16 = v16_equivalent_config("V16")
        reg.create(v16)
        s2 = card_summary(reg.open(v16["installation"]["uid"]).load())
        self.assertEqual((s2["state"], s2["ems"][0]), ("ativa", "pronta"))
        self.assertEqual(s2["storage_basis"], ["modelo"])


# =========================================================================== isolamento
class IsolamentoTest(_Tmp):
    def test_equipamentos_revisoes_blobs_e_rodadas_isolados(self):        # requisitos 5–7
        reg = self.reg()
        a, b = self.make(reg, "A"), self.make(reg, "B")
        sa, sb = reg.open(a), reg.open(b)
        before_b = _db_snapshot(sb)
        cfg = copy.deepcopy(sa.load().config)
        C.add_equipment(cfg, C.new_equipment("wind", "Aerogerador A", params={"reference": "EWT DW61-1MW", "count": 1}))
        h = sa.put_blob(b"t_min,P_kW\n0,1\n1,2\n", "a.csv")
        cfg["demand"].update(source="csv", provenance="medido",
                             csv={"blob": h, "filename": "a.csv", "start_min": 0, "duration_min": 2})
        sa.save(cfg, 1)
        sa.record_run(config_revision=2, config_fingerprint="f" * 64, spec_fingerprint="s" * 64, spec_origin="microrrede",
                      excluded=[], summary={"microgrid_uid": a})
        self.assertEqual(_db_snapshot(sb), before_b)
        self.assertEqual(len(sb.load().config["equipment"]), 6)
        self.assertEqual(len(sa.load().config["equipment"]), 7)
        self.assertEqual((sa.load().revision, sb.load().revision), (2, 1))
        self.assertEqual((len(sa.runs()), len(sb.runs())), (1, 0))
        with self.assertRaises(StoreError):
            sb.get_blob(h)                                                 # blob de A inexistente em B

    def test_restaurar_reverter_e_excluir_A_nao_alteram_B(self):         # requisito 17
        reg = self.reg()
        a, b = self.make(reg, "A"), self.make(reg, "B")
        snap_b = _db_snapshot(reg.open(b))
        files_b = {p.name: _sha(p) for p in reg.dir_for(b).iterdir() if p.is_file() and p.suffix == ".db"}
        sa = reg.open(a)
        z = sa.export_backup()
        cfg = copy.deepcopy(sa.load().config)
        cfg["installation"]["description"] = "editada"
        sa.save(cfg, 1)
        reg.restore_into(a, z, 2)
        sa.revert_to(2, 3)
        reg.delete(a)
        self.assertEqual(_db_snapshot(reg.open(b)), snap_b)
        self.assertEqual({p.name: _sha(p) for p in reg.dir_for(b).iterdir() if p.is_file() and p.suffix == ".db"}, files_b)
        self.assertEqual([e.uid for e in reg.entries()], [b])

    def test_armazenamento_do_catalogo_recusa_documento_de_outra_microrrede(self):
        reg = self.reg()
        a, b = self.make(reg, "A"), self.make(reg, "B")
        other = reg.open(b).load().config
        with self.assertRaises(IdentityError):
            reg.open(a).save(other, 1, allow_identity_change=True)       # nem com a confirmação antiga
        with self.assertRaises(RegistryError):
            reg.restore_into(a, reg.open(b).export_backup(), 1)
        self.assertEqual(reg.open(a).load().config["installation"]["uid"], a)


# =========================================================================== exportação / relatório / importação
class ExportacaoImportacaoTest(_Tmp):
    def test_zip_contem_somente_a_microrrede_escolhida(self):            # requisito 12
        reg = self.reg()
        a, b = self.make(reg, "A"), self.make(reg, "B")
        hb = reg.open(b).put_blob(b"t_min,P_kW\n0,9\n", "b.csv")
        cfg_b = copy.deepcopy(reg.open(b).load().config)
        cfg_b["demand"].update(source="csv", provenance="medido", csv={"blob": hb, "filename": "b.csv", "start_min": 0, "duration_min": 1})
        reg.open(b).save(cfg_b, 1)
        z = reg.open(a).export_backup()
        with zipfile.ZipFile(io.BytesIO(z)) as zf:
            names = zf.namelist()
            manifest = json.loads(zf.read("manifest.json"))
        self.assertEqual(manifest["installation_uid"], a)
        self.assertNotIn(f"blobs/{hb}", names)
        self.assertNotIn(b, z.decode("latin-1"))

    def test_pdf_de_microrrede_nao_ativa_sem_abri_la(self):               # requisito 13
        from pypdf import PdfReader

        from seeds2.report.pdf import build_report

        reg = self.reg()
        cfg = v16_equivalent_config("Em configuração")
        cfg["commissioning"].update(completed=False, step=3, completed_at=None)
        reg.create(cfg)
        store = reg.open(cfg["installation"]["uid"])
        pdf = build_report(store.load(), store)
        text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn("PRELIMINAR", text)
        self.assertIn("Em configuração", text)
        self.assertIn(cfg["installation"]["uid"], text.replace("\n", ""))

    def test_importar_como_nova_preserva_identidade(self):                # requisito 14 (identidade do backup)
        src = self.reg()
        a = self.make(src, "Origem")
        z = src.open(a).export_backup()
        other = MicrogridRegistry(self.dir / "outra_instalacao")
        uid, stored = other.import_new(z)
        self.assertEqual(uid, a)
        self.assertEqual(stored.config, src.open(a).load().config)
        self.assertEqual(other.get(a).origin, "import")

    def test_importacao_duplicada_exige_escolha_explicita(self):         # requisitos 14–15
        reg = self.reg()
        a = self.make(reg, "A")
        z = reg.open(a).export_backup()
        rep, existing = reg.inspect(z)
        self.assertTrue(rep.ok)
        self.assertEqual(existing.uid, a)
        with self.assertRaises(RegistryError):
            reg.import_new(z)                                             # nunca sobrescreve silenciosamente
        self.assertEqual(len(reg.entries()), 1)
        # cópia independente: nova identidade + origem registrada
        new_uid, copy_st = reg.import_copy(z)
        self.assertNotEqual(new_uid, a)
        inst = copy_st.config["installation"]
        self.assertEqual(inst["uid"], new_uid)
        self.assertEqual(inst["copied_from"]["uid"], a)
        self.assertEqual(inst["copied_from"]["fingerprint"], reg.open(a).load().fingerprint)
        e = reg.get(new_uid)
        self.assertEqual((e.origin, e.source_uid), ("copy", a))
        self.assertEqual(C.errors(C.validate(copy_st.config)), [])
        # a cópia continua exportável e restaurável (em outro catálogo, como nova)
        z2 = reg.open(new_uid).export_backup()
        other = MicrogridRegistry(self.dir / "outro")
        uid2, _ = other.import_new(z2)
        self.assertEqual(uid2, new_uid)
        # restauração na existente: nova revisão, histórico preservado
        cfg = copy.deepcopy(reg.open(a).load().config)
        cfg["installation"]["description"] = "alterada"
        reg.open(a).save(cfg, 1)
        restored = reg.restore_into(a, z, 2)
        self.assertEqual(restored.revision, 3)
        self.assertEqual([h["origin"] for h in reg.open(a).history()][0], "restore")
        self.assertEqual(restored.config["installation"]["description"], v16_equivalent_config()["installation"]["description"])

    def test_backups_formato_1_e_2(self):                                 # requisito 22
        reg = self.reg()
        rep, existing = reg.inspect(V1_BACKUP.read_bytes())
        self.assertTrue(rep.ok, rep.errors)
        self.assertTrue(rep.migrated)
        self.assertIsNone(existing)
        uid, stored = reg.import_new(V1_BACKUP.read_bytes())
        self.assertEqual(stored.config["schema_version"], 2)
        v1 = json.loads(V1_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(uid, v1["installation"]["uid"])
        self.assertEqual(reg.open(uid).get_blob(v1["demand"]["csv"]["blob"])[:5], b"t_min")
        z2 = reg.open(uid).export_backup()                                # formato 2
        self.assertEqual(json.loads(zipfile.ZipFile(io.BytesIO(z2)).read("manifest.json"))["format_version"], 2)
        new_uid, _ = reg.import_copy(z2)
        self.assertEqual(len(reg.entries()), 2)
        self.assertNotEqual(new_uid, uid)

    def test_backup_invalido_e_rejeitado_sem_criar_entrada(self):
        reg = self.reg()
        for bad in (b"nao e zip", b"PK\x03\x04lixo"):
            rep, existing = reg.inspect(bad)
            self.assertFalse(rep.ok)
            with self.assertRaises(RegistryError):
                reg.import_new(bad)
            with self.assertRaises(RegistryError):
                reg.import_copy(bad)
        self.assertEqual(reg.entries(), [])
        self.assertEqual(list(reg.microgrids_dir.iterdir()), [])


# =========================================================================== exclusão e recuperação
class ExclusaoTest(_Tmp):
    def test_exclusao_definitiva_remove_somente_a_microrrede(self):      # requisitos 16–17
        reg = self.reg()
        a, b = self.make(reg, "A"), self.make(reg, "B")
        reg.open(a).record_run(config_revision=1, config_fingerprint=None, spec_fingerprint="x", spec_origin="manual",
                               excluded=[], summary={})
        snap_b = _db_snapshot(reg.open(b))
        reg.delete(a)
        self.assertFalse(reg.dir_for(a).exists())
        self.assertIsNone(reg.get(a))
        self.assertEqual(list(reg.trash_dir.iterdir()), [])
        with self.assertRaises(MicrogridNotFound):
            reg.open(a)
        self.assertFalse(reg.dir_for(a).exists())                         # abrir não recria
        with self.assertRaises(MicrogridNotFound):
            reg.delete(a)
        self.assertEqual(_db_snapshot(reg.open(b)), snap_b)
        self.assertTrue(reg.path.is_file())
        # recomeçar do zero: o mesmo backup pode ser importado de novo depois da exclusão
        self.assertEqual(len(MicrogridRegistry(self.dir).entries()), 1)

    def test_exclusao_interrompida_e_concluida_na_reabertura(self):     # recuperável
        reg = self.reg()
        a, b = self.make(reg, "A"), self.make(reg, "B")
        with mock.patch.object(MicrogridRegistry, "_move_to_trash", side_effect=OSError("queda simulada")):
            with self.assertRaises(OSError):
                reg.delete(a)
        self.assertIsNone(reg.get(a))                                     # já invisível (estado "deleting")
        self.assertTrue(reg.dir_for(a).exists())
        with self.assertRaises(MicrogridNotFound):
            reg.open(a)
        reopened = MicrogridRegistry(self.dir)                            # recover() conclui
        self.assertFalse(reopened.dir_for(a).exists())
        self.assertEqual([e.uid for e in reopened.entries()], [b])
        with sqlite3.connect(reopened.path) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM microgrids WHERE uid = ?", (a,)).fetchone()[0], 0)

    def test_sessao_com_armazenamento_em_cache_nao_recria_a_microrrede(self):   # requisito 18 (backend)
        reg = self.reg()
        a = self.make(reg, "A")
        cached = reg.open(a)                                              # como o cache de outra sessão
        reg.delete(a)
        with self.assertRaises(MicrogridDeletedError):                    # erro explícito do domínio (H-01)
            cached.load()
        self.assertFalse(reg.dir_for(a).exists())
        with self.assertRaises(StoreError):
            MicrogridStore(reg.dir_for(a), must_exist=True, fixed_uid=a)
        self.assertFalse(reg.dir_for(a).exists())


class CriacaoRecuperavelTest(_Tmp):
    def test_falha_antes_da_confirmacao_nao_deixa_registro(self):
        reg = self.reg()
        cfg = v16_equivalent_config("A")
        real_rename = os.rename

        def boom(src, dst):
            if Path(dst).parent == reg.microgrids_dir:
                raise OSError("disco cheio (simulado)")
            return real_rename(src, dst)

        with mock.patch("seeds2.microgrid.registry.os.rename", side_effect=boom):
            with self.assertRaises(OSError):
                reg.create(cfg)
        self.assertEqual(reg.entries(), [])
        self.assertEqual(list(reg.microgrids_dir.iterdir()), [])
        self.assertEqual(list(reg.staging_dir.iterdir()), [])
        reg.create(cfg)                                                    # nova tentativa funciona
        self.assertEqual(len(reg.entries()), 1)

    def test_falha_no_insert_desfaz_o_rename(self):
        reg = self.reg()
        cfg = v16_equivalent_config("A")
        orig_connect = MicrogridRegistry._connect

        class Boom(Exception):
            pass

        def connect(self_):
            con = orig_connect(self_)

            class Wrapped:
                def __init__(self, c):
                    self._c = c

                def execute(self, sql, *a):
                    if sql.startswith("INSERT INTO microgrids"):
                        raise Boom("falha no catálogo")
                    return self._c.execute(sql, *a)

                def __getattr__(self, n):
                    return getattr(self._c, n)
            return Wrapped(con)

        with mock.patch.object(MicrogridRegistry, "_connect", connect):
            with self.assertRaises(Boom):
                reg.create(cfg)
        self.assertEqual(reg.entries(), [])
        self.assertEqual(list(reg.microgrids_dir.iterdir()), [])

    def test_diretorio_orfao_e_preparacao_abandonada_sao_descartados(self):
        reg = self.reg()
        a = self.make(reg, "A")
        orphan = reg.microgrids_dir / ("f" * 32)
        orphan.mkdir()
        (orphan / "seeds2.db").write_bytes(b"x")
        stale = reg.staging_dir / ("e" * 32)
        stale.mkdir()
        old = time.time() - 2 * R.STAGING_MAX_AGE_S
        os.utime(stale, (old, old))
        fresh = reg.staging_dir / ("d" * 32)
        fresh.mkdir()                                                      # outra operação em andamento: preservada
        foreign = reg.microgrids_dir / "nao-e-uid"
        foreign.mkdir()                                                    # nome fora do padrão: nunca tocado
        MicrogridRegistry(self.dir)
        self.assertFalse(orphan.exists())
        self.assertEqual([p.name.split("-")[0] for p in reg.quarantine_dir.iterdir()], ["f" * 32])   # preservado
        self.assertFalse(stale.exists())
        self.assertTrue(fresh.exists())
        self.assertTrue(foreign.exists())
        self.assertTrue(reg.dir_for(a).exists())

    def test_caminhos_derivados_somente_de_uid_validado(self):
        reg = self.reg()
        for bad in ("../../etc", "..", "A" * 32, "g" * 32, "", None, "a" * 31, "a" * 33, "a" * 31 + "/"):
            with self.assertRaises(MicrogridNotFound):
                reg.dir_for(bad)
            with self.assertRaises(MicrogridNotFound):
                reg.open(bad)
            self.assertIsNone(reg.get(bad))
        with self.assertRaises(RegistryError):
            reg._move_to_trash(self.dir)                                   # fora de microgrids/ e .staging/

    def test_aberturas_concorrentes_do_catalogo(self):
        reg = self.reg()
        self.make(reg, "A")
        errs, out = [], []
        start = threading.Barrier(4)

        def run():
            start.wait()
            try:
                out.append(len(MicrogridRegistry(self.dir).entries()))
            except Exception as exc:  # noqa: BLE001
                errs.append(exc)

        ts = [threading.Thread(target=run) for _ in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(30)
        self.assertEqual(errs, [])
        self.assertEqual(out, [1, 1, 1, 1])


# =========================================================================== armazenamento anterior ao Gestor
class AdocaoLegadoTest(_Tmp):
    def _legacy_v2(self, *, keep_open: bool = False):
        """seeds2.db do Piso 1/refinamento em SEEDS2_DATA_DIR, com histórico, CSV e rodada."""
        s = MicrogridStore(self.dir)
        cfg = v16_equivalent_config("Instalação existente")
        s.save(cfg, 0, origin="commissioning")
        h = s.put_blob(b"t_min,P_kW\n" + b"".join(f"{i},{50 + i % 5}\n".encode() for i in range(60)), "medicao.csv")
        cfg["demand"].update(source="csv", provenance="medido", csv={"blob": h, "filename": "medicao.csv", "start_min": 0,
                                                                     "duration_min": 30})
        s.save(cfg, 1)
        s.record_run(config_revision=2, config_fingerprint=s.load().fingerprint, spec_fingerprint="a" * 64,
                     spec_origin="microrrede", excluded=[], summary={"custo_total_rs": 12.5})
        return s, cfg

    def test_base_herdada_e_adotada_com_identidade_historico_dados_e_rodadas(self):   # requisito 19
        legacy, cfg = self._legacy_v2()
        uid = cfg["installation"]["uid"]
        before = _db_snapshot(legacy)
        legacy_hash = _sha(self.dir / "seeds2.db")
        reg = self.reg()
        self.assertEqual([e.uid for e in reg.entries()], [uid])
        e = reg.get(uid)
        self.assertEqual(e.origin, "legacy")
        adopted = reg.open(uid)
        self.assertEqual(adopted.load().config, legacy.load().config)     # nome, identidade, inventário
        self.assertEqual(_db_snapshot(adopted), before)                   # revisões, blobs, rodadas preservados
        self.assertEqual(_sha(self.dir / "seeds2.db"), legacy_hash)        # arquivo anterior intacto (byte a byte)
        info = json.loads(reg.meta("legacy_adoption"))
        self.assertEqual((info["state"], info["uid"], info["revisions"], info["blobs"], info["runs"]), ("done", uid, 2, 1, 1))
        # não se repete em reinícios — nem depois de excluir a microrrede adotada
        self.assertEqual(len(MicrogridRegistry(self.dir).entries()), 1)
        reg.delete(uid)
        self.assertEqual(MicrogridRegistry(self.dir).entries(), [])
        self.assertTrue((self.dir / "seeds2.db").is_file())

    def test_base_v1_real_e_migrada_na_copia_sem_alterar_o_original(self):          # requisitos 12 e 19
        v1 = json.loads(V1_CONFIG.read_text(encoding="utf-8"))
        db = self.dir / "seeds2.db"
        con = sqlite3.connect(db)
        from seeds2.microgrid.store import MIGRATIONS
        for stmt in MIGRATIONS[0][1]:
            con.execute(stmt)
        con.execute("PRAGMA user_version = 1")
        with zipfile.ZipFile(V1_BACKUP) as z:
            name = next(n for n in z.namelist() if n.startswith("blobs/"))
            blob = z.read(name)
        con.execute("INSERT INTO blobs VALUES (?,?,?,?,?,?)", (name[6:], "c.csv", "text/csv", len(blob), blob, "2026-11-01"))
        con.execute("INSERT INTO revisions VALUES (1,?,?,?,?,?,?)", (v1["installation"]["uid"], C.fingerprint(v1), json.dumps(v1),
                                                                    "2026-11-01T00:00:00+00:00", "v1", "commissioning"))
        con.execute("INSERT INTO microgrid VALUES (1,?,1,?,?,?)", (v1["installation"]["uid"], C.fingerprint(v1), json.dumps(v1),
                                                                   "2026-11-01T00:00:00+00:00"))
        con.commit()
        con.close()
        legacy_hash = _sha(db)
        reg = self.reg()
        uid = v1["installation"]["uid"]
        cur = reg.open(uid).load()
        self.assertEqual(cur.config["schema_version"], 2)
        self.assertEqual(cur.revision, 2)                                  # revisão de migração (na cópia)
        self.assertTrue((reg.dir_for(uid) / "seeds2.db.bak-v1").is_file())
        self.assertEqual(_sha(db), legacy_hash)
        with sqlite3.connect(db) as c:
            self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0], 1)        # original continua v1
        self.assertEqual(len(cur.config["equipment"]), len(v1["equipment"]))

    def test_base_herdada_com_wal_pendente_e_leitor_aberto(self):        # requisito 21
        w = sqlite3.connect(self.dir / "seeds2.db", isolation_level=None)
        w.execute("PRAGMA journal_mode=WAL")
        w.execute("PRAGMA wal_autocheckpoint=0")
        from seeds2.microgrid.store import MIGRATIONS
        w.execute("BEGIN")
        for stmt in MIGRATIONS[0][1]:
            w.execute(stmt)
        w.execute("PRAGMA user_version = 2")
        w.execute("COMMIT")
        cfg = v16_equivalent_config("WAL")
        doc = json.loads(C.canonical_json(cfg))
        w.execute("INSERT INTO revisions VALUES (1,?,?,?,?,?,?)", (doc["installation"]["uid"], C.fingerprint(doc),
                                                                   json.dumps(doc), C.utc_now(), "", "commissioning"))
        w.execute("INSERT INTO microgrid VALUES (1,?,1,?,?,?)", (doc["installation"]["uid"], C.fingerprint(doc),
                                                                 json.dumps(doc), C.utc_now()))
        self.assertGreater((self.dir / "seeds2.db-wal").stat().st_size, 0)
        reader = sqlite3.connect(self.dir / "seeds2.db", isolation_level=None)
        reader.execute("BEGIN")
        reader.execute("SELECT * FROM microgrid").fetchall()
        reg = self.reg()
        self.assertEqual(reg.open(doc["installation"]["uid"]).load().config, doc)
        reader.execute("COMMIT")
        reader.close()
        w.close()

    def test_base_herdada_vazia_nao_cria_microrrede(self):
        MicrogridStore(self.dir)                                          # banco criado, nada salvo
        reg = self.reg()
        self.assertEqual(reg.entries(), [])
        self.assertEqual(json.loads(reg.meta("legacy_adoption"))["state"], "empty")

    def test_adocao_interrompida_mantem_dados_e_e_retomada(self):        # requisito 20
        legacy, cfg = self._legacy_v2()
        before = _db_snapshot(legacy)
        legacy_hash = _sha(self.dir / "seeds2.db")
        with mock.patch.object(MicrogridRegistry, "_counts", side_effect=RuntimeError("queda simulada durante a verificação")):
            with self.assertRaises(LegacyAdoptionError) as ctx:
                MicrogridRegistry(self.dir)
        self.assertIn("mantidos intactos", str(ctx.exception))
        reg = MicrogridRegistry(self.dir, adopt_legacy=False)
        self.assertEqual(reg.entries(), [])                               # nenhuma microrrede vazia criada
        self.assertIsNone(reg.meta("legacy_adoption"))
        self.assertEqual(list(reg.microgrids_dir.iterdir()), [])
        self.assertEqual(_sha(self.dir / "seeds2.db"), legacy_hash)
        self.assertEqual(_db_snapshot(legacy), before)
        reg2 = MicrogridRegistry(self.dir)                                 # nova tentativa: concluída
        self.assertEqual([e.uid for e in reg2.entries()], [cfg["installation"]["uid"]])

    def test_falha_no_rename_da_adocao_nao_confirma(self):
        legacy, cfg = self._legacy_v2()
        real = os.rename

        def boom(src, dst):
            if Path(dst).parent.name == R.MICROGRIDS_DIR:
                raise OSError("falha simulada")
            return real(src, dst)

        with mock.patch("seeds2.microgrid.registry.os.rename", side_effect=boom):
            with self.assertRaises(LegacyAdoptionError):
                MicrogridRegistry(self.dir)
        reg = MicrogridRegistry(self.dir, adopt_legacy=False)
        self.assertEqual(reg.entries(), [])
        self.assertIsNone(reg.meta("legacy_adoption"))
        self.assertEqual(len(MicrogridRegistry(self.dir).entries()), 1)

    def test_adocao_concorrente_acontece_uma_unica_vez(self):
        self._legacy_v2()
        start, errs, regs = threading.Barrier(4), [], []

        def run():
            start.wait()
            try:
                regs.append(MicrogridRegistry(self.dir))
            except Exception as exc:  # noqa: BLE001
                errs.append(exc)

        ts = [threading.Thread(target=run) for _ in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(60)
        self.assertEqual(errs, [])
        self.assertEqual(len(regs[0].entries()), 1)
        self.assertEqual(len(list(regs[0].microgrids_dir.iterdir())), 1)

    def test_arquivo_herdado_corrompido_gera_erro_claro(self):
        (self.dir / "seeds2.db").write_bytes(b"isto nao e sqlite" * 100)
        with self.assertRaises(LegacyAdoptionError) as ctx:
            MicrogridRegistry(self.dir)
        self.assertIn("intactos", str(ctx.exception))
        self.assertEqual((self.dir / "seeds2.db").read_bytes(), b"isto nao e sqlite" * 100)
        self.assertEqual(MicrogridRegistry(self.dir, adopt_legacy=False).entries(), [])


# =========================================================================== proteção da exclusão
class PoliticaExclusaoTest(unittest.TestCase):
    def test_padrao_desativado_modo_dev_e_credencial(self):
        self.assertEqual(deletion_policy({}).mode, "disabled")
        self.assertFalse(deletion_policy({}).check("qualquer"))
        dev = deletion_policy({"SEEDS2_DEV_MODE": "1"})
        self.assertEqual(dev.mode, "dev")
        self.assertTrue(dev.check(None))
        prot = deletion_policy({"SEEDS2_ADMIN_PASSWORD": "s3gredo", "SEEDS2_DEV_MODE": "1"})   # credencial prevalece
        self.assertEqual(prot.mode, "protected")
        self.assertTrue(prot.check("s3gredo"))
        for wrong in ("", None, "S3gredo", "s3gredo ", 123):
            self.assertFalse(prot.check(wrong))
        self.assertNotIn("s3gredo", repr(prot))
        self.assertNotIn("s3gredo", prot.describe())
        sec = deletion_policy({}, lambda: "do-secrets")
        self.assertEqual(sec.mode, "protected")
        self.assertTrue(sec.check("do-secrets"))

        def no_secrets():
            raise FileNotFoundError("sem secrets.toml")
        self.assertEqual(deletion_policy({}, no_secrets).mode, "disabled")
        self.assertIsInstance(prot, DeletionPolicy)


# =========================================================================== EMS por microrrede
class RodadaPorMicrorredeTest(_Tmp):
    def test_duas_microrredes_identicas_tem_procedencia_distinta_e_rodada_preservada(self):   # requisitos 10, 24, 25
        import orchestrator_runtime as RT

        reg = self.reg()
        a = self.make(reg, "Gêmea A")
        b, _ = reg.import_copy(reg.open(a).export_backup())               # cópia: mesmos equipamentos e condições
        sa, sb = reg.open(a).load(), reg.open(b).load()
        pa = A.build_plan(sa.config, revision=sa.revision, fingerprint=sa.fingerprint)
        pb = A.build_plan(sb.config, revision=sb.revision, fingerprint=sb.fingerprint)
        self.assertEqual(pa.spec_fingerprint, pb.spec_fingerprint)        # mesma especificação científica...
        self.assertNotEqual(pa.provenance()["microgrid_uid"], pb.provenance()["microgrid_uid"])   # ...instalações distintas
        self.assertEqual((pa.provenance()["microgrid_uid"], pb.provenance()["microgrid_uid"]), (a, b))
        carga = A.build_load(pa.load_descriptor, reg.open(a).get_blob)
        opt = RT.default_optimizer_config()
        with tempfile.TemporaryDirectory() as pkg:
            path, _ = RT.build_exchange_package(carga, pa.spec, opt, destino=Path(pkg))
            r, _ = RT.run_optimizer(path, opt)
        with tempfile.TemporaryDirectory() as pkg2:                       # preservação numérica V1.6
            path2, _ = RT.build_exchange_package(carga, RT.default_model_spec(), opt, destino=Path(pkg2))
            r2, _ = RT.run_optimizer(path2, opt)
        np.testing.assert_allclose(r["P_kW"], r2["P_kW"])
        self.assertAlmostEqual(r["rel"]["custo_total_rs"], r2["rel"]["custo_total_rs"])
        reg.open(a).record_run(config_revision=sa.revision, config_fingerprint=sa.fingerprint,
                               spec_fingerprint=pa.spec_fingerprint, spec_origin="microrrede", excluded=[],
                               summary={"microgrid_uid": a, "custo_total_rs": float(r["rel"]["custo_total_rs"])})
        self.assertEqual(reg.open(b).runs(), [])                          # B não herda a rodada de A
        self.assertEqual(reg.open(a).runs()[0]["summary"]["microgrid_uid"], a)


if __name__ == "__main__":
    unittest.main()
