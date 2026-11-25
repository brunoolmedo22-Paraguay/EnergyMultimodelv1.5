"""Slide 4 — v5: duas soluções para o que faltava (consequências na microrrede com tarifa e permanência da PEMFC;
ponte visível «mesmo princípio»). P1 mantém o layout da v4; P2 espelha SIN × microrrede em dois cartões."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide4_v3 import (CSS, DEFS, NAVY, SLATE, TEAL, LIGHT, LINE, BAT, REDE, PEM, AGUA, TERM, G2,
                             RODAPE, TIT, T, ic, chevrons)
from gerar_slide4_v4 import fcf, reservatorio, IMED, FUT

D = os.path.dirname(os.path.abspath(__file__))
REF = ('<div class="ref">[8–11] cadeia de modelos do CEPEL e custo futuro da água · [7, 14] decisões intertemporais em microrredes · '
       'gráfico adaptado de ONS, <i>O Planejamento da Operação Energética no SIN</i> (2020), Fig. 3.15 — curvas esquemáticas</div>')


def tarifa_mini(x, y, w, h, lbl=True):
    a, b = x + w * .70, x + w * .86
    lo, hi = y + h - 14, y + 16
    o = (f'<rect x="{a}" y="{y+4}" width="{b-a}" height="{h-12}" rx="4" fill="{REDE}" opacity=".12"/>'
         f'<path d="M{x} {lo} H{a} V{hi} H{b} V{lo} H{x+w}" fill="none" stroke="{REDE}" stroke-width="3.5" stroke-linejoin="round"/>'
         f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="#C9D3DD" stroke-width="1.5"/>')
    if lbl:
        o += T((a + b) / 2, y - 4, "ponta", 14, 700, REDE, anchor="middle") + T(x, y + h + 18, "tarifa ao longo do dia", 13, 600, "#9AA5B1")
    return o


def pemfc_mini(x, y, w, h):
    a, b, m = x + w * .16, x + w * .86, x + w * .60
    o = (f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="#C9D3DD" stroke-width="1.5"/>'
         f'<rect x="{a}" y="{y+h-30}" width="{b-a}" height="30" rx="6" fill="{PEM}" opacity=".9"/>'
         + T((a + b) / 2, y + h - 10, "ligada", 14, 800, "#fff", anchor="middle")
         + f'<path d="M{a} {y+16} V{y+8} H{m} V{y+16}" fill="none" stroke="{NAVY}" stroke-width="2.5"/>'
         + T((a + m) / 2, y + 2, "tempo mínimo", 14, 700, NAVY, anchor="middle")
         + T(x, y + h + 18, "estado da unidade", 13, 600, "#9AA5B1"))
    return o


def ponte(cx, cy):
    return (f'<circle cx="{cx}" cy="{cy}" r="38" fill="{NAVY}" stroke="#fff" stroke-width="5"/>'
            + T(cx, cy + 12, "≡", 36, 700, "#C1FF72", "Gelasio", anchor="middle")
            + T(cx, cy + 66, "mesmo", 15, 700, TEAL, anchor="middle") + T(cx, cy + 84, "princípio", 15, 700, TEAL, anchor="middle"))


def chip_filo(x, y, k, cor, nome, txt):
    w = 64 + len(nome) * 11.5 + len(txt) * 9.4 + 26
    return (f'<rect x="{x}" y="{y}" width="{w}" height="48" rx="24" fill="#fff" stroke="{LINE}" stroke-width="2"/>' + ic(k, x + 14, y + 10, 28, cor)
            + f'<text x="{x+52}" y="{y+31}"><tspan font-family="Gelasio" font-weight="700" font-size="20" fill="{NAVY}">{nome}</tspan>'
              f'<tspan dx="10" font-family="Manrope" font-weight="600" font-size="17" fill="{SLATE}">→ {txt}</tspan></text>'), w


def painel_sin(L, Tp, Wp, Hp, chart_w=560, chart_h=380, compacto=False):
    s = f'<rect x="{L}" y="{Tp}" width="{Wp}" height="{Hp}" rx="28" fill="{LIGHT}"/>'
    s += T(L + 40, Tp + 50, "SISTEMA INTERLIGADO NACIONAL", 15, 700, "#7B8794", ls=1.5)
    s += T(L + 40, Tp + 88, "Quanto vale a água guardada?", 30, 700, NAVY, "Gelasio")
    rw = 100 if compacto else 120
    g, _ = fcf(L + rw + 70, Tp + 120, chart_w, chart_h)
    s += g
    for xr, nivel, nome, ci, cf_ in ((L + 34, 0, "Turbinar agora", "BAIXO", "ALTO"), (L + Wp - rw - 34, .95, "Guardar", "ALTO", "BAIXO")):
        cx = xr + rw / 2
        s += reservatorio(xr, Tp + 150, rw, rw * .62, nivel)
        s += T(cx, Tp + 252, nome, 18, 700, NAVY, "Gelasio", anchor="middle")
        s += T(cx, Tp + 278, "imediato", 14, 600, IMED, anchor="middle") + T(cx, Tp + 295, ci, 14, 800, IMED, anchor="middle")
        s += T(cx, Tp + 320, "futuro", 14, 600, FUT, anchor="middle") + T(cx, Tp + 337, cf_, 14, 800, FUT, anchor="middle")
    return s


HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'


def salvar(nome, s):
    body = TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS}{s}</svg>' + REF + RODAPE
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=body))


# ===================================================================== P1 — layout da v4, direita refeita
L, Tp, Wp, Hp = 110, 170, 1050, 760
s = painel_sin(L, Tp, Wp, Hp)
yh = Tp + 548
s += f'<line x1="{L+40}" x2="{L+Wp-40}" y1="{yh-24}" y2="{yh-24}" stroke="{LINE}" stroke-width="2"/>'
s += T(L + 40, yh + 8, "Por que modelos de vários horizontes?", 22, 700, NAVY, "Gelasio")
s += (f'<text font-family="Manrope" font-weight="500" font-size="17" fill="{SLATE}"><tspan x="{L+40}" y="{yh+40}">O valor da água depende de meses e anos à frente; o despacho, de horas.</tspan>'
      f'<tspan x="{L+40}" y="{yh+64}">Cada modelo resolve o seu horizonte e entrega ao seguinte o custo futuro [8–11].</tspan></text>')
s += chevrons(L + 40, yh + 92, [("NEWAVE", "médio e longo prazo", 300, "#0E4F86"), ("DECOMP", "curto prazo", 300, "#2C6FB0"), ("DESSEM", "programação diária", 300, AGUA)], h=44, gap=8)
R = 1250
s += T(R, Tp + 34, "A CADA INTERVALO, A MESMA PERGUNTA", 15, 700, TEAL, ls=1.5)
s += (f'<text font-family="Gelasio" font-weight="700" font-size="44" fill="{NAVY}"><tspan x="{R}" y="{Tp+92}">Usar agora ou</tspan>'
      f'<tspan x="{R}" y="{Tp+144}">guardar para depois?</tspan></text>')
# ponte sobre a borda do cartão + seta
s += ponte(L + Wp, Tp + 300)
s += (f'<path d="M{L+Wp+40} {Tp+300} C{R-40} {Tp+300}, {R-50} {Tp+246}, {R-6} {Tp+246}" fill="none" stroke="{G2}" stroke-width="3" stroke-dasharray="3 8" stroke-linecap="round"/>')
s += T(R, Tp + 220, "Na microrrede:", 20, 700, NAVY, "Gelasio")
for i, (k, cor, a, b, mini) in enumerate((("bat", BAT, "Energia usada agora", "falta na ponta", "t"), ("h2", PEM, "Ligar a PEMFC", "tempo mínimo ligada", "p"))):
    y = Tp + 246 + i * 138
    s += f'<rect x="{R-6}" y="{y}" width="566" height="120" rx="22" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
    s += f'<circle cx="{R+36}" cy="{y+60}" r="28" fill="{NAVY}"/>' + ic(k, R + 18, y + 42, 36, "#fff")
    s += T(R + 80, y + 54, a, 20, 700, NAVY, "Gelasio") + T(R + 80, y + 80, "→ " + b, 17, 600, REDE if mini == "t" else PEM)
    s += (tarifa_mini(R + 330, y + 30, 200, 58) if mini == "t" else pemfc_mini(R + 330, y + 34, 200, 54))
yf = Tp + 548
s += T(R, yf + 8, "O objetivo muda com o sistema:", 20, 700, NAVY, "Gelasio")
c1, w1 = chip_filo(R - 6, yf + 30, "grid", REDE, "Conectada", "reduzir o custo")
c2, _ = chip_filo(R - 6, yf + 92, "bat", BAT, "Isolada", "garantir o atendimento")
s += c1 + c2
s += (f'<text x="{R}" y="{Tp+728}" font-family="Gelasio" font-size="26"><tspan font-style="italic" fill="{TEAL}">Cada decisão presente tem um </tspan>'
      f'<tspan font-weight="700" fill="{NAVY}">custo futuro.</tspan></text>')
salvar("S4v5_P1", s)

# ===================================================================== P2 — espelho: dois cartões e a ponte no meio
s = T(110, 200, "A CADA INTERVALO, A MESMA PERGUNTA", 15, 700, TEAL, ls=1.5)
s += T(110, 256, "Usar agora ou guardar para depois?", 46, 700, NAVY, "Gelasio")
s += (f'<text x="1810" y="256" text-anchor="end" font-family="Gelasio" font-size="26"><tspan font-style="italic" fill="{TEAL}">Cada decisão presente tem um </tspan>'
      f'<tspan font-weight="700" fill="{NAVY}">custo futuro.</tspan></text>')
L, Tp, Wp, Hp = 110, 290, 840, 630
s += painel_sin(L, Tp, Wp, Hp, chart_w=440, chart_h=330, compacto=True)
yh = Tp + 486
s += f'<line x1="{L+40}" x2="{L+Wp-40}" y1="{yh-22}" y2="{yh-22}" stroke="{LINE}" stroke-width="2"/>'
s += T(L + 40, yh + 10, "Valor de meses à frente, despacho de horas: cada horizonte orienta o seguinte [8–11].", 16, 600, SLATE)
s += chevrons(L + 40, yh + 34, [("NEWAVE", "médio e longo prazo", 248, "#0E4F86"), ("DECOMP", "curto prazo", 248, "#2C6FB0"), ("DESSEM", "diário", 248, AGUA)], h=42, gap=8)
R0, RW = 1030, 780
s += f'<rect x="{R0}" y="{Tp}" width="{RW}" height="{Hp}" rx="28" fill="{LIGHT}"/>'
s += T(R0 + 40, Tp + 50, "MICRORREDE", 15, 700, "#7B8794", ls=1.5)
s += T(R0 + 40, Tp + 88, "O mesmo vale para a energia e os estados", 28, 700, NAVY, "Gelasio")
for i, (k, cor, a, b, mini) in enumerate((("bat", BAT, "Energia usada agora", "falta na ponta", "t"), ("h2", PEM, "Ligar a PEMFC", "tempo mínimo ligada", "p"))):
    y = Tp + 130 + i * 168
    s += f'<rect x="{R0+30}" y="{y}" width="{RW-60}" height="146" rx="22" fill="#fff"/>'
    s += f'<circle cx="{R0+86}" cy="{y+73}" r="34" fill="{NAVY}"/>' + ic(k, R0 + 64, y + 51, 44, "#fff")
    s += T(R0 + 140, y + 64, a, 22, 700, NAVY, "Gelasio") + T(R0 + 140, y + 92, "→ " + b, 18, 600, REDE if mini == "t" else PEM)
    s += (f'<path d="M{R0+400} {y+73} h40" stroke="{cor}" stroke-width="3" stroke-dasharray="3 7" stroke-linecap="round"/>')
    s += (tarifa_mini(R0 + 460, y + 38, 260, 72) if mini == "t" else pemfc_mini(R0 + 460, y + 44, 260, 66))
yf = Tp + 486
s += f'<line x1="{R0+40}" x2="{R0+RW-40}" y1="{yf-22}" y2="{yf-22}" stroke="{LINE}" stroke-width="2"/>'
s += T(R0 + 40, yf + 10, "Mas o objetivo muda com o sistema:", 16, 600, SLATE)
c1, w1 = chip_filo(R0 + 40, yf + 32, "grid", REDE, "Conectada", "reduzir o custo")
c2, _ = chip_filo(R0 + 40 + w1 + 14, yf + 32, "bat", BAT, "Isolada", "garantir o atendimento")
s += c1 + c2
s += ponte(990, Tp + 270)
salvar("S4v5_P2", s)
print("ok")
