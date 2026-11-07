"""Exportação de um cenário COMPLETO para o pacote portátil ``seeds2-study`` (Piso 2D-A).

Tudo é lido de UM instantâneo do banco da microrrede (``MicrogridStore.snapshot`` — H-03): versões, revisões do
inventário referenciadas, blobs, rodadas e seus dados formam um conjunto coerente mesmo com outras sessões gravando.
Documentos e manifestos são exportados com o TEXTO EXATO gravado na origem (sem reserialização: nenhuma perda de
precisão e nenhuma mudança de impressão digital); dados das rodadas são descomprimidos e conferidos pelo SHA-256.
O pacote é escrito recurso a recurso (sem montar tudo em memória). Nada aqui grava no banco da microrrede, executa
modelos ou chama o otimizador.

Rodadas em execução impedem a exportação (o arquivo contém somente rodadas finalizadas — concluídas, falhas e
interrompidas — com seus estados originais; nenhuma é convertida em concluída e nenhum resultado é inventado).
"""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from dataclasses import asdict, dataclass, is_dataclass
from hashlib import sha256
from pathlib import Path
from typing import IO, Any

from seeds2.microgrid import config as C
from seeds2.microgrid.migrations import MigrationError, migrate_document
from seeds2.microgrid.store import MicrogridStore, StoreError

from . import format as FMT

_FIXED_TIME = (1980, 1, 1, 0, 0, 0)       # datas fixas nas entradas: o mesmo conteúdo gera os mesmos bytes por recurso


class ExportError(StoreError):
    """A exportação não pôde ser feita (mensagem apresentável); nenhum arquivo parcial é entregue."""


@dataclass(frozen=True)
class ExportResult:
    path: Path | None
    filename: str
    size: int
    package_sha256: str
    content_id: str
    manifest: dict


def _jsonable(v: Any) -> Any:
    if is_dataclass(v) and not isinstance(v, type):
        v = asdict(v)
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_jsonable(x) for x in v]
    if isinstance(v, float):
        return v if v == v and v not in (float("inf"), float("-inf")) else None
    if isinstance(v, (str, int, bool)) or v is None:
        return v
    try:
        import numpy as np

        if isinstance(v, np.generic):
            return _jsonable(v.item())
        if isinstance(v, np.ndarray):
            return _jsonable(v.tolist())
    except ImportError:                                    # pragma: no cover
        pass
    return str(v)


def _strings(obj: Any, out: set[str]) -> set[str]:
    if isinstance(obj, dict):
        for x in obj.values():
            _strings(x, out)
    elif isinstance(obj, list):
        for x in obj:
            _strings(x, out)
    elif isinstance(obj, str) and len(obj) <= 200:
        out.add(obj)
    return out


def catalog_snapshot(revision_docs: dict[int, dict]) -> dict:
    """Instantâneo SOMENTE LEITURA das referências de catálogo citadas pelos equipamentos das revisões incluídas
    (para inspecionar o estudo sem o catálogo do software exportador). Falhas de leitura ficam registradas."""
    from seeds2.microgrid import references as R

    out: dict = {"note": "Instantâneo das referências técnicas (catálogos do software exportador) citadas pelo inventário. "
                         "Apenas consulta: o modelo científico usado pelas rodadas é identificado no manifesto de cada "
                         "rodada (SHA-256 do código científico).", "references": {}, "wind_curves": {}, "errors": []}
    used: set[str] = set()
    for doc in revision_docs.values():
        try:
            d, _ = migrate_document(json.loads(json.dumps(doc)))
        except (MigrationError, ValueError, TypeError):
            d = doc
        for eq in (d.get("equipment") or []) + (d.get("retired") or []):
            if isinstance(eq, dict):
                _strings(eq, used)
    for kind in R.KINDS:
        try:
            refs = R.references_for(kind)
        except Exception as exc:  # noqa: BLE001 — catálogo indisponível: registrado, não inventado
            out["errors"].append(f"{kind}: {type(exc).__name__}")
            continue
        hit = {k: _jsonable(v) for k, v in refs.items() if k in used}
        if hit:
            out["references"][kind] = hit
        if kind == "wind":
            for k in hit:
                try:
                    curve = R.wind_curve(k)
                except Exception:  # noqa: BLE001
                    curve = None
                if curve is not None:
                    out["wind_curves"][k] = _jsonable(curve)
    return out


