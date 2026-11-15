# Roteiro integral das sete seções do artigo

**Princípio de coesão:** cada seção responde a uma pergunta necessária e prepara a seguinte. A ordem geral é **problema → literatura → plataforma → método matemático → avaliação → evidência → conclusão**. Não é uma lista de componentes e não deve ser transformada em sete capítulos isolados.

## 1. Introdução

**Pergunta:** Qual é o problema de engenharia que justifica esta investigação?

**Movimento argumentativo:**

1. Iniciar de modo concreto: configurações energéticas distintas introduzem fontes com propriedades e limites diferentes; a composição de recursos altera os caminhos possíveis do despacho.
2. Explicar que armazenamento, geração variável e fontes despacháveis exigem decisões ao longo do tempo, com efeitos sobre estados e recursos posteriores.
3. Situar o problema das ferramentas de modelagem e gestão: o pesquisador precisa variar sistemas, definir cenários e comparar resultados dentro de um ambiente confiável e rastreável.
4. Aproximar os antecedentes de plataformas modulares e os métodos MILP, MPC e coordenação entre horizontes, sem uma revisão exaustiva antecipada.
5. Delimitar a questão investigada: integrar arquitetura reconfigurável e despacho hierárquico sob premissas e restrições explícitas, verificando essa integração em aplicações computacionais diferentes.
6. Apresentar SEEDS2, eventualmente expandindo **Smart Energy Ecosystem for Decision Support** de modo breve, explicando que a plataforma apoia decisões; não opera equipamentos reais autonomamente.
7. Declarar claramente as **duas contribuições com peso equivalente** e anunciar os dois estudos como demonstrações/evidências.

**O que deve aparecer:** problema operacional e temporal, necessidade de reconfiguração, contribuição específica, objetivo do trabalho, escopo computacional e roteiro breve.

**O que deve ficar para depois:** formulação completa do EMS, catálogo de tecnologias, parâmetros numéricos dos estudos, resultados e descrição de telas.

**Erro a evitar:** abertura genérica do tipo «no cenário energético contemporâneo, a busca por soluções inovadoras...»; grandiloquência e afirmações de inexistência de estudos similares.

**Base bibliográfica:** Claude deve selecionar autonomamente trabalhos relevantes e verificá-los, incluindo plataforma/EMS/otimização temporal, podendo sair da biblioteca Work.

## 2. Fundamentação teórica e trabalhos relacionados

**Pergunta:** O que a literatura já oferece e em que conjunto de problemas o SEEDS2 se insere?

**Movimento argumentativo:**

1. Definir somente conceitos necessários ao objetivo: microrrede como sistema energético a modelar, despacho, recursos e restrições relevantes.
2. Examinar plataformas de simulação/modelagem reconfiguráveis, seus objetivos, modalidades de dados, componentes e níveis de acoplamento. Usar exemplos documentados, não transformar a seção em catálogo de marcas.
3. Examinar formulações de gerenciamento por otimização, incluindo balanços, custos, restrições inteiras, armazenamento e elementos de despacho.
4. Examinar MPC e estratégias de hierarquia temporal, distinguindo planejamento de prazo maior e execução reavaliada em janelas menores; discutir literatura sobre informação/valor futuro conforme fontes verificadas.
5. Mostrar como modelos tecnológicos se fundamentam em formulações e referências específicas, sem repetir ainda as equações detalhadas de cada implementação.
6. Elaborar síntese crítica: quais recursos e abordagens são comuns, quais escolhas arquiteturais diferem, quais aspectos do SEEDS2 podem ser avaliados diante desse panorama.

**Saída esperada:** definição honesta de uma **contribuição de integração** e da delimitação da avaliação, sem alegar unicidade ou superioridade não examinadas.

**Figura/quadro opcional:** comparação concisa de capacidades e compromissos metodológicos entre plataformas/trabalhos selecionados; só incluir diferenças explicitamente documentadas.

## 3. Arquitetura e desenvolvimento da plataforma SEEDS2

