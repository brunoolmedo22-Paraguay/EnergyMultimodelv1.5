"""Slide 19 (deck) — Representação energética comum: três propostas. Fonte: Seção 5.2 do artigo.
Por quê: recursos com naturezas distintas (sem estado, com estado, despacháveis, intercâmbio) entram num MESMO problema porque são expressos
numa representação comum: barramento equivalente único, kW líquidos com convenção de sinais única, potências médias por intervalo e energias
nas fronteiras, mesma discretização (previsões alinhadas sem interpolação). Como: a não linearidade é resolvida ANTES do MILP —
renováveis = limite superior exógeno (média das amostras; diferença = vertimento); bateria = balanço da eq. 4 por banco (α = 1, sem agregar);
PEMFC = curva H₂–potência linear por partes, gerada uma vez e aceita só com erro verificado (modelo dinâmico confere depois); PCC = modo,
sentidos, limites e tarifas declarados (ausência ≠ ilimitado; isolada ⇒ termos não existem); demanda = série prevista agregada.
Origens: inventário · cenário · declarações da estratégia. Mini-gráficos ESQUEMÁTICOS."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, DEF2, HEAD, NAVY, SLATE, TEAL, LIGHT, LINE, BAT, PEM, MUTED, T, div, ic, barramento, SOLAR, REDE, FUT, WIND
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
TIT = '<div class="tt">Representação energética comum</div>'
REF = "Seção 5.2 do artigo · eq. 4 (bateria) · mini-gráficos esquemáticos"


def salvar(nome, s, h):
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEF2}{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(19))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


# ---------------------------------------------------------------- mini-gráficos (esquemáticos)
def g_renov(x, y, w, h):
    n = 24
    av = [max(0, __import__("math").sin(3.14159 * (i - 5) / 14)) for i in range(n)]
    us = [min(a, .62) for a in av]
    bw = w / n
    o = ""
    for i in range(n):
        ha, hu = av[i] * h, us[i] * h
        o += f'<rect x="{x+i*bw+1}" y="{y+h-ha}" width="{bw-2}" height="{ha-hu}" fill="{SOLAR}" opacity=".28"/>'
        o += f'<rect x="{x+i*bw+1}" y="{y+h-hu}" width="{bw-2}" height="{hu}" fill="{SOLAR}"/>'
    o += f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="{NAVY}" stroke-width="1.6"/>'
    o += T(x + w * .52, y + h - .97 * h - 6, "Vertimento", 15, 700, "#B88710", anchor="middle")
    return o


def g_bat(x, y, w, h):
    E = [.45, .45, .58, .74, .86, .86, .62, .36, .22]
    n = len(E) - 1
    px = lambda k: x + w * k / n
    py = lambda e: y + h - h * e
    o = f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="{NAVY}" stroke-width="1.6"/>'
    o += f'<path d="M{px(0)} {py(E[0])} ' + " ".join(f"L{px(k)} {py(e)}" for k, e in enumerate(E)) + f'" fill="none" stroke="{BAT}" stroke-width="3"/>'
    for k, e in enumerate(E):
        o += f'<circle cx="{px(k)}" cy="{py(e)}" r="5.5" fill="#fff" stroke="{BAT}" stroke-width="2.5"/>'
    return o


def g_pem(x, y, w, h):
    f = lambda p: .08 + .55 * p + .37 * p ** 2.4
    n = 60
    curva = " ".join(f"{'M' if i == 0 else 'L'}{x+w*i/n:.1f} {y+h-h*f(i/n):.1f}" for i in range(n + 1))
    vs = [0, .3, .55, .78, 1]
    pwl = " ".join(f"{'M' if i == 0 else 'L'}{x+w*v:.1f} {y+h-h*f(v):.1f}" for i, v in enumerate(vs))
    o = (f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="{NAVY}" stroke-width="1.6"/>'
         f'<path d="{curva}" fill="none" stroke="{MUTED}" stroke-width="3" stroke-dasharray="5 6"/>'
         f'<path d="{pwl}" fill="none" stroke="{PEM}" stroke-width="3.5"/>')
    for v in vs:
        o += f'<circle cx="{x+w*v}" cy="{y+h-h*f(v)}" r="5" fill="{PEM}"/>'
    return o


def g_pcc(x, y, w, h):
    a, b = x + w * .68, x + w * .86
    o = (f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="{NAVY}" stroke-width="1.6"/>'
         f'<rect x="{a}" y="{y}" width="{b-a}" height="{h}" fill="{REDE}" opacity=".10"/>'
         f'<path d="M{x} {y+h*.72} H{a} V{y+h*.12} H{b} V{y+h*.72} H{x+w}" fill="none" stroke="{REDE}" stroke-width="3.5"/>')
    return o + T((a + b) / 2, y - 6, "Ponta", 15, 700, REDE, anchor="middle")


def g_dem(x, y, w, h):
    import math
    n = 24
    v = [.45 + .25 * math.sin(6.283 * (i - 6) / 24) + .18 * (17 <= i <= 20) for i in range(n)]
    bw = w / n
    o = "".join(f'<rect x="{x+i*bw+1}" y="{y+h-h*a}" width="{bw-2}" height="{h*a}" fill="{NAVY}" opacity=".75"/>' for i, a in enumerate(v))
    return o + f'<line x1="{x}" x2="{x+w}" y1="{y+h}" y2="{y+h}" stroke="{NAVY}" stroke-width="1.6"/>'


REC = [  # chave, ícone, cor, nome, entra no MILP como, detalhe, gráfico
    ("ren", "sun", SOLAR, "Solar e eólica", "Limite superior", "Média das amostras do intervalo, sem interpolação; o que sobra é vertimento", g_renov),
    ("bat", "bat", BAT, "Bateria", "Energia nas fronteiras", "Balanço da eq. 4 em cada banco, sem agregar bancos", g_bat),
    ("pem", "h2", PEM, "PEMFC", "Curva H₂ linear por partes", "Gerada uma vez pelo modelo e aceita só com erro verificado", g_pem),
    ("pcc", "grid", REDE, "Rede (PCC)", "Sentidos, limites e tarifas", "Declarados; ausência não é intercâmbio ilimitado", g_pcc),
    ("dem", "load", NAVY, "Demanda", "Série prevista", "Agregada, na mesma malha de tempo", g_dem),
]


# ===================================================================== P1 · barramento + o que cada recurso entrega
def p1():
    s, h = "", ""
    s += f'<rect x="110" y="176" width="1700" height="12" rx="6" fill="url(#gb)"/>'
    n, w, gap = 5, 322, 22
    for i, (k, icn, c, nome, como, det, g) in enumerate(REC):
        x = 110 + i * (w + gap)
        cx = x + w / 2
        s += f'<line x1="{cx}" x2="{cx}" y1="188" y2="214" stroke="{c}" stroke-width="3"/><circle cx="{cx}" cy="182" r="6" fill="#fff" stroke="{c}" stroke-width="2.5"/>'
        s += f'<circle cx="{cx}" cy="246" r="32" fill="#fff" stroke="{c}" stroke-width="3"/>' + ic(icn, cx - 20, 226, 40, c)
        s += f'<rect x="{x}" y="296" width="{w}" height="490" rx="24" fill="{LIGHT}"/>'
        s += T(cx, 340, nome, 24, 700, NAVY, "Gelasio", anchor="middle")
        s += g(x + 34, 372, w - 68, 106)
        h += div(x + 24, 512, w - 48, None, f'<div style="font:600 18px Manrope;color:#7B8794;margin-bottom:8px">Entra no MILP como</div><div style="font:700 22px/1.25 Gelasio,serif;color:{c if k != "dem" else NAVY};margin-bottom:14px">{como}</div>{det}', "p",
                 "font-size:22px;line-height:1.55;text-align:center")
    # convenções comuns
    s += f'<rect x="110" y="808" width="1700" height="116" rx="24" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
    h += div(140, 826, 1640, 80, "<span><b>Comum a todos:</b> Barramento equivalente único · kW líquidos com uma convenção de sinais · Potências médias por "
             "intervalo e energias nas fronteiras · A mesma malha de tempo · A não linearidade resolvida <b>antes</b> do MILP</span>", "p",
             "font-size:22px;line-height:1.5;display:flex;align-items:center")
    salvar("S19_P1_barramento", s, h)


# ===================================================================== P2 · do modelo físico ao MILP, linha a linha
def p2():
    s, h = "", ""
    s += T(390, 204, "Modelo físico", 24, 700, SLATE, "Gelasio", anchor="middle")
    s += T(900, 204, "Representação comum", 24, 700, TEAL, "Gelasio", anchor="middle")
    s += T(1540, 204, "Entra no MILP como", 24, 700, NAVY, "Gelasio", anchor="middle")
    fis = ["Irradiância, temperatura, vento → potência", "Capacidade, SOC, eficiências", "Modelo eletroquímico (não linear)",
           "Modo, sentidos, limites, tarifas", "Perfil previsto"]
    for i, (k, icn, c, nome, como, det, g) in enumerate(REC):
        y = 228 + i * 134
        s += f'<rect x="110" y="{y}" width="1700" height="118" rx="20" fill="{LIGHT if i % 2 == 0 else "#fff"}"/>'
        s += f'<circle cx="160" cy="{y+59}" r="28" fill="#fff" stroke="{c}" stroke-width="3"/>' + ic(icn, 142, y + 41, 36, c)
        h += div(204, y + 14, 430, 90, f'<b>{nome}</b><br><span style="font-size:19px">{fis[i]}</span>', "p", "font-size:22px;line-height:1.35;display:flex;flex-direction:column;justify-content:center")
        s += f'<line x1="650" x2="700" y1="{y+59}" y2="{y+59}" stroke="{NAVY}" stroke-width="3" marker-end="url(#ar)"/>'
        s += g(720, y + 18, 340, 82)
        s += f'<line x1="1090" x2="1140" y1="{y+59}" y2="{y+59}" stroke="{NAVY}" stroke-width="3" marker-end="url(#ar)"/>'
        h += div(1160, y + 10, 630, 98, f'<div style="font:700 22px Gelasio,serif;color:#14213D">{como}</div>{det}', "p", "font-size:20px;line-height:1.3;display:flex;flex-direction:column;justify-content:center")
    salvar("S19_P2_linhas", s, h)


# ===================================================================== P3 · uma malha de tempo comum + recursos + verificação
def p3():
    s, h = "", ""
    # malha de tempo: N intervalos (potência média) e N+1 fronteiras (energia)
    x0, x1, yb = 150, 1150, 330
    N = 8
    cw = (x1 - x0) / N
    s += f'<rect x="110" y="176" width="1080" height="330" rx="24" fill="{LIGHT}"/>'
    s += T(150, 222, "Uma só malha de tempo", 26, 700, NAVY, "Gelasio")
    import math
    for t in range(N):
        p = .35 + .3 * math.sin(t * .9)
        s += f'<rect x="{x0+t*cw+6}" y="{yb+120-p*120}" width="{cw-12}" height="{p*120}" rx="6" fill="{TEAL}" opacity=".85"/>'
    for k in range(N + 1):
        s += f'<line x1="{x0+k*cw}" x2="{x0+k*cw}" y1="{yb-60}" y2="{yb+130}" stroke="{MUTED}" stroke-width="1.5" stroke-dasharray="3 5"/>'
        s += f'<circle cx="{x0+k*cw}" cy="{yb-40}" r="8" fill="#fff" stroke="{BAT}" stroke-width="3"/>'
    s += f'<line x1="{x0}" x2="{x1}" y1="{yb+120}" y2="{yb+120}" stroke="{NAVY}" stroke-width="2"/>'
    s += T(x0, yb + 160, "potência média por intervalo Δt (kW)", 20, 700, TEAL) + T(x1, yb + 160, "energia nas fronteiras (kWh)", 20, 700, BAT, anchor="end")
    # convenções
    h += div(1230, 184, 580, 320, "<b>Barramento equivalente único</b>, em kW líquidos com uma convenção de sinais.<br><br>"
             "Previsões <b>alinhadas</b> à malha, sem interpolação; nada ausente vira zero.", "p", "font-size:23px")
    # recursos: chips com o que entra
    y = 540
    w, gap = 322, 22
    for i, (k, icn, c, nome, como, det, g) in enumerate(REC):
        x = 110 + i * (w + gap)
        s += f'<rect x="{x}" y="{y}" width="{w}" height="230" rx="22" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
        s += f'<circle cx="{x+44}" cy="{y+46}" r="24" fill="#fff" stroke="{c}" stroke-width="2.5"/>' + ic(icn, x + 29, y + 31, 30, c)
        s += T(x + 82, y + 54, nome, 22, 700, NAVY, "Gelasio")
        h += div(x + 24, y + 92, w - 48, None, f'<b>{como}</b><br>{det}', "p", "font-size:20px;line-height:1.32")
    # verificação
    s += f'<rect x="110" y="808" width="1700" height="116" rx="24" fill="{NAVY}"/>'
    s += T(150, 856, "Antes de executar:", 24, 700, "#fff", "Gelasio")
    for j, (t, c) in enumerate((("representável", "#6DB527"), ("excluído", "#D9A21B"), ("impeditivo", "#E0524F"))):
        xx = 440 + j * 280
        s += f'<rect x="{xx}" y="822" width="250" height="48" rx="24" fill="none" stroke="{c}" stroke-width="2.5"/>' + T(xx + 125, 854, t, 22, 700, c, anchor="middle")
    h += div(1300, 806, 490, 80, "nada é aproximado nem omitido em silêncio", "", "display:flex;align-items:center;font:italic 500 22px/1.3 Gelasio,serif;color:#C1FF72")
    salvar("S19_P3_malha", s, h)


if __name__ == "__main__":
    p1()
    p2()
    p3()
