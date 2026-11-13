# UI-REDESIGN-01 — navegação, fluxo experimental e identidade visual da Planta

Missão de **interface** pedida pelo responsável sobre `main` `8cbd15c` (merge do PR #24). Nenhuma alteração em `ems_v2/`,
`integracao_v2/`, modelos físicos, motor V1.6, contratos, persistência, critérios de aceitação ou resultados científicos
(auditoria `python tests/ems_v2/ui_redesign01_guard_policy.py` ⇒ `ok: true`). Referências visuais do pedido: pacote
`SEEDS2_OPUS_UI_REDESIGN_2026-11-13` (imagens 01–05, estado anterior). Evidência antes × depois: `docs/seeds2/evidencia_ui_redesign01/`.

## 1. «Console V1.6» → «Bancadas» (barra lateral)

* `seeds2/ui/shell.py`: o grupo «Console V1.6» (Simulação V1.6 / Resultados V1.6, telas sem o EMS hierárquico) saiu de
  `sidebar_items`; no lugar, o grupo **Bancadas** com Solar, Eólica, Bateria, H₂ / PEMFC e Térmica (`shell.BANCADAS`, a
  mesma lista e ordem de `home.BENCHES`). Ação nova do componente `{type:"bancada", fonte}` → `shell.abrir_bancada`, que faz
  EXATAMENTE o que os botões «ABRIR …» faziam (`energy_source`, e `current_page` na solar): mesmas telas, independentes da
  configuração da microrrede, com o retorno de sempre («← FONTES DE ENERGIA»). Fonte desconhecida é ignorada.
* Ícones dos itens = os do **Gestor** (abaixo), num círculo claro na cor da tecnologia.
* O bloco «Ferramentas V1.6» saiu da área principal do Centro de Operação. Como a barra INFERIOR do celular só comporta os
  destinos essenciais, no celular (≤ 760 px) as mesmas bancadas aparecem no fim do Centro de Operação («Bancadas dos
  modelos»); no desktop esse bloco não é exibido (CSS) — nunca as duas formas ao mesmo tempo.
* **Não removido (de propósito):** as vistas `simulacao`/`resultados` continuam em `shell.VIEWS` e roteáveis por URL e pela
  navegação clássica opcional (`SEEDS2_NAV_CLASSICA=1`, usada só pelos roteiros E2E antigos); `seeds2/ui/main.py` e
  `operations.py` são fixados por SHA-256 e o console V1.6 é usado por testes e pela estabilização. `home.benches()`
  continua sendo o código dos botões. Nenhum arquivo foi apagado.
* A execução e os resultados do fluxo experimental ATUAL (etapa 04, rodada, Partitura, Caderno) não mudaram.

## 2. «Etapas do experimento» como fluxo contínuo

* `seeds2/ui/operation_center.py` (`_stages`, `ETAPAS`, `ETAPAS_CSS`): uma faixa única com trilho 01 → 02 → 03 → 04;
  marcador numerado (✓ concluída, ! impedimento), etapa, título, descrição e o estado com o seu detalhe; o trecho do trilho
  é cheio entre etapas concluídas; «próxima» = primeira etapa não concluída. No celular/tablet (≤ 900 px) vira um stepper
  vertical com o trilho à esquerda.
* **A etapa inteira é o alvo**: o botão que já existia (mesma chave `op_open_*` e mesmo nome acessível «ABRIR …») cobre a
  superfície da etapa, transparente; foco de teclado visível sobre a etapa; Enter/clique navegam. Não há mais botão preto
  dentro de cartão. Sem cenário, as etapas ficam indisponíveis (botões desabilitados, «Selecione um cenário»).
* **Estados**: os MESMOS de antes (`S.readiness`, `S.strategy_status`, `execution_ui.stage_state`); nada é decidido aqui.
  A etapa 04 com impedimento continua abrindo a seção 04, onde o preflight explica o bloqueio e o botão de executar
  continua desabilitado.

## 3. Planta com a identidade do Gestor

* **Reutilização sem cópia** (`seeds2/ui/trama.py`): ao registrar um componente de página, `icones_gestor_js()` lê o objeto
  `ICONS` de `static/inventory.js` (o mesmo de `techpicker.js`) e `tokens_gestor_css()` lê as cores `--k-pv … --k-load` de
  `static/kit.css`, e ambos são injetados (`ICONES_GESTOR`, `.pt { --k-* }`). O Gestor não foi alterado; se os ícones ou as
  cores do Gestor mudarem, a Planta e a barra lateral acompanham. A bancada de testes (`tools/e2e/bancada_piso3db.py`)
  monta os componentes do mesmo jeito.
* `static/trama/planta.js`: cada nó = cartão com o **ícone da tecnologia num círculo claro** na cor do Gestor (como na
  referência 05), tipo curto (SOLAR, EÓLICA, H₂ / PEMFC, TÉRMICA, BATERIA) + TAG, nome, nominal do inventário (kWp, kW,
  kWh) e o estado; com rodada, a potência GRAVADA do intervalo. O UID foi para o destaque/painel (menos microtipografia).
  Demanda agregada (cor `--k-load` do Gestor) e PCC têm ícones próprios no mesmo traço — o Gestor não os tem.
* Topologia, ligações e semântica preservadas: barramento único, injetores acima, armazenamento/consumo abaixo, uma ligação
  por nó até um ponto de conexão no barramento; SEM setas nem fluxos; ligação apagada = potência gravada nula; tracejada =
  dado ausente; presente × participou × sem rodada, hover/Tab, clique/Enter e painel de detalhes iguais.
* Painel lateral: nenhum corte nem rolagem horizontal medido entre 400 e 1540 px (antes e depois). O corte visível na
  referência 04 não se reproduziu (pela geometria, o painel começa onde a captura termina).

## 4. Verificação

Ver `PARAMIJEFE.md` (Entrega 20) e `docs/ai/HANDOFF.md`.
