"""Slide 7 — v2: mais claro. Responde: o que é · que lacuna resolve · como · o que oferece · para quem.
K1 grade de perguntas · K2 até aqui × com o SEEDS · K3 ficha (tabela de perguntas e respostas).
«Para quem» é o público PRETENDIDO (pesquisa, ensino, projeto e operação) — não é afirmação de uso medido."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide7 import (NAVY, SLATE, TEAL, LIGHT, LINE, LIME, G1, G2, G3, MUTED, A, B, T, ICON, ic, div, salvar, chevs)

ICON.update({
    "flask": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M15 5h10M17 5v11L7 34h26L23 16V5"/><path d="M11 27h18"/></g>',
    "cap": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M3 15l17-8 17 8-17 8z"/><path d="M10 19v9c5 4 15 4 20 0v-9M37 15v10"/></g>',
    "ruler": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M5 27L27 5l8 8-22 22z"/><path d="M12 20l3 3M16 16l3 3M20 12l3 3M24 8l3 3"/></g>',
})
O_QUE_E = ('Uma <span style="color:#1F7A6D">bancada experimental</span>, no navegador, para '
           '<span style="color:#2E9E6B">compor microrredes</span> e <span style="color:#2C6FB0">testar o seu gerenciamento energético</span>.')
PUBLICO = [("flask", "pesquisa"), ("cap", "ensino"), ("ruler", "projeto e operação de microrredes")]


def chip(x, y, k, t, h=60):
    w = len(t) * 10.6 + 86
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
            + ic(k, x + 20, y + h / 2 - 17, 34, TEAL) + T(x + 66, y + h / 2 + 7, t, 20, 700, NAVY)), w


# ===================================================================== K1 · grade de perguntas
def k1():
    html = div(110, 178, 1700, O_QUE_E, "h", "font-size:44px")
    s = ""
    cards = [(110, 330, "O que resolve"), (970, 330, "Como"), (110, 628, "O que oferece"), (970, 628, "Para quem")]
    for x, y, t in cards:
        s += f'<rect x="{x}" y="{y}" width="840" height="{280 if y == 330 else 270}" rx="26" fill="{LIGHT}"/>'
        s += T(x + 40, y + 58, t, 28, 700, TEAL, "Gelasio")
    html += div(150, 410, 760, 'Hoje, ou se avalia um EMS avançado em <b>uma única microrrede</b>, ou se troca a composição '
                'com <b>estratégias predefinidas</b>. O SEEDS reúne as duas coisas.', "p", "font-size:22px")
    s += chevs(1010, 420, ["modelos", "microrrede", "EMS hierárquico", "resultados"], G2, 44)
    html += div(1010, 492, 760, 'Modelos físicos dos equipamentos formam a microrrede; um EMS hierárquico MILP–MPC decide '
                'com o valor futuro da energia; cada rodada fica registrada.', "p", "font-size:20px")
    for i, (k, c, t) in enumerate([("swap", A, "compor microrredes diferentes"), ("brain", B, "operá-las com o mesmo EMS"),
                                   ("trace", G3, "comparar e reproduzir resultados")]):
        y = 738 + i * 54
        s += ic(k, 150, y - 26, 34, c) + T(198, y, t, 23, 700, NAVY, "Gelasio")
    x = 1010
    for k, t in PUBLICO[:2]:
        c, w = chip(x, 716, k, t); s += c; x += w + 16
    c, _ = chip(1010, 796, *PUBLICO[2]); s += c
    salvar("S7v2_K1_perguntas", "O SEEDS", s, html)


# ===================================================================== K2 · até aqui × com o SEEDS
def k2():
    html = div(110, 178, 1700, O_QUE_E, "h", "font-size:44px")
    s = ""
    y0, h = 340, 420
    # até aqui
    s += f'<rect x="110" y="{y0}" width="760" height="{h}" rx="28" fill="{LIGHT}"/>'
    s += T(150, y0 + 62, "Até aqui", 30, 700, MUTED, "Gelasio")
    antes = [("lock", "Composição fixa", "EMS avançado avaliado em uma única microrrede"),
             ("rule", "Estratégia predefinida", "troca-se a composição, com regras fixas de operação"),
             ("doc", "Avaliações isoladas", "configuração, cenário e resultado sem vínculo")]
    depois = [("swap", A, "Plataforma modular", "qualquer composição, a partir dos modelos dos equipamentos"),
              ("brain", B, "EMS hierárquico MILP–MPC", "o mesmo gerenciamento, com o valor futuro da energia"),
              ("trace", G3, "Rastreabilidade", "cada rodada guardada e reaberta com verificação")]
    for i, (k, t, d) in enumerate(antes):
        y = y0 + 132 + i * 96
        s += ic(k, 150, y - 26, 38, MUTED) + T(206, y - 2, t, 24, 700, "#7B8794", "Gelasio") + T(206, y + 28, d, 18, 600, MUTED)
    # seta
    s += f'<polygon points="900,{y0+h/2-40} 950,{y0+h/2} 900,{y0+h/2+40}" fill="url(#gb)"/>'
    # com o SEEDS
    s += f'<rect x="980" y="{y0}" width="830" height="{h}" rx="28" fill="#fff" stroke="url(#gb)" stroke-width="5" filter="url(#sh)"/>'
    s += f'<image href="../capa/assets/seeds.png" x="1020" y="{y0+22}" width="190" height="59"/>'
    for i, (k, c, t, d) in enumerate(depois):
        y = y0 + 132 + i * 96
        s += f'<circle cx="1040" cy="{y-8}" r="26" fill="{c}"/>' + ic(k, 1022, y - 26, 36, "#fff")
        s += T(1086, y - 2, t, 25, 700, NAVY, "Gelasio") + T(1086, y + 28, d, 18, 600, SLATE)
    # para quem
    s += T(110, 848, "Para quem", 26, 700, TEAL, "Gelasio")
    x = 270
    for k, t in PUBLICO:
        c, w = chip(x, 812, k, t, 58); s += c; x += w + 18
    salvar("S7v2_K2_antes_depois", "O SEEDS", s, html)


# ===================================================================== K3 · ficha
def k3():
    s = f'<rect x="110" y="172" width="560" height="730" rx="28" fill="{NAVY}"/>'
    s += f'<image href="../capa/assets/seeds_dark.png" x="150" y="214" width="300" height="93"/>'
    html = div(150, 360, 480, O_QUE_E.replace("#1F7A6D", "#C1FF72").replace("#2E9E6B", "#C1FF72").replace("#2C6FB0", "#C1FF72"),
               "h", "font-size:38px;line-height:1.3;color:#fff")
    linhas = [("O que resolve", "reúne o que a literatura avaliava separado: <b>composição variável</b> e <b>gerenciamento avançado</b>"),
              ("Como", "modelos físicos dos equipamentos → microrrede → <b style=\"white-space:nowrap\">EMS hierárquico MILP–MPC</b> com valor futuro → resultados registrados"),
              ("O que oferece", "compor microrredes diferentes, operá-las com o mesmo EMS, <b>comparar e reproduzir</b> resultados"),
              ("Para quem", "")]
    X, y0, dy = 720, 178, 182
    for i, (q, r) in enumerate(linhas):
        y = y0 + i * dy
        if i:
            s += f'<line x1="{X}" x2="1810" y1="{y}" y2="{y}" stroke="{LINE}" stroke-width="1.5"/>'
        s += T(X, y + 62, q, 28, 700, TEAL, "Gelasio")
        if r:
            html += div(X + 270, y + 30, 820, r, "p", "font-size:22px;line-height:1.45;color:#14213D")
    x = X + 270
    for k, t in PUBLICO[:2]:
        c, w = chip(x, y0 + 3 * dy + 30, k, t, 56); s += c; x += w + 14
    c, _ = chip(X + 270, y0 + 3 * dy + 100, *PUBLICO[2], 56); s += c
    salvar("S7v2_K3_ficha", "O SEEDS", s, html)


if __name__ == "__main__":
    k1()
    k2()
    k3()


# ===================================================================== K3 v2 · ficha com ilustração (barramento vertical, recursos e curvas)
from gerar_slide7 import SOLAR, WIND, PEM, BAT, REDE  # noqa: E402


def ilustracao(cx, y0, y1, xl, xr, r=37, sep=34):
    """Barramento vertical com o gradiente SEEDS; recursos à esquerda (fontes) e à direita (bateria, rede),
    ligados por curvas suaves com um traço de fluxo perto do barramento (como a referência do responsável)."""
    o = (f'<linearGradient id="gbv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{G1}"/>'
         f'<stop offset=".55" stop-color="{G2}"/><stop offset="1" stop-color="{G3}"/></linearGradient>')
    esq = [("sun", SOLAR, y0 + r * .8), ("wind", WIND, (y0 + y1) / 2), ("h2", PEM, y1 - r * .8)]
    dir_ = [("bat", BAT, y0 + (y1 - y0) * .28), ("grid", REDE, y1 - (y1 - y0) * .28)]
    for lado, itens in ((-1, esq), (1, dir_)):
        for j, (k, c, yy) in enumerate(itens):
            xn = xl if lado < 0 else xr
            yb = (y0 + y1) / 2 + (j - (len(itens) - 1) / 2) * sep      # chegada no barramento
            xb = cx + lado * 11
            x0 = xn - lado * r
            d = f"M{x0} {yy} C{(x0+xb)/2} {yy}, {(x0+xb)/2 + lado*20} {yb}, {xb} {yb}"
            o += f'<path d="{d}" fill="none" stroke="{c}" stroke-width="3.5" stroke-opacity=".55"/>'
            # traço de fluxo: segmento da própria curva perto do barramento
            o += (f'<path d="{d}" fill="none" stroke="{c}" stroke-width="6" stroke-linecap="round" '
                  f'pathLength="100" stroke-dasharray="7 100" stroke-dashoffset="-78"/>')
            o += f'<circle cx="{xn}" cy="{yy}" r="{r}" fill="{c}" fill-opacity=".18" stroke="{c}" stroke-opacity=".55" stroke-width="2"/>'
            o += ic(k, xn - r * .57, yy - r * .57, r * 1.14, c)
    o += f'<rect x="{cx-11}" y="{y0-10}" width="22" height="{y1-y0+20}" rx="11" fill="url(#gbv)"/>'
    for t in range(6):
        o += f'<circle cx="{cx}" cy="{y0 + 14 + t*(y1-y0-8)/5}" r="2.5" fill="#fff" opacity=".55"/>'
    return o


O_QUE_E2 = O_QUE_E.replace("compor microrredes", "compor sistemas elétricos")


def k3v2():
    s = f'<rect x="110" y="172" width="560" height="730" rx="28" fill="{NAVY}"/>'
    s += f'<image href="../capa/assets/seeds_dark.png" x="150" y="217" width="280" height="87"/>'
    s += ilustracao(390, 679, 847, 236, 544, r=26, sep=26)
    html = div(150, 329, 490, O_QUE_E2.replace("#1F7A6D", "#C1FF72").replace("#2E9E6B", "#C1FF72").replace("#2C6FB0", "#C1FF72"),
               "h", "font-size:37px;line-height:1.28;color:#fff")
    linhas = [("O que resolve", "reúne o que a literatura avaliava separado: <b>composição variável</b> e <b>gerenciamento avançado</b>"),
              ("Como", "modelos físicos dos equipamentos → sistema elétrico → <b style=\"white-space:nowrap\">EMS hierárquico MILP–MPC</b> com valor futuro → resultados registrados"),
              ("O que oferece", "compor sistemas elétricos diferentes, operá-los com o mesmo EMS, <b>comparar e reproduzir</b> resultados"),
              ("Para quem", "quem <b>pesquisa</b>, <b>ensina</b>, <b>projeta</b> ou <b>opera</b> sistemas elétricos")]
    X, y0, dy = 720, 172, 182.5
    for i, (q, r) in enumerate(linhas):
        y = y0 + i * dy
        if i:
            s += f'<line x1="{X}" x2="1810" y1="{y}" y2="{y}" stroke="{LINE}" stroke-width="1.5"/>'
        s += T(X, y + 70, q, 28, 700, TEAL, "Gelasio")
        html += div(X + 270, y + 40, 820, r, "p", "font-size:23px;line-height:1.45;color:#14213D")
    salvar("S7v3_K3_ficha", "O SEEDS", s, html)


k3v2()