**Pergunta:** Como o ambiente foi organizado para permitir configurar, executar e inspecionar diferentes experimentos energéticos?

**Eixo principal:** a **plataforma científica**, primeira contribuição, não uma apresentação comercial de UI.

**Encadeamento recomendado:**

1. Arquitetura em alto nível: módulos, funções e fronteiras de responsabilidade.
2. Modelos físicos e operacionais de tecnologias disponíveis e forma de parametrização; distinguir uma bancada física detalhada de uma abstração usada na otimização.
3. Catálogos de dispositivos, composição de microrredes e criação de variantes sem reprogramar cada cenário.
4. Contratos e origem das séries temporais de demanda, meteorologia, tecnologias, tarifas e estados; sincronização de timestamps e unidades quando efetivamente implementada.
5. Dinâmica experimental: criar/configurar → selecionar cenários → executar → registrar → visualizar/comparar/exportar.
6. Persistência, identificação das execuções, verificação de entradas e rastreabilidade conforme o commit auditado.
7. Escolhas de Python, Streamlit e recursos de software relevantes, relacionando-as à modularidade e à interação, sem descrição de instalação.

**Figuras propostas:** diagrama de componentes e fluxo de dados de uma execução. Screenshots só se demonstram efetivamente alguma função científica.

**Fecho:** o leitor compreendeu o ambiente e sua dinâmica; o próximo passo é descrever o **mecanismo matemático de despacho** que ele executa. Não anunciar que «a plataforma ainda será descrita» após a seção 4.

## 4. Modelagem matemática e sistema de gerenciamento energético hierárquico

**Pergunta:** Como o SEEDS2 calcula as decisões de despacho e coordena curto e longo prazo?

**Eixo principal:** o **coração matemático**, segunda contribuição de igual importância.

**Encadeamento recomendado:**

1. Definir conjuntos, índices, estado energético, decisões por intervalo, convenção de sinais e resolução temporal somente no nível necessário.
2. Formular a função objetivo **tal como implementada**, incluindo custos, penalidades ou termos que realmente existam.
3. Apresentar balanço energético do sistema e limites comuns das fontes, cargas, armazenadores, intercâmbios e recursos despacháveis.
4. Modelagem operacional da bateria e seus limites de SOC, potência e eficiências, se constarem do EMS.
5. Tratamento de fotovoltaica/eólica, rede/PCC, tecnologia térmica e PEMFC na medida em que participam do EMS, evitando fingir identidade entre modelos físicos detalhados e envoltórias energéticas.
6. Planejamento de longo prazo e como gera sinal/informação relevante ao curto prazo; explicar a **aproximação** de valor futuro e suas hipóteses.
7. Curto prazo em horizonte móvel/MPC: atualização de estados, reotimização, sequência causal de decisões e interface com a camada superior.
8. Limites do solucionador, auditabilidade, factibilidade, exceções e evidências numéricas que possam ser demonstradas.

**A fórmula ilustrativa** `J_curto + V_futuro_aprox(estado_terminal)` é apenas uma forma de expressar a ideia; a equação final deve ser reconstruída **a partir do código**, não imposta pelo protocolo.

**Figuras propostas:** camadas e janelas temporais, estados e sinal de valor futuro; formulação expandida somente em apêndice.

**Fecho da seção 4:** ao final das seções 3 e 4, a plataforma e o EMS estão **integralmente caracterizados no nível do artigo**. A seção 5 passa diretamente à metodologia de avaliação, sem nova seção de desenvolvimento.

## 5. Metodologia de avaliação e estudos de caso

**Pergunta:** Como observar e verificar o comportamento do SEEDS2 sob condições controladas?

**Natureza:** experimento computacional/demonstração em cenários hipotéticos. Não chamar «validação experimental».

**Componentes:**

