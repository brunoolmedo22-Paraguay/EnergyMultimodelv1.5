# Evidência executada — Piso 3C-2 (gerada por `python -m ems_v2.mpc.evidencia`)

- Data (UTC): 2026-11-09T12:10:46+00:00 · commit: `a7b2a4622f78b30c5111ebca5cc257c48eb83a24`
- Python 3.13.18 · Linux-6.18.44-fc-v310-x86_64-with-glibc2.39 · 4 CPUs · x86_64
- Pyomo 6.10.1 · highspy 1.15.1 · HiGHS 1.15.1 · interface `pyomo.contrib.solver:highs` · configuração `CONFIG_ANALITICA` (gaps nulos, 1 thread, semente 0)

Simulação causal de laço fechado **ALGÉBRICA** (planta = dublê 3C-1) sobre fixtures sintéticas — **não é validação física** nem afirmação de desempenho de tempo real.

## 1. Experimentos E1–E8

| Exp. | N/m | Desfecho | Classe de falha | Registros | Aplicados | Custo realizado (R$) | E_final banco (kWh) | Obrigações pendentes no fim (s) | Auditoria independente | Nota |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 oráculo MPC (ablação) | 4/2 | `concluida` | — | 4 | 8 | 2.075 | 2.5 | — | aprovada | previsão perfeita DECLARADA |
| E1 oráculo horizonte completo | 8/8 | `concluida` | — | 1 | 8 | 2.075 | 2.5 | — | aprovada | referência de ablação |
| E2 previsão reemitida | 4/2 | `concluida_com_obrigacoes_pendentes` | — | 4 | 8 | 12.9 | 2.5 | {'syn-fc': 900} | aprovada | FV prevista 10 → 25 após observar o degrau |
| E3 open-loop | 8/8 | `concluida` | — | 1 | 8 | 18.7 | 3.55271e-15 | — | aprovada | uma decisão em τ_0 |
| E3 MPC | 4/2 | `concluida_com_obrigacoes_pendentes` | — | 4 | 8 | 12.9 | 2.5 | {'syn-fc': 900} | aprovada | mesma informação/planta/regras |
| E4 m = 1 | 4/1 | `concluida_com_obrigacoes_pendentes` | — | 8 | 8 | 7.2625 | 1.25 | {'syn-fc': 1800} | aprovada | 8 resoluções |
| E4 m = 2 | 4/2 | `concluida_com_obrigacoes_pendentes` | — | 4 | 8 | 12.9 | 2.5 | {'syn-fc': 900} | aprovada | 4 resoluções |
| E4 m = 4 | 4/4 | `concluida_com_obrigacoes_pendentes` | — | 2 | 8 | 12.9 | 2.5 | {'syn-fc': 900} | aprovada | 2 resoluções |
| E5 memória (T_on em 3 janelas) | 2/1 | `concluida` | — | 8 | 8 | 10.075 | 20 | — | aprovada | u = [0, 0, 0, 1, 1, 1, 0, 0] |
| E7 sem solução na janela 1 | 4/2 | `interrompida` | falha_solver | 2 | 2 | 1.7 | 10 | — | aprovada | planta parada em g = 2 |
| E8 revisão tardia (registrar_sem_reconciliar) | 4/2 | `concluida_com_obrigacoes_pendentes` | — | 4 | 8 | 12.9 | 2.5 | {'syn-fc': 900} | aprovada | revisão do FV de g = 1 após τ_2 |
| E8 revisão tardia (interromper) | 4/2 | `interrompida` | revisao_tardia | 3 | 4 | 3.7 | 0 | — | aprovada | revisão do FV de g = 1 após τ_2 |

## 2. Comparações (sem veredito; energia final e obrigações não valoradas — 3C-4)

### E3 open-loop × MPC — comparável: True (causal)

| Grandeza | open_loop | mpc | mpc − open_loop |
|---|---|---|---|
| custo_realizado_total_R | 18.7 | 12.9 | -5.8 |
| intervalos_aplicados | 8 | 8 | 0 |
| custo_realizado_R[combustivel_h2] | 12.2 | 6.15 | -6.05 |
| custo_realizado_R[curtailment_operacional] | 4.5 | 1.5 | -3 |
| custo_realizado_R[eventos] | 1 | 4 | 3 |
| custo_realizado_R[throughput_bess] | 1 | 1.25 | 0.25 |
| E_curtailment_kWh | 22.5 | 7.5 | -15 |
| E_final_kWh[syn-bess] | 3.55271e-15 | 2.5 | 2.5 |
| E_geracao_kWh[syn-fc] | 20 | 7.5 | -12.5 |
| partidas[syn-fc] | 0 | 1 | 1 |
| paradas[syn-fc] | 1 | 2 | 1 |
| resolucoes | 1 | 4 | 3 |

