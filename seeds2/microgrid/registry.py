"""Catálogo de microrredes do SEEDS2 (Gestor de microrredes) — sem Streamlit.

Decisão do responsável (missão "Gestor de microrredes"): uma instalação do SEEDS2 administra VÁRIAS
microrredes independentes. Esta decisão substitui a regra anterior de "uma microrrede por instalação".

Armazenamento::

    SEEDS2_DATA_DIR/
    ├── registry.db                 catálogo (identidades, estado, origem) — nunca dados técnicos
    ├── microgrids/<uid>/seeds2.db  um MicrogridStore COMPLETO por microrrede (configuração, revisões, blobs,
    │                               rodadas, cópias .bak-v<N>) — a garantia CHECK(id = 1) continua valendo
    ├── .staging/<op>/              preparação de criação/importação/adoção (descartável)
    ├── .trash/<uid>-<t>/           exclusões em andamento (descartável)
    └── seeds2.db                   armazenamento ANTERIOR ao Gestor (somente leitura; adotado uma vez)

Protocolo recuperável (várias bases SQLite + sistema de arquivos — não há transação única entre eles):

* **criar / importar / copiar / adotar**: o banco é montado e verificado em ``.staging`` (preparação); a
  confirmação é ``rename(staging → microgrids/<uid>)`` + ``INSERT`` no catálogo, ambos sob o bloqueio de
  escrita do catálogo. Falha antes da confirmação → nada aparece no catálogo; diretório órfão (sem linha
  no catálogo) é movido para ``.trash`` na próxima abertura.
* **excluir** (H-01): (1) **lápide** ``meta.lifecycle`` gravada no banco da microrrede sob o SEU bloqueio de
  escrita — espera gravações em andamento terminarem; depois do COMMIT toda leitura/gravação (de qualquer
  sessão ou processo, inclusive referências antigas) é recusada; (2) linha marcada ``deleting`` no catálogo
  (exatamente UM excluidor vence); (3) diretório movido para ``.trash`` + linha removida; (4) ``.trash``
  esvaziado. Interrupção em qualquer ponto → ``recover()`` conclui (só exclusões com lápide confirmada).
* **ordem de bloqueios**: L1 = escrita do catálogo (``registry.db``), L2 = escrita de UMA microrrede. Nunca
  se adquire L2 de uma microrrede do catálogo segurando L1, nem L1 segurando L2 (sem impasse). Bancos em
  ``.staging`` são privados da operação e podem ser escritos sob L1. Excluir A não toma L2 de nenhuma outra.
* **incarnação**: cada entrada recebe um token gravado no catálogo e no banco (``meta.incarnation``); uma
  referência antiga a uma microrrede excluída e reimportada com o MESMO UID é recusada. Toda exclusão é
  VINCULADA a uma incarnação (H-02): a lápide confere a incarnação do banco sob L2, a reivindicação
  ``ready → deleting`` confere a do catálogo sob L1 e a remoção física confere as duas — uma exclusão obsoleta
  falha (``StaleDeletionError``) sem tocar na nova microrrede com o mesmo UID.
* **adotar o armazenamento anterior**: cópia consistente pela API de backup do SQLite (inclui o ``-wal``),
  verificação de contagens (revisões, blobs, rodadas) e confirmação como acima. O arquivo anterior NUNCA é
  alterado; a adoção é marcada no catálogo e não se repete.

Caminhos no sistema de arquivos são derivados SOMENTE do UID validado (32 hex); nenhum texto do usuário é
usado como caminho.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from . import config as C
from .store import (DB_FILENAME, INCARNATION_KEY, LIFECYCLE_KEY, BackupInspection, MicrogridStore, MissingStoreError, Stored, StoreError,
                    ensure_wal, inspect_backup_data, resolve_data_dir, sqlite_backup_copy)

REGISTRY_FILENAME = "registry.db"
MICROGRIDS_DIR = "microgrids"
STAGING_DIR = ".staging"
TRASH_DIR = ".trash"
QUARANTINE_DIR = ".quarantine"                # diretórios sem linha no catálogo: guardados, nunca apagados sozinhos
DELETE_LOCK_TIMEOUT_S = 30.0                  # espera máxima por gravações em andamento antes da lápide
LEGACY_FILENAME = DB_FILENAME                 # SEEDS2_DATA_DIR/seeds2.db (Piso 1 e refinamento)
STAGING_MAX_AGE_S = 3600.0                    # preparação abandonada (outro processo nunca demora tanto)
UID_RE = re.compile(r"[0-9a-f]{32}")
ORIGIN_LABELS = {"new": "Criada no SEEDS2", "legacy": "Adotada do armazenamento anterior",
                 "import": "Importada de backup", "copy": "Cópia independente importada"}

REGISTRY_MIGRATIONS: list[tuple[int, list[str]]] = [
    (1, [
        """CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
        """CREATE TABLE microgrids (
               uid TEXT PRIMARY KEY CHECK (length(uid) = 32 AND uid NOT GLOB '*[^0-9a-f]*'),
               state TEXT NOT NULL CHECK (state IN ('ready', 'deleting')),
               origin TEXT NOT NULL CHECK (origin IN ('new', 'legacy', 'import', 'copy')),
               created_at TEXT NOT NULL,
               source_uid TEXT,
               source_fingerprint TEXT,
               note TEXT NOT NULL DEFAULT '')""",
    ]),
]
REGISTRY_MIGRATIONS.append(
    # v2 (hotfix H-01): incarnação de cada entrada (preenchida para entradas existentes na abertura)
    (2, ["""ALTER TABLE microgrids ADD COLUMN incarnation TEXT"""]))
