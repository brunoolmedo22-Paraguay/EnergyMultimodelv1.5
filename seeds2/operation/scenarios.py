"""Documento do cenário operativo (esquema ``seeds2-scenario`` v1) e seu vínculo com o inventário.

Um cenário é um conjunto EDITÁVEL de condições experimentais de UMA microrrede. Regra central: o cenário NUNCA
modifica a configuração física permanente (o documento da microrrede e suas revisões). Ele apenas REFERENCIA a
revisão do inventário sobre a qual foi definido (``inventory_ref``) e guarda um instantâneo das características
físicas de referência de cada equipamento, o que permite:

* validar os estados iniciais sem reler a revisão (documento autossuficiente — portabilidade futura, Piso 2D);
* detectar mudanças posteriores do inventário (``drift``): equipamentos incluídos, retirados ou alterados;
* atualizar a referência de forma EXPLÍCITA (``rebase``), preservando estados de equipamentos retirados em
  ``initialization.orphaned`` (nada é descartado em silêncio).

Versões do cenário (``scenario_versions`` no banco da microrrede) são independentes das revisões do inventário.

Estrutura::

    {"schema": "seeds2-scenario", "schema_version": 1, "scenario_uid": <hex32>,
     "name": str, "description": str,
     "microgrid": {"uid": <hex32>, "incarnation": <str|None>},
     "inventory_ref": {"config_revision": int, "config_fingerprint": <sha256>, "inventory_fingerprint": <sha256>,
                       "equipment": {<eq_id>: {"kind", "name", "tag", "enabled", "fingerprint", ...referência física}}},
     "initialization": {"equipment": {<eq_id>: estado}, "orphaned": {<eq_id>: {...}}},
     "forecasts": {},          # Piso 2B — ver contracts.FORECAST_SLOTS
     "ems_strategy": None,     # Piso 2C — ainda não implementado
     "lineage": {"created_at": iso, "duplicated_from": None | {"scenario_uid", "version", "name"}}}
"""
from __future__ import annotations

import copy
import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from seeds2.microgrid import config as C

from . import contracts
from . import initialization as I

SCHEMA = "seeds2-scenario"
SCHEMA_VERSION = 1
NAME_MAX, DESCRIPTION_MAX = 120, 2000
_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
# Campos do equipamento que NÃO mudam a física de referência (rótulos/registro): não entram na impressão digital.
_COSMETIC = ("created_at", "updated_at", "notes", "name", "tag")


class ScenarioValidationError(ValueError):
    """Documento de cenário inválido ou com erros de coerência (mensagem apresentável)."""

    def __init__(self, messages: list[str]):
        super().__init__("; ".join(messages[:8]))
        self.messages = messages


# ------------------------------------------------------------------ impressões digitais do inventário
def equipment_fingerprint(eq: dict) -> str:
    phys = {k: v for k, v in eq.items() if k not in _COSMETIC}
    return hashlib.sha256(C.canonical_json(phys).encode("utf-8")).hexdigest()


def inventory_fingerprint(config: dict) -> str:
    """Impressão digital do inventário FÍSICO ativo (independe de descrição, demanda, localização...)."""
    eqs = {e["id"]: equipment_fingerprint(e) for e in config.get("equipment", [])}
    return hashlib.sha256(C.canonical_json(eqs).encode("utf-8")).hexdigest()


def inventory_reference(config: dict, revision: int, fingerprint: str) -> dict:
    """Referência à revisão salva do inventário + instantâneo das características físicas de cada equipamento."""
    equipment = {}
    for eq in config.get("equipment", []):
        ref = I.equipment_reference(eq)
        ref["fingerprint"] = equipment_fingerprint(eq)
        equipment[eq["id"]] = ref
    return {"config_revision": int(revision), "config_fingerprint": str(fingerprint),
            "inventory_fingerprint": inventory_fingerprint(config), "equipment": equipment}


# ------------------------------------------------------------------ construção
def new_scenario_uid() -> str:
    return uuid.uuid4().hex


def _clean_text(value: Any, limit: int) -> str:
    """Nome: espaços normalizados numa linha; descrição: apenas aparada. O limite é validado em
    ``structural_errors`` (nada é truncado em silêncio)."""
    text = str(value or "")
    return " ".join(text.split()) if limit == NAME_MAX else text.strip()


def new_scenario(config: dict, revision: int, fingerprint: str, *, name: str, description: str = "",
                 incarnation: str | None = None) -> dict:
    """Cenário NOVO sobre a revisão salva ``revision`` do inventário. Equipamentos habilitados recebem o estado
    padrão (disponível, demais campos não definidos); desabilitados não recebem estado."""
    ref = inventory_reference(config, revision, fingerprint)
    states = {eid: I.default_state(r["kind"]) for eid, r in ref["equipment"].items() if r["enabled"]}
    return {
        "schema": SCHEMA, "schema_version": SCHEMA_VERSION, "scenario_uid": new_scenario_uid(),
        "name": _clean_text(name, NAME_MAX), "description": _clean_text(description, DESCRIPTION_MAX),
        "microgrid": {"uid": config["installation"]["uid"], "incarnation": incarnation},
        "inventory_ref": ref,
        "initialization": {"equipment": states, "orphaned": {}},
        "forecasts": contracts.empty_forecasts(),
        "ems_strategy": None,
        "lineage": {"created_at": C.utc_now(), "duplicated_from": None},
    }


