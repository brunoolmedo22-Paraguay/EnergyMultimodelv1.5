# PARAMIJEFE — Relatório técnico para auditoria independente

> Canal permanente de comunicação entre o agente construtor (Claude Code) e o auditor independente. Cada missão
> acrescenta uma entrega (seção "Histórico de entregas" no fim) sem apagar decisões anteriores. O código e os
> testes são a fonte de verdade; aqui ficam o raciocínio, os contratos e a evidência.

---

## Entrega 1 — SEEDS2 Piso 2A · Centro de Operação · Fundação Operacional

### 1. Identificação

| Campo | Valor |
|---|---|
| Projeto | SEEDS2 v2.0 sobre Energy MultiModel V1.6 (`brunoolmedo22-Paraguay/EnergyMultimodelv1.5`) |
| Piso / missão | **Piso 2A** — Centro de Operação, fundação operacional (primeira missão de construção do Piso 2) |
| Data | 2026-11-06 |
| Base | `main` em `50ef4d6` ("SEEDS2: Gestor de microrredes (PR #5)") — PR #5 **integrado** (squash, 2026-11-06 10:59 UTC) |
| Rama | `claude/seeds2-piso2a-centro-operacao` |
| PR | [#6](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/6) (sem merge; aguarda auditoria do responsável) |
| Estado | Implementado e verificado na rama; **não integrado** em `main` |
| Commits de código | `56c71fa` (backend, domínio e interface), `6d18ea6` (testes, E2E, correções e documentação). O commit seguinte só preenche PR/SHAs neste relatório; o SHA final da rama é informado na resposta da entrega. |

### 2. Resumo executivo

**Solicitado:** a fundação do Piso 2 — Centro de Operação como início permanente da microrrede comissionada,
identidade da microrrede como contexto ("perfil") na barra superior, módulo independente de **cenários
operativos** persistentes por microrrede, módulo funcional de **Inicialização** (estados iniciais por equipamento
com validação em três categorias), persistência versionada sem romper as garantias H-01/H-02/H-03, contratos para
os Pisos 2B/2C/2D e o protocolo `PARAMIJEFE.md`.

**Entregue:**
- Vista **Centro de Operação** (`operacao`) substitui o antigo "Início"; microrrede não comissionada continua no
  comissionamento; `?view=inicio` é redirecionado (links antigos).
- Barra superior: controle compacto de **identidade** (avatar com iniciais, nome, ID curto, revisão do inventário)
  com **TROCAR MICRORREDE**; navegação agrupada *operação (Centro de Operação · Simulação) | gestão física (Gestão
  da Microrrede) | resultados (Resultados)*; **Alcance** como link secundário de documentação.
- **Cenários** (`seeds2/operation/`): criar, nomear/descrever, editar, listar, abrir, duplicar (cópia
  independente), retomar após reinício; vínculo explícito com a revisão do inventário + detecção de deriva +
  atualização de referência explícita (`rebase`) que preserva estados órfãos.
- **Persistência**: esquema v3 do banco DE CADA microrrede (`scenarios` + `scenario_versions` append-only), apenas
  tabelas novas, migração com cópia `.bak-v2`; concorrência otimista por versão; incarnação e revisão-base
  verificadas dentro da transação da microrrede.
- **Inicialização**: controles gerados do inventário de referência (bateria: SOC por banco; PEMFC: estado,
  unidades em operação, potência; térmica: estado, potência; FV/eólica: disponibilidade), com **erro de
  coerência** (impede salvar), **advertência técnica** (permitida) e **capacidade científica pendente** (registrada,
  não interpretada pelo EMS V1.6), além de "não definido".
- **Contratos** para 2B (`ForecastInput`, slots de previsão), 2C (`RunReference`, estados de execução) e 2D
  (documento JSON autossuficiente) — sem implementar esses pisos.
- Testes: 34 novos (23 de domínio/persistência + 11 de interface) e E2E em Chromium do fluxo do Piso 2A; suíte
  completa e E2E existentes repetidos (seção 9).

**Pendente (fora do escopo, intencionalmente):** Previsões (2B), Estratégia EMS e Execução (2C), Arquivo científico
(2D); aplicar o cenário às rodadas; reformular o tratamento de SOC/`n_ini` no EMS (piso do otimizador); exclusão/
arquivamento de cenários; cenários no backup ZIP.

### 3. Estado anterior (encontrado em `main` `50ef4d6`)

- `app.py` → shell `seeds2/ui/main.py`: Gestor de microrredes → [Comissionamento] → **Início** (`home.py`: hero,
  KPIs do inventário, esquema do balanço, prontidão para o console V1.6, últimas rodadas, bancadas V1.6 e um
  cartão "Centro de Operação — Próximo piso" sem ação) · Gestão · Simulação · Resultados · Alcance.
- Barra superior (`static/topbar.js`): marca + nome da microrrede sob o logotipo, navegação plana com "Alcance",
  botão TROCAR MICRORREDE separado.
- Persistência: `registry.db` (catálogo, L1) + `microgrids/<uid>/seeds2.db` (`MicrogridStore`, L2, esquema **v2**:
  `microgrid`, `revisions`, `blobs`, `simulation_runs`, `meta`). Garantias H-01 (lápide sob L2), H-02 (exclusão
  vinculada à incarnação), H-03 (leitura em instantâneo único).
- Já existia no documento da microrrede `run_conditions.battery_soc0_pct` (SOC inicial da rodada V1.6, editado na
  Simulação) — condição da rodada **dentro** da configuração física versionada. Não foi alterado.
- HANDOFF desatualizado: dizia "PR #5 pendiente; no integrado". Verificado via GitHub: PR #5 **merged** em
  2026-11-06 (`50ef4d6`). Corrigido em `docs/ai/HANDOFF.md`.
- Linha de base medida antes de qualquer alteração: `python -m pytest tests/ -q` → **237 passed** (108 s).

### 4. Decisões arquitetônicas

| # | Tema | Alternativas | Escolha e justificativa |
|---|---|---|---|
| D1 | Onde guardar cenários | (a) `registry.db`; (b) banco novo por microrrede (`scenarios.db`); (c) tabelas novas no `seeds2.db` da microrrede | **(c)**. Herda sem código novo a lápide/incarnação (H-01/H-02), a leitura de instantâneo (H-03), a exclusão física junto com a microrrede e a FK para `revisions`. (a) criaria base global (proibido); (b) exigiria um segundo bloqueio L2 e um segundo protocolo de exclusão. |
| D2 | Versionamento | (a) sobrescrever; (b) só versão atual + contador; (c) estado atual + histórico append-only | **(c)** `scenarios` (estado atual, `version`) + `scenario_versions` (imutável por triggers). Permite ao Piso 2C referenciar `(scenario_uid, version)` imutável e auditar edições. Independe das revisões do inventário (requisito explícito). |
| D3 | Conflito entre sessões | (a) último grava; (b) bloqueio pessimista; (c) concorrência otimista | **(c)**, mesmo padrão do inventário (`ConflictError`): `save_scenario(doc, expected_version)` compara a versão dentro de `BEGIN IMMEDIATE`; perdedor recebe `ScenarioConflictError`, a edição dele permanece na sessão, e a interface oferece recarregar. Nada é sobrescrito em silêncio. |
| D4 | Relação cenário × inventário | (a) só `revision`; (b) cópia integral do documento; (c) referência + instantâneo das características físicas relevantes | **(c)** `inventory_ref`: revisão, impressão digital da configuração, impressão digital do inventário físico e, por equipamento (id estável), tipo/nome/tag/habilitado/impressão física + grandezas de referência (energia, limites de SOC e sua origem, quantidade e potência por unidade PEMFC, Pmín/Pmáx térmica...). Valida sem reler a revisão e torna o documento autossuficiente (portabilidade 2D) sem duplicar a configuração inteira. A loja confere que a revisão-base existe com a mesma impressão digital (FK + verificação). |
| D5 | Inventário mudou depois | (a) migrar automaticamente; (b) bloquear; (c) detectar e atualizar explicitamente | **(c)** `drift()` (incluídos/retirados/alterados, comparando impressões físicas — rótulos como nome/tag/notas não contam) e `rebase()` sob ação explícita: mantém estados dos que continuam, cria estado padrão para novos, move estados de retirados para `initialization.orphaned` (preservados, não aplicados). Erros de coerência revelados pela nova referência não bloqueiam o rebase (ficam visíveis para correção). |
| D6 | Estado padrão de um equipamento no cenário | (a) presumir valores "típicos"; (b) tudo vazio; (c) disponível + demais campos não definidos | **(c)**. Disponibilidade "disponível" corresponde à hipótese já implícita na V1.6 (todo equipamento habilitado participa); SOC, estado e potência ficam **não definidos** (regra 7 do CLAUDE.md: não inventar). |
| D7 | Limites de SOC | (a) bloquear fora de [min,max]; (b) aviso | **(b)**, por decisão do responsável. Hierarquia: físico 0–100 % (erro; o modelo de bateria exige SOC ∈ [0,1]); restrição operacional deliberada (`soc_limits_source` ∈ fabricante/instalação/migrado) e intervalo recomendado (`sugerido`) → advertência + pendência do EMS. Extremos (<5 % ou >95 %) → advertência adicional. |
| D8 | Validar no salvamento | (a) gravar tudo; (b) recusar erros estruturais e de coerência | **(b)** `check_for_save`: estrutural/coerência → `ScenarioValidationError`, nada gravado; avisos e pendências não bloqueiam. A cópia de trabalho continua na sessão (sem perda). |
| D9 | Vista e rota | (a) manter `inicio` e adicionar aba; (b) nova vista `operacao` + alias | **(b)** rota canônica `operacao`; `VIEW_ALIASES = {"inicio": "operacao"}` em `shell.route()/go()` mantém links antigos. O conteúdo útil do antigo Início foi preservado em seções secundárias (expansores) do Centro. |
| D10 | Controles da Inicialização | (a) componente JS; (b) widgets nativos em cartões com borda | **(b)** testável com AppTest, acessível e compatível com tablet; chaves de widget renovadas por `op_token` ao recarregar/salvar. |
| D11 | Etapas futuras | (a) botões desabilitados "em breve"; (b) cartões informativos sem controles | **(b)** "Não implementado" + piso previsto; nenhum botão (requisito "no crear botones falsos"). Teste automatizado e E2E verificam a ausência. |
| D12 | Componente `areas` (cartões do antigo Início) | manter sem uso / remover | **Removido** (`static/areas.js/.css`): seu único uso era o Início; nenhum teste/E2E o referenciava. |
| D13 | `APP_VERSION` | manter `2.0.0-piso1` / atualizar | `2.0.0-piso2a` (gravado em manifestos de backup e no PDF; deve identificar o código que os gerou). |

### 5. Implementação

**Pacote `seeds2/operation/` (domínio, sem UI e sem ciência)**

- `scenarios.py` — documento `seeds2-scenario` v1:
  ```
  {schema, schema_version, scenario_uid(hex32), name, description,
   microgrid: {uid, incarnation},
   inventory_ref: {config_revision, config_fingerprint, inventory_fingerprint,
                   equipment: {eq_id: {kind, name, tag, enabled, fingerprint, nominal_kW, ...referência física}}},
   initialization: {equipment: {eq_id: estado}, orphaned: {eq_id: {state, reference, orphaned_at_revision}}},
   forecasts: {},            # Piso 2B
   ems_strategy: null,       # Piso 2C (qualquer valor ≠ null é recusado nesta versão)
   lineage: {created_at, duplicated_from: null | {scenario_uid, version, name}}}
  ```
  Funções: `equipment_fingerprint` (exclui `created_at, updated_at, notes, name, tag`), `inventory_fingerprint`,
  `inventory_reference`, `new_scenario`, `duplicate`, `structural_errors`, `findings`, `check_for_save`,
  `drift` → `Drift(added, removed, changed, same_revision, inventory_changed)`, `rebase`, `readiness`
  (Inicialização + três etapas "Não implementado"; `executable` sempre `False`).
- `initialization.py` — `equipment_reference(eq)`, `default_state(kind)`, `FIELDS` por tipo, `validate_state`,
  `validate` (inclui pendência global para SOC distintos entre bancos), `Finding(level, eq_id, field, message)`,
  `summarize`. Regras na seção 8.
- `contracts.py` — `FORECAST_SLOTS`, `FORECAST_SOURCE_TYPES`, `ForecastInput`, `forecast_errors`,
  `RunReference`, `run_reference(stored_scenario)`, `RUN_STATES`.
- `service.py` — `create` (exige microrrede comissionada e usa a revisão **salva**), `duplicate` (da versão salva),
  `save`, `rebase`. Todas passam pelo `MicrogridStore`.

**`seeds2/microgrid/store.py`**
- `MIGRATIONS` v3 (tabelas/triggers, seção 6); `StoredScenario`; `ScenarioConflictError`, `ScenarioNotFound`.
- `create_scenario(doc, origin, note)`, `save_scenario(doc, expected_version, note, origin)`,
  `get_scenario(uid, version=None)`, `list_scenarios()`, `scenario_history(uid)`; `_check_scenario_base`
  (identidade, incarnação, revisão-base + impressão digital) executado **dentro** de `_tx()`.

**Interface (`seeds2/ui/`)**
- `operation_center.py` (novo): painel e módulo de Inicialização (seção 7); estado de sessão `op_*`.
- `main.py`: rota `operacao` como início da microrrede comissionada; despacho para `operation_center.render()`;
  dados de identidade para a barra.
- `shell.py`: `VIEWS` com `operacao`, `VIEW_ALIASES`, `NAV_ACTIVE` agrupado `(view, rótulo, grupo)`, `NAV_DOCS`,
  `SCENARIO_KEY`; `go()` preserva `?mg=` e `?sc=`; `topbar(..., site_sub, mg_name, aux)`.
- `static/topbar.js/.css`: controle de identidade `.tb-mg` (`.tb-av`, `.tb-site`, `.tb-sub`, `.tb-switch`),
  separadores de grupo `.tb-sep`, link de documentação `.tb-doc`.
- `home.py`: refatorado em `installation_facts`, `identification_notice`, `installation_summary`, `benches`
  (conteúdo preservado, exibido em expansores do Centro).
- `commissioning.py`, `gestor.py`: redirecionam para `operacao`.

**Fluxos**
1. Gestor → ABRIR → `session.open_microgrid` (limpa a sessão) → `main` → comissionada? `operacao` : `comissionamento`.
2. Centro → "＋ NOVO CENÁRIO" → formulário → `service.create` → v1 sobre a revisão salva → selecionado.
3. ABRIR INICIALIZAÇÃO → widgets escrevem na cópia `op_work` → constatações ao vivo → SALVAR CENÁRIO →
   `service.save(work, op_base_version)` → nova versão | `ScenarioValidationError` | `ScenarioConflictError`.
4. Inventário salvo muda (Gestão) → cartão "Inventário mudou" com a lista → "Atualizar referência para a revisão N"
   → `service.rebase`.

### 6. Persistência e migrações

- **Esquema do banco da microrrede v2 → v3** (`PRAGMA user_version`): somente `CREATE TABLE scenarios`,
  `CREATE TABLE scenario_versions` e dois triggers de imutabilidade. Nenhuma linha/tabela existente alterada.
  Executada pelo mecanismo existente: uma transação `BEGIN IMMEDIATE`, cópia `.bak-v2` via API de backup do SQLite
  antes, rollback total em falha. Banco mais novo que o software continua recusado.
  ```sql
  scenarios(scenario_uid PK CHECK len=32, microgrid_uid, name CHECK não vazio, version CHECK>=1,
            base_revision REFERENCES revisions(revision), base_fingerprint, fingerprint, document,
            origin DEFAULT 'new', created_at, updated_at)
  scenario_versions(scenario_uid REFERENCES scenarios, version, microgrid_uid, base_revision REFERENCES revisions,
                    base_fingerprint, fingerprint, document, saved_at, note, origin, PK(scenario_uid, version))
  + triggers BEFORE UPDATE/DELETE ON scenario_versions → RAISE(ABORT)
  ```
- **Isolamento:** tabelas no banco de cada microrrede; nenhuma tabela de cenários em `registry.db` (verificado em
  teste). Documento de outra microrrede → `IdentityError`; uid de cenário de outra microrrede → `ScenarioNotFound`.
- **Exclusão e reimportação:** o banco inteiro (com cenários) segue o protocolo H-01/H-02; a microrrede reimportada
  com o mesmo UID tem nova incarnação e nenhuma tabela herdada. Referências antigas (`MicrogridStore` em cache,
  sessão aberta) → `MicrogridDeletedError` em leitura e escrita; documento da incarnação antiga → `IdentityError`.
- **Garantias mantidas:** gravações só via `MicrogridStore._tx` (lápide/incarnação verificadas sob L2); leituras via
  `_read` (instantâneo único); nenhum bloqueio aninhado novo; L1 não é tocado.
- **Compatibilidade de backup:** formato 2 inalterado; manifesto passa a declarar `db_schema_version: 3`; backups
  v1/v2 continuam aceitos. O ZIP **não** inclui cenários (Piso 2D) — documentado em `ARMAZENAMENTO.md`.
- **Recuperação:** cenários sobrevivem a reinício (verificado em novo processo e com reinício real do servidor).
- **Sem dados versionados:** nenhum `*.db`, backup ou diretório de dados no Git; o E2E usa diretórios temporários
  e uma microrrede fictícia de fixture (`tools/e2e/seed_piso2a.py`).

### 7. Interface

- **Barra superior:** marca · navegação agrupada [Centro de Operação · Simulação] | [Gestão da Microrrede] |
  [Resultados] · link "Alcance" (documentação) · **controle de identidade** (avatar com iniciais, nome, `ID xxxxxxxx ·
  inventário rev. N`, botão TROCAR MICRORREDE) · estado de salvamento do inventário. No Gestor o controle mostra
  "Nenhuma microrrede aberta" (tracejado, sem botão). A microrrede **não** é item do menu.
- **Centro de Operação (painel):** hero (nome, revisão do inventário, identidade, nº de cenários, natureza/modo/
  local); barra de cenário (seletor "Cenário selecionado", "＋ Novo", "Duplicar", "Nome e descrição"; estado vazio
  com "＋ NOVO CENÁRIO"); três cartões — *Cenário* (nome, descrição, versão, salvo/alterações não salvas, linhagem,
  ID), *Inventário de referência* (revisão, "Revisão atual"/"Equivalente ao atual"/"Inventário mudou" + lista, botão
  de atualização explícita), *Preparação do cenário* (Inicialização + três etapas "Não implementado"; selo "Não
  executável nesta versão"); *Etapas do experimento* (01 Inicialização com ABRIR INICIALIZAÇÃO; 02–04 sem
  controles); aviso de que o cenário ainda não é aplicado às rodadas; expansores "Instalação física (inventário
  salvo) e prontidão do console V1.6" e "Ferramentas V1.6 — bancadas individuais".
