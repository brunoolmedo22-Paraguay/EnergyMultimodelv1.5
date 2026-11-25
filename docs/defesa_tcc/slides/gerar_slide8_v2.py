"""Slide 8 — v2 (dois slides, 3 + 2; o barramento continua de um para o outro), cartões completos:
nome do recurso · nome do modelo físico · referência · equações do artigo (LaTeX, numeradas como no artigo) ·
variáveis com unidade · o que entra e o que vai ao EMS (com unidade).
Curva da eólica: ILUSTRATIVA (forma típica de curva de potência; não é a de um aerogerador do catálogo)."""
import json
import os
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import CSS, NAVY, SLATE, TEAL, LIGHT, LINE, SOLAR, BAT, REDE, PEM, WIND, MUTED, T
from gerar_slide5_v3 import DEFS3
from gerar_slide8 import NM, ic, no_e_haste, barra, rodape  # noqa: F401

D = os.path.dirname(os.path.abspath(__file__))

EQ = {
    "fv": r"\begin{aligned}T_{c}&=T_{a}+\frac{\mathrm{NOCT}-20}{800}\,G_{\mathrm{ef}}\\[4pt]P_{\mathrm{FV}}&=10^{-3}N_sN_p\,\eta_{\mathrm{STC}}\,A\,G_{\mathrm{ef}}\\&\quad\times\max\!\left[0,\;1+\gamma_P\,(T_c-25)\right]\end{aligned}",
    "eol": r"v_{\mathrm{eq}}=v\left(\frac{\rho}{\rho_{\mathrm{ref}}}\right)^{1/3}",
    "pem": r"\begin{aligned}P_{\mathrm{stack}}&=10^{-3}N_{\mathrm{cel}}\,V_{\mathrm{cel}}\,I\\[4pt]\dot m_{\mathrm{H_2}}&=3600\,\frac{N_{\mathrm{cel}}\,I\,M_{\mathrm{H_2}}}{2\,F\,U_{\mathrm{H_2}}}\end{aligned}",
    "bat": r"E_{t+1}=\alpha\,E_t+\left(\eta_c\,P_{c,t}-\frac{P_{d,t}}{\eta_d}\right)\Delta t\qquad\mathrm{SOC}_t=\frac{E_t}{C_b}",
    "rede": r"C_{\mathrm{rede}}=\sum_t \Delta t\left(c_{\mathrm{imp},t}\,P_{\mathrm{imp},t}-c_{\mathrm{exp},t}\,P_{\mathrm{exp},t}\right)",
}
NUM = {"fv": "eq. 1–2", "eol": "eq. 3", "pem": "eq. 6–7", "bat": "eq. 4–5", "rede": "eq. 8"}
# (símbolo TeX, descrição, unidade)
VARS = {
    "fv": [(r"G_{\mathrm{ef}}", "irradiância efetiva", "W/m²"), (r"T_a,\,T_c", "temp. ambiente e da célula", "°C"),
           (r"\mathrm{NOCT}", "temp. nominal de operação", "°C"), (r"\gamma_P", "coef. térmico de potência", "°C⁻¹"),
           (r"A", "área bruta do módulo", "m²"), (r"\eta_{\mathrm{STC}}", "eficiência nas STC", "—"),
           (r"N_s,\,N_p", "módulos em série e paralelo", "—"), (r"P_{\mathrm{FV}}", "potência disponível (CC)", "kW")],
    "eol": [(r"v", "velocidade do vento", "m/s"), (r"v_{\mathrm{eq}}", "velocidade equivalente", "m/s"),
            (r"\rho", "densidade do ar", "kg/m³"), (r"\rho_{\mathrm{ref}}", "densidade da curva", "kg/m³")],
    "pem": [(r"N_{\mathrm{cel}}", "número de células", "—"), (r"V_{\mathrm{cel}}", "tensão da célula", "V"),
            (r"I", "corrente elétrica", "A"), (r"P_{\mathrm{stack}}", "potência do stack", "kW"),
            (r"\dot m_{\mathrm{H_2}}", "vazão de hidrogênio", "kg/h"), (r"M_{\mathrm{H_2}}", "massa molar do H₂", "kg/mol"),
            (r"F", "constante de Faraday", "C/mol"), (r"U_{\mathrm{H_2}}", "fator de utilização", "—")],
    "bat": [(r"E_t", "energia armazenada", "kWh"), (r"P_{c},\,P_{d}", "potência de carga e descarga", "kW"),
            (r"\eta_c,\,\eta_d", "eficiências de carga e descarga", "—"), (r"\Delta t", "duração do intervalo", "h"),
            (r"\alpha", "fator de retenção", "—"), (r"C_b", "capacidade nominal", "kWh")],
    "rede": [(r"P_{\mathrm{imp}},\,P_{\mathrm{exp}}", "potência importada e exportada", "kW"),
             (r"c_{\mathrm{imp}},\,c_{\mathrm{exp}}", "tarifas de compra e de venda", "R$/kWh"),
             (r"\Delta t", "duração do intervalo", "h"), (r"C_{\mathrm{rede}}", "custo líquido do intercâmbio", "R$")],
}
# chave, ícone, cor, nome, modelo físico, referência, entrada, vai ao EMS, sentido
RES = [
    ("fv", "sun", SOLAR, "Solar fotovoltaica", "Temperatura NOCT e correção térmica", "Ross (1976) [33]",
     "irradiância e temperatura", "potência disponível [kW]", "in"),
    ("eol", "wind", WIND, "Eólica", "Curva de potência do fabricante", "com correção da densidade do ar",
     "vento e densidade do ar", "potência disponível [kW]", "in"),
    ("pem", "h2", PEM, "Célula a combustível PEMFC", "Modelo eletroquímico semiempírico",
     "Altıntaş e Ertan (2024) [35] · parametrização: Chavez et al. (2026) [36]",
     "condições de operação", "consumo de H₂ × potência [kg/h]", "in"),
    ("bat", "bat", BAT, "Bateria", "Balanço energético discreto", "Electric Power Research Institute (EPRI) [34]",
     "potências de carga e descarga", "energia armazenada [kWh], limites e eficiências", "bi"),
    ("rede", "grid", REDE, "Rede elétrica (PCC)", "Ponto de acoplamento comum, sem fluxo de potência",
     "Parisio, Rikos e Glielmo (2014) [17]", "tarifas, sentidos e limites declarados", "custo do intercâmbio [R$]", "bi"),
]

