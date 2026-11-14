"""UI-RESULTADOS-02 — desenho VETORIAL, num canvas reportlab, do SVG restrito que o motor gráfico Trama serializa para o
relatório PDF da rodada (``partitura.js`` → ``svgPdf``).

Por que um conversor próprio (e pequeno): o relatório reproduz os MESMOS gráficos da Partitura, desenhados pelo próprio
navegador com os dados gravados; o SVG serializado tem um vocabulário fechado (``svg``, ``defs``, ``clipPath``, ``g``,
``line``, ``rect``, ``path``, ``polyline``, ``circle``, ``text``), cores já RESOLVIDAS (``#rrggbb`` + opacidades) e hachuras
como atributos (``data-hatch``). Não há CSS, script, imagem, fonte externa nem referência a arquivos: nada do que não está
na lista é desenhado.

Entrada NÃO confiável (vem do navegador): tamanho e número de elementos limitados, DTD/entidades recusadas antes da análise,
números validados (finitos, limitados), textos desenhados como texto (nunca interpretados como marcação). Nenhum dado é
recalculado aqui: só geometria e cor.
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable

MAX_BYTES = 3_000_000                      # por gráfico
MAX_ELEMENTOS = 80_000
MAX_COORD = 1e6
TAGS = {"svg", "defs", "clipPath", "g", "line", "rect", "path", "polyline", "circle", "text"}
_PROIBIDO = re.compile(r"<!DOCTYPE|<!ENTITY|<\?xml-stylesheet|<script|<foreignObject|<image|<use\b|href\s*=", re.I)
_COR = re.compile(r"#[0-9a-fA-F]{6}")
FONTE, FONTE_NEGRITO = "DV", "DV-B"        # DejaVu Sans (registrada por seeds2.report.run_pdf._fonts)


class SvgInvalido(ValueError):
    """O SVG recebido está fora do vocabulário admitido ou excede os limites (mensagem apresentável)."""


def _tag(e: ET.Element) -> str:
    return e.tag.rsplit("}", 1)[-1]


def analisar(texto: str) -> ET.Element:
    """SVG restrito → árvore (sem namespace). Recusa DTD/entidades, elementos fora da lista e excesso de elementos."""
    if not isinstance(texto, str) or not texto.startswith("<svg"):
        raise SvgInvalido("gráfico sem SVG")
    if len(texto) > MAX_BYTES:
        raise SvgInvalido(f"gráfico com {len(texto)} bytes (limite {MAX_BYTES})")
    if _PROIBIDO.search(texto):
        raise SvgInvalido("gráfico com construção não admitida (DTD, entidade, script, imagem ou referência externa)")
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError as exc:
        raise SvgInvalido(f"SVG malformado ({exc})") from exc
    n = 0
    for e in raiz.iter():
        n += 1
        if n > MAX_ELEMENTOS:
            raise SvgInvalido("gráfico com elementos demais")
        e.tag = _tag(e)
        if e.tag not in TAGS:
            raise SvgInvalido(f"elemento SVG não admitido: {e.tag!r}")
    if raiz.tag != "svg":
        raise SvgInvalido("raiz do gráfico não é <svg>")
    _num(raiz.get("width")), _num(raiz.get("height"))
    return raiz


def _num(v, padrao: float | None = None) -> float:
    if v is None or v == "":
        if padrao is None:
            raise SvgInvalido("atributo numérico ausente")
        return padrao
    try:
        x = float(str(v).strip().removesuffix("px"))
    except ValueError as exc:
        raise SvgInvalido(f"número inválido no SVG: {str(v)[:20]!r}") from exc
    if not math.isfinite(x) or abs(x) > MAX_COORD:
        raise SvgInvalido("número fora dos limites no SVG")
    return x


def _cor(v):
    if not v or v == "none":
        return None
    if not _COR.fullmatch(v):
        raise SvgInvalido(f"cor não resolvida no SVG: {v[:20]!r}")
    return colors.HexColor(v)


def _alpha(e: ET.Element, prop: str) -> float:
    a = _num(e.get(prop + "-opacity"), 1.0) * _num(e.get("opacity"), 1.0)
    return max(0.0, min(1.0, a))


_TOKEN = re.compile(r"[MmLlHhVvZzAaCc]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _arco(x1, y1, rx, ry, phi, fa, fs, x2, y2):
    """Arco elíptico SVG (parametrização por extremos) → segmentos de Bézier cúbica [(c1, c2, p)]."""
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [((x1, y1), (x2, y2), (x2, y2))]
    rx, ry = abs(rx), abs(ry)
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = (x1p ** 2) / rx ** 2 + (y1p ** 2) / ry ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if fa == fs:
        co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx, cy = cp * cxp - sp * cyp + (x1 + x2) / 2, sp * cxp + cp * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dt > 0:
        dt -= 2 * math.pi
    elif fs and dt < 0:
        dt += 2 * math.pi
    n = max(1, int(math.ceil(abs(dt) / (math.pi / 2))))
    d = dt / n
    k = 4 / 3 * math.tan(d / 4)
    out = []

    def pt(t):
        return (cx + rx * math.cos(t) * cp - ry * math.sin(t) * sp, cy + rx * math.cos(t) * sp + ry * math.sin(t) * cp)

    def dp(t):
        return (-rx * math.sin(t) * cp - ry * math.cos(t) * sp, -rx * math.sin(t) * sp + ry * math.cos(t) * cp)
    t = t1
    for _ in range(n):
        p0, p3 = pt(t), pt(t + d)
        d0, d3 = dp(t), dp(t + d)
        out.append(((p0[0] + k * d0[0], p0[1] + k * d0[1]), (p3[0] - k * d3[0], p3[1] - k * d3[1]), p3))
        t += d
    return out


def _caminho(canv, d: str):
    """Comandos M L H V Z A C (absolutos e relativos) → caminho reportlab."""
    tk = _TOKEN.findall(d or "")
    if len(tk) > 400_000:
        raise SvgInvalido("caminho longo demais")
    p = canv.beginPath()
    i, cmd, x, y, x0, y0 = 0, None, 0.0, 0.0, 0.0, 0.0

    def nums(k):
        nonlocal i
        vs = [_num(v) for v in tk[i:i + k]]
        if len(vs) < k:
            raise SvgInvalido("caminho incompleto")
        i += k
        return vs
    while i < len(tk):
        if tk[i].isalpha():
            cmd = tk[i]
            i += 1
            if cmd in "Zz":
                p.close()
                x, y = x0, y0
                continue
        if cmd is None:
            raise SvgInvalido("caminho sem comando inicial")
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            a, b = nums(2)
            x, y = (x + a, y + b) if rel else (a, b)
            p.moveTo(x, y)
            x0, y0 = x, y
            cmd = "l" if rel else "L"
        elif c == "L":
            a, b = nums(2)
            x, y = (x + a, y + b) if rel else (a, b)
            p.lineTo(x, y)
        elif c == "H":
            (a,) = nums(1)
            x = x + a if rel else a
            p.lineTo(x, y)
        elif c == "V":
            (b,) = nums(1)
            y = y + b if rel else b
            p.lineTo(x, y)
        elif c == "C":
            v = nums(6)
            if rel:
                v = [v[0] + x, v[1] + y, v[2] + x, v[3] + y, v[4] + x, v[5] + y]
            p.curveTo(*v)
            x, y = v[4], v[5]
        elif c == "A":
            rx, ry, phi, fa, fs, a, b = nums(7)
            xe, ye = (x + a, y + b) if rel else (a, b)
            for c1, c2, p3 in _arco(x, y, rx, ry, phi, int(fa), int(fs), xe, ye):
                p.curveTo(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
            x, y = xe, ye
        else:
            raise SvgInvalido(f"comando de caminho não admitido: {cmd!r}")
    return p


class FiguraSVG(Flowable):
    """Gráfico vetorial: o SVG restrito desenhado em escala para a largura ``largura`` [pt]."""

    def __init__(self, svg: str | ET.Element, largura: float, altura_max: float | None = None):
        super().__init__()
        self.raiz = analisar(svg) if isinstance(svg, str) else svg
        self.w0, self.h0 = _num(self.raiz.get("width")), _num(self.raiz.get("height"))
        if self.w0 <= 0 or self.h0 <= 0:
            raise SvgInvalido("gráfico sem dimensões")
        s = largura / self.w0
        if altura_max and self.h0 * s > altura_max:
            s = altura_max / self.h0
        self.s = s
        self.width, self.height = self.w0 * s, self.h0 * s
        self.clips = {e.get("id"): e for e in self.raiz.iter("clipPath") if e.get("id")}

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.translate(0, self.height)
        c.scale(self.s, -self.s)                 # coordenadas do SVG (y para baixo)
        for e in self.raiz:
            self._el(c, e)
        c.restoreState()

    # ------------------------------------------------------------------------------------------------ elementos
    def _estilo(self, c, e) -> tuple[bool, bool]:
        f, s = _cor(e.get("fill")), _cor(e.get("stroke"))
        if f is not None:
            c.setFillColor(f)
            c.setFillAlpha(_alpha(e, "fill"))
        if s is not None:
            c.setStrokeColor(s)
            c.setStrokeAlpha(_alpha(e, "stroke"))
            c.setLineWidth(max(0.0, _num(e.get("stroke-width"), 1.0)))
            dash = [max(0.0, _num(v)) for v in (e.get("stroke-dasharray") or "").replace(",", " ").split()]
            c.setDash(dash if dash and sum(dash) > 0 else [])
            c.setLineJoin(1)
        return f is not None, s is not None and _num(e.get("stroke-width"), 1.0) > 0

    def _el(self, c, e):
        t = e.tag
        if t in ("defs", "clipPath"):
            return
        if t == "g":
            c.saveState()
            m = re.match(r"url\(#([^)]+)\)", e.get("clip-path") or "")
            if m and m.group(1) in self.clips:
                r = next(iter(self.clips[m.group(1)]), None)
                if r is not None and r.tag == "rect":
                    p = c.beginPath()
                    p.rect(_num(r.get("x"), 0), _num(r.get("y"), 0), _num(r.get("width"), 0), _num(r.get("height"), 0))
                    c.clipPath(p, stroke=0, fill=0)
            for k in e:
                self._el(c, k)
            c.restoreState()
            return
        if t == "svg":
            for k in e:
                self._el(c, k)
            return
        c.saveState()
        try:
            if t == "text":
                self._texto(c, e)
                return
            fill, stroke = self._estilo(c, e)
            if t == "rect":
                x, y, w, h = (_num(e.get(k), 0) for k in ("x", "y", "width", "height"))
                if w <= 0 or h <= 0:
                    return
                rx = min(_num(e.get("rx"), 0), w / 2, h / 2)
                if fill or stroke:
                    if rx > 0.05:
                        c.roundRect(x, y, w, h, rx, stroke=int(stroke), fill=int(fill))
                    else:
                        c.rect(x, y, w, h, stroke=int(stroke), fill=int(fill))
                if e.get("data-hatch"):
                    self._hachura(c, e, x, y, w, h, rx)
            elif t == "line":
                if stroke:
                    c.line(*(_num(e.get(k), 0) for k in ("x1", "y1", "x2", "y2")))
            elif t == "circle":
                r = _num(e.get("r"), 0)
                if r > 0 and (fill or stroke):
                    c.circle(_num(e.get("cx"), 0), _num(e.get("cy"), 0), r, stroke=int(stroke), fill=int(fill))
            elif t == "polyline":
                v = [_num(x) for x in (e.get("points") or "").replace(",", " ").split()]
                if len(v) >= 4 and (stroke or fill):
                    p = c.beginPath()
                    p.moveTo(v[0], v[1])
                    for i in range(2, len(v) - 1, 2):
                        p.lineTo(v[i], v[i + 1])
                    c.drawPath(p, stroke=int(stroke), fill=int(fill))
            elif t == "path":
                if fill or stroke:
                    c.drawPath(_caminho(c, e.get("d")), stroke=int(stroke), fill=int(fill), fillMode=0)
                if e.get("data-hatch"):
                    self._hachura(c, e, 0, 0, self.w0, self.h0, 0, recorte=_caminho(c, e.get("d")))
        finally:
            c.restoreState()

    def _hachura(self, c, e, x, y, w, h, rx, recorte=None):
        cor = _cor(e.get("data-hatch"))
        if cor is None:
            return
        lw, per = max(0.3, _num(e.get("data-hatch-w"), 2.0)), max(1.5, _num(e.get("data-hatch-p"), 5.0))
        c.saveState()
        p = recorte
        if p is None:
            p = c.beginPath()
            if rx > 0.05:
                p.roundRect(x, y, w, h, rx)
            else:
                p.rect(x, y, w, h)
        c.clipPath(p, stroke=0, fill=0)
        c.setStrokeColor(cor)
        c.setStrokeAlpha(_alpha(e, "fill"))
        c.setLineWidth(lw)
        c.setDash([])
        passo = per * math.sqrt(2)
        k = -h
        while k < w + h:
            c.line(x + k, y + h, x + k + h, y)
            k += passo
        c.restoreState()

    def _texto(self, c, e):
        s = (e.text or "")[:500]
        if not s.strip():
            return
        tam = max(1.0, min(_num(e.get("font-size"), 11.0), 96.0))
        fonte = FONTE_NEGRITO if _num(e.get("font-weight"), 400) >= 600 else FONTE
        nat = stringWidth(s, fonte, tam)
        alvo = _num(e.get("data-w"), 0.0)
        esc = 100.0
        if alvo > 0 and nat > alvo * 1.01:            # a fonte do PDF é mais larga que a da tela: comprime no mesmo espaço
            esc = max(72.0, 100.0 * alvo / nat)
        larg = nat * esc / 100.0
        x = _num(e.get("x"), 0) + _num(e.get("dx"), 0)
        y = _num(e.get("y"), 0)
        ancora = e.get("text-anchor") or "start"
        x0 = x - larg / 2 if ancora == "middle" else x - larg if ancora == "end" else x
        c.translate(x0, y)
        c.scale(1, -1)
        if e.get("data-halo") and _cor(e.get("stroke")) is not None:
            c.saveState()                        # o modo de texto (Tr) persiste no estado gráfico: isolado em q … Q
            t = c.beginText(0, 0)
            t.setFont(fonte, tam)
            t.setHorizScale(esc)
            t.setTextRenderMode(1)
            c.setStrokeColor(_cor(e.get("stroke")))
            c.setStrokeAlpha(_alpha(e, "stroke"))
            c.setLineWidth(max(0.0, _num(e.get("stroke-width"), 2.0)))
            c.setLineJoin(1)
            t.textOut(s)
            c.drawText(t)
            c.restoreState()
        f = _cor(e.get("fill"))
        if f is None:
            return
        c.setFillColor(f)
        c.setFillAlpha(_alpha(e, "fill"))
        t = c.beginText(0, 0)
        t.setFont(fonte, tam)
        t.setHorizScale(esc)
        t.setTextRenderMode(0)
        t.textOut(s)
        c.drawText(t)


__all__ = ["FiguraSVG", "MAX_BYTES", "SvgInvalido", "analisar"]
