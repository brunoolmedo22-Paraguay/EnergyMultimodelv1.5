"""Comissionamento (primeira configuração) da ÚNICA microrrede administrada por esta instalação do SEEDS2.

O progresso é salvo no armazenamento local a cada etapa (revisões com origem ``commissioning``):
fechar o navegador ou reiniciar o servidor não perde o que foi registrado, e é possível voltar a
etapas anteriores. Só a etapa 01 (nome) é obrigatória para salvar; o restante pode ficar pendente,
com indicação explícita do que falta para simular.
"""
from __future__ import annotations

import streamlit as st

from seeds2.microgrid import config as C
from seeds2.microgrid.references import KIND_LABELS, KINDS

from . import forms, session, shell

STEPS = [(1, "Identificação"), (2, "Inventário energético"), (3, "Configuração elétrica"),
         (4, "Parâmetros operacionais"), (5, "Revisão e ativação")]
STEP_KEY = "mg_cstep"


def _states(cfg: dict | None, plan, saved_exists: bool, current: int) -> list[dict]:
    out = []
    for n, title in STEPS:
        state, reason = "pendente", ""
        if not saved_exists and n > 1:
            state, reason = "bloqueada", "salve a identificação primeiro"
        elif cfg is not None:
            if n == 1:
                state = "completa" if cfg["installation"].get("name") and saved_exists else "progresso"
            elif n == 2:
                k = len(cfg["equipment"])
                state, reason = ("completa", f"{k} equipamento(s)") if k else ("atencao", "nenhum equipamento")
            elif n == 3:
                t = cfg["topology"]
                ok = t["bus_kind"] != "nao_declarado" and t["grid_connection"] != "nao_declarada"
                state, reason = ("completa", "") if ok else ("atencao", "barramento ou conexão não declarados")
            elif n == 4:
                inc = [e for e in cfg["equipment"] if e.get("enabled", True) and not C.is_configured(e)]
                dem = bool(plan and plan.load_descriptor)
                if not inc and dem:
                    state = "completa"
                else:
                    state = "atencao"
                    reason = " · ".join(([f"{len(inc)} equipamento(s) incompleto(s)"] if inc else []) + ([] if dem else ["demanda não definida"]))
            elif n == 5:
                state = "progresso" if current == 5 else "pendente"
        if n == current and state == "pendente":
            state = "progresso"
        out.append({"n": n, "title": title, "state": state, "reason": reason})
    return out


def _goto(step: int) -> None:
    st.session_state[STEP_KEY] = step
    cfg = session.work()
    if cfg is not None and session.saved() is not None:
        cfg["commissioning"]["step"] = step
        session.save(note=f"Comissionamento: etapa {step:02d}", origin="commissioning")
    forms.bump()


def _on_stepper() -> None:
    a = shell.payload("seeds_stepper")
    if a and a.get("type") == "goto" and session.saved() is not None:
        _goto(int(a["step"]))


def _nav(step: int, *, next_label: str = "Continuar →", next_disabled: bool = False) -> None:
    st.write("")
    c1, _, c3 = st.columns([1, 2, 1])
    if step > 1 and c1.button("← Voltar", key=f"cm_back_{step}", width="stretch"):
        _goto(step - 1)
        st.rerun()
    if step < 5 and c3.button(next_label, key=f"cm_next_{step}", type="primary", width="stretch", disabled=next_disabled):
        _goto(step + 1)
        st.rerun()


def render() -> None:
    saved = session.saved()
    cfg = session.work()
    if cfg is None:
        cfg = session.begin_new("")
    if STEP_KEY not in st.session_state:
        st.session_state[STEP_KEY] = int(cfg["commissioning"].get("step") or 1) if saved else 1
    step = st.session_state[STEP_KEY] if saved else 1
    plan = session.plan(cfg) if saved else None
    shell.hero("Comissionamento · primeira configuração",
               "Configure a microrrede desta instalação",
               "Esta instalação do SEEDS2 administra uma única microrrede. Registre-a uma vez: identificação, equipamentos, "
               "organização elétrica, parâmetros e demanda. O progresso é salvo localmente a cada etapa; depois da ativação, "
               "a configuração é mantida em Gestão da Microrrede.",
               [("Armazenamento", str(session.store().path))] + ([("Revisão", str(saved.revision))] if saved else []))
    shell.component("stepper")(key="seeds_stepper", data={"steps": _states(cfg, plan, saved is not None, step), "current": step},
                               on_action_change=_on_stepper)
    with st.container(key=f"cm_stage_{step}"):
        st.html('<div class="sd-stage"></div>')
        {1: _step1, 2: _step2, 3: _step3, 4: _step4, 5: _step5}[step](cfg, plan)


def _step1(cfg: dict, plan) -> None:
    st.markdown('<div class="sd-section">Etapa 01 — Identificação da instalação</div>', unsafe_allow_html=True)
    st.caption("Somente o nome é obrigatório. Campos não declarados ficam explicitamente marcados como tal.")
    if forms.installation_form(cfg, submit="Salvar e continuar →", key="cm_inst"):
        cfg["commissioning"]["step"] = 2
        if session.save(note="Comissionamento: identificação", origin="commissioning"):
            st.session_state[STEP_KEY] = 2
            forms.bump()
            st.rerun()
        else:
            st.error(st.session_state.get("mg_conflict") or st.session_state.get("mg_error") or "Falha ao salvar.")


