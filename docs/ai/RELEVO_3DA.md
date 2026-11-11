# SEEDS2 — Relevo del Piso 3D-A (integración operativa del EMS V2)

**Fecha:** 2026-11-11 · **Estado:** publicado como **PR Draft, SIN MERGE**. Desarrollo detenido por orden del responsable; la
auditoría y las correcciones siguientes se coordinan externamente. **No iniciar 3D-B ni 3D-C.**

## 1. Identificación

| Dato | Valor |
|---|---|
| Base | `main` `a636350271fa35a9e20d000f2d2121502c132913` |
| Rama | `claude/adoring-newton-jzfmfx` |
| PR | **#21 (Draft)** — https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/21 |
| Último SHA de **código** publicado | `5e2a4581c6453e19f24617d0bf1a1c148fb06e85` |
| SHA de este relevo | el HEAD de la rama: commit de documentación inmediatamente posterior a `5e2a458` (`git log -1 origin/claude/adoring-newton-jzfmfx`) |
| Checkpoints anteriores | `0da030a`, `729ea30`, `2390014`, `005eb6c` |
| `ems_v2/` | árbol Git `58cc13b6de0abff0f0cff824d469f2fb3f4ed3d7`, **idéntico a `main`** |

## 2. Archivos modificados respecto de `main`

**Nuevos — integración:** `integracao_v2/{__init__,estrategia,montagem,preflight,execucao,registro,ui}.py`.

**Modificados — `seeds2` (despacho por motor, cambios mínimos):** `seeds2/operation/scenarios.py`,
`seeds2/operation/preflight.py`, `seeds2/ui/execution_ui.py`, `seeds2/ui/archive_ui.py`.

**Tests nuevos:** `tests/piso3da_util.py` (apoyo), `tests/test_piso3da_preflight.py` (7), `tests/test_piso3da_execucao.py` (19),
`tests/test_piso3da_app.py` (4), `tests/ems_v2/piso3da_guard_policy.py` (política nominal + auditoría del diff),
`tests/ems_v2/test_piso3da_guardas.py` (8 + 1 omitido salvo `SEEDS2_AUDITORIA_PISO3DA=1`).

**Guardias ajustadas nominalmente (C-3DA-01):** `tests/ems_v2/stabilization_guard_policy.py`,
`tests/ems_v2/test_ems_v2_isolamento.py`. Ninguna guardia global fue eliminada ni debilitada.

**E2E:** `tools/e2e/{seed_piso3da.py,e2e_piso3da_v2.js,run_piso3da.sh,sabotage_v2/sitecustomize.py}`.

**Documentación:** `docs/ems_v2/INTEGRACAO_3DA.md`, `docs/ems_v2/evidencia_3da/` (registros de texto), `CLAUDE.md`,
`PARAMIJEFE.md` (Entrega 13), `docs/ai/HANDOFF.md`, este archivo.

**No tocados:** `ems_v2/`, `models/`, `h2_pemfc/`, `simulation/`, `config/`, `ems_integration/`, `orchestrator_*.py`,
`app.py`, `seeds2/operation/runner.py`, `seeds2/ui/main.py`, `seeds2/ui/operations.py`, `requirements*.txt`, el workflow de CI.

## 3. Qué opera hoy

1. **Selección explícita de motor por escenario** (`doc["engine"]`: ausente = `legacy_v16`; `milp_mpc_v1`). Un escenario V2
   nunca corre en V1.6 (el preflight V1.6 lo rechaza) ni al revés.
2. **Estrategia V2 versionada** (`doc["milp_mpc"]`): campos científicos vacíos al crear; cada declaración con procedencia;
   se guarda en la versión inmutable del escenario.
3. **Preflight V2** (`integracao_v2/preflight.py: preparar`): explica suficiencia o falta de parámetros y series, bloquea sin
   ejecutar; solver ausente ⇒ bloqueo (nunca recaída a V1.6).
4. **Runner V2** (`integracao_v2/execucao.py: submit`): misión real con Pyomo/HiGHS sobre el EMS jerárquico 3C-4; misma
   persistencia `scenario_runs` del Piso 2C; `run_uid` = `missao_uid`; progreso real por ventana; `request_id` idempotente;
   proceso muerto ⇒ `interrompida` (recuperación del runner V1.6 reutilizada).
5. **Persistencia científica** (`integracao_v2/registro.py`): `v2/registros_selados.zip` (canónico), `v2/modelo.json`,
   `v2/indice.json`, vistas `v2/{intervalos,fronteiras,janelas,planos}.csv`, `v2/coordenacoes.json`, `v2/auditoria.json`,
   `v2/preflight.json`.
