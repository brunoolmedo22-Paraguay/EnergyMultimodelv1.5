# MISIÓN WORK-BIBLIO-SEEDS2-01
## Auditoría del código fuente + levantamiento bibliográfico exhaustivo y trazabilidad científica del TCC SEEDS2

**Fecha de encargo:** 12 de noviembre de 2026.  
**Tipo de misión:** Investigación científica exhaustiva, auditoría bibliográfica del código, construcción de una biblioteca de referencias y matriz de evidencia.  
**Idioma del diálogo/encargo:** español; **todos los informes académicos, tablas de interpretación, fichas y textos de fundamentación del TCC deberán redactarse en PORTUGUÉS (Brasil)**, excepto títulos originales, citas textuales breves y cadenas técnicas.  
**Acción permitida sobre SEEDS2:** SOLO LECTURA. NO modificar código, abrir PR, crear ramas, hacer commits, actualizar dependencias, ejecutar cargas destructivas ni alterar el repositorio.

---

# 0. LA MISIÓN EN UNA FRASE

Necesito que investigues profundamente la literatura científica internacional para sustentar **cada parte relevante** de la plataforma SEEDS2 y su EMS jerárquico MILP–MPC, comenzando por **leer y auditar la implementación matemática y computacional real en GitHub**. Entrega una biblioteca bibliográfica verificable, jerarquizada y directamente utilizable para escribir un artículo científico autónomo de alta calidad.

No quiero una lista genérica ni un ensayo inventado. Quiero una **cartografía de evidencias**: cada publicación importante debe decir qué afirmación, modelo, ecuación, algoritmo, decisión arquitectónica o metodología de evaluación puede sustentar, qué demuestra y qué NO demuestra, y, cuando sea pertinente, a qué módulo/línea del código SEEDS2 corresponde.

# 1. CONTEXTO CIENTÍFICO INNEGOCIABLE

Repositorio: https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5

SEEDS2 es una plataforma computacional de investigación en Python/Streamlit para configuración, modelado, simulación, operación y evaluación energética de microrredes. Incluye o ha desarrollado modelos de tecnologías renovables, baterías, PEMFC/H₂, tecnología térmica y conexión a red; manejo de catálogos, escenarios, perfiles, previsiones, persistencia y visualización. Su EMS experimental V2 incorpora optimización matemática MILP y operación MPC de horizontes coordinados, con planificación de largo plazo y señal de valor futuro de la energía. El legado V1.6 incluye otras estrategias de optimización; **no confundir sus capacidades con las del EMS V2**.

Las DOS contribuciones centrales tienen IGUAL PESO:

**I. Plataforma:** arquitectura modular/reconfigurable, integración tecnológica, interfaces científicas, reproducibilidad, coherencia de datos y capacidad de estudiar distintas microrredes sin rehacer la aplicación.

**II. EMS jerárquico:** formulación, implementación y evaluación de coordinación MILP–MPC entre horizontes largos y cortos; decisiones causales, restricciones operativas, actualización de estado y valor futuro de energía.

Los casos de estudio son exactamente DOS:

- **Estudo de Caso I:** microrred industrial hipotética conectada a la red, con CUATRO configuraciones de un MISMO estudio comparativo: C1 red; C2 red + solar FV; C3 red + batería; C4 red + FV + batería. Contexto de curva típica/tarifas de COPEL, Paraná. No son cuatro artículos ni cuatro estudios separados.
- **Estudo de Caso II:** embarcación aislada de la red, con sistema energético híbrido propio, incluyendo PEMFC/H₂, batería, solar si está efectivamente configurado y demanda embarcada. No presentar el caso como validación experimental física si no hay mediciones reales que lo sustenten. En decisiones recientes de diseño de la embarcación la PEMFC comienza encendida, potencia anterior de 30 kW y una rampa de 2 kW/s (120 kW/min); verificar la configuración real en código y no interpretar estos valores como resultados.

