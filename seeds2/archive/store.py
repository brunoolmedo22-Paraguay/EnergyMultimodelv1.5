"""Arquivo Científico da INSTALAÇÃO (Piso 2D-A): estudos arquivados, somente leitura.

Armazenamento: ``SEEDS2_DATA_DIR/scientific_archive/archive.db`` — banco PRÓPRIO, separado do catálogo
(``registry.db``) e dos bancos das microrredes (``microgrids/<uid>/seeds2.db``). Motivos (``PARAMIJEFE.md`` Entrega 4):

* um estudo deve poder ser aberto numa instalação que NÃO possui a microrrede de origem, sem recriá-la;
* importar um estudo nunca toca o inventário, os cenários operativos nem as rodadas de nenhuma microrrede (isolamento
  por construção) — nem o protocolo de exclusão H-01/H-02/H-03, cujos bloqueios (L1 catálogo, L2 microrrede) nunca são
  tomados aqui. Este banco tem o seu próprio bloqueio (L3), nunca aninhado com L1/L2: a exportação lê L2 (instantâneo) e
  só depois a importação escreve L3;
* excluir uma microrrede não apaga os estudos já arquivados (são registros históricos da instalação).

Esquema (v1): ``studies`` (identidade LOCAL ``archive_uid`` + identidade de ORIGEM preservada + manifesto exato do
pacote), ``study_resources`` (caminho → SHA-256) e ``archive_blobs`` (conteúdo endereçado por SHA-256, deduplicado).
As três tabelas são imutáveis (triggers): um estudo arquivado nunca é editado. Importação ATÔMICA: inspeção completa
→ uma única transação (estudo + todos os recursos, cada um com SHA-256 e tamanho reconferidos na 2ª leitura) → COMMIT.
Qualquer falha (dependência corrompida, erro SQLite, conflito, processo interrompido) desfaz tudo: nunca há estudo
parcial.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
import zlib
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator

from seeds2.microgrid import config as C
from seeds2.microgrid.store import StoreError, ensure_wal, resolve_data_dir, sqlite_backup_copy

from . import format as FMT

ARCHIVE_DIRNAME = "scientific_archive"
DB_FILENAME = "archive.db"
ACQUISITIONS = {"importado": "Importado de um pacote .seeds2study.zip", "arquivado": "Arquivado a partir de uma microrrede desta instalação"}
_HEX32 = re.compile(r"[0-9a-f]{32}")

MIGRATIONS: list[tuple[int, list[str]]] = [
    (1, [
        """CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
        """CREATE TABLE archive_blobs (
               sha256 TEXT PRIMARY KEY CHECK (length(sha256) = 64),
               size INTEGER NOT NULL CHECK (size >= 0),
               encoding TEXT NOT NULL CHECK (encoding IN ('identity', 'zlib')),
               content BLOB NOT NULL)""",
        """CREATE TABLE studies (
               archive_uid TEXT PRIMARY KEY CHECK (length(archive_uid) = 32),
               content_id TEXT NOT NULL CHECK (length(content_id) = 64),
               package_sha256 TEXT NOT NULL,
               format TEXT NOT NULL,
               format_version INTEGER NOT NULL,
               acquisition TEXT NOT NULL CHECK (acquisition IN ('importado', 'arquivado')),
               copy_of TEXT REFERENCES studies(archive_uid),
               context_microgrid_uid TEXT,
               context_incarnation TEXT,
               context_name TEXT,
               origin_microgrid_uid TEXT NOT NULL,
               origin_microgrid_name TEXT NOT NULL,
               origin_incarnation TEXT,
               origin_scenario_uid TEXT NOT NULL,
               scenario_name TEXT NOT NULL,
               exported_at TEXT NOT NULL,
               exporter_version TEXT NOT NULL,
               n_versions INTEGER NOT NULL,
               n_runs INTEGER NOT NULL,
               n_resources INTEGER NOT NULL,
               total_bytes INTEGER NOT NULL,
               package_bytes INTEGER NOT NULL,
               first_run_at TEXT,
               last_run_at TEXT,
               imported_at TEXT NOT NULL,
               verification TEXT NOT NULL,
               manifest TEXT NOT NULL)""",
        """CREATE INDEX studies_by_content ON studies(content_id)""",
        """CREATE INDEX studies_by_origin ON studies(origin_scenario_uid)""",
        """CREATE TABLE study_resources (
               archive_uid TEXT NOT NULL REFERENCES studies(archive_uid),
               path TEXT NOT NULL,
               sha256 TEXT NOT NULL REFERENCES archive_blobs(sha256),
               size INTEGER NOT NULL,
               media_type TEXT NOT NULL,
               PRIMARY KEY (archive_uid, path))""",
        """CREATE TRIGGER studies_immutable_u BEFORE UPDATE ON studies
               BEGIN SELECT RAISE(ABORT, 'estudos arquivados são imutáveis'); END""",
        """CREATE TRIGGER studies_immutable_d BEFORE DELETE ON studies
               BEGIN SELECT RAISE(ABORT, 'estudos arquivados são imutáveis'); END""",
        """CREATE TRIGGER study_resources_immutable_u BEFORE UPDATE ON study_resources
               BEGIN SELECT RAISE(ABORT, 'recursos de estudos arquivados são imutáveis'); END""",
        """CREATE TRIGGER study_resources_immutable_d BEFORE DELETE ON study_resources
               BEGIN SELECT RAISE(ABORT, 'recursos de estudos arquivados são imutáveis'); END""",
        """CREATE TRIGGER archive_blobs_immutable_u BEFORE UPDATE ON archive_blobs
               BEGIN SELECT RAISE(ABORT, 'conteúdos arquivados são imutáveis'); END""",
        """CREATE TRIGGER archive_blobs_immutable_d BEFORE DELETE ON archive_blobs
               BEGIN SELECT RAISE(ABORT, 'conteúdos arquivados são imutáveis'); END""",
    ]),
]
LATEST_ARCHIVE_VERSION = MIGRATIONS[-1][0]


