"""Slide 4 — Decisões com consequências futuras (v2).

Ideia: o slide 3 mostrou fontes CONVERGINDO numa carga; o slide 4 mostra uma decisão DIVERGINDO em futuros.
Cada nó de decisão («usar agora» × «guardar») abre dois caminhos; medidores de nível ao longo do caminho mostram o
armazenamento esvaziando ou sendo preservado; o desfecho do caminho ruim depende da filosofia (conectada × isolada).
Mesma linguagem da capa/sumário/slide 3: nós circulares, linhas coloridas com seta, barramento em gradiente, chevrons.
Conteúdo da Introdução do artigo ([8–11] cadeia CEPEL e custo futuro da água; [7, 14] decisões intertemporais).
"""
import math
import os
D = os.path.dirname(os.path.abspath(__file__))

NAVY, SLATE, TEAL, LIGHT, LINE = "#14213D", "#4A5568", "#1F7A6D", "#EEF3F2", "#DCE3E2"
SOLAR, BAT, REDE, PEM = "#D9A21B", "#7B6CF6", "#E0524F", "#1BA39C"
AGUA, TERM, OK = "#2F7CC0", "#9A5B3C", "#2E9E6B"
G1, G2, G3 = "#6DB527", "#1E8A72", "#0072BA"

ICON = {
 "drop": '<path d="M20 4C14 13 9 19 9 25a11 11 0 0 0 22 0c0-6-5-12-11-21z" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/>',
 "bat": '<rect x="6" y="11" width="25" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="3"/><rect x="32" y="16" width="3" height="8" fill="currentColor"/><rect x="10" y="15" width="11" height="10" fill="currentColor"/>',
 "fire": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M5 36V22l7 4v-4l7 4V12h6v24z"/><path d="M28 9c2-3 6-2 6 1M26 4c2-1 4 0 4 2"/></g>',
 "grid": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M14 37L20 4l6 33M10 12h20M8 20h24M16 29h8"/></g>',
 "load": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><path d="M6 19L20 7l14 12v16H6z"/><path d="M17 35v-9h6v9"/></g>',
 "check": '<path d="M9 21l7 7 15-16" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>',
 "h2": '<text x="20" y="27" text-anchor="middle" font-family="Manrope,sans-serif" font-weight="800" font-size="19" fill="currentColor">H₂</text>',
 "cloud": '<path d="M12 31h17a7 7 0 0 0 0-14 10 10 0 0 0-19 3 6 6 0 0 0 2 11z" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/>',
}


def ic(k, x, y, s, c):
    return f'<svg x="{x}" y="{y}" width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c}">{ICON[k]}</svg>'


def bez(p0, p1, p2, p3, t):
    u = 1 - t
    return tuple(u**3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t**3 * d for a, b, c, d in zip(p0, p1, p2, p3))


def medidor(cx, cy, nivel, cor, tipo):
    """Mini reservatório (trapézio) ou mini bateria com o nível preenchido."""
    w, h = 40, 50
    x, y = cx - w / 2, cy - h / 2
    if tipo == "agua":
        top, bot = w, w * .62
        dx = (top - bot) / 2
        ly = y + h - h * nivel
        lx0 = x + dx * (1 - nivel); lx1 = x + w - dx * (1 - nivel)
        return (f'<path d="M{x} {y} L{x+dx} {y+h} L{x+w-dx} {y+h} L{x+w} {y}" fill="#fff" stroke="{SLATE}" stroke-width="2.5" stroke-linejoin="round"/>'
                f'<path d="M{lx0} {ly} L{x+dx} {y+h} L{x+w-dx} {y+h} L{lx1} {ly} Z" fill="{cor}" opacity=".9"/>')
    lv = (h - 10) * nivel
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#fff" stroke="{cor}" stroke-width="2.5"/>'
            f'<rect x="{cx-7}" y="{y-6}" width="14" height="6" rx="2" fill="{cor}"/>'
            f'<rect x="{x+5}" y="{y+h-5-lv}" width="{w-10}" height="{lv}" rx="4" fill="{cor}" opacity=".9"/>')


