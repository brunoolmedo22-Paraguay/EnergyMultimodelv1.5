# Piso 3C-4 — EMS jerárquico MILP–MPC: planificación de largo plazo, costo de continuación y valor futuro

> Perfil **`v1.1-3C-4`** (`ems_v2.hierarquia.FORMULACAO_3C4`). Implementación: `ems_v2/hierarquia/` (núcleo solo
> biblioteca estándar) + `ems_v2/milp/{modelo,solver,resultado,evidencia}_3c4.py` (únicos módulos nuevos con Pyomo).
> Fixtures sintéticas: `ems_v2/fixtures_3c4.py`. Trazabilidad: [`MATRIZ_3C4.md`](MATRIZ_3C4.md). Brechas:
> [`BRECHAS_3C4.md`](BRECHAS_3C4.md). Evidencia: [`EVIDENCIA_3C4_EJECUCION.md`](EVIDENCIA_3C4_EJECUCION.md).
> Transición: [`TRANSICAO_3C4_3D.md`](TRANSICAO_3C4_3D.md). Base: `main` `10365c5478b4dd137906b58819cd7f71d8de9cea`
> (merge del PR #16).
>
> **Rótulo obligatorio:** EMS jerárquico ALGEBRAICO sobre fixtures y tarifas SINTÉTICAS. El costo futuro es un
> **instrumento de decisión** (estimación del planificador bajo las previsiones disponibles en τ_k), nunca un costo
> monetario incurrido ni un ingreso realizado. No es validación física, fatura real ni desempeño de tiempo real. El EMS
> V1.6 sigue siendo el único motor operacional; nada está integrado a la aplicación, al catálogo ni al runtime.

## 1. Hipótesis científica y qué se demuestra

*Una coordinación jerárquica mediante información económica de largo plazo puede mejorar las decisiones operativas de
un MPC de horizonte corto, al considerar el valor futuro de la energía almacenada y las restricciones intertemporales,
sin sacrificar causalidad ni factibilidad.* El mecanismo implementado es el **costo de continuación** `V^tail` en la
frontera terminal del MPC corto, estimado por **reoptimización paramétrica auditada** y transmitido como un contrato
sellado y verificable. Los experimentos separan el efecto de **reoptimización** del de **anticipación** (§12).

## 2. Auditoría del punto de partida (fase A)

Estado real verificado en `main` `10365c5`: 3A, 3B-P, 3C-0, 3C-1, 3C-2 y 3C-3 integrados; línea de base
`tests/ems_v2` medida antes de cambiar nada: **1080 passed** (con `requirements.txt` + `requirements-ems_v2.txt`).

Puntos de extensión inventariados (`mpc/orquestrador.py`, refactorización controlada del 3C-3): `_chaves_previsao`,
`_montar_entrada_janela`, `_validar_entrada_janela`, `_hash_entrada`, `_plano_de_resultado`, `_consignas_comando`,
`_executor_conciliacao`, `_contabilidade`, `_hash_plano_complementar`, `_artefatos_registro`, `_registrar_anexo`, más
`_falhar_sem_plano`, `_selar_e_gravar`, `finalizar`, `resultado`. **Son suficientes**: el 3C-4 no modifica
`orquestrador.py` ni ningún archivo de `ems_v2/mpc`, `ems_v2/rede`, `ems_v2/milp` (3B-P/3C-1/3C-3), contratos 3A/3C-0/3C-1
(guardia `test_ems_v2_3c4_isolamento.py` desde `10365c5`). Alternativas evaluadas y descartadas: duplicar `decidir`
(~95 líneas) en una subclase; añadir un término terminal opcional a `EntradaRede3C3` (rompería hashes y el perfil 3C-3);
un nuevo punto de extensión en el orquestrador (modificaría un archivo protegido sin necesidad).

## 3. Horizontes y notación

| Símbolo | Significado | Dónde |
|---|---|---|
| Δ | intervalo de discretización (misma malla en ambos niveles: sin agregación entre resoluciones) | `MalhaTemporal.delta_min` |
| H_S = NΔ | horizonte del MPC corto | `ConfiguracaoMPC.malha.intervalos_otimizacao` |
| ρ = mΔ | período de aplicación/reoptimización (1 ≤ m ≤ N) | `intervalos_reotimizacao` |
| H_L | horizonte de planificación largo (**declarado**, sin defecto de 24 h) | `ConfiguracaoPlanejador3C4.horizonte_longo_intervalos` |
| H_F | horizonte de previsión disponible | `malha.horizonte_previsao_min` |
| T_M = K_M Δ | duración de la misión | `intervalos_missao` |
| τ_k | instante de decisión (frontera global k) | `relogio` |
| x_k | estado EJECUTADO y conciliado (energías, ON/OFF, potencia, tiempo en el estado ⇒ memoria) | `EstadoMicrorrede` |

Validaciones (`validar_configuracao_planejador`, sin defecto): **H_L > N** (`horizonte_longo_nao_maior`), **H_L Δ ≤ H_F**
(`horizonte_longo_alem_da_previsao`: ningún horizonte se amplía con extrapolación oculta), H_L,k = min(H_L, K_M − k)
(`reduzido_ao_fim_da_missao`, único modo de cobertura implementado; uno extendido exigiría previsión pos-misión
declarada). La frontera terminal del MPC corto es b = k + N_k; el planificador emitido en τ_p termina en p + H_L,p.

## 4. Función de costo de continuación

### 4.1 Definición

Para un estado x en la frontera b del MPC corto (energías E, modo discreto σ de los generadores):

```
V_p^tail(x) = min Σ_{t=b}^{f−1} c_t(x_t, u_t) + Φ_L(x_f)      f = p + H_L,p
              s.a. física, PCC 3C-3, baterías, commitment 3C-1 (M02–M16, M09–M12), estado inicial x en τ_b
```

con previsiones y tarifas **disponibles en τ_p ≤ τ_k** (emisión). `V^tail` se calcula con el **mismo MILP** del núcleo
(`resolver_3c4` = composición sobre el constructor 3C-3, con auditor 3C-3 + auditor terminal): la física del
planificador es exactamente la del MPC. La cola empieza en b: **no contiene ningún intervalo de J_S** (sin doble
conteo, §8).

### 4.2 Política terminal del planificador Φ_L (explícita, sin miopía arbitraria)

`TermoTerminal3C4` declarado (sin defecto, con justificación y procedencia): `nenhum_declarado` (energía/estado
residual valorados en 0 por declaración explícita — aceptado solo con justificación; en los experimentos es IGUAL para
todas las estrategias, de modo que el tratamiento terminal es común y comparable), `valor_linear_declarado`
(Φ_L(E) = −Σ λ_b E_b, λ_b ≥ 0 R$/kWh) o `energia_minima_declarada` (E_b ≥ Ē_b). La permanencia en el fin del horizonte
largo también es declarada (`permanencia_fim_planejamento`).

### 4.3 Modos terminales y memoria de commitment

El valor de continuación depende del estado discreto de los generadores en b. Cada modo σ declara, por generador,
`ligado` y la **obligación residual** de permanencia en b. Lema (prueba en el código de `compromisso/memoria.py` y
`discretizar`): las restricciones M12 de la cola dependen de la memoria **solo** a través de la obligación residual
⌈max(0, T − tempo)⌉; por tanto cualquier tiempo en el estado ≥ T produce la **misma** cola, y el planificador usa
tempo = ⌈T⌉ − ρ. Con `cumprir_na_janela` en las ventanas intermedias (exigido por la configuración cuando hay
generadores y el signo está condicionado), la obligación residual de un evento dentro de la ventana es 0 en b; una
obligación HEREDADA que excede la ventana es un hecho conocido en τ_k y el modo queda **fijo** (u0, ρ = obligación −
N_kΔ). Un estado terminal cuya memoria no coincida con un modo del signo es **rechazado** (validación del contrato +
auditor: `modo_memoria_incompativel`, `estado_terminal_fora_dos_modos`); nunca se atribuye a la batería el valor de
estar encendido (familia V_σ separada por modo, H9).

### 4.4 Potencia del último intervalo (rampas de transición)

Lema implementado en `rampa_inativa_na_fronteira`: con u_{b−1} = 1, la potencia p_{b−1} no restringe la cola si
P_max − P_min ≤ min(R⁺Δ, R⁻Δ) y (parada no representable o S⁻ ≥ P_max). En caso contrario el modo **fija** p_{b−1}
(p del plan largo, o P_on_min si el plan largo no enciende la unidad) y el MILP corto la respeta
(`P_fix s ≤ p ≤ P_fix + (P_max − P_fix)(1 − s)`, coeficientes = límites físicos declarados).

## 5. Método de estimación del valor futuro (evaluación crítica)

| Alternativa | Implementación | Ventajas | Límites | Decisión |
|---|---|---|---|---|
| 1. Referencia terminal energética del plan largo | `referencia_energia_dura` (E(N) ≥ E_ref) | barata (1 MILP) | no es valor económico; el plan largo con previsión puntual puede ser frágil; restricción dura puede volver inviable | **ablación experimental** |
| Condición blanda | `referencia_energia_branda` ρ·max(0, E_ref − E) | siempre factible | ρ es heurística DECLARADA (rotulada), no derivada | **ablación experimental** |
| 2. Valor marginal por reoptimización paramétrica | `valor_marginal_local`: λ = −(V(E⁺) − V(E⁻))/(E⁺ − E⁻) con E± = E_ref ± δ factibles; dominio [E⁻, E⁺] | interpretación económica directa (R$/kWh) | **local**; falla en quiebres/discontinuidades (UC) y en umbrales de factibilidad; no separable para varios bancos | alternativa; **indisponible** cuando el error en los extremos supera la tolerancia (H10: en τ_6 de H2 la diferencia central 0,99 cae sobre el quiebre 1,49/0,49 ⇒ rechazada) |
| 3. Función costo-a-futuro lineal por tramos | `custo_futuro_pwl`: V^tail evaluado en una grilla de energías por modo; refinamiento adaptativo 1D por bisección hasta tolerancia; frontera de factibilidad por bisección (conservadora); 2D por envolvente convexa **verificada en la muestra** (no prueba global) | valor económico global en el dominio muestreado; captura umbrales de factibilidad (dominio) y no convexidad 1D; exacta en los puntos (MILP auditado) | costo computacional (N_modos × N_puntos MILP por ventana); 2D solo convexo; interpolante, no identidad | **método PRINCIPAL** |
| Multiplicadores duales del MILP | — | — | **prohibido**: con variables enteras no son precios sombra económicamente válidos | descartado |

Para una batería con valor útil, λ_E = −∂V/∂E y la aproximación local es V̂(E) = V(E_ref) − λ_E (E − E_ref): **aproximación
local, no identidad global** (contrato y docstrings). Si una señal no puede calcularse de forma defendible
(falla de una evaluación, dominio no conexo, tolerancia no alcanzada, 2D no convexo, >2 bancos, modos > límite) el
planificador emite `qualidade.estado = "indisponivel"` con el motivo y la evidencia (puntos/sensibilidad conservados) y
el controlador aplica la **degradación declarada** (§9).

Calidad registrada por señal: errores en puntos de validación (punto medio de cada segmento final 1D; centro de cada
celda 2D; extremos ±δ en la local), gap absoluto máximo de las evaluaciones (solo `aceito_otimo` certifica un punto),
número de evaluaciones y tiempos.

## 6. Planificador de largo plazo (`hierarquia/planejador.py`)

En τ_k (emisión): (1) previsión LARGA [τ_k, τ_k + H_L,k) emitida por el **mismo proveedor** a partir del **mismo
instantáneo K6** de la decisión y validada (`validar_previsao_janela`: causalidad, cobertura, vínculo informacional,
independencia de la verdad); (2) tarifas de decisión seleccionadas **en τ_k** (`selecionar_perfil_causal` en el instante
de EMISIÓN — seleccionar en τ_b filtraría revisiones futuras); (3) **plan largo** desde x_k (referencia E_ref, modo de
referencia, diagnóstico; **nunca se ejecuta**); (4) **colas paramétricas** para la frontera b de cada ventana objetivo;
(5) señal(es) sellada(s) con los hashes de previsión larga, instantáneo, tarifas, modelo de red, estado de emisión,
configuración del planificador, Φ_L, resolvedor y plan largo.

Política de actualización (`POLITICAS_ATUALIZACAO`): `a_cada_janela` o `periodica` (P ventanas; en τ_p se emite un
LOTE de señales para las fronteras de las P ventanas del cronograma nominal, con fin de planificación fijo p + H_L). Una
señal solo vale para SU ventana/frontera; frontera divergente o señal inválida ⇒ replanificación registrada.

## 7. Interfaz de coordinación (`SinalValorFuturo`, esquema 1)

Campos: identidad (misión, microrred, escenario), ventana y k de aplicación, instantes de emisión/aplicación/frontera,
índice de frontera global, fin del planeamiento y cola, UIDs de bancos (orden de las dimensiones) y generadores,
unidades (`R$`, `kWh`) y convención de signos (texto exacto `CONVENCAO_SINAIS`), modos con representación, puntos
(valor + límite inferior dual + clasificación), energías inviables muestreadas, dominio por banco, convexidad
verificada en la muestra, referencia, sensibilidad local, ρ (solo branda), Φ_L, calidad, hashes de procedencia, procedencia,
diagnóstico de TODOS los modos terminales (`diagnostico_modos`, A02) y
**sello SHA-256**.

El MPC **rechaza** (`validar_sinal_para_entrada` + `validar_sinal_para_janela`): sello adulterado, esquema/perfil,
unidades/convención, no finito, otra microrred/escenario, otra misión, **otra ventana (caducidad)**, otra frontera,
emisión posterior a τ_k, **instantáneo de emisión ≠ corte K6 sellado** (causalidad verificada contra el libro),
modelo de red/configuración del planificador distintos, recursos distintos, dominio fuera de los límites físicos,
puntos fuera del dominio/no crecientes/sin cobertura, 2D sin convexidad verificada en la muestra, señal válida que omite un modo no resuelto, modos × memoria incompatibles,
señal indisponible.

## 8. MILP corto 3C-4 (`milp/modelo_3c4.py`, `solver_3c4.py`)

Composición sobre `construir_modelo_3c3` (inalterado). Objetivo `J = J_S + θ`, con J_S = términos 3C-3 de la ventana y
θ el término terminal:

* selección exacta de modo `s_i ∈ {0,1}`, `Σ s_i = 1`, `u_{g,N−1} = Σ_{i: g ON} s_i` (sin Big-M);
* 1D: segmentos consecutivos con binarias explícitas (sin SOS, como M14–M16): `Σ_j δ_ij = s_i`, `φ_ij ≤ δ_ij`,
  `e_{b,N} = Σ[E_j δ + (E_{j+1} − E_j) φ]`, `θ = Σ[V_j δ + (V_{j+1} − V_j) φ]` — representación EXACTA del interpolante
  (convexo o no) y del dominio;
* 2D: `λ_ij ≥ 0`, `Σ_j λ_ij = s_i`, `e = Σ λ x_j`, `θ = Σ λ V_j` (envolvente convexa; solo con convexidad verificada EN LA MUESTRA — grilla y centros —, no prueba global);
* local: modo fijo, `E_lo ≤ e_{b,N} ≤ E_hi`, `θ = V_ref − Σ λ_b (e_{b,N} − E_ref,b)`;
* referencias: `e_{b,N} ≥ E_ref` (dura) o `σ ≥ E_ref − e`, `θ = ρ Σ σ` (branda); Φ declarados (lineal, energía mínima).

Separación registrada (`ResultadoResolucao3C4`, `DecomposicaoObjetivo`): **costo operativo previsto** J_S, **costo
futuro estimado** θ (clave `custo_futuro_estimado`, nunca sumada al realizado), **objetivo total** del solver, **costo
realmente incurrido** (contabilidad 3C-3 de los intervalos aplicados) y valoración terminal declarada del estado final
EJECUTADO (registro de misión, nunca costo). Los horizontes superpuestos nunca se suman (invariante 3C-2).

**Auditor independiente** (`hierarquia/auditor.py`, sin Pyomo): `auditar_3c3` sobre el núcleo con los costos 3C-3
**sin** el término terminal + auditor terminal que recalcula E(N), la memoria terminal (`memoria_terminal`), el modo
compatible único, el dominio, V̂ por evaluación exacta (`valor.py`: interpolante 1D, envolvente 2D por enumeración de
Carathéodory, lineal local), referencias, integralidad de la selección y **total = total 3C-3 reconstruido + θ
recalculado**. "optimal" del HiGHS no basta (H16: θ, E(N) o total alterados ⇒ `rejeitado_auditoria`).

## 9. Controlador jerárquico causal (`hierarquia/mpc.py`)

`ControladorMPCHierarquico(ControladorMPCConectado)` sobrescribe SOLO puntos de extensión. Ciclo por τ_k: (1) sellar
I_k [orquestador]; (2) x_k ejecutado [orquestador]; (3) previsión corta [orquestador] y larga [3C-4]; (4) planificar o
usar la señal del lote vigente PARA ESTA ventana; (5) verificar la señal; (6) MILP 3C-4 (adaptador `ResolvedorMILP3C4`);
(7–9) aplicar m_k, conciliar y contabilizar con la maquinaria 3C-3 **intacta** (K6, observaciones tardías,
confirmaciones, suspensión, checkpoints, PCC, ajuste local, liquidación); (10) replanificar según la política. Toda
reoptimización parte del estado EJECUTADO; el plan largo nunca toca la planta.

Degradación declarada (`DEGRADACOES`, sin defecto): `interromper` (falla `bloqueado_validacao`), `sem_valor_futuro_rotulado`
(término `nenhum_declarado`, ventana rotulada DEGRADADA — **equivale exactamente al MPC 3C-3**: mismos despachos
aplicados, test `test_degradacao_sem_valor_futuro_equivale_ao_mpc_3c3`), `referencia_terminal_do_plano_longo` (E(N) ≥
E_ref del plan largo como `energia_minima_declarada`).

Registros: `RegistroCoordenacao3C4` sellado por POSICIÓN (señal o indisponibilidad, origen, lote emitido, plan largo
resumido, evaluaciones, decomposición, falla, tiempos fuera de la impresión determinista) comprometido en el registro
3C-0 de la ventana ejecutada **antes** de su sello (`hashes['coordenacao_3c4']`, impresión, `entrada_3c4`,
`sinal_valor_futuro`); `VinculoHierarquico3C4` por punto de reanudación (incluye el lote pendiente sellado);
`RegistroMissaoHierarquica3C4` al final (vínculos a los registros de misión MPC y de red, secuencia de coordinaciones,
conteos, valoración terminal declarada del estado final, tiempos del planificador). Reanudación
(`retomar_controlador_hierarquico`): verificación 3C-3 completa + coordinaciones de todas las posiciones + compromiso
en cada registro 3C-0 + vínculo + lote. Auditoría integral (`auditar_missao_hierarquica`): auditoría integral 3C-3 +
sección jerárquica (recalcula el término terminal a partir del plan 3C-0 y de la memoria planificada del anexo 3C-3,
causalidad contra el libro, compromisos, ausencia de valor futuro en el costo realizado) + registro de misión 3C-4.

## 10. Decisiones y contradicciones

| ID | Decisión | Alternativa descartada |
|---|---|---|
| D-3C4-01 | Contrato EMBRULHO `EntradaHierarquica3C4` = `EntradaRede3C3` (validada sin relajación) + `TermoTerminal3C4` | Campo opcional en `EntradaRede3C3` (rompería hashes/perfil 3C-3) |
| D-3C4-02 | Método principal: PWL de V^tail por reoptimización paramétrica auditada, por modo terminal | Duales del MILP (prohibidos); penalidad SOC arbitraria |
| D-3C4-03 | Misma malla Δ en ambos niveles | Segunda resolución sin transformación energética comprobada |
| D-3C4-04 | Modo = (ligado, obligación residual); `cumprir_na_janela` exigido con generadores; obligación heredada ⇒ modo fijo | Modos (u, ρ) con ρ libre (más evaluaciones; propuesto para 3D) |
| D-3C4-05 | Tarifas y previsión del planificador seleccionadas en el instante de EMISIÓN | Selección en τ_b (fuga de información) |
| D-3C4-06 | Señal válida solo para su ventana/frontera; lote periódico con fin fijo p + H_L | Reutilizar señales caducadas |
| D-3C4-07 | Degradación declarada; `sem_valor_futuro_rotulado` ≡ MPC 3C-3 | Inventar precio/aceptar aproximación inválida |
| D-3C4-08 | Comparación con tratamiento terminal explícito (Φ_L común; ajuste por valoración declarada en faixa de precios) | Afirmar superioridad por costo acumulado con estados finales distintos |

| ID | Hallazgo | Tratamiento |
|---|---|---|
| **C-3C4-01** | El orquestrador compara `res.hash_entrada` con `_hash_entrada(e)` y `plano_de_resultado_3c3` exige perfil 3C-3; la evidencia 3C-3 (registro 3C-0, anexo 3C-3, auditoría integral) exige plan con la entrada NÚCLEO | `ResultadoNucleo3C3De3C4` = **visión** del despacho 3C-4 sobre la entrada núcleo (mismas variables, aprobado por el auditor 3C-3), con `perfil_resolucao = v1.1-3C-4`, `resultado_3c4` adjunto y `custos_modelo` con `custo_futuro_estimado` SEPARADO; `plano_de_resultado_3c4` verifica perfil, hashes 3C-4/núcleo, identidad del despacho y auditoría terminal antes de crear el plan; el registro 3C-0 declara `formulacao = v1.1-3C-4` y compromete `entrada_3c4`. El óptimo es del problema 3C-4 (documentado), no del 3C-3 |
| **C-3C4-02** | Cuatro guardias anteriores impedían por construcción añadir el 3C-4 (lista nominal de módulos con Pyomo; `ADICOES_*`; prefijos admitidos por las guardias 3C-2/3C-3) | Ajuste **nominal mínimo**: `milp/modelo_3c4.py`, `milp/solver_3c4.py` en la lista; `ADICOES_3C4` (4 archivos, solo adición); prefijos `ems_v2/hierarquia/`, `fixtures_3c4.py`, `tests/ems_v2/test_ems_v2_3c4_`. Nueva guardia desde `10365c5`: solo esas 4 guardias cambian; ningún otro archivo modificado |
| **C-3C4-03** | **Defecto heredado (3C-0/3C-2/3C-3)**: la energía ejecutada acumulaba deriva de coma flotante (10,000000000000002 kWh con C = 10) y la validación SIN recorte de la ventana siguiente la bloqueaba | **Corregido por hotfix AUTORIZADO** en la auditoría del PR #17 (§10b, B3C4-01); el segundo artefacto (residuo negativo del solver en P_imp × C-01, B3C4-10) fue corregido por el hotfix AUTORIZADO de la 2ª auditoría (§10c) |
| C-3C4-04 | El campo 3C-0 `valor_futuro` sigue `nao_implementado_3C0` aunque el 3C-4 estime V̂ | Esquema 3C-0 intacto; la estimación vive en la coordinación 3C-4 y en `custo_objetivo_planejado` separada; `contabilizado_como_custo = False` auditado |

## 10b. Auditoría independiente del PR #17 (commit auditado `9630e73`) — correcciones

Los tres defectos se **reprodujeron sobre `9630e73` antes de corregir** (salida literal en
`EVIDENCIA_3C4_EJECUCION.md` §4). Correcciones en `c964a2e`.

| ID | Antes (`9630e73`, reproducido) | Después |
|---|---|---|
| **C-3C4-A01** | Un `RegistroMissaoHierarquica3C4` alterado y RE-SELADO pasaba la auditoría integral (`aceito = True`) con `contagens`, `energias_finais_kWh`, `valoracao_terminal_declarada_R`, `hash_configuracao_rede`, `missao_uid` o `tempos_planejador_s` (negativo o inflado) falsos | `verificar_registro_hierarquico` confronta CADA campo con su fuente: contagens = `contagens_de(coordenações)`; energías = estado final EJECUTADO del registro de misión; valoración = Φ_L declarado (`termo_longo` de la configuración suministrada) en ese estado; `hash_modelo_rede`/`hash_configuracao_rede`/`hash_configuracao_planejador` = hashes de los objetos SUMINISTRADOS (obligatorios); `missao_uid` = identidad del registro de misión y de cada coordinación; tiempos: claves conocidas, reales finitos ≥ 0, total ≥ componentes y **igualdad con la suma de las mediciones selladas en las coordinaciones** (coherencia con la fuente registrada; NO reproducción determinista — son medidas de reloj). El registro final se construye con las mismas funciones (`contagens_de`, `tempos_planejador_de`, `valor_termo_declarado`), y la retomada reconstruye los tiempos desde las coordinaciones. El SELLO solo detecta alteración del contenido sellado; no identifica una fuente confiable (B3C4-08) |
| **C-3C4-A02** | `_modo_1d` clasificaba un modo `inviavel` cuando la grilla inicial no tenía ningún punto factible; con dos modos, el más barato (región factible estrecha [7,1; 7,9] kWh fuera de la grilla 0/5/10/15/20) era **omitido** y la señal salía `valido` | Estados de modo (`ESTADOS_MODO`): `valido`, `inviavel` (solo con **certificado de cobertura**: el MISMO MILP 3C-4 con la energía inicial LIBRE en toda la faixa — `resolver_cobertura_3c4`; prueba del B&B del HiGHS, no certificado independiente de Farkas), `dominio_indeterminado` (sin certificado o inconcluso ⇒ el modo no puede excluirse ⇒ **señal indisponible**), `indisponivel` (dominio no conexo certificado, tolerancia no alcanzada, 2D no convexo en la muestra). Un certificado factible propone E* fuera de la grilla, que se **re-evalúa** por la resolución auditada normal. Tras la bisección, las regiones excluidas a cada lado se certifican; el dominio declarado es una **aproximación INTERNA conservadora** (margen ≤ `tolerancia_dominio_kWh`). `SinalValorFuturo.diagnostico_modos` registra TODOS los estados terminales con sus certificados; una señal `valido` con un modo no resuelto es rechazada (`sinal_valido_com_modo_nao_resolvido`). 2D: `convexidade_verificada_na_amostra` (grilla + centros), descrita como verificación sobre la muestra, no prueba global. No se afirma exhaustividad más allá del certificado del solver |
| **B3C4-01** (hotfix autorizado) | `P_d = −1,7763568394002505e-15` kW (residuo primal del HiGHS) ⇒ `e = 10,000000000000002` = C + 1 ulp, aceptado por el ejecutor (≤ C + tolE D07) y transportado; la validación 3A de la ventana siguiente (`e0 > C`) interrumpía la misión 3C-3 original (H9) | Política `projecao_numerica_limite_energia_v1` (función única `energia_apos_intervalo` + `projecao_numerica_energia` en `ponte/execucao.py`, usada por los ejecutores 3C-0/3C-1 y 3C-3): un exceso sobre un límite DECLARADO [s_min C, s_max C] ≤ ε_num = min(tolE_D07, 16·u·S) (u = 2⁻⁵³; S = \|α e0\| + h(η_c\|P_c\| + \|P_d\|/η_d) + max\|lim\|) se proyecta al límite con aviso `projecao_numerica_limite_energia` (bruto, límite, corrección, ε_num). Excesos mayores: tratamiento D07 inalterado (aceptados hasta tolE y transportados SIN cambio; > tolE ⇒ inexequible). La auditoría reconstruye **bit a bit** cada proyección desde datos sellados (`reconstruir_projecoes_energia`; sección `projecoes_numericas`). El mismo valor (10,0) aparece en la trayectoria, el registro 3C-0, el checkpoint, la ventana siguiente y el punto de retomada |

**Archivos protegidos modificados (solo B3C4-01):** `ems_v2/ponte/execucao.py` (SHA-256₁₆ `a3f64678500a51d0` → `cdad389b48ee3d24`)
y `ems_v2/rede/execucao.py` (`71db8fd2e405e2ad` → `507c7ae2de09217a`): 62 líneas añadidas, 13 eliminadas — la recurrencia
M07 pasa a la función compartida (misma aritmética, mismos resultados bit a bit fuera de la política), la proyección y
el aviso. Guardias ajustadas nominalmente y una nueva (`test_hotfix_b3c4_01_restrito_a_projecao_numerica`) que admite
solo esas líneas eliminadas y prohíbe `min(max(` / `clip(`. Regresiones 3C-0, 3C-1, 3C-2 (E1–E8 con huellas), 3C-3
(G1–G15) y 3C-4 sin cambios.

**Detenido y documentado (fuera de la autorización): B3C4-10.** Con la energía corregida, la misión 3C-3 original de H9
avanza hasta k = 10 y se detiene por un SEGUNDO artefacto heredado: `P_imp = −8,881784197001252e-16` kW rechazado por la
regla C-01 del 3C-3 (programa real ≥ 0, sin recorte), aprobada en la auditoría del PR #16. Corregirlo reinterpretaría
una regla de contrato auditada ⇒ requiere decisión del responsable (`BRECHAS_3C4.md`).

**Afirmaciones que se sostienen después de las correcciones:** el registro final de misión es verificable contra sus
fuentes (salvo re-sellado en bloque de TODOS los artefactos, B3C4-08); un modo terminal solo se excluye con certificado
de cobertura del solver; los dominios son aproximaciones internas conservadoras; la deriva de energía de 1 ulp ya no
interrumpe misiones y su corrección es auditable; H2/H6/H7/H8/H10/H17 reproducen los mismos costos. **No se sostiene:**
exhaustividad independiente del solver, convexidad global en 2D, ni comparaciones H9 con la línea de base 3C-3 (B3C4-10).

## 10c. Segunda auditoría del PR #17 (HEAD auditado `8f48aed`) — hotfix AUTORIZADO B3C4-10

**Autorización:** corregir el residuo numérico negativo del solver en las variables de intercambio del PCC. **No** se
autoriza relajar ni eliminar la regla C-01 del 3C-3: `valor_intercambio_valido`, `programa_valido`, `validar_programa`
y `plano_de_resultado_3c3` son **idénticos (AST) a la base `10365c5`** (guardia
`test_hotfix_b3c4_10_restrito_e_regra_c01_identica_a_base`); toda consigna o programa EXTERNO con negativo (incluso
−8,88e-16 o −5e-324), NaN, ±Inf, booleano o incompleto sigue rechazado.

**Reproducción antes de corregir (`8f48aed`, `EVIDENCIA_3C4_EJECUCION.md` §4.4):** H9, `ControladorMPCConectado`
(perfil 3C-3 original), ventana k = 10 (N_k = 2, m_k = 1, inicio 2026-01-01T10:00Z); HiGHS 1.15.1 `optimal`
(`convergenceCriteriaSatisfied`, gap 0, objetivo 20,05) devuelve `P_imp = (−8,881784197001252e-16, 5,0)`,
`P_exp = (0, 0)`; PCC `somente_importacao`, P̄_imp = 50 kW; la variable es `NonNegativeReals` (valor por DEBAJO de la
cota 0, dentro de la `primal_feasibility_tolerance` = 1e-7 del HiGHS, no alterada por `ConfiguracaoSolver`); el
auditor 3C-3 ACEPTA (pcc_dominio 8,88e-16 ≤ tolP 1,5e-5); la primera función que rechaza es `plano_de_resultado_3c3`
(`intercambio_programado_invalido`) ⇒ `falha_integridade`, misión interrumpida en k = 10.

**Política `residuo_numerico_pcc_v1`** (`ems_v2/rede/execucao.py`: `normalizar_residuos_pcc`, `escala_balanco_pcc`,
`limiar_residuo_pcc`, `NormalizacaoNumericaPCC`, `aviso_normalizacao_pcc`):

1. **Dónde:** SOLO en la frontera de EXTRACCIÓN de los resolvedores (`resolver_3c3`, `resolver_3c4`), sobre los valores
   que el PROPIO solver devolvió para P_imp/P_exp, ANTES del auditor independiente y del plan. Ningún otro código la
   llama (el ejecutor, la planta, los programas y `plano_de_resultado_3c3` siguen aplicando C-01 sin excepción).
2. **Cota:** v < 0 se normaliza a 0,0 solo si |v| ≤ ε_pcc,t = min(κ·u·S_t, tol_fact_solver, tolP_D07,t), con κ = 16,
   u = 2⁻⁵³, tol_fact_solver = 1e-7 (factibilidad primal del HiGHS), tolP_D07,t = 1e-5 + 1e-7·S_t y
   S_t = 1 + Σ|P_R| + Σ(|P_c| + |P_d|) + Σ|p| + Σ|ℓ| + |d| + P̄_imp,t + P̄_exp,t (escala del balance M02 del intervalo;
   la carga queda acotada por el balance; reconstruible del plan y del modelo). Así la cota depende de la precisión
   numérica Y de las tolerancias de factibilidad: nunca supera la del solver ni la del auditor.
3. **Fuera de la cota:** NO se normaliza ni se recorta: el resolvedor rechaza la solución
   (`intercambio_negativo_fora_da_politica_numerica`, `rejeitado_auditoria`); valores extraídos no finitos/no reales ⇒
   `intercambio_extraido_invalido`. Valores 0 (incl. −0,0) y positivos: intactos (mismos objetos).
4. **Registro:** `NormalizacaoNumericaPCC` (PCC, grandeza, intervalo de la ventana, bruto, normalizado, diferencia,
   umbral, escala, motivo) en `ResultadoResolucao3C3/3C4.normalizacoes_numericas` + aviso `normalizacao_numerica_pcc`
   (`repr` exacto de cada número) en el resultado ⇒ código en el `ResumoResolucaoJanela` sellado de la ventana; en el
   registro 3C-0 de la ventana, el aviso y el hash `normalizacoes_pcc_b3c4_10` = SHA-256 de las normalizaciones,
   comprometidos ANTES del sello (`ControladorMPCConectado._artefatos_registro`). Sin normalización: ningún aviso,
   ninguna clave nueva ⇒ registros, hashes y huellas históricas idénticos (E1–E8, G1–G15 sin cambios).
5. **Revalidación:** el despacho normalizado pasa por el auditor independiente 3C-3/3C-4 (balance, dominio,
   exclusividad, sentido, costos contra el modelo) y por la integridad del testigo: una "normalización" que rompa el
   balance (anular una importación real) o la economía (importar y exportar a la vez) es RECHAZADA.
6. **Auditoría:** `rede/auditoria.reconstruir_normalizacoes_pcc` (verificador ÚNICO desde A03, §10d; sección
   `normalizacoes_pcc` de las auditorías integrales 3C-3 y 3C-4) reconstruye cada normalización desde artefactos SELLADOS: aviso ↔ hash comprometido
   (`normalizacao_pcc_nao_comprometida`); código en la resolución sellada (`normalizacao_pcc_sem_origem_no_solver`:
   el valor bruto proviene del solver, no de una consigna externa — éstas nunca pasan por la política);
   programa del anexo 3C-3 = 0,0; bruto < 0; diferencia = −bruto; |bruto| ≤ umbral; motivo = política; S_t y umbral
   RECALCULADOS desde el plan 3C-0 y los límites del modelo suministrado (`normalizacao_pcc_fora_da_politica`);
   ilegible ⇒ `normalizacao_pcc_ilegivel`.

**Archivos protegidos modificados (solo B3C4-10):** `ems_v2/rede/execucao.py` (bloque nuevo + 2 importaciones; C-01 sin
cambios), `ems_v2/milp/solver_3c3.py` (llamada a la política en la extracción), `ems_v2/milp/resultado_3c3.py` (campo
`normalizacoes_numericas = ()`), `ems_v2/rede/mpc.py` (aviso + hash en el registro 3C-0). Además (no protegidos):
`ems_v2/milp/solver_3c4.py`, `ems_v2/hierarquia/auditoria.py`. Guardias: `HOTFIX_B3C4_10` y `REMOVIDAS_B3C4_10`
(solo líneas de importación/`__all__`/argumento final reescritas) en `test_ems_v2_3c4_isolamento.py`.

**Después:** H9 con las cinco estrategias concluye (tabla en §11 y `EVIDENCIA_3C4_EJECUCION.md` §4.4); la normalización
única de H9 (k = 10, P_imp, bruto −8,881784197001252e-16, umbral 1,35e-13, S = 76) aparece en el resultado, la
resolución sellada, el registro 3C-0 y la reconstrucción de la auditoría. **Se sostiene:** C-01 intacta para toda
entrada externa; solo residuos del solver por debajo de la menor de las tolerancias de precisión/factibilidad se
normalizan, con registro reconstruible; comparación H9 contra la línea de base 3C-3 con condiciones terminales
idénticas. **No se sostiene:** que el umbral sea una cota de error hacia atrás del HiGHS (es una política declarada);
que el hash sea firma (B3C4-08).

## 10d. Último cierre de la auditoría del PR #17 (HEAD auditado `8dd8edb`) — C-3C4-A03

Coherencia DOCUMENTAL de B3C4-10. No cambia la física, la matemática, la política numérica ni C-01 (guardia
`test_a03_politica_b3c4_10_e_c01_inalteradas_desde_o_head_auditado`: `rede/execucao.py`, `ponte/execucao.py`,
`milp/solver_3c3.py`, `milp/solver_3c4.py`, `milp/resultado_3c3.py` y `rede/mpc.py` idénticos a `8dd8edb`).

| ID | Antes (`8dd8edb`, reproducido con cadenas selladas CONSISTENTES: el propio resolvedor fabrica las evidencias) | Después |
|---|---|---|
| **A03-1** | `reconstruir_normalizacoes_pcc` omitía la ventana si el registro 3C-0 no tenía aviso NI hash (`if not avs and not tem_hash: continue`) aunque el resumen sellado de la resolución declarara `normalizacao_numerica_pcc` ⇒ aceptado | Las TRES evidencias (código en la resolución sellada; avisos; hash comprometido en el registro 3C-0) están todas presentes y coherentes o todas ausentes. Ausentes las tres = ventana sin normalización (incluye todo registro anterior a B3C4-10: ninguna obligación nueva). Código sin aviso ni hash ⇒ `normalizacao_pcc_declarada_sem_registro`; aviso/hash sin código ⇒ `normalizacao_pcc_sem_origem_no_solver`; aviso sin hash, hash sin aviso o hash alterado ⇒ `normalizacao_pcc_nao_comprometida` |
| **A03-2** | La auditoría INTEGRAL 3C-3 (`auditar_missao_conectada`) no reconstruía las normalizaciones: una normalización injustificada (bruto −1e-3 ≫ umbral) registrada en una cadena consistente era ACEPTADA (sellos, documental, balance y costos aprobados) | El verificador ÚNICO vive en el núcleo de red (`ems_v2/rede/auditoria.py`: `reconstruir_normalizacoes_pcc`, sin dependencia de `ems_v2.hierarquia`, guardia AST) y la auditoría integral 3C-3 añade la sección `normalizacoes_pcc` (+ `RelatorioAuditoriaMissaoConectada.normalizacoes_pcc = ()`). La auditoría 3C-4 lo reutiliza a través de la 3C-3: su sección `normalizacoes_pcc` ESPEJA la de la 3C-3 sin re-ejecutar ni duplicar constataciones; `hierarquia.auditoria.reconstruir_normalizacoes_pcc` sigue disponible (re-exportación del MISMO objeto). El escopo analítico parcial no cambia (no tiene artefactos documentales) |

**Archivos modificados (A03):** `ems_v2/rede/auditoria.py` (protegido; solo adición: verificador, sección
`normalizacoes_pcc` en la auditoría integral, campo del informe, `__all__`; `_balanco_3c3`, `custo_rede_independente`,
`_analitica`, `auditar_missao_conectada_analitica` y `_documental` idénticos a la base — guardia
`test_a03_auditoria_3c3_so_acrescenta_a_secao_de_normalizacoes`) y `ems_v2/hierarquia/auditoria.py` (implementación
local retirada; reutilización). Tests: `test_ems_v2_3c4_a03.py` (nueva), `test_ems_v2_3c4_isolamento.py` (3 guardias,
`HOTFIX_A03`), `test_ems_v2_3c4_b3c4_10.py` (importación de la expresión regular desde el nuevo módulo).

**Registros históricos:** una misión G11 ejecutada por el CÓDIGO de `10365c5` (artefactos escritos en disco por ese
código) se relee y la auditoría integral actual la ACEPTA sin exigir evidencias nuevas; su huella determinista es igual
a la del código actual. **Límite:** los sellos SHA-256 detectan alteración frente al artefato sellado; no son firma
ni prueban la procedencia auténtica del solver (B3C4-08): un conjunto re-sellado en bloque que contenga una
normalización DENTRO de la política no es distinguible de uno legítimo.

## 11. Experimentos (detalle y tablas: `EVIDENCIA_3C4_EJECUCION.md`)

| Exp. | Resultado (sintético, Δ = 1 h, K_M = 12, N = 3, m = 1, H_L = 10, Φ_L = 0 declarado común) |
|---|---|
| H1 | tarifa plana: todas las estrategias R$ 50,2; λ = 0,49 en todo el dominio; efecto de anticipación 0 (sin incentivo artificial) |
| H2 | pico 1,5 en h8–9: MPC sin señal R$ 60,4 (descarga temprano; recarga tardía limitada a 5 kW) × jerárquico PWL R$ 50,2; E final 0 en ambos ⇒ **anticipación = R$ 10,2 comparable**; reoptimización (OL × encolhido) = 0; jerárquico = oráculo |
| H3 | pico dentro de H_S: beneficio adicional 0 |
| H4 | λ₀ en τ_0: plana 0,49 < pico lejano 0,51 (energía reponible desde la red) < pico próximo 1,49 (no hay tiempo de recargar) |
| H5 | demanda realizada ≠ prevista (misma verdad): ambos concluyen, jerárquico más barato con condiciones terminales iguales; auditoría con separación previsión × realización aprobada |
| H6/H10 | V(0, 5, 10, 15, 20) = 25; 17,55; 10,1; 7,65; 5,2 exactos ⇒ λ = 1,49 en [0, 10] y 0,49 en [10, 20]; local unilateral λ = 0,51 en τ_0; local INDISPONIBLE en τ_6 (quiebre) |
| H7/H8 | límite de importación 0 / PCC indisponible previsto en h8–9 con tarifa PLANA: MPC sin señal **inviable** (misión interrumpida), jerárquico PWL concluye (R$ 50,2) con dominio E ≥ reserva — valor por restricción FÍSICA; local también falla (limitación) |
| H9 | PEMFC + banco: dos modos por señal (valor de estar ENCENDIDO separado del de la energía), obligación residual planificada 0, sin obligaciones pendientes, auditoría aprobada. Jerárquico PWL y referencia blanda R$ 129,6 (PEMFC encendida 25 200 s al final) × horizonte completo/open-loop/oráculo R$ 127,6 (18 000 s): brecha de R$ 2,0 atribuible a `cumprir_na_janela` con N = U = 3 (B3C4-02). Tras los hotfixes B3C4-01 (proyección de 1 ulp en k = 8) y B3C4-10 (residuo P_imp = −8,88e-16 normalizado en k = 10), las CINCO estrategias concluyen con condiciones terminales idénticas (E = 0, PEMFC encendida, sin obligaciones): MPC 3C-3 sin señal R$ 129,8; PWL, referencia dura y blanda R$ 129,6 ⇒ anticipación R$ 0,2 comparable; horizonte completo R$ 127,6 (brecha R$ 2,0 = B3C4-02, no atribuida a la aproximación del valor futuro) |
| H11 | dominio inalcanzable ⇒ MILP inviable (sin recorte); señales caducadas/otra frontera/no causales rechazadas; local no defendible ⇒ degradación |
| H12 | intervención en la verdad desde h6: coordinaciones y planos idénticos para k ≤ 6, distintos después |
| H13 | N × H_L (H2): costo no creciente en H_L (N = 3: 55,5 / 50,6 / 50,4 / 50,2 / 50,2 con H_L = 4 / 6 / 8 / 10 / 12); MPC sin señal 65,3 / 60,4 / 55,5 con N = 2 / 3 / 4; con H_L ≥ 10 el jerárquico alcanza el óptimo de información perfecta para todo N ∈ {2, 3, 4} |
| H14 | open-loop, MPC sin señal, encolhido, PWL, local, referencias y oráculo con condiciones idénticas (tabla) |
| H15 | interrupción tras 5 ventanas (política periódica P = 2, lote pendiente) + reanudación: impresiones idénticas |
| H16 | θ/E(N)/total post-solver, coordinación alterada (resellada o no), señal alterada, configuración sustituida, registro de misión adulterado, vínculo/lote alterado ⇒ rechazo |
| H17 | dos bancos: envolvente convexa 2D verificada en la muestra; MPC sin señal R$ 55,5 × jerárquico R$ 50,2 |
| H18 | regresión: suites 3A–3C-3 (incl. G1–G15, E1–E8 con pins) sin cambios |

## 12. Diseño experimental (artículo)

* **Reoptimización** = costo(open-loop, N = m = K_M) − costo(MPC encolhido, N = K_M, m = 1): misma información de
  horizonte, difiere la realimentación (en H2–H8 sintéticos = 0: con previsión de tabla exacta la realimentación no
  aporta; con error de previsión (H5) el PCC absorbe el desvío).
* **Anticipación** = costo(MPC sin señal, N, m) − costo(jerárquico, N, m, H_L): idéntica política de reoptimización.
* **Información perfecta** = costo(estrategia) − costo(oráculo); el oráculo es ablación ROTULADA, nunca controlador.
* Se mantienen idénticos estado inicial, microrred, verdad, tarifas de liquidación, PCC, servicio, K_M, reglas de costo,
  aceptación y Φ_L. `comparadores.efeito` solo declara comparable con energía final, ON/OFF y obligaciones iguales y
  misiones concluidas; si no, reporta la diferencia ajustada por valoración terminal declarada en una faja de precios y
  si la ordenación es robusta. Una instancia sintética no establece superioridad general.

## 13. Límites metodológicos

Aproximación interpolante (no función de valor exacta) fuera de los puntos; dominio = aproximación INTERNA
conservadora (margen ≤ tolerancia de dominio) y exclusiones justificadas solo por el certificado de cobertura del
solver (prueba del B&B del HiGHS, sin certificado independiente para MILP; sin certificado ⇒ `dominio_indeterminado` y
señal indisponible — el método no afirma exhaustividad); 2D solo convexo EN LA MUESTRA; >2 bancos no soportados;
modos limitados (`max_modos`); valor determinista bajo previsión puntual (sin incertidumbre estocástica — familia no
modelada `incerteza_estocastica_do_valor_futuro`); costo computacional O(modos × puntos) MILP por ventana (sin promesa de
tiempo real; tiempos solo indicativos); tarifas y equipos sintéticos; misma malla temporal; ninguna microrred del
catálogo ejecuta el EMS V2.
