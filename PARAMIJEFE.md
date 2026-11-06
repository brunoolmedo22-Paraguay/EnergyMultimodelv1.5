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
| Estado | Implementado e verificado na rama; auditoria independente favorável com **uma correção solicitada (C-01, seção 15), implementada**; **não integrado** em `main` |
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
| `seeds2/ui/shell.py` (`BACKUP_SCOPE`, `RESTORE_SCOPE`), `gestor.py`, `management.py`, `exports.py` | **C-01**: avisos de alcance do backup e consentimento específico na exclusão (seção 15) |

### 12. Riscos e dívidas técnicas

1. **Cenário ainda não alimenta rodadas.** Até o Piso 2C, SOC inicial da rodada V1.6 continua em
   `run_conditions` da configuração física (Piso 1) — há, portanto, dois lugares com "SOC inicial" (o do cenário,
   experimental, e o da rodada V1.6). A interface explica isso; a unificação é decisão do Piso 2C.
2. **Incompatibilidades do EMS V1.6 registradas, não corrigidas:** limites de SOC como restrição efetiva; um SOC
   por grupo agregado; `n_ini`/`P_prev` fixos; indisponibilidade não aplicável por cenário.
3. **Sem exclusão/arquivamento de cenários** (não solicitado). A lista cresce; ordenação por criação.
4. **Backup ZIP não transporta cenários**: exportar/importar uma microrrede perde seus cenários (portabilidade =
   Piso 2D). **Mitigado pela correção C-01** (seção 15): toda exportação/restauração/exclusão o declara e a exclusão
   de uma microrrede com cenários exige consentimento específico.
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

### 15. Correção de auditoria C-01 — cenários e backup incompleto

**Achado da auditoria independente (único, bloqueante para o merge):** o backup ZIP (formato 2) não inclui as tabelas
`scenarios`/`scenario_versions`, mas o Gestor oferecia "Preparar ZIP antes de excluir" sem advertir que os cenários
não seriam recuperáveis a partir desse arquivo → risco de perda de cenários por backup incompleto.

