"""Main orchestration interface for Energy MultiModel.

The orchestration shell now includes the real multifont EMS imported from the
Marília branch. The overview/model-result panels still use ``orchestrator_demo``
as a UI prototype and remain explicitly identified as MODO TESTE; the
"Otimizador" page launches the real EMS workflow.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from simulation.orchestrator_demo import (
    DemoConfig,
    SOURCE_LABELS,
    build_demo_model_frame,
    make_demand_curve,
    run_demo_optimizer,
)


PAGES = (
    "Visão Geral",
    "Módulo de Carga",
    "Otimizador",
    "Resultados dos Modelos",
    "Testar Modelos",
    "Exportar Resultados",
)
PAGE_ICONS = {
    "Visão Geral": "▦",
    "Módulo de Carga": "⌁",
    "Otimizador": "◎",
    "Resultados dos Modelos": "◫",
    "Testar Modelos": "◇",
    "Exportar Resultados": "⇩",
}
SOURCE_COLORS = {
    "solar": "#F0A43A",
    "wind": "#2B9BB3",
    "battery": "#6F8F3D",
    "h2": "#5274C9",
    "thermal": "#A06A4B",
    "demand": "#17222D",
    "excess": "#AAB6BF",
}

ORCHESTRATOR_CSS = """
<style>
  :root {
    --em-navy:#203746; --em-navy2:#182A36; --em-blue:#087BA8; --em-cyan:#29A6B8;
    --em-ink:#18242D; --em-muted:#6D7D88; --em-border:#DCE3E8; --em-soft:#F4F8FA;
    --em-green:#198B68; --em-amber:#BC7B12; --em-red:#C84C4C;
  }
  .block-container { max-width:1780px; padding-top:1.15rem; padding-bottom:2rem; }
  [data-testid="stSidebar"] { background:linear-gradient(180deg,#182A36 0%,#203746 100%) !important; }
  [data-testid="stSidebar"] > div { padding-top:.7rem; }
  .orq-brand { padding:.55rem .2rem 1rem; text-align:center; }
  .orq-brand-mark { width:48px;height:48px;margin:0 auto .45rem;border-radius:13px;display:grid;place-items:center;
    background:linear-gradient(135deg,#0B87B4,#36B4B8);color:white;font-weight:950;font-size:1.02rem;box-shadow:0 7px 20px rgba(0,0,0,.15); }
  .orq-brand-name { color:#FFF;font-size:.91rem;font-weight:900;letter-spacing:.14em; }
  .orq-brand-sub { color:#90A9B8;font-size:.58rem;font-weight:800;letter-spacing:.12em;margin-top:.22rem; }
  .orq-side-label { color:#89A2B1;font-size:.61rem;font-weight:900;letter-spacing:.14em;margin:.4rem 0 .35rem; }
  .orq-side-status { border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.045);border-radius:9px;padding:.58rem .68rem;margin-top:.5rem; }
  .orq-side-status small { color:#8FA8B6 !important;font-size:.57rem;letter-spacing:.1em;font-weight:900; }
  .orq-side-status b { color:white !important;font-size:.73rem;display:block;margin-top:.12rem; }
  .mode-test { display:inline-flex;align-items:center;gap:.36rem;padding:.28rem .58rem;border-radius:999px;background:#FFF1D8;border:1px solid #F0D19A;color:#96620D;font-size:.64rem;font-weight:900;letter-spacing:.08em; }
  .page-hero { border:1px solid var(--em-border);border-radius:12px;padding:.8rem 1rem;background:linear-gradient(90deg,#FFF 0%,#F7FBFD 100%);margin-bottom:.72rem; }
  .hero-eyebrow { color:var(--em-blue);font-size:.62rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase; }
  .hero-title { color:#14232D;font-size:1.65rem;line-height:1.08;font-weight:950;letter-spacing:-.035em;margin:.18rem 0 .12rem; }
  .hero-sub { color:#687A85;font-size:.76rem;line-height:1.45; }
  .kpi-card { border:1px solid var(--em-border);border-radius:10px;background:white;padding:.67rem .74rem;min-height:92px;box-shadow:0 2px 10px rgba(36,55,70,.035); }
  .kpi-card small { color:#7A8993;font-size:.58rem;font-weight:900;letter-spacing:.095em;text-transform:uppercase; }
  .kpi-card b { display:block;color:#18252E;font-size:1.25rem;line-height:1.1;margin:.18rem 0 .14rem;font-weight:930; }
  .kpi-card span { color:#6F808B;font-size:.66rem; }
  .section-head { display:flex;justify-content:space-between;align-items:end;margin:.8rem 0 .42rem; }
  .section-head small { display:block;color:var(--em-blue);font-size:.59rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.12rem; }
  .section-head b { color:#1B2A33;font-size:.95rem;font-weight:900; }
  .section-head span { color:#778690;font-size:.67rem; }
  .run-strip { display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.48rem;margin-bottom:.65rem; }
  .run-cell { border:1px solid #DFE6EA;border-radius:9px;padding:.5rem .58rem;background:#FBFCFD; }
  .run-cell small { display:block;color:#7C8B95;font-size:.55rem;font-weight:900;letter-spacing:.09em;text-transform:uppercase; }
  .run-cell b { display:block;color:#20313C;font-size:.74rem;margin-top:.1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }
  .alert-card { border-radius:9px;padding:.57rem .65rem;margin-bottom:.42rem;border:1px solid #DFE5E9;background:#FBFCFD; }
  .alert-card b { color:#21323C;font-size:.72rem; }
  .alert-card p { margin:.15rem 0 0;color:#70808B;font-size:.66rem;line-height:1.4; }
  .alert-ok { border-left:3px solid #2B9A72; }
  .alert-warn { border-left:3px solid #D3942A; }
  .alert-info { border-left:3px solid #338CAA; }
  .source-mini { border:1px solid var(--em-border);border-radius:10px;padding:.62rem .66rem;background:white;min-height:104px; }
  .source-mini small { color:#7A8992;font-size:.56rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase; }
  .source-mini b { display:block;color:#1B2932;font-size:.85rem;margin:.16rem 0; }
  .source-mini strong { font-size:1.05rem;color:#152630; }
  .source-mini p { color:#778790;font-size:.62rem;margin:.15rem 0 0;line-height:1.35; }
  .test-card { border:1px solid var(--em-border);border-radius:11px;background:white;padding:.72rem .78rem .64rem;min-height:154px; }
  .test-icon { font-size:1.65rem;line-height:1; }
  .test-card h4 { margin:.32rem 0 .2rem;color:#1C2B34;font-size:.9rem;font-weight:930; }
  .test-card p { color:#71818B;font-size:.66rem;line-height:1.45;min-height:47px;margin:0 0 .35rem; }
  .callout { border-left:3px solid #1683A8;background:#F0F7FA;border-radius:0 8px 8px 0;padding:.58rem .7rem;color:#456575;font-size:.69rem;line-height:1.48;margin:.38rem 0 .5rem; }
  .good-callout { border-left-color:#2D9271;background:#F1F8F5; }
  .warn-callout { border-left-color:#D29328;background:#FFF8EB; }
  .optimizer-map { display:grid;grid-template-columns:1fr auto 1.25fr auto 1fr;gap:.45rem;align-items:center;margin:.45rem 0 .7rem; }
  .opt-step { border:1px solid #DDE5EA;border-radius:9px;padding:.55rem .62rem;background:white;text-align:center; }
  .opt-step small { display:block;color:#7B8B94;font-size:.55rem;font-weight:900;letter-spacing:.08em; }
  .opt-step b { display:block;color:#20343F;font-size:.76rem;margin-top:.12rem; }
  .opt-arrow { color:#88A1AF;font-size:1.25rem;font-weight:900; }
  .result-tag { display:inline-block;padding:.22rem .48rem;border-radius:999px;background:#E8F6F1;border:1px solid #C1E7D9;color:#167456;font-size:.61rem;font-weight:900;letter-spacing:.07em; }
  .stButton > button[kind="primary"] { background:#087BA8;border-color:#087BA8; }
  .stButton > button { border-radius:8px;font-weight:800; }
  div[data-testid="stMetric"] { border:1px solid #E0E6EA;border-radius:9px;padding:.55rem .62rem;background:white; }
  div[data-testid="stMetric"] label { color:#778690 !important;font-size:.64rem !important; }
  div[data-testid="stMetric"] [data-testid="stMetricValue"] { color:#1A2A34;font-size:1.25rem; }
  [data-testid="stDataFrame"] { border:1px solid #E1E7EB;border-radius:9px;overflow:hidden; }
</style>
"""


def _init_state() -> None:
    defaults = {
        "orchestrator_page": "Visão Geral",
        "demo_demand_profile": "Operação balanceada",
        "demo_demand_scale": 1.0,
        "demo_demand_df": None,
        "demo_dispatch_df": None,
        "demo_summary": None,
        "demo_last_run": None,
        "demo_battery_preservation": 0.35,
        "demo_h2_preservation": 0.45,
        "demo_thermal_cost": 0.75,
        "demo_active_solar": True,
        "demo_active_wind": True,
        "demo_active_battery": True,
        "demo_active_h2": True,
        "demo_active_thermal": True,
    }
    for key, val in defaults.items():
        st.session_state.setdefault(key, val)
    if st.session_state["demo_demand_df"] is None:
        st.session_state["demo_demand_df"] = make_demand_curve(
            profile=st.session_state["demo_demand_profile"], scale=st.session_state["demo_demand_scale"]
        )
    if st.session_state["demo_dispatch_df"] is None:
        _run_demo()


def _config_from_state() -> DemoConfig:
    return DemoConfig(
        demand_scale=float(st.session_state.get("demo_demand_scale", 1.0)),
        demand_profile=str(st.session_state.get("demo_demand_profile", "Operação balanceada")),
        active_solar=bool(st.session_state.get("demo_active_solar", True)),
        active_wind=bool(st.session_state.get("demo_active_wind", True)),
        active_battery=bool(st.session_state.get("demo_active_battery", True)),
        active_h2=bool(st.session_state.get("demo_active_h2", True)),
        active_thermal=bool(st.session_state.get("demo_active_thermal", True)),
        battery_preservation=float(st.session_state.get("demo_battery_preservation", 0.35)),
        h2_preservation=float(st.session_state.get("demo_h2_preservation", 0.45)),
        thermal_cost=float(st.session_state.get("demo_thermal_cost", 0.75)),
    )


def _run_demo() -> None:
    demand = st.session_state.get("demo_demand_df")
    if demand is None:
        demand = make_demand_curve()
        st.session_state["demo_demand_df"] = demand
    result, summary = run_demo_optimizer(demand, _config_from_state())
    st.session_state["demo_dispatch_df"] = result
    st.session_state["demo_summary"] = summary
    st.session_state["demo_last_run"] = datetime.now()


def _fmt_energy(value: float) -> str:
    return f"{value/1000:.2f} MWh" if abs(value) >= 1000 else f"{value:.0f} kWh"


def _header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="page-hero"><div class="hero-eyebrow">{eyebrow}</div><div class="hero-title">{title}</div><div class="hero-sub">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def _section(kicker: str, title: str, note: str = "") -> None:
    st.markdown(
        f'<div class="section-head"><div><small>{kicker}</small><b>{title}</b></div><span>{note}</span></div>',
        unsafe_allow_html=True,
    )


def _kpi(label: str, value: str, note: str) -> None:
    st.markdown(
        f'<div class="kpi-card"><small>{label}</small><b>{value}</b><span>{note}</span></div>',
        unsafe_allow_html=True,
    )


def _sidebar() -> str:
    with st.sidebar:
        st.markdown(
            '<div class="orq-brand"><div class="orq-brand-mark">EM</div><div class="orq-brand-name">ENERGY MULTIMODEL</div><div class="orq-brand-sub">ORCHESTRATION CONSOLE</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="orq-side-label">NAVEGAÇÃO</div>', unsafe_allow_html=True)
        current = st.session_state["orchestrator_page"]
        for page in PAGES:
            if st.button(f"{PAGE_ICONS[page]}  {page}", key=f"orq_nav_{page}", type="primary" if page == current else "secondary", width="stretch"):
                if page != current:
                    st.session_state["orchestrator_page"] = page
                    st.rerun()
        st.divider()
        st.markdown('<div class="orq-side-label">ESTADO DO SISTEMA</div>', unsafe_allow_html=True)
        summary = st.session_state.get("demo_summary") or {}
        last = st.session_state.get("demo_last_run")
        last_txt = last.strftime("%d/%m/%Y %H:%M:%S") if last else "Ainda não executado"
        st.markdown(
            f'<div class="orq-side-status"><small>EXECUÇÃO</small><b>{summary.get("status", "MODO TESTE")}</b></div>'
            f'<div class="orq-side-status"><small>HORIZONTE</small><b>24 h · 15 min</b></div>'
            f'<div class="orq-side-status"><small>ÚLTIMA RODADA</small><b>{last_txt}</b></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="margin-top:.65rem"><span class="mode-test">● MODO TESTE · DADOS SINTÉTICOS</span></div>', unsafe_allow_html=True)
        st.caption("A interface já segue o contrato futuro do otimizador; o solver definitivo ainda não está conectado.")
    return st.session_state["orchestrator_page"]


def _base_layout(fig: go.Figure, height: int = 350, ytitle: str = "Potência [kW]") -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=36, r=18, t=18, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=10)),
        font=dict(family="Arial", color="#334650"),
        xaxis=dict(showgrid=False, title=None),
        yaxis=dict(gridcolor="#EDF1F3", zerolinecolor="#DDE4E8", title=ytitle),
    )
    return fig


def _dispatch_figure(d: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    stacks = [
        ("Solar", "P_solar_kW", SOURCE_COLORS["solar"]),
        ("Eólica", "P_eolica_kW", SOURCE_COLORS["wind"]),
        ("Bateria · descarga", "P_bateria_descarga_kW", SOURCE_COLORS["battery"]),
        ("H₂ / PEMFC", "P_H2_kW", SOURCE_COLORS["h2"]),
        ("Térmica", "P_termica_kW", SOURCE_COLORS["thermal"]),
    ]
    for name, col, color in stacks:
        fig.add_trace(go.Scatter(x=d["timestamp"], y=d[col], name=name, mode="lines", stackgroup="one", line=dict(width=0.8, color=color)))
    fig.add_trace(go.Scatter(x=d["timestamp"], y=d["P_demanda_kW"], name="Demanda", mode="lines", line=dict(width=3, color=SOURCE_COLORS["demand"])))
    return _base_layout(fig, 385)


def _soc_excess_figure(d: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d["timestamp"], y=d["SOC_bateria_pct"], name="SOC bateria", mode="lines", line=dict(width=2.5, color=SOURCE_COLORS["battery"])))
    fig.add_trace(go.Scatter(x=d["timestamp"], y=d["P_excedente_kW"], name="Excedente", mode="lines", yaxis="y2", line=dict(width=2, dash="dot", color=SOURCE_COLORS["excess"])))
    fig.update_layout(yaxis2=dict(title="Excedente [kW]", overlaying="y", side="right", showgrid=False))
    return _base_layout(fig, 260, "SOC [%]")


def _run_strip(summary: dict) -> None:
    order = " → ".join(SOURCE_LABELS[x] for x in summary.get("dispatch_order", []))
    st.markdown(
        '<div class="run-strip">'
        f'<div class="run-cell"><small>Status</small><b>{summary.get("status", "—")}</b></div>'
        '<div class="run-cell"><small>Horizonte</small><b>24 h</b></div>'
        '<div class="run-cell"><small>Resolução</small><b>15 min</b></div>'
        f'<div class="run-cell"><small>Ordem despachável</small><b>{order or "—"}</b></div>'
        f'<div class="run-cell"><small>Violação de carga</small><b>{summary.get("unserved_energy_kwh",0):.2f} kWh</b></div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _overview_page() -> None:
    d = st.session_state["demo_dispatch_df"]
    s = st.session_state["demo_summary"]
    _header(
        "Operação coordenada · Resultado do otimizador",
        "VISÃO GERAL DO DESPACHO",
        "Tela principal da aplicação. Aqui o usuário lê o resultado consolidado da operação antes de entrar nos detalhes de carga, otimização ou modelos.",
    )
    _run_strip(s)

    k = st.columns(6, gap="small")
    with k[0]: _kpi("Demanda", _fmt_energy(s["demand_energy_kwh"]), f"Pico {s['peak_demand_kw']:.0f} kW")
    with k[1]: _kpi("Renováveis", f"{s['renewable_share_pct']:.1f}%", "parcela da energia atendida")
    with k[2]: _kpi("Térmica", _fmt_energy(s["thermal_energy_kwh"]), "energia despachada")
    with k[3]: _kpi("Bateria", _fmt_energy(s["battery_discharge_kwh"]), f"SOC final {s['final_soc_pct']:.0f}%")
    with k[4]: _kpi("H₂ / PEMFC", _fmt_energy(s["h2_energy_kwh"]), f"{s['h2_consumed_kg']:.2f} kg H₂")
    with k[5]: _kpi("Excedente", _fmt_energy(s["excess_energy_kwh"]), "geração não aproveitada")

    left, right = st.columns([1.65, .72], gap="medium")
    with left:
        _section("Despacho", "Potência por fonte × demanda", "solar/eólica entram na disponibilidade máxima")
        with st.container(border=True):
            st.plotly_chart(_dispatch_figure(d), width="stretch", config={"displaylogo": False})
    with right:
        _section("Operação", "Alertas e observações")
        min_soc = s["min_soc_pct"]
        st.markdown(
            '<div class="alert-card alert-ok"><b>✓ Balanço atendido</b><p>Não há energia não atendida no cenário atual.</p></div>'
            if s["unserved_energy_kwh"] < 0.01 else
            f'<div class="alert-card alert-warn"><b>⚠ Déficit de atendimento</b><p>{s["unserved_energy_kwh"]:.2f} kWh não foram atendidos.</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="alert-card {"alert-warn" if min_soc < 25 else "alert-info"}"><b>🔋 SOC mínimo · {min_soc:.1f}%</b><p>Reserva operacional configurada em 20%. A página de modelos mostra a trajetória completa.</p></div>',
            unsafe_allow_html=True,
        )
        if s["excess_energy_kwh"] > 1:
            st.markdown(f'<div class="alert-card alert-info"><b>↗ Excedente renovável</b><p>{s["excess_energy_kwh"]:.1f} kWh ficaram sem uso após o carregamento da bateria.</p></div>', unsafe_allow_html=True)
        st.markdown('<div class="callout">Este bloco será o lugar ideal para <b>alertas reais do solver</b>: restrição ativa, rampa, SOC, combustível, déficit, clipping e inconsistências de entrada.</div>', unsafe_allow_html=True)

    _section("Estado", "Bateria e excedente ao longo do dia")
    with st.container(border=True):
        st.plotly_chart(_soc_excess_figure(d), width="stretch", config={"displaylogo": False})

    _section("Participação", "Leitura rápida por recurso")
    cols = st.columns(5, gap="small")
    metrics = [
        ("Solar", s["solar_energy_kwh"], "fonte não despachável", "solar"),
        ("Eólica", s["wind_energy_kwh"], "fonte não despachável", "wind"),
        ("Bateria", s["battery_discharge_kwh"], "energia descarregada", "battery"),
        ("H₂ / PEMFC", s["h2_energy_kwh"], "geração despachável", "h2"),
        ("Térmica", s["thermal_energy_kwh"], "geração despachável", "thermal"),
    ]
    for col, (label, energy, note, source) in zip(cols, metrics):
        with col:
            share = 100 * energy / max(s["demand_energy_kwh"], 1e-9)
            st.markdown(f'<div class="source-mini"><small>{label}</small><b>{note}</b><strong>{_fmt_energy(energy)}</strong><p>{share:.1f}% da demanda diária</p></div>', unsafe_allow_html=True)


def _load_page() -> None:
    _header(
        "Entrada operacional",
        "MÓDULO DE CARGA",
        "A carga é a entrada central do despacho. Nesta versão de teste, ela pode ser gerada por perfil sintético ou carregada por CSV antes de ser entregue ao otimizador.",
    )
    left, right = st.columns([.72, 1.45], gap="medium")
    with left:
        with st.container(border=True):
            st.markdown("#### Configuração da carga")
            mode = st.radio("Fonte da curva", ["Perfil sintético", "CSV"], horizontal=True)
            if mode == "Perfil sintético":
                profile = st.selectbox("Perfil", ["Operação balanceada", "Dois picos", "Pico noturno", "Carga quase constante"], index=["Operação balanceada", "Dois picos", "Pico noturno", "Carga quase constante"].index(st.session_state["demo_demand_profile"]))
                scale = st.slider("Escala da demanda", 0.50, 1.60, float(st.session_state["demo_demand_scale"]), 0.05)
                st.caption("Horizonte fixo do protótipo: 24 h · resolução: 15 min.")
                if st.button("APLICAR CURVA AO CENÁRIO", type="primary", width="stretch"):
                    st.session_state["demo_demand_profile"] = profile
                    st.session_state["demo_demand_scale"] = scale
                    st.session_state["demo_demand_df"] = make_demand_curve(profile=profile, scale=scale)
                    _run_demo()
                    st.success("Curva aplicada e cenário recalculado.")
                    st.rerun()
            else:
                up = st.file_uploader("CSV de carga", type=["csv"], help="Contrato mínimo: timestamp e P_demanda_kW")
                st.markdown('<div class="callout"><b>Contrato mínimo</b><br>timestamp · P_demanda_kW<br><br>O restante das colunas pode existir e será ignorado pelo protótipo.</div>', unsafe_allow_html=True)
                if up is not None:
                    try:
                        raw = pd.read_csv(up, sep=None, engine="python")
                        if not {"timestamp", "P_demanda_kW"}.issubset(raw.columns):
                            st.error("O CSV precisa conter timestamp e P_demanda_kW.")
                        else:
                            raw["timestamp"] = pd.to_datetime(raw["timestamp"])
                            if st.button("USAR ESTE CSV", type="primary", width="stretch"):
                                st.session_state["demo_demand_df"] = raw[["timestamp", "P_demanda_kW"]].copy()
                                _run_demo()
                                st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível ler o CSV: {exc}")
            template = make_demand_curve().head(8).to_csv(index=False).encode("utf-8")
            st.download_button("Baixar template CSV", template, "template_carga.csv", "text/csv", width="stretch")

    demand = st.session_state["demo_demand_df"]
    dt_h = (pd.to_datetime(demand["timestamp"].iloc[1]) - pd.to_datetime(demand["timestamp"].iloc[0])).total_seconds()/3600 if len(demand) > 1 else 0.25
    energy = float(demand["P_demanda_kW"].sum() * dt_h)
    peak = float(demand["P_demanda_kW"].max())
    avg = float(demand["P_demanda_kW"].mean())
    with right:
        a,b,c,d = st.columns(4, gap="small")
        a.metric("Energia diária", _fmt_energy(energy))
        b.metric("Pico", f"{peak:.1f} kW")
        c.metric("Média", f"{avg:.1f} kW")
        d.metric("Fator de carga", f"{100*avg/peak:.1f}%")
        with st.container(border=True):
            fig = go.Figure(go.Scatter(x=demand["timestamp"], y=demand["P_demanda_kW"], mode="lines", name="Demanda", fill="tozeroy", line=dict(width=2.5, color=SOURCE_COLORS["demand"])))
            st.plotly_chart(_base_layout(fig, 355), width="stretch", config={"displaylogo":False})
        with st.expander("Pré-visualizar dados de entrada"):
            st.dataframe(demand, width="stretch", hide_index=True, height=230)


def _optimizer_page() -> None:
    _header(
        "EMS real integrado",
        "OTIMIZADOR",
        "O motor de despacho multifonte da ramificação de Marília já faz parte desta versão. "
        "Ele usa os modelos físicos da plataforma para caracterizar as fontes e resolve o despacho por "
        "GA, GWO, NGO ou SQP com refino SLSQP.",
    )

    st.markdown(
        '<div class="optimizer-map"><div class="opt-step"><small>1 · MODELOS</small><b>Solar · Eólica · PEMFC · Bateria · Térmica</b></div>'
        '<div class="opt-arrow">→</div><div class="opt-step"><small>2 · EMS REAL</small><b>Envelope + custos + restrições + horizonte N</b></div>'
        '<div class="opt-arrow">→</div><div class="opt-step"><small>3 · DESPACHO</small><b>Potência · stacks · SOC · H₂ · custos</b></div></div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.0, 1.15], gap="medium")
    with left:
        with st.container(border=True):
            st.markdown("#### Motor EMS · primeira integração")
            st.markdown(
                """
- **Solar e eólica:** não despacháveis; abatem a carga antes da otimização.
- **PEMFC:** número de stacks + potência; custo derivado da curva física kg H₂/kWh.
- **Bateria:** potência de carga/descarga, SOC e custo de degradação.
- **Térmica:** mínimo técnico, rampa, CVU e custo de partida.
- **Solver:** GA / GWO / NGO como busca inicial opcional + refinamento SLSQP.
"""
            )
            st.markdown(
                '<div class="callout good-callout"><b>Correções desta integração:</b> potência líquida da PEMFC não recebe η DC/DC duas vezes; '
                'o vertimento total inclui renováveis; e o receding horizon resolve até o último minuto da missão.</div>',
                unsafe_allow_html=True,
            )
            if st.button("⚡ ABRIR EMS REAL →", key="open_real_ems", type="primary", width="stretch"):
                st.session_state["energy_source"] = "ems"
                st.rerun()

    with right:
        with st.container(border=True):
            st.markdown("#### Estado da integração")
            a, b = st.columns(2)
            a.metric("Núcleo EMS", "Integrado")
            b.metric("Modelos físicos", "Reutilizados")
            st.markdown("**Fluxo já disponível:** configurar carga → escolher fontes → executar → comparar algoritmos → validar H₂ → exportar pacote e resultados.")
            st.caption(
                "A Visão Geral, Resultados dos Modelos e Exportação do Orchestrator ainda exibem o protótipo sintético "
                "MODO TESTE. Nesta primeira etapa, o EMS real foi preservado como módulo completo para evitar alterar "
                "a lógica de Marília além das correções acordadas. A próxima etapa pode ligar as saídas reais do EMS "
                "diretamente a essas páginas do Orchestrator."
            )

        with st.expander("Pendências para conversar com Marília", expanded=False):
            st.markdown(
                """
- permitir que excedente solar/eólico carregue a bateria antes do curtailment;
- avaliar o efeito e a escolha do horizonte **N**;
- discutir custo/degradação de partidas da PEMFC;
- decidir se entram degradação eletroquímica e penalidade de flutuação da FC;
- revisar a reconstrução heurística do número anterior de stacks usada na restrição de rampa.
"""
            )


def _model_figure(frame: pd.DataFrame, model: str) -> go.Figure:
    fig = go.Figure()
    for col in frame.columns:
        if col == "timestamp" or col in {"SOC [%]", "H₂ acumulado [kg]", "Rampa [kW/passo]"}:
            continue
        dash = "dash" if "Solicitado" in col else "solid"
        fig.add_trace(go.Scatter(x=frame["timestamp"], y=frame[col], name=col, mode="lines", line=dict(width=2.2, dash=dash)))
    return _base_layout(fig, 330)


def _models_page() -> None:
    d = st.session_state["demo_dispatch_df"]
    s = st.session_state["demo_summary"]
    _header(
        "Diagnóstico operacional",
        "RESULTADOS DOS MODELOS",
        "O otimizador decide a potência desejada; cada modelo mostra o que foi solicitado, o que conseguiu entregar e quais estados ou limites foram relevantes.",
    )
    model = st.segmented_control("Modelo analisado", options=["solar","wind","battery","h2","thermal"], format_func=lambda x: SOURCE_LABELS[x], default="solar")
    if model is None:
        model = "solar"
    frame = build_demo_model_frame(d, model)
    energy_map = {
        "solar": s["solar_energy_kwh"], "wind": s["wind_energy_kwh"], "battery": s["battery_discharge_kwh"],
        "h2": s["h2_energy_kwh"], "thermal": s["thermal_energy_kwh"],
    }
    left, right = st.columns([.57, 1.43], gap="medium")
    with left:
        with st.container(border=True):
            st.markdown(f"### {SOURCE_LABELS[model]}")
            st.markdown(f'<span class="result-tag">● MODELO ATIVO · RESULTADO DEMO</span>', unsafe_allow_html=True)
            st.metric("Energia no horizonte", _fmt_energy(energy_map[model]))
            st.metric("Participação na demanda", f"{100*energy_map[model]/max(s['demand_energy_kwh'],1):.1f}%")
            if model == "battery":
                st.metric("SOC mínimo", f"{s['min_soc_pct']:.1f}%")
                st.metric("SOC final", f"{s['final_soc_pct']:.1f}%")
                st.caption("Convenção: potência positiva = descarga; negativa = carga.")
            elif model == "h2":
                st.metric("Consumo de H₂", f"{s['h2_consumed_kg']:.2f} kg")
                st.metric("Limite de potência", "50 kW")
            elif model == "thermal":
                max_ramp = frame["Rampa [kW/passo]"].abs().max()
                st.metric("Rampa máxima usada", f"{max_ramp:.1f} kW/passo")
                st.metric("Limite de potência", "85 kW")
            else:
                st.metric("Pico disponível", f"{frame['Disponível [kW]'].max():.1f} kW")
                st.caption("Solar/eólica são tratados como não despacháveis: o otimizador recebe sua disponibilidade, não uma potência arbitrária.")
    with right:
        with st.container(border=True):
            st.plotly_chart(_model_figure(frame, model), width="stretch", config={"displaylogo":False})
        state_cols = [c for c in frame.columns if c in {"SOC [%]", "H₂ acumulado [kg]", "Rampa [kW/passo]"}]
        if state_cols:
            with st.container(border=True):
                fig2 = go.Figure()
                for col in state_cols:
                    fig2.add_trace(go.Scatter(x=frame["timestamp"], y=frame[col], name=col, mode="lines", line=dict(width=2.2)))
                st.plotly_chart(_base_layout(fig2, 215, state_cols[0]), width="stretch", config={"displaylogo":False})
    with st.expander("Dados temporais do modelo"):
        st.dataframe(frame, width="stretch", hide_index=True, height=250)


def _launch_legacy(source: str) -> None:
    st.session_state["energy_source"] = source
    st.rerun()


def _test_models_page() -> None:
    _header(
        "Biblioteca técnica",
        "TESTAR MODELOS DE FORMA INDEPENDENTE",
        "A antiga tela inicial passa a viver aqui. Ela serve para validar cada modelo isoladamente, sem confundir essa função com a operação coordenada do sistema.",
    )
    cards = [
        ("☀️", "Solar", "Entrada meteorológica, três modelos FV, comparação e exportação.", "solar"),
        ("🌬️", "Eólica", "Curva do fabricante, densidade do ar, potência, energia e fator de capacidade.", "wind"),
        ("🔥", "Térmica", "Usina termelétrica e pequena unidade geradora com dinâmica operacional.", "thermal"),
        ("🔋", "Bateria", "Tremblay–Dessaint/Shepherd e circuito equivalente Li-Ion 2RC.", "battery"),
        ("💧", "H₂ / PEMFC", "Stack equivalente, potência solicitada, dinâmica, eficiência e consumo de H₂.", "h2"),
        ("🔀", "MIX atual", "Interface MIX já existente, preservada como bancada técnica durante a transição.", "mix"),
    ]
    for row in range(2):
        cols = st.columns(3, gap="medium")
        for col, (icon, title, copy, source) in zip(cols, cards[row*3:(row+1)*3]):
            with col:
                st.markdown(f'<div class="test-card"><div class="test-icon">{icon}</div><h4>{title}</h4><p>{copy}</p></div>', unsafe_allow_html=True)
                if st.button(f"ABRIR {title.upper()} →", key=f"test_{source}", type="primary", width="stretch"):
                    _launch_legacy(source)
    st.markdown('<div class="callout good-callout"><b>Separação correta de responsabilidades:</b> esta página responde “o modelo funciona sozinho?”. A Visão Geral e o Otimizador respondem “como o sistema inteiro deve operar?”.</div>', unsafe_allow_html=True)


def _export_bundle(dispatch: pd.DataFrame, demand: pd.DataFrame, summary: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("despacho_otimizador.csv", dispatch.to_csv(index=False))
        zf.writestr("curva_carga.csv", demand.to_csv(index=False))
        zf.writestr("resumo_execucao.json", json.dumps(summary, indent=2, ensure_ascii=False))
        zf.writestr("configuracao_demo.json", json.dumps(asdict(_config_from_state()), indent=2, ensure_ascii=False))
    return buf.getvalue()


def _export_page() -> None:
    d = st.session_state["demo_dispatch_df"]
    demand = st.session_state["demo_demand_df"]
    s = st.session_state["demo_summary"]
    _header(
        "Saídas e rastreabilidade",
        "EXPORTAR RESULTADOS",
        "Arquivos separados para consumo técnico e um pacote completo da rodada. No futuro, esta página também pode gerar relatório e artefatos de auditoria do otimizador.",
    )
    a,b,c = st.columns(3, gap="medium")
    with a:
        with st.container(border=True):
            st.markdown("#### Despacho completo")
            st.caption("Séries temporais de demanda, fontes, SOC, H₂, excedente e energia não atendida.")
            st.download_button("⬇ CSV DESPACHO", d.to_csv(index=False).encode("utf-8"), "despacho_otimizador_demo.csv", "text/csv", type="primary", width="stretch")
    with b:
        with st.container(border=True):
            st.markdown("#### Curva de carga")
            st.caption("Entrada efetivamente usada pela última execução do cenário.")
            st.download_button("⬇ CSV CARGA", demand.to_csv(index=False).encode("utf-8"), "curva_carga_demo.csv", "text/csv", type="primary", width="stretch")
    with c:
        with st.container(border=True):
            st.markdown("#### Pacote da rodada")
            st.caption("Despacho + carga + resumo + configuração em um único ZIP rastreável.")
            st.download_button("⬇ ZIP COMPLETO", _export_bundle(d, demand, s), "rodada_energy_multimodel_demo.zip", "application/zip", type="primary", width="stretch")
    _section("Pré-visualização", "Tabela de despacho")
    st.dataframe(d, width="stretch", hide_index=True, height=410)


def render_orchestrator_app() -> None:
    st.markdown(ORCHESTRATOR_CSS, unsafe_allow_html=True)
    _init_state()
    page = _sidebar()
    if page == "Visão Geral":
        _overview_page()
    elif page == "Módulo de Carga":
        _load_page()
    elif page == "Otimizador":
        _optimizer_page()
    elif page == "Resultados dos Modelos":
        _models_page()
    elif page == "Testar Modelos":
        _test_models_page()
    else:
        _export_page()
