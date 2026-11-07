"""Estado de sessão ↔ catálogo de microrredes ↔ armazenamento da microrrede ATIVA.

* **Microrrede ativa** — escolhida POR SESSÃO de navegador (``mg_active_uid``); nunca uma variável global do
  processo. Abrir/trocar de microrrede limpa TODO o estado da sessão (cópias de trabalho, diálogos,
  widgets, especificação/carga/resultados do console V1.6...), de modo que nada de uma microrrede reapareça
  em outra.
* **Configuração salva** — última revisão no SQLite da microrrede ativa (``saved()``), compartilhada por
  todas as sessões que a abrirem;
* **Edição pendente** — cópia de trabalho desta sessão (``work()``), ainda não gravada;
* **Configuração aplicada a uma simulação** — registrada pela ponte de operação (``operations``) com
  identidade da microrrede, revisão e impressão digital.

Uma microrrede NOVA existe apenas nesta sessão (``mg_creating``) até o primeiro salvamento (etapa 01 do
comissionamento), quando é registrada no catálogo com armazenamento próprio.
"""
from __future__ import annotations

import copy
from typing import Any

import streamlit as st

from seeds2.microgrid import config as C
from seeds2.microgrid.adapter import build_plan
from seeds2.microgrid.references import KIND_LABELS
from seeds2.microgrid.registry import MicrogridNotFound, MicrogridRegistry, valid_uid
from seeds2.microgrid.store import (ConflictError, MicrogridStore, MissingStoreError, Stored, StoreError,
                                    resolve_data_dir)

from .shell import fmt_time


ACTIVE_KEY = "mg_active_uid"
INCARNATION_KEY = "mg_active_inc"     # incarnação aberta nesta sessão (excluída + reimportada com o mesmo UID ≠ a mesma)
CREATING_KEY = "mg_creating"
# Chaves que sobrevivem à troca de microrrede: rota (redefinida em seguida) e o aviso a exibir no Gestor.
_KEEP_ON_SWITCH = ("seeds_route", "mg_flash")


@st.cache_resource(show_spinner=False)
def _registry_for(path: str) -> MicrogridRegistry:
    return MicrogridRegistry(path)


@st.cache_resource(show_spinner=False)
def _store_for(path: str, uid: str, incarnation: str | None) -> MicrogridStore:
    return MicrogridStore(path, must_exist=True, fixed_uid=uid, incarnation=incarnation)


def registry() -> MicrogridRegistry:
    return _registry_for(str(resolve_data_dir()))


@st.cache_resource(show_spinner=False)
def _archive_for(path: str):
    from seeds2.archive.store import ArchiveStore

    return ArchiveStore(path)


def archive():
    """Arquivo Científico da INSTALAÇÃO (Piso 2D-A): banco próprio, independente da microrrede ativa."""
    return _archive_for(str(resolve_data_dir()))


def _ss():
    return st.session_state


def active_uid() -> str | None:
    uid = _ss().get(ACTIVE_KEY)
    return uid if valid_uid(uid) else None


def creating() -> bool:
    return bool(_ss().get(CREATING_KEY)) and active_uid() is None


def store() -> MicrogridStore:
    """Armazenamento da microrrede ATIVA desta sessão (nunca cria uma microrrede)."""
    uid = active_uid()
    if uid is None:
        raise MicrogridNotFound("Nenhuma microrrede aberta nesta sessão.")
    reg = registry()
    entry = reg.get(uid)
    if entry is None:
        raise MicrogridNotFound("A microrrede não existe mais no catálogo (pode ter sido excluída em outra sessão).")
    ss = _ss()
    if ss.get(INCARNATION_KEY) is None:
        ss[INCARNATION_KEY] = entry.incarnation         # liga a sessão à incarnação aberta
    elif ss[INCARNATION_KEY] != entry.incarnation:
        raise MicrogridNotFound("A microrrede aberta foi excluída e substituída por outra com o mesmo identificador.")
    try:
        return _store_for(str(reg.dir_for(uid)), uid, entry.incarnation)
    except MissingStoreError:
        raise MicrogridNotFound("A microrrede não existe mais (excluída em outra sessão).") from None


