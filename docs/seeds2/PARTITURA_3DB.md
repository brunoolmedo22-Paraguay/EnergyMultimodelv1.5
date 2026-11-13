# Partitura e motor gráfico Trama — Piso 3D-B (entregas B0, B1, B3 e B2)

Direção de design aprovada pelo responsável: **Partitura V2** (uma linha do tempo, lentes, inspetor sincronizado e
explorador de recursos). Este documento descreve o que está **integrado na aplicação Streamlit real**, o que ainda existe só
no protótipo e como verificar. A entrega **B3** (decisão do responsável «avançar para as lentes científicas») acrescentou a
correção de N/D no navegador (§3a), as lentes Decisão, Economia e Evidência (§3b) e recolheu a vista clássica (§5, C-3DB-05).

## 1. O que está integrado

| Peça | Onde | Estado |
|---|---|---|
| Marco de dados `seeds2-trama-frame` v2 (v1 + planos, coordenações, auditoria, procedência, tabelas) | `integracao_v2/trama_frame.py` | integrado |
| Motor gráfico Trama (SVG, sem dependências) | `seeds2/ui/static/trama/trama.js` | integrado |
| Instrumento Partitura: lentes **Operação, Decisão, Economia e Evidência**, inspetor, barra de estado, temas | `seeds2/ui/static/trama/partitura.js` + `trama.css` | integrado |
| Explorador de recursos: **Solar, Eólica, Bateria, PEMFC (Operação · Curva q(P) e B04 · Verificação dinâmica), Rede/PCC, Carga, Custos**, com seleção por UID | idem | integrado |
| Componente v2 | `seeds2/ui/trama.py` (`st.components.v2.component("seeds_partitura", …)`) | integrado |
| Página da rodada V2 (local **e** estudo arquivado) | `integracao_v2/ui.py::_partitura`, chamada no início de `run_results` | integrado |
| Vista clássica (tabelas, Plotly, descargas, procedência) | mesma página, num expansor identificado, **recolhido por padrão** quando a Partitura é desenhada | **mantida inteira** |

Ainda **só no protótipo** (não integrado; etapa 3D-B2, só depois deste checkpoint): barra lateral compacta; Catálogo;
Planta; Caderno de ensaios; Folha de ensaio; exportação de figuras; séries climáticas nos painéis solar e eólico (hoje N/D).

## 2. Fluxo de dados

```
MicrogridStore | StudyView ──run_data──▶ integracao_v2.registro (ler_csv / ler_json / verificar)
                                              │  só leitura, sem solver, sem modelos
                                              ▼
                               integracao_v2.trama_frame.montar(source, run)
                                              │  dict JSON estrito (sem NaN), com hash
                                              ▼
                 seeds2.ui.trama.partitura(frame)  ──data──▶  componente v2 (navegador)
```

* O marco contém **os valores gravados, sem arredondamento**: colunas de `v2/intervalos.csv` (N valores de intervalo),
  `v2/fronteiras.csv` (N + 1 estados de fronteira), linhas de `v2/janelas.csv`, parâmetros e diagnósticos de
  `v2/renovaveis.json`, curva/certificado de `v2/pemfc.json`, verificação de `v2/pemfc_dinamica.json`, resumo selado,
  aceitação, avisos, declarações da estratégia (limites, preços) do manifesto e o resultado de `registro.verificar`.
* **v2 (B3), só acréscimos:** `planos` (uma entrada por janela com as séries `<uid>|<grandeza>` de `v2/planos.csv` e a marca
  `aplicado`), `coordenacoes` (de `v2/coordenacoes.json`: situação, origem e motivo, decomposição do objetivo, **sinal de
  valor futuro** com modos, pontos V(E), domínio, energias inviáveis, validações e qualidade, e o plano de longo prazo),
  `auditoria` (resumo de `v2/auditoria.json`), `procedencia` (identidades, impressões, formulações, software — do
  manifesto), `limitacoes`/`convencoes` (as do registro), `tabelas` (as quatro vistas CSV como gravadas) e `arquivos`.
* Coluna inexistente ou célula vazia vira `None` → a interface mostra **N/D**. Nenhuma série é sintetizada.
* O marco **não agrega nem acumula**. Somas por tecnologia, acumulados, participação na demanda, classificação de
  comportamento da bateria e a diferença PWL − modelo são calculadas no navegador e **rotuladas como «derivado»**.
* Nomes e TAG dos equipamentos vêm do `inventory_ref` da versão do cenário executada, quando a origem o expõe
  (`get_scenario`); senão o painel mostra o tipo e o UID.
