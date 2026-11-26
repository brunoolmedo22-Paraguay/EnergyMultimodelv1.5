"""Slide 34 (deck) — Expansibilidade e desempenho computacional (Seção 7.4 e Tabela 7.2 do artigo), no estilo dos slides 32–33.

Esquerda: as nove composições executadas pelo MESMO código do EMS e a dimensão da 1.ª janela do MILP (variáveis, das quais binárias)
— Tabela 7.2. Direita: a curva linear por partes da PEMFC usada pelo MILP sobre o modelo estacionário, valores GRAVADOS na rodada
055096cf (C5): 15 vértices em 10–50 kW, 401 pontos do modelo, 402 pontos de validação independentes (o artigo diz 500: divergência
registrada em CONTINUAR.md), erro relativo máximo 0,087 % (limite 0,5 %), subestimação 0. Embaixo: 168 janelas ótimas (14 missões),
≤ 0,42 s por MILP de janela (C1–C5), ≤ 5 s por decisão com o planejador, 11 s (C6) a 277 s (C4) por missão, resíduos ~10⁻¹⁵."""
import bisect
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, NAVY, LIGHT, T, div, ic, SOLAR, REDE, BAT, PEM
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
TIT = "Expansibilidade e desempenho computacional"
REF = "Tabela 7.2 e Seção 7.4 do artigo · curva da PEMFC gravada na rodada 055096cf (C5) · bancada de 14 missões sintéticas de 12 h"
TEAL, CINZA = "#1F7A6D", "#9AA5B1"
COMP = [("Rede", 7, 1, ["grid"]), ("FV e rede", 13, 1, ["sun", "grid"]), ("Bateria e rede", 28, 8, ["bat", "grid"]),
        ("Bateria e rede (2.º inventário)", 28, 8, ["bat", "grid"]), ("Dois bancos e rede", 32, 6, ["bat2", "grid"]),
        ("FV, bateria e rede", 34, 8, ["sun", "bat", "grid"]), ("FV, bateria e PEMFC (isolada)", 118, 54, ["sun", "bat", "h2"]),
        ("FV, eólica, bateria, PEMFC e rede", 148, 64, ["sun", "wind", "bat", "h2", "grid"]),
        ("Bateria, duas PEMFC e rede", 217, 105, ["bat", "h22", "grid"])]
CURVA = json.load(open(os.path.join(D, "dados", "pemfc_curva_c5.json"), encoding="utf-8"))
COR = {"sun": SOLAR, "wind": "#4C8DD6", "bat": BAT, "h2": PEM, "grid": REDE}


def pwl(p):
    V = CURVA["vertices"]
    xs = [v[0] for v in V]
    i = min(max(bisect.bisect_right(xs, p) - 1, 0), len(V) - 2)
    (x0, y0), (x1, y1) = V[i], V[i + 1]
    return y0 + (y1 - y0) * (p - x0) / (x1 - x0)


def composicoes(x, y, w, hc):
    """Colunas compactas: número de variáveis (binárias em verde escuro) e, embaixo, os recursos de cada composição."""
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{hc}" rx="24" fill="{LIGHT}"/>'
    h = div(x + 30, y + 20, w - 60, None, "Mesmo código, nove composições", "", "font:700 26px Gelasio,serif;color:#14213D")
    h += div(x + 30, y + 58, w - 60, None, f'<span>Variáveis da 1.ª janela do MILP · <b style="color:{TEAL}">binárias</b></span>', "p", "font-size:22px")
    cw = (w - 60) / 9
    base, H = y + 296, 170
    s += f'<line x1="{x+30}" x2="{x+w-30}" y1="{base}" y2="{base}" stroke="#C9D3DD" stroke-width="2"/>'
    for i, (nome, v, b, recs) in enumerate(COMP):
        cx = x + 30 + i * cw + cw / 2
        hv, hb = max(H * v / 217, 4), max(H * b / 217, 3)
        s += f'<rect x="{cx-15}" y="{base-hv}" width="30" height="{hv}" rx="5" fill="#B9D9D3"/><rect x="{cx-15}" y="{base-hb}" width="30" height="{hb}" rx="5" fill="{TEAL}"/>'
        s += T(cx, base - hv - 10, str(v), 22, 800, "#14213D", anchor="middle")
        for k, r in enumerate(recs):
            cy, rr = base + 28 + k * 31, 13
            dois = r in ("bat2", "h22")
            kk = r[:-1] if dois else r
            s += f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="#fff" stroke="{COR[kk]}" stroke-width="2.5"/>' + ic(kk, cx - rr * .66, cy - rr * .66, rr * 1.32, COR[kk])
            if dois:
                s += f'<circle cx="{cx+13}" cy="{cy-11}" r="9" fill="{COR[kk]}"/>' + T(cx + 13, cy - 6, "2", 13, 800, "#fff", anchor="middle")
    h += div(x + 30, y + hc - 44, w - 60, None, "7 → 217 variáveis, sem reformular o EMS", "", f"font:700 22px Manrope;color:{TEAL}")
    return s, h


