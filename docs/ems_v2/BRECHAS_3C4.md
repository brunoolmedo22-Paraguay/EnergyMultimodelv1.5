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
| **B3C4-01** | **Deriva de coma flotante de la energía ejecutada (heredada de 3C-0/3C-2/3C-3; contradicción C-3C4-03)**: la recurrencia del ejecutor y los valores del solver producen E = C + 2 ulp; la validación de la ventana siguiente es SIN recorte ⇒ `energia_maior_que_capacidade` / `soc_inicial_fora_dos_limites` ⇒ misión interrumpida (`bloqueado_validacao`) | Misiones correctas se detienen por un artefacto numérico (H9: línea de base 3C-3 y `hier_ref_dura`) | Requiere AUTORIZACIÓN para tocar pisos protegidos: (a) ejecutor que proyecte al límite físico cuando |E − C| ≤ tolerancia D07 de energía, registrando la transformación; o (b) validación que admita la frontera con tolerancia D07 declarada. Nunca recorte silencioso |
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