* Só rodadas V2 **concluídas** e com **evidência verificada** recebem a Partitura. Rodada falha/interrompida, evidência com
  problemas ou erro de leitura ⇒ a página mostra apenas a vista clássica (com a mensagem do motivo).

## 3. Motor Trama

* Um script (`trama.js`) com funções puras de escala e desenho: `trama(host, opções)` desenha raias sobre uma malha de N
  intervalos e N + 1 fronteiras; `xy(host, opções)` desenha gráficos não temporais (curva q(P), erro da PWL).
* Semântica por construção: `stack`/`step`/`strip`/`dots` desenham grandezas de **intervalo** (ocupam `[τ_g, τ_g+1)`);
  `front` desenha **estados de fronteira** em `τ_k`. Nada é interpolado para exibir números.
* Um barramento de eventos por instrumento sincroniza o cursor entre o gráfico principal e o painel aberto.
* Interações sem servidor: passar o mouse (cursor), clique/Enter (fixa o instante), setas (movem), foco por recurso
  (as outras séries recuam), zoom por período (tudo, metade, um quarto da missão), dicas com unidade.
* Persistência do contexto: `sessionStorage` por rodada (instante, fixação, zoom, painel aberto, vista, UID escolhido) e
  `localStorage` para o tema. Um **rerun** do Streamlit com o mesmo marco (mesmo `hash`) não redesenha nada.

## 3a. N/D no navegador — três situações que nunca se confundem (B3)

Uma auditoria independente do B1 encontrou `|| 0` e `Array(K).fill(0)` nas agregações do `partitura.js`: uma grandeza não
persistida passava a contar como zero. Corrigido em três níveis, sem tocar em contratos nem na formulação:

| Situação | No marco | No navegador |
|---|---|---|
| **zero gravado** | `0.0` | número 0: entra nas somas e é desenhado como zero |
| **dado ausente** (coluna inexistente, célula vazia, série não gravada) | `None` → `null` | «N/D»: não é somado, não é desenhado como zero, e **torna N/D toda grandeza derivada** que dependa dele (total do balanço, acumulados, participações, diferenças) |
| **não aplicável** (o recurso não existe na microrrede, PCC isolado, termo fora do objetivo) | recurso ausente de `recursos` / termo todo vazio | `undefined`: omitido — sem N/D e sem zero inventado |

* **Modelo de vista** (`modelo`, `balancoDe`, `planoPorTipo` e os utilitários puros `agg`, `mais`, `vezes`, `menos`, `razao`,
  `somaT`, `acum`, `opc`, `conta`): nenhuma expressão aritmética toca um valor ausente. `acum` não acumula depois de uma
  lacuna; `agg` de N unidades com uma sem dado é N/D (nunca a soma das outras); `razao(a, 0)` é «não aplicável», não N/D.
* **Motor** (`trama.js`): `stack`/`step`/`front`/`strip` aceitam `null` (série ausente ⇒ a raia declara «N/D — série não
  persistida») e `undefined` (não aplicável ⇒ nada), marcam «N/D» no intervalo sem valor e interrompem linhas na lacuna.
* **Painéis**: todo valor mostrado passa por `el()`; multiplicações por 100/1000 e diferenças usam `vezes`/`menos`
  (antes, `100 * null` virava `0,0 %`). O comportamento derivado da bateria tem o estado «N/D».
* Séries obrigatórias ausentes ficam N/D ou bloqueiam a soma (inspetor: «balanço incompleto: rede sem dado neste intervalo.
  Nada é assumido como zero»). As agregações continuam válidas quando um recurso realmente não participa.

## 3b. Lentes científicas (B3)

Todas partilham o instante (cursor/fixação), o explorador de recursos e a barra de estado; trocar de lente não muda o
instante. O estado (lente, janela, instante, zoom, opções) é guardado por rodada no `sessionStorage`.

* **Decisão** — tapete de decisões do MPC (uma linha por janela; grandeza selecionável: energia planejada de cada banco,
  PEMFC planejada, importação programada; traço = intervalo aplicado; clique seleciona a janela); seletor de janela e
  «janela do instante»; energia da bateria **executada até τ_k × plano MPC da janela × plano de longo prazo × o que ocorreu
  depois**; despacho planejado (cheio = aplicado, claro = planejado e depois revisto) com a demanda prevista × realizada;
  sinal de valor futuro **V(E)** desenhado só com os pontos gravados (modos, pontos, domínio, validações, energias
  inviáveis, referência do plano longo, energia terminal escolhida); para dois bancos, tabela dos pontos (sem projeção
  inventada). Janelas **sem sinal válido** são um resultado científico: aparecem marcadas (∅) no tapete, com «sem valor
  futuro», custo futuro N/D e o motivo gravado; os pontos avaliados aparecem tracejados, só como registro. O botão «o que
  ocorreu depois» separa o que o controlador sabia em τ_k do que só aconteceu depois (pode ser ocultado). A interface
  descreve; **não atribui causas**.
