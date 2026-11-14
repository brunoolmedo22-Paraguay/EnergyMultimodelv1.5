"""Instantânea COMPLETA de uma microrrede (``.seeds2snapshot.zip``) — sem Streamlit.

Decisão do responsável (missão «Exemplos persistentes», 14/11/2026): os casos de exemplo entregues com o SEEDS2
precisam sobreviver ao reinício do Streamlit Cloud, cujo disco é efímero. O backup (``.seeds2backup.zip``) só leva a
configuração, e o estudo (``.seeds2study.zip``) só abre um cenário no Arquivo Científico. A instantânea leva o
banco INTEIRO da microrrede — configuração, revisões, dados de entrada, cenários e suas versões, previsões,
estratégias, rodadas (Simulação V1.6 e cenários V1.6/V2) e todos os dados gravados das rodadas — e, restaurada,
reproduz a microrrede exatamente como estava.

Formato (versão 1)::

    manifest.json   formato, versões, identidade, revisão, impressão digital, contagens por tabela, SHA-256 do banco
    seeds2.db       cópia transacionalmente consistente do banco (API de backup do SQLite; journal DELETE)

Garantias:

* **exportação**: cópia por ``sqlite_backup_copy`` (inclui o ``-wal``; ``integrity_check``), recusada se houver lápide
  ou rodada em execução (estado não reprodutível). A **incarnação viaja** com a instantânea: os documentos dos
  cenários a registram e só aceitam novas versões na mesma incarnação;
* **inspeção** (entrada tratada como NÃO confiável, nunca levanta exceção): limites de tamanho lidos em blocos,
  exatamente duas entradas, manifesto validado campo a campo, SHA-256, ``integrity_check``, versão do esquema,
  identidade, ausência de lápide e de rodada em execução, contagens iguais às do manifesto e **esquema idêntico**
  ao que esta versão do SEEDS2 cria (nenhuma tabela, índice, gatilho ou visão a mais ou a menos);
* a **restauração** é feita pelo catálogo (``MicrogridRegistry.import_snapshot``) com o mesmo protocolo recuperável
  da criação/importação: preparação em ``.staging``, verificação e confirmação atômica.

Não confundir com o backup (configuração) nem com o estudo científico (um cenário, para o Arquivo Científico).
"""
from __future__ import annotations

import io
import json
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from . import config as C
from .store import (DB_FILENAME, INCARNATION_KEY, LATEST_DB_VERSION, LIFECYCLE_KEY, MicrogridStore, StoreError,
                    sqlite_backup_copy)

FORMAT = "seeds2-snapshot"
FORMAT_VERSION = 1
SUFFIX = ".seeds2snapshot.zip"
MANIFEST = "manifest.json"
MAX_PACKAGE_BYTES = 512 * 1024 * 1024
MAX_DB_BYTES = 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX64 = re.compile(r"[0-9a-f]{64}")

# Tabelas cujo número de linhas é comprometido no manifesto (``meta`` fica de fora: guarda marcas de catálogo).
COUNTED_TABLES = ("revisions", "blobs", "simulation_runs", "scenarios", "scenario_versions", "scenario_runs",
                  "scenario_run_data")


class SnapshotError(StoreError):
    """Instantânea recusada (exportação ou restauração)."""


@dataclass
class SnapshotInspection:
    ok: bool = False
    errors: list[str] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)
    db_bytes: bytes = b""

    @property
    def uid(self) -> str:
        return str(self.manifest.get("installation_uid", ""))


# ============================================================================ utilidades do banco
def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True, isolation_level=None)


def _tables(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}


def counts(db: Path) -> dict[str, int]:
    """Número de linhas das tabelas comprometidas (tabela ausente na versão do banco = 0)."""
    con = _ro(db)
    try:
        present = _tables(con)
        return {t: (int(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]) if t in present else 0)
                for t in COUNTED_TABLES}
    finally:
        con.close()


