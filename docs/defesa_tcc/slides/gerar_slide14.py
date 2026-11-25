"""Slide 14 (deck) — Controle preditivo baseado em modelo (MPC): três propostas.
Fonte: Seções 1, 4.2 e 4.3 do artigo (eq. 15). Por quê: decisões intertemporais conhecidas só por previsões, rever a cada nova
informação [7, 14]; restrições explícitas; MPC econômico = MILP a cada atualização [16–19]. Como: resolve N intervalos, aplica m,
atualiza o estado e repete. Limite: «Sem custo terminal ou reserva mínima, a otimização tende a reduzir a energia armazenada ao fim
do horizonte» (4.2) e «O MPC não elimina os efeitos da limitação do horizonte» (4.3) → próximo slide (valor futuro).
V_f na cor do «custo futuro» do slide 4. Exemplo de N e m: Tabela 6.2 (CT-046: N = 8, Δt = 15 min, m = 1). Trajetórias: ESQUEMÁTICAS."""
import json
import math
import os
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import CSS, NAVY, SLATE, TEAL, LIGHT, LINE, BAT, MUTED, T, ICON
from gerar_slide5_v3 import DEFS3
from gerar_slide8 import NM, rodape

D = os.path.dirname(os.path.abspath(__file__))
FUT, APL, PLN = "#C0532F", "#1F7A6D", "#BFD9D3"           # custo futuro (slide 4) · aplicado · planejado e descartado
TEX = {
    "e15": r"\begin{aligned}\min_{\{d_t\}}\;\; & \sum_{t=k}^{k+N-1}\ell_{t|k}(x_t,d_t)\;+\;{\color{%s}{V_f(x_{k+N})}}\\[3pt]"
           r"\text{sujeito a}\;\; & x_{t+1}=f_{t|k}(x_t,d_t),\quad (x_t,d_t)\in Z_{t|k},\quad x_{k+N}\in X_f,\quad x_k=\hat x_k\end{aligned}" % FUT,
    "e15c": r"\min_{\{d_t\}}\sum_{t=k}^{k+N-1}\ell_{t|k}(x_t,d_t)+{\color{%s}{V_f(x_{k+N})}}\quad\text{s.a.}\;\;x_k=\hat x_k" % FUT,
    "i_vf": r"{\color{%s}{V_f}}" % FUT, "i_xk": r"\hat x_k",
}
SVG = json.loads(subprocess.run(["node", os.path.join(D, "tex2svg.js")], input=json.dumps(TEX), capture_output=True,
                                text=True, env=dict(os.environ, NODE_PATH=NM), check=True).stdout)
CSSM = CSS + """
.d{position:absolute}
.eq{display:flex;align-items:center;justify-content:center;color:#14213D}
.eq svg{overflow:visible}
.p{font:500 18px/1.45 "Manrope";color:#4A5568}
.p b{font-weight:800;color:#14213D}
.p i{font-style:normal;color:#C0532F;font-weight:800}
"""
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
TIT = '<div class="tt">Controle preditivo baseado em modelo (MPC)</div>'
REF = "eq. 15 do artigo (Seções 4.2–4.3) · [7, 14] decisões intertemporais e previsões · [16] Rawlings, Mayne e Diehl · [17–19] MPC em microrredes · trajetórias esquemáticas"


def div(x, y, w, h, inner, cls="", st=""):
    hh = f"height:{h}px;" if h else ""
    return f'<div class="d {cls}" style="left:{x}px;top:{y}px;width:{w}px;{hh}{st}">{inner}</div>'


def eq(k, x, y, w, h, px):
    return div(x, y, w, h, SVG[k], "eq", f"font-size:{px}px")


def salvar(nome, s, html):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS3}{s}</svg>'
            + html + f'<div class="ref">{REF}</div>' + rodape(14))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


