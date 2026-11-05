"""Editores reutilizados pelo comissionamento e pela Gestão da Microrrede.

Regras: nenhum valor físico é pré-preenchido (campos vazios = "não declarado"); toda grandeza mostra
unidade; referências exibem a procedência do catálogo; alterações vão para a cópia de trabalho e são
salvas imediatamente (``autosave``, comissionamento) ou ficam pendentes até "Salvar" (Gestão).
O editor de equipamentos (catálogo de tecnologias e editores por tecnologia) está em ``equipment.py``.
"""
from __future__ import annotations

from functools import partial
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from seeds2.microgrid import adapter as A
from seeds2.microgrid import config as C
from seeds2.microgrid.derived import battery_derived, pv_plant_summary
from seeds2.microgrid.references import KIND_LABELS, KINDS, references_for

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
    p = eq.get("params") or {}
    k = eq["kind"]
    if k == "thermal":
        dyn = p.get("dynamic")
        return C.choices("thermal", "dynamic").get(dyn) if dyn else None
    if k == "pv":
        refs = {a.get("reference") for a in eq.get("arrays") or [] if a.get("mode") == "modulo" and a.get("reference")}
        n = len(eq.get("arrays") or [])
        return f"{n} arranjo(s) · {len(refs)} modelo(s) de módulo" if n else None
    if k == "battery":
        txt = " ".join(x for x in (p.get("manufacturer"), p.get("model")) if x)
        chem = C.BATTERY_CHEMISTRIES.get(p.get("chemistry"))
        return " · ".join(x for x in (txt, chem) if x) or None
    if k == "pemfc":
        if p.get("reference") == C.PEMFC_IMPORT_REF:
            dev = (eq.get("imported") or {}).get("device") or {}
            return f"ModelLab · {dev.get('name') or 'dispositivo importado'}"
        return "Perfil equivalente SEEDS2 (aproximado)" if p.get("reference") else None
    ref = p.get("reference")
    r = references_for(k).get(ref) if ref else None
    return r.label if r else ref


def facts(eq: dict) -> list[tuple[str, str]]:
    p = eq.get("params") or {}
    k = eq["kind"]
    if k == "pv":
        s = pv_plant_summary(eq)
        return [("Potência registrada", fmt(s["total_kWp"], 2, "kWp") if (s["n_computed"] or s["n_declared"]) else "—"),
                ("Arranjos", str(s["n_arrays"])), ("Calculada", fmt(s["computed_kWp"], 2, "kWp")),
                ("Declarada", fmt(s["declared_kWp"], 2, "kWp"))]
    if k == "wind":
        return [("Potência nominal", fmt(C.installed_power_kW(eq), 0, "kW")), ("Quantidade", str(p.get("count") or "—")),
                ("Perda genérica", "sim" if p.get("apply_grid_loss") else "não"), ("", "")]
    if k == "battery":
        d = battery_derived(p)
        e, basis, _ = d["energy_kWh"]
        me = C.battery_model_energy_kWh(eq)
        return [("Energia nominal", f"{fmt(e, 1, 'kWh')}{' (estim.)' if basis == 'derivada' else ''}" if e is not None else
                 (f"{fmt(me, 1, 'kWh')} (modelo)" if me is not None else "—")),
                ("Tensão nominal", fmt(d["voltage_V"][0], 0, "V")),
                ("SOC mín/máx", f"{fmt(p.get('soc_min_pct'), 0)} / {fmt(p.get('soc_max_pct'), 0)} %"),
                ("Carga/descarga", f"{fmt(d['c_charge'][0], 2)} / {fmt(d['c_discharge'][0], 2)} C")]
    if k == "pemfc":
        return [("Potência líquida máx.", fmt(C.installed_power_kW(eq), 1, "kW")), ("Sistemas", str(p.get("quantity") or "—")),
                ("Base no EMS", C.PEMFC_POWER_BASIS.get(p.get("power_basis"), "—")), ("", "")]
    return [("Potência máx.", fmt(p.get("pmax_kW"), 1, "kW")), ("Mín. técnica", fmt(p.get("pmin_kW"), 1, "kW")),
            ("CVU", fmt(p.get("cvu_rs_MWh"), 0, "R$/MWh")), ("Rampa", fmt(p.get("ramp_kW_min"), 1, "kW/min") if p.get("ramp_kW_min") else "sem limite")]


