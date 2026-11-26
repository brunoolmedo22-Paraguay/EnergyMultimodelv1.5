"""Slide 32 (deck) — Resultados: custos operacionais C1–C4, estilo do deck, COM a figura dos quatro custos por intervalo.

Esquerda: custo realizado a cada 15 min de C1, C2, C3 e C4 (séries `custo_realizado_intervalo_R` gravadas nas rodadas 4f7da832,
dbccd121, 7252f033, 14d8e5b3; em `seeds_fig/custos_c1c4.json`), escala comum 0–50 R$, ponta sombreada, cada caso na sua cor e
o total do dia ao lado. Direita: parcela do custo do dia paga na ponta (41,1 / 47,3 / 22,4 / 26,6 %) com a marca de 13,7 % (parcela
da ENERGIA na ponta). Embaixo: «O plano se cumpre» (865,02 × 865,03) e «Economia de C1 para C4» (409,22 = 173,28 + 235,94).
Fonte: Tabela 7.1 e Seção 7.1 do artigo."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, NAVY, LIGHT, LINE, T, div
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
TIT = "Resultados — custos operacionais (C1–C4)"
REF = ("Tabela 7.1 e Seção 7.1 do artigo · séries gravadas nas rodadas 4f7da832 (C1), dbccd121 (C2), 7252f033 (C3) e 14d8e5b3 (C4) · "
       "custos realizados, sem o custo futuro estimado")
PONTA, TEAL = "#E0524F", "#1F7A6D"
CASOS = [("C1", "Rede", "#6B7480", "1.274,25", .411, "41,1"),
         ("C2", "Rede + Solar", "#C98A00", "1.100,97", .473, "47,3"),
         ("C3", "Rede + Bateria", "#7A63E0", "1.038,31", .224, "22,4"),
         ("C4", "Rede + Solar + Bateria", TEAL, "865,03", .266, "26,6")]
SERIES = [L["v"] for L in json.load(open(os.path.join(D, "seeds_fig", "custos_c1c4.json"), encoding="utf-8"))["custom"]]


def figura_custos():
    s, h = "", ""
    px, pw = 172, 640                       # área de desenho
    cw = pw / 96
    X = lambda k: px + k * cw
    y0, rh, ph, vmax = 214, 112, 70, 50.0
    h += div(110, 168, 900, None, "Custo realizado a cada 15 min [R$]", "", "font:700 24px Gelasio,serif;color:#14213D")
    yb_fim = y0 + 3 * rh + 26 + ph
    s += f'<rect x="{X(72)}" y="{y0+2}" width="{X(84)-X(72)}" height="{yb_fim-y0-2}" fill="{PONTA}" opacity=".09"/>'
    for i, ((c, comp, cor, tot, _, _), v) in enumerate(zip(CASOS, SERIES)):
        yt = y0 + i * rh
        base = yt + 26 + ph
        Y = lambda val: base - ph * val / vmax
        h += div(px, yt - 2, 560, None, f'<b style="font:700 24px Gelasio,serif;color:{cor}">{c}</b>&nbsp;&nbsp;{comp}', "p", "font-size:22px")
        for t in (0, 25, 50):
            s += f'<line x1="{px}" x2="{px+pw}" y1="{Y(t)}" y2="{Y(t)}" stroke="{"#C9D3DD" if t == 0 else "#E8EDEC"}" stroke-width="1.4"/>'
        s += T(px - 10, Y(50) + 7, "50", 18, 600, "#9AA5B1", anchor="end") + T(px - 10, base + 6, "0", 18, 600, "#9AA5B1", anchor="end")
        for k, val in enumerate(v):
            s += f'<rect x="{X(k)+.6:.1f}" y="{Y(val):.1f}" width="{cw-1.2:.2f}" height="{base-Y(val):.1f}" rx="1" fill="{cor}"/>'
        # total do dia, grande, na cor do caso
        h += div(px + pw + 22, yt + 30, 200, None, f'<span style="font:600 20px Manrope;color:#7B8794">R$</span>&nbsp;{tot}', "",
                 f"font:700 34px Gelasio,serif;color:{cor};white-space:nowrap")
    h += div(X(72) - 40, y0 - 30, X(84) - X(72) + 80, None, "Ponta", "", f"font:700 22px Manrope;color:{PONTA};text-align:center")
    for k, lab in ((0, "0 h"), (24, "6 h"), (48, "12 h"), (72, "18 h"), (96, "24 h")):
        s += T(X(k), yb_fim + 26, lab, 20, 600, "#9AA5B1", anchor="middle")
    h += div(px + pw + 22, y0 - 30, 200, None, "Total do dia", "", "font:700 22px Manrope;color:#4A5568")
    return s, h


def cartao_ponta(x, y, w, hc):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{hc}" rx="24" fill="{LIGHT}"/>'
    h = div(x + 30, y + 22, w - 60, None, "Parcela do custo do dia paga na ponta", "", "font:700 26px Gelasio,serif;color:#14213D")
    bx, bw = x + 96, w - 96 - 150
    for i, (c, _, cor, _, frac, txt) in enumerate(CASOS):
        yy = y + 84 + i * 66
        h += div(x + 30, yy + 4, 60, None, c, "", f"font:700 26px Gelasio,serif;color:{cor}")
        s += f'<rect x="{bx}" y="{yy}" width="{bw}" height="40" rx="10" fill="#DDE3E2"/><rect x="{bx}" y="{yy}" width="{bw*frac:.0f}" height="40" rx="10" fill="{PONTA}"/>'
        h += div(bx + bw + 16, yy, 130, None, f"{txt}&nbsp;%", "", "font:700 32px Gelasio,serif;color:#14213D;white-space:nowrap")
    xm = bx + bw * .137
    s += f'<line x1="{xm}" x2="{xm}" y1="{y+74}" y2="{y+84+3*66+50}" stroke="{NAVY}" stroke-width="2.5" stroke-dasharray="6 5"/>'
    yt = y + 84 + 4 * 66 + 10
    h += div(x + 30, yt, w - 60, None, f'<span>A linha tracejada marca <b>13,7&nbsp;%</b>, a parcela da <b>energia</b> consumida na ponta. '
             f'A <b style="color:#7A63E0">bateria</b> leva o custo da ponta para perto dela.</span>', "p", "font-size:22px;line-height:1.38")
    h += div(x + 30, yt + 104, w - 60, None, "C3 e C4 terminam com 20&nbsp;kWh na bateria (começaram com 60): o ciclo do dia vale R$&nbsp;217,31 em C3.",
             "p", "font-size:22px;line-height:1.35;color:#7B8794")
    return s, h


def cartoes_baixo(yc, hc):
    s = f'<rect x="110" y="{yc}" width="836" height="{hc}" rx="24" fill="{LIGHT}"/>'
    h = div(144, yc + 20, 780, None, "O plano se cumpre (C4)", "", "font:700 26px Gelasio,serif;color:#14213D")
    for k, (rot, v) in enumerate((("Previsto na 1.ª decisão", "R$&nbsp;865,02"), ("Realizado no fim do dia", "R$&nbsp;865,03"))):
        xx = 144 + k * 280
        h += div(xx, yc + 66, 270, None, rot, "p", "font-size:22px")
        h += div(xx, yc + 98, 270, None, v, "", "font:700 42px Gelasio,serif;color:#14213D;white-space:nowrap")
    h += div(724, yc + 70, 190, 92, '<span style="font:600 20px Manrope">diferença</span><b style="font:700 30px Gelasio,serif">R$&nbsp;0,01</b>', "",
             f"display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:18px;background:#DDEFEC;color:{TEAL}")
    s += f'<rect x="974" y="{yc}" width="836" height="{hc}" rx="24" fill="{TEAL}"/>'
    h += div(1008, yc + 20, 780, None, "Economia de C1 para C4", "", "font:700 26px Gelasio,serif;color:#fff")
    h += div(1008, yc + 64, 440, None, 'R$&nbsp;409,22<span style="font:700 26px Manrope;margin-left:14px;color:#BFE3DC">−32,1&nbsp;%</span>', "",
             "font:700 56px/1.1 Gelasio,serif;color:#fff;white-space:nowrap")
    h += div(1008, yc + 140, 440, None, "por dia: R$&nbsp;1.274,25 → R$&nbsp;865,03", "", "font:500 22px Manrope;color:#DDEFEC")
    h += div(1490, yc + 64, 300, None, '<b style="color:#fff">173,28</b> da solar<br><b style="color:#fff">+ 235,94</b> da bateria<br>'
             '<span style="color:#BFE3DC">= 409,22, sem sinergia</span>', "", "font:500 22px/1.42 Manrope;color:#DDEFEC")
    s += f'<line x1="1466" x2="1466" y1="{yc+66}" y2="{yc+170}" stroke="#5FA89C" stroke-width="2"/>'
    return s, h


def slide():
    s, h = "", ""
    a, b = figura_custos(); s += a; h += b
    a, b = cartao_ponta(1060, 166, 750, 530); s += a; h += b
    a, b = cartoes_baixo(722, 186); s += a; h += b
    body = (f'<div class="tt">{TIT}</div><svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(32))
    open(os.path.join(D, "S32c_custos.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


if __name__ == "__main__":
    slide()
