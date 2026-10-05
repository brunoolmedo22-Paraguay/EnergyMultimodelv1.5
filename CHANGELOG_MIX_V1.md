# MIX V1

- Adicionado sexto recurso na tela inicial: `MIX`.
- Novo fluxo em cinco páginas: Explicação, Configuração de fontes, Entrada de dados, Resultados e Exportação.
- Seleção independente de Solar, Eólica, Térmica, Bateria e H₂.
- Solar fixado no modelo NOCT + eficiência corrigida por temperatura.
- Solar e Eólica operam sempre na potência disponível calculada; o MIX apenas sinaliza excedente/curtailment.
- CSV operacional é a timeline mestre; clima é interpolado para os timestamps operacionais.
- Térmica, Bateria e H₂ recebem consignas individuais do otimizador.
- Bateria mantém os modelos Tremblay–Dessaint e 2RC; camada MIX converte consigna de potência em corrente sem alterar o modelo físico.
- Demanda total é opcional/recomendada: quando disponível, calcula balanço, excedente, déficit, curtailment e oportunidade de carga da bateria.
- Exportação configurável por coluna, com preset essencial sugerido e opção de todas as colunas.
- Incluídos CSVs de exemplo separados para operação e clima.
