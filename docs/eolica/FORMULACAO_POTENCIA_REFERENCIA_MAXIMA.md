# Potência de referência, pico de curva e domínio eólico — contrato v2

Missão eólica autorizada, base `10365c5478b4dd137906b58819cd7f71d8de9cea`. Nenhuma alteração em ciência solar, bateria, PEMFC, EMS V2 ou administração do Gestor.

## Magnitudes distintas

- `rated_power_kw`: nominal do fabricante (Grupo A) ou referência secundária do arquivo a 11 m/s (Grupo B, confirmação primária pendente). Nunca substituída pelo pico.
- `curve_peak_power_kw`: máximo elétrico dos pontos originais admitidos, com SHA-256. Não é potência nominal certificada.
- `operating_power_limit_kw`: teto numérico da curva aplicável; igual ao pico documentado. NÃO é limite mecânico, térmico ou eletrônico certificado. Nos quatro pendentes é utilizável apenas na análise da tabela.
- `curve_valid_wind_range_mps`: extremos dos dados; último ponto medido não é cut-out.

Seis entradas V1 permanecem intactas, inclusive metadados, extrapolação e recorte históricos. V2 é opt-in por `schema_version=2`. Não corrige retrospectivamente a física V1 nem reclassifica suas fontes.

## Interpolação e atmosfera

Interpolação linear entre pontos originais, m/s e kW, sem suavização, meseta inventada ou eficiências internas adicionais. O avaliador de coordenadas `evaluate_documented_curve` reproduz TODOS os nós, inclusive observações negativas e a potência operativa tabulada em cut-out. Ele NÃO simula o controlador.

A simulação física `run_wind_model`, para os três aprovados, usa a correção existente `v_eq = v_hub (rho/rho_ref)^(1/3)`. É uma aproximação SEEDS2, não uma família certificada de curvas a outras densidades. Vento fornecido é no buje: não se corrige altura. Vento real e equivalente devem estar no domínio em estados operativos. Fora dele: `ValueError`, condição não modelada, sem resultado parcial aparentemente válido. Estados de parada conhecidos usam vento REAL: abaixo de cut-in e a partir de cut-out, zero por regra documentada. Não se aplica artificialmente cut-in à velocidade equivalente.

Temperatura/pressão/umidade faltantes mantêm a lógica histórica explicitamente rotulada; dados atmosféricos fornecidos inválidos e densidade calculada inválida são rejeitados em V2, não substituídos silenciosamente por ar padrão. As três curvas publicam rho=1,225 kg/m³. Nos pequenos rho é `None`, não 1,225 por suposição. Vestas registra re-cut-in de 20 m/s, mas não há histerese/controlador transitório: o uso é energético estático.

## Negativos e contabilidade

Para análise de tabela elétrica líquida: `G=max(P,0)`, `A=max(-P,0)`, `N=G-A`. `A` é importação líquida observada atribuível a auxiliares, não medição de todos os consumos internos quando há geração. Não se deduz geração bruta interna oculta a partir de uma curva líquida. A tabela original e sua coluna Cp são preservadas byte a byte.

Para N unidades: `G_N=N*G`, `A_N=N*A`. Desconto externo opcional: `N_grid=0,97*G_N-A_N`. Aplica-se uma única vez sobre geração exportada; NÃO reduz importações negativas. Sem desconto, `N_grid=G_N-A_N`. Energias por amostras representativas são somas de potência vezes passo em horas. Passo e quantidade devem ser finitos/positivos e quantidade inteira. O balanço é `E_net=E_gen-E_consumida-E_perda_externa`.

Nos três modelos aprovados (curvas não negativas), a V1 continua fornecendo `power_gross_kw` (elétrica de curva, não potência interna do rotor) e `power_net_kw` após desconto externo. Nos pequenos, `analyze_wind_curve` retorna colunas distintas e `analysis_only=True`: NÃO gera um pacote utilizável pelo EMS. `run_wind_model` rejeita os quatro; `missing_required` os classifica como pendentes, impedindo o plano de simulação do Gestor. Permanecem selecionáveis, registráveis e analisáveis no catálogo único.

## Indicadores e critérios

Potência instalada continua `rated_power_kw*quantidade`; pico agregado é uma magnitude separada. Denominador do fator de capacidade e horas equivalentes: referência instalada vezes duração. Não saturar FC a 100%; referência em 11 m/s pode ser inferior ao pico. Horas de referência usam >=99% da referência; na análise, geração é estritamente >0, enquanto o limiar histórico V1 permanece intacto.

Validador nominal: erro relativo de pico vs nominal (1% para as três tabelas). Validador de referência em velocidade: compara P interpolada na velocidade declarada, não no pico; tolerância deve ser explícita. Não usa margem absoluta de 10 kW para os novos. Para os quatro pequenos, 1% é APENAS um filtro numérico de leitura, herdado do protocolo Work, não incerteza do ensaio nem aprovação. Aprovação primária permanece pendente mesmo se o filtro passar. Kestrel e400nb (1,6864%) e SWIFT (9,7647%) não passam esse filtro a 11 m/s; não alteramos seus pontos nem sua referência para aprová-lo.
