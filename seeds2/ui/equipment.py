"""Diálogo de equipamento: Escolher tecnologia → Configurar equipamento → Confirmar registro.

O editor trabalha sobre um RASCUNHO (``draft``) guardado no estado do diálogo; nada é registrado antes da
confirmação. Três situações distintas ao salvar:

1. dados obrigatórios de REGISTRO ausentes (nome do equipamento/arranjo) → bloqueia e aponta o campo;
2. dados numéricos FISICAMENTE inválidos → bloqueia e explica o erro;
3. parâmetros de SIMULAÇÃO ausentes → permite registrar após confirmação explícita ("Salvar como pendente").
"""
from __future__ import annotations

import copy
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from seeds2.microgrid import config as C
from seeds2.microgrid.derived import PV_STC_ASSUMPTIONS, battery_derived, pv_array_nominal, pv_plant_summary
from seeds2.microgrid.modellab import ImportRejected, imported_record, parse_modellab_file
from seeds2.microgrid.references import (KIND_LABELS, KINDS, PEMFC_REF_KEY, THERMAL_PRESET_NOTE, pemfc_references,
                                         references_for, thermal_fuel_presets, wind_curve, wind_spec)

from . import forms, session, shell

DLG = "mg_dialog"
MODELLAB_URL = "https://pemfc-modelab.streamlit.app/?view=home"
TECH_CARDS = [
    {"kind": "pv", "name": "Solar fotovoltaica",
     "description": "Usina composta por arranjos: módulos do catálogo (Ns × Np) ou potência nominal declarada."},
    {"kind": "wind", "name": "Eólica",
     "description": "Aerogeradores do catálogo, com a curva de potência original e a quantidade instalada."},
    {"kind": "battery", "name": "Bateria",
     "description": "Banco registrado pelo datasheet: energia, capacidade, tensão e correntes; modelo científico opcional."},
    {"kind": "pemfc", "name": "H₂ / PEMFC",
     "description": "Perfil equivalente do SEEDS2 ou dispositivo importado do PEMFC ModelLab."},
    {"kind": "thermal", "name": "Térmica",
     "description": "Grupo gerador ou usina térmica: potências, rampa, CVU e custo de partida."},
]


def _ss():
    return st.session_state


def open_new(autosave: bool) -> None:
    _ss()[DLG] = {"type": "equipment", "id": None, "step": "pick", "autosave": autosave, "token": forms.token() + 1,
                  "draft": None}
    forms.bump()


def open_edit(eq_id: str, autosave: bool) -> None:
    eq = C.find_equipment(session.work(), eq_id)
    if eq is None:
        return
    _ss()[DLG] = {"type": "equipment", "id": eq_id, "step": "edit", "autosave": autosave, "token": forms.token() + 1,
                  "draft": copy.deepcopy(eq)}
    forms.bump()


def close() -> None:
    _ss().pop(DLG, None)


def _start_kind(kind: str) -> None:
    dlg = _ss().get(DLG)
    if not dlg or kind not in KINDS:
        return
    draft = C.new_equipment(kind, "")
    if kind == "pv":
        draft["arrays"] = [C.new_array("Arranjo 01")]
    dlg.update(step="edit", draft=draft, kind=kind)


def _on_pick() -> None:
    a = shell.payload(f"seeds_tech_{(_ss().get(DLG) or {}).get('token')}")
    if a and a.get("type") == "pick":
        _start_kind(a.get("kind"))


# ------------------------------------------------------------------ widgets genéricos de parâmetro
def param_widget(kind: str, spec: C.ParamSpec, value: Any, k: str):
    unit = f" [{spec.unit}]" if spec.unit else ""
    label = f"{spec.label}{unit}{' *' if spec.required else ''}"
    if spec.type == "choice":
        opts = C.choices(kind, spec.name)
        keys = list(opts)
        return st.selectbox(label, keys, index=keys.index(value) if value in keys else None, format_func=lambda x: opts.get(x, x),
                            placeholder="— não declarado —", key=k, help=spec.help or None)
    if spec.type == "bool":
        return st.toggle(label.replace(" *", ""), value=bool(value) if value is not None else bool(spec.default), key=k,
                         help=spec.help or None)
    if spec.type == "text":
        v = st.text_input(label.replace(" *", ""), value=value or "", key=k, help=spec.help or None, max_chars=500)
        return v.strip() or None
    if spec.type == "int":
        v = st.number_input(label, min_value=int(spec.min) if spec.min is not None and not spec.min_exclusive else None,
                            value=int(value) if value is not None else None, step=1, format="%d", key=k,
                            placeholder="não declarado", help=spec.help or None)
        return int(v) if v is not None else None
    return st.number_input(label, min_value=float(spec.min) if spec.min is not None and not spec.min_exclusive else None,
                           max_value=float(spec.max) if spec.max is not None and not spec.max_exclusive else None,
                           value=float(value) if value is not None else None, step=None, format="%.4g", key=k,
                           placeholder="não declarado", help=spec.help or None)


