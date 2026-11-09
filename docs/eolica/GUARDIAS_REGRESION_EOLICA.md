# Ajuste autorizado de tres guardias históricas — misión eólica

El usuario autorizó expresamente ajustar exclusivamente las tres guardias afectadas, con excepciones mínimas por archivo, hashes originales verificables, protección íntegra del EMS y pruebas adversariales. Se mantienen todos los nombres y todas las aserciones originales. No se modifica código de `ems_v2/`, modelos solares, baterías, PEMFC, ni trabajo de otra rama.

## Tres archivos existentes modificados

| Guardia | Referencia SHA-256 original | Cambio puntual |
|---|---|---|
| `tests/ems_v2/test_ems_v2_ponte_isolamento.py` | `90e6f868ab77099666cab7d4892c615c2d47e3d0412cfb77efc8d9c6919ea7bc` | Filtrar solo estados M/A y nombres nominales validados antes de las aserciones existentes; aplicar el mismo filtro nominal a adiciones no rastreadas |
| `tests/ems_v2/test_ems_v2_3c2_isolamento.py` | `9ba068e886341432b10270392b3880ab230f0781d205214f1939c39c3e89161a` | Filtrar solo estados M/A y nombres nominales validados antes de las aserciones existentes |
| `tests/ems_v2/test_ems_v2_3c3_isolamento.py` | `078ab955a1a4ed642f644befac505ca3022b57edd26f1dc8a493a10a44d85296` | Filtrar solo estados M/A y nombres nominales validados antes de las aserciones existentes; aplicar el mismo filtro nominal a la unión de archivos nuevos |

Las líneas originales no se borraron ni se relajaron. La transformación permitida se reconstruye exactamente desde el texto del commit base, mediante `expected_guard_source`: import local, filtrado validado de `linhas` y, donde corresponde, filtrado de adiciones. Cualquier otro cambio en las propias guardias, incluso eliminar una aserción, se rechaza por igualdad exacta de bytes con esa transformación. La cuarta guardia `test_aplicacao_nao_referencia_ems_v2` sigue intacta; por eso el soporte nuevo reside en `tests/ems_v2/`.

## Excepciones nominales para archivos ya existentes

No hay comodines, exclusiones de carpetas ni permiso para borrar, renombrar o sustituir tipos de archivo. Cada excepción se aplica únicamente al estado **M**, con SHA-256 final de la implementación eólica publicada ANTES de esta autorización.

Base original fija: `10365c5478b4dd137906b58819cd7f71d8de9cea`. Implementación eólica previamente publicada: `5bc42834e03b6206e88d987f58dbc1b1eae7f5df`. Ambos commits permanecen en la historia de esta rama. No se utiliza el HEAD remoto como sustituto.

| Archivo | SHA-256 original | SHA-256 eólico fijado previamente | Motivo |
|---|---|---|---|
| `config/wind_turbine_database.py` | `f3a67f0037be2abb05e664e6585047f6443c0e45ef1384783363a437f2d8affb` | `a200c31db31ec60f8c224a9ed7400d44c93b4a28432829d4d338da0b58ec8915` | Catálogo único, contrato nuevo y validador relativo |
| `models/wind_model.py` | `069a6f8d4e21cd603725d92fcc77dd92ba77d82521dc21205c2efff5560baad7` | `cde9fe0bdd4bf765fe0dc47bafd40b1b8a0a7aa30fa1f41efd86b61938d59721` | Pico, dominio válido, densidad y contabilidad analítica de negativos |
| `seeds2/microgrid/config.py` | `7e7311f96ac4daeb80d7d2408de006a37f821e72c5bd2e5bf42dbe32435d46ed` | `6562196aeb6043a39ba39ebe06f56ecc5677468eed51a7da7f796760989b4693` | Bloquear simulación de referencias con integración pendiente |
| `seeds2/microgrid/references.py` | `deb5bce1fdbc4bbf83dfcf8f9b402c9f5e7fc37c932b40d6fc645a597a9d2e1c` | `196922de67be55b1d40703167551307e6d8fc05dbccab2c5a468d595d61cc615` | Exponer procedencia, referencia, pico y dominio eólicos |
| `seeds2/ui/equipment.py` | `0c9d11c78d438cc9867bc3c9fd16d38af16e06ed0e0546dbb73e25a693e28b5e` | `ec19b508d1260974f1f75781f2b5fc43bcbb0796193f828660220d85271cb2be` | Ficha y curva eólicas con unidades legibles |
| `tests/test_wind_model.py` | `669024c3f936f6e34afca126a0f4fc1831aedc948e80f94f97bde583784f3731` | `751ef13104eb935446a70d4a25e28ab2f885ddc0d5e54b1831d1d56b10be7fa5` | Recorrido limitado a los seis históricos, con autorización anterior |
| `tests/test_wind_turbine_database.py` | `51960181fb50da35eccfd76165e79abdc0d3c0786df19d8d7bdbc1d38fa99bc3` | `8b4232d1934717930ccc1feca638a40f5c09c004b09fdad533e90cce9b56a075` | Conteo de los seis históricos, con autorización anterior |
| `visualization/wind_plots.py` | `92dadf32d3c777161a70df8640fbceec1a838b75b4600e1f26804b46a2e04064` | `dbf14b459d161ee317eeb3abe211ed6cb19db6cf0c74329e27329bd6cefaa792` | Curvas pequeñas en kW |
| `wind_app.py` | `55e329503598faeb58afee1374000f1ed4d345e76b8327d2d22378882c85a1ec` | `309edc017971da7124da77361e537941e2a589501f6280d0e3a9cdee96424c7f` | Ficha, selección y análisis de curva eólica |

