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
    ("Programação linear inteira mista (MILP)", 2, "slides/slide12_aprovado.html"),
    ("O MILP da microrrede", 2, "slides/slide13_aprovado.html"),
    ("Controle preditivo baseado em modelo (MPC)", 2, "slides/slide14_aprovado.html"),
    ("Coordenação hierárquica e valor futuro", 2, "slides/slide15_aprovado.html"),
    ("Gerenciamento energético hierárquico MILP–MPC", 2, "slides/slide16_aprovado.html"),
    ("Desenvolvimento do SEEDS", 3, "slides/divisor03.html"),
    ("Arquitetura do SEEDS", 3, "slides/slide18_aprovado.html"),
    ("Representação energética comum", 3, "slides/slide19_aprovado.html"),
    ("Gerenciamento energético hierárquico no SEEDS", 3, "slides/slide20_aprovado.html"),
    ("Verificação e fluxo de execução", 3, "slides/slide21_aprovado.html"),
    ("Estudos de caso", 4, "slides/divisor04.html"),
    ("Estratégia de avaliação", 4, "slides/slide23_aprovado.html"),
    ("Dados de entrada da microrrede CT-046", 4, "slides/slide24_aprovado.html"),
    ("Configuração da CT-046 no SEEDS", 4, "slides/slide25_aprovado.html"),
    ("Dados de entrada da embarcação EMB-H2-120", 4, "slides/slide26_aprovado.html"),
    ("Configuração da EMB-H2-120 no SEEDS", 4, "slides/slide27_aprovado.html"),
    ("Demonstração do SEEDS", 5, "slides/divisor05.html"),
    ("Demonstração do SEEDS — acesso ao aplicativo", 5, "slides/slide29_aprovado.html"),
    ("Resultados", 6, "slides/divisor06.html"),
    ("Resultados — operação do armazenamento", 6, "slides/slide31_aprovado.html"),
    ("Resultados — custos operacionais (C1–C4)", 6, "slides/slide32_aprovado.html"),
    ("Resultados — embarcação híbrida (C5)", 6, None),
    ("Resultados — papel do armazenamento (C4, C5 e C6)", 6, None),
    ("Expansibilidade e desempenho computacional", 6, None),
    ("Conclusões e perspectivas", 7, "slides/divisor07.html"),
    ("Conclusões", 7, None),
    ("Perspectivas", 7, None),
    ("Agradecimentos", 7, None),
]
# título do slide no roteiro (conteudo.py) quando difere do título no deck — para buscar a fala
ALIAS = {"Estratégia de avaliação": "Estudos de caso", "Demonstração do SEEDS — acesso ao aplicativo": "Demonstração do SEEDS",
         "Resultados — coordenação hierárquica": "Resultados — coordenação hierárquica"}
