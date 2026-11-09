# Evidência executada — Piso 3C-3 (gerada por `python -m ems_v2.milp.evidencia_3c3`)

- Data (UTC): 2026-11-09T17:12:30+00:00 · commit: `24534c1357f0fe1b5ab868e4214e72fe2c4ab401`
- Python 3.13.18 · Linux-6.18.44-fc-v310-x86_64-with-glibc2.39 · 4 CPUs · x86_64
- Pyomo 6.10.1 · highspy 1.15.1 · HiGHS 1.15.1 · configuração `CONFIG_ANALITICA` (gaps nulos, 1 thread, semente 0)

Modelo ALGÉBRICO agregado do PCC sobre fixtures e tarifas **SINTÉTICAS** — não é fluxo AC, validação física, controle primário de frequência, fatura elétrica real nem afirmação de tempo real.

## 1. MILP de uma janela (G1–G4, G9, G10, isolado)

| Caso | Esperado (analítico) | Classificação | Estado | P_imp | P_exp | J (R$) | Gasto imp. | Receita exp. | Auditor 3C-3 |
|---|---|---|---|---|---|---|---|---|---|
| G1 | P_imp = 20, J = 8,0 | otimo | aceito_otimo | (20.0, 20.0) | (0.0, 0.0) | 8 | 8 | 0 | aprovada |
| G2 remunerada | P_exp = 20, J = −3,0 | otimo | aceito_otimo | (0.0, 0.0) | (20.0, 20.0) | -3 | 0 | 3 | aprovada |
| G2 sem remuneração | P_exp = 20, J = 0 | otimo | aceito_otimo | (0.0, 0.0) | (20.0, 20.0) | 0 | 0 | -0 | aprovada |
| G3 | P_exp = 0, J = 0,875 | otimo | aceito_otimo | (0.0, 0.0) | (0.0, 0.0) | 0.875 | 0 | -0 | aprovada |
| G4 sem banco | inviável | inviavel | sem_despacho | — | — | — | — | — | — |
| G4 com banco | sem intercâmbio, J = 0,5 | otimo | aceito_otimo | (0.0, 0.0) | (0.0, 0.0) | 0.5 | 0 | 0 | aprovada |
| G9 perfil A | P_imp = (20; 0), J = 1,25 | otimo | aceito_otimo | (20.0, 0.0) | (0.0, 0.0) | 1.25 | 1 | -0 | aprovada |
| G9 perfil B | P_imp = (0; 20), J = 1,25 | otimo | aceito_otimo | (0.0, 20.0) | (0.0, 0.0) | 1.25 | 1 | -0 | aprovada |
| G10 | sem fluxo simultâneo, J = 0 | otimo | aceito_otimo | (0.0, 0.0) | (0.0, 0.0) | 0 | 0 | 0 | aprovada |
| Isolado declarado | = 3C-1, J = 0,875 | otimo | aceito_otimo | — | — | 0.875 | — | — | aprovada |

G10 contraprova: com o indicador de sentido RELAXADO a [0, 1] o mesmo modelo dá J = -5 R$ (P_imp = (25.0, 25.0), P_exp = (25.0, 25.0)) com fluxos simultâneos (importa e exporta ao mesmo tempo); a binária o impede e o auditor rejeita a candidata relaxada (`pcc_exclusividade`).

## 2. G14 — adulteração após o solver

| Adulteração | Estado | Famílias reprovadas |
|---|---|---|
| P_imp[0] + 1 kW | rejeitado_auditoria | ['balanco', 'custo'] |
| custo de importação − R$ 0,5 | rejeitado_auditoria | ['custo'] |
| fluxo simultâneo + 3 kW | rejeitado_auditoria | ['custo', 'pcc_exclusividade', 'pcc_sentido'] |
| mesma solução com PCC indisponível em t = 0 | rejeitada | ['pcc_capacidade', 'pcc_sentido'] |

## 3. Missões MPC conectadas (G5–G8, G11, G12, comparação)

