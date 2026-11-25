# Sistema visual da defesa — SEEDS

Fonte de verdade para implementar a apresentação em PPTX. Canvas de referência: **1920 × 1080 px** (16:9).
No PowerPoint (13,333 × 7,5 pol.), **1 px = 1/144 pol.** (dividir por 144 para polegadas ou multiplicar por 0,0176 cm).

## 1. Paleta

| Token | Hex | Uso |
|---|---|---|
| navy | `#14213D` | títulos, texto principal, nó Demanda |
| slate | `#4A5568` | texto secundário, rótulos |
| teal | `#1F7A6D` | "Defesa de TCC", linhas tracejadas de conexão, destaques |
| rust | `#C0532F` | acento pontual (alertas, sublinhados curtos) |
| light | `#EEF3F2` | fundos de cartões e painéis |
| line | `#DCE3E2` | divisórias, bordas |
| lime | `#C1FF72` | destaque sobre fundo escuro (slides navy) |
| **Gradiente SEEDS** | `#6DB527` → `#1E8A72` (55 %) → `#0072BA` | barramento, barras de progresso (extraído do logo) |

**Cores dos recursos** (iguais às do aplicativo, para a demonstração parecer contínua):

| Recurso | Hex | Ícone |
|---|---|---|
| Solar | `#D9A21B` | sol |
| Eólica | `#4C8DD6` | turbina |
| PEMFC | `#1BA39C` | "H₂" |
| Bateria | `#7B6CF6` | bateria |
| Rede | `#E0524F` | torre |
| Demanda | `#14213D` | casa |

## 2. Tipografia

| Papel | Fonte (maquete) | Equivalente no PPTX | Peso / tamanho de referência |
|---|---|---|---|
| Títulos e nomes | Gelasio | **Georgia** (métrica compatível, presente em Windows e macOS) | 700; título da capa 62 px ≈ 31 pt |
| "Defesa de TCC" | Gelasio | Georgia | 700, 46 px ≈ 23 pt, teal |
| Subtítulo itálico | Gelasio itálico | Georgia itálico | 400, 24 px ≈ 12 pt, slate |
| Rótulos, dados, data | Manrope | Manrope (instalar/embutir) ou **Segoe UI** | 600, 19–21 px ≈ 10 pt |

Regra: **nada de rótulos em CAIXA ALTA espaçada** (decisão do responsável). Hierarquia por tamanho e peso da serifa.
Conversão: pt = px × 0,5 (canvas de 1920 px em 13,333 pol.).

## 3. Elementos de assinatura

1. **Barramento**: barra arredondada com o gradiente SEEDS (altura 12 px, raio 6 px).
2. **Nós de recurso**: círculo branco r = 36 px, contorno 3 px na cor do recurso, ícone de 40 px dentro;
   haste de 3 px até o barramento, com ponto de junção (r = 7 px, contorno 3 px) e **seta de sentido**:
   fontes injetam (seta para o barramento), Demanda consome (seta saindo), Bateria e Rede bidirecionais (duas setas).
   Rótulo Manrope 600, 19 px, slate, sob o nó.
3. **Conexão tracejada**: linha teal de 2 px, traço de 8 px a cada 14 px. Liga o logo SEEDS ao barramento e o bloco
   "Defesa de TCC" ao barramento. É o elemento que "conecta" partes do slide.
4. **Logo SEEDS** (`capa/assets/seeds.png`, fundo transparente) e versão para fundo escuro (`seeds_dark.png`).
5. **UNILA**: `capa/assets/unila.png` (roxo) e `unila_branco.png`. Resolução baixa (317 px de origem, ampliado):
   **substituir pela versão oficial em alta resolução/vetor antes da versão final.**

## 4. Capa oficial (aprovada) — `capa/capa_oficial.html` · `capa/png/capa_oficial.png`