**La comparación entre C1–C4 evalúa composición tecnológica**. Para identificar el efecto del EMS jerárquico, comparar estrategias bajo la MISMA configuración física y condiciones equivalentes (por ejemplo, C4 con y sin señal de valor futuro). No inferir ahorro por algoritmo a partir de la mera diferencia C1 vs C4.

El artículo científico principal debe ser autónomo: fundamentación suficiente, métodos centrales, ecuaciones esenciales, parámetros relevantes, protocolo experimental, resultados y conclusiones dentro del propio manuscrito. Materiales suplementarios podrán ampliar o permitir reproducir, pero no sustituir explicaciones esenciales. No redactes el manuscrito ahora: **esta misión es exclusivamente bibliográfica y de auditoría de respaldo**.

Estructura principal ya acordada para el TCC en portugués:
1. Introdução.
2. Fundamentação teórica e trabalhos relacionados.
3. Arquitetura e desenvolvimento da plataforma SEEDS2.
4. Modelagem matemática e sistema de gerenciamento energético hierárquico.
5. Metodologia de avaliação e estudos de caso.
6. Resultados e discussão: avaliação da plataforma; estudo industrial comparativo C1–C4; embarcação isolada; discussão integrada.
7. Conclusões e trabalhos futuros.

Título provisional: **SEEDS2: Desenvolvimento e Avaliação de uma Plataforma Modular de Simulação de Microrredes com Gerenciamento Energético Hierárquico Baseado em MILP–MPC**.

# 2. PRIMERA FASE OBLIGATORIA: AUDITORÍA DEL REPOSITORIO

Antes de iniciar la búsqueda bibliográfica masiva:

1. Abre el repositorio GitHub. Registra **fecha UTC, rama, SHA completo, PRs relevantes y estado real** al momento de la auditoría. La situación de referencia al 12/11/2026 incluía trabajo 3D-B en PR draft #24; **no asumas que sigue igual**. Identifica código fusionado a main y código solo presente en branches/drafts. Diferencia implementado, en revisión, experimental, documentado pero no ejecutable y planeado. Si no puedes acceder a GitHub, informa el bloqueo y NO pretendas haber leído la implementación.
2. Realiza un inventario basado en código, NO en README solamente: organización, importaciones, catálogos, modelos físicos, módulos de simulación, `orchestrator`, EMS legado y EMS V2, almacenamiento de estados, mecanismos de auditoría, curvas, costos, solver, horizonte temporal, normalizaciones de unidades y resultados científicos.
3. Para CADA familia tecnológica (FV, eólica, baterías, PEMFC/H₂, térmica, demanda, PCC/red), encuentra las funciones implementadas, entradas, salidas, hipótesis, ecuaciones efectivas, interpolaciones y discretizaciones, límites físicos y su tratamiento de excepciones.
4. Para optimización: identifica variables, índices temporales, función objetivo, balance de energía, restricciones unit commitment, rampas, tiempos mínimos de operación, SOC, eficiencia, estados iniciales, ventanas MPC, horizonte largo, fórmula exacta del valor futuro y criterios de solución/tolerancias. Distingue código de solver de visualización. Si algo no está implementado, dilo.
5. Rastrea referencias ya citadas en repositorio: archivos README, docs, comentarios, `*.bib`, trabajos de tesis, docstrings, tests, manuales y archivos de catálogo. Verifica que existan y correspondan realmente al modelo. **No presupongas que el autor o el nombre de un archivo es la referencia original correcta**.
6. Investiga especialmente la fuente que el autor del proyecto identifica como **«Otekon»** para la PEMFC (posible grafía imprecisa). Busca variantes en código, documentación y literatura; identifica título, autores, año, DOI, ecuaciones y parámetros. Si hay varias coincidencias, registra alternativas y evidencia; NO inventes una atribución.
7. Fija un *mapa código → ecuación/modelo → referencia candidata* con `ruta`, `función/clase`, `línea o intervalo`, `commit`, expresión matemática interpretada, fuente y grado de correspondencia. Distingue correspondencia exacta, adaptación justificada, analogía, inconsistencia o falta de fuente.
8. Audita, con igual atención, afirmaciones de arquitectura (plug-and-play, modularidad, trazabilidad, ejecución reabrible) y afirmaciones matemáticas. No etiquetes como «validada» una implementación por el solo hecho de que exista un paper similar.

