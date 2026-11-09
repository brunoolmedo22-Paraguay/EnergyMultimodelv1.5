# Piso 3C-4 — Evidencia de ejecución (sintética, algebraica)

> Generada en la rama de la misión 3C-4 sobre `main` `10365c5`. **Rótulo:** simulación causal de lazo cerrado
> ALGEBRAICA sobre fixtures/tarifas SINTÉTICAS (`ems_v2/fixtures_3c4.py`); ningún número es validación física, factura
> real ni desempeño de tiempo real. Los tiempos valen SOLO para el ambiente impreso (4 CPU compartidas; indicativos).

## 1. Pruebas realmente ejecutadas

### 1a. Entrega original (commit `9630e73`, 2026-11-09)

| Comando | Resultado |
|---|---|
| `python -m pytest tests/ems_v2 -q` (línea de base en `10365c5`, antes de cambiar nada) | **1080 passed** |
| `tests/ems_v2/test_ems_v2_3c4_*.py` | **101 passed** |
| `tests/ems_v2` (rama) / sin Pyomo-HiGHS | **1181 passed** / **794 passed, 42 skipped** |
| `python -m pytest tests/ -q` | **1635 passed, 7 warnings, 128 subtests** (445,4 s) |

### 1b. Tras la auditoría del PR #17 (correcciones en `c964a2e`)

| Comando | Resultado |
|---|---|
| `tests/ems_v2/test_ems_v2_3c4_auditoria_pr17.py` (nueva suite A01/A02/B3C4-01) | **38 passed** |
| `tests/ems_v2/test_ems_v2_3c4_*.py` (H1–H18 + auditoría) | **139 passed** (101 + 38; la prueba obsoleta de H9 fue sustituida) |
| `tests/ems_v2 -k "isolamento or perfil"` (guardias, incl. `test_hotfix_b3c4_01_restrito_a_projecao_numerica`) | **52 passed** |
| `tests/ems_v2` con Pyomo/HiGHS (incl. G1–G15, E1–E8 con huellas `pins_3c2_base_a4c6b1c.json`, 3C-0, 3C-1) | **1220 passed (= 1181 + 38 + 1 guardia del hotfix)** |
| `tests/ems_v2` con Pyomo/HiGHS **bloqueados** (buscador de metapath ⇒ `ModuleNotFoundError`) | **812 passed, 63 skipped** |
| `python -m pytest tests/ -q` (suite completa) | **1674 passed, 7 warnings, 128 subtests (449,9 s) = 1635 + 39** |
| `python -m ems_v2.milp.evidencia_3c4` | salida literal en §2 (78,4 s) |

Todas con `PYTHONDONTWRITEBYTECODE=1`, Python 3.13.18, Pyomo 6.10.1, HiGHS 1.15.1 (`CONFIG_ANALITICA`: 1 hilo, gap 0,
semilla 0).

## 2. Salida literal de `python -m ems_v2.milp.evidencia_3c4` (regenerada en `c964a2e`)

### Ambiente

```json
{"cpus": 4, "plataforma": "Linux-6.18.44-fc-v338-x86_64-with-glibc2.39", "processador": "x86_64", "python": "3.13.18", "solver": {"disponivel": true, "divergencias": [], "erro": null, "fixadas": {"highspy": "1.15.1", "pyomo": "6.10.1"}, "interface": "pyomo.contrib.solver:highs", "versao_highs": "1.15.1", "versoes": {"highspy": "1.15.1", "pyomo": "6.10.1"}}}
```

### Campanha (estratégias × cenários)

