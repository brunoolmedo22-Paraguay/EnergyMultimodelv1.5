"""Persistência local (SQLite) da ÚNICA microrrede desta instalação do SEEDS2.

Decisões (detalhadas em docs/seeds2/ARMAZENAMENTO.md):

* **Uma microrred por banco:** a tabela ``microgrid`` tem ``CHECK (id = 1)``; não existe
  noção de "projetos". A identidade (``installation_uid``) é preservada entre edições.
* **Revisões imutáveis:** cada salvamento grava um *snapshot* completo em ``revisions``
  (append-only, protegido por *triggers*). Nada é sobrescrito sem deixar rastro.
* **Concorrência otimista:** ``save`` exige a revisão-base; se outra sessão salvou antes,
  levanta ``ConflictError`` em vez de sobrescrever (proteção contra perda de alterações).
* **Transações:** escritas com ``BEGIN IMMEDIATE`` + WAL + ``busy_timeout``.
* **Esquema versionado:** ``PRAGMA user_version`` + lista ordenada de migrações; antes de
  migrar um banco existente, copia-se o arquivo (``.bak-v<N>``). Banco mais novo que o
  software é recusado.
* **Local:** diretório configurável por ``SEEDS2_DATA_DIR`` (padrão ``~/.seeds2``), fora do
  código versionado.
"""
from __future__ import annotations

import io
import json
import os
import re
import sqlite3
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator

from . import config as C
from .migrations import MigrationError, migrate_document

DB_FILENAME = "seeds2.db"
ENV_DATA_DIR = "SEEDS2_DATA_DIR"
BACKUP_FORMAT = "seeds2-microgrid-backup"
BACKUP_FORMAT_VERSION = 2
SUPPORTED_BACKUP_FORMATS = (1, 2)          # v1 = Piso 1 original (documento v1, migrado na importação)
SUPPORTED_DOC_VERSIONS = (1, 2)
BACKUP_SUFFIX = ".seeds2backup.zip"
MAX_BLOB_BYTES = 50 * 1024 * 1024
BACKUP_COPY_TIMEOUT_S = 30.0               # espera máxima por bloqueios ao copiar o banco antes de migrar
# Limites da importação de backup (arquivo NÃO confiável). Dados referenciados: CSVs de demanda e clima e
# pacotes de dispositivos importados do ModelLab; o total descomprimido é contado lendo os dados, não pelo
# tamanho declarado no ZIP.
MAX_BACKUP_ENTRIES = 64
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_BACKUP_UNCOMPRESSED = 256 * 1024 * 1024
MAX_BACKUP_BYTES = MAX_BACKUP_UNCOMPRESSED
_READ_CHUNK = 1024 * 1024
_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_JSON_ENTRIES = ("manifest.json", "configuration.json", "history.json")


class _BackupRejected(Exception):
    """Rejeição controlada de um backup (mensagem apresentável)."""


def _allowed_entry(name: str) -> bool:
    return name in _JSON_ENTRIES or (name.startswith("blobs/") and bool(_HEX64.fullmatch(name[6:])))


def _entry_cap(name: str) -> int:
    return MAX_JSON_BYTES if name in _JSON_ENTRIES else MAX_BLOB_BYTES

