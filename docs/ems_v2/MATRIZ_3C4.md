# Piso 3C-4 — Matriz de trazabilidad (requisito → código → prueba)

Base `10365c5`. "Prueba" = archivo `tests/ems_v2/test_ems_v2_3c4_<x>.py` (`contrato`, `auditor`, `milp`,
`planejador`, `mpc`, `isolamento`). Todo sintético/algebraico.

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

| Experimento | Prueba |
|---|---|
| H1 | `mpc::test_h1_tarifa_plana_sem_incentivo_artificial` |
| H2, H14 | `mpc::test_h2_h14_comparacao_de_politicas_e_efeitos` |
| H3 | `mpc::test_h3_pico_dentro_do_horizonte_curto_sem_beneficio_adicional` |
| H4 | `planejador::test_h4_deslocamento_do_pico_muda_o_valor_coerentemente` |
| H5 | `mpc::test_h5_erro_de_previsao_mesma_verdade` |
| H6 | `planejador::test_h6_soc_baixo_medio_alto` |
| H7, H8 | `mpc::test_h7_h8_valor_de_reserva_por_restricao_fisica` |
| H9 | `mpc::test_h9_pemfc_obrigacoes_e_modos`, `mpc::test_h9_linha_de_base_*_B3C4_01` |
| H10 | `planejador::test_h10_*` |
| H11 | `milp::test_h11_*`, `contrato::test_sinal_contra_entrada`, `planejador::test_degradacao_*` |
| H12 | `mpc::test_h12_causalidade_por_intervencao` |
| H13 | `planejador::test_h13_horizontes_curto_e_longo` |
| H15 | `mpc::test_h15_*` |
| H16 | `auditor::*`, `milp::test_h16_*`, `mpc::test_h16_*`, `mpc::test_h15_h16_*` |
| H17 | `mpc::test_h17_*`, `mpc::test_h9_*`, `milp::test_envoltoria_2d_*` |
| H18 | suites 3A–3C-3 (incl. `test_ems_v2_3c3_regressao_3c2.py`, pins E1–E8) + `isolamento` |

## Archivos protegidos (SHA-256, prefijo de 16) — idénticos a la base `10365c5`

| Archivo | Base | Rama |
|---|---|---|
| `ems_v2/mpc/orquestrador.py` | `b6bdf9283a341ec8` | `b6bdf9283a341ec8` |
| `ems_v2/rede/mpc.py` | `a7d9ae9f1c4032aa` | `a7d9ae9f1c4032aa` |
| `ems_v2/rede/contrato.py` | `15ce7e94794a25b9` | `15ce7e94794a25b9` |
| `ems_v2/milp/modelo_3c3.py` | `8f219d85de898755` | `8f219d85de898755` |
| `ems_v2/milp/solver_3c3.py` | `2424316383c96aab` | `2424316383c96aab` |
| `ems_v2/compromisso/contrato.py` | `d1c6b0c90b095909` | `d1c6b0c90b095909` |
| `ems_v2/contracts.py` | `0c9366f6c015208d` | `0c9366f6c015208d` |
| `ems_v2/ponte/registro.py` | `e28bea61bb9f122f` | `e28bea61bb9f122f` |

Únicos archivos existentes modificados (nominales, C-3C4-02): `tests/ems_v2/test_ems_v2_{3c2_isolamento,3c3_isolamento,
ponte_isolamento,milp_perfil}.py`.
