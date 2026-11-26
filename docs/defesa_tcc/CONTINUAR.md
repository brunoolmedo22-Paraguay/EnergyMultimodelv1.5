# Como continuar a preparação da defesa (passagem de sessão)

Branch: `claude/dazzling-bohr-5d0121` · pasta `docs/defesa_tcc/`. Defesa de TCC (SEEDS, UNILA) em **9/12/2026**, 30 min.

## Estado (26/11/2026)
- **Deck: 38 slides**, ordem única em `pptx/deck.py` (→ `deck.json`). Tabela vigente: `ROTEIRO.md` § «Ordem do deck».
- **Aprovados (38 — deck completo):** 1 capa · 2 sumário · 3 separador 01 · 4 Contexto · 5 Decisões com consequências futuras · 6 Trabalhos relacionados ·
  7 Objetivos · 8 O SEEDS · 9 separador 02 · 10–11 Modelagem dos recursos (3 + 2) · 12 Por que MILP · 13 O MILP da microrrede · 14 MPC · 15 Coordenação hierárquica e valor futuro · 16 Gerenciamento energético hierárquico MILP–MPC (Fig. 4.1) · 18 Arquitetura do SEEDS (Fig. 5.1) · 19 Representação energética comum · 20 EMS hierárquico no SEEDS (Fig. 5.2) · 21 Verificação e fluxo de execução (Fig. 5.3) · 23 Estratégia de avaliação ·
  24 Dados de entrada CT-046 · 25 Configuração CT-046 · 26 Dados de entrada EMB-H2-120 · 27 Configuração EMB-H2-120 · 29 Demonstração — acesso ao aplicativo (QR) · 31 Resultados — operação do armazenamento · 32 Resultados — custos C1–C4 · 33 Resultados — embarcação C5 × C6 · 34 Expansibilidade e desempenho · 36 Conclusões · 37 Trabalhos futuros · 38 Agradecimentos ·
  separadores 03–07 (17, 22, 28, 30, 36).
