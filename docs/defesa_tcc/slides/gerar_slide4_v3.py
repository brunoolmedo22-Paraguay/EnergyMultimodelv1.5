"""Slide 4 — mais três propostas (B trajetórias, C barramento do tempo, D tanques), na identidade do deck.
Curvas de B são ESQUEMÁTICAS (rotuladas assim no slide); conteúdo da Introdução do artigo [7–11, 14]."""
import os
D = os.path.dirname(os.path.abspath(__file__))

NAVY, SLATE, TEAL, LIGHT, LINE, LIME = "#14213D", "#4A5568", "#1F7A6D", "#EEF3F2", "#DCE3E2", "#C1FF72"
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
 "clock": '<circle cx="20" cy="20" r="15" fill="none" stroke="currentColor" stroke-width="3"/><path d="M20 11v10l7 4" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',
 "cloud": '<path d="M12 31h17a7 7 0 0 0 0-14 10 10 0 0 0-19 3 6 6 0 0 0 2 11z" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/>',
 "rev": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M31 15a12 12 0 1 0 1 9"/><path d="M32 6v9h-9"/></g>',
}
DEFS = (f'<defs><linearGradient id="gb" x1="0" x2="1"><stop offset="0" stop-color="{G1}"/><stop offset=".55" stop-color="{G2}"/><stop offset="1" stop-color="{G3}"/></linearGradient>'
        f'<filter id="sh" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#14213D" flood-opacity=".10"/></filter></defs>')


def ic(k, x, y, s, c):
    return f'<svg x="{x}" y="{y}" width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c}">{ICON[k]}</svg>'


def no(cx, cy, r, k, cor, cheio=False):
    f, c = (cor, "#fff") if cheio else ("#fff", cor)
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{f}" stroke="{cor}" stroke-width="3"/>' + ic(k, cx - r * .58, cy - r * .58, r * 1.16, c)


def T(x, y, txt, size=18, w=500, c=SLATE, fam="Manrope", anchor="start", it=False, ls=0):
    st = ' font-style="italic"' if it else ""
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{fam}" font-weight="{w}" font-size="{size}" fill="{c}" letter-spacing="{ls}"{st}>{txt}</text>'


def chevrons(x, y, itens, h=46, gap=6):
    out = ""
    for i, (nome, sub, w, c) in enumerate(itens):
        pts = f"{x},{y} {x+w-18},{y} {x+w},{y+h/2} {x+w-18},{y+h} {x},{y+h}" + ("" if i == 0 else f" {x+18},{y+h/2}")
        out += f'<polygon points="{pts}" fill="{c}"/>' + T(x + (30 if i else 16), y + h / 2 + 7, nome, 19, 800, "#fff")
        if sub:
            out += T(x + (30 if i else 16), y + h + 24, sub, 15, 500)
        x += w + gap
    return out


def chip(x, y, k, cor, nome, txt):
    w = 70 + len(nome) * 11.5 + len(txt) * 9.6 + 28
    return (f'<rect x="{x}" y="{y}" width="{w}" height="46" rx="23" fill="#fff" stroke="{LINE}" stroke-width="2"/>' + ic(k, x + 14, y + 9, 28, cor)
            + f'<text x="{x+52}" y="{y+30}"><tspan font-family="Gelasio" font-weight="700" font-size="19" fill="{NAVY}">{nome}</tspan>'
              f'<tspan dx="10" font-family="Manrope" font-weight="600" font-size="18" fill="{SLATE}">→ {txt}</tspan></text>'), w


def chips2(x, y, horiz=True, a="reduzir o custo", b="garantir o atendimento", gap=14):
    c1, w1 = chip(x, y, "grid", REDE, "Conectada", a)
    c2, _ = chip(x + w1 + gap if horiz else x, y if horiz else y + 58, "bat", BAT, "Isolada", b)
    return c1 + c2


def frase(x, y, size=34):
    return (f'<text x="{x}" y="{y}" font-family="Gelasio" font-size="{size}"><tspan font-style="italic" fill="{TEAL}">Cada decisão presente tem um </tspan>'
            f'<tspan font-weight="700" fill="{NAVY}">custo futuro.</tspan><tspan font-family="Manrope" font-size="16" fill="#9AA5B1" dx="8">[11]</tspan></text>')


SEQ = [("NEWAVE", "médio e longo prazo", 168, "#0E4F86"), ("DECOMP", "curto prazo", 150, "#2C6FB0"), ("DESSEM", "diário", 140, AGUA)]

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
REF = '<div class="ref">[8–11] cadeia de modelos do CEPEL e custo futuro da água · [7, 14] decisões intertemporais em microrredes</div>'
TIT = '<div class="tt">Decisões com consequências futuras</div>'


def pagina(svg):
    return TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS}{svg}</svg>' + REF + RODAPE


