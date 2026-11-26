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


def painel_pv(x, y, w, h, ang=0, cols=4, rows=2):
    o = f'<g transform="translate({x} {y}) skewX({ang})"><rect width="{w}" height="{h}" rx="3" fill="url(#pv)" stroke="#0E1E3A" stroke-width="1.5"/>'
    for i in range(1, cols):
        o += f'<line x1="{w*i/cols}" x2="{w*i/cols}" y1="0" y2="{h}" stroke="#7FA3D6" stroke-width="1" opacity=".6"/>'
    for j in range(1, rows):
        o += f'<line x1="0" x2="{w}" y1="{h*j/rows}" y2="{h*j/rows}" stroke="#7FA3D6" stroke-width="1" opacity=".6"/>'
    return o + "</g>"


def sol(cx, cy, r=26):
    o = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{SOLAR}"/>'
    import math
    for k in range(8):
        a = k * math.pi / 4
        o += (f'<line x1="{cx+math.cos(a)*(r+8)}" y1="{cy+math.sin(a)*(r+8)}" x2="{cx+math.cos(a)*(r+20)}" y2="{cy+math.sin(a)*(r+20)}" '
              f'stroke="{SOLAR}" stroke-width="4" stroke-linecap="round"/>')
    return o


def bateria_cont(x, y, w, h):
    o = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{BAT}"/>'
    for i in range(1, 5):
        o += f'<line x1="{x+w*i/5}" x2="{x+w*i/5}" y1="{y+8}" y2="{y+h-8}" stroke="#fff" stroke-width="2" opacity=".35"/>'
    o += f'<rect x="{x+w/2-26}" y="{y+h/2-14}" width="52" height="28" rx="5" fill="none" stroke="#fff" stroke-width="3"/>'
    o += f'<rect x="{x+w/2+26}" y="{y+h/2-6}" width="5" height="12" rx="1.5" fill="#fff"/><rect x="{x+w/2-21}" y="{y+h/2-9}" width="26" height="18" rx="2" fill="#fff"/>'
    return o


def torre(x, y, h, cor=REDE):
    """Torre de transmissão (base em y)."""
    w = h * .36
    o = (f'<g stroke="{cor}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none">'
         f'<path d="M{x-w/2} {y} L{x} {y-h} L{x+w/2} {y}"/><path d="M{x-w*.36} {y-h*.28} L{x+w*.36} {y-h*.28} M{x-w*.22} {y-h*.56} L{x+w*.22} {y-h*.56}"/>'
         f'<path d="M{x-w*.9} {y-h*.78} H{x+w*.9} M{x-w*.6} {y-h*.62} H{x+w*.6}"/>'
         f'<path d="M{x-w*.36} {y-h*.28} L{x+w*.22} {y-h*.56} M{x+w*.36} {y-h*.28} L{x-w*.22} {y-h*.56}"/></g>')
    return o


def microrrede(ox, oy, s=1.0, escuro=False):
    """Microrrede industrial conectada: rede (torre + cabos) → fábrica com FV no telhado, FV em solo e contêiner de baterias."""
    g = f'<g transform="translate({ox} {oy}) scale({s})">'
    chao = 360
    g += sol(600, 70)
    g += f'<path d="M0 {chao} H700" stroke="{NAVY}" stroke-width="3"/>'
    # rede
    g += torre(60, chao, 210) + torre(165, chao, 160)
    g += (f'<path d="M22 {chao-164} Q110 {chao-110} 136 {chao-125}" fill="none" stroke="{REDE}" stroke-width="2.5"/>'
          f'<path d="M98 {chao-164} Q140 {chao-120} 194 {chao-125}" fill="none" stroke="{REDE}" stroke-width="2.5"/>'
          f'<path d="M194 {chao-125} Q235 {chao-118} 262 {chao-140}" fill="none" stroke="{REDE}" stroke-width="2.5"/>')
    # fábrica (telhado em dente de serra)
    fx, fw, fh = 250, 290, 150
    yt = chao - fh
    g += f'<rect x="{fx}" y="{yt}" width="{fw}" height="{fh}" fill="#fff" stroke="{NAVY}" stroke-width="3"/>'
    dentes = "".join(f"L{fx+i*fw/4} {yt-40} L{fx+(i+1)*fw/4} {yt} " for i in range(4))
    g += f'<path d="M{fx} {yt} {dentes}" fill="#fff" stroke="{NAVY}" stroke-width="3" stroke-linejoin="round"/>'
    for i in range(4):
        x1 = fx + i * fw / 4
        g += f'<path d="M{x1+4} {yt-4} L{x1+fw/4*.92} {yt-36} L{x1+fw/4-4} {yt-4} Z" fill="url(#pv)" stroke="#0E1E3A" stroke-width="1"/>'
    for i in range(5):
        g += f'<rect x="{fx+20+i*54}" y="{yt+34}" width="34" height="30" rx="3" fill="{CEU}" stroke="{NAVY}" stroke-width="2"/>'
    g += f'<rect x="{fx+fw/2-26}" y="{chao-62}" width="52" height="62" fill="{LIGHT}" stroke="{NAVY}" stroke-width="3"/>'
    g += f'<rect x="{fx+fw-52}" y="{yt-90}" width="22" height="70" fill="#fff" stroke="{NAVY}" stroke-width="3"/>'
    # FV em solo
    for i in range(3):
        px = 30 + i * 0
    g += bateria_cont(566, chao - 62, 78, 62)
    return g + "</g>"


