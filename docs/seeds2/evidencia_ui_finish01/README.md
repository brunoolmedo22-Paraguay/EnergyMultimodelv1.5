# Evidência visual — UI-FINISH-01

Capturas em navegador real (Chromium/Playwright, 2×) sobre servidores Streamlit locais. **ANTES** = código de `main`
`c29e600`; **DEPOIS** = esta branch. Dados FICTÍCIOS e rotulados de `tools/e2e/seed_ui_finish.py` (missões V2 reais com
HiGHS; nada de microrrede real). As capturas «DEPOIS» vêm do E2E `tools/e2e/run_ui_finish.sh` (exceto `03i`/`03j`, tiradas
sobre os mesmos dados para mostrar a página inteira).

| Arquivo | O que mostra |
|---|---|
| `01a`/`01d` ANTES · `01b`/`01c`/`01e` DEPOIS | Catálogo: cartões cheios de botões × recolhidos (só identidade, estado, resumo e o convite); hover expande só o cartão sob o mouse; no celular o toque no convite expande. |
| `02a` ANTES · `02b` DEPOIS | Barra lateral sem microrrede aberta: as cinco bancadas passam a aparecer. |
| `03a`/`03d`/`03f`/`03h` ANTES · `03b`/`03c`/`03e`/`03g`/`03i`/`03j` DEPOIS | Etapa 04: cartão «Rodada · execução V2» logo abaixo da Folha (o único botão de executar; apto, 1366×768, bloqueado com «Revisar», celular antes da seção); relatório do preflight compacto (resumo, advertências por área com o texto completo a um clique; aprovadas recolhidas) × a lista extensa anterior. |
| `04a` DEPOIS · `04b_overlay_piscava_ANTES.gif` · `04c_overlay_estavel_DEPOIS.gif` | Modal durante uma missão longa: ANTES o fundo perdia o desfoque em alguns quadros (o Streamlit marcava o contêiner como «stale»); DEPOIS o desfoque fica constante em todos os quadros (medido: nitidez idêntica em 30 quadros, 2 deles durante a atualização do fragmento). |
| `05a` ANTES · `05b`/`05c` DEPOIS | Painel da bateria e gráfico principal: botão Exportar e menu PNG/SVG × claro/escuro. |
| `06a` ANTES · `06b`/`06c` DEPOIS | Página da rodada V2: ANTES sem nenhum PDF/Excel/ZIP; DEPOIS a área de exportações visível logo após a Partitura (gerar → baixar). |
| `exemplos/` | Arquivos REAIS baixados pelo E2E: gráfico da operação em PNG claro e escuro (300 ppp) e SVG claro, painel da bateria em SVG escuro, relatório PDF da rodada EXP-02. (O ZIP de figuras e o Excel são conferidos por `tools/e2e/check_ui_finish.py`.) |