class _Writer:
    def __init__(self, zf: zipfile.ZipFile):
        self.zf = zf
        self.resources: dict[str, dict] = {}

    def add(self, path: str, data: bytes, media_type: str, role: str, **extra: Any) -> None:
        if FMT.classify(path) is None:
            raise ExportError(f"Caminho de recurso não permitido pelo formato: {path!r}.")
        if path in self.resources:
            raise ExportError(f"Recurso duplicado: {path!r}.")
        info = zipfile.ZipInfo(path, date_time=_FIXED_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (0o100644 << 16)              # arquivo regular
        self.zf.writestr(info, data)
        self.resources[path] = {"sha256": sha256(data).hexdigest(), "size": len(data), "media_type": media_type,
                                "role": role, **{k: v for k, v in extra.items() if v is not None}}

    def json(self, path: str, obj: Any, role: str) -> None:
        self.add(path, json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8"), "application/json", role)

    def text(self, path: str, text: str, role: str) -> None:
        self.add(path, text.encode("utf-8"), "application/json", role)


def _blob_media_type(meta: dict) -> str:
    mt = str(meta.get("media_type") or "application/octet-stream")
    return mt if mt in FMT.BLOB_MEDIA_TYPES else "application/octet-stream"


def write_package(store: MicrogridStore, scenario_uid: str, fh: IO[bytes]) -> dict:
    """Escreve o pacote em ``fh`` (binário, gravável) e devolve o manifesto. ``ExportError`` se o cenário não puder ser
    exportado de forma íntegra."""
    from seeds2 import APP_NAME, APP_VERSION
    from seeds2.operation import runner

    with store.snapshot() as snap, zipfile.ZipFile(fh, "w", zipfile.ZIP_DEFLATED) as zf:
        w = _Writer(zf)
        scn = snap.scenario_row(scenario_uid)
        versions = snap.scenario_versions(scenario_uid)
        runs = snap.run_rows(scenario_uid)
        busy = [r["run_uid"] for r in runs if r["state"] not in FMT.RUN_FINAL_STATES]
        if busy:
            raise ExportError(f"Há {len(busy)} rodada(s) deste cenário em execução; aguarde a conclusão para exportar (o "
                              "arquivo científico contém somente rodadas finalizadas). Nada foi exportado.")
        if not versions:
            raise ExportError("O cenário não tem versões gravadas; nada foi exportado.")
        cur = snap.current()
        mg_uid = scn["microgrid_uid"]
        incarnation = snap.meta("incarnation")
        # ---- cenário e versões (texto exato do documento)
        w.json("scenario/scenario.json", {k: scn[k] for k in ("scenario_uid", "microgrid_uid", "name", "version",
                                                                 "base_revision", "base_fingerprint", "fingerprint", "origin",
                                                                 "created_at", "updated_at")}, "scenario")
        forecast_blobs: dict[str, str] = {}
        revisions: set[int] = set()
        for v in versions:
            w.json(FMT.version_path(v["version"]), {k: v[k] for k in ("scenario_uid", "version", "microgrid_uid",
                                                                       "base_revision", "base_fingerprint", "fingerprint",
                                                                       "saved_at", "note", "origin")}, "version_meta")
            w.text(FMT.version_path(v["version"], True), v["document"], "version_document")
            revisions.add(int(v["base_revision"]))
            for h in sorted(MicrogridStore._scenario_blobs(json.loads(v["document"]))):
                forecast_blobs.setdefault(h, f"v{v['version']}")
        for r in runs:
            revisions.add(int(r["config_revision"]))
        # ---- inventário de referência (revisões necessárias, texto exato) + dados referenciados
        rev_docs: dict[int, dict] = {}
        inv_blobs: set[str] = set()
        for rev in sorted(revisions):
            row = snap.revision_row(rev)
            w.json(FMT.revision_path(rev), {k: row[k] for k in ("revision", "installation_uid", "fingerprint", "saved_at",
                                                                 "note", "origin")}, "revision_meta")
            w.text(FMT.revision_path(rev, True), row["document"], "revision_document")
            rev_docs[rev] = json.loads(row["document"])
            inv_blobs |= MicrogridStore._referenced_blobs(rev_docs[rev])
        for h in sorted(inv_blobs):
            data, meta = snap.blob(h)
            w.add(f"inventory/blobs/{h}", data, _blob_media_type(meta), "inventory_blob",
                  original_name=str(meta.get("name") or "")[:200], original_media_type=meta.get("media_type"),
                  stored_at=meta.get("created_at"))
        w.json("inventory/catalog_references.json", catalog_snapshot(rev_docs), "catalog_references")
        # ---- previsões (séries normalizadas e arquivos originais)
        for h in sorted(forecast_blobs):
            data, meta = snap.blob(h)
            w.add(f"forecasts/blobs/{h}", data, _blob_media_type(meta), "forecast_blob",
                  original_name=str(meta.get("name") or "")[:200], original_media_type=meta.get("media_type"),
                  stored_at=meta.get("created_at"))
        # ---- rodadas (todas, com o estado original)
        by_state: dict[str, int] = {}
        for r in runs:
            ru = r["run_uid"]
            by_state[r["state"]] = by_state.get(r["state"], 0) + 1
            idx = {}
            for d in snap.run_data_index(ru):
                if not FMT.RUN_DATA_NAME.fullmatch(d["name"]):
                    raise ExportError(f"Rodada {ru[:8]}…: nome de dado não exportável ({d['name']!r}); nada foi exportado.")
                raw = snap.run_data(ru, d["name"])
                mt = FMT.DATA_MEDIA_TYPES[os.path.splitext(d["name"])[1]]
                w.add(f"runs/{ru}/data/{d['name']}", raw, mt, "run_data", original_media_type=d["media_type"])
                idx[d["name"]] = {"sha256": d["sha256"], "size": int(d["size"]), "media_type": d["media_type"],
                                  "encoding_at_origin": d["encoding"]}
            row = {k: r[k] for k in ("run_uid", "request_id", "microgrid_uid", "incarnation", "scenario_uid",
                                     "scenario_version", "scenario_fingerprint", "config_revision", "config_fingerprint",
                                     "state", "owner", "created_at", "heartbeat_at", "finished_at")}
            row["progress"] = json.loads(r["progress"] or "{}")
            row["data"] = idx
            for n in ("outcome", "summary", "error"):
                row[f"has_{n}"] = r[n] is not None
            w.json(f"runs/{ru}/run.json", row, "run_json")
            w.text(f"runs/{ru}/manifest.json", r["manifest"], "run_json")
            for n in ("outcome", "summary", "error"):
                if r[n] is not None:
                    w.text(f"runs/{ru}/{n}.json", r[n], "run_json")
        # ---- manifesto (índice + dependências)
        mg_name = (cur.config.get("installation") or {}).get("name", "") if cur else ""
        dependencies = {
            "versions": {str(v["version"]): {"document": FMT.version_path(v["version"], True),
                                              "inventory_revision": FMT.revision_path(v["base_revision"], True),
                                              "forecasts": [f"forecasts/blobs/{h}" for h in sorted(
                                                  MicrogridStore._scenario_blobs(json.loads(v["document"])))]}
                         for v in versions},
            "inventory_revisions": {str(rev): {"document": FMT.revision_path(rev, True),
                                               "blobs": [f"inventory/blobs/{h}" for h in
                                                         sorted(MicrogridStore._referenced_blobs(rev_docs[rev]))]}
                                    for rev in sorted(revisions)},
            "runs": {r["run_uid"]: {"scenario_version": FMT.version_path(r["scenario_version"], True),
                                    "inventory_revision": FMT.revision_path(r["config_revision"], True),
                                    "files": sorted(p for p in w.resources if p.startswith(f"runs/{r['run_uid']}/"))}
                     for r in runs},
        }
        manifest = {
            "format": FMT.FORMAT, "format_version": FMT.FORMAT_VERSION, "created_at": C.utc_now(),
            "exporter": {"app": APP_NAME, "app_version": APP_VERSION, "db_schema_version": snap.db_version(),
                         "software": runner.software_versions()},
            "study": {
                "title": scn["name"],
                "origin": {"microgrid_uid": mg_uid, "microgrid_name": mg_name, "microgrid_incarnation": incarnation,
                           "scenario_uid": scn["scenario_uid"], "scenario_name": scn["name"],
                           "scenario_origin": scn["origin"], "scenario_created_at": scn["created_at"],
                           "scenario_updated_at": scn["updated_at"], "current_version": int(scn["version"])},
                "versions": [int(v["version"]) for v in versions],
                "inventory_revisions": sorted(revisions),
                "runs": [r["run_uid"] for r in runs],
                "counts": {"versions": len(versions), "runs": len(runs), "runs_by_state": by_state,
                           "inventory_revisions": len(revisions), "forecast_blobs": len(forecast_blobs),
                           "inventory_blobs": len(inv_blobs)},
            },
            "dependencies": dependencies,
            "resources": w.resources,
            "integrity": {"algorithm": "sha256", "note": FMT.INTEGRITY_NOTE},
        }
        info = zipfile.ZipInfo("manifest.json", date_time=_FIXED_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (0o100644 << 16)
        zf.writestr(info, json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8"))
    return manifest


def export_to_file(store: MicrogridStore, scenario_uid: str, dest: str | os.PathLike) -> ExportResult:
    """Escreve o pacote em ``dest`` (publicado atomicamente: arquivo temporário + rename; falha → nada em ``dest``)."""
    dest = Path(dest)
    tmp = dest.with_name(dest.name + ".part")
    try:
        with open(tmp, "wb") as fh:
            manifest = write_package(store, scenario_uid, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return ExportResult(dest, dest.name, dest.stat().st_size, FMT.package_digest(dest), FMT.content_id(manifest), manifest)


def export_bytes(store: MicrogridStore, scenario_uid: str) -> tuple[bytes, dict]:
    """Variante em memória (testes e estudos pequenos)."""
    import io

    buf = io.BytesIO()
    manifest = write_package(store, scenario_uid, buf)
    return buf.getvalue(), manifest


def export_dir() -> Path:
    """Diretório temporário das exportações preparadas pela interface (fora do armazenamento do SEEDS2)."""
    d = Path(tempfile.gettempdir()) / "seeds2_study_exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def prune_exports(max_age_s: float = 3600.0) -> None:
    import time

    now = time.time()
    for f in export_dir().glob("*" + FMT.SUFFIX):
        try:
            if now - f.stat().st_mtime > max_age_s:
                f.unlink()
        except OSError:
            pass


__all__ = ["ExportError", "ExportResult", "catalog_snapshot", "export_bytes", "export_dir", "export_to_file",
           "prune_exports", "write_package"]
