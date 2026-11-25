"""Slide 23 (deck) — Estratégia de avaliação: três propostas. Fonte: Seção 6.1 do artigo.
Dois sistemas com filosofias de despacho diferentes: microrrede industrial conectada (minimiza custo de importação, 24 h; varia a COMPOSIÇÃO,
C1–C4, com mesma demanda, tarifa, dia meteorológico, conexão e estratégia) × embarcação híbrida isolada (minimiza H₂, 120 min; mesma
composição, varia o estado inicial da bateria e a reserva final, C5–C6). Ambos hipotéticos; contexto de ensaio (realizado = previsto)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, DEF2, HEAD, NAVY, SLATE, TEAL, LIGHT, LINE, BAT, PEM, MUTED, T, div, ic, SOLAR, REDE
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
TIT = '<div class="tt">Estratégia de avaliação</div>'
REF = "Seção 6.1 do artigo · sistemas hipotéticos, contexto de ensaio"
REC = {"sun": (SOLAR, "Solar"), "bat": (BAT, "Bateria"), "h2": (PEM, "PEMFC"), "grid": (REDE, "Rede"), "load": (NAVY, "Demanda")}


def salvar(nome, s, h):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEF2}{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(23))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


def bus(x, y, w, ks, r=26, rot=True, apagados=()):
    o = f'<rect x="{x}" y="{y-5}" width="{w}" height="10" rx="5" fill="url(#gb)"/>'
    for i, k in enumerate(ks):
        c, nome = REC[k]
        cx = x + w * (i + .5) / len(ks)
        op = ' opacity=".22"' if k in apagados else ""
        o += f'<g{op}><line x1="{cx}" x2="{cx}" y1="{y+5}" y2="{y+30}" stroke="{c}" stroke-width="3"/><circle cx="{cx}" cy="{y}" r="5" fill="#fff" stroke="{c}" stroke-width="2.5"/>'
        o += f'<circle cx="{cx}" cy="{y+30+r}" r="{r}" fill="#fff" stroke="{c}" stroke-width="2.5"/>' + ic(k, cx - r * .62, y + 30 + r * .38, r * 1.24, c)
        if rot:
            o += T(cx, y + 30 + 2 * r + 24, nome, 17, 600, SLATE, anchor="middle")
        o += "</g>"
    return o


def bateria(x, y, w, h, nivel, cor=BAT, reserva=None):
    o = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#fff" stroke="{cor}" stroke-width="3"/><rect x="{x+w/2-12}" y="{y-8}" width="24" height="8" rx="2" fill="{cor}"/>'
    lv = (h - 10) * nivel
    o += f'<rect x="{x+5}" y="{y+h-5-lv}" width="{w-10}" height="{lv}" rx="6" fill="{cor}"/>'
    if reserva is not None:
        yr = y + h - 5 - (h - 10) * reserva
        o += f'<line x1="{x-10}" x2="{x+w+10}" y1="{yr}" y2="{yr}" stroke="{NAVY}" stroke-width="2.5" stroke-dasharray="6 5"/>'
    return o


LINHAS = [("Conexão", "Conectada à rede", "Isolada"),
          ("O EMS minimiza", "Custo de importação", "Consumo de hidrogênio"),
          ("Horizonte", "24 h", "120 min"),
          ("O que varia", "A composição (C1–C4)", "O estado inicial e a reserva (C5–C6)")]


# ===================================================================== P1 · dois cartões espelhados
def p1():
    s, h = "", ""
    for j, (tit, ks, cor) in enumerate((("Microrrede industrial", ["sun", "bat", "grid", "load"], REDE),
                                         ("Embarcação híbrida", ["h2", "bat", "sun", "load"], PEM))):
        x = 110 + j * 872
        s += f'<rect x="{x}" y="172" width="828" height="620" rx="26" fill="{LIGHT}"/>'
        s += T(x + 40, 226, tit, 30, 700, NAVY, "Gelasio")
        s += bus(x + 120, 270, 588, ks)
        for i, (lab, a, b) in enumerate(LINHAS):
            y = 420 + i * 88
            s += f'<line x1="{x+40}" x2="{x+788}" y1="{y-10}" y2="{y-10}" stroke="#D5DDDC" stroke-width="1.5"/>'
            h += div(x + 40, y, 240, None, lab, "p", "font-size:21px;color:#7B8794;font-weight:700")
            h += div(x + 280, y - 4, 510, None, [a, b][j], "", "font:700 25px/1.25 Gelasio,serif;color:#14213D")
    h += div(110, 820, 1700, 80, "<span>O mesmo EMS nos dois sistemas, sem reformulação. Ambos são <b>hipotéticos</b> e executados em contexto de ensaio, "
             "com demanda e renovável realizadas iguais às previstas.</span>", "p", "font-size:22px;display:flex;align-items:center")
    salvar("S23_P1_espelho", s, h)


# ===================================================================== P2 · matriz das seis configurações
def p2():
    s, h = "", ""
    cols = ["C1", "C2", "C3", "C4", "C5", "C6"]
    xs = [700 + i * 186 for i in range(6)]
    rows = [("sun", "Solar"), ("bat", "Bateria"), ("h2", "PEMFC"), ("grid", "Rede")]
    tem = {"C1": {"grid"}, "C2": {"sun", "grid"}, "C3": {"bat", "grid"}, "C4": {"sun", "bat", "grid"},
           "C5": {"sun", "bat", "h2"}, "C6": {"sun", "bat", "h2"}}
    s += f'<rect x="{xs[0]-80}" y="172" width="{186*4-26}" height="660" rx="24" fill="#FCEDEC"/>'
    s += f'<rect x="{xs[4]-80}" y="172" width="{186*2-26}" height="660" rx="24" fill="#E3F3F1"/>'
    s += T(xs[0] - 50 + (186 * 4 - 26) / 2 - 30, 214, "Microrrede industrial", 24, 700, NAVY, "Gelasio", anchor="middle")
    s += T(xs[4] - 80 + (186 * 2 - 26) / 2, 214, "Embarcação", 24, 700, NAVY, "Gelasio", anchor="middle")
    for i, c in enumerate(cols):
        s += T(xs[i], 270, c, 30, 700, NAVY, "Gelasio", anchor="middle")
    for r, (k, nome) in enumerate(rows):
        y = 330 + r * 96
        col = REC[k][0]
        s += f'<circle cx="150" cy="{y}" r="26" fill="#fff" stroke="{col}" stroke-width="2.5"/>' + ic(k, 134, y - 16, 32, col)
        s += T(194, y + 8, nome, 23, 700, NAVY, "Gelasio")
        for i, c in enumerate(cols):
            if k in tem[c]:
                s += f'<circle cx="{xs[i]}" cy="{y}" r="22" fill="{col}"/>'
            else:
                s += f'<circle cx="{xs[i]}" cy="{y}" r="9" fill="none" stroke="#C9D3DD" stroke-width="2"/>'
    # linha SOC / reserva
    y = 330 + 4 * 96
    s += T(194, y + 8, "Bateria inicial / reserva", 22, 700, NAVY, "Gelasio")
    s += bateria(xs[4] - 22, y - 40, 44, 76, .50, reserva=.30) + bateria(xs[5] - 22, y - 40, 44, 76, .12)
    s += T(xs[4], y + 66, "50 % · reserva", 17, 700, SLATE, anchor="middle") + T(xs[5], y + 66, "12 % · sem", 17, 700, SLATE, anchor="middle")
    s += T(xs[0] + 278, y + 8, "Mesma demanda, tarifa, clima e estratégia", 20, 600, SLATE, anchor="middle")
    h += div(110, 858, 1700, 50, "<span>Na indústria varia a <b>composição</b>; na embarcação, a <b>condição inicial</b>. Sistemas hipotéticos, em contexto de ensaio.</span>",
             "p", "font-size:22px;display:flex;align-items:center")
    salvar("S23_P2_matriz", s, h)


# ===================================================================== P3 · duas filosofias, empilhadas sobre o barramento
def p3():
    s, h = "", ""
    for j, (tit, sub, ks, chips) in enumerate((
            ("Microrrede industrial · conectada", "O EMS minimiza o custo de importação · 24 h", ["sun", "bat", "grid", "load"],
             [("C1", "Rede"), ("C2", "Solar + Rede"), ("C3", "Bateria + Rede"), ("C4", "Solar + Bateria + Rede")]),
            ("Embarcação híbrida · isolada", "O EMS minimiza o consumo de hidrogênio · 120 min", ["h2", "bat", "sun", "load"],
             [("C5", "Bateria a 50 %, com reserva final"), ("C6", "Bateria a 12 %, sem reserva")]))):
        y = 176 + j * 346
        s += f'<rect x="110" y="{y}" width="1700" height="318" rx="26" fill="{LIGHT}"/>'
        s += T(150, y + 52, tit, 30, 700, NAVY, "Gelasio")
        h += div(150, y + 66, 700, None, sub, "p", "font-size:22px")
        s += bus(150, y + 156, 520, ks, r=24)
        h += div(770, y + 26, 500, None, ["Varia a <b>composição</b>", "Varia a <b>condição inicial</b>"][j], "", "font:500 23px Manrope;color:#4A5568")
        for i, (c, d) in enumerate(chips):
            if j == 0:
                xx, yy, ww = 770 + (i % 2) * 510, y + 84 + (i // 2) * 106, 490
            else:
                xx, yy, ww = 770 + i * 510, y + 110, 490
            s += f'<rect x="{xx}" y="{yy}" width="{ww}" height="92" rx="18" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
            s += T(xx + 28, yy + 58, c, 32, 700, REDE if j == 0 else PEM, "Gelasio")
            h += div(xx + 100, yy, ww - 120, 92, d, "", "display:flex;align-items:center;font:600 22px/1.25 Manrope;color:#14213D")
    h += div(110, 876, 1700, 40, "Mesmo EMS em todos os casos, sem reformulação · sistemas hipotéticos, em contexto de ensaio (realizado = previsto).", "p", "font-size:21px")
    salvar("S23_P3_filosofias", s, h)


if __name__ == "__main__":
    p1()
    p2()
    p3()
