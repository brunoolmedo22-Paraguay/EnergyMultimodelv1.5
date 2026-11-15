# Mapa de sustentación bibliográfica por sección del futuro artículo

El trabajo académico tendrá siete secciones. Este documento determina qué evidencia buscar, no anticipa afirmaciones cuantitativas no demostradas.

## 1. Introdução
- Microredes/híbridos, retos de integración tecnológica y operación con recursos heterogéneos.
- Variabilidad de carga/renovables; restricciones y coordinación temporal.
- Dificultad de reproducir comparaciones entre configuraciones distintas.
- Trabajos de revisión y perspectivas con DOI verificable; al menos 5–10 referencias fuertes candidatas.

## 2. Fundamentação teórica e trabalhos relacionados
- Matriz de plataformas comparables: funcionalidad, software, modularidad, optimización, reproducibilidad, limitaciones; evidencia de características REALES.
- Literatura de EMS, MILP, MPC, optimización jerárquica y valor terminal/futuro.
- Modelos tecnológicos y adaptaciones. Distinguir origen de modelo vs referencia de contexto.
- Top 15–20 trabajos que puedan fundamentar el posicionamiento científico.

## 3. Arquitetura e desenvolvimento da plataforma SEEDS2
- Fundamentos de software científico modular, trazabilidad, experimentación, versionado e interfaces reproducibles.
- Publicaciones/manuales primarios de tecnologías realmente utilizadas (Python, Streamlit, Pyomo, HiGHS, datos climáticos, etc.).
- Comparación con arquitecturas similares en microgrids. No convertirlo en manual de UI.
- Bibliografía de orígenes matemáticos cuando se describen integración de modelos.

## 4. Modelagem matemática e sistema de gerenciamento energético hierárquico
- **Todas las ecuaciones esenciales de la formulación real**, respaldadas por papers originales o por derivación explícita; en el código ubicar función y línea.
- MILP: balances, restricciones, no simultaneidad, PWL, commitment, rampas, etc.
- MPC: horizonte móvil, estado causal, términos terminales, valor de energía almacenada, actualización de decisiones.
- Distinguir hipótesis del paper vs ecuaciones realmente implementadas.

## 5. Metodologia de avaliação e estudos de caso
- Diseño comparativo de cuatro configuraciones del MISMO caso industrial COPEL y caso embarcación autónoma.
- Fuentes originales del perfil típico COPEL, tarifas, irradiación/temperatura/datasets y datos de equipos cuando realmente usados.
- Baselines, métricas energéticas/económicas, comprobación de restricciones, sensibilidad y reproducibilidad.
- Evitar extrapolar escenarios hipotéticos a representatividad de clientes reales.

## 6. Resultados e discussão
- Citar literatura comparable solo para contextualizar magnitud, mecanismos y límites; no usar resultados ajenos como resultados de SEEDS2.
- Resaltar la evaluación comparativa C1–C4 como UN estudio; EMS con y sin jerarquía en configuración idéntica, y embarcación como segundo estudio.
- Verificar si los papers comparados usan igual métrica, periodo, tecnología, tarifa, horizonte y modo de optimización; si no, no afirmar superioridad por números cruzados.

## 7. Conclusões e trabalhos futuros
- Conclusiones dependientes de experimentos propios. Las referencias sirven para contextualizar límites y futuras líneas, no para reemplazar evidencia.
- Señalar modelado simplificado, validación física pendiente, incertidumbres no tratadas y alcance exacto del código.

## Entregable central
Crear tabla `seção → questão → claim provável → REF IDs → tipo de evidência → observação/limitação → fontes ainda faltantes`. El artículo futuro es AUTÓNOMO; los ZIP de código/casos/figuras son secundarios y pueden aparecer en una Data Availability Statement.
