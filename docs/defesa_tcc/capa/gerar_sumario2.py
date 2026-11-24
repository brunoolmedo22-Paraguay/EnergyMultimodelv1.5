"""Sumário refinado (cartões neutros com ícones) + cabeçalho/rodapé discretos."""
import os
D = os.path.dirname(os.path.abspath(__file__))

AUT = "Bruno Manuel Olmedo Chávez"
CUR = "Engenharia de Energia · ILATIT"
TIT = ["Contexto e objetivos", "Fundamentação teórica", "Desenvolvimento do&nbsp;SEEDS", "Estudos de caso",
       "Demonstração do&nbsp;SEEDS", "Resultados", "Conclusões e perspectivas"]

# ícones de seção — mesmo traço dos ícones de recurso (40×40, 3 px, pontas arredondadas)
IC = [
 '<circle cx="20" cy="20" r="15"/><circle cx="20" cy="20" r="8.5"/><circle cx="20" cy="20" r="2.5" fill="currentColor"/>',
 '<path d="M29 7H11l10 13-10 13h18"/>',
 '<rect x="5" y="5" width="12" height="12" rx="2.5"/><rect x="23" y="5" width="12" height="12" rx="2.5"/><rect x="5" y="23" width="12" height="12" rx="2.5"/><rect x="23" y="23" width="12" height="12" rx="2.5" fill="currentColor"/>',
 '<path d="M4 35V19l9 6v-6l9 6v-6l9 6V7h5v28z"/>',
 '<rect x="3" y="6" width="34" height="23" rx="3"/><path d="M14 35h12M20 29v6"/><path d="M17 12.5l8 5-8 5z" fill="currentColor"/>',
 '<path d="M5 35h30"/><path d="M9 35V22M17 35V13M25 35V18M33 35V8"/>',
 '<path d="M9 36V5"/><path d="M9 6h20l-4 7 4 7H9"/>',
]

STOPS = [(0, (0x6D, 0xB5, 0x27)), (.55, (0x1E, 0x8A, 0x72)), (1, (0x00, 0x72, 0xBA))]
def cor(t):
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if t <= b:
            u = (t - a) / (b - a)
            return "#%02x%02x%02x" % tuple(round(x + (y - x) * u) for x, y in zip(ca, cb))
    return "#0072BA"

GRAD = '<linearGradient id="g" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#6DB527"/><stop offset=".55" stop-color="#1E8A72"/><stop offset="1" stop-color="#0072BA"/></linearGradient>'

CSS = """
.hd{position:absolute;left:110px;right:110px;top:34px;height:64px;display:flex;align-items:center;gap:26px;font:500 17px var(--sans);color:#7B8794;letter-spacing:.01em}
.hd img{height:62px}
.hd .sep{width:1.5px;height:34px;background:#DCE3E2}
.hd .r{margin-left:auto}
.hd b{font-weight:600;color:#5B6675}
.hl{position:absolute;left:110px;right:110px;height:1.5px;background:#E6ECEB}
.ft{position:absolute;left:110px;right:110px;bottom:34px;height:60px;display:flex;align-items:center;gap:24px;font:500 17px var(--sans);color:#7B8794}
.ft img{height:56px}.ft .sep{width:1.5px;height:30px;background:#DCE3E2}.ft b{font-weight:600;color:#5B6675}
.pn{position:absolute;right:110px;font:700 40px var(--serif);color:var(--navy);line-height:1;text-align:right}
.pn::before{content:"";display:block;width:44px;height:5px;border-radius:3px;margin:0 0 10px auto;background:linear-gradient(90deg,#6DB527,#1E8A72 55%,#0072BA)}
.tt{position:absolute;left:110px;font:700 60px var(--serif);color:var(--navy)}
.cd{position:absolute;background:var(--light);border-radius:22px;border-top:6px solid;padding:30px 18px 30px 20px}
.cd .nn{font:700 80px var(--serif);line-height:1;letter-spacing:-.01em}
.cd .ic{position:absolute;right:18px;top:30px;width:38px;height:38px}
.cd .ic svg{width:38px;height:38px;fill:none;stroke:currentColor;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}
.cd h3{position:absolute;left:20px;right:8px;bottom:30px;font:700 22.5px var(--serif);color:var(--navy);line-height:1.22}
"""

def cabecalho():
    return (f'<div class="hd"><img src="assets/unila.png"><div class="sep"></div><span>{CUR}</span>'
            f'<span class="r"><b>Defesa de TCC</b> · {AUT}</span></div><div class="hl" style="top:116px"></div>')

def rodape():
    return (f'<div class="hl" style="bottom:112px"></div><div class="ft"><img src="assets/unila.png"><div class="sep"></div>'
            f'<span>{CUR}</span><div class="sep"></div><span><b>Defesa de TCC</b> · {AUT}</span></div>')

