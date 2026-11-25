"""Slide 12 (deck) — Programação linear inteira mista (MILP): três propostas.
Conteúdo da Seção 4.1 do artigo (eq. 9–13). Variáveis CONTÍNUAS em teal, BINÁRIAS em ferrugem, nas equações e nos desenhos.
M1 duas naturezas (eq. 9 em destaque + três «interruptores» no barramento) · M2 do geral ao barramento (eq. 9 → 11 → 12–13)
M3 barramento central com as variáveis de decisão de cada recurso."""
import json
import os
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import CSS, NAVY, SLATE, TEAL, LIGHT, SOLAR, BAT, REDE, PEM, WIND, MUTED, T
from gerar_slide5_v3 import DEFS3
from gerar_slide8 import NM, ic, no_e_haste, barra, rodape

D = os.path.dirname(os.path.abspath(__file__))
CT, BN = "#1F7A6D", "#C0532F"                      # contínua · binária
c = lambda x: r"{\color{%s}{%s}}" % (CT, x)
b = lambda x: r"{\color{%s}{%s}}" % (BN, x)

TEX = {
    "e9": r"\begin{aligned}\min_{%s,\,%s}\;\; & c^{\mathsf T}%s+g^{\mathsf T}%s\\ \text{sujeito a}\;\; & A%s+B%s\le b,\quad %s\in\mathbb{R}^n,\quad %s\in\{0,1\}^p\end{aligned}"
          % (c("v"), b("w"), c("v"), b("w"), c("v"), b("w"), c("v"), b("w")),
    "e9c": r"\min_{%s,\,%s}\; c^{\mathsf T}%s+g^{\mathsf T}%s\quad\text{s.a.}\; A%s+B%s\le b" % (c("v"), b("w"), c("v"), b("w"), c("v"), b("w")),
    "e11": r"%s+%s-%s+%s+%s=P_{L,t}+%s" % (c(r"P_{\mathrm{ren},t}"), c(r"P_{d,t}"), c(r"P_{c,t}"), c(r"P_{g,t}"), c(r"P_{\mathrm{imp},t}"), c(r"P_{\mathrm{exp},t}")),
    "e12": r"0\le %s\le \bar P_c\,%s,\qquad 0\le %s\le \bar P_d\,(1-%s)" % (c(r"P_{c,t}"), b(r"\omega_t"), c(r"P_{d,t}"), b(r"\omega_t")),
    "e13": r"\begin{aligned}P_{\min}\,%s\le %s\le P_{\max}\,%s\\ %s-%s=%s-%s,\quad %s+%s\le 1\end{aligned}"
           % (b("u_t"), c(r"P_{g,t}"), b("u_t"), b("u_t"), b("u_{t-1}"), b("y_t"), b("z_t"), b("y_t"), b("z_t")),
    "e13a": r"P_{\min}\,%s\le %s\le P_{\max}\,%s" % (b("u_t"), c(r"P_{g,t}"), b("u_t")),
    "e13b": r"%s-%s=%s-%s" % (b("u_t"), b("u_{t-1}"), b("y_t"), b("z_t")),
    "imp": r"0\le %s\le \bar P_{\mathrm{imp}}\,%s,\quad 0\le %s\le \bar P_{\mathrm{exp}}(1-%s)" % (c(r"P_{\mathrm{imp},t}"), b(r"w_t"), c(r"P_{\mathrm{exp},t}"), b(r"w_t")),
    "i_ren": c(r"P_{\mathrm{ren}}"), "i_bat": c(r"P_c,\,P_d") + r"\;\;" + b(r"\omega"), "i_pem": c(r"P_g") + r"\;\;" + b(r"u,\,y,\,z"),
    "i_pcc": c(r"P_{\mathrm{imp}},\,P_{\mathrm{exp}}") + r"\;\;" + b("w"), "i_dem": r"P_L", "i_v": c("v"), "i_w": b("w"),
}
SVG = json.loads(subprocess.run(["node", os.path.join(D, "tex2svg.js")], input=json.dumps(TEX), capture_output=True,
                                text=True, env=dict(os.environ, NODE_PATH=NM), check=True).stdout)
