"""Editores reutilizados pelo comissionamento e pela Gestão da Microrrede.

Regras: nenhum valor físico é pré-preenchido (campos vazios = "não declarado"); toda grandeza mostra
unidade; referências exibem a procedência do catálogo; alterações vão para a cópia de trabalho e são
salvas imediatamente (``autosave``, comissionamento) ou ficam pendentes até "Salvar" (Gestão).
"""
from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from seeds2.microgrid import adapter as A
from seeds2.microgrid import config as C
from seeds2.microgrid.references import KIND_LABELS, KINDS, THERMAL_PRESET_NOTE, references_for, thermal_fuel_presets

from . import session, shell


# ------------------------------------------------------------------ utilidades
def fmt(x: float | None, d: int = 1, unit: str = "") -> str:
    if x is None:
        return "—"
    s = f"{x:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"{s} {unit}".strip()


def token() -> int:
    return int(st.session_state.get("mg_form_token", 0))


def bump() -> None:
    st.session_state["mg_form_token"] = token() + 1


def after_change(autosave: bool, note: str, origin: str = "edit") -> None:
    """Depois de alterar a cópia de trabalho: grava (comissionamento) ou deixa pendente (Gestão)."""
    if autosave:
        session.save(note=note, origin=origin)
    bump()
    st.rerun()


def ref_label(eq: dict) -> str | None:
    ref = (eq.get("params") or {}).get("reference")
    if eq["kind"] == "thermal":
        dyn = (eq.get("params") or {}).get("dynamic")
        return C.choices("thermal", "dynamic").get(dyn) if dyn else None
    if not ref:
        return None
    r = references_for(eq["kind"]).get(ref)
    return r.label if r else ref


def facts(eq: dict) -> list[tuple[str, str]]:
    p = eq.get("params") or {}
    k = eq["kind"]
    if k == "pv":
        return [("Potência STC", fmt(C.installed_power_kW(eq), 2, "kWp")),
                ("Arranjo", f"{p.get('n_series') or '—'} × {p.get('n_parallel') or '—'}"),
                ("Sujeira", fmt(p.get("soiling_pct"), 1, "%")), ("Módulos", str((p.get('n_series') or 0) * (p.get('n_parallel') or 0) or "—"))]
    if k == "wind":
        return [("Potência nominal", fmt(C.installed_power_kW(eq), 0, "kW")), ("Quantidade", str(p.get("count") or "—")),
                ("Perda genérica", "sim" if p.get("apply_grid_loss") else "não"), ("", "")]
    if k == "battery":
        return [("Energia nominal", fmt(C.battery_energy_kWh(eq), 1, "kWh")),
                ("Ns × Np", f"{p.get('n_series') or '—'} × {p.get('n_parallel') or '—'}"),
                ("SOC mín/máx", f"{fmt(p.get('soc_min_pct'), 0)} / {fmt(p.get('soc_max_pct'), 0)} %"),
                ("Carga/descarga", f"{fmt(p.get('c_charge'), 2)} / {fmt(p.get('c_discharge'), 2)} C")]
    if k == "pemfc":
        return [("Potência líquida máx.", fmt(C.installed_power_kW(eq), 1, "kW")), ("Sistemas", str(p.get("quantity") or "—")),
                ("Base no EMS", C.PEMFC_POWER_BASIS.get(p.get("power_basis"), "—")), ("", "")]
    return [("Potência máx.", fmt(p.get("pmax_kW"), 1, "kW")), ("Mín. técnica", fmt(p.get("pmin_kW"), 1, "kW")),
            ("CVU", fmt(p.get("cvu_rs_MWh"), 0, "R$/MWh")), ("Rampa", fmt(p.get("ramp_kW_min"), 1, "kW/min") if p.get("ramp_kW_min") else "sem limite")]


def card_data(cfg: dict, plan) -> dict:
    status = {m.id: m for m in (plan.mappings if plan else [])}
    items = []
    for eq in cfg.get("equipment", []):
        missing = C.missing_required(eq)
        errs = C.errors(C.equipment_issues(eq))
        m = status.get(eq["id"])
        badges = []
        if not eq.get("enabled", True):
            badges.append({"tone": "off", "text": "Desabilitado"})
        badges.append({"tone": "ok", "text": "Configurado"} if not missing and not errs else
                      {"tone": "warn", "text": f"Faltam {len(missing)} parâmetro(s)" if missing else "Dados inválidos",
                       "title": ", ".join(missing)})
        if m and m.status == A.REPRESENTED:
            badges.append({"tone": "ok", "text": "Compatível com a simulação", "title": m.reason or ""})
        elif m and m.status == A.INCOMPATIBLE:
            badges.append({"tone": "bad", "text": "Não representável no EMS", "title": m.reason})
        reason, tone = "", ""
        if m and m.status == A.INCOMPATIBLE:
            reason, tone = m.reason, "bad"
        elif missing and eq.get("enabled", True):
            reason, tone = "Obrigatório para simular: " + ", ".join(missing), "warn"
        elif m and m.status == A.REPRESENTED and m.reason:
            reason = m.reason
        items.append({"id": eq["id"], "kind": eq["kind"], "kind_label": KIND_LABELS[eq["kind"]], "name": eq["name"],
                      "tag": eq.get("tag", ""), "enabled": bool(eq.get("enabled", True)), "reference_label": ref_label(eq),
                      "badges": badges, "facts": [f for f in facts(eq) if f[0]], "reason": reason, "reason_tone": tone,
                      "sim_status": m.status if m else ""})
    return {"items": items, "kinds": [[k, KIND_LABELS[k]] for k in KINDS],
            "states": [[k, v] for k, v in A.STATUS_LABELS.items()]}


