"""Ponte entre a configuração persistida da microrrede e o console V1.6 (Simulação / Resultados).

* Aplica ao orquestrador SOMENTE a configuração SALVA (nunca a edição pendente) via adaptador.
* Detecta quando o usuário altera a especificação nas páginas V1.6 (Modelos / Módulo de Carga): a origem
  passa a "manual" e os resultados deixam de ser atribuídos à microrrede.
* Controla a execução (``orq_run_gate``): bloqueios do adaptador e confirmação explícita de exclusões.
* Registra cada rodada no armazenamento local (``simulation_runs``) com revisão e impressões digitais.
* Identifica resultados obsoletos quando a configuração salva muda depois da rodada.

O console V1.6 continua sendo renderizado por ``orchestrator_app.render_orchestrator_app``, sem alterar
modelos, contrato de troca ou otimizador.
"""
from __future__ import annotations

import copy
import hashlib
from html import escape
from typing import Callable

import numpy as np
import streamlit as st

from seeds2.microgrid import adapter as A
from seeds2.microgrid import config as C
from seeds2.microgrid.references import KIND_LABELS

from . import forms, session, shell

SIM_PAGES = ("Visão Geral", "Módulo de Carga", "Modelos", "Otimizador")
RESULT_PAGES = ("Resultados do Otimizador", "Resultados dos Modelos", "Exportar Resultados")


def _state_hash() -> str:
    ss = st.session_state
    h = hashlib.sha256()
    h.update(C.canonical_json(ss.get("orq_model_spec")).encode())
    load = ss.get("orq_load")
    if load is not None:
        h.update(str(load.t0).encode())
        h.update(np.asarray(load.P_kW, dtype=float).tobytes())
        h.update(np.asarray(load.t_min, dtype=float).tobytes())
    clim = ss.get("orq_climate_raw")
    h.update(b"clim:" + (str(clim.shape).encode() + clim.to_csv().encode() if clim is not None else b"none"))
    return h.hexdigest()


def _apply(plan: A.SimulationPlan) -> None:
    """Transfere a configuração compatível ao estado do orquestrador V1.6."""
    ss = st.session_state
    store = session.store()
    ss["orq_model_spec"] = copy.deepcopy(plan.spec)
    if plan.load_descriptor:
        ss["orq_load"] = A.build_load(plan.load_descriptor, store.get_blob)
        ss["orq_load_mode"] = {"walkforward": "Walk-forward · embarcação (2 h)", "copel": "COPEL B1",
                               "csv": "CSV próprio"}[plan.load_descriptor["source"]]
    elif ss.get("orq_load") is None:
        # Mesma carga inicial do console V1.6; a rodada fica bloqueada pelo adaptador (demanda não definida).
        from ems_integration import ponte
        ss["orq_load"] = ponte.carga_walkforward("Ideal", "Normal", 12)
    ss["orq_climate_raw"] = A.build_climate_raw(plan.climate_descriptor, store.get_blob) if plan.climate_descriptor else None
    ss["orq_mg_applied"] = {"spec_fingerprint": plan.spec_fingerprint, "state_hash": _state_hash(),
                            "config_revision": plan.config_revision, "config_fingerprint": plan.config_fingerprint}
    ss.pop("orq_manual", None)


def _after_run_hook(plan: A.SimulationPlan | None) -> Callable[[dict], None]:
    def hook(item: dict) -> None:
        origin = item.get("origem") or {}
        r = item["resultado"]
        rel = r["rel"]
        summary = {"algoritmo": r.get("algoritmo"), "carga": r.get("carga_descricao"), "k_validos": int(r["k_validos"]),
                   "custo_total_rs": float(rel["custo_total_rs"]), "energia_nao_atendida_kWh": float(rel["energia_nao_atendida_kWh"]),
                   "energia_vertida_kWh": float(rel["energia_vertida_kWh"]), "fontes": list(r.get("nomes", []))}
        try:
            run_id = session.store().record_run(
                config_revision=origin.get("config_revision"), config_fingerprint=origin.get("config_fingerprint"),
                spec_fingerprint=origin.get("spec_fingerprint") or "manual", spec_origin=origin.get("origin", "manual"),
                excluded=origin.get("excluded", []), summary=summary)
            item.setdefault("origem", {})["run_id"] = run_id
        except Exception as exc:  # noqa: BLE001 — a rodada já ocorreu; registrar falha de rastreabilidade
            r.setdefault("avisos", []).append(f"Não foi possível registrar a rodada no armazenamento local: {exc}")
    return hook


