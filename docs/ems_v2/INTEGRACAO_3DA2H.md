# Piso 3D-A2-H — PEMFC/H₂ no EMS V2 (MILP–MPC hierárquico)

Base `main` `0c9df80` (merge do PR #22). Ramo `claude/adoring-newton-jzfmfx`. PR independente contra `main`, **sem merge**.
Térmica (3D-A2-T) e dashboard (3D-B) **não** foram iniciados.

> **Decisão do responsável no PR #23 (2026-11-11):** política B04 `b04-proposta-2` **APROVADA** (commit independente
> `8be5de4`; limiares, identidade e versão inalterados) para a certificação MATEMÁTICA da PWL contra o modelo PEMFC
> existente — **não** é validação experimental do modelo Horizon nem certificação de operação física. Decisões
> C-3DA2H-02 a 05 e 08 a 11 aprovadas com alcance delimitado (§9). Verificações finais: A — massas por evento em malha
> densa (§5a); B — fluxo completo com a política REALMENTE aprovada, sem aprovação simulada (§12). **C-3DA2H-12
> APROVADA** (resíduo das rampas de descida aceito como resíduo quantificado, SEM termo de rampa no MILP; condições em
> §5b). Alcance 3D-A2-H tecnicamente aceito para ENSAIOS reproduzíveis, com as limitações físicas e dinâmicas
> registradas; integração em `main` só com autorização expressa.
>
> **Estado em uma frase.** A integração está implementada e foi demonstrada de ponta a ponta pelo caminho NORMAL: a curva
> q_H₂(P_líq) é derivada do modelo físico, gerada uma vez e reutilizada em toda a missão, passa pela sua própria
> verificação B04 (a aprovação da política não aprova automaticamente nenhuma curva) e a evidência é verificável sem
> modelo nem solver. Auditoria A–D aplicada: massa por evento sem dupla contagem (§5), aceitação algébrica × dinâmica ×
> física separada (§7), autoridade B04 no núcleo (§3) e restrições físicas que bloqueiam (§5–6).

## 1. O que muda para o responsável

- **Cenário V2 com PEMFC.** A estratégia (formato 3) declara, por registro PEMFC:
  - as condições físicas estacionárias: T do stack, p do ânodo, p do cátodo e p ambiente;
  - P_mín, rampa, T_on e T_off;
  - temperatura ambiente;
  - preço do H₂ [R$/kg];
  - custos de partida e de parada (só com o termo `eventos`);
  - abstração da transição e limites (`rampa_convencional`);
  - estado inicial por unidade `eq-…#k`;
  - procedência.

  Todos os campos começam **vazios**. Nada é preenchido pelo sistema.
- **Preflight V2.** Gera a curva do modelo físico e reverifica os valores contra o modelo. Em seguida registra o
  certificado B04 do núcleo, que RECOMPUTA os critérios desta curva. Curva fora dos limiares ⇒ `b04_reprovada`; política
  não aprovada ou revogada ⇒ `b04_aguardando_aprovacao` (testado por revogação simulada). Em ambos os casos o botão
  EXECUTAR fica desabilitado.
- **Rodada.** Mostra por unidade:
  - energia;
  - H₂ previsto pelo EMS e H₂ do modelo dinâmico;
  - custo;
  - consumo específico;
  - partidas e paradas;
  - veredito da verificação dinâmica.

  A composição do atendimento ganha a série «PEMFC <unidade>».
- **Bancada H₂ (`h2_app.py` → Caracterização).** Nova seção «H₂ · Curva de consumo do EMS»:
  - gráfico «Consumo de hidrogênio × potência líquida»: modelo físico × PWL do EMS × vértices × referência
    estequiométrica, com a faixa P_mín–P_máx e hover com a diferença;
  - unidades g/s, kg/s e kg/h;
  - KPIs: P_máx, H₂ a P_máx, consumo específico, erro máximo, vértices e «Certificação B04: Não aprovada»;
  - gráfico do erro com a linha do limiar;
  - tabela de vértices e critérios;
  - downloads CSV/JSON.

  Não há motor JS/SVG novo: o gráfico é Plotly, como o restante da bancada.

## 2. Curva q_H₂(P_líq): geração única e reutilização

**Modelo usado.** O modelo ESTACIONÁRIO existente do SEEDS2 (`h2_pemfc`), perfil `EQUIVALENT_65KW_HORIZON_CONSTRAINED`.
Nenhuma equação foi duplicada (`integracao_v2/curva_h2.py`):

1. Domínio:
   - P_mín é DECLARADO;
   - P_máx = mín(máximo da rama operacional nas condições declaradas, pico do sistema, `p_max_liquida_unidade_kW` do
     inventário).

   Fora de [P_mín, P_máx] não há curva: `q_pwl` recusa e não extrapola. Também não há segmento (0, 0)–P_mín (M14–M16).
2. Avaliação:
   - os extremos usam `solve_requested_power`;
   - o interior é uma grade de corrente avaliada de forma vetorizada com `Equivalent65kWHorizonSystemModel.evaluate`
     (P_net, H₂ suprido, H₂ consumido).

   Exige-se P e q estritamente crescentes; caso contrário, `CurvaInvalida`. A vazão usada é o H₂ **suprido**
   (estequiométrico ÷ utilização), base do custo. O estequiométrico é só referência.
