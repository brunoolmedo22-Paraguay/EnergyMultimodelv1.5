"""Centro de Operação · Previsões e Dados (Piso 2B) — vista ``operacao`` / ``tab = "previsoes"``.

Para cada previsão editável do cenário (Demanda elétrica, Clima) a página mostra dois cartões SEPARADOS:

1. **Perfil do cenário** — a entrada atualmente na cópia de trabalho do cenário (salva na versão vN ou incorporada
   nesta sessão e ainda não salva), com gráfico, resumo temporal, qualidade, estatísticas e verificação de
   integridade/reprodutibilidade;
2. **Nova entrada — pré-visualização pendente** — construída AO VIVO a partir do editor da fonte escolhida
   (manual, CSV, sintético, referência). Nunca mostra o perfil anterior como se fosse o pendente. Só depois de
   inspecionada pode ser incorporada (INCORPORAR AO CENÁRIO) — e só é gravada com SALVAR CENÁRIO (nova versão).

Estado de sessão (prefixos ``op_fcs_`` e ``op_blobs`` — limpos ao trocar de cenário/microrrede):
``op_blobs`` {sha256: (bytes, meta)} dados incorporados e ainda não gravados; ``op_fcs_tbl_<slot>`` tabela base do
perfil manual; ``op_fcs_csv_<slot>`` (nome, bytes) do CSV enviado; ``op_fcs_tok_<slot>`` renova as chaves do editor;
``op_fcs_chk_<slot>`` resultado da última verificação de reprodutibilidade. Widgets: prefixo ``opw_fc_``.
"""
from __future__ import annotations

import json
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from seeds2.microgrid import config as C
from seeds2.operation import forecast_sources as FS
from seeds2.operation import forecasts as F
from seeds2.operation import initialization as I
from seeds2.operation import scenarios as S

from . import forecast_charts as CH
from . import session, shell

TAB = "previsoes"
TAB_KEY = "opw_fc_tab"
TAB_LABELS = {"demand": "Demanda elétrica (kW)", "climate": "Clima — variáveis meteorológicas"}
SLOT_TITLES = {"demand": "Previsão de demanda elétrica", "climate": "Previsão climática (variáveis meteorológicas)"}
SOURCES = {"manual": "Manual (tabela)", "csv": "Importar CSV", "sintetico": "Sintético", "referencia": "Referência do software"}
SOURCE_STATUS = {"manual": "manual", "csv": "CSV", "sintetico": "SINTÉTICO", "referencia": "REFERÊNCIA"}
TZ_COMMON = ("UTC", "America/Sao_Paulo", "America/Asuncion", "America/Fortaleza", "America/Recife", "America/Belem",
             "America/Manaus", "America/Cuiaba", "America/Porto_Velho", "America/Rio_Branco", "America/Noronha",
             "UTC-03:00", "UTC-04:00")
TONE = {I.ERROR: "bad", I.WARNING: "warn", I.PENDING: "info", I.INCOMPLETE: "off"}
GLYPH = {I.ERROR: "✕", I.WARNING: "!", I.PENDING: "◷", I.INCOMPLETE: "–"}
STATE_PREFIXES = ("op_fcs_", "op_blobs")


def _ss():
    return st.session_state


def _oc():
    from . import operation_center as OC          # importação tardia (operation_center importa este módulo)

    return OC


def clear_state() -> None:
    """Remove todo o estado das previsões desta sessão (troca de cenário, descarte)."""
    for k in [k for k in list(_ss().keys()) if str(k).startswith(STATE_PREFIXES) or str(k).startswith("opw_fc_")]:
        _ss().pop(k, None)


def pending_blobs() -> dict:
    return _ss().setdefault("op_blobs", {})


def _tok(slot: str) -> int:
    return int(_ss().get(f"op_fcs_tok_{slot}") or 0)


def _bump(slot: str) -> None:
    _ss()[f"op_fcs_tok_{slot}"] = _tok(slot) + 1


def get_blob_fn(store):
    pend = pending_blobs()

    def get(h: str) -> bytes:
        if h in pend:
            return pend[h][0]
        return store.get_blob(h)
    return get


# ======================================================================= apresentação
def _pill(text: str, tone: str) -> str:
    return f'<span class="op-pill {escape(tone)}">{escape(text)}</span>'


def _findings_html(items: list[dict]) -> str:
    order = {I.ERROR: 0, I.INCOMPLETE: 1, I.WARNING: 2, I.PENDING: 3}
    rows = []
    for f in sorted(items, key=lambda f: order.get(f["level"], 9)):
        lvl = f["level"]
        rows.append(f'<div class="op-f"><i class="{TONE.get(lvl, "off")}">{GLYPH.get(lvl, "·")}</i><span>'
                    f'<b>{escape(I.LEVEL_LABELS.get(lvl, lvl))}:</b> {escape(f["message"])}</span></div>')
    return "".join(rows)