def _sync_view_with_page(view: str) -> str:
    ss = st.session_state
    page = ss.get("orchestrator_page", "Visão Geral")
    last = ss.get("seeds_last_view")
    if view != last:                                   # navegação pela barra superior
        if view == "resultados" and page not in RESULT_PAGES:
            ss["orchestrator_page"] = "Resultados do Otimizador"
        elif view == "simulacao" and page not in SIM_PAGES:
            ss["orchestrator_page"] = "Otimizador"
    else:                                              # navegação interna do console V1.6
        group = "resultados" if page in RESULT_PAGES else "simulacao"
        if group != view:
            shell.go(group)
            view = group
    ss["seeds_last_view"] = view
    return view


def prepare(view: str) -> str:
    """Executa ANTES da barra superior: sincroniza a página V1.6 com a vista e aplica a configuração salva."""
    view = _sync_view_with_page(view)
    ss = st.session_state
    saved = session.saved()
    plan = A.build_plan(saved.config, revision=saved.revision, fingerprint=saved.fingerprint) if saved else None
    ss["mg_plan"] = plan
    applied = ss.get("orq_mg_applied") or {}
    if plan is not None and plan.spec_fingerprint != applied.get("spec_fingerprint"):
        try:
            _apply(plan)
        except Exception as exc:  # noqa: BLE001
            ss["mg_apply_error"] = f"Não foi possível transferir a configuração ao orquestrador: {exc}"
        else:
            ss.pop("mg_apply_error", None)
    applied = ss.get("orq_mg_applied") or {}
    manual = bool(applied) and _state_hash() != applied.get("state_hash")
    if manual:
        ss["orq_manual"] = True
    if plan is None or ss.get("orq_manual") or ss.get("mg_apply_error"):
        ss["orq_spec_origin"] = {"origin": "manual", "config_revision": None, "config_fingerprint": None,
                                 "spec_fingerprint": hashlib.sha256(_state_hash().encode()).hexdigest(), "excluded": []}
        ss["orq_run_gate"] = {"ok": True, "message": ""}
    else:
        ss["orq_spec_origin"] = plan.provenance()
        ack = ss.get("mg_ack_fp") == plan.spec_fingerprint
        if not plan.runnable:
            ss["orq_run_gate"] = {"ok": False, "message": "Simulação bloqueada: " + " ".join(plan.blockers)}
        elif plan.needs_ack and not ack:
            ss["orq_run_gate"] = {"ok": False, "message": f"{len(plan.excluded)} equipamento(s) instalado(s) não entram nesta "
                                  "rodada. Confirme a exclusão no painel 'Configuração aplicada' acima."}
        else:
            ss["orq_run_gate"] = {"ok": True, "message": ""}
    ss["orq_after_run"] = _after_run_hook(plan)
    return view


def _origin_text(o: dict | None) -> str:
    if not o:
        return "origem não registrada"
    if o.get("origin") == "microrrede":
        return f"microrrede · revisão {o.get('config_revision')} · {str(o.get('config_fingerprint') or '')[:12]}…"
    return "especificação manual do console V1.6 (não vinculada à microrrede)"


