# Defesa de TCC — material de preparação

Material da apresentação da defesa do TCC *SEEDS: Desenvolvimento e Avaliação de um Simulador Modular Expansível com
Gerenciamento Energético Hierárquico Baseado em MILP–MPC* (UNILA, 9/12/2026). Não faz parte da aplicação.

| Arquivo | Conteúdo |
|---|---|
| `ROTEIRO.md` | mapa vigente dos 27 slides (títulos, conteúdo, vínculos) |
| `ROTEIRO_DETALHADO_v1.md` | primeira versão detalhada (falas, justificativas, auxiliares, perguntas prováveis; numeração antiga) |
| `DESIGN.md` | sistema visual: paleta, tipografia, elementos e medidas da capa aprovada, para implementar em PPTX |
| `capa/capa_oficial.html`, `capa/png/capa_oficial.png` | capa **aprovada** |
| `capa/sumario.html`, `capa/png/sumario.png` | sumário **aprovado** (barramento em chevrons, cartões em zigue-zague) com rodapé |
| `capa/gerar_b.py`, `capa/gerar_sumario2.py` | geradores das variações (capa B1–B7; sumário X1–X3, Z1–Z3; Z2 = aprovado) |
| `capa/assets/` | logos (SEEDS, UNILA) e fontes de maquete (Gelasio, Manrope, etc. — licença OFL, Google Fonts) |
| `pptx/SEEDS_Defesa_TCC.pptx`, `pptx/SEEDS_Defesa_TCC.pdf` | deck: capa e sumário nativos; slides 3–7 aprovados (imagem HD, fala nas notas); 8–28 em branco |
| `pptx/deck.py`, `pptx/deck.json`, `pptx/exportar_deck.js` | ordem do deck (36 slides) e exportação do PDF completo + imagens HD |
| `pptx/gerar_pptx.js` | gerador do deck (pptxgenjs; formas nativas e editáveis; fontes Georgia + Calibri) |
| `guia/Guia_Defesa_SEEDS.pdf` | guia completo slide a slide (título, mensagem, tela, motivo, vínculos, fala-guia); fonte em `guia/conteudo.py` |
| `slides/slide03_aprovado.html`, `slides/png/slide03_aprovado.png` | slide 3 (Contexto) **aprovado**; gerador `slides/gerar_slide3_v3.py`; fontes originais em `slides/fonte_*` |
| `slides/slide05_aprovado.html`, `slides/png/slide05_aprovado.png` | slide 5 (Trabalhos relacionados) **aprovado**; gerador `slides/gerar_slide5_v4.py` |
| `slides/slide06_aprovado.html`, `slides/png/slide06_aprovado.png` | slide 6 (Objetivos e contribuições) **aprovado**; gerador `slides/gerar_slide6.py` (`g6_final`) |
| `slides/slide07_aprovado.html`, `slides/png/slide07_aprovado.png` | slide 7 (O SEEDS — proposta e contribuições) **aprovado**; gerador `slides/gerar_slide7_v2.py` (`k3v2`) |
| `slides/slide08_aprovado.*`, `slides/slide09_aprovado.*` | Modelagem dos recursos (deck 10–11) **aprovados**; `slides/gerar_slide8_v2.py` |
| `slides/divisor01…07.*` | separadores de seção **aprovados**; `slides/gerar_divisores.py` |