**PROHIBIDO modificar el código.** Si detectas divergencias entre publicación y código, inclúyelas en hallazgos, con severidad, evidencia y recomendación de revisión, sin corregirlas.

# 3. ALCANCE DE LA INVESTIGACIÓN BIBLIOGRÁFICA

Busca simultáneamente por **similitud con SEEDS2** y **fundamentos específicos de sus modelos**:

## A. Prioridad máxima: precedentes próximos a SEEDS2
- Plataformas científicas modulares de modelado, simulación, optimización y análisis de microrredes; configuración plug-and-play, APIs de dispositivos, modelos reconfigurables, simulación reproducible y benchmarking.
- Herramientas existentes: plataformas académicas/open-source o comerciales comparables en funcionalidad (por ejemplo HOMER, REopt, OpenEMS, GridLAB-D, PyPSA, oemof, pandapower, OpenDSS, pymgrid, etc.) **solo si existe una comparación honesta y relevante**. Identificar exactamente qué problema resuelven; evitar afirmar que no existen herramientas similares.
- Software científico con plataformas multi-tecnología, diseño orientado a componentes y validación de motores de optimización.

## B. EMS, MILP–MPC y coordinación temporal
- Energy management system en microrredes, despacho óptimo, MPC de horizonte recedente, state carry-over, horizontes múltiples, pronóstico, planificación estratégica-operativa, dual decomposition y coordinación jerárquica cuando corresponda.
- Valor futuro de energía, valor terminal, coste-de-ir, shadow prices, water value, approximate dynamic programming, stochastic programming y valoración de batería/reserva. **Precisar diferencias entre estas familias y la implementación real. No atribuir a SEEDS2 algoritmos que no implementa.**
- Modelos MILP de almacenamiento, commitment de generadores/PEMFC, rampas, modos excluyentes del PCC, piecewise-linear / PWL nonconvex, tratamiento de costos y límites.
- Investigaciones con baselines comparables y métodos de validación reproducible, análisis causal de despacho y evaluación de sensibilidad.

## C. Origen matemático de cada modelo energético implementado
- Solar FV: ecuaciones reales según la implementación (p. ej. curva I–V, irradiancia, temperatura de celda, temperatura ambiente, inversor, eficiencias), no encajar a la fuerza una fórmula de diodo si el código no la usa.
- Eólica: curvas de potencia, interpolación, densidad del aire, altura, efecto estela/wake **solo si el código lo modela**, comportamiento off-design y fidelidad de fichas técnicas.
- Batería/BESS: balance de energía/SOC, potencia de carga/descarga, eficiencias, límites, degradación **solo si existe**, consistencia temporal y estados iniciales.
- PEMFC/H₂: ecuaciones electroquímicas, consumo de H₂ vs potencia, curva característica, segmentación/PWL, costo, estados ON/OFF, rampas y arranques. Rastrear exactamente «Otekon» y toda adaptación o diferencia de variables/unidades.
- Térmica / generadores: modelos de combustible y costo variable, rampas, exclusión de módulos pendientes; no atribuir funcionalidad que aún no está operativa en V2.
- Redes y demandas: intercambio en PCC, tarifas, capacidad, perfiles típicos oficiales COPEL/ANEEL, datos meteorológicos/ERA5/Open-Meteo y transformaciones temporales relevantes.