NOTA_EXTRA = {
    "Resultados — custos operacionais (C1–C4)": "Aqui estão os quatro dias lado a lado, custo a cada quinze minutos, na mesma escala. Só com a rede, o dia custa 1.274 reais, e 41 % disso é pago na ponta, que tem apenas 13,7 % da energia. A solar baixa o custo do meio-dia; a bateria achata a ponta, e a parcela paga nela cai para perto da parcela de energia. Os efeitos se somam: em C4 a economia é de 409 reais por dia, 32 %, exatamente a soma da solar e da bateria. E o plano se cumpre: o custo previsto na primeira decisão difere do realizado em um centavo. Vale notar que, sem condição final, a bateria termina o dia com 20 kWh, abaixo dos 60 iniciais.",
    "Resultados — operação do armazenamento": "Este é o dia da configuração C4, desenhado pelo próprio SEEDS a partir da rodada gravada. A rede fica embaixo, a solar e a bateria por cima, e a faixa vermelha é a ponta. A bateria preservou o estoque inicial durante a manhã, quando valeria só 0,44 reais por kWh, carregou fora de ponta até 178 kWh e descarregou no limite do banco, 50 kW, durante toda a ponta. Foram 150 kWh entregues na ponta: comprados da rede, custariam 290,84 reais; carregar fora de ponta custou 54,90 a mais; o ganho líquido foi de 235,94 reais. E metade dessa carga foi decidida antes de a ponta entrar no horizonte do MPC: quem indicou que valia a pena guardar foi o valor futuro do planejador.",
    "Demonstração do SEEDS — acesso ao aplicativo": "O SEEDS está publicado e pode ser aberto agora, por este QR code ou pelo endereço energymultimodelv15.streamlit.app. Vou mostrar ao vivo um dos estudos de caso: abrir uma rodada já concluída, que é reaberta e reauditada sem resolver de novo, e executar outra a partir do cenário salvo.",
    "Dados de entrada da microrrede CT-046": "Na microrrede industrial, as entradas são quatro. A demanda vem de uma curva real da ANEEL, a CT-046, de um dia útil, escalada para 100 kW de pico: são 1.967 kWh no dia, com consumo mantido também na ponta. Irradiância e temperatura são sintéticas, de um dia de céu claro, com máximo de 970 W/m². E a tarifa A4 Horária Verde da COPEL: entre 18 e 21 horas a energia custa 4,4 vezes mais. A potência fotovoltaica não é entrada: o modelo a calcula a partir da irradiância e da temperatura.",
    "Configuração da CT-046 no SEEDS": "No SEEDS, essa microrrede vira quatro configurações que só diferem na composição: só rede; rede e solar; rede e bateria; rede, solar e bateria — a bateria começando em 30 %. O dia tem 96 intervalos de 15 minutos. A cada intervalo, o MPC resolve uma janela de duas horas e aplica só o primeiro intervalo; o horizonte longo cobre o resto do dia e encurta até a meia-noite. A demanda é crítica, a realização é igual à previsão, e não declaramos condição final: quem orienta quanto guardar é o valor futuro, recalculado a cada janela.",
    "Dados de entrada da embarcação EMB-H2-120": "Na embarcação, a demanda é a propulsão: um registro de potência do projeto, repetido para completar 120 minutos e agregado em médias de 15 minutos. As médias conservam a energia da missão, 68,21 kWh, mas reduzem o pico original de 63 para 58,8 kW. Irradiância e temperatura são sintéticas, do meio-dia, quase constantes. O custo é o hidrogênio, a 10 reais por quilo, um preço sintético.",
    "Configuração da EMB-H2-120 no SEEDS": "A composição é a mesma nas duas configurações: solar, bateria e uma PEMFC de cerca de 50 kW, sempre ligada, com mínimo de 10 kW. Muda a bateria: em C5 ela começa em 50 % e deve terminar com pelo menos 45 kWh; em C6 começa quase vazia, em 12 %, sem reserva. São 8 intervalos de 15 minutos; a janela do MPC é de uma hora e o horizonte longo cobre a missão inteira. O objetivo é consumir o mínimo de hidrogênio.",
    "Estratégia de avaliação": "Avaliamos o SEEDS em dois sistemas com filosofias opostas. Uma microrrede industrial ligada à rede, em que o objetivo é otimizar o preço final pago à concessionária. E uma embarcação isolada, em que não há rede: é preciso usar bem a bateria e garantir o suprimento da carga com os recursos de bordo. O mesmo EMS, sem reformulação, nos dois casos.",
    "Verificação e fluxo de execução": "Todo estudo segue estas cinco etapas: a microrrede, com seu inventário em revisão; e o cenário — estados iniciais, previsões e estratégia — salvo como uma versão imutável. Na execução, o Pyomo com o HiGHS resolve cada janela, uma verificação independente confere a solução e, ao fim, uma auditoria integral. Nada é presumido: o que falta volta como pendência. São exatamente as etapas que vou mostrar no aplicativo.",
    "Gerenciamento energético hierárquico no SEEDS": "Assim isso foi implementado. A cada instante de decisão, o planejador parte do estado executado, resolve um plano longo que nunca é aplicado e reotimiza o trecho após a janela várias vezes, com energias iniciais diferentes: daí sai o sinal de valor futuro, uma função linear por partes por modo das unidades. O MPC verifica esse sinal antes de usá-lo; se não for válido, aplica a degradação declarada. O MILP da janela soma operação e custo futuro, a solução é verificada de forma independente, só os m primeiros intervalos são aplicados, e o custo realizado nunca inclui o custo futuro.",
    "Representação energética comum": "Os recursos são muito diferentes, mas entram no mesmo MILP porque falam a mesma língua: um barramento equivalente, kW líquidos com uma convenção de sinais, potências médias por intervalo e energias nas fronteiras, na mesma malha de tempo. Toda a não linearidade é resolvida antes: a renovável vira um limite superior, a bateria um balanço por banco, a célula uma curva de hidrogênio linear por partes com erro verificado, e a rede só existe com sentidos, limites e tarifas declarados.",
    "Arquitetura do SEEDS": "O SEEDS separa o sistema físico da estratégia de gerenciamento. À esquerda, a modularidade: modelos e catálogos, a configuração de cada microrrede, com revisões, e o cenário operativo. No centro, a integração: tudo vira uma representação energética comum por recurso e passa por uma verificação de compatibilidade. À direita, o EMS hierárquico que acabamos de ver, em malha fechada. Trocar um equipamento muda a instância do problema, não a formulação, e cada resultado fica ligado à revisão e à versão do cenário que o originaram.",
    "Gerenciamento energético hierárquico MILP–MPC": "Juntando as peças: o planejamento de horizonte ampliado, também um MILP, enxerga além da janela e estima o custo de continuar — mas não decide; o plano longo nunca é aplicado. O que ele passa ao MPC é a informação de coordenação: o valor futuro, que entra como custo terminal da janela. O MPC decide o despacho, o sistema elétrico executa, e a decisão seguinte parte do estado realizado, não do planejado.",
    "Coordenação hierárquica e valor futuro": "O MPC só enxerga N intervalos; o que vem depois precisa entrar como custo. Pela relação de Bellman, decidir bem é somar o custo de agora ao custo de continuar a partir do estado final — e, se esse custo for exato, a janela reproduz o ótimo do horizonte completo. A inclinação dessa função é o valor de um kWh guardado, em reais: o mesmo valor da água do SIN, agora para a energia armazenada. Só que no SIN esse valor sai dos duais de problemas lineares; aqui, com decisões inteiras como ligar a célula, a função pode ser não convexa ou descontínua e a derivada pode nem existir. Por isso não usamos os duais do MILP como preço: o planejador constrói essa função por pontos, como mostro adiante.",
    "Controle preditivo baseado em modelo (MPC)": "O futuro só é conhecido por previsões; por isso a decisão é revista a cada intervalo. O MPC resolve uma janela de N intervalos, aplica só o início, atualiza o estado com o que de fato ocorreu e repete. Mas a janela acaba: sem um custo terminal, nada dá valor à energia que sobra, e a otimização tende a gastá-la. O V_f é a peça que falta.",
    "Programação linear inteira mista (MILP)": "As decisões têm duas naturezas: quanto e sim ou não. A célula, por exemplo, ou está desligada ou opera entre 10 e 50 kW — um conjunto que a programação linear não representa, mas uma binária sim. É a mesma ferramenta que o ONS usa no DESSEM para a programação diária.",
    "O MILP da microrrede": "Na nossa microrrede, cada recurso entra no balanço do barramento com as suas variáveis: potências contínuas e, quando há escolha, uma binária. O objetivo soma o custo de importação, o hidrogênio e as partidas e paradas.",
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
