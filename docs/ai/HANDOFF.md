# SEEDS2 — Cuaderno de relevo entre agentes (HANDOFF)

> **Fuente de continuidad operativa.** Leer junto con [CLAUDE.md](../../CLAUDE.md) antes de comenzar cualquier sesión. Mantener breve, con hechos verificables, fecha y referencias a PRs. El código y los tests son la fuente de verdad funcional.

**Actualización:** 2026-11-06 · **rama:** `ccr-21b1e00e-u5u64z` · **PR:** [#8](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/8) (pendiente de auditoría; sin merge) · **estado:** **Piso 2C — Execução EMS e Persistência Científica** implementado; auditoría favorable y corrección C-02 aplicada; **no integrado** en `main` (espera autorización).

> **Informe técnico completo de la entrega vigente: [`PARAMIJEFE.md`](../../PARAMIJEFE.md) — Entrega 3** (canal permanente con el auditor). Este HANDOFF es solo el resumen de continuidad.

## 1. Estado actual

- `main` (`43ee6f5`): V1.6 + PR #1–#5 + **PR #6** (Piso 2A + C-01, `4709f0c`) + **PR #7** (Piso 2B, `43ee6f5`), verificado con `git fetch`.
- Rama `ccr-21b1e00e-u5u64z` (designada por el entorno de la sesión; la misión proponía `claude/seeds2-piso2c-execucao`): **Piso 2C** (sección 2).
- Arquitectura: `app.py` → shell `seeds2/ui/` (**Gestor** → [Comissionamento] → **Centro de Operação**: 01 Inicialização · 02 Previsões · **03 Estratégia EMS** · **04 Execução** · vista de **rodada** `?run=`). Backend: `registry.db` + `microgrids/<uid>/seeds2.db` (**esquema v4**: `scenario_runs` + `scenario_run_data`); dominio en `seeds2/operation/` (`strategy`, `mission`, `preflight`, `runner` nuevos).
- EMS, modelos, runtime y console V1.6 **sin cambios** (`git diff origin/main --stat -- models h2_pemfc simulation config ems_integration reference_models orchestrator_runtime.py orchestrator_app.py` vacío).

## 2. Última entrega — Piso 2C · Execução EMS e Persistência Científica (esta rama)

- **Implementado:** Estratégia EMS con opciones existentes del V1.6 (función objetivo única identificada; algoritmo, N, semilla, tolerancia, económicos, validación H₂) gravada en el escenario; ventana de la misión (`mission`) separada de horizonte de perfiles, paso (60 s fijo) y N; **preflight** (fase A estática + fase B sobre el contrato efectivo del motor vía `montar_fontes`) que BLOQUEA lo no representable; fusos → UTC, cobertura sin extrapolación, interpolación registrada (circular para dirección); runner en thread propio (progreso real k/n en el banco), idempotente, una rodada activa por microrred, `falhou`/`interrompida` sin resultados parciales; persistencia v4 con manifiesto inmutable y series completas; resultados (KPIs + curvas Plotly) reabiertos sin recalcular; avisos de backup y consentimiento específico de exclusión con rodadas. Detalle: `PARAMIJEFE.md` Entrega 3.
- **Verificado (2026-11-06):** `python -m pytest tests/ -q` → **345 passed** (7 avisos, iguales a la línea de base) (línea de base `main`: 308 passed; +37 nuevos; 7 tests existentes actualizados al estado real); E2E Chromium desde directorios vacíos: Piso 2C **55/55** (con `kill -9` del servidor durante una rodada → `Interrompida` tras reiniciar); Piso 2B **58/58**, Piso 2A **53/53**, Gestor **52/52**, Piso 1 **66/66**. Costo idéntico al EMS V1.6 para entradas equivalentes (R$ 88,3190884544543 en 30 min; despacho ≤ 1e-9 kW).
- **Decisiones del responsable aplicadas:** no corregir el optimizador; bloquear (no reinterpretar) lo no representable; ZIP sin cambio de formato; textos en portugués.
- **Decisiones técnicas a revisar (Claude Code):** ventana en el escenario (no en la rodada); indisponible = excluido solo de la rodada; equipo disponible no representable = bloqueo; deriva del inventario = advertencia (usa la revisión de referencia); declaración explícita de "mismo reloj" para series sin fuso; prueba de rampa del 1º paso con `despacho._n_prev_de`; ver `PARAMIJEFE.md` Entrega 3 §4.
- **Auditoría del PR #8 (2026-11-07): favorable** + corrección **C-02** (commit `4c8f14e`): C-02.1 equipo indisponible y excluido no exige estado inicial (`incompleto` → información; errores de coherencia y equipos disponibles incompletos siguen bloqueando); C-02.2 potencia inicial > 0 verificada contra `n_ini × [P_min_unid, P_max_unid]` del 1º paso ANTES de la rampa (rampa ilimitada no dispensa límites físicos), rechazo sin llamar al optimizador. Verificado: 355 passed; E2E 2C 55/55; diff científico vacío. Detalle: `PARAMIJEFE.md` Entrega 3 §17.
- **Pendiente / riesgos:** capacidades científicas bloqueadas (SOC fuera de límites efectivos, SOC distintos, PEMFC apagada/parcial, térmica ≠ `int(Pmín>0)`, rampa activa); sin cancelación de rodada; ejecuciones serializadas por proceso; ZIP sin escenarios/rodadas (2D); rodadas del console V1.6 siguen solo con resumen.

## 3. Próxima misión propuesta

**Piso 2D — Arquivo científico** (no implementada ni autorizada): exportación/importación de escenarios + rodadas (manifiesto y `scenario_run_data` con SHA-256) en ZIP científico, PDF/Excel. Después: piso del optimizador para las capacidades pendientes (Entrega 3 §14.1).

---

## Histórico — entrega anterior: Piso 2B · Previsões e Dados (PR #7, integrado en `43ee6f5`)

- Etapa 02 del Centro de Operação: demanda y clima (manual/CSV/sintético/referencia V1.6), pre-visualización Plotly, calidad, fusos explícitos, blobs en la misma transacción de la versión del escenario. Verificado entonces: 308 passed; E2E 2B 58/58, 2A 51/51, Gestor 52/52, Piso 1 66/66. Informe: `PARAMIJEFE.md` Entrega 2.

## Histórico — entrega anterior: Piso 2A · Centro de Operação (PR #6, integrado en `4709f0c`)

- Centro de Operação como inicio de la microrred comisionada; escenarios operativos versionados (append-only, concurrencia optimista, vínculo con la revisión del inventario, deriva + `rebase`); Inicialización con erro/aviso/pendente; contratos 2B/2C/2D; corrección de auditoría **C-01** (avisos de alcance del backup ZIP y consentimiento específico en la exclusión). Verificado entonces: 276 passed; E2E Piso 2A 50/50, Gestor 52/52, Piso 1 66/66. Informe: `PARAMIJEFE.md` Entrega 1.

## Histórico — entrega anterior: Gestor de microrredes (PR #5, integrado en `50ef4d6`)


**Implementado**
- **Catálogo** (`MicrogridRegistry`): `registry.db` (uid PK validado, estado `ready/deleting`, origen `new/legacy/import/copy`, procedencia de copias) + `microgrids/<uid>/seeds2.db` (el mismo `MicrogridStore` del Piso 1, con `CHECK(id = 1)`). Operaciones con varios archivos recuperables: preparación en `.staging` → confirmación (rename + INSERT bajo `BEGIN IMMEDIATE` del catálogo); exclusión `deleting → .trash → DELETE`; `recover()` concluye interrupciones. Rutas derivadas solo del UID validado.
- **Adopción del `seeds2.db` anterior al Gestor**: una vez, idempotente, segura entre procesos, copia **de solo lectura** vía API de backup SQLite (original byte a byte intacto), migración de la copia, verificación de conteos; fallo → error claro y ninguna microrred creada.
- `MicrogridStore`: `must_exist` (no recrea microrredes eliminadas), `fixed_uid` (sin cambio de identidad), `import_inspected`, `inspect_backup_data`, `sqlite_backup_copy(read_only=…)`, `ensure_wal` (corrige "database is locked" en aperturas concurrentes de bases nuevas).
- **Interfaz**: página inicial GESTOR DE MICRORREDES (estado vacío; tarjetas con estado *Em configuração / Ativa / Atenção* separado de la compatibilidad con el EMS; FV calculada × declarada, eólica de catálogo, almacenamiento con su base); ＋ NOVA MICRORREDE (comisionamiento reutilizado íntegro; se registra al guardar la etapa 01), ABRIR, ZIP y PDF **sin abrir** la microrred, IMPORTAR (nueva / restaurar en la existente / copia independiente con `installation.copied_from`; nunca sobrescribe en silencio), EXCLUIR (resumen, ZIP previo, nombre exacto, credencial). TROCAR MICRORREDE en la barra superior; nombre de la microrred activa siempre visible.
- **Sesión**: microrred activa por sesión de navegador (`mg_active_uid`, `?mg=` para recarga); abrir/cambiar limpia todo el `session_state` (incluido el console V1.6); microrred eliminada por otra sesión → vuelta al Gestor sin recrearla.
- **Procedencia**: `microgrid_uid` en el plan, en `orq_mg_applied` y en el resumen de cada rodada; resultado de otra microrred señalado como tal; rodadas persistidas mostradas al volver.
- **Protección de la exclusión**: `SEEDS2_ADMIN_PASSWORD` / Streamlit Secrets `seeds2_admin_password` (verificación en servidor, tiempo constante); sin credencial, `SEEDS2_DEV_MODE=1` habilita la exclusión solo para uso local; por defecto **desactivada**.

**Hotfix H-01 — exclusión concurrente (auditoría del PR #5)**
- *Causa raíz:* `delete()` tomaba y soltaba el bloqueo de escritura de la microrred antes de marcar `deleting` y mover el directorio; una escritura de otra sesión en ese intervalo se confirmaba y luego se perdía en silencio (reproducido en `ad1d736`). Instancias `MicrogridStore` antiguas no se invalidaban; una microrred eliminada y reimportada con el mismo UID podía recibir la edición pendiente de una sesión antigua.
- *Corrección:* lápide `meta.lifecycle` grabada bajo el bloqueo L2 de la microrred y verificada por TODA transacción/lectura del `MicrogridStore` dentro de su `BEGIN IMMEDIATE`; protocolo lápide (L2) → `deleting` (L1, un único ganador) → remoción física (L1), sin bloqueos anidados; incarnación por entrada (catálogo v2 + `meta.incarnation`, con relleno de las existentes) y sesión ligada a ella; conexiones `mode=rw`; `recover()` idempotente que solo concluye exclusiones con lápide y lleva directorios sin fila a `.quarantine`; la interfaz vuelve al Gestor si la microrred se elimina durante una página. Detalle: `docs/seeds2/ARMAZENAMENTO.md` §H-01.
- *Pruebas:* `tests/test_seeds2_concorrencia.py` (17, deterministas con `Event`/`Barrier`, 10 ejecuciones consecutivas idénticas) + 1 de interfaz. Mapa escenario → prueba: `docs/seeds2/VERIFICACAO_PISO1.md` §H-01.

**Auditoría independiente del PR #5 — H-02 y H-03 (ambos reproducidos en `b8f721c` antes de corregir)**
- *H-02 (alta):* una exclusión obsoleta (validada sobre la incarnación I1) podía grabar la lápide, reivindicar y borrar la microrred **reimportada** con el mismo UID (I2). Corrección: exclusión vinculada a una incarnación en la lápide (L2), en `ready→deleting` (L1), en la remoción física y en `recover()`; `StaleDeletionError` sin tocar la nueva; diálogo del Gestor vinculado a la incarnación mostrada. Sin bloqueos anidados ni global.
- *H-03 (media):* `_read()` comprobaba la lápide y consultaba en instantáneas distintas (leyó la revisión 2 de una base ya con lápide). Corrección: transacción de lectura cuyo instantáneo WAL nace en la propia comprobación (lectura anterior a la lápide → estado anterior válido; posterior → rechazada); `export_backup` en un solo instantáneo.
- Detalle: `docs/seeds2/ARMAZENAMENTO.md` §H-02/§H-03; pruebas y reproducciones: `docs/seeds2/VERIFICACAO_PISO1.md` §H-02/H-03.

**Validado (por Claude Code, 2026-11-05)**
- `python -m pytest tests/ -q` → **237 passed, 0 failed, 0 skipped** tras H-02/H-03 (226 tras H-01; 208 antes). Nuevos: `test_seeds2_gestor.py` (32), `test_seeds2_gestor_app.py` (15), `test_seeds2_concorrencia.py` (27). Mapa requisitos 1–25 → pruebas: `docs/seeds2/VERIFICACAO_PISO1.md` §G.
- Despacho y costo idénticos a `main` (hash de `P_kW`, R$ 417,684638) con la configuración por defecto V1.6 y con una microrred del catálogo.
- Tras el hotfix H-01, E2E repetidos desde cero en Chromium: Gestor **52/52** y Piso 1 **66/66** (simulación EMS real), sin errores de JavaScript.
- Tras H-02/H-03 (`c4aade6`), E2E repetidos desde cero: Gestor **52/52** y Piso 1 **66/66**, sin errores de JavaScript y sin residuos en `.trash`/`.staging`/`.quarantine`; EMS idéntico a `main`.
- Chromium: `tools/e2e/e2e_gestor_microrredes.js` **52/52** (multi → reinicio del servidor → tablet/oscuro → legado) y `tools/e2e/e2e_piso1_microrrede.js` **66/66** (ahora desde el Gestor; rodada EMS real). Capturas revisadas.
- Rodada EMS real desde una microrred seleccionada = despacho y costo de la V1.6.
- **Sin CI.**

### Decisiones (con origen) — Gestor

- **Responsable:** varias microrredes por instalación; catálogo central + base independiente por microrred; eliminación definitiva real (no ocultar), protegida en despliegues compartidos; textos en portugués; no tocar ciencia ni EMS.
- **Claude Code (técnica, a revisar):** estado `deleting` + `.trash` en lugar de borrar en el lugar; staging + rename bajo el bloqueo del catálogo; el catálogo no guarda datos técnicos (tarjetas calculadas de la configuración guardada); `seeds2.db` anterior se conserva como respaldo (no se borra automáticamente); limpieza **total** del `session_state` al cambiar de microrred (más seguro que listas de claves); exclusión desactivada por defecto sin credencial; nombre de exportación incluye 8 dígitos del UID; la restauración dentro de Gestão solo acepta backups de la misma identidad.

### Pendencias / observaciones — Gestor (vigentes salvo indicación)

- Sin autenticación/roles: cualquier sesión puede crear, editar, importar y restaurar; solo la exclusión definitiva tiene protección. La credencial es única (no hay auditoría por usuario).
- El `seeds2.db` anterior queda en `SEEDS2_DATA_DIR` tras la adopción; eliminarlo manualmente después de conferir.
- Las series completas del despacho no se persisten (solo el resumen de cada rodada); al volver a una microrred no se reconstruyen resultados.
- ~~Escritura concurrente con una exclusión podía perderse~~ → **corregido por H-01** (escrituras confirmadas antes de la lápide o rechazadas explícitamente). Límite restante: la exclusión espera como máximo 30 s por una escritura en curso y, si no obtiene el bloqueo, desiste sin alterar nada; la edición pendiente de una sesión cuya microrred fue eliminada no se graba (comportamiento pretendido).
- **Deuda técnica para la fase científica:** persistir las series temporales completas del despacho EMS (hoy solo el resumen de cada rodada en `simulation_runs`).
- Heredadas: decisiones científicas (perfil V–I del ModelLab; equipos heterogéneos; >1 térmica), red sin import/export, MIX inaccesible, `__pycache__/` versionado, README V1.5, sin CI.

### (Propuesta de entonces) Piso 2: Centro de Operação → **iniciado en el Piso 2A** (rama `claude/seeds2-piso2a-centro-operacao`).

## 4. Ritual de actualización y histórico

Actualizar **este archivo en el mismo PR** con: fecha, rama, PR y commit, alcance, tests realmente ejecutados, decisiones, pendencias y próxima misión. Nunca incluir contraseñas, tokens o datos sensibles.

**Histórico:**
- PR [#1](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/1) — tests UI V1.6 + `CLAUDE.md` (merge `5ffe2ee`).
- PR #2 — protocolo de relevo (`f70dd94`).
- PR [#3](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/3) — SEEDS2 v2.0 Piso 1 (merge `67a7a6f`). Regla entonces vigente: **"una instalación = una microrred"** (directriz del prompt maestro del Piso 1; sustituyó la idea anterior de "cadastro/seleção").
- PR [#4](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/4) — refinamiento del Piso 1 + backup `.bak-v<N>` consistente con WAL (merge `05e29ef`; 163 passed, E2E 64/64 reportados entonces).
- PR [#5](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/5) — Gestor de microrredes + H-01/H-02/H-03 (merge squash `50ef4d6`, 2026-11-06; 237 passed, E2E Gestor 52/52 y Piso 1 66/66 reportados entonces). La regla de microrred única queda **sustituida por autorización del responsable**.
- PR [#6](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/6) — Piso 2A, Centro de Operação + C-01 (merge `4709f0c`); inicia el protocolo `PARAMIJEFE.md`.
- PR [#7](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/7) — Piso 2B, Previsões e Dados (merge `43ee6f5`): `PARAMIJEFE.md` Entrega 2.
- Piso 2C — Execução EMS e Persistência Científica (rama `ccr-21b1e00e-u5u64z`; PR [#8](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/8)): `PARAMIJEFE.md` Entrega 3.

**Lectura obligatoria al entrar:** `CLAUDE.md` → este `HANDOFF.md` → `PARAMIJEFE.md` → estado real de `main` y PRs recientes. En caso de conflicto, reportar; no improvisar decisión científica.