def _params(kind: str, draft: dict, kp: str, names: list[str], cols: int = 2) -> None:
    specs = [C.PARAM_INDEX[kind][n] for n in names]
    columns = st.columns(cols)
    for i, spec in enumerate(specs):
        with columns[i % cols]:
            draft["params"][spec.name] = param_widget(kind, spec, draft["params"].get(spec.name), f"{kp}p_{spec.name}")


def _table(rows: list[tuple[str, str]], title: str = "") -> None:
    body = "".join(f"<tr><td style='opacity:.75;padding:2px 14px 2px 0'>{escape(k)}</td><td><b>{escape(v)}</b></td></tr>"
                   for k, v in rows if v not in (None, ""))
    st.html(f"<div class='sd-callout'>{f'<div class=sd-eyebrow>{escape(title)}</div>' if title else ''}"
            f"<table style='font-size:.84rem;border-collapse:collapse'>{body}</table></div>")


# ------------------------------------------------------------------ Solar: usina → arranjos
def _pv_editor(draft: dict, kp: str) -> None:
    top = st.container()
    arrays: list[dict] = draft.setdefault("arrays", [])
    refs = C.choices("pv_array", "reference")
    ref_keys = list(refs)
    remove: str | None = None
    for i, arr in enumerate(arrays):
        ak = f"{kp}arr_{arr['id']}_"
        with st.container(border=True, key=f"{ak}card"):
            h1, h2 = st.columns([3, 1], vertical_alignment="bottom")
            arr["name"] = h1.text_input("Nome do arranjo *", value=arr.get("name", ""), key=ak + "name").strip()
            if h2.button("Retirar arranjo", key=ak + "rm", width="stretch"):
                remove = arr["id"]
            mode = st.radio("Forma de cadastro", list(C.PV_ARRAY_MODES), index=list(C.PV_ARRAY_MODES).index(arr.get("mode", "modulo")),
                            format_func=C.PV_ARRAY_MODES.get, horizontal=True, key=ak + "mode")
            arr["mode"] = mode
            if mode == "modulo":
                c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1])
                arr["reference"] = c1.selectbox("Módulo FV (referência) *", ref_keys,
                                                index=ref_keys.index(arr["reference"]) if arr.get("reference") in ref_keys else None,
                                                format_func=refs.get, placeholder="— não declarado —", key=ak + "ref")
                ns = c2.number_input("Módulos em série *", min_value=1, value=arr.get("n_series"), step=1, format="%d",
                                     placeholder="—", key=ak + "ns")
                np_ = c3.number_input("Strings em paralelo *", min_value=1, value=arr.get("n_parallel"), step=1, format="%d",
                                      placeholder="—", key=ak + "np")
                arr["n_series"] = int(ns) if ns is not None else None
                arr["n_parallel"] = int(np_) if np_ is not None else None
                soil = c4.number_input("Perdas por sujeira [%]", min_value=0.0, max_value=99.9,
                                       value=float(arr.get("soiling_pct") if arr.get("soiling_pct") is not None else 0.0),
                                       format="%.4g", key=ak + "soil",
                                       help="0 % = hipótese de perdas por sujeira não consideradas (não é medição de limpeza).")
                if soil != (arr.get("soiling_pct") or 0.0):
                    arr["soiling_default"] = False
                arr["soiling_pct"] = float(soil)
                nom = pv_array_nominal(arr)
                if nom:
                    shell.kpis([("P STC", forms.fmt(nom["P_STC_kW"], 2, "kWp"), f"{nom['n_modules']} módulos"),
                                ("Voc", forms.fmt(nom["Voc_V"], 1, "V"), "Voc_mód × Ns"),
                                ("Isc", forms.fmt(nom["Isc_A"], 2, "A"), "Isc_mód × Np"),
                                ("Vmp", forms.fmt(nom["Vmp_V"], 1, "V"), "Vmp_mód × Ns"),
                                ("Imp", forms.fmt(nom["Imp_A"], 2, "A"), "Imp_mód × Np")])
                    st.caption(PV_STC_ASSUMPTIONS)
                else:
                    st.caption("Informe módulo, Ns e Np para calcular os valores nominais teóricos em STC.")
                if arr.get("soiling_default"):
                    st.caption("Sujeira: 0 % aplicado como **valor padrão** (hipótese de perdas não consideradas).")
            else:
                c1, c2 = st.columns([1, 2])
                v = c1.number_input("Potência nominal declarada [kWp] *", min_value=0.0, value=arr.get("declared_kWp"),
                                    format="%.4g", placeholder="—", key=ak + "kwp")
                arr["declared_kWp"] = float(v) if v else None
                src = c2.text_input("Procedência (placa, projeto, as-built…)", value=arr.get("declared_source") or "",
                                    key=ak + "src", max_chars=300)
                arr["declared_source"] = src.strip() or None
                st.caption("Registro descritivo válido para o inventário e relatórios. Sem módulo identificado, o modelo FV "
                           "existente não pode simular este arranjo; nenhum módulo, Ns/Np ou parâmetro elétrico é inventado.")
            arr["notes"] = st.text_input("Observações do arranjo", value=arr.get("notes", ""), key=ak + "notes", max_chars=500)
    if remove:
        draft["arrays"] = [a for a in arrays if a["id"] != remove]
        st.rerun()
    if st.button("＋ Adicionar arranjo", key=f"{kp}addarr", type="secondary"):
        draft["arrays"].append(C.new_array(f"Arranjo {len(arrays) + 1:02d}"))
        st.rerun()
    s = pv_plant_summary(draft)
    with top:
        shell.kpis([("Potência total registrada", forms.fmt(s["total_kWp"], 2, "kWp"),
                     f"{s['n_computed']} calculado(s) · {s['n_declared']} declarado(s)"),
                    ("Calculada por datasheet", forms.fmt(s["computed_kWp"], 2, "kWp"), "Σ P_STC dos arranjos"),
                    ("Declarada", forms.fmt(s["declared_kWp"], 2, "kWp"), "sem módulo identificado"),
                    ("Arranjos", str(s["n_arrays"]), f"{s['n_modules']} módulo(s) identificados")])
        if s["unknown_arrays"]:
            st.caption("Arranjos ainda sem potência calculável: " + shell.md(", ".join(s["unknown_arrays"])))
        st.caption("A usina soma apenas potências nominais. Tensões e correntes (Voc, Isc, Vmp, Imp) pertencem a cada "
                   "arranjo e não são somadas entre arranjos diferentes.")