def caminho(p0, p3, cor, rot, niveis, tipo, cor_nivel, larg=6, rot_dy=-16):
    p1 = (p0[0] + (p3[0] - p0[0]) * .45, p0[1]); p2 = (p0[0] + (p3[0] - p0[0]) * .45, p3[1])
    s = f'<path d="M{p0[0]} {p0[1]} C{p1[0]} {p1[1]}, {p2[0]} {p2[1]}, {p3[0]-14} {p3[1]}" fill="none" stroke="{cor}" stroke-width="{larg}" stroke-linecap="round"/>'
    s += f'<path d="M{p3[0]-24} {p3[1]-13} L{p3[0]-2} {p3[1]} L{p3[0]-24} {p3[1]+13} Z" fill="{cor}"/>'
    # rótulo do caminho
    lx, ly = bez(p0, p1, p2, p3, .20)
    s += f'<text x="{lx}" y="{ly+rot_dy}" text-anchor="middle" font-family="Gelasio" font-style="italic" font-weight="700" font-size="24" fill="{cor}">{rot}</text>'
    for t, n in zip((.62, .86), niveis):
        x, y = bez(p0, p1, p2, p3, t)
        s += f'<circle cx="{x}" cy="{y}" r="34" fill="#fff" stroke="{cor}" stroke-width="2.5"/>' + medidor(x, y + 2, n, cor_nivel, tipo)
    return s


def no(cx, cy, r, k, cor, fundo="#fff", borda=None, s=None):
    s = s or r * 1.15
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fundo}" stroke="{borda or cor}" stroke-width="3"/>'
            + ic(k, cx - s / 2, cy - s / 2, s, cor))


def chevrons(x, y, itens, h=46):
    out = ""
    for i, (nome, sub, w, c) in enumerate(itens):
        pts = f"{x},{y} {x+w-18},{y} {x+w},{y+h/2} {x+w-18},{y+h} {x},{y+h}" + ("" if i == 0 else f" {x+18},{y+h/2}")
        out += (f'<polygon points="{pts}" fill="{c}"/>'
                f'<text x="{x+(30 if i else 16)}" y="{y+h/2+7}" font-family="Manrope" font-weight="800" font-size="19" fill="#fff">{nome}</text>'
                f'<text x="{x+(30 if i else 16)}" y="{y+h+24}" font-family="Manrope" font-weight="500" font-size="15" fill="{SLATE}">{sub}</text>')
        x += w + 6
    return out


def linha_tempo(x0, x1, y, a, b):
    return (f'<rect x="{x0}" y="{y-3}" width="{x1-x0}" height="6" rx="3" fill="url(#gb)" opacity=".55"/>'
            f'<circle cx="{x0}" cy="{y}" r="6" fill="#fff" stroke="{G1}" stroke-width="2.5"/><circle cx="{x1}" cy="{y}" r="6" fill="#fff" stroke="{G3}" stroke-width="2.5"/>'
            f'<text x="{x0}" y="{y+28}" text-anchor="middle" font-family="Manrope" font-weight="700" font-size="16" fill="{SLATE}">{a}</text>'
            f'<text x="{x1}" y="{y+28}" text-anchor="middle" font-family="Manrope" font-weight="700" font-size="16" fill="{SLATE}">{b}</text>')


def desfecho(x, y, titulo, sub, cor, k):
    return (no(x, y, 34, k, cor) +
            f'<text x="{x+52}" y="{y-4}" font-family="Gelasio" font-weight="700" font-size="24" fill="{NAVY}">{titulo}</text>'
            f'<text x="{x+52}" y="{y+22}" font-family="Manrope" font-weight="500" font-size="17" fill="{SLATE}">{sub}</text>')


W, H = 1920, 1080
s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="position:absolute;left:0;top:0">',
     f'<defs><linearGradient id="gb" x1="0" x2="1"><stop offset="0" stop-color="{G1}"/><stop offset=".55" stop-color="{G2}"/><stop offset="1" stop-color="{G3}"/></linearGradient>'
     f'<filter id="sh" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#14213D" flood-opacity=".08"/></filter></defs>']

