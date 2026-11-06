"""Operações completas sobre cenários da microrrede ATIVA (domínio + ``MicrogridStore``).

Toda gravação passa pelo ``MicrogridStore`` (transação da microrrede com verificação de lápide e incarnação —
H-01/H-02/H-03). A configuração física permanente NUNCA é gravada aqui: apenas as tabelas de cenários.
"""
from __future__ import annotations

from seeds2.microgrid.store import MicrogridStore, Stored, StoredScenario, StoreError

from . import scenarios as S


def _require_saved(store: MicrogridStore) -> Stored:
    saved = store.load()
    if saved is None:
        raise StoreError("A microrrede ainda não tem configuração salva.")
    if not saved.config.get("commissioning", {}).get("completed"):
        raise StoreError("Cenários operativos exigem uma microrrede comissionada (ativada).")
    return saved


def create(store: MicrogridStore, *, name: str, description: str = "") -> StoredScenario:
    """Novo cenário sobre a revisão SALVA atual do inventário (nunca sobre edição pendente)."""
    saved = _require_saved(store)
    doc = S.new_scenario(saved.config, saved.revision, saved.fingerprint, name=name, description=description,
                         incarnation=store.incarnation)
    S.check_for_save(doc)
    return store.create_scenario(doc, origin="new", note="Criação do cenário")


def duplicate(store: MicrogridStore, scenario_uid: str, *, name: str, description: str | None = None) -> StoredScenario:
    """Duplica a versão SALVA atual do cenário (edição pendente não é copiada) como cenário independente."""
    src = store.get_scenario(scenario_uid)
    doc = S.duplicate(src.document, src.version, name=name, description=description)
    S.check_for_save(doc)
    return store.create_scenario(doc, origin="duplicate",
                                 note=f"Duplicado de '{src.name}' (versão {src.version})")


def save(store: MicrogridStore, doc: dict, expected_version: int, *, note: str = "Edição do cenário") -> StoredScenario:
    """Grava nova versão. Erros estruturais/de coerência → ``ScenarioValidationError``; outra sessão gravou antes →
    ``ScenarioConflictError``. Em ambos os casos nada é gravado."""
    S.check_for_save(doc)
    return store.save_scenario(doc, expected_version, note=note, origin="edit")


def rebase(store: MicrogridStore, scenario_uid: str, expected_version: int) -> StoredScenario:
    """Atualiza explicitamente a referência do inventário do cenário para a revisão salva atual."""
    saved = _require_saved(store)
    cur = store.get_scenario(scenario_uid)
    doc, note = S.rebase(cur.document, saved.config, saved.revision, saved.fingerprint)
    if S.structural_errors(doc):
        raise S.ScenarioValidationError(S.structural_errors(doc))
    # Erros de coerência revelados pela nova referência NÃO impedem a atualização (ficam visíveis para correção):
    # bloquear aqui deixaria o cenário preso a um inventário que não existe mais.
    return store.save_scenario(doc, expected_version, note=note, origin="rebase")


__all__ = ["create", "duplicate", "rebase", "save"]