def _f2d(fs: list[F.Finding]) -> list[dict]:
    return [{"level": f.level, "variable": f.variable, "code": f.code, "message": f.message} for f in fs]


def _num(v: Any, nd: int = 2) -> str:
    if v is None:
        return "—"
    return f"{float(v):,.{nd}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _when(iso: str | None) -> str:
    if not iso:
        return "—"
    t = pd.Timestamp(iso)
    return t.strftime("%Y-%m-%d %H:%M") + (f":{t.second:02d}" if t.second else "")


def _tz_label(tz: str | None, source: str | None = None) -> str:
    if tz is None:
        return "não declarado"
    extra = {"arquivo": " (do arquivo)", "arquivo_utc": " (convertido para UTC)", "usuario": " (declarado)"}.get(source or "", "")
    return tz + extra


def _summary_html(entry: dict) -> str:
    """Resumo temporal + origem (período, resolução, observações, fuso) de uma entrada."""
    step = entry.get("step_s")
    reg = "regular" if entry.get("regular") else "irregular"
    rows = [("Origem", entry.get("label") or SOURCES.get(entry.get("source_type"), "")),
            ("Procedência", C.PROVENANCE_KINDS.get(entry.get("provenance"), entry.get("provenance"))),
            ("Período disponível", f"{_when(entry.get('t0'))} → {_when(entry.get('t_end'))}"),
            ("Cobertura", F.fmt_duration(entry.get("horizon_s") or 0)),
            ("Resolução original", (F.fmt_duration(step) if step else "—") + f" ({reg})"),
            ("Observações", str(entry.get("n_points"))),
            ("Fuso horário", _tz_label(entry.get("timezone"), entry.get("timezone_source"))),
            ("Variáveis", ", ".join(f"{F.VARIABLES[v].short} ({F.VARIABLES[v].unit})" for v in entry.get("variables") or []))]
    body = "".join(f"<tr><td>{escape(k)}</td><td><b>{escape(str(v))}</b></td></tr>" for k, v in rows)
    return f'<table class="op-tbl">{body}</table>'


def _stats_table(entry: dict) -> pd.DataFrame:
    out = []
    for k in entry.get("variables") or []:
        s = (entry.get("stats") or {}).get(k) or {}
        v = F.VARIABLES[k]
        row = {"Variável": f"{v.short} ({v.unit})", "Mínimo": _num(s.get("min"), 3), "Em": _when(s.get("t_min")),
               "Máximo": _num(s.get("max"), 3), "No instante": _when(s.get("t_max")),
               "Média": _num(s.get("mean"), 3), "Ausentes": s.get("missing", 0)}
        row["Maior variação entre amostras"] = (f"{_num(s['max_jump'])} {v.unit} em {_when(s.get('t_max_jump'))}"
                                                if "max_jump" in s else "—")
        out.append(row)
    return pd.DataFrame(out)


def _energy_line(entry: dict) -> str:
    e = ((entry.get("stats") or {}).get("demand_kW") or {}).get("energy_kWh")
    if e is None:
        return ""
    return (f"Energia estimada no período: <b>{_num(e, 1)} kWh</b> — integração trapezoidal da potência (kW) nos "
            "instantes reais; intervalos ausentes não são integrados. Grandeza derivada, distinta da potência.")


# ======================================================================= controles comuns
def _tz_select(label: str, key: str, inst_tz: str | None, default: str | None = None) -> str | None:
    opts: list[str | None] = [None]
    if inst_tz:
        opts.append(inst_tz)
    opts += [t for t in TZ_COMMON if t not in opts]
    if default is not None and default not in opts:
        opts.append(default)
    idx = opts.index(default) if default in opts else 0

    def fmt(t):
        if t is None:
            return "Não declarado (relógio local sem referência — aviso)"
        return f"{t} (localização da instalação)" if t == inst_tz else t
    return st.selectbox(label, opts, index=idx, key=key, format_func=fmt,
                        help="Fuso dos instantes SEM deslocamento explícito. Não declarado é permitido, mas fica "
                             "identificado como tal. Instantes com deslocamento (±hh:mm/Z) no arquivo usam o fuso do arquivo.")


def _provenance_select(source: str, key: str) -> str:
    opts = list(FS.PROVENANCE_BY_SOURCE[source])
    if len(opts) == 1:
        st.caption(f"Procedência: **{C.PROVENANCE_KINDS[opts[0]]}** (fixa para esta origem).")
        return opts[0]
    return st.selectbox("Procedência dos dados", opts, key=key, format_func=lambda k: C.PROVENANCE_KINDS[k],
                        help="Declare 'medido' apenas para medições reais da instalação. Perfis sintéticos ou de "
                             "referência nunca são medidos.")


def _inst_tz() -> str | None:
    saved = session.saved()
    return ((saved.config.get("installation") or {}).get("location") or {}).get("timezone") or None if saved else None


