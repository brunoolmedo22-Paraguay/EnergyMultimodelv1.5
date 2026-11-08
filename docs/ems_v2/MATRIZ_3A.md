# Piso 3A — Matriz de trazabilidad requisito → ecuación → archivo → test → resultado

Todas las pruebas son **sintéticas/algebraicas** (marcador `synthetic_algebraic`); ninguna es validación física.
Comando: `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ems_v2 -q` → **235 passed** (2026-11-08, tras las correcciones C-3A-01..03; antes 135).

Estados: `implemented` (contrato/referencia/auditor + test verde) · `test_spec_only` (resultado teórico registrado,
sin solver) · `not_applicable` (fuera de 3A, rechazado explícitamente).

## Casos analíticos y bloqueadores B01–B05

| Req. | Ecuación | Archivo(s) | Test(s) (`tests/ems_v2/…`) | Resultado | Estado |
|---|---|---|---|---|---|
| A01 | M01 | `timegrid.py`, `reference.energia_kWh`, `audit.auditar` | `test_ems_v2_malha_unidades::test_a01_60_intervalos_61_fronteiras_60_kWh` | 60 intervalos, 61 fronteras, 60 kWh exactos; auditor acepta | implemented |
| A02 | M01 | ídem | `…::test_a02_10_kW_um_minuto_um_sexto_exato`, `…::test_instante_terminal_nao_e_integrado` | 1/6 kWh exacto; vector de 61 valores ⇒ `instante_terminal_como_intervalo` | implemented |
| A03 | M07, M08 | `reference.trajetoria_energia_bess`, `audit` | `test_ems_v2_referencia::test_a03_*`, `test_ems_v2_auditor::test_candidatas_analiticas_aceitas[A03, A03-60]` | e₁ = 50 kWh, SOC = 1/2 (1×60 min y 60×1 min) | implemented |
| A04 | M07, M08 | ídem | `test_ems_v2_referencia::test_a04_carga`, auditor `[A04]` | e₁ = 69 kWh, SOC = 69/100 | implemented |
| B01 (A) | M03-v1.1, B01-KPI, M21-CURT | `reference.renovavel_v11`, `audit` | `test_ems_v2_referencia::test_b01a_*`, `test_ems_v2_auditor::test_b01_custos_e_kpis_reconstruidos` | P = 0, C_oper = 0, E_indisp = 100 kWh, costo R$ 0 | implemented |
| B01 (B) | ídem | ídem | `…::test_b01b_curtailment_operacional`, auditor `[B01B]` | C_oper = 20 kW, E_curt = 20 kWh, costo R$ 10 | implemented |
| B01 (negativo) | M03-v1.1, M21-CURT | `audit` | `test_ems_v2_auditor::test_indisponibilidade_cobrada_como_vertimento`, `test_ems_v2_contrato::test_politicas_terminal_e_objetivo` | a = 0 con C_oper > 0 ⇒ rechazo; costo inflado ⇒ rechazo; término `indisponibilidade_como_curtailment` prohibido | implemented |
| B02 / A05-FEAS | M02, M06, M07 | `fixtures.a05_feas`, `audit` | `test_ems_v2_auditor::test_a05_feas_carregar_e_verter_ambos_factiveis`, `test_ems_v2_referencia::test_a05_feas_*` | Cargar 10 kW (+9 kWh) y verter 10 kW: **ambos factibles**; no se infiere optimalidad | implemented |
| B02 / A05-OPT | M21-v1.1 | `fixtures.a05_opt_entrada`, `fixtures.CASOS` | `test_ems_v2_contrato::test_a05_opt_registrado_mas_nao_executavel_no_3A`, `test_ems_v2_referencia::test_casos_so_especificacao_*` | Resultado teórico P_c = 10, C_oper = 0, e₁ = 59, costo 0 registrado; validación 3A ⇒ `termo_objetivo_nao_suportado_3A` | test_spec_only |
| B03 | M01–M23 + v1.1 | `ems_v2/catalogo/*`, `catalog.py` | `test_ems_v2_catalogo_cobertura::*` (10 tests) | 150 símbolos, 42 ecuaciones; etiquetas `\tag` extraídas automáticamente = cubiertas; 0 indefinidos; activos con código resoluble; futuros no presentados como capacidad | implemented |
| B04 / A06 | M10, M15, M16 (M17 parte h·q) | `reference.vazao_pwl`, `audit.auditar_pwl`, `contracts.validar_curva` | `test_ems_v2_referencia::test_a06_pwl_sintetica`, `test_ems_v2_auditor::test_a06_*`, `test_ems_v2_contrato::test_gerador_curva_variante_e_b04` | q = 9/10 kg/h, m = 3/200 kg en 1 min; ON a 5 kW inválido; OFF p = q = 0; curva `real` ⇒ pendente | implemented (referencia) / solver 3B |
| B05 | M05, M17, M20–M21-MULTI | catálogo (`variante`) | `test_ems_v2_catalogo_cobertura::test_variantes_exclusivas_derivadas_e_sem_mistura`, `test_ems_v2_contrato::test_gerador_curva_variante_e_b04` | Variantes excluyentes verificadas; multimodo ⇒ `multimodo_nao_suportado_3A` | implemented (catálogo) |
| B05A | B05-MULTI-H2 | `reference.massa_modo_kg`, `fixtures.CASOS` | `test_ems_v2_referencia::test_b05a_*` | 1/300 kg (aritmética de referencia); autómata no construido | test_spec_only |
| A07 | M04, M10 | `fixtures.CASOS["A07"]` | `test_ems_v2_referencia::test_casos_so_especificacao_*` | Teórico: inviable en servicio duro | test_spec_only |
| A08 | M04, M22 | `fixtures.CASOS["A08"]` | ídem | Teórico: χ = 0 inviable; χ = 1 ENS = 5 kWh | test_spec_only |

