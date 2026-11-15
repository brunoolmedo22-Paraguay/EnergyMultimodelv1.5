# Evidências, indicadores e discussão — o que o artigo poderá demonstrar

## Princípio editorial

**As figuras nascem das perguntas científicas, não o inverso.** O desenho de uma análise precede a escolha de curvas e tabelas; os resultados só são afirmados após execução, extração e verificação dos dados.

O artigo deve distinguir:

1. **Fato computacional observado:** valor, curva, mudança, evento ou status produzido e reprodutível.
2. **Interpretação matemática:** efeito do objetivo, das restrições, estados e horizonte.
3. **Explicação física/operacional:** relação com carga, geração, disponibilidade, armazenamento e custos.
4. **Conclusão autorizada:** o que aquela evidência sustenta, sem extrapolar para experimentos físicos.

## Contribuição I — evidência de plataforma

| Pergunta | Evidência possível | Limite da inferência |
|---|---|---|
| O sistema é configurável? | Cadastro e execução de topologias distintas sob o mesmo fluxo | Não prova que qualquer tecnologia futura pode ser conectada sem adaptação |
| Os dados estão sincronizados? | Auditoria de timestamps, unidades e cobertura por execução | Não prova qualidade da previsão externa |
| O sistema é rastreável? | Identificação de corrida, entradas, parâmetros, versão, estados e saídas | Captura de tela sem metadados não é rastreabilidade suficiente |
| A execução é reprodutível? | Reexecução nas mesmas condições e comparação de saídas/tolerâncias | Algoritmos estocásticos podem exigir semente, ambiente e tolerância |
| As tecnologias são integradas? | Estudos industrial e embarcado com fontes e perfis distintos | Não equivale a validar física e experimentalmente cada recurso |

## Contribuição II — evidência do EMS

| Pergunta | Evidência possível | Limite da inferência |
|---|---|---|
| O balanço energético fecha? | Série de resíduos de potência/energia e tolerância | Depende de definições, discretização e perdas modeladas |
| O SOC respeita limites? | Série temporal e violações observadas | Não garante degradação eletroquímica real |
| Fontes respeitam limites? | Potência, estados e rampas com margens | Só limites realmente representados |
| O controlador reage ao contexto? | Comparação temporal de decisões com sinais e informações do prazo maior | Não basta mostrar mudanças: é necessário conectar causalmente ao sinal |
| A hierarquia melhora alguma métrica? | Comparação controlada com baseline sob condições iguais | Não assumir resultado favorável; medir trade-offs |
| A otimização é solucionável? | Status de solver, factibilidade e tempos de execução | Não inferir desempenho em sistemas e horizontes não testados |

## Figuras candidatas — não são uma cota fixa

Sugestões a escolher **depois da inspeção dos resultados reais**:

1. Arquitetura SEEDS2 e fluxo de um ensaio (seção 3).
2. Linha temporal do EMS hierárquico, estados e intercâmbio de informações (seção 4).
3. Figura integrada do Estudo I: carga, importação da rede e contribuição FV/bateria nas quatro configurações, no formato que preservar legibilidade.
4. Figura de comparação do Estudo I: evolução do SOC e carga/descarga em C3 e C4, com limites.
5. Figura ou tabela de custo energético modelado, energia importada, energia de fontes e métricas de pico em C1–C4.
6. Figura do ensaio de hierarquia em **topologia física idêntica**: séries de despacho, SOC e/ou custo, mostrando sinais e diferenças entre estratégias.
7. Figura do Estudo II: atendimento de carga e repartição PEMFC/FV/bateria, estados operacionais e limites.
8. Figura do Estudo II: SOC, potência PEMFC e consumo integrado de H₂, se calculados.
9. Tabela sintética de verificação computacional, cobertura das duas topologias e rastreabilidade.

Se a revista limitar figuras, combinar painéis por fenômeno; não sacrificar unidade, legenda e leitura. Figuras de software promocionais são material opcional, não base dos argumentos.

## Indicadores possíveis, sujeitos à formulação executada

### Energia e potência

- Energia da demanda e fornecida por fonte [kWh].
- Energia importada da rede [kWh] e perfil de potência [kW].
- Potência máxima da importação e seu horário [kW].
- Energia gerada/curtailed, quando a variável existir [kWh].
- Energia não atendida e eventual penalização, **somente se prevista pelo modelo** [kWh].
- Balanço energético/resíduo [kW] ou [kWh], com convenção explícita.

### Armazenamento

- SOC inicial e final [%] e trajetória temporal [%].
- Energia de carga e descarga [kWh], com eficiência e sinal definidos.
- Eventos de saturação de limite, potência e reserva.
- Se desejado, throughput de bateria, sem confundi-lo automaticamente com degradação física.

### PEMFC e H₂

- Potência entregue pela PEMFC, variação temporal e limites [kW].
- Consumo de hidrogênio modelado [kg] ou unidade originalmente calculada.
- Auxiliares, eficiência e estados operacionais somente se explicitamente disponíveis.
- Eventuais violações ou atuação de limites de rampa, sem pressupor restrições não implementadas.

### Custos e otimização

- Custo operacional ou de energia **dos termos incluídos** na função objetivo [R$, por exemplo].
- Diferença entre estratégias sobre o mesmo arranjo, com referência denominadora clara.
- Indicadores do solucionador: status, gap, tempo e tolerância quando acessíveis.
- Importância da informação futura sobre decisões de curto prazo, medida por contraste controlado.

## Estrutura da discussão de qualquer figura

**Passo 1 — Observação:** «No intervalo X, a importação passou de A para B kW» (somente quando A e B forem conhecidos).  
**Passo 2 — Relação:** associar ao perfil de carga, geração, preço, limite da bateria ou função objetivo.  
**Passo 3 — Alcance:** interpretar o comportamento dentro da hipótese simulada, sem afirmar comportamento universal de campo.

Esse esquema deriva da identidade autoral aprovada: prosa causal e orgânica, com números antes de interpretações, **sem fórmulas verbais rígidas**.

## O que NÃO deve ser dito sem comprovação

- «Redução de X%» sem base numérica, referência e métricas definidas.
- «Controlador superior» sem comparação metodológica com mesmo problema.
- «Menor custo total do consumidor» quando só se simulou uma tarifa parcial.
- «Validação do modelo» baseada exclusivamente em execução com status ótimo.
- «Autonomia da embarcação» em um cenário de combustível não limitante.
- «Sistema em tempo real» se só houver simulação offline ou horizonte recedente sem requisito temporal demonstrado.
- «Otimização física global» quando foi resolvido um modelo aproximado.
- «Reprodutibilidade garantida» se não houver controle de versões, arquivos, condições e resultados.

## Evidências para eventual submissão

Conservar junto aos resultados: CSVs/JSONs originais, configuração de estudo, identificador e commit de execução, parâmetros, scripts geradores de figuras, tabelas, logs/status do solver e registro de qualquer intervenção manual. Exportar SVG/PDF/PNG quando útil, mas não confundir figura renderizada com dados brutos.