def eixos(s, px, py, pw, ph, xt, yt, fy):
    X = lambda p: px + pw * (p - 10) / 40
    for q in yt:
        s += f'<line x1="{px}" x2="{px+pw}" y1="{fy(q)}" y2="{fy(q)}" stroke="#DCE3E2" stroke-width="1.5"/>' + T(px - 12, fy(q) + 7, xt(q), 20, 600, CINZA, anchor="end")
    for p in (10, 20, 30, 40, 50):
        s += T(X(p), py + ph + 28, str(p), 20, 600, CINZA, anchor="middle")
    s += T(px + pw / 2, py + ph + 58, "Potência líquida [kW]", 20, 700, "#7B8794", anchor="middle")
    return s, X


def curva(x, y, w, hc):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{hc}" rx="24" fill="{LIGHT}"/>'
    h = div(x + 30, y + 20, w - 60, None, "A PEMFC no MILP: curva linear por partes e o seu erro", "", "font:700 26px Gelasio,serif;color:#14213D")
    # --- curva q(P)
    px, py, pw, ph = x + 110, y + 92, 390, 250
    Y = lambda q: py + ph - ph * q / 4.0
    s, X = eixos(s, px, py, pw, ph, str, (0, 1, 2, 3, 4), Y)
    s += f'<text x="{px-78}" y="{py+ph/2}" transform="rotate(-90 {px-78} {py+ph/2})" text-anchor="middle" font-family="Manrope" font-weight="700" font-size="20" fill="#7B8794">H₂ suprido [kg/h]</text>'
    mod = " ".join(f"{X(p):.1f},{Y(q):.1f}" for p, q in CURVA["modelo"])
    s += f'<polyline points="{mod}" fill="none" stroke="{NAVY}" stroke-width="9" stroke-opacity=".14" stroke-linejoin="round"/>'
    ver = " ".join(f"{X(p):.1f},{Y(q):.1f}" for p, q in CURVA["vertices"])
    s += f'<polyline points="{ver}" fill="none" stroke="{PEM}" stroke-width="3" stroke-linejoin="round"/>'
    for p, q in CURVA["vertices"]:
        s += f'<circle cx="{X(p):.1f}" cy="{Y(q):.1f}" r="5.5" fill="#fff" stroke="{PEM}" stroke-width="2.6"/>'
    s += f'<line x1="{px+14}" x2="{px+46}" y1="{py+16}" y2="{py+16}" stroke="{NAVY}" stroke-width="9" stroke-opacity=".14"/>'
    h += div(px + 54, py + 3, 330, None, "modelo estacionário", "p", "font-size:20px")
    s += f'<line x1="{px+14}" x2="{px+46}" y1="{py+48}" y2="{py+48}" stroke="{PEM}" stroke-width="3"/><circle cx="{px+30}" cy="{py+48}" r="5.5" fill="#fff" stroke="{PEM}" stroke-width="2.6"/>'
    h += div(px + 54, py + 35, 330, None, "PWL, 15 vértices", "p", "font-size:20px")
    # --- erro relativo nos pontos de validação
    qx, pw2 = x + 650, 410
    Y2 = lambda e: py + ph - ph * e / 0.10
    s, X2 = eixos(s, qx, py, pw2, ph, lambda e: f"{e:.2f}".replace(".", ","), (0, 0.05, 0.10), Y2)
    s += f'<text x="{qx-82}" y="{py+ph/2}" transform="rotate(-90 {qx-82} {py+ph/2})" text-anchor="middle" font-family="Manrope" font-weight="700" font-size="20" fill="#7B8794">Erro relativo [%]</text>'
    pts = sorted(CURVA["validacao"])
    linha = " ".join(f"{X2(p):.1f},{Y2((pwl(p) - q) / q * 100):.1f}" for p, q in pts)
    s += f'<polygon points="{X2(pts[0][0]):.1f},{Y2(0):.1f} {linha} {X2(pts[-1][0]):.1f},{Y2(0):.1f}" fill="{PEM}" fill-opacity=".18"/>'
    s += f'<polyline points="{linha}" fill="none" stroke="{PEM}" stroke-width="2.4" stroke-linejoin="round"/>'
    emax = max((pwl(p) - q) / q * 100 for p, q in pts)
    s += f'<line x1="{qx}" x2="{qx+pw2}" y1="{Y2(emax)}" y2="{Y2(emax)}" stroke="{NAVY}" stroke-width="1.6" stroke-dasharray="6 5"/>'
    h += div(qx + pw2 - 260, Y2(emax) - 30, 260, None, f"máx. {emax:.3f}&nbsp;%".replace(".", ","), "", f"font:700 20px Manrope;color:{NAVY};text-align:right")
    # números da verificação
    nums = [("0,087&nbsp;%", "erro máximo · limite 0,5&nbsp;%"), ("0", "pontos com consumo subestimado"), ("402", "pontos de validação independentes")]
    cw = (w - 60) / 3
    for k, (n, t) in enumerate(nums):
        xx = x + 30 + k * cw
        h += div(xx, y + hc - 96, cw - 16, None, f'<div style="font:700 32px Gelasio,serif;color:{TEAL}">{n}</div>'
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
    for f in (lambda: composicoes(110, 166, 560, 524), lambda: curva(690, 166, 1120, 524), lambda: kpis(712, 196)):
        a, b = f(); s += a; h += b
    body = (f'<div class="tt">{TIT}</div><svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(34))
    open(os.path.join(D, "S34_expansibilidade.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


if __name__ == "__main__":
    slide()
