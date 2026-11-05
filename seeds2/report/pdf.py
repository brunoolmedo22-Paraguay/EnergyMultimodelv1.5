"""Relatório técnico de configuração da microrrede (PDF, reportlab, sem serviços externos).

Gerado EXCLUSIVAMENTE a partir da configuração salva (revisão + impressão digital), com os valores exatos e a
procedência registrada. Dados desconhecidos aparecem como "Não declarado"; nada é completado ficticiamente.
O documento não atribui certificação, conformidade normativa nem validação experimental.

Fontes: Helvetica (padrão PDF, sem dependência de fontes do sistema). Caracteres fora do repertório da fonte são
transcritos (p. ex. H₂ → H<sub>2</sub>) por ``_t``.
"""
from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, KeepTogether, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

from seeds2 import APP_NAME, APP_VERSION
from seeds2.microgrid import adapter as A
from seeds2.microgrid import config as C
from seeds2.microgrid.derived import PV_STC_ASSUMPTIONS, battery_derived, pv_array_nominal, pv_plant_summary
from seeds2.microgrid.references import (KIND_LABELS, PEMFC_REF_KEY, battery_references, pemfc_references, pv_references,
                                         wind_curve, wind_spec)

TEAL = colors.HexColor("#0E7C86")
TEAL_DARK = colors.HexColor("#0A5A62")
INK = colors.HexColor("#132030")
MUTED = colors.HexColor("#5B6B7C")
SURFACE = colors.HexColor("#EEF3F6")
BORDER = colors.HexColor("#D3DBE4")
OK = colors.HexColor("#2E8B57")
WARN = colors.HexColor("#B06A00")
BAD = colors.HexColor("#C2364A")
KIND_COLORS = {"pv": "#E0891E", "wind": "#2F6FED", "battery": "#3C9D5D", "pemfc": "#0E7C86", "thermal": "#D1495B"}
ND = "Não declarado"
PAGE_W, PAGE_H = A4
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 18 * mm, 24 * mm, 20 * mm

_REPLACE = {"₂": "<sub>2</sub>", "≤": "<=", "≥": ">=", "→": "->", "←": "<-", "−": "-", "✓": "", "✕": "x", "≈": "~",
            "Σ": "soma ", "η": "eta", "Δ": "delta", "‑": "-"}


def _t(s: Any) -> str:
    """Texto do usuário/catálogo → markup seguro para Paragraph (XML escapado, repertório Helvetica/cp1252)."""
    s = xml_escape(str(s if s is not None else ""))
    out = []
    for ch in s:
        if ch in _REPLACE:
            out.append(_REPLACE[ch])
            continue
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            base = unicodedata.normalize("NFKD", ch).encode("cp1252", "ignore").decode("cp1252")
            out.append(base or "?")
    return "".join(out)


