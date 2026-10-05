"""Interface Streamlit do modo MIX — orquestra as cinco fontes existentes."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.pv_database import MODULE_DB, get_module
from config.thermal_database import (
    DEFAULT_CVU_BY_DYNAMIC,
    DYNAMIC_LABELS,
    LOCAL_GENERATOR,
    THERMAL_PLANT,
    get_cvu_preset,
    list_fuels,
)
from config.wind_turbine_database import TURBINE_DB, get_turbine
from models.battery_model import (
    BATTERY_2RC,
    BATTERY_MODEL_LABELS,
    BATTERY_TREMBLAY,
    RC_CAPACITY_AH,
    RC_V_NOM_V,
    TREMBLAY_BATTERIES,
)
from simulation.mix_engine import (
    SOURCE_LABELS,
    SOURCE_ORDER,
    MixRunResult,
    available_export_columns,
    build_example_inputs,
    build_export_dataframe,
    default_export_columns,
    detect_climate_columns,
    detect_disabled_source_inputs,
    detect_operation_columns,
    read_csv_auto,
    run_mix,
)

MIX_EXPLANATION = "1 · Explicação"
MIX_CONFIG = "2 · Configuração de fontes"
MIX_INPUT = "3 · Entrada de dados"
MIX_RESULTS = "4 · Resultados"
MIX_EXPORT = "5 · Exportação"
MIX_NAV = (MIX_EXPLANATION, MIX_CONFIG, MIX_INPUT, MIX_RESULTS, MIX_EXPORT)

CHART_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "svg", "filename": "energy_mix"},
}

MIX_CSS = """
<style>
  :root { --mix:#147A73; --mix-dark:#173A37; --mix-border:#D8E6E3; --mix-soft:#F1FAF8; --mix-text:#17302E; }
  [data-testid="stSidebar"] { background:linear-gradient(180deg,#153632 0%,#214942 100%); border-right:1px solid #315C55; }
  [data-testid="stSidebar"] p,[data-testid="stSidebar"] span,[data-testid="stSidebar"] label,[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 { color:#EFFAF8 !important; }
  .mix-brand { text-align:center; padding:1rem .3rem 1.25rem; }
  .mix-mark { width:70px;height:70px;margin:0 auto .72rem;display:grid;place-items:center;border-radius:18px;background:#147A73;color:white;font-size:1.85rem;border:1px solid rgba(255,255,255,.2);font-weight:950; }
  .mix-brand-name { color:white;font-weight:950;letter-spacing:.20em;font-size:1.02rem; }
  .mix-brand-sub { color:#A8D1CB;font-weight:760;letter-spacing:.11em;font-size:.61rem;margin-top:.3rem; }
  .mix-head { border:1px solid var(--mix-border);border-radius:11px;padding:.78rem 1rem;margin-bottom:.7rem;background:white; }
  .mix-eyebrow { color:var(--mix);font-size:.66rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase; }
  .mix-title { color:var(--mix-text);font-size:1.58rem;font-weight:930;letter-spacing:-.032em;margin:.18rem 0 .1rem; }
  .mix-sub { color:#667A76;font-size:.79rem; }
  .mix-hero { background:linear-gradient(112deg,#EDF8F6 0%,#FFFFFF 66%);border:1px solid #D8E8E4;border-radius:13px;padding:1.05rem 1.1rem; }
  .mix-hero h2 { margin:.22rem 0 .45rem;font-size:1.48rem;letter-spacing:-.03em;color:#17302E; }
  .mix-hero p { color:#536B67;line-height:1.6;font-size:.83rem;max-width:1150px; }
  .mix-flow { display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.48rem;margin:.75rem 0; }
  .mix-flow-card {border:1px solid #DDE9E7;border-radius:9px;padding:.62rem;background:#FCFEFD;min-height:94px;}
  .mix-flow-card small {display:block;color:#147A73;font-size:.59rem;font-weight:900;letter-spacing:.1em;text-transform:uppercase;}
  .mix-flow-card b {display:block;color:#203B37;font-size:.81rem;margin:.22rem 0;}
  .mix-flow-card span {color:#71837F;font-size:.69rem;line-height:1.4;}
  .mix-source-card {border:1px solid #DDE8E6;border-radius:10px;padding:.65rem .72rem;background:#FEFFFF;min-height:102px;}
  .mix-source-card b {display:block;color:#1D3834;font-size:.82rem;margin-bottom:.22rem;}
  .mix-source-card span {display:block;color:#6C807C;font-size:.71rem;line-height:1.45;}
  .mix-note {border-left:3px solid var(--mix);background:#F1F9F7;border-radius:0 8px 8px 0;padding:.62rem .72rem;color:#45645F;font-size:.74rem;line-height:1.5;}
  .mix-warning {border-left:3px solid #D28A16;background:#FFF8EA;border-radius:0 8px 8px 0;padding:.62rem .72rem;color:#72551F;font-size:.74rem;line-height:1.5;}
  .mix-ok {border-left:3px solid #1A8D67;background:#EEF9F5;border-radius:0 8px 8px 0;padding:.62rem .72rem;color:#356758;font-size:.74rem;line-height:1.5;}
  .mix-kicker {color:#147A73;font-size:.63rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.28rem;}
  .mix-contract {font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#F7FAFA;border:1px solid #DEE8E6;border-radius:9px;padding:.72rem;color:#36504B;font-size:.73rem;line-height:1.55;}
  @media (max-width:900px){.mix-flow{grid-template-columns:1fr 1fr}.mix-flow-card:last-child{grid-column:1/-1}}
</style>
"""


def _init_state() -> None:
    defaults = {
        "mix_page": MIX_EXPLANATION,
        "mix_enabled_solar": True,
        "mix_enabled_wind": True,
        "mix_enabled_thermal": True,
        "mix_enabled_battery": True,
        "mix_enabled_h2": True,
        "mix_result": None,
        "mix_run_config": None,
        "mix_operation_raw": None,
        "mix_climate_raw": None,
        "mix_operation_name": None,
        "mix_climate_name": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _header(title: str, eyebrow: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="mix-head"><div class="mix-eyebrow">{eyebrow}</div><div class="mix-title">{title}</div><div class="mix-sub">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def _enabled_sources() -> dict[str, bool]:
    return {src: bool(st.session_state.get(f"mix_enabled_{src}", False)) for src in SOURCE_ORDER}


def _sidebar() -> str:
    enabled = _enabled_sources()
    with st.sidebar:
        if st.button("← FONTES DE ENERGIA", key="mix_back_sources", width="stretch"):
            st.session_state["energy_source"] = None
            st.rerun()
        st.markdown('<div class="mix-brand"><div class="mix-mark">MIX</div><div class="mix-brand-name">ENERGY MIX</div><div class="mix-brand-sub">MULTI-SOURCE ORCHESTRATOR</div></div>', unsafe_allow_html=True)
        page = st.session_state["mix_page"]
        for option in MIX_NAV:
            if st.button(option, key=f"mix_nav_{option}", type="primary" if option == page else "secondary", width="stretch"):
                st.session_state["mix_page"] = option
                st.rerun()
        st.divider()
        st.caption("FONTES ATIVAS")
        for src in SOURCE_ORDER:
            icon = "●" if enabled[src] else "○"
            st.caption(f"{icon} {SOURCE_LABELS[src]}")
        result: MixRunResult | None = st.session_state.get("mix_result")
        if result is not None:
            st.divider()
            st.caption("ÚLTIMA EXECUÇÃO")
            st.metric("Pontos", f"{len(result.dataframe)}")
            if result.dataframe["P_demand_kW"].notna().all():
                st.metric("Excedente máx.", f"{result.dataframe['P_excess_kW'].max():.2f} kW")
                st.metric("Déficit máx.", f"{result.dataframe['P_deficit_kW'].max():.2f} kW")
        st.caption("MIX não toma decisões de despacho: executa os modelos e diagnostica a proposta do otimizador.")
        return page


def _invalidate_mix_result() -> None:
    """Descarta resultados que ficaram incompatíveis após alterar fontes ativas."""
    st.session_state["mix_result"] = None
    st.session_state["mix_run_config"] = None


def _source_toggle_card(src: str, description: str, key: str) -> bool:
    with st.container(border=True):
        enabled = st.toggle(
            SOURCE_LABELS[src],
            value=bool(st.session_state.get(key, True)),
            key=key,
            on_change=_invalidate_mix_result,
        )
        st.caption(description)
        return bool(enabled)


def _render_explanation() -> None:
    _header(
        "MIX · execução coordenada das fontes",
        "AUTOMAÇÃO MULTI-FONTE",
        "Uma única proposta operacional entra no sistema; cada fonte é resolvida pelo seu modelo físico atual e todas as saídas são consolidadas na mesma linha do tempo.",
    )
    st.markdown(
        """
        <div class="mix-hero">
          <div class="mix-kicker">Objetivo do módulo</div>
          <h2>Do CSV do otimizador ao comportamento físico combinado</h2>
          <p>O otimizador pode produzir várias propostas de despacho. O MIX recebe uma proposta por vez com as consignas de Térmica, Bateria e H₂, além de um arquivo climático separado. Solar e Eólica operam sempre na potência máxima calculada pelas condições disponíveis. O MIX não redistribui despacho nem executa curtailment: ele verifica o que cada modelo realmente entrega, calcula o balanço quando a demanda total está disponível e devolve um CSV unificado para análise.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="mix-flow">
          <div class="mix-flow-card"><small>1 · Explicação</small><b>Contrato comum</b><span>Define fronteiras, convenções e responsabilidade do otimizador.</span></div>
          <div class="mix-flow-card"><small>2 · Configuração</small><b>Ativar fontes</b><span>Seleciona os modelos e parâmetros que já existem nos módulos individuais.</span></div>
          <div class="mix-flow-card"><small>3 · Entrada</small><b>Dois CSVs</b><span>Operação é a timeline mestre; clima é interpolado para esses timestamps.</span></div>
          <div class="mix-flow-card"><small>4 · Resultados</small><b>Rodar e comparar</b><span>Solicitado × entregue, renováveis, SOC, H₂, custo e balanço.</span></div>
          <div class="mix-flow-card"><small>5 · Exportação</small><b>CSV configurável</b><span>Escolha exatamente as colunas que deseja enviar ao próximo estágio.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("### Regras de despacho")
        st.markdown(
            '<div class="mix-note"><b>Solar + Eólica:</b> sempre 100 % da potência disponível calculada. Se houver excedente, ele é apenas sinalizado como necessidade de curtailment. Nenhuma dinâmica de corte é simulada.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="mix-note" style="margin-top:.5rem"><b>Térmica + Bateria + H₂:</b> seguem as consignas do CSV operacional. O MIX não decide automaticamente carregar a bateria nem aumentar outra fonte.</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown("### Sincronização temporal")
        st.markdown(
            '<div class="mix-note"><b>Timeline mestre = CSV do otimizador.</b> O clima pode estar em outra resolução e é interpolado para os timestamps operacionais. As consignas de potência não são interpoladas pelo MIX.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="mix-warning" style="margin-top:.5rem"><b>Balanço e curtailment:</b> para calcular excedente/déficit, informe também a demanda total no CSV operacional. Sem essa coluna, os cinco modelos continuam executando, mas o MIX não inventa a carga.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Contrato mínimo recomendado")
    st.markdown(
        '<div class="mix-contract">CSV OPERACIONAL → timestamp, P_demanda_total_kW (recomendado), P_termica_requested_kW, P_bateria_requested_kW, P_H2_requested_kW<br>CSV CLIMÁTICO → timestamp, GHI, temperatura_C, wind_speed, wind_direction, pressure_hPa, humidity_pct<br><br>Bateria: +kW = descarga · −kW = carga</div>',
        unsafe_allow_html=True,
    )


def _render_config() -> None:
    _header(
        "MIX · configuração das fontes",
        "SELEÇÃO E PARAMETRIZAÇÃO",
        "Ative somente as fontes presentes no estudo. Cada bloco reutiliza o modelo já disponível na página individual correspondente.",
    )
    st.markdown("### Fontes ativas")
    cols = st.columns(5)
    descriptions = {
        "solar": "NOCT + eficiência corrigida por temperatura.",
        "wind": "Curva do fabricante + correção por densidade.",
        "thermal": "Usina ou pequena unidade geradora.",
        "battery": "Tremblay–Dessaint ou circuito 2RC.",
        "h2": "PEMFC Horizon equivalente ~66 kW.",
    }
    for idx, src in enumerate(SOURCE_ORDER):
        with cols[idx]:
            _source_toggle_card(src, descriptions[src], f"mix_enabled_{src}")

    enabled = _enabled_sources()
    if not any(enabled.values()):
        st.warning("Ative pelo menos uma fonte para executar o MIX.")
        return

    st.markdown("### Parâmetros dos modelos")
    if enabled["solar"]:
        with st.expander("☀️ Solar · NOCT + eficiência", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            keys = list(MODULE_DB.keys())
            default_key = "CS7L-580MS" if "CS7L-580MS" in keys else keys[0]
            module_key = c1.selectbox("Módulo FV", keys, index=keys.index(st.session_state.get("mix_solar_module", default_key)) if st.session_state.get("mix_solar_module", default_key) in keys else keys.index(default_key), key="mix_solar_module")
            ns = c2.number_input("Módulos em série", min_value=1, max_value=10000, value=int(st.session_state.get("mix_solar_ns", 2)), step=1, key="mix_solar_ns")
            np_ = c3.number_input("Strings em paralelo", min_value=1, max_value=10000, value=int(st.session_state.get("mix_solar_np", 3)), step=1, key="mix_solar_np")
            losses = c4.number_input("Perdas ópticas [%]", min_value=0.0, max_value=99.0, value=float(st.session_state.get("mix_solar_losses", 0.0)), step=0.5, key="mix_solar_losses")
            module = get_module(module_key)
            installed = module.stc.p_nom * int(ns) * int(np_) / 1000.0
            st.caption(f"Modelo fixo no MIX: NOCT + eficiência corrigida por γPmax · {module.name} · potência instalada ≈ {installed:.3f} kWp · NOCT {module.stc.noct:.1f} °C")

    if enabled["wind"]:
        with st.expander("🌬️ Eólica · curva elétrica do fabricante", expanded=True):
            c1, c2, c3 = st.columns([1.5, .6, .8])
            keys = list(TURBINE_DB.keys())
            turbine_key = c1.selectbox("Aerogerador", keys, index=keys.index(st.session_state.get("mix_wind_turbine", keys[0])) if st.session_state.get("mix_wind_turbine", keys[0]) in keys else 0, key="mix_wind_turbine")
            count = c2.number_input("Quantidade", min_value=1, max_value=500, value=int(st.session_state.get("mix_wind_count", 1)), step=1, key="mix_wind_count")
            apply_loss = c3.toggle("Perdas genéricas 3 %", value=bool(st.session_state.get("mix_wind_loss", False)), key="mix_wind_loss")
            entry = get_turbine(turbine_key)
            st.caption(f"{entry['spec']['manufacturer']} · {entry['spec']['model']} · {float(entry['spec']['rated_power_kw']):.0f} kW por unidade")

    if enabled["thermal"]:
        with st.expander("🔥 Térmica · modelo operacional-econômico", expanded=True):
            dynamic = st.radio(
                "Dinâmica térmica",
                [THERMAL_PLANT, LOCAL_GENERATOR],
                format_func=lambda d: DYNAMIC_LABELS[d],
                horizontal=True,
                key="mix_thermal_dynamic",
            )
            c1, c2, c3 = st.columns(3)
            pmax = c1.number_input("Pmax [MW]", min_value=0.001, value=float(st.session_state.get("mix_thermal_pmax", 1.0)), step=0.05, key="mix_thermal_pmax")
            fuel_default = DEFAULT_CVU_BY_DYNAMIC[dynamic]
            fuels = list_fuels()
            fuel = c2.selectbox("Preset de combustível", fuels, index=fuels.index(st.session_state.get("mix_thermal_fuel", fuel_default)) if st.session_state.get("mix_thermal_fuel", fuel_default) in fuels else fuels.index(fuel_default), key="mix_thermal_fuel")
            preset = get_cvu_preset(fuel)
            cvu = c3.number_input("CVU [R$/MWh]", min_value=0.0, value=float(st.session_state.get("mix_thermal_cvu", preset["cvu_rs_mwh"])), step=10.0, key="mix_thermal_cvu")
            if dynamic == THERMAL_PLANT:
                a, b, c = st.columns(3)
                inflex = a.number_input("Inflexibilidade constante [MW]", min_value=0.0, max_value=float(pmax), value=min(float(st.session_state.get("mix_thermal_inflex", 0.0)), float(pmax)), step=0.01, key="mix_thermal_inflex")
                use_pmin = b.toggle("Considerar mínimo técnico", value=bool(st.session_state.get("mix_thermal_use_pmin", False)), key="mix_thermal_use_pmin")
                pmin = b.number_input("Pmin [MW]", min_value=0.0, max_value=float(pmax), value=min(float(st.session_state.get("mix_thermal_pmin", 0.0)), float(pmax)), step=0.01, disabled=not use_pmin, key="mix_thermal_pmin") if use_pmin else 0.0
                use_ramps = c.toggle("Considerar rampas", value=bool(st.session_state.get("mix_thermal_use_ramps", False)), key="mix_thermal_use_ramps")
                if use_ramps:
                    r1, r2 = st.columns(2)
                    r_up = r1.number_input("Rampa subida [MW/min]", min_value=0.001, value=float(st.session_state.get("mix_thermal_rup", 0.05)), step=0.01, key="mix_thermal_rup")
                    r_down = r2.number_input("Rampa descida [MW/min]", min_value=0.001, value=float(st.session_state.get("mix_thermal_rdown", 0.05)), step=0.01, key="mix_thermal_rdown")
                else:
                    r_up = r_down = None
                st.session_state["mix_thermal_startup"] = 0.0
            else:
                st.session_state["mix_thermal_inflex"] = 0.0
                st.session_state["mix_thermal_pmin"] = 0.0
                st.session_state["mix_thermal_use_pmin"] = False
                st.session_state["mix_thermal_use_ramps"] = False
                startup = st.number_input("Custo de partida [R$]", min_value=0.0, value=float(st.session_state.get("mix_thermal_startup", 0.0)), step=10.0, key="mix_thermal_startup")
            st.caption("No MIX a inflexibilidade, quando usada, é configurada aqui como valor constante. A potência solicitada continua vindo do CSV do otimizador.")

    if enabled["battery"]:
        with st.expander("🔋 Bateria · modelo dinâmico", expanded=True):
            model_id = st.radio(
                "Modelo",
                [BATTERY_2RC, BATTERY_TREMBLAY],
                format_func=lambda m: BATTERY_MODEL_LABELS[m],
                horizontal=True,
                key="mix_battery_model",
            )
            c1, c2, c3, c4 = st.columns(4)
            ns = c1.number_input("Células em série · Ns", min_value=1, max_value=5000, value=int(st.session_state.get("mix_battery_ns", 120)), step=1, key="mix_battery_ns")
            np_ = c2.number_input("Strings em paralelo · Np", min_value=1, max_value=5000, value=int(st.session_state.get("mix_battery_np", 50)), step=1, key="mix_battery_np")
            soc = c3.slider("SOC inicial [%]", 0.0, 100.0, float(st.session_state.get("mix_battery_soc", 90.0)), 1.0, key="mix_battery_soc")
            step = c4.number_input("Passo interno [s]", min_value=0.5, max_value=60.0, value=float(st.session_state.get("mix_battery_step", 5.0)), step=0.5, key="mix_battery_step")
            if model_id == BATTERY_TREMBLAY:
                keys = list(TREMBLAY_BATTERIES)
                default = "liion_3p3v_2p3ah" if "liion_3p3v_2p3ah" in keys else keys[0]
                battery_key = st.selectbox("Química / célula", keys, index=keys.index(st.session_state.get("mix_battery_key", default)) if st.session_state.get("mix_battery_key", default) in keys else keys.index(default), format_func=lambda k: TREMBLAY_BATTERIES[k].name, key="mix_battery_key")
                bat = TREMBLAY_BATTERIES[battery_key]
                nominal_energy = bat.V_nom_V * bat.Q_Ah * int(ns) * int(np_) / 1000.0
            else:
                nominal_energy = RC_V_NOM_V * RC_CAPACITY_AH * int(ns) * int(np_) / 1000.0
            st.caption(f"Banco nominal aproximado: {nominal_energy:.2f} kWh. No CSV operacional: +kW = descarga; −kW = carga. O MIX converte a consigna de potência para a corrente requerida pelo modelo existente.")

    if enabled["h2"]:
        with st.expander("💧 H₂ / PEMFC · Horizon equivalente", expanded=True):
            step = st.number_input("Passo interno da PEMFC [s]", min_value=0.5, max_value=60.0, value=float(st.session_state.get("mix_h2_step", 5.0)), step=0.5, key="mix_h2_step")
            st.caption("Mesmo modelo dinâmico da página H₂. A consigna P_H2_requested_kW é fornecida diretamente pelo otimizador.")

    st.markdown('<div class="mix-ok"><b>Configuração pronta.</b> A próxima página carrega separadamente operação e clima. Nenhum modelo físico novo é criado pelo MIX.</div>', unsafe_allow_html=True)


def _select_mapping(label: str, columns: list[str], detected: str | None, key: str, required: bool) -> str | None:
    none = "— Não informado —"
    options = columns if required else [none] + columns
    if detected in options:
        index = options.index(detected)
    else:
        index = 0
    value = st.selectbox(label, options, index=index, key=key)
    return None if value == none else value


def _load_inputs_widget() -> tuple[pd.DataFrame | None, pd.DataFrame | None, str | None, str | None]:
    mode = st.radio("Fonte dos arquivos", ["Exemplo interno MIX", "Carregar CSVs"], horizontal=True, key="mix_input_mode")
    if mode == "Exemplo interno MIX":
        operation, climate = build_example_inputs()
        c1, c2 = st.columns(2)
        with c1:
            st.caption("Operação exemplo · timeline 1 min")
            st.dataframe(operation.head(8), hide_index=True, width="stretch", height=245)
            st.download_button("⬇️ CSV operacional de exemplo", operation.to_csv(index=False).encode("utf-8-sig"), "mix_operacao_exemplo.csv", "text/csv", width="stretch")
        with c2:
            st.caption("Clima exemplo · resolução 10 min")
            st.dataframe(climate.head(8), hide_index=True, width="stretch", height=245)
            st.download_button("⬇️ CSV climático de exemplo", climate.to_csv(index=False).encode("utf-8-sig"), "mix_clima_exemplo.csv", "text/csv", width="stretch")
        return operation, climate, "Exemplo operacional interno", "Exemplo climático interno"

    c1, c2 = st.columns(2, gap="large")
    operation = climate = None
    operation_name = climate_name = None
    with c1:
        st.markdown("#### 1 · CSV operacional")
        op_file = st.file_uploader("Operação / proposta do otimizador", type=["csv", "txt"], key="mix_operation_upload")
        if op_file is not None:
            try:
                operation = read_csv_auto(op_file)
                operation_name = op_file.name
                st.success(f"{len(operation)} linhas carregadas")
                st.dataframe(operation.head(8), hide_index=True, width="stretch", height=245)
            except Exception as exc:
                st.error(f"Falha no CSV operacional: {exc}")
    with c2:
        st.markdown("#### 2 · CSV climático")
        cl_file = st.file_uploader("Condições meteorológicas", type=["csv", "txt"], key="mix_climate_upload")
        if cl_file is not None:
            try:
                climate = read_csv_auto(cl_file)
                climate_name = cl_file.name
                st.success(f"{len(climate)} linhas carregadas")
                st.dataframe(climate.head(8), hide_index=True, width="stretch", height=245)
            except Exception as exc:
                st.error(f"Falha no CSV climático: {exc}")
    return operation, climate, operation_name, climate_name


def _build_run_config(enabled: dict[str, bool]) -> dict:
    cfg: dict[str, dict] = {}
    if enabled["solar"]:
        module_key = st.session_state.get("mix_solar_module") or ("CS7L-580MS" if "CS7L-580MS" in MODULE_DB else list(MODULE_DB)[0])
        cfg["solar"] = {
            "module_key": module_key,
            "n_series": int(st.session_state.get("mix_solar_ns", 2)),
            "n_parallel": int(st.session_state.get("mix_solar_np", 3)),
            "soiling_losses_pct": float(st.session_state.get("mix_solar_losses", 0.0)),
            "noct": None,
        }
    if enabled["wind"]:
        cfg["wind"] = {
            "turbine_key": st.session_state.get("mix_wind_turbine") or list(TURBINE_DB)[0],
            "turbine_count": int(st.session_state.get("mix_wind_count", 1)),
            "apply_grid_loss": bool(st.session_state.get("mix_wind_loss", False)),
        }
    if enabled["thermal"]:
        dynamic = st.session_state.get("mix_thermal_dynamic", THERMAL_PLANT)
        cfg["thermal"] = {
            "dynamic": dynamic,
            "pmax_mw": float(st.session_state.get("mix_thermal_pmax", 1.0)),
            "cvu_rs_mwh": float(st.session_state.get("mix_thermal_cvu", 0.0)),
            "constant_inflexibility_mw": float(st.session_state.get("mix_thermal_inflex", 0.0)) if dynamic == THERMAL_PLANT else 0.0,
            "pmin_technical_mw": float(st.session_state.get("mix_thermal_pmin", 0.0)) if st.session_state.get("mix_thermal_use_pmin", False) and dynamic == THERMAL_PLANT else 0.0,
            "ramp_up_mw_min": float(st.session_state.get("mix_thermal_rup", 0.05)) if st.session_state.get("mix_thermal_use_ramps", False) and dynamic == THERMAL_PLANT else None,
            "ramp_down_mw_min": float(st.session_state.get("mix_thermal_rdown", 0.05)) if st.session_state.get("mix_thermal_use_ramps", False) and dynamic == THERMAL_PLANT else None,
            "startup_cost_rs": float(st.session_state.get("mix_thermal_startup", 0.0)) if dynamic == LOCAL_GENERATOR else 0.0,
        }
    if enabled["battery"]:
        cfg["battery"] = {
            "model_id": st.session_state.get("mix_battery_model", BATTERY_2RC),
            "battery_key": st.session_state.get("mix_battery_key", "liion_3p3v_2p3ah"),
            "n_series": int(st.session_state.get("mix_battery_ns", 120)),
            "n_parallel": int(st.session_state.get("mix_battery_np", 50)),
            "initial_soc": float(st.session_state.get("mix_battery_soc", 90.0)) / 100.0,
            "integration_step_s": float(st.session_state.get("mix_battery_step", 5.0)),
            "power_iterations": 4,
        }
    if enabled["h2"]:
        cfg["h2"] = {"integration_step_s": float(st.session_state.get("mix_h2_step", 5.0))}
    return cfg


def _render_input() -> None:
    _header(
        "MIX · entrada de dados",
        "OPERAÇÃO + CONDIÇÃO CLIMÁTICA",
        "O arquivo operacional define todos os timestamps da simulação. O clima é interpolado para essa timeline; nenhuma consigna do otimizador é interpolada.",
    )
    enabled = _enabled_sources()
    if not any(enabled.values()):
        st.warning("Volte à configuração e ative pelo menos uma fonte.")
        return

    operation, climate, operation_name, climate_name = _load_inputs_widget()
    if operation is None:
        st.info("Carregue o CSV operacional para continuar.")
        return
    climate_needed = enabled["solar"] or enabled["wind"]
    if climate_needed and climate is None:
        st.info("Solar/Eólica ativa: carregue também o CSV climático.")
        return

    ignored_messages = detect_disabled_source_inputs(operation, climate, enabled)
    for message in ignored_messages:
        st.warning(message)

    st.markdown("### Mapeamento das colunas")
    op_detected = detect_operation_columns(operation.columns)
    op_cols = list(operation.columns)
    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True):
            st.markdown("#### Operação · otimizador")
            op_mapping = {
                "timestamp": _select_mapping("Timestamp *", op_cols, op_detected.get("timestamp"), "mix_map_op_ts", True),
                "demand_total_kw": _select_mapping("Demanda total do sistema [kW] · recomendada", op_cols, op_detected.get("demand_total_kw"), "mix_map_op_demand", False),
                "thermal_kw": _select_mapping("Demanda Térmica [kW]" + (" *" if enabled["thermal"] else ""), op_cols, op_detected.get("thermal_kw"), "mix_map_op_thermal", enabled["thermal"]) if enabled["thermal"] else None,
                "battery_kw": _select_mapping("Demanda Bateria [kW] · + descarga / − carga" + (" *" if enabled["battery"] else ""), op_cols, op_detected.get("battery_kw"), "mix_map_op_battery", enabled["battery"]) if enabled["battery"] else None,
                "h2_kw": _select_mapping("Demanda H₂/PEMFC [kW]" + (" *" if enabled["h2"] else ""), op_cols, op_detected.get("h2_kw"), "mix_map_op_h2", enabled["h2"]) if enabled["h2"] else None,
            }
            if op_mapping["demand_total_kw"] is None:
                st.caption("Sem demanda total: solicitado × entregue será calculado, mas excedente/déficit/curtailment ficará indisponível.")

    climate_mapping = None
    with right:
        with st.container(border=True):
            st.markdown("#### Clima")
            if climate_needed and climate is not None:
                cl_detected = detect_climate_columns(climate.columns)
                cl_cols = list(climate.columns)
                climate_mapping = {
                    "timestamp": _select_mapping("Timestamp *", cl_cols, cl_detected.get("timestamp"), "mix_map_cl_ts", True),
                    "ghi": _select_mapping("GHI [W/m²]" + (" *" if enabled["solar"] else ""), cl_cols, cl_detected.get("ghi"), "mix_map_cl_ghi", enabled["solar"]) if enabled["solar"] else None,
                    "temperature": _select_mapping("Temperatura [°C]" + (" *" if enabled["solar"] else ""), cl_cols, cl_detected.get("temperature"), "mix_map_cl_temp", enabled["solar"]),
                    "wind_speed": _select_mapping("Velocidade do vento [m/s]" + (" *" if enabled["wind"] else ""), cl_cols, cl_detected.get("wind_speed"), "mix_map_cl_ws", enabled["wind"]) if enabled["wind"] else None,
                    "wind_direction": _select_mapping("Direção do vento [°]", cl_cols, cl_detected.get("wind_direction"), "mix_map_cl_wd", False) if enabled["wind"] else None,
                    "pressure": _select_mapping("Pressão [hPa ou Pa]", cl_cols, cl_detected.get("pressure"), "mix_map_cl_pressure", False) if enabled["wind"] else None,
                    "humidity": _select_mapping("Umidade [% ou 0–1]", cl_cols, cl_detected.get("humidity"), "mix_map_cl_humidity", False) if enabled["wind"] else None,
                }
                st.caption("GHI, temperatura, vento e demais variáveis são interpolados para a timeline do otimizador. Direção do vento usa interpolação angular.")
            else:
                st.info("Nenhuma fonte dependente de clima está ativa; este arquivo não é necessário.")

    config = _build_run_config(enabled)
    with st.container(border=True):
        st.markdown("#### Executar proposta")
        active_names = ", ".join(SOURCE_LABELS[s] for s in SOURCE_ORDER if enabled[s])
        st.caption(f"Fontes: {active_names} · operação: {operation_name or '—'} · clima: {climate_name or 'não necessário'}")
        if st.button("▶ EXECUTAR MIX", type="primary", width="stretch", key="mix_run"):
            try:
                with st.spinner("Executando modelos e consolidando o balanço..."):
                    result = run_mix(
                        operation,
                        climate,
                        operation_mapping=op_mapping,
                        climate_mapping=climate_mapping,
                        enabled_sources=enabled,
                        config=config,
                    )
            except Exception as exc:
                st.exception(exc)
                return
            st.session_state["mix_result"] = result
            st.session_state["mix_run_config"] = config
            st.session_state["mix_operation_raw"] = operation
            st.session_state["mix_climate_raw"] = climate
            st.session_state["mix_operation_name"] = operation_name
            st.session_state["mix_climate_name"] = climate_name
            st.session_state["mix_page"] = MIX_RESULTS
            st.rerun()


def _integrated_kwh(df: pd.DataFrame, col: str) -> float:
    if col not in df:
        return 0.0
    hours = np.asarray(df.attrs.get("step_hours", np.zeros(len(df))), dtype=float)
    if len(hours) != len(df):
        ts = pd.to_datetime(df["timestamp"])
        hours = ts.shift(-1).sub(ts).dt.total_seconds().to_numpy(dtype=float) / 3600.0
        positive = hours[np.isfinite(hours) & (hours > 0)]
        typical = float(np.median(positive)) if len(positive) else 0.0
        if len(hours): hours[-1] = typical
    return float(np.nansum(pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float) * hours))


def _power_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    traces = [
        ("P_solar_kW", "Solar"), ("P_wind_kW", "Eólica"),
        ("P_thermal_delivered_kW", "Térmica entregue"), ("P_battery_delivered_kW", "Bateria"),
        ("P_H2_delivered_kW", "H₂ entregue"),
    ]
    for col, label in traces:
        if col in df and np.nanmax(np.abs(pd.to_numeric(df[col], errors="coerce").fillna(0))) > 1e-9:
            fig.add_trace(go.Scatter(x=df["timestamp"], y=df[col], mode="lines", name=label))
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["P_total_generated_kW"], mode="lines", name="Total líquido", line={"width": 3}))
    if df["P_demand_kW"].notna().all():
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["P_demand_kW"], mode="lines", name="Demanda", line={"dash": "dash", "width": 3}))
    fig.update_layout(title="Potência por fonte e balanço do sistema", xaxis_title="Tempo", yaxis_title="kW", margin={"l":20,"r":20,"t":48,"b":20}, legend={"orientation":"h"})
    return fig


def _requested_delivered_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    pairs = [
        ("P_thermal_requested_kW", "P_thermal_delivered_kW", "Térmica"),
        ("P_battery_requested_kW", "P_battery_delivered_kW", "Bateria"),
        ("P_H2_requested_kW", "P_H2_delivered_kW", "H₂"),
    ]
    for req, delivered, label in pairs:
        if req in df and np.nanmax(np.abs(df[req].to_numpy(dtype=float))) > 1e-9:
            fig.add_trace(go.Scatter(x=df["timestamp"], y=df[req], mode="lines", name=f"{label} · solicitada", line={"dash":"dot"}))
            fig.add_trace(go.Scatter(x=df["timestamp"], y=df[delivered], mode="lines", name=f"{label} · entregue"))
    fig.update_layout(title="Consignas do otimizador × resposta física", xaxis_title="Tempo", yaxis_title="kW", margin={"l":20,"r":20,"t":48,"b":20}, legend={"orientation":"h"})
    return fig


def _render_results() -> None:
    _header(
        "MIX · resultados consolidados",
        "RESPOSTA FÍSICA DA PROPOSTA",
        "Todas as fontes foram projetadas sobre a timeline operacional. Solar/Eólica permanecem em máxima disponibilidade; as demais respondem às consignas do otimizador.",
    )
    result: MixRunResult | None = st.session_state.get("mix_result")
    if result is None:
        st.info("Execute uma proposta na página Entrada de dados.")
        return
    df = result.dataframe
    has_demand = df["P_demand_kW"].notna().all()

    enabled_run = dict(df.attrs.get("enabled_sources") or {})
    metrics: list[tuple[str, str]] = []
    if enabled_run.get("solar") or enabled_run.get("wind"):
        metrics.append(("Energia renovável", f"{_integrated_kwh(df, 'P_renewable_kW'):.2f} kWh"))
    if enabled_run.get("thermal"):
        metrics.append(("Energia térmica", f"{_integrated_kwh(df, 'P_thermal_delivered_kW'):.2f} kWh"))
    if enabled_run.get("h2"):
        metrics.append(("Energia H₂", f"{_integrated_kwh(df, 'P_H2_delivered_kW'):.2f} kWh"))
    if enabled_run.get("battery"):
        metrics.append(("Bateria · líquido", f"{_integrated_kwh(df, 'P_battery_delivered_kW'):.2f} kWh"))
    metrics.append(("Demanda", f"{_integrated_kwh(df, 'P_demand_kW'):.2f} kWh") if has_demand else ("Pontos", str(len(df))))
    for slot, (label, value) in zip(st.columns(len(metrics)), metrics):
        slot.metric(label, value)

    if has_demand:
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Excedente", f"{_integrated_kwh(df, 'P_excess_kW'):.2f} kWh")
        b2.metric("Déficit", f"{_integrated_kwh(df, 'P_deficit_kW'):.2f} kWh")
        b3.metric("Pico excedente", f"{df['P_excess_kW'].max():.2f} kW")
        b4.metric("Pico déficit", f"{df['P_deficit_kW'].max():.2f} kW")

    for message in result.messages:
        if "Excedente" in message or "oportunidade" in message:
            st.warning(message)
        else:
            st.info(message)

    st.plotly_chart(_power_figure(df), width="stretch", config=CHART_CONFIG)
    if any(enabled_run.get(src) for src in ("thermal", "battery", "h2")):
        st.plotly_chart(_requested_delivered_figure(df), width="stretch", config=CHART_CONFIG)

    if has_demand:
        if enabled_run.get("battery"):
            c1, c2 = st.columns(2, gap="large")
        else:
            c1, c2 = st.container(), None
        with c1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["timestamp"], y=df["P_excess_kW"], mode="lines", name="Excedente"))
            fig.add_trace(go.Scatter(x=df["timestamp"], y=df["P_deficit_kW"], mode="lines", name="Déficit"))
            fig.update_layout(title="Excedente e déficit", xaxis_title="Tempo", yaxis_title="kW", margin={"l":20,"r":20,"t":45,"b":20})
            st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
        if c2 is not None:
            with c2:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df["timestamp"], y=df["SOC_battery_pct"], mode="lines", name="SOC"))
                fig.update_layout(title="Estado de carga da bateria", xaxis_title="Tempo", yaxis_title="SOC [%]", margin={"l":20,"r":20,"t":45,"b":20})
                st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)

    source_kpis = result.source_kpis
    if source_kpis:
        with st.expander("Indicadores por modelo", expanded=False):
            rows = []
            for src, metrics in source_kpis.items():
                for key, value in metrics.items():
                    if isinstance(value, (str, int, float, np.integer, np.floating, bool)):
                        rows.append({"fonte": SOURCE_LABELS.get(src, src), "indicador": key, "valor": value})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=360)

    with st.expander("Tabela consolidada", expanded=False):
        visible_columns = available_export_columns(df)
        st.dataframe(df[visible_columns], hide_index=True, width="stretch", height=480)


def _safe_filename(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    text = text.strip("._") or "mix_resultado"
    return text if text.lower().endswith(".csv") else text + ".csv"


def _render_export() -> None:
    _header(
        "MIX · exportação configurável",
        "CSV PARA OTIMIZADOR / GÊMEO DIGITAL",
        "Escolha o conjunto de colunas. O perfil essencial sugerido corresponde ao contrato consolidado; você pode removê-lo, ampliá-lo ou exportar todas as variáveis internas.",
    )
    result: MixRunResult | None = st.session_state.get("mix_result")
    if result is None:
        st.info("Execute primeiro uma proposta MIX.")
        return
    df = result.dataframe
    all_columns = available_export_columns(df)
    essential = default_export_columns(df)

    left, right = st.columns([.72, 1.28], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("#### Configuração")
            preset = st.selectbox("Preset de colunas", ["Essencial sugerido", "Todas as colunas", "Personalizado"], key="mix_export_preset")
            if preset == "Essencial sugerido":
                default = essential
            elif preset == "Todas as colunas":
                default = all_columns
            else:
                default = essential
            selected = st.multiselect("Colunas exportadas", all_columns, default=default, key=f"mix_export_cols_{preset}")
            filename = _safe_filename(st.text_input("Nome do arquivo", value="mix_resultado.csv", key="mix_export_name"))
            sep_label = st.selectbox("Separador", ["Vírgula (,)", "Ponto e vírgula (;)"])
            dec_label = st.selectbox("Decimal", ["Ponto (.)", "Vírgula (,)"])
            sep = ";" if ";" in sep_label else ","
            decimal = "," if "Vírgula" in dec_label else "."
            st.caption(f"{len(selected)} de {len(all_columns)} colunas selecionadas")

    with right:
        with st.container(border=True):
            st.markdown("#### Pré-visualização")
            if not selected:
                st.warning("Selecione pelo menos uma coluna.")
                return
            export_df = build_export_dataframe(df, selected)
            st.dataframe(export_df.head(80), hide_index=True, width="stretch", height=430)
            csv_bytes = export_df.to_csv(index=False, sep=sep, decimal=decimal, float_format="%.6f").encode("utf-8-sig")
            st.download_button("⬇️ BAIXAR CSV MIX", csv_bytes, filename, "text/csv", type="primary", width="stretch")

    st.markdown('<div class="mix-note"><b>O CSV não altera a simulação.</b> A seleção acima controla apenas a interface de saída. Os resultados completos permanecem na sessão atual.</div>', unsafe_allow_html=True)


def render_mix_app() -> None:
    _init_state()
    st.markdown(MIX_CSS, unsafe_allow_html=True)
    page = _sidebar()
    if page == MIX_EXPLANATION:
        _render_explanation()
    elif page == MIX_CONFIG:
        _render_config()
    elif page == MIX_INPUT:
        _render_input()
    elif page == MIX_RESULTS:
        _render_results()
    else:
        _render_export()