def _sim_badge(ms: list) -> tuple[dict | None, str, str]:
    """Estado agregado de simulação de um equipamento (FV: por arranjo)."""
    if not ms:
        return None, "", ""
    st_ = {m.status for m in ms}
    if st_ == {A.REPRESENTED}:
        return {"tone": "ok", "text": "Compatível com a simulação"}, ms[0].reason or "", ""
    if A.REPRESENTED in st_:
        out = [m for m in ms if m.status != A.REPRESENTED]
        return ({"tone": "warn", "text": f"Parcialmente simulável ({len(ms) - len(out)}/{len(ms)} arranjos)"},
                "Fora da rodada: " + "; ".join(f"{m.name.split(' · ')[-1]}: {m.reason}" for m in out), "warn")
    bad = [m for m in ms if m.status == A.INCOMPATIBLE]
    if bad:
        return {"tone": "bad", "text": "Não representável no EMS", "title": bad[0].reason}, bad[0].reason, "bad"
    return None, "", ""


def card_data(cfg: dict, plan) -> dict:
    items = []
    for eq in cfg.get("equipment", []):
        missing = C.missing_required(eq)
        errs = C.errors(C.equipment_issues(eq))
        ms = plan.for_equipment(eq["id"]) if plan else []
        badges = []
        if not eq.get("enabled", True):
            badges.append({"tone": "off", "text": "Desabilitado"})
        if eq["kind"] == "battery":
            badges.append({"tone": "ok", "text": "Registrado fisicamente"} if C.battery_physically_registered(eq) else
                          {"tone": "warn", "text": "Sem dados de datasheet"})
            badges.append({"tone": "ok", "text": "Parametrizado (modelo)"} if C.battery_model_parametrized(eq) else
                          {"tone": "off", "text": "Sem parametrização do modelo"})
        badges.append({"tone": "ok", "text": "Configurado"} if not missing and not errs else
                      {"tone": "warn", "text": f"Pendente: {len(missing)} item(ns)" if missing else "Dados inválidos",
                       "title": ", ".join(missing)})
        sim, reason, tone = _sim_badge(ms)
        if sim:
            badges.append(sim)
        if not reason and missing and eq.get("enabled", True):
            reason, tone = "Obrigatório para simular: " + ", ".join(missing), "warn"
        elif not reason and any(m.status == A.INCOMPLETE for m in ms):
            reason, tone = next(m.reason for m in ms if m.status == A.INCOMPLETE), "warn"
        status = ms[0].status if len({m.status for m in ms}) == 1 and ms else (A.INCOMPLETE if ms else "")
        items.append({"id": eq["id"], "kind": eq["kind"], "kind_label": KIND_LABELS[eq["kind"]], "name": eq["name"],
                      "tag": eq.get("tag", ""), "enabled": bool(eq.get("enabled", True)), "reference_label": ref_label(eq),
                      "badges": badges, "facts": [f for f in facts(eq) if f[0]], "reason": reason, "reason_tone": tone,
                      "sim_status": status})
    return {"items": items, "kinds": [[k, KIND_LABELS[k]] for k in KINDS],
            "states": [[k, v] for k, v in A.STATUS_LABELS.items()]}


# ------------------------------------------------------------------ inventário
def _on_inventory() -> None:
    from . import equipment

    a = shell.payload("seeds_inventory")
    if not a:
        return
    autosave = bool(st.session_state.get("mg_inventory_autosave"))
    if a.get("type") == "open" and session.work() and C.find_equipment(session.work(), a.get("id", "")):
        equipment.open_edit(a["id"], autosave)
    elif a.get("type") == "add":
        equipment.open_new(autosave)


