# Piso 3C-4 — Evidencia de ejecución (sintética, algebraica)

> Generada en la rama de la misión 3C-4 sobre `main` `10365c5`. **Rótulo:** simulación causal de lazo cerrado
> ALGEBRAICA sobre fixtures/tarifas SINTÉTICAS (`ems_v2/fixtures_3c4.py`); ningún número es validación física, factura
> real ni desempeño de tiempo real. Los tiempos valen SOLO para el ambiente impreso (4 CPU compartidas; indicativos).

## 1. Pruebas realmente ejecutadas (2026-11-09)

| Comando | Resultado |
|---|---|
| `python -m pytest tests/ems_v2 -q` (línea de base en `10365c5`, antes de cambiar nada) | **1080 passed** |
| `python -m pytest tests/ems_v2/test_ems_v2_3c4_*.py -q` | **101 passed** (contrato 48, auditor 5, MILP 13, planificador 12, misión 18, aislamiento 5) |
| `python -m pytest tests/ems_v2 -q` (rama) | **1181 passed** (= 1080 + 101) |
| `tests/ems_v2` con Pyomo/HiGHS **bloqueados** (buscador de metapath ⇒ `ModuleNotFoundError`) | **794 passed, 42 skipped** (= 736 + 58 sin solver; 3 módulos 3C-4 con HiGHS saltados explícitamente) |
| `python -m pytest tests/ -q` (suite completa) | **1635 passed, 7 warnings, 128 subtests** (445,4 s) = 1534 de `main` + 101 |
| `python -m ems_v2.milp.evidencia_3c4` | salida literal en §2 (79,4 s) |

Todas con `PYTHONDONTWRITEBYTECODE=1`, Python 3.13.18, Pyomo 6.10.1, HiGHS 1.15.1 (`CONFIG_ANALITICA`: 1 hilo, gap 0,
semilla 0). Limitación: el primer intento sin solver lanzaba `ImportError` en vez de `ModuleNotFoundError` y dejaba
centinelas en `sys.modules`, lo que hacía fallar artefactualmente las guardias de importación de TODOS los pisos; el
método registrado arriba (sin rastro en `sys.modules`) es el fiel.

## 2. Salida literal de `python -m ems_v2.milp.evidencia_3c4`

## Ambiente

```json
{"cpus": 4, "plataforma": "Linux-6.18.44-fc-v310-x86_64-with-glibc2.39", "processador": "x86_64", "python": "3.13.18", "solver": {"disponivel": true, "divergencias": [], "erro": null, "fixadas": {"highspy": "1.15.1", "pyomo": "6.10.1"}, "interface": "pyomo.contrib.solver:highs", "versao_highs": "1.15.1", "versoes": {"highspy": "1.15.1", "pyomo": "6.10.1"}}}
```

## Campanha (estratégias × cenários)