- **Inicialização:** "← Centro de Operação"; hero com versão e revisão de referência; aviso de deriva; legenda das três
  categorias; seções por tipo (Armazenamento, H₂/PEMFC, Térmica, Solar, Eólica) com um cartão por equipamento
  **habilitado** do inventário de referência (nome, tipo, tag, linha de referência física, controles, constatações
  logo abaixo); desabilitados listados sem controles; estados órfãos em expansor; contadores; SALVAR CENÁRIO
  (habilitado só com alterações) e DESCARTAR ALTERAÇÕES; em conflito, "Recarregar versão salva (descarta as
  alterações desta sessão)".
- **Comportamento entre telas:** a cópia de trabalho do cenário persiste na sessão ao navegar; trocar de cenário com
  alterações pendentes é recusado com mensagem; trocar de microrrede limpa todo o estado `op_*`; `?sc=` reabre o
  cenário na recarga apenas se ele pertencer à microrrede aberta.
- Comissionamento do Piso 1 **não** foi redesenhado.

### 8. Regras de inicialização

| Tipo | Campos | Erro de coerência (impede salvar) | Advertência (permitido) | Capacidade científica pendente |
|---|---|---|---|---|
| Bateria | disponibilidade, `soc0_pct` | SOC ∉ [0, 100] (limite físico; o widget também limita); tipo inválido | SOC fora da restrição operacional declarada ou do intervalo recomendado; SOC < 5 % ou > 95 % | SOC fora de [soc_min, soc_max]: o EMS V1.6 usa esses limites como restrição efetiva e o adaptador **exclui** o banco; bancos com SOC distintos não são agregáveis no V1.6 (pendência global); indisponibilidade não aplicada |
| PEMFC | disponibilidade, `state` (desligada/em partida/em operação), `units_on`, `power_kW` | indisponível e não desligada; desligada com P > 0 ou unidades > 0; unidades > instaladas; em partida/operação com 0 unidades; P > unidades × Pmáx por unidade; P < 0 | "em partida" (o SEEDS2 não modela a física de partida); em operação com P = 0; Pmáx por unidade desconhecida | **qualquer** estado declarado: o runtime fixa `n_ini = N_fc` e `P_prev = 0` (`ems_integration/fontes.py`, `despacho.py`) |
| Térmica | disponibilidade, `state`, `power_kW` | indisponível e não desligada; desligada com P > 0; P > Pmáx; **em operação** com P < Pmín técnica do inventário; P < 0 | "em partida" (sem tempos/física de partida) | **qualquer** estado declarado: o runtime deriva `n_ini = int(Pmin > 0)` e `P_prev = 0` |
| FV / eólica | disponibilidade | campo inexistente (p. ex. potência inicial) | — | indisponibilidade não aplicada pelo V1.6 |

