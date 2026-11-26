"""Slide 32 (deck) — Resultados: custos operacionais C1–C4, no estilo do deck (pedido do responsável: sem o visual do app aqui).

Uma figura explica tudo: custo do dia de cada caso dividido por posto tarifário (fora de ponta × ponta), com a parcela da ponta
dentro da barra; à direita, o total e o que mudou em relação a C1. Embaixo, lado a lado: «O plano se cumpre» (C4) e a economia
de C1 para C4.
Dados (Tabela 7.1 e Seção 7.1; conferidos nas rodadas 4f7da832, dbccd121, 7252f033, 14d8e5b3):
  total 1.274,25 / 1.100,97 / 1.038,31 / 865,03 R$; ponta 523,54 / 521,08 / 232,70 / 230,24 R$;
  fora de ponta = total − ponta = 750,71 / 579,89 / 805,61 / 634,79 R$; parcela da ponta 41,1 / 47,3 / 22,4 / 26,6 %.
  C2 × C1: fora de ponta −170,82, ponta −2,46 (artigo: 98,6 % fora de ponta). C3 × C1: ponta −290,84, fora de ponta +54,90.
  C4 × C1: −409,22 (−32,1 %) = 173,28 + 235,94. Objetivo do MILP na 1.ª decisão de C4: 865,02 (54,34 + 810,68) × realizado 865,03.
  C3/C4 terminam com 20 kWh (60 no início): ciclo do dia R$ 217,31 em C3."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, NAVY, LIGHT, LINE, T, div
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
TIT = "Resultados — custos operacionais (C1–C4)"
REF = ("Tabela 7.1 e Seção 7.1 do artigo · rodadas 4f7da832 (C1), dbccd121 (C2), 7252f033 (C3) e 14d8e5b3 (C4) · "
       "custos realizados, sem o custo futuro estimado")
PONTA, FORA, TEAL = "#E0524F", "#C3CCD6", "#1F7A6D"
CASOS = [  # nome, composição, cor, fora de ponta, ponta, total, parcela, mudança × C1
    ("C1", "Rede", "#6B7480", 750.71, 523.54, "1.274,25", "41,1", None),
    ("C2", "Rede + Solar", "#C98A00", 579.89, 521.08, "1.100,97", "47,3", ("−170,82 fora de ponta", "−2,46 na ponta")),
    ("C3", "Rede + Bateria", "#7A63E0", 805.61, 232.70, "1.038,31", "22,4", ("−290,84 na ponta", "+54,90 fora de ponta")),
    ("C4", "Rede + Solar + Bateria", TEAL, 634.79, 230.24, "865,03", "26,6", ("−293,30 na ponta", "−115,92 fora de ponta")),
]


def br(v):
    return f"{v:,.0f}".replace(",", ".")


def slide():
    s, h = "", ""
    X0, WMAX, VMAX = 470, 740, 1300.0
    xs = lambda v: X0 + WMAX * v / VMAX
    y0, rh = 236, 92
    # cabeçalhos e legenda
    h += div(110, 172, 340, None, "Custo do dia", "", "font:700 24px Gelasio,serif;color:#14213D")
    h += div(X0, 176, 700, None, f'<span style="display:inline-flex;align-items:center;gap:10px;margin-right:30px">'
             f'<i style="width:22px;height:22px;border-radius:5px;background:{FORA};display:inline-block"></i>Fora de ponta</span>'
             f'<span style="display:inline-flex;align-items:center;gap:10px"><i style="width:22px;height:22px;border-radius:5px;background:{PONTA};display:inline-block"></i>'
             f'Ponta (18:00–21:00)</span>', "p", "font-size:22px;display:flex")
    h += div(1480, 172, 330, None, "Em relação a C1", "", "font:700 24px Gelasio,serif;color:#14213D")
    for v in (0, 500, 1000):
        s += f'<line x1="{xs(v)}" x2="{xs(v)}" y1="{y0-10}" y2="{y0+4*rh-14}" stroke="#E3E9E8" stroke-width="1.5"/>'
        s += T(xs(v), y0 + 4 * rh + 14, f"R$ {br(v)}", 20, 600, "#9AA5B1", anchor="middle")
    for i, (c, comp, cor, fora, pon, tot, parc, mud) in enumerate(CASOS):
        y = y0 + i * rh
        bh = 58
        # rótulo do caso
        s += f'<rect x="110" y="{y}" width="8" height="{bh}" rx="4" fill="{cor}"/>'
        h += div(134, y - 4, 330, None, f'<span style="font:700 32px Gelasio,serif;color:{cor}">{c}</span>', "")
        h += div(134, y + 34, 330, None, comp, "p", "font-size:22px")
        # barra: fora de ponta + ponta
        s += f'<rect x="{X0}" y="{y}" width="{xs(fora+pon)-X0}" height="{bh}" rx="8" fill="{PONTA}"/>'      # barra inteira (ponta)
        s += f'<rect x="{X0}" y="{y}" width="{xs(fora)-X0}" height="{bh}" rx="8" fill="{FORA}"/>'             # fora de ponta por cima
        s += f'<rect x="{xs(fora)-8}" y="{y}" width="8" height="{bh}" fill="{FORA}"/>'                        # junta reta
        s += T((X0 + xs(fora)) / 2, y + bh / 2 + 8, br(fora), 22, 700, "#3B4654", anchor="middle")
        s += T((xs(fora) + xs(fora + pon)) / 2, y + bh / 2 + 8, f"{parc} %", 22, 800, "#fff", anchor="middle")
        # total
        h += div(xs(fora + pon) + 18, y + 6, 240, None, f'R$&nbsp;{tot}', "", f"font:700 32px Gelasio,serif;color:{NAVY};white-space:nowrap")
        # o que mudou
        if mud:
            h += div(1480, y + 2, 330, None, f'<b style="color:#14213D">{mud[0]}</b><br>{mud[1]}', "p", "font-size:22px;line-height:1.3")
        else:
            h += div(1480, y + 14, 330, None, "referência: só a rede", "p", "font-size:22px;color:#9AA5B1")
    # leitura em uma linha
    h += div(110, 634, 1700, None, '<span>A <b style="color:#A57A0E">solar</b> corta o custo <b>fora de ponta</b>; a <b style="color:#7A63E0">bateria</b> '
             'corta a <b style="color:#E0524F">ponta</b> e paga um pouco mais fora dela para carregar. Em C4, os dois efeitos se somam.</span>',
             "p", "font-size:24px")
    # cartões: o plano se cumpre (esq.) · economia C1 → C4 (dir.)
    yc, hc = 722, 186
    s += f'<rect x="110" y="{yc}" width="836" height="{hc}" rx="24" fill="{LIGHT}"/>'
    h += div(144, yc + 22, 780, None, "O plano se cumpre (C4)", "", "font:700 26px Gelasio,serif;color:#14213D")
    for k, (rot, v) in enumerate((("Previsto na 1.ª decisão", "R$&nbsp;865,02"), ("Realizado no fim do dia", "R$&nbsp;865,03"))):
        xx = 144 + k * 280
        h += div(xx, yc + 72, 270, None, rot, "p", "font-size:22px")
        h += div(xx, yc + 104, 270, None, v, "", "font:700 42px Gelasio,serif;color:#14213D;white-space:nowrap")
    h += div(724, yc + 76, 190, 92, '<span style="font:600 20px Manrope">diferença</span><b style="font:700 30px Gelasio,serif">R$&nbsp;0,01</b>', "",
             f"display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:18px;background:#DDEFEC;color:{TEAL}")
    s += f'<rect x="974" y="{yc}" width="836" height="{hc}" rx="24" fill="{TEAL}"/>'
    h += div(1008, yc + 22, 780, None, "Economia de C1 para C4", "", "font:700 26px Gelasio,serif;color:#fff")
    h += div(1008, yc + 70, 420, None, 'R$&nbsp;409,22<span style="font:700 26px Manrope;margin-left:14px;color:#BFE3DC">−32,1&nbsp;%</span>', "",
             "font:700 56px/1.1 Gelasio,serif;color:#fff;white-space:nowrap")
    h += div(1008, yc + 146, 420, None, "por dia: R$&nbsp;1.274,25 → R$&nbsp;865,03", "", "font:500 22px Manrope;color:#DDEFEC")
    h += div(1490, yc + 70, 290, None, '<b style="color:#fff">173,28</b> da solar<br><b style="color:#fff">+ 235,94</b> da bateria<br>'
             '<span style="color:#BFE3DC">= 409,22, sem sinergia</span>', "", "font:500 22px/1.42 Manrope;color:#DDEFEC")
    s += f'<line x1="1466" x2="1466" y1="{yc+72}" y2="{yc+176}" stroke="#5FA89C" stroke-width="2"/>'
    h += div(110, 672, 1700, None, "C3 e C4 terminam o dia com 20&nbsp;kWh na bateria (começaram com 60): o ciclo do dia vale R$&nbsp;217,31 em C3. "
             "Sem déficit, exportação ou vertimento.", "p", "font-size:22px;color:#7B8794")
    body = (f'<div class="tt">{TIT}</div><svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(32))
    open(os.path.join(D, "S32b_postos.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


if __name__ == "__main__":
    slide()