3. PWL:
   - os vértices são pontos do modelo, escolhidos por inserção gulosa do ponto de maior erro relativo;
   - critério de parada: erro ≤ 0,1 % ou 48 vértices;
   - ajuste com 401 pontos.
4. Validação **independente**:
   - 400 pontos que não coincidem com a grade de ajuste (médias de correntes vizinhas e pontos junto às fronteiras);
   - métricas: erro relativo e absoluto máximos, subestimação, erro integral no domínio de potência;
   - **erro de massa no TEMPO**: Σ q·Δt [kg] em 6 perfis temporais de 1 min:
     - cargas parciais de 25/50/75 %;
     - P_máx;
     - degraus de 15 min com semente fixa;
     - despacho senoidal contínuo.

**Identidade (impressão digital SHA-256).** É computada sobre:

- o gerador `curva-h2-pwl-v1` e o SHA-256 do seu código-fonte;
- o SHA-256 dos arquivos de `h2_pemfc/` e o perfil do modelo;
- as condições (T, p_ân, p_cát, p_amb);
- P_mín e o limite de P_máx;
- a política de aproximação, a versão da política B04 e os parâmetros do modelo.

**Reutilização.** Mesma impressão ⇒ mesma instância de `CurvaH2` (cache em memória). O contador `GERACOES` conta gerações,
não consultas.

- Uma missão completa gera **no máximo uma** curva: planejador longo + 12 janelas MPC, teste
  `test_missao_hibrida_…` (`n1 − n0 ≤ 1`).
- Duas microrredes com a mesma configuração física e um novo preflight reutilizam a MESMA curva, com zero gerações novas
  (`test_curva_gerada_uma_vez_…`).
- Em nenhum ponto a curva é regerada por intervalo, janela, potência, ON/OFF ou replanejamento. Ela entra uma única vez
  no `EspecGerador.curva_h2` da entrada da missão.

**Desempenho.** 0,2–0,7 s por curva; a versão inicial com brentq levava 61 s.

**Erro quantitativo na condição nominal** (353,15 K; 140/120 kPag; 101,325 kPa; P_mín = 10 kW):

| Métrica | Valor |
|---|---|
| Domínio | [10, 50] kW, 15 vértices |
| Erro relativo máx. (validação independente) | 0,087 % |
| Erro absoluto máx. | 0,0028 kg/h |
| Subestimação | 0 (PWL por pontos do modelo sobre curva convexa na amostra) |
| Erro de massa no tempo, máx. dos 6 perfis | 0,072 % |
| Erro integral no domínio de potência (métrica de domínio, NÃO massa) | 0,037 % |
| q | 0,6027–3,8383 kg/h |
| Consumo específico | 0,0603–0,0768 kg/kWh |

**Generalização.** A política foi congelada ANTES desta avaliação. Ela foi aplicada a cinco condições físicas não
usadas para escolher os limiares (`CONDICOES_GENERALIZACAO`: 333,15 K; 358,15 K; 160/140 kPag; 120/100 kPag com 95 kPa;
348,15 K com 130/110 kPag e 100 kPa). Todas ficaram conformes: erro relativo ≤ 0,098 %; massa ≤ 0,072 %.

## 3. B04 — três certificações distintas e estado REAL

| | O que é | Estado |
|---|---|---|
| (a) certificação matemática da curva (B04) | a PWL representa o modelo dentro de limiares aprovados ANTES | **política APROVADA** pelo responsável (`b04-proposta-2`, congelada e aprovada em 2026-11-11); cada curva continua sujeita à sua própria verificação |
| (b) validação do modelo aproximado | Model Card do Horizon: modelo parametrizado aproximado, sem validação no equipamento | inalterada; a curva herda a aproximação |
| (c) validação física do equipamento | medições do equipamento real | inexistente |

**Limiares APROVADOS (idênticos aos congelados):**

| Limiar | Valor |
|---|---|
| Erro relativo máximo | 0,5 % |
| Erro absoluto máximo | 0,02 kg/h |
| Subestimação máxima | 0,1 % |
| Erro de massa acumulada no tempo | 0,2 % |
| Pontos de validação | ≥ 200 |

As justificativas foram revisadas: são limiares de **engenharia da aproximação PWL**, não incerteza experimental. A
utilização de H₂ de 97 % NÃO é tratada como ±3 %.

**Correções exigidas pelo responsável (todas implementadas):**

