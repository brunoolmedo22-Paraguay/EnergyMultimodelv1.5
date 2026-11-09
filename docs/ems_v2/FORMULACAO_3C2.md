# Piso 3C-2 — M23: MPC de horizonte recedente, política de información y límites (entregables B, G, J)

> Implementación: `ems_v2/mpc/` (núcleo solo biblioteca estándar) + adaptador explícito `ems_v2/mpc/adaptador_milp.py`
> hacia `resolver_3c1`. Fixtures sintéticas: `ems_v2/fixtures_3c2.py`. Trazabilidad: [`MATRIZ_3C2.md`](MATRIZ_3C2.md).
> Brechas: [`BRECHAS_3C2.md`](BRECHAS_3C2.md). Transición: [`TRANSICAO_3C2_3C3_3C4.md`](TRANSICAO_3C2_3C3_3C4.md).
> Evidencia: [`EVIDENCIA_3C2.md`](EVIDENCIA_3C2.md) y [`EVIDENCIA_3C2_EJECUCION.md`](EVIDENCIA_3C2_EJECUCION.md).
>
> **Rótulo obligatorio:** simulación causal de lazo cerrado **algebraica** (planta = dublé 3C-1) sobre datos
> sintéticos. No es validación física de la planta, ni control de equipos, ni prueba de tiempo real. El EMS V1.6 sigue
> siendo el único motor operacional; nada de esto está integrado a la aplicación.

## 1. Notación temporal (reutiliza `MalhaTemporal`, 3A)

| Símbolo | Campo | Definición |
|---|---|---|
| Δ | `delta_min` | duración de cada intervalo (s enteros); h = Δ/60 h |
| N | `intervalos_otimizacao` | intervalos de optimización por ventana; H_o = NΔ |
| m | `intervalos_reotimizacao` | intervalos aplicados entre reoptimizaciones; ρ = mΔ; 1 ≤ m ≤ N |
| K_M | `intervalos_missao` | intervalos de la misión; T_M = K_MΔ |
| H_f | `horizonte_previsao_min` | horizonte de previsión, **obligatorio** en el MPC (H_f ≥ NΔ) |
| τ_k | — | frontera global τ_k = τ_0 + kΔ, k = 0…K_M; los estados viven en fronteras, nunca en un intervalo extra |

Ventana j que empieza en τ_k (`relogio.janela_em`): N_k intervalos optimizados, m_k = min(m, K_M − k) aplicados (el
último bloque puede ser < m). El contador global k **nunca retrocede** (`RelogioMissao.avancar` acepta solo
1 ≤ n ≤ m_k) y Σ aplicados ≤ K_M.

### 1.1 Política terminal de la misión (entregable B; especificación v1.0 §13)

| Política | N_k | Validez | Consecuencias |
|---|---|---|---|
| `janela_reduzida` | min(N, K_M − k) | Siempre (no usa previsiones posmisión). Recomendada por la especificación ("N_k = min(N, K_M − k) sin inventar previsiones") | Cada acortamiento queda registrado (`JanelaMPC.reduzida`); con U/D > N_k la ventana final es miope (advertencias 3C-1) |
| `horizonte_estendido_declarado` | N | Solo con cobertura de previsión posmisión **declarada** (`cobertura_pos_missao_min` ≥ máx_k (k + N − K_M)Δ del cronograma nominal) **y verificada en cada emisión** | Intervalos posmisión se planifican pero **nunca** se aplican ni se contabilizan; sin cobertura ⇒ `previsao_invalida` (sin extrapolación ni retroceso silencioso a la ventana reducida) |

La política de permanencia 3C-1 de cada ventana es la **final** si k + N_k ≥ K_M y la **intermedia** en otro caso;
ambas se declaran (`cumprir_na_janela` × `obrigacao_residual_vinculante`, sin defecto). **Ninguna obligación
desaparece por terminar la misión:** el registro de la misión reporta `obrigacoes_pendentes_fim_s`, derivadas de la
memoria EJECUTADA en τ_{K_M} (`memorias_do_estado`); si existen, el desenlace es
`concluida_com_obrigacoes_pendentes` (E2/E4 lo muestran).

