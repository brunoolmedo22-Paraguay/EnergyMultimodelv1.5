"""Persistência local (SQLite) de UMA microrrede do SEEDS2 (um banco por microrrede; catálogo em ``registry.py``).

Decisões (detalhadas em docs/seeds2/ARMAZENAMENTO.md):

* **Uma microrred por banco:** a tabela ``microgrid`` tem ``CHECK (id = 1)``; não existe
  noção de "projetos". A identidade (``installation_uid``) é preservada entre edições.
* **Cenários operativos (Piso 2A, esquema v3):** ``scenarios`` + ``scenario_versions`` (append-only), no MESMO
  banco da microrrede (nunca numa base global); versões independentes das revisões do inventário.
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
    # v3 (Piso 2A — Centro de Operação): cenários operativos DESTA microrrede. Somente tabelas novas (nenhuma
    # tabela, revisão ou documento existente é alterado). ``scenarios`` guarda o estado atual de cada cenário
    # (concorrência otimista por ``version``); ``scenario_versions`` é o histórico append-only (imutável, como
    # ``revisions``) — base para associar execuções imutáveis a (scenario_uid, version) no Piso 2C. As versões
    # do cenário são INDEPENDENTES das revisões do inventário: ``base_revision`` apenas referencia a revisão
    # (existente) do inventário físico sobre a qual o cenário foi definido.
    (3, [
        """CREATE TABLE scenarios (
               scenario_uid TEXT PRIMARY KEY CHECK (length(scenario_uid) = 32),
               microgrid_uid TEXT NOT NULL,
               name TEXT NOT NULL CHECK (length(trim(name)) > 0),
               version INTEGER NOT NULL CHECK (version >= 1),
               base_revision INTEGER NOT NULL REFERENCES revisions(revision),
               base_fingerprint TEXT NOT NULL,
               fingerprint TEXT NOT NULL,
               document TEXT NOT NULL,
               origin TEXT NOT NULL DEFAULT 'new',
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL)""",
        """CREATE TABLE scenario_versions (
               scenario_uid TEXT NOT NULL REFERENCES scenarios(scenario_uid),
               version INTEGER NOT NULL CHECK (version >= 1),
               microgrid_uid TEXT NOT NULL,
               base_revision INTEGER NOT NULL REFERENCES revisions(revision),
               base_fingerprint TEXT NOT NULL,
               fingerprint TEXT NOT NULL,
               document TEXT NOT NULL,
               saved_at TEXT NOT NULL,
               note TEXT NOT NULL DEFAULT '',
               origin TEXT NOT NULL DEFAULT 'edit',
               PRIMARY KEY (scenario_uid, version))""",
        """CREATE TRIGGER scenario_versions_immutable_u BEFORE UPDATE ON scenario_versions
               BEGIN SELECT RAISE(ABORT, 'versões de cenário são imutáveis'); END""",
        """CREATE TRIGGER scenario_versions_immutable_d BEFORE DELETE ON scenario_versions
               BEGIN SELECT RAISE(ABORT, 'versões de cenário são imutáveis'); END""",
    ]),
    # v4 (Piso 2C — Execução EMS e persistência científica): rodadas de cenário DESTA microrrede. Somente tabelas
    # novas. ``scenario_runs``: uma linha por execução de uma versão IMUTÁVEL do cenário (chave estrangeira para
    # ``scenario_versions``), com manifesto (procedência completa) gravado no início e resultado gravado na MESMA
    # transação que muda o estado para 'concluida'. Linhas finalizadas são imutáveis (triggers) e nunca excluídas.
    # ``scenario_run_data``: séries completas de entrada/saída e dados dos modelos (SHA-256 do conteúdo), gravados
    # somente enquanto a rodada está em execução (na transação de conclusão) e imutáveis depois.
    (4, [
        """CREATE TABLE scenario_runs (
               run_uid TEXT PRIMARY KEY CHECK (length(run_uid) = 32),
               request_id TEXT NOT NULL UNIQUE,
               microgrid_uid TEXT NOT NULL,
               incarnation TEXT,
               scenario_uid TEXT NOT NULL,
               scenario_version INTEGER NOT NULL CHECK (scenario_version >= 1),
               scenario_fingerprint TEXT NOT NULL,
               config_revision INTEGER NOT NULL REFERENCES revisions(revision),
               config_fingerprint TEXT NOT NULL,
               state TEXT NOT NULL CHECK (state IN ('em_execucao', 'concluida', 'falhou', 'interrompida')),
               owner TEXT NOT NULL,
               created_at TEXT NOT NULL,
               heartbeat_at TEXT NOT NULL,
               finished_at TEXT,
               progress TEXT NOT NULL DEFAULT '{}',
               manifest TEXT NOT NULL,
               outcome TEXT,
               summary TEXT,
               error TEXT,
               FOREIGN KEY (scenario_uid, scenario_version) REFERENCES scenario_versions(scenario_uid, version))""",
        """CREATE INDEX scenario_runs_by_scenario ON scenario_runs(scenario_uid, created_at)""",
        """CREATE TRIGGER scenario_runs_final_u BEFORE UPDATE ON scenario_runs WHEN OLD.state <> 'em_execucao'
               BEGIN SELECT RAISE(ABORT, 'rodadas finalizadas são imutáveis'); END""",
        """CREATE TRIGGER scenario_runs_identity_u BEFORE UPDATE ON scenario_runs
               WHEN NEW.run_uid IS NOT OLD.run_uid OR NEW.request_id IS NOT OLD.request_id
                 OR NEW.microgrid_uid IS NOT OLD.microgrid_uid OR NEW.incarnation IS NOT OLD.incarnation
                 OR NEW.scenario_uid IS NOT OLD.scenario_uid OR NEW.scenario_version IS NOT OLD.scenario_version
                 OR NEW.scenario_fingerprint IS NOT OLD.scenario_fingerprint
                 OR NEW.config_revision IS NOT OLD.config_revision OR NEW.config_fingerprint IS NOT OLD.config_fingerprint
                 OR NEW.owner IS NOT OLD.owner OR NEW.created_at IS NOT OLD.created_at OR NEW.manifest IS NOT OLD.manifest
               BEGIN SELECT RAISE(ABORT, 'identidade e manifesto da rodada são imutáveis'); END""",
        """CREATE TRIGGER scenario_runs_immutable_d BEFORE DELETE ON scenario_runs
               BEGIN SELECT RAISE(ABORT, 'rodadas são imutáveis'); END""",
        """CREATE TABLE scenario_run_data (
               run_uid TEXT NOT NULL REFERENCES scenario_runs(run_uid),
               name TEXT NOT NULL,
               sha256 TEXT NOT NULL,
               media_type TEXT NOT NULL,
               encoding TEXT NOT NULL CHECK (encoding IN ('identity', 'zlib')),
               size INTEGER NOT NULL,
               content BLOB NOT NULL,
               PRIMARY KEY (run_uid, name))""",
        """CREATE TRIGGER scenario_run_data_open_only BEFORE INSERT ON scenario_run_data
               WHEN (SELECT state FROM scenario_runs WHERE run_uid = NEW.run_uid) IS NOT 'em_execucao'
               BEGIN SELECT RAISE(ABORT, 'dados de rodada só podem ser gravados durante a execução'); END""",
        """CREATE TRIGGER scenario_run_data_immutable_u BEFORE UPDATE ON scenario_run_data
               BEGIN SELECT RAISE(ABORT, 'dados de rodada são imutáveis'); END""",
        """CREATE TRIGGER scenario_run_data_immutable_d BEFORE DELETE ON scenario_run_data
               BEGIN SELECT RAISE(ABORT, 'dados de rodada são imutáveis'); END""",
    ]),
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


class ScenarioConflictError(StoreError):
    """Outra sessão salvou o cenário depois da versão-base desta edição (nada foi sobrescrito)."""

    def __init__(self, scenario_uid: str, expected: int, current: int):
        super().__init__(f"O cenário foi alterado por outra sessão (versão base {expected}, atual {current}). "
                         "Recarregue antes de salvar; nada foi sobrescrito.")
        self.scenario_uid, self.expected, self.current = scenario_uid, expected, current


class ScenarioNotFound(StoreError):
    """O cenário não existe NESTA microrrede (nunca existiu, ou pertence a outra microrrede/incarnação)."""


class RunNotFound(StoreError):
    """A rodada não existe NESTA microrrede."""


class RunBusyError(StoreError):
    """Já existe uma rodada de cenário em execução nesta microrrede (nenhuma nova foi iniciada)."""


class RunStateError(StoreError):
    """Operação incompatível com o estado da rodada (p. ex. concluir uma rodada já finalizada ou de outro dono)."""


class MissingStoreError(StoreError):
    """O banco da microrrede não existe (p. ex. excluída por outra sessão)."""


class MicrogridDeletedError(MissingStoreError):
    """A microrrede foi excluída (lápide gravada no próprio banco) ou substituída por outra incarnação com o
    mesmo UID. Nenhuma leitura ou gravação é aceita por referências antigas."""


LIFECYCLE_KEY = "lifecycle"          # meta: lápide gravada pela exclusão (sob o bloqueio de escrita do banco)
INCARNATION_KEY = "incarnation"      # meta: identifica ESTA incarnação da microrrede (gravada ao entrar no catálogo)


@dataclass(frozen=True)
class Stored:
    config: dict
    revision: int
    fingerprint: str
    saved_at: str


@dataclass(frozen=True)
class StoredScenario:
    """Uma versão (imutável) de um cenário operativo. ``document`` é o documento completo do cenário
    (``seeds2.operation.scenarios``); as demais colunas são desnormalizadas para listagem e integridade."""
    scenario_uid: str
    microgrid_uid: str
    name: str
    version: int
    base_revision: int
    base_fingerprint: str
    fingerprint: str
    document: dict
    origin: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class StoredRun:
    """Rodada de cenário (Piso 2C). ``manifest`` é a procedência gravada no início (imutável); ``outcome`` e
    ``summary`` só existem em rodadas concluídas (ou falhas, com ``error``). ``data`` lista os dados gravados
    (nome → {sha256, media_type, size}) sem o conteúdo (lido sob demanda por ``run_data``)."""
    run_uid: str
    request_id: str
    microgrid_uid: str
    incarnation: str | None
    scenario_uid: str
    scenario_version: int
    scenario_fingerprint: str
    config_revision: int
    config_fingerprint: str
    state: str
    owner: str
    created_at: str
    heartbeat_at: str
    finished_at: str | None
    progress: dict
    manifest: dict
    outcome: dict | None
    summary: dict | None
    error: dict | None
    data: dict = field(default_factory=dict)

    @property
    def final(self) -> bool:
        return self.state != "em_execucao"


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
      coerentes;
    * ``incarnation``: incarnação esperada (gravada em ``meta`` quando a microrrede entra no catálogo). Uma
      referência antiga a uma microrrede excluída e reimportada com o MESMO UID é recusada.

    **Exclusão concorrente (H-01).** Toda transação de escrita verifica, DEPOIS de obter o bloqueio de escrita
    (``BEGIN IMMEDIATE``) e na mesma transação, a lápide ``meta.lifecycle`` e a incarnação. A exclusão grava a
    lápide sob esse mesmo bloqueio; portanto cada gravação ou é confirmada ANTES da lápide (e a exclusão espera
    por ela) ou é recusada com ``MicrogridDeletedError`` — nunca confirmada em silêncio numa microrrede excluída.
    Leituras também recusam microrredes com lápide. Com ``must_exist`` as conexões usam ``mode=rw``: o SQLite
    nunca recria um banco vazio no lugar de uma microrrede removida."""

    def __init__(self, data_dir: str | os.PathLike | None = None, *, must_exist: bool = False,
                 fixed_uid: str | None = None, incarnation: str | None = None):
        self.data_dir = resolve_data_dir(data_dir)
        self.path = self.data_dir / DB_FILENAME
        self.fixed_uid = fixed_uid
        self.incarnation = incarnation
        self._must_exist = must_exist
        if must_exist:
            if not self.path.is_file():
                raise MissingStoreError(f"Armazenamento da microrrede não encontrado em {self.data_dir}.")
        else:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        self._migrate()

    # ------------------------------------------------------------ conexão / migração
    def _connect(self) -> sqlite3.Connection:
        if self._must_exist:
            if not self.path.is_file():
                raise MicrogridDeletedError("A microrrede não existe mais (excluída em outra sessão).")
            try:            # mode=rw: se o arquivo sumir, falha — nunca cria um banco vazio
                con = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=10.0, isolation_level=None)
            except sqlite3.OperationalError:
                raise MicrogridDeletedError("A microrrede não existe mais (excluída em outra sessão).") from None
        else:
            con = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        con.row_factory = sqlite3.Row
        ensure_wal(con)
        con.execute("PRAGMA busy_timeout=10000")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def _check_alive(self, con: sqlite3.Connection) -> None:
        """Recusa operar numa microrrede com lápide ou de outra incarnação (ver docstring da classe)."""
        try:
            rows = {r[0]: r[1] for r in con.execute(
                "SELECT key, value FROM meta WHERE key IN (?, ?)", (LIFECYCLE_KEY, INCARNATION_KEY)).fetchall()}
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc):            # banco ainda vazio (antes da primeira migração)
                return
            raise
        if rows.get(LIFECYCLE_KEY):
            raise MicrogridDeletedError("A microrrede foi excluída; nenhuma leitura ou gravação é aceita.")
        if self.incarnation is not None and rows.get(INCARNATION_KEY) != self.incarnation:
            raise MicrogridDeletedError("A microrrede aberta foi excluída e substituída por outra com o mesmo "
                                        "identificador; reabra-a pelo Gestor.")

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")              # bloqueio de escrita desta microrrede (ponto de serialização)
            self._check_alive(con)                      # lápide/incarnação verificadas SOB o bloqueio
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
        """Leitura numa TRANSAÇÃO de leitura explícita (H-03). Em WAL, o instantâneo é fixado na primeira consulta
        — a própria verificação da lápide/incarnação — e todas as consultas seguintes desta leitura veem o MESMO
        estado. Política: uma leitura cujo instantâneo é anterior à lápide termina sobre esse estado válido
        anterior; uma leitura iniciada depois do COMMIT da lápide é recusada. Nunca se verifica um estado e se
        consulta outro."""
        con = self._connect()
        try:
            con.execute("BEGIN")                        # DEFERRED: o instantâneo nasce na verificação abaixo
            self._check_alive(con)
            yield con
        finally:
            if con.in_transaction:
                con.execute("ROLLBACK")                 # somente leitura: nada a confirmar
            con.close()

    def stamp_incarnation(self, incarnation: str) -> str:
        """Grava a incarnação (se ainda não houver) e devolve a efetivamente gravada (idempotente entre processos)."""
        with self._tx() as con:
            con.execute("INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)", (INCARNATION_KEY, incarnation))
            return con.execute("SELECT value FROM meta WHERE key = ?", (INCARNATION_KEY,)).fetchone()[0]

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
                self._check_alive(con)
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
        except MissingStoreError:
            raise                                       # microrrede excluída/substituída: o tipo é preservado
        except StoreError as exc:
            msg = str(exc)
            if "banco mantido na versão anterior" not in msg:
                msg = f"Migração do banco interrompida (banco mantido na versão anterior): {msg}"
            raise StoreError(msg) from None
        finally:
            con.close()

    # ------------------------------------------------------------ leitura
    @staticmethod
    def _load_con(con: sqlite3.Connection) -> Stored | None:
        row = con.execute("SELECT * FROM microgrid WHERE id = 1").fetchone()
        if row is None:
            return None
        return Stored(json.loads(row["document"]), int(row["revision"]), row["fingerprint"], row["saved_at"])

    def load(self) -> Stored | None:
        with self._read() as con:
            return self._load_con(con)

    def is_commissioned(self) -> bool:
        s = self.load()
        return bool(s and s.config.get("commissioning", {}).get("completed"))

    @staticmethod
    def _history_con(con: sqlite3.Connection, limit: int) -> list[dict]:
        rows = con.execute("SELECT revision, fingerprint, saved_at, note, origin FROM revisions "
                           "ORDER BY revision DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def history(self, limit: int = 50) -> list[dict]:
        with self._read() as con:
            return self._history_con(con, limit)

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
            return self._get_blob_con(con, digest)

    @staticmethod
    def _get_blob_con(con: sqlite3.Connection, digest: str) -> bytes:
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

    # ------------------------------------------------------------ cenários operativos (Piso 2A)
    # O documento do cenário é validado pelo domínio (``seeds2.operation``) ANTES de chegar aqui; o armazenamento
    # garante a integridade relacional DENTRO da transação da microrrede (lápide/incarnação verificadas por
    # ``_tx``/``_read``): identidade da microrrede, revisão-base existente com a mesma impressão digital,
    # concorrência otimista por versão e histórico append-only.
    _SCN_UID = re.compile(r"[0-9a-f]{32}")

    @staticmethod
    def _scenario_row(row: sqlite3.Row, *, created_at: str | None = None) -> StoredScenario:
        """Linha de ``scenarios`` (estado atual) ou de ``scenario_versions`` (versão imutável)."""
        keys = row.keys()
        doc = json.loads(row["document"])
        return StoredScenario(row["scenario_uid"], row["microgrid_uid"],
                              row["name"] if "name" in keys else str(doc.get("name") or ""), int(row["version"]),
                              int(row["base_revision"]), row["base_fingerprint"], row["fingerprint"], doc, row["origin"],
                              created_at or row["created_at"], row["updated_at"] if "updated_at" in keys else row["saved_at"])

    def _check_scenario_base(self, con: sqlite3.Connection, doc: dict) -> tuple[str, int, str]:
        """Identidade da microrrede e revisão-base, verificadas na MESMA transação da gravação."""
        mg = con.execute("SELECT installation_uid FROM microgrid WHERE id = 1").fetchone()
        if mg is None:
            raise StoreError("A microrrede ainda não tem configuração salva; não é possível criar cenários.")
        mg_uid = (doc.get("microgrid") or {}).get("uid")
        if mg_uid != mg["installation_uid"] or (self.fixed_uid is not None and mg_uid != self.fixed_uid):
            raise IdentityError("O cenário pertence a outra microrrede; nada foi gravado.")
        inc = (doc.get("microgrid") or {}).get("incarnation")
        cur_inc = con.execute("SELECT value FROM meta WHERE key = ?", (INCARNATION_KEY,)).fetchone()
        if inc is not None and cur_inc is not None and inc != cur_inc[0]:
            raise IdentityError("O cenário foi definido para outra incarnação desta microrrede (excluída e "
                                "reimportada); nada foi gravado.")
        ref = doc.get("inventory_ref") or {}
        base_rev, base_fp = ref.get("config_revision"), ref.get("config_fingerprint")
        if not isinstance(base_rev, int) or isinstance(base_rev, bool) or not isinstance(base_fp, str):
            raise StoreError("Cenário sem referência válida ao inventário (revisão/impressão digital).")
        row = con.execute("SELECT fingerprint FROM revisions WHERE revision = ?", (base_rev,)).fetchone()
        if row is None or row["fingerprint"] != base_fp:
            raise StoreError(f"A revisão {base_rev} do inventário referenciada pelo cenário não existe nesta "
                             "microrrede com a mesma impressão digital; nada foi gravado.")
        return mg_uid, base_rev, base_fp

    @staticmethod
    def _scenario_blobs(doc: Any) -> set[str]:
        """SHA-256 referenciados pelas previsões do cenário (Piso 2B): série normalizada (``data``) e arquivo
        original (``blob``). Tolerante a estruturas inválidas."""
        refs: set[str] = set()
        fc = doc.get("forecasts") if isinstance(doc, dict) else None
        for entry in (fc.values() if isinstance(fc, dict) else []):
            if isinstance(entry, dict):
                for k in ("data", "blob"):
                    v = entry.get(k)
                    if isinstance(v, str) and _HEX64.fullmatch(v):
                        refs.add(v)
        return refs

    def _store_scenario_blobs(self, con: sqlite3.Connection, doc: dict,
                              new_blobs: dict[str, tuple[bytes, dict]] | None) -> None:
        """Dentro de ``_tx``: insere os blobs novos (conteúdo conferido com o SHA-256 declarado) e exige que TODO blob
        referenciado pelo cenário exista. Qualquer falha desfaz a transação inteira (versão + blobs): nunca um
        documento referenciando blob inexistente, nunca um blob gravado por uma versão recusada."""
        for digest, (content, meta) in (new_blobs or {}).items():
            if self._insert_blob(con, bytes(content), str((meta or {}).get("name", ""))[:200],
                                 str((meta or {}).get("media_type", "text/csv"))[:100]) != digest:
                raise StoreError("Falha de integridade ao gravar os dados da previsão (SHA-256 divergente); nada foi gravado.")
        missing = [b for b in sorted(self._scenario_blobs(doc))
                   if con.execute("SELECT 1 FROM blobs WHERE sha256 = ?", (b,)).fetchone() is None]
        if missing:
            raise StoreError("Dados de previsão referenciados pelo cenário não estão armazenados nesta microrrede "
                             f"({', '.join(m[:12] + '…' for m in missing)}); nada foi gravado.")

    def create_scenario(self, doc: dict, *, origin: str = "new", note: str = "",
                        new_blobs: dict[str, tuple[bytes, dict]] | None = None) -> StoredScenario:
        """Grava um cenário NOVO (versão 1). ``doc['scenario_uid']`` deve ser novo nesta microrrede."""
        uid = doc.get("scenario_uid")
        if not (isinstance(uid, str) and self._SCN_UID.fullmatch(uid)):
            raise StoreError("Identificador de cenário inválido.")
        text, fp = C.canonical_json(doc), C.fingerprint(doc)
        name = str(doc.get("name") or "").strip()
        now = C.utc_now()
        with self._tx() as con:
            mg_uid, base_rev, base_fp = self._check_scenario_base(con, doc)
            if con.execute("SELECT 1 FROM scenarios WHERE scenario_uid = ?", (uid,)).fetchone() is not None:
                raise StoreError("Já existe um cenário com este identificador nesta microrrede.")
            self._store_scenario_blobs(con, doc, new_blobs)
            con.execute("INSERT INTO scenarios(scenario_uid, microgrid_uid, name, version, base_revision, base_fingerprint, "
                        "fingerprint, document, origin, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (uid, mg_uid, name, 1, base_rev, base_fp, fp, text, str(origin), now, now))
            con.execute("INSERT INTO scenario_versions(scenario_uid, version, microgrid_uid, base_revision, base_fingerprint, "
                        "fingerprint, document, saved_at, note, origin) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (uid, 1, mg_uid, base_rev, base_fp, fp, text, now, str(note), str(origin)))
            row = con.execute("SELECT * FROM scenarios WHERE scenario_uid = ?", (uid,)).fetchone()
            return self._scenario_row(row)

    def save_scenario(self, doc: dict, expected_version: int, *, note: str = "", origin: str = "edit",
                      new_blobs: dict[str, tuple[bytes, dict]] | None = None) -> StoredScenario:
        """Grava uma NOVA versão se o conteúdo mudou. Concorrência otimista: se outra sessão salvou depois de
        ``expected_version``, levanta ``ScenarioConflictError`` (nada é sobrescrito)."""
        uid = doc.get("scenario_uid")
        text, fp = C.canonical_json(doc), C.fingerprint(doc)
        name = str(doc.get("name") or "").strip()
        with self._tx() as con:
            row = con.execute("SELECT * FROM scenarios WHERE scenario_uid = ?", (uid,)).fetchone()
            if row is None:
                raise ScenarioNotFound("O cenário não existe nesta microrrede.")
            if int(row["version"]) != int(expected_version):
                raise ScenarioConflictError(uid, int(expected_version), int(row["version"]))
            mg_uid, base_rev, base_fp = self._check_scenario_base(con, doc)
            if mg_uid != row["microgrid_uid"]:
                raise IdentityError("O cenário pertence a outra microrrede; nada foi gravado.")
            if row["fingerprint"] == fp:
                return self._scenario_row(row)
            self._store_scenario_blobs(con, doc, new_blobs)
            ver, now = int(row["version"]) + 1, C.utc_now()
            con.execute("INSERT INTO scenario_versions(scenario_uid, version, microgrid_uid, base_revision, base_fingerprint, "
                        "fingerprint, document, saved_at, note, origin) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (uid, ver, mg_uid, base_rev, base_fp, fp, text, now, str(note), str(origin)))
            con.execute("UPDATE scenarios SET name=?, version=?, base_revision=?, base_fingerprint=?, fingerprint=?, "
                        "document=?, updated_at=? WHERE scenario_uid=?", (name, ver, base_rev, base_fp, fp, text, now, uid))
            return self._scenario_row(con.execute("SELECT * FROM scenarios WHERE scenario_uid = ?", (uid,)).fetchone())

    def get_scenario(self, scenario_uid: str, version: int | None = None) -> StoredScenario:
        """Versão atual (ou a ``version`` pedida, imutável) de um cenário DESTA microrrede."""
        with self._read() as con:
            cur = con.execute("SELECT * FROM scenarios WHERE scenario_uid = ?", (str(scenario_uid),)).fetchone()
            if cur is None:
                raise ScenarioNotFound("O cenário não existe nesta microrrede.")
            if version is None:
                return self._scenario_row(cur)
            row = con.execute("SELECT * FROM scenario_versions WHERE scenario_uid = ? AND version = ?",
                              (str(scenario_uid), int(version))).fetchone()
            if row is None:
                raise ScenarioNotFound(f"Versão {version} do cenário inexistente.")
            return self._scenario_row(row, created_at=cur["created_at"])

    def list_scenarios(self) -> list[StoredScenario]:
        with self._read() as con:
            rows = con.execute("SELECT * FROM scenarios ORDER BY created_at, rowid").fetchall()
        return [self._scenario_row(r) for r in rows]

    def scenario_history(self, scenario_uid: str, limit: int = 100) -> list[dict]:
        with self._read() as con:
            rows = con.execute("SELECT version, base_revision, fingerprint, saved_at, note, origin FROM scenario_versions "
                               "WHERE scenario_uid = ? ORDER BY version DESC LIMIT ?", (str(scenario_uid), int(limit))).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ rodadas de cenário (Piso 2C)
    # Ciclo de vida: ``start_run`` (linha 'em_execucao' + manifesto imutável) → ``heartbeat_run`` (progresso real do
    # motor) → ``finish_run`` (dados + resumo + estado 'concluida' NA MESMA transação) ou ``fail_run`` ('falhou' /
    # 'interrompida', sem dados). Nenhum resultado parcial é marcado como concluído. Toda operação passa por
    # ``_tx``/``_read`` (lápide e incarnação verificadas — H-01/H-02/H-03).
    _RUN_UID = re.compile(r"[0-9a-f]{32}")
    RUN_FINAL_STATES = ("concluida", "falhou", "interrompida")

    @staticmethod
    def _run_row(con: sqlite3.Connection, row: sqlite3.Row) -> StoredRun:
        data = {r["name"]: {"sha256": r["sha256"], "media_type": r["media_type"], "size": int(r["size"])}
                for r in con.execute("SELECT name, sha256, media_type, size FROM scenario_run_data WHERE run_uid = ? "
                                     "ORDER BY name", (row["run_uid"],)).fetchall()}
        js = (lambda v: json.loads(v) if v else None)
        return StoredRun(row["run_uid"], row["request_id"], row["microgrid_uid"], row["incarnation"], row["scenario_uid"],
                         int(row["scenario_version"]), row["scenario_fingerprint"], int(row["config_revision"]),
                         row["config_fingerprint"], row["state"], row["owner"], row["created_at"], row["heartbeat_at"],
                         row["finished_at"], json.loads(row["progress"] or "{}"), json.loads(row["manifest"]),
                         js(row["outcome"]), js(row["summary"]), js(row["error"]), data)

    @staticmethod
    def _recover_con(con: sqlite3.Connection, is_dead) -> list[str]:
        """Dentro de ``_tx``: rodadas 'em_execucao' cujo dono morreu (processo encerrado, servidor reiniciado) passam a
        'interrompida' — nunca a 'concluida' — e ficam imutáveis, sem dados."""
        out = []
        for r in con.execute("SELECT run_uid, owner, heartbeat_at FROM scenario_runs WHERE state = 'em_execucao'").fetchall():
            if is_dead(r["run_uid"], r["owner"], r["heartbeat_at"]):
                err = {"kind": "interrupcao", "message": "Execução interrompida: o processo que a executava terminou "
                       "(encerramento ou reinício do servidor) antes da conclusão. Nenhum resultado foi gravado."}
                con.execute("UPDATE scenario_runs SET state = 'interrompida', finished_at = ?, error = ? WHERE run_uid = ?",
                            (C.utc_now(), C.canonical_json(err), r["run_uid"]))
                out.append(r["run_uid"])
        return out

    def recover_runs(self, is_dead) -> list[str]:
        with self._tx() as con:
            return self._recover_con(con, is_dead)

    def start_run(self, *, run_uid: str, request_id: str, scenario_uid: str, scenario_version: int,
                  scenario_fingerprint: str, manifest: dict, owner: str, is_dead=None) -> tuple[StoredRun, bool]:
        """Abre uma rodada sobre a versão IMUTÁVEL ``scenario_version``. Idempotente por ``request_id`` (o mesmo pedido
        nunca executa duas vezes: devolve ``(rodada existente, False)``). Recusa se já houver rodada em execução nesta
        microrrede (``RunBusyError``) ou se a versão não existir/tiver outra impressão digital."""
        if not (isinstance(run_uid, str) and self._RUN_UID.fullmatch(run_uid)):
            raise StoreError("Identificador de rodada inválido.")
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 80:
            raise StoreError("Identificador de pedido de execução inválido.")
        now = C.utc_now()
        with self._tx() as con:
            ex = con.execute("SELECT * FROM scenario_runs WHERE request_id = ?", (request_id,)).fetchone()
            if ex is not None:
                return self._run_row(con, ex), False
            if is_dead is not None:
                self._recover_con(con, is_dead)
            busy = con.execute("SELECT run_uid FROM scenario_runs WHERE state = 'em_execucao'").fetchone()
            if busy is not None:
                raise RunBusyError(f"Já há uma execução em andamento nesta microrrede (rodada {busy[0][:8]}…); "
                                   "aguarde a conclusão. Nada foi iniciado.")
            sv = con.execute("SELECT * FROM scenario_versions WHERE scenario_uid = ? AND version = ?",
                             (str(scenario_uid), int(scenario_version))).fetchone()
            if sv is None:
                raise ScenarioNotFound(f"Versão {scenario_version} do cenário inexistente nesta microrrede.")
            if sv["fingerprint"] != scenario_fingerprint:
                raise StoreError("A versão do cenário gravada difere da versão preparada (impressão digital); nada foi "
                                 "iniciado.")
            mg = con.execute("SELECT installation_uid FROM microgrid WHERE id = 1").fetchone()
            if mg is None or mg["installation_uid"] != sv["microgrid_uid"] or (
                    self.fixed_uid is not None and sv["microgrid_uid"] != self.fixed_uid):
                raise IdentityError("O cenário pertence a outra microrrede; nada foi iniciado.")
            inc = con.execute("SELECT value FROM meta WHERE key = ?", (INCARNATION_KEY,)).fetchone()
            con.execute("INSERT INTO scenario_runs(run_uid, request_id, microgrid_uid, incarnation, scenario_uid, "
                        "scenario_version, scenario_fingerprint, config_revision, config_fingerprint, state, owner, "
                        "created_at, heartbeat_at, progress, manifest) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (run_uid, request_id, sv["microgrid_uid"], inc[0] if inc else None, sv["scenario_uid"],
                         int(sv["version"]), sv["fingerprint"], int(sv["base_revision"]), sv["base_fingerprint"],
                         "em_execucao", str(owner), now, now, C.canonical_json({"phase": "preparando"}),
                         C.canonical_json(manifest)))
            return self._run_row(con, con.execute("SELECT * FROM scenario_runs WHERE run_uid = ?", (run_uid,)).fetchone()), True

    def heartbeat_run(self, run_uid: str, owner: str, progress: dict) -> bool:
        """Atualiza o progresso REAL (fase e passo do motor). Falso se a rodada não está mais em execução por este dono."""
        with self._tx() as con:
            cur = con.execute("UPDATE scenario_runs SET heartbeat_at = ?, progress = ? WHERE run_uid = ? AND owner = ? "
                              "AND state = 'em_execucao'", (C.utc_now(), C.canonical_json(progress), run_uid, owner))
            return cur.rowcount == 1

    def _open_run(self, con: sqlite3.Connection, run_uid: str, owner: str) -> sqlite3.Row:
        row = con.execute("SELECT * FROM scenario_runs WHERE run_uid = ?", (run_uid,)).fetchone()
        if row is None:
            raise RunNotFound("A rodada não existe nesta microrrede.")
        if row["state"] != "em_execucao" or row["owner"] != owner:
            raise RunStateError(f"A rodada não está mais em execução por este processo (estado: {row['state']}); "
                                "nada foi gravado.")
        return row

    def finish_run(self, run_uid: str, owner: str, *, outcome: dict, summary: dict,
                   data: dict[str, tuple[bytes, str]]) -> StoredRun:
        """Conclui a rodada: grava TODOS os dados, o resultado e o estado 'concluida' numa única transação."""
        import zlib

        with self._tx() as con:
            self._open_run(con, run_uid, owner)
            for name, (content, media_type) in sorted(data.items()):
                raw = bytes(content)
                if len(raw) > MAX_BLOB_BYTES * 4:
                    raise StoreError(f"Dado de rodada '{name}' grande demais; nada foi gravado.")
                packed = zlib.compress(raw, 6) if len(raw) > 2048 else raw
                con.execute("INSERT INTO scenario_run_data(run_uid, name, sha256, media_type, encoding, size, content) "
                            "VALUES (?,?,?,?,?,?,?)", (run_uid, str(name)[:200], sha256(raw).hexdigest(), str(media_type)[:100],
                                                       "zlib" if packed is not raw else "identity", len(raw), packed))
            now = C.utc_now()
            con.execute("UPDATE scenario_runs SET state = 'concluida', finished_at = ?, heartbeat_at = ?, progress = ?, "
                        "outcome = ?, summary = ? WHERE run_uid = ?",
                        (now, now, C.canonical_json({"phase": "concluida"}), C.canonical_json(outcome),
                         C.canonical_json(summary), run_uid))
            return self._run_row(con, con.execute("SELECT * FROM scenario_runs WHERE run_uid = ?", (run_uid,)).fetchone())

    def fail_run(self, run_uid: str, owner: str, error: dict, *, state: str = "falhou", outcome: dict | None = None) -> StoredRun:
        """Finaliza SEM resultados ('falhou' ou 'interrompida'); a linha fica imutável com o motivo."""
        if state not in ("falhou", "interrompida"):
            raise StoreError("Estado final inválido para falha.")
        with self._tx() as con:
            self._open_run(con, run_uid, owner)
            now = C.utc_now()
            con.execute("UPDATE scenario_runs SET state = ?, finished_at = ?, heartbeat_at = ?, error = ?, outcome = ? "
                        "WHERE run_uid = ?", (state, now, now, C.canonical_json(error),
                                              C.canonical_json(outcome) if outcome is not None else None, run_uid))
            return self._run_row(con, con.execute("SELECT * FROM scenario_runs WHERE run_uid = ?", (run_uid,)).fetchone())

    def get_run(self, run_uid: str) -> StoredRun:
        with self._read() as con:
            row = con.execute("SELECT * FROM scenario_runs WHERE run_uid = ?", (str(run_uid),)).fetchone()
            if row is None:
                raise RunNotFound("A rodada não existe nesta microrrede.")
            return self._run_row(con, row)

    def list_runs(self, scenario_uid: str | None = None, limit: int = 200) -> list[StoredRun]:
        with self._read() as con:
            if scenario_uid is None:
                rows = con.execute("SELECT * FROM scenario_runs ORDER BY created_at DESC, rowid DESC LIMIT ?",
                                   (int(limit),)).fetchall()
            else:
                rows = con.execute("SELECT * FROM scenario_runs WHERE scenario_uid = ? ORDER BY created_at DESC, rowid DESC "
                                   "LIMIT ?", (str(scenario_uid), int(limit))).fetchall()
            return [self._run_row(con, r) for r in rows]

    def count_scenario_runs(self) -> dict[str, int]:
        with self._read() as con:
            rows = con.execute("SELECT state, COUNT(*) FROM scenario_runs GROUP BY state").fetchall()
        return {r[0]: int(r[1]) for r in rows}

    def run_data(self, run_uid: str, name: str) -> bytes:
        """Conteúdo de um dado da rodada (SHA-256 conferido)."""
        import zlib

        with self._read() as con:
            row = con.execute("SELECT sha256, encoding, content FROM scenario_run_data WHERE run_uid = ? AND name = ?",
                              (str(run_uid), str(name))).fetchone()
        if row is None:
            raise RunNotFound(f"Dado '{name}' não encontrado na rodada.")
        try:
            raw = zlib.decompress(bytes(row["content"])) if row["encoding"] == "zlib" else bytes(row["content"])
        except zlib.error:
            raise StoreError(f"Dado '{name}' da rodada corrompido (descompressão).") from None
        if sha256(raw).hexdigest() != row["sha256"]:
            raise StoreError(f"Dado '{name}' da rodada corrompido (hash divergente).")
        return raw

    # ------------------------------------------------------------ backup / restauração
    def export_backup(self) -> bytes:
        """Backup de UM instantâneo (H-03): configuração, blobs, histórico e versão lidos na mesma transação de
        leitura — o manifesto nunca descreve uma revisão diferente da do histórico ou dos dados."""
        from seeds2 import APP_VERSION

        files: dict[str, bytes] = {}
        blob_meta = {}
        with self._read() as con:
            cur = self._load_con(con)
            if cur is None:
                raise StoreError("Não há configuração salva para exportar.")
            files["configuration.json"] = json.dumps(cur.config, ensure_ascii=False, indent=2).encode("utf-8")
            for b in sorted(self._referenced_blobs(cur.config)):
                files[f"blobs/{b}"] = self._get_blob_con(con, b)
                blob_meta[b] = self._blob_meta(con, b)
            history = self._history_con(con, 10_000)
            db_version = int(con.execute("PRAGMA user_version").fetchone()[0])
        files["history.json"] = json.dumps(history, ensure_ascii=False, indent=2).encode("utf-8")
        manifest = {
            "format": BACKUP_FORMAT, "format_version": BACKUP_FORMAT_VERSION,
            "db_schema_version": db_version, "doc_schema_version": cur.config.get("schema_version"),
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


__all__: list[Any] = ["BackupInspection", "ConflictError", "IdentityError", "MicrogridDeletedError", "MicrogridStore",
                      "MissingStoreError", "ScenarioConflictError", "ScenarioNotFound", "Stored", "StoredScenario",
                      "StoreError", "ValidationError", "backup_filename", "default_store", "inspect_backup_data",
                      "resolve_data_dir", "sqlite_backup_copy"]
