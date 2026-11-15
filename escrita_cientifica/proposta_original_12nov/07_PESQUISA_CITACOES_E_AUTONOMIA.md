# Literatura, citações, rastreabilidade e liberdade intelectual de Claude

## Posição expressa do autor

A pesquisa bibliográfica da Work oferece um **acervo inicial**, não um índice de citações obrigatórias. Claude **pode e deve** buscar, ler, comparar e selecionar outras referências, inclusive trabalhos mais recentes, diretamente em editoras e bases científicas acessíveis, e substituir referências fracas por outras melhores.

**Não impor:** «citar a referência X no parágrafo Y», «usar apenas as 121 referências» ou «usar todas as fontes da Work». Isso prejudica a função intelectual do assistente de escrita.

**Exigir:** selecionar a melhor sustentação disponível para cada argumento relevante, distinguindo literatura de antecedentes, fundamentos dos modelos, fontes metodológicas, implementações tecnológicas e trabalhos de software científico.

## O que a biblioteca de Work representa

A entrega recebida em 12/11/2026 inclui relatórios, matrizes, referências bibliográficas estruturadas, fichas críticas e mapeamentos de código–literatura. Work declarou, na síntese revista, centenas de registros descobertos e mais de uma centena de referências selecionadas, com níveis diferentes de leitura (texto completo, resumo, metadados).

**Advertência:** estar na biblioteca não significa que a referência tenha sido lida integralmente nem que sustente uma determinada afirmação. Conferir toda citação antes de inserir no manuscrito. As limitações de acesso a bases como Scopus, Web of Science e Google Scholar precisam ser consideradas quando se falar em abrangência da revisão.

## Classes de referência a buscar

### A. Plataforma e arquitetura científica

Plataformas reconfiguráveis de energia/microrredes, frameworks abertos, modelagem multi-recurso, composição de equipamentos, qualidade do software científico, gestão de cenários, rastreabilidade e reprodutibilidade. Comparar **capacidades documentadas** e modelos de execução.

### B. Estratégias de despacho e otimização

Formulações MILP, MPC, hierarquia temporal, planejamento de longo prazo, valor futuro/terminal da energia, estados intertemporais, incerteza de geração e carga, restrições causais de operação. Distinguir métodos que só tenham nomes semelhantes daqueles que implementam o mesmo mecanismo matemático.

### C. Modelagem de componentes

Fontes originais/primárias dos modelos de FV (irradiância, térmico, SDM), eólica, bateria (Tremblay–Dessaint/Shepherd, 2RC ou outras variantes efetivas), PEMFC/H₂, térmica e equipamentos. Uma referência teórica não prova identidade com os parâmetros ou o código executado.

### D. Ferramentas e dados

Python, Streamlit, bibliotecas do solver, bases de perfis de carga, fontes meteorológicas, dados tarifários oficiais e documentação técnica específica quando pertinente. Citar fontes oficiais para padrões e parâmetros, e literatura primária para mecanismos físicos/matemáticos.

### E. Trabalhos próximos e contrapontos

Dar atenção especial às pesquisas com **plataformas modulares e EMS hierárquico**, incluindo recursos PEMFC, baterias, microrredes conectadas e sistemas embarcados. O objetivo é diferenciar o SEEDS2 com precisão, não evitar trabalhos semelhantes nem inferir que ninguém fez algo próximo.

## Contrato de checagem por citação

Para cada referência efetivamente usada, idealmente registrar:

- Autor(es), ano, título, periódico/editora e identificador persistente.
- DOI/URL de fonte oficial e acesso permitido.
- Qual parte do texto é sustentada e em que trecho da fonte.
- Nível de acesso: texto completo, resumo ou somente metadados.
- Se é fonte primária do método, aplicação derivada, revisão, fonte oficial, software ou documentação.
- Possíveis diferenças entre o que o artigo original propõe e o que SEEDS2 implementa.

Uma citação de revisão não substitui o artigo original quando se está atribuindo uma equação a seu autor. Não citar um resumo como se o texto completo tivesse sido consultado.

## Rastreamento de equações e código

Ao redigir a seção 4, construir uma matriz entre:

`EQUAÇÃO NO ARTIGO ↔ VARIÁVEIS E UNIDADES ↔ FUNÇÃO/ARQUIVO/COMMIT ↔ TESTE/RESULTADO ↔ FONTE TÉCNICA`.

Se não houver fonte para uma formulação própria, descrevê-la como decisão de modelagem da implementação, sustentando os fundamentos conhecidos sem atribuir autoria alheia. Evitar a palavra «validado» quando só há teste de integridade, verificação de cálculo ou comparação com literatura teórica.

## Liberdade e limites de Claude

**Liberdade:** escolher fontes, construir a progressão dos parágrafos, sugerir subtítulos, propor diagramas, identificar lacunas, criticar a arquitetura documentada e recomendar experimentos de controle.

**Limites:** as sete seções principais, as duas contribuições e os dois estudos de caso são decisões de autor; seus nomes podem ser refinados linguisticamente sem alterar a organização científica. Não inventar resultados, funcionalidades, comparações, referências, parâmetros ou validações. Mudanças de escopo devem ser propostas e submetidas à decisão do autor, não inseridas silenciosamente.

## Entregas bibliográficas durante a redação

- BibTeX limpo com DOI e chaves estáveis.
- Registro da alegação sustentada por cada fonte e acesso obtido.
- Lista de pontos com suporte insuficiente, para pesquisa ou revisão de redação.
- Síntese comparativa de antecedentes relevantes, com diferenças verificáveis.
- Documentação de referências novas acrescentadas além do acervo Work.