* **Economia** — custo operacional **realizado** por intervalo (por componente: rede, hidrogênio/eventos, bateria) e
  acumulado (valor gravado); por decisão, bloco aplicado previsto × realizado; objetivo do MILP por decisão = custo
  operativo previsto + valor futuro estimado (hachura), com ∅ nas decisões sem valor futuro. Três grandezas que não se
  somam: custo realizado × objetivo do MILP × valor futuro; toda soma mostrada é rotulada «derivado».
* **Evidência** — estado e integridade (resultado de `registro.verificar` do **servidor**; o navegador só o exibe), as três
  aceitações separadas (algébrica, dinâmica, física) com critério, auditoria independente gravada, solver/gap/terminação
  por decisão, procedência e versões, arquivos com SHA-256, **tabelas originais** (as quatro vistas CSV, valores como
  gravados), advertências agrupadas, limitações e convenções; um botão abre a vista clássica (descargas, exportações).

## 4. Isolamento de estilos e temas

* O componente usa o **isolamento padrão** do `st.components.v2` (raiz de sombra): as regras de `trama.css` não alcançam a
  aplicação e o CSS da aplicação não entra no componente. Além disso, todo seletor começa por `.pt` (teste
  `test_estaticos_sem_recursos_externos_e_estilos_sob_o_prefixo`), de modo que desligar o isolamento no futuro não
  contaminaria outras telas.
* `isolate_styles=False` (usado pelo ProgE-Web) não foi necessário: o painel amplo é um elemento `position: fixed` dentro
  do próprio componente e cobre a janela (verificado no navegador: 1748 × 833 px numa janela de 1768 × 853).
* Sem fontes nem scripts externos: a pilha tipográfica cai em Source Sans (a fonte do próprio Streamlit).
* Tema: detectado a partir do tema efetivo do Streamlit (luminância do fundo da página) e alternável no botão do
  instrumento; os dois temas têm paleta própria, validada para daltonismo.
* A única regra emitida para fora do componente é a largura da página da rodada (`trama.WIDE_CSS`, `.block-container`),
  aplicada só quando a Partitura é desenhada.

## 5. Decisões e contradições

* **C-3DB-01 — guardas nominais.** `tests/ems_v2/piso3db_guard_policy.py` autoriza, por nome e status, os arquivos novos
  do componente e dos testes; `piso3da2h_guard_policy.py` só encadeia o novo filtro. `ems_v2/`, modelos físicos, motor
  V1.6, armazenamento e contratos estão em `INTOCADOS` (auditoria: `python tests/ems_v2/piso3db_guard_policy.py`).
* **C-3DB-02 — convivência.** A Partitura é desenhada **antes** da vista clássica e vem ao topo da janela ao abrir.
  Substituída em parte pela C-3DB-05 (B3).
* **C-3DB-03 — sem contrato novo.** Nenhum arquivo persistido mudou. O marco é derivado sob demanda e não é gravado
  (continua válido no B3: o marco v2 só LÊ mais arquivos já gravados).
* **C-3DB-04 — N/D em três estados (B3).** `null` = ausente, `undefined` = não aplicável, número = gravado (§3a). O teste
  Node do B1 que fixava `acum([1, null, 2]) = [0, 1, 1, 3]` descrevia o defeito e passou a exigir `[0, 1, null, null]`.
* **C-3DB-05 — vista clássica recolhida (B3, autorizada pelo responsável).** Quando a Partitura é desenhada, toda a página
  anterior fica dentro do expansor «Vista clássica — tabelas completas, gráficos anteriores, descargas e procedência»,
  recolhido por padrão; o aviso de motor experimental continua visível fora dele. Sem Partitura (rodada falha/interrompida,
  evidência com problemas, marco indisponível) a vista clássica continua aberta como antes. Conteúdo inalterado
  (`integracao_v2/ui._vista_classica`). Os roteiros E2E dos pisos 3D-A/A2-R/A2-H só ganharam o passo de abrir o expansor
  (navegação); nenhuma verificação foi removida.
* **C-3DB-06 — correção do cache do marco (B3).** A chave de cache por sessão usava um atributo que o estudo arquivado não
  tem; a rodada local e a mesma rodada num estudo arquivado partilhariam a entrada. Agora a origem é a identidade local do
  estudo (`study.archive_uid`) ou «local». Detectado pelo teste novo do estudo arquivado.
