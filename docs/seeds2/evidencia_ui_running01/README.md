# Evidência visual — UI-RUNNING-01

Capturas num navegador real (Chromium/Playwright) sobre um servidor Streamlit local com o HiGHS instalado; microrredes e
cenários de ENSAIO criados por `tools/e2e/seed_piso3da.py` (+ uma missão de 240 h criada com o mesmo apoio
`tests/piso3da_util.criar_cenario_v2`, para ter tempo de exercitar os fluxos) — dados sintéticos de teste, nunca
resultados de microrrede real. Todo progresso visto nas capturas de servidor é o `run.progress` gravado pelo runner V2
durante missões reais.

**Revisão do PR #27:** 02–06, 08 e 14–19 foram refeitas com o código final da revisão (mensagem do desfecho/recusa no
rodapé fixo do cartão). 07 e 09–13 são da primeira rodada (estado «em andamento», sem mensagem; a única diferença
visual é o espaçamento do rodapé).

| Arquivo | O que mostra |
|---|---|
| `01_antes_etapa04_sem_modal.jpg` | Antes: etapa 04 pronta para executar (até aqui só havia o cartão «Execução em andamento…» na página). |
| `02_modal_em_execucao.jpg` | Modal aberto sozinho ao executar: marca, animação, cenário/versão, rodada, N/m/H_L, fases, intervalo k de n, porcentagem, horizonte MPC. |
| `03_painel_oculto_faixa_acompanhar.jpg` | OCULTAR PAINEL: a rodada segue; a faixa «ACOMPANHAR EXECUÇÃO» reabre (overlay com `display: none` computado). |
| `04_confirmar_cancelamento.jpg` | Confirmação explícita antes de cancelar. |
| `05_cancelamento_solicitado.jpg` | Pedido ACEITO pelo servidor; a janela em curso termina e é descartada. |
| `06_cancelada.jpg` | Desfecho real: rodada `interrompida`, `cancelada_pelo_usuario`, nenhum dado gravado. |
| `07_missao_curta_em_execucao.jpg` / `08_concluida_100.jpg` | Missão curta até a conclusão: 100 % só com a rodada `concluida` no banco; em seguida a rodada abre. |
| `09_desktop_1366x768.jpg`, `10_desktop_1280x720.jpg` | Proporção do cartão (42 % e 46 % da altura). |
| `11_tema_escuro_1440x900.jpg` | Tema escuro. |
| `12_movimento_reduzido.jpg` | `prefers-reduced-motion: reduce` (animações desligadas). |
| `13_celular_390x844.jpg` | Celular: 92 % da largura, uma coluna. |
| `14_fluxo_cancelamento.gif` | Sequência 02 → 04 → 05 → 06. |
| `15_animacao_modal.gif` | Animação do cartão (24 quadros a ~110 ms), desenhada pela bancada `tools/e2e/bancada_piso3db.py` com dados de TESTE de `dados_modal` (k = 14 de 48). |
| `16_pedido_recusado_bancada.jpg` | Pedido RECUSADO (`tarde`): o pendente é limpo, «CANCELAMENTO NÃO realizado — <motivo do servidor>», botão de volta ao estado real (desabilitado em auditoria). **Bancada com dados de TESTE**: na aplicação a recusa só ocorre numa corrida (os estados recusáveis já desabilitam o botão); a resposta real é coberta por `RespostaDoServidorTest`. |
| `17_outro_processo_cancelamento_indisponivel.jpg` | Dois servidores sobre o MESMO diretório de dados: no que não executa a rodada, o cancelamento fica desabilitado com o motivo. |
| `18_desktop_1366x768_com_mensagem.jpg`, `19_celular_390x844_com_mensagem.jpg` | Desfecho com mensagem: 50 % da altura (1366×768) e 67 % (390×844); mensagem e ações sempre visíveis (rodapé fixo; só a parte superior rola). |
