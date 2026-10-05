# Energy MultiModel V1.5 — Primeira integração do EMS de Marília

## Objetivo

A V1.5 unifica a ramificação **Energy_MultiModel_V1.4** (Orchestrator + MIX) com a ramificação de Marília que contém o **EMS de despacho ótimo multifonte**, preservando o Orchestrator como entrada principal e o EMS como módulo completo.

## Integração

- adicionados `ems_app.py`, `ems_integration/` e `visualization/ems_plots.py`;
- preservados `orchestrator_app.py`, `mix_app.py`, `simulation/mix_engine.py` e `simulation/orchestrator_demo.py`;
- a página **Otimizador** do Orchestrator agora abre o **EMS real**;
- o protótipo sintético do Orchestrator continua identificado como **MODO TESTE** nas páginas que ainda não foram conectadas diretamente às saídas reais do EMS;
- modelos MATLAB de referência do EMS preservados em `reference_models/ems_matlab/`.

## Correções acordadas

### 1. PEMFC — eliminação da dupla eficiência

Quando `fc_base_potencia = entregue`, o envelope usa `P_FC_delivered_kW`, que já representa a potência líquida após auxiliares e DC/DC. Nessa condição, a fonte entra no balanço com `eta = 1.0`.

A eficiência `eta_dc1` continua disponível somente para a opção legacy baseada em potência bruta do stack.

### 2. Vertimento total

`energia_vertida_kWh` agora representa:

`excesso despachável + excedente solar/eólico não aproveitado`.

Também são expostos separadamente:

- `energia_vertida_despachavel_kWh`;
- `energia_vertida_renovavel_kWh`;
- `custo_vertimento_renovavel_rs`.

A penalidade de vertimento renovável é somada ao custo efetivo da rodada e aos custos por passo, embora seja constante para o solver na arquitetura atual (renováveis must-take).

### 3. Horizonte até o último minuto

O receding horizon não abandona mais os últimos `N-1` pontos. Para uma missão de `Nt` passos, são geradas `Nt` decisões. Nos passos finais o horizonte encolhe automaticamente de `N` para `N-1 ... 1`.

Exemplo validado: 120 pontos de carga → `k_validos = 120`.

## Validação

- `python -m compileall`: OK;
- suíte disponível no ambiente: **41 testes executados, 0 falhas, 8 skips** (skips ligados ao ambiente sem Streamlit);
- caso numérico de 120 pontos confirmou `eta_fc = 1.0` com base entregue e despacho válido no último ponto;
- caso de excedente renovável confirmou `vertimento_total = renovável + despachável` e fechamento entre soma dos custos por passo e custo total reportado.

## Próxima etapa

Conectar as saídas reais do EMS diretamente às páginas **Visão Geral**, **Resultados dos Modelos** e **Exportar Resultados** do Orchestrator, sem alterar ainda as decisões metodológicas listadas em `EMS_TO_TALK_ABOUT.md`.
