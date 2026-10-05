# Módulo Térmico V1.2

O módulo térmico é um modelo **operacional-econômico**, não um simulador termodinâmico de caldeira/turbina.
Ele foi desenhado para fornecer ao futuro EMS/otimizador potência disponível, factibilidade, energia e custo.

## Dinâmica 1 — Usina termelétrica de grande porte

Entradas principais:

- série temporal de potência solicitada [MW];
- curva de inflexibilidade [MW] ou valor constante;
- potência máxima disponível [MW];
- CVU [R$/MWh];
- mínimo técnico opcional [MW];
- rampas de subida/descida opcionais [MW/min].

Para cada intervalo:

```text
P_alvo = max(P_solicitada, P_inflex)
P_entregue = min(P_alvo, Pmax)
C_variavel = P_entregue * Δt * CVU
```

O programa original não é silenciosamente alterado: os intervalos abaixo da inflexibilidade,
acima de Pmax, abaixo do mínimo técnico ou além das rampas são explicitamente marcados como violações.
A aplicação também calcula quanto de energia/custo adicional seria necessário para restaurar a inflexibilidade.

## Dinâmica 2 — Pequena unidade geradora

Representa um grupo gerador de backup rápido, por exemplo diesel.

- não possui inflexibilidade na V1.2;
- recebe uma curva de potência necessária/solicitada;
- entrega até `Pmax`;
- o excesso é contabilizado como potência/energia não atendida;
- contabiliza CVU e um custo fixo opcional por partida;
- cada transição desligado → ligado é contada como uma partida.

```text
P_entregue = min(P_solicitada, Pmax)
C_total = Σ(P_entregue * Δt * CVU) + N_partidas * C_partida
```

Essa dinâmica responde diretamente perguntas como: “se o sistema ficar com déficit por 25 minutos,
quanto custa ligar o gerador e cobrir esse período?”.

## CVU

A aplicação oferece valores de inicialização por combustível, **somente para uso acadêmico**.
Eles permanecem editáveis. O CVU real depende da usina/equipamento e do período, incluindo combustível,
eficiência, logística, transporte, armazenamento, O&M e condições comerciais.

Para casos brasileiros reais, utilizar dados específicos publicados por ONS/CCEE ou pelo agente responsável.

Fontes públicas de referência conceitual:

- ONS Dados Abertos — CVU das Usinas Térmicas: https://dados.ons.org.br/dataset/cvu-usitermica
- CCEE Dados Abertos — Custo Variável Unitário: https://dadosabertos.ccee.org.br/dataset/custo_variavel_unitario_conjuntural

## Fora do escopo da V1.2

- caldeira / combustão / ciclo Rankine ou Brayton;
- heat-rate curve;
- consumo físico de combustível;
- minimum up/down time;
- custos de parada;
- emissões;
- despacho ótimo.

O despacho ótimo será responsabilidade do módulo de otimização; este modelo apenas avalia uma decisão solicitada.