TEX = dict(EQ)
for k, vs in VARS.items():
    for i, (sym, _, _) in enumerate(vs):
        TEX[f"i_{k}{i}"] = sym
SVG = json.loads(subprocess.run(["node", os.path.join(D, "tex2svg.js")], input=json.dumps(TEX), capture_output=True,
                                text=True, env=dict(os.environ, NODE_PATH=NM), check=True).stdout)

CSS8 = CSS + """
.d{position:absolute}
.nm{font:700 27px/1.15 "Gelasio",Georgia,serif;color:#14213D;text-align:center}
.md{font:italic 700 20px/1.25 "Gelasio",Georgia,serif;text-align:center;margin-top:8px}
.rf{font:500 14.5px/1.35 "Manrope";color:#7B8794;text-align:center;margin-top:3px}
.eq{display:flex;align-items:center;justify-content:center;color:#14213D}
.eq svg{overflow:visible}
.tg{position:absolute;right:4px;top:-2px;font:600 13px "Manrope";color:#9AA5B1}
.vs{display:grid;grid-template-columns:auto 1fr auto;column-gap:12px;row-gap:5px;align-items:center;color:#14213D}
.vs .s{font-size:16.5px;text-align:right;white-space:nowrap}
.vs .s svg{vertical-align:middle!important}
.vs .t{font:500 15px "Manrope";color:#4A5568;white-space:nowrap}
.vs .u{font:700 14.5px "Manrope";color:#14213D;text-align:right;white-space:nowrap}
.fl{display:flex;align-items:center;justify-content:center;gap:10px;font:600 15.5px/1.3 "Manrope";color:#4A5568;text-align:center;white-space:nowrap}
.fl b{font-weight:800}
.fl .ar{font-size:22px;color:#9AA5B1}
"""
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
TIT = '<div class="tt">Modelagem dos recursos energéticos</div>'


