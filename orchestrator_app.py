"""Console unificado do Energy MultiModel.

Fluxo operacional único:
Carga -> Modelos -> Otimizador -> Resultados do Otimizador -> Resultados dos Modelos -> Exportação.

O EMS de Marília é usado como motor interno. Não existe uma segunda app EMS
aberta dentro desta interface: todas as páginas compartilham o mesmo estado.
"""
from __future__ import annotations

from datetime import datetime
import copy

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.pv_database import MODULE_DB, get_module
from config.wind_turbine_database import TURBINE_DB, get_turbine
from ems_integration import ponte
from models.battery_model import BATTERY_2RC, BATTERY_MODEL_LABELS, BATTERY_TREMBLAY, TREMBLAY_BATTERIES
from visualization import ems_plots as EMSP
import orchestrator_runtime as RT


PAGES = (
    "Visão Geral",
    "Módulo de Carga",
    "Modelos",
    "Otimizador",
    "Resultados do Otimizador",
    "Resultados dos Modelos",
    "Exportar Resultados",
)
PAGE_ICONS = {
    "Visão Geral": "▦",
    "Módulo de Carga": "⌁",
    "Modelos": "◈",
    "Otimizador": "◎",
    "Resultados do Otimizador": "◫",
    "Resultados dos Modelos": "▤",
    "Exportar Resultados": "⇩",
}
SOURCE_LABELS = {"solar": "Solar", "wind": "Eólica", "battery": "Bateria", "h2": "H₂ / PEMFC", "thermal": "Térmica"}
SOURCE_ICONS = {"solar": "☀️", "wind": "🌬️", "battery": "🔋", "h2": "💧", "thermal": "🔥"}
CHART_CONFIG = {"displaylogo": False, "responsive": True, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}

ORCHESTRATOR_CSS = """
<style>
:root{--navy:#203746;--navy2:#182A36;--blue:#087BA8;--cyan:#29A6B8;--ink:#18242D;--muted:#6D7D88;--border:#DCE3E8;--soft:#F4F8FA;--green:#198B68;--amber:#BC7B12;--red:#C84C4C}
.block-container{max-width:1780px;padding-top:1.15rem;padding-bottom:2rem}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#182A36 0%,#203746 100%)!important}
[data-testid="stSidebar"]>div{padding-top:.7rem}
.orq-brand{padding:.55rem .2rem 1rem;text-align:center}.orq-brand-mark{width:48px;height:48px;margin:0 auto .45rem;border-radius:13px;display:grid;place-items:center;background:linear-gradient(135deg,#0B87B4,#36B4B8);color:white;font-weight:950;font-size:1.02rem;box-shadow:0 7px 20px rgba(0,0,0,.15)}
.orq-brand-name{color:#FFF;font-size:.91rem;font-weight:900;letter-spacing:.14em}.orq-brand-sub{color:#90A9B8;font-size:.58rem;font-weight:800;letter-spacing:.12em;margin-top:.22rem}.orq-side-label{color:#89A2B1;font-size:.61rem;font-weight:900;letter-spacing:.14em;margin:.4rem 0 .35rem}
.orq-side-status{border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.045);border-radius:9px;padding:.58rem .68rem;margin-top:.5rem}.orq-side-status small{color:#8FA8B6!important;font-size:.57rem;letter-spacing:.1em;font-weight:900}.orq-side-status b{color:white!important;font-size:.73rem;display:block;margin-top:.12rem}
.page-hero{border:1px solid var(--border);border-radius:12px;padding:.8rem 1rem;background:linear-gradient(90deg,#FFF 0%,#F7FBFD 100%);margin-bottom:.72rem}.hero-eyebrow{color:var(--blue);font-size:.62rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase}.hero-title{color:#14232D;font-size:1.65rem;line-height:1.08;font-weight:950;letter-spacing:-.035em;margin:.18rem 0 .12rem}.hero-sub{color:#687A85;font-size:.76rem;line-height:1.45}
.kpi-card{border:1px solid var(--border);border-radius:10px;background:white;padding:.67rem .74rem;min-height:92px;box-shadow:0 2px 10px rgba(36,55,70,.035)}.kpi-card small{color:#7A8993;font-size:.58rem;font-weight:900;letter-spacing:.095em;text-transform:uppercase}.kpi-card b{display:block;color:#18252E;font-size:1.22rem;line-height:1.1;margin:.18rem 0 .14rem;font-weight:930}.kpi-card span{color:#6F808B;font-size:.66rem}
.section-head{display:flex;justify-content:space-between;align-items:end;margin:.8rem 0 .42rem}.section-head small{display:block;color:var(--blue);font-size:.59rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.12rem}.section-head b{color:#1B2A33;font-size:.95rem;font-weight:900}.section-head span{color:#778690;font-size:.67rem}
.callout{border-left:3px solid #1683A8;background:#F0F7FA;border-radius:0 8px 8px 0;padding:.58rem .7rem;color:#456575;font-size:.69rem;line-height:1.48;margin:.38rem 0 .5rem}.good-callout{border-left-color:#2D9271;background:#F1F8F5}.warn-callout{border-left-color:#D29328;background:#FFF8EB}.danger-callout{border-left-color:#C84C4C;background:#FFF2F2}
.flow-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:.45rem;margin:.6rem 0 .9rem}.flow-step{border:1px solid #DDE5EA;border-radius:10px;background:#fff;padding:.55rem .62rem;min-height:86px}.flow-step small{display:block;color:#7B8B94;font-size:.53rem;font-weight:900;letter-spacing:.08em}.flow-step b{display:block;color:#20343F;font-size:.77rem;margin:.15rem 0}.flow-step span{color:#70818C;font-size:.62rem;line-height:1.35}.flow-step.active{border-color:#7FC7DF;box-shadow:0 0 0 2px rgba(41,166,184,.08)}
.model-card{border:1px solid #DDE5EA;border-radius:11px;background:#fff;padding:.68rem .72rem;min-height:116px}.model-card .icon{font-size:1.4rem}.model-card h4{margin:.18rem 0;color:#1C2B34;font-size:.9rem;font-weight:930}.model-card p{color:#71818B;font-size:.65rem;line-height:1.4;margin:.15rem 0}.tag-on,.tag-off{display:inline-block;padding:.18rem .42rem;border-radius:999px;font-size:.57rem;font-weight:900;letter-spacing:.07em}.tag-on{background:#E8F6F1;border:1px solid #C1E7D9;color:#167456}.tag-off{background:#F2F4F5;border:1px solid #DDE2E5;color:#75848D}
.readiness{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.55rem}.ready-card{border:1px solid var(--border);border-radius:10px;padding:.65rem .7rem;background:#fff}.ready-card small{display:block;color:#7A8992;font-size:.56rem;font-weight:900;letter-spacing:.08em}.ready-card b{display:block;color:#1B2932;font-size:.84rem;margin:.13rem 0}.ready-card span{color:#778790;font-size:.62rem}
.result-tag{display:inline-block;padding:.22rem .48rem;border-radius:999px;background:#E8F6F1;border:1px solid #C1E7D9;color:#167456;font-size:.61rem;font-weight:900;letter-spacing:.07em}
.stButton>button[kind="primary"]{background:#087BA8;border-color:#087BA8}.stButton>button{border-radius:8px;font-weight:800}div[data-testid="stMetric"]{border:1px solid #E0E6EA;border-radius:9px;padding:.55rem .62rem;background:white}div[data-testid="stMetric"] label{color:#778690!important;font-size:.64rem!important}div[data-testid="stMetric"] [data-testid="stMetricValue"]{color:#1A2A34;font-size:1.25rem}[data-testid="stDataFrame"]{border:1px solid #E1E7EB;border-radius:9px;overflow:hidden}
@media(max-width:1100px){.flow-grid{grid-template-columns:repeat(3,1fr)}.readiness{grid-template-columns:repeat(2,1fr)}}
</style>
"""


