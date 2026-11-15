# Estrategias iniciales de búsqueda científica — inglés

Son **consultas semilla**, no un conjunto exhaustivo. Work debe adaptarlas a la sintaxis de cada base, registrar filtros y usar snowballing. En WoS, un ejemplo general es `TS=(...)`; en Scopus, `TITLE-ABS-KEY(...)`; Google Scholar admite consultas más cortas. No afirmar que una consulta fue ejecutada si no lo fue.

## 1. Plataformas similares SEEDS2 — prioridad P1
1. `("microgrid" OR "hybrid energy system") AND ("modular simulation platform" OR "modular framework" OR "configurable platform") AND (optimization OR "energy management")`
2. `microgrid "plug-and-play" "energy management system"`
3. `microgrid "open source" "simulation" "optimization" framework`
4. `"energy system" platform "component-based" microgrid`
5. `"multi-energy" "simulation platform" "optimization" modular`
6. `"microgrid modeling" "software architecture" reproducibility`
7. `"microgrid" "configuration management" "device models" simulation`
8. `"microgrid management" "scientific software" modular`

## 2. EMS jerárquico y optimización — P1/P2
9. `"hierarchical energy management" AND microgrid AND (MILP OR MPC)`
10. `"long-term" "short-term" "model predictive control" microgrid`
11. `"multi-timescale" "energy management" "battery" microgrid`
12. `"receding horizon" "mixed integer" "microgrid" scheduling`
13. `"two-layer" "energy management" "microgrid" prediction`
14. `"terminal cost" "model predictive control" "battery" microgrid`
15. `"value function" "energy storage" "microgrid" scheduling`
16. `"cost-to-go" "storage" "short-term dispatch"`
17. `"future value" "energy" "hierarchical" storage scheduling`
18. `"marginal value of stored energy" "battery"`
19. `"rolling horizon" "unit commitment" "fuel cell" storage`
20. `"MPC" "energy storage" "time-of-use tariff" industrial`
21. `"hydrogen" "fuel cell" "mixed integer linear programming" microgrid`
22. `"piecewise linear" "fuel cell" "optimization"`
23. `"on off" "ramp limits" "minimum up time" microgrid MILP`
24. `"photovoltaic battery" "MILP MPC" comparative study`

## 3. Célula de combustible PEMFC / H₂ — P0/P2
25. `"Otekon" "PEMFC"`
26. `"Otekin" "proton exchange membrane fuel cell"`
27. `"fuel cell" "polarization curve" "hydrogen consumption" model`
28. `"PEMFC" "Nernst" "activation losses" "ohmic losses" "concentration losses"`
29. `"PEMFC" "power hydrogen consumption" model`
30. `"fuel cell" "piecewise linear" "hydrogen consumption" MILP`
31. `"PEMFC" "ramp rate" "start-up" "minimum load"`
32. `"shipboard" "PEMFC battery" "energy management"`

**Nota:** «Otekon» es un nombre suministrado por el usuario y puede estar mal escrito. Verificar en el código la referencia exacta ANTES de atribuir autor o artículo.

## 4. Batería y generación renovable — P0/P2
33. `"battery energy storage" "SOC" "charge discharge efficiency" discrete time`
34. `"battery" "mixed-integer linear" "charge discharge exclusivity"`
35. `"battery" "terminal state" "model predictive control" microgrid`
36. `"PV" "irradiance temperature" "power output" validated model`
37. `"photovoltaic module" "single diode" "temperature" "irradiance"`
38. `"photovoltaic" "inverter efficiency" "microgrid" modeling`
39. `"wind turbine power curve" "interpolation" "manufacturer" model`
40. `"wind turbine" "air density correction" "power curve"`
41. `"Jensen wake model" "Park model" wind farms`
42. `"wind turbine" "Werle" "wake" model`

**Advertencia:** solo incorporar modelos wake o diodo si realmente están presentes en el código; de lo contrario serán antecedentes o trabajos futuros.

## 5. Embarcación autónoma y microrred industrial — P1/P2
43. `"all electric ship" "hybrid energy management" "PEMFC" battery`
44. `"shipboard microgrid" "hydrogen fuel cell" "battery" isolated`
45. `"maritime microgrid" "model predictive control" hydrogen`
46. `"industrial consumer" "time of use" photovoltaic battery "energy management"`
47. `"representative industrial load profile" Brazil distribution`
48. `"COPEL" "curva típica" "consumidor" tarifa`
49. `"PV battery" "peak shaving" "electricity purchase cost" industrial`

## 6. Software científico y validación — P3
50. `"scientific software" "reproducibility" "versioned datasets" energy`
51. `"scientific workflow provenance" "computational experiment"`
52. `"energy systems modelling" "reproducible research"`
53. `"Pyomo" "optimization modeling" paper`
54. `"HiGHS" "linear optimization software" publication`
55. `"Streamlit" "scientific web application" energy`
56. `"scenario management" "microgrid simulation" reproducibility`
57. `"open source energy system modeling" "verification validation"`
58. `"model predictive control" "baseline comparison" "reproducibility" microgrid`

## 7. Ampliación avanzada
- Obtener al menos 3 revisiones recientes fuertes de microgrids/EMS, extraer su bibliografía y seguir sus citantes.
- Buscar autores y DOI exactos de modelos presentes en repositorio, no solo títulos de categorías.
- Buscar por ecuaciones, constantes y parámetros característicos, cuando sea legítimo y técnicamente posible.
- Separar documentos oficiales de herramientas/software de la evidencia académica peer-reviewed.
- Revisar artículos que cuestionen la superioridad económica de EMS jerárquicos o la precisión de modelos simplificados.

## Plataformas para iniciar
- Web of Science: https://www.webofscience.com/
- Google Scholar: https://scholar.google.com/
- Scopus: https://www.scopus.com/
- Crossref Search: https://search.crossref.org/
- OpenAlex: https://openalex.org/
- Semantic Scholar: https://www.semanticscholar.org/
- IEEE Xplore: https://ieeexplore.ieee.org/
- ScienceDirect: https://www.sciencedirect.com/
- ResearchGate: https://www.researchgate.net/
- DOAJ: https://doaj.org/
