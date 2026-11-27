"""Slide 8 — Modelagem dos recursos energéticos: três propostas.
Barramento SEEDS no alto; cada recurso pendurado nele (círculo como na capa) com o seu cartão logo abaixo.
Equações do artigo (Seção 3, eq. 1–8) em LaTeX → SVG (MathJax, `tex2svg.js`); conciso, como no artigo.
P1 um slide, 5 colunas · P2 dois slides (3 + 2), o barramento continua de um para o outro · P3 um slide em zigue-zague.
Uso: SEEDS_NODE_MODULES=<node_modules com mathjax-full> python3 gerar_slide8.py"""
import json
import os
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import CSS, NAVY, SLATE, TEAL, LIGHT, LINE, SOLAR, BAT, REDE, PEM, WIND, G1, G2, G3, MUTED, T, ICON
from gerar_slide5_v3 import DEFS3

D = os.path.dirname(os.path.abspath(__file__))
NM = os.environ.get("SEEDS_NODE_MODULES", "/tmp/claude-0/-home-user-EnergyMultimodelv1-5/1e38ba72-7f98-5498-bc13-346c23387e38/scratchpad/nm/node_modules")

TEX = {
    "fv": r"\begin{aligned}T_c&=T_a+\frac{\mathrm{NOCT}-20}{800}\,G_{\mathrm{ef}}\\[2pt]P_{\mathrm{FV}}&=10^{-3}N_sN_p\,\eta_{\mathrm{STC}}\,A\,G_{\mathrm{ef}}\\&\quad\times\max\!\left[0,\,1+\gamma_P\,(T_c-25)\right]\end{aligned}",
    "eol": r"v_{\mathrm{eq}}=v\left(\frac{\rho}{\rho_{\mathrm{ref}}}\right)^{1/3}",
    "bat": r"\begin{aligned}E_{t+1}&=\alpha E_t+\left(\eta_c P_c-\frac{P_d}{\eta_d}\right)\Delta t\\[2pt]\mathrm{SOC}_t&=\frac{E_t}{C_b}\end{aligned}",
    "pem": r"\begin{aligned}P_{\mathrm{stack}}&=10^{-3}N_{\mathrm{cel}}V_{\mathrm{cel}}\,I\\[2pt]\dot m_{\mathrm{H_2}}&=3600\,\frac{N_{\mathrm{cel}}\,I\,M_{\mathrm{H_2}}}{2\,F\,U_{\mathrm{H_2}}}\end{aligned}",
    "rede": r"C_{\mathrm{rede}}=\sum_t \Delta t\left(c_{\mathrm{imp}}P_{\mathrm{imp}}-c_{\mathrm{exp}}P_{\mathrm{exp}}\right)",
    "fv_c": r"\begin{aligned}P_{\mathrm{FV}}=\;&10^{-3}N_sN_p\,\eta_{\mathrm{STC}}\,A\,G_{\mathrm{ef}}\\&\times\max\!\left[0,\,1+\gamma_P\,(T_c-25)\right]\end{aligned}",
    "pem_c": r"\dot m_{\mathrm{H_2}}=3600\,\frac{N_{\mathrm{cel}}\,I\,M_{\mathrm{H_2}}}{2\,F\,U_{\mathrm{H_2}}}",
    "bat_c": r"E_{t+1}=\alpha E_t+\left(\eta_c P_c-\frac{P_d}{\eta_d}\right)\Delta t",
    "rede_c": r"C_{\mathrm{rede}}=\sum_t \Delta t\,(c_{\mathrm{imp}}P_{\mathrm{imp}}-c_{\mathrm{exp}}P_{\mathrm{exp}})",
}
USA = {"fv": "irradiância e temperatura", "eol": "velocidade do vento e densidade do ar", "pem": "corrente e condições de operação",
       "bat": "potências de carga e descarga", "rede": "tarifas de compra e de venda"}