def barco(ox, oy, s=1.0):
    """Embarcação híbrida isolada: casco, cabine com FV no teto, tanques de H₂ e banco de baterias; mar com ondas."""
    g = f'<g transform="translate({ox} {oy}) scale({s})">'
    nivel = 300
    g += sol(610, 66)
    # casco
    g += (f'<path d="M70 {nivel-50} H610 L660 {nivel-92} H690 L640 {nivel+20} Q630 {nivel+38} 600 {nivel+38} H130 Q96 {nivel+38} 86 {nivel+16} Z" '
          f'fill="{NAVY}"/>')
    g += f'<path d="M86 {nivel-12} H646" stroke="#fff" stroke-width="3" opacity=".5"/>'
    for i in range(7):
        g += f'<circle cx="{150+i*62}" cy="{nivel-28}" r="7" fill="#9CC8EA"/>'
    # cabine
    g += f'<path d="M230 {nivel-50} V{nivel-150} Q230 {nivel-160} 240 {nivel-160} H500 L560 {nivel-50} Z" fill="#fff" stroke="{NAVY}" stroke-width="3" stroke-linejoin="round"/>'
    for i in range(4):
        g += f'<rect x="{254+i*58}" y="{nivel-136}" width="42" height="34" rx="5" fill="{CEU}" stroke="{NAVY}" stroke-width="2"/>'
    g += f'<path d="M490 {nivel-136} L530 {nivel-80} H490 Z" fill="{CEU}" stroke="{NAVY}" stroke-width="2"/>'
    # FV no teto
    g += painel_pv(250, nivel - 182, 220, 18, 0, 6, 1)
    g += f'<path d="M270 {nivel-164} V{nivel-160} M450 {nivel-164} V{nivel-160}" stroke="{NAVY}" stroke-width="3"/>'
    # tanques H₂
    for i in range(2):
        tx = 110 + i * 54
        g += f'<rect x="{tx}" y="{nivel-128}" width="40" height="78" rx="20" fill="{PEM}"/>'
        g += f'<rect x="{tx+14}" y="{nivel-138}" width="12" height="12" rx="3" fill="{PEM}"/>' + T(tx + 20, nivel - 82, "H₂", 17, 800, "#fff", anchor="middle")
    # baterias (na proa)
    g += bateria_cont(572, nivel - 112, 52, 46)
    # mar
    g += f'<path d="M0 {nivel+8} H700 V{nivel+120} H0 Z" fill="url(#mar)"/>'
    for j, a in enumerate((.9, .6, .4)):
        y = nivel + 22 + j * 30
        d = f"M0 {y} " + " ".join(f"q 25 -12 50 0 t 50 0" for _ in range(7))
        g += f'<path d="{d}" fill="none" stroke="#fff" stroke-width="3" opacity="{a}" stroke-linecap="round"/>'
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
        s += f'<g clip-path="url(#c{j})"><rect x="{x+40}" y="300" width="750" height="420" fill="url(#ceu)"/>' + (microrrede(x + 65, 330, 1.0) if j == 0 else barco(x + 65, 300, 1.0)) + "</g>"
        h += obj(x + 60, 752, 710, OBJ[j], NAVY, 32)
    salvar("S23v2_A_cartoes", s, h)


# ===================================================================== B · terra × mar: metade clara e metade escura
def b():
    s, h = "", ""
    s += f'<rect x="110" y="170" width="830" height="740" rx="32" fill="{LIGHT}"/>'
    s += f'<rect x="980" y="170" width="830" height="740" rx="32" fill="url(#noite)"/>'
    s += T(525, 250, "Ligado à rede", 56, 700, NAVY, "Gelasio", anchor="middle")
    s += T(1395, 250, "Isolado", 56, 700, "#fff", "Gelasio", anchor="middle")
    s += f'<clipPath id="ca"><rect x="150" y="290" width="750" height="410" rx="22"/></clipPath><g clip-path="url(#ca)"><rect x="150" y="290" width="750" height="410" fill="url(#ceu)"/>{microrrede(175, 316, 1.0)}</g>'
    s += f'<clipPath id="cb"><rect x="1020" y="290" width="750" height="410" rx="22"/></clipPath><g clip-path="url(#cb)"><rect x="1020" y="290" width="750" height="410" fill="url(#ceu)"/>{barco(1045, 286, 1.0)}</g>'
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
        s += f'<g clip-path="url(#k{j})"><rect x="{x}" y="170" width="830" height="520" fill="url(#ceu)"/>' + (microrrede(x + 10, 230, 1.15) if j == 0 else barco(x + 10, 170, 1.15)) + "</g>"
        s += f'<rect x="{x}" y="170" width="830" height="520" rx="32" fill="none" stroke="{LINE}" stroke-width="2"/>'
        s += f'<rect x="{x+30}" y="196" width="{[330, 210][j]}" height="70" rx="35" fill="{NAVY}"/>' + T(x + 30 + [330, 210][j] / 2, 244, ["Ligado à rede", "Isolado"][j], 36, 700, "#fff", "Gelasio", anchor="middle")
        s += f'<rect x="{x}" y="716" width="830" height="194" rx="28" fill="{LIGHT}"/>'
        h += obj(x + 50, 730, 740, OBJ[j], NAVY, 34).replace("text-align:center", "text-align:center;height:166px;display:flex;align-items:center;justify-content:center")
    salvar("S23v2_C_ilustracoes", s, h)


if __name__ == "__main__":
    a()
    b()
    c()