**Correção (somente interface; formato de backup, contratos de cenário, migrações SQLite, EMS e modelos intactos):**
1. Texto único de alcance em `seeds2/ui/shell.py`: `BACKUP_SCOPE` ("contém a configuração e os dados compatíveis do
   Piso 1 … **não inclui os cenários operativos do Piso 2A** … não podem ser recuperados a partir deste arquivo …
   Piso 2D") e `RESTORE_SCOPE` ("nenhum cenário operativo é restaurado; os existentes são mantidos e passam a indicar
   que o inventário mudou").
2. Exibido em **todas** as exportações e restaurações: componente comum `exports.export_actions` (etapa 05 do
   comissionamento e Gestão → Relatório), Gestão → Exportar backup (aviso) e Restaurar backup, botão ZIP do cartão
   do Gestor (ajuda + legenda "não inclui cenários operativos" do arquivo preparado), diálogo IMPORTAR MICRORREDE
   (ZIP) e diálogo de exclusão (sob "Preparar ZIP antes de excluir").
3. Diálogo de exclusão: linha **"Cenários operativos (Piso 2A)"** com a contagem no resumo; os cenários entram na lista
   do que será excluído.
4. Com ≥ 1 cenário: aviso específico e **checkbox obrigatório adicional** ("Entendo que os N cenário(s) operativo(s)
   desta microrrede serão excluídos e que o ZIP atual não permite recuperá-los"); EXCLUIR DEFINITIVAMENTE só habilita
   com nome exato **e** esse consentimento (e credencial, quando exigida). A chave do checkbox inclui N: se outra sessão
   criar cenários, o consentimento é renovado; no clique o número é **recontado** e, se aumentou, nada é excluído.
5. A exclusão definitiva continua possível para quem confirma conscientemente; sem cenários, o fluxo é o anterior.

**Evidência**
- Novos testes `tests/test_seeds2_piso2a_app.py::BackupEscopoTest` (5, AppTest): consentimento específico exigido e
  suficiente (nome exato sozinho não habilita; com o checkbox exclui de fato — diretório removido); sem cenários não
  há checkbox e a exclusão segue como antes; cenário criado por outra sessão com o diálogo aberto → nada excluído,
  consentimento renovado; exclusão desativada continua mostrando a contagem; avisos presentes em Gestão (exportar e
  restaurar), no botão/legenda ZIP do Gestor e no diálogo de importação.
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ -q` → **276 passed, 0 failed** (271 + 5).
- E2E Chromium do Gestor repetido do zero (servidor real, reinício entre fases, `SEEDS2_DEV_MODE=1`):
  `e2e_gestor_microrredes.js` **52/52** (multi 39 — inclui exclusão definitiva de B, sem cenários; reinício 6;
  tablet 2; legado 5).
- `git diff` da correção restrito a `seeds2/ui/{shell,gestor,management,exports}.py`, ao teste e à documentação.

**Limite residual:** entre a recontagem e a remoção física existe uma janela mínima em que outra sessão poderia criar
um cenário; eliminá-la exigiria alterar o protocolo de exclusão do catálogo (H-01/H-02), fora do escopo desta
correção. A exportação real dos cenários permanece no Piso 2D.

---

## Entrega 2 — SEEDS2 Piso 2B · Centro de Operação · Previsões e Dados

### 1. Identificação

| Campo | Valor |
|---|---|
| Piso / missão | **Piso 2B** — Previsões e Dados (etapa 02 do Centro de Operação) |
| Data | 2026-11-06 |
| Base | `main` em `4709f0c` (merge do PR #6 — Piso 2A + C-01), verificado com `git fetch` (o `origin/main` local do contêiner estava desatualizado em `761f032`; corrigido antes da linha de base) |
| Rama | `ccr-68eaae98-0rs4e4` — rama de desenvolvimento designada pelo ambiente desta sessão (a missão propunha `claude/seeds2-piso2b-previsoes`; a regra do ambiente proíbe publicar em outra rama sem autorização explícita) |
| PR | [#7](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/7) (sem merge; aguarda auditoria) |
| Commits | `04ee15b` (código, testes e E2E), `4ab54a0` (documentação + ajuste de aviso em teste). O commit seguinte só preenche PR/commits neste relatório; o SHA final da rama é informado na resposta da entrega. |
| Estado | Implementado e verificado na rama; **não integrado** em `main` |

### 2. Resumo executivo

**Solicitado:** módulo Previsões e Dados — demanda elétrica e variáveis meteorológicas por perfil manual, CSV,
sintético ou referência da V1.6; visualização gráfica interativa antes de aceitar; validação de datas, unidades,
resolução e qualidade; gravação no cenário com versões, conflitos, isolamento e integridade; reabertura idêntica
após reinício — sem executar o cenário (Piso 2C) e sem tocar no EMS.

**Entregue:**
- Etapa **02 Previsões** ativa no Centro de Operação (botão ABRIR PREVISÕES; estado na prontidão do cenário);
  Estratégia EMS e Execução continuam "Não implementado", sem controles.
- Página **Previsões e Dados** com abas *Demanda elétrica (kW)* e *Clima — variáveis meteorológicas*; em cada aba,
  dois cartões separados: **Perfil do cenário** (salvo em vN ou incorporado e não salvo) e **Nova entrada —
  pré-visualização pendente** (fonte manual / CSV / sintético / referência).
- Gráficos **Plotly** (data e hora × grandeza com unidade; hover, zoom, restauração; lacunas sombreadas e linha
  interrompida; ausentes marcados; série transformada de 1 min opcional e tracejada; clima em painéis por
  grandeza, nunca dois eixos Y).
- Resumo temporal (período, cobertura, resolução original e regularidade, observações, fuso), estatísticas
  (mín./máx. com instante, média, ausentes, maior variação entre amostras) e energia estimada (kWh) separada da
  potência (kW).
- Validações temporais e físicas em **erro / aviso / pendente / não definido**; nada é preenchido com zero, nenhuma
  extrapolação, toda transformação registrada.
- Persistência: entradas `ForecastInput` em `doc["forecasts"]` + séries no `blobs` da microrrede, **gravadas na
  mesma transação** da nova versão do cenário; reprodutibilidade verificável (SHA-256 + reconstrução da origem).
- Testes: 32 novos (24 de domínio/persistência + 8 de interface) e E2E Chromium do Piso 2B (58 verificações),
  com repetição dos E2E do Piso 1, Gestor e Piso 2A (seção 10).

### 3. Arquitetura encontrada em `main` (`4709f0c`)

- Contrato preliminar `contracts.ForecastInput` (9 campos), `FORECAST_SLOTS` (`demand`, `climate`, `resources`) e
  `forecast_errors` (estrutural); bloco `forecasts: {}` em todo cenário; prontidão com "Previsões — Não
  implementado".
- Demanda/clima já existiam **no inventário** (Piso 1: `config.demand`/`config.climate`, CSV como blob) e alimentam a
  rodada V1.6 via `adapter.build_load`/`build_climate_raw`. Funções reaproveitáveis encontradas:
  `ponte.carga_walkforward`, `ponte.carga_copel`, `ponte.PerfilCarga`, `orchestrator_runtime.synthetic_climate`,
  `mix_engine.detect_climate_columns`/`OPERATION_ALIASES`/`_numeric`/`_decode_bytes`/`align_climate_to_operation`
  (interpolação angular por `unwrap`), `wind_model.prepare_wind_profile` (variáveis opcionais do vento).
- `MicrogridStore`: tabela `blobs` (SHA-256 verificado na leitura), `_tx`/`_read` com lápide/incarnação (H-01/H-02/
  H-03), cenários v3 com concorrência otimista. Linha de base: **276 passed** (`python -m pytest tests/ -q`, 137 s).

### 4. Decisões técnicas

| # | Tema | Alternativas | Escolha e justificativa |
|---|---|---|---|
| B1 | Onde guardar as séries | (a) dentro do JSON do cenário; (b) tabela nova (`scenario_series`, migração v4); (c) tabela `blobs` existente por SHA-256 | **(c)**. Sem migração de banco; deduplicação por conteúdo; integridade verificada na leitura; segue H-01/H-03 sem código novo; versões antigas referenciam blobs imutáveis. (a) incharia cada versão (cópia integral a cada edição); (b) duplicaria o mecanismo de blobs. |
| B2 | Atomicidade blobs × versão | (a) `put_blob` antes e salvar depois; (b) blobs e versão na mesma transação | **(b)** `save_scenario(..., new_blobs)`: insere, confere hashes e exige TODOS os blobs referenciados dentro do mesmo `BEGIN IMMEDIATE`. Nenhum documento com blob inexistente; conflito/erro não deixa blob órfão. |
| B3 | Representação normalizada | (a) só reaplicar arquivo + mapeamento; (b) guardar também a série normalizada | **(b)** CSV canônico determinístico (instantes ISO sem fuso + `repr(float)`, vazio = ausente) → SHA-256 estável; leitura uniforme para o Piso 2C. A reprodutibilidade a partir da origem é verificável (`rederive`) e testada para as 4 fontes. |
| B4 | Base temporal | recortar/reamostrar para a grade do EMS ao importar × preservar | **Preservar** instantes e resolução originais (nenhum limite de 2 h). Grade de 1 min só como visualização opcional; resolução ≠ 1 min gera **pendente** (método de conversão = Piso 2C). |
| B5 | Fuso | presumir o da instalação × explícito | Deslocamento no arquivo → fuso do arquivo (uniforme: relógio de parede + `UTC±hh:mm`; vários offsets → convertido para UTC, registrado). Sem deslocamento → escolha do usuário; **não declarado** permitido com aviso e rótulo explícito. O fuso da instalação aparece como opção, nunca pré-selecionado. |
| B6 | Unidades | presumir pela convenção × confirmar | Detectada só por sufixo inequívoco do cabeçalho (`_kW`, `_W_m2`, `_hPa`…); caso contrário o usuário **confirma** (sem confirmação = erro). Conversões explícitas (W/MW→kW, kW/m²→W/m², K/°F→°C, km/h/kn→m/s, Pa/kPa/mbar→hPa, fração→%) registradas em `transforms`. |
| B7 | Duplicatas | descartar silenciosamente (como `mix_engine.prepare_climate`) × política explícita | Padrão **recusar** (erro com exemplos); políticas primeira / última / média (direção: média circular), registradas. Por isso `prepare_climate` não foi reutilizado para normalizar. |
| B8 | Clima obrigatório | sempre as 6 variáveis × pelo inventário | Pelo inventário de referência **habilitado**: FV → GHI + temperatura (modelo NOCT); eólica → velocidade (obrigatória) + direção/temperatura/pressão/umidade (opcionais, densidade do ar com retorno à referência). Conjunto único e compartilhado; variável ausente = "não definido" (não erro); variável sem tecnologia = aviso. |
| B9 | Leitura de CSV | `mix_engine.read_csv_auto` × leitor próprio | `read_csv_auto` (V1.6, protegido) adota uma LETRA como separador em arquivos de uma coluna ("apenas" → colunas `pen`, `s`). `read_table` reutiliza a decodificação da V1.6 e escolhe o separador explicitamente entre `; , \t \|`, lendo tudo como texto. A V1.6 não foi alterada. |
| B10 | Fluxo de gravação | botão por previsão que salva × incorporar + SALVAR CENÁRIO | **Incorporar** (cópia de trabalho) + barra única **SALVAR CENÁRIO** (mesma da Inicialização): demanda e clima podem entrar numa só versão; conflito e descarte com o mesmo comportamento do Piso 2A. |
| B11 | Abas | `st.tabs` sem estado × com `key` | `st.tabs(key="opw_fc_tab", on_change="rerun")` e renderização só da aba aberta: sem estado, a aba ativa voltava para "Demanda" a cada reexecução (detectado no E2E). |
| B12 | Contrato | substituir × estender `ForecastInput` | **Estender**: os 9 campos do Piso 2A ficam inalterados; campos novos opcionais na validação estrutural; completude exigida para gravar em `forecasts.entry_errors` (via `check_for_save`). `schema_version` do cenário continua 1 (o bloco era vazio por contrato). |
| B13 | Slot `resources` | entrada operativa de H₂/combustível × reservado | **Reservado** e não editável (`entry_errors` recusa): nenhum contrato científico o consome ainda. |
| B14 | `APP_VERSION` | — | `2.0.0-piso2b`. |

### 5. Contrato de perfis e séries temporais

`doc["forecasts"][slot]` (slot ∈ `demand`, `climate`) — `contracts.ForecastInput`, `format_version` 1:

```
{slot, format_version: 1, source_type: manual|csv|sintetico|referencia, provenance, label,
 variables: [chaves canônicas],            # ordem canônica forecasts.VARIABLES
 t0, t_end,                                # ISO 8601 SEM fuso = relógio de parede do fuso declarado
 step_s (mediana), horizon_s, n_points, regular,
 timezone: IANA | "UTC" | "UTC±hh:mm" | null (= NÃO DECLARADO),
 timezone_source: arquivo | arquivo_utc | usuario | nao_declarado,
 data: sha256 da série normalizada,  blob: sha256 do CSV original | null,
 params: {CSV: filename,size,sha256,rows,columns | manual: construction |
          sintético: generator, generator_version, seed, params | referência: dataset, params, file, file_sha256},
 mapping: {CSV: time_mode, time_column, date_order, relative_unit, t0, timezone, duplicates,
           columns: {var: {column, unit}}} | null,
 transforms: [...], quality: {erro, aviso, pendente, incompleto, items: [...]}, stats: {var: {...}},
 notes, created_at}
```

| Variável canônica | Unidade | Uso pelos modelos existentes |
|---|---|---|
| `demand_kW` | kW (potência instantânea) | demanda |
| `ghi_W_m2` | W/m² | FV (obrigatória) |
| `temperature_C` | °C | FV (obrigatória); eólica (opcional) |
| `wind_speed_m_s` | m/s | eólica (obrigatória) |
| `wind_direction_deg` | graus | eólica (opcional; angular) |
| `pressure_hPa` | hPa | eólica (opcional) |
| `humidity_pct` | % | eólica (opcional) |

Série normalizada (blob `data`): `timestamp,<variáveis>` UTF-8, instantes `AAAA-MM-DDTHH:MM:SS[.ffffff]`,
valores `repr(float)` (ida e volta exata), célula vazia = ausente, sem índice; `forecasts.to_csv_bytes` /
`from_csv_bytes`; carregamento verificado por `forecasts.load` (hash, cabeçalho, variáveis, contagem).

### 6. Tabelas, blobs e regras de persistência

- **Sem migração:** banco da microrrede continua v3. Séries em `blobs` (ver `docs/seeds2/ARMAZENAMENTO.md`,
  "Previsões dos cenários"). Toda incorporação/modificação/remoção grava **nova versão** em `scenario_versions`
  (append-only; versões antigas recuperam SUAS curvas — testado).
- **Atomicidade:** `MicrogridStore._store_scenario_blobs` dentro de `_tx` (create e save): insere `new_blobs`
  (hash conferido) → exige todos os blobs referenciados → grava a versão; qualquer exceção desfaz tudo.
  `service.save` envia só blobs referenciados pelo documento. Pendentes ficam apenas na sessão (`op_blobs`).
- **Órfãos:** não produzidos pelo fluxo; **sem limpeza destrutiva** (blobs podem ser referenciados por versões
  históricas e revisões do inventário). Saem só com a exclusão da microrrede.
- **Conflito:** `ScenarioConflictError` → nada gravado (nem blobs); a cópia de trabalho e `op_blobs` da sessão
  perdedora permanecem; "Recarregar versão salva" descarta conscientemente.
- **Isolamento:** blobs por banco de microrrede; documento copiado para outra microrrede é recusado.
- **Backup ZIP:** inalterado (sem cenários/previsões); `BACKUP_SCOPE` agora cita "nem as previsões associadas a
  eles (Piso 2B)"; avisos e consentimento da C-01 preservados.

### 7. Interface e sistema de pré-visualização

- **Centro de Operação:** cartão 02 Previsões com estado (Incompletas / Definidas / Com erros) e ABRIR PREVISÕES;
  "Preparação do cenário" inclui o estado das previsões; o aviso de que o cenário não é aplicado às rodadas agora
  cita explicitamente demanda e clima.
- **Previsões e Dados:** hero (versão, revisão do inventário, renováveis habilitadas, estado), legenda das
  categorias, abas Demanda / Clima (tabela de requisitos por tecnologia, com os nomes dos equipamentos), cartões
  *Perfil do cenário* e *Nova entrada*, constatações do conjunto (demanda × clima: fusos, período comum), aviso de
  não execução e barra SALVAR / DESCARTAR.
- **Editores:** *Manual* — gerar tabela regular (início, passo, pontos) + colar uma coluna de valores (vírgula
  decimal) + `st.data_editor` dinâmico; *CSV* — upload, estrutura detectada (dados originais), mapeamento (modo de
  tempo, coluna, ordem da data ou unidade relativa + t0 obrigatório, fuso, duplicatas, coluna e unidade por
  variável com a origem da unidade: "detectada no cabeçalho" / "confirmada pelo usuário" / "não indicada"),
  procedência; *Sintético* — 4 geradores com ruído opcional e semente; *Referência* — walk-forward, COPEL B1 (data
  escolhida explicitamente), exemplos `Dados_exemplo/`, clima sintético V1.6, eólico sintético do Ceará.
- **Pré-visualização:** recalculada a cada interação a partir do editor; com erros não há curva (nunca a anterior);
  o botão INCORPORAR/SUBSTITUIR fica desabilitado com o motivo. O título do gráfico distingue "perfil do cenário" ×
  "PRÉ-VISUALIZAÇÃO (pendente)".
- **Integridade:** botão VERIFICAR INTEGRIDADE E REPRODUTIBILIDADE (relê pelo SHA-256 e reconstrói da origem);
  blob ausente/corrompido → mensagem, sem exceção, nada alterado.

### 8. Validações científicas implementadas

| Categoria | Regra |
|---|---|
| Erro | instante inválido/ambíguo (dia×mês), fusos misturados, fuso desconhecido, tempo relativo sem t0, < 2 observações, duplicatas sem política, coluna inexistente/repetida, unidade não confirmada, valor infinito, ausente em variável obrigatória (demanda; GHI/temperatura com FV; vento com eólica), demanda < 0, GHI < 0, vento < 0, direção ∉ [0, 360], umidade ∉ [0, 100], pressão ≤ 0, temperatura < −273,15 °C |
| Aviso | fuso não declarado, linhas reordenadas, duplicatas tratadas, intervalos ausentes (> 1,5 × passo típico; nada preenchido), resolução irregular, ausente em variável opcional, variável sem tecnologia habilitada, GHI > 1361 W/m², vento > 60 m/s, pressão ∉ [500, 1100] hPa, temperatura ∉ [−60, 60] °C (unidade suspeita), fusos distintos ou sem período comum entre demanda e clima |
| Pendente | resolução ≠ 1 min (conversão para a grade do EMS = Piso 2C) |
| Não definido | demanda ausente; clima ausente com FV/eólica; variável obrigatória ausente no clima |

Sem limites arbitrários novos: erros só para o fisicamente impossível; plausibilidade = aviso. O sistema de SOC do
Piso 2A não foi tocado. Energia (kWh) = trapézio da potência nos instantes reais, sem integrar lacunas.

### 9. Pruebas e resultados exatos

Ambiente: Linux, Python 3.13.18, Streamlit 1.66.1, Plotly 6.3.0, pandas 2.2.3; `PYTHONDONTWRITEBYTECODE=1`.

| Momento | Comando | Resultado |
|---|---|---|
| Linha de base (`main` `4709f0c`, worktree limpo) | `python -m pytest tests/ -q` | **276 passed** (137 s) |
| Durante a implementação | `pytest tests/test_seeds2_piso2a.py` | 1 falha esperada: `test_prontidao_nunca_declara_execucao` afirmava "Previsões — Não implementado"; atualizada para o estado real (`("warn", "Incompletas", "falta: demanda, clima")`), mantendo Estratégia/Execução "Não implementado" |
| Versão final da rama | `python -m pytest tests/ -q` | **308 passed, 0 failed, 0 skipped** (162 s; 105 subtests; 7 avisos, os mesmos da linha de base) — 276 anteriores + 32 novos; testes 2A + 2B repetidos 5× consecutivas: 71 passed em todas |

Ajustes em testes existentes (navegação real nova; nenhuma asserção enfraquecida): `test_seeds2_piso2a.py` (acima);
`test_seeds2_piso2a_app.py` — `FAKE` deixa de proibir "PREVIS" (a etapa existe; "GERAR PREVIS" continua proibido) e
a contagem "Não implementado" passa de ≥3 para ≥2 com a nova asserção de que ABRIR PREVISÕES existe;
`apptest_utils.py` — `continuar()` transporta `op_blobs`, `op_fcs_*`, `opw_fc_src_*` e `opw_fc_tab`.

Novos testes — mapa dos 22 requisitos:

| # | Requisito | Teste |
|---|---|---|
| 1 | manual de demanda | `PerfilManualTest` (2); `PrevisoesFluxoTest.test_demanda_manual_colada_preview_salvar_e_reabrir` |
| 2 | CSV de demanda | `ImportacaoCSVTest.test_csv_de_demanda_com_fuso_virgula_decimal_e_original_preservado` |
| 3 | sintético determinista | `SinteticoTest` |
| 4 | referências reutilizadas | `ReferenciaTest` (valores idênticos a `ponte`/`synthetic_climate`; todos os conjuntos reproduzíveis) |
| 5 | meteorologia | `test_variaveis_meteorologicas_e_conjunto_compartilhado`; `test_csv_climatico_mapeamento_unidade_e_procedencia` |
| 6 | detecção/mapeamento | `test_deteccao_e_mapeamento_de_colunas` |
| 7 | unidades | `test_unidades_convertidas_e_registradas` |
| 8 | ausentes e duplicados | `ValidacaoTemporalTest` (duplicatas, ordem, lacunas, irregular, fusos, datas ambíguas, ausentes) |
| 9 | CSV malformado | `test_csv_malformados_nao_derrubam_a_interface`; `test_csv_malformado_recusado_sem_excecao` |
| 10 | fisicamente inválido | `ValidacaoFisicaTest` |
| 11 | pré-visualização correta | `PreVisualizacaoTest` (dados dos traços, lacunas, eixos, ausentes, grade sem extrapolação, ângulo) + especificações Plotly no AppTest |
| 12–13 | persistência, reinício | `test_gravar_reabrir_e_prontidao`; `test_recuperacao_apos_reinicio_em_novo_processo` (subprocesso) |
| 14–15 | duplicação; versões imutáveis | `test_duplicacao_e_versoes_historicas_imutaveis`; `test_sintetico_e_referencia_pendente_nunca_mostrado_como_atual` |
| 16 | conflito | `test_conflito_entre_sessoes_preserva_pendente_e_nao_grava_blobs`; `PrevisoesConcorrenciaTest` |
| 17 | isolamento | `test_isolamento_entre_microrredes`; `test_troca_de_microrrede_limpa_o_estado_e_isola_dados` |
| 18 | blobs inexistentes/corrompidos | `test_blobs_inexistentes_corrompidos_e_atomicidade`; `test_blob_corrompido_e_inicializacao_sem_regressao` |
| 19 | originais preservados | CSV original byte a byte (domínio e interface); `rederive` |
| 20 | Inicialização | `test_inicializacao_inalterada_com_previsoes`; `test_blob_corrompido_e_inicializacao_sem_regressao`; suíte do 2A |
| 21 | Gestor | suíte do Gestor + E2E Gestor (seção 10); `test_backup_zip_continua_sem_cenarios_nem_previsoes` |
| 22 | EMS inalterado | `test_ems_e_configuracao_fisica_inalterados` (configuração, especificação, descritores, `P_kW` e custo idênticos) + `EMSInalteradoTest` do 2A |

### 10. E2E e evidência visual

Chromium real (Playwright), servidores Streamlit reais, diretórios vazios, **reinício real do servidor entre fases**:

| Roteiro | Fases | Resultado |
|---|---|---|
| `tools/e2e/e2e_piso2b_previsoes.js` (novo; dados `tools/e2e/seed_piso2b.py`: microrrede fictícia FV + eólica e CSVs sintéticos) | operar 43 · reinício 8 · tablet 7 | **58/58** |
| `tools/e2e/e2e_piso2a_centro_operacao.js` | operar · reinício · tablet | **51/51** (operar 41 — +1 verificação de ABRIR PREVISÕES; reinício 5; tablet 5) |
| `tools/e2e/e2e_gestor_microrredes.js` (`SEEDS2_DEV_MODE=1`; `legado` com banco v2 anterior ao Gestor) | multi · reinício · tablet · legado | **52/52** (multi 39; reinício 6; tablet 2; legado 5 — banco v2 adotado e migrado) |
| `tools/e2e/e2e_piso1_microrrede.js` (inclui rodada EMS real) | comissionar · reabrir · tablet | **66/66** (comissionar 41; reabrir 21 com rodada EMS real; tablet 4) |

Todos executados desde diretórios vazios, depois da implementação final; ao final, o catálogo do Gestor tinha
exatamente 2 microrredes e `.trash`/`.staging` vazios; sem exceções Streamlit nem erros de JavaScript.
Ajuste no roteiro do Piso 2A (navegação real nova, não enfraquecimento): a verificação "nenhum botão fictício"
deixou de proibir "PREVIS" (ABRIR PREVISÕES agora existe e é verificado); EXECUTAR/RODAR/OTIMIZAR/GERAR PREVIS/
ESTRAT continuam proibidos. Na primeira repetição, essa asserção obsoleta falhou exatamente por isso.

Verificado no navegador (2B): curva pendente = valores do CSV (vírgula decimal, fuso −03:00); eixo único em kW;
hover com valor e unidade; zoom por arraste e restauração por duplo clique; CSV malformado sem curva e sem
exceção; clima com 4 painéis (W/m², °C, m/s, °), sem eixo sobreposto; direção 350°→5° interpolada pelo menor arco;
salvar v2; nova fonte sintética mostra a NOVA curva pendente enquanto o perfil salvo continua o do CSV;
reprodutibilidade por SHA-256; Inicialização intacta; após reinício, demanda (121 valores) e GHI recuperadas
exatamente; tablet retrato/paisagem sem rolagem horizontal; tema escuro. Sem erros de JavaScript.
Capturas revisadas: pré-visualização com hover, clima com grade transformada, pendente × atual, tablet, escuro.
Defeitos visuais corrigidos na revisão: legenda sobreposta ao título do 1º painel (movida para a base);
"60 s" → "1 min"; datas do eixo no formato dd/mm/aaaa; "None" na tabela de estatísticas.

### 11. Compatibilidade

- **Piso 1 / Gestor:** sem mudança de fluxo; banco v3 inalterado (sem migração); backup ZIP formato 2 inalterado.
- **Piso 2A:** Inicialização idêntica; mesmo salvar/descartar/conflito; `check_for_save` só acrescenta a
  completude das previsões; cenários antigos (`forecasts: {}`) continuam válidos.
- **EMS / modelos:** `git diff origin/main --stat -- models h2_pemfc simulation config ems_integration
  reference_models` **vazio**. Previsões não alimentam rodadas: a Simulação V1.6 usa a configuração salva
  (demanda/clima do inventário). Despacho e custo idênticos (testes da seção 9).

### 12. Arquivos modificados

| Arquivo | Propósito |
|---|---|
| `seeds2/operation/forecasts.py` (novo) | variáveis, unidades, instantes/fusos, normalização, qualidade, forma canônica, grade de visualização, prontidão |
| `seeds2/operation/forecast_sources.py` (novo) | CSV (leitura, detecção, mapeamento), manual, sintético, referências V1.6, `rederive` |
| `seeds2/operation/contracts.py` | `ForecastInput` estendido; validação estrutural dos campos novos |
| `seeds2/operation/scenarios.py`, `service.py`, `__init__.py` | completude das previsões no salvamento; prontidão; `save(..., new_blobs)` |
| `seeds2/microgrid/store.py` | blobs de previsão na transação do cenário (`_scenario_blobs`, `_store_scenario_blobs`) |
| `seeds2/ui/forecasts_ui.py`, `forecast_charts.py` (novos) | página Previsões e Dados; gráficos Plotly |
| `seeds2/ui/operation_center.py` | rota `previsoes`, etapa 02 ativa, salvar com blobs, limpeza de estado, estilos |
| `seeds2/ui/shell.py` | `BACKUP_SCOPE` cita as previsões |
| `seeds2/__init__.py` | `APP_VERSION = "2.0.0-piso2b"` |
| `tests/test_seeds2_piso2b.py`, `tests/test_seeds2_piso2b_app.py` (novos) | 24 + 8 testes |
| `tests/test_seeds2_piso2a.py`, `tests/test_seeds2_piso2a_app.py`, `tests/apptest_utils.py` | ver seção 9 |
| `tools/e2e/e2e_piso2b_previsoes.js`, `tools/e2e/seed_piso2b.py` (novos) | E2E do Piso 2B |
| `PARAMIJEFE.md`, `CLAUDE.md`, `docs/ai/HANDOFF.md`, `docs/seeds2/ARMAZENAMENTO.md`, `docs/seeds2/ARQUITETURA_PISO1.md` | documentação |

### 13. Problemas detectados e corrigidos durante a missão

1. `np.isclose` com tolerância RELATIVA em instantes (s desde 1970 → ±17 000 s) fazia a grade transformada colar
   valores de pontos vizinhos → tolerância absoluta (teste `test_grade_transformada_sem_extrapolacao_e_angular`).
2. `rederive` de perfis sintéticos/referência não conferia o blob armazenado (um blob corrompido passava) → a
   verificação começa por `forecasts.load`.
3. `read_csv_auto` (V1.6) adotava uma letra como separador em CSV de uma coluna; colunas repetidas eram renomeadas
   pelo pandas (`a.1`) → `read_table` com separador explícito e checagem do cabeçalho (sem alterar a V1.6).
4. Detecção de deslocamento de fuso confundia "21-03-2026" com "−2026" → o deslocamento só é aceito após um horário.
5. Aba ativa voltava para "Demanda" a cada reexecução (E2E) → `st.tabs` com chave e `on_change="rerun"`.
6. Unidade não era sugerida quando o usuário escolhia manualmente uma coluna com sufixo (`direcao_vento_deg`) →
   detecção a partir do cabeçalho da coluna escolhida.
7. `origin/main` local desatualizado (`761f032`) → linha de base refeita sobre `4709f0c` após `git fetch`.

### 14. Limitações pendentes

1. **Previsões não alimentam rodadas** (Piso 2C): coexistem a demanda/clima do inventário (rodada V1.6) e as do
   cenário. Unificação = decisão do Piso 2C.
2. Conversão para a grade do EMS (método, janela, horizonte móvel) não definida — apenas sinalizada como pendente.
3. Um conjunto climático único por cenário (não há combinação de fontes por variável).
4. Fusos: o alinhamento entre séries com fusos distintos só é avisado (tratamento no Piso 2C).
5. `st.data_editor` não é exercitado pelo AppTest (sem suporte); o perfil manual é testado pela tabela regular +
   valores colados e no domínio. Gráficos: AppTest verifica a especificação; o desenho real no E2E.
6. Sem limpeza de blobs (intencional); sem exclusão/arquivamento de cenários; backup ZIP sem cenários (Piso 2D).
7. `quality`/`stats` da entrada são um instantâneo do momento da incorporação (inventário de referência de então);
   após um `rebase` do inventário, os requisitos do conjunto (`scenario_findings`/prontidão) são recalculados, mas
   avisos como "variável sem tecnologia habilitada" gravados na entrada não. Reincorporar atualiza o instantâneo.
8. Herdadas: `__pycache__/` versionado, sem CI, sem autenticação.

### 15. Instruções para auditoria independente

1. `seeds2/microgrid/store.py` — `_store_scenario_blobs` chamado dentro de `_tx` em `create_scenario`/`save_scenario`
   (depois da verificação de versão/base, antes do INSERT da versão).
2. `seeds2/operation/forecasts.py` — `parse_absolute` (fusos, ordem de data), `assemble` (ordem, duplicatas),
   `analyze`/`_value_findings` (seção 8), `to_csv_bytes`, `grid_view` (sem extrapolação; angular), `entry_errors`.
3. `seeds2/operation/forecast_sources.py` — `read_table`, `inspect_csv`, `normalize_csv` (unidade não confirmada =
   erro), geradores (semente), referências (mesmas funções V1.6), `rederive`.
4. `seeds2/ui/forecasts_ui.py` — separação perfil × pendente; INCORPORAR desabilitado com erros; `op_blobs`.
5. Reproduzir: criar cenário → Previsões → CSV `demanda_e2e.csv` (gerado por `seed_piso2b.py`) → inspecionar →
   incorporar → clima CSV (confirmar unidades) → SALVAR → reiniciar o servidor → reabrir; duas abas no mesmo cenário
   (conflito com o pendente preservado); `UPDATE blobs` no banco de teste → mensagem de dado corrompido.

### 16. Contratos para o Piso 2C

- Ler `doc["forecasts"][slot]` de uma versão IMUTÁVEL (`store.get_scenario(uid, version)`) e a série por
  `forecasts.load(entry, store.get_blob)` (verificada). `contracts.RunReference` continua sendo a chave de
  procedência; a impressão digital do cenário já cobre os SHA-256 das séries.
- A série está na base ORIGINAL; o runner deve escolher a janela experimental e converter para a grade do motor.
  `forecasts.grid_view` (linear; circular para direção; nunca extrapola; ausente em lacunas) é um candidato,
  não uma decisão: método e tratamento de lacunas precisam de aprovação científica.
- Unidades canônicas (seção 5) já correspondem às entradas do adaptador V1.6 (`GHI_W_m2`, `temperature_C`,
  `wind_speed_mps`, `wind_direction_deg`, `pressure_hPa`, `humidity_pct`, `P_kW`).
- `timezone`: `null` = não declarado; o runner deve recusar ou avisar ao combinar séries com fusos diferentes.
- `forecasts.scenario_findings`/`stage_status` dão a prontidão das previsões; `readiness()["executable"]` continua
  `False` até existir o runner.

---

## Entrega 3 — SEEDS2 Piso 2C · Execução EMS e Persistência Científica

### 1. Identificação

| Campo | Valor |
|---|---|
| Piso / missão | **Piso 2C** — Execução EMS e persistência científica (etapas 03 Estratégia EMS e 04 Execução do Centro de Operação) |
| Data | 2026-11-06 |
| Base | `main` em `43ee6f5` (merge do PR #7 — Piso 2B), conferido com `git fetch`; PR #6 (`4709f0c`) e PR #7 integrados |
| Rama | `ccr-21b1e00e-u5u64z` — rama de desenvolvimento designada pelo ambiente desta sessão (a missão propunha `claude/seeds2-piso2c-execucao`; a regra do ambiente proíbe publicar em outra rama sem autorização explícita) |
| PR | [#8](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/8) (sem merge; aguarda auditoria) |
| Estado | Implementado e verificado na rama; **não integrado** em `main` |

### 2. Resumo executivo

**Solicitado:** fechar o circuito experimental *cenário → validação de compatibilidade → preparação das entradas →
modelos físicos → EMS → resultados persistentes*, sem corrigir o otimizador: preflight científico, janela temporal
com fusos/UTC e conversão registrada, Estratégia EMS só com opções existentes, runner separado do Streamlit, entidade
Run imutável com séries completas, resultados mínimos e reabertura sem recalcular, avisos de backup e exclusão.

**Entregue:**
- **Etapa 03 — Estratégia EMS** (`seeds2/operation/strategy.py`, `seeds2/ui/execution_ui.py`): função objetivo ÚNICA
  identificada (custo econômico do EMS V1.6, termos listados; sem seletor multiobjetivo), algoritmo (GA/GWO/NGO/só
  SQP = `RT.ALGORITMOS`), metaheurística penalizada, N, semente, tolerância do SOC-alvo, parâmetros econômicos e
  conversores (mesmas faixas do console V1.6), validação dinâmica do H₂ (única validação implementada); tolerâncias
  fixas do motor apenas informadas. Gravada em `doc["ems_strategy"]` (antes reservado `None`).
- **Etapa 04 — Execução**: janela da missão (`doc["mission"]`, chave nova opcional) separada do horizonte dos
  perfis, do passo do motor (60 s, fixo) e de N; **preflight** com relatório legível (representável / advertência /
  incompatibilidade / verificação no motor / informação), equipamentos excluídos e parâmetros que chegam ao motor;
  EXECUTAR só para a versão SALVA e compatível; progresso real; histórico; vista da rodada imutável (`?run=`).
- **Preflight científico** (`seeds2/operation/preflight.py`): fase A estática + fase B no contrato efetivo do motor
  (lido com a própria `montar_fontes`, antes do otimizador). Casos não representáveis BLOQUEADOS, nunca ignorados.
- **Tempo** (`seeds2/operation/mission.py`): conversão para UTC antes de combinar, recusa de fusos indefinidos
  ambíguos, horário de verão, cobertura sem extrapolação, interpolação linear/circular registrada, ausentes nunca
  viram zero.
- **Runner** (`seeds2/operation/runner.py`): thread própria independente da sessão, serialização no processo,
  idempotência por pedido, uma rodada ativa por microrrede, falha → 'falhou' sem resultados, processo morto →
  'interrompida' por recuperação.
- **Persistência v4** (`scenario_runs` + `scenario_run_data`): manifesto de procedência imutável, conclusão atômica
  (dados + resumo + estado na mesma transação), triggers de imutabilidade.
- **Resultados**: estado, identificação, cenário/versão, custo, energia atendida/não atendida/excedente, H₂, curvas
  Plotly de demanda + potência por fonte, SOC e H₂ — tudo lido do banco.
- **Backup/exclusão**: `BACKUP_SCOPE`/`RESTORE_SCOPE` citam as rodadas do 2C; diálogo de exclusão mostra a contagem e
  exige consentimento específico (com recontagem no clique), somado ao da C-01.
- Testes: 37 novos (29 domínio + 8 interface), 7 ajustados (estado real da navegação); E2E Chromium novo do Piso 2C
  com **servidor derrubado durante uma rodada** e reinício; E2E dos Pisos 1/Gestor/2A/2B repetidos (§10).

**Fora do escopo (intencional):** reformular o EMS (SOC, `n_ini`, `P_prev`, rampas, partidas), múltiplos objetivos,
arquivo científico PDF/Excel/ZIP e portabilidade das rodadas (Piso 2D), comparações avançadas (Piso 4), cancelamento
de rodada em andamento.

### 3. Arquitetura encontrada (`main` `43ee6f5`) e contrato real do runtime

- `RT.build_exchange_package(carga, model_spec, optimizer_cfg, climate_raw=None, destino=None)` → (pasta do pacote,
  saídas dos modelos). `carga` é `ponte.PerfilCarga(t_min, P_kW, t0 ingênuo, descrição)` com grade de 1 min
  (`t_min` 0..D, D+1 pontos); `Ts_s` = 60 fixo no `ems_config.json`. Clima: `"Sintético diário"` ou `"CSV climático"`
  (`climate_from_csv` → `mix_engine.detect_climate_columns` → `prepare_climate` → `align_climate_to_operation`).
  Atenção: `align_climate_to_operation` interpola **sobre ausentes** e `np.interp` **satura nas bordas** (extrapolação
  constante); por isso o 2C entrega o clima JÁ na grade exata da missão e só com variáveis completas (ver §6).
- `RT.run_optimizer(pasta, optimizer_cfg, progress=None)` → `executor.executar_pacote(progresso=…)`: o callback
  recebe `(k, n)` a cada passo do despacho — progresso REAL usado pela interface. `validar=True` chama
  `validar_fc_dinamico`.
- `RT.series_dataframe(r)` (ponto de partida das séries gravadas) omite saídas existentes do motor: potência
  renovável disponível (η aplicado), custo de partida, violação do refino, combinações avaliadas, envelopes
  `P_max_unid_kW` e o H₂ da validação dinâmica. O 2C grava `series_dataframe` **inteiro** + essas colunas.
- Estados iniciais implícitos (código): `fontes.montar_fontes` fixa `n_ini = N_fc` (PEMFC, `dn_max = 1`),
  `n_ini = int(P_min[0] > 0)` (térmica) e `SOC_ini` = primeiro SOC da caracterização; `despacho` começa com
  `P_prev = 0` e, com `|P_prev| < 1e-6`, NÃO aplica a rampa do 1º passo; o SOC-alvo final é o SOC inicial ± tolerância.

### 4. Decisões técnicas

| # | Tema | Alternativas | Escolha e justificativa |
|---|---|---|---|
| C1 | Onde fica a janela | parâmetro da rodada × no cenário | **No cenário** (`mission`): a rodada é determinada por (cenário, versão) — reprodutível; a mesma versão reexecutada dá o mesmo resultado (semente). |
| C2 | Evolução do documento | `schema_version` 2 × campos compatíveis | `ems_strategy` (já reservado) passa a aceitar o bloco validado; `mission` é chave **opcional** (ausente = `None`): versões antigas mantêm a impressão digital; `schema_version` continua 1. |
| C3 | Indisponibilidade | ignorar × bloquear × excluir só da rodada | **Excluir só da rodada**: cópia da revisão de referência com o equipamento desabilitado → o adaptador agrega apenas o fisicamente equivalente (p. ex. N_fc 4 → 3). Listado no relatório e na rodada; inventário intacto. |
| C4 | Equipamento disponível não representável (FV declarado, heterogêneo, ModelLab, térmica de grande porte) | confirmar e omitir (como o console V1.6) × bloquear | **Bloquear** (regra "nunca executar outro cenário"); o usuário pode declará-lo indisponível no cenário (decisão explícita e registrada). |
| C5 | Inventário mudou depois do cenário | bloquear × usar a revisão de referência | **Revisão de referência** (imutável) com **advertência**; `rebase` continua explícito. |
| C6 | Séries sem fuso | recusar sempre × declaração explícita | Recusar ao combinar, salvo declaração explícita "mesmo relógio" na janela (gravada na rodada). Necessária porque os conjuntos de referência do 2B não declaram fuso. Declarado × não declarado = recusa. |
| C7 | Grade do clima | entregar a série original ao runtime × grade da missão | **Grade da missão** com nomes reconhecidos por `detect_climate_columns`: o alinhamento interno vira identidade; nada é interpolado/extrapolado pelo runtime sem registro. |
| C8 | Variável opcional com lacuna na janela | descartar em silêncio × usar referência × bloquear | **Bloquear** (e informar). Variável opcional ausente do perfil → comportamento existente do modelo eólico (densidade de referência), informado. |
| C9 | PEMFC/térmica com potência inicial > 0 | bloquear sempre × provar equivalência | **Provar** (fase B): com a própria `despacho._n_prev_de`, a rampa do 1º passo que o EMS aplicaria com `P_prev = P0` é inativa em toda a caixa viável das configurações candidatas ⇒ mesmo problema que `P_prev = 0`. Senão: rodada 'falhou' (incompatibilidade) SEM chamar o otimizador. |
| C10 | Execução | síncrona no script Streamlit × thread própria | **Thread própria** (recarga/fechamento da página não interrompe; progresso lido do banco por `st.fragment(run_every=1s)`); `_ENGINE_LOCK` serializa execuções no processo. |
| C11 | Séries | tabela `blobs` × tabela própria | **`scenario_run_data`** com triggers de imutabilidade e inserção só durante a execução (blobs não têm essas garantias). zlib > 2 KiB; SHA-256 do conteúdo descomprimido. |
| C12 | Duplicação | confiar no botão × chave de pedido | `request_id` UNIQUE gerado por renderização e consumido no clique + no máximo 1 rodada ativa por microrrede. |
| C13 | Recuperação | timeout fixo × dono verificável | Dono `host|pid|token`; PID inexistente / token diferente / thread encerrada ⇒ 'interrompida'; outro host: 30 min sem sinal. |
| C14 | `readiness()["executable"]` | manter `False` × decidir no documento | `None` = "decidido pelo preflight" (a prontidão do documento não lê inventário nem séries). |
| C15 | `APP_VERSION` | — | `2.0.0-piso2c`. |

### 5. Contrato de execução

```
runner.submit(store, scenario_uid, version, request_id, background=True) -> StoredRun
  1. P.prepare(store, store.get_scenario(uid, version))   # fase A; PreflightError se incompatível (nada iniciado)
  2. store.start_run(run_uid, request_id, …, manifest)    # 'em_execucao'; idempotente; RunBusyError
  3. thread: PerfilCarga(grade da missão) + clima na grade → RT.build_exchange_package(…, destino=tmp)
  4. P.engine_check(pf, pacote)                           # fase B; incompatível → fail_run('incompatibilidade')
  5. RT.run_optimizer(pacote, optimizer_cfg, progress=k/n → heartbeat_run)
  6. store.finish_run(dados + resumo + resultado)         # uma transação; exceção → fail_run('falha')
runner.recover(store)   # rodadas órfãs → 'interrompida'
```

`optimizer_cfg` = `strategy.optimizer_config(ems_strategy)` — formato idêntico ao do formulário V1.6 (o padrão é
igual a `RT.default_optimizer_config()`, testado). `model_spec` = `adapter.build_plan(cópia efetiva,
external_inputs=True).spec`. O EMS, os modelos e o runtime são chamados sem alteração.

**Manifesto** (`scenario_runs.manifest`, imutável): `reference` (`RunReference`: microrrede/incarnação, cenário,
versão, impressão digital, revisão/impressão do inventário), cenário (nome, descrição), `software` (SEEDS2, Python,
numpy, pandas, scipy e SHA-256 de 64 arquivos `.py`/`.csv`/`.json` de `models/`, `h2_pemfc/`, `simulation/`, `ems_integration/`,
`config/`, `orchestrator_runtime.py`), função objetivo, estratégia exata, parâmetros fixos do motor, janela
(início local/UTC, fuso, duração, passos, declaração de relógio), previsões (SHA-256 da série e do original, origem,
procedência, fuso, transformações), `engine_inputs` (spec, optimizer_cfg, estado declarado, regra do motor, grade,
conversões), relatório completo do preflight. **Resultado** (`outcome`): verificação da fase B com o estado inicial
efetivo do motor (n_ini, SOC_ini, P_prev, envelopes, rampas), fontes efetivas, avisos e tempo.

### 6. Compatibilidade com o EMS — casos representáveis e não representáveis

| Condição declarada | Motor V1.6 | Decisão |
|---|---|---|
| Bateria, SOC em [SOC_min, SOC_max] do inventário | `SOC_ini` = SOC; alvo final = SOC ± tol | **Representável** (fase B confere `SOC_ini` = SOC ± 1e-6) |
| Bateria, SOC em [0, 100] fora de [SOC_min, SOC_max] | limites são restrição efetiva | Cenário **gravável** (aviso); execução **bloqueada** |
| Bancos agregáveis com SOC diferentes | um único SOC por grupo | **Bloqueado** |
| PEMFC em operação, todas as unidades, P0 = 0 | `n_ini = N_fc`, `P_prev = 0` | **Exatamente** o contrato |
| PEMFC em operação, todas as unidades, P0 > 0 (base "entregue") | `P_prev = 0` | **Condicional** (fase B: rampa do 1º passo inativa) — testado: 100 kW executa; 195 kW recusado sem otimizador |
| PEMFC desligada / em partida / parte das unidades / P0 > 0 com base "stack" | `n_ini = N_fc` | **Bloqueado** |
| Térmica desligada com Pmín = 0 | `n_ini = 0` | **Exato** (fase B confere `n_ini`) |
| Térmica em operação com Pmín > 0 | `n_ini = 1`, `P_prev = 0` | **Condicional** (fase B) — testado: 50 kW / rampa 40 executa; 75 kW recusado |
| Térmica desligada com Pmín > 0; em operação com Pmín = 0; em partida | — | **Bloqueado** |
| Equipamento indisponível | — | **Excluído só da rodada** (agregação exata) |
| Nenhuma fonte despachável disponível | EMS exige ≥ 1 | **Bloqueado** |
| Equipamento disponível não representável | — | **Bloqueado** (C4) |
| Variável opcional (eólica) ausente do perfil | densidade do ar de referência | Representável (informado) |

### 7. Tratamento temporal

UTC comum (IANA com DST via `tz_localize(ambiguous/nonexistent="NaT")`, `UTC±hh:mm` fixo); instantes ambíguos
de mudança de horário a menos de 2 h da janela → recusa; início ambíguo → recusa. Grade = início (UTC) + k·60 s,
k = 0..D; ao runtime vai a grade UNIFORME a partir do início local (rótulos), e cada passo grava `timestamp_utc`,
`timestamp_local` (relógio real do fuso) e `timestamp_runtime`. Cobertura: a grade inteira dentro de cada série
(sem extrapolação). Conversão: amostra coincidente → identidade; senão linear entre vizinhas (direção: circular
pelo menor arco), registrada por variável (método, nº de pontos exatos/interpolados, passo original; passo < 60 s
→ "valores pontuais, sem média"). Ponto em lacuna (> 1,5 × passo típico) ou junto a ausente → ausente → bloqueio
se a variável for usada. Séries originais do cenário intocadas.

### 8. Armazenamento

Esquema **v4** (migração só com tabelas novas; `.bak-v3`). Detalhes, garantias de imutabilidade, recuperação e
H-01/H-02/H-03: `docs/seeds2/ARMAZENAMENTO.md` §"Rodadas de cenário". Dados por rodada concluída:
`entradas/missao.csv` (grade com UTC/local/runtime, demanda e clima usados), `saidas/despacho_ems.csv`
(`series_dataframe` + extras), `saidas/relatorio_ems.json` (`rel`, log, avisos, metadados das fontes, bateria,
configuração do pacote, validação dinâmica), `modelos/*.csv` (caracterizações FC/bateria, disponibilidade térmica,
clima, saídas solar/eólica) e `pacote_troca.zip` (o pacote auditável lido pelo EMS).

### 9. Pruebas e resultados exatos

Ambiente: Linux, Python 3.13.18, Streamlit 1.66.1, numpy 2.2.6, scipy 1.15.3, pandas 2.2.3; `PYTHONDONTWRITEBYTECODE=1`.

| Momento | Comando | Resultado |
|---|---|---|
| Linha de base (`main` `43ee6f5`) | `python -m pytest tests/ -q` | **308 passed** (120 s; 105 subtests; 7 avisos) |
| Primeira execução com o 2C | idem | 7 failed / 301 passed — todas asserções do estado anterior ("Não implementado", `executable is False`, esquema v3, textos do ZIP); atualizadas para o estado real (abaixo) |
| Versão final da rama | `python -m pytest tests/ -q` | **345 passed, 0 failed, 0 skipped** (189 s; 105 subtests; 7 avisos, os mesmos da linha de base) — 308 anteriores + 37 novos |

Ajustes em testes existentes (navegação/estado reais; nenhuma asserção enfraquecida — cada uma foi substituída por
outra mais forte): `test_seeds2_piso2a.py` (migração v2 → **v4** com `.bak-v2`; manifesto `db_schema_version` =
`LATEST_DB_VERSION`; prontidão: `executable is None`, Estratégia "Não definida", Execução "Janela não definida"),
`test_seeds2_piso2b.py` (idem prontidão), `test_seeds2_piso2a_app.py`/`test_seeds2_piso2b_app.py` (FAKE não proíbe
mais "ESTRATÉGIA" — `ABRIR ESTRATÉGIA EMS`/`ABRIR EXECUÇÃO` existem e são verificados; "EXECUTAR" continua proibido
no painel e nas etapas 01/02; zero "Não implementado"; textos de alcance do ZIP com as rodadas), `apptest_utils.py`
(`continuar()` transporta `op_run_uid` e `op_ex_*`). Comparação numérica: nenhuma tolerância alterada.

Novos testes — mapa dos requisitos da missão (§11):

| Requisito | Teste (`tests/test_seeds2_piso2c.py` / `_app.py`) |
|---|---|
| Preflight compatível / incompatível | `test_cenario_compativel_relata_o_que_chega_ao_motor`; `test_cenario_incompativel_nao_pode_ser_executado` (UI) |
| SOC fora da recomendação mas gravável; incompatível com limites efetivos | `test_soc_fora_da_recomendacao_salva_mas_fora_dos_limites_efetivos_bloqueia`; `test_bancos_com_soc_diferentes_nao_sao_representaveis` |
| PEMFC / térmica não representáveis | `test_pemfc_estados_nao_representaveis`; `test_termica_estados_e_pmin`; `test_pemfc_potencia_inicial_rampa_comprovada_ou_execucao_recusada`; `test_termica_em_operacao_executa_com_rampa_comprovada` |
| Disponibilidade | `test_disponibilidade_exclui_somente_da_rodada`; `test_equipamento_nao_representavel_nunca_omitido_em_silencio` |
| Fusos e conversão | `test_fusos_diferentes_convertidos_para_utc`; `test_fuso_nao_declarado_exige_declaracao_explicita`; `test_horario_de_verao_ambiguo_perto_da_janela_recusado` |
| Ausência de cobertura | `test_sem_cobertura_nunca_extrapola` |
| Interpolação documentada sem extrapolação | `test_interpolacao_registrada_sem_extrapolacao_e_angular`; `test_clima_de_10_min_interpolado_e_registrado_na_rodada` |
| Execução real + comparação com o V1.6 | `test_execucao_real_igual_ao_ems_v16_e_gravacao_completa` (custo idêntico; `P_kW` ≤ 1e-9 kW; SOC ≤ 1e-12) |
| Resultados completos | idem (colunas de `series_dataframe` ⊂ gravadas; indicadores = séries; pacote de troca) |
| Recuperação após reinício | `test_reinicio_reabre_resultados_sem_recalcular_e_interrupcao_recuperada` (subprocesso com runtime sabotado; `os._exit` no meio do despacho → 'interrompida') |
| Versões históricas imutáveis | `test_rodada_concluida_e_imutavel_e_versao_historica_preservada`; `test_edicao_posterior_nao_altera_rodada_e_nova_rodada_usa_nova_versao` (UI) |
| Conflitos e isolamento | `test_isolamento_entre_microrredes`; `test_uma_rodada_ativa_por_microrrede` |
| Falhas do solver e interrupções | `test_falha_do_solver_e_dos_modelos_nao_gravam_resultados`; `test_rodada_falha_mostra_motivo_sem_resultados` (UI) |
| Sem execução duplicada por recarga | `test_sem_execucao_duplicada_por_reenvio_do_mesmo_pedido`; `test_executar_em_segundo_plano_reabrir_sem_recalcular_e_sem_duplicar` (UI) |
| Progresso real | `test_execucao_em_segundo_plano_com_progresso_real` |
| Estratégia (opções existentes, gravada na versão) | `EstrategiaTest` (3); `test_definir_padrao_salvar_como_nova_versao` (UI) |
| Pisos 1/2A/2B preservados | suíte completa; `test_console_v16_inalterado` (R$ 417,684638); `test_migracao_v3_para_v4_preserva_cenarios_e_backup_sem_rodadas`; `test_documento_antigo_sem_bloco_mission_continua_valido` |
| Exclusão com rodadas | `test_dialogo_informa_rodadas_e_exige_consentimento_especifico` (UI) |

### 10. E2E e evidência visual

Chromium real (Playwright), servidores Streamlit reais, diretórios vazios:

| Roteiro | Fases | Resultado |
|---|---|---|
| `tools/e2e/e2e_piso2c_execucao.js` (novo; dados `tools/e2e/seed_piso2c.py`) | operar 38 · **`kill -9` do servidor durante a rodada longa** · reinício 10 · tablet 7 | **55/55** |

(Repetição dos E2E dos Pisos 1, Gestor, 2A e 2B: em execução no momento deste commit — resultado no commit seguinte.)

### 11. Compatibilidade

- **EMS / modelos / runtime / console V1.6:** `git diff origin/main --stat -- models h2_pemfc simulation config
  ems_integration reference_models orchestrator_runtime.py orchestrator_app.py` **vazio**. A Simulação V1.6 continua
  independente (configuração salva, `run_conditions`, demanda/clima do inventário) — despacho e custo de referência
  inalterados (R$ 417,684638).
- **Piso 1 / Gestor:** fluxo inalterado; banco v3 → v4 automático; backup ZIP formato 2 inalterado (manifesto
  declara `db_schema_version` 4; backups antigos aceitos).
- **Pisos 2A/2B:** documentos antigos válidos sem mudança de impressão digital (`mission` opcional); Inicialização e
  Previsões inalteradas (só textos de alcance atualizados).

### 12. Arquivos modificados

| Arquivo | Propósito |
|---|---|
| `seeds2/operation/strategy.py` (novo) | estratégia EMS e janela da missão: opções existentes, faixas, `optimizer_config` |
| `seeds2/operation/mission.py` (novo) | fusos/UTC, cobertura, conversão para a grade, clima para o runtime |
| `seeds2/operation/preflight.py` (novo) | fases A e B, relatório, regras de representabilidade |
| `seeds2/operation/runner.py` (novo) | execução, procedência, séries, resumo, recuperação |
| `seeds2/operation/scenarios.py`, `contracts.py` | blocos `ems_strategy`/`mission`; prontidão das etapas 03/04; estados de rodada |
| `seeds2/microgrid/store.py` | esquema v4 e API de rodadas |
| `seeds2/microgrid/adapter.py` | `build_plan(..., external_inputs=True)` (demanda/clima vindos do cenário; classificação inalterada) |
| `seeds2/ui/execution_ui.py`, `run_charts.py` (novos) | etapas 03/04, rodada, gráficos |
| `seeds2/ui/operation_center.py`, `forecasts_ui.py`, `shell.py`, `gestor.py` | rotas, etapas reais, `?run=`, textos de alcance, exclusão com rodadas |
| `seeds2/__init__.py` | `APP_VERSION = "2.0.0-piso2c"` |
| `tests/test_seeds2_piso2c.py`, `tests/test_seeds2_piso2c_app.py` (novos) + ajustes (§9) | testes |
| `tools/e2e/e2e_piso2c_execucao.js`, `tools/e2e/seed_piso2c.py` (novos); `e2e_piso2a…`, `e2e_piso2b…` | E2E |
| `PARAMIJEFE.md`, `CLAUDE.md`, `docs/ai/HANDOFF.md`, `docs/seeds2/ARMAZENAMENTO.md` | documentação |

### 13. Problemas detectados e corrigidos durante a missão

1. `mix_engine.detect_climate_columns` não reconhece `GHI_W_m2` (só `ghi`/`irradiance`…): o clima entregue ao
   runtime usa a coluna `GHI` (sem alterar a V1.6).
2. Interpolação angular devolvia 360,0 para ângulos ≈ −1e-15 (arredondamento de `% 360`) → normalizado para [0, 360).
3. `shell.go` limpava `?run=` ao recompor a URL → a rodada aberta passou a sobreviver à recarga.
4. Plotly 6 serializa arrays como `{dtype, bdata}`: os testes de interface e o E2E decodificam/usam `_fullData`.
5. Arquivos `__pycache__/*.pyc` versionados foram reescritos por comandos auxiliares sem `PYTHONDONTWRITEBYTECODE`
   e restaurados com `git checkout` antes do commit (nenhum `.pyc` no PR).

### 14. Limitações pendentes

1. **Capacidades científicas pendentes (piso do otimizador; bloqueadas, não reformuladas):** SOC inicial fora dos
   limites efetivos; SOC distintos entre bancos; PEMFC desligada/em partida/parcial; potência inicial cuja rampa do
   1º passo seria ativa; térmica com estado ≠ `int(Pmín > 0)`; física de partida; excedente renovável → bateria.
2. Variável opcional com lacuna na janela bloqueia (não há política de preenchimento aprovada).
3. Sem cancelamento de rodada em andamento; execuções serializadas no processo (uma por vez no servidor).
4. Um processo vivo em OUTRO host só é considerado morto após 30 min sem sinal (implantação multi-host não é alvo).
5. A grade entregue ao runtime é uniforme a partir do início local: numa janela que cruza mudança de horário os
   rótulos `timestamp_runtime` diferem do relógio real (ambos gravados; os modelos V1.6 não usam a hora do dia com
   clima por CSV).
6. Backup ZIP sem cenários/rodadas; arquivo científico completo (PDF/Excel/ZIP) e importação = Piso 2D.
7. Herdadas: `__pycache__/` versionado, sem CI, sem autenticação.

### 15. Instruções para auditoria independente

1. `seeds2/operation/preflight.py` — `_classify` (regras de §6), `ramp_inactive` (prova com `despacho._n_prev_de`),
   `_engine_sources` (cópia literal das linhas de `executor.executar_pacote` que montam `arch`/`econ`).
2. `seeds2/operation/mission.py` — `wall_to_utc`, `build_window`, `resample` (comparar com `forecasts.grid_view`).
3. `seeds2/operation/runner.py` — `_execute` (ordem fase B → otimizador → `finish_run`), `owner_is_dead`, `submit`.
4. `seeds2/microgrid/store.py` — migração 4 (triggers), `start_run`/`finish_run`/`fail_run`/`_recover_con`.
5. Reproduzir: `python tools/e2e/seed_piso2c.py <dir>` → servidor → Centro → Estratégia (padrão, salvar) → Execução
   (definir janela, salvar, EXECUTAR) → rodada; Inicialização com SOC 15 % → Execução bloqueada; missão longa e
   `kill -9` do servidor durante a rodada → reinício → "Interrompida".

### 16. Próximo passo sugerido (não implementado)

**Piso 2D — Arquivo científico:** exportação/importação de cenários + rodadas (manifesto, `scenario_run_data` com
SHA-256) em ZIP científico, PDF/Excel; depois, piso do otimizador para as capacidades pendentes do §14.1.

---


## Histórico de entregas

| Entrega | Data | Missão | Rama / PR | Estado |
|---|---|---|---|---|
| 1 | 2026-11-06 | Piso 2A — Centro de Operação (fundação operacional) | `claude/seeds2-piso2a-centro-operacao` / [#6](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/6) | **Integrado** em `main` (merge `4709f0c`), após auditoria favorável e correção C-01 (§15) |
| 2 | 2026-11-06 | Piso 2B — Previsões e Dados | `ccr-68eaae98-0rs4e4` / [#7](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/7) | **Integrado** em `main` (merge `43ee6f5`) |
| 3 | 2026-11-06 | Piso 2C — Execução EMS e Persistência Científica | `ccr-21b1e00e-u5u64z` / [#8](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/8) | Implementado e verificado na rama; aguardando auditoria (sem merge) |