# ------------------------------------------------------------------ Eólica: curva do catálogo
def _wind_editor(draft: dict, kp: str) -> None:
    _params("wind", draft, kp, ["reference", "count"])
    draft["params"]["apply_grid_loss"] = param_widget("wind", C.PARAM_INDEX["wind"]["apply_grid_loss"],
                                                       draft["params"].get("apply_grid_loss"), f"{kp}p_apply_grid_loss")
    key = draft["params"].get("reference")
    if not key:
        st.caption("Selecione um aerogerador do catálogo para ver sua curva de potência.")
        return
    curve = wind_curve(key)
    spec = wind_spec(key)
    hub = spec.get("hub_height_m") or ", ".join(f"{h:g}" for h in spec.get("hub_height_options_m") or []) or None
    _table([("Fabricante e modelo", f"{spec.get('manufacturer', '')} {spec.get('model', '')}".strip()),
            ("Potência nominal / referência", forms.fmt(spec.get("rated_power_kw"), 2, "kW")),
            ("Pico documentado da curva", forms.fmt(spec.get("curve_peak_power_kw", max(p for _, p in curve["points"]) if curve else None), 3, "kW")),
            ("Diâmetro do rotor", forms.fmt(spec.get("rotor_diameter_m"), 1, "m")),
            ("Altura do cubo", f"{hub} m" if hub else "não informada no catálogo"),
            ("Classe IEC", spec.get("wind_class_iec") or "não informada"),
            ("Partida / nominal / corte", " / ".join(forms.fmt(spec.get(k), 1, "m/s") if spec.get(k) else "—"
                                                    for k in ("cut_in_mps", "rated_wind_speed_mps", "cut_out_mps"))),
            ("Regulação", spec.get("power_regulation") or "não informada"),
            ("Densidade de referência", forms.fmt(spec.get("reference_air_density_kg_m3"), 3, "kg/m³"))],
           "Aerogerador do catálogo")
    if curve is None:
        st.info("Este aerogerador não possui curva de potência utilizável no catálogo. Nenhuma curva é gerada.")
        return
    if curve.get("integration_limitation"):
        st.warning(curve["integration_limitation"])
    if curve.get("curve_valid_wind_range_mps"):
        st.caption(f"Domínio válido [m/s]: {curve['curve_valid_wind_range_mps']} · referência: {spec.get('power_rating_basis')}")
    import plotly.graph_objects as go

    v = [p[0] for p in curve["points"]]
    pw = [p[1] for p in curve["points"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=v, y=pw, mode="lines", name="Interpolação linear (apenas visual)",
                             line=dict(dash="dot", width=1.6, color="#2F6FED"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=v, y=pw, mode="markers", name="Pontos tabulados do catálogo",
                             marker=dict(size=7, color="#0E7C86", line=dict(width=1, color="white")),
                             hovertemplate="%{x:.1f} m/s → %{y:,.3f} kW<extra></extra>"))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=36, b=10), hovermode="closest",
                      title=dict(text=f"Curva de potência · {key}", font=dict(size=14)),
                      xaxis=dict(title="Velocidade do vento [m/s]", zeroline=False),
                      yaxis=dict(title="Potência elétrica [kW]", rangemode="tozero"),
                      legend=dict(orientation="h", y=-0.25), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch", key=f"{kp}curve_{key}")
    (st.warning if curve["digitized"] else st.success)(
        f"{curve['source_label']}. Fonte: {shell.md(curve.get('reference') or '—')} "
        f"({shell.md(curve.get('document') or '—')}). Densidade de referência {forms.fmt(curve['reference_density_kg_m3'], 3, 'kg/m³')}.")