- Desenho geral dos ensaios; quais capacidades da plataforma e do EMS são examinadas.
- Dados de entrada, origem, hipótese de representatividade, resolução e sincronização.
- Condições iniciais, restrições, duração e horizontes, solver, ambiente computacional e tratamento de falhas.
- Métricas para energia, operação, custo **somente dos componentes efetivamente modelados**, factibilidade e rastreabilidade.
- Separação entre efeito de **tecnologia/configuração** e efeito de **estratégia de controle**.
- Referência comparativa para o EMS caso se pretenda inferir benefício de hierarquia, sob sistema físico igual e demais variáveis controladas.
- Estudos I e II conforme arquivo `05_ESTUDOS_DE_CASO_E_METODOLOGIA.md`.

**Regra:** são **dois estudos**. As quatro configurações industriais são tratamentos de um mesmo estudo, não quatro estudos autônomos.

## 6. Resultados e discussão

**Pergunta:** O que as execuções realmente demonstraram sobre a plataforma e o EMS?

### 6.1 Avaliação da plataforma e consistência computacional

Demonstrar somente características que se possam observar ou testar: criação/reconfiguração de sistemas, integridade dos dados, execução de diferentes tecnologias, consistência de resultados, persistência, reprodutibilidade, auditoria e cumprimento de restrições. Não substituir essas evidências por capturas de tela de funcionalidades sem execução.

### 6.2 Estudo de Caso I — Avaliação comparativa da microrrede industrial

**Maior extensão relativa.** Organizar por fenômenos comuns entre **C1–C4**: perfis e potência importada, influência da FV, carregamento/descarregamento da bateria, deslocamento temporal de energia, custos modelados e decisões do EMS. Se for comparar estratégias, manter a mesma configuração física e parâmetros; discutir diferenças do EMS em bloco claramente separado da mudança dos recursos.

### 6.3 Estudo de Caso II — Operação do sistema energético embarcado

Distribuição do suprimento entre PEMFC, FV e bateria, potência e estados, SOC, H₂ consumido, restrições e variações da carga, papel do horizonte maior. Não apresentar autonomia, quilômetros ou esgotamento de tanque.

### 6.4 Discussão integrada e limitações

Retomar as **duas contribuições**, explicitar semelhanças e diferenças entre os estudos, confrontar literatura pertinente e separar observação numérica, explicação física e inferência. Delimitar validade dos modelos e do experimento hipotético, sem alegar realização de ensaio físico.

**Estilo preferido de análise:** «observa-se um valor ou mudança», «esse comportamento é explicado por...», «isso implica... no escopo do modelo». Não inverter essa ordem para iniciar com elogios à ferramenta.

## 7. Conclusões e trabalhos futuros

**Pergunta:** Quais perguntas foram respondidas pelas evidências, com que limites e que trabalho decorre disso?

1. Síntese da contribuição de plataforma: o que se demonstrou sobre configuração, representação de sistemas heterogêneos e execuções rastreáveis.
2. Síntese da contribuição EMS: o que foi observado em decisões, restrições e orientação entre horizontes; quantificar somente o que se mediu/produziu.
3. Discussão dos limites de escopo, hipóteses, modelos e ausência de validação experimental física integrada.
4. Perspectivas de expansão motivadas por limites demonstrados, não lista genérica de tecnologias desejadas.

**Proibições:** prometer redução de custos/consumo/emissões sem dados; alegar otimalidade física irrestrita; apresentar hipóteses futuras como resultados concluídos.

## Mapa dos limites entre seções

| Tema | Onde desenvolver | Onde não duplicar |
|---|---|---|
| Motivação/objetivo/contribuições | 1 | Repetições longas em 2–7 |
| Trabalhos correlatos/estado da arte | 2 | Catálogos de referências em 3 |
| Arquitetura/modelos/microrredes e cenários | 3 | Manual de interface em 6 |
| Formulação/EMS/valor futuro | 4 | Derivação completa repetida em 5 |
| Entradas, desenho e métricas dos ensaios | 5 | Definição tardia em 6 |
| Saídas, comparações e interpretações | 6 | Antecipação em 1–5 |
| Respostas finais e limites | 7 | Resultados inéditos em 7 |
