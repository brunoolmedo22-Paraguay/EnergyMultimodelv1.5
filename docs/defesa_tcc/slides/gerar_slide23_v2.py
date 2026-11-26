"""Slide 23 (deck) — Estratégia de avaliação, v2: só o CONTRASTE das duas filosofias (pedido do responsável).
Dois cartões grandes: «Ligado à rede» (ilustração da microrrede industrial) × «Isolado» (ilustração da embarcação) e, embaixo, o que se espera
de cada um, com as palavras do responsável. Sem especificações (vão nos slides 24 e 25). Ilustrações vetoriais próprias, esquemáticas."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, DEF2, HEAD, NAVY, SLATE, TEAL, LIGHT, LINE, BAT, PEM, T, div, SOLAR, REDE
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
TIT = '<div class="tt">Estratégia de avaliação</div>'
MAR, MAR2, CEU = "#2F7CC0", "#9CC8EA", "#EAF3FB"
OBJ = ("Otimizar o preço final pago à concessionária", "Otimizar o uso da bateria garantindo o suprimento da carga")
DEFS = DEF2.replace("</defs>",
    f'<linearGradient id="ceu" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F3F8FC"/><stop offset="1" stop-color="#FFFFFF"/></linearGradient>'
    f'<linearGradient id="mar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{MAR2}"/><stop offset="1" stop-color="{MAR}"/></linearGradient>'
    f'<linearGradient id="pv" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2B4A7A"/><stop offset="1" stop-color="#18305A"/></linearGradient>'
    f'<linearGradient id="noite" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1B2C4F"/><stop offset="1" stop-color="#14213D"/></linearGradient></defs>')


from gerar_slide16 import ICON, ic
from gerar_slide4_v3 import G1, G2, G3
ICON2 = dict(ICON)
ICON2["fab"] = '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M5 35V20l8 5v-5l8 5v-5l8 5V8h6v27z"/><path d="M5 35h30"/></g>'
ICON2["helice"] = ('<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><circle cx="20" cy="20" r="3.5"/>'
                   '<path d="M20 16.5C18 9 20 4 24 4.5c3 .5 2 7-2.5 12.5"/><path d="M23 21.8c7.5 2 10.5 6.5 8.2 9.6-1.8 2.4-7.2-1.5-9-8.2"/>'
                   '<path d="M17 21.8c-7.3 2.6-11.7.7-11.3-3.1.3-3 6.6-2.7 11.6.9"/></g>')
NODO = {"sun": (SOLAR, "Solar"), "bat": (BAT, "Bateria"), "h2": (PEM, "PEMFC"), "fab": (NAVY, "Indústria"), "helice": (NAVY, "Propulsão")}


def icn(k, x, y, s_, c):
    return f'<svg x="{x}" y="{y}" width="{s_}" height="{s_}" viewBox="0 0 40 40" style="color:{c}">{ICON2[k]}</svg>'


def no_pend(cx, yb, k, hst=64, r=44, lab=True):
    c, nome = NODO[k]
    cy = yb + hst + r
    o = (f'<line x1="{cx}" x2="{cx}" y1="{yb+6}" y2="{cy-r}" stroke="{c}" stroke-width="4"/>'
         f'<circle cx="{cx}" cy="{yb}" r="8" fill="#fff" stroke="{c}" stroke-width="3.5"/>'
         f'<circle cx="{cx}" cy="{cy}" r="{r+10}" fill="{c}" opacity=".10"/>'
         f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" stroke="{c}" stroke-width="4"/>' + icn(k, cx - r * .62, cy - r * .62, r * 1.24, c))
    if lab:
        o += T(cx, cy + r + 32, nome, 21, 700, NAVY, anchor="middle")
    return o


def bus_h(x1, x2, y, esp=14):
    return f'<rect x="{x1}" y="{y-esp/2}" width="{x2-x1}" height="{esp}" rx="{esp/2}" fill="url(#gb)"/>'


def microrrede(ox, oy, s=1.0, escuro=False):
    """Microrrede ligada à rede, na linguagem do deck: torre (Rede) → PCC → barramento SEEDS com Solar, Bateria e Indústria pendurados,
    sobre a silhueta suave de uma planta industrial."""
    g = f'<g transform="translate({ox} {oy}) scale({s})">'
    # silhueta industrial ao fundo (mesma lógica do casco do barco)
    dentes = "".join("l90 -46 v46 " for _ in range(5))
    g += (f'<path d="M270 400 V226 {dentes} V400 Z" fill="#DCE6E5"/>'
          '<rect x="664" y="138" width="26" height="70" rx="4" fill="#DCE6E5"/>'
          '<path d="M0 400 H750" stroke="#C9D3D2" stroke-width="3"/>')
    # torre de transmissão em traço
    tx, base, h = 128, 400, 290
    w = h * .34
    g += (f'<g fill="none" stroke="{REDE}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round">'
          f'<path d="M{tx-w/2} {base} L{tx} {base-h} L{tx+w/2} {base}"/>'
          f'<path d="M{tx-w*.95} {base-h*.80} H{tx+w*.95} M{tx-w*.62} {base-h*.64} H{tx+w*.62}"/>'
          f'<path d="M{tx-w*.34} {base-h*.3} H{tx+w*.34} M{tx-w*.34} {base-h*.3} L{tx+w*.2} {base-h*.55} M{tx+w*.34} {base-h*.3} L{tx-w*.2} {base-h*.55}"/></g>')
    yb = 118
    g += f'<path d="M{tx} {base-h} C{tx+40} {yb-30}, 190 {yb}, 230 {yb}" fill="none" stroke="{REDE}" stroke-width="3.5"/>'
    g += T(tx - 48, base - h + 6, "Rede", 21, 700, NAVY, anchor="end")
    g += bus_h(230, 720, yb)
    g += f'<circle cx="230" cy="{yb}" r="12" fill="#fff" stroke="{REDE}" stroke-width="4"/>' + T(230, yb - 26, "PCC", 17, 800, REDE, anchor="middle")
    for cx, k in ((360, "sun"), (500, "bat"), (640, "fab")):
        g += no_pend(cx, yb, k)
    return g + "</g>"


def barco(ox, oy, s=1.0):
    """Embarcação isolada, na mesma linguagem: barramento SEEDS a bordo com PEMFC, Bateria, Solar e Propulsão pendurados, sobre a
    silhueta suave do casco; mar em duas linhas finas; nenhuma rede."""
    g = f'<g transform="translate({ox} {oy}) scale({s})">'
    # mar
    g += '<path d="M0 360 C90 346 180 374 270 360 S450 346 540 360 S690 374 750 360 V420 H0 Z" fill="#E3EEF8"/>'
    for j, (y, a) in enumerate(((372, .9), (394, .55))):
        g += f'<path d="M0 {y} C90 {y-12} 180 {y+12} 270 {y} S450 {y-12} 540 {y} S690 {y+12} 750 {y}" fill="none" stroke="#7FB3E2" stroke-width="3" opacity="{a}"/>'
    # casco e cabine (silhuetas)
    g += '<path d="M40 214 H690 L740 168 L716 214 L660 350 Q650 366 626 366 H120 Q96 366 88 346 Z" fill="#DCE6F2"/>'
    g += '<path d="M170 214 V150 Q170 138 182 138 H470 L530 214 Z" fill="#E7EEF7"/>'
    yb = 118
    g += bus_h(70, 690, yb)
    for cx, k in ((160, "h2"), (310, "bat"), (460, "sun"), (610, "helice")):
        g += no_pend(cx, yb, k)
    return g + "</g>"


def salvar(nome, s, h):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS}{s}</svg>'
            + h + rodape(23))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


def obj(x, y, w, txt, cor, px=30):
    return div(x, y, w, None, txt, "", f"font:700 {px}px/1.28 Gelasio,serif;color:{cor};text-align:center")


# ===================================================================== A · dois cartões claros, ilustração ao centro, objetivo embaixo
def a():
    s, h = "", ""
    for j in range(2):
        x = 110 + j * 870
        s += f'<rect x="{x}" y="170" width="830" height="740" rx="32" fill="{LIGHT}"/>'
        s += T(x + 415, 248, ["Ligado à rede", "Isolado"][j], 54, 700, NAVY, "Gelasio", anchor="middle")
        s += f'<clipPath id="c{j}"><rect x="{x+40}" y="300" width="750" height="420" rx="22"/></clipPath>'
        s += f'<g clip-path="url(#c{j})"><rect x="{x+40}" y="300" width="750" height="420" fill="url(#ceu)"/>' + (microrrede(x + 40, 300, 1.0) if j == 0 else barco(x + 40, 300, 1.0)) + "</g>"
        h += obj(x + 60, 752, 710, OBJ[j], NAVY, 32)
    salvar("S23v2_A_cartoes", s, h)


# ===================================================================== B · terra × mar: metade clara e metade escura
def b():
    s, h = "", ""
    s += f'<rect x="110" y="170" width="830" height="740" rx="32" fill="{LIGHT}"/>'
    s += f'<rect x="980" y="170" width="830" height="740" rx="32" fill="url(#noite)"/>'
    s += T(525, 250, "Ligado à rede", 56, 700, NAVY, "Gelasio", anchor="middle")
    s += T(1395, 250, "Isolado", 56, 700, "#fff", "Gelasio", anchor="middle")
    s += f'<clipPath id="ca"><rect x="150" y="290" width="750" height="410" rx="22"/></clipPath><g clip-path="url(#ca)"><rect x="150" y="290" width="750" height="410" fill="url(#ceu)"/>{microrrede(150, 290, 1.0)}</g>'
    s += f'<clipPath id="cb"><rect x="1020" y="290" width="750" height="410" rx="22"/></clipPath><g clip-path="url(#cb)"><rect x="1020" y="290" width="750" height="410" fill="url(#ceu)"/>{barco(1020, 290, 1.0)}</g>'
    s += f'<circle cx="960" cy="495" r="44" fill="#fff" stroke="{LINE}" stroke-width="3"/>' + T(960, 506, "×", 40, 700, NAVY, "Gelasio", anchor="middle")
    h += obj(170, 736, 710, OBJ[0], NAVY, 33) + obj(1040, 736, 710, OBJ[1], "#C1FF72", 33)
    salvar("S23v2_B_terra_mar", s, h)


# ===================================================================== C · ilustrações grandes sem moldura, títulos sobre elas, objetivos em faixas
def c():
    s, h = "", ""
    for j in range(2):
        x = 110 + j * 870
        cor = [REDE, PEM][j]
        s += f'<clipPath id="k{j}"><rect x="{x}" y="170" width="830" height="520" rx="32"/></clipPath>'
        s += f'<g clip-path="url(#k{j})"><rect x="{x}" y="170" width="830" height="520" fill="url(#ceu)"/>' + (microrrede(x + 20, 210, 1.05) if j == 0 else barco(x + 20, 210, 1.05)) + "</g>"
        s += f'<rect x="{x}" y="170" width="830" height="520" rx="32" fill="none" stroke="{LINE}" stroke-width="2"/>'
        s += f'<rect x="{x+30}" y="196" width="{[330, 210][j]}" height="70" rx="35" fill="{NAVY}"/>' + T(x + 30 + [330, 210][j] / 2, 244, ["Ligado à rede", "Isolado"][j], 36, 700, "#fff", "Gelasio", anchor="middle")
        s += f'<rect x="{x}" y="716" width="830" height="194" rx="28" fill="{LIGHT}"/>'
        h += obj(x + 50, 730, 740, OBJ[j], NAVY, 34).replace("text-align:center", "text-align:center;height:166px;display:flex;align-items:center;justify-content:center")
    salvar("S23v2_C_ilustracoes", s, h)


if __name__ == "__main__":
    a()
    b()
    c()