"Não definido" (`incompleto`): SOC, estado ou potência (em operação) ausentes; equipamento habilitado sem estado.
Nenhuma restrição é passada ao otimizador: **o cenário não é aplicado a rodadas no Piso 2A** — a Simulação V1.6
continua usando a configuração salva e `run_conditions` (aviso explícito no Centro). Diferenças entre disponibilidade
(técnica) e estado (operativo) são campos distintos.

### 9. Pruebas

Ambiente: Linux, Python 3.13, `requirements.txt` (Streamlit 1.66.1), Chromium via Playwright pré-instalado.
Todas as execuções com `PYTHONDONTWRITEBYTECODE=1` (o `__pycache__/` versionado não foi alterado).

**Suíte automatizada**

| Momento | Comando | Resultado |
|---|---|---|
| Linha de base (`main` `50ef4d6`, antes de qualquer alteração) | `python -m pytest tests/ -q` | **237 passed** (108 s) |
| Após a primeira implementação | idem | 234 passed, **3 failed** — as 3 asserções `view == "inicio"` (navegação substituída por decisão da missão). Atualizadas para `"operacao"`; uma reforçada (verifica o Centro renderizado). Nenhuma asserção removida. |
| Versão final da rama | `python -m pytest tests/ -q` | **271 passed, 0 failed, 0 skipped** (136 s); 105 subtests |
| Repetição (determinismo) | `pytest tests/test_seeds2_piso2a.py tests/test_seeds2_piso2a_app.py tests/test_seeds2_concorrencia.py` ×8 consecutivas | **61 passed** em todas |