# ------------------------------------------------------------------ inventário
def open_equipment(eq_id: str | None = None, kind: str | None = None, autosave: bool = False) -> None:
    st.session_state["mg_dialog"] = {"type": "equipment", "id": eq_id, "kind": kind, "autosave": autosave,
                                     "token": token() + 1}
    bump()


def _on_inventory() -> None:
    a = shell.payload("seeds_inventory")
    if not a:
        return
    autosave = bool(st.session_state.get("mg_inventory_autosave"))
    if a.get("type") == "open" and session.work() and C.find_equipment(session.work(), a.get("id", "")):
        open_equipment(a["id"], autosave=autosave)
    elif a.get("type") == "add":
        open_equipment(None, autosave=autosave)


def inventory(cfg: dict, plan, *, autosave: bool, key: str = "inv") -> None:
    st.session_state["mg_inventory_autosave"] = autosave
    data = card_data(cfg, plan)
    c1, c2 = st.columns([4, 1.25], vertical_alignment="bottom")
    with c1:
        n = len(cfg.get("equipment", []))
        st.markdown(f'<div class="sd-section">Inventário energético · {n} equipamento(s)</div>', unsafe_allow_html=True)
        st.caption("Cada cartão é uma unidade ou agrupamento físico desta microrrede. Clique para editar; "
                   "estados: registrado → tecnicamente configurado → compatível com a simulação.")
    with c2:
        if st.button("＋ Adicionar equipamento", key=f"{key}_add", type="primary", width="stretch"):
            open_equipment(None, autosave=autosave)
            st.rerun()
    shell.component("inventory")(key="seeds_inventory", data={**data, "readonly": False}, on_action_change=_on_inventory)
    if cfg.get("equipment"):
        with st.expander("Lista tabular e edição por seleção"):
            rows = [{"Equipamento": i["name"], "Tecnologia": i["kind_label"], "TAG": i["tag"], "Referência": i["reference_label"] or "—",
                     "Habilitado": "sim" if i["enabled"] else "não", "Estado na simulação": A.STATUS_LABELS.get(i["sim_status"], "—"),
                     "Identificador": i["id"]} for i in data["items"]]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            ids = [e["id"] for e in cfg["equipment"]]
            names = {e["id"]: f"{e['name']} · {KIND_LABELS[e['kind']]} · {e['id']}" for e in cfg["equipment"]}
            s1, s2 = st.columns([4, 1], vertical_alignment="bottom")
            sel = s1.selectbox("Equipamento", ids, format_func=names.get, key=f"{key}_sel_{token()}")
            if s2.button("Editar", key=f"{key}_edit", width="stretch"):
                open_equipment(sel, autosave=autosave)
                st.rerun()
    retired = cfg.get("retired") or []
    if retired:
        with st.expander(f"Equipamentos retirados ({len(retired)}) — registro de auditoria"):
            st.dataframe(pd.DataFrame([{"Equipamento": r["name"], "Tecnologia": KIND_LABELS[r["kind"]], "Identificador": r["id"],
                                        "Retirado em": shell.fmt_time(r.get("retired_at")), "Motivo": r.get("retired_reason") or "—"}
                                       for r in retired]), hide_index=True, width="stretch")
    dlg = st.session_state.get("mg_dialog")
    if dlg and dlg.get("type") == "equipment":
        equipment_dialog()


def _close_dialog() -> None:
    st.session_state.pop("mg_dialog", None)


