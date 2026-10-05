"""Interface Streamlit do módulo de baterias — Tremblay/Dessaint + 2RC."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from models.battery_model import (
    BATTERY_2RC,
    BATTERY_MODEL_LABELS,
    BATTERY_TREMBLAY,
    RC_CAPACITY_AH,
    RC_V_NOM_V,
    TREMBLAY_BATTERIES,
    battery_kpis,
    build_battery_example,
    detect_battery_columns,
    export_battery_dataframe,
    prepare_battery_profile,
    read_battery_csv,
    simulate_2rc,
    simulate_tremblay,
)

BAT_OVERVIEW = "Visão geral"
BAT_SIMULATION = "Simulação"
BAT_COMPARISON = "Comparação"
BAT_EXPORT = "Exportação"
BAT_NAV = (BAT_OVERVIEW, BAT_SIMULATION, BAT_COMPARISON, BAT_EXPORT)

CHART_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "svg", "filename": "battery_model"},
}

BATTERY_CSS = """
<style>
  :root { --bat:#6A53A3; --bat-dark:#242030; --bat-border:#E0DCE8; --bat-soft:#F7F4FC; --bat-text:#211C2A; }
  [data-testid="stSidebar"] { background:linear-gradient(180deg,#211D2C 0%,#312943 100%); border-right:1px solid #4A3D61; }
  [data-testid="stSidebar"] p,[data-testid="stSidebar"] span,[data-testid="stSidebar"] label,[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 { color:#F4EFFB !important; }
  .battery-brand { text-align:center; padding:1rem .3rem 1.25rem; }
  .battery-mark { width:68px;height:68px;margin:0 auto .7rem;display:grid;place-items:center;border-radius:16px;background:#6A53A3;color:white;font-size:2rem;border:1px solid rgba(255,255,255,.2); }
  .battery-brand-name { color:white;font-weight:900;letter-spacing:.2em;font-size:1rem; }
  .battery-brand-sub { color:#C6B8E2;font-weight:750;letter-spacing:.1em;font-size:.62rem;margin-top:.3rem; }
  .battery-head { border:1px solid var(--bat-border);border-radius:10px;padding:.76rem .95rem;margin-bottom:.65rem;background:white; }
  .battery-eyebrow { color:var(--bat);font-size:.66rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase; }
  .battery-title { color:var(--bat-text);font-size:1.55rem;font-weight:920;letter-spacing:-.03em;margin:.18rem 0 .1rem; }
  .battery-sub { color:#716A7D;font-size:.78rem; }
  .battery-hero { background:linear-gradient(110deg,#F8F5FD 0%,#FFFFFF 62%);border:1px solid #E6E0EE;border-radius:12px;padding:1rem 1.05rem; }
  .battery-hero h2 { margin:.25rem 0 .45rem;font-size:1.45rem;letter-spacing:-.03em; }
  .battery-hero p { color:#5F586B;line-height:1.58;font-size:.82rem;max-width:1100px; }
  .battery-grid { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.48rem;margin:.48rem 0; }
  .battery-spec { border:1px solid #E6E0EC;border-radius:9px;padding:.58rem .62rem;background:#FEFDFF; }
  .battery-spec small { display:block;color:#81778E;font-size:.58rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase; }
  .battery-spec b { display:block;color:#2A2432;font-size:.88rem;margin-top:.12rem; }
  .battery-note { border-left:3px solid var(--bat);border-radius:0 8px 8px 0;background:#F7F3FC;padding:.62rem .72rem;color:#5F5075;font-size:.74rem;line-height:1.5; }
</style>
"""


def _init_state() -> None:
    defaults = {
        "battery_page": BAT_OVERVIEW,
        "battery_model_id": BATTERY_TREMBLAY,
        "battery_result": None,
        "battery_kpis": None,
        "battery_profile": None,
        "battery_config": None,
        "battery_source_name": None,
        "battery_compare_results": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _header(title: str, eyebrow: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="battery-head"><div class="battery-eyebrow">{eyebrow}</div><div class="battery-title">{title}</div><div class="battery-sub">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def _sidebar() -> str:
    with st.sidebar:
        if st.button("← FONTES DE ENERGIA", key="battery_back_sources", width="stretch"):
            st.session_state["energy_source"] = None
            st.rerun()
        st.markdown('<div class="battery-brand"><div class="battery-mark">🔋</div><div class="battery-brand-name">BATERIA</div><div class="battery-brand-sub">DYNAMIC STORAGE MODELS</div></div>', unsafe_allow_html=True)

        st.markdown("**MODELO ATIVO**")
        model = st.session_state["battery_model_id"]
        if st.button("Tremblay–Dessaint", key="bat_model_tremblay", type="primary" if model == BATTERY_TREMBLAY else "secondary", width="stretch"):
            st.session_state["battery_model_id"] = BATTERY_TREMBLAY
            st.session_state["battery_result"] = None
            st.session_state["battery_kpis"] = None
            st.rerun()
        if st.button("Circuito equivalente · 2 RC", key="bat_model_2rc", type="primary" if model == BATTERY_2RC else "secondary", width="stretch"):
            st.session_state["battery_model_id"] = BATTERY_2RC
            st.session_state["battery_result"] = None
            st.session_state["battery_kpis"] = None
            st.rerun()

        st.divider()
        page = st.session_state["battery_page"]
        for option in BAT_NAV:
            if st.button(option, key=f"battery_nav_{option}", type="primary" if option == page else "secondary", width="stretch"):
                st.session_state["battery_page"] = option
                st.rerun()
        st.divider()
        k = st.session_state.get("battery_kpis")
        if k:
            st.caption("ÚLTIMA EXECUÇÃO")
            st.metric("SOC final", f"{k['soc_final_percent']:.1f} %")
            st.metric("Energia entregue", f"{k['energy_discharge_Wh']/1000:.3f} kWh")
            st.metric("Energia absorvida", f"{k['energy_charge_Wh']/1000:.3f} kWh")
        st.caption("Corrente positiva = descarga · corrente negativa = carga.")
        return st.session_state["battery_page"]


def _render_overview() -> None:
    _header(
        "Bateria · dois modelos dinâmicos",
        "ARMAZENAMENTO ELETROQUÍMICO",
        "Os dois protótipos MATLAB fornecidos foram portados para Python e integrados à mesma arquitetura temporal dos demais recursos.",
    )
    st.markdown(
        """
        <div class="battery-hero">
          <div class="battery-eyebrow">Biblioteca de modelos</div>
          <h2>Do modelo empírico genérico ao circuito equivalente com duas constantes de tempo</h2>
          <p>O módulo recebe um perfil temporal de corrente e devolve tensão, potência e SOC. O banco pode ser escalado por número de células em série e strings em paralelo, mantendo as equações de célula dos modelos originais.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            st.markdown("### 🔋 Modelo 01 · Tremblay–Dessaint / Shepherd")
            st.write("Modelo dinâmico de tensão terminal com integração coulômbica, corrente filtrada e zona exponencial. O protótipo fornecido inclui Lead-Acid, NiCd, Li-Ion e NiMH.")
            st.markdown("**Entrada:** corrente do banco [A] · **Saídas:** V, P, SOC, corrente filtrada e termo exponencial.")
            if st.button("USAR TREMBLAY–DESSAINT →", key="overview_bat_tremblay", type="primary", width="stretch"):
                st.session_state["battery_model_id"] = BATTERY_TREMBLAY
                st.session_state["battery_page"] = BAT_SIMULATION
                st.rerun()
    with c2:
        with st.container(border=True):
            st.markdown("### ⚡ Modelo 03 · Circuito equivalente 2 RC")
            st.write("Modelo Li-Ion 18650 de 2,35 Ah baseado em Zhang et al. (2017): OCV(SOC), R0(SOC) e dois ramos R-C dependentes do estado de carga.")
            st.markdown("**Entrada:** corrente do banco [A] · **Saídas:** V, P, SOC, OCV, VRC1 e VRC2.")
            if st.button("USAR CIRCUITO 2 RC →", key="overview_bat_2rc", type="primary", width="stretch"):
                st.session_state["battery_model_id"] = BATTERY_2RC
                st.session_state["battery_page"] = BAT_SIMULATION
                st.rerun()

    st.markdown("### Convenção e fronteira do modelo")
    st.markdown(
        '<div class="battery-note"><b>Convenção comum:</b> I &gt; 0 descarrega a bateria e gera potência positiva; I &lt; 0 carrega a bateria e produz potência negativa. O escalonamento Ns×Np é elétrico: V<sub>banco</sub>=Ns·V<sub>célula</sub> e I<sub>célula</sub>=I<sub>banco</sub>/Np. Conversor DC/DC, temperatura, degradação e SOH ainda não fazem parte desta versão.</div>',
        unsafe_allow_html=True,
    )


def _load_profile_widget() -> tuple[pd.DataFrame | None, str | None]:
    source = st.radio("Fonte do perfil", ("Exemplo interno", "Carregar CSV"), horizontal=True, key="battery_profile_source")
    if source == "Exemplo interno":
        profile = build_battery_example()
        st.caption("Exemplo de 10 s com descarga, repouso e carga regenerativa.")
        st.dataframe(profile.head(12), hide_index=True, width="stretch", height=240)
        return profile, "Exemplo interno"

    uploaded = st.file_uploader("CSV de corrente", type=["csv", "txt"], key="battery_uploader")
    if uploaded is None:
        st.info("CSV mínimo: `timestamp,current_A`. Corrente positiva = descarga; negativa = carga.")
        return None, None
    try:
        raw = read_battery_csv(uploaded)
    except Exception as exc:
        st.error(f"Não foi possível ler o arquivo: {exc}")
        return None, None
    guessed_t, guessed_i = detect_battery_columns(raw)
    cols = list(raw.columns)
    c1, c2 = st.columns(2)
    with c1:
        timestamp_col = st.selectbox("Coluna de timestamp", cols, index=cols.index(guessed_t) if guessed_t in cols else 0)
    with c2:
        current_col = st.selectbox("Coluna de corrente [A]", cols, index=cols.index(guessed_i) if guessed_i in cols else min(1, len(cols)-1))
    try:
        profile = prepare_battery_profile(raw, timestamp_col, current_col)
    except ValueError as exc:
        st.error(str(exc))
        return None, None
    st.dataframe(profile.head(20), hide_index=True, width="stretch", height=240)
    return profile, uploaded.name


def _plot_result(result: pd.DataFrame) -> None:
    c1, c2 = st.columns(2, gap="large")
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["voltage_V"], mode="lines", name="Tensão"))
        fig.update_layout(title="Tensão terminal do banco", xaxis_title="Tempo", yaxis_title="V", margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["soc_percent"], mode="lines", name="SOC"))
        fig.update_layout(title="Estado de carga", xaxis_title="Tempo", yaxis_title="SOC (%)", yaxis_range=[0, 105], margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
    c3, c4 = st.columns(2, gap="large")
    with c3:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["current_A"], mode="lines", name="Corrente"))
        fig.add_hline(y=0)
        fig.update_layout(title="Corrente do banco", xaxis_title="Tempo", yaxis_title="A", margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
    with c4:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["power_W"]/1000.0, mode="lines", name="Potência"))
        fig.add_hline(y=0)
        fig.update_layout(title="Potência elétrica", xaxis_title="Tempo", yaxis_title="kW", margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)

    if "V_RC1_V_cell" in result:
        with st.expander("Diagnóstico do circuito 2 RC"):
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=result["timestamp"], y=result["ocv_V_cell"], mode="lines", name="OCV"))
            fig.add_trace(go.Scatter(x=result["timestamp"], y=result["V_RC1_V_cell"], mode="lines", name="VRC1"))
            fig.add_trace(go.Scatter(x=result["timestamp"], y=result["V_RC2_V_cell"], mode="lines", name="VRC2"))
            fig.update_layout(xaxis_title="Tempo", yaxis_title="V por célula", margin={"l":20,"r":20,"t":30,"b":20})
            st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)


def _render_simulation() -> None:
    model_id = st.session_state["battery_model_id"]
    _header(
        "Bateria · Simulação temporal",
        BATTERY_MODEL_LABELS[model_id],
        "Configure o banco, forneça a corrente solicitada pelo sistema e calcule a resposta elétrica e o SOC.",
    )
    left, right = st.columns([0.78, 1.22], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("#### Configuração do banco")
            n_series = st.number_input("Células em série · Ns", min_value=1, max_value=2000, value=12, step=1, key="battery_ns")
            n_parallel = st.number_input("Strings em paralelo · Np", min_value=1, max_value=1000, value=4, step=1, key="battery_np")
            initial_soc = st.slider("SOC inicial", 0.0, 100.0, 90.0, 1.0, key="battery_initial_soc") / 100.0
            battery_key = None
            if model_id == BATTERY_TREMBLAY:
                keys = list(TREMBLAY_BATTERIES)
                battery_key = st.selectbox("Química / célula do artigo", keys, index=keys.index("liion_3p3v_2p3ah"), format_func=lambda k: TREMBLAY_BATTERIES[k].name)
                bat = TREMBLAY_BATTERIES[battery_key]
                nominal_energy = bat.V_nom_V * bat.Q_Ah * int(n_series) * int(n_parallel)
                st.caption(f"Célula: {bat.V_nom_V:.1f} V · {bat.Q_Ah:.2f} Ah · banco nominal ≈ {nominal_energy/1000:.3f} kWh")
            else:
                nominal_energy = RC_V_NOM_V * RC_CAPACITY_AH * int(n_series) * int(n_parallel)
                st.caption(f"Célula fixa do modelo: Li-Ion 18650 · {RC_V_NOM_V:.1f} V · {RC_CAPACITY_AH:.2f} Ah · banco nominal ≈ {nominal_energy/1000:.3f} kWh")
    with right:
        with st.container(border=True):
            st.markdown("#### Perfil de corrente")
            profile, source_name = _load_profile_widget()

    if profile is None:
        return

    if st.button("▶ SIMULAR BATERIA", key="run_battery", type="primary", width="stretch"):
        try:
            if model_id == BATTERY_TREMBLAY:
                result = simulate_tremblay(profile, battery_key=battery_key or "liion_3p3v_2p3ah", n_series=int(n_series), n_parallel=int(n_parallel), initial_soc=float(initial_soc))
            else:
                result = simulate_2rc(profile, n_series=int(n_series), n_parallel=int(n_parallel), initial_soc=float(initial_soc))
            kpis = battery_kpis(result)
        except (ValueError, KeyError, RuntimeError) as exc:
            st.error(str(exc))
            return
        st.session_state["battery_result"] = result
        st.session_state["battery_kpis"] = kpis
        st.session_state["battery_profile"] = profile
        st.session_state["battery_source_name"] = source_name
        st.session_state["battery_config"] = {
            "model_id": model_id, "battery_key": battery_key, "n_series": int(n_series), "n_parallel": int(n_parallel), "initial_soc": initial_soc,
        }
        st.success("Simulação concluída.")

    result = st.session_state.get("battery_result")
    kpis = st.session_state.get("battery_kpis")
    config = st.session_state.get("battery_config") or {}
    if result is None or kpis is None or config.get("model_id") != model_id:
        return

    st.markdown("### Resultado")
    q1, q2, q3, q4, q5 = st.columns(5)
    q1.metric("SOC final", f"{kpis['soc_final_percent']:.1f} %", f"{kpis['soc_final_percent']-kpis['soc_initial_percent']:+.1f} p.p.")
    q2.metric("Energia entregue", f"{kpis['energy_discharge_Wh']/1000:.3f} kWh")
    q3.metric("Energia absorvida", f"{kpis['energy_charge_Wh']/1000:.3f} kWh")
    q4.metric("V mínima", f"{kpis['voltage_min_V']:.2f} V")
    q5.metric("Pico descarga", f"{kpis['power_discharge_peak_W']/1000:.2f} kW")
    if kpis["limit_points"] > 0:
        st.warning(f"Foram marcados {int(kpis['limit_points'])} ponto(s) em limite de SOC/tensão do modelo.")
    _plot_result(result)
    with st.expander("Tabela detalhada"):
        st.dataframe(export_battery_dataframe(result), hide_index=True, width="stretch", height=420)


def _render_comparison() -> None:
    _header(
        "Bateria · Comparação de modelos",
        "MESMO PERFIL DE CORRENTE",
        "Executa Tremblay–Dessaint (Li-Ion) e 2RC sobre a mesma corrente e o mesmo arranjo Ns×Np. As células de referência não são idênticas, portanto a comparação é estrutural e não uma validação cruzada direta.",
    )
    profile = st.session_state.get("battery_profile")
    cfg = st.session_state.get("battery_config") or {}
    if profile is None:
        st.info("Execute primeiro uma simulação para definir o perfil comum.")
        return
    ns = int(cfg.get("n_series", 1)); np_ = int(cfg.get("n_parallel", 1)); soc0 = float(cfg.get("initial_soc", .9))
    st.caption(f"Perfil: {st.session_state.get('battery_source_name') or '—'} · banco comum {ns}s × {np_}p · SOC inicial {soc0*100:.1f}%")
    if st.button("COMPARAR OS DOIS MODELOS", type="primary", width="stretch", key="battery_compare_run"):
        try:
            trem = simulate_tremblay(profile, battery_key="liion_3p3v_2p3ah", n_series=ns, n_parallel=np_, initial_soc=soc0)
            rc = simulate_2rc(profile, n_series=ns, n_parallel=np_, initial_soc=soc0)
            st.session_state["battery_compare_results"] = {BATTERY_TREMBLAY: trem, BATTERY_2RC: rc}
        except Exception as exc:
            st.error(str(exc)); return
    results = st.session_state.get("battery_compare_results")
    if not results:
        return
    fig = go.Figure()
    for mid, df in results.items():
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["soc_percent"], mode="lines", name=BATTERY_MODEL_LABELS[mid]))
    fig.update_layout(title="SOC · comparação", xaxis_title="Tempo", yaxis_title="SOC (%)", margin={"l":20,"r":20,"t":45,"b":20})
    st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
    fig = go.Figure()
    for mid, df in results.items():
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["voltage_V"], mode="lines", name=BATTERY_MODEL_LABELS[mid]))
    fig.update_layout(title="Tensão terminal do banco", xaxis_title="Tempo", yaxis_title="V", margin={"l":20,"r":20,"t":45,"b":20})
    st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
    rows = []
    for mid, df in results.items():
        k = battery_kpis(df)
        rows.append({"Modelo": BATTERY_MODEL_LABELS[mid], "SOC final [%]": k["soc_final_percent"], "Energia entregue [Wh]": k["energy_discharge_Wh"], "Energia absorvida [Wh]": k["energy_charge_Wh"], "V mínima [V]": k["voltage_min_V"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_export() -> None:
    _header("Bateria · Exportação", "SÉRIE TEMPORAL PARA EMS", "Exporte a resposta elétrica da última simulação para o futuro otimizador/gêmeo digital.")
    result = st.session_state.get("battery_result")
    kpis = st.session_state.get("battery_kpis")
    if result is None or kpis is None:
        st.info("Execute primeiro uma simulação de bateria.")
        return
    export = export_battery_dataframe(result)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Linhas", len(export)); c2.metric("SOC final", f"{kpis['soc_final_percent']:.1f} %"); c3.metric("Energia entregue", f"{kpis['energy_discharge_Wh']/1000:.3f} kWh"); c4.metric("Energia absorvida", f"{kpis['energy_charge_Wh']/1000:.3f} kWh")
    st.dataframe(export.head(300), hide_index=True, width="stretch", height=420)
    model_id = result.attrs.get("model_id", "battery")
    csv = export.to_csv(index=False, sep=";", decimal=".", float_format="%.8f").encode("utf-8-sig")
    st.download_button("⬇️ BAIXAR RESULTADO CSV", csv, file_name=f"resultado_bateria_{model_id}.csv", mime="text/csv", type="primary", width="stretch")


def render_battery_app() -> None:
    _init_state()
    st.markdown(BATTERY_CSS, unsafe_allow_html=True)
    page = _sidebar()
    if page == BAT_OVERVIEW:
        _render_overview()
    elif page == BAT_SIMULATION:
        _render_simulation()
    elif page == BAT_COMPARISON:
        _render_comparison()
    else:
        _render_export()


__all__ = ["render_battery_app", "BAT_OVERVIEW", "BAT_SIMULATION", "BAT_COMPARISON", "BAT_EXPORT"]
