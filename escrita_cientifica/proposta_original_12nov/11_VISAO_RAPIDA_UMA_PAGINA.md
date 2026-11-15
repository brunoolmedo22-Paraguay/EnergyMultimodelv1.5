# SEEDS2 — Visão de uma página para iniciar qualquer sessão de escrita

**Título de trabalho:** *SEEDS2: Desenvolvimento e Avaliação de uma Plataforma Modular para Simulação Operacional e Otimização do Despacho Energético em Microrredes por Meio de um EMS Hierárquico Baseado em MILP–MPC*.

**SEEDS = Smart Energy Ecosystem for Decision Support.** SEEDS2 é uma plataforma científica de **apoio à tomada de decisão**, não um sistema apresentado como controlador físico autônomo.

**Ideia científica:** possibilitar ao pesquisador configurar e executar diferentes arranjos energéticos, com modelos e restrições, e examinar a operação e o despacho resultantes. A filosofia de projeto é a de uma **bancada virtual reconfigurável** em contraste com um único otimizador fixo para uma única configuração.

**Duas contribuições com peso igual:**

1. **Plataforma:** modularidade, modelos físicos e operacionais, catálogos, criação e execução de cenários, visualização, comparação e rastreabilidade.
2. **EMS hierárquico:** otimização matemática MILP–MPC, curto e longo prazo, estados, limites, transferência de informações e valor futuro **aproximado** da energia.

**Sete seções:**

1. Introdução — problema concreto, literatura relevante, motivação, objetivo e contribuições.
2. Fundamentação teórica e trabalhos relacionados — plataformas, modelos e EMS, com comparação crítica.
3. Arquitetura e desenvolvimento da plataforma SEEDS2 — composição e dinâmica do ambiente científico.
4. Modelagem matemática e sistema de gerenciamento energético hierárquico — formulação e operação do EMS.
5. Metodologia de avaliação e estudos de caso — experimento computacional hipotético, condições e métricas.
6. Resultados e discussão — 6.1 plataforma/consistência; 6.2 industrial C1–C4; 6.3 embarcação; 6.4 síntese/limites.
7. Conclusões e trabalhos futuros — respostas verificadas às duas contribuições, limites e continuidade.

**Estudo I (mais extenso):** uma microrrede industrial hipotética conectada à COPEL, com quatro configurações comparadas por fenômenos: **C1 rede**, **C2 rede+FV**, **C3 rede+bateria**, **C4 rede+FV+bateria**. Não são quatro estudos separados. Não confundir efeito da mudança de tecnologia com efeito do EMS; estratégias devem ser comparadas na mesma composição física.

**Estudo II:** embarcação **Boto H₂** isolada, com PEMFC/H₂, FV, bateria e perfil de carga. Examinar repartição do despacho, SOC, decisões operacionais, limites e consumo de H₂. **H₂ não limitante durante a janela**. Não estudar autonomia, alcance, quilometragem ou esgotamento de tanque.

**Tipo de evidência:** simulação e avaliação de funcionamento em condições hipotéticas, **não validação experimental física integrada**. Verificações matemáticas, balanças, limites, factibilidade e repetibilidade continuam essenciais.

**Redação:** português brasileiro, impessoal, estilo progressivo e orgânico (ZIP de identidade autoral v1.0). Resultados: **primeiro número/observação, depois explicação física e implicação**. Artigo conciso e autossuficiente.

**Bibliografia:** ZIP Work é base inicial. Claude pode consultar novas publicações e selecionar melhores referências, sem lista fechada ou atribuição compulsória de citações. É proibido inventar referências, código ou resultados.

**Publicação:** primeiro TCC em português; possível adaptação posterior ao inglês. LaTeX/Overleaf `elsarticle` `3p` como estilo visual de trabalho, condicionado às regras editoriais específicas.

**Estado atual:** roteiro aprovado. **Resultados, parâmetros definitivos e versão final do código ainda exigem conferência.** Este documento NÃO autoriza inventar dados nem começar a redação final sem pedido do autor.
