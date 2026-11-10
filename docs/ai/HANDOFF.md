> **Estado combinado del PR #18:** PR #17 / 3C-4 ya integrado en main `19aa3ac328f337e31ec4c36baa837c056299a57a`. Se conserva íntegro a continuación su HANDOFF científico original como registro de la entrega. La ampliación eólica permanece en revisión en PR #18, sin merge en main; cierre y nueva regresión en [INTEGRACAO_3C4_PR18.md](../eolica/INTEGRACAO_3C4_PR18.md).

# SEEDS2 — Cuaderno de relevo entre agentes (HANDOFF)

> **Fuente de continuidad operativa.** Leer junto con [CLAUDE.md](../../CLAUDE.md) antes de comenzar cualquier sesión. Mantener breve, con hechos verificables, fecha y referencias a PRs. El código y los tests son la fuente de verdad funcional.

**Actualización:** 2026-11-09 · **rama:** `ccr-50f8fad7-s073ob` · **PR:** [#17](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/17) contra `main`, sin merge · **auditoría del PR #17 (commit `9630e73`): A01, A02 y hotfix B3C4-01 aplicados en `c964a2e`; 2ª auditoría (HEAD `8f48aed`): hotfix autorizado B3C4-10 aplicado en `8efc927`; cierre A03 (HEAD `8dd8edb`) en `322ffa6`** · **estado:** **Piso 3C-4 — EMS jerárquico MILP–MPC (planificador de largo plazo, costo de continuación y valor futuro)** implementado y verificado en la rama; **no integrado** (sin UI/runtime/catálogo; algebraico, fixtures y tarifas sintéticas). **No iniciar 3D.**

> **Informe técnico vigente: [`PARAMIJEFE.md`](../../PARAMIJEFE.md) — Entrega 12**; formulación, método, decisiones D-3C4-* y contradicciones C-3C4-* en [`docs/ems_v2/FORMULACAO_3C4.md`](../ems_v2/FORMULACAO_3C4.md); trazabilidad y hashes protegidos en [`MATRIZ_3C4.md`](../ems_v2/MATRIZ_3C4.md); evidencia en [`EVIDENCIA_3C4_EJECUCION.md`](../ems_v2/EVIDENCIA_3C4_EJECUCION.md); brechas en [`BRECHAS_3C4.md`](../ems_v2/BRECHAS_3C4.md); transición en [`TRANSICAO_3C4_3D.md`](../ems_v2/TRANSICAO_3C4_3D.md).

## 1. Estado actual

- `main` (`10365c5`): V1.6 + PR #1–#16 (3A, 3B-P, 3C-0, 3C-1, 3C-2 y 3C-3 integrados). Línea de base `tests/ems_v2` medida en esta sesión antes de cambiar nada: **1080 passed** (con `requirements.txt` + `requirements-ems_v2.txt` instalados).
- Rama `ccr-50f8fad7-s073ob` desde `main`: **Piso 3C-4** (sección 2). Desde `10365c5` NINGÚN archivo existente de `ems_v2` fue modificado; solo 4 guardias de tests ajustadas nominalmente (C-3C4-02). V1.6, `seeds2`, aplicación y `requirements*.txt` intactos; la aplicación no referencia `ems_v2`.

## 2. Última entrega — Piso 3C-4 (esta rama)

- **Implementado:** `ems_v2/hierarquia/` (solo biblioteca estándar): `contrato` (TermoTerminal3C4, SinalValorFuturo sellado, EntradaHierarquica3C4, ConfiguracaoPlanejador3C4, validaciones de señal × entrada × ventana), `valor` (evaluación exacta: interpolante 1D, envolvente 2D, lineal local), `auditor` (auditor terminal independiente), `planejador` (plan largo + V^tail por reoptimización paramétrica auditada, PWL con refinamiento y dominio de factibilidad, 2D convexo verificado, sensibilidad local, referencias), `mpc` (`ControladorMPCHierarquico`, `ResolvedorMILP3C4`, registros de coordinación/vínculo/misión), `auditoria` (auditoría integral + retomada verificada), `comparadores` (reoptimización × anticipación × información perfecta con condiciones terminales), `experimentos`; `ems_v2/milp/{modelo,solver,resultado,evidencia}_3c4.py`; `ems_v2/fixtures_3c4.py`.
- **Verificado (2026-11-09):** 101 tests nuevos (`tests/ems_v2/test_ems_v2_3c4_*.py`); `tests/ems_v2` **1181 passed** (sin Pyomo: 794 passed, 42 skipped); suite completa **1635 passed, 7 warnings, 128 subtests** (445,4 s) = 1534 + 101. Evidencia: `python -m ems_v2.milp.evidencia_3c4` (salida en `EVIDENCIA_3C4_EJECUCION.md`).
- **Resultados clave (sintéticos):** H2 anticipación R$ 10,2 con condiciones terminales iguales (60,4 × 50,2); H1/H3 ⇒ 0; H7/H8 (tarifa plana, límite/indisponibilidad del PCC) MPC sin señal INVIABLE × jerárquico concluye; H17 dos bancos R$ 5,3; reoptimización 0 en todas las instancias; local indisponible en quiebres.
- **Hallazgos:** C-3C4-01 (visión núcleo `ResultadoNucleo3C3De3C4`), C-3C4-02 (guardias nominales), **C-3C4-03 / B3C4-01: deriva numérica HEREDADA de la energía ejecutada (C + 2 ulp) que la validación sin recorte convierte en interrupción — NO corregida, requiere autorización** (reproducida en `test_h9_linha_de_base_*`), C-3C4-04 (campo 3C-0 `valor_futuro` intacto). B3C4-02: `cumprir_na_janela` cuesta R$ 2,0 en H9.
- **Auditoría del PR #17 (commit `9630e73`; arquitectura favorable)** — los tres defectos reproducidos antes de corregir (EVIDENCIA_3C4 §4):
  - **A01:** el registro final de misión re-sellado con contagens/energías/valoración/hash de red/`missao_uid`/tiempos falsos pasaba la auditoría integral; ahora cada campo se confronta con su fuente (objetos de configuración obligatorios; tiempos = suma de mediciones selladas, no reproducibles).
  - **A02:** `inviavel` solo con certificado de cobertura (MILP con energía inicial libre, `resolver_cobertura_3c4`); sin él `dominio_indeterminado` ⇒ señal indisponible; `diagnostico_modos`; dominio = aproximación interna; convexidad 2D "en la muestra".
  - **B3C4-01 (hotfix AUTORIZADO):** proyección numérica de la energía al límite si exceso ≤ min(tolE, 16·u·S), reconstruible bit a bit; archivos protegidos modificados: `ems_v2/ponte/execucao.py`, `ems_v2/rede/execucao.py` (guardia de diff). E1–E8/G1–G15/3C-0/3C-1 idénticos.
  - **B3C4-10:** `P_imp = −8,88e-16` del solver rechazado por la regla C-01 del 3C-3 ⇒ H9 3C-3 sin señal y referencia dura se detenían en k = 10 (corregido en la 2ª auditoría, abajo).
  - Verificado: suite `test_ems_v2_3c4_auditoria_pr17.py` 38 passed; 3C-4 139 passed; `tests/ems_v2` **1220 passed (= 1181 + 38 + 1 guardia del hotfix)** (sin Pyomo 812 passed, 63 skipped); suite completa **1674 passed, 7 warnings, 128 subtests (449,9 s) = 1635 + 39**.
- **2ª auditoría del PR #17 (HEAD `8f48aed`) — hotfix AUTORIZADO B3C4-10 (`8efc927`):** política `residuo_numerico_pcc_v1` SOLO en la extracción de `resolver_3c3`/`resolver_3c4`: v < 0 del SOLVER con |v| ≤ min(16·u·S_t, 1e-7, tolP D07) ⇒ 0,0 con registro (resultado, resolución sellada, registro 3C-0 aviso + hash) y reconstrucción en la auditoría (`reconstruir_normalizacoes_pcc`); mayores ⇒ solución rechazada. **C-01 idéntica a la base** (guardia AST): consignas/programas externos negativos/NaN/Inf/bool/incompletos siguen rechazados. Protegidos modificados: `rede/execucao.py`, `milp/solver_3c3.py`, `milp/resultado_3c3.py`, `rede/mpc.py` (FORMULACAO_3C4 §10c). H9 × 5: todas concluyen con E = 0, PEMFC encendida, sin obligaciones; sin señal 129,8; PWL/dura/blanda 129,6; horizonte completo 127,6 (brecha 2,0 = B3C4-02). Verificado: nueva suite 66 passed; `tests/ems_v2` **1287 passed** (sin Pyomo 859 passed, 83 skipped); suite completa **1741 passed, 7 warnings, 128 subtests (451,8 s)**.
- **Cierre C-3C4-A03 (HEAD `8dd8edb`, `322ffa6`):** A03-1 — las tres evidencias de una normalización (código en la resolución sellada, avisos y hash en el registro 3C-0) todas presentes y coherentes o todas ausentes; A03-2 — verificador único `rede/auditoria.reconstruir_normalizacoes_pcc` (sin dependencia de `hierarquia`) en la auditoría integral 3C-3 (sección `normalizacoes_pcc`), reutilizado/espejado por la 3C-4. Política B3C4-10 y C-01 intactas (guardia contra `8dd8edb`); registro histórico G11 de `10365c5` aceptado sin obligación nueva. Verificado: suite A03 18 passed; `tests/ems_v2` **1308 passed** (sin Pyomo 862 passed, 101 skipped); suite completa **1762 passed, 7 warnings, 128 subtests (458,3 s)**.
- **Decisiones:** D-3C4-01..08 (FORMULACAO_3C4 §10).
- **No implementado (fuera de alcance):** >2 bancos o 2D no convexo, incertidumbre estocástica del valor futuro, segunda resolución temporal, modos con obligación residual elegible, integración (3D).

## 3. Próxima misión propuesta

Re-auditoría del PR #17 tras el cierre A03 y decisión de integración por el responsable (sin merge automático). 3D (integración con catálogo/UI/runtime) **no autorizado**; interfaces en `TRANSICAO_3C4_3D.md`.

---

## Histórico — entrega anterior: Piso 3C-3 · Red eléctrica e intercambio (PR #16, integrado en `10365c5`)

- `ems_v2/rede/` (PCC, tarifas, auditor, ejecución programado × realizado, anexo 3C-3, MPC conectado, retomada, auditoría integral/analítica) + `ems_v2/milp/*_3c3.py` + `ems_v2/fixtures_3c3.py`; correcciones C-01/C-02/C-03 de la auditoría aplicadas. Verificado entonces: `tests/ems_v2` 1080 passed; suite 1534 passed. Informe: `PARAMIJEFE.md` Entrega 11.

## Histórico — entrega anterior: Piso 3C-2 · MPC recedente (PR #15, integrado en `a4c6b1c`)

- `ems_v2/mpc/` (reloj, K6, previsión por ventana, orquestador, registros, retomada, auditoría, métricas, comparadores, E1–E8) + `ems_v2/fixtures_3c2.py`; correcciones C-01/C-02 de la auditoría aplicadas. Verificado entonces: `tests/ems_v2` 824 passed; suite 1278 passed. Informe: `PARAMIJEFE.md` Entrega 10.

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


## Missão eólica Codex — catálogo de sete equipamentos e potência de referência × pico

Base verificada `10365c5478b4dd137906b58819cd7f71d8de9cea`, rama exclusiva `codex/eolica-siete-curvas-potencias`. Autorização explícita do usuário para ciência eólica; não é parte do Piso 3C-4 de Claude. Nenhum arquivo EMS alterado nesta implementação. Sem merge.

Catálogo único com 13 entradas: três tabelas de fabricante (Vergnet C275, V47 de um gerador, V52 OptiSpeed 104,2 dB(A)) simuláveis em domínio restrito; quatro tabelas secundárias (Excel 10/15, e400nb, SWIFT) disponíveis para análise fiel, mas integração energética bloqueada até cotejo primário/densidade/variantes e contabilidade no balanço. Não se recortam os picos à referência e não se apagam negativos. Domínio real/equivalente explícito, sem extrapolação nova. Os seis registros e saídas históricas são exatamente iguais nos perfis fixados antes da implementação.

Dossier: [formulação](../eolica/FORMULACAO_POTENCIA_REFERENCIA_MAXIMA.md), [rastreabilidade](../eolica/RASTREABILIDAD_7_EQUIPOS.md), [validação](../eolica/VALIDACION_7_EQUIPOS.md), [resultados](../eolica/RESULTADOS_REGRESION.md). Pacote Work original preservado com sete CSV e fontes; validador `python -m tools.validate_wind_catalog` não transforma integridade numérica em certificação.

110 testes novos passaram. Duas provas históricas foram delimitadas aos seis originais com autorização expressa, preservando asserções. Três guardias antigas que proíbem qualquer edição eólica foram identificadas; o resultado integral e o eventual ajuste autorizado estão em RESULTADOS_REGRESION.md. Pendência de rede para informes primários/API GitHub. Não sobrescrever nem reinterpretar entregas EMS anteriores com esta seção.


### Missão eólica — autorização posterior para três guardias nominais

O usuário autorizou expressamente o ajuste EXCLUSIVO das três guardias históricas de ponte/3C-2/3C-3. Foram inseridos filtros por arquivos e estados exatos, mantendo todas as asserções anteriores. Originais em `10365c5` e implementação eólica já publicada em `5bc4283` fixados por SHA-256; nenhum hash regenerado pelo teste. Arquivos autorizados continuam congelados integralmente, e os seis registros históricos também são conferidos por digest e regressão numérica independente.

Nenhum byte de `ems_v2/` mudou; a nova verificação global rejeita alterações e adições EMS, inclusive em caminho 3C-4. A quarta guarda de ausência de integração continua intacta; suporte novo em `tests/ems_v2/`. Lote de guardias/adversariais: **128 passed**. Históricos separados: **12 passed** e **9 passed**. Detalhes e lista nominal completa: [guardias e hashes](../eolica/GUARDIAS_REGRESION_EOLICA.md); resultado integral atualizado em `docs/eolica/RESULTADOS_REGRESION.md`. Não tocar a rama simultânea de Claude; sem merge.

**Regressão final da continuação eólica autorizada:** `1758 passed, 0 failed, 0 skipped, 7 warnings` em `415.84s (0:06:55)`. Nenhum código EMS modificado; PR ainda bloqueado pela API GitHub. Ver `docs/eolica/RESULTADOS_REGRESION.md`.


### C-EOL-01 — PR #18: corregir el alcance temporal de las guardias eólicas

La política anterior congelaba indirectamente todo EMS contra `10365c5`. Se separó la auditoría explícita base/head del PR de las comprobaciones permanentes. Estas mantienen los hashes eólicos y las seis máquinas históricas, pero leen evidencia auditada retenida para las entregas anteriores; permiten cambios EMS de otro PR y no dependen de commits antiguos disponibles localmente. La prueba Git de los subárboles EMS de `10365c5` y `9621543` conserva su identidad sin red.

Lote focalizado **135 passed**; en un clon real de profundidad 1 las guardias ejecutan **14 passed, 0 skipped**, antes y después de integrar centinelas de una rama 3C-4 independiente. Modificar una curva después sigue fallando. Ningún código de producción, curva, parámetro o regla física cambió. Dossier: `docs/eolica/AUDITORIA_C_EOL_01.md`; suite completa en `docs/eolica/RESULTADOS_REGRESION.md`. El PR #18 fue creado externamente; esta corrección se entrega en su misma rama, sin merge. La descripción anterior de una congelación global permanente queda sustituida por C-EOL-01.

**Cierre verificado C-EOL-01:** suite completa **1765 passed, 0 failed, 0 skipped, 7 warnings**, 411,59 s; lote focalizado **135 passed**. Se entrega un commit correctivo en la misma rama del PR #18; sin merge. Producción EMS y física eólica intactas.


## PR #18 — integración combinada con 3C-4 de main

Por autorización expresa, se incorpora `origin/main` en `19aa3ac328f337e31ec4c36baa837c056299a57a` mediante merge en la rama eólica, preservando todos los commits documentales. Se conserva completa la entrega científica 3C-4 de PR #17 y el registro eólico. No se hace merge del PR #18 en main.

Los conflictos de PARAMIJEFE y las tres guardias se resuelven combinando las garantías de ambas entregas: C-EOL-01, ADICOES_3C4 y B3C4-01. La guardia propia de 3C-4 mantiene todas sus comprobaciones científicas ACTIVAS; solo reconoce excepciones eólicas nominales verificadas. La producción `ems_v2/` es idéntica al nuevo main, no al main anterior. La auditoría explícita del diff combinado debe usar `19aa3ac`, nunca exigir igualdad del EMS final frente a `10365c5`.

Nueva regresión y lista completa de archivos respecto de main: `docs/eolica/INTEGRACAO_3C4_PR18.md`. No se reutiliza el resultado 1765 anterior como evidencia combinada. Los seis aerogeneradores históricos y las siete incorporaciones se mantienen intactos. No se inicia 3D.

**Cierre de la integración combinada:** **2004 passed, 0 failed, 0 skipped, 7 warnings**, 501.77s (0:08:21); 3C-4 **228 passed**, 3C-1/2/3 **545 passed**, sin solver EMS **994 passed/101 skipped** por ausencia de solver y eólica **119 passed**. Conflictos resueltos; producción EMS idéntica al main `19aa3ac`. Detalle y lista completa de archivos relativos al nuevo main en `docs/eolica/INTEGRACAO_3C4_PR18.md`.


## Estabilización integral posterior a PR #17/#18 — 2026-11-10

Base comprobada `5e6267833538716678125ab962fc645cfee53eb0`; rama `codex/estabilizacion-aceptacion-integral`; producción en `02d898d819e752c0ebd89c8564376eb200db33fd`. Transferencia fallida bloqueada con rollback/reintento; manual separado del store; consentimiento de exclusiones vinculado a identidad/revisión; huella cubre preparación V1.6; errores de arranque/térmica controlados. Solo cuatro archivos de aplicación; EMS, modelos, catálogos y datos históricos intactos. Guardias científicas activas; nuevas excepciones nominales verificadas mediante evidencia independiente, sin directorios/tolerancias ni cambios de fixtures anteriores.

Resultado nuevo: **2044 passed / 0 failed / 0 skipped / 9 warnings**; EMS separado **1458 passed**; sin solver real **1598 passed / 101 skips**, con lista individual de 446 casos no ejecutados. Cuatro algoritmos antes/después exactos. Navegador real en seis bancadas y protocolos completos del Gestor, escenarios, reinicios/interrupción, Archivo e informes. P0/consentimiento: 24 verificaciones; catálogo: 103; descargas: 157.

[Dictamen y evidencias](../estabilizacao/VEREDICTO_FINAL.md). Conservados los límites: cuatro eólicas solo curvas, MIX sin enlace normal, V2 experimental sin integración operativa, backup convencional distinto del científico, uso local/de confianza. Rama publicada; API GitHub `Forbidden` impide confirmar la creación del PR. Próximo paso: abrir/revisar el PR y auditoría matemática independiente; **sin merge y sin 3D**. Esta sección no sustituye ninguna entrega científica previa.


## Hotfix CI-01 — reproducibilidad eólica, PR #19 — 2026-11-10

Diagnóstico controlado: con/sin Pyomo/HiGHS los doce hashes y KPI son exactos en la misma CPU; desactivar AVX-512 reproduce seis divergencias weather, máximo 8 ULP / 5.4569682106375694e-12 kW, con los doce KPI exactos. Se conserva el JSON histórico, las curvas y todo código científico. Revisión nominal de la comparación weather: SHA canónico primero; en otra ruta CPU, máximo 16 ULP tanto contra los arrays autenticados por el SHA original como contra Decimal independiente de 80 dígitos; KPI estrictos y boundaries exactos. 31 nuevos adversariales y soporte de guardia con archivos explícitos, sin actualizar hashes anteriores ni tocar las tres guardias históricas/EMS. Validación enfocada: 291 passed; completas y aceptación remota pendientes. [Informe CI-01](docs/estabilizacao/HOTFIX_CI01_REPRODUCIBILIDAD_EOLICA.md) (ruta desde raíz). Misma rama/PR #19, sin merge ni 3D. Esta sección preserva las entregas científicas anteriores.