| Elemento | Posição (px, canto superior esquerdo) | Tamanho |
|---|---|---|
| Logo UNILA | x 110, y 60 | altura 150 |
| Data "Foz do Iguaçu, 9 de dezembro de 2026" | alinhada à direita em x 1810, y 118 | Manrope 600, 21 px, slate |
| Título (com "SEEDS:" no MESMO estilo) | x 110, y 255, largura 1700 | Georgia 700, 62 px, entrelinha 1,15, navy |
| "Defesa de TCC" | x 110, y 615 | Georgia 700, 46 px, teal |
| "Engenharia de Energia · ILATIT" | logo abaixo | Georgia itálico, 24 px, slate |
| Linha tracejada horizontal | x 110 → 956, y 749 | 2 px, teal |
| Autor | x 110, y 775 | Georgia 700, 38 px, navy |
| Orientador / Coorientador | abaixo do autor | Georgia 25 px ("Orientador:" em 600) |
| Logo SEEDS | x 1160, y 548 | largura 460 |
| Tracejado vertical logo → barramento | x 1384, y 700 → 740 | 2 px, teal |
| Barramento | x 960 → 1810, centro y 750 | 12 px, gradiente |
| 6 nós sob o barramento | centros em y 865, espaçados igualmente entre x 960 e 1810 | ver §3 |

Ordem dos nós: Solar · Eólica · PEMFC · Bateria · Rede · Demanda.

## 5. Como regenerar as imagens

```bash
cd docs/defesa_tcc/capa
python3 gerar_b.py                       # escreve B1…B7 (B7_oficial.html = capa_oficial.html)
NODE_PATH=$(npm root -g) node render.js capa_oficial.html   # PNG em png/
```

## 6. Sumário (aprovado) — `capa/sumario.html` · `capa/png/sumario.png`

- Título "Sumário": Georgia 700, 60 px, navy, em x 110, y 78.
- **Barramento em chevrons**: 7 tramos em forma de seta (altura 40 px, ponta de 20 px, folga de 8 px entre tramos),
  de x 110 a 1810, centro em y 545; cada tramo com a cor do gradiente SEEDS na sua posição; ponto branco (r 7) no centro de cada nó.
- **Cartões em zigue-zague**: ímpares (01, 03, 05, 07) acima, pares (02, 04, 06) abaixo; 410 × 250 px, fundo light,
  raio 24 px, borda de 6 px na cor do nó (embaixo nos de cima, em cima nos de baixo). Cartões de cima em y 205; de baixo em y 635.
- **Conector cartão–barramento**: 10 px, na cor do nó.
- Número: Georgia 700, 96 px, na cor do nó. Título: Georgia 700, 34 px, navy, alinhado à base do cartão. **Só o título** (sem descrição, sem ícone).
- **Cartão 05 (Demonstração)**: fundo navy, número lime `#C1FF72`, título branco e marca "● ao vivo" (Manrope 600, 20 px, lime) no canto superior direito.

## 7. Rodapé e número de página (todos os slides de conteúdo)

- Linha fina (1,5 px, `#E6ECEB`) de x 110 a 1810, a 112 px da base.
- Rodapé a 34 px da base: logo UNILA (altura 56) · separador · "Engenharia de Energia · ILATIT" · separador ·
  "**Defesa de TCC** · Bruno Manuel Olmedo Chávez" — Manrope 500, 17 px, `#7B8794` ("Defesa de TCC" em 600, `#5B6675`).
- **Número de página** à direita: Georgia 700, 40 px, navy, com traço de 44 × 5 px do gradiente SEEDS acima.

## 8. Slide 3 — Contexto (aprovado) — `slides/slide03_aprovado.html` · `slides/png/slide03_aprovado.png`

