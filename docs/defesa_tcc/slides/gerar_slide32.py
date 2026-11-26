"""Slide 32 (deck) — Resultados: custos operacionais C1–C4, na mesma linguagem do slide 31 (contêiner do SEEDS, figura do motor
Trama em ~50 % da largura, cartões `.card` à direita). Proposta P1 aprovada; cada caso tem uma cor (ligada ao recurso que
acrescenta): C1 cinza, C2 dourado (solar), C3 violeta (bateria), C4 teal; totais do dia em destaque sob o gráfico.

Figura: custo realizado POR INTERVALO das quatro rodadas (4f7da832, dbccd121, 7252f033, 14d8e5b3), desenhado pela API de raias
do próprio motor (`seeds_fig/extrair.py`, modo `custom`; séries `custo_realizado_intervalo_R` gravadas, escala COMUM 0–50 R$),
com a faixa da ponta. Entrada das séries: `seeds_fig/custos_c1c4.json`.
Números (Tabela 7.1, Seção 7.1, conferidos nos marcos): 1.274,25 / 1.100,97 / 1.038,31 / 865,03 R$; na ponta 523,54 / 521,08 /
232,70 / 230,24 R$ (= 41,1 / 47,3 / 22,4 / 26,6 % do custo); ponta = 13,7 % da energia; FV −173,28 (98,6 % fora de ponta);
bateria −235,94 (R$ 290,84 evitados na ponta − 54,90 a mais fora de ponta); C4 −409,22 = soma; objetivo do MILP na 1.ª decisão
de C4 R$ 865,02 (54,34 + 810,68) × realizado 865,03; banco termina com 20 kWh (60 no início): ciclo do dia R$ 217,31 em C3."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD
from gerar_slide8 import rodape
from gerar_slide31b import CSS_SEEDS, BG, SURF, INK, INK2, INK3, FV, BAT, GRID, FUT, FD, FT
from gerar_slide31c import CSS_31

D = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(D, "assets")
TIT = "Resultados — custos operacionais (C1–C4)"
REF = ("Tabela 7.1 e Seção 7.1 do artigo · rodadas 4f7da832 (C1), dbccd121 (C2), 7252f033 (C3) e 14d8e5b3 (C4) · custos realizados, "
       "sem o custo futuro estimado")
CSS_32 = f"""
.eq{{display:grid;grid-template-columns:150px 1fr auto;align-items:center;gap:14px;padding:9px 0;border-top:1.5px solid rgba(20,24,28,.10)}}
.eq:first-of-type{{border-top:0}}
.eq span{{font:400 22px/1.25 {FT};color:{INK2}}}
.eq b{{font:700 28px {FD};color:{INK};text-align:right;white-space:nowrap}}
.tag{{display:inline-flex;align-items:center;gap:8px;font:700 22px {FT};color:{INK}}}
.tag i{{width:16px;height:16px;border-radius:5px;display:inline-block}}
"""


def figura(nome, x, y, s):
    m = json.load(open(os.path.join(A, nome + ".json"), encoding="utf-8"))
    W, H, pl, pr = m["W"], m["H"], m["padL"], m["padR"]
    v0, v1 = m["view"]
    cw = (W - pl - pr) / (v1 - v0)
    X = lambda k: pl + (k - v0) * cw
    corpo = open(os.path.join(A, nome + ".svg"), encoding="utf-8").read()
    corpo = corpo[corpo.index(">") + 1: corpo.rindex("</svg>")]
    o = (f'<svg x="{x}" y="{y}" width="{W*s}" height="{H*s}" viewBox="0 0 {W} {H}" overflow="visible">'
         f'<rect x="{X(72)}" y="2" width="{X(84)-X(72)}" height="{H-22}" fill="{GRID}" opacity=".10"/>{corpo}</svg>')
    return o, m, (lambda k: x + X(k) * s)


CASOS = [("C1", "#6b7480", "1.274,25", None), ("C2", "#c98a00", "1.100,97", "−13,6&nbsp;%"),
         ("C3", "#7a63e0", "1.038,31", "−18,5&nbsp;%"), ("C4", "#1F7A6D", "865,03", "−32,1&nbsp;%")]
C1, C2, C3, C4 = (c[1] for c in CASOS)
NOTA = ("C3 e C4 terminam com 20&nbsp;kWh (começaram com 60): o ciclo do dia vale R$&nbsp;217,31 em C3. "
        "Sem déficit, exportação ou vertimento.")


def cartao(x, y, w, h, acc, titulo, corpo):
    return f'<div class="card" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;--acc:{acc}"><h3>{titulo}</h3>{corpo}</div>'


def barra(x, y, w, h, cor, r=8):
    return f'<div class="barra" style="left:{x}px;top:{y}px;width:{w:.0f}px;height:{h}px;border-radius:{r}px;background:{cor}"></div>'


def cartoes_direita(xr, wr):
    h = ""
    # 1 · a ponta pesa menos: fração do custo do dia que cai na ponta, C1 × C4 (barras 100 %)
    y, hc = 180, 186
    h += cartao(xr, y, wr, hc, GRID, "Parcela do custo do dia paga na ponta", "")
    lb, bx, bw = 64, xr + 96, 520
    for k, (c, cor, frac, txt) in enumerate((("C1", C1, .411, "41,1&nbsp;%"), ("C4", C4, .266, "26,6&nbsp;%"))):
        yy = y + 56 + k * 48
        h += f'<div class="sd" style="left:{xr+30}px;top:{yy+3}px;font:700 24px {FD};color:{cor}">{c}</div>'
        h += barra(bx, yy, bw, 36, "#e2e2df") + barra(bx, yy, bw * frac, 36, GRID)
        h += f'<div class="sd" style="left:{bx+bw+18}px;top:{yy}px;font:700 32px {FD};color:{INK};white-space:nowrap">{txt}</div>'
    h += f'<div class="sd" style="left:{xr+30}px;top:{y+hc-40}px;font:400 22px {FT};color:{INK3}">a ponta tem só 13,7&nbsp;% da energia do dia</div>'
    # 2 · os efeitos se somam: barras de redução na mesma escala (a de C4 = solar + bateria, encaixadas)
    y2, h2 = y + hc + 14, 356
    h += cartao(xr, y2, wr, h2, C4, "Os efeitos se somam: redução em relação a C1", "")
    esc = 380 / 409.22
    bx2 = xr + 196
    linhas = [("Solar", "C2", C2, 0, 173.28, "R$&nbsp;173,28"), ("Bateria", "C3", C3, 173.28, 235.94, "R$&nbsp;235,94"),
              ("Juntas", "C4", C4, 0, 409.22, "R$&nbsp;409,22")]
    for k, (rot, c, cor, off, v, txt) in enumerate(linhas):
        yy = y2 + 60 + k * 62 + (10 if k == 2 else 0)
        h += (f'<div class="sd" style="left:{xr+30}px;top:{yy+4}px;width:180px;font:600 22px {FT};color:{INK2};white-space:nowrap">'
              f'<b style="font:700 22px {FD};color:{cor}">{c}</b>&nbsp; {rot}</div>')
        if k == 2:
            h += f'<div class="sd" style="left:{xr+30}px;top:{yy-12}px;width:{wr-60}px;border-top:1.5px dashed rgba(20,24,28,.22)"></div>'
        h += barra(bx2 + off * esc, yy, v * esc, 38, cor)
        h += f'<div class="sd" style="left:{bx2+380+18}px;top:{yy+2}px;font:700 28px {FD};color:{INK};white-space:nowrap">−{txt}</div>'
    h += (f'<div class="sd" style="left:{xr+30}px;top:{y2+250}px;width:{wr-60}px;font:400 22px/1.3 {FT};color:{INK2}">'
          f'<b style="color:{INK}">−32,1&nbsp;% = 13,6&nbsp;% + 18,5&nbsp;%</b> · solar fora de ponta, bateria na ponta</div>'
          f'<div class="sd" style="left:{xr+30}px;top:{y2+288}px;width:{wr-60}px;font:400 22px/1.3 {FT};color:{INK3}">{NOTA}</div>')
    # 3 · o plano se cumpre
    y3 = y2 + h2 + 14
    h3 = 898 - y3
    h += cartao(xr, y3, wr, h3, FUT, "O plano se cumpre (C4)", "")
    blocos = [("Previsto na 1.ª decisão", "R$&nbsp;865,02"), ("Realizado no fim do dia", "R$&nbsp;865,03")]
    for k, (rot, v) in enumerate(blocos):
        xx = xr + 30 + k * 290
        h += (f'<div class="sd" style="left:{xx}px;top:{y3+50}px;font:400 22px {FT};color:{INK3}">{rot}</div>'
              f'<div class="sd" style="left:{xx}px;top:{y3+78}px;font:700 40px {FD};letter-spacing:-.02em;color:{INK};white-space:nowrap">{v}</div>')
    h += (f'<div class="sd" style="left:{xr+wr-206}px;top:{y3+56}px;width:176px;height:66px;border-radius:16px;background:#e3f1ee;'
          f'display:flex;flex-direction:column;align-items:center;justify-content:center;font:600 20px {FT};color:#1F7A6D">diferença'
          f'<b style="font:700 26px {FD}">R$&nbsp;0,01</b></div>')
    return h


def salvar(nome, s, h):
    body = ('<link rel="stylesheet" href="assets/fonts_seeds.css">' + f'<div class="tt">{TIT}</div>'
            + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(32))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM + CSS_SEEDS + CSS_31 + CSS_32, body=body))


# ===================================================================== P1 · custo por intervalo C1–C4 (motor do SEEDS) + totais + cartões
def p1():
    s = f'<rect x="110" y="166" width="1700" height="746" rx="30" fill="{BG}"/><rect x="124" y="180" width="860" height="718" rx="24" fill="{SURF}"/>'
    h = f'<div class="sd" style="left:150px;top:198px;font:600 22px {FT};color:{INK2}">Custo realizado por intervalo de 15 min [R$]</div>'
    f_, m, XS = figura("seeds_custos_c1c4", 136, 232, 1.53)
    s += f_
    h += (f'<div class="sd" style="left:{(XS(72)+XS(84))/2-90}px;top:198px;width:180px;text-align:center;white-space:nowrap;'
          f'font:700 22px {FT};color:{GRID}">Ponta</div>')
    # totais pagos no dia, um por caso, na cor do caso
    h += f'<div class="sd" style="left:150px;top:774px;font:600 22px {FT};color:{INK2}">Total pago no dia</div>'
    x0, w, g = 140, 200, 10
    for k, (c, cor, tot, red) in enumerate(CASOS):
        x = x0 + k * (w + g)
        h += (f'<div class="sd" style="left:{x}px;top:808px;width:{w}px;height:78px;border-radius:16px;background:#fff;box-shadow:inset 0 -5px 0 {cor}">'
              f'<div style="position:absolute;left:16px;top:6px;font:700 22px {FD};color:{cor}">{c}</div>'
              + (f'<div style="position:absolute;right:14px;top:8px;font:700 20px {FT};color:#1F7A6D">{red}</div>' if red else "")
              + f'<div style="position:absolute;left:16px;top:32px;font:700 32px {FD};letter-spacing:-.02em;color:{INK};white-space:nowrap">'
              f'<span style="font:600 20px {FT};color:{INK3}">R$</span>&nbsp;{tot}</div></div>')
    h += cartoes_direita(1000, 796)
    salvar("S32_P1_intervalos", s, h)


if __name__ == "__main__":
    p1()
