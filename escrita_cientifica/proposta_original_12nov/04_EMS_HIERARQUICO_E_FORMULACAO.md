# Contribuição II — O coração matemático: EMS hierárquico MILP–MPC

## Mensagem nuclear

O problema de despacho não se resume a atender a carga a cada instante. As decisões sobre armazenamento, acionamento de fontes e intercâmbio energético têm consequências futuras porque afetam estados e a disponibilidade dos recursos. A coordenação temporal busca **introduzir informação de um horizonte maior nas decisões repetidas de curto prazo**.

A hipótese metodológica não é «o futuro é conhecido» ou «a solução é globalmente ótima em qualquer condição». O projeto dispõe de uma **representação/estimativa do valor futuro da energia** e de mecanismos para conduzi-la ao despacho de curto prazo; sua definição real, qualidade e efeitos devem ser examinados.

## Descrição conceitual aprovada

1. A camada de prazo mais amplo analisa a disponibilidade futura dos recursos sob hipóteses e previsões definidas.
2. O resultado dessa camada informa, por algum mecanismo matemático implementado, o valor de preservar ou consumir determinado estado energético futuro.
3. A camada de curto prazo resolve um problema de despacho com decisões operacionais, balanços e restrições para uma janela.
4. A execução aplica a primeira decisão ou a parte prevista da sequência, atualiza estados e repete a otimização de forma causal, **na medida em que isso ocorre no código**.
5. A auditoria permite examinar qual solução, estado e orientação foram associados a cada janela.

**Não impor como fato** uma arquitetura genérica de MPC se o código tiver diferenças na frequência da reotimização, passagem de estados, memória ou método para gerar o valor futuro.

## O que deve ser reconstruído do código

### Variáveis e índices

- Resolução temporal e horizontes adotados.
- Potências por recurso, potência de importação/exportação, estado energético, sinais de carga e descarga.
- Variáveis contínuas e discretas (binárias/inteiras) efetivamente presentes.
- Estados herdados, estados terminais e quaisquer estados de máquina (por exemplo PEMFC ligada/desligada), se modelados.
- Convenções de sinais e unidades.

### Equações e restrições centrais

- Balanço de potência/energia do sistema, incluindo perdas ou rendimentos quando declarados.
- Limites de geração variável, disponibilidade e eventual corte (*curtailment*).
- Bateria: SOC, potência, energia, perdas, limites, exclusividade de carga/descarga se implementada.
- Fontes despacháveis: mínimos/máximos, rampas e outras restrições realmente presentes.
- PCC/rede: limites de importação, exportação e custos nos cenários conectados.
- Carga não atendida: se permitida, penalidade e interpretação; se proibida, tratamento de infactibilidade.
- Restrições específicas de PEMFC/H₂ nos cenários aplicáveis.
- Transições de estados entre janelas, estados terminais e eventuais restrições de consistência intertemporal.

### Função objetivo

Reproduzir fielmente os componentes codificados: aquisição de energia, uso ou operação de fontes, penalidades, reserva/SOC, hidrogênio ou outras parcelas quando existirem. Não chamar «custo total da conta de luz» se forem modeladas apenas parcelas de energia, TE/TUSD ou algum preço horário representativo.

A notação ilustrativa de nossa conversa foi:

`min [ J_curto + V_futuro_aproximado(x_terminal) ]`

**ALERTA:** é **apenas uma intuição editorial**, não a formulação confirmada. A representação real pode incluir sinais, estados, pesos, limites e convenções distintas; Claude deve extraí-la dos arquivos e testes do EMS.

### Camada de prazo maior e valor futuro

Responder cientificamente:

1. Qual é o domínio da informação futura? Qual horizonte e passo temporal são utilizados?
2. Como a aproximação é construída? Por otimização, projeção, envelope, interpolação, dualidade ou outro mecanismo efetivamente implementado?
3. Quais estados recebem valor futuro e com que unidades?
4. Como a aproximação alcança a camada MPC? Termo de objetivo, condição terminal, limite ou sinal equivalente?
5. Como são tratados eventuais erros de previsão, limites desconhecidos e problemas de cobertura do domínio?
6. Há certificações, auditorias ou testes de exatidão/consistência disponíveis? Quais as limitações declaradas?

**Tratar o valor futuro como ponto forte e ponto examinável.** É forte porque contextualiza o curto prazo com informação temporal mais ampla; é vulnerável porque uma aproximação mal especificada pode orientar inadequadamente o despacho. Não esconder essa questão; torná-la auditável.

### Horizonte móvel e causalidade

Verificar se a decisão aplicada em cada janela depende apenas das informações disponíveis naquele momento, como são transportados o SOC e outros estados, e se os resultados comparados utilizaram as mesmas previsões e condições de informação. Não confundir um plano perfeito calculado offline com MPC causal.

### Solver e garantias

Distinguem-se:

- Solução ótima do **modelo MILP formulado** sob tolerâncias e parâmetros do solver.
- Factibilidade e aderência às **restrições modeladas**.
- Qualidade do despacho sob **aproximações, horizonte e dados escolhidos**.
- Aderência física a uma microrrede real, que não decorre automaticamente das anteriores.

Ao mencionar «ótimo», especificar o objeto: ótimo do problema matemático com hipóteses e tolerâncias declaradas, quando de fato demonstrado pelo solver. Nunca ampliar para operação fisicamente ótima universal.

## Estratégias de comparação sem prometer resultados

O autor aprovou **examinar** a influência da hierarquia, não decidiu antecipadamente a vantagem. Para inferir efeitos do valor futuro:

- Manter **a mesma microrrede física** (por exemplo, configuração industrial C4), mesmos perfis, horizonte de teste, limites, estado inicial e custos.
- Comparar estratégias com diferença metodológica bem definida, por exemplo MPC de horizonte curto sem sinal de valor futuro vs estratégia hierárquica com sinal, **se ambas forem implementadas e disponíveis**.
- Usar métricas que se conectem à função objetivo e aos recursos, e apresentar eventuais conflitos com variáveis de interesse não otimizadas.
- Controlar *look-ahead* de informação, condições terminais e orçamento de solução para não favorecer indevidamente uma estratégia.
- Demonstrar onde o sinal hierárquico aparece nos resultados; não inferir vantagem somente pelo nome da abordagem.

Se a comparação metodológica ainda não existir no software, apresentá-la como experimento a implementar, não como resultado.

## Escopo gráfico sugerido

Uma figura de tempo e estados: **camada superior** (horizonte maior, estimativa de valor, estado de referência) → **camada MPC** (janela recedente, restrições, decisão) → **planta computacional e atualização de estados** → retorno de informação. O desenho final deve ser consistente com a arquitetura efetiva.

## Como escrever a seção sem torná-la monografia

Apresentar as equações indispensáveis com definições concisas de variáveis e hipóteses; agrupar restrições semelhantes e indicar o papel de cada grupo. Reservar demonstrações algébricas extensas, documentação de contratos, pseudocódigo pormenorizado e variantes secundárias para apêndices. **O artigo deve continuar compreensível sem consultá-los.**