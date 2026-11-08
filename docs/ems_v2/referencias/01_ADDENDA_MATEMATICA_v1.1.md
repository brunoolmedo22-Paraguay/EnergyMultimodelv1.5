# Adenda científica MILP–MPC v1.1 — correcciones vinculantes a Work v1.0

**Autoridad:** anula o sustituye únicamente las cláusulas identificadas; lo restante de `02_Especificacion_matematica.md` v1.0 continúa como propuesta condicionada. **Estado:** diseño para prototipo; ninguna ecuación nueva ha sido verificada empíricamente con los modelos físicos.

## A. Convenciones y alcance

- Escenario inicial: **microrred aislada, un bus eléctrico equivalente**, energía de intervalo (kW medios durante Δ), `h=Δ/60 h`, decisiones `t=0...N-1`, estados `k=0...N`.
- Potencias del balance: **netas en bus**. PEMFC: potencia neta ya descuenta BoP/conversión cuando así se caracterizó; jamás volver a aplicar eficiencias. BESS: capacidad y eficiencias corresponden a frontera declarada. Renovables: potencial frente a disponibilidad diferenciados.
- Valores faltantes: `null` + diagnóstico, nunca `0`, `1`, `∞` o Big-M arbitrario. El primer 3A usa parámetros sintéticos explícitos, no inventarios físicos.
- Magnitudes/términos de costos: convertibles a **R$ por período** mediante `h`, salvo eventos (`R$/evento`) y terminal (`R$/kWh × kWh`). Cada fórmula debe demostrar dimensionalidad.

## B01 — Sustitución de M03 y término de curtailment de M21

Definir el potencial renovable técnico **antes de disponibilidad** `A^pot_{r,t} ≥ 0 [kW_bus]`, disponibilidad efectiva exógena `a_{r,t} ∈ {0,1}` en la variante binaria inicial. Para derating fraccionario, ampliar separadamente a `a∈[0,1]` solo cuando provenga de caracterización y se declare el significado.

\[
A^{utilizable}_{r,t}=a_{r,t} A^{pot}_{r,t},\quad
P^R_{r,t}+C^{oper}_{r,t}=A^{utilizable}_{r,t},\quad P^R_{r,t},C^{oper}_{r,t}\ge0.
\tag{M03-v1.1}
\]

Pérdida **por indisponibilidad** (KPI, no decisión de curtailment):

\[
E^{indisp}_{r,t}=h(1-a_{r,t}) A^{pot}_{r,t},\quad
E^{curt,oper}_{r,t}=h C^{oper}_{r,t}.
\]

En objetivo M21 sustituir **exclusivamente** `h ∑_r c^{curt}_r C^R_{r,t}` por `h ∑_r c^{curt}_r C^{oper}_{r,t}`. No cobrar indisponibilidad como vertimiento. Si la serie fue caracterizada directamente como potencia utilizable **después de disponibilidad**, registrar `A^pot := A^utilizable` y `a=1` solamente bajo un contrato de origen explícito; no multiplicar dos veces. Tratar perfiles desconocidos/NaN como error, nunca como cero.

**Bloqueador B01:** para `A^pot=100 kW`, `a=0`, `h=1 h`, `c_curt=0.5 R$/kWh`, se exige `P^R=0`, `C_oper=0`, `E_indisp=100 kWh` y costo de curtailment operacional **R$0**. Si `a=1` y el vertimiento es 20 kW, `E_curtailed=20 kWh` y costo R$10.

## B02 — Revisión de fixture A05

**No concluir despacho óptimo a partir de balances solamente**. Diferenciar:

- **A05-FEAS (física):** carga fija 10 kW, FV utilizable 20 kW, BESS puede cargar 10 kW; terminal no vinculante; existe una solución factible `P^c=10`, `P_R=20`, `C_oper=0`; esto no implica que sea óptima para cualquier objetivo.
- **A05-OPT (económica, solo desde 3B):** un intervalo de 1 h, `c_curt=1 R$/kWh`, `c_throughput=0`, BESS inicial 50 kWh de 100 kWh, SOC permitido 0–1, potencia de carga máx. 10 kW, `η_c=0.9`, sin generación controlable, sin descarte, sin descarga simultánea y sin término terminal. `P_FV=20`, `P_load=10`. Solución óptima: `P_charge=10 kW`, `C_oper=0`, energía interna final `59 kWh` y costo de curtailment R$0. Con costos distintos podría ser óptimo verter.

