# Piso 3C-0 — Informe de brechas (entregable F)

Elementos que **todavía impiden ejecutar físicamente el EMS V2** sobre una microrred real del SEEDS2. Verificado:
la microrred de prueba equivalente al V1.6 es leída por dispositivo y `montar_entrada` la **bloquea** en contexto
`operacional` con los códigos listados (test `test_microrrede_real_bloqueada_com_explicacao`).

## 1. Datos (faltan en el inventario/escenario; no se infieren)

| # | Brecha | Afecta | Código que la expone | Camino propuesto |
|---|---|---|---|---|
| D1 | η de carga/descarga por banco | M07 | `parametro_obrigatorio_ausente` (`eta_c`, `eta_d`) | Campo en el inventario con procedencia, o método de identificación aprobado |
| D2 | Potencias máximas de carga/descarga **en la barra** | M06 | `parametro_obrigatorio_ausente` (`Pc_max`, `Pd_max`, pendente) | Declarar en la barra o aprobar conversión terminal → barra (BND-BESS) |
| D3 | Hipótesis de autodescarga | M07 | `hipotese_autodescarga` | Declaración explícita (α = 1 o λ) |
| D4 | Límites de SOC solo sugeridos (20/80 %) | M08 | `valor_sugerido_nao_confirmado` | Confirmar origen fabricante/instalación |
| D5 | PEMFC: P_min, curva q(P_net) certificada | M10, M14–M16 | `P_min`, `curva_h2` (pendente, B04) | Certificación estática de la curva (3D) |
| D6 | Permanencias, rampas PEMFC, costos de parada, parámetros de arranque | M09–M12 | `necessario_3C1` (aviso hoy) | Declaración en el inventario antes de 3C-1 (D05) |
| D7 | Procedencia por parámetro (documento de origen) | todos | `declarado_seeds2` (rastreable, no conferido) | Campo de procedencia por valor en el Piso 1 |
| D8 | Demanda sin UID de clase ni criticidad | M02, M04 | `classes_demanda_nao_declaradas`, `demanda_sem_uid_e_criticidade` | Clases de demanda en el escenario (D01) |
| D9 | Estado inicial por unidad (bloques con `quantity > 1`) | EST-INI, M09 | `estado_por_unidade_nao_declarado` | Inicialización por unidad en el escenario |
| D10 | Costos económicos del objetivo (curtailment, throughput, H₂, ENS) | M21 | `parametro_obrigatorio_ausente` cuando el término se declara | Decisión del responsable + procedencia |
| D11 | Instante de las condiciones iniciales | EST-INI | `instante_condicoes_utc = None` en escenarios reales | Vincular a la misión con fuso declarado |

## 2. Contratos

| # | Brecha | Estado |
|---|---|---|
| K1 | Semántica de las previsiones del Piso 2B (media de intervalo × muestra instantánea) | `semantica_previsao_nao_declarada` (pendente); decisión del responsable (riesgo 3A §6.2) |
| K2 | Instante de emisión de la previsión | Solo `created_at`; causalidad no verificable ⇒ aviso |
| K3 | Remuestreo/alineación a Δ del EMS V2 | No hay remuestreo (3A); series del 2B con otra resolución ⇒ pendente |
| K4 | Disponibilidad variable en el tiempo | Solo estática por escenario (D-3C0-05) |
| K5 | Políticas terminal/servicio/objetivo | Siguen como declaración explícita (D01/D02 abiertas) |
| K6 | Operación online del MPC (3C-2): log de observaciones *append-only* con instante de recepción, datos tardíos/revisados, previsión reemitida por ventana, estimación de estado, política de huecos | **Bloqueante para 3C-2.** Preparado en 3C-0 (H-04): `Realizacao.modo = "incremental_online"` + `observado_ate_utc`, cobertura solo hasta τ_k, valores futuros rechazados, ejecución que se detiene en τ_k y se reanuda desde checkpoint. Verificable: `test_h04_*` |

## 3. Modelos

| # | Brecha | Estado |
|---|---|---|
| M1 | Potencial renovable en la barra a partir del clima (modelos FV/eólico por arreglo/turbina) | No existe adaptador ⇒ `potencial_renovavel_sem_serie` |
| M2 | Ejecutor físico (`ExecutorPasso` de natureza `modelo_fisico`) | Solo el dublê algébrico; ningún modelo de planta conectado |
| M3 | PEMFC: modelo real con estados de arranque/multimodo | M13/M20 no soportados |
| M4 | Batería: frontera terminal → barra (convertidor) | BND-BESS no implementado |

## 4. Optimización

| # | Brecha | Fase |
|---|---|---|
| O1 | Commitment libre con transiciones, rampas y permanencias (M09–M12) | 3C-1 |
| O2 | MPC recedente (M23), reoptimización por ventanas | 3C-2 |
| O3 | Red/tarifas/intercambio (topología conectada) | 3C-3 |
| O4 | Planificación jerárquica y función de valor futuro por reoptimización paramétrica | 3C-4 |
| O5 | Costo térmico M19 y lexicográfico M22 | 3C |
| O6 | Tolerancias del auditor provisionales (D07) | Aprobación pendiente |

## 5. Integración

| # | Brecha | Estado |
|---|---|---|
| I1 | Selector de motor / UI / Centro de Operação | Prohibido en 3C-0 (test `test_aplicacao_nao_referencia_ems_v2`) |
| I2 | Persistencia del `RegistroExecucaoEMS` en el banco de la microrred y en el Archivo Científico | Solo archivo JSON inmutable (D-3C0-07) |
| I3 | Lectura de previsiones del 2B (blobs) para construir `ConjuntoPrevisao` | No implementado (depende de K1–K3, M1) |
| I4 | Excepción C-3C0-01 (lector `ems_v2 → seeds2`) | Aceptada condicionalmente (auditoría PR #13); condiciones verificadas por tests |
| I5 | Congelar las salidas numéricas del V1.6 antes de comparar motores | Obligación previa (decisión 3A) |
| I6 | Campañas de tiempo (p95/p99/máx por horizonte) | Instrumentación lista; sin campaña ejecutada |
