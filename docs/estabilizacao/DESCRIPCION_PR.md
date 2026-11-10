Una transferencia fallida de una configuración nueva podía habilitar el console como manual con estado residual. Ahora la transferencia restaura su estado previo y bloquea la ejecución hasta un reintento correcto. El consentimiento de exclusiones pertenece a la identidad y revisión completas: añadir equipos excluidos exige nueva confirmación aunque la especificación efectiva del motor no cambie. Las rodadas manuales no se registran en la microrred activa.

También se corrigen el arranque sin permisos de escritura y la presentación de entradas térmicas inválidas; se amplía solamente la huella de procedencia del runner V1.6 para cubrir sus dependencias reales de preparación. Producción limitada a cuatro archivos. EMS V2, modelos, curvas, parámetros y fixtures históricos permanecen intactos; las guardias científicas continúan activas con excepciones de mantenimiento por archivo/hash exactos.

Validación sobre `main` consolidado `5e6267833538716678125ab962fc645cfee53eb0`:

- Referencia limpia: 2.004 passed, 7 warnings.
- Suite final: **2.044 passed, 0 failed, 0 skipped, 9 warnings** (544,27 s); 40 pruebas añadidas.
- EMS separado: **1.458 passed**; 98 archivos de `ems_v2/` idénticos a la base.
- Eólica histórica/ampliación/guardias: **251 passed**, incluidos seis equipos históricos y doce comparaciones exactas.
- Venv realmente separado sin Pyomo/HiGHS: **1.598 passed, 101 marcadores de skip**, todos de solver; 446 casos completos no ejecutados identificados individualmente.
- GA/GWO/NGO/SQP: series y resúmenes antes/después exactamente iguales.
- Chromium/Playwright real: seis bancadas, Gestor, escenarios, previsiones, ejecución, interrupción/reinicio, Archivo Científico y exportaciones; cero errores JavaScript registrados. P0/consentimiento: 24 comprobaciones; catálogo eólico: 103; documentos descargados: 157.
- `git diff --check` limpio. CI reproducible con/sin solver e historia completa; ejecución remota por confirmar.

Los siete informes de `docs/estabilizacao/` contienen inventario, matriz, causas reproducidas, regresión, recorridos, veredicto y omisiones individuales, con logs/XML/hashes/capturas. El listado completo del diff está en `ARCHIVOS_MODIFICADOS.md`.

Límites preservados: cuatro aerogeneradores pequeños solo para curvas; MIX funcional mediante su ruta legada, sin nuevo enlace; EMS V2 experimental sin integración operativa; backup convencional distinto del paquete científico; despliegue local/de confianza. No se inició 3D. Candidato listo para revisión técnica y auditoría matemática independiente; **no realizar merge automático**.