## D. Arquitectura científica, herramientas y reproducibilidad
- Python para computación científica; Streamlit como interfaz y sus limitaciones reales; Pyomo y HiGHS como modelado/solución; SciPy si está en uso; persistencia, versionado de escenarios, provenance, scientific software engineering, tests y reproducibilidad.
- Priorizar **publicaciones de herramientas y documentación primaria mantenida**. Un manual oficial puede fundamentar API/funcionalidad, pero no reemplaza papers para afirmaciones científicas generales.
- Distinguir software científico, gemelos digitales, hardware-in-the-loop y validación en campo: no llamar a SEEDS2 digital twin o experimentalmente validado sin evidencia específica.

## E. Metodología y evaluación
- Normas de benchmarking de optimización, comparación con baselines, validación de modelos numéricos y de conservación energética, reproducibilidad, análisis de incertidumbre y limitaciones.
- Aplicaciones industrial grid-connected y shipboard/isolated energy management con batería, PEMFC e hidrógeno. Buscar referencias tanto de la composición tecnológica como de la estrategia EMS.
- Aporte de estudios de casos para validar RECONFIGURABILIDAD arquitectónica y viabilidad matemática, sin reclamar universalidad.

# 4. FUENTES Y ESTRATEGIA DE BÚSQUEDA

Explora, cuando accesibles, **Web of Science, Google Scholar, Scopus, ResearchGate**, IEEE Xplore, ScienceDirect, SpringerLink, Wiley, MDPI, Taylor & Francis, ACS cuando relevante, arXiv como pista, y bases bibliográficas abiertas Crossref, OpenAlex, Semantic Scholar, DOAJ, CORE, institutional repositories, editoriales, NREL/DOE/IEA, documentación oficial de librerías y organismos brasileños COPEL/ANEEL/INMET cuando proceda.

- Utiliza principalmente términos **en inglés** y sinónimos. Repite consultas en campos TITLE/ABSTRACT/KEYWORDS cuando el buscador lo permita.
- Cubre trabajos fundacionales antiguos + panorama reciente (especialmente 2015–12/11/2026, ajustando por área). No descartes originales relevantes por antigüedad.
- Métodos de exploración: búsqueda temática, *backward snowballing* (referencias citadas) y *forward snowballing* (quién cita a un paper), búsqueda por autores/modelos, trabajos de revisión y búsqueda cruzada por título/DOI.
- Prioriza artículos revisados por pares, trabajos seminales, tesis originales técnicamente justificadas, estándares relevantes y documentación técnica primaria; clasifica preprints/no revisados y páginas promocionales como evidencia distinta.
- **ResearchGate es una vía de descubrimiento o de acceso, no garantía de calidad editorial ni fuente canónica de metadatos.** Utiliza DOI/página de editor para la cita principal.
- Si WoS/Scopus requieren credenciales institucionales, registra la barrera y pide interacción autenticada únicamente si existe acceso legítimo; no eludas controles de acceso, captchas ni paywalls. Continúa mediante fuentes abiertas. No uses automáticamente un resultado de Google Scholar como prueba de que se leyó el texto completo.
- Guarda consultas, fecha, plataforma, filtros, cantidad inicial, cantidad descartada, duplicados y criterios de selección. **No afirmar revisión sistemática PRISMA si no se implementó realmente un protocolo sistemático**.
- Comprueba DOI, título, autores, año, revista/editorial y URL; identifica retractaciones/correcciones cuando sea posible. No inventes DOIs, citas, páginas, fórmulas, resultados, cuartiles o índices de citación.

# 5. VOLUMEN Y PROFUNDIDAD OBJETIVO