class ArchiveError(StoreError):
    """Erro do Arquivo Científico com mensagem apresentável."""


class StudyRejected(ArchiveError):
    """O pacote não passou na verificação; nada foi importado. ``errors`` lista os diagnósticos."""

    def __init__(self, errors: list[str]):
        super().__init__("Pacote rejeitado; nada foi importado: " + " | ".join(errors[:4]))
        self.errors = list(errors)


class StudyNotFound(ArchiveError):
    """O estudo não existe no Arquivo Científico desta instalação."""


@dataclass(frozen=True)
class ArchivedStudy:
    archive_uid: str
    content_id: str
    package_sha256: str
    format_version: int
    acquisition: str
    copy_of: str | None
    context_microgrid_uid: str | None
    context_incarnation: str | None
    context_name: str | None
    origin_microgrid_uid: str
    origin_microgrid_name: str
    origin_incarnation: str | None
    origin_scenario_uid: str
    scenario_name: str
    exported_at: str
    exporter_version: str
    n_versions: int
    n_runs: int
    n_resources: int
    total_bytes: int
    package_bytes: int
    first_run_at: str | None
    last_run_at: str | None
    imported_at: str
    verification: dict
    manifest: dict = field(repr=False)
    manifest_text: str = field(repr=False, default="")

    @property
    def runs_by_state(self) -> dict:
        return dict(((self.manifest.get("study") or {}).get("counts") or {}).get("runs_by_state") or {})


@dataclass(frozen=True)
class ImportResult:
    study: ArchivedStudy
    created: bool                      # False = o mesmo conteúdo já estava arquivado (nada foi inserido)
    duplicate_of: str | None = None