| # | Correção | Onde |
|---|---|---|
| 1 | Massa = ∫ q(P(t)) dt [h]; a integral em potência foi renomeada como métrica de domínio | `curva_h2._perfis_temporais`, `metricas.erro_massa_temporal_rel_max` × `erro_integral_dominio_potencia_rel` |
| 2 | Perfis temporais independentes: parcial, nominal e variáveis; modelo × PWL | 6 perfis; `test_massa_acumulada_integrada_no_tempo_…` |
| 3 | Limiares mantidos, justificativas revisadas | `POLITICA_B04["justificativas"]` |
| 4 | Política congelada e generalização em condições não usadas | `congelada_em`, `avaliar_generalizacao`; `test_generalizacao_…` |
| 5 | Os critérios verificam a curva; certificado adulterado é rejeitado; nenhuma curva é certificada só por rótulo ou hash | `contracts.verificar_certificado_b04` RECOMPUTA tudo; `tests/ems_v2/test_ems_v2_b04_certificado.py` e `test_piso3da2h_curva.py` |

**Mecanismo no núcleo (C-3DA2H-01).**

- `CurvaPWL(classificacao="real_certificada_b04")` só é aceita por `validar_curva` se:
  - existir um `CertificadoB04` **registrado** cuja identidade SHA-256 é a `procedencia.sha256` da curva;
  - os vértices forem idênticos aos do certificado.