# (chave, ícone, cor, nome, modelo [ref], equação, o que entrega ao EMS, sentido no barramento)
RES = [
    ("fv", "sun", SOLAR, "Solar fotovoltaica", "temperatura NOCT (Ross) e correção térmica [33]", "potência disponível", "in"),
    ("eol", "wind", WIND, "Eólica", "curva do fabricante, corrigida pela densidade do ar", "potência disponível", "in"),
    ("pem", "h2", PEM, "Célula a combustível", "modelo eletroquímico semiempírico [35, 36]", "curva de consumo de H₂", "in"),
    ("bat", "bat", BAT, "Bateria", "balanço energético (EPRI) [34]", "energia, limites e eficiências", "bi"),
    ("rede", "grid", REDE, "Rede elétrica (PCC)", "intercâmbio no ponto de acoplamento [17]", "sentidos, limites e custo", "bi"),
]
ICON = dict(ICON)
ICON.update({
    "sun": '<circle cx="20" cy="20" r="7" fill="none" stroke="currentColor" stroke-width="3"/><g stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 3v5M20 32v5M3 20h5M32 20h5M8 8l3.5 3.5M28.5 28.5L32 32M8 32l3.5-3.5M28.5 11.5L32 8"/></g>',
    "wind": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 18v19M20 18V4M20 18l12 7M20 18L8 25"/></g><circle cx="20" cy="18" r="3" fill="currentColor"/>',
})
CSS8 = CSS + """
.d{position:absolute}
.eq{color:#14213D;text-align:center;display:flex;align-items:center;justify-content:center}
.eq svg{overflow:visible}
.sub{font:600 16px/1.35 "Manrope";color:#9AA5B1;text-align:center}
"""
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
TIT = '<div class="tt">Modelagem dos recursos energéticos</div>'
REF = ('<div class="ref">[17] Parisio et al. · [33] Ross · [34] EPRI · [35] Altıntaş e Ertan · [36] Chavez et al. (modelo PEMFC do autor) · '
       'equações 1–8 do artigo</div>')


def rodape(n):
    return ('<div class="hl" style="bottom:112px"></div><div class="ft"><img src="../capa/assets/unila.png"><div class="sep"></div>'
            '<span>Engenharia de Energia · ILATIT</span><div class="sep"></div><span><b>Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>'
            f'<div class="pn">{n}</div>')


CACHE = os.path.join(D, "tex_cache_slide8.json")     # equações já convertidas: o kit funciona sem Node/MathJax


def tex_svgs():
    """LaTeX → SVG por MathJax (Node). Sem Node/MathJax disponíveis, usa o cache gravado (mesmas equações)."""
    try:
        env = dict(os.environ, NODE_PATH=NM)
        out = subprocess.run(["node", os.path.join(D, "tex2svg.js")], input=json.dumps(TEX), capture_output=True, text=True, env=env, check=True)
        svg = json.loads(out.stdout)
        json.dump(svg, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        return svg
    except (OSError, subprocess.CalledProcessError, ValueError):
        return json.load(open(CACHE, encoding="utf-8"))


SVG = tex_svgs()


def ic(k, x, y, s, c):
    return f'<svg x="{x}" y="{y}" width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c}">{ICON[k]}</svg>'


def div(x, y, w, h, inner, cls="", st=""):
    return f'<div class="d {cls}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;{st}">{inner}</div>'


def seta(x, y, cima, c):
    """Ponta de seta na haste (cima = aponta para o barramento)."""
    return (f'<path d="M{x-7} {y+6} L{x} {y-5} L{x+7} {y+6}" fill="none" stroke="{c}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
            if cima else
            f'<path d="M{x-7} {y-6} L{x} {y+5} L{x+7} {y-6}" fill="none" stroke="{c}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')


def no_e_haste(cx, yb, yn, k, cor, sentido, r=42, abaixo=True):
    """Haste do barramento (yb) até o nó (yn), ponto de junção e setas de sentido; círculo branco com o ícone."""
    o = f'<line x1="{cx}" x2="{cx}" y1="{yb}" y2="{yn - r if abaixo else yn + r}" stroke="{cor}" stroke-width="3"/>'
    o += f'<circle cx="{cx}" cy="{yb}" r="7" fill="#fff" stroke="{cor}" stroke-width="3"/>'
    ym = (yb + yn) / 2
    if sentido == "in":
        o += seta(cx, ym, abaixo, cor)
    else:
        o += seta(cx, ym - 9, True if abaixo else False, cor) + seta(cx, ym + 9, False if abaixo else True, cor)
    o += f'<circle cx="{cx}" cy="{yn}" r="{r}" fill="#fff" stroke="{cor}" stroke-width="4"/>' + ic(k, cx - r * .58, yn - r * .58, r * 1.16, cor)
    return o


def cartao(x, y, w, h, res, eq_px, curta=False, nome_px=26, topo=64):
    """Cartão claro: nome, modelo (citação), equação centrada e, no pé, «usa → entrega ao EMS»."""
    chave, k, cor, nome, modelo, entrega, _ = res
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="24" fill="{LIGHT}"/>'
    top = y + topo
    s += T(x + w / 2, top, nome, nome_px, 700, NAVY, "Gelasio", anchor="middle")
    html = div(x + 20, top + 12, w - 40, 50, modelo, "sub")
    yb = y + h - 92
    s += f'<line x1="{x+28}" x2="{x+w-28}" y1="{yb}" y2="{yb}" stroke="{LINE}" stroke-width="1.5"/>'
    s += T(x + w / 2, yb + 34, f"usa {USA[chave]}", 16, 600, SLATE, anchor="middle")
    s += T(x + w / 2, yb + 64, f"→ {entrega}", 20, 700, cor, anchor="middle")
    y0 = top + 62
    html += div(x + 14, y0, w - 28, yb - 8 - y0, SVG[chave + ("_c" if curta and chave + "_c" in SVG else "")], "eq", f"font-size:{eq_px}px")
    return s, html


def barra(x0, x1, y, h=12):
    return f'<rect x="{x0}" y="{y-h/2}" width="{x1-x0}" height="{h}" rx="{h/2}" fill="url(#gb)"/>'


def salvar(nome, s, html, n=8):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS3}{s}</svg>'
            + html + f'<div class="ref">{REF[17:-6]}</div>' + rodape(n))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS8, body=body))


