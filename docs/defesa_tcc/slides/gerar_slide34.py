"""Slide 34 (deck) — Expansibilidade e desempenho computacional (Seção 7.4 e Tabela 7.2 do artigo), no estilo dos slides 32–33.

Esquerda: as nove composições executadas pelo MESMO código do EMS e a dimensão da 1.ª janela do MILP (variáveis, das quais binárias)
— Tabela 7.2. Direita: a curva linear por partes da PEMFC usada pelo MILP sobre o modelo estacionário, valores GRAVADOS na rodada
055096cf (C5): 15 vértices em 10–50 kW, 401 pontos do modelo, 402 pontos de validação independentes (o artigo diz 500: divergência
registrada em CONTINUAR.md), erro relativo máximo 0,087 % (limite 0,5 %), subestimação 0. Embaixo: 168 janelas ótimas (14 missões),
≤ 0,42 s por MILP de janela (C1–C5), ≤ 5 s por decisão com o planejador, 11 s (C6) a 277 s (C4) por missão, resíduos ~10⁻¹⁵."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, NAVY, LIGHT, T, div
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
TIT = "Expansibilidade e desempenho computacional"
REF = "Tabela 7.2 e Seção 7.4 do artigo · curva da PEMFC gravada na rodada 055096cf (C5) · bancada de 14 missões sintéticas de 12 h"
TEAL, PEM, CINZA = "#1F7A6D", "#1BA39C", "#9AA5B1"
COMP = [("Rede", 7, 1), ("FV e rede", 13, 1), ("Bateria e rede", 28, 8), ("Bateria e rede (2.º inventário)", 28, 8),
        ("Dois bancos e rede", 32, 6), ("FV, bateria e rede", 34, 8), ("FV, bateria e PEMFC (isolada)", 118, 54),
        ("FV, eólica, bateria, PEMFC e rede", 148, 64), ("Bateria, duas PEMFC e rede", 217, 105)]
CURVA = json.load(open(os.path.join(D, "dados", "pemfc_curva_c5.json"), encoding="utf-8"))


def composicoes(x, y, w, hc):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{hc}" rx="24" fill="{LIGHT}"/>'
    h = div(x + 30, y + 20, w - 60, None, "O mesmo código do EMS, nove composições", "", "font:700 26px Gelasio,serif;color:#14213D")
    h += div(x + 30, y + 58, w - 60, None, f'<span>Variáveis da 1.ª janela do MILP · <b style="color:{TEAL}">das quais binárias</b></span>', "p", "font-size:22px")
    bx, bw, vmax = x + 400, w - 400 - 120, 217.0
    for i, (nome, v, b) in enumerate(COMP):
        yy = y + 104 + i * 45
        h += div(x + 30, yy + 2, 360, None, nome, "p", "font-size:22px;white-space:nowrap;color:#14213D")
        s += f'<rect x="{bx}" y="{yy+4}" width="{max(bw*v/vmax, 4):.0f}" height="30" rx="6" fill="#B9D9D3"/>'
        s += f'<rect x="{bx}" y="{yy+4}" width="{max(bw*b/vmax, 3):.0f}" height="30" rx="6" fill="{TEAL}"/>'
        h += div(bx + bw * v / vmax + 12, yy + 2, 120, None, f'<b style="color:#14213D">{v}</b> · {b}', "p", "font-size:22px;white-space:nowrap")
    return s, h


def curva(x, y, w, hc):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{hc}" rx="24" fill="{LIGHT}"/>'
    h = div(x + 30, y + 20, w - 60, None, "A PEMFC no MILP: curva linear por partes", "", "font:700 26px Gelasio,serif;color:#14213D")
    h += div(x + 30, y + 58, w - 60, None, "Consumo de H₂ [kg/h] × potência líquida [kW]", "p", "font-size:22px")
    px, py, pw, ph = x + 80, y + 108, w - 124, 268
    X = lambda p: px + pw * (p - 10) / 40
    Y = lambda q: py + ph - ph * q / 4.0
    for q in (0, 1, 2, 3, 4):
        s += f'<line x1="{px}" x2="{px+pw}" y1="{Y(q)}" y2="{Y(q)}" stroke="#DCE3E2" stroke-width="1.5"/>' + T(px - 12, Y(q) + 7, str(q), 20, 600, CINZA, anchor="end")
    for p in (10, 20, 30, 40, 50):
        s += T(X(p), py + ph + 28, f"{p} kW" if p == 50 else f"{p}", 20, 600, CINZA, anchor="end" if p == 50 else "middle")
    mod = " ".join(f"{X(p):.1f},{Y(q):.1f}" for p, q in CURVA["modelo"])
    s += f'<polyline points="{mod}" fill="none" stroke="{NAVY}" stroke-width="9" stroke-opacity=".14" stroke-linejoin="round"/>'
    ver = " ".join(f"{X(p):.1f},{Y(q):.1f}" for p, q in CURVA["vertices"])
    s += f'<polyline points="{ver}" fill="none" stroke="{PEM}" stroke-width="3.5" stroke-linejoin="round"/>'
    for p, q in CURVA["vertices"]:
        s += f'<circle cx="{X(p):.1f}" cy="{Y(q):.1f}" r="6.5" fill="#fff" stroke="{PEM}" stroke-width="3"/>'
    # legenda interna
    s += f'<line x1="{px+20}" x2="{px+56}" y1="{py+22}" y2="{py+22}" stroke="{NAVY}" stroke-width="9" stroke-opacity=".14"/>'
    h += div(px + 66, py + 8, 400, None, "modelo estacionário (h2_pemfc)", "p", "font-size:20px")
    s += f'<line x1="{px+20}" x2="{px+56}" y1="{py+58}" y2="{py+58}" stroke="{PEM}" stroke-width="3.5"/><circle cx="{px+38}" cy="{py+58}" r="6" fill="#fff" stroke="{PEM}" stroke-width="3"/>'
    h += div(px + 66, py + 44, 400, None, "PWL com 15 vértices (MILP)", "p", "font-size:20px")
    # números da verificação
    nums = [("0,087&nbsp;%", "erro máximo<br>(limite 0,5&nbsp;%)"), ("0", "subestimação<br>do consumo"), ("402", "pontos de<br>validação")]
    cw = (w - 60) / 3
    for k, (n, t) in enumerate(nums):
        xx = x + 30 + k * cw
        h += div(xx, y + hc - 104, cw - 10, None, f'<div style="font:700 32px Gelasio,serif;color:{TEAL}">{n}</div>'
                 f'<div style="font:500 20px/1.2 Manrope;color:#4A5568">{t}</div>', "")
    return s, h


def kpis(y, hc):
    s, h = "", ""
    it = [("168 de 168", "janelas ótimas, em 14 missões"), ("≤ 0,42&nbsp;s", "por MILP de janela (C1–C5)"),
          ("≤ 5&nbsp;s", "por decisão, com o planejador"), ("277&nbsp;s", "um dia inteiro de operação (C4)"),
          ("~10<sup>−15</sup>", "resíduos da reconstrução independente")]
    w = (1700 - 4 * 18) / 5
    for k, (n, t) in enumerate(it):
        x = 110 + k * (w + 18)
        fundo, tc, sc = (TEAL, "#fff", "#DDEFEC") if k == 0 else (LIGHT, "#14213D", "#4A5568")
        s += f'<rect x="{x}" y="{y}" width="{w}" height="{hc}" rx="22" fill="{fundo}"/>'
        h += div(x + 24, y + 26, w - 48, None, f'<div style="font:700 40px/1.1 Gelasio,serif;color:{tc};white-space:nowrap">{n}</div>'
                 f'<div style="font:500 22px/1.3 Manrope;color:{sc};margin-top:8px">{t}</div>', "")
    return s, h


def slide():
    s, h = "", ""
    for f in (lambda: composicoes(110, 166, 880, 524), lambda: curva(1010, 166, 800, 524), lambda: kpis(712, 196)):
        a, b = f(); s += a; h += b
    body = (f'<div class="tt">{TIT}</div><svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(34))
    open(os.path.join(D, "S34_expansibilidade.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


if __name__ == "__main__":
    slide()
