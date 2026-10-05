"""Interface Streamlit do módulo EMS · despacho ótimo multifonte.

Fecha o fluxo da plataforma: os módulos calculam a dinâmica de cada fonte → o
EMS recebe essas séries como envelope/custo → escolhe, a cada minuto, quantos
stacks ligar e quanto cada fonte entrega para atender o perfil de carga.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from ems_integration import ponte
from ems_integration.executor import executar_pacote, validar_fc_dinamico
from visualization import ems_plots as P

EMS_OVERVIEW = "Visão geral"
EMS_CONFIG = "Configuração"
EMS_RESULTS = "Otimização"
EMS_COMPARE = "Comparação"
EMS_EXPORT = "Exportação"
EMS_NAV = (EMS_OVERVIEW, EMS_CONFIG, EMS_RESULTS, EMS_COMPARE, EMS_EXPORT)

ALGORITMOS = {
    "GWO · Grey Wolf Optimizer": 2,
    "NGO · Northern Goshawk Optimization": 3,
    "GA · Algoritmo genético": 1,
    "Só SQP (sem metaheurística)": 0,
}
ORIGEM_AUTO_FC = "Caracterização automática (modelo PEMFC)"
ORIGEM_AUTO_BAT = "Caracterização automática (modelo de bateria)"
ORIGEM_AUTO_TERM = "Disponibilidade automática (modelo térmico)"
ORIGEM_MODULO = "Resultado do módulo da plataforma"
DESATIVADA = "Desativada"
MAX_HISTORICO = 12
PASSO_VALIDACAO_S = 10.0   # H2 a 0,1 % do obtido com 2 s; o custo do modelo quase não depende do passo

CHART_CONFIG = {
    "displaylogo": False, "responsive": True, "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "svg", "filename": "ems_despacho"},
}

EMS_CSS = """
<style>
  :root { --ems:#4B3FB5; --ems-border:#DCDAF0; --ems-text:#1D1A3A; }
  [data-testid="stSidebar"] { background:linear-gradient(180deg,#1D1A3A 0%,#2A2556 100%); border-right:1px solid #3A3570; }
  [data-testid="stSidebar"] p,[data-testid="stSidebar"] span,[data-testid="stSidebar"] label,[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 { color:#F0EEFB !important; }
  .ems-brand { text-align:center; padding:1rem .3rem 1.25rem; }
  .ems-mark { width:68px;height:68px;margin:0 auto .7rem;display:grid;place-items:center;border-radius:16px;background:#4B3FB5;color:white;font-size:1.5rem;border:1px solid rgba(255,255,255,.2);font-weight:900; }
  .ems-brand-name { color:white;font-weight:900;letter-spacing:.18em;font-size:1rem; }
  .ems-brand-sub { color:#B7B0EA;font-weight:750;letter-spacing:.1em;font-size:.62rem;margin-top:.3rem; }
  .ems-head { border:1px solid var(--ems-border);border-radius:10px;padding:.76rem .95rem;margin-bottom:.65rem;background:white; }
  .ems-eyebrow { color:var(--ems);font-size:.66rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase; }
  .ems-title { color:var(--ems-text);font-size:1.55rem;font-weight:920;letter-spacing:-.03em;margin:.18rem 0 .1rem; }
  .ems-sub { color:#66637F;font-size:.78rem; }
  .ems-note { border-left:3px solid var(--ems);border-radius:0 8px 8px 0;background:#F3F2FC;padding:.62rem .72rem;color:#403C66;font-size:.76rem;line-height:1.55; }
  .ems-flow { display:grid; grid-template-columns:1fr auto 1fr auto 1fr auto 1fr; align-items:stretch; gap:.55rem; margin:.9rem 0 1.1rem; }
  .ems-arrow { display:flex; align-items:center; color:#B3ADE6; font-size:1.7rem; font-weight:900; }
  .ems-card { position:relative; border:1px solid #E1DFF3; border-radius:14px; padding:1.05rem .95rem .95rem; background:#FFFFFF;
              box-shadow:0 2px 10px rgba(45,38,110,.06); border-top:5px solid var(--cor); }
  .ems-num { position:absolute; top:.7rem; right:.8rem; width:26px; height:26px; border-radius:50%; display:grid; place-items:center;
             background:var(--cor); color:white; font-size:.78rem; font-weight:900; }
  .ems-ico { width:54px; height:54px; border-radius:14px; display:grid; place-items:center; font-size:1.65rem;
             background:var(--fundo); margin-bottom:.65rem; }
  .ems-card h4 { margin:0 0 .35rem !important; padding:0 !important; color:#1D1A3A; font-size:1.02rem; font-weight:900; line-height:1.25; }
  .ems-card p { margin:0; color:#55517A; font-size:.8rem; line-height:1.5; }
  .ems-chips { display:flex; flex-wrap:wrap; gap:.3rem; margin-top:.6rem; }
  .ems-chip { font-size:.66rem; font-weight:800; color:#3F3596; background:#EFEDFB; border:1px solid #DAD6F5; border-radius:999px; padding:.14rem .5rem; }
  .ems-saidas { display:flex; flex-wrap:wrap; gap:.45rem; margin:.2rem 0 1rem; }
  .ems-saida { font-size:.78rem; font-weight:750; color:#1D1A3A; background:#F6F5FD; border:1px solid #E1DFF3; border-radius:10px; padding:.45rem .7rem; }
  @media (max-width: 1100px) {
    .ems-flow { grid-template-columns:1fr 1fr; }
    .ems-arrow { display:none; }
  }
  @media (max-width: 640px) { .ems-flow { grid-template-columns:1fr; } }
</style>
"""


# ================================================================== estado
def _init_state() -> None:
    for k, v in {"ems_page": EMS_OVERVIEW, "ems_historico": [], "ems_sel": None, "ems_contador": 0}.items():
        st.session_state.setdefault(k, v)


def _header(title: str, eyebrow: str, subtitle: str) -> None:
    st.markdown(f'<div class="ems-head"><div class="ems-eyebrow">{eyebrow}</div>'
                f'<div class="ems-title">{title}</div><div class="ems-sub">{subtitle}</div></div>',
                unsafe_allow_html=True)


def _ir(pagina: str) -> None:
    st.session_state["ems_page"] = pagina
    st.rerun()


def _resultado_atual() -> dict | None:
    hist = st.session_state["ems_historico"]
    if not hist:
        return None
    sel = st.session_state.get("ems_sel")
    return next((h for h in hist if h["id"] == sel), hist[-1])


def _sidebar() -> str:
    with st.sidebar:
        if st.button("← FONTES DE ENERGIA", key="ems_back_sources", width="stretch"):
            st.session_state["energy_source"] = None
            st.rerun()
        st.markdown('<div class="ems-brand"><div class="ems-mark">EMS</div><div class="ems-brand-name">DESPACHO</div>'
                    '<div class="ems-brand-sub">OTIMIZAÇÃO MULTIFONTE</div></div>', unsafe_allow_html=True)
        page = st.session_state["ems_page"]
        for option in EMS_NAV:
            if st.button(option, key=f"ems_nav_{option}", type="primary" if option == page else "secondary",
                         width="stretch"):
                _ir(option)
        st.divider()
        st.caption("MÓDULOS COM RESULTADO NA SESSÃO")
        for rotulo, chave in (("Solar", "results_by_model"), ("Eólica", "wind_result"), ("Térmica", "thermal_result"),
                              ("Bateria", "battery_result"), ("H₂ / PEMFC", "h2_result")):
            ok = bool(st.session_state.get(chave) is not None and (chave != "results_by_model"
                                                                  or st.session_state.get(chave)))
            st.caption(("● " if ok else "○ ") + rotulo)
        item = _resultado_atual()
        if item:
            r = item["resultado"]
            st.divider()
            st.caption(f"ÚLTIMA EXECUÇÃO · #{item['id']} · {r['algoritmo']}")
            h2 = r["rel"]["consumo_fisico"].get("fc", {}).get("valor")
            if h2 is not None:
                st.metric("H₂ consumido", f"{h2:.2f} kg")
            st.metric("Custo total", f"R$ {r['rel']['custo_total_rs']:,.2f}")
        return st.session_state["ems_page"]


# ============================================================== caches
@st.cache_data(show_spinner=False, max_entries=16)
def _cache_fc(t0_iso: str, dur: float) -> pd.DataFrame:
    return ponte.caracterizar_fc(pd.Timestamp(t0_iso), dur)


@st.cache_data(show_spinner=False, max_entries=16)
def _cache_bat(t0_iso, dur, modelo, key, Ns, Np, soc0, c_desc, c_carga):
    return ponte.caracterizar_bateria(pd.Timestamp(t0_iso), dur, modelo, key, Ns, Np, soc0, c_desc, c_carga)


def _cfg_termica(pmax_kW, cvu, pmin_kW, ramp_kW_min, partida):
    from config.thermal_database import LOCAL_GENERATOR
    from models.thermal_model import ThermalConfig
    ramp = ramp_kW_min / 1000.0 if ramp_kW_min > 0 else None
    return ThermalConfig(dynamic=LOCAL_GENERATOR, pmax_mw=pmax_kW / 1000.0, cvu_rs_mwh=cvu,
                         pmin_technical_mw=pmin_kW / 1000.0, ramp_up_mw_min=ramp, ramp_down_mw_min=ramp,
                         startup_cost_rs=partida)


@st.cache_data(show_spinner=False, max_entries=16)
def _cache_term(t0_iso, dur, pmax_kW, cvu, pmin_kW, ramp, partida) -> pd.DataFrame:
    return ponte.disponibilidade_termica(pd.Timestamp(t0_iso), dur, _cfg_termica(pmax_kW, cvu, pmin_kW, ramp, partida))


@st.cache_data(show_spinner=False)
def _cache_wf_opcoes() -> pd.DataFrame:
    return ponte.opcoes_walkforward()


# ================================================================ visão geral
def _cartao(num: int, icone: str, titulo: str, texto: str, cor: str, fundo: str, chips: tuple[str, ...] = ()) -> str:
    extra = ""
    if chips:
        extra = '<div class="ems-chips">' + "".join(f'<span class="ems-chip">{c}</span>' for c in chips) + "</div>"
    return (f'<div class="ems-card" style="--cor:{cor};--fundo:{fundo}"><div class="ems-num">{num}</div>'
            f'<div class="ems-ico">{icone}</div><h4>{titulo}</h4><p>{texto}</p>{extra}</div>')


def _render_overview() -> None:
    _header("EMS · Despacho ótimo multifonte", "O QUE O EMS FAZ",
            "Recebe o perfil de carga e decide, minuto a minuto, quanto cada fonte entrega e quantos stacks de "
            "H₂ ficam ligados, para atender a carga ao menor custo.")
    seta = '<div class="ems-arrow">➜</div>'
    cartoes = [
        _cartao(1, "🔌", "Puxa os modelos das fontes",
                "Usa as séries calculadas pelos módulos da plataforma: PEMFC, bateria, térmica, solar e eólica. "
                "Os modelos não são alterados.", "#4B3FB5", "#EFEDFB"),
        _cartao(2, "☀️", "Desconta as renováveis",
                "Solar e eólica são <b>não despacháveis</b>: toda a potência delas entra primeiro e abate a carga. "
                "O que sobra é a carga líquida.", "#E9A23B", "#FDF3E2"),
        _cartao(3, "🧠", "Metaheurística + refino local",
                "Divide a carga líquida entre <b>FC, bateria e térmica</b> ao menor custo. A metaheurística "
                "(GA, GWO ou NGO) busca uma boa solução e o refino local a ajusta respeitando:",
                "#16869B", "#E3F3F6", ("Teto / piso", "Rampa", "Curva kg H₂/kWh", "Eficiências", "SOC")),
        _cartao(4, "✅", "Validação",
                "O despacho da FC volta ao modelo dinâmico PEMFC da plataforma, que confere o H₂ realmente "
                "consumido.", "#2E9E5B", "#E4F5EA"),
    ]
    st.markdown('<div class="ems-flow">' + seta.join(cartoes) + "</div>", unsafe_allow_html=True)

    st.markdown("##### O que você recebe")
    st.markdown('<div class="ems-saidas">' + "".join(f'<span class="ems-saida">{t}</span>' for t in (
        "💧 Consumo de H₂", "🍩 Participação de cada fonte", "📈 Despacho de potência no tempo",
        "🔢 Stacks ligados no tempo", "⚖️ Metaheurística × refino", "🔋 SOC final da bateria")) + "</div>",
        unsafe_allow_html=True)
    if st.button("Configurar despacho →", type="primary"):
        _ir(EMS_CONFIG)


# ============================================================ configuração
def _secao_carga() -> ponte.PerfilCarga | None:
    tipo = st.radio("Perfil de carga", ("Walk-forward · embarcação (2 h)", "COPEL B1 · 24 h", "CSV próprio"),
                    horizontal=True, key="ems_carga_tipo")
    try:
        if tipo.startswith("Walk"):
            op = _cache_wf_opcoes()
            c1, c2, c3 = st.columns(3)
            cen = c1.selectbox("Cenário", sorted(op.scenario.unique()), index=1, key="ems_wf_cen")
            prof = c2.selectbox("Perfil de uso", ["Econômico", "Normal", "Máxima"], index=1, key="ems_wf_prof")
            hora = c3.selectbox("Início", sorted(op.start_hour.unique()), index=4, key="ems_wf_hora",
                                format_func=lambda h: f"{int(h):02d}:00")
            carga = ponte.carga_walkforward(cen, prof, int(hora))
        elif tipo.startswith("COPEL"):
            c1, c2, c3 = st.columns(3)
            dia = c1.selectbox("Dia", ["util", "sabado", "domingo"], key="ems_copel_dia",
                               format_func=lambda d: {"util": "Dia útil", "sabado": "Sábado", "domingo": "Domingo"}[d])
            ini = c2.number_input("Início [h]", 0, 23, 8, key="ems_copel_ini")
            dur = c3.number_input("Duração [min]", 30, 1440, 120, step=30, key="ems_copel_dur")
            carga = ponte.recortar(ponte.carga_copel(dia), ini * 60, min(dur, 1439 - ini * 60))
        else:
            up = st.file_uploader("CSV de carga (t_min,P_kW ou timestamp,P_kW)", type=["csv"], key="ems_carga_up")
            if up is None:
                st.info("Colunas aceitas: `t_min`/`tempo` ou `timestamp`, e `P_kW`/`potencia`/`load`. "
                        "A série é reamostrada em passo de 1 min.")
                return None
            base = ponte.carga_de_dataframe(pd.read_csv(up, sep=None, engine="python"), up.name)
            c1, c2 = st.columns(2)
            ini = c1.number_input("Início [min]", 0, int(base.duracao_min) - 5, 0, key="ems_csv_ini")
            dur = c2.number_input("Duração [min]", 5, int(base.duracao_min), min(120, int(base.duracao_min)),
                                  key="ems_csv_dur")
            carga = ponte.recortar(base, ini, dur)
    except Exception as exc:
        st.error(f"Perfil de carga inválido: {exc}")
        return None
    if carga.t_min.size > 360:
        st.warning(f"{carga.t_min.size} passos: a execução leva proporcionalmente mais tempo (≈ 1–3 s por 100 "
                   "passos com FC + bateria, mais com térmica).")
    st.plotly_chart(P.fig_carga(carga.t_min, carga.P_kW,
                                f"{carga.descricao} · pico {carga.P_kW.max():.0f} kW · média {carga.P_kW.mean():.0f} kW"),
                    width="stretch", config=CHART_CONFIG)
    return carga


def _tem(chave: str) -> bool:
    v = st.session_state.get(chave)
    return v is not None and (not isinstance(v, dict) or bool(v))


def _secao_fontes(carga_pico: float | None = None) -> dict:
    spec: dict = {}
    col1, col2 = st.columns(2, gap="large")
    with col1:
        with st.container(border=True):
            st.markdown("##### 💧 H₂ / PEMFC")
            ops = [ORIGEM_AUTO_FC] + ([ORIGEM_MODULO] if _tem("h2_result") else []) + [DESATIVADA]
            spec["fc"] = {"origem": st.selectbox("Origem", ops, key="ems_fc_origem")}
            if spec["fc"]["origem"] != DESATIVADA:
                c1, c2 = st.columns(2)
                spec["fc"]["N_fc"] = c1.number_input("Stacks instalados", 1, 12, 4, key="ems_fc_n")
                base = c2.radio("Base do envelope", ("Potência entregue", "Potência do stack"), key="ems_fc_base",
                                help="Entregue = líquida, após auxiliares e DC/DC (é o que chega ao barramento). "
                                     "Stack = bruta, como no EMS original (superestima a FC em ~30 %).")
                spec["fc"]["base"] = "entregue" if base.startswith("Potência e") else "stack"
                st.caption(f"Capacidade instalada ≈ {50 * spec['fc']['N_fc']:.0f} kW líquidos "
                           "(stack Horizon equivalente de ~50 kW).")
        with st.container(border=True):
            st.markdown("##### 🔥 Térmica")
            ops = [DESATIVADA, ORIGEM_AUTO_TERM] + ([ORIGEM_MODULO] if _tem("thermal_result") else [])
            spec["termica"] = {"origem": st.selectbox("Origem", ops, key="ems_term_origem")}
            if spec["termica"]["origem"] == ORIGEM_AUTO_TERM:
                c1, c2, c3 = st.columns(3)
                spec["termica"]["pmax_kW"] = c1.number_input("Pmax [kW]", 1.0, 5000.0, 80.0, key="ems_term_pmax")
                spec["termica"]["pmin_kW"] = c2.number_input("Mín. técnico [kW]", 0.0, 5000.0, 20.0, key="ems_term_pmin")
                spec["termica"]["cvu"] = c3.number_input("CVU [R$/MWh]", 0.0, 10000.0, 1100.0, key="ems_term_cvu")
                c4, c5 = st.columns(2)
                spec["termica"]["ramp"] = c4.number_input("Rampa [kW/min] (0 = livre)", 0.0, 5000.0, 20.0,
                                                          key="ems_term_ramp")
                spec["termica"]["partida"] = c5.number_input("Custo de partida [R$]", 0.0, 1e5, 50.0,
                                                             key="ems_term_partida")
                st.caption("Gerador local pedido no Pmax durante toda a missão: o EMS lê isso como disponibilidade.")
    with col2:
        with st.container(border=True):
            st.markdown("##### 🔋 Bateria")
            ops = [ORIGEM_AUTO_BAT] + ([ORIGEM_MODULO] if _tem("battery_result") else []) + [DESATIVADA]
            spec["bateria"] = {"origem": st.selectbox("Origem", ops, key="ems_bat_origem")}
            b = spec["bateria"]
            if b["origem"] == ORIGEM_AUTO_BAT:
                from models.battery_model import BATTERY_2RC, BATTERY_MODEL_LABELS, BATTERY_TREMBLAY, TREMBLAY_BATTERIES
                c1, c2 = st.columns(2)
                b["modelo"] = c1.selectbox("Modelo", [BATTERY_TREMBLAY, BATTERY_2RC], key="ems_bat_modelo",
                                           format_func=lambda k: BATTERY_MODEL_LABELS[k])
                b["key"] = None
                if b["modelo"] == BATTERY_TREMBLAY:
                    chaves = list(TREMBLAY_BATTERIES)
                    b["key"] = c2.selectbox("Célula", chaves, index=chaves.index("liion_3p3v_2p3ah"), key="ems_bat_cel",
                                            format_func=lambda k: TREMBLAY_BATTERIES[k].name)
                c3, c4 = st.columns(2)
                b["Ns"] = c3.number_input("Células em série · Ns", 1, 2000, 200, key="ems_bat_ns")
                b["Np"] = c4.number_input("Strings em paralelo · Np", 1, 2000, 132, key="ems_bat_np")
                c5, c6 = st.columns(2)
                b["c_desc"] = c5.number_input("Taxa máx. descarga [C]", 0.1, 5.0, 1.0, 0.1, key="ems_bat_cd")
                b["c_carga"] = c6.number_input("Taxa máx. carga [C]", 0.1, 5.0, 0.5, 0.1, key="ems_bat_cc")
                E, _ = ponte.energia_banco_kWh(b["modelo"], b["key"], int(b["Ns"]), int(b["Np"]))
                st.caption(f"Banco nominal ≈ {E:.1f} kWh · descarga até ≈ {E * b['c_desc']:.0f} kW")
            if b["origem"] != DESATIVADA:
                c7, c8, c9 = st.columns(3)
                if b["origem"] == ORIGEM_AUTO_BAT:
                    b["soc0"] = c7.slider("SOC inicial [%]", 5, 95, 60, key="ems_bat_soc0") / 100
                b["soc_min"] = c8.slider("SOC mín. [%]", 0, 60, 20, key="ems_bat_socmin") / 100
                b["soc_max"] = c9.slider("SOC máx. [%]", 40, 100, 90, key="ems_bat_socmax") / 100
        with st.container(border=True):
            st.markdown("##### ☀️ 🌬️ Renováveis · não despacháveis")
            st.caption("Toda a potência de solar e eólica é descontada da carga antes da otimização; o EMS "
                       "despacha FC, bateria e térmica só para o restante. As séries vêm dos módulos da plataforma.")
            if _tem("results_by_model"):
                from simulation.multimodel import MODEL_LABELS
                res = st.session_state["results_by_model"]
                modelos = list(res)
                pref = st.session_state.get("selected_result_model")
                ops_pv = [f"Módulo Solar · {MODEL_LABELS.get(m, m)}" for m in modelos] + [DESATIVADA]
                esc = st.selectbox("Solar", ops_pv, index=modelos.index(pref) if pref in modelos else 0,
                                   key="ems_pv_origem")
                spec["pv"] = {"origem": DESATIVADA if esc == DESATIVADA else ORIGEM_MODULO,
                              "modelo": None if esc == DESATIVADA else modelos[ops_pv.index(esc)]}
            else:
                spec["pv"] = {"origem": DESATIVADA}
                st.caption("☀️ Solar: sem resultado na sessão. Rode o módulo **Solar** e volte aqui.")
            if _tem("wind_result"):
                esc = st.selectbox("Eólica", ["Módulo Eólica · resultado da sessão", DESATIVADA], key="ems_eol_origem")
                spec["eolica"] = {"origem": DESATIVADA if esc == DESATIVADA else ORIGEM_MODULO}
                pico = float(np.nanmax(st.session_state["wind_result"]["power_net_kw"])) \
                    if "power_net_kw" in st.session_state["wind_result"] else None
                if pico is not None and carga_pico and pico > 2 * carga_pico:
                    st.caption(f"⚠️ Pico eólico de {pico:.0f} kW contra carga de {carga_pico:.0f} kW: nos períodos de "
                               "vento a eólica cobre a carga sozinha e o excedente é vertido.")
            else:
                spec["eolica"] = {"origem": DESATIVADA}
                st.caption("🌬️ Eólica: sem resultado na sessão. Rode o módulo **Eólica** e volte aqui.")
        spec["alinhar"] = st.checkbox(
            "Alinhar séries longas ao horário de início da missão", True, key="ems_alinhar",
            help="Térmica, eólica e solar de 24 h ou mais são cortadas no mesmo horário do dia em que a missão começa. "
                 "Sem isso, cada série é lida a partir do seu próprio primeiro instante.")
    return spec


def _secao_otimizacao() -> dict:
    o: dict = {}
    c1, c2 = st.columns([1.2, 1], gap="large")
    with c1:
        nome = st.radio("Metaheurística", list(ALGORITMOS), key="ems_alg")
        o["algoritmo"] = ALGORITMOS[nome]
        o["meta_penalizada"] = st.toggle(
            "Metaheurística com penalidade de restrições", False, key="ems_meta_pen",
            help="Desligado (original): a metaheurística minimiza só o custo e serve de ponto inicial do SQP. "
                 "Ligado: minimiza custo + 10× o preço do déficit por kW de violação.")
        o["validar"] = st.toggle(
            "Validar o H₂ no modelo dinâmico PEMFC logo após o despacho", False, key="ems_validar",
            help="Reenvia o despacho de cada stack ao modelo dinâmico (≈ 15–20 s por stack em 2 h de missão). "
                 "Também pode ser feito depois, sob demanda, na aba H₂ da página Otimização.")
    with c2:
        o["N"] = st.number_input(
            "Horizonte de previsão N [passos de 1 min]", 1, 15, 3, key="ems_N",
            help="3 = valor do EMS original. Horizonte curto é míope para custo de partida: com térmica "
                 "(partida R$ 50) e N=3 o otimizador a desliga no 1º minuto e nunca religa; com N=8 ela fica "
                 "ligada e o custo cai ~30 %. O tempo de execução cresce com N.")
        o["seed"] = int(st.number_input(
            "Semente aleatória (repetibilidade)", 0, 10_000, 0, key="ems_seed",
            help="GA, GWO e NGO fazem sorteios internos. A semente fixa esses sorteios: mesma semente + mesmas "
                 "entradas = exatamente o mesmo resultado. Troque o número para ver outra sequência de sorteios."))
        o["soc_alvo_tol"] = st.number_input("Tolerância do SOC-alvo (±)", 0.01, 0.5, 0.05, 0.01, key="ems_soctol",
                                            help="Ao fim de cada horizonte o SOC deve ficar a ± este valor do SOC "
                                                 "inicial (banda do despacho.m original).")
    with st.expander("Parâmetros econômicos e de conversão (placeholders do EMS original)"):
        e1, e2, e3, e4 = st.columns(4)
        o["econ"] = {
            "preco_H2_rs_kg": e1.number_input("Preço H₂ [R$/kg]", 0.0, 500.0, 25.0, key="ems_h2price"),
            "c_deg_bateria_rs_kWh": e2.number_input("Degradação bateria [R$/kWh]", 0.0, 10.0, 0.08, 0.01,
                                                    key="ems_cdeg"),
            "pen_deficit_rs_kWh": e3.number_input("Penalidade déficit [R$/kWh]", 0.0, 1e4, 50.0, key="ems_pdef"),
            "pen_excesso_rs_kWh": e4.number_input("Penalidade vertimento [R$/kWh]", 0.0, 1e3, 0.5, key="ems_pexc"),
        }
        k1, k2, k3 = st.columns(3)
        o["eta_conv"] = {
            "eta_dc1": k1.number_input("η conversor FC → barramento (base stack)", 0.5, 1.0, 0.97, 0.01, key="ems_eta1",
                                         help="Só é aplicado quando o envelope usa potência bruta do stack. "
                                              "Com 'Potência entregue', P_FC_delivered_kW já é líquida e η=1 no balanço."),
            "eta_dc2": k2.number_input("η conversor bateria ↔ barramento", 0.5, 1.0, 0.96, 0.01, key="ems_eta2"),
            "eta_dc": k3.number_input("η conversor PV", 0.5, 1.0, 0.97, 0.01, key="ems_eta0"),
        }
        st.caption("A penalidade de déficit deve ficar 10–100× acima do maior custo variável (H₂ ≈ "
                   f"{0.06 * o['econ']['preco_H2_rs_kg']:.2f} R$/kWh), senão o otimizador “compra” déficit. "
                   "O vertimento reportado soma excesso despachável + excedente solar/eólico não aproveitado.")
    return o


def _montar_pacote(carga: ponte.PerfilCarga, spec: dict, opt: dict) -> Path:
    t0, dur = carga.t0, carga.duracao_min
    t0_iso = t0.isoformat()
    tabelas: dict[str, pd.DataFrame] = {}
    opcoes: dict = {}
    notas: list[str] = []
    N_fc = 1

    fc = spec["fc"]
    if fc["origem"] != DESATIVADA:
        N_fc = int(fc["N_fc"])
        opcoes["fc_base_potencia"] = fc["base"]
        if fc["origem"] == ORIGEM_AUTO_FC:
            tabelas["fc"] = _cache_fc(t0_iso, dur)
        else:
            tabelas["fc"] = st.session_state["h2_result"][[c for c in ponte.FC_COLUNAS
                                                           if c in st.session_state["h2_result"].columns]]

    b = spec["bateria"]
    if b["origem"] != DESATIVADA:
        if b["origem"] == ORIGEM_AUTO_BAT:
            df, E = _cache_bat(t0_iso, dur, b["modelo"], b["key"], int(b["Ns"]), int(b["Np"]), float(b["soc0"]),
                               float(b["c_desc"]), float(b["c_carga"]))
        else:
            from models.battery_model import export_battery_dataframe
            cfgb = st.session_state.get("battery_config") or {}
            df = export_battery_dataframe(st.session_state["battery_result"])
            E, _ = ponte.energia_banco_kWh(cfgb.get("model_id", "tremblay"), cfgb.get("battery_key"),
                                           int(cfgb.get("n_series", 1)), int(cfgb.get("n_parallel", 1)))
        soc0 = float(df.soc_percent.iloc[0]) / 100
        if not b["soc_min"] <= soc0 <= b["soc_max"]:
            raise ValueError(f"SOC inicial da bateria ({soc0:.0%}) fora da faixa [{b['soc_min']:.0%}, {b['soc_max']:.0%}].")
        tabelas["bateria"] = df
        opcoes.update(bateria_E_kWh=float(E), bateria_SOC_min=b["soc_min"], bateria_SOC_max=b["soc_max"])

    tm = spec["termica"]
    if tm["origem"] != DESATIVADA:
        if tm["origem"] == ORIGEM_AUTO_TERM:
            tabelas["termica"] = _cache_term(t0_iso, dur, tm["pmax_kW"], tm["cvu"], tm["pmin_kW"], tm["ramp"],
                                             tm["partida"])
            opcoes.update(ponte.opcoes_termica(_cfg_termica(tm["pmax_kW"], tm["cvu"], tm["pmin_kW"], tm["ramp"],
                                                            tm["partida"])))
        else:
            from models.thermal_model import export_thermal_dataframe
            df = export_thermal_dataframe(st.session_state["thermal_result"])
            if spec["alinhar"]:
                df, msg = ponte.alinhar_horario(df, t0, dur)
                notas.append(f"Térmica: {msg}")
            tabelas["termica"] = df
            if st.session_state.get("thermal_config") is not None:
                opcoes.update(ponte.opcoes_termica(st.session_state["thermal_config"]))

    eolica = None
    if spec["eolica"]["origem"] == ORIGEM_MODULO:
        eolica, msg = ponte.eolica_de_modulo(st.session_state["wind_result"], t0, dur, spec["alinhar"])
        notas.append(f"Eólica: {msg}")

    pv = None
    if spec["pv"]["origem"] == ORIGEM_MODULO:
        modelo = spec["pv"]["modelo"]
        pv, msg = ponte.pv_de_solar(st.session_state["results_by_model"][modelo], t0, dur, spec["alinhar"])
        notas.append(f"Solar ({modelo}): {msg}")

    if not tabelas:
        raise ValueError("Ative pelo menos uma fonte despachável (H₂/PEMFC, bateria ou térmica).")
    config = {
        "tag": carga.descricao, "N_fc": N_fc, "Ts_s": 60, "N": int(opt["N"]), "algoritmo": opt["algoritmo"],
        "meta_penalizada": opt["meta_penalizada"], "seed": opt["seed"], "soc_alvo_tol": opt["soc_alvo_tol"],
        "econ": opt["econ"], "eta_conv": opt["eta_conv"], "opcoes_fontes": opcoes,
        "pv_P_rated_kWp": float(pv.P_kW.max()) + 1.0 if pv is not None else None, "notas": notas,
    }
    return ponte.escrever_pacote(carga, tabelas, pv, config, eolica=eolica)


def _executar(pasta: Path, algoritmos: list[int], validar: bool) -> None:
    barra = st.progress(0.0, text="Preparando…")
    total = len(algoritmos)
    for i, alg in enumerate(algoritmos):
        rotulo = next(k for k, v in ALGORITMOS.items() if v == alg)

        def prog(k, n, i=i, rotulo=rotulo):
            if k % 5 == 0 or k == n:
                barra.progress((i + k / n) / total, text=f"{rotulo} · passo {k}/{n}")

        r = executar_pacote(pasta, progresso=prog, sobrescrever={"algoritmo": alg})
        val = None
        if validar and "fc" in r["nomes"]:
            barra.progress((i + 1) / total, text=f"{rotulo} · validando H₂ no modelo dinâmico PEMFC…")
            try:
                val = validar_fc_dinamico(r, passo_s=PASSO_VALIDACAO_S)
            except Exception as exc:  # validação não deve derrubar o resultado do despacho
                r["avisos"].append(f"Validação dinâmica falhou: {exc}")
        st.session_state["ems_contador"] += 1
        item = {"id": st.session_state["ems_contador"], "resultado": r, "validacao": val,
                "quando": datetime.now().strftime("%H:%M:%S")}
        st.session_state["ems_historico"] = (st.session_state["ems_historico"] + [item])[-MAX_HISTORICO:]
        st.session_state["ems_sel"] = item["id"]
    barra.progress(1.0, text="Concluído.")


def _render_config() -> None:
    _header("EMS · Configuração do despacho", "ENTRADAS DO OTIMIZADOR",
            "Escolha o perfil de carga, de onde vem cada fonte e a metaheurística. Ao executar, a plataforma "
            "calcula os modelos e entrega as séries ao EMS.")
    with st.container(border=True):
        st.markdown("#### 1 · Perfil de carga")
        carga = _secao_carga()
    with st.container(border=True):
        st.markdown("#### 2 · Fontes")
        spec = _secao_fontes(float(carga.P_kW.max()) if carga is not None else None)
    with st.container(border=True):
        st.markdown("#### 3 · Método de otimização")
        opt = _secao_otimizacao()

    c1, c2 = st.columns([1.4, 1])
    rodar = c1.button("▶ CALCULAR MODELOS E OTIMIZAR DESPACHO", type="primary", width="stretch",
                      disabled=carga is None, key="ems_run")
    comparar = c2.button("▶ COMPARAR GA · GWO · NGO · SQP", width="stretch", disabled=carga is None,
                         key="ems_run_all")
    if rodar or comparar:
        try:
            with st.spinner("Calculando os modelos das fontes na plataforma…"):
                pasta = _montar_pacote(carga, spec, opt)
            _executar(pasta, [opt["algoritmo"]] if rodar else [2, 3, 1, 0], opt["validar"])
        except Exception as exc:
            st.error(f"Falha na execução: {exc}")
            return
        _ir(EMS_RESULTS if rodar else EMS_COMPARE)


# ============================================================== resultados
def _kpis(r: dict, val: dict | None) -> None:
    rel = r["rel"]
    kv = r["k_validos"]
    cols = st.columns(6)
    h2 = rel["consumo_fisico"].get("fc", {}).get("valor")
    if h2 is not None:
        delta = f"dinâmico: {val['h2_kg']:.2f} kg ({100 * (val['h2_kg'] - h2) / max(h2, 1e-9):+.1f} %)" if val else None
        cols[0].metric("H₂ consumido", f"{h2:.2f} kg", delta, delta_color="off")
    else:
        cols[0].metric("H₂ consumido", "—")
    cols[1].metric("Custo total", f"R$ {rel['custo_total_rs']:,.2f}")
    cols[2].metric("Energia não atendida", f"{rel['energia_nao_atendida_kWh']:.2f} kWh",
                   f"vertida {rel['energia_vertida_kWh']:.2f} kWh", delta_color="off")
    if "bateria" in r["nomes"]:
        j = r["nomes"].index("bateria")
        s0 = r["bateria"]["SOC_ini"]
        sf = rel["SOC_final"][j]
        cols[3].metric("SOC final bateria", f"{100 * sf:.1f} %", f"{100 * (sf - s0):+.1f} p.p.")
    else:
        cols[3].metric("SOC final bateria", "—")
    if "fc" in r["nomes"]:
        n = r["n_unid"][:kv, r["nomes"].index("fc")]
        cols[4].metric("Stacks ligados", f"{n.mean():.2f} médio", f"mín {n.min()} · máx {n.max()}", delta_color="off")
    else:
        cols[4].metric("Stacks ligados", "—")
    cols[5].metric("Tempo", f"{r['tempo_total_s']:.1f} s",
                   f"meta {r['t_meta_s']:.1f} s · SQP {r['t_ref_s']:.1f} s", delta_color="off")


def _tabela_fontes(r: dict) -> pd.DataFrame:
    rel = r["rel"]
    kv = r["k_validos"]
    Ts_h = r["Ts_s"] / 3600.0
    E = P.energias_barramento(r)
    total = sum(E.values()) or 1.0
    linhas = []
    for nome, oferta in (("pv", r["eta_pv"] * r["P_pv_kW"][:kv]), ("eolica", r["eta_eol"] * r["P_eol_kW"][:kv])):
        if nome in E:
            linhas.append({"Fonte": P.rotulo(nome) + " (não despachável)", "Energia [kWh]": E[nome],
                           "Participação [%]": 100 * E[nome] / total, "Custo [R$]": 0.0, "Partidas": 0,
                           "Pico [kW]": float(oferta.max()),
                           "Consumo físico": f"{oferta.sum() * Ts_h - E[nome]:.2f} kWh vertidos"})
    for j, nome in enumerate(r["nomes"]):
        linha = {"Fonte": P.rotulo(nome), "Energia [kWh]": E.get(nome, 0.0),
                 "Participação [%]": 100 * E.get(nome, 0.0) / total, "Custo [R$]": rel["custo_por_fonte_rs"][j],
                 "Partidas": int(rel["partidas"][j]), "Pico [kW]": float(np.max(r["P_kW"][:kv, j]))}
        if nome in rel["consumo_fisico"]:
            cf = rel["consumo_fisico"][nome]
            linha["Consumo físico"] = f"{cf['valor']:.3f} {cf['unidade']}"
        linhas.append(linha)
    return pd.DataFrame(linhas)


def _render_results() -> None:
    item = _resultado_atual()
    _header("EMS · Resultado da otimização", "SAÍDA DO OTIMIZADOR",
            "Consumo de H₂, participação por fonte, despacho no tempo, stacks ligados, metaheurística × refino e SOC.")
    if item is None:
        st.info("Nenhuma execução ainda.")
        if st.button("Ir para Configuração", type="primary"):
            _ir(EMS_CONFIG)
        return
    hist = st.session_state["ems_historico"]
    if len(hist) > 1:
        ids = [h["id"] for h in hist]
        sel = st.selectbox("Execução exibida", ids, index=ids.index(item["id"]), key="ems_sel_box",
                           format_func=lambda i: next(f"#{h['id']} · {h['resultado']['algoritmo']} · "
                                                      f"{h['resultado']['carga_descricao']} · {h['quando']}"
                                                      for h in hist if h["id"] == i))
        if sel != item["id"]:
            st.session_state["ems_sel"] = sel
            st.rerun()
    r, val = item["resultado"], item["validacao"]
    st.caption(f"#{item['id']} · {r['algoritmo']} · {r['carga_descricao']} · {r['k_validos']} passos de "
               f"{r['Ts_s']:.0f} s · horizonte N={r['N']} · S_base {r['S_base_kW']:.0f} kW"
               + (" · meta penalizada" if r["config"].get("meta_penalizada") else ""))
    _kpis(r, val)
    if r["avisos"] or r["config"].get("notas"):
        with st.expander(f"Avisos e notas ({len(r['avisos']) + len(r['config'].get('notas', []))})"):
            for a in r["avisos"]:
                st.warning(a)
            for n in r["config"].get("notas", []):
                st.caption(n)

    abas = st.tabs(["Despacho", "Stacks PEMFC", "Metaheurística × refino", "Bateria", "H₂"])
    with abas[0]:
        st.plotly_chart(P.fig_despacho(r), width="stretch", config=CHART_CONFIG)
        c1, c2 = st.columns([1, 1.2], gap="large")
        c1.plotly_chart(P.fig_participacao(r), width="stretch", config=CHART_CONFIG)
        c2.dataframe(_tabela_fontes(r), hide_index=True, width="stretch",
                     column_config={"Energia [kWh]": st.column_config.NumberColumn(format="%.2f"),
                                    "Participação [%]": st.column_config.NumberColumn(format="%.1f"),
                                    "Custo [R$]": st.column_config.NumberColumn(format="%.2f"),
                                    "Pico [kW]": st.column_config.NumberColumn(format="%.1f")})
    with abas[1]:
        fig = P.fig_stacks(r)
        if fig is None:
            st.info("A fonte H₂/PEMFC não participou desta execução.")
        else:
            st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
            j = r["nomes"].index("fc")
            n = r["n_unid"][: r["k_validos"], j]
            dist = pd.Series(n).value_counts().sort_index()
            st.dataframe(pd.DataFrame({"Stacks ligados": dist.index, "Minutos": dist.values,
                                       "% do tempo": 100 * dist.values / n.size}),
                         hide_index=True, width="stretch")
    with abas[2]:
        kv = r["k_validos"]
        dJ = r["J_meta"][:kv] - r["J_ref"][:kv]
        inviavel = r["viol_meta"][:kv] > 1e-6
        c = st.columns(4)
        c[0].metric("ΔJ mediano (meta − refino)", f"R$ {np.nanmedian(dJ):+.3f}")
        c[1].metric("Passos com meta inviável", f"{100 * inviavel.mean():.0f} %")
        c[2].metric("Violação mediana da meta", f"{np.nanmedian(r['viol_meta'][:kv]):.2f} kW")
        c[3].metric("Tempo meta / SQP", f"{r['t_meta_s']:.1f} s / {r['t_ref_s']:.1f} s")
        st.plotly_chart(P.fig_meta_refino(r), width="stretch", config=CHART_CONFIG)
        st.plotly_chart(P.fig_delta_potencia(r), width="stretch", config=CHART_CONFIG)
        if r["algoritmo"] == "SQP":
            st.caption("Sem metaheurística: o ‘antes do refino’ é o ponto central da caixa, como no despacho.m.")
        elif not r["config"].get("meta_penalizada"):
            st.caption("Custo da meta abaixo do refino com violação alta = a meta achou um ponto barato porque ignora "
                       "o balanço. Ligue ‘metaheurística com penalidade’ para compará-las em pé de igualdade.")
    with abas[3]:
        fig = P.fig_soc(r)
        if fig is None:
            st.info("A bateria não participou desta execução.")
        else:
            b = r["bateria"]
            j = r["nomes"].index("bateria")
            c = st.columns(4)
            c[0].metric("SOC inicial", f"{100 * b['SOC_ini']:.1f} %")
            c[1].metric("SOC final", f"{100 * r['rel']['SOC_final'][j]:.1f} %")
            c[2].metric("Capacidade", f"{b['E_kWh']:.1f} kWh")
            m = r["fontes_meta"].get("bateria", {})
            c[3].metric("Resistência interna", f"{m.get('Rint', float('nan')) * 1000:.1f} mΩ",
                        f"ajuste R² {m.get('R2', 0):.3f}", delta_color="off",
                        help="Estimada da série de tensão × corrente que o modelo de bateria da plataforma gerou "
                             "(V = Voc + deriva·t − Rint·I, mínimos quadrados). O R² mostra a qualidade do ajuste. "
                             "O EMS usa essa leitura para obter as eficiências de carga e descarga.")
            st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
    with abas[4]:
        fig = P.fig_h2(r, val)
        if fig is None:
            st.info("A fonte H₂/PEMFC não participou desta execução.")
        else:
            st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)
            c1, c2 = st.columns(2, gap="large")
            curva = P.fig_curva_h2(r)
            if curva is not None:
                c1.plotly_chart(curva, width="stretch", config=CHART_CONFIG)
            if not val:
                c2.markdown("**Validação no modelo dinâmico PEMFC**")
                c2.write("O EMS estima o H₂ por uma curva estática kg/kWh. A validação reenvia o despacho de cada "
                         "stack ligado ao modelo dinâmico da plataforma (partida, idle, rampas, saturação).")
                n_fc = int(r["n_unid_inst"][r["nomes"].index("fc")])
                if c2.button(f"▶ VALIDAR NO MODELO DINÂMICO (≈ {15 * n_fc * r['k_validos'] / 120:.0f}–"
                             f"{20 * n_fc * r['k_validos'] / 120:.0f} s)", type="primary", key=f"ems_val_{item['id']}"):
                    with st.spinner("Simulando cada stack no modelo dinâmico PEMFC…"):
                        item["validacao"] = validar_fc_dinamico(r, passo_s=PASSO_VALIDACAO_S)
                    st.rerun()
            if val:
                c2.markdown("**Validação no modelo dinâmico PEMFC**")
                c2.dataframe(pd.DataFrame(val["por_stack"]).rename(columns={
                    "stack": "Stack", "h2_kg": "H₂ [kg]", "E_entregue_kWh": "Entregue [kWh]",
                    "E_pedida_kWh": "Pedida [kWh]"}), hide_index=True, width="stretch")
                deficit = val["E_pedida_kWh"] - val["E_entregue_kWh"]
                c2.caption(f"Energia pedida pelo EMS e não entregue pelo modelo dinâmico: {deficit:.2f} kWh "
                           "(partidas e rampas que a curva estática não enxerga).")


# ============================================================== comparação
def _resumo(item: dict) -> dict:
    r, val = item["resultado"], item["validacao"]
    kv = r["k_validos"]
    rel = r["rel"]
    d = {"#": item["id"], "Algoritmo": r["algoritmo"], "Carga": r["carga_descricao"],
         "Meta penalizada": bool(r["config"].get("meta_penalizada")),
         "H₂ EMS [kg]": rel["consumo_fisico"].get("fc", {}).get("valor", np.nan),
         "H₂ dinâmico [kg]": val["h2_kg"] if val else np.nan,
         "Custo [R$]": rel["custo_total_rs"], "Não atendida [kWh]": rel["energia_nao_atendida_kWh"],
         "ΔJ mediano [R$]": float(np.nanmedian(r["J_meta"][:kv] - r["J_ref"][:kv])),
         "Tempo meta [s]": r["t_meta_s"], "Tempo SQP [s]": r["t_ref_s"]}
    if "bateria" in r["nomes"]:
        d["SOC final [%]"] = 100 * rel["SOC_final"][r["nomes"].index("bateria")]
    if "fc" in r["nomes"]:
        d["Stacks médio"] = float(r["n_unid"][:kv, r["nomes"].index("fc")].mean())
    E = P.energias_barramento(r)
    total = sum(E.values()) or 1.0
    for nome, e in E.items():
        d[f"% {P.rotulo(nome)}"] = 100 * e / total
    return d


def _render_compare() -> None:
    _header("EMS · Comparação de execuções", "METAHEURÍSTICAS E CENÁRIOS",
            f"Até {MAX_HISTORICO} execuções desta sessão. Use ‘COMPARAR GA · GWO · NGO · SQP’ na configuração para "
            "rodar os quatro sobre as mesmas entradas.")
    hist = st.session_state["ems_historico"]
    if not hist:
        st.info("Nenhuma execução ainda.")
        return
    tab = pd.DataFrame([_resumo(h) for h in hist])
    st.dataframe(tab, hide_index=True, width="stretch")
    ids = st.multiselect("Execuções nos gráficos", [h["id"] for h in hist], default=[h["id"] for h in hist[-4:]],
                         key="ems_cmp_ids")
    escolhidos = [h for h in hist if h["id"] in ids]
    if escolhidos:
        c1, c2 = st.columns(2, gap="large")
        c1.plotly_chart(P.fig_comparacao(escolhidos, "h2", "H₂ acumulado (EMS)", "kg"), width="stretch",
                        config=CHART_CONFIG)
        c2.plotly_chart(P.fig_comparacao(escolhidos, "custo", "Custo acumulado", "R$"), width="stretch",
                        config=CHART_CONFIG)
    if st.button("Limpar histórico", key="ems_clear"):
        st.session_state["ems_historico"] = []
        st.session_state["ems_sel"] = None
        st.rerun()


# ============================================================== exportação
def serie_temporal(r: dict) -> pd.DataFrame:
    kv = r["k_validos"]
    df = pd.DataFrame({
        "timestamp": r["t0"] + pd.to_timedelta(r["t_min"][:kv], unit="min"), "t_min": r["t_min"][:kv],
        "P_carga_kW": r["P_load_kW"][:kv], "P_solar_kW": r["P_pv_kW"][:kv], "P_eolica_kW": r["P_eol_kW"][:kv],
        "P_renovavel_vertida_kW": r["P_renov_vertida_kW"][:kv], "P_carga_liquida_kW": r["P_load_liq_kW"][:kv],
    })
    for j, nome in enumerate(r["nomes"]):
        df[f"P_{nome}_kW"] = r["P_kW"][:kv, j]
        df[f"P_{nome}_meta_kW"] = r["P_meta_kW"][:kv, j]
        if r["tipos"][j] == "armazenamento":
            df[f"SOC_{nome}"] = r["SOC"][:kv, j]
        else:
            df[f"n_{nome}"] = r["n_unid"][:kv, j]
    df["deficit_kW"] = r["deficit_kW"][:kv]
    df["excesso_kW"] = r["excesso_kW"][:kv]
    df["h2_kg"] = r["rel"]["h2_kg_passo"][:kv]
    df["custo_rs"] = r["custo_rs"][:kv]
    df["J_meta_rs"] = r["J_meta"][:kv]
    df["J_refino_rs"] = r["J_ref"][:kv]
    df["violacao_meta"] = r["viol_meta"][:kv]
    return df


def _render_export() -> None:
    _header("EMS · Exportação", "SÉRIE TEMPORAL DO DESPACHO",
            "Uma linha por minuto: carga, renováveis, potência de cada fonte, stacks ligados, SOC, H₂ e custo.")
    item = _resultado_atual()
    if item is None:
        st.info("Nenhuma execução ainda.")
        return
    r = item["resultado"]
    df = serie_temporal(r)
    st.dataframe(df.head(200), hide_index=True, width="stretch", height=360)
    st.download_button("⬇️ BAIXAR CSV", df.to_csv(index=False, sep=";", decimal=",", float_format="%.6f").encode("utf-8-sig"),
                       file_name=f"ems_{item['id']}_{r['algoritmo'].lower()}_serie.csv", mime="text/csv",
                       type="primary")
    st.caption("Separador ‘;’ e vírgula decimal: abre direto no Excel em português.")


# ================================================================ entrada
def render_ems_app() -> None:
    _init_state()
    st.markdown(EMS_CSS, unsafe_allow_html=True)
    page = _sidebar()
    if page == EMS_OVERVIEW:
        _render_overview()
    elif page == EMS_CONFIG:
        _render_config()
    elif page == EMS_RESULTS:
        _render_results()
    elif page == EMS_COMPARE:
        _render_compare()
    else:
        _render_export()


__all__ = ["render_ems_app", "serie_temporal", "EMS_OVERVIEW", "EMS_CONFIG", "EMS_RESULTS", "EMS_COMPARE",
           "EMS_EXPORT"]
