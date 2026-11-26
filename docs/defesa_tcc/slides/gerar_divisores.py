"""Separadores de seção (um para cada etapa do sumário), com a subdivisão da seção.
Cores e ícones = os do sumário aprovado (`capa/gerar_sumario2.py`: posição de cada nó no gradiente; ícones IC).
Três propostas (V1 sumário em foco · V2 número grande + barramento · V3 fundo azul-marinho), cada uma com os separadores 02 e 03."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide5 import CSS, NAVY, SLATE, LIGHT, LIME, MUTED, T
from gerar_slide5_v3 import DEFS3
import types
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "capa", "gerar_sumario2.py"), encoding="utf-8").read()
SM = types.SimpleNamespace(__file__=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "capa", "gerar_sumario2.py"))
exec(_src[:_src.index("GRAD =")], SM.__dict__)          # só IC e cor(); não regera as maquetas do sumário

D = os.path.dirname(os.path.abspath(__file__))
SECOES = ["Contexto e objetivos", "Fundamentação teórica", "Desenvolvimento do SEEDS", "Estudos de caso",
          "Demonstração do SEEDS", "Resultados", "Conclusões e perspectivas"]
_XS = [315, 530, 745, 960, 1175, 1390, 1605]            # posições dos nós no sumário aprovado (zigue-zague)
COR = [SM.cor((x - 110) / 1700) for x in _XS]
SUB = {
    1: ["Contexto", "Decisões com consequências futuras", "Trabalhos relacionados", "Objetivos", "O SEEDS"],
    2: ["Modelagem dos recursos energéticos", "Programação linear inteira mista (MILP)",
        "Controle preditivo baseado em modelo (MPC)", "Coordenação hierárquica e valor futuro"],
    3: ["Arquitetura e representação energética comum", "Gerenciamento energético hierárquico no SEEDS",
        "Verificação e fluxo de execução"],
    4: ["Estratégia de avaliação", "Microrrede industrial CT-046 (C1–C4)", "Embarcação híbrida EMB-H2-120 (C5–C6)"],
    5: ["Reprodução ao vivo de um estudo de caso no aplicativo"],
    6: ["Operação do armazenamento", "Custos operacionais (C1–C4)", "Embarcação híbrida (C5 × C6)",
        "Expansibilidade e desempenho computacional"],
    7: ["Conclusões", "Trabalhos futuros", "Agradecimentos"],
}
PN = {1: 3, 2: 9, 3: 16, 4: 21, 5: 25, 6: 27, 7: 34}     # posição no deck de 36 slides (ver pptx/deck.json)
CSSD = CSS + """
.d{position:absolute}
.big{font:700 86px/1.05 "Gelasio",Georgia,serif;color:#14213D}
.it{font:700 34px/1.2 "Gelasio",Georgia,serif;color:#14213D}
"""
HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide" style="{bg}">{body}</div></body></html>'


def rodape(n, escuro=False):
    if escuro:
        return ('<div class="hl" style="bottom:112px;background:#2C3A5C"></div><div class="ft" style="color:#9AA5B1">'
                '<img src="../capa/assets/unila_branco.png"><div class="sep" style="background:#2C3A5C"></div>'
                '<span>Engenharia de Energia · ILATIT</span><div class="sep" style="background:#2C3A5C"></div>'
                '<span><b style="color:#DCE3E2">Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>'
                f'<div class="pn" style="color:#fff">{n}</div>')
    return ('<div class="hl" style="bottom:112px"></div><div class="ft"><img src="../capa/assets/unila.png"><div class="sep"></div>'
            '<span>Engenharia de Energia · ILATIT</span><div class="sep"></div><span><b>Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>'
            f'<div class="pn">{n}</div>')


def icone(k, x, y, s, c):
    return (f'<svg x="{x}" y="{y}" width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c}" fill="none" stroke="currentColor" '
            f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round">{SM.IC[k]}</svg>')


def chevrons(x0, x1, y, h, ativo, apagado=.22, rot=True):
    """Os 7 tramos do sumário; o da seção atual cheio, os demais esmaecidos."""
    n, gap, p = 7, 8, 20
    w = (x1 - x0 - gap * (n - 1)) / n
    o = ""
    for k in range(n):
        x = x0 + k * (w + gap)
        pts = f"{x},{y} {x+w-p},{y} {x+w},{y+h/2} {x+w-p},{y+h} {x},{y+h}" + ("" if k == 0 else f" {x+p},{y+h/2}")
        op = 1 if k + 1 == ativo else apagado
        o += f'<polygon points="{pts}" fill="{COR[k]}" opacity="{op}"/>'
        if rot:
            o += T(x + w / 2 + 6, y + h / 2 + 8, f"{k+1:02d}", 22, 700, "#fff", "Gelasio", anchor="middle")
    return o


def salvar(nome, s, html, n, escuro=False):
    bg = "background:#14213D" if escuro else ""
    body = (f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS3}{s}</svg>'
            + html + rodape(n, escuro))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSD, body=body, bg=bg))


# ===================================================================== V1 · sumário em foco
def v1(sec, nome=None):
    c = COR[sec - 1]
    s = chevrons(110, 1810, 96, 48, sec)
    s += T(110, 400, f"{sec:02d}", 230, 700, c, "Gelasio")
    s += icone(sec - 1, 1694, 236, 116, c)
    if sec == 5:                                        # demonstração: a marca «ao vivo» do sumário
        s += f'<circle cx="1640" cy="294" r="13" fill="{LIME}" opacity=".35"/><circle cx="1640" cy="294" r="7" fill="#7FB800"/>'
        s += T(1622, 302, "ao vivo", 24, 700, "#5B8A00", anchor="end")
    html = f'<div class="d big" style="left:110px;top:452px;width:1500px">{SECOES[sec-1]}</div>'
    itens = SUB[sec]
    n = len(itens)
    um = n == 1
    passo, alto = (108, 92) if n > 4 else (120, 100)
    y0 = 600 if n <= 4 else 586
    for i, t in enumerate(itens):
        x = 110 + (0 if um else (i % 2) * 860)
        y = y0 + (i // (1 if um else 2)) * passo
        w = 1700 if um else 840
        s += f'<rect x="{x}" y="{y}" width="{w}" height="{alto}" rx="22" fill="{LIGHT}"/>'
        s += f'<circle cx="{x+54}" cy="{y+alto/2}" r="28" fill="{c}"/>' + T(x + 54, y + alto / 2 + 9, f"{i+1}", 26, 700, "#fff", "Gelasio", anchor="middle")
        html += f'<div class="d it" style="left:{x+104}px;top:{y+alto/2-22}px;width:{w-130}px;font-size:28px">{t}</div>'
    salvar(nome or f"DIV_V1_{sec:02d}", s, html, PN[sec])


# ===================================================================== V2 · número grande à esquerda + barramento com as partes
def v2(sec):
    c = COR[sec - 1]
    s = f'<rect x="110" y="150" width="720" height="760" rx="34" fill="{LIGHT}"/>'
    s += T(160, 470, f"{sec:02d}", 300, 700, c, "Gelasio")
    s += icone(sec - 1, 690, 196, 96, c)
    html = f'<div class="d big" style="left:160px;top:548px;width:640px;font-size:74px">{SECOES[sec-1]}</div>'
    s += chevrons(160, 780, 836, 26, sec, apagado=.25, rot=False)
    # barramento vertical com as partes da seção
    n = len(SUB[sec])
    xb, y0, y1 = 930, 200, 870
    s += (f'<linearGradient id="gvd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6DB527"/><stop offset=".55" stop-color="#1E8A72"/>'
          f'<stop offset="1" stop-color="#0072BA"/></linearGradient><rect x="{xb-6}" y="{y0}" width="12" height="{y1-y0}" rx="6" fill="url(#gvd)"/>')
    passo = (y1 - y0) / n
    for i, t in enumerate(SUB[sec]):
        yy = y0 + passo * (i + .5)
        s += f'<circle cx="{xb}" cy="{yy}" r="9" fill="#fff" stroke="{c}" stroke-width="4"/><line x1="{xb+9}" x2="{xb+60}" y1="{yy}" y2="{yy}" stroke="{c}" stroke-width="3"/>'
        s += f'<circle cx="{xb+100}" cy="{yy}" r="40" fill="#fff" stroke="{c}" stroke-width="4"/>' + T(xb + 100, yy + 13, f"{i+1}", 36, 700, c, "Gelasio", anchor="middle")
        html += f'<div class="d it" style="left:{xb+170}px;top:{yy-24}px;width:720px">{t}</div>'
    salvar(f"DIV_V2_{sec:02d}", s, html, PN[sec])


# ===================================================================== V3 · fundo azul-marinho, sumário embaixo
def v3(sec):
    c = COR[sec - 1]
    s = f'<text x="1840" y="760" text-anchor="end" font-family="Gelasio" font-weight="700" font-size="620" fill="{c}" opacity=".16">{sec:02d}</text>'
    s += T(110, 250, f"{sec:02d}", 120, 700, c, "Gelasio")
    s += icone(sec - 1, 290, 160, 92, c)
    html = f'<div class="d big" style="left:110px;top:282px;width:1400px;color:#fff">{SECOES[sec-1]}</div>'
    y0 = 450
    for i, t in enumerate(SUB[sec]):
        y = y0 + i * 92
        s += T(110, y + 44, f"{sec}.{i+1}", 30, 700, LIME, "Gelasio")
        s += f'<line x1="196" x2="236" y1="{y+34}" y2="{y+34}" stroke="{c}" stroke-width="3"/>'
        html += f'<div class="d it" style="left:256px;top:{y+12}px;width:1200px;color:#fff">{t}</div>'
    s += chevrons(110, 1810, 836, 34, sec, apagado=.30)
    salvar(f"DIV_V3_{sec:02d}", s, html, PN[sec], escuro=True)


if __name__ == "__main__":
    for sec in range(1, 8):                             # V1 aprovado: separadores definitivos divisor01…07
        v1(sec, f"divisor{sec:02d}")