## Requisitos de la matriz Work asignados a 3A

| Req. | Ecuación | Archivo(s) | Test(s) | Resultado | Estado |
|---|---|---|---|---|---|
| R01 | M01 | `timegrid.py` | A01/A02 | ver arriba | implemented |
| R02 | M01, §14 | `series.py` | `test_ems_v2_contrato::test_semantica_resolucao_cobertura_e_causalidade` | muestra instantánea como media ⇒ rechazo; sin remuestreo | implemented |
| R03 | M01 | `series.py`, `timegrid.py` | `…::test_nan_na_serie_nunca_vira_zero`, `…::test_serie_de_instantes_*`, `…::test_periodo_final_duplicado_rejeitado`, `test_ems_v2_malha_unidades::test_fuso_*` | NaN, huecos, duplicados, no monótonos, fuso ambiguo, cobertura y extrapolación ⇒ rechazo | implemented |
| R04 | M02, M04 | `contracts.py`, `series.py`, `audit.py` | `test_ems_v2_contrato::test_potencia_bruta_misturada_ao_barramento_rejeitada`, `…::test_convencao_de_sinais_e_fronteira_fixas`; balance auditado en todos los casos | frontera ≠ bus ⇒ rechazo; balance ≤ 1e-5 kW + 1e-7 P_scale (provisional) | implemented |
| R27 | §12 | `contracts.PoliticaTerminal` | `test_ems_v2_contrato::test_politicas_terminal_e_objetivo` | `nenhuma` solo con justificación; otras ⇒ pendente (D02) | implemented (contrato) |
| R30 | M01, §13 | `timegrid.py` | `test_ems_v2_malha_unidades::test_campos_temporais_separados_e_regras`, `…::test_horizonte_alem_da_missao_e_hf_nao_declarado` | H_o = NΔ, ρ = mΔ, H_f ≥ H_o, divisibilidad o rechazo | implemented |
| R46 | Arquitectura | `parameters.py`, `provenance.py` | `test_ems_v2_malha_unidades::test_parametros_invalidos`, `…::test_parametro_bruto_*`, `test_ems_v2_contrato::test_campos_cientificos_sem_padrao_implicito` | valor/unidad/fuente/cadena; `null` rechaza la capacidad; sin valores por defecto | implemented |
| R32 (anticipado) | §17 | `audit.py` | `test_ems_v2_auditor::test_toda_mutacao_isolada_*` + 14 tests | toda mutación aislada ±1e-3 en 7 casos rechazada; independencia por AST | implemented (auditor); integración con solver 3B |

## Rechazos explícitos de `05_FIXTURES_Y_PUERTAS.md`

