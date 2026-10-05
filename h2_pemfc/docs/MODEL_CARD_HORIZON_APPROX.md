# Model Card — VLIIPro50-22 / VLSIIPro66-22 aproximado

**Identificador do perfil:** `EQUIVALENT_65KW_HORIZON_CONSTRAINED`  
**Versão auditada:** 1.0 — 3 de agosto de 2026  
**Estado científico:** modelo físico parametrizado aproximado, restrito por dados nominais; sem validação específica no equipamento do Boto H₂.

## 1. Objetivo

Representar, em estudos preliminares de gestão de energia, a resposta elétrica de um sistema PEMFC na escala do Horizon VLIIPro50-22. O modelo recebe corrente ou potência líquida solicitada e calcula tensão, potência bruta, consumo auxiliar equivalente, potência líquida, vazões, calor e limitações operacionais.

O modelo foi desenvolvido para:

- caracterização eletroquímica estática;
- avaliação de solicitações de potência do EMS;
- simulação temporal com partida, desligamento, saturação e rampas;
- geração de dados para integração preliminar com bateria, geração fotovoltaica e otimizador da embarcação.

## 2. Escopo e arquitetura

A implementação é composta por camadas:

1. `PEMFCModel`: equações eletroquímicas da célula;
2. `Equivalent65kWHorizonStackModel`: geometria e limites do stack aproximado;
3. `Equivalent65kWHorizonSystemModel`: DC/DC, consumo auxiliar, H₂, ar e calor;
4. `Equivalent65kWHorizonPowerRequestModel`: inversão potência líquida → corrente;
5. `Equivalent65kWHorizonDynamicModel`: máquina de estados e resposta temporal.

Existe uma única implementação das equações eletroquímicas, em `models/pemfc_model.py`. As demais camadas usam composição.

## 3. Fontes e papel de cada fonte

### 3.1 Estrutura eletroquímica

Altıntaş, N.; Ertan, R. *Modeling of a PEM Fuel Cell System in MATLAB*, OTEKON 2024. A reprodução computacional é preservada no perfil `OTEKON_REFERENCE` e fornece a estrutura matemática e o prior dos parâmetros não identificados novamente.

### 3.2 Curva experimental equivalente

Chen, H. et al. “Research on membrane electrode assembly consistency of high-power proton exchange membrane fuel cell stack.” *CIESC Journal*, 75(2), 637–646, 2024. DOI: `10.11949/0438-1157.20230745`.

Foram utilizados quatro pontos de um stack de outro fabricante, com 210 células e área ativa de 300 cm². Esse conjunto fornece a forma experimental de uma curva PEMFC em escala próxima, mas não é uma medição do produto Horizon.

### 3.3 Restrições do equipamento-alvo

Horizon Fuel Cell Technologies. *VLIIPro50-22 Fuel Cell System User Manual*, V1.3, 7 nov. 2025, Tabela 4.2.

O manual fornece número de células, corrente, tensão, potências, pressões, rampas, tempos operacionais, vazões máximas e outros limites. O manual não publica a área ativa nem a curva completa de polarização do VLSIIPro66-22.

## 4. Equações principais

### 4.1 Célula e stack

\[
V_{cell}=E-V_{act}-V_{ohm}-V_{conc}
\]

\[
V_{stack}=N_{cells}V_{cell}, \qquad I_{stack}=jA_{active}
\]

\[
P_{stack}=V_{stack}I_{stack}
\]

### 4.2 Potência líquida preliminar

\[
P_{net}=\eta_{DC/DC}P_{stack}-P_{aux,eq}
\]

O consumo auxiliar é uma lei agregada:

\[
P_{aux,eq}=P_{aux,nom}\left(\frac{P_{stack}}{P_{stack,ref}}\right)^{n_{aux}}
\]

Ela foi calibrada somente para fechar 50 kW líquidos no ponto nominal calculado.

### 4.3 Hidrogênio

\[
\dot m_{H_2}=\frac{N_{cells}IM_{H_2}}{2FU_{H_2}}
\]

### 4.4 Solicitação de potência

A corrente é obtida numericamente na rama crescente de operação:

\[
P_{net}(I)-P_{requested}=0, \qquad 0\le I\le450\;A
\]

### 4.5 Dinâmica

A referência temporal é mantida por retenção de ordem zero. São aplicados:

- rampa de subida de 2 kW/s;
- rampa de descida de 3,5 kW/s;
- estados `OFF`, `STARTUP`, `IDLE`, `RUN`, `SHUTDOWN` e `FAULT_LIMITED`.

## 5. Parâmetros centrais

| Parâmetro | Valor | Classificação |
|---|---:|---|
| Número de células | 220 | `MANUAL_HORIZON` |
| Área ativa | 300 cm² | `HIPOTESE` |
| Corrente máxima normal | 450 A | `MANUAL_HORIZON` |
| Tensão nominal do stack | 145 V | `MANUAL_HORIZON` |
| Faixa de tensão | 110–220 V | `MANUAL_HORIZON` |
| Potência nominal bruta publicada | 66 kW | `MANUAL_HORIZON` |
| Potência nominal líquida | 50 kW | `MANUAL_HORIZON` |
| Potência de pico | 51 kW | `MANUAL_HORIZON` |
| Pressão nominal ânodo/cátodo | 140/120 kPag | `MANUAL_HORIZON` |
| Eficiência constante do DC/DC | 0,97 | `HIPOTESE` baseada no máximo publicado |
| Utilização de H₂ | 0,97 | `HIPOTESE` conservadora baseada no limite publicado |
| Razão estequiométrica de ar | 2,0 | `HIPOTESE` |
| Expoente do auxiliar agregado | 1,35 | `HIPOTESE` |

