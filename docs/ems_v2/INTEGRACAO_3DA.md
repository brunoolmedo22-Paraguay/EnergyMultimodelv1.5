# Piso 3D-A — Integración operativa del EMS V2 jerárquico MILP–MPC en SEEDS2

**Rama:** `claude/adoring-newton-jzfmfx` · **Base:** `main` `a636350271fa35a9e20d000f2d2121502c132913` · **Estado:** GATE 0 + GATE 1 (3D-A) del paquete maestro del Piso 3D. PR contra `main`, **sin merge**. 3D-B/3D-C/3D-D **no iniciados**.

> **Alcance científico.** Lo que se integra es una **simulación offline de lazo cerrado, algebraica, en contexto de ensayo**: el controlador jerárquico decide con la previsión declarada y una planta algebraica realiza cada intervalo. *Microrred real* significa **configurada y guardada en el Gestor de SEEDS2**; no es control de hardware, telemetría SCADA, validación física ni factura real. Toda entrada sintética queda rotulada como sintética en el preflight, el manifiesto y los registros.

## 1. Qué cambia y qué no

| | |
|---|---|
| **Nuevo** | Paquete `integracao_v2/` (capa de integración): `estrategia` (bloque declarativo `milp_mpc` del escenario), `montagem` (escenario → contratos del motor), `preflight` (preflight V2), `execucao` (runner V2), `registro` (evidencia persistida y reapertura), `ui` (controles mínimos Streamlit). |
| **Modificado (4 archivos de aplicación)** | `seeds2/operation/scenarios.py` (claves opcionales `engine` / `milp_mpc`), `seeds2/operation/preflight.py` (el preflight V1.6 **rechaza** escenarios que seleccionan el V2), `seeds2/ui/execution_ui.py` (despacho por motor), `seeds2/ui/archive_ui.py` (estrategia V2 y costo rotulado en estudios archivados). |
| **Intacto (byte a byte)** | `ems_v2/` completo (árbol Git `58cc13b…` idéntico a la base: formulación MILP, planificador, MPC, costo futuro, política numérica, fixtures, referencias); V1.6 (`models/`, `h2_pemfc/`, `simulation/`, `config/`, `ems_integration/`, `orchestrator_*.py`, `app.py`); `seeds2/operation/runner.py`, `seeds2/microgrid/`, `seeds2/archive/`, `seeds2/report/`; `requirements*.txt`; esquema SQLite (v4) y formato `seeds2-study` v1. |

Dependencias en un solo sentido: `seeds2` (aplicación) → `integracao_v2` (coordinación, import tardío) → `ems_v2` (motor). `seeds2` sigue sin contener el literal `ems_v2`; `ems_v2` sigue sin importar la aplicación (la excepción C-3C0-01 continúa siendo exactamente `ponte_seeds2/leitor.py`).

## 2. Escenario mínimo reproducible desde el Gestor (GATE 0)

Primera configuración admisible del motor V2: **demanda agregada crítica + 1 o 2 bancos de baterías + PCC declarado** (conectado con tarifa declarada, o aislado declarado). El caso de aceptación reproduce, sobre una microrred **registrada en el catálogo** (documento v2 + `MicrogridRegistry`), las condiciones del experimento analítico de pico futuro: demanda 10 kW × 12 h (Δ = 60 min), banco de 20 kWh (SOC inicial 100 %, límites 0–100 % definidos por la instalación), PCC solo importación 50 kW, tarifa 0,5 R$/kWh con pico 1,5 en las horas 8–9, c_thr = 0,01 R$/kWh, N = 3, m = 1, H_L = 10.

Resultado **analítico** (oráculo independiente del código; la integración no usa `ems_v2.fixtures_3c4` en ningún punto): con costo de continuación el banco se conserva hasta el pico ⇒ 0,5·80 + 0,5·20 + 0,01·20 = **R$ 50,2** (sin coordinación, con N = 3, serían R$ 70,2). La corrida obtiene R$ 50,2, con 12 ventanas óptimas (gap 0) y 12 señales de valor futuro válidas.

No representables en 3D-A (el preflight V2 **bloquea** si están habilitados y disponibles; se pueden declarar *indisponibles* en el escenario para excluirlos solo de esa misión):