def duplicate(source: dict, source_version: int, *, name: str, description: str | None = None) -> dict:
    """Cópia INDEPENDENTE (novo identificador; mesma referência de inventário e mesmas condições)."""
    doc = copy.deepcopy(source)
    doc["scenario_uid"] = new_scenario_uid()
    doc["name"] = _clean_text(name, NAME_MAX)
    if description is not None:
        doc["description"] = _clean_text(description, DESCRIPTION_MAX)
    doc["lineage"] = {"created_at": C.utc_now(), "duplicated_from": {
        "scenario_uid": source["scenario_uid"], "version": int(source_version), "name": source.get("name", "")}}
    return doc


# ------------------------------------------------------------------ validação estrutural
def structural_errors(doc: Any) -> list[str]:
    if not isinstance(doc, dict):
        return ["O cenário não é um objeto."]
    errs: list[str] = []
    if doc.get("schema") != SCHEMA or doc.get("schema_version") != SCHEMA_VERSION:
        return ["Formato de cenário não reconhecido ou de versão incompatível."]
    if not (isinstance(doc.get("scenario_uid"), str) and _HEX32.fullmatch(doc["scenario_uid"])):
        errs.append("Identificador do cenário inválido.")
    name = doc.get("name")
    if not isinstance(name, str) or not name.strip():
        errs.append("O cenário precisa de um nome.")
    elif len(name) > NAME_MAX:
        errs.append(f"Nome do cenário com mais de {NAME_MAX} caracteres.")
    if not isinstance(doc.get("description", ""), str) or len(doc.get("description", "")) > DESCRIPTION_MAX:
        errs.append(f"Descrição inválida (até {DESCRIPTION_MAX} caracteres).")
    mg = doc.get("microgrid")
    if not isinstance(mg, dict) or not (isinstance(mg.get("uid"), str) and _HEX32.fullmatch(mg["uid"])):
        errs.append("Identidade da microrrede ausente ou inválida.")
    ref = doc.get("inventory_ref")
    if not isinstance(ref, dict):
        return errs + ["Referência ao inventário ausente."]
    rev = ref.get("config_revision")
    if not isinstance(rev, int) or isinstance(rev, bool) or rev < 1:
        errs.append("Revisão do inventário de referência inválida.")
    for k in ("config_fingerprint", "inventory_fingerprint"):
        if not (isinstance(ref.get(k), str) and _HEX64.fullmatch(ref[k])):
            errs.append(f"Referência ao inventário sem '{k}' válido.")
    eqs = ref.get("equipment")
    if not isinstance(eqs, dict) or any(not isinstance(v, dict) or v.get("kind") not in I.FIELDS for v in eqs.values()):
        errs.append("Instantâneo do inventário de referência inválido.")
    ini = doc.get("initialization")
    if not isinstance(ini, dict) or not isinstance(ini.get("equipment"), dict) or not isinstance(ini.get("orphaned", {}), dict):
        errs.append("Bloco de inicialização inválido.")
    errs += contracts.forecast_errors(doc.get("forecasts"))
    if doc.get("ems_strategy") is not None:
        errs.append("Estratégia EMS ainda não é suportada (Piso 2C); o campo deve permanecer vazio.")
    return errs


def findings(doc: dict) -> list[I.Finding]:
    """Constatações (erro / aviso / pendente / incompleto) dos estados iniciais contra a referência do cenário."""
    return I.validate(doc.get("initialization") or {}, (doc.get("inventory_ref") or {}).get("equipment") or {})


def check_for_save(doc: dict) -> list[I.Finding]:
    """Valida para gravação: erro estrutural ou de coerência → ``ScenarioValidationError`` (nada é gravado)."""
    errs = structural_errors(doc)
    if errs:
        raise ScenarioValidationError(errs)
    fs = findings(doc)
    bad = [f for f in fs if f.level == I.ERROR]
    if bad:
        raise ScenarioValidationError([f"{_eq_label(doc, f.eq_id)}: {f.message}" for f in bad])
    return fs


def _eq_label(doc: dict, eq_id: str | None) -> str:
    if eq_id is None:
        return "Cenário"
    ref = ((doc.get("inventory_ref") or {}).get("equipment") or {}).get(eq_id) or {}
    return ref.get("name") or eq_id


# ------------------------------------------------------------------ deriva do inventário
@dataclass
class Drift:
    base_revision: int
    current_revision: int
    same_revision: bool
    inventory_changed: bool
    added: list[str] = field(default_factory=list)       # ids presentes no inventário atual e não na referência
    removed: list[str] = field(default_factory=list)     # ids da referência que não estão mais no inventário
    changed: list[str] = field(default_factory=list)     # ids cujas características físicas mudaram

    @property
    def stale(self) -> bool:
        return self.inventory_changed

    def describe(self, doc: dict, current_config: dict) -> list[str]:
        names_cur = {e["id"]: e["name"] for e in current_config.get("equipment", [])}
        out = [f"Incluído: {names_cur.get(i, i)}" for i in self.added]
        out += [f"Retirado: {_eq_label(doc, i)}" for i in self.removed]
        out += [f"Alterado: {names_cur.get(i, i)}" for i in self.changed]
        return out


