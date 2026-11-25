"""Slide 15 (deck) — Coordenação hierárquica e valor futuro: três propostas.
Fonte: Seção 4.4 do artigo (eq. 16–18) e 5.3 (por que não os duais). Por quê: o MPC só enxerga N intervalos (slide 14); pela relação de
Bellman, o custo ótimo = custo da janela + custo de continuação; se V_{k+N} for exato, a janela reproduz o ótimo do horizonte restante.
O valor marginal μ = −∂V/∂E [R$/kWh] é o «valor da água» da energia armazenada (slide 5). Com decisões inteiras, V pode ser não convexa
ou descontínua e a derivada pode não existir: os duais do MILP não são usados como preços; a função é aproximada pelo planejador de
horizonte longo (como → slide 19). Curvas ESQUEMÁTICAS. Custo futuro sempre #C0532F."""
import json
import os
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import CSS, NAVY, SLATE, TEAL, LIGHT, LINE, BAT, PEM, MUTED, T
from gerar_slide5_v3 import DEFS3
from gerar_slide8 import NM, rodape

D = os.path.dirname(os.path.abspath(__file__))
FUT = "#C0532F"
F = r"{\color{%s}{%%s}}" % FUT
TEX = {
    "e16": r"V_t(x)=\min_{d\,\in\,D_t(x)}\big\{\,\ell_t(x,d)+%s\,\big\}" % (F % r"V_{t+1}\big(f_t(x,d)\big)"),
    "e17": r"J_k^{*}=\min_{\{d_t\}}\Big\{\sum_{t=k}^{k+N-1}\ell_t(x_t,d_t)\;+\;%s\Big\}" % (F % r"V_{k+N}(x_{k+N})"),
    "e18": r"\mu_t=-\,\partial %s/\partial E" % (F % r"V_t"),
    "i_mu": r"\mu", "i_v": F % "V", "i_e": "E",
}
SVG = json.loads(subprocess.run(["node", os.path.join(D, "tex2svg.js")], input=json.dumps(TEX), capture_output=True,
                                text=True, env=dict(os.environ, NODE_PATH=NM), check=True).stdout)
CSSM = CSS + """
.d{position:absolute}
.eq{display:flex;align-items:center;justify-content:center;color:#14213D}
.eq svg{overflow:visible}
.p{font:500 23px/1.4 "Manrope";color:#4A5568}
.p b{font-weight:800;color:#14213D}
.p i{font-style:normal;color:#C0532F;font-weight:800}
.p .s{display:inline-block;vertical-align:middle}
"""
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
TIT = '<div class="tt">Coordenação hierárquica e valor futuro</div>'
REF = ("eq. 16–18 do artigo (Seção 4.4) · [16] Rawlings, Mayne e Diehl (Bellman) · [6] aproximações da função de continuação · "
       "[8, 11] valor da água no SIN · curvas esquemáticas")


def div(x, y, w, h, inner, cls="", st=""):
    hh = f"height:{h}px;" if h else ""
    return f'<div class="d {cls}" style="left:{x}px;top:{y}px;width:{w}px;{hh}{st}">{inner}</div>'


def eq(k, x, y, w, h, px, al="center"):
    return div(x, y, w, h, SVG[k], "eq", f"font-size:{px}px;justify-content:{al}")


def salvar(nome, s, html):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS3}{s}</svg>'
            + html + f'<div class="ref">{REF}</div>' + rodape(15))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


def bateria(cx, cy, nivel, s=1.0):
    w, h = 26 * s, 40 * s
    x, y = cx - w / 2, cy - h / 2
    lv = (h - 8 * s) * nivel
    o = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{5*s}" fill="#fff" stroke="{BAT}" stroke-width="2.5"/>'
    o += f'<rect x="{cx-5*s}" y="{y-5*s}" width="{10*s}" height="{5*s}" rx="1.5" fill="{BAT}"/>'
    if nivel > 0:
        o += f'<rect x="{x+4*s}" y="{y+h-4*s-lv}" width="{w-8*s}" height="{lv}" rx="{2*s}" fill="{BAT}"/>'
    return o


def eixo(X0, X1, Y0, Y1, ylab="custo futuro", xlab="energia armazenada ao fim da janela", icones=True, fs=17):
    o = (f'<line x1="{X0}" x2="{X1}" y1="{Y1}" y2="{Y1}" stroke="{NAVY}" stroke-width="2"/>'
         f'<line x1="{X0}" x2="{X0}" y1="{Y0}" y2="{Y1}" stroke="{NAVY}" stroke-width="2"/>'
         + T(X0 + 10, Y0 + 4, ylab, fs, 700, FUT))
    if icones:
        o += bateria(X0 + 18, Y1 + 34, 0.08, .8) + bateria(X1 - 16, Y1 + 34, .95, .8)
        o += T((X0 + X1) / 2, Y1 + 40, xlab, fs, 600, SLATE, anchor="middle")
    else:
        o += T((X0 + X1) / 2, Y1 + 30, xlab, fs, 600, SLATE, anchor="middle")
    return o


