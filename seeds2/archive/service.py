"""Operações compostas do Arquivo Científico (Piso 2D-A).

``archive_scenario``: guarda NESTA instalação um estudo de um cenário da microrrede ativa, exatamente como seria
exportado e importado (mesmo pacote, mesma verificação, mesma importação atômica), sem passar pelo navegador.
Ordem de bloqueios: a exportação lê UM instantâneo do banco da microrrede (L2, só leitura) e termina; só então a
importação escreve no banco do arquivo (L3). Nunca há bloqueios aninhados e nada da microrrede é alterado.

Preparado e NÃO implementado (decisão da missão): *CRIAR VARIANTE OPERATIVA* a partir de um estudo arquivado. O contrato
previsto: (1) escolher a versão do estudo; (2) verificar a compatibilidade com o inventário salvo da microrrede de
destino (deriva por equipamento, como ``scenarios.drift``) — nunca copiar sobre um cenário existente; (3) criar um
cenário NOVO (novo ``scenario_uid``) com ``lineage.archived_from = {archive_uid, origin_scenario_uid, version,
content_id}``, sem rodadas; (4) o estudo arquivado permanece intacto. Nenhuma reexecução automática.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import exporter
from .store import ArchiveStore, ImportResult


def archive_scenario(mg_store, archive: ArchiveStore, scenario_uid: str, *, context: dict | None = None,
                     on_duplicate: str = "recognize") -> ImportResult:
    with tempfile.TemporaryDirectory(prefix="seeds2_archive_") as tmp:
        dest = Path(tmp) / f"estudo{exporter.FMT.SUFFIX}"
        exporter.export_to_file(mg_store, scenario_uid, dest)
        return archive.import_package(dest, acquisition="arquivado", context=context, on_duplicate=on_duplicate)


__all__ = ["archive_scenario"]