# ------------------------------------------------------------------ Bateria: datasheet primeiro
def _battery_editor(draft: dict, kp: str) -> None:
    p = draft["params"]
    st.markdown("**Dados do banco (datasheet)** — informe apenas o que é conhecido.")
    _params("battery", draft, kp, ["manufacturer", "model", "chemistry"], cols=3)
    _params("battery", draft, kp, ["energy_kWh", "capacity_Ah", "voltage_V", "power_kW"], cols=4)
    _params("battery", draft, kp, ["i_charge_max_A", "i_discharge_max_A", "c_charge_max", "c_discharge_max"], cols=4)
    d = battery_derived(p, C.battery_model_energy_kWh(draft))
    rows = []
    for key, label, unit, nd in (("energy_kWh", "Energia nominal", "kWh", 2), ("capacity_Ah", "Capacidade nominal", "Ah", 1),
                                 ("voltage_V", "Tensão nominal", "V", 1), ("c_charge", "Taxa máx. de carga", "C", 3),
                                 ("c_discharge", "Taxa máx. de descarga", "C", 3), ("i_charge_A", "Corrente máx. de carga", "A", 1),
                                 ("i_discharge_A", "Corrente máx. de descarga", "A", 1)):
        val, basis, how = d[key]
        if basis == "derivada":
            rows.append((label, f"{forms.fmt(val, nd, unit)} — estimativa ({how})"))
    if rows:
        _table(rows, "Grandezas derivadas (estimativas a partir dos dados declarados)")
    for w in d["warnings"]:
        st.warning(shell.md(w))
    st.markdown("**Limites operacionais de SOC**")
    _params("battery", draft, kp, ["soc_min_pct", "soc_max_pct", "soc_limits_source"], cols=3)
    if p.get("soc_limits_source") == "sugerido":
        st.caption("20 % / 80 % são valores iniciais SUGERIDOS para configuração operacional, não limites universais do "
                   "fabricante. Se houver limites documentados para o equipamento, informe-os e altere a origem.")
    st.caption("O SOC inicial não faz parte do inventário: é uma condição de cada rodada (Simulação → Condições da rodada).")
    with st.expander("Configuração avançada do modelo científico", expanded=C.battery_model_parametrized(draft)):
        st.caption("Parametrização do modelo existente (models/battery_model.py). Necessária apenas para simular o banco "
                   "com o modelo eletroquímico atual; não descreve o produto comercial.")
        _params("battery", draft, kp, ["model_reference", "model_n_series", "model_n_parallel"], cols=3)
        e = C.battery_model_energy_kWh(draft)
        if e is not None:
            st.caption(f"Energia da parametrização do modelo: **{forms.fmt(e, 2, 'kWh')}** (V·Q da célula × Ns × Np).")
    reg, par = C.battery_physically_registered(draft), C.battery_model_parametrized(draft)
    st.html(shell.check("Banco registrado fisicamente (datasheet)" if reg else "Sem grandezas nominais do datasheet declaradas",
                        "ok" if reg else "warn")
            + shell.check("Parametrizado para o modelo científico existente" if par else
                          "Não parametrizado para o modelo científico (não simulável até completar a seção avançada)",
                          "ok" if par else "warn"))