P = {}

# =====================================================================  B · Trajetórias
s = frase(110, 214)


def painel(x, y, w, h, tag, tit, eixo_x, ticks, faixa, curvas, finais, extra=""):
    o = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="28" fill="{LIGHT}"/>'
    o += T(x + 36, y + 48, tag, 15, 700, "#7B8794", ls=1.5) + T(x + 36, y + 84, tit, 28, 700, NAVY, "Gelasio")
    cx0, cx1, cy0, cy1 = x + 70, x + w - 230, y + 140, y + h - 150
    if faixa:
        a, b, lab, cor = faixa
        o += f'<rect x="{cx0+(cx1-cx0)*a}" y="{cy0-10}" width="{(cx1-cx0)*(b-a)}" height="{cy1-cy0+10}" fill="{cor}" opacity=".10"/>'
        o += T(cx0 + (cx1 - cx0) * (a + b) / 2, cy0 - 18, lab, 15, 700, cor, anchor="middle")
    o += f'<line x1="{cx0}" x2="{cx1}" y1="{cy1}" y2="{cy1}" stroke="#C9D3DD" stroke-width="2"/><line x1="{cx0}" x2="{cx0}" y1="{cy0-10}" y2="{cy1}" stroke="#C9D3DD" stroke-width="2"/>'
    o += f'<text x="{cx0-16}" y="{(cy0+cy1)/2}" text-anchor="middle" font-family="Manrope" font-weight="600" font-size="15" fill="#7B8794" transform="rotate(-90 {cx0-16} {(cy0+cy1)/2})">{eixo_x[1]}</text>'
    for t, lab in ticks:
        o += T(cx0 + (cx1 - cx0) * t, cy1 + 26, lab, 15, 600, "#7B8794", anchor="middle")
    o += T(cx1, cy1 + 52, eixo_x[0], 15, 600, "#9AA5B1", anchor="end")
    for pts, cor, lab, ly in curvas:
        P_ = [(cx0 + (cx1 - cx0) * t, cy1 - (cy1 - cy0) * v) for t, v in pts]
        d = "M" + " ".join(f"{a:.1f} {b:.1f}" if i == 0 else f"L{a:.1f} {b:.1f}" for i, (a, b) in enumerate(P_))
        o += f'<path d="{d}" fill="none" stroke="{cor}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>'
        o += f'<circle cx="{P_[0][0]}" cy="{P_[0][1]}" r="8" fill="#fff" stroke="{NAVY}" stroke-width="3"/>'
        lx = cx0 + (cx1 - cx0) * ly[0]; lyy = cy1 - (cy1 - cy0) * ly[1]
        o += T(lx, lyy, lab, 22, 700, cor, "Gelasio", it=True)
    for (t, v), k, cor, tit2, sub in finais:
        px, py = cx0 + (cx1 - cx0) * t, cy1 - (cy1 - cy0) * v
        px = max(px, cx1)
        o += no(px + 44, py, 26, k, cor) + T(px + 80, py - 2, tit2, 20, 700, NAVY, "Gelasio") + T(px + 80, py + 20, sub, 15, 500)
    return o + extra


s += painel(110, 250, 830, 600, "SISTEMA INTERLIGADO NACIONAL", "Água nos reservatórios", ("tempo", "água armazenada"),
            [(0, "hoje"), (1, "amanhã")], None,
            [([(0, .78), (.25, .42), (.5, .14), (.75, .05), (1, .04)], AGUA, "turbinar agora", (.36, .45)),
             ([(0, .78), (.25, .70), (.5, .62), (.75, .55), (1, .50)], TEAL, "guardar", (.40, .80))],
            [((1, .04), "fire", TERM, "Térmica", "mais cara"), ((1, .50), "check", OK, "Água", "disponível")],
            chevrons(146, 772, [(a, "", w * .92, c) for a, _, w, c in SEQ], h=40, gap=5) + T(586, 799, "o horizonte maior orienta o menor [8–10]", 16, 500))
s += painel(980, 250, 830, 600, "MICRORREDE", "Energia na bateria", ("horas do dia", "energia armazenada"),
            [(0, "0 h"), (.5, "12 h"), (.75, "18 h"), (.875, "21 h"), (1, "24 h")], (.75, .875, "ponta", REDE),
            [([(0, .55), (.2, .55), (.5, .12), (.75, .10), (.875, .10), (1, .10)], BAT, "descarregar cedo", (.0, .30)),
             ([(0, .55), (.55, .55), (.75, .92), (.875, .12), (1, .12)], TEAL, "guardar", (.20, .64))],
            [((.875, .10), "load", REDE, "Falta", "na ponta"), ((.875, .55), "check", OK, "Ponta", "coberta")],
            chips2(1016, 768, a="custo", b="atendimento"))