def schema(db: Path) -> list[tuple]:
    """Esquema declarado (tabelas, índices, gatilhos, visões), sem objetos internos do SQLite."""
    con = _ro(db)
    try:
        return sorted(tuple(r) for r in con.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall())
    finally:
        con.close()


_REFERENCE: dict[int, list[tuple]] = {}


def reference_schema() -> list[tuple]:
    """Esquema que ESTA versão do SEEDS2 cria para um banco de microrrede (versão ``LATEST_DB_VERSION``)."""
    if LATEST_DB_VERSION not in _REFERENCE:
        with tempfile.TemporaryDirectory(prefix="seeds2_schema_") as tmp:
            MicrogridStore(tmp)                                  # banco vazio, todas as migrações aplicadas
            _REFERENCE[LATEST_DB_VERSION] = schema(Path(tmp) / DB_FILENAME)
    return _REFERENCE[LATEST_DB_VERSION]


def _identity(db: Path) -> dict:
    con = _ro(db)
    try:
        row = con.execute("SELECT installation_uid, revision, fingerprint FROM microgrid WHERE id = 1").fetchone()
        meta = {r[0]: r[1] for r in con.execute("SELECT key, value FROM meta").fetchall()} if "meta" in _tables(con) else {}
        running = (con.execute("SELECT count(*) FROM scenario_runs WHERE state = 'em_execucao'").fetchone()[0]
                   if "scenario_runs" in _tables(con) else 0)
        return {"row": tuple(row) if row else None, "user_version": int(con.execute("PRAGMA user_version").fetchone()[0]),
                "integrity": con.execute("PRAGMA integrity_check").fetchone()[0], "meta": meta, "running": int(running)}
    finally:
        con.close()


def state_stamp(store: MicrogridStore) -> str:
    """Impressão barata do ESTADO COMPLETO (não só da configuração): muda com novas revisões, versões de cenário e
    rodadas. Usada pelo Gestor para saber se uma instantânea já preparada ainda corresponde ao banco."""
    with store._read() as con:                                   # noqa: SLF001 — leitura de instantâneo único (H-03)
        row = con.execute("SELECT revision, fingerprint FROM microgrid WHERE id = 1").fetchone()
        parts = [repr(tuple(row)) if row is not None else ""]                # valores, nunca o objeto ``Row``
        for t in COUNTED_TABLES:
            parts.append(str(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]))
        parts.append(str(con.execute("SELECT max(coalesce(finished_at, heartbeat_at, created_at)) FROM scenario_runs").fetchone()[0]))
        parts.append(str(con.execute("SELECT max(saved_at) FROM scenario_versions").fetchone()[0]))
    return sha256("|".join(parts).encode()).hexdigest()


# ============================================================================ exportação
def snapshot_filename(config: dict) -> str:
    from .store import backup_filename

    return backup_filename(config).replace(".seeds2backup.zip", SUFFIX)


