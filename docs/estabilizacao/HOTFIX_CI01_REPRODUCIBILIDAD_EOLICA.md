# CI-01 — reproducibilidad numérica eólica

## Estado y alcance

Diagnóstico y corrección CI-01, con aceptación remota pendiente. Rama del PR **#19**; HEAD auditado `267ed149f29d2e4fad7d30d49f8e1c463ebfb4fe`, base `5e6267833538716678125ab962fc645cfee53eb0`: verificados sin diferencias antes de modificar archivos. No se creó otro PR ni se hizo merge. Modelos, curvas y hashes/fixtures históricos no se han modificado. La revisión nominal del contrato de comparación y sus soportes se detalla al final; las tres guardias históricas y las aserciones científicas de 3C-4 permanecen intactas.

Run original: https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/actions/runs/42740857886. El responsable confirmó en logs oficiales: [true](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/actions/runs/42740857886/job/129581248716) **2044 passed / 0 failed / 0 skipped**; [false](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/actions/runs/42740857886/job/129581249679) **1592 passed / 6 failed / 101 skipped**, ambos 9 warnings y Python 3.12.16. Se consultaron sus páginas públicas; la descarga por API está bloqueada. Los seis SHA calculados del job fallido y sus environment.txt se solicitaron para cotejo exacto: **la atribución del incidente remoto permanece pendiente de ese cotejo o de los nuevos artefactos**.

## Experimento local controlado

Python 3.12.14; NumPy 2.2.6; SciPy 1.15.3; pandas 2.2.3. Venv con Pyomo 6.10.1/HiGHS 1.15.1 y venv separado donde ambos faltan. Las versiones completas, CPU, libc, configuración BLAS, tipo/forma/strides, fenv, selección de ufunc y SHA de datos/código/binario están en los metadata.json. No se atribuye la diferencia de Python 3.12.14/3.12.16 a una causa sin prueba.

1. Ejecutar las doce simulaciones históricas con un LP Pyomo/HiGHS real previo: **12 hashes y 12 KPI exactos**.
2. Ejecutar las doce en el venv sin solver, mismo CPU nativo: **12 hashes y 12 KPI exactos**, arrays completos iguales al venv con solver.
3. En proceso nuevo del venv sin solver, desactivar exclusivamente AVX512F/CD/SKX/CLX/CNL/ICL mediante NPY_DISABLE_CPU_FEATURES: **6 hashes weather distintos, 6 boundaries exactos y 12 diccionarios KPI exactos**. Se reprodujo también mediante pytest: seis fallos originales, sin xfail/skip ni cambios de aserciones.
4. Desactivar otras extensiones/libm o cambiar BLAS no se usa como corrección. El binario NumPy es idéntico entre procesos: `e6241082eaab01d0f68b2b661522ecb9d5d2160915104df8b112cc161dfa18b4`. La variable experimental cambia la selección del kernel, no el modelo, los datos, la fórmula ni el orden escrito de evaluación.
5. Se ejecutó el modelo del commit histórico 10365c5 con las mismas entradas: sus seis arrays weather coinciden exactamente con los del modelo vigente. Los datos/parametrización tienen sus hashes originales.
6. Cálculo independiente con Decimal a **80 dígitos**, sin np.exp/np.power/np.interp: máximo 10 ULP respecto de ambos perfiles. Es una comprobación de aritmética/formulación en este experimento, no calibración contra medidas reales.

La presencia/instalación del solver no cambia estas series en el CPU ensayado. El modelo eólico no importa Pyomo/HiGHS; el import del solver en el primer experimento es explícito y controlado. La física eólica no usa operaciones BLAS. Los experimentos distinguen paquete instalado de paquete importado/LP ejecutado.

## Localización de las diferencias

Las entradas normalizadas y el argumento del exponencial son idénticos. Cambian 64 valores de presión de saturación (máximo 7.105427357601002e-15 hPa), que producen dos densidades distintas (máximo 2.220446049250313e-16 kg/m³). Con densidad canónica fija, la ruta sin AVX-512 difiere en 16 velocidades equivalentes. Con viento/densidad/velocidad equivalente fijados, **las seis interpolaciones son exactamente iguales**: `stage-control.json`. El error se propaga desde exp/power seleccionados por CPU, no desde tablas diferentes ni una modificación del interpolador.