Os quatro parâmetros efetivos identificados são:

| Parâmetro | Valor identificado |
|---|---:|
| \(\xi_1\) | −0,8617092428 V |
| \(R_{mem,ref}\) | 0,01697769365 Ω·cm² |
| \(a_{ref}\) | 0,0006012169244 V |
| \(b\) | 1,901875086 cm²/A |

Os demais parâmetros eletroquímicos permanecem ancorados no perfil OTEKON.

## 6. Procedimento de calibração

1. Normalização da curva equivalente por célula e por área ativa;
2. inclusão do ponto nominal Horizon: 450 A, 145 V, 220 células e área assumida de 300 cm²;
3. ajuste de somente quatro parâmetros efetivos;
4. mínimos quadrados não lineares com limites físicos;
5. múltiplos inícios determinísticos;
6. regularização fraca e explícita em relação ao prior OTEKON;
7. diagnóstico de posto, condicionamento e correlação.

Resultados da calibração:

- RMSE nos quatro pontos equivalentes: 3,867 mV/célula;
- erro no ponto nominal Horizon: +0,979 mV/célula;
- erro correspondente em 220 células: +0,215 V;
- correlação máxima entre parâmetros: 0,9993;
- sinalizador de identificabilidade fraca: ativo.

Consequentemente, os coeficientes ajustados devem ser interpretados em conjunto como parâmetros efetivos da curva, e não como propriedades medidas individualmente do equipamento.

## 7. Resultados nominais da configuração preliminar

Em 450 A e nas condições nominais adotadas:

| Grandeza | Resultado aproximado |
|---|---:|
| Densidade de corrente | 1,5 A/cm² |
| Tensão por célula | 0,66007 V |
| Tensão do stack | 145,215 V |
| Potência bruta | 65,347 kW |
| Perda no DC/DC | 1,960 kW |
| Consumo auxiliar equivalente | 13,386 kW |
| Potência líquida | 50,000 kW |
| H₂ fornecido | 3,838 kg/h |
| Ar estimado, \(\lambda=2\) | 70,759 g/s |
| Eficiência elétrica líquida pelo PCI | 39,08% |

## 8. Hipóteses relevantes

- área ativa do Horizon igual a 300 cm²;
- temperatura comum de calibração igual a 353,15 K;
- uso da curva de outro fabricante como referência de forma;
- parâmetros não ajustados herdados do OTEKON;
- eficiência do DC/DC constante;
- consumo auxiliar agregado e não decomposto;
- razão estequiométrica de ar igual a 2;
- temperatura do refrigerante e tensão do barramento ainda informativas na dinâmica;
- ausência de degradação, inundação, secagem, histerese, variação célula a célula e envelhecimento;
- dinâmica térmica e fluidodinâmica não identificadas.

## 9. Limitações

O modelo não permite afirmar desempenho exato, garantia, durabilidade, segurança, consumo real, eficiência certificada ou resposta transitória específica do VLIIPro50-22. O fechamento nominal de 50 kW não valida a forma da curva auxiliar em outras cargas.

A forte correlação paramétrica impede interpretar isoladamente os quatro coeficientes identificados. O ponto de 51 kW é um limite declarado, enquanto a configuração física atual alcança aproximadamente 50 kW na rama de 0–450 A.

## 10. Usos permitidos

- estudos preliminares de despacho do EMS;
- verificação de rampas, saturação e déficit de potência;
- estimativas comparativas de corrente, tensão e consumo de H₂;
- desenvolvimento e teste de interfaces, CSVs e algoritmos;
- análises de sensibilidade claramente identificadas como aproximações;
- planejamento de ensaios e definição de variáveis CAN necessárias.

## 11. Usos não recomendados

- projeto de segurança ou certificação da instalação;
- dimensionamento final de tanque, refrigeração, compressor ou cabos;
- estimativa de garantia, vida útil ou degradação;
- controle direto do equipamento sem validação e salvaguardas do fabricante;
- apresentação dos resultados como medições do VLIIPro50-22;
- extrapolação fora de 0–450 A ou das condições operacionais documentadas.

## 12. Dados necessários para validação futura

São necessários ensaios ou registros CAN sincronizados contendo, no mínimo:

- corrente e tensão do stack;
- tensões mínima, média e máxima das células;
- potência antes e depois do DC/DC;
- potência ou velocidade do compressor;
- potência da bomba, ventiladores e demais auxiliares;
- vazão e pressão do H₂;
- vazão e pressão do ar;
- temperaturas de stack e refrigerante;
- estado operacional e potência solicitada;
- resposta a degraus e rampas;
- condições ambientais e altitude.

Com esses dados, a área ativa poderá ser confirmada, a curva eletroquímica recalibrada e os modelos auxiliar, térmico e dinâmico substituídos por relações identificadas no equipamento.
