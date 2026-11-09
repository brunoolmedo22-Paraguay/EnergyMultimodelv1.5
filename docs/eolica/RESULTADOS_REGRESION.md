# Resultados finales de regresión — misión eólica

## Integración real con 3C-4 — resultado vigente del PR #18

Main incorporado mediante merge en la rama eólica: `19aa3ac328f337e31ec4c36baa837c056299a57a`. Nueva ejecución global: **2004 passed, 0 failed, 0 skipped, 7 warnings**, 501.77s (0:08:21). No es el resultado 1765 de la etapa anterior.

- Históricos originales: **9 passed**; comparación exacta por separado: **12 passed, 98 no seleccionados**.
- Siete curvas: **110 passed**; guardias/adversariales combinados: **153 passed**.
- EMS 3C-1/2/3: **545 passed**; suite 3C-4 completa: **228 passed**.
- Entorno separado realmente sin Pyomo/HiGHS: EMS **994 passed, 101 skipped** por solver; eólica **119 passed, 0 skipped**. Sin omisiones nuevas por historia Git.
- `ems_v2/` idéntico a main integrado (árbol `9a28ed95fc2c5be4267fb296ea0e8a4422b035ed`); curvas, parámetros y reglas eólicas intactos. Auditoría combinada usa **19aa3ac**, conservando 10365c5 solo como evidencia histórica sellada.

Resolución de cada guardia, preservación documental y lista COMPLETA de archivos relativos al nuevo main: [INTEGRACAO_3C4_PR18.md](INTEGRACAO_3C4_PR18.md). Sin merge del PR #18 en main. Los resultados siguientes son registros de etapas anteriores.

## C-EOL-01 — resultado anterior a la integración real, PR #18

Suite completa repetida después de la corrección: **1765 passed, 0 failed, 0 skipped, 7 warnings**, **411,59 s (6:51)**. Lote focalizado: **135 passed**. Históricos por separado: **12 passed, 98 deselected**; la suite completa también ejecutó los no seleccionados.

Las guardias se ejecutaron sin omisiones en un clon real de profundidad 1 sin los objetos Git antiguos: **14 passed, 0 skipped**, antes y después de integrar una rama temporal 3C-4 con archivos nuevos y cambios en un módulo EMS existente. Los adversariales eólicos siguieron detectando modificaciones no autorizadas después de esa integración. La auditoría CLI de base/head de esta misión pasó, también en el clon superficial. Los tres deltas históricos retenidos se contrastaron con Git: 23, 50 y 51 archivos respectivamente.

C-EOL-01 elimina la comparación global permanente del EMS con una base antigua. Mantiene los hashes originales eólicos sin cambios, conserva evidencia verificable y separa una auditoría explícita del diff del PR. No se modificó producción EMS, curvas ni reglas físicas. Detalle: [AUDITORIA_C_EOL_01.md](AUDITORIA_C_EOL_01.md).

