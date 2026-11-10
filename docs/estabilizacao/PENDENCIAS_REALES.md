# Pendencias reales y límites de aceptación

## Defectos nuevos

No quedan defectos operativos P0/P1 conocidos en el alcance ejecutado. Se corrigieron la transferencia fallida del console, la atribución de resultados manuales, el consentimiento de exclusiones por revisión, la cobertura de procedencia, el arranque sin escritura y la presentación de entradas térmicas inválidas. La ausencia de defectos detectados no sustituye una auditoría matemática ni certifica funcionamiento industrial.

## Limitaciones conocidas que se conservan

- **Cuatro turbinas pequeñas:** Bergey Excel 10/15, Kestrel e400nb y SWIFT están disponibles únicamente para análisis de curvas originales. Faltan condiciones documentales/políticas de integración para simular su energía y auxiliares. El navegador confirmó el rechazo de las cuatro; no se añadieron valores típicos, cut-out, densidad ni curvas.
- **Bancadas individuales:** resultados y controles temporales pertenecen a la sesión Streamlit. La recarga recupera la microrred mediante su URL, pero no constituye almacenamiento científico de la bancada. Exportar CSV antes de cerrar. Una selección eólica calculada sí se conserva al navegar entre páginas de la misma sesión.
- **Console V1.6:** persiste procedencia y resumen de rodadas vinculadas a microrred, no todas sus series. Los resultados manuales se conservan en la sesión sin registro en la microrred. Para persistencia científica completa se usa **Escenario → Ejecución → Archivo Científico**.
- **Backup convencional:** configuración, revisiones y blobs referenciados; no es un experimento científico completo. El paquete `.seeds2study.zip` sí transporta versiones, previsiones, rodadas y series del escenario. No intercambiar ambos mecanismos.
- **Integración temporal histórica:** una misión declarada de 30 min contiene 31 instantes integrados como 31 pasos de 60 s en el runtime V1.6. Se preserva y se declara en exportaciones; no se corrigió la convención numérica durante estabilización.
- **Huella científica:** cubre preparación, modelos, datos de equipos, datasets PEMFC y EMS V1.6. Se calcula una vez por proceso; exige código/datasets instalados inmutables y reinicio después de actualizarlos. No garantiza una mezcla de módulos modificados en caliente.
- **Despliegue:** instalación local o entorno de investigación con usuarios de confianza. El aislamiento por UID/SQLite no es autorización entre organizaciones. No se validó exposición pública, múltiples réplicas, sistemas de archivos de red ni control de hardware. No se creó autenticación.
- **Advertencias:** SciPy informa recortes internos de iteraciones SLSQP igual que en la referencia; Streamlit omite atributos auxiliares no serializables del DataFrame térmico en la presentación. No cambia las series exportadas.

## Implementado, todavía no integrado

- **MIX:** motor y bancada funcionales, sin enlace en el shell actual. Fue probado en Chromium mediante `tools/e2e/mix_acceptance_app.py`, que selecciona su ruta legada existente y ejecuta `app.py` sin alterar producción. No se declara acceso normal desde el Gestor.
- **EMS V2 hasta 3C-4:** núcleo experimental MILP/MPC y auditorías, íntegro y probado separadamente. No participa en el despacho del console ni del runner V1.6; su ausencia del selector operativo no es un defecto. No se inició 3D.

## Validaciones futuras ajenas a estabilización

Auditoría científico-matemática independiente; calibración contra medidas reales; certificación de curvas pequeñas y auxiliares; restricciones de operación física y seguridad industrial; despliegue multiusuario con autenticación; política de publicación de versiones de modelos; integración futura de MIX/V2 mediante misiones autorizadas.

La ejecución remota del workflow de CI y la creación del PR se deben confirmar en GitHub. Las pruebas locales del mismo entorno y comandos están documentadas; no se presume un resultado de Actions no observado.