CSSM = CSS + """
.d{position:absolute}
.eq{display:flex;align-items:center;justify-content:center;color:#14213D}
.eq.l{justify-content:flex-start}
.eq svg{overflow:visible}
.h{font:700 28px/1.2 "Gelasio",Georgia,serif;color:#14213D}
.p{font:500 19px/1.45 "Manrope";color:#4A5568}
.tg{font:600 14px "Manrope";color:#9AA5B1}
"""
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
TIT = '<div class="tt">Programação linear inteira mista (MILP)</div>'
REF = "Seção 4.1 do artigo (eq. 9–13) · formulação aplicada por Parisio, Rikos e Glielmo [17]"


def div(x, y, w, h, inner, cls="", st=""):
    hh = f"height:{h}px;" if h else ""
    return f'<div class="d {cls}" style="left:{x}px;top:{y}px;width:{w}px;{hh}{st}">{inner}</div>'


def eq(k, x, y, w, h, px, cls="eq", tag=""):
    t = f'<span class="tg" style="position:absolute;right:0;top:-4px">{tag}</span>' if tag else ""
    return div(x, y, w, h, SVG[k] + t, cls, f"font-size:{px}px")


def legenda(x, y):
    """Contínuas × binárias (chave de cores do slide)."""
    o = f'<rect x="{x}" y="{y}" width="26" height="26" rx="7" fill="{CT}"/>' + T(x + 40, y + 20, "contínuas — quanto", 20, 700, NAVY)
    o += f'<rect x="{x+290}" y="{y}" width="26" height="26" rx="7" fill="{BN}"/>' + T(x + 330, y + 20, "binárias — sim ou não", 20, 700, NAVY)
    return o


def chave(cx, cy, cor, ligado, rot, sub):
    """Interruptor (pílula com bolinha) e rótulo."""
    w, h = 74, 38
    x0 = cx - w / 2
    o = f'<rect x="{x0}" y="{cy-h/2}" width="{w}" height="{h}" rx="{h/2}" fill="{BN if ligado else "#fff"}" stroke="{BN}" stroke-width="3"/>'
    bx = x0 + w - h / 2 if ligado else x0 + h / 2
    o += f'<circle cx="{bx}" cy="{cy}" r="{h/2-6}" fill="{"#fff" if ligado else BN}"/>'
    o += T(cx, cy + 50, rot, 22, 700, NAVY, "Gelasio", anchor="middle") + T(cx, cy + 76, sub, 16, 600, SLATE, anchor="middle")
    return o


def salvar(nome, s, html, n=12):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS3}{s}</svg>'
            + html + f'<div class="ref">{REF}</div>' + rodape(n))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


# ===================================================================== M1 · duas naturezas
def m1():
    s = f'<rect x="110" y="172" width="1700" height="250" rx="28" fill="{LIGHT}"/>'
    html = eq("e9", 150, 190, 1200, 210, 40, tag="")
    s += T(1770, 214, "eq. 9", 15, 600, MUTED, anchor="end")
    s += legenda(1400, 268) if False else ""
    s += f'<rect x="1420" y="236" width="26" height="26" rx="7" fill="{CT}"/>' + T(1460, 256, "v  contínuas", 22, 700, NAVY)
    s += T(1460, 284, "potências e energia — quanto", 17, 600, SLATE)
    s += f'<rect x="1420" y="320" width="26" height="26" rx="7" fill="{BN}"/>' + T(1460, 340, "w  binárias", 22, 700, NAVY)
    s += T(1460, 368, "estados e modos — sim ou não", 17, 600, SLATE)
    # barramento com três interruptores
    s += T(110, 486, "Três decisões do tipo «sim ou não» numa microrrede", 28, 700, NAVY, "Gelasio")
    yb = 560
    s += barra(110, 1810, yb)
    for cx, k, cor, rot, sub, lig, sent in ((395, "bat", BAT, "ω  bateria", "carrega ou descarrega", True, "bi"),
                                             (960, "h2", PEM, "u  célula a combustível", "ligada ou desligada · partida y, parada z", True, "in"),
                                             (1525, "grid", REDE, "w  rede", "importa ou exporta", False, "bi")):
        s += no_e_haste(cx, yb, 650, k, cor, sent, r=38)
        s += chave(cx, 742, cor, lig, rot, sub)
    s += f'<line x1="110" x2="1810" y1="862" y2="862" stroke="#DCE3E2" stroke-width="1.5"/>'
    html += div(110, 874, 1700, None, "O tempo de solução pode crescer de forma exponencial com o número de variáveis inteiras, o horizonte e a quantidade de equipamentos.",
                "p", "font-size:18px;color:#7B8794")
    salvar("S12_M1_naturezas", s, html)