def inventory(cfg: dict, plan, *, autosave: bool, key: str = "inv") -> None:
    from . import equipment

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
            equipment.open_new(autosave)
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
                equipment.open_edit(sel, autosave)
                st.rerun()
    retired = cfg.get("retired") or []
    if retired:
        with st.expander(f"Equipamentos retirados ({len(retired)}) — registro de auditoria"):
            st.dataframe(pd.DataFrame([{"Equipamento": r["name"], "Tecnologia": KIND_LABELS[r["kind"]], "Identificador": r["id"],
                                        "Retirado em": shell.fmt_time(r.get("retired_at")), "Motivo": r.get("retired_reason") or "—"}
                                       for r in retired]), hide_index=True, width="stretch")
    equipment.maybe_dialog()


# ------------------------------------------------------------------ identificação e localização (2 cartões)
GEO_TONES = {"ok": "ok", "denied": "bad", "unavailable": "warn", "timeout": "warn", "unsupported": "warn", "insecure": "warn"}
GEO_MESSAGES = {
    "unsupported": "Este navegador não oferece geolocalização. Informe as coordenadas manualmente.",
    "insecure": "A geolocalização do navegador exige HTTPS ou acesso local (localhost). Informe as coordenadas manualmente.",
    "denied": "Permissão de localização negada pelo navegador. Autorize-a nas configurações do site ou informe os dados manualmente.",
    "unavailable": "O navegador não conseguiu determinar a posição. Informe as coordenadas manualmente.",
    "timeout": "O navegador não respondeu a tempo. Tente novamente ou informe as coordenadas manualmente.",
}