# ---------- coluna esquerda: a pergunta e a cadeia do SIN
s.append(f'<text x="110" y="214" font-family="Manrope" font-weight="700" font-size="16" letter-spacing="1.5" fill="{TEAL}">A CADA INTERVALO, A MESMA PERGUNTA</text>')
s.append(f'<text font-family="Gelasio" font-weight="700" font-size="56" fill="{NAVY}"><tspan x="110" y="282">Usar agora</tspan><tspan x="110" y="346">ou guardar</tspan><tspan x="110" y="410">para depois?</tspan></text>')
s.append(f'<text font-family="Manrope" font-weight="500" font-size="20" fill="{SLATE}"><tspan x="110" y="470">No SIN, a cadeia de modelos do CEPEL</tspan><tspan x="110" y="498">responde a essa pergunta por horizontes:</tspan></text>')
s.append(chevrons(110, 530, [("NEWAVE", "médio e longo prazo", 168, "#0E4F86"), ("DECOMP", "curto prazo", 150, "#2C6FB0"), ("DESSEM", "diário", 140, AGUA)]))
s.append(f'<text x="110" y="640" font-family="Manrope" font-weight="500" font-size="17" fill="{SLATE}">o horizonte maior orienta o menor [8–10]</text>')
# conclusão (não é faixa): citação com aspas grandes
s.append(f'<text x="104" y="760" font-family="Gelasio" font-weight="700" font-size="110" fill="{G2}" opacity=".25">“</text>')
s.append(f'<text font-family="Gelasio" font-style="italic" font-size="31" fill="{TEAL}"><tspan x="110" y="752">Cada decisão presente</tspan><tspan x="110" y="792">tem um <tspan font-weight="700" font-style="normal" fill="{NAVY}">custo futuro.</tspan></tspan></text>')
s.append(f'<text x="110" y="826" font-family="Manrope" font-size="15" fill="#9AA5B1">[11]</text>')

# ---------- painel direito: duas linhas (SIN e microrrede)
X0, X1 = 640, 1810
s.append(f'<rect x="{X0}" y="170" width="{X1-X0}" height="770" rx="28" fill="{LIGHT}"/>')


def linha(y0, tag, titulo, k_dec, cor_dec, tipo, cor_lvl, rot_ruim, rot_bom, ruim, bom, tempo, chips=False):
    out = []
    xd, yc, dv = X0 + 140, y0 + 205, 92
    out.append(f'<text x="{X0+40}" y="{y0+50}" font-family="Manrope" font-weight="700" font-size="15" letter-spacing="1.5" fill="#7B8794">{tag}</text>')
    out.append(f'<text x="{X0+40}" y="{y0+84}" font-family="Gelasio" font-weight="700" font-size="28" fill="{NAVY}">{titulo}</text>')
    xo = X1 - 420
    out.append(caminho((xd + 52, yc), (xo - 36, yc - dv), cor_dec, rot_ruim, (.4, .12), tipo, cor_lvl, rot_dy=-34))
    out.append(caminho((xd + 52, yc), (xo - 36, yc + dv), TEAL, rot_bom, (.85, .8), tipo, cor_lvl, rot_dy=40))
    out.append(f'<circle cx="{xd}" cy="{yc}" r="56" fill="{NAVY}" filter="url(#sh)"/>' + ic(k_dec, xd - 30, yc - 30, 60, "#fff"))
    out.append(f'<text x="{xd}" y="{yc+86}" text-anchor="middle" font-family="Manrope" font-weight="700" font-size="17" fill="{SLATE}">{tempo[0]}</text>')
    out.append(f'<text x="{xo}" y="{yc-dv-50}" text-anchor="middle" font-family="Manrope" font-weight="700" font-size="17" fill="{SLATE}">{tempo[1]}</text>')
    out.append(desfecho(xo, yc - dv, *ruim))
    out.append(desfecho(xo, yc + dv, *bom))
    if chips:
        x, y = xo + 52, yc - dv + 40
        for i, (nome, txt, c) in enumerate((("conectada", "compra cara da rede", REDE), ("isolada", "demanda não atendida", BAT))):
            yy = y + i * 36
            out.append(f'<rect x="{x}" y="{yy}" width="104" height="28" rx="14" fill="#fff" stroke="{c}" stroke-width="1.8"/>'
                       f'<text x="{x+52}" y="{yy+19}" text-anchor="middle" font-family="Manrope" font-weight="700" font-size="14" fill="{c}">{nome}</text>'
                       f'<text x="{x+114}" y="{yy+19}" font-family="Manrope" font-weight="600" font-size="15" fill="{SLATE}">→ {txt}</text>')
    return "".join(out)


