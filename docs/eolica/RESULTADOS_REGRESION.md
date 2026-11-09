# Resultados de regresión — misión eólica

Base real de `main`: `10365c5478b4dd137906b58819cd7f71d8de9cea` (PR #16). Rama exclusiva `codex/eolica-siete-curvas-potencias`. Sin merge ni push a main.

## Evidencia ejecutada

- Antes de cambios: `pytest tests/test_wind_model.py tests/test_wind_turbine_database.py -q`: **9 passed**.
- Después: las mismas pruebas **9 passed**, manteniendo todas las aserciones físicas. El usuario autorizó limitar exactamente dos pruebas al conjunto histórico (conteo y recorrido), sin alterar datos.
- `pytest tests/test_wind_catalog_expansion.py -q`: **110 passed**, incluyendo 12 comparaciones históricas exactas (seis equipos × dos perfiles), siete curvas punto por punto y siete AppTest del catálogo.
- `pytest tests/test_wind_catalog_expansion.py tests/test_seeds2_refinamento.py tests/test_app_smoke.py -q`: **151 passed** en el código final, incluidos todos los nuevos adversariales.
- Auditoría de catálogo: `python -m tools.validate_wind_catalog --output docs/eolica/RESULTADOS_VALIDACAO_CATALOGO.json`: exit 0, siete registros íntegros. NO certifica cuatro fuentes primarias pendientes.
- Los **21 archivos** listados en SHA256_PAK_INPUT.txt fueron contrastados con sus hashes originales. Los cuatro CSV NREL coinciden con el commit remoto fijado y sus SHA de blob.

## Comparación histórica

Cero diferencias de los seis registros completos (hash JSON canónico), tres columnas de potencia (SHA de bytes float64) y todos los KPIs. Perfiles: semana meteorológica real de ejemplo, 1008 muestras; grade 0–30 m/s, 601 muestras. Dos turbinas y descuento opcional del 3%, misma versión de dependencias. Densidad tabulada Nordex y corrección equivalente V1 conservadas. La fixture se capturó antes de implementar, no después.

## Suite completa ejecutada

`pytest tests/ -q -rs`: **1605 passed, 3 failed, 0 skipped, 7 warnings**, 410,49 s. Incluyó los primeros 74 tests nuevos; los 36 agregados posteriormente pasaron en la ejecución dedicada final de 110 y en el lote afectado de 151. Los únicos tres fallos fueron las guardias de alcance descritas abajo. No se presenta esta ejecución como totalmente aprobada.

## Contradicción de alcance de tres guardias anteriores

Tres tests de `tests/ems_v2` comparan el árbol completo de modelos/configuración/UI contra bases antiguas y prohíben CUALQUIER modificación eólica. Por construcción rechazan esta misión, aunque no cambie un byte del motor EMS. Se reprodujo con el subconjunto de guardias: **3 failed, 8 passed**. No son fallos numéricos de despacho.

- `test_ems_v2_ponte_isolamento.py::test_v16_e_aplicacao_sem_alteracao_desde_a_base_auditada`
- `test_ems_v2_3c2_isolamento.py::test_pisos_anteriores_v16_e_aplicacao_sem_alteracao_desde_o_merge_do_pr14`
- `test_ems_v2_3c3_isolamento.py::test_pisos_anteriores_v16_e_aplicacao_sem_alteracao_desde_o_merge_do_pr15`

Se solicitó autorización adicional para excepciones nominales y verificables. Hasta recibirla, las tres guardias permanecen intactas: no se las omite ni se falsea el resultado de la suite completa.

## Protección de alcance

`git diff origin/main -- ems_v2 ems_integration models/battery_model.py models/single_diode.py h2_pemfc config/pv_database.py orchestrator_runtime.py seeds2/microgrid/registry.py` sin diferencias. No se implementa Piso 3C-4 ni se toca la rama simultánea de Claude. El ajuste del Gestor es solo la disponibilidad de la referencia eólica para simulación, no su administración.

## Limitaciones de entrega

Los cuatro pequeños están presentes en el catálogo único con puntos y contabilidad de importaciones, pero integración energética pendiente. API GitHub y documentos primarios bloqueados por red (403); el intento de guardar los dominios requeridos en la configuración de plataforma no confirmó persistencia. Falta verificar informes primarios y crear PR si no se restablece API. No se fabrican URL de PR ni condiciones de ensayo.

## Publicación de la rama y bloqueo del PR

Implementación publicada en el commit `e992a9629cb87c04ad982eb9a510c88c40a8200f`; el commit siguiente solo completa este registro. El remoto confirmó el mismo SHA para `refs/heads/codex/eolica-siete-curvas-potencias`. `main` seguía en `10365c5478b4dd137906b58819cd7f71d8de9cea` en la comprobación final.

Se intentó `gh pr create --draft --base main --head codex/eolica-siete-curvas-potencias` con título y cuerpo completos. Resultado: `Post "https://api.github.com/graphql": Forbidden`. **PR NO creado**; no hay número/URL de PR que reportar. Texto listo en `/workspace/.local/state/energy/wind-pr.md`. No hubo merge. Se requiere acceso de red a `api.github.com` para reintentar la creación. La configuración de plataforma no confirmó persistencia del cambio solicitado.

Las tres guardias continúan intactas al no haberse recibido autorización adicional. No se describe la suite completa como aprobada.

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
- `tests/fixtures/wind_historical_v1.json`
- `tests/test_wind_catalog_expansion.py`
- `tests/test_wind_model.py`
- `tests/test_wind_turbine_database.py`
- `tools/validate_wind_catalog.py`
- `visualization/wind_plots.py`
- `wind_app.py`
