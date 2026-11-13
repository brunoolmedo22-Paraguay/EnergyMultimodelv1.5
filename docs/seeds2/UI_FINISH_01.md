# UI-FINISH-01 — navegação, catálogo compacto, prontidão do ensaio e exportações da Partitura

Missão pedida pelo responsável (pacote `SEEDS2_OPUS_UI_FINISH_2026-11-13`: `PROMPT_PARA_OPUS.md`, seis referências e o
fonte de referência do ProgE-Web v0.1.379-r1, lido só como benchmark — nada copiado), sobre `main` `c29e600` (merge do
PR #27). Acabamento de interface e integração de capacidades existentes: **`ems_v2/`, o runner V2
(`integracao_v2/execucao.py`), modelos físicos, motor V1.6, contratos, armazenamento e dados persistidos ficam intocados**
(auditoria `python tests/ems_v2/ui_finish01_guard_policy.py`). Evidência: `docs/seeds2/evidencia_ui_finish01/`.

## 1. Bancadas também sem microrrede (ponto 1)

`seeds2/ui/shell.sidebar_items`: o grupo «Bancadas» (Solar, Eólica, Bateria, H₂ / PEMFC, Térmica — ícones e cores do Gestor)
aparece nos TRÊS contextos (sem microrrede/Arquivo, comissionamento, microrrede aberta), com a MESMA ação
`{type:"bancada"}` → `shell.abrir_bancada` (só `energy_source`; nenhuma configuração de microrrede é usada). Uma lista por
contexto: nunca duplicada. No celular (barra inferior só com os destinos essenciais) o Catálogo ganha, no fim, o mesmo
bloco de bancadas do Centro de Operação (`home.benches`), escondido no desktop por CSS.

## 2. Catálogo com cartões recolhidos (ponto 2)

`seeds2/ui/gestor.py`. Recolhido: estado (chips), nome, ID, um resumo de uma linha (equipamentos, tecnologias, cenários e
rodadas concluídas — números já calculados pelo resumo do cartão) e o convite **«Passe o mouse ou clique para
expandir»**. Detalhe (`.gc-det`) e TODAS as ações (contêiner `mgca_<uid>`: ABRIR, ZIP, PDF, Excluir, downloads) ficam com
`display: none` — fora da tela, do Tab e da árvore de acessibilidade. Expansão só com HTML/CSS nativos (nenhum
componente, nenhum rerun, nenhuma consulta ao banco):

* `<details>/<summary>`: foco, **Enter/Espaço** e o estado expandido/recolhido anunciados pelo navegador; clique/toque no
  convite **fixa** o cartão aberto (novo clique recolhe) sem acionar nenhuma ação;
* **hover** expande só em dispositivos com mouse (`@media (hover: hover)`); no toque só o toque no convite expande;
* o cartão continua aberto enquanto o foco está numa das ações (`:has(… :focus)`) — nunca some sob o teclado;
* as ações, chaves (`g_open_/g_zip_/g_pdf_/g_del_<uid>`), validações e a exclusão protegida são as de antes; a grade
  alinha pelo topo (expandir um cartão não estica os vizinhos). Cartão com armazenamento indisponível: o mesmo esquema
  (o botão de exclusão aparece ao expandir).

Escape não recolhe (não há JavaScript); o próprio convite recolhe por clique ou teclado.

## 3. Pré-execução limpa + cartão de rodada (ponto 3)

**3A — relatório compacto** (`integracao_v2/ui.relatorio_preflight`): os MESMOS itens de `PF.PreflightV2.report()`
(nenhuma reclassificação). Resumo em chips (bloqueios, advertências, aprovadas, informações, excluídos); **bloqueios
sempre visíveis** com o texto inteiro, título forte, corpo menor e «Onde revisar (orientação)» só para áreas inequívocas
(`ONDE_REVISAR`); advertências resumidas por área com o texto completo a um clique; informações (alcance científico)
visíveis em letra menor; **«Ver N verificações aprovadas»** agrupadas por classe/contrato com o texto integral. Matriz
fonte → … → vista e o relatório da ponte 3C-0/3C-1 continuam nos seus expansores.

**3B — cartão «Rodada · execução V2»** (`integracao_v2/ui.cartao_rodada`) logo abaixo da Folha de Ensaio (posição da
referência 05). É o **único** lugar do botão de executar da etapa 04 V2 e é o MESMO botão: chave `op_ex_run_v2`, rótulo,
ajuda, razões de bloqueio (alterações não salvas, bloqueios do preflight, outra rodada ativa) e a MESMA chamada
`X.submit(…, request_id, background=True)` com o pedido idempotente e o `st.rerun` de antes — só mudou de lugar. A etapa
entrega o cartão por um «slot» de sessão (`CTA_SLOT`) que a Folha abre antes da etapa e desenha depois do índice
(`folha_ui.render`; a Folha não importa o pacote do motor — C-3DB-12); fora da Folha o cartão é desenhado no lugar antigo.
Estado do cartão = contagens do preflight da versão SALVA («Pronto para executar a versão salva vN», «Execução bloqueada —
N bloqueio(s)» + «Revisar: <áreas>», «Alterações não salvas», «Em execução»). Durante uma rodada: executar desabilitado e
**«VER PROGRESSO DA RODADA»** reabre o modal (pedido do servidor ao componente; nenhum rerun extra da rodada). No celular as
colunas empilham índice → cartão → seção → prontidão. Cenários V1.6: inalterados.

## 4. Overlay que piscava (ponto 4) — causa raiz medida

Reproduzido num servidor real (missão de 240 h): o overlay era o MESMO elemento (sem remontagem), com estilo computado
constante, mas em alguns quadros o fundo aparecia NÍTIDO. Correlação exata em 40 quadros: a nitidez (média de bordas)
saltava de 3,7 para 32,1 **só** quando o Streamlit marcava o contêiner `st-key-seeds_execucao` como `data-stale="true"`
durante a atualização do fragmento — o contêiner recebe `transition: opacity 1s ease-in 0.5s`, e uma transição de
opacidade pendente faz do contêiner uma nova **raiz de fundo** do `backdrop-filter`: o desfoque passa a cobrir só o que está
dentro dele. Correção (`integracao_v2/ui.MODAL_ESTAVEL_CSS`): o contêiner do modal fica fora do efeito «stale» (`transition:
none; opacity: 1`); os demais elementos da página mantêm o comportamento do Streamlit. Depois: nitidez constante em todos
os quadros, inclusive nos capturados durante a atualização. Animação interna, foco, atalhos, ocultar/reabrir, cancelar e
conclusão inalterados.

## 5. Exportar cada gráfico (ponto 5)

`seeds2/ui/static/trama/trama.js` (motor Trama; usado pela Partitura): botão **Exportar** em cada gráfico (`trama()` e `xy()`
recebem `exp`; a Partitura passa os metadados em `opts`, então TODOS os gráficos das quatro lentes e dos painéis por
recurso o têm) com menu (`role=menu`, setas, Escape): **PNG · claro (publicação)**, **PNG · escuro**, **SVG · claro**,
**SVG · escuro** — tema da exportação independente do tema da tela. Inspirado no padrão do ProgE-Web (`proge_chart.js`:
menu, `exportSvg`, `renderPng`, nomes determinísticos), reimplementado sobre o SVG da própria Partitura:

* SVG **autocontido**: o gráfico é clonado num contêiner fora da tela, dentro do MESMO shadow root e com o tema escolhido,
  para valerem as regras de `trama.css`; os estilos computados viram atributos (inclusive `currentColor` e `paint-order`),
  as hachuras referenciadas são copiadas, classes/`tabindex` saem. Sem CSS externo, variáveis, scripts ou fontes embutidas;
* estado transitório da interface fora: cursor, recuo de foco, links «↗»; a janela exibida (zoom) é identificada
  («Intervalos exibidos: …»);
* cabeçalho (título do gráfico; cenário, versão, rodada, malha, fuso), legenda (a mostrada junto do gráfico), rodapé
  (fontes = arquivos gravados da rodada; «N/D = dado ausente (nunca desenhado como zero)»; rótulo de dados sintéticos),
  `<title>/<desc>/<metadata>`;
* PNG = rasterização desse SVG a **300 ppp** (`pHYs`) com `tEXt` (Title, Software, Source, Description);
* números, formas, sinais e N/D são os do gráfico desenhado — nada é recalculado.

## 6. PDF / ZIP / Excel na página da rodada V2 (ponto 6)

**Diagnóstico.** `seeds2/ui/report_exports.render` não aparecia porque `execution_ui.run_results` desvia as rodadas V2 para
`integracao_v2/ui.run_results` antes de chamá-lo — e, mais fundo, **os geradores do 2D-B não cobrem rodadas V2**: leem o
contrato V1.6 (`entradas/missao.csv`, `saidas/despacho_ems.csv`, `saidas/relatorio_ems.json`) e recusavam a rodada V2
(«Rodada concluída incompleta…»), como registrado no `CLAUDE.md`. Montar o painel na página V2 só mostraria três recusas.

**Lacuna preenchida reutilizando a arquitetura existente** (nenhum segundo motor documental):

* `seeds2/report/dossier.py`: o dossiê conhece o motor da rodada (`engine_id`); rodada V2 exige o SEU contrato de dados
  (`REQUIRED_CONCLUDED_V2` = `registro.OBRIGATORIOS`, igualdade testada); `require_complete(d, engine=…)` recusa
  EXPLICITAMENTE gerar documentos de um motor sobre a rodada do outro. Identidade, impressões digitais e SHA-256 de cada
  dado: as mesmas verificações de antes;
* `integracao_v2/documentos.py` (novo): fonte = dossiê + `registro.verificar` (hashes, vistas regeneradas, reauditoria —
  a mesma verificação da Partitura); **figuras** pelo MESMO desenho do 2D-B (`figures.render`: Plotly → matplotlib, PNG
  300 ppp + SVG vetorial) e o MESMO ZIP (`figures.figures_zip`: `manifest.json` com SHA-256 de cada arquivo e dos dados de
  origem); **PDF** com o MESMO miolo de `run_pdf` (capa, cabeçalhos, estilos, tabelas, figuras vetoriais, seções genéricas
  de configuração/condições iniciais/diagnóstico) e seções V2 (resumo selado, aceitações algébrica × dinâmica × física,
  método e escopo, convenções do registro, resultados, armazenamento, advertências do preflight, discussão factual,
  procedência com SHA-256 e a verificação da evidência, limitações); **Excel** com o MESMO escritor de `xlsx` (double exato
  por `repr`, ausente = célula vazia, texto literal, divisão explícita, aviso dos 15 algarismos) e as tabelas gravadas
  (intervalos, fronteiras, janelas, planos), indicadores selados, estratégia, procedência e dicionário. Rodada falha ou
  interrompida ⇒ PDF/Excel de DIAGNÓSTICO; ZIP de figuras recusado. Nunca importa o solver;
* `seeds2/ui/report_exports.render`: o MESMO painel (geração sob demanda, progresso real, cache por rodada, erros sem
  perder a página) aceita opcionalmente o gerador, os rótulos e as ajudas do chamador; V1.6 inalterado;
* `integracao_v2/ui.exportacoes`: área **visível** na página da rodada V2 (rodada local e estudo arquivado), logo após a
  Partitura e fora da vista clássica: **GERAR RELATÓRIO PDF**, **BAIXAR TODAS AS FIGURAS (ZIP)**, **EXPORTAR TABELAS EXCEL
  (.xlsx)**. As figuras do ZIP são de publicação (fundo claro); o tema escuro está na exportação por gráfico (ponto 5) —
  escopo explicitado na ajuda. O ZIP traz as figuras CIENTÍFICAS derivadas dos dados gravados, não capturas da interface.

## 7. Guardas

Exceção nominal `tests/ems_v2/ui_finish01_guard_policy.py` (encadeada no fim da do UI-RUNNING-01; a auditoria do 3D-B a
consulta para o caminho intocado `seeds2/report/dossier.py`): nomes e status exatos e, para os dois arquivos fora das áreas
de interface (`seeds2/report/dossier.py`, `seeds2/ui/report_exports.py`), as linhas REMOVIDAS têm de estar numa lista
explícita — qualquer outra alteração volta a falhar (testado em `tests/ems_v2/test_ui_finish01_guardas.py`). Quatro
asserções antigas mudaram porque o pedido muda o que fixavam (bancadas sem microrrede e no comissionamento; botões do Gestor
vazio; o dossiê 2D-B que não lia rodadas V2 — a recusa dos geradores V1.6 continua, agora nomeando o motor). Os roteiros E2E
anteriores expandem os cartões do Catálogo antes de usar as ações (`tools/e2e/catalogo_util.js`, como o usuário faria) e
contam os downloads «Baixar» por nome exato. **C-DEPLOY-01 NÃO foi aplicada:** as duas
guardas de `requirements.txt` continuam falhando como no `main`.

## 8. Arquivos e justificativa

| Arquivo | Por quê |
|---|---|
| `seeds2/ui/shell.py` | ponto 1 — bancadas nos três contextos |
| `seeds2/ui/gestor.py` | pontos 1 e 2 — bancadas no celular; cartão recolhido (HTML/CSS) |
| `integracao_v2/ui.py` | pontos 3, 4 e 6 — relatório compacto, cartão de rodada, CSS do modal, área de exportações |
| `seeds2/ui/folha_ui.py`, `static/trama/folha.js` | ponto 3 — slot do cartão sob a Folha; texto da prontidão |
| `seeds2/ui/static/trama/execucao.js` | ponto 3 — reabrir o modal a pedido do cartão |
| `seeds2/ui/static/trama/trama.js`, `partitura.js`, `trama.css` | ponto 5 — exportar cada gráfico |
| `seeds2/report/dossier.py` | ponto 6 — dossiê ciente do motor (recusa cruzada explícita) |
| `seeds2/ui/report_exports.py` | ponto 6 — o mesmo painel com gerador/rótulos opcionais |
| `integracao_v2/documentos.py` (novo) | ponto 6 — PDF/ZIP/Excel V2 sobre a infraestrutura do 2D-B |
| `tests/test_ui_finish01.py` (novo), 3 asserções antigas, políticas de guarda | testes e exceção nominal |
| `tools/e2e/seed_ui_finish.py`, `e2e_ui_finish.js`, `check_ui_finish.py`, `run_ui_finish.sh` (novos) | verificação em navegador real e conferência dos arquivos |

## 9. Matriz pedido → alteração → teste → evidência

| Pedido | Alteração | Teste | Evidência |
|---|---|---|---|
| 1 Bancadas sem microrrede | `shell.sidebar_items`, bloco no Catálogo (celular) | `BancadasTest`; E2E fase preparo (5 bancadas abertas e retorno) | `03_barra_lateral_sem_microrrede` |
| 2 Cartões recolhidos | `gestor` (`<details>`, CSS) | `CatalogoTest`; E2E (hover, clique, Tab, Enter/Espaço, toque, sem rolagem) | `01`/`02`/`04` catálogo |
| 3A Checks compactos | `relatorio_preflight` | `PreflightCompactoTest`, `CartaoDeRodadaTest` | `05_etapa04_*` |
| 3B Cartão de rodada | `cartao_rodada` + slot da Folha | `CartaoDeRodadaTest`; testes 3D-A (submit pelo botão); E2E (posição 1366/1440/390, uma rodada) | `05_etapa04_*`, `06_modal` |
| 4 Overlay estável | `MODAL_ESTAVEL_CSS` | `ModalEstavelTest`; E2E (≥ 10 progressos; nitidez por quadro) | GIF `11_overlay_estavel.gif` |
| 5 Gráfico PNG/SVG claro/escuro | `trama.js` (`exportavel`, `svgExport`, `pngExport`) | `PngMetadadosTest`, `ExportarGraficoNoNavegadorTest`; E2E + `check_ui_finish.py` | `07`/`08`, arquivos de exemplo |
| 6 PDF / ZIP / Excel | `documentos.py`, `dossier.py`, `report_exports.render`, `exportacoes` | `DossierPorMotorTest`, `DocumentosV2Test` (arquivos reais, adulteração, sem solver, estudo arquivado, diagnóstico); E2E com motor sabotado | `09`/`10`, PDF/ZIP/xlsx de exemplo |
