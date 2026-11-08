# Casos sintéticos de referencia y puertas de auditoría

**No son resultados ejecutados**. Son respuestas derivadas analíticamente para que Claude implemente tests y, en 3B, compruebe un solver independiente. Datos numéricos en este archivo son *fixtures sintéticas*, no parámetros físicos calibrados de SEEDS2.

| ID | Caso | Resultado matemático | Etapa |
|---|---|---|---|
| A01 | Potencia 60 kW por 60 intervalos de 1 min | Energía 60 kWh; 61 fronteras | 3A |
| A02 | Potencia 10 kW en 1 min | 0.1666666667 kWh | 3A |
| A03 | BESS 100kWh, e0=60kWh, descarga 9kW, ηd=.9, 1h | e1=50kWh; SOC=.50 | 3A |
| A04 | BESS 100kWh, e0=60kWh, carga 10kW, ηc=.9, 1h | e1=69kWh; SOC=.69 | 3A |
| B01A | FV potencial 100kW, a=0, P_used=0, 1h, c_curt=.5 | C_oper=0, E_indisp=100kWh, costo=0 | 3A |
| B01B | FV potencial 100kW, a=1, P_used=80kW, 1h, c_curt=.5 | C_oper=20kW, E_curt=20kWh, costo=10R$ | 3A |
| A05-FEAS | FV 20kW, L=10kW, BESS carga 10kW, ηc=.9, 1h | balance 0; e aumenta 9kWh; no inferir optimalidad | 3A |
| A05-OPT | mismo + e0=50/100kWh, c_curt=1R$/kWh, c_thr=0, terminal none, no dumping | óptimo esperado carga 10kW, C_oper=0, e1=59kWh | 3B |
| A06 | PEMFC PWL sintética (10kW,.7kg/h)-(20kW,1.1kg/h) a 15kW | q=.9kg/h, m=.015kg/1min; ON en 5kW inválido | 3A ref / 3B solver |
| A07 | Gen forzado ON Pmin=20kW, demanda=5kW sin BESS ni dump | inviabilidad en servicio duro, no verter potencia ficticia | 3B |
| A08 | Gen útil máx 5kW, L=10kW por 1h | χ=0: inviable; χ=1: ENS=5kWh | 3B |
| B05A | PEMFC STARTUP qmode=.02kg/h durante 10min, no ON | masa=.003333333kg, sin doble contar m_SU | 3C/multimodo |

## Rechazos explícitos 3A

- Duplicados UID, NaN/Inf, horas locales sin zona/offset, timestamps no monótonos, resolución incompatible no declarada.
- Eficiencia ≤0 o >1; SOC inicial fuera [SOC_min,SOC_max]; potencia media en bus mezclada con potencia bruta sin conversión declarada.
- Carga crítica sin permiso de desconexión tratada como `ell>0`.
- `A_pot=0` insertado automáticamente por dato de irradiancia ausente.
- `a=0` y `C_oper>0` etiquetado como curtailment operativo.
- BESS satura SOC mediante `clip` ocultando violación.
- 60 intervalos + instante final interpretados como 61 integraciones.

## Puerta G3A

- `TimeGrid` N/N+1 verificado; energía y costos dimensionales.
- Fixtures A01–A04 y B01 pasan con resultados analíticos; A05-FEAS y A06 reportados como referencias no resueltas por un MILP.
- Auditor independiente rechaza mutaciones explícitas.
- Catálogo M01–M23 completo con pruebas de cobertura declarativa.
- Legacy intacto y suite existente sin regresiones atribuibles al PR.
- PR abierto, commit, logs y matriz de evidencia. No iniciar 3B sin revisión.

## Puerta G3B (posterior)

- Pyomo+HiGHS resuelve A01–A08 bajo modelo/magnitudes definidas; distingue optimal, feasible time-limit y no solution.
- PWL sintética exacta y dominio ON/OFF; balance, SOC, terminal, costos reconstruidos independientemente.
- Reporte reproducible de versiones, time limits, MIP gap y hardware.
- Sin integración UI y sin datos físicos aceptados por simple existencia del archivo.