# ======================================================================= editores (fontes)
def _editor_manual(slot: str, ref: dict, k: str) -> F.Candidate | None:
    ss = _ss()
    variables = F.relevant_variables(slot, ref) or F.SLOT_VARIABLES[slot]
    tbl_key = f"op_fcs_tbl_{slot}"
    st.caption("Construa a curva numa única tabela editável: gere instantes regulares e cole ou digite os valores. "
               "Linhas podem ser acrescentadas/removidas. Células vazias = ausentes (nunca zero).")
    with st.container(border=True):
        st.markdown("**Construir por intervalos regulares**")
        c1, c2, c3 = st.columns([1.6, 1, 1])
        start = c1.text_input("Início (AAAA-MM-DD HH:MM)", value="2026-09-01 08:00", key=f"{k}_start")
        step = c2.number_input("Passo (min)", min_value=1, max_value=1440, value=1, step=1, key=f"{k}_step")
        npts = c3.number_input("Pontos", min_value=2, max_value=20000, value=121, step=1, key=f"{k}_n")
        if st.button("GERAR TABELA REGULAR", key=f"{k}_gen"):
            try:
                ss[tbl_key] = FS.regular_table(variables, str(pd.Timestamp(start)), int(step) * 60, int(npts))
                _bump(slot)
                st.rerun()
            except (ValueError, TypeError):
                st.error("Início inválido: use o formato AAAA-MM-DD HH:MM.")
        c4, c5 = st.columns([1.2, 2.8], vertical_alignment="bottom")
        var = c4.selectbox("Colar valores na coluna", variables, key=f"{k}_pastevar",
                           format_func=lambda v: f"{F.VARIABLES[v].short} ({F.VARIABLES[v].unit})")
        text = c5.text_area("Valores colados (um por linha; vírgula = decimal)", key=f"{k}_paste", height=80,
                            placeholder="120,5\n118\n131,2 …")
        if st.button("APLICAR VALORES COLADOS", key=f"{k}_apply", disabled=tbl_key not in ss):
            vals, bad = FS.parse_pasted(text)
            base = ss[tbl_key].copy()
            if bad:
                st.error(f"Valores não numéricos: {', '.join(bad[:5])}. Nada foi aplicado.")
            elif len(vals) != len(base):
                st.error(f"Foram colados {len(vals)} valores para {len(base)} linhas da tabela. Nada foi aplicado.")
            else:
                base[var] = pd.array(vals, dtype="Float64")
                ss[tbl_key] = base
                _bump(slot)
                st.rerun()
    if tbl_key not in ss:
        st.info("Gere a tabela regular para começar.")
        return None
    cfg = {"timestamp": st.column_config.DatetimeColumn("Instante", format="YYYY-MM-DD HH:mm:ss", required=True)}
    for v in variables:
        cfg[v] = st.column_config.NumberColumn(f"{F.VARIABLES[v].short} ({F.VARIABLES[v].unit})", format="%.4g")
    edited = st.data_editor(ss[tbl_key], key=f"{k}_tbl_{_tok(slot)}", num_rows="dynamic", column_config=cfg,
                            hide_index=True, width="stretch", height=260)
    c6, c7 = st.columns(2)
    with c6:
        tz = _tz_select("Fuso horário dos instantes", f"{k}_tz", _inst_tz())
    with c7:
        prov = _provenance_select("manual", f"{k}_prov")
    return FS.manual_candidate(pd.DataFrame(edited), slot, timezone=tz, inventory_ref=ref, provenance=prov,
                               construction={"start": start, "step_min": int(step), "points": int(npts)})


