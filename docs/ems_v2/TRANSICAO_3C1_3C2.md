# Transición 3C-1 → 3C-2 (entregable H)

3C-2 (MPC recedente, M23) **no está autorizado**; nada de lo siguiente fue implementado en 3C-1.

## 1. Contratos preparados por 3C-1

| Necesidad del MPC | Preparado | Dónde |
|---|---|---|
| Resolver una ventana con commitment libre/parcial | `resolver_3c1(entrada_3c1, configuracao, compromisso_parcial)` | `ems_v2/milp/solver_3c1.py` |
| Memoria al final de la ventana PLANIFICADA | `ResultadoResolucao3C1.memoria_terminal`, `obrigacoes_residuais_s`, `garantia_permanencia` | `milp/resultado_3c1.py`, `compromisso/memoria.py` |
| Memoria EJECUTADA en cualquier frontera | `EstadoGeracao.tempo_no_estado_s` (sellado en `Checkpoint`) + `memorias_do_estado` (obligación derivada) | `ponte/execucao.py`, `ponte/compromisso.py` |
| Construir la ventana siguiente desde el estado | `entrada_de_continuacao(e3_siguiente, estado, procedencia=…)` (instante, microrred y UIDs verificados) | `ponte/compromisso.py` |
| Aplicar solo m de N intervalos (ρ = mΔ) | `executar(..., intervalos=m)` + `retomar` (3C-0) con `ExecutorAlgebricoCommitment3C1` | `ponte/execucao.py` |
| Obligaciones que cruzan ventanas | Política `obrigacao_residual_vinculante` + `M12ini` en la ventana siguiente (Caso J) | `milp/modelo_3c1.py` |
| Fijar decisiones ya comprometidas (no anticipatividad) | `compromisso_parcial` (0/1/None por intervalo) | `compromisso/preflight.py` |
| Costos planificados × incurridos | `PlanoCommitment3C1.custo_eventos_planejado_R` × `custo_eventos_realizado` | `ponte/compromisso.py` |
| Observación online | `Realizacao.modo = "incremental_online"` + barrera `observado_ate_utc` (3C-0, H-04/C-02) | `ponte/cenario.py`, `ponte/execucao.py` |

## 2. Trabajo necesario para 3C-2 (propuesta, sujeta a autorización)

1. Bucle recedente: para k = 0, m, 2m…: previsión emitida en τ_k → entrada de la ventana [τ_k, τ_k + NΔ) con
   `entrada_de_continuacao` → `resolver_3c1` → plan → aplicar m intervalos con la realización observada → checkpoint.
2. Previsión re-emitida por ventana y registro *append-only* de observaciones (brecha K6 del 3C-0).
3. Política para la ventana final de la misión (extensión de previsiones vs. prohibición de transiciones; hoy
   `cumprir_na_janela` es la única garantía completa).
4. Registro de la cadena de ventanas (registro 3C-0 por ventana + índice de la misión) y métricas de miopía.
5. Decidir tolerancias definitivas (D07) y tiempo límite por ventana (campaña p95/p99).

## 3. Límites y riesgos heredados

- Sin parámetros reales de rampas/permanencias (BRECHAS_3C1 U1–U9) el MPC solo correrá en ensayo.
- La abstracción instantánea no valida PEMFC; el multimodo (M20) sigue pendiente (D05).
- La memoria transportada por la ejecución es la del dublê algébrico; un ejecutor físico deberá exponer su memoria
  interna (especificación v1.0 §18: `_simulate_states` reinicia la PEMFC en cada simulación).
- La miopía del horizonte (U/D > N) se advierte (`permanencia_maior_que_janela`) pero no se corrige: requiere el
  planificador de largo plazo (3C-4).