def geo_result(payload: Any) -> dict:
    """Interpreta o retorno do componente de geolocalização (função pura, testável).

    Devolve ``{"ok", "lat", "lon", "accuracy_m", "tz_suggested", "tone", "message"}``. Coordenadas fora do
    domínio físico são rejeitadas. Cidade/estado/endereço NUNCA são inferidos das coordenadas."""
    if not isinstance(payload, dict) or payload.get("type") != "geo":
        return {"ok": False, "tone": "warn", "message": GEO_MESSAGES["unavailable"]}
    tz = payload.get("tz") if isinstance(payload.get("tz"), str) else ""
    if not payload.get("ok"):
        code = payload.get("code") if payload.get("code") in GEO_MESSAGES else "unavailable"
        return {"ok": False, "tone": GEO_TONES[code], "message": GEO_MESSAGES[code], "tz_suggested": tz[:60]}
    lat, lon, acc = payload.get("lat"), payload.get("lon"), payload.get("accuracy")
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    if not (num(lat) and num(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        return {"ok": False, "tone": "warn", "message": GEO_MESSAGES["unavailable"], "tz_suggested": tz[:60]}
    acc = float(acc) if num(acc) and acc >= 0 else None
    msg = "Coordenadas recebidas do navegador" + (f" (precisão estimada ±{acc:.0f} m)" if acc is not None else "") + \
          ". Revise e confirme para salvar."
    return {"ok": True, "lat": round(float(lat), 6), "lon": round(float(lon), 6), "accuracy_m": acc,
            "tz_suggested": tz[:60], "tone": "ok", "message": msg}


def _keys(key: str) -> dict:
    t = token()
    return {f: f"{key}_{f}_{t}" for f in ("name", "desc", "nature", "mode", "country", "region", "city", "address",
                                          "lat", "lon", "tz")}


def _on_geo(key: str) -> None:
    k = _keys(key)
    r = geo_result(shell.payload(f"seeds_geo_{key}"))
    ss = st.session_state
    ss[f"{key}_geo_msg"] = (r["tone"], r["message"])
    ss[f"{key}_geo_tz"] = r.get("tz_suggested") or ""
    if r["ok"]:
        ss[k["lat"]], ss[k["lon"]] = r["lat"], r["lon"]
        ss[f"{key}_geo_meta"] = {"lat": r["lat"], "lon": r["lon"], "accuracy_m": r["accuracy_m"], "captured_at": C.utc_now()}


def _init(k: str, value: Any) -> None:
    if k not in st.session_state:
        st.session_state[k] = value


def identification_cards(cfg: dict, *, key: str) -> None:
    """Desenha os dois cartões (sem salvar). Os valores ficam nos widgets até ``apply_identification``."""
    inst = cfg["installation"]
    loc = inst.get("location") or C.new_location()
    k = _keys(key)
    # Somente os campos que a geolocalização pode preencher são inicializados via session_state (o callback do
    # componente escreve neles antes do desenho); os demais recebem o valor inicial pelo parâmetro do widget.
    for f, v in (("lat", loc.get("latitude")), ("lon", loc.get("longitude")), ("tz", loc.get("timezone", ""))):
        _init(k[f], v)
    c1, c2 = st.columns(2, gap="large")
    with c1, st.container(border=True, key=f"{key}_card_ident"):
        st.html('<div class="sd-eyebrow">Cartão 1</div><div class="sd-section">Identificação da instalação</div>')
        st.text_input("Nome da instalação *", value=inst.get("name", ""), key=k["name"],
                      placeholder="p. ex. Laboratório de Microrredes — Bloco C", max_chars=300)
        st.text_area("Descrição", value=inst.get("description", ""), key=k["desc"], height=90)
        nk = list(C.NATURE_OPTIONS)
        st.selectbox("Natureza da atividade *", nk, key=k["nature"], format_func=C.NATURE_OPTIONS.get, placeholder="— selecione —",
                     index=nk.index(inst["nature"]) if inst.get("nature") in nk else None)
        mk = list(C.OPERATION_MODE_OPTIONS)
        st.selectbox("Modo de operação previsto *", mk, key=k["mode"], format_func=C.OPERATION_MODE_OPTIONS.get,
                     placeholder="— selecione —", help="Declaração da instalação. O EMS atual não otimiza importação/exportação com a rede.",
                     index=mk.index(inst["operation_mode"]) if inst.get("operation_mode") in mk else None)
        st.caption("Campos com * são obrigatórios.")
    with c2, st.container(border=True, key=f"{key}_card_loc"):
        st.html('<div class="sd-eyebrow">Cartão 2</div><div class="sd-section">Localização</div>')
        shell.component("geolocate")(key=f"seeds_geo_{key}", data={}, on_action_change=partial(_on_geo, key))
        msg = st.session_state.get(f"{key}_geo_msg")
        if msg:
            {"ok": st.success, "bad": st.error, "warn": st.warning}[msg[0]](msg[1])
        a, b, c = st.columns(3)
        a.text_input("País", value=loc.get("country", ""), key=k["country"], max_chars=300)
        b.text_input("Estado / região", value=loc.get("region", ""), key=k["region"], max_chars=300)
        c.text_input("Cidade / localidade", value=loc.get("city", ""), key=k["city"], max_chars=300)
        st.text_input("Endereço ou descrição do local", value=loc.get("address", ""), key=k["address"], max_chars=300)
        a, b = st.columns(2)
        a.number_input("Latitude [°]", min_value=-90.0, max_value=90.0, key=k["lat"], format="%.6f", placeholder="não declarada")
        b.number_input("Longitude [°]", min_value=-180.0, max_value=180.0, key=k["lon"], format="%.6f", placeholder="não declarada")
        st.text_input("Fuso horário (IANA)", key=k["tz"], placeholder="p. ex. America/Sao_Paulo", max_chars=60)
        sug = st.session_state.get(f"{key}_geo_tz") or ""
        if sug and sug != st.session_state.get(k["tz"]):
            st.caption(f"Sugestão do navegador (fuso do dispositivo, não da instalação): `{shell.md(sug)}`")
            st.button("Usar fuso sugerido", key=f"{key}_use_tz", on_click=lambda: st.session_state.__setitem__(k["tz"], sug))
        st.caption("Todos os campos desta seção são opcionais e podem ser corrigidos manualmente. Cidade, estado e endereço "
                   "não são deduzidos das coordenadas; nenhum serviço externo é consultado. A localização só é gravada "
                   "quando você confirma o formulário.")


def location_source(lat: Any, lon: Any, meta: dict | None, old: dict | None) -> dict:
    """Procedência das coordenadas a gravar (função pura).

    * iguais às recebidas do navegador nesta edição → ``navegador`` (com precisão e instante da leitura);
    * iguais às já salvas → procedência anterior preservada;
    * qualquer outro caso (digitadas ou corrigidas manualmente) → ``manual``, sem precisão."""
    meta, old = meta or {}, old or {}
    if meta and lat == meta.get("lat") and lon == meta.get("lon"):
        return {"source": "navegador", "accuracy_m": meta.get("accuracy_m"), "captured_at": meta.get("captured_at")}
    if lat == old.get("latitude") and lon == old.get("longitude") and old.get("source") in C.LOCATION_SOURCES:
        return {"source": old["source"], "accuracy_m": old.get("accuracy_m"), "captured_at": old.get("captured_at")}
    return {"source": "manual", "accuracy_m": None, "captured_at": None}


def apply_identification(cfg: dict, *, key: str) -> list[str]:
    """Valida e aplica os dois cartões à cópia de trabalho. Devolve erros (vazio = aplicado)."""
    ss = st.session_state
    k = _keys(key)
    errs = []
    name = (ss.get(k["name"]) or "").strip()
    if not name:
        errs.append("Informe o nome da instalação.")
    if ss.get(k["nature"]) is None:
        errs.append("Selecione a natureza da atividade.")
    if ss.get(k["mode"]) is None:
        errs.append("Selecione o modo de operação previsto.")
    lat, lon = ss.get(k["lat"]), ss.get(k["lon"])
    meta = ss.get(f"{key}_geo_meta") or {}
    old = cfg["installation"].get("location") or C.new_location()
    loc = {**C.new_location(), "country": (ss.get(k["country"]) or "").strip(), "region": (ss.get(k["region"]) or "").strip(),
           "city": (ss.get(k["city"]) or "").strip(), "address": (ss.get(k["address"]) or "").strip(),
           "latitude": lat, "longitude": lon, "timezone": (ss.get(k["tz"]) or "").strip(),
           "timezone_suggested": ss.get(f"{key}_geo_tz") or old.get("timezone_suggested") or ""}
    loc.update(location_source(lat, lon, meta, old))
    errs += [i.message for i in C.errors(C.validate_location(loc))]
    if errs:
        return errs
    cfg["installation"].update(name=name, description=(ss.get(k["desc"]) or "").strip(), nature=ss[k["nature"]],
                               operation_mode=ss[k["mode"]], location=loc)
    ss.pop(f"{key}_geo_meta", None)
    ss.pop(f"{key}_geo_msg", None)
    return []


def location_text(loc: dict | None) -> str:
    loc = loc or {}
    parts = [loc.get(k) for k in ("address", "city", "region", "country") if loc.get(k)]
    return ", ".join(parts)


# ------------------------------------------------------------------ modelo lógico de balanço energético
def balance_data(cfg: dict, plan) -> dict:
    sources, storage = [], []
    for eq in cfg.get("equipment", []):
        ms = plan.for_equipment(eq["id"]) if plan else []
        sts = {m.status for m in ms}
        # Usina FV com parte dos arranjos representada: "parcial" (nunca rotulada como incompleta/completa).
        status = (A.REPRESENTED if sts == {A.REPRESENTED} else A.DISABLED if sts == {A.DISABLED} else
                  "parcial" if A.REPRESENTED in sts else
                  A.INCOMPATIBLE if A.INCOMPATIBLE in sts else A.INCOMPLETE if sts else "")
        f = facts(eq)
        node = {"name": eq["name"], "kind": eq["kind"], "kind_label": KIND_LABELS[eq["kind"]], "enabled": bool(eq.get("enabled", True)),
                "detail": f"{f[0][1]}" if f and f[0][1] not in ("—", "") else "", "status": status,
                "status_label": ("Parcialmente representado no EMS" if status == "parcial" else
                                 A.STATUS_LABELS.get(status, "") if status else "")}
        (storage if eq["kind"] == "battery" else sources).append(node)
    dem = cfg.get("demand") or {}
    grid = (cfg.get("energy_balance") or {}).get("grid_connection")
    return {"sources": sources, "storage": storage,
            "core_note": "Soma de potências a cada passo de 1 min: renováveis abatem a carga; despacháveis e armazenamento "
                         "cobrem o restante. Déficit e vertimento são contabilizados e penalizados.",
            "demand_note": C.DEMAND_SOURCES.get(dem.get("source"), "Ainda não definida"),
            "grid": ({"title": "Rede elétrica — conexão declarada",
                      "note": "Não modelada pelo EMS atual: sem importação/exportação nem tarifas. Déficit ≠ compra de energia."}
                     if grid == "conectada" else None),
            "scope_note": "Modelo energético AGREGADO (balanço de potência e energia), não um esquema unifilar: não representa "
                          "barramentos, tensões, conversores, proteções nem conexões físicas entre equipamentos."}


def balance_view(cfg: dict, plan, key: str = "bal") -> None:
    shell.component("balance")(key=f"seeds_{key}", data=balance_data(cfg, plan))


def grid_form(cfg: dict, *, key: str) -> bool:
    bal = cfg["energy_balance"]
    gk = list(C.GRID_CONNECTION_OPTIONS)
    grid = st.radio("Conexão com a rede elétrica (declaração)", gk, index=gk.index(bal.get("grid_connection", "nao_declarada")),
                    horizontal=True, format_func=C.GRID_CONNECTION_OPTIONS.get, key=f"{key}_grid_{token()}",
                    help="Declarar conexão NÃO habilita importação/exportação no EMS atual (não modelado).")
    if grid != bal.get("grid_connection"):
        cfg["energy_balance"] = {**bal, "grid_connection": grid}
        return True
    return False


def grid_notice(cfg: dict) -> None:
    if (cfg.get("energy_balance") or {}).get("grid_connection") == "conectada" or \
            cfg["installation"].get("operation_mode") in ("conectada", "conectada_ilhamento"):
        shell.callout("<b>Conexão com a rede declarada.</b> O EMS atual não otimiza importação/exportação nem tarifas: a "
                      "simulação trata a microrrede como balanço local (déficit e vertimento penalizados). O déficit do EMS "
                      "<b>não</b> equivale a uma compra física de energia da rede. Capacidade identificada como <b>não "
                      "implementada</b>.", "warn")


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
    loc = inst.get("location") or {}
    out.append(shell.check(f"Localização: {escape(location_text(loc) or 'não declarada')}"
                           + (f" · {loc['latitude']:.5f}, {loc['longitude']:.5f}" if loc.get("latitude") is not None else ""),
                           "ok" if location_text(loc) or loc.get("latitude") is not None else "off"))
    out.append(shell.check(f"Inventário: {len(eqs)} equipamento(s) registrado(s)", "ok" if eqs else "warn"))
    conf = [e for e in eqs if C.is_configured(e)]
    out.append(shell.check(f"Tecnicamente configurados para simulação: {len(conf)} de {len(eqs)}",
                           "ok" if eqs and len(conf) == len(eqs) else "warn"))
    grid = (cfg.get("energy_balance") or {}).get("grid_connection", "nao_declarada")
    out.append(shell.check(f"Balanço energético: {escape(C.GRID_CONNECTION_OPTIONS[grid])}", "ok" if grid != "nao_declarada" else "warn"))
    dem = cfg["demand"]
    out.append(shell.check(f"Demanda: {escape(C.DEMAND_SOURCES[dem['source']])} · procedência: {escape(C.PROVENANCE_KINDS[dem['provenance']])}",
                           "ok" if A.demand_descriptor(dem) else "warn"))
    if plan:
        if plan.pv_installed_kWp:
            out.append(shell.check(f"FV: {fmt(plan.pv_installed_kWp, 2, 'kWp')} registrados · {fmt(plan.pv_represented_kWp, 2, 'kWp')} "
                                   "representáveis na simulação (potência nominal, não produção)",
                                   "ok" if abs(plan.pv_installed_kWp - plan.pv_represented_kWp) < 1e-9 else "warn"))
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