Todos los arrays de potencia son float64 nativo little-endian, forma (1008, 3), igual representación/strides; 3024 valores por equipo. No hay NaN, infinitos ni diferencias de ceros con signo. Primer valor distinto en todos: índice **(16, 0)** (fila y columna, base cero). Las columnas son potencia unitaria, bruta y neta, en kW.

| Modelo | Muestras distintas / 1008 | Valores distintos / 3024 | Máx. abs [kW] | Máx. relativo | RMSE [kW] | Máx. ULP | ΔE neta compensada [kWh] | KPI exactos |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Nordex N117/2400 | 2 | 6 | 9.0949470177292824e-13 | 2.4502635741725857e-16 | 2.7736748306453285e-14 | 2 | -2.2737367544323206e-13 | Sí |
| Vestas V164-7.0 MW | 17 | 51 | 5.4569682106375694e-12 | 8.0253411885053391e-16 | 3.9273598873332463e-13 | 6 | 5.0780120848988491e-12 | Sí |
| Siemens SWT-3.6-120 | 17 | 51 | 2.7284841053187847e-12 | 6.9194276673458784e-16 | 1.6625347189662421e-13 | 4 | 2.0084674664152163e-12 | Sí |
| Vestas V90-3.0 MW | 17 | 51 | 1.8189894035458565e-12 | 9.0098925217404663e-16 | 1.3817816525842575e-13 | 8 | 1.6484591469634324e-12 | Sí |
| EWT DW61-1MW | 17 | 51 | 4.5474735088646412e-13 | 3.4985832705488872e-16 | 3.6517126002287399e-14 | 2 | 3.6000831945178408e-13 | Sí |
| WEG AGW 147 / 4.2 | 17 | 51 | 3.637978807091713e-12 | 6.9032110637667493e-16 | 2.45591638698589e-13 | 4 | 2.2737367544323206e-12 | Sí |

La energía del KPI (reducción ordinaria de NumPy) coincide **exactamente** con el histórico. La columna ΔE utiliza fsum sobre las diferencias por muestra, revelando residuos menores que el redondeo de ese KPI. No se presentan esos residuos como cero: todas las diferencias de energía unitaria/bruta/neta, primeros índices y métricas están en comparison.json. Los NPZ conservan los arrays completos; no son fixtures sustitutos ni se usan para adaptar expectativas.

## Alternativas antes de corregir

**A — entorno:** fijar versiones no fija el ISA de ubuntu-latest. Desactivar AVX-512 fuerza la ruta portable pero no conserva los hashes históricos, como demuestra el experimento. Un runner con ISA/entorno garantizados podría mantener identidad binaria; este repositorio no configura tal runner. No se propone instalar solver en ambos jobs ni reintentar hasta obtener hardware favorable.

**B — modelo:** no se propone cambiar cálculo, orden de evaluación, exp, power, densidad ni interpolación de producción. Requeriría autorización previa.

**C — propuesta documentada antes de su aplicación (commit diagnóstico 4a8ca6e):** conservar la evidencia SHA original, las entradas/curvas/parámetros/fuentes exactos y los KPI con igualdad estricta. Para weather, verificar cada potencia contra el oráculo independiente de 80 dígitos; límite propuesto **16 ULP** (máximo medido 10 ULP; margen explícito de 6). Límite relativo máximo de 16 ULP en números normales < 3.56e-15; a 14.000 kW equivale como máximo a 2.9103830456733704e-11 kW. El hash canónico se conserva y se comprueba siempre que la ejecución reproduce sus bytes; boundaries mantiene siempre su hash exacto. No se usa allclose ni una tolerancia absoluta en kW. Dtype, forma, finitud, signos de cero y KPI permanecen estrictos. Cualquier desviación superior falla; no se incrementa el límite automáticamente.

La propuesta y la necesidad de protección nominal se publicaron antes de adoptar la corrección. Las guardias deben comprobar exactamente la transformación autorizada del test y la integridad de modelos/datasets/fixtures; las demás aserciones históricas deben conservarse. Adversariales previstos: ganancia alterada, un punto perturbado, redistribución que conserve energía global, cambio de dtype, NaN/inf, signos y modificación del presupuesto/oráculo. Su implementación posterior y resultados se detallan en la siguiente sección.

## Archivos de esta fase diagnóstica