6. **Reapertura sin optimizador** (`registro.verificar`): hashes, identidad, vistas regeneradas byte a byte, resumen igual al
   persistido y reauditoría integral; no importa Pyomo/HiGHS. Vale para la rodada local y para el estudio archivado.
7. **Archivo Científico**: exportar e importar el estudio con rodadas V2; consulta de sólo lectura con la misma evidencia.
8. **UI mínima** (`integracao_v2/ui.py`, despachada desde `seeds2/ui/execution_ui.py`): selector de motor, declaración,
   preflight, ejecución con progreso, página de la rodada (KPIs, dos figuras Plotly, tablas, descargas, procedencia).

**Configuración admisible:** demanda agregada crítica + hasta 2 bancos + PCC declarado (conectado con tarifa rotulada, o
aislado declarado). FV/eólica/PEMFC/térmica habilitadas y disponibles ⇒ bloqueo explicado. Sólo contexto de **ensayo**
(simulación offline algebraica; no es validación física).

## 4. Último E2E completo de navegador

`bash tools/e2e/run_piso3da.sh` sobre el código final (`integracao_v2/ui.py` y script E2E tal como están en `5e2a458`):
**106 verificaciones, exit 0** — operar 65 · reinicio tras `kill -9` 14 · tablet 8 · importar 19. Registros en
`docs/ems_v2/evidencia_3da/` (`e2e_*.log`, `run_piso3da_resumen.log`, `rodada_v2.json`).

- Microrred «Microrrede E2E 3D-A» (catálogo del Gestor), escenario «Experimento V2 pela interface» v4, `run_uid`
  `05e9cfd818f44bca801063740813cb8c`: 12 intervalos, **costo realizado R$ 50,20** = oráculo analítico (70,2 sin coordinación).
- Microrred B aislada: R$ 55,10; la rodada de A no aparece en B.
- Los UID son de un directorio de datos temporal del E2E: se regeneran en cada ejecución. Entradas **sintéticas y rotuladas**;
  no se usan las fixtures H1–H18.

## 5. Evidencia de reapertura sin reoptimización

- **Navegador:** tras recarga y tras `kill -9` + reinicio, la rodada concluida muestra «Evidência verificada» y el mismo costo;
  la rodada derribada queda `interrompida`, sin costo de misión. En la instalación limpia **sin solver** y con los motores
  saboteados (`tools/e2e/sabotage_v2/sitecustomize.py`) el estudio importado muestra la misma evidencia y el mismo `run_uid`
  de origen; **registro de llamadas al motor: VACÍO**.
- **Tests** (`tests/test_piso3da_execucao.py`): reapertura con el solver saboteado, adulteración de datos detectada,
  exportar/importar estudio, imutabilidad.

## 6. Estado de las pruebas

| Prueba | Resultado | Sobre qué código |
|---|---|---|
| Focalizadas 3D-A + guardias, con solver | **40 passed, 1 skipped** (64,8 s) | `5e2a458` |
| Focalizadas 3D-A + guardias, sin solver | **24 passed, 17 skipped** (32,3 s) | `5e2a458` |
| Regresión completa, con solver | **2116 passed, 1 skipped**, 9 warnings (677 s) | anterior — ver nota |
| Regresión completa, sin solver | **1652 passed, 120 skipped**, 9 warnings (504 s) | anterior — ver nota |
| E2E de navegador | **106 verificaciones, exit 0** | `5e2a458` |
| Auditoría explícita del diff | **aprobada** (exit 0) | `12221d0`, en un **clon limpio** — ver §8 |
| CI remoto («SEEDS2 regression», solver true/false) | **en curso, sin resultado** al cerrar esta sesión (run `42963356574`) | PR #21 |

**Nota:** las regresiones completas se midieron antes de (a) añadir un test (`rechazo del dossier 2D-B para rodadas V2`),
(b) el ajuste cosmético de leyenda en `integracao_v2/ui.py` y (c) los arreglos del script E2E. Esperado en el HEAD final con
solver: 2117 passed, 1 skipped — **no medido**.

## 7. Comandos para reproducir

Entorno: Python con `requirements.txt` + `pytest`; para el solver, además `requirements-ems_v2.txt` (Pyomo 6.10.1, HiGHS 1.15.1).
Ejecutar siempre desde la raíz del repositorio.

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_piso3da_preflight.py tests/test_piso3da_execucao.py tests/test_piso3da_app.py tests/ems_v2/test_piso3da_guardas.py tests/ems_v2/test_ems_v2_isolamento.py -q -p no:cacheprovider
```

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ -q -p no:cacheprovider
```

```bash
python tests/ems_v2/piso3da_guard_policy.py
```