Novos testes (34):
- `tests/test_seeds2_piso2a.py` (23): criar/editar/duplicar/listar; cenário não altera a configuração física nem a
  especificação V1.6; versões imutáveis (UPDATE/DELETE recusados); **retomada em novo processo**; migração v2→v3
  com `.bak-v2` e dados intactos; backup continua compatível (manifesto v3; não transporta cenários); vínculo com a
  revisão, deriva (descrição ≠ deriva; retirado/alterado/incluído detectados) e `rebase` com órfãos e erro revelado
  (3 unidades > 2 instaladas); revisão-base inexistente/divergente recusada; microrrede não comissionada não cria
  cenário; **duas microrredes independentes** (`ScenarioNotFound`/`IdentityError`; nenhuma tabela de cenários em
  `registry.db`); **exclusão + reimportação do mesmo UID** (nova incarnação sem cenários; referência antiga →
  `MicrogridDeletedError` em leitura/escrita; documento antigo → `IdentityError`); **duas sessões** (conflito
  explícito, gravação vencedora preservada) e corrida com `Barrier` (exatamente um vencedor); regras de
  inicialização (SOC 0/5/10/95/100 % → aviso + pendente, sem erro, e salva; 120 %/−1 % → erro de limite físico;
  hierarquia recomendado × operacional; PEMFC/térmica coerentes e contraditórias; FV/eólica só disponibilidade;
  estruturas inválidas; SOC distintos → pendência global; prontidão nunca executável); contratos 2B/2C
  (`ForecastInput` válido, "medido" para sintético recusado, slot desconhecido recusado, `ems_strategy` recusado,
  `RunReference`); **EMS inalterado** (especificação e impressão digital idênticas antes/depois de criar cenários;
  `P_kW` e custo **exatamente** iguais aos da configuração padrão V1.6 numa rodada real).
