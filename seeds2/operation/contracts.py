"""Contratos preparados para os próximos pisos — SEM implementá-los (Piso 2A).

Piso 2B — Previsões
    Cada cenário terá entradas de previsão em ``doc["forecasts"]``, uma por *slot* (``FORECAST_SLOTS``). Uma
    entrada é um ``ForecastInput``: tipo de origem (manual, CSV, sintético), procedência (mesmas categorias do
    Piso 1 — nunca "medido" para perfis de referência ou sintéticos), base temporal e, para dados tabulares, o
    SHA-256 do conteúdo armazenado na tabela ``blobs`` da PRÓPRIA microrrede (endereçamento por conteúdo, já
    usado pelo Piso 1). No Piso 2A o bloco existe vazio e qualquer entrada é validada estruturalmente; não há
    editores, gráficos nem novas fontes meteorológicas.

Piso 2C — Execução
    Entidades separadas: ``Scenario`` (editável, versionado em ``scenario_versions``) e ``Run`` (imutável depois
    de concluída). Uma execução deverá referenciar a versão IMUTÁVEL do cenário que a gerou (``RunReference``),
    além da microrrede/incarnação e da revisão do inventário. As séries completas do despacho serão gravadas com
    a execução (dívida técnica registrada no Piso 1). Nada disso existe ainda: não há runner novo e o otimizador
    não foi alterado.

Piso 2D — Arquivo científico
    O documento do cenário é JSON autossuficiente (esquema + versão, instantâneo das referências físicas,
    dados referenciados apenas por SHA-256), o que permite exportá-lo junto com execuções sem recalcular. Nenhum
    formato de exportação (PDF/Excel/ZIP) é implementado aqui.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from seeds2.microgrid import config as C

# ------------------------------------------------------------------ Piso 2B — previsões
FORECAST_SLOTS = {
    "demand": "Demanda elétrica",
    "climate": "Clima (irradiância, temperatura, vento)",
    "resources": "Recursos (hidrogênio, combustível)",
}
FORECAST_SOURCE_TYPES = {"manual": "Perfil manual", "csv": "CSV importado", "sintetico": "Perfil sintético",
                         "referencia": "Conjunto de referência do software"}
_HEX64 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class ForecastInput:
    """Entrada de previsão associada a um cenário (contrato do Piso 2B; ainda sem interface)."""
    slot: str
    source_type: str
    provenance: str                      # chave de ``config.PROVENANCE_KINDS``
    t0: str | None = None                # início ISO 8601 (com fuso) do horizonte
    step_s: int | None = None            # passo temporal
    horizon_s: int | None = None         # duração
    blob: str | None = None              # SHA-256 do conteúdo na tabela ``blobs`` da microrrede (CSV)
    params: dict | None = None           # parâmetros do gerador sintético / perfil manual
    notes: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def empty_forecasts() -> dict:
    return {}


def forecast_errors(forecasts: Any) -> list[str]:
    """Validação estrutural do bloco de previsões (aceita vazio; recusa slots/tipos desconhecidos)."""
    if not isinstance(forecasts, dict):
        return ["Bloco de previsões inválido."]
    errs: list[str] = []
    for slot, entry in forecasts.items():
        if slot not in FORECAST_SLOTS:
            errs.append(f"Previsão para slot desconhecido: {str(slot)[:40]!r}.")
            continue
        if not isinstance(entry, dict):
            errs.append(f"Previsão '{slot}' ilegível.")
            continue
        if entry.get("slot") != slot or entry.get("source_type") not in FORECAST_SOURCE_TYPES:
            errs.append(f"Previsão '{slot}' com slot ou tipo de origem inválido.")
        if entry.get("provenance") not in C.PROVENANCE_KINDS:
            errs.append(f"Previsão '{slot}' com procedência inválida.")
        if entry.get("source_type") in ("sintetico", "referencia") and entry.get("provenance") == "medido":
            errs.append(f"Previsão '{slot}': perfis sintéticos ou de referência não podem ser declarados medidos.")
        if entry.get("source_type") == "csv" and not _HEX64.fullmatch(str(entry.get("blob") or "")):
            errs.append(f"Previsão '{slot}' do tipo CSV sem conteúdo armazenado (SHA-256).")
        unknown = set(entry) - set(ForecastInput.__dataclass_fields__)
        if unknown:
            errs.append(f"Previsão '{slot}' com campos desconhecidos: {sorted(unknown)}.")
    return errs


# ------------------------------------------------------------------ Piso 2C — execução
@dataclass(frozen=True)
class RunReference:
    """Chave de procedência que toda execução (Run) do Piso 2C deverá gravar. ``scenario_version`` aponta para uma
    linha IMUTÁVEL de ``scenario_versions``; editar o cenário depois não altera execuções já concluídas."""
    microgrid_uid: str
    microgrid_incarnation: str | None
    scenario_uid: str
    scenario_version: int
    scenario_fingerprint: str
    config_revision: int
    config_fingerprint: str


def run_reference(stored_scenario: Any) -> RunReference:
    """Constrói a referência a partir de uma versão gravada (``store.StoredScenario``). Não executa nada."""
    doc = stored_scenario.document
    return RunReference(microgrid_uid=stored_scenario.microgrid_uid,
                        microgrid_incarnation=(doc.get("microgrid") or {}).get("incarnation"),
                        scenario_uid=stored_scenario.scenario_uid, scenario_version=stored_scenario.version,
                        scenario_fingerprint=stored_scenario.fingerprint,
                        config_revision=stored_scenario.base_revision, config_fingerprint=stored_scenario.base_fingerprint)


RUN_STATES = ("preparada", "em_execucao", "concluida", "falhou")     # concluída/falhou → imutável (Piso 2C)

__all__ = ["FORECAST_SLOTS", "FORECAST_SOURCE_TYPES", "ForecastInput", "RUN_STATES", "RunReference",
           "empty_forecasts", "forecast_errors", "run_reference"]