# ===================================================================== P1 · um slide, cinco colunas
def p1():
    s, html = "", ""
    yb, yn, ytop, h = 196, 306, 306, 560
    s += barra(110, 1810, yb)
    w, gap = 322, 22
    for i, r in enumerate(RES):
        x = 110 + i * (w + gap)
        cx = x + w / 2
        c, hh = cartao(x, ytop, w, h, r, 17.5, curta=True, nome_px=24)
        s += c
        html += hh
        s += no_e_haste(cx, yb, yn, r[1], r[2], r[6])
    salvar("S8_P1_colunas", s, html)


# ===================================================================== P2 · dois slides (3 + 2), o barramento continua
def p2():
    yb, yn, ytop, h = 196, 304, 304, 590
    # 8a: geração
    s, html = barra(110, 1920 + 20, yb), ""
    w, gap = 546, 31
    for i, r in enumerate(RES[:3]):
        x = 110 + i * (w + gap)
        c, hh = cartao(x, ytop, w, h, r, 29 if r[0] == "fv" else 34)
        s += c
        html += hh
        s += no_e_haste(x + w / 2, yb, yn, r[1], r[2], r[6])
    salvar("S8_P2a_geracao", s, html, 8)
    # 8b: armazenamento e rede (o barramento entra pela esquerda)
    s, html = barra(-20, 1810, yb), ""
    w, gap = 834, 32
    for i, r in enumerate(RES[3:]):
        x = 110 + i * (w + gap)
        c, hh = cartao(x, ytop, w, h, r, 40)
        s += c
        html += hh
        s += no_e_haste(x + w / 2, yb, yn, r[1], r[2], r[6])
    salvar("S8_P2b_armazenamento", s, html, 9)


# ===================================================================== P3 · um slide em zigue-zague (3 em cima, 2 embaixo)
def p3():
    s, html = "", ""
    yb = 538
    s += barra(110, 1810, yb)
    w, gap = 546, 31
    for i, r in enumerate(RES[:3]):           # acima: nó na base do cartão
        x = 110 + i * (w + gap)
        y, h = 162, 316
        c, hh = cartao_baixo(x, y, w, h, r, 24)
        s += c
        html += hh
        s += no_e_haste(x + w / 2, yb, y + h, r[1], r[2], r[6], r=36, abaixo=False)
    for i, r in enumerate(RES[3:]):           # abaixo: nó no topo do cartão
        x = 110 + w / 2 + gap / 2 + i * (w + gap)
        y, h = 618, 300
        c, hh = cartao(x, y, w, h, r, 24, curta=True, topo=60)
        s += c
        html += hh
        s += no_e_haste(x + w / 2, yb, y, r[1], r[2], r[6], r=36, abaixo=True)
    salvar("S8_P3_ziguezague", s, html)


def cartao_baixo(x, y, w, h, res, eq_px):
    """Cartão acima do barramento: o nó encosta na base; nome e modelo no alto, «usa → entrega» antes do nó."""
    chave, k, cor, nome, modelo, entrega, _ = res
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="24" fill="{LIGHT}"/>'
    s += T(x + w / 2, y + 44, nome, 26, 700, NAVY, "Gelasio", anchor="middle")
    html = div(x + 20, y + 54, w - 40, 26, modelo, "sub")
    yb = y + h - 108
    s += f'<line x1="{x+28}" x2="{x+w-28}" y1="{yb}" y2="{yb}" stroke="{LINE}" stroke-width="1.5"/>'
    s += T(x + w / 2, yb + 30, f"usa {USA[chave]}", 16, 600, SLATE, anchor="middle")
    s += T(x + w / 2, yb + 58, f"→ {entrega}", 20, 700, cor, anchor="middle")
    html += div(x + 14, y + 84, w - 28, yb - 6 - (y + 84), SVG[chave + ("_c" if chave + "_c" in SVG else "")], "eq", f"font-size:{eq_px}px")
    return s, html


if __name__ == "__main__":
    p1()
    p2()
    p3()