def _param_widget(kind: str, spec: C.ParamSpec, value: Any, k: str):
    unit = f" [{spec.unit}]" if spec.unit else ""
    label = f"{spec.label}{unit}{' *' if spec.required else ''}"
    if spec.type == "choice":
        opts = C.choices(kind, spec.name)
        keys = list(opts)
        return st.selectbox(label, keys, index=keys.index(value) if value in keys else None, format_func=lambda x: opts.get(x, x),
                            placeholder="— não declarado —", key=k, help=spec.help or None)
    if spec.type == "bool":
        return st.toggle(label.replace(" *", ""), value=bool(value) if value is not None else bool(spec.default), key=k, help=spec.help or None)
    if spec.type == "int":
        return st.number_input(label, min_value=int(spec.min) if spec.min is not None and not spec.min_exclusive else None,
                               value=int(value) if value is not None else None, step=1, format="%d", key=k,
                               placeholder="não declarado", help=spec.help or None)
    v = st.number_input(label, min_value=float(spec.min) if spec.min is not None and not spec.min_exclusive else None,
                        max_value=float(spec.max) if spec.max is not None and not spec.max_exclusive else None,
                        value=float(value) if value is not None else None, step=None, format="%.4g", key=k,
                        placeholder="não declarado", help=spec.help or None)
    return v


def _reference_panel(kind: str, ref_key: str | None) -> None:
    if kind == "thermal" or not ref_key:
        return
    r = references_for(kind).get(ref_key)
    if not r:
        return
    rows = "".join(f"<tr><td>{escape(str(k))}</td><td><b>{escape(str(v))}</b></td></tr>" for k, v in r.summary.items() if v is not None)
    st.html(f'<div class="sd-callout"><div class="sd-eyebrow">Referência técnica · {escape(r.category)}</div>'
            f'<div style="font-weight:650;margin:.15rem 0 .3rem">{escape(r.label)}</div>'
            f'<table style="font-size:.82rem;border-collapse:collapse">{rows}</table>'
            f'<div style="font-size:.78rem;opacity:.8;margin-top:.35rem">Procedência: {escape(r.provenance)}</div>'
            f'{"<div style=font-size:.78rem;opacity:.8>" + escape(r.notes) + "</div>" if r.notes else ""}</div>')


