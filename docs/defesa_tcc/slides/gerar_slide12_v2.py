"""Slide 12 dividido em dois (pedido do responsável):
A · «Por que MILP» — forma geral (eq. 9) + três argumentos: decisões discretas (conjunto {0} ∪ [P_mín, P_máx] da PEMFC),
    ótimo comprovado e rápido nas janelas (Tabela 6.2; Seção 7.4) e prática do setor (DESSEM/ONS é MILP [10]; microrredes [17]).
B · «MILP na microrrede» — balanço (eq. 11) no barramento; Solar, Eólica, Bateria, PEMFC, Rede e Demanda com as suas variáveis;
    custo minimizado (eq. 10) e restrições com binárias (eq. 12–13).
Números do artigo: PEMFC 10–50 kW (Tab. 6.3); solução ótima sem tolerância de gap (Tab. 6.2); 168 janelas ótimas, até 0,42 s por janela (7.4).
DESSEM como MILP: Santos et al. [10] (PSCC 2020 / EPSR 189) e documentação do CEPEL."""
import json
import os
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import CSS, NAVY, SLATE, TEAL, LIGHT, SOLAR, BAT, REDE, PEM, WIND, MUTED, T
from gerar_slide5_v3 import DEFS3
from gerar_slide8 import NM, ic, no_e_haste, barra, rodape

D = os.path.dirname(os.path.abspath(__file__))
CT, BN = "#1F7A6D", "#C0532F"
c = lambda x: r"{\color{%s}{%s}}" % (CT, x)
b = lambda x: r"{\color{%s}{%s}}" % (BN, x)
TEX = {
    "e9": r"\begin{aligned}\min_{%s,\,%s}\;\; & c^{\mathsf T}%s+g^{\mathsf T}%s\\ \text{sujeito a}\;\; & A%s+B%s\le b,\quad %s\in\mathbb{R}^n,\quad %s\in\{0,1\}^p\end{aligned}"
          % (c("v"), b("w"), c("v"), b("w"), c("v"), b("w"), c("v"), b("w")),
    "set": r"%s\in\{0\}\;\cup\;[P_{\min},\,P_{\max}]\;\Longleftrightarrow\;P_{\min}\,%s\le %s\le P_{\max}\,%s" % (c("P_g"), b("u"), c("P_g"), b("u")),
    "e11": r"%s+%s-%s+%s+%s=P_{L,t}+%s" % (c(r"P_{\mathrm{ren},t}"), c(r"P_{d,t}"), c(r"P_{c,t}"), c(r"P_{g,t}"), c(r"P_{\mathrm{imp},t}"), c(r"P_{\mathrm{exp},t}")),
    "ren": r"0\le %s\le P_{\mathrm{FV},t}+P_{\mathrm{EOL},t}" % c(r"P_{\mathrm{ren},t}"),
    "e10": r"\begin{aligned}J=\sum_{t}\Big[\Delta t\,\big(c_{\mathrm{imp}}%s-c_{\mathrm{exp}}%s+c_{\mathrm{H_2}}\,%s\big)\\+\,C_{\mathrm{SU}}\,%s+C_{\mathrm{SD}}\,%s\Big]\end{aligned}"
           % (c(r"P_{\mathrm{imp},t}"), c(r"P_{\mathrm{exp},t}"), c(r"\dot m_{\mathrm{H_2},t}"), b("y_t"), b("z_t")),
    "e12": r"0\le %s\le \bar P_c\,%s,\quad 0\le %s\le \bar P_d\,(1-%s)" % (c(r"P_{c,t}"), b(r"\omega_t"), c(r"P_{d,t}"), b(r"\omega_t")),
    "e13a": r"P_{\min}\,%s\le %s\le P_{\max}\,%s" % (b("u_t"), c(r"P_{g,t}"), b("u_t")),
    "e13b": r"%s-%s=%s-%s,\quad %s+%s\le 1" % (b("u_t"), b("u_{t-1}"), b("y_t"), b("z_t"), b("y_t"), b("z_t")),
    "i_fv": r"P_{\mathrm{FV}}", "i_eol": r"P_{\mathrm{EOL}}", "i_bat": c(r"P_c,\,P_d") + r"\;\;" + b(r"\omega"),
    "i_pem": c(r"P_g") + r"\;\;" + b(r"u,\,y,\,z"), "i_pcc": c(r"P_{\mathrm{imp}},P_{\mathrm{exp}}") + r"\;" + b("w"), "i_dem": r"P_L",
}
SVG = json.loads(subprocess.run(["node", os.path.join(D, "tex2svg.js")], input=json.dumps(TEX), capture_output=True,
                                text=True, env=dict(os.environ, NODE_PATH=NM), check=True).stdout)