| Missão | N/m | Desfecho | Falha | Aplicados | Importação aplicada por intervalo (kW) | Exportação (kW) | Custo realizado (R$) | Planejado prefixos (R$) | E_imp / E_imp prog. (kWh) | Desvio +/− (kWh) | Auditoria |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G5 erro +4 kW em g=1 (esp. R$ 12,6) | 2/1 | `concluida` | — | 4 | [20.0, 24.0, 20.0, 20.0] | [0.0, 0.0, 0.0, 0.0] | 12.6 | 12 | 21 / 20 | 1 / 0 | aprovada |
| G6 erro −4 kW (esp. R$ 11,4) | 2/1 | `concluida` | — | 4 | [20.0, 16.0, 20.0, 20.0] | [0.0, 0.0, 0.0, 0.0] | 11.4 | 12 | 19 / 20 | 0 / 1 | aprovada |
| G6 demanda 5 kW, exportação permitida (esp. R$ 8,75) | 2/1 | `concluida` | — | 4 | [20.0, 0.0, 20.0, 20.0] | [0.0, 5.0, 0.0, 0.0] | 8.75 | 12 | 15 / 20 | 0 / 6.25 | aprovada |
| G6 demanda 5 kW, exportação PROIBIDA | 2/1 | `interrompida` | consigna_inexequivel | 1 | [20.0] | [0.0] | 3 | 3 | 5 / 5 | 0 / 0 | aprovada |
| G7 FV realizada 4 kW (esp. R$ 12,9) | 2/1 | `concluida` | — | 4 | [20.0, 26.0, 20.0, 20.0] | [0.0, 0.0, 0.0, 0.0] | 12.9 | 12 | 21.5 / 20 | 1.5 / 0 | aprovada |
| G8 saturação P̄_imp = 22 kW | 2/1 | `interrompida` | consigna_inexequivel | 1 | [20.0] | [0.0] | 3 | 3 | 5 / 5 | 0 / 0 | aprovada |
| G11 MPC conectado (revisão tarifária em τ_4) | 4/2 | `concluida` | — | 8 | [0.0, 3.0, 17.0, 20.0, 25.0, 0.0, 0.0, 0.0] | [0.0, 0.0, 0.0, 0.0, 0.0, 15.0, 11.0, 0.0] | 15.9 | 8.1 | 16.25 / 11.5 | 7 / 3.75 | aprovada |
| G12 conectado (demanda = prevista) | 4/2 | `concluida_com_obrigacoes_pendentes` | — | 8 | [0.0, 0.0, 20.0, 20.0, 0.0, 0.0, 0.0, 0.0] | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] | 16.7 | 16.7 | 10 / 10 | 0 / 0 | aprovada |
| G12 isolado (demanda = prevista) | 4/2 | `concluida` | — | 8 | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] | 16.7 | 16.7 | 0 / 0 | 0 / 0 | aprovada |
| G12 conectado (demanda com erro) | 4/2 | `concluida_com_obrigacoes_pendentes` | — | 8 | [0.0, 3.0, 17.0, 20.0, 6.0, 0.0, 0.0, 0.0] | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 6.0, 0.0] | 18.2 | 16.7 | 11.5 / 10 | 2.25 / 2.25 | aprovada |
| G12 isolado (demanda com erro) | 4/2 | `interrompida` | consigna_inexequivel | 1 | [0.0] | [0.0] | 1.45 | 1.45 | 0 / 0 | 0 / 0 | aprovada |
| Open-loop (N = m = 8) | 8/8 | `concluida` | — | 8 | [0.0, 3.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0] | [0.0, 0.0, 3.0, 0.0, 0.0, 0.0, 6.0, 0.0] | 20.95 | 14.2 | 3.25 / 0 | 3.25 / 2.25 | aprovada |
| MPC (N = 4, m = 2) | 4/2 | `concluida` | — | 8 | [0.0, 3.0, 17.0, 20.0, 25.0, 0.0, 0.0, 0.0] | [0.0, 0.0, 0.0, 0.0, 0.0, 15.0, 11.0, 0.0] | 15.9 | 8.1 | 16.25 / 11.5 | 7 / 3.75 | aprovada |

