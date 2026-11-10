# Aceptación en navegador real

Se ejecutó Streamlit real con Playwright **1.62.1** / Chromium **156.0.8078.79**, en Linux, con un `SEEDS2_DATA_DIR` temporal por protocolo. No se usó AppTest como sustituto de estos recorridos. Los dos harnesses se identifican expresamente abajo. Escritorio: 1440×900/1000; tablet: 820×1180 y 1180×820. También se recorrieron temas claro/oscuro en los protocolos existentes. Los contextos originales usan DPR 2 y las bancadas DPR 1.

## Recorridos ejecutados

| Protocolo | Operaciones reales | Resultado y evidencia |
|---|---|---|
| Piso 1 | Inicio vacío, geolocalización concedida/denegada/no disponible, cinco etapas, inventario, curvas, demanda, activación, EMS, backup/restauración | comissionar, reabrir después de reinicio y tablet aprobados; `evidencias/logs/navegador/piso1/` |
| Gestor | Crear A/B, inventarios separados, cambio de microrred, ZIP/PDF, copia/importación, rechazo de operaciones ambiguas y eliminación | multi, reinicio, tablet aprobados; `.../gestor/` |
| Centro | Escenarios, estados iniciales, versiones, vínculo al inventario, navegación y URL | operar, reinicio, tablet aprobados; `.../2a/` |
| Previsiones | CSV malformado bloqueado; demanda y cuatro magnitudes climáticas; mapeo/unidades/fusos; datos del gráfico iguales al CSV; zoom/reset; guardar y SHA | operar, reinicio, tablet aprobados; `.../2b/` |
| Previsiones independiente | Importar demanda/clima, guardar v2, verificar SHA, recuperar exactamente todas las series después de recarga y reinicio | 35 + 10 comprobaciones; `.../forecasts-acceptance/` |
| Ejecución | Estrategia y ventana, preflight válido/negativo SOC, ejecución física+EMS, resultado inmutable, recarga y mismo costo | operar aprobado; `.../2c/` |
| Interrupción | Iniciar misión larga, terminar el servidor con SIGKILL, reiniciar: anterior concluida recuperada y activa marcada interrumpida | reinicio y tablet aprobados; `.../2c/` |
| Archivo | Exportar escenario real, importar en instalación vacía con motor sabotado, SHA, consulta, duplicata, URL, reinicio, tablet | cuatro fases aprobadas; `.../2da/` |
| Informes | PDF, diagnóstico de fallo, Excel, figuras PNG/SVG, ZIP, origen local/archivo/reinicio | cuatro fases aprobadas; `.../2db/`; 157 comprobaciones de los archivos descargados en `evidencias/logs/stab-report-downloads.log` |
| Solar | Tres modelos, comparación, gráfico, CSV, temperatura inválida rechazada y recarga | 23 comprobaciones; `evidencias/logs/stab-bench-solar.log` |
| Eólica | Simulación histórica, curvas, CSV, viento negativo rechazado, recarga | 22 comprobaciones; `.../stab-bench-wind.log` |
| Térmica | Central, despacho y costos, gráficos, CSV, timestamp inválido rechazado y recarga | 21 comprobaciones; `.../stab-bench-thermal.log`; unidad local cubierta por regresión de dominio |
| Batería | Tremblay–Dessaint y 2RC, simulación, SOC/gráficos, dos CSV, CSV inválido y recarga | 29 comprobaciones; `.../stab-bench-battery.log` |
| H₂/PEMFC | Dinámica, hidrógeno, gráficos, CSV, entrada inválida y recarga | 20 comprobaciones; `.../stab-bench-h2.log` |
| MIX | Cinco fuentes, timeline común, respuesta, balances, gráficos, CSV, propuesta incompleta bloqueada y recarga | 16 comprobaciones; harness de ruta legada `mix_acceptance_app.py`; `.../stab-bench-mix.log` |
| Catálogo eólico | Trece selectores; todos los nodos gráficos comparados exactamente en las unidades mostradas; referencia/pico; tres nuevas simulaciones y CSV; cuatro rechazos energéticos | 103 comprobaciones; `.../wind/`; límites/cut-in/cut-out/densidad adversarial en regresión física, sin atribuir estos últimos a un recorrido de navegador |
| P0 transferencia | A válida → guardar B con distinta cantidad PEMFC → fallo después de escribir estado → ejecución deshabilitada → navegación no desbloquea → reintento explícito | 24 comprobaciones de P0 y consentimiento; `transfer_fault_app.py` inyecta la falla únicamente en servidor de prueba; `.../stab-transfer-browser.log` y capturas blocked/retried; dos revisiones con exclusiones distintas vuelven a exigir confirmación, aunque su especificación efectiva sea igual |
| Sin escritura | Directorio real chmod 0555, arranque antes/después | Antes traceback; después mensaje de almacenamiento y detención controlada, sin excepción; capturas readonly y protocolo `readonly` |