def export_snapshot(store: MicrogridStore) -> bytes:
    """Gera a instantânea completa da microrrede de ``store``. Recusa banco com lápide ou rodada em execução."""
    from seeds2 import APP_VERSION

    cur = store.load()                                           # verifica lápide/incarnação (leitura válida)
    if cur is None:
        raise SnapshotError("Não há configuração salva para guardar.")
    with tempfile.TemporaryDirectory(prefix="seeds2_snapshot_") as tmp:
        copy = Path(tmp) / DB_FILENAME
        store._backup_copy(copy)                                 # noqa: SLF001 — cópia consistente (inclui o -wal)
        con = sqlite3.connect(copy, isolation_level=None)
        try:
            if con.execute("SELECT 1 FROM meta WHERE key = ?", (LIFECYCLE_KEY,)).fetchone():
                raise SnapshotError("A microrrede foi excluída; nada foi guardado.")
            if con.execute("SELECT 1 FROM scenario_runs WHERE state = 'em_execucao'").fetchone():
                raise SnapshotError("Há uma rodada em execução nesta microrrede. Aguarde a conclusão (ou o cancelamento) "
                                    "e guarde de novo: uma rodada em andamento não pode ser reproduzida.")
            # A incarnação VIAJA com a instantânea: os documentos dos cenários a registram (``microgrid.incarnation``) e
            # o armazenamento recusa novas versões de um cenário de outra incarnação. Restaurada com a MESMA incarnação,
            # a microrrede continua editável (decisão: exemplos editáveis). A restauração só acontece ao iniciar o
            # processo, quando nenhuma sessão antiga pode guardar referência a uma incarnação anterior.
            if not con.execute("SELECT 1 FROM meta WHERE key = ?", (INCARNATION_KEY,)).fetchone():
                raise SnapshotError("A microrrede não tem incarnação registrada; reabra-a pelo Gestor e guarde de novo.")
            con.execute("VACUUM")
        finally:
            con.close()
        ident = _identity(copy)
        if ident["integrity"] != "ok" or ident["row"] is None or ident["row"][0] != cur.config["installation"]["uid"]:
            raise SnapshotError("A cópia do banco não passou na verificação; nada foi guardado.")
        db = copy.read_bytes()
        n = counts(copy)
    manifest = {
        "format": FORMAT, "format_version": FORMAT_VERSION, "created_at": C.utc_now(), "app_version": APP_VERSION,
        "db_schema_version": ident["user_version"], "installation_uid": ident["row"][0],
        "installation_name": str(cur.config["installation"].get("name", ""))[:300],
        "revision": int(ident["row"][1]), "fingerprint": ident["row"][2],
        "counts": n, "db_sha256": sha256(db).hexdigest(), "db_size": len(db),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(DB_FILENAME, db)
    return buf.getvalue()


# ============================================================================ inspeção (entrada NÃO confiável)
def _read_capped(zf: zipfile.ZipFile, info: zipfile.ZipInfo, cap: int) -> bytes:
    out = bytearray()
    with zf.open(info) as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                return bytes(out)
            out += chunk
            if len(out) > cap:
                raise SnapshotError(f"«{info.filename}» excede o limite de {cap // (1024 * 1024)} MiB")


def _check_manifest(m: object, errors: list[str]) -> dict:
    if not isinstance(m, dict):
        errors.append("manifest.json não é um objeto JSON.")
        return {}
    if m.get("format") != FORMAT:
        errors.append(f"Formato desconhecido ({str(m.get('format'))[:40]!r}); esperado «{FORMAT}».")
    if m.get("format_version") != FORMAT_VERSION:
        errors.append(f"Versão do formato não suportada ({str(m.get('format_version'))[:10]}).")
    if not (isinstance(m.get("installation_uid"), str) and _HEX32.fullmatch(m["installation_uid"])):
        errors.append("Identidade da microrrede inválida no manifesto.")
    if not (isinstance(m.get("db_sha256"), str) and _HEX64.fullmatch(m["db_sha256"])):
        errors.append("SHA-256 do banco ausente ou inválido no manifesto.")
    v = m.get("db_schema_version")
    if not (isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= LATEST_DB_VERSION):
        errors.append(f"Versão do esquema do banco não suportada por este SEEDS2 ({str(v)[:10]}; máximo "
                      f"v{LATEST_DB_VERSION}). Atualize o SEEDS2.")
    if not (isinstance(m.get("revision"), int) and not isinstance(m.get("revision"), bool) and m["revision"] >= 1):
        errors.append("Revisão inválida no manifesto.")
    if not isinstance(m.get("fingerprint"), str):
        errors.append("Impressão digital ausente no manifesto.")
    cnt = m.get("counts")
    if not (isinstance(cnt, dict) and set(cnt) == set(COUNTED_TABLES)
            and all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in cnt.values())):
        errors.append("Contagens do manifesto ausentes ou inválidas.")
    return m


