# Piso 3B-P — Formulación MILP efectivamente ejecutada (Pyomo + HiGHS)

**Estado:** prototipo MILP de **una ventana**, ejecutable solo por API y tests (`ems_v2.milp.solver.resolver`).
Sin MPC, sin integración con la interfaz, el Centro de Operação ni el runtime V1.6. Resultados **sintéticos y
algebraicos**: no constituyen validación física de equipos reales. Base: `main` `f6d009db169b60a84657f79a7006640e20470b82`.

## 1. Dependencias e interfaz del solver

| Ítem | Decisión verificada |
|---|---|
| Versiones | `pyomo==6.10.1` (BSD-3-Clause, 2026-06-04) y `highspy==1.15.1` (MIT, 2026-07-02; HiGHS 1.15.1, githash `04024d7`), con wheels cp313 |
| Archivo | `requirements-ems_v2.txt`, **separado** de `requirements.txt` (V1.6 intacto). Instalación: `pip install -r requirements.txt -r requirements-ems_v2.txt` |
| Entorno limpio | venv nuevo con Python 3.13.18: la combinación conserva `numpy==2.2.6`, `pandas==2.2.3`, `scipy==1.15.3` y `streamlit==1.66.1` (highspy solo exige `numpy` sin fijar versión) |
| Smoke MILP | 1 variable binaria + 1 continua: `highs` y `appsi_highs` dan `x=2, y=1, obj=11`. Un problema inviable devuelve `provenInfeasible/noSolution` |
| Capacidades reales | La interfaz **rechaza SOS** (`NotImplementedError`) y **expresiones no lineales** (`IncompatibleModelError`). Un problema no acotado devuelve `unbounded` con `solution_status=feasible`, que **nunca** se convierte en despacho. No se asume MIQP ni MINLP |
| Interfaz elegida | **`pyomo.contrib.solver` "highs"**: es la API actual de Pyomo. Separa `termination_condition` de `solution_status`, admite `load_solutions=False` y `raise_exception_on_nonoptimal_result=False`, y expone `incumbent_objective`, `objective_bound`, `rel_gap`/`abs_gap`/`time_limit`/`threads`. `appsi_highs` también funciona, pero es la interfaz experimental anterior |
| Detalle | La fábrica `highs` solo se registra tras `import pyomo.environ`; `ems_v2.milp` lo hace explícitamente |

## 2. Perfil de capacidades (obstáculos A y B)

- **Obstáculo A, contrato.** El perfil se elige por la `versao_formulacao` **declarada en la entrada**.
  - `"v1.1-3A"` conserva exactamente el comportamiento y los códigos de 3A; A05-OPT 3A sigue `pendente`.
  - `"v1.1-3B-P"` habilita los términos implementados y probados: `curtailment_operacional`, `throughput_bess`, `energia_nao_suprida` y `combustivel_h2` (este último solo en variante `instantanea`, parte operacional h·q).
  - Cada término exige **todos** sus coeficientes declarados; no hay costo cero implícito.
  - Servicio `degradado` exige un criterio ENS explícito (`criterio_ens_ausente`).
  - Un coeficiente declarado sin su término es un error.
  - El MILP **rechaza** las entradas 3A (`formulacao_nao_3bp`): no ganan capacidades implícitamente.
- **Extensión retrocompatible del esquema v1:** se añaden dos campos opcionales, `ClasseDemanda.custo_energia_nao_suprida` (V_ℓ, R$/kWh) y `EspecGerador.preco_h2` (c_H, R$/kg). Cuando son `None` se omiten del JSON canónico, así que toda entrada 3A conserva **el mismo texto y el mismo SHA-256** que en `main`. Un test fija los hashes medidos en `f6d009d`.
- **Obstáculo B, auditor.** `auditar(..., compromisso_fixo=programa)`, todavía **sin Pyomo**.
  - Sin programa, los generadores siguen como `nao_suportado`, igual que en 3A.
  - Con programa, verifica de forma independiente:
    - fidelidad e integralidad de `u`;
    - programa constante e igual al estado inicial;
    - dominio ON/OFF (M10);
    - caudal PWL (M15/M16, bisección propia);
    - contribución de `p` al balance M02;
    - costos de los cuatro términos y total. El total se compara con el objetivo del solver.
  - **Rampas (M11) y permanencias (M12) no se modelan ni se certifican.** Se declaran en `familias_nao_modeladas` de cada resultado.
