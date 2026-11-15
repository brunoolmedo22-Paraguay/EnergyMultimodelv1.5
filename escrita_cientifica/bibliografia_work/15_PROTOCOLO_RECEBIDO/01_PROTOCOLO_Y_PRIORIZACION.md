# Protocolo de evidencia, cobertura y priorización

## Principio rector
No confundir «referencia bibliográfica que fundamenta una teoría», «implementación equivalente a un paper», «software matemáticamente probado» y «validación empírica». Son proposiciones diferentes y requieren evidencias diferentes.

## Cobertura numérica
- Prospección aspiracional: 200–300 candidatos pertinentes deduplicados.
- Cribado de 100 o más fuentes.
- 80–120 referencias con metadatos verificables, clasificación y nivel de lectura indicado.
- Mínimo 50 fuentes de alta relevancia con metadatos y relevancia comprobados.
- 20–30 fichas profundas con evidencia exacta del texto completo si accesible.
- No inflar cifras. Diferenciar encontrado, leído en abstract, leído completo, rechazado, duplicado y fuente final.

## Doble evaluación
**P0** Fuente original del modelo/algoritmo/dataset realmente usado en código (prioridad documental superior).  
**P1** Investigación muy próxima a plataforma modular + EMS jerárquico + MICRORRED (prioridad argumentativa).  
**P2** Fundamentación tecnológica y matemática útil, aunque no sea código de fuente original.  
**P3** Reproducibilidad, software científico, herramientas y benchmarking.  
**P4** Antecedentes generales, revisión y contexto.

**F** Texto completo leído y evidencia relevante ubicada. **A** Abstract leído. **M** Solo metadatos. **X** Dudoso/excluido.

## Calidad de fuente
1. Original o seminal, revisión por pares, pertinente y verificable.
2. Revisión científica de alta calidad que establezca estado del arte/lagunas.
3. Documento técnico oficial/software primario para cuestiones técnicas concretas.
4. Preprint legítimo para señalar una línea en curso, etiquetado como no revisado.
5. ResearchGate/Scholar solo para descubrimiento, cotejar siempre editor/DOI.

## Trazabilidad de resultados
Asignar ids estables `REF0001`, `MOD0001`, `CLM0001`, `BUS0001`. Registrar fecha, URL y fuente de comprobación. Para citas identificar página, figura o número de ecuación SOLO si se consultó el texto correspondiente.

## Dedupe
Primero DOI normalizado, luego combinación de título + autores + año. Las versiones preprint y publicadas deben vincularse en una sola familia y preferir la versión editorial verificable para cita. Detectar papers erróneamente agregados como duplicados por título genérico.

## Falsos positivos a evitar
- «MPC» en un título sin MPC recedente real.
- «Hierarchical» como mera jerarquía de dispositivos en vez de coordinación temporal.
- «Plug and play» como marketing sin interfaz modular definida.
- «Digital twin» sin actualización bidireccional o acoplamiento con planta.
- «H₂ consumption» sin ecuaciones/curvas comparables al modelo PEMFC real.
- «Optimal» sin condiciones solver y función objetivo.
- «Validation» como ejemplo numérico sin experimento físico.