def drift(doc: dict, current_config: dict, current_revision: int) -> Drift:
    ref = doc["inventory_ref"]
    old = {k: v.get("fingerprint") for k, v in ref["equipment"].items()}
    new = {e["id"]: equipment_fingerprint(e) for e in current_config.get("equipment", [])}
    return Drift(base_revision=int(ref["config_revision"]), current_revision=int(current_revision),
                 same_revision=int(ref["config_revision"]) == int(current_revision),
                 inventory_changed=ref["inventory_fingerprint"] != inventory_fingerprint(current_config),
                 added=[i for i in new if i not in old], removed=[i for i in old if i not in new],
                 changed=[i for i in new if i in old and new[i] != old[i]])


def rebase(doc: dict, current_config: dict, revision: int, fingerprint: str) -> tuple[dict, str]:
    """Atualiza EXPLICITAMENTE a referência do cenário para a revisão salva atual do inventário.

    * estados de equipamentos que continuam no inventário (mesmo tipo) são mantidos e revalidados contra a nova
      referência (p. ex. menos sistemas PEMFC instalados → erro de coerência visível);
    * estados de equipamentos retirados vão para ``initialization.orphaned`` (preservados, não aplicados);
    * equipamentos novos e habilitados recebem o estado padrão (disponível; demais campos não definidos)."""
    d = drift(doc, current_config, revision)
    new = copy.deepcopy(doc)
    ref = inventory_reference(current_config, revision, fingerprint)
    states = new["initialization"]["equipment"]
    orphaned = new["initialization"].setdefault("orphaned", {})
    for eq_id in list(states):
        r = ref["equipment"].get(eq_id)
        if r is None or r["kind"] != doc["inventory_ref"]["equipment"].get(eq_id, {}).get("kind"):
            orphaned[eq_id] = {"state": states.pop(eq_id), "reference": doc["inventory_ref"]["equipment"].get(eq_id),
                               "orphaned_at_revision": int(revision)}
    for eq_id, r in ref["equipment"].items():
        if r["enabled"] and eq_id not in states:
            states[eq_id] = I.default_state(r["kind"])
    new["inventory_ref"] = ref
    note = (f"Referência do inventário atualizada: revisão {d.base_revision} → {revision} "
            f"(+{len(d.added)} incluído(s), −{len(d.removed)} retirado(s), ~{len(d.changed)} alterado(s)).")
    return new, note


# ------------------------------------------------------------------ prontidão
STAGES = (
    ("inicializacao", "Inicialização", "Estados iniciais dos equipamentos"),
    ("previsoes", "Previsões", "Demanda, clima e recursos — Piso 2B"),
    ("estrategia", "Estratégia EMS", "Escolha e parâmetros da estratégia — piso dedicado ao otimizador"),
    ("execucao", "Execução", "Rodada EMS do cenário e arquivo de resultados — Piso 2C"),
)


def readiness(doc: dict, fs: list[I.Finding], d: Drift | None) -> dict:
    """Estado de preparação do cenário. Somente a Inicialização está disponível no Piso 2A; as demais etapas são
    declaradas como NÃO implementadas (nunca simuladas como prontas)."""
    s = I.summarize(fs)
    if s[I.ERROR]:
        init = ("bad", "Com erros de coerência", f"{s[I.ERROR]} erro(s) a corrigir")
    elif d is not None and d.stale:
        init = ("warn", "Inventário mudou", "Revise e atualize a referência do inventário")
    elif s[I.INCOMPLETE]:
        init = ("warn", "Incompleta", f"{s[I.INCOMPLETE]} item(ns) não definido(s)")
    else:
        extra = ", ".join(x for x in (f"{s[I.WARNING]} aviso(s)" if s[I.WARNING] else "",
                                      f"{s[I.PENDING]} pendência(s) do EMS" if s[I.PENDING] else "") if x)
        init = ("ok", "Definida", extra or "sem avisos")
    stages = {"inicializacao": init,
              "previsoes": ("off", "Não implementado", "Piso 2B"),
              "estrategia": ("off", "Não implementado", "Piso dedicado ao otimizador"),
              "execucao": ("off", "Não implementado", "Piso 2C")}
    return {"stages": stages, "counts": s, "executable": False,
            "summary": "Inicialização " + init[1].lower() + " · Previsões, Estratégia EMS e Execução ainda não "
                       "implementadas (o cenário ainda não é executável)."}


__all__ = ["Drift", "SCHEMA", "SCHEMA_VERSION", "STAGES", "ScenarioValidationError", "check_for_save", "drift", "duplicate",
           "equipment_fingerprint", "findings", "inventory_fingerprint", "inventory_reference", "new_scenario",
           "readiness", "rebase", "structural_errors"]