# ------------------------------------------------------------------ PEMFC: catálogo + ModelLab
def _pemfc_editor(draft: dict, kp: str, dlg: dict) -> None:
    p = draft["params"]
    opts = C.choices("pemfc", "reference")
    choice = st.radio("Origem do dispositivo", list(opts), index=list(opts).index(p.get("reference") or PEMFC_REF_KEY),
                      format_func=opts.get, key=kp + "src", horizontal=True)
    p["reference"] = choice
    if choice == PEMFC_REF_KEY:
        r = pemfc_references()[PEMFC_REF_KEY]
        _table([("Perfil", r.label), ("Categoria", r.category), ("Procedência", r.provenance)], "Catálogo SEEDS2")
        st.caption("Aproximação de modelo físico parametrizado — NÃO é um equipamento validado experimentalmente.")
    else:
        imp = draft.get("imported") or dlg.get("import_info")
        up = st.file_uploader("IMPORTAR DISPOSITIVO DO PEMFC MODELLAB (.pmldevice.zip ou profile.json)", type=["zip", "json"],
                              key=kp + "up")
        if up is not None:
            data = up.getvalue()
            try:
                info = parse_modellab_file(data, up.name)
            except ImportRejected as exc:
                st.error(shell.md(exc))
                dlg.pop("import_info", None)
                dlg.pop("import_bytes", None)
            else:
                if dlg.get("import_info", {}).get("sha256") != info["sha256"]:
                    dlg["import_info"], dlg["import_bytes"] = info, data
                imp = info
        if imp:
            dev = imp["device"]
            _table([("Dispositivo", dev.get("name")), ("Fabricante", dev.get("manufacturer") or "não declarado"),
                    ("Modelo", dev.get("model") or "não declarado"), ("Identificação no ModelLab", dev.get("id") or "—"),
                    ("Células", f"{dev['n_cells']} ({dev.get('n_cells_origin') or 'origem não declarada'})" if dev.get("n_cells") else "não declarado"),
                    ("Área ativa", f"{forms.fmt(dev.get('active_area_cm2'), 1, 'cm²')} ({dev.get('active_area_origin') or '—'})" if dev.get("active_area_cm2") else "não declarada"),
                    ("Potência nominal", forms.fmt(dev["rated_power_W"] / 1000.0, 2, "kW") if dev.get("rated_power_W") else "não declarada"),
                    ("Arquivo", f"{imp.get('filename')} · ModelLab {imp['source'].get('app_version') or '?'}"),
                    ("Procedência", dev.get("provenance") or "não declarada")], "Dispositivo do PEMFC ModelLab")
            cals = imp.get("calibrations") or []
            if cals:
                st.dataframe(pd.DataFrame([{
                    "Perfil": c["profile_id"], "Estado": c["status_label"], "Validação": c["validation_label"],
                    "RMSE [mV/célula]": round(c["rmse_V"] * 1000, 2) if c.get("rmse_V") is not None else None,
                    "T calibrada [K]": "–".join(f"{x:g}" for x in c["domain"]["temperature_K"]) if c["domain"]["temperature_K"] else "—",
                    "Ativo": "sim" if c["id"] and c["id"] == imp.get("active_calibration_id") else ""} for c in cals]),
                    hide_index=True, width="stretch")
            else:
                st.caption("O pacote não contém calibrações.")
            shell.callout(escape(imp["integration_note"]), "warn")
        st.link_button("CRIAR DISPOSITIVO NO PEMFC MODELLAB ↗", MODELLAB_URL, width="stretch")
        st.caption("Abre o PEMFC ModelLab em nova aba. O dispositivo é configurado e calibrado lá e depois importado aqui "
                   "pelo pacote .pmldevice.zip exportado. Não há sincronização automática entre as aplicações.")
    _params("pemfc", draft, kp, ["quantity", "power_basis"])