def _editor_csv(slot: str, ref: dict, k: str) -> F.Candidate | None:
    ss = _ss()
    up = st.file_uploader("Arquivo CSV (separador vírgula, ponto e vírgula ou tabulação)", type=["csv", "txt"],
                          key=f"{k}_up_{_tok(slot)}")
    csv_key = f"op_fcs_csv_{slot}"
    if up is not None:
        data = up.getvalue()
        if ss.get(csv_key, (None, b""))[1] != data:
            ss[csv_key] = (up.name, data)
    if csv_key not in ss:
        st.info("Envie um arquivo para ver a estrutura detectada, confirmar o mapeamento e pré-visualizar.")
        return None
    name, data = ss[csv_key]
    insp = FS.inspect_csv(data, name, slot)
    fid = F.digest(data)[:10]
    st.caption(f"Arquivo: **{shell.md(name)}** · {len(data):,} bytes · SHA-256 {fid}…".replace(",", "."))
    if not insp.ok:
        st.error("Arquivo recusado: " + " ".join(insp.errors))
        return F.Candidate(slot, None, None, F.Analysis([F.Finding(I.ERROR, None, "csv", e) for e in insp.errors]))
    with st.expander(f"Estrutura detectada — {len(insp.raw)} linhas × {len(insp.columns)} colunas (dados originais)",
                     expanded=False):
        st.dataframe(insp.raw.head(12), hide_index=True, width="stretch")
    sug = insp.suggestion
    kk = f"{k}_{fid}"                                   # novo arquivo → mapeamento sugerido de novo
    st.markdown("**Mapeamento das colunas** — confirme ou corrija")
    c1, c2, c3 = st.columns(3)
    mode = c1.radio("Tempo", ["absoluto", "relativo"], index=0 if sug["time_mode"] == "absoluto" else 1, horizontal=True,
                    key=f"{kk}_mode", format_func=lambda m: {"absoluto": "Data e hora", "relativo": "Tempo relativo"}[m])
    cols = insp.columns
    tcol = c2.selectbox("Coluna de tempo", cols, index=cols.index(sug["time_column"]) if sug["time_column"] in cols else 0,
                        key=f"{kk}_tcol")
    mapping: dict[str, Any] = {"time_mode": mode, "time_column": tcol, "duplicates": "recusar"}
    if mode == "absoluto":
        mapping["date_order"] = c3.selectbox("Ordem da data", list(F.DATE_ORDERS), key=f"{kk}_order",
                                             format_func=lambda o: F.DATE_ORDERS[o])
    else:
        mapping["relative_unit"] = c3.selectbox("Unidade do tempo", list(F.TIME_UNITS_S),
                                                index=list(F.TIME_UNITS_S).index(sug.get("relative_unit") or "min"),
                                                key=f"{kk}_runit")
        mapping["t0"] = st.text_input("Instante inicial (t = 0) — AAAA-MM-DD HH:MM *", value="", key=f"{kk}_t0",
                                      help="Obrigatório: dados de tempo relativo não têm data própria.").strip() or None
    c4, c5 = st.columns(2)
    with c4:
        mapping["timezone"] = _tz_select("Fuso horário (instantes sem deslocamento)", f"{kk}_tz", _inst_tz())
    with c5:
        mapping["duplicates"] = st.selectbox("Instantes repetidos", list(F.DUPLICATE_POLICIES), key=f"{kk}_dup",
                                             format_func=lambda d: F.DUPLICATE_POLICIES[d])
    reqs = F.climate_requirements(ref) if slot == "climate" else {}
    variables = F.relevant_variables(slot, ref) or F.SLOT_VARIABLES[slot]
    colmap: dict[str, dict] = {}
    for v in variables:
        var = F.VARIABLES[v]
        s = sug["columns"].get(v) or {}
        r = st.columns([2.2, 2, 1.6], vertical_alignment="bottom")
        need = "obrigatória" if (slot == "demand" or reqs.get(v, {}).get("required")) else "opcional"
        opts = [None, *cols]
        col = r[0].selectbox(f"{var.label} — {need}", opts, index=opts.index(s.get("column")) if s.get("column") in opts else 0,
                             key=f"{kk}_c_{v}", format_func=lambda c: "— não mapeada —" if c is None else c,
                             placeholder="— não mapeada —")
        uopts = [None, *F.UNITS[v]]
        det = F.detect_unit(v, col) if col else None       # unidade indicada no cabeçalho DA coluna escolhida
        unit = r[1].selectbox(f"Unidade de {var.short}", uopts, index=uopts.index(det) if det in uopts else 0,
                              key=f"{kk}_u_{v}_{F.normalize_name(col) if col else 'nenhuma'}", disabled=col is None,
                              format_func=lambda u: "— confirme a unidade —" if u is None else u,
                              placeholder="— confirme a unidade —")
        r[2].caption(("unidade detectada no cabeçalho" if det and unit == det else
                      "unidade confirmada pelo usuário" if unit else "unidade não indicada no arquivo")
                     if col else "")
        if col:
            colmap[v] = {"column": col, "unit": unit}
    mapping["columns"] = colmap
    prov = _provenance_select("csv", f"{k}_prov")
    return FS.csv_candidate(insp, slot, mapping, inventory_ref=ref, provenance=prov)


