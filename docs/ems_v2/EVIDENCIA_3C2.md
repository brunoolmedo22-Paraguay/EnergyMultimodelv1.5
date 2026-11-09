# Piso 3C-2 — Evidencia de pruebas y regresión (entregable N)

Entorno de esta sesión: Python 3.13.18 · Linux x86_64 (contenedor, 4 CPUs) · Pyomo 6.10.1 · highspy/HiGHS 1.15.1 ·
Streamlit 1.66.1 (`pip install -r requirements.txt -r requirements-ems_v2.txt pytest`). Base: `main` `55440f4`
(merge del PR #14). Todas las ejecuciones con `PYTHONDONTWRITEBYTECODE=1` y `-p no:cacheprovider`.

Simulación causal de lazo cerrado **algebraica** sobre fixtures sintéticas — **no es validación física**, ni control
de equipos, ni prueba de tiempo real.

## 1. Línea de base (antes de cualquier cambio)

| Comando | Resultado |
|---|---|
| `python -m pytest tests/ems_v2 -q` (en `55440f4`) | **717 passed** (= HANDOFF tras B-03) |

## 2. Pruebas nuevas del Piso 3C-2

| Archivo | Tests | Solver | Cubre |
|---|---|---|---|
| `test_ems_v2_3c2_contrato.py` | 19 | no | configuración sin defectos, malla (m ≤ N, H_f), fallas (sin contingencia; clases solo interrumpir), aceptación (sin incumbente/rechazado/no óptimo fuera de política), cronograma (último bloque), políticas terminales, reloj monotónico, capacidad M23 |
| `test_ems_v2_3c2_observacoes.py` | 8 | no | K6: aceptadas/instantáneo por recepción, inválidas (incl. recibida antes del fin), otra microrred, duplicados, secuencia, revisiones y conflictos, cortes sellados y recepción retroactiva, realización observada y barrera C-02, exportar/importar/adulteración |
| `test_ems_v2_3c2_previsao.py` | 7 | no | claves por UID, vínculo informacional, emisión tardía, cobertura/resolución/UID, oráculo solo en ablación, independencia, reemisión al cambiar la información |
| `test_ems_v2_3c2_laco.py` | 16 | **no** (dublé de regla analítica aprobado por el auditor 3C-1) | valores analíticos de varias ventanas, sin doble conteo, una ventana = flujo directo, último bloque, inexequible sin recorte, faltante y parada segura, otra microrred, inválidas/duplicadas en el canal, **modo 2** (pausa C-02 y reanudación; plazo vencido ⇒ suspensión), identidad, cadena/vínculo de checkpoint, reproducción, persistencia y reanudación, ponto adulterado, gravación exclusiva |
| `test_ems_v2_3c2_milp.py` | 29 | **HiGHS real** | E1–E8 y la batería obligatoria (ver `MATRIZ_3C2.md`) |
| `test_ems_v2_3c2_isolamento.py` | 4 | no | núcleo MPC sin Pyomo/HiGHS/Streamlit/`seeds2` al importar; solver solo por el adaptador con import tardío; **ningún archivo existente modificado desde `55440f4`**; `ADICOES_3C1` intacto |
| **Total** | **83** | | |

## 3. Resultados

| Comando | Resultado |
|---|---|
| `python -m pytest tests/ems_v2/test_ems_v2_3c2_*.py -q` | **83 passed** (≈ 6 s) |
| `python -m pytest tests/ems_v2 -q` | **800 passed** (≈ 19 s) = 717 + 83 |
| `PYTHONPATH=<bloqueador> python -m pytest tests/ems_v2 -q -rs` con Pyomo/HiGHS **bloqueados** (`sitecustomize` que hace fallar `import pyomo/highspy`) | **563 passed, 19 skipped** (los saltos dicen `could not import 'pyomo'`; el único archivo 3C-2 saltado es `test_ems_v2_3c2_milp.py`; el lazo sin solver corre) |
| `python -m pytest tests/ -q` (suite completa) | {FULL} |
| `python -m ems_v2.mpc.evidencia docs/ems_v2/EVIDENCIA_3C2_EJECUCION.md 5` | ver [`EVIDENCIA_3C2_EJECUCION.md`](EVIDENCIA_3C2_EJECUCION.md) (E1–E8 auditados, comparaciones, intervención, campaña de tiempos con n declarado) |

Las aserciones de los 717 tests anteriores no fueron modificadas. Las guardias históricas (3A, 3B-P, 3C-0 con
`ADICOES_3C1`) siguen pasando sin ajuste.

## 4. Valores verificados de forma independiente

- **NS (sin solver):** R$ 0,175 / 0,15 / 0,15 por ventana y R$ 0,475 total, energía final 18,5 kWh — calculados a mano
  en la docstring de `test_ems_v2_3c2_laco.py` y recomputados por `auditoria.custo_realizado_independente`.
- **E2 (HiGHS):** R$ 1,7 / 2,0 / 6,125 / 3,075 = 12,9 — calculados a mano a partir del despacho aplicado (docstring de
  `test_ems_v2_3c2_milp.py`), recomputados por la auditoría (PWL propia en `Fraction`).
- **Una ventana:** el MPC con N = m = K_M reproduce exactamente `resolver_3c1` + `executar` + `contabilidade_realizada_3c1`
  (R$ 18,7).
- **E5:** u = [0,0,0,1,1,1,0,0], memoria ejecutada 900 s y 1800 s al inicio de τ_4 y τ_5; la auditoría recalcula las
  permanencias en toda la misión (incluida la memoria inicial).

## 5. Limitaciones de esta evidencia

- Una máquina, muestras pequeñas: los tiempos son indicativos, sin restricción operacional validada.
- Sin Windows (heredado K5).
- Fixtures sintéticas: ninguna microrred real del catálogo ejecuta el MPC (brechas 3C-0/3C-1/3C-2).