## Adiciones nominales

Los siguientes archivos nuevos son excepciones **solo para estado A**, con hashes congelados en el mismo manifiesto:

- `config/wind_curves/.gitattributes` — SHA-256 `3433d26e3d70db226b944862dd8382a1768d9749c5e095fba9abf8d126bd0d3f`.
- `config/wind_curves/BergeyExcel10_8.9kW_7.csv` — SHA-256 `794d45b30da9ae3745a46a37fda0e2256a8673262a8592f09805752932ad90b3`.
- `config/wind_curves/BergeyExcel15_15.6kW_9.6.csv` — SHA-256 `d5eb6ccf68ba9de4e30fd01dd5bb481c097eb141ca1c04d94d58707176d82cc5`.
- `config/wind_curves/Kestrele400nb_2.5kW_4.csv` — SHA-256 `4f6f8be33910a653e2ba115cd27865ce7a1b4ca9462da51bea1a522dc48fcfc5`.
- `config/wind_curves/NREL_LICENSE.txt` — SHA-256 `c855db7975f89527d2a8069aa0a8dcbfc7941a11928eb5a2f0ada395f15fe4d7`.
- `config/wind_curves/SWIFT_1kW_2.1.csv` — SHA-256 `d151168e38e2798f60bcc0689610c8fc5e43257361409df4bf5d8d03e2705d57`.
- `config/wind_curves/catalog_additions.json` — SHA-256 `7b93cb7552decd270859d4d0fa9fa0f98740378cdacc3361417ea59b39387f2b`.
- `config/wind_curves/vergnet275.csv` — SHA-256 `0b0a1665ade82a117fbaa496eaecb041f8643b01c50170116aa5f74a69b3cccc`.
- `config/wind_curves/vestas47.csv` — SHA-256 `3a7afbfe22b48409e3056f498973bc18217828e5face9c8826514e3760591171`.
- `config/wind_curves/vestas52.csv` — SHA-256 `5efdf48fdf02356ac8b1176437f83023d89ea7db5a78e43edbf9b584e11ca52f`.
- `tests/fixtures/wind_historical_v1.json` — SHA-256 `d148d917cc5dd31271deff689a34117abb8c79f15348299f0c3322b86f686e00`.
- `tests/test_wind_catalog_expansion.py` — SHA-256 `7ab1b71cf1b7328e404aeef49943cedf64e1a651effaaf30bb9b7d8548a4be2a`.

Son siete CSV originales, metadatos del catálogo, licencia/atributos de preservación de bytes y las dos evidencias de regresión ya publicadas. Se verifican los bytes completos; que un archivo aparezca en esta lista no permite alterarlo libremente.

Tres adiciones nuevas de soporte, también enumeradas por nombre completo:

- `tests/ems_v2/wind_guard_policy.py`: comprobaciones comunes de hashes, originales de guardias y protección global del EMS.
- `tests/ems_v2/test_wind_guard_policy.py`: pruebas adversariales; no toca archivos reales de producción.
- `tests/fixtures/wind_guard_policy_v1.json`: manifiesto estático de referencia, con SHA-256 literal fijado en el soporte.

No hay comando de actualización automática de hashes. Los valores se capturaron desde objetos Git de los dos commits explícitos, no desde el árbol mutable para convertir fallos en éxitos. Un manifiesto con un hash nuevo falla su comprobación. Futuros cambios científicos requieren revisión explícita; no regenerar estas referencias como paso de test.

## Protección del EMS y de los seis históricos

Además de las comprobaciones originales de cada piso, `assert_ems_unchanged` compara TODO el árbol `ems_v2/` con la base de esta misión, e inspecciona adiciones no rastreadas. No agrega ninguna excepción EMS: rechaza modificaciones, borrados, renombrados y archivos nuevos, incluso en una futura ruta 3C-4. Esta rama no contiene la implementación independiente 3C-4; los tests de ese caso usan repositorios temporales con centinelas, sin inspeccionar ni alterar la otra rama.

Los nueve archivos eólicos existentes y los doce artefactos añadidos de datos/tests ya publicados están congelados byte a byte. En particular, modificar parámetros históricos dentro de `config/wind_turbine_database.py` falla aunque ese nombre esté autorizado. Se comparan además los seis registros completos en memoria con los hashes originales de `wind_historical_v1.json`, que también está fijada por hash. Las 12 comprobaciones numéricas independientes de potencias y TODOS los KPIs se mantienen sin modificación.

## Validación ejecutada

- Lote de guardias y adversariales, incluida la cuarta guardia intacta: **128 passed** (114 tests nuevos y 14 anteriores).
- Históricos por separado: **12 passed, 98 deselected** en selección `-k e01`; las 98 pruebas no seleccionadas no se presentan como ejecutadas en ese comando.
- Pruebas eólicas originales, después del ajuste de alcance autorizado anteriormente: **9 passed**.
- Regresión completa final: resultado en `RESULTADOS_REGRESION.md`.

Los adversariales comprueban modificaciones dentro de cada archivo permitido, cada parámetro/curva histórica, familia de densidades Nordex, nombres hermanos no autorizados, estados D/R/T/A sobre excepciones M, manipulación del manifiesto, cambios adicionales en las tres guardias y symlinks. En repositorios Git temporales se prueban modificaciones/borrados y adiciones preparadas/no rastreadas en rutas de 3C-1, 3C-2, 3C-3 y 3C-4. Ninguna mutación se hace sobre el checkout productivo.
