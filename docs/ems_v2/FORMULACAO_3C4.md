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
| 3. Función costo-a-futuro lineal por tramos | `custo_futuro_pwl`: V^tail evaluado en una grilla de energías por modo; refinamiento adaptativo 1D por bisección hasta tolerancia; frontera de factibilidad por bisección (conservadora); 2D por envolvente convexa **verificada** | valor económico global en el dominio muestreado; captura umbrales de factibilidad (dominio) y no convexidad 1D; exacta en los puntos (MILP auditado) | costo computacional (N_modos × N_puntos MILP por ventana); 2D solo convexo; interpolante, no identidad | **método PRINCIPAL** |
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
verificada, referencia, sensibilidad local, ρ (solo branda), Φ_L, calidad, hashes de procedencia, procedencia y
**sello SHA-256**.

El MPC **rechaza** (`validar_sinal_para_entrada` + `validar_sinal_para_janela`): sello adulterado, esquema/perfil,
unidades/convención, no finito, otra microrred/escenario, otra misión, **otra ventana (caducidad)**, otra frontera,
emisión posterior a τ_k, **instantáneo de emisión ≠ corte K6 sellado** (causalidad verificada contra el libro),
modelo de red/configuración del planificador distintos, recursos distintos, dominio fuera de los límites físicos,
puntos fuera del dominio/no crecientes/sin cobertura, 2D sin convexidad verificada, modos × memoria incompatibles,
señal indisponible.

## 8. MILP corto 3C-4 (`milp/modelo_3c4.py`, `solver_3c4.py`)

Composición sobre `construir_modelo_3c3` (inalterado). Objetivo `J = J_S + θ`, con J_S = términos 3C-3 de la ventana y
θ el término terminal:

* selección exacta de modo `s_i ∈ {0,1}`, `Σ s_i = 1`, `u_{g,N−1} = Σ_{i: g ON} s_i` (sin Big-M);
* 1D: segmentos consecutivos con binarias explícitas (sin SOS, como M14–M16): `Σ_j δ_ij = s_i`, `φ_ij ≤ δ_ij`,
  `e_{b,N} = Σ[E_j δ + (E_{j+1} − E_j) φ]`, `θ = Σ[V_j δ + (V_{j+1} − V_j) φ]` — representación EXACTA del interpolante
  (convexo o no) y del dominio;
* 2D: `λ_ij ≥ 0`, `Σ_j λ_ij = s_i`, `e = Σ λ x_j`, `θ = Σ λ V_j` (envolvente convexa; solo con convexidad verificada);
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
| **C-3C4-03** | **Defecto heredado (3C-0/3C-2/3C-3)**: la energía ejecutada acumula deriva de coma flotante (p. ej. 10,000000000000002 kWh con C = 10) y la validación SIN recorte de la ventana siguiente la bloquea (`energia_maior_que_capacidade`) | **No corregido** (exigiría tocar contratos protegidos): reproducido en `test_h9_linha_de_base_interrompida_por_deriva_numerica_herdada_B3C4_01`; la comparación H9 se declara NO comparable; propuesta en `BRECHAS_3C4.md` (B3C4-01) para autorización |
| C-3C4-04 | El campo 3C-0 `valor_futuro` sigue `nao_implementado_3C0` aunque el 3C-4 estime V̂ | Esquema 3C-0 intacto; la estimación vive en la coordinación 3C-4 y en `custo_objetivo_planejado` separada; `contabilizado_como_custo = False` auditado |

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
| H9 | PEMFC + banco: dos modos por señal (valor de estar ENCENDIDO separado del de la energía), obligación residual planificada 0 en todas las ventanas, sin obligaciones pendientes, auditoría aprobada. Jerárquico R$ 129,6 × información perfecta/open-loop/encolhido R$ 127,6: la brecha de R$ 2,0 es el costo de la condición `cumprir_na_janela` con N = U = 3 (arranque solo en t = 0 de cada ventana; B3C4-02), no de la previsión. Línea de base sin señal y `hier_ref_dura` interrumpidas por la deriva heredada C-3C4-03 (no comparables) |
| H11 | dominio inalcanzable ⇒ MILP inviable (sin recorte); señales caducadas/otra frontera/no causales rechazadas; local no defendible ⇒ degradación |
| H12 | intervención en la verdad desde h6: coordinaciones y planos idénticos para k ≤ 6, distintos después |
| H13 | N × H_L (H2): costo no creciente en H_L (N = 3: 55,5 / 50,6 / 50,4 / 50,2 / 50,2 con H_L = 4 / 6 / 8 / 10 / 12); MPC sin señal 65,3 / 60,4 / 55,5 con N = 2 / 3 / 4; con H_L ≥ 10 el jerárquico alcanza el óptimo de información perfecta para todo N ∈ {2, 3, 4} |
| H14 | open-loop, MPC sin señal, encolhido, PWL, local, referencias y oráculo con condiciones idénticas (tabla) |
| H15 | interrupción tras 5 ventanas (política periódica P = 2, lote pendiente) + reanudación: impresiones idénticas |
| H16 | θ/E(N)/total post-solver, coordinación alterada (resellada o no), señal alterada, configuración sustituida, registro de misión adulterado, vínculo/lote alterado ⇒ rechazo |
| H17 | dos bancos: envolvente convexa 2D verificada; MPC sin señal R$ 55,5 × jerárquico R$ 50,2 |
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

Aproximación interpolante (no función de valor exacta) fuera de los puntos; 2D solo convexo; >2 bancos no soportados;
modos limitados (`max_modos`); valor determinista bajo previsión puntual (sin incertidumbre estocástica — familia no
modelada `incerteza_estocastica_do_valor_futuro`); costo computacional O(modos × puntos) MILP por ventana (sin promesa de
tiempo real; tiempos solo indicativos); tarifas y equipos sintéticos; misma malla temporal; ninguna microrred del
catálogo ejecuta el EMS V2.
