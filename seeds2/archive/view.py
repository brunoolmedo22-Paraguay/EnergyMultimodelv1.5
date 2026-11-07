"""Leitura de um estudo arquivado (Piso 2D-A) — consulta histórica, SEM recalcular.

``StudyView`` reconstrói, a partir SOMENTE dos recursos gravados no Arquivo Científico, a experiência de consulta do
experimento: cenário e todas as versões (documentos exatos), revisões do inventário de referência, previsões (séries
normalizadas e originais), rodadas (``StoredRun`` com manifesto, resultado, resumo, erro e índice de dados) e as séries
de cada rodada. Oferece ``run_data``/``get_run``/``get_blob`` com a mesma forma usada pelos gráficos do Piso 2C
(``run_charts``) e das previsões (``forecasts.load``), para que a interface reutilize os mesmos componentes.

Nada aqui importa ``orchestrator_runtime`` nem o EMS: não há como recalcular a partir desta camada.
"""
from __future__ import annotations

import io
import json
from functools import cached_property

import pandas as pd

from seeds2.microgrid.migrations import MigrationError, migrate_document
from seeds2.microgrid.store import StoredRun

from . import format as FMT
from .store import ArchivedStudy, ArchiveError, ArchiveStore


class StudyView:
    """Visão somente leitura de UM estudo arquivado. Os conteúdos são lidos sob demanda (SHA-256 conferido)."""

    def __init__(self, archive: ArchiveStore, archive_uid: str):
        self.archive = archive
        self.study: ArchivedStudy = archive.get_study(archive_uid)
        self.uid = self.study.archive_uid
        self.manifest = self.study.manifest
        self._cache: dict[str, object] = {}

    # ------------------------------------------------------------ recursos
    def raw(self, path: str) -> bytes:
        return self.archive.resource(self.uid, path)

    def json(self, path: str):
        if path not in self._cache:
            self._cache[path] = FMT.load_json(self.raw(path), path)
        return self._cache[path]

    @property
    def origin(self) -> dict:
        return (self.manifest.get("study") or {}).get("origin") or {}

    @cached_property
    def scenario(self) -> dict:
        return self.json("scenario/scenario.json")

    def version_numbers(self) -> list[int]:
        return sorted(int(v) for v in (self.manifest.get("study") or {}).get("versions") or [])

    def version_meta(self, v: int) -> dict:
        return self.json(FMT.version_path(v))

    def version_document(self, v: int) -> dict:
        return self.json(FMT.version_path(v, True))

    def revision_numbers(self) -> list[int]:
        return sorted(int(r) for r in (self.manifest.get("study") or {}).get("inventory_revisions") or [])

    def revision_meta(self, r: int) -> dict:
        return self.json(FMT.revision_path(r))

    def revision_document(self, r: int, *, migrated: bool = True) -> dict:
        """Documento da revisão do inventário. ``migrated``: forma atual para exibição (o texto original fica intacto
        no arquivo e é o que tem a impressão digital conferida)."""
        doc = self.json(FMT.revision_path(r, True))
        if not migrated:
            return doc
        try:
            out, _ = migrate_document(json.loads(json.dumps(doc)))
            return out
        except MigrationError:
            return doc

    def catalog_references(self) -> dict:
        try:
            return self.json("inventory/catalog_references.json")
        except ArchiveError:
            return {}

    def get_blob(self, digest: str) -> bytes:
        """Mesmo contrato de ``MicrogridStore.get_blob`` (usado por ``forecasts.load``): previsões ou inventário."""
        res = self.manifest.get("resources") or {}
        for path in (f"forecasts/blobs/{digest}", f"inventory/blobs/{digest}"):
            if path in res:
                return self.raw(path)
        raise ArchiveError(f"Dado {digest[:12]}… não está neste estudo.")

    def blob_meta(self, digest: str) -> dict:
        res = self.manifest.get("resources") or {}
        return dict(res.get(f"forecasts/blobs/{digest}") or res.get(f"inventory/blobs/{digest}") or {})

    # ------------------------------------------------------------ rodadas
    def run_uids(self) -> list[str]:
        return list((self.manifest.get("study") or {}).get("runs") or [])

    def get_run(self, run_uid: str) -> StoredRun:
        if run_uid not in self.run_uids():
            raise ArchiveError("Esta rodada não pertence ao estudo.")
        key = f"run:{run_uid}"
        if key not in self._cache:
            base = f"runs/{run_uid}/"
            row = self.json(base + "run.json")
            opt = {n: (self.json(f"{base}{n}.json") if row.get(f"has_{n}") else None) for n in ("outcome", "summary", "error")}
            data = {k: {"sha256": v["sha256"], "media_type": v["media_type"], "size": int(v["size"])}
                    for k, v in sorted((row.get("data") or {}).items())}
            self._cache[key] = StoredRun(
                row["run_uid"], row["request_id"], row["microgrid_uid"], row.get("incarnation"), row["scenario_uid"],
                int(row["scenario_version"]), row["scenario_fingerprint"], int(row["config_revision"]),
                row["config_fingerprint"], row["state"], row["owner"], row["created_at"], row["heartbeat_at"],
                row.get("finished_at"), row.get("progress") or {}, self.json(base + "manifest.json"), opt["outcome"],
                opt["summary"], opt["error"], data)
        return self._cache[key]

    def list_runs(self) -> list[StoredRun]:
        """Rodadas do estudo, mais recentes primeiro (mesma ordem do histórico do Piso 2C)."""
        return sorted((self.get_run(u) for u in self.run_uids()), key=lambda r: r.created_at, reverse=True)

    def run_data(self, run_uid: str, name: str) -> bytes:
        """Mesmo contrato de ``MicrogridStore.run_data`` (SHA-256 conferido contra o índice ORIGINAL da rodada)."""
        run = self.get_run(run_uid)
        if name not in run.data:
            raise ArchiveError(f"Dado '{name}' não encontrado na rodada.")
        raw = self.raw(f"runs/{run_uid}/data/{name}")
        from hashlib import sha256

        if sha256(raw).hexdigest() != run.data[name]["sha256"]:
            raise ArchiveError(f"Dado '{name}' da rodada corrompido (hash divergente do índice original).")
        return raw

    def run_csv(self, run_uid: str, name: str) -> pd.DataFrame:
        return pd.read_csv(io.BytesIO(self.run_data(run_uid, name)))


__all__ = ["StudyView"]