Ambición bibliográfica:
- **Objetivo de prospección:** 200–300 registros candidatos potencialmente relevantes, después de eliminar duplicados. El objetivo es amplitud; no inventar fuentes para completar una cifra.
- **Objetivo de cribado serio:** al menos 100 registros revisados a nivel de título/resumen y relevancia.
- **Objetivo de verificación prioritaria:** 80–120 referencias con metadatos contrastados y clasificación temática; cuando exista texto completo, verificar las ecuaciones/afirmaciones importantes directamente allí.
- **MÍNIMO ACADÉMICO DE ENTREGA:** 50 referencias de alta relevancia con identidad bibliográfica y fuente primaria comprobadas, justificación individual y posibilidad concreta de uso en el artículo. Si el universo realmente comprobable fuera menor, informa la cifra real y la razón: nunca rellene con publicaciones ficticias.
- Un subconjunto de 20–30 fuentes NÚCLEO debe recibir ficha profunda de lectura y vinculación con código/método o con el argumento científico central.
- No saturar el artículo con 200 citas. El repositorio de fuentes es más amplio que la bibliografía que se seleccionará para el manuscrito.

# 6. CLASIFICACIÓN, PRIORIZACIÓN Y HONESTIDAD DE EVIDENCIA

Clasifica cada fuente con DOS etiquetas independientes:

**Prioridad editorial**
- **P0 — Fonte original da implementação:** paper/manual/dataset del que se tomó una ecuación, curva, coeficiente o algoritmo efectivamente presente en código. Puede ser imprescindible aunque su tema no sea una plataforma similar.
- **P1 — Correspondência de alta prioridade:** plataformas verdaderamente comparables; EMS modular/plug-and-play; coordinación MILP–MPC de largo-corto plazo; valor futuro en microrredes, cuando hay convergencia real.
- **P2 — Fundamentação metodológica e de tecnologia:** artículos sustanciales de PV, eólica, baterías, PEMFC/H₂, térmica, PCC, optimización y criterios de modelado, incluso si no son la fuente exacta implementada.
- **P3 — Validação, comparação e engenharia de software científico:** reproducibilidad, pruebas, benchmarks, datos, Pyomo/HiGHS, Streamlit/Python, marcos científicos y otros métodos.
- **P4 — Contexto e revisão geral:** antecedentes amplios, transición energética, microredes en general, revisiones de soporte secundario.

**Nivel de evidencia/lectura (por fuente, separado de la prioridad):**
- F = texto completo consultado y pasajes relevantes verificados (página/ecuación cuando corresponda);
- A = abstract/resumen consultado, sin confirmación en texto completo;
- M = metadatos contrastados únicamente;
- X = fuente inválida o dudosa (fuera del corpus de 50).

**Tipo de relación:** fuente directa de modelo; ecuación equivalente; adaptación compatible; respaldo contextual; analogía parcial; contradicción; referencia por verificar.

**Crítica obligatoria:** identificar papers que contradicen simplificaciones o muestran limitaciones, no solo los que respaldan nuestras decisiones.

# 7. MATRIZ DE TRAZABILIDAD OBLIGATORIA

Por cada punto de implementación de interés, completar al menos:
`id_modelo`, `componente`, `arquivo_codigo`, `funcao_ou_classe`, `linhas`, `commit_sha`, `equacao_ou_logica_real`, `unidades`, `hipoteses`, `referencia_original_candidata`, `doi`, `local_exato_no_paper_pagina_eq`, `grau_correspondencia`, `lacunas_ou_divergencias`, `status_de_verificacao`, `risco_para_tcc`.

Para cada afirmación científica pretendida en el artículo:
`claim_id`, `seção_artigo`, `afirmação_que_pode_ser_escrita`, `referencias_adequadas`, `o_que_as_fontes_sustentam`, `o_que_NAO_sustentam`, `necessidade_de_resultado_do_SEEDS2`, `status`.

Ejemplos de diferencias que deben quedar visibles:
- Papel fundamenta ecuación teórica pero código utiliza aproximación/interpolación adaptada.
- Código calcula consumo de H₂ en un régimen que el paper original no estudió.
- La batería no tiene modelo de degradación aunque un artículo de BESS sí lo tenga.
- Un artículo encuentra ventajas del MPC, pero en SEEDS2 todavía debemos demostrar nuestras propias ventajas con resultados.
- La tarifa oficial COPEL respalda el insumo tarifario, no la supuesta representatividad estadística de todos los consumidores industriales.

