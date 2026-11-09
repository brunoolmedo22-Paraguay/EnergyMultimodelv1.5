# Piso 3C-2 — Informe de brechas e hipótesis pendientes (entregable L)

Las brechas de `BRECHAS_3C0.md` (η, P en barra, autodescarga, curva PEMFC, previsiones del SEEDS2) y de
`BRECHAS_3C1.md` (rampas, T_on/T_off, S⁺/S⁻, C_SD, m_SU/m_SD, estado/memoria por unidad) **siguen vigentes**: ninguna
microrred real del catálogo puede ejecutar el MPC hoy. Todo lo ejecutado en 3C-2 usa fixtures sintéticas y la planta
algebraica.

## 1. Cerradas por 3C-2

| # | Brecha previa | Cierre |
|---|---|---|
| K6 (3C-0) | Operación online del MPC: libro append-only, recepción, tardías/revisiones, previsión reemitida, política de huecos | `ems_v2/mpc/observacoes.py`, `previsao.py`, `orquestrador.py` (modos 1 y 2), FORMULACAO_3C2 §3–§4 |
| T-3C1 §2.1 | Bucle recedente | `ControladorMPC` |
| T-3C1 §2.3 | Política para la ventana final | `PoliticaTerminalMissao` (dos políticas, condiciones de validez) |
| T-3C1 §2.4 | Registro de la cadena de ventanas | `RegistroJanelaMPC` + `RegistroMissaoMPC` |

## 2. Abiertas (bloquean o limitan el uso científico/operacional)

| # | Brecha | Efecto | Responsable/piso sugerido |
|---|---|---|---|
| B3C2-01 | **Recurso de equilibrio** ante error de previsión (C-3C2-01): sin red ni capa primaria modelada, cualquier error de demanda o sobreestimación renovable en un intervalo aplicado vuelve la consigna inexequible | El MPC solo completa misiones con errores absorbibles por las consignas | Red/intercambio (3C-3) o capa primaria con modelo físico (3D); requiere especificación aprobada |
| B3C2-02 | **Estimador de estado**: solo propagación algebraica con observaciones completas; con latencia en la frontera de decisión la misión se detiene (D-3C2-06) | Sin tolerancia a datos tardíos en la decisión | Especificación propia (estimador + incertidumbre); no se inventa |
| B3C2-03 | **Planta física** (Φ_phys): el ejecutor es el dublé 3C-1; la PEMFC/BESS reales con memoria interna no existen como `ExecutorPasso` | No es validación física (adenda v1.1, límite 3) | 3D (adaptador físico con checkpoint/avance continuo, especificación §15) |
| B3C2-04 | **Valor futuro/terminal**: horizonte corto miope (drena el banco; arranca en el último intervalo) | Comparaciones económicas sesgadas por energía final distinta | 3C-4 (planificador jerárquico) |
| B3C2-05 | Disponibilidad de bancos no verificada por el ejecutor 3C-0 (C-3C2-03) | La observación se registra, no condiciona la conciliación | Extensión versionada del ejecutor |
| B3C2-06 | `estatica_declarada` no se contrasta con observaciones del libro en la conciliación (C-3C2-04) | Contradicción no detectada en ese caso | Pasar claves opcionales a la conciliación (requiere series con huecos) |
| B3C2-07 | Imputación de faltantes | Ausente ⇒ parada | Política de imputación propia (no introducida) |
| B3C2-08 | Persistencia en el banco de cada microrred (`MicrogridStore`) | Evidencia en directorio de archivos exclusivos | Integración 3D |
| B3C2-09 | Firma/almacenamiento de confianza (K10 heredada) | SHA-256 detecta alteración frente a un registro confiable, no prueba autoría | Fuera de alcance |
| B3C2-10 | Protección contra fuga es estructural + auditoría posterior por intervención (límite de confianza §3) | Un proveedor con referencia oculta a la verdad pasa en ejecución | Aislamiento de proceso/sandbox del proveedor (no implementado) |
| B3C2-11 | Campaña de tiempos: n pequeño, una máquina, sin restricción operacional | Sin afirmación de tiempo real | Campaña dedicada (D07 y límites de tiempo por ventana) |
| B3C2-12 | Modo 2 sin conexión física: confirmaciones y observaciones provienen de la planta de ensayo o del operador del ensayo | No hay control real | 3D/operación |
| B3C2-13 | **Tiempo de ingestión confiable** (C-01): el orden causal del libro usa el `recebido_utc` DECLARADO por la fuente/canal; una fuente con reloj falso puede declarar recepciones verosímiles | El libro garantiza coherencia de las recepciones declaradas (orden, cortes, prefijos, cuarentena), no su veracidad | Reloj de ingestión propio del controlador + contrato de fuente (no implementado) |

## 3. Hipótesis aceptadas provisionalmente (requieren aprobación)

1. Corte inclusivo `recebido ≤ τ_k` (D-3C2-01).
2. Conciliación exige confirmación `aplicada` **y** observaciones obligatorias (D-3C2-05).
3. `horizonte_estendido_declarado` con `intervalos_missao` de la entrada = N_k (D-3C2-04, C-3C2-02).
4. Costo planificado del prefijo = plan × previsión con la contabilidad 3C-1 (D-3C2-08).
5. Proveedores sintéticos (tabla declarada, corrección aditiva con piso 0) como únicos generadores de previsión.
6. Política de revisión tardía `registrar_sem_reconciliar` no reescribe el estado ya reconstruido (el estado puede
   quedar sostenido por un valor luego revisado; queda señalado en el registro de la ventana).