* **Dependência registrada:** séries climáticas por intervalo (GHI, temperatura, vento) estão na previsão do cenário
  (blob por SHA-256), não nos dados da rodada. Lê-las exige ligar o marco à leitura de blobs do cenário, inclusive em
  estudos arquivados; até lá os painéis solar e eólico declaram N/D.

* **C-3DB-07 — «não aplicável» só com evidência (C0 do 3D-B2, pedido do responsável).** A regra anterior (`opc`) tratava
  uma série toda vazia como termo não declarado. Agora o marco leva `objetivo.termos` (os termos DECLARADOS na estratégia
  gravada no manifesto) e o navegador usa `termo(série, declarado)`: série vazia + termo comprovadamente fora do objetivo
  ⇒ não aplicável (omitido); série vazia + termo declarado, **ou sem declaração legível**, ⇒ dado ausente (N/D); valores
  gravados aparecem sempre. O custo de desvio do PCC deixou de ser «opcional» (não é termo do objetivo): vazio ⇒ N/D. No
  painel da bateria, «não declarado» exige a declaração gravada do banco; sem ela ⇒ N/D.
* **C-3DB-08 — zero negativo só na apresentação (C0).** `nf`/`ne` (formatação) mostram «0,0» para o `-0.0` do solver e
  para negativos que arredondam a zero na precisão exibida. Os números do marco, das tabelas originais e dos arquivos não
  mudam; tolerâncias e decisões do solver não foram tocadas.
* **C-3DB-09 — limpeza garantida dos servidores E2E (C0).** `tools/e2e/servidor.sh` (biblioteca dos quatro roteiros
  `run_piso3d*.sh`): exige a porta livre, inicia cada servidor num grupo de processos próprio e instala uma armadilha que,
  em qualquer saída (fase falha, erro, Ctrl-C), encerra o servidor e os filhos. Teste com servidor de fachada:
  `tests/test_piso3db_e2e_servidor.py`.

## 6. Pendências técnicas independentes (não corrigidas)

Achados da investigação anterior, mantidos fora do escopo visual:

1. **R-1** — resíduo numérico do solver na potência aplicada da PEMFC desligada (≈ ±10⁻¹⁵ kW) faz a entrada da janela
   seguinte ser recusada (`quantidade_negativa` / `off_com_potencia`) e interrompe a missão; observado com m = 1.
2. **R-2** — `custo_partida/parada` declarados pelo utilitário de testes produzem `unidade_incompativel` (`R$` × `R$/evento`)
   no preflight; não verificado pelo caminho da interface.
3. **R-3** — com a tolerância de interpolação de 10⁻⁶ R$ e 9 pontos, o sinal de valor futuro fica indisponível na maioria
   das janelas; a degradação declarada funciona, mas a interface anterior não o tornava visível.

## 7. Como verificar

```bash
python -m pytest tests/test_piso3db_trama.py tests/test_piso3db_app.py tests/test_piso3db_nd.py tests/test_piso3db_lentes.py \
       tests/ems_v2/test_piso3db_guardas.py -q
tools/e2e/run_piso3db.sh <python com Pyomo/HiGHS> <pasta vazia>     # navegador real; servidor sem solver, sabotado
python tests/ems_v2/piso3db_guard_policy.py                          # auditoria explícita do diff da missão
python tools/e2e/bancada_piso3db.py <marco.json> <saida.html>        # bancada: o componente real com um marco qualquer
```

* `tests/test_piso3db_nd.py` — **sem solver**: utilitários puros e modelo de vista em Node com dados ausentes (PCC,
  renováveis, bateria, custos, planos), zero gravado, recurso inexistente e termo não declarado; e, com Chromium/Playwright,
  o componente REAL montado numa página local (`tools/e2e/bancada_piso3db.{py,js}`) com oito marcos adulterados,
  percorrendo as quatro lentes e todos os painéis (recurso × vista × UID): nenhum erro e a ausência visível.
* `tests/test_piso3db_lentes.py` — com HiGHS: marco v2 × arquivos gravados (planos, coordenações/sinal, auditoria, tabelas,
  bit a bit); **dois bancos** e **duas unidades PEMFC** com seleção por UID; **12 h/60 min, 24 h (m = 2) e 6 h/30 min**;
  rodada do **contrato v1**; janelas sem sinal válido; no navegador: trocar de lente conserva o instante, trocar de rodada
  não mistura estado, recarregar conserva o contexto.
* `tests/test_piso3db_app.py` — vista clássica recolhida e inteira (tabelas, descargas, procedência, Plotly), troca de
  rodada na mesma sessão, sessão nova sem solver, estudo arquivado.
