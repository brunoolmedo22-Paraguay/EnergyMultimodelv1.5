# SEEDS2 — Cuaderno de relevo entre agentes (HANDOFF)

> **Fuente de continuidad operativa.** Leer junto con [CLAUDE.md](../../CLAUDE.md) antes de comenzar cualquier sesión. Mantener breve, con hechos verificables, fecha y referencias a PRs. El código y los tests son la fuente de verdad funcional.

**Actualización:** 2026-11-09 · **rama:** `ccr-2529baa8-16lz1j` · **PR:** [#15](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/15) contra `main`, sin merge (pendiente de auditoría independiente) · **estado:** **Piso 3C-2 — MPC de horizonte recedente (M23), K6 y primer lazo cerrado reproducible** implementado y verificado en la rama; **no integrado** (sin UI/runtime; simulación causal **algebraica**, no física).

> **Informe técnico vigente: [`PARAMIJEFE.md`](../../PARAMIJEFE.md) — Entrega 10**; formulación M23, política de información, decisiones y contradicciones en [`docs/ems_v2/FORMULACAO_3C2.md`](../ems_v2/FORMULACAO_3C2.md); trazabilidad en [`MATRIZ_3C2.md`](../ems_v2/MATRIZ_3C2.md); evidencia en [`EVIDENCIA_3C2.md`](../ems_v2/EVIDENCIA_3C2.md) y [`EVIDENCIA_3C2_EJECUCION.md`](../ems_v2/EVIDENCIA_3C2_EJECUCION.md); brechas en [`BRECHAS_3C2.md`](../ems_v2/BRECHAS_3C2.md); transición en [`TRANSICAO_3C2_3C3_3C4.md`](../ems_v2/TRANSICAO_3C2_3C3_3C4.md).

## 1. Estado actual

- `main` (`55440f4`): V1.6 + PR #1–#14 (3A, 3B-P, 3C-0 y 3C-1 integrados; el PR #14 fue integrado después de la última actualización de este cuaderno, que aún lo marcaba "pendiente"). Línea de base `tests/ems_v2` medida en esta sesión: **717 passed**.
- Rama `ccr-2529baa8-16lz1j` desde `main`: **Piso 3C-2** (sección 2).
- **Ningún archivo existente** de `ems_v2` (3A/3B-P/3C-0/3C-1), V1.6, `seeds2`, aplicación ni `requirements*.txt` fue modificado desde `55440f4` (guardia nueva `test_pisos_anteriores_v16_e_aplicacao_sem_alteracao_desde_o_merge_do_pr14`; `ADICOES_3C1` sin ajuste). La aplicación sigue sin referenciar `ems_v2`.

## 2. Última entrega — Piso 3C-2 (esta rama)

- **Implementado:** `ems_v2/mpc/` (núcleo solo biblioteca estándar): `contrato` (configuración, identidad, políticas terminal/aceptación/fallas/revisión tardía sin defecto), `relogio` (τ_k, N_k, m_k, último bloque, contador monotónico), `observacoes` (K6 append-only, instantáneo = prefijo comprometido), `previsao`/`provedores` (previsión por ventana con vínculo al instantáneo; tabla declarada, corrección por observación, oráculo de ablación), `entorno` (protocolo de paso + planta algebraica con canal y perturbaciones declaradas), `janela` (entrada 3C-1 con estado/memoria EJECUTADOS), `adaptador_milp` (único camino a `resolver_3c1`, import tardío), `orquestrador` (`ControladorMPC` modos 1 y 2, conciliación por C-02), `registro`/`persistencia` (registros encadenados, `PontoRetomada`, reanudación verificada), `auditoria` (temporal, causal, estado, balance, costos, aceptación, separación, intervención), `metricas`, `comparadores`, `capacidades` (M23 `parcial_3C2`), `experimentos` (E1–E8) y `evidencia`; `ems_v2/fixtures_3c2.py`.
- **Verificado (2026-11-09):** 83 tests nuevos (`tests/ems_v2/test_ems_v2_3c2_*.py`); `tests/ems_v2` **800 passed** (sin Pyomo: 563 passed, 19 skipped); suite completa **1254 passed, 7 warnings, 128 subtests** (379 s) = 1171 + 83. Detalle: `EVIDENCIA_3C2.md`.
- **Hallazgos:** C-3C2-01 (sin recurso de equilibrio: error de demanda en intervalo aplicado ⇒ consigna inexequible ⇒ interrupción clasificada, sin recorte); C-3C2-02 (`intervalos_missao` de la entrada con horizonte extendido); miopía sin valor terminal (banco drenado por ventana; obligaciones pendientes reportadas al final); límite de confianza de la protección contra fuga (estructural + intervención posterior).
- **Decisiones:** D-3C2-01..13 (FORMULACAO_3C2 §8). **Contradicciones:** C-3C2-01..05 (§9).
- **No implementado (fuera de alcance):** valor futuro/planificador (3C-4), red/tarifas (3C-3), estimador de estado, planta física, multimodo PEMFC (M20), control real, UI/selector, sustitución del V1.6.

## 3. Próxima misión propuesta

3C-3 (red/tarifas/recurso de equilibrio) o 3C-4 (planificador jerárquico y valor futuro) — **no autorizados**; requieren auditoría del 3C-2 y decisiones D-3C2-*. Interfaces preparadas en `TRANSICAO_3C2_3C3_3C4.md`.

---

## Histórico — entrega anterior: Piso 3C-1 · Unit Commitment dinámico (PR #14, integrado en `55440f4`)

- `ems_v2/compromisso/` (contrato embrulho, discretización, memoria, preflight, auditor independiente) + `ems_v2/milp/*_3c1.py` (`resolver_3c1`) + `ems_v2/ponte/compromisso.py` y `registro_3c1.py`; auditorías A-01..A-03, B-01/B-02 y B-03 aplicadas. Verificado entonces: `tests/ems_v2` 717 passed; suite 1171 passed. Informe: `PARAMIJEFE.md` Entrega 9.

## Histórico — entrega anterior: Piso 3C-0 · Puente científico (PR #13, integrado en `81aa09c`)

- `ems_v2/ponte/` (inventario por UID, requisitos, escenario/previsión/realización, proyección, plan → ejecución → estado, preflight, registro sellado, instrumentación) y `ems_v2/ponte_seeds2/leitor.py` (solo lectura, C-3C0-01 aceptada condicionalmente); auditorías H-01..H-04 y C-01..C-03 aplicadas. Verificado entonces: `tests/ems_v2` 535 passed; suite 989 passed. Informe: `PARAMIJEFE.md` Entrega 8.

## Histórico — entrega anterior: Piso 3B-P · Primer MILP Pyomo + HiGHS (PR #12, integrado en `3c65d98`)

- `ems_v2/milp/` con `resolver(entrada, configuracao, compromisso_fixo)`: MILP de una ventana (M02, M03-v1.1, M04, M06–M08, M10 con compromiso fijo constante, M14–M16 PWL sin SOS), clasificación de terminación y aceptación solo tras auditor independiente; correcciones C-3B-01/02/03. Verificado entonces: `tests/ems_v2` 416 passed; suite 870 passed. Informe: `PARAMIJEFE.md` Entrega 7.

## Histórico — entrega anterior: Piso 3A · Fundaciones del EMS MILP–MPC (PR #11, integrado en `f6d009d`)

- Contratos canónicos por UID, malla N/N+1, referencia racional exacta, auditor independiente, catálogo M01–M23 + v1.1 (150 símbolos, 42 ecuaciones); auditoría favorable con correcciones C-3A-01..04. Verificado entonces: `tests/ems_v2` 268 passed; suite 722 passed. Informe: `PARAMIJEFE.md` Entrega 6.

## Histórico — entrega anterior: Piso 2D-B · Relatórios Científicos e Exportações (PR #10, integrado en `8556b71`)

- `RunDossier` unificado (rodada local × archivada), PDF científico/diagnóstico, Excel completo (doubles con `repr`; Excel garantiza 15 dígitos), figuras PNG/SVG y ZIP `seeds2-figures`; auditoría favorable + corrección C-04. Verificado entonces: 454 passed; E2E 2D-B 57/57 + 157/157 descargas. Informe: `PARAMIJEFE.md` Entrega 5.

## Histórico — entrega anterior: Piso 2D-A · Arquivo Científico Portátil (PR #9, integrado en `3b73971`)

- Paquete `seeds2-study` v1 (`.seeds2study.zip`), inspección de paquetes no confiables, Arquivo Científico de la instalación (banco propio, importación atómica, identidad local ≠ origen), consulta histórica sin recalcular; auditoría favorable + corrección C-03. Verificado entonces: 407 passed; E2E 2D-A 62/62. Informe: `PARAMIJEFE.md` Entrega 4.

## Histórico — entrega anterior: Piso 2C · Execução EMS e Persistência Científica (PR #8, integrado en `34a8b52`)

- Etapas 03 Estrategia EMS y 04 Ejecución; preflight (fases A/B) que BLOQUEA lo no representable; runner en thread propio; persistencia v4 (`scenario_runs` + `scenario_run_data`) con manifiesto inmutable y series completas; auditoría favorable + corrección C-02. Verificado entonces: 355 passed; E2E 2C 55/55. Informe: `PARAMIJEFE.md` Entrega 3.

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
- PR [#8](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/8) — Piso 2C, Execução EMS e Persistência Científica + C-02 (merge `34a8b52`): `PARAMIJEFE.md` Entrega 3.
- PR [#9](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/9) — Piso 2D-A, Arquivo Científico Portátil + C-03 (merge `3b73971`): `PARAMIJEFE.md` Entrega 4.
- PR [#10](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/10) — Piso 2D-B, Relatórios Científicos, Excel e Figuras (merge `8556b71`): `PARAMIJEFE.md` Entrega 5.
- PR [#11](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/11) — Piso 3A (merge `f6d009d`): Entrega 6. PR [#12](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/12) — Piso 3B-P (merge `3c65d98`): Entrega 7.
- PR [#13](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/13) — Piso 3C-0, Puente científico (merge `81aa09c`): Entrega 8.
- PR [#14](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/14) — Piso 3C-1, Commitment dinámico (merge `55440f4`): Entrega 9.
- Piso 3C-2 — MPC de horizonte recedente (rama `ccr-2529baa8-16lz1j`; PR [#15](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/15), pendiente de auditoría): Entrega 10.

**Lectura obligatoria al entrar:** `CLAUDE.md` → este `HANDOFF.md` → `PARAMIJEFE.md` → estado real de `main` y PRs recientes. En caso de conflicto, reportar; no improvisar decisión científica.
