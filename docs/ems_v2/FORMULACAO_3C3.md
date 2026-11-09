# Piso 3C-3 — Red eléctrica, intercambio económico y recurso explícito de equilibrio (entregables A–J)

> Perfil **`v1.1-3C-3`** (`ems_v2.rede.FORMULACAO_3C3`). Implementación: `ems_v2/rede/` (núcleo solo biblioteca
> estándar) + `ems_v2/milp/{modelo,solver,resultado,evidencia}_3c3.py` (únicos módulos nuevos que importan Pyomo).
> Fixtures sintéticas: `ems_v2/fixtures_3c3.py`. Trazabilidad: [`MATRIZ_3C3.md`](MATRIZ_3C3.md). Brechas:
> [`BRECHAS_3C3.md`](BRECHAS_3C3.md). Transición: [`TRANSICAO_3C3_3C4.md`](TRANSICAO_3C3_3C4.md). Evidencia:
> [`EVIDENCIA_3C3_EJECUCION.md`](EVIDENCIA_3C3_EJECUCION.md). Base: `main` `a4c6b1c1a5e9be86b7b20556f91ec3a753dfb225`
> (merge del PR #15).
>
> **Rótulo obligatorio:** modelo ALGEBRAICO **agregado** del intercambio en el PCC (balance de potencia activa en kW en
> el bus equivalente) para experimentos de despacho energético, sobre fixtures y tarifas **sintéticas**. **No**
> representa flujo AC, tensiones nodales, potencia reactiva, frecuencia, dinámica electromecánica, protección,
> transitorios de conmutación, límites térmicos de alimentadores ni dinámica de convertidores. El ajuste realizado
> **no** es un controlador primario de frecuencia validado. Ninguna función representa una factura eléctrica real. El
> EMS V1.6 sigue siendo el único motor operacional; nada está integrado a la aplicación.

## 1. Modelo del PCC (contrato `EspecPCC`, `rede/contrato.py`)

| Símbolo | Campo | Unidad | Regla |
|---|---|---|---|
| P_t^imp ≥ 0 | variable `P_imp` | kW | inyecta al bus |
| P_t^exp ≥ 0 | variable `P_exp` | kW | consume del bus |
| P_t^net = P_t^imp − P_t^exp | — | kW | positivo al importar |
| P̄_t^imp, P̄_t^exp | `limite_importacao`, `limite_exportacao` (`SerieTemporal` kW, barramento_liquido) | kW | contratados por intervalo; **obligatorios** si el sentido está permitido; prohibidos si no; 0 admitido (aviso `capacidade_contratada_nula`); negativos ⇒ error |
| a_t ∈ {0,1} | `disponibilidade` | 1 | obligatoria en `conectado`; fraccionaria ⇒ pendiente |
| modo | `modo` | — | `conectado` × `isolado_declarado` (**sin defecto**): un PCC ausente **no** es conexión ilimitada |
| sentidos | `sentidos_permitidos` | — | `importacao_e_exportacao` · `somente_importacao` · `somente_exportacao` · `nenhum` (obligatorio en isolado) |
| medidores | `medidor_importacao_uid`, `medidor_exportacao_uid` | — | registros de importación/exportación (observación `potencia` ≥ 0); exigidos por el MPC conectado como evidencia del ajuste |

Otras verificaciones: PCC de otra microrred ⇒ `pcc_de_outra_microrrede` (sin intercambio entre microrredes); UID del
PCC/medidores no colisiona con recursos; series desalineadas, sin cobertura o con paso ≠ Δ ⇒ error (sin
remuestreo/extrapolación). Casos representables (G1–G4, G6, G12): importa, exporta, intercambio cero, exportación
prohibida, importación limitada, PCC indisponible, operación aislada declarada.

## 2. Tarifas (`PerfilTarifario`, `PoliticaEconomicaRede`)

Perfil = bloques `[inicio, inicio + duración)` con valor R$/kWh (o `None` = **desconocido**, explícito), magnitud
(`importacao`, `exportacao`, `desvio_positivo`, `desvio_negativo`), naturaleza (`contratual_conhecida`, `prevista`,
`aplicavel_liquidacao`), revisión, `emitido_utc` (instante de disponibilidad), regla de aplicación
(`valor_do_bloco_que_contem_o_intervalo`: cada intervalo debe estar **entero** dentro de un bloque; atraviesa bloques ⇒
error, nunca prorrateo), contrato, procedencia y rótulo `SINTÉTICA`; hash = SHA-256 canónico (`hash_perfil`).
Precios negativos no soportados (`preco_negativo`); precio desconocido usado ⇒ `pendente preco_desconhecido`.

Política económica (sin defecto): importación permitida ⇒ término `importacao_rede` + perfil (la red no es energía
gratuita); exportación permitida ⇒ remuneración **declarada**: `remunerada` (término `exportacao_rede` + perfil) o
`sem_remuneracao` (crédito nulo declarado); exportación prohibida/isolado ⇒ `nao_aplicavel`. Aviso
`remuneracao_maior_que_importacao` cuando c_exp > c_imp (incentivo de arbitraje simultáneo, impedido por §3).

**Causalidad de precios.** Decisión: solo `contratual_conhecida` o `prevista` emitidas **hasta** el inicio de la
ventana; `aplicavel_liquidacao` en la decisión solo con `rotulo_informacao = ablacao_oraculo` (rotulado). En el MPC,
`selecionar_perfil_causal` toma en cada τ_k la **mayor revisión** emitida ≤ τ_k (G11: r1 emitida en τ_4 solo se usa
desde τ_4). Liquidación: solo perfiles de la política de ajuste (`contratual_conhecida` o `aplicavel_liquidacao`; un
precio **previsto nunca liquida**).

## 3. MILP de una ventana (`milp/modelo_3c3.py`, `solver_3c3.py`)

Composición sobre el constructor 3C-1 **sin modificarlo**: `construir_modelo_3c1` (que reutiliza el 3B-P) construye
el núcleo M03–M12, M14–M16 y los términos 3B-P/3C-1. En modo `conectado` se agrega:

```
PCC1   P_imp_t <= a_t P̄_imp_t w_t            P_exp_t <= a_t P̄_exp_t (1 − w_t)      w_t ∈ {0,1}  (dos sentidos)
       sentido prohibido ⇒ variable fijada en 0 (sin w)
M02-3C3  Σ P_R + Σ (P_d − P_c) + Σ p + P_imp_t  =  Σ L − Σ ℓ + d + P_exp_t
J      = J_3C-1 + h Σ_t c_imp_t P_imp_t − h Σ_t c_exp_t P_exp_t
```

* **Exclusividad sin Big-M arbitrario:** los coeficientes de w son los límites **contratados** × disponibilidad
  declarados. G10 demuestra que es necesaria: sin exclusividad el modelo arbitraría 50 + 50 kW (J = −10 R$); con w
  relajado a [0, 1] aún 25 + 25 kW (J = −5 R$); con w binaria, J = 0 y ningún flujo simultáneo.
* **M02 extendido de forma verificable:** la M02-3C3 se reconstruye desde los componentes del modelo y, en la
  construcción, se compara **término a término** (coeficientes y constante, `generate_standard_repn`) con el cuerpo
  del M02 del núcleo; cualquier divergencia levanta `ExtensaoM02Incoerente`. El M02 original se desactiva (no se
  borra). Sin variables de holgura en el balance.
* **Isolado declarado:** nada se agrega; el modelo es idéntico al 3C-1 (mismo tamaño y misma solución — test).
* Unidades: kW, h = Δ/60 [h], R$/kWh ⇒ R$. Costos de eventos (R$/evento) **no** se multiplican por h (3C-1 intacto);
  H₂ no se duplica (solo el núcleo lo cuenta).
* `resolver_3c3` sigue la disciplina 3B-P/3C-1: preflight → construcción → HiGHS → clasificación → extracción → coherencia
  del objetivo → **auditor independiente 3C-3** + integridad 3B-P → estado. Un resultado 3C-3 declara
  `versao_formulacao = v1.1-3C-3` y `hash_entrada = hash_entrada_3c3`; `resolver_3c1`, `plano_de_resultado_3c1` y
  `verificar_anexo_3c1` lo rechazan (no se hace pasar por 3C-1).

## 4. Auditor independiente (`rede/auditor.py`)

Composición explícita: `auditar_3c1` (inalterado) audita **todas** las familias del núcleo; en `conectado` solo el
residuo de balance M02 del 3C-1 (que desconoce el PCC) se **sustituye** por el balance M02-3C3 reconstruido en el
auditor (escala de tolerancia D07 que incluye los límites del PCC); en `isolado_declarado` el balance 3C-1 se mantiene y
se agrega el 3C-3. Familias del PCC: dominio, capacidad × disponibilidad, exclusividad, integralidad/coherencia de w,
sentido prohibido, PCC indisponible, intercambio en operación aislada. Costos: importación (gasto), exportación
(crédito, signo negativo) y total = total 3C-1 + J_imp + J_exp. Series y precios realineados con **aritmética entera
de segundos propia** (no usa `precos_na_malha`, que alimenta el MILP). G14: alteraciones post-solver de P_imp, costos,
flujos simultáneos, disponibilidad o tarifa ⇒ `rejeitado_auditoria`.

## 5. Intercambio programado × realizado (`rede/execucao.py`) — parte central

* **Programado:** decidido por el MILP con información causal (`PlanoRede3C3`: P_imp/P_exp por intervalo, ligado al
  hash del `PlanoDespacho`; costo de red planificado de la ventana; plan de commitment del núcleo).
* **Realizado:** intercambio efectivo del intervalo ejecutado (en `PassoAplicado.aplicado` como `<pcc>|P_imp/P_exp`).
* **Desvío:** `DesvioIntercambio` = P_net realizado − P_net programado (positivo = importación neta mayor).

**Política de ajuste (`PoliticaAjustePCC`, sin defecto):**

| Campo | Opciones | Regla |
|---|---|---|
| `tipo` | `sem_ajuste` | realizado = programado; cualquier desbalance observado ⇒ `balanco_realizado_violado` (inexequible) |
| | `ajuste_local_algebrico` | con las demás consignas ya ejecutadas y la demanda/recurso **observados**: P_net^real = Σ(L^obs − ℓ) + d + Σ P_c − Σ P_d − Σ P_R^ef − Σ p; se aplica SOLO si el PCC está declarado conectado, a^obs = 1, el sentido está permitido y |P| ≤ límite contratado; si no ⇒ `pcc_indisponivel`, `importacao_proibida`, `exportacao_proibida`, `pcc_saturado_importacao/exportacao` (inexequible, sin recorte) |
| `injecao_renovavel` | `consigna_exata` | regla 3C-0: consigna > disponible observado ⇒ inexequible |
| | `limitada_pela_disponibilidade` | P_R^real = min(consigna, A^obs·a^obs): la diferencia es **desvío físico** registrado (`DesvioPlanoRealizado` P_R); el excedente sobre la consigna **no** se inyecta (permanece vertido) |
| `liquidacao` | `energia_medida_tarifa_aplicavel` | referencia sintética: h(c_imp^liq P_imp^real − c_exp^liq P_exp^real) |
| | `desvio_diferenciado` | programado a precios de liquidación + h(c_dp max(0, ΔP) − c_dn max(0, −ΔP)) con perfiles de desvío **declarados** |

**Evidencia del ajuste.** En la conciliación del MPC, el intercambio reconstruido algebraicamente se confronta con la
**medición** de los registros del PCC (`exigir_medicao`): ausente ⇒ error de datos (pausa C-02 / estado no
reconstruible); divergente ⇒ `intercambio_medido_divergente` ⇒ falla de **integridad**. Ninguna desviación se
sustituye por importación ilimitada, ENS inventada ni cambios retroactivos de batería/PEMFC: el executor hereda
**todas** las verificaciones de commitment del 3C-1 (memoria, rampas, permanencias, disponibilidad efectiva por fuente
declarada) y repite la álgebra 3C-0 de bancos/generadores; solo el balance cambia.

## 6. Costos realizados (`contabilidade_realizada_3c3`)

Costo realizado de una ejecución = contabilidad 3C-1 **sin cambios** del núcleo (curtailment con el P_R **efectivo**,
throughput, ENS, H₂ continuo + eventos aplicados, eventos) + `importacao_rede` (gasto ≥ 0) + `exportacao_rede`
(−crédito) + `desvio_rede` (solo `desvio_diferenciado`). Indicadores separados: `gasto_importacao_R`,
`receita_exportacao_R`, energías importada/exportada **realizadas** y **programadas** y desvíos ±. Costo planificado
del prefijo aplicado (MPC) = plan × previsión con las **tarifas de decisión** de la ventana. Ventanas superpuestas
nunca se suman; valor futuro no implementado ni contabilizado (invariante 3C-0).

## 7. Registros y evidencia (`rede/registro.py`, `rede/mpc.py`)

Por ventana ejecutada: `RegistroExecucaoEMS` 3C-0 (esquema intacto) + **anexo 3C-3 sellado** (`<uid>.ems3c3.json`,
protocolo B-03 en tres fases): plan de red completo, política de ajuste completa, fuentes y disponibilidad efectiva
por paso, evidencia del PCC por paso (`RegistroPassoPCC`: programado, a observada, exigido, realizado, renovable
consigna × efectiva, medido, ajuste aplicado — **recalculada** paso a paso por la misma regla del ejecutor y exigida
idéntica a la trayectoria conciliada), liquidación por paso, desvíos, H₂ y eventos. El registro compromete
`entrada_3c3`, `plano_rede_3c3`, `politica_ajuste_3c3`, `fontes_disponibilidade_3c3`, `anexo_3c3_conteudo` antes del
sello. Una ejecución 3C-3 **no** produce anexo 3C-1. Por punto de retomada: `VinculoRede3C3` sellado (hash del modelo
3C-3 y de la configuración de red). La auditoría de misión distingue escopo **integral** (certificación documental
obligatoria) y **analítico parcial** (solo reproducción numérica) — §10b, C-02. Al final: `RegistroMissaoRede3C3` sellado ligado al `RegistroMissaoMPC` (totales
de intercambio, desvíos y liquidación = Σ de las ventanas). SHA-256 no es firma (K10 heredada).

## 8. Integración con el MPC 3C-2 — auditoría del punto de extensión (entregable H)

Antes de implementar se auditó `ControladorMPC`. Dependencias específicas del 3C-1 encontradas (y solo estas):
`chaves_de_previsao(modelo)`, `montar_entrada_janela`, `validar_entrada_3c1`, `hash_entrada_3c1` (entrada y registro),
`plano_de_resultado_3c1`, consignas de los comandos, `ExecutorAlgebricoCommitment3C1` (conciliación y costo
planificado del prefijo), `contabilidade_realizada_3c1`, `hash_plano_commitment` y los artefactos 3C-1
(`preparar_conteudo_anexo_3c1`/`montar_anexo_3c1`, `anexos_3c1`). **Punto de extensión mínimo:** estas 12 llamadas
pasan a métodos del orquestrador (`_chaves_previsao`, `_montar_entrada_janela`, `_validar_entrada_janela`,
`_hash_entrada`, `_plano_de_resultado`, `_consignas_comando`, `_executor_conciliacao`, `_contabilidade`,
`_hash_plano_complementar`, `_artefatos_registro`, `_registrar_anexo`) cuya implementación por defecto es **exactamente**
la llamada 3C-2. Regresión: impresiones deterministas de E1–E8 (12 misiones; misión, ventanas, contenidos de anexos,
planes y costos) **idénticas** a las de la base `a4c6b1c` (G15). `ControladorMPCConectado` sobrescribe solo esos
métodos (y la grabación/finalización para sus artefactos); no duplica la máquina MPC.

Se reutilizan sin cambios: reloj, libro K6 (cortes, prefijos, cuarentena, revisiones), previsión causal, aceptación,
fallas clasificadas, confirmaciones, conciliación 3C-0 (barrera C-02), estado y memoria EJECUTADOS, registros
encadenados, persistencia, retomada (verificación ampliada en `rede/persistencia.py`) y auditoría de misión
(compuesta en `rede/auditoria.py`). Distinciones registradas: consigna de intercambio programada (comando),
acción de ajuste autorizada (política + paso), intercambio medido (libro K6), disponibilidad observada del PCC (K6),
costo planificado × realizado y desvío. La conexión no reinicializa batería ni commitment (estado transportado igual
que en 3C-2; G11/G13). Una misión `isolado_declarado` nunca pasa a conectada (modo del modelo comprometido; el
vínculo de rede rechaza otro modelo/configuración en la retomada; observaciones del PCC ⇒
`rejeitada_recurso_desconhecido`).

## 9. Decisiones (D-3C3-*) — requieren conocimiento/aprobación del auditor

| ID | Decisión | Alternativa descartada |
|---|---|---|
| D-3C3-01 | Contrato **embrulho** `EntradaRede3C3` sobre `EntradaCommitment3C1` (núcleo validado sin relajación) | Campos opcionales en contratos 3A/3C-1 (rompería hashes y la guardia) |
| D-3C3-02 | Exclusividad por binaria w con coeficientes = límites contratados × disponibilidad | Big-M arbitrario; complementariedad no lineal |
| D-3C3-03 | M02-3C3 reconstruida y **verificada término a término** contra el M02 del núcleo | Editar `modelo.py` 3B-P; usar `.body` sin verificación |
| D-3C3-04 | Auditor 3C-3 = auditor 3C-1 + sustitución SOLO del balance (conectado) | Desactivar la auditoría 3C-1 o reescribirla entera |
| D-3C3-05 | Ajuste local algebraico del PCC como **única** respuesta realizada declarada; renovable nunca recortada para absorber excedente (no hay política de curtailment en tiempo real) | Recortar FV silenciosamente; ENS/descarte implícitos |
| D-3C3-06 | Renovable: `limitada_pela_disponibilidade` = min(consigna, disponible); exceso no inyectado | Inyectar todo el disponible; consigna exacta como única regla |
| D-3C3-07 | Evidencia del ajuste = medición del PCC en el libro K6, obligatoria en la conciliación y confrontada con la reconstrucción | Confiar en la reconstrucción algebraica sola |
| D-3C3-08 | Liquidación de referencia `energia_medida_tarifa_aplicavel`; `desvio_diferenciado` solo con perfiles declarados | Inventar reglas regulatorias/penalidades |
| D-3C3-09 | Precios: mayor revisión emitida ≤ τ_k; liquidación solo con perfiles de liquidación; precios negativos fuera de alcance | Usar el precio realizado en la decisión; prorratear bloques |
| D-3C3-10 | Costo planificado del prefijo con las tarifas de **decisión** de la ventana | Con las de liquidación (mezclaría información no disponible) |
| D-3C3-11 | Punto de extensión por métodos del orquestrador (refactorización controlada con regresión exacta) | Duplicar `decidir`/`conciliar`/`_fechar` (~240 líneas) |
| D-3C3-12 | Medidores como recursos propios (UIDs) con magnitud `potencia` ≥ 0 por sentido | Nueva magnitud con signo (modificaría K6/3C-0) |

## 10. Contradicciones e incompatibilidades detectadas (no ocultadas)

| ID | Hallazgo | Tratamiento |
|---|---|---|
| **C-3C3-01** | El contrato 3A solo admite `fronteira.topologia = "isolada"` (`TOPOLOGIAS`); la base del 3C-3 debe validarse sin relajación | Interpretación registrada: en 3C-3 la frontera de la base describe el **bus interno** (recursos propios); el PCC existe solo en el embrulho; `topologia_base_incompativel` si la base declarara otra cosa. Contrato 3A intacto |
| **C-3C3-02** | Tres guardias anteriores impedían por construcción el 3C-3: (a) lista nominal de módulos que importan Pyomo; (b) `ADICOES_3C1` en `ems_v2/milp`; (c) guardia 3C-2 "ningún archivo existente modificado y adiciones solo en `ems_v2/mpc/`" | Ajuste **nominal mínimo**: (a) agrega `milp/modelo_3c3.py`, `milp/solver_3c3.py`; (b) `ADICOES_3C3` (4 archivos) con la misma regla de solo adición; (c) admite la ÚNICA modificación `ems_v2/mpc/orquestrador.py` (refactorización controlada, regresión G15) y adiciones en `ems_v2/rede/`, `fixtures_3c3.py`, `ADICOES_3C3`. Nueva guardia `test_ems_v2_3c3_isolamento.py` desde `a4c6b1c`: solo `orquestrador.py` y las 3 guardias cambian; V1.6/`seeds2`/aplicación/requirements intactos |
| **C-3C3-03** | El campo `ConteudoJanelaMPC.hash_entrada_3c1` y `RegistroJanelaMPC.selo_anexo_3c1` tienen nombre 3C-1 | En misiones conectadas guardan, respectivamente, el hash de la entrada **de la ventana** (perfil 3C-3, coincide con `plano.hash_entrada` de `v1.1-3C-3`) y el sello del anexo **3C-3**; el perfil queda inequívoco por el plan y el anexo. Esquemas 3C-2 sin cambios |
| **C-3C3-04** | Con exportación prohibida y excedente realizado (demanda < prevista), ni el PCC ni ningún recurso declarado puede absorberlo (la FV no se recorta por política) | Falla clasificada `consigna_inexequivel` (G6 con `somente_importacao`); requiere una política de curtailment en tiempo real declarada (brecha B3C3-04) |
| C-3C3-05 | La liquidación usa un único perfil por magnitud; revisiones posteriores del precio de liquidación no re-liquidan intervalos ya cerrados | Brecha B3C3-06 (re-liquidación) |

## 10b. Correcciones de la auditoría independiente del PR #16 (commit auditado `d7da6c5`)

Dictamen: MILP del PCC, exclusividad, integración MPC por puntos de extensión, contabilidad y aislamiento de los pisos
anteriores aprobados estructuralmente; dos correcciones de integridad. Ambas se **reprodujeron sobre `d7da6c5` antes
de corregir** (salida literal en `EVIDENCIA_3C3_EJECUCION.md` §7).

| ID | Antes (`d7da6c5`, reproducido) | Después |
|---|---|---|
| C-01 | Consigna `P_imp = NaN` ⇒ `PassoAplicado` **exequible** (en `sem_ajuste` con `NaN` aplicado; la comparación `abs(a − b) > tol` no detecta NaN); consigna PARCIAL (solo `P_imp`) ignorada en silencio cuando había programa; `plano_de_resultado_3c3` recortaba `max(0, v)` (−3 ⇒ 0, NaN ⇒ 0) y completaba con ceros un intercambio ausente | `valor_intercambio_valido`: cada valor programado = `int`/`float` estricto, finito y ≥ 0 (bool, texto, NaN, ±Inf, negativos ⇒ inválidos, nunca recortados ni convertidos). `ExecutorAlgebricoConectado3C3.avancar` valida el programado **antes** de cualquier operación física o económica: las dos consignas del PCC o ninguna (`intercambio_programado_incompleto`), valores válidos (`intercambio_programado_invalido`), comando = programa cuando ambos existen (igualdad exacta; `programa_pcc_contraditorio`), ninguna fuente ⇒ `programa_pcc_ausente`; todo ⇒ falla de **DATOS** (`erro_dados`; nada aplicado). El programa explícito se valida en la construcción (`programa_pcc_invalido`). Caso legítimo preservado: en la conciliación el programado viene SOLO del programa (el plan 3C-0 tiene solo recursos internos). `plano_de_resultado_3c3` exige N valores válidos por sentido en modo conectado (sin recorte ni defecto) ⇒ `ContratoInvalido` ⇒ falla de **integridad** en el MPC; isolado con intercambio ⇒ rechazado. Consignas internas no numéricas ⇒ `consigna_invalida` (datos). NaN/Inf ni siquiera son representables en un comando (JSON canónico del hash) |
| C-02 | `auditar_missao_conectada(..., anexos=None, registros_3c0=None)` devolvía `aceito = True` sin validar ningún documento; el `RegistroMissaoRede3C3` no se exigía; un modelo PCC con límites más amplios o una política económica sustituida eran aceptados | Dos **escopos explícitos**: `auditar_missao_conectada` = **INTEGRAL** (registros 3C-0, anexos 3C-3 y registro de misión de red como argumentos keyword **obligatorios**; `None` ⇒ `auditoria_integral_incompleta`, `aceito = False`); `auditar_missao_conectada_analitica` = **analítica parcial** rotulada (`escopo = "analitica_parcial"`, `integridade_documental_certificada = False` siempre). La sección `documental` verifica, POR POSICIÓN, cada ventana ejecutada con `rede.persistencia.verificar_artefatos_carregados_3c3` (la misma verificación pura de la retomada: `verificar_registro`, `verificar_anexo_3c3`, sellos comprometidos en el `RegistroJanelaMPC`, `execucao_uid` determinista, identidad/misión/posición, plan, plan de red, estados, discretización, checkpoint, información y costo), ventanas sin plan sin artefactos, número exacto de artefactos, PCC/modo del plan de red, `verificar_registro_rede` (sello, vínculo con el `RegistroMissaoMPC`, secuencia de anexos, totales), `hash_modelo_3c3` y `hash_configuracao_rede` contra los objetos **concretos** suministrados (`modelo_3c3_divergente`, `configuracao_rede_divergente`), configuración de red válida y misión/modo. `aceito` exige además todas las secciones analíticas. Esquemas 3C-0/3C-1/3C-2 sin cambios |

Pruebas: `tests/ems_v2/test_ems_v2_3c3_auditoria_pr16.py` (**132**: C-01 ×120 parametrizadas para ambas políticas con y
sin programa, C-02 ×12 con misiones conectadas reales). Las pruebas C-02 demuestran que la auditoría integral falla
aunque balance y costos sigan correctos (`reprovada_so_documental`). El modelo físico, el MILP, las políticas
económicas y los resultados G1–G15 no cambian (impresiones y costos idénticos).

## 11. Experimentos (detalle en `EVIDENCIA_3C3_EJECUCION.md`)

| Exp. | Resultado (sintético) |
|---|---|
| G1 | importa exactamente 20 kW (< 25 contratados), J = R$ 8,0; límite 19 kW ⇒ inviable |
| G2 | excedente 20 kW exportado: remunerada c_exp 0,3 ⇒ J = −R$ 3,0; `sem_remuneracao` declarada ⇒ exporta igual (evita vertimiento 0,2), J = 0 |
| G3 | exportación prohibida: carga 15 kW y vierte 5 kW, J = R$ 0,875, P_exp ≡ 0 |
| G4 | PCC indisponible: sin banco ⇒ inviable (sin energía inventada); con banco ⇒ sin intercambio, J = R$ 0,5 |
| G5 | demanda +4 kW en g = 1: importación realizada 24 vs programada 20; R$ 12,6 (planificado 12,0) |
| G6 | −4 kW ⇒ importa 16 (R$ 11,4); demanda 5 kW ⇒ exporta 5 (R$ 8,75); con exportación prohibida ⇒ `consigna_inexequivel` en g = 1 |
| G7 | FV realizada 4 kW con consigna 10: inyección efectiva 4, PCC importa 26; R$ 12,9 |
| G8 | P̄_imp = 22 y se exigen 24 kW ⇒ `pcc_saturado_importacao` ⇒ misión interrumpida en k = 1, sin respaldo oculto |
| G9 | dos perfiles tarifarios con física igual ⇒ decisiones intercambiadas (importa en el intervalo barato), J = 1,25 ambos |
| G10 | arbitraje: sin exclusividad −10 R$, w relajado −5 R$, MILP con w binaria 0 R$ sin flujo simultáneo |
| G11 | 4 ventanas, demanda y FV perturbadas, previsión reemitida, revisión tarifaria causal (r0 en τ_0/τ_2, r1 en τ_4/τ_6), ajustes ±, auditoría aprobada, impresión determinista reproducida |
| G12 | demanda = prevista: conectado e isolado R$ 16,7 ambos (conectado deja 900 s de obligación); con error de demanda: isolado interrumpido, conectado concluye (R$ 18,2) — contraste de topología, no superioridad |
| G13 | interrupción tras 2 ventanas + retomada verificada ⇒ impresión, totales de red y anexos idénticos a la ejecución continua; adulteraciones/otro modelo/otra política ⇒ rechazo |
| G14 | P_imp, costo, flujo simultáneo, disponibilidad, tarifa, liquidación del anexo, intercambio de la ventana y disponibilidad observada alterados ⇒ rechazados |
| G15 | E1–E8 del 3C-2 idénticos a la base (12 misiones, igualdad exacta) |
| §13 | open-loop (N = m = 8) R$ 20,95 × MPC (N = 4, m = 2) R$ 15,9, E_final 0 kWh y obligaciones 0 s en ambos: condiciones comparables; **una** instancia sintética, sin afirmar superioridad general |

## 12. Límites

Sin valor futuro/planificador (3C-4): horizonte corto miope (banco drenado). Sin flujo AC ni dinámica (rótulo). La
medición del PCC en la planta de ensayo es la del propio simulador (no hay equipo real). Ninguna microrred del catálogo
ejecuta el EMS V2 (brechas 3C-0/3C-1/3C-2 + B3C3). Tiempos solo indicativos.
