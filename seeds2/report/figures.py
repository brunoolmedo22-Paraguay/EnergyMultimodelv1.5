"""Figuras científicas estáticas (Piso 2D-B, Hito C) — PNG, SVG, PDF vetorial e ZIP com manifesto.

As curvas NÃO são redefinidas aqui: cada figura é a MESMA figura Plotly dos gráficos da interface
(``seeds2.ui.run_charts`` para a rodada, ``seeds2.ui.forecast_charts`` para as previsões), construída a partir dos dados
persistidos da rodada. ``render`` apenas desenha esse objeto Plotly com o matplotlib (traços, cores, tracejados,
interrupções em valores ausentes, linhas de referência, faixas sombreadas, títulos de painéis e eixos com unidades),
sem navegador nem Kaleido (dependência que exigiria Chrome no ambiente de implantação).

Padrão gráfico: fundo branco, largura de 170 mm (coluna de texto A4), DejaVu Sans (fonte embarcada no matplotlib),
legenda abaixo dos eixos, eixos com unidade; PNG a 300 dpi; SVG vetorial com o texto convertido em contornos
(aparência idêntica em qualquer visualizador); PDF vetorial (embutido no relatório).
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from html import unescape

import matplotlib

matplotlib.use("Agg", force=False)
import matplotlib.dates as mdates  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from seeds2.operation import forecasts as FV  # noqa: E402

from . import dossier as D  # noqa: E402

WIDTH_MM = 170.0
DPI = 300
FONT = "DejaVu Sans"
FIG_FORMAT = "seeds2-figures"
FIG_FORMAT_VERSION = 1
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
RC = {"font.family": FONT, "font.size": 8.5, "axes.titlesize": 8.5, "axes.labelsize": 8.5, "xtick.labelsize": 7.5,
      "ytick.labelsize": 7.5, "legend.fontsize": 7.5, "axes.edgecolor": "#4A5563", "axes.linewidth": 0.6,
      "xtick.color": "#2B3440", "ytick.color": "#2B3440", "axes.labelcolor": "#1F2933", "text.color": "#1F2933",
      "svg.fonttype": "path", "svg.hashsalt": "seeds2", "pdf.fonttype": 42, "figure.facecolor": "white",
      "axes.facecolor": "white", "savefig.facecolor": "white"}
_DASH = {"dot": (0, (1.2, 1.8)), "dash": (0, (4.5, 2.5)), "dashdot": (0, (4.5, 2, 1.2, 2)), "longdash": (0, (8, 3)),
         "solid": "-", None: "-"}
_MARKER = {"x-thin": "x", "x": "x", "circle": "o", "square": "s", "diamond": "D", "triangle-up": "^", None: "o"}


class FigureError(D.DossierError):
    """Uma figura não pôde ser produzida a partir dos dados gravados."""


@dataclass
class FigureSpec:
    key: str                       # nome de arquivo (ASCII, sem extensão)
    title: str
    description: str
    units: str
    data_sources: list[str]        # dados da rodada / previsões usados (com SHA-256 no manifesto)
    plotly: object                 # plotly.graph_objects.Figure (o MESMO dos gráficos da interface)
    height_px: int = 440
    notes: list[str] = field(default_factory=list)


# ====================================================================== catálogo (a partir do dossiê)
def _subtitle(d: D.RunDossier, n: int) -> str:
    from seeds2.operation import mission as M

    from html import escape                       # o título Plotly aceita marcação: texto do usuário vai escapado

    return escape(f"Rodada {d.run_uid[:8]} · {d.scenario_name} v{d.run.scenario_version} · {n} passos de 60 s · "
                  f"fuso {M.tz_label(d.timezone)}")


def run_figures(d: D.RunDossier, *, forecasts: bool = True) -> list[FigureSpec]:
    """Figuras disponíveis da rodada (somente as que os dados gravados sustentam; nada é sintetizado)."""
    from seeds2.ui import forecast_charts as FCH
    from seeds2.ui import run_charts as RC_

    if not d.concluded:
        return []
    out_df, inp = d.outputs(), d.inputs()
    specs: list[FigureSpec] = []
    if out_df is not None:
        sub = _subtitle(d, len(out_df))
        fig = RC_.power_figure(out_df, subtitle=sub)
        specs.append(FigureSpec("01_demanda_potencia_por_fonte", "Demanda e potência por fonte",
                                "Demanda elétrica, potência renovável DISPONÍVEL (FV/eólica) e potência DESPACHADA pelo EMS "
                                "por fonte controlável; déficit e excedente quando registrados.", "kW",
                                [D.CSV_OUTPUTS], fig, 440))
        bat = ((d.manifest.get("engine_inputs") or {}).get("declared_initial_state") or {}).get("battery") or {}
        fig = RC_.soc_figure(out_df, soc_min=bat.get("soc_min_pct"), soc_max=bat.get("soc_max_pct"), subtitle=sub)
        if fig is not None:
            specs.append(FigureSpec("02_estado_de_carga_bateria", "Estado de carga da bateria",
                                    "SOC gravado (fração 0–1) exibido em % (× 100), com os limites efetivos de SOC "
                                    "declarados ao motor.", "%", [D.CSV_OUTPUTS], fig, 320))
        fig = RC_.h2_figure(out_df, subtitle=sub)
        if fig is not None:
            specs.append(FigureSpec("03_hidrogenio_acumulado", "Consumo acumulado de hidrogênio",
                                    "Soma acumulada da coluna h2_kg (kg por passo, estimativa do EMS) e, quando gravada, "
                                    "da validação dinâmica PEMFC (metodologias distintas). O total oficial é o do resumo "
                                    "persistido da rodada.", "kg", [D.CSV_OUTPUTS], fig, 300))
    if inp is not None:
        sub = _subtitle(d, len(inp))
        fig = RC_.inputs_figure(inp, subtitle=sub)
        n = len([c for c in fig.layout.annotations or []])
        specs.append(FigureSpec("04_entradas_da_missao", "Entradas da missão na grade do motor",
                                "Demanda e variáveis climáticas efetivamente entregues ao motor (grade de 1 min), lidas de "
                                "entradas/missao.csv.", "por painel (kW, W/m², °C, …)", [D.CSV_INPUTS], fig,
                                120 + 170 * max(1, n)))
    if forecasts:
        for i, (slot, entry) in enumerate(sorted(d.forecasts().items(), key=lambda kv: kv[0] != "demand"), start=5):
            if slot not in ("demand", "climate"):
                continue
            df = d.forecast_frame(slot)
            from seeds2.microgrid import config as C
            from seeds2.operation import contracts

            label = contracts.FORECAST_SOURCE_TYPES.get(entry.get("source_type"), entry.get("source_type"))
            prov = C.PROVENANCE_KINDS.get(entry.get("provenance"), entry.get("provenance"))
            from html import escape

            sub = escape(f"{label} · {prov} · {len(df)} pontos · fuso {entry.get('timezone') or 'não declarado'} · "
                         f"série original do cenário v{d.run.scenario_version}")
            title = "Previsão de demanda" if slot == "demand" else "Previsão climática"
            fig = FCH.figure(slot, df, title=title, subtitle=sub, transformed=False)
            keys = [k for k in df.columns if k != "timestamp"]
            specs.append(FigureSpec(f"{i:02d}_previsao_{'demanda' if slot == 'demand' else 'clima'}", title,
                                    f"Série ORIGINAL normalizada da previsão ({entry.get('label')}) gravada no cenário; "
                                    "intervalos ausentes sombreados; nada interpolado.",
                                    ", ".join(dict.fromkeys(FV.VARIABLES[k].unit for k in keys if k in FV.VARIABLES)),
                                    [f"previsao:{slot}:{entry.get('data')}"], fig,
                                    int(fig.layout.height or 380)))
    return specs


# ====================================================================== Plotly → matplotlib
def _color(c, default="#1F2933"):
    if not c:
        return default
    c = str(c).strip()
    m = re.fullmatch(r"rgba?\(([^)]*)\)", c)
    if m:
        p = [float(x) for x in m.group(1).split(",")]
        rgb = tuple(min(max(v / 255.0, 0.0), 1.0) for v in p[:3])
        return (*rgb, p[3]) if len(p) > 3 else rgb
    return c


_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean(s) -> str:
    """Texto não confiável para o desenho: controles → U+FFFD; '$' escapado (sem mathtext do matplotlib)."""
    return _CTRL.sub("\ufffd", str(s or "")).replace("$", r"\$")


def _text(s) -> tuple[str, str]:
    """Título Plotly ("t<br><span …>sub</span>") → (título, subtítulo) em texto simples."""
    s = str(s or "")
    parts = re.split(r"<br\s*/?>", s, maxsplit=1)
    out = [clean(unescape(re.sub(r"<[^>]+>", "", p))).strip() for p in parts]
    return out[0], (out[1] if len(out) > 1 else "")


def _xs(values) -> np.ndarray:
    if values is None:
        return np.array([])
    arr = pd.to_datetime(pd.Series(list(values)), errors="coerce")
    return arr.to_numpy()


def _ys(values) -> np.ndarray:
    if values is None:
        return np.array([], dtype=float)
    return pd.to_numeric(pd.Series(list(values), dtype=object), errors="coerce").to_numpy(dtype=float)


def _axis_id(ref: str | None, letter: str) -> str:
    ref = (ref or letter).replace(" domain", "")
    return letter + ref[1:] if ref != letter else letter


def render(spec: FigureSpec, fmt: str, *, dpi: int = DPI, width_mm: float = WIDTH_MM) -> bytes:
    """Desenha ``spec.plotly`` em ``fmt`` ("png" | "svg" | "pdf"). Determinístico para os mesmos dados."""
    if fmt not in ("png", "svg", "pdf"):
        raise FigureError(f"Formato de figura não suportado: {fmt!r}.")
    import matplotlib as mpl

    with mpl.rc_context(RC):
        fig = _draw(spec, width_mm)
        buf = io.BytesIO()
        meta = {"png": {"Software": f"SEEDS2 (matplotlib {mpl.__version__})", "Title": spec.title},
                "svg": {"Date": None, "Creator": "SEEDS2", "Title": spec.title},
                "pdf": {"CreationDate": None, "Creator": "SEEDS2", "Title": spec.title}}[fmt]
        fig.savefig(buf, format=fmt, dpi=dpi, metadata=meta)
        return buf.getvalue()


def size_mm(spec: FigureSpec, width_mm: float = WIDTH_MM) -> tuple[float, float]:
    rows = max(1, len({_axis_id(getattr(t, "yaxis", None), "y") for t in spec.plotly.data}))
    h = max(62.0, min(225.0, 0.27 * spec.height_px + (10.0 if rows > 1 else 0.0)))
    return width_mm, h


def _draw(spec: FigureSpec, width_mm: float) -> Figure:
    pf = spec.plotly
    lay = pf.layout
    w_mm, h_mm = size_mm(spec, width_mm)
    fig = Figure(figsize=(w_mm / 25.4, h_mm / 25.4), layout="constrained")
    fig.get_layout_engine().set(h_pad=0.04, hspace=0.06)
    # eixos y presentes (painéis), ordenados de cima para baixo pelo domínio
    yids = []
    for t in pf.data:
        y = _axis_id(getattr(t, "yaxis", None), "y")
        if y not in yids:
            yids.append(y)
    if not yids:
        yids = ["y"]

    def dom(yid):
        ax = lay[("yaxis" + yid[1:]) if yid != "y" else "yaxis"]
        d = list(ax.domain) if ax and ax.domain else [0, 1]
        return d

    yids.sort(key=lambda y: -dom(y)[1])
    ratios = [max(0.05, dom(y)[1] - dom(y)[0]) for y in yids]
    axes = fig.subplots(len(yids), 1, sharex=True, squeeze=False, gridspec_kw={"height_ratios": ratios})[:, 0]
    ax_of = dict(zip(yids, axes))
    handles: dict[str, object] = {}
    span: list = []
    for t in pf.data:
        ax = ax_of[_axis_id(getattr(t, "yaxis", None), "y")]
        x, y = _xs(t.x), _ys(t.y)
        if not len(x):
            continue
        ok = x[~pd.isna(x)]
        if len(ok):
            span += [ok.min(), ok.max()]
        mode = t.mode or "lines"
        line, marker = t.line or {}, t.marker or {}
        color = _color(line.color or marker.color)
        kw = {"label": clean(t.name)}
        if "lines" in mode:
            h, = ax.plot(x, y, color=color, linewidth=max(0.6, float(line.width or 2) * 0.62),
                         linestyle=_DASH.get(line.dash, "-"),
                         marker=_MARKER.get(marker.symbol) if "markers" in mode else None,
                         markersize=max(1.5, float(marker.size or 4) * 0.45), **kw)
        else:
            h = ax.scatter(x, y, color=_color(marker.color or color), s=max(4.0, float(marker.size or 5) ** 2 * 0.35),
                           marker=_MARKER.get(marker.symbol, "o"), linewidths=0.9, **kw)
        if t.showlegend is not False and t.name and clean(t.name) not in handles:
            handles[clean(t.name)] = h
    # formas: linhas horizontais (limites) e faixas verticais (intervalos ausentes)
    for s in lay.shapes or []:
        yid = _axis_id(s.yref, "y")
        ax = ax_of.get(yid, axes[0])
        lc = _color((s.line or {}).color, "#8A94A3")
        if s.type == "line" and s.y0 == s.y1 and "domain" in str(s.xref or "") + "paper":
            ax.axhline(float(s.y0), color=lc, linewidth=0.8, linestyle=_DASH.get((s.line or {}).dash, "-"))
        elif s.type == "rect":
            ax.axvspan(pd.Timestamp(s.x0), pd.Timestamp(s.x1), color=_color(s.fillcolor, "#C77700"), linewidth=0,
                       alpha=None if "rgba" in str(s.fillcolor) else 0.12, zorder=0)
    # anotações: títulos de painel (paper) e rótulos das linhas de referência (eixo y)
    for a in lay.annotations or []:
        txt = clean(unescape(re.sub(r"<[^>]+>", "", str(a.text or ""))))
        if str(a.yref or "").startswith("y") and "domain" not in str(a.yref):
            ax = ax_of.get(_axis_id(a.yref, "y"), axes[0])
            ax.annotate(txt, xy=(0.005, float(a.y)), xycoords=("axes fraction", "data"), xytext=(0, 2),
                        textcoords="offset points", fontsize=6.8, color="#4A5563", va="bottom")
        elif a.yref in (None, "paper") and a.xref in (None, "paper") and len(yids) > 1:
            best = min(yids, key=lambda y: abs(dom(y)[1] - float(a.y or 0)))
            ax_of[best].set_title(txt, loc="left", fontsize=8, color="#1F2933", pad=3)
    # eixos
    for yid, ax in ax_of.items():
        yl = lay[("yaxis" + yid[1:]) if yid != "y" else "yaxis"]
        if yl.title and yl.title.text:
            ax.set_ylabel(clean(unescape(yl.title.text)))
        if yl.range:
            ax.set_ylim(float(yl.range[0]), float(yl.range[1]))
        elif yl.rangemode == "tozero":
            lo, hi = ax.get_ylim()
            ax.set_ylim(min(0.0, lo), max(0.0, hi))
        if yl.tickvals:
            ax.set_yticks(list(yl.tickvals))
        ax.grid(True, color="#D5DAE1", linewidth=0.5)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    bottom = axes[-1]
    xid = "xaxis" + (str(len(yids)) if len(yids) > 1 else "")
    xl = lay[xid] if xid in lay else lay.xaxis
    xtitle = (xl.title.text if xl and xl.title and xl.title.text else None) or \
             (lay.xaxis.title.text if lay.xaxis.title and lay.xaxis.title.text else "")
    title, sub = _text(lay.title.text if lay.title else spec.title)
    fig.suptitle(title or spec.title, x=0.01, ha="left", fontsize=10, fontweight="bold")
    if sub:
        import textwrap

        sub = "\n".join(textwrap.wrap(sub, 118))
        first = axes[0].get_title("left") if len(yids) > 1 else ""
        axes[0].set_title(f"{sub}\n{first}" if first else sub, loc="left", fontsize=7.2, color="#4A5563", pad=3)
    _date_axis(bottom, xtitle, span)
    if handles:
        n = len(handles)
        fig.legend(list(handles.values()), list(handles.keys()), loc="outside lower center",
                   ncol=min(3, n), frameon=False, handlelength=2.4, columnspacing=1.4)
    return fig


def _date_axis(ax, xtitle: str | None, span: list) -> None:
    """Eixo temporal: horas nos rótulos; a data vai no título do eixo se os DADOS cabem num só dia (sem ambiguidade)."""
    if span:
        lo, hi = pd.Timestamp(min(span)), pd.Timestamp(max(span))
    else:
        lo, hi = (pd.Timestamp(mdates.num2date(v).replace(tzinfo=None)) for v in ax.get_xlim())
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
    title = clean(unescape(xtitle or ""))
    if lo.date() == hi.date():
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        title = f"{title} · {lo:%d/%m/%Y}" if title else f"{lo:%d/%m/%Y}"
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y\n%H:%M"))
    ax.set_xlabel(title)


# ====================================================================== ZIP de figuras
def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def figures_zip(d: D.RunDossier, *, specs: list[FigureSpec] | None = None, generated_at: str | None = None,
                progress=None) -> tuple[bytes, dict]:
    """ZIP com ``figuras/png/*.png``, ``figuras/svg/*.svg``, ``manifest.json`` e ``LEIA-ME.txt``."""
    specs = run_figures(d) if specs is None else specs
    if not specs:
        raise FigureError("Esta rodada não tem séries gravadas para figuras (rodada não concluída ou sem dados).")
    generated_at = generated_at or D.utc_now()
    files: dict[str, bytes] = {}
    entries = []
    for i, s in enumerate(specs, start=1):
        if progress:
            progress(f"Figura {i} de {len(specs)}: {s.title}")
        w, h = size_mm(s)
        for fmt in ("png", "svg"):
            b = render(s, fmt)
            path = f"figuras/{fmt}/{s.key}.{fmt}"
            files[path] = b
            entries.append({"file": path, "format": fmt, "sha256": _sha(b), "size": len(b), "figure": s.key,
                            "title": s.title, "description": s.description, "units": s.units,
                            "width_mm": round(w, 2), "height_mm": round(h, 2),
                            **({"dpi": DPI, "width_px": round(w / 25.4 * DPI), "height_px": round(h / 25.4 * DPI)}
                               if fmt == "png" else {"vector": True, "text_as_paths": True}),
                            "data_sources": [_source_ref(d, x) for x in s.data_sources]})
    manifest = {
        "format": FIG_FORMAT, "format_version": FIG_FORMAT_VERSION, "generated_at": generated_at,
        "generator": D.generator_info(), "derived": True, "note": D.DERIVED_NOTE,
        "experiment": {**D.identity_for_manifest(d)},
        "figures": entries,
    }
    readme = ("SEEDS2 — figuras científicas de uma rodada (pacote DERIVADO)\n\n"
              f"Rodada: {d.run_uid}\nCenário: {d.scenario_name} (versão {d.run.scenario_version})\n"
              f"Microrrede de origem: {d.microgrid.get('name')} ({d.run.microgrid_uid})\n"
              f"Origem dos dados: {D.ORIGIN_LABELS[d.kind]}\nGerado em: {generated_at}\n\n"
              "As figuras foram desenhadas a partir das séries persistidas da rodada, sem executar modelos nem o EMS.\n"
              "manifest.json lista cada arquivo com SHA-256, unidade, descrição e os dados de origem (com SHA-256).\n"
              "Este pacote NÃO substitui o estudo científico portátil (.seeds2study.zip).\n")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, b in [("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")),
                        ("LEIA-ME.txt", readme.encode("utf-8")), *sorted(files.items())]:
            info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, b)
    return buf.getvalue(), manifest


def _source_ref(d: D.RunDossier, src: str) -> dict:
    if src.startswith("previsao:"):
        _, slot, digest = src.split(":", 2)
        return {"kind": "previsao", "slot": slot, "sha256": digest}
    idx = d.run.data.get(src) or {}
    return {"kind": "dado_da_rodada", "name": src, "sha256": idx.get("sha256"), "size": idx.get("size")}


__all__ = ["DPI", "FigureError", "FigureSpec", "figures_zip", "render", "run_figures", "size_mm"]
