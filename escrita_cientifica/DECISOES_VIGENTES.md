# Decisões científicas vigentes — 15/11/2026

## Título definitivo
**SEEDS2: Desenvolvimento e Avaliação de um Simulador Modular de Microrredes com Gerenciamento Energético Hierárquico Baseado em MILP–MPC**

SEEDS significa *Smart Energy Ecosystem for Decision Support*. Não discutir o significado histórico do número 2 nem plataformas anteriores.

## Delimitação
Duas contribuições com peso equivalente: simulador modular e reconfigurável e EMS V2 hierárquico MILP–MPC. Não prometer plug-and-play irrestrito, operação autônoma de equipamento real ou validação experimental física.

**Exclusão expressa:** o otimizador legado V1.6, associado ao desenvolvimento anterior de Marília, é paralelo e **não integra o artigo**, a formulação científica, os fluxogramas nem os resultados. Pode ser inspecionado apenas para verificar interferência técnica com V2.

## Estrutura acordada com o orientador
- Resumo e palavras-chave
- 1. Introdução
- 2. Revisão bibliográfica
- 3. Embasamento teórico
  - 3.1 Modelagem fotovoltaica
  - 3.2 Modelagem eólica
  - 3.3 Modelagem do armazenamento em baterias
  - 3.4 Modelagem da célula a combustível PEMFC
  - 3.5 Fundamentos de otimização MILP
  - 3.6 Controle preditivo baseado em modelo (MPC)
  - 3.7 Coordenação hierárquica e planejamento energético
- 4. Método de avaliação — título atualizado pelo autor no Google Docs em 15/11; detalhamento pendente de auditoria e alinhamento metodológico
- 5. Resultados e discussão
- 6. Conclusões
- Referências

A introdução vai do macro ao específico, apresenta problema, objetivo e contribuições sem excesso de números. A revisão bibliográfica discute trabalhos e lacunas reais; o embasamento teórico apresenta conceitos e fórmulas com fontes verificadas. A explicação dos fluxos reais de arquitetura e EMS deverá ser situada coerentemente no método, após a auditoria. Resultados devem interpretar mecanismos e limites, não narrar gráficos.

## Estudos
Estudo industrial conectado à rede com configurações C1–C4 (rede; rede+FV; rede+bateria; rede+FV+bateria) e tarifa temporal. Estudo de embarcação híbrida isolada C5 com PEMFC, FV e bateria. Verificar logs antes de atribuir causalidade ao comportamento observado. Comparar C1–C4 não comprova isoladamente a superioridade da hierarquia.

## Referências
Citar, quando pertinente e após verificação bibliográfica, o trabalho próprio sobre PEMFC apresentado no ENCOM 2026: DOI 10.5281/zenodo.22978126. Bibliografia histórica e matriz de referências são insumos, não evidência automaticamente validada.

## Estado de validação
A auditoria final de Claude e os fluxos operacionais detalhados estão pendentes. Não tratar notas preliminares como achados definitivos.

## Regra de tempo verbal para o Resumo (15/11/2026)
Por decisão expressa do autor, redigir o **Resumo** predominantemente no **pretérito**, em voz impessoal, apresentando o trabalho como realizado: «foi desenvolvido», «foram considerados», «adotou-se», «avaliou-se», «foram analisados». Não redigir a metodologia ou as ações realizadas como proposta futura. Afirmações científicas gerais podem permanecer no presente quando gramaticalmente apropriado. Não inventar resultados nem antecipar conclusões pendentes de auditoria.
