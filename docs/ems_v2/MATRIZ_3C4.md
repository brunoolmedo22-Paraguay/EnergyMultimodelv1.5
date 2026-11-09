# Piso 3C-4 — Matriz de trazabilidad (requisito → código → prueba)

Base `10365c5`. "Prueba" = archivo `tests/ems_v2/test_ems_v2_3c4_<x>.py` (`contrato`, `auditor`, `milp`,
`planejador`, `mpc`, `isolamento`, `auditoria_pr17`, `b3c4_10`). Todo sintético/algebraico.

| Requisito de la misión | Código | Prueba |
|---|---|---|
| §2 auditoría del punto de partida, puntos de extensión, contradicciones versionadas | FORMULACAO_3C4 §2, §10 | `isolamento` (ningún archivo protegido cambia) |
| §3 Δ, H_S, ρ, H_L, H_F, T_M, τ_k, x_k; H_L > H_S ≥ ρ; sin 24 h por defecto; sin extrapolación | `contrato.validar_configuracao_planejador`, `planejador.horizonte_longo_em` | `contrato::test_configuracao_planejador_sem_padrao` |
| §4 V^tail desde la frontera, Φ_L explícito, sin doble conteo | `planejador.Planejador3C4.avaliar`, `TermoTerminal3C4` | `planejador::test_h10_*`, `planejador::test_phi_l_*`, `mpc::test_custo_realizado_nunca_contem_valor_futuro_e_decomposicao` |
| §5 alternativas (referencia, marginal, PWL, duras/blandas); signo λ_E; local ≠ global; duales prohibidos; indisponibilidad | `TIPOS_SINAL`, `planejador._sinal_*`, `valor.py` | `planejador::test_h10_sensibilidade_local_*`, `planejador::test_degradacao_*`, `mpc::test_h2_h14_*` |
| §5 factibilidad de perturbaciones, límites SOC, dominio, error, región de validez, costo | `planejador._modo_1d` (bisección de dominio, refinamiento), `QualidadeSinal` | `planejador::test_refinamento_*`, `mpc::test_h7_h8_*`, `milp::test_h11_*` |
| §5 varias baterías no separables | `_modo_2d` + `valor.convexidade_verificada`/`envoltoria_convexa` | `contrato::test_dois_bancos_*`, `milp::test_envoltoria_2d_*`, `mpc::test_h17_*` |
| §6 planificador: estado ejecutado, previsiones/tarifas causales, PCC 3C-3, física reutilizada, Pyomo+HiGHS, hashes, actualización | `planejador.py`, `milp/solver_3c4.py`, `mpc._previsao_longa` | `planejador::test_politica_periodica_*`, `mpc::test_h12_*` |
| §7 contrato de coordinación y rechazos | `SinalValorFuturo`, `validar_sinal`, `validar_sinal_para_entrada`, `validar_sinal_para_janela` | `contrato::test_sinal_*` |
| §8 perfil nuevo; 3C-3 histórico intacto; costos separados; auditor independiente | `milp/modelo_3c4.py`, `solver_3c4.py`, `hierarquia/auditor.py` | `milp::test_termo_nenhum_equivale_ao_3c3`, `milp::test_resolvedores_historicos_*`, `auditor::*`, `milp::test_h16_*` |
| §9 ciclo recedente jerárquico, estado ejecutado, K6/confirmaciones/checkpoints conservados | `hierarquia/mpc.py` | `mpc::*`, `planejador::test_degradacao_sem_valor_futuro_equivale_ao_mpc_3c3` |
| §10 memoria y commitment de generadores | modos `EstadoTerminalGerador`, `_validar_modos_memoria`, lema de rampas, auditor de modo | `contrato::test_modos_memoria_*`, `contrato::test_rampa_inativa_lema`, `auditor::test_modo_e_memoria_*`, `milp::test_selecao_de_modo_*`, `mpc::test_h9_*` |
| §11 H1–H18 | `fixtures_3c4.py`, `hierarquia/experimentos.py`, `milp/evidencia_3c4.py` | ver tabla de experimentos abajo |
| §12 efectos separados, condiciones terminales | `hierarquia/comparadores.py` | `mpc::test_h2_h14_*`, `mpc::test_h7_h8_*`, `mpc::test_h9_linha_de_base_*` |
| §13 tiempos, gaps, tolerancias, determinismo | `ResultadoPlanejamento.tempos_s`, `QualidadeSinal`, `impressao_coordenacao` | `planejador::test_custo_computacional_registrado`, `mpc::test_reproducao_deterministica` |
| §14 compatibilidad | guardias | `isolamento::*` + suites 3A–3C-3 |
| **Auditoría PR #17 — A01** registro final confrontado con sus fuentes | `mpc.verificar_registro_hierarquico`, `contagens_de`, `tempos_planejador_de`, `energias_executadas` | `auditoria_pr17::test_a01_*` (11 alteraciones re-selladas, ∞ sin re-sellar, objetos obligatorios, tiempos tras retomada) |
| **Auditoría PR #17 — A02** inviable solo con certificado; dominio indeterminado; diagnóstico por modo | `milp/solver_3c4.resolver_cobertura_3c4`, `planejador._cobertura/_modo_1d/_modo_2d/_sinal_pwl`, `contrato.ESTADOS_MODO/DiagnosticoModo` | `auditoria_pr17::test_a02_*` (función de factibilidad sintética, dos modos, certificado real MILP, H7/H8) |
| **Auditoría PR #17 — B3C4-01** proyección numérica auditada | `ponte/execucao.energia_apos_intervalo/projecao_numerica_energia`, `rede/execucao.py`, `auditoria.reconstruir_projecoes_energia` | `auditoria_pr17::test_b01_*` (extremos, capacidades, tolerancias, violaciones reales, continuidad, retomada 3C-3, H9 × 5), `isolamento::test_hotfix_b3c4_01_restrito_a_projecao_numerica` |
| **2ª auditoría PR #17 — B3C4-10** residuo negativo del solver en P_imp/P_exp normalizado SOLO en la extracción; C-01 intacta; registro sellado; reconstrucción auditada | `rede/execucao.normalizar_residuos_pcc/escala_balanco_pcc/limiar_residuo_pcc/NormalizacaoNumericaPCC`, `milp/solver_3c3.py`, `milp/solver_3c4.py`, `milp/resultado_3c3.py`, `rede/mpc._artefatos_registro`, `hierarquia/auditoria.reconstruir_normalizacoes_pcc` | `b3c4_10::*` (política pura, cotas con límites distintos, P_exp, cero/positivos, NaN/inf/bool, C-01 externa, resolvedores con HiGHS, transformaciones maliciosas, H9 sellado, adulteraciones), `isolamento::test_hotfix_b3c4_10_restrito_e_regra_c01_identica_a_base`, `auditoria_pr17::test_b01_h9_cinco_estrategias` |

