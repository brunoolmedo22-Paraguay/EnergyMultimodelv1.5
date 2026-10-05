"""Interface Streamlit do módulo eólico V1."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from config.wind_turbine_database import (
    TURBINE_DB,
    catalog_summary,
    get_turbine,
    list_models,
    specific_power_w_m2,
)
from models.wind_model import (
    WindInputMapping,
    detect_columns,
    export_wind_dataframe,
    prepare_wind_profile,
    read_wind_csv,
    run_wind_model,
)
from visualization.wind_plots import (
    plot_catalog_comparison,
    plot_catalog_curve,
    plot_daily_energy,
    plot_environment,
    plot_power_curve_with_operation,
    plot_power_profile,
    plot_wind_profile,
    plot_wind_rose,
)

WIND_OVERVIEW = "Visão geral"
WIND_SIMULATION = "Simulação"
WIND_CATALOG = "Catálogo de aerogeradores"
WIND_EXPORT = "Exportação"
WIND_NAV = (WIND_OVERVIEW, WIND_SIMULATION, WIND_CATALOG, WIND_EXPORT)

CHART_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "svg", "filename": "modelo_eolico"},
}

WIND_CSS = """
<style>
  :root {
    --wind-navy: #173348;
    --wind-teal: #087D8C;
    --wind-cyan: #23A8B9;
    --wind-pale: #EAF7F8;
    --wind-border: #D6E3E8;
    --wind-text: #172630;
    --wind-muted: #667A87;
  }
  .wind-brand { text-align:center; padding:.8rem .2rem 1.1rem; }
  .wind-mark {
    width:68px; height:68px; display:grid; place-items:center; margin:0 auto .7rem;
    border-radius:50%; border:1px solid rgba(255,255,255,.25); background:rgba(255,255,255,.07);
    color:white; font-size:2.05rem;
  }
  .wind-brand-name { color:white; font-size:1.02rem; letter-spacing:.22em; font-weight:900; }
  .wind-brand-sub { color:#9BC5CE; font-size:.63rem; letter-spacing:.12em; font-weight:800; margin-top:.3rem; }
  .wind-head {
    border:1px solid var(--wind-border); border-radius:11px; padding:.78rem 1rem; margin-bottom:.68rem;
    background:linear-gradient(90deg,#F7FBFC 0%,#FFFFFF 70%);
  }
  .wind-eyebrow { color:var(--wind-teal); font-size:.68rem; font-weight:900; letter-spacing:.14em; text-transform:uppercase; }
  .wind-title { color:#14242D; font-size:1.55rem; line-height:1.08; font-weight:920; margin:.18rem 0 .08rem; letter-spacing:-.025em; }
  .wind-subtitle { color:#667A87; font-size:.76rem; line-height:1.5; }
  .wind-note {
    border-left:3px solid var(--wind-teal); background:#F0F8F9; padding:.62rem .74rem;
    border-radius:0 8px 8px 0; color:#355B65; font-size:.75rem; line-height:1.5;
  }
  .wind-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.48rem; }
  .wind-spec { border:1px solid #DFE7EB; background:#FBFCFD; border-radius:8px; padding:.58rem .64rem; min-height:68px; }
  .wind-spec small { display:block; color:#7B8B95; font-size:.58rem; letter-spacing:.09em; font-weight:850; text-transform:uppercase; }
  .wind-spec b { display:block; color:#1C303B; font-size:.82rem; margin-top:.15rem; }
  .wind-spec span { display:block; color:#7A8A94; font-size:.63rem; margin-top:.1rem; line-height:1.3; }
  .wind-chip { display:inline-flex; border-radius:999px; padding:.27rem .55rem; margin:.12rem .18rem .12rem 0; font-size:.65rem; font-weight:850; }
  .wind-ok { color:#087A55; background:#E9F7F1; border:1px solid #C3E9D9; }
  .wind-warn { color:#9B6200; background:#FFF5E2; border:1px solid #EFD59F; }
  .wind-info { color:#096B77; background:#EAF7F8; border:1px solid #C5E8EC; }
  .wind-kpi-note { color:#71828C; font-size:.65rem; line-height:1.35; }
  .wind-hero {
    border:1px solid #D9E5E9; border-radius:12px; background:linear-gradient(135deg,#F7FCFC 0%,#FFFFFF 58%,#EEF9F9 100%);
    padding:1.25rem 1.3rem;
  }
  .wind-hero h2 { margin:.18rem 0 .5rem; color:#142630; font-size:1.8rem; }
  .wind-hero p { color:#506974; font-size:.88rem; line-height:1.65; margin:0; }
  .wind-flow {
    display:grid; grid-template-columns:1fr auto 1fr auto 1fr auto 1fr; gap:.45rem; align-items:center;
    margin-top:.8rem;
  }
  .wind-flow-step { border:1px solid #DCE7EA; border-radius:9px; padding:.65rem; background:white; min-height:88px; }
  .wind-flow-step small { color:#087D8C; font-weight:900; font-size:.59rem; letter-spacing:.1em; }
  .wind-flow-step b { display:block; color:#263B45; font-size:.76rem; margin-top:.18rem; }
  .wind-flow-step span { display:block; color:#71838D; font-size:.66rem; margin-top:.15rem; line-height:1.35; }
  .wind-flow-arrow { color:#7B9BA4; font-size:1.2rem; font-weight:900; }
  @media(max-width:900px) {
    .wind-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .wind-flow { grid-template-columns:1fr; }
    .wind-flow-arrow { transform:rotate(90deg); text-align:center; }
  }
</style>
"""


def _init_wind_state() -> None:
    defaults = {
        "wind_page": WIND_OVERVIEW,
        "wind_raw": None,
        "wind_profile": None,
        "wind_result": None,
        "wind_kpis": None,
        "wind_density_summary": None,
        "wind_turbine_key": list(TURBINE_DB.keys())[0],
        "wind_turbine_count": 1,
        "wind_apply_grid_loss": False,
        "wind_mapping": None,
        "wind_source_name": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _header(eyebrow: str, title: str, subtitle: str | None = None) -> None:
    subtitle_html = f'<div class="wind-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="wind-head"><div class="wind-eyebrow">{eyebrow}</div><div class="wind-title">{title}</div>{subtitle_html}</div>',
        unsafe_allow_html=True,
    )


def _fmt(value, unit: str = "", decimals: int = 1, missing: str = "Não informado") -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return missing
    return f"{float(value):,.{decimals}f}{(' ' + unit) if unit else ''}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_list(values, unit="m") -> str:
    if not values:
        return "Não informado"
    return " / ".join(_fmt(v, unit, 0) for v in values)


def _chip(text: str, kind: str = "info") -> str:
    return f'<span class="wind-chip wind-{kind}">{text}</span>'


def _sidebar() -> str:
    with st.sidebar:
        if st.button("← FONTES DE ENERGIA", key="wind_back_sources", width="stretch"):
            st.session_state["energy_source"] = None
            st.rerun()
        st.markdown(
            '<div class="wind-brand"><div class="wind-mark">🌬</div><div class="wind-brand-name">EÓLICA</div><div class="wind-brand-sub">POWER CURVE ENGINE</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="sidebar-label">NAVEGAÇÃO</div>', unsafe_allow_html=True)
        current = st.session_state["wind_page"]
        for page in WIND_NAV:
            if st.button(page, key=f"wind_nav_{page}", type="primary" if current == page else "secondary", width="stretch"):
                if page != current:
                    st.session_state["wind_page"] = page
                    st.rerun()
        st.divider()
        st.markdown('<div class="sidebar-label">ESTADO DA EXECUÇÃO</div>', unsafe_allow_html=True)
        turbine = st.session_state.get("wind_turbine_key") or "Ainda não selecionado"
        result = st.session_state.get("wind_result")
        source = st.session_state.get("wind_source_name") or "Aguardando entrada"
        if result is not None:
            start = pd.to_datetime(result["timestamp"]).min()
            end = pd.to_datetime(result["timestamp"]).max()
            span = f"{start:%d/%m %H:%M}–{end:%d/%m %H:%M}"
        else:
            span = "Aguardando simulação"
        st.markdown(
            f'<div class="sidebar-status"><small>AEROGERADOR</small><b>{turbine}</b></div>'
            f'<div class="sidebar-status"><small>DADOS</small><b>{source}</b></div>'
            f'<div class="sidebar-status"><small>JANELA</small><b>{span}</b></div>',
            unsafe_allow_html=True,
        )
        st.divider()
        st.caption("V1: medições assumidas na altura do cubo · sem wake · direção não penaliza a potência.")
        return st.session_state["wind_page"]


def _render_overview() -> None:
    _header("Eólica · Visão geral", "MODELO ENERGÉTICO EÓLICO", "Curvas reais de fabricante + condições atmosféricas + perfil temporal de vento.")
    with st.container(border=True):
        st.markdown(
            """
            <div class="wind-hero">
              <div class="wind-eyebrow">Fronteira física da V1</div>
              <h2>Do vento à potência elétrica do aerogerador</h2>
              <p>
                A V1 não reconstrói rotor, caixa de engrenagens ou gerador com eficiências genéricas.
                A <b>curva de potência do fabricante</b> é a referência para a potência elétrica da máquina.
                Quando ativado pelo usuário, aplica-se apenas um desconto genérico adicional de <b>3%</b>
                entre o aerogerador e o ponto de inserção à rede, representando transformador, linhas,
                disjuntores e perdas elétricas externas à fronteira do aerogerador.
              </p>
              <div class="wind-flow">
                <div class="wind-flow-step"><small>01 · ENTRADA</small><b>Perfil meteorológico</b><span>Timestamp + vento. T, P, UR e direção são opcionais.</span></div>
                <div class="wind-flow-arrow">→</div>
                <div class="wind-flow-step"><small>02 · ATMOSFERA</small><b>Densidade do ar</b><span>Ar úmido, ar seco ou ρ = 1,225 kg/m³.</span></div>
                <div class="wind-flow-arrow">→</div>
                <div class="wind-flow-step"><small>03 · TURBINA</small><b>Curva do fabricante</b><span>Interpolação da curva parametrizada, com correção de densidade.</span></div>
                <div class="wind-flow-arrow">→</div>
                <div class="wind-flow-step"><small>04 · SAÍDA</small><b>Potência + energia + FC</b><span>Bruta da turbina e, opcionalmente, após desconto de 3%.</span></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns([1.15, .85], gap="large")
    with c1:
        with st.container(border=True):
            st.markdown('<div class="panel-title">Contrato de entrada</div>', unsafe_allow_html=True)
            st.markdown(
                """
                **Obrigatórios**
                - `timestamp`
                - `wind_speed`

                **Opcionais**
                - `temperature`
                - `pressure`
                - `humidity`
                - `wind_direction`
                """
            )
            st.markdown(
                '<div class="wind-note"><b>Altura da medição.</b> Nesta versão assume-se que a velocidade do vento fornecida corresponde à altura do cubo/nacele. Se a medição estiver em outra altura, deve ser corrigida antes da V1. O corretor de altura fica para uma versão posterior.</div>',
                unsafe_allow_html=True,
            )
    with c2:
        with st.container(border=True):
            st.markdown('<div class="panel-title">O que a V1 não modela</div>', unsafe_allow_html=True)
            st.markdown(
                "- Wake entre aerogeradores\n- Correção de altura / rugosidade\n- Turbulência e wind shear sobre o rotor\n- Yaw dinâmico\n- Curtailment / indisponibilidade\n- Controle mecânico detalhado"
            )
            st.info("A direção do vento é usada para análise/rosa dos ventos. Na V1 não reduz a potência: assume-se alinhamento ideal da nacele.")


def _mapping_widget(raw: pd.DataFrame) -> WindInputMapping:
    detected = detect_columns(raw.columns)
    columns = list(raw.columns)
    none_option = "— Não disponível —"

    def select_optional(label: str, semantic: str, key: str):
        opts = [none_option] + columns
        default = detected.get(semantic)
        idx = opts.index(default) if default in opts else 0
        value = st.selectbox(label, opts, index=idx, key=key)
        return None if value == none_option else value

    c1, c2 = st.columns(2)
    with c1:
        timestamp_default = detected.get("timestamp")
        ts_idx = columns.index(timestamp_default) if timestamp_default in columns else 0
        timestamp = st.selectbox("Timestamp *", columns, index=ts_idx, key="wind_map_timestamp")
        wind_default = detected.get("wind_speed")
        ws_idx = columns.index(wind_default) if wind_default in columns else min(1, len(columns)-1)
        wind_speed = st.selectbox("Velocidade do vento *", columns, index=ws_idx, key="wind_map_speed")
        wind_direction = select_optional("Direção do vento", "wind_direction", "wind_map_direction")
    with c2:
        temperature = select_optional("Temperatura", "temperature", "wind_map_temperature")
        pressure = select_optional("Pressão", "pressure", "wind_map_pressure")
        humidity = select_optional("Umidade relativa", "humidity", "wind_map_humidity")
    return WindInputMapping(timestamp, wind_speed, wind_direction, temperature, pressure, humidity)


def _load_example() -> tuple[pd.DataFrame, str]:
    path = Path(__file__).resolve().parent / "Dados_exemplo" / "perfil_eolico_sintetico_ceara_1_semana_10min.csv"
    return read_wind_csv(path), path.name


def _render_simulation() -> None:
    _header("Eólica · Simulação", "PERFIL DE POTÊNCIA E ENERGIA", "Selecione o aerogerador, carregue o perfil meteorológico e calcule a semana.")

    left, right = st.columns([.92, 1.08], gap="large")
    with left:
        with st.container(border=True):
            st.markdown('<div class="panel-title">1 · Configuração do sistema</div>', unsafe_allow_html=True)
            keys = list(TURBINE_DB.keys())
            current = st.session_state.get("wind_turbine_key", keys[0])
            turbine_key = st.selectbox("Aerogerador", keys, index=keys.index(current) if current in keys else 0)
            count = st.number_input("Quantidade de aerogeradores", min_value=1, max_value=500, value=int(st.session_state.get("wind_turbine_count", 1)), step=1)
            apply_loss = st.toggle(
                "Descontar 3% até o ponto de inserção à rede",
                value=bool(st.session_state.get("wind_apply_grid_loss", False)),
                help="Desconto genérico opcional após a potência elétrica do aerogerador: transformador, linhas, disjuntores e perdas externas equivalentes.",
            )
            entry = get_turbine(turbine_key)
            spec = entry["spec"]
            st.markdown(
                f'<div class="wind-grid" style="grid-template-columns:repeat(2,minmax(0,1fr));margin-top:.5rem">'
                f'<div class="wind-spec"><small>Potência unitária</small><b>{_fmt(spec["rated_power_kw"]/1000,"MW",2)}</b></div>'
                f'<div class="wind-spec"><small>Potência instalada</small><b>{_fmt(spec["rated_power_kw"]*count/1000,"MW",2)}</b></div>'
                f'<div class="wind-spec"><small>Rotor</small><b>{_fmt(spec["rotor_diameter_m"],"m",0)}</b></div>'
                f'<div class="wind-spec"><small>ρ ref.</small><b>{_fmt(entry["curve"].get("reference_density_kg_m3"),"kg/m³",3)}</b></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="wind-note" style="margin-top:.55rem"><b>Fronteira de perdas.</b> Não se aplicam eficiências adicionais de rotor, caixa ou gerador sobre a curva do fabricante. O switch acima é o único desconto elétrico externo da V1.</div>', unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown('<div class="panel-title">2 · Dados meteorológicos</div>', unsafe_allow_html=True)
            source_mode = st.radio("Fonte", ["Carregar CSV", "Exemplo sintético · Ceará"], horizontal=True)
            raw = None
            source_name = None
            if source_mode == "Carregar CSV":
                uploaded = st.file_uploader("Arquivo CSV", type=["csv", "txt"], help="Timestamp e velocidade do vento são obrigatórios.")
                if uploaded is not None:
                    try:
                        raw = read_wind_csv(uploaded)
                        source_name = uploaded.name
                    except Exception as exc:
                        st.error(f"Falha ao ler o arquivo: {exc}")
            else:
                raw, source_name = _load_example()
                st.caption("Semana sintética de 10 min inspirada no litoral do Ceará; medições assumidas na altura do cubo.")

            if raw is not None:
                st.success(f"{len(raw):,} linhas carregadas · {len(raw.columns)} colunas".replace(",", "."))
                with st.expander("Mapeamento de colunas", expanded=True):
                    mapping = _mapping_widget(raw)
                st.session_state["wind_raw"] = raw
                st.session_state["wind_mapping"] = mapping
                st.session_state["wind_source_name"] = source_name
                st.dataframe(raw.head(8), hide_index=True, width="stretch")
            else:
                st.info("Carregue um CSV ou use o exemplo sintético para habilitar o cálculo.")

    with right:
        with st.container(border=True):
            st.markdown('<div class="panel-title">3 · Execução</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="wind-note"><b>Lógica de densidade.</b> P + T + UR → ar úmido; P + T → ar seco; caso falte P ou T → ρ = 1,225 kg/m³. A direção é informativa e não altera a potência nesta versão.</div>',
                unsafe_allow_html=True,
            )
            run = st.button("▶ CALCULAR PERFIL EÓLICO", type="primary", width="stretch", disabled=raw is None)
            if run and raw is not None:
                try:
                    mapping = st.session_state["wind_mapping"]
                    profile = prepare_wind_profile(raw, mapping)
                    result, kpis, density_summary = run_wind_model(profile, turbine_key, int(count), bool(apply_loss))
                    st.session_state["wind_profile"] = profile
                    st.session_state["wind_result"] = result
                    st.session_state["wind_kpis"] = kpis
                    st.session_state["wind_density_summary"] = density_summary
                    st.session_state["wind_turbine_key"] = turbine_key
                    st.session_state["wind_turbine_count"] = int(count)
                    st.session_state["wind_apply_grid_loss"] = bool(apply_loss)
                    st.success("Simulação concluída.")
                except Exception as exc:
                    st.error(f"Não foi possível executar o modelo: {exc}")

            result = st.session_state.get("wind_result")
            kpis = st.session_state.get("wind_kpis")
            density_summary = st.session_state.get("wind_density_summary")
            if result is None or kpis is None:
                st.markdown("### Aguardando simulação")
                st.caption("Os KPIs e gráficos aparecem aqui após o cálculo.")
                return

            if st.session_state.get("wind_turbine_key") != turbine_key or st.session_state.get("wind_turbine_count") != int(count) or st.session_state.get("wind_apply_grid_loss") != bool(apply_loss):
                st.warning("A configuração da tela mudou desde a última execução. Clique em **CALCULAR PERFIL EÓLICO** para atualizar os resultados.")

            chips = []
            if result["temperature_c"].notna().any(): chips.append(_chip("✓ Temperatura", "ok"))
            else: chips.append(_chip("○ Temperatura ausente", "warn"))
            if result["pressure_hpa"].notna().any(): chips.append(_chip("✓ Pressão", "ok"))
            else: chips.append(_chip("○ Pressão ausente", "warn"))
            if result["humidity_pct"].notna().any(): chips.append(_chip("✓ Umidade", "ok"))
            else: chips.append(_chip("○ Umidade ausente", "warn"))
            if result["wind_direction_deg"].notna().any(): chips.append(_chip("✓ Direção", "ok"))
            else: chips.append(_chip("○ Direção ausente · yaw ideal", "warn"))
            st.markdown("".join(chips), unsafe_allow_html=True)

            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Energia bruta", f"{kpis['energy_gross_kwh']/1000:.2f} MWh")
            q2.metric("Energia após perdas", f"{kpis['energy_net_kwh']/1000:.2f} MWh")
            q3.metric("FC bruto", f"{kpis['capacity_factor_gross']*100:.2f} %")
            q4.metric("FC líquido", f"{kpis['capacity_factor_net']*100:.2f} %")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("P média", f"{kpis['power_mean_gross_kw']/1000:.2f} MW")
            r2.metric("P máxima", f"{kpis['power_max_gross_kw']/1000:.2f} MW")
            r3.metric("Vento médio", f"{kpis['wind_mean_mps']:.2f} m/s")
            r4.metric("ρ média", f"{kpis['air_density_mean_kg_m3']:.3f} kg/m³")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Horas equivalentes", f"{kpis['equivalent_hours_gross']:.1f} h")
            s2.metric("Horas gerando", f"{kpis['generating_hours']:.1f} h")
            s3.metric("Abaixo de cut-in", f"{kpis['below_cut_in_hours']:.1f} h")
            s4.metric("Em potência nominal", f"{kpis['nominal_hours']:.1f} h")

            if kpis["generic_grid_loss_applied"]:
                st.caption(f"Perda genérica aplicada: 3,00% · energia descontada = {kpis['energy_losses_kwh']/1000:.3f} MWh.")
            else:
                st.caption("Sem desconto externo: potência líquida = potência elétrica da curva do aerogerador.")
            if density_summary is not None:
                st.caption(
                    f"Densidade: {density_summary.dominant_mode} · úmido {density_summary.moist_count} pontos · seco {density_summary.dry_count} · referência {density_summary.reference_count}."
                )
            current_entry = get_turbine(st.session_state["wind_turbine_key"])
            if current_entry["spec"].get("cut_out_mps") is None:
                curve_max = float(current_entry["curve"].get("max_wind_mps") or 0.0)
                if float(result["wind_speed_mps"].max()) > curve_max:
                    st.warning(
                        f"O datasheet não informa V cut-out e o perfil ultrapassa {curve_max:.1f} m/s, limite da curva parametrizada. "
                        "Acima desse ponto a V1 mantém a última potência conhecida; interprete esse trecho com cautela."
                    )

    # Resultados em largura total
    result = st.session_state.get("wind_result")
    kpis = st.session_state.get("wind_kpis")
    if result is not None and kpis is not None:
        st.markdown("### Resultados temporais")
        g1, g2 = st.columns(2, gap="large")
        with g1:
            st.plotly_chart(plot_wind_profile(result), width="stretch", config=CHART_CONFIG)
        with g2:
            st.plotly_chart(plot_power_profile(result, kpis["generic_grid_loss_applied"]), width="stretch", config=CHART_CONFIG)
        g3, g4 = st.columns(2, gap="large")
        with g3:
            st.plotly_chart(plot_power_curve_with_operation(result, st.session_state["wind_turbine_key"]), width="stretch", config=CHART_CONFIG)
        with g4:
            rose = plot_wind_rose(result)
            if rose is not None:
                st.plotly_chart(rose, width="stretch", config=CHART_CONFIG)
            else:
                with st.container(border=True):
                    st.info("Direção do vento não disponível: rosa dos ventos omitida. O modelo assume alinhamento ideal da nacele.")
        g5, g6 = st.columns(2, gap="large")
        with g5:
            st.plotly_chart(plot_daily_energy(result, kpis["generic_grid_loss_applied"]), width="stretch", config=CHART_CONFIG)
        with g6:
            st.plotly_chart(plot_environment(result), width="stretch", config=CHART_CONFIG)

        with st.expander("Tabela detalhada da simulação"):
            st.dataframe(export_wind_dataframe(result), width="stretch", hide_index=True, height=420)


def _quality_label(value: str | None) -> str:
    mapping = {
        "manufacturer_spec": "Fabricante",
        "manufacturer_range; lower_bound_used_by_model": "Faixa do fabricante · limite inferior na V1",
        "manufacturer_range; upper_bound_used_as_representative": "Faixa do fabricante · limite superior na V1",
        "derived_from_curve": "Derivado da curva",
        "derived_from_curve_start": "Derivado do início da curva",
        "derived_from_curve_first_rated_point": "Derivado da curva",
        "derived_from_curve_endpoint": "Derivado do fim da curva",
        "not_provided": "Não informado",
        "exact_manufacturer_table": "Tabela exata do fabricante",
        "digitized_from_manufacturer_graph": "Digitalizada da gráfica do fabricante",
    }
    return mapping.get(value, value or "—")


def _render_catalog() -> None:
    _header("Eólica · Base parametrizada", "CATÁLOGO DE AEROGERADORES", "Curvas de potência, dados operacionais, rastreabilidade e qualidade da parametrização.")
    keys = list(TURBINE_DB.keys())
    selected = st.selectbox("Aerogerador do catálogo", keys, index=keys.index(st.session_state.get("wind_turbine_key")) if st.session_state.get("wind_turbine_key") in keys else 0)
    entry = get_turbine(selected)
    spec, curve, quality, source = entry["spec"], entry["curve"], entry["quality"], entry["source"]
    boundary = entry.get("power_boundary", {})

    with st.container(border=True):
        a, b = st.columns([1.15, .85], gap="large")
        with a:
            st.markdown(f"## {spec['manufacturer']} · {spec['model']}")
            st.caption(spec.get("notes") or "")
            st.markdown(
                f'<div class="wind-grid">'
                f'<div class="wind-spec"><small>Potência nominal</small><b>{_fmt(spec["rated_power_kw"]/1000,"MW",2)}</b></div>'
                f'<div class="wind-spec"><small>Rotor</small><b>{_fmt(spec["rotor_diameter_m"],"m",0)}</b></div>'
                f'<div class="wind-spec"><small>Área varrida</small><b>{_fmt(spec["swept_area_m2"],"m²",0)}</b></div>'
                f'<div class="wind-spec"><small>Potência específica</small><b>{_fmt(specific_power_w_m2(selected),"W/m²",0)}</b></div>'
                f'<div class="wind-spec"><small>V cut-in</small><b>{_fmt(spec.get("cut_in_mps"),"m/s",1)}</b><span>{_quality_label(quality.get("cut_in"))}</span></div>'
                f'<div class="wind-spec"><small>V nominal</small><b>{_fmt(spec.get("rated_wind_speed_mps"),"m/s",1)}</b><span>{_quality_label(quality.get("rated_wind_speed"))}</span></div>'
                f'<div class="wind-spec"><small>V cut-out</small><b>{_fmt(spec.get("cut_out_mps"),"m/s",1)}</b><span>{_quality_label(quality.get("cut_out"))}</span></div>'
                f'<div class="wind-spec"><small>Altura do cubo</small><b>{_fmt_list(spec.get("hub_height_options_m"))}</b></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with b:
            st.markdown("#### Dados complementares")
            st.write(f"**Classe IEC:** {spec.get('wind_class_iec') or 'Não informado'}")
            st.write(f"**Gerador:** {spec.get('generator') or 'Não informado'}")
            st.write(f"**Controle:** {spec.get('power_regulation') or 'Não informado'}")
            st.write(f"**Densidade de referência:** {_fmt(curve.get('reference_density_kg_m3'), 'kg/m³', 3)}")
            st.write(f"**Fonte da curva:** {_quality_label(quality.get('power_curve'))}")
            st.write(f"**Grandeza da curva:** potência elétrica do aerogerador")
            st.write(f"**Ponto de medição:** {boundary.get('measurement_point_label', 'Não explicitado')}")
            st.write(f"**Documento:** `{source.get('document')}` · pág. {', '.join(map(str, source.get('pages', [])))}")
            if selected == "Nordex N117/2400":
                st.success("Este modelo possui tabela do fabricante para múltiplas densidades (1,000–1,300 kg/m³); a simulação usa interpolação 2D dentro desse intervalo.")
            elif curve.get("density_correction") == "equivalent_wind_speed":
                st.info("A curva é corrigida por velocidade equivalente com base na densidade do ar.")

    c1, c2 = st.columns([1.4, .6], gap="large")
    with c1:
        st.plotly_chart(plot_catalog_curve(selected), width="stretch", config=CHART_CONFIG)
    with c2:
        with st.container(border=True):
            st.markdown('<div class="panel-title">Pontos da curva</div>', unsafe_allow_html=True)
            curve_df = pd.DataFrame(curve["points"], columns=["Velocidade (m/s)", "Potência (kW)"])
            st.dataframe(curve_df, hide_index=True, width="stretch", height=420)

    with st.container(border=True):
        st.markdown('<div class="panel-title">Comparar catálogo</div>', unsafe_allow_html=True)
        compare = st.multiselect("Curvas exibidas", keys, default=keys)
        if compare:
            st.plotly_chart(plot_catalog_comparison(compare), width="stretch", config=CHART_CONFIG)


def _render_export() -> None:
    _header("Eólica · Exportação", "RESULTADO PARA INTEGRAÇÃO", "CSV temporal pronto para consumo por outros módulos ou pelo futuro otimizador.")
    result = st.session_state.get("wind_result")
    kpis = st.session_state.get("wind_kpis")
    if result is None or kpis is None:
        st.info("Execute primeiro uma simulação eólica.")
        if st.button("Ir para Simulação", type="primary"):
            st.session_state["wind_page"] = WIND_SIMULATION
            st.rerun()
        return

    export_df = export_wind_dataframe(result)
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Linhas", len(export_df))
        c2.metric("Passo", f"{kpis['timestep_minutes']:.1f} min")
        c3.metric("Energia bruta", f"{kpis['energy_gross_kwh']/1000:.2f} MWh")
        c4.metric("FC bruto", f"{kpis['capacity_factor_gross']*100:.2f} %")
        st.dataframe(export_df.head(250), hide_index=True, width="stretch", height=390)
        csv_bytes = export_df.to_csv(index=False, sep=";", decimal=".", float_format="%.6f").encode("utf-8-sig")
        suffix = st.session_state.get("wind_turbine_key", "wind").replace(" ", "_").replace("/", "-")
        st.download_button("⬇️ BAIXAR RESULTADO CSV", data=csv_bytes, file_name=f"resultado_eolico_{suffix}.csv", mime="text/csv", type="primary", width="stretch")
        st.caption("Para integração energética, `power_gross_kw` representa a potência elétrica do conjunto de aerogeradores. `power_net_kw` só difere quando o desconto genérico de 3% foi ativado.")


def render_wind_app() -> None:
    _init_wind_state()
    st.markdown(WIND_CSS, unsafe_allow_html=True)
    page = _sidebar()
    if page == WIND_OVERVIEW:
        _render_overview()
    elif page == WIND_SIMULATION:
        _render_simulation()
    elif page == WIND_CATALOG:
        _render_catalog()
    else:
        _render_export()


__all__ = ["render_wind_app", "WIND_OVERVIEW", "WIND_SIMULATION", "WIND_CATALOG", "WIND_EXPORT"]