- tools/ci/wind_numeric_probe.py: exportación NPZ/CSV completa, metadatos y comparación; no cambia aserciones.
- tools/ci/wind_decimal_reference.py: cálculo independiente de verificación, sin uso en producción ni en tests históricos.
- .github/workflows/regression.yml: capturar ambos perfiles en procesos separados antes de pytest; guardar todos los arrays y resumen. El entorno de pytest sigue siendo nativo e incluye sus pruebas originales.
- Este informe, evidencia diagnóstica y actualización del veredicto para indicar que CI-01 está abierto.

## Reproducción

```bash
python tools/ci/wind_numeric_probe.py --output /tmp/native
NPY_DISABLE_CPU_FEATURES=AVX512F,AVX512CD,AVX512_SKX,AVX512_CLX,AVX512_CNL,AVX512_ICL python tools/ci/wind_numeric_probe.py --output /tmp/no512
python tools/ci/wind_numeric_probe.py --compare /tmp/native /tmp/no512 --output /tmp/comparison
python tools/ci/wind_decimal_reference.py --captures /tmp/native /tmp/no512 --output /tmp/decimal
python -m pytest tests/test_wind_catalog_expansion.py -k e01 -q
NPY_DISABLE_CPU_FEATURES=AVX512F,AVX512CD,AVX512_SKX,AVX512_CLX,AVX512_CNL,AVX512_ICL python -m pytest tests/test_wind_catalog_expansion.py -k e01 -q
```

El último comando produjo seis fallos antes de corregir, en el HEAD auditado 267ed149. En la rama actual pasa las doce comparaciones. Para reproducir el fallo anterior debe usarse un worktree separado de ese HEAD, con el mismo venv y NPY_DISABLE_CPU_FEATURES; nunca cambiar los fixtures. No se utiliza aquella ejecución fallida como aprobación. Los resultados posteriores están al final de este informe.

## Cotejo de hashes calculados solicitado al responsable

Estos son resultados del experimento, no nuevos valores aceptados por los tests. El JSON histórico original permanece intacto.

| Modelo | SHA canónico = histórico | SHA sin AVX-512 reproducido |
|---|---|---|
| Nordex N117/2400 | `1b17667b24e49d67603f5fd44a7f15ec8ecd7763c179600930d2e38277bf112c` | `d27880cda883ee398af6650747a1b552e78006fe89c9963b5103bebf754820dc` |
| Vestas V164-7.0 MW | `293eb4dbd0122b10403639d1867a611a96715eeb7b6720666f230597a74032cb` | `fc065e601db0a4e9e5f5bd63b4dc6627ab2ee666a1c6c2b7cc5a2e97f5bfcef5` |
| Siemens SWT-3.6-120 | `82f80c5d524ca2d03f353423f93f7ab94ad0c3dafb456b3d7726f99e232d48ed` | `f798debde5fa692508485775d7ef858f6a76c091ccbf023819de2c8c73309510` |
| Vestas V90-3.0 MW | `24e0e30a3e05fea2308ca685b13492e0bd7a497b569ea13185864f67b3bbcd15` | `50fcac430c482ef85c17d3f75e3595ffc1328eab5fda3598f381a160db0a0d00` |
| EWT DW61-1MW | `90414326472837d83633082de98d6341865a9a8212e054319dfa6c8e225d2429` | `d153d50693ed4019c31a2e2b306fdda852ee8414417ea14b9f75eea41c2c50fb` |
| WEG AGW 147 / 4.2 | `77afbc31589dab19ca3c3924dbda9ee28ff25fe5ac56a8727aac9af1adaaf796` | `f1c4e7995bad051deaead5e35db4586ac97a1c9cc46b5cef6adc6c1583a6554f` |


## Corrección adoptada después del diagnóstico

Se aplica C exclusivamente al experimento histórico `weather`, sin cambiar una operación de producción. No se sustituye SHA por `allclose`: los seis hashes originales permanecen en el mismo JSON, cuyo SHA original también se comprueba. La ruta canónica sigue exigiendo esos bytes; `boundaries` conserva incondicionalmente sus seis SHA exactos. Cuando `weather` difiere, se exigen **simultáneamente**:

