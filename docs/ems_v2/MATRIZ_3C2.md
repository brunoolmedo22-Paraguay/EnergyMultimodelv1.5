# Piso 3C-2 — Matriz de trazabilidad requisito → código → prueba → evidencia (entregable K)

Todas las pruebas son **sintéticas/algebraicas** (`synthetic_algebraic`). Las de solver corren contra **HiGHS 1.15.1
real** (Pyomo 6.10.1) por el adaptador `ResolvedorMILP3C1` y se saltan explícitamente sin Pyomo. Abreviaturas:
`ct::` = `test_ems_v2_3c2_contrato.py` (19), `ob::` = `test_ems_v2_3c2_observacoes.py` (8), `pv::` =
`test_ems_v2_3c2_previsao.py` (7), `la::` = `test_ems_v2_3c2_laco.py` (16, **sin solver**: dublé de regla analítica
aprobado por el auditor independiente 3C-1), `mi::` = `test_ems_v2_3c2_milp.py` (29, HiGHS), `is::` =
`test_ems_v2_3c2_isolamento.py` (4), `pr15::` = `test_ems_v2_3c2_auditoria_pr15.py` (24, correcciones C-01/C-02).
Total nuevo: **107**. Evidencia ejecutada: `EVIDENCIA_3C2_EJECUCION.md` (`ev §n`).

## Batería obligatoria (misión §13)