| Equipo | Motivo del bloqueo |
|---|---|
| FV / eólica | El potencial **en el barramento por UID** exige aplicar los modelos físicos al clima previsto con semántica de intervalo y emisión declaradas: adaptador no aprobado (brecha 3C-0). |
| PEMFC | Falta P_min, curva q(P) certificada (adenda B04), rampas, permanencias, memoria por unidad y la decisión D05; nada se infiere del V1.6. |
| Térmica | El costo de generación térmica **M19 (CVU) no está implementado** en el núcleo 3C-4: una térmica despachable produciría conclusiones económicas sin costo de combustible. |

## 3. Matriz fuente → transformación → validación → registro → vista

La matriz efectiva de **cada** corrida (con valores, procedencia por campo y transformaciones exactas) se calcula en el preflight, se muestra antes de ejecutar y se graba en el manifiesto (`engine_inputs.matriz`) y en `v2/preflight.json`. Resumen:

| Dato | Fuente | Transformación | Validación | Registro | Vista (3D-B/3D-C) |
|---|---|---|---|---|---|
| Identidad (microrred, encarnación, revisión, escenario/versión, huellas) | `MicrogridStore` (revisión **referenciada** por la versión del escenario) | ninguna | `ler` 3C-0 + coherencia escenario × inventario; `missao_uid` = `run_uid` | manifiesto `reference`; registros sellados (`IdentidadeMissao`) | Encabezado · Análise |
| C_b, s_min, s_max | Inventario (por dispositivo `eq-…`) | % → fracción (conversión exacta registrada) | matriz 3C-0 (un valor solo *sugerido* por SEEDS2 **bloquea**) + `validar_entrada` | `v2/modelo.json` | Parâmetros · Fontes |
| η_c, η_d, P̄_c y P̄_d **en barramento**, hipótesis de autodescarga, c_thr | Bloque `milp_mpc.baterias.<uid>` (declaración con procedencia tipo + fuente) | ninguna (unidad canónica) | dominio en la estrategia + matriz 3C-0 + `validar_entrada` | `v2/modelo.json` | Parâmetros |
| Energía inicial e₀ | SOC inicial del escenario (%) | e₀ = SOC₀ · C_b (registrada en la procedencia) | límites [s_min·C, s_max·C] | `v2/fronteiras.csv` (frontera 0) | Operação · Diagrama |
| Demanda **prevista** (disponible al decidir) | Serie de demanda del escenario (blob SHA-256, Piso 2B) | alineación exacta a la malla; **sin** remuestreo ni interpolación; semántica *media de intervalo* y emisión **declaradas** | `validar_serie`, `alinhar_a_malha`, emisión ≤ τ₀; vínculo al instantáneo K6 en cada ventana | `v2/intervalos.csv` (`demanda_prevista_kW`), `v2/planos.csv` | Operação · Respostas |
| Demanda **realizada** (simulada) | Bloque `milp_mpc.realizacao` (igual a la previsión, o serie declarada) | ninguna | `validar_realizacao` + separación previsión × realización; se entrega **solo** a la planta | `v2/intervalos.csv` (`demanda_realizada_kW`) | Operação |
| PCC: modo, sentidos, límites, disponibilidad | Bloque `milp_mpc.pcc` | series constantes por intervalo | `validar_entrada_3c3` + coherencia con el modo operativo del inventario | `v2/modelo.json` | Parâmetros · Diagrama |
| Tarifas de decisión y de liquidación | Bloque `milp_mpc.pcc` (un valor por intervalo, rótulo obligatorio) | un bloque tarifario por intervalo; perfil de liquidación propio con los mismos valores | `validar_perfil`; selección causal por emisión en cada τ_k | `v2/intervalos.csv` (`tarifa_*`, `preco_*`) | Operação · Análise |
| Malla Δ, N, m, H_L, K_M | Bloque `milp_mpc.malha` + ventana de la misión del escenario | inicio local → UTC por el huso declarado | `validar_malha`, `validar_configuracao_mpc`, `validar_configuracao_planejador` | manifiesto `mission`, `v2/indice.json` | Parâmetros · Respostas |
| Φ_L, señal, degradación, puntos, tolerancias | Bloque `milp_mpc.planejador` | ninguna | `validar_configuracao_planejador`, `validar_termo_declarado` | `v2/modelo.json`, `v2/coordenacoes.json` | Respostas · Análise |
| Solver (límite de tiempo, gaps, threads, semilla) | Bloque `milp_mpc.solver` | ninguna | `milp.config.validar_configuracao` | `v2/janelas.csv` (terminación, gap, tiempos) | Análise |