def div(x, y, w, h, inner, cls="", st=""):
    hh = f"height:{h}px;" if h else ""
    return f'<div class="d {cls}" style="left:{x}px;top:{y}px;width:{w}px;{hh}{st}">{inner}</div>'


def vars_html(k, idx):
    rows = "".join(f'<div class="s">{SVG[f"i_{k}{i}"]}</div><div class="t">{VARS[k][i][1]}</div><div class="u">{VARS[k][i][2]}</div>'
                   for i in idx)
    return f'<div class="vs">{rows}</div>'


def curva_eolica(x, y, w, h, cor):
    """Curva de potência ILUSTRATIVA: zero até v_in, subida cúbica, patamar nominal até v_out."""
    vin, vr, vout = .18, .62, .88
    px = lambda u: x + w * u
    pts = []
    for i in range(41):
        u = vin + (vr - vin) * i / 40
        f = ((u - vin) / (vr - vin)) ** 2.6
        pts.append((px(u), y + h - h * f))
    d = f"M{x} {y+h} L{px(vin)} {y+h} " + " ".join(f"L{a:.1f} {b:.1f}" for a, b in pts) + f" L{px(vout)} {y} L{px(vout)} {y+h} L{x+w} {y+h}"
    area = f"M{px(vin)} {y+h} " + " ".join(f"L{a:.1f} {b:.1f}" for a, b in pts) + f" L{px(vout)} {y} L{px(vout)} {y+h} Z"
    g = (f'<linearGradient id="gw" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{cor}" stop-opacity=".22"/>'
         f'<stop offset="1" stop-color="{cor}" stop-opacity="0"/></linearGradient>')
    o = g + f'<path d="{area}" fill="url(#gw)"/><path d="{d}" fill="none" stroke="{cor}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>'
    o += f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="{NAVY}" stroke-width="2"/><line x1="{x}" x2="{x}" y1="{y-8}" y2="{y+h}" stroke="{NAVY}" stroke-width="2"/>'
    for u, t in ((vin, "v<tspan baseline-shift='sub' font-size='11'>entrada</tspan>"), (vr, "v<tspan baseline-shift='sub' font-size='11'>nominal</tspan>"),
                 (vout, "v<tspan baseline-shift='sub' font-size='11'>corte</tspan>")):
        o += f'<line x1="{px(u)}" x2="{px(u)}" y1="{y+h}" y2="{y+h+6}" stroke="{NAVY}" stroke-width="2"/>'
        o += T(px(u), y + h + 26, t, 15, 600, SLATE, "Gelasio", anchor="middle", it=True)
    o += T(x + 8, y - 12, "P [kW]", 14, 700, SLATE) + T(x + w + 6, y + h + 5, "[m/s]", 14, 700, SLATE)
    o += T(x + w, y - 12, "curva ilustrativa", 12.5, 600, MUTED, anchor="end")
    return o