La validación de A05-OPT depende de disponer de solver; en 3A se registran los datos y resultados de referencia, no se afirma haber ejecutado el solver.

## B03 — Diccionario obligatorio y control estático

Construir un registro exhaustivo de **todo símbolo realmente utilizado**, incluidos `χ_{ℓ,t}`, `P_i^sb`, `m^sb_{i,t}`, `c_t^dump`, `γ_i`, `w_ℓ`, `m^in_{h,t}`, potencias netas/brutas, modos y costos. Por símbolo especificar: `id`, indices, `parameter|variable|set|derived`, dominio, unidad, frontera/convención de signos, `optional`, `enabled_if`, origen/procedencia, ecuaciones y estado (`activo|futuro|sintético`).

El `06_CATALOGO_SIMBOLOS_v1.1.csv` es **semilla de auditoría**, no una declaración de completitud. Claude debe cerrar en 3A el inventario de M01–M23 (+ variantes) y crear una comprobación automatizada de cobertura (si no puede analizar LaTeX de modo fiable, usar un manifiesto explícito de uso por ecuación revisado por tests; no afirmar parser exhaustivo falso).

Cargas interrumpibles: `χ_{ℓ,t}∈[0,1]` representa fracción AUTORIZADA, no un interruptor eléctrico libre sin contrato; `ℓ_{ℓ,t}` es carga realmente desconectada. `w_ℓ` no prueba prioridad estricta salvo que haya niveles lexicográficos separados. `P^sb` y `m^sb` no pueden activarse sin modo standby definido, ni coexistir con un autómata que contabilice el mismo consumo.

## B04 — Puerta PWL PEMFC antes de integración física

- 3B: solo PWL **sintética** exacta; ejemplo 10kW→0.7kg/h, 20kW→1.1kg/h, a 15kW: 0.9kg/h y 0.015kg en 1min. `OFF` tiene `p=q=0`; `ON` no admite `p=5kW` cuando `Pmin=10kW`.
- Antes de conectar una curva PEMFC real al MILP en 3D: construir `q_H2_suministrado(P_neto_bus)` sobre rama de operación estacionaria, declarar temperatura, presión, utilización, límites físicos y versión/hash del modelo; dividir puntos ajuste/validación; comprobar error absoluto/relativo y subestimación del consumo. **Los umbrales de aceptación deben aprobarse antes de evaluar los datos**; no se fijan aquí sin evidencia del rango físico.
- El perfil V–I importado de ModelLab por sí solo no determina consumo de H2 ni potencia neta; bloquear capacidad incompleta.
- Validación dinámica (arranques, saturación, rampas y memoria) permanece en puerta posterior a la prueba estática.

## B05 — Variantes de costo mutuamente exclusivas

Definir explícitamente dos modos **excluyentes** por unidad:

### Variante INSTANTÁNEA (`ON/OFF`, M09–M12)

Solo cuando encendido instantáneo es una aproximación permitida o las unidades ya arrancaron con sus estados fijados. Para PEMFC, `q^{ON}_{f,t}` proviene de M14–M16 (kg/h). Masa total suministrada por intervalo:

\[
m^{inst}_{f,t}=h q^{ON}_{f,t}+m_f^{SU} y_{f,t}+m_f^{SD}z_{f,t}.
\]

La componente de combustible del objetivo es `Σ_t c_H,t m^{inst}_{f,t}`, **no** `h*c_H*m_event`. Costos eléctricos de eventos `W^{SU},W^{SD}` solo entran al balance por `W/h` si están cuantificados y no incluidos en la potencia neta; `C^{SU},C^{SD}` se desglosan como costos de evento **sin combustible ni auxiliares ya valorados**. No usar término de standby salvo modo certificado.

### Variante MULTIMODO (`OFF→S1→...→ON→...`, M20/M20b/M20c)

Con variables `m_{i,q,t}` para modo y `v_{i,q,q',t}` para arco, `u_{i,t}=m_{i,ON,t}`. La parte operativa en ON usa `p_{i,t}` y (PEMFC) `q^{ON}_{i,t}`. Para cada modo `q≠ON` declarar perfil **por intervalo** `g^{mode}_{i,q,t} [kW_bus]` (generación neta) y `a^{mode}_{i,q,t} [kW_bus]` (auxiliar no incluido), `q^{mode}_{f,q,t} [kg/h]` para PEMFC, y opcional `c^{mode,nonfuel}_{i,q,t} [R$/h]`.