- `tests/test_seeds2_piso2a_app.py` (11, AppTest): abertura pelo Gestor → Centro de Operação; microrrede não
  comissionada permanece no comissionamento mesmo pedindo `operacao`/`inicializacao`/`inicio`; `?view=inicio` →
  Centro; **ausência de controles fictícios** (nenhum botão EXECUTAR/RODAR/OTIMIZAR/PREVIS…/ESTRATÉGIA; etapas
  "Não implementado"); bancadas e Simulação V1.6 acessíveis (`orq_mg_applied` da microrrede); criar → editar
  (SOC 10 %: aviso sem bloqueio) → salvar → nova sessão retoma o cenário e os valores; `?sc=`; estado contraditório
  recusado sem gravar; duplicar/renomear; duas sessões (conflito exibido, edição da perdedora preservada,
  recarregar); troca de microrrede limpa `op_*` e cenário de A não aparece em B (nem via `?sc=`); exclusão +
  reimportação não traz cenários antigos.

**Navegador real (Chromium/Playwright)** — servidores Streamlit reais, diretórios de dados vazios, reinício real do
servidor entre fases:

| Roteiro | Fases | Verificações |
|---|---|---|
| `tools/e2e/e2e_piso2a_centro_operacao.js` (novo; dados de `tools/e2e/seed_piso2a.py`) | operar 40 · reinício 5 · tablet 5 | **50/50** (executado 2× — a 2ª após o último ajuste de interface) |
| `tools/e2e/e2e_gestor_microrredes.js` (`SEEDS2_DEV_MODE=1`) | multi 39 · reinício 6 · tablet 2 · legado 5 (banco anterior ao Gestor em esquema v2) | **52/52** |
| `tools/e2e/e2e_piso1_microrrede.js` | comissionar 41 · reabrir 21 (inclui rodada EMS real) · tablet 4 | **66/66** |

