# Piso 3D-A2-R — FV e eólica no EMS V2 (MILP–MPC hierárquico)

**Estado:** implementado e validado localmente na rama `claude/adoring-newton-jzfmfx` desde `main` `7eb29e5` (merge do
PR #21). PR **sem merge**. Só o módulo **R** (renováveis) do Piso 3D-A2 foi autorizado; **3D-A2-H** (PEMFC/H₂),
**3D-A2-T** (térmica) e **3D-B** (dashboard) NÃO foram iniciados.

**Contexto científico:** simulação OFFLINE de ensaio, em laço fechado e algébrica. Não é controle de equipamentos nem
validação física. Dados de teste sintéticos, sempre rotulados.

## 1. O que muda para o responsável

Uma microrrede do Gestor com **usina FV, aerogerador(es), bateria(s) e PCC** pode executar uma missão do EMS V2. Os
equipamentos são os do inventário salvo; o potencial renovável vem dos **modelos físicos existentes** do SEEDS2 aplicados
ao clima previsto do cenário. A rodada mostra como a carga foi atendida e persiste, **por UID e por intervalo**:

- a potência disponível;
- a potência aproveitada;
- a potência vertida;
- a energia acumulada.

A reabertura **não reexecuta** modelo físico nem otimizador.

Continua igual:

- missões só com bateria + PCC (rodadas 3D-A legíveis);
- V1.6 intacto e motor por omissão;
- `ems_v2/` byte a byte o da base (árvore `58cc13b6de0abff0f0cff824d469f2fb3f4ed3d7`);
- modelos físicos intocados.

## 2. Arquitetura dos adaptadores

```
inventário (revisão do cenário) ─┐
previsão climática (Piso 2B) ────┼─▶ renovaveis.alinhar_clima ─▶ derivar_fv / derivar_eolica ─▶ Derivacao por UID
estratégia (formato 2) ──────────┘        (instantes exatos)        (modelos REAIS do código)      (K médias, kW)
                                                                                                        │
            ┌──────────── previsão (provedor de tabela; base "antes_da_disponibilidade") ◀─────────────┤
            │                                                                                           │
 ponte 3C-0 (PotencialRenovavel) ─▶ MILP 3C-4 (P_R ≤ a·A; vertimento = a·A − P_R) ─▶ planta 3C-3 ◀─ realização (separada)
                                                       │
                                  registros selados ─▶ vistas v2 + v2/renovaveis.json (comprometido no manifesto)
```

| Arquivo | Papel |
|---|---|
| `integracao_v2/renovaveis.py` (novo) | Adaptador: clima → subamostras; FV **por arranjo** (`arr-…`) com `simulation.multimodel.simulate_noct_efficiency_model`; eólica **por registro** (`eq-…`) com `models.wind_model.run_wind_model`. Média aritmética exata (`math.fsum`) das subamostras por intervalo. Hipóteses e diagnóstico por recurso. |
| `integracao_v2/estrategia.py` | Bloco `milp_mpc` **formato 2** (o formato 1 do 3D-A continua legível): `clima {semantica, emissao_utc}` e `renovaveis {eq-…: {tecnologia, eta_conversao_barramento \| hipotese_densidade, custo_curtailment_R_kWh, procedencia}}`. Nenhum valor científico padrão. Termo opcional `curtailment_operacional`. |
| `integracao_v2/preflight.py` | Classificação POR UID (FV/eólica representáveis quando completas), derivação, causalidade, bloqueios legíveis, previsão × realização separadas, matriz de rastreabilidade. |
| `integracao_v2/montagem.py` | `c_curt` declarado → inventário efetivo; `bases` do provedor; políticas fixas atualizadas. |
| `integracao_v2/registro.py` | Contrato `seeds2-milp-mpc-run-data` **v2** (v1 legível); colunas por UID; `v2/renovaveis.json`; verificação na reabertura. |
| `integracao_v2/execucao.py` | Grava `v2/renovaveis.json` (concluída) ou o anexa à evidência PARCIAL (interrompida). A impressão científica cobre os modelos e catálogos usados. |
| `integracao_v2/ui.py` | Etapa 03: clima + declarações por renovável (vazias). Rodada: tabela por UID e figura disponível × aproveitado × vertido. |

Nenhuma fórmula do núcleo foi alterada: o MILP 3B-P/3C-x já tinha `PotencialRenovavel`, P_R ≤ a·A e vertimento. O
executor 3C-3 já tinha `limitada_pela_disponibilidade`, e as auditorias já tinham `renovavel_acima_do_observado`.

## 3. Parâmetros, transformações e procedência

| Grandeza | Fonte | Transformação | Hipótese registrada |
|---|---|---|---|
| Módulo FV (P_nom, área, η_STC, NOCT, γ_Pmax) | `config/pv_database.py` (catálogo) via `inventory.arrays[].reference` | nenhuma | ficha do catálogo |
| N_s, N_p, sujeira | inventário (`arrays[]`) | sujeira % → fração | sujeira **declarada** (padrão de 0 % do Piso 1 ⇒ BLOQUEIO) |
| GHI, T_amb | previsão climática do cenário (blob SHA-256) | UTC pelo fuso declarado; sem reamostragem | GHI = irradiância no plano do módulo (convenção do V1.6, sem transposição) |
| Potência FV no barramento | `simulate_noct_efficiency_model` | P̄_k = η · (1/n) Σ_j P_CC,j / 1000 | η **declarado** (o modelo não representa inversor/MPPT) |
| Aerogerador (curva, cortes, limite, ρ_ref) | `config/wind_turbine_database.py` via `params.reference` | nenhuma | curva = potência nos terminais do gerador |
| Quantidade, perda genérica | inventário (`count`, `apply_grid_loss`) | n × curva; (1 − 0,03) só se a opção estiver ativa | sem esteira; perda NUNCA aplicada duas vezes |
| Vento, T, p, UR | previsão climática | — | vento = velocidade no cubo (o modelo não aplica cisalhamento) |
| Densidade do ar | modelo eólico | `calculada_do_clima_previsto` (exige T e p; recaída no ar padrão ⇒ BLOQUEIO) × `referencia_do_catalogo` (declarada) | declarada na estratégia |
| Potência eólica no barramento | `run_wind_model` (`power_net_kw`) | P̄_k = (1/n) Σ_j P_j | — |
| Disponibilidade a | estado estático do cenário | série a = 1 (arranjos herdam da usina) | indisponível ⇒ excluído só da missão |
| c_curt | estratégia (só com o termo no objetivo) | por arranjo (da usina) / por registro | procedência por campo |

Toda série de potencial tem:

- procedência com o SHA-256 da série climática;
- a regra de agregação usada;
- a primeira hipótese do recurso;
- o instante de emissão DECLARADO da previsão climática.

## 4. Semântica temporal e causalidade

- O potencial entra no contrato como **média de intervalo** (kW), alinhado à malha UTC da missão.
- O clima é usado nos **instantes exatos** da série gravada. O passo da série precisa dividir Δ, e todas as n
  subamostras de cada intervalo precisam existir com passo uniforme.
- Não há interpolação, deslocamento nem preenchimento. Valor ausente ⇒ bloqueio `clima_insuficiente`.
- A semântica do clima é DECLARADA:
  - `media_intervalo`: aplicar o modelo à média é uma aproximação declarada (não linear);
  - `amostra_instantanea`: retângulo à esquerda.
  - Com uma subamostra por intervalo, o preflight adverte.
- Emissão da previsão climática depois de τ₀ ⇒ bloqueio `previsao_nao_causal`.
- Previsão e realização são objetos e fontes separados. A realização renovável DECLARADA é **igual ao potencial previsto**
  (mesmo modelo, mesmo clima: sem erro de previsão renovável). A separação estrutural é verificada pela ponte e pelo MPC.
- A ausência de antecipação foi demonstrada por intervenção (§7, caso 7).

## 5. Preflight V2

**Representável:**

- usina FV com arranjos em modo `modulo`, módulo do catálogo, N_s/N_p e sujeira declarados;
- registro eólico com curva habilitada para energia (`legacy` ou `restricted_domain`), quantidade e opção de perda;
- declarações da estratégia completas.

**Bloqueia, com mensagem que nomeia o equipamento e a causa:**

| Situação | Código |
|---|---|
| Clima ausente | mensagem «Previsão CLIMÁTICA ausente» |
| Passo que não divide Δ, cobertura incompleta, lacuna ou valor negativo | `clima_insuficiente` |
| Emissão futura | `previsao_nao_causal` |
| Arranjo «potência declarada» (sem módulo) | `renovavel_nao_derivavel` |
| Sujeira padrão | `renovavel_nao_derivavel` |
| Curva `curve_analysis_only` | `renovavel_nao_derivavel` |
| Vento fora do domínio documentado | `renovavel_nao_derivavel` |
| Curva legada além do último ponto, sem corte documentado (extrapolação) | `renovavel_nao_derivavel` |
| Densidade calculada sem T/p | `clima_insuficiente` |
| Declaração ausente | `nao_declarado` |
| Bloco formato 1 com renováveis participantes | pendência `renovaveis` |

Missões só com bateria e PCC continuam aptas. Renováveis declaradas indisponíveis são excluídas e o clima deixa de ser
exigido.

## 6. Persistência: contrato `seeds2-milp-mpc-run-data` v2 (o que o 3D-B consome)

Versões **1** (Piso 3D-A) e **2** são legíveis. Sem renováveis, as vistas e o resumo v2 são idênticos aos v1. Isso está
demonstrado reabrindo uma rodada gravada no formato v1 (`test_caso9_rodada_no_contrato_v1_do_3da_continua_legivel`).

### Fonte canônica e vistas

Os nomes da fonte canônica e das vistas são os do 3D-A:

- `v2/registros_selados.zip`, `v2/modelo.json`, `v2/indice.json`;
- `v2/{intervalos,fronteiras,janelas,planos}.csv`, `v2/coordenacoes.json`, `v2/auditoria.json`, `v2/preflight.json`.

Novo, só quando o modelo tem renováveis: **`v2/renovaveis.json`**.

### `v2/renovaveis.json`

Estrutura:

```json
{"formato": "seeds2-milp-mpc-renovaveis", "versao": 1,
 "clima": {"sha256_serie_normalizada", "sha256_arquivo_original", "procedencia", "fuso_da_serie", "passo_s",
           "subamostras_por_intervalo", "variaveis_usadas", "semantica_declarada", "emissao_declarada_utc",
           "regra_agregacao", "primeira_subamostra_utc", "ultima_subamostra_utc"},
 "base_potencial": "antes_da_disponibilidade",
 "realizacao": {"tipo": "igual_a_previsao", "descricao"},
 "recursos": [{"uid", "registro", "tecnologia", "nome", "modelo", "rotulo_modelo", "parametros", "hipoteses",
               "potencial_kW": [K], "energia_potencial_kWh", "pico_kW", "diagnostico"}]}
```

Regras:

- o SHA-256 do documento é comprometido em `manifest.engine_inputs.hashes.renovaveis` ANTES da execução;
- `parametros` traz, para FV, módulo, fabricante, N_s, N_p, sujeira, η e P_STC; para eólica, aerogerador, quantidade,
  cortes, domínio, densidade e perda;
- `diagnostico` traz, para FV, a temperatura de célula máxima; para eólica, as contagens de densidade e as horas abaixo
  do cut-in e acima do cut-out.

### `v2/intervalos.csv` — colunas novas por UID renovável (`<uid>|…`)

| Coluna | Unidade | Origem | Significado |
|---|---|---|---|
| `A_prevista_kW` | kW | selada | a·A previsto disponível NA DECISÃO da janela |
| `A_observada_kW` | kW | selada | potencial REALIZADO observado (livro K6), antes da disponibilidade |
| `disponibilidade_observada` | 1 | selada | a observado |
| `A_utilizavel_kW` | kW | derivada | a × A observado |
| `P_R_kW` | kW | selada | injeção APLICADA (≤ a·A) |
| `vertimento_kW` | kW | derivada | a·A − P_R |
| `E_aproveitada_acum_kWh` | kWh | derivada | Σ P_R·Δ até o fim do intervalo |

`residuo_balanco_kW` passa a incluir Σ P_R.

### Demais vistas e resumo

- `v2/planos.csv` ganha `plano:<uid>|A_prevista_kW`. As consignas `plano:<uid>|P_R` já existiam.
- `run.summary.mission.renovaveis[<uid>]` traz `tecnologia`, `energia_potencial_observada_kWh`, `energia_utilizavel_kWh`,
  `energia_aproveitada_kWh`, `energia_vertida_kWh` e `pico_aproveitado_kW`. Esses valores são conferidos contra os
  indicadores SELADOS `E_renovavel_usada_kWh` e `E_curtailment_kWh`.

### Verificação na reabertura (`registro.verificar`, sem modelos nem solver)

Além das verificações do 3D-A:

1. presença coerente com o modelo;
2. SHA-256 = manifesto;
3. recursos = UIDs do modelo selado;
4. potencial PREVISTO entregue a cada janela = série gravada, **bit a bit**;
5. potencial REALIZADO observado em cada intervalo = série gravada, **bit a bit**.

## 7. Casos demonstrados

Todos são sobre microrredes do catálogo, usam os modelos reais e têm oráculos independentes reescritos no teste.

| # | Caso | Teste | Evidência |
|---|---|---|---|
| 1 | FV variável coerente com o clima | `test_caso1_*` | A = oráculo NOCT (rtol 1e-12); zero à noite; P_R ≤ a·A |
| 2 | Eólica com curva válida | `test_caso2_*` | A = curva do catálogo (atol 1e-12); zero abaixo do cut-in |
| 3 | Híbrida FV + eólica + bateria + PCC | `test_caso3_*` | concluída; v2 + `renovaveis.json`; verificação aprovada |
| 4 | Potencial > carga | `test_caso4_*` | vertimento > 0 nos intervalos excedentes; banco carrega até 20 kWh; P_c ≤ 5, P_d ≤ 10; importação 0 |
| 5 | Baixa disponibilidade | `test_caso5_*` | renovável + bateria + rede = 40 kW; bateria na ponta tarifária |
| 6 | Integridade por UID e conservação | `test_caso6_*` | resíduo < 1e-6; realizado = derivado bit a bit; balanço de energia exato |
| 7 | Previsão × realização, não antecipação | `test_caso7_*` | realização eólica reduzida a partir de k = 8 ⇒ aplicados idênticos em k < 8; previsões idênticas |
| 8 | Reabertura sem modelos | `test_caso8_*` | modelos FV/eólico, adaptadores, runner, preflight e Pyomo/HiGHS sabotados ⇒ verificação aprovada; adulteração detectada |
| 9 | Compatibilidade | `test_caso9_*` | rodada v1 (3D-A) legível; híbrida isolada sem PCC; V1.6 recusa cenário V2 |
| 10 | Arquivo Científico | `test_caso10_*` | estudo importado em outra instalação, consultado sem modelos |
| — | Interrompida | `test_missao_isolada_interrompida_*` | estado `interrompida` no intervalo 6, evidência parcial com a derivação |

### Caso híbrido de referência (fixture sintética; 12 h, Δ = 60 min, N = 3, H_L = 10)

- **Demanda:** 40 kW.
- **Banco:** 20 kWh, com SOC inicial de 50 %.
- **PCC:** só importação, limite de 50 kW, tarifa 0,5 R$/kWh com pico de 1,5 nas horas 8–9.
- **Vento:** 2–3 m/s nos intervalos 0–1, 9–12 m/s nos intervalos 2–7 e 2–4 m/s nos intervalos 8–11.

| Fonte | Utilizável [kWh] | Aproveitada [kWh] | Vertida [kWh] |
|---|---:|---:|---:|
| FV (1 arranjo, 20 × CS6K-275P, η = 1) | 18,098 | 15,757 | 2,340 |
| Eólica (Vergnet GEV MP C 275 kW) | 1315,000 | 263,000 | 1052,000 |
| Bateria (descarga − carga) | — | 30,000 − 20,000 | — |
| Importação | — | 191,243 | — |

Fechamento do balanço:

- demanda de 480 kWh = 15,757 + 263,000 + 10,000 + 191,243 kWh;
- custo realizado R$ 146,35 (importação R$ 145,85 + throughput R$ 0,50), sem valor futuro.

O banco descarrega no intervalo 0, recarrega com excedente renovável nos intervalos 2–6 e descarrega na ponta (8–9).

### Navegador real (`tools/e2e/run_piso3da2r.sh`)

43 verificações, exit 0. Registros em `docs/ems_v2/evidencia_3da2r/`.

| Fase | Verificações | O que cobre |
|---|---:|---|
| operar | 22 | preflight com potencial derivado, missão, rodada, recarga, exportação |
| reinício do servidor | 6 | rodada reaberta com o mesmo custo |
| tablet | 7 | rodada em tablet retrato |
| importar | 8 | instalação limpa sem solver, motores e MODELOS sabotados; registro de chamadas VAZIO |

## 8. Decisões e contradições registradas

- **C-3DA2R-01 — exceção nominal de guardas** (`tests/ems_v2/piso3da2r_guard_policy.py`). Mesmo mecanismo da C-3DA-01:
  nomes e status exatos, encadeada por `piso3da_guard_policy` (única modificação de guarda). Nenhuma guarda global foi
  removida. A auditoria explícita do diff está em `python tests/ems_v2/piso3da2r_guard_policy.py`.
- **C-3DA2R-02 — fronteira FV → barramento.** O modelo NOCT entrega potência CC do arranjo, e o inventário não tem
  inversor. A conversão é o η DECLARADO na estratégia (sem padrão).
- **C-3DA2R-03 — vertimento sem custo** quando o termo `curtailment_operacional` não está no objetivo. Isso é decisão do
  modelo econômico declarado, não física. Com o termo, c_curt é exigido por recurso.
- **C-3DA2R-04 — realização renovável = previsão.** Não existe no cenário fonte de clima REALIZADO (o slot `resources` do
  Piso 2B é reservado e não editável). Nenhum erro de previsão renovável é inventado. A intervenção sobre a realização é
  demonstrada no nível de teste (caso 7).
- **C-3DA2R-05 — formato 2 da estratégia** e **C-3DA2R-06 — contrato de dados v2**: ambos ADITIVOS, com o formato 1 e a
  versão 1 legíveis.
- **C-3DA2R-07 — densidade do ar.** O modelo eólico recai silenciosamente no ar padrão para T/p ausentes ou absurdos. A
  integração exige a hipótese declarada e BLOQUEIA a recaída quando a densidade foi declarada «calculada».
- **C-3DA2R-08 — curvas legadas.** `np.interp` mantém o último ponto além do domínio. O preflight bloqueia a extrapolação
  sem corte documentado. O modelo não foi alterado.

## 9. Limitações remanescentes

- **Clima:** uma única série climática por cenário, comum a todos os arranjos e aerogeradores (sem clima por local).
- **FV:** GHI como irradiância no plano; sem sombreamento, degradação, mismatch nem limite de inversor.
- **Eólica:** vento no cubo, sem cisalhamento; sem efeito esteira.
- **Agregação no tempo:** aplicar o modelo à média do clima é uma aproximação declarada.
- **Realização:** sem erro de previsão renovável (C-3DA2R-04).
- **Escala da missão:** até 2 bancos; demanda agregada crítica; PCC declarado; ≤ 336 intervalos.
- **Equipamentos bloqueados:** PEMFC e térmica continuam BLOQUEADAS (§10, §11).
- **Relatórios:** os relatórios PDF/Excel/figuras do 2D-B continuam recusando rodadas V2.
- **Execução:** síncrona por janela no servidor.

## 10. Matriz preparatória — PEMFC/H₂ (Piso 3D-A2-H, NÃO implementado)

Três coisas distintas, que não podem ser confundidas:

- **(a) certificação matemática** da curva q(P) para o MILP — porta B04: construção sobre a rama estacionária, pontos de
  ajuste × validação, erro e subestimação, com limiares APROVADOS ANTES de avaliar os dados;
- **(b) validação do modelo aproximado** — Model Card do Horizon: «modelo físico parametrizado aproximado, … sem validação
  específica no equipamento do Boto H₂»;
- **(c) validação física** do equipamento da embarcação. Inexistente hoje.

| Exigência do contrato V2 | Campo (`ems_v2`) | Fonte hoje | Situação | Porta |
|---|---|---|---|---|
| P_max líquida por unidade | `EspecGerador.p_max_kW` | `references.pemfc_max_net_power_kW()` (modelo dinâmico de referência, ≈ 50 kW na rama 0–450 A) | derivável; aproximado | (b) |
| P_min técnica | `EspecGerador.p_min_kW` | inexistente no inventário (o V1.6 identifica, não declara) | AUSENTE | declaração do responsável |
| Curva q_H₂(P_líq) | `CurvaPWL` (M14–M16) | `ṁ = N·I·M/(2F·U)` + `P_net(I)` do modelo aproximado | derivável por varredura de I; NÃO certificada | (a) B04 + (b) |
| Variante de custo | `PoliticaObjetivo.variante_combustivel` (B05) | — | só `instantanea` no perfil 3B-P; multimodo M20 pendente | decisão |
| Preço do H₂ | `EspecGerador.preco_h2` (R$/kg) | inexistente | AUSENTE | declaração econômica |
| Rampas R⁺/R⁻ [kW/min] | `compromisso` por unidade `eq-…#k` | Model Card: 2 kW/s subida, 3,5 kW/s descida (dinâmica aproximada) | derivável; aproximado | (b) |
| Partida/parada (S, eventos, custo) | `compromisso` (limites `declarados` × `rampa_convencional`, custo R$/evento) | estados OFF/STARTUP/IDLE/RUN/SHUTDOWN do modelo dinâmico, sem durações certificadas | parcial | (b) + D05 |
| Permanência mínima ON/OFF T_on/T_off | `compromisso` | inexistente | AUSENTE | declaração |
| Estado inicial e memória por unidade | `EstadoGerador`, memória 3C-1 | cenário Piso 2A (estado operacional) sem tempo no estado | parcial | declaração |
| Quantidade disponível de H₂ | — (não modelado no núcleo) | inexistente | fora do contrato atual | extensão futura autorizada |
| Abstração de transição | `instantanea_unidade_quente` × `transicoes_bloqueadas` | — | declarar | decisão |

O caso completo FV + eólica + bateria + PEMFC + PCC exige, nesta ordem:

1. aprovar os limiares B04;
2. construir e certificar q(P) sobre o modelo aproximado com hash e versão;
3. declarar P_min, preço, permanências, abstração de transição e estado inicial;
4. resolver a decisão D05 de partida.

Nada disso foi implementado nem afirmado neste PR.

## 11. Térmica (Piso 3D-A2-T) — lacuna M19

A especificação vigente define:

```
Ċ_g,t = c^E_g,t · p_g,t + c^on_g · u_g,t   [R$/h]   (M19)
```

No catálogo de termos, `geracao_termica` está como **«futuro»** (`ems_v2/contracts.py: TERMOS_OBJETIVO`). Nenhum perfil
de formulação (3B-P, 3C-1, 3C-3, 3C-4) inclui o termo. Por isso uma térmica despachável entraria **sem custo de
combustível**, e o preflight continua BLOQUEANDO.

A extensão necessária é uma mudança de FORMULAÇÃO. Exige autorização específica e PR separado, e inclui:

- o termo no perfil;
- os coeficientes declarados: c^E [R$/kWh] a partir do CVU do inventário (`cvu_rs_MWh` / 1000) e c^on;
- a construção no MILP;
- o auditor independente;
- a contabilidade realizada.

Não introduzir geração térmica gratuita.

## 12. Reprodução

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_piso3da2r_renovaveis.py tests/test_piso3da2r_execucao.py tests/test_piso3da2r_app.py tests/ems_v2/test_piso3da2r_guardas.py -q -p no:cacheprovider
```

```bash
python tests/ems_v2/piso3da2r_guard_policy.py
```

```bash
bash tools/e2e/run_piso3da2r.sh <python com Pyomo/HiGHS> <python sem solver> <pasta vazia>
```