def _plain(s: Any) -> str:
    """Para Strings de gráficos (sem markup)."""
    return re.sub(r"</?sub>", "", _t(s)).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def _dt(iso: Any) -> str | None:
    """ISO 8601 → "dd/mm/aaaa hh:mm UTC" (mantém o valor original se não for interpretável)."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M UTC")
    except ValueError:
        return str(iso)


SHORT_STATUS = {A.REPRESENTED: "Simulado", A.INCOMPLETE: "Pendente", A.INCOMPATIBLE: "Não representável",
                A.DISABLED: "Desabilitado"}
SHORT_KIND = {"pv": "Solar FV", "wind": "Eólica", "battery": "Bateria", "pemfc": "H2 / PEMFC", "thermal": "Térmica"}


def _num(x: Any, d: int = 1, unit: str = "") -> str:
    if x is None or isinstance(x, bool):
        return ND
    s = f"{float(x):,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"{s} {unit}".strip()


# ---------------------------------------------------------------------------------------------- estilos
def _styles() -> dict[str, ParagraphStyle]:
    base = dict(fontName="Helvetica", textColor=INK, leading=13.2, fontSize=9.4)
    return {
        "body": ParagraphStyle("body", **base, spaceAfter=4),
        "small": ParagraphStyle("small", **{**base, "fontSize": 7.8, "leading": 10.2, "textColor": MUTED}, spaceAfter=3),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 7.9, "leading": 9.8}),
        "cellb": ParagraphStyle("cellb", **{**base, "fontSize": 7.9, "leading": 9.8, "fontName": "Helvetica-Bold"}),
        "th": ParagraphStyle("th", **{**base, "fontSize": 7.4, "leading": 9.2, "fontName": "Helvetica-Bold", "textColor": colors.white}),
        "h1": ParagraphStyle("h1", **{**base, "fontSize": 15.5, "leading": 19, "fontName": "Helvetica-Bold", "textColor": INK},
                             spaceBefore=4, spaceAfter=3),
        "eyebrow": ParagraphStyle("eyebrow", **{**base, "fontSize": 7.4, "leading": 9, "fontName": "Helvetica-Bold", "textColor": TEAL}),
        "h2": ParagraphStyle("h2", **{**base, "fontSize": 11.2, "leading": 14, "fontName": "Helvetica-Bold", "textColor": TEAL_DARK},
                             spaceBefore=9, spaceAfter=4),
        "kpi_v": ParagraphStyle("kpi_v", **{**base, "fontSize": 13.5, "leading": 16, "fontName": "Helvetica-Bold"}),
        "kpi_k": ParagraphStyle("kpi_k", **{**base, "fontSize": 6.8, "leading": 8.4, "fontName": "Helvetica-Bold", "textColor": MUTED}),
        "kpi_n": ParagraphStyle("kpi_n", **{**base, "fontSize": 7.2, "leading": 9, "textColor": MUTED}),
        "note": ParagraphStyle("note", **{**base, "fontSize": 8.4, "leading": 11.4, "textColor": INK}, leftIndent=7, borderPadding=(5, 6, 5, 8)),
    }


S = _styles()


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


# ---------------------------------------------------------------------------------------------- blocos
def section(num: int, title: str, kicker: str) -> list:
    return [CondPageBreak(60 * mm), Spacer(1, 6 * mm), P(f"{num:02d} · {_t(kicker).upper()}", "eyebrow"), P(_t(title), "h1"),
            _rule(), Spacer(1, 2.5 * mm)]


def _rule(color=TEAL, width=1.1) -> Table:
    t = Table([[""]], colWidths=[PAGE_W - 2 * MARGIN_X], rowHeights=[0.1])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), width, color)]))
    return t


def note(text: str, tone: str = "info") -> Table:
    c = {"info": TEAL, "warn": WARN, "bad": BAD, "ok": OK}[tone]
    bg = {"info": colors.HexColor("#E8F3F4"), "warn": colors.HexColor("#FBF3E6"), "bad": colors.HexColor("#FBECEE"),
          "ok": colors.HexColor("#EAF5EF")}[tone]
    t = Table([[P(text, "note")]], colWidths=[PAGE_W - 2 * MARGIN_X])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 2.4, c),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def table(header: list[str], rows: list[list[Any]], widths: list[float], *, zebra: bool = True, bold_first: bool = False) -> Table:
    """Tabela com cabeçalho repetido em quebras de página; células como Paragraph (quebra de linha)."""
    data = [[P(_t(h), "th") for h in header]]
    for r in rows:
        data.append([c if isinstance(c, Paragraph) else P(_t(c) if c not in (None, "") else ND,
                                                          "cellb" if (bold_first and i == 0) else "cell")
                     for i, c in enumerate(r)])
    total = PAGE_W - 2 * MARGIN_X
    scale = total / sum(widths)
    t = Table(data, colWidths=[w * scale for w in widths], repeatRows=1, splitByRow=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), TEAL), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LINEBELOW", (0, 0), (-1, -1), 0.35, BORDER), ("LEFTPADDING", (0, 0), (-1, -1), 4.2),
             ("RIGHTPADDING", (0, 0), (-1, -1), 4.2), ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2)]
    if zebra:
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), SURFACE))
    t.setStyle(TableStyle(style))
    return t


def kv(rows: list[tuple[str, Any]], widths=(0.34, 0.66)) -> Table:
    data = [[P(_t(k), "cellb"), P(_t(v) if v not in (None, "") else f"<font color='#5B6B7C'>{ND}</font>", "cell")] for k, v in rows]
    total = PAGE_W - 2 * MARGIN_X
    t = Table(data, colWidths=[total * widths[0], total * widths[1]])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.35, BORDER),
                           ("BACKGROUND", (0, 0), (0, -1), SURFACE), ("LEFTPADDING", (0, 0), (-1, -1), 5),
                           ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2)]))
    return t


def kpis(items: list[tuple[str, str, str]]) -> Table:
    cells = [[P(_t(k).upper(), "kpi_k"), P(_t(v), "kpi_v"), P(_t(n), "kpi_n")] for k, v, n in items]
    n = len(cells)
    total = PAGE_W - 2 * MARGIN_X
    gap = 3 * mm
    w = (total - gap * (n - 1)) / n
    inner = [Table([[c[0]], [c[1]], [c[2]]], colWidths=[w - 10]) for c in cells]
    for t in inner:
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5)]))
    row, widths = [], []
    for i, t in enumerate(inner):
        row.append(t)
        widths.append(w)
        if i < n - 1:
            row.append("")
            widths.append(gap)
    outer = Table([row], colWidths=widths)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i in range(0, len(row), 2):
        st += [("BACKGROUND", (i, 0), (i, 0), SURFACE), ("BOX", (i, 0), (i, 0), 0.5, BORDER),
               ("LINEABOVE", (i, 0), (i, 0), 2, TEAL), ("LEFTPADDING", (i, 0), (i, 0), 6), ("TOPPADDING", (i, 0), (i, 0), 6),
               ("BOTTOMPADDING", (i, 0), (i, 0), 6)]
    outer.setStyle(TableStyle(st))
    return outer


# ---------------------------------------------------------------------------------------------- gráficos vetoriais
def wind_curve_drawing(key: str, width: float) -> Drawing | None:
    c = wind_curve(key)
    if not c:
        return None
    h = 62 * mm
    d = Drawing(width, h)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 40, 30, width - 56, h - 48
    pts = [tuple(p) for p in c["points"]]
    lp.data = [pts, pts]
    lp.lines[0].strokeColor = colors.HexColor("#2F6FED")
    lp.lines[0].strokeWidth = 0.9
    lp.lines[0].strokeDashArray = [2, 2]
    lp.lines[1].strokeColor = colors.transparent
    lp.lines[1].symbol = makeMarker("FilledCircle", size=4.6, fillColor=TEAL, strokeColor=None)
    vmax = max(p[0] for p in pts)
    pmax = max(p[1] for p in pts)
    import math

    lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 0, math.ceil(vmax / 5) * 5
    lp.xValueAxis.valueStep = 5
    lp.yValueAxis.valueMin = 0
    lp.yValueAxis.valueMax = pmax * 1.12
    for ax in (lp.xValueAxis, lp.yValueAxis):
        ax.labels.fontName, ax.labels.fontSize, ax.labels.fillColor = "Helvetica", 6.8, MUTED
        ax.strokeColor = BORDER
    lp.yValueAxis.labelTextFormat = lambda v: f"{v:,.0f}".replace(",", ".")
    lp.yValueAxis.visibleGrid, lp.yValueAxis.gridStrokeColor, lp.yValueAxis.gridStrokeWidth = 1, colors.HexColor("#E6ECF1"), 0.4
    d.add(lp)
    d.add(String(lp.x + lp.width / 2, 6, "Velocidade do vento [m/s]", fontName="Helvetica", fontSize=7.2, fillColor=INK, textAnchor="middle"))
    lab = String(0, 0, "Potência elétrica [kW]", fontName="Helvetica", fontSize=7.2, fillColor=INK, textAnchor="middle")
    from reportlab.graphics.shapes import Group
    g = Group(lab)
    g.translate(11, lp.y + lp.height / 2)
    g.rotate(90)
    d.add(g)
    lx = lp.x + 6
    ly = h - 10
    d.add(Line(lx, ly + 2.5, lx + 14, ly + 2.5, strokeColor=colors.HexColor("#2F6FED"), strokeWidth=0.9, strokeDashArray=[2, 2]))
    d.add(String(lx + 18, ly, "Interpolação linear (apenas visual)", fontName="Helvetica", fontSize=6.8, fillColor=MUTED))
    d.add(Rect(lx + 150, ly + 0.8, 3.4, 3.4, fillColor=TEAL, strokeColor=None))
    d.add(String(lx + 158, ly, "Pontos tabulados do catálogo", fontName="Helvetica", fontSize=6.8, fillColor=MUTED))
    return d


def balance_drawing(cfg: dict, plan: A.SimulationPlan, width: float) -> Drawing:
    eqs = cfg.get("equipment", [])
    srcs = [e for e in eqs if e["kind"] != "battery"]
    stor = [e for e in eqs if e["kind"] == "battery"]
    rows = max(len(srcs) + len(stor) + (1 if stor else 0), 3)
    row_h = 15
    h = max(70 * mm, rows * row_h + 40)
    d = Drawing(width, h)
    colw = width * 0.34
    y = h - 22
    d.add(String(0, h - 9, "FONTES E ARMAZENAMENTO", fontName="Helvetica-Bold", fontSize=6.6, fillColor=MUTED))
    status_col = {A.REPRESENTED: OK, A.INCOMPLETE: WARN, A.INCOMPATIBLE: BAD, A.DISABLED: MUTED}

    def node(e):
        nonlocal y
        ms = plan.for_equipment(e["id"])
        sts = {m.status for m in ms}
        stc = OK if sts == {A.REPRESENTED} else MUTED if sts == {A.DISABLED} else BAD if A.INCOMPATIBLE in sts and A.REPRESENTED not in sts else WARN
        d.add(Rect(0, y - 9, colw, 12.5, rx=3, ry=3, fillColor=colors.HexColor("#F6F9FB"), strokeColor=BORDER, strokeWidth=0.5))
        d.add(Rect(0, y - 9, 3, 12.5, fillColor=colors.HexColor(KIND_COLORS.get(e["kind"], "#5B6B7C")), strokeColor=None))
        name = _plain(e["name"])
        name = name if len(name) <= 27 else name[:26].rstrip() + "…"
        txt = f"{name} · {SHORT_KIND[e['kind']]}"
        d.add(String(7, y - 5, txt, fontName="Helvetica", fontSize=6.9, fillColor=INK))
        d.add(Rect(colw - 9, y - 6, 5.5, 5.5, rx=2.7, ry=2.7, fillColor=stc, strokeColor=None))
        y -= row_h

    for e in srcs:
        node(e)
    if stor:
        d.add(String(0, y - 3, "ARMAZENAMENTO", fontName="Helvetica-Bold", fontSize=6.6, fillColor=MUTED))
        y -= 12
        for e in stor:
            node(e)
    if not eqs:
        d.add(String(0, y - 5, "Nenhum equipamento registrado.", fontName="Helvetica", fontSize=7, fillColor=MUTED))
    cx = colw + 18
    cw = width * 0.30
    cy = h / 2 - 22
    arrow = lambda x1, x2, yy: [Line(x1, yy, x2 - 4, yy, strokeColor=TEAL, strokeWidth=1.4),  # noqa: E731
                                Polygon([x2, yy, x2 - 6, yy + 3.5, x2 - 6, yy - 3.5], fillColor=TEAL, strokeColor=None)]
    for el in arrow(colw + 3, cx - 2, cy + 22):
        d.add(el)
    d.add(Rect(cx, cy, cw, 44, rx=6, ry=6, fillColor=colors.HexColor("#E3F1F2"), strokeColor=TEAL, strokeWidth=1))
    d.add(String(cx + cw / 2, cy + 28, "Balanço energético agregado", fontName="Helvetica-Bold", fontSize=8, fillColor=INK, textAnchor="middle"))
    d.add(String(cx + cw / 2, cy + 17, "soma de potências a cada passo de 1 min", fontName="Helvetica", fontSize=6.5, fillColor=MUTED, textAnchor="middle"))
    d.add(String(cx + cw / 2, cy + 8, "déficit e vertimento contabilizados", fontName="Helvetica", fontSize=6.5, fillColor=MUTED, textAnchor="middle"))
    dx = cx + cw + 18
    dw = width - dx
    for el in arrow(cx + cw + 2, dx - 2, cy + 22):
        d.add(el)
    d.add(Rect(dx, cy + 6, dw, 32, rx=5, ry=5, fillColor=colors.HexColor("#F1EEFA"), strokeColor=colors.HexColor("#B9A9E6"), strokeWidth=0.8))
    d.add(String(dx + dw / 2, cy + 25, "Atendimento da demanda", fontName="Helvetica-Bold", fontSize=7.6, fillColor=INK, textAnchor="middle"))
    dem = C.DEMAND_SOURCES.get((cfg.get("demand") or {}).get("source"), "")
    d.add(String(dx + dw / 2, cy + 14, _plain(dem)[:38], fontName="Helvetica", fontSize=6.3, fillColor=MUTED, textAnchor="middle"))
    if (cfg.get("energy_balance") or {}).get("grid_connection") == "conectada":
        d.add(Rect(dx, cy - 30, dw, 26, rx=5, ry=5, fillColor=colors.white, strokeColor=MUTED, strokeWidth=0.8, strokeDashArray=[3, 2]))
        d.add(String(dx + dw / 2, cy - 15, "Rede elétrica (conexão declarada)", fontName="Helvetica-Bold", fontSize=6.8, fillColor=INK, textAnchor="middle"))
        d.add(String(dx + dw / 2, cy - 25, "não modelada pelo EMS atual", fontName="Helvetica", fontSize=6.3, fillColor=MUTED, textAnchor="middle"))
    return d


# ---------------------------------------------------------------------------------------------- página
class _NumberedCanvas(rl_canvas.Canvas):
    """Canvas em duas passagens para imprimir "Página X de Y"."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._saved: list[dict] = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self.setFont("Helvetica", 7.2)
                self.setFillColor(MUTED)
                self.drawRightString(PAGE_W - MARGIN_X, 11 * mm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


def _decorations(meta: dict):
    def cover(c, doc):
        c.saveState()
        c.setFillColor(TEAL)
        c.rect(0, PAGE_H - 108 * mm, PAGE_W, 108 * mm, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#0B6D76"))
        for i in range(7):                                         # linhas de fluxo estilizadas (marca gráfica)
            c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.08 + 0.02 * i))
            c.setLineWidth(1)
            y0 = PAGE_H - 30 * mm - i * 10 * mm
            c.bezier(PAGE_W * 0.42, y0, PAGE_W * 0.6, y0 + 14 * mm, PAGE_W * 0.8, y0 - 12 * mm, PAGE_W, y0 + 4 * mm)
        x, y = MARGIN_X, PAGE_H - 30 * mm
        c.setStrokeColor(colors.white)
        c.setFillColor(colors.white)
        c.setLineWidth(1.6)
        c.roundRect(x, y - 2 * mm, 14 * mm, 14 * mm, 3.5 * mm, stroke=1, fill=0)
        c.line(x + 2.5 * mm, y + 5 * mm, x + 11.5 * mm, y + 5 * mm)
        for dx, h in ((4.5, 3.5), (7, 4.5), (9.5, 3)):
            c.line(x + dx * mm, y + 5 * mm, x + dx * mm, y + (5 + h) * mm)
            c.circle(x + dx * mm, y + (5 + h) * mm, 0.9 * mm, stroke=0, fill=1)
        c.setFont("Helvetica-Bold", 17)
        c.drawString(x + 18 * mm, y + 5 * mm, APP_NAME)
        c.setFont("Helvetica", 8.5)
        c.drawString(x + 18 * mm, y + 0.3 * mm, f"Sistema de gestão de microrrede · v{APP_VERSION}")
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, PAGE_H - 62 * mm, "RELATÓRIO TÉCNICO DE CONFIGURAÇÃO DA MICRORREDE")
        c.setFont("Helvetica-Bold", 25)
        name = _plain(meta["name"])
        lines = _wrap(name, 34)[:3]
        for i, ln in enumerate(lines):
            c.drawString(x, PAGE_H - 74 * mm - i * 10 * mm, ln)
        if meta["preliminary"]:
            c.setFillColor(colors.HexColor("#FFF4E0"))
            c.roundRect(PAGE_W - MARGIN_X - 70 * mm, PAGE_H - 22 * mm, 70 * mm, 9 * mm, 2 * mm, stroke=0, fill=1)
            c.setFillColor(WARN)
            c.setFont("Helvetica-Bold", 7.6)
            c.drawCentredString(PAGE_W - MARGIN_X - 35 * mm, PAGE_H - 18.6 * mm, "PRELIMINAR · CONFIGURAÇÃO NÃO ATIVADA")
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.2)
        c.drawString(MARGIN_X, 11 * mm, "Documento gerado localmente pelo SEEDS2. Não constitui certificação, laudo de conformidade "
                                        "normativa nem validação experimental.")
        c.restoreState()

    def page(c, doc):
        c.saveState()
        c.setStrokeColor(TEAL)
        c.setLineWidth(0.8)
        c.line(MARGIN_X, PAGE_H - 13 * mm, PAGE_W - MARGIN_X, PAGE_H - 13 * mm)
        c.setFont("Helvetica-Bold", 7.4)
        c.setFillColor(TEAL)
        c.drawString(MARGIN_X, PAGE_H - 11 * mm, "SEEDS2 · RELATÓRIO TÉCNICO DE CONFIGURAÇÃO")
        c.setFont("Helvetica", 7.4)
        c.setFillColor(MUTED)
        c.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 11 * mm, _plain(meta["name"])[:70] + (" · PRELIMINAR" if meta["preliminary"] else ""))
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.line(MARGIN_X, 15 * mm, PAGE_W - MARGIN_X, 15 * mm)
        c.drawString(MARGIN_X, 11 * mm, f"Revisão {meta['revision']} · impressão digital {meta['fingerprint'][:16]}… · gerado em {meta['generated']}")
        c.restoreState()
    return cover, page


