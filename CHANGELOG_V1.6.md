# Energy MultiModel V1.6 — integração unificada do EMS

## Mudança principal

O EMS de Marília deixou de ser uma segunda aplicação aberta a partir do Orchestrator. A aplicação principal agora possui um único fluxo e um único estado compartilhado:

**Módulo de Carga → Modelos → Otimizador → Resultados do Otimizador → Resultados dos Modelos → Exportar Resultados**

## Integração real

- `orchestrator_runtime.py` é a nova camada de integração sem UI.
- A carga configurada no Orchestrator é convertida diretamente em `PerfilCarga` do EMS.
- A página **Modelos** ativa/desativa Solar, Eólica, Bateria, H₂/PEMFC e Térmica e guarda seus parâmetros.
- Ao clicar **CALCULAR MODELOS E RODAR OTIMIZAÇÃO**, a mesma aplicação:
  1. executa/caracteriza os modelos físicos ativos;
  2. constrói o pacote de troca interno;
  3. executa o solver EMS;
  4. grava despacho, validação e saídas físicas no estado comum;
  5. abre **Resultados do Otimizador**.
- `ems_app.py` permanece apenas como referência/compatibilidade da ramificação original e não é mais roteada pela aplicação principal.

## Páginas

1. **Visão Geral** — estado real da integração e resumo da última rodada.
2. **Módulo de Carga** — Walk-forward, COPEL ou CSV próprio.
3. **Modelos** — seleção das fontes e parâmetros físicos; clima sintético explícito ou CSV climático para solar/eólica.
4. **Otimizador** — algoritmo, horizonte N, penalidades, custos, eficiências e botão de execução.
5. **Resultados do Otimizador** — despacho, custo, H₂, déficit/vertimento, stacks, SOC e metaheurística × SQP.
6. **Resultados dos Modelos** — séries da mesma rodada EMS, sem dados DEMO.
7. **Exportar Resultados** — CSV e ZIP auditável da rodada integrada.

## Correções V1.5 preservadas

- `P_FC_delivered_kW` entra no balanço com `eta_fc = 1.0`.
- vertimento total inclui excesso renovável e excesso despachável;
- receding horizon cobre até o último minuto da missão.

## Pendências deliberadamente não alteradas

Ver `EMS_TO_TALK_ABOUT.md`.
