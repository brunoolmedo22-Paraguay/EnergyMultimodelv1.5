# Piso 3B-P — Matriz de trazabilidad requisito → ecuación → implementación → test → resultado

Todos los tests son **sintéticos/algebraicos** (`synthetic_algebraic`) y se ejecutan contra **HiGHS real** (sin
Pyomo, los de solver se saltan explícitamente). Comandos y resultados en la descripción del PR y en
[`EVIDENCIA_3BP.md`](EVIDENCIA_3BP.md).

- `tests/ems_v2/test_ems_v2_milp_casos.py`: 32 tests.
- `tests/ems_v2/test_ems_v2_milp_integridade.py`: 41 tests.
- `tests/ems_v2/test_ems_v2_milp_perfil.py`: 13 tests.
- `tests/ems_v2/test_ems_v2_milp_auditoria_3b.py` (correcciones C-3B-01..03): 62 tests.
- Total nuevo: 148. `tests/ems_v2` completo: **416 passed** (268 del 3A + 148).

Abreviaturas: `casos::` = `test_ems_v2_milp_casos.py`, `integ::` = `test_ems_v2_milp_integridade.py`,
`perfil::` = `test_ems_v2_milp_perfil.py`, `aud3b::` = `test_ems_v2_milp_auditoria_3b.py`. Todos los módulos de implementación están en `ems_v2/`.

## Puerta G3B-P (orden ejecutiva §8)

| Req. | Ecuación | Implementación | Test(s) | Resultado (HiGHS 1.15.1) | Estado |
|---|---|---|---|---|---|
| A01 | M01, M02, M03-v1.1 | `milp/modelo.py`, `milp/solver.py` | `casos::test_a01_sessenta_intervalos_sem_energia_terminal` | 60 intervalos, 61 fronteras, 60 kWh (no 61) | implemented |
| A02 | M01 | ídem | `casos::test_a02_um_sexto_de_kWh` | 1/6 kWh | implemented |
| A03 | M06–M08 | ídem | `casos::test_a03_descarga_com_eficiencia[60-1, 1-60, 15-4]` | e_N = 50 kWh en 1×60, 60×1 y 4×15 min | implemented |
| A04 | M06–M08, M21-CURT | ídem + `fixtures_3b.a04` (c_curt declarado) | `casos::test_a04_carga_com_eficiencia` | P_c = 10 kW, e₁ = 69 kWh | implemented |
| B01A | M03-v1.1, B01-KPI | ídem + auditor | `casos::test_b01a_indisponibilidade_sem_penalidade` | P = C = 0; E_indisp = 100 kWh; costo R$ 0 | implemented |
| B01B | M21-CURT | ídem | `casos::test_b01b_custo_operacional_reconstruido` | C_oper = 20 kW; R$ 10 (modelo = auditor = solver) | implemented |
| A05-FEAS | M02, M06, M07 | `milp/modelo.py` (variables fijadas en el test) | `casos::test_a05_feas_carregar_e_verter_sao_ambos_factiveis_com_objetivo_nulo` | Cargar (e₁ = 59) y verter (C_oper = 10): ambos óptimos con objetivo 0 y aceptados por el auditor | implemented |
| A05-OPT | M21-v1.1 | ídem | `casos::test_a05_opt_solver_encontra_a_carga` | **Lo encuentra el solver**: P_c = 10 kW, C_oper = 0, e₁ = 59 kWh, R$ 0, gap 0 | implemented |
| A06 | M10, M14–M16, B05-INST (h·q) | ídem | `casos::test_a06_pwl_sintetica_milp`, `casos::test_a06_on_a_5_kW_e_inviavel_e_off_tem_p_q_nulos` | q = 0,9 kg/h, 0,015 kg/min, R$ 0,15; ON a 5 kW inviable; OFF p = q = 0 | implemented |
| PWL ≥3 vértices, no convexa | M14–M16 | ídem | `casos::test_pwl_nao_convexa_quatro_vertices_vazao_exata` (8 cargas), `casos::test_pwl_nao_convexa_com_bateria_igual_a_enumeracao` (5 c_thr) | q = interpolación racional exacta; óptimo = **enumeración independiente** (sin Pyomo); vértice interno p = 16 kW, R$ 12,5 | implemented |
| A07 | M04, M10 | ídem | `casos::test_a07_minimo_tecnico_sem_sumidouro_e_inviavel` | `provenInfeasible`; sin sumidero ni reducción de P_min | implemented |
| A08 duro | M04 | ídem | `casos::test_a08_servico_duro_inviavel` | inviable | implemented |
| A08 degradado | M04, M21-v1.1 (V·ℓ) | ídem + `fixtures_3b.a08` (V = 2 R$/kWh declarado) | `casos::test_a08_servico_degradado_minima_ens_5_kWh` | ℓ = 5 kW, ENS = 5 kWh, R$ 10 | implemented |

