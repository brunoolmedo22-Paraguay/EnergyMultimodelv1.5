# SEEDS2 — Protocolo científico mestre

## 0. Título e identidade

### Título de trabalho acordado

> **SEEDS2: Desenvolvimento e Avaliação de uma Plataforma Modular para Simulação Operacional e Otimização do Despacho Energético em Microrredes por Meio de um EMS Hierárquico Baseado em MILP–MPC**

É um título **provisório, mas preferido**. Sua construção é deliberada:

- **«Simulação operacional»** esclarece a modalidade de simulação: operação energética e decisões de despacho. Não sugere simulações de fluxo de potência, estabilidade eletromecânica, fenômenos térmicos de rede ou qualquer análise não implementada.
- **«Otimização do despacho energético»** é preferível a «despacho ótimo» porque não pressupõe otimalidade global de sistemas físicos em qualquer cenário.
- **«Por meio de um EMS hierárquico»** explicita que o EMS é o método empregado na plataforma, não uma qualidade intrínseca da microrrede.
- **«Baseado em MILP–MPC»** comunica a coordenação entre planejamento e controle preditivo, sujeita à descrição fiel da implementação.

O título poderá ser abreviado por motivos editoriais, **sem perder** os eixos plataforma + simulação/otimização operacional + hierarquia temporal.

### Nome

**SEEDS = Smart Energy Ecosystem for Decision Support.** O artigo pode expandir o acrônimo uma vez ao apresentar SEEDS2. O significado enfatiza **apoio à tomada de decisão**. O número **2** faz parte da identidade nominal e **não requer explicação**. Não contextualizar origens institucionais, denominações de outras iniciativas ou história de naming.

### Definição operacional

SEEDS2 é uma **plataforma computacional modular e reconfigurável** que permite ao pesquisador configurar sistemas energéticos com modelos físicos e operacionais, combinar recursos e cenários, executar simulações, visualizar resultados e analisar decisões de despacho com um sistema de gerenciamento energético (EMS) hierárquico.

A analogia interna aprovada para orientar o texto é a de uma **bancada virtual configurável**, em contraste com um software concebido exclusivamente para uma configuração fixa. A analogia não precisa aparecer literalmente na publicação: sua função é preservar a filosofia de concepção.

SEEDS2 **não comanda autonomamente instalações reais** no escopo deste artigo. Simulação, análise, experimentação computacional e apoio a decisões são os termos corretos.

## 1. Tese científica central

O trabalho investiga o desenvolvimento e a avaliação computacional de um **ambiente de modelagem, simulação operacional e otimização de despacho reconfigurável**, no qual a seleção de tecnologias e condições de operação não é presa a uma única microrrede. Esse ambiente incorpora um EMS hierárquico que coordena decisões de curto e longo prazo mediante uma representação do valor futuro da energia.

A tese deve ser demonstrada por **evidências de funcionamento**, e não por declarações promocionais ou pela contagem de módulos.

### O objetivo geral proposto

> Desenvolver e avaliar computacionalmente uma plataforma modular de modelagem, simulação operacional e gerenciamento energético de microrredes, integrando modelos de geração e armazenamento, restrições operacionais e uma estratégia hierárquica de otimização baseada em MILP–MPC, de modo a permitir análises reprodutíveis do despacho em diferentes configurações e cenários.

Formulação editorial; pode ser aperfeiçoada na escrita, preservando significado e sem alegar validação experimental.

## 2. Duas contribuições de igual peso

### Contribuição I — Arquitetura e dinâmica de uso da plataforma

- Modularidade de tecnologias e recursos.
- Configuração de equipamentos e composição de microrredes.
- Catálogos, parametrização e integração de modelos.
- Criação e gerenciamento de cenários, entradas e séries temporais.
- Bancadas/modelos, fluxos de execução e interface de análise.
- Rastreabilidade, armazenamento, identificação de execuções e evidências de reprodutibilidade, quando efetivamente implementados.
- Reutilização do mesmo ambiente em configurações físicas e contextos operacionais distintos.

O que interessa não é a quantidade de telas, mas a **dinâmica do ambiente científico**: configuração → geração de condições → execução → coleta/inspeção de resultados → comparação e interpretação.

### Contribuição II — Formulação e execução do EMS hierárquico