@st.dialog("Equipamento da microrrede", width="large", on_dismiss=_close_dialog)
def equipment_dialog() -> None:
    dlg = st.session_state.get("mg_dialog") or {}
    cfg = session.work()
    eq = C.find_equipment(cfg, dlg.get("id")) if dlg.get("id") else None
    t = dlg.get("token", 0)
    kp = f"eqd_{t}_"
    if eq is None:
        kind = st.radio("Tecnologia *", list(KINDS), format_func=KIND_LABELS.get, horizontal=True, key=kp + "kind",
                        index=list(KINDS).index(dlg["kind"]) if dlg.get("kind") in KINDS else 0)
        st.caption("Somente o nome e a tecnologia são obrigatórios para registrar. Parâmetros marcados com * são exigidos "
                   "apenas para a simulação; deixe vazio o que ainda não é conhecido.")
        params0: dict = {p.name: p.default for p in C.PARAM_SPECS[kind]}
    else:
        kind = eq["kind"]
        params0 = dict(eq["params"])
        st.html(f'<div class="sd-eyebrow">{escape(KIND_LABELS[kind])}</div><div class="sd-mono" style="opacity:.75">'
                f'Identificador estável: {escape(eq["id"])} · criado {escape(shell.fmt_time(eq.get("created_at")))} · '
                f'alterado {escape(shell.fmt_time(eq.get("updated_at")))}</div>')
    c1, c2 = st.columns([2, 1])
    name = c1.text_input("Nome do equipamento *", value=eq["name"] if eq else "", key=kp + "name",
                         placeholder="p. ex. Arranjo FV cobertura norte")
    tag = c2.text_input("TAG / código técnico", value=eq.get("tag", "") if eq else "", key=kp + "tag")
    c3, c4 = st.columns([2, 1])
    serial = c3.text_input("Nº de série / identificação física", value=eq.get("serial", "") if eq else "", key=kp + "serial")
    enabled = c4.toggle("Habilitado", value=bool(eq.get("enabled", True)) if eq else True, key=kp + "enabled",
                        help="Desabilitado: permanece no inventário, mas não entra em simulações.")
    st.markdown("**Parâmetros técnicos**")
    values: dict[str, Any] = {}
    specs = C.PARAM_SPECS[kind]
    cols = st.columns(2)
    for i, spec in enumerate(specs):
        with cols[i % 2]:
            values[spec.name] = _param_widget(kind, spec, params0.get(spec.name), kp + f"p_{kind}_{spec.name}")
    if kind == "thermal":
        fp = values.get("fuel_preset")
        if fp:
            pr = thermal_fuel_presets()[fp]
            st.caption(f"Preset ACADÊMICO «{fp}»: CVU de referência {fmt(pr['cvu_rs_mwh'], 0, 'R$/MWh')} — {pr['note']} "
                       "O CVU acima só é alterado se você digitá-lo.")
        st.caption(THERMAL_PRESET_NOTE)
    _reference_panel(kind, values.get("reference"))
    notes = st.text_area("Observações", value=eq.get("notes", "") if eq else "", key=kp + "notes", height=68)
    clean = {k: (int(v) if isinstance(v, float) and C.PARAM_INDEX[kind][k].type == "int" else v) for k, v in values.items()}
    probe = C.new_equipment(kind, name or "—", params=clean)
    issues = C.errors(C.equipment_issues(probe))
    missing = C.missing_required(probe)
    derived = []
    if C.installed_power_kW(probe) is not None:
        derived.append(f"Potência derivada: **{fmt(C.installed_power_kW(probe), 2, 'kW')}** (referência × quantidade)")
    if C.battery_energy_kWh(probe) is not None:
        derived.append(f"Energia nominal derivada: **{fmt(C.battery_energy_kWh(probe), 1, 'kWh')}** (V·Q da célula × Ns × Np)")
    if derived:
        st.markdown(" · ".join(derived))
    for i in issues:
        st.error(shell.md(i.message))
    if missing and not issues:
        st.info("Registrável, mas ainda **não tecnicamente configurado** — faltam: " + ", ".join(missing))
    b1, b2 = st.columns(2)
    ok = b1.button("Aplicar" if not dlg.get("autosave") else "Salvar equipamento", type="primary", width="stretch",
                   key=kp + "apply", disabled=not str(name).strip() or bool(issues))
    if b2.button("Cancelar", width="stretch", key=kp + "cancel"):
        _close_dialog()
        st.rerun()
    if ok:
        try:
            if eq is None:
                new = C.new_equipment(kind, name, tag=tag, serial=serial, enabled=enabled, notes=notes, params=clean)
                C.add_equipment(cfg, new)
                note = f"Equipamento adicionado: {new['name']}"
            else:
                C.update_equipment(cfg, eq["id"], name=name, tag=tag, serial=serial, enabled=enabled, notes=notes, params=clean)
                note = f"Equipamento alterado: {name}"
        except (ValueError, KeyError) as exc:
            st.error(shell.md(exc))
            return
        _close_dialog()
        after_change(bool(dlg.get("autosave")), note, "commissioning" if dlg.get("autosave") else "edit")
    if eq is not None:
        with st.expander("Retirar este equipamento do inventário"):
            st.caption("O equipamento sai do inventário ativo e deixa de participar de simulações. O registro permanece em "
                       "'Equipamentos retirados' e nas revisões anteriores (auditoria).")
            reason = st.text_input("Motivo da retirada", key=kp + "ret_reason", placeholder="p. ex. desmontado para manutenção")
            confirm = st.checkbox(f"Confirmo a retirada de «{shell.md(eq['name'])}»", key=kp + "ret_ok")
            if st.button("Retirar equipamento", key=kp + "retire", disabled=not confirm):
                C.retire_equipment(cfg, eq["id"], reason)
                _close_dialog()
                after_change(bool(dlg.get("autosave")), f"Equipamento retirado: {eq['name']}",
                             "commissioning" if dlg.get("autosave") else "edit")


# ------------------------------------------------------------------ instalação
def installation_form(cfg: dict, *, submit: str, key: str) -> bool:
    inst = cfg["installation"]
    with st.form(f"{key}_{token()}"):
        name = st.text_input("Nome da instalação *", value=inst.get("name", ""), placeholder="p. ex. Laboratório de Microrredes — Bloco C")
        desc = st.text_area("Descrição", value=inst.get("description", ""), height=80)
        c1, c2 = st.columns(2)
        nat_keys = list(C.NATURE_OPTIONS)
        nature = c1.selectbox("Natureza da atividade", nat_keys, index=nat_keys.index(inst["nature"]) if inst.get("nature") in nat_keys else None,
                              format_func=C.NATURE_OPTIONS.get, placeholder="— não declarado —")
        mode_keys = list(C.OPERATION_MODE_OPTIONS)
        mode = c2.selectbox("Modo de operação previsto", mode_keys,
                            index=mode_keys.index(inst["operation_mode"]) if inst.get("operation_mode") in mode_keys else None,
                            format_func=C.OPERATION_MODE_OPTIONS.get, placeholder="— não declarado —",
                            help="Declaração da instalação. O EMS atual não otimiza importação/exportação com a rede.")
        loc = st.text_input("Localização (opcional)", value=inst.get("location", ""), placeholder="cidade, endereço ou referência interna")
        c3, c4, c5 = st.columns(3)
        lat = c3.number_input("Latitude [°] (opcional)", min_value=-90.0, max_value=90.0, value=inst.get("latitude"), format="%.5f", placeholder="não declarada")
        lon = c4.number_input("Longitude [°] (opcional)", min_value=-180.0, max_value=180.0, value=inst.get("longitude"), format="%.5f", placeholder="não declarada")
        tz = c5.text_input("Fuso horário IANA (opcional)", value=inst.get("timezone", ""), placeholder="p. ex. America/Sao_Paulo")
        sent = st.form_submit_button(submit, type="primary", width="stretch")
    if not sent:
        return False
    if not name.strip():
        st.error("O nome da instalação é obrigatório.")
        return False
    probe = {**inst, "name": name.strip(), "description": desc.strip(), "nature": nature, "operation_mode": mode,
             "location": loc.strip(), "latitude": lat, "longitude": lon, "timezone": tz.strip()}
    test = {**cfg, "installation": probe}
    errs = [i for i in C.errors(C.validate(test)) if i.path.startswith("installation")]
    if errs:
        for e in errs:
            st.error(e.message)
        return False
    cfg["installation"] = probe
    return True


# ------------------------------------------------------------------ topologia
def topology_data(cfg: dict, plan) -> dict:
    topo = cfg["topology"]
    status = {m.id: m for m in (plan.mappings if plan else [])}
    nodes = []
    for eq in cfg.get("equipment", []):
        m = status.get(eq["id"])
        f = facts(eq)
        nodes.append({"id": eq["id"], "name": eq["name"], "kind": eq["kind"], "kind_label": KIND_LABELS[eq["kind"]],
                      "role": "storage" if eq["kind"] == "battery" else "gen", "enabled": bool(eq.get("enabled", True)),
                      "detail": f"{f[0][0]}: {f[0][1]}" if f else "",
                      "coupling": C.COUPLING_OPTIONS.get(topo.get("couplings", {}).get(eq["id"], "nao_declarado")),
                      "sim_status": m.status if m else "", "sim_label": (A.STATUS_LABELS[m.status] + (": " + m.reason if m.reason else "")) if m else ""})
    dem = cfg.get("demand") or {}
    v = topo.get("nominal_voltage_V")
    return {"bus": {"label": topo.get("bus_label") or "Barramento principal", "kind_label": C.BUS_KIND_OPTIONS[topo["bus_kind"]],
                    "voltage": fmt(v, 0, "V") + " (declarada)" if v else ""},
            "grid": {"state": topo.get("grid_connection")},
            "nodes": nodes,
            "load": {"label": "Demanda da instalação", "detail": C.DEMAND_SOURCES.get(dem.get("source"), "")[:30],
                     "coupling": C.COUPLING_OPTIONS.get(topo.get("load_coupling"))}}


def topology_view(cfg: dict, plan, key: str = "topo") -> None:
    shell.component("topology")(key=f"seeds_{key}", data=topology_data(cfg, plan))


def topology_form(cfg: dict, *, submit: str, key: str) -> bool:
    topo = cfg["topology"]
    with st.form(f"{key}_{token()}"):
        c1, c2, c3 = st.columns([1.2, 1.6, 1])
        bk = list(C.BUS_KIND_OPTIONS)
        bus_kind = c1.radio("Tipo de barramento", bk, index=bk.index(topo["bus_kind"]), format_func=C.BUS_KIND_OPTIONS.get)
        bus_label = c2.text_input("Nome do barramento", value=topo.get("bus_label", ""))
        volt = c3.number_input("Tensão nominal declarada [V]", min_value=0.0, value=topo.get("nominal_voltage_V"), placeholder="não declarada",
                               help="Informativa. O EMS faz apenas balanço de potência; não calcula tensões.")
        gk = list(C.GRID_CONNECTION_OPTIONS)
        grid = st.radio("Conexão com a rede elétrica", gk, index=gk.index(topo["grid_connection"]), horizontal=True,
                        format_func=C.GRID_CONNECTION_OPTIONS.get,
                        help="Declarar conexão NÃO habilita importação/exportação no EMS atual (não modelado).")
        st.markdown("**Acoplamento de cada equipamento ao barramento**")
        ck = list(C.COUPLING_OPTIONS)
        couplings = {}
        eqs = cfg.get("equipment", [])
        cols = st.columns(2)
        for i, eq in enumerate(eqs):
            cur = topo.get("couplings", {}).get(eq["id"], "nao_declarado")
            couplings[eq["id"]] = cols[i % 2].selectbox(f"{shell.md(eq['name'])} · {KIND_LABELS[eq['kind']]}", ck, index=ck.index(cur),
                                                        format_func=C.COUPLING_OPTIONS.get, key=f"{key}_cp_{eq['id']}_{token()}")
        if not eqs:
            st.caption("Nenhum equipamento registrado ainda.")
        load = st.selectbox("Acoplamento da demanda", ck, index=ck.index(topo.get("load_coupling", "nao_declarado")),
                            format_func=C.COUPLING_OPTIONS.get)
        sent = st.form_submit_button(submit, type="primary", width="stretch")
    if not sent:
        return False
    cfg["topology"] = {**topo, "bus_kind": bus_kind, "bus_label": bus_label.strip() or "Barramento principal",
                       "nominal_voltage_V": float(volt) if volt else None, "grid_connection": grid,
                       "couplings": couplings, "load_coupling": load}
    return True