def esquema_bateria(x, y, w, h, cor):
    """Banco com faixa operacional de SOC (ilustrativa) e a hipótese do EMS."""
    bw, bh = 120, h - 70
    bx, by = x + 40, y + 18
    lo, hi, nv = .10, .90, .55
    yy = lambda f: by + bh - bh * f
    o = f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="16" fill="#fff" stroke="{cor}" stroke-width="3"/>'
    o += f'<rect x="{bx+bw/2-18}" y="{by-10}" width="36" height="10" rx="3" fill="{cor}"/>'
    o += f'<rect x="{bx+8}" y="{yy(nv)}" width="{bw-16}" height="{bb(by, bh, nv)}" rx="9" fill="{cor}" opacity=".35"/>'
    for f, t in ((hi, "SOC<tspan baseline-shift='sub' font-size='12'>máx</tspan>"), (lo, "SOC<tspan baseline-shift='sub' font-size='12'>mín</tspan>")):
        o += f'<line x1="{bx-14}" x2="{bx+bw+14}" y1="{yy(f)}" y2="{yy(f)}" stroke="{NAVY}" stroke-width="2" stroke-dasharray="6 5"/>'
        o += T(bx + bw + 24, yy(f) + 6, t, 17, 700, NAVY, "Gelasio", it=True)
    o += T(bx + bw + 24, yy(nv) + 6, "E<tspan baseline-shift='sub' font-size='12'>t</tspan>", 17, 700, cor, "Gelasio", it=True)
    o += T(x + w / 2, y + h - 18, "no EMS: α = 1 (autodescarga desprezada)", 15, 600, SLATE, anchor="middle")
    o += T(x + w / 2, y + h + 4, "limites de potência e de SOC", 15, 600, MUTED, anchor="middle")
    return o


def bb(by, bh, nv):
    return bh * nv - 8


def esquema_rede(x, y, w, h, cor):
    """Intercâmbio no PCC: importação e exportação com sinais opostos; isolada = sem termos de rede."""
    cx1, cx2, cy = x + 46, x + w - 46, y + (h - 60) / 2
    o = f'<circle cx="{cx1}" cy="{cy}" r="34" fill="#fff" stroke="{cor}" stroke-width="3"/>' + ic("grid", cx1 - 20, cy - 20, 40, cor)
    o += f'<rect x="{cx2-6}" y="{cy-56}" width="12" height="112" rx="6" fill="url(#gbv8)"/>'
    o += (f'<linearGradient id="gbv8" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6DB527"/><stop offset=".55" stop-color="#1E8A72"/>'
          f'<stop offset="1" stop-color="#0072BA"/></linearGradient>')
    for dy, txt, dirr in ((-22, "P<tspan baseline-shift='sub' font-size='12'>imp</tspan> · c<tspan baseline-shift='sub' font-size='12'>imp</tspan>", 1),
                          (22, "P<tspan baseline-shift='sub' font-size='12'>exp</tspan> · c<tspan baseline-shift='sub' font-size='12'>exp</tspan>", -1)):
        a, b = (cx1 + 44, cx2 - 16) if dirr > 0 else (cx2 - 16, cx1 + 44)
        o += f'<line x1="{a}" x2="{b}" y1="{cy+dy}" y2="{cy+dy}" stroke="{cor}" stroke-width="3"/>'
        o += f'<path d="M{b - 10*dirr} {cy+dy-7} L{b} {cy+dy} L{b - 10*dirr} {cy+dy+7}" fill="none" stroke="{cor}" stroke-width="3" stroke-linejoin="round"/>'
        o += T((cx1 + cx2) / 2, cy + dy + (-10 if dy < 0 else 26), txt, 17, 700, NAVY, "Gelasio", anchor="middle", it=True)
    o += T(cx2, cy + 80, "barramento", 13, 600, MUTED, anchor="middle")
    o += T(x + w / 2, y + h - 18, "sinais opostos no balanço de potência", 15, 600, SLATE, anchor="middle")
    o += T(x + w / 2, y + h + 4, "isolada: sem termos de rede", 15, 600, MUTED, anchor="middle")
    return o


