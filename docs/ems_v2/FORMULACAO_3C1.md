# Piso 3C-1 — Unit Commitment dinámico, rampas, permanencias y memoria operativa (formulación ejecutada)

**Estado:** implementado y verificado **en la rama**, sin integración con la UI, el Centro de Operação ni el runtime
V1.6. MILP de **una ventana** (sin MPC recedente, sin valor futuro). Resultados **sintéticos/algebraicos**: no son
validación física de ningún equipo. Base: `main` `81aa09cfb5ee4bd7ff66ec6eec8fa4ccc049fc44` (merge del PR #13).

Perfil nuevo: **`FORMULACAO_3C1 = "v1.1-3C-1"`** (`ems_v2/__init__.py`). API nueva y versionada:
`ems_v2.milp.solver_3c1.resolver_3c1(entrada_3c1, configuracao, compromisso_parcial=None)`.
`ems_v2.milp.solver.resolver` (3B-P) **no fue modificado**.

## 1. Arquitectura (qué se agregó y qué no se tocó)

| Componente | Archivo | Pyomo |
|---|---|---|
| Contrato embrulho, validación, discretización exacta, JSON canónico/hash propios | `ems_v2/compromisso/contrato.py` | no |
| Memoria terminal y garantía de permanencia | `ems_v2/compromisso/memoria.py` | no |
| Preflight 3C-1 (compromiso parcial, obligaciones × disponibilidad, transiciones fijadas) | `ems_v2/compromisso/preflight.py` | no |
| **Auditor independiente 3C-1** | `ems_v2/compromisso/auditor.py` | no |
| Construcción del MILP (reutiliza el constructor 3B-P) | `ems_v2/milp/modelo_3c1.py` | sí |
| API de resolución + resultado | `ems_v2/milp/solver_3c1.py`, `ems_v2/milp/resultado_3c1.py` | sí / no |
| Evidencia reproducible | `ems_v2/milp/evidencia_3c1.py` | sí |
| Integración con la puente 3C-0 (plan, ejecutor, transporte, proyección) | `ems_v2/ponte/compromisso.py` | no |
| Fixtures sintéticas | `ems_v2/fixtures_3c1.py` | no |

**Sin cambios byte a byte** respecto de la base: `ems_v2/contracts.py`, `audit.py`, `reference.py` y todos los
archivos existentes de `ems_v2/milp/` (guardia `test_v16_e_aplicacao_sem_alteracao_desde_a_base_auditada`, §9).
Cambios **aditivos con valor por defecto que reproduce el 3C-0**: `ponte/requisitos.py` (`perfil=None`),
`ponte/projecao.py` (`estados_por_unidade=None`, `perfil=None`), `ponte/preflight.py` (`commitment_3c1=None`),
`capabilities.py` (`CAPACIDADES_3C1`), catálogo (columnas `status_3C1/codigo_3C1/obs_3C1`).

### 1.1 Contrato embrulho (decisión D-3C1-01)

`EntradaCommitment3C1 = (versao_esquema_3c1, versao_formulacao = "v1.1-3C-1", base: EntradaModeloEMS declarada
"v1.1-3B-P", unidades: EspecCommitmentUnidade…, memorias: MemoriaCommitmentUnidade…, politica_permanencia,
termos_adicionais, procedencia)`.

* La **base** es una entrada 3B-P completa (núcleo continuo y económico: M02–M08, M10, M14–M16, términos 3B-P) y es
  validada por `contracts.validar_entrada` **sin relajación**.
* Ninguna `EntradaModeloEMS` puede declarar `v1.1-3C-1`: `FORMULACOES` no cambió ⇒ `formulacao_incompativel`.
  Los contratos anteriores **no ganan** capacidades implícitas.
* El JSON canónico del embrulho usa la misma regla (`contracts.para_dict`): la base embebida tiene **exactamente** el
  diccionario canónico 3B-P. Las entradas 3A/3B-P conservan texto y SHA-256 (pins de `f6d009d` y de `81aa09c` en
  `test_ems_v2_milp_perfil.py` y `test_ems_v2_3c1_contrato.py`). `hash_entrada_3c1` ≠ `hash_entrada(base)`.

## 2. Conjuntos, parámetros y variables

`T = {0..N−1}` intervalos, `K = {0..N}` fronteras, `Δ` [min] (segundos enteros), `h = Δ/60`. `G` = **unidades**
generadoras por UID (`eq-…#k` cuando un registro tiene `quantity > 1`; sin agregación).

| Símbolo | Unidad | Origen | Contrato |
|---|---|---|---|
| `P_min, P_max`, `a_{i,t}` | kW, 1 | base 3B-P | `EspecGerador` |
| `u_i^{−1}`, `p_i^{−1}` | 1, kW | declarados (nunca inferidos) | `EstadoGerador` |
| `R_i^+`, `R_i^−` | kW/min | **obligatorios** si la unidad puede estar ON | `rampa_subida_kW_min`, `rampa_descida_kW_min` |
| `S_i^+`, `S_i^−` | kW | declarados **o** `R·Δ` (D-3C1-02) | `potencia_partida_max_kW`, `potencia_parada_max_kW` |
| `T_i^{on}`, `T_i^{off}` | min | **obligatorios** si la unidad transita | `tempo_min_ligado_min`, `tempo_min_desligado_min` |
| `C_i^{SU}`, `C_i^{SD}` | R$/evento | solo con término `eventos` | `custo_partida`, `custo_parada` |
| `m_i^{SU}`, `m_i^{SD}` | kg/evento | PEMFC con transiciones y `combustivel_h2` | `massa_h2_partida_kg`, `massa_h2_parada_kg` |
| `d_i` (tiempo en el estado), `o_i` (obligación) | s | memoria declarada/transportada | `MemoriaCommitmentUnidade` |
| `u_{i,t}`, `y_{i,t}`, `z_{i,t}` | {0,1} | decididos por el MILP | `pyomo:u/y/z` |
| `p_{i,t}` | kW | decidido | `pyomo:p` |

## 3. Restricciones

### M09 — commitment y transiciones

```
u_{i,t} − u_{i,t−1} = y_{i,t} − z_{i,t}      (u_{i,−1} = u_i^{−1} declarado)
y_{i,t} + z_{i,t} <= 1
u_{i,t} <= a_{i,t}
```

**Sin eventos ficticios (prueba).** Con u, y, z binarias: si `u_t = u_{t−1}` entonces `y = z` y `y + z <= 1` ⇒
`y = z = 0`; si `u_t − u_{t−1} = 1` ⇒ `y = 1, z = 0`; si `= −1` ⇒ `y = 0, z = 1`. Por lo tanto `y_t = 1 ⇔` transición
OFF→ON real y `z_t = 1 ⇔` ON→OFF real. El auditor lo verifica además de forma explícita (`evento_ficticio`).

La indisponibilidad solo entra como `u <= a`: no genera curtailment ni costo (B01).

### M10 — dominio (se mantiene) `P_min·u <= p <= P_max·u`; con curva PWL, M14–M16 del 3B-P sin cambio (`Σδ = u`).

### M11 — rampas y transiciones (`p_{i,−1} = p_i^{−1}`, también en t = 0)

```
M11a:  p_{i,t} − p_{i,t−1} <= R_i^+ Δ · u_{i,t−1} + S_i^+ · y_{i,t}
M11b:  p_{i,t−1} − p_{i,t} <= R_i^− Δ · u_{i,t}   + S_i^− · z_{i,t}
```

**Exactitud por transición (prueba).** Con M10 (`u = 0 ⇒ p = 0`):

| Transición | M11a | M11b | Efecto |
|---|---|---|---|
| ON→ON (`y = z = 0`) | `p_t − p_{t−1} <= R⁺Δ` | `p_{t−1} − p_t <= R⁻Δ` | modulación limitada por la rampa normal |
| OFF→ON (`y = 1`) | `p_t <= S⁺` | `−p_t <= R⁻Δ` (trivial) | límite de **arranque** |
| ON→OFF (`z = 1`) | `−p_{t−1} <= R⁺Δ` (trivial) | `p_{t−1} <= S⁻` | límite de **parada** |
| OFF→OFF | `0 <= 0` | `0 <= 0` | — |

Ningún coeficiente es un Big-M: `R⁺Δ`, `R⁻Δ`, `S⁺`, `S⁻` son parámetros físicos declarados (o la derivación
conservadora D-3C1-02). La rampa de operación normal y los límites de arranque/parada son símbolos distintos.

**Coherencia con `P_min`** (especificación v1.0 §7.1). Sea `P_on_min = max(P_min, P_0 de la curva)`. Si
`S⁺ < P_on_min` el arranque exige más de un intervalo (multietapa/M20): **no representable** ⇒ `y ≡ 0` (restricción
`M11rep_y`) con aviso `partida_nao_representavel_bloqueada`; análogamente `S⁻ < P_on_min` ⇒ `z ≡ 0`
(`parada_nao_representavel_bloqueada`). Un compromiso parcial que **fije** una de esas transiciones es bloqueante
(`transicao_fixada_nao_representavel`). Si la transición es necesaria para la factibilidad, el problema es
**inviable** (no se relaja nada).

### M12 — tiempos mínimos ON/OFF

`U_i = ⌈T_i^{on}/Δ⌉`, `D_i = ⌈T_i^{off}/Δ⌉` (exactos con `Fraction`; redondeo hacia arriba **conservador** y
registrado — aviso `permanencia_arredondada_para_cima`; nunca hacia abajo). Para todo t:

```
Σ_{j=max(0,t−U_i+1)}^{t} y_{i,j} <= u_{i,t}          (M12on)
Σ_{j=max(0,t−D_i+1)}^{t} z_{i,j} <= 1 − u_{i,t}      (M12off)
u_{i,t} = u_i^{−1}   para t < min(r_i, N),   r_i = ⌈o_i / Δ⌉     (M12ini: obligación heredada)
```

`U = 0` o `D = 0` ⇒ suma vacía, sin restricción (solo si `T = 0` fue **declarado**).

**Política terminal explícita** (`PoliticaPermanenciaTerminal.tipo`, sin valor por defecto):

* `cumprir_na_janela` — `y_{i,t} = 0` si `t + U_i > N`; `z_{i,t} = 0` si `t + D_i > N` (`M12term_*`). Toda transición
  **nueva** completa su permanencia dentro de la ventana (garantía completa); las obligaciones heredadas que exceden la
  ventana se transportan.
* `obrigacao_residual_vinculante` — se permiten transiciones cerca del final; la parte que excede la ventana se
  exporta como **obligación residual vinculante** de la ventana siguiente (`memoria_terminal`,
  `obrigacoes_residuais_s`, `garantia_permanencia = "residual_vinculante"`). **No se declara garantía completa.**

El optimizador **no** puede eludir permanencias arrancando/apagando al final: en `cumprir_na_janela` esas
transiciones están prohibidas; en `obrigacao_residual_vinculante` las restricciones M12 en ventana siguen vigentes
para los intervalos presentes y el remanente se impone desde `t = 0` en la ventana siguiente (M12ini; Caso J).

## 4. Objetivo

```
J = J_3B-P (curtailment, throughput, ENS, combustível h·q) 
    + Σ_{i∈PEMFC} c_H · Σ_t (m_i^{SU} y_{i,t} + m_i^{SD} z_{i,t})      [si 'combustivel_h2' y la PEMFC transita; B05]
    + Σ_i Σ_t (C_i^{SU} y_{i,t} + C_i^{SD} z_{i,t})                    [solo con el término 'eventos'; R$/evento, SIN h]
```

Cada término exige **todos** sus coeficientes con procedencia; coeficiente declarado sin término ⇒ `coeficiente_sem_termo`.
Sin el término `eventos`, las transiciones siguen sujetas a M09–M12 pero ningún costo no declarado entra al objetivo
(test `test_caso_a_sem_termo_eventos_transicoes_restritas_sem_custo`). El costo de evento no depende de Δ (test
`test_caso_a_custo_de_evento_nao_e_multiplicado_por_h`, Δ = 1, 15, 60 min). Costos **planificados** (objetivo) y
**incurridos** (`ponte.compromisso.contabilidade_realizada_3c1`, desde las transiciones aplicadas; A-02) están separados; el valor
futuro sigue sin implementar (3C-0: nunca contabilizado como costo).

Linealidad: todas las restricciones y el objetivo tienen grado ≤ 1 y no hay SOS (test
`test_modelo_sem_variaveis_de_folga_linear_e_sem_sos`); no hay variables de holgura (conjunto de variables exacto).

## 5. Memoria operativa y continuidad (semántica temporal)

Memoria por unidad en la frontera k: `u`, `p`, tiempo en el estado vigente `d` [s] y obligación residual `o` [s].

* Declarada (`MemoriaCommitmentUnidade`): obligatoria cuando el `T` del estado vigente es > 0; con procedencia.
  `o` debe ser **igual** a `⌈max(0, T_estado − d)⌉` (D-3C1-05; divergencia ⇒ `obrigacao_residual_inconsistente`).
* Al final de la ventana (`compromisso.memoria.memoria_apos`): si la última transición fue en el intervalo `j`,
  `d_N = (N − j)Δ`; si no hubo transición, `d_N = d_0 + NΔ` y la obligación heredada decrece `o_0 − NΔ`.
* En la ejecución (3C-0): `EstadoGeracao.tempo_no_estado_s` ya se transportaba y se sella en el `Checkpoint`; la
  obligación se **deriva** de él con los T declarados (`ponte.compromisso.memorias_do_estado`).

**Equivalencia ventana continua × ventanas consecutivas (prueba).** Arranque en el intervalo global j con U. Una
ventana continua fuerza `u = 1` en `j..j+U−1`. Partida en la frontera `k_0 > j`: `d = mΔ` con `m = k_0 − j`,
`o = ⌈max(0, T − mΔ)⌉` y `r = ⌈o/Δ⌉ = ⌈T/Δ − m⌉ = U − m` cuando es positivo (m entero): la ventana siguiente fuerza
exactamente `k_0..j+U−1`, como la ventana continua. Lo mismo vale para D.
Verificado: Caso J (`test_caso_j_*`) — ejecución continua = ejecución partida por checkpoint (estados idénticos, misma
cadena de hashes); la memoria transportada **admite exactamente** la continuación del plan continuo (auditor de la
ventana 2 la acepta) y **rechaza** una continuación que viola la obligación (`obrigacao_herdada_M12`).

No se implementa reoptimización recedente (3C-2): solo transporte y verificación de estados.

## 6. Disponibilidad, PEMFC y unidades físicas

* `u <= a`; obligación ON heredada con `a = 0` ⇒ error `obrigacao_ligado_com_indisponibilidade` (parada forzada
  sin envolvente de emergencia documentada no se modela, v1.0 §7.1); unidad ON con `a_0 = 0` exige parada
  representable con `p^{−1} <= S⁻` (si no, `parada_forcada_nao_representavel`).
* **PEMFC.** La variante instantánea (`instantanea_unidade_quente`) es una **abstracción matemática declarada**
  (aviso `pemfc_abstracao_instantanea` en todo resultado): no valida la partida física. Con `combustivel_h2` exige
  `m^SU`/`m^SD` declarados (B05). En la puente, contexto `operacional` + PEMFC + transición instantánea ⇒
  `pendente pemfc_partida_nao_representavel_D05`; la alternativa honesta es `transicoes_bloqueadas` (estado mantenido).
  La variante multimodo (M20) sigue `pendente`. La curva q(P) conserva las condiciones de B04 (solo
  `sintetica_exata`). No se infieren tiempos de arranque del V1.6.
* **Por unidad.** Cada `eq-…#k` tiene estado, memoria y commitment propios (Caso G). La proyección exige el estado
  **por unidad** (`CondicaoInicialUnidade`) para bloques con `quantity > 1`; nunca distribuye una potencia agregada.

## 7. Preflight (antes del solver)

`compromisso.preflight.preflight_3c1`: `validar_entrada_3c1` (base 3B-P, unidades por UID, parámetros, memoria,
política terminal, términos) + compromiso parcial estricto (`int` 0/1 o `None`; mismo criterio C-3B-01) + obligaciones
× disponibilidad + transiciones fijadas no representables. En la puente: `preflight_ems_v2(..., commitment_3c1=decl)`
(proyección 3C-1 con requisitos M09–M12 **bloqueantes**, `apto_para_otimizacao` solo con entrada 3C-1 aceptada).

## 8. Auditor independiente (`ems_v2/compromisso/auditor.py`)

Sin Pyomo, sin `reference`, **sin** `contrato.discretizar` (recalcula U, D, r, R·Δ, S con `decimal`; test de
coincidencia y test de sabotaje del constructor). Verifica: núcleo 3B-P **reimplementado** (M02 con la potencia de los
generadores, M03-v1.1, M04, M06–M08, M10, M16, KPIs, costos), M09 (integralidad u/y/z, transición, simultaneidad,
disponibilidad, eventos ficticios), M11a/b con `p^{−1}`, transiciones no representables, M12 en **dos formas
independientes** (sumas en ventana y longitud de corridas ON/OFF, incluida la corrida heredada y la terminal),
política terminal, compromiso parcial y costos (`eventos` sin h; combustible con masas de evento). Resultado rechazado
⇒ `rejeitado_auditoria` ⇒ `plano_de_resultado_3c1` lanza `plano_de_solucao_nao_aceita` (no llega como plan a 3C-0).
La integridad del testigo auxiliar 3B-P (z_b, δ, θ) se reutiliza sin cambios.

Tolerancias: las **mismas** provisionales D07 (binaria 1e-6; potencia 1e-5 kW + 1e-7·P_scale; costo 1e-4 R$ +
1e-7·|J|); corridas en intervalos enteros con tolerancia 0 (tras pasar la integralidad).

## 9. Decisiones y contradicciones (requieren conocimiento/aprobación)

| ID | Decisión / contradicción | Alternativa descartada |
|---|---|---|
| D-3C1-01 | Contrato **embrulho** con base 3B-P (sin tocar `contracts.py`) | Campos opcionales en `EspecGerador` (exigía modificar archivos 3A/3B-P protegidos por la guardia 3C-0) |
| D-3C1-02 | Sin S declarados: `S⁺ := R⁺Δ`, `S⁻ := R⁻Δ` (`rampa_convencional`, declarado) — ningún salto mayor que la rampa, ni desde/hacia cero | `S = P_max` (prohibido por la especificación) o S ilimitado |
| D-3C1-03 | Transición no representable ⇒ bloqueada (`y/z ≡ 0`) con aviso; fijada por el llamador ⇒ bloqueante | Ignorarla o aproximarla con Big-M |
| D-3C1-04 | `U, D = ⌈T/Δ⌉`; obligaciones en segundos `⌈·⌉` | Redondeo al más cercano/abajo |
| D-3C1-05 | Obligación declarada = derivada (`⌈max(0, T − d)⌉`) | Obligaciones externas arbitrarias (no auditables) |
| D-3C1-06 | Dos políticas terminales explícitas, sin defecto; residual = vinculante, nunca "garantía" | Truncar la permanencia al final de la ventana |
| D-3C1-07 | `eventos` en R$/evento sin h; SEEDS2 "Custo de partida" (R$) ≡ R$/evento por reinterpretación **registrada** | Multiplicar por h; costo cero implícito |
| D-3C1-08 | PEMFC instantánea solo como abstracción declarada; masas de evento obligatorias con combustible; `operacional` ⇒ D05 pendiente | Inferir 30 s/600 s del V1.6 |
| D-3C1-09 | "Rampa máxima" única del inventario ⇒ `R⁺ = R⁻` (interpretación registrada en la procedencia) | Inventar rampas asimétricas |
| D-3C1-10 | Ejecutor 3C-1 = dublê **algébrico** que rechaza transiciones contra la memoria, rampas y disponibilidad efectiva (fuente declarada por unidad, A-01) | Modelo físico (fuera de alcance) |
| **C-3C1-01** | Dos guardias de pisos anteriores impedían por construcción el 3C-1: (a) `test_so_o_subpacote_milp_importa_pyomo_ou_highspy` (lista nominal de 3 archivos que importan Pyomo) y (b) `test_v16_e_aplicacao_sem_alteracao_desde_a_base_auditada` (`git diff --stat` vacío sobre `ems_v2/milp`). **Ajuste mínimo:** (a) agrega nominalmente `milp/modelo_3c1.py` y `milp/solver_3c1.py` (la regla "solo `ems_v2/milp` importa Pyomo" se mantiene); (b) pasa a exigir que **todo archivo existente en la base esté sin modificar ni eliminar** (`--name-status`, sin renombres) y admite solo las **adiciones** nominales `ADICOES_3C1` en `ems_v2/milp`; además verifica archivos no rastreados (antes no lo hacía). V1.6, modelos, runtime, `seeds2`, aplicación y requirements siguen sin admitir ningún cambio | Modificar `modelo.py`/`solver.py` 3B-P (rompería la evidencia de no alteración) |
| **C-3C1-02** | Latente en 3C-0: la reinterpretación R$ ≡ R$/evento de `requisitos` produce un `Parametro` con cadena bruto→canónico que el verificador 3A no reconoce (no es conversión lineal) ⇒ `cadeia_transformacao_inconsistente` al primer uso real de `C_SU`. Resuelto **solo** en la proyección 3C-1 (`_par3c1`: la reinterpretación queda en `transformacoes`, sin cadena numérica); 3C-0 y 3A sin cambios | Agregar "R$→R$/evento" a `units.CONVERSOES` (cambiaría el núcleo 3A) |

## 9b. Correcciones de la auditoría independiente del PR #14 (base `540ac1b`)

Dictamen: arquitectura, M09–M12 y auditor aprobados estructuralmente; tres correcciones de integridad/contabilidad.
Las tres se **reprodujeron sobre `540ac1b` antes de corregir** (EVIDENCIA_3C1 §6). Formulación MILP, auditor,
contratos 3A/3B-P/3C-0 y V1.6 **sin cambios**; solo `ems_v2/ponte/compromisso.py`, una fixture y tests.

| ID | Defecto (antes) | Corrección | Después |
|---|---|---|---|
| A-01 | `ExecutorAlgebricoCommitment3C1` leía `entorno.get("<uid>\|disponibilidade")` y, **si no existía, omitía** la verificación: una consigna ON se ejecutaba sin saber si la unidad estaba disponible. Un valor fraccionario se clasificaba como inviabilidad física | Fuente **obligatoria y explícita por unidad** (`FonteDisponibilidadeExecucao`, validada en el constructor; sin defecto): `observada` (serie de la realización con el UID **exacto** de la unidad, valor ∈ {0,1}; la alineación la impone `executar`/`entorno_realizado` del 3C-0) o `estatica_declarada` (int 0/1 + procedencia + justificativa; una observación del mismo UID debe coincidir). Series de disponibilidad de UID que no es recurso de la entrada (p. ej. la del registro de un bloque `#k`) ⇒ rechazadas (sin herencia) | Ausente / inválida / contradictoria / de otro recurso ⇒ `falha = "dados"` (`erro_dados`); efectiva 0 con ON ⇒ `inexequivel`; nunca 1 por omisión; no se inventa telemetría |
| A-02 | El objetivo incluía c_H·(m_SU y + m_SD z) pero la contabilidad **realizada** (3C-0 `indicadores_e_custo`) solo conoce h·q: el H₂ de los eventos ejecutados no se conciliaba | `contabilidade_realizada_3c1(e3, plano, traj, real)`: reutiliza **sin cambios** la función 3C-0 (términos base + H₂ continuo) y agrega, desde las transiciones **efectivamente aplicadas** (estados consecutivos de la trayectoria), c_H·(m_SU·partidas + m_SD·paradas) al componente `combustivel_h2` y el componente `eventos` (C_SU/C_SD, R$/evento, sin h). Detalle por unidad (`DetalheH2Realizado`) e indicadores `H2_continuo_kg`, `H2_eventos_kg`, `partidas_aplicadas`, `paradas_aplicadas` | `C_H2_realizado = c_H·[Σ h·q + Σ (m_SU y_real + m_SD z_real)]`; ejecución parcial/interrumpida cuenta solo lo aplicado; sin doble conteo (continuo = 3C-0, eventos = extensión); `CustoRealizado` 3C-0 sellable en el registro; valor futuro separado |
| A-03 | `montar_entrada_3c1` convertía `decl.unidades` en diccionario **antes** de verificar: una duplicata contradictoria sobrescribía en silencio (la última ganaba) y un UID desconocido se ignoraba | `_condicoes_por_unidade` valida ANTES de indexar: duplicatas (incluso idénticas) ⇒ `condicao_unidade_duplicada` (ninguna se usa); UID que no es unidad generadora habilitada **de esta microrred** (otra microrred, recurso inexistente, otro índice `#k`, UID del registro de un bloque, batería…) ⇒ `condicao_unidade_uid_desconhecido`; procedencia, unidad y dominio de la potencia y del tiempo verificados. La declaración pasa a estar **vinculada** a `microrrede_uid` y `cenario_uid` (`declaracao_de_outra_microrrede`, `declaracao_de_outro_cenario`). Registro de una unidad con condición en el cenario **y** declaración: idénticas ⇒ aviso; distintas ⇒ `condicao_unidade_contradiz_cenario` | Ningún estado desaparece por sobrescritura; la **origen** de la condición usada queda en la procedencia de la potencia y de la memoria (`origem: DeclaracaoCommitment3C1.unidades[i]` o `condição do registro … no cenário`) |

Las hipótesis aceptadas provisionalmente por la auditoría (embrulho separado, redondeo conservador, obligación
residual vinculante, `S := R·Δ` declarado, PEMFC instantánea solo como abstracción analítica) se mantienen como
**hipótesis de ensayo**, con sus avisos y bloqueos.

## 10. Fuera de alcance (no implementado)

MPC recedente (M23) y reoptimización; planificador de largo plazo y valor futuro; multimodo PEMFC (M20); potencias
de extremo (M11-EXT); auxiliares de evento (M05, W^SU/W^SD); costo térmico M19; red/tarifas; selector de motor;
integración con V1.6/UI; migraciones; ejecutor físico.

## 11. Reproducir

```bash
pip install -r requirements.txt -r requirements-ems_v2.txt pytest
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ems_v2 -q                 # sin Pyomo: los tests de solver se saltan
PYTHONDONTWRITEBYTECODE=1 python -m ems_v2.milp.evidencia_3c1 docs/ems_v2/EVIDENCIA_3C1_EJECUCION.md 5
```
