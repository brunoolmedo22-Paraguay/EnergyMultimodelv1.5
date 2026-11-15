# Metodologia e estudos de caso — exatamente dois

## Natureza dos estudos

Os casos são **demonstrações e avaliações de comportamento computacional** de uma plataforma e de um EMS, por meio de cenários hipotéticos tecnicamente parametrizados. O objetivo é observar como diferentes configurações energéticas são modeladas e como o despacho é calculado; **não** é validar uma central ou embarcação física contra campanha experimental de medição.

As duas aplicações têm papéis complementares:

- **I — Microrrede industrial conectada:** comparação controlada de **quatro configurações** de recursos e potencial avaliação metodológica da hierarquia; análise mais extensa.
- **II — Sistema energético de embarcação isolada Boto H₂:** outra topologia e outras fontes (PEMFC, bateria, FV) para examinar composição de recursos, operação sem rede e despacho em regime de carga variável.

Não tratar a combinação como **cinco estudos**. C1, C2, C3 e C4 pertencem ao mesmo **Estudo I**.

## Estudo I — Microrrede industrial hipotética na área da COPEL

### Propósito

Representar um consumidor industrial hipotético conectado à rede de distribuição, com perfil de carga comum, para verificar como a **composição de recursos** altera o despacho e os custos representados. A aplicação permite ainda ensaiar, com sistema físico fixo, a **influência da coordenação hierárquica** no gerenciamento da energia.

### Quatro configurações (mesma microrrede, quatro tratamentos)

| Código | Composição | Função na comparação |
|---|---|---|
| C1 | Rede (PCC) | Referência física de fornecimento apenas pela rede |
| C2 | Rede + solar fotovoltaica | Isolar a contribuição da disponibilidade FV |
| C3 | Rede + bateria | Examinar armazenamento e deslocamento temporal de energia |
| C4 | Rede + FV + bateria | Examinar interação de geração variável e armazenamento |

As quatro compartilham **o mesmo perfil de demanda, o mesmo intervalo de análise e demais condições pertinentes**, mudando somente a composição tecnológica indicada e os parâmetros necessários a ela.

### Dados e hipóteses de referência — SUJEITOS A CONFERÊNCIA

A preparação histórica discutiu um perfil industrial típico vinculado a dados COPEL, identificado como **CT-046**, categoria **A4**, um estudo localizado no Paraná e valores tarifários e de dimensionamento propostos. Nenhum número deve ser transportado ao texto sem conferir:

1. Origem e versão exatas da curva de carga (fonte oficial, dados originais, tratamento e eventual normalização).
2. Resolução temporal e duração do perfil; sincronização com meteorologia e tarifa.
3. Escalonamento hipotético do consumidor e definição de pico ou consumo energético.
4. Dados meteorológicos de irradiância e temperatura, fonte, localidade, série e interpretação física.
5. Parâmetros da instalação FV: equipamento, número de módulos, inversor, potência nominal e deratings.
6. Parâmetros da bateria: energia, potência, eficiências, SOC inicial, limites, custos e estado final.
7. Limites de PCC, importação/exportação, perdas e regras de curtailment.
8. Componentes tarifários efetivamente modelados, janelas de ponta, premissas de faturamento e data de vigência.
9. Compatibilidade da estrutura econômica com a função objetivo MILP–MPC implementada.

**Parâmetros discutidos historicamente, mas NÃO consolidados como valores finais do artigo:** escalonamento para ordem de 100 kW de carga de pico; potência FV próxima de 58 kWp; bateria em torno de 200 kWh/50 kW; conexão de 200 kW; SOC inicial de 30%; curva com 96 pontos de 15 minutos e uma data de referência em outubro de 2026. Houve também estimativas de tarifas diferenciadas ponta/fora de ponta. **Todos esses valores são recordatórios e devem ser substituídos pelos arquivos de configuração finais, se forem diferentes.**

### Perguntas de análise

- Qual a energia importada e como evolui o intercâmbio com a rede ao longo do dia?
- O que muda quando a geração FV passa a estar disponível? Há redução de importação, alteração dos picos ou de horas críticas?
- Em que momentos a bateria carrega ou descarrega e qual sua relação com o perfil de carga, FV e preços?
- Como se comportam SOC, energia fornecida, corte FV e limites de potência?
- Quais componentes de **custo explicitamente modelado** mudam entre C1–C4?
- Sob C4 fixa (ou outra configuração adequada), em que decisões o horizonte de longo prazo influencia o MPC, comparado a um procedimento de referência válido?

### Regras fortes de interpretação

- Não narrar quatro microestudos isolados em sequência. **Comparar todas as configurações por fenômeno**, usando figuras integradas e métricas comuns.
- Melhorias ao passar de C1 para C4 não são automaticamente benefícios do EMS; a disponibilidade tecnológica também mudou.
- Para falar sobre mérito do método de controle, comparar **estratégias distintas sob o mesmo arranjo físico** e com hipóteses equivalentes.
- O custo não significa tarifa industrial completa a menos que efetivamente inclua demanda contratada, encargos, impostos, bandeiras, etc. Nomear as parcelas presentes.
- Não inferir rentabilidade, payback ou viabilidade financeira sem custos de investimento e demais dados necessários.