def _wrap(s: str, n: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


# ---------------------------------------------------------------------------------------------- conteúdo
def _yes(b: bool) -> str:
    return "sim" if b else "não"


def _status_para(m: A.Mapping, short: bool = False) -> Paragraph:
    col = {A.REPRESENTED: "#2E8B57", A.INCOMPLETE: "#B06A00", A.INCOMPATIBLE: "#C2364A", A.DISABLED: "#5B6B7C"}[m.status]
    label = SHORT_STATUS[m.status] if short else A.STATUS_LABELS[m.status]
    return P(f"<font color='{col}'><b>{_t(label)}</b></font>", "cell")


def _provenance(eq: dict) -> str:
    k, p = eq["kind"], eq.get("params") or {}
    if k == "pv":
        return "Datasheets do catálogo (config/pv_database.py) e potências declaradas pela instalação"
    if k == "wind":
        c = wind_curve(p.get("reference") or "")
        return c["source_label"] if c else ND
    if k == "battery":
        out = "Datasheet informado pela instalação" if C.battery_physically_registered(eq) else "Datasheet não informado"
        if p.get("model_reference"):
            r = battery_references().get(p["model_reference"])
            out += f"; modelo: {r.category if r else p['model_reference']}"
        return out
    if k == "pemfc":
        if p.get("reference") == C.PEMFC_IMPORT_REF:
            return "Importado do PEMFC ModelLab (pendente de integração científica)"
        return pemfc_references()[PEMFC_REF_KEY].category if p.get("reference") else ND
    return "Parâmetros declarados; presets de CVU são acadêmicos" if p.get("fuel_preset") else "Parâmetros declarados pela instalação"


def _summary(eq: dict) -> str:
    k, p = eq["kind"], eq.get("params") or {}
    if k == "pv":
        s = pv_plant_summary(eq)
        return f"{s['n_arrays']} arranjo(s) · {_num(s['total_kWp'], 2, 'kWp') if (s['n_computed'] or s['n_declared']) else 'potência não determinada'}"
    if k == "wind":
        return f"{p.get('count') or '?'} × {p.get('reference') or ND} · {_num(C.installed_power_kW(eq), 0, 'kW')}"
    if k == "battery":
        e = C.battery_energy_kWh(eq)
        soc = (f" · SOC {_num(p.get('soc_min_pct'), 0)}–{_num(p.get('soc_max_pct'), 0)} %"
               if p.get("soc_min_pct") is not None and p.get("soc_max_pct") is not None else " · limites de SOC não declarados")
        return f"{_num(e, 1, 'kWh') if e is not None else 'energia não declarada'}{soc}"
    if k == "pemfc":
        return f"{p.get('quantity') or '?'} sistema(s) · {_num(C.installed_power_kW(eq), 1, 'kW')} líquidos máx."
    return f"Pmáx {_num(p.get('pmax_kW'), 1, 'kW')} · Pmín {_num(p.get('pmin_kW'), 1, 'kW')}"


def _ref(eq: dict) -> str:
    p = eq.get("params") or {}
    k = eq["kind"]
    if k == "pv":
        refs = sorted({a.get("reference") for a in eq.get("arrays") or [] if a.get("reference")})
        return ", ".join(refs) or "sem módulo identificado"
    if k == "battery":
        txt = " ".join(x for x in (p.get("manufacturer"), p.get("model")) if x)
        return txt or ND
    if k == "pemfc" and p.get("reference") == C.PEMFC_IMPORT_REF:
        dev = (eq.get("imported") or {}).get("device") or {}
        return " ".join(x for x in (dev.get("manufacturer"), dev.get("model")) if x) or dev.get("name") or ND
    if k == "pemfc":
        return "Perfil equivalente SEEDS2 (aproximado)" if p.get("reference") else ND
    if k == "thermal":
        return C.choices("thermal", "dynamic").get(p.get("dynamic")) or ND
    return p.get("reference") or ND


def _content(stored, store, plan: A.SimulationPlan, meta: dict) -> list:
    cfg = stored.config
    inst = cfg["installation"]
    loc = inst.get("location") or {}
    eqs = cfg.get("equipment", [])
    by = {k: [e for e in eqs if e["kind"] == k] for k in ("pv", "wind", "battery", "pemfc", "thermal")}
    W = PAGE_W - 2 * MARGIN_X
    out: list = [NextPageTemplate("page"), PageBreak()]

    # 01 resumo executivo
    out += section(1, "Resumo executivo", "Visão geral")
    tiles = [("Equipamentos", str(len(eqs)), f"{sum(len(e.get('arrays') or []) for e in by['pv'])} arranjo(s) FV"),
             ("FV registrada", _num(sum(pv_plant_summary(e)["total_kWp"] for e in by["pv"]), 1, "kWp") if by["pv"] else "—",
              "potência nominal STC/declarada"),
             ("Armazenamento", _num(sum(C.battery_energy_kWh(e) or 0 for e in by["battery"]), 1, "kWh") if by["battery"] else "—",
              f"{len(by['battery'])} banco(s)"),
             ("Simulação", "pronta" if plan.runnable and not plan.needs_ack else ("com exclusões" if plan.runnable else "bloqueada"),
              f"{len(plan.represented)} representado(s) · {len(plan.excluded)} excluído(s)")]
    out += [kpis(tiles), Spacer(1, 4 * mm)]
    techs = [f"{KIND_LABELS[k]} ({len(v)})" for k, v in by.items() if v]
    pw_rows = []
    for k in ("pv", "wind", "pemfc", "thermal"):
        if by[k]:
            pw_rows.append([KIND_LABELS[k], str(len(by[k])), _num(sum(C.installed_power_kW(e) or 0 for e in by[k]), 2, "kW" if k != "pv" else "kWp"),
                            {"pv": "Σ arranjos (calculada por datasheet + declarada)", "wind": "nominal do catálogo × quantidade",
                             "pemfc": "potência líquida máx. (modelo/declarada)", "thermal": "potência máxima declarada"}[k]])
    if by["battery"]:
        pw_rows.append(["Bateria", str(len(by["battery"])), _num(sum(C.battery_energy_kWh(e) or 0 for e in by["battery"]), 1, "kWh"),
                        "energia nominal (datasheet; senão parametrização do modelo)"])
    out.append(P(f"A microrrede <b>{_t(inst.get('name'))}</b> ({_t(C.NATURE_OPTIONS.get(inst.get('nature'), ND))}; "
                 f"modo declarado: {_t(C.OPERATION_MODE_OPTIONS.get(inst.get('operation_mode'), ND))}) possui "
                 f"{len(eqs)} equipamento(s) registrado(s): {_t(', '.join(techs) or 'nenhum')}. "
                 "Os valores abaixo são nominais registrados no inventário, não resultados de simulação."))
    if pw_rows:
        out.append(table(["Tecnologia", "Equip.", "Capacidade nominal", "Base"], pw_rows, [1.2, 0.5, 1.1, 2.6]))
    out.append(Spacer(1, 3 * mm))
    out.append(note(f"<b>Prontidão para simulação:</b> {len(plan.represented)} unidade(s) representada(s) no EMS, "
                    f"{len(plan.excluded)} excluída(s) e {len([m for m in plan.mappings if m.status == A.DISABLED])} desabilitada(s)."
                    + (" Bloqueios: " + _t("; ".join(plan.blockers)) if plan.blockers else ""),
                    "ok" if plan.runnable and not plan.needs_ack else "warn"))
    if meta["preliminary"]:
        out.append(Spacer(1, 2 * mm))
        out.append(note("<b>Relatório PRELIMINAR:</b> o comissionamento ainda não foi concluído (configuração não ativada).", "warn"))

    # 02 identificação e localização
    out += section(2, "Identificação e localização", "Instalação")
    acc = loc.get("accuracy_m")
    out.append(kv([("Nome da instalação", inst.get("name")), ("Descrição", inst.get("description")),
                   ("Natureza da atividade", C.NATURE_OPTIONS.get(inst.get("nature"))),
                   ("Modo de operação previsto", C.OPERATION_MODE_OPTIONS.get(inst.get("operation_mode"))),
                   ("Identidade da instalação", inst.get("uid")), ("Criada em", _dt(inst.get("created_at"))),
                   ("Comissionamento", "concluído em " + _dt(cfg["commissioning"]["completed_at"]) if cfg["commissioning"].get("completed")
                    else f"em andamento (etapa {cfg['commissioning'].get('step')})"),
                   ("País / estado / cidade", " / ".join(x for x in (loc.get("country"), loc.get("region"), loc.get("city")) if x)),
                   ("Endereço / descrição", loc.get("address")),
                   ("Coordenadas", f"{loc['latitude']:.6f}, {loc['longitude']:.6f}" if loc.get("latitude") is not None else None),
                   ("Origem das coordenadas", C.LOCATION_SOURCES.get(loc.get("source")) + (f" · precisão estimada ±{acc:.0f} m" if acc else "")
                    if loc.get("latitude") is not None else None),
                   ("Fuso horário", loc.get("timezone"))]))

    # 03 inventário
    out += section(3, "Inventário técnico", "Equipamentos registrados")
    rows = []
    for e in eqs:
        rows.append([e.get("tag") or "—", e["name"], KIND_LABELS[e["kind"]], _ref(e), _summary(e),
                     ("habilitado" if e.get("enabled", True) else "desabilitado") + " · " +
                     ("configurado" if C.is_configured(e) else "pendente"), _provenance(e)])
    if rows:
        out.append(table(["TAG", "Equipamento", "Tecnologia", "Fabricante / modelo / referência", "Quantidade e capacidade",
                          "Estado", "Procedência dos dados"], rows, [0.55, 1.15, 0.8, 1.3, 1.3, 0.9, 1.5], bold_first=False))
    else:
        out.append(P("Nenhum equipamento registrado.", "small"))
    if cfg.get("retired"):
        out.append(Spacer(1, 3 * mm))
        out.append(P("<b>Equipamentos retirados (auditoria)</b>", "body"))
        out.append(table(["Equipamento", "Tecnologia", "Retirado em", "Motivo"],
                         [[r["name"], KIND_LABELS.get(r["kind"], r["kind"]), _dt(r.get("retired_at")), r.get("retired_reason") or ND]
                          for r in cfg["retired"]], [1.4, 0.9, 1.0, 2.0]))

    # 04 fotovoltaica
    if by["pv"]:
        out += section(4, "Fotovoltaica", "Usinas e arranjos")
        out.append(P(_t(PV_STC_ASSUMPTIONS), "small"))
        for e in by["pv"]:
            s = pv_plant_summary(e)
            block = [P(f"{_t(e['name'])}{' · TAG ' + _t(e['tag']) if e.get('tag') else ''}", "h2"),
                     kpis([("Potência total registrada", _num(s["total_kWp"], 2, "kWp"), "Σ arranjos"),
                           ("Calculada", _num(s["computed_kWp"], 2, "kWp"), f"{s['n_computed']} arranjo(s) por datasheet"),
                           ("Declarada", _num(s["declared_kWp"], 2, "kWp"), f"{s['n_declared']} arranjo(s) sem módulo"),
                           ("Módulos identificados", str(s["n_modules"]), f"{s['n_arrays']} arranjo(s)")])]
            out.append(KeepTogether(block))
            out.append(Spacer(1, 2.5 * mm))
            arows = []
            for a in e.get("arrays") or []:
                nom = pv_array_nominal(a)
                ms = [m for m in plan.mappings if m.id == a["id"]]
                arows.append([a["name"], {"modulo": "Datasheet", "declarado": "Declarado"}.get(a.get("mode"), "—"),
                              (pv_references().get(a.get("reference")).label if a.get("reference") in pv_references() else
                               ("—" if a.get("mode") == "declarado" else ND)),
                              f"{a['n_series']} × {a['n_parallel']}" if a.get("n_series") and a.get("n_parallel") else "—",
                              _num(nom["P_STC_kW"], 2) if nom else (_num(a.get("declared_kWp"), 2) + " (decl.)"
                                                                   if a.get("declared_kWp") else ND),
                              _num(nom["Voc_V"], 1) if nom else "—", _num(nom["Isc_A"], 2) if nom else "—",
                              _num(nom["Vmp_V"], 1) if nom else "—", _num(nom["Imp_A"], 2) if nom else "—",
                              (f"{_num(a.get('soiling_pct'), 1)}{' (padrão)' if a.get('soiling_default') else ''}"
                               if a.get("mode") == "modulo" else "—"),
                              _status_para(ms[0], short=True) if ms else "—"])
            if arows:
                out.append(table(["Arranjo", "Cadastro", "Módulo", "Ns × Np", "P STC [kWp]", "Voc [V]", "Isc [A]", "Vmp [V]",
                                  "Imp [A]", "Sujeira [%]", "Simulação"],
                                 arows, [0.9, 0.75, 1.25, 0.55, 0.72, 0.58, 0.55, 0.58, 0.55, 0.62, 1.08]))
            for a in e.get("arrays") or []:
                if a.get("mode") == "declarado":
                    out.append(P(f"• {_t(a['name'])}: potência declarada {_num(a.get('declared_kWp'), 2, 'kWp')}; procedência: "
                                 f"{_t(a.get('declared_source') or ND)}. Sem módulo identificado, nenhum parâmetro elétrico é estimado.", "small"))
            out.append(Spacer(1, 3 * mm))
        out.append(note("A usina soma somente potências nominais. Voc, Isc, Vmp e Imp são valores por arranjo e não são somados "
                        "entre arranjos diferentes. Potência registrada ≠ potência simulada: ver seção 09.".replace("≠", "difere da")))

    # 05 eólica
    if by["wind"]:
        out += section(5, "Eólica", "Aerogeradores")
        for e in by["wind"]:
            p = e["params"]
            spec = wind_spec(p.get("reference") or "")
            c = wind_curve(p.get("reference") or "")
            hub = spec.get("hub_height_m") or ", ".join(f"{h:g}" for h in spec.get("hub_height_options_m") or [])
            items = [P(f"{_t(e['name'])}{' · TAG ' + _t(e['tag']) if e.get('tag') else ''}", "h2"),
                     kv([("Aerogerador", p.get("reference")), ("Quantidade", p.get("count")),
                         ("Fabricante / modelo", f"{spec.get('manufacturer', '')} {spec.get('model', '')}".strip() or None),
                         ("Potência nominal unitária", _num(spec.get("rated_power_kw"), 0, "kW") if spec else None),
                         ("Diâmetro do rotor", _num(spec.get("rotor_diameter_m"), 1, "m") if spec.get("rotor_diameter_m") else None),
                         ("Altura do cubo", f"{hub} m" if hub else None), ("Classe IEC", spec.get("wind_class_iec")),
                         ("Velocidades de partida / nominal / corte", " / ".join(_num(spec.get(k), 1, "m/s") if spec.get(k) else ND
                                                                                for k in ("cut_in_mps", "rated_wind_speed_mps", "cut_out_mps"))
                          if spec else None),
                         ("Procedência da curva", (c["source_label"] + f" — {c.get('reference') or ''} ({c.get('document') or ''})") if c else None)])]
            out.append(KeepTogether(items))
            dwg = wind_curve_drawing(p.get("reference") or "", W) if c else None
            if dwg:
                out.append(KeepTogether([Spacer(1, 2 * mm), dwg,
                                         P(f"Curva potência × velocidade do vento do catálogo (pontos originais, densidade de referência "
                                           f"{_num(c['reference_density_kg_m3'], 3, 'kg/m³')}). "
                                           + ("Curva DIGITALIZADA de gráfico: aproximada, não é medição certificada." if c["digitized"]
                                              else "Tabela do fabricante."), "small")]))
            else:
                out.append(P("Curva de potência não disponível no catálogo para esta referência.", "small"))

    # 06 baterias
    if by["battery"]:
        out += section(6, "Baterias", "Armazenamento")
        soc0 = cfg["run_conditions"]["battery_soc0_pct"]
        for e in by["battery"]:
            p = e["params"]
            d = battery_derived(p, C.battery_model_energy_kWh(e))

            def val(key, unit, nd):
                v, basis, how = d[key]
                return _num(v, nd, unit) + (f" (estimativa: {how})" if basis == "derivada" else "") if v is not None else None

            out.append(KeepTogether([P(f"{_t(e['name'])}{' · TAG ' + _t(e['tag']) if e.get('tag') else ''}", "h2"),
                                     kv([("Fabricante / modelo", " ".join(x for x in (p.get("manufacturer"), p.get("model")) if x) or None),
                           ("Tecnologia / química", C.BATTERY_CHEMISTRIES.get(p.get("chemistry"))),
                           ("Energia nominal", val("energy_kWh", "kWh", 2)), ("Capacidade nominal", val("capacity_Ah", "Ah", 1)),
                           ("Tensão nominal", val("voltage_V", "V", 1)), ("Potência nominal", _num(p.get("power_kW"), 1, "kW") if p.get("power_kW") else None),
                           ("Corrente máx. carga / descarga", " / ".join(_num(d[k][0], 1, "A") if d[k][0] is not None else ND
                                                                        for k in ("i_charge_A", "i_discharge_A"))),
                           ("Taxa máx. carga / descarga", " / ".join((_num(d[k][0], 3, "C") + (" (estim.)" if d[k][1] == "derivada" else ""))
                                                                    if d[k][0] is not None else ND for k in ("c_charge", "c_discharge"))),
                           ("Limites operacionais de SOC", f"{_num(p.get('soc_min_pct'), 0)} % – {_num(p.get('soc_max_pct'), 0)} % · "
                                                           f"{C.SOC_LIMIT_SOURCES.get(p.get('soc_limits_source'), ND)}"
                            if p.get("soc_min_pct") is not None and p.get("soc_max_pct") is not None else None),
                           ("Parametrização do modelo científico", (f"{battery_references()[p['model_reference']].label} · Ns {p['model_n_series']} × "
                                                                    f"Np {p['model_n_parallel']} · {_num(C.battery_model_energy_kWh(e), 2, 'kWh')}")
                            if C.battery_model_parametrized(e) and p.get("model_reference") in battery_references() else
                            "não parametrizado (banco registrado fisicamente, não simulável pelo modelo atual)"),
                           ("SOC inicial (condição de rodada)", f"{_num(soc0[e['id']], 0)} %" if e["id"] in soc0 else
                            "não definido — é condição da rodada, não dado do banco")])]))
            for w in d["warnings"]:
                out.append(note(_t(w), "warn"))

    # 07 PEMFC e térmica
    if by["pemfc"] or by["thermal"]:
        out += section(7, "PEMFC e térmica", "Geração despachável")
        for e in by["pemfc"]:
            p = e["params"]
            head = P(_t(e["name"]), "h2")
            if p.get("reference") == C.PEMFC_IMPORT_REF and e.get("imported"):
                imp = e["imported"]
                dev = imp["device"]
                out.append(KeepTogether([head, kv([("Origem", "Dispositivo importado do PEMFC ModelLab"),
                               ("Dispositivo", dev.get("name")), ("Fabricante / modelo", " ".join(x for x in (dev.get("manufacturer"), dev.get("model")) if x) or None),
                               ("Células / área ativa", f"{dev.get('n_cells') or ND} células ({dev.get('n_cells_origin') or ND}) · "
                                                        f"{_num(dev.get('active_area_cm2'), 1, 'cm²') if dev.get('active_area_cm2') else ND}"),
                               ("Arquivo importado", f"{imp.get('filename')} · SHA-256 {imp.get('blob', '')[:16]}… · importado em {_dt(imp.get('imported_at'))}"),
                               ("Sistemas instalados", p.get("quantity")), ("Integração no EMS", imp.get("integration_note"))])]))
                cal = imp.get("calibrations") or []
                if cal:
                    out.append(Spacer(1, 2 * mm))
                    out.append(table(["Perfil", "Estado do perfil", "Validação independente", "RMSE [mV/célula]", "Domínio T [K]"],
                                     [[c["profile_id"], c["status_label"], c["validation_label"],
                                       _num(c["rmse_V"] * 1000, 2) if c.get("rmse_V") is not None else ND,
                                       " – ".join(_num(x, 2) for x in c["domain"]["temperature_K"]) if c["domain"].get("temperature_K") else ND]
                                      for c in cal], [1.3, 1.8, 1.4, 0.8, 0.8]))
            else:
                r = pemfc_references()[PEMFC_REF_KEY]
                out.append(KeepTogether([head, kv([("Origem", "Perfil equivalente do catálogo SEEDS2"), ("Perfil", r.label), ("Categoria", r.category),
                               ("Procedência", r.provenance), ("Sistemas instalados", p.get("quantity")),
                               ("Potência líquida máx. total", _num(C.installed_power_kW(e), 1, "kW")),
                               ("Base do envelope no EMS", C.PEMFC_POWER_BASIS.get(p.get("power_basis")))]),
                                         P("Perfil APROXIMADO: não é equipamento validado experimentalmente nesta instalação.", "small")]))
        for e in by["thermal"]:
            p = e["params"]
            out.append(KeepTogether([P(_t(e["name"]), "h2"), kv([("Dinâmica", C.choices("thermal", "dynamic").get(p.get("dynamic"))),
                           ("Potência máxima / mínima técnica", f"{_num(p.get('pmax_kW'), 1, 'kW')} / {_num(p.get('pmin_kW'), 1, 'kW')}"),
                           ("Rampa máxima", _num(p.get("ramp_kW_min"), 1, "kW/min") if p.get("ramp_kW_min") else "sem limite declarado"),
                           ("CVU", _num(p.get("cvu_rs_MWh"), 0, "R$/MWh") + (f" (preset ACADÊMICO «{p['fuel_preset']}»)" if p.get("fuel_preset") else "")),
                           ("Custo de partida", _num(p.get("startup_cost_rs"), 2, "R$"))])]))

    # 08 balanço energético
    out += section(8, "Modelo de balanço energético", "Esquema lógico")
    out.append(balance_drawing(cfg, plan, W))
    out.append(Spacer(1, 2 * mm))
    out.append(P("Esquema LÓGICO: fontes e armazenamento → balanço energético agregado (soma de potências a cada passo de 1 min) → "
                 "atendimento da demanda. <b>Não é um esquema unifilar</b>: não representa barramentos, tensões, inversores ou "
                 "conversores individuais, controle grid-following/grid-forming, proteções, estabilidade nem conexões físicas."))
    grid = (cfg.get("energy_balance") or {}).get("grid_connection")
    out.append(kv([("Conexão com a rede (declarada)", C.GRID_CONNECTION_OPTIONS.get(grid))]))
    if grid == "conectada":
        out.append(note("O EMS atual não otimiza importação/exportação nem tarifas; o déficit do EMS não equivale a compra física "
                        "de energia da rede.", "warn"))
    if (cfg.get("legacy") or {}).get("topology_v1"):
        out.append(P("A topologia declarada na versão anterior (barramento/acoplamentos) foi substituída por este modelo lógico e é "
                     "mantida apenas para rastreabilidade; não representa conexões verificadas.", "small"))

    # 09 compatibilidade
    out += section(9, "Compatibilidade com a simulação", "EMS existente")
    out.append(P(f"FV: {_num(plan.pv_installed_kWp, 2, 'kWp')} registrados nas usinas habilitadas, dos quais "
                 f"{_num(plan.pv_represented_kWp, 2, 'kWp')} representáveis pelo EMS atual (potência nominal; não é produção)."))
    if plan.mappings:
        out.append(table(["Unidade", "Tecnologia", "Estado", "Motivo / observação"],
                         [[m.name, KIND_LABELS[m.kind], _status_para(m), m.reason or "—"] for m in plan.mappings],
                         [1.6, 0.9, 1.1, 3.4]))
    for b in plan.blockers:
        out.append(note("<b>Bloqueio:</b> " + _t(b), "bad"))
    for w in plan.warnings:
        out.append(note(_t(w), "warn"))

    # 10 demanda
    out += section(10, "Demanda e dados de entrada", "Dados")
    dem = cfg["demand"]
    csv = dem.get("csv") or {}
    out.append(kv([("Fonte da demanda", C.DEMAND_SOURCES.get(dem.get("source"))),
                   ("Procedência declarada", C.PROVENANCE_KINDS.get(dem.get("provenance"))),
                   ("Parâmetros", {"walkforward": " · ".join(f"{k}: {v}" for k, v in (dem.get("walkforward") or {}).items()),
                                   "copel": " · ".join(f"{k}: {v}" for k, v in (dem.get("copel") or {}).items()),
                                   "csv": f"{csv.get('filename')} · SHA-256 {str(csv.get('blob', ''))[:16]}… · janela {csv.get('start_min')}+{csv.get('duration_min')} min"}
                    .get(dem.get("source"))),
                   ("Fuso dos carimbos de tempo", dem.get("timezone")),
                   ("Convenções", "potência ativa consumida positiva, em kW; grade de 1 min do EMS"),
                   ("Clima para solar/eólica", C.CLIMATE_SOURCES.get((cfg.get("climate") or {}).get("source")))]))

    # 11 rastreabilidade
    out += section(11, "Rastreabilidade e alcance", "Procedência")
    out.append(kv([("Aplicação", f"{APP_NAME} v{APP_VERSION} · Energy MultiModel V1.6 (motores científicos inalterados)"),
                   ("Revisão da configuração", str(stored.revision)), ("Salva em", _dt(stored.saved_at)),
                   ("Impressão digital SHA-256", stored.fingerprint), ("Esquema do documento", f"v{cfg.get('schema_version')}"),
                   ("Gerado em", meta["generated"]),
                   ("Catálogos", "config/pv_database.py · config/wind_turbine_database.py · models/battery_model.py · "
                                 "h2_pemfc (perfil EQUIVALENT_65KW_HORIZON_CONSTRAINED) · config/thermal_database.py"),
                   ("Migrações aplicadas", "; ".join(f"v{m['from']} para v{m['to']} em {_dt(m['at'])}" for m in cfg.get("migrations") or []) or "nenhuma")]))
    out.append(Spacer(1, 3 * mm))
    out.append(note("<b>Declaração de alcance.</b> Este relatório descreve a configuração registrada no SEEDS2 e a compatibilidade com "
                    "os modelos computacionais existentes. Não constitui certificação, laudo de conformidade normativa, projeto "
                    "elétrico executivo nem validação experimental. Valores calculados são estimativas nominais com as hipóteses "
                    "indicadas; dados não informados aparecem como “Não declarado”."))
    return out


def report_filename(config: dict) -> str:
    from seeds2.microgrid.store import backup_filename

    return backup_filename(config).replace("seeds2_", "seeds2_relatorio_").replace(".seeds2backup.zip", ".pdf")


def build_report(stored, store=None, *, generated: datetime | None = None) -> bytes:
    """PDF (bytes) da configuração salva ``stored`` (``store.Stored``)."""
    cfg = stored.config
    plan = A.build_plan(cfg, revision=stored.revision, fingerprint=stored.fingerprint)
    gen = (generated or datetime.now()).strftime("%d/%m/%Y %H:%M")
    meta = {"name": cfg["installation"].get("name") or "Microrrede", "revision": stored.revision,
            "fingerprint": stored.fingerprint, "generated": gen,
            "preliminary": not cfg.get("commissioning", {}).get("completed")}
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=MARGIN_TOP,
                          bottomMargin=MARGIN_BOTTOM, title=f"Relatório técnico de configuração — {_plain(meta['name'])}",
                          author=f"{APP_NAME} v{APP_VERSION}", subject="Relatório técnico de configuração da microrrede",
                          creator=f"{APP_NAME} {APP_VERSION}")
    cover, page = _decorations(meta)
    frame_cover = Frame(MARGIN_X, MARGIN_BOTTOM, PAGE_W - 2 * MARGIN_X, PAGE_H - 108 * mm - MARGIN_BOTTOM - 8 * mm, id="cover")
    frame = Frame(MARGIN_X, MARGIN_BOTTOM, PAGE_W - 2 * MARGIN_X, PAGE_H - MARGIN_TOP - MARGIN_BOTTOM, id="body")
    doc.addPageTemplates([PageTemplate("cover", [frame_cover], onPage=cover), PageTemplate("page", [frame], onPage=page)])
    inst = cfg["installation"]
    cover_story = [
        Spacer(1, 4 * mm),
        kv([("Instalação", inst.get("name")), ("Natureza", C.NATURE_OPTIONS.get(inst.get("nature"))),
            ("Localização", ", ".join(x for x in ((inst.get("location") or {}).get(k) for k in ("city", "region", "country")) if x) or None),
            ("Data de geração", gen), ("Revisão da configuração", str(stored.revision)),
            ("Impressão digital (SHA-256)", stored.fingerprint), ("Aplicação", f"{APP_NAME} v{APP_VERSION}"),
            ("Estado", "PRELIMINAR — comissionamento não concluído" if meta["preliminary"] else "Configuração ativada")]),
        Spacer(1, 6 * mm),
        P("<b>Conteúdo</b>", "body"),
        P("01 Resumo executivo · 02 Identificação e localização · 03 Inventário técnico · 04 Fotovoltaica · 05 Eólica · "
          "06 Baterias · 07 PEMFC e térmica · 08 Modelo de balanço energético · 09 Compatibilidade com a simulação · "
          "10 Demanda e dados · 11 Rastreabilidade e alcance (seções sem equipamentos registrados são omitidas).", "small"),
    ]
    doc.build(cover_story + _content(stored, store, plan, meta), canvasmaker=_NumberedCanvas)
    return buf.getvalue()
