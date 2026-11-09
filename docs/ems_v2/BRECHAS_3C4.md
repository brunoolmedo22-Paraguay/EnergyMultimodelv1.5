# Piso 3C-4 — Informe de brechas, hipótesis y riesgos

Las brechas de `BRECHAS_3C0.md` … `BRECHAS_3C3.md` siguen vigentes salvo las cerradas abajo. Todo lo ejecutado en
3C-4 usa fixtures, previsiones y tarifas **sintéticas**; ninguna microrred del catálogo ejecuta el EMS V2.

## 1. Cerradas por 3C-4

| # | Brecha previa | Cierre |
|---|---|---|
| Valor futuro (3C-0 `nao_implementado_3C0`, TRANSICAO_3C3_3C4 §2) | Miopía del horizonte corto | Custo de continuação estimado por reoptimización paramétrica auditada (`custo_futuro_pwl`), contrato sellado, MILP corto 3C-4, auditor terminal, registros; nunca contabilizado como costo |
| Separar reoptimizar × anticipar (TRANSICAO_3C3_3C4 §2.2) | Comparación open-loop × MPC mezclaba efectos | `comparadores.comparar`: reoptimización, anticipación e información perfecta con condiciones terminales explícitas |
| Horizonte de planificación reservado (3C-0 `horizonte_planejamento_min`) | Sin uso | `ConfiguracaoPlanejador3C4.horizonte_longo_intervalos` validado contra N y H_F (el campo 3C-0 sigue reservado: no se reinterpreta) |

## 2. Abiertas (nuevas)

| # | Brecha | Efecto | Propuesta / piso |
|---|---|---|---|
| ~~B3C4-01~~ | **Cerrada por hotfix AUTORIZADO (auditoría del PR #17, `c964a2e`)**: deriva de coma flotante de la energía ejecutada (C + 1 ulp por `P_d = −1,78e-15` del solver) | Proyección numérica al límite SOLO si el exceso ≤ min(tolE D07, 16·u·S), con aviso y reconstrucción bit a bit en la auditoría (FORMULACAO_3C4 §10b); excesos mayores inalterados | — |
| **B3C4-10** (nueva, heredada del 3C-3) | **Residuo del solver en variables ≥ 0 del PCC**: `P_imp = −8,881784197001252e-16` kW; la regla C-01 del 3C-3 (programa real ≥ 0, sin recorte; aprobada en la auditoría del PR #16) rechaza el plan ⇒ falla de integridad (H9, línea de base 3C-3 y referencia dura, k = 10) | Misiones correctas se detienen por un artefacto numérico del solver | **Decisión del responsable**: p. ej. extender la misma política numérica (|v| ≤ 16·u·S con S = límites contratados) a la extracción del programa, registrando la corrección; NO implementado (fuera de la autorización: reinterpretaría C-01) |
| B3C4-11 | **Cobertura del dominio (A02)**: la exclusión de un modo/rango depende del certificado de inviabilidad del B&B del HiGHS (sin certificado independiente para MILP); el dominio es una aproximación INTERNA (margen ≤ tolerancia de dominio) | El planificador es conservador: sin certificado ⇒ `dominio_indeterminado` y señal indisponible (degradación declarada) | Certificados verificables (p. ej. enumeración de commitment + Farkas por subproblema LP) |
| B3C4-02 | Modos con obligación residual ρ > 0 elegible en la frontera (hoy: `cumprir_na_janela` exigido ⇒ ρ = 0 salvo obligación heredada) | Restringe el instante de arranque cerca de la frontera; H9: jerárquico R$ 129,6 × óptimo de información perfecta R$ 127,6 (brecha de R$ 2,0 atribuible a la condición, no a la previsión) | Familia V_{(u, ρ)} con ρ lineal en y (ver FORMULACAO_3C4 §10, D-3C4-04) |
| B3C4-03 | Más de 2 bancos; 2D no convexo (triangulación con binarias); dominio 2D no rectangular | Señal `indisponivel` (declarado) | Triangulación con selección de símplice; o agregación probada |
| B3C4-04 | Incertidumbre: V^tail determinista bajo previsión puntual | Valor futuro sin cobertura de riesgo | Escenarios/SDDP (fuera de alcance); familia `incerteza_estocastica_do_valor_futuro` no modelada |
| B3C4-05 | Costo computacional O(modos × puntos) MILP por ventana; sin presupuesto de tiempo ni paralelismo | No apto para tiempo real (no se promete) | Presupuesto declarado + caché entre ventanas con la misma información (política `ao_mudar_informacao`) |
| B3C4-06 | Segunda resolución temporal (planificador horario × MPC subhorario) | Todo en la misma malla (D-3C4-03) | Transformación energética explícita comprobada |
| B3C4-07 | Ventanas finales: señal = Φ_L declarado; con `nenhum_declarado` el valor residual del estado final es 0 por declaración | Comparaciones dependen de Φ_L común | Φ_L calibrado por el responsable (p. ej. valor de reposición) |
| B3C4-08 | La auditoría integral certifica coherencia ENTRE artefactos; un conjunto re-sellado en bloque por quien controle todos los archivos sigue siendo coherente (SHA-256 no es firma, K10/B3C3-11 heredadas) | Certificación relativa a una referencia confiable | Firma/almacenamiento de confianza |
| B3C4-09 | Persistencia en `MicrogridStore`, UI y runtime | Evidencia en directorio de archivos | 3D |

## 3. Hipótesis aceptadas provisionalmente (requieren aprobación)

1. Φ_L `nenhum_declarado` común a todas las estrategias como tratamiento terminal de los experimentos.
2. Tolerancia de interpolación 1e-6 R$ y tolerancia de dominio 0,5 kWh (bisección conservadora) en las fixtures.
3. Una señal solo es "válida" con todas sus evaluaciones `aceito_otimo` (gap 0 en `CONFIG_ANALITICA`).
4. Tiempo en el estado ⌈T⌉ − ρ en la memoria de la cola (lema §4.3) y potencia P_on_min cuando las rampas son inactivas
   (lema §4.4).
5. Tolerancias del auditor: las provisionales D07.