El PR fue creado externamente y es [#18](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/18). Esta corrección se entrega por su rama `codex/eolica-siete-curvas-potencias`, sin merge. Los resultados y bloqueos anteriores que siguen abajo son registros históricos, no el estado vigente de creación del PR.

Base real de `main`: `10365c5478b4dd137906b58819cd7f71d8de9cea` (PR #16). Rama exclusiva `codex/eolica-siete-curvas-potencias`. Sin merge ni push a main.

## Resultado final después de la autorización de tres guardias

`PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ -q -rs`: **1758 passed, 0 failed, 0 skipped, 7 warnings**, 415.84s (0:06:55). La suite completa incluye todos los 110 tests nuevos de ampliación eólica, los 114 nuevos adversariales de política y las regresiones anteriores. Advertencias SLSQP de SciPy sobre clipping durante el paso interno, presentes también en la base.

No se excluyó ningún test ni se actualizó un resultado esperado para ocultar diferencias. No cambió código EMS. Solo se insertaron ocho líneas en las tres guardias existentes autorizadas; el detalle, las listas nominales y los hashes originales están en [GUARDIAS_REGRESION_EOLICA.md](GUARDIAS_REGRESION_EOLICA.md).

## Comprobación histórica separada

- Antes de implementar la ampliación: pruebas eólicas existentes **9 passed**.
- Después del ajuste autorizado: las mismas pruebas **9 passed**, con todas sus aserciones físicas intactas, limitando solamente conteo/recorrido a los seis equipos originales.
- Selección independiente `pytest tests/test_wind_catalog_expansion.py -k e01 -q`: **12 passed, 98 deselected**. Seis equipos × dos perfiles. Los 98 no seleccionados se ejecutaron posteriormente en la suite completa.
- Cero diferencias de los seis registros completos (hash JSON canónico), tres columnas de potencia (SHA de bytes float64) y todos los KPIs. Perfiles: semana meteorológica de ejemplo, 1008 muestras; grade 0–30 m/s, 601 muestras. Dos turbinas y descuento del 3%. Densidad tabulada Nordex y corrección equivalente V1 conservadas.
- Fixture `tests/fixtures/wind_historical_v1.json` capturada ANTES de implementar en la base `10365c5`. Se conserva intacta, ahora además fijada por hash en el manifiesto de política. No se regeneró para acomodar la implementación.

## Otras ejecuciones útiles

- Nuevas pruebas eólicas: **110 passed**.
- Lote de ampliación + refinamiento SEEDS2 + smoke V1.6: **151 passed**.
- Tres guardias ajustadas, nuevos adversariales y cuarta guardia intacta: **128 passed** (114 nuevos + 14 anteriores).
- `python -m tools.validate_wind_catalog --output docs/eolica/RESULTADOS_VALIDACAO_CATALOGO.json`: exit 0, siete registros íntegros. No certifica las cuatro fuentes primarias pendientes.
- Los 21 archivos de SHA256_PAK_INPUT.txt coinciden con sus hashes originales. Los cuatro CSV NREL coinciden byte a byte con el commit remoto fijado y sus SHA de blob. Los siete CSV coinciden también con los objetos Git publicados, sin normalizar sus finales de línea.
- `git diff --check`: sin errores. Atributos Git locales preservan los bytes originales de CSV/YAML de evidencia.

## Diagnóstico previo y corrección autorizada

La primera suite de ampliación terminó con **1605 passed, 3 failed, 0 skipped, 7 warnings**, antes de la autorización adicional: los tres fallos eran guardias que prohibían cualquier edición eólica desde bases antiguas. No eran fallos numéricos del despacho. El usuario autorizó después el ajuste mínimo y nominal.

La primera ubicación del soporte nuevo, fuera de `tests/ems_v2/`, activó la guardia léxica `test_aplicacao_nao_referencia_ems_v2`; se interrumpió esa ejecución para diagnosticarla (**1 failed, 1215 passed** hasta la interrupción). Se reubicaron únicamente los archivos nuevos de soporte a la carpeta correcta. Esa cuarta guardia no fue modificada ni omitida. La suite completa final de arriba reemplaza ese intento interrumpido como resultado de aceptación.

## Garantías de alcance

`git diff 10365c5478b4dd137906b58819cd7f71d8de9cea -- ems_v2` sin diferencias. Igualmente sin diferencias en ciencia solar, batería, PEMFC, EMS V1.6, runtime y administración del Gestor. Los únicos archivos existentes modificados en la continuación autorizada son las tres guardias y documentación. No se inspecciona ni modifica la otra rama de Claude; la detección de cambios 3C-4 se prueba con centinelas en repositorios temporales.

Los nueve archivos eólicos ya existentes y los doce artefactos de datos/tests de la implementación previa están congelados por nombres exactos y SHA. Las tres guardias son iguales a sus originales salvo las inserciones textuales exactas admitidas. No se admiten directorios, comodines, borrados, renombrados, cambios de tipo o ediciones adicionales dentro de un archivo autorizado. El manifiesto también tiene un SHA literal; no contiene ningún mecanismo para actualizar sus propios hashes.

## Disponibilidad física y bloqueo externo del PR

Catálogo único con 13 entradas: seis históricos, tres nuevos simulables dentro del dominio documentado y cuatro pequeños disponibles para análisis fiel de curva, todavía NO para integración energética. En los cuatro quedan pendientes informes primarios/variantes/densidad y compatibilidad de importación auxiliar con el balance. Kestrel y SWIFT discrepan del filtro numérico a 11 m/s; no se alteraron puntos o referencias para aprobarlos.

La API GitHub continúa bloqueada: `gh pr create --draft --base main --head codex/eolica-siete-curvas-potencias` devuelve `Post "https://api.github.com/graphql": Forbidden`. **PR no creado**; no hay número/URL de PR verificable. Cuerpo listo en `/workspace/.local/state/energy/wind-pr.md`. La rama se publica por Git HTTPS; no se hizo merge. Hace falta acceso permitido a `api.github.com` para completar la creación. La herramienta de configuración de plataforma no pudo verificar el borrador. No se solicitan ni se publican secretos.

## Archivos de esta misión

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
- `docs/eolica/FORMULACAO_POTENCIA_REFERENCIA_MAXIMA.md`
- `docs/eolica/GUARDIAS_REGRESION_EOLICA.md`
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
- `tests/ems_v2/test_ems_v2_ponte_isolamento.py`
- `tests/ems_v2/test_wind_guard_policy.py`
- `tests/ems_v2/wind_guard_policy.py`
- `tests/fixtures/wind_guard_policy_v1.json`
- `tests/fixtures/wind_historical_v1.json`
- `tests/test_wind_catalog_expansion.py`
- `tests/test_wind_model.py`
- `tests/test_wind_turbine_database.py`
- `tools/validate_wind_catalog.py`
- `visualization/wind_plots.py`
- `wind_app.py`