## 2. Ciclo recedente (M23)

Para cada ventana (`orquestrador.ControladorMPC`):

1. **Corte informacional.** Se sella τ_k en el libro K6 y se obtiene el instantáneo I_k = {observaciones recibidas con
   `recebido_utc ≤ τ_k`} (corte inclusivo, D-3C2-01).
2. **Estado.** x̂_k = estado EJECUTADO y conciliado en τ_k (con memoria por unidad). Si no está reconstruido ⇒
   `estado_nao_reconstruivel` (no se inventa estimador).
3. **Previsión causal.** El proveedor declarado recibe SOLO el `PedidoPrevisao` (misión, ventana, claves, I_k) y emite
   F_k (`ConjuntoPrevisao` propio), validado (§3).
4. **Entrada 3C-1.** `montar_entrada_janela`: modelo declarado + malla de la ventana + series de F_k + estado/memoria
   de x̂_k por `entrada_de_continuacao` (3C-1). Los hashes de F_k e I_k entran en `base.hashes_fontes`.
5. **Resolución** por el adaptador (`resolver_3c1`) y **aceptación** (§5).
6. **Plan** `plano_de_resultado_3c1(res, e3, indice_fronteira_inicial = k)` y **comandos** `ComandoIntervalo` para los
   m_k primeros intervalos.
7. **Aplicación.** Modo 1: el entorno realiza el intervalo g solo después de recibir el comando de g. Modo 2: los
   comandos quedan emitidos y la confirmación llega después.
8. **Conciliación** en T (§4): solo intervalos con confirmación `aplicada` recibida hasta T **y** observaciones
   obligatorias en I(T) se reconstruyen, con el contrato 3C-0 `executar`/`retomar` (barrera C-02 intacta) y el
   ejecutor algebraico 3C-1.
9. **Cierre**: registros sellados y encadenados; x̂_{k+m_k} = estado conciliado; k ← k + m_k.

La propagación es exactamente M23 con Φ_phys = dublé algebraico 3C-1:

  x̂_{k+m} = Φ_alg(x̂_k, u^{aplicado}_{k:k+m−1}, w^{observado}_{k:k+m−1}),   x_{0|k+m} = x̂_{k+m}.

El estado terminal **planificado** de la ventana (frontera N_k) **nunca** se transporta (E6: plan de la ventana 0
termina con e = 0 kWh; el estado ejecutado en τ_2 es 10 kWh y es el que inicia la ventana 1).

## 3. Política de información y previsión por ventana

Verificaciones en ejecución (`previsao.validar_previsao_janela`, todas bloqueantes ⇒ `previsao_invalida`):

- 3C-0 `validar_previsao`: emisión del conjunto ≤ τ_k; emisión de cada serie ≤ emisión del conjunto; unidad, semántica,
  resolución = Δ, alineación y cobertura de N_k (sin extrapolación);
- claves exactamente las pedidas (UID, magnitud, base del potencial) y cada serie empezando en τ_k con N_k valores;
- **vínculo informacional**: `procedencia.sha256` del conjunto = hash de I_k;
- oráculo (`previsao_perfeita`) solo con misión `ablacao_oraculo` (y viceversa); naturaleza del proveedor coherente;
- independencia: el proveedor no es el proveedor de verdad (identificador) ni declara su fuente sin oráculo.

**Límite de confianza (documentado):** son verificaciones estructurales. Un proveedor que obtuvo la verdad por otro
camino (referencia en memoria) y declara el vínculo correctamente **pasa** en ejecución (test
`test_fuga_deliberada…`). Se detecta después por:

1. **Intervención** (`auditoria.verificar_nao_antecipatividade`): dos verdades iguales en los intervalos < k* y
   distintas después ⇒ toda decisión en τ_k con k ≤ k* debe ser idéntica (hash de I_k, F_k, entrada, plan). La fuga se
   detecta siempre que el valor filtrado difiera entre las dos verdades; no se detecta si coincide en ambas o depende
   de partes no perturbadas;
