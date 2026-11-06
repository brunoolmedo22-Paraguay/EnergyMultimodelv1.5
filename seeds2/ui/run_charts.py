"""Gráficos Plotly das rodadas de cenário (Piso 2C) — lidos SOMENTE dos dados gravados da rodada."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import forecast_charts as FCH

CONFIG = FCH.CONFIG
SOURCE_LABELS = {"fc": "H₂ / PEMFC", "bateria": "Bateria (+ descarga / − carga)", "termica": "Térmica"}
COLORS = {"demanda": "#1F2933", "solar": "#E0A100", "eolica": "#2E86AB", "fc": "#2E8B57", "bateria": "#7B4FD6",
          "termica": "#C2364A", "deficit": "#D9480F", "vertido": "#8D99AE"}


def _x(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["timestamp_local"])


def _layout(fig: go.Figure, title: str, subtitle: str, height: int) -> go.Figure:
    fig.update_layout(
        title={"text": f"{title}<br><span style='font-size:12px;opacity:.75'>{subtitle}</span>", "x": 0, "xanchor": "left"},
        height=height, margin={"l": 10, "r": 10, "t": 74, "b": 44}, hovermode="x unified",
        legend={"orientation": "h", "yref": "container", "y": 0.0, "yanchor": "bottom", "xanchor": "left", "x": 0,
                "font": {"size": 11}}, uirevision=title)
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,.15)", tickformat="%H:%M\n%d/%m/%Y",
                     hoverformat="%Y-%m-%d %H:%M")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,.15)", zeroline=True, zerolinecolor="rgba(128,128,128,.4)")
    return fig


def power_figure(out: pd.DataFrame, *, subtitle: str) -> go.Figure:
    """Demanda e potência por fonte (kW) — um único eixo, mesma grandeza."""
    x = _x(out)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=out["P_carga_kW"], name="Demanda", line={"color": COLORS["demanda"], "width": 2.4},
                             hovertemplate="%{y:.2f} kW"))
    if (out["P_solar_kW"].abs() > 0).any():
        fig.add_trace(go.Scatter(x=x, y=out["P_solar_kW"], name="Solar FV (disponível)", line={"color": COLORS["solar"]},
                                 hovertemplate="%{y:.2f} kW"))
    if (out["P_eolica_kW"].abs() > 0).any():
        fig.add_trace(go.Scatter(x=x, y=out["P_eolica_kW"], name="Eólica (disponível)", line={"color": COLORS["eolica"]},
                                 hovertemplate="%{y:.2f} kW"))
    for col in out.columns:
        if col.startswith("P_") and col.endswith("_kW") and not col.endswith("_meta_kW"):
            nome = col[2:-3]
            if nome in SOURCE_LABELS:
                fig.add_trace(go.Scatter(x=x, y=out[col], name=SOURCE_LABELS[nome], line={"color": COLORS[nome]},
                                         hovertemplate="%{y:.2f} kW"))
    if (out["deficit_kW"] > 1e-6).any():
        fig.add_trace(go.Scatter(x=x, y=out["deficit_kW"], name="Não atendida (déficit)",
                                 line={"color": COLORS["deficit"], "dash": "dot"}, hovertemplate="%{y:.2f} kW"))
    vert = out["P_renovavel_vertida_kW"] + out["excesso_despachavel_kW"]
    if (vert > 1e-6).any():
        fig.add_trace(go.Scatter(x=x, y=vert, name="Excedente (vertido)", line={"color": COLORS["vertido"], "dash": "dash"},
                                 hovertemplate="%{y:.2f} kW"))
    fig.update_yaxes(title_text="Potência (kW)")
    fig.update_xaxes(title_text="Data e hora (fuso da missão)")
    return _layout(fig, "Demanda e potência por fonte", subtitle, 440)


def soc_figure(out: pd.DataFrame, *, soc_min: float | None, soc_max: float | None, subtitle: str) -> go.Figure | None:
    cols = [c for c in out.columns if c.startswith("SOC_")]
    if not cols:
        return None
    x = _x(out)
    fig = go.Figure()
    for c in cols:
        fig.add_trace(go.Scatter(x=x, y=100.0 * out[c], name="SOC " + c[4:], line={"color": COLORS["bateria"]},
                                 hovertemplate="%{y:.2f} %"))
    for v, name in ((soc_min, "SOC mín. efetivo"), (soc_max, "SOC máx. efetivo")):
        if v is not None:
            fig.add_hline(y=v, line={"dash": "dot", "color": "rgba(128,128,128,.7)"}, annotation_text=name,
                          annotation_position="top left")
    fig.update_yaxes(title_text="Estado de carga (%)", range=[0, 100])
    fig.update_xaxes(title_text="Data e hora (fuso da missão)")
    return _layout(fig, "Estado de carga da bateria", subtitle, 320)


def h2_figure(out: pd.DataFrame, *, subtitle: str) -> go.Figure | None:
    if "h2_kg" not in out or not (out["h2_kg"] > 0).any():
        return None
    x = _x(out)
    fig = make_subplots(specs=[[{"secondary_y": False}]])
    fig.add_trace(go.Scatter(x=x, y=np.cumsum(out["h2_kg"].to_numpy(float)), name="H₂ acumulado (estimativa do EMS)",
                             line={"color": COLORS["fc"]}, hovertemplate="%{y:.4f} kg"))
    if "h2_kg_validacao_dinamica" in out:
        fig.add_trace(go.Scatter(x=x, y=np.cumsum(out["h2_kg_validacao_dinamica"].to_numpy(float)),
                                 name="H₂ acumulado (validação dinâmica PEMFC)", line={"color": COLORS["fc"], "dash": "dash"},
                                 hovertemplate="%{y:.4f} kg"))
    fig.update_yaxes(title_text="H₂ (kg)", rangemode="tozero")
    fig.update_xaxes(title_text="Data e hora (fuso da missão)")
    return _layout(fig, "Consumo de hidrogênio", subtitle, 300)


def inputs_figure(inp: pd.DataFrame, *, subtitle: str) -> go.Figure:
    """Entradas da missão na grade do motor (demanda + clima usado), painéis por grandeza."""
    from seeds2.operation import forecasts as F

    keys = ["demand_kW"] + [k for k in F.SLOT_VARIABLES["climate"] if k in inp.columns]
    fig = make_subplots(rows=len(keys), cols=1, shared_xaxes=True, vertical_spacing=0.07,
                        subplot_titles=[f"{F.VARIABLES[k].label} ({F.VARIABLES[k].unit})" for k in keys])
    x = pd.to_datetime(inp["timestamp_local"])
    for r, k in enumerate(keys, start=1):
        fig.add_trace(go.Scatter(x=x, y=inp[k], name=F.VARIABLES[k].short, showlegend=False,
                                 hovertemplate=f"%{{y:.3f}} {F.VARIABLES[k].unit}"), row=r, col=1)
        fig.update_yaxes(title_text=F.VARIABLES[k].unit, row=r, col=1)
    fig.update_xaxes(title_text="Data e hora (fuso da missão)", row=len(keys), col=1)
    return _layout(fig, "Entradas da missão na grade de 1 min do motor", subtitle, 120 + 170 * len(keys))


__all__ = ["CONFIG", "h2_figure", "inputs_figure", "power_figure", "soc_figure"]
