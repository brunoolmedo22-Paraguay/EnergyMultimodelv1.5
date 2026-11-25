"""Slide 16 (deck, NOVO) — Gerenciamento energético hierárquico MILP–MPC: a integração (Fig. 4.1 do artigo, redesenhada).
Fonte: Seção 4 (abertura: «combina MILP, planejamento de horizonte finito e MPC para coordenar o despacho», Fig. 4.1) e 4.4 («o planejamento
de horizonte longo fornece essa informação ao problema de curto prazo, atribuindo valor à energia armazenada além do horizonte de predição»).
Conceito apenas: a implementação (reotimização paramétrica, modos, verificação do sinal) fica no slide «EMS hierárquico no SEEDS».
Cores: coordenação/valor futuro #C0532F (como nos slides 5, 14, 15); realimentação teal (slide 14); etiquetas MILP em navy, MPC em teal."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import CSS, DEFS, NAVY, SLATE, TEAL, LIGHT, LINE, BAT, PEM, MUTED, T, ICON
from gerar_slide4_v3 import SOLAR, REDE
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
FUT, WIND, PLAN = "#C0532F", "#4C8DD6", "#DCE8F3"
DEF2 = DEFS.replace("</defs>",
    f'<marker id="af" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="{FUT}"/></marker>'
    f'<linearGradient id="gf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{FUT}" stop-opacity=".24"/><stop offset="1" stop-color="{FUT}" stop-opacity="0"/></linearGradient></defs>')
CSSM = CSS + """
.d{position:absolute}
.p{font:500 22px/1.38 "Manrope";color:#4A5568}
.p b{font-weight:800;color:#14213D}
.p i{font-style:normal;color:#C0532F;font-weight:800}
.p u{text-decoration:none;color:#1F7A6D;font-weight:800}
"""
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
TIT = '<div class="tt">Gerenciamento energético hierárquico MILP–MPC</div>'
REF = "Fig. 4.1 do artigo (redesenhada) · Seção 4 e 4.4 · eq. 15 (MPC) e 17 (custo terminal) · esquema conceitual"


def div(x, y, w, h, inner, cls="", st=""):
    hh = f"height:{h}px;" if h else ""
    return f'<div class="d {cls}" style="left:{x}px;top:{y}px;width:{w}px;{hh}{st}">{inner}</div>'


def salvar(nome, s, html):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEF2}{s}</svg>'
            + html + f'<div class="ref">{REF}</div>' + rodape(16))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


def ic(k, x, y, s, c):
    return f'<svg x="{x}" y="{y}" width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c}">{ICON[k]}</svg>'


def tag(x, y, txt, cor, fill=True):
    w = 18 + len(txt) * 13
    f, c = (cor, "#fff") if fill else ("#fff", cor)
    return (f'<rect x="{x}" y="{y}" width="{w}" height="32" rx="16" fill="{f}" stroke="{cor}" stroke-width="2"/>'
            + T(x + w / 2, y + 22, txt, 16, 800, c, anchor="middle")), w


def tags(x, y, itens):
    o = ""
    for txt, cor in itens:
        t_, w = tag(x, y, txt, cor)
        o += t_
        x += w + 8
    return o


def barramento(x, y, w, r=24, rot=True, fs=15):
    """Barramento SEEDS com os recursos pendurados (identidade da capa)."""
    rec = [("sun", SOLAR, "Solar"), ("wind", WIND, "Eólica"), ("h2", PEM, "PEMFC"), ("bat", BAT, "Bateria"), ("grid", REDE, "Rede"), ("load", NAVY, "Demanda")]
    o = f'<rect x="{x}" y="{y-5}" width="{w}" height="10" rx="5" fill="url(#gb)"/>'
    n = len(rec)
    for i, (k, c, nome) in enumerate(rec):
        cx = x + w * (i + .5) / n
        cy = y + 30 + r
        o += f'<line x1="{cx}" x2="{cx}" y1="{y+5}" y2="{cy-r}" stroke="{c}" stroke-width="3"/><circle cx="{cx}" cy="{y}" r="5" fill="#fff" stroke="{c}" stroke-width="2.5"/>'
        o += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" stroke="{c}" stroke-width="2.5"/>' + ic(k, cx - r * .62, cy - r * .62, r * 1.24, c)
        if rot:
            o += T(cx, cy + r + 22, nome, fs, 600, SLATE, anchor="middle")
    return o


def mini_v(x, y, w, h):
    """V(E) em miniatura (custo futuro), igual à do slide 15."""
    n = 40
    pts = [(x + w * i / n, y + h - h * (.10 + .85 * (1 - i / n) ** 2.1)) for i in range(n + 1)]
    d = "M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in pts)
    return (f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="{NAVY}" stroke-width="1.6"/><line x1="{x}" x2="{x}" y1="{y}" y2="{y+h}" stroke="{NAVY}" stroke-width="1.6"/>'
            f'<path d="{d} L{x+w} {y+h} L{x} {y+h} Z" fill="url(#gf)"/><path d="{d}" fill="none" stroke="{FUT}" stroke-width="4" stroke-linecap="round"/>'
            + T(x + w - 2, y + h + 18, "E", 15, 700, SLATE, "Gelasio", anchor="end", it=True) + T(x + 8, y + 12, "V(E)", 16, 700, FUT, "Gelasio", it=True))


def nivel(x, y, w, h, titulo, sub, tg, cor_borda=LINE):
    o = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="#fff" stroke="{cor_borda}" stroke-width="2"/>'
    o += T(x + 30, y + 46, titulo, 26, 700, NAVY, "Gelasio")
    o += tags(x + w - 30 - sum(18 + len(t) * 13 + 8 for t, _ in tg) + 8, y + 22, tg)
    return o, div(x + 30, y + 62, w - 60, None, sub, "p", "font-size:22px")


# ===================================================================== H1 · fluxo horizontal: entradas → EMS (2 níveis) → sistema → resultados
def h1():
    s, html = "", ""
    # entradas
    s += f'<rect x="110" y="400" width="250" height="300" rx="24" fill="{LIGHT}"/>' + T(140, 450, "Entradas", 26, 700, NAVY, "Gelasio")
    html += div(140, 474, 200, None, "Previsões<br>Demanda<br>Restrições", "p", "font-size:22px;line-height:1.7")
    s += f'<line x1="362" x2="420" y1="550" y2="550" stroke="{NAVY}" stroke-width="3" marker-end="url(#ar)"/>'
    # EMS
    X, Y, W, H = 430, 170, 780, 730
    s += f'<rect x="{X}" y="{Y}" width="{W}" height="{H}" rx="30" fill="{LIGHT}"/>'
    a, b = nivel(X + 30, Y + 86, W - 60, 150, "Planejamento de horizonte ampliado", "Enxerga além da janela: <b>horizonte H<sub>L</sub></b>.", [("MILP", NAVY)])
    s += a; html += b
    # coordenação
    yc = Y + 250
    s += f'<line x1="{X+200}" x2="{X+200}" y1="{yc}" y2="{yc+150}" stroke="{FUT}" stroke-width="4" marker-end="url(#af)"/>'
    html += div(X + 232, yc + 22, 360, None, "<i>Valor futuro</i> da energia ao fim da janela (custo terminal, eq. 17)", "p", "font-size:22px")
    s += mini_v(X + 592, yc + 20, 120, 100)
    a, b = nivel(X + 30, Y + 410, W - 60, 150, "Controle preditivo operacional", "Janela de <b>N</b> intervalos; aplica os <b>m</b> primeiros (eq. 15).", [("MPC", TEAL), ("MILP", NAVY)])
    s += a; html += b
    # decisão e realimentação
    ym = Y + 485
    s += f'<line x1="{X+W-30}" x2="{1370}" y1="{ym-28}" y2="{ym-28}" stroke="{NAVY}" stroke-width="3" marker-end="url(#ar)"/>'
    s += T(1290, ym - 44, "despacho", 19, 700, NAVY, anchor="middle")
    s += f'<line x1="1370" x2="{X+W-28}" y1="{ym+28}" y2="{ym+28}" stroke="{TEAL}" stroke-width="3" stroke-dasharray="8 7" marker-end="url(#at)"/>'
    s += T(1290, ym + 62, "estado", 19, 700, TEAL, anchor="middle") + T(1290, ym + 84, "atualizado", 19, 700, TEAL, anchor="middle")
    html += div(X + 30, Y + 590, W - 60, None, "O MPC decide; o planejamento só <b>informa</b> quanto vale guardar energia.", "p", "font-size:22px;text-align:center;color:#1F7A6D")
    # sistema e resultados
    s += f'<rect x="1380" y="330" width="430" height="330" rx="24" fill="{LIGHT}"/>' + T(1412, 380, "Sistema elétrico", 26, 700, NAVY, "Gelasio")
    s += barramento(1410, 440, 370, r=22, fs=14)
    html += div(1412, 578, 380, None, "Microrrede simulada", "p", "font-size:20px;color:#7B8794")
    s += f'<line x1="1595" x2="1595" y1="662" y2="716" stroke="{NAVY}" stroke-width="3" marker-end="url(#ar)"/>'
    s += f'<rect x="1380" y="722" width="430" height="178" rx="24" fill="{LIGHT}"/>' + T(1412, 772, "Resultados", 26, 700, NAVY, "Gelasio")
    html += div(1412, 790, 380, None, "Potências, estados (SOC) e custos", "p", "font-size:22px")
    salvar("S16_H1_fluxo", s, html)


# ===================================================================== H2 · duas escalas de tempo (horizonte longo × janelas) sobre o barramento
def h2():
    s, html = "", ""
    x0, x1 = 420, 1810
    # nível 1: planejamento
    s += T(110, 214, "Planejamento", 28, 700, NAVY, "Gelasio") + T(110, 244, "horizonte ampliado", 19, 600, SLATE)
    s += tags(110, 262, [("MILP", NAVY)])
    s += f'<rect x="{x0}" y="196" width="{x1-x0}" height="60" rx="14" fill="{PLAN}"/>'
    s += T(x0 + 24, 234, "plano longo: estima o custo de continuar", 20, 700, NAVY)
    s += f'<text x="{x1-20}" y="236" text-anchor="end" font-family="Gelasio" font-style="italic" font-weight="700" font-size="24" fill="{NAVY}">H<tspan font-size="16" dy="6">L</tspan></text>'
    # nível 2: MPC com janelas deslizantes
    s += T(110, 474, "Controle preditivo", 28, 700, NAVY, "Gelasio") + T(110, 504, "operacional", 19, 600, SLATE)
    s += tags(110, 522, [("MPC", TEAL), ("MILP", NAVY)])
    cw, N = 52, 8
    for k in range(3):
        y = 410 + k * 50
        for t in range(N):
            xx = x0 + (k + t) * cw
            s += f'<rect x="{xx+2}" y="{y}" width="{cw-4}" height="38" rx="7" fill="{TEAL if t == 0 else "#BFD9D3"}"/>'
        xe = x0 + (k + N) * cw
        s += f'<line x1="{xe+3}" x2="{xe+3}" y1="{y-4}" y2="{y+42}" stroke="{FUT}" stroke-width="3.5"/>'
    # coordenação: do plano longo ao fim de cada janela
    for k in range(3):
        xe = x0 + (k + N) * cw + 3
        s += f'<line x1="{xe}" x2="{xe}" y1="258" y2="{402+k*50}" stroke="{FUT}" stroke-width="3" stroke-dasharray="3 7" marker-end="url(#af)"/>'
    s += f'<rect x="1150" y="300" width="660" height="92" rx="18" fill="#fff" stroke="{FUT}" stroke-width="2"/>'
    s += mini_v(1172, 312, 96, 62)
    html += div(1300, 312, 500, None, "<i>Valor futuro</i>: o custo de continuar entra no fim de cada janela (eq. 17)", "p", "font-size:21px")
    # decisão → sistema → estado
    yb = 760
    s += f'<line x1="{x0+cw/2}" x2="{x0+cw/2}" y1="{410+150-6}" y2="{yb-14}" stroke="{NAVY}" stroke-width="3" marker-end="url(#ar)"/>'
    s += T(x0 + cw / 2 + 14, 640, "aplica m: despacho", 20, 700, NAVY)
    s += f'<path d="M{x0+520} {yb-14} C{x0+520} 640, {x0+3*cw+cw/2} 650, {x0+3*cw+cw/2} {410+2*50+44}" fill="none" stroke="{TEAL}" stroke-width="3" stroke-dasharray="8 7" marker-end="url(#at)"/>'
    s += T(x0 + 540, 690, "estado atualizado", 20, 700, TEAL)
    s += T(110, 744, "Sistema elétrico", 28, 700, NAVY, "Gelasio") + T(110, 774, "microrrede simulada", 19, 600, SLATE)
    s += barramento(x0, yb, 920, r=26, fs=16)
    s += f'<rect x="1400" y="{yb-34}" width="410" height="156" rx="24" fill="{LIGHT}"/>' + T(1430, yb + 8, "Resultados", 26, 700, NAVY, "Gelasio")
    html += div(1430, yb + 22, 360, None, "Potências, estados (SOC) e custos", "p", "font-size:22px")
    s += f'<line x1="{x0+930}" x2="1396" y1="{yb}" y2="{yb}" stroke="{NAVY}" stroke-width="3" marker-end="url(#ar)"/>'
    salvar("S16_H2_escalas", s, html)


# ===================================================================== H3 · fluxo vertical fiel à Fig. 4.1, com o porquê de cada passagem ao lado
def h3():
    s, html = "", ""
    cx, w = 760, 760
    x = cx - w / 2

    def caixa(y, h, tit, sub, tg=None, fill="#fff", borda=LINE):
        o = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="20" fill="{fill}" stroke="{borda}" stroke-width="2"/>'
        o += T(x + 28, y + (40 if sub else h / 2 + 9), tit, 25, 700, NAVY, "Gelasio")
        if sub:
            o += T(x + 28, y + 70, sub, 20, 600, SLATE)
        if tg:
            o += tags(x + w - 28 - sum(18 + len(t) * 13 + 8 for t, _ in tg) + 8, y + (h - 32) / 2, tg)
        return o

    def seta(y1, y2, c=NAVY, mk="ar"):
        return f'<line x1="{cx}" x2="{cx}" y1="{y1}" y2="{y2}" stroke="{c}" stroke-width="3" marker-end="url(#{mk})"/>'

    s += caixa(166, 86, "Entradas do problema", "previsões · demanda · restrições", fill=LIGHT, borda=LIGHT)
    s += seta(254, 284)
    s += f'<rect x="{x-24}" y="286" width="{w+48}" height="430" rx="28" fill="none" stroke="#9DB7CF" stroke-width="2.5" stroke-dasharray="9 8"/>'
    s += T(x, 280 - 10, "", 1)
    s += caixa(306, 96, "Planejamento de horizonte ampliado", "horizonte longo", [("MILP", NAVY)])
    s += seta(404, 450, FUT, "af")
    s += f'<rect x="{cx-250}" y="452" width="500" height="54" rx="27" fill="#fff" stroke="{FUT}" stroke-width="2.5"/>'
    s += T(cx, 486, "valor futuro / custo terminal", 21, 700, FUT, anchor="middle", it=True)
    s += seta(508, 540, FUT, "af")
    s += caixa(542, 96, "Controle preditivo operacional", "janela N, aplica m", [("MPC", TEAL), ("MILP", NAVY)])
    s += seta(640, 668)
    s += f'<rect x="{cx-170}" y="670" width="340" height="40" rx="20" fill="{NAVY}"/>' + T(cx, 697, "decisão de despacho", 19, 700, "#fff", anchor="middle")
    s += seta(718, 752)
    s += f'<rect x="{x}" y="754" width="{w}" height="150" rx="20" fill="{LIGHT}"/>' + T(x + 28, 792, "Sistema elétrico", 25, 700, NAVY, "Gelasio")
    s += barramento(x + 300, 790, 440, r=20, rot=False)
    s += T(x + 28, 880, "→ potências, estados (SOC) e custos", 19, 600, SLATE)
    # realimentação
    s += (f'<path d="M{x+w} 830 H{x+w+70} V590 H{x+w+4}" fill="none" stroke="{TEAL}" stroke-width="3" stroke-dasharray="8 7" marker-end="url(#at)"/>')
    s += T(x + w + 84, 700, "estado", 19, 700, TEAL) + T(x + w + 84, 722, "atualizado", 19, 700, TEAL)
    # coluna do porquê
    X = 1300
    passos = [(330, "O planejamento enxerga além da janela, mas <b>não decide</b>: o plano longo nunca é aplicado."),
              (450, "O que passa de um nível ao outro é o <i>valor da energia</i> ao fim da janela."),
              (572, "O MPC decide com esse custo terminal e revê a decisão a cada intervalo."),
              (790, "O estado <u>realizado</u>, não o planejado, é o ponto de partida da decisão seguinte.")]
    for y, t in passos:
        html += div(X, y, 510, None, t, "p", "font-size:22px")
    salvar("S16_H3_vertical", s, html)


if __name__ == "__main__":
    h1()
    h2()
    h3()
