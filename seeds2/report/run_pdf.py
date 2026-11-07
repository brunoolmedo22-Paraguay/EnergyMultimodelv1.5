"""Relatório científico PDF de UMA rodada (Piso 2D-B, Hito C) — a partir do ``RunDossier``, sem recalcular.

Documento técnico autônomo (não é captura da interface): capa, resumo executivo, configuração, condições iniciais,
previsões e entradas, estratégia e metodologia, resultados energéticos, armazenamento e hidrogênio, discussão
limitada a fatos, procedência e rastreabilidade, limitações. Rodada falha/interrompida → relatório DIAGNÓSTICO (sem
tabelas nem gráficos de resultados inexistentes).

Tipografia: DejaVu Sans (TTF embarcado no matplotlib, subconjunto embutido no PDF — Unicode completo: H₂, ±, →, ⁻⁹).
Figuras: VETORIAIS — cada figura é desenhada pelo matplotlib (``figures.render(..., "pdf")``) a partir da MESMA figura
Plotly da interface e sobreposta, com ``pypdf``, à posição reservada na página (texto pesquisável, zoom sem perda).
Todo texto vindo de cenários/pacotes é escapado (marcação XML do ReportLab) — nenhuma marcação do usuário é
interpretada.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)

from seeds2 import APP_NAME, APP_VERSION
from seeds2.microgrid import config as C
from seeds2.microgrid.references import KIND_LABELS
from seeds2.operation import contracts
from seeds2.operation import forecasts as F
from seeds2.operation import initialization as I
from seeds2.operation import mission as M
from seeds2.operation import strategy as SG

from . import dossier as D
from . import figures as FG

PAGE_W, PAGE_H = A4
MX, MT, MB = 18 * mm, 22 * mm, 20 * mm
TEXT_W = PAGE_W - 2 * MX
INK = colors.HexColor("#17212B")
MUTED = colors.HexColor("#5B6673")
ACCENT = colors.HexColor("#0E5E66")
RULE = colors.HexColor("#C9D1D9")
HEAD_BG = colors.HexColor("#E8EEF1")
ZEBRA = colors.HexColor("#F6F8FA")
WARN_BG = colors.HexColor("#FFF6E5")
BAD_BG = colors.HexColor("#FDECEC")
INFO_BG = colors.HexColor("#EEF4F7")
ND = "não disponível"
_FONT_DONE = False


def _fonts() -> None:
    global _FONT_DONE
    if _FONT_DONE:
        return
    import matplotlib

    base = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    for name, f in (("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"), ("DV-I", "DejaVuSans-Oblique.ttf"),
                    ("DV-BI", "DejaVuSans-BoldOblique.ttf")):
        pdfmetrics.registerFont(TTFont(name, os.path.join(base, f)))
    pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")
    _FONT_DONE = True


# ====================================================================== texto / números
_CTRL = __import__("re").compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def t(s: Any) -> str:
    """Texto NÃO confiável → markup seguro (escapado; controles → U+FFFD; quebras de linha preservadas)."""
    return xml_escape(_CTRL.sub("\ufffd", "" if s is None else str(s))).replace("\n", "<br/>")


_SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def num(x: Any, d: int = 2, unit: str = "") -> str:
    """Número em pt-BR; valores muito pequenos (|x| < 10⁻³) em notação científica — nunca arredondados para zero."""
    if x is None or isinstance(x, bool) or not D.is_number(x):
        return ND if x is None else str(x)
    if isinstance(x, int):
        s = f"{x:,d}".replace(",", ".")
        return f"{s} {unit}".strip()
    v = float(x)
    if v != 0 and abs(v) < 1e-3:
        m, e = f"{v:.2e}".split("e")
        s = f"{m.replace('.', ',')} × 10{str(int(e)).translate(_SUP)}"
    else:
        s = f"{v:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"{s} {unit}".strip()


def pct_from_fraction(x: Any, d: int = 1) -> str:
    return num(100.0 * float(x), d, "%") if D.is_number(x) else ND


def when(iso: Any) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M:%S UTC")
    except ValueError:
        return str(iso)


# ====================================================================== estilos e blocos
def _styles() -> dict:
    b = dict(fontName="DV", textColor=INK, fontSize=8.8, leading=12.4)
    return {
        "body": ParagraphStyle("body", **b, spaceAfter=4),
        "small": ParagraphStyle("small", **{**b, "fontSize": 7.4, "leading": 9.8, "textColor": MUTED}, spaceAfter=3),
        "cell": ParagraphStyle("cell", **{**b, "fontSize": 7.4, "leading": 9.3}),
        "mono": ParagraphStyle("mono", **{**b, "fontSize": 6.8, "leading": 8.6}),
        "th": ParagraphStyle("th", **{**b, "fontSize": 7.2, "leading": 9, "fontName": "DV-B"}),
        "h1": ParagraphStyle("h1", **{**b, "fontSize": 13.5, "leading": 17, "fontName": "DV-B"}, spaceBefore=2, spaceAfter=2,
                             keepWithNext=1),
        "h2": ParagraphStyle("h2", **{**b, "fontSize": 9.6, "leading": 12.4, "fontName": "DV-B", "textColor": ACCENT},
                             spaceBefore=7, spaceAfter=3, keepWithNext=1),
        "kick": ParagraphStyle("kick", **{**b, "fontSize": 7, "leading": 9, "fontName": "DV-B", "textColor": ACCENT},
                               keepWithNext=1),
        "cap": ParagraphStyle("cap", **{**b, "fontSize": 7.4, "leading": 9.8, "textColor": MUTED}, spaceBefore=2, spaceAfter=8),
        "kv": ParagraphStyle("kv", **{**b, "fontSize": 12, "leading": 14.5, "fontName": "DV-B"}),
        "kk": ParagraphStyle("kk", **{**b, "fontSize": 6.6, "leading": 8.4, "fontName": "DV-B", "textColor": MUTED}),
        "kn": ParagraphStyle("kn", **{**b, "fontSize": 6.8, "leading": 8.6, "textColor": MUTED}),
        "bullet": ParagraphStyle("bullet", **b, leftIndent=10, bulletIndent=2, spaceAfter=2.5, bulletFontName="DV"),
    }


S: dict = {}


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def section(n: int, title: str, kicker: str = "") -> list:
    return [CondPageBreak(42 * mm), Spacer(1, 3 * mm), P(f"SEÇÃO {n:02d}" + (f" · {t(kicker).upper()}" if kicker else ""), "kick"),
            P(t(title), "h1"), _rule(), Spacer(1, 2.5 * mm)]


def _rule(color=ACCENT, w=0.9) -> Table:
    r = Table([[""]], colWidths=[TEXT_W], rowHeights=[0.1])
    r.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), w, color)]))
    return r


def table(head: list[str], rows: list[list], widths: list[float], *, mono_cols: tuple = (), align_right: tuple = ()) -> Table:
    tot = sum(widths)
    cw = [TEXT_W * w / tot for w in widths]
    data = [[P(t(h), "th") for h in head]]
    for r in rows:
        data.append([c if isinstance(c, Flowable) else P(t(c) if c is not None else "—", "mono" if i in mono_cols else "cell")
                     for i, c in enumerate(r)])
    tb = Table(data, colWidths=cw, repeatRows=1, hAlign="LEFT")
    style = [("BACKGROUND", (0, 0), (-1, 0), HEAD_BG), ("LINEBELOW", (0, 0), (-1, 0), 0.6, ACCENT),
             ("LINEBELOW", (0, -1), (-1, -1), 0.4, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 3.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
             ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    for c in align_right:
        style.append(("ALIGN", (c, 1), (c, -1), "RIGHT"))
    tb.setStyle(TableStyle(style))
    return tb


def kv(rows: list[tuple], widths=(0.33, 0.67), *, mono: bool = False) -> Table:
    data = [[P(t(a), "th"), b if isinstance(b, Flowable) else P(t(b) if b not in (None, "") else "—", "mono" if mono else "cell")]
            for a, b in rows]
    tb = Table(data, colWidths=[TEXT_W * widths[0], TEXT_W * widths[1]], hAlign="LEFT")
    tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return tb


def note(text: str, tone: str = "info") -> Table:
    bg = {"info": INFO_BG, "warn": WARN_BG, "bad": BAD_BG}[tone]
    bar = {"info": ACCENT, "warn": colors.HexColor("#B06A00"), "bad": colors.HexColor("#B42335")}[tone]
    tb = Table([[P(text, "body")]], colWidths=[TEXT_W], hAlign="LEFT")
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 2.2, bar),
                            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return tb


def kpis(items: list[tuple[str, str, str]]) -> Table:
    cells = [[P(t(k).upper(), "kk"), P(t(v), "kv"), P(t(n), "kn")] for k, v, n in items]
    per = 4
    rows = []
    for i in range(0, len(cells), per):
        chunk = cells[i:i + per] + [[""]] * (per - len(cells[i:i + per]))
        rows.append(chunk)
    tb = Table(rows, colWidths=[TEXT_W / per] * per, hAlign="LEFT")
    tb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, RULE), ("INNERGRID", (0, 0), (-1, -1), 0.4, RULE),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return tb


def bullets(items: list[str]) -> list:
    return [Paragraph(x, S["bullet"], bulletText="•") for x in items]


class FigureSlot(Flowable):
    """Espaço reservado para uma figura vetorial; registra página e posição absolutas no momento do desenho."""

    def __init__(self, spec: FG.FigureSpec, registry: list):
        super().__init__()
        self.spec = spec
        w, h = FG.size_mm(spec)
        self.width, self.height = w * mm, h * mm
        self.registry = registry

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        x, y = self.canv.absolutePosition(0, 0)
        self.registry.append((self.canv.getPageNumber(), x, y, self.spec))


def figure_block(spec: FG.FigureSpec, n: int, registry: list) -> KeepTogether:
    cap = P(f"<b>Figura {n}.</b> {t(spec.title)} — {t(spec.description)} Unidade: {t(spec.units)}. "
            f"Fonte: {t(', '.join(s.split(':')[0] + (':' + s.split(':')[1] if s.startswith('previsao:') else '') for s in spec.data_sources))}.",
            "cap")
    return KeepTogether([FigureSlot(spec, registry), cap])


# ====================================================================== página
class _NumberedCanvas(rl_canvas.Canvas):
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
                self.setFont("DV", 7)
                self.setFillColor(MUTED)
                self.drawRightString(PAGE_W - MX, 11 * mm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


def _clip(s: str, n: int) -> str:
    s = _CTRL.sub("\ufffd", s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _decor(meta: dict):
    def cover(c, doc):
        c.saveState()
        c.setFillColor(ACCENT)
        c.rect(0, PAGE_H - 6 * mm, PAGE_W, 6 * mm, stroke=0, fill=1)
        c.setFillColor(INK)
        c.setFont("DV-B", 15)
        c.drawString(MX, PAGE_H - 26 * mm, APP_NAME)
        c.setFont("DV", 7.6)
        c.setFillColor(MUTED)
        c.drawString(MX, PAGE_H - 31 * mm, "Plataforma científica de modelagem, operação experimental e otimização de microrredes")
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(MX, 26 * mm, PAGE_W - MX, 26 * mm)
        c.setFont("DV", 6.9)
        c.setFillColor(MUTED)
        y = 21 * mm
        import textwrap

        for line in textwrap.wrap(D.DERIVED_NOTE, 125):
            c.drawString(MX, y, line)
            y -= 3.4 * mm
        c.restoreState()

    def page(c, doc):
        c.saveState()
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(MX, PAGE_H - 13 * mm, PAGE_W - MX, PAGE_H - 13 * mm)
        c.setFont("DV-B", 7)
        c.setFillColor(ACCENT)
        c.drawString(MX, PAGE_H - 11 * mm, meta["header"])
        c.setFont("DV", 7)
        c.setFillColor(MUTED)
        c.drawRightString(PAGE_W - MX, PAGE_H - 11 * mm, _clip(meta["right"], 70))
        c.line(MX, 15 * mm, PAGE_W - MX, 15 * mm)
        c.drawString(MX, 11 * mm, _clip(f"Rodada {meta['run']} · gerado em {meta['generated']} · {APP_NAME} {APP_VERSION}", 105))
        c.restoreState()
    return cover, page


# ====================================================================== conteúdo
def _cover(d: D.RunDossier, generated_at: str) -> list:
    out = [Spacer(1, 40 * mm)]
    title = "Relatório de Simulação de Microrrede" if d.concluded else "Relatório Diagnóstico de Rodada"
    out.append(P(f"SEEDS2 — {title}".upper(), "kick"))
    out.append(Spacer(1, 3 * mm))
    out.append(Paragraph(t(d.microgrid.get("name") or "Microrrede"), ParagraphStyle(
        "cv", fontName="DV-B", fontSize=24, leading=29, textColor=INK)))
    out.append(Spacer(1, 2 * mm))
    out.append(Paragraph(f"Cenário <b>{t(d.scenario_name)}</b> · versão {d.run.scenario_version}", ParagraphStyle(
        "cv2", fontName="DV", fontSize=12, leading=16, textColor=INK)))
    out.append(Spacer(1, 10 * mm))
    if not d.concluded:
        out += [note(f"<b>Rodada {t(d.state_label.lower())}.</b> Este documento é um diagnóstico de procedência e erro: "
                     "a rodada não produziu resultados e nenhum indicador, tabela ou gráfico de resultado é apresentado.",
                     "bad"), Spacer(1, 6 * mm)]
    rows = [("Microrrede de origem", f"{d.microgrid.get('name')} · {d.run.microgrid_uid}"),
            ("Cenário", f"{d.scenario_name} · {d.run.scenario_uid}"),
            ("Versão do cenário", f"{d.run.scenario_version} · impressão digital {d.run.scenario_fingerprint[:16]}…"),
            ("Rodada", d.run_uid), ("Estado da rodada", d.state_label),
            ("Execução", f"{when(d.run.created_at)} → {when(d.run.finished_at)}"),
            ("Software da rodada", d.software.get("app") or ND),
            ("Origem dos dados deste relatório", D.ORIGIN_LABELS[d.kind]),
            ("Relatório gerado em", f"{when(generated_at)} · {APP_NAME} {APP_VERSION}")]
    out.append(kv(rows, (0.3, 0.7)))
    if d.kind == D.ARCHIVED:
        out += [Spacer(1, 4 * mm), note("Os resultados foram produzidos na instalação de ORIGEM e apenas consultados nesta "
                                        "instalação a partir do estudo arquivado. Gerar este relatório não executou o EMS.")]
    return out


def _executive(d: D.RunDossier) -> list:
    s = d.summary
    out = section(1, "Resumo executivo", "indicadores persistidos")
    tiles = [("Custo total", f"R$ {num(s.get('custo_total_rs'), 2)}" if D.is_number(s.get("custo_total_rs")) else ND,
              "função objetivo do EMS V1.6"),
             ("Energia demandada", num(s.get("energia_demanda_kWh"), 2, "kWh"), "na janela da missão"),
             ("Energia atendida", num(s.get("energia_atendida_kWh"), 2, "kWh"), "demandada − não atendida"),
             ("Não atendida", num(s.get("energia_nao_atendida_kWh"), 3, "kWh"), "déficit"),
             ("Excedente", num(s.get("energia_excedente_kWh"), 3, "kWh"), "vertido (despachável + renovável)"),
             ("H₂ (EMS)", num(s.get("h2_kg"), 3, "kg") if s.get("h2_kg") is not None else ND, "estimativa do EMS"),
             ("SOC final", "; ".join(pct_from_fraction(v) for v in (s.get("soc_final") or {}).values()) or ND,
              "fração gravada × 100"),
             ("Algoritmo", f"{s.get('algoritmo') or ND} · N = {s.get('N', ND)}",
              f"{s.get('passos', ND)} passos de {num(s.get('Ts_s'), 0, 's')}")]
    out += [kpis(tiles), Spacer(1, 3 * mm)]
    mis = d.mission
    out.append(P(f"Missão de <b>{t(mis.get('duration_min'))} min</b> a partir de {t(mis.get('start_wall'))} "
                 f"({t(M.tz_label(d.timezone))}; UTC {t(mis.get('start_utc'))}), discretizada pelo motor em "
                 f"{t(s.get('passos'))} instantes com passo de {num(s.get('Ts_s'), 0, 's')}. Todos os valores desta seção "
                 "são lidos do resumo persistido da rodada (<i>StoredRun.summary</i>); nenhum foi recalculado."))
    rows = []
    for ind in D.indicators(d):
        if ind.key.startswith(("energia_por_fonte", "custo_por_fonte", "rel.pct")):
            continue
        v = ind.value
        shown = (pct_from_fraction(v) + f" (fração {num(v, 4)})") if ind.unit.startswith("fração") else \
            (num(int(v)) if isinstance(v, float) and D.is_number(v) and v.is_integer() and abs(v) < 1e12 else
             num(v, 4) if D.is_number(v) else (str(v) if v is not None else ND))
        rows.append([ind.label, shown, ind.unit if not ind.unit.startswith("fração") else "%", ind.key])
    out.append(table(["Indicador", "Valor", "Unidade", "Campo persistido"], rows, [2.4, 1.5, 0.7, 2.4],
                     mono_cols=(3,), align_right=(1,)))
    return out


def _equipment_text(e: dict) -> str:
    ref = e["reference"]
    k = e["kind"]
    parts = []
    if k == "pv":
        parts.append(f"{ref.get('arrays') or 0} arranjo(s); potência nominal registrada {num(ref.get('nominal_kW'), 2, 'kWp')}")
    elif k == "wind":
        parts.append(f"{ref.get('count') or '?'} turbina(s) · {ref.get('reference') or 'referência não declarada'}; "
                     f"nominal {num(ref.get('nominal_kW'), 1, 'kW')}")
    elif k == "battery":
        parts.append(f"energia nominal {num(ref.get('energy_kWh'), 2, 'kWh')}; limites de SOC "
                     f"{num(ref.get('soc_min_pct'), 0)}–{num(ref.get('soc_max_pct'), 0)} % (origem: {ref.get('soc_limits_source')})")
    elif k == "pemfc":
        parts.append(f"{ref.get('quantity') or '?'} unidade(s) × {num(ref.get('unit_max_kW'), 1, 'kW')} = "
                     f"{num(ref.get('nominal_kW'), 1, 'kW')} (potência líquida); referência {ref.get('reference') or ND}")
    elif k == "thermal":
        parts.append(f"Pmín {num(ref.get('pmin_kW'), 1, 'kW')} · Pmáx {num(ref.get('pmax_kW'), 1, 'kW')}")
    return "; ".join(parts)


def _configuration(d: D.RunDossier, n: int) -> list:
    inv = d.inventory or {}
    inst = inv.get("installation") or {}
    out = section(n, "Configuração da microrrede", f"inventário · revisão {d.run.config_revision}")
    out.append(P(f"Equipamentos da <b>revisão {d.run.config_revision}</b> do inventário (impressão digital "
                 f"<font name='DV' size='7'>{t(d.run.config_fingerprint)}</font>), referenciada pela versão executada do "
                 f"cenário. Natureza declarada: {t(C.NATURE_OPTIONS.get(inst.get('nature'), inst.get('nature') or ND))}; "
                 f"modo de operação: {t(C.OPERATION_MODE_OPTIONS.get(inst.get('operation_mode'), inst.get('operation_mode') or ND))}. "
                 "Potências são NOMINAIS registradas no inventário (não resultados); a disponibilidade é uma condição "
                 "da rodada e não altera a presença física do equipamento na instalação."))
    rows = [[f"{e['name']}" + (f" ({e['tag']})" if e.get("tag") else ""), KIND_LABELS.get(e["kind"], e["kind"]),
             _equipment_text(e), e["availability"] or "não definido", e["situation"] + (f" — {e['situation_reason']}" if
                                                                                         e.get("situation_reason") else "")]
            for e in d.equipment()]
    out.append(table(["Equipamento", "Tecnologia", "Características registradas", "Disponibilidade", "Situação na rodada"],
                     rows, [1.4, 0.95, 2.45, 1.25, 1.6]))
    present = {e["kind"] for e in d.equipment()}
    absent = [KIND_LABELS[k] for k in ("pv", "wind", "battery", "pemfc", "thermal") if k not in present]
    if absent:
        out.append(P(f"Tecnologias sem equipamento registrado nesta revisão: {t(', '.join(absent))}. "
                     "Nenhuma série é apresentada para elas.", "small"))
    eng = (d.run.outcome or {}).get("effective_engine") or {}
    if eng:
        out.append(P("Configuração efetiva do motor registrada na conclusão da rodada", "h2"))
        bat = eng.get("bateria") or {}
        rows = [("Fontes despacháveis (ordem do motor)", ", ".join(f"{D.source_label(a)} ({b})" for a, b in
                                                                   zip(eng.get("nomes") or [], eng.get("tipos") or []))),
                ("Unidades instaladas por fonte", ", ".join(f"{D.source_label(a)}: {b}" for a, b in
                                                             zip(eng.get("nomes") or [], eng.get("n_unid_inst") or []))),
                ("Potência de base S_base", num(eng.get("S_base_kW"), 3, "kW"))]
        if bat:
            rows.append(("Bateria agregada (motor)", f"E = {num(bat.get('E_kWh'), 3, 'kWh')}; SOC_ini {pct_from_fraction(bat.get('SOC_ini'))}; "
                                                     f"limites {pct_from_fraction(bat.get('SOC_min'))}–{pct_from_fraction(bat.get('SOC_max'))}; "
                                                     f"tolerância do SOC-alvo ±{num(bat.get('soc_alvo_tol'), 2)}"))
        out.append(kv(rows))
    return out


def _rule_label(k: str) -> str:
    return {"battery": "Bateria", "fc": "H₂ / PEMFC", "thermal": "Térmica"}.get(k, k)


def _initial(d: D.RunDossier, n: int) -> list:
    out = section(n, "Condições iniciais", "estado declarado no cenário")
    rows = []
    for e in d.equipment():
        st = e["state"]
        k = e["kind"]
        states = I.THERMAL_STATES if k == "thermal" else I.DISPATCH_STATES
        rows.append([e["name"], KIND_LABELS.get(k, k), e["availability"] or "não definido",
                     states.get(st.get("state"), st.get("state")) if k in ("pemfc", "thermal") else "não aplicável",
                     num(st.get("soc0_pct"), 1, "%") if k == "battery" else "não aplicável",
                     num(st.get("power_kW"), 2, "kW") if k in ("pemfc", "thermal") else "não aplicável",
                     (str(st.get("units_on")) if st.get("units_on") is not None else ND) if k == "pemfc" else "não aplicável"])
    out.append(table(["Equipamento", "Tipo", "Disponibilidade", "Estado inicial", "SOC inicial", "Potência inicial",
                      "Unidades ativas"], rows, [1.4, 0.95, 1.25, 0.9, 0.8, 0.9, 0.8]))
    ei = d.manifest.get("engine_inputs") or {}
    rule = ei.get("engine_initial_state_rule") or {}
    chk = d.engine_check_items()
    if rule or chk:
        out.append(P("Representabilidade no motor", "h2"))
        out.append(P("Regras de estado inicial do EMS V1.6 registradas no manifesto e verificação do contrato efetivo do "
                     "motor antes do otimizador:", "small"))
        out += bullets([f"<b>{t(_rule_label(k))}:</b> {t(v)}" for k, v in rule.items()]
                       + [f"[{t(i.get('level'))}] {t(i.get('message'))}" for i in chk])
    return out


def _forecasts(d: D.RunDossier, n: int, figs: list, reg: list, fig_no: list) -> list:
    out = section(n, "Previsões e dados de entrada", "procedência das séries")
    fc = d.forecasts()
    rows = []
    for slot, e in sorted(fc.items(), key=lambda kv: kv[0] != "demand"):
        rows.append([contracts.FORECAST_SLOTS.get(slot, slot),
                     f"{contracts.FORECAST_SOURCE_TYPES.get(e.get('source_type'), e.get('source_type'))} · {e.get('label') or ''}",
                     C.PROVENANCE_KINDS.get(e.get("provenance"), e.get("provenance")),
                     f"{e.get('t0')} → {e.get('t_end')}",
                     f"{e.get('n_points')} pontos · passo {num(e.get('step_s'), 0, 's')}",
                     e.get("timezone") or "não declarado",
                     ", ".join(f"{F.VARIABLES[v].short} [{F.VARIABLES[v].unit}]" for v in e.get("variables") or [] if v in F.VARIABLES)])
    if rows:
        out.append(table(["Série", "Fonte", "Procedência", "Período original (relógio local)", "Resolução", "Fuso",
                          "Variáveis [unidade]"], rows, [0.9, 1.4, 1.3, 1.5, 0.9, 0.9, 1.3]))
        out.append(P("Procedência conforme declarada no cenário. Perfis sintéticos e conjuntos de referência NÃO são "
                     "medições desta instalação; procedência 'não declarada' é apresentada como tal.", "small"))
    else:
        out.append(P("O cenário não declara previsões.", "small"))
    mis = d.mission
    out.append(P("Período utilizado na missão e transformação para a grade do motor", "h2"))
    out.append(kv([("Janela (relógio de parede)", f"{mis.get('start_wall')} · {M.tz_label(d.timezone)} · {mis.get('duration_min')} min"),
                   ("Janela (UTC)", f"{mis.get('start_utc')} → {mis.get('end_utc')}"),
                   ("Grade do motor", f"{mis.get('n_steps')} instantes · passo {mis.get('step_s')} s (fixo no runtime V1.6)"),
                   ("Relógio não declarado", "declarado pelo usuário: mesmo relógio" if mis.get("undeclared_clock") else "não se aplica")]))
    res = (d.manifest.get("engine_inputs") or {}).get("resampling") or {}
    if res:
        rows = [[F.VARIABLES[k].label if k in F.VARIABLES else k, v.get("slot"), v.get("method"),
                 f"{v.get('exact')} / {v.get('interpolated')}", num(v.get("original_step_s"), 0, "s")] for k, v in res.items()]
        out.append(Spacer(1, 2 * mm))
        out.append(table(["Variável", "Série", "Conversão para a grade de 1 min (registrada)", "Exatos / interpolados",
                          "Passo original"], rows, [1.6, 0.6, 2.6, 0.9, 0.8]))
    tr = [(slot, x) for slot, e in fc.items() for x in (e.get("transforms") or [])]
    if tr:
        out.append(P("Transformações registradas nas previsões: " + "; ".join(t(f"{s}: {x if isinstance(x, str) else x}") for s, x in tr), "small"))
    for spec in figs:
        if spec.key.startswith(("04_", "05_", "06_")):
            fig_no[0] += 1
            out.append(figure_block(spec, fig_no[0], reg))
    return out


def _method(d: D.RunDossier, n: int) -> list:
    m = d.manifest
    s = m.get("strategy") or {}
    out = section(n, "Estratégia e metodologia computacional", "EMS V1.6")
    obj = m.get("objective") or {}
    out.append(P(f"<b>Função objetivo:</b> {t(obj.get('label'))} — única função objetivo disponível no EMS V1.6 "
                 "(o motor não implementa otimização multiobjetivo). Termos:"))
    out += bullets([t(x) for x in obj.get("terms") or []])
    rows = [("Algoritmo", SG.ALGORITHMS.get(s.get("algorithm"), s.get("algorithm")))]
    for k, lab in SG.LABELS.items():
        cur = s
        for part in k.split("."):
            cur = (cur or {}).get(part) if isinstance(cur, dict) else None
        rows.append((lab, num(cur, 4) if D.is_number(cur) else cur))
    rows += [("Meta penalizada", "sim" if s.get("meta_penalizada") else "não"),
             ("Validação dinâmica do H₂", "sim" if s.get("validar_h2") else "não"),
             ("Janela de simulação", f"{d.mission.get('start_wall')} · {d.mission.get('duration_min')} min"),
             ("Passo temporal", f"{d.mission.get('step_s')} s")]
    rows += list((m.get("engine_fixed") or {}).items())
    out.append(kv(rows, (0.42, 0.58)))
    out.append(P("Fluxo metodológico da rodada", "h2"))
    out.append(P("Cenário (versão gravada, imutável) → <b>preflight</b> (fase A: compatibilidade científica; o que o motor "
                 "não representa é bloqueado) → preparação dos dados (conversão para UTC e para a grade de 1 min, sem "
                 "extrapolação) → <b>modelos físicos</b> e pacote de troca (runtime V1.6) → fase B do preflight (contrato "
                 "efetivo do motor) → <b>EMS</b> em horizonte móvel (metaheurística + refino SLSQP por passo) → "
                 "armazenamento atômico de séries, resumo e procedência."))
    out.append(P("O término do algoritmo não implica otimalidade global: o despacho é obtido passo a passo em horizonte "
                 "móvel por metaheurística com refino local. Este relatório não é um artigo revisado por pares e não "
                 "contém referências bibliográficas geradas automaticamente.", "small"))
    return out


def _results(d: D.RunDossier, n: int, figs: list, reg: list, fig_no: list) -> list:
    s = d.summary
    out = section(n, "Resultados energéticos", "despacho")
    rel = (d.ems_report() or {}).get("rel") or {}
    names = s.get("fontes") or []
    pct = dict(zip(names, rel.get("pct_atendimento") or []))
    rows = [[D.source_label(k), num(v, 4), num((s.get("custo_por_fonte_rs") or {}).get(k), 4),
             num(pct.get(k), 2, "%") if k in pct else ND, str((s.get("partidas") or {}).get(k, ND))]
            for k, v in (s.get("energia_por_fonte_kWh") or {}).items()]
    if rows:
        out.append(table(["Fonte despachável", "Energia entregue [kWh]", "Custo [R$]", "Participação no atendimento",
                          "Partidas"], rows, [1.6, 1.2, 1.0, 1.4, 0.7], align_right=(1, 2, 3, 4)))
        out.append(P("Energia entregue = Σ max(P, 0)·Ts por fonte e participação = 100·E_fonte / Σ E das fontes "
                     "despacháveis — definições do relatório do EMS V1.6, lidas de <i>saidas/relatorio_ems.json</i>.", "small"))
    present = {e["kind"] for e in d.equipment()}
    ren = [["Solar fotovoltaica", "pv" in present, s.get("energia_solar_kWh")],
           ["Eólica", "wind" in present, s.get("energia_eolica_kWh")]]
    out.append(Spacer(1, 2 * mm))
    out.append(table(["Fonte renovável", "Instalada na revisão", "Energia aproveitável [kWh] (resumo)"],
                     [[a, "sim" if b else "não", num(c, 4) if b else "não instalada"] for a, b, c in ren],
                     [1.6, 1.2, 2.2], align_right=(2,)))
    for spec in figs:
        if spec.key.startswith("01_"):
            fig_no[0] += 1
            out.append(figure_block(spec, fig_no[0], reg))
    out.append(P("Na figura, as curvas solar/eólica são potências DISPONÍVEIS calculadas pelos modelos físicos; as curvas "
                 "das fontes controláveis são potências DESPACHADAS pelo EMS. Déficit e excedente só aparecem quando "
                 "registrados acima de 10⁻⁶ kW.", "small"))
    return out


def _storage(d: D.RunDossier, n: int, figs: list, reg: list, fig_no: list) -> list:
    s = d.summary
    out = section(n, "Armazenamento e hidrogênio", "SOC e H₂")
    has_soc = bool(s.get("soc_final"))
    has_h2 = s.get("h2_kg") is not None
    bat = ((d.manifest.get("engine_inputs") or {}).get("declared_initial_state") or {}).get("battery") or {}
    if has_soc:
        out.append(kv([("SOC inicial declarado", num(bat.get("soc0_pct"), 1, "%")),
                       ("Limites efetivos de SOC (restrição do EMS)", f"{num(bat.get('soc_min_pct'), 1)}–{num(bat.get('soc_max_pct'), 1)} %"),
                       ("SOC final (resumo)", "; ".join(f"{D.source_label(k)}: {pct_from_fraction(v, 2)} (fração {num(v, 6)})"
                                                         for k, v in s["soc_final"].items()))]))
    else:
        out.append(P("Sem bateria representada nesta rodada: nenhuma série de SOC.", "small"))
    if has_h2:
        dyn = s.get("h2_kg_validacao_dinamica")
        out.append(Spacer(1, 2 * mm))
        out.append(kv([("H₂ consumido — estimativa do EMS", num(s.get("h2_kg"), 6, "kg")),
                       ("H₂ — validação dinâmica PEMFC", num(dyn, 6, "kg") if dyn is not None else "não executada nesta rodada")]))
        out.append(P("A estimativa do EMS (curva empírica kg/kWh) e a validação dinâmica PEMFC são metodologias distintas e "
                     "não são tratadas como equivalentes.", "small"))
    else:
        out.append(P("Sem consumo de H₂ registrado (PEMFC ausente ou não despachada).", "small"))
    for spec in figs:
        if spec.key.startswith(("02_", "03_")):
            fig_no[0] += 1
            out.append(figure_block(spec, fig_no[0], reg))
    return out


def _discussion(d: D.RunDossier, n: int) -> list:
    s = d.summary
    out = section(n, "Discussão técnica (fatos registrados)", "observações descritivas")
    out.append(P("Observações derivadas diretamente dos valores persistidos; não constituem parecer sobre viabilidade "
                 "econômica, precisão dos modelos ou otimalidade.", "small"))
    items = []
    uns = s.get("energia_nao_atendida_kWh")
    if D.is_number(uns):
        items.append(f"Energia não atendida registrada: {num(uns, 4, 'kWh')}"
                     + (" (nula)." if uns == 0 else (" — valor inferior a 10⁻⁶ kWh." if abs(uns) < 1e-6 else ".")))
    exc = s.get("energia_excedente_kWh")
    if D.is_number(exc):
        items.append(f"Excedente vertido registrado: {num(exc, 4, 'kWh')} (despachável {num(s.get('energia_excedente_despachavel_kWh'), 4, 'kWh')}; "
                     f"renovável {num(s.get('energia_excedente_renovavel_kWh'), 4, 'kWh')}).")
    e_src = s.get("energia_por_fonte_kWh") or {}
    if e_src:
        rank = sorted(e_src.items(), key=lambda kv: -(kv[1] or 0))
        items.append("Energia entregue pelas fontes despacháveis, em ordem decrescente: "
                     + "; ".join(f"{t(D.source_label(k))} {num(v, 3, 'kWh')}" for k, v in rank) + ".")
    if D.is_number(s.get("energia_solar_kWh")) and s.get("energia_solar_kWh"):
        items.append(f"Energia solar FV considerada no balanço: {num(s.get('energia_solar_kWh'), 3, 'kWh')}.")
    for k, v in (s.get("soc_final") or {}).items():
        bat = ((d.manifest.get("engine_inputs") or {}).get("declared_initial_state") or {}).get("battery") or {}
        items.append(f"SOC final ({t(D.source_label(k))}): {pct_from_fraction(v, 2)}; SOC inicial declarado "
                     f"{num(bat.get('soc0_pct'), 1, '%')}; tolerância do SOC-alvo da estratégia "
                     f"±{num((d.manifest.get('strategy') or {}).get('soc_alvo_tol'), 2)} (fração).")
    if s.get("h2_kg") is not None:
        items.append(f"Hidrogênio consumido (estimativa do EMS): {num(s.get('h2_kg'), 4, 'kg')}.")
    pi = s.get("passos_inviaveis")
    items.append(f"Passos inviáveis registrados pelo motor: {pi if pi is not None else ND} de {s.get('passos', ND)}.")
    w = d.engine_warnings()
    items.append(f"Avisos do motor registrados: {len(w)}." + (" " + "; ".join(t(x) for x in w[:6]) if w else ""))
    nwarn = sum(1 for i in d.preflight_items() if i.get("level") == "aviso")
    items.append(f"Advertências do preflight registradas no manifesto: {nwarn} (ver seção de limitações).")
    out += bullets(items)
    return out


def _provenance(d: D.RunDossier, n: int, generated_at: str) -> list:
    r = d.run
    sw = d.software
    sci = sw.get("science") or {}
    out = section(n, "Procedência científica e rastreabilidade", "identificadores")
    rows = [("UID da microrrede de origem", r.microgrid_uid), ("Incarnação", r.incarnation or "não registrada"),
            ("UID do cenário", r.scenario_uid), ("Versão do cenário", str(r.scenario_version)),
            ("Impressão digital da versão", r.scenario_fingerprint),
            ("Revisão do inventário", str(r.config_revision)), ("Impressão digital da revisão", r.config_fingerprint),
            ("UID da rodada", r.run_uid), ("Pedido (request_id)", r.request_id),
            ("Iniciada / finalizada (UTC)", f"{r.created_at} / {r.finished_at or '—'}"),
            ("SEEDS2 que executou", sw.get("app")), ("Runtime", sw.get("runtime")),
            ("Python · numpy · pandas · scipy", f"{sw.get('python')} · {sw.get('numpy')} · {sw.get('pandas')} · {sw.get('scipy')}"),
            ("Código científico (SHA-256)", f"{sci.get('sha256')} ({sci.get('files')} arquivos)"),
            ("Algoritmo e parâmetros efetivos", f"{(d.run.outcome or {}).get('effective_engine', {}).get('algoritmo', ND)} · "
                                                f"N = {d.summary.get('N', ND)} · semente {(d.manifest.get('strategy') or {}).get('seed')}")]
    if d.kind == D.ARCHIVED and d.archive:
        a = d.archive
        rows += [("Estudo arquivado (ID local)", a.get("archive_uid")), ("Identidade do conteúdo", a.get("content_id")),
                 ("SHA-256 do pacote importado", a.get("package_sha256")), ("Exportado / importado", f"{a.get('exported_at')} / {a.get('imported_at')}")]
    rows += [("Documento gerado em", f"{generated_at} por {APP_NAME} {APP_VERSION}")]
    out.append(kv(rows, (0.3, 0.7), mono=True))
    out.append(P("Dados persistidos da rodada (SHA-256 conferido nesta leitura)", "h2"))
    out.append(table(["Dado", "SHA-256", "Tamanho [bytes]"],
                     [[k, v["sha256"], f"{int(v['size']):,}".replace(",", ".")] for k, v in sorted(r.data.items())],
                     [1.8, 4.0, 0.8], mono_cols=(1,), align_right=(2,)))
    if d.forecasts():
        out.append(Spacer(1, 2 * mm))
        out.append(table(["Previsão do cenário", "Série normalizada (SHA-256)", "Arquivo original (SHA-256)"],
                         [[s_, e.get("data"), e.get("blob") or "—"] for s_, e in d.forecasts().items()],
                         [1.0, 2.8, 2.8], mono_cols=(1, 2)))
    msg = ("Os resultados foram produzidos na instalação de origem e apenas consultados nesta instalação a partir do "
           "estudo arquivado. " if d.kind == D.ARCHIVED else "")
    out.append(Spacer(1, 2 * mm))
    out.append(note(msg + "A geração deste relatório NÃO é uma nova execução do EMS: nenhum modelo nem o otimizador foi "
                          "chamado e nenhum dado persistido foi alterado. A fonte portátil integral é o pacote .seeds2study.zip; "
                          "PDF, Excel e figuras são representações derivadas."))
    return out


def _limitations(d: D.RunDossier, n: int) -> list:
    out = section(n, "Limitações e advertências registradas", "experimento × software")
    exp = []
    for i in d.preflight_items():
        if i.get("level") in ("aviso", "pendente", "verificacao", "erro"):
            exp.append(f"[preflight · {t(i.get('level'))}] {t(i.get('message'))}")
    for x in (d.manifest.get("preflight") or {}).get("drift") or []:
        exp.append(f"[deriva do inventário] {t(x)}")
    for e in (d.manifest.get("preflight") or {}).get("excluded") or []:
        exp.append(f"[exclusão da rodada] {t(e.get('name'))}: {t(e.get('reason'))}")
    for w in d.engine_warnings():
        exp.append(f"[aviso do motor] {t(w)}")
    out.append(P("Do experimento (registradas nesta rodada)", "h2"))
    out += bullets(exp or ["Nenhuma advertência, exclusão ou deriva registrada."])
    out.append(P("Do software (registradas no manifesto da rodada)", "h2"))
    sw = [f"{t(_rule_label(k))}: {t(v)}" for k, v in ((d.manifest.get("engine_inputs") or {}).get("engine_initial_state_rule") or {}).items()]
    sw += [f"{t(k)}: {t(v)}" for k, v in (d.manifest.get("engine_fixed") or {}).items()]
    sw.append("Função objetivo única (custo econômico do EMS V1.6); sem otimização multiobjetivo.")
    out += bullets(sw)
    return out


def _diagnostic(d: D.RunDossier) -> list:
    err = d.run.error or {}
    out = section(1, "Diagnóstico da rodada", "rodada não concluída")
    out.append(note(f"<b>Estado: {t(d.state_label)}.</b> Nenhum resultado foi gravado como concluído; este documento não "
                    "apresenta indicadores, tabelas nem gráficos de resultados.", "bad"))
    out.append(Spacer(1, 2 * mm))
    out.append(kv([("Tipo de falha", err.get("kind") or ("interrupção do processo" if d.run.state == "interrompida" else ND)),
                   ("Exceção", err.get("type")), ("Mensagem", err.get("message")),
                   ("Último progresso registrado", ", ".join(f"{k}={v}" for k, v in (d.run.progress or {}).items()) or "—")]))
    chk = d.engine_check_items()
    if chk:
        out.append(P("Verificação do contrato efetivo do motor", "h2"))
        out += bullets([f"[{t(i.get('level'))}] {t(i.get('message'))}" for i in chk])
    if err.get("traceback"):
        out.append(P("Rastreamento registrado (trecho final)", "h2"))
        out.append(P(t(err["traceback"][-2500:]), "mono"))
    return out


# ====================================================================== montagem
def build_report(d: D.RunDossier, *, generated_at: str | None = None, progress=None) -> bytes:
    """PDF do relatório (rodada concluída) ou do diagnóstico (falha/interrupção). Nada é gravado."""
    _fonts()
    S.update(_styles())
    say = progress or (lambda _m: None)
    generated_at = generated_at or D.utc_now()
    say("Preparando figuras a partir das séries gravadas")
    figs = FG.run_figures(d) if d.concluded else []
    reg: list = []
    fig_no = [0]
    story: list = _cover(d, generated_at) + [NextPageTemplate("page"), PageBreak()]
    say("Montando o documento")
    if d.concluded:
        story += _executive(d)
        story += _configuration(d, 2)
        story += _initial(d, 3)
        story += _forecasts(d, 4, figs, reg, fig_no)
        story += _method(d, 5)
        story += _results(d, 6, figs, reg, fig_no)
        story += _storage(d, 7, figs, reg, fig_no)
        story += _discussion(d, 8)
        story += _provenance(d, 9, generated_at)
        story += _limitations(d, 10)
    else:
        story += _diagnostic(d)
        story += _configuration(d, 2)
        story += _initial(d, 3)
        story += _method(d, 4)
        story += _provenance(d, 5, generated_at)
        story += _limitations(d, 6)
    buf = io.BytesIO()
    meta = {"header": "SEEDS2 · " + ("RELATÓRIO DE SIMULAÇÃO DE MICRORREDE" if d.concluded else "RELATÓRIO DIAGNÓSTICO"),
            "right": f"{d.microgrid.get('name')} · {d.scenario_name} v{d.run.scenario_version}",
            "run": d.run_uid, "generated": generated_at}
    cover, page = _decor(meta)
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=MX, rightMargin=MX, topMargin=MT, bottomMargin=MB,
                          title=f"SEEDS2 — {'Relatório de simulação' if d.concluded else 'Relatório diagnóstico'} · "
                                f"{d.scenario_name} v{d.run.scenario_version}",
                          author=f"{APP_NAME} {APP_VERSION}", subject=f"Rodada {d.run_uid}", creator=f"{APP_NAME} {APP_VERSION}")
    frame = Frame(MX, MB, TEXT_W, PAGE_H - MT - MB, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate("cover", [frame], onPage=cover), PageTemplate("page", [frame], onPage=page)])
    doc.build(story, canvasmaker=_NumberedCanvas)
    pdf = buf.getvalue()
    if reg:
        pdf = _merge_figures(pdf, reg, say)
    return pdf


def _merge_figures(pdf: bytes, reg: list, say) -> bytes:
    from pypdf import PdfReader, PdfWriter, Transformation

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    for i, (page_no, x, y, spec) in enumerate(reg, start=1):
        say(f"Desenhando figura vetorial {i} de {len(reg)}: {spec.title}")
        fig = PdfReader(io.BytesIO(FG.render(spec, "pdf"))).pages[0]
        writer.pages[page_no - 1].merge_transformed_page(fig, Transformation().translate(tx=x, ty=y))
    writer.add_metadata({"/Producer": f"{APP_NAME} {APP_VERSION} (reportlab + matplotlib + pypdf)"})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def report_filename(d: D.RunDossier) -> str:
    return D.safe_stem(d, "relatorio" if d.concluded else "diagnostico") + ".pdf"


__all__ = ["build_report", "num", "report_filename"]
