"""Slide 4 — v4 (a partir da proposta B). Esquerda: SIN — função de custo imediato × custo futuro (adaptada de
ONS, 2020, Fig. 3.15) e por que há modelos de vários horizontes. Direita: a pergunta de cada intervalo, a transposição
da filosofia para microrredes e as filosofias de gestão (conectada × isolada). Curvas ESQUEMÁTICAS (sem valores)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide4_v3 import (CSS, DEFS, NAVY, SLATE, TEAL, LIGHT, LINE, LIME, BAT, REDE, PEM, AGUA, TERM, G1, G2, G3,
                             RODAPE, TIT, T, ic, chevrons)

D = os.path.dirname(os.path.abspath(__file__))
IMED, FUT = "#2E9E6B", "#C0532F"   # custo imediato (verde, como no ONS) · custo futuro (ferrugem da paleta)


def reservatorio(x, y, w, h, nivel, cor=AGUA):
    k = w * .2
    f = lambda yy: k * (yy - y) / h
    yl = y + h * (1 - nivel)
    o = ""
    if nivel > 0:
        o += f'<path d="M{x+f(yl)} {yl} L{x+k} {y+h} L{x+w-k} {y+h} L{x+w-f(yl)} {yl} Z" fill="{cor}" opacity=".9"/>'
    return o + f'<path d="M{x} {y} L{x+k} {y+h} L{x+w-k} {y+h} L{x+w} {y}" fill="none" stroke="{SLATE}" stroke-width="3" stroke-linejoin="round"/>'


def fcf(x0, y0, W, H):
    """Custo imediato × custo futuro em função do volume armazenado ao fim do período."""
    pl, pb = 50, 40
    X0, X1, Y0, Y1 = x0 + pl, x0 + W - 20, y0 + 20, y0 + H - pb
    n = 120
    vs = [i / n for i in range(n + 1)]
    ci = [0.06 + 0.94 * v ** 3.2 for v in vs]
    cf = [0.05 + 0.13 / (v + 0.13) for v in vs]
    tot = [a + b for a, b in zip(ci, cf)]
    m = max(max(ci), max(cf), max(tot)) * 1.02
    px = lambda v: X0 + (X1 - X0) * v
    py = lambda c: Y1 - (Y1 - Y0) * c / m
    path = lambda arr: "M" + " L".join(f"{px(v):.1f} {py(c):.1f}" for v, c in zip(vs, arr))
    k = min(range(n + 1), key=lambda i: tot[i])
    o = (f'<line x1="{X0}" x2="{X1}" y1="{Y1}" y2="{Y1}" stroke="#C9D3DD" stroke-width="2"/>'
         f'<line x1="{X0}" x2="{X0}" y1="{Y0-6}" y2="{Y1}" stroke="#C9D3DD" stroke-width="2"/>'
         f'<text x="{X0-18}" y="{(Y0+Y1)/2}" text-anchor="middle" font-family="Manrope" font-weight="600" font-size="15" fill="#7B8794" transform="rotate(-90 {X0-18} {(Y0+Y1)/2})">custo</text>'
         + T(X0, Y1 + 26, "0 %", 15, 600, "#7B8794", anchor="middle") + T(X1, Y1 + 26, "100 %", 15, 600, "#7B8794", anchor="middle")
         + T((X0 + X1) / 2, Y1 + 26, "volume armazenado ao fim do período", 15, 600, "#7B8794", anchor="middle"))
    o += f'<path d="{path(tot)}" fill="none" stroke="{NAVY}" stroke-width="2.5" stroke-dasharray="3 7" stroke-linecap="round" opacity=".55"/>'
    o += f'<path d="{path(cf)}" fill="none" stroke="{FUT}" stroke-width="5" stroke-linecap="round"/>'
    o += f'<path d="{path(ci)}" fill="none" stroke="{IMED}" stroke-width="5" stroke-linecap="round"/>'
    # rótulos diretos
    o += T(px(.80) + 16, py(ci[96]) - 6, "custo imediato", 21, 700, IMED, "Gelasio", it=True)
    o += T(px(.70), py(cf[84]) + 34, "custo futuro", 21, 700, FUT, "Gelasio", it=True)
    o += T(px(.93) - 14, py(tot[112]) + 4, "soma", 16, 700, NAVY, anchor="end")
    # ponto ótimo
    xo, yo = px(vs[k]), py(tot[k])
    o += f'<line x1="{xo}" x2="{xo}" y1="{yo+10}" y2="{Y1}" stroke="{TEAL}" stroke-width="2" stroke-dasharray="3 6"/>'
    o += f'<circle cx="{xo}" cy="{yo}" r="9" fill="{TEAL}" stroke="#fff" stroke-width="3"/>'
    o += T(xo, yo - 22, "melhor decisão", 17, 700, TEAL, anchor="middle")
    return o, (X0, X1, Y0, Y1)


s = ""
# ---------------- painel esquerdo: SIN
L, Tp, Wp, Hp = 110, 170, 1050, 760
s += f'<rect x="{L}" y="{Tp}" width="{Wp}" height="{Hp}" rx="28" fill="{LIGHT}"/>'
s += T(L + 40, Tp + 50, "SISTEMA INTERLIGADO NACIONAL", 15, 700, "#7B8794", ls=1.5)
s += T(L + 40, Tp + 88, "Quanto vale a água guardada?", 30, 700, NAVY, "Gelasio")
g, (X0, X1, Y0, Y1) = fcf(L + 230, Tp + 120, 560, 380)
s += g
# extremos (como no ONS): reservatório vazio × cheio
s += reservatorio(L + 48, Tp + 150, 120, 74, 0)
s += T(L + 108, Tp + 256, "Turbinar agora", 18, 700, NAVY, "Gelasio", anchor="middle")
s += T(L + 108, Tp + 282, "imediato", 15, 600, IMED, anchor="middle") + T(L + 108, Tp + 300, "BAIXO", 15, 800, IMED, anchor="middle")
s += T(L + 108, Tp + 326, "futuro", 15, 600, FUT, anchor="middle") + T(L + 108, Tp + 344, "ALTO", 15, 800, FUT, anchor="middle")
s += reservatorio(L + Wp - 188, Tp + 150, 120, 74, .95)
s += T(L + Wp - 128, Tp + 256, "Guardar", 18, 700, NAVY, "Gelasio", anchor="middle")
s += T(L + Wp - 128, Tp + 282, "imediato", 15, 600, IMED, anchor="middle") + T(L + Wp - 128, Tp + 300, "ALTO", 15, 800, IMED, anchor="middle")
s += T(L + Wp - 128, Tp + 326, "futuro", 15, 600, FUT, anchor="middle") + T(L + Wp - 128, Tp + 344, "BAIXO", 15, 800, FUT, anchor="middle")
s += T(L + Wp - 128, Tp + 370, "(térmica hoje)", 13, 500, "#9AA5B1", anchor="middle")
# por que vários horizontes
yh = Tp + 548
s += f'<line x1="{L+40}" x2="{L+Wp-40}" y1="{yh-24}" y2="{yh-24}" stroke="{LINE}" stroke-width="2"/>'
s += T(L + 40, yh + 8, "Por que modelos de vários horizontes?", 22, 700, NAVY, "Gelasio")
s += (f'<text font-family="Manrope" font-weight="500" font-size="17" fill="{SLATE}"><tspan x="{L+40}" y="{yh+40}">O valor da água depende de meses e anos à frente; o despacho, de horas.</tspan>'
      f'<tspan x="{L+40}" y="{yh+64}">Cada modelo resolve o seu horizonte e entrega ao seguinte o custo futuro [8–11].</tspan></text>')
s += chevrons(L + 40, yh + 92, [("NEWAVE", "médio e longo prazo", 300, "#0E4F86"), ("DECOMP", "curto prazo", 300, "#2C6FB0"), ("DESSEM", "programação diária", 300, AGUA)], h=44, gap=8)
# seta de transposição (da esquerda para a direita)
s += (f'<path d="M{L+Wp+6} {Tp+300} C{L+Wp+40} {Tp+300}, {L+Wp+40} {Tp+392}, {L+Wp+76} {Tp+392}" fill="none" stroke="{G2}" stroke-width="3" stroke-dasharray="3 8" stroke-linecap="round"/>'
      f'<path d="M{L+Wp+66} {Tp+382} L{L+Wp+80} {Tp+392} L{L+Wp+66} {Tp+402}" fill="none" stroke="{G2}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')

# ---------------- coluna direita
R = 1250
s += T(R, Tp + 36, "A CADA INTERVALO, A MESMA PERGUNTA", 15, 700, TEAL, ls=1.5)
s += (f'<text font-family="Gelasio" font-weight="700" font-size="50" fill="{NAVY}"><tspan x="{R}" y="{Tp+100}">Usar agora</tspan>'
      f'<tspan x="{R}" y="{Tp+158}">ou guardar</tspan><tspan x="{R}" y="{Tp+216}">para depois?</tspan></text>')
s += T(R, Tp + 278, "A mesma filosofia vale para microrredes:", 19, 600, SLATE)
s += T(R, Tp + 304, "o que fica guardado também tem custo futuro.", 19, 600, SLATE)
for i, (k, cor, txt) in enumerate((("bat", BAT, "energia armazenada"), ("h2", PEM, "estado das unidades despacháveis"))):
    y = Tp + 336 + i * 56
    s += (f'<rect x="{R}" y="{y}" width="{70 + len(txt)*10.2}" height="44" rx="22" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
          + ic(k, R + 12, y + 8, 28, cor) + T(R + 50, y + 29, txt, 18, 600, NAVY))
yf = Tp + 486
s += T(R, yf, "Mas o objetivo muda com o sistema:", 19, 600, SLATE)
for i, (k, cor, nome, txt) in enumerate((("grid", REDE, "Conectada", "reduzir o custo de aquisição"),
                                         ("bat", BAT, "Isolada", "garantir o atendimento com recursos locais"))):
    y = yf + 22 + i * 92
    s += (f'<rect x="{R}" y="{y}" width="560" height="78" rx="20" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
          f'<circle cx="{R+40}" cy="{y+39}" r="24" fill="#fff" stroke="{cor}" stroke-width="2.5"/>' + ic(k, R + 24, y + 23, 32, cor)
          + T(R + 80, y + 34, nome, 22, 700, NAVY, "Gelasio") + T(R + 80, y + 60, txt, 17, 500, SLATE))

s += (f'<text x="{R}" y="{Tp+728}" font-family="Gelasio" font-size="26"><tspan font-style="italic" fill="{TEAL}">Cada decisão presente tem um </tspan>'
      f'<tspan font-weight="700" fill="{NAVY}">custo futuro.</tspan></text>')
REF2 = ('<div class="ref">[8–11] cadeia de modelos do CEPEL e custo futuro da água · gráfico adaptado de ONS, '
        '<i>O Planejamento da Operação Energética no SIN</i> (2020), Fig. 3.15 — curvas esquemáticas</div>')
body = TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS}{s}</svg>' + REF2 + RODAPE
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
open(os.path.join(D, "S4v4.html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=body))
print("ok")