- **Registro de capacidades.** `CAPACIDADES_3BP`, con estados `implementado_3BP`/`parcial_3BP`. El catálogo único recibe las columnas `status_3BP`/`codigo_3BP`; los estados 3A quedan como histórico. Un test impide que un símbolo futuro aparezca en una ecuación declarada implementada.

## 3. Modelo (una ventana; `T = {0..N−1}`, `K = {0..N}`, `h = Δ/60`)

| Bloque | Restricción ejecutada | Notas |
|---|---|---|
| M02 | `Σ P_R + Σ p + Σ (P_d − P_c) = Σ L − Σ_{autorizadas} ℓ + d` | Sin holguras libres. Un intervalo sin ninguna decisión y con balance ≠ 0 es inviable en la construcción, sin llamar al solver |
| M03-v1.1 | `P_R + C_oper = a·A_pot`; `P_R, C_oper ≥ 0` | `base_potencial` "utilizavel" exige `a = 1`. La indisponibilidad nunca entra en el costo |
| M04 | `0 ≤ ℓ ≤ χ·L` solo en clases interrumpibles con servicio degradado; `0 ≤ d ≤ D̄` solo con dispositivo | En servicio duro o carga crítica, ℓ no existe; un déficit es `inviavel` |
| M06 | `P_c ≤ a·P̄^c·z`, `P_d ≤ a·P̄^d·(1 − z)`, z binaria | Exclusividad MILP por banco |
| M07 | `e_{t+1} = α e_t + h(η^c P_c − P_d/η^d)` | α = 1 (hipótesis declarada) o `exp(−λh)` |
| M08 | `C s_min ≤ e_k ≤ C s_max`, `e_0 = e^0` | Cotas en las N+1 fronteras, sin recorte |
| M10 | `P_min u ≤ p ≤ P_max u`, u **fijada** | Programa constante = estado inicial; transiciones bloqueadas (`transicao_nao_modelada_3BP`) |
| M14–M16 | `Σ_s δ_s = u`; `θ_s ≤ δ_s`; `p = Σ[P_s δ_s + ΔP_s θ_s]`; `q = Σ[Q_s δ_s + ΔQ_s θ_s]` | Binaria por segmento consecutivo, sin SOS. Válido para curvas no convexas. OFF ⇒ p = q = 0. No hay segmento entre (0,0) y P_0. Solo curvas `sintetica_exata` (B04) |
| Objetivo (min, R$) | `h Σ_t [Σ c^curt C_oper + Σ c^thr (P_c + P_d) + Σ V ℓ + Σ c_H q]` | Solo los términos declarados. Sin términos se resuelve un problema de factibilidad con objetivo nulo (A05-FEAS) y se informa como tal |

Todas las restricciones y el objetivo son lineales: un test verifica `polynomial_degree() ≤ 1` y la ausencia de SOS.

## 4. API y resultado

`resolver(entrada, configuracao, compromisso_fixo)` produce un `ResultadoResolucao`. El orden del flujo es:

1. ambiente;
2. validación (contrato + configuración + pre-verificación 3B-P);
3. construcción;
4. HiGHS;
5. clasificación;
6. carga y extracción, solo si la clasificación admite despacho;
7. **auditoría independiente**;
8. estado final.

