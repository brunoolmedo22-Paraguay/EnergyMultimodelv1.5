# Como continuar a preparação da defesa (passagem de sessão)

Branch: `claude/dazzling-bohr-5d0121` · pasta `docs/defesa_tcc/`.

## Estado
- Aprovados: capa (`capa/capa_oficial.html`), sumário (`capa/sumario.html`), slide 3 (`slides/slide03_aprovado.html`, gerador `slides/gerar_slide3_v3.py`), slide 4 (`slides/slide04_aprovado.html`, gerador `slides/gerar_slide4_v6.py`, variante H1), slide 5 (`slides/slide05_aprovado.html`, gerador `slides/gerar_slide5_v4.py`, variante E1), slide 6 (`slides/slide06_aprovado.html`, gerador `slides/gerar_slide6.py`, função `g6_final`).
- Slide 6 — validar com o orientador a redação da pergunta guia e dos objetivos específicos (derivados do artigo); o objetivo geral é o texto do artigo.
- Slide 5 — conferir no PDF do artigo: frase exata da lacuna, números de referência de PyPSA/oemof/Calliope/ETHOS.FINE e a divisão dos simuladores em dois grupos.
- PPTX/PDF (`pptx/`) só tem capa + sumário; slides 3–6 ainda não foram passados ao PPTX (fazer depois, em lote).
- Guia em PDF: `guia/Guia_Defesa_SEEDS.pdf` (fonte `guia/conteudo.py`). Mapa: `ROTEIRO.md`. Sistema visual: `DESIGN.md`.
- Próximo: slide 7 «Modelagem dos recursos energéticos», depois 8…27 (ver `ROTEIRO.md`).

## Como renderizar
`cd docs/defesa_tcc/slides && python3 gerar_slideN.py && NODE_PATH=$(npm root -g) node render.js ARQ.html` → `png/`. Canvas 1920×1080, fontes em `capa/assets/fonts.css`.

## Preferências do responsável (seguir à risca)
- Visual, pouco texto; inovar mantendo a identidade (Gelasio títulos, Manrope texto, navy #14213D, teal #1F7A6D, gradiente SEEDS #6DB527→#1E8A72→#0072BA, cores dos recursos do app, rodapé UNILA + número grande).
- Nada de ícones decorativos em listas de texto nem de rótulos que digam o óbvio (ex.: «?» sobre a pergunta, «respondida nas conclusões»).
- NÃO parecer IA: nada de kicker em CAIXA ALTA + título + subtítulo empilhados; nada de faixa azul de resumo em todo slide; nada de rótulos óbvios («SISTEMA INTERLIGADO NACIONAL» em card). Um título humano por bloco.
- Gráficos bonitos (áreas suaves, rótulos nas curvas); evitar desenhos tipo Paint.
- Sempre mostrar 2–4 propostas lado a lado; iterar com feedback; dados só de fontes conferidas (citar; marcar «esquemático» quando for).
- Valorizar o trabalho (tom de venda, limitações suaves).
- Conversa em espanhol/portunhol; slides em português.
