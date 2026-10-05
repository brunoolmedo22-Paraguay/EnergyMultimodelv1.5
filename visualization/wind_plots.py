"""Gráficos do módulo eólico V1."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config.wind_turbine_database import get_turbine

PLOT_LAYOUT = dict(
    template="plotly_white",
    margin=dict(l=48, r=28, t=48, b=42),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)


def plot_wind_profile(result: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result["timestamp"], y=result["wind_speed_mps"], mode="lines", name="Vento medido"))
    if "equivalent_wind_speed_mps" in result and not np.allclose(result["wind_speed_mps"], result["equivalent_wind_speed_mps"]):
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["equivalent_wind_speed_mps"], mode="lines", name="Vento equivalente", line=dict(dash="dot")))
    fig.update_layout(**PLOT_LAYOUT, title="Perfil de velocidade do vento", xaxis_title="Tempo", yaxis_title="Velocidade (m/s)")
    return fig


def plot_power_profile(result: pd.DataFrame, show_net: bool) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result["timestamp"], y=result["power_gross_kw"] / 1000.0, mode="lines", name="Potência do aerogerador"))
    if show_net:
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["power_net_kw"] / 1000.0, mode="lines", name="Após -3%", line=dict(dash="dot")))
    fig.update_layout(**PLOT_LAYOUT, title="Potência elétrica no período", xaxis_title="Tempo", yaxis_title="Potência (MW)")
    return fig


def plot_environment(result: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if result["temperature_c"].notna().any():
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["temperature_c"], name="Temperatura (°C)", mode="lines"), secondary_y=False)
    if result["air_density_kg_m3"].notna().any():
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["air_density_kg_m3"], name="Densidade (kg/m³)", mode="lines"), secondary_y=True)
    fig.update_layout(**PLOT_LAYOUT, title="Condições atmosféricas")
    fig.update_yaxes(title_text="Temperatura (°C)", secondary_y=False)
    fig.update_yaxes(title_text="Densidade (kg/m³)", secondary_y=True)
    return fig


def plot_power_curve_with_operation(result: pd.DataFrame, turbine_key: str) -> go.Figure:
    entry = get_turbine(turbine_key)
    curve = entry["curve"]["points"]
    x = [p[0] for p in curve]
    y = [p[1] for p in curve]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=np.asarray(y) / 1000.0, mode="lines+markers", name="Curva parametrizada"))

    # Subamostra visual para arquivos longos.
    stride = max(1, len(result) // 350)
    sample = result.iloc[::stride]
    fig.add_trace(go.Scatter(
        x=sample["equivalent_wind_speed_mps"],
        y=sample["power_unit_kw"] / 1000.0,
        mode="markers",
        name="Pontos operativos",
        marker=dict(size=5, opacity=0.42),
        hovertemplate="v=%{x:.2f} m/s<br>P=%{y:.3f} MW<extra></extra>",
    ))
    spec = entry["spec"]
    for value, label in ((spec.get("cut_in_mps"), "cut-in"), (spec.get("rated_wind_speed_mps"), "nominal"), (spec.get("cut_out_mps"), "cut-out")):
        if value is not None:
            fig.add_vline(x=float(value), line_dash="dash", opacity=0.45, annotation_text=label, annotation_position="top")
    fig.update_layout(**PLOT_LAYOUT, title=f"Curva de potência · {turbine_key}", xaxis_title="Velocidade do vento (m/s)", yaxis_title="Potência unitária (MW)")
    return fig


def plot_catalog_curve(turbine_key: str) -> go.Figure:
    entry = get_turbine(turbine_key)
    curve = entry["curve"]["points"]
    fig = go.Figure(go.Scatter(
        x=[p[0] for p in curve],
        y=[p[1] / 1000.0 for p in curve],
        mode="lines+markers",
        name=turbine_key,
    ))
    spec = entry["spec"]
    for value, label in ((spec.get("cut_in_mps"), "V cut-in"), (spec.get("rated_wind_speed_mps"), "V nominal"), (spec.get("cut_out_mps"), "V cut-out")):
        if value is not None:
            fig.add_vline(x=float(value), line_dash="dash", opacity=0.5, annotation_text=label, annotation_position="top")
    fig.update_layout(**PLOT_LAYOUT, title="Curva de potência parametrizada", xaxis_title="Velocidade do vento (m/s)", yaxis_title="Potência (MW)")
    return fig


def plot_catalog_comparison(keys: list[str]) -> go.Figure:
    fig = go.Figure()
    for key in keys:
        curve = get_turbine(key)["curve"]["points"]
        fig.add_trace(go.Scatter(x=[p[0] for p in curve], y=[p[1] / 1000.0 for p in curve], mode="lines", name=key))
    fig.update_layout(**PLOT_LAYOUT, title="Comparação das curvas do catálogo", xaxis_title="Velocidade do vento (m/s)", yaxis_title="Potência (MW)")
    return fig


def plot_wind_rose(result: pd.DataFrame) -> go.Figure | None:
    if "wind_direction_deg" not in result or not result["wind_direction_deg"].notna().any():
        return None
    valid = result[["wind_direction_deg", "wind_speed_mps"]].dropna()
    if valid.empty:
        return None

    sectors = 16
    width = 360.0 / sectors
    idx = np.floor(((valid["wind_direction_deg"].to_numpy() + width / 2.0) % 360.0) / width).astype(int)
    counts = np.bincount(idx, minlength=sectors).astype(float)
    pct = counts / counts.sum() * 100.0
    theta = np.arange(sectors) * width
    mean_speed = []
    for i in range(sectors):
        subset = valid.loc[idx == i, "wind_speed_mps"]
        mean_speed.append(float(subset.mean()) if len(subset) else 0.0)

    fig = go.Figure(go.Barpolar(
        r=pct,
        theta=theta,
        width=[width * 0.88] * sectors,
        customdata=np.asarray(mean_speed)[:, None],
        hovertemplate="Direção %{theta:.0f}°<br>Frequência %{r:.1f}%<br>V média %{customdata[0]:.2f} m/s<extra></extra>",
        name="Frequência",
    ))
    fig.update_layout(
        template="plotly_white",
        title="Rosa dos ventos",
        margin=dict(l=35, r=35, t=50, b=35),
        polar=dict(
            angularaxis=dict(direction="clockwise", rotation=90),
            radialaxis=dict(title="Frequência (%)"),
        ),
        showlegend=False,
    )
    return fig


def plot_daily_energy(result: pd.DataFrame, show_net: bool) -> go.Figure:
    step_h = float(result.attrs.get("timestep_hours", 1.0 / 6.0))
    frame = result.copy()
    frame["date"] = pd.to_datetime(frame["timestamp"]).dt.date
    daily = frame.groupby("date", as_index=False).agg(power_gross_kw=("power_gross_kw", "sum"), power_net_kw=("power_net_kw", "sum"))
    daily["gross_mwh"] = daily["power_gross_kw"] * step_h / 1000.0
    daily["net_mwh"] = daily["power_net_kw"] * step_h / 1000.0
    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily["date"], y=daily["gross_mwh"], name="Bruta"))
    if show_net:
        fig.add_trace(go.Bar(x=daily["date"], y=daily["net_mwh"], name="Após -3%"))
    fig.update_layout(**PLOT_LAYOUT, title="Energia por dia", xaxis_title="Dia", yaxis_title="Energia (MWh)", barmode="group")
    return fig
