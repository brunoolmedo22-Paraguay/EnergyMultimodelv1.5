# Metodologia do modelo PEMFC Horizon aproximado

## 1. Pergunta de modelagem

O projeto precisava representar uma célula a combustível de aproximadamente 50 kW líquidos para estudos do EMS da embarcação, enquanto a implementação inicial reproduzia um modelo acadêmico próximo de 5 kW. O manual do VLIIPro50-22 fornece valores nominais e limites operacionais, mas não publica a curva completa de polarização nem a área ativa da célula.

A solução adotada foi construir uma representação rastreável em camadas, combinando informação de três naturezas distintas sem misturá-las:

- estrutura matemática e prior do OTEKON;
- forma experimental de um stack PEMFC de 65 kW de outro fabricante;
- restrições nominais do manual Horizon VLIIPro50-22 V1.3.

## 2. Preservação da referência OTEKON

O perfil `OTEKON_REFERENCE` permanece congelado. Seus 41 elementos em série, área ativa de 232 cm², parâmetros, curvas da Figura 3 e resultados numéricos são protegidos por testes de regressão. `DEFAULT_PARAMS` continua sendo um alias exclusivo desse perfil.

A arquitetura multiperfil não duplicou as equações. `models/pemfc_model.py` permaneceu idêntico ao arquivo da versão inicial, inclusive em hash SHA-256.

## 3. Preparação dos dados

### 3.1 Curva experimental equivalente

A curva de outro fabricante foi armazenada como corrente e tensão brutas:

| Corrente | Tensão do stack |
|---:|---:|
| 180 A | 150 V |
| 300 A | 147 V |
| 420 A | 140 V |
| 540 A | 133 V |

A publicação informa 210 células e 300 cm². O código deriva:

\[
j=\frac{I}{A}, \qquad V_{cell}=\frac{V_{stack}}{N}
\]

assim como potência e densidade de potência. Os valores derivados não são armazenados como novas medições.

### 3.2 Restrições Horizon

O manual V1.3 fornece, entre outros:

- 220 células;
- 0–450 A;
- 110–220 V, 145 V nominal;
- 66 kW no stack;
- 50 kW nominais e 51 kW de pico no sistema;
- pressões de 140/120 kPag;
- rampas de 2/3,5 kW/s;
- consumo máximo de H₂ de 4,8 kg/h;
- vazão máxima de ar de 80 g/s.

A área ativa de 300 cm² é uma hipótese do projeto, motivada pela proximidade de escala com o stack experimental. Ela não é atribuída ao manual.

## 4. Calibração eletroquímica

Uma única curva não contém informação suficiente para identificar independentemente todos os parâmetros do modelo. Por isso, foram ajustados somente:

- `xi1`;
- `R_mem_ref_ohm_cm2`;
- `concentration_a_ref_V`;
- `concentration_b_cm2_A`.

Os demais coeficientes permanecem no prior OTEKON.

O vetor residual foi separado em três blocos:

\[
r(\theta)=
\begin{bmatrix}
r_{equivalente}(\theta)\\
r_{Horizon}(\theta)\\
r_{prior}(\theta)
\end{bmatrix}
\]

O primeiro bloco compara os quatro pontos equivalentes. O segundo restringe o ponto nominal calculado para 450 A e 145 V. O terceiro aplica regularização fraca e explícita em torno do OTEKON. Pesos, escalas, limites e múltiplos inícios estão registrados nos artefatos da calibração.

O ajuste produziu baixo erro de curva, mas elevada correlação paramétrica. Assim, o resultado é tratado como uma parametrização efetiva, não como identificação de propriedades individuais da MEA Horizon.

## 5. Transferência para a geometria aproximada

O perfil calibrado foi combinado com:

\[
N_{cells}=220, \qquad A=300\;cm^2, \qquad 0\le I\le450\;A
\]

A corrente do stack é convertida em densidade de corrente, o `PEMFCModel` calcula a tensão por célula e a camada de stack deriva tensão total e potência bruta.

No ponto de 450 A, o modelo calcula aproximadamente 145,215 V e 65,347 kW. A proximidade com 145 V e 66 kW mostra consistência nominal, mas não demonstra que a curva intermediária seja a do equipamento.

## 6. Balance of plant preliminar

