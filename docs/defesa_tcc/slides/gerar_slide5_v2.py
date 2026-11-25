"""Slide 5 — v2: a partir da proposta C (interseção), escolhida pelo responsável.
Mais informação nos conjuntos e a LACUNA como elemento principal (texto do artigo, decomposto e destacado).
C1 interseção + coluna da lacuna (citação com destaques nas cores dos conjuntos)
C2 interseção + lupa: a lente ampliada mostra as três partes da lacuna
C3 interseção larga e detalhada + lacuna como citação sob a lente
Tratamento da energia final (glifos) e grupos dos simuladores: conforme as notas do artigo; a conferir no PDF."""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import (CSS, NAVY, SLATE, TEAL, LIGHT, LINE, LIME, SOLAR, BAT, REDE, PEM, WIND, G1, G2, G3,
                          EMS, SIM, MUTED, T, ic, nome, DEFS, HEAD, TIT, RODAPE, REF_BASE)

D = os.path.dirname(os.path.abspath(__file__))
CSS2 = CSS + """
.q{position:absolute;font:italic 400 30px/1.5 "Gelasio",Georgia,serif;color:#14213D}
.q b{font-weight:700}
.q .a{background:linear-gradient(transparent 60%,rgba(46,158,107,.30) 60%)}
.q .b{background:linear-gradient(transparent 60%,rgba(44,111,176,.26) 60%)}
.q .c{background:linear-gradient(transparent 60%,rgba(31,122,109,.30) 60%)}
.q .src{display:block;margin-top:14px;font:600 16px "Manrope";font-style:normal;color:#9AA5B1}
"""
CIT = ('…não se identificou uma abordagem que reunisse <b class="a">a composição de diferentes microrredes a partir de modelos dos equipamentos</b> '
       'e <b class="b">sua avaliação operacional sob um mesmo gerenciamento hierárquico</b>, preservando '
       '<b class="c">a rastreabilidade entre configurações, cenários e resultados</b>.')
EMS_ITENS = [("Parisio", "[17]", "livre", "sem valor final"), ("Fan", "[20]", "piso", "limite mínimo fixo"),
             ("Vivas", "[21]", "igual", "estado final imposto"), ("Kopka", "[6]", "preco", "custo predefinido"),
             ("Aaslid", "[22]", "convexo", "exige convexidade")]


def salvar(nome_arq, s, html="", ref=REF_BASE):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS}{s}</svg>'
            + html + f'<div class="ref">{ref}</div>' + RODAPE)
    open(os.path.join(D, nome_arq + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS2, body=body))


def fim(tipo, x, y, w=48, h=28):
    """Glifo compacto: energia armazenada ao longo da janela e o tratamento no fim (ESQUEMÁTICO)."""
    xb = x + w - 10
    fins = {"livre": .06, "piso": .36, "igual": .58, "preco": .46, "convexo": .46}
    ey = y + h - h * fins[tipo]
    o = f'<line x1="{x}" x2="{xb+4}" y1="{y+h}" y2="{y+h}" stroke="#C9D3DD" stroke-width="2"/>'
    o += f'<line x1="{xb}" x2="{xb}" y1="{y-2}" y2="{y+h}" stroke="#C9D3DD" stroke-width="1.6" stroke-dasharray="2 3"/>'
    y1, y2 = y + h * .42, y + h * .22
    o += (f'<path d="M{x} {y1} C{x+(xb-x)*.2} {y-4} {x+(xb-x)*.45} {y2} {x+(xb-x)*.6} {y+h*.4} S{xb-6} {ey} {xb} {ey}" '
          f'fill="none" stroke="{BAT}" stroke-width="2.6" stroke-linecap="round"/>')
    if tipo == "livre":
        o += f'<circle cx="{xb}" cy="{ey}" r="4" fill="#fff" stroke="{REDE}" stroke-width="2.2"/>'
    elif tipo == "piso":
        o += f'<line x1="{x}" x2="{xb+8}" y1="{ey}" y2="{ey}" stroke="{NAVY}" stroke-width="1.8" stroke-dasharray="4 3"/><circle cx="{xb}" cy="{ey}" r="3.2" fill="{BAT}"/>'
    elif tipo == "igual":
        o += f'<circle cx="{xb}" cy="{ey}" r="6" fill="none" stroke="{NAVY}" stroke-width="2"/><circle cx="{xb}" cy="{ey}" r="2.6" fill="{NAVY}"/>'
    elif tipo == "preco":
        o += f'<line x1="{xb-4}" x2="{xb+10}" y1="{ey+7}" y2="{ey-7}" stroke="{NAVY}" stroke-width="2.4" stroke-linecap="round"/><circle cx="{xb}" cy="{ey}" r="3.2" fill="{BAT}"/>'
    else:
        o += f'<path d="M{xb-5} {ey-13} Q{xb+3} {ey+17} {xb+11} {ey-13}" fill="none" stroke="{NAVY}" stroke-width="2.2"/><circle cx="{xb}" cy="{ey}" r="3.2" fill="{BAT}"/>'
    return o


def ems_lista(x, y, dy=64, size=21):
    o = ""
    for i, (a, r, tp, txt) in enumerate(EMS_ITENS):
        yy = y + i * dy
        o += fim(tp, x, yy - 26) + nome(x + 62, yy - 6, a, r, size) + T(x + 62, yy + 17, txt, 15, 600, SLATE)
    return o


def sim_lista(x, y, size=21, larg=False):
    o = ic("rule", x, y - 26, 30, SIM) + T(x + 40, y - 5, "estratégias predefinidas", 15, 600, SLATE)
    o += nome(x + 40, y + 24, "HOMER", "[31]", size) + nome(x + 40 + (176 if larg else 150), y + 24, "pymgrid", "[27]", size)
    y2 = y + 84
    o += ic("cal", x, y2 - 26, 30, SIM) + T(x + 40, y2 - 5, "foco no planejamento", 15, 600, SLATE)
    if larg:
        o += T(x + 40, y2 + 24, '<tspan font-family="Gelasio" font-weight="700" fill="#14213D">PyPSA · oemof · Calliope · ETHOS.FINE</tspan>', size)
    else:
        o += T(x + 40, y2 + 24, '<tspan font-family="Gelasio" font-weight="700" fill="#14213D">PyPSA · oemof</tspan>', size)
        o += T(x + 40, y2 + 52, '<tspan font-family="Gelasio" font-weight="700" fill="#14213D">Calliope · ETHOS.FINE</tspan>', size)
    return o


def venn(c1, c2, cy, r, lente_txt=None, logo=True):
    s = f'<circle cx="{c1}" cy="{cy}" r="{r}" fill="url(#ge)" stroke="{EMS}" stroke-opacity=".4" stroke-width="2.5"/>'
    s += f'<circle cx="{c2}" cy="{cy}" r="{r}" fill="url(#gs)" stroke="{SIM}" stroke-opacity=".4" stroke-width="2.5"/>'
    d = (c2 - c1) / 2
    hh = math.sqrt(r * r - d * d)
    xm = (c1 + c2) / 2
    s += f'<path d="M{xm} {cy-hh:.1f} A{r} {r} 0 0 1 {xm} {cy+hh:.1f} A{r} {r} 0 0 1 {xm} {cy-hh:.1f} Z" fill="url(#gv)"/>'
    if logo:
        s += f'<circle cx="{xm}" cy="{cy-28}" r="40" fill="#fff"/><image href="../capa/assets/seeds_icon.png" x="{xm-26}" y="{cy-56}" width="52" height="56"/>'
        s += T(xm, cy + 46, "SEEDS", 28, 700, "#fff", "Gelasio", anchor="middle")
    if lente_txt:
        s += T(xm, cy + 8, lente_txt, 24, 700, "#fff", "Gelasio", anchor="middle", it=True)
    return s, xm, hh


def marca(x, y, k, cor, l1, l2="", ok=True, anchor="start", size=19):
    icx = x if anchor == "start" else x - 30
    tx = x + 40 if anchor == "start" else x - 40
    c = NAVY if ok else MUTED
    o = ic(k, icx, y - 22, 30, cor if ok else MUTED) + T(tx, y, l1, size, 700, c, anchor=anchor)
    if l2:
        o += T(tx, y + 24, l2, 16, 600, SLATE if ok else MUTED, anchor=anchor)
    return o


# ===================================================================== C1 · interseção + coluna da lacuna
def c1():
    r, cy, a, b = 288, 560, 468, 828
    s, xm, hh = venn(a, b, cy, r)
    s += T(392, cy - 196, "EMS MILP–MPC", 28, 700, EMS, "Gelasio", anchor="middle", it=True)
    s += ems_lista(262, cy - 118)
    s += T(944, cy - 196, "Ambientes e", 28, 700, SIM, "Gelasio", anchor="middle", it=True)
    s += T(944, cy - 162, "simuladores", 28, 700, SIM, "Gelasio", anchor="middle", it=True)
    s += sim_lista(784, cy - 74, 20)
    # o que cada lado traz (acima) e o que falta (abaixo)
    s += marca(130, 214, "check", EMS, "decisões discretas e coordenação de horizontes")
    s += marca(1110, 214, "swap", SIM, "trocam a composição", anchor="end")
    s += marca(130, 900, "lock", EMS, "composição fixa: uma microrrede por estudo", ok=False, size=17)
    s += marca(1118, 900, "rule", SIM, "decisão predefinida ou planejamento", ok=False, anchor="end", size=17)
    # conexão lente → lacuna
    s += f'<path d="M{xm+40} {cy-hh+30} C 740 250, 1080 250, 1196 300" fill="none" stroke="{TEAL}" stroke-width="2.5" stroke-dasharray="8 6" marker-end="url(#at)"/>'
    # coluna da lacuna
    X = 1210
    s += f'<rect x="{X}" y="200" width="600" height="690" rx="28" fill="{LIGHT}"/>'
    s += f'<rect x="{X+48}" y="246" width="54" height="6" rx="3" fill="url(#gb)"/>'
    s += T(X + 48, 306, "A lacuna", 40, 700, NAVY, "Gelasio")
    html = (f'<div class="q" style="left:{X+48}px;top:336px;width:520px;font-size:28px">{CIT}'
            '<span class="src">texto do artigo, entre os trabalhos analisados</span></div>')
    # o que preenche
    s += f'<line x1="{X+48}" x2="{X+552}" y1="768" y2="768" stroke="{LINE}" stroke-width="2"/>'
    s += f'<circle cx="{X+76}" cy="828" r="26" fill="{G1}"/>' + T(X + 76, 838, "A", 26, 700, "#fff", "Gelasio", anchor="middle")
    s += T(X + 114, 822, "plataforma", 20, 700, NAVY, "Gelasio") + T(X + 114, 846, "modular", 20, 700, NAVY, "Gelasio")
    s += f'<circle cx="{X+316}" cy="828" r="26" fill="{G3}"/>' + T(X + 316, 838, "B", 26, 700, "#fff", "Gelasio", anchor="middle")
    s += T(X + 354, 822, "EMS hierárquico", 20, 700, NAVY, "Gelasio") + T(X + 354, 846, "MILP–MPC", 20, 700, NAVY, "Gelasio")
    salvar("S5v2_C1_coluna", s, html, REF_BASE + ' · glifos esquemáticos')