Gerador: `slides/gerar_slide3_v3.py` (variante `S3v3_a`). Estrutura:
- Linha superior: «Redução do custo nivelado da energia (LCOE)», 2010 → 2024 [1] | **−90 %** solar fotovoltaica | **−70 %** eólica terrestre (lado a lado).
- Gráfico de barras empilhadas 2011–2025: eólica (azul `#4C8DD6`) embaixo, solar (âmbar `#D9A21B`) em cima; rótulos de participação na geração total em 2011 (0,5 %), 2018 (8,6 %) e 2025 (26,4 %); nota «2025: 204,6 TWh = eólica 116,5 + solar 88,1 — 60 % da geração solar já ocorre junto à carga (MMGD)».
- Cartão à direita «Cargas pequenas, várias fontes»: fontes convergindo na carga — Residências e comércios (Solar + Rede) [3] · Edificações (Solar + Rede + Bateria) [4] · Localidades isoladas (Eólica + Solar + Célula H₂ + Bateria) [5] · Embarcações (Célula H₂ + Bateria) [6].
- Faixa azul-marinho: «Várias fontes em um mesmo sistema **exigem coordenação.**» (lima).

**Fontes conferidas nos originais (25/11/2026):**
- [1] IRENA, *Renewable Power Generation Costs in 2024*, tabela-resumo: FV 0,417 → 0,043 USD/kWh (−90 %); eólica terrestre 0,113 → 0,034 USD/kWh (−70 %).
- [3] EPE, BEN — Séries Históricas Completas, «Capítulo 5 … 1970 a 2025.xlsx», **Tabela 5.3** (centrais elétricas — total), linhas GWh de geração total, eólica e solar (solar inclui MMGD). Cópia: `slides/fonte_BEN_SeriesHistoricas_Cap5.xlsx`.
- [3] EPE, BEN 2026 — Relatório Síntese, p. 50: MMGD solar = 60,3 % da geração solar em 2025 (`slides/fonte_BEN2026_p50.png`).

## 9. Slide 5 — Trabalhos relacionados (aprovado) — `slides/slide05_aprovado.html` · `slides/png/slide05_aprovado.png`

Gerador: `slides/gerar_slide5_v4.py` (variante `S5v4_E1`; usa `gerar_slide5.py`, `_v2`, `_v3`). Estrutura:
- Três cartões (y 168–652): **EMS MILP–MPC** (x 110, 610 px, fundo light) · **SEEDS** (x 750, 420 px, fundo branco, borda de 5 px com o gradiente SEEDS, sombra) · **Ambientes e simuladores** (x 1200, 610 px).
- EMS em tabela sem grade: glifo esquemático (energia guardada na janela + tratamento no fim) · nome [ref] (Gelasio 21) · limitação (Manrope 18); filetes de 1,5 px; pergunta «E a energia guardada no fim da janela?» (nexo com o slide 4).
- SEEDS: logo (300 px) + faixas «gerenciamento» (azul `#2C6FB0`) e «composição» (verde `#2E9E6B`) que nascem nas bordas dos cartões vizinhos e se unem num nó com o gradiente; «integrados em uma mesma plataforma».
- Simuladores: barramento centrado com recursos (eólica e H₂ tracejados = entram e saem) e duas colunas com divisor.
- Ponto forte de cada lado (ícone colorido) e limitação no pé (cinza `#9AA5B1`), à mesma altura nos dois cartões.
- Tracejado teal do SEEDS para «A lacuna: não se identificou uma abordagem que reunisse» + três partes com círculos G1/G2/G3.

## 10. Slide 6 — Objetivos e contribuições (aprovado) — `slides/slide06_aprovado.html` · `slides/png/slide06_aprovado.png`

Gerador: `slides/gerar_slide6.py`, função `g6_final` (as propostas G1–G4 e H1/H2 ficam no mesmo arquivo).
- «Objetivo geral» (Gelasio 700, 26 px, teal) e o texto do artigo em Gelasio 700, 33 px, navy, largura 1700; filete de 5 px com o gradiente SEEDS em y 384.
- Cartão navy (x 110, y 420, 640 × 482, raio 28) só com a pergunta (Gelasio 700, 40 px, branco; trechos-chave em lima `#C1FF72`), centrada na vertical.
- «Objetivos específicos» (Gelasio 700, 28 px) + 4 linhas (passo 105 px) entre filetes: caixa vazia 40 px (contorno teal), número 0N (Gelasio 40; verde `#2E9E6B` para composição, azul `#2C6FB0` para o EMS, teal no 03), texto Gelasio 700, 26 px.