| # | Requisito | Código | Prueba(s) | Resultado / evidencia |
|---|---|---|---|---|
| 1 | Misión de una ventana | `orquestrador`, `relogio` | `la::test_missao_de_uma_janela_igual_ao_fluxo_direto_3c1_3c0`, `mi::test_missao_de_uma_janela_igual_ao_fluxo_3c1_direto` | Estados/costos idénticos al flujo directo `resolver_3c1` + `executar` (R$ 18,7) |
| 2 | Varias ventanas, m < N | `ControladorMPC`, `executar_missao_simulada` | `la::test_missao_de_varias_janelas_valores_analiticos…`, `mi::test_e2_varias_janelas_…` | NS: R$ 0,175/0,15/0,15 (analítico); E2: R$ 1,7/2,0/6,125/3,075 = 12,9 (a mano) |
| 3 | Último bloque < m | `relogio.janela_em` (m_k = min(m, K_M − k)) | `ct::test_cronograma_m_menor_que_N_e_ultimo_bloco_curto`, `la::test_ultimo_bloco_menor_que_m…`, `mi::test_ultimo_bloco_menor_que_m` | K_M = 7, m = 2 ⇒ bloques 2, 2, 2, 1 |
| 4 | Horizonte que excede el fin | `PoliticaTerminalMissao`, `cobertura_pos_missao_exigida_min` | `ct::test_janela_reduzida_x_horizonte_estendido`, `ct::test_horizonte_maior_que_missao_tratado…`, `mi::test_horizonte_estendido_declarado_planeja_mas_nunca_aplica_pos_missao`, `mi::test_politica_cumprir_na_janela_final…` | Reducida: N_k = 2 registrada; extendida: 2 intervalos posmisión planificados y nunca aplicados; sin cobertura ⇒ `previsao_invalida` en k = 6 |
| 5 | Previsión reemitida por ventana | `previsao`, `provedores` | `pv::test_provedor_reemite_quando_a_informacao_muda…`, `pv::test_previsao_reemitida_em_cada_janela_tem_hash_proprio`, `mi::test_e2_varias_janelas_…` | FV 10 → 25 tras observar el escalón; 4 hashes distintos |
| 6 | Previsión emitida tarde | `validar_previsao_janela` | `pv::test_previsao_emitida_tarde_serie_apos_conjunto_e_sem_vinculo`, `mi::test_previsao_emitida_tarde_bloqueia_sem_comando` | `previsao_nao_causal`; planta sin comando (g = 0) |
| 7 | Fuga deliberada de información futura | `auditoria.verificar_nao_antecipatividade`, `_separacao` | `mi::test_fuga_deliberada_de_informacao_futura_detectada_por_intervencao`, `mi::test_fuga_com_evidencia_de_hash_bloqueada…` | Honesto: 0 divergencias; malicioso: `hash_previsao` diverge en τ_2 (pasó en ejecución: límite documentado); hash del realizado ⇒ `previsao_derivada_da_realizacao` |
| 8 | Observación tardía y revisión append-only | `observacoes`, `_examinar_revisoes`, `politica_revisao_tardia` | `ob::test_revisoes_append_only_conflitos_e_resolucao`, `ob::test_corte_selado_e_recepcao_retroativa_recusada`, `mi::test_e8_revisao_tardia_nao_altera_decisao_passada` | Decisiones en τ_0, τ_2 idénticas (instantáneo y plan); original preservado; `interromper` ⇒ parada en τ_4 |
| 9 | Observación faltante y parada segura | `realizacao_de_instantaneo`, barrera C-02 | `ob::test_realizacao_de_instantaneo_faltantes_e_barreira_c02`, `la::test_observacao_faltante_parada_segura_modo1`, `mi::test_disponibilidade_do_gerador_omitida_parada_segura` | `estado_nao_reconstruivel`; ningún comando posterior; ausente ≠ cero |
| 10 | SOC transportado | `entrada_de_continuacao`, `_estado` (auditoría) | `mi::test_e6_soc_transportado_do_executado_nunca_do_terminal_planejado`, `la::*` (auditoría de recurrencia) | Plan v0 termina en 0 kWh; ejecutado en τ_2 = 10 kWh inicia la ventana 1 |
| 11 | Commitment y tiempos mínimos entre ventanas | memoria ejecutada + 3C-1 | `mi::test_e5_memoria_de_commitment_atravessa_tres_janelas`, `mi::test_e5_contraprova_memoria_descartada…` | u = [0,0,0,1,1,1,0,0] (U = 3 en 3 ventanas); sin memoria ⇒ planta rechaza `permanencia_minima_violada` |
| 12 | Reanudación desde checkpoint | `persistencia.PontoRetomada`, `retomar_controlador` | `la::test_persistencia_retomada_…`, `la::test_retomada_recusa_ponto_adulterado…`, `mi::test_retomada_de_checkpoint_com_highs` | Impresión determinista idéntica a la ejecución continua; punto adulterado/otra configuración ⇒ rechazo |
| 13 | Falla del solver | `avaliar_aceitacao`, `ResolvedorComFalha` | `ct::test_aceitacao_nunca_aceita…`, `mi::test_e7_falha_do_solver_nao_reaproveita_plano_anterior`, `mi::test_e7_excecao_do_solver…` | Sin plan; el sufijo del plan anterior no se usa (planta en g = 2) |
| 14 | Rechazo del auditor | auditor 3C-1 vía `resolver_3c1` | `mi::test_e7_rejeicao_do_auditor_nada_e_executado` | `rejeitado_auditoria`; ningún comando |
| 15 | Cambio de identidad | `verificar_identidade`, libro K6 | `la::test_mudanca_de_identidade_de_microrrede_ou_cenario`, `la::test_observacao_de_outra_microrrede…`, `mi::test_construcao_com_identidade_divergente…` | `identidade_divergente` (solo interrumpe); observación ajena rechazada |
| 16 | Costo acumulado sin doble conteo | `custo_acumulado`, `custo_realizado_independente` | `la::test_custo_acumulado_sem_dupla_contagem…`, `mi::test_custo_sem_dupla_contagem…` | Σ realizados = misión (R$ 0,475 / 12,9); Σ objetivos de ventanas ≠ realizado |
| 17 | Integridad de la cadena | `verificar_cadeia_janelas`, `verificar_registro_missao`, `verificar_cadeia_livro` | `la::test_integridade_da_cadeia_…`, `ob::test_exportar_importar_reproduz_e_detecta_adulteracao`, `mi::test_e2_registros_3c0_e_anexos_3c1_verificaveis…` | Alteración/remoción/reordenación/vínculo de checkpoint detectados; anexos 3C-1 verifican contra el registro 3C-0 |
| 18 | Reproducción determinista | `impressao_deterministica` | `la::test_reproducao_determinista_da_mesma_missao`, `mi::test_reproducao_determinista_com_highs` | Misma impresión, cadena de contenido y cadena del libro |
| 19 | Open-loop × MPC | `comparadores` | `mi::test_e3_open_loop_versus_mpc_em_condicoes_comparaveis`, `mi::test_e3_comparador_recusa_condicoes_diferentes` | OL R$ 18,7 (E_final 0) × MPC R$ 12,9 (E_final 2,5; obligación 900 s pendiente) — sin veredicto (ev §2) |
| 20 | Adversariales de causalidad e integridad | `auditoria`, `entorno` | `mi::test_adversarial_registro_e_livro_adulterados…`, `ob::test_invalidas_outra_microrrede_recurso_e_informacao_futura`, `ob::test_duplicatas_conflito…`, `pv::test_oraculo_so_em_ablacao…` | Instantáneo/livro adulterados ⇒ rechazo; comando fuera de orden ⇒ `rejeitada_protocolo`; observación recibida antes del fin ⇒ inválida |