# ===================================================================== M2 · do geral ao barramento
def m2():
    s, html = "", ""
    linhas = [("Forma geral", "contínuas e binárias com restrições lineares", "e9c", "eq. 9", 34),
              ("Balanço no barramento", "o que entra é igual ao que sai, a cada intervalo", "e11", "eq. 11", 34),
              ("Bateria", "não carrega e descarrega ao mesmo tempo", "e12", "eq. 12", 32),
              ("Unidade despachável", "potência só com a unidade ligada; partidas e paradas", "e13", "eq. 13", 30)]
    y0, h, gap = 170, 172, 14
    for i, (t, sub, k, tag, px) in enumerate(linhas):
        y = y0 + i * (h + gap)
        s += f'<rect x="110" y="{y}" width="1700" height="{h}" rx="24" fill="{LIGHT}"/>'
        s += f'<circle cx="160" cy="{y+h/2}" r="26" fill="{NAVY}"/>' + T(160, y + h / 2 + 9, str(i + 1), 24, 700, "#fff", "Gelasio", anchor="middle")
        s += T(210, y + h / 2 - 6, t, 28, 700, NAVY, "Gelasio") + T(210, y + h / 2 + 26, sub, 17, 600, SLATE)
        html += eq(k, 760, y + 10, 1000, h - 20, px)
        s += T(1790, y + 28, tag, 15, 600, MUTED, anchor="end")
    s += f'<rect x="1500" y="96" width="22" height="22" rx="6" fill="{CT}"/>' + T(1532, 114, "contínua", 18, 700, NAVY)
    s += f'<rect x="1660" y="96" width="22" height="22" rx="6" fill="{BN}"/>' + T(1692, 114, "binária", 18, 700, NAVY)
    salvar("S12_M2_etapas", s, html)


# ===================================================================== M3 · barramento central com as variáveis de cada recurso
def m3():
    s = ""
    html = eq("e11", 110, 178, 1700, 90, 40)
    s += T(1810, 196, "eq. 11 · balanço no barramento", 15, 600, MUTED, anchor="end")
    yb = 330
    s += barra(110, 1810, yb, 14)
    rec = [("sun", SOLAR, "Renováveis", "i_ren", "aproveitada ≤ disponível", "in"),
           ("bat", BAT, "Bateria", "i_bat", "carga ou descarga", "bi"),
           ("h2", PEM, "Célula a combustível", "i_pem", "estado, partida e parada", "in"),
           ("grid", REDE, "Rede (PCC)", "i_pcc", "importa ou exporta", "bi"),
           ("load", NAVY, "Demanda", "i_dem", "dado da previsão", "out")]
    w, gap = 322, 22
    for i, (k, cor, nome, tx, sub, sent) in enumerate(rec):
        x = 110 + i * (w + gap)
        cx = x + w / 2
        s += f'<rect x="{x}" y="430" width="{w}" height="230" rx="24" fill="{LIGHT}"/>'
        s += no_e_haste(cx, yb, 430, k, cor, sent, r=40)
        s += T(cx, 512, nome, 24, 700, NAVY, "Gelasio", anchor="middle")
        html += eq(tx, x + 10, 530, w - 20, 70, 28)
        s += T(cx, 632, sub, 16, 600, SLATE, anchor="middle")
    # restrições com binárias
    s += f'<rect x="110" y="700" width="1700" height="200" rx="24" fill="#fff" stroke="#DCE3E2" stroke-width="2"/>'
    s += T(150, 748, "As binárias ligam as restrições", 26, 700, NAVY, "Gelasio")
    html += eq("e12", 150, 770, 760, 60, 26, "eq l") + eq("e13a", 990, 770, 780, 60, 26, "eq l")
    html += eq("imp", 150, 830, 760, 60, 26, "eq l") + eq("e13b", 990, 830, 780, 60, 26, "eq l")
    s += T(1770, 748, "eq. 12–13", 15, 600, MUTED, anchor="end")
    s += f'<rect x="1150" y="728" width="22" height="22" rx="6" fill="{CT}"/>' + T(1182, 746, "contínua", 18, 700, NAVY)
    s += f'<rect x="1310" y="728" width="22" height="22" rx="6" fill="{BN}"/>' + T(1342, 746, "binária", 18, 700, NAVY)
    salvar("S12_M3_barramento", s, html)


if __name__ == "__main__":
    m1()
    m2()
    m3()
