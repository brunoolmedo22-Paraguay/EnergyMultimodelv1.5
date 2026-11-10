# PR #18 — integración definitiva con main 3C-4

## Alcance y sincronización

- Rama exclusiva: `codex/eolica-siete-curvas-potencias`.
- HEAD eólico remoto inicial: `8ec7f84ecf7cb3e6cb0a9ef1cd632d09b4d3ee46`.
- Main remoto verificado: `19aa3ac328f337e31ec4c36baa837c056299a57a`, PR #17 integrado.
- Incorporación mediante merge de main EN la rama eólica, sin rebase, sin force-push y sin merge del PR #18 en main. Se conservan los commits de referencia 10365c5, 5bc4283, 9621543 y 8ec7f84.

## Resolución de archivos compartidos

| Archivo | Resolución |
|---|---|
| `PARAMIJEFE.md` | Entrega científica completa de main, incluido 3C-4/A01/A02/B3C4-01/B3C4-10/A03, seguida del registro eólico completo. No selección global de una rama. |
| `docs/ai/HANDOFF.md` | Merge automático revisado: se conserva íntegro el HANDOFF científico de 3C-4 y el registro eólico; nota de integración actual al final. |
| `test_ems_v2_ponte_isolamento.py` | Constantes de main, incluida `ADICOES_3C4`, más el mecanismo C-EOL-01 de auditoría histórica y pins eólicos. |
| `test_ems_v2_3c2_isolamento.py` | Auditoría histórica C-EOL-01 con adiciones 3C-4 y la excepción B3C4-01 de `ponte/execucao.py`. Aislamiento/imports tardíos preservados. |
| `test_ems_v2_3c3_isolamento.py` | Constantes de main, incluida la excepción B3C4-01, referencias a `ADICOES_3C4` y auditoría histórica C-EOL-01. Aislamiento intacto. |

Git marcó conflictos de contenido en PARAMIJEFE y las tres guardias. HANDOFF se combinó automáticamente y se comprobó igualmente. Se verificó por inclusión textual que los documentos originales completos de main y el registro eólico completo permanecen presentes, no solo sus resúmenes.

## Garantías científicas ACTIVAS

La guardia propia de 3C-4 `test_ems_v2_3c4_isolamento.py` sigue comprobando el árbol real y conserva TODAS sus funciones científicas y constantes de main. Solo se filtran los nombres eólicos exactos ya autorizados antes de sus aserciones de alcance. No se convierte esa guardia en una comprobación exclusivamente histórica.

Continúan activas las verificaciones de proyección numérica controlada B3C4-01, normalización PCC B3C4-10, regla C-01, cierre A03, dependencias, imports tardíos y ausencia de integración de la aplicación. `assert_3c4_guards` verifica por AST todas las funciones y constantes originales contra la fuente revisada de main, salvo las dos inserciones de filtrado nominal en la función de alcance. Los nuevos adversariales detectan eliminar/debilitar cada comprobación científica o vaciar el conjunto de excepciones.

La evidencia adicional `tests/fixtures/wind_3c4_integration_v1.json` conserva el commit/árbol de main y la fuente original de su guardia, con SHA-256 fijo **662de6976b6ca7a6883442273d978bc6913b4547a34f9f0eb8ebd9b544439ce7**. No se alteran los hashes originales ni la evidencia sellada de C-EOL-01.

## Auditoría de producción y base correcta

El árbol `ems_v2/` combinado es idéntico a main `19aa3ac`, identificador Git **9a28ed95fc2c5be4267fb296ea0e8a4422b035ed**. Esta misión no añade, elimina ni modifica archivos de producción EMS frente a esa base.

Después del commit de integración, la auditoría explícita utiliza:

```bash
PYTHONDONTWRITEBYTECODE=1 python tests/ems_v2/wind_guard_policy.py \
  --audit-mission-base 19aa3ac328f337e31ec4c36baa837c056299a57a

git diff --exit-code 19aa3ac328f337e31ec4c36baa837c056299a57a -- ems_v2
```

La base `10365c5` se conserva únicamente para la evidencia histórica de la misión previa y para las restricciones científicas propias de 3C-4 que deliberadamente verifican sus hotfixes autorizados. NO se usa para exigir igualdad de todo el EMS final, pues eso incluiría los cambios legítimos del PR #17.

En un clon superficial, el verificador puede resolver el nuevo main mediante la prueba de objetos Git retenida. La prueba combinada comprueba que el nuevo árbol pasa contra 19aa3ac y que compararlo por igualdad con la base eólica antigua falla. No se oculta el cambio de base.

## Regresión conjunta NUEVA