def curva_convexa(X0, X1, Y0, Y1, e0=.42, tang=True, fs=20, rot=True):
    """V(E) convexa e decrescente; tangente em E0 com inclinação −μ."""
    n = 140
    vs = [i / n for i in range(n + 1)]
    V = lambda v: .08 + .80 * (1 - v) ** 2.1
    px = lambda v: X0 + 6 + (X1 - X0 - 12) * v
    py = lambda c: Y1 - (Y1 - Y0 - 30) * c
    d = "M" + " L".join(f"{px(v):.1f} {py(V(v)):.1f}" for v in vs)
    o = f'<path d="{d} L{px(1)} {Y1} L{px(0)} {Y1} Z" fill="url(#gf)"/>'
    o += f'<path d="{d}" fill="none" stroke="{FUT}" stroke-width="6" stroke-linecap="round"/>'
    if rot:
        o += T(px(.07) + 22, py(V(.07)) + 6, "V(E)", fs + 4, 700, FUT, "Gelasio", it=True)
    if tang:
        h = 1e-4
        sl = (V(e0 + h) - V(e0 - h)) / (2 * h)
        a, b = e0 - .2, e0 + .26
        x1, y1, x2, y2 = px(a), py(V(e0) + sl * (a - e0)), px(b), py(V(e0) + sl * (b - e0))
        o += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{NAVY}" stroke-width="3" stroke-dasharray="2 7" stroke-linecap="round"/>'
        xe, ye = px(e0), py(V(e0))
        o += f'<line x1="{xe}" x2="{xe}" y1="{ye+10}" y2="{Y1}" stroke="{NAVY}" stroke-width="1.6" stroke-dasharray="3 6" opacity=".5"/>'
        o += f'<circle cx="{xe}" cy="{ye}" r="9" fill="{NAVY}" stroke="#fff" stroke-width="3"/>'
        o += T(xe + 18, ye - 24, "inclinação = −μ", fs, 700, NAVY)
    return o


def curva_nconvexa(X0, X1, Y0, Y1, fs=18, rot=True):
    """V(E) com uma decisão inteira (ex.: ligar a célula): dois ramos, salto e bico — derivada inexistente no ponto marcado."""
    n = 80
    px = lambda v: X0 + 6 + (X1 - X0 - 12) * v
    py = lambda c: Y1 - (Y1 - Y0 - 30) * c
    A = lambda v: .74 + .16 * (1 - v) ** 2      # pouca energia: precisa ligar a célula (custo de partida)
    B = lambda v: .10 + .50 * (1 - v) ** 1.8    # energia suficiente: célula desligada
    e1 = .46
    d1 = "M" + " L".join(f"{px(v):.1f} {py(A(v)):.1f}" for v in [i / n * e1 for i in range(n + 1)])
    d2 = "M" + " L".join(f"{px(v):.1f} {py(B(v)):.1f}" for v in [e1 + i / n * (1 - e1) for i in range(n + 1)])
    g1 = "M" + " L".join(f"{px(v):.1f} {py(A(v)):.1f}" for v in [e1 + i / n * (1 - e1) * .6 for i in range(n + 1)])
    g2 = "M" + " L".join(f"{px(v):.1f} {py(B(v)):.1f}" for v in [i / n * e1 for i in range(n + 1)])
    o = (f'<path d="{g1}" fill="none" stroke="{MUTED}" stroke-width="2.5" stroke-dasharray="4 7"/>'
         f'<path d="{g2}" fill="none" stroke="{MUTED}" stroke-width="2.5" stroke-dasharray="4 7"/>')
    o += f'<path d="{d1}" fill="none" stroke="{FUT}" stroke-width="6" stroke-linecap="round"/>'
    o += f'<path d="{d2}" fill="none" stroke="{FUT}" stroke-width="6" stroke-linecap="round"/>'
    xa, ya, yb = px(e1), py(A(e1)), py(B(e1))
    o += f'<line x1="{xa}" x2="{xa}" y1="{ya+8}" y2="{yb-8}" stroke="{FUT}" stroke-width="2" stroke-dasharray="2 5"/>'
    o += f'<circle cx="{xa}" cy="{ya}" r="7" fill="{FUT}"/><circle cx="{xa}" cy="{yb}" r="7" fill="#fff" stroke="{FUT}" stroke-width="3"/>'
    o += f'<circle cx="{xa}" cy="{(ya+yb)/2}" r="26" fill="none" stroke="{NAVY}" stroke-width="2.5"/>'
    o += T(xa + 34, (ya + yb) / 2 - 6, "salto: ∂V/∂E", fs, 700, NAVY) + T(xa + 34, (ya + yb) / 2 + 18, "não existe", fs, 700, NAVY)
    if rot:
        o += T(px(.03), py(A(.03)) - 14, "liga a célula", fs - 2, 700, PEM)
        o += T(px(.97), py(B(.97)) - 16, "célula desligada", fs - 2, 700, PEM, anchor="end")
    return o


