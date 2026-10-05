# EMS · Despacho ótimo multifonte — Energy MultiModel V1.4

O EMS fecha o fluxo da plataforma. Os módulos calculam a dinâmica de cada
fonte, e o EMS usa essas séries como envelope e custo para decidir, a cada
minuto, **quantos stacks PEMFC ligar** e **quanto cada fonte entrega** para
atender o perfil de carga ao menor custo.

O núcleo foi portado do EMS MATLAB `ems_h2_embarcacao_powertrain_v2`. A cópia
original, sem alterações, está em `reference_models/ems_matlab/` para
rastreabilidade. Tudo roda em Python: não é preciso MATLAB.

## Como usar

1. `streamlit run app.py` → cartão **EMS · DESPACHO** → **Configuração**.
2. **Perfil de carga**: walk-forward da embarcação (3 cenários × 3 perfis ×
   15 horários, 2 h cada), COPEL B1 de 24 h com janela recortável, ou CSV
   próprio (`t_min,P_kW` ou `timestamp,P_kW`).
3. **Fontes**: para cada uma, escolha a origem.

   | Fonte | Origens |
   |---|---|
   | H₂ / PEMFC | caracterização automática (N stacks) · resultado do módulo H₂ |
   | Bateria | caracterização automática (Ns × Np, química, taxas C) · resultado do módulo Bateria |
   | Térmica | disponibilidade automática (gerador local) · resultado do módulo Térmica |
   | Eólica | resultado do módulo Eólica (não despachável) |
   | Solar | resultado do módulo Solar, com escolha do modelo (não despachável) |

   **Solar e eólica são não despacháveis**: toda a potência disponível é
   descontada da carga antes da otimização, e o EMS despacha FC, bateria e
   térmica só para o restante. O que passa da carga é vertido (não carrega a
   bateria), como já acontecia com a solar no EMS original. Para aparecerem
   como opção, rode antes os módulos Solar e/ou Eólica na mesma sessão.

4. **Otimização**: metaheurística (GWO, NGO, GA ou só SQP), horizonte N,
   semente e preços.
5. **▶ CALCULAR MODELOS E OTIMIZAR DESPACHO**, ou **▶ COMPARAR GA · GWO · NGO · SQP**
   para rodar os quatro sobre as mesmas entradas.

### Resultados

- consumo de H₂ (estimado pelo EMS e, sob demanda, validado no modelo dinâmico PEMFC);
- participação de cada fonte na energia entregue (%, kWh, custo, partidas);
- despacho de potência no barramento ao longo do tempo;
- quantidade de stacks ligados e potência por stack;
- metaheurística × refino SQP a cada passo (custo, violação de restrições, ΔP por fonte);
- SOC da bateria ao longo do tempo e SOC final.

A exportação entrega a série temporal em CSV (separador `;` e vírgula
decimal, para abrir direto no Excel em português), com uma linha por minuto.

## Arquitetura

```text
módulos da plataforma ──► ems_integration/ponte.py ──► pacote de troca ──► executor.py
 (PEMFC, bateria, térmica,    caracterização +           carga.csv, fc.csv,     montar_fontes → despacho
  eólica, solar)              alinhamento temporal       bateria.csv, pv.csv,   → relatório
                                                         eolica.csv (renováveis)
                                                         ems_config.json              │
                                                                                      ▼
                                        ems_app.py  ◄── visualization/ems_plots.py ◄──┘
```

| Arquivo | Origem MATLAB |
|---|---|
| `ems_integration/contrato.py` | `contrato_fonte.m` |
| `ems_integration/fontes.py` | `montar_fontes.m`, `ler_serie_csv.m`, `carregar_pv.m` |
| `ems_integration/despacho.py` | `despacho.m`, `custo_despacho.m`, `restricoes_despacho.m`, `candidatos_config.m`, `idx_despacho.m`, `relatorio_despacho.m` |
| `ems_integration/metaheuristicas.py` | `gwo.m`, `NGO.m`, `executar_ga.m` |
| `ems_integration/ponte.py` | novo: plataforma → pacote de troca |
| `ems_integration/executor.py` | `main.m` + validação dinâmica (nova) |

Os CSVs do pacote seguem **os mesmos esquemas** que o `montar_fontes.m` lia,
que são exatamente as colunas exportadas pelos módulos da plataforma.

## Caracterização automática

O EMS não recebe um modelo de FC ou de bateria. Ele deriva envelope, rampa,
curva kg H₂/kWh, Rint e eficiências **do que observa na série**. Isso impõe
dois requisitos: a série precisa cobrir a missão inteira e varrer a faixa de
operação.

- **PEMFC**: uma escada de 10–100 % da potência líquida máxima (50 kW),
  mantida por 2 min em cada nível, com saltos 20→100 % e 100→10 % para que a
  rampa-limite do modelo apareça. A escada não passa do máximo físico:
  pedir mais leva o modelo a `FAULT_LIMITED`, que o EMS lê como
  indisponibilidade.
- **Bateria**: degraus de corrente de ±25/50/100 % das taxas C escolhidas, com
  carga e descarga compensadas (Ah líquido ≈ 0). A calibração de Rint exige
  corrente variando nos dois sentidos.
- **Térmica**: pedido constante no Pmax. O `contractual_target` resultante é
  lido como teto disponível. CVU, mínimo técnico e rampa vêm da
  `ThermalConfig`.

