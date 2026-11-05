"""Comissionamento (primeira configuração) de uma microrrede do catálogo — nova ou ainda em configuração.

O progresso é salvo no armazenamento local a cada etapa (revisões com origem ``commissioning``):
fechar o navegador ou reiniciar o servidor não perde o que foi registrado, e é possível voltar a
etapas anteriores. A etapa 01 exige nome, natureza da atividade e modo de operação; o restante pode ficar
pendente, com indicação explícita do que falta para simular.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from seeds2.microgrid import config as C
from seeds2.microgrid.references import KIND_LABELS, KINDS

from . import equipment, exports, forms, session, shell

STEPS = [(1, "Identificação e localização"), (2, "Inventário energético"), (3, "Balanço energético"),
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
                miss = C.identification_missing(cfg)
                state, reason = ("completa", "") if saved_exists and not miss else \
                    (("atencao", "falta: " + ", ".join(miss).lower()) if saved_exists else ("progresso", ""))
            elif n == 2:
                k = len(cfg["equipment"])
                state, reason = ("completa", f"{k} equipamento(s)") if k else ("atencao", "nenhum equipamento")
            elif n == 3:
                ok = cfg["energy_balance"]["grid_connection"] != "nao_declarada"
                state, reason = ("completa", "") if ok else ("atencao", "conexão com a rede não declarada")
            elif n == 4:
                inc = [e for e in cfg["equipment"] if e.get("enabled", True) and not C.is_configured(e)]
                dem = bool(plan and plan.load_descriptor)
                if not inc and dem:
                    state = "completa"
                else:
                    state = "atencao"
                    reason = " · ".join(([f"{len(inc)} equipamento(s) pendente(s)"] if inc else []) + ([] if dem else ["demanda não definida"]))
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
        if session.active_uid() is not None:            # não deveria ocorrer: a microrrede aberta sempre tem configuração
            st.error("Configuração da microrrede indisponível nesta sessão. Volte ao Gestor e abra-a novamente.")
            return
        cfg = session.begin_new("")
    if STEP_KEY not in st.session_state:
        st.session_state[STEP_KEY] = int(cfg["commissioning"].get("step") or 1) if saved else 1
    step = st.session_state[STEP_KEY] if saved else 1
    plan = session.plan(cfg) if saved else None
    shell.hero("Comissionamento · " + ("nova microrrede" if saved is None else "configuração em andamento"),
               cfg["installation"].get("name") or "Configure a nova microrrede",
               "Registre a microrrede: identificação, equipamentos, modelo de balanço energético, parâmetros e demanda. "
               "Ela entra no Gestor de microrredes ao salvar a etapa 01 (armazenamento próprio e independente) e o progresso "
               "é salvo a cada etapa — é possível sair e retomar depois. Após a ativação, a configuração é mantida em "
               "Gestão da Microrrede.",
               [("Armazenamento", session.storage_label())] + ([("Revisão", str(saved.revision))] if saved else []) +
               [("Identidade", cfg["installation"]["uid"])])
    shell.component("stepper")(key="seeds_stepper", data={"steps": _states(cfg, plan, saved is not None, step), "current": step},
                               on_action_change=_on_stepper)
    with st.container(key=f"cm_stage_{step}"):
        st.html('<div class="sd-stage"></div>')
        {1: _step1, 2: _step2, 3: _step3, 4: _step4, 5: _step5}[step](cfg, plan)


def _step1(cfg: dict, plan) -> None:
    st.markdown('<div class="sd-section">Etapa 01 — Identificação e localização</div>', unsafe_allow_html=True)
    forms.identification_cards(cfg, key="cm_ident")
    st.write("")
    _, c2 = st.columns([2, 1])
    if c2.button("Salvar e continuar →", key="cm_ident_save", type="primary", width="stretch"):
        errs = forms.apply_identification(cfg, key="cm_ident")
        if errs:
            for e in errs:
                st.error(shell.md(e))
            return
        cfg["commissioning"]["step"] = 2
        if session.save(note="Comissionamento: identificação e localização", origin="commissioning"):
            st.session_state[STEP_KEY] = 2
            forms.bump()
            st.rerun()
        else:
            st.error(shell.md(st.session_state.get("mg_conflict") or st.session_state.get("mg_error") or "Falha ao salvar."))


def _step2(cfg: dict, plan) -> None:
    st.markdown('<div class="sd-section">Etapa 02 — Inventário energético</div>', unsafe_allow_html=True)
    st.caption("Registre os equipamentos solares, eólicos, de armazenamento, PEMFC e térmicos. Várias unidades da mesma "
               "tecnologia são permitidas. Cada registro confirmado é salvo imediatamente.")
    forms.inventory(cfg, plan, autosave=True, key="cm_inv")
    if not cfg["equipment"]:
        shell.callout("Nenhum equipamento registrado. É possível continuar e registrar depois, mas a simulação exigirá ao "
                      "menos uma fonte despachável (PEMFC, bateria ou térmica).", "warn")
    _nav(2)


def _step3(cfg: dict, plan) -> None:
    st.markdown('<div class="sd-section">Etapa 03 — Esquema lógico do balanço energético</div>', unsafe_allow_html=True)
    st.caption("O SEEDS2 integra modelos energéticos para um balanço de potência e energia agregado. Não há configuração "
               "de barramentos, tensões ou acoplamentos físicos nesta versão.")
    forms.balance_view(cfg, plan, key="cm_bal")
    if forms.grid_form(cfg, key="cm_bal"):
        session.save(note="Comissionamento: conexão com a rede declarada", origin="commissioning")
        forms.bump()
        st.rerun()
    forms.grid_notice(cfg)
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
            state = "configurado para simulação" if not missing else "pendente: " + ", ".join(missing)
            c1.html(f"<b>{escape(eq['name'])}</b> · {escape(KIND_LABELS[eq['kind']])}<br>"
                    f"<span class='sd-muted'>{escape(state)}</span>")
            en = c2.toggle("Habilitado", value=bool(eq.get("enabled", True)), key=f"cm_en_{eq['id']}_{forms.token()}")
            if en != bool(eq.get("enabled", True)):
                C.update_equipment(cfg, eq["id"], enabled=en)
                forms.after_change(True, f"Disponibilidade alterada: {eq['name']}", "commissioning")
            if c3.button("Parâmetros", key=f"cm_edit_{eq['id']}", width="stretch"):
                equipment.open_edit(eq["id"], True)
                st.rerun()
    equipment.maybe_dialog()
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
    forms.balance_view(cfg, plan, key="cm_review_bal")
    html, _ = forms.readiness_checks(cfg, plan)
    st.html(f'<div class="sd-section">Verificação técnica</div>{html}')
    st.caption("✓ completo/compatível · ! requer informação ou será excluído da simulação · ✕ bloqueio · – desabilitado")
    st.markdown('<div class="sd-section">Documentação da configuração</div>', unsafe_allow_html=True)
    exports.export_actions(key="cm_exp")
    st.write("")
    shell.callout("A ativação conclui o comissionamento e abre o ambiente habitual. Nada impede completar ou alterar dados "
                  "depois, em <b>Gestão da Microrrede</b>, sem criar outra microrrede.")
    miss = C.identification_missing(cfg)
    if miss:
        st.warning("Complete a identificação (etapa 01) antes de ativar: " + shell.md(", ".join(miss)))
    c1, _, c3 = st.columns([1, 1.2, 1.8])
    if c1.button("← Voltar", key="cm_back_5", width="stretch"):
        _goto(4)
        st.rerun()
    if c3.button("Ativar microrrede e concluir comissionamento", key="cm_activate", type="primary", width="stretch",
                 disabled=bool(miss)):
        cfg["commissioning"].update(completed=True, step=5, completed_at=C.utc_now())
        if session.save(note="Comissionamento concluído — microrrede ativada", origin="commissioning"):
            st.session_state.pop(STEP_KEY, None)
            shell.go("inicio")
            forms.bump()
            st.rerun()
        else:
            st.error(shell.md(st.session_state.get("mg_conflict") or st.session_state.get("mg_error") or "Falha ao salvar."))