def _editor_synthetic(slot: str, ref: dict, k: str) -> F.Candidate | None:
    shell.callout("<b>Perfil SINTÉTICO hipotético</b>: gerado por fórmula com parâmetros e semente registrados — "
                  "reprodutível, procedência <b>sintético</b>. Não é previsão meteorológica real nem medição.", "")
    gens = [g for g, d in FS.GENERATORS.items() if d["slot"] == slot]
    gen = st.selectbox("Gerador", gens, key=f"{k}_gen", format_func=lambda g: FS.GENERATORS[g]["label"])
    c1, c2, c3 = st.columns([1.6, 1, 1])
    t0 = c1.text_input("Início (AAAA-MM-DD HH:MM)", value="2026-09-01 00:00", key=f"{k}_t0")
    step = c2.number_input("Passo (min)", min_value=1, max_value=1440, value=1 if slot == "demand" else 10, key=f"{k}_step")
    hours = c3.number_input("Duração (h)", min_value=0.5, max_value=24.0 * 366, value=24.0, step=1.0, key=f"{k}_dur")
    p: dict[str, Any] = {"t0": t0, "step_s": int(step) * 60, "duration_s": int(round(float(hours) * 3600))}
    try:
        pd.Timestamp(t0)
    except (ValueError, TypeError):
        st.error("Início inválido: use o formato AAAA-MM-DD HH:MM.")
        return None
    if gen == "demanda_constante":
        p["value_kW"] = st.number_input("Potência (kW)", min_value=0.0, value=100.0, key=f"{k}_v")
    elif gen == "demanda_tramos":
        txt = st.text_input("Tramos horários (hora:kW; …) — cada valor vale até o tramo seguinte, ciclo de 24 h",
                            value="0:80; 8:150; 18:200; 22:90", key=f"{k}_blocks")
        try:
            p["blocks"] = [[float(a.replace(",", ".")), float(b.replace(",", "."))]
                           for a, b in (x.split(":") for x in txt.split(";") if x.strip())]
            if any(not 0 <= h < 24 or v < 0 for h, v in p["blocks"]):
                raise ValueError
        except ValueError:
            st.error("Tramos inválidos: use 'hora:kW' separados por ';' (0 ≤ hora < 24; kW ≥ 0).")
            return None
    elif gen == "demanda_diaria":
        a, b, c, d = st.columns(4)
        p["base_kW"] = a.number_input("Base (kW)", min_value=0.0, value=60.0, key=f"{k}_base")
        peak = {"hour": b.number_input("Hora do pico", min_value=0.0, max_value=23.99, value=12.0, key=f"{k}_ph"),
                "width_h": c.number_input("Largura (h)", min_value=0.1, value=2.0, key=f"{k}_pw"),
                "kW": d.number_input("Acréscimo no pico (kW)", value=80.0, key=f"{k}_pk")}
        p["peaks"] = [peak]
        if st.checkbox("Segundo pico", key=f"{k}_p2"):
            b2, c2_, d2 = st.columns(3)
            p["peaks"].append({"hour": b2.number_input("Hora do 2º pico", min_value=0.0, max_value=23.99, value=19.0, key=f"{k}_ph2"),
                               "width_h": c2_.number_input("Largura do 2º (h)", min_value=0.1, value=1.5, key=f"{k}_pw2"),
                               "kW": d2.number_input("Acréscimo do 2º (kW)", value=60.0, key=f"{k}_pk2")})
    else:
        relevant = list(F.relevant_variables("climate", ref)) or ["ghi_W_m2", "temperature_C"]
        p["variables"] = st.multiselect("Variáveis geradas", list(F.SLOT_VARIABLES["climate"]), default=relevant,
                                        key=f"{k}_vars", format_func=lambda v: f"{F.VARIABLES[v].short} ({F.VARIABLES[v].unit})")
        cols = st.columns(4)
        if "ghi_W_m2" in p["variables"]:
            p["sunrise_h"] = cols[0].number_input("Nascer do sol (h)", 0.0, 23.0, 6.0, key=f"{k}_sr")
            p["sunset_h"] = cols[1].number_input("Pôr do sol (h)", 1.0, 24.0, 18.0, key=f"{k}_ss")
            p["ghi_peak_W_m2"] = cols[2].number_input("GHI máxima (W/m²)", 0.0, 1361.0, 850.0, key=f"{k}_gp")
        if "temperature_C" in p["variables"]:
            p["t_min_C"] = cols[3].number_input("Temp. mínima (°C)", -40.0, 50.0, 20.0, key=f"{k}_tmin")
            p["t_max_C"] = cols[0].number_input("Temp. máxima (°C)", -40.0, 60.0, 30.0, key=f"{k}_tmax")
            p["t_max_hour"] = cols[1].number_input("Hora da máxima", 0.0, 23.99, 15.0, key=f"{k}_tmh")
        if "wind_speed_m_s" in p["variables"]:
            p["wind_mean_m_s"] = cols[2].number_input("Vento médio (m/s)", 0.0, 40.0, 7.0, key=f"{k}_wm")
            p["wind_amp_m_s"] = cols[3].number_input("Oscilação do vento (m/s)", 0.0, 20.0, 1.5, key=f"{k}_wa")
            p["wind_period_h"] = cols[0].number_input("Período da oscilação (h)", 0.5, 48.0, 8.0, key=f"{k}_wp")
        if "wind_direction_deg" in p["variables"]:
            p["wind_dir_deg"] = cols[1].number_input("Direção (°)", 0.0, 359.9, 110.0, key=f"{k}_wd")
        if "pressure_hPa" in p["variables"]:
            p["pressure_hPa"] = cols[2].number_input("Pressão (hPa)", 500.0, 1100.0, 1013.25, key=f"{k}_pr")
        if "humidity_pct" in p["variables"]:
            p["humidity_pct"] = cols[3].number_input("Umidade (%)", 0.0, 100.0, 65.0, key=f"{k}_hu")
    a, b = st.columns(2)
    p["noise_pct"] = a.number_input("Ruído aleatório (% do valor)", min_value=0.0, max_value=50.0, value=0.0, key=f"{k}_noise",
                                    help="0 = determinístico. Com ruído, a semente abaixo é registrada e reproduz o perfil exatamente.")
    p["seed"] = int(b.number_input("Semente", min_value=0, max_value=2**31 - 1, value=2026, step=1, key=f"{k}_seed"))
    tz = _tz_select("Fuso horário", f"{k}_tz", _inst_tz())
    return FS.synthetic_candidate(gen, p, timezone=tz, inventory_ref=ref)


