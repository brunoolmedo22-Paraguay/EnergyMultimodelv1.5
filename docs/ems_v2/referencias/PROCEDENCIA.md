# Procedencia de los documentos de referencia del EMS MILP–MPC (Piso 3A)

Copias **byte a byte** de documentos del paquete maestro entregado por el responsable el 2026-11-08
(`SEEDS2_Piso3_Paquete_Maestro_Claude_3A_2026-11-08-2.zip`). Se versionan para que la trazabilidad
ecuación → símbolo → código → test tenga una fuente dentro del repositorio. **No** se copian los PDF, la
bibliografía ni los antecedentes (decisión 2 aprobada en la fiscalización del plan 3A).

Estos documentos son **especificación y propuesta científica**, no evidencia de implementación ni de validación.
Jerarquía (paquete, `00_EMPEZAR_AQUI.md`): código real de `main` > decisiones del contrato 3A > adenda v1.1 >
especificación v1.0 de Work > antecedentes. La adenda v1.1 prevalece sobre la v1.0 en B01–B05.

| Archivo | SHA-256 | Origen en el paquete | Hash verificado contra |
|---|---|---|---|
| `02_Especificacion_matematica.md` | `bd60029b26d7c5544796ec62c0a15bf2a50b255a6108e9bb3ac95a1af0da8745` | `REFERENCIAS/SEEDS2_PAQUETE_COMPLETO_PARA_GPT.zip` → `01_DOSSIER/02_Especificacion_matematica.md` (v1.0, 2026-11-07) | `01_DOSSIER/09_SHA256.json` y `05_MANIFIESTO_DEL_PAQUETE.json` del ZIP de referencia |
| `01_ADDENDA_MATEMATICA_v1.1.md` | `36fbbb69fa0aada845b56566ca4c3a819ee64eac8467326cb7a0a9b88815ca8a` | raíz del paquete maestro | `99_MANIFIESTO_SHA256.json` del paquete maestro |
| `06_CATALOGO_SIMBOLOS_v1.1.csv` | `850a1c2c4a4b93e7cdc2d8b9976f0f11d488641822cc993ca50aad2ec5c07d6a` | raíz del paquete maestro (catálogo **semilla**) | `99_MANIFIESTO_SHA256.json` |
| `05_FIXTURES_Y_PUERTAS.md` | `30ae40ba60c46f8e55eca01fba539c22679527a5f15ed803b8da3c1c4a0a47c2` | raíz del paquete maestro | `99_MANIFIESTO_SHA256.json` |

Base de código contrastada por el paquete: `8556b71a76dd13d279a0e0ecd8ad9bd498df72f1` (= `main` al iniciar el Piso 3A).

`tests/ems_v2/test_catalogo_cobertura.py` verifica estos hashes y extrae automáticamente las etiquetas `\tag{…}` de
la especificación v1.0 y de la adenda v1.1 para comprobar que el manifiesto de ecuaciones las cubre. La relación
ecuación → símbolos es un **manifiesto revisado manualmente** (`ems_v2/catalogo/equacoes.json`); no existe un
analizador exhaustivo de LaTeX.

No editar estos archivos: una corrección científica se registra como nueva adenda con nuevo hash.