| Experimento | Prueba |
|---|---|
| H1 | `mpc::test_h1_tarifa_plana_sem_incentivo_artificial` |
| H2, H14 | `mpc::test_h2_h14_comparacao_de_politicas_e_efeitos` |
| H3 | `mpc::test_h3_pico_dentro_do_horizonte_curto_sem_beneficio_adicional` |
| H4 | `planejador::test_h4_deslocamento_do_pico_muda_o_valor_coerentemente` |
| H5 | `mpc::test_h5_erro_de_previsao_mesma_verdade` |
| H6 | `planejador::test_h6_soc_baixo_medio_alto` |
| H7, H8 | `mpc::test_h7_h8_valor_de_reserva_por_restricao_fisica` |
| H9 | `mpc::test_h9_pemfc_obrigacoes_e_modos`, `mpc::test_h9_linha_de_base_comparavel_apos_hotfixes_B3C4_01_e_B3C4_10`, `b3c4_10::test_h9_*` |
| H10 | `planejador::test_h10_*` |
| H11 | `milp::test_h11_*`, `contrato::test_sinal_contra_entrada`, `planejador::test_degradacao_*` |
| H12 | `mpc::test_h12_causalidade_por_intervencao` |
| H13 | `planejador::test_h13_horizontes_curto_e_longo` |
| H15 | `mpc::test_h15_*` |
| H16 | `auditor::*`, `milp::test_h16_*`, `mpc::test_h16_*`, `mpc::test_h15_h16_*` |
| H17 | `mpc::test_h17_*`, `mpc::test_h9_*`, `milp::test_envoltoria_2d_*` |
| H18 | suites 3A–3C-3 (incl. `test_ems_v2_3c3_regressao_3c2.py`, pins E1–E8) + `isolamento` |