| Cenário | Estratégia | Situação | k final | Custo realizado [R$] | E final [kWh] | Degradadas | Avaliações planejador | Certificados A02 (inviável/total) | Projeções B3C4-01 | Tempo planejador [s] | Tempo total [s] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| h1_tarifa_plana | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.28 |
| h1_tarifa_plana | mpc_sem_sinal | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.22 |
| h1_tarifa_plana | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.23 |
| h1_tarifa_plana | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 93 | 0/0 | 0 | 1.327 | 1.61 |
| h1_tarifa_plana | hier_local | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 30 | 0/0 | 0 | 0.438 | 0.73 |
| h1_tarifa_plana | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.187 | 0.46 |
| h1_tarifa_plana | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.188 | 0.47 |
| h1_tarifa_plana | oraculo | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h2_pico_futuro | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h2_pico_futuro | mpc_sem_sinal | encerrada | 12 | 60.40 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.23 |
| h2_pico_futuro | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.29 |
| h2_pico_futuro | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 93 | 0/0 | 0 | 1.384 | 1.68 |
| h2_pico_futuro | hier_local | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 1 | 31 | 0/0 | 0 | 0.472 | 0.76 |
| h2_pico_futuro | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.236 | 0.49 |
| h2_pico_futuro | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.182 | 0.45 |
| h2_pico_futuro | oraculo | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h3_pico_no_horizonte_curto | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h3_pico_no_horizonte_curto | mpc_sem_sinal | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.23 |
| h3_pico_no_horizonte_curto | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.26 |
| h3_pico_no_horizonte_curto | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 93 | 0/0 | 0 | 1.374 | 1.66 |
| h3_pico_no_horizonte_curto | hier_local | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 30 | 0/0 | 0 | 0.486 | 0.80 |
| h3_pico_no_horizonte_curto | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.189 | 0.46 |
| h3_pico_no_horizonte_curto | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.181 | 0.46 |
| h3_pico_no_horizonte_curto | oraculo | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h5_erro_previsao | open_loop | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h5_erro_previsao | mpc_sem_sinal | encerrada | 12 | 71.40 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.23 |
| h5_erro_previsao | mpc_encolhido | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.25 |
| h5_erro_previsao | hier_pwl | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 93 | 0/0 | 0 | 1.427 | 1.72 |
| h5_erro_previsao | hier_local | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 1 | 31 | 0/0 | 0 | 0.471 | 0.76 |
| h5_erro_previsao | hier_ref_dura | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.186 | 0.44 |
| h5_erro_previsao | hier_ref_branda | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.187 | 0.51 |
| h5_erro_previsao | oraculo | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.04 |
| h7_limite_importacao | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h7_limite_importacao | mpc_sem_sinal | interrompida/inviavel | 7 | 27.75 | {"syn-bess": 5.0} | 0 | 0 | — | 0 | — | 0.14 |
| h7_limite_importacao | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.23 |
| h7_limite_importacao | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 106 | 5/5 | 0 | 1.269 | 1.54 |
| h7_limite_importacao | hier_local | interrompida/inviavel | 7 | 30.10 | {"syn-bess": 10.0} | 3 | 23 | 0/0 | 0 | 0.374 | 0.56 |
| h7_limite_importacao | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.181 | 0.43 |
| h7_limite_importacao | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.171 | 0.42 |
| h7_limite_importacao | oraculo | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h8_indisponibilidade_pcc | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h8_indisponibilidade_pcc | mpc_sem_sinal | interrompida/inviavel | 7 | 27.75 | {"syn-bess": 5.0} | 0 | 0 | — | 0 | — | 0.14 |
| h8_indisponibilidade_pcc | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.21 |
| h8_indisponibilidade_pcc | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 106 | 5/5 | 0 | 1.380 | 1.65 |
| h8_indisponibilidade_pcc | hier_local | interrompida/inviavel | 7 | 30.10 | {"syn-bess": 10.0} | 3 | 23 | 0/0 | 0 | 0.314 | 0.51 |
| h8_indisponibilidade_pcc | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.160 | 0.40 |
| h8_indisponibilidade_pcc | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.164 | 0.42 |
| h8_indisponibilidade_pcc | oraculo | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h9_pemfc | open_loop | encerrada | 12 | 127.60 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.05 |
| h9_pemfc | mpc_sem_sinal | interrompida/integridade | 10 | 109.75 | {"syn-bess": 5.0} | 0 | 0 | — | 1 | — | 0.25 |
| h9_pemfc | mpc_encolhido | encerrada | 12 | 127.60 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.42 |
| h9_pemfc | hier_pwl | encerrada | 12 | 129.60 | {"syn-bess": 0.0} | 0 | 174 | 0/0 | 0 | 3.447 | 3.85 |
| h9_pemfc | hier_local | encerrada | 12 | 129.60 | {"syn-bess": 0.0} | 1 | 33 | 0/0 | 0 | 0.742 | 1.11 |
| h9_pemfc | hier_ref_dura | interrompida/integridade | 10 | 109.55 | {"syn-bess": 5.0} | 0 | 11 | 0/0 | 1 | 0.245 | 0.59 |
| h9_pemfc | hier_ref_branda | encerrada | 12 | 129.60 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.269 | 0.63 |
| h9_pemfc | oraculo | encerrada | 12 | 127.60 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.05 |
| h17_dois_bancos | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 0 | — | 0 | — | 0.05 |
| h17_dois_bancos | mpc_sem_sinal | encerrada | 12 | 55.50 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 0 | — | 0 | — | 0.25 |
| h17_dois_bancos | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 0 | — | 0 | — | 0.29 |
| h17_dois_bancos | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 129 | 0/0 | 0 | 2.325 | 2.66 |
| h17_dois_bancos | hier_local | encerrada | 12 | 50.30 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 1 | 41 | 0/0 | 0 | 0.792 | 1.13 |
| h17_dois_bancos | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 12 | 0/0 | 0 | 0.215 | 0.51 |
| h17_dois_bancos | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 12 | 0/0 | 0 | 0.238 | 0.54 |
| h17_dois_bancos | oraculo | encerrada | 12 | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 0 | — | 0 | — | 0.04 |

