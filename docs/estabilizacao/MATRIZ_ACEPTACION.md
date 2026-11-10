# Matriz de aceptación integral

Todos los estados indican evidencia ejecutada sobre la base consolidada y las correcciones. **B** = navegador Chromium real; **D** = dominio/persistencia/procesos mediante pytest; **I** = inspección de código/diff. B no se infiere de D/I. Los logs y capturas enlazados en [E2E_NAVEGADOR](E2E_NAVEGADOR.md) y los resultados de [REGRESION_CIENTIFICA](REGRESION_CIENTIFICA.md) permiten reconstruir cada constatación.

| Componente | Ruta de acceso | Funcionalidad / prueba | Evidencia | Estado / observaciones |
|---|---|---|---|---|
| Arranque limpio | `app.py` | Gestor vacío, HTML y controles, URL/recarga/reinicio | B piso1/gestor; B readonly | Aprobado; falta de escritura detiene claramente |
| Navegación | Gestor → microrred → secciones | Centro, Simulación, Gestión, Resultados, Archivo; volver/cambiar/URL/reload | B piso1, gestor, 2A–2D-B y seis bancadas | Aprobado; cero pageerror/console.error finales |
| Comisionamiento | ＋ Nova → cinco etapas | Identidad, ubicación, inventario, demanda, validación y activación | B piso1 41 + 21 + 4 comprobaciones | Aprobado |
| Gestión de equipos | Gestão → Inventário | Catálogos, cantidades, parámetros, salvar y revisión | B piso1/gestor; D refinamento y gestor | Aprobado; incompletos/excluidos declarados |
| Centro de Operación | Abrir instalación | Escenarios crear/duplicar/editar, estados y referencia al inventario | B 2A 43 + 5 + 5; D piso2a | Aprobado |
| Previsiones | Centro → Abrir Previsões | Importar/mapear unidades/fusos; demanda/clima; gráfico vs CSV, SHA, persistencia, corrupción rechazada | B 2B 45 + 8 + 7; B independiente 35 + 10; D piso2b | Aprobado; entrada no incorporada no reemplaza perfil guardado |
| Ejecución del escenario | Estrategia → Janela → Executar | Preflight, estado inicial, modelos físicos, EMS V1.6, resultados/huellas/series | B 2C 38 + 10 + 7; D piso2c | Aprobado; caso SOC incompatible bloqueado |
| Recuperación de proceso | Rodada activa → SIGKILL → reiniciar | Concluida preservada; activa interrumpida sin resultado ficticio | B 2C; D interrupción en subproceso | Aprobado |
| Console operativo | Simulação / Otimizador | Configuración guardada; procedencia; gate; resultados y exportación | B piso1 y fallo P0, D aplicación y nuevas adversariales | Aprobado; manual separado de microrred |
| Transferencia fallida | A aplicada → nueva revisión B | Fallo parcial bloquea; rollback; latch; navegación no reabre; reintento | B harness combinado P0/consentimiento 24; D 17 casos específicos de estado/procedencia | Aprobado |
| Consentimiento de exclusiones | Cambiar inventario manteniendo la misma especificación efectiva | Cada revisión/identidad exige confirmación propia; checkbox anterior no se hereda | B harness combinado 24; D dos nuevas adversariales con inventarios reales | Aprobado |
| Modificación manual intencional | Console → Modelos/Carga | Desvincular origen de la microrred; conservar historia | D nueva prueba + regresión original de modificación manual; I UI | Aprobado; no se atribuyen manuales a un store activo |
| A/B aisladas | Gestor → abrir/cambiar | UID, stores, inventarios, revisiones, blobs y resultados independientes | B gestor 39 + 6 + 2; D gestor/pisos2a–c | Aprobado |
| Conflictos y concurrencia | Dos stores/sesiones/procesos | Edición obsoleta, borrado concurrente, reimportación del mismo UID, recuperación sin borrar otra instalación | D test_seeds2_concorrencia con Event/Barrier y procesos reales; B gestor cambio/eliminación | Aprobado en pruebas; no se declara navegador para las intercalaciones de backend |
| Idempotencia | Runner / request_id repetido | No duplica rodada ni recálculo | D piso2c; B recarga de rodada | Aprobado |
| Backup convencional | Gestor/Gestão → ZIP | Configuración/revisiones/blobs; importar/copia/restaurar; consentimiento de sobrescritura | B piso1/gestor; D gestor/microgrid para corrupción/SHA/rollback | Aprobado dentro de su alcance; no contiene todo el experimento |
| Archivo Científico | Gestor/Centro → Archivo | Paquete íntegro, importación atómica, duplicata/corrupción/SHA, recuperar sin motor | B 2D-A 13 + 34 + 8 + 7; D piso2da | Aprobado; no crea una microrred al importar un estudio |
| PDF/Excel/figuras | Rodada → Exportaciones científicas | Datos locales/archivados/reinicio; diagnóstico sin resultados; SHA de figuras | B 2D-B 21 + 14 + 8 + 14; checker 157; D piso2db | Aprobado; Excel local y archivado igual exactamente |
| Solar | Centro → Ferramentas V1.6 → Abrir Solar | Irradiancia/NOCT/SDM, comparación, CSV; temperatura inválida | B 23; D suite solar | Aprobado; modelos intactos |
| Eólica histórica | Abrir Eólica | Simulación semanal, potencia/energía/unidades, CSV | B 22; D nueve originales + doce comparaciones exactas | Aprobado; seis equipos y resultados intactos |
| Catálogo eólico completo | Eólica → Catálogo/Simulação | Trece entradas, referencia vs pico, fuentes, nodos y selectores, tres nuevas ejecuciones | B catálogo 103; D ampliación 110 + guardias | Aprobado: nueve simulables, cuatro solo curvas |
| Dominio eólico | Catálogo/modelo | Cut-in/cut-out conocidos, dominio real/equivalente por densidad, auxiliares, pico, escala y pérdidas | D adversariales de ampliación; B cuatro rechazos energéticos y curvas | Aprobado en alcance; no se inventan datos faltantes |
| Térmica | Abrir Térmica | Central grande y unidad local; costos/restricciones; inválida rechazada | B central 21; D ambas modalidades y adaptador | Aprobado; integración de gran central conserva restricciones existentes |
| Batería | Abrir Bateria | Tremblay–Dessaint/2RC; SOC, corriente, dos CSV, entrada inválida | B 29; D modelos | Aprobado; ecuaciones intactas |
| H₂/PEMFC | Abrir H₂/PEMFC | Temporal, hidrógeno/potencia/gráficos, CSV e inválida | B 20; D modelo/datos | Aprobado; datos intactos |
| MIX legado | Harness que selecciona ruta existente | Cinco fuentes, timeline, balance, gráfico, CSV e incompleto rechazado | B 16; D mix_engine | Aprobado como bancada legada; sin enlace normal del shell |
| EMS V1.6 | Console / estrategia de escenario | GA/GWO/NGO/SQP; despacho, costo, SOC, energía e hidrógeno | Cuatro ejecuciones antes/después exactas; D integración | Aprobado en los casos ejecutados |
| EMS V2 experimental | API/tests | 3C-1/2/3/4, H1–H18, auditorías/guardias/adversariales | D 1.458; I 98 archivos byte a byte | Íntegro; no integrado al runtime operativo |
| Sin solver | Segundo venv real | Dependencias ausentes, omisiones exclusivamente de solver | D 1.598 passed / 101 marcadores; registro individual de 446 casos no ejecutados | Aprobado en alcance compatible; sin skips por historia Git |
| CI | `.github/workflows/regression.yml` | Dos jobs, versiones, suite global, artefactos, historia completa | I workflow + comandos ejecutados localmente | Configurado; ejecución remota pendiente de PR/Actions |
| Auditoría matemática | Futura misión independiente | Validación universal/formal/calibración | Fuera de esta estabilización | Pendiente expresamente; no es defecto operativo |

## Repetir catálogo y exportaciones

Con un servidor propio y una microrred ficticia comisionada, exportar JSON de `TURBINE_DB` con campos `key`, `slug` (clave alfanumérica con `_`), `points`, `new` (`schema_version == 2`), `analysis` (`integration_status == curve_analysis_only`) y ejecutar:

```bash
NODE_OPTIONS=--require=$PWD/tools/e2e/chromium_system.cjs \
 node tools/e2e/e2e_stabilization_wind.js http://localhost:8611 /tmp/eolica-e2e /tmp/catalogo.json
# Para el checker de PDF hace falta además pypdfium2 (ver versión instalada en evidencia):
python tools/e2e/check_piso2db_downloads.py tools/e2e/out/stabilization/2db /ruta/datos-origen/e2e_origem.json /ruta/motor-sabotado.log
```

La comparación de nodos del navegador contra el catálogo demuestra la fidelidad de la visualización; la comparación independiente del catálogo contra CSV/documentos pertenece a las 110 pruebas científicas y sus hashes. No se usa el propio catálogo como fuente independiente para certificar su física.
