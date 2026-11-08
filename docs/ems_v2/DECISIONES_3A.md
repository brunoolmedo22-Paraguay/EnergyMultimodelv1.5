# Piso 3A — Decisiones, hipótesis, contradicciones y riesgos

Fecha: 2026-11-08. Plan aprobado por el responsable con condiciones A–F (fiscalización del plan 3A).

## 1. Estado de `main` y diferencias con la base auditada

| Ítem | Valor |
|---|---|
| SHA base auditado por el paquete | `8556b71a76dd13d279a0e0ecd8ad9bd498df72f1` |
| `main` local y `origin/main` al iniciar | `8556b71a76dd13d279a0e0ecd8ad9bd498df72f1` |
| Diferencias de código con la base | **Ninguna** (`git log 8556b71..origin/main` vacío) |
| PR abiertos al iniciar | Ninguno (PR #6–#10 integrados) — sin riesgo de concurrencia |
| Línea de base de la suite en `main` | `454 passed, 7 warnings, 128 subtests passed` |

## 2. Decisiones aprobadas (fiscalización del plan)

1. Paquete `ems_v2/` en la **raíz**, separado de `seeds2/` (que solo adapta) y del V1.6.
2. Especificación v1.0, adenda v1.1, catálogo semilla y fixtures versionados en `docs/ems_v2/referencias/` con SHA-256.
3. **Congelamiento de salidas numéricas de V1.6 POSPUESTO**: queda registrado como **obligación previa a cualquier
   benchmark comparativo** (campañas L/A1/A2 de 3E). Ahora se preservan el SHA base y la evidencia de regresión.
4. Código y docstrings en PT-BR; documentación científica y PR en ES.

## 3. Tabla de decisiones por tema (orden ejecutiva 3A, "Antes de codificar" §3)

| Tema | Clasificación | Tratamiento en 3A |
|---|---|---|
| Bus equivalente único, potencias netas | implementable now | `FronteiraBarramento` + convención fija; otra frontera ⇒ rechazo |
| Microrred conectada a red | unsupported | `topologia_nao_suportada_3A` (pendente) |
| Servicio crítico (`ℓ = 0`) | implementable now | Servicio `duro` por defecto **declarado**; `ℓ > 0` en crítica ⇒ rechazo |
| Cargas interrumpibles / prioridad | requires owner (D01) | `degradado` exige autorización y χ; lexicográfico (M22) = futuro |
| Diagnóstico elástico de contingencia | future (3C) | No implementado; nunca emitiría consignas |
| Descarte físico (`d`) | requires owner (D03) | `D̄ = 0` sin dispositivo; con dispositivo, `D̄` con procedencia |
| Reservas / política terminal | requires owner (D02) | Solo `nenhuma` con justificación (fixtures); otras ⇒ pendente |
| Combustible externo / tanque H2 | requires owner (D04) | M18 no soportado; no se afirma autonomía |
| Parámetros de arranque PEMFC (30 s / 600 s) | requires owner (D05) | No usados; multimodo ⇒ pendente; no se infieren de V1.6 |
| Curva PWL real q(P_net) | future (3D, B04) | Clasificación `real` ⇒ `pwl_real_requer_certificacao_estatica` |
| Costos (CVU, H2, throughput, eventos) | future (3B) / requires owner | Declarables con procedencia; solo `curtailment_operacional` reconstruido |
| Tolerancias numéricas | requires owner (D07) | Propuestas del dossier como **provisionales** (`Tolerancias.status = "provisoria"`) |
| Horizonte H = 30/60 min | requires owner (D06) | Ningún horizonte se optimiza; la malla solo valida combinaciones |
| Selector de motores | future (3D, D08) | No existe; test garantiza que la app no referencia `ems_v2` |
| Remuestreo / conversión muestra→media | future | Rechazo explícito (`resolucion_incompativel`, `amostra_instantanea_como_media`) |
| Semántica de las previsiones del Piso 2B | requires owner (3D) | Ver C7 |

## 4. Resolución de contradicciones (C1–C8, aceptadas)

| ID | Contradicción | Resolución implementada | Trazabilidad |
|---|---|---|---|
| C1 | Semilla marca `alpha_b` como futuro, pero A03/A04 solo cierran con α = 1 | `hipotese_autodescarga` **obligatoria**: `nao_modelada_alpha_1` (hipótesis declarada) o `lambda_declarado` con λ | `EspecBateria.hipotese_autodescarga`; catálogo `alpha_b` |
| C2 | Semilla `a_r`, `c_curt(r,t)` vs v1.0 `a_it`, `c_r` | Un único símbolo `a` (x,t) para R ∪ B ∪ U (`id_semente = a_r`); `c_curt` indexado (r,t), constante en el tiempo en 3A | catálogo `a`, `c_curt` |
| C3 | `y`/`z` solo instantáneos; `z` choca con `z^b` | Ids únicos `y`, `z`, `z_b`, `y_run`, `z_run`, `y_start`, `z_stop`; contadores usan `y_start` | catálogo; `test_variantes_exclusivas_derivadas_e_sem_mistura` |
| C4 | v1.0 propone `to_interval_means`; la orden 3A manda rechazar | Rechazo explícito; ningún remuestreo | `series.alinhar_a_malha` |
| C5 | M05/M17 suman masa/energía por evento; B05 lo prohíbe en multimodo | Columna `variante` en catálogo y manifiesto; test impide `m_SU, m_SD, W_SU, W_SD, m_inst, y, z, C_SU, C_SD` en ecuaciones multimodo | `test_variantes_exclusivas_derivadas_e_sem_mistura` |
| C6 | `CLAUDE.md` solo prevé el EMS V1.6 | Registro de la arquitectura experimental sin cambiar reglas generales (condición E) | `CLAUDE.md` §Piso 3A |
| C7 | Series del 2B sin semántica muestra/media | No se ingieren en 3A; decisión de contrato para el adaptador de 3D | este documento |
| C8 | Tolerancias del dossier = propuestas (D07) | Usadas como provisionales; nunca ajustadas para obtener verde | `audit.Tolerancias` |

### Observación adicional (no bloquea, registrada)

- **M12 en la variante multimodo:** la v1.0 escribe M12 con `y, z` (instantánea) y dice en prosa que en multimodo
  se usa `y^run`. El manifiesto clasifica M12 como variante instantánea; la versión multimodo de las permanencias
  queda sin ecuación escrita. Se resolverá al construir M20 (3C); no altera ninguna ecuación aprobada.
- **Tolerancia de vazão/masa:** el dossier no fija tolerancia para kg/h ni kg. 3A usa una **propuesta**
  (`1e-6 kg/h + 1e-8 Q_max`; `1e-9 kg + 1e-8 m`), rotulada provisional (D07).

## 5. Registro de hipótesis simplificadoras (3A)

| ID | Hipótesis | Dónde | Efecto |
|---|---|---|---|
| H-3A-01 | Malla uniforme, `Δ` en segundos enteros; misión divisible por Δ | `timegrid` | Último intervalo corto ⇒ rechazo |
| H-3A-02 | Disponibilidad binaria `a ∈ {0,1}` | `contracts._disp` | Fraccionaria ⇒ pendente |
| H-3A-03 | `c_curt` constante en el tiempo por recurso | `PotencialRenovavel.custo_curtailment` | Índice t reservado |
| H-3A-04 | `P_scale = max(1 kW, max_t ΣL, max_t ΣA_pot, max_b P̄)` | `audit.auditar` | Define tolerancia de potencia; el dossier no detalla "P_nominal bus" |
| H-3A-05 | Violación de SOC medida en kWh equivalentes (`1e-6 × C_b`) | `audit.auditar` | Equivale a 1e-6 de fracción |
| H-3A-06 | Servicio `duro` ⇒ χ efectivo = 0 para TODA clase | `audit.auditar` | Interrumpible en servicio duro = aviso |
| H-3A-07 | Valores no exigidos por un caso y exigidos por el contrato se declaran en la fixture (p. ej. η^c en A03) | `fixtures.py` | Procedencia `sintetico` + observación; no intervienen |
| H-3A-08 | Serie potencia/disponibilidad con semántica `media_intervalo` y paso = Δ | `fixtures.py`, `series` | Sin conversión |
| H-3A-09 | Un cero declarado con procedencia es dato; solo NaN/Inf/ausente se reconoce como ausencia | `series` | Un `A_pot = 0` insertado a mano por la fuente no es detectable sin cadena de transformación |

## 6. Riesgos pendientes

1. **Conversión de frontera BESS (v1.0 §3)** no implementada: inventarios con potencia terminal se rechazan.
2. **Previsiones del Piso 2B** sin semántica declarada: el adaptador de 3D necesitará decisión del responsable.
3. **Inventario actual** sin η^c/η^d, potencias de carga/descarga separadas ni autodescarga por banco; sin
   permanencias térmicas; PEMFC sin q(P). El adaptador de 3D no podrá completar esos datos por inferencia.
4. **Tolerancias provisionales** (D07) deben aprobarse antes de la campaña confirmatoria.
5. **Congelamiento de V1.6** (decisión 3) es obligatorio antes de comparar motores.
6. `__pycache__/` versionado preexistente: la suite se ejecutó con `PYTHONDONTWRITEBYTECODE=1`.
7. El entorno del contenedor traía numpy 2.5.3 / pandas 3.0.5; se reinstaló `requirements.txt` (numpy 2.2.6,
   pandas 2.2.3) antes de medir. `ems_v2` no depende de ninguno.

## 7. Propuesta concreta para el PR 3B-P (no iniciado; requiere revisión)

1. Dependencias fijadas: `pyomo` y `highspy` con versión exacta, licencia y smoke de instalación limpia; decidir
   APPSI × interfaz `highs` por smoke (sin SOS).
2. `ems_v2/model/` (builder Pyomo) sobre `EntradaModeloEMS`: M02, M03-v1.1, M04, M06–M08, PWL M14–M16 sintética,
   térmica simple con commitment **fijado**; objetivo `J_curt` + throughput.
3. `ems_v2/solvers/highs.py`: `SolveResult` con `termination`, `incumbent_available`, `bound`, `gap`, versiones,
   tiempos; sin incumbent ⇒ sin plan.
4. Todo plan pasa por `ems_v2.audit.auditar` (sin consultar el modelo Pyomo) antes de considerarse factible.
5. Tests G3B: A01–A08 resueltos, A05-OPT óptimo único, A07 inviable en servicio duro, A08 χ=0 inviable / χ=1
   ENS = 5 kWh, estados del solver (óptimo, límite de tiempo con/sin incumbent, inviable).
6. Sin UI, sin datos físicos, sin selector.