| Cenário | Estratégia | Situação | Custo realizado [R$] | E final [kWh] | Degradadas | Avaliações planejador | Tempo planejador [s] | Tempo total [s] |
|---|---|---|---|---|---|---|---|---|
| h1_tarifa_plana | open_loop | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.30 |
| h1_tarifa_plana | mpc_sem_sinal | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.24 |
| h1_tarifa_plana | mpc_encolhido | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.27 |
| h1_tarifa_plana | hier_pwl | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 93 | 1.404 | 1.69 |
| h1_tarifa_plana | hier_local | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 30 | 0.422 | 0.71 |
| h1_tarifa_plana | hier_ref_dura | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0.204 | 0.52 |
| h1_tarifa_plana | hier_ref_branda | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0.202 | 0.50 |
| h1_tarifa_plana | oraculo | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.03 |
| h2_pico_futuro | open_loop | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.03 |
| h2_pico_futuro | mpc_sem_sinal | encerrada | 60.40 | {"syn-bess": 0.0} | 0 | 0 | — | 0.22 |
| h2_pico_futuro | mpc_encolhido | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.27 |
| h2_pico_futuro | hier_pwl | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 93 | 1.317 | 1.61 |
| h2_pico_futuro | hier_local | encerrada | 50.20 | {"syn-bess": 0.0} | 1 | 31 | 0.443 | 0.72 |
| h2_pico_futuro | hier_ref_dura | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0.220 | 0.47 |
| h2_pico_futuro | hier_ref_branda | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0.176 | 0.44 |
| h2_pico_futuro | oraculo | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.03 |
| h3_pico_no_horizonte_curto | open_loop | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.03 |
| h3_pico_no_horizonte_curto | mpc_sem_sinal | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.21 |
| h3_pico_no_horizonte_curto | mpc_encolhido | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.23 |
| h3_pico_no_horizonte_curto | hier_pwl | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 93 | 1.420 | 1.71 |
| h3_pico_no_horizonte_curto | hier_local | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 30 | 0.432 | 0.72 |
| h3_pico_no_horizonte_curto | hier_ref_dura | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0.179 | 0.44 |
| h3_pico_no_horizonte_curto | hier_ref_branda | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0.180 | 0.46 |
| h3_pico_no_horizonte_curto | oraculo | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.03 |
| h5_erro_previsao | open_loop | encerrada | 61.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.03 |
| h5_erro_previsao | mpc_sem_sinal | encerrada | 71.40 | {"syn-bess": 0.0} | 0 | 0 | — | 0.22 |
| h5_erro_previsao | mpc_encolhido | encerrada | 61.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.24 |
| h5_erro_previsao | hier_pwl | encerrada | 61.20 | {"syn-bess": 0.0} | 0 | 93 | 1.390 | 1.67 |
| h5_erro_previsao | hier_local | encerrada | 61.20 | {"syn-bess": 0.0} | 1 | 31 | 0.455 | 0.74 |
| h5_erro_previsao | hier_ref_dura | encerrada | 61.20 | {"syn-bess": 0.0} | 0 | 12 | 0.175 | 0.41 |
| h5_erro_previsao | hier_ref_branda | encerrada | 61.20 | {"syn-bess": 0.0} | 0 | 12 | 0.176 | 0.47 |
| h5_erro_previsao | oraculo | encerrada | 61.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.03 |
| h7_limite_importacao | open_loop | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.04 |
| h7_limite_importacao | mpc_sem_sinal | interrompida/inviavel | 27.75 | {"syn-bess": 5.0} | 0 | 0 | — | 0.14 |
| h7_limite_importacao | mpc_encolhido | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.21 |
| h7_limite_importacao | hier_pwl | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 101 | 1.184 | 1.45 |
| h7_limite_importacao | hier_local | interrompida/inviavel | 30.10 | {"syn-bess": 10.0} | 3 | 23 | 0.428 | 0.62 |
| h7_limite_importacao | hier_ref_dura | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0.179 | 0.43 |
| h7_limite_importacao | hier_ref_branda | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0.177 | 0.45 |
| h7_limite_importacao | oraculo | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.04 |
| h8_indisponibilidade_pcc | open_loop | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.03 |
| h8_indisponibilidade_pcc | mpc_sem_sinal | interrompida/inviavel | 27.75 | {"syn-bess": 5.0} | 0 | 0 | — | 0.15 |
| h8_indisponibilidade_pcc | mpc_encolhido | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.24 |
| h8_indisponibilidade_pcc | hier_pwl | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 101 | 1.469 | 1.76 |
| h8_indisponibilidade_pcc | hier_local | interrompida/inviavel | 30.10 | {"syn-bess": 10.0} | 3 | 23 | 0.365 | 0.60 |
| h8_indisponibilidade_pcc | hier_ref_dura | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0.188 | 0.45 |
| h8_indisponibilidade_pcc | hier_ref_branda | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0.177 | 0.45 |
| h8_indisponibilidade_pcc | oraculo | encerrada | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0.04 |
| h9_pemfc | open_loop | encerrada | 127.60 | {"syn-bess": 0.0} | 0 | 0 | — | 0.06 |
| h9_pemfc | mpc_sem_sinal | interrompida/bloqueado_validacao | 95.70 | {"syn-bess": 10.0} | 0 | 0 | — | 0.22 |
| h9_pemfc | mpc_encolhido | encerrada | 127.60 | {"syn-bess": 0.0} | 0 | 0 | — | 0.47 |
| h9_pemfc | hier_pwl | encerrada | 129.60 | {"syn-bess": 0.0} | 0 | 174 | 3.954 | 4.41 |
| h9_pemfc | hier_local | encerrada | 129.60 | {"syn-bess": 0.0} | 1 | 33 | 0.835 | 1.27 |
| h9_pemfc | hier_ref_dura | interrompida/bloqueado_validacao | 95.50 | {"syn-bess": 10.0} | 1 | 10 | 0.251 | 0.55 |
| h9_pemfc | hier_ref_branda | encerrada | 129.60 | {"syn-bess": 0.0} | 0 | 12 | 0.294 | 0.68 |
| h9_pemfc | oraculo | encerrada | 127.60 | {"syn-bess": 0.0} | 0 | 0 | — | 0.05 |
| h17_dois_bancos | open_loop | encerrada | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 0 | — | 0.05 |
| h17_dois_bancos | mpc_sem_sinal | encerrada | 55.50 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 0 | — | 0.26 |
| h17_dois_bancos | mpc_encolhido | encerrada | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 0 | — | 0.32 |
| h17_dois_bancos | hier_pwl | encerrada | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 129 | 2.462 | 2.84 |
| h17_dois_bancos | hier_local | encerrada | 50.30 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 1 | 41 | 0.775 | 1.15 |
| h17_dois_bancos | hier_ref_dura | encerrada | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 12 | 0.240 | 0.68 |
| h17_dois_bancos | hier_ref_branda | encerrada | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 12 | 0.241 | 0.58 |
| h17_dois_bancos | oraculo | encerrada | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 0 | — | 0.04 |