def _editor_reference(slot: str, ref: dict, k: str) -> F.Candidate | None:
    shell.callout("<b>Perfil de referência incluído no software</b> (Energy MultiModel V1.6) — reutilizado sem "
                  "alteração; <b>não é medição desta instalação</b>.", "")
    keys = [r for r, d in FS.REFERENCES.items() if d["slot"] == slot]
    key = st.selectbox("Conjunto de referência", keys, key=f"{k}_ds", format_func=lambda r: FS.REFERENCES[r]["label"])
    st.caption(FS.REFERENCES[key]["note"])
    p: dict[str, Any] = {}
    if key == "walkforward":
        opts = FS.walkforward_options()
        o = st.selectbox("Janela (cenário × perfil × hora de início)", opts, key=f"{k}_wf",
                         format_func=lambda x: f"{x[0]} × {x[1]} · {x[2]:02d} h")
        p = {"scenario": o[0], "profile": o[1], "start_hour": int(o[2])}
    elif key == "copel_b1":
        a, b = st.columns(2)
        p["day"] = a.selectbox("Tipo de dia", ["util", "sabado", "domingo"], key=f"{k}_day",
                               format_func=lambda d: {"util": "Dia útil", "sabado": "Sábado", "domingo": "Domingo"}[d])
        p["date"] = b.text_input("Data atribuída (convenção explícita)", value="2026-09-01", key=f"{k}_date")
    elif key == "clima_sintetico_v16":
        a, b = st.columns(2)
        p["t0"] = a.text_input("Início (AAAA-MM-DD HH:MM)", value="2026-09-01 06:00", key=f"{k}_t0")
        p["duration_min"] = int(b.number_input("Duração (min, passo de 1 min)", 10, 7 * 1440, 720, key=f"{k}_dm"))
    try:
        for f in ("date", "t0"):
            if f in p:
                pd.Timestamp(p[f])
    except (ValueError, TypeError):
        st.error("Data/hora inválida: use AAAA-MM-DD [HH:MM].")
        return None
    return FS.reference_candidate(key, p, inventory_ref=ref)


EDITORS = {"manual": _editor_manual, "csv": _editor_csv, "sintetico": _editor_synthetic, "referencia": _editor_reference}


# ======================================================================= cartões
def _chart(slot: str, df: pd.DataFrame, *, title: str, subtitle: str, key: str) -> None:
    show_grid = st.checkbox("Mostrar também a grade de 1 min do EMS (série transformada: interpolação linear sem "
                            "extrapolação, apenas para visualização)", key=f"{key}_grid")
    fig = CH.figure(slot, df, title=title, subtitle=subtitle, transformed=show_grid)
    st.plotly_chart(fig, config=CH.CONFIG, key=f"{key}_fig", width="stretch")