def inspect_snapshot(data: bytes) -> SnapshotInspection:
    """Verifica uma instantânea SEM gravar nada no armazenamento. Nunca levanta exceção: todo defeito vira erro."""
    rep = SnapshotInspection()
    try:
        if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_PACKAGE_BYTES:
            raise SnapshotError("Arquivo ausente ou maior que o limite (512 MiB).")
        try:
            zf = zipfile.ZipFile(io.BytesIO(bytes(data)))
        except zipfile.BadZipFile:
            raise SnapshotError("O arquivo não é um ZIP válido.") from None
        with zf:
            infos = zf.infolist()
            names = [i.filename for i in infos]
            if sorted(names) != sorted([MANIFEST, DB_FILENAME]):
                raise SnapshotError(f"Conteúdo inesperado: a instantânea deve ter exatamente «{MANIFEST}» e «{DB_FILENAME}».")
            for i in infos:
                if i.flag_bits & 0x1:
                    raise SnapshotError("Entradas criptografadas não são aceitas.")
                if i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise SnapshotError("Método de compressão não suportado.")
            raw_m = _read_capped(zf, zf.getinfo(MANIFEST), MAX_MANIFEST_BYTES)
            try:
                manifest = json.loads(raw_m.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise SnapshotError("manifest.json ilegível.") from None
            rep.manifest = _check_manifest(manifest, rep.errors)
            if rep.errors:
                return rep
            db = _read_capped(zf, zf.getinfo(DB_FILENAME), MAX_DB_BYTES)
        if sha256(db).hexdigest() != manifest["db_sha256"]:
            raise SnapshotError("O banco não corresponde ao SHA-256 do manifesto (arquivo alterado ou corrompido).")
        with tempfile.TemporaryDirectory(prefix="seeds2_snapshot_chk_") as tmp:
            path = Path(tmp) / DB_FILENAME
            path.write_bytes(db)
            try:
                ident = _identity(path)
                n = counts(path)
                if ident["user_version"] == LATEST_DB_VERSION and schema(path) != reference_schema():
                    rep.errors.append("O esquema do banco difere do que o SEEDS2 cria (tabelas, índices, gatilhos ou "
                                      "visões a mais ou a menos); instantânea recusada.")
            except sqlite3.DatabaseError as exc:
                raise SnapshotError(f"O banco da instantânea não é legível: {exc}") from None
        if ident["integrity"] != "ok":
            rep.errors.append(f"O banco não passou na verificação de integridade: {str(ident['integrity'])[:200]}")
        if ident["user_version"] != manifest["db_schema_version"]:
            rep.errors.append("A versão do esquema do banco difere da declarada no manifesto.")
        if ident["row"] is None:
            rep.errors.append("O banco não contém uma microrrede.")
        else:
            uid, revision, fingerprint = ident["row"]
            if uid != manifest["installation_uid"]:
                rep.errors.append("A identidade do banco difere da declarada no manifesto.")
            if revision != manifest["revision"] or fingerprint != manifest["fingerprint"]:
                rep.errors.append("Revisão ou impressão digital do banco diferem das declaradas no manifesto.")
        if ident["meta"].get(LIFECYCLE_KEY):
            rep.errors.append("O banco pertence a uma microrrede excluída.")
        if ident["running"]:
            rep.errors.append("O banco contém uma rodada em execução (estado não reprodutível).")
        if n != manifest["counts"]:
            rep.errors.append("O número de registros do banco difere do declarado no manifesto.")
        if not rep.errors:
            rep.ok = True
            rep.db_bytes = db
    except SnapshotError as exc:
        rep.errors.append(str(exc))
    except Exception as exc:  # noqa: BLE001 — entrada não confiável: nenhum defeito vira exceção
        rep.errors.append(f"Instantânea ilegível: {type(exc).__name__}: {str(exc)[:200]}")
    return rep
