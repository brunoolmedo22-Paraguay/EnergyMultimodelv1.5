"""H-01 — Exclusão concorrente de microrredes: cenários DETERMINÍSTICOS de concorrência.

As intercalações críticas são forçadas com ``threading.Event``/``Barrier`` em pontos exatos do protocolo:
* um gravador é pausado DENTRO da transação de escrita (``_write_revision``, sob o bloqueio L2 da microrrede);
* o excluidor é pausado imediatamente DEPOIS de gravar a lápide (``_tombstone``), antes de reivindicar a linha;
* falhas de processo são simuladas por uma exceção em cada etapa do protocolo.
Esperas com tempo-limite só existem para não travar a suíte se algo der errado; a ordem dos eventos é
garantida pelos próprios bloqueios do SQLite, não por ``sleep``.
"""
from __future__ import annotations

import copy
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from seeds2.microgrid import config as C
from seeds2.microgrid.registry import MicrogridNotFound, MicrogridRegistry, RegistryError
from seeds2.microgrid.store import MicrogridDeletedError, MicrogridStore, MissingStoreError
from seeds2_fixtures import v16_equivalent_config

RAIZ = Path(__file__).resolve().parents[1]
T = 20          # tempo-limite de segurança (s) para eventos/joins — nunca usado como mecanismo de ordenação


class Crash(Exception):
    """Interrupção simulada do processo numa etapa do protocolo."""