s += T(1810, 880, "curvas esquemáticas", 14, 500, "#9AA5B1", anchor="end")
P["S4v3_B_trajetorias"] = pagina(s)

# =====================================================================  C · Barramento do tempo
yb = 540; x0, x1 = 110, 1810
s = f'<rect x="{x0}" y="{yb-9}" width="{x1-x0-40}" height="18" rx="9" fill="url(#gb)"/><path d="M{x1-52} {yb-30} L{x1} {yb} L{x1-52} {yb+30} Z" fill="{G3}"/>'
s += T(x0, yb + 50, "agora", 26, 700, NAVY, "Gelasio") + T(x1 - 10, yb - 40, "depois", 26, 700, NAVY, "Gelasio", anchor="end")
pares = [
    (270, 1150, "drop", AGUA, "Turbinar a água", "SIN", "fire", TERM, "Térmica mais cara", "a água faltou"),
    (530, 1410, "bat", BAT, "Descarregar a bateria", "microrrede", "load", REDE, "Falta na ponta", "tarifa alta"),
    (790, 1670, "h2", PEM, "Ligar a PEMFC", "microrrede", "clock", PEM, "Permanência", "tempo mínimo ligada"),
]
yd, yc = 400, 690
for xd, xc, kd, cd, td, sd, kc, cc, tc, sc in pares:
    s += (f'<path d="M{xd+40} {yd+22} C{xd+420} {yd+60}, {xc-420} {yc-60}, {xc-50} {yc-20}" fill="none" stroke="{cd}" stroke-width="3.5" stroke-dasharray="3 9" stroke-linecap="round"/>'
          f'<path d="M{xc-70} {yc-34} L{xc-48} {yc-20} L{xc-70} {yc-6}" fill="none" stroke="{cd}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>')
for xd, xc, kd, cd, td, sd, kc, cc, tc, sc in pares:
    s += f'<line x1="{xd}" x2="{xd}" y1="{yd+44}" y2="{yb-9}" stroke="{cd}" stroke-width="4"/><circle cx="{xd}" cy="{yb}" r="9" fill="#fff" stroke="{cd}" stroke-width="3"/>'
    s += f'<line x1="{xc}" x2="{xc}" y1="{yb+9}" y2="{yc-40}" stroke="{cc}" stroke-width="4"/><circle cx="{xc}" cy="{yb}" r="9" fill="#fff" stroke="{cc}" stroke-width="3"/>'
    s += f'<circle cx="{xd}" cy="{yd}" r="44" fill="{NAVY}" filter="url(#sh)"/>' + ic(kd, xd - 24, yd - 24, 48, "#fff")
    s += T(xd, yd - 82, sd.upper(), 14, 700, "#7B8794", anchor="middle", ls=1.4) + T(xd, yd - 56, td, 21, 700, NAVY, "Gelasio", anchor="middle")
    s += no(xc, yc, 40, kc, cc) + T(xc, yc + 74, tc, 21, 700, NAVY, "Gelasio", anchor="middle") + T(xc, yc + 98, sc, 16, 600, "#7B8794", anchor="middle")
s += T(1180, 214, "No SIN, a cadeia de modelos do CEPEL decide por horizontes:", 18, 500)
s += chevrons(1180, 234, SEQ, h=44) + T(1180, 330, "o horizonte maior orienta o menor [8–10]", 16, 500)
s += frase(110, 214)
s += T(110, 760, "FILOSOFIA DE GESTÃO", 15, 700, "#7B8794", ls=1.5) + chips2(110, 778, horiz=False)
P["S4v3_C_barramento"] = pagina(s)

# =====================================================================  D · Tanques (painel escuro + dois reservatórios)
s = f'<rect x="110" y="170" width="560" height="752" rx="30" fill="{NAVY}"/>'
s += T(150, 232, "A CADA INTERVALO", 15, 700, LIME, ls=1.8)
s += f'<text font-family="Gelasio" font-weight="700" font-size="54" fill="#fff"><tspan x="150" y="304">Usar agora</tspan><tspan x="150" y="366">ou guardar</tspan><tspan x="150" y="428">para depois?</tspan></text>'
s += f'<line x1="150" x2="260" y1="478" y2="478" stroke="url(#gb)" stroke-width="5" stroke-linecap="round"/>'
s += f'<text font-family="Manrope" font-weight="500" font-size="19" fill="#C9D3E3"><tspan x="150" y="530">A energia guardada hoje deixa de</tspan><tspan x="150" y="558">existir se for usada agora — e pode</tspan><tspan x="150" y="586">faltar quando valer mais.</tspan></text>'
s += T(150, 650, "No SIN, a cadeia do CEPEL decide por horizontes:", 17, 500, "#C9D3E3") + chevrons(150, 668, [(a, "", w * .86, c) for a, _, w, c in SEQ], h=40, gap=5) + T(150, 740, "o horizonte maior orienta o menor [8–10]", 15, 500, "#8FA3BF")
s += f'<text font-family="Gelasio" font-style="italic" font-size="30" fill="#fff"><tspan x="150" y="830">Cada decisão presente</tspan><tspan x="150" y="868">tem um <tspan fill="{LIME}" font-weight="700" font-style="normal">custo futuro.</tspan></tspan></text>'
s += T(150, 898, "[11]", 15, 500, "#8FA3BF")


