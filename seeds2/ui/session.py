"""Estado de sessão ↔ armazenamento local.

Três estados distintos (requisito do Piso 1):

* **configuração salva** — última revisão no SQLite (``saved()``), compartilhada por todas as sessões;
* **edição pendente** — cópia de trabalho desta sessão (``work()``), ainda não gravada;
* **configuração aplicada a uma simulação** — registrada pela ponte de operação (``operations``) com
  revisão e impressão digital.

A configuração salva é relida a cada execução (leitura SQLite barata), de modo que alterações feitas
por outra sessão aparecem; se houver edição pendente, o salvamento posterior detecta o conflito.
"""
from __future__ import annotations

import copy
from typing import Any

import streamlit as st

from seeds2.microgrid import config as C
from seeds2.microgrid.adapter import build_plan
from seeds2.microgrid.references import KIND_LABELS
from seeds2.microgrid.store import ConflictError, MicrogridStore, Stored, StoreError, resolve_data_dir

from .shell import fmt_time


@st.cache_resource(show_spinner=False)
def _store_for(path: str) -> MicrogridStore:
    return MicrogridStore(path)


def store() -> MicrogridStore:
    return _store_for(str(resolve_data_dir()))


def _ss():
    return st.session_state


def sync() -> Stored | None:
    """Relê a configuração salva e atualiza a cópia de trabalho quando não há edição pendente."""
    saved = store().load()
    ss = _ss()
    ss["mg_saved"] = saved
    base_rev = int(ss.get("mg_base_rev") or 0)
    if saved is None:
        if base_rev:                                   # havia revisão base e o banco foi trocado/limpo externamente
            ss["mg_work"] = None
        ss["mg_base_rev"], ss["mg_base_fp"] = 0, None
        return None
    adopt = ss.get("mg_work") is None or (saved.revision != base_rev and not is_dirty())
    if adopt:
        if ss.get("mg_work") is not None and base_rev:
            ss["mg_notice"] = f"Configuração atualizada para a revisão {saved.revision} (salva em outra sessão)."
        ss["mg_work"] = copy.deepcopy(saved.config)
        ss["mg_base_rev"], ss["mg_base_fp"] = saved.revision, saved.fingerprint
    elif saved.revision != base_rev:
        ss["mg_stale_base"] = saved.revision           # edição pendente sobre base antiga: salvar acusará conflito
    return saved


def saved() -> Stored | None:
    return _ss().get("mg_saved")


def work() -> dict | None:
    return _ss().get("mg_work")


def set_work(cfg: dict | None) -> None:
    _ss()["mg_work"] = cfg


def is_dirty() -> bool:
    """Há edição desta sessão ainda não gravada (cópia de trabalho ≠ revisão base)?"""
    w = work()
    if w is None:
        return False
    return C.fingerprint(w) != _ss().get("mg_base_fp")


def save(note: str = "", origin: str = "edit") -> bool:
    ss = _ss()
    w = work()
    if w is None:
        return False
    try:
        res = store().save(w, int(ss.get("mg_base_rev") or 0), note=note, origin=origin)
    except ConflictError as exc:
        ss["mg_conflict"] = str(exc)
        return False
    except StoreError as exc:
        ss["mg_error"] = str(exc)
        return False
    ss["mg_saved"] = res
    ss["mg_work"] = copy.deepcopy(res.config)
    ss["mg_base_rev"] = res.revision
    ss["mg_base_fp"] = res.fingerprint
    ss.pop("mg_conflict", None)
    ss.pop("mg_error", None)
    ss.pop("mg_stale_base", None)
    return True


def discard() -> None:
    ss = _ss()
    s = store().load()
    ss["mg_saved"] = s
    ss["mg_work"] = copy.deepcopy(s.config) if s else None
    ss["mg_base_rev"] = s.revision if s else 0
    ss["mg_base_fp"] = s.fingerprint if s else None
    ss.pop("mg_conflict", None)
    ss.pop("mg_error", None)
    ss.pop("mg_stale_base", None)


def begin_new(name: str) -> dict:
    cfg = C.new_config(name)
    set_work(cfg)
    return cfg


def plan(cfg: dict | None = None):
    cfg = cfg if cfg is not None else work()
    s = saved()
    if cfg is None:
        return None
    is_saved = s is not None and C.fingerprint(cfg) == s.fingerprint
    return build_plan(cfg, revision=s.revision if is_saved else None, fingerprint=s.fingerprint if is_saved else None)


# ------------------------------------------------------------------ diferenças (edição pendente)
def changes(old: dict | None, new: dict | None) -> list[str]:
    if new is None:
        return []
    if old is None:
        return ["Nova configuração ainda não salva."]
    out: list[str] = []
    labels = {"name": "nome", "description": "descrição", "location": "localização", "nature": "natureza",
              "operation_mode": "modo operativo"}
    for k, lab in labels.items():
        if old["installation"].get(k) != new["installation"].get(k):
            out.append(f"Instalação: {lab}")
    oe = {e["id"]: e for e in old.get("equipment", [])}
    ne = {e["id"]: e for e in new.get("equipment", [])}
    for i in ne.keys() - oe.keys():
        out.append(f"Adicionado: {ne[i]['name']} ({KIND_LABELS[ne[i]['kind']]})")
    for i in oe.keys() - ne.keys():
        out.append(f"Retirado: {oe[i]['name']} ({KIND_LABELS[oe[i]['kind']]})")
    for i in ne.keys() & oe.keys():
        a, b = oe[i], ne[i]
        fields = [k for k in ("name", "tag", "serial", "enabled", "notes", "imported") if a.get(k) != b.get(k)]
        fields += [k for k in b["params"] if a["params"].get(k) != b["params"].get(k)]
        if a.get("arrays") != b.get("arrays"):
            fields.append("arranjos")
        if fields:
            out.append(f"Alterado: {b['name']} ({', '.join(fields)})")
    for section, lab in (("energy_balance", "Balanço energético (conexão com a rede)"), ("demand", "Demanda e dados"),
                         ("climate", "Clima"), ("run_conditions", "Condições da rodada"), ("commissioning", "Comissionamento")):
        if old.get(section) != new.get(section):
            out.append(lab)
    return out


def pending_changes() -> list[str]:
    s = saved()
    return changes(s.config if s else None, work())


# ------------------------------------------------------------------ indicador de salvamento
def save_status() -> dict[str, Any]:
    ss = _ss()
    s = saved()
    if ss.get("mg_conflict"):
        return {"state": "conflito", "text": "Conflito de salvamento", "title": ss["mg_conflict"]}
    if ss.get("mg_error"):
        return {"state": "erro", "text": "Erro ao salvar", "title": ss["mg_error"]}
    path = str(store().path)
    if s is None:
        return {"state": "novo", "text": "Nenhuma configuração salva", "title": f"Armazenamento local: {path}"}
    n = max(1, len(pending_changes())) if is_dirty() else 0
    if n:
        return {"state": "pendente", "text": f"Alterações pendentes ({n})",
                "title": f"Edição ainda não gravada. Última revisão salva: {s.revision}. Armazenamento: {path}"}
    if not s.config.get("commissioning", {}).get("completed"):
        return {"state": "comissionando", "text": f"Comissionamento salvo · rev. {s.revision}",
                "title": f"Progresso salvo localmente em {path}"}
    return {"state": "salvo", "text": f"Salvo · rev. {s.revision} · {fmt_time(s.saved_at)}",
            "title": f"Revisão {s.revision} · impressão digital {s.fingerprint[:12]}… · {path}"}