LATEST_REGISTRY_VERSION = REGISTRY_MIGRATIONS[-1][0]


class RegistryError(StoreError):
    """Erro do catálogo com mensagem apresentável ao usuário."""


class MicrogridNotFound(RegistryError):
    """A microrrede não existe (ou está sendo excluída)."""


class StaleDeletionError(MicrogridNotFound):
    """Exclusão obsoleta (H-02): a microrrede com este UID é outra incarnação (excluída e reimportada).
    Nada é alterado na nova microrrede."""


class LegacyAdoptionError(RegistryError):
    """O armazenamento anterior não pôde ser adotado; ele permanece intacto."""


@dataclass(frozen=True)
class Entry:
    uid: str
    state: str
    origin: str
    created_at: str
    source_uid: str | None
    source_fingerprint: str | None
    note: str
    incarnation: str | None = None


def valid_uid(uid: Any) -> bool:
    return isinstance(uid, str) and UID_RE.fullmatch(uid) is not None


def _check_uid(uid: Any) -> str:
    if not valid_uid(uid):
        raise MicrogridNotFound("Identificador de microrrede inválido.")
    return uid


class MicrogridRegistry:
    """Catálogo de microrredes. Cada operação abre e fecha suas conexões (seguro entre sessões/processos)."""

    def __init__(self, data_dir: str | os.PathLike | None = None, *, adopt_legacy: bool = True):
        self.root = resolve_data_dir(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / REGISTRY_FILENAME
        self.microgrids_dir = self.root / MICROGRIDS_DIR
        self.staging_dir = self.root / STAGING_DIR
        self.trash_dir = self.root / TRASH_DIR
        self.quarantine_dir = self.root / QUARANTINE_DIR
        for d in (self.microgrids_dir, self.staging_dir, self.trash_dir):
            d.mkdir(exist_ok=True)
        self._migrate()
        self.recover()
        self._backfill_incarnations()
        if adopt_legacy:
            self.adopt_legacy()

    # ------------------------------------------------------------ conexão
    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        con.row_factory = sqlite3.Row
        ensure_wal(con)
        con.execute("PRAGMA busy_timeout=30000")
        return con

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """Transação de escrita do catálogo (BEGIN IMMEDIATE: serializa operações estruturais)."""
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.execute("COMMIT")
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        con = self._connect()
        try:
            yield con
        finally:
            con.close()

    def _migrate(self) -> None:
        with self._tx() as con:
            current = int(con.execute("PRAGMA user_version").fetchone()[0])
            if current > LATEST_REGISTRY_VERSION:
                raise RegistryError(f"O catálogo {self.path} usa o esquema v{current}, mais novo que este software. "
                                    "Atualize o SEEDS2; nada foi alterado.")
            for version, stmts in REGISTRY_MIGRATIONS:
                if version > current:
                    for s in stmts:
                        con.execute(s)
                    con.execute(f"PRAGMA user_version = {int(version)}")

    # ------------------------------------------------------------ caminhos (somente a partir do UID validado)
    def dir_for(self, uid: str) -> Path:
        return self.microgrids_dir / _check_uid(uid)

    def _move_to_trash(self, path: Path, *, quarantine: bool = False) -> None:
        """Move um diretório DESTE catálogo para ``.trash`` (ou ``.quarantine``) — rename atômico no mesmo
        sistema de arquivos."""
        if path.parent not in (self.microgrids_dir, self.staging_dir) or path.is_symlink():
            raise RegistryError(f"Recusado: {path} não pertence ao armazenamento do SEEDS2.")
        if path.exists():
            dest = self.quarantine_dir if quarantine else self.trash_dir
            dest.mkdir(exist_ok=True)
            os.rename(path, dest / f"{path.name}-{uuid.uuid4().hex[:8]}")

    def _purge_trash(self) -> None:
        for item in list(self.trash_dir.iterdir()):
            if item.parent != self.trash_dir:
                continue
            if item.is_symlink() or item.is_file():
                item.unlink(missing_ok=True)
            else:
                shutil.rmtree(item, ignore_errors=True)

    def _new_staging(self) -> Path:
        d = self.staging_dir / uuid.uuid4().hex
        d.mkdir()
        return d

    # ------------------------------------------------------------ recuperação
    def recover(self) -> None:
        """Conclui exclusões interrompidas e descarta preparações abandonadas. Idempotente: executar de novo não
        remove nada além do que já estava em exclusão confirmada.

        * fase A (sem L1): para cada linha ``deleting`` garante a lápide DA MESMA incarnação (versões antigas /
          interrupções); detecta linhas ``ready`` cujo banco tem lápide e a mesma incarnação (exclusão
          interrompida antes de reivindicar a linha);
        * fase B (sob L1): para essas — e SOMENTE essas — reconfirma linha e banco (mesma incarnação), move o
          diretório para ``.trash`` e remove a linha; diretórios sem linha vão para ``.quarantine``;
        * preparações em ``.staging`` com mais de 1 h e o ``.trash`` são esvaziados.
        Divergência de incarnação (que o protocolo não produz) nunca resulta em remoção: a entrada é mantida.
        Uma exclusão cuja lápide ainda não pôde ser gravada fica para a próxima abertura."""
        with self._read() as con:
            rows = [(r["uid"], r["state"], r["incarnation"])
                    for r in con.execute("SELECT uid, state, incarnation FROM microgrids").fetchall()]
        finishing: dict[str, str | None] = {}
        for uid, state, inc in rows:
            if not valid_uid(uid):
                continue
            if state == "deleting":
                try:
                    self._tombstone(uid, incarnation=inc, timeout_s=2.0)
                except RegistryError:                   # bloqueio ocupado ou incarnação divergente: não remove
                    continue
                finishing[uid] = inc
            elif self._tombstoned_incarnation(uid, inc):
                finishing[uid] = inc
        with self._tx() as con:
            for uid, inc in sorted(finishing.items()):
                row = con.execute("SELECT state, incarnation FROM microgrids WHERE uid = ?", (uid,)).fetchone()
                if row is None or row["incarnation"] != inc:
                    continue                            # outra incarnação (reimportada): intocada
                if row["state"] == "ready" and not self._tombstoned_incarnation(uid, inc):
                    continue
                if not self._dir_matches(uid, inc):
                    continue
                self._move_to_trash(self.dir_for(uid))
                con.execute("DELETE FROM microgrids WHERE uid = ? AND incarnation IS ?", (uid, inc))
            known = {r["uid"] for r in con.execute("SELECT uid FROM microgrids").fetchall()}
            for item in self.microgrids_dir.iterdir():
                if valid_uid(item.name) and item.name not in known and item.is_dir() and not item.is_symlink():
                    self._move_to_trash(item, quarantine=True)
        now = time.time()
        for item in list(self.staging_dir.iterdir()):
            try:
                if valid_uid(item.name) and now - item.stat().st_mtime > STAGING_MAX_AGE_S:
                    shutil.rmtree(item, ignore_errors=True)
            except FileNotFoundError:
                pass
        self._purge_trash()

    def _backfill_one(self, uid: str) -> None:
        try:
            inc = MicrogridStore(self.dir_for(uid), must_exist=True, fixed_uid=uid).stamp_incarnation(uuid.uuid4().hex)
        except StoreError:
            return
        with self._tx() as con:
            con.execute("UPDATE microgrids SET incarnation = ? WHERE uid = ? AND incarnation IS NULL", (inc, uid))

    def _backfill_incarnations(self) -> None:
        """Entradas criadas antes do hotfix H-01 recebem incarnação (banco primeiro, catálogo depois; seguro
        entre processos: ``INSERT OR IGNORE`` no banco e ``UPDATE ... WHERE incarnation IS NULL``)."""
        with self._read() as con:
            uids = [r["uid"] for r in con.execute(
                "SELECT uid FROM microgrids WHERE state = 'ready' AND incarnation IS NULL").fetchall()]
        for uid in uids:
            self._backfill_one(uid)

    # ------------------------------------------------------------ lápide (bloqueio L2 da microrrede)
    def _mg_db(self, uid: str) -> Path:
        return self.dir_for(uid) / DB_FILENAME

    def _db_identity(self, uid: str) -> dict:
        """Leitura somente leitura do banco da microrrede: existe? incarnação? lápide (JSON)?"""
        db = self._mg_db(uid)
        if not db.is_file():
            return {"exists": False, "incarnation": None, "tombstone": None}
        try:
            con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=10.0)
        except sqlite3.OperationalError:
            return {"exists": False, "incarnation": None, "tombstone": None}
        try:
            meta = {k: v for k, v in con.execute("SELECT key, value FROM meta WHERE key IN (?, ?)",
                                                 (LIFECYCLE_KEY, INCARNATION_KEY)).fetchall()}
        except sqlite3.OperationalError:
            meta = {}
        finally:
            con.close()
        tomb = None
        if meta.get(LIFECYCLE_KEY):
            try:
                tomb = json.loads(meta[LIFECYCLE_KEY])
            except ValueError:
                tomb = {"state": "deleted"}
        return {"exists": True, "incarnation": meta.get(INCARNATION_KEY), "tombstone": tomb}

    def _lifecycle(self, uid: str) -> str | None:
        """Estado gravado no banco da microrrede: "deleted" (lápide), "missing" (sem banco) ou None (ativa)."""
        ident = self._db_identity(uid)
        if not ident["exists"]:
            return "missing"
        return "deleted" if ident["tombstone"] else None

    def _dir_matches(self, uid: str, incarnation: str | None) -> bool:
        """O diretório microgrids/<uid> pertence a ESTA incarnação (ou já não existe)?"""
        ident = self._db_identity(uid)
        if not ident["exists"]:
            return True
        return incarnation is None or ident["incarnation"] == incarnation

    def _tombstoned_incarnation(self, uid: str, incarnation: str | None) -> bool:
        """O banco tem lápide E pertence à incarnação dada (lápide gravada para ela ou sem registro de qual)."""
        ident = self._db_identity(uid)
        tomb = ident["tombstone"]
        if not ident["exists"] or not tomb:
            return False
        if incarnation is not None and ident["incarnation"] != incarnation:
            return False
        return tomb.get("incarnation") in (None, incarnation)

    def _tombstone(self, uid: str, *, incarnation: str | None, timeout_s: float = DELETE_LOCK_TIMEOUT_S) -> bool:
        """Transição crítica da exclusão, sob o bloqueio de escrita (L2) DESTA microrrede: espera as gravações
        em andamento terminarem (``busy_timeout``), CONFERE a incarnação do banco (H-02) e grava a lápide
        vinculada a ela. Depois do COMMIT nenhuma gravação é aceita. Devolve False se o banco não existe.
        Incarnação divergente → ``StaleDeletionError``; bloqueio não obtido → ``RegistryError``; em ambos os
        casos NADA é alterado."""
        db = self._mg_db(uid)
        if not db.is_file():
            return False
        try:
            con = sqlite3.connect(db.as_uri() + "?mode=rw", uri=True, timeout=timeout_s, isolation_level=None)
        except sqlite3.OperationalError:
            return False
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT value FROM meta WHERE key = ?", (INCARNATION_KEY,)).fetchone()
            actual = row[0] if row else None
            if incarnation is not None and actual != incarnation:
                raise StaleDeletionError("A microrrede com este identificador foi substituída por outra (excluída e "
                                         "reimportada); a exclusão solicitada é obsoleta e nada foi alterado.")
            con.execute("INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
                        (LIFECYCLE_KEY, json.dumps({"state": "deleted", "incarnation": actual, "at": C.utc_now()})))
            con.execute("COMMIT")
            return True
        except sqlite3.OperationalError as exc:
            raise RegistryError(f"A microrrede está em uso (gravação em andamento); nada foi excluído. ({exc})") from None
        finally:
            if con.in_transaction:
                con.execute("ROLLBACK")
            con.close()

    # ------------------------------------------------------------ consulta
    @staticmethod
    def _entry(row: sqlite3.Row) -> Entry:
        return Entry(row["uid"], row["state"], row["origin"], row["created_at"], row["source_uid"],
                     row["source_fingerprint"], row["note"], row["incarnation"])

    def entries(self) -> list[Entry]:
        with self._read() as con:
            rows = con.execute("SELECT * FROM microgrids WHERE state = 'ready' ORDER BY created_at, uid").fetchall()
        return [self._entry(r) for r in rows]

    def get(self, uid: str) -> Entry | None:
        if not valid_uid(uid):
            return None
        with self._read() as con:
            row = con.execute("SELECT * FROM microgrids WHERE uid = ? AND state = 'ready'", (uid,)).fetchone()
        return self._entry(row) if row else None

    def exists(self, uid: str) -> bool:
        return self.get(uid) is not None

    def open(self, uid: str) -> MicrogridStore:
        """Armazenamento de uma microrrede EXISTENTE, ligado à sua incarnação. Nunca cria diretório nem banco."""
        entry = self.get(uid)
        if entry is None:
            raise MicrogridNotFound("A microrrede não existe mais no catálogo (pode ter sido excluída em outra sessão).")
        try:
            return MicrogridStore(self.dir_for(uid), must_exist=True, fixed_uid=uid, incarnation=entry.incarnation)
        except MissingStoreError:
            raise MicrogridNotFound("O armazenamento da microrrede não foi encontrado (excluída em outra sessão?).") from None

    def meta(self, key: str) -> str | None:
        with self._read() as con:
            row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    # ------------------------------------------------------------ confirmação de uma nova entrada
    def _commit_new(self, uid: str, build: Callable[[MicrogridStore], Stored], *, origin: str,
                    source_uid: str | None = None, source_fingerprint: str | None = None, note: str = "",
                    on_commit: Callable[[sqlite3.Connection], None] | None = None) -> Stored:
        """Prepara a microrrede em ``.staging`` (``build``), depois confirma: rename + INSERT sob o bloqueio
        do catálogo. Qualquer falha antes do COMMIT deixa o catálogo inalterado."""
        uid = _check_uid(uid)
        staging = self._new_staging()
        try:
            result = build(MicrogridStore(staging, fixed_uid=uid))
            prepared = MicrogridStore(staging, must_exist=True, fixed_uid=uid)
            check = prepared.load()
            if check is None or check.config["installation"]["uid"] != uid:
                raise RegistryError("Preparação da microrrede inconsistente; nada foi registrado.")
            incarnation = prepared.stamp_incarnation(uuid.uuid4().hex)
            target = self.dir_for(uid)
            con = self._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                if con.execute("SELECT 1 FROM microgrids WHERE uid = ?", (uid,)).fetchone():
                    raise RegistryError("Já existe uma microrrede com esta identidade no catálogo.")
                if target.exists():                       # órfão de operação interrompida (sem linha no catálogo)
                    self._move_to_trash(target, quarantine=True)
                os.rename(staging, target)
                try:
                    con.execute("INSERT INTO microgrids(uid, state, origin, created_at, source_uid, source_fingerprint, note, "
                                "incarnation) VALUES (?,?,?,?,?,?,?,?)", (uid, "ready", origin, C.utc_now(), source_uid,
                                                                          source_fingerprint, note[:500], incarnation))
                    if on_commit is not None:
                        on_commit(con)
                    con.execute("COMMIT")
                except BaseException:
                    if con.in_transaction:
                        con.execute("ROLLBACK")
                    if target.exists() and not staging.exists():
                        os.rename(target, staging)        # desfaz a confirmação no sistema de arquivos
                    raise
            except BaseException:
                if con.in_transaction:
                    con.execute("ROLLBACK")
                raise
            finally:
                con.close()
            return result
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            self._purge_trash()

    # ------------------------------------------------------------ criar
    def create(self, config: dict, *, note: str = "Comissionamento: identificação e localização",
               origin: str = "commissioning") -> Stored:
        """Registra uma NOVA microrrede com a primeira revisão de ``config`` (identidade = installation.uid)."""
        uid = str((config.get("installation") or {}).get("uid", ""))
        if self.get(uid) is not None:
            raise RegistryError("Já existe uma microrrede com esta identidade no catálogo.")
        return self._commit_new(uid, lambda s: s.save(config, 0, note=note, origin=origin), origin="new")

    # ------------------------------------------------------------ importar
    def inspect(self, data: bytes) -> tuple[BackupInspection, Entry | None]:
        """Inspeção de um backup NÃO confiável + coincidência de identidade com o catálogo."""
        rep = inspect_backup_data(data)
        existing = self.get(rep.config["installation"]["uid"]) if rep.ok else None
        return rep, existing

    def import_new(self, data: bytes) -> tuple[str, Stored]:
        """Importa como NOVA entrada preservando a identidade do backup (que não pode existir no catálogo)."""
        rep, existing = self.inspect(data)
        if not rep.ok:
            raise RegistryError("Backup rejeitado: " + " | ".join(rep.errors))
        if existing is not None:
            raise RegistryError("Esta microrrede já existe no catálogo: escolha restaurá-la ou importar uma cópia independente.")
        uid = rep.config["installation"]["uid"]
        m = rep.manifest
        note = (f"Importada do backup de {str(m.get('created_at'))[:40]} (revisão {m.get('revision')} da origem, "
                f"{str(m.get('fingerprint'))[:12]}…)" + (" — migrada do formato anterior" if rep.migrated else ""))
        stored = self._commit_new(uid, lambda s: s.import_inspected(rep, note=note, origin="import"), origin="import",
                                  source_fingerprint=m.get("fingerprint"), note=note)
        return uid, stored

    def import_copy(self, data: bytes) -> tuple[str, Stored]:
        """Importa como CÓPIA INDEPENDENTE: nova identidade; UID e impressão digital de origem registrados."""
        rep, _ = self.inspect(data)
        if not rep.ok:
            raise RegistryError("Backup rejeitado: " + " | ".join(rep.errors))
        src_uid = rep.config["installation"]["uid"]
        m = rep.manifest
        new_uid = uuid.uuid4().hex
        note = (f"Cópia independente da microrrede {src_uid} (revisão {m.get('revision')}, "
                f"{str(m.get('fingerprint'))[:12]}…). Não representa a mesma instalação física.")
        stored = self._commit_new(new_uid, lambda s: s.import_inspected(rep, new_uid=new_uid, note=note, origin="import"),
                                  origin="copy", source_uid=src_uid, source_fingerprint=m.get("fingerprint"), note=note)
        return new_uid, stored

    def restore_into(self, uid: str, data: bytes, expected_revision: int) -> Stored:
        """Restaura o backup na microrrede EXISTENTE de mesma identidade (nova revisão; histórico preservado)."""
        store = self.open(uid)
        rep = store.inspect_backup(data)
        if not rep.ok:
            raise RegistryError("Backup rejeitado: " + " | ".join(rep.errors))
        if rep.config["installation"]["uid"] != uid:
            raise RegistryError("O backup pertence a outra microrrede; importe-o pelo Gestor.")
        return store.restore_backup(data, expected_revision, confirm=True)

    # ------------------------------------------------------------ excluir
    def delete(self, uid: str, *, expected_incarnation: str | None = None,
               lock_timeout_s: float = DELETE_LOCK_TIMEOUT_S) -> None:
        """Exclusão DEFINITIVA dos dados desta microrrede (configuração, revisões, blobs, rodadas, cópias).
        Somente o diretório ``microgrids/<uid>`` é removido; o restante do catálogo não é tocado.

        Protocolo H-01/H-02 (sem bloqueios aninhados), VINCULADO a uma incarnação (a informada em
        ``expected_incarnation`` — p. ex. a que o usuário via ao confirmar — ou a atual do catálogo):
        lápide sob L2 conferindo a incarnação do banco → reivindicação sob L1 conferindo a do catálogo (um único
        vencedor) → remoção física sob L1 conferindo ambas. Uma exclusão obsoleta (a microrrede foi excluída e
        reimportada com o mesmo UID no meio) falha com ``StaleDeletionError`` sem alterar a nova."""
        uid = _check_uid(uid)
        entry = self.get(uid)
        if entry is None:
            raise MicrogridNotFound("A microrrede não existe mais no catálogo.")
        if entry.incarnation is None:                           # entrada anterior ao H-01 ainda sem incarnação
            self._backfill_one(uid)
            entry = self.get(uid)
            if entry is None or entry.incarnation is None:
                raise RegistryError("Não foi possível identificar a incarnação desta microrrede; nada foi excluído.")
        inc = entry.incarnation
        if expected_incarnation is not None and expected_incarnation != inc:
            raise StaleDeletionError("A microrrede com este identificador foi substituída por outra (excluída e "
                                     "reimportada); nada foi excluído.")
        self._tombstone(uid, incarnation=inc, timeout_s=lock_timeout_s)   # (1) L2 — início efetivo da exclusão
        with self._tx() as con:                                            # (2) L1 — um único vencedor
            cur = con.execute("UPDATE microgrids SET state = 'deleting' WHERE uid = ? AND state = 'ready' "
                              "AND incarnation = ?", (uid, inc))
            if cur.rowcount != 1:
                row = con.execute("SELECT incarnation FROM microgrids WHERE uid = ?", (uid,)).fetchone()
                if row is not None and row["incarnation"] != inc:
                    raise StaleDeletionError("A microrrede com este identificador foi substituída por outra; nada foi "
                                             "excluído.")
                raise MicrogridNotFound("A microrrede já foi excluída (por outra operação).")
        self._finish_deletion(uid, inc)                                    # (3) L1 — remoção física

    def _finish_deletion(self, uid: str, incarnation: str | None) -> None:
        """Remoção física SOMENTE da incarnação cuja exclusão foi confirmada: linha ``deleting`` com essa
        incarnação e diretório cujo banco é dessa incarnação (ou já ausente)."""
        with self._tx() as con:
            row = con.execute("SELECT state, incarnation FROM microgrids WHERE uid = ?", (uid,)).fetchone()
            if row is not None and row["state"] == "deleting" and row["incarnation"] == incarnation:
                if not self._dir_matches(uid, incarnation):
                    raise RegistryError("O diretório da microrrede pertence a outra incarnação; nada foi removido.")
                self._move_to_trash(self.dir_for(uid))
                con.execute("DELETE FROM microgrids WHERE uid = ? AND state = 'deleting' AND incarnation IS ?",
                            (uid, incarnation))
        self._purge_trash()

    # ------------------------------------------------------------ adoção do armazenamento anterior ao Gestor
    def adopt_legacy(self) -> str | None:
        """Adota ``SEEDS2_DATA_DIR/seeds2.db`` (uma microrrede do Piso 1) como entrada do catálogo, UMA vez.

        Idempotente (marcada em ``meta``), segura entre processos (bloqueio do catálogo), recuperável (nada é
        confirmado antes da verificação) e compatível com WAL (cópia pela API de backup). O arquivo anterior
        nunca é modificado. Devolve o UID adotado (ou None)."""
        legacy = self.root / LEGACY_FILENAME
        if not legacy.is_file() or self.meta("legacy_adoption"):
            return None
        staging = self._new_staging()
        try:
            con = self._connect()
            try:
                con.execute("BEGIN IMMEDIATE")              # serializa: só um processo adota
                if con.execute("SELECT 1 FROM meta WHERE key = 'legacy_adoption'").fetchone():
                    con.execute("ROLLBACK")
                    return None
                uid, info = self._prepare_legacy(legacy, staging)
                if uid is None:
                    con.execute("INSERT INTO meta(key, value) VALUES ('legacy_adoption', ?)",
                                (json.dumps({"state": "empty", "at": C.utc_now(), "source": str(legacy)}),))
                    con.execute("COMMIT")
                    return None
                marker = json.dumps({"state": "done", "uid": uid, "at": C.utc_now(), "source": str(legacy), **info})
                if con.execute("SELECT 1 FROM microgrids WHERE uid = ?", (uid,)).fetchone():
                    con.execute("INSERT INTO meta(key, value) VALUES ('legacy_adoption', ?)", (marker,))
                    con.execute("COMMIT")
                    return uid
                incarnation = MicrogridStore(staging, must_exist=True, fixed_uid=uid).stamp_incarnation(uuid.uuid4().hex)
                target = self.dir_for(uid)
                if target.exists():
                    self._move_to_trash(target, quarantine=True)
                os.rename(staging, target)
                try:
                    note = (f"Adotada do armazenamento anterior ao Gestor ({LEGACY_FILENAME}, revisão "
                            f"{info['legacy_revision']}); o arquivo original foi mantido intacto.")
                    con.execute("INSERT INTO microgrids(uid, state, origin, created_at, source_uid, source_fingerprint, note, "
                                "incarnation) VALUES (?,?,?,?,?,?,?,?)", (uid, "ready", "legacy", C.utc_now(), None,
                                                                          info["legacy_fingerprint"], note, incarnation))
                    con.execute("INSERT INTO meta(key, value) VALUES ('legacy_adoption', ?)", (marker,))
                    con.execute("COMMIT")
                except BaseException:
                    if con.in_transaction:
                        con.execute("ROLLBACK")
                    if target.exists() and not staging.exists():
                        os.rename(target, staging)
                    raise
                return uid
            except LegacyAdoptionError:
                raise
            except Exception as exc:  # noqa: BLE001 — qualquer falha: arquivo anterior intacto, nada confirmado
                raise LegacyAdoptionError(
                    f"Não foi possível migrar o armazenamento anterior ({legacy}). Os dados antigos foram mantidos "
                    f"intactos; nenhuma microrrede foi criada. Detalhe: {exc}") from None
            finally:
                if con.in_transaction:
                    con.execute("ROLLBACK")
                con.close()
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            self._purge_trash()

    @staticmethod
    def _counts(db: Path) -> dict:
        con = sqlite3.connect(db)
        try:
            row = con.execute("SELECT installation_uid, revision, fingerprint FROM microgrid WHERE id = 1").fetchone()
            return {"row": row, "user_version": int(con.execute("PRAGMA user_version").fetchone()[0]),
                    "revisions": con.execute("SELECT count(*) FROM revisions").fetchone()[0],
                    "blobs": con.execute("SELECT count(*) FROM blobs").fetchone()[0],
                    "runs": con.execute("SELECT count(*) FROM simulation_runs").fetchone()[0]}
        finally:
            con.close()

    def _prepare_legacy(self, legacy: Path, staging: Path) -> tuple[str | None, dict]:
        """Cópia consistente do banco anterior em ``staging`` + migração da CÓPIA + verificação."""
        copy_db = staging / DB_FILENAME
        sqlite_backup_copy(legacy, copy_db, read_only=True)          # o arquivo anterior não é modificado
        try:
            before = self._counts(copy_db)
        except sqlite3.DatabaseError as exc:
            raise LegacyAdoptionError(f"O armazenamento anterior ({legacy}) não é um banco do SEEDS2 legível: {exc}") from None
        if before["row"] is None:
            return None, {}
        uid = before["row"][0]
        if not valid_uid(uid):
            raise LegacyAdoptionError(f"O armazenamento anterior tem identidade inválida ({str(uid)[:40]!r}); nada foi adotado.")
        store = MicrogridStore(staging, must_exist=True, fixed_uid=uid)     # migra a CÓPIA (cria .bak-v<N> na cópia)
        cur = store.load()
        after = self._counts(copy_db)
        if cur is None or cur.config["installation"]["uid"] != uid:
            raise LegacyAdoptionError("A cópia migrada não contém a mesma microrrede; nada foi adotado.")
        if after["revisions"] < before["revisions"] or after["blobs"] != before["blobs"] or after["runs"] != before["runs"]:
            raise LegacyAdoptionError("A verificação da cópia migrada falhou (revisões, dados de entrada ou rodadas "
                                      "divergentes); nada foi adotado.")
        return uid, {"legacy_revision": int(before["row"][1]), "legacy_fingerprint": before["row"][2],
                     "legacy_db_version": before["user_version"], "revisions": before["revisions"],
                     "blobs": before["blobs"], "runs": before["runs"]}