## Estudo II — Sistema energético embarcado Boto H₂

### Propósito

Mostrar a aplicação da mesma plataforma e do EMS a uma arquitetura **isolada da rede**, com fontes e restrições diferentes das industriais. Observar a coordenação entre PEMFC, geração FV e bateria diante de um perfil de demanda variável.

### Elementos a representar

- Perfil de carga elétrica do sistema embarcado, origem e potência temporal.
- Geração FV e condições meteorológicas, se estiverem presentes na configuração final.
- PEMFC/H₂: curva de capacidade, limites, disponibilidade, consumo, custos/pesos da otimização, estado inicial, dinâmica e resposta operacional.
- Bateria: capacidade, potência, SOC, carga e descarga.
- Sem PCC ou importação de rede; atendimento de carga dependente dos recursos internos e do tratamento de déficit que exista no software.

### Hipótese expressamente aprovada pelo autor

**Disponibilidade de H₂ não limitante durante o horizonte do experimento.** É uma hipótese do cenário, não uma afirmação de reservatório físico infinito ou autonomia ilimitada na navegação. O consumo de H₂ pode ser calculado pelo modelo, sem impor um tanque finito ou estudar seu esgotamento.

**Fora do escopo:** alcance, quilômetros de navegação, tempo máximo até esgotamento do tanque, autonomia energética de longo prazo ou validação contra navegação real.

### Valores de referência discutidos que exigem conferência

A preparação recente considerou a PEMFC **inicialmente ligada**, com **potência anterior de 30 kW** e uma rampa documentada de **2 kW/s (equivalente a 120 kW/min)**. Esses parâmetros devem coincidir com o cadastro/configuração final do caso e ser interpretados conforme o passo temporal do EMS. Não confundir rampa de potência com restrição de permanência mínima, custo de transição ou estado de máquina; só formular o que estiver implementado.

### Perguntas de análise

- Como o despacho reparte a potência demandada entre PEMFC, FV e bateria?
- Em quais intervalos há carga e descarga e como isso modifica o SOC?
- O controlador preserva os limites e transições efetivamente modelados?
- Em que momento a PEMFC aumenta/reduz potência e como seu comportamento está associado à rampa e demais limites?
- Qual consumo de H₂ é estimado pela simulação e em quais condições?
- A informação de prazo maior produz comportamento interpretável, sem pressupor que a bateria «deva» carregar em horário predeterminado?
- A plataforma registra e apresenta de modo comparável o caso conectado e o caso isolado?

### Regras de interpretação

- Não exigir um padrão antecipado de uso da bateria. O funcionamento deve ser comparado **à função objetivo, aos dados e às restrições**, não à expectativa intuitiva do pesquisador.
- Não afirmar que o EMS controla uma embarcação real.
- Não converter consumo calculado de H₂ em autonomia real sem capacidade e condições físicas compatíveis.
- Não comparar diretamente o custo industrial tarifado com custo naval, salvo métrica comum explicitamente definida e metodologicamente justificada.

## 3. Estrutura de experimentos e comparações

A matriz abaixo indica **perguntas**, não resultados. Não impõe que todos os ensaios já estejam implementados:

| Análise | Sistema mantido | Variável de interesse | Inferência legítima |
|---|---|---|---|
| Efeito tecnológico | Mesmo consumidor, perfil e cenário industrial | C1–C4 | Diferenças de composição de fontes/armazenamento |
| Efeito da hierarquia | Uma configuração física fixa (ex. C4) | MPC curto prazo vs EMS hierárquico, se disponível | Diferenças entre estratégias no mesmo problema |
| Transferibilidade da plataforma | Configurações industrial e embarcada | Tipo de recurso, topologia, fonte de energia | Capacidade de modelar/executar arquiteturas distintas |
| Consistência de operação | Cada execução | Saldos, SOC, limites, custos, factibilidade | Coerência do resultado com o modelo computacional |

## 4. Protocolo mínimo de reprodução

Registrar, para cada execução: identificador da microrrede e do cenário, versão/commit do software, catálogos e parâmetros, séries de entrada e origem, fuso e granularidade, estados iniciais, solver e tolerâncias, horizonte, estratégia EMS, status, métricas e artefatos de saída. Quando algum elemento não estiver registrado automaticamente, documentar o procedimento de coleta manual e a limitação.

## 5. Relação com as seções

- **Seção 3:** explica como o SEEDS2 suporta ambas as composições.
- **Seção 4:** explica como o EMS representa e decide o despacho.
- **Seção 5:** fixa hipóteses, entradas e desenho dos dois casos.
- **Seção 6:** mostra o que foi executado, observado e comparado, com maior espaço para o caso industrial.
