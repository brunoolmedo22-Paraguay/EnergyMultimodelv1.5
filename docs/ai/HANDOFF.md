# SEEDS2 — Cuaderno de relevo entre agentes (HANDOFF)

> **Fuente de continuidad operativa.** Leer junto con [CLAUDE.md](../../CLAUDE.md) antes de comenzar cualquier sesión. Mantener breve, con hechos verificables, fecha y referencias a PRs. El código y los tests son la fuente de verdad funcional.

**Actualización:** 2026-11-05 · **rama:** `claude/seeds2-gestor-microrredes` · **PR [#5](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/5)** (pendiente de revisión; sin merge) · **estado:** Gestor de microrredes implementado y verificado en la rama; **no integrado en `main`**.

## 1. Estado actual

- `main` (`05e29ef`): V1.6 + PR #1 + PR #2 + PR #3 (Piso 1) + **PR #4 integrado** (refinamiento del Piso 1, incl. backup WAL-consistente).
- Rama `claude/seeds2-gestor-microrredes`: **Gestor de microrredes** (esta misión; sección 2).
- **Decisión de producto vigente (responsable, misión "Gestor de microrredes"):** una instalación del SEEDS2 administra **varias microrredes independientes**. *Sustituye expresamente* la regla anterior "una sola microrred por instalación" (vigente desde el prompt maestro del Piso 1 hasta el PR #4; ver histórico en la sección 6). No son proyectos de simulación: cada microrred es una instalación con configuración, inventario, almacenamiento, revisiones y rodadas propias; sin optimización conjunta ni intercambio entre microrredes.
- Arquitectura: `app.py` → shell `seeds2/ui/` (**Gestor** → [Comissionamento] → Início · Gestão · Simulação · Resultados · Alcance; TROCAR MICRORREDE). Backend: `seeds2/microgrid/registry.py` (catálogo `registry.db` + un `MicrogridStore` por microrred en `microgrids/<uid>/`). Detalles: `docs/seeds2/ARQUITETURA_PISO1.md` §1, `docs/seeds2/ARMAZENAMENTO.md`.
- EMS y modelos científicos **sin cambios** (`git diff origin/main` vacío en `models`, `h2_pemfc`, `simulation`, `config`, `ems_integration`, `reference_models`).

## 2. Última entrega — Gestor de microrredes (esta rama)

**Implementado**
- **Catálogo** (`MicrogridRegistry`): `registry.db` (uid PK validado, estado `ready/deleting`, origen `new/legacy/import/copy`, procedencia de copias) + `microgrids/<uid>/seeds2.db` (el mismo `MicrogridStore` del Piso 1, con `CHECK(id = 1)`). Operaciones con varios archivos recuperables: preparación en `.staging` → confirmación (rename + INSERT bajo `BEGIN IMMEDIATE` del catálogo); exclusión `deleting → .trash → DELETE`; `recover()` concluye interrupciones. Rutas derivadas solo del UID validado.
- **Adopción del `seeds2.db` anterior al Gestor**: una vez, idempotente, segura entre procesos, copia **de solo lectura** vía API de backup SQLite (original byte a byte intacto), migración de la copia, verificación de conteos; fallo → error claro y ninguna microrred creada.
- `MicrogridStore`: `must_exist` (no recrea microrredes eliminadas), `fixed_uid` (sin cambio de identidad), `import_inspected`, `inspect_backup_data`, `sqlite_backup_copy(read_only=…)`, `ensure_wal` (corrige "database is locked" en aperturas concurrentes de bases nuevas).
- **Interfaz**: página inicial GESTOR DE MICRORREDES (estado vacío; tarjetas con estado *Em configuração / Ativa / Atenção* separado de la compatibilidad con el EMS; FV calculada × declarada, eólica de catálogo, almacenamiento con su base); ＋ NOVA MICRORREDE (comisionamiento reutilizado íntegro; se registra al guardar la etapa 01), ABRIR, ZIP y PDF **sin abrir** la microrred, IMPORTAR (nueva / restaurar en la existente / copia independiente con `installation.copied_from`; nunca sobrescribe en silencio), EXCLUIR (resumen, ZIP previo, nombre exacto, credencial). TROCAR MICRORREDE en la barra superior; nombre de la microrred activa siempre visible.
- **Sesión**: microrred activa por sesión de navegador (`mg_active_uid`, `?mg=` para recarga); abrir/cambiar limpia todo el `session_state` (incluido el console V1.6); microrred eliminada por otra sesión → vuelta al Gestor sin recrearla.
- **Procedencia**: `microgrid_uid` en el plan, en `orq_mg_applied` y en el resumen de cada rodada; resultado de otra microrred señalado como tal; rodadas persistidas mostradas al volver.
- **Protección de la exclusión**: `SEEDS2_ADMIN_PASSWORD` / Streamlit Secrets `seeds2_admin_password` (verificación en servidor, tiempo constante); sin credencial, `SEEDS2_DEV_MODE=1` habilita la exclusión solo para uso local; por defecto **desactivada**.

**Validado (por Claude Code, 2026-11-05)**
- `python -m pytest tests/ -q` → **208 passed, 0 failed, 0 skipped** (+105 subtests; 7 avisos SLSQP preexistentes). Nuevos: `test_seeds2_gestor.py` (32), `test_seeds2_gestor_app.py` (13). Mapa requisitos 1–25 → pruebas: `docs/seeds2/VERIFICACAO_PISO1.md` §G.
- Chromium: `tools/e2e/e2e_gestor_microrredes.js` **52/52** (multi → reinicio del servidor → tablet/oscuro → legado) y `tools/e2e/e2e_piso1_microrrede.js` **66/66** (ahora desde el Gestor; rodada EMS real). Capturas revisadas.
- Rodada EMS real desde una microrred seleccionada = despacho y costo de la V1.6.
- **Sin CI.**

## 3. Decisiones (con origen)

- **Responsable:** varias microrredes por instalación; catálogo central + base independiente por microrred; eliminación definitiva real (no ocultar), protegida en despliegues compartidos; textos en portugués; no tocar ciencia ni EMS.
- **Claude Code (técnica, a revisar):** estado `deleting` + `.trash` en lugar de borrar en el lugar; staging + rename bajo el bloqueo del catálogo; el catálogo no guarda datos técnicos (tarjetas calculadas de la configuración guardada); `seeds2.db` anterior se conserva como respaldo (no se borra automáticamente); limpieza **total** del `session_state` al cambiar de microrred (más seguro que listas de claves); exclusión desactivada por defecto sin credencial; nombre de exportación incluye 8 dígitos del UID; la restauración dentro de Gestão solo acepta backups de la misma identidad.

## 4. Pendencias / observaciones

- Sin autenticación/roles: cualquier sesión puede crear, editar, importar y restaurar; solo la exclusión definitiva tiene protección. La credencial es única (no hay auditoría por usuario).
- El `seeds2.db` anterior queda en `SEEDS2_DATA_DIR` tras la adopción; eliminarlo manualmente después de conferir.
- Las series completas del despacho no se persisten (solo el resumen de cada rodada); al volver a una microrred no se reconstruyen resultados.
- Una sesión con escritura en curso exactamente durante una exclusión hecha por otra sesión puede perder esa escritura (la exclusión espera escrituras en curso, pero no bloquea las siguientes).
- Heredadas: decisiones científicas (perfil V–I del ModelLab; equipos heterogéneos; >1 térmica), red sin import/export, MIX inaccesible, `__pycache__/` versionado, README V1.5, sin CI.

## 5. Próxima misión propuesta — Piso 2: Centro de Operação

**No implementada ni autorizada.** Partir del catálogo (`MicrogridRegistry`) + `MicrogridStore` + `adapter` + `run_conditions`: estrategias EMS y escenarios por microrred, historial de rodadas comparables por revisión. Requiere aprobación del prompt maestro y las decisiones de la sección 4.

## 6. Ritual de actualización y histórico

Actualizar **este archivo en el mismo PR** con: fecha, rama, PR y commit, alcance, tests realmente ejecutados, decisiones, pendencias y próxima misión. Nunca incluir contraseñas, tokens o datos sensibles.

**Histórico:**
- PR [#1](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/1) — tests UI V1.6 + `CLAUDE.md` (merge `5ffe2ee`).
- PR #2 — protocolo de relevo (`f70dd94`).
- PR [#3](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/3) — SEEDS2 v2.0 Piso 1 (merge `67a7a6f`). Regla entonces vigente: **"una instalación = una microrred"** (directriz del prompt maestro del Piso 1; sustituyó la idea anterior de "cadastro/seleção").
- PR [#4](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/4) — refinamiento del Piso 1 + backup `.bak-v<N>` consistente con WAL (merge `05e29ef`; 163 passed, E2E 64/64 reportados entonces).
- Misión "Gestor de microrredes" (esta rama): la regla de microrred única queda **sustituida por autorización del responsable**.

**Lectura obligatoria al entrar:** `CLAUDE.md` → este `HANDOFF.md` → estado real de `main` y PRs recientes. En caso de conflicto, reportar; no improvisar decisión científica.
