# Transición 3C-3 → 3C-4 (entregable N)

3C-4 (planificador jerárquico y **valor futuro**) **no está autorizado**; nada de lo siguiente se implementó en 3C-3.

| Piso | Responsabilidad | No es responsabilidad |
|---|---|---|
| **3C-3 (este)** | Interconexión: PCC, tarifas, intercambio programado × realizado, ajuste local declarado, liquidación, MPC conectado | Valor de largo plazo de la energía almacenada / commitment |
| **3C-4** | Planificador de largo plazo (12–24 h o más) y valor futuro / referencia terminal para el MPC; separar el valor de **reoptimizar** del valor de **anticipar** | Recurso de equilibrio de corto plazo (ya en 3C-3) |

## 1. Interfaces y datos que el planificador jerárquico necesitará (ya disponibles)

| Necesidad | Disponible en 3C-3 | Dónde |
|---|---|---|
| Precios futuros causales (decisión) con revisiones | `PerfilTarifario` + `selecionar_perfil_causal` | `rede/contrato.py` |
| Separación precio de decisión × liquidación | `NATUREZAS_PRECO`, `PoliticaAjustePCC` | `rede/contrato.py`, `rede/execucao.py` |
| Límites de intercambio por intervalo | `EspecPCC.limite_*` (series sobre la misión) | `rede/contrato.py` |
| Energía final, obligaciones pendientes, costo realizado sin valor futuro | `RegistroMissaoMPC` + `RegistroMissaoRede3C3` | `mpc/registro.py`, `rede/mpc.py` |
| Desvíos programado × realizado (calibración de incertidumbre) | `DesvioIntercambio`, totales `E_desvio_±` | `rede/execucao.py` |
| Comparación con energía final diferente | `comparar_missoes_3c3` (`comparavel_para_superioridade`) | `rede/comparadores.py` |
| Horizonte de planificación reservado | `DefinicaoTemporal.horizonte_planejamento_min` (3C-0, `pendente`) | `ponte/cenario.py` |
| Punto de inserción del término terminal | `PoliticaTerminal` (3A, solo `nenhuma`), `AvaliacaoValorFuturo` `nao_implementado_3C0` | `contracts.py`, `ponte/registro.py` |
| Punto de extensión del MPC | métodos `_montar_entrada_janela`, `_contabilidade`, … | `mpc/orquestrador.py` |

## 2. Trabajo propuesto (sujeto a autorización)

1. Función de valor/referencia terminal declarada (unidades R$/kWh o R$, cota, sensibilidad) producida por un
   planificador que use las mismas tarifas causales; nunca contabilizada como costo realizado (invariante 3C-0).
2. Repetir la comparación open-loop × MPC (§13) con condiciones terminales equivalentes y con valor futuro, para
   separar reoptimización de anticipación.
3. Decisiones pendientes: D07 (tolerancias), B3C3-01/02 (parámetros y tarifas reales), B3C3-04 (curtailment como
   acción de equilibrio), estimador de estado (B3C2-02).

## 3. Riesgos heredados

- Miopía del horizonte corto (banco drenado; obligaciones al final) — sin 3C-4 toda comparación económica muestra la
  energía final.
- La planta de ensayo mide su propio intercambio; no hay medición real (B3C3-05).
- Tarifas sintéticas: ningún resultado económico se extrapola a una factura real.