def janelas(x0, y0, cw, ch, N=8, m=1, linhas=4, gap=12, rot=True, legenda=True, estreito=False):
    """Janelas deslizantes: cada linha k planeja N intervalos a partir de k; só os m primeiros são aplicados."""
    o = ""
    for k in range(linhas):
        y = y0 + k * (ch + gap)
        for t in range(N):
            x = x0 + (k * m + t) * cw
            cor = APL if t < m else PLN
            o += f'<rect x="{x+2}" y="{y}" width="{cw-4}" height="{ch}" rx="6" fill="{cor}"/>'
        # fim da janela: onde entra V_f
        xe = x0 + (k * m + N) * cw
        o += f'<line x1="{xe+3}" x2="{xe+3}" y1="{y-4}" y2="{y+ch+4}" stroke="{FUT}" stroke-width="3"/>'
        if rot:
            o += T(x0 - 14, y + ch / 2 + 7, f"k+{k}" if k else "k", 18, 700, NAVY, "Gelasio", anchor="end", it=True)
        if k < linhas - 1:   # realimentação: estado executado vira o ponto de partida seguinte
            xa = x0 + (k * m) * cw + cw / 2
            o += (f'<path d="M{xa} {y+ch+2} C{xa} {y+ch+gap}, {xa+cw} {y+ch}, {xa+cw} {y+ch+gap-2}" fill="none" stroke="{NAVY}" '
                  f'stroke-width="2.2" marker-end="url(#ar)"/>')
    if legenda:
        yl = y0 + linhas * (ch + gap) + 22
        o += f'<rect x="{x0}" y="{yl}" width="22" height="18" rx="4" fill="{APL}"/>' + T(x0 + 32, yl + 15, "aplicado (m)", 16, 700, NAVY)
        o += f'<rect x="{x0+170}" y="{yl}" width="22" height="18" rx="4" fill="{PLN}"/>' + T(x0 + 202, yl + 15, "planejado e descartado", 16, 700, NAVY)
        fx, fy = (x0, yl + 30) if estreito else (x0 + 430, yl)
        o += f'<line x1="{fx+10}" x2="{fx+10}" y1="{fy-2}" y2="{fy+20}" stroke="{FUT}" stroke-width="3"/>' + T(fx + 24, fy + 15, "fim da janela", 16, 700, FUT)
    return o


def miopia(x, y, w, h, legenda=True):
    """Energia armazenada ao longo de UMA janela: sem valor terminal ela é gasta até o mínimo; com V_f, guardada (esquemático)."""
    o = f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="{NAVY}" stroke-width="2"/>'
    o += f'<line x1="{x}" x2="{x+w}" y1="{y+h-14}" y2="{y+h-14}" stroke="{MUTED}" stroke-width="1.6" stroke-dasharray="5 5"/>'
    o += T(x + w + 6, y + h - 9, "mín.", 13, 700, MUTED)
    xe = x + w
    o += f'<line x1="{xe}" x2="{xe}" y1="{y-6}" y2="{y+h}" stroke="{FUT}" stroke-width="3"/>'
    p = lambda u, v: (x + w * u, y + 34 + (h - 34) * (1 - v))
    sem = [p(0, .62), p(.25, .66), p(.5, .55), p(.75, .32), p(1, .10)]
    com = [p(0, .62), p(.25, .68), p(.5, .66), p(.75, .62), p(1, .60)]

    def curva(pts):
        d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
        for (a, b_), (c_, d_) in zip(pts, pts[1:]):
            mx = (a + c_) / 2
            d += f" C{mx:.1f} {b_:.1f} {mx:.1f} {d_:.1f} {c_:.1f} {d_:.1f}"
        return d
    o += f'<path d="{curva(com)}" fill="none" stroke="{APL}" stroke-width="4" stroke-linecap="round"/>'
    o += f'<path d="{curva(sem)}" fill="none" stroke="{BAT}" stroke-width="4" stroke-linecap="round" stroke-dasharray="9 7"/>'
    o += f'<circle cx="{sem[-1][0]}" cy="{sem[-1][1]}" r="7" fill="{BAT}"/><circle cx="{com[-1][0]}" cy="{com[-1][1]}" r="7" fill="{APL}"/>'
    if legenda:
        o += f'<line x1="{x}" x2="{x+34}" y1="{y+14}" y2="{y+14}" stroke="{APL}" stroke-width="4"/>' + T(x + 44, y + 20, "com custo terminal", 15, 700, APL)
        o += (f'<line x1="{x+220}" x2="{x+254}" y1="{y+14}" y2="{y+14}" stroke="{BAT}" stroke-width="4" stroke-dasharray="9 7"/>'
              + T(x + 264, y + 20, "sem", 15, 700, BAT))
    o += T(x, y - 10, "energia armazenada", 14, 700, SLATE) + T(xe, y - 12, "fim da janela", 13, 700, FUT, anchor="middle")
    return o