### Efeitos separados

| Cenário | Efeito | a − b | Diferença [R$] | Comparável | Motivo |
|---|---|---|---|---|---|
| h1_tarifa_plana | reotimizacao | open_loop − mpc_encolhido | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h1_tarifa_plana | antecipacao | mpc_sem_sinal − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h1_tarifa_plana | metodo_hier_local_vs_pwl | hier_local − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h1_tarifa_plana | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h1_tarifa_plana | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h1_tarifa_plana | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h1_tarifa_plana | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h2_pico_futuro | reotimizacao | open_loop − mpc_encolhido | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h2_pico_futuro | antecipacao | mpc_sem_sinal − hier_pwl | 10.20 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h2_pico_futuro | metodo_hier_local_vs_pwl | hier_local − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h2_pico_futuro | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h2_pico_futuro | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h2_pico_futuro | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | 10.20 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h2_pico_futuro | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h3_pico_no_horizonte_curto | reotimizacao | open_loop − mpc_encolhido | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h3_pico_no_horizonte_curto | antecipacao | mpc_sem_sinal − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h3_pico_no_horizonte_curto | metodo_hier_local_vs_pwl | hier_local − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h3_pico_no_horizonte_curto | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h3_pico_no_horizonte_curto | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h3_pico_no_horizonte_curto | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h3_pico_no_horizonte_curto | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h5_erro_previsao | reotimizacao | open_loop − mpc_encolhido | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h5_erro_previsao | antecipacao | mpc_sem_sinal − hier_pwl | 10.20 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h5_erro_previsao | metodo_hier_local_vs_pwl | hier_local − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h5_erro_previsao | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h5_erro_previsao | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h5_erro_previsao | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | 10.20 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h5_erro_previsao | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h7_limite_importacao | reotimizacao | open_loop − mpc_encolhido | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h7_limite_importacao | antecipacao | mpc_sem_sinal − hier_pwl | — | NÃO | missão não concluída (mpc_sem_sinal: interrompida/inviavel; hier_pwl: encerrada/None): custos acumulados NÃO c |
| h7_limite_importacao | metodo_hier_local_vs_pwl | hier_local − hier_pwl | — | NÃO | missão não concluída (hier_local: interrompida/inviavel; hier_pwl: encerrada/None): custos acumulados NÃO comp |
| h7_limite_importacao | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h7_limite_importacao | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h7_limite_importacao | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | — | NÃO | missão não concluída (mpc_sem_sinal: interrompida/inviavel; oraculo: encerrada/None): custos acumulados NÃO co |
| h7_limite_importacao | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h8_indisponibilidade_pcc | reotimizacao | open_loop − mpc_encolhido | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h8_indisponibilidade_pcc | antecipacao | mpc_sem_sinal − hier_pwl | — | NÃO | missão não concluída (mpc_sem_sinal: interrompida/inviavel; hier_pwl: encerrada/None): custos acumulados NÃO c |
| h8_indisponibilidade_pcc | metodo_hier_local_vs_pwl | hier_local − hier_pwl | — | NÃO | missão não concluída (hier_local: interrompida/inviavel; hier_pwl: encerrada/None): custos acumulados NÃO comp |
| h8_indisponibilidade_pcc | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h8_indisponibilidade_pcc | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h8_indisponibilidade_pcc | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | — | NÃO | missão não concluída (mpc_sem_sinal: interrompida/inviavel; oraculo: encerrada/None): custos acumulados NÃO co |
| h8_indisponibilidade_pcc | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h9_pemfc | reotimizacao | open_loop − mpc_encolhido | -0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h9_pemfc | antecipacao | mpc_sem_sinal − hier_pwl | — | NÃO | missão não concluída (mpc_sem_sinal: interrompida/integridade; hier_pwl: encerrada/None): custos acumulados NÃ |
| h9_pemfc | metodo_hier_local_vs_pwl | hier_local − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h9_pemfc | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | — | NÃO | missão não concluída (hier_ref_dura: interrompida/integridade; hier_pwl: encerrada/None): custos acumulados NÃ |
| h9_pemfc | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h9_pemfc | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | — | NÃO | missão não concluída (mpc_sem_sinal: interrompida/integridade; oraculo: encerrada/None): custos acumulados NÃO |
| h9_pemfc | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 2.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | reotimizacao | open_loop − mpc_encolhido | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | antecipacao | mpc_sem_sinal − hier_pwl | 5.30 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | metodo_hier_local_vs_pwl | hier_local − hier_pwl | 0.10 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | 5.30 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |

### H9 — PEMFC: estados finais, memória e obrigações

| Estratégia | Situação | k final | Custo [R$] | E final [kWh] | PEMFC ligada / p [kW] / tempo no estado [s] | Obrigações pendentes | Projeções B3C4-01 (k, limite, correção kWh) | Falha |
|---|---|---|---|---|---|---|---|---|
| mpc_sem_sinal | interrompida | 10 | 109.75 | [5.000000000000001] | True / 20.0 / 18000 | {} | [(8, 'superior', 1.7763568394002505e-15)] | [intercambio_programado_invalido] resultado.intercambio[P_imp]: Exigidos 2 valores reais f |
| hier_pwl | encerrada | 12 | 129.6 | [0.0] | True / 5.0 / 25200 | {} | [] | — |
| hier_ref_dura | interrompida | 10 | 109.55 | [5.000000000000001] | True / 20.0 / 18000 | {} | [(8, 'superior', 1.7763568394002505e-15)] | [intercambio_programado_invalido] resultado.intercambio[P_imp]: Exigidos 2 valores reais f |
| hier_ref_branda | encerrada | 12 | 129.6 | [0.0] | True / 5.0 / 25200 | {} | [] | — |
| mpc_encolhido | encerrada | 12 | 127.60000000000001 | [0.0] | True / 5.0 / 18000 | {} | [] | — |
| open_loop | encerrada | 12 | 127.6 | [0.0] | True / 5.0 / 18000 | {} | [] | — |
| oraculo | encerrada | 12 | 127.6 | [0.0] | True / 5.0 / 18000 | {} | [] | — |

### H13 — horizonte curto × longo (H2)