## Pruebas adicionales de integridad

| Requisito | Test(s) | Resultado |
|---|---|---|
| Inviabilidad sin incumbent | A07/A08 duro; `integ::test_modelo_inviavel_trivial_sem_chamar_o_solver` | sin despacho; la inviabilidad trivial se detecta en la construcción |
| Tiempo límite sin incumbent (**real**) | `integ::test_limite_de_tempo_real_sem_incumbente_nenhum_despacho`, `integ::test_limite_de_nos_real_sem_incumbente` | `maxTimeLimit` / `iterationLimit` + `noSolution` ⇒ `sem_solucao` |
| Incumbent no óptimo (**real**) | `integ::test_incumbente_real_nao_otimo_e_auditado` | `iterationLimit` + `feasible`, objetivo > óptimo, gap > 0, auditado ⇒ `aceito_factivel_nao_otimo` |
| Tiempo límite con incumbent (**simulado** en el adaptador) | `integ::test_limite_de_tempo_simulado_com_incumbente_aceito_como_nao_otimo`, `…_sem_incumbente_nao_carrega_valores` | clasificación y auditoría correctas; sin incumbent no se carga nada (real no determinista: ver EVIDENCIA) |
| Estado desconocido, error, ilimitado | `integ::test_estados_nao_despachaveis` (6), `integ::test_classificacao_exaustiva_sobre_os_enums_do_pyomo` | ningún despacho; solo (convergencia o límite) × (optimal/feasible) son despachables |
| Modelo sin solución útil / valores no cargados | `integ::test_valores_nao_carregados_nunca_viram_nan_no_despacho` | `valor_nao_carregado`, sin NaN en el despacho |
| Parámetros ausentes | `integ::test_parametro_economico_ausente_bloqueia`, `…_fisico_…`, `perfil::test_coeficientes_obrigatorios_nunca_presumidos` | `bloqueado_validacao`; el solver no se llama |
| Varios UIDs | `casos::test_varios_uids_distintos` | 2 FV, 2 cargas, 2 BESS, PEMFC ON y térmica OFF; auditoría y costos coinciden |
| Dos baterías heterogéneas | `casos::test_duas_baterias_heterogeneas_analitico` | 8,75 / 6,25 kW; R$ 1,1875 (analítico) |
| Exclusividad (sin simultaneidad) | `casos::test_exclusividade_impede_ciclar_para_esconder_vertimento` | R$ 18,888… > 17,2 (solución con simultaneidad, prohibida) |
| Candidata adulterada después de resolver | `integ::test_solucao_adulterada_apos_resolver_e_rejeitada` (potencia, estado, simultaneidad) | `rejeitado_auditoria` |
| Integridad violada | `integ::test_integralidade_violada_rejeitada` | u = 0,5 ⇒ rechazada |
| PWL con segmento incorrecto | `integ::test_pwl_com_segmento_errado_rejeitada` | cuerda en lugar de la curva ⇒ `vazao_pwl` rechazada |
| Objetivo incoherente con los valores | `integ::test_objetivo_incoerente_com_os_valores_rejeitado` | rechazado |
| Reproducibilidad | `integ::test_reprodutibilidade_das_fixtures_e_das_solucoes` | mismo JSON, hash, despacho y objetivo |
| HiGHS no hace SOS ni no lineal; modelo lineal | `integ::test_highs_recusa_sos_e_nao_linearidade` | rechazos reales; el modelo 3B-P tiene grado ≤ 1 y no usa SOS |
| Configuración explícita / inválida; solver ausente | `integ::test_configuracao_invalida_bloqueia` (7), `integ::test_solver_indisponivel_sem_falha` | bloqueo controlado |
| Compromiso libre / con transición | `integ::test_compromisso_livre_ou_com_transicao_bloqueado` (5) | `pendente` / `erro`; sin solver |

## Obstáculos A/B y catálogo

