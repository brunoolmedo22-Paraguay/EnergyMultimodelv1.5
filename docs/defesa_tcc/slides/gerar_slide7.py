"""Slide 7 (NOVO) — O SEEDS: a proposta que preenche a lacuna do slide 5 e apresenta as duas contribuições.
Só funcionalidades que existem no aplicativo (CLAUDE.md): gestor de várias microrredes, bancadas por equipamento,
cenários (previsões, estado inicial, tarifa), EMS hierárquico MILP–MPC (planejador + MPC), rodadas imutáveis
reabertas com verificação, estudos exportáveis, relatórios; aplicação web; simulação (ambiente de ensaio).
J1 da lacuna à plataforma · J2 o nome (Smart Energy Ecosystem for Decision Support) · J3 bancada experimental (fluxo)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import CSS, NAVY, SLATE, TEAL, LIGHT, LINE, LIME, SOLAR, BAT, REDE, PEM, WIND, G1, G2, G3, MUTED, T, ICON
from gerar_slide5_v3 import DEFS3

D = os.path.dirname(os.path.abspath(__file__))
A, B = "#2E9E6B", "#2C6FB0"
ICON = dict(ICON)
ICON.update({
    "doc": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M10 4h14l7 7v25H10z"/><path d="M24 4v7h7M15 20h11M15 26h11"/></g>',
    "gear": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><circle cx="20" cy="20" r="6"/><path d="M20 4v6M20 30v6M4 20h6M30 20h6M8.7 8.7l4.2 4.2M27.1 27.1l4.2 4.2M8.7 31.3l4.2-4.2M27.1 12.9l4.2-4.2"/></g>',
    "bus": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M5 14h30"/><path d="M11 14v8M20 14v8M29 14v8"/><circle cx="11" cy="27" r="4"/><circle cx="20" cy="27" r="4"/><circle cx="29" cy="27" r="4"/></g>',
    "brain": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M6 30l8-10 7 6 13-16"/><circle cx="34" cy="10" r="3"/><path d="M6 35h28"/></g>',
})
CSS7 = CSS + """
.d{position:absolute}
.h{font:700 44px/1.18 "Gelasio",Georgia,serif;color:#14213D}
.p{font:500 20px/1.45 "Manrope";color:#4A5568}
.t{font:700 24px/1.25 "Gelasio",Georgia,serif;color:#14213D}
"""
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
RODAPE = ('<div class="hl" style="bottom:112px"></div><div class="ft"><img src="../capa/assets/unila.png"><div class="sep"></div>'
          '<span>Engenharia de Energia · ILATIT</span><div class="sep"></div><span><b>Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>'
          '<div class="pn">7</div>')
RES = [("sun", SOLAR), ("wind", WIND), ("h2", PEM), ("bat", BAT), ("grid", REDE)]


def ic(k, x, y, s, c):
    return f'<svg x="{x}" y="{y}" width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c}">{ICON[k]}</svg>'


def div(x, y, w, inner, cls="", st=""):
    return f'<div class="d {cls}" style="left:{x}px;top:{y}px;width:{w}px;{st}">{inner}</div>'


def salvar(nome, titulo, s, html=""):
    tit = f'<div class="tt">{titulo}</div>' if titulo else ""
    body = (tit + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS3}{s}</svg>'
            + html + RODAPE)
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS7, body=body))


def mini_bus(x, y, passo=58, r=20):
    o = f'<rect x="{x}" y="{y-4}" width="{passo*4+44}" height="8" rx="4" fill="url(#gb)"/>'
    for i, (k, c) in enumerate(RES):
        cx = x + 22 + i * passo
        o += (f'<line x1="{cx}" x2="{cx}" y1="{y+4}" y2="{y+16}" stroke="{c}" stroke-width="3"/>'
              f'<circle cx="{cx}" cy="{y+16+r}" r="{r}" fill="#fff" stroke="{c}" stroke-width="3"/>' + ic(k, cx - 12, y + 4 + r, 24, c))
    return o


def chevs(x, y, itens, cor, h=40):
    o = ""
    for k, t in enumerate(itens):
        w = len(t) * 10.4 + 50
        pts = f"{x},{y} {x+w-16},{y} {x+w},{y+h/2} {x+w-16},{y+h} {x},{y+h}" + ("" if k == 0 else f" {x+16},{y+h/2}")
        o += f'<polygon points="{pts}" fill="{cor}" opacity="{0.6 + 0.2*k}"/>' + T(x + (28 if k else 18), y + 27, t, 17, 700, "#fff")
        x += w + 6
    return o


def elos(x, y, itens, cor):
    o = ""
    for k, t in enumerate(itens):
        cx = x + k * 150
        if k:
            o += f'<line x1="{cx-150+14}" x2="{cx-14}" y1="{y}" y2="{y}" stroke="{cor}" stroke-width="3"/>'
        o += f'<circle cx="{cx}" cy="{y}" r="11" fill="#fff" stroke="{cor}" stroke-width="4"/>' + T(cx, y + 36, t, 16, 700, SLATE, anchor="middle")
    return o


# ===================================================================== J1 · da lacuna à plataforma
def j1():
    s = T(110, 212, "A lacuna", 24, 700, MUTED, "Gelasio")
    lac = [("swap", G1, "composição de diferentes", "microrredes a partir de modelos"),
           ("clock", G2, "avaliação sob um mesmo", "gerenciamento hierárquico"),
           ("trace", G3, "rastreabilidade entre configurações,", "cenários e resultados")]
    resp = [("Plataforma modular", "microrredes compostas a partir dos modelos físicos dos equipamentos", A, "bus"),
            ("EMS hierárquico MILP–MPC", "um planejador de longo prazo informa ao MPC o valor futuro da energia guardada", B, "chev"),
            ("Rodadas rastreáveis", "configuração, cenário e resultado guardados juntos e reabertos com verificação", A, "elos")]
    html = ""
    for i, ((k, c, l1, l2), (t, d, cr, vis)) in enumerate(zip(lac, resp)):
        y = 262 + i * 226
        s += f'<circle cx="{142}" cy="{y+40}" r="30" fill="{c}" opacity=".9"/>' + ic(k, 124, y + 22, 36, "#fff")
        s += T(190, y + 34, l1, 19, 600, SLATE) + T(190, y + 60, l2, 19, 600, SLATE)
        s += f'<path d="M560 {y+40} H650" stroke="{TEAL}" stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#at)"/>'
        s += f'<rect x="676" y="{y-22}" width="1134" height="200" rx="24" fill="{LIGHT}"/>'
        s += T(716, y + 46, t, 30, 700, NAVY, "Gelasio")
        html += div(716, y + 64, 560, d, "p")
        if vis == "bus":
            s += mini_bus(1370, y + 50)
        elif vis == "chev":
            s += chevs(1356, y + 54, ["planejador", "valor futuro", "MPC"], B)
        else:
            s += elos(1410, y + 64, ["configuração", "cenário", "resultado"], A)
    s += f'<rect x="676" y="{250-6}" width="10" height="{176}" rx="5" fill="{A}"/>' if False else ""
    salvar("S7_J1_lacuna", "O SEEDS", s, html)


# ===================================================================== J2 · o nome
def j2():
    s = ""
    letras = [("S", "Smart", G1, "decide com um EMS hierárquico MILP–MPC que considera o valor futuro"),
              ("E", "Energy", "#47A33E", "modelos físicos de FV, eólica, bateria, PEMFC e rede"),
              ("E", "Ecosystem", G2, "várias microrredes, bancadas e cenários na mesma plataforma"),
              ("D", "Decision", "#138082", "compara composições e estratégias de operação"),
              ("S", "Support", G3, "rodadas rastreáveis, relatórios e estudos reprodutíveis")]
    html = ""
    w, gap = 322, 22
    for i, (L, pal, c, txt) in enumerate(letras):
        x = 110 + i * (w + gap)
        s += f'<rect x="{x}" y="178" width="{w}" height="446" rx="26" fill="{LIGHT}"/>'
        s += f'<rect x="{x}" y="186" width="{w}" height="10" rx="5" fill="{c}"/>' if False else ""
        s += T(x + 34, 330, L, 150, 700, c, "Gelasio")
        s += T(x + 36, 392, ("for " if pal == "Decision" else "") + pal, 30, 700, NAVY, "Gelasio", it=True)
        html += div(x + 36, 424, w - 70, txt, "p", "font-size:21px")
    # contribuições
    s += T(110, 702, "Duas contribuições", 30, 700, NAVY, "Gelasio")
    for x, c, t1, t2 in ((110, A, "Plataforma modular", "compor e avaliar microrredes diferentes"),
                         (970, B, "EMS hierárquico MILP–MPC", "decidir agora considerando o valor futuro")):
        s += f'<rect x="{x}" y="734" width="840" height="160" rx="80" fill="#fff" stroke="{c}" stroke-width="3"/>'
        s += f'<circle cx="{x+80}" cy="814" r="50" fill="{c}"/>' + ic("bus" if c == A else "brain", x + 52, 786, 56, "#fff")
        s += T(x + 152, 804, t1, 32, 700, NAVY, "Gelasio") + T(x + 152, 842, t2, 20, 600, SLATE)
    salvar("S7_J2_nome", "O SEEDS", s, html)


# ===================================================================== J3 · bancada experimental (fluxo)
def j3():
    html = div(110, 178, 1300, 'Uma bancada experimental para <span style="color:#1F7A6D">compor microrredes</span> '
               'e <span style="color:#2C6FB0">testar o seu gerenciamento</span>', "h", "font-size:46px")
    s = ""
    x0, x1, yb = 150, 1770, 470
    s += f'<rect x="{x0}" y="{yb-6}" width="{x1-x0}" height="12" rx="6" fill="url(#gb)"/>'
    etapas = [("gear", "Equipamentos", "modelos físicos e", "bancadas de ensaio", A),
              ("bus", "Microrrede", "composição a partir", "dos equipamentos", A),
              ("cloud", "Cenário", "previsões, tarifa e", "estado inicial", A),
              ("brain", "Gerenciamento", "planejador + MPC,", "com valor futuro", B),
              ("doc", "Resultados", "rastreáveis, relatórios", "e estudos exportáveis", A)]
    passo = (x1 - x0) / 5
    for i, (k, t, l1, l2, c) in enumerate(etapas):
        cx = x0 + passo * (i + .5)
        destaque = c == B
        s += f'<circle cx="{cx}" cy="{yb}" r="{58 if destaque else 50}" fill="{NAVY if destaque else "#fff"}" stroke="{c}" stroke-width="4"/>'
        s += ic(k, cx - 26, yb - 26, 52, "#fff" if destaque else c)
        if i < 4:
            s += f'<path d="M{cx+64} {yb-30} l14 0" stroke="{MUTED}" stroke-width="0"/>'
        s += T(cx, yb + 106, t, 26, 700, NAVY, "Gelasio", anchor="middle")
        s += T(cx, yb + 138, l1, 18, 600, SLATE, anchor="middle") + T(cx, yb + 162, l2, 18, 600, SLATE, anchor="middle")
    # chaves das contribuições
    yk = 700
    pa, pb = x0 + passo * 0.5, x0 + passo * 4.5
    s += f'<path d="M{x0+20} {yk} v14 H{x1-20} v-14" fill="none" stroke="{A}" stroke-width="3"/>'
    s += f'<line x1="960" x2="960" y1="{yk+14}" y2="{yk+34}" stroke="{A}" stroke-width="3"/>'
    s += T(960, yk + 70, "Plataforma modular", 28, 700, A, "Gelasio", anchor="middle")
    cxe = x0 + passo * 3.5
    s += f'<path d="M{cxe} {yb-64} V{yb-112}" stroke="{B}" stroke-width="3"/>'
    s += T(cxe, yb - 124, "EMS hierárquico MILP–MPC", 26, 700, B, "Gelasio", anchor="middle")
    # para quê
    usos = [("swap", "comparar composições"), ("clock", "comparar estratégias"), ("trace", "reproduzir estudos")]
    for i, (k, t) in enumerate(usos):
        x = 380 + i * 400
        s += f'<rect x="{x}" y="820" width="360" height="66" rx="33" fill="{LIGHT}"/>' + ic(k, x + 24, 835, 36, TEAL) + T(x + 74, 862, t, 21, 700, NAVY)
    salvar("S7_J3_bancada", "O SEEDS", s, html)


if __name__ == "__main__":
    j1()
    j2()
    j3()