| N | H_L | MPC sem sinal [R$] | Hierárquico PWL [R$] | Avaliações | Tempo planejador [s] |
|---|---|---|---|---|---|
| 2 | 3 | 65.30 | 60.40 | 102 | 1.039 |
| 2 | 6 | 65.30 | 50.60 | 102 | 1.526 |
| 2 | 8 | 65.30 | 50.40 | 102 | 1.525 |
| 2 | 10 | 65.30 | 50.20 | 102 | 1.691 |
| 2 | 12 | 65.30 | 50.20 | 102 | 1.721 |
| 3 | 4 | 60.40 | 55.50 | 93 | 0.917 |
| 3 | 6 | 60.40 | 50.60 | 93 | 1.337 |
| 3 | 8 | 60.40 | 50.40 | 93 | 1.498 |
| 3 | 10 | 60.40 | 50.20 | 93 | 1.386 |
| 3 | 12 | 60.40 | 50.20 | 93 | 1.493 |
| 4 | 5 | 55.50 | 50.60 | 84 | 0.840 |
| 4 | 6 | 55.50 | 50.60 | 84 | 1.182 |
| 4 | 8 | 55.50 | 50.40 | 84 | 1.190 |
| 4 | 10 | 55.50 | 50.20 | 84 | 1.223 |
| 4 | 12 | 55.50 | 50.20 | 84 | 1.242 |

### H6/H10 — λ(E) na fronteira b = 9 (τ_6, H2)

| Segmento E [kWh] | V nos extremos [R$] | λ_E = −dV/dE [R$/kWh] |
|---|---|---|
| [0, 5] | 25.0000 → 17.5500 | 1.4900 |
| [5, 10] | 17.5500 → 10.1000 | 1.4900 |
| [10, 15] | 10.1000 → 7.6500 | 0.4900 |
| [15, 20] | 7.6500 → 5.2000 | 0.4900 |

### H4 — λ₀ × posição do pico

| Perfil (previsão causal) | λ₀ em τ_0 (E ∈ [0, 5]) [R$/kWh] |
|---|---|
| plana 0,5 | 0.4900 |
| pico h4–5 | 1.4900 |
| pico h6–7 | 1.4900 |
| pico h8–9 | 0.5100 |

### Custo computacional (H2)

| Configuração | Custo [R$] | Janelas válidas/degradadas | Avaliações | Planejador [s] | Erro máx. [R$] |
|---|---|---|---|---|---|
| PWL pontos=3, máx 9 | 50.20 | 12/0 | 61 | 0.909 | 3.55e-15 |
| PWL pontos=5, máx 9 | 50.20 | 12/0 | 93 | 1.497 | 3.55e-15 |
| PWL pontos=4, máx 4 (sem refinamento) | 55.50 | 7/5 | 75 | 1.154 | 1.67 |
| periódica P=2 | 50.20 | 12/0 | 87 | 1.305 | 3.55e-15 |
| periódica P=3 | 50.20 | 12/0 | 85 | 1.359 | 3.55e-15 |
| periódica P=4 | 50.20 | 12/0 | 84 | 1.226 | 3.55e-15 |

_Tempo total da evidência: 78.4 s (só este ambiente)._

## 3. Lectura (sin extrapolación)

* **Las correcciones no cambian ningún costo** de H1, H2, H3, H5, H7, H8, H10 (λ) ni H17 respecto de la entrega
  original; en H7/H8 el jerárquico PWL registra 5 exclusiones de dominio **certificadas** (cobertura con energía libre,
  `provenInfeasible`).
* **Anticipación** (MPC sin señal − jerárquico, misma N = 3, m = 1): H2 R$ 10,2, H5 R$ 10,2, H17 R$ 5,3 con condiciones
  terminales iguales; H1/H3 ⇒ 0. **Reoptimización** (open-loop − encolhido) = 0 en todas las instancias.