| Campo | Contenido |
|---|---|
| `classificacao` | `otimo` (convergencia **dentro de los gaps configurados**), `factivel_nao_otimo` (límite con incumbent), `sem_solucao`, `inviavel`, `inviavel_ou_ilimitado`, `ilimitado`, `erro`, `desconhecido`, `bloqueado_validacao`, `solver_indisponivel` |
| `terminacao` / `status_solucao` | Nombres crudos de `TerminationCondition` / `SolutionStatus` |
| `solucao_primal`, `objetivo`, `limite_dual`, `gap_abs`, `gap_rel`, `gap_highs` | Convención declarada (minimización): gap_abs = \|incumbent − cota\|; gap_rel = gap_abs/\|incumbent\|. Lo que no está disponible se registra como `None`, nunca como 0 |
| `tempos_s`, `tamanho` | Construcción, solver, HiGHS y total; número de variables, binarias libres y restricciones |
| `ambiente`, `configuracao`, `hash_entrada`, `hash_compromisso` | Versiones, configuración explícita (sin valores implícitos) e identidad de la entrada |
| `despacho`, `candidato`, `custos_modelo` | Por UID y por intervalo (incluye `z_b` y el segmento PWL activo). Las clases sin autorización tienen ℓ ≡ 0 por estructura |
| `auditoria`, `estado_despacho`, `aceito` | `aceito_otimo`, `aceito_factivel_nao_otimo`, `rejeitado_auditoria` o `sem_despacho`. **Ninguna solución rechazada por el auditor se acepta** |

Configuración explícita y obligatoria: `CONFIG_ANALITICA = (time_limit 60 s, 1 thread, rel_gap 0, abs_gap 0,
semente 0)`. Es configuración de software, no un parámetro físico.

## 5. Hipótesis, decisiones de software y límites (3B-P)

| ID | Hipótesis o límite | Efecto |
|---|---|---|
| H-3B-01 | Compromiso **fijo, constante e igual al estado inicial** | No hay arranques/paradas en la ventana; M09/M11/M12 no se modelan ni se certifican (se declara en cada resultado) |
| H-3B-02 | Combustible: solo h·q de la variante instantánea | m^SU/m^SD no existen en el contrato y las transiciones están bloqueadas, así que no hay doble conteo posible |
| H-3B-03 | Criterio ENS por término económico V_ℓ·ℓ (no lexicográfico) | En A08 cualquier V > 0 da el mismo despacho (no hay otro costo). La prioridad estricta (M22) sigue futura |
| H-3B-04 | Objetivo vacío = problema de factibilidad declarado | No se infiere optimalidad (A05-FEAS) |
| H-3B-05 | "Óptimo" = convergencia de HiGHS dentro de rel_gap/abs_gap configurados (0 en los casos analíticos) | La optimalidad es del **modelo reducido**, no de la planta |
| H-3B-06 | Tolerancias del auditor PROVISIONALES (D07), sin cambios | Absorben el ruido numérico (p. ej. A04: `P_c = 9,999999999999984`) |
| H-3B-07 | Límite de **tiempo** con incumbent no es determinista | Test: incumbent real por `mip_max_improving_sols=1` (determinista con 1 thread y semente 0) más límite de tiempo simulado en el adaptador; la evidencia registra un límite de tiempo real (N=48, 0,05 s) como observación |

**Fuera del alcance (no implementado):** MPC y realimentación, arranque caliente/frío, autómata multimodo, ModelLab
real, curva PEMFC real (B04), selector en la UI, Centro de Operação, migraciones, benchmark contra V1.6, terminal
físico, lexicográfico, rampas y permanencias.

## 6. Reproducir

```bash
pip install -r requirements.txt -r requirements-ems_v2.txt pytest
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ems_v2 -q        # sin Pyomo: los tests del solver se saltan explícitamente
PYTHONDONTWRITEBYTECODE=1 python -m ems_v2.milp.evidencia docs/ems_v2/EVIDENCIA_3BP.md
```
