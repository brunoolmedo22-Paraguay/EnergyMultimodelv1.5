"""Slide 5 — Trabalhos relacionados: três propostas na identidade do deck.
A  mapa      — posicionamento QUALITATIVO (composição × gerenciamento); o SEEDS ocupa o quadrante vazio.
B  janela    — como cada EMS trata a energia ao fim da janela × simuladores; coluna SEEDS com as contribuições A e B.
C  interseção — dois conjuntos (decisão × composição); o SEEDS na interseção.
Conteúdo: só o que o artigo afirma (registrado em guia/conteudo.py e ROTEIRO_DETALHADO_v1.md, slide 3 antigo).
Números de referência de PyPSA, oemof, Calliope e ETHOS.FINE: a conferir no artigo (por isso aparecem sem número)."""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide4_v3 import CSS, NAVY, SLATE, TEAL, LIGHT, LINE, LIME, SOLAR, BAT, REDE, PEM, G1, G2, G3, T, ICON

D = os.path.dirname(os.path.abspath(__file__))
WIND = "#4C8DD6"
EMS, SIM = "#2C6FB0", "#2E9E6B"          # azul dos EMS, verde dos ambientes (dentro do gradiente SEEDS)
MUTED = "#9AA5B1"
ICON = dict(ICON)
ICON.update({
    "sun": '<circle cx="20" cy="20" r="7" fill="none" stroke="currentColor" stroke-width="3"/><g stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 3v5M20 32v5M3 20h5M32 20h5M8 8l3.5 3.5M28.5 28.5L32 32M8 32l3.5-3.5M28.5 11.5L32 8"/></g>',
    "wind": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 18v19M20 18V4M20 18l12 7M20 18L8 25"/></g><circle cx="20" cy="18" r="3" fill="currentColor"/>',
    "lock": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><rect x="9" y="18" width="22" height="17" rx="3"/><path d="M14 18v-5a6 6 0 0 1 12 0v5"/></g>',
    "swap": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M7 14h24l-6-6M33 26H9l6 6"/></g>',
    "rule": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M20 5l11 11-11 11L9 16z"/><path d="M20 27v8"/></g>',
    "cal": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><rect x="6" y="9" width="28" height="25" rx="3"/><path d="M6 17h28M13 5v7M27 5v7"/></g>',
    "trace": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="20" r="4"/><circle cx="32" cy="20" r="4"/><circle cx="20" cy="20" r="4"/><path d="M12 20h4M24 20h4"/></g>',
    "check": '<path d="M9 21l7 7 15-16" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>',
})
DEFS = (f'<defs><linearGradient id="gb" x1="0" x2="1"><stop offset="0" stop-color="{G1}"/><stop offset=".55" stop-color="{G2}"/><stop offset="1" stop-color="{G3}"/></linearGradient>'
        f'<linearGradient id="gv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{G1}"/><stop offset=".55" stop-color="{G2}"/><stop offset="1" stop-color="{G3}"/></linearGradient>'
        f'<radialGradient id="ge" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{EMS}" stop-opacity=".16"/><stop offset="1" stop-color="{EMS}" stop-opacity=".03"/></radialGradient>'
        f'<radialGradient id="gs" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{SIM}" stop-opacity=".16"/><stop offset="1" stop-color="{SIM}" stop-opacity=".03"/></radialGradient>'
        f'<linearGradient id="gq" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="{G2}" stop-opacity="0"/><stop offset="1" stop-color="{G2}" stop-opacity=".13"/></linearGradient>'
        f'<linearGradient id="gsoc" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BAT}" stop-opacity=".22"/><stop offset="1" stop-color="{BAT}" stop-opacity="0"/></linearGradient>'
        f'<linearGradient id="glime" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{LIME}" stop-opacity=".30"/><stop offset="1" stop-color="{LIME}" stop-opacity="0"/></linearGradient>'
        f'<filter id="halo" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="14"/></filter>'
        f'<marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{NAVY}"/></marker>'
        f'<marker id="at" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="{TEAL}"/></marker>'
        f'<clipPath id="cl"><circle cx="0" cy="0" r="1"/></clipPath></defs>')
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
TIT = '<div class="tt">Trabalhos relacionados</div>'
RODAPE = ('<div class="hl" style="bottom:112px"></div><div class="ft"><img src="../capa/assets/unila.png"><div class="sep"></div>'
          '<span>Engenharia de Energia · ILATIT</span><div class="sep"></div><span><b>Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>'
          '<div class="pn">5</div>')
