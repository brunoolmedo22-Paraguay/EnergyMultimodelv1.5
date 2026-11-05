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
import shutil
import sqlite3
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator

from . import config as C

DB_FILENAME = "seeds2.db"
ENV_DATA_DIR = "SEEDS2_DATA_DIR"
BACKUP_FORMAT = "seeds2-microgrid-backup"
BACKUP_FORMAT_VERSION = 1
BACKUP_SUFFIX = ".seeds2backup.zip"
MAX_BLOB_BYTES = 50 * 1024 * 1024
MAX_BACKUP_BYTES = 200 * 1024 * 1024

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
]
LATEST_DB_VERSION = MIGRATIONS[-1][0]


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


def resolve_data_dir(explicit: str | os.PathLike | None = None) -> Path:
    raw = explicit or os.environ.get(ENV_DATA_DIR) or (Path.home() / ".seeds2")
    return Path(raw).expanduser().resolve()


class MicrogridStore:
    def __init__(self, data_dir: str | os.PathLike | None = None):
        self.data_dir = resolve_data_dir(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / DB_FILENAME
        self._migrate()

    # ------------------------------------------------------------ conexão / migração
    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
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

    def _migrate(self) -> None:
        existed = self.path.exists() and self.path.stat().st_size > 0
        with self._read() as con:
            current = int(con.execute("PRAGMA user_version").fetchone()[0])
        if current > LATEST_DB_VERSION:
            raise StoreError(f"O banco {self.path} usa o esquema v{current}, mais novo que este software "
                             f"(v{LATEST_DB_VERSION}). Atualize o SEEDS2; o banco não foi alterado.")
        pending = [(v, stmts) for v, stmts in MIGRATIONS if v > current]
        if not pending:
            return
        if existed and current > 0:
            shutil.copy2(self.path, self.path.with_name(f"{self.path.name}.bak-v{current}"))
        for version, stmts in pending:
            with self._tx() as con:
                for s in stmts:
                    con.execute(s)
                con.execute(f"PRAGMA user_version = {int(version)}")
                con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('migrated_to', ?)", (str(version),))
                con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('migrated_at', ?)", (C.utc_now(),))

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
        return Stored(json.loads(row["document"]), int(row["revision"]), row["fingerprint"], row["saved_at"])

    # ------------------------------------------------------------ escrita
    def _referenced_blobs(self, config: dict) -> set[str]:
        refs = set()
        for section in ("demand", "climate"):
            csv = (config.get(section) or {}).get("csv") or {}
            if csv.get("blob"):
                refs.add(csv["blob"])
        return refs

    def save(self, config: dict, expected_revision: int, *, note: str = "", origin: str = "edit",
             allow_identity_change: bool = False) -> Stored:
        """Grava uma nova revisão se o conteúdo mudou. ``expected_revision`` = 0 para o primeiro salvamento."""
        issues = C.validate(config)
        if C.errors(issues):
            raise ValidationError(C.errors(issues))
        doc = json.loads(C.canonical_json(config))           # cópia normalizada e serializável
        fp = C.fingerprint(doc)
        uid = doc["installation"]["uid"]
        with self._tx() as con:
            row = con.execute("SELECT installation_uid, revision, fingerprint, saved_at FROM microgrid WHERE id = 1").fetchone()
            current = int(row["revision"]) if row else 0
            if int(expected_revision) != current:
                raise ConflictError(int(expected_revision), current)
            if row and row["installation_uid"] != uid and not allow_identity_change:
                raise IdentityError("A configuração pertence a outra instalação; este SEEDS2 administra uma única "
                                    "microrrede. Use a restauração de backup com confirmação explícita.")
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

    def revert_to(self, revision: int, expected_revision: int) -> Stored:
        old = self.get_revision(revision)
        return self.save(old.config, expected_revision, note=f"Reversão ao conteúdo da revisão {revision}", origin="revert")

    # ------------------------------------------------------------ blobs (dados de entrada)
    def put_blob(self, content: bytes, name: str = "", media_type: str = "text/csv") -> str:
        if len(content) > MAX_BLOB_BYTES:
            raise StoreError(f"Arquivo maior que {MAX_BLOB_BYTES // (1024 * 1024)} MB.")
        h = sha256(content).hexdigest()
        with self._tx() as con:
            con.execute("INSERT OR IGNORE INTO blobs(sha256, name, media_type, size, content, created_at) "
                        "VALUES (?,?,?,?,?,?)", (h, str(name), str(media_type), len(content), content, C.utc_now()))
        return h

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

    def inspect_backup(self, data: bytes) -> BackupInspection:
        rep = BackupInspection(ok=False)
        if len(data) > MAX_BACKUP_BYTES:
            rep.errors.append("Arquivo de backup grande demais.")
            return rep
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            rep.errors.append("O arquivo não é um ZIP válido de backup do SEEDS2.")
            return rep
        with zf:
            names = set(zf.namelist())
            bad = [n for n in names if n.startswith("/") or ".." in n.split("/")
                   or not (n in ("manifest.json", "configuration.json", "history.json") or n.startswith("blobs/"))]
            if bad:
                rep.errors.append(f"Entradas inesperadas no backup: {sorted(bad)[:5]}")
                return rep
            if "manifest.json" not in names or "configuration.json" not in names:
                rep.errors.append("Backup incompleto: manifest.json ou configuration.json ausente.")
                return rep
            for info in zf.infolist():
                if info.file_size > MAX_BLOB_BYTES * 2:
                    rep.errors.append(f"Entrada {info.filename} grande demais.")
                    return rep
            try:
                manifest = json.loads(zf.read("manifest.json"))
            except (ValueError, UnicodeDecodeError):
                rep.errors.append("manifest.json ilegível.")
                return rep
            rep.manifest = manifest if isinstance(manifest, dict) else {}
            if rep.manifest.get("format") != BACKUP_FORMAT:
                rep.errors.append("Formato não reconhecido: não é um backup de microrrede do SEEDS2.")
                return rep
            if rep.manifest.get("format_version") != BACKUP_FORMAT_VERSION:
                rep.errors.append(f"Versão de formato de backup {rep.manifest.get('format_version')!r} não suportada.")
                return rep
            if int(rep.manifest.get("db_schema_version") or 0) > LATEST_DB_VERSION:
                rep.errors.append("Backup gerado por versão mais nova do SEEDS2 (esquema desconhecido).")
            hashes = rep.manifest.get("files") or {}
            for name in sorted(names - {"manifest.json"}):
                content = zf.read(name)
                if hashes.get(name) != sha256(content).hexdigest():
                    rep.errors.append(f"Integridade violada: hash de {name} não confere com o manifesto.")
                if name.startswith("blobs/"):
                    digest = name.split("/", 1)[1]
                    if sha256(content).hexdigest() != digest:
                        rep.errors.append(f"Dado de entrada {digest[:12]}… corrompido.")
                    rep.blobs[digest] = (content, (rep.manifest.get("blobs") or {}).get(digest, {}))
            missing_listed = set(hashes) - (names - {"manifest.json"})
            if missing_listed:
                rep.errors.append(f"Arquivos listados no manifesto ausentes: {sorted(missing_listed)}")
            try:
                cfg = json.loads(zf.read("configuration.json"))
            except (ValueError, UnicodeDecodeError):
                rep.errors.append("configuration.json ilegível.")
                return rep
        rep.config = cfg if isinstance(cfg, dict) else None
        if rep.config is None:
            rep.errors.append("configuration.json não contém um objeto de configuração.")
            return rep
        if C.fingerprint(rep.config) != rep.manifest.get("fingerprint"):
            rep.errors.append("A impressão digital da configuração não confere com o manifesto.")
        for issue in C.errors(C.validate(rep.config)):
            rep.errors.append(f"Configuração incompatível: {issue.path}: {issue.message}")
        missing_blobs = self._referenced_blobs(rep.config) - set(rep.blobs)
        if missing_blobs:
            rep.errors.append(f"Dados de entrada referenciados ausentes no backup: {sorted(missing_blobs)}")
        cur = self.load()
        if cur is not None:
            rep.same_installation = cur.config["installation"]["uid"] == rep.config.get("installation", {}).get("uid")
            if not rep.same_installation:
                rep.warnings.append("O backup pertence a OUTRA instalação. Restaurá-lo substituirá a identidade da "
                                    "microrrede administrada por este SEEDS2 (o histórico atual é preservado).")
        rep.ok = not rep.errors
        return rep

    def restore_backup(self, data: bytes, expected_revision: int, *, confirm: bool,
                       confirm_identity_change: bool = False) -> Stored:
        if not confirm:
            raise StoreError("A restauração exige confirmação explícita.")
        rep = self.inspect_backup(data)
        if not rep.ok:
            raise StoreError("Backup rejeitado: " + " | ".join(rep.errors))
        if rep.same_installation is False and not confirm_identity_change:
            raise IdentityError("O backup é de outra instalação: confirme explicitamente a troca de identidade.")
        for digest, (content, meta) in rep.blobs.items():
            if self.put_blob(content, meta.get("name", ""), meta.get("media_type", "text/csv")) != digest:
                raise StoreError("Falha de integridade ao restaurar dados de entrada.")
        m = rep.manifest
        return self.save(rep.config, expected_revision, origin="restore", allow_identity_change=True,
                         note=f"Restaurado do backup de {m.get('created_at')} (revisão {m.get('revision')} da origem, "
                              f"{str(m.get('fingerprint', ''))[:12]}…)")


def backup_filename(config: dict) -> str:
    """Nome ASCII portátil (acentos transliterados), seguro em qualquer sistema de arquivos e navegador."""
    import re
    import unicodedata
    from datetime import datetime

    ascii_name = unicodedata.normalize("NFKD", config["installation"]["name"]).encode("ascii", "ignore").decode("ascii")
    safe = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]", "_", ascii_name))[:40].strip("_") or "microrrede"
    return f"seeds2_{safe}_{datetime.now():%Y%m%d_%H%M}{BACKUP_SUFFIX}"


def default_store() -> MicrogridStore:
    return MicrogridStore()


__all__: list[Any] = ["BackupInspection", "ConflictError", "IdentityError", "MicrogridStore", "Stored", "StoreError",
                      "ValidationError", "backup_filename", "default_store", "resolve_data_dir"]