def storage_label() -> str:
    uid = active_uid()
    return str(registry().dir_for(uid)) if uid else "será criado ao salvar a etapa 01"


def reset_state() -> None:
    """Limpa TODO o estado da sessão ligado a uma microrrede (inclusive o do console V1.6)."""
    ss = _ss()
    for k in list(ss.keys()):
        if k not in _KEEP_ON_SWITCH:
            del ss[k]


def open_microgrid(uid: str) -> bool:
    """Abre a microrrede ``uid`` NESTA sessão. Devolve se ela está comissionada (ativada)."""
    if not registry().exists(uid):
        raise MicrogridNotFound("A microrrede não existe mais no catálogo.")
    reset_state()
    _ss()[ACTIVE_KEY] = uid
    _ss()[INCARNATION_KEY] = registry().get(uid).incarnation if registry().get(uid) else None
    s = store().load()
    return bool(s and s.config.get("commissioning", {}).get("completed"))


def close_microgrid(flash: tuple[str, str] | None = None) -> None:
    """Volta ao Gestor: a sessão deixa de ter microrrede ativa (dados persistidos não são alterados)."""
    reset_state()
    if flash:
        _ss()["mg_flash"] = flash


def sync() -> Stored | None:
    """Relê a configuração salva e atualiza a cópia de trabalho quando não há edição pendente.
    Levanta ``MicrogridNotFound`` se a microrrede ativa foi excluída (por outra sessão)."""
    ss = _ss()
    if active_uid() is None:                           # Gestor, ou microrrede NOVA (só a cópia de trabalho da sessão)
        ss["mg_saved"] = None
        return None
    try:
        saved = store().load()
    except MissingStoreError:                          # lápide/incarnação: referência antiga invalidada
        raise MicrogridNotFound("A microrrede não existe mais (excluída em outra sessão).") from None
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
        if active_uid() is None:                       # primeiro salvamento de uma microrrede NOVA → catálogo
            res = registry().create(w, note=note or "Comissionamento: identificação e localização", origin=origin)
            ss[ACTIVE_KEY] = res.config["installation"]["uid"]
            ss[INCARNATION_KEY] = registry().get(ss[ACTIVE_KEY]).incarnation
            ss.pop(CREATING_KEY, None)
            st.query_params["mg"] = ss[ACTIVE_KEY]
        else:
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
    s = store().load() if active_uid() else None
    ss["mg_saved"] = s
    ss["mg_work"] = copy.deepcopy(s.config) if s else None
    ss["mg_base_rev"] = s.revision if s else 0
    ss["mg_base_fp"] = s.fingerprint if s else None
    ss.pop("mg_conflict", None)
    ss.pop("mg_error", None)
    ss.pop("mg_stale_base", None)


def begin_new(name: str = "") -> dict:
    """Inicia o comissionamento de uma microrrede NOVA nesta sessão (nada é gravado até a etapa 01)."""
    reset_state()
    _ss()[CREATING_KEY] = True
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
    path = storage_label()
    if s is None:
        return {"state": "novo", "text": "Nova microrrede · ainda não salva", "title": f"Armazenamento: {path}"}
    n = max(1, len(pending_changes())) if is_dirty() else 0
    if n:
        return {"state": "pendente", "text": f"Alterações pendentes ({n})",
                "title": f"Edição ainda não gravada. Última revisão salva: {s.revision}. Armazenamento: {path}"}
    if not s.config.get("commissioning", {}).get("completed"):
        return {"state": "comissionando", "text": f"Comissionamento salvo · rev. {s.revision}",
                "title": f"Progresso salvo localmente em {path}"}
    return {"state": "salvo", "text": f"Salvo · rev. {s.revision} · {fmt_time(s.saved_at)}",
            "title": f"Revisão {s.revision} · impressão digital {s.fingerprint[:12]}… · {path}"}