## Efeitos separados

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
| h9_pemfc | antecipacao | mpc_sem_sinal − hier_pwl | — | NÃO | missão não concluída (mpc_sem_sinal: interrompida/bloqueado_validacao; hier_pwl: encerrada/None): custos acumu |
| h9_pemfc | metodo_hier_local_vs_pwl | hier_local − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h9_pemfc | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | — | NÃO | missão não concluída (hier_ref_dura: interrompida/bloqueado_validacao; hier_pwl: encerrada/None): custos acumu |
| h9_pemfc | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h9_pemfc | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | — | NÃO | missão não concluída (mpc_sem_sinal: interrompida/bloqueado_validacao; oraculo: encerrada/None): custos acumul |
| h9_pemfc | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 2.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | reotimizacao | open_loop − mpc_encolhido | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | antecipacao | mpc_sem_sinal − hier_pwl | 5.30 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | metodo_hier_local_vs_pwl | hier_local − hier_pwl | 0.10 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | 5.30 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |

## H13 — horizonte curto × longo (H2)

| N | H_L | MPC sem sinal [R$] | Hierárquico PWL [R$] | Avaliações | Tempo planejador [s] |
|---|---|---|---|---|---|
| 2 | 3 | 65.30 | 60.40 | 102 | 1.163 |
| 2 | 6 | 65.30 | 50.60 | 102 | 1.527 |
| 2 | 8 | 65.30 | 50.40 | 102 | 1.480 |
| 2 | 10 | 65.30 | 50.20 | 102 | 1.615 |
| 2 | 12 | 65.30 | 50.20 | 102 | 1.524 |
| 3 | 4 | 60.40 | 55.50 | 93 | 0.951 |
| 3 | 6 | 60.40 | 50.60 | 93 | 1.292 |
| 3 | 8 | 60.40 | 50.40 | 93 | 1.585 |
| 3 | 10 | 60.40 | 50.20 | 93 | 1.328 |
| 3 | 12 | 60.40 | 50.20 | 93 | 1.474 |
| 4 | 5 | 55.50 | 50.60 | 84 | 0.806 |
| 4 | 6 | 55.50 | 50.60 | 84 | 1.035 |
| 4 | 8 | 55.50 | 50.40 | 84 | 1.408 |
| 4 | 10 | 55.50 | 50.20 | 84 | 1.380 |
| 4 | 12 | 55.50 | 50.20 | 84 | 1.462 |

