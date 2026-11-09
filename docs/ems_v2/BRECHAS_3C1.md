# Piso 3C-1 — Informe de brechas (entregable G)

Lo que **todavía impide** aplicar el commitment dinámico a microrredes reales del SEEDS2. Verificado sobre una
microrred real del catálogo (`po::test_microrrede_real_bloqueada_no_3c1_com_explicacao`, solo lectura: el banco queda
byte a byte igual): la matriz con perfil 3C-1 marca `rampa`, `t_on_min`, `t_off_min` y `C_SD` como
`parametro_obrigatorio_ausente` (bloqueantes) y la proyección no construye entrada. Las brechas del 3C-0
(`BRECHAS_3C0.md`: η, P en barra, autodescarga, P_min/curva PEMFC, previsiones) siguen vigentes.

## 1. Parámetros faltantes en el inventario/escenario (no se infieren)

| # | Brecha | Afecta | Estado en el SEEDS2 (Piso 1) | Código que la expone |
|---|---|---|---|---|
| U1 | Rampa R⁺/R⁻ [kW/min] | M11 | Térmica: `ramp_kW_min` **opcional** ("vacío = sin límite" en la UI); PEMFC: inexistente | `parametro_obrigatorio_ausente` (`rampa`) — vacío **no** es "sin límite" |
| U2 | Rampa asimétrica | M11 | Un único campo "Rampa máxima" ⇒ R⁺ = R⁻ por interpretación registrada (D-3C1-09) | nota en la procedencia |
| U3 | T_on, T_off [min] | M12 | Inexistentes | `parametro_obrigatorio_ausente` (`t_on_min`, `t_off_min`) |
| U4 | S⁺, S⁻ (límites de arranque/parada) [kW] | M11 | Inexistentes ⇒ solo `rampa_convencional` (D-3C1-02) | `limites_transicao` declarado por política |
| U5 | Costo de parada C_SD [R$/evento] | M21 | Inexistente (solo "Custo de partida" térmico, en R$) | `parametro_obrigatorio_ausente` (`C_SD`) con término `eventos` |
| U6 | Masas de H₂ por evento m^SU/m^SD [kg] | B05/M17 | Inexistentes | `parametro_ausente` cuando PEMFC transita con `combustivel_h2` |
| U7 | Parámetros de arranque PEMFC (duraciones, etapas) | M20/B05 | Inexistentes (decisión D05 pendiente) | `pemfc_partida_nao_representavel_D05` (pendiente) en contexto operacional |
| U8 | Estado inicial POR UNIDAD (bloques `quantity > 1`) | M09–M12 | El escenario solo tiene `units_on` del registro | `estado_por_unidade_nao_declarado` |
| U9 | Tiempo en el estado vigente (memoria) | M12 | El escenario no lo registra (el lector deja `tempo_no_estado_s = None`) | `memoria_ausente` |
| U10 | Procedencia por valor (documento de origen) | todos | `declarado_seeds2` (rastreable, no conferido) | — |

## 2. Restricciones no soportadas (bloqueadas o declaradas no modeladas)

| # | Fenómeno | Tratamiento 3C-1 |
|---|---|---|
| N1 | Arranque/parada en más de un intervalo (S < P_min, PEMFC fría, rampas lentas) | Transición **bloqueada** con aviso; fijarla ⇒ bloqueante; multimodo M20 no habilitado |
| N2 | Potencias de extremo (M11-EXT): seguimiento continuo dentro del intervalo | No modelado (M11 restringe consignas de intervalo; aproximación declarada en `familias_nao_modeladas`) |
| N3 | Energía eléctrica de eventos W^SU/W^SD y auxiliares (M05) | No modelado (`auxiliares_evento_M05`) |
| N4 | Parada forzada por indisponibilidad repentina | Error explícito (`obrigacao_ligado_com_indisponibilidade`, `parada_forcada_nao_representavel`); sin envolvente de emergencia |
| N5 | Obligaciones externas distintas de la permanencia mínima | No admitidas (D-3C1-05: obligación = derivada) |
| N6 | Costo térmico CVU (M19) | Futuro; un caso térmico solo tiene costo de eventos |
| N7 | Disponibilidad fraccionaria (derating) de generadores | `pendente` (heredado de 3A) |

## 3. Contratos / integración

| # | Brecha | Estado |
|---|---|---|
| K1 | Persistencia de la memoria de commitment en el banco de la microrred | No implementada (memoria en `EstadoGeracao` + checkpoints sellados de la puente) |
| K2 | Lectura de T_on/T_off/rampas/S desde la UI del Piso 1 | Prohibido en esta misión (sin migraciones ni UI) |
| K3 | Reinterpretación R$ ≡ R$/evento no verificable por la cadena 3A (C-3C1-02) | Resuelto solo en la proyección 3C-1; recomendación: decidir si `units` debe reconocer equivalencias semánticas declaradas |
| K4 | Ejecutor físico con memoria interna (arranque/parada) | Solo dublê algébrico (`ExecutorAlgebricoCommitment3C1`) |
| K7 | Telemetría de disponibilidad de generadores (A-01) | El SEEDS2 no registra observaciones de disponibilidad por unidad: una ejecución real solo puede usar `estatica_declarada` (condición del escenario con procedencia) o quedará en `erro_dados` con `observada`; no se inventa telemetría |
| K8 | Persistencia de la contabilidad 3C-1 (A-02) | `ContabilidadeRealizada3C1.custo` es un `CustoRealizado` 3C-0 sellable en el registro JSON; el detalle por unidad (`DetalheH2Realizado`) no tiene campo propio en `RegistroExecucaoEMS`: solo los agregados `H2_continuo_kg`, `H2_eventos_kg`, `partidas_aplicadas` y `paradas_aplicadas` van a `indicadores` |
| K5 | Validación en Windows | No ejecutada |
| K6 | Campaña de tiempos (p95/p99) | Solo mediciones indicativas (EVIDENCIA_3C1); sin carácter estadístico |