Sem erros de JavaScript; sem exceções Streamlit; `.trash`/`.staging`/`.quarantine` vazios ao final; na fase
`legado`, a cópia adotada recebeu `seeds2.db.bak-v2` antes de migrar para v3. Capturas revisadas: Centro (claro,
tablet retrato/paisagem, escuro), Inicialização com erro de coerência, conflito na segunda sessão, barra superior.

**Defeitos encontrados e corrigidos durante a missão**
1. Seletores do roteiro E2E com rótulo não exato (casavam o ícone de ajuda) → `exact: true` (roteiro, não app).
2. PEMFC/térmica declaradas **desligadas** não recebiam a pendência do EMS, embora o runtime V1.6 assuma unidades
   ligadas (`n_ini = N_fc`; `n_ini = int(Pmin>0)`) → pendência registrada para qualquer estado declarado.
3. Cartões da Inicialização na ordem dos ids (o JSON canônico ordena as chaves) → `position` no instantâneo e
   ordenação pela ordem do inventário.
4. Falha intermitente (1 em 5 repetições) em `test_duas_sessoes_sem_sobrescrita_silenciosa`, introduzida pelo item 3:
   o teste escolhia "o primeiro banco" pela ordem do dicionário, e a interface pela ordem do inventário → o teste
   passou a usar a mesma ordem (`_batteries`); 8/8 repetições limpas depois. A aplicação estava correta.

