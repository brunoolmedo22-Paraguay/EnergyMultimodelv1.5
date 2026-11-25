"""Ordem do deck (fonte única): escreve pptx/deck.json, as notas e os slides provisórios dos que ainda não foram desenhados.
Cada item: n (posição no deck), título, seção do sumário, arquivo HTML aprovado (ou provisório) e notas do orador.
O número de página de cada HTML é substituído na exportação (`exportar_deck.js`), então mudar a ordem aqui basta."""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(AQUI, "..")
sys.path.insert(0, os.path.join(R, "guia"))
sys.path.insert(0, os.path.join(R, "slides"))
import conteudo  # noqa: E402
from gerar_slide4_v3 import CSS  # noqa: E402

FALA = {s["t"]: s.get("fala", "") for s in conteudo.SLIDES}
SEC = ["Contexto e objetivos", "Fundamentação teórica", "Desenvolvimento do SEEDS", "Estudos de caso",
       "Demonstração do SEEDS", "Resultados", "Conclusões e perspectivas"]

# (título, seção 1–7, html aprovado relativo a docs/defesa_tcc, ou None = provisório)
ORDEM = [
    ("Capa", 0, "capa/capa_oficial.html"),
    ("Sumário", 0, "capa/sumario.html"),
    ("Contexto e objetivos", 1, "slides/divisor01.html"),
    ("Contexto", 1, "slides/slide03_aprovado.html"),
    ("Decisões com consequências futuras", 1, "slides/slide04_aprovado.html"),
    ("Trabalhos relacionados", 1, "slides/slide05_aprovado.html"),
    ("Objetivos", 1, "slides/slide06_aprovado.html"),
    ("O SEEDS", 1, "slides/slide07_aprovado.html"),
    ("Fundamentação teórica", 2, "slides/divisor02.html"),
    ("Modelagem dos recursos energéticos", 2, "slides/slide08_aprovado.html"),
    ("Modelagem dos recursos energéticos (2/2)", 2, "slides/slide09_aprovado.html"),
    ("Programação linear inteira mista (MILP)", 2, None),
    ("Controle preditivo baseado em modelo (MPC)", 2, None),
    ("Coordenação hierárquica e valor futuro", 2, None),
    ("Desenvolvimento do SEEDS", 3, "slides/divisor03.html"),
    ("Arquitetura do SEEDS", 3, None),
    ("Representação energética comum", 3, None),
    ("Gerenciamento energético hierárquico no SEEDS", 3, None),
    ("Verificação e fluxo de execução", 3, None),
    ("Estudos de caso", 4, "slides/divisor04.html"),
    ("Estratégia de avaliação", 4, None),
    ("Microrrede industrial CT-046 (C1–C4)", 4, None),
    ("Embarcação híbrida EMB-H2-120 (C5–C6)", 4, None),
    ("Demonstração do SEEDS", 5, "slides/divisor05.html"),
    ("Demonstração do SEEDS — roteiro", 5, None),
    ("Resultados", 6, "slides/divisor06.html"),
    ("Resultados — custos operacionais (C1–C4)", 6, None),
    ("Resultados — operação do armazenamento", 6, None),
    ("Resultados — coordenação hierárquica", 6, None),
    ("Resultados — embarcação híbrida (C5)", 6, None),
    ("Resultados — papel do armazenamento (C4, C5 e C6)", 6, None),
    ("Expansibilidade e desempenho computacional", 6, None),
    ("Conclusões e perspectivas", 7, "slides/divisor07.html"),
    ("Conclusões", 7, None),
    ("Perspectivas", 7, None),
    ("Agradecimentos", 7, None),
]
# título do slide no roteiro (conteudo.py) quando difere do título no deck — para buscar a fala
ALIAS = {"Estratégia de avaliação": "Estudos de caso", "Demonstração do SEEDS — roteiro": "Demonstração do SEEDS",
         "Resultados — coordenação hierárquica": "Resultados — coordenação hierárquica"}
NOTA_EXTRA = {
    "Modelagem dos recursos energéticos (2/2)": "O banco de baterias entra como balanço de energia entre fronteiras; a rede, como intercâmbio com tarifas no ponto de acoplamento comum — numa microrrede isolada, esses termos não existem.",
}
PROV = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}
.pv{{position:absolute;left:110px;top:200px;font:600 22px "Manrope";color:#9AA5B1}}</style></head><body><div class="slide">
<div class="tt">{t}</div><div class="pv">Slide em preparação</div>
<div class="hl" style="bottom:112px"></div><div class="ft"><img src="../../capa/assets/unila.png"><div class="sep"></div>
<span>Engenharia de Energia · ILATIT</span><div class="sep"></div><span><b>Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>
<div class="pn">{n}</div></div></body></html>"""


def main():
    os.makedirs(os.path.join(R, "slides", "provisorios"), exist_ok=True)
    deck = []
    for n, (t, sec, html) in enumerate(ORDEM, 1):
        if sec and t == SEC[sec - 1] and html and "divisor" in html:
            nota = f"Separador da seção {sec:02d} — {t}."
        else:
            nota = NOTA_EXTRA.get(t) or FALA.get(ALIAS.get(t, t), "") or FALA.get(t.replace(" (2/2)", ""), "")
        if html is None:
            html = f"slides/provisorios/p{n:02d}.html"
            css = CSS.replace('@import url("../capa/assets/fonts.css");', '@import url("../../capa/assets/fonts.css");')
            open(os.path.join(R, html), "w", encoding="utf-8").write(PROV.format(css=css, t=t, n=n))
            pronto = False
        else:
            pronto = True
        deck.append(dict(n=n, titulo=t, secao=sec, html=html, pronto=pronto, notas=nota))
    json.dump(deck, open(os.path.join(AQUI, "deck.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(deck), "slides;", sum(d["pronto"] for d in deck), "prontos")


if __name__ == "__main__":
    main()
