# SEEDS2 — ACUERDOS CIENTÍFICOS Y EDITORIALES
**Registro de decisiones | 15 de noviembre de 2026 | Estado: aprobado como orientación editorial, sujeto a auditoría del código**

## 0. Propósito y jerarquía documental
Este documento conserva los acuerdos entre el autor y su asistente para escribir el TCC de SEEDS2. **No es una descripción verificada de la implementación**. La auditoría integral read-only de Claude determinará el comportamiento efectivo del código. Las afirmaciones sobre capacidades, fórmulas, flujos y resultados deberán contrastarse con el commit auditado y los artefactos finales.

Documentos históricos: paquete `DOC-20261112-WA0044.zip` (guion/protocolo original); `DOC-20261112-WA0045.zip` (bibliografía e inventario histórico); `DOC-20261112-WA0040.zip` (identidad autoral). Guion extraído: `SEEDS2_GUION_ORIGINAL_12NOV/`. **Las decisiones del 15/11 actualizan el índice de siete secciones original**, conservando su lógica y las dos contribuciones.

## 1. Identidad del trabajo
**Título de trabajo (PT):** *SEEDS2: Desenvolvimento e Avaliação de uma Plataforma Modular para Simulação Operacional e Otimização do Despacho Energético em Microrredes utilizando EMS Hierárquico MILP–MPC*.

**SEEDS:** Smart Energy Ecosystem for Decision Support. No explicar la historia del número 2 ni mezclar SEEDS2 con otra plataforma anterior.

**Tesis central:** SEEDS2 es un entorno computacional **modular y reconfigurable de simulación y apoyo a decisiones**, en el que el usuario compone microrredes, configura equipos, define o modifica escenarios y examina resultados bajo una arquitectura común. Su segunda contribución, de igual peso, es la integración de un EMS jerárquico basado en MILP–MPC. No describirlo como controlador autónomo de una planta real.

**NO usar por ahora «plug-and-play» como promesa de uso irrestricto.** Existen condiciones de configuración y restricciones de admisibilidad; la experiencia no es todavía totalmente automática. Preferir *plataforma modular e reconfigurável*, *ambiente de simulação configurável* y términos equivalentes, siempre contrastados con código.

**No reivindicar:** invención de MILP/MPC; superioridad universal; primer sistema de su clase; validación física experimental; compatibilidad irrestricta con cualquier equipo o usuario.

## 2. Mensaje científico que debe guiar introducción y resumen
La versatilidad se ilustra mediante **dos aplicaciones computacionales contrastantes** bajo la misma plataforma:

- **Estudio I — Microrred industrial conectada a la red:** cuatro configuraciones C1–C4 dentro de un único estudio (red; red+FV; red+batería; red+FV+batería). El contexto tarifario diferencia periodos de menor y mayor precio; se observó un comportamiento de carga de batería antes de la punta y descarga en la punta. Verificar causalidad y registros antes de afirmar que el valor futuro fue la causa decisiva.
- **Estudio II — Embarcación híbrida aislada:** coordinación PEMFC/FV/batería bajo variaciones de demanda. Se observó uso de batería para responder a variaciones y aumento de generación PEMFC para recuperar energía almacenada antes de una segunda fase de alta carga. Confirmar el registro exacto y las restricciones antes de atribuir intención/causalidad al algoritmo. No discutir autonomía, kilometraje o agotamiento de H₂ como resultado si no fueron modelados.

**En la introducción y el resumen:** describir el contraste y su significado cualitativo; no sobrecargar con valores de costo, porcentajes, SOC, parámetros, tablas ni derivaciones. La introducción presenta problema, objetivo y contribución; no adelanta la sección de resultados. La redacción definitiva dependerá de la auditoría y los datos comprobados.

## 3. Estructura adoptada — secuencia del orientador
El orientador, con amplia experiencia editorial, pidió una secuencia **macro → micro → literatura crítica → teoría referenciada → método explicado por fluxogramas → análisis de resultados → conclusiones**. Se adopta como estructura principal:

### 1. Introdução
Contextualizar de lo macro a lo específico; diversidad de configuraciones y desafíos de despacho temporal; necesidad de herramientas reconfigurables y rastreables; problema científico; objetivo; dos contribuciones equivalentes; adelanto breve de los dos contextos evaluados. Evitar frases genéricas, grandilocuencia y números innecesarios.

### 2. Revisão bibliográfica
**No confundir con teoría.** Para cada trabajo seleccionado: qué investigó, cómo lo hizo, qué aportó y qué limitación/lacuna pertinente permanece. Citar especialmente los antecedentes principales utilizados para diseñar SEEDS2. No inventar lacunas ni forzar críticas. Concluir con posicionamiento específico de la contribución de integración de SEEDS2.

### 3. Embasamento teórico
Presentar los conceptos y formulaciones consolidados **con referencias comprobables**, sin repetir toda la implementación. Subestructura preliminar:
- **3.1 Modelagem fotovoltaica** — fundamento, formulación de referencia y alcance.
- **3.2 Modelagem eólica** — fundamento, formulación de referencia y alcance.
- **3.3 Modelagem do armazenamento em baterias** — energía/SOC, eficiencias y restricciones relevantes.
- **3.4 Modelagem da célula a combustível PEMFC** — citar obligatoriamente el trabajo propio *Desenvolvimento Computacional e Estimação de Parâmetros de uma Célula a Combustível Tipo PEM*, publicado en ENCOM 2026, DOI **10.5281/zenodo.22978126**; comprobar título bibliográfico exacto, alcance y correspondencia con el modelo de SEEDS2 antes de atribuir derivación directa.
- **3.5 Fundamentos de otimização MILP**.
- **3.6 Controle preditivo baseado em modelo (MPC)**.
- **3.7 Coordenação hierárquica e planejamento energético**.
No dedicar sección extensa a tecnología térmica si no aporta a las aplicaciones/tesis; comprobar si necesita mención de alcance. Teoría consolidada **justifica elección** pero **no valida automáticamente** el código ni sustituye validación experimental. Diferenciar verificación numérica, validación del modelo y evaluación del sistema.

### 4. Desenvolvimento do método
**Corazón original del trabajo.** Organizar por fluxogramas y explicar bloque por bloque qué recibe, qué hace y qué entrega, como pidió el orientador. Describir arquitectura efectiva de SEEDS2; catálogos, gestor, modelos, escenarios, datos, integración, persistencia y resultados; explicar el EMS real, función objetivo, balances, restricciones, planificación de largo plazo, valor futuro aproximado, MPC, ejecución, estados y auditoría. Evitar duplicar fundamentos de la sección 3. Incluir aquí la metodología de evaluación y diseño de los dos estudios, con una subsección específica si conviene. **El índice interno se cerrará solo después de la auditoría.** Distinguir modelos físicos detallados de envolventes de despacho.

### 5. Resultados e discussão
Dos estudios, no cinco. Mostrar qué se observa y **analizar por qué** ocurre y qué evidencia proporciona; no narrar el contenido visible de las curvas. Separar efectos de composición física de efectos de estrategia EMS. Cualquier alegación de beneficio específico de jerarquía requiere comparación controlada con configuración física idéntica. Gráficos claros, legibles, autocontenidos, unidades y señales correctas, interpretación sucinta; no capturas de pantalla decorativas.

### 6. Conclusões
Responder al objetivo; sintetizar las contribuciones demostradas; reconocer limitaciones reales; último párrafo: trabajos futuros. Directo, sin resultados nuevos ni promesas no sustentadas.

### 7. Referências
Seguir normativa de la plantilla/revista oficial; completar autores, año, título, fuente, volumen/páginas/DOI cuando corresponda. Revisar metadatos; evitar s/d, s/n o referencias incompletas sin justificación. **La bibliografía es sección final, no una séptima contribución técnica.**

## 4. Principio de figuras
**«Las figuras nacen de las preguntas científicas, no al revés».** Cada figura debe sostener un argumento necesario. No usar capturas de UI como sustituto de evidencia; pueden aparecer solo cuando demuestran una capacidad científica específica. El texto interpreta tendencias, decisiones, límites y mecanismos que no son evidentes a simple vista; no repite coordenadas del gráfico.

