# Piso 3C-0 — Matriz de parámetros (entregable C)

> Fuente de verdad: `ems_v2/ponte/requisitos.py` (`REQUISITOS`). La tabla se generó a partir de ese módulo y el
> test `test_matriz_documentada_lista_todos_os_simbolos` exige que cada símbolo esté aquí. La columna «Situación»
> resume la auditoría del inventario del Piso 1 (`seeds2/microgrid/config.py`, `derived.py`, `references.py`) y fue
> **verificada** con la microrred de prueba equivalente al V1.6 (`tests/seeds2_fixtures.py`) y con una segunda
> microrred con limites de SOC solo sugeridos (`tests/ems_v2/test_ems_v2_ponte_seeds2.py`).

## Clases (3C-0 §3.2)

| Nº | Clase (`ClassificacaoParametro.classe`) | Significado | ¿Bloquea? |
|---|---|---|---|
| 1 | `disponivel_verificavel` | Declarado con procedencia rastreable (revisión + ruta en el documento) | No |
| 2 | `derivavel` | Relación registrada (`derivacao`) a partir de valores declarados o catálogo de referencia | No |
| 3 | `faltante_necessario` | Ausente, o solo **sugerido** por el SEEDS2, y exigido | Sí (`erro`/`pendente`); requisitos `futuro_3C1` solo `aviso` |
| 4 | `opcional` | Ausente y no exigido por la configuración declarada (p. ej. término del objetivo inactivo) | No |
| 5 | `sintetico_ensaio` | Origen sintético | Solo en contexto `ensaio`; en `operacional` ⇒ `dado_sintetico_fora_de_ensaio` |

Reglas: nada ausente se sustituye; unidades se convierten solo por conversiones exactas declaradas (`ems_v2/units.py`)
con la cadena bruto → canónico preservada; unidad sin conversión ⇒ `unidade_incompativel` (bloquea). Los valores del
inventario SEEDS2 tienen procedencia `declarado_seeds2` (nuevo tipo aditivo): rastreables a la revisión, **sin**
documento de origen por parámetro (no son ficha técnica conferida).

Claves marcadas «(propuesta)» **no existen** en el inventario del Piso 1: son el lugar contractual donde el futuro
inventario debe declararlas; hoy solo aparecen en inventarios sintéticos de ensayo (`ems_v2/fixtures_3c0.py`).

## Matriz

| Símbolo | Dispositivos | Descripción | Naturaleza | Unidad canónica | Obligatoriedad | Ecuaciones | Claves aceptadas (orden) | Situación en una microrred SEEDS2 real | Bloqueo si falta |
|---|---|---|---|---|---|---|---|---|---|
| `C_b` | bateria | Capacidade energética utilizável do banco | fisico | kWh | obrigatorio | M06, M07, M08 | `energy_kWh`, `energy_kWh_derivada` (derivada), `energy_kWh_modelo` (derivada) | 2 — derivable (V·Q del datasheet o parametrización del modelo); 1 si `energy_kWh` declarado | `erro` · `parametro_obrigatorio_ausente` |
| `s_min` | bateria | Limite inferior de SOC (fração) | fisico | 1 | obrigatorio | M08 | `soc_min_pct` | 1 si origen fabricante/instalación/migrado; **3** si solo «sugerido» (20 %) | `erro` · `parametro_obrigatorio_ausente` |
| `s_max` | bateria | Limite superior de SOC (fração) | fisico | 1 | obrigatorio | M08 | `soc_max_pct` | Idem `s_min` (80 % sugerido) | `erro` · `parametro_obrigatorio_ausente` |
| `eta_c` | bateria | Eficiência de carga barramento → energia interna | fisico | 1 | obrigatorio | M07 | `eta_carga` (propuesta) | **3** — no existe en el inventario | `erro` · `parametro_obrigatorio_ausente` |
| `eta_d` | bateria | Eficiência de descarga energia interna → barramento | fisico | 1 | obrigatorio | M07 | `eta_descarga` (propuesta) | **3** — no existe en el inventario | `erro` · `parametro_obrigatorio_ausente` |
| `Pc_max` | bateria | Potência máxima de carga NO BARRAMENTO | fisico | kW | obrigatorio | M06 | `p_carga_barramento_kW` (propuesta) | **3** — solo potencia terminal C·E (frontera BND-BESS no aprobada) | `pendente` · `parametro_obrigatorio_ausente` |
| `Pd_max` | bateria | Potência máxima de descarga NO BARRAMENTO | fisico | kW | obrigatorio | M06 | `p_descarga_barramento_kW` (propuesta) | **3** — idem | `pendente` · `parametro_obrigatorio_ausente` |
| `hipotese_autodescarga` | bateria | Hipótese de autodescarga (α = 1 declarada ou λ) | declaracao | — | obrigatorio | M07 | `hipotese_autodescarga` (propuesta) | **3** — no existe | `erro` · `parametro_obrigatorio_ausente` |
| `c_thr` | bateria | Custo de throughput | economico | R$/kWh | condicional | M21-v1.1 | `custo_throughput` (propuesta) | 4 — opcional (término inactivo); 3 si el término se declara | `erro` solo con `termo:throughput_bess` |
| `modulo_ref` | pv_arranjo | Módulo FV (catálogo) — entrada do modelo físico | modelagem | — | obrigatorio | M03-v1.1 | `reference` | 1 (arreglo «módulo»); **3** arreglo «potencia declarada» | `erro` · `parametro_obrigatorio_ausente` |
| `Ns` | pv_arranjo | Módulos em série | contagem | — | obrigatorio | M03-v1.1 | `n_series` | 1 | `erro` · `parametro_obrigatorio_ausente` |
| `Np` | pv_arranjo | Strings em paralelo | contagem | — | obrigatorio | M03-v1.1 | `n_parallel` | 1 | `erro` · `parametro_obrigatorio_ausente` |
| `perdas_sujeira` | pv_arranjo | Perdas por sujeira (fração) | fisico | 1 | obrigatorio | M03-v1.1 | `soiling_pct` | 1 si declarado; **3** si 0 % por defecto no declarado | `erro` · `parametro_obrigatorio_ausente` |
| `c_curt` | pv_arranjo, eolica | Custo de curtailment operacional | economico | R$/kWh | condicional | M21-CURT | `custo_curtailment` (propuesta) | 4 / 3 si el término se declara (no existe) | `erro` solo con `termo:curtailment_operacional` |
| `turbina_ref` | eolica | Aerogerador (catálogo) — entrada do modelo físico | modelagem | — | obrigatorio | M03-v1.1 | `reference` | 1 | `erro` · `parametro_obrigatorio_ausente` |
| `n_turbinas` | eolica | Aerogeradores idênticos no registro | contagem | — | obrigatorio | M03-v1.1 | `count` | 1 | `erro` · `parametro_obrigatorio_ausente` |
| `perda_rede_generica` | eolica | Opção de perda genérica do modelo eólico | modelagem | — | obrigatorio | M03-v1.1 | `apply_grid_loss` | 1 (opción con valor por defecto del Piso 1) | `erro` · `parametro_obrigatorio_ausente` |
| `perfil_pemfc` | pemfc | Perfil/dispositivo PEMFC | modelagem | — | obrigatorio | M10, M13 | `reference` | 1 | `erro` · `parametro_obrigatorio_ausente` |
| `n_sistemas` | pemfc | Sistemas PEMFC idênticos no registro | contagem | — | obrigatorio | M10 | `quantity` | 1 | `erro` · `parametro_obrigatorio_ausente` |
| `P_max` | pemfc, termica | Potência máxima líquida no barramento (por unidade) | fisico | kW | obrigatorio | M10 | `p_max_liquida_unidade_kW` (derivada), `pmax_kW` | PEMFC: 2 (modelo dinámico de referencia, perfil aproximado). Térmica: 1 | `erro` · `parametro_obrigatorio_ausente` |
| `P_min` | pemfc, termica | Potência mínima técnica líquida (por unidade, quando ON) | fisico | kW | obrigatorio | M10 | `pmin_kW` | Térmica: 1. PEMFC: **3** (V1.6 lo identifica de series simuladas) | `erro` · `parametro_obrigatorio_ausente` |
| `curva_h2` | pemfc | Curva q(P_net) de H₂ suprido | fisico | kg/h | obrigatorio | M14, M15, M16 | — | **3** — B04 (curva real exige certificación estática) | `pendente` · `parametro_obrigatorio_ausente` |
| `c_H` | pemfc | Preço do hidrogênio | economico | R$/kg | condicional | M17 | `preco_h2` (propuesta) | 4 / 3 si el término se declara | `erro` solo con `termo:combustivel_h2` |
| `dinamica_termica` | termica | Dinâmica operacional (pequena unidade geradora) | modelagem | — | obrigatorio | M10 | `dynamic` | 1 (solo `local_generator` representable) | `erro` · `parametro_obrigatorio_ausente` |
| `CVU` | termica | Custo variável unitário | economico | R$/kWh | condicional | M19 | `cvu_rs_MWh` | 1 (R$/MWh → R$/kWh exacto); término M19 no soportado | `erro` solo con `termo:geracao_termica` |
| `rampa` | pemfc, termica | Rampa máxima | fisico | kW/min | futuro_3C1 | M11a, M11b | `ramp_kW_min` | Térmica: 1 si declarada, vacía = «sin límite declarado» (≠ ilimitada); PEMFC: **3** | `aviso` · `necessario_3C1` (bloqueará en 3C-1) |
| `t_on_min` | pemfc, termica | Tempo mínimo em operação | fisico | min | futuro_3C1 | M12 | `t_on_min` (propuesta) | **3** | `aviso` · `necessario_3C1` (bloqueará en 3C-1) |
| `t_off_min` | pemfc, termica | Tempo mínimo em repouso | fisico | min | futuro_3C1 | M12 | `t_off_min` (propuesta) | **3** | `aviso` · `necessario_3C1` (bloqueará en 3C-1) |
| `C_SU` | pemfc, termica | Custo de partida (por evento) | economico | R$/evento | futuro_3C1 | M21-v1.1 | `startup_cost_rs` | Térmica: 1 (R$ ≡ R$/evento); PEMFC: **3** | `aviso` · `necessario_3C1` (bloqueará en 3C-1) |
| `C_SD` | pemfc, termica | Custo de parada (por evento) | economico | R$/evento | futuro_3C1 | M21-v1.1 | `shutdown_cost_rs` (propuesta) | **3** | `aviso` · `necessario_3C1` (bloqueará en 3C-1) |
| `partida_pemfc` | pemfc | Parâmetros de partida (durações/estados intermediários) | fisico | s | futuro_3C1 | M20, B05 | — | **3** (D05) | `aviso` · `necessario_3C1` (bloqueará en 3C-1) |

