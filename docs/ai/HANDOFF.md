# SEEDS2 — Cuaderno de relevo entre agentes (HANDOFF)

> **Fuente de continuidad operativa.** Leer junto con [CLAUDE.md](../../CLAUDE.md) antes de comenzar cualquier sesión. Mantener breve, con hechos verificables, fecha y referencias a PRs. El código y los tests son la fuente de verdad funcional.

**Actualización:** 2026-11-05 · **rama:** `claude/seeds2-piso1-refinamento` · **PR [#4](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/4)** (pendiente de revisión; sin merge) · **estado:** refinamiento del Piso 1 implementado y verificado en la rama; **no integrado en `main`**.

## 1. Estado actual

- `main` (`67a7a6f`): V1.6 + PR #1 + PR #2 + **PR #3 integrado** (SEEDS2 v2.0 — Piso 1). *Corrige* el texto anterior de este cuaderno, que lo daba como pendiente.
- Rama `claude/seeds2-piso1-refinamento` (PR #4): **refinamiento del Piso 1** (esta misión; sección 2).
- Arquitectura: `app.py` → shell `seeds2/ui/` (Comissionamento → Início · Gestão da Microrrede · Simulação · Resultados · Alcance); Simulação/Resultados embeben el console V1.6. Backend sin UI en `seeds2/microgrid/`; informe PDF en `seeds2/report/`. Detalles: `docs/seeds2/ARQUITETURA_PISO1.md`, `docs/seeds2/ARMAZENAMENTO.md`.
- EMS y modelos científicos **sin cambios** (`git diff origin/main` vacío en `models`, `h2_pemfc`, `simulation`, `config`, `ems_integration`, `reference_models`).

## 2. Última entrega — refinamiento del Piso 1 (esta rama)

**Implementado**
- **Inventario físico × condiciones de la rodada:** documento **v2** con migración versionada v1→v2 (`seeds2/microgrid/migrations.py`); SOC inicial de baterías pasa a `run_conditions` (Simulação → "Condições da rodada", registrado en la procedencia).
- **Etapa 01:** dos tarjetas (identificación con nombre/natureza/modo obligatorios; localización opcional) y "LOCALIZAÇÃO AUTOMÁTICA" (`navigator.geolocation`: una lectura tras clic, precisión, huso sólo como sugerencia, errores negado/indisponible/inseguro/timeout, sin geocodificación, guardado sólo al confirmar; procedencia `navegador`/`manual`). Instalaciones antiguas sin natureza/modo: aviso + "Completar identificação" en Gestão.
- **Diálogo de equipos:** catálogo visual de 5 tecnologías → configuración → confirmación ("Voltar às tecnologias"; nada se registra antes); edición abre el editor directamente; confirmación "Equipamento com configuração pendente" (Salvar como pendente / Voltar à configuração); datos de registro faltantes y valores físicamente inválidos bloquean.
- **FV = usina → arranjos** (módulos identificados Ns/Np o kWp declarado con procedencia); STC por arranjo homogéneo con hipótesis declaradas, sin sumar Voc/Isc entre arranjos; sujeira 0 % marcada como padrón; EMS agrega sólo arranjos homogéneos; potencia instalada ≠ simulada (mostradas ambas).
- **Eólica:** curva Plotly desde los puntos originales (tabulados × interpolación visual; digitalizada × tabla del fabricante rotulado).
- **Batería:** datasheet primero, estimaciones derivadas rotuladas, SOC 20/80 sugerido y editable, taxa C sólo con I+Ah, "Configuração avançada do modelo científico", registrado físicamente × parametrizado.
- **PEMFC:** perfil equivalente del catálogo o "IMPORTAR DISPOSITIVO DO PEMFC MODELLAB" (`.pmldevice.zip`/`profile.json` validado, procedencia y estado de validación, original guardado como blob e incluido en backups, **pendiente de integración científica**: no entra en la simulación); "CRIAR DISPOSITIVO NO PEMFC MODELLAB" abre `https://pemfc-modelab.streamlit.app/?view=home` en otra pestaña.
- **Etapa 03:** "Esquema lógico do balanço energético" sustituye la topología eléctrica; sólo queda la declaración de conexión a la red con aviso (EMS sin import/export; déficit ≠ compra de la red). Topología v1 preservada en `legacy.topology_v1`. Usina parcialmente representada se muestra como tal.
- **Exportaciones** (etapa 05 y Gestão → "Relatório, histórico e backups"): ZIP (backup formato 2, acepta formato 1) y **informe técnico PDF** local (reportlab; "Não declarado"; PRELIMINAR antes de la activación; sin afirmaciones de certificación).
- Base de datos v2: migración del documento como nueva revisión (`origin = migration`), copia `.bak-v1`, revisiones antiguas migradas en lectura.
- **Corrección de la auditoría del PR #4 (review del 2026-11-05):** la copia `.bak-v<N>` previa a la migración ya no usa `shutil.copy2` (no incluía el contenido del `-wal`; reproducido: la copia quedaba sin tablas). Ahora usa la **API de backup de SQLite** en una conexión propia mientras la migración retiene `BEGIN IMMEDIATE` (copia = estado exacto migrado), espera acotada (`BACKUP_COPY_TIMEOUT_S`), archivo autosuficiente (journal DELETE) verificado con `integrity_check` y publicado con `os.replace`. Copia + todas las migraciones pendientes en **una única transacción**; versión releída bajo el bloqueo (idempotente con aperturas concurrentes); fallos → rollback y `StoreError`. `CLAUDE.md` regla 8: excepción restringida a fixtures sintéticas auditadas (`tests/fixtures/README.md`).
- Dependencias nuevas: `reportlab==4.4.10`, `pypdf==6.21.4` (sólo tests). Archivos de UI eliminados: `ui/static/topology.*`.

**Validado (por Claude Code, en esta rama, 2026-11-05)**
- `python -m pytest tests/ -q` → **163 passed, 0 failed, 0 skipped** (+105 subtests; 7 avisos SLSQP preexistentes), tras la corrección del backup WAL (158 antes de ella).
- Migraciones desde **datos v1 reales** generados con el código de `main` antes de los cambios (`tests/fixtures/`): documento, backup formato 1, banco SQLite v1 (histórico y rodadas preservados, `.bak-v1`, idempotente, documento inválido no corrompe); **rodada EMS con la configuración migrada = configuración V1.6** (mismo despacho y costo).
- Chromium (`tools/e2e/e2e_piso1_microrrede.js`, diretório vacío, reinicio del servidor): 64 verificaciones aprobadas (40 + 20 + 4), sin excepciones ni errores JS — repetido completo tras la corrección del backup WAL (commit `ccf33be`) con el mismo resultado; tablet sin scroll horizontal; tema oscuro. Capturas e informe PDF revisados visualmente. Detalle: `docs/seeds2/VERIFICACAO_PISO1.md` §0.
- **Sin CI**: nada fue reejecutado de forma independiente.

## 3. Decisiones (con origen)

- **Responsable (misión "Refinamiento del Piso 1"):** separar inventario permanente de condiciones de simulación; una sola microrred; textos de la app en portugués; sin integraciones externas (geocodificación, cuentas, sincronización con ModelLab).
- **Claude Code (técnica, a revisar):** migración explícita del documento con `legacy` para lo no reinterpretable; ids de arranjos migrados determinísticos (`arr-<id del equipo>`); límites de SOC 20/80 sólo como "sugerido"; reportlab con Helvetica (repertorio cp1252, sin fuentes externas); dispositivo ModelLab importado marcado como no representable hasta decisión científica; límites de backup ampliados (64 entradas / 256 MiB) para admitir paquetes ModelLab.
- Decisiones anteriores (Piso 1) siguen vigentes: SQLite local, revisiones inmutables, simulación sólo con la configuración **guardada**, sin autenticación en este piso.

## 4. Pendencias / observaciones

- Hallazgo de la corrección: `Connection.backup()` desde la **misma** conexión que retiene `BEGIN IMMEDIATE` queda en espera infinita (CPython reintenta BUSY/LOCKED sin límite); por eso la copia usa otra conexión y un `progress` con plazo. No volver a ese patrón.
- En modo journal no-WAL un lector abierto impide el commit de cualquier escritor (comportamiento de SQLite); el store siempre abre en WAL.

- **Decisión científica:** cómo (y si) usar el perfil V–I calibrado del ModelLab en la simulación; hoy sólo se registra.
- **Decisión metodológica (Marília):** equipos heterogéneos de una misma tecnología (incl. arranjos FV distintos) y más de una unidad térmica en el EMS; hoy son excluidos con motivo.
- Importación/exportación con la red y tarifas: no modelado.
- Capturas `fullPage` limitadas al viewport (Streamlit rola en un contenedor interno); partes largas capturadas por elemento.
- Comparación visual lado a lado con PEMFC ModelLab no generada (ejecutar código de otro repositorio no autorizado).
- Heredadas: MIX inaccesible desde la navegación; `__pycache__/` versionado; README histórico V1.5; sin autenticación/roles; sin CI.

## 5. Próxima misión propuesta — Piso 2: Centro de Operação

**No implementada ni autorizada.** Partir de `MicrogridStore` + `adapter` + `run_conditions` sin reconstruir la Gestão: estrategias EMS y escenarios sobre la configuración persistida, histórico de rodadas comparables por revisión y condiciones de rodada. Requiere aprobación del prompt maestro y las decisiones de la sección 4.

## 6. Ritual de actualización al final de cada misión

Actualizar **este archivo en el mismo PR** con: fecha, versión/rama, PR y commit, alcance y archivos, tests realmente ejecutados y resultados, decisiones confirmadas, limitaciones/pendencias, próxima misión recomendada. Separar claramente **implementado**, **validado**, **propuesto** y **bloqueado**; sustituir el relato anterior resumidamente, preservando enlaces históricos. Nunca incluir contraseñas, tokens o datos sensibles.

**Histórico:** PR [#1](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/1) — tests UI V1.6 + `CLAUDE.md` (merge `5ffe2ee`). PR #2 — protocolo de relevo (`f70dd94`). PR [#3](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/3) — SEEDS2 v2.0 Piso 1 (merge `67a7a6f`; 120 passed reportado entonces).

**Lectura obligatoria al entrar:** `CLAUDE.md` → este `HANDOFF.md` → estado real de `main` y PRs recientes. En caso de conflicto, reportar; no improvisar decisión científica.
