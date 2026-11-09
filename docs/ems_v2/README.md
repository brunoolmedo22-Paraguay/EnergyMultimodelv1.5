# `ems_v2` — Fundaciones del EMS MILP–MPC (Piso 3A), primer MILP ejecutable (Piso 3B-P), commitment dinámico (Piso 3C-1), MPC recedente (Piso 3C-2) y red/intercambio (Piso 3C-3)

> **Piso 3C-3 (red, intercambio económico y recurso explícito de equilibrio, perfil `v1.1-3C-3`):** `ems_v2/rede/`
> (núcleo solo biblioteca estándar) declara el **PCC** (modo conectado × isolado declarado, sentidos permitidos, límites
> contratados por intervalo, disponibilidad, medidores), **perfiles tarifarios** por bloques con naturaleza, revisión,
> emisión y hash, y la política económica; `ems_v2/milp/{modelo,solver,resultado,evidencia}_3c3.py` resuelven el MILP
> con importación/exportación exclusivas (binaria con coeficientes = límites contratados) y balance M02 extendido y
> verificado término a término (`resolver_3c3`); el **auditor independiente** compone el auditor 3C-1. En ejecución,
> el **intercambio programado** se distingue del **realizado**: política de ajuste local del PCC declarada (límites,
> disponibilidad, sentidos, medición como evidencia), inyección renovable limitada por el potencial observado y
> liquidación realizada separada (gasto de importación × crédito de exportación). `ControladorMPCConectado` extiende
> el MPC 3C-2 por puntos de extensión mínimos del orquestador (E1–E8 idénticos). Modelo **algebraico agregado** (no
> flujo AC, no control primario, tarifas sintéticas). Ver [`FORMULACAO_3C3.md`](FORMULACAO_3C3.md),
> [`MATRIZ_3C3.md`](MATRIZ_3C3.md), [`EVIDENCIA_3C3_EJECUCION.md`](EVIDENCIA_3C3_EJECUCION.md),
> [`BRECHAS_3C3.md`](BRECHAS_3C3.md) y [`TRANSICAO_3C3_3C4.md`](TRANSICAO_3C3_3C4.md).

> **Piso 3C-2 (MPC de horizonte recedente, M23):** `ems_v2/mpc/` (núcleo solo biblioteca estándar) ejecuta misiones
> de varias ventanas: reloj τ_k / N_k / m_k con política terminal explícita, libro de observaciones **append-only**
> (K6: tiempo físico × recepción, revisiones, conflictos, cortes sellados), previsión **reemitida y validada por
> ventana** (vínculo al instantáneo informacional), entrada 3C-1 con el estado y la memoria **ejecutados**,
> `resolver_3c1` solo por el adaptador explícito `adaptador_milp.py`, aceptación con política declarada, conciliación
> por la barrera C-02 (modos 1 y 2), registros sellados y encadenados (3C-0 + anexo 3C-1 + `RegistroJanelaMPC`),
> reanudación verificada, auditoría temporal/causal/contable independiente, métricas y comparadores. Simulación causal
> de lazo cerrado **algebraica** (no física). Ver [`FORMULACAO_3C2.md`](FORMULACAO_3C2.md),
> [`MATRIZ_3C2.md`](MATRIZ_3C2.md), [`EVIDENCIA_3C2.md`](EVIDENCIA_3C2.md), [`BRECHAS_3C2.md`](BRECHAS_3C2.md) y
> [`TRANSICAO_3C2_3C3_3C4.md`](TRANSICAO_3C2_3C3_3C4.md).