## Requisitos que NO provienen del inventario (verificados por la proyección/preflight)

| Dato | Fuente prevista | Situación en SEEDS2 | Bloqueo |
|---|---|---|---|
| `e0` (energía inicial por banco) | Escenario: `soc0_pct` (% → fracción exacta) × `C_b` | Disponible si SOC declarado y `C_b` disponible | `soc_inicial_ausente`, `soc_inicial_fora_dos_limites` |
| Estado ON/OFF y potencia anterior | Escenario: `state`, `power_kW`, `units_on` | Declarables; **por unidad** no existen (bloques PEMFC con `quantity > 1`) | `estado_inicial_ausente`, `estado_por_unidade_nao_declarado`, `estado_em_partida_nao_representavel` |
| Disponibilidad `a` | Escenario (estática por registro `eq-…`; los arreglos heredan de la usina) | Disponible | `condicao_inicial_ausente` |
| Potencial renovable `A_pot` [kW barra] | Previsión por recurso (`SerieRecurso(uid, "potencia")`) | **No existe**: el Piso 2B guarda clima; convertirlo exige los modelos físicos | `potencial_renovavel_sem_serie` (pendente) |
| Demanda por clase + criticidad | Políticas declaradas + previsión | Demanda agregada sin UID ni criticidad | `classes_demanda_nao_declaradas`, `serie_demanda_ausente` |
| Semántica de series (media/instantánea) | `SerieTemporal.semantica` | **No declarada** en el Piso 2B | `semantica_previsao_nao_declarada` (pendente) |
| Topología | `installation.operation_mode` | Declarable; `conectada` no soportada | `topologia_nao_declarada` / `topologia_nao_suportada_3A` |
| Políticas (servicio, terminal, objetivo, variante de commitment) | Declaración explícita (D01/D02) | No existen en SEEDS2 | `variante_commitment_nao_declarada`, validaciones 3A |
