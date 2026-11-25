"""Slide 4 — v6: menos rótulos empilhados, gráfico de valor da água redesenhado, layouts empilhados.
O eixo do gráfico carrega a pergunta («usar agora ← → guardar para depois»). Curvas esquemáticas (ONS, 2020, Fig. 3.15)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide4_v3 import (CSS, NAVY, SLATE, TEAL, LIGHT, LINE, BAT, REDE, PEM, AGUA, G1, G2, G3,
                             RODAPE, TIT, T, ic, chevrons)

D = os.path.dirname(os.path.abspath(__file__))
IMED, FUT = "#2E9E6B", "#C0532F"
DEFS = (f'<defs><linearGradient id="gb" x1="0" x2="1"><stop offset="0" stop-color="{G1}"/><stop offset=".55" stop-color="{G2}"/><stop offset="1" stop-color="{G3}"/></linearGradient>'
        f'<linearGradient id="gi" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{IMED}" stop-opacity=".22"/><stop offset="1" stop-color="{IMED}" stop-opacity="0"/></linearGradient>'
        f'<linearGradient id="gf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{FUT}" stop-opacity=".22"/><stop offset="1" stop-color="{FUT}" stop-opacity="0"/></linearGradient>'
        f'<linearGradient id="ga" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6FB3E8"/><stop offset="1" stop-color="{AGUA}"/></linearGradient>'
        f'<filter id="halo" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter></defs>')
REF = ('<div class="ref">[8–11] cadeia de modelos do CEPEL e custo futuro da água · [7, 14] decisões intertemporais em microrredes · '
       'curvas esquemáticas, adaptadas de ONS, <i>O Planejamento da Operação Energética no SIN</i> (2020), Fig. 3.15</div>')


def bacia(cx, cy, w, nivel):
    """Reservatório em corte: margens inclinadas, fundo arredondado, barragem à direita, água com gradiente."""
    h = w * .52
    x0, y0 = cx - w / 2, cy - h / 2
    k = w * .18
    contorno = f"M{x0} {y0} L{x0+k} {y0+h-8} Q{x0+k+3} {y0+h} {x0+k+12} {y0+h} L{x0+w-k-12} {y0+h} Q{x0+w-k-3} {y0+h} {x0+w-k} {y0+h-8} L{x0+w} {y0}"
    o = ""
    if nivel > 0:
        yl = y0 + h * (1 - nivel)
        f = lambda y: k * (y - y0) / (h - 8)
        o += (f'<path d="M{x0+f(yl)} {yl} L{x0+k} {y0+h-8} Q{x0+k+3} {y0+h} {x0+k+12} {y0+h} L{x0+w-k-12} {y0+h} Q{x0+w-k-3} {y0+h} {x0+w-k} {y0+h-8} L{x0+w-f(yl)} {yl} Z" fill="url(#ga)"/>'
              f'<path d="M{x0+f(yl)+6} {yl+5} q{w*.12} -5 {w*.24} 0 t{w*.24} 0" fill="none" stroke="#fff" stroke-width="2" opacity=".7"/>')
    o += f'<path d="{contorno}" fill="none" stroke="{NAVY}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
    o += f'<rect x="{x0+w-3}" y="{y0-4}" width="9" height="{h+4}" rx="3" fill="{NAVY}"/>'
    return o


def grafico(x0, y0, W, H, eixo=True, fs=22):
    """Custo imediato × custo futuro × volume final. Áreas suaves, rótulos nas curvas, ponto ótimo com halo."""
    X0, X1, Y0, Y1 = x0 + 30, x0 + W - 30, y0 + 10, y0 + H - (92 if eixo else 40)
    n = 160
    vs = [i / n for i in range(n + 1)]
    ci = [0.05 + 0.95 * v ** 3.2 for v in vs]
    cf = [0.05 + 0.13 / (v + 0.13) for v in vs]
    tot = [a + b for a, b in zip(ci, cf)]
    m = max(tot) * 1.04
    px = lambda v: X0 + (X1 - X0) * v
    py = lambda c: Y1 - (Y1 - Y0) * c / m
    linha = lambda arr: "M" + " L".join(f"{px(v):.1f} {py(c):.1f}" for v, c in zip(vs, arr))
    area = lambda arr: linha(arr) + f" L{X1} {Y1} L{X0} {Y1} Z"
    k = min(range(n + 1), key=lambda i: tot[i])
    o = f'<path d="{area(cf)}" fill="url(#gf)"/><path d="{area(ci)}" fill="url(#gi)"/>'
    o += f'<path d="{linha(tot)}" fill="none" stroke="{NAVY}" stroke-width="2.5" stroke-dasharray="2 8" stroke-linecap="round" opacity=".45"/>'
    o += f'<path d="{linha(cf)}" fill="none" stroke="{FUT}" stroke-width="6" stroke-linecap="round"/>'
    o += f'<path d="{linha(ci)}" fill="none" stroke="{IMED}" stroke-width="6" stroke-linecap="round"/>'
    o += f'<line x1="{X0}" x2="{X1}" y1="{Y1}" y2="{Y1}" stroke="{NAVY}" stroke-width="2"/>'
    o += T(px(.83) + 18, py(ci[int(.83 * n)]) + 8, "custo imediato", fs, 700, IMED, "Gelasio", it=True)
    o += T(px(.97), py(cf[int(.97 * n)]) + 38, "custo futuro", fs, 700, FUT, "Gelasio", anchor="end", it=True)
    xo, yo = px(vs[k]), py(tot[k])
    o += f'<circle cx="{xo}" cy="{yo}" r="16" fill="{TEAL}" opacity=".35" filter="url(#halo)"/>'
    o += f'<line x1="{xo}" x2="{xo}" y1="{yo+10}" y2="{Y1}" stroke="{TEAL}" stroke-width="2" stroke-dasharray="2 6"/>'
    o += f'<circle cx="{xo}" cy="{yo}" r="9" fill="{TEAL}" stroke="#fff" stroke-width="3"/>'
    o += T(xo, yo - 24, "melhor decisão", 18, 700, TEAL, anchor="middle")
    if eixo:
        yb = Y1 + 50
        o += bacia(X0 + 34, yb, 62, 0) + bacia(X1 - 34, yb, 62, .92)
        o += T(X0 + 78, yb + 8, "← usar a água agora", 19, 700, NAVY)
        o += T(X1 - 78, yb + 8, "guardar para depois →", 19, 700, NAVY, anchor="end")
        o += T((X0 + X1) / 2, yb + 8, "volume guardado ao fim do período", 15, 600, "#9AA5B1", anchor="middle")
    return o


def tarifa_bat(x, y, w, h):
    """Dia: tarifa em degraus com a ponta; bateria vazia sobre a ponta."""
    a, b = x + w * .66, x + w * .84
    lo, hi = y + h - 6, y + 22
    o = (f'<rect x="{a}" y="{y}" width="{b-a}" height="{h}" rx="6" fill="{REDE}" opacity=".10"/>'
         f'<path d="M{x} {lo} H{a} V{hi} H{b} V{lo} H{x+w}" fill="none" stroke="{REDE}" stroke-width="3.5" stroke-linejoin="round"/>'
         + T((a + b) / 2, y - 8, "ponta", 15, 700, REDE, anchor="middle")
         + T(x, y + h + 22, "tarifa ao longo do dia", 14, 600, "#9AA5B1"))
    bx, by = (a + b) / 2 - 15, y + h - 50
    o += (f'<rect x="{bx}" y="{by}" width="30" height="40" rx="6" fill="#fff" stroke="{BAT}" stroke-width="2.5"/>'
          f'<rect x="{bx+9}" y="{by-5}" width="12" height="5" rx="1.5" fill="{BAT}"/>'
          f'<rect x="{bx+5}" y="{by+31}" width="20" height="4" rx="1" fill="{REDE}"/>')
    return o


def estado_pem(x, y, w, h):
    a, b, m = x + w * .12, x + w * .90, x + w * .58
    return (f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="#C9D3DD" stroke-width="2"/>'
            f'<rect x="{a}" y="{y+h-34}" width="{b-a}" height="34" rx="8" fill="{PEM}"/>'
            + T((a + b) / 2, y + h - 11, "ligada", 15, 800, "#fff", anchor="middle")
            + f'<path d="M{a} {y+22} V{y+12} H{m} V{y+22}" fill="none" stroke="{NAVY}" stroke-width="2.5"/>'
            + T((a + m) / 2, y + 4, "tempo mínimo", 15, 700, NAVY, anchor="middle")
            + T(x, y + h + 22, "estado da célula", 14, 600, "#9AA5B1"))


def chip(x, y, k, cor, nome, txt, h=50):
    w = 66 + len(nome) * 12 + len(txt) * 9.6 + 26
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="#fff" stroke="{LINE}" stroke-width="2"/>' + ic(k, x + 15, y + 11, 28, cor)
            + f'<text x="{x+54}" y="{y+h/2+7}"><tspan font-family="Gelasio" font-weight="700" font-size="20" fill="{NAVY}">{nome}</tspan>'
              f'<tspan dx="10" font-family="Manrope" font-weight="600" font-size="17" fill="{SLATE}">→ {txt}</tspan></text>'), w


def para(x, y, linhas, size=18, c=SLATE, lh=27, w=500):
    return f'<text font-family="Manrope" font-weight="{w}" font-size="{size}" fill="{c}">' + "".join(f'<tspan x="{x}" y="{y+i*lh}">{l}</tspan>' for i, l in enumerate(linhas)) + "</text>"


SEQ = lambda w: [("NEWAVE", "", max(w, 160), "#0E4F86"), ("DECOMP", "", max(w * .86, 150), "#2C6FB0"), ("DESSEM", "", max(w * .72, 142), AGUA)]
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'


def salvar(nome, s):
    body = TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS}{s}</svg>' + REF + RODAPE
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=body))


# ===================================================================== H1 — empilhado: valor da água em cima, microrrede embaixo
s = f'<rect x="110" y="168" width="1700" height="470" rx="28" fill="{LIGHT}"/>'
s += T(150, 228, "Conceito de valor da água", 32, 700, NAVY, "Gelasio")
s += para(150, 272, ["No SIN, turbinar hoje é barato,", "mas pode exigir térmicas amanhã.", "O despacho busca o equilíbrio entre", "o custo de agora e o custo futuro."])
s += chevrons(150, 410, SEQ(170), h=42, gap=6)
s += para(150, 486, ["Os modelos de horizonte maior", "entregam aos menores o valor da", "água guardada [8–11]."], 16, "#7B8794", 24)
s += grafico(640, 190, 1140, 440)
# microrrede
s += T(110, 702, "Na microrrede, o mesmo dilema", 30, 700, NAVY, "Gelasio")
s += f'<circle cx="150" cy="778" r="30" fill="{NAVY}"/>' + ic("bat", 132, 760, 36, "#fff")
s += T(196, 772, "Energia usada agora", 21, 700, NAVY, "Gelasio") + T(196, 798, "pode faltar na ponta", 17, 600, SLATE)
s += tarifa_bat(420, 742, 220, 64)
s += f'<circle cx="760" cy="778" r="30" fill="{NAVY}"/>' + ic("h2", 742, 760, 36, "#fff")
s += T(806, 772, "Ligar a célula", 21, 700, NAVY, "Gelasio") + T(806, 798, "obriga a mantê-la ligada", 17, 600, SLATE)
s += estado_pem(1030, 746, 230, 60)
c1, _ = chip(1350, 724, "grid", REDE, "Conectada", "reduzir o custo")
c2, _ = chip(1350, 790, "bat", BAT, "Isolada", "garantir a demanda")
s += T(1350, 712, "o objetivo depende do sistema", 15, 600, "#7B8794") + c1 + c2
salvar("S4v6_H1", s)

# ===================================================================== H2 — gráfico protagonista + três passos numerados
s = grafico(110, 250, 1020, 500, fs=24)
s += T(110, 200, "Conceito de valor da água", 32, 700, NAVY, "Gelasio")
s += para(110, 236, ["custo de usar a água agora × custo de não tê-la depois"], 17, "#7B8794")
R = 1210
passos = [
    ("1", "No SIN, cada horizonte orienta o seguinte", None),
    ("2", "Na microrrede, energia e estados também", None),
    ("3", "O objetivo depende do sistema", None),
]
y = 190
s += f'<line x1="{R+24}" x2="{R+24}" y1="{y+30}" y2="{y+600}" stroke="{LINE}" stroke-width="3"/>'
for i, (n_, t, _) in enumerate(passos):
    yy = [y, y + 210, y + 470][i]
    s += f'<circle cx="{R+24}" cy="{yy+20}" r="24" fill="{NAVY}"/>' + T(R + 24, yy + 29, n_, 22, 700, "#C1FF72", "Gelasio", anchor="middle")
    s += T(R + 66, yy + 28, t, 22, 700, NAVY, "Gelasio")
s += chevrons(R + 66, y + 58, SEQ(170), h=40, gap=6) + para(R + 66, y + 134, ["meses e anos → semanas → dias [8–11]"], 16, "#7B8794")
s += tarifa_bat(R + 66, y + 280, 230, 62) + estado_pem(R + 340, y + 284, 230, 58)
c1, _ = chip(R + 66, y + 510, "grid", REDE, "Conectada", "custo")
c2, _ = chip(R + 66, y + 572, "bat", BAT, "Isolada", "atendimento")
s += c1 + c2
salvar("S4v6_H2", s)

# ===================================================================== H3 — empilhado, microrrede no barramento da capa
s = T(110, 214, "Conceito de valor da água", 30, 700, NAVY, "Gelasio")
s += para(110, 252, ["Turbinar hoje é barato, mas pode exigir térmicas amanhã.", "O despacho equilibra o custo de agora e o custo futuro."])
s += chevrons(110, 318, SEQ(150), h=40, gap=6) + para(110, 392, ["cada horizonte entrega ao", "seguinte o valor da água [8–11]"], 15, "#7B8794", 22)
s += grafico(720, 160, 1090, 440)
# faixa inferior: barramento com os dois recursos e suas consequências
yb = 700
s += T(110, 670, "Na microrrede, o mesmo dilema:", 24, 700, NAVY, "Gelasio")
s += f'<rect x="110" y="{yb-6}" width="1700" height="12" rx="6" fill="url(#gb)"/>'
for cx, k, cor, tit, sub, mini in ((330, "bat", BAT, "Energia usada agora", "pode faltar na ponta", "t"), (930, "h2", PEM, "Ligar a célula", "obriga a mantê-la ligada", "p")):
    s += (f'<line x1="{cx}" x2="{cx}" y1="{yb+6}" y2="{yb+44}" stroke="{cor}" stroke-width="3"/><circle cx="{cx}" cy="{yb}" r="7" fill="#fff" stroke="{cor}" stroke-width="3"/>'
          f'<circle cx="{cx}" cy="{yb+78}" r="34" fill="#fff" stroke="{cor}" stroke-width="3"/>' + ic(k, cx - 20, yb + 58, 40, cor))
    s += T(cx + 52, yb + 72, tit, 21, 700, NAVY, "Gelasio") + T(cx + 52, yb + 98, sub, 17, 600, SLATE)
    s += (tarifa_bat(cx - 130 + 400, yb + 50, 200, 58) if mini == "t" else estado_pem(cx - 130 + 400, yb + 52, 210, 56))
c1, _ = chip(1500, yb + 40, "grid", REDE, "Conectada", "custo", h=46)
c2, _ = chip(1500, yb + 100, "bat", BAT, "Isolada", "demanda", h=46)
s += c1 + c2
salvar("S4v6_H3", s)
print("ok")