| Comprobación | Resultado |
|---|---|
| Históricos eólicos originales | 9 passed |
| Seis históricos, dos perfiles, registros/potencias/KPIs exactos | 12 passed, 98 no seleccionados en ese comando; todos ejecutados en la global |
| Siete curvas y aceptación eólica | 110 passed |
| Guardias combinadas y adversariales | 153 passed |
| EMS 3C-1/3C-2/3C-3 | 545 passed |
| Toda la suite original y nueva 3C-4 | 228 passed |
| Suite global `tests/` | **2004 passed, 0 failed, 0 skipped, 7 warnings**, 501.77s (0:08:21) |
| Entorno real separado sin Pyomo ni HiGHS, `tests/ems_v2` | 994 passed, 101 skipped (solver ausente), 17,78 s |
| Eólica sin solver, históricos + siete curvas | 119 passed, 0 skipped, 2,98 s |

Las 101 omisiones del entorno sin solver coinciden con las documentadas por main 3C-4; no son omisiones por historia incompleta. Se verificó con `importlib.util.find_spec` que Pyomo y HiGHS realmente no están instalados en ese entorno, sin alterar el entorno con solver.

`git diff --check`: sin errores. Conflictos resueltos, `git ls-files -u` vacío. Identidad de producción EMS comprobada con el nuevo main y con su identificador de árbol Git. Todas las referencias históricas se conservan. Las siete advertencias son las conocidas de SciPy/SLSQP (clipping interno del paso), no cambios en las reglas físicas. Los resultados previos 1765/1758 pertenecen a fases anteriores y no se usan como prueba de la integración combinada.

## Limitaciones conservadas

No se cambian curvas, parámetros, reglas físicas ni disponibilidad de los equipos: tres incorporaciones simulables en dominio documentado y cuatro equipos pequeños de análisis con integración energética pendiente. No se inicia 3D ni se sustituye el EMS V1.6 operativo.

## Lista completa de archivos modificados respecto de main 19aa3ac

- `PARAMIJEFE.md`
- `config/wind_curves/.gitattributes`
- `config/wind_curves/BergeyExcel10_8.9kW_7.csv`
- `config/wind_curves/BergeyExcel15_15.6kW_9.6.csv`
- `config/wind_curves/Kestrele400nb_2.5kW_4.csv`
- `config/wind_curves/NREL_LICENSE.txt`
- `config/wind_curves/SWIFT_1kW_2.1.csv`
- `config/wind_curves/catalog_additions.json`
- `config/wind_curves/vergnet275.csv`
- `config/wind_curves/vestas47.csv`
- `config/wind_curves/vestas52.csv`
- `config/wind_turbine_database.py`
- `docs/ai/HANDOFF.md`
- `docs/eolica/AUDITORIA_C_EOL_01.md`
- `docs/eolica/FORMULACAO_POTENCIA_REFERENCIA_MAXIMA.md`
- `docs/eolica/GUARDIAS_REGRESION_EOLICA.md`
- `docs/eolica/INTEGRACAO_3C4_PR18.md`
- `docs/eolica/RASTREABILIDAD_7_EQUIPOS.md`
- `docs/eolica/RESULTADOS_REGRESION.md`
- `docs/eolica/RESULTADOS_VALIDACAO_CATALOGO.json`
- `docs/eolica/VALIDACION_7_EQUIPOS.md`
- `docs/eolica/evidencia/.gitattributes`
- `docs/eolica/evidencia/BergeyExcel10_8.9kW_7.yaml`
- `docs/eolica/evidencia/BergeyExcel15_15.6kW_9.6.yaml`
- `docs/eolica/evidencia/Kestrele400nb_2.5kW_4.yaml`
- `docs/eolica/evidencia/SEEDS2_CODEX_7_EOLICAS_INPUT.zip`
- `docs/eolica/evidencia/SWIFT_1kW_2.1.yaml`
- `models/wind_model.py`
- `seeds2/microgrid/config.py`
- `seeds2/microgrid/references.py`
- `seeds2/ui/equipment.py`
- `tests/ems_v2/test_ems_v2_3c2_isolamento.py`
- `tests/ems_v2/test_ems_v2_3c3_isolamento.py`
- `tests/ems_v2/test_ems_v2_3c4_isolamento.py`
- `tests/ems_v2/test_ems_v2_ponte_isolamento.py`
- `tests/ems_v2/test_wind_3c4_integration.py`
- `tests/ems_v2/test_wind_guard_policy.py`
- `tests/ems_v2/wind_guard_policy.py`
- `tests/fixtures/wind_3c4_integration_v1.json`
- `tests/fixtures/wind_guard_evidence_v1.json`
- `tests/fixtures/wind_guard_policy_v1.json`
- `tests/fixtures/wind_historical_v1.json`
- `tests/test_wind_catalog_expansion.py`
- `tests/test_wind_model.py`
- `tests/test_wind_turbine_database.py`
- `tools/validate_wind_catalog.py`
- `visualization/wind_plots.py`
- `wind_app.py`
