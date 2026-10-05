"""Interface Streamlit do módulo térmico V1.2."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from config.thermal_database import (
    CVU_PRESETS,
    DEFAULT_CVU_BY_DYNAMIC,
    DYNAMIC_LABELS,
    LOCAL_GENERATOR,
    SOURCE_NOTE,
    THERMAL_PLANT,
    get_cvu_preset,
    list_fuels,
)
from models.thermal_model import (
    ThermalConfig,
    ThermalInputMapping,
    detect_thermal_columns,
    evaluate_thermal_dispatch,
    export_thermal_dataframe,
    prepare_thermal_profile,
    read_thermal_csv,
    violations_dataframe,
)
from visualization.thermal_plots import (
    plot_cumulative_cost,
    plot_energy_balance,
    plot_interval_cost,
    plot_power_and_cost,
    plot_thermal_power,
)

THERMAL_OVERVIEW = "Visão geral"
THERMAL_SIMULATION = "Simulação"
THERMAL_EXPORT = "Exportação"
THERMAL_NAV = (THERMAL_OVERVIEW, THERMAL_SIMULATION, THERMAL_EXPORT)

CHART_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "svg", "filename": "thermal_model"},
}

THERMAL_CSS = """
<style>
  :root { --th:#B3561B; --th-dark:#33251D; --th-border:#E4DDD8; --th-soft:#FFF8F3; --th-text:#201A17; }
  [data-testid="stSidebar"] { background:linear-gradient(180deg,#2A211C 0%,#3B2B22 100%); border-right:1px solid #533A2D; }
  [data-testid="stSidebar"] p,[data-testid="stSidebar"] span,[data-testid="stSidebar"] label,[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 { color:#F8EEE8 !important; }
  .thermal-brand { text-align:center; padding:1rem .3rem 1.25rem; }
  .thermal-mark { width:68px;height:68px;margin:0 auto .7rem;display:grid;place-items:center;border-radius:16px;background:#B3561B;color:white;font-size:2rem;border:1px solid rgba(255,255,255,.2); }
  .thermal-brand-name { color:white;font-weight:900;letter-spacing:.2em;font-size:1rem; }
  .thermal-brand-sub { color:#C9A996;font-weight:750;letter-spacing:.1em;font-size:.62rem;margin-top:.3rem; }
  .thermal-head { border:1px solid var(--th-border);border-radius:10px;padding:.76rem .95rem;margin-bottom:.65rem;background:white; }
  .thermal-eyebrow { color:var(--th);font-size:.66rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase; }
  .thermal-title { color:var(--th-text);font-size:1.55rem;font-weight:920;letter-spacing:-.03em;margin:.18rem 0 .1rem; }
  .thermal-sub { color:#786B64;font-size:.78rem; }
  .panel-title { color:var(--th);font-size:.66rem;font-weight:880;letter-spacing:.13em;text-transform:uppercase;margin-bottom:.4rem; }
  .thermal-hero { background:linear-gradient(110deg,#FFF8F2 0%,#FFFFFF 62%);border:1px solid #E8DDD5;border-radius:12px;padding:1rem 1.05rem; }
  .thermal-hero h2 { margin:.25rem 0 .45rem;font-size:1.45rem;letter-spacing:-.03em; }
  .thermal-hero p { color:#62554E;line-height:1.58;font-size:.82rem;max-width:1100px; }
  .thermal-grid { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.48rem;margin:.48rem 0; }
  .thermal-spec { border:1px solid #E7DED8;border-radius:9px;padding:.58rem .62rem;background:#FFFDFC; }
  .thermal-spec small { display:block;color:#8C7D74;font-size:.58rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase; }
  .thermal-spec b { display:block;color:#2B211C;font-size:.88rem;margin-top:.12rem; }
  .thermal-note { border-left:3px solid var(--th);border-radius:0 8px 8px 0;background:#FFF7F1;padding:.62rem .72rem;color:#674F42;font-size:.74rem;line-height:1.5; }
  .mode-card { min-height:150px;border:1px solid #E6DDD7;border-radius:10px;padding:.82rem;background:white; }
  .mode-card .icon { font-size:1.8rem; }.mode-card b{font-size:1rem;color:#2D211B;}.mode-card p{font-size:.76rem;line-height:1.5;color:#75665D;}
  .violation-good { background:#ECF8F1;border:1px solid #C7EAD6;color:#17653E;border-radius:8px;padding:.6rem .72rem;font-size:.74rem; }
  .violation-bad { background:#FFF1EE;border:1px solid #F1CBC1;color:#A13724;border-radius:8px;padding:.6rem .72rem;font-size:.74rem; }
</style>
"""


def _init_state() -> None:
    defaults = {
        "thermal_page": THERMAL_OVERVIEW,
        "thermal_dynamic": THERMAL_PLANT,
        "thermal_result": None,
        "thermal_kpis": None,
        "thermal_source_name": None,
        "thermal_config": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _header(title: str, eyebrow: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="thermal-head"><div class="thermal-eyebrow">{eyebrow}</div><div class="thermal-title">{title}</div><div class="thermal-sub">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def _set_dynamic(dynamic: str, go_to_simulation: bool = True) -> None:
    """Seleciona explicitamente a dinâmica térmica e limpa resultados incompatíveis."""
    if st.session_state.get("thermal_dynamic") != dynamic:
        st.session_state["thermal_result"] = None
        st.session_state["thermal_kpis"] = None
        st.session_state["thermal_source_name"] = None
        st.session_state["thermal_config"] = None
    st.session_state["thermal_dynamic"] = dynamic
    if go_to_simulation:
        st.session_state["thermal_page"] = THERMAL_SIMULATION


def _sidebar() -> str:
    with st.sidebar:
        if st.button("← FONTES DE ENERGIA", key="thermal_back_sources", width="stretch"):
            st.session_state["energy_source"] = None
            st.rerun()
        st.markdown('<div class="thermal-brand"><div class="thermal-mark">🔥</div><div class="thermal-brand-name">TÉRMICA</div><div class="thermal-brand-sub">OPERATION + COST ENGINE</div></div>', unsafe_allow_html=True)

        st.markdown("**TIPO DE RECURSO TÉRMICO**")
        current = st.session_state["thermal_dynamic"]
        if st.button(
            "🏭  USINA TERMELÉTRICA",
            key="thermal_mode_plant",
            type="primary" if current == THERMAL_PLANT else "secondary",
            width="stretch",
            help="Grande porte: inflexibilidade/must-run, Pmax, mínimo técnico e rampas opcionais.",
        ):
            _set_dynamic(THERMAL_PLANT)
            st.rerun()
        if st.button(
            "🛢️  PEQUENA UNIDADE GERADORA",
            key="thermal_mode_local",
            type="primary" if current == LOCAL_GENERATOR else "secondary",
            width="stretch",
            help="Grupo gerador diesel, gás ou biogás de respaldo rápido. Sem inflexibilidade.",
        ):
            _set_dynamic(LOCAL_GENERATOR)
            st.rerun()

        st.caption(
            "Modo ativo: " + DYNAMIC_LABELS[st.session_state["thermal_dynamic"]]
        )
        st.divider()
        page = st.session_state["thermal_page"]
        for option in THERMAL_NAV:
            if st.button(option, key=f"thermal_nav_{option}", type="primary" if option == page else "secondary", width="stretch"):
                st.session_state["thermal_page"] = option
                st.rerun()
        st.divider()
        k = st.session_state.get("thermal_kpis")
        if k:
            st.caption("ÚLTIMA EXECUÇÃO")
            st.metric("Energia entregue", f"{k['energy_delivered_mwh']:.2f} MWh")
            st.metric("Custo total", f"R$ {k['total_cost_rs']:,.0f}".replace(",", "."))
            st.metric("FC do período", f"{k['capacity_factor_period']*100:.2f} %")
        st.caption("V1.2: modelo operacional-econômico; não modela caldeira/ciclo termodinâmico.")
        return st.session_state["thermal_page"]

def _render_overview() -> None:
    _header(
        "Térmica · escolha a dinâmica",
        "MODELO OPERACIONAL-ECONÔMICO",
        "Primeiro defina se o recurso é uma usina termelétrica de grande porte ou uma pequena unidade geradora de respaldo.",
    )

    st.markdown(
        """
        <div class="thermal-hero">
          <div class="thermal-eyebrow">Escolha obrigatória do modelo</div>
          <h2>Duas dinâmicas operacionais diferentes</h2>
          <p>Uma usina termelétrica de grande porte pode possuir inflexibilidade contratual, mínimo técnico e limites de rampa. Já uma pequena unidade geradora — por exemplo um grupo diesel de um cliente — é tratada como recurso rápido de respaldo: sem curva de inflexibilidade, com potência máxima, custo de geração e custo de partida opcional.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            st.markdown("### 🏭 Usina termelétrica de grande porte")
            st.markdown(
                "**Para:** turbinas a gás, ciclos combinados, usinas a óleo, carvão etc.\n\n"
                "**Considera:** curva/valor de inflexibilidade, Pmax, mínimo técnico opcional, rampas opcionais e CVU.\n\n"
                "Se o despacho solicitado ficar abaixo da inflexibilidade, o período é marcado como violação."
            )
            if st.button("USAR MODO USINA TERMELÉTRICA →", key="overview_choose_plant", type="primary", width="stretch"):
                _set_dynamic(THERMAL_PLANT)
                st.rerun()

    with c2:
        with st.container(border=True):
            st.markdown("### 🛢️ Pequena unidade geradora")
            st.markdown(
                "**Para:** grupo gerador diesel, gás, GLP, biogás ou outro equipamento local de respaldo.\n\n"
                "**Não possui inflexibilidade.** O recurso fica desligado quando não é necessário e pode ser acionado para cobrir um déficit por alguns minutos ou horas.\n\n"
                "**Considera:** Pmax, CVU, custo de partida opcional, energia atendida e energia não atendida."
            )
            if st.button("USAR PEQUENA UNIDADE GERADORA →", key="overview_choose_local", type="primary", width="stretch"):
                _set_dynamic(LOCAL_GENERATOR)
                st.rerun()

    st.markdown("### Contrato comum com o futuro otimizador")
    st.code(
        "power_requested[t]\nPmax\nCVU\n→ power_delivered[t]\n→ feasibility / violations\n→ energy_mwh\n→ variable_cost_rs\n→ total_cost_rs",
        language="text",
    )
    st.info(SOURCE_NOTE)

def _mapping_widget(raw: pd.DataFrame, allow_inflex: bool) -> ThermalInputMapping:
    detected = detect_thermal_columns(raw.columns)
    cols = list(raw.columns)
    none = "— Não disponível —"
    ts_default = detected.get("timestamp")
    p_default = detected.get("power_requested")
    c1, c2, c3 = st.columns(3)
    with c1:
        timestamp = st.selectbox("Timestamp *", cols, index=cols.index(ts_default) if ts_default in cols else 0, key="th_map_ts")
    with c2:
        power = st.selectbox("Potência solicitada *", cols, index=cols.index(p_default) if p_default in cols else min(1, len(cols)-1), key="th_map_power")
    with c3:
        if allow_inflex:
            opts = [none] + cols
            d = detected.get("inflexibility")
            inflex = st.selectbox("Inflexibilidade", opts, index=opts.index(d) if d in opts else 0, key="th_map_inflex")
            inflex = None if inflex == none else inflex
        else:
            st.text_input("Inflexibilidade", value="Não aplicável", disabled=True, key="th_map_inflex_disabled")
            inflex = None
    return ThermalInputMapping(timestamp, power, inflex)


def _example_path(dynamic: str) -> Path:
    name = "perfil_termico_usina_exemplo_30min.csv" if dynamic == THERMAL_PLANT else "perfil_gerador_local_exemplo_5min.csv"
    return Path(__file__).resolve().parent / "Dados_exemplo" / name


def _render_simulation() -> None:
    dynamic = st.session_state["thermal_dynamic"]
    label = DYNAMIC_LABELS[dynamic]
    _header(f"Térmica · {label}", "SIMULAÇÃO", "Configure o recurso, carregue o despacho solicitado e avalie custo e factibilidade.")

    if dynamic == THERMAL_PLANT:
        st.info("🏭 **Modo ativo: Usina termelétrica de grande porte.** Inflexibilidade/must-run habilitada; mínimo técnico e rampas são opcionais.")
    else:
        st.info("🛢️ **Modo ativo: Pequena unidade geradora.** Sem inflexibilidade. Pensado para grupo diesel/gás/biogás de respaldo rápido, acionado somente quando necessário.")

    top_left, top_right = st.columns([.92, 1.08], gap="large")
    with top_left:
        with st.container(border=True):
            st.markdown('<div class="panel-title">1 · Recurso térmico</div>', unsafe_allow_html=True)
            default_pmax = 300.0 if dynamic == THERMAL_PLANT else 0.50
            pmax = st.number_input("Potência máxima disponível [MW]", min_value=0.001, value=float(default_pmax), step=10.0 if dynamic == THERMAL_PLANT else 0.05, format="%.3f")

            cvu_mode = st.radio("Definição do CVU", ["Preset acadêmico por combustível", "CVU manual"], horizontal=True)
            default_fuel = DEFAULT_CVU_BY_DYNAMIC[dynamic]
            if cvu_mode.startswith("Preset"):
                fuels = list_fuels()
                fuel = st.selectbox("Combustível", fuels, index=fuels.index(default_fuel))
                preset = get_cvu_preset(fuel)
                cvu = st.number_input("CVU utilizado [R$/MWh]", min_value=0.0, value=float(preset["cvu_rs_mwh"]), step=10.0)
                st.caption(preset["note"])
            else:
                fuel = "Manual"
                cvu = st.number_input("CVU [R$/MWh]", min_value=0.0, value=400.0 if dynamic == THERMAL_PLANT else 1000.0, step=10.0)

            if dynamic == THERMAL_PLANT:
                st.markdown("**Inflexibilidade / must-run**")
                use_file_inflex = st.toggle("Usar curva do arquivo quando disponível", value=True)
                constant_inflex = st.number_input("Fallback / inflexibilidade constante [MW]", min_value=0.0, max_value=float(pmax), value=min(80.0, float(pmax)), step=10.0)
                use_pmin = st.toggle("Considerar mínimo técnico", value=False)
                pmin = st.number_input("Potência mínima técnica [MW]", min_value=0.0, max_value=float(pmax), value=min(60.0, float(pmax)), step=10.0, disabled=not use_pmin) if use_pmin else 0.0
                use_ramps = st.toggle("Considerar limites de rampa", value=False)
                if use_ramps:
                    r1, r2 = st.columns(2)
                    ramp_up = r1.number_input("Subida [MW/min]", min_value=0.001, value=10.0, step=1.0)
                    ramp_down = r2.number_input("Descida [MW/min]", min_value=0.001, value=10.0, step=1.0)
                else:
                    ramp_up = ramp_down = None
                startup_cost = 0.0
            else:
                use_file_inflex = False
                constant_inflex = 0.0
                pmin = 0.0
                ramp_up = ramp_down = None
                startup_cost = st.number_input("Custo fixo por partida [R$]", min_value=0.0, value=0.0, step=10.0, help="Opcional. Soma-se ao custo variável sempre que o gerador passa de desligado para ligado.")
                st.markdown('<div class="thermal-note"><b>Dinâmica rápida.</b> Nesta V1.2 a pequena unidade geradora não tem inflexibilidade nem rampa limitada por padrão. Se a solicitação superar Pmax, o excedente é contabilizado como energia não atendida.</div>', unsafe_allow_html=True)

            st.markdown('<div class="thermal-note" style="margin-top:.55rem"><b>CVU acadêmico.</b> O valor real deve ser informado para cada equipamento/usina. Combustível, eficiência, logística, transporte, armazenamento e O&M podem alterar substancialmente o custo.</div>', unsafe_allow_html=True)

    raw = None
    mapping = None
    source_name = None
    with top_right:
        with st.container(border=True):
            st.markdown('<div class="panel-title">2 · Programa solicitado</div>', unsafe_allow_html=True)
            source_mode = st.radio("Fonte dos dados", ["Exemplo interno", "Carregar CSV"], horizontal=True)
            if source_mode == "Exemplo interno":
                path = _example_path(dynamic)
                raw = read_thermal_csv(path)
                source_name = path.name
                st.caption("Perfil sintético criado para testar operação normal, violações e cálculo de custos.")
            else:
                uploaded = st.file_uploader("CSV", type=["csv", "txt"], help="Obrigatórios: timestamp + potência solicitada. Inflexibilidade é opcional no modo usina.")
                if uploaded is not None:
                    try:
                        raw = read_thermal_csv(uploaded)
                        source_name = uploaded.name
                    except Exception as exc:
                        st.error(f"Falha ao ler o arquivo: {exc}")

            if raw is not None:
                st.success(f"{len(raw):,} linhas carregadas".replace(",", "."))
                with st.expander("Mapeamento de colunas", expanded=True):
                    mapping = _mapping_widget(raw, dynamic == THERMAL_PLANT)
                st.dataframe(raw.head(10), hide_index=True, width="stretch", height=300)
            else:
                st.info("Carregue um CSV para continuar.")

    with st.container(border=True):
        st.markdown('<div class="panel-title">3 · Executar avaliação</div>', unsafe_allow_html=True)
        if st.button("▶ CALCULAR MODELO TÉRMICO", type="primary", width="stretch", disabled=raw is None or mapping is None):
            try:
                profile = prepare_thermal_profile(raw, mapping)
                cfg = ThermalConfig(
                    dynamic=dynamic,
                    pmax_mw=float(pmax),
                    cvu_rs_mwh=float(cvu),
                    constant_inflexibility_mw=float(constant_inflex),
                    use_profile_inflexibility=bool(use_file_inflex),
                    pmin_technical_mw=float(pmin),
                    ramp_up_mw_min=float(ramp_up) if ramp_up is not None else None,
                    ramp_down_mw_min=float(ramp_down) if ramp_down is not None else None,
                    startup_cost_rs=float(startup_cost),
                )
                result, kpis = evaluate_thermal_dispatch(profile, cfg)
                st.session_state["thermal_result"] = result
                st.session_state["thermal_kpis"] = kpis
                st.session_state["thermal_config"] = cfg
                st.session_state["thermal_source_name"] = source_name
                st.success("Modelo térmico calculado.")
            except Exception as exc:
                st.exception(exc)

    result = st.session_state.get("thermal_result")
    k = st.session_state.get("thermal_kpis")
    cfg = st.session_state.get("thermal_config")
    if result is None or k is None or cfg is None or k.get("dynamic") != dynamic:
        return

    st.markdown("### Indicadores do período")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Energia entregue", f"{k['energy_delivered_mwh']:.2f} MWh")
    m2.metric("Custo variável", f"R$ {k['variable_cost_rs']:,.0f}".replace(",", "."))
    m3.metric("Custo total", f"R$ {k['total_cost_rs']:,.0f}".replace(",", "."))
    m4.metric("CVU", f"R$ {k['cvu_rs_mwh']:.2f}/MWh")
    m5.metric("FC do período", f"{k['capacity_factor_period']*100:.2f} %")

    if dynamic == THERMAL_PLANT:
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Energia inflexível", f"{k['energy_inflexible_mwh']:.2f} MWh")
        s2.metric("Energia flexível", f"{k['energy_flexible_mwh']:.2f} MWh")
        s3.metric("Violações inflex.", str(k["violations_inflexibility"]))
        s4.metric("Violações Pmax", str(k["violations_pmax"]))
        s5.metric("Violações rampa", str(k["violations_ramp_up"] + k["violations_ramp_down"]))
        if k["violations_inflexibility"]:
            st.markdown(
                f'<div class="violation-bad"><b>Programa abaixo do contrato em {k["violations_inflexibility"]} intervalos.</b> Para restaurar a inflexibilidade seriam necessários +{k["inflexibility_adjustment_mwh"]:.2f} MWh, equivalentes a aproximadamente R$ {k["cost_to_restore_inflexibility_rs"]:,.0f} de CVU adicional.</div>'.replace(",", "."),
                unsafe_allow_html=True,
            )
        elif k["total_violations"] == 0:
            st.markdown('<div class="violation-good"><b>Programa operacionalmente coerente com as restrições configuradas.</b></div>', unsafe_allow_html=True)
    else:
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Horas ligado", f"{k['operating_hours']:.2f} h")
        s2.metric("Partidas", str(k["start_count"]))
        s3.metric("Custo de partidas", f"R$ {k['startup_cost_rs']:,.0f}".replace(",", "."))
        s4.metric("Energia não atendida", f"{k['energy_unmet_mwh']:.3f} MWh")
        s5.metric("Custo efetivo", f"R$ {k['effective_cost_rs_mwh']:.2f}/MWh")
        if k["energy_unmet_mwh"] > 1e-9:
            st.markdown(f'<div class="violation-bad"><b>Capacidade insuficiente.</b> A pequena unidade geradora não consegue atender {k["energy_unmet_mwh"]:.3f} MWh do pedido no período.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="violation-good"><b>A pequena unidade geradora consegue atender integralmente o perfil solicitado dentro de Pmax.</b></div>', unsafe_allow_html=True)

    g1, g2 = st.columns(2, gap="large")
    with g1:
        st.plotly_chart(plot_thermal_power(result, dynamic, cfg.pmax_mw, cfg.pmin_technical_mw), width="stretch", config=CHART_CONFIG)
    with g2:
        st.plotly_chart(plot_interval_cost(result), width="stretch", config=CHART_CONFIG)
    g3, g4 = st.columns(2, gap="large")
    with g3:
        st.plotly_chart(plot_cumulative_cost(result), width="stretch", config=CHART_CONFIG)
    with g4:
        st.plotly_chart(plot_energy_balance(result, dynamic), width="stretch", config=CHART_CONFIG)
    st.plotly_chart(plot_power_and_cost(result), width="stretch", config=CHART_CONFIG)

    violations = violations_dataframe(result)
    with st.expander("Violações e tabela detalhada", expanded=k["total_violations"] > 0):
        if violations.empty:
            st.success("Nenhuma violação detectada.")
        else:
            st.dataframe(violations, hide_index=True, width="stretch")
        st.dataframe(export_thermal_dataframe(result), hide_index=True, width="stretch", height=420)


def _render_export() -> None:
    _header("Térmica · Exportação", "RESULTADO PARA INTEGRAÇÃO", "Série temporal de potência, energia, custos e flags de factibilidade.")
    result = st.session_state.get("thermal_result")
    k = st.session_state.get("thermal_kpis")
    if result is None or k is None:
        st.info("Execute primeiro uma simulação térmica.")
        if st.button("Ir para Simulação", type="primary"):
            st.session_state["thermal_page"] = THERMAL_SIMULATION
            st.rerun()
        return
    if k.get("dynamic") != st.session_state.get("thermal_dynamic"):
        st.warning("A última execução pertence à outra dinâmica térmica. Execute novamente a simulação antes de exportar.")
        if st.button("Ir para Simulação", type="primary", key="thermal_export_rerun"):
            st.session_state["thermal_page"] = THERMAL_SIMULATION
            st.rerun()
        return
    df = export_thermal_dataframe(result)
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Linhas", len(df))
        c2.metric("Energia entregue", f"{k['energy_delivered_mwh']:.2f} MWh")
        c3.metric("Custo total", f"R$ {k['total_cost_rs']:,.0f}".replace(",", "."))
        c4.metric("Violações", k["total_violations"])
        st.dataframe(df.head(300), hide_index=True, width="stretch", height=420)
        data = df.to_csv(index=False, sep=";", decimal=".", float_format="%.6f").encode("utf-8-sig")
        suffix = "usina" if k["dynamic"] == THERMAL_PLANT else "gerador_local"
        st.download_button("⬇️ BAIXAR RESULTADO CSV", data=data, file_name=f"resultado_termico_{suffix}.csv", mime="text/csv", type="primary", width="stretch")


def render_thermal_app() -> None:
    _init_state()
    st.markdown(THERMAL_CSS, unsafe_allow_html=True)
    page = _sidebar()
    if page == THERMAL_OVERVIEW:
        _render_overview()
    elif page == THERMAL_SIMULATION:
        _render_simulation()
    else:
        _render_export()


__all__ = ["render_thermal_app", "THERMAL_OVERVIEW", "THERMAL_SIMULATION", "THERMAL_EXPORT"]