* Os testes de navegador são **pulados explicitamente** onde não há Node/Chromium/Playwright; os de missão, onde não há
  Pyomo/HiGHS. O marco sintético de `tests/piso3db_util.marco_sintetico` é dado de teste (números redondos), nunca resultado.

Evidência: `docs/seeds2/evidencia_3db/` (registro do E2E e capturas da aplicação real; B3 em `e2e_partitura_b3.log`).

## 8. Piso 3D-B2 — integração visual da plataforma (em curso)

Autorizado pelo responsável depois de aprovar o 3D-B3 (HEAD `590b826`). Critério central: percorrer **Gestor → Microrrede →
Planta → Cenário → Folha de Ensaio → Execução → Rodada Partitura → Dashboard individual → Arquivo Científico** numa
experiência coerente, sem que nenhum fluxo anterior desapareça. Estado por etapa: `docs/ai/HANDOFF.md` (bloco «Continuação
imediata») e a tabela abaixo. A referência visual é a Partitura V2 aprovada (não há outra linguagem).

### 8.1 Telas do protótipo aprovado (descrição para quem não viu o artefato)

* **Barra lateral.** Trilho estreito à esquerda (só ícones) que se expande por cima do conteúdo ao passar o mouse ou receber
  foco; marca SEEDS2; Catálogo; grupo «Microrrede»: Planta, Caderno de ensaios, Folha de ensaio, Rodada; tema. Em telas
  estreitas vira navegação horizontal.
* **Catálogo.** Uma prateleira de cartões, um por microrrede: nome, «assinatura» (um barramento com um marcador por
  tecnologia, dimensionado pela potência/energia instalada), linha de contexto (natureza, modo, cenários, rodadas por
  estado), quatro números (Solar kWp, Eólica kW, Bateria kWh, PEMFC kW) e prontidão por motor; abaixo, os estudos do
  Arquivo Científico (somente leitura, com a identidade do conteúdo).
* **Planta.** O barramento equivalente único desenhado como o modelo o enxerga: o que injeta acima, o que armazena ou
  consome abaixo; um nó por equipamento (nome, TAG/UID, potência do instante); passar o mouse/foco destaca o nó e abre um
  resumo; clique/Enter abre o painel do recurso; um cursor de instante percorre a missão. **Sem ramos nem fluxos por
  linha**: o modelo não os calcula.
* **Caderno de ensaios.** Tabela de todas as rodadas (cenário · versão, rodada, estado, N · m · H_L, PCC, custo realizado,
  energia importada, H₂, valor futuro) com «Abrir»; seleção de rodadas concluídas para comparar (a diferença é um fato dos
  ensaios; a interface não lhe atribui causa).
* **Folha de ensaio.** Três colunas: índice das seções (estado inicial, previsões, motor e estratégia, malha e horizontes,
  baterias, renováveis, PEMFC/H₂, PCC e tarifas, planejador e solver, missão) com o estado de cada uma; a seção escolhida ao
  centro; à direita a prontidão (o mesmo preflight do motor) e o botão de executar a versão salva.

### 8.2 Estado

| Etapa | Estado |
|---|---|
| C0 — correções A (N/D × não aplicável), B (zero negativo), C (E2E) | concluído |
| B2-A — barra lateral, navegação responsiva, identidade | concluído (§8.3) |
| B2-B — Catálogo e Planta | concluído (§8.4, §8.5) |
| B2-C — Caderno de Ensaios | concluído (§8.5) |
| B2-D — Folha de Ensaio | concluído como cabeçalho + índice (§8.5); **finalizado em três colunas, subseções e régua (§8.8)** |
| Finalização (auditoria independente) — Folha, Caderno (indicadores e comparação), estabilização | concluído (§8.8) |

### 8.3 B2-A — barra lateral, navegação e identidade (concluído)

* **Componente.** `seeds_sidebar` (`static/trama/sidebar.js`, regras `.pt.sb`): trilho fixo de 56 px com ícones; expande-se
  **por cima** do conteúdo (244 px) com o mouse ou o foco do teclado — o conteúdo não se move; abaixo de 760 px vira uma
  barra inferior com os destinos essenciais. Não guarda estado no servidor e não provoca reruns por si; um rerun com os
  mesmos dados não o redesenha.
* **Destinos** (`shell.sidebar_items`): sem microrrede — Catálogo, Arquivo Científico, Alcance; em comissionamento —
  Catálogo (= trocar de microrrede), Comissionamento, Alcance; microrrede ativa — Catálogo (= trocar), Centro de Operação,
  Gestão, Arquivo Científico, Simulação V1.6, Resultados V1.6, Alcance. **A barra superior anterior continua completa**
  (os testes e roteiros dos pisos anteriores navegam por ela).
