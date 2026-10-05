# Energy MultiModel V1 — módulo eólico

## Entrada

O modelo aceita CSV com, no mínimo:

- `timestamp`
- `wind_speed`

Campos opcionais:

- `wind_direction`
- `temperature`
- `pressure`
- `humidity`

A interface permite mapear manualmente os nomes de coluna. A pressão pode estar em hPa/mbar ou Pa; a umidade relativa pode estar em 0–1 ou 0–100.

## Hipóteses V1

- A velocidade do vento é assumida na altura do cubo/nacele.
- A direção não altera a potência: yaw ideal.
- Sem wake entre aerogeradores.
- Sem correção de altura, rugosidade ou estabilidade atmosférica.
- A curva do fabricante é tratada como potência elétrica do aerogerador; não são reaplicadas perdas de rotor, caixa ou gerador.
- Existe um switch opcional para descontar exatamente 3% entre a saída elétrica do aerogerador e o ponto de inserção à rede (transformador, linhas, disjuntores e perdas externas equivalentes).

## Densidade do ar

1. Pressão + temperatura + umidade: densidade de ar úmido.
2. Pressão + temperatura: densidade de ar seco.
3. Dados insuficientes: 1,225 kg/m³.

Para o Nordex N117/2400, a V1 utiliza a tabela do fabricante por densidade entre 1,000 e 1,300 kg/m³. Para os demais modelos, utiliza velocidade equivalente por densidade sobre a curva de referência.

## Saídas principais

- potência elétrica unitária;
- potência bruta do conjunto;
- potência após o desconto opcional de 3%;
- energia bruta e líquida;
- fator de capacidade bruto e líquido;
- horas equivalentes;
- horas gerando;
- tempo abaixo de cut-in;
- tempo em potência nominal;
- perfis temporais, curva de potência com pontos operativos e rosa dos ventos;
- CSV detalhado para integração futura.

## Catálogo

A V1 contém seis aerogeradores parametrizados:

- EWT DW61-1MW
- Nordex N117/2400
- Vestas V90-3.0 MW
- Siemens SWT-3.6-120
- WEG AGW 147 / 4.2
- Vestas V164-7.0 MW

Curvas tabuladas diretamente do fabricante são identificadas como tal; curvas extraídas de gráficos permanecem marcadas como digitalizadas.
