"""Visualizações do módulo térmico V1.1."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config.thermal_database import LOCAL_GENERATOR, THERMAL_PLANT

PLOT_LAYOUT = dict(
    template="plotly_white",
    margin=dict(l=52, r=28, t=52, b=44),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)


def plot_thermal_power(result: pd.DataFrame, dynamic: str, pmax_mw: float, pmin_mw: float = 0.0) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result["timestamp"], y=result["power_requested_mw"], mode="lines", name="Potência solicitada"))
    if dynamic == THERMAL_PLANT:
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["inflexibility_mw"], mode="lines", name="Inflexibilidade", line=dict(dash="dash")))
    fig.add_trace(go.Scatter(x=result["timestamp"], y=result["power_delivered_mw"], mode="lines", name="Potência considerada/entregue", line=dict(width=3)))
    fig.add_hline(y=pmax_mw, line_dash="dot", annotation_text="Pmax", annotation_position="top left")
    if pmin_mw > 0 and dynamic == THERMAL_PLANT:
        fig.add_hline(y=pmin_mw, line_dash="dot", annotation_text="Pmin técnico", annotation_position="bottom left")

    violations = (
        result["violation_below_inflexibility"]
        | result["violation_above_pmax"]
        | result["violation_below_pmin"]
        | result["violation_ramp_up"]
        | result["violation_ramp_down"]
    )
    if violations.any():
        v = result.loc[violations]
        fig.add_trace(go.Scatter(
            x=v["timestamp"], y=v["power_requested_mw"], mode="markers", name="Violação",
            marker=dict(symbol="x", size=10),
            hovertemplate="%{x}<br>Solicitado=%{y:.3f} MW<extra>Violação</extra>",
        ))
    fig.update_layout(**PLOT_LAYOUT, title="Despacho térmico", xaxis_title="Tempo", yaxis_title="Potência (MW)")
    return fig


def plot_interval_cost(result: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=result["timestamp"], y=result["variable_cost_rs"], name="Custo variável"))
    if result["startup_cost_rs"].sum() > 0:
        fig.add_trace(go.Bar(x=result["timestamp"], y=result["startup_cost_rs"], name="Partida"))
    fig.update_layout(**PLOT_LAYOUT, title="Custo por intervalo", xaxis_title="Tempo", yaxis_title="Custo (R$)", barmode="stack")
    return fig


def plot_cumulative_cost(result: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(x=result["timestamp"], y=result["cumulative_cost_rs"], mode="lines", name="Custo acumulado", fill="tozeroy"))
    fig.update_layout(**PLOT_LAYOUT, title="Custo acumulado", xaxis_title="Tempo", yaxis_title="Custo acumulado (R$)")
    return fig


def plot_energy_balance(result: pd.DataFrame, dynamic: str) -> go.Figure:
    if dynamic == THERMAL_PLANT:
        labels = ["Inflexível", "Flexível", "Não atendida"]
        values = [
            result["energy_inflexible_mwh"].sum(),
            result["energy_flexible_mwh"].sum(),
            result["energy_unmet_mwh"].sum(),
        ]
    else:
        labels = ["Atendida pelo gerador", "Não atendida"]
        values = [result["energy_delivered_mwh"].sum(), result["energy_unmet_mwh"].sum()]
    fig = go.Figure(go.Bar(x=labels, y=values))
    fig.update_layout(**PLOT_LAYOUT, title="Balanço de energia no período", xaxis_title="", yaxis_title="Energia (MWh)", showlegend=False)
    return fig


def plot_power_and_cost(result: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=result["timestamp"], y=result["power_delivered_mw"], mode="lines", name="Potência entregue"), secondary_y=False)
    fig.add_trace(go.Scatter(x=result["timestamp"], y=result["total_cost_rs"], mode="lines", name="Custo/intervalo", line=dict(dash="dot")), secondary_y=True)
    fig.update_layout(**PLOT_LAYOUT, title="Potência × custo")
    fig.update_yaxes(title_text="Potência (MW)", secondary_y=False)
    fig.update_yaxes(title_text="Custo (R$ / intervalo)", secondary_y=True)
    return fig