- Modelagem matemática pertinente ao despacho energético.
- Restrição de balanço energético, tecnologias, estados e limites operacionais.
- Planejamento em horizontes distintos e coordenação das informações.
- Camada de curto prazo com decisões atualizadas e estados transportados entre janelas.
- Camada de longo prazo fornecendo orientação por **valor futuro aproximado**.
- Verificações de coerência numérica, factibilidade e rastreabilidade das decisões, conforme a implementação efetiva.

Não afirmar invenção de MILP/MPC, nem de conceitos de valor futuro da energia. A contribuição a defender está nas **escolhas de arquitetura, integração, implementação matemática e aplicação conjunta**.

### Regra editorial de equilíbrio

A plataforma e o EMS devem receber **importância científica equivalente** nas partes centrais da narrativa. Os estudos de caso não formam uma terceira contribuição independente: são veículos para mostrar **como a plataforma funciona** e **como o otimizador atua**.

## 3. Originalidade sem excepcionalismo

É legítimo que existam outros estudos sobre EMS hierárquico, energia, H₂, software modular e aplicações embarcadas. A proximidade temática demonstra relevância de pesquisa, **não prova** novidade nem torna uma arquitetura idêntica a outra.

A caracterização científica do SEEDS2 deve repousar em aspectos demonstráveis de seu conjunto e de sua filosofia de integração. Evitar tanto a afirmação «é o primeiro/único/inédito» quanto a redução «é apenas uma coleção de algoritmos». Não atribuir ao projeto novidade não respaldada por comparação efetiva com trabalhos relacionados.

## 4. A pergunta que conecta todo o artigo

**Como construir e empregar um ambiente computacional reconfigurável que represente sistemas energéticos heterogêneos e permita examinar seu despacho por uma estratégia hierárquica de curto e longo prazo, de forma rastreável e coerente com restrições operacionais?**

Subperguntas, a formular com rigor e sem prometer resultados:

1. A plataforma consegue representar e executar **diferentes configurações** usando uma mesma estrutura de modelagem e análise?
2. As decisões computadas respeitam a representação energética, estados, limites e hipóteses declaradas?
3. A orientação de longo prazo modifica ou contextualiza as decisões do horizonte curto de maneira matematicamente explicável e observável?
4. O que os estudos hipotéticos permitem concluir, e o que **não** permitem (especialmente em relação à operação física real)?

## 5. O artigo é uma investigação, não um manual

**Descrever:** decisões de arquitetura, abstrações físicas e matemáticas, seleção de cenários, funções do EMS, evidência empírica computacional, comparação de alternativas e limites.

**Evitar:** roteiro de cliques, catálogo de botões, excesso de screenshots promocionais, cronologia do desenvolvimento, log de commits, adjetivos como «revolucionário», métricas sem unidade/base e opiniões sem evidência.

Imagens da interface só entram quando ilustram uma característica científica importante, por exemplo integração da configuração, controle de cenário ou rastreabilidade da execução. A discussão de resultados deve usar preferencialmente gráficos energéticos, séries, indicadores, comparações e tabelas de execução.

## 6. Escopo de avaliação

- Avaliação por **cenários hipotéticos computacionais**.
- Não se dispõe de uma campanha de medidas físicas das instalações representadas que valide o conjunto completo.
- Pode-se comprovar **consistência computacional** de balanços, restrições, repetibilidade e integridade de dados mediante testes efetivamente executados.
- O software pode ter modelos respaldados por bibliografia ou ensaios específicos, mas isso não equivale à validação experimental integrada de SEEDS2 para os casos descritos.
- Não extrapolar os resultados para ganhos reais de campo, segurança física ou autonomia real de embarcações.

## 7. Hierarquia de entrega científica

**Artigo principal:** autossuficiente; apresenta o problema, a contribuição, as equações indispensáveis, hipóteses, descrição suficiente dos cenários, resultados necessários e conclusões suportadas.

**Materiais secundários:** apêndice de arquitetura, formulação expandida, dados e configurações completas, verificações numéricas, arquivos reprodutíveis, fontes de software, figuras exportáveis. Servem para reproduzir e ampliar, **não** para esconder do artigo a informação sem a qual seus resultados não podem ser entendidos.

**Estado editorial:** TCC em português; possível adaptação futura ao inglês para periódico especializado. Formato de trabalho LaTeX/Overleaf `elsarticle` 3p em duas colunas; conferir regras atuais da revista antes de submeter.
