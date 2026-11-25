"""Slide 5 — v3: cartões retangulares no lugar dos círculos; o SEEDS como o VÍNCULO entre os dois lados (= a lacuna);
continuidade com o slide 4 (pergunta sobre a energia guardada no fim da janela; curva de custo futuro do slide 4).
D1 ponte    — dois cartões ligados por um barramento; o SEEDS no meio; a lacuna em três partes embaixo
D2 espelho  — mesma estrutura do slide 4 (painel claro em cima, «A lacuna» embaixo no estilo «Na microrrede, o mesmo dilema»)
D3 três     — EMS | SEEDS | simuladores, ligados ao barramento; o cartão SEEDS repete a curva de custo futuro do slide 4
A lacuna usa as palavras do artigo, separadas em três partes (conferir a frase exata no PDF)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import (CSS, NAVY, SLATE, TEAL, LIGHT, LINE, LIME, SOLAR, BAT, REDE, PEM, WIND, G1, G2, G3,
                          EMS, SIM, MUTED, T, ic, nome, DEFS, HEAD, TIT, RODAPE, REF_BASE)
from gerar_slide5_v2 import fim

D = os.path.dirname(os.path.abspath(__file__))
FUT, IMED = "#C0532F", "#2E9E6B"
DEFS3 = DEFS.replace("</defs>",
    f'<linearGradient id="gf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{FUT}" stop-opacity=".24"/><stop offset="1" stop-color="{FUT}" stop-opacity="0"/></linearGradient>'
    f'<filter id="sh" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="8" stdDeviation="14" flood-color="#14213D" flood-opacity=".12"/></filter></defs>')
EMS_ITENS = [("Parisio", "[17]", "livre", "sem valor", "final"), ("Fan", "[20]", "piso", "limite", "mínimo fixo"),
             ("Vivas", "[21]", "igual", "estado final", "imposto"), ("Kopka", "[6]", "preco", "custo", "predefinido"),
             ("Aaslid", "[22]", "convexo", "exige", "convexidade")]
LACUNA = [("swap", G1, "a composição de diferentes microrredes", "a partir de modelos dos equipamentos"),
          ("clock", G2, "sua avaliação operacional sob um", "mesmo gerenciamento hierárquico"),
          ("trace", G3, "preservando a rastreabilidade entre", "configurações, cenários e resultados")]
REF = REF_BASE + ' · lacuna: texto do artigo · glifos esquemáticos'


def salvar(nome_arq, s, ref=REF):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS3}{s}</svg>'
            + f'<div class="ref">{ref}</div>' + RODAPE)
    open(os.path.join(D, nome_arq + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=body))


def glifo(tipo, x, y, k=1.75):
    return f'<g transform="translate({x} {y}) scale({k})">{fim(tipo, 0, 0)}</g>'


def ems_tiles(x, y, w=138, gap=12, h=176):
    o = ""
    for i, (a, r, tp, l1, l2) in enumerate(EMS_ITENS):
        xx = x + i * (w + gap)
        o += f'<rect x="{xx}" y="{y}" width="{w}" height="{h}" rx="16" fill="#fff"/>'
        o += glifo(tp, xx + 22, y + 22)
        o += nome(xx + 18, y + 108, a, r, 20) + T(xx + 18, y + 134, l1, 15, 600, SLATE) + T(xx + 18, y + 154, l2, 15, 600, SLATE)
    return o


def ems_linhas(x, y, dy=50):
    o = ""
    for i, (a, r, tp, l1, l2) in enumerate(EMS_ITENS):
        yy = y + i * dy
        o += glifo(tp, x, yy - 24, 1.25) + nome(x + 80, yy, a, r, 20) + T(x + 226, yy, f"{l1} {l2}", 16, 600, SLATE)
    return o


def barra_trocavel(x, y, passo=70, r=24):
    o = f'<rect x="{x}" y="{y-5}" width="{passo*4+60}" height="10" rx="5" fill="url(#gb)"/>'
    for i, (k, c, tr) in enumerate([("sun", SOLAR, 0), ("wind", WIND, 1), ("h2", PEM, 1), ("bat", BAT, 0), ("grid", REDE, 0)]):
        cx = x + 30 + i * passo
        dash = ' stroke-dasharray="5 5"' if tr else ""
        o += f'<line x1="{cx}" x2="{cx}" y1="{y+5}" y2="{y+r+14}" stroke="{c}" stroke-width="3"{dash}/>'
        o += f'<circle cx="{cx}" cy="{y+2*r+14}" r="{r}" fill="#fff" stroke="{c}" stroke-width="3"{dash}/>' + ic(k, cx - r * .58, y + r + 14 - r * .58 + r, r * 1.16, c)
    return o


def sim_grupos(x, y, size=21, quebra=False):
    o = ic("rule", x, y - 24, 28, SIM) + T(x + 38, y - 4, "estratégias predefinidas", 15, 600, SLATE)
    o += nome(x + 38, y + 26, "HOMER", "[31]", size) + nome(x + 190, y + 26, "pymgrid", "[27]", size)
    y2 = y + 78
    o += ic("cal", x, y2 - 24, 28, SIM) + T(x + 38, y2 - 4, "foco no planejamento", 15, 600, SLATE)
    if quebra:
        o += T(x + 38, y2 + 26, '<tspan font-family="Gelasio" font-weight="700" fill="#14213D">PyPSA · oemof</tspan>', size)
        o += T(x + 38, y2 + 54, '<tspan font-family="Gelasio" font-weight="700" fill="#14213D">Calliope · ETHOS.FINE</tspan>', size)
    else:
        o += T(x + 38, y2 + 26, '<tspan font-family="Gelasio" font-weight="700" fill="#14213D">PyPSA · oemof · Calliope · ETHOS.FINE</tspan>', size)
    return o


def forte(x, y, k, cor, txt, anchor="start"):
    if anchor == "end":
        return ic(k, x - 26, y - 20, 26, cor) + T(x - 34, y, txt, 17, 700, NAVY, anchor="end")
    return ic(k, x, y - 20, 26, cor) + T(x + 34, y, txt, 17, 700, NAVY)


def falta(x, y, k, txt):
    return ic(k, x, y - 20, 26, MUTED) + T(x + 34, y, txt, 17, 600, MUTED)


def lacuna_itens(x0, y, larg=560, size=23):
    o = ""
    for i, (k, c, l1, l2) in enumerate(LACUNA):
        x = x0 + i * larg
        o += f'<circle cx="{x+30}" cy="{y+12}" r="30" fill="{c}"/>' + ic(k, x + 12, y - 6, 36, "#fff")
        o += T(x + 80, y + 4, l1, size, 700, NAVY, "Gelasio") + T(x + 80, y + 4 + size * 1.35, l2, size, 700, NAVY, "Gelasio")
    return o


def custo_futuro(x, y, w, h, rot=True):
    """A MESMA curva de custo futuro do slide 4 (forma esquemática), agora para a energia guardada."""
    n = 80
    vs = [i / n for i in range(n + 1)]
    cf = [0.05 + 0.13 / (v + 0.13) for v in vs]
    m = max(cf) * 1.05
    px = lambda v: x + w * v
    py = lambda c: y + h - h * c / m
    lin = "M" + " L".join(f"{px(v):.1f} {py(c):.1f}" for v, c in zip(vs, cf))
    o = f'<path d="{lin} L{x+w} {y+h} L{x} {y+h} Z" fill="url(#gf)"/>'
    o += f'<path d="{lin}" fill="none" stroke="{FUT}" stroke-width="5" stroke-linecap="round"/>'
    o += f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="{NAVY}" stroke-width="2"/>'
    if rot:
        o += T(x + w, py(cf[-1]) - 14, "custo futuro", 20, 700, FUT, "Gelasio", anchor="end", it=True)
        o += T(x + w, y + h + 24, "energia guardada →", 15, 600, MUTED, anchor="end")
    return o


# ===================================================================== D1 · ponte
def d1():
    s = f'<rect x="110" y="172" width="830" height="372" rx="28" fill="{LIGHT}"/>'
    s += T(150, 230, "EMS MILP–MPC", 30, 700, NAVY, "Gelasio") + forte(900, 228, "check", EMS, "decisões discretas e horizontes", "end")
    s += T(150, 272, "E a energia guardada no fim da janela?", 20, 400, SLATE, "Gelasio", it=True)
    s += ems_tiles(150, 292)
    s += falta(150, 516, "lock", "composição fixa: uma microrrede por estudo")
    s += f'<rect x="980" y="172" width="830" height="372" rx="28" fill="{LIGHT}"/>'
    s += T(1020, 230, "Ambientes e simuladores", 30, 700, NAVY, "Gelasio") + forte(1770, 228, "swap", SIM, "trocam a composição", "end")
    s += barra_trocavel(1022, 296)
    s += sim_grupos(1400, 318, 20, quebra=True)
    s += T(1022, 436, "recursos entram e saem", 15, 600, MUTED)
    s += falta(1020, 516, "rule", "estratégias predefinidas ou modelos simplificados")
    # ponte
    yb = 616
    for xs, c in ((525, EMS), (1395, SIM)):
        s += f'<line x1="{xs}" x2="{xs}" y1="544" y2="{yb}" stroke="{c}" stroke-width="4"/><circle cx="{xs}" cy="{yb}" r="8" fill="#fff" stroke="{c}" stroke-width="4"/>'
    s += f'<rect x="525" y="{yb-6}" width="870" height="12" rx="6" fill="url(#gb)"/>'
    for xs, c in ((525, EMS), (1395, SIM)):
        s += f'<circle cx="{xs}" cy="{yb}" r="8" fill="#fff" stroke="{c}" stroke-width="4"/>'
    s += f'<circle cx="960" cy="{yb}" r="54" fill="{G2}" opacity=".3" filter="url(#halo)"/>'
    s += f'<circle cx="960" cy="{yb}" r="46" fill="#fff" stroke="url(#gb)" stroke-width="5"/><image href="../capa/assets/seeds_icon.png" x="932" y="{yb-30}" width="56" height="60"/>'
    # lacuna
    s += T(110, 718, "A lacuna que o SEEDS ocupa", 32, 700, NAVY, "Gelasio")
    s += T(606, 718, "não se identificou uma abordagem que reunisse", 21, 400, SLATE, "Gelasio", it=True)
    s += lacuna_itens(110, 790, 572, 22)
    salvar("S5v3_D1_ponte", s)


# ===================================================================== D2 · espelho do slide 4
def d2():
    s = f'<rect x="110" y="168" width="1700" height="470" rx="28" fill="{LIGHT}"/>'
    s += T(150, 228, "O mesmo dilema na literatura", 32, 700, NAVY, "Gelasio")
    # EMS (branco)
    s += f'<rect x="150" y="256" width="890" height="350" rx="20" fill="#fff"/>'
    s += T(184, 304, "EMS MILP–MPC", 26, 700, EMS, "Gelasio", it=True) + forte(1006, 302, "check", EMS, "decisões discretas e horizontes", "end")
    s += T(184, 340, "E a energia guardada no fim da janela?", 19, 400, SLATE, "Gelasio", it=True)
    for i, (a, r, tp, l1, l2) in enumerate(EMS_ITENS):
        xx = 184 + i * 166
        s += glifo(tp, xx, 366) + nome(xx, 456, a, r, 20) + T(xx, 482, l1, 15, 600, SLATE) + T(xx, 502, l2, 15, 600, SLATE)
    s += f'<line x1="184" x2="1006" y1="532" y2="532" stroke="{LINE}" stroke-width="2"/>'
    s += falta(184, 574, "lock", "composição fixa: cada um avaliado em uma única microrrede")
    # simuladores (branco)
    s += f'<rect x="1070" y="256" width="700" height="350" rx="20" fill="#fff"/>'
    s += T(1104, 304, "Ambientes e simuladores", 26, 700, SIM, "Gelasio", it=True)
    s += forte(1104, 346, "swap", SIM, "trocam a composição")
    s += sim_grupos(1104, 410)
    s += f'<line x1="1104" x2="1736" y1="532" y2="532" stroke="{LINE}" stroke-width="2"/>'
    s += falta(1104, 574, "rule", "estratégias predefinidas, modelos simplificados")
    # lacuna, no estilo de «Na microrrede, o mesmo dilema»
    s += T(110, 702, "A lacuna", 30, 700, NAVY, "Gelasio")
    s += T(252, 702, "não se identificou uma abordagem que reunisse", 19, 400, SLATE, "Gelasio", it=True)
    itens = [("swap", "Diferentes microrredes", "compostas a partir de modelos"),
             ("clock", "Um mesmo gerenciamento", "hierárquico na operação"),
             ("trace", "Rastreabilidade", "configurações · cenários · resultados")]
    for i, (k, t1, t2) in enumerate(itens):
        x = 110 + i * 400
        s += f'<circle cx="{x+30}" cy="{790}" r="30" fill="{NAVY}"/>' + ic(k, x + 12, 772, 36, "#fff")
        s += T(x + 78, 784, t1, 21, 700, NAVY, "Gelasio") + T(x + 78, 810, t2, 17, 600, SLATE)
    # SEEDS reúne
    s += f'<rect x="1400" y="736" width="410" height="112" rx="56" fill="#fff" stroke="url(#gb)" stroke-width="4" filter="url(#sh)"/>'
    s += f'<image href="../capa/assets/seeds.png" x="1428" y="758" width="220" height="68"/>'
    s += T(1660, 786, "reúne os", 18, 700, TEAL) + T(1660, 810, "dois lados", 18, 700, TEAL)
    s += f'<path d="M1322 790 h60" stroke="{TEAL}" stroke-width="2.5" stroke-dasharray="8 6" marker-end="url(#at)"/>'
    salvar("S5v3_D2_espelho", s)


# ===================================================================== D3 · três cartões no barramento
def d3():
    y0, h = 172, 446
    # EMS
    s = f'<rect x="110" y="{y0}" width="610" height="{h}" rx="28" fill="{LIGHT}"/>'
    s += T(146, y0 + 56, "EMS MILP–MPC", 28, 700, NAVY, "Gelasio")
    s += forte(146, y0 + 96, "check", EMS, "decisões discretas e horizontes")
    s += T(146, y0 + 142, "E a energia guardada no fim da janela?", 19, 400, SLATE, "Gelasio", it=True)
    s += ems_linhas(146, y0 + 192, 46)
    s += falta(146, y0 + h - 30, "lock", "composição fixa")
    # simuladores
    s += f'<rect x="1200" y="{y0}" width="610" height="{h}" rx="28" fill="{LIGHT}"/>'
    s += T(1236, y0 + 56, "Ambientes e simuladores", 28, 700, NAVY, "Gelasio")
    s += forte(1236, y0 + 96, "swap", SIM, "trocam a composição")
    s += barra_trocavel(1240, y0 + 136, 66, 22)
    s += sim_grupos(1236, y0 + 270, 19)
    s += falta(1236, y0 + h - 30, "rule", "estratégia predefinida ou planejamento")
    # SEEDS — o vínculo
    s += f'<rect x="750" y="{y0-6}" width="420" height="{h+12}" rx="28" fill="#fff" stroke="url(#gb)" stroke-width="5" filter="url(#sh)"/>'
    s += f'<image href="../capa/assets/seeds.png" x="796" y="{y0+26}" width="230" height="72"/>'
    s += custo_futuro(796, y0 + 130, 330, 120)
    s += T(796, y0 + 300, "custo futuro da energia guardada,", 18, 700, NAVY, "Gelasio")
    s += T(796, y0 + 324, "calculado por um planejador", 18, 700, NAVY, "Gelasio")
    pas = 62
    s += f'<rect x="796" y="{y0+360}" width="{pas*4+54}" height="8" rx="4" fill="url(#gb)"/>'
    for i, (k, c) in enumerate([("sun", SOLAR), ("wind", WIND), ("h2", PEM), ("bat", BAT), ("grid", REDE)]):
        cx = 823 + i * pas
        s += f'<line x1="{cx}" x2="{cx}" y1="{y0+368}" y2="{y0+382}" stroke="{c}" stroke-width="3"/><circle cx="{cx}" cy="{y0+402}" r="20" fill="#fff" stroke="{c}" stroke-width="3"/>' + ic(k, cx - 12, y0 + 390, 24, c)
    # setas de vínculo
    for xa, xb_ in ((724, 746), (1196, 1174)):
        s += f'<path d="M{xa} {y0+h/2} L{xb_} {y0+h/2}" stroke="{TEAL}" stroke-width="3" marker-end="url(#at)"/>'
    # lacuna
    s += f'<line x1="960" x2="960" y1="{y0+h+8}" y2="{y0+h+46}" stroke="{TEAL}" stroke-width="2.5" stroke-dasharray="6 6"/>'
    s += T(960, 712, "A lacuna: não se identificou uma abordagem que reunisse", 26, 700, NAVY, "Gelasio", anchor="middle")
    s += lacuna_itens(110, 784, 572, 22)
    salvar("S5v3_D3_tres", s)


if __name__ == "__main__":
    d1()
    d2()
    d3()