def _step2(cfg: dict, plan) -> None:
    st.markdown('<div class="sd-section">Etapa 02 — Inventário energético</div>', unsafe_allow_html=True)
    st.caption("Registre os equipamentos solares, eólicos, de armazenamento, PEMFC e térmicos. Várias unidades da mesma "
               "tecnologia são permitidas. Cada inclusão é salva imediatamente.")
    forms.inventory(cfg, plan, autosave=True, key="cm_inv")
    if not cfg["equipment"]:
        shell.callout("Nenhum equipamento registrado. É possível continuar e registrar depois, mas a simulação exigirá ao "
                      "menos uma fonte despachável (PEMFC, bateria ou térmica).", "warn")
    _nav(2)


def _step3(cfg: dict, plan) -> None:
    st.markdown('<div class="sd-section">Etapa 03 — Configuração elétrica</div>', unsafe_allow_html=True)
    st.caption("Topologia simplificada de barramento comum, coerente com o balanço de potência do EMS atual.")
    forms.topology_view(cfg, plan, key="cm_topo")
    forms.grid_notice(cfg)
    if forms.topology_form(cfg, submit="Salvar configuração elétrica", key="cm_topo_form"):
        session.save(note="Comissionamento: topologia", origin="commissioning")
        forms.bump()
        st.rerun()
    _nav(3)


def _step4(cfg: dict, plan) -> None:
    st.markdown('<div class="sd-section">Etapa 04 — Parâmetros operacionais, demanda e dados</div>', unsafe_allow_html=True)
    st.caption("Limites, capacidades e disponibilidade de cada equipamento. Parâmetros com * são obrigatórios apenas para simular.")
    eqs = cfg["equipment"]
    if not eqs:
        st.info("Nenhum equipamento registrado (etapa 02).")
    for eq in eqs:
        missing = C.missing_required(eq)
        with st.container(border=True, key=f"cm_op_{eq['id']}"):
            c1, c2, c3 = st.columns([3.2, 1.2, 1.2], vertical_alignment="center")
            state = "configurado" if not missing else "faltam: " + ", ".join(missing)
            c1.markdown(f"**{eq['name']}** · {KIND_LABELS[eq['kind']]}  \n<span class='sd-muted'>{state}</span>", unsafe_allow_html=True)
            en = c2.toggle("Habilitado", value=bool(eq.get("enabled", True)), key=f"cm_en_{eq['id']}_{forms.token()}")
            if en != bool(eq.get("enabled", True)):
                C.update_equipment(cfg, eq["id"], enabled=en)
                forms.after_change(True, f"Disponibilidade alterada: {eq['name']}", "commissioning")
            if c3.button("Parâmetros", key=f"cm_edit_{eq['id']}", width="stretch"):
                forms.open_equipment(eq["id"], autosave=True)
                st.rerun()
    dlg = st.session_state.get("mg_dialog")
    if dlg and dlg.get("type") == "equipment":
        forms.equipment_dialog()
    st.markdown('<div class="sd-section">Demanda da instalação</div>', unsafe_allow_html=True)
    if forms.demand_editor(cfg, key="cm_dem", submit="Salvar demanda"):
        session.save(note="Comissionamento: demanda", origin="commissioning")
        forms.bump()
        st.rerun()
    if any(e["kind"] in ("pv", "wind") for e in eqs):
        st.markdown('<div class="sd-section">Clima para solar/eólica</div>', unsafe_allow_html=True)
        if forms.climate_editor(cfg, key="cm_clim", submit="Salvar clima"):
            session.save(note="Comissionamento: clima", origin="commissioning")
            forms.bump()
            st.rerun()
    _nav(4)


def _step5(cfg: dict, plan) -> None:
    st.markdown('<div class="sd-section">Etapa 05 — Revisão técnica e ativação</div>', unsafe_allow_html=True)
    by_kind = {k: [e for e in cfg["equipment"] if e["kind"] == k] for k in KINDS}
    tiles = []
    for k in ("pv", "wind", "pemfc", "thermal"):
        p = sum(C.installed_power_kW(e) or 0 for e in by_kind[k])
        tiles.append((KIND_LABELS[k], forms.fmt(p, 1, "kW") if by_kind[k] else "—", f"{len(by_kind[k])} equipamento(s)"))
    e_bat = sum(C.battery_energy_kWh(e) or 0 for e in by_kind["battery"])
    tiles.append(("Armazenamento", forms.fmt(e_bat, 1, "kWh") if by_kind["battery"] else "—", f"{len(by_kind['battery'])} banco(s)"))
    shell.kpis(tiles)
    forms.topology_view(cfg, plan, key="cm_review_topo")
    html, _ = forms.readiness_checks(cfg, plan)
    st.html(f'<div class="sd-section">Verificação técnica</div>{html}')
    st.caption("✓ completo/compatível · ! requer informação ou será excluído da simulação · ✕ bloqueio · – desabilitado")
    st.write("")
    shell.callout("A ativação conclui o comissionamento e abre o ambiente habitual. Nada impede completar ou alterar dados "
                  "depois, em <b>Gestão da Microrrede</b>, sem criar outra microrrede.")
    c1, _, c3 = st.columns([1, 1.2, 1.8])
    if c1.button("← Voltar", key="cm_back_5", width="stretch"):
        _goto(4)
        st.rerun()
    if c3.button("Ativar microrrede e concluir comissionamento", key="cm_activate", type="primary", width="stretch"):
        cfg["commissioning"].update(completed=True, step=5, completed_at=C.utc_now())
        if session.save(note="Comissionamento concluído — microrrede ativada", origin="commissioning"):
            st.session_state.pop(STEP_KEY, None)
            shell.go("inicio")
            forms.bump()
            st.rerun()
        else:
            st.error(st.session_state.get("mg_conflict") or st.session_state.get("mg_error") or "Falha ao salvar.")