def cartao(x, y, w, h, n, tit, corpo_html, extra=""):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="24" fill="{LIGHT}"/>'
    s += f'<circle cx="{x+44}" cy="{y+48}" r="21" fill="{NAVY}"/>' + T(x + 44, y + 56, str(n), 21, 700, "#fff", "Gelasio", anchor="middle")
    s += T(x + 80, y + 56, tit, 26, 700, NAVY, "Gelasio") + extra
    return s, corpo_html


# ===================================================================== P1 · equação + janelas + três cartões (por quê · como · limite)
def p1():
    s = f'<rect x="110" y="166" width="1700" height="190" rx="28" fill="{LIGHT}"/>'
    html = eq("e15", 130, 172, 1660, 178, 32)
    s += T(1780, 196, "eq. 15", 15, 600, MUTED, anchor="end")
    y0, h, w, gap = 386, 520, 552, 22
    xs = [110 + i * (w + gap) for i in range(3)]
    # 1 · por quê
    c1, _ = cartao(xs[0], y0, w, h, 1, "Por que MPC?", "")
    s += c1
    itens = [("cloud", "Demanda e geração futuras são conhecidas só por <b>previsões</b>; as decisões precisam ser revistas quando chega informação nova."),
             ("rev", "A <b>realimentação</b> do estado incorpora as diferenças entre o previsto e o realizado."),
             ("check", "Cada janela é um <b>MILP</b>: as mesmas restrições e decisões discretas a cada atualização (MPC econômico).")]
    for i, (k, t) in enumerate(itens):
        yy = y0 + 108 + i * 132
        s += f'<svg x="{xs[0]+36}" y="{yy}" width="34" height="34" viewBox="0 0 40 40" style="color:{TEAL}">{ICON[k]}</svg>'
        html += div(xs[0] + 84, yy - 2, w - 116, None, t, "p", "font-size:17.5px")
    # 2 · como
    c2, _ = cartao(xs[1], y0, w, h, 2, "Como funciona", "")
    s += c2
    s += janelas(xs[1] + 92, y0 + 104, 34, 34, N=8, m=1, linhas=5, gap=14, estreito=True)
    html += div(xs[1] + 36, y0 + 428, w - 72, None, "Resolve <b>N</b> intervalos, aplica os <b>m</b> primeiros, atualiza o estado <b>x̂<sub>k</sub></b> e repete.<br>"
                "<span style='color:#9AA5B1;font-size:15px'>ex.: N = 8 (2 h de 15 min), m = 1 — microrrede CT-046</span>", "p", "font-size:17.5px")
    # 3 · limite
    c3, _ = cartao(xs[2], y0, w, h, 3, "O limite: a janela acaba", "")
    s += c3
    s += miopia(xs[2] + 50, y0 + 130, w - 130, 200)
    html += div(xs[2] + 36, y0 + 380, w - 72, None, "Sem custo terminal ou reserva mínima, a otimização tende a <b>esgotar a energia armazenada</b> no fim do horizonte: nada lhe atribui valor depois dele. "
                "<i>V<sub>f</sub></i> é a peça que falta.", "p", "font-size:17.5px")
    salvar("S14_P1_cartoes", s, html)


# ===================================================================== P2 · janelas grandes à esquerda; por quê e limite à direita
def p2():
    s = f'<rect x="110" y="166" width="1700" height="132" rx="28" fill="{LIGHT}"/>'
    html = eq("e15c", 130, 170, 1560, 124, 32)
    s += T(1780, 196, "eq. 15", 15, 600, MUTED, anchor="end")
    # janelas
    s += T(110, 360, "Como funciona: a janela desliza", 28, 700, NAVY, "Gelasio")
    s += janelas(210, 394, 62, 44, N=8, m=1, linhas=6, gap=14)
    s += f'<path d="M{210+62*14+30} 394 v{6*58-14}" stroke="{NAVY}" stroke-width="0"/>'
    html += div(110, 820, 1000, None, "Resolve <b>N</b> intervalos, aplica os <b>m</b> primeiros, atualiza o estado <b>x̂<sub>k</sub></b> com o que de fato ocorreu e resolve de novo.", "p", "font-size:19px")
    # por quê
    X = 1250
    s += T(X, 360, "Por que MPC?", 28, 700, NAVY, "Gelasio")
    itens = [("cloud", "o futuro chega por <b>previsões</b>, revistas a cada atualização"), ("rev", "a <b>realimentação</b> corrige o previsto pelo realizado"),
             ("check", "cada janela é um <b>MILP</b> com as restrições da microrrede")]
    for i, (k, t) in enumerate(itens):
        yy = 392 + i * 70
        s += f'<svg x="{X}" y="{yy}" width="32" height="32" viewBox="0 0 40 40" style="color:{TEAL}">{ICON[k]}</svg>'
        html += div(X + 46, yy, 520, None, t, "p", "font-size:18px")
    # limite
    s += f'<rect x="{X-30}" y="610" width="590" height="292" rx="24" fill="{LIGHT}"/>'
    s += T(X, 652, "O limite: a janela acaba", 24, 700, NAVY, "Gelasio")
    s += miopia(X + 10, 700, 470, 120)
    html += div(X, 852, 520, None, "Sem <i>V<sub>f</sub></i>, a energia guardada é gasta até o mínimo.", "p", "font-size:17px")
    salvar("S14_P2_janelas", s, html)


