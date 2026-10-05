"""Interface Streamlit do módulo H₂ / PEMFC de aproximadamente 66 kW."""
from __future__ import annotations

import numpy as np
import pandas as pd
from models.numerics import trapezoid_integral
import plotly.graph_objects as go
import streamlit as st

from h2_pemfc import Equivalent65kWHorizonDynamicModel, Equivalent65kWHorizonSystemModel
from h2_pemfc.ems_input import build_example_ems_profile, prepare_ems_profile

H2_OVERVIEW = "Visão geral"
H2_SIMULATION = "Simulação"
H2_CHARACTERIZATION = "Caracterização"
H2_EXPORT = "Exportação"
H2_NAV = (H2_OVERVIEW, H2_SIMULATION, H2_CHARACTERIZATION, H2_EXPORT)

CHART_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "svg", "filename": "pemfc_h2"},
}

H2_CSS = """
<style>
  :root { --h2:#16869B; --h2-dark:#173036; --h2-border:#D7E4E7; --h2-soft:#F0FAFB; --h2-text:#142A30; }
  [data-testid="stSidebar"] { background:linear-gradient(180deg,#142A30 0%,#1D3A42 100%); border-right:1px solid #2D5059; }
  [data-testid="stSidebar"] p,[data-testid="stSidebar"] span,[data-testid="stSidebar"] label,[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 { color:#EEF9FA !important; }
  .h2-brand { text-align:center; padding:1rem .3rem 1.25rem; }
  .h2-mark { width:68px;height:68px;margin:0 auto .7rem;display:grid;place-items:center;border-radius:16px;background:#16869B;color:white;font-size:1.8rem;border:1px solid rgba(255,255,255,.2);font-weight:900; }
  .h2-brand-name { color:white;font-weight:900;letter-spacing:.18em;font-size:1rem; }
  .h2-brand-sub { color:#9ECBD3;font-weight:750;letter-spacing:.1em;font-size:.62rem;margin-top:.3rem; }
  .h2-head { border:1px solid var(--h2-border);border-radius:10px;padding:.76rem .95rem;margin-bottom:.65rem;background:white; }
  .h2-eyebrow { color:var(--h2);font-size:.66rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase; }
  .h2-title { color:var(--h2-text);font-size:1.55rem;font-weight:920;letter-spacing:-.03em;margin:.18rem 0 .1rem; }
  .h2-sub { color:#64797E;font-size:.78rem; }
  .h2-hero { background:linear-gradient(110deg,#EFF9FA 0%,#FFFFFF 62%);border:1px solid #D8E7EA;border-radius:12px;padding:1rem 1.05rem; }
  .h2-hero h2 { margin:.25rem 0 .45rem;font-size:1.45rem;letter-spacing:-.03em; }
  .h2-hero p { color:#526B71;line-height:1.58;font-size:.82rem;max-width:1100px; }
  .h2-grid { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.48rem;margin:.48rem 0; }
  .h2-spec { border:1px solid #DCE8EA;border-radius:9px;padding:.58rem .62rem;background:#FCFEFE; }
  .h2-spec small { display:block;color:#718A90;font-size:.58rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase; }
  .h2-spec b { display:block;color:#1D343A;font-size:.88rem;margin-top:.12rem; }
  .h2-note { border-left:3px solid var(--h2);border-radius:0 8px 8px 0;background:#EFF8FA;padding:.62rem .72rem;color:#3D6570;font-size:.74rem;line-height:1.5; }
</style>
"""