def grid_notice(cfg: dict) -> None:
    if cfg["topology"].get("grid_connection") == "conectada" or cfg["installation"].get("operation_mode") in ("conectada", "conectada_ilhamento"):
        shell.callout("<b>Conexão com a rede declarada.</b> O EMS atual não modela importação/exportação nem tarifas: a "
                      "simulação trata a microrrede como balanço local (déficit e vertimento penalizados). Essa capacidade "
                      "permanece identificada como <b>não implementada</b>.", "warn")


# ------------------------------------------------------------------ demanda e clima
def _csv_meta(raw: pd.DataFrame, filename: str) -> dict:
    from ems_integration import ponte

    base = ponte.carga_de_dataframe(raw, filename)
    return {"rows": int(len(raw)), "columns": [str(c) for c in raw.columns], "t0": str(base.t0),
            "duration_total_min": float(base.duracao_min)}


def demand_editor(cfg: dict, *, key: str, submit: str) -> bool:
    from ems_integration import ponte
    from visualization import ems_plots as EMSP

    dem = cfg["demand"]
    kp = f"{key}_{token()}_"
    src_keys = list(C.DEMAND_SOURCES)
    src = st.radio("Fonte da demanda", src_keys, index=src_keys.index(dem.get("source", "nao_definida")),
                   format_func=C.DEMAND_SOURCES.get, key=kp + "src")
    desc: dict = {}
    new_blob: tuple[bytes, str] | None = None
    csv_meta: dict | None = None
    prov = dem.get("provenance", "nao_declarado")
    try:
        if src == "walkforward":
            opts = ponte.opcoes_walkforward()
            w = dem.get("walkforward") or {}
            c1, c2, c3 = st.columns(3)
            scen = sorted(opts.scenario.unique())
            prof = ["Econômico", "Normal", "Máxima"]
            hours = [int(h) for h in sorted(opts.start_hour.unique())]
            s = c1.selectbox("Cenário", scen, index=scen.index(w["scenario"]) if w.get("scenario") in scen else None, placeholder="—", key=kp + "wf_s")
            p = c2.selectbox("Perfil", prof, index=prof.index(w["profile"]) if w.get("profile") in prof else None, placeholder="—", key=kp + "wf_p")
            h = c3.selectbox("Início", hours, index=hours.index(int(w["start_hour"])) if w.get("start_hour") is not None and int(w["start_hour"]) in hours else None,
                             format_func=lambda x: f"{x:02d}:00", placeholder="—", key=kp + "wf_h")
            prov = "referencia"
            st.caption("Conjunto de referência do projeto (missão de embarcação, 2 h, resolução 1 min). Não é medição desta instalação.")
            if s and p and h is not None:
                desc = {"source": "walkforward", "scenario": s, "profile": p, "start_hour": int(h)}
        elif src == "copel":
            c = dem.get("copel") or {}
            c1, c2, c3 = st.columns(3)
            days = ["util", "sabado", "domingo"]
            day = c1.selectbox("Dia", days, index=days.index(c["day"]) if c.get("day") in days else None, placeholder="—",
                               format_func=lambda x: {"util": "Dia útil", "sabado": "Sábado", "domingo": "Domingo"}[x], key=kp + "cp_d")
            sh = c2.number_input("Início [h]", 0, 23, value=c.get("start_h"), placeholder="—", key=kp + "cp_h")
            du = c3.number_input("Duração [min]", 30, 1440, value=c.get("duration_min"), step=30, placeholder="—", key=kp + "cp_m")
            prov = "referencia"
            st.caption("Curva típica COPEL B1 incluída no software (referência; não medida nesta instalação).")
            if day and sh is not None and du:
                desc = {"source": "copel", "day": day, "start_h": int(sh), "duration_min": int(du)}
        elif src == "csv":
            cur = dem.get("csv") or {}
            up = st.file_uploader("CSV de carga (t_min/P_kW ou timestamp/P_kW, potência em kW)", type=["csv"], key=kp + "up")
            blob_name = cur.get("filename")
            meta_src = None
            if up is not None:
                data = up.getvalue()
                raw = A.read_csv_bytes(data)
                csv_meta = _csv_meta(raw, up.name)
                new_blob, blob_name, meta_src = (data, up.name), up.name, csv_meta
            elif cur.get("blob"):
                st.caption(f"Arquivo armazenado: **{shell.md(cur.get('filename'))}** · SHA-256 `{cur['blob'][:12]}…` · "
                           f"{shell.md(cur.get('rows', '?'))} linhas")
                meta_src = cur
            if meta_src is not None:
                tot = float(meta_src.get("duration_total_min") or 0)
                c1, c2 = st.columns(2)
                start = c1.number_input("Início da janela [min]", 0, max(0, int(tot) - 5), value=int(cur.get("start_min") or 0) if not new_blob else 0, key=kp + "csv_s")
                dur = c2.number_input("Duração [min]", 5, max(5, int(tot)), value=min(int(cur.get("duration_min") or 120), max(5, int(tot))) if not new_blob else min(120, max(5, int(tot))), key=kp + "csv_d")
                if new_blob is not None:
                    from hashlib import sha256
                    desc = {"source": "csv", "blob": sha256(new_blob[0]).hexdigest(), "filename": blob_name, "start_min": int(start), "duration_min": int(dur)}
                else:
                    desc = {"source": "csv", "blob": cur["blob"], "filename": blob_name, "start_min": int(start), "duration_min": int(dur)}
            pk = ["medido", "sintetico", "nao_declarado"]
            prov = st.radio("Procedência declarada do CSV", pk, index=pk.index(prov) if prov in pk else 2, horizontal=True,
                            format_func=C.PROVENANCE_KINDS.get, key=kp + "prov")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Não foi possível preparar a demanda: {shell.md(exc)}")
        desc = {}
    c1, c2 = st.columns(2)
    tz = c1.text_input("Fuso horário dos carimbos de tempo (opcional)", value=dem.get("timezone", ""), key=kp + "tz",
                       placeholder="p. ex. America/Sao_Paulo — vazio = não declarado")
    notes = c2.text_input("Observações sobre os dados", value=dem.get("notes", ""), key=kp + "notes")
    st.caption("Convenções: potência ativa consumida **positiva**, em **kW**; o EMS usa grade de **1 min** (o CSV é interpolado "
               "nessa grade pela função da V1.6). Os dados importados ficam armazenados localmente com hash SHA-256.")
    if desc:
        try:
            get = (lambda h: new_blob[0]) if new_blob is not None else session.store().get_blob
            carga = A.build_load(desc, get)
            e = float(carga.P_kW.sum() / 60.0)
            shell.kpis([("Energia na janela", fmt(e, 1, "kWh"), ""), ("Pico", fmt(float(carga.P_kW.max()), 1, "kW"), ""),
                        ("Média", fmt(float(carga.P_kW.mean()), 1, "kW"), ""), ("Passos", str(len(carga.P_kW)), "1 min")])
            st.plotly_chart(EMSP.fig_carga(carga.t_min, carga.P_kW, carga.descricao), width="stretch", key=kp + "plot")
        except Exception as exc:  # noqa: BLE001
            st.error(f"A janela escolhida não pode ser reconstruída: {shell.md(exc)}")
            desc = {}
    elif src != "nao_definida":
        st.info("Complete os campos acima para definir a demanda.")
    if not st.button(submit, type="primary", key=kp + "apply", width="stretch"):
        return False
    if src != "nao_definida" and not desc:
        st.error("Demanda incompleta: preencha os campos ou escolha 'Ainda não definida'.")
        return False
    if new_blob is not None:
        digest = session.store().put_blob(new_blob[0], new_blob[1], "text/csv")
        desc["blob"] = digest
    new = {**dem, "source": src, "provenance": prov if src != "nao_definida" else "nao_declarado", "timezone": tz.strip(), "notes": notes.strip()}
    if src == "walkforward":
        new["walkforward"] = {k: desc[k] for k in ("scenario", "profile", "start_hour")}
    elif src == "copel":
        new["copel"] = {k: desc[k] for k in ("day", "start_h", "duration_min")}
    elif src == "csv":
        meta = csv_meta or {k: (dem.get("csv") or {}).get(k) for k in ("rows", "columns", "t0", "duration_total_min")}
        new["csv"] = {"blob": desc["blob"], "filename": desc["filename"], "start_min": desc["start_min"],
                      "duration_min": desc["duration_min"], **meta}
    test = {**cfg, "demand": new}
    errs = [i for i in C.errors(C.validate(test)) if i.path.startswith("demand")]
    if errs:
        for e in errs:
            st.error(e.message)
        return False
    cfg["demand"] = new
    return True