G11 — hash do perfil de importação usado em cada decisão (τ_0, τ_2, τ_4, τ_6): ['c84bb725f13a', 'c84bb725f13a', '4e896c938340', '4e896c938340'] (r1 só a partir da sua emissão em τ_4).

## 4. Comparação open-loop × MPC (§13)

Tipo `causal` · comparável: True · comparável para superioridade (energia final e obrigações iguais): True

| Grandeza | Open-loop | MPC | MPC − OL |
|---|---|---|---|
| custo_realizado_total_R | 20.95 | 15.9 | -5.05 |
| E_final_kWh[syn-bess] | 0 | 0 | 0 |
| obrigacoes_pendentes_s | 0 | 0 | 0 |
| E_importada_kWh | 3.25 | 16.25 | 13 |
| E_exportada_kWh | 2.25 | 6.5 | 4.25 |
| E_importada_programada_kWh | 0 | 11.5 | 11.5 |
| E_desvio_positivo_kWh | 3.25 | 7 | 3.75 |
| E_desvio_negativo_kWh | 2.25 | 3.75 | 1.5 |
| gasto_importacao_R | 3.45 | 13.5 | 10.05 |
| receita_exportacao_R | 0.45 | 1.3 | 0.85 |
| partidas[syn-fc] | 0 | 0 | 0 |
| resolucoes | 1 | 4 | 3 |

> Desfechos: A = 'concluida', B = 'concluida'. Sem veredito: diferenças de energia final armazenada (E_final_kWh) e obrigações pendentes não são valoradas (valor futuro = 3C-4). Rede: conectado × conectado. Energia final/obrigações iguais. Uma única instância sintética: NÃO se afirma que o MPC sempre reduz custos.

G12 isolado × conectado: tipo `contraste_de_topologia` (contraste de factibilidade/uso da rede, não benefício econômico); custos 16.7 × 16.7 R$, E_final 0 × 0 kWh, obrigações 0 × 900 s.

## 5. G13 — interrupção após 2 janelas e retomada verificada

- Impressão determinística da missão retomada = contínua: **True** (`76a59f2a3a2df073…`); totais de rede iguais: True; anexos 3C-3 iguais: True
- Tipos de artefato gravados: ['ems3c0.json', 'ems3c3.json', 'livro.mpc3c2.json', 'missao.mpc3c2.json', 'p0000.janela.mpc3c2.json', 'p0000.rede.mpc3c3.json', 'p0000.retomada.mpc3c2.json', 'p0001.janela.mpc3c2.json', 'p0001.rede.mpc3c3.json', 'p0001.retomada.mpc3c2.json', 'p0002.janela.mpc3c2.json', 'p0002.rede.mpc3c3.json', 'p0002.retomada.mpc3c2.json', 'p0003.janela.mpc3c2.json', 'p0003.rede.mpc3c3.json', 'p0003.retomada.mpc3c2.json', 'rede.missao.mpc3c3.json']

## 6. G15 — retrocompatibilidade 3C-2

- E2: impressão atual `e880fa159d3512db…` = base `e880fa159d3512db…`: True; anexos 3C-1: True. Os 12 conjuntos E1–E8 são comparados por igualdade exata em `tests/ems_v2/test_ems_v2_3c3_regressao_3c2.py`.

## 7. Auditoria independente do PR #16 (commit auditado `d7da6c5`) — C-01 e C-02

**Antes (reproduzido sobre `d7da6c5`, ANTES de qualquer correção; saída literal do script de reprodução):**

```
== C-01 (commit d7da6c5 )
sem_ajuste               programa=False NaN      exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': nan} cod=[]
sem_ajuste               programa=False parcial  exequivel=False aplicado_pcc={} cod=['programa_pcc_ausente']
sem_ajuste               programa=True  NaN      exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': nan} cod=[]
sem_ajuste               programa=True  parcial  exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': 20.0} cod=[]
ajuste_local_algebrico   programa=False NaN      exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': 20.0} cod=[]
ajuste_local_algebrico   programa=False parcial  exequivel=False aplicado_pcc={} cod=['programa_pcc_ausente']
ajuste_local_algebrico   programa=True  NaN      exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': 20.0} cod=[]
ajuste_local_algebrico   programa=True  parcial  exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': 20.0} cod=[]
plano com imp (-3, NaN) aceito? (0.0, 0.0)
plano com imp (-3, 20) => RECORTADO para (0.0, 20.0)
== C-02
sem anexos/registros_3c0/registro de rede: aceito = True ['aceitacao', 'balanco', 'cadeia_registros', 'causal', 'custos', 'estado_e_permanencias', 'livro_observacoes', 'separacao_previsao_realizacao', 'temporal']
modelo PCC substituido (P_imp_max 60): aceito = True
politica economica substituida: aceito = True
```