## 4. Estrategia versionada (`engine` + `milp_mpc`)

Dos claves **opcionales** del documento del escenario (`seeds2-scenario` v1; los escenarios anteriores no las tienen y conservan su huella): `engine` (`legacy_v16` si falta × `milp_mpc_v1`) y `milp_mpc` (bloque `format_version` 1). Viven en la **versión inmutable** del escenario: cada corrida referencia la declaración exacta que usó.

* Los parámetros físicos, económicos y de política empiezan **vacíos** y solo valen cuando se declaran con procedencia (`tipo` + `fuente`). Un bloque incompleto se puede guardar; el preflight V2 bloquea la ejecución listando cada campo ausente (código `nao_declarado`). No hay valor de respaldo.
* Solo los parámetros **numéricos de software** del planificador/solver tienen valor inicial: los de los ensayos 3C-4 auditados, rotulados como tales.
* Políticas **fijas** de la integración 3D-A (declaradas en `montagem.FIXOS` y grabadas en el manifiesto `engine_fixed`): lazo causal simulado, servicio duro, ventana reducida al fin de la misión, toda falla interrumpe, solo solución óptima, latencia de observación 0.
* Un escenario V2 **nunca** se ejecuta con el motor V1.6 (el preflight V1.6 lo rechaza) y viceversa. Solver ausente ⇒ bloqueo explicado, nunca recaída.

## 5. Preflight V2 (distinto del V1.6)

`integracao_v2.preflight.preparar(store, versión_guardada)` — solo lectura; cualquier ítem `erro` impide abrir la corrida:

1. documento del escenario, encarnación, revisión referenciada y su huella;
2. selección explícita del motor V2 y estrategia sin errores ni declaraciones ausentes;
3. clasificación **por UID**: representable × excluido (indisponible) × bloqueante (no representable);
4. coherencia topología del inventario × modo del PCC declarado;
5. malla (duración múltiplo de Δ, m ≤ N, N < H_L ≤ K_M) y series (alineación exacta, causalidad de emisión, tarifas con un valor por intervalo);
6. preflight de la **ponte 3C-0/3C-1** (`preflight_ems_v2`, finalidad `otimizacao`, contexto `ensaio`) **sin relajación**; su informe original y su SHA-256 se graban;
7. contratos 3C-3 / 3C-2 / 3C-4 construyendo el controlador jerárquico sin resolver;
8. ambiente del solver (Pyomo/HiGHS).

## 6. Runner V2 y estados finales

Mismo ciclo de vida y garantías del runner V1.6 (manifiesto inmutable al abrir, `request_id` idempotente, una corrida activa por microrred, thread propio, conclusión atómica). El lazo de la misión es el **del motor** (`executar_missao_simulada`, una ventana por llamada para informar el progreso real); equivalencia con la llamada única verificada por la impresión determinística.

| Estado | Cuándo | Qué se guarda |
|---|---|---|
| `concluida` | Misión **completa** (todos los intervalos aplicados) **y** auditoría integral independiente aprobada | `scenario_run_data` (§7), `summary`, `outcome` |
| `interrompida` | El controlador interrumpió la misión por una falla clasificada (inviable, consigna inexequible…), o el proceso murió | Ningún dato de corrida concluida. Si hubo ventanas: evidencia **parcial** rotulada en `outcome.evidence` (mismos textos canónicos + vistas); el costo parcial nunca se presenta como costo de la misión |
| `falhou` | Solver indisponible en ejecución, excepción, auditoría reprobada | Diagnóstico en `error` (sin resultados concluidos) |

## 7. Contrato de persistencia de una corrida V2 concluida — **lo que consumirá 3D-B**

Formato `seeds2-milp-mpc-run-data` v1; nombres dentro de la whitelist de `seeds2-study` v1 (solo `.csv`, `.json`, `.zip`). Manifiesto: mismo sobre `seeds2-run` v1 con la clave nueva `engine` (`id = milp_mpc_v1`; ausente = V1.6).

