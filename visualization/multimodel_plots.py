"""Gráficos compactos e consistentes da plataforma multimodelo."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from models.single_diode import iv_curve
from simulation.mpp import find_mpp
from simulation.multimodel import (
    MODEL_COLORS,
    MODEL_LABELS,
    MODEL_ORDER,
    MODEL_SDM,
    MODEL_SHORT_LABELS,
)
from simulation.solver import translate_params


GRID = "#E5EAF0"
TEXT = "#263746"
MUTED = "#718096"


def _rgba(hex_color: str, alpha: float) -> str:
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _finish(
    fig: go.Figure,
    *,
    ytitle: str = "",
    ytitle2: str | None = None,
    height: int = 236,
    showlegend: bool = True,
) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=50, r=20 if ytitle2 is None else 50, t=10, b=36),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Arial, sans-serif", color=TEXT, size=11),
        hovermode="x unified",
        showlegend=showlegend,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
    )
    fig.update_xaxes(
        title="Horário",
        gridcolor=GRID,
        linecolor=GRID,
        tickformat="%H:%M",
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikedash="dot",
        spikecolor="#9AA9B7",
    )
    fig.update_yaxes(title=ytitle, gridcolor=GRID, linecolor=GRID, zerolinecolor=GRID)
    if ytitle2 is not None:
        fig.update_yaxes(title=ytitle2, secondary_y=True, showgrid=False, linecolor=GRID)
    return fig


def plot_input_profile(profile: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=profile.index,
            y=profile["G"],
            name="GHI",
            mode="lines",
            line=dict(color="#2F80ED", width=2.2),
            fill="tozeroy",
            fillcolor=_rgba("#2F80ED", 0.10),
            hovertemplate="%{y:.1f} W/m²<extra>GHI</extra>",
        ),
        secondary_y=False,
    )
    if "Tamb" in profile and profile["Tamb"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=profile.index,
                y=profile["Tamb"],
                name="Temperatura ambiente",
                mode="lines",
                line=dict(color="#E67E22", width=2.0),
                hovertemplate="%{y:.1f} °C<extra>Tamb</extra>",
            ),
            secondary_y=True,
        )
    return _finish(
        fig,
        ytitle="Irradiância [W/m²]",
        ytitle2="Temperatura [°C]",
        height=270,
    )


def plot_model_power(
    results: pd.DataFrame,
    model_id: str,
    *,
    height: int = 236,
) -> go.Figure:
    color = MODEL_COLORS[model_id]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=results.index,
            y=results["P_array"],
            name=MODEL_LABELS[model_id],
            mode="lines",
            line=dict(color=color, width=2.5),
            fill="tozeroy",
            fillcolor=_rgba(color, 0.11),
            hovertemplate="%{y:.2f} W<extra>Potência</extra>",
        )
    )
    return _finish(
        fig,
        ytitle="Potência do arranjo [W]",
        height=height,
        showlegend=False,
    )


def plot_cumulative_energy(results: pd.DataFrame, model_id: str) -> go.Figure:
    color = MODEL_COLORS[model_id]
    energy_kwh = results["energy_step_Wh"].cumsum() / 1000.0
    fig = go.Figure(
        go.Scatter(
            x=results.index,
            y=energy_kwh,
            mode="lines",
            line=dict(color=color, width=2.5),
            fill="tozeroy",
            fillcolor=_rgba(color, 0.09),
            hovertemplate="%{y:.4f} kWh<extra>Energia acumulada</extra>",
        )
    )
    return _finish(fig, ytitle="Energia acumulada [kWh]", showlegend=False)


def plot_temperatures(results: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if "Tamb" in results and results["Tamb"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=results.index,
                y=results["Tamb"],
                name="Ambiente",
                line=dict(color="#4C9BE8", width=2),
                hovertemplate="%{y:.2f} °C<extra>Ambiente</extra>",
            )
        )
    if "Tc" in results and results["Tc"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=results.index,
                y=results["Tc"],
                name="Célula",
                line=dict(color="#E05C5C", width=2.2),
                hovertemplate="%{y:.2f} °C<extra>Célula</extra>",
            )
        )
    return _finish(fig, ytitle="Temperatura [°C]")


def plot_efficiency(results: pd.DataFrame, model_id: str) -> go.Figure:
    color = MODEL_COLORS[model_id]
    fig = go.Figure(
        go.Scatter(
            x=results.index,
            y=results["eta"] * 100.0,
            mode="lines",
            line=dict(color=color, width=2.3),
            fill="tozeroy",
            fillcolor=_rgba(color, 0.08),
            hovertemplate="%{y:.3f} %<extra>Eficiência</extra>",
        )
    )
    return _finish(fig, ytitle="Eficiência [%]", showlegend=False)


def plot_comparison_power(
    results_by_model: dict[str, pd.DataFrame],
    *,
    height: int = 236,
) -> go.Figure:
    fig = go.Figure()
    for model_id in MODEL_ORDER:
        if model_id not in results_by_model:
            continue
        result = results_by_model[model_id]
        fig.add_trace(
            go.Scatter(
                x=result.index,
                y=result["P_array"],
                name=MODEL_LABELS[model_id],
                mode="lines",
                line=dict(color=MODEL_COLORS[model_id], width=2.4),
                hovertemplate="%{y:.2f} W<extra>" + MODEL_LABELS[model_id] + "</extra>",
            )
        )
    return _finish(fig, ytitle="Potência do arranjo [W]", height=height)


def plot_comparison_energy(results_by_model: dict[str, pd.DataFrame]) -> go.Figure:
    fig = go.Figure()
    for model_id in MODEL_ORDER:
        if model_id not in results_by_model:
            continue
        result = results_by_model[model_id]
        energy = result["energy_step_Wh"].cumsum() / 1000.0
        fig.add_trace(
            go.Scatter(
                x=result.index,
                y=energy,
                name=MODEL_LABELS[model_id],
                mode="lines",
                line=dict(color=MODEL_COLORS[model_id], width=2.4),
                hovertemplate="%{y:.4f} kWh<extra>" + MODEL_LABELS[model_id] + "</extra>",
            )
        )
    return _finish(fig, ytitle="Energia acumulada [kWh]", height=236)


def plot_comparison_efficiency(results_by_model: dict[str, pd.DataFrame]) -> go.Figure:
    fig = go.Figure()
    for model_id in MODEL_ORDER:
        if model_id not in results_by_model:
            continue
        result = results_by_model[model_id]
        fig.add_trace(
            go.Scatter(
                x=result.index,
                y=result["eta"] * 100.0,
                name=MODEL_LABELS[model_id],
                mode="lines",
                line=dict(color=MODEL_COLORS[model_id], width=2.2),
                hovertemplate="%{y:.3f} %<extra>" + MODEL_LABELS[model_id] + "</extra>",
            )
        )
    return _finish(fig, ytitle="Eficiência [%]", height=236)


def plot_difference_to_reference(
    results_by_model: dict[str, pd.DataFrame],
    reference_model: str,
) -> go.Figure | None:
    if reference_model not in results_by_model:
        return None
    ref = results_by_model[reference_model]["P_array"].astype(float)
    reference_label = MODEL_SHORT_LABELS[reference_model]
    fig = go.Figure()
    has_line = False
    for model_id in MODEL_ORDER:
        if model_id == reference_model or model_id not in results_by_model:
            continue
        power = results_by_model[model_id]["P_array"].astype(float).reindex(ref.index)
        ref_values = ref.to_numpy()
        power_values = power.to_numpy()
        difference = np.full(ref_values.shape, np.nan, dtype=float)
        valid = ref_values > 1.0
        difference[valid] = (
            (power_values[valid] - ref_values[valid]) / ref_values[valid] * 100.0
        )
        fig.add_trace(
            go.Scatter(
                x=ref.index,
                y=difference,
                name=MODEL_LABELS[model_id],
                mode="lines",
                line=dict(color=MODEL_COLORS[model_id], width=2.1),
                hovertemplate=(
                    "%{y:+.2f} %<extra>Diferença vs " + reference_label + "</extra>"
                ),
            )
        )
        has_line = True
    if not has_line:
        return None
    fig.add_hline(y=0, line_color="#8B98A5", line_dash="dash", line_width=1)
    return _finish(
        fig,
        ytitle=f"Diferença de potência vs {reference_label} [%]",
        height=236,
    )


def plot_difference_to_sdm(results_by_model: dict[str, pd.DataFrame]) -> go.Figure | None:
    """Compatibilidade com a comparação originalmente fixa no SDM."""
    return plot_difference_to_reference(results_by_model, MODEL_SDM)


def plot_iv_pv_at_peak(module, results: pd.DataFrame) -> go.Figure:
    """Curvas I-V e P-V do SDM no instante de maior potência da janela."""
    peak_ts = results["P_array"].idxmax()
    row = results.loc[peak_ts]
    p_operating = translate_params(module.sdm, module.stc, float(row["G_eff"]), float(row["Tc"]))
    voltage, current, power = iv_curve(p_operating, n_points=260)
    mpp = find_mpp(p_operating)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=voltage,
            y=current,
            name="Corrente I-V",
            line=dict(color="#2F80ED", width=2.4),
            hovertemplate="V=%{x:.2f} V<br>I=%{y:.3f} A<extra>I-V</extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=voltage,
            y=power,
            name="Potência P-V",
            line=dict(color="#F2994A", width=2.4),
            hovertemplate="V=%{x:.2f} V<br>P=%{y:.2f} W<extra>P-V</extra>",
        ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(
            x=[mpp["Vmp"]],
            y=[mpp["Pmp"]],
            name="MPP",
            mode="markers",
            marker=dict(color="#D64545", size=10, symbol="diamond"),
            hovertemplate="Vmp=%{x:.2f} V<br>Pmp=%{y:.2f} W<extra>MPP</extra>",
        ),
        secondary_y=True,
    )
    fig.update_layout(
        template="plotly_white",
        height=280,
        margin=dict(l=52, r=52, t=16, b=42),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Arial, sans-serif", color=TEXT, size=11),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
    )
    fig.update_xaxes(title="Tensão do módulo [V]", gridcolor=GRID)
    fig.update_yaxes(title="Corrente [A]", gridcolor=GRID, secondary_y=False)
    fig.update_yaxes(title="Potência [W]", showgrid=False, secondary_y=True)
    return fig