# ------------------------------------------------------------------ migrações do banco
MIGRATIONS: list[tuple[int, list[str]]] = [
    (1, [
        """CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
        """CREATE TABLE microgrid (
               id INTEGER PRIMARY KEY CHECK (id = 1),
               installation_uid TEXT NOT NULL,
               revision INTEGER NOT NULL CHECK (revision >= 1),
               fingerprint TEXT NOT NULL,
               document TEXT NOT NULL,
               saved_at TEXT NOT NULL)""",
        """CREATE TABLE revisions (
               revision INTEGER PRIMARY KEY,
               installation_uid TEXT NOT NULL,
               fingerprint TEXT NOT NULL,
               document TEXT NOT NULL,
               saved_at TEXT NOT NULL,
               note TEXT NOT NULL DEFAULT '',
               origin TEXT NOT NULL DEFAULT 'edit')""",
        """CREATE TRIGGER revisions_immutable_u BEFORE UPDATE ON revisions
               BEGIN SELECT RAISE(ABORT, 'revisões são imutáveis'); END""",
        """CREATE TRIGGER revisions_immutable_d BEFORE DELETE ON revisions
               BEGIN SELECT RAISE(ABORT, 'revisões são imutáveis'); END""",
        """CREATE TABLE blobs (
               sha256 TEXT PRIMARY KEY,
               name TEXT NOT NULL DEFAULT '',
               media_type TEXT NOT NULL DEFAULT 'application/octet-stream',
               size INTEGER NOT NULL,
               content BLOB NOT NULL,
               created_at TEXT NOT NULL)""",
        """CREATE TABLE simulation_runs (
               run_id INTEGER PRIMARY KEY AUTOINCREMENT,
               created_at TEXT NOT NULL,
               config_revision INTEGER,
               config_fingerprint TEXT,
               spec_fingerprint TEXT NOT NULL,
               spec_origin TEXT NOT NULL,
               excluded TEXT NOT NULL DEFAULT '[]',
               summary TEXT NOT NULL DEFAULT '{}')""",
    ]),
    # v2 (refinamento do Piso 1): sem mudança de tabelas; o documento atual é migrado (v1 → v2) e gravado
    # como NOVA revisão (origem "migration"). Revisões antigas permanecem intactas e são migradas na leitura.
    (2, []),
]
LATEST_DB_VERSION = MIGRATIONS[-1][0]


def _migrate_current_document(con: sqlite3.Connection) -> None:
    row = con.execute("SELECT * FROM microgrid WHERE id = 1").fetchone()
    if row is None:
        return
    doc = json.loads(row["document"])
    try:
        new, applied = migrate_document(doc)
    except MigrationError as exc:
        raise StoreError(f"Migração do documento falhou (banco mantido na versão anterior): {exc}") from None
    if not applied:
        return
    issues = C.errors(C.validate(new))
    if issues:
        raise StoreError("Migração do documento não validou (banco mantido na versão anterior): "
                         + "; ".join(f"{i.path}: {i.message}" for i in issues[:5]))
    text = json.dumps(new, ensure_ascii=False)
    fp, now, rev = C.fingerprint(new), C.utc_now(), int(row["revision"]) + 1
    note = f"Migração automática do documento v{doc.get('schema_version')} → v{new['schema_version']}: " + \
           "; ".join(applied[-1]["notes"])[:900]
    con.execute("INSERT INTO revisions(revision, installation_uid, fingerprint, document, saved_at, note, origin) "
                "VALUES (?,?,?,?,?,?,?)", (rev, row["installation_uid"], fp, text, now, note, "migration"))
    con.execute("UPDATE microgrid SET revision=?, fingerprint=?, document=?, saved_at=? WHERE id = 1", (rev, fp, text, now))


MIGRATION_STEPS = {2: _migrate_current_document}


class StoreError(Exception):
    """Erro de persistência com mensagem apresentável ao usuário."""


class ConflictError(StoreError):
    def __init__(self, expected: int, current: int):
        super().__init__(f"A configuração foi alterada por outra sessão (revisão base {expected}, atual {current}). "
                         "Recarregue antes de salvar; nada foi sobrescrito.")
        self.expected, self.current = expected, current


class ValidationError(StoreError):
    def __init__(self, issues: list[C.Issue]):
        super().__init__("Configuração inválida: " + "; ".join(f"{i.path}: {i.message}" for i in issues[:8]))
        self.issues = issues


class IdentityError(StoreError):
    pass


class MissingStoreError(StoreError):
    """O banco da microrrede não existe (p. ex. excluída por outra sessão)."""


@dataclass(frozen=True)
class Stored:
    config: dict
    revision: int
    fingerprint: str
    saved_at: str


@dataclass
class BackupInspection:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)
    config: dict | None = None
    blobs: dict[str, tuple[bytes, dict]] = field(default_factory=dict)
    same_installation: bool | None = None
    migrated: bool = False


def resolve_data_dir(explicit: str | os.PathLike | None = None) -> Path:
    raw = explicit or os.environ.get(ENV_DATA_DIR) or (Path.home() / ".seeds2")
    return Path(raw).expanduser().resolve()


def ensure_wal(con: sqlite3.Connection, timeout_s: float = 15.0) -> None:
    """Ativa o modo WAL somente se ainda não estiver ativo. A troca de modo numa base recém-criada pode
    responder "database is locked" SEM passar pelo ``busy_timeout`` quando várias conexões abrem ao mesmo
    tempo; repete com espera limitada (o modo é persistente: só a primeira conexão precisa trocá-lo)."""
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            if str(con.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal":
                con.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or time.monotonic() > deadline:
                raise
            time.sleep(0.05)


def sqlite_backup_copy(source: Path, dest: Path, timeout_s: float = BACKUP_COPY_TIMEOUT_S, *,
                       read_only: bool = False) -> None:
    """Cópia transacionalmente consistente do banco pela API de backup do SQLite.

    Inclui o conteúdo ainda no ``-wal`` (uma cópia do arquivo ``.db`` não o inclui). Usa uma conexão PRÓPRIA,
    sem transação aberta: em WAL ela só precisa de um instantâneo de leitura, compatível com o bloqueio de
    escrita mantido pela migração. ``pages=-1`` copia tudo num único passo (um único instantâneo). A espera
    por bloqueios é limitada (o laço de repetição do ``Connection.backup`` seria infinito). O resultado é
    um arquivo autossuficiente (journal DELETE, sem ``-wal``/``-shm``), verificado e publicado atomicamente.
    ``read_only``: a origem é aberta somente para leitura (``mode=ro``) — nenhum checkpoint é feito nela; usado
    para adotar o armazenamento anterior ao Gestor sem alterar o arquivo original."""
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.unlink(missing_ok=True)
    deadline = time.monotonic() + timeout_s

    def progress(_status: int, _remaining: int, _total: int) -> None:
        if time.monotonic() > deadline:
            raise StoreError("tempo esgotado ao copiar o banco (bloqueado por outra conexão)")

    src = (sqlite3.connect(f"file:{Path(source).as_posix()}?mode=ro", uri=True, timeout=timeout_s, isolation_level=None)
           if read_only else sqlite3.connect(source, timeout=timeout_s, isolation_level=None))
    try:
        dst = sqlite3.connect(tmp, isolation_level=None)
        try:
            src.backup(dst, pages=-1, progress=progress, sleep=0.05)
            dst.execute("PRAGMA journal_mode=DELETE")
            check = dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            dst.close()
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        src.close()
    if check != "ok":
        tmp.unlink(missing_ok=True)
        raise StoreError(f"cópia de segurança não passou na verificação de integridade: {check}")
    with open(tmp, "rb") as fh:
        os.fsync(fh.fileno())
    os.replace(tmp, dest)



class MicrogridStore:
    """Armazenamento SQLite de UMA microrrede (um diretório, um ``seeds2.db``).

    * ``must_exist``: não cria diretório nem banco — usado pelo catálogo para abrir microrredes existentes
      (uma microrrede excluída nunca é recriada vazia por uma sessão que ainda a referencie);
    * ``fixed_uid``: identidade imutável do armazenamento; qualquer gravação de documento de outra
      instalação é recusada (mesmo com ``allow_identity_change``), mantendo catálogo, diretório e documento
      coerentes."""

    def __init__(self, data_dir: str | os.PathLike | None = None, *, must_exist: bool = False,
                 fixed_uid: str | None = None):
        self.data_dir = resolve_data_dir(data_dir)
        self.path = self.data_dir / DB_FILENAME
        self.fixed_uid = fixed_uid
        if must_exist:
            if not self.path.is_file():
                raise MissingStoreError(f"Armazenamento da microrrede não encontrado em {self.data_dir}.")
        else:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        self._migrate()

    # ------------------------------------------------------------ conexão / migração
    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        con.row_factory = sqlite3.Row
        ensure_wal(con)
        con.execute("PRAGMA busy_timeout=10000")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.execute("COMMIT")
        except BaseException:
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

    def db_version(self) -> int:
        with self._read() as con:
            return int(con.execute("PRAGMA user_version").fetchone()[0])

    def _backup_copy(self, dest: Path, timeout_s: float = BACKUP_COPY_TIMEOUT_S) -> None:
        sqlite_backup_copy(self.path, dest, timeout_s)

    def _migrate(self) -> None:
        existed = self.path.exists() and self.path.stat().st_size > 0
        with self._read() as con:
            current = int(con.execute("PRAGMA user_version").fetchone()[0])
        if current > LATEST_DB_VERSION:
            raise StoreError(f"O banco {self.path} usa o esquema v{current}, mais novo que este software "
                             f"(v{LATEST_DB_VERSION}). Atualize o SEEDS2; o banco não foi alterado.")
        if not any(v > current for v, _ in MIGRATIONS):
            return
        # Uma única transação de escrita para cópia + todas as migrações pendentes:
        # * BEGIN IMMEDIATE garante que nenhuma outra conexão grave entre a cópia e a migração (a cópia é
        #   exatamente o estado migrado) e serializa aberturas concorrentes;
        # * a versão é relida sob o bloqueio (outra conexão pode ter migrado antes) → idempotente;
        # * qualquer falha desfaz tudo (rollback): o banco permanece na versão anterior.
        con = self._connect()
        try:
            try:
                con.execute("BEGIN IMMEDIATE")
                current = int(con.execute("PRAGMA user_version").fetchone()[0])
                pending = [(v, stmts) for v, stmts in MIGRATIONS if v > current]
                if not pending:
                    con.execute("ROLLBACK")
                    return
                if existed and current > 0:
                    self._backup_copy(self.path.with_name(f"{self.path.name}.bak-v{current}"))
                for version, stmts in pending:
                    for s in stmts:
                        con.execute(s)
                    step = MIGRATION_STEPS.get(version)
                    if step is not None:
                        step(con)
                    con.execute(f"PRAGMA user_version = {int(version)}")
                    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('migrated_to', ?)", (str(version),))
                    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('migrated_at', ?)", (C.utc_now(),))
                con.execute("COMMIT")
            except BaseException:
                if con.in_transaction:
                    con.execute("ROLLBACK")
                raise
        except sqlite3.Error as exc:
            raise StoreError(f"Migração do banco interrompida (banco mantido na versão anterior): {exc}") from None
        except StoreError as exc:
            msg = str(exc)
            if "banco mantido na versão anterior" not in msg:
                msg = f"Migração do banco interrompida (banco mantido na versão anterior): {msg}"
            raise StoreError(msg) from None
        finally:
            con.close()

    # ------------------------------------------------------------ leitura
    def load(self) -> Stored | None:
        with self._read() as con:
            row = con.execute("SELECT * FROM microgrid WHERE id = 1").fetchone()
        if row is None:
            return None
        return Stored(json.loads(row["document"]), int(row["revision"]), row["fingerprint"], row["saved_at"])

    def is_commissioned(self) -> bool:
        s = self.load()
        return bool(s and s.config.get("commissioning", {}).get("completed"))

    def history(self, limit: int = 50) -> list[dict]:
        with self._read() as con:
            rows = con.execute("SELECT revision, fingerprint, saved_at, note, origin FROM revisions "
                               "ORDER BY revision DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def get_revision(self, revision: int) -> Stored:
        with self._read() as con:
            row = con.execute("SELECT * FROM revisions WHERE revision = ?", (int(revision),)).fetchone()
        if row is None:
            raise StoreError(f"Revisão {revision} inexistente.")
        doc = json.loads(row["document"])
        try:
            doc, _ = migrate_document(doc)       # revisões antigas permanecem gravadas como estavam
        except MigrationError as exc:
            raise StoreError(f"Revisão {revision}: {exc}") from None
        return Stored(doc, int(row["revision"]), row["fingerprint"], row["saved_at"])

    # ------------------------------------------------------------ escrita
    @staticmethod
    def _referenced_blobs(config: Any) -> set[str]:
        """Hashes de blobs referenciados (tolerante a estruturas inválidas: o que não for dict é ignorado)."""
        refs: set[str] = set()
        if not isinstance(config, dict):
            return refs
        for section in ("demand", "climate"):
            sec = config.get(section)
            csv = sec.get("csv") if isinstance(sec, dict) else None
            if isinstance(csv, dict) and isinstance(csv.get("blob"), str) and csv["blob"]:
                refs.add(csv["blob"])
        for section in ("equipment", "retired"):
            items = config.get(section)
            for eq in items if isinstance(items, list) else []:
                imp = eq.get("imported") if isinstance(eq, dict) else None
                if isinstance(imp, dict) and isinstance(imp.get("blob"), str) and imp["blob"]:
                    refs.add(imp["blob"])
        return refs

    @staticmethod
    def _insert_blob(con: sqlite3.Connection, content: bytes, name: str, media_type: str) -> str:
        if len(content) > MAX_BLOB_BYTES:
            raise StoreError(f"Arquivo maior que {MAX_BLOB_BYTES // (1024 * 1024)} MB.")
        h = sha256(content).hexdigest()
        con.execute("INSERT OR IGNORE INTO blobs(sha256, name, media_type, size, content, created_at) "
                    "VALUES (?,?,?,?,?,?)", (h, str(name), str(media_type), len(content), content, C.utc_now()))
        return h

    @staticmethod
    def _prepare(config: dict) -> tuple[dict, str]:
        issues = C.validate(config)
        if C.errors(issues):
            raise ValidationError(C.errors(issues))
        doc = json.loads(C.canonical_json(config))           # cópia normalizada e serializável
        return doc, C.fingerprint(doc)

    def _write_revision(self, con: sqlite3.Connection, doc: dict, fp: str, expected_revision: int, *, note: str,
                        origin: str, allow_identity_change: bool,
                        new_blobs: dict[str, tuple[bytes, dict]] | None = None) -> Stored:
        """Núcleo transacional: DEVE ser chamado dentro de ``_tx``. Qualquer exceção desfaz TUDO
        (inclusive os blobs inseridos aqui)."""
        uid = doc["installation"]["uid"]
        row = con.execute("SELECT installation_uid, revision, fingerprint, saved_at FROM microgrid WHERE id = 1").fetchone()
        current = int(row["revision"]) if row else 0
        if int(expected_revision) != current:
            raise ConflictError(int(expected_revision), current)
        if self.fixed_uid is not None and uid != self.fixed_uid:
            raise IdentityError("A configuração pertence a outra microrrede do catálogo. Para trazê-la, use "
                                "IMPORTAR MICRORREDE (ZIP) no Gestor de microrredes.")
        if row and row["installation_uid"] != uid and not allow_identity_change:
            raise IdentityError("A configuração pertence a outra instalação. Use a restauração de backup com "
                                "confirmação explícita.")
        for digest, (content, meta) in (new_blobs or {}).items():
            if self._insert_blob(con, content, meta.get("name", ""), meta.get("media_type", "text/csv")) != digest:
                raise StoreError("Falha de integridade ao gravar dados de entrada.")
        missing = [b for b in self._referenced_blobs(doc)
                   if con.execute("SELECT 1 FROM blobs WHERE sha256 = ?", (b,)).fetchone() is None]
        if missing:
            raise StoreError(f"Dados de entrada referenciados não estão armazenados: {missing}")
        if row and row["fingerprint"] == fp:
            return Stored(doc, current, fp, row["saved_at"])
        now = C.utc_now()
        rev = current + 1
        text = json.dumps(doc, ensure_ascii=False)
        con.execute("INSERT INTO revisions(revision, installation_uid, fingerprint, document, saved_at, note, origin) "
                    "VALUES (?,?,?,?,?,?,?)", (rev, uid, fp, text, now, str(note), str(origin)))
        con.execute("INSERT INTO microgrid(id, installation_uid, revision, fingerprint, document, saved_at) "
                    "VALUES (1,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET installation_uid=excluded.installation_uid, "
                    "revision=excluded.revision, fingerprint=excluded.fingerprint, document=excluded.document, "
                    "saved_at=excluded.saved_at", (uid, rev, fp, text, now))
        return Stored(doc, rev, fp, now)

    def save(self, config: dict, expected_revision: int, *, note: str = "", origin: str = "edit",
             allow_identity_change: bool = False) -> Stored:
        """Grava uma nova revisão se o conteúdo mudou. ``expected_revision`` = 0 para o primeiro salvamento."""
        doc, fp = self._prepare(config)
        with self._tx() as con:
            return self._write_revision(con, doc, fp, expected_revision, note=note, origin=origin,
                                        allow_identity_change=allow_identity_change)

    def revert_to(self, revision: int, expected_revision: int) -> Stored:
        old = self.get_revision(revision)
        return self.save(old.config, expected_revision, note=f"Reversão ao conteúdo da revisão {revision}", origin="revert")

    # ------------------------------------------------------------ blobs (dados de entrada)
    def put_blob(self, content: bytes, name: str = "", media_type: str = "text/csv") -> str:
        if len(content) > MAX_BLOB_BYTES:
            raise StoreError(f"Arquivo maior que {MAX_BLOB_BYTES // (1024 * 1024)} MB.")
        with self._tx() as con:
            return self._insert_blob(con, content, name, media_type)

    def get_blob(self, digest: str) -> bytes:
        with self._read() as con:
            row = con.execute("SELECT content FROM blobs WHERE sha256 = ?", (digest,)).fetchone()
        if row is None:
            raise StoreError(f"Dado de entrada {digest[:12]}… não encontrado no armazenamento local.")
        data = bytes(row["content"])
        if sha256(data).hexdigest() != digest:
            raise StoreError(f"Dado de entrada {digest[:12]}… corrompido (hash divergente).")
        return data

    def _blob_meta(self, con: sqlite3.Connection, digest: str) -> dict:
        row = con.execute("SELECT name, media_type, size, created_at FROM blobs WHERE sha256 = ?", (digest,)).fetchone()
        return dict(row) if row else {}

    # ------------------------------------------------------------ rodadas (procedência)
    def record_run(self, *, config_revision: int | None, config_fingerprint: str | None, spec_fingerprint: str,
                   spec_origin: str, excluded: list[dict], summary: dict) -> int:
        with self._tx() as con:
            cur = con.execute("INSERT INTO simulation_runs(created_at, config_revision, config_fingerprint, spec_fingerprint, "
                              "spec_origin, excluded, summary) VALUES (?,?,?,?,?,?,?)",
                              (C.utc_now(), config_revision, config_fingerprint, spec_fingerprint, spec_origin,
                               json.dumps(excluded, ensure_ascii=False), C.canonical_json(summary)))
            return int(cur.lastrowid)

    def runs(self, limit: int = 20) -> list[dict]:
        with self._read() as con:
            rows = con.execute("SELECT * FROM simulation_runs ORDER BY run_id DESC LIMIT ?", (int(limit),)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["excluded"] = json.loads(d["excluded"])
            d["summary"] = json.loads(d["summary"])
            out.append(d)
        return out

    # ------------------------------------------------------------ backup / restauração
    def export_backup(self) -> bytes:
        cur = self.load()
        if cur is None:
            raise StoreError("Não há configuração salva para exportar.")
        from seeds2 import APP_VERSION

        files: dict[str, bytes] = {"configuration.json": json.dumps(cur.config, ensure_ascii=False, indent=2).encode("utf-8")}
        blob_meta = {}
        with self._read() as con:
            for b in sorted(self._referenced_blobs(cur.config)):
                files[f"blobs/{b}"] = self.get_blob(b)
                blob_meta[b] = self._blob_meta(con, b)
        files["history.json"] = json.dumps(self.history(limit=10_000), ensure_ascii=False, indent=2).encode("utf-8")
        manifest = {
            "format": BACKUP_FORMAT, "format_version": BACKUP_FORMAT_VERSION,
            "db_schema_version": self.db_version(), "doc_schema_version": cur.config.get("schema_version"),
            "app_version": APP_VERSION, "created_at": C.utc_now(),
            "installation_uid": cur.config["installation"]["uid"], "installation_name": cur.config["installation"]["name"],
            "revision": cur.revision, "fingerprint": cur.fingerprint, "blobs": blob_meta,
            "files": {name: sha256(data).hexdigest() for name, data in files.items()},
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for name, data in files.items():
                zf.writestr(name, data)
        return buf.getvalue()

    # ------------------------------------------------------------ inspeção de backup (entrada NÃO confiável)
    @staticmethod
    def _read_capped(zf: zipfile.ZipFile, info: zipfile.ZipInfo, cap: int, budget: list[int]) -> bytes:
        """Lê uma entrada em blocos, sem confiar no tamanho declarado no ZIP (proteção contra zip bomb).
        ``budget`` = [bytes restantes no total descomprimido]."""
        out = bytearray()
        with zf.open(info) as fh:
            while True:
                chunk = fh.read(_READ_CHUNK)
                if not chunk:
                    break
                out += chunk
                budget[0] -= len(chunk)
                if len(out) > cap:
                    raise _BackupRejected(f"Entrada {info.filename!r} excede o limite de {cap // (1024 * 1024)} MiB descomprimidos.")
                if budget[0] < 0:
                    raise _BackupRejected(f"O conteúdo descomprimido excede o limite total de "
                                          f"{MAX_BACKUP_UNCOMPRESSED // (1024 * 1024)} MiB.")
        return bytes(out)

    @staticmethod
    def _manifest_errors(m: Any) -> list[str]:
        """Valida tipos e estrutura de TODOS os campos do manifesto antes de qualquer uso."""
        if not isinstance(m, dict):
            return ["manifest.json não contém um objeto."]
        errs: list[str] = []

        def is_int(v: Any) -> bool:
            return isinstance(v, int) and not isinstance(v, bool)

        def short_str(v: Any, n: int = 500) -> bool:
            return isinstance(v, str) and len(v) <= n

        if m.get("format") != BACKUP_FORMAT:
            return ["Formato não reconhecido: não é um backup de microrrede do SEEDS2."]
        if not is_int(m.get("format_version")) or m["format_version"] not in SUPPORTED_BACKUP_FORMATS:
            return ["Versão de formato de backup não suportada."]
        if not is_int(m.get("db_schema_version")) or not 1 <= m["db_schema_version"] <= LATEST_DB_VERSION:
            errs.append("Versão de esquema do banco ausente, inválida ou mais nova que este SEEDS2.")
        if not is_int(m.get("doc_schema_version")) or m["doc_schema_version"] not in SUPPORTED_DOC_VERSIONS:
            errs.append("Versão do documento de configuração ausente ou incompatível.")
        if not is_int(m.get("revision")) or m["revision"] < 1:
            errs.append("Campo 'revision' ausente ou inválido.")
        for key in ("app_version", "created_at", "installation_name"):
            if not short_str(m.get(key)):
                errs.append(f"Campo {key!r} ausente ou inválido.")
        if not (isinstance(m.get("installation_uid"), str) and _HEX32.fullmatch(m["installation_uid"])):
            errs.append("Campo 'installation_uid' ausente ou inválido.")
        if not (isinstance(m.get("fingerprint"), str) and _HEX64.fullmatch(m["fingerprint"])):
            errs.append("Campo 'fingerprint' ausente ou inválido.")
        files = m.get("files")
        if not isinstance(files, dict) or not files:
            errs.append("Campo 'files' ausente ou inválido.")
        else:
            for name, h in files.items():
                if not (isinstance(name, str) and _allowed_entry(name)):
                    errs.append("Campo 'files' lista uma entrada não permitida.")
                    break
                if not (isinstance(h, str) and _HEX64.fullmatch(h)):
                    errs.append("Campo 'files' contém hash inválido.")
                    break
            if "configuration.json" not in files:
                errs.append("Campo 'files' não inclui configuration.json.")
        blobs = m.get("blobs")
        if not isinstance(blobs, dict):
            errs.append("Campo 'blobs' ausente ou inválido.")
        else:
            for digest, meta in blobs.items():
                if not (isinstance(digest, str) and _HEX64.fullmatch(digest)) or not isinstance(meta, dict):
                    errs.append("Campo 'blobs' com estrutura inválida.")
                    break
                if any(k in meta and not short_str(meta[k], 255) for k in ("name", "media_type", "created_at")) or \
                        ("size" in meta and not (is_int(meta["size"]) and meta["size"] >= 0)):
                    errs.append("Metadados de dados de entrada com tipos inválidos.")
                    break
        return errs

    def inspect_backup(self, data: bytes) -> BackupInspection:
        """Inspeciona um backup NÃO confiável e o compara com a configuração deste armazenamento."""
        rep = inspect_backup_data(data)
        if rep.ok:
            cur = self.load()
            if cur is not None:
                rep.same_installation = cur.config["installation"]["uid"] == rep.config["installation"]["uid"]
                if not rep.same_installation:
                    rep.warnings.append("O backup pertence a OUTRA microrrede (identidade diferente).")
        return rep

    @classmethod
    def _inspect(cls, data: bytes, rep: BackupInspection) -> None:
        if not isinstance(data, (bytes, bytearray)):
            raise _BackupRejected("Conteúdo de backup inválido.")
        if len(data) > MAX_BACKUP_BYTES:
            raise _BackupRejected("Arquivo de backup grande demais.")
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise _BackupRejected("O arquivo não é um ZIP válido de backup do SEEDS2.") from None
        with zf:
            infos = zf.infolist()
            # ---- estrutura do ZIP (antes de descomprimir qualquer coisa)
            if len(infos) > MAX_BACKUP_ENTRIES:
                raise _BackupRejected(f"Backup com entradas demais ({len(infos)} > {MAX_BACKUP_ENTRIES}).")
            names = [i.filename for i in infos]
            if len(set(names)) != len(names):
                raise _BackupRejected("Backup com entradas duplicadas.")
            bad = [n for n in names if not _allowed_entry(n)]
            if bad:
                raise _BackupRejected(f"Entradas inesperadas no backup: {sorted(bad)[:5]}")
            if "manifest.json" not in names or "configuration.json" not in names:
                raise _BackupRejected("Backup incompleto: manifest.json ou configuration.json ausente.")
            declared = 0
            for info in infos:
                if info.flag_bits & 0x1:
                    raise _BackupRejected("Backup com entradas criptografadas não é suportado.")
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise _BackupRejected("Método de compressão não suportado no backup.")
                if info.file_size > _entry_cap(info.filename):
                    raise _BackupRejected(f"Entrada {info.filename!r} excede o tamanho permitido.")
                declared += info.file_size
            if declared > MAX_BACKUP_UNCOMPRESSED:
                raise _BackupRejected("O conteúdo declarado do backup excede o limite total permitido.")
            # ---- leitura limitada (tamanho real, não o declarado)
            budget = [MAX_BACKUP_UNCOMPRESSED]
            content = {i.filename: cls._read_capped(zf, i, _entry_cap(i.filename), budget) for i in infos}
        # ---- manifesto
        try:
            manifest = json.loads(content["manifest.json"].decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise _BackupRejected("manifest.json ilegível.") from None
        merrs = cls._manifest_errors(manifest)
        if merrs:
            rep.errors.extend(merrs)
            return
        rep.manifest = manifest
        files: dict = manifest["files"]
        for name in sorted(set(content) - {"manifest.json"}):
            if name not in files:
                rep.errors.append(f"Entrada {name!r} não declarada no manifesto.")
            elif files[name] != sha256(content[name]).hexdigest():
                rep.errors.append(f"Integridade violada: hash de {name} não confere com o manifesto.")
        missing_listed = set(files) - set(content)
        if missing_listed:
            rep.errors.append(f"Arquivos listados no manifesto ausentes: {sorted(missing_listed)}")
        if rep.errors:
            return
        # ---- configuração
        try:
            cfg = json.loads(content["configuration.json"].decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise _BackupRejected("configuration.json ilegível.") from None
        if not isinstance(cfg, dict):
            raise _BackupRejected("configuration.json não contém um objeto de configuração.")
        if "history.json" in content:
            try:
                hist = json.loads(content["history.json"].decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                hist = None
            if not isinstance(hist, list):
                rep.errors.append("history.json com estrutura inválida.")
        if C.fingerprint(cfg) != manifest["fingerprint"]:
            rep.errors.append("A impressão digital da configuração não confere com o manifesto.")
        if cfg.get("schema_version") != manifest["doc_schema_version"]:
            rep.errors.append("A versão do documento não confere com o manifesto.")
        if rep.errors:
            return
        try:
            cfg, applied = migrate_document(cfg)
        except MigrationError as exc:
            raise _BackupRejected(f"Configuração incompatível: {exc}") from None
        if applied:
            rep.warnings.append(f"Backup no formato anterior (documento v{manifest['doc_schema_version']}): será migrado "
                                f"para o esquema atual — " + "; ".join(applied[-1]["notes"]))
            rep.migrated = True
        for issue in C.errors(C.validate(cfg)):
            rep.errors.append(f"Configuração incompatível: {issue.path}: {issue.message}")
        if rep.errors:
            return
        if cfg["installation"]["uid"] != manifest["installation_uid"]:
            rep.errors.append("A identidade da instalação no manifesto não confere com a configuração.")
        # ---- dados de entrada (blobs)
        refs = cls._referenced_blobs(cfg)
        for name in content:
            if name.startswith("blobs/"):
                digest = name.split("/", 1)[1]
                if sha256(content[name]).hexdigest() != digest:
                    rep.errors.append(f"Dado de entrada {digest[:12]}… corrompido.")
                elif digest not in refs:
                    rep.errors.append(f"Dado de entrada {digest[:12]}… não é referenciado pela configuração.")
                else:
                    rep.blobs[digest] = (content[name], manifest["blobs"].get(digest, {}))
        missing_blobs = refs - set(rep.blobs)
        if missing_blobs:
            rep.errors.append(f"Dados de entrada referenciados ausentes no backup: {sorted(missing_blobs)}")
        if rep.errors:
            return
        rep.config = cfg

    def import_inspected(self, rep: BackupInspection, *, new_uid: str | None = None, note: str = "",
                         origin: str = "import") -> Stored:
        """Grava num armazenamento VAZIO o conteúdo de um backup já inspecionado (blobs + revisão 1 numa única
        transação). ``new_uid`` cria uma cópia independente: nova identidade, origem registrada no documento
        (``installation.copied_from``) — a cópia não finge ser a mesma instalação física."""
        if not rep.ok or rep.config is None:
            raise StoreError("Backup rejeitado: " + " | ".join(rep.errors))
        cfg = json.loads(C.canonical_json(rep.config))
        m = rep.manifest
        if new_uid is not None:
            src = cfg["installation"]
            cfg["installation"] = {**src, "uid": new_uid, "copied_from": {
                "uid": src["uid"], "fingerprint": m.get("fingerprint"), "revision": m.get("revision"),
                "name": src.get("name", ""), "copied_at": C.utc_now()}}
        doc, fp = self._prepare(cfg)
        with self._tx() as con:
            if con.execute("SELECT 1 FROM microgrid WHERE id = 1").fetchone() is not None:
                raise StoreError("O armazenamento de destino não está vazio.")
            return self._write_revision(con, doc, fp, 0, note=note, origin=origin, allow_identity_change=False,
                                        new_blobs=rep.blobs)

    def restore_backup(self, data: bytes, expected_revision: int, *, confirm: bool,
                       confirm_identity_change: bool = False) -> Stored:
        """Restauração ATÔMICA: dados de entrada e configuração são gravados na MESMA transação.
        Conflito de revisão, troca de identidade não confirmada ou qualquer falha → nada é persistido."""
        if not confirm:
            raise StoreError("A restauração exige confirmação explícita.")
        rep = self.inspect_backup(data)
        if not rep.ok:
            raise StoreError("Backup rejeitado: " + " | ".join(rep.errors))
        doc, fp = self._prepare(rep.config)
        m = rep.manifest
        note = (f"Restaurado do backup de {m['created_at'][:40]} (revisão {m['revision']} da origem, "
                f"{m['fingerprint'][:12]}…)" + (" — migrado do formato anterior" if rep.migrated else ""))
        with self._tx() as con:
            return self._write_revision(con, doc, fp, expected_revision, note=note, origin="restore",
                                        allow_identity_change=bool(confirm_identity_change), new_blobs=rep.blobs)


def inspect_backup_data(data: bytes) -> BackupInspection:
    """Inspeciona um backup NÃO confiável sem depender de um armazenamento. Nunca levanta exceção: todo
    problema vira ``errors``."""
    rep = BackupInspection(ok=False)
    try:
        MicrogridStore._inspect(data, rep)
    except _BackupRejected as exc:
        rep.errors.append(str(exc))
    except Exception as exc:  # noqa: BLE001 — qualquer outro defeito do arquivo é rejeição controlada
        rep.errors.append(f"Arquivo de backup malformado ou ilegível ({type(exc).__name__}).")
    if rep.errors:
        rep.config, rep.blobs, rep.same_installation = None, {}, None
    rep.ok = not rep.errors
    return rep


def backup_filename(config: dict) -> str:
    """Nome ASCII portátil (acentos transliterados), seguro em qualquer sistema de arquivos e navegador. Inclui os
    8 primeiros dígitos do UID: microrredes com o mesmo nome geram arquivos distinguíveis."""
    import unicodedata
    from datetime import datetime

    ascii_name = unicodedata.normalize("NFKD", config["installation"]["name"]).encode("ascii", "ignore").decode("ascii")
    safe = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]", "_", ascii_name))[:40].strip("_") or "microrrede"
    uid = re.sub(r"[^0-9a-f]", "", str(config["installation"].get("uid", "")))[:8] or "semid"
    return f"seeds2_{safe}_{uid}_{datetime.now():%Y%m%d_%H%M}{BACKUP_SUFFIX}"


def default_store() -> MicrogridStore:
    return MicrogridStore()


__all__: list[Any] = ["BackupInspection", "ConflictError", "IdentityError", "MicrogridStore", "MissingStoreError", "Stored",
                      "StoreError", "ValidationError", "backup_filename", "default_store", "inspect_backup_data",
                      "resolve_data_dir", "sqlite_backup_copy"]