# 8. ENTREGABLES OBLIGATORIOS

Entregar un **paquete bibliográfico descargable**, no únicamente una respuesta en chat. Estructura ideal:

```
SEEDS2_BIBLIO_AUDITORIA_ENTREGA/
├── 00_LEIA-ME.md                      # índice e instrucciones
├── 01_RELATORIO_EXECUTIVO_PT.pdf      # conclusiones y prioridades
├── 02_MAPA_DE_ESTADO_DA_ARTE_PT.pdf   # tendencias, taxonomía, revisiones críticas
├── 03_INVENTARIO_CODIGO_E_MODELOS.md # por componente, commit, evidencia
├── 04_MATRIZ_REFERENCIAS.xlsx         # 200+ candidatos cuando verificables; ranking, DOI, etiquetas, URLs, notas
├── 05_CODIGO_VS_LITERATURA.xlsx       # rutas/ecuaciones/fuentes y divergencias
├── 06_CLAIMS_PARA_O_ARTIGO.xlsx      # afirmación → fuentes → sección → nivel de soporte
├── 07_REFERENCIAS_VERIFICADAS.bib     # BibTeX limpio sin duplicados, orientado a elsarticle
├── 08_REFERENCIAS_VERIFICADAS.ris     # compatible Zotero/Mendeley
├── 09_FICHAS_NUCLEARES_PT/           # 20–30 lecturas críticas profundas, con citas
├── 10_BUSCAS_E_PROVENIENCIA/         # consultas WoS/Scholar y otras, límites, proceso de deduplicación
├── 11_LACUNAS_E_DISCREPANCIAS.md     # errores/ausencias, sin modificar el código
├── 12_ROTEIRO_CITACOES_ARTIGO_PT.md  # secciones 1–7, qué citar, por qué, fuentes fuertes
├── 13_LISTA_PRIORITARIA_DE_LEITURA.md # top 30 con orden y motivo
└── 14_MANIFESTO_E_VALIDACOES.md      # sumas, porcentajes, cobertura, fecha, links de salida
```

**No es obligatorio generar PDFs si el entorno no permite:** entrega equivalente MD/DOCX con tablas legibles. Lo crucial es la integridad de la evidencia y los archivos `.xlsx`, `.bib`, `.ris`, `.md`.

**En 04_MATRIZ_REFERENCIAS.xlsx:** una fila por trabajo único, con campos verificables de identificación, inclusión, prioridad, categoría, nivel de lectura, síntesis, diferencias, código conectado, sección del artículo, fecha de validación, DOI y enlaces al editor/OA. Incluir filtros y hojas de resumen.

**En 07_BIB:** las claves deben ser estables, sin duplicados; los metadatos deben corresponder a fuentes comprobadas, compatibles con `elsarticle`. No inventar clave DOI/URL si no existe. Diferenciar editor vs preprint.

**En 09_FICHAS:** para cada núcleo, incluir (a) pregunta/problema; (b) método ecuaciones y supuestos; (c) resultados REALES con límites; (d) comparación con SEEDS2; (e) fragmento conceptual para sección del artículo; (f) ubicación exacta de evidencia: página/ecuación/figura si se leyó. No inventar citas textuales; parafrasear con fuente.

**Materiales con derechos de autor:** no redistribuir PDFs cerrados o artículos completos sin permiso. Entrega DOI/links y, solo cuando esté permitido, enlaces o copias de acceso abierto conforme a la licencia.

# 9. PREGUNTAS DE AUDITORÍA QUE NECESITO QUE RESPONDAS