| Archivo | Papel | Contenido |
|---|---|---|
| `v2/registros_selados.zip` | **fuente canónica** | Texto canónico exacto de todo registro sellado del motor: ventanas MPC (cadena), registros 3C-0, anexos 3C-3, coordinaciones 3C-4, libro K6, registros de misión MPC / red / jerárquico. ZIP determinístico. |
| `v2/modelo.json` | fuente canónica | `EntradaRede3C3` de la misión (parámetros efectivos con procedencia por campo) + configuraciones MPC, red y planificador; reconstruibles y conferidos por los hashes sellados. |
| `v2/intervalos.csv` | vista derivada | **N filas** (intervalos aplicados): demanda prevista/realizada/atendida/no atendida, `"<uid>|P_c_kW"` y `"<uid>|P_d_kW"` por banco, PCC programado × realizado × desvío × medido, tarifas de decisión y precios de liquidación, costos por componente y acumulado, residuo de balance. |
| `v2/fronteiras.csv` | vista derivada | **N + 1 filas** (fronteras de estado): `"<uid>|energia_kWh"` y `"<uid>|soc"`. |
| `v2/janelas.csv` | vista derivada | Una fila por ventana: N_k, m_k, desenlace, clase de falla, terminación/estado del solver, objetivo, límite dual, gap, tamaño del modelo, costo operativo previsto, **costo futuro estimado**, planificado × realizado, situación/origen/calidad de la señal, evaluaciones del planificador, tiempos. |
| `v2/planos.csv` | vista derivada | Plan de cada ventana × intervalo del horizonte (consignas y energías planificadas) con la marca `aplicado`. |
| `v2/coordenacoes.json` | vista derivada | Coordinaciones 3C-4 completas: señal V(E) por modo (puntos, dominio, convexidad), calidad, validaciones, término aplicado, degradación, plan largo. |
| `v2/auditoria.json` | auditoría | Veredicto, verificaciones y constataciones de `auditar_missao_hierarquica` (independiente del MILP). |
| `v2/preflight.json` | contexto | Informe del preflight V2 + matriz + informe de la ponte. |
| `v2/indice.json` | índice | Papeles, SHA-256, diccionario de columnas (unidad, tipo de muestra intervalo/frontera/ventana, signo, origen sellado × derivado), convenciones y limitaciones. |

Convenciones (grabadas en el índice): potencias en kW **líquidos en el barramento**, medias de intervalo; descarga/importación inyectan (≥ 0), carga de batería/exportación/demanda consumen (≥ 0) — **la carga de batería nunca es generación**; N intervalos y N + 1 fronteras; energía = potencia × Δ; costo **realizado** sin valor futuro; instantes en UTC.

`summary` de la corrida: `{"engine": "milp_mpc_v1", "mission": {…indicadores leídos de los registros sellados…}, "execution": {…}}`. `mission` incluye `custo_realizado_total_R`, componentes, `custo_realizado_inclui_valor_futuro = false`, energías demandada/atendida/no atendida/importada/exportada, por banco (energía y SOC inicial/final, cargada/descargada), conteos de señal, estadísticas del solver.

**Lo que NO se registra (y por tanto 3D-B/3D-C no deben dibujar):** trayectoria de convergencia de HiGHS; restricciones activas o precios duales; flujos por rama; motivaciones textuales de las decisiones (solo existen restricciones, señales y comparaciones realmente calculadas).

## 8. Reapertura sin recalcular

`integracao_v2.registro.verificar(source, run)` — `source` es el `MicrogridStore` o un `StudyView` del Archivo Científico (mismo contrato `run_data`). No importa Pyomo/HiGHS:

1. SHA-256 de cada ítem contra el registro de la corrida y contra el índice;
2. reconstrucción estricta de los registros sellados (`de_json`) y del modelo (`de_dict`);
3. identidad: `missao_uid` = `run_uid`; microrred, escenario/versión/huella, revisión/huella = los de la corrida; hashes del modelo/configuraciones = los comprometidos en el manifiesto **antes** de ejecutar;
4. **vistas regeneradas** de los registros sellados idénticas byte a byte a las grabadas; `summary` = resumen recalculado;
5. **auditoría integral independiente** (cadena, K6, causalidad, estado, balance, costos, coordinaciones) aprobada de nuevo.

La interfaz muestra el resultado de esta verificación al abrir cada corrida V2 (local o archivada).

## 9. Contradicciones y decisiones de integración (para auditoría)