2. **Separación 3C-0** con evidencia (`validar_separacao`): procedencia que apunta al SHA-256 del contenido realizado
   o mismo objeto ⇒ error; igualdad numérica sola ⇒ advertencia (nunca bloqueo).

Proveedores sintéticos (no son pronosticadores validados): `ProvedorTabelaDeclarada` (perfil conocido/programado),
`ProvedorCorrecaoPorObservacao` (perfil base + δ = último valor observado válido − base, piso 0; reemite cuando I_k
cambia) y `ProvedorOraculoAblacao` (lee la realización; solo ablación rotulada, excluida de comparaciones causales).

## 4. K6 — libro de observaciones append-only y reconstrucción del estado

`observacoes.LivroObservacoes` registra **toda** recepción (aceptada o rechazada) con: UID de recurso, magnitud,
intervalo físico [inicio, fin), valor, unidad, procedencia, `recebido_utc`, `evento_uid`, `fonte` + `sequencia`,
revisión (`revisao`, `revisa_evento_uid`), clasificación, `atraso_s`, `tardia_apos_corte`, hash del evento y hash de
cadena (`H(anterior | evento | clasificación | posición)`).

| Situación | Regla (D-3C2-02/03) |
|---|---|
| Faltante | El consumidor recibe `Faltante(…, "ausente")`; nunca cero, última medición ni disponibilidad plena |
| Retraso | Aceptada; `atraso_s = recebido − fin`; usable solo desde su recepción |
| Recibida antes del fin del intervalo | `rejeitada_invalida` (sería información futura) |
| Duplicado | Mismo `evento_uid` y contenido ⇒ `duplicata_identica`; contenido distinto ⇒ `rejeitada_conflito_evento_uid` |
| Conflicto entre originales | `aceita_original_conflitante`: la clave queda **conflictiva** (sin valor) hasta una revisión explícita |
| Revisiones | Evento nuevo con `revisao = r`; r debe ser la siguiente; repetida/salto ⇒ `rejeitada_conflito_revisao`; sin original ⇒ `rejeitada_revisao_sem_original`; el original se conserva |
| Fuera de secuencia | Lagunas: aceptada con nota; número menor que el máximo con evento nuevo ⇒ `aceita_fora_de_sequencia`; número reutilizado ⇒ `rejeitada_conflito_sequencia` |
| Valores inválidos | NaN/Inf/negativo/fuera de dominio ⇒ `rejeitada_invalida` (NaN se guarda como `None`: el JSON canónico prohíbe NaN) |
| Otra microrred / recurso no declarado | `rejeitada_outra_microrrede` / `rejeitada_recurso_desconhecido` |
| Recibida después de cerrar una ventana | Recepción ≤ un corte sellado o anterior a la marca de agua ⇒ **cuarentena** `quarentena_recepcao_retroativa` (C-01); recepción posterior que cubre un intervalo ya decidido ⇒ aceptada con `tardia_apos_corte` y **nunca** altera la decisión |
| Recepción ilegible / sin huso | **Cuarentena** `quarentena_recepcao_invalida`: no se inventa hora de llegada (C-01) |
| Revisión de intervalo ya conciliado | Política declarada (`interromper` × `registrar_sem_reconciliar`); nunca se reescribe el pasado |