## Correcciones de la auditoría del PR #15

| ID | Requisito | Código | Prueba(s) | Resultado |
|---|---|---|---|---|
| C-01 | I_k nunca depende de un evento con recepción > τ_k (cualquier clasificación) | `observacoes` (marca de agua total, cuarentena, prefijo por recepción) | `pr15::test_c01_evento_futuro_de_qualquer_classificacao…` (8 clasificaciones) | n y hash de τ_2 idénticos con y sin el evento futuro; sellar τ_2 ⇒ `corte_antes_de_recepcao_registrada` |
| C-01 | Eventos anteriores al corte (todas las clases) en el prefijo | `instantaneo` | `pr15::test_c01_eventos_antes_do_corte…` | prefijo de 6 entradas (aceptada, duplicada, rechazada, inválida, semántica) |
| C-01 | Recepción retroactiva/ilegible: cuarentena trazable, sin hora inventada, corte intacto | `_quarentena_motivo`, `importar` | `pr15::test_c01_recepcao_retroativa_ou_ilegivel…`, `pr15::test_c01_fora_de_sequencia_dos_dois_lados…` | cuarentena 4 entradas; I(τ_2) idéntico; exportar/importar reproducen; quarentena adulterada ⇒ rechazo |
| C-01 | Auditoría de la propiedad temporal de TODAS las entradas | `auditoria._propriedade_temporal`, `verificar_cadeia_livro` | `pr15::test_c01_auditoria_verifica…`, `pr15::test_c01_missao_completa_auditada…` | `informacao_futura_no_instantaneo`; `corte_inclui_recepcao_posterior`; `quarentena_divergente_da_missao` |
| C-01 | El controlador no decide con evento futuro en el libro | `decidir` | `pr15::test_c01_controlador_recusa_decidir…` | `integridade`, ningún comando |
| C-02 | Reanudación intacta restaura históricos | `retomar_controlador` | `pr15::test_c02_retomada_intacta…` | 2/2 registros y anexos con los mismos sellos |
| C-02 | Registro/anexo eliminado, alterado, re-sellado, de otra ejecución, intercambiado | `verificar_artefatos_janela` | `pr15::test_c02_artefato_eliminado…`, `…registro_3c0_alterado…`, `…anexo_alterado_e_reselado…`, `…de_outra_execucao_ou_trocados…` | `registro_3c0_ausente`, `anexo_3c1_ausente`, `registro_3c0_adulterado`, `selo_registro_3c0_divergente`, `selo_anexo_3c1_divergente`, `anexo_3c1_invalido`, `artefato_de_outra_execucao` |
| C-02 | Sello referenciado incorrecto; ventana sin plan | idem | `pr15::test_c02_selo_referenciado_incorreto…`, `pr15::test_c02_janela_sem_plano…` | ventana sin plan no exige artefactos; referenciarlos ⇒ `artefato_referenciado_sem_plano` |
| C-02 | Libro/punto de retomada coherentes con las ventanas | `_verificar_livro_contra_janelas` | `pr15::test_c02_ponto_de_retomada_com_livro_truncado…` | `livro_incoerente_com_janelas` |
| C-02 | Reanudaciones sucesivas = ejecución continua | idem | `pr15::test_c02_retomadas_sucessivas…`, `mi::test_retomada_de_checkpoint_com_highs` | misma impresión determinista; 3 registros 3C-0 con los mismos `execucao_uid` |