* **H7/H8**: MPC sin señal INVIABLE; jerárquico concluye — valor de reserva por restricción física. Local también falla.
* **H9 (tras B3C4-01)**: PWL y referencia blanda R$ 129,6; horizonte completo/open-loop/oráculo R$ 127,6 (brecha R$ 2,0
  atribuible a `cumprir_na_janela`, B3C4-02); E final 0 kWh, PEMFC encendida y sin obligaciones pendientes en todas las
  concluidas. La línea de base 3C-3 sin señal y la referencia dura avanzan ahora hasta k = 10 (proyección de 1 ulp en
  k = 8) y se detienen por B3C4-10 (C-01, `P_imp = −8,88e-16`): NO comparables. No se afirma superioridad.
* Una instancia sintética no establece superioridad general. Tiempos solo indicativos (4 CPU compartidas).

## 4. Auditoría del PR #17 — defectos reproducidos ANTES (`9630e73`) y DESPUÉS (`c964a2e`)

Scripts de reproducción fuera del repositorio (scratchpad de la sesión); su lógica está fijada en
`tests/ems_v2/test_ems_v2_3c4_auditoria_pr17.py`.

### 4.1 C-3C4-A01 — registro final alterado y re-sellado

Antes:
```
commit 9630e73f436cd3306abf28c7d4cf9cbad0950fd4
valido: True
contagens                        aceito=True verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': True} codigos=[]
energias_finais_kWh              aceito=True verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': True} codigos=[]
valoracao_terminal_declarada_R   aceito=True verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': True} codigos=[]
hash_configuracao_rede           aceito=True verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': True} codigos=[]
missao_uid                       aceito=True verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': True} codigos=[]
tempos_planejador_s(negativo)    aceito=True verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': True} codigos=[]
tempos_planejador_s(inflado)     aceito=True verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': True} codigos=[]
tempos_planejador_s(inf, sem reselo) aceito= False ['previsao_coincide_com_realizacao', 'registro_hierarquico_adulterado']
```
Después:
```
commit c964a2efb0da20db3611d5ab4de4e8ac72851a90
valido: True
contagens                        aceito=False verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': False, 'projecoes_numericas': True} codigos=[]
energias_finais_kWh              aceito=False verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': False, 'projecoes_numericas': True} codigos=[]
valoracao_terminal_declarada_R   aceito=False verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': False, 'projecoes_numericas': True} codigos=[]
hash_configuracao_rede           aceito=False verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': False, 'projecoes_numericas': True} codigos=['configuracao_hierarquica_divergente']
missao_uid                       aceito=False verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': False, 'projecoes_numericas': True} codigos=['registro_hierarquico_missao_divergente']
tempos_planejador_s(negativo)    aceito=False verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': False, 'projecoes_numericas': True} codigos=[]
tempos_planejador_s(inflado)     aceito=False verificacoes={'integral_3c3': True, 'hierarquica': True, 'registro_hierarquico': False, 'projecoes_numericas': True} codigos=[]
tempos_planejador_s(inf, sem reselo) aceito= False ['previsao_coincide_com_realizacao', 'registro_hierarquico_adulterado', 'tempos_planejador_invalidos']
```

### 4.2 C-3C4-A02 — región factible estrecha fuera de la grilla (función de factibilidad sintética)