def _current_card(store, cur, slot: str, entry: dict | None) -> None:
    ss = _ss()
    with st.container(border=True):
        if not entry:
            st.html(f'<div class="op-k">Perfil do cenário</div><div class="op-row"><div class="op-t">Nenhuma previsão '
                    f'definida</div>{_pill("Não definida", "off")}</div><p class="op-d">Crie uma entrada abaixo: ela '
                    'aparece aqui depois de incorporada.</p>')
            return
        saved_entry = (cur.document.get("forecasts") or {}).get(slot)
        if saved_entry is not None and C.fingerprint(saved_entry) == C.fingerprint(entry):
            status = _pill(f"Salvo · v{cur.version}", "ok")
        else:
            status = _pill("Incorporado nesta sessão — não salvo", "warn")
        st.html(f'<div class="op-k">Perfil do cenário</div><div class="op-row"><div class="op-t">'
                f'{escape(entry.get("label") or "")}</div>{status}{_pill(SOURCE_STATUS.get(entry["source_type"], ""), "info")}'
                f'</div>' + _summary_html(entry))
        try:
            df = F.load(entry, get_blob_fn(store))
        except F.ForecastDataError as exc:
            st.error(f"Não foi possível ler os dados deste perfil: {exc} A entrada do cenário é mantida; nada foi "
                     "alterado. Substitua o perfil ou restaure a microrrede a partir de um armazenamento íntegro.")
            df = None
        if df is not None:
            _chart(slot, df, title=f"{SLOT_TITLES[slot]} — perfil do cenário",
                   subtitle=f"{entry.get('label', '')} · {_when(entry.get('t0'))} → {_when(entry.get('t_end'))}",
                   key=f"opw_fc_cur_{slot}_{C.fingerprint(entry)[:8]}")
        en = _energy_line(entry)
        if en:
            st.html(f'<p class="op-d">{en}</p>')
        items = (entry.get("quality") or {}).get("items") or []
        if items:
            st.html(_findings_html(items))
        st.dataframe(_stats_table(entry), hide_index=True, width="stretch")
        c1, c2 = st.columns(2)
        if c1.button("VERIFICAR INTEGRIDADE E REPRODUTIBILIDADE", key=f"opw_fc_chk_{slot}", width="stretch",
                     help="Relê os dados pelo SHA-256 e reconstrói a série a partir da origem registrada."):
            ss[f"op_fcs_chk_{slot}"] = (C.fingerprint(entry), *FS.rederive(entry, get_blob_fn(store)))
        if c2.button("REMOVER PREVISÃO DO CENÁRIO", key=f"opw_fc_rm_{slot}", width="stretch",
                     help="Retira a entrada da cópia de trabalho; grave com SALVAR CENÁRIO. Versões anteriores e os "
                          "dados armazenados são preservados."):
            _oc().work()["forecasts"].pop(slot, None)
            ss.pop(f"op_fcs_chk_{slot}", None)
            st.rerun()
        chk = ss.get(f"op_fcs_chk_{slot}")
        if chk and chk[0] == C.fingerprint(entry):
            (st.success if chk[1] else st.error)(chk[2])
        with st.expander("Detalhes técnicos — origem, mapeamento, transformações e SHA-256"):
            st.markdown(f"- Série normalizada: `{entry.get('data')}`")
            if entry.get("blob"):
                st.markdown(f"- Arquivo original: `{entry.get('blob')}`")
            tr = entry.get("transforms") or []
            st.markdown("- Transformações aplicadas: " + ("; ".join(shell.md(t) for t in tr) if tr else "nenhuma"))
            st.json({k: entry.get(k) for k in ("source_type", "provenance", "params", "mapping", "timezone",
                                                 "timezone_source", "format_version", "created_at")}, expanded=False)
            if df is not None:
                st.dataframe(df, hide_index=True, width="stretch", height=220)


def _pending_card(store, slot: str, ref: dict, entry: dict | None) -> None:
    ss = _ss()
    with st.container(border=True):
        st.html('<div class="op-k">Nova entrada</div><div class="op-row"><div class="op-t">Fonte de dados e '
                f'pré-visualização</div>{_pill("Pendente — não incorporada", "off")}</div>')
        src = st.radio("Fonte de dados", list(SOURCES), key=f"opw_fc_src_{slot}", horizontal=True,
                       format_func=lambda s: SOURCES[s])
        k = f"opw_fc_{slot}_{src}"
        cand = EDITORS[src](slot, ref, k)
        if cand is None:
            return
        st.markdown('<div class="sd-section">Pré-visualização — dados ainda NÃO incorporados ao cenário</div>',
                    unsafe_allow_html=True)
        items = _f2d(cand.analysis.findings)
        if cand.df is not None and cand.entry is not None:
            st.html(_summary_html(cand.entry))
            _chart(slot, cand.df, title=f"{SLOT_TITLES[slot]} — PRÉ-VISUALIZAÇÃO (pendente)",
                   subtitle=f"{cand.entry['label']} · ainda não incorporada ao cenário", key=f"{k}_pv")
            en = _energy_line(cand.entry)
            if en:
                st.html(f'<p class="op-d">{en}</p>')
            st.dataframe(_stats_table(cand.entry), hide_index=True, width="stretch")
        elif cand.df is not None and len(cand.df):
            st.caption("Pré-visualização dos dados lidos (com erros — não incorporáveis):")
            st.dataframe(cand.df.head(50), hide_index=True, width="stretch", height=200)
        else:
            st.caption("Sem pré-visualização: corrija os erros abaixo.")
        if items:
            st.html(_findings_html(items))
        if cand.transforms:
            st.caption("Transformações registradas: " + "; ".join(shell.md(t) for t in cand.transforms))
        c1, c2 = st.columns([1.4, 2.6], vertical_alignment="center")
        label = "SUBSTITUIR NO CENÁRIO" if entry else "INCORPORAR AO CENÁRIO"
        if c1.button(label, key=f"opw_fc_inc_{slot}", type="primary", width="stretch", disabled=not cand.ok):
            work = _oc().work()
            work.setdefault("forecasts", {})[slot] = cand.entry
            pending_blobs().update(cand.blobs)
            ss.pop(f"op_fcs_chk_{slot}", None)
            ss.pop(f"op_fcs_tbl_{slot}", None)
            ss.pop(f"op_fcs_csv_{slot}", None)
            _bump(slot)
            _oc()._flash("ok", f"{SLOT_TITLES[slot]} incorporada à cópia de trabalho do cenário. Use SALVAR CENÁRIO "
                               "para gravar uma nova versão.")
            st.rerun()
        c2.caption("Bloqueado: há erros nos dados." if not cand.ok else
                   ("Substituirá o perfil atual na cópia de trabalho. " if entry else "") +
                   "Nada é gravado até SALVAR CENÁRIO (nova versão; versões anteriores preservadas).")


