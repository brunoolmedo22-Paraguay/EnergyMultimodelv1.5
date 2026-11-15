# Contribuição I — Arquitetura modular, modelagem e dinâmica da plataforma

## Tese desta contribuição

A arquitetura do SEEDS2 deve permitir a um pesquisador **compor uma microrrede a partir de seus recursos, dados, parâmetros e objetivos de observação**, sem que toda investigação dependa de um sistema predeterminado. A plataforma deve conectar configuração, simulação operacional, gerenciamento energético, observação, comparação e registro de resultados.

A publicação deve demonstrar **a utilidade científica da composição e da execução**, em vez de tentar provar valor com uma lista de telas ou pela complexidade do código.

## Perguntas que a seção de arquitetura deve responder

- Qual é a estrutura geral e quais as responsabilidades de cada módulo?
- Como o sistema representa a identidade de uma microrrede e seus equipamentos?
- Como os modelos físicos são configurados por catálogos ou parâmetros?
- Como dados meteorológicos, carga e outras séries passam pela validação e sincronização temporal?
- Como um cenário se transforma em uma execução do modelo e do EMS?
- Que dados resultam da execução, como são comparados e como se mantém sua procedência?
- O que muda na configuração tecnológica e o que permanece comum no ambiente de análise?
- Quais funcionalidades são **efetivamente disponibilizadas pelo commit auditado**?

## Filosofia da bancada virtual configurável

**Não é uma analogia publicitária:** é uma forma de explicar decisões de arquitetura. Um estudo com único conjunto fixo de equipamentos pode analisar bem aquele sistema, mas não demonstra automaticamente um ambiente capaz de variar a composição tecnológica. SEEDS2 procura tornar a composição da bancada um ato do pesquisador, mantendo o vínculo entre modelos, condições de operação e resultados.

Não basta afirmar «plug-and-play». Deve-se precisar o que significa no SEEDS2: seleção e parametrização de recursos, contratos de entrada, compatibilidade de unidades/tempos, montagem de envelopes ou estado do sistema, execução e inspeção. Se um recurso exigir integração manual ou estiver apenas previsto, isso deve ser descrito corretamente, sem «plug-and-play» absoluto.

## Inventário de famílias tecnológicas a conferir no código

O repositório histórico documenta famílias de modelos que **não devem ser confundidas com garantia de que todas estão integradas ao EMS no mesmo nível**:

| Família | Elementos conhecidos pelo histórico do projeto | O que Claude deve verificar |
|---|---|---|
| Solar FV | Modelo baseado em irradiância, correção térmica/NOCT e modelo de um diodo (SDM) em bancadas anteriores | Quais variantes permanecem no sistema atual e quais variáveis são levadas ao despacho |
| Eólica | Curvas de potência, condições atmosféricas e rendimento/energia | Qual curva e contrato são efetivamente usados nas simulações/EMS |
| Bateria | Modelos físico-elétricos como Tremblay–Dessaint/Shepherd e circuito equivalente 2RC; envoltória de energia/SOC no despacho | Diferenciar modelo de bancada, modelo para execução e abstração MILP |
| PEMFC / H₂ | Modelo equivalente com dinâmica, auxiliares, potência requerida, eficiência e consumo de H₂ | Conferir referência originária exata, equações, parametrização, limites, estados e interface com EMS |
| Térmica | Modelos operacionais/econômicos de fontes despacháveis | Qual tratamento de custos, acionamento, potência e limites está implementado |
| Rede/PCC | Importação, limites contratuais, eventual exportação e tarifas | Conferir convenção de sinais, restrições, custos e hipóteses de cada estudo |
| Carga | Perfis temporais e demandas da instalação/embarcação | Origem, resolução temporal, unidades e como são tratados eventuais déficits |

**O nome «Otekon» apareceu na discussão oral anterior sobre PEMFC.** Não fixar esse nome, autores, DOI ou formulação sem checar o trabalho original e o código. Se a referência fundamenta apenas uma parte do modelo, atribuí-la apenas àquela parte. A biblioteca de Work e o estudo próprio em Zenodo devem ser confrontados com a implementação atual.

**Atenção:** modelos físicos de bancada podem usar discretizações e estados mais detalhados do que a representação linear/mista adotada pelo EMS. Essa distinção é científica, não defeito: precisa ser explicitada e justificada conforme as aproximações realmente utilizadas.

## Componentes de arquitetura que merecem investigação

### 1. Composição e gestão de microrredes

Explorar a lógica do Gestor de Microrredes, catálogo de equipamentos e vínculo entre configuração e cenário. Investigar se há funções de adicionar, duplicar, renomear, versionar ou excluir sistemas, e quais dados persistem. Só narrar como disponível o que os testes e a revisão do commit comprovarem.

### 2. Catálogos e parâmetros

Descrever o papel dos catálogos na seleção de tecnologias e sua parametrização, incluindo coerência de unidades, limites e proveniência dos dados técnicos. Distinguir dispositivo comercial parametrizado de equivalente genérico, hipótese de desempenho e dados de ensaio.

### 3. Fluxos e contratos temporais

Explicar, se implementados: série de carga, previsão solar/eólica, temperatura, resolução temporal, fuso horário, alinhamento dos índices e agregação/desagregação. Uma boa interface não dispensa consistência temporal dos cálculos.

### 4. Execução de cenários e registros

Descrever o encadeamento entre dados, simulador, solver/EMS e relatórios. Se existirem Caderno de Ensaios, Folha de Ensaio, histórico SQLite e assinatura da execução, investigar seu comportamento real. O valor científico está em reproduzir a mesma execução e reconhecer o que mudou entre ensaios.

### 5. Visualização e avaliação

O artigo deve demonstrar como resultados reais são apresentados, por exemplo despachos, balanços, SOC, consumo de combustível e custos modelados. Prints podem ser secundários; gráficos exportados do experimento são evidências centrais.

### 6. Ambiente tecnológico

Python e Streamlit são escolhas de implementação e podem ser contextualizadas com fontes oficiais ou literatura de software científico. Não atribuir inovação científica a uma linguagem ou framework por si só. Apresentar bibliotecas/solver específicos apenas após conferir versões e funções do commit congelado.

## Diagrama científico opcional

Um diagrama de uma página deve mostrar aproximadamente:

**Definição da microrrede + catálogos** → **cenários/séries** → **modelos e restrições** → **EMS hierárquico** → **simulação/execução** → **resultados, comparação e registro**.

O desenho final deve respeitar o fluxo real. Se módulos funcionam em paralelo, isso precisa aparecer. Evitar diagrama fictício linear quando a implementação tiver ramificações.

## Evidência mínima desejável

- Duas composições tecnológicas substancialmente diferentes executadas no mesmo ambiente (industrial e embarcada).
- Demonstração de que a configuração dos recursos modifica a estrutura física do problema e os resultados, sem recompilar um otimizador dedicado.
- Um registro reexecutável: entradas, identificação da configuração, parâmetros, estados, condições da corrida e saídas correspondentes.
- Testes de integridade/factibilidade e auditorias numéricas, **se efetivamente disponíveis**.

## Limites da contribuição

Uma plataforma científica não se valida apenas por apresentar menus. Inversamente, uma simulação de cenário não comprova validade física universal dos modelos. A análise deve distinguir **funcionalidade de software**, **consistência computacional** e **aderência à realidade física**, que exigem evidências diferentes.