# Piso 3C-3 — Informe de brechas: parámetros reales, física, tarifas y medición (entregable M)

Las brechas de `BRECHAS_3C0.md`, `BRECHAS_3C1.md` y `BRECHAS_3C2.md` siguen vigentes salvo las cerradas abajo. Todo
lo ejecutado en 3C-3 usa fixtures, tarifas y PCC **sintéticos**; ninguna microrred del catálogo ejecuta el EMS V2.

## 1. Cerradas por 3C-3

| # | Brecha previa | Cierre |
|---|---|---|
| O3 (3C-0) | Topología conectada / red / tarifas | `EspecPCC`, tarifas por bloques, MILP 3C-3 (FORMULACAO_3C3 §1–§3) |
| B3C2-01 | Recurso de equilibrio ante error de previsión | Ajuste local algebraico del PCC con política declarada, límites, disponibilidad y medición (§5); los errores absorbibles por el PCC ya no interrumpen la misión (G5–G7, G11) |

## 2. Abiertas

| # | Brecha | Efecto | Responsable/piso sugerido |
|---|---|---|---|
| B3C3-01 | **Parámetros reales del PCC**: límites contratados de importación/exportación por intervalo, disponibilidad, sentidos, contrato. No existen en el inventario SEEDS2 ni en `ponte/requisitos.py` | Ninguna microrred real puede declarar un PCC | Inventario/escenario 3D (campos nuevos con procedencia; nunca inferidos) |
| B3C3-02 | **Tarifas reales** (ANDE u otras), cargos de demanda/potencia, impuestos, bandas horarias oficiales, reglas de compensación/net metering, cargos por desvío | La función de costo NO representa una factura; los experimentos usan tarifas sintéticas rotuladas | Especificación tarifaria verificada y aprobada por el responsable; nada se inventa |
| B3C3-03 | **Física de red**: flujo AC, tensión, reactivo, frecuencia, protecciones, límites térmicos de alimentadores, dinámica de convertidores, transitorios | Modelo de balance activo agregado; el ajuste no es control primario validado | 3D/estudios eléctricos dedicados |
| B3C3-04 | **Curtailment en tiempo real como acción de equilibrio** (y ENS/descarte realizados) | Con exportación prohibida y excedente, la misión se interrumpe (C-3C3-04) | Política declarada adicional (recorte renovable autorizado, orden de mérito) |
| B3C3-05 | **Medición real del PCC**: incertidumbre, clase de exactitud, sincronización del medidor, energía integrada vs potencia media | La comparación reconstruido × medido usa la tolerancia provisional D07 de potencia | Especificación metrológica (D07 + clase del medidor) |
| B3C3-06 | **Re-liquidación** con revisiones posteriores del precio de liquidación; precios negativos; liquidación por energía integrada de medidor | Un perfil por magnitud; liquidación al cerrar la ventana | Especificación económica |
| B3C3-07 | Disponibilidad **parcial** del PCC (derating fraccionario, límites dependientes del estado de la red) | a ∈ {0,1}; fraccionaria ⇒ pendiente | Contrato propio (como B01) |
| B3C3-08 | Banda de desvío contractual (límite del desvío respecto del programado más allá del límite físico) | Solo límites contratados absolutos | Parámetro contractual declarado |
| B3C3-09 | Seguridad/permiso de conexión–desconexión (isla intencional, resincronización) | El modo es fijo en la misión; no hay transición conectado ↔ isla | Especificación de operación (3D) |
| B3C3-10 | Persistencia en el `MicrogridStore` y UI | Evidencia en directorio de archivos exclusivos | 3D |
| B3C3-11 | La auditoría integral verifica la coherencia de los artefactos ENTRE SÍ y con los objetos suministrados; un conjunto (registros + anexos + registro de red + modelo + configuración) re-sellado en bloque por quien controle todos los archivos sigue siendo coherente | SHA-256 no es firma (K10 heredada): la certificación es relativa a una referencia confiable conservada | Firma digital / almacenamiento de confianza (fuera de alcance) |

## 3. Hipótesis aceptadas provisionalmente (requieren aprobación)

1. Precio = valor del bloque que contiene el intervalo entero (sin prorrateo).
2. Liquidación de referencia por potencia media × h (energía del intervalo) a precio de liquidación.
3. Costo planificado del prefijo con las tarifas de decisión de la ventana (D-3C3-10).
4. Tolerancia de comparación reconstruido × medido = tolerancia provisional D07 de potencia.
5. Exportación sin remuneración declarada se trata como crédito cero (no como prohibición).