Candidatos sujetos a selección: arquitectura y flujo de ejecución; coordinación de horizontes; trazas energéticas industriales; SOC y potencia de batería; comparación de costos/indicadores; evidencia controlada del EMS; reparto PEMFC/FV/BESS embarcado; SOC y H₂; consistencia y trazabilidad. **No son nueve figuras obligatorias.**

## 5. Trabajos futuros ya identificados
Mejorar la facilidad de uso mediante análisis automático de la microrred configurada y **recomendación fundamentada** de discretización temporal, paso/steps, horizontes, tolerancias y parámetros adecuados, con validación y advertencias. Reducir intervención manual y errores de configuración. No afirmar que estas capacidades ya existen. Incorporar otras limitaciones reales que revele la auditoría, priorizadas por impacto.

## 6. Identidad autoral y disciplina editorial
Portugués brasileño, voz impersonal, razonamiento progresivo, decisiones justificadas, precisión terminológica y brevedad. Seguir el paquete de identidad autoral (`WA0040`) al redactar. Evitar introducciones genéricas, superlativos, frases vacías, enumeraciones innecesarias, repetición y «marcadores de IA». **No hacen falta todos los parámetros en todas las secciones:** solo los imprescindibles para el argumento y reproducibilidad, en su lugar correcto.

**Auditor sin piedad:** cuestionar cada afirmación sin evidencia, cada ecuación irrelevante, cada figura sin pregunta y cada redundancia; proponer corrección concreta. No ser hostil ni confundir severidad con exceso de texto. No validar por complacencia.

## 7. Auditoría técnica pendiente y estado
Claude realiza auditoría **read-only** del `main` posterior a PR #37, commit informado `507a4bd598bf07cad62b78f038a32e8b96201780`, con seis auditores paralelos y suite de 2.483 tests. Se interrumpió por límite de uso; **no hay informe final confirmado**. Los tres ZIP de referencia no estaban en su sesión y deberán adjuntarse. Hallazgos preliminares por confirmar: jerarquía y PCC incorporados después de la propuesta inicial; renovable realizada igual a prevista en una ruta de integración V2; dependencias cruzadas entre paquetes. No convertir hallazgos preliminares en defectos probados.

Entregables esperados: `SEEDS2_AUDITORIA_FINAL.zip` (arquitectura, EMS, trazabilidad, riesgos, propuesta versus implementación, nuevo guion) y `SEEDS2_FLUXOS_OPERACIONAIS_AUDITORIA_FINAL.zip` (Markdown por flujo: app, gestor, escenarios, modelos, optimizador, jerarquía, MPC, gráficos, resultados, persistencia, fallas, etc., con pasos, decisiones, bucles, contratos, referencias al código y nodos para diagramación).

**Orden de trabajo aprobado:** recibir ZIP → auditar críticamente los hallazgos → consensuar índice definitivo → seleccionar y dibujar fluxogramas → escoger/producir figuras → escribir en plantilla oficial → revisar evidencias, referencias y consistencia. No cambiar código para forzar el artículo; adaptar el artículo al software real. No afirmar que la auditoría está cerrada antes de revisar sus pruebas.

## 8. Preguntas que siguen abiertas
- ¿Qué rutas y capacidades del software están verificadas en el commit final?
- ¿Qué afirmaciones causales sobre decisiones EMS respaldan logs/ablaciones?
- ¿Qué hipótesis, límites y aproximaciones deben aparecer explícitamente?
- ¿Qué ecuaciones son esenciales en el cuerpo del artículo y cuáles van a apéndice?
- ¿Qué diagramas y gráficos maximizan información por espacio?
- ¿Cuál es la plantilla oficial definitiva y sus reglas editoriales?
- ¿Cuáles son los resultados y referencias finales verificados?

## 9. Regla de actualización
Cuando la auditoría cambie una descripción, registrar **decisión anterior → evidencia nueva (archivo/función/commit) → decisión editorial nueva → impacto en el manuscrito**. No reescribir la historia como si todas las funciones hubieran estado previstas desde el inicio.