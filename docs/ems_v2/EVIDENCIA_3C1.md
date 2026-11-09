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

**Cierre de la auditoría del PR #14 (A-01..A-03, base `540ac1b`):**

| Comando | Resultado |
|---|---|
| `… pytest tests/ems_v2/test_ems_v2_3c1_auditoria_pr14.py` | **36 passed** (A-01: 21, de ellos 1 con HiGHS · A-02: 4, con HiGHS · A-03: 11) |
| Los 7 archivos `tests/ems_v2/test_ems_v2_3c1_*.py` (casos A–L + A-01..A-03) | 146 passed (28 + 36 + 7 + 30 + 32 + 6 + 7) |
| `… pytest tests/ems_v2 -q` (3A + 3B-P + 3C-0 + 3C-1) | **681 passed** (= 645 + 36) |
| ídem con Pyomo/HiGHS bloqueados | **494 passed, 14 skipped** (los 5 nuevos dependientes del solver se saltan con `could not import 'pyomo'`) |
| `… pytest tests/ -q` (suite completa) | **1135 passed, 7 warnings, 128 subtests** (435 s) = 1099 + 36 |

**Segunda auditoría del PR #14 (B-01/B-02, base `20243aa`):**

| Comando | Resultado |
|---|---|
| `… pytest tests/ems_v2/test_ems_v2_3c1_auditoria_pr14_b.py` | **18 passed** (B-01: 9 · B-02 vínculo: 6 · B-02 evidencia: 3, con HiGHS) |
| Los 8 archivos `tests/ems_v2/test_ems_v2_3c1_*.py` | 164 passed (28 + 36 + 18 + 7 + 30 + 32 + 6 + 7) |
| `… pytest tests/ems_v2 -q` | **699 passed** (= 681 + 18) |
| ídem con Pyomo/HiGHS bloqueados | **509 passed, 17 skipped** (los 3 nuevos de evidencia se saltan explícitamente) |
| `… pytest tests/ -q` (suite completa) | **1153 passed, 7 warnings, 128 subtests** (429 s) = 1135 + 18 |

**Corrección final B-03 (base `1b953db`):**

| Comando | Resultado |
|---|---|
| `… pytest tests/ems_v2/test_ems_v2_3c1_auditoria_pr14_c.py` | **18 passed** (13 adulteraciones re-selladas + intacta + declaración + integridad del registro + límite SHA ≠ firma + coherencia con metadatos) |
| Los 9 archivos `tests/ems_v2/test_ems_v2_3c1_*.py` (casos A–L, A-01..A-03, B-01..B-03) | **182 passed** |
| `… pytest tests/ems_v2 -q` | **717 passed** (= 699 + 18) |
| ídem con Pyomo/HiGHS bloqueados | **509 passed, 18 skipped** (el archivo B-03 se salta entero con `could not import 'pyomo'`) |
| `… pytest tests/ -q` (suite completa) | **1171 passed, 7 warnings, 128 subtests** (432 s) = 1153 + 18 |

Los tests B-02 de evidencia se adaptaron a la API en tres fases (conteúdo → hashes en el registro → anexo); sus
aserciones se mantienen (acceso a los campos por `anexo.conteudo`).

Datos de prueba corregidos (no se relajó ninguna validación): en los bloques `quantidade = 2` de A-03 el agregado del
registro venía de la fixture de una unidad (10 kW) y una prueba declaraba #1 ON a 12 kW; ahora cada prueba DECLARA
el agregado coherente (`_cenario(..., agregado=12.0)`). Los helpers de declaración construyen el vínculo con
`vinculo_do_instantaneo(inv, cen)` (B-02).

Los tests 3C-1 que construían `ExecutorAlgebricoCommitment3C1` sin fuente de disponibilidad se actualizaron para
DECLARARLA (Caso J: serie `observada` en la realización; casos de memoria/ponte: `estatica_declarada` con procedencia
y justificativa). Ninguna aserción fue relajada: el caso D, con `observada` y sin serie realizada, pasó a fallar por
`disponibilidade_realizada_ausente` (comportamiento correcto) y se le declaró la fuente estática.

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

## 6. Reproducción de los defectos del PR #14 sobre `540ac1b` (antes de corregir)

Script ad hoc que carga `ems_v2/ponte/compromisso.py` de `540ac1b` (copiado temporalmente, luego borrado) y aplica
las mismas entradas de `test_ems_v2_3c1_auditoria_pr14.py`:

| ID | Entrada | Resultado en `540ac1b` | Resultado corregido |
|---|---|---|---|
| A-01 | Caso A, consigna ON, entorno **sin** `syn-ter\|disponibilidade` | `exequivel = True` (verificación omitida) | `erro_dados` / `disponibilidade_realizada_ausente` (fuente `observada`) |
| A-01 | ídem con disponibilidad 0,5 | `falha = "inexequivel"` (rotulado como físico) | `falha = "dados"` / `disponibilidade_realizada_invalida` |
| A-02 | PEMFC con arranque y parada (m_SU = 0,002, m_SD = 0,001 kg) | solo la contabilidad 3C-0: H₂ R$ 0,30 (sin eventos) | R$ 0,33 = 10 × (0,03 + 0,003); eventos R$ 2,0 |
| A-03 | `#1` válido, `#2` declarado dos veces (OFF y luego ON a 15 kW), `#7` inexistente | entrada **aceptada**; `#2` = ON a 15 kW (la última sobrescribió), `#7` ignorado | `condicao_unidade_duplicada` + `condicao_unidade_uid_desconhecido`; ninguna entrada |

## 7. Reproducción de los defectos B-01/B-02 sobre `20243aa` (antes de corregir)

Script ad hoc sobre el código de `20243aa` (mismas entradas de `test_ems_v2_3c1_auditoria_pr14_b.py`):

| ID | Entrada | Resultado en `20243aa` | Resultado corregido |
|---|---|---|---|
| B-01 | Bloque q = 2; escenario `unidades_ligadas = 1`; #1 ON y #2 ON | **aceptada** | `unidades_ligadas_incoerente`; ninguna entrada (rechazo previo a la proyección) |
| B-01 | Potencia del registro 10 kW; #1 ON 25 kW, #2 OFF | **aceptada** | `potencia_agregada_incoerente` |
| B-02 | Declaración hecha para la versión 1 aplicada a la versión 2 del mismo escenario (mismo UID) | **aceptada** | `declaracao_de_outra_versao_do_cenario` |
| B-02 | Declaración aplicada a otra revisión del inventario (mismo inventario físico) | **aceptada** (sin constatación) | `declaracao_de_outra_revisao_do_inventario` |
| B-02 | Fuente de disponibilidad estática usada en la ejecución | no aparecía en ninguna evidencia persistida | valor, procedencia y justificativa en `AnexoExecucao3C1`, ligado por hash al registro |

## 8. Reproducción del defecto B-03 sobre `1b953db` (antes de corregir)

Script ad hoc con la cadena PEMFC de `test_ems_v2_3c1_auditoria_pr14_b._cadeia` (fuente estática), código de
`1b953db`: evidencia válida y sellada; luego cada campo alterado y el anexo **re-sellado** con `selar_anexo_3c1`:

| Campo alterado (anexo re-sellado) | `verificar_anexo_3c1` en `1b953db` | Tras B-03 |
|---|---|---|
| ninguno (íntegro) | `[]` | `[]` |
| `disponibilidade_efetiva[0].valor` 1 → 0 | `[]` (**aceptado**) | `conteudo_anexo_divergente` |
| `detalhe_h2[0].massa_eventos_kg` 0,003 → 0 | `[]` (**aceptado**) | `conteudo_anexo_divergente` |
| `eventos_aplicados` partidas 1 → 0 | `[]` (**aceptado**) | `conteudo_anexo_divergente` (+ `anexo_eventos_incoerentes`, `anexo_h2_incoerente`) |