def _requirements(ref: dict) -> None:
    reqs = F.climate_requirements(ref)
    techs = F.technologies(ref)
    if not reqs:
        shell.callout("Nenhuma fonte solar ou eólica habilitada no inventário de referência: a previsão climática não "
                      "é necessária para este cenário (pode ser registrada opcionalmente).", "")
        return
    rows = "".join(
        f"<tr><td>{escape(F.VARIABLES[v].label)}</td><td>{escape(F.VARIABLES[v].unit)}</td>"
        f"<td><b>{'obrigatória' if r['required'] else 'opcional'}</b></td>"
        f"<td>{escape(', '.join(F.TECH_LABELS[t] for t in r['techs']))}</td></tr>" for v, r in reqs.items())
    names = "; ".join(f"{F.TECH_LABELS[t]}: {', '.join(n)}" for t, n in techs.items())
    st.html(f'<p class="op-d">Conjunto climático <b>compartilhado</b> pelas tecnologias habilitadas no inventário de '
            f'referência ({escape(names)}). Apenas entradas meteorológicas — nenhuma potência FV/eólica é calculada '
            'aqui.</p><table class="op-tbl"><tr><th>Variável</th><th>Unidade</th><th>Exigência</th><th>Usada por</th></tr>'
            f'{rows}</table>')


def render(store, cur) -> None:
    oc = _oc()
    if st.button("← Centro de Operação", key="op_back_fc"):
        shell.go("operacao")
        st.rerun()
    if cur is None or oc.work() is None:
        st.info("Nenhum cenário selecionado. Crie ou selecione um cenário no Centro de Operação.")
        return
    doc = oc.work()
    doc.setdefault("forecasts", {})
    saved = session.saved()
    ref = doc["inventory_ref"]
    techs = F.technologies(ref)
    tone, label, detail = F.stage_status(doc)
    shell.hero("Previsões e Dados", doc["name"],
               "Condições FUTURAS do experimento — demanda elétrica e variáveis meteorológicas — com base temporal "
               "original preservada. Não altera o inventário físico e ainda não é aplicada às rodadas (Piso 2C).",
               [("Cenário", f"v{cur.version}" + (" · alterações não salvas" if oc.is_dirty() else "")),
                ("Inventário de referência", f"rev. {ref['config_revision']}"),
                ("Renováveis habilitadas", ", ".join(F.TECH_LABELS[t] for t in techs) or "nenhuma"),
                ("Previsões", f"{label}" + (f" · {detail}" if detail else "")),
                ("Microrrede", saved.config["installation"]["name"])])
    st.html('<div class="op-legend">'
            '<span><b style="color:#C2364A">✕ Erro</b> — impede incorporar e salvar</span>'
            '<span><b style="color:#C77700">! Advertência</b> — permitido</span>'
            '<span><b style="color:#2F6FED">◷ Capacidade pendente</b> — ainda não interpretada pelo EMS V1.6 (Piso 2C)</span>'
            '<span><b>– Não definido</b> — prontidão do cenário</span></div>')
    # Abas com estado (chave própria): a aba ativa sobrevive às reexecuções e só a aba aberta é processada.
    tabs = st.tabs(list(TAB_LABELS.values()), key=TAB_KEY, on_change="rerun")
    for tab, slot in zip(tabs, F.EDITABLE_SLOTS):
        if tab.open is False:
            continue
        with tab:
            entry = doc["forecasts"].get(slot)
            if slot == "climate":
                _requirements(ref)
            else:
                st.html('<p class="op-d">Potência elétrica demandada (kW, valor instantâneo) ao longo do tempo. A energia '
                        '(kWh) só aparece como grandeza derivada, calculada por integração temporal.</p>')
            _current_card(store, cur, slot, entry)
            _pending_card(store, slot, ref, entry)
    fs = F.scenario_findings(doc)
    if fs:
        st.markdown('<div class="sd-section">Conjunto de previsões do cenário</div>', unsafe_allow_html=True)
        st.html(_findings_html(_f2d(fs)))
    ov = F.overlap(doc["forecasts"].get("demand"), doc["forecasts"].get("climate"))
    if ov:
        st.caption(f"Período comum demanda × clima: {_when(ov[0])} → {_when(ov[1])}. A janela experimental, a "
                   "discretização do motor e o horizonte móvel serão escolhidos no Piso 2C.")
    shell.callout("Este cenário <b>ainda não é executado</b> com estas previsões: a Simulação (console V1.6) continua "
                  "usando a configuração salva da microrrede. O runner do cenário é o Piso 2C.", "")
    oc._save_bar(store, cur, I.summarize(S.findings(doc)))


__all__ = ["TAB", "clear_state", "get_blob_fn", "pending_blobs", "render"]