def _init_state() -> None:
    defaults = {
        "orchestrator_page": "Visão Geral",
        "orq_load": None,
        "orq_load_mode": "Walk-forward · embarcação (2 h)",
        "orq_model_spec": RT.default_model_spec(),
        "orq_climate_raw": None,
        "orq_optimizer_config": RT.default_optimizer_config(),
        "orq_result_item": None,
        "orq_model_outputs": {},
        "orq_history": [],
        "orq_run_counter": 0,
        "orq_last_run": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(value)
    if st.session_state["orq_load"] is None:
        st.session_state["orq_load"] = ponte.carga_walkforward("Ideal", "Normal", 12)


def _header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(f'<div class="page-hero"><div class="hero-eyebrow">{eyebrow}</div><div class="hero-title">{title}</div><div class="hero-sub">{subtitle}</div></div>', unsafe_allow_html=True)


def _section(kicker: str, title: str, note: str = "") -> None:
    st.markdown(f'<div class="section-head"><div><small>{kicker}</small><b>{title}</b></div><span>{note}</span></div>', unsafe_allow_html=True)


def _kpi(label: str, value: str, note: str = "") -> None:
    st.markdown(f'<div class="kpi-card"><small>{label}</small><b>{value}</b><span>{note}</span></div>', unsafe_allow_html=True)


def _fmt_energy(v: float) -> str:
    return f"{v/1000:.2f} MWh" if abs(v) >= 1000 else f"{v:.1f} kWh"


def _current_result() -> dict | None:
    item = st.session_state.get("orq_result_item")
    return item["resultado"] if item else None


def _invalidate_result(reason: str) -> None:
    st.session_state["orq_result_item"] = None
    st.session_state["orq_model_outputs"] = {}
    st.session_state["orq_last_run"] = None
    st.session_state["orq_invalidation_reason"] = reason


def _go(page: str) -> None:
    st.session_state["orchestrator_page"] = page
    st.rerun()


def _sidebar() -> str:
    with st.sidebar:
        st.markdown('<div class="orq-brand"><div class="orq-brand-mark">EM</div><div class="orq-brand-name">ENERGY MULTIMODEL</div><div class="orq-brand-sub">UNIFIED EMS CONSOLE</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="orq-side-label">NAVEGAÇÃO</div>', unsafe_allow_html=True)
        current = st.session_state["orchestrator_page"]
        for page in PAGES:
            if st.button(f"{PAGE_ICONS[page]}  {page}", key=f"orq_nav_{page}", type="primary" if page == current else "secondary", width="stretch"):
                if page != current:
                    st.session_state["orchestrator_page"] = page
                    st.rerun()
        st.divider()
        carga = st.session_state.get("orq_load")
        spec = st.session_state.get("orq_model_spec") or {}
        active = RT.active_source_labels(spec)
        item = st.session_state.get("orq_result_item")
        opt = st.session_state.get("orq_optimizer_config") or {}
        st.markdown('<div class="orq-side-label">ESTADO DO SISTEMA</div>', unsafe_allow_html=True)
        carga_txt = f"{len(carga.P_kW)} min · pico {carga.P_kW.max():.0f} kW" if carga is not None else "Não configurada"
        run_txt = f"{item['resultado']['algoritmo']} · concluído" if item else "Aguardando execução"
        last = st.session_state.get("orq_last_run")
        last_txt = last.strftime("%d/%m/%Y %H:%M:%S") if last else "—"
        st.markdown(
            f'<div class="orq-side-status"><small>CARGA</small><b>{carga_txt}</b></div>'
            f'<div class="orq-side-status"><small>MODELOS ATIVOS</small><b>{len(active)} · {" · ".join(active) if active else "nenhum"}</b></div>'
            f'<div class="orq-side-status"><small>OTIMIZADOR</small><b>{run_txt} · N={int(opt.get("N",3))}</b></div>'
            f'<div class="orq-side-status"><small>ÚLTIMA RODADA</small><b>{last_txt}</b></div>',
            unsafe_allow_html=True,
        )
        st.caption("Um único estado: carga, modelos, EMS, resultados e exportação compartilham a mesma rodada.")
    return st.session_state["orchestrator_page"]


def _flow() -> None:
    current = st.session_state["orchestrator_page"]
    pairs = [
        ("Módulo de Carga", "1 · Carga", "define a missão"),
        ("Modelos", "2 · Modelos", "ativa e parametriza fontes"),
        ("Otimizador", "3 · Otimizador", "configura e roda o EMS"),
        ("Resultados do Otimizador", "4 · Resultado EMS", "despacho e custos"),
        ("Resultados dos Modelos", "5 · Modelos", "resposta física da rodada"),
        ("Exportar Resultados", "6 · Exportação", "pacote auditável"),
    ]
    html = '<div class="flow-grid">'
    for page, title, desc in pairs:
        html += f'<div class="flow-step {"active" if current == page else ""}"><small>FLUXO ÚNICO</small><b>{title}</b><span>{desc}</span></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def _overview_page() -> None:
    _header("Arquitetura integrada", "ENERGY MULTIMODEL + EMS", "A aplicação agora usa o otimizador como motor interno. A carga e os modelos configurados nas páginas anteriores entram diretamente na mesma rodada do EMS.")
    _flow()
    carga = st.session_state["orq_load"]
    spec = st.session_state["orq_model_spec"]
    item = st.session_state.get("orq_result_item")
    active = RT.active_source_labels(spec)
    st.markdown(
        '<div class="callout good-callout"><b>Integração real:</b> não existe uma segunda interface do EMS. '
        'O botão Rodar da página Otimizador calcula os modelos ativos, monta o contrato interno, executa o solver de Marília e devolve as saídas para estas mesmas páginas.</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="readiness">'
                f'<div class="ready-card"><small>1 · CARGA</small><b>✓ {carga.descricao}</b><span>{len(carga.P_kW)} passos de 1 min</span></div>'
                f'<div class="ready-card"><small>2 · MODELOS</small><b>{len(active)} ativos</b><span>{" · ".join(active)}</span></div>'
                f'<div class="ready-card"><small>3 · EMS</small><b>{"✓ Rodado" if item else "Pronto para rodar"}</b><span>{item["resultado"]["algoritmo"] if item else "configuração na página Otimizador"}</span></div>'
                f'<div class="ready-card"><small>4 · SAÍDAS</small><b>{"Disponíveis" if item else "Aguardando"}</b><span>despacho · modelos · exportação</span></div>'
                '</div>', unsafe_allow_html=True)
    if item is None:
        st.info("Ainda não há uma rodada otimizada nesta sessão. A carga e os modelos já estão configurados; siga para Otimizador quando quiser executar.")
        c1, c2, c3 = st.columns(3)
        if c1.button("AJUSTAR CARGA →", width="stretch"):
            _go("Módulo de Carga")
        if c2.button("AJUSTAR MODELOS →", width="stretch"):
            _go("Modelos")
        if c3.button("IR AO OTIMIZADOR →", type="primary", width="stretch"):
            _go("Otimizador")
        return

    r = item["resultado"]
    rel = r["rel"]
    kv = r["k_validos"]
    E_demand = float(np.sum(r["P_load_kW"][:kv]) * r["Ts_s"] / 3600.0)
    E = EMSP.energias_barramento(r)
    h2 = rel["consumo_fisico"].get("fc", {}).get("valor")
    cols = st.columns(6, gap="small")
    with cols[0]: _kpi("Demanda", _fmt_energy(E_demand), f"pico {np.max(r['P_load_kW'][:kv]):.0f} kW")
    with cols[1]: _kpi("Custo", f"R$ {rel['custo_total_rs']:,.2f}", r["algoritmo"])
    with cols[2]: _kpi("H₂", f"{h2:.2f} kg" if h2 is not None else "—", "curva física PEMFC")
    with cols[3]: _kpi("Não atendida", _fmt_energy(rel["energia_nao_atendida_kWh"]), "déficit")
    with cols[4]: _kpi("Vertida", _fmt_energy(rel["energia_vertida_kWh"]), "todas as fontes")
    with cols[5]: _kpi("Fontes", str(len(E)), "participaram do atendimento")
    left, right = st.columns([1.55, .75], gap="medium")
    with left:
        with st.container(border=True):
            st.plotly_chart(EMSP.fig_despacho(r), width="stretch", config=CHART_CONFIG)
    with right:
        with st.container(border=True):
            st.plotly_chart(EMSP.fig_participacao(r), width="stretch", config=CHART_CONFIG)
    if r.get("avisos"):
        with st.expander(f"Avisos da última rodada ({len(r['avisos'])})"):
            for a in r["avisos"]:
                st.warning(a)


def _load_page() -> None:
    _header("Entrada operacional", "MÓDULO DE CARGA", "Define a demanda que será entregue ao EMS. Esta curva fica no estado comum da aplicação e será usada diretamente quando a otimização for executada.")
    _flow()
    current: ponte.PerfilCarga = st.session_state["orq_load"]
    left, right = st.columns([.78, 1.42], gap="medium")
    new_load = None
    with left:
        with st.container(border=True):
            st.markdown("#### Configuração da missão")
            mode = st.radio("Fonte da carga", ["Walk-forward · embarcação (2 h)", "COPEL B1", "CSV próprio"], index=["Walk-forward · embarcação (2 h)", "COPEL B1", "CSV próprio"].index(st.session_state.get("orq_load_mode", "Walk-forward · embarcação (2 h)")))
            try:
                if mode.startswith("Walk"):
                    opts = ponte.opcoes_walkforward()
                    c1, c2, c3 = st.columns(3)
                    scenario = c1.selectbox("Cenário", sorted(opts.scenario.unique()), index=sorted(opts.scenario.unique()).index("Ideal"))
                    profile = c2.selectbox("Perfil", ["Econômico", "Normal", "Máxima"], index=1)
                    hour = c3.selectbox("Início", sorted(opts.start_hour.unique()), index=4, format_func=lambda h: f"{int(h):02d}:00")
                    new_load = ponte.carga_walkforward(scenario, profile, int(hour))
                elif mode.startswith("COPEL"):
                    c1, c2, c3 = st.columns(3)
                    day = c1.selectbox("Dia", ["util", "sabado", "domingo"], format_func=lambda x: {"util":"Dia útil","sabado":"Sábado","domingo":"Domingo"}[x])
                    start = c2.number_input("Início [h]", 0, 23, 8)
                    dur = c3.number_input("Duração [min]", 30, 1440, 120, step=30)
                    new_load = ponte.recortar(ponte.carga_copel(day), start * 60, min(dur, 1439 - start * 60))
                else:
                    up = st.file_uploader("CSV de carga", type=["csv"], help="Aceita t_min/P_kW ou timestamp/P_kW.")
                    if up is not None:
                        raw = pd.read_csv(up, sep=None, engine="python")
                        base = ponte.carga_de_dataframe(raw, up.name)
                        c1, c2 = st.columns(2)
                        start = c1.number_input("Início [min]", 0, max(0, int(base.duracao_min)-5), 0)
                        dur = c2.number_input("Duração [min]", 5, max(5, int(base.duracao_min)), min(120, max(5, int(base.duracao_min))))
                        new_load = ponte.recortar(base, start, dur)
                    else:
                        st.caption("Carregue o CSV para visualizar e aplicar a nova missão.")
            except Exception as exc:
                st.error(f"Não foi possível preparar a carga: {exc}")
                new_load = None
            if st.button("APLICAR CARGA À APLICAÇÃO", type="primary", width="stretch", disabled=new_load is None):
                st.session_state["orq_load"] = new_load
                st.session_state["orq_load_mode"] = mode
                _invalidate_result("A carga foi alterada.")
                st.success("Carga aplicada. O otimizador passará a usar esta missão.")
                st.rerun()
    show = new_load if new_load is not None else current
    with right:
        energy = float(np.sum(show.P_kW) / 60.0)
        a, b, c, d = st.columns(4)
        a.metric("Energia", _fmt_energy(energy))
        b.metric("Pico", f"{np.max(show.P_kW):.1f} kW")
        c.metric("Média", f"{np.mean(show.P_kW):.1f} kW")
        d.metric("Passos", str(len(show.P_kW)), "1 min")
        st.plotly_chart(EMSP.fig_carga(show.t_min, show.P_kW, show.descricao), width="stretch", config=CHART_CONFIG)
        with st.expander("Dados da curva"):
            df = show.df().copy()
            df.insert(0, "timestamp", RT.load_timestamps(show))
            st.dataframe(df, hide_index=True, width="stretch", height=260)
    st.caption(f"Carga atualmente salva para o EMS: **{current.descricao}**.")


def _model_summary_cards(spec: dict) -> None:
    cards = []
    for key in ("solar", "wind", "battery", "fc", "thermal"):
        active = bool(spec.get(key, {}).get("active"))
        detail = ""
        s = spec.get(key, {})
        if key == "solar":
            detail = f"{s.get('module_key','—')} · {s.get('n_series','—')}×{s.get('n_parallel','—')} módulos"
        elif key == "wind":
            detail = f"{s.get('turbine_key','—')} · {s.get('turbine_count','—')} un."
        elif key == "battery":
            detail = f"{s.get('Ns','—')}s × {s.get('Np','—')}p · SOC {100*s.get('soc0',0):.0f}%"
        elif key == "fc":
            detail = f"{s.get('N_fc','—')} stacks · base {s.get('base','—')}"
        else:
            detail = f"{s.get('pmax_kW','—')} kW · CVU {s.get('cvu','—')} R$/MWh"
        cards.append(f'<div class="model-card"><div class="icon">{SOURCE_ICONS[key]}</div><h4>{SOURCE_LABELS[key]}</h4><span class="{"tag-on" if active else "tag-off"}">{"ATIVO" if active else "DESATIVADO"}</span><p>{detail}</p></div>')
    cols = st.columns(5, gap="small")
    for c, html in zip(cols, cards):
        with c:
            st.markdown(html, unsafe_allow_html=True)


def _models_config_page() -> None:
    _header("Arquitetura física", "MODELOS", "Ative as fontes que pertencem à rodada e configure seus parâmetros. O otimizador usará exatamente esta seleção; não é necessário abrir outra aplicação.")
    _flow()
    saved = st.session_state["orq_model_spec"]
    _model_summary_cards(saved)
    st.markdown("---")
    with st.form("orq_models_form"):
        st.markdown("#### Fontes renováveis")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            solar_on = st.toggle("☀️ Solar ativo", bool(saved["solar"]["active"]))
            pv_keys = list(MODULE_DB)
            pv_key = st.selectbox("Módulo FV", pv_keys, index=pv_keys.index(saved["solar"].get("module_key", "CS7L-590MS")) if saved["solar"].get("module_key") in pv_keys else 0, disabled=not solar_on)
            s1, s2, s3 = st.columns(3)
            ns = s1.number_input("Série", 1, 200, int(saved["solar"].get("n_series",2)), disabled=not solar_on)
            np_ = s2.number_input("Paralelo", 1, 500, int(saved["solar"].get("n_parallel",10)), disabled=not solar_on)
            soil = s3.number_input("Perdas sujeira [%]", 0.0, 30.0, float(saved["solar"].get("soiling_losses_pct",0.0)), 0.5, disabled=not solar_on)
            if solar_on:
                module = get_module(pv_key)
                st.caption(f"Potência instalada ≈ {module.stc.p_nom * int(ns) * int(np_) / 1000:.1f} kWp · {module.stc.manufacturer} {module.stc.model}")
        with c2:
            wind_on = st.toggle("🌬️ Eólica ativa", bool(saved["wind"]["active"]))
            wind_keys = list(TURBINE_DB)
            old_w = saved["wind"].get("turbine_key")
            wind_key = st.selectbox("Aerogerador", wind_keys, index=wind_keys.index(old_w) if old_w in wind_keys else 0, disabled=not wind_on)
            count = st.number_input("Quantidade", 1, 100, int(saved["wind"].get("turbine_count",1)), disabled=not wind_on)
            grid_loss = st.toggle("Aplicar perdas de rede do módulo eólico", bool(saved["wind"].get("apply_grid_loss",False)), disabled=not wind_on)
            if wind_on:
                wt = get_turbine(wind_key)
                st.caption(f"Potência nominal unitária: {wt['spec']['rated_power_kw']:.0f} kW. Revise a escala para a embarcação antes de usar aerogeradores de grande porte.")
        if solar_on or wind_on:
            st.markdown("##### Clima usado por Solar/Eólica")
            climate_source = st.radio("Fonte climática", ["Sintético diário", "CSV climático"], index=0 if saved.get("climate",{}).get("source") != "CSV climático" else 1, horizontal=True)
            climate_upload = st.file_uploader("CSV climático", type=["csv"], disabled=climate_source != "CSV climático", help="Detecção automática de timestamp, GHI, temperatura, velocidade/direção do vento, pressão e umidade.")
            if climate_source == "Sintético diário":
                st.caption("O perfil é explícito e usa o horário real da missão: GHI diário, temperatura e vento suaves. Serve para integração/demonstração; para estudo, use o CSV climático real.")
        else:
            climate_source = saved.get("climate",{}).get("source", "Sintético diário")
            climate_upload = None

        st.markdown("#### Fontes despacháveis")
        a, b, c = st.columns(3, gap="large")
        with a:
            fc_on = st.toggle("💧 H₂ / PEMFC ativo", bool(saved["fc"]["active"]))
            nfc = st.number_input("Stacks instalados", 1, 12, int(saved["fc"].get("N_fc",4)), disabled=not fc_on)
            base_label = st.radio("Base do envelope", ["Potência entregue", "Potência do stack"], index=0 if saved["fc"].get("base","entregue") == "entregue" else 1, disabled=not fc_on, help="Potência entregue já é líquida; nesta base o EMS usa η=1 para a FC.")
            st.caption("O modelo físico Horizon equivalente caracteriza potência, rampa e curva kg H₂/kWh antes do despacho.")
        with b:
            bat_on = st.toggle("🔋 Bateria ativa", bool(saved["battery"]["active"]))
            model_ids = [BATTERY_TREMBLAY, BATTERY_2RC]
            bat_model = st.selectbox("Modelo", model_ids, index=model_ids.index(saved["battery"].get("model",BATTERY_TREMBLAY)), format_func=lambda x: BATTERY_MODEL_LABELS[x], disabled=not bat_on)
            keys = list(TREMBLAY_BATTERIES)
            old_key = saved["battery"].get("key","liion_3p3v_2p3ah")
            bat_key = st.selectbox("Célula", keys, index=keys.index(old_key) if old_key in keys else 0, disabled=(not bat_on or bat_model != BATTERY_TREMBLAY))
            q1, q2 = st.columns(2)
            bns = q1.number_input("Ns", 1, 2000, int(saved["battery"].get("Ns",200)), disabled=not bat_on)
            bnp = q2.number_input("Np", 1, 2000, int(saved["battery"].get("Np",132)), disabled=not bat_on)
            q3, q4, q5 = st.columns(3)
            soc0 = q3.slider("SOC inicial [%]", 5, 95, int(100*saved["battery"].get("soc0",.6)), disabled=not bat_on)
            socmin = q4.slider("SOC mín. [%]", 0, 70, int(100*saved["battery"].get("soc_min",.2)), disabled=not bat_on)
            socmax = q5.slider("SOC máx. [%]", 30, 100, int(100*saved["battery"].get("soc_max",.9)), disabled=not bat_on)
            q6, q7 = st.columns(2)
            cdesc = q6.number_input("Descarga máx. [C]", .1, 5.0, float(saved["battery"].get("c_desc",1.0)), .1, disabled=not bat_on)
            ccarga = q7.number_input("Carga máx. [C]", .1, 5.0, float(saved["battery"].get("c_carga",.5)), .1, disabled=not bat_on)
        with c:
            th_on = st.toggle("🔥 Térmica ativa", bool(saved["thermal"]["active"]))
            t1, t2 = st.columns(2)
            pmax = t1.number_input("Pmax [kW]", 1.0, 5000.0, float(saved["thermal"].get("pmax_kW",80.0)), disabled=not th_on)
            pmin = t2.number_input("Mín. [kW]", 0.0, 5000.0, float(saved["thermal"].get("pmin_kW",20.0)), disabled=not th_on)
            t3, t4 = st.columns(2)
            cvu = t3.number_input("CVU [R$/MWh]", 0.0, 10000.0, float(saved["thermal"].get("cvu",1100.0)), disabled=not th_on)
            ramp = t4.number_input("Rampa [kW/min]", 0.0, 5000.0, float(saved["thermal"].get("ramp",20.0)), disabled=not th_on)
            startup = st.number_input("Custo de partida [R$]", 0.0, 1e5, float(saved["thermal"].get("partida",50.0)), disabled=not th_on)

        submit = st.form_submit_button("APLICAR CONFIGURAÇÃO DOS MODELOS", type="primary", width="stretch")
        if submit:
            if not any([fc_on, bat_on, th_on]):
                st.error("Ative pelo menos uma fonte despachável: H₂/PEMFC, bateria ou térmica.")
            elif bat_on and not (socmin <= soc0 <= socmax):
                st.error("O SOC inicial precisa ficar entre SOC mínimo e máximo.")
            elif (solar_on or wind_on) and climate_source == "CSV climático" and climate_upload is None and st.session_state.get("orq_climate_raw") is None:
                st.error("Carregue o CSV climático ou selecione Sintético diário.")
            else:
                climate_raw = st.session_state.get("orq_climate_raw")
                if climate_source == "CSV climático" and climate_upload is not None:
                    try:
                        climate_raw = pd.read_csv(climate_upload, sep=None, engine="python")
                    except Exception as exc:
                        st.error(f"Não foi possível ler o CSV climático: {exc}")
                        climate_raw = None
                new_spec = {
                    "solar": {"active": solar_on, "module_key": pv_key, "n_series": int(ns), "n_parallel": int(np_), "soiling_losses_pct": float(soil)},
                    "wind": {"active": wind_on, "turbine_key": wind_key, "turbine_count": int(count), "apply_grid_loss": bool(grid_loss)},
                    "fc": {"active": fc_on, "N_fc": int(nfc), "base": "entregue" if base_label.startswith("Potência e") else "stack"},
                    "battery": {"active": bat_on, "model": bat_model, "key": bat_key if bat_model == BATTERY_TREMBLAY else None, "Ns": int(bns), "Np": int(bnp), "soc0": soc0/100, "soc_min": socmin/100, "soc_max": socmax/100, "c_desc": float(cdesc), "c_carga": float(ccarga)},
                    "thermal": {"active": th_on, "pmax_kW": float(pmax), "pmin_kW": float(pmin), "cvu": float(cvu), "ramp": float(ramp), "partida": float(startup)},
                    "climate": {"source": climate_source},
                }
                st.session_state["orq_model_spec"] = new_spec
                st.session_state["orq_climate_raw"] = climate_raw if climate_source == "CSV climático" else None
                _invalidate_result("A configuração dos modelos foi alterada.")
                st.success("Modelos aplicados ao contexto comum da aplicação.")
                st.rerun()

    with st.expander("Bancadas individuais dos modelos · ferramenta avançada", expanded=False):
        st.caption("Estas bancadas continuam disponíveis para validar cada física isoladamente. Elas não são necessárias para executar o fluxo integrado.")
        cols = st.columns(5)
        for col, key, label in zip(cols, ["solar","wind","battery","h2","thermal"], ["SOLAR","EÓLICA","BATERIA","H₂ / PEMFC","TÉRMICA"]):
            with col:
                if st.button(f"ABRIR {label}", key=f"open_lab_{key}", width="stretch"):
                    st.session_state["energy_source"] = key
                    if key == "solar":
                        st.session_state["current_page"] = "Visão geral"
                    st.rerun()


def _optimizer_page() -> None:
    _header("Cérebro do sistema", "OTIMIZADOR", "Configura o EMS e executa a rodada usando a carga e os modelos já salvos na aplicação. Este botão é o ponto em que toda a arquitetura conversa de verdade.")
    _flow()
    carga = st.session_state["orq_load"]
    spec = st.session_state["orq_model_spec"]
    saved = st.session_state["orq_optimizer_config"]
    active = RT.active_source_labels(spec)
    c1, c2, c3 = st.columns(3)
    c1.metric("Carga", f"{len(carga.P_kW)} min", f"pico {carga.P_kW.max():.0f} kW")
    c2.metric("Modelos ativos", len(active), " · ".join(active))
    c3.metric("Despacháveis", sum(bool(spec[k]["active"]) for k in ("fc","battery","thermal")), "H₂ · bateria · térmica")
    st.markdown('<div class="callout"><b>Entrada do EMS nesta rodada:</b> a aplicação calculará os modelos ativos com a missão acima, extrairá envelopes/custos/restrições e enviará esse contrato ao solver. A saída volta para Resultados do Otimizador e Resultados dos Modelos.</div>', unsafe_allow_html=True)

    with st.form("orq_optimizer_form"):
        left, right = st.columns([1.05, .95], gap="large")
        with left:
            st.markdown("#### Método")
            alg_labels = list(RT.ALGORITMOS)
            saved_alg = next((k for k,v in RT.ALGORITMOS.items() if v == int(saved.get("algoritmo",2))), alg_labels[0])
            alg_label = st.radio("Algoritmo", alg_labels, index=alg_labels.index(saved_alg))
            meta_pen = st.toggle("Metaheurística com penalidade de restrições", bool(saved.get("meta_penalizada",False)))
            validate = st.toggle("Validar H₂ no modelo dinâmico PEMFC após o despacho", bool(saved.get("validar",False)), disabled=not bool(spec["fc"]["active"]))
        with right:
            st.markdown("#### Horizonte")
            N = st.number_input("Horizonte N [min]", 1, 15, int(saved.get("N",3)), help="O EMS resolve em receding horizon; no final da missão o horizonte encurta até N=1 para cobrir o último minuto.")
            seed = st.number_input("Semente aleatória", 0, 10000, int(saved.get("seed",0)))
            soc_tol = st.number_input("Tolerância SOC-alvo (±)", .01, .50, float(saved.get("soc_alvo_tol",.05)), .01)
        with st.expander("Parâmetros econômicos e conversores"):
            econ_saved = saved.get("econ", {})
            e1,e2,e3,e4 = st.columns(4)
            h2price = e1.number_input("Preço H₂ [R$/kg]", 0.0, 500.0, float(econ_saved.get("preco_H2_rs_kg",25.0)))
            cdeg = e2.number_input("Degradação bateria [R$/kWh]", 0.0, 10.0, float(econ_saved.get("c_deg_bateria_rs_kWh",.08)), .01)
            pdef = e3.number_input("Penalidade déficit [R$/kWh]", 0.0, 1e4, float(econ_saved.get("pen_deficit_rs_kWh",50.0)))
            pexc = e4.number_input("Penalidade vertimento [R$/kWh]", 0.0, 1e3, float(econ_saved.get("pen_excesso_rs_kWh",.5)))
            eta_saved = saved.get("eta_conv", {})
            q1,q2,q3 = st.columns(3)
            eta1 = q1.number_input("η FC (somente base stack)", .5, 1.0, float(eta_saved.get("eta_dc1",.97)), .01)
            eta2 = q2.number_input("η bateria ↔ barramento", .5, 1.0, float(eta_saved.get("eta_dc2",.96)), .01)
            eta0 = q3.number_input("η PV", .5, 1.0, float(eta_saved.get("eta_dc",.97)), .01)
            st.caption("Com base PEMFC = Potência entregue, a potência já é líquida e o EMS força ηFC = 1 no balanço. O valor acima fica apenas para a opção legacy 'Potência do stack'.")
        run = st.form_submit_button("▶ CALCULAR MODELOS E RODAR OTIMIZAÇÃO", type="primary", width="stretch")

    if run:
        opt = {
            "algoritmo": RT.ALGORITMOS[alg_label], "N": int(N), "seed": int(seed), "meta_penalizada": bool(meta_pen),
            "validar": bool(validate), "soc_alvo_tol": float(soc_tol),
            "econ": {"preco_H2_rs_kg": float(h2price), "c_deg_bateria_rs_kWh": float(cdeg), "pen_deficit_rs_kWh": float(pdef), "pen_excesso_rs_kWh": float(pexc)},
            "eta_conv": {"eta_dc1": float(eta1), "eta_dc2": float(eta2), "eta_dc": float(eta0)},
        }
        st.session_state["orq_optimizer_config"] = opt
        bar = st.progress(0.0, text="Calculando os modelos físicos da rodada…")
        try:
            with st.spinner("Modelos físicos → contrato EMS → otimização…"):
                package, outputs = RT.build_exchange_package(carga, spec, opt, climate_raw=st.session_state.get("orq_climate_raw"))
                bar.progress(.08, text="Modelos prontos. Executando EMS…")
                def progress(k: int, n: int) -> None:
                    if k % 3 == 0 or k == n:
                        bar.progress(min(.10 + .88 * k/max(n,1), .98), text=f"EMS · passo {k}/{n}")
                r, val = RT.run_optimizer(package, opt, progress=progress)
            bar.progress(1.0, text="Rodada concluída.")
        except Exception as exc:
            st.error(f"Falha na rodada integrada: {exc}")
            return
        st.session_state["orq_run_counter"] += 1
        item = {"id": st.session_state["orq_run_counter"], "resultado": r, "validacao": val, "quando": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
        st.session_state["orq_result_item"] = item
        st.session_state["orq_model_outputs"] = outputs
        st.session_state["orq_last_run"] = datetime.now()
        st.session_state["orq_history"] = (st.session_state.get("orq_history", []) + [item])[-12:]
        st.session_state["orchestrator_page"] = "Resultados do Otimizador"
        st.rerun()

    with st.expander("Pendências metodológicas para conversar com Marília"):
        st.markdown("""
- avaliar futuramente renovável excedente → carga da bateria antes de vertimento;
- discutir a escolha do horizonte **N** e seu impacto econômico;
- avaliar custo/degradação de start/stop da PEMFC;
- decidir se entram degradação eletroquímica e penalidade de flutuação da FC;
- revisar a reconstrução heurística do número anterior de stacks na restrição de rampa.
""")


def _source_table(r: dict) -> pd.DataFrame:
    rel = r["rel"]; kv = r["k_validos"]; E = EMSP.energias_barramento(r); total = sum(E.values()) or 1.0
    rows = []
    for name in ("pv","eolica"):
        if name in E:
            offer = r["eta_pv"]*r["P_pv_kW"][:kv] if name == "pv" else r["eta_eol"]*r["P_eol_kW"][:kv]
            rows.append({"Fonte": EMSP.rotulo(name), "Energia [kWh]": E[name], "Participação [%]":100*E[name]/total, "Custo [R$]":0.0, "Pico [kW]":float(np.max(offer))})
    for j,name in enumerate(r["nomes"]):
        rows.append({"Fonte":EMSP.rotulo(name),"Energia [kWh]":E.get(name,0.0),"Participação [%]":100*E.get(name,0.0)/total,"Custo [R$]":float(rel["custo_por_fonte_rs"][j]),"Pico [kW]":float(np.max(r["P_kW"][:kv,j]))})
    return pd.DataFrame(rows)


def _optimizer_results_page() -> None:
    _header("Saída do EMS", "RESULTADOS DO OTIMIZADOR", "Despacho ótimo da rodada atual: custo, H₂, balanço, participação por fonte, stacks, SOC e comportamento da metaheurística/refino.")
    _flow()
    item = st.session_state.get("orq_result_item")
    if item is None:
        st.warning("Ainda não existe uma rodada integrada. Configure o EMS e clique em Rodar Otimização.")
        if st.button("IR AO OTIMIZADOR →", type="primary"):
            _go("Otimizador")
        return
    r, val = item["resultado"], item.get("validacao")
    rel = r["rel"]; kv = r["k_validos"]
    h2 = rel["consumo_fisico"].get("fc",{}).get("valor")
    cols = st.columns(6)
    cols[0].metric("H₂ consumido", f"{h2:.2f} kg" if h2 is not None else "—", f"dinâmico {val['h2_kg']:.2f} kg" if val and h2 is not None else None, delta_color="off")
    cols[1].metric("Custo total", f"R$ {rel['custo_total_rs']:,.2f}")
    cols[2].metric("Não atendida", f"{rel['energia_nao_atendida_kWh']:.2f} kWh", f"vertida {rel['energia_vertida_kWh']:.2f} kWh", delta_color="off")
    if "bateria" in r["nomes"]:
        j=r["nomes"].index("bateria"); sf=rel["SOC_final"][j]; s0=r["bateria"]["SOC_ini"]
        cols[3].metric("SOC final", f"{100*sf:.1f}%", f"{100*(sf-s0):+.1f} p.p.", delta_color="off")
    else: cols[3].metric("SOC final", "—")
    if "fc" in r["nomes"]:
        n=r["n_unid"][:kv,r["nomes"].index("fc")]; cols[4].metric("Stacks", f"{n.mean():.2f} médio", f"{n.min()}–{n.max()}", delta_color="off")
    else: cols[4].metric("Stacks","—")
    cols[5].metric("Tempo", f"{r['tempo_total_s']:.1f} s", f"meta {r['t_meta_s']:.1f} · SQP {r['t_ref_s']:.1f}", delta_color="off")
    st.caption(f"Rodada #{item['id']} · {item['quando']} · {r['algoritmo']} · {r['carga_descricao']} · {kv} passos · N={r['N']}")
    tabs = st.tabs(["Despacho", "PEMFC", "Bateria", "Metaheurística × refino", "Dados"])
    with tabs[0]:
        st.plotly_chart(EMSP.fig_despacho(r), width="stretch", config=CHART_CONFIG)
        c1,c2=st.columns([.85,1.15],gap="large")
        c1.plotly_chart(EMSP.fig_participacao(r),width="stretch",config=CHART_CONFIG)
        c2.dataframe(_source_table(r),hide_index=True,width="stretch")
    with tabs[1]:
        f1=EMSP.fig_stacks(r); f2=EMSP.fig_h2(r,val); f3=EMSP.fig_curva_h2(r)
        if f1 is None: st.info("PEMFC não participou da rodada.")
        else:
            st.plotly_chart(f1,width="stretch",config=CHART_CONFIG)
            if f2 is not None: st.plotly_chart(f2,width="stretch",config=CHART_CONFIG)
            if f3 is not None: st.plotly_chart(f3,width="stretch",config=CHART_CONFIG)
    with tabs[2]:
        f=EMSP.fig_soc(r)
        if f is None: st.info("Bateria não participou da rodada.")
        else: st.plotly_chart(f,width="stretch",config=CHART_CONFIG)
    with tabs[3]:
        st.plotly_chart(EMSP.fig_meta_refino(r),width="stretch",config=CHART_CONFIG)
        st.plotly_chart(EMSP.fig_delta_potencia(r),width="stretch",config=CHART_CONFIG)
        dJ=r["J_meta"][:kv]-r["J_ref"][:kv]
        a,b,c=st.columns(3); a.metric("ΔJ mediano",f"R$ {np.nanmedian(dJ):+.3f}"); b.metric("Violação mediana meta",f"{np.nanmedian(r['viol_meta'][:kv]):.3f} kW"); c.metric("Meta inviável",f"{100*np.mean(r['viol_meta'][:kv]>1e-6):.0f}%")
    with tabs[4]:
        st.dataframe(RT.series_dataframe(r),hide_index=True,width="stretch",height=430)
    if r.get("avisos") or r.get("config",{}).get("notas"):
        with st.expander("Avisos e notas"):
            for a in r.get("avisos",[]): st.warning(a)
            for n in r.get("config",{}).get("notas",[]): st.caption(n)


def _models_results_page() -> None:
    _header("Resposta física da rodada", "RESULTADOS DOS MODELOS", "Aqui os gráficos deixam de ser DEMO: são as séries que o próprio EMS acabou de usar/produzir na última execução integrada.")
    _flow()
    item=st.session_state.get("orq_result_item")
    if item is None:
        st.warning("Rode o otimizador primeiro. Esta página mostra os modelos da mesma rodada EMS, não resultados independentes.")
        return
    r=item["resultado"]; spec=st.session_state["orq_model_spec"]
    active_keys=[k for k in ("solar","wind","battery","h2","thermal") if bool(spec.get({"h2":"fc"}.get(k,k),{}).get("active"))]
    if not active_keys:
        st.info("Nenhum modelo ativo na rodada."); return
    source=st.segmented_control("Modelo analisado", active_keys, default=active_keys[0], format_func=lambda x: f"{SOURCE_ICONS[x]} {SOURCE_LABELS[x]}") or active_keys[0]
    frame=RT.model_dispatch_dataframe(r,source)
    st.markdown(f'<span class="result-tag">● MESMA RODADA EMS · {SOURCE_LABELS[source]}</span>',unsafe_allow_html=True)
    left,right=st.columns([.52,1.48],gap="medium")
    with left:
        with st.container(border=True):
            st.markdown(f"### {SOURCE_ICONS[source]} {SOURCE_LABELS[source]}")
            numeric=[c for c in frame.columns if c!="timestamp" and pd.api.types.is_numeric_dtype(frame[c])]
            if numeric:
                st.metric("Pico |potência|", f"{max(float(np.nanmax(np.abs(frame[c]))) for c in numeric if 'SOC' not in c and 'H₂' not in c):.1f} kW" if any(('SOC' not in c and 'H₂' not in c) for c in numeric) else "—")
            if source=="h2" and "fc" in r["nomes"]:
                j=r["nomes"].index("fc"); h2=r["rel"]["consumo_fisico"].get("fc",{}).get("valor"); st.metric("H₂ estimado",f"{h2:.2f} kg" if h2 is not None else "—"); st.metric("Stacks máx.",f"{int(np.max(r['n_unid'][:r['k_validos'],j]))}")
            elif source=="battery" and "bateria" in r["nomes"]:
                j=r["nomes"].index("bateria"); st.metric("SOC inicial",f"{100*r['bateria']['SOC_ini']:.1f}%"); st.metric("SOC final",f"{100*r['rel']['SOC_final'][j]:.1f}%")
            elif source in ("solar","wind"):
                st.caption("Renovável não despachável: o gráfico separa potência disponível, potência usada para abater a carga e vertimento renovável.")
    with right:
        with st.container(border=True):
            fig=go.Figure()
            for col in frame.columns:
                if col=="timestamp" or not pd.api.types.is_numeric_dtype(frame[col]): continue
                dash="dash" if "Disponível" in col else "solid"
                fig.add_trace(go.Scatter(x=frame["timestamp"],y=frame[col],name=col,mode="lines",line=dict(width=2,dash=dash)))
            fig.update_layout(height=390,margin=dict(l=30,r=20,t=25,b=30),hovermode="x unified",legend=dict(orientation="h",y=1.08),yaxis=dict(gridcolor="#EDF1F3"),xaxis=dict(showgrid=False))
            st.plotly_chart(fig,width="stretch",config=CHART_CONFIG)
    with st.expander("Série temporal da resposta deste modelo"):
        st.dataframe(frame,hide_index=True,width="stretch",height=300)
    outputs=st.session_state.get("orq_model_outputs") or {}
    raw_key={"solar":"solar","wind":"wind","battery":"battery_characterization","h2":"fc_characterization","thermal":"thermal_availability"}[source]
    raw=outputs.get(raw_key)
    if isinstance(raw,pd.DataFrame):
        with st.expander("Dados físicos/envelope entregues ao EMS"):
            st.caption("Esta tabela é a saída do modelo físico que foi usada para construir as restrições/envelope da mesma rodada.")
            st.dataframe(raw.head(800),hide_index=True,width="stretch",height=340)


def _export_page() -> None:
    _header("Rastreabilidade", "EXPORTAR RESULTADOS", "Exporta a mesma rodada integrada: carga, configuração dos modelos, configuração do EMS, despacho e saídas físicas usadas pelo otimizador.")
    _flow()
    item=st.session_state.get("orq_result_item")
    if item is None:
        st.warning("Nenhuma rodada para exportar."); return
    r=item["resultado"]; carga=st.session_state["orq_load"]; series=RT.series_dataframe(r)
    a,b,c=st.columns(3,gap="medium")
    with a:
        with st.container(border=True):
            st.markdown("#### Despacho EMS")
            st.caption("Carga, renováveis, potência por fonte, stacks, SOC, H₂, déficit, vertimento e custo por minuto.")
            st.download_button("⬇ CSV DESPACHO",series.to_csv(index=False,sep=";",decimal=",",float_format="%.6f").encode("utf-8-sig"),f"ems_rodada_{item['id']}.csv","text/csv",type="primary",width="stretch")
    with b:
        with st.container(border=True):
            st.markdown("#### Curva de carga")
            df=carga.df().copy(); df.insert(0,"timestamp",RT.load_timestamps(carga)); st.caption("Entrada exata usada na rodada atual.")
            st.download_button("⬇ CSV CARGA",df.to_csv(index=False,sep=";",decimal=",",float_format="%.6f").encode("utf-8-sig"),f"carga_rodada_{item['id']}.csv","text/csv",width="stretch")
    with c:
        with st.container(border=True):
            st.markdown("#### Pacote completo")
            st.caption("ZIP auditável com carga, despacho, configurações, resumo, validação PEMFC e tabelas físicas dos modelos.")
            bundle=RT.export_bundle(carga,st.session_state["orq_model_spec"],st.session_state["orq_optimizer_config"],item,st.session_state.get("orq_model_outputs"))
            st.download_button("⬇ ZIP DA RODADA",bundle,f"energy_multimodel_rodada_{item['id']}.zip","application/zip",type="primary",width="stretch")
    _section("Pré-visualização","Despacho exportável")
    st.dataframe(series,hide_index=True,width="stretch",height=430)


def render_orchestrator_app() -> None:
    st.markdown(ORCHESTRATOR_CSS, unsafe_allow_html=True)
    _init_state()
    page=_sidebar()
    if page=="Visão Geral": _overview_page()
    elif page=="Módulo de Carga": _load_page()
    elif page=="Modelos": _models_config_page()
    elif page=="Otimizador": _optimizer_page()
    elif page=="Resultados do Otimizador": _optimizer_results_page()
    elif page=="Resultados dos Modelos": _models_results_page()
    else: _export_page()
