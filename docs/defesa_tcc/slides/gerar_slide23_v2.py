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
NODO = {"sun": (SOLAR, "Solar"), "bat": (BAT, "Bateria"), "h2": (PEM, "PEMFC"), "grid": (REDE, "Rede"),
        "fab": (NAVY, "Indústria"), "helice": (NAVY, "Propulsão")}
LA = "#B9C8CE"     # traço do desenho técnico de fundo


def icn(k, x, y, s_, c):
    return f'<svg x="{x}" y="{y}" width="{s_}" height="{s_}" viewBox="0 0 40 40" style="color:{c}">{ICON2[k]}</svg>'


def seta_v(cx, y, para_baixo, c):
    d = 1 if para_baixo else -1
    return f'<path d="M{cx-7} {y-6*d} L{cx} {y+6*d} L{cx+7} {y-6*d} Z" fill="{c}"/>'


def fonte(cx, yb, k, bi=False, r=40, hst=46):
    """Fonte acima do barramento: injeta (seta para o barramento); bateria e rede são bidirecionais."""
    c, nome = NODO[k]
    cy = yb - hst - r
    o = f'<line x1="{cx}" x2="{cx}" y1="{cy+r}" y2="{yb-7}" stroke="{c}" stroke-width="4"/>'
    m = (cy + r + yb) / 2
    o += (seta_v(cx, m - 8, False, c) + seta_v(cx, m + 8, True, c)) if bi else seta_v(cx, m, True, c)
    o += f'<circle cx="{cx}" cy="{yb}" r="8" fill="#fff" stroke="{c}" stroke-width="3.5"/>'
    o += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" stroke="{c}" stroke-width="4"/>' + icn(k, cx - r * .6, cy - r * .6, r * 1.2, c)
    o += T(cx, cy - r - 14, nome, 20, 700, NAVY, anchor="middle")
    return o


def carga(cx, yb, k, r=48, hst=40):
    """Carga abaixo do barramento: consome (seta saindo do barramento); círculo cheio, diferente das fontes."""
    c, nome = NODO[k]
    cy = yb + hst + r
    o = f'<line x1="{cx}" x2="{cx}" y1="{yb+7}" y2="{cy-r}" stroke="{NAVY}" stroke-width="4"/>' + seta_v(cx, (yb + cy - r) / 2 + 4, True, NAVY)
    o += f'<circle cx="{cx}" cy="{yb}" r="8" fill="#fff" stroke="{NAVY}" stroke-width="3.5"/>'
    o += f'<circle cx="{cx}" cy="{cy}" r="{r+9}" fill="#fff"/><circle cx="{cx}" cy="{cy}" r="{r}" fill="{NAVY}"/>' + icn(k, cx - r * .56, cy - r * .56, r * 1.12, "#fff")
    o += f'<rect x="{cx-70}" y="{cy+r+12}" width="140" height="34" rx="17" fill="#fff"/>' + T(cx, cy + r + 36, nome, 21, 700, NAVY, anchor="middle")
    return o


def bus_h(x1, x2, y, esp=14):
    return f'<rect x="{x1}" y="{y-esp/2}" width="{x2-x1}" height="{esp}" rx="{esp/2}" fill="url(#gb)"/>'


def microrrede(ox, oy, s=1.0, escuro=False):
    """Microrrede ligada à rede: desenho técnico (traço fino) de uma planta industrial ao fundo; barramento SEEDS com fontes acima
    (Rede e Bateria bidirecionais, Solar injeta) e a carga (Indústria) abaixo, em círculo cheio."""
    g = f'<g transform="translate({ox} {oy}) scale({s})">'
    st = f'fill="none" stroke="{LA}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"'
    dentes = "".join("l70 -32 v32 " for _ in range(6))
    g += (f'<g {st}><path d="M0 410 H750"/><path d="M120 410 V300 {dentes} V410"/>'
          f'<path d="M140 340 h400 M140 372 h400"/>' + "".join(f'<path d="M{140+i*70} 326 v70"/>' for i in range(7))
          + '<path d="M600 300 V256 h20 V300"/><path d="M610 246 c-8 -8 6 -14 0 -22"/>'
          '<path d="M560 410 V352 h80 V410"/><path d="M580 410 V378 h40 V410"/></g>')
    yb = 172
    g += bus_h(40, 710, yb)
    for cx, k, bi in ((140, "grid", True), (330, "sun", False), (650, "bat", True)):
        g += fonte(cx, yb, k, bi)
    g += carga(492, yb, "fab")
    return g + "</g>"