def climate_editor(cfg: dict, *, key: str, submit: str) -> bool:
    clim = cfg["climate"]
    kp = f"{key}_{token()}_"
    ck = list(C.CLIMATE_SOURCES)
    src = st.radio("Clima usado por solar/eólica", ck, index=ck.index(clim.get("source", "sintetico")), horizontal=True,
                   format_func=C.CLIMATE_SOURCES.get, key=kp + "src")
    new_blob = None
    prov = "sintetico"
    if src == "sintetico":
        st.caption("Perfil diário sintético e explícito (GHI, temperatura e vento suaves no horário real da missão). Serve para "
                   "integração/demonstração; não representa o clima medido da instalação.")
    else:
        cur = clim.get("csv") or {}
        up = st.file_uploader("CSV climático (timestamp, GHI, temperatura, vento, pressão, umidade — detecção automática da V1.6)",
                              type=["csv"], key=kp + "up")
        if up is not None:
            new_blob = (up.getvalue(), up.name)
        elif cur.get("blob"):
            st.caption(f"Arquivo armazenado: **{shell.md(cur.get('filename'))}** · SHA-256 `{cur['blob'][:12]}…`")
        pk = ["medido", "sintetico", "nao_declarado"]
        prov = st.radio("Procedência declarada", pk, index=pk.index(clim.get("provenance")) if clim.get("provenance") in pk else 2,
                        horizontal=True, format_func=C.PROVENANCE_KINDS.get, key=kp + "prov")
    if not st.button(submit, key=kp + "apply", width="stretch"):
        return False
    new = {**clim, "source": src, "provenance": prov}
    if src == "csv":
        if new_blob is not None:
            try:
                A.read_csv_bytes(new_blob[0])
            except Exception as exc:  # noqa: BLE001
                st.error(f"CSV climático ilegível: {shell.md(exc)}")
                return False
            new["csv"] = {"blob": session.store().put_blob(new_blob[0], new_blob[1], "text/csv"), "filename": new_blob[1]}
        elif not (clim.get("csv") or {}).get("blob"):
            st.error("Carregue o CSV climático ou escolha o perfil sintético.")
            return False
    cfg["climate"] = new
    return True


