"""Contratos entre os pisos do Centro de Operação (preparados no Piso 2A; Previsões implementadas no Piso 2B).

Piso 2B — Previsões (IMPLEMENTADO — ``seeds2/operation/forecasts.py`` e ``forecast_sources.py``)
    Cada cenário tem entradas de previsão em ``doc["forecasts"]``, uma por *slot* editável (``demand``,
    ``climate``). Uma entrada é um ``ForecastInput`` (formato ``format_version`` 1): tipo de origem (manual, CSV,
    sintético, referência), procedência (mesmas categorias do Piso 1 — nunca "medido" para perfis de referência
    ou sintéticos), base temporal ORIGINAL (``t0``/``t_end``/``step_s``/``n_points``/``regular``, fuso declarado ou
    identificado como não declarado), variáveis em unidades canônicas e o SHA-256 da série normalizada
    (``data``) e, para CSV, do arquivo original (``blob``), ambos na tabela ``blobs`` da PRÓPRIA microrrede,
    gravados na MESMA transação da versão do cenário. O slot ``resources`` (hidrogênio/combustível) continua
    reservado: nenhum contrato científico o consome ainda, e ele não é editável.

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
    """Entrada de previsão associada a um cenário (contrato do Piso 2B).

    Os nove primeiros campos são os do contrato preliminar do Piso 2A (inalterados); os demais foram acrescentados
    no Piso 2B, todos opcionais na validação ESTRUTURAL (``forecast_errors``). A completude exigida para GRAVAR
    uma entrada (série armazenada, sem erros, procedência reprodutível) é verificada por
    ``seeds2.operation.forecasts.entry_errors`` em ``scenarios.check_for_save``."""
    slot: str
    source_type: str
    provenance: str                      # chave de ``config.PROVENANCE_KINDS``
    t0: str | None = None                # primeiro instante ISO 8601 (relógio de parede do fuso ``timezone``)
    step_s: float | None = None          # passo típico (mediana) da série original, em segundos
    horizon_s: float | None = None       # duração coberta pela série original (t_end − t0), em segundos
    blob: str | None = None              # SHA-256 do arquivo ORIGINAL (CSV) na tabela ``blobs`` da microrrede
    params: dict | None = None           # origem: gerador+versão+semente / conjunto de referência / arquivo / tabela
    notes: str = ""
    # ---- Piso 2B
    format_version: int | None = None    # versão do formato da entrada (1)
    label: str = ""                      # descrição legível da origem
    variables: list | None = None        # variáveis canônicas presentes (``forecasts.VARIABLES``)
    t_end: str | None = None             # último instante
    n_points: int | None = None          # observações na série original normalizada
    regular: bool | None = None          # passo constante?
    timezone: str | None = None          # IANA, "UTC" ou "UTC±hh:mm"; None = NÃO DECLARADO (explícito)
    timezone_source: str | None = None   # arquivo | arquivo_utc | usuario | nao_declarado
    data: str | None = None              # SHA-256 da série NORMALIZADA canônica (``forecasts.to_csv_bytes``)
    mapping: dict | None = None          # CSV: mapeamento aplicado (colunas, unidades, tempo, fuso, duplicatas)
    transforms: list | None = None       # transformações aplicadas (registradas; dados originais preservados)
    quality: dict | None = None          # contagem de constatações {erro, aviso, pendente, incompleto}
    stats: dict | None = None            # mín./máx./média/ausentes por variável (+ energia estimada da demanda)
    created_at: str | None = None

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
        for k in ("data", "blob"):
            v = entry.get(k)
            if v is not None and not _HEX64.fullmatch(str(v)):
                errs.append(f"Previsão '{slot}' com referência '{k}' inválida (SHA-256).")
        for k, typ in (("params", dict), ("mapping", dict), ("variables", list), ("transforms", list),
                       ("quality", dict), ("stats", dict)):
            if entry.get(k) is not None and not isinstance(entry[k], typ):
                errs.append(f"Previsão '{slot}': campo '{k}' com tipo inválido.")
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
