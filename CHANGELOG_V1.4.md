# Energy MultiModel V1.4 — Orquestração / Visualizador de Resultados

## Nova arquitetura de uso

A aplicação deixa de abrir na biblioteca de modelos e passa a abrir no **console operacional coordenado**, organizado em seis páginas:

1. **Visão Geral** — despacho consolidado, KPIs, participação por fonte, SOC, excedente e alertas.
2. **Módulo de Carga** — criação/entrada da curva de demanda, KPIs e contrato CSV.
3. **Otimizador** — runner, fontes ativas, preferências de despacho, status e diagnóstico da rodada.
4. **Resultados dos Modelos** — solicitado × entregue, estados e limites de cada fonte.
5. **Testar Modelos** — antiga lógica de acesso individual a Solar, Eólica, Térmica, Bateria, H₂ e MIX.
6. **Exportar Resultados** — CSVs e pacote ZIP da rodada.

## Modo teste

O otimizador definitivo ainda não foi integrado. A V1.4 inclui `simulation/orchestrator_demo.py`, que gera um cenário determinístico de 24 h / 15 min com:

- curva sintética de demanda;
- disponibilidade solar e eólica;
- carga/descarga da bateria com SOC;
- geração H₂ / PEMFC;
- geração térmica;
- excedente e energia não atendida;
- preferências sintéticas para preservar bateria, preservar H₂ ou penalizar térmica.

O objetivo deste motor é **validar a interface, contratos de dados e fluxo de uso**, não substituir o solver final.

## Compatibilidade

Os modelos existentes não foram removidos. Permanecem acessíveis pela página **Testar Modelos**.
