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

### 1c. Tras la 2ª auditoría del PR #17 (hotfix B3C4-10 en `8efc927`)

| Comando | Resultado |
|---|---|
| `tests/ems_v2/test_ems_v2_3c4_b3c4_10.py` (nueva suite B3C4-10) | **66 passed** |
| `tests/ems_v2/test_ems_v2_3c4_b3c4_10.py` + `test_ems_v2_3c4_auditoria_pr17.py` | **104 passed** (66 + 38; 1 prueba de H9 actualizada) |
| `tests/ems_v2 -k 3c4` (H1–H18 + auditorías) | **207 passed** |
| `tests/ems_v2 -k "isolamento or perfil"` (guardias, incl. `test_hotfix_b3c4_10_restrito_e_regra_c01_identica_a_base`) | **53 passed** |
| `test_ems_v2_3c3_regressao_3c2.py` (E1–E8 con huellas) + `test_ems_v2_3c3_milp.py` (G1–G4, G9, G10, G14) + `test_ems_v2_3c3_mpc.py` + `test_ems_v2_3c2_milp.py` | **75 passed** |
| `tests/ems_v2` con Pyomo/HiGHS (G1–G15, E1–E8, 3C-0, 3C-1, 3C-4) | **1287 passed (= 1220 + 66 + 1 guardia)** |
| `tests/ems_v2` con Pyomo/HiGHS **bloqueados** | **859 passed, 83 skipped** |
| `python -m pytest tests/ -q` (suite completa) | **1741 passed, 7 warnings, 128 subtests (451,8 s) = 1674 + 67** |
| `python -m ems_v2.milp.evidencia_3c4` | salida literal en §2 (84,5 s) |

### 1d. Último cierre de la auditoría del PR #17 (C-3C4-A03, `322ffa6`)