- `registrar_certificado_b04` só registra se `verificar_certificado_b04` recomputar, a partir dos pontos de validação e dos
  perfis, erro relativo, erro absoluto, subestimação e massa temporal. Também confere:
  - independência dos pontos de validação em relação aos vértices;
  - domínio;
  - monotonia;
  - a AUTORIDADE da política (auditoria do PR #23, ponto C — abaixo).
- A classificação `real` continua `pendente`.

**Autoridade da política (auditoria do PR #23, C).** O campo `situacao` do certificado NÃO tem autoridade:

- a identidade da política é o SHA-256 do seu CONTEÚDO (versão + limiares + mínimo de pontos, sem `situacao`);
- o núcleo reconhece SÓ as políticas congeladas em `ems_v2.contracts.POLITICAS_B04_NUCLEO`, com a situação fixada no
  código. Hoje há uma: `b04-proposta-2` (`412863021aee…`), situação `aprovada_pelo_responsavel` desde o commit
  `8be5de4` (com `aprovada_em`, `aprovacao` e `alcance` registrados);
- política desconhecida (p. ex. autodeclarada «aprovada» com limiares arbitrários) ⇒ erro `politica_b04_desconhecida`;
  versão conhecida com conteúdo alterado ⇒ `politica_b04_alterada`; situação declarada diferente da do núcleo ⇒
  `politica_b04_situacao_divergente`; conhecida e pendente ⇒ `politica_b04_nao_aprovada` (pendente);
- a verificação quantitativa (pontos independentes e perfis temporais) continua obrigatória mesmo com a política aprovada;
- **aprovar** = mudar a situação dessa entrada para `aprovada_pelo_responsavel` num commit revisado e autorizado (feito em
  `8be5de4`). Os testes usam o caminho normal; a REVOGAÇÃO é simulada só dentro de um teste
  (`tests/piso3da2h_util.politica_pendente_no_teste`) para provar que uma política pendente continua bloqueando.
- A reabertura re-registra o certificado a partir de `v2/pemfc.json`, recomputando os critérios.

## 4. Alteração do núcleo autorizada (C-3DA2H-01) e extensão aprovada (C-3DA2H-02)

**Autorizado pelo responsável:** alteração nominal e aditiva em 4 arquivos:

- `ems_v2/contracts.py`;
- `ems_v2/ponte/projecao.py`, `ems_v2/ponte/compromisso.py` e `ems_v2/ponte/preflight.py`: parâmetro opcional
  `curvas_h2`; ausente ⇒ comportamento idêntico. `sem_curva_declarada` remove só a constatação `curva_h2` ausente dos
  registros declarados.

Regressão do núcleo após a alteração: `tests/ems_v2` com solver, **1519 passed, 2 skipped** (comportamento anterior
intacto).

**Extensão autorizada pelo responsável (C-3DA2H-02).** O parâmetro opcional
`massas_h2_eventos={uid: (m_SU, m_SD)}` em `montar_entrada_3c1` e `preflight_ems_v2`.

- **Por quê:** a adenda B05, já implementada no 3C-1, EXIGE `massa_h2_partida_kg`/`massa_h2_parada_kg` quando uma PEMFC
  transita com o termo `combustivel_h2`. Sem esse transporte, a ponte não tinha como entregá-las.
- **Comportamento:** ausente ⇒ idêntico. Só é usado para PEMFC com abstração `instantanea_unidade_quente` e o termo
  `combustivel_h2`.
- **Origem das massas:** derivadas do modelo dinâmico (§5), nunca inventadas.
- **Sem parâmetros declarados ou modelo compatível:** o bloqueio correspondente é mantido.

## 5. Modelo dinâmico, D05 e coerência das consignas

**Separação.**

- O modelo ESTACIONÁRIO gera a curva do MILP.
- O modelo DINÂMICO (`Equivalent65kWHorizonDynamicModel`) é reutilizado para três fins:
  1. massas ADICIONAIS de partida e parada (B05);
  2. análise transitória A PRIORI, que BLOQUEIA configurações incompatíveis no preflight;
  3. verificação A POSTERIORI das consignas aplicadas.

  A verificação não altera o despacho nem a planta algébrica. IDLE, rampas, durações e o limiar de partida fria são LIDOS
  da configuração do modelo, nunca redigitados.

O modelo dinâmico sempre avalia a resposta estática nas condições PADRÃO. `pemfc_dinamica._PotenciaNasCondicoes` é
apenas um ADAPTADOR (subclasse) que fixa as condições declaradas em cada chamada, sem duplicar equações. As respostas
estáticas já resolvidas são reutilizadas por potência solicitada (idênticas bit a bit às do modelo; só evitam repetir o
brentq).

**D05, resolução conceitual.**

- O MILP usa a abstração DECLARADA `instantanea_unidade_quente` (contexto «ensaio»).
- Ela só é admitida se a análise transitória A PRIORI (pior caso de partida, parada e rampas P_mín ↔ P_máx no domínio,
  no Δ e na T_amb declarados) couber nas tolerâncias; caso contrário o preflight BLOQUEIA (§6).
- As consignas aplicadas são conferidas a posteriori, por intervalo (tolerâncias absolutas como MÉDIAS por unidade de
  tempo, para não afrouxar em Δ curtos; em Δ = 60 min valem 0,5 kWh e 0,02 kg):
  - energia: |E_entregue − E_solicitada| ≤ máx(2 %, 0,5 kW·Δ);
  - H₂: |m_dinâmico − m_EMS| ≤ máx(2 %, 0,02 kg/h·Δ), com m_EMS = q̂(p)·Δ·u + m_SU·y + m_SD·z (a contabilidade do MILP).
- Fora dessas tolerâncias, a consigna é INCOERENTE com a dinâmica e a rodada é classificada como tal (§7). Nunca é
  declarada «fisicamente executável».
- **D05 autorizado SÓ para o contexto «ensaio»** (C-3DA2H-04), condicionado ao preflight dinâmico e à verificação a
  posteriori; não é modelo operacional fisicamente validado. A representação multimodo (M20) continua pendente.

**Massa de H₂ por evento (B05) — auditoria do PR #23, ponto A.** A abstração instantânea JÁ conta q̂(p)·Δ no intervalo
de partida inteiro. Por isso m_SU/m_SD são massas ADICIONAIS, definidas pela integração TEMPORAL do modelo dinâmico:

- δ_SU(p) = ∫ q_din(intervalo com partida em p) dt − ∫ q_din(mesmo intervalo em regime em p) dt;
- δ_SD(p) = ∫ q_din(intervalo após a parada a partir de p) dt − 0 (em regime desligado o consumo é nulo);
- constante por evento: m = máx(0, máx_p δ(p)) numa malha de 9 potências em [P_mín, P_máx].

Resultado nominal (T_amb 25 °C, partida quente de 30 s):

| Evento | δ(p) no domínio | m adotado | Superestimação máx. |
|---|---|---|---|
| Partida | −0,0027 kg (10 kW) … −0,0390 kg (50 kW): sempre NEGATIVO | **0** | 0,039 kg |
| Parada | +0,00015 kg (10 kW) … +0,0064 kg (50 kW) | **0,0064 kg** | 0,0063 kg |

A semântica anterior (m_SU = massa no estado STARTUP ≈ 0,00233 kg) era dupla contagem: o consumo do STARTUP e da rampa até
p já está dentro de ∫ q_din, e mesmo assim ∫ q_din < q̂(p)·Δ. A decomposição exata, verificada nos testes em partida,
parada e permanência ligada (com degraus), é

M_EMS − M_din = (q̂(p) − q(p))·Δ + (m − δ(p)) ≥ 0,

isto é, o erro B04 da PWL (≥ 0, limitado) mais o resíduo do evento (≥ 0, limitado pela superestimação registrada; a
aproximação é CONSERVADORA e identificada como tal). Partida fria (T_amb ≤ 5 °C, 600 s): δ_SU de −0,05 a −0,30 kg e
déficit de energia de 0,8 a 7,6 kWh por partida ⇒ inadmissível com a abstração instantânea (§6).

**§5a. Verificação A (decisão do responsável, item 3A): malha densa e configurações diferentes.** A malha de 9 potências
NÃO prova sozinha que a constante é conservadora entre os pontos. `tests/verificacao_massas_3da2h.py` faz uma verificação
INDEPENDENTE dessa rotina:

- simula intervalos COMPLETOS de Δ = 60 min em sequências longas e contínuas do modelo dinâmico (cada partida a partir
  de OFF, cada parada a partir de RUN estabelecido, cada rampa a partir do regime do intervalo anterior);
- integra com implementação PRÓPRIA (retenção de ordem zero vetorizada);
- compara a massa CONTABILIZADA pelo EMS (q̂·Δ·u + m_SU·y + m_SD·z) com a do modelo dinâmico, numa malha de 0,5 kW
  (partidas e paradas) e de pares a cada 2,5 kW (rampas), em 6 configurações físicas ADMISSÍVEIS (nominal; P_mín 15 kW;
  stack 333 K; stack 358 K com T_amb 6 °C; 120/100 kPa(g) e 95 kPa com P_mín 12 kW; 348 K com T_amb 40 °C).

| Caso (6 configurações; 77–82 partidas, 77–82 paradas, 418–610 rampas por configuração) | Resultado |
|---|---|
| Partidas | **nenhuma subestimação**; resíduo mínimo +0,0027 a +0,0056 kg |
| Paradas | **nenhuma subestimação** (igualdade em P_máx; resíduo ≥ −9·10⁻¹⁹ kg = arredondamento) |
| Rampas de SUBIDA em operação contínua | **nenhuma subestimação** (resíduo ≥ −2·10⁻¹³ kg = arredondamento) |
| Rampas de DESCIDA em operação contínua | **SUBESTIMAÇÃO encontrada**: máximos OBSERVADOS de 0,0034–0,0044 kg por rampa (0,36–0,72 % da massa do intervalo) nos casos ensaiados; pior caso SEMPRE no par P_máx → P_mín |

Conclusões:

- as massas por evento são conservadoras em todas as configurações verificadas (densa), mas **não há garantia GLOBAL de
  não subestimação do H₂ do EMS**;
- a subestimação das rampas de descida NÃO é das massas por evento: em operação contínua o modelo dinâmico, ao descer a
  3,5 kW/s, consome mais do que q̂(p_destino)·Δ, e o MILP não tem termo de rampa para representá-lo. Corrigi-la exigiria
  um termo de rampa na formulação (não autorizado) ou uma constante não derivada do modelo (proibido);
- nos casos ensaiados, o pior caso é exatamente a rampa P_máx → P_mín que a análise a priori do preflight já avalia (o
  teste confere a igualdade entre os dois caminhos, 1e-9) e fica dentro da tolerância dinâmica (0,0044 kg ≤ 0,02 kg em
  Δ = 60 min);
- cada rodada REPORTA a subestimação por unidade (máximo por intervalo e total; documento dinâmico, resumo,
  interface), recalculada na reabertura. Decisão C-3DA2H-12 APROVADA com condições (§5b).

**§5b. Decisão C-3DA2H-12 (APROVADA pelo responsável, alcance experimental).** A subestimação nas rampas de descida é
aceita como RESÍDUO QUANTIFICADO entre a formulação MILP estacionária e a resposta do modelo dinâmico aproximado. NÃO se
acrescenta termo de rampa ao MILP (formulação inalterada). Condições científicas e onde cada uma é garantida:

| # | Condição | Garantia / registro |
|---|---|---|
| 1 | Subestimação visível por INTERVALO, por UNIDADE e ACUMULADA, com verificação de integridade na reabertura | por intervalo: `v2/pemfc_dinamica.json` (`h2_ems_kg` × `h2_modelo_dinamico_kg`); por unidade e acumulada: `h2_subestimacao_max_kg`, `h2_subestimacao_total_kg`, `intervalos_com_subestimacao_h2` (documento dinâmico, resumo e tabela PEMFC da rodada); a reabertura RECALCULA dos intervalos gravados e confere (`registro._pemfc_verificar`) |
| 2 | 0,0044 kg/rampa e 0,72 % NÃO são cotas universais | são máximos OBSERVADOS nos casos e condições ensaiados (6 configurações, Δ = 60 min, malha de 0,5 kW e pares a cada 2,5 kW, §5a) |
| 3 | Classificação independente: algébrica, coerência dinâmica e validação física | `summary.execution.aceitacao` (§7), inalterada |
| 4 | Custos e decisões do MILP NÃO representam exatamente a operação transitória | os custos estimados estão sujeitos ao erro da aproximação documentada: erro B04 da PWL (≥ 0), resíduo dos eventos (≥ 0, conservador) e resíduo das rampas de descida (subestimação limitada) |
| 5 | TCC: considerar a magnitude ECONÔMICA dos resíduos; não afirmar superioridade concluinte quando a diferença entre estratégias couber na incerteza de modelagem | ordem de grandeza no caso híbrido de referência (§8/§12): H₂ do EMS − H₂ dinâmico = +0,0264 kg ≈ R$ 0,26 (0,23 % do custo realizado de R$ 116,02); subestimação acumulada 0,00059 kg ≈ R$ 0,006 (1 intervalo); diferença de energia solicitada − entregue 0,27 kWh. A comparação entre estratégias deve reportar esses resíduos de cada rodada |
| 6 | Discrepância acima das tolerâncias aprovadas ⇒ incoerência marcada e formulação revista antes de usar o resultado como evidência | automática: a rodada é classificada `algebrica_aprovada_dinamica_incoerente`, com alerta «DINAMICAMENTE INCOERENTE» (§7); tal rodada NÃO deve ser usada como evidência científica sem a revisão |
| 7 | A avaliação com Δ = 60 min NÃO se estende automaticamente a outros passos | o preflight avalia a admissibilidade a priori NO Δ declarado (bloqueia o incompatível), mas a verificação densa A só foi feita em Δ = 60 min: para outro Δ, repetir `tests/verificacao_massas_3da2h.py` (parâmetro `delta_s`) antes de usar os resultados como evidência |

Evidência: `docs/ems_v2/evidencia_3da2h/verificacao_massas_eventos.{json,log}`; teste
`tests/test_piso3da2h_verificacao_massas.py` (configuração nominal, malha de 1 kW e pares a cada 5 kW).

**Restrições físicas — auditoria do PR #23, ponto D.** Agora BLOQUEIAM (antes só avisavam):

- P_mín < IDLE do modelo dinâmico (10 kW, hipótese do manual ≤ 10 kW): em RUN uma consigna menor é entregue como IDLE
  (`IDLE_MINIMUM_ENFORCED`) ⇒ excesso de energia e de H₂;
- rampa declarada > 60·mín(subida, descida) = 120 kW/min: a rampa ÚNICA vale nos dois sentidos e o modelo sobe a 2 kW/s;
- transitórios incompatíveis com Δ e T_amb (análise a priori): p. ex. partida fria, ou Δ ≤ 15 min com partida quente.
  Com `transicoes_bloqueadas` só as rampas se aplicam.

**Nada é inventado.** P_mín, T_on/T_off, custos, preço, estados iniciais e condições são DECLARADOS. A rampa única do
inventário vale para subida E descida (interpretação registrada na procedência).

## 6. Preflight V2 com PEMFC (bloqueios legíveis)

**Bloqueios:**

| Código | Situação |
|---|---|
| `b04_aguardando_aprovacao` | política não aprovada; produção atual |
| `b04_reprovada` | critérios recomputados acima dos limiares |
| `pemfc_curva_invalida` | condições recusadas pelo modelo; P_mín ≥ P_máx; P_mín antes da rama |
| `pemfc_curva_divergente_do_modelo` | reverificação contra o modelo falhou |
| `pemfc_perfil_nao_suportado` | perfil de modelo diferente do suportado |
| `pemfc_pmin_abaixo_do_idle` | P_mín declarado < IDLE do modelo dinâmico (auditoria PR #23, D) |
| `pemfc_rampa_acima_do_modelo_dinamico` | rampa declarada > capacidade do modelo dinâmico nos dois sentidos (D) |
| `pemfc_transitorio_incompativel` | partida/parada/rampa a priori fora das tolerâncias no Δ e na T_amb declarados (D) |

**Outras regras:**

- Declaração ausente ou formato < 3 com PEMFC participante ⇒ `pendente` na estratégia (bloqueia).
- PEMFC indisponível ⇒ excluída só da rodada. Os termos `combustivel_h2`/`eventos` sem recurso caem com INFO.
- Térmica: continua BLOQUEADA (M19).
- Disponibilidade por unidade: `FonteDisponibilidadeExecucao` estática declarada `a = 1` e série `<uid>:disponibilidade` na
  previsão e na realização. Não há disponibilidade 1 «por omissão» no executor 3C-1: ela é declarada pela integração a
  partir do cenário.

## 7. Persistência: contrato `seeds2-milp-mpc-run-data` **v3** (o que o 3D-B consome)

**Versões.** `registro.VERSAO = 3`; legíveis 1, 2 e 3. Testado:

- v1 do 3D-A: `test_caso9_…`;
- v2 do 3D-A2-R: `test_rodada_renovavel_gravada_no_contrato_v2_…`.

**Documentos:**

- `v2/pemfc.json` (`seeds2-milp-mpc-pemfc` v1), por registro:
  - documento da curva: inicialização, identidade e impressão, pontos de ajuste e de validação (com corrente), vértices,
    métricas, estado B04, diagnóstico da rama, hipóteses e perfis temporais;
  - certificado B04 do núcleo e seu hash;
  - temperatura ambiente, massas ADICIONAIS por evento com a análise transitória que as sustenta, admissibilidade a
    priori e declaração.

  É comprometido no manifesto ANTES da execução (`hashes["pemfc"]`).
- `v2/pemfc_dinamica.json` (versão 2): por unidade e intervalo:
  - evento (partida, parada, ligada, desligada);
  - potência solicitada, potência média entregue e energias; déficit e excesso;
  - H₂ do modelo dinâmico × H₂ do EMS (contabilidade do MILP com as massas de evento);
  - tolerâncias aplicadas, estados, limitações, coerência e a lista de incoerências;
  - totais.
- **Aceitação SEPARADA** em `summary.execution.aceitacao` (auditoria do PR #23, B): `algebrica` (missão completa +
  auditoria integral), `dinamica` (`coerente` × `incoerente` × `nao_aplicavel`), `fisica` (sempre `nao_validada`),
  `classificacao` e `rotulo`. `concluida` no armazenamento significa só evidência ALGÉBRICA completa e auditada; uma
  rodada `algebrica_aprovada_dinamica_incoerente` é exibida com o alerta «DINAMICAMENTE INCOERENTE» e o rótulo «NÃO
  representa operação executável».

**Colunas por unidade em `v2/intervalos.csv`:** `<eq-…#k>|{u, p_kW, partida, parada, q_h2_kg_h, m_h2_kg, m_h2_acum_kg,
custo_h2_R, custo_eventos_R}`. Detalhes:

- `q_h2_kg_h` é calculado pela MESMA função PWL do núcleo (`ems_v2.reference.vazao_pwl`);
- o resíduo de balanço inclui p;
- o custo inclui H₂ e eventos;
- o resumo por unidade é conferido contra `E_geracao_kWh[uid]` do registro selado.

**Reabertura e importação.**

- A reabertura (local ou de estudo importado) não reconstrói a curva, não roda modelo PEMFC nem solver. Testado com:
  - `obter_curva`, `verificar_despacho`, `construir_missao` e `submit` sabotados;
  - `pyomo`/`highspy` ausentes;
  - registro de certificados VAZIO.
- O certificado é re-registrado RECOMPUTANDO os critérios e os vértices são conferidos.
- As consignas do documento dinâmico precisam ser as aplicadas seladas.
- O H₂ do EMS no documento dinâmico precisa ser a coluna selada `m_h2_kg` de cada intervalo.
- A coerência é RECALCULADA dos valores e das tolerâncias gravados (sem modelo) e o rótulo de aceitação do resumo precisa
  ser o recalculado: rótulo ou coerência adulterados ⇒ verificação falha.
- Qualquer adulteração (curva, certificado ou dinâmica) ⇒ verificação falha.
- Com a política revogada (simulação nos testes), a reabertura **não** certifica a curva.
- A subestimação de H₂ por unidade (máximo por intervalo e total) gravada no documento dinâmico e no resumo é
  RECALCULADA dos intervalos e conferida.

## 8. Caso híbrido demonstrado (sintético; política B04 do repositório, aprovada)

Microrrede do catálogo com FV + eólica + banco + PEMFC + PCC (importação limitada a 25 kW). Demanda de 40 kW × 12 h; preço
do H₂ 10 R$/kg; Δ = 60 min; N = 3; H_L = 10.

**Resultado:** missão concluída e auditada, 12 janelas, energia não atendida 0, resíduo de balanço 0, reabertura
verificada.

**Custo realizado: R$ 116,02** (com as massas ADICIONAIS por evento; antes da correção A: R$ 116,00).

| Componente | Valor |
|---|---|
| H₂ | R$ 65,72 |
| Importação | R$ 50,00 |
| Throughput | R$ 0,30 |
| Valor futuro | nunca somado |

**PEMFC:**

- 100,54 kWh;
- 6,5717 kg de H₂ (= 6,5653 kg da PWL + 2 × m_SU (= 0) + 1 × m_SD (0,0064 kg));
- 2 partidas, 1 parada, 6 h ligada.

**Aceitação:** algébrica aprovada · dinâmica COERENTE · física não validada.

| Grandeza | Modelo dinâmico | EMS |
|---|---|---|
| Energia | 100,27 kWh entregues | 100,54 kWh solicitados |
| H₂ | 6,5452 kg | 6,5717 kg (total; resíduo +0,4 %); maior subestimação num intervalo 0,0006 kg (rampa de descida) |
| Intervalo da parada | 0,00015 kg | 0,0064 kg (superestimação limitada) |

## 9. Decisões e contradições registradas

| Código | Conteúdo | Situação |
|---|---|---|
| C-3DA2H-01 | Núcleo: `real_certificada_b04` + `curvas_h2` opcional em 3 arquivos da ponte; guardas nominais | autorizado |
| C-3DA2H-02 | `massas_h2_eventos` opcional (massas ADICIONAIS do modelo dinâmico); sem parâmetros/modelo compatível ⇒ bloqueio | **aprovado** |
| C-3DA2H-03 | Rampa única declarada = limite simétrico de subida e descida, sem exceder o modelo dinâmico (simplificação registrada) | **aprovado** |
| C-3DA2H-04 | D05 só em «ensaio»: abstração instantânea condicionada ao preflight dinâmico e à verificação a posteriori; não é modelo operacional validado; multimodo pendente | **aprovado (alcance delimitado)** |
| C-3DA2H-05 | Bloqueio de P_mín < IDLE de 10 kW enquanto a condição pertencer à configuração física usada | **aprovado** |
| C-3DA2H-06 | Estratégia formato 3 e contrato de dados v3 (aditivos; formatos 1/2 e contratos v1/v2 legíveis) | registrado |
| C-3DA2H-07 | Testes do 3D-A2-R ajustados NOMINALMENTE (versão vigente; versões anteriores continuam testadas) | registrado |
| C-3DA2H-08 | Massas por evento = massas ADICIONAIS pela integração temporal; m = máx(0, máx_p δ); aproximação conservadora identificada (A) | **aprovado** |
| C-3DA2H-09 | Aceitação separada algébrica × dinâmica × física; rodada dinamicamente incoerente continua `concluida` no armazenamento, rotulada e com alerta (B) | **aprovado** |
| C-3DA2H-10 | Autoridade B04 = registro `POLITICAS_B04_NUCLEO` por identidade do conteúdo; aprovação = commit no núcleo (C) | **aprovado** |
| C-3DA2H-11 | Tolerâncias dinâmicas absolutas como médias por unidade de tempo (tolerâncias de engenharia do ensaio) | **aprovado** |
| B04 | Política `b04-proposta-2` para a certificação MATEMÁTICA da PWL (não validação experimental) | **APROVADA** (`8be5de4`) |
| C-3DA2H-12 | Rampas de DESCIDA em operação contínua: subestimação do H₂ do EMS aceita como RESÍDUO QUANTIFICADO (máximos observados 0,0044 kg/rampa e 0,72 % nos casos ensaiados, §5a — não são cotas universais); SEM termo de rampa no MILP; reportada por intervalo/unidade/acumulada e verificada na reabertura | **aprovado (alcance experimental; 7 condições em §5b)** |

**Auditorias explícitas anteriores.** São opt-in, por missão: `piso3da_guard_policy.py` e `piso3da2r_guard_policy.py`
(e `SEEDS2_AUDITORIA_PISO3DA=1`). Elas auditam o diff da SUA missão desde a sua base. Rodadas sobre este ramo, acusam
corretamente os 4 arquivos do C-3DA2H-01 e `h2_app.py`, que são alterações desta missão. A auditoria vigente é
`python tests/ems_v2/piso3da2h_guard_policy.py` (aprovada).

## 10. Limitações remanescentes

- O H₂ do EMS não é cota superior global: rampas de descida em operação contínua subestimam (resíduo aceito, C-3DA2H-12,
  §5b); os custos e decisões do MILP não representam exatamente a operação transitória.
- A verificação densa das massas (§5a) foi feita só em Δ = 60 min: não se estende automaticamente a outros passos.
- Condições físicas constantes durante a missão: hipótese do responsável e campo da identidade.
- Uma curva por registro: unidades idênticas do mesmo registro compartilham a curva.
- Quantidade disponível de H₂ (tanque) não modelada.
- Multimodo M20 e curva com IDLE como modo próprio não implementados.
- A verificação dinâmica não realimenta o despacho: a realização algébrica continua igual à consigna. Uma rodada
  dinamicamente incoerente só é ROTULADA (não é reotimizada); em produção, as configurações incompatíveis conhecidas são
  bloqueadas antes (§6).
- Uma constante por evento não reproduz δ(p) exatamente: a superestimação fica limitada e registrada.
- Relatórios 2D-B continuam recusando rodadas V2.
- Modelo físico aproximado: sem validação (b) nem (c).

## 11. Reprodução

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_piso3da2h_curva.py tests/ems_v2/test_ems_v2_b04_certificado.py
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_piso3da2h_execucao.py tests/test_piso3da2h_app.py   # requer Pyomo/HiGHS
PYTHONDONTWRITEBYTECODE=1 python tests/ems_v2/piso3da2h_guard_policy.py
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_piso3da2h_auditoria_pr23.py                      # A, B, D (missões: Pyomo/HiGHS)
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_piso3da2h_verificacao_massas.py                  # verificação A (nominal)
PYTHONDONTWRITEBYTECODE=1 python tests/verificacao_massas_3da2h.py <saida.json>                           # verificação A (6 configurações)
bash tools/e2e/run_piso3da2h.sh <python com Pyomo/HiGHS> <pasta vazia> <python SEM solver>             # verificação B
```

## 12. Verificação B (decisão do responsável, item 3B): fluxo completo com a B04 REALMENTE aprovada

Sem `politica_aprovada_no_teste` (removida) e sem nenhum `sitecustomize` de autorização: preflight normal, política do
repositório. Roteiro `tools/e2e/run_piso3da2h.sh`, evidência em `docs/ems_v2/evidencia_3da2h/`:

| Fase | O que prova | Verificações |
|---|---|---|
| `e2e_bancada.log` | bancada H₂: PWL do modelo físico APROXIMADO, verificada MATEMATICAMENTE, «Certificada», sem validação experimental | 6 |
| `e2e_fluxo.log` | microrrede FV + eólica + bateria + PEMFC + PCC; declarações renováveis e PEMFC preenchidas PELA INTERFACE; preflight normal apto; missão real (HiGHS); rodada com aceitação separada (coerente); balanço (não atendida 0) | 20 |
| `e2e_reabrir.log` | aplicação reiniciada; python SEM solver; motor e modelos (renováveis e PEMFC) sabotados; rodada reaberta com custo idêntico; rodadas legadas nos contratos v1 (3D-A) e v2 (3D-A2-R) legíveis e verificadas | 16 |
| `e2e_conferencia_quantitativa.log` | dados gravados: balanço (resíduo 0), despacho no domínio, H₂ = q̂·Δ·u + m_SU·y + m_SD·z, custo = preço × massa, componente do custo realizado, aceitação, B04 re-registrado; registro de chamadas ao motor/modelos VAZIO | 18 |

Resultado da missão: custo realizado R$ 116,02 (H₂ R$ 65,72; importação R$ 50,00; throughput R$ 0,30); PEMFC 100,54 kWh,
6,5717 kg de H₂, 2 partidas, 1 parada; dinâmica coerente (100,27 de 100,54 kWh; H₂ dinâmico 6,5452 kg); maior subestimação
de H₂ num intervalo 0,0006 kg.