# ------------------------------------------------------------------ diálogo
def _registration_errors(draft: dict) -> list[str]:
    out = []
    if not str(draft.get("name") or "").strip():
        out.append("Informe o nome do equipamento.")
    for a in draft.get("arrays") or []:
        if not str(a.get("name") or "").strip():
            out.append("Todos os arranjos precisam de nome.")
            break
    return out


def _commit(dlg: dict, draft: dict) -> None:
    cfg = session.work()
    if draft["kind"] == "pemfc" and draft["params"].get("reference") == C.PEMFC_IMPORT_REF and dlg.get("import_bytes"):
        info = dlg["import_info"]
        h = session.store().put_blob(dlg["import_bytes"], info["filename"], "application/zip"
                                     if info["format"] == "pmldevice" else "application/json")
        draft["imported"] = imported_record(info, h, C.utc_now())
    if draft["kind"] == "pemfc" and draft["params"].get("reference") != C.PEMFC_IMPORT_REF:
        draft["imported"] = draft.get("imported") if dlg.get("id") else None
    if dlg.get("id") is None:
        C.add_equipment(cfg, draft)
        note = f"Equipamento adicionado: {draft['name']}"
    else:
        extra = {k: draft[k] for k in ("arrays", "imported") if k in draft}
        C.update_equipment(cfg, dlg["id"], name=draft["name"], tag=draft.get("tag", ""), serial=draft.get("serial", ""),
                           enabled=draft["enabled"], notes=draft.get("notes", ""), params=draft["params"], **extra)
        note = f"Equipamento alterado: {draft['name']}"
    close()
    forms.after_change(bool(dlg.get("autosave")), note, "commissioning" if dlg.get("autosave") else "edit")