## H6/H10 — λ(E) na fronteira b = 9 (τ_6, H2)

| Segmento E [kWh] | V nos extremos [R$] | λ_E = −dV/dE [R$/kWh] |
|---|---|---|
| [0, 5] | 25.0000 → 17.5500 | 1.4900 |
| [5, 10] | 17.5500 → 10.1000 | 1.4900 |
| [10, 15] | 10.1000 → 7.6500 | 0.4900 |
| [15, 20] | 7.6500 → 5.2000 | 0.4900 |

## H4 — λ₀ × posição do pico

| Perfil (previsão causal) | λ₀ em τ_0 (E ∈ [0, 5]) [R$/kWh] |
|---|---|
| plana 0,5 | 0.4900 |
| pico h4–5 | 1.4900 |
| pico h6–7 | 1.4900 |
| pico h8–9 | 0.5100 |

## Custo computacional (H2)

| Configuração | Custo [R$] | Janelas válidas/degradadas | Avaliações | Planejador [s] | Erro máx. [R$] |
|---|---|---|---|---|---|
| PWL pontos=3, máx 9 | 50.20 | 12/0 | 61 | 0.966 | 3.55e-15 |
| PWL pontos=5, máx 9 | 50.20 | 12/0 | 93 | 1.576 | 3.55e-15 |
| PWL pontos=4, máx 4 (sem refinamento) | 55.50 | 7/5 | 75 | 1.075 | 1.67 |
| periódica P=2 | 50.20 | 12/0 | 87 | 1.328 | 3.55e-15 |
| periódica P=3 | 50.20 | 12/0 | 85 | 1.287 | 3.55e-15 |
| periódica P=4 | 50.20 | 12/0 | 84 | 1.284 | 3.55e-15 |

_Tempo total da evidência: 79.4 s (só este ambiente)._

## 3. Lectura (sin extrapolación)

* **Anticipación** (MPC sin señal − jerárquico, misma N = 3, m = 1): H2 R$ 10,2 y H5 R$ 10,2 (error de previsión, misma
  verdad), H17 R$ 5,3 — condiciones terminales iguales (E final 0, sin generadores/obligaciones distintos). H1 (tarifa
  plana) y H3 (pico visible en H_S) ⇒ 0: el mecanismo no crea incentivos artificiales.
* **Reoptimización** (open-loop − encolhido) = 0 en todos los casos: con previsión de tabla y PCC de ajuste local, la
  realimentación no cambia el costo en estas instancias (el error de H5 se absorbe por el PCC en ambos).
* **Reserva por restricción física** (H7/H8, tarifa plana): el MPC sin señal termina INVIABLE; el jerárquico PWL
  concluye con el óptimo de información perfecta. La aproximación LOCAL también falla (umbral de factibilidad fuera de
  [E_ref ± δ]) — limitación documentada del método local.
* **H9:** jerárquico R$ 129,6 vs información perfecta R$ 127,6: brecha de R$ 2,0 atribuible a la condición
  `cumprir_na_janela` (B3C4-02); la línea de base sin señal y `hier_ref_dura` se detienen por la deriva numérica
  HEREDADA (C-3C4-03/B3C4-01) ⇒ NO comparables.
* **Costo computacional:** PWL de 5 puntos ≈ 93 MILP auditados por misión de 12 ventanas (~1,3–1,6 s en este ambiente);
  3 puntos con refinamiento ≈ 61; la grilla de 4 puntos SIN refinamiento deja 5 ventanas degradadas y cuesta R$ 55,5
  (la degradación es visible, no oculta). Política periódica P = 2–4 reduce evaluaciones sin cambiar el costo en H2.
* Una instancia sintética no establece superioridad general.