REF_BASE = ('[6] Kopka et al. · [17] Parisio et al. · [20] Fan et al. · [21] Vivas et al. · [22] Aaslid et al. · '
            '[27] pymgrid · [31] HOMER · PyPSA, oemof, Calliope, ETHOS.FINE')


def ic(k, x, y, s, c):
    return f'<svg x="{x}" y="{y}" width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c}">{ICON[k]}</svg>'


def no(cx, cy, r, k, cor, fundo="#fff", sw=3):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fundo}" stroke="{cor}" stroke-width="{sw}"/>' + ic(k, cx - r * .6, cy - r * .6, r * 1.2, cor)


def nome(x, y, autor, ref, size=21, c=NAVY, anchor="start", rc=MUTED):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}"><tspan font-family="Gelasio" font-weight="700" font-size="{size}" fill="{c}">{autor}</tspan>'
            + (f'<tspan dx="6" font-family="Manrope" font-weight="500" font-size="{size*.72:.0f}" fill="{rc}">{ref}</tspan>' if ref else "") + '</text>')


def salvar(nome_arq, s, ref):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS}{s}</svg>'
            + f'<div class="ref">{ref}</div>' + RODAPE)
    open(os.path.join(D, nome_arq + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=body))


def blob(cx, cy, rx, ry, fill, rot=0):
    """Mancha suave (superelipse) — agrupa trabalhos sem sugerir medida."""
    pts = []
    for i in range(72):
        a = 2 * math.pi * i / 72
        r = 1 + .05 * math.sin(3 * a + .8) + .03 * math.cos(5 * a)
        pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"
    return f'<path d="{d}" fill="{fill}" transform="rotate({rot} {cx} {cy})"/>'


def pill(x, y, autor, ref, cor, anchor="start"):
    w = len(autor) * 11.9 + (len(ref) * 8.6 + 8 if ref else 0) + 42
    x0 = x if anchor == "start" else x - w / 2
    return (f'<rect x="{x0}" y="{y-21}" width="{w}" height="42" rx="21" fill="#fff" stroke="{cor}" stroke-opacity=".35" stroke-width="2"/>'
            f'<circle cx="{x0+19}" cy="{y}" r="5" fill="{cor}"/>' + nome(x0 + 32, y + 7, autor, ref, 19))