O manual informa 66 kW no stack e 50 kW no sistema. Como não foi encontrado um mapa completo dos auxiliares, adotou-se:

\[
P_{net}=\eta_{DC/DC}P_{stack}-P_{aux,eq}
\]

com eficiência constante de 0,97 e uma curva auxiliar contínua, não negativa e crescente. A potência auxiliar nominal foi calculada para fechar exatamente 50 kW na condição nominal do modelo. O expoente da curva foi assumido, portanto a decomposição em compressor, bomba, ventiladores e controladores ainda não existe.

O H₂ é calculado pela lei de Faraday, e o ar por estequiometria com razão de excesso configurável. Vazões e calor são comparados aos limites publicados, mas não usados como pontos adicionais de ajuste.

## 7. Operação por potência solicitada

Para integrar o modelo ao EMS, a entrada de operação é potência líquida solicitada, não corrente. O modelo resolve:

\[
P_{net}(I)=P_{requested}
\]

por método acotado na rama crescente entre 0 e 450 A. A curva é amostrada antes de cada solução para detectar não monotonicidade. Solicitações inviáveis são saturadas e devolvem déficit e motivo de limitação.

A região de 10–40 kW é uma recomendação operacional, não um limite rígido. A potência física máxima da parametrização atual é aproximadamente 50 kW, mesmo que o manual declare 51 kW de pico.

## 8. Resposta temporal

A camada dinâmica recebe um perfil do EMS com timestamp, potência solicitada e habilitação. A referência usa retenção de ordem zero em passo interno de 1 s. A máquina de estados representa partida, idle, operação, desligamento e limitação.

A dinâmica é operacional e lógica. Ela não é uma identificação térmica, pneumática ou eletroquímica transitória do produto. Temperatura do refrigerante e tensão do barramento são registradas, mas ainda não alteram as equações físicas.

## 9. Por que o modelo não reproduz experimentalmente o Horizon

A reprodução específica exigiria uma curva medida no próprio VLSIIPro66-22, sua área ativa confirmada, condições completas de temperatura, pressão, umidade e estequiometria, além dos consumos auxiliares em cada carga. Esses dados não estão disponíveis no manual.

A curva usada foi medida em um stack de outro fabricante, e o fechamento de 50 kW foi imposto no balance of plant. Logo, não há base para declarar equivalência experimental com o equipamento-alvo.

## 10. Por que o modelo é representativo de uma escala próxima

A representação é útil porque combina:

- uma curva experimental real de 65 kW;
- geometria e corrente da mesma ordem de grandeza;
- tensão por célula e densidade de corrente fisicamente coerentes;
- número de células e limites publicados do Horizon;
- fechamento explícito entre potência bruta e líquida;
- conservação de massa e energia em primeira aproximação;
- rastreabilidade de cada valor como manual, experimento equivalente, derivação, calibração ou hipótese.

Esse conjunto é suficiente para estudar lógica de despacho, rampas, saturação, déficit e tendências de consumo, desde que a incerteza seja declarada.

## 11. Aplicação em estudos preliminares de EMS

O otimizador fornece `P_FC_requested_kW`. O modelo devolve potência possível, corrente, tensão, consumo de H₂, eficiência, calor e flags. Isso permite ao EMS redistribuir déficits para a bateria e evitar comandos incompatíveis com rampas ou limites.

A integração é adequada para desenvolvimento de software e comparação de estratégias, não para controle final ou certificação.

## 12. Recalibração futura

Quando houver dados CAN ou ensaios do barco, o procedimento deve ser:

1. sincronizar corrente, tensão, potência líquida, auxiliares, vazões, pressões e temperaturas;
2. selecionar patamares estacionários e transientes controlados;
3. confirmar área ativa e unidades;
4. recalibrar a curva eletroquímica com múltiplas condições;
5. substituir a curva auxiliar agregada por mapas medidos;
6. identificar dinâmica térmica e do compressor;
7. separar conjuntos de calibração e validação;
8. publicar erros fora da amostra e intervalos de incerteza;
9. versionar um novo perfil sem alterar `OTEKON_REFERENCE`.

Até essa etapa, o nome `EQUIVALENT_65KW_HORIZON_CONSTRAINED` e os avisos de escopo devem ser mantidos.
