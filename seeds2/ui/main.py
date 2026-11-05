"""Ponto de entrada do shell SEEDS2 (chamado por ``app.py`` quando nenhuma bancada individual está aberta).

Fluxo: Gestor de microrredes → (abrir | nova microrrede → Comissionamento → Ativação) → ambiente da microrrede.
A microrrede ativa é escolhida por sessão de navegador; "TROCAR MICRORREDE" volta ao Gestor.
"""
from __future__ import annotations

from typing import Callable

import streamlit as st

from seeds2.microgrid.registry import MicrogridNotFound, valid_uid
from seeds2.microgrid.store import StoreError

from . import commissioning, gestor, home, management, operations, scope, session, shell


def _restore_from_url() -> None:
    """Nova sessão (recarga da página) com ``?mg=<uid>``: reabre a microrrede DESTA aba, se ainda existir."""
    ss = st.session_state
    if "seeds_url_checked" in ss:
        return
    ss["seeds_url_checked"] = True
    uid = st.query_params.get("mg")
    if session.active_uid() is None and valid_uid(uid) and session.registry().exists(uid):
        view = shell.route()["view"]
        session.open_microgrid(uid)
        st.session_state["seeds_url_checked"] = True
        shell.route()["view"] = view


def render(legacy_css: Callable[[], None]) -> None:
    ss = st.session_state
    try:
        session.registry()
    except StoreError as exc:
        shell.global_css()
        st.error(f"Armazenamento do SEEDS2 indisponível: {shell.md(exc)}")
        st.stop()
    if ss.pop(shell.SWITCH_KEY, False):                 # TROCAR MICRORREDE (barra superior)
        session.close_microgrid()
        shell.go("gestor")
    _restore_from_url()
    try:
        saved = session.sync()
    except MicrogridNotFound:
        session.close_microgrid(("warn", "A microrrede que estava aberta nesta sessão foi excluída (em outra sessão) "
                                          "ou não está mais disponível. Nenhum dado foi recriado."))
        shell.go("gestor")
        st.rerun()
    except StoreError as exc:
        shell.global_css()
        st.error(f"Armazenamento da microrrede indisponível: {shell.md(exc)}")
        if st.button("Voltar ao Gestor de microrredes", key="mg_err_back"):
            session.close_microgrid()
            shell.go("gestor")
            st.rerun()
        st.stop()
    uid = session.active_uid()
    is_open = uid is not None or session.creating()
    commissioned = bool(saved and saved.config.get("commissioning", {}).get("completed"))
    r = shell.route()
    view = r["view"]
    if not is_open:
        if view not in ("gestor", "alcance"):
            view = "gestor"
    elif not commissioned and view not in ("comissionamento", "alcance"):
        view = "comissionamento"
    elif commissioned and view in ("comissionamento", "gestor"):
        view = "inicio"
    if view != r["view"] or (uid and st.query_params.get("mg") != uid):
        shell.go(view, r.get("tab") if view == r["view"] else None)
    legacy = view in ("simulacao", "resultados")
    if legacy:
        view = operations.prepare(view)
    else:
        shell.global_css()
        ss["seeds_last_view"] = view
    inst = (saved.config["installation"] if saved else (session.work() or {}).get("installation")) or {}
    site = inst.get("name") or ""
    if not is_open:
        items, label, home_view = shell.NAV_GESTOR, "", "gestor"
    elif commissioned:
        items, label, home_view = shell.NAV_ACTIVE, site, "inicio"
    else:
        items, home_view = shell.NAV_COMMISSIONING, "comissionamento"
        label = f"Comissionamento · {site}" if site else "Nova microrrede · comissionamento"
    shell.topbar(view=view, items=items, site=label, site_title=f"Microrrede {inst.get('uid', '')}" if is_open else "",
                 save=session.save_status() if is_open else {"state": "novo", "text": ""}, force_light=legacy,
                 home=home_view, switch=is_open)
    if view == "gestor":
        gestor.render()
    elif view == "comissionamento":
        commissioning.render()
    elif view == "alcance":
        scope.render()
    elif view == "gestao":
        management.render()
    elif legacy:
        operations.render(view, legacy_css)
    else:
        home.render()