# ===================================================================== A · mapa (posicionamento qualitativo)
def mapa():
    X0, X1, Y0, Y1 = 170, 1810, 176, 836
    xm, ym = (X0 + X1) / 2, (Y0 + Y1) / 2
    s = f'<rect x="{xm}" y="{Y0}" width="{X1-xm}" height="{ym-Y0}" rx="26" fill="url(#gq)"/>'
    s += f'<line x1="{xm}" x2="{xm}" y1="{Y0+10}" y2="{Y1-10}" stroke="{LINE}" stroke-width="2" stroke-dasharray="2 8" stroke-linecap="round"/>'
    s += f'<line x1="{X0+10}" x2="{X1-10}" y1="{ym}" y2="{ym}" stroke="{LINE}" stroke-width="2" stroke-dasharray="2 8" stroke-linecap="round"/>'
    # eixos
    s += f'<path d="M{X0} {Y1} H{X1}" stroke="{NAVY}" stroke-width="2.5" marker-end="url(#ar)"/>'
    s += f'<path d="M{X0} {Y1} V{Y0}" stroke="{NAVY}" stroke-width="2.5" marker-end="url(#ar)"/>'
    s += T(X0 + 4, Y1 + 40, "composição fixa", 19, 600, SLATE)
    s += T(X1, Y1 + 40, "composição montada a partir de modelos dos equipamentos", 19, 700, NAVY, anchor="end")
    s += f'<text transform="translate({X0-26} {Y1-4}) rotate(-90)" font-family="Manrope" font-weight="600" font-size="19" fill="{SLATE}">estratégia predefinida</text>'
    s += f'<text transform="translate({X0-26} {Y0+4}) rotate(-90)" text-anchor="end" font-family="Manrope" font-weight="700" font-size="19" fill="{NAVY}">operação otimizada</text>'
    # EMS — alto, à esquerda
    s += blob(560, 360, 330, 150, "url(#ge)", -4)
    s += T(300, 262, "EMS MILP–MPC", 28, 700, EMS, "Gelasio", it=True)
    s += pill(290, 322, "Parisio", "[17]", EMS) + pill(480, 322, "Fan", "[20]", EMS)
    s += pill(350, 382, "Vivas", "[21]", EMS) + pill(540, 382, "Aaslid", "[22]", EMS)
    s += pill(420, 442, "Kopka", "[6]", EMS)
    s += T(300, 500, "decisões discretas e coordenação de horizontes,", 17, 600, SLATE)
    s += T(300, 524, "cada um avaliado em uma única microrrede", 17, 600, SLATE)
    # ambientes — baixo, à direita
    s += blob(1330, 690, 420, 118, "url(#gs)", 2)
    s += T(980, 618, "Ambientes e simuladores", 28, 700, SIM, "Gelasio", it=True)
    s += pill(980, 676, "HOMER", "[31]", SIM) + pill(1176, 676, "pymgrid", "[27]", SIM)
    s += pill(1394, 676, "PyPSA", "", SIM) + pill(1536, 676, "oemof", "", SIM)
    s += pill(1030, 736, "Calliope", "", SIM) + pill(1192, 736, "ETHOS.FINE", "", SIM)
    s += T(1400, 742, "estratégias predefinidas, modelos", 17, 600, SLATE) + T(1400, 766, "simplificados ou foco no planejamento", 17, 600, SLATE)
    # SEEDS — quadrante vazio
    sx, sy = 1470, 330
    s += f'<path d="M780 300 C 1000 230, 1250 250, {sx-58} {sy-8}" fill="none" stroke="{TEAL}" stroke-width="2.5" stroke-dasharray="8 6" marker-end="url(#at)"/>'
    s += f'<path d="M1300 596 C 1330 500, 1400 420, {sx-24} {sy+44}" fill="none" stroke="{TEAL}" stroke-width="2.5" stroke-dasharray="8 6" marker-end="url(#at)"/>'
    s += f'<circle cx="{sx}" cy="{sy}" r="60" fill="{G2}" opacity=".35" filter="url(#halo)"/>'
    s += f'<circle cx="{sx}" cy="{sy}" r="52" fill="#fff" stroke="url(#gb)" stroke-width="5"/>'
    s += f'<image href="../capa/assets/seeds_icon.png" x="{sx-34}" y="{sy-37}" width="68" height="73"/>'
    s += T(sx + 78, sy - 20, "SEEDS", 34, 700, NAVY, "Gelasio")
    for i, (k, t) in enumerate([("swap", "microrredes diferentes"), ("clock", "mesmo EMS hierárquico"), ("trace", "rastreabilidade")]):
        s += ic(k, sx + 78, sy + 4 + i * 34, 24, TEAL) + T(sx + 110, sy + 24 + i * 34, t, 19, 600, NAVY)
    salvar("S5_A_mapa", s, REF_BASE + ' · posicionamento qualitativo, segundo a revisão do artigo')