def cartao(x, y, w, h, n, tit):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="24" fill="{LIGHT}"/>'
    s += f'<circle cx="{x+44}" cy="{y+48}" r="21" fill="{NAVY}"/>' + T(x + 44, y + 56, str(n), 21, 700, "#fff", "Gelasio", anchor="middle")
    s += T(x + 80, y + 56, tit, 26, 700, NAVY, "Gelasio")
    return s


# ===================================================================== P1 · eq. 17 em cima + três cartões (por quê · valor do kWh · duais)
def p1():
    s = f'<rect x="110" y="166" width="1700" height="170" rx="28" fill="{LIGHT}"/>'
    html = eq("e17", 130, 170, 1100, 162, 34)
    s += T(1215, 196, "eq. 17", 15, 600, MUTED, anchor="end")
    s += f'<line x1="1250" x2="1250" y1="196" y2="306" stroke="{LINE}" stroke-width="2"/>'
    html += eq("e16", 1270, 180, 520, 120, 22)
    s += T(1780, 196, "Bellman · eq. 16", 15, 600, MUTED, anchor="end")
    y0, h, w, gap = 360, 552, 552, 22
    xs = [110 + i * (w + gap) for i in range(3)]
    s += cartao(xs[0], y0, w, h, 1, "Por que valor futuro?")
    html += div(xs[0] + 40, y0 + 104, w - 80, None,
                "O MPC só enxerga <b>N intervalos</b>; o que vem depois precisa entrar como custo.", "p")
    html += div(xs[0] + 40, y0 + 230, w - 80, None,
                "Pela relação de Bellman, decidir bem é somar o custo de agora ao <i>custo de continuar</i> a partir do estado final.", "p")
    html += div(xs[0] + 40, y0 + 390, w - 80, None,
                "Se esse custo for exato, a janela reproduz o <b>ótimo do horizonte completo</b>.", "p")
    s += cartao(xs[1], y0, w, h, 2, "Quanto vale o kWh guardado")
    X0, X1, Y0, Y1 = xs[1] + 50, xs[1] + w - 50, y0 + 96, y0 + 330
    s += eixo(X0, X1, Y0, Y1) + curva_convexa(X0, X1, Y0, Y1, e0=.40, fs=19)
    html += eq("e18", xs[1] + 40, y0 + 398, w - 80, 56, 30)
    html += div(xs[1] + 40, y0 + 462, w - 80, None, "Em R$/kWh: o <b>valor da água</b>, agora para a energia armazenada.", "p", "font-size:22px;text-align:center")
    s += cartao(xs[2], y0, w, h, 3, "Por que não os duais do MILP")
    X0, X1, Y0, Y1 = xs[2] + 50, xs[2] + w - 50, y0 + 96, y0 + 330
    s += eixo(X0, X1, Y0, Y1) + curva_nconvexa(X0, X1, Y0, Y1)
    html += div(xs[2] + 40, y0 + 400, w - 80, None,
                "Com decisões inteiras, <i>V</i> pode ser <b>não convexa</b> ou descontínua: a derivada pode não existir e o dual não é preço.", "p", "font-size:22px")
    salvar("S15_P1_cartoes", s, html)