El monitor añadido por `chromium_system.cjs` registra `pageerror` y `console.error` de todas las páginas/contextos. **Cero eventos de esos tipos** en los recibos finales. Los recorridos rechazan `stException`, salvo el registro deliberado anterior a las correcciones. Las bancadas y los protocolos tablet verifican ausencia de desplazamiento horizontal de página; las tablas mantienen desplazamiento interno legítimo. No se encontraron controles bloqueantes inaccesibles ni gráficos que impidieran operar en esas resoluciones.

## Defectos del guion identificados

Streamlit monta Plotly cuando entra en el viewport: leer inmediatamente después del fin de Python podía obtener `null`. Se añadieron esperas de renderizado en los guiones 2B/2D-A. Plotly usa `reset+autosize`: los modos alternan márgenes automáticos con diferencias de redondeo subpíxel (se observaron 23 ms en un eje de dos horas). El guion 2B ahora recorre ambos modos; **conserva la aserción exacta de encuadre original** y añade comprobaciones de dominio completo y de todos los valores tras el primer reset. No se introdujo tolerancia ni se alteró producción para esa observación. El recorrido final pasó sus 45 comprobaciones operativas.

## Reproducción

```bash
python -m pip install -r requirements.txt pytest==8.4.2
npm install --no-save playwright@1.62.1
# Chromium debe existir; CHROMIUM_EXECUTABLE permite seleccionar su ruta.
python tools/e2e/run_stabilization.py piso1 gestor 2a 2b 2c 2da 2db forecasts benches transfer readonly
```

El runner prepara datos ficticios, inicia servidores propios, guarda stdout/telemetría/capturas en `tools/e2e/out/stabilization/` y reinicia entre fases. No usar datos reales. La prueba de permisos debe ejecutarse como usuario sin privilegios. El protocolo 2C termina un servidor propio durante una rodada; 2DB repite recuperación tras SIGKILL. El catálogo ampliado se reproduce con `e2e_stabilization_wind.js`; el JSON esperado debe exportarse del catálogo revisado, como indica el comando de la matriz.

Los logs finales completos y recibos están versionados en `evidencias/logs/`. Una selección de capturas originales se conserva en `evidencias/capturas/`. `artefactos-navegador.json` enumera tamaño y SHA-256 de todos los archivos producidos; el estudio científico sintético completo se incluye en el ZIP de evidencias del workspace (fuera de Git). No se versionan archivos de almacenamiento de instalaciones. Las restantes capturas/descargas se regeneran con los comandos; no se confunde un hash sin archivo con una captura inspeccionada.

Los archivos `FAIL`/`failure` conservados son diagnósticos de intentos anteriores (incluidos selectores incorrectos del guion y el error térmico previo). El recibo y stdout finales de cada protocolo determinan su aceptación; esos diagnósticos no se presentan como fallos finales ni se borran para ocultar incidencias.

Los stdout que contienen espacios finales se almacenan como `.log.gz`, conservando **todos los bytes originales** y evitando errores de formato en `git diff --check`. Leerlos con `gzip -dc archivo.log.gz`. El registro `evidencias/logs-comprimidos.json` fija tamaño y SHA-256 de cada original; no se normalizaron ni editaron los mensajes o valores del log.