> **Piso 3C-1 (Unit Commitment dinámico, perfil `v1.1-3C-1`):** `ems_v2/compromisso/` (contrato embrulho por unidad,
> discretización exacta, memoria, preflight y **auditor independiente**, solo biblioteca estándar) y
> `ems_v2/milp/{modelo,solver,resultado,evidencia}_3c1.py` resuelven M09–M12 (transiciones y/z, rampas con p_{−1},
> límites de arranque/parada, permanencias U/D = ⌈T/Δ⌉, obligaciones heredadas, política terminal explícita) y el
> término `eventos`, con compromiso libre o parcial: `resolver_3c1(entrada_3c1, configuracao, compromisso_parcial)`.
> `resolver` (3B-P) sin cambios. Integración con la puente en `ems_v2/ponte/compromisso.py` (plan, ejecutor algébrico,
> transporte de memoria entre ventanas). Sin MPC. Ver [`FORMULACAO_3C1.md`](FORMULACAO_3C1.md),
> [`MATRIZ_3C1.md`](MATRIZ_3C1.md), [`EVIDENCIA_3C1.md`](EVIDENCIA_3C1.md), [`BRECHAS_3C1.md`](BRECHAS_3C1.md) y
> [`TRANSICAO_3C1_3C2.md`](TRANSICAO_3C1_3C2.md).

> **Piso 3C-0 (puente científico):** `ems_v2/ponte/` (contratos, solo biblioteca estándar) y `ems_v2/ponte_seeds2/`
> (lector SOLO LECTURA de microrredes reales) conectan **contractualmente** el EMS V2 con el Gestor de microrredes:
> inventario por UID con procedencia, matriz de parámetros, escenario/previsión/realización separados, plan →
> ejecución → estado con checkpoints, preflight, registro sellado (costo realizado ≠ valor futuro) e instrumentación.
> Sin integración con la UI ni el runtime. Ver [`PONTE_3C0.md`](PONTE_3C0.md).

> **Piso 3B-P:** el subpaquete `ems_v2/milp/` construye y resuelve un MILP de **una ventana** con Pyomo + HiGHS
> (`resolver(entrada, configuracao, compromisso_fixo)`), solo por API y tests. Dependencias en
> `requirements-ems_v2.txt`; formulación ejecutada, interfaz y límites en [`FORMULACAO_3BP.md`](FORMULACAO_3BP.md);
> trazabilidad en [`MATRIZ_3BP.md`](MATRIZ_3BP.md); evidencia en [`EVIDENCIA_3BP.md`](EVIDENCIA_3BP.md). El texto
> siguiente describe el Piso 3A (sigue vigente para las entradas `v1.1-3A`).

**Estado:** experimental, **sin solver**. Base: `main` = `8556b71a76dd13d279a0e0ecd8ad9bd498df72f1`.
El EMS V1.6 (`legacy_v16`, paquete `ems_integration/`) sigue siendo el **único motor operacional** de la
aplicación. Nada de este paquete es llamado por la interfaz, el Centro de Operação ni el runtime.

## Qué contiene (y qué no)

| Módulo | Responsabilidad | Ecuaciones |
|---|---|---|
| `ems_v2/units.py` | Unidades canónicas y conversiones explícitas exactas (W→kW, R$/MWh→R$/kWh, %→fracción…) | — |
| `ems_v2/provenance.py`, `parameters.py` | `Procedencia` (SourceProvenance), `Parametro` con valor normalizado + bruto + transformaciones | R46 |
| `ems_v2/timegrid.py` | `MalhaTemporal` (TimeGrid): N intervalos, N+1 fronteras, `h = Δ/60` exacto, H_f/H_o/ρ/T_M separados | M01, §13 |
| `ems_v2/series.py` | `SerieTemporal` tipada (`media_intervalo` × `amostra_instantanea`), cobertura, causalidad; **sin** remuestreo | R02, R03 |
| `ems_v2/contracts.py` | `EntradaModeloEMS` (EMSModelInput) por UID, políticas declarativas, validación con códigos, JSON canónico + SHA-256 | M02–M08, M10, §12 |
| `ems_v2/reference.py` | Cálculo de referencia **racional exacto**: energía, M07, M03-v1.1/B01, PWL en un punto, masas H2 | M01, M03-v1.1, M07, M15/M16 |
| `ems_v2/audit.py` | Auditor algebraico **independiente** (punto flotante, segundos, bisección; no importa `reference`) | M02, M03-v1.1, M04, M06–M08, M10, M16, M21-CURT |
| `ems_v2/capabilities.py` | Registro declarativo `legacy_v16` / `milp_mpc_v1` y estado por familia | — |
| `ems_v2/fixtures.py` | Fixtures sintéticas A01–A08, B01A/B, A05-FEAS/OPT, B05A con etapa | — |
| `ems_v2/catalogo/` | `simbolos_v1_1.csv` (150 símbolos) y `equacoes.json` (manifiesto revisado) | M01–M23 + v1.1 |