| Comando | Resultado |
|---|---|
| `tests/ems_v2/test_ems_v2_3c4_a03.py` (nueva suite A03) | **18 passed** |
| `tests/ems_v2 -k 3c4` (H1–H18 + auditorías + B3C4-10 + A03) | **228 passed** (207 + 18 + 3 guardias) |
| `tests/ems_v2 -k "isolamento or perfil"` (incl. `test_a03_*`) | **56 passed** |
| E1–E8 (huellas) + G1–G15 (MILP, MPC, auditorías PR #16 C-01/C-02/C-03) + 3C-2 MILP | **252 passed** |
| `tests/ems_v2` con Pyomo/HiGHS | **1308 passed (= 1287 + 21)** |
| `tests/ems_v2` con Pyomo/HiGHS **bloqueados** | **862 passed, 101 skipped** |
| `python -m pytest tests/ -q` (suite completa) | **1762 passed, 7 warnings, 128 subtests (458,3 s) = 1741 + 21** |

Todas con `PYTHONDONTWRITEBYTECODE=1`, Python 3.13.18, Pyomo 6.10.1, HiGHS 1.15.1 (`CONFIG_ANALITICA`: 1 hilo, gap 0,
semilla 0).

## 2. Salida literal de `python -m ems_v2.milp.evidencia_3c4` (código del hotfix B3C4-10, `8efc927`; columna de normalizaciones B3C4-10 añadida a H9)

### Ambiente

```json
{"cpus": 4, "plataforma": "Linux-6.18.44-fc-v338-x86_64-with-glibc2.39", "processador": "x86_64", "python": "3.13.18", "solver": {"disponivel": true, "divergencias": [], "erro": null, "fixadas": {"highspy": "1.15.1", "pyomo": "6.10.1"}, "interface": "pyomo.contrib.solver:highs", "versao_highs": "1.15.1", "versoes": {"highspy": "1.15.1", "pyomo": "6.10.1"}}}
```

### Campanha (estratégias × cenários)

| Cenário | Estratégia | Situação | k final | Custo realizado [R$] | E final [kWh] | Degradadas | Avaliações planejador | Certificados A02 (inviável/total) | Projeções B3C4-01 | Tempo planejador [s] | Tempo total [s] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| h1_tarifa_plana | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.30 |
| h1_tarifa_plana | mpc_sem_sinal | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.25 |
| h1_tarifa_plana | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.26 |
| h1_tarifa_plana | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 93 | 0/0 | 0 | 1.632 | 1.97 |
| h1_tarifa_plana | hier_local | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 30 | 0/0 | 0 | 0.558 | 0.91 |
| h1_tarifa_plana | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.205 | 0.50 |
| h1_tarifa_plana | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.218 | 0.56 |
| h1_tarifa_plana | oraculo | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h2_pico_futuro | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.04 |
| h2_pico_futuro | mpc_sem_sinal | encerrada | 12 | 60.40 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.24 |
| h2_pico_futuro | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.36 |
| h2_pico_futuro | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 93 | 0/0 | 0 | 1.653 | 1.99 |
| h2_pico_futuro | hier_local | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 1 | 31 | 0/0 | 0 | 0.512 | 0.83 |
| h2_pico_futuro | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.270 | 0.55 |
| h2_pico_futuro | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.210 | 0.51 |
| h2_pico_futuro | oraculo | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.04 |
| h3_pico_no_horizonte_curto | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.04 |
| h3_pico_no_horizonte_curto | mpc_sem_sinal | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.28 |
| h3_pico_no_horizonte_curto | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.30 |
| h3_pico_no_horizonte_curto | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 93 | 0/0 | 0 | 1.579 | 1.89 |
| h3_pico_no_horizonte_curto | hier_local | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 30 | 0/0 | 0 | 0.467 | 0.78 |
| h3_pico_no_horizonte_curto | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.194 | 0.48 |
| h3_pico_no_horizonte_curto | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.201 | 0.50 |
| h3_pico_no_horizonte_curto | oraculo | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h5_erro_previsao | open_loop | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.04 |
| h5_erro_previsao | mpc_sem_sinal | encerrada | 12 | 71.40 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.23 |
| h5_erro_previsao | mpc_encolhido | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.25 |
| h5_erro_previsao | hier_pwl | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 93 | 0/0 | 0 | 1.590 | 1.90 |
| h5_erro_previsao | hier_local | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 1 | 31 | 0/0 | 0 | 0.529 | 0.84 |
| h5_erro_previsao | hier_ref_dura | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.194 | 0.48 |
| h5_erro_previsao | hier_ref_branda | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.200 | 0.55 |
| h5_erro_previsao | oraculo | encerrada | 12 | 61.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h7_limite_importacao | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.04 |
| h7_limite_importacao | mpc_sem_sinal | interrompida/inviavel | 7 | 27.75 | {"syn-bess": 5.0} | 0 | 0 | — | 0 | — | 0.16 |
| h7_limite_importacao | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.24 |
| h7_limite_importacao | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 106 | 5/5 | 0 | 1.382 | 1.67 |
| h7_limite_importacao | hier_local | interrompida/inviavel | 7 | 30.10 | {"syn-bess": 10.0} | 3 | 23 | 0/0 | 0 | 0.374 | 0.66 |
| h7_limite_importacao | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.187 | 0.44 |
| h7_limite_importacao | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.193 | 0.45 |
| h7_limite_importacao | oraculo | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h8_indisponibilidade_pcc | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.04 |
| h8_indisponibilidade_pcc | mpc_sem_sinal | interrompida/inviavel | 7 | 27.75 | {"syn-bess": 5.0} | 0 | 0 | — | 0 | — | 0.15 |
| h8_indisponibilidade_pcc | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.24 |
| h8_indisponibilidade_pcc | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 106 | 5/5 | 0 | 1.406 | 1.70 |
| h8_indisponibilidade_pcc | hier_local | interrompida/inviavel | 7 | 30.10 | {"syn-bess": 10.0} | 3 | 23 | 0/0 | 0 | 0.361 | 0.57 |
| h8_indisponibilidade_pcc | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.201 | 0.47 |
| h8_indisponibilidade_pcc | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.175 | 0.44 |
| h8_indisponibilidade_pcc | oraculo | encerrada | 12 | 50.20 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.03 |
| h9_pemfc | open_loop | encerrada | 12 | 127.60 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.06 |
| h9_pemfc | mpc_sem_sinal | encerrada | 12 | 129.80 | {"syn-bess": 0.0} | 0 | 0 | — | 1 | — | 0.29 |
| h9_pemfc | mpc_encolhido | encerrada | 12 | 127.60 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.45 |
| h9_pemfc | hier_pwl | encerrada | 12 | 129.60 | {"syn-bess": 0.0} | 0 | 174 | 0/0 | 0 | 3.792 | 4.20 |
| h9_pemfc | hier_local | encerrada | 12 | 129.60 | {"syn-bess": 0.0} | 1 | 33 | 0/0 | 0 | 0.717 | 1.18 |
| h9_pemfc | hier_ref_dura | encerrada | 12 | 129.60 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 1 | 0.278 | 0.65 |
| h9_pemfc | hier_ref_branda | encerrada | 12 | 129.60 | {"syn-bess": 0.0} | 0 | 12 | 0/0 | 0 | 0.304 | 0.67 |
| h9_pemfc | oraculo | encerrada | 12 | 127.60 | {"syn-bess": 0.0} | 0 | 0 | — | 0 | — | 0.05 |
| h17_dois_bancos | open_loop | encerrada | 12 | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 0 | — | 0 | — | 0.04 |
| h17_dois_bancos | mpc_sem_sinal | encerrada | 12 | 55.50 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 0 | — | 0 | — | 0.27 |
| h17_dois_bancos | mpc_encolhido | encerrada | 12 | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 0 | — | 0 | — | 0.30 |
| h17_dois_bancos | hier_pwl | encerrada | 12 | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 129 | 0/0 | 0 | 2.396 | 2.74 |
| h17_dois_bancos | hier_local | encerrada | 12 | 50.30 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 1 | 41 | 0/0 | 0 | 0.752 | 1.21 |
| h17_dois_bancos | hier_ref_dura | encerrada | 12 | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 12 | 0/0 | 0 | 0.225 | 0.53 |
| h17_dois_bancos | hier_ref_branda | encerrada | 12 | 50.20 | {"syn-bess": 0.0, "syn-bess-2": 0.0} | 0 | 12 | 0/0 | 0 | 0.226 | 0.55 |
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
| h9_pemfc | antecipacao | mpc_sem_sinal − hier_pwl | 0.20 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h9_pemfc | metodo_hier_local_vs_pwl | hier_local − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h9_pemfc | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h9_pemfc | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h9_pemfc | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | 2.20 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h9_pemfc | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 2.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | reotimizacao | open_loop − mpc_encolhido | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | antecipacao | mpc_sem_sinal − hier_pwl | 5.30 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | metodo_hier_local_vs_pwl | hier_local − hier_pwl | 0.10 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | metodo_hier_ref_dura_vs_pwl | hier_ref_dura − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | metodo_hier_ref_branda_vs_pwl | hier_ref_branda − hier_pwl | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | informacao_perfeita_mpc_sem_sinal | mpc_sem_sinal − oraculo | 5.30 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |
| h17_dois_bancos | informacao_perfeita_hier_pwl | hier_pwl − oraculo | 0.00 | sim | condições terminais iguais (energia, ON/OFF, obrigações): diferença de custo comparável |

### H9 — PEMFC: estados finais, memória e obrigações

| Estratégia | Situação | k final | Custo [R$] | E final [kWh] | PEMFC ligada / p [kW] / tempo no estado [s] | Obrigações pendentes | Projeções B3C4-01 (k, limite, correção kWh) | Normalizações B3C4-10 (k, grandeza, bruto kW, limiar kW) | Falha |
|---|---|---|---|---|---|---|---|---|---|
| mpc_sem_sinal | encerrada | 12 | 129.8 | [0.0] | True / 5.0 / 25200 | {} | [(8, 'superior', 1.7763568394002505e-15)] | [(10, 'P_imp', -8.881784197001252e-16, 1.3500311979441904e-13)] | — |
| hier_pwl | encerrada | 12 | 129.6 | [0.0] | True / 5.0 / 25200 | {} | [] | [] | — |
| hier_ref_dura | encerrada | 12 | 129.6 | [0.0] | True / 5.0 / 25200 | {} | [(8, 'superior', 1.7763568394002505e-15)] | [(10, 'P_imp', -8.881784197001252e-16, 1.3500311979441904e-13)] | — |
| hier_ref_branda | encerrada | 12 | 129.6 | [0.0] | True / 5.0 / 25200 | {} | [] | [] | — |
| mpc_encolhido | encerrada | 12 | 127.60000000000001 | [0.0] | True / 5.0 / 18000 | {} | [] | [] | — |
| open_loop | encerrada | 12 | 127.6 | [0.0] | True / 5.0 / 18000 | {} | [] | [] | — |
| oraculo | encerrada | 12 | 127.6 | [0.0] | True / 5.0 / 18000 | {} | [] | [] | — |

### H13 — horizonte curto × longo (H2)

| N | H_L | MPC sem sinal [R$] | Hierárquico PWL [R$] | Avaliações | Tempo planejador [s] |
|---|---|---|---|---|---|
| 2 | 3 | 65.30 | 60.40 | 102 | 1.129 |
| 2 | 6 | 65.30 | 50.60 | 102 | 1.496 |
| 2 | 8 | 65.30 | 50.40 | 102 | 1.599 |
| 2 | 10 | 65.30 | 50.20 | 102 | 1.616 |
| 2 | 12 | 65.30 | 50.20 | 102 | 1.541 |
| 3 | 4 | 60.40 | 55.50 | 93 | 0.875 |
| 3 | 6 | 60.40 | 50.60 | 93 | 1.514 |
| 3 | 8 | 60.40 | 50.40 | 93 | 1.394 |
| 3 | 10 | 60.40 | 50.20 | 93 | 1.613 |
| 3 | 12 | 60.40 | 50.20 | 93 | 1.545 |
| 4 | 5 | 55.50 | 50.60 | 84 | 1.001 |
| 4 | 6 | 55.50 | 50.60 | 84 | 1.197 |
| 4 | 8 | 55.50 | 50.40 | 84 | 1.244 |
| 4 | 10 | 55.50 | 50.20 | 84 | 1.409 |
| 4 | 12 | 55.50 | 50.20 | 84 | 1.393 |

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
| PWL pontos=3, máx 9 | 50.20 | 12/0 | 61 | 0.965 | 3.55e-15 |
| PWL pontos=5, máx 9 | 50.20 | 12/0 | 93 | 1.539 | 3.55e-15 |
| PWL pontos=4, máx 4 (sem refinamento) | 55.50 | 7/5 | 75 | 1.357 | 1.67 |
| periódica P=2 | 50.20 | 12/0 | 87 | 1.465 | 3.55e-15 |
| periódica P=3 | 50.20 | 12/0 | 85 | 1.469 | 3.55e-15 |
| periódica P=4 | 50.20 | 12/0 | 84 | 1.308 | 3.55e-15 |

_Tempo total da evidência: 84.2 s (só este ambiente)._

## 3. Lectura (sin extrapolación)

* **Las correcciones no cambian ningún costo** de H1, H2, H3, H5, H7, H8, H10 (λ) ni H17 respecto de la entrega
  original; en H7/H8 el jerárquico PWL registra 5 exclusiones de dominio **certificadas** (cobertura con energía libre,
  `provenInfeasible`).
* **Anticipación** (MPC sin señal − jerárquico, misma N = 3, m = 1): H2 R$ 10,2, H5 R$ 10,2, H17 R$ 5,3 con condiciones
  terminales iguales; H1/H3 ⇒ 0. **Reoptimización** (open-loop − encolhido) = 0 en todas las instancias.
* **H7/H8**: MPC sin señal INVIABLE; jerárquico concluye — valor de reserva por restricción física. Local también falla.
* **H9 (tras B3C4-01 y B3C4-10)**: las cinco estrategias pedidas concluyen en k = 12 con condiciones terminales
  idénticas (E final 0 kWh, PEMFC encendida 5 kW, sin obligaciones pendientes): MPC 3C-3 sin señal R$ 129,8; PWL,
  referencia dura y blanda R$ 129,6 ⇒ **anticipación R$ 0,2 comparable**; horizonte completo/open-loop/oráculo
  R$ 127,6 (PEMFC 18 000 s en el estado). La brecha R$ 2,0 del jerárquico frente al óptimo de información perfecta (y
  R$ 2,2 del MPC sin señal) es COMÚN a ambos MPC cortos con `cumprir_na_janela` y N = U = 3 (B3C4-02): se atribuye a la
  condición de commitment, no a la aproximación del valor futuro. Reoptimización = 0. Ningún otro costo cambió.
* Una instancia sintética no establece superioridad general. Tiempos solo indicativos (4 CPU compartidas).

## 4. Auditoría del PR #17 — defectos reproducidos ANTES (`9630e73`, `8f48aed`, `8dd8edb`) y DESPUÉS (`c964a2e`, `8efc927`, `322ffa6`)

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

### 4.4 B3C4-10 — residuo negativo del solver en P_imp × C-01 (2ª auditoría, H9, `ControladorMPCConectado`)

Antes (HEAD auditado `8f48aed`; script con resolvedor de captura y espía sobre `plano_de_resultado_3c3`):
```
commit 8f48aede78fb240a2bfd0c5208f12bb1395c999e
missão: interrompida/integridade, k final = 10
janela: índice 10, k = 10, N_k = 2, m_k = 1, início 2026-01-01T10:00:00+00:00
P_imp bruto = ['-8.881784197001252e-16', '5.0'] | P_exp bruto = ['0.0', '0.0']
intervalo(s) global(is) com P_imp < 0: [(10, '-8.881784197001252e-16')]
HiGHS: classificação=otimo terminação=convergenceCriteriaSatisfied status=optimal estado=aceito_otimo aceito=True objetivo=20.049999999999997 gap_rel=0.0
auditor 3C-3 aceito: True | máximo PCC dominio/capacidade: {'pcc_dominio': (8.881784197001252e-16, 'kW', 1.5e-05), 'pcc_capacidade': (0.0, 'kW', 1.5e-05), 'pcc_exclusividade': (0.0, 'kW', 1.5e-05), 'balanco': (0.0, 'kW', 1.5e-05)}
PCC: modo=conectado sentidos=somente_importacao limite_imp=[50.0, 50.0] limite_exp=[0.0, 0.0] a=[1.0, 1.0]
tolerâncias: HiGHS primal_feasibility=1e-07, mip_feasibility=1e-06 (padrão; ConfiguracaoSolver não as altera); auditor D07 potência = 1e-05 + 1e-07·escala
variável P_imp: domínio NonNegativeReals (cota inferior 0) — o valor está ABAIXO da cota, dentro da tolerância do solver
primeira função que recusa: [('plano_de_resultado_3c3', '[intercambio_programado_invalido] resultado.intercambio[P_imp]: Exigidos 2 valores reais finitos >= 0 (sem recorte); recebido (-8.881784197001252e-16, 5.0).')]
efeito: [('falha_integridade', '[intercambio_programado_invalido] resultado.intercambio[P_imp]: Exigidos 2 valores reais finitos >= 0 (sem recorte); rec')]
```
Después (`8efc927`; la misma ventana k = 10):
```
commit 8efc927af4cdddc282d8eb729c46cfe505b17bee
missão: encerrada/None, k final = 12
resolução nº 10 (janela k = 10): estado=aceito_otimo aceito=True auditor=True
  bruto=-8.881784197001252e-16 normalizado=0.0 diferença=8.881784197001252e-16 limiar=1.3500311979441904e-13 escala=76.0
  intercâmbio programado: P_imp=(0.0, 5.0) P_exp=(0.0, 0.0)
  máximos do auditor: {'pcc_dominio': (0.0, 'kW', 1.5e-05), 'pcc_capacidade': (0.0, 'kW', 1.5e-05), 'pcc_exclusividade': (0.0, 'kW', 1.5e-05), 'balanco': (0.0, 'kW', 1.5e-05)}
  constatações: [('pemfc_abstracao_instantanea', 'aviso', 'compromisso.unidades[syn-fc].abstracao_transicao'), ('permanencia_maior_que_janela', 'aviso', 'compromisso.unidades[syn-fc]'), ('normalizacao_numerica_pcc', 'aviso', 'pcc[syn-pcc].P_imp[0]')]
resumo da resolução selado (códigos): ('normalizacao_numerica_pcc', 'pemfc_abstracao_instantanea', 'permanencia_maior_que_janela')
registro 3C-0: hash normalizacoes_pcc_b3c4_10 = 8db6d4bc00ba58b3 …; ['bruto=-8.881784197001252e-16 normalizado=0.0 diferenca=8.881784197001252e-16 limiar=1.3500311979441904e-13 esc']
anexo 3C-3 plano_rede.importacao_programada_kW = (0.0, 5.0)
```
H9 × 5 estrategias después (normalizaciones y proyecciones RECONSTRUIDAS de los artefactos sellados; `desvios` = constataciones de
`reconstruir_normalizacoes_pcc`; `aud3C3` = `auditar_missao_conectada`):
```
mpc_sem_sinal    encerrada  k=12 custo=129.8 E=[0.0] FC(lig=True,p=5.0,t=25200) obrig={} normalizacoes=[('P_imp', 0, -8.881784197001252e-16, 1.3500311979441904e-13)] desvios=0 projecoes=[(8, 1.7763568394002505e-15)] aud3C3=True
hier_pwl         encerrada  k=12 custo=129.6 E=[0.0] FC(lig=True,p=5.0,t=25200) obrig={} normalizacoes=[] desvios=0 projecoes=[] aud3C3=True
hier_ref_dura    encerrada  k=12 custo=129.6 E=[0.0] FC(lig=True,p=5.0,t=25200) obrig={} normalizacoes=[('P_imp', 0, -8.881784197001252e-16, 1.3500311979441904e-13)] desvios=0 projecoes=[(8, 1.7763568394002505e-15)] aud3C3=True
hier_ref_branda  encerrada  k=12 custo=129.6 E=[0.0] FC(lig=True,p=5.0,t=25200) obrig={} normalizacoes=[] desvios=0 projecoes=[] aud3C3=True
mpc_encolhido    encerrada  k=12 custo=127.60000000000001 E=[0.0] FC(lig=True,p=5.0,t=18000) obrig={} normalizacoes=[] desvios=0 projecoes=[] aud3C3=True
```
Lectura: el único residuo de H9 (−8,881784197001252e-16 kW ≤ ε_pcc = 1,35e-13 kW con S = 76) se normaliza en la
extracción, el auditor independiente revalida la solución (balance 0,0) y el plano de red programa 0,0; la normalización
queda en el resultado, en el resumen sellado de la resolución, en el registro 3C-0 (aviso + hash) y se reconstruye en la
auditoría. La regla C-01 sigue rechazando el MISMO valor si llega como consigna o programa externo
(`test_c01_consigna_externa_minima_negativa_recusada_pelo_executor`).

### 4.5 C-3C4-A03 — coherencia de las evidencias B3C4-10 y auditoría integral 3C-3

Cadenas selladas CONSISTENTES: el normalizador del resolvedor 3C-3 se sustituye durante la misión H9 (perfil 3C-3)
para fabricar (a) una normalización injustificada (bruto −1e-3) y (b) el código en la resolución sin aviso ni hash en el
registro 3C-0; ningún sello diverge. Antes (HEAD auditado `8dd8edb`):
```
commit 8dd8edbd8a1f6533285108a7b9d45d52076b2194
--- A03-2 normalização injustificada (cadeia selada consistente): situação=encerrada k=12
    k=10: códigos da resolução=('normalizacao_numerica_pcc', 'pemfc_abstracao_instantanea', 'permanencia_maior_que_janela') | hash no 3C-0=True | avisos no 3C-0=['normalizacao_numerica_pcc']
    reconstrução: normalizações=0 constatações=['normalizacao_pcc_fora_da_politica']
    auditoria integral 3C-3: aceito=True verificações={'cadeia_registros': True, 'livro_observacoes': True, 'temporal': True, 'causal': True, 'estado_e_permanencias': True, 'balanco': True, 'custos': True, 'aceitacao': True, 'separacao_previsao_realizacao': True, 'documental': True}
--- A03-1 código sem aviso nem hash (cadeia selada consistente): situação=encerrada k=12
    k=10: códigos da resolução=('normalizacao_numerica_pcc', 'pemfc_abstracao_instantanea', 'permanencia_maior_que_janela') | hash no 3C-0=False | avisos no 3C-0=[]
    reconstrução: normalizações=0 constatações=[]
    auditoria integral 3C-3: aceito=True verificações={'cadeia_registros': True, 'livro_observacoes': True, 'temporal': True, 'causal': True, 'estado_e_permanencias': True, 'balanco': True, 'custos': True, 'aceitacao': True, 'separacao_previsao_realizacao': True, 'documental': True}
--- válida: situação=encerrada k=12
    k=10: códigos da resolução=('normalizacao_numerica_pcc', 'pemfc_abstracao_instantanea', 'permanencia_maior_que_janela') | hash no 3C-0=True | avisos no 3C-0=['normalizacao_numerica_pcc']
    reconstrução: normalizações=1 constatações=[]
    auditoria integral 3C-3: aceito=True verificações={'cadeia_registros': True, 'livro_observacoes': True, 'temporal': True, 'causal': True, 'estado_e_permanencias': True, 'balanco': True, 'custos': True, 'aceitacao': True, 'separacao_previsao_realizacao': True, 'documental': True}
```
Después (`322ffa6`; la sección `normalizacoes_pcc` de la auditoría integral 3C-3 es la única que reprueba):
```
--- A03-2 normalização injustificada (cadeia selada consistente): situação=encerrada k=12
    k=10: códigos da resolução=('normalizacao_numerica_pcc', 'pemfc_abstracao_instantanea', 'permanencia_maior_que_janela') | hash no 3C-0=True | avisos no 3C-0=['normalizacao_numerica_pcc']
    reconstrução: normalizações=0 constatações=['normalizacao_pcc_fora_da_politica']
    auditoria integral 3C-3: aceito=False verificações={'cadeia_registros': True, 'livro_observacoes': True, 'temporal': True, 'causal': True, 'estado_e_permanencias': True, 'balanco': True, 'custos': True, 'aceitacao': True, 'separacao_previsao_realizacao': True, 'documental': True, 'normalizacoes_pcc': False}
--- A03-1 código sem aviso nem hash (cadeia selada consistente): situação=encerrada k=12
    k=10: códigos da resolução=('normalizacao_numerica_pcc', 'pemfc_abstracao_instantanea', 'permanencia_maior_que_janela') | hash no 3C-0=False | avisos no 3C-0=[]
    reconstrução: normalizações=0 constatações=['normalizacao_pcc_declarada_sem_registro']
    auditoria integral 3C-3: aceito=False verificações={'cadeia_registros': True, 'livro_observacoes': True, 'temporal': True, 'causal': True, 'estado_e_permanencias': True, 'balanco': True, 'custos': True, 'aceitacao': True, 'separacao_previsao_realizacao': True, 'documental': True, 'normalizacoes_pcc': False}
--- válida: situação=encerrada k=12
    k=10: códigos da resolução=('normalizacao_numerica_pcc', 'pemfc_abstracao_instantanea', 'permanencia_maior_que_janela') | hash no 3C-0=True | avisos no 3C-0=['normalizacao_numerica_pcc']
    reconstrução: normalizações=1 constatações=[]
    auditoria integral 3C-3: aceito=True verificações={'cadeia_registros': True, 'livro_observacoes': True, 'temporal': True, 'causal': True, 'estado_e_permanencias': True, 'balanco': True, 'custos': True, 'aceitacao': True, 'separacao_previsao_realizacao': True, 'documental': True, 'normalizacoes_pcc': True}
```