def _raw(db: Path, sql: str):
    con = sqlite3.connect(Path(db).as_uri() + "?mode=ro", uri=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _snapshot(store: MicrogridStore) -> dict:
    return {t: _raw(store.path, f"SELECT * FROM {t} ORDER BY 1") for t in ("microgrid", "revisions", "blobs", "simulation_runs")}


class _Run(threading.Thread):
    """Thread que guarda o resultado ou a exceção do alvo."""

    def __init__(self, fn):
        super().__init__(daemon=True)
        self.fn, self.result, self.error = fn, None, None

    def run(self):
        try:
            self.result = self.fn()
        except BaseException as exc:  # noqa: BLE001
            self.error = exc


class _Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.dir = Path(self._t.name)
        self.reg = MicrogridRegistry(self.dir)
        self.a = self._make("A")
        self.b = self._make("B")

    def tearDown(self):
        self._t.cleanup()

    def _make(self, name: str) -> str:
        cfg = v16_equivalent_config(name)
        self.reg.create(cfg)
        return cfg["installation"]["uid"]

    def edited(self, uid: str, text: str = "editada") -> tuple[MicrogridStore, dict]:
        store = self.reg.open(uid)
        cfg = copy.deepcopy(store.load().config)
        cfg["installation"]["description"] = text
        return store, cfg

    @staticmethod
    def pause_inside_write(store: MicrogridStore) -> tuple[threading.Event, threading.Event]:
        """Pausa a PRÓXIMA gravação desta instância dentro da transação (com o bloqueio L2 obtido)."""
        inside, release = threading.Event(), threading.Event()
        orig = store._write_revision

        def slow(*a, **kw):
            inside.set()
            if not release.wait(T):
                raise RuntimeError("liberação não recebida")
            return orig(*a, **kw)
        store._write_revision = slow
        return inside, release

    def pause_after_tombstone(self, reg: MicrogridRegistry) -> tuple[threading.Event, threading.Event, dict]:
        """O excluidor para logo depois do COMMIT da lápide (antes de reivindicar a linha no catálogo)."""
        done, release, seen = threading.Event(), threading.Event(), {}
        orig = reg._tombstone

        def tomb(uid, **kw):
            r = orig(uid, **kw)
            seen["revision_at_tombstone"] = _raw(reg.dir_for(uid) / "seeds2.db", "SELECT revision FROM microgrid")[0][0]
            done.set()
            if not release.wait(T):
                raise RuntimeError("liberação não recebida")
            return r
        reg._tombstone = tomb
        return done, release, seen

    def assert_gone(self, uid: str) -> None:
        self.assertIsNone(self.reg.get(uid))
        self.assertFalse(self.reg.dir_for(uid).exists())
        with sqlite3.connect(self.reg.path) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM microgrids WHERE uid = ?", (uid,)).fetchone()[0], 0)
        self.assertEqual(list(self.reg.trash_dir.iterdir()), [])
        with self.assertRaises(MicrogridNotFound):
            self.reg.open(uid)
        self.assertFalse(self.reg.dir_for(uid).exists())                 # tentar abrir não recria


# =========================================================================== escrita × exclusão
class EscritaExclusaoTest(_Base):
    def test_escrita_iniciada_antes_termina_antes_da_remocao_fisica(self):
        store, cfg = self.edited(self.a)
        inside, release = self.pause_inside_write(store)
        writer = _Run(lambda: store.save(cfg, 1))
        writer.start()
        self.assertTrue(inside.wait(T))                                   # gravador segura o bloqueio L2 de A
        seen, started = {}, threading.Event()
        orig = self.reg._tombstone

        def tomb(uid, **kw):
            started.set()
            r = orig(uid, **kw)                                           # bloqueia até o gravador confirmar
            seen["rev"] = _raw(self.reg.dir_for(uid) / "seeds2.db", "SELECT revision FROM microgrid")[0][0]
            return r
        self.reg._tombstone = tomb
        deleter = _Run(lambda: self.reg.delete(self.a))
        deleter.start()
        self.assertTrue(started.wait(T))
        deleter.join(0.3)
        self.assertTrue(deleter.is_alive())                               # a exclusão espera a gravação em andamento
        release.set()
        writer.join(T)
        deleter.join(T)
        self.assertIsNone(writer.error)
        self.assertIsNone(deleter.error)
        self.assertEqual(writer.result.revision, 2)                       # a gravação foi confirmada...
        self.assertEqual(seen["rev"], 2)                                  # ...ANTES da lápide/remoção física
        self.assert_gone(self.a)

    def test_escrita_durante_a_exclusao_e_recusada(self):
        old = self.reg.open(self.a)                                       # referência de outra sessão
        snap = _snapshot(old)
        done, release, seen = self.pause_after_tombstone(self.reg)
        deleter = _Run(lambda: self.reg.delete(self.a))
        deleter.start()
        self.assertTrue(done.wait(T))                                     # lápide confirmada; exclusão em curso
        cfg = copy.deepcopy(v16_equivalent_config("X"))
        cfg["installation"]["uid"] = self.a
        for op in (lambda: old.save(cfg, 1), lambda: old.put_blob(b"t_min,P_kW\n0,1\n", "x.csv"),
                   lambda: old.record_run(config_revision=1, config_fingerprint=None, spec_fingerprint="s",
                                          spec_origin="manual", excluded=[], summary={}),
                   lambda: old.revert_to(1, 1), old.load, old.history,
                   lambda: MicrogridStore(self.reg.dir_for(self.a), must_exist=True, fixed_uid=self.a)):
            with self.assertRaises(MicrogridDeletedError):
                op()
        with self.assertRaises(MicrogridNotFound):
            self.reg.restore_into(self.a, b"x", 1)
        self.assertEqual({k: v for k, v in _snapshot_raw(self.reg.dir_for(self.a)).items()}, snap)   # nada gravado
        release.set()
        deleter.join(T)
        self.assertIsNone(deleter.error)
        self.assertEqual(seen["revision_at_tombstone"], 1)
        self.assert_gone(self.a)

    def test_escrita_depois_da_exclusao_e_recusada_sem_recriar_arquivos(self):
        old = self.reg.open(self.a)
        self.reg.delete(self.a)
        before = sorted(p.name for p in self.dir.rglob("*"))
        for op in (old.load, lambda: old.save(old_cfg(self.a), 1), lambda: old.put_blob(b"x", "x"),
                   lambda: old.record_run(config_revision=None, config_fingerprint=None, spec_fingerprint="s",
                                          spec_origin="manual", excluded=[], summary={}), old.runs):
            with self.assertRaises(MicrogridDeletedError):
                op()
        with self.assertRaises(MissingStoreError):
            MicrogridStore(self.reg.dir_for(self.a), must_exist=True, fixed_uid=self.a)
        self.assertEqual(sorted(p.name for p in self.dir.rglob("*")), before)    # nenhum arquivo recriado
        self.assert_gone(self.a)

    def test_lapide_nao_obtida_nao_altera_nada(self):
        store, cfg = self.edited(self.a)
        inside, release = self.pause_inside_write(store)
        writer = _Run(lambda: store.save(cfg, 1))
        writer.start()
        self.assertTrue(inside.wait(T))
        with self.assertRaises(RegistryError):
            self.reg.delete(self.a, lock_timeout_s=0.3)                   # gravação longa: exclusão desiste
        self.assertIsNotNone(self.reg.get(self.a))                        # nada mudou
        self.assertEqual(self.reg._lifecycle(self.a), None)
        release.set()
        writer.join(T)
        self.assertIsNone(writer.error)
        self.assertEqual(self.reg.open(self.a).load().revision, 2)       # microrrede segue íntegra e utilizável


def _snapshot_raw(d: Path) -> dict:
    return {t: _raw(d / "seeds2.db", f"SELECT * FROM {t} ORDER BY 1") for t in ("microgrid", "revisions", "blobs", "simulation_runs")}


def old_cfg(uid: str) -> dict:
    cfg = v16_equivalent_config("X")
    cfg["installation"]["uid"] = uid
    return cfg


# =========================================================================== exclusões / restauração / importação
class OperacoesSimultaneasTest(_Base):
    def test_duas_exclusoes_simultaneas_uma_efetiva(self):
        snap_b = _snapshot(self.reg.open(self.b))
        regs = [MicrogridRegistry(self.dir, adopt_legacy=False) for _ in range(2)]   # dois processos/sessões
        barrier = threading.Barrier(2)
        for r in regs:
            orig = r._tombstone

            def tomb(uid, _orig=orig, **kw):
                res = _orig(uid, **kw)
                barrier.wait(T)                                           # ambos gravaram a lápide antes de reivindicar
                return res
            r._tombstone = tomb
        runs = [_Run(lambda r=r: r.delete(self.a)) for r in regs]
        for t in runs:
            t.start()
        for t in runs:
            t.join(T)
        errors = [t.error for t in runs]
        self.assertEqual(sum(e is None for e in errors), 1, errors)
        self.assertEqual(sum(isinstance(e, MicrogridNotFound) for e in errors), 1, errors)
        self.assert_gone(self.a)
        self.assertEqual(_snapshot(self.reg.open(self.b)), snap_b)

    def test_restauracao_antes_da_lapide_e_confirmada_e_depois_excluida(self):
        z = self.reg.open(self.a).export_backup()
        store, cfg = self.edited(self.a)
        store.save(cfg, 1)
        restorer_store = self.reg.open(self.a)
        inside, release = self.pause_inside_write(restorer_store)
        restorer = _Run(lambda: restorer_store.restore_backup(z, 2, confirm=True))
        restorer.start()
        self.assertTrue(inside.wait(T))
        seen = {}
        orig = self.reg._tombstone

        def tomb(uid, **kw):
            r = orig(uid, **kw)
            seen["rev"] = _raw(self.reg.dir_for(uid) / "seeds2.db", "SELECT revision FROM microgrid")[0][0]
            return r
        self.reg._tombstone = tomb
        deleter = _Run(lambda: self.reg.delete(self.a))
        deleter.start()
        release.set()
        restorer.join(T)
        deleter.join(T)
        self.assertIsNone(restorer.error)
        self.assertIsNone(deleter.error)
        self.assertEqual((restorer.result.revision, seen["rev"]), (3, 3))   # restauração inteira antes da lápide
        self.assert_gone(self.a)

    def test_restauracao_depois_da_lapide_e_recusada(self):
        z = self.reg.open(self.a).export_backup()
        old = self.reg.open(self.a)
        done, release, _ = self.pause_after_tombstone(self.reg)
        deleter = _Run(lambda: self.reg.delete(self.a))
        deleter.start()
        self.assertTrue(done.wait(T))
        with self.assertRaises(MicrogridNotFound):
            self.reg.restore_into(self.a, z, 1)
        with self.assertRaises(MicrogridDeletedError):
            old.restore_backup(z, 1, confirm=True)
        release.set()
        deleter.join(T)
        self.assertIsNone(deleter.error)
        self.assert_gone(self.a)

    def test_importacao_simultanea_com_o_mesmo_uid_gera_uma_entrada(self):
        src = MicrogridRegistry(self.dir / "origem")
        cfg = v16_equivalent_config("Importada")
        src.create(cfg)
        z = src.open(cfg["installation"]["uid"]).export_backup()
        barrier = threading.Barrier(2)
        orig = MicrogridStore.import_inspected

        def both_prepared(self_, *a, **kw):
            res = orig(self_, *a, **kw)
            barrier.wait(T)                                               # as duas preparações existem em .staging
            return res
        regs = [MicrogridRegistry(self.dir, adopt_legacy=False) for _ in range(2)]
        with mock.patch.object(MicrogridStore, "import_inspected", both_prepared):
            runs = [_Run(lambda r=r: r.import_new(z)) for r in regs]
            for t in runs:
                t.start()
            for t in runs:
                t.join(T)
        errors = [t.error for t in runs]
        self.assertEqual(sum(e is None for e in errors), 1, errors)
        self.assertTrue(any(isinstance(e, RegistryError) and "Já existe" in str(e) for e in errors), errors)
        uid = cfg["installation"]["uid"]
        self.assertEqual([e.uid for e in self.reg.entries()].count(uid), 1)
        self.assertEqual(sorted(p.name for p in self.reg.microgrids_dir.iterdir()), sorted([self.a, self.b, uid]))
        self.assertEqual(list(self.reg.staging_dir.iterdir()), [])
        self.assertFalse(self.reg.quarantine_dir.exists() and list(self.reg.quarantine_dir.iterdir()))
        self.assertEqual(self.reg.open(uid).load().config["installation"]["name"], "Importada")


# =========================================================================== referências antigas
class ReferenciaAntigaTest(_Base):
    def test_sessao_antiga_apos_excluir_e_reimportar_o_mesmo_uid(self):
        z = self.reg.open(self.a).export_backup()
        old, cfg = self.edited(self.a, "edição pendente da sessão antiga")
        old_inc = self.reg.get(self.a).incarnation
        self.reg.delete(self.a)
        uid, _ = self.reg.import_new(z)                                   # MESMO uid, nova incarnação
        self.assertEqual(uid, self.a)
        self.assertNotEqual(self.reg.get(self.a).incarnation, old_inc)
        for op in (old.load, lambda: old.save(cfg, 1), old.history):
            with self.assertRaises(MicrogridDeletedError):
                op()
        fresh = self.reg.open(self.a).load()
        self.assertEqual(fresh.revision, 1)                               # a edição antiga nunca chegou à nova
        self.assertNotEqual(fresh.config["installation"]["description"], "edição pendente da sessão antiga")

    def test_incarnacao_gravada_no_catalogo_e_no_banco(self):
        for uid in (self.a, self.b):
            inc = self.reg.get(uid).incarnation
            self.assertRegex(inc, r"^[0-9a-f]{32}$")
            self.assertEqual(_raw(self.reg.dir_for(uid) / "seeds2.db",
                                  "SELECT value FROM meta WHERE key = 'incarnation'")[0][0], inc)
        self.assertNotEqual(self.reg.get(self.a).incarnation, self.reg.get(self.b).incarnation)

    def test_catalogo_anterior_ao_hotfix_recebe_incarnacao(self):
        with sqlite3.connect(self.reg.path) as con:                       # simula entrada criada antes do H-01
            con.execute("UPDATE microgrids SET incarnation = NULL WHERE uid = ?", (self.a,))
        with sqlite3.connect(self.reg.dir_for(self.a) / "seeds2.db") as con:
            con.execute("DELETE FROM meta WHERE key = 'incarnation'")
        r1 = MicrogridRegistry(self.dir)
        inc = r1.get(self.a).incarnation
        self.assertIsNotNone(inc)
        self.assertEqual(_raw(r1.dir_for(self.a) / "seeds2.db", "SELECT value FROM meta WHERE key = 'incarnation'")[0][0], inc)
        self.assertEqual(MicrogridRegistry(self.dir).get(self.a).incarnation, inc)   # estável em reaberturas
        self.assertEqual(r1.open(self.a).load().config["installation"]["uid"], self.a)


# =========================================================================== interrupções e reinícios
class InterrupcaoTest(_Base):
    def _check_recovered(self, snap_b):
        for _ in range(3):                                                # recuperação idempotente
            r = MicrogridRegistry(self.dir)
            self.assertEqual([e.uid for e in r.entries()], [self.b])
            self.assertFalse(r.dir_for(self.a).exists())
            self.assertEqual(list(r.trash_dir.iterdir()), [])
            self.assertEqual(_snapshot(r.open(self.b)), snap_b)
            with sqlite3.connect(r.path) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM microgrids").fetchone()[0], 1)

    def test_interrupcao_depois_da_lapide(self):
        snap_b = _snapshot(self.reg.open(self.b))
        orig = self.reg._tombstone

        def crash(uid, **kw):
            orig(uid, **kw)
            raise Crash("queda depois da lápide")
        self.reg._tombstone = crash
        with self.assertRaises(Crash):
            self.reg.delete(self.a)
        self.assertEqual(self.reg._lifecycle(self.a), "deleted")
        with self.assertRaises(MicrogridNotFound):
            self.reg.open(self.a)                                         # já inacessível, mesmo antes da recuperação
        other = self.reg.open(self.b)                                     # sessão aberta em outra microrrede
        self._check_recovered(snap_b)
        self.assertEqual(other.load().config["installation"]["uid"], self.b)   # continua operando

    def test_interrupcao_depois_da_reivindicacao(self):
        snap_b = _snapshot(self.reg.open(self.b))
        with mock.patch.object(MicrogridRegistry, "_finish_deletion", side_effect=Crash("queda")):
            with self.assertRaises(Crash):
                self.reg.delete(self.a)
        self.assertIsNone(self.reg.get(self.a))
        self.assertTrue(self.reg.dir_for(self.a).exists())
        self._check_recovered(snap_b)

    def test_interrupcao_durante_a_remocao_fisica(self):
        snap_b = _snapshot(self.reg.open(self.b))
        orig = MicrogridRegistry._move_to_trash

        def move_then_crash(self_, path, **kw):
            orig(self_, path, **kw)
            raise Crash("queda depois do rename")
        with mock.patch.object(MicrogridRegistry, "_move_to_trash", move_then_crash):
            with self.assertRaises(Crash):
                self.reg.delete(self.a)
        self.assertFalse(self.reg.dir_for(self.a).exists())
        with sqlite3.connect(self.reg.path) as con:                       # rollback: linha ainda "deleting"
            self.assertEqual(con.execute("SELECT state FROM microgrids WHERE uid = ?", (self.a,)).fetchone()[0], "deleting")
        self._check_recovered(snap_b)

    def test_linha_deleting_sem_lapide_de_versao_anterior(self):
        snap_b = _snapshot(self.reg.open(self.b))
        with sqlite3.connect(self.reg.path) as con:
            con.execute("UPDATE microgrids SET state = 'deleting' WHERE uid = ?", (self.a,))
        self.assertIsNone(self.reg._lifecycle(self.a))
        self._check_recovered(snap_b)

    def test_reinicios_repetidos_mantem_o_catalogo_consistente(self):
        c = self._make("C")
        self.reg.delete(self.b)
        snaps = {u: _snapshot(self.reg.open(u)) for u in (self.a, c)}
        incs = {u: self.reg.get(u).incarnation for u in (self.a, c)}
        code = ("import sys; from seeds2.microgrid.registry import MicrogridRegistry as R; "
                "[R(sys.argv[1]) for _ in range(3)]; r = R(sys.argv[1]); print(','.join(sorted(e.uid for e in r.entries())))")
        for i in range(6):
            if i == 3:
                out = subprocess.run([sys.executable, "-c", code, str(self.dir)], cwd=RAIZ, capture_output=True, text=True,
                                     timeout=120)
                self.assertEqual(out.returncode, 0, out.stderr)
                self.assertEqual(out.stdout.strip(), ",".join(sorted([self.a, c])))
            r = MicrogridRegistry(self.dir)
            self.assertEqual(sorted(e.uid for e in r.entries()), sorted([self.a, c]))
            self.assertEqual({u: r.get(u).incarnation for u in (self.a, c)}, incs)
            self.assertEqual({u: _snapshot(r.open(u)) for u in (self.a, c)}, snaps)
            self.assertEqual(sorted(p.name for p in r.microgrids_dir.iterdir()), sorted([self.a, c]))
            self.assertEqual(list(r.trash_dir.iterdir()), [])
            self.assertFalse(r.quarantine_dir.exists() and list(r.quarantine_dir.iterdir()))


# =========================================================================== independência entre microrredes
class IndependenciaTest(_Base):
    def test_exclusao_de_A_nao_bloqueia_gravacoes_nem_exclusoes_de_outras(self):
        c = self._make("C")
        store_a, cfg_a = self.edited(self.a)
        inside, release = self.pause_inside_write(store_a)
        writer_a = _Run(lambda: store_a.save(cfg_a, 1))
        writer_a.start()
        self.assertTrue(inside.wait(T))                                   # L2(A) ocupado
        deleter_a = _Run(lambda: self.reg.delete(self.a))
        deleter_a.start()                                                 # esperando L2(A)
        store_b, cfg_b = self.edited(self.b, "B editada")
        self.assertEqual(store_b.save(cfg_b, 1).revision, 2)              # B grava normalmente
        store_b.put_blob(b"t_min,P_kW\n0,1\n", "b.csv")
        store_b.record_run(config_revision=2, config_fingerprint=None, spec_fingerprint="s", spec_origin="manual",
                           excluded=[], summary={"microgrid_uid": self.b})
        self.reg.delete(c)                                                # e outra exclusão termina
        self.assertIsNone(self.reg.get(c))
        self.assertTrue(deleter_a.is_alive())                             # enquanto a exclusão de A ainda espera
        self.assertIsNotNone(self.reg.get(self.a))
        release.set()
        writer_a.join(T)
        deleter_a.join(T)
        self.assertIsNone(writer_a.error)
        self.assertIsNone(deleter_a.error)
        self.assert_gone(self.a)
        self.assertEqual(self.reg.open(self.b).load().revision, 2)
        self.assertEqual(len(self.reg.open(self.b).runs()), 1)


if __name__ == "__main__":
    unittest.main()