def sumario(top_tt, yb, ch, x0=110, x1=1810):
    n = len(TIT); gap = 12; cw = (x1 - x0 - gap * (n - 1)) / n
    xs = [x0 + cw / 2 + k * (cw + gap) for k in range(n)]
    sv = [f'<svg width="1920" height="1080" style="position:absolute;left:0;top:0"><defs>{GRAD}</defs>',
          f'<rect x="{x0}" y="{yb-6}" width="{x1-x0}" height="12" rx="6" fill="url(#g)"/>']
    cds = ""
    for k, (t, x) in enumerate(zip(TIT, xs)):
        c = cor((x - x0) / (x1 - x0))
        sv.append(f'<line x1="{x}" y1="{yb+6}" x2="{x}" y2="{yb+62}" stroke="{c}" stroke-width="3"/>'
                  f'<circle cx="{x}" cy="{yb}" r="7" fill="#fff" stroke="{c}" stroke-width="3"/>')
        cds += (f'<div class="cd" style="left:{x-cw/2:.1f}px;top:{yb+62}px;width:{cw:.1f}px;height:{ch}px;border-top-color:{c}">'
                f'<div class="nn" style="color:{c}">{k+1:02d}</div>'
                f'<div class="ic" style="color:{c}"><svg viewBox="0 0 40 40">{IC[k]}</svg></div><h3>{t}</h3></div>')
    sv.append("</svg>")
    return f'<div class="tt" style="top:{top_tt}px">Sumário</div>' + "".join(sv) + cds

HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><link rel="stylesheet" href="base.css"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'

P = {
 "X1_sumario_cabecalho": cabecalho() + sumario(160, 400, 360) + '<div class="pn" style="bottom:46px">2</div>',
 "X2_sumario_rodape": sumario(78, 345, 380) + rodape() + '<div class="pn" style="bottom:42px">2</div>',
}
for k, body in P.items():
    open(os.path.join(D, k + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=body))
print(list(P))

# ===================== zigue-zague: ímpares acima, pares abaixo =====================
CSS_Z = CSS + """
.cz{position:absolute;width:410px;height:250px;background:var(--light);border-radius:24px;padding:30px 34px}
.cz.up{border-bottom:6px solid}.cz.dn{border-top:6px solid}
.cz .nn{font:700 96px var(--serif);line-height:.9}
.cz h3{position:absolute;left:34px;right:24px;bottom:30px;font:700 34px var(--serif);color:var(--navy);line-height:1.15}
.cz.dm{background:var(--navy)}.cz.dm h3{color:#fff}
.cz .vivo{position:absolute;right:30px;top:36px;display:flex;align-items:center;gap:10px;font:600 20px var(--sans);color:var(--lime)}
.cz .vivo i{width:12px;height:12px;border-radius:50%;background:var(--lime);box-shadow:0 0 0 6px rgba(193,255,114,.18)}
"""

def zigue(top_tt=78, y_up=215, h=250, yb=545, x0=110, x1=1810, w=410):
    gap = (x1 - x0 - 4 * w) / 3
    up = [x0 + w / 2 + k * (w + gap) for k in range(4)]
    dn = [(a + b) / 2 for a, b in zip(up, up[1:])]
    xs = [up[0], dn[0], up[1], dn[1], up[2], dn[2], up[3]]
    sv = [f'<svg width="1920" height="1080" style="position:absolute;left:0;top:0"><defs>{GRAD}</defs>',
          f'<rect x="{x0}" y="{yb-6}" width="{x1-x0}" height="12" rx="6" fill="url(#g)"/>']
    cds = ""
    y_dn = yb + (yb - (y_up + h))
    for k, (t, x) in enumerate(zip(TIT, xs)):
        c = cor((x - x0) / (x1 - x0)); acima = k % 2 == 0; dm = k == 4
        ya, yb2 = (y_up + h, yb - 6) if acima else (yb + 6, y_dn)
        sv.append(f'<line x1="{x}" y1="{ya}" x2="{x}" y2="{yb2}" stroke="{c}" stroke-width="3"/>'
                  f'<circle cx="{x}" cy="{yb}" r="8" fill="#fff" stroke="{c}" stroke-width="3"/>')
        top = y_up if acima else y_dn
        cds += (f'<div class="cz {"up" if acima else "dn"}{" dm" if dm else ""}" style="left:{x-w/2:.1f}px;top:{top}px;border-color:{c}">'
                f'<div class="nn" style="color:{"#C1FF72" if dm else c}">{k+1:02d}</div>'
                + ('<div class="vivo"><i></i>ao vivo</div>' if dm else "") + f'<h3>{t}</h3></div>')
    sv.append("</svg>")
    return f'<div class="tt" style="top:{top_tt}px">Sumário</div>' + "".join(sv) + cds