Antes:
```
commit 9630e73f436cd3306abf28c7d4cf9cbad0950fd4
modo ligado isolado: inviavel | modo [('syn-fc', True, 0)]: cauda inviável em toda a grade (excluído) | energias avaliadas: [0.0, 5.0, 10.0, 15.0, 20.0]
dois modos: estado = valido | modos no sinal = [[False]] | motivo: PWL por reotimização paramétrica auditada; modo [('syn-fc', True, 0)]: cauda inviável em toda a grade (excluído)
```
Después — mismo script (resolvedor sin capacidad de certificado):
```
commit c964a2efb0da20db3611d5ab4de4e8ac72851a90
modo ligado isolado: dominio_indeterminado | modo [('syn-fc', True, 0)]: grade sem ponto factível e certificado inconclusivo (cobertura[0,20]:resolvedor_sem_certificado) | energias avaliadas: [0.0, 5.0, 10.0, 15.0, 20.0]
dois modos: estado = indisponivel | modos no sinal = [] | motivo: dominio_indeterminado: modo [('syn-fc', True)] — modo [('syn-fc', True, 0)]: grade sem ponto factível e certificado inconclusivo (cobertura[0,20]:resolvedor_sem_certificado)
```
Después — sin certificado × con certificado sintético coherente con la función:
```
[SEM certificado (resolvedor sem cobertura)] modo ligado isolado: dominio_indeterminado | modo [('syn-fc', True, 0)]: grade sem ponto factível e certificado inconclusivo (cobertura[0,20]:resolvedor_sem_certificado)
[SEM certificado (resolvedor sem cobertura)] dois modos: estado = indisponivel | modos = [] | domínios = []
     diagnóstico = [('valido', [False]), ('dominio_indeterminado', [True])]
     motivo: dominio_indeterminado: modo [('syn-fc', True)] — modo [('syn-fc', True, 0)]: grade sem ponto factível e certificado inconclusivo (cobertura[0,20]:resolvedor_sem
[COM certificado sintético] modo ligado isolado: valido | ((7.1,), (7.870312500000001,), [(7.1, 10.0), (7.825, 10.0), (7.870312500000001, 10.0)], ['cobertura[0,20]:otimo', 'ponto_factivel_encontrado_fora_da_grade:E*=7.1', 'cobertura[0,7.06719]:inviavel', 'cobertura[7.91563,20]:inviavel'])
[COM certificado sintético] dois modos: estado = valido | modos = [[False], [True]] | domínios = [((0.0,), (20.0,)), ((7.1,), (7.870312500000001,))]
     diagnóstico = [('valido', [False]), ('valido', [True])]
     motivo: PWL por reotimização paramétrica auditada (domínio = aproximação interna conservadora)
```

### 4.3 B3C4-01 — deriva de energía en el perfil 3C-3 ORIGINAL (H9, `ControladorMPCConectado`)