# ===================================================================== B · fim da janela + coluna SEEDS
def mini(x, y, w, h, tipo, escuro=False):
    """SOC ao longo de uma janela; o fim da janela mostra o tratamento da energia final. ESQUEMÁTICO."""
    cor = LIME if escuro else BAT
    eixo = "#3A4A6B" if escuro else "#C9D3DD"
    xb = x + w - 34                     # fronteira final da janela
    o = f'<line x1="{x}" x2="{xb}" y1="{y+h}" y2="{y+h}" stroke="{eixo}" stroke-width="2"/>'
    o += f'<line x1="{xb}" x2="{xb}" y1="{y}" y2="{y+h}" stroke="{eixo}" stroke-width="2" stroke-dasharray="3 5"/>'
    p = lambda u, v: (x + (xb - x) * u, y + h - h * v)
    if tipo == "livre":
        tr = [(0, .62), (.25, .72), (.5, .55), (.75, .3), (1, .04)]
    elif tipo == "piso":
        tr = [(0, .62), (.25, .74), (.5, .58), (.75, .40), (1, .30)]
    elif tipo == "igual":
        tr = [(0, .55), (.25, .74), (.5, .5), (.75, .4), (1, .55)]
    else:
        tr = [(0, .6), (.25, .72), (.5, .55), (.75, .42), (1, .46)]
    pts = [p(u, v) for u, v in tr]
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        cx = (x1 + x2) / 2
        d += f" C{cx:.1f} {y1:.1f} {cx:.1f} {y2:.1f} {x2:.1f} {y2:.1f}"
    o += f'<path d="{d} L{pts[-1][0]:.1f} {y+h} L{pts[0][0]:.1f} {y+h} Z" fill="{"url(#glime)" if escuro else "url(#gsoc)"}"/>'
    o += f'<path d="{d}" fill="none" stroke="{cor}" stroke-width="4" stroke-linecap="round"/>'
    ex, ey = pts[-1]
    if tipo == "livre":
        o += f'<circle cx="{ex}" cy="{ey}" r="7" fill="#fff" stroke="{REDE}" stroke-width="3"/>'
        o += T(xb + 10, ey - 12, "?", 26, 800, REDE, "Gelasio")
    elif tipo == "piso":
        o += f'<line x1="{x}" x2="{xb+20}" y1="{ey}" y2="{ey}" stroke="{NAVY}" stroke-width="2.5" stroke-dasharray="7 6"/>'
        o += f'<circle cx="{ex}" cy="{ey}" r="6" fill="{cor}"/>'
    elif tipo == "igual":
        o += f'<circle cx="{ex}" cy="{ey}" r="13" fill="none" stroke="{NAVY}" stroke-width="2.5"/><circle cx="{ex}" cy="{ey}" r="5" fill="{NAVY}"/>'
    elif tipo == "preco":
        o += f'<line x1="{xb-6}" x2="{xb+30}" y1="{ey+14}" y2="{ey-14}" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/>'
        o += f'<circle cx="{ex}" cy="{ey}" r="6" fill="{cor}"/>'
    elif tipo == "convexo":
        o += f'<path d="M{xb-6} {ey-34} Q{xb+12} {ey+40} {xb+30} {ey-34}" fill="none" stroke="{NAVY}" stroke-width="3"/>'
        o += f'<circle cx="{ex}" cy="{ey}" r="6" fill="{cor}"/>'
    elif tipo == "pwl":
        vs = [(xb - 10, y - 4), (xb + 6, y + h * .42), (xb + 16, y + h * .3), (xb + 34, y + h * .62)]
        o += f'<path d="M{" L".join(f"{a:.1f} {b:.1f}" for a, b in vs)}" fill="none" stroke="#fff" stroke-width="3" stroke-linejoin="round"/>'
        o += "".join(f'<circle cx="{a}" cy="{b}" r="3.5" fill="#fff"/>' for a, b in vs)
        o += f'<circle cx="{ex}" cy="{ey}" r="7" fill="{LIME}"/>'
    return o


