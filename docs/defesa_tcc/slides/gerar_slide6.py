"""Slide 6 — Objetivos e contribuições: quatro propostas.
G1 pergunta em destaque + quatro cartões de objetivos (estilo do sumário)
G2 as duas metades da pergunta → contribuições A e B; objetivo 3 como ponte entre elas (estilo do slide 5)
G3 barramento: objetivos pendurados no barramento SEEDS (estilo da capa); pilares embaixo
G4 contrato: pergunta num cartão escuro + lista de objetivos com caixas a marcar no slide 25
Pergunta guia, objetivo geral (texto do artigo) e específicos (derivados do artigo) — VALIDAR a redação com o orientador.
Cores: A = composição (verde do slide 5), B = gerenciamento (azul do slide 5)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import CSS, NAVY, SLATE, TEAL, LIGHT, LINE, LIME, G1, G2, G3, MUTED, T, ICON
from gerar_slide5_v3 import DEFS3

D = os.path.dirname(os.path.abspath(__file__))
A, B = "#2E9E6B", "#2C6FB0"
ICON = dict(ICON)
ICON.update({
    "factory": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M4 35V19l9 5v-5l9 5V12h6l2 23z"/><path d="M4 35h32"/></g>',
    "ship": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M4 24h32l-5 9H9z"/><path d="M11 24V15h14v9M17 15V9h6"/></g>',
    "grow": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 34h30"/><path d="M8 28l8-8 6 5 11-12"/><path d="M26 13h7v7"/></g>',
    "nodes": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M5 20h30"/><circle cx="11" cy="31" r="4"/><circle cx="20" cy="31" r="4"/><circle cx="29" cy="31" r="4"/><path d="M11 20v7M20 20v7M29 20v7"/><circle cx="20" cy="9" r="4"/><path d="M20 13v7"/></g>',
    "q": '<text x="20" y="30" text-anchor="middle" font-family="Gelasio" font-weight="700" font-size="28" fill="currentColor">?</text>',
})
CSS6 = CSS + """
.d{position:absolute}
.perg{font:700 44px/1.24 "Gelasio",Georgia,serif;color:#14213D}
.perg .a{color:#2E9E6B}.perg .b{color:#2C6FB0}
.og{font:500 21px/1.5 "Manrope";color:#4A5568}.og b{font-weight:700;color:#14213D}
.ot{font:700 25px/1.28 "Gelasio",Georgia,serif;color:#14213D}
.sm{font:600 16px/1.4 "Manrope";color:#9AA5B1}
"""
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
TIT = '<div class="tt">Objetivos e contribuições</div>'
RODAPE = ('<div class="hl" style="bottom:112px"></div><div class="ft"><img src="../capa/assets/unila.png"><div class="sep"></div>'
          '<span>Engenharia de Energia · ILATIT</span><div class="sep"></div><span><b>Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>'
          '<div class="pn">6</div>')

PERG = ('<span class="b">Um mesmo gerenciamento energético</span> consegue operar '
        '<span class="a">microrredes de composições diferentes</span>, considerando '
        '<span class="b">o valor futuro da energia armazenada</span>?')
OG = ('Apresentar o desenvolvimento do SEEDS e avaliar, por meio de estudos computacionais, sua capacidade de '
      'representar diferentes configurações de microrredes e coordenar o despacho energético sob restrições operacionais.')
OBJ = [  # (nº, ícones, pilar, texto)
    (1, ["nodes"], "A", "Integrar modelos físicos dos equipamentos em uma representação energética comum"),
    (2, ["clock"], "B", "Integrar um EMS hierárquico MILP–MPC com sinal de valor futuro"),
    (3, ["factory", "ship"], "AB", "Avaliar em dois sistemas distintos: microrrede industrial e embarcação híbrida"),
    (4, ["grow"], "A", "Verificar a expansibilidade e o desempenho computacional"),
]
COR = {"A": A, "B": B, "AB": G2}
PILAR = {"A": "A · plataforma", "B": "B · EMS hierárquico", "AB": "A + B"}


def ic(k, x, y, s, c):
    return f'<svg x="{x}" y="{y}" width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c}">{ICON[k]}</svg>'


def div(x, y, w, inner, cls="", st=""):
    return f'<div class="d {cls}" style="left:{x}px;top:{y}px;width:{w}px;{st}">{inner}</div>'


def chip(x, y, p, anchor="start"):
    t = PILAR[p]
    w = len(t) * 9.4 + 30
    x0 = x if anchor == "start" else x - w
    c = COR[p]
    return (f'<rect x="{x0}" y="{y}" width="{w}" height="32" rx="16" fill="#fff" stroke="{c}" stroke-width="2"/>'
            + T(x0 + w / 2, y + 22, t, 15, 700, c, anchor="middle"))


def letra(cx, cy, r, p, txt=None):
    fill = "url(#gb)" if p == "AB" else COR[p]
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>' + T(cx, cy + r * .36, txt or p, r * 1.05, 700, "#fff", "Gelasio", anchor="middle")


def salvar(nome, s, html=""):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS3}{s}</svg>'
            + html + RODAPE)
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS6, body=body))


# ===================================================================== G1 · pergunta + quatro cartões
def g1():
    html = div(110, 176, 1700, PERG, "perg", "font-size:42px")
    s = f'<rect x="110" y="310" width="64" height="6" rx="3" fill="url(#gb)"/>'
    html += div(110, 330, 1700, f'<b>Objetivo geral.</b> {OG}', "og", "font-size:20px")
    w, gap, y, h = 407, 24, 468, 436
    for i, (n, ics, p, txt) in enumerate(OBJ):
        x = 110 + i * (w + gap)
        c = COR[p]
        s += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="24" fill="{c if p != "AB" else "url(#gb)"}"/>'
        s += f'<rect x="{x}" y="{y+6}" width="{w}" height="{h-6}" rx="24" fill="{LIGHT}"/>'
        s += T(x + 34, y + 112, f"0{n}", 84, 700, c, "Gelasio")
        for j, k in enumerate(ics):
            s += ic(k, x + w - 82 - j * 56, y + 44, 48, c)
        s += chip(x + 34, y + 150, p)
        html += div(x + 34, y + 240, w - 68, txt, "ot", "font-size:27px")
    salvar("S6_G1_cartoes", s, html)


# ===================================================================== G2 · as duas metades da pergunta
def g2():
    html = div(110, 176, 1700, PERG, "perg", "font-size:40px")
    html += div(110, 290, 1700, f'<b>Objetivo geral.</b> {OG}', "og", "font-size:19px")
    s = ""
    y, h = 392, 330
    for (x, p, titulo, metade, itens, fluxo) in [
        (110, "A", "Plataforma modular", "microrredes de composições diferentes", [OBJ[0], OBJ[3]],
         ["modelos dos equipamentos", "representação comum", "EMS"]),
        (975, "B", "EMS hierárquico MILP–MPC", "um mesmo gerenciamento, com o valor futuro", [OBJ[1]],
         ["planejador", "sinal de valor futuro", "MPC"])]:
        c = COR[p]
        w = 835
        s += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="28" fill="{LIGHT}"/>'
        s += letra(x + 66, y + 66, 32, p)
        s += T(x + 116, y + 64, titulo, 32, 700, NAVY, "Gelasio")
        s += T(x + 116, y + 94, f"«{metade}»", 18, 400, c, "Gelasio", it=True)
        # fluxo
        fx, fy = x + 40, y + 132
        for k, t in enumerate(fluxo):
            fw = len(t) * 10.2 + 52
            pts = f"{fx},{fy} {fx+fw-16},{fy} {fx+fw},{fy+21} {fx+fw-16},{fy+42} {fx},{fy+42}" + ("" if k == 0 else f" {fx+16},{fy+21}")
            s += f'<polygon points="{pts}" fill="{c}" opacity="{0.55 + 0.2*k}"/>' + T(fx + (28 if k else 18), fy + 28, t, 17, 700, "#fff")
            fx += fw + 6
        for j, (n, ics, pp, txt) in enumerate(itens):
            yy = y + 226 + j * 62
            s += f'<circle cx="{x+60}" cy="{yy}" r="20" fill="#fff" stroke="{c}" stroke-width="3"/>' + T(x + 60, yy + 7, str(n), 20, 700, c, "Gelasio", anchor="middle")
            html += div(x + 96, yy - 16, w - 140, txt, "ot", "font-size:22px")
    # ponte: objetivo 3
    yb = 776
    for xs, c in ((527, A), (1392, B)):
        s += f'<line x1="{xs}" x2="{xs}" y1="{y+h}" y2="{yb}" stroke="{c}" stroke-width="4"/><circle cx="{xs}" cy="{yb}" r="8" fill="#fff" stroke="{c}" stroke-width="4"/>'
    s += f'<rect x="527" y="{yb-6}" width="865" height="12" rx="6" fill="url(#gb)"/>'
    for xs, c in ((527, A), (1392, B)):
        s += f'<circle cx="{xs}" cy="{yb}" r="8" fill="#fff" stroke="{c}" stroke-width="4"/>'
    s += f'<circle cx="960" cy="{yb}" r="24" fill="#fff" stroke="url(#gb)" stroke-width="4"/>' + T(960, yb + 9, "3", 24, 700, G2, "Gelasio", anchor="middle")
    s += T(960, yb + 66, "Avaliar nos dois sistemas", 26, 700, NAVY, "Gelasio", anchor="middle")
    s += ic("factory", 560, yb + 76, 40, NAVY) + T(610, yb + 104, "microrrede industrial conectada · C1–C4", 19, 600, SLATE)
    s += ic("ship", 1360 - 40, yb + 76, 40, NAVY) + T(1310, yb + 104, "embarcação híbrida isolada · C5–C6", 19, 600, SLATE, anchor="end")
    salvar("S6_G2_metades", s, html)


# ===================================================================== G3 · barramento de objetivos
def g3():
    html = div(110, 184, 660, PERG, "perg", "font-size:40px;line-height:1.28")
    s = f'<rect x="110" y="560" width="64" height="6" rx="3" fill="url(#gb)"/>'
    html += div(110, 584, 660, f'<b>Objetivo geral.</b> {OG}', "og", "font-size:20px")
    # barramento com logo
    x0, x1, yb = 860, 1810, 356
    s += f'<image href="../capa/assets/seeds.png" x="{(x0+x1)/2-150}" y="182" width="300" height="93"/>'
    s += f'<line x1="{(x0+x1)/2}" x2="{(x0+x1)/2}" y1="282" y2="{yb-8}" stroke="{TEAL}" stroke-width="2" stroke-dasharray="8 6"/>'
    s += f'<rect x="{x0}" y="{yb-6}" width="{x1-x0}" height="12" rx="6" fill="url(#gb)"/>'
    passo = (x1 - x0) / 4
    for i, (n, ics, p, txt) in enumerate(OBJ):
        cx = x0 + passo * (i + .5)
        c = COR[p]
        cs = "url(#gb)" if p == "AB" else c
        s += f'<line x1="{cx}" x2="{cx}" y1="{yb+6}" y2="{yb+64}" stroke="{c}" stroke-width="3"/><circle cx="{cx}" cy="{yb}" r="7" fill="#fff" stroke="{c}" stroke-width="3"/>'
        s += f'<circle cx="{cx}" cy="{yb+112}" r="48" fill="#fff" stroke="{cs}" stroke-width="4"/>'
        if len(ics) == 1:
            s += ic(ics[0], cx - 24, yb + 88, 48, c)
        else:
            s += ic(ics[0], cx - 38, yb + 92, 38, c) + ic(ics[1], cx + 0, yb + 92, 38, c)
        s += f'<circle cx="{cx+38}" cy="{yb+74}" r="17" fill="{c if p != "AB" else G2}"/>' + T(cx + 38, yb + 81, str(n), 19, 700, "#fff", "Gelasio", anchor="middle")
        html += div(cx - 112, yb + 182, 224, txt, "ot", "font-size:21px;text-align:center")
    # pilares
    yp = 780
    for x, p, t1, t2 in ((860, "A", "Plataforma modular", "composição a partir de modelos"),
                         (1345, "B", "EMS hierárquico", "MILP–MPC com valor futuro")):
        s += f'<rect x="{x}" y="{yp}" width="465" height="112" rx="56" fill="{LIGHT}"/>'
        s += letra(x + 56, yp + 56, 34, p)
        s += T(x + 108, yp + 50, t1, 24, 700, NAVY, "Gelasio") + T(x + 108, yp + 78, t2, 17, 600, SLATE)
    salvar("S6_G3_barramento", s, html)


# ===================================================================== G4 · contrato com a banca
def g4():
    s = f'<rect x="110" y="172" width="640" height="730" rx="28" fill="{NAVY}"/>'
    s += T(150, 290, "?", 110, 700, LIME, "Gelasio")
    perg = PERG.replace('class="b"', 'style="color:#C1FF72"').replace('class="a"', 'style="color:#C1FF72"')
    html = div(150, 330, 560, perg, "perg", "font-size:42px;line-height:1.3;color:#fff")
    s += f'<line x1="150" x2="710" y1="812" y2="812" stroke="#2C3A5C" stroke-width="2"/>'
    s += T(150, 856, "respondida nas conclusões", 19, 600, "#B9C3D6") + T(710, 856, "slide 25 →", 19, 700, LIME, anchor="end")
    # objetivo geral + específicos
    X = 810
    s += T(X, 214, "Objetivo geral", 28, 700, NAVY, "Gelasio")
    html += div(X, 232, 1000, OG, "og", "font-size:19px")
    onde = ["slides 7, 11 e 12", "slides 10, 13 e 21", "slides 15 a 23", "slide 24"]
    y0, dy = 410, 122
    s += T(X, y0 - 22, "Objetivos específicos", 28, 700, NAVY, "Gelasio")
    for i, (n, ics, p, txt) in enumerate(OBJ):
        y = y0 + i * dy
        c = COR[p]
        s += f'<line x1="{X}" x2="1810" y1="{y+6}" y2="{y+6}" stroke="{LINE}" stroke-width="1.5"/>'
        s += f'<rect x="{X}" y="{y+36}" width="40" height="40" rx="10" fill="#fff" stroke="{TEAL}" stroke-width="3"/>'
        s += T(X + 70, y + 72, f"0{n}", 40, 700, c if p != "AB" else G2, "Gelasio")
        html += div(X + 150, y + 30, 520, txt, "ot", "font-size:23px")
        s += chip(1810, y + 34, p, anchor="end")
        s += T(1810, y + 98, onde[i], 16, 600, MUTED, anchor="end")
    salvar("S6_G4_contrato", s, html)


if __name__ == "__main__":
    g1()
    g2()
    g3()
    g4()


# ===================================================================== v2 (a partir da G4): objetivo geral em largura total
OG_REALCE = ('Apresentar <b>o desenvolvimento do SEEDS</b> e avaliar, por meio de estudos computacionais, sua capacidade de '
             '<b>representar diferentes configurações de microrredes</b> e <b>coordenar o despacho energético</b> sob restrições operacionais.')
CSS6 += """
.ogg{font:400 31px/1.42 "Gelasio",Georgia,serif;color:#14213D}
.ogg b{font-weight:700;color:#1F7A6D}
"""


def g4v2(nome, estilo):
    s = ""
    if estilo == "cartao":
        s += f'<rect x="110" y="172" width="1700" height="214" rx="28" fill="{LIGHT}"/>'
        s += f'<rect x="138" y="204" width="8" height="150" rx="4" fill="url(#gv)"/>'
        s += T(172, 226, "Objetivo geral", 26, 700, TEAL, "Gelasio")
        html = div(172, 244, 1600, OG_REALCE, "ogg")
    else:  # aberto: rótulo à esquerda, texto grande, filete com o gradiente embaixo
        s += T(110, 218, "Objetivo geral", 26, 700, TEAL, "Gelasio")
        html = div(110, 236, 1700, OG_REALCE, "ogg", "font-size:33px")
        s += f'<rect x="110" y="384" width="1700" height="5" rx="2.5" fill="url(#gb)"/>'
    # pergunta
    y0 = 420
    s += f'<rect x="110" y="{y0}" width="640" height="{902-y0}" rx="28" fill="{NAVY}"/>'
    s += T(150, y0 + 104, "?", 96, 700, LIME, "Gelasio")
    perg = PERG.replace('class="b"', 'style="color:#C1FF72"').replace('class="a"', 'style="color:#C1FF72"')
    html += div(150, y0 + 130, 570, perg, "perg", "font-size:37px;line-height:1.32;color:#fff")
    # objetivos específicos
    X = 810
    s += T(X, y0 + 34, "Objetivos específicos", 28, 700, NAVY, "Gelasio")
    yl, dy = y0 + 62, 105
    for i, (n, ics, p, txt) in enumerate(OBJ):
        y = yl + i * dy
        c = COR[p] if p != "AB" else G2
        s += f'<line x1="{X}" x2="1810" y1="{y}" y2="{y}" stroke="{LINE}" stroke-width="1.5"/>'
        s += f'<rect x="{X}" y="{y+32}" width="40" height="40" rx="10" fill="#fff" stroke="{TEAL}" stroke-width="3"/>'
        s += T(X + 70, y + 68, f"0{n}", 40, 700, c, "Gelasio")
        k = ics[0] if len(ics) == 1 else None
        html += div(X + 152, y + 22, 700, txt, "ot", "font-size:25px")
        if k:
            s += ic(k, 1810 - 44, y + 30, 44, c)
        else:
            s += ic(ics[1], 1810 - 44, y + 30, 44, c) + ic(ics[0], 1810 - 96, y + 30, 44, c)
    s += f'<line x1="{X}" x2="1810" y1="{yl+4*dy}" y2="{yl+4*dy}" stroke="{LINE}" stroke-width="1.5"/>'
    salvar(nome, s, html)


g4v2("S6v2_H1_cartao", "cartao")
g4v2("S6v2_H2_aberto", "aberto")


# ===================================================================== v3 (APROVADO): H2 com objetivo geral todo em negrito escuro,
# sem ícones nos objetivos específicos e sem o «?» — só a pergunta.
def g6_final(nome="S6v3_final"):
    global TIT
    TIT = '<div class="tt">Objetivos</div>'   # as contribuições passaram para o slide 7 (O SEEDS)
    s = T(110, 218, "Objetivo geral", 26, 700, TEAL, "Gelasio")
    html = div(110, 236, 1700, OG, "ogg", "font-size:33px;font-weight:700;color:#14213D")
    s += f'<rect x="110" y="384" width="1700" height="5" rx="2.5" fill="url(#gb)"/>'
    y0 = 420
    s += f'<rect x="110" y="{y0}" width="640" height="{902-y0}" rx="28" fill="{NAVY}"/>'
    perg = PERG.replace('class="b"', 'style="color:#C1FF72"').replace('class="a"', 'style="color:#C1FF72"')
    html += div(150, y0, 570, f"<div>{perg}</div>", "perg",
                f"font-size:40px;line-height:1.32;color:#fff;height:{902-y0}px;display:flex;align-items:center")
    X = 810
    s += T(X, y0 + 34, "Objetivos específicos", 28, 700, NAVY, "Gelasio")
    yl, dy = y0 + 62, 105
    for i, (n, ics, p, txt) in enumerate(OBJ):
        y = yl + i * dy
        c = COR[p] if p != "AB" else G2
        s += f'<line x1="{X}" x2="1810" y1="{y}" y2="{y}" stroke="{LINE}" stroke-width="1.5"/>'
        s += f'<rect x="{X}" y="{y+32}" width="40" height="40" rx="10" fill="#fff" stroke="{TEAL}" stroke-width="3"/>'
        s += T(X + 70, y + 68, f"0{n}", 40, 700, c, "Gelasio")
        html += div(X + 152, y + 22, 840, txt, "ot", "font-size:26px")
    s += f'<line x1="{X}" x2="1810" y1="{yl+4*dy}" y2="{yl+4*dy}" stroke="{LINE}" stroke-width="1.5"/>'
    salvar(nome, s, html)


g6_final()