Séries mais longas que a missão (térmica, eólica, solar) são, por padrão,
cortadas no mesmo horário do dia em que a missão começa. O `montar_fontes.m`
original lia cada série a partir do seu próprio início, ou seja, da meia-noite.

## Diferenças em relação ao EMS MATLAB

Nenhuma das diferenças abaixo muda o problema otimizado. Algumas corrigem
defeitos; as mudanças de comportamento são opcionais ou vêm documentadas.

1. **Bateria como descarga + carga separadas** (`P = P_desc + P_carga`). Todas
   as restrições ficam lineares e o SQP passa de ~46 s para ~1,5 s em 2 h de
   missão, com zero passos inviáveis. No ótimo, as duas formulações coincidem:
   carga e descarga simultâneas só somam perdas e degradação. O despacho mede
   e reporta qualquer simultaneidade.
2. **Caixa da metaheurística**: o `despacho.m` limitava as folgas de
   déficit/excesso a 1000 × S_base, o que faz a população ser sorteada longe
   de qualquer ponto balanceado. Aqui o déficit é limitado à carga e o
   excesso à geração máxima; o SQP continua com as folgas ilimitadas. Isso
   eliminou déficits espúrios nos testes.
3. **Custo do H₂ no custo total**: o `despacho.m` somava `c_var_rs_kWh`, que é
   zero quando a fonte declara `custo_fn`, como a FC. Corrigido.
4. **Térmica sem rampa observada** recebia rampa 0, o que a travava no
   primeiro valor. **Térmica sem energia entregue** recebia custo 0, ou seja,
   ficava gratuita. Agora usa os parâmetros da `ThermalConfig`.
5. **Base do envelope da FC**: o original usava `P_stack_kW` (bruta, ~65 kW),
   mas o balanço soma potência líquida (50 kW), o que superestima a FC em
   ~30 %. O padrão agora é a potência **entregue**; a opção "Potência do
   stack" reproduz o original.
6. **Capacidade da bateria** vem do banco Ns × Np da plataforma, e não mais dos
   200 kWh fixos da arquitetura.
7. **Eólica não despachável.** No original ela era uma fonte com curtailment
   contínuo decidido pelo otimizador; agora é descontada da carga como a solar.
8. **SQP**: `fmincon('sqp')` → `scipy SLSQP`. Mapeamento de convergência:
   SLSQP 0 ≈ exitflag 1, SLSQP 8 ≈ exitflag 2 (ambos aceitos), SLSQP 9 ≈
   exitflag 0 (não aceito). A tolerância de viabilidade é a mesma (1e-6).
9. **GA** é aproximado: mesma configuração do `ga` do MATLAB (população 15,
   20 gerações, 5 elites, cruzamento 0,8), mas com operadores próprios. GWO e
   NGO são transcrições diretas.
10. **Opcional, desligado por padrão**: metaheurística com penalidade exata de
   restrições. Na formulação original ela minimiza só o custo e serve de
   ponto inicial.

## Achados que afetam a interpretação dos resultados

- **O refino SQP domina a solução.** No cenário walk-forward Ideal × Normal
  12h (4 stacks + 200 kWh + térmica 80 kW), GA, GWO, NGO e SQP puro chegaram
  a custos entre R$ 449,02 e R$ 449,26. A metaheurística muda principalmente
  o tempo e o ponto de partida.
- **Na formulação original, a solução da metaheurística é inviável** em
  praticamente todos os passos (violação mediana de ~100 kW no balanço): ela
  acha pontos baratos porque não enxerga as restrições. A aba
  "Metaheurística × refino" mostra isso passo a passo.
- **O horizonte N = 3 é míope para custo de partida.** Com uma térmica de
  partida R$ 50, o EMS a desliga no 1º minuto (a bateria é mais barata nesse
  instante) e nunca a religa. Com N = 8, ela fica ligada; no mesmo cenário, o
  custo cai de R$ 458 para R$ 316 e o H₂ de 18,3 para 6,1 kg.
- **A curva estática do EMS acompanha bem o modelo dinâmico**: 18,27 kg
  estimados contra 18,02 kg no modelo dinâmico PEMFC (−1,4 %), com 4 stacks.

## Parâmetros que continuam sendo placeholders

Vêm do `parametros_economicos.m` original e são editáveis na interface:
preço do H₂ (R$ 25/kg), degradação da bateria (R$ 0,08/kWh), penalidade de
déficit (R$ 50/kWh) e penalidade de vertimento (R$ 0,5/kWh). O resultado
econômico só vale o que esses números valerem.

## Desempenho (2 h, passos de 1 min, N = 3)

| Etapa | Tempo típico |
|---|---|
| Caracterização PEMFC (cacheada) | ~9 s |
| Despacho FC + bateria | ~4 s |
| Despacho FC + bateria + térmica | ~8 s |
| Validação dinâmica (sob demanda) | ~15–20 s por stack |

A validação é lenta porque o modelo dinâmico PEMFC da plataforma processa
cada passo interno com operações pandas. O passo interno de 10 s dá H₂ a
0,1 % do resultado com 2 s.

## Testes

```bash
python -m unittest tests.test_ems_integration -v
```

Os testes cobrem leitura/interpolação de séries, desconto das renováveis, vizinhança de
configurações, restrições e gradiente, atendimento da carga com os quatro
algoritmos, efeito da penalidade na metaheurística, o pipeline real com os
modelos da plataforma e a execução completa pela interface.