**Orden temporal (C-01, auditoría del PR #15).** El libro tiene dos secciones append-only con cadenas propias: el
**libro principal** (toda recepción ordenable, de CUALQUIER clasificación — aceptada, rechazada, duplicada, inválida,
fuera de secuencia —, que avanza la marca de agua; recepciones declaradas no decrecientes y estrictamente posteriores al
último corte sellado) y la **cuarentena** (recepciones retroactivas o ilegibles: registradas con la posición del libro
principal y el número de cortes en el instante del registro; nunca entran en un prefijo causal, no definen identidad de
evento ni consumen secuencia). Un corte τ solo se sella si ninguna entrada del libro principal tiene recepción > τ; I_k
es el **prefijo** de las entradas con recepción ≤ τ_k, comprometido por el hash de cadena: **ningún instantáneo depende
de un evento cuya recepción declarada sea posterior a τ_k**. La auditoría lo recalcula (`instantaneo_de_prefixo`),
exige el mismo hash y verifica la propiedad temporal de TODAS las entradas del prefijo (y de cada conciliación);
`verificar_cadeia_livro` comprueba orden y cortes; el registro de misión compromete la cadena de la cuarentena.
Límite: `recebido_utc` es el instante DECLARADO por la fuente/canal; un tiempo de ingestión confiable exigiría un
reloj propio del controlador (brecha B3C2-13).

**Conciliación** (D-3C2-05): `realizacao_de_instantaneo` construye una `Realizacao` `incremental_online` con
`observado_ate_utc` = última frontera hasta la que **todas** las observaciones obligatorias están presentes de forma
contigua. Obligatorias = las que el ejecutor 3C-1 necesita (demanda; potencial y disponibilidad renovables;
disponibilidad de generadores con fuente `observada`). Se distingue: plan calculado, comando emitido, acción
confirmada, observación recibida, estado reconstruido (`propagacao_algebrica_3C1`) y costo confirmado (solo
intervalos conciliados).

## 5. Aceptación y fallas

`contrato.avaliar_aceitacao` (D-3C2-09): `aceito_otimo` ⇒ plan; `aceito_factivel_nao_otimo` (aprobado por el auditor
3C-1) solo si la política declara `aceitar_factivel_nao_otimo`, la terminación está en `terminacoes_admitidas` y
`gap_rel ≤ gap_rel_max`; cualquier otro estado (sin incumbente, rechazado por auditoría/integridad, inviable, error)
⇒ **ningún** despacho. No hay plan de reserva ni reutilización del plan anterior (E7: la planta queda en g = 2).

Clases de falla (`CLASSES_FALHA`) y acción declarada por clase (`interromper` × `suspender`, sin defecto;
`identidade_divergente`, `integridade`, `consigna_inexequivel` y `revisao_tardia` solo `interromper`):
`previsao_invalida`, `bloqueado_validacao`, `identidade_divergente`, `solver_indisponivel`, `falha_solver`, `inviavel`,
`rejeitado_auditoria`, `rejeitado_integridade`, `fora_politica_aceitacao`, `consigna_inexequivel`,
`estado_nao_reconstruivel`, `erro_dados`, `revisao_tardia`, `integridade`.

Modo 1: si en τ_{k+m} el estado no es reconstruible (latencia/omisión) ⇒ `estado_nao_reconstruivel` (D-3C2-06; una
decisión para un intervalo ya iniciado no sería causal). Modo 2: la conciliación se pausa (C-02) y se reanuda desde el
checkpoint al llegar los datos; si la frontera de decisión pasa sin estado, se aplica la política (suspensión).

## 6. Costos y registros

- **Realizado por ventana** = `contabilidade_realizada_3c1` (3C-1, sin cambios) sobre los intervalos conciliados con el
  entorno OBSERVADO efectivamente usado en cada paso.
- **Planificado del prefijo aplicado** = misma contabilidad sobre el plan con la PREVISIÓN como entorno (D-3C2-08);
  diferencia = realizado − planificado del prefijo.
- **Planificado de la ventana entera** (`custos_modelo`) se registra pero **nunca** se suma: las ventanas se superponen.
- **Acumulado de la misión** = Σ realizados de las ventanas (cada uno solo con intervalos aplicados); sin valor futuro
  (`valor_futuro_nao_implementado`, `contabilizado_como_custo = False`).

Registros (`registro.py`, tipos NUEVOS; esquemas 3C-0/3C-1 intactos): por ventana, `RegistroExecucaoEMS` 3C-0 +
`AnexoExecucao3C1` (cuando hubo plan) + `RegistroJanelaMPC` con `ConteudoJanelaMPC` determinista, `hash_conteudo`,
`cadeia_conteudo` (encadenamiento determinista), `selo_janela_anterior`, `selo_checkpoint_origem` (vínculo explícito
con el checkpoint final de la ventana ejecutada anterior: cada plan tiene ejecución propia y nunca reutiliza un
checkpoint ligado a otro plan) y sello. `RegistroMissaoMPC` cierra la cadena e incluye
`impressao_deterministica` (sin tiempos medidos; dos ejecuciones idénticas coinciden). SHA-256 no es firma digital
(brecha K10 heredada).

## 7. Métricas (`metricas.py`) — definiciones

Operación (E_dem, E_ENS, E_servida, E_curt, E_ren, E_ger por recurso, carga/descarga, SOC por frontera), commitment
(arranques/paradas aplicados, máx |Δp|, menor corrida ON/OFF completa, obligación heredada y pendiente), economía
(realizado por componente, planificado de prefijos, diferencia; ventanas enteras no sumadas), previsión (error
previsto − observado por clave y antelación ℓ solo con observación válida: n, sesgo, EAM, REQM, máx), computación
(tiempos por resolución, tamaño, terminaciones, gaps; n/media/p50/p95/p99/máx por percentil de rango más cercano)
y confiabilidad (desenlaces, fallas por clase, clasificaciones del libro, tardías, revisiones, pausas). El entorno
(Python, plataforma, CPUs, versiones del solver) se registra en `RegistroMissaoMPC.ambiente_json`. No se afirma
tiempo real.

## 8. Decisiones (D-3C2-*) — requieren conocimiento del auditor

| ID | Decisión | Motivo |
|---|---|---|
| D-3C2-01 | Corte informacional **inclusivo**: disponible ⇔ `recebido_utc ≤ τ_k` | Convención explícita y verificable; una observación de [τ_{k−1}, τ_k) recibida exactamente en τ_k es usable en τ_k |
| D-3C2-02 | Libro en orden de recepción; recepción retroactiva rechazada; I_k = prefijo | Ningún conjunto de información usado en una decisión puede cambiar después |
| D-3C2-03 | Reglas K6 de §4 (conflicto ⇒ clave conflictiva; revisión numerada; secuencia) | Nada se elige ni se sobrescribe en silencio |
| D-3C2-04 | `horizonte_estendido_declarado`: `intervalos_missao` de la entrada de la ventana = N_k | La política posmisión explícita vive en el contrato MPC (ver C-3C2-02) |
| D-3C2-05 | Estado reconstruido = propagación ALGEBRAICA 3C-1 con comandos confirmados + observaciones obligatorias | No se inventa estimador físico; requisito de la misión |
| D-3C2-06 | Modo 1: estado no reconstruible en la frontera de decisión ⇒ falla clasificada | Decidir tarde para un intervalo iniciado no es causal |
| D-3C2-07 | Políticas de permanencia intermedia/final declaradas; obligaciones al final reportadas | "No permitir que una obligación desaparezca" |
| D-3C2-08 | Costo planificado del prefijo = plan × previsión con la misma contabilidad 3C-1 | Comparación homogénea planificado × realizado |
| D-3C2-09 | No óptimo solo con gap y terminaciones declarados | Contrato existente + política explícita |
| D-3C2-10 | `interromper` × `suspender`; clases de integridad/identidad/inexequibilidad/revisión solo interrumpen | Sin contingencia inventada |
| D-3C2-11 | Persistencia por ventana + `PontoRetomada` sellado; reanudación verificada; planta de ensayo reconstituida por replay | Reanudación reproducible (test de impresión idéntica) |
| D-3C2-12 | `impressao_deterministica` excluye tiempos y sellos con fecha | Reproducibilidad separada de la medición |
| D-3C2-13 | No anticipatividad por intervención como auditoría posterior | Límite de confianza explícito (§3) |

## 9. Contradicciones e incompatibilidades detectadas (no ocultadas)

| ID | Hallazgo | Tratamiento |
|---|---|---|
| **C-3C2-01** | El ejecutor 3C-0/3C-1 exige **balance exacto** con la demanda realizada y no existe recurso de equilibrio (la consigna no se recorta). En lazo cerrado, **cualquier** error de previsión de demanda — o un potencial renovable realizado menor que el planificado — en un intervalo aplicado vuelve la consigna inexequible | No se relajó nada: la misión se interrumpe con `consigna_inexequivel` (test `test_consigna_inexequivel_interrompe_sem_recorte…`). El MPC solo completa misiones cuyo error en los intervalos aplicados es absorbible por las consignas (subestimación renovable ⇒ vertimiento). Un lazo con errores de demanda exige un recurso de equilibrio DECLARADO (red 3C-3 o capa primaria con modelo físico): brecha B3C2-01 |
| **C-3C2-02** | `validar_malha` (3A) marca `pendente` si N > K_M; la entrada de una ventana con horizonte extendido lo dispararía | La política explícita vive en el contrato MPC; la entrada declara `intervalos_missao = N_k` (D-3C2-04). 3A intacto |
| **C-3C2-03** | El ejecutor 3C-0 no verifica la disponibilidad de bancos | La observación se registra y se usa en la previsión, pero no es obligatoria en la conciliación (brecha) |
| **C-3C2-04** | En la conciliación solo se pasan observaciones obligatorias: una disponibilidad `estatica_declarada` no se contrasta con observaciones del libro | Las fixtures usan `observada`; brecha documentada |
| C-3C2-05 | Planta y conciliación usan escalas de tolerancia D07 calculadas de entradas distintas (modelo × ventana) | Diferencia solo en el borde de tolerancia; D07 sigue provisional |

## 10. Correcciones de la auditoría independiente del PR #15 (base `d97f831`)

| ID | Antes (reproducido en `d97f831`) | Después |
|---|---|---|
| C-01 | Un evento **rechazado** (otra microrred) con recepción 45 min posterior a τ_2 entraba en el prefijo de τ_2 (n = 2, hash dependiente de él); la marca de agua solo consideraba aceptadas, el corte τ_2 se sellaba y `_causal` solo verificaba aceptadas: ninguna anomalía | Marca de agua sobre toda entrada del libro principal; cuarentena con cadena propia para recepciones retroactivas/ilegibles; corte imposible con recepción posterior registrada (`corte_antes_de_recepcao_registrada`); prefijo = recepción ≤ τ; auditoría `informacao_futura_no_instantaneo` / `informacao_disponivel_omitida` sobre todas las entradas; `verificar_cadeia_livro` con `recepcao_fora_de_ordem_no_livro_principal` y `corte_inclui_recepcao_posterior`. Esquema del libro v2 |
| C-02 | La reanudación aceptaba registro 3C-0 eliminado o alterado y anexo 3C-1 eliminado; históricos `registros_3c0`/`anexos_3c1` no restaurados (0/0) | `verificar_artefatos_janela` para cada ventana ejecutada (`execucao_uid` determinista registrado en `ConteudoJanelaMPC`): registro 3C-0 (`verificar_registro`), anexo (`verificar_anexo_3c1`), sellos referenciados, identidad/misión/posición, ventana, plan, entrada, estados, checkpoint, previsión, instantáneo, costo e intervalos; ventana sin plan no exige artefactos (y no puede referenciarlos); el libro del punto de retomada debe reproducir todos los instantáneos comprometidos; errores `ContratoInvalido` estructurados; históricos restaurados |

Pruebas: `test_ems_v2_3c2_auditoria_pr15.py` (24). Ni el modelo físico, ni el solver, ni las políticas económicas
cambiaron; los resultados de E1–E8 son idénticos.

## 11. Límites

- Sin término terminal ni valor futuro: el horizonte corto es **miope** (E2/E4 drenan el banco en cada ventana; E4
  m = 1 deja la PEMFC arrancando en el último intervalo con 1800 s de obligación pendiente). Corresponde a 3C-4.
- La optimalidad es del modelo reducido; la planta es el dublé algebraico (no PEMFC/BESS física; arranque instantáneo
  = abstracción declarada).
- Ninguna microrred real ejecuta el MPC (brechas 3C-0/3C-1 vigentes); no hay integración con la UI ni el runtime.
- Tiempos medidos solo indicativos (EVIDENCIA_3C2_EJECUCION); ninguna restricción de tiempo real fue validada.