def janela():
    # --- linha 1: EMS
    s = f'<rect x="110" y="172" width="1240" height="380" rx="28" fill="{LIGHT}"/>'
    s += T(150, 228, "EMS MILP–MPC", 30, 700, NAVY, "Gelasio")
    s += T(420, 227, "cada um avaliado em uma única microrrede: e a energia no fim da janela?", 19, 600, SLATE)
    casos = [("Parisio", "[17]", "livre", "sem valor final"), ("Fan", "[20]", "piso", "limite mínimo fixo"),
             ("Vivas", "[21]", "igual", "estado final imposto"), ("Kopka", "[6]", "preco", "custo predefinido"),
             ("Aaslid", "[22]", "convexo", "exige convexidade")]
    for i, (a, r, tp, txt) in enumerate(casos):
        x = 150 + i * 236
        s += f'<rect x="{x}" y="262" width="214" height="262" rx="18" fill="#fff"/>'
        s += mini(x + 22, 300, 170, 120, tp)
        s += nome(x + 22, 466, a, r, 22) + T(x + 22, 496, txt, 17, 600, SLATE)
    # --- linha 2: ambientes
    s += f'<rect x="110" y="580" width="1240" height="330" rx="28" fill="{LIGHT}"/>'
    s += T(150, 636, "Ambientes e simuladores", 30, 700, NAVY, "Gelasio")
    s += T(566, 635, "mudam a composição da microrrede", 19, 600, SLATE)
    # barramento com recursos trocáveis
    bx0, bx1, by = 170, 560, 720
    s += f'<rect x="{bx0}" y="{by-5}" width="{bx1-bx0}" height="10" rx="5" fill="url(#gb)"/>'
    for i, (k, c, tr) in enumerate([("sun", SOLAR, 0), ("wind", WIND, 1), ("h2", PEM, 1), ("bat", BAT, 0), ("grid", REDE, 0)]):
        cx = bx0 + 40 + i * 78
        dash = ' stroke-dasharray="5 5"' if tr else ""
        s += f'<line x1="{cx}" x2="{cx}" y1="{by+5}" y2="{by+44}" stroke="{c}" stroke-width="3"{dash}/>'
        s += f'<circle cx="{cx}" cy="{by+70}" r="26" fill="#fff" stroke="{c}" stroke-width="3"{dash}/>' + ic(k, cx - 15, by + 55, 30, c)
    s += T(bx0, by + 146, "recursos entram e saem da configuração", 16, 600, MUTED)
    gx = 640
    s += ic("rule", gx, 690, 34, SIM) + T(gx + 48, 704, "estratégias predefinidas ou modelos simplificados", 18, 600, SLATE)
    s += nome(gx + 48, 740, "HOMER", "[31]", 22) + nome(gx + 200, 740, "pymgrid", "[27]", 22)
    s += ic("cal", gx, 790, 34, SIM) + T(gx + 48, 804, "foco no planejamento", 18, 600, SLATE)
    s += (nome(gx + 48, 840, "PyPSA", "", 22) + T(gx + 128, 840, "·", 22, 700, MUTED) + nome(gx + 146, 840, "oemof", "", 22)
          + T(gx + 228, 840, "·", 22, 700, MUTED) + nome(gx + 246, 840, "Calliope", "", 22) + T(gx + 350, 840, "·", 22, 700, MUTED)
          + nome(gx + 368, 840, "ETHOS.FINE", "", 22))
    # --- coluna SEEDS
    X, W = 1380, 430
    s += f'<rect x="{X}" y="172" width="{W}" height="738" rx="28" fill="{NAVY}"/>'
    s += f'<image href="../capa/assets/seeds_dark.png" x="{X+40}" y="200" width="190" height="59"/>'
    # B — valor futuro: V(E) por partes (pode ser não convexa), como na Fig. 5.2 — ESQUEMÁTICO
    gx0, gx1, gy0, gy1 = X + 56, X + W - 50, 318, 446
    vv = [(0, .92), (.22, .58), (.45, .44), (.62, .40), (.80, .22), (1, .14)]
    P = [(gx0 + (gx1 - gx0) * u, gy1 - (gy1 - gy0) * v) for u, v in vv]
    lin = "M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in P)
    s += f'<path d="{lin} L{gx1} {gy1} L{gx0} {gy1} Z" fill="url(#glime)"/>'
    s += f'<path d="M{gx0} {gy0-14} V{gy1} H{gx1+14}" fill="none" stroke="#3A4A6B" stroke-width="2"/>'
    s += f'<path d="{lin}" fill="none" stroke="{LIME}" stroke-width="4" stroke-linejoin="round"/>'
    s += "".join(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="5" fill="{NAVY}" stroke="{LIME}" stroke-width="3"/>' for a, b in P)
    s += T(gx0 + 14, gy0 + 2, "V(E)", 20, 700, LIME, "Gelasio", it=True)
    s += T(gx1 + 10, gy1 + 26, "E", 18, 700, "#B9C3D6", "Gelasio", anchor="end", it=True)
    s += T(X + 40, 494, "custo futuro da energia guardada", 22, 700, "#fff", "Gelasio")
    s += T(X + 40, 522, "calculado por um planejador", 18, 600, "#B9C3D6")
    s += f'<line x1="{X+40}" x2="{X+W-40}" y1="560" y2="560" stroke="#2C3A5C" stroke-width="2"/>'
    # A — composição a partir de modelos
    by2 = 640
    s += f'<rect x="{X+40}" y="{by2-5}" width="{W-80}" height="10" rx="5" fill="url(#gb)"/>'
    for i, (k, c) in enumerate([("sun", SOLAR), ("wind", WIND), ("h2", PEM), ("bat", BAT), ("grid", REDE)]):
        cx = X + 75 + i * 70
        s += f'<line x1="{cx}" x2="{cx}" y1="{by2+5}" y2="{by2+36}" stroke="{c}" stroke-width="3"/>'
        s += f'<circle cx="{cx}" cy="{by2+58}" r="23" fill="{NAVY}" stroke="{c}" stroke-width="3"/>' + ic(k, cx - 13, by2 + 45, 26, c)
    s += T(X + 40, 770, "microrredes compostas a partir", 22, 700, "#fff", "Gelasio")
    s += T(X + 40, 798, "de modelos dos equipamentos", 22, 700, "#fff", "Gelasio")
    s += ic("trace", X + 40, 838, 26, LIME) + T(X + 76, 858, "sob o mesmo EMS, com rastreabilidade", 17, 600, LIME)
    salvar("S5_B_janela", s, REF_BASE + ' · trajetórias esquemáticas')


# ===================================================================== C · interseção
def intersecao():
    r, cy = 330, 540
    c1, c2 = 960 - 205, 960 + 205
    s = f'<circle cx="{c1}" cy="{cy}" r="{r}" fill="url(#ge)" stroke="{EMS}" stroke-opacity=".35" stroke-width="2.5"/>'
    s += f'<circle cx="{c2}" cy="{cy}" r="{r}" fill="url(#gs)" stroke="{SIM}" stroke-opacity=".35" stroke-width="2.5"/>'
    # lente
    hh = math.sqrt(r * r - 205 * 205)
    lente = f"M960 {cy-hh:.1f} A{r} {r} 0 0 1 960 {cy+hh:.1f} A{r} {r} 0 0 1 960 {cy-hh:.1f} Z"
    s += f'<path d="{lente}" fill="url(#gv)"/>'
    s += f'<circle cx="960" cy="{cy-110}" r="46" fill="#fff"/><image href="../capa/assets/seeds_icon.png" x="930" y="{cy-142}" width="60" height="65"/>'
    s += T(960, cy - 26, "SEEDS", 32, 700, "#fff", "Gelasio", anchor="middle")
    for i, (k, t) in enumerate([("swap", "composição"), ("clock", "EMS hierárquico"), ("trace", "rastreável")]):
        s += ic(k, 960 - 13, cy + 4 + i * 62, 26, "#fff") + T(960, cy + 50 + i * 62, t, 17, 700, "#fff", anchor="middle")
    # conjunto EMS
    s += T(c1 - 160, cy - 170, "EMS MILP–MPC", 30, 700, EMS, "Gelasio", anchor="middle", it=True)
    for i, (a, rf) in enumerate([("Parisio", "[17]"), ("Fan", "[20]"), ("Vivas", "[21]"), ("Kopka", "[6]"), ("Aaslid", "[22]")]):
        s += nome(c1 - 160, cy - 104 + i * 46, a, rf, 23, anchor="middle")
    # conjunto ambientes
    s += T(c2 + 160, cy - 170, "Ambientes", 30, 700, SIM, "Gelasio", anchor="middle", it=True)
    s += T(c2 + 160, cy - 136, "e simuladores", 30, 700, SIM, "Gelasio", anchor="middle", it=True)
    for i, (a, rf) in enumerate([("HOMER", "[31]"), ("pymgrid", "[27]"), ("PyPSA", ""), ("oemof", ""), ("Calliope", ""), ("ETHOS.FINE", "")]):
        s += nome(c2 + 160, cy - 80 + i * 44, a, rf, 23, anchor="middle")
    # margens: o que cada lado traz e o que falta
    def nota(x, y, k, cor, l1, l2, ok=True, anchor="start"):
        icx = x if anchor == "start" else x - 34
        tx = x + 44 if anchor == "start" else x - 44
        c = NAVY if ok else MUTED
        return (ic(k, icx, y - 24, 34, cor if ok else MUTED) + T(tx, y, l1, 20, 700, c, anchor=anchor)
                + T(tx, y + 26, l2, 17, 600, SLATE if ok else MUTED, anchor=anchor))
    s += nota(110, 300, "check", EMS, "decisões discretas", "estados liga/desliga")
    s += nota(110, 410, "clock", EMS, "coordenação", "de horizontes")
    s += nota(110, 700, "lock", EMS, "composição fixa", "uma microrrede por estudo", ok=False)
    s += nota(1810, 300, "swap", SIM, "trocam a composição", "vários sistemas no mesmo ambiente", anchor="end")
    s += nota(1810, 700, "rule", SIM, "decisão predefinida", "ou foco no planejamento", ok=False, anchor="end")
    salvar("S5_C_intersecao", s, REF_BASE)


if __name__ == "__main__":
    mapa()
    janela()
    intersecao()