def cartao(x, y, w, h, r, eq_px, largo=False):
    k, icn, cor, nome, modelo, ref, entra, sai, _ = r
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="26" fill="{LIGHT}"/>'
    html = div(x + 24, y + 54, w - 48, None,
               f'<div class="nm">{nome}</div><div class="md" style="color:{cor}">{modelo}</div><div class="rf">{ref}</div>')
    top = y + 172
    yb = y + h - 78                          # filete do pé
    s += f'<line x1="{x+30}" x2="{x+w-30}" y1="{top-10}" y2="{top-10}" stroke="#DCE3E2" stroke-width="1.5"/>'
    s += f'<line x1="{x+30}" x2="{x+w-30}" y1="{yb}" y2="{yb}" stroke="#DCE3E2" stroke-width="1.5"/>'
    html += div(x + 24, yb + 16, w - 48, 46,
                f'<span>{entra}</span><span class="ar">→</span><b style="color:{cor}">{sai}</b>', "fl")
    n = len(VARS[k])
    if largo:                                # equação no alto; variáveis à esquerda; esquema e nota à direita
        hq = 150
        html += div(x + 30, top, w - 60, hq, SVG[k] + f'<span class="tg">{NUM[k]}</span>', "eq", f"font-size:{eq_px}px")
        meio = x + w * .56
        y2 = top + hq + 18
        s += f'<line x1="{meio}" x2="{meio}" y1="{y2}" y2="{yb-22}" stroke="#DCE3E2" stroke-width="1.5"/>'
        html += div(x + 30, y2, meio - x - 56, yb - y2 - 14, vars_html(k, range(n)), "", "display:flex;align-items:center;justify-content:center")
        s += (esquema_bateria if k == "bat" else esquema_rede)(meio + 24, y2, x + w - meio - 54, yb - y2 - 14, cor)
    elif k == "eol":
        hq = 96
        html += div(x + 24, top, w - 48, hq, SVG[k] + f'<span class="tg">{NUM[k]}</span>', "eq", f"font-size:{eq_px}px")
        s += curva_eolica(x + 60, top + hq + 36, w - 150, 104, cor)
        html += div(x + 40, top + hq + 182, w - 80, None, vars_html(k, range(n)), "", "display:flex;justify-content:center")
    else:
        hq = 150
        html += div(x + 24, top, w - 48, hq, SVG[k] + f'<span class="tg">{NUM[k]}</span>', "eq", f"font-size:{eq_px}px")
        html += div(x + 34, top + hq + 16, w - 68, yb - top - hq - 26, vars_html(k, range(n)), "", "display:flex;align-items:center;justify-content:center")
    return s, html


def salvar(nome, s, html, n, refs):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS3}{s}</svg>'
            + html + f'<div class="ref">{refs}</div>' + rodape(n))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS8, body=body))


def gerar():
    yb, yn, ytop = 190, 282, 282
    h = 920 - ytop
    # 8 · geração
    s, html = barra(110, 1940, yb), ""
    w, gap = 550, 25
    for i, r in enumerate(RES[:3]):
        x = 110 + i * (w + gap)
        c, hh = cartao(x, ytop, w, h, r, 21 if r[0] == "fv" else 26)
        s += c
        html += hh
        s += no_e_haste(x + w / 2, yb, yn, r[1], r[2], r[8], r=40)
    salvar("S8v2_a_geracao", s, html, 8,
           "[33] Ross · [35] Altıntaş e Ertan · [36] Chavez et al. (modelo PEMFC do autor) · equações numeradas como no artigo · curva eólica ilustrativa")
    # 9 · armazenamento e rede
    s, html = barra(-20, 1810, yb), ""
    w, gap = 835, 30
    for i, r in enumerate(RES[3:]):
        x = 110 + i * (w + gap)
        c, hh = cartao(x, ytop, w, h, r, 26 if r[0] == "bat" else 28, largo=True)
        s += c
        html += hh
        s += no_e_haste(x + w / 2, yb, yn, r[1], r[2], r[8], r=40)
    salvar("S8v2_b_armazenamento", s, html, 9, "[17] Parisio, Rikos e Glielmo · [34] EPRI · equações numeradas como no artigo")


if __name__ == "__main__":
    gerar()