# ===================================================================== P3 · laço fechado (previsão → MILP da janela → aplica m → microrrede → estado)
def p3():
    s, html = "", ""
    # laço: quatro nós num círculo, arcos com seta entre eles
    cx, cy, R = 560, 590, 255
    nos = [("Previsões", "demanda e clima", -90, "cloud"), ("MILP da janela", "N intervalos (eq. 15)", 0, "check"),
           ("Aplica m", "só o início do plano", 90, "clock"), ("Microrrede", "estado executado x̂ₖ", 180, "load")]
    for i, (t, sub, ang, k) in enumerate(nos):
        a1 = math.radians(ang + 24)
        a2 = math.radians(nos[(i + 1) % 4][2] - 24 + (360 if i == 3 else 0))
        x1, y1 = cx + R * math.cos(a1), cy + R * math.sin(a1)
        x2, y2 = cx + R * math.cos(a2), cy + R * math.sin(a2)
        s += f'<path d="M{x1:.1f} {y1:.1f} A{R} {R} 0 0 1 {x2:.1f} {y2:.1f}" fill="none" stroke="{TEAL}" stroke-width="4" marker-end="url(#at)"/>'
    for t, sub, ang, k in nos:
        x, y = cx + R * math.cos(math.radians(ang)), cy + R * math.sin(math.radians(ang))
        s += f'<rect x="{x-150}" y="{y-56}" width="300" height="112" rx="24" fill="{LIGHT}"/>'
        s += f'<svg x="{x-130}" y="{y-20}" width="40" height="40" viewBox="0 0 40 40" style="color:{TEAL}">{ICON[k]}</svg>'
        s += T(x - 78, y - 2, t, 25, 700, NAVY, "Gelasio") + T(x - 78, y + 26, sub, 15, 600, SLATE)
    s += T(cx, cy + 8, "repete a cada Δt", 20, 700, TEAL, "Gelasio", anchor="middle", it=True)
    html += eq("e15c", 1110, 166, 700, 90, 24)
    # direita: por quê + limite
    X = 1130
    s += T(X, 318, "Por que MPC?", 28, 700, NAVY, "Gelasio")
    itens = [("o futuro chega por <b>previsões</b>, revistas a cada atualização"), ("a <b>realimentação</b> corrige o previsto pelo realizado"),
             ("cada janela é um <b>MILP</b> com as restrições da microrrede")]
    for i, t in enumerate(itens):
        s += f'<circle cx="{X+12}" cy="{336+i*58+12}" r="6" fill="{TEAL}"/>'
        html += div(X + 32, 330 + i * 58, 640, None, t, "p", "font-size:18px")
    s += f'<rect x="{X-20}" y="530" width="700" height="372" rx="24" fill="{LIGHT}"/>'
    s += T(X + 10, 576, "O limite: a janela acaba", 26, 700, NAVY, "Gelasio")
    s += miopia(X + 30, 624, 560, 170)
    html += div(X + 10, 836, 650, None, "Sem custo terminal, a otimização esgota a energia armazenada no fim do horizonte. <i>V<sub>f</sub></i> é a peça que falta.", "p", "font-size:17px")
    salvar("S14_P3_laco", s, html)


if __name__ == "__main__":
    p1()
    p2()
    p3()