**Limitações da verificação:** AppTest não executa o JavaScript dos componentes (barra superior verificada no E2E);
as capturas `fullPage` registram só a área visível (Streamlit rola num contêiner interno); sem CI no repositório.

### 10. Compatibilidade

- **Piso 1 / comissionamento:** inalterado (fluxo, etapas e validações). Única mudança: ao ativar, a microrrede abre
  no Centro de Operação (antes: Início).
- **Gestor de microrredes:** inalterado (criar, abrir, ZIP, PDF, importar, excluir, adoção do legado, proteção da
  exclusão). Bancos v2 existentes migram para v3 ao serem abertos (cópia `.bak-v2`); adoção do `seeds2.db`
  anterior ao Gestor continua funcionando (E2E `legado` com banco v2).
- **Console V1.6 e EMS:** nenhum arquivo em `models/`, `h2_pemfc/`, `simulation/`, `config/`, `ems_integration/`,
  `reference_models/` alterado (`git diff origin/main --stat` vazio nesses diretórios). Especificação transferida ao
  V1.6 idêntica com e sem cenários; despacho (`P_kW`) e custo idênticos ao da configuração padrão V1.6
  (`EMSInalteradoTest`, igualdade exata). Simulação/Resultados e bancadas acessíveis.

### 11. Alterações introduzidas

| Arquivo | Propósito |
|---|---|
| `seeds2/operation/__init__.py`, `scenarios.py`, `initialization.py`, `contracts.py`, `service.py` | Domínio do Piso 2A (novo) |
| `seeds2/microgrid/store.py` | Esquema v3 e API de cenários no `MicrogridStore` |
| `seeds2/ui/operation_center.py` | Centro de Operação + Inicialização (novo) |
| `seeds2/ui/main.py`, `shell.py` | Rota `operacao`, alias `inicio`, navegação agrupada, identidade, `?sc=` |
| `seeds2/ui/static/topbar.js`, `topbar.css` | Controle de identidade, grupos, link de documentação |
| `seeds2/ui/home.py` | Antigo Início refatorado em seções reutilizáveis |
| `seeds2/ui/commissioning.py`, `gestor.py` | Redirecionamento para `operacao` |
| `seeds2/ui/static/areas.js`, `areas.css` | Removidos (sem uso) |
| `seeds2/__init__.py` | `APP_VERSION = "2.0.0-piso2a"` |
| `tests/test_seeds2_piso2a.py`, `tests/test_seeds2_piso2a_app.py` | Testes novos (23 + 11) |
| `tests/test_seeds2_app.py`, `tests/test_seeds2_gestor_app.py` | 3 asserções de rota `inicio` → `operacao` (navegação real nova; uma asserção reforçada) |
| `tests/apptest_utils.py` | `continuar()` transporta o estado de aplicação `op_*` |
| `tools/e2e/e2e_piso2a_centro_operacao.js`, `tools/e2e/seed_piso2a.py` | E2E do Piso 2A (novo) |
| `tools/e2e/e2e_piso1_microrrede.js`, `e2e_gestor_microrredes.js` | Texto esperado da tela inicial da microrrede |
| `PARAMIJEFE.md`, `CLAUDE.md`, `docs/ai/HANDOFF.md`, `docs/seeds2/ARMAZENAMENTO.md`, `docs/seeds2/ARQUITETURA_PISO1.md` | Documentação |