class ArchiveStore:
    """Banco do Arquivo Científico da instalação. Cada operação abre e fecha a sua conexão."""

    def __init__(self, data_dir: str | os.PathLike | None = None):
        self.root = resolve_data_dir(data_dir) / ARCHIVE_DIRNAME
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / DB_FILENAME
        self._migrate()

    # ------------------------------------------------------------ conexão / migração
    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        con.row_factory = sqlite3.Row
        ensure_wal(con)
        con.execute("PRAGMA busy_timeout=30000")
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
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        con = self._connect()
        try:
            con.execute("BEGIN")
            yield con
        finally:
            if con.in_transaction:
                con.execute("ROLLBACK")
            con.close()

    def _migrate(self) -> None:
        existed = self.path.exists() and self.path.stat().st_size > 0
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            current = int(con.execute("PRAGMA user_version").fetchone()[0])
            if current > LATEST_ARCHIVE_VERSION:
                con.execute("ROLLBACK")
                raise ArchiveError(f"O Arquivo Científico ({self.path}) usa o esquema v{current}, mais novo que este "
                                   f"software (v{LATEST_ARCHIVE_VERSION}). Atualize o SEEDS2; nada foi alterado.")
            pending = [(v, s) for v, s in MIGRATIONS if v > current]
            if not pending:
                con.execute("ROLLBACK")
                return
            if existed and current > 0:                # cópia de segurança ANTES de migrar (protocolo do projeto)
                sqlite_backup_copy(self.path, self.path.with_name(f"{self.path.name}.bak-v{current}"))
            for version, stmts in pending:
                for s in stmts:
                    con.execute(s)
                con.execute(f"PRAGMA user_version = {int(version)}")
                con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('migrated_to', ?)", (str(version),))
            con.execute("COMMIT")
        except sqlite3.Error as exc:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise ArchiveError(f"Migração do Arquivo Científico interrompida (banco mantido na versão anterior): {exc}") from None
        finally:
            con.close()

    def db_version(self) -> int:
        with self._read() as con:
            return int(con.execute("PRAGMA user_version").fetchone()[0])

    # ------------------------------------------------------------ leitura
    @staticmethod
    def _row(row: sqlite3.Row) -> ArchivedStudy:
        d = dict(row)
        return ArchivedStudy(
            d["archive_uid"], d["content_id"], d["package_sha256"], int(d["format_version"]), d["acquisition"], d["copy_of"],
            d["context_microgrid_uid"], d["context_incarnation"], d["context_name"], d["origin_microgrid_uid"],
            d["origin_microgrid_name"], d["origin_incarnation"], d["origin_scenario_uid"], d["scenario_name"],
            d["exported_at"], d["exporter_version"], int(d["n_versions"]), int(d["n_runs"]), int(d["n_resources"]),
            int(d["total_bytes"]), int(d["package_bytes"]), d["first_run_at"], d["last_run_at"], d["imported_at"],
            json.loads(d["verification"]), json.loads(d["manifest"]), d["manifest"])

    def list_studies(self) -> list[ArchivedStudy]:
        with self._read() as con:
            return [self._row(r) for r in con.execute("SELECT * FROM studies ORDER BY imported_at, rowid").fetchall()]

    def get_study(self, archive_uid: str) -> ArchivedStudy:
        with self._read() as con:
            row = con.execute("SELECT * FROM studies WHERE archive_uid = ?", (str(archive_uid),)).fetchone()
        if row is None:
            raise StudyNotFound("O estudo não existe no Arquivo Científico desta instalação.")
        return self._row(row)

    def find_by_content(self, content_id: str) -> list[ArchivedStudy]:
        with self._read() as con:
            return [self._row(r) for r in con.execute("SELECT * FROM studies WHERE content_id = ? ORDER BY imported_at, rowid",
                                                      (str(content_id),)).fetchall()]

    def find_by_origin(self, scenario_uid: str) -> list[ArchivedStudy]:
        with self._read() as con:
            return [self._row(r) for r in con.execute("SELECT * FROM studies WHERE origin_scenario_uid = ? "
                                                      "ORDER BY imported_at, rowid", (str(scenario_uid),)).fetchall()]

    def resources(self, archive_uid: str) -> list[dict]:
        with self._read() as con:
            return [dict(r) for r in con.execute("SELECT path, sha256, size, media_type FROM study_resources WHERE "
                                                 "archive_uid = ? ORDER BY path", (str(archive_uid),)).fetchall()]

    @staticmethod
    def _content(con: sqlite3.Connection, digest: str, path: str) -> bytes:
        row = con.execute("SELECT size, encoding, content FROM archive_blobs WHERE sha256 = ?", (digest,)).fetchone()
        if row is None:
            raise ArchiveError(f"Conteúdo de {path!r} ausente do Arquivo Científico.")
        try:
            raw = zlib.decompress(bytes(row["content"])) if row["encoding"] == "zlib" else bytes(row["content"])
        except zlib.error:
            raise ArchiveError(f"Conteúdo de {path!r} corrompido (descompressão).") from None
        if len(raw) != int(row["size"]) or sha256(raw).hexdigest() != digest:
            raise ArchiveError(f"Conteúdo de {path!r} corrompido (SHA-256 divergente).")
        return raw

    def resource(self, archive_uid: str, path: str) -> bytes:
        """Conteúdo de um recurso do estudo (SHA-256 e tamanho reconferidos a cada leitura)."""
        with self._read() as con:
            row = con.execute("SELECT sha256 FROM study_resources WHERE archive_uid = ? AND path = ?",
                              (str(archive_uid), str(path))).fetchone()
            if row is None:
                raise ArchiveError(f"Recurso {path!r} não existe neste estudo.")
            return self._content(con, row["sha256"], path)

    def verify(self, archive_uid: str) -> tuple[bool, list[str]]:
        """Reconfere TODOS os recursos do estudo (SHA-256 e tamanho) e o manifesto gravado."""
        problems: list[str] = []
        with self._read() as con:
            st = con.execute("SELECT manifest, n_resources FROM studies WHERE archive_uid = ?", (str(archive_uid),)).fetchone()
            if st is None:
                raise StudyNotFound("O estudo não existe no Arquivo Científico desta instalação.")
            res = (json.loads(st["manifest"]).get("resources") or {})
            rows = con.execute("SELECT path, sha256, size FROM study_resources WHERE archive_uid = ?",
                               (str(archive_uid),)).fetchall()
            if len(rows) != int(st["n_resources"]) or {r["path"] for r in rows} != set(res):
                problems.append("O conjunto de recursos gravados não corresponde ao manifesto do pacote.")
            for r in rows:
                decl = res.get(r["path"]) or {}
                if decl.get("sha256") != r["sha256"] or decl.get("size") != r["size"]:
                    problems.append(f"{r['path']}: registro diverge do manifesto.")
                    continue
                try:
                    self._content(con, r["sha256"], r["path"])
                except ArchiveError as exc:
                    problems.append(str(exc))
        return not problems, problems

    # ------------------------------------------------------------ importação atômica
    @staticmethod
    def _insert_resource(con: sqlite3.Connection, archive_uid: str, path: str, decl: dict, data: bytes) -> None:
        digest = sha256(data).hexdigest()
        if digest != decl["sha256"] or len(data) != decl["size"]:
            raise FMT.Rejected(f"Integridade violada durante a importação: {path!r}.")
        ex = con.execute("SELECT size FROM archive_blobs WHERE sha256 = ?", (digest,)).fetchone()
        if ex is None:
            packed = zlib.compress(data, 6) if len(data) > 2048 else data
            con.execute("INSERT INTO archive_blobs(sha256, size, encoding, content) VALUES (?,?,?,?)",
                        (digest, len(data), "zlib" if packed is not data else "identity", packed))
        elif int(ex["size"]) != len(data):
            raise ArchiveError("Conflito de conteúdo no Arquivo Científico (mesmo SHA-256, tamanho diferente); nada foi "
                               "importado.")
        con.execute("INSERT INTO study_resources(archive_uid, path, sha256, size, media_type) VALUES (?,?,?,?,?)",
                    (archive_uid, path, digest, len(data), str(decl["media_type"])))

    def import_package(self, source, *, on_duplicate: str = "recognize", acquisition: str = "importado",
                       context: dict | None = None, expected_content_id: str | None = None) -> ImportResult:
        """Importa um pacote ``.seeds2study.zip`` (caminho, bytes ou arquivo binário). Nunca executa modelos.

        * a inspeção completa é SEMPRE refeita aqui (a inspeção mostrada ao usuário não é confiada);
        * ``expected_content_id``: o conteúdo confirmado pelo usuário — se o arquivo mudou, nada é importado;
        * ``on_duplicate``: ``"recognize"`` (o mesmo conteúdo já arquivado → devolve o existente, nada é inserido) ou
          ``"copy"`` (nova cópia identificável: novo ``archive_uid`` com ``copy_of``);
        * ``context``: microrrede local em cujo contexto o estudo foi importado (apenas registro; nada da microrrede é
          lido ou alterado)."""
        if on_duplicate not in ("recognize", "copy"):
            raise ArchiveError("Política de duplicata inválida.")
        if acquisition not in ACQUISITIONS:
            raise ArchiveError("Origem da aquisição inválida.")
        rep = FMT.inspect(source)
        if not rep.ok:
            raise StudyRejected(rep.errors)
        if expected_content_id is not None and rep.content_id != expected_content_id:
            raise ArchiveError("O pacote mudou desde a inspeção confirmada; nada foi importado. Inspecione-o novamente.")
        ctx = context or {}
        m, s = rep.manifest, rep.summary
        o = m["study"]["origin"]
        uid = uuid.uuid4().hex
        try:
            with self._tx() as con:
                dups = con.execute("SELECT archive_uid FROM studies WHERE content_id = ? ORDER BY imported_at, rowid",
                                   (rep.content_id,)).fetchall()
                if dups and on_duplicate == "recognize":
                    return ImportResult(self._row(con.execute("SELECT * FROM studies WHERE archive_uid = ?",
                                                              (dups[0][0],)).fetchone()), False, dups[0][0])
                con.execute(
                    "INSERT INTO studies(archive_uid, content_id, package_sha256, format, format_version, acquisition, "
                    "copy_of, context_microgrid_uid, context_incarnation, context_name, origin_microgrid_uid, "
                    "origin_microgrid_name, origin_incarnation, origin_scenario_uid, scenario_name, exported_at, "
                    "exporter_version, n_versions, n_runs, n_resources, total_bytes, package_bytes, first_run_at, "
                    "last_run_at, imported_at, verification, manifest) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,"
                    "?,?,?,?,?)",
                    (uid, rep.content_id, rep.package_sha256, m["format"], int(m["format_version"]), acquisition,
                     dups[0][0] if dups else None,
                     ctx.get("microgrid_uid") if _HEX32.fullmatch(str(ctx.get("microgrid_uid") or "")) else None,
                     ctx.get("incarnation"), str(ctx.get("name") or "")[:200] or None,
                     o["microgrid_uid"], o.get("microgrid_name") or "", o.get("microgrid_incarnation"), o["scenario_uid"],
                     o.get("scenario_name") or "", str(m["created_at"]), str(m["exporter"]["app_version"])[:100],
                     int(s["versions"]), int(s["runs"]), int(s["resources"]), int(s["uncompressed_bytes"]),
                     int(rep.package_bytes), s.get("first_run_at"), s.get("last_run_at"), C.utc_now(),
                     C.canonical_json(rep.as_report()), rep.manifest_text))
                n = 0
                for path, decl, data in FMT.iter_resources(source, m):
                    self._insert_resource(con, uid, path, decl, data)
                    n += 1
                if n != int(s["resources"]):
                    raise ArchiveError("Número de recursos importados diverge do manifesto; nada foi importado.")
                return ImportResult(self._row(con.execute("SELECT * FROM studies WHERE archive_uid = ?",
                                                          (uid,)).fetchone()), True, dups[0][0] if dups else None)
        except FMT.Rejected as exc:
            raise StudyRejected([str(exc)]) from None
        except sqlite3.Error as exc:
            raise ArchiveError(f"Falha do banco ao importar (operação desfeita; nada foi importado): {exc}") from None


__all__ = ["ACQUISITIONS", "ArchiveError", "ArchiveStore", "ArchivedStudy", "ImportResult", "LATEST_ARCHIVE_VERSION",
           "StudyNotFound", "StudyRejected"]