def _init_state() -> None:
    defaults = {
        "h2_page": H2_OVERVIEW,
        "h2_result": None,
        "h2_kpis": None,
        "h2_source_name": None,
        "h2_defaults_message": None,
        "h2_step_s": 1.0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _header(title: str, eyebrow: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="h2-head"><div class="h2-eyebrow">{eyebrow}</div><div class="h2-title">{title}</div><div class="h2-sub">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def _dynamic_model() -> Equivalent65kWHorizonDynamicModel:
    # Instância por execução Streamlit; o construtor já deriva a rama operacional.
    return Equivalent65kWHorizonDynamicModel()


def _sidebar() -> str:
    with st.sidebar:
        if st.button("← FONTES DE ENERGIA", key="h2_back_sources", width="stretch"):
            st.session_state["energy_source"] = None
            st.rerun()
        st.markdown('<div class="h2-brand"><div class="h2-mark">H₂</div><div class="h2-brand-name">HIDROGÊNIO</div><div class="h2-brand-sub">PEMFC · ~66 kW</div></div>', unsafe_allow_html=True)
        page = st.session_state["h2_page"]
        for option in H2_NAV:
            if st.button(option, key=f"h2_nav_{option}", type="primary" if option == page else "secondary", width="stretch"):
                st.session_state["h2_page"] = option
                st.rerun()
        st.divider()
        k = st.session_state.get("h2_kpis")
        if k:
            st.caption("ÚLTIMA EXECUÇÃO")
            st.metric("Energia entregue", f"{k['energy_delivered_kWh']:.2f} kWh")
            st.metric("H₂ consumido", f"{k['hydrogen_kg']:.3f} kg")
            st.metric("Déficit máximo", f"{k['max_deficit_kW']:.2f} kW")
        st.caption("Modelo PEMFC Horizon equivalente; uso preliminar em estudos de EMS.")
        return st.session_state["h2_page"]


def _integrate(y: np.ndarray, ts: pd.Series) -> float:
    if len(y) < 2:
        return 0.0
    x_h = (pd.to_datetime(ts) - pd.to_datetime(ts).iloc[0]).dt.total_seconds().to_numpy(dtype=float) / 3600.0
    return trapezoid_integral(np.asarray(y, dtype=float), x_h)


def _compute_kpis(result: pd.DataFrame) -> dict[str, float]:
    requested = _integrate(result["P_FC_requested_kW"].to_numpy(dtype=float), result["timestamp"])
    delivered = _integrate(result["P_FC_delivered_kW"].to_numpy(dtype=float), result["timestamp"])
    deficit = _integrate(result["P_deficit_kW"].to_numpy(dtype=float), result["timestamp"])
    h2_kg = _integrate(result["hydrogen_supplied_kg_h"].to_numpy(dtype=float), result["timestamp"])
    active = result["P_FC_delivered_kW"].to_numpy(dtype=float) > 1e-6
    eff = result.loc[active, "net_electrical_efficiency_LHV_percent"] if active.any() else pd.Series(dtype=float)
    return {
        "energy_requested_kWh": requested,
        "energy_delivered_kWh": delivered,
        "energy_deficit_kWh": deficit,
        "hydrogen_kg": h2_kg,
        "max_power_kW": float(result["P_FC_delivered_kW"].max()),
        "max_deficit_kW": float(result["P_deficit_kW"].max()),
        "max_h2_kg_h": float(result["hydrogen_supplied_kg_h"].max()),
        "mean_efficiency_percent": float(eff.mean()) if not eff.empty else 0.0,
        "limited_points": float(result["limitation_flag"].sum()),
    }


def _render_overview() -> None:
    _header(
        "H₂ · PEMFC equivalente de ~66 kW",
        "CONVERSÃO H₂ → ELETRICIDADE",
        "O modelo recebido foi incorporado como módulo de geração despachável: o EMS solicita potência e a célula a combustível retorna potência entregue, corrente, tensão, consumo de H₂, eficiência e limitações dinâmicas.",
    )
    st.markdown(
        """
        <div class="h2-hero">
          <div class="h2-eyebrow">Modelo integrado</div>
          <h2>Stack eletroquímico + balance of plant + dinâmica operacional</h2>
          <p>A cadeia preserva o modelo semiempírico OTEKON/Altıntaş & Ertan, a calibração equivalente de aproximadamente 65–66 kW, o conversor DC/DC, consumos auxiliares, balanço de H₂/ar/calor, inversão potência→corrente e a máquina de estados temporal usada pela interface EMS do projeto original.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="h2-grid">'
        '<div class="h2-spec"><small>Entrada principal</small><b>P_FC_requested_kW</b></div>'
        '<div class="h2-spec"><small>Potência nominal</small><b>≈ 50 kW líquido</b></div>'
        '<div class="h2-spec"><small>Stack</small><b>220 células</b></div>'
        '<div class="h2-spec"><small>Domínio de corrente</small><b>0–450 A</b></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        with st.container(border=True):
            st.markdown("### ⚙️ Eletroquímica")
            st.write("Tensão de Nernst, perdas de ativação, ôhmicas e de concentração; geometria equivalente do stack.")
    with c2:
        with st.container(border=True):
            st.markdown("### 💧 Balance of plant")
            st.write("DC/DC, potência auxiliar, vazão de H₂, ar e calor rejeitado compõem a potência líquida do sistema.")
    with c3:
        with st.container(border=True):
            st.markdown("### ⏱️ Operação EMS")
            st.write("Partida, idle, run, shutdown, rampas, saturação e déficit são avaliados no domínio temporal.")
    st.markdown(
        '<div class="h2-note"><b>Status científico:</b> o perfil integrado é um Horizon VLIIPro50-22 equivalente/restringido, adequado para estudos preliminares de EMS. Não deve ser interpretado como validação experimental do equipamento físico do barco H₂.</div>',
        unsafe_allow_html=True,
    )


def _load_ems_profile(model: Equivalent65kWHorizonDynamicModel) -> tuple[pd.DataFrame | None, str | None, str | None]:
    source = st.radio("Fonte do perfil", ("Exemplo interno", "Carregar CSV"), horizontal=True, key="h2_profile_source")
    if source == "Exemplo interno":
        raw = build_example_ems_profile()
        st.dataframe(raw, hide_index=True, width="stretch", height=250)
        prepared = prepare_ems_profile(raw, dynamic_model=model)
        return prepared.profile, "Exemplo interno", prepared.defaults_message

    uploaded = st.file_uploader("CSV do EMS", type=["csv"], key="h2_uploader")
    if uploaded is None:
        st.info("CSV mínimo: `timestamp,P_FC_requested_kW`. Opcionais: `FC_enable,T_ambient_C,T_coolant_in_C,V_bus_V`.")
        return None, None, None
    try:
        raw = pd.read_csv(uploaded, sep=None, engine="python")
        prepared = prepare_ems_profile(raw, dynamic_model=model)
    except Exception as exc:
        st.error(str(exc)); return None, None, None
    st.dataframe(prepared.profile.head(50), hide_index=True, width="stretch", height=280)
    return prepared.profile, uploaded.name, prepared.defaults_message


def _render_simulation() -> None:
    _header(
        "H₂ · Operação por potência solicitada",
        "INTEGRAÇÃO EMS",
        "Forneça a potência requerida ao fuel cell. O modelo resolve a resposta dinâmica, limites de rampa, potência líquida e consumo de hidrogênio.",
    )
    model = _dynamic_model()
    left, right = st.columns([0.70, 1.30], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("#### Configuração temporal")
            step = st.number_input("Passo interno da simulação [s]", min_value=0.5, max_value=60.0, value=float(st.session_state.get("h2_step_s", 1.0)), step=0.5, key="h2_step_input")
            st.caption("Passos menores representam melhor as rampas e transições, mas aumentam o número de pontos calculados.")
            st.markdown("#### Contrato")
            st.code("timestamp,P_FC_requested_kW\n2026-08-03 13:00:00,10\n2026-08-03 13:01:00,30", language="text")
    with right:
        with st.container(border=True):
            st.markdown("#### Perfil de despacho")
            profile, source_name, defaults_message = _load_ems_profile(model)

    if profile is None:
        return
    if defaults_message:
        st.caption(defaults_message)
    if st.button("▶ SIMULAR PEMFC / H₂", key="run_h2", type="primary", width="stretch"):
        try:
            with st.spinner("Resolvendo dinâmica PEMFC..."):
                result = model.simulate_profile(profile, internal_time_step_s=float(step))
            kpis = _compute_kpis(result)
        except (ValueError, TypeError, RuntimeError) as exc:
            st.error(str(exc)); return
        st.session_state["h2_result"] = result
        st.session_state["h2_kpis"] = kpis
        st.session_state["h2_source_name"] = source_name
        st.session_state["h2_defaults_message"] = defaults_message
        st.session_state["h2_step_s"] = float(step)
        st.success("Simulação concluída.")

    result = st.session_state.get("h2_result")
    kpis = st.session_state.get("h2_kpis")
    if result is None or kpis is None:
        return

    st.markdown("### Resultado operacional")
    q1, q2, q3, q4, q5 = st.columns(5)
    q1.metric("Energia solicitada", f"{kpis['energy_requested_kWh']:.2f} kWh")
    q2.metric("Energia entregue", f"{kpis['energy_delivered_kWh']:.2f} kWh")
    q3.metric("H₂ consumido", f"{kpis['hydrogen_kg']:.3f} kg")
    q4.metric("Eficiência líquida média", f"{kpis['mean_efficiency_percent']:.1f} %")
    q5.metric("Déficit máximo", f"{kpis['max_deficit_kW']:.2f} kW")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result["timestamp"], y=result["P_FC_requested_kW"], mode="lines", name="Solicitada"))
    fig.add_trace(go.Scatter(x=result["timestamp"], y=result["P_FC_delivered_kW"], mode="lines", name="Entregue"))
    fig.add_trace(go.Scatter(x=result["timestamp"], y=result["P_deficit_kW"], mode="lines", name="Déficit"))
    fig.update_layout(title="Potência PEMFC", xaxis_title="Tempo", yaxis_title="kW", margin={"l":20,"r":20,"t":45,"b":20})
    st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)

    c1, c2 = st.columns(2, gap="large")
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["hydrogen_supplied_kg_h"], mode="lines", name="H₂"))
        fig.update_layout(title="Consumo instantâneo de H₂", xaxis_title="Tempo", yaxis_title="kg/h", margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["net_electrical_efficiency_LHV_percent"], mode="lines", name="Eficiência líquida"))
        fig.update_layout(title="Eficiência elétrica líquida · PCI", xaxis_title="Tempo", yaxis_title="%", margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)

    c3, c4 = st.columns(2, gap="large")
    with c3:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["current_A"], mode="lines", name="Corrente"))
        fig.update_layout(title="Corrente do stack", xaxis_title="Tempo", yaxis_title="A", margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
    with c4:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["V_stack_V"], mode="lines", name="Tensão"))
        fig.update_layout(title="Tensão do stack", xaxis_title="Tempo", yaxis_title="V", margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)

    state_summary = result.groupby("state", dropna=False).agg(pontos=("state", "size"), potencia_media_kW=("P_FC_delivered_kW", "mean"), deficit_max_kW=("P_deficit_kW", "max")).reset_index()
    with st.expander("Estados, limitações e diagnóstico"):
        st.dataframe(state_summary, hide_index=True, width="stretch")
        limited = result[result["limitation_flag"]][["timestamp", "state", "P_FC_requested_kW", "P_FC_delivered_kW", "P_deficit_kW", "limitation_reason"]]
        if limited.empty:
            st.success("Nenhuma limitação dinâmica registrada.")
        else:
            st.dataframe(limited, hide_index=True, width="stretch", height=320)


def _render_characterization() -> None:
    _header(
        "H₂ · Caracterização estática",
        "CURVA DO SISTEMA EQUIVALENTE",
        "Visualize a relação corrente–tensão–potência, consumo de H₂ e eficiência da planta estática que sustenta a simulação temporal.",
    )
    try:
        model = Equivalent65kWHorizonSystemModel()
        curve = model.curve(points=181)
    except Exception as exc:
        st.error(f"Falha ao construir a curva estática: {exc}"); return

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Corrente máxima", f"{curve['current_A'].max():.0f} A")
    q2.metric("Potência líquida máxima", f"{curve['P_net_kW'].max():.2f} kW")
    q3.metric("H₂ máximo calculado", f"{curve['hydrogen_supplied_kg_h'].max():.3f} kg/h")
    q4.metric("Tensão mínima do stack", f"{curve['V_stack_V'].min():.1f} V")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve["current_A"], y=curve["V_stack_V"], mode="lines", name="Tensão"))
        fig.update_layout(title="Curva de polarização do stack", xaxis_title="Corrente [A]", yaxis_title="Tensão [V]", margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve["current_A"], y=curve["P_net_kW"], mode="lines", name="Potência líquida"))
        fig.add_trace(go.Scatter(x=curve["current_A"], y=curve["P_stack_kW"], mode="lines", name="Potência stack"))
        fig.update_layout(title="Potência elétrica", xaxis_title="Corrente [A]", yaxis_title="kW", margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
    c3, c4 = st.columns(2, gap="large")
    with c3:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve["P_net_kW"], y=curve["hydrogen_supplied_kg_h"], mode="lines", name="H₂"))
        fig.update_layout(title="Consumo de H₂ × potência líquida", xaxis_title="Potência líquida [kW]", yaxis_title="kg/h", margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
    with c4:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve["P_net_kW"], y=curve["net_electrical_efficiency_LHV_percent"], mode="lines", name="Eficiência líquida"))
        fig.update_layout(title="Eficiência líquida · PCI", xaxis_title="Potência líquida [kW]", yaxis_title="%", margin={"l":20,"r":20,"t":45,"b":20})
        st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)

    with st.expander("Tabela de parâmetros do balance of plant"):
        st.dataframe(model.parameters_table(), hide_index=True, width="stretch", height=420)


def _render_export() -> None:
    _header("H₂ · Exportação", "RESULTADO PARA O OTIMIZADOR", "Exporte a série temporal completa da última simulação PEMFC.")
    result = st.session_state.get("h2_result")
    kpis = st.session_state.get("h2_kpis")
    if result is None or kpis is None:
        st.info("Execute primeiro uma simulação PEMFC/H₂.")
        return
    preferred = [
        "timestamp", "P_FC_requested_kW", "P_FC_delivered_kW", "P_deficit_kW", "state",
        "current_A", "V_stack_V", "P_stack_kW", "hydrogen_supplied_kg_h",
        "net_electrical_efficiency_LHV_percent", "P_aux_equivalent_kW", "P_dc_dc_loss_kW",
        "limitation_flag", "limitation_reason", "T_ambient_C", "T_coolant_in_C", "V_bus_V",
    ]
    export = result[[c for c in preferred if c in result.columns]].copy()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Linhas", len(export)); c2.metric("Energia entregue", f"{kpis['energy_delivered_kWh']:.2f} kWh"); c3.metric("H₂", f"{kpis['hydrogen_kg']:.3f} kg"); c4.metric("Eficiência média", f"{kpis['mean_efficiency_percent']:.1f} %")
    st.dataframe(export.head(400), hide_index=True, width="stretch", height=420)
    csv = export.to_csv(index=False, sep=";", decimal=".", float_format="%.8f").encode("utf-8-sig")
    st.download_button("⬇️ BAIXAR RESULTADO CSV", csv, file_name="resultado_h2_pemfc_66kw.csv", mime="text/csv", type="primary", width="stretch")


def render_h2_app() -> None:
    _init_state()
    st.markdown(H2_CSS, unsafe_allow_html=True)
    page = _sidebar()
    if page == H2_OVERVIEW:
        _render_overview()
    elif page == H2_SIMULATION:
        _render_simulation()
    elif page == H2_CHARACTERIZATION:
        _render_characterization()
    else:
        _render_export()


__all__ = ["render_h2_app", "H2_OVERVIEW", "H2_SIMULATION", "H2_CHARACTERIZATION", "H2_EXPORT"]