| Requisito | Implementación | Test(s) | Estado |
|---|---|---|---|
| A: perfil explícito y versionado | `contracts.PERFIS_FORMULACAO`, `_coeficientes_3bp` | `perfil::test_perfil_3A_inalterado_e_3BP_explicito`, `perfil::test_regras_de_combustivel_e_ens_no_3BP`, `integ::test_entrada_3A_nao_ganha_capacidades_implicitamente`, `integ::test_degradado_sem_criterio_ens_bloqueia` | implemented |
| A: contrato 3A intacto (texto y hash) | `contracts.CAMPOS_EXTENSAO_3BP` | `perfil::test_campos_novos_nao_alteram_o_json_nem_o_hash_das_entradas_3A` + los 268 tests del 3A | implemented |
| B: auditor independiente para cada familia declarada | `audit._auditar_geradores`, `audit._custos_3bp` | `perfil::test_auditor_*` (4), tests de adulteración | implemented |
| Capacidades y catálogo únicos y coherentes | `capabilities.CAPACIDADES_3BP`, catálogo `status_3BP`/`codigo_3BP` | `perfil::test_capacidades_*`, `perfil::test_catalogo_3BP_*` (2) | implemented |
| Aislamiento | solo `ems_v2/milp/{modelo,solver,ambiente}.py` importan Pyomo/HiGHS | `perfil::test_so_o_subpacote_milp_importa_pyomo_ou_highspy`, 3A `test_ems_v2_isolamento` (sin cambios) | implemented |

## Requisitos de la matriz Work asignados a 3B

| Req. | Estado 3B-P | Evidencia |
|---|---|---|
| R05 renovable usada/vertida | implemented | A05, B01 |
| R06 carga no servida ≠ energía creada | implemented | A08 |
| R07 descarte solo con destino físico | implemented | A07; `d` solo con dispositivo (catálogo) |
| R08 exclusividad | implemented | exclusividad |
| R09/R10 energía y SOC sin recorte | implemented | A03/A04, dos BESS, adulteración de `e` |
| R17/R18 PWL caudal y dominio ON/OFF | implemented (curva sintética) | A06, PWL no convexa |
| R19 sin SOS ni no linealidad | implemented | `test_highs_recusa_sos_e_nao_linearidade` |
| R25 costo reconstruido | implemented | B01B, A08, multi-UID (auditor = modelo = solver) |
| R32 evaluador independiente | implemented | auditor sin Pyomo; adulteraciones |
| R33 óptimo / factible / sin solución | implemented | terminaciones reales y simuladas |
| R12–R16 commitment, rampas, permanencias | **not implemented** (3C) | programa fijo constante; transiciones bloqueadas |

## Correcciones de la auditoría del PR #12

| Hallazgo | Ecuación / requisito | Implementación | Test(s) | Resultado | Estado |
|---|---|---|---|---|---|
| C-3B-01 identidad y preflight del compromiso | M10 (programa fijo), R33 | `milp/solver._canonico`, `_hash_compromisso`; `milp/config.programa_valido`, `preflight_3bp`; `audit._auditar_geradores` | `aud3b::test_c3b01_*` (24) | 21 programas inválidos ⇒ `bloqueado_validacao` sin excepción ni solver; hash sin pérdida, determinista e independiente del orden | implemented |
| C-3B-02 testigo auxiliar del MILP | M06 (z_b), M14–M16 (δ, θ) | `milp/integridade.verificar_testemunho`; extracción de δ/θ en `milp/solver._extrair`; estado `rejeitado_integridade` | `aud3b::test_c3b02_*` (20) | z_b fraccional o incoherente, δ en otro segmento o fraccional, θ fuera del segmento o de [0,1] ⇒ rechazados; sin valor o no finito ⇒ `sem_despacho`; soluciones legítimas íntegras; tolerancias no relajadas | implemented |
| Robustez a excepciones del solver y del cargador; opciones HiGHS | R33 | `milp/solver._validar_opcoes_highs`, `try/except` en `resolver` | `aud3b::test_opcao_highs_invalida_*`, `aud3b::test_excecao_*` (5) | `erro` controlado (`opcao_highs_invalida`, `falha_solver`, `falha_carregamento`), sin despacho | implemented |
| C-3B-03 metadatos de configuración antes de validar | R33, configuración explícita | `milp/solver.resolver` (valida antes del registro), `milp/config.configuracao_registro` (sin excepciones, sin reinterpretación) | `aud3b::test_c3b03_*` (13) | `opcoes_highs` inválidas (None, 42, "abc", 3.5, lista de pares, tupla, bool, dict reservado) y configuraciones de tipo incorrecto ⇒ `bloqueado_validacao` + `configuracao_invalida`, valor original preservado; registro válido sin cambios | implemented |
