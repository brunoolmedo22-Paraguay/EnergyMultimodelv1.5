# Transición 3C-0 → 3C-1 (entregable G)

3C-1 (commitment dinámico, M09–M12) **no está autorizado**; este documento enumera lo que queda preparado y lo que
3C-1 deberá construir. Nada de lo siguiente fue implementado en 3C-0.

## 1. Interfaces y estados preparados

| Necesidad de 3C-1 | Preparado en 3C-0 | Dónde |
|---|---|---|
| Commitment **por unidad** | Expansión determinista `eq-…#k` para generadores con `quantidade > 1`; estado por unidad nunca inventado (`estado_por_unidade_nao_declarado`) | `inventario.recursos_ems`, `projecao._estado_gerador` |
| Arranques y paradas (u_{t} ≠ u_{t−1}) | Consigna `u` por intervalo en el plan (N valores, binaria verificada) y estado discreto `ligado` en cada frontera; el ejecutor detecta el cambio de estado | `execucao.PlanoDespacho`, `EstadoGeracao` |
| Rampas (M11a/M11b) | `EstadoGeracao.potencia_kW` en la frontera k (= `p_{t−1}` de la ventana siguiente); requisito `rampa` (kW/min) con clave `ramp_kW_min`, **ausente ≠ ilimitada** | `execucao`, `requisitos` |
| Tiempos mínimos ON/OFF (M12) | Memoria operativa `tempo_no_estado_s` transportada por el ejecutor (acumula si el estado se mantiene, reinicia si cambia; `None` = no rastreada); condición inicial `CondicaoInicialDispositivo.tempo_no_estado_s`; requisitos `t_on_min`, `t_off_min` | `execucao.ExecutorAlgebricoReferencia`, `cenario` |
| Costos de evento | Requisitos `C_SU` (`startup_cost_rs`, R$ ≡ R$/evento) y `C_SD` (`shutdown_cost_rs`) | `requisitos` |
| Arranque PEMFC (D05) | Requisito `partida_pemfc` (sin clave: decisión pendiente); estado `em_partida` bloqueado como no representable | `requisitos`, `projecao` |
| Estados iniciales y transporte entre ventanas | `EstadoMicrorrede` con índice **global** de frontera e instante UTC; `PlanoDespacho.indice_fronteira_inicial`; `estado_inicial_de_entrada(..., indice_fronteira, memoria)` | `execucao` |
| Checkpoints / reanudación | `Checkpoint` sellado y encadenado; `retomar` exige mismo plan, cursor, estado, ejecución y ejecutor | `execucao` |
| Condiciones terminales | Estado en la frontera N del plan (`estados_planejados`, N+1 valores) y `AvaliacaoValorFuturo` (no implementado, nunca costo) | `execucao`, `registro` |
| Trazabilidad | `RegistroExecucaoEMS` con hashes de entrada, matriz, preflight, previsión, realización y plan | `registro` |

## 2. Lo que 3C-1 deberá hacer (propuesta, sujeta a autorización)

1. Extender `EstadoGerador` (3A) o la proyección para llevar `tempo_no_estado_s` a la entrada canónica, con versión
   de formulación nueva (perfil controlado como en 3B-P: entradas 3A/3B-P sin cambio de hash).
2. Hacer obligatorios (bloqueantes) los requisitos `futuro_3C1` cuando la variante de commitment libre se declare.
3. Implementar M09 (transiciones y/z), M11 (rampas con `p_{-1}` del estado) y M12 (permanencias con memoria) en el
   MILP y en el auditor independiente (sin Pyomo), con casos analíticos A07/B05A.
4. Reemplazar `preflight_3bp` (compromiso fijo constante) por la verificación del compromiso libre/parcial.
5. Mantener: sin MPC (3C-2), sin valor futuro (3C-4), sin integración con la UI.

## 3. Riesgos que 3C-1 hereda

- Datos de permanencias/rampas inexistentes en el inventario real (brechas D6, D9): sin ellos 3C-1 solo correrá en
  ensayo.
- Tolerancias provisionales (D07) y semántica temporal de rampas en la frontera (M11-EXT) a confirmar.
- La excepción C-3C0-01 fue aceptada condicionalmente (auditoría PR #13): cualquier uso del lector en 3C-1 debe
  preservar sus condiciones (solo lectura, identidad UID/incarnación/revisión, sin excepciones genéricas).
- Para 3C-2 (no para 3C-1): el modo `incremental_online` de `Realizacao` (H-04) es el punto de partida del lazo
  cerrado; la brecha K6 enumera lo que falta.
- El preflight exige `finalidade="otimizacao"` para autorizar el solver (H-02); 3C-1 deberá sustituir
  `preflight_3bp` por la verificación del commitment libre dentro de esa misma rama.