| Rechazo | Test |
|---|---|
| UID duplicado | `test_ems_v2_contrato::test_uid_duplicado_entre_familias` |
| NaN/Inf | `…::test_nan_na_serie_nunca_vira_zero`, `test_ems_v2_auditor::test_vetores_temporais_incompativeis_e_ausentes` |
| Horas locales sin zona | `test_ems_v2_malha_unidades::test_fuso_ambiguo_ou_invalido_rejeitado`, `test_ems_v2_contrato::test_serie_de_instantes_*` |
| Timestamps no monótonos / resolución no declarada | `test_ems_v2_contrato::test_serie_de_instantes_*`, `…::test_semantica_resolucao_cobertura_e_causalidade` |
| Eficiencia ≤ 0 o > 1 | `…::test_bateria_eficiencia_capacidade_soc`, `test_ems_v2_malha_unidades::test_parametros_invalidos` |
| SOC inicial fuera de [SOC_min, SOC_max] | `test_ems_v2_contrato::test_estado_inicial_bateria` |
| Potencia de bus mezclada con bruta | `…::test_potencia_bruta_misturada_ao_barramento_rejeitada` |
| Carga crítica tratada como `ℓ > 0` | `…::test_demanda_critica_e_interrompivel`, `test_ems_v2_auditor::test_demanda_critica_falsamente_interrompida` |
| `A_pot = 0` por dato ausente | NaN/ausente ⇒ rechazo (`test_nan_na_serie_nunca_vira_zero`); ver hipótesis H-3A-09 |
| `a = 0` y `C_oper > 0` como curtailment | `test_ems_v2_auditor::test_indisponibilidade_cobrada_como_vertimento` |
| SOC saturado por `clip` | `test_ems_v2_auditor::test_soc_saturado_por_recorte_rejeitado`, `test_ems_v2_referencia::test_recorrencia_sem_recorte` |
| 60 intervalos + instante final = 61 integraciones | `test_ems_v2_malha_unidades::test_instante_terminal_nao_e_integrado`, auditor `instante_terminal_como_intervalo` |
| Candidato adulterado (potencia, disponibilidad, estado) | `test_ems_v2_auditor::test_toda_mutacao_*`, `…::test_mutacao_de_disponibilidade_na_entrada`, `…::test_mutacao_do_estado_inicial_na_entrada` |
| Carga y descarga simultáneas | `…::test_carga_e_descarga_simultaneas_rejeitadas_mesmo_com_energia_coerente` |
| Descarte sin dispositivo físico | `…::test_descarte_sem_dispositivo_fisico_e_com_dispositivo` |
| Descarte negativo (generación ficticia), con y sin dispositivo — **C-3A-01** | `test_ems_v2_auditor::test_c3a01_descarte_negativo_sem_dispositivo_rejeitado`, `…::test_c3a01_descarte_negativo_com_dispositivo_rejeitado`, control `…::test_c3a01_descarte_nulo_sem_dispositivo_continua_aceito` |
| Tolerancia NaN/Inf/negativa/no numérica — **C-3A-02** | `test_ems_v2_auditor::test_c3a02_tolerancia_invalida_rejeita_explicitamente` (77 casos), `…::test_c3a02_tolerancias_provisorias_inalteradas_e_validas` |
| Estructura JSON incompatible / tupla de longitud incorrecta / vértices PWL malformados / NaN literal — **C-3A-03** | `test_ems_v2_contrato::test_c3a03_vertices_pwl_malformados_rejeitados`, `…::test_c3a03_estruturas_incompativeis_rejeitadas`, `…::test_c3a03_constantes_nao_padrao_rejeitadas`, `…::test_c3a03_ida_e_volta_sem_perda_em_todas_as_fixtures` |

## Condiciones de la fiscalización

| Cond. | Evidencia |
|---|---|
| A — auditor independiente | `audit.py` en punto flotante/segundos/bisección, sin importar `reference` (`test_auditor_independente_do_calculo_de_referencia`); esperados = literales analíticos; tests de mutación |
| B — activos/futuros/variantes | `test_simbolos_ativos_tem_codigo_e_futuros_nao_se_passam_por_capacidade`, `test_variantes_exclusivas_*`, `test_nenhum_simbolo_usado_indefinido_e_nenhum_orfao` |
| C — sin valores implícitos | `test_campos_cientificos_sem_padrao_implicito`, `test_parametro_opcional_ausente_e_pendente_nao_presumido`, `parametro_ausente` en contratos |
| D — tolerancias provisionales | `Tolerancias.status == "provisoria"`; ninguna tolerancia modificada para obtener verde; valores fijados por `test_c3a02_tolerancias_provisorias_inalteradas_e_validas`; inválidas ⇒ `tolerancia_invalida` (C-3A-02) |
| E — documentación acotada | `CLAUDE.md`, `HANDOFF.md`, `PARAMIJEFE.md` solo registran arquitectura experimental y estado real |
| F — A05-OPT/A07/A08/B05A como especificación | `test_casos_so_especificacao_nao_sao_resultados_executados` |

## Correcciones de la auditoría del PR #11

| Hallazgo | Ecuación / requisito | Archivo | Test(s) | Resultado | Estado |
|---|---|---|---|---|---|
| C-3A-01 descarte negativo | M04 (`0 <= d <= D̄`), M02 | `ems_v2/audit.py` | `test_c3a01_*` (3) | d = −10 rechazado con y sin dispositivo; d = 0 aceptado | implemented |
| C-3A-02 tolerancias inválidas | §17, D07 | `ems_v2/audit.py` (`validar_tolerancias`) | `test_c3a02_*` (78) | rechazo explícito `tolerancia_invalida`; valores provisionales intactos | implemented |
| C-3A-03 serialización con pérdida | R46, R49 (procedencia/integridad) | `ems_v2/contracts.py` (`_construir`, `de_dict`, `entrada_de_json`, `ErroSerializacao`) | `test_c3a03_*` (19) | estructuras incompatibles rechazadas; ida y vuelta idéntica | implemented |