## Experimentos (misión §12)

| Exp. | Código | Prueba | Resultado |
|---|---|---|---|
| E1 oráculo (ablación) | `experimentos.e1_oraculo` | `mi::test_e1_oraculo_rotulado_e_excluido…` | MPC y horizonte completo R$ 2,075 (comparación de referencia; excluida de las causales) |
| E2 previsión imperfecta | `e2_previsao_reemitida` | `mi::test_e2_*` | Se adapta tras observar; auditoría independiente aprobada |
| E3 open-loop × MPC | `e3_open_loop_vs_mpc` | `mi::test_e3_*` | Ver #19 |
| E4 frecuencia m | `e4_frequencia` | `mi::test_e4_frequencia_de_reotimizacao` | m = 1: R$ 7,2625 (8 resoluciones; obligación 1800 s pendiente); m = 2 y 4: R$ 12,9 |
| E5 memoria | `e5_memoria` | `mi::test_e5_*` | Ver #11 |
| E6 batería | E2 + auditoría `_estado` | `mi::test_e6_*` | Ver #10; SOC ∈ [0, 1] |
| E7 falla solver/auditor | `e7_falha_na_janela` | `mi::test_e7_*` | Ver #13/#14; no óptimo solo con política (gap/terminación) |
| E8 observaciones tardías | `e8_revisao_tardia`, modo 2 | `mi::test_e8_*`, `la::test_modo2_*` | Ver #8; modo 2 pausa C-02 y reanuda del checkpoint |

## Requisitos transversales

| Requisito (misión) | Implementación | Prueba(s) | Estado |
|---|---|---|---|
| §3 contratos temporales (N, m, K_M, H_f distintos; 1 ≤ m ≤ N; contador monotónico) | `contrato`, `relogio` | `ct::test_malha_*`, `ct::test_relogio_monotonico…` | implementado |
| §4 núcleo sin Pyomo/HiGHS/Streamlit/SEEDS2; adaptador explícito | `adaptador_milp` (import tardío) | `is::test_nucleo_mpc_so_biblioteca_padrao_ao_importar`, `is::test_mpc_sem_seeds2_ui…` | implementado |
| §5 K6 (identidad, tiempos físico × recepción, reglas) | `observacoes` | `ob::*` (8) | implementado |
| §6 previsión por ventana, independencia, oráculo rotulado | `previsao`, `provedores` | `pv::*` (7) | implementado (límite §3 de FORMULACAO) |
| §7 modo 1 / modo 2; C-02 intacta | `entorno`, `orquestrador` | `la::test_modo2_*`, `mi::*` | implementado (algebraico) |
| §8 estado/memoria ejecutados; checkpoints con vínculo explícito | `janela`, `selo_checkpoint_origem` | `mi::test_e5_*`, `mi::test_e6_*`, `la::test_integridade…` | implementado |
| §9 registro por ventana; seguridad de aceptación | `ConteudoJanelaMPC`, `avaliar_aceitacao` | `ct::test_aceitacao_*`, `mi::test_e7_*` | implementado |
| §10 persistencia y evidencia de misión; tipos nuevos | `registro`, `persistencia` | `la::test_persistencia_*`, `la::test_registros_sao_gravados_de_forma_exclusiva` | implementado |
| §11 métricas con definiciones; entorno registrado | `metricas`, `ambiente_execucao` | `mi::test_metricas_*` | implementado |
| §14 compatibilidad 3A/3B-P/3C-0/3C-1/V1.6 | ningún archivo existente modificado desde `55440f4` | `is::test_pisos_anteriores_v16_e_aplicacao_sem_alteracao…`, `is::test_adicoes_3c1…`, 717 tests anteriores | implementado |
| Capacidad M23 declarada | `mpc/capacidades.py` (`parcial_3C2`) | `ct::test_capacidade_m23_declarada_parcial…` | implementado |