TIT[2] = "Desenvolvimento do&nbsp;SEEDS"; TIT[4] = "Demonstração do&nbsp;SEEDS"
open(os.path.join(D, "X3_sumario_zigue.html"), "w", encoding="utf-8").write(
    HEAD.format(css=CSS_Z, body=zigue() + rodape() + '<div class="pn" style="bottom:42px">2</div>'))

# ===================== barramento maior, com sentido =====================
def zigue2(estilo, top_tt=78, y_up=205, h=250, yb=545, x0=110, x1=1810, w=410):
    gap = (x1 - x0 - 4 * w) / 3
    up = [x0 + w / 2 + k * (w + gap) for k in range(4)]
    dn = [(a + b) / 2 for a, b in zip(up, up[1:])]
    xs = [up[0], dn[0], up[1], dn[1], up[2], dn[2], up[3]]
    y_dn = yb + (yb - (y_up + h))
    sv = [f'<svg width="1920" height="1080" style="position:absolute;left:0;top:0"><defs>{GRAD}</defs>']
    if estilo in ("seta", "sangria"):
        bx0 = 0 if estilo == "sangria" else x0 - 40
        bx1 = 1920 if estilo == "sangria" else x1 + 40
        T = 24
        sv.append(f'<rect x="{bx0}" y="{yb-T/2}" width="{bx1-bx0-34}" height="{T}" rx="{0 if estilo=="sangria" else T/2}" fill="url(#g)"/>')
        sv.append(f'<path d="M{bx1-46} {yb-30} L{bx1} {yb} L{bx1-46} {yb+30} Z" fill="#0072BA"/>' if estilo == "seta"
                  else f'<path d="M{bx1-60} {yb-30} L{bx1-14} {yb} L{bx1-60} {yb+30} Z" fill="#0072BA"/>')
        pts = [bx0 + 10] + xs + [bx1 - 50]
        for a, b in zip(pts, pts[1:]):
            m = (a + b) / 2
            sv.append(f'<path d="M{m-5} {yb-7} L{m+3} {yb} L{m-5} {yb+7}" fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" opacity=".9"/>')
        meio = T / 2
        for k, x in enumerate(xs):
            c = cor((x - x0) / (x1 - x0))
            sv.append(f'<circle cx="{x}" cy="{yb}" r="15" fill="#fff" stroke="{c}" stroke-width="4"/><circle cx="{x}" cy="{yb}" r="5.5" fill="{c}"/>')
    else:  # chevrons de processo
        H = 40; d = 20; g = 8
        bnd = [x0] + [(a + b) / 2 - d / 2 for a, b in zip(xs, xs[1:])] + [x1 - d]
        for k in range(len(xs)):
            a, b = bnd[k] + (g / 2 if k else 0), bnd[k + 1] - (g / 2 if k < len(xs) - 1 else 0)
            c = cor((xs[k] - x0) / (x1 - x0))
            left = f"L{a+d} {yb}" if k else ""
            sv.append(f'<path d="M{a} {yb-H/2} L{b} {yb-H/2} L{b+d} {yb} L{b} {yb+H/2} L{a} {yb+H/2} {left} Z" fill="{c}"/>')
        meio = H / 2
        for k, x in enumerate(xs):
            sv.append(f'<circle cx="{x}" cy="{yb}" r="7" fill="#fff"/>')
    cds = ""
    for k, (t, x) in enumerate(zip(TIT, xs)):
        c = cor((x - x0) / (x1 - x0)); acima = k % 2 == 0; dm = k == 4
        xx = x
        ya, yb2 = (y_up + h, yb - (15 if estilo != "chevron" else meio)) if acima else (yb + (15 if estilo != "chevron" else meio), y_dn)
        sw = 10 if estilo == "chevron" else 3
        sv.append(f'<line x1="{xx}" y1="{ya - (2 if acima else -2)}" x2="{xx}" y2="{yb2 + (2 if acima else -2)}" stroke="{c}" stroke-width="{sw}"/>')
        top = y_up if acima else y_dn
        cds += (f'<div class="cz {"up" if acima else "dn"}{" dm" if dm else ""}" style="left:{xx-w/2:.1f}px;top:{top}px;border-color:{c}">'
                f'<div class="nn" style="color:{"#C1FF72" if dm else c}">{k+1:02d}</div>'
                + ('<div class="vivo"><i></i>ao vivo</div>' if dm else "") + f'<h3>{t}</h3></div>')
    sv.append("</svg>")
    return f'<div class="tt" style="top:{top_tt}px">Sumário</div>' + "".join(sv) + cds

for nome, est in (("Z1_seta", "seta"), ("Z2_chevron", "chevron"), ("Z3_sangria", "sangria")):
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(
        HEAD.format(css=CSS_Z, body=zigue2(est) + rodape() + '<div class="pn" style="bottom:42px">2</div>'))
