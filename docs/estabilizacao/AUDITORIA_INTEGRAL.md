# Auditoría integral — inventario previo a correcciones

Base real verificada: `5e6267833538716678125ab962fc645cfee53eb0`. Rama exclusiva de estabilización. Esta matriz se creó ANTES de modificar producción. Ninguna fila se declara verificada en navegador por mera inspección de código.

| Componente | Ruta de acceso | Funcionalidad | Evidencia inicial | Estado inicial |
|---|---|---|---|---|
| Arranque | app.py → seeds2/ui/main.py | Streamlit + shell | Código inspeccionado; lanzamiento Chromium probado | Pendiente de aceptación operativa |
| Gestor | Gestor → Crear/Abrir/Trocar | Catálogo SQLite por instalación, store por UID | session.py; e2e_gestor_microrredes.js | Pendiente de aceptación operativa |
| Comisionamiento | Nueva microrred → etapas | Identificación, inventario, demanda, validación | e2e_piso1_microrrede.js | Pendiente de aceptación operativa |
| Gestión de equipos | Gestión → Inventario | Referencias, unidades, revisiones | equipment.py; suite refinamento | Pendiente de aceptación operativa |
| Centro de Operación | Abrir microrred comisionada | Escenarios operativos por microrred | e2e_piso2a_centro_operacao.js | Pendiente de aceptación operativa |
| Previsiones | Escenario → Previsiones | Demanda/clima, unidades/fusos/series | e2e_piso2b_previsoes.js | Pendiente de aceptación operativa |
| Ejecución de escenario | Escenario → Estrategia/Ejecución | Preflight, modelos + EMS V1.6, persistencia | e2e_piso2c_execucao.js | Pendiente de aceptación operativa |
| Simulación/Resultados | Microrred → Simulación/Resultados | Console V1.6 + procedencia | operations.py: riesgo P0 identificado; falta reproducción | Pendiente de aceptación operativa |
| Archivo Científico | Gestor → Archivo | Paquete científico y resultados inmutables | e2e_piso2da_arquivo.js | Pendiente de aceptación operativa |
| Informes | Rodada → Exportaciones | PDF/Excel/figuras y ZIP científico | e2e_piso2db_relatorios.js | Pendiente de aceptación operativa |
| Solar | Simulación → Modelos → Bancadas | Irradiancia / NOCT / SDM y comparación | app.py; tests/test_multimodel.py | Pendiente de aceptación operativa |
| Eólica | Bancada Eólica | 13 referencias; 9 simulables y 4 solo análisis | wind_app.py; tests/test_wind_catalog_expansion.py | Pendiente de aceptación operativa |
| Térmica | Bancada Térmica | Unidad local / central grande; restricciones explícitas | thermal_app.py; tests/test_thermal_model.py | Pendiente de aceptación operativa |
| Batería | Bancada Batería | Tremblay–Dessaint / 2RC | battery_app.py; tests/test_battery_h2.py | Pendiente de aceptación operativa |
| H2/PEMFC | Bancada H2 | Modelo temporal equivalente, consumo y exportación | h2_app.py; tests/test_battery_h2.py | Pendiente de aceptación operativa |
| MIX | Ruta legada energy_source=mix | Sincronización multifuent e y balance | mix_app.py; no accesible en navegación V1.6 normal (limitación documentada) | Pendiente de aceptación operativa |
| EMS operativo | Simulación → Optimizador | GA/GWO/NGO/SQP (SciPy) | orchestrator_app.py; ems_integration | Pendiente de aceptación operativa |
| EMS V2 3C-1..4 | API/tests experimentales | MILP/MPC/valor futuro; no integrado en UI | ems_v2 intacto; NO es defecto ni autoriza 3D | Pendiente de aceptación operativa |

## Problemas candidatos, aún sin corregir

- P0: `operations.prepare` habilita gate manual si falla `_apply`; la transferencia puede haber sido parcial. Reproducción controlada pendiente.
- Procedencia: revisar `_after_run_hook` cuando origen manual o identidad activa cambió.
- Huella científica: cubre modelos/datasets/config/runtime/EMS V1.6; revisar cobertura de transformación temporal y runner, sin incorporar EMS V2 que no participa.
- MIX legado y EMS V2 sin integración normal: limitaciones de alcance, no fallos por sí mismas.

