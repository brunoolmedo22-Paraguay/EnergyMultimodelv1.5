# SEEDS2 — Cuaderno de relevo entre agentes (HANDOFF)

> **Fuente de continuidad operativa.** Leer junto con [CLAUDE.md](../../CLAUDE.md) antes de comenzar cualquier sesión. Mantener breve, con hechos verificables, fecha y referencias a PRs. El código y los tests son la fuente de verdad funcional.

**Actualización:** 2026-11-05 · **rama:** `claude/seeds2-piso1-microrrede` · **PR [#3](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/3)** (pendiente de revisión; sin merge) · **estado:** SEEDS2 v2.0 — Piso 1 implementado y verificado en la rama; **no integrado en `main`**.

## 1. Estado actual

- `main` (`f70dd94`): base V1.6 + PR #1 (tests UI V1.6, `CLAUDE.md`) + PR #2 (protocolo de relevo).
- Rama `claude/seeds2-piso1-microrrede` (PR #3): **Piso 1 — configuración e instalación de una microrrede** (PR de esta misión; ver sección 2).
- Arquitectura: `app.py` → shell `seeds2/ui/` (Comissionamento → Início · Gestão da Microrrede · Simulação · Resultados · Alcance); Simulação/Resultados embeben el console V1.6 (`orchestrator_app.py`). Backend sin UI en `seeds2/microgrid/` (referencias, documento/validación, SQLite, adaptador). Detalles: `docs/seeds2/ARQUITETURA_PISO1.md`.
- EMS y modelos científicos **sin cambios**. No presentar la aplicación como operación en tiempo real ni validación física experimental.

## 2. Última entrega — Piso 1 (esta rama)

**Implementado**
- Una microrred por instalación: tabla `microgrid` con `CHECK (id = 1)`, identidad estable (`installation.uid`), sin proyectos/selector/duplicación.
- Comissionamento en 5 etapas (identificación, inventario, configuración eléctrica, parámetros/demanda, revisión y activación), guardado por etapa, retomable tras reinicio.
- Inventario: PV, eólica, batería, PEMFC, térmica; varias unidades por tecnología; IDs `eq-…` estables; habilitar/deshabilitar; retirar con auditoría (`retired[]`); estados *registrado → configurado → compatible*; referencias de los catálogos existentes con procedencia; ningún valor físico presumido.
- Topología declarativa de barramento común + esquema SVG generado de los datos (sin flujo de potencia; conexión a red marcada como no modelada por el EMS).
- Demanda (walk-forward, COPEL B1, CSV almacenado con SHA-256 y ventana) y clima (sintético explícito o CSV), con procedencia y convenciones.
- Persistencia SQLite en `SEEDS2_DATA_DIR` (def. `~/.seeds2`): revisiones inmutables, concurrencia optimista, transacciones, migraciones versionadas (`.bak-v<N>`), backups ZIP verificables y restauración con confirmación. `docs/seeds2/ARMAZENAMENTO.md`.
- Adaptador inventario → `model_spec` V1.6: agrega solo lo físicamente equivalente; identifica no representables (heterogéneos, >1 térmica, usina de gran porte), nunca omite; exige confirmación de exclusiones; registra cada rodada (`simulation_runs`) con revisión e impresiones digitales; marca resultados obsoletos; detecta edición manual en páginas V1.6.
- Kit visual propio con la identidad de PEMFC ModelLab (`.streamlit/config.toml` teal claro/oscuro, `st.components.v2`).

**Cambios en archivos existentes (mínimos):** `app.py` (CSS V1.6 solo en vistas V1.6; entrada al shell), `orchestrator_app.py` (gate de ejecución, `origem`, hook post-rodada), `orchestrator_runtime.py` (`origem_configuracao` en el ZIP), `requirements.txt` (`streamlit==1.66.1`, resto igual), `tests/apptest_utils.py` y un test V1.6 (abren el console dentro de Simulação con una microrred fixture).

**Validado (por Claude Code, en esta rama)**
- `python -m pytest tests/ -q` → **106 passed, 0 failed, 0 skipped** (+44 subtests; 7 avisos SLSQP preexistentes), dos ejecuciones idénticas. 63 tests previos + 28 backend + 15 UI SEEDS2.
- Rodada EMS real con configuración leída del SQLite = mismo despacho y costo que la configuración por defecto V1.6.
- Navegador real (Chromium): `tools/e2e/e2e_piso1_microrrede.js` con **reinicio del servidor** entre comisionamiento y reapertura; escritorio, tablet (820×1180 / 1180×820, sin scroll horizontal) y tema oscuro. Detalle: `docs/seeds2/VERIFICACAO_PISO1.md`.
- **Sin CI**: nada de esto fue reejecutado de forma independiente.

## 3. Decisiones (con origen)

- **Directriz del responsable (prompt maestro Piso 1):** una instalación = una microrred. *Sustituye* la propuesta anterior de este cuaderno ("cadastro/**seleção**/edição"), que se descarta.
- **Claude Code (técnica, a revisar):** SQLite local; documento JSON versionado + revisiones inmutables; Streamlit 1.66.1 (misma versión que ModelLab) para `st.components.v2`; edición pendiente explícita en Gestão (guardar/descartar) y autoguardado en comissionamento; la simulación usa solo la configuración **guardada**.
- Sin autenticación/perfiles en este piso (documentado como limitación de despliegue).

## 4. Pendencias / observaciones

- **Decisión metodológica (Marília):** representar en el EMS equipos heterogéneos de una misma tecnología y más de una unidad térmica; hoy se identifican como no representables.
- Importación/exportación con la red y tarifas: no modelado (declararlo solo queda registrado).
- Perfiles calibrados de PEMFC ModelLab: arquitectura preparada (`references.py` + adaptador), **no implementado**; no inventar dinámica/BoP.
- Usina termelétrica de gran porte solo en la bancada; runtime integrado usa la pequeña unidad.
- MIX (`mix_app.py`) sigue inaccesible desde la navegación (decisión pendiente desde PR #1).
- `__pycache__/` versionado (nuevo `.gitignore` evita nuevos; limpieza pendiente). README histórico V1.5 (aviso SEEDS2 añadido).
- Autenticación/roles para despliegue corporativo; CI (GitHub Actions solo para tests) aún no configurado.
- Orígenes de rodada `manual` (ediciones en páginas V1.6) se registran pero no se vinculan a la microrred: evaluar si el Centro de Operação debe bloquear ese modo.

## 5. Próxima misión propuesta — Piso 2: Centro de Operação

**No implementada ni autorizada.** Partir de `MicrogridStore` + `adapter` sin reconstruir la Gestão: estrategias EMS y escenarios sobre la configuración persistida, histórico de rodadas comparables por revisión, y decisiones de Marília sobre equipos heterogéneos. Requiere aprobación del prompt maestro.

## 6. Ritual de actualización al final de cada misión

Actualizar **este archivo en el mismo PR** con: fecha, versión/rama, PR y commit, alcance y archivos, tests realmente ejecutados y resultados, decisiones confirmadas, limitaciones/pendencias, próxima misión recomendada. Separar claramente **implementado**, **validado**, **propuesto** y **bloqueado**; sustituir el relato anterior resumidamente, preservando enlaces históricos. Nunca incluir contraseñas, tokens o datos sensibles.

**Histórico:** PR [#1](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/1) — tests UI V1.6 + `CLAUDE.md` (merge `5ffe2ee`, 63 passed reportado por Claude Code). PR #2 — protocolo de relevo (`f70dd94`).

**Lectura obligatoria al entrar:** `CLAUDE.md` → este `HANDOFF.md` → estado real de `main` y PRs recientes. En caso de conflicto, reportar; no improvisar decisión científica.