Desfechos: A = 'concluida', B = 'concluida_com_obrigacoes_pendentes'. Sem veredito: diferenças de energia final armazenada (E_final_kWh) e obrigações pendentes não são valoradas (valor futuro = 3C-4).

### E4 m = 2 × m = 1 — comparável: True (causal)

| Grandeza | m2 | m1 | m1 − m2 |
|---|---|---|---|
| custo_realizado_total_R | 12.9 | 7.2625 | -5.6375 |
| intervalos_aplicados | 8 | 8 | 0 |
| custo_realizado_R[combustivel_h2] | 6.15 | 2.45 | -3.7 |
| custo_realizado_R[curtailment_operacional] | 1.5 | 0.75 | -0.75 |
| custo_realizado_R[eventos] | 4 | 3 | -1 |
| custo_realizado_R[throughput_bess] | 1.25 | 1.0625 | -0.1875 |
| E_curtailment_kWh | 7.5 | 3.75 | -3.75 |
| E_final_kWh[syn-bess] | 2.5 | 1.25 | -1.25 |
| E_geracao_kWh[syn-fc] | 7.5 | 2.5 | -5 |
| partidas[syn-fc] | 1 | 1 | 0 |
| paradas[syn-fc] | 2 | 1 | -1 |
| resolucoes | 4 | 8 | 4 |

Desfechos: A = 'concluida_com_obrigacoes_pendentes', B = 'concluida_com_obrigacoes_pendentes'. Sem veredito: diferenças de energia final armazenada (E_final_kWh) e obrigações pendentes não são valoradas (valor futuro = 3C-4).

### E1 oráculo N = 8 × oráculo MPC (referência) — comparável: True (referencia_oraculo)

| Grandeza | orac_N8 | orac_mpc | orac_mpc − orac_N8 |
|---|---|---|---|
| custo_realizado_total_R | 2.075 | 2.075 | 0 |
| intervalos_aplicados | 8 | 8 | 0 |
| custo_realizado_R[combustivel_h2] | 0.2 | 0.2 | 0 |
| custo_realizado_R[curtailment_operacional] | 0 | 0 | 0 |
| custo_realizado_R[eventos] | 1 | 1 | 0 |
| custo_realizado_R[throughput_bess] | 0.875 | 0.875 | 0 |
| E_curtailment_kWh | 0 | 0 | 0 |
| E_final_kWh[syn-bess] | 2.5 | 2.5 | 0 |
| E_geracao_kWh[syn-fc] | 0 | 0 | 0 |
| partidas[syn-fc] | 0 | 0 | 0 |
| paradas[syn-fc] | 1 | 1 | 0 |
| resolucoes | 1 | 4 | 3 |

Desfechos: A = 'concluida', B = 'concluida'. Sem veredito: diferenças de energia final armazenada (E_final_kWh) e obrigações pendentes não são valoradas (valor futuro = 3C-4).

## 3. Não antecipatividade por intervenção

Verdades iguais até τ_2 e diferentes depois: 2 decisão(ões) com k <= 2 comparadas; divergências: nenhuma ⇒ não antecipativo: **True**.

## 4. Campanha de tempos de resolução (indicativa)

Cada missão executada 5 vez(es) nesta máquina; estatísticas por PERCENTIL DE POSTO MAIS PRÓXIMO sobre TODAS as resoluções (n = tamanho da amostra). Sem caráter de garantia de tempo real.

| Missão | K/N/m | n resoluções | Var. / bin. / restr. (máx.) | solver p50 / p95 / p99 / máx. (s) | total resolução p50 / p95 / p99 / máx. (s) |
|---|---|---|---|---|---|
| E2 (K = 8, N = 4, m = 2) | 8/4/2 | 20 | 53 / 20 / 73 | 0.0109 / 0.0117 / 0.0129 / 0.0129 | 0.0168 / 0.0264 / 0.0514 / 0.0514 |
| K = 32, N = 8, m = 2 | 32/8/2 | 80 | 105 / 40 / 147 | 0.0208 / 0.0679 / 0.0739 / 0.0739 | 0.0304 / 0.0759 / 0.0816 / 0.0816 |
| K = 32, N = 16, m = 4 | 32/16/4 | 40 | 209 / 80 / 289 | 0.0315 / 0.4729 / 0.4966 / 0.4966 | 0.0447 / 0.4821 / 0.5053 / 0.5053 |