Baseline global nuevo en ejecución; resultados y evidencia de navegador se registrarán después de ejecutarlos.

## Auditoría posterior y causas demostradas

El inventario inicial de arriba conserva su estado previo. La aceptación ejecutada y sus observaciones finales están en [MATRIZ_ACEPTACION.md](MATRIZ_ACEPTACION.md); el dictamen operativo en [VEREDICTO_FINAL.md](VEREDICTO_FINAL.md).

| ID / severidad | Reproducción y causa | Corrección mínima | Protección / evidencia |
|---|---|---|---|
| EST-01 / P0 | A válida; guardar B; `_apply` escribe parcialmente y falla. `mg_apply_error` participaba en la condición que habilitaba origen manual y gate `ok=True` | Snapshot/restauración solo del estado de transferencia; origen indisponible y gate cerrado; latch por identidad/revisión/huella; reintento explícito. No se borran resultados ni datos persistidos | Log de prueba fallida anterior; adversariales de error en carga/clima; reintento/rerender/edición manual/cambio/nueva sesión; Chromium sobre revisión B real: 14 comprobaciones |
| EST-02 / P1 | `_after_run_hook` registraba cualquier origen en el store activo; una ejecución manual o un cambio de microrred podía atribuir un resumen al origen incorrecto | Registrar únicamente origen microrred cuyo UID coincide con plan y microrred activa. Manual permanece en sesión; resultado de otra identidad no escribe en el store actual | Cuatro combinaciones adversariales; regresión de edición manual V1.6 intacta; sin cambios de contrato matemático |
| EST-03 / P2 | Seis mutaciones de preparación/adaptador no cambiaban la huella aunque esos módulos determinan entradas/series | Añadir dependencias reales a `SCIENCE_PATHS`, manteniendo V2 fuera del runtime V1.6 | Antes 6 fallos/4 aprobaciones; después 10 aprobaciones. CSV y resumen de cuatro algoritmos idénticos |
| EST-04 / P1 de disponibilidad en despliegue inválido | Directorio real sin escritura: `PermissionError` no capturado al iniciar el catálogo | Capturar errores de sistema/SQLite de apertura en el borde de UI y detener con mensaje claro | Chromium antes/después y AppTest para PermissionError/SQLite; no recuperación destructiva ni cambio de DB |
| EST-05 / P2 | Timestamp térmico inválido: ValueError conocido mostrado como traceback; la página continuaba hasta indicadores residuales de una ejecución previa | `st.error` y retorno inmediato para ValueError. Resultado previo conservado en sesión, identificado como última ejecución en sidebar | Prueba conserva DataFrame anterior exactamente y comprueba ausencia de métricas en el cuerpo de la simulación fallida; navegador vuelve a operar/exportar |
| EST-06 / P1 | Una nueva revisión añade otro equipo excluido, pero mantiene la misma especificación efectiva del motor. La confirmación previa se reutilizaba porque estaba ligada solo a esa especificación | Confirmación y clave del widget ligadas conjuntamente a UID, revisión, huella de configuración y especificación. Cada nueva revisión necesita confirmación propia | Reproducción fallida anterior, dos pruebas nuevas con inventarios reales y recorrido Chromium: dos nuevas exclusiones quedan bloqueadas hasta confirmación explícita |
| E2E-01 / herramienta | Consulta de Plotly antes de su montaje diferido; reset+autosize alterna márgenes redondeados | Esperas de viewport en guiones; comprobar datos/dominio tras primer reset y recorrer ambos modos conservando la aserción exacta original | Guiones finales 2B y 2D-A completos aprobados; ninguna modificación de curvas/tolerancias |

## Alcance del diff

Cuatro archivos de producción: `seeds2/ui/operations.py`, `seeds2/ui/main.py`, `seeds2/operation/runner.py` (solo lista de procedencia), `thermal_app.py` (solo presentación del error de entrada). No se modificaron ecuaciones, parámetros, catálogos, EMS V1.6 ni EMS experimental. El soporte nominal de guardias se amplió para reconocer únicamente esos archivos y las cinco adiciones de prueba/manifiesto; conserva los originales y rechaza alteraciones dentro de archivos permitidos.

Ninguna funcionalidad faltante se convirtió en defecto: MIX legado, cuatro pequeñas eólicas restringidas y V2 experimental conservan su alcance. No se inició el Piso 3D ni se rediseñó la aplicación.
