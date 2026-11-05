"""Ponto de entrada do shell SEEDS2 (chamado por ``app.py`` quando nenhuma bancada individual está aberta)."""
from __future__ import annotations

from typing import Callable

import streamlit as st

from seeds2.microgrid.store import StoreError

from . import commissioning, home, management, operations, scope, session, shell


def render(legacy_css: Callable[[], None]) -> None:
    try:
        saved = session.sync()
    except StoreError as exc:
        shell.global_css()
        st.error(f"Armazenamento local indisponível: {exc}")
        st.stop()
    commissioned = bool(saved and saved.config.get("commissioning", {}).get("completed"))
    r = shell.route()
    view = r["view"]
    if not commissioned and view not in ("comissionamento", "alcance"):
        view = "comissionamento"
    if commissioned and view == "comissionamento":
        view = "inicio"
    if view != r["view"]:
        shell.go(view)
    legacy = view in ("simulacao", "resultados")
    if legacy:
        view = operations.prepare(view)
    else:
        shell.global_css()
        st.session_state["seeds_last_view"] = view
    inst = saved.config["installation"] if saved else {}
    site = inst.get("name") or ""
    shell.topbar(view=view, items=shell.NAV_ACTIVE if commissioned else shell.NAV_COMMISSIONING,
                 site=site if commissioned else (f"Comissionamento · {site}" if site else ""),
                 site_title=f"Instalação {inst.get('uid', '')}" if inst else "", save=session.save_status(),
                 force_light=legacy, home="inicio" if commissioned else "comissionamento")
    if view == "comissionamento":
        commissioning.render()
    elif view == "alcance":
        scope.render()
    elif view == "gestao":
        management.render()
    elif legacy:
        operations.render(view, legacy_css)
    else:
        home.render()