s.append(linha(170, "SISTEMA INTERLIGADO NACIONAL", "Água nos reservatórios", "drop", AGUA, "agua", AGUA,
               "turbinar agora", "guardar",
               ("Térmica mais cara", "a água faltou depois", TERM, "fire"),
               ("Água disponível", "quando vale mais", OK, "check"),
               ("hoje", "amanhã")))
# divisor
s.append(f'<line x1="{X0+40}" x2="{X1-40}" y1="555" y2="555" stroke="{G2}" stroke-width="2" stroke-dasharray="3 9" stroke-linecap="round"/>')
s.append(f'<rect x="{(X0+X1)/2-190}" y="537" width="380" height="36" rx="18" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
         f'<text x="{(X0+X1)/2}" y="561" text-anchor="middle" font-family="Gelasio" font-style="italic" font-size="20" fill="{TEAL}">o mesmo princípio, em escala menor</text>')
extra = (f'<g font-family="Manrope" font-size="15" font-weight="600" fill="{SLATE}">'
         f'<rect x="{X1-400-40}" y="{555+170+78+46}" width="120" height="30" rx="15" fill="#fff" stroke="{REDE}" stroke-width="1.8"/>'
         f'<text x="{X1-400+20}" y="{555+170+78+67}" text-anchor="middle" fill="{REDE}">conectada</text>'
         f'<text x="{X1-400+92}" y="{555+170+78+67}">→ compra cara da rede</text>'
         f'<rect x="{X1-400-40}" y="{555+170+78+84}" width="120" height="30" rx="15" fill="#fff" stroke="{BAT}" stroke-width="1.8"/>'
         f'<text x="{X1-400+20}" y="{555+170+78+105}" text-anchor="middle" fill="{BAT}">isolada</text>'
         f'<text x="{X1-400+92}" y="{555+170+78+105}">→ demanda não atendida</text></g>')
s.append(linha(555, "MICRORREDE", "Energia na bateria", "bat", BAT, "bat", BAT,
               "descarregar agora", "guardar",
               ("Falta na ponta", "", REDE, "load"),
               ("Ponta coberta", "pela energia guardada", OK, "check"),
               ("agora", "na ponta"), chips=True))
s.append("</svg>")

# os chips conectada/isolada ficam junto ao desfecho ruim da microrrede (substituem a linha de tempo naquela altura)
CSS = """
@import url("../capa/assets/fonts.css");
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:#fff}
.slide{position:relative;width:1920px;height:1080px;overflow:hidden;font-family:"Manrope",sans-serif;color:#14213D}
.tt{position:absolute;left:110px;top:70px;font:700 60px "Gelasio",Georgia,serif}
.hl{position:absolute;left:110px;right:110px;height:1.5px;background:#E6ECEB}
.ft{position:absolute;left:110px;right:110px;bottom:34px;height:60px;display:flex;align-items:center;gap:24px;font:500 17px "Manrope";color:#7B8794}
.ft img{height:56px}.ft .sep{width:1.5px;height:30px;background:#DCE3E2}.ft b{font-weight:600;color:#5B6675}
.pn{position:absolute;right:110px;bottom:42px;font:700 40px "Gelasio",serif;line-height:1;text-align:right}
.pn::before{content:"";display:block;width:44px;height:5px;border-radius:3px;margin:0 0 10px auto;background:linear-gradient(90deg,#6DB527,#1E8A72 55%,#0072BA)}
.ref{position:absolute;left:110px;bottom:124px;font:500 14px "Manrope";color:#9AA5B1}
"""
RODAPE = ('<div class="hl" style="bottom:112px"></div><div class="ft"><img src="../capa/assets/unila.png"><div class="sep"></div>'
          '<span>Engenharia de Energia · ILATIT</span><div class="sep"></div><span><b>Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>'
          '<div class="pn">4</div>')
REF = '<div class="ref" style="left:110px;bottom:124px;width:520px">[8–11] cadeia de modelos do CEPEL e custo futuro da água · [7, 14] decisões intertemporais em microrredes</div>'
body = '<div class="tt">Decisões com consequências futuras</div>' + "".join(s) + REF + RODAPE
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
open(os.path.join(D, "S4v2_decisao.html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=body))
print("ok")
