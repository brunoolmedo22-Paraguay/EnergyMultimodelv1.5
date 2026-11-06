"""Gráficos Plotly das previsões (Piso 2B) — funções puras (testáveis sem navegador).

Regras de apresentação:
* eixo X = data e hora; eixo Y = UMA grandeza física com sua unidade (nunca dois eixos Y; variáveis climáticas de
  unidades diferentes ficam em painéis separados com eixo X compartilhado);
* a linha é interrompida nas descontinuidades (intervalo > 1,5 × passo típico) e nos valores ausentes — nada é
  desenhado como se existisse; intervalos ausentes aparecem sombreados e ausentes marcados no eixo;
* a série transformada (grade de 1 min do EMS, só para visualização) é desenhada tracejada e rotulada como tal;
* o título identifica o estado (perfil do cenário × pré-visualização pendente) e a origem dos dados.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from seeds2.operation import forecasts as F

SERIES = "#2a78d6"          # série original (categórica 1)
TRANSFORMED = "#eb6834"     # série transformada (categórica 2), tracejada
WARN = "#C77700"            # estado: ausente / descontinuidade (sempre com rótulo na legenda)
GAP_FILL = "rgba(199,119,0,0.10)"
CONFIG = {"displaylogo": False, "responsive": True,
          "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
          "toImageButtonOptions": {"format": "png", "scale": 2}}


def _broken(ts: pd.Series, v: np.ndarray) -> tuple[list, list]:
    """Pontos com ``None`` inserido em cada descontinuidade: o Plotly interrompe a linha ali."""
    gaps, _ = F.gap_mask(ts)
    xs, ys = [], []
    t = list(pd.to_datetime(ts))
    for i, (x, y) in enumerate(zip(t, v)):
        xs.append(x)
        ys.append(None if not np.isfinite(y) else float(y))
        if i < len(gaps) and gaps[i]:
            xs.append(x + (t[i + 1] - x) / 2)
            ys.append(None)
    return xs, ys


def _mode(n: int) -> str:
    return "lines+markers" if n <= 200 else "lines"


def _gap_shapes(fig: go.Figure, ts: pd.Series, row: int | None = None) -> int:
    gaps, _ = F.gap_mask(ts)
    t = list(pd.to_datetime(ts))
    idx = np.flatnonzero(gaps)
    for i in idx[:60]:                                   # limite de formas (desempenho); a contagem total vai no texto
        kw = {"row": row, "col": 1} if row is not None else {}
        fig.add_vrect(x0=t[i], x1=t[i + 1], fillcolor=GAP_FILL, line_width=0, layer="below", **kw)
    return int(len(idx))


def variable_traces(df: pd.DataFrame, key: str, *, transformed: bool = False, legend: bool = True) -> list[go.Scatter]:
    var = F.VARIABLES[key]
    ts = pd.to_datetime(df["timestamp"])
    v = df[key].to_numpy(dtype=float)
    xs, ys = _broken(ts, v)
    angular = key in F.ANGULAR
    traces = [go.Scatter(
        x=xs, y=ys, name=f"{var.short} — dados originais", legendgroup="orig", showlegend=legend,
        mode="markers" if angular else _mode(len(df)), connectgaps=False,
        line={"color": SERIES, "width": 2}, marker={"color": SERIES, "size": 5 if angular else 4},
        hovertemplate=f"%{{y:.4g}} {var.unit}<extra></extra>")]
    miss = ~np.isfinite(v)
    if miss.any():
        traces.append(go.Scatter(
            x=list(ts[miss]), y=[None] * int(miss.sum()), name="Valor ausente", legendgroup="miss", showlegend=legend,
            mode="markers", marker={"color": WARN, "symbol": "x-thin", "size": 9, "line": {"width": 2, "color": WARN}},
            hovertemplate="valor ausente (não preenchido)<extra></extra>"))
    if transformed and len(df) >= 2:
        g = F.grid_view(df, key)
        traces.append(go.Scatter(
            x=list(g["timestamp"]), y=[None if not np.isfinite(y) else float(y) for y in g[key]],
            name=f"{var.short} — grade 1 min (transformada, só visualização)", legendgroup="grid", showlegend=legend,
            mode="markers" if angular else "lines", connectgaps=False,
            line={"color": TRANSFORMED, "width": 1.5, "dash": "dot"}, marker={"color": TRANSFORMED, "size": 3},
            hovertemplate=f"%{{y:.4g}} {var.unit} (interpolado)<extra></extra>"))
    return traces


def _missing_y(fig: go.Figure, df: pd.DataFrame, key: str, row: int | None) -> None:
    """Posiciona as marcas de ausentes na base do painel (y = mínimo observado)."""
    v = df[key].to_numpy(dtype=float)
    fin = v[np.isfinite(v)]
    base = float(fin.min()) if fin.size else 0.0
    for tr in fig.data:
        if tr.name == "Valor ausente" and (row is None or getattr(tr, "yaxis", "y") == ("y" if row == 1 else f"y{row}")):
            tr.y = [base] * len(tr.x)


def _layout(fig: go.Figure, title: str, subtitle: str, height: int) -> go.Figure:
    fig.update_layout(
        title={"text": f"{title}<br><span style='font-size:12px;opacity:.75'>{subtitle}</span>", "x": 0, "xanchor": "left"},
        height=height + 34, margin={"l": 10, "r": 10, "t": 74, "b": 44}, hovermode="x unified",
        # legenda na base do contêiner: nunca sobre títulos de painel nem sobre os dados
        legend={"orientation": "h", "yref": "container", "y": 0.0, "yanchor": "bottom", "xanchor": "left", "x": 0,
                "font": {"size": 11}},
        uirevision=title)
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,.15)", rangeslider={"visible": False},
                     tickformat="%H:%M\n%d/%m/%Y", hoverformat="%Y-%m-%d %H:%M:%S")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,.15)", zeroline=False)
    return fig


def demand_figure(df: pd.DataFrame, *, title: str, subtitle: str, transformed: bool = False) -> go.Figure:
    fig = go.Figure(variable_traces(df, "demand_kW", transformed=transformed))
    n_gaps = _gap_shapes(fig, df["timestamp"])
    _missing_y(fig, df, "demand_kW", None)
    fig.update_yaxes(title_text="Potência demandada (kW)", rangemode="tozero")
    fig.update_xaxes(title_text="Data e hora")
    if n_gaps:
        subtitle += f" · {n_gaps} intervalo(s) ausente(s) sombreado(s)"
    return _layout(fig, title, subtitle, 380)


def climate_figure(df: pd.DataFrame, *, title: str, subtitle: str, transformed: bool = False) -> go.Figure:
    keys = [k for k in F.SLOT_VARIABLES["climate"] if k in df.columns]
    rows = max(1, len(keys))
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.06 if rows > 1 else 0.0,
                        subplot_titles=[f"{F.VARIABLES[k].label} ({F.VARIABLES[k].unit})" for k in keys])
    n_gaps = 0
    for r, k in enumerate(keys, start=1):
        for tr in variable_traces(df, k, transformed=transformed, legend=(r == 1)):
            fig.add_trace(tr, row=r, col=1)
        n_gaps = _gap_shapes(fig, df["timestamp"], row=r)
        _missing_y(fig, df, k, r)
        fig.update_yaxes(title_text=F.VARIABLES[k].unit, row=r, col=1)
        if k == "wind_direction_deg":
            fig.update_yaxes(range=[0, 360], tickvals=[0, 90, 180, 270, 360], row=r, col=1)
        elif k in ("ghi_W_m2", "wind_speed_m_s"):
            fig.update_yaxes(rangemode="tozero", row=r, col=1)
    fig.update_xaxes(title_text="Data e hora", row=rows, col=1)
    if n_gaps:
        subtitle += f" · {n_gaps} intervalo(s) ausente(s) sombreado(s)"
    return _layout(fig, title, subtitle, 150 + 190 * rows)


def figure(slot: str, df: pd.DataFrame, **kw) -> go.Figure:
    return (demand_figure if slot == "demand" else climate_figure)(df, **kw)


__all__ = ["CONFIG", "climate_figure", "demand_figure", "figure", "variable_traces"]