CSSM = CSS + """
.d{position:absolute}
.eq{display:flex;align-items:center;justify-content:center;color:#14213D}
.eq.l{justify-content:flex-start}
.eq svg{overflow:visible}
.h{font:700 27px/1.2 "Gelasio",Georgia,serif;color:#14213D}
.p{font:500 18px/1.45 "Manrope";color:#4A5568}
.p b{font-weight:800;color:#14213D}
"""
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'


def div(x, y, w, h, inner, cls="", st=""):
    hh = f"height:{h}px;" if h else ""
    return f'<div class="d {cls}" style="left:{x}px;top:{y}px;width:{w}px;{hh}{st}">{inner}</div>'


def eq(k, x, y, w, h, px, cls="eq"):
    return div(x, y, w, h, SVG[k], cls, f"font-size:{px}px")


def salvar(nome, tit, s, html, ref, n):
    body = (f'<div class="tt">{tit}</div><svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS3}{s}</svg>'
            + html + f'<div class="ref">{ref}</div>' + rodape(n))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


def legenda(x, y):
    return (f'<rect x="{x}" y="{y}" width="24" height="24" rx="7" fill="{CT}"/>' + T(x + 36, y + 19, "contínuas — quanto", 19, 700, NAVY)
            + f'<rect x="{x}" y="{y+42}" width="24" height="24" rx="7" fill="{BN}"/>' + T(x + 36, y + 61, "binárias — sim ou não", 19, 700, NAVY))