# ============================================================================ resumo para o Gestor
def card_summary(stored: Stored | None) -> dict:
    """Dados de UMA tarjeta do Gestor, calculados da configuração salva. Nada é inventado: grandezas
    ausentes ficam ``None``; potências declaradas e calculadas são somadas apenas quando têm a mesma natureza
    (kWp nominal STC/declarado da FV) e a base é informada."""
    from . import adapter as A
    from .derived import battery_derived, pv_plant_summary
    from .references import KIND_LABELS

    if stored is None:
        return {"empty": True}
    cfg = stored.config
    inst = cfg.get("installation") or {}
    eqs = cfg.get("equipment") or []
    by = {k: [e for e in eqs if e.get("kind") == k] for k in ("pv", "wind", "battery", "pemfc", "thermal")}
    pv = [pv_plant_summary(e) for e in by["pv"]]
    pv_comp = sum(s["computed_kWp"] for s in pv)
    pv_decl = sum(s["declared_kWp"] for s in pv)
    wind_kw = [C.installed_power_kW(e) for e in by["wind"]]
    bat_parts = {"declarada": 0.0, "derivada": 0.0, "modelo": 0.0}
    for e in by["battery"]:
        v, basis, _ = battery_derived(e.get("params") or {})["energy_kWh"]
        if v is not None:
            bat_parts["declarada" if basis == "declarada" else "derivada"] += v
        else:
            m = C.battery_model_energy_kWh(e)
            if m is not None:
                bat_parts["modelo"] += m
    loc = inst.get("location") or {}
    commissioned = bool((cfg.get("commissioning") or {}).get("completed"))
    plan = A.build_plan(cfg, revision=stored.revision, fingerprint=stored.fingerprint)
    pending = [e for e in eqs if e.get("enabled", True) and not C.is_configured(e)]
    ident_missing = C.identification_missing(cfg)
    if not commissioned:
        state = "configuracao"
    elif pending or ident_missing or not plan.runnable:
        state = "atencao"
    else:
        state = "ativa"
    attention = ([f"{len(pending)} equipamento(s) com configuração pendente"] if pending else []) + \
                ([f"identificação incompleta: {', '.join(ident_missing).lower()}"] if ident_missing else [])
    if not plan.runnable:
        ems = ("bloqueada", "; ".join(plan.blockers)[:200])
    elif plan.excluded:
        ems = ("parcial", f"{len(plan.represented)} representado(s) · {len(plan.excluded)} fora da rodada")
    else:
        ems = ("pronta", f"{len(plan.represented)} representado(s) no EMS")
    return {
        "empty": False,
        "uid": inst.get("uid"),
        "name": inst.get("name") or "",
        "description": inst.get("description") or "",
        "nature": C.NATURE_OPTIONS.get(inst.get("nature")),
        "operation_mode": C.OPERATION_MODE_OPTIONS.get(inst.get("operation_mode")),
        "location": ", ".join(x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x) or
                    (loc.get("address") or None) or
                    (f"{loc['latitude']:.4f}, {loc['longitude']:.4f}" if loc.get("latitude") is not None and
                     loc.get("longitude") is not None else None),
        "technologies": [KIND_LABELS[k] for k, v in by.items() if v],
        "n_equipment": len(eqs),
        "pv_kWp": (pv_comp + pv_decl) if (by["pv"] and any(s["n_computed"] or s["n_declared"] for s in pv)) else None,
        "pv_computed_kWp": pv_comp, "pv_declared_kWp": pv_decl,
        "wind_kW": sum(w for w in wind_kw if w) if any(wind_kw) else None,
        "storage_kWh": sum(bat_parts.values()) if any(bat_parts.values()) else None,
        "storage_basis": [k for k, v in bat_parts.items() if v],
        "commissioned": commissioned,
        "commissioning_step": int((cfg.get("commissioning") or {}).get("step") or 1),
        "state": state,
        "attention": attention,
        "ems": ems,
        "revision": stored.revision,
        "fingerprint": stored.fingerprint,
        "saved_at": stored.saved_at,
        "copied_from": inst.get("copied_from"),
    }


STATE_LABELS = {"configuracao": "Em configuração", "ativa": "Ativa", "atencao": "Atenção"}
EMS_LABELS = {"pronta": "Pronta para simulação", "parcial": "Simulação parcial", "bloqueada": "Simulação bloqueada"}

__all__ = ["Entry", "LegacyAdoptionError", "MicrogridNotFound", "MicrogridRegistry", "RegistryError", "StaleDeletionError",
           "card_summary",
           "valid_uid", "EMS_LABELS", "STATE_LABELS", "ORIGIN_LABELS"]
