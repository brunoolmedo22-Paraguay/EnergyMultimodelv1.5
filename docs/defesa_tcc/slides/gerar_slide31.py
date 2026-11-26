"""Slide 31 (deck) — Resultados: custos operacionais C1–C4 (Tabela 7.1 e Seção 7.1 do artigo). Três propostas:
  P1 barras empilhadas (custo na ponta × fora de ponta) · P2 cascata C1 → FV → bateria → C4 · P3 matriz 2 × 2 (FV × bateria), aditividade.
Dados (Tabela 7.1, rodadas 4f7da832, dbccd121, 7252f033, 14d8e5b3): custo realizado 1.274,25 / 1.100,97 / 1.038,31 / 865,03 R$;
na ponta 523,54 / 521,08 / 232,70 / 230,24 R$; fora de ponta = diferença (conferida: importação fora de ponta × 0,44234).
Importação na ponta 270,01 / 268,74 / 120,01 / 118,74 kWh. Reduções 173,28 (13,6 %), 235,94 (18,5 %), 409,22 (32,1 %).
C1: ponta = 13,7 % da energia e 41,1 % do custo. C2: 98,6 % da redução fora de ponta; preço médio 0,648 → 0,697 R$/kWh.
C3/C4: banco termina com 20,00 kWh (60,00 no início); redução só do ciclo do dia = R$ 217,31 (estimativa do artigo)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, NAVY, SLATE, LIGHT, LINE, T, div, ic
from gerar_slide8 import rodape
from gerar_slide24_25 import DEFS, COR, NOME, PONTA, MUTED

D = os.path.dirname(os.path.abspath(__file__))
TIT = "Resultados — custos operacionais (C1–C4)"
REF = "Tabela 7.1 e Seção 7.1 do artigo · rodadas 4f7da832 (C1), dbccd121 (C2), 7252f033 (C3) e 14d8e5b3 (C4) · custos realizados, sem o custo futuro estimado"
FORA = "#AEBBC9"
CFG = [("C1", ["grid"], 1274.25, 523.54, 270.01, None),
       ("C2", ["grid", "sun"], 1100.97, 521.08, 268.74, (173.28, "13,6")),
       ("C3", ["grid", "bat"], 1038.31, 232.70, 120.01, (235.94, "18,5")),
       ("C4", ["grid", "sun", "bat"], 865.03, 230.24, 118.74, (409.22, "32,1"))]
NOTA = ("Sem condição final, o banco termina o dia com 20 kWh (começou com 60): a redução só do ciclo do dia é estimada em "
        "<b>R$&nbsp;217,31</b> em C3. Em todas: sem déficit, exportação ou vertimento.")


def br(v, d=2):
    s = f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def icones(x, y, recs, r=18):
    o = ""
    for j, k in enumerate(recs):
        cx = x + j * (2 * r + 8)
        o += f'<circle cx="{cx}" cy="{y}" r="{r}" fill="#fff" stroke="{COR[k]}" stroke-width="2.5"/>' + ic(k, cx - r * .62, y - r * .62, r * 1.24, COR[k])
    return o


def salvar(nome, s, h, ref=REF):
    body = (f'<div class="tt">{TIT}</div><svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS}{s}</svg>'
            + h + f'<div class="ref">{ref}</div>' + rodape(31))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


PONTOS = [("A ponta pesa", "Em C1, a ponta tem 13,7&nbsp;% da energia e <b>41,1&nbsp;% do custo</b>: a tarifa é 4,4 vezes maior."),
          ("Cada recurso atua num posto", "O FV reduz a importação <b>fora de ponta</b>; a bateria desloca energia para a <b>ponta</b>, onde a importação cai de 270 para 120&nbsp;kWh."),
          ("Os efeitos se somam", "C4 reduz <b>R$&nbsp;409,22</b> (32,1&nbsp;%), igual à soma das reduções de C2 e C3.")]


def pontos(x, y, w, gap=30):
    h = ""
    for t, d in PONTOS:
        h += div(x, y, w, None, f'<div style="font:700 26px Gelasio,serif;color:#14213D;margin-bottom:6px">{t}</div>{d}', "p", "font-size:22px;line-height:1.45")
        y += 168 + gap
    return h


# ===================================================================== P1 · barras empilhadas ponta × fora de ponta
def p1():
    s, h = "", ""
    s += f'<rect x="110" y="170" width="1060" height="680" rx="26" fill="#fff" stroke="{LINE}" stroke-width="2" filter="url(#sh)"/>'
    x0, yb, H, vmax = 200, 720, 450, 1400
    Y = lambda v: yb - H * v / vmax
    for v in (0, 500, 1000):
        s += f'<line x1="{x0}" x2="1130" y1="{Y(v)}" y2="{Y(v)}" stroke="#E3E9E8" stroke-width="1.5"/>' + T(x0 - 14, Y(v) + 8, br(v, 0), 22, 600, MUTED, anchor="end")
    s += T(x0 - 14, Y(vmax) + 4, "R$", 22, 700, MUTED, anchor="end")
    bw, gap = 150, 84
    for i, (c, recs, tot, pon, imp, red) in enumerate(CFG):
        x = x0 + 60 + i * (bw + gap)
        fora = tot - pon
        s += f'<rect x="{x}" y="{Y(fora)}" width="{bw}" height="{yb-Y(fora)}" fill="{FORA}"/>'
        s += f'<rect x="{x}" y="{Y(tot)}" width="{bw}" height="{Y(fora)-Y(tot)}" fill="{PONTA}"/>'
        s += T(x + bw / 2, Y(tot) + (Y(fora) - Y(tot)) / 2 + 8, br(pon, 0), 22, 800, "#fff", anchor="middle")
        s += T(x + bw / 2, Y(fora) + (yb - Y(fora)) / 2 + 8, br(fora, 0), 22, 800, NAVY, anchor="middle")
        s += T(x + bw / 2, Y(tot) - 18, br(tot), 28, 700, NAVY, "Gelasio", anchor="middle")
        if red:
            s += T(x + bw / 2, Y(tot) - 54, f"−{red[1]} %", 24, 800, "#1F7A6D", anchor="middle")
        s += T(x + bw / 2, yb + 40, c, 30, 700, NAVY, "Gelasio", anchor="middle")
        s += icones(x + bw / 2 - (len(recs) - 1) * 22, yb + 78, recs)
    s += f'<line x1="{x0}" x2="1130" y1="{yb}" y2="{yb}" stroke="{NAVY}" stroke-width="2"/>'
    s += f'<rect x="{x0}" y="196" width="22" height="22" rx="4" fill="{PONTA}"/>' + T(x0 + 32, 215, "Custo na ponta", 22, 600, SLATE)
    s += f'<rect x="{x0+240}" y="196" width="22" height="22" rx="4" fill="{FORA}"/>' + T(x0 + 272, 215, "Fora de ponta", 22, 600, SLATE)
    h += pontos(1220, 176, 590)
    h += div(110, 868, 1700, None, NOTA, "p", "font-size:22px")
    salvar("S31_P1_barras", s, h)


# ===================================================================== P2 · cascata C1 → FV → bateria → C4
def p2():
    s, h = "", ""
    s += f'<rect x="110" y="170" width="1060" height="680" rx="26" fill="#fff" stroke="{LINE}" stroke-width="2" filter="url(#sh)"/>'
    x0, yb, H, vmax = 200, 720, 470, 1400
    Y = lambda v: yb - H * v / vmax
    for v in (0, 500, 1000):
        s += f'<line x1="{x0}" x2="1130" y1="{Y(v)}" y2="{Y(v)}" stroke="#E3E9E8" stroke-width="1.5"/>' + T(x0 - 14, Y(v) + 8, br(v, 0), 22, 600, MUTED, anchor="end")
    s += T(x0 - 14, Y(vmax) + 4, "R$", 22, 700, MUTED, anchor="end")
    passos = [("C1", "Rede", 0, 1274.25, NAVY, "1.274,25"), ("FV", "−173,28", 1100.97, 1274.25, COR["sun"], "−13,6 %"),
              ("Bateria", "−235,94", 865.03, 1100.97, COR["bat"], "−18,5 %"), ("C4", "Rede + FV + bateria", 0, 865.03, "#1F7A6D", "865,03")]
    bw, gap = 160, 74
    prev = None
    for i, (nome, sub, a, b, cor, lab) in enumerate(passos):
        x = x0 + 50 + i * (bw + gap)
        s += f'<rect x="{x}" y="{Y(b)}" width="{bw}" height="{Y(a)-Y(b)}" rx="6" fill="{cor}"/>'
        if prev is not None:
            s += f'<line x1="{prev}" x2="{x}" y1="{Y(b)}" y2="{Y(b)}" stroke="{SLATE}" stroke-width="2" stroke-dasharray="6 5"/>'
        prev = x + bw
        if a:
            s += f'<line x1="{prev}" x2="{prev+gap}" y1="{Y(a)}" y2="{Y(a)}" stroke="{SLATE}" stroke-width="2" stroke-dasharray="6 5"/>'
            s += T(x + bw / 2, Y(b) - 18, sub, 26, 700, NAVY, "Gelasio", anchor="middle")
            s += T(x + bw / 2, Y(b) + (Y(a) - Y(b)) / 2 + 8, lab, 22, 800, "#fff", anchor="middle")
        else:
            s += T(x + bw / 2, Y(b) - 18, lab, 28, 700, NAVY, "Gelasio", anchor="middle")
        s += T(x + bw / 2, yb + 40, nome, 28, 700, NAVY, "Gelasio", anchor="middle")
    s += f'<line x1="{x0}" x2="1130" y1="{yb}" y2="{yb}" stroke="{NAVY}" stroke-width="2"/>'
    h += div(x0 + 50 + 3 * (bw + gap) - 30, yb + 62, bw + 60, None, "−32,1 %", "", "font:800 24px Manrope;color:#1F7A6D;text-align:center")
    h += div(150, 196, 980, None, "C2 = C1 − FV (R$&nbsp;1.100,97) · C3 = C1 − bateria (R$&nbsp;1.038,31)", "p", "font-size:22px")
    h += pontos(1220, 176, 590)
    h += div(110, 868, 1700, None, NOTA, "p", "font-size:22px")
    salvar("S31_P2_cascata", s, h)


# ===================================================================== P3 · matriz 2 × 2: FV × bateria
def p3():
    s, h = "", ""
    s += ('<defs><marker id="ms" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="16" markerHeight="16" markerUnits="userSpaceOnUse" orient="auto">'
          f'<path d="M0 0L10 5L0 10z" fill="{COR["sun"]}"/></marker><marker id="mb" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="16" '
          f'markerHeight="16" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0L10 5L0 10z" fill="{COR["bat"]}"/></marker></defs>')
    cx0, cy0, cw, ch, g = 330, 236, 360, 226, 116
    h += div(cx0, 172, 2 * cw + g, None, '<span style="display:flex;justify-content:space-around"><span>Sem FV</span><span>Com FV</span></span>', "",
             "font:700 24px Gelasio,serif;color:#14213D")
    for r, rot in enumerate(("Sem bateria", "Com bateria")):
        h += div(110, cy0 + r * (ch + g) + ch / 2 - 18, 200, None, rot, "", "font:700 24px Gelasio,serif;color:#14213D")
    for i, (c, recs, tot, pon, imp, red) in enumerate(CFG):
        col, row = i % 2, i // 2
        x, y = cx0 + col * (cw + g), cy0 + row * (ch + g)
        destaque = c == "C4"
        s += (f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="24" fill="{"#1F7A6D" if destaque else "#fff"}" stroke="{LINE}" stroke-width="2"'
              + ('' if destaque else ' filter="url(#sh)"') + "/>")
        tc, sc = ("#fff", "#DDEFEC") if destaque else (NAVY, "#4A5568")
        s += T(x + 28, y + 52, c, 32, 700, tc, "Gelasio")
        h += div(x + 28, y + 78, cw - 56, None, f"R$&nbsp;{br(tot)}", "", f"font:700 46px/1.1 Gelasio,serif;color:{tc}")
        h += div(x + 28, y + 140, cw - 56, None, f"Na ponta: R$&nbsp;{br(pon)}<br>{br(imp, 0)}&nbsp;kWh importados na ponta", "",
                 f"font:500 22px/1.45 Manrope;color:{sc}")
        if red:
            s += (f'<rect x="{x+cw-150}" y="{y+24}" width="126" height="40" rx="20" fill="{"#fff" if destaque else "#E3F3F1"}"/>'
                  + T(x + cw - 87, y + 52, f"−{red[1]} %", 22, 800, "#1F7A6D", anchor="middle"))
    # setas com os deltas (mesmos nas duas linhas e nas duas colunas)
    for row in (0, 1):
        y = cy0 + row * (ch + g) + ch / 2
        xa = cx0 + cw + 10
        s += f'<line x1="{xa}" x2="{xa+g-26}" y1="{y+16}" y2="{y+16}" stroke="{COR["sun"]}" stroke-width="4" marker-end="url(#ms)"/>'
        s += T(xa + (g - 20) / 2, y - 6, "−173,28", 22, 800, "#A57A0E", anchor="middle")
    for col in (0, 1):
        x = cx0 + col * (cw + g) + cw / 2
        ya = cy0 + ch + 10
        s += f'<line x1="{x}" x2="{x}" y1="{ya}" y2="{ya+g-26}" stroke="{COR["bat"]}" stroke-width="4" marker-end="url(#mb)"/>'
        s += T(x + 18, ya + g / 2 + 4, "−235,94", 22, 800, COR["bat"])
    h += pontos(1300, 176, 510)
    h += div(110, 868, 1700, None, NOTA, "p", "font-size:22px")
    salvar("S31_P3_matriz", s, h)


if __name__ == "__main__":
    p1()
    p2()
    p3()
