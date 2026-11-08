# Piso 3C-0 — Evidencia de pruebas (entregable E)

Entorno: Python 3.13.18, `requirements.txt` (streamlit 1.66.1, numpy 2.2.6, pandas 2.2.3) + `requirements-ems_v2.txt`
(pyomo 6.10.1, highspy 1.15.1), contenedor Linux x86_64. Todas las ejecuciones con `PYTHONDONTWRITEBYTECODE=1`.

## 1. Comandos y resultados

| # | Comando | Resultado |
|---|---|---|
| 1 | Línea de base en `main` `3c65d98`: `python -m pytest tests/ -q -p no:cacheprovider` | **870 passed**, 7 warnings, 128 subtests (372 s) |
| 2 | Rama: `python -m pytest tests/ems_v2 -q -p no:cacheprovider` | **495 passed** (416 previos + 79 nuevos) |
| 3 | Rama sin Pyomo/HiGHS (`sys.modules['pyomo'] = sys.modules['highspy'] = None` antes de `pytest.main(['tests/ems_v2'])`) | **354 passed, 5 skipped** (los módulos MILP se saltan explícitamente) |
| 4 | Rama, regresión completa: `python -m pytest tests/ -q -p no:cacheprovider` | **949 passed**, 7 warnings, 128 subtests (381 s) = 870 + 79 |

Los 7 avisos son los mismos de la línea de base (SLSQP del V1.6, `clipping to bounds`).

## 2. Tests nuevos (79) — qué comprueban y qué NO

| Archivo | Tests | Comprueba | No valida |
|---|---|---|---|
| `test_ems_v2_ponte_3c0.py` | 62 | Inventario (UID, mezcla de microrredes, retirados, padres FV, valores ausentes/NaN/derivados/sintéticos), expansión por unidad, 5 clases de parámetros, valor sugerido bloqueado, conversión de unidades (% → 1, R$/MWh → R$/kWh, unidad incompatible/desconocida), coherencia escenario × microrred (otra microrred, incarnación, deriva, UID inexistente/retirado, condición ausente), horizonte de planeamiento reservado, previsión causal, realización sin emisión y cubriendo la misión, separación previsión × realización (oráculo), entrada independiente de la realización, proyección aceptada por `validar_entrada`, bloqueo por parámetro ausente y por sintético en `operacional`, políticas obligatorias, estado por unidad no inventado, indisponible ⇒ `a = 0`, plan solo de resultado aceptado y de la misma entrada, malla N/N+1 (consignas N, estados N+1, terminal como intervalo, binario), ejecución completa, retomada desde checkpoint serializado = ejecución continua, checkpoint adulterado/incoherente/desincronizado rechazado, ejecutor desincronizado detectado, interrupción sin recorte, memoria `tempo_no_estado_s` transportada, costo realizado × valor futuro (5 violaciones rechazadas), registro sellado/serializado/persistido inmutable/adulterado, serialización determinista de 7 contratos, cronómetro, percentiles, mapa de desenlaces, preflight (ensayo × operacional, referencias, restricciones, estados iniciales fuera de límites), núcleo solo biblioteca estándar | Física; desempeño; MPC |
| `test_ems_v2_ponte_seeds2.py` | 8 | Con microrredes REALES del catálogo (directorio temporal, fixtures de prueba): aislamiento entre dos inventarios distintos, conservación de UID/procedencia/huella/incarnación, sin agregación (V1.6 agrega `N_fc = 4`, la puente conserva 3 + 1 y 4 unidades identificables), valor sugerido bloqueado, CVU R$/MWh → R$/kWh, **lectura no graba** (bytes del banco, historial y catálogo idénticos), revisión fijada × actual y deriva, escenario real (SOC % → fracción, versiones), escenario de otra microrred rechazado, **microrred real bloqueada con explicación**, microrred excluida no se lee | Instalaciones reales (las microrredes son fixtures de prueba) |
| `test_ems_v2_ponte_milp.py` | 5 | HiGHS real: cadena preflight → 3A → `resolver` → plan → ejecución → registro (`aceito_otimo`, descarga analítica 10 kW, costo realizado = objetivo = R$ 0,025 con oráculo declarado), reproducibilidad (hash del plan y checkpoint final idénticos), error de predicción interrumpe y el costo cubre solo lo ejecutado, solución inviable no genera plan (`inviavel`), tiempos medidos registrados | Optimalidad de la planta; campaña de tiempos |
| `test_ems_v2_ponte_isolamento.py` | 4 | Solo `ponte_seeds2/leitor.py` importa `seeds2` y solo módulos de lectura; el lector no invoca APIs de escritura; la puente no importa UI/motor legado/solver; V1.6, aplicación, `seeds2`, requirements y núcleo 3A/3B-P sin diff desde `3c65d98` | — |

Test 3B-P modificado: `test_ems_v2_milp_perfil.py::test_so_o_subpacote_milp_importa_pyomo_ou_highspy` — excepción
nominal para `ponte_seeds2/leitor.py` respecto de `seeds2` (C-3C0-01); las demás aserciones intactas.

## 3. Evidencia sobre la microrred equivalente al V1.6 (fixture de prueba)

Lectura por `ler_inventario` + escenario recién creado; preflight `operacional` sin previsión:

- dispositivos: 2 `pv_usina`, 2 `pv_arranjo`, 2 `pemfc` (quantidade 3 y 1), 2 `bateria`;
- matriz: 16 `disponivel_verificavel`, 4 `derivavel`, 6 `opcional`, **26 `faltante_necessario`**;
- bloqueantes: 18 × `parametro_obrigatorio_ausente` (por banco: η_c, η_d, Pc_max, Pd_max, hipótesis de autodescarga;
  por bloque PEMFC: P_min, curva q(P)), `previsao_ausente`;
- advertencias: 12 × `necessario_3C1`, 2 × `disponibilidade_herdada_do_agrupador`, `realizacao_nao_fornecida`;
- brechas de previsiones del escenario: `previsoes_ausentes`, `demanda_sem_uid_e_criticidade`.

## 4. Limitaciones

- Ninguna prueba es validación física o experimental; el ejecutor es un dublê algébrico.
- Los tiempos de `test_tempos_medidos_sao_registrados_sem_meta_de_desempenho` (5 repeticiones) solo prueban el
  registro; no hay campaña ni meta.
- No se ejecutaron E2E de navegador: la aplicación no cambió (diff vacío verificado).