def panel(view: str) -> None:
    ss = st.session_state
    saved = session.saved()
    plan: A.SimulationPlan | None = ss.get("mg_plan")
    item = ss.get("orq_result_item")
    if item is not None:
        o = item.get("origem") or {}
        stale = o.get("origin") != "microrrede" or (saved is not None and o.get("config_fingerprint") != saved.fingerprint)
        if stale and o.get("origin") == "microrrede":
            shell.callout(f"<b>Resultado de configuração anterior.</b> A rodada #{item['id']} usou a {escape(_origin_text(o))}; "
                          f"a configuração salva atual é a revisão {saved.revision}. O resultado é mantido apenas para consulta e "
                          "não corresponde aos equipamentos atuais.", "bad")
        elif o.get("origin") != "microrrede" and view == "resultados":
            shell.callout(f"<b>Resultado da rodada #{item['id']}</b> — {escape(_origin_text(o))}.", "warn")
        elif view == "resultados":
            shell.callout(f"<b>Resultado da rodada #{item['id']}</b> — {escape(_origin_text(o))}"
                          f"{' · registro local nº ' + str(o['run_id']) if o.get('run_id') else ''}.", "ok")
    if view != "simulacao":
        return
    if ss.get("mg_apply_error"):
        shell.callout(escape(ss["mg_apply_error"]), "bad")
    if session.is_dirty():
        shell.callout("Há <b>edição pendente</b> em Gestão da Microrrede. A simulação usa somente a configuração "
                      f"<b>salva</b> (revisão {saved.revision if saved else '—'}).", "warn")
    if plan is None:
        return
    manual = bool(ss.get("orq_manual"))
    title = ("Especificação MANUAL no console V1.6" if manual else
             f"Configuração aplicada · revisão {plan.config_revision} · {str(plan.config_fingerprint)[:12]}…")
    with st.expander(title, expanded=manual or not plan.runnable or (plan.needs_ack and ss.get("mg_ack_fp") != plan.spec_fingerprint)):
        if manual:
            shell.callout("Os modelos ou a carga foram alterados nas páginas do console V1.6. As próximas rodadas serão "
                          "registradas como <b>manuais</b>, não como a microrrede configurada.", "warn")
            if st.button("Reaplicar a configuração salva da microrrede", key="ops_reapply", type="primary"):
                ss.pop("orq_mg_applied", None)
                ss.pop("orq_manual", None)
                st.rerun()
        rows = []
        for m in plan.mappings:
            tone = {A.REPRESENTED: "ok", A.DISABLED: "off", A.INCOMPLETE: "warn", A.INCOMPATIBLE: "bad"}[m.status]
            rows.append(shell.check(f"<b>{escape(m.name)}</b> ({escape(KIND_LABELS[m.kind])}) — {escape(A.STATUS_LABELS[m.status])}"
                                    f"{': ' + escape(m.reason) if m.reason else ''}", tone))
        for b in plan.blockers:
            rows.append(shell.check(f"<b>Bloqueio:</b> {escape(b)}", "bad"))
        for w in plan.warnings:
            rows.append(shell.check(escape(w), "warn"))
        st.html("".join(rows) or "<span class='sd-muted'>Nenhum equipamento registrado.</span>")
        if plan.runnable and plan.needs_ack and not manual:
            ack = st.checkbox(f"Confirmo executar esta rodada SEM os {len(plan.excluded)} equipamento(s) excluído(s) acima "
                              "(a exclusão fica registrada na rodada).", value=ss.get("mg_ack_fp") == plan.spec_fingerprint,
                              key=f"ops_ack_{plan.spec_fingerprint[:12]}")
            new = plan.spec_fingerprint if ack else None
            if new != ss.get("mg_ack_fp"):
                ss["mg_ack_fp"] = new
                st.rerun()
        c1, c2 = st.columns(2)
        if c1.button("Abrir Gestão da Microrrede", key="ops_manage", width="stretch"):
            shell.go("gestao", "inventario")
            st.rerun()
        c2.caption(f"Impressão digital da especificação: `{plan.spec_fingerprint[:16]}…`")


def render(view: str, legacy_css: Callable[[], None]) -> None:
    from orchestrator_app import render_orchestrator_app

    legacy_css()
    shell.callout_css()
    panel(view)
    render_orchestrator_app()