1. Código completo del modelo, catálogo, CSV meteorológico y fixture histórico con sus SHA originales inalterados; identidad exacta de cada registro histórico.
2. Forma (1008, 3), float64, finitud, potencia no negativa y representación exacta de ceros.
3. Recuperación de los arrays históricos originales desde la exportación diagnóstica: sus bytes deben autenticar el SHA del JSON **original**. Ese NPZ no puede definir ni actualizar expectativas; modificarlo provoca fallo.
4. Cada potencia a un máximo de **16 ULP tanto de los bytes históricos como del cálculo independiente Decimal a 80 dígitos**. Se observaron 8 ULP entre kernels y 10 ULP frente al cálculo independiente; se reserva un margen explícito de 8 y 6 ULP, respectivamente. Este presupuesto fijo para binary64 es inferior a 3.56e-15 relativo en números normales, muy por debajo de la precisión decimal publicada de las curvas. No implica cambiar la precisión física ni aceptar nuevos datos. Una plataforma que exceda el límite deberá investigarse: no se amplía automáticamente.
5. Un límite integrado calculado a partir de 16 veces el espaciado binary64 por muestra y el paso temporal exacto. La igualdad **estricta de todo el diccionario KPI original**, que incluye energía y factor de capacidad, permanece en su aserción original.

La integridad de entradas y código es exacta; solo la representación de resultados `weather` admite el presupuesto demostrado. No se atribuye capacidad física distinta a residuos del orden de 1e-12 kW. No hay cambios en `requirements*`, instalación de solver en el trabajo false, xfail, skip nuevo ni actualización de hashes anteriores.

### Guardias: transformación nominal, sin excepciones de directorio

`tests/test_wind_catalog_expansion.py` conserva **todos los bytes anteriores** salvo una aserción SHA sustituida por la llamada a la verificación anterior. La aserción de identidad del registro y la de KPI continúan byte a byte. El módulo original completo se retiene comprimido con SHA original `7ab1b71cf1b7328e404aeef49943cedf64e1a651effaaf30bb9b7d8548a4be2a`; su autenticación usa el valor ya presente en `wind_guard_policy_v1.json`, sin modificar ese manifiesto.

`tests/ems_v2/wind_guard_policy.py` delega **solo ese nombre de archivo** a la transformación exacta anterior. `stabilization_guard_policy.py` exige que el resto del soporte eólico continúe igual al original retenido, valida el SHA explícito del nuevo soporte CI-01 antes de importarlo y mantiene los cuatro pins de producción anteriores. El soporte CI-01 autentica el oráculo, comparador y tests adversariales mediante nuevos pins de esta revisión. No se actualizan los manifiestos históricos `wind_guard_policy_v1.json`, `wind_guard_evidence_v1.json`, `wind_3c4_integration_v1.json` ni `stabilization_scope_v1.json`.

Las únicas adiciones nominales filtradas son `tests/ems_v2/ci01_guard_policy.py`, `tests/ems_v2/test_ci01_wind_reproducibility.py`, `tools/ci/wind_historical_comparison.py` y `tools/ci/wind_decimal_reference.py`; solo estado A, nunca borrado/rename ni otro archivo. Los scripts bajo tools no estaban en el rango de aislamiento 3C-4, pero se nombran y autentican explícitamente. No se toca ninguna de las tres guardias originales, ninguna aserción numérica de 3C-4 ni archivo de producción del EMS.

### Pruebas adversariales implementadas

31 casos nuevos: aceptación de los seis experimentos canónicos y portables; alteración de un punto (1e-6 kW), ganancia (1e-10 relativo), redistribución que conserva energía, perturbación de 32 ULP, dtype, NaN, infinito, forma, signo/cero, hash sustituido y parámetros alterados; un ULP cambiado en boundaries; manipulación de los arrays retenidos; cambios en los cuatro archivos científicos protegidos; cambios adicionales dentro del test, evidencia original, presupuesto, oráculo y adversariales; conservación byte a byte de las demás aserciones; nombres/statuses nominales y modificación del propio soporte de guardia.

Validación enfocada: **291 passed** (14.11 s), ampliación + adversariales + guardias eólicas/estabilización + aislamiento 3C-4. Antes de la corrección, el proceso sin AVX-512 reprodujo seis fallos; con la nueva política, las doce comparaciones pasan. Suites completas con/sin solver, repetición de cuatro algoritmos y primeros dos trabajos remotos: aprobados; resultados al final. El cotejo numérico remoto ampliado se publica adicionalmente mediante anotaciones.

### Diagnóstico remoto publicado

[Run diagnóstico 42748936732](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/actions/runs/42748936732), commit `4a8ca6e235128bf687bec3bc67b54184ea1f22db`: ambos trabajos terminaron con failure en Run complete suite; este commit todavía exigía el hash original sin ruta portable. No se afirma el número o la causa concreta de sus fallos sin leer los logs. Los pasos de exportación terminaron y se produjeron dos artefactos:

- regression-solver-false, ID 13732494363, SHA-256 `1d18ea4ca89112df2b13f37d3dcbba4af2e56521da9f64b0cf556ab62e911f9a`.
- regression-solver-true, ID 13733117091, SHA-256 `0bb555f8fe300cc37f8deaf4797c22b03f874cff9ea293fff00b755eda6bd249`.

El cotejo remoto requiere los `ci01/native/metadata.json` y `arrays.npz` de ambos artefactos (o los seis SHA calculados y versiones de los jobs originales). Las páginas públicas permiten observar estados; los logs/descargas autenticados siguen inaccesibles en este entorno. No se convierte esa falta de evidencia en aprobación. El nuevo workflow también compara cada entorno contra el archivo histórico autenticado y escribe CPU, versiones y SHA en su resumen.


## Resultados posteriores comprobados

Código correctivo: `5c69543f0f06c024e28ba8cc90d9ec708d3fa609`. La revisión posterior `fef6596` solo publica recibos diagnósticos y conteos en anotaciones; no altera pruebas ni comparaciones.

| Comando / entorno local separado | Resultado | Duración |
|---|---|---:|
| energy/bin/python -m pytest tests/ -q -rs | **2075 passed / 0 failed / 0 skipped / 9 warnings** | 517.51 s |
| energy-no-solver/bin/python -m pytest tests/ -q -rs | **1629 passed / 0 failed / 101 skipped / 9 warnings** | 394.98 s |
| Eólica histórica + catálogo + ampliación + CI-01 + guardias | **290 passed** | 13.78 s |
| Ampliación + CI-01 + guardias + aislamiento 3C-4 | **291 passed** | 14.11 s |
| Doce comparaciones históricas / CPU nativo | **12 passed / 98 deselected** | 0.45 s |
| Doce comparaciones / sin solver / sin AVX-512 | **12 passed / 98 deselected** | 1.23 s |

Las nueve advertencias son las mismas de la suite anterior: dos sobre atributos ThermalConfig/parseo de fechas y siete sobre pasos SLSQP fuera de cotas; no se silencian. Actions avisa por separado la transición de Node/Ubuntu, sin cambiar el resultado de pytest. Logs y XML completos comprimidos, listas de paquetes, identidades de omisiones, comparación de algoritmos e integridad: `ci01_evidencia/post-fix/`, con SHA en su manifest. Los 101 marcadores omitidos tienen **exactamente las mismas identidades** que el XML anterior a CI-01: 59 casos con razón Pyomo/HiGHS, 27 con import pyomo ausente y 15 módulos omitidos en colección. Estos últimos corresponden a 360 casos; en total 446 casos solver de la suite completa no se ejecutan en el venv sin solver, igual que antes. No se presentan 101 marcadores como si fueran solo 101 casos.

GA/GWO/NGO/SQP: repetido `tools/e2e/capture_stabilization_numbers.py`, incluyendo despachos, balances, SOC, H₂, energía y costos; JSON **exactamente igual** al previo a estabilización y al anterior a CI-01, excluyendo únicamente los tiempos e identidades que ya excluía la comparación original. Costo: GA 20.624746705690317; GWO 20.62474938808517; NGO 20.624746993826953; SQP 20.624746663370345. No se cambió ninguna referencia.

EMS: **98 archivos intactos**, mismo objeto de árbol Git `9a28ed95fc2c5be4267fb296ea0e8a4422b035ed` que main `5e626783`. El diff CI-01 en modelos, catálogos, EMS V1.6/V2, h2_pemfc, simulation, reference_models, requirements y fixtures históricos está vacío. Auditoría explícita `wind_guard_policy.py --audit-mission-base 5e6267833538716678125ab962fc645cfee53eb0`: aprobada, sin historia omitida. `git diff --check`: aprobado.

### Primera aceptación remota del código correctivo

Run [42751027096](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/actions/runs/42751027096), HEAD correctivo `5c69543`: estado global **Success**, dos jobs completados. Comprobado en páginas públicas, no inferido de pruebas locales:

- [scientific-regression (true), 129614414822](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/actions/runs/42751027096/job/129614414822): **success**.
- [scientific-regression (false), 129614414476](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/actions/runs/42751027096/job/129614414476): **success**.

