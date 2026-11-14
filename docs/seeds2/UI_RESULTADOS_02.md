# UI-RESULTADOS-02 — visualizações científicas, Visão Geral e relatório PDF integrado

Pedido do responsável (14/11/2026, missão «SEEDS2 — UI-RESULTADOS-02»). Branch `ccr-3d9d6a3e-67m47p` a partir de `main`
`e765028` (merge do PR #32). PR para `main` **sem merge** até autorização expressa.

Não houve redesenho: a página de resultados (Partitura) continua com a mesma identidade, navegação, inspeção temporal e
exportações; foram ACRESCENTADAS capacidades de análise. Nada em `ems_v2/`, modelos físicos, motor V1.6, runner,
armazenamento, contratos de dados, marco Trama (`integracao_v2/trama_frame.py`), geradores 2D-B, painel do 2D-B
(`seeds2/ui/report_exports.py`) ou `integracao_v2/documentos.py` mudou (auditoria `tests/ems_v2/ui_resultados02_guard_policy.py`).

## 1. Matriz pedido → alteração → teste → evidência

| # | Pedido | Alteração | Teste | Evidência |
|---|---|---|---|---|
| 01 | Tarifa como curva escalonada | `partitura.js` `laneTarifa` (degrau por intervalo `[t_k, t_k+1)`, início de cada período marcado e rotulado; importação × remuneração de exportação) em Operação, Economia e nos painéis Bateria, Rede e Custos; `tarifaExportacao` (omitida só com evidência: sentidos declarados sem exportação) | `DerivadasTest.test_tarifa_de_exportacao_*`, `test_mudancas_tarifarias_*`; `InterfaceTest.test_tarifa_como_curva_escalonada_em_todas_as_vistas` (caminhos `M…H…` sem curvas) | `evidencia_ui_resultados02/01_operacao_tarifa.png`, `05_painel_rede.png` |
| 02 | Demanda nas fontes | `demRef`/`legDem`/`tipDem`: demanda TOTAL (linha fina neutra) nos gráficos de POTÊNCIA de Solar, Eólica, Bateria, PEMFC e Rede; demanda ATENDIDA pontilhada só com déficit gravado; legenda e dica; nunca somada; ausente em SOC/energia/tarifa/custo | `InterfaceTest.test_demanda_de_referencia_so_nos_graficos_de_potencia_das_fontes` | `03_painel_solar.png`, `04_painel_bateria.png`, `05_painel_rede.png` |
| 03 | Aba Carga líquida | recurso `liq` no explorador (entre Carga e Custos): (A) demanda × carga líquida com a faixa renovável; (B) compensação pelos controláveis (suprem acima de zero, absorvem abaixo); (C) fechamento por intervalo; cartões da missão e cascata de energia (`cargaLiquida`, `cascata`) | `DerivadasTest.test_carga_liquida_*` (definição, negativa preservada, sem dupla contagem, ausente ⇒ N/D, sem renováveis = demanda); `InterfaceTest.test_aba_carga_liquida` | `06_painel_carga_liquida.png` |
| 04 | Lente Visão Geral | lente `visao` (última; NUNCA restaurada ao abrir uma rodada): KPIs (selado × derivado), energia por fonte, participação (rosca com denominador explícito), balanço entradas × saídas com fechamento, participação temporal (áreas em degrau + demanda; faixa percentual), indicadores complementares (`visaoGeral`, `complementares`, `areas`) | `DerivadasTest.test_visao_geral_*`; `InterfaceTest.test_visao_geral`, `test_abertura_em_operacao_e_visao_geral_nunca_restaurada` | `02_visao_geral.png`, `02b_visao_geral_temporal.png` |
| 05 | Relatório PDF | `partitura.js` `relatorio` (desenha com as MESMAS funções, missão completa, tema claro) + `svgPdf`; `integracao_v2/relatorio_visual.py` (confere hash e evidência, diagrama) + `integracao_v2/svg_pdf.py` (SVG restrito → vetores reportlab); botão «Relatório PDF» na barra da Partitura e o MESMO botão «GERAR RELATÓRIO PDF» do painel (`integracao_v2/ui.py`) | `RelatorioC4Test` (C4: missão completa com a tela ampliada, mesmo desenho da tela, seções e fontes, PDF paginado, evidência intacta, recusas, sem solver), `TopologiasTest`, `SvgRestritoTest`, `PainelExportacoesTest` | `relatorio_C4_UI_RESULTADOS_02.pdf`, `07_relatorio_pronto.png`, `08_exportacoes.png`, páginas `pdf_p*.png` |

## 2. Decisões (registradas; revisáveis pelo responsável)

- **D-UR02-01 — abertura em Operação.** A lente Visão Geral nunca é restaurada do `sessionStorage` ao montar a Partitura
  (abrir/reabrir/recarregar a rodada ⇒ Operação). As outras lentes mantêm o comportamento aprovado no 3D-B3 (restauradas
  na mesma aba) — testado.
- **D-UR02-02 — onde entra a demanda.** Nos gráficos de potência dos painéis das fontes (o «seletor de fontes»). As raias
  compactas da lente Operação não mudaram: a raia «Atendimento» já traz a demanda e, numa raia de 50 px, a demanda
  esmagaria a série da fonte.
- **D-UR02-03 — remuneração de exportação.** Desenhada quando gravada; série vazia só é «não aplicável» se os sentidos do
  PCC declarados excluírem a exportação; exportação permitida (ou sentidos não declarados) com série vazia = N/D (mesma
  regra de evidência do C-3DB-07).
- **D-UR02-04 — carga líquida.** `P_liq = P_demanda − Σ P_renovável aproveitada` (depois do vertimento). Compensação =
  descarga + PEMFC + importação + não atendida − carga − exportação; o fechamento por intervalo é, pela equação de balanço,
  o resíduo gravado (`residuo_balanco_kW`) — a interface mostra a diferença entre os dois. As séries são as gravadas por UID
  (arranjos FV, bancos, unidades PEMFC), somadas uma única vez por tecnologia.
- **D-UR02-05 — Visão Geral.** Prioridade aos indicadores SELADOS (`indicadores_selados`: `E_renovavel_usada_kWh`,
  `E_bess_carga/descarga_kWh`, `E_geracao_kWh`, `E_curtailment_kWh`); somas por tecnologia e razões são «derivado». A
  participação energética usa as INJEÇÕES do barramento como denominador (escrito no centro da rosca); a descarga da bateria
  é hachurada e sempre acompanhada da energia carregada (não é geração primária); carga e exportação ficam nas SAÍDAS.
- **D-UR02-06 — arquitetura do PDF.** O navegador desenha (as MESMAS raias, painéis, cartões e funções derivadas da
  interface, sem uma segunda implementação), o servidor confere e diagrama. Alternativas descartadas: navegador sem
  interface no servidor (exigiria Chromium e mudança no `requirements.txt` protegido do deploy) e redesenho dos gráficos em
  Python (duas implementações que podem divergir — o pedido pede para evitar). O pacote é entrada NÃO confiável: hash do
  marco remontado dos dados gravados, evidência verificada (`registro.verificar`), limites de tamanho, SVG restrito, texto
  sempre escapado.
- **D-UR02-07 — relatório técnico anterior preservado.** `documentos.pdf` continua igual (API, diagnóstico de rodadas
  falhas/interrompidas, rodadas sem Partitura). O relatório visual reorganiza TODO o seu conteúdo científico na seção
  Evidência (configuração, condições iniciais, método e escopo, advertências do preflight, discussão factual, procedência com
  SHA-256, verificação e limitações — que fecham o documento).
- **D-UR02-08 — diagramação.** A4 paisagem (eixos de tempo largos); capa escura com violeta e a demanda GRAVADA da missão
  desenhada como «partitura»; páginas internas claras (impressão); sumário com páginas e marcadores do PDF; uma página por
  fonte com o gráfico à esquerda e os cartões à direita, como no painel da interface; mesma escala px → pt em todo o
  documento (textos do mesmo tamanho); texto na fonte DejaVu Sans comprimido horizontalmente quando necessário para ocupar o
  MESMO espaço medido no navegador.
- **D-UR02-09 — Decisão completa.** Tapete de decisões (24 janelas por gráfico, recortado ao trecho de tempo coberto), a
  decisão de CADA janela (energia planejada × executada e despacho planejado) em galeria 3 × 3, o sinal V(E) de cada
  decisão em galeria 4 × 3, decisões sem sinal listadas com o motivo e a tabela previsto × realizado por bloco.
- **D-UR02-10 — tabelas originais.** No PDF, listadas com linhas, colunas e SHA-256; os valores completos ficam no Excel e
  no `.seeds2study.zip` (a vista clássica também os mostra).

## 3. Limites conhecidos

- O relatório visual precisa da Partitura aberta no navegador (é ela quem desenha); gerar o PDF da rodada C4 leva ~14 s
  (≈ 1,4 s de desenho, o resto de diagramação). Sem resposta da Partitura em 180 s, o painel orienta usar o botão dela.
- A fonte do PDF (DejaVu Sans) difere da fonte da tela; os textos são comprimidos para caber no mesmo espaço (no limite de
  72 %).
- Os painéis seguem exatamente a interface: o que a interface não mostra (p. ex. térmica, que o motor V2 não representa)
  também não aparece.

## 4. Arquivos

Modificados: `seeds2/ui/static/trama/{partitura.js,trama.js,trama.css}`, `integracao_v2/ui.py`,
`tests/ems_v2/exemplos01_guard_policy.py` (gancho), seis asserções antigas em `tests/test_piso3db_{trama,nd,lentes}.py`
(fixavam a lista de recursos do explorador), `tools/e2e/{bancada_piso3db.js,check_ui_finish.py}`.
Novos: `integracao_v2/relatorio_visual.py`, `integracao_v2/svg_pdf.py`, `tests/test_ui_resultados02.py`,
`tests/ems_v2/{ui_resultados02_guard_policy.py,test_ui_resultados02_guardas.py}`, `tools/e2e/{run_ui_resultados02.sh,
e2e_ui_resultados02.js,check_ui_resultados02.py}`, este documento e `docs/seeds2/evidencia_ui_resultados02/`.