* **C-3DB-10 — onde a barra é desenhada.** `seeds2/ui/main.py` é fixado por SHA-256 na guarda de estabilização; por isso a
  barra lateral é desenhada dentro de `shell.topbar()`, que já recebe o contexto. Pelo mesmo motivo, as páginas novas do
  3D-B2 entram como `tab` do Centro de Operação ou dentro do Gestor, nunca como uma `view` nova em `main.py`.
* **C-3DB-11 — tema.** `.streamlit/config.toml` passou à paleta neutra da Partitura (claro: fundo `#F4F4F2`, tinta `#171717`;
  escuro: fundo `#0F0F0F`), com raios maiores e botões em pílula. As cores categóricas dos gráficos nativos não mudaram.
  A mudança é de apresentação, reversível num arquivo.
* **Verificação.** `tests/test_piso3db_plataforma.py`; navegador `tools/e2e/e2e_piso3db_plataforma.js` (fase 3 de
  `run_piso3db.sh`): trilho, expansão por hover e por foco, Enter, destino atual, rerun sem redesenho, navegação lateral e
  superior em conjunto, troca de microrrede, barra inferior a 400 px, tablet em tema escuro, sem transbordo horizontal.

### 8.4 B2-B — Planta (concluída)

* **O que mostra.** O barramento equivalente da microrrede a partir do **inventário salvo**: acima o que injeta (FV, eólica,
  PEMFC, térmica), abaixo o que armazena ou consome (bancos, demanda agregada) e o PCC, se houver conexão. Um nó por
  equipamento, identificado por nome, TAG e UID, com o nominal do inventário («não declarado» quando desconhecido).
  Equipamento desabilitado aparece tracejado.
* **Rodada opcional.** Escolhida uma rodada V2 concluída **e verificada**, cada nó mostra a potência média GRAVADA do
  intervalo do cursor (e, na bateria, a energia nas duas fronteiras). É uma seleção do marco da Partitura por UID
  (`integracao_v2/ui.planta_rodada`): sem solver, sem modelos, sem aritmética no servidor. Equipamento que não estava na
  rodada diz «não participou desta rodada» (não é zero nem N/D). Dado ausente é «N/D» e torna N/D a soma do nó.
* **Sem fluxos.** As ligações só dizem que o equipamento está no barramento; apagam-se quando a potência gravada é nula e
  ficam tracejadas quando o dado falta. Não há setas, sentidos nem animação: o modelo não calcula ramos.
* **Interação.** Hover ou foco destaca o nó (os outros recuam) e abre o resumo; clique ou Enter seleciona; o cartão do
  selecionado leva ao **painel individual por UID** na Partitura da rodada (no instante do cursor) ou ao inventário.
* **C-3DB-12 — acesso à integração.** A guarda do 3D-A fixa quais módulos de `seeds2` importam a camada de integração.
  `planta_ui` não a importa: usa o acesso tardio já existente em `execution_ui` e a seleção vive em `integracao_v2/ui.py`.
* **Defeito encontrado pelo teste novo e corrigido antes de publicar:** a energia da bateria (K + 1 fronteiras) era
  agregada com K valores (perdia a última fronteira).

### 8.5 Catálogo, Caderno de Ensaios e Folha de Ensaio (concluídos)

* **Catálogo = o Gestor de microrredes.** Não há uma segunda lista: cada cartão existente ganhou a assinatura do barramento
  (só o que o inventário tem; «isolada» quando não há PCC) e a linha de ensaios (cenários e rodadas por estado), e a página
  ganhou a prateleira do Arquivo Científico. Criar, importar, abrir, ZIP, PDF e excluir são os mesmos botões.
  **C-3DB-13:** o `st.html` remove SVG, por isso a assinatura é HTML/CSS; ela ilustra o inventário, não é diagrama elétrico.
* **Caderno de Ensaios** (`tab = caderno`). Uma página para tudo o que foi ensaiado numa microrrede: cenários (com a versão
  atual e o motor) e todas as rodadas, de qualquer cenário e dos dois motores, com estado, datas, revisão do inventário,
  resultado rotulado pelo motor e dados gravados. Rodadas V1.6 abrem na página anterior; rodadas V2 concluídas, na
  Partitura; as demais, no diagnóstico. Os estudos do Arquivo aparecem como somente leitura. Nenhum dado é alterado.
* **Folha de Ensaio.** O cabeçalho da folha (cenário, versão, motor, índice de seções com estado, prontidão, alterações não
  salvas) fica acima de cada uma das quatro etapas existentes e permite ir de uma a outra. **C-3DB-14:** a Folha não
  reescreve os formulários — widgets, chaves, campos científicos, validações, preflight e execução são os de antes; por
  isso o layout de três colunas do protótipo e a régua de horizontes ficaram de fora desta entrega (pendência declarada).