# ===================================================================== A · por que MILP
def slide_a():
    s = f'<rect x="110" y="168" width="1700" height="236" rx="28" fill="{LIGHT}"/>'
    html = eq("e9", 140, 180, 1220, 212, 38)
    s += legenda(1440, 246) + T(1770, 204, "eq. 9", 15, 600, MUTED, anchor="end")
    s += T(110, 472, "Por que MILP?", 34, 700, NAVY, "Gelasio")
    y0, h, w, gap = 500, 400, 552, 22
    xs = [110 + i * (w + gap) for i in range(3)]
    # 1 · decisões discretas: o conjunto viável da PEMFC
    x = xs[0]
    s += f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" rx="24" fill="{LIGHT}"/>'
    s += f'<circle cx="{x+46}" cy="{y0+52}" r="22" fill="{NAVY}"/>' + T(x + 46, y0 + 60, "1", 22, 700, "#fff", "Gelasio", anchor="middle")
    s += T(x + 84, y0 + 46, "Decisões discretas", 26, 700, NAVY, "Gelasio") + T(x + 84, y0 + 74, "a célula: desligada ou entre 10 e 50 kW", 16, 600, SLATE)
    lx0, lx1, ly = x + 50, x + w - 50, y0 + 186
    px = lambda p: lx0 + (lx1 - lx0) * p / 55
    s += f'<line x1="{lx0}" x2="{lx1}" y1="{ly}" y2="{ly}" stroke="#C9D3DD" stroke-width="3"/>'
    s += f'<line x1="{px(10)}" x2="{px(50)}" y1="{ly}" y2="{ly}" stroke="{CT}" stroke-width="12" stroke-linecap="round"/>'
    s += f'<circle cx="{px(0)}" cy="{ly}" r="11" fill="{BN}"/>'
    for p in (0, 10, 50):
        s += T(px(p), ly + 42, f"{p}", 19, 700, NAVY, anchor="middle")
    s += T(lx1 + 4, ly + 42, "kW", 16, 600, MUTED)
    s += T(px(0), ly - 26, "desligada", 15, 700, BN, anchor="middle") + T(px(30), ly - 26, "em operação", 15, 700, CT, anchor="middle")
    s += T(px(5), ly + 4, "", 10)
    s += f'<path d="M{px(1.6)} {ly} H{px(8.4)}" stroke="#fff" stroke-width="0"/>'
    html += eq("set", x + 20, y0 + 256, w - 40, 60, 19)
    html += div(x + 36, y0 + 326, w - 72, None, "Um conjunto com um buraco não é convexo: a programação linear não o representa; uma binária <b>u</b> sim.", "p", "font-size:16.5px")
    # 2 · ótimo comprovado e rápido
    x = xs[1]
    s += f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" rx="24" fill="{LIGHT}"/>'
    s += f'<circle cx="{x+46}" cy="{y0+52}" r="22" fill="{NAVY}"/>' + T(x + 46, y0 + 60, "2", 22, 700, "#fff", "Gelasio", anchor="middle")
    s += T(x + 84, y0 + 46, "Ótimo comprovado", 26, 700, NAVY, "Gelasio") + T(x + 84, y0 + 74, "o solver prova a otimalidade de cada janela", 16, 600, SLATE)
    for i, (num, rot) in enumerate((("168", "de 168 janelas resolvidas até a otimalidade na bancada de expansibilidade"), ("≤ 0,42 s", "por janela do MPC nos estudos C1 a C5, sem tolerância de gap"))):
        yy = y0 + 160 + i * 116
        s += T(x + 40, yy, num, 58, 700, TEAL, "Gelasio")
        html += div(x + 40, yy + 10, w - 80, None, rot, "p", "font-size:17px")
    # 3 · prática do setor
    x = xs[2]
    s += f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" rx="24" fill="{LIGHT}"/>'
    s += f'<circle cx="{x+46}" cy="{y0+52}" r="22" fill="{NAVY}"/>' + T(x + 46, y0 + 60, "3", 22, 700, "#fff", "Gelasio", anchor="middle")
    s += T(x + 84, y0 + 46, "Prática do setor", 26, 700, NAVY, "Gelasio") + T(x + 84, y0 + 74, "a mesma ferramenta, em outra escala", 16, 600, SLATE)
    cx0, cy, ch = x + 40, y0 + 130, 44
    for i, (t, cor, wd) in enumerate((("NEWAVE", "#0E4F86", 156), ("DECOMP", "#2C6FB0", 150), ("DESSEM", "#2F7CC0", 150))):
        pts = f"{cx0},{cy} {cx0+wd-16},{cy} {cx0+wd},{cy+ch/2} {cx0+wd-16},{cy+ch} {cx0},{cy+ch}" + ("" if i == 0 else f" {cx0+16},{cy+ch/2}")
        s += f'<polygon points="{pts}" fill="{cor}" opacity="{1 if i == 2 else .35}"/>' + T(cx0 + (28 if i else 16), cy + 29, t, 17, 800, "#fff")
        cx0 += wd + 5
    s += f'<rect x="{x+378}" y="{cy+58}" width="84" height="32" rx="16" fill="#fff" stroke="{BN}" stroke-width="2.5"/>' + T(x + 420, cy + 80, "MILP", 16, 800, BN, anchor="middle")
    html += div(x + 40, cy + 104, w - 80, None, "No SIN, a programação diária da operação (DESSEM, usada pelo ONS) é formulada como MILP [10].", "p", "font-size:17px")
    html += div(x + 40, cy + 196, w - 80, None, "Em microrredes, o mesmo tipo de formulação é aplicado ao despacho com restrições operacionais [17].", "p", "font-size:17px")
    s += f'<line x1="{x+40}" x2="{x+w-40}" y1="{cy+186}" y2="{cy+186}" stroke="#DCE3E2" stroke-width="1.5"/>'
    salvar("S12v2_A_porque", "Programação linear inteira mista (MILP)", s, html,
           "eq. 9 do artigo · [10] Santos et al. (DESSEM) · [17] Parisio, Rikos e Glielmo · números: Tabelas 6.2–6.3 e Seção 7.4 do artigo", 12)