**No contiene:** Pyomo/HiGHS, despacho, objetivo, selector de motor, adaptador de inventario (`seeds2`), lectura
de previsiones del Piso 2B, migración de resultados, autómata multimodo, tanque de H2, diagnóstico elástico.
Solo biblioteca estándar de Python (verificado por `tests/ems_v2/test_ems_v2_isolamento.py`).

## Convenciones fijas

- Una microrred **aislada**, un **bus eléctrico equivalente**; potencias en **kW netos en el bus**.
- `P > 0` inyecta al bus; `P_carga ≥ 0` consume del bus; `P_descarga ≥ 0` inyecta.
- Energía de intervalo = potencia media × `h`; `N` intervalos `[t, t+Δ)` y `N+1` estados; el estado terminal
  **no** se integra.
- Ausente = `None` + diagnóstico (`erro`/`pendente`); nunca 0, 1, ∞ ni Big-M. Ningún parámetro físico,
  costo, eficiencia, estado inicial o política terminal tiene valor por defecto (test
  `test_campos_cientificos_sem_padrao_implicito`). Única regla fijada por política aprobada: sin dispositivo de
  descarte declarado, `D̄ = 0` (adenda v1.1; decisión D03).
- Servicio `duro` ⇒ `ℓ = 0` para toda carga; `degradado` solo con autorización explícita y clase interrumpible.
- Terminal `nenhuma` solo con justificación explícita (casos analíticos); las demás son `pendente` en 3A.

## Uso mínimo

```python
from ems_v2 import fixtures as F
from ems_v2.contracts import validar_entrada, hash_entrada
from ems_v2.audit import auditar

entrada, candidata = F.b01a()          # FV 100 kW indisponible (a = 0), c_curt = 0,5 R$/kWh
assert validar_entrada(entrada).aceito
rel = auditar(entrada, candidata)       # no resuelve nada: confiere la candidata dada
rel.aceito, rel.custos_reconstruidos, rel.kpis_reconstruidos["E_indisp_kWh"]
# (True, {'curtailment_operacional': 0.0}, {'syn-fv': 100.0})
```

## Limitaciones que deben acompañar toda evidencia (adenda v1.1)

1. Las pruebas son **sintéticas/algebraicas**; no son validación física. Ningún dato es medición de SEEDS2.
2. La optimalidad MILP (futura) será del **modelo reducido**, no de la planta no lineal.
3. Un MILP algebraicamente factible no prueba seguimiento de la PEMFC ni estabilidad.
4. Un MPC algebraico no es lazo cerrado físico hasta existir `physical_step` o checkpoints equivalentes.
5. Sin tanque de H2 no se afirma autonomía; el suministro externo es hipótesis explícita.
6. V1.6 tiene limitaciones conocidas (dossier C01–C19); su presencia no certifica despachos físicos.

Decisiones, hipótesis y riesgos: [`DECISIONES_3A.md`](DECISIONES_3A.md). Trazabilidad:
[`MATRIZ_3A.md`](MATRIZ_3A.md). Procedencia de las especificaciones: [`referencias/PROCEDENCIA.md`](referencias/PROCEDENCIA.md).