def barco(ox, oy, s=1.0):
    """Embarcação isolada: desenho técnico (traço fino) do casco e da cabine ao fundo, mar em linhas; barramento a bordo com fontes acima
    (PEMFC e Solar injetam, Bateria bidirecional) e a carga (Propulsão) abaixo, em círculo cheio. Nenhuma rede."""
    g = f'<g transform="translate({ox} {oy}) scale({s})">'
    st = f'fill="none" stroke="{LA}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"'
    g += (f'<g {st}><path d="M30 330 H660 L722 290 L700 330 L656 392 Q648 404 628 404 H112 Q92 404 84 390 Z"/>'
          '<path d="M56 352 H674"/><path d="M110 330 V280 Q110 270 120 270 H560 L612 330"/>'
          + "".join(f'<rect x="{134+i*62}" y="286" width="42" height="28" rx="5"/>' for i in range(3))
          + "".join(f'<rect x="{454+i*62}" y="286" width="42" height="28" rx="5"/>' for i in range(2))
          + "".join(f'<circle cx="{130+i*68}" cy="376" r="6"/>' for i in range(8)) + '</g>')
    for j, (y, a) in enumerate(((414, 1), (428, .6))):
        g += f'<path d="M0 {y} C90 {y-10} 180 {y+10} 270 {y} S450 {y-10} 540 {y} S690 {y+10} 750 {y}" fill="none" stroke="#8FBCE6" stroke-width="2.5" opacity="{a}"/>'
    yb = 172
    g += bus_h(40, 710, yb)
    for cx, k, bi in ((140, "h2", False), (330, "sun", False), (650, "bat", True)):
        g += fonte(cx, yb, k, bi)
    g += carga(492, yb, "helice")
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
        s += f'<g clip-path="url(#c{j})"><rect x="{x+40}" y="300" width="750" height="420" fill="#fff"/>' + (microrrede(x + 40, 300, 1.0) if j == 0 else barco(x + 40, 300, 1.0)) + "</g>"
        h += obj(x + 60, 752, 710, OBJ[j], NAVY, 32)
    salvar("S23v2_A_cartoes", s, h)


# ===================================================================== B · terra × mar: metade clara e metade escura
def b():
    s, h = "", ""
    s += f'<rect x="110" y="170" width="830" height="740" rx="32" fill="{LIGHT}"/>'
    s += f'<rect x="980" y="170" width="830" height="740" rx="32" fill="url(#noite)"/>'
    s += T(525, 250, "Ligado à rede", 56, 700, NAVY, "Gelasio", anchor="middle")
    s += T(1395, 250, "Isolado", 56, 700, "#fff", "Gelasio", anchor="middle")
    s += f'<clipPath id="ca"><rect x="150" y="290" width="750" height="410" rx="22"/></clipPath><g clip-path="url(#ca)"><rect x="150" y="290" width="750" height="410" fill="#fff"/>{microrrede(150, 280, 1.0)}</g>'
    s += f'<clipPath id="cb"><rect x="1020" y="290" width="750" height="410" rx="22"/></clipPath><g clip-path="url(#cb)"><rect x="1020" y="290" width="750" height="410" fill="#fff"/>{barco(1020, 280, 1.0)}</g>'
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
        s += f'<g clip-path="url(#k{j})"><rect x="{x}" y="170" width="830" height="520" fill="#fff"/>' + (microrrede(x + 40, 262, 1.0) if j == 0 else barco(x + 40, 262, 1.0)) + "</g>"
        s += f'<rect x="{x}" y="170" width="830" height="520" rx="32" fill="none" stroke="{LINE}" stroke-width="2"/>'
        s += f'<rect x="{x+30}" y="196" width="{[330, 210][j]}" height="70" rx="35" fill="{NAVY}"/>' + T(x + 30 + [330, 210][j] / 2, 244, ["Ligado à rede", "Isolado"][j], 36, 700, "#fff", "Gelasio", anchor="middle")
        s += f'<rect x="{x}" y="716" width="830" height="194" rx="28" fill="{LIGHT}"/>'
        h += obj(x + 50, 730, 740, OBJ[j], NAVY, 34).replace("text-align:center", "text-align:center;height:166px;display:flex;align-items:center;justify-content:center")
    salvar("S23v2_C_ilustracoes", s, h)


if __name__ == "__main__":
    a()
    b()
    c()


# ===================================================================== D · ilustrações fornecidas pelo responsável (assets/ilus_*.png)
def d():
    s, h = "", ""
    for j, img in enumerate(("assets/ilus_microrrede.png", "assets/ilus_embarcacao.png")):
        x = 110 + j * 870
        s += f'<rect x="{x}" y="196" width="830" height="690" rx="32" fill="#fff" stroke="{LINE}" stroke-width="2" filter="url(#sh)"/>'
        s += T(x + 415, 284, ["Ligado à rede", "Isolado"][j], 56, 700, NAVY, "Gelasio", anchor="middle")
        h += f'<img src="{img}" style="position:absolute;left:{x+30}px;top:322px;width:770px;height:{770*340/730:.0f}px;object-fit:cover">'
        h += obj(x + 60, 722, 710, OBJ[j], NAVY, 34)
    salvar("S23v2_D_ilustracoes", s, h)


if __name__ == "__main__":
    d()
