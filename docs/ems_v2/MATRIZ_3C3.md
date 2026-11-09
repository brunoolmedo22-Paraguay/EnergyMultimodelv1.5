# Piso 3C-3 — Matriz de trazabilidad, resultados y reproducción (entregable L)

Requisito de la misión → implementación → verificación. Tests en `tests/ems_v2/test_ems_v2_3c3_*.py` (211 tests:
contrato 15, ejecución 15, MILP 15, MPC 18, regresión G15 13, aislamiento 3 + auditoría del PR #16: 132). "HiGHS" = test que ejecuta el solver real
(se salta explícitamente sin Pyomo/HiGHS).

| § misión | Requisito | Implementación | Verificación |
|---|---|---|---|
| 3 | PCC versionado: P_imp, P_exp, P_net, límites por intervalo, a_t, precios | `rede/contrato.py` `EspecPCC`, `series_pcc` | `test_casos_validos_sem_bloqueio`, `test_modo_e_sentidos_sem_padrao…` |
| 3 | Exclusividad MILP sin Big-M arbitrario | `milp/modelo_3c3.py` PCC1 + `w_pcc` | `test_g10_exclusividade…` (HiGHS) |
| 3 | 7 situaciones representables | fixtures G1–G4, G6, G12 | `test_g1…`, `test_g2…`, `test_g3…`, `test_g4…`, `test_g6…`, `test_isolado_declarado_identico_ao_3c1` |
| 3 | Red ausente ≠ ilimitada; capacidad cero ≠ intercambio | `modo_conexao_invalido`, `limite_pcc_ausente`, aviso `capacidade_contratada_nula` | `test_modo_e_sentidos…`, `test_limites_negativos_e_nulos` |
| 4 | Balance M02 extendido, aditivo, verificado | `construir_modelo_3c3` + `_verificar_extensao_m02` | `test_m02_3c3_sem_pcc_coincide…` |
| 4 | Restricciones originales intactas | composición sobre `construir_modelo_3c1` (inalterado) | `test_nucleo_com_commitment_preservado_com_pcc`, `test_isolado_declarado_identico_ao_3c1` |
| 4/11 | Auditor conoce la red; 3C-1 no desactivado | `rede/auditor.py` | `test_g14_solucao_alterada…`, `test_g14_disponibilidade_e_tarifa…` |
| 5 | Programado × realizado × desvío | `PlanoRede3C3`, `RegistroPassoPCC`, `desvios_intercambio` | `test_g5_erro_positivo…` (sin solver y HiGHS) |
| 5 | Ajuste local solo con conexión, disponibilidad, límites, sentido, política y evidencia | `ExecutorAlgebricoConectado3C3`, `PoliticaAjustePCC` | `test_g8_saturacao…`, `test_g6_exportacao_proibida…`, `test_sem_ajuste…`, `test_medicao_obrigatoria…` |
| 5 | Renovable limitada por disponibilidad; desvío físico registrado; exceso no inyectado | `injecao_renovavel` | `test_g7_renovavel_superestimado…`, `test_renovavel_acima_da_consigna_nao_e_injetado…` |
| 5 | Fallo clasificado y seguro; sin respaldo oculto | `pcc_saturado_*`, `pcc_indisponivel`, falla `consigna_inexequivel` | `test_g8_saturacao_do_pcc_sem_respaldo_oculto` (HiGHS) |
| 6 | Alcance físico declarado | rótulo `ROTULO_REDE`, `NAO_MODELADAS_3C3` | FORMULACAO_3C3 §0, §12 |
| 7 | Gasto de importación y crédito de exportación separados; unidades | `custos_modelo`, `economia_rede`, `contabilidade_realizada_3c3` | `test_g2…`, `test_g6_erro_negativo…` |
| 7 | Liquidación realizada explícita (medida × diferenciada) | `LIQUIDACOES` | `test_liquidacao_desvio_diferenciado_valores_analiticos` |
| 8 | Perfiles por intervalo (valor, unidad, bloque, procedencia, revisión, emisión, hash, regla) | `PerfilTarifario`, `hash_perfil` | `test_tarifas_faltantes_negativas_desconhecidas_e_blocos`, `test_json_canonico…` |
| 8 | Contractual × prevista × liquidación × desconocida; sin precio futuro salvo oráculo | `NATUREZAS_PRECO`, `selecionar_perfil_causal` | `test_dados_futuros_filtrados_na_tarifa`, `test_selecao_causal…`, `test_g11…` (r0/r1), `test_tarifa_de_decisao_ausente…` |
| 8 | Constantes, horarias, variables, con/sin remuneración, exportación prohibida | fixtures `tarifa`, G2/G3/G9/G11 | tests G2, G3, G9, G11 |
| 9 | Perfil explícito, sin Pyomo en contratos/preflight | `rede/contrato.py`, `rede/preflight.py` | `test_nucleo_rede_so_biblioteca_padrao_ao_importar` |
| 9 | No se hace pasar por 3C-1 | `FORMULACAO_3C3`, `plano_de_resultado_3c3` | `test_perfil_nao_se_faz_passar_por_3c1…`, `test_resolver_3c1_recusa_entrada_3c3…`, `test_plano_3c3_nao_se_faz_passar_por_3c1`, `test_anexo_3c3_selado…` |
| 10 | Punto de extensión mínimo del MPC | hooks en `mpc/orquestrador.py` + `rede/mpc.py` | G15 (`test_ems_v2_3c3_regressao_3c2.py`) |
| 10 | K6 con observaciones nuevas | libro con PCC + medidores | `test_g14_medicao_divergente…`, `test_missao_isolada_nao_vira_conectada…` |
| 10 | Isolado no pasa a conectado | modo en el modelo + `VinculoRede3C3` | `test_missao_isolada…`, `test_g13_retomada_recusa…` |
| 11 | Auditoría de misión independiente con PCC | `rede/auditoria.py` | `test_g11…`, `test_g14_auditoria_rejeita…` |
| 12 | G1–G15 | `fixtures_3c3`, `rede/experimentos.py` | tests G* + `EVIDENCIA_3C3_EJECUCION.md` |
| 13 | Open-loop × MPC con igualdad de condiciones; E_final y obligaciones | `rede/comparadores.py` | `test_comparacao_open_loop_vs_mpc…`, `test_comparador_recusa_tarifas_ou_pcc_diferentes` |
| 14 | Pisos anteriores intactos | guardias nominales (C-3C3-02) | `test_pisos_anteriores…pr15`, guardias 3B-P/3C-0/3C-2, G15 |
| Aud. #16 C-01 | Intercambio programado validado (finito ≥ 0; ambas consignas; comando = programa; sin recorte); defecto ⇒ datos/integridad; nunca `PassoAplicado` exitoso | `valor_intercambio_valido`, `ExecutorAlgebricoConectado3C3.programado/avancar`, `validar_programa`, `plano_de_resultado_3c3` | `test_c01_*` (120 casos, ambas políticas, con y sin programa) |
| Aud. #16 C-02 | Auditoría integral × analítica parcial; artefatos por ventana; registro de misión de red; vínculo modelo/configuración | `rede/auditoria.py` (`auditar_missao_conectada`, `auditar_missao_conectada_analitica`), `rede/persistencia.verificar_artefatos_carregados_3c3` | `test_c02_*` (12 casos adversariales) |
| 16.10 | Misión verificable y recuperable | anexos, vínculos, `retomar_controlador_conectado` | `test_g13_retomada…` |

## Hashes de los perfiles protegidos (base `a4c6b1c` → rama)

65 de los 66 módulos Python de `ems_v2` existentes en la base son **byte a byte idénticos** (git blob); el único
modificado es `ems_v2/mpc/orquestrador.py` (refactorización controlada). Ejemplos (SHA-256 del archivo, 16 hex):
`contracts.py` `0c9366f6c015208d`, `audit.py` `31d9e04099c2ded2`, `reference.py` `785e2edf902f7d0a`,
`milp/modelo.py` `a6116739a3b3d3e7`, `milp/solver.py` `de0431009d3f4d51`, `milp/modelo_3c1.py` `01c01cde0bd88af3`,
`milp/solver_3c1.py` `42796a9d6effec8e`, `compromisso/auditor.py` `88afdcb84d766830`, `ponte/execucao.py`
`a3f64678500a51d0`, `ponte/registro.py` `e28bea61bb9f122f`. Pins de regresión 3C-2
(`tests/ems_v2/dados/pins_3c2_base_a4c6b1c.json`, generados en la base antes de cualquier cambio):
SHA-256 `7c7fd2f7892a269d6db851c89f4445780036f03816807cd892ff24e2bdbf01ad`; E2 = `e880fa159d35…` (R$ 12,9).

## Reproducir

```bash
pip install -r requirements.txt -r requirements-ems_v2.txt pytest
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ems_v2 -q
PYTHONDONTWRITEBYTECODE=1 python -m ems_v2.milp.evidencia_3c3 docs/ems_v2/EVIDENCIA_3C3_EJECUCION.md 5
```
