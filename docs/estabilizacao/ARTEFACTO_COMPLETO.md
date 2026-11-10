# Artefacto completo fuera de Git

Archivo del workspace compartido: `/workspace/SEEDS2_ESTABILIZACION_EVIDENCIAS.zip`.

- SHA-256: `c54b1afcbe63d2b2f41ce438144990a8603ca15317beab0267552ada996d8e3c`.
- Tamaño: 55226771 bytes; 369 entradas; CRC de todas las entradas verificado.
- Código de producción: `02d898d819e752c0ebd89c8564376eb200db33fd`; base `5e6267833538716678125ab962fc645cfee53eb0`.

Contiene todas las capturas/descargas originales de Chromium, incluyendo CSV, PDF, Excel, figuras y el estudio sintético portable `navegador/2db/estudo_exportado.seeds2study.zip`, más stdout/JUnit completos sin normalización y registros numéricos. Los ficheros FAIL/failure son intentos diagnósticos previos; los recibos finales aprobados determinan la aceptación.

No contiene datos de instalaciones reales ni bases SQLite. El artefacto generado de instalación ficticia se entrega fuera del repositorio; Git conserva informes, hashes, logs y capturas relevantes. Copiar el ZIP al workspace del auditor para contrastar los hashes de `evidencias/artefactos-navegador.json`. No es un backup de usuario ni autoriza importar un estudio como inventario real.

```bash
sha256sum SEEDS2_ESTABILIZACION_EVIDENCIAS.zip
unzip -t SEEDS2_ESTABILIZACION_EVIDENCIAS.zip
```