## Archivos protegidos (SHA-256, prefijo de 16) — base `10365c5` × rama (`8efc927`)

| Archivo | Base | Rama | Motivo |
|---|---|---|---|
| `ems_v2/ponte/execucao.py` | `a3f64678500a51d0` | `cdad389b48ee3d24` | **B3C4-01 (hotfix autorizado, PR #17)**: función compartida de la recurrencia + proyección numérica + aviso |
| `ems_v2/rede/execucao.py` | `71db8fd2e405e2ad` | `a910853ec3754ea6` | **B3C4-01**: usa la misma función (sin aritmética propia; `507c7ae2de09217a` en `c964a2e`) + **B3C4-10 (hotfix autorizado, 2ª auditoría)**: bloque `residuo_numerico_pcc_v1`; C-01 (`valor_intercambio_valido`, `programa_valido`, `validar_programa`, `plano_de_resultado_3c3`) idéntica a la base |
| `ems_v2/mpc/orquestrador.py` | `b6bdf9283a341ec8` | `b6bdf9283a341ec8` | idéntico |
| `ems_v2/rede/mpc.py` | `a7d9ae9f1c4032aa` | `3b3f0be105ce8b99` | **B3C4-10**: aviso + hash `normalizacoes_pcc_b3c4_10` en el registro 3C-0 (solo si hubo normalización) |
| `ems_v2/rede/contrato.py` | `15ce7e94794a25b9` | `15ce7e94794a25b9` | idéntico |
| `ems_v2/milp/modelo_3c3.py` | `8f219d85de898755` | `8f219d85de898755` | idéntico |
| `ems_v2/milp/solver_3c3.py` | `2424316383c96aab` | `067b48ff8a93e2ea` | **B3C4-10**: llamada a la política en la extracción (antes del auditor) |
| `ems_v2/milp/resultado_3c3.py` | `358071080abd0b16` | `76036b862802bd71` | **B3C4-10**: campo `normalizacoes_numericas = ()` |
| `ems_v2/compromisso/contrato.py` | `d1c6b0c90b095909` | `d1c6b0c90b095909` | idéntico |
| `ems_v2/contracts.py` | `0c9366f6c015208d` | `0c9366f6c015208d` | idéntico (validación 3A `e0 > C` sin cambios) |
| `ems_v2/ponte/registro.py` | `e28bea61bb9f122f` | `e28bea61bb9f122f` | idéntico |

Archivos existentes modificados: los dos de B3C4-01, los cuatro de B3C4-10 (`rede/execucao.py` es común a ambos:
`ponte/execucao.py`, `rede/execucao.py`, `milp/solver_3c3.py`, `milp/resultado_3c3.py`, `rede/mpc.py`) + guardias de tests
ajustadas nominalmente `tests/ems_v2/test_ems_v2_{3c2_isolamento,3c3_isolamento,ponte_isolamento,milp_perfil}.py`
(C-3C4-02 y B3C4-01); las listas `HOTFIX_B3C4_10`/`REMOVIDAS_B3C4_10` están en `test_ems_v2_3c4_isolamento.py`.