* **C-3DA-01 — guardias «la aplicación no referencia `ems_v2`» × integración autorizada.** Las guardias de 3A–3C-4 eran verdaderas mientras la integración no estaba autorizada. Resolución: (a) la capa de integración vive en su **propio paquete** `integracao_v2/`; `seeds2` sigue sin el literal `ems_v2`, de modo que la guardia 3C-4 `test_aplicacao_nao_importa_o_ems_hierarquico` (congelada por la política eólica, cuya evidencia no se re-fija) permanece **idéntica y verdadera en su letra** — su intención original («ninguna integración») queda **superada por la autorización del responsable** y se declara aquí, no se oculta; (b) la guardia 3A `test_aplicacao_nao_referencia_ems_v2` conserva la exploración global con una excepción **nominal** (paquete de integración + 4 archivos de test); (c) el filtro nominal `tests/ems_v2/piso3da_guard_policy.py` (nombres y estados exactos; sin directorios ni patrones) se encadena en `stabilization_guard_policy.filter_maintenance_changes`, el mismo mecanismo que usó CI-01. Ninguna guardia global se elimina; ningún archivo fijado por hash por políticas anteriores se toca. Auditoría explícita del diff: `python tests/ems_v2/piso3da_guard_policy.py`. **Requiere aprobación del responsable.**
* **C-3DA-02 — puente 3C-0 × topología 3C-3.** `ponte.projecao` proyecta el modo operativo «conectada» como topología que el contrato 3A rechaza; en 3C-3 la base debe declarar el barramento interno (`isolada`) y la interconexión vive solo en el embrulho (C-3C3-01 del propio motor). La integración entrega al puente un **inventario efectivo** con `modo_operacao = "isolada"` (registrado en sus observaciones); el modo real de la instalación se valida contra el PCC declarado y queda en el manifiesto. No existe un puente 3C-3 en `ems_v2`; no se modificó el motor.
* **C-3DA-03 — declaraciones V2 en el escenario, no en el inventario.** El inventario del Piso 1 no tiene η, potencia en barramento ni autodescarga, y `seeds2/microgrid/config.py` está fijado por hash (política eólica). Las declaraciones se guardan en la estrategia versionada del escenario, por UID y con procedencia por campo, vinculadas a la revisión del inventario. Migrarlas al inventario es una decisión futura del responsable.
* **C-3DA-04 — `seeds2-study` v1 no admite datos en corridas no concluidas.** La evidencia de una misión interrumpida se guarda en `outcome.evidence` (JSON), rotulada parcial; no se cambió el formato del Archivo.
* **C-3DA-05 — vocabulario del contrato 3C-2/3A.** El proveedor de la previsión del escenario se registra con la naturaleza `sintetico_conhecido` (única del contrato para una tabla declarada por anticipado); la procedencia real de la serie (medida/sintética/referencia) va por separado. La clase de demanda agregada, el PCC, sus medidores virtuales y el contrato usan UIDs `syn-…`: son entidades **declaradas en la estrategia**, no equipos `eq-…` del inventario.
* **C-3DA-06 — runner V1.6 fijado por hash.** El runner V2 es un módulo separado que reutiliza el registro de corridas vivas, el dueño de proceso y la exclusión mutua del runner V1.6 (una sola fuente de verdad para `owner_is_dead`).
* **C-3DA-07 — autodescarga.** El puente 3C-0 no proyecta λ; solo se admite la hipótesis declarada α = 1.

## 10. Limitaciones conocidas

* Solo contexto de **ensayo**: no existe fuente de realización medida ni operación online; el contexto `operacional` del puente se rechaza.
* Solo demanda agregada crítica + hasta 2 bancos + PCC; Δ debe ser igual al paso de la serie de demanda; una sola clase de demanda; tarifas con un valor por intervalo; PCC siempre disponible (declarado).
* Sin reanudación de misiones interrumpidas (los puntos de retomada del motor no se persisten); un proceso muerto deja la corrida `interrompida` sin resultados.
* Los informes PDF/Excel/figuras del Piso 2D-B **no** cubren corridas V2 (rechazo explícito por recurso ausente); los datos íntegros se descargan de la corrida y viajan en el `.seeds2study.zip`.
* No se registra convergencia de HiGHS, duales ni flujos por rama. La auditoría de no-anticipatividad por intervención del motor (`verificar_nao_antecipatividade`) no se ejecuta en cada corrida (se cubre con un test de intervención).
* Tolerancias del auditor provisorias (D07); SHA-256 no es firma digital; tiempos de reloj no reproducibles.
* Presupuesto computacional del planificador (B3C4-05): misiones limitadas a 336 intervalos.