### 12. Riscos e dívidas técnicas

1. **Cenário ainda não alimenta rodadas.** Até o Piso 2C, SOC inicial da rodada V1.6 continua em
   `run_conditions` da configuração física (Piso 1) — há, portanto, dois lugares com "SOC inicial" (o do cenário,
   experimental, e o da rodada V1.6). A interface explica isso; a unificação é decisão do Piso 2C.
2. **Incompatibilidades do EMS V1.6 registradas, não corrigidas:** limites de SOC como restrição efetiva; um SOC
   por grupo agregado; `n_ini`/`P_prev` fixos; indisponibilidade não aplicável por cenário.
3. **Sem exclusão/arquivamento de cenários** (não solicitado). A lista cresce; ordenação por criação.
4. **Backup ZIP não transporta cenários**: exportar/importar uma microrrede perde seus cenários (comportamento
   documentado; portabilidade = Piso 2D).
5. **Migração v3 obrigatória**: ao abrir com este software, bancos v2 passam a v3; uma versão anterior do SEEDS2
   recusará o banco migrado ("mais novo que este software") — mitigado pela cópia `.bak-v2`.
6. **Concorrência**: conflitos são detectados, não mesclados; o perdedor reaplica manualmente (valores ficam
   visíveis na sessão dele até recarregar).
7. Edição de nome/descrição exige que não haja alterações pendentes da Inicialização (recusa explícita).
8. Herdadas: `__pycache__/` versionado (testes rodados com `PYTHONDONTWRITEBYTECODE=1`), sem CI, sem autenticação.

### 13. Instruções para o auditor

Prioridade de revisão:
1. `seeds2/microgrid/store.py` — migração v3 e `create_scenario`/`save_scenario`/`_check_scenario_base`: tudo
   dentro de `_tx()`; FK para `revisions`; triggers; conflito por versão.
2. `seeds2/operation/initialization.py` — regras da seção 8 (especialmente: SOC fora do recomendado nunca é erro;
   estados contraditórios são erros; pendências nunca viram restrição).
3. `seeds2/operation/scenarios.py` — `drift`/`rebase` (órfãos preservados), `structural_errors`, `readiness`
   (`executable` sempre falso).
4. `seeds2/ui/operation_center.py` — `sync()` (nenhuma edição pendente substituída em silêncio), `_save_bar`,
   ausência de controles das etapas 02–04.
5. `tests/test_seeds2_piso2a.py` (`CenarioIsolamentoTest`, `CenarioConcorrenciaTest`, `InicializacaoRegrasTest`,
   `EMSInalteradoTest`) e `tests/test_seeds2_piso2a_app.py`.
Comportamentos a reproduzir manualmente: criar cenário → Inicialização → SOC 10 % (aviso, salva) → PEMFC
desligada com 25 kW (erro, "Nada foi gravado"); duas abas no mesmo cenário (conflito); alterar o inventário na
Gestão e ver "Inventário mudou" → atualizar referência; TROCAR MICRORREDE.

### 14. Próximo passo (preparado, não implementado)

- **Piso 2B — Previsões:** preencher `doc["forecasts"][slot]` com `contracts.ForecastInput` (manual/CSV/sintético/
  referência; procedência; base temporal; CSV pelo `blobs` da microrrede via `MicrogridStore.put_blob`). A validação
  estrutural já recusa slots/tipos desconhecidos e "medido" para sintético/referência. Falta: editores, gráficos,
  validação temporal e inclusão dos blobs de cenário em `_referenced_blobs`/backup.
- **Piso 2C — Execução:** nova tabela `scenario_runs` (migração v4) referenciando `contracts.RunReference`
  `(scenario_uid, scenario_version)` imutável + séries completas; runner que traduza o cenário para o contrato V1.6
  sem alterar o otimizador; `ems_strategy` deixa de ser recusado. Decidir o destino de `run_conditions` do Piso 1.
- **Piso 2D — Arquivo:** o documento do cenário já é JSON autossuficiente (esquema + versão + instantâneo físico +
  dados por SHA-256); falta o empacotamento (ZIP/PDF/Excel) com as execuções.
- **Piso do otimizador:** tratar as pendências da seção 8 (SOC como restrição, `n_ini`, `P_prev`, SOC por banco).

---

## Histórico de entregas

| Entrega | Data | Missão | Rama / PR | Estado |
|---|---|---|---|---|
| 1 | 2026-11-06 | Piso 2A — Centro de Operação (fundação operacional) | `claude/seeds2-piso2a-centro-operacao` / [#6](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/6) | Aguardando auditoria |
