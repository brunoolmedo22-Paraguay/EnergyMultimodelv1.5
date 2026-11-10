# Regresión científica final

Base consolidada verificada y nuevamente consultada: **`5e6267833538716678125ab962fc645cfee53eb0`**. Rama `codex/estabilizacion-aceptacion-integral`; ninguna reescritura de historia, modificación de `main` ni merge de estabilización.

## Ejecuciones válidas

| Ejecución | Resultado | Duración | Evidencia |
|---|---|---|---|
| Referencia, clon limpio separado de la base | 2.004 passed, 0 failed, 0 skipped, 7 warnings | 517,67 s | `evidencias/logs/stab-clean-baseline-global.log.gz` |
| Suite global final | **2.044 passed, 0 failed, 0 skipped, 9 warnings** | 544,27 s | `evidencias/logs/stab-final-global.log.gz` y XML |
| EMS experimental separado | **1.458 passed, 0 failed, 0 skipped** | 173,35 s | `evidencias/logs/stab-final-ems.log` y XML |
| Eólica histórica + ampliación + guardias/adversariales | **251 passed** | 11,87 s | `evidencias/logs/stab-final-wind.log` |
| Correcciones, interfaz histórica, política nominal y guardia 3C-4 | **77 passed**, 2 warnings | 27,60 s | `evidencias/logs/stab-corrections-final.log.gz` |
| Entorno sin solver, venv separado | **1.598 passed, 101 skipped, 9 warnings** | 431,35 s | `evidencias/logs/stab-final-no-solver.log.gz`, XML y [omisiones individuales](OMISIONES_SIN_SOLVER.md) |
| Archivos científicos descargados por navegador | **157 comprobaciones** | Ver log | `evidencias/logs/stab-report-downloads.log` |
| Auditoría explícita contra base de esta misión | EMS íntegro; catálogo e históricos íntegros | — | `evidencias/logs/stab-explicit-ems-audit.log` |
| Espacios de diff | `git diff --check` sin errores | — | Se repite antes del commit |

Las 40 nuevas pruebas aumentan la cobertura: 22 de fallos/estado/UI, 10 de huella y 8 de alcance/adversariales. Ninguna prueba histórica ni fixture anterior fue eliminada o modificada. Las dos advertencias adicionales son de las nuevas pruebas térmicas adversariales: atributos auxiliares del DataFrame omitidos al mostrarlo y parseo de timestamps inválidos. Las otras siete advertencias SLSQP coinciden con la base; no se suprimen ni se modifican tolerancias.

Entorno: Linux, Python **3.12.14**, NumPy **2.2.6**, SciPy **1.15.3**, pandas **2.2.3**, Streamlit **1.66.1**, pytest **8.4.2**, Pyomo **6.10.1**, highspy **1.15.1**. Inventarios completos de paquetes en `evidencias/logs/stab-environment-*.txt`. `pypdfium2` se instaló únicamente como herramienta separada de inspección de PDF; versión y comando en el log de instalación. Los dos venv son distintos y la ausencia de Pyomo/highspy se verificó con `importlib.util.find_spec`.

Se descartan como evidencia final las ejecuciones intermedias iniciadas mientras se editaba el árbol o el nuevo manifiesto: una auditoría detectó correctamente la diferencia de hashes en memoria. La referencia válida usa un clon limpio y la suite final comenzó después de fijar las cuatro correcciones de producción y el manifiesto. No se reutilizan resultados de misiones anteriores.

## Integridad y auditorías activas

`evidencias/integridad.json` registra comparación byte a byte contra blobs de la base: **98 archivos EMS V2, 18 de models, 20 de config, 12 de simulation, 55 de h2_pemfc, 18 de ems_integration y 50 de reference_models**, todos idénticos; también registra sus hashes combinados y el OID del árbol EMS. Los datasets y curvas están incluidos. No existe diferencia de producción científica ni archivos EMS añadidos sin rastrear.

La suite EMS separada incluye 3C-1 (182 casos), 3C-2 (120), 3C-3 (256), 3C-4 (239), puente 3C-0, MILP, pruebas H1–H18, guardias, adulteraciones y auditorías numéricas. Los conteos por nombre pueden solaparse (p. ej. regresión 3C-2 dentro de 3C-3); el total sin doble conteo es 1.458. H18, los hotfixes B3C4-01/B3C4-10, C-01 y A03 permanecen cubiertos activamente.

La regresión eólica ejecuta las **9 pruebas originales**, **12 comparaciones exactas** (seis equipos × dos condiciones), las **110 pruebas de ampliación** (incluyen las doce comparaciones exactas) y las guardias de procedencia, variante, hashes y adversariales. No se cambió una curva ni un parámetro. Los cuatro equipos pequeños siguen fuera de simulación energética; su análisis conserva intercambio neto y auxiliares sin inventar generación.