def tanque(cx, top, tipo, cor, tag, tit):
    o = T(cx, top - 16, tag, 15, 700, "#7B8794", anchor="middle", ls=1.5) + T(cx, top + 22, tit, 28, 700, NAVY, "Gelasio", anchor="middle")
    yt, yb_, w = top + 60, top + 440, 280
    xl = cx - w / 2
    nivel = yt + (yb_ - yt) * .30; meta = yt + (yb_ - yt) * .58
    if tipo == "agua":
        k = 50
        path = f"M{xl} {yt} L{xl+k} {yb_} L{xl+w-k} {yb_} L{xl+w} {yt}"
        f = lambda y: k * (y - yt) / (yb_ - yt)
        agua = f"M{xl+f(nivel)} {nivel} L{xl+k} {yb_} L{xl+w-k} {yb_} L{xl+w-f(nivel)} {nivel} Z"
        reserva = f"M{xl+f(meta)} {meta} L{xl+k} {yb_} L{xl+w-k} {yb_} L{xl+w-f(meta)} {meta} Z"
        o += f'<path d="{agua}" fill="{cor}" opacity=".35"/><path d="{reserva}" fill="{cor}" opacity=".9"/>'
        o += f'<path d="{path}" fill="none" stroke="{SLATE}" stroke-width="4" stroke-linejoin="round"/>'
        o += f'<rect x="{xl+w-6}" y="{yt-8}" width="26" height="{yb_-yt+8}" rx="5" fill="#C9D3DD" stroke="{SLATE}" stroke-width="3"/>'
        xm0, xm1 = xl + f(meta) - 10, xl + w - f(meta) + 10
        xlab = xl + w + 34
    else:
        o += f'<rect x="{xl}" y="{yt}" width="{w}" height="{yb_-yt}" rx="34" fill="#fff" stroke="{cor}" stroke-width="5"/>'
        o += f'<rect x="{cx-40}" y="{yt-22}" width="80" height="22" rx="7" fill="{cor}"/>'
        o += f'<rect x="{xl+16}" y="{nivel}" width="{w-32}" height="{meta-nivel}" rx="0" fill="{cor}" opacity=".35"/>'
        o += f'<rect x="{xl+16}" y="{meta}" width="{w-32}" height="{yb_-16-meta}" rx="20" fill="{cor}" opacity=".9"/>'
        xm0, xm1 = xl - 10, xl + w + 10
        xlab = xm1 + 14
    o += f'<line x1="{xm0}" x2="{xm1}" y1="{meta}" y2="{meta}" stroke="{NAVY}" stroke-width="3" stroke-dasharray="8 7"/>'
    o += T(xlab, nivel + (meta - nivel) / 2 + 2, "usar agora", 20, 700, cor, "Gelasio", it=True)
    o += T(xlab, meta + 46, "guardar:", 20, 700, TEAL, "Gelasio", it=True) + T(xlab, meta + 72, "valor futuro", 20, 700, NAVY, "Gelasio")
    return o, yb_


o1, yb1 = tanque(870, 220, "agua", AGUA, "SIN", "Água nos reservatórios")
o2, yb2 = tanque(1450, 220, "bat", BAT, "MICRORREDE", "Energia na bateria")
s += o1 + o2
s += f'<circle cx="1250" cy="450" r="30" fill="#fff" stroke="{LINE}" stroke-width="2"/>' + T(1250, 462, "≡", 32, 700, TEAL, "Gelasio", anchor="middle")
s += T(1250, 505, "mesmo", 14, 600, "#7B8794", anchor="middle") + T(1250, 523, "princípio", 14, 600, "#7B8794", anchor="middle")
s += no(760, yb1 + 70, 30, "fire", TERM) + T(804, yb1 + 64, "Se faltar depois:", 17, 600) + T(804, yb1 + 88, "térmica mais cara", 20, 700, NAVY, "Gelasio")
s += T(1310, yb2 + 52, "SE FALTAR NA PONTA", 14, 700, "#7B8794", ls=1.4) + chips2(1310, yb2 + 66, horiz=False, a="compra cara", b="demanda não atendida")
P["S4v3_D_tanques"] = pagina(s)

HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
for nome, body in P.items():
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=body))
print(list(P))
