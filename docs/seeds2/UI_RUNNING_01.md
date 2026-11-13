# UI-RUNNING-01 — modal de acompanhamento da execução V2

Missão pedida pelo responsável (pacote `SEEDS2_OPUS_RUNNING_SIMULATION_MODAL_2026-11-13`; referências 01 = cartão
«Execução em andamento» real, 02 = composição de overlay), sobre `main` `9d2bcf0` (merge do PR #26). **O modal é uma
nova experiência de ACOMPANHAMENTO, não um novo motor**: `ems_v2/`, o runner V2 (`integracao_v2/execucao.py`), modelos
físicos, motor V1.6, armazenamento e contratos ficam intactos (auditoria `python tests/ems_v2/ui_running01_guard_policy.py`).
Evidência visual: `docs/seeds2/evidencia_ui_running01/`.

## 1. De onde vem o progresso (fonte de verdade)

O runner V2 já grava, a cada janela MPC, `run.progress` no banco da microrrede (`store.heartbeat_run`):
`{"phase": "fila"|"montagem"|"missao"|"auditoria"|"gravando", "k": intervalos aplicados, "n": K_M, "janelas": n.º de
janelas resolvidas}`; a conclusão grava `{"phase": "concluida"}` junto com dados, resumo e estado, numa única transação.
O cartão «Execução em andamento» é redesenhado por um fragmento Streamlit existente (`execution_ui._live`,
`run_every = 1 s`). O modal é desenhado **pelo mesmo fragmento, com os mesmos dados**: nenhum polling novo, nenhuma thread
nova, nenhum rerun extra da página.

* Porcentagem **só** na fase `missao` com `k < n` (`k / n`, truncada); nas fases sem contador (fila, montagem,
  auditoria, gravação) e com todos os intervalos aplicados a barra é **indeterminada**; **100 % só com a rodada
  `concluida` no banco**. Nenhum tempo restante é estimado.
* Além da barra, uma faixa do **horizonte recedente real**: aplicado `0…k` e a próxima janela de `N` intervalos a partir
  de `k` (N, m, H_L do manifesto da rodada).
* Fases mostradas como etapas (Fila → Montagem → Missão MPC → Auditoria → Gravação), a atual destacada.

## 2. Fluxos

| Momento | Comportamento |
|---|---|
| Início | «EXECUTAR MISSÃO V2» continua o MESMO botão (pedido idempotente por `request_id`, desabilitado com rodada ativa; `start_run` recusa uma segunda rodada ativa). Aceita a rodada, o fragmento a acompanha e o modal abre sozinho. Falha de início (preflight/rodada ocupada) continua sendo o erro da página — nenhuma rodada fictícia. |
| Em andamento | Barra, intervalo, janelas, fase e horizonte a cada 1 s; o cartão da página continua como fallback. |
| Ocultar / Escape / clique fora | Só esconde (estado do navegador por rodada, `sessionStorage`); a execução segue no servidor; aparece «ACOMPANHAR EXECUÇÃO» para reabrir. Nunca cancela. |
| Recarga / outra aba | A rodada ativa é relida do banco (a mesma; nenhuma nova). Na mesma aba, o painel oculto continua oculto (reabre por «ACOMPANHAR EXECUÇÃO»); numa aba nova o modal abre sozinho ao chegar à tela de execução. Uma MUDANÇA de desfecho (concluída, falha, cancelada) reabre o painel. |
| Conclusão | «Concluída» (100 %) por um ciclo e abertura automática da rodada — o mesmo destino de antes (testes e roteiros dependem dele). |
| Falha / missão interrompida | «Falha na execução» / «Missão interrompida» com a mensagem REAL gravada pelo runner; o desfecho fica visível (modal e cartão) até o usuário escolher «VER DIAGNÓSTICO» ou «FECHAR/OK». Nunca vira sucesso nem «cancelada». FECHAR do modal = «OK» da página (o desfecho sai da página inteira); VER DIAGNÓSTICO abre a rodada. |

## 3. Cancelamento — auditoria e decisão

**Não existia API de cancelamento.** Auditoria do runner V2 (`integracao_v2/execucao._executar`):

* entre janelas (`executar_janela_a_janela` → `ao_avancar`), antes da auditoria e antes da gravação o runner chama
  `beat(force=True)` → `store.heartbeat_run(run, OWNER, …)`, que só atualiza linhas `em_execucao` DESTE dono; falso ⇒
  `RunStateError` ⇒ o runner retorna **sem gravar nada**;
* `finish_run` e `fail_run` abrem a rodada sob o bloqueio de escrita da microrrede e exigem `em_execucao` + dono
  (`_open_run`): a conclusão e qualquer finalização são mutuamente exclusivas e atômicas.

Logo, **um cancelamento cooperativo seguro já é possível pela API existente**, sem tocar no runner, no solver nem nos
contratos: `integracao_v2/ui.cancelar(store, run)` faz `store.fail_run(run, runner.OWNER, {"kind":
"cancelada_pelo_usuario", …}, state="interrompida")`. Garantias (testadas com HiGHS real e uma pausa determinística entre
janelas, só no teste):

* só cancela rodada `em_execucao` cuja thread roda NESTE processo (`runner.is_running_here`); outro processo ⇒ recusa
  explicada; rodada já terminada ⇒ «nada foi cancelado» (a corrida com `finish_run` é resolvida pela transação);
* nas fases `auditoria`/`gravando` o botão fica desabilitado com explicação (a missão já terminou; descartar o trabalho
  seria perder um resultado prestes a ser gravado);
* a janela em curso NÃO é interrompida no meio do solver: termina e é descartada; até lá o modal diz «Cancelamento
  solicitado» e só depois de a thread terminar diz «Cancelada»;
* estado final `interrompida` (estado já existente), `error.kind = cancelada_pelo_usuario`, mensagem com os intervalos
  aplicados; **nenhum dado, resumo ou custo** é gravado; o runner não sobrescreve o desfecho; a microrrede fica livre para
  uma nova rodada; nada é reexecutado automaticamente; outras rodadas não são afetadas.
* confirmação explícita antes do pedido («Cancelar esta rodada? … SIM, CANCELAR»); um pedido por vez (cliques
  duplicados ignorados);
* o modal só sai de «CANCELAMENTO SOLICITADO…» com a RESPOSTA do servidor ao MESMO pedido (§5).

Limitação documentada: o cancelamento é por **janela** (o solver não é abortado no meio de uma resolução; o tempo até a
confirmação é o da janela em curso, limitado pelo `time_limit_s` declarado). Abortar o HiGHS no meio exigiria mexer no
adaptador do solver (`ems_v2`), o que não foi feito.

## 4. Visual e acessibilidade

* Componente `seeds2/ui/static/trama/execucao.js` (Trama/Partitura, `st.components.v2`, estilos `.pt.mx` em `trama.css`),
  com os ícones e as cores do Gestor (`trama.icones_gestor_js`/`tokens_gestor_css`).
* Cartão central `min(50vw, 680px)` × no máximo `50dvh` (medido: 42–46 % da altura em 1366×768, 1280×720 e 1440×900),
  overlay translúcido com desfoque leve; celular: `92vw` × até `78dvh` (medido 58 % em 390×844); rolagem interna só se
  necessária, só na parte superior: o rodapé (mensagem do desfecho/recusa + ações) fica preso embaixo e sempre visível;
  sem rolagem horizontal.
* Marca **SEEDS2 | RUNNING SIMULATION** com o traço da plataforma; animação ORIGINAL em SVG/CSS: mini-diagrama abstrato
  (fontes → barramento → armazenamento/rede, pulsos delicados) — decorativo (`aria-hidden`), não representa fluxos;
  parada fora de «em andamento».
* `role="dialog"`, `aria-modal`, nome e descrição acessíveis, barra `role="progressbar"` com `aria-valuenow`/`valuetext`,
  texto do progresso em `aria-live="polite"`; foco no diálogo ao abrir, Tab preso, Escape oculta, foco devolvido a
  «ACOMPANHAR EXECUÇÃO»; `prefers-reduced-motion` desliga pulsos, brilho e transições.
* A estrutura do componente é montada uma vez por rodada e só atualizada: a animação não reinicia e o foco do teclado não
  é perdido a cada ciclo.

## 5. Revisão do PR #27 (correções)

1. **Visibilidade REAL do modal e da faixa.** `.pt.mx .mx-fundo { display: grid }` e `.pt.mx .mx-faixa { display: flex }`
   podiam vencer o atributo `hidden`. Medido em Chromium: a ocultação só funcionava graças à regra geral
   `.pt [hidden] { display: none !important }`; sem ela o overlay continuava `display: grid` em 1366×768 com
   `hidden === true` (e interceptava os cliques). Regra EXPLÍCITA acrescentada:
   `.pt.mx .mx-fundo[hidden], .pt.mx .mx-faixa[hidden] { display: none !important; }`. Os testes medem `getComputedStyle`
   e a caixa (e, no servidor real, qual elemento recebe o clique no centro da tela) em: abrir, ocultar, ciclos do
   fragmento com o painel oculto, recarga, reabrir, Escape, clique fora, desfecho (reabre) e FECHAR — também com a regra
   geral REMOVIDA, provando que a regra do modal basta sozinha.
2. **Pedidos de cancelamento recusados.** O pedido leva um identificador (`t`); `integracao_v2/ui._acao_modal` grava a
   resposta REAL de `cancelar` vinculada a ele (`op_v2_cancel_resp_<rodada>`), e o modal a recebe em
   `resposta_cancelamento`. Só a resposta ao MESMO pedido resolve o pendente: aceito ⇒ o estado gravado decide
   («Cancelamento solicitado» → «Cancelada»); recusado (`tarde`, `outro_processo`, `finalizada`, `inexistente`) ⇒ o
   pendente é limpo, o botão volta ao estado real (desabilitado se o servidor também o desabilitou) e o modal mostra
   «Cancelamento NÃO realizado — <justificativa do servidor>» até uma nova tentativa ou a mudança de estado; SEM resposta
   em 20 s ⇒ o pendente também é limpo, com «O servidor não respondeu… nada indica que a rodada tenha sido cancelada».
   Confirmação explícita e bloqueio de cliques duplicados preservados (um só pedido enviado). A recusa só ocorre numa
   corrida (os estados recusáveis já desabilitam o botão), por isso é exercitada pela bancada + teste do servidor.
3. **Encontrados na verificação e corrigidos:**
   * FECHAR/VER DIAGNÓSTICO do modal só escondiam o painel: `st.rerun` num callback de componente não tem efeito, e o
     cartão do desfecho e a faixa ficavam na página. Agora a ação marca `op_v2_rerun_app` e o ciclo seguinte do
     fragmento faz `st.rerun(scope="app")` — mesmo efeito do «OK»/«VER DIAGNÓSTICO» da página.
   * A mensagem (que tem `overflow: auto`) encolhia até sumir dentro do cartão limitado a 50dvh. Agora os filhos do
     cartão não encolhem e a mensagem fica no rodapé fixo, junto das ações.

O EMS, o runner, os modelos e a persistência continuam intocados (auditoria `ok: true`). Guardas preexistentes de
`requirements.txt`: proposta separada em `docs/seeds2/PROPOSTA_C_DEPLOY_01.md` (não aplicada).