El balance debe utilizar:

\[
P^{gen,total}_{i,t}=p_{i,t}+\sum_{q\ne ON}g^{mode}_{i,q,t}m_{i,q,t},\quad
P^{aux,total}_{i,t}=\sum_{q\ne ON}a^{mode}_{i,q,t}m_{i,q,t}+P^{aux,otro}_{i,t}.
\]

`P_aux_otro` solo incluye consumos separados de otra naturaleza, con origen rastreable. Masa suministrada PEMFC:

\[
m^{multi}_{f,t}=h\left(q^{ON}_{f,t}+\sum_{q\ne ON}q^{mode}_{f,q,t}m_{f,q,t}\right).
\]

Costo de combustible `Σ_t c_H,t m^{multi}_{f,t}` y costo complementario de modos `Σ_t h Σ_{i,q≠ON} c^{mode,nonfuel}_{i,q,t}m_{i,q,t}`. Costos de evento `Σ_t (C^{SU,nonenergy}_i y^{start}_{i,t}+C^{SD,nonenergy}_i z^{stop}_{i,t})` **únicamente para conceptos no ya contabilizados por combustible, auxiliares y modos**. `z^{stop}` debe definirse como el arco que inicia parada (no necesariamente salida de ON si hay standby). Contadores de arranque usan `y^{start}`, no `y^{run}`. **Excluir en esta variante** `m^{SU}y + m^{SD}z`, `W^{SU}y/h + W^{SD}z/h` y cargos duplicados si sus consumos se distribuyeron por modos. No activar multimodo sin datos.

El término económico **canónico** es la suma de generación térmica, BESS, `h*c_curt*C_oper`, servicio interrumpido autorizado, costo de combustible seleccionado según variante, costos de modo y eventos no duplicados, descarte físico real y penalización terminal registrada. No agregar indisponibilidad como curtailment.

**Prueba de no duplicación:** escenario PEMFC con `q^{mode}=0.02 kg/h` durante 10 min y sin potencia en ON, H2 total `0.02×10/60=0.003333… kg`; no añadir arbitrariamente un `m_SU` del mismo arranque. Un costo adicional legítimo debe llevar desglose y fuente.

## Política de servicio y factibilidad (bloque adicional)

- Microrred aislada de **servicio duro**: `ℓ=0` para carga crítica. Si la capacidad es insuficiente, el problema es inviable y **no existe despacho válido**. No introducir energía ficticia para hacerlo pasar.
- **Servicio degradado**: `0≤ℓ_{ℓ,t}≤χ_{ℓ,t}L_{ℓ,t}` únicamente con autorización explícita de interrupción. Registrar EENS por clase y período; si hay prioridad estricta, usar niveles lexicográficos, no pesos arbitrariamente grandes.
- **Diagnóstico elástico de contingencia**: solver separado, resultados rotulados `NO_OPERATIVO_DIAGNOSTICO`, muestra déficit mínimo posible, nunca habilita consignas.
- No existe disipación eléctrica `d_t>0` sin un dispositivo o sumidero físico definido (`D̄=0` por defecto).

## Temporalidad y decisión terminal

Separar `forecast_horizon`, `optimization_horizon`, `step_minutes`, `reoptimization_minutes` y `mission_duration`. Para prototipo: Δ=1min y ρ=1min, H=30min como **ensayo inicial provisional**, también evaluar H=5,15,60,120 posteriores. Work sugirió H=60min: **ninguna cifra está validada como óptimo**. Condición inicial real y estado de frontera N+1. Nunca devolver al SOC inicial por defecto al final de cada ventana. No inventar un κ de valoración terminal: 3A registra `terminal_policy=none` para fixtures de matemática, los experimentos económicos futuros declaran política y pesos por escrito.

## Limitaciones que deben quedar impresas en evidencias

1. La optimalidad MILP es del **modelo reducido**, no de la planta no lineal.
2. Un MILP algebraicamente factible no prueba seguimiento de la PEMFC ni frecuencia/tensión estable.
3. Un MPC algebraico no constituye lazo cerrado físico hasta disponer de `physical_step` o checkpoints equivalentes.
4. Sin tanque de H2 no afirmar autonomía; el suministro externo es hipótesis explícita.
5. V1.6 tiene limitaciones conocidas; su presencia como opción no certifica despachos físicos ante todos los escenarios.
