# Plantillas del paquete

El archivo `MATRIZ_INVESTIGACION_SEEDS2.xlsx` es un **esqueleto** para que Work normalice la investigación en cinco hojas:
- `Referencias`: un trabajo por fila (DOI único), con P0..P4 y nivel F/A/M/X.
- `Mapa_codigo`: una implementación/equación por fila, ruta/líneas/commit y respaldo.
- `Claims_articulo`: una afirmación propuesta por fila, grado de soporte y sección.
- `Busquedas`: consultas, fuentes, fechas, resultados y obstáculos.
- `Lacunas`: vacíos de evidencia, contradicciones o peligros de sobreafirmar.
- `Resumen`: convenciones, metas y definiciones; SIN cifras inventadas.

Los encabezados son guía; se pueden agregar más columnas, pero las claves `REF0001`, `MOD0001`, `CLM0001` y `BUS0001` deben ser estables y permitir relaciones entre tablas. Nunca cargar citas falsas para completar un objetivo.

El archivo `referencias.bib` es deliberadamente vacío: Work lo poblará exclusivamente con bibliografía real verificada.