Las tres guardias históricas y la guardia científica 3C-4 conservan íntegros sus archivos. Solo `wind_guard_policy.authorized_changes/authorized_additions` delegan una segunda filtración de mantenimiento. `stabilization_scope_v1.json` añade **cuatro archivos concretos** de aplicación, originales retenidos y hashes finales; no añade excepciones para EMS/modelos/datasets ni directorios. La transformación completa del helper eólico también se comprueba byte a byte. Las nuevas pruebas alteran copias de archivos admitidos, el manifiesto y el helper: las alteraciones se rechazan. No se regeneraron hashes ni evidencia histórica de la misión eólica.

Los tres guardias históricos y la política nominal funcionan sin historia Git antigua gracias a su evidencia sellada, comprobada en clones superficiales. **Los controles numéricos activos 3C-4 todavía necesitan los commits históricos**; el entorno final dispone de ellos y no hubo skips. CI usa `fetch-depth: 0`; no se presenta un checkout superficial como cobertura completa del 3C-4. La auditoría del diff de estabilización usa esta base consolidada, nunca `10365c5` para atribuir cambios finales del EMS.

## Comparación numérica independiente antes/después

Se ejecutaron cuatro escenarios reales de 12 min, 13 pasos, con idénticas entradas/semillas sobre el clon limpio y sobre la rama corregida. Se comparan todos los valores de despacho, SOC, costos, demanda, suministro/déficit, generación, hidrógeno y balances de sus CSV, además del resumen. Solo se excluyen identidades generadas y tiempo de ejecución; ninguna columna física fue excluida. Los archivos antes/después son **exactamente iguales**: `evidencias/numeros-before.json` y `numeros-after.json`, incluidos SHA-256 de series y valores numéricos completos.

| Algoritmo | Costo antes = después [R$] | Series y resumen |
|---|---|---|
| GA | 20.624746705690317 | Iguales exactamente |
| GWO | 20.62474938808517 | Iguales exactamente |
| NGO | 20.624746993826953 | Iguales exactamente |
| SQP | 20.624746663370345 | Iguales exactamente |

La equivalencia se refiere a estos casos ejecutados y a las referencias históricas de las suites; no es prueba universal para cualquier entrada. Las series completas de una rodada científica de 30 min se adjuntan fuera de Git en `SEEDS2_ESTABILIZACION_EVIDENCIAS.zip`, entrada `navegador/2db/estudo_exportado.seeds2study.zip` (SHA-256 en `artefactos-navegador.json`), verificadas mediante Archivo Científico y exportaciones. Diez CSV descargados se analizaron adicionalmente: series temporales crecientes sin duplicados e infinitos; columnas y campos nulos explícitos en `validacion-csv.json`.

La nueva huella V1.6 añade `seeds2/operation` y los adaptadores/configuración/referencias de microrred a los modelos, datasets, EMS V1.6 y runtime ya cubiertos. Es un cambio de procedencia, no de cálculo. El EMS experimental no se incluye: no determina esas ejecuciones.

## Reproducción

```bash
python -m pip install -r requirements.txt -r requirements-ems_v2.txt pytest==8.4.2
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ -q -rs
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ems_v2/ -q -rs
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_wind_model.py tests/test_wind_turbine_database.py tests/test_wind_catalog_expansion.py tests/ems_v2/test_wind_guard_policy.py tests/ems_v2/test_wind_3c4_integration.py -q -rs
python tests/ems_v2/wind_guard_policy.py --audit-mission-base 5e6267833538716678125ab962fc645cfee53eb0
python -m venv /tmp/seeds2-no-solver
/tmp/seeds2-no-solver/bin/pip install -r requirements.txt pytest==8.4.2
PYTHONDONTWRITEBYTECODE=1 /tmp/seeds2-no-solver/bin/python -m pytest tests/ -q -rs
# Dos fuentes distintas, mismo intérprete y dependencias:
python tools/e2e/capture_stabilization_numbers.py /ruta/clon-base /tmp/before.json
python tools/e2e/capture_stabilization_numbers.py /ruta/rama-corregida /tmp/after.json
cmp /tmp/before.json /tmp/after.json
git diff --check
```

El workflow `.github/workflows/regression.yml` ejecuta la suite completa en dos jobs independientes con/sin solver, guarda versiones, log y JUnit y obtiene historia completa. Su ejecución futura en GitHub Actions no se da por aprobada sin observarla.

La revisión final añadió EST-06: el consentimiento de exclusiones se liga a UID/revisión/configuración/especificación, en vez de solo a la especificación efectiva. Un inventario con nuevos equipos excluidos puede conservar la especificación del motor; se reprodujo el permiso residual antes de corregirlo. Dos nuevas pruebas y el recorrido de Chromium con dos revisiones sucesivas protegen ese caso. La suite completa se repite después de ese último ajuste.

Los informes de cobertura sin solver y CSV descargados pueden reconstruirse desde los XML/archivos originales:

```bash
python tools/e2e/check_stabilization_results.py GLOBAL.xml NO_SOLVER.xml tools/e2e/out/stabilization /tmp/informes
```

Las direcciones de objetos de Python incluidas por pytest en nombres de parámetros se normalizan solamente para emparejar identificadores de casos entre procesos; ningún valor científico se normaliza.