# ===================================================================== P2 · do valor da água ao valor da energia: gráfico grande + equações em coluna
def p2():
    s = f'<rect x="110" y="166" width="1030" height="744" rx="28" fill="{LIGHT}"/>'
    s += T(150, 226, "O valor da energia armazenada", 32, 700, NAVY, "Gelasio")
    html = div(150, 246, 950, None, "Mesma ideia do valor da água: quanto custará continuar a operação a partir da energia que sobra ao fim da janela.", "p", "font-size:22px")
    X0, X1, Y0, Y1 = 190, 1080, 350, 800
    s += eixo(X0, X1, Y0, Y1, fs=20) + curva_convexa(X0, X1, Y0, Y1, e0=.38, fs=24)
    html += eq("e18", 640, 400, 420, 70, 36)
    s += T(1080, 420, "eq. 18", 15, 600, MUTED, anchor="end")
    html += div(640, 474, 420, None, "<b>μ</b> em R$/kWh: o preço do kWh guardado", "p", "font-size:22px;text-align:center")
    X = 1190
    s += T(X, 210, "Na janela do MPC", 28, 700, NAVY, "Gelasio")
    html += eq("e17", X - 10, 226, 630, 120, 25, "flex-start")
    s += T(1810, 226, "eq. 17", 15, 600, MUTED, anchor="end")
    html += div(X, 352, 620, None, "Custo da janela + <i>custo de continuação</i> no estado final (Bellman, eq. 16). Exato ⇒ ótimo do horizonte completo.", "p", "font-size:22px")
    s += f'<rect x="{X}" y="516" width="620" height="394" rx="24" fill="{LIGHT}"/>'
    s += T(X + 36, 564, "Por que não os duais do MILP", 26, 700, NAVY, "Gelasio")
    s += eixo(X + 56, X + 580, 600, 760, icones=False, xlab="E") + curva_nconvexa(X + 56, X + 580, 600, 760, fs=17, rot=False)
    html += div(X + 36, 806, 560, None, "Com inteiros, <i>V</i> pode ser não convexa: a derivada pode não existir.", "p", "font-size:22px")
    salvar("S15_P2_valor", s, html)


# ===================================================================== P3 · a hierarquia: horizonte longo informa a janela curta
def p3():
    s, html = "", ""
    x0, x1 = 110, 1810
    # horizonte longo
    yl, ys = 210, 300
    s += T(x0, yl - 18, "Planejamento · horizonte longo", 22, 700, NAVY, "Gelasio")
    s += f'<rect x="{x0}" y="{yl}" width="{x1-x0}" height="40" rx="12" fill="#D7E6F3"/>'
    s += f'<text x="{x1-18}" y="{yl+27}" text-anchor="end" font-family="Gelasio" font-style="italic" font-weight="700" font-size="22" fill="{NAVY}">H<tspan font-size="15" dy="5">L</tspan></text>'
    cw, N = 46, 8
    s += T(x0, ys - 18, "MPC · janela de N intervalos", 22, 700, NAVY, "Gelasio")
    for t in range(N):
        s += f'<rect x="{x0+t*cw+2}" y="{ys}" width="{cw-4}" height="40" rx="7" fill="{TEAL if t==0 else "#BFD9D3"}"/>'
    xe = x0 + N * cw + 4
    s += f'<line x1="{xe}" x2="{xe}" y1="{ys-10}" y2="{ys+52}" stroke="{FUT}" stroke-width="4"/>'
    s += f'<rect x="{xe+6}" y="{ys}" width="{x1-xe-6}" height="40" rx="10" fill="none" stroke="{FUT}" stroke-width="2" stroke-dasharray="6 6"/>'
    s += T(xe + 26, ys + 27, "depois da janela: o custo de continuar entra como V(E)", 20, 700, FUT)
    html += eq("e17", 110, 372, 1700, 110, 34)
    s += T(1810, 380, "eq. 17", 15, 600, MUTED, anchor="end")
    # dois cartões comparativos
    y0, h, w = 506, 404, 838
    s += f'<rect x="110" y="{y0}" width="{w}" height="{h}" rx="24" fill="{LIGHT}"/>'
    s += T(146, y0 + 52, "O valor do kWh guardado", 26, 700, NAVY, "Gelasio")
    s += eixo(160, 520, y0 + 92, y0 + 300, fs=16) + curva_convexa(160, 520, y0 + 92, y0 + 300, e0=.40, fs=17, rot=False)
    html += eq("e18", 560, y0 + 110, 360, 60, 32)
    html += div(560, y0 + 182, 360, None, "Em R$/kWh: o <b>valor da água</b> aplicado à energia armazenada.", "p", "font-size:22px")
    s += f'<rect x="972" y="{y0}" width="{w}" height="{h}" rx="24" fill="{LIGHT}"/>'
    s += T(1008, y0 + 52, "Por que não os duais do MILP", 26, 700, NAVY, "Gelasio")
    s += eixo(1022, 1400, y0 + 92, y0 + 300, fs=16) + curva_nconvexa(1022, 1400, y0 + 92, y0 + 300, fs=16, rot=False)
    html += div(1440, y0 + 104, 340, None, "Com decisões inteiras, <i>V</i> pode ser <b>não convexa</b> ou descontínua: a derivada pode não existir.", "p", "font-size:22px")
    salvar("S15_P3_hierarquia", s, html)


if __name__ == "__main__":
    p1()
    p2()
    p3()