# ------------------------------------------------------------------ verificação técnica
def readiness_checks(cfg: dict, plan) -> tuple[str, dict]:
    """HTML da lista de verificação + contadores."""
    eqs = cfg.get("equipment", [])
    out = []
    inst = cfg["installation"]
    out.append(shell.check(f"Identificação: <b>{escape(inst.get('name') or '—')}</b>", "ok" if inst.get("name") else "bad"))
    for k, lab, opts in (("nature", "Natureza da atividade", C.NATURE_OPTIONS), ("operation_mode", "Modo operativo", C.OPERATION_MODE_OPTIONS)):
        out.append(shell.check(f"{lab}: {escape(opts.get(inst.get(k), 'não declarado'))}", "ok" if inst.get(k) else "warn"))
    out.append(shell.check(f"Inventário: {len(eqs)} equipamento(s) registrado(s)", "ok" if eqs else "warn"))
    conf = [e for e in eqs if C.is_configured(e)]
    out.append(shell.check(f"Tecnicamente configurados: {len(conf)} de {len(eqs)}", "ok" if eqs and len(conf) == len(eqs) else "warn"))
    topo = cfg["topology"]
    declared = topo["bus_kind"] != "nao_declarado" and topo["grid_connection"] != "nao_declarada"
    out.append(shell.check(f"Topologia: {escape(C.BUS_KIND_OPTIONS[topo['bus_kind']])} · {escape(C.GRID_CONNECTION_OPTIONS[topo['grid_connection']])}",
                           "ok" if declared else "warn"))
    dem = cfg["demand"]
    out.append(shell.check(f"Demanda: {escape(C.DEMAND_SOURCES[dem['source']])} · procedência: {escape(C.PROVENANCE_KINDS[dem['provenance']])}",
                           "ok" if A.demand_descriptor(dem) else "warn"))
    if plan:
        for m in plan.mappings:
            tone = {A.REPRESENTED: "ok", A.DISABLED: "off", A.INCOMPLETE: "warn", A.INCOMPATIBLE: "bad"}[m.status]
            out.append(shell.check(f"<b>{escape(m.name)}</b> ({escape(KIND_LABELS[m.kind])}) — {escape(A.STATUS_LABELS[m.status])}"
                                   f"{': ' + escape(m.reason) if m.reason else ''}", tone))
        for b in plan.blockers:
            out.append(shell.check(f"Simulação bloqueada: {escape(b)}", "bad"))
        for w in plan.warnings:
            out.append(shell.check(escape(w), "warn"))
        if plan.runnable:
            out.append(shell.check("Configuração executável no EMS existente" + (" (com exclusões que exigirão confirmação)" if plan.needs_ack else ""),
                                   "warn" if plan.needs_ack else "ok"))
    return "".join(out), {"configured": len(conf), "total": len(eqs)}
