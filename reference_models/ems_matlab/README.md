# EMS Híbrido H2/Bateria/PV — versão modular

Reorganização do `main_hibrido.m` original (577 linhas) em módulos, sem alterar
a física/otimização já validada. `main.m` caiu para ~75 linhas e só orquestra.

## Estrutura

```
main.m                          <- único arquivo que você edita para trocar de cenário/algoritmo

config/
  config_cenario.m              <- 1 struct por aplicação (perfil de carga, PV, algoritmo NMPC...)

arquitetura/
  arquitetura_embarcacao_h2.m   <- parâmetros físicos (FC, bateria, PV, conversores) + EMS (modos/pesos)
  montar_equipamentos.m         <- traduz arch -> structs fc/bat/conv/nmpc; aplica limite V×I do conversor
  validar_arch.m                <- checagem de sanidade antes de rodar

carga/
  carregar_perfil_carga.m       <- ponto único de entrada da carga (despacha por tipo)
  carregar_perfil_csv.m         <- loader genérico (qualquer CSV com t_min/P_kW)
  preparar_carga_artigo.m       <- loader específico do artigo Zhang et al. (.mat digitalizado)
  processar_carga.m             <- classificação (propulsão/hotel/aux) + contingência + perdas

fontes/
  carregar_fonte_csv.m          <- loader genérico p/ qualquer fonte pré-calculada
  carregar_pv.m                 <- PV (usa o genérico + satura na potência nominal)

fisica/
  bateria_step.m                <- ÚNICA fonte da dinâmica da bateria (corrente, SOC, V terminal)
  fc_efficiency.m                <- interpola eta_fc(P)
  carregar_curva_eficiencia_fc.m <- tabela digitalizada OU modelo analítico (Eq.2 Jiang et al.)
  Dbat_eq14.m / battery_h2_equiv.m

otimizacao/
  ems_dispatch.m                <- o loop NMPC (era ~150 linhas dentro do main)
  cost_function_hibrido.m
  constraints_hibrido.m         <- inclui limite de tensão terminal da bateria
  pesos_por_modo.m / classificar_modo_simples.m
  executar_ga.m / gwo.m / NGO.m <- metaheurísticas (inalteradas)

pos_processamento/
  calcular_indicadores.m
  imprimir_balanco.m
  gerar_graficos.m
  gerar_tabela_resultados.m

utils/
  getfield_default.m / nome_algoritmo.m
```

## Como trocar só o perfil de carga (nova aplicação)

1. Abra `config/config_cenario.m`.
2. Copie o bloco `case 'exemplo_csv_generico'` e ajuste:
   - `cenario.perfil.arquivo` → seu CSV, com colunas `t_min`/`tempo` e `P_kW`/`potencia`
     (opcionalmente `Pfc_req` se você tiver uma curva de referência de FC).
   - `cenario.pv_csv` → seu CSV de PV.
3. Mude `NOME_CENARIO` em `main.m` para o nome do novo `case`.

**Nenhum outro arquivo precisa mudar.** Todo o resto do pipeline só conhece o
contrato `[t_min, P_load_kW, Pfc_req_kW]` — é isso que garante que trocar o
perfil não quebra nada em `ems_dispatch.m`, `cost_function_hibrido.m` etc.

## Como trocar os componentes (embarcação/equipamentos)

1. Copie `arquitetura/arquitetura_embarcacao_h2.m` para `arquitetura_minhaapp.m`
   e ajuste os parâmetros de FC, bateria, PV, conversores e a seção 7 (`arch.ems`:
   modos de operação, pesos do custo por modo, limiares).
2. Em `config_cenario.m`, aponte `cenario.arch_fn = @arquitetura_minhaapp;`.

FC e bateria **continuam sempre como decisão do otimizador** (nunca viram
"input pronto" como o PV) — o que fica plugável são os *parâmetros e curvas*
delas: eficiência da FC (`carregar_curva_eficiencia_fc.m`), física da bateria
(`bateria_step.m`), e limites elétricos (V×I do conversor, em
`montar_equipamentos.m`, opcional via `arch.conv.I_max_fc_A`/`I_max_bat_A`).

## O que foi corrigido/consolidado nesta reorganização

- **Física da bateria estava triplicada** (custo, restrições, loop principal),
  cada uma podendo divergir silenciosamente se uma fosse editada e as outras
  não. Agora vive só em `fisica/bateria_step.m`.
- **Limite de capacidade elétrica do conversor (V×I)** — antes ausente, agora
  em `montar_equipamentos.m` (opcional, não quebra cenários sem esse dado).
- Os campos `arch.ems.*` (modos, pesos, limiares) e `arch.bat.V_min_V/V_max_V`
  não estavam nos arquivos de arquitetura originais enviados — foram
  adicionados como **placeholders explícitos** (comentados como `AJUSTAR`) só
  para o pipeline rodar de ponta a ponta. Ajuste com dados reais/tuning.

## Pendências para você rodar de fato

- Os arquivos de dados (`Modelo_solar_12am.csv`, `layer1_data_artg1.mat`) não
  foram enviados — o código espera eles no path do MATLAB (mesma pasta do
  `main.m` ou em `addpath`).
- Revise os placeholders de `arch.ems.*` e `arch.bat.V_min_V/V_max_V` em
  `arquitetura/arquitetura_embarcacao_h2.m` — marcados com `AJUSTAR`.