La descarga autenticada de logs permanece bloqueada por la política efectiva de red de este proceso (`api.github.com` no figura permitido); no se inventan conteos remotos. Para cerrar el cotejo de CPU/versiones/SHA/métricas se publica un recibo JSON de los doce casos y los conteos XML en las anotaciones públicas del siguiente run, además de conservar todos los arrays en los artefactos. Se publican datos científicos sintéticos, paquetes/CPU y controles numéricos en lista explícita: NPY_DISABLE_CPU_FEATURES y cinco opciones de BLAS/threads; no credenciales ni variables ajenas a ese propósito.

### Archivos modificados por la corrección

- Comparación histórica: `tests/test_wind_catalog_expansion.py`, único hunk de una aserción.
- Soportes nominales de integridad: `tests/ems_v2/wind_guard_policy.py`, `stabilization_guard_policy.py`, `ci01_guard_policy.py`.
- Comparador y oráculo independientes: `tools/ci/wind_historical_comparison.py`, `wind_decimal_reference.py`.
- 31 adversariales independientes: `tests/ems_v2/test_ci01_wind_reproducibility.py`.
- Diagnóstico/CI: `tools/ci/wind_numeric_probe.py`, `.github/workflows/regression.yml`.
- Informes, continuidad y evidencia sintética: este documento, VEREDICTO_FINAL, PARAMIJEFE, HANDOFF y `ci01_evidencia/`.

No hay diff de producción en CI-01. La política de equivalencia conserva integridad exacta de la ciencia y evidencia histórica más comparación numérica estricta y adversarial. La auditoría matemática independiente y la aprobación de integración siguen correspondiendo al responsable. **Sin merge y sin 3D.**


### Comandos de regresión local reproducibles

Los paquetes de ambos venv están listados en `post-fix/environment-*.txt`; Python local 3.12.14. En un checkout con historia completa:

```bash
python3.12 -m venv /tmp/seeds2-ci01-with
/tmp/seeds2-ci01-with/bin/python -m pip install -r requirements.txt -r requirements-ems_v2.txt pytest==8.4.2
/tmp/seeds2-ci01-with/bin/python -m pytest tests/ -q -rs
python3.12 -m venv /tmp/seeds2-ci01-without
/tmp/seeds2-ci01-without/bin/python -m pip install -r requirements.txt pytest==8.4.2
/tmp/seeds2-ci01-without/bin/python -c "import importlib.util; assert importlib.util.find_spec('pyomo') is None; assert importlib.util.find_spec('highspy') is None"
/tmp/seeds2-ci01-without/bin/python -m pytest tests/ -q -rs
NPY_DISABLE_CPU_FEATURES=AVX512F,AVX512CD,AVX512_SKX,AVX512_CLX,AVX512_CNL,AVX512_ICL /tmp/seeds2-ci01-without/bin/python -m pytest tests/test_wind_catalog_expansion.py -k e01 -q
/tmp/seeds2-ci01-with/bin/python tests/ems_v2/wind_guard_policy.py --audit-mission-base 5e6267833538716678125ab962fc645cfee53eb0
git diff --check
```

El control de AVX-512 es un proceso de prueba adicional: no cambia el entorno de los jobs de pytest ni se usa para saltar casos. La comparación Decimal independiente y las exportaciones completas se reproducen con los comandos anteriores del diagnóstico.


## Cierre verificado — prioridad de entrega

Código final validado: **79cb4540f89020f3b03537578ffeef546c2ead2a**. El commit de cierre solo incorpora documentación y evidencia; no modifica ciencia, comparación, guardias, pruebas ni workflow respecto de ese código. No se repite manualmente la suite completa por cambios documentales.

Requisitos cumplidos: diagnóstico controlado y cuantificación de los seis modelos; doce comparaciones históricas; ampliación completa; 31 adversariales; ambas suites completas locales; 101 omisiones con las mismas identidades; GA/GWO/NGO/SQP exactos; 98 archivos EMS intactos; diff científico vacío; diff --check; publicación en el mismo PR y dos trabajos remotos en success. No hay bloqueo científico conocido en CI-01.

### Entornos remotos y comparación completa

Run [42812301019](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/actions/runs/42812301019):

| Trabajo | Resultado publicado en anotaciones | Tiempo pytest |
|---|---|---:|
| [true, 129816511858](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/actions/runs/42812301019/job/129816511858) | **2075 passed / 0 failed / 0 skipped**, success | 719.494 s |
| [false, 129816512409](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/actions/runs/42812301019/job/129816512409) | **1629 passed / 0 failed / 101 skipped**, success | 561.581 s |