# ===================================================================== C2 · interseção + lupa
def c2():
    r, cy, a, b = 252, 500, 364, 672
    s = ""
    # cone da lupa (atrás de tudo)
    zx, zy, zr = 1462, 530, 334
    d = (b - a) / 2
    hh = math.sqrt(r * r - d * d)
    xm = (a + b) / 2
    t1, t2 = math.radians(122), math.radians(-122)
    p1 = (zx + zr * math.cos(t1), zy - zr * math.sin(t1))
    p2 = (zx + zr * math.cos(t2), zy - zr * math.sin(t2))
    s += (f'<linearGradient id="gz" x1="0" x2="1"><stop offset="0" stop-color="{G2}" stop-opacity=".22"/><stop offset="1" stop-color="{G2}" stop-opacity=".04"/></linearGradient>'
          f'<path d="M{xm} {cy-hh:.1f} L{p1[0]:.1f} {p1[1]:.1f} L{p2[0]:.1f} {p2[1]:.1f} L{xm} {cy+hh:.1f} Z" fill="url(#gz)"/>'
          f'<line x1="{xm}" y1="{cy-hh:.1f}" x2="{p1[0]:.1f}" y2="{p1[1]:.1f}" stroke="{TEAL}" stroke-width="2" stroke-dasharray="6 6"/>'
          f'<line x1="{xm}" y1="{cy+hh:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" stroke="{TEAL}" stroke-width="2" stroke-dasharray="6 6"/>')
    v, _, _ = venn(a, b, cy, r, lente_txt="lacuna", logo=False)
    s += v
    s += T(276, cy - 168, "EMS MILP–MPC", 26, 700, EMS, "Gelasio", anchor="middle", it=True)
    s += ems_lista(166, cy - 96, dy=56, size=19)
    s += T(770, cy - 168, "Ambientes e", 26, 700, SIM, "Gelasio", anchor="middle", it=True)
    s += T(770, cy - 138, "simuladores", 26, 700, SIM, "Gelasio", anchor="middle", it=True)
    s += ic("rule", 640, cy - 96, 26, SIM) + T(674, cy - 77, "estratégias predefinidas", 15, 600, SLATE)
    s += nome(674, cy - 46, "HOMER", "[31]", 19) + nome(674, cy - 16, "pymgrid", "[27]", 19)
    s += ic("cal", 640, cy + 18, 26, SIM) + T(674, cy + 37, "foco no planejamento", 15, 600, SLATE)
    for i, n_ in enumerate(["PyPSA · oemof", "Calliope", "ETHOS.FINE"]):
        s += nome(674, cy + 68 + i * 30, n_, "", 19)
    # o que cada lado traz e o que falta, sob os conjuntos
    s += marca(120, 820, "check", EMS, "decisões discretas, horizontes", size=18)
    s += marca(120, 874, "lock", EMS, "composição fixa", ok=False, size=18)
    s += marca(590, 820, "swap", SIM, "trocam a composição", size=18)
    s += marca(590, 874, "rule", SIM, "predefinida ou planejamento", ok=False, size=18)
    # lupa
    s += f'<circle cx="{zx}" cy="{zy}" r="{zr+12}" fill="#fff" stroke="url(#gb)" stroke-width="6"/>'
    s += T(zx, zy - 238, "A lacuna", 40, 700, NAVY, "Gelasio", anchor="middle")
    s += T(zx, zy - 196, "não se identificou uma abordagem que reunisse", 18, 500, SLATE, "Gelasio", anchor="middle", it=True)
    itens = [("swap", G1, "a composição de diferentes microrredes", "a partir de modelos dos equipamentos"),
             ("clock", G2, "sua avaliação operacional sob um", "mesmo gerenciamento hierárquico"),
             ("trace", G3, "a rastreabilidade entre configurações,", "cenários e resultados")]
    for i, (k, c, l1, l2) in enumerate(itens):
        yy = zy - 120 + i * 112
        s += f'<circle cx="{zx-226}" cy="{yy+8}" r="30" fill="{c}"/>' + ic(k, zx - 244, yy - 10, 36, "#fff")
        s += T(zx - 180, yy, l1, 21, 700, NAVY, "Gelasio") + T(zx - 180, yy + 28, l2, 21, 700, NAVY, "Gelasio")
    s += f'<image href="../capa/assets/seeds.png" x="{zx-120}" y="{zy+222}" width="240" height="75"/>'
    salvar("S5v2_C2_lupa", s, "", REF_BASE + ' · lacuna: texto do artigo')


# ===================================================================== C3 · interseção larga + citação sob a lente
def c3():
    r, cy, a, b = 272, 470, 785, 1135
    s, xm, hh = venn(a, b, cy, r)
    s += T(700, cy - 176, "EMS MILP–MPC", 28, 700, EMS, "Gelasio", anchor="middle", it=True)
    s += ems_lista(580, cy - 100, dy=60, size=20)
    s += T(1236, cy - 176, "Ambientes e", 28, 700, SIM, "Gelasio", anchor="middle", it=True)
    s += T(1236, cy - 142, "simuladores", 28, 700, SIM, "Gelasio", anchor="middle", it=True)
    s += sim_lista(1092, cy - 60, 20)
    # margens
    s += marca(110, 290, "check", EMS, "decisões discretas", "estados liga/desliga")
    s += marca(110, 390, "clock", EMS, "coordenação", "de horizontes")
    s += marca(110, 560, "lock", EMS, "composição fixa", "uma microrrede por estudo", ok=False)
    s += marca(1810, 290, "swap", SIM, "trocam a composição", "vários sistemas no mesmo ambiente", anchor="end")
    s += marca(1810, 560, "rule", SIM, "decisão predefinida", "ou foco no planejamento", ok=False, anchor="end")
    # lente → citação
    s += f'<path d="M{xm} {cy+hh:.1f} V{cy+hh+44:.1f}" stroke="{TEAL}" stroke-width="2.5" stroke-dasharray="6 6"/>'
    s += f'<circle cx="{xm}" cy="{cy+hh+50:.1f}" r="6" fill="{TEAL}"/>'
    s += T(xm, cy + hh + 32, "", 10)
    html = (f'<div class="q" style="left:150px;top:{cy+hh+70:.0f}px;width:1620px;text-align:center;font-size:29px;line-height:1.55">'
            f'<span style="font-style:normal;font-weight:700;color:#1F7A6D">A lacuna:</span> {CIT}</div>')
    salvar("S5v2_C3_citacao", s, html, REF_BASE + ' · lacuna: texto do artigo · glifos esquemáticos')


if __name__ == "__main__":
    c1()
    c2()
    c3()
