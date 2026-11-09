# Transición 3C-2 → 3C-3 y 3C-4 (entregable M)

3C-3 y 3C-4 **no están autorizados**; nada de lo siguiente fue implementado en 3C-2. Responsabilidades separadas:

| Piso | Responsabilidad | No es responsabilidad |
|---|---|---|
| **3C-2 (este)** | Lazo recedente M23 de UN MPC de corto plazo: reloj, K6, previsión por ventana, estado/memoria ejecutados, aceptación, registros encadenados, métricas, comparadores | Valor futuro, coordinación jerárquica, red/tarifas, planta física |
| **3C-3** | Topología conectada: red, tarifas e intercambio (brecha O3 del 3C-0); recurso de equilibrio que absorbe errores de previsión (B3C2-01) | Valor de largo plazo de los recursos |
| **3C-4** | Planificador jerárquico de largo plazo y **valor futuro** de batería/recursos (referencia/terminal valorada para el MPC; reoptimización paramétrica, sin tomar duales de MILP como precios sombra — 3C-0) | Recurso de equilibrio de corto plazo |
| **3D** | Integración con microrredes reales (inventario, previsiones 2B, persistencia en `MicrogridStore`), planta física (`ExecutorPasso` `modelo_fisico`), UI/selector | — |

## 1. Interfaces preparadas por 3C-2

| Necesidad | Preparado | Dónde |
|---|---|---|
| Horizonte de planificación (3C-4) | Campo reservado `DefinicaoTemporal.horizonte_planejamento_min` (3C-0) — sigue `pendente`; el MPC no lo usa | `ponte/cenario.py` |
| Referencia terminal/valor futuro (3C-4) | Política terminal 3A `nenhuma`; `AvaliacaoValorFuturo` `nao_implementado_3C0`; los registros MPC reportan energía final y obligaciones pendientes SIN valorarlas | `ponte/registro.py`, `mpc/registro.py` |
| Comparación con energía final distinta | `comparadores` reporta E_final y la diferencia (especificación §12) | `mpc/comparadores.py` |
| Recurso de equilibrio (3C-3) | Clase de falla `consigna_inexequivel` + C-3C2-01 delimitan exactamente qué errores no se absorben hoy | `mpc/contrato.py`, FORMULACAO_3C2 §9 |
| Previsiones reales (3D) | Protocolo `ProvedorPrevisao` + `validar_previsao_janela` (vínculo al instantáneo, causalidad, cobertura) | `mpc/previsao.py` |
| Telemetría real (3D) | `Observacao` + `LivroObservacoes` (recepción, secuencia, revisiones) | `mpc/observacoes.py` |
| Planta física (3D) | `EntornoPasso` (comando → recibo; confirmaciones/observaciones por entrega) | `mpc/entorno.py` |
| Persistencia/retomada | `PontoRetomada` sellado + `retomar_controlador` verificado | `mpc/persistencia.py` |

## 2. Trabajo necesario (propuesta, sujeta a autorización)

1. **3C-4:** función de valor/referencia terminal declarada (unidades, cota, sensibilidad) y coordinación planificador
   (12–24 h) × MPC; mantener separados costo realizado y valor futuro (invariante 3C-0).
2. **3C-3:** variables de red (importación/exportación, tarifas) en el MILP y en el ejecutor como recurso de
   equilibrio declarado; repetir E2/E3 con errores de demanda.
3. **Estimador de estado** con especificación propia antes de admitir decisiones con datos tardíos (B3C2-02).
4. **D07:** tolerancias definitivas y tiempo límite por ventana a partir de una campaña dedicada (B3C2-11).

## 3. Riesgos heredados

- Miopía del horizonte corto (E2/E4): sin 3C-4 cualquier comparación económica debe mostrar la energía final.
- El dublé algebraico no reproduce dinámica física; la PEMFC instantánea es abstracción declarada (D05/M20 pendientes).
- Sin parámetros reales (BRECHAS_3C1) ninguna microrred del catálogo ejecuta el MPC.