# ===================================================================== B · o MILP da microrrede
def slide_b():
    s = ""
    html = eq("e11", 110, 156, 1700, 76, 36) + eq("ren", 110, 228, 1700, 44, 24)
    s += T(1810, 178, "eq. 11 · balanço no barramento", 15, 600, MUTED, anchor="end")
    yb = 306
    s += barra(110, 1810, yb, 14)
    rec = [("sun", SOLAR, "Solar", "i_fv", "potência disponível (dado)", "in"),
           ("wind", WIND, "Eólica", "i_eol", "potência disponível (dado)", "in"),
           ("bat", BAT, "Bateria", "i_bat", "carga ou descarga", "bi"),
           ("h2", PEM, "Célula a combustível", "i_pem", "estado, partida e parada", "in"),
           ("grid", REDE, "Rede (PCC)", "i_pcc", "importa ou exporta", "bi"),
           ("load", NAVY, "Demanda", "i_dem", "dado da previsão", "out")]
    w, gap = 268, 18.4
    for i, (k, cor, nome, tx, sub, sent) in enumerate(rec):
        x = 110 + i * (w + gap)
        cx = x + w / 2
        s += f'<rect x="{x}" y="396" width="{w}" height="214" rx="22" fill="{LIGHT}"/>'
        s += no_e_haste(cx, yb, 396, k, cor, sent, r=36)
        s += T(cx, 470, nome, 22, 700, NAVY, "Gelasio", anchor="middle")
        html += eq(tx, x + 8, 488, w - 16, 66, 25)
        s += T(cx, 584, sub, 15, 600, SLATE, anchor="middle")
    # custo minimizado e restrições com binárias
    s += f'<rect x="110" y="640" width="760" height="262" rx="24" fill="#fff" stroke="#DCE3E2" stroke-width="2"/>'
    s += T(146, 686, "O que se minimiza", 25, 700, NAVY, "Gelasio") + T(834, 686, "eq. 10", 15, 600, MUTED, anchor="end")
    html += eq("e10", 130, 704, 720, 180, 25)
    s += f'<rect x="894" y="640" width="916" height="262" rx="24" fill="#fff" stroke="#DCE3E2" stroke-width="2"/>'
    s += T(930, 686, "As binárias ligam as restrições", 25, 700, NAVY, "Gelasio") + T(1774, 686, "eq. 12–13", 15, 600, MUTED, anchor="end")
    html += eq("e12", 930, 708, 860, 56, 24, "eq l") + eq("e13a", 930, 770, 860, 56, 24, "eq l") + eq("e13b", 930, 832, 860, 56, 24, "eq l")
    s += f'<rect x="1490" y="96" width="22" height="22" rx="6" fill="{CT}"/>' + T(1522, 114, "contínua", 18, 700, NAVY)
    s += f'<rect x="1650" y="96" width="22" height="22" rx="6" fill="{BN}"/>' + T(1682, 114, "binária", 18, 700, NAVY)
    salvar("S12v2_B_microrrede", "O MILP da microrrede", s, html,
           "eq. 10–13 do artigo (Seção 4.1) · P_ren: renovável aproveitada; a diferença para a disponível é vertimento · cada parcela entra só se o recurso existe no cenário", 13)


if __name__ == "__main__":
    slide_a()
    slide_b()