```bash
bash tools/e2e/run_piso3da.sh
```

El E2E necesita Node con Playwright y Chromium, y dos entornos Python (con y sin solver); las variables que acepta están al
inicio de `tools/e2e/run_piso3da.sh`.

## 8. Fallos y limitaciones conocidos

No hay tests fallando en lo ejecutado. Pendientes y sus causas:

- **C-3DA-01 — requiere decisión del responsable.** Las guardias de aislamiento prohibían que la aplicación alcanzara el motor
  V2; la integración exige una excepción **nominal** (nombres y estados exactos) en `piso3da_guard_policy.py`. Las guardias
  globales siguen activas.
- **Regresión global y CI remoto sin confirmar** sobre el HEAD final (sección 6).
- **Alcance mínimo:** FV, eólica, PEMFC y térmica no son representables en la integración ⇒ bloqueo (térmica: M19/CVU no
  implementado en el núcleo).
- **C-3DA-02:** la ponte 3C-0 rechaza la topología «conectada»; el inventario efectivo usa `modo_operacao="isolada"`
  (barramento interno) y el PCC se declara en el embrulho 3C-3.
- **C-3DA-03:** las declaraciones V2 viven en el escenario, no en el inventario.
- **C-3DA-04:** misión interrumpida por el controlador ⇒ estado `interrompida` con evidencia **parcial** en
  `outcome.evidence`; el formato `seeds2-study` v1 no admite datos en rodadas no concluidas.
- **C-3DA-05:** provedor de previsión de naturaleza `sintetico_conhecido`; UID `syn-…` para demanda, PCC y medidores.
- **C-3DA-06:** runner V2 separado que reutiliza `_LIVE`, `OWNER`, `_ENGINE_LOCK` y `owner_is_dead` del runner V1.6.
- **C-3DA-07:** sólo la hipótesis α = 1 de autodescarga.
- Los informes 2D-B (PDF/Excel/figuras) rechazan explícitamente las rodadas V2.
- **La auditoría del diff falla en un workspace «sucio»** (`caminhos protegidos alterados … config/__pycache__/…`, `models/__pycache__/…`). Causa: el repositorio versiona `__pycache__/*.pyc` y cualquier ejecución sin `PYTHONDONTWRITEBYTECODE=1` (p. ej. el servidor Streamlit del E2E) los regenera; la auditoría mira también el árbol de trabajo. No es un cambio de la misión: el diff publicado no contiene ningún `.pyc` (0 archivos) y la auditoría aprueba en un clon limpio. Esos `.pyc` **no** se incluyeron en ningún commit ni se descartaron del workspace de la sesión.

## 9. Trabajo sin publicar

- **Código, tests y documentación: nada pendiente.** Todo lo legítimo está en la rama.
- **Capturas PNG del E2E** (11 archivos, ≈ 5 MB) y el paquete `estudo_v2.seeds2study.zip` exportado: sólo en el directorio
  temporal de la sesión, **no versionados** por tamaño. Se regeneran con `bash tools/e2e/run_piso3da.sh`.
- **Registros completos de las regresiones globales:** no versionados; sólo sus totales (sección 6).

## 10. Próximos pasos exactos para otro agente

1. `git fetch origin claude/adoring-newton-jzfmfx && git checkout claude/adoring-newton-jzfmfx`; leer `CLAUDE.md`, este
   archivo y `docs/ems_v2/INTEGRACAO_3DA.md`.
2. Consultar el CI del PR #21 (run `42963356574`, matriz solver true/false; estaba en curso al cierre). Si falla, reproducir localmente el job antes de corregir.
3. Ejecutar `python tests/ems_v2/piso3da_guard_policy.py` en un **clon limpio** (`git clone` de la rama) tras cualquier commit nuevo; en un workspace donde ya se ejecutó la aplicación falla por los `.pyc` versionados (§8).
4. Ejecutar la regresión completa con y sin solver sobre el HEAD y anotar los totales en `PARAMIJEFE.md` Entrega 13 y en la
   descripción del PR.
5. Esperar la decisión del responsable sobre **C-3DA-01** y la auditoría independiente; aplicar sólo las correcciones pedidas.
6. Con todo confirmado, pasar el PR de Draft a listo para revisión. **Nunca hacer merge por iniciativa propia.**
7. 3D-B (dashboard operacional) sólo con autorización expresa; los contratos que consumirá están en
   `docs/ems_v2/INTEGRACAO_3DA.md`.

**Prohibido en la continuación:** modificar `ems_v2/` o V1.6, eliminar o relajar guardias globales, rellenar parámetros
físicos ausentes, presentar datos sintéticos como resultados de una microrred, `git reset --hard` / `git clean`.