* **Barra lateral.** Ganhou Planta, Caderno de ensaios e Folha de ensaio. Depois de um clique de mouse recolhe-se até o
  ponteiro sair; expande com hover ou com o foco do teclado.

### 8.6 Estabilização visual e fluxo de ponta a ponta (concluídos)

* **C-3DB-15 — barra superior compacta.** Com a barra lateral em todas as vistas, a barra superior deixou de repetir a
  navegação: mostra a marca, a identidade da microrrede, TROCAR MICRORREDE e o estado de salvamento. A navegação clássica
  completa (os mesmos links, visíveis) continua disponível com `SEEDS2_NAV_CLASSICA=1` no ambiente do servidor — é a
  alternativa durante a migração e o modo dos roteiros E2E dos pisos anteriores (`tools/e2e/servidor.sh`).
* **Fluxo de aceitação verificado no navegador** (`tools/e2e/run_piso3db.sh`, servidor sem solver): Gestor/Catálogo →
  ABRIR MICRORREDE → Planta → equipamento por UID → painel individual na Partitura da rodada → Caderno → Folha (seções
  01–04, com o preflight e a execução da etapa existente) → rodada → estudo do Arquivo Científico.
* **Motor e modelos.** Consultar (Catálogo, Planta, painéis, Caderno, rodada, estudo) não chama motor, solver nem modelos
  — conferido com o registro vazio. As páginas de PREPARAÇÃO (Centro de Operação, Folha, Execução) executam o preflight V2
  da versão salva, que deriva o potencial renovável pelos modelos físicos (uma vez por versão e sessão): comportamento
  anterior ao 3D-B2, que a Folha herda ao mostrar o estado da seção 04.
* **Regressão completa sobre `5cade04`:** com solver 2314 passed, 2 skipped, 150 subtests (929,9 s); sem solver 1795 passed, 176 skipped, 145 subtests (520,0 s).

### 8.7 Pendências concretas do 3D-B2

1. ~~Folha em três colunas com subseções navegáveis da estratégia V2 e a régua de horizontes~~ — feito (§8.8).
2. ~~Comparação de rodadas no Caderno~~ — feito (§8.8; elegibilidade definida em C-3DB-18).
3. ~~Restos de verde-azulado fixo~~ — feito no que era acento de página (§8.8); continuam, de propósito, os verdes de ESTADO
   («ok» dos selos) e as cores científicas das tecnologias. O `kit.css` mantém o acento verde-azulado só no modo
   `sd-light` das telas V1.6 forçadas em claro (aparência V1.6 preservada).
4. Séries climáticas por intervalo nos painéis solar e eólico; V(E) com dois bancos em gráfico 2D (não feito).
5. Os roteiros E2E dos pisos 1 a 2D-B (sem `run_*.sh`) precisam de `SEEDS2_NAV_CLASSICA=1` no servidor; não foram
   reexecutados depois do 3D-B2.

### 8.8 Finalização da Partitura V2 (pendências da auditoria independente; autorizada pelo responsável)

* **Folha de Ensaio em três colunas** (`folha_ui.render`, chamado por `operation_center.render` para as quatro etapas):
  **índice** (identidade, as quatro seções com os MESMOS estados do painel e, na seção 03 com o motor V2, as subseções
  03.1–03.10 com o número de declarações ausentes de cada uma — as MESMAS de `estrategia.pendencias`), **seção** (a etapa
  existente, intacta) e **prontidão** (versão salva × alterações não salvas, estado das quatro seções, preflight da versão
  salva e se a execução está disponível — pelas MESMAS razões que habilitam o botão da seção 04; o botão de executar
  continua só na seção 04). Acima de 1180 px as colunas laterais ficam fixas ao rolar; entre 641 e 1180 px a prontidão
  desce para baixo da seção; no celular as três empilham (índice → seção → prontidão) e as subseções viram uma faixa
  rolável. O cartão de abertura da etapa vira o cabeçalho da seção (os mesmos textos) e «← Centro de Operação», uma trilha
  discreta (os roteiros dos pisos anteriores continuam a usá-lo).
* **Subseções da estratégia V2** (`integracao_v2/ui.py`): Motor · Malha temporal e horizontes · Demanda e realização ·
  Bancos de baterias · Recursos renováveis · PEMFC e hidrogênio · Rede, PCC e objetivo · Planejamento de longo prazo · MPC e
  solver · Declarações pendentes e políticas fixas (só as que existem no cenário). Cada uma é uma âncora `data-fl-sub` no
  formulário; o índice ROLA até ela e destaca a visível (sem rerun). Reorganização só de apresentação: mesmas chaves,
  campos, vocabulários, unidades, procedência e validações (o planejador e o solver, antes num cartão, ficaram em dois).