**Depois (esta execução):**

| Ensaio | Política | Programa explícito | Resultado |
|---|---|---|---|
| P_imp = NaN | `sem_ajuste` | False | exequível = False, falha `dados`, ['intercambio_programado_invalido'] |
| só P_imp (parcial) | `sem_ajuste` | False | exequível = False, falha `dados`, ['intercambio_programado_incompleto'] |
| P_imp = NaN | `sem_ajuste` | True | exequível = False, falha `dados`, ['intercambio_programado_invalido'] |
| só P_imp (parcial) | `sem_ajuste` | True | exequível = False, falha `dados`, ['intercambio_programado_incompleto'] |
| P_imp = NaN | `ajuste_local_algebrico` | False | exequível = False, falha `dados`, ['intercambio_programado_invalido'] |
| só P_imp (parcial) | `ajuste_local_algebrico` | False | exequível = False, falha `dados`, ['intercambio_programado_incompleto'] |
| P_imp = NaN | `ajuste_local_algebrico` | True | exequível = False, falha `dados`, ['intercambio_programado_invalido'] |
| só P_imp (parcial) | `ajuste_local_algebrico` | True | exequível = False, falha `dados`, ['intercambio_programado_incompleto'] |
| plano com P_imp = (-3.0, 20.0) | — | — | recusado: ['intercambio_programado_invalido'] (sem recorte) |
| plano com P_imp = (nan, 20.0) | — | — | recusado: ['intercambio_programado_invalido'] (sem recorte) |

| Auditoria INTEGRAL — caso | aceito | integridade certificada | balanço / custos | Constatações (erro) |
|---|---|---|---|---|
| missão G11 válida | True | True | True / True | [] |
| sem anexos | False | False | True / True | ['anexos_3c3_divergentes', 'auditoria_integral_incompleta'] |
| sem registros 3C-0 | False | False | True / True | ['auditoria_integral_incompleta'] |
| sem registro de missão de rede | False | False | True / True | ['auditoria_integral_incompleta'] |
| registro 3C-0 de outra janela | False | False | True / True | ['anexo_3c3_invalido', 'artefato_de_outra_execucao', 'artefato_de_outra_missao', 'checkpoint_divergente', 'custo_divergente'] |
| evidências de duas janelas trocadas | False | False | True / True | ['anexos_3c3_divergentes', 'artefato_de_outra_execucao', 'artefato_de_outra_missao', 'checkpoint_divergente', 'custo_divergente'] |
| modelo PCC com P̄_imp + 10 kW (mesmo núcleo) | False | False | True / True | ['modelo_3c3_divergente'] |
| configuração de rede sem a revisão r1 (mesmos custos realizados) | False | False | True / True | ['configuracao_rede_divergente'] |

Auditoria ANALÍTICA PARCIAL com o modelo de limites mais amplos: aceito = True, escopo `analitica_parcial`, integridade documental certificada = False — reproduz os números, mas nunca certifica integridade.

## 8. Campanha de tempos (indicativa)

Missão G11 completa (4 janelas, MILP 3C-3 + auditorias + registros), n = 5: {"definicao": "percentil de posto mais pr\u00f3ximo: valor de ordem ceil(p\u00b7n) (1-indexado), sem interpola\u00e7\u00e3o", "maximo": 0.1314, "media": 0.1262, "n": 5, "p50": 0.1275, "p95": 0.1314, "p99": 0.1314} s. Uma máquina, sem restrição operacional: nenhuma afirmação de tempo real.

