"""Resumo da instalação física e bancadas V1.6 (conteúdo do antigo "Início", preservado no Centro de Operação).

Piso 2A: o "Início" da microrrede foi substituído pelo Centro de Operação (``operation_center``). Este módulo
mantém o resumo do inventário salvo, o esquema lógico do balanço, a prontidão do console V1.6, as últimas rodadas
registradas e o acesso às bancadas individuais — exibidos em seções secundárias do Centro de Operação.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from seeds2.microgrid import adapter as A
from seeds2.microgrid import config as C
from seeds2.microgrid.references import KIND_LABELS, KINDS

from . import forms, session, shell

BENCHES = [("solar", "Solar"), ("wind", "Eólica"), ("battery", "Bateria"), ("h2", "H₂ / PEMFC"), ("thermal", "Térmica")]


def installation_facts(saved) -> list[tuple[str, str]]:
    cfg = saved.config
    inst = cfg["installation"]
    return [("Natureza", C.NATURE_OPTIONS.get(inst.get("nature"), "não declarada")),
            ("Modo", C.OPERATION_MODE_OPTIONS.get(inst.get("operation_mode"), "não declarado")),
            ("Local", forms.location_text(inst.get("location"))), ("Fuso", (inst.get("location") or {}).get("timezone") or ""),
            ("Comissionada", shell.fmt_time(cfg["commissioning"].get("completed_at")))]


def identification_notice() -> None:
    """Pendências do Piso 1 que exigem ação na Gestão (edição pendente, identificação incompleta)."""
    saved = session.saved()
    cfg = saved.config
    if session.is_dirty():
        shell.callout("Há <b>edição pendente</b> em Gestão da Microrrede ainda não salva.", "warn")
    miss = C.identification_missing(cfg)
    if miss:
        c1, c2 = st.columns([4, 1.2], vertical_alignment="center")
        c1.warning("Identificação incompleta: " + shell.md(", ".join(miss)) + ". Complete-a em Gestão → Instalação "
                   "(o inventário existente é preservado).")
        if c2.button("Completar identificação", key="home_complete_ident", width="stretch"):
            shell.go("gestao", "instalacao")
            st.rerun()


def installation_summary() -> None:
    """Inventário salvo, balanço energético, prontidão do console V1.6 e últimas rodadas registradas."""
    saved = session.saved()
    cfg = saved.config
    plan = A.build_plan(cfg, revision=saved.revision, fingerprint=saved.fingerprint)
    by = {k: [e for e in cfg["equipment"] if e["kind"] == k] for k in KINDS}
    tiles = []
    for k in ("pv", "wind", "pemfc", "thermal"):
        if by[k]:
            p = sum(C.installed_power_kW(e) or 0 for e in by[k] if e.get("enabled", True))
            tiles.append((KIND_LABELS[k], forms.fmt(p, 1, "kW"), f"{len(by[k])} equipamento(s) · nominal habilitado"))
    if by["battery"]:
        e = sum(C.battery_energy_kWh(x) or 0 for x in by["battery"] if x.get("enabled", True))
        tiles.append(("Armazenamento", forms.fmt(e, 1, "kWh"), f"{len(by['battery'])} banco(s) · energia nominal"))
    rep, exc = len(plan.represented), len(plan.excluded)
    tiles.append(("Simulação", "pronta" if plan.runnable and not exc else ("com exclusões" if plan.runnable else "bloqueada"),
                  f"{rep} representado(s) · {exc} excluído(s)"))
    shell.kpis(tiles)
    st.write("")
    c1, c2 = st.columns([1.55, 1], gap="large")
    with c1:
        st.markdown('<div class="sd-section">Esquema lógico do balanço energético</div>', unsafe_allow_html=True)
        forms.balance_view(cfg, plan, key="home_bal")
    with c2:
        st.markdown('<div class="sd-section">Prontidão para o console V1.6 (Simulação)</div>', unsafe_allow_html=True)
        rows = []
        for m in plan.mappings:
            tone = {A.REPRESENTED: "ok", A.DISABLED: "off", A.INCOMPLETE: "warn", A.INCOMPATIBLE: "bad"}[m.status]
            rows.append(shell.check(f"<b>{escape(m.name)}</b> — {escape(A.STATUS_LABELS[m.status])}", tone))
        rows += [shell.check(escape(b), "bad") for b in plan.blockers]
        dem = cfg["demand"]
        rows.append(shell.check(f"Demanda: {escape(C.DEMAND_SOURCES[dem['source']])} ({escape(C.PROVENANCE_KINDS[dem['provenance']])})",
                                "ok" if plan.load_descriptor else "warn"))
        st.html("".join(rows))
        runs = session.store().runs(limit=3)
        st.markdown('<div class="sd-section">Últimas rodadas registradas</div>', unsafe_allow_html=True)
        if runs:
            for r in runs:
                cur = r["config_fingerprint"] == saved.fingerprint
                st.markdown(f"- #{r['run_id']} · {shell.fmt_time(r['created_at'])} · "
                            f"{'revisão ' + str(r['config_revision']) if r['spec_origin'] == 'microrrede' else 'manual'}"
                            f"{'' if cur else ' · *configuração anterior*'} · custo R$ {forms.fmt(r['summary'].get('custo_total_rs'), 2)}")
        else:
            st.caption("Nenhuma rodada registrada.")


def benches() -> None:
    """Bancadas individuais V1.6 (ferramentas de validação isolada)."""
    st.caption("Executam cada física de forma independente, sem usar nem alterar a configuração da microrrede.")
    cols = st.columns(len(BENCHES))
    for col, (key, label) in zip(cols, BENCHES):
        if col.button(f"ABRIR {label.upper()}", key=f"home_bench_{key}", width="stretch"):
            st.session_state["energy_source"] = key
            if key == "solar":
                st.session_state["current_page"] = "Visão geral"
            st.rerun()