@st.dialog("Equipamento da microrrede", width="large", on_dismiss=close)
def dialog() -> None:
    dlg = _ss().get(DLG) or {}
    t = dlg.get("token", 0)
    if dlg.get("step") == "pick":
        st.markdown("**Escolher tecnologia** — selecione o tipo de equipamento a registrar.")
        shell.component("techpicker")(key=f"seeds_tech_{t}", data={"cards": TECH_CARDS}, on_action_change=_on_pick)
        if st.button("Cancelar", key=f"eqd_{t}_cancel_pick"):
            close()
            st.rerun()
        return
    draft = dlg.get("draft")
    if draft is None:
        close()
        return
    kp = f"eqd_{t}_"
    kind = draft["kind"]
    if dlg.get("step") == "confirm":
        st.markdown("### Equipamento com configuração pendente")
        st.markdown("O equipamento pode ser registrado, mas ainda faltam parâmetros para utilizá-lo na simulação:")
        st.html("".join(shell.check(escape(m), "warn") for m in dlg.get("missing", [])))
        st.markdown("Deseja salvar agora e completar a configuração posteriormente?")
        c1, c2 = st.columns(2)
        if c1.button("Salvar como pendente", type="primary", width="stretch", key=kp + "save_pending"):
            _commit(dlg, draft)
        if c2.button("Voltar à configuração", width="stretch", key=kp + "back_cfg"):
            dlg["step"] = "edit"
            st.rerun()
        return
    head = f"<div class='sd-eyebrow'>{escape(KIND_LABELS[kind])}</div>"
    if dlg.get("id"):
        head += (f"<div class='sd-mono' style='opacity:.75'>Identificador estável: {escape(draft['id'])} · criado "
                 f"{escape(shell.fmt_time(draft.get('created_at')))} · alterado {escape(shell.fmt_time(draft.get('updated_at')))}</div>")
    st.html(head)
    if dlg.get("id") is None and st.button("← Voltar às tecnologias", key=kp + "back_tech"):
        dlg.update(step="pick", draft=None)
        dlg.pop("import_info", None)
        dlg.pop("import_bytes", None)
        st.rerun()
    c1, c2 = st.columns([2, 1])
    draft["name"] = c1.text_input("Nome do equipamento *", value=draft.get("name", ""), key=kp + "name",
                                  placeholder={"pv": "p. ex. Usina fotovoltaica cobertura"}.get(kind, "p. ex. Banco de baterias 01")).strip()
    draft["tag"] = c2.text_input("TAG / código técnico", value=draft.get("tag", ""), key=kp + "tag").strip()
    c3, c4 = st.columns([2, 1])
    draft["serial"] = c3.text_input("Nº de série / identificação física", value=draft.get("serial", ""), key=kp + "serial").strip()
    draft["enabled"] = c4.toggle("Habilitado", value=bool(draft.get("enabled", True)), key=kp + "enabled",
                                 help="Desabilitado: permanece no inventário, mas não entra em simulações.")
    st.markdown("**Configuração técnica**")
    if kind == "pv":
        _pv_editor(draft, kp)
    elif kind == "wind":
        _wind_editor(draft, kp)
    elif kind == "battery":
        _battery_editor(draft, kp)
    elif kind == "pemfc":
        _pemfc_editor(draft, kp, dlg)
    else:
        _params("thermal", draft, kp, [s.name for s in C.PARAM_SPECS["thermal"]])
        fp = draft["params"].get("fuel_preset")
        if fp:
            pr = thermal_fuel_presets()[fp]
            st.caption(f"Preset ACADÊMICO «{fp}»: CVU de referência {forms.fmt(pr['cvu_rs_mwh'], 0, 'R$/MWh')} — {pr['note']} "
                       "O CVU acima só é alterado se você digitá-lo.")
        st.caption(THERMAL_PRESET_NOTE)
    draft["notes"] = st.text_area("Observações", value=draft.get("notes", ""), key=kp + "notes", height=68)
    probe = copy.deepcopy(draft)
    if kind == "pemfc" and probe["params"].get("reference") == C.PEMFC_IMPORT_REF and not probe.get("imported") and dlg.get("import_info"):
        probe["imported"] = imported_record(dlg["import_info"], "0" * 64, C.utc_now())
    probe["name"] = probe["name"] or "—"
    issues = C.errors(C.equipment_issues(probe))
    for i in issues:
        st.error(shell.md(i.message))
    missing = C.missing_required(probe)
    if missing and not issues:
        st.info("Registrável, mas ainda **não tecnicamente configurado** para a simulação — faltam: "
                + shell.md(", ".join(missing)))
    b1, b2 = st.columns(2)
    save = b1.button("Salvar equipamento", type="primary", width="stretch", key=kp + "apply")
    if b2.button("Cancelar", width="stretch", key=kp + "cancel"):
        close()
        st.rerun()
    if save:
        reg = _registration_errors(draft)
        if reg:
            for r in reg:
                st.error(r)
        elif issues:
            st.error("Corrija os dados fisicamente inválidos acima antes de salvar.")
        elif missing:
            dlg.update(step="confirm", missing=missing)
            st.rerun()
        else:
            _commit(dlg, draft)
    if dlg.get("id"):
        with st.expander("Retirar este equipamento do inventário"):
            st.caption("O equipamento sai do inventário ativo e deixa de participar de simulações. O registro permanece em "
                       "'Equipamentos retirados' e nas revisões anteriores (auditoria).")
            reason = st.text_input("Motivo da retirada", key=kp + "ret_reason", placeholder="p. ex. desmontado para manutenção")
            confirm = st.checkbox(f"Confirmo a retirada de «{shell.md(draft['name'])}»", key=kp + "ret_ok")
            if st.button("Retirar equipamento", key=kp + "retire", disabled=not confirm):
                C.retire_equipment(session.work(), dlg["id"], reason)
                close()
                forms.after_change(bool(dlg.get("autosave")), f"Equipamento retirado: {draft['name']}",
                                   "commissioning" if dlg.get("autosave") else "edit")


def maybe_dialog() -> None:
    dlg = _ss().get(DLG)
    if dlg and dlg.get("type") == "equipment":
        dialog()