Antes:
```
commit 9630e73f436cd3306abf28c7d4cf9cbad0950fd4
controlador: ControladorMPCConectado | situação: interrompida bloqueado_validacao
k= 0 P_c[0]=0.0 P_d[0]=10.0 e_plan=(10.0, 0.0) e_exec=10.0->0.0
k= 1 P_c[0]=0.0 P_d[0]=0.0 e_plan=(0.0, 0.0) e_exec=0.0->0.0
k= 2 P_c[0]=0.0 P_d[0]=0.0 e_plan=(0.0, 0.0) e_exec=0.0->0.0
k= 3 P_c[0]=0.0 P_d[0]=0.0 e_plan=(0.0, 0.0) e_exec=0.0->0.0
k= 4 P_c[0]=0.0 P_d[0]=0.0 e_plan=(0.0, 0.0) e_exec=0.0->0.0
k= 5 P_c[0]=0.0 P_d[0]=0.0 e_plan=(0.0, 0.0) e_exec=0.0->0.0
k= 6 P_c[0]=10.0 P_d[0]=0.0 e_plan=(0.0, 10.0) e_exec=0.0->10.0
k= 7 P_c[0]=0.0 P_d[0]=0.0 e_plan=(10.0, 10.0) e_exec=10.0->10.0
k= 8 P_c[0]=0.0 P_d[0]=-1.7763568394002505e-15 e_plan=(10.0, 10.000000000000002) e_exec=10.0->10.000000000000002
última janela: 9 [('energia_maior_que_capacidade', 'e0 = 10.000000000000002 kWh > C = 10.0 kWh.'), ('soc_inicial_fora_dos_limites', 'e0/C = 1.0000000000000002 fora de [0.0, 1.0] (sem recorte).')]
estado transportado: 10.000000000000002 C = 10.0 | excesso = 1.7763568394002505e-15 | ulp(10) = 0x1.4000000000000p+3 1.7763568394002505e-15
```
Después (la proyección en k = 8 transporta 10.0; la misión se detiene en k = 10 por B3C4-10):
```
commit c964a2efb0da20db3611d5ab4de4e8ac72851a90
controlador: ControladorMPCConectado | situação: interrompida integridade
k= 0 P_c[0]=0.0 P_d[0]=10.0 e_plan=(10.0, 0.0) e_exec=10.0->0.0
k= 1 P_c[0]=0.0 P_d[0]=0.0 e_plan=(0.0, 0.0) e_exec=0.0->0.0
k= 2 P_c[0]=0.0 P_d[0]=0.0 e_plan=(0.0, 0.0) e_exec=0.0->0.0
k= 3 P_c[0]=0.0 P_d[0]=0.0 e_plan=(0.0, 0.0) e_exec=0.0->0.0
k= 4 P_c[0]=0.0 P_d[0]=0.0 e_plan=(0.0, 0.0) e_exec=0.0->0.0
k= 5 P_c[0]=0.0 P_d[0]=0.0 e_plan=(0.0, 0.0) e_exec=0.0->0.0
k= 6 P_c[0]=10.0 P_d[0]=0.0 e_plan=(0.0, 10.0) e_exec=0.0->10.0
k= 7 P_c[0]=0.0 P_d[0]=0.0 e_plan=(10.0, 10.0) e_exec=10.0->10.0
k= 8 P_c[0]=0.0 P_d[0]=-1.7763568394002505e-15 e_plan=(10.0, 10.000000000000002) e_exec=10.0->10.0
k= 9 P_c[0]=0.0 P_d[0]=4.999999999999999 e_plan=(10.0, 5.000000000000001) e_exec=10.0->5.000000000000001
última janela: 10 [('falha_integridade', '[intercambio_programado_invalido] resultado.intercambio[P_imp]: Exigidos 2 valor')]
estado transportado: 5.000000000000001 C = 10.0 | excesso = -4.999999999999999 | ulp(10) = 0x1.4000000000000p+3 1.7763568394002505e-15
```
H9 con siete estrategias después del hotfix:
```
mpc_sem_sinal    interrompida integridade          k=10 custo=109.75               E=[5.000000000000001] FC(ligado=True, p=20.0, tempo=18000) obrig={} projecoes=[(8, 'superior', 1.7763568394002505e-15)] desvios_politica=0 [('falha_integridade', '[intercambio_programado_invalido] resultado.intercambio[P_imp]: Exigidos 2 valores reais finitos >= 0 (sem rec')]
hier_pwl         encerrada   None                 k=12 custo=129.6                E=[0.0] FC(ligado=True, p=5.0, tempo=25200) obrig={} projecoes=[] desvios_politica=0 []
hier_ref_dura    interrompida integridade          k=10 custo=109.55               E=[5.000000000000001] FC(ligado=True, p=20.0, tempo=18000) obrig={} projecoes=[(8, 'superior', 1.7763568394002505e-15)] desvios_politica=0 [('falha_integridade', '[intercambio_programado_invalido] resultado.intercambio[P_imp]: Exigidos 2 valores reais finitos >= 0 (sem rec')]
hier_ref_branda  encerrada   None                 k=12 custo=129.6                E=[0.0] FC(ligado=True, p=5.0, tempo=25200) obrig={} projecoes=[] desvios_politica=0 []
mpc_encolhido    encerrada   None                 k=12 custo=127.60000000000001   E=[0.0] FC(ligado=True, p=5.0, tempo=18000) obrig={} projecoes=[] desvios_politica=0 []
open_loop        encerrada   None                 k=12 custo=127.6                E=[0.0] FC(ligado=True, p=5.0, tempo=18000) obrig={} projecoes=[] desvios_politica=0 []
oraculo          encerrada   None                 k=12 custo=127.6                E=[0.0] FC(ligado=True, p=5.0, tempo=18000) obrig={} projecoes=[] desvios_politica=0 []
```
