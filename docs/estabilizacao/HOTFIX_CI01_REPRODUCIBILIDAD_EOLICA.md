# CI-01 — reproducibilidad numérica eólica

## Estado y alcance

Diagnóstico previo a la corrección. Rama del PR **#19**; HEAD auditado `267ed149f29d2e4fad7d30d49f8e1c463ebfb4fe`, base `5e6267833538716678125ab962fc645cfee53eb0`: verificados sin diferencias antes de modificar archivos. No se creó otro PR ni se hizo merge. Modelos, curvas, hashes/fixtures históricos y guardias no se han modificado.

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

**C — propuesta de comparación científica (todavía no aplicada):** conservar la evidencia SHA original, las entradas/curvas/parámetros/fuentes exactos y los KPI con igualdad estricta. Para weather, verificar cada potencia contra el oráculo independiente de 80 dígitos; límite propuesto **16 ULP** (máximo medido 10 ULP; margen explícito de 6). Límite relativo máximo de 16 ULP en números normales < 3.56e-15; a 14.000 kW equivale como máximo a 2.9103830456733704e-11 kW. El hash canónico se conserva y se comprueba siempre que la ejecución reproduce sus bytes; boundaries mantiene siempre su hash exacto. No se usa allclose ni una tolerancia absoluta en kW. Dtype, forma, finitud, signos de cero y KPI permanecen estrictos. Cualquier desviación superior falla; no se incrementa el límite automáticamente.

La propuesta requiere revisar la política y su protección nominal antes de adoptarla. Las guardias deben comprobar exactamente la transformación autorizada del test y la integridad de modelos/datasets/fixtures; las demás aserciones históricas deben conservarse. Adversariales previstos: ganancia alterada, un punto perturbado, redistribución que conserve energía global, cambio de dtype, NaN/inf, signos y modificación del presupuesto/oráculo. Ninguno se declara implementado o aprobado todavía.

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

El último comando reproduce deliberadamente seis fallos bajo la política original. No es una omisión ni un resultado aceptado. Las suites completas y los dos trabajos finales en verde siguen pendientes de la corrección justificada. **No se declara resuelto CI-01 por estos experimentos locales.**

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