- **Slide «papel do armazenamento (C4, C5 e C6)» REMOVIDO** (decisão do responsável): a comparação entre os dois
  estudos ("na microrrede industrial observamos… / na embarcação observamos…") abre as CONCLUSÕES. **Deck COMPLETO (38/38), aprovado pelo responsável (26/11/2026).** Próximo (pedido do responsável): **slide(s) de
  referências** e, depois, **slides auxiliares** para a arguição (base: `ROTEIRO_DETALHADO_v1.md`, A1–A15); depois revisão geral e ensaio; depois 34 papel do armazenamento (C4 × C6),
  35 expansibilidade e desempenho (+ curva PWL da PEMFC; conferir 500 × 402 pontos), encerramento 37–39.
  Seção de resultados (plano aprovado): 31 operação do armazenamento (+ coordenação: «decide antes de ver a ponta»), 32 custos
  (+ «o plano se cumpre» 865,02 × 865,03), 33 C5, 34 C4 × C6, 35 apoio. **Gráficos com o MOTOR GRÁFICO DO SEEDS**: marcos das
  rodadas por `slides/seeds_fig/marco.py` (exemplos, diretório temporário, evidência verificada) e figuras por
  `slides/seeds_fig/extrair.py` (JS/CSS reais da Partitura; opção `ordem_artigo` = empilhamento da Fig. 7.1: rede, solar, bateria).
  Cartões no estilo `.pt .card` (fundo #f4f4f2 sobre #e6e6e4, filete de cor, números em Archivo; fontes em `slides/assets/fonts_seeds`).
  Rodada de C6 REPRODUZIDA no SEEDS por `slides/seeds_fig/rodar_c6.py` (venv com pyomo/highspy no scratchpad; idêntica ao artigo: 4,163 kg, 60,00 kWh, fim em 15,00 kWh). Rodar com PYTHONDONTWRITEBYTECODE=1 (senão regenera os __pycache__ versionados).
- Geradores aprovados: `slides/gerar_slide3_v3.py`, `gerar_slide4_v6.py` (H1), `gerar_slide5_v4.py` (E1), `gerar_slide6.py` (`g6_final`),
  `gerar_slide7_v2.py` (`k3v2`), `gerar_slide8_v2.py` (modelagem), `gerar_slide12_v2.py` (MILP A e B), `gerar_slide14.py` (`p1`), `gerar_slide15.py` (`p1`), `gerar_slide16.py` (`h4`), `gerar_slide18.py`, `gerar_slide19.py` (`p1`), `gerar_slide20.py`, `gerar_slide21.py`, `gerar_slide23_v2.py` (`d`; ilustrações em `slides/assets/ilus_*.png`, fornecidas pelo responsável), `gerar_slide24_27_v2.py` (`e2b` e `k1b`; usa `gerar_slide24_27.py` e `gerar_slide24_25.py`), `gerar_slide29.py` (`b`), `gerar_slide31c.py`, `gerar_slide32c.py` (estilo do deck: o responsável preferiu, no 32, NÃO usar o visual do app), `gerar_slide33b.py` (despachos COM o visual do SEEDS), `gerar_slide34.py`, `gerar_slide36.py`, `gerar_slide37.py`, `gerar_slide38.py`,
  `gerar_divisores.py` (V1). Cópias congeladas: `slides/slideNN_aprovado.html` (numeração antiga no nome) e `slides/divisor0N.html`.

## Fontes
- **Artigo final do TCC: NÃO está no repositório** (texto extraído só na sessão) — pedir ao responsável o PDF (`TCC_BRUNO_OLMEDO_COMPLETO_1.pdf`, 56 p.) e lê-lo antes
  de qualquer slide técnico. Seções: 3 modelos (eq. 1–8) · 4.1 MILP (eq. 9–13) · 4.2 longo horizonte (eq. 14) · 4.3 MPC (eq. 15) ·
  4.4 hierarquia e valor futuro (eq. 16–18) · 5 SEEDS (Fig. 5.1–5.3) · 6 estudos (Tab. 6.1–6.3) · 7 resultados (Tab. 7.1–7.2, Fig. 7.1–7.5) ·
  Anexo A = 13 capturas do aplicativo.
- Código confere o artigo (resumo em `PLANO_BLOCO_II.md`). Divergência CONFIRMADA: o artigo diz 500 pontos de validação da curva H₂; a rodada gravada (C5) registra 402 (o slide 34 usa 402). Corrigir o artigo.
- Números/dados SÓ do artigo ou de fonte conferida; marcar «esquemático/ilustrativo» quando não for dado real.

## Pendências registradas
- `AUDITORIA_BLOCO_I.md`: slide 4 (Contexto) «Edificações» deve ser **Bateria + H₂** [4] (o artigo diz «edificações que combinam baterias e
  armazenamento de hidrogênio»); slide 6 (Trabalhos relacionados): PyPSA, oemof, Calliope, ETHOS.FINE = **[23–26]**; pymgrid [27] é «modelos
  simplificados» (HOMER = «estratégias predefinidas»); lacuna: falta «energético» («sob um mesmo gerenciamento **energético** hierárquico»).
  Correções ainda NÃO aplicadas (perguntar antes).
- Validar com o orientador: redação da pergunta guia e dos objetivos específicos (slide 7).
- Confirmar no PDF de [10] (Santos et al., DESSEM) a frase de que o DESSEM é MILP (conferido só por busca).
- Tempo: separadores (~35 s) consumiram a margem; recortar ao ensaiar. Guia (`guia/`) ainda na numeração antiga de 28 slides.
- Subdivisões dos separadores 04 e 05 foram redigidas a partir do roteiro (ajustáveis em `gerar_divisores.py`, SUB).

## Como trabalhar (o fluxo que funcionou)
1. Ler o artigo e o código da seção; dizer em 3–5 linhas o que o slide deve transmitir (o **por quê** e o **como**; a banca já conhece a técnica:
   é preciso **defender** a escolha).
2. Gerar **3 propostas diferentes** (gerador Python em `slides/gerar_slideNN.py` → HTML 1920×1080 → PNG), revisar cada PNG (sobreposições,
   texto cortado, tamanhos), montar a folha lado a lado (`png/SNN_opcoes.png`), commit + push e enviar as imagens.
3. O responsável escolhe uma e pede ajustes; iterar no mesmo gerador.
4. Ao aprovar: copiar para `slides/slideNN_aprovado.html`, pôr o html em `pptx/deck.py` (+ fala em NOTA_EXTRA), rodar a exportação (abaixo),
   atualizar `ROTEIRO.md` (§ Ordem do deck), `CONTINUAR.md` e `DESIGN.md`, commit + push e entregar PDF + PPTX.

## Ambiente (instalar numa sessão nova)
- Playwright/Chromium já vêm instalados (`NODE_PATH=$(npm root -g)`).
- Numa pasta de trabalho fora do repositório: `npm install pptxgenjs sharp mathjax-full@3.2.2` e exportar `SEEDS_NODE_MODULES=<essa pasta>/node_modules`
  (usado por `slides/tex2svg.js` via `gerar_slide8.py` → constante `NM`; ajustar `NM` se o caminho mudar).
- Skill pptx: `apply_theme.js` e `office/validate.py` do skill `anthropic-skills:pptx`.

## Como renderizar e exportar
- Um slide: `cd docs/defesa_tcc/slides && PYTHONDONTWRITEBYTECODE=1 python3 gerar_slideN.py && NODE_PATH=$(npm root -g) node render.js ARQ.html` → `png/`.
- Deck inteiro: `cd docs/defesa_tcc/pptx && python3 deck.py && NODE_PATH=$(npm root -g) node exportar_deck.js` (→ `img_hd/deckNN.png` 3840×2160 +
  `SEEDS_Defesa_TCC.pdf`; o número de página é trocado pelo do deck) e depois
  `NODE_PATH=<node_modules com pptxgenjs> node gerar_pptx.js <skill pptx>/scripts/apply_theme.js` + `validate.py` → `SEEDS_Defesa_TCC.pptx`
  (capa e sumário nativos; aprovados como imagem HD com a fala nas notas; não desenhados = provisórios editáveis).
- Equações: LaTeX → SVG por `slides/tex2svg.js` (chaves `i_…` = inline). Cor dentro do TeX: `{\color{#1F7A6D}{v}}`.
- Separadores: `slides/gerar_divisores.py` (não importar `capa/gerar_sumario2.py` direto: ele regrava maquetas em `capa/`).

## Preferências do responsável (seguir à risca)
- Visual, pouco texto, **texto grande** (corpo ≥ 22 px nos cartões); inovar mantendo a identidade: Gelasio títulos, Manrope texto, navy #14213D,
  teal #1F7A6D, gradiente SEEDS #6DB527→#1E8A72→#0072BA, cores dos recursos do app (Solar #D9A21B, Eólica #4C8DD6, PEMFC #1BA39C,
  Bateria #7B6CF6, Rede #E0524F), rodapé UNILA + número grande. Contínuas teal × binárias #C0532F; custo futuro #C0532F.
- Motivo recorrente: **barramento SEEDS** com recursos pendurados (círculo + haste com seta) e cartões claros (#EEF3F2, raio 24).
- NÃO parecer IA: nada de kicker em CAIXA ALTA + título + subtítulo; nada de faixa azul de resumo; nada de rótulos óbvios; nada de ícones
  decorativos em listas de texto (ele pediu explicitamente para tirar). Um título humano por bloco. Frases começam com maiúscula.
- Figuras do artigo (Fig. 4.1, 5.1…): reproduzir IDÊNTICAS (mesmos blocos/textos/cores), só em horizontal, + 3 pontos em colunas embaixo.
- Ilustrações figurativas: NÃO desenhar à mão em SVG (o responsável recusou); usar imagens fornecidas por ele.
- Equações sempre em LaTeX, numeradas como no artigo; unidades só dos resultados (não de cada variável), salvo quando ele pedir.
- Resultados (números de desempenho) não entram em slides de fundamentação — vão para o bloco de resultados.
- Gráficos bonitos (áreas suaves, rótulos nas curvas); nada de desenho tipo Paint; tudo centrado e bem distribuído nos cartões.
- Sempre 3 propostas diferentes lado a lado; iterar com feedback; dados só de fontes conferidas (citar; «esquemático» quando for).
- Valorizar o trabalho (tom de defesa, limitações suaves). Conversa em espanhol/portunhol; slides em português.
- Commit + push na mesma branch a cada passo; não abrir PR.
- **NÃO enviar PDF/PPTX a cada slide aprovado** (gasta tokens): só registrar no deck.py/docs; exportar e entregar o deck apenas quando o responsável pedir.

- Seção 07 renomeada (pedido do responsável): «Conclusões e trabalhos futuros» (sumário `capa/sumario.html`, separador, deck.py, gerar_pptx.js); o slide 37 chama-se «Trabalhos futuros».
