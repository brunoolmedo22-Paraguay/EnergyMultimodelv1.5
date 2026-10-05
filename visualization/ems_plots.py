"""Figuras Plotly do módulo EMS (despacho ótimo)."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

CORES = {
    "fc": "#16869B", "bateria": "#E0A100", "termica": "#C8553D", "eolica": "#4C8BF5",
    "pv": "#F2C14E", "deficit": "#D62828", "excesso": "#8A969C", "carga": "#14232D",
}
ROTULOS = {
    "fc": "H₂ / PEMFC", "bateria": "Bateria", "termica": "Térmica", "eolica": "Eólica",
    "pv": "Solar", "deficit": "Não atendida", "excesso": "Vertida",
}
# Título no topo e legenda logo acima da área do gráfico, com folga entre os dois
# (margem superior de 48 px fazia a legenda horizontal subir por cima do título).
LAYOUT = dict(margin={"l": 20, "r": 20, "t": 110, "b": 20}, hovermode="x unified",
              title_y=0.97, title_yanchor="top", title_font_size=17,
              legend={"orientation": "h", "yanchor": "bottom", "y": 1.03, "x": 0, "font": {"size": 12}})


def rotulo(nome: str) -> str:
    return ROTULOS.get(nome, nome)


def _t(r: dict) -> np.ndarray:
    return r["t_min"][: r["k_validos"]]


def contribuicoes_barramento(r: dict) -> dict[str, np.ndarray]:
    """Potência que cada fonte coloca no barramento (mesmas eficiências do balanço).

    Solar e eólica (não despacháveis) entram com a parte que de fato abateu a
    carga, min(renovável, carga), repartida na proporção do que cada uma
    ofereceu. Bateria: +eta·P descarregando, P/eta carregando (negativo)."""
    kv = r["k_validos"]
    out: dict[str, np.ndarray] = {}
    usado = r["P_load_kW"][:kv] - r["P_load_liq_kW"][:kv]
    oferta_pv = r["eta_pv"] * r["P_pv_kW"][:kv]
    oferta_eol = r["eta_eol"] * r["P_eol_kW"][:kv]
    total = oferta_pv + oferta_eol
    frac_pv = np.divide(oferta_pv, total, out=np.zeros_like(total), where=total > 1e-12)
    if np.any(oferta_pv > 1e-9):
        out["pv"] = usado * frac_pv
    if np.any(oferta_eol > 1e-9):
        out["eolica"] = usado * (1 - frac_pv)
    for j, nome in enumerate(r["nomes"]):
        P = r["P_kW"][:kv, j]
        eta = r["eta"][j]
        out[nome] = np.where(P >= 0, eta * P, P / eta) if r["tipos"][j] == "armazenamento" else eta * P
    out["deficit"] = r["deficit_kW"][:kv]
    out["excesso"] = -r["excesso_kW"][:kv]
    return out


def energias_barramento(r: dict) -> dict[str, float]:
    """kWh entregues ao barramento por fonte (parte positiva), renováveis incluídas."""
    Ts_h = r["Ts_s"] / 3600.0
    return {n: float(np.maximum(y, 0).sum() * Ts_h) for n, y in contribuicoes_barramento(r).items()
            if n not in ("deficit", "excesso")}


def fig_despacho(r: dict) -> go.Figure:
    t = _t(r)
    fig = go.Figure()
    contrib = contribuicoes_barramento(r)
    for nome, y in contrib.items():
        if nome in ("deficit", "excesso") and np.max(np.abs(y)) < 1e-6:
            continue
        pos, neg = np.maximum(y, 0), np.minimum(y, 0)
        cor = CORES.get(nome, "#777")
        if np.any(pos > 1e-9):
            fig.add_trace(go.Scatter(x=t, y=pos, name=rotulo(nome), stackgroup="pos", mode="lines",
                                     line={"width": 0.5, "color": cor}, fillcolor=cor))
        if np.any(neg < -1e-9):
            nome_neg = "Bateria (carga)" if nome == "bateria" else rotulo(nome)
            fig.add_trace(go.Scatter(x=t, y=neg, name=nome_neg, stackgroup="neg", mode="lines",
                                     line={"width": 0.5, "color": cor}, fillcolor=cor, opacity=0.6))
    fig.add_trace(go.Scatter(x=t, y=r["P_load_kW"][: r["k_validos"]], name="Carga", mode="lines",
                             line={"color": CORES["carga"], "width": 2.2}))
    renov = r["P_renov_kW"][: r["k_validos"]]
    if np.any(renov > 1e-9):
        fig.add_trace(go.Scatter(x=t, y=renov, name="Renovável disponível", mode="lines",
                                 line={"color": "#2A9D8F", "width": 1.6, "dash": "dot"}))
    fig.update_layout(title="Despacho de potência no barramento", xaxis_title="Tempo [min]",
                      yaxis_title="kW", **LAYOUT)
    return fig


def fig_participacao(r: dict) -> go.Figure:
    """Rosca com a energia que cada fonte entregou para atender a carga (renováveis incluídas)."""
    E = {n: e for n, e in energias_barramento(r).items() if e > 1e-6}
    nao_atendida = float(r["deficit_kW"][: r["k_validos"]].sum() * r["Ts_s"] / 3600.0)
    if nao_atendida > 1e-3:
        E["deficit"] = nao_atendida
    total = sum(E.values())
    nomes = list(E)
    fig = go.Figure(go.Pie(
        labels=[rotulo(n) for n in nomes], values=[E[n] for n in nomes], hole=0.58, sort=False,
        direction="clockwise", marker={"colors": [CORES.get(n, "#777") for n in nomes],
                                       "line": {"color": "white", "width": 2}},
        textinfo="percent", textposition="outside", automargin=True, texttemplate="%{label}<br><b>%{percent:.1%}</b>",
        hovertemplate="%{label}<br>%{value:.1f} kWh · %{percent:.1%}<extra></extra>",
    ))
    fig.update_layout(
        title="Participação de cada fonte no atendimento da carga", title_y=0.97, title_yanchor="top",
        title_font_size=17, margin={"l": 30, "r": 30, "t": 80, "b": 30}, height=420, showlegend=False,
        annotations=[{"text": f"<b>{total:.0f} kWh</b><br><span style='font-size:12px'>energia total</span>",
                      "x": 0.5, "y": 0.5, "showarrow": False, "font": {"size": 20}}],
    )
    return fig


def fig_stacks(r: dict) -> go.Figure | None:
    if "fc" not in r["nomes"]:
        return None
    j = r["nomes"].index("fc")
    t = _t(r)
    kv = r["k_validos"]
    n = r["n_unid"][:kv, j]
    P = r["P_kW"][:kv, j]
    por_stack = np.where(n > 0, P / np.maximum(n, 1), 0.0)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=t, y=n, name="Stacks ligados", mode="lines", line_shape="hv",
                             line={"color": CORES["fc"], "width": 2.5}), secondary_y=False)
    fig.add_trace(go.Scatter(x=t, y=por_stack, name="Potência por stack", mode="lines",
                             line={"color": "#8FB8C2", "width": 1.3, "dash": "dot"}), secondary_y=True)
    N_fc = int(r["n_unid_inst"][j])
    fig.update_yaxes(title_text="Stacks ligados", range=[-0.2, N_fc + 0.4], dtick=1, secondary_y=False)
    fig.update_yaxes(title_text="kW por stack", secondary_y=True, showgrid=False)
    fig.update_layout(title="Quantidade de stacks PEMFC ligados", xaxis_title="Tempo [min]", **LAYOUT)
    return fig


def fig_meta_refino(r: dict) -> go.Figure:
    t = _t(r)
    kv = r["k_validos"]
    Jm, Jr = r["J_meta"][:kv], r["J_ref"][:kv]
    vm = r["viol_meta"][:kv]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("Custo do passo: metaheurística × refino SQP",
                                        "Violação de restrições da solução da metaheurística"))
    fig.add_trace(go.Scatter(x=t, y=Jm, name=f"{r['algoritmo']} (antes do refino)", mode="lines",
                             line={"color": "#9B5DE5"}), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=Jr, name="Após refino SQP", mode="lines",
                             line={"color": "#14232D", "width": 2}), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=np.maximum(vm, 1e-9), name="Violação máx. (meta)", mode="lines",
                             line={"color": CORES["deficit"]}), row=2, col=1)
    fig.update_yaxes(title_text="R$ no horizonte", row=1, col=1)
    fig.update_yaxes(title_text="kW (balanço)", type="log", row=2, col=1)
    fig.update_xaxes(title_text="Tempo [min]", row=2, col=1)
    fig.update_layout(height=620, **{**LAYOUT, "margin": {**LAYOUT["margin"], "t": 130},
                                     "legend": {**LAYOUT["legend"], "y": 1.09}})
    return fig


def fig_delta_potencia(r: dict) -> go.Figure:
    t = _t(r)
    kv = r["k_validos"]
    fig = go.Figure()
    for j, nome in enumerate(r["nomes"]):
        d = r["P_meta_kW"][:kv, j] - r["P_kW"][:kv, j]
        fig.add_trace(go.Scatter(x=t, y=d, name=rotulo(nome), mode="lines",
                                 line={"color": CORES.get(nome, "#777")}))
    fig.add_hline(y=0, line_color="#999", line_width=1)
    fig.update_layout(title="Diferença de potência no 1º passo: metaheurística − refino",
                      xaxis_title="Tempo [min]", yaxis_title="kW", **LAYOUT)
    return fig


def fig_soc(r: dict) -> go.Figure | None:
    b = r.get("bateria")
    if b is None or "bateria" not in r["nomes"]:
        return None
    j = r["nomes"].index("bateria")
    kv = r["k_validos"]
    t = np.concatenate([[0.0], r["t_min"][:kv] + r["Ts_s"] / 60])
    y = 100 * np.concatenate([[b["SOC_ini"]], r["SOC"][:kv, j]])
    tol = b["soc_alvo_tol"]
    fig = go.Figure()
    fig.add_hrect(y0=100 * (b["SOC_ini"] - tol), y1=100 * (b["SOC_ini"] + tol), fillcolor="#E0A100",
                  opacity=0.10, line_width=0, annotation_text="banda do SOC-alvo", annotation_position="top left")
    for lim, txt in ((b["SOC_min"], "SOC mín."), (b["SOC_max"], "SOC máx.")):
        fig.add_hline(y=100 * lim, line_dash="dash", line_color="#B0452F", annotation_text=txt)
    fig.add_trace(go.Scatter(x=t, y=y, name="SOC", mode="lines", line={"color": CORES["bateria"], "width": 2.5}))
    fig.update_layout(title="Estado de carga da bateria", xaxis_title="Tempo [min]", yaxis_title="SOC [%]",
                      **LAYOUT)
    return fig


def fig_h2(r: dict, validacao: dict | None) -> go.Figure | None:
    if "fc" not in r["nomes"]:
        return None
    kv = r["k_validos"]
    t = r["t_min"][:kv] + r["Ts_s"] / 60
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=np.cumsum(r["rel"]["h2_kg_passo"][:kv]), name="EMS (curva estática kg/kWh)",
                             mode="lines", line={"color": CORES["fc"], "width": 2.5}))
    if validacao is not None:
        fig.add_trace(go.Scatter(x=t, y=np.cumsum(validacao["h2_kg_passo"]), name="Modelo dinâmico PEMFC",
                                 mode="lines", line={"color": "#14232D", "dash": "dash", "width": 2}))
    fig.update_layout(title="Consumo acumulado de H₂", xaxis_title="Tempo [min]", yaxis_title="kg", **LAYOUT)
    return fig


def fig_curva_h2(r: dict) -> go.Figure | None:
    meta = r.get("fontes_meta", {}).get("fc")
    if not meta or "curva_x" not in meta:
        return None
    x, y = np.asarray(meta["curva_x"]), np.asarray(meta["curva_y"])
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines+markers", line={"color": CORES["fc"]}, name="kg/kWh"))
    fig.update_layout(title="Curva kg H₂/kWh derivada do modelo PEMFC (por stack)",
                      xaxis_title="Potência por stack [kW]", yaxis_title="kg H₂ / kWh", margin=LAYOUT["margin"])
    return fig


def fig_carga(t: np.ndarray, p: np.ndarray, titulo: str) -> go.Figure:
    fig = go.Figure(go.Scatter(x=t, y=p, mode="lines", line={"color": CORES["carga"]}, fill="tozeroy",
                               fillcolor="rgba(20,35,45,0.08)"))
    fig.update_layout(title=titulo, xaxis_title="Tempo [min]", yaxis_title="kW", height=260,
                      margin={"l": 20, "r": 20, "t": 40, "b": 20})
    return fig


def fig_comparacao(historico: list[dict], campo: str, titulo: str, eixo: str) -> go.Figure:
    fig = go.Figure()
    for i, item in enumerate(historico):
        r = item["resultado"]
        kv = r["k_validos"]
        t = r["t_min"][:kv] + r["Ts_s"] / 60
        y = np.cumsum(r["rel"]["h2_kg_passo"][:kv]) if campo == "h2" else np.cumsum(r["custo_rs"][:kv])
        fig.add_trace(go.Scatter(x=t, y=y, name=f"#{item['id']} · {r['algoritmo']}", mode="lines"))
    fig.update_layout(title=titulo, xaxis_title="Tempo [min]", yaxis_title=eixo, **LAYOUT)
    return fig