* **Régua dos horizontes** (`regua_dados` + `folha.js` parte `regua`): missão K_M = duração/Δ, passo Δ, horizonte curto N,
  bloco aplicado m, horizonte longo H_L, número de janelas ⌈K_M/m⌉ e as primeiras janelas (planeja N, aplica m; reduzida no
  fim da missão, política fixa `montagem.FIXOS`). Só com valores declarados: ausente ⇒ N/D e «régua incompleta»; as
  relações que o preflight V2 verifica (duração múltipla de Δ, K_M ≤ 336, 1 ≤ m ≤ N, H_L > N, H_L ≤ K_M) são EXIBIDAS, não
  impostas. Aparece na subseção 03.2 (cópia de trabalho) e na seção 04 (versão SALVA, a que será executada).
* **C-3DB-16 — a Folha é moldura.** Nenhum widget, chave, validação, regra de preflight, condição inicial ou gravação
  mudou; o índice e a prontidão são desenhados DEPOIS da etapa na mesma execução (refletem as edições dela).
* **C-3DB-17 — «alterações não salvas» falso.** Causa: os campos numéricos devolvem `float` para valores gravados como
  `int` (p. ex. 0 → 0.0; `time_limit_s` 60 → 60.0), e a impressão da cópia de trabalho os distinguia — abrir a etapa 01 ou
  03 já marcava alteração. Correção na camada de edição (`operation_center._fp_edicao`): só a COMPARAÇÃO trata inteiro e
  real de mesmo valor como o mesmo número; o documento não é alterado nem gravado. Teste negativo (percorrer as quatro
  seções de cenários V2 e V1.6 não cria alteração; nada é gravado) e positivos (número e texto alterados continuam
  detectados e bloqueiam a execução).
* **Caderno — indicadores persistidos por rodada** (`caderno_ui.indicadores`; V2 por `integracao_v2.ui.indicadores_rodada`):
  malha Δ·N·m·H_L (V1.6: passo e N), PCC, custo rotulado pela NATUREZA (V1.6: função objetivo; V2: custo realizado —
  só de missão concluída, nunca o parcial), energia importada, H₂, sinal de valor futuro (válidos/degradados/janelas),
  integridade (auditoria integral registrada + arquivos; a verificação completa continua ao abrir a rodada). Métricas do
  EMS V2 são «não aplicáveis» ao V1.6 (por evidência do motor); o que o resumo não registra é N/D.
* **C-3DB-18 — comparação de rodadas** (`caderno_ui.comparar`; só rodadas DESTA microrrede; sem solver nem modelos):
  diferença absoluta só entre números do mesmo motor e da mesma natureza, relativa só com |A| > 0; motores diferentes ⇒ lado
  a lado, sem diferença (inclusive a energia: as convenções de integração diferem); condições experimentais (cenário,
  versão, inventário, janela, malha, PCC, contrato de dados) conferidas e as distintas ADVERTIDAS; comparação temporal
  (custo acumulado, importação no PCC, demanda) só entre duas rodadas V2 concluídas com instantes de intervalo IDÊNTICOS —
  nada alinhado, reamostrado nem interpolado; caso contrário, o motivo. «Abrir os resultados completos» de A ou B.
* **Barra lateral:** destino **Rodada** quando há rodada selecionada que existe na microrrede ativa; a marca SEEDS2
  continua visível no trilho recolhido (o ícone encolhia até um ponto).
* **Preflight nas seções 01–03:** a prontidão usa o estado da seção 04, que deriva o potencial renovável pelo preflight V2 da
  versão salva — uma vez por versão e sessão (cache `op_ex_pf_v2` já existente). Mantido e documentado; os modelos não foram
  tocados. A coluna de prontidão não recupera rodadas de processos mortos (só lê); isso continua na seção 04.
* **Verificação (código `068ef9d`):** regressão com solver 2335 passed, 2 skipped; sem solver 1814 passed, 178 skipped; E2E `run_piso3db.sh` 103 + 78; E2E 3D-A 106, 3D-A2-R 43, 3D-A2-H 60 (detalhe: `PARAMIJEFE.md` Entrega 19).
* **Diferenças restantes em relação ao protótipo:** a Folha da V1.6 não tem subseções (o formulário é curto); séries
  climáticas nos painéis solar/eólico e V(E) 2D continuam pendentes; o Caderno não compara estudos arquivados (só rodadas
  locais).
