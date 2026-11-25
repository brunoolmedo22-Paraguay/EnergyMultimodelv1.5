"""Slide 5 — v4: refinamento da D3 (escolhida).
EMS como tabela (glifo · referência · limitação); SEEDS = logo + vínculo abstrato (gerenciamento ⇄ composição);
simuladores com o conteúdo centrado em duas colunas; lacuna com mais respiro vertical."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import NAVY, SLATE, TEAL, LIGHT, LINE, SOLAR, BAT, REDE, PEM, WIND, G1, G2, G3, EMS, SIM, MUTED, T, ic, nome
from gerar_slide5_v3 import salvar, glifo, forte, falta, EMS_ITENS, LACUNA, DEFS3  # noqa: F401

GN = '<tspan font-family="Gelasio" font-weight="700" fill="#14213D">{}</tspan>'


def cartao_ems(x, y, w, h):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="28" fill="{LIGHT}"/>'
    s += T(x + 40, y + 60, "EMS MILP–MPC", 30, 700, NAVY, "Gelasio")
    s += forte(x + 40, y + 102, "check", EMS, "decisões discretas e coordenação de horizontes")
    s += T(x + 40, y + 148, "E a energia guardada no fim da janela?", 20, 400, SLATE, "Gelasio", it=True)
    c1, c2, c3 = x + 40, x + 170, x + 360          # glifo · referência · limitação
    y1, dy = y + 168, 50
    for i, (a, r, tp, l1, l2) in enumerate(EMS_ITENS):
        top = y1 + i * dy
        s += f'<line x1="{x+40}" x2="{x+w-40}" y1="{top}" y2="{top}" stroke="{LINE}" stroke-width="1.5"/>'
        s += glifo(tp, c1 + 6, top + 9, 1.45)
        s += nome(c2, top + 33, a, r, 21) + T(c3, top + 32, f"{l1} {l2}", 18, 600, SLATE)
    s += f'<line x1="{x+40}" x2="{x+w-40}" y1="{y1+5*dy}" y2="{y1+5*dy}" stroke="{LINE}" stroke-width="1.5"/>'
    s += falta(x + 40, y + h - 28, "lock", "composição fixa: uma microrrede por estudo")
    return s


def cartao_sim(x, y, w, h):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="28" fill="{LIGHT}"/>'
    s += T(x + 40, y + 60, "Ambientes e simuladores", 30, 700, NAVY, "Gelasio")
    s += forte(x + 40, y + 102, "swap", SIM, "trocam a composição da microrrede")
    # barramento com recursos que entram e saem — centrado
    passo, r = 74, 25
    bw = passo * 4 + 64
    bx, by = x + (w - bw) / 2, y + 150
    s += f'<rect x="{bx}" y="{by-5}" width="{bw}" height="10" rx="5" fill="url(#gb)"/>'
    for i, (k, c, tr) in enumerate([("sun", SOLAR, 0), ("wind", WIND, 1), ("h2", PEM, 1), ("bat", BAT, 0), ("grid", REDE, 0)]):
        cx = bx + 32 + i * passo
        dash = ' stroke-dasharray="5 5"' if tr else ""
        s += f'<line x1="{cx}" x2="{cx}" y1="{by+5}" y2="{by+24}" stroke="{c}" stroke-width="3"{dash}/>'
        s += f'<circle cx="{cx}" cy="{by+24+r}" r="{r}" fill="#fff" stroke="{c}" stroke-width="3"{dash}/>' + ic(k, cx - 14.5, by + 24 + r - 14.5, 29, c)
    # duas colunas
    yg = y + 262
    s += f'<line x1="{x+40}" x2="{x+w-40}" y1="{yg-30}" y2="{yg-30}" stroke="{LINE}" stroke-width="1.5"/>'
    s += f'<line x1="{x+w/2}" x2="{x+w/2}" y1="{yg-6}" y2="{yg+124}" stroke="{LINE}" stroke-width="1.5"/>'
    for j, (k, rot, linhas) in enumerate([("rule", "estratégias predefinidas", [("HOMER", "[31]"), ("pymgrid", "[27]")]),
                                          ("cal", "foco no planejamento", [("PyPSA · oemof", ""), ("Calliope", ""), ("ETHOS.FINE", "")])]):
        cx = x + w / 4 + j * w / 2
        s += ic(k, cx - 112, yg - 4, 26, SIM) + T(cx - 78, yg + 16, rot, 16, 600, SLATE)
        for i, (n_, rf) in enumerate(linhas):
            s += nome(cx - 78, yg + 56 + i * 32, n_, rf, 21)
    s += f'<line x1="{x+40}" x2="{x+w-40}" y1="{y1_sim(y)}" y2="{y1_sim(y)}" stroke="{LINE}" stroke-width="1.5"/>'
    s += falta(x + 40, y + h - 28, "rule", "estratégia predefinida ou foco no planejamento")
    return s


def y1_sim(y):
    return y + 168 + 5 * 50          # mesma linha de fechamento da tabela EMS


def cartao_seeds(x, y, w, h, xe, xs):
    """Logo + vínculo abstrato: o gerenciamento (azul) e a composição (verde) entram e se unem no SEEDS."""
    cx = x + w / 2
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="28" fill="#fff" stroke="url(#gb)" stroke-width="5" filter="url(#sh)"/>'
    s += f'<image href="../capa/assets/seeds.png" x="{cx-150}" y="{y+38}" width="300" height="93"/>'
    ym, yn = y + 236, y + 318             # entrada das faixas · nó de união
    s += (f'<linearGradient id="fe" gradientUnits="userSpaceOnUse" x1="{xe}" y1="0" x2="{cx}" y2="0"><stop offset="0" stop-color="{EMS}"/><stop offset="1" stop-color="{G2}"/></linearGradient>'
          f'<linearGradient id="fs" gradientUnits="userSpaceOnUse" x1="{xs}" y1="0" x2="{cx}" y2="0"><stop offset="0" stop-color="{SIM}"/><stop offset="1" stop-color="{G2}"/></linearGradient>')
    for g, x0 in (("fe", xe), ("fs", xs)):
        d = f"M{x0} {ym} C{(x0+cx)/2} {ym}, {cx} {ym+20}, {cx} {yn}"
        s += f'<path d="{d}" fill="none" stroke="url(#{g})" stroke-width="22" stroke-linecap="round" opacity=".14"/>'
        s += f'<path d="{d}" fill="none" stroke="url(#{g})" stroke-width="8" stroke-linecap="round"/>'
    for x0, c in ((xe, EMS), (xs, SIM)):
        s += f'<circle cx="{x0}" cy="{ym}" r="9" fill="#fff" stroke="{c}" stroke-width="4"/>'
    s += T(x + 44, ym - 22, "gerenciamento", 19, 700, EMS, "Gelasio", it=True)
    s += T(x + w - 44, ym - 22, "composição", 19, 700, SIM, "Gelasio", anchor="end", it=True)
    s += f'<circle cx="{cx}" cy="{yn}" r="40" fill="{G2}" opacity=".3" filter="url(#halo)"/>'
    s += f'<circle cx="{cx}" cy="{yn}" r="26" fill="url(#gb)" stroke="#fff" stroke-width="5"/>'
    s += ic("check", cx - 13, yn - 13, 26, "#fff")
    s += T(cx, yn + 78, "integrados em uma", 22, 700, NAVY, "Gelasio", anchor="middle")
    s += T(cx, yn + 106, "mesma plataforma", 22, 700, NAVY, "Gelasio", anchor="middle")
    return s


def lacuna(y):
    s = T(960, y, "A lacuna: não se identificou uma abordagem que reunisse", 28, 700, NAVY, "Gelasio", anchor="middle")
    larg = 566
    for i, (k, c, l1, l2) in enumerate(LACUNA):
        x = 110 + i * larg
        yy = y + 96
        s += f'<circle cx="{x+32}" cy="{yy}" r="32" fill="{c}"/>' + ic(k, x + 13, yy - 19, 38, "#fff")
        s += T(x + 82, yy - 6, l1, 22, 700, NAVY, "Gelasio") + T(x + 82, yy + 25, l2, 22, 700, NAVY, "Gelasio")
    return s


def e1():
    y0, h = 168, 484
    s = cartao_ems(110, y0, 610, h)
    s += cartao_sim(1200, y0, 610, h)
    s += cartao_seeds(750, y0 - 6, 420, h + 12, 720, 1200)
    s += f'<line x1="960" x2="960" y1="{y0+h+10}" y2="{y0+h+52}" stroke="{TEAL}" stroke-width="2.5" stroke-dasharray="6 6"/>'
    s += lacuna(y0 + h + 96)
    salvar("S5v4_E1", s)


if __name__ == "__main__":
    e1()