1. ¿Cuáles son las 10–20 investigaciones y plataformas más parecidas a SEEDS2, en qué se parecen y se diferencian, con evidencia verificable?
2. ¿Qué literatura demuestra la conveniencia/las limitaciones de un EMS jerárquico largo-corto plazo, y cuáles son los mejores baselines para nuestro caso?
3. ¿Qué trabajos definen el uso del valor futuro de energía/terminal cost/value function de forma conceptualmente compatible con nuestro código, y cuáles no son equivalentes?
4. ¿Qué ecuaciones, curvas y restricciones del software cuentan con soporte bibliográfico DIRECTO? ¿Cuál es su fuente original?
5. ¿Qué componentes tienen solo apoyo INDIRECTO o documentos técnicos, y cuáles presentan discrepancias bibliográficas/matemáticas?
6. ¿Cuál es la referencia exacta de «Otekon» vinculada con nuestro modelo PEMFC y qué parte del código viene efectivamente de ella?
7. ¿Qué bibliografía sustenta las elecciones de modelos FV, eólico, BESS y límites de aplicación? ¿Qué hipótesis no están representadas?
8. ¿Cómo podemos fundamentar científicamente la ingeniería de plataforma (modularidad, interfaces, persistencia, reproducibilidad) sin presentar Streamlit como innovación algorítmica?
9. ¿Qué referencias son obligatorias en la introducción, en trabajos relacionados, en arquitectura, en la sección matemática y en metodología experimental?
10. ¿Qué afirmaciones del futuro artículo debemos evitar por falta de evidencia, evidencia conflictiva o límites de implementación?

# 10. CONTROL DE CALIDAD ANTES DE TERMINAR

- No dar por concluida la misión con apenas 15–20 fuentes o una lista informal. Construir la biblioteca solicitada y reportar métricas de cobertura reales.
- No atribuir soporte empírico al código por similitud temática; correlacionar expresiones exactas cuando sea posible.
- No crear bibliografía inventada, DOIs ficticios, revistas falsas ni citas atribuidas a autores incorrectos.
- No usar una misma publicación como validación universal de muchos modelos sin justificar las correspondencias.
- Marcar diferencias entre versiones de código; no asumir que un draft está fusionado.
- No modificar repositorios.
- No redactar el TCC ni abrir PRs. Esta misión prepara su fundamentación.
- Separa: (i) respaldo teórico, (ii) respaldo metodológico, (iii) evidencia de implementación en el código, (iv) validación numérica, y (v) validación física/experimental. Estas categorías no son equivalentes.
- Explica limitaciones de acceso y trabajo no verificado; nunca simules haber leído un texto completo si solo accediste a un resumen.
- Haz una verificación final de integridad entre XLSX, BibTeX, RIS, fichas, DOIs y rutas; los identificadores deben coincidir.

# 11. ORDEN DE EJECUCIÓN

**Fase 1:** inspección de GitHub e inventario científico del código.  
**Fase 2:** búsqueda de fuentes originales para cada modelo y curva; documento Otekon.  
**Fase 3:** levantamiento exhaustivo de plataformas/EMS e investigaciones comparables.  
**Fase 4:** búsqueda por referencias/citantes y deduplicación; crítica, clasificación y verificación profunda.  
**Fase 5:** vínculo ecuaciones–código–publicaciones, y reclamos científicos–referencias.  
**Fase 6:** ensamblaje de archivos y auditoría final de enlaces, DOI y cobertura.

**ENTREGA FINAL:** un ZIP más una síntesis gerencial en portugués con: cantidad encontrada/cribada/verificada, top 15, riesgos bibliográficos, mapas de soporte por componente, documentos imprescindibles que falta conseguir, y propuestas de qué secciones del artículo pueden ya fundamentarse con rigor. Prioriza calidad y honestidad; si falta acceso a una fuente, consígnalo sin fingir lectura.

**COMIENZA LEYENDO EL REPOSITORIO Y REGISTRANDO EL SHA. NO EMPIECES ESCRIBIENDO INTRODUCCIONES NI PROPONIENDO CAMBIOS AL SOFTWARE.**
