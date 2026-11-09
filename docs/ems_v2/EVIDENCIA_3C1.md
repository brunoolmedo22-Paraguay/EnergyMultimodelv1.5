# Piso 3C-1 — Evidencia reproducible (entregable F)

Sintético/algebraico: **no es validación física**. Todas las corridas son de esta sesión (2026-11-09).

## 1. Entorno

| Ítem | Valor |
|---|---|
| Base | `main` `81aa09cfb5ee4bd7ff66ec6eec8fa4ccc049fc44` (= `origin/main` al iniciar) |
| Python | 3.13.18 · Linux 6.18 x86_64 (glibc 2.39) · 4 CPUs |
| Solver | Pyomo 6.10.1 · highspy 1.15.1 · HiGHS 1.15.1 · interfaz `pyomo.contrib.solver:highs` (versiones fijadas sin divergencia) |
| Otros | pytest 9.2.0 · streamlit 1.66.1 · numpy 2.2.6 |
| Configuración analítica | `CONFIG_ANALITICA` (time_limit 60 s, 1 thread, rel_gap = abs_gap = 0, semente 0) — parámetro de software |
| Instalación | `pip install -r requirements.txt -r requirements-ems_v2.txt pytest` (sin dependencias nuevas) |

## 2. Pruebas ejecutadas

| Comando | Resultado |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ems_v2 -q` en `main` antes de cambiar nada | **535 passed** (línea de base) |
| `… pytest tests/ems_v2/test_ems_v2_3c1_contrato.py` | 30 passed |
| `… pytest tests/ems_v2/test_ems_v2_3c1_auditor.py` | 28 passed |
| `… pytest tests/ems_v2/test_ems_v2_3c1_milp.py` | 32 passed (≈ 9,6 s; incluye la enumeración exhaustiva del Caso H ≈ 8 s) |
| `… pytest tests/ems_v2/test_ems_v2_3c1_continuidade.py` | 7 passed |
| `… pytest tests/ems_v2/test_ems_v2_3c1_ponte.py` | 7 passed |
| `… pytest tests/ems_v2/test_ems_v2_3c1_perfil.py` | 6 passed |
| `… pytest tests/ems_v2 -q` (rama) | **645 passed** (= 535 + 110), ≈ 17 s |
| `PYTHONPATH=<bloqueador> … pytest tests/ems_v2 -q -rs` con Pyomo/HiGHS **bloqueados** (`sitecustomize` que hace fallar `import pyomo/highspy` con `ModuleNotFoundError`) | **463 passed, 9 skipped** (todos los saltos dicen `could not import 'pyomo'`; ningún test de solver se cuenta como ejecutado) |
| `… pytest tests/ -q` (suite completa de la aplicación) | **1099 passed, 7 warnings, 128 subtests** (503 s) = 989 de `main` + 110 |

Tests anteriores **modificados**: solo las dos guardias de C-3C1-01 (`FORMULACAO_3C1.md` §9); ninguna aserción numérica,
tolerancia ni caso existente fue alterado o eliminado.

## 3. Ejecución de los casos (generada por `python -m ems_v2.milp.evidencia_3c1`)

Tabla completa (5 repeticiones por caso; mediana/máximo; **amostra pequeña, sin carácter estadístico**):
[`EVIDENCIA_3C1_EJECUCION.md`](EVIDENCIA_3C1_EJECUCION.md). Resumen de esta máquina:

| Caso | Esperado | Obtenido | Var./bin./restr. | Solver (s, mediana) |
|---|---|---|---|---|
| A transiciones | u = [0,1,1,0]; R$ 7 | igual, `aceito_otimo` | 16 / 12 / 32 | ≈ 0,008 |
| B rampa | p = [15,20,25,30]; R$ 2,5 | igual | 33 / 16 / 53 | ≈ 0,007 |
| C T_on = 45 / 0 | [1,1,1,0] R$ 5 / [1,0,0,0] R$ 0 | igual | 33 / 16 / 49 | ≈ 0,006–0,011 |
| D T_off = 45 / 0 | [0,0,0,1] R$ 3,5 / [1,0,0,1] R$ 1 | igual | 33 / 16 / 49 | ≈ 0,013 |
| E heredada OFF / ON | [0,0,1,1] R$ 10 / [1,1,0,0] R$ 5 | igual | 33 / 16 / 51 | ≈ 0,012 |
| F cumprir / residual | [0,1,1,1] R$ 5 completa / [0,0,0,1] R$ 0, 1800 s vinculante | igual | 33 / 16 / 49–51 | ≈ 0,012 |
| G 2 unidades | #1 = 1111, #2 = 0011; R$ 1 | igual | 32 / 24 / 78 | ≈ 0,006 |
| H enumeración | R$ 12,7 (enumeración exhaustiva) | igual (u, y, z, p) | 52 / 28 / 96 | ≈ 0,015 |
| I rampa / permanencia | inviable | `inviavel`, sin despacho | 16 / 12 / 38–40 | ≈ 0,004 |
| J N = 8 / 32 / 96 | aceptado | `aceito_otimo` | 65/32/105 · 257/128/417 · 769/384/1249 | ≈ 0,02 · 0,04 · 0,11 |
| PEMFC instantánea | R$ 0,33 | igual | 28 / 16 / 48 | ≈ 0,006 |

## 4. Tolerancias numéricas

Las **mismas** tolerancias provisionales del auditor 3A (D07, sin cambios): binaria 1e-6; potencia 1e-5 kW +
1e-7·P_scale; energía 1e-6 kWh + 1e-8·C_b; costo 1e-4 R$ + 1e-7·max(1, |J|); vazão 1e-6 kg/h + 1e-8·Q_max.
Corridas ON/OFF en intervalos enteros con tolerancia 0 (tras la verificación de integralidad). Coherencia
objetivo del solver × objetivo evaluado: 1e-6 relativo (igual que 3B-P). La enumeración del Caso H es **exacta**
(`Fraction`); la comparación con HiGHS usa 1e-6.

## 5. Limitaciones de esta evidencia

- Tiempos de pared en una sola máquina, pocas repeticiones; no son p95/p99 (campaña pendiente, BRECHAS_3C1 K6).
- El ejecutor es el dublê **algébrico**: la continuidad probada es contractual, no física.
- PEMFC: abstracción instantánea declarada; la curva es sintética (B04). Windows no ejecutado.