Ambos: Python **3.12.16**, NumPy **2.2.6**, SciPy **1.15.3**, pandas **2.2.3**, glibc **2.43**, AMD EPYC **7763**, AVX512F **false**. NPY_DISABLE_CPU_FEATURES y los cinco controles BLAS/threads registrados: **None**; redondeo fenv **0**. NumPy binario SHA `e6241082eaab01d0f68b2b661522ecb9d5d2160915104df8b112cc161dfa18b4`, igual al local. Exp usa AVX2 y power baseline. True tiene Pyomo 6.10.1/HiGHS 1.15.1 y ejecutó un LP previo; false no tiene ambos. Las fuentes científicas coinciden exactamente en ambos jobs.

**Los doce arrays remotos son idénticos entre entornos con/sin solver.** Sus seis SHA weather coinciden exactamente con los seis reproducidos localmente sin AVX-512; boundaries conserva sus SHA originales y todos los KPI siguen exactos. Por tanto, la diferencia sigue la ruta numérica de CPU, no la instalación del solver. El run anterior 42810749071 registró rutas AVX512_SKX y AVX2/baseline en trabajos distintos; el nombre nominal de CPU no bastaba para fijar las capacidades efectivas. En el nuevo recibo se registran todas las banderas, sin inferirlas del nombre.

| Modelo | Máx. ULP remoto vs histórico, true / false | Valores distintos entre jobs | Máx. abs / RMSE / ΔE entre jobs | KPI históricos |
|---|---:|---:|---|---|
| Nordex N117/2400 | 2 / 2 | 0 | 0 / 0 / 0 | Exactos |
| Vestas V164-7.0 MW | 6 / 6 | 0 | 0 / 0 / 0 | Exactos |
| Siemens SWT-3.6-120 | 4 / 4 | 0 | 0 / 0 / 0 | Exactos |
| Vestas V90-3.0 MW | 8 / 8 | 0 | 0 / 0 / 0 | Exactos |
| EWT DW61-1MW | 2 / 2 | 0 | 0 / 0 / 0 | Exactos |
| WEG AGW 147 / 4.2 | 4 / 4 | 0 | 0 / 0 / 0 | Exactos |

Las diferencias **respecto del histórico** son exactamente las de la tabla de seis modelos del experimento local: primeros índices, muestras, RMSE y ΔE compensada incluidos. No se confunde diferencia cero **entre jobs con la misma ruta** con diferencia cero respecto de la referencia AVX-512. Cada recibo publica las magnitudes, SHA, dtype, finitud, ceros y KPI; el contraste Decimal independiente se conserva por equipo.

Los arrays completos remotos se exportaron a los dos artefactos. Sin acceso autenticado a su descarga, los bytes se identificaron en las exportaciones locales por sus SHA remotos exactos, para comparar las 3024 potencias de cada equipo. Los NPZ `*-sha-identified-arrays.npz` son esa reconstrucción autenticada, **no descargas** ni nuevos fixtures. Recibos completos, identificación, comparación entre jobs y contra Decimal: `ci01_evidencia/post-fix/remote/`. El script efectivamente usado queda comprimido como evidencia documental; ninguna referencia histórica se regenera. La falta de los logs raw originales 42740857886 se declara: sus conteos proceden del responsable; la comprobación numérica remota nueva es directa y verificable en las anotaciones de 42812301019.

### Pendientes y riesgos

- Ningún defecto científico o fallo de regresión conocido queda abierto en CI-01.
- El commit documental final puede disparar automáticamente otro workflow; no se presenta como ejecutado antes de que termine. El código de producción, tests y CI es idéntico al HEAD validado 79cb454. No se solicita otra ejecución manual.
- Un futuro kernel que supere 16 ULP o altere un KPI exacto seguirá fallando y requerirá diagnóstico; no se ajustará el límite automáticamente.
- La aprobación técnica y la auditoría independiente corresponden al responsable. No se hizo merge ni se inició 3D.

Lista completa de archivos del hotfix, respecto del HEAD auditado 267ed149: `ci01_evidencia/post-fix/CI01_FILES.txt`. Predominan evidencia y documentación; el diff de producción CI-01 es cero. **Dictamen: regresión histórica protegida; hotfix listo para revisión técnica.**
