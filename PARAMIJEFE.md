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

| `tools/e2e/e2e_piso2b_previsoes.js` | operar 43 · reinício 8 · tablet 7 | **58/58** (2 asserções atualizadas ao estado real: zero "Não implementado"; aviso de que as previsões alimentam a Execução) |
| `tools/e2e/e2e_piso2a_centro_operacao.js` | operar 43 · reinício 5 · tablet 5 | **53/53** (+2 verificações: ABRIR ESTRATÉGIA EMS e ABRIR EXECUÇÃO; EXECUTAR continua proibido no painel) |
| `tools/e2e/e2e_gestor_microrredes.js` (`SEEDS2_DEV_MODE=1`; `legado` com banco v2 anterior ao Gestor, agora migrado até v4) | multi 39 · reinício 6 · tablet 2 · legado 5 | **52/52** |
| `tools/e2e/e2e_piso1_microrrede.js` (inclui rodada EMS real do console V1.6) | comissionar 41 · reabrir 21 · tablet 4 | **66/66** |

Todos desde diretórios vazios, com reinício real do servidor entre fases, sem exceções Streamlit nem erros de
JavaScript. Verificado no navegador (2C): função objetivo única e algoritmos existentes; estratégia e janela gravadas
como versões 3 e 4; relatório com conversão UTC (demanda America/Sao_Paulo × clima UTC) e interpolação registrada
(clima de 10 min → grade de 1 min); EXECUTAR bloqueado com alterações não salvas e com SOC 15 %; rodada concluída com
indicadores e curvas Plotly (121 passos); recarga do navegador reabre a MESMA rodada (`?run=`) sem criar outra;
`kill -9` do servidor durante a rodada de 700 min (fase "modelos" gravada no banco) → após o reinício: "Interrompida",
sem dados (`scenario_run_data` vazio), rodada concluída reaberta com o mesmo custo; tablet retrato/paisagem sem rolagem
horizontal; tema escuro. Estado final do banco: `[('concluida', v4, 8 dados), ('interrompida', v7, 0 dados)]`.
Na primeira execução do roteiro 2C a verificação do número de pontos da curva falhou por um erro do PRÓPRIO roteiro
(lia `data[].y`, que o Plotly 6 mantém codificado em base64); corrigido para `_fullData` e o protocolo inteiro repetido.

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

### 17. Correção de auditoria C-02 — validade do preflight científico

A auditoria independente do PR #8 foi **favorável** (arquitetura de execução, persistência v4, separação
cenário/rodada, integração com o EMS V1.6, rastreabilidade e recuperação aprovadas) e pediu duas correções pontuais do
preflight antes do merge. Escopo: somente `seeds2/operation/preflight.py` e testes de regressão; modelos, EMS,
otimizador, N, esquema v4 e contratos de resultados **inalterados**.

**C-02.1 — equipamento indisponível com estado inicial incompleto**

- *Causa:* `initialization._battery/_pemfc/_thermal` (Piso 2A) devolvem `incompleto` quando o SOC / o estado operativo
  não está definido, mesmo com `availability = "indisponivel"`; `preflight.prepare` convertia TODO `incompleto` em
  incompatibilidade ANTES de excluir o equipamento do plano efetivo. Um banco excluído — cujo SOC o motor nunca lê —
  impedia a execução.
- *Correção:* o preflight determina primeiro os equipamentos declarados indisponíveis e habilitados na revisão de
  referência (os que serão excluídos do despacho). Para ESSES, `incompleto` vira **informação** explícita ("estado
  inicial não definido e NÃO requerido — excluído do despacho desta rodada"); `erro` de coerência continua
  bloqueando (p. ex. indisponível e "em operação"); `aviso` continua aviso. Equipamentos disponíveis com estado
  incompleto continuam bloqueados. As regras do Piso 2A não foram alteradas (gravação e Inicialização idênticas); o
  inventário físico e a versão do cenário não são modificados. Vale para bateria, PEMFC e térmica.

**C-02.2 — potência inicial e limites efetivos da caracterização**

- *Causa:* `ramp_inactive` só verificava a rampa do 1º passo e, com rampa infinita, aceitava qualquer potência inicial
  sem conferi-la com o envelope caracterizado pelo motor.
- *Correção:* nova `initial_power_admissible(f, P0)` na fase B, executada ANTES da rampa para PEMFC e térmica com
  P0 > 0: com o contrato já caracterizado (`montar_fontes`), exige `n_ini ≥ 1` e
  `n_ini·P_min_unid_kW[0] ≤ P0 ≤ n_ini·P_max_unid_kW[0]` (estado discreto que o motor realmente representa:
  PEMFC `n_ini = N_fc`; térmica `n_ini = 1`). Fora do intervalo → rodada `falhou` (`incompatibilidade`) sem chamar
  `run_optimizer`, com o valor declarado e o intervalo efetivo no relatório da rodada. Só se admissível avalia-se a
  rampa; rampa ilimitada dispensa a rampa, NÃO os limites físicos. P0 = 0 mantém o tratamento existente (convenção
  inicial exata do motor, sem verificação condicionada). Nenhuma física de partida acrescentada.

**Evidência** (`tests/test_seeds2_piso2c.py`, classes `CorrecaoC02IndisponivelTest` e `CorrecaoC02PotenciaInicialTest`):

| Exigência da auditoria | Teste | Resultado |
|---|---|---|
| Bateria indisponível, SOC indefinido, outra despachável disponível → compatível | `test_bateria_indisponivel_sem_soc_executa_e_fica_fora_do_pacote` | rodada concluída; 2 informações "NÃO requerido" |
| Mesma bateria disponível com SOC indefinido → bloqueada | `test_bateria_disponivel_sem_soc_continua_bloqueada` | `PreflightError`, nada iniciado |
| Indisponível com estado contraditório → erro conservado | `test_indisponivel_com_estado_contraditorio_mantem_o_erro` | Piso 2A recusa gravar; documento gravado à força → preflight recusa |
| Fonte excluída ausente do pacote do EMS | idem ao 1º | `nomes = ["fc"]`; sem `bateria.csv`; `opcoes_fontes.fontes = ["fc"]`; sem coluna de SOC |
| Inventário e cenário gravado intactos | idem ao 1º | revisão/impressão digital do inventário e do cenário iguais; SOC continua `None` |
| PEMFC e térmica (mesma regra) | `test_pemfc_e_termica_indisponiveis_sem_estado_nao_exigem_estado` | compatível (N_fc 3; térmica fora); PEMFC disponível sem estado → bloqueio |
| P0 > 0 dentro do envelope e rampa inativa → permitida | `test_dentro_do_envelope_rampa_inativa_e_resultado_identico_ao_p0_zero` | concluída; custo e despacho **idênticos** ao caso P0 = 0 |
| P0 fora do envelope, rampa ilimitada → recusada | `test_fora_do_envelope_com_rampa_ilimitada_recusada`; `test_admissibilidade_independe_da_rampa` | `falhou/incompatibilidade`; "intervalo efetivo [40, 200] kW" |
| P0 fora do envelope, rampa finita → recusada | `test_fora_do_envelope_com_rampa_finita_recusada_antes_do_otimizador` | idem; rampa nem avaliada |
| P0 válida, rampa restritiva → recusada | `test_valida_mas_rampa_restritiva_continua_recusada` | envelope ok, depois "PODERIA restringir" |
| Detecção antes de `run_optimizer` | todos os casos recusados com `run_optimizer` substituído por `AssertionError` | otimizador nunca chamado |
| Térmica sem rampa (ilimitada) dentro do envelope | `test_termica_sem_rampa_dentro_do_envelope_executa` | concluída; "[20, 80] kW" |
| Casos equivalentes ao V1.6 inalterados | `test_execucao_real_igual_ao_ems_v16_e_gravacao_completa`; `test_console_v16_inalterado` | custo idêntico; R$ 417,684638 |

Execuções: `python -m pytest tests/ -q` → **355 passed, 0 failed** (248 s; 105 subtests; os mesmos 7 avisos) — 345 anteriores + 10 novos; nenhum teste existente alterado. E2E Piso 2C repetido desde diretório vazio
(`kill -9` do servidor durante a rodada + reinício): **55/55** (operar 38 · reinício 10 · tablet 7; estado final do banco `[('concluida', v4, 8 dados), ('interrompida', v7, 0 dados)]`). `git diff origin/main --stat -- models h2_pemfc
simulation config ems_integration reference_models orchestrator_runtime.py orchestrator_app.py` **vazio**.

**Riscos residuais:** (1) a admissibilidade usa o envelope do 1º passo da caracterização (como o próprio EMS); a
duração da missão altera a caracterização da PEMFC (rampa observada 6 kW/min em 10 min × 36 kW/min em ≥ 30 min) —
comportamento existente do motor, não alterado; (2) estados de equipamentos indisponíveis continuam visíveis na
Inicialização como "não definido" (regra do Piso 2A preservada de propósito); (3) avisos de valores declarados de
equipamentos indisponíveis (p. ex. SOC fora do recomendado) continuam aparecendo como advertências não bloqueantes.

---


## Entrega 4 — SEEDS2 Piso 2D-A · Arquivo Científico Portátil

### Ponto de continuidade (atualizar ao encerrar ou interromper a sessão)

| Campo | Valor |
|---|---|
| Rama vigente | `ccr-dea994b8-wl7tp3` (designada pelo ambiente desta sessão; a missão propunha `claude/seeds2-piso2da-arquivo-cientifico` — a regra do ambiente proíbe publicar noutra rama sem autorização explícita) |
| PR | [#9](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/9) (sem merge; aguarda auditoria) |
| Último commit publicado | ver `git log -1 origin/ccr-dea994b8-wl7tp3` (o SHA final é informado no PR) |
| Hitos concluídos | A (contrato + verificação), B (exportador), C (importador + persistência), D (interface + E2E); correção de auditoria C-03 (§20) |
| Hito pendente | nenhum desta missão; integração aguarda auditoria |
| Pruebas aprovadas | `python -m pytest tests/ -q` 407 passed (após C-03); E2E 2D-A 62/62; regressão E2E Piso 1 66/66, Gestor 52/52, 2A 53/53, 2B 58/58, 2C 55/55 |
| Próxima ação concreta | auditoria independente do PR; depois, Piso 2D-B (relatórios PDF/Excel/figuras a partir de `StudyView`) |

### 1. Resumo executivo

**Solicitado:** exportar um cenário científico completo, guardá-lo fora do SEEDS2 e importá-lo noutra instalação,
recuperando configurações, dados, gráficos, resultados e procedência **sem executar o EMS de novo**; verificação de
integridade antes de importar; importação atômica e somente leitura; segurança contra pacotes maliciosos; interface
"ARQUIVO CIENTÍFICO" no Centro de Operação; separação nítida entre o arquivo científico e o backup do Gestor.

**Entregue:**
- **Contrato `seeds2-study` v1** (`.seeds2study.zip`; `seeds2/archive/format.py`): manifesto com identidade de origem,
  contagens, índice de recursos (SHA-256, tamanho, tipo, papel) e grafo de dependências; documentos e manifestos com o
  **texto exato** gravado na origem; blobs endereçados pelo SHA-256; rodadas finalizadas com os estados originais.
- **Exportador** (`exporter.py`) a partir de UM instantâneo de leitura (`MicrogridStore.snapshot`, H-03), escrevendo
  recurso a recurso; rodada em execução impede a exportação.
- **Inspeção** de pacote não confiável (formato, versão, estrutura, SHA-256 e tamanho de TODOS os recursos, impressões
  digitais dos documentos, relações cenário↔versões↔inventário↔previsões↔rodadas, ausência de arquivos inesperados,
  duplicados, links, caminhos perigosos, executáveis, bombas ZIP, JSON aninhado/duplicado) com diagnóstico legível.
- **Arquivo Científico da instalação** (`store.py`): banco próprio `scientific_archive/archive.db`, tabelas imutáveis,
  importação atômica (uma transação), identidade LOCAL (`archive_uid`) separada da identidade de ORIGEM, duplicatas
  reconhecidas por `content_id` ou cópia identificável (`copy_of`).
- **Consulta histórica** (`view.py` + `ui/archive_ui.py`): procedência, configuração (inventário de referência, estados
  iniciais, estratégia, janela), previsões (gráficos 2B), rodadas e resultados (KPIs e gráficos 2C reutilizados por
  `execution_ui.run_results`), integridade — sem nenhuma rota até `run_optimizer`/`build_exchange_package`.
- **Interface:** cartão + aba "Arquivo Científico" no Centro de Operação (exportar / arquivar nesta instalação /
  importar / consultar) e botão **ARQUIVO CIENTÍFICO** no Gestor (instalação vazia: importar e consultar sem microrrede).
- **Gestor:** textos de alcance atualizados (o backup não contém cenários; o arquivo científico não substitui o backup);
  diálogo de exclusão aponta EXPORTAR CENÁRIO COMPLETO; consentimentos C-01/C-02 e H-01/H-02/H-03 intactos.

**Fora do escopo (intencional):** PDF, Excel, ZIP de figuras (Piso 2D-B); "CRIAR VARIANTE OPERATIVA" (só contrato
documentado em `seeds2/archive/service.py`); reexecução de estudos antigos; exclusão/edição de estudos arquivados;
qualquer mudança no EMS, modelos, SOC, PEMFC, térmica ou horizonte móvel.

### 2. Arquitetura encontrada em `main` (`34a8b52`, merge do PR #8)

- Verificado com `git fetch`: `HEAD = origin/main = 34a8b5279eb6b1123e2d4dd67df3615218f741f2`. Linha de base:
  `python -m pytest tests/ -q` → **355 passed** (223 s; 7 avisos).
- Um cenário vive no banco da microrrede (esquema v4): `scenarios` (estado atual), `scenario_versions` (append-only,
  documento JSON canônico + `fingerprint`, `base_revision`/`base_fingerprint`), `revisions` (inventário, append-only),
  `blobs` (previsões: série normalizada `data` e original `blob`; CSV/ModelLab do inventário), `scenario_runs`
  (manifesto/outcome/summary/error, imutável depois de finalizada) e `scenario_run_data` (séries, SHA-256 do conteúdo
  descomprimido). Dependências de uma rodada: versão do cenário (FK), revisão do inventário, previsões da versão.
- **Backup do Gestor** (`.seeds2backup.zip`, formato 2): somente configuração + revisões + blobs do inventário; nenhum
  cenário/rodada. **Produto distinto** do arquivo científico; nenhum dos dois formatos é aceito pelo importador do outro
  (testado: o backup é recusado pela inspeção científica com explicação).
- Divergência documentação × código registrada: nenhuma relevante; `contracts.py` dizia que o 2D não estava
  implementado (atualizado).

### 3. Decisões de design

| # | Tema | Alternativas | Escolha e justificativa |
|---|---|---|---|
| D1 | Onde guardar estudos importados | tabelas novas no banco da microrrede ativa (v5) × banco da instalação | **Banco próprio da instalação** (`scientific_archive/archive.db`): o estudo abre numa instalação SEM a microrrede de origem e sem exigir criar/comissionar uma microrrede; importar não toca nenhum banco de microrrede nem o catálogo (isolamento por construção); excluir uma microrrede não apaga registros históricos; os bloqueios L1/L2 (H-01/H-02/H-03) não são tocados. Esquema da microrrede **inalterado (v4)**: nenhuma migração de `scenario_runs`/`scenario_versions`. |
| D2 | Estrutura do ZIP | exemplo da missão × variante | Mantida a estrutura sugerida com três ajustes: (a) documento de cada versão/revisão em arquivo próprio (`*.document.json`) com o **texto exato** da origem — os metadados ficam ao lado; reserializar mudaria bytes e arriscaria a impressão digital; (b) blobs endereçados por SHA-256 em `inventory/blobs/` e `forecasts/blobs/` (o nome É o hash: verificável sem índice); (c) `runs/<uid>/data/<nome>` reproduz os nomes de `scenario_run_data`. |
| D3 | Precisão numérica | reexportar CSV/JSON × bytes originais | **Bytes originais** (CSV das séries, documentos e manifestos): nenhuma conversão ⇒ nenhuma perda; teste compara `DataFrame` com `check_exact=True` e SHA-256 iguais. |
| D4 | Validação na importação | validar documentos com as regras ATUAIS de edição × estrutura mínima | **Estrutura mínima + impressões digitais** (compatibilidade de LEITURA): validar com regras de edição atuais acoplaria a leitura de estudos antigos a mudanças futuras do domínio. |
| D5 | Duplicatas | sempre nova cópia × reconhecer | `content_id` = SHA-256 do (formato, origem, recursos→SHA-256): independe da data de exportação; padrão **reconhecer** (nada inserido); opção explícita "outra cópia" (`copy_of`). Mesmo cenário de origem com conteúdo diferente = estudos distintos, ambos preservados. |
| D6 | Atomicidade | gravar em etapas com estado `importando` × uma transação | **Uma transação** `BEGIN IMMEDIATE` (estudo + recursos); 2ª leitura do ZIP reconfere SHA-256/tamanho de cada recurso (o arquivo pode mudar após a inspeção); `expected_content_id` liga a importação ao que o usuário confirmou. |
| D7 | Rodadas em execução | exportar como estão × omitir × recusar | **Recusar** a exportação (mensagem) — um arquivo só contém rodadas finalizadas com o estado original. |
| D8 | Memória | montar o ZIP em memória × arquivo temporário | Exportação escrita recurso a recurso num arquivo temporário (fora do `SEEDS2_DATA_DIR`), entregue por `download_button(data=callable)`; a sessão guarda só metadados (caminho, SHA-256, tamanho). A inspeção guarda só o relatório (não o conteúdo). |
| D9 | Arquivar sem navegador | — | `ARQUIVAR NESTA INSTALAÇÃO` = exportar + importar pelo mesmo caminho verificado (`acquisition = arquivado`). |
| D10 | `APP_VERSION` | — | `2.0.0-piso2da`. |

### 4. Contrato e versão do ZIP científico

- `manifest.format = "seeds2-study"`, `format_version = 1`; extensão `.seeds2study.zip`.
- `manifest.study.origin`: `microgrid_uid`, `microgrid_name`, `microgrid_incarnation`, `scenario_uid`, `scenario_name`,
  `scenario_origin`, `scenario_created_at`, `scenario_updated_at`, `current_version`.
- `manifest.study`: `versions` (contínuas 1..N), `inventory_revisions`, `runs`, `counts` (incl. `runs_by_state`).
- `manifest.exporter`: `app`, `app_version`, `db_schema_version`, `software` (Python, numpy, pandas, scipy e SHA-256 do
  código científico — `runner.software_versions`).
- `manifest.resources[path] = {sha256, size, media_type, role, [original_name, original_media_type, stored_at]}`.
- `manifest.dependencies`: versão → documento/revisão/previsões; revisão → blobs; rodada → versão/revisão/arquivos.
- `manifest.integrity.note`: "o SHA-256 detecta corrupção acidental e inconsistências… **não é assinatura digital**".
- **Política de versões:** o leitor aceita `SUPPORTED_FORMAT_VERSIONS = (1,)`; versão mais nova → recusa com "atualize
  esta instalação"; versão desconhecida/inválida → recusa. Uma nova versão do formato será criada quando QUALQUER
  esquema embutido deixar de ser legível pelo leitor anterior; o leitor novo continuará lendo v1 (compatibilidade de
  leitura); compatibilidade de execução (reexecutar estudos antigos) **não** é prometida.

### 5. Estrutura exata de arquivos

```
manifest.json
scenario/scenario.json                         linha atual do cenário (sem documento)
scenario/versions/v000001.json                 metadados da versão (scenario_uid, version, base_revision, fingerprint, saved_at, note, origin)
scenario/versions/v000001.document.json        texto exato do documento da versão
inventory/revisions/r000001.json               metadados da revisão (revision, installation_uid, fingerprint, saved_at, note, origin)
inventory/revisions/r000001.document.json      texto exato do documento da revisão
inventory/blobs/<sha256>                       CSV/pacotes ModelLab referenciados pelas revisões incluídas
inventory/catalog_references.json              instantâneo somente leitura das referências de catálogo citadas
forecasts/blobs/<sha256>                       séries normalizadas e arquivos originais de TODAS as versões
runs/<run_uid>/run.json                        linha da rodada (identidade, estado, datas, progresso, índice de dados, has_*)
runs/<run_uid>/manifest.json                   texto exato do manifesto de procedência
runs/<run_uid>/outcome.json|summary.json|error.json   texto exato (quando existem)
runs/<run_uid>/data/entradas/missao.csv, saidas/despacho_ems.csv, saidas/relatorio_ems.json, modelos/*.csv, pacote_troca.zip
```

Nomes permitidos por expressões regulares fechadas (`format._PATTERNS`); tipos por papel (JSON/CSV/ZIP/TXT; blobs numa
lista permitida). Entradas com data fixa (1980-01-01) e modo de arquivo regular.

### 6. Dependências e hashes

Inspeção (`format.inspect`) — uma única dependência obrigatória ausente ou corrompida reprova o estudo:
SHA-256 e tamanho reais (lidos em blocos, sem confiar no cabeçalho) = declarados, para TODOS os recursos; nome do blob =
SHA-256; `config.fingerprint(documento) = fingerprint` declarado (versões e revisões — detecta alteração mesmo com o
manifesto recalculado); versões contínuas e a atual = última; documento ↔ cenário/microrrede de origem; referência ao
inventário coerente e revisão incluída com a mesma impressão digital; blobs de previsão e do inventário presentes;
rodadas: estado final, versão/revisão existentes com as mesmas impressões digitais, manifesto ↔ rodada, `has_*` ↔
arquivos, concluída ⇒ resumo + resultado + dados, não concluída ⇒ sem dados, índice de dados = recursos; nenhum
recurso órfão; contagens = conteúdo.

### 7. Exportação

`exporter.write_package(store, scenario_uid, fh)` dentro de `store.snapshot()`: cenário + TODAS as versões (texto
exato) → revisões citadas por versões e rodadas (texto exato) + blobs do inventário + referências de catálogo →
previsões de todas as versões → todas as rodadas (dados descomprimidos e conferidos pelo SHA-256 de origem; nomes
validados) → manifesto. `export_to_file` publica atomicamente (`.part` + `fsync` + `rename`). Testado: cenário sem
rodadas; 4 versões; 3 rodadas (concluída real, falha, interrompida); exportar não altera nenhuma linha das tabelas de
cenários/rodadas/revisões/blobs; rodada em execução impede.

### 8. Importação e modelo de identidade

- Identidade de ORIGEM (microrrede, incarnação, cenário, rodadas, versões, impressões digitais, manifestos) preservada
  byte a byte; identidade LOCAL = `archive_uid` (novo, 32 hex) + `imported_at` + `acquisition` + contexto opcional
  (microrrede local em cujo Centro o estudo foi importado — apenas registro).
- Resultados atribuídos à origem: a interface declara "consulta histórica da microrrede «X»", as rodadas mostram a
  microrrede de origem, nada é gravado em `scenario_runs` de nenhuma microrrede.
- Fluxo em instalação nova: Gestor → **ARQUIVO CIENTÍFICO** → selecionar ZIP → relatório (cenário, microrrede de origem,
  versões, rodadas por estado, revisões, datas do experimento, data de exportação, versão do SEEDS2 que exportou,
  formato, tamanhos, SHA-256 do pacote, identidade do conteúdo) → confirmar → estudo na lista → ABRIR ESTUDO. Nenhuma
  microrrede precisa existir.
- Colisões: mesmo `content_id` → reconhecido (ou "outra cópia" explícita, `copy_of`); mesma origem com conteúdo
  diferente → estudos distintos, nenhum sobrescrito, ambos identificados pela data de exportação e ID local.

### 9. Persistência e migrações

- Novo banco `scientific_archive/archive.db` (esquema v1: `studies`, `study_resources`, `archive_blobs`, `meta`;
  triggers de imutabilidade). Migração versionada com cópia `archive.db.bak-v<N>` antes de migrar um banco existente;
  banco mais novo recusado sem alteração (testado).
- Bancos de microrrede: **sem migração** (v4); só uma API de leitura (`MicrogridStore.snapshot` → `StoreSnapshot`).
- Limites: pacote ≤ 512 MiB; conteúdo descomprimido ≤ 1 GiB; recurso ≤ 256 MiB; JSON ≤ 32 MiB e ≤ 100 níveis;
  ≤ 20 000 entradas; razão de compressão > 1000:1 em entradas > 1 MiB recusada. O Streamlit limita o upload a 200 MB
  por padrão (`server.maxUploadSize`) e mantém o arquivo enviado em memória do servidor durante a sessão; a importação
  lê o ZIP em blocos, mas a transação única mantém o estudo inteiro no WAL até o COMMIT.

### 10. Integridade e segurança

Defesas (todas testadas em `SegurancaTest`): Zip Slip / `..` / caminhos absolutos / `C:\` / diretórios / nomes ocultos
(lista fechada de padrões); links simbólicos e entradas não regulares (`external_attr`); entradas duplicadas e que
diferem só em maiúsculas; criptografia e métodos de compressão desconhecidos; bomba ZIP (razão + leitura limitada
pelo tamanho REAL, orçamento total); tamanho do pacote/recurso/total/entradas; JSON inválido, aninhado demais
(inclusive `RecursionError`) ou com chave duplicada; conteúdo executável (ELF, PE, Mach-O, `#!`); versão/formato
desconhecidos; backup do Gestor oferecido por engano. Nada é extraído em disco; nenhum `pickle`/`eval`/`exec`; o
`pacote_troca.zip` interno é guardado como dado e nunca aberto. Diagnóstico sempre em texto (nunca traceback).

### 11. Interface e recuperação histórica

- Centro de Operação: cartão "Arquivo Científico" (sem alterar as etapas 01–04) → aba `arquivo`: exportar cenário
  desta microrrede (versões/rodadas incluídas, aviso de rodada em execução, PREPARAR → ⬇ EXPORTAR CENÁRIO COMPLETO,
  ARQUIVAR NESTA INSTALAÇÃO), importar, lista de estudos (aquisição, verificação, origem, versões/rodadas, data do
  experimento, versão do SEEDS2, ID local; "Origem: esta microrrede").
- Estudo (`tab = estudo`, `?study=`, `?srun=` sobrevivem à recarga): Procedência · Configuração · Previsões ·
  Rodadas e resultados · Integridade (verificação sob demanda, tabela de recursos com SHA-256, dependências).
- Reutilização: `forecast_charts.figure` (previsões) e `execution_ui.run_results` (KPIs, potência, SOC, H₂, entradas,
  contrato do motor, procedência) — extraído de `render_run` sem mudar o comportamento do 2C (testes 2C inalterados).

### 12. Pruebas e resultados

Ambiente: Linux, Python 3.13.18, Streamlit 1.66.1, numpy 2.2.6, scipy 1.15.3, pandas 2.2.3; `PYTHONDONTWRITEBYTECODE=1`.

| Momento | Comando | Resultado |
|---|---|---|
| Linha de base (`main` `34a8b52`) | `python -m pytest tests/ -q` | **355 passed** (223 s; 7 avisos) |
| Versão final da rama | `python -m pytest tests/ -q` | **398 passed, 0 failed, 0 skipped** (259 s; 128 subtests; os mesmos 7 avisos da linha de base) — 355 anteriores + 43 novos (35 domínio + 8 interface) |

Novos: `tests/test_seeds2_piso2da.py` (35) e `tests/test_seeds2_piso2da_app.py` (8). Ajustes em testes existentes
(estado real, nenhuma asserção enfraquecida): `test_seeds2_gestor_app.test_inicio_sem_microrredes` (lista EXATA de
botões agora inclui ARQUIVO CIENTÍFICO); `apptest_utils.continuar` transporta as chaves de aplicação `ar_*`.

| Requisito da missão (§13) | Teste |
|---|---|
| 1 sem rodadas | `ExportacaoTest.test_cenario_sem_rodadas` |
| 2–4 várias versões/rodadas; concluídas, falhas, interrompidas | `test_varias_versoes_e_varias_rodadas_com_estados_originais` |
| 5 manifestos originais | `test_manifestos_e_documentos_com_texto_exato_da_origem`; `ImportacaoTest.test_identidade_de_origem_e_identidade_local_distintas` |
| 6 inventário de referência | `test_inventario_de_referencia_preservado` |
| 7 previsões originais e normalizadas | `test_previsoes_normalizadas_e_originais_preservadas` (CSV importado com nome original) |
| 8 séries completas | `test_series_completas_do_ems_preservadas` |
| 9 SHA-256 de todos os recursos | `IntegridadeTest.test_todos_os_recursos_tem_sha256_e_tamanho_conferidos` |
| 10 recurso corrompido | `test_recurso_corrompido_detectado`; `test_corrupcao_coerente_com_manifesto_recalculado_ainda_detectada`; `test_corrupcao_no_arquivo_local_detectada_na_leitura` |
| 11 obrigatório faltante | `test_arquivo_obrigatorio_faltante_detectado`; `test_relacoes_inconsistentes_detectadas` |
| 12 ZIP malicioso | `SegurancaTest` (Zip Slip, absolutos, links, duplicatas, executável, JSON) |
| 13 ZIP grande demais | `test_bomba_zip_e_limites` |
| 14 formato/versão incompatível | `test_formatos_e_versoes_incompativeis`; `test_banco_do_arquivo_mais_novo_e_recusado_sem_alteracao` |
| 15 instalação vazia | `test_instalacao_limpa_reabre_em_novo_processo_sem_executar_o_ems`; UI `test_instalacao_vazia_importa_verifica_e_abre_sem_executar` |
| 16 revisitar sem EMS | `ProvaCientificaTest` (otimizador e modelos sabotados); subprocesso com motor sabotado; UI inteira com o motor sabotado |
| 17 previsões e gráficos após importar | UI `test_secoes_do_estudo_configuracao_previsoes_rodadas_integridade`; E2E |
| 18 metadados e procedência | `test_identidade_de_origem_e_identidade_local_distintas` |
| 19 identificadores de origem coincidentes | `test_dois_estudos_com_identificadores_de_origem_coincidentes` |
| 20 reimportar | `test_reimportar_o_mesmo_arquivo`; UI `test_duplicata_reconhecida_e_copia_identificavel` |
| 21 erro/interrupção → rollback | `AtomicidadeTest` (erro SQLite no 7º recurso; arquivo alterado; `os._exit` no 12º recurso em subprocesso) |
| 22 isolamento entre microrredes | `IsolamentoTest` (banco e catálogo byte a byte); UI `test_cartao_no_painel_e_importacao_no_contexto_nao_altera_a_microrrede` |
| 23–24 cenários intactos; rodadas imutáveis | `test_exportacao_nao_altera_cenarios_nem_rodadas_e_rodadas_continuam_imutaveis`; `test_estudo_arquivado_e_somente_leitura` |
| 25 EMS V1.6 inalterado | `ProvaCientificaTest.test_ems_v16_inalterado` + `test_console_v16_inalterado` (2C, R$ 417,684638) |
| 26 pisos anteriores | suíte completa + E2E de regressão |
| **Prova científica** | `ProvaCientificaTest.test_rodada_real_exportada_importada_e_reaberta_sem_recomputacao`: rodada REAL do 2C → exportada → importada noutra instalação → reaberta (nova instância) com `run_optimizer`/`build_exchange_package` substituídos por exceções; custo (R$ 88,3190884544543 = rodada 2C de referência), energias, SOC, H₂, custos por fonte, potências por fonte, timestamps UTC (`check_exact`), identificadores e SHA-256 de todos os dados **idênticos** |

### 13. E2E real e evidência

Chromium real (Playwright), servidores Streamlit reais, diretórios vazios, reinício real do servidor entre fases.

| Roteiro | Fases | Resultado |
|---|---|---|
| `tools/e2e/e2e_piso2da_arquivo.js` (novo; origem `tools/e2e/seed_piso2da.py`: rodada REAL concluída + rodada falha) | exportar 13 (ORIGEM) · importar 34 (DESTINO **vazio**, motor sabotado) · `kill -9` do servidor · reinício 8 · tablet 7 | **62/62** |
| `tools/e2e/e2e_piso2c_execucao.js` | operar 38 · **`kill -9` durante a rodada longa** · reinício 10 · tablet 7 | **55/55** |
| `tools/e2e/e2e_piso2b_previsoes.js` | operar 43 · reinício 8 · tablet 7 | **58/58** |
| `tools/e2e/e2e_piso2a_centro_operacao.js` | operar 43 · reinício 5 · tablet 5 | **53/53** |
| `tools/e2e/e2e_gestor_microrredes.js` (`SEEDS2_DEV_MODE=1`; `legado` com `seeds2.db` anterior ao Gestor) | multi 39 · reinício 6 · tablet 2 · legado 5 | **52/52** |
| `tools/e2e/e2e_piso1_microrrede.js` (rodada EMS real do console V1.6) | comissionar 41 · reabrir 21 · tablet 4 | **66/66** |

**Servidor de destino com o motor sabotado:** o servidor da instalação limpa foi iniciado com um `sitecustomize` que
substitui `orchestrator_runtime.run_optimizer` e `build_exchange_package` por funções que registram a chamada num
arquivo e falham. Ao fim de importar → consultar (configuração, previsões, rodadas, integridade, recarga) → `kill -9` →
reinício → reabrir → tablet → tema escuro: **nenhuma chamada registrada**. O diretório de destino terminou com
`registry.db`, `microgrids/` VAZIO e `scientific_archive/` — nenhuma microrrede criada ou restaurada.

Verificado no navegador: download real do `.seeds2study.zip` (nome ASCII com 8 dígitos do UID do cenário; começa por
`PK`); relatório de verificação com cenário, microrrede de origem, versões (3), rodadas (1 concluída, 1 falhou),
versão do SEEDS2 exportador, tamanho e a ressalva de que o SHA-256 não é assinatura; CONFIRMAR desabilitado sem
confirmação; estudo "Importado / Verificado na importação / Somente leitura"; Configuração (inventário de referência,
estados iniciais, estratégia GWO, janela); Previsões (demanda e clima desenhados com os dados do estudo); rodada falha
com o motivo original e sem curvas; rodada concluída com o **mesmo custo da origem** e 31 passos; integridade
reconferida; recarga e link direto após reinício reabrem o mesmo estudo e a mesma rodada; reimportação reconhecida
como duplicata; tablet retrato/paisagem sem rolagem horizontal e gráfico dentro da tela; tema escuro.
Primeira execução: 2 falhas do PRÓPRIO roteiro (procurava gráficos abaixo da dobra antes de o Streamlit desenhá-los)
e a ordem clima→demanda corrigida na interface (§15); o protocolo inteiro foi repetido do zero.

### 14. Regressões e compatibilidade

- `git diff origin/main --stat -- models h2_pemfc simulation config ems_integration reference_models
  orchestrator_runtime.py orchestrator_app.py` → **vazio**.
- Banco da microrrede inalterado (v4); backup ZIP formato 2 inalterado (apenas o texto de alcance mudou);
  `execution_ui.render_run` delega a `run_results` (mesma saída; testes 2C sem alteração).
- Estudos v1 serão legíveis pelas próximas versões (política §4).

### 15. Problemas detectados e corrigidos durante a missão

1. Previsões apareciam clima → demanda (ordem canônica das chaves JSON): ordenadas demanda → clima, como no 2B.
2. Recarga com `?srun=` voltava à seção Procedência: a seção inicial passa a ser "Rodadas e resultados".
3. Primeiro E2E: o roteiro procurava gráficos abaixo da dobra; o Streamlit só desenha o Plotly ao entrar na área
   visível — o roteiro passou a rolar até cada gráfico; o protocolo inteiro foi repetido do zero.
4. Teste auxiliar `_resign` usava tipo JSON para CSV (a inspeção recusava por tipo antes da relação testada);
   corrigido no teste para que cada caso exercite a regra pretendida.

### 16. Riscos residuais

1. SHA-256 interno ≠ assinatura: um pacote forjado de forma coerente (documentos com impressões digitais recalculadas)
   é aceito como consistente; autenticidade exigiria assinatura (fora do escopo).
2. Estudos arquivados não podem ser excluídos pela interface (imutáveis); limpeza exige intervenção manual no banco.
3. Upload limitado pelo Streamlit (200 MB padrão) e mantido em memória do servidor; pacotes grandes exigem ajuste de
   `server.maxUploadSize`. A transação única da importação cresce o WAL até o COMMIT.
4. `owner` das rodadas (host|pid|token) e caminhos não aparecem no pacote, mas o nome do host de origem sim (parte da
   linha imutável da rodada).
5. A exportação usa a pasta temporária do sistema; arquivos preparados com mais de 1 h são removidos na próxima
   preparação.
6. "CRIAR VARIANTE OPERATIVA" apenas documentada (contrato em `seeds2/archive/service.py`).

### 17. Arquivos modificados

| Arquivo | Propósito |
|---|---|
| `seeds2/archive/__init__.py`, `format.py`, `exporter.py`, `store.py`, `view.py`, `service.py` (novos) | contrato, inspeção, exportação, Arquivo Científico, consulta, arquivar |
| `seeds2/ui/archive_ui.py` (novo) | interface do Arquivo Científico |
| `seeds2/microgrid/store.py` | `snapshot()` + `StoreSnapshot` (somente leitura) |
| `seeds2/ui/execution_ui.py` | `run_results` extraído de `render_run` (reutilizado pelo estudo) |
| `seeds2/ui/operation_center.py`, `main.py`, `shell.py`, `session.py`, `gestor.py` | rotas `arquivo`/`estudo`, cartão, `?study=`/`?srun=`, `session.archive()`, botão no Gestor, textos de alcance e de exclusão |
| `seeds2/__init__.py`, `seeds2/operation/contracts.py` | `APP_VERSION = 2.0.0-piso2da`; contrato 2D-A |
| `tests/test_seeds2_piso2da.py`, `tests/test_seeds2_piso2da_app.py` (novos); `tests/apptest_utils.py`, `tests/test_seeds2_gestor_app.py` | testes |
| `tools/e2e/e2e_piso2da_arquivo.js`, `tools/e2e/seed_piso2da.py` (novos) | E2E |
| `PARAMIJEFE.md`, `CLAUDE.md`, `docs/ai/HANDOFF.md`, `docs/seeds2/ARMAZENAMENTO.md` | documentação |

### 18. Instruções de auditoria independente

1. `seeds2/archive/format.py` — `_structure` (estrutura antes de descomprimir), `stream_entry` (leitura limitada),
   `_manifest_errors`, `_relations` (regras do §6), `iter_resources` (2ª leitura reconferida).
2. `seeds2/archive/store.py` — `import_package` (inspeção sempre refeita, transação única, `expected_content_id`,
   duplicatas) e os triggers do esquema v1.
3. `seeds2/archive/exporter.py` — leitura num único `snapshot`; texto exato; recusa de rodada em execução.
4. `seeds2/ui/archive_ui.py` — nenhuma importação de `orchestrator_runtime`/EMS; `run_results(view, …)`.
5. Reproduzir: `python tools/e2e/seed_piso2da.py <origem>` → servidor na origem → Centro → Arquivo Científico →
   PREPARAR → baixar; servidor NOVO com `SEEDS2_DATA_DIR` vazio → Gestor → ARQUIVO CIENTÍFICO → enviar → confirmar →
   ABRIR ESTUDO → Rodadas → custo igual ao da origem; reiniciar o servidor e reabrir pelo link.

### 19. Preparação para o Piso 2D-B

`StudyView` é a fonte única para relatórios: documentos de versão, revisões (migradas para exibição), previsões
(`F.load(entry, view.get_blob)`), rodadas (`StoredRun`) e séries (`view.run_csv`). PDF/Excel/figuras poderão ser
gerados igualmente para rodadas locais (`MicrogridStore`) e arquivadas (`StudyView`), pois ambas oferecem
`run_data`/`get_run`. Os relatórios deverão identificar a procedência (origem × local) como a interface faz.

### 20. Correção de auditoria C-03 — consistência de procedência do Arquivo Científico

A auditoria independente do PR #9 foi **favorável** (formato v1, exportação por instantâneo, importação atômica,
separação de identidades, estudos imutáveis, recuperação sem recalcular, testes e E2E aprovados) e pediu uma correção
focalizada do verificador de pacotes não confiáveis. Escopo: somente `seeds2/archive/format.py` (`_relations`) e testes;
formato ZIP v1, exportador, importação, `archive.db`, bancos das microrredes (v4), EMS e modelos **inalterados**.

**Causa.** `_relations()` conferia SHA-256/tamanho, impressões digitais e várias referências, mas (a) da rodada só
contrastava `run_uid`, `scenario_uid`, versão e impressão digital do cenário — não a microrrede, a incarnação, nem a
revisão/impressão do inventário do manifesto de procedência (`reference`) contra o registro (`run.json`), nem a revisão
do registro contra a revisão referenciada pela versão executada; (b) o índice `manifest.dependencies` não era
verificado. Um pacote com recursos íntegros e manifesto recalculado podia, portanto, atribuir uma rodada a outra
microrrede, declarar outra incarnação/revisão no manifesto da rodada ou trazer um grafo de dependências falso — e ser
aceito. Reproduzido: os 7 testes negativos abaixo **falham** com o `format.py` anterior (pacotes aceitos) e passam com a
correção.

**Solução** (`format._relations`; `_clash(a, b)` = dois valores DECLARADOS e diferentes):
- **Versões:** `microgrid_uid` dos metadados = origem; incarnação do documento × origem (só quando ambas declaradas).
- **Rodadas:** `run.json.microgrid_uid` = origem; incarnação do registro × origem (ambas declaradas); revisão e
  impressão do inventário do registro = as da versão executada; `manifest.json.reference`: `microgrid_uid` = registro,
  incarnação × registro e × origem (declaradas), e `scenario_uid`, `scenario_version`, `scenario_fingerprint`,
  `config_revision`, `config_fingerprint` IGUAIS ao registro (que já era conferido contra versão e revisão incluídas).
- **Dependências:** o grafo é RECONSTRUÍDO dos recursos verificados com as mesmas funções de referência usadas pelo
  exportador (`MicrogridStore._scenario_blobs`, `_referenced_blobs`, caminhos `version_path`/`revision_path`, arquivos
  da rodada) e deve ser **exatamente igual** a `manifest.dependencies` (seções `versions`, `inventory_revisions`,
  `runs`; chave ausente, adicional, inexistente ou alterada → rejeição). A comparação só ocorre quando o restante do
  pacote é consistente (diagnóstico sem cascata).
- `None` continua significando "não registrado" (dados legítimos anteriores ou armazenamento sem incarnação): não é
  conflito. Os pacotes autênticos exportados pelo 2D-A continuam aceitos (todos os testes anteriores inalterados).
- O SHA-256 continua sem constituir assinatura: as novas verificações garantem consistência interna, não autoria.

**Evidência** (`tests/test_seeds2_piso2da.py::RelacoesC03Test`, pacotes com recursos íntegros e hashes recalculados):

| Caso | Teste | Resultado |
|---|---|---|
| Pacote autêntico (e reempacotado) aceito; grafo reconstruído = declarado | `test_pacote_autentico_continua_aceito_e_dependencias_reconstruidas` | aceito |
| 1 rodada com `microgrid_uid` de outra microrrede | `test_1_rodada_atribuida_a_outra_microrrede` | rejeitado |
| 2 incarnação contraditória (registro; manifesto da rodada) | `test_2_incarnacao_contraditoria_quando_ambas_declaradas` | rejeitado |
| Incarnação `None` (registros/manifestos herdados; origem sem incarnação) | `test_incarnacao_nao_registrada_em_dados_herdados_nao_e_conflito` | aceito |
| 3 `config_revision`/`config_fingerprint` do manifesto ≠ registro; registro ≠ versão executada | `test_3_revisao_ou_impressao_do_manifesto_da_rodada_diferente_do_registro` | rejeitado |
| 4 referência de cenário contraditória (microrrede, cenário, versão) | `test_4_referencia_de_cenario_contraditoria` | rejeitado |
| 5 dependência de versão apontando para OUTRA revisão real (estudo com revisões 1 e 2, versão rebaseada) | `test_5_dependencia_de_versao_aponta_para_outra_revisao` | rejeitado |
| 6 dependência apontando para blob diferente (previsão; inventário) | `test_6_dependencia_aponta_para_blob_diferente` | rejeitado |
| 7 dependência de rodada omitindo/acrescentando arquivo; versão errada; rodada inexistente; versão ausente; índice ausente | `test_7_dependencia_de_rodada_omite_ou_acrescenta_arquivo` | rejeitado |

Execuções: `python -m pytest tests/ -q` → **407 passed, 0 failed** (264 s; 128 subtests; os mesmos 7 avisos) — 398
anteriores + 9 novos; nenhum teste existente alterado. Reprodução da insuficiência: os 9 testes executados contra o
`format.py` anterior (HEAD `89026b1`) → **7 failed** (todos os casos negativos aceitos) / 2 passed (casos positivos).
E2E `tools/e2e/e2e_piso2da_arquivo.js` repetido desde diretórios vazios (exportação legítima na origem → importação
numa instalação LIMPA com o motor sabotado → `kill -9` → reinício → tablet/escuro): **62/62**, motor nunca chamado no
destino. `git diff origin/main --stat -- models h2_pemfc simulation config ems_integration reference_models
orchestrator_runtime.py orchestrator_app.py` **vazio**.

---

## Entrega 5 — SEEDS2 Piso 2D-B · Relatórios Científicos e Exportações

### Ponto de continuidade (atualizar ao encerrar ou interromper a sessão)

| Campo | Valor |
|---|---|
| Rama | `claude/seeds2-piso2db-relatorios-9k1qph` (designada pelo ambiente desta sessão; a missão sugeria `claude/seeds2-piso2db-relatorios`) |
| Base | `main` `3b73971` (merge do PR #9, Piso 2D-A + C-03) |
| PR | [#10](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/10) contra `main` (sem merge; aguarda auditoria) |
| Último commit | `git log -1 origin/claude/seeds2-piso2db-relatorios-9k1qph` (o SHA final é informado no PR) |
| Hitos concluídos | A (contrato de leitura unificado), B (Excel), C (figuras + PDF), D (interface + E2E); correção de auditoria C-04 (§21) |
| Pendências | nenhuma desta missão; integração aguarda auditoria e autorização humana |
| Testes | após C-04: `python -m pytest tests/ -q` **454 passed, 0 failed (353 s; 128 subtests; os mesmos 7 avisos) — 443 anteriores + 11 novos**; E2E 2D-B **57/57 (+157/157 nos arquivos baixados)** (antes de C-04: 443 passed; 55/55 + 145/145); regressão E2E Piso 1 e Gestor concluídos, 2A 53/53, 2B 58/58, 2C 55/55, 2D-A 62/62 |
| Próxima ação | auditoria independente do PR; depois, piso do otimizador (§20) |

### 1. Resumo executivo

**Solicitado:** transformar os dados científicos persistidos (rodadas locais do Piso 2C e rodadas de estudos
arquivados/importados do Piso 2D-A) em entregáveis: relatório técnico PDF, planilha científica `.xlsx`, figuras PNG/SVG
e ZIP de figuras com manifesto — **sem nova simulação**, sem alterar nada do que foi persistido.

**Entregue:**
- **Contrato de leitura unificado** `seeds2/report/dossier.py` (`RunDossier`, `load_local`, `load_archived`, `load`):
  a mesma estrutura para `MicrogridStore` e `StudyView`; integridade conferida na leitura (impressões digitais
  recalculadas, identidade do manifesto, SHA-256 e tamanho de TODOS os dados da rodada e das previsões); indicadores
  como fonte única (`indicators`) lidos do resumo persistido.
- **Excel** `seeds2/report/xlsx.py`: 12+ folhas (índice, identificação, indicadores, equipamentos, condições iniciais,
  estratégia, entradas, despacho, previsões, uma folha por modelo, procedência, dicionário), doubles SERIALIZADOS
  exatos no arquivo (leitura bit a bit por Python; o Microsoft Excel garante 15 algarismos — ver §9 e §21), datas reais com referência temporal declarada, texto nunca fórmula, limites do formato tratados explicitamente.
- **Figuras** `seeds2/report/figures.py`: as MESMAS figuras Plotly da interface (`run_charts`, `forecast_charts`)
  desenhadas estaticamente (matplotlib) em PNG 300 dpi, SVG vetorial e PDF vetorial; ZIP `seeds2-figures` v1 com
  `manifest.json` (SHA-256 por arquivo, unidade, descrição, dados de origem com SHA-256) e `LEIA-ME.txt`.
- **PDF** `seeds2/report/run_pdf.py`: relatório técnico autônomo de 10 seções (+ capa), figuras vetoriais embutidas,
  DejaVu Sans embarcada; rodada falha/interrompida → **relatório diagnóstico** sem resultados.
- **Interface** `seeds2/ui/report_exports.py`: painel "Exportações científicas" (EXPORTAR RELATÓRIO PDF / DADOS
  EXCEL / FIGURAS) dentro de `execution_ui.run_results` — logo, presente na rodada local E na rodada do estudo
  arquivado; geração sob demanda com progresso por etapas reais (`st.status`), download, figura individual.
- **Nada** em `models/`, `h2_pemfc/`, `simulation/`, `config/`, `ems_integration/`, `reference_models/`,
  `orchestrator_runtime.py`, `orchestrator_app.py` foi alterado; nenhum banco mudou de esquema.

### 2. Arquitetura encontrada (`main` `3b73971`)

- Rodadas 2C (`scenario_runs` + `scenario_run_data`): manifesto imutável, `summary`, `outcome`, `error`; dados
  `entradas/missao.csv`, `saidas/despacho_ems.csv`, `saidas/relatorio_ems.json`, `modelos/*.csv` (battery/fc
  characterization, climate, solar, wind quando houver), `pacote_troca.zip` — todos com SHA-256 no índice.
- `MicrogridStore.get_run/run_data/snapshot` (H-03) e `StudyView.get_run/run_data/version_document/revision_document/
  get_blob` com o MESMO contrato de dados; `execution_ui.run_results(source, run)` já era comum às duas origens.
- `runner.summarize` define os indicadores persistidos (custo = `rel.custo_total_rs` do EMS; energias integradas
  com `Ts`; H₂ = `rel.consumo_fisico.fc`); `despacho.relatorio` define energia/participação por fonte
  (`energia_por_fonte_kWh = Σ max(P,0)·Ts`, `pct_atendimento = 100·E/ΣE`) — gravados em `relatorio_ems.json`.
- O PDF existente (`seeds2/report/pdf.py`) documenta a CONFIGURAÇÃO da microrrede (Piso 1) e não foi alterado.

### 3. Contrato de leitura unificado (`RunDossier`)

| Campo | Rodada local | Estudo arquivado |
|---|---|---|
| `run` (`StoredRun`) | `MicrogridStore.get_run` | `StudyView.get_run` |
| `scenario` (documento EXATO da versão executada) | `snapshot.scenario_versions` (texto gravado) | `versions/vN/document.json` (texto da origem) |
| `inventory` (revisão referenciada pela rodada) | `snapshot.revision_row` | `inventory/revisions/rN/document.json` |
| `microgrid` | UID + nome na revisão + incarnação | idem (+ nome na exportação) |
| `archive` | — | `archive_uid`, `content_id`, SHA-256 do pacote, datas |
| dados (`raw/table/json_data`) | `store.run_data` (SHA-256) | `view.run_data` (SHA-256 contra o índice ORIGINAL) |
| previsões (`forecast_frame`) | `forecasts.load(entry, store.get_blob)` | `forecasts.load(entry, view.get_blob)` |

Conferências na leitura (falha → `DossierIntegrityError`; nenhum documento é gerado): rodada `em_execucao` recusada;
manifesto × colunas da rodada (UID, microrrede, incarnação quando ambas declaradas, cenário, versão, revisão,
impressões digitais); `config.fingerprint` recalculado sobre o texto da versão e da revisão = o registrado = o da
rodada; todos os dados relidos com SHA-256 e tamanho = índice original; séries de previsão com SHA-256 e forma
conferidos; limite de 512 MiB de dados por rodada (proteção de memória). Documentos são lidos num ÚNICO instantâneo e
liberados; os dados são lidos em transações curtas — nenhuma transação fica aberta durante a geração.
`dossier.py` não importa runtime/EMS; um teste em subprocesso prova que gerar os três documentos de um estudo arquivado
não carrega `orchestrator_runtime`, `ems_integration` nem `simulation`.

### 4. Bibliotecas escolhidas

| Biblioteca | Uso | Justificativa / compatibilidade |
|---|---|---|
| reportlab 4.4.10 (já presente) | composição do PDF | sem serviços externos; já usado pelo PDF de configuração |
| pypdf 6.21.4 (já presente) | sobreposição das figuras vetoriais nas páginas | `merge_transformed_page`; puro Python |
| **matplotlib 3.10.7** (nova) | desenho estático das figuras Plotly (PNG/SVG/PDF) | rodas manylinux para Python 3.13, sem navegador; traz a fonte DejaVu Sans usada também pelo PDF |
| **openpyxl 3.1.5** (nova) | `.xlsx` em modo *write-only* | maduro; permite gravar o texto decimal exato do double (ver §9) |

**Kaleido descartado:** a v1.x exige Chrome no servidor de implantação (Streamlit Community Cloud não tem) e a v0.2.1
está obsoleta para o Plotly ≥ 6.1. O matplotlib desenha o MESMO objeto Plotly (traços, cores, tracejados, quebras em
ausentes, linhas de referência, faixas, títulos de painel e eixos) — não há um segundo conjunto de curvas.

### 5. Estrutura do relatório PDF

Capa (título "SEEDS2 — Relatório de Simulação de Microrrede", microrrede de origem, cenário, versão + impressão
digital, rodada, estado, execução, software da rodada, origem dos dados, data de geração; aviso de estudo arquivado) →
**01 Resumo executivo** (8 cartões + tabela de TODOS os indicadores com o campo persistido de origem) → **02
Configuração** (equipamentos da revisão: características registradas, disponibilidade, situação na rodada; tecnologias
ausentes declaradas; configuração efetiva do motor) → **03 Condições iniciais** (disponibilidade, estado, SOC,
potência, unidades — "não aplicável" por tipo; regras do motor e verificação da fase B) → **04 Previsões e dados de
entrada** (fonte, procedência — sintético/referência nunca "medido" —, período original, resolução, fuso, variáveis e
unidades; janela local/UTC; conversão para a grade registrada; figuras: entradas da missão, previsões originais) →
**05 Estratégia e metodologia** (função objetivo única e termos, algoritmo, N, semente, tolerâncias, econômicos,
parâmetros fixos do motor; fluxo cenário → preflight → dados → modelos → EMS → armazenamento; ressalva de otimalidade)
→ **06 Resultados energéticos** (energia/custo/participação/partidas por fonte despachável; renováveis instaladas ou
"não instalada"; figura demanda × fontes com disponível ≠ despachado) → **07 Armazenamento e hidrogênio** (SOC
inicial/limites/final em % com a fração; H₂ do EMS × validação dinâmica, declaradas não equivalentes; figuras) →
**08 Discussão (fatos)** → **09 Procedência** (todos os identificadores, software, código científico, SHA-256 de cada
dado e previsão; estudo arquivado: ID local, `content_id`, SHA-256 do pacote; "não é nova execução") → **10
Limitações** (do experimento: advertências do preflight, deriva, exclusões, avisos do motor; do software: regras de
estado inicial e parâmetros fixos registrados no manifesto). Cabeçalho/rodapé discretos, "Página X de Y".
Diagnóstico (falha/interrupção): capa marcada, 01 Diagnóstico (tipo, exceção, mensagem, último progresso, verificação
do motor, rastreamento), configuração, condições iniciais, metodologia, procedência, limitações — sem resultados.

### 6. Estrutura da planilha Excel

`00 Índice` (folhas, linhas, colunas, avisos da exportação) · `01 Identificação` · `02 Indicadores` (valor exato,
unidade, chave, fonte, definição) ou `02 Diagnóstico` · `03 Equipamentos` · `04 Condições iniciais` · `05 Estratégia
EMS` (inclui configuração efetiva do motor e janela) · `06 Entradas` (= `entradas/missao.csv`) · `07 Despacho EMS`
(= `saidas/despacho_ems.csv`) · `08 Previsão demanda|clima` (séries originais normalizadas) · `09 <modelo>` (uma por
`modelos/*.csv`) · `10 Procedência` (SHA-256 de todos os dados, previsões, manifesto e desfecho achatados) · `11
Dicionário de dados` (unidade, referência temporal, descrição, tipo e nº de ausentes de CADA coluna). Cabeçalho =
nome EXATO da coluna original (com comentário de unidade/referência), filtros, painéis congelados, larguras ajustadas.
Sem fórmulas. Folhas de dados ausentes numa rodada falha.

### 7. Figuras disponíveis e formatos

| Arquivo | Fonte (mesma função da interface) | Condição |
|---|---|---|
| `01_demanda_potencia_por_fonte` | `run_charts.power_figure` | rodada concluída |
| `02_estado_de_carga_bateria` | `run_charts.soc_figure` | há coluna `SOC_*` |
| `03_hidrogenio_acumulado` | `run_charts.h2_figure` | `h2_kg` > 0 em algum passo |
| `04_entradas_da_missao` | `run_charts.inputs_figure` | `entradas/missao.csv` |
| `05_previsao_demanda`, `06_previsao_clima` | `forecast_charts.figure` (série original, sem transformação) | previsão declarada |

PNG 300 dpi (largura 170 mm = 2007 px), SVG vetorial (texto em contornos, `svg.hashsalt` fixo → determinístico), PDF
vetorial (no relatório). ZIP: `figuras/png/*`, `figuras/svg/*`, `manifest.json` (`seeds2-figures` v1: experimento,
gerador, por arquivo SHA-256/tamanho/dimensões/unidade/descrição/dados de origem com SHA-256), `LEIA-ME.txt`. Figuras
de uma rodada local e da mesma rodada arquivada são **idênticas byte a byte** (verificado no E2E).

### 8. Cálculos derivados

Nenhum indicador é recalculado. Únicas transformações de apresentação, todas declaradas no documento:
SOC fração × 100 → % (o valor gravado em fração é mostrado ao lado); H₂ **acumulado** na figura = soma acumulada da
coluna `h2_kg` (kg por passo) — feita pela função já existente `run_charts.h2_figure`; o total oficial é o do resumo
(diferença de arredondamento de ponto flutuante: 3,4996721730425198 × 3,4996721730425207 kg na rodada de referência);
participação por fonte lida de `relatorio_ems.json` (`pct_atendimento`, definição do EMS). Valores |x| < 10⁻³ são
exibidos em notação científica (nunca arredondados para zero).

### 9. Garantias de precisão numérica (redação revista pela correção C-04.2, §21)

Três níveis, distinguidos no índice do Excel, na interface e aqui:

1. **Precisão serializada no arquivo `.xlsx`.** openpyxl e xlsxwriter gravariam `%.16g` (16 algarismos: NÃO reproduz
   todo double). O escritor grava cada número com `repr(float)` — a menor representação decimal que reproduz o double
   EXATO (≤ 17 algarismos) — no elemento numérico `<v>` (a célula continua numérica). Os CSVs são lidos com
   `float_precision="round_trip"`. Teste: cada célula numérica das folhas de entradas, despacho e modelos, **lida por
   Python (openpyxl/pandas)**, tem os mesmos bits (`float.hex`) que o texto do CSV persistido (> 5 000 células); casos
   extremos (0,1+0,2; 1/3; 5e-324; 1,797…e308; −0,0; 2⁵³).
2. **Precisão garantida pelo Microsoft Excel.** O Excel documenta precisão de **15 algarismos significativos**: ao
   abrir, editar ou salvar o arquivo no Excel, valores com mais algarismos podem ser exibidos ou regravados
   arredondados. **Não se afirma preservação bit a bit dentro do Excel.** Quando a planilha contém valores com mais de
   15 algarismos significativos, a exportação emite uma advertência explícita (índice + interface) com a contagem.
3. **Fontes originais para reprodução exata:** os CSVs da rodada e o pacote `.seeds2study.zip`.

NaN → célula vazia (contada); ±∞ → texto "inf"/"-inf"; inteiros > 2⁵³ → texto; o formato de exibição "Geral" não
altera o valor serializado. Datas: células de data/hora do Excel (resolução de segundo verificada na volta),
referência (UTC / relógio de parede do fuso / grade do runtime / relógio não declarado) no comentário do cabeçalho e
no dicionário — missão sem fuso nunca é rotulada UTC. Linhas > 1 048 575 → divisão EXPLÍCITA em partes numeradas
registradas no índice e nos avisos; > 12 M células → recusa com indicação do `.seeds2study.zip`; textos > 32 767
caracteres → encurtados e marcados; controles ilegais em XML → U+FFFD (contados).

### 10. Procedência e imutabilidade

Cada documento identifica rodada, versão + impressão digital do cenário, revisão + impressão digital do inventário,
microrrede + incarnação, software da rodada, código científico (SHA-256), SEEDS2 gerador e data/hora de geração; os
manifestos originais são apresentados, nunca reescritos. A distinção ".seeds2study.zip = fonte integral; PDF/Excel/
figuras = derivados" está na interface, na capa, no índice do Excel, no `LEIA-ME.txt` e no manifesto das figuras.
Testes provam: `_dump` lógico do banco da microrrede e do Arquivo Científico idênticos antes/depois de gerar os três
documentos de rodadas concluída/falha/interrompida nas duas origens; SHA-256 dos dados e manifesto da rodada intactos;
`ArchiveStore.verify` aprovado; nenhuma rodada criada.

### 11. Testes automatizados

`tests/test_seeds2_piso2db.py` (32) e `tests/test_seeds2_piso2db_app.py` (4). Mapa requisitos (missão §10) → testes:

| # | Requisito | Teste(s) |
|---|---|---|
| 1, 2 | PDF local / arquivado | `PdfTest.test_pdf_rodada_local_concluida`, `test_pdf_rodada_arquivada_identica_em_conteudo_cientifico` |
| 3 | indicadores iguais | `ContratoTest.test_indicadores_iguais_e_iguais_ao_resumo_persistido`, `ExcelTest.test_indicadores_excel_iguais_entre_origens` |
| 4, 5 | microrrede original; IDs e impressões | `ContratoTest.test_identidade_e_impressoes_digitais_iguais_nas_duas_origens`, PDF/Excel acima |
| 6 | eixos e unidades | `PdfTest.test_graficos_com_eixos_e_unidades_no_pdf`, `FigurasTest.test_catalogo_minimo_com_eixos_e_unidades` |
| 7 | rodada falha | `PdfTest.test_pdf_diagnostico_de_rodadas_nao_concluidas_sem_resultados`, `ExcelTest.test_diagnostico_excel_sem_series_de_resultado`, `FigurasTest.test_rodada_nao_concluida_sem_figuras`, `RodadaLocalTest.test_rodada_falha_so_diagnostico_sem_figuras` |
| 8–10 | colunas de entradas, despacho, modelos | `ExcelTest.test_folhas_e_todas_as_colunas_de_entradas_despacho_e_modelos` |
| 11 | precisão | `ExcelTest.test_precisao_numerica_bit_a_bit`, `test_escritor_numerico_casos_extremos`, `test_ausentes_nunca_viram_zero` |
| 12 | timestamps/fusos | `ExcelTest.test_timestamps_e_fusos` (inclui missão sem fuso) |
| 13–15 | SVG, PNG, ZIP | `FigurasTest.test_svg_vetorial_valido`, `test_png_valido_300_dpi_fundo_branco`, `test_zip_de_figuras_manifesto_e_hashes` |
| 16 | ausentes/corrompidos | `IntegridadeTest` (despacho, modelo e previsão corrompidos no arquivo; dado local; manifesto divergente; dado inexistente), `EstudoArquivadoTest.test_estudo_corrompido_erro_legivel_sem_documento`; limites: `ExcelTest.test_limite_de_linhas_divide_explicitamente_e_limite_de_celulas_recusa` |
| 17 | nomes/conteúdos maliciosos | `IntegridadeTest.test_nomes_e_conteudos_maliciosos` (markup, fórmula, `../`, controle) |
| 18 | sem otimizador | `ImutabilidadeTest.*` com motor/modelos/`despacho.relatorio`/`runner.submit` sabotados; `test_camada_de_relatorios_nao_importa_o_motor` (subprocesso) |
| 19 | sem alterar | `ImutabilidadeTest.test_exportacoes_sem_motor_e_sem_alterar_rodadas_cenarios_ou_estudos`, `RodadaLocalTest` |
| 20 | instalação limpa | `ImutabilidadeTest.test_instalacao_limpa_sem_a_microrrede_original`, `EstudoArquivadoTest` |
| 21–23 | sem bateria / sem PEMFC / sem FV | `CombinacoesTest` (inclui déficit real e H₂ "não disponível") |
| 24 | regressões | suíte completa + E2E dos pisos anteriores (§14) |
| 25 | EMS V1.6 idêntico | `ImutabilidadeTest.test_ems_v16_inalterado` (custo 88,3190884544543; SHA-256 científico = código atual) |

**Prova científica essencial:** rodada REAL do 2C → `exporter.export_bytes` → importação numa instalação limpa →
PDF/Excel/PNG/SVG com `run_optimizer`, `build_exchange_package`, `_simulate_solar`, `_simulate_wind`,
`series_dataframe`, `despacho.relatorio` e `runner.submit` substituídos por exceções → indicadores do PDF/Excel = resumo
da origem; séries do Excel = séries originais bit a bit.

### 12. Evidências de qualidade visual

PDFs renderizados página a página (pypdfium2) e inspecionados: capa limpa, cartões sem corte, tabelas dentro das
margens, figuras vetoriais nítidas com legendas abaixo dos eixos (sem sobreposição), títulos de painel, eixos com
unidade, data no título do eixo quando a janela cabe num dia, "Página X de Y". Ajustes feitos após a inspeção:
título do 1º painel perdido em figuras multi-painel; subtítulos longos cortados (agora quebrados); títulos órfãos no
fim de página (`keepWithNext`); cabeçalhos de tabela partidos; inteiros mostrados como "31,0000"; lista longa de
figuras individuais substituída por seletor + um botão.

### 13. E2E com Chromium

`tools/e2e/e2e_piso2db_relatorios.js` (origem `tools/e2e/seed_piso2db.py`; destino com o motor sabotado por
`tools/e2e/sabotage/sitecustomize.py`, que registra qualquer chamada) e conferência dos arquivos baixados por
`tools/e2e/check_piso2db_downloads.py`: fases `local` (ORIGEM: rodada concluída → PDF/Excel/figuras baixados, figura SVG individual, rodada falha → diagnóstico com figuras desabilitadas, exportação do estudo) **20** · `importar` (instalação LIMPA, motor sabotado: importar → rodada → os três documentos) **13** · `kill -9` do servidor + reinício → `reinicio` (link direto, nada pré-gerado, PDF e Excel novamente) **8** · `tablet` retrato/paisagem (sem rolagem horizontal, botões na tela, PDF baixado) **14** = **55/55**, executado desde diretórios vazios com o código final. Conferência dos arquivos baixados: **145/145** — PDFs (local, arquivo, reinício) com todos os identificadores, custo e SHA-256 dos dados; páginas renderizadas e inspecionadas; folhas de dados do Excel idênticas (`check_exact`) nas três origens e indicadores = resumo da origem bit a bit; figuras do ZIP com SHA-256 conferido, PNG ≥ 1 900 px, SVG válido e **idênticas byte a byte** entre a rodada local e a arquivada; registro do motor sabotado **vazio**; destino terminou com `microgrids/` vazio.

### 14. Resultados de regressão

E2E desde diretórios vazios, com reinícios entre as fases (servidor derrubado com `kill -9`): Piso 1 (`comissionar`/`reabrir`/`tablet`) e Gestor (`multi`/`reinicio`/`tablet`/`legado`) — todas as fases CONCLUÍDAS (estes dois roteiros abortam na primeira asserção falha e não imprimem contagem); 2A **53/53** (43+5+5); 2B **58/58** (43+8+7); 2C **55/55** (38 com `kill -9` durante a rodada longa + 10 + 7); 2D-A **62/62** (13+34+8+7; motor sabotado no destino: 0 chamadas). Suíte: `python -m pytest tests/ -q` → **443 passed**, 0 failed (356 s; 128 subtests; os mesmos 7 avisos da linha de base) — 407 da linha de base medidos nesta sessão + 36 novos. `git diff origin/main --stat -- models h2_pemfc simulation config ems_integration reference_models orchestrator_runtime.py orchestrator_app.py` **vazio**.

### 15. Problemas detectados e corrigidos durante a missão

- O escritor padrão do openpyxl perderia o 17º algarismo de alguns doubles → escrita com `repr` (leitura bit a bit por
  Python testada; o Excel garante 15 algarismos — §9/§21).
- `pd.read_csv` padrão não garante o double exato → `float_precision="round_trip"`.
- Texto do cenário entrava no título Plotly como marcação (o matplotlib descartaria `<b>…</b>`) → escapado antes;
  caracteres de controle → U+FFFD (sem avisos de glifo); `$` escapado (sem mathtext).
- Teste de dano no disco: as tabelas do Arquivo são imutáveis por gatilho (como no 2D-A, o teste remove o gatilho
  para simular corrupção).
- Asserções que fixavam a versão "2.0.0-piso2da" (teste AppTest e E2E 2D-A) passaram a usar a versão corrente
  (`APP_VERSION` = `2.0.0-piso2db`), sem enfraquecer a verificação (versão do exportador exibida).

### 16. Riscos residuais

- **Integração de energia do runner (registrado, não alterado — regra 4):** `energia_demanda_kWh = Σ_{k<passos}
  P_k·Ts` com `passos = duração + 1` (o instante terminal entra como um passo de 60 s): numa missão de 30 min são 31
  min integrados. Os relatórios mostram o valor persistido com a fórmula declarada; a decisão metodológica é do piso
  do otimizador (`EMS_TO_TALK_ABOUT.md`).
- O desenho estático usa matplotlib (não o motor Plotly): as curvas são as mesmas, mas a tipografia difere da tela.
- Excel não tem fuso: a referência temporal está no comentário/dicionário; datas com sub-segundos não ocorrem hoje.
- Geração síncrona no servidor Streamlit (PDF ≈ 2–3 s, figuras ≈ 4 s para 30 min; cresce com a missão); limite de
  12 M células no Excel; os documentos ficam na sessão só para a rodada aberta.
- Sem assinatura digital: SHA-256 prova integridade, não autoria.

### 17. Arquivos modificados

| Arquivo | Mudança |
|---|---|
| `seeds2/report/dossier.py`, `columns.py`, `xlsx.py`, `figures.py`, `run_pdf.py` (novos) | Hitos A–C |
| `seeds2/ui/report_exports.py` (novo) | painel de exportação (Hito D) |
| `seeds2/ui/execution_ui.py` | `run_results` chama o painel (rodada local e estudo arquivado); prefixo `rx_` limpo com o estado |
| `seeds2/__init__.py` | `APP_VERSION = "2.0.0-piso2db"` |
| `requirements.txt` | `matplotlib==3.10.7`, `openpyxl==3.1.5` |
| `tests/test_seeds2_piso2db.py`, `tests/test_seeds2_piso2db_app.py` (novos) | 36 testes |
| `tests/test_seeds2_piso2da_app.py`, `tools/e2e/e2e_piso2da_arquivo.js` | versão do exportador = versão corrente |
| `tools/e2e/e2e_piso2db_relatorios.js`, `seed_piso2db.py`, `check_piso2db_downloads.py`, `sabotage/sitecustomize.py` (novos) | E2E |
| `PARAMIJEFE.md`, `CLAUDE.md`, `docs/ai/HANDOFF.md`, `docs/seeds2/ARMAZENAMENTO.md` | documentação |

### 18. Instruções para auditoria independente

1. `pip install -r requirements.txt pytest` → `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ -q`.
2. `python -m pytest tests/test_seeds2_piso2db.py -q` (prova científica: `ImutabilidadeTest`, `ExcelTest.test_precisao_numerica_bit_a_bit`).
3. `git diff origin/main --stat -- models h2_pemfc simulation config ems_integration reference_models orchestrator_runtime.py orchestrator_app.py` → vazio.
4. E2E: `python tools/e2e/seed_piso2db.py <origem>` → servidor na origem → fase `local` → servidor na instalação
   VAZIA com `PYTHONPATH=tools/e2e/sabotage SEEDS2_E2E_ROOT=<raiz> SEEDS2_E2E_ENGINE_LOG=<log>` → `importar` →
   `kill -9` + reinício → `reinicio` → `tablet` → `python tools/e2e/check_piso2db_downloads.py <saida> <origem>/e2e_origem.json <log>`;
   inspecionar `<saida>/paginas/*.png`.
5. Abrir o `.xlsx` baixado no Excel/LibreOffice: folhas, filtros, comentários de cabeçalho, valores com 17 algarismos.

### 19. Estado final do Piso 2

| Sub-piso | Estado |
|---|---|
| 2A Centro de Operação | integrado (PR #6) |
| 2B Previsões e Dados | integrado (PR #7) |
| 2C Execução EMS | integrado (PR #8) |
| 2D-A Arquivo Científico | integrado (PR #9, `3b73971`) |
| 2D-B Relatórios e exportações | implementado e verificado nesta rama; aguarda auditoria |

Com o 2D-B o Piso 2 cobre o ciclo completo: cenário → previsões → execução → arquivo portátil → documentação
verificável, sem recomputação. Dívida remanescente: rodadas do console V1.6 (Simulação) só têm resumo.

### 20. Próximas interfaces necessárias para o piso do otimizador

- Representar no motor o que hoje o preflight BLOQUEIA (SOC por banco, `n_ini`/`P_prev` declarados, estados de
  partida) — capacidades pendentes da Entrega 3 §14.1.
- Decidir a convenção de integração temporal (instante terminal) antes de novas métricas; os relatórios já leem só o
  resumo persistido, então uma nova versão do resumo exigirá apenas novas entradas em `dossier.indicators` e
  `columns` (com versão de formato).
- Funções objetivo adicionais: `manifest.objective` já identifica a função; o PDF lê o rótulo e os termos do manifesto.
- Comparação de múltiplas rodadas/estudos: o `RunDossier` é a unidade de leitura reutilizável.

### 21. Correção de auditoria C-04 — completude do dossiê e precisão documentada do Excel

Auditoria independente do PR #10: **favorável**, com duas observações focalizadas, corrigidas nesta rama/PR.

**C-04.1 — rodada concluída com recursos essenciais ausentes.** *Causa:* `dossier._check_run` exigia o resumo, mas não
os dados essenciais; `xlsx.build_workbook` usava `if d.has(name)` e omitiria em silêncio uma tabela obrigatória (o PDF
e as figuras também toleravam a ausência). *Correção:* `dossier.REQUIRED_CONCLUDED = (entradas/missao.csv,
saidas/despacho_ems.csv, saidas/relatorio_ems.json)`; `_check_run` (antes de qualquer leitura) e `require_complete`
(barreira chamada por `run_pdf.build_report`, `xlsx.build_workbook` e `figures.run_figures`, mesmo para um dossiê
montado por fora de `load`) recusam com `DossierIntegrityError` que NOMEIA o recurso ausente do índice original;
verificações de SHA-256 e tamanho preservadas; o `if d.has` do Excel foi removido (tabelas obrigatórias). Rodadas
falha/interrompida continuam gerando diagnóstico (nada exigido); modelos físicos (`modelos/*.csv`) não são impostos
(dependem das tecnologias da rodada — p. ex. rodada sem FV não tem `solar.csv` e é aceita).

**C-04.2 — precisão do XLSX frente ao Excel.** A escrita `repr` foi mantida (as células continuam numéricas; nenhuma
virou texto); a documentação foi corrigida para distinguir precisão serializada × precisão garantida pelo Microsoft
Excel (15 algarismos) × fontes originais (§9): `xlsx.PRECISION_NOTE` no índice da planilha; advertência condicional
quando há números com > 15 algarismos significativos (`sig_digits`; contagem no índice e na interface); legenda junto
ao download do Excel (`report_exports.EXCEL_PRECISION_CAPTION`) e ajuda do botão sem "precisão integral"; CLAUDE.md e
HANDOFF ajustados. Nenhuma afirmação de preservação bit a bit DENTRO do Excel permanece.

**Risco metodológico (dívida científica prioritária, não corrigida):** PDF e Excel identificam agora, explicitamente,
a duração declarada (30 min), os passos usados (31), Ts (60 s), a duração efetivamente integrada (31 min) e a
convenção do runner (`E = Σ_{k=0}^{passos−1} P_k · Ts`), por `dossier.integration_convention` (somente descrição):
nota no Resumo executivo e nas Limitações do PDF; linhas em `02 Indicadores` e nota no índice do Excel. Fórmula do
runner, optimizador e valores persistidos inalterados (teste confirma `energia_demanda_kWh` idêntico).

**Testes (11 novos + 1 asserção de interface):**

| Exigência | Teste | Resultado |
|---|---|---|
| 1 concluída sem entradas → recusada (local e arquivada; PDF/Excel/figuras) | `C04CompletudeTest.test_1_sem_entradas_recusada` | recusada, recurso nomeado |
| 2 sem despacho | `test_2_sem_despacho_recusada` | recusada |
| 3 sem relatório do EMS | `test_3_sem_relatorio_ems_recusada` | recusada |
| 4 completa aceita; modelos não impostos (rodada sem FV) | `test_4_rodada_completa_aceita_e_modelos_nao_sao_impostos` | aceita |
| 5 falha/interrompida sem resultados → diagnóstico | `test_5_rodada_falha_sem_resultados_permite_diagnostico` | PDF/Excel diagnóstico |
| 6 geradores não produzem documento de dossiê incompleto (inclusive montado por fora) | `test_6_geradores_recusam_dossie_incompleto_mesmo_montado_por_fora` + 1–3 | recusado |
| precisão: algarismos significativos; nota no índice; aviso só quando > 15 | `C04PrecisaoTest` (4) | ok |
| leitura exata por Python preservada | `C04PrecisaoTest.test_leitura_exata_por_python_preservada` + `ExcelTest.test_precisao_numerica_bit_a_bit` | bits iguais |
| texto na interface | `test_interface_explica_a_precisao`; `RodadaLocalTest` (legenda + aviso na página) | ok |
| duração × passos × convenção no PDF e Excel | `C04IntegracaoTemporalTest` | 30 min · 31 passos · 31 min |

**Resultados medidos:** `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ -q` → **454 passed, 0 failed (353 s; 128 subtests; os mesmos 7 avisos) — 443 anteriores + 11 novos**. E2E 2D-B repetido
desde diretórios vazios com o código corrigido (origem → instalação LIMPA com o motor sabotado → `kill -9` → reinício
→ tablet): **57/57** (local 21 · importar 14 · reinício 8 · tablet 14; +2 asserções da legenda de precisão) e
conferência dos downloads **157/157** (+12: nota de precisão nos 3 Excel; duração/passos/integração nos 3 PDF);
motor nunca chamado; nenhuma microrrede criada no destino. PDF e Excel legítimos inspecionados (nota de integração no
Resumo executivo). Diff científico, esquemas SQLite e formato `.seeds2study.zip`: inalterados.

**Arquivos:** `seeds2/report/dossier.py` (`REQUIRED_CONCLUDED`, `missing_required`, `require_complete`,
`integration_convention`), `xlsx.py` (`PRECISION_NOTE`, `sig_digits`, aviso, linhas de integração, tabelas
obrigatórias), `run_pdf.py`, `figures.py` (barreira; nota), `seeds2/ui/report_exports.py` (legenda/ajuda),
`tests/test_seeds2_piso2db.py`, `tests/test_seeds2_piso2db_app.py`, `tools/e2e/e2e_piso2db_relatorios.js`,
`tools/e2e/check_piso2db_downloads.py`, `PARAMIJEFE.md`, `CLAUDE.md`, `docs/ai/HANDOFF.md`.

---

## Entrega 6 — SEEDS2 Piso 3A · Fundaciones del EMS MILP–MPC (contratos, referencia y auditor; sin solver)

> Redactada en español (decisión 4 del responsable para la documentación científica del Piso 3). Detalle completo en
> `docs/ems_v2/` — este apartado resume y remite, sin duplicar.

### Punto de continuidad

| Campo | Valor |
|---|---|
| Rama | `ccr-fb5b5eb8-bvbyw2` (designada por el entorno de la sesión) |
| Base | `main` `8556b71a76dd13d279a0e0ecd8ad9bd498df72f1` (merge del PR #10) = SHA base auditado por el paquete maestro; **sin diferencias de código** |
| PR | [#11](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/11) contra `main` **sin merge** (commits `96c2762`, `3c6aabc` + este registro) |
| Autorización | Plan 3A aprobado con condiciones A–F (2026-11-08); sólo Piso 3A |
| Pendientes de esta misión | ninguno; correcciones C-3A-01..04 aplicadas (§5, §5b); integración aguarda auditoría final y autorización humana. **No iniciar 3B sin revisión.** |

### 1. Resumen

**Solicitado:** fundaciones del EMS MILP–MPC (orden ejecutiva 3A): contratos canónicos por UID con procedencia,
unidades/fronteras, malla temporal N/N+1, cálculo de referencia algebraico (B01), fixtures sintéticas, auditor
algebraico independiente, catálogo de símbolos M01–M23 + adenda v1.1 con prueba de cobertura. Sin Pyomo/HiGHS,
sin despacho, sin selector, sin cambios en el Centro de Operação ni en el V1.6.

**Entregado:** paquete `ems_v2/` (solo biblioteca estándar), `ems_v2/catalogo/` (150 símbolos, 42 ecuaciones),
`docs/ems_v2/` (README, DECISIONES_3A, MATRIZ_3A, referencias versionadas con SHA-256) y `tests/ems_v2/` (135 tests
sintéticos/algebraicos). Registro de la arquitectura experimental en `CLAUDE.md` y `docs/ai/HANDOFF.md`.

### 2. Condiciones de la fiscalización (A–F)

| Cond. | Cumplimiento |
|---|---|
| A — auditor independiente | `ems_v2/audit.py` (punto flotante, segundos, bisección) no importa `ems_v2/reference.py` (racionales exactos); verificado por AST. Esperados = literales analíticos de los documentos. Toda mutación aislada ±1e-3 en 7 casos es rechazada. |
| B — catálogo | estados `ativo_3A` / `auditado_3A` / `futuro` / `substituido` y `variante` `comum`/`instantanea`/`multimodo`; 0 símbolos indefinidos; activos con código resoluble; futuros sin capacidad; variantes B05 sin mezcla. |
| C — sin valores implícitos | Ningún campo científico con valor por defecto (test parametrizado); ausente ⇒ `erro`/`pendente`. Única regla de política: `D̄ = 0` sin dispositivo (adenda v1.1, D03). |
| D — tolerancias provisionales | `Tolerancias.status = "provisoria"` (dossier §Métricas algebraicas + propuesta 3A para kg/h y kg); ninguna ajustada para obtener verde. |
| E — documentación acotada | `CLAUDE.md` +10 líneas (arquitectura y estado real); reglas generales intactas. `ems_v2/` **no** se agregó a la lista de directorios protegidos (sería cambiar una regla general): queda para decisión del responsable. |
| F — especificaciones | A05-OPT, A07, A08 (`especificacao_3B`) y B05A (`especificacao_3C`) con `executado_por_solver = False`. |

### 3. Pruebas y evidencia

- Nuevas: `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ems_v2 -q` → **135 passed** (≈0,5 s; sin solver).
- Regresión completa: `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ -q` → **589 passed, 7 warnings, 128 subtests
  passed (366 s)** = 454 de `main` (medidos en esta sesión antes de cambiar nada) + 135 nuevos; los mismos 7 avisos
  (SciPy SLSQP del V1.6). Ninguna falla preexistente ni introducida.
- V1.6 intacto: `git diff --stat 8556b71 -- ems_integration models h2_pemfc simulation config reference_models
  orchestrator_runtime.py orchestrator_app.py app.py seeds2 requirements.txt` vacío; ningún archivo Python fuera de
  `ems_v2/` y `tests/ems_v2/` menciona `ems_v2` (test).
- Sin E2E de navegador: el PR no toca interfaz.

### 4. Contradicciones, hipótesis y riesgos

C1–C8 resueltas según lo aprobado; observaciones adicionales (M12 en multimodo; tolerancia de kg/h) e hipótesis
H-3A-01…09 en `docs/ems_v2/DECISIONES_3A.md` §4–§5. Riesgos y propuesta para 3B-P en §6–§7 del mismo documento.
**Obligación registrada:** congelar las salidas numéricas del V1.6 antes de cualquier benchmark comparativo.

### 5. Corrección de auditoría C-3A (PR #11, dictamen favorable con correcciones obligatorias)

| ID | Defecto | Antes | Después |
|---|---|---|---|
| C-3A-01 (bloqueante) | Sin dispositivo de descarte, `audit.auditar` no exigía `d >= 0` (descarte negativo = generación ficticia) | B01B con P_R = 70, C_oper = 30, d = −10 y costo/KPI coherentes: **aceptado** | `0 <= d <= D̄` siempre (`D̄ = 0` sin dispositivo); código `descarte_negativo`; rechazado con y sin dispositivo |
| C-3A-02 | Tolerancias NaN/±Inf/negativas/no numéricas aceptadas | `potencia_abs_kW = inf` aceptaba candidata adulterada (+1 kW) | `validar_tolerancias` ⇒ `tolerancia_invalida`, sin evaluar familias; valores provisionales intactos |
| C-3A-03 | `_construir` truncaba tuplas de longitud fija (`zip`) y no verificaba tipos | vértice `[10, 0.7, 99]` truncado; `"abc"` → vértices de caracteres; escalar → `TypeError` no controlado | deserialización estricta con `ErroSerializacao` y ruta del campo; ida y vuelta JSON idéntica (texto y SHA-256) |

Nuevos tests: 100 casos (`test_c3a01_*`, `test_c3a02_*`, `test_c3a03_*`). Contra el código anterior (`5592847`):
94 fallan, 6 pasan (controles positivos o estructuras que ya lanzaban `TypeError`). Tras la corrección:
`python -m pytest tests/ems_v2 -q` → **235 passed**; `python -m pytest tests/ -q` → **689 passed, 7 warnings,
128 subtests (367 s)** = 454 + 235. Formulación científica, tolerancias provisionales, V1.6, runtime e interfaz
sin cambios. Detalle: `docs/ems_v2/DECISIONES_3A.md` §8 y `MATRIZ_3A.md` (sección final).

### 5b. Corrección C-3A-04 (segunda fiscalización: C-3A-01..03 aprobados)

| | |
|---|---|
| Defecto | La verificación de la cadena bruto → normalizado exigía igualdad RACIONAL con el `float` producido por el conversor: `Parametro.de_bruto(0.12345678912345678, "W")` (→ `0.00012345678912345677 kW`) era rechazado por `validar_parametro` (`cadeia_transformacao_inconsistente`); igual en series con valores brutos. |
| Corrección | Regla única `units.converter` (racional exacto redondeado una vez al `float` más próximo) usada por el conversor y por `parameters.verificar_cadeia` (parámetros y series). Acepta exactamente ese `float`; rechaza cualquier otro (incluso ±1 ulp) y transformaciones registradas incoherentes (`transformacao_inconsistente`). Tolerancias físicas de `audit.py` intactas. |
| Evidencia | 33 casos `test_c3a04_*`; contra `7becd42`: 6 fallan / 27 pasan (conversiones exactas en binario y rechazos ±1 ulp ya correctos). Tras la corrección: `tests/ems_v2` **268 passed**; `python -m pytest tests/ -q` **722 passed, 7 warnings, 128 subtests (366 s)** = 454 + 268. Detalle: `docs/ems_v2/DECISIONES_3A.md` §9. |

### 6. Rollback

Revertir el PR elimina `ems_v2/`, `tests/ems_v2/`, `docs/ems_v2/` y las líneas de `CLAUDE.md`/`HANDOFF.md`/
`PARAMIJEFE.md`; ningún otro archivo, base de datos ni resultado histórico depende de ellos.

---

## Entrega 7 — SEEDS2 Piso 3B-P · Primer optimizador MILP ejecutable (Pyomo + HiGHS)

> Redactada en español (documentación científica del Piso 3). Detalle: `docs/ems_v2/FORMULACAO_3BP.md`,
> `docs/ems_v2/MATRIZ_3BP.md` y `docs/ems_v2/EVIDENCIA_3BP.md`. Este apartado resume y remite.

### Punto de continuidad

| Campo | Valor |
|---|---|
| Rama | `claude/seeds2-piso3b-milp-highs` (nueva, desde `main`; no reutiliza la rama del PR #11) |
| Base | `main` `f6d009db169b60a84657f79a7006640e20470b82` (merge del PR #11); árbol idéntico al HEAD auditado del 3A (`37ba4f1`) |
| PR | [#12](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/12) contra `main` **sin merge** |
| Pendientes de esta misión | ninguno; correcciones C-3B-01/02 (§6b) y C-3B-03 (§6c) aplicadas; integración aguarda la fiscalización final. **No iniciar 3C sin autorización.** |

### 1. Resumen

Primer MILP real del motor `milp_mpc_v1`: `ems_v2.milp.solver.resolver(entrada, configuracao, compromisso_fixo)`.
Construye en Pyomo un modelo de **una ventana** (N intervalos / N+1 fronteras) a partir de `EntradaModeloEMS`
declarada `v1.1-3B-P` y lo resuelve con HiGHS. Clasifica la terminación y **solo acepta el despacho aprobado por el
auditor independiente**, que no usa Pyomo.

- **Restricciones:** M02, M03-v1.1, M04, M06–M08, M10 con compromiso **fijo** constante e igual al estado inicial, y M14–M16 (PWL sintética con binarias por segmento, sin SOS).
- **Objetivo:** curtailment, throughput, ENS y combustible h·q, siempre con coeficientes declarados.
- **No incluye:** MPC, transiciones/rampas/permanencias, multimodo, curva PEMFC real, UI ni Centro de Operação.

### 2. Dependencias y entorno

`pyomo==6.10.1` (BSD-3) y `highspy==1.15.1` (MIT, HiGHS 1.15.1) en `requirements-ems_v2.txt`, separado de
`requirements.txt`. Verificado en un venv limpio con Python 3.13.18: la combinación conserva numpy 2.2.6, pandas
2.2.3, scipy 1.15.3 y streamlit 1.66.1. Smoke MILP (binaria + continua) correcto en `highs` y `appsi_highs`.

Se eligió `pyomo.contrib.solver` "highs" (justificación en FORMULACAO_3BP §1). HiGHS rechaza SOS y expresiones no
lineales en esta interfaz, y un problema no acotado devuelve `feasible`; el clasificador nunca lo convierte en
despacho. Hardware de la evidencia: 4 CPU x86_64, 15 GiB.

### 3. Obstáculos A/B (extensión controlada)

- **A:** el perfil lo elige la `versao_formulacao` de la entrada (`PERFIS_FORMULACAO`).
  - Las entradas 3A no cambian: A05-OPT 3A sigue `pendente`, y el MILP rechaza las entradas 3A con `formulacao_nao_3bp`.
  - Dos campos opcionales nuevos (V_ℓ y c_H) se omiten del JSON cuando están ausentes, así que las entradas 3A conservan el mismo texto y el mismo SHA-256 que en `main` (test con los hashes medidos en `f6d009d`).
- **B:** `auditar(..., compromisso_fixo)` verifica de forma independiente el programa, la integralidad, M10, la PWL, el balance y los costos 3B-P. Rampas y permanencias se declaran `familias_nao_modeladas`. Sin programa, el comportamiento 3A no cambia.
- **Capacidades y catálogo:** `CAPACIDADES_3BP` y las columnas `status_3BP`/`codigo_3BP` en el **mismo** catálogo. Un test impide símbolos futuros en ecuaciones declaradas implementadas.

### 4. Resultados (HiGHS real; esperados analíticos o por enumeración independiente)

| Caso | Resultado |
|---|---|
| A01, A02 | 60 kWh / 1/6 kWh; 61 fronteras |
| A03, A04 | e_N = 50 / 69 kWh |
| B01A, B01B | R$ 0 con E_indisp = 100 kWh / R$ 10 |
| A05-FEAS | Cargar y verter: ambas factibles con objetivo 0 |
| A05-OPT | **El solver lo encuentra**: P_c = 10 kW, C_oper = 0, e₁ = 59 kWh, R$ 0 |
| A06 | q = 0,9 kg/h, 0,015 kg/min; ON a 5 kW inviable; OFF p = q = 0 |
| PWL no convexa | Igual a la enumeración en 5 escenarios; vértice interno p = 16 kW, R$ 12,5 |
| A07, A08 duro | `provenInfeasible` |
| A08 degradado | ENS = 5 kWh, R$ 10 (V = 2 R$/kWh declarado) |
| Dos BESS | 8,75 / 6,25 kW, R$ 1,1875 |
| Exclusividad | R$ 18,888… (no la solución simultánea de R$ 17,2) |
| Terminaciones incompletas reales | `time_limit=0` y `mip_max_nodes=0` ⇒ `sem_solucao`; `mip_max_improving_sols=1` ⇒ incumbent no óptimo (gap 0,88 %) auditado y aceptado como `aceito_factivel_nao_otimo`; límite de tiempo real con incumbent (N=48, 0,05 s) registrado en EVIDENCIA |

### 5. Pruebas

- Base `main`: `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ -q` ⇒ **722 passed, 7 warnings, 128 subtests**.
- Rama: `tests/ems_v2` ⇒ **354 passed** (268 del 3A + 86 nuevos). Sin Pyomo: 280 passed y 3 skipped explícitos.
- Regresión completa ⇒ **808 passed, 7 warnings, 128 subtests (366 s)**; los avisos son los mismos.
- `git diff --stat f6d009d -- ems_integration models h2_pemfc simulation config reference_models orchestrator_runtime.py orchestrator_app.py app.py ems_app.py seeds2 requirements.txt` ⇒ vacío.
- Ningún test del 3A fue modificado. El generador de evidencia está dentro del paquete (`python -m ems_v2.milp.evidencia`) para no relajar el test de aislamiento de 3A, que detectó la primera ubicación en `tools/`.

### 6. Decisiones y contradicciones registradas (no bloquean; requieren conocimiento del responsable)

1. **Compromiso fijo más estricto que "fijar compromiso".** El programa debe ser constante e igual al estado inicial, porque sin M09/M11/M12 un arranque o una parada se ignorarían físicamente. Las transiciones quedan para 3C.
2. **A04 único:** exige un criterio económico declarado (c_curt = 1 R$/kWh en la fixture). Con objetivo nulo, cualquier carga entre 0 y 10 kW es factible.
3. **A08 degradado:** el criterio de mínima ENS es económico (V_ℓ·ℓ, V declarado). La prioridad lexicográfica (M22) sigue fuera de alcance.
4. **Combustible:** solo h·q. Los eventos (m^SU/m^SD) no existen en el contrato y las transiciones están bloqueadas.
5. **"Óptimo"** = convergencia de HiGHS dentro de los gaps configurados (0 en los casos analíticos); es la optimalidad del modelo reducido.
6. **Límite de tiempo con incumbent:** no es determinista. Como test se usa un límite de soluciones real más una simulación en el adaptador, y la observación real queda en EVIDENCIA.

### 6b. Corrección de auditoría C-3B (PR #12: favorable con dos correcciones bloqueantes)

| ID | Antes (`a8e3426`) | Después |
|---|---|---|
| C-3B-01 | Programas de compromiso con NaN/Inf/None/texto/escalar/anidados ⇒ **excepción no controlada** en `_hash_compromisso` (`int(x)` antes del preflight). `(1,)`, `(1.0,)` y `(True,)` tenían el mismo hash; `1.0` se aceptaba | Hash canónico sin pérdida y con tipo, que nunca lanza excepción. Preflight con `int` estricto en `{0, 1}` ⇒ `bloqueado_validacao` + `compromisso_invalido` |
| C-3B-02 | `z_b = 0,5`, `z_b` incoherente, δ en otro segmento o fraccional, θ fuera del segmento o de [0,1], θ = None y δ = NaN ⇒ **`aceito_otimo`** | Capa separada `ems_v2/milp/integridade.py` (sin Pyomo) ⇒ `rejeitado_integridade` (o `sem_despacho` con valores ausentes). Auditoría algebraica intacta; tolerancias no relajadas |
| Robustez | Excepción del executor/cargador ⇒ no controlada. Opción HiGHS inválida ⇒ ignorada en silencio (`aceito_otimo`) | `erro` controlado: `falha_solver`, `falha_carregamento`, `opcao_highs_invalida` |

49 tests adversariales (`test_ems_v2_milp_auditoria_3b.py`): **37 fallan contra `a8e3426`** y todos pasan con la
corrección. `tests/ems_v2` ⇒ **403 passed**. Suite completa ⇒ **857 passed, 7 warnings, 128 subtests (370 s)** =
808 + 49. V1.6, runtime, UI, `requirements.txt` y `requirements-ems_v2.txt` sin cambios en el hotfix. Detalle:
`docs/ems_v2/FORMULACAO_3BP.md` §7.

### 6c. Corrección C-3B-03 (segunda fiscalización: C-3B-01/02 aprobados)

- **Defecto:** `configuracao_registro()` ejecutaba `dict(opcoes_highs)` antes de `validar_configuracao()`. Con `X.b01b()`, `opcoes_highs` igual a None, 42 o "abc" provocaba una **excepción no controlada**. Una lista de pares se registraba **reinterpretada** como dict, y una configuración de tipo incorrecto se registraba como `{}`.
- **Corrección:** `resolver()` valida antes de preparar los metadatos. El registro nunca lanza excepciones ni reinterpreta valores: preserva el valor original y marca `valida: False`. El registro válido no cambia.
- **Verificación:**
  - 13 tests `test_c3b03_*`: 12 fallan contra `a47a306` (solo pasa el control válido).
  - `tests/ems_v2`: **416 passed**.
  - Suite completa: **870 passed, 7 warnings, 128 subtests**.
  - Formulación, tolerancias, auditor, contrato y dependencias sin cambios. Detalle: FORMULACAO_3BP §7.

### 7. Rollback

Revertir el PR elimina `ems_v2/milp/`, `ems_v2/fixtures_3b.py`, los tests `test_ems_v2_milp_*`, la documentación
3B-P y `requirements-ems_v2.txt`. También revierte las extensiones de `contracts.py`, `audit.py`,
`capabilities.py`, `fixtures.py` y del catálogo; el comportamiento y los hashes del 3A se conservan en ambos
sentidos. Nada en V1.6, en la aplicación ni en los bancos depende de ello.

---

## Entrega 8 — SEEDS2 Piso 3C-0 · Puente científico entre el EMS MILP y la plataforma de microrredes

> Redactada en español. Detalle: `docs/ems_v2/PONTE_3C0.md` (arquitectura, decisiones, contradicciones),
> `MATRIZ_INTEGRACAO_3C0.md`, `MATRIZ_PARAMETROS_3C0.md`, `BRECHAS_3C0.md`, `TRANSICAO_3C0_3C1.md` y
> `EVIDENCIA_3C0.md`. Este apartado resume y remite.

### Punto de continuidad

| Campo | Valor |
|---|---|
| Rama | `ccr-0cc9677c-ydyfl7` (desde `main`) |
| Base | `main` `3c65d980` (merge del PR #12, 3A + 3B-P integrados); verificado idéntico al HEAD de la rama al iniciar |
| PR | [#13](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/13) contra `main`, **sin merge** |
| Pendientes | C-3C0-01 aceptada condicionalmente; correcciones H-01..H-04 aplicadas (§6b); D-3C0-01..09 a revisión; **no iniciar 3C-1 sin autorización** |

### 1. Resumen

Contratos verificables que permiten construir el EMS V2 sobre las microrredes del SEEDS2 sin integrarlo todavía:

- **Inventario por UID** (`ems_v2/ponte/inventario.py`): microrred = UID + incarnación + revisión + huellas; cada
  dispositivo (`eq-…`, `arr-…`) con su UID de microrred, modelo asociado, papel EMS, `quantidade` y valores con
  origen/unidad/ruta/procedencia. Sin agregación (el adaptador V1.6 agrega; la puente no).
- **Matriz de parámetros** (`requisitos.py`): 31 símbolos declarativos, 5 clases (disponible, derivable, faltante,
  opcional, sintético). Sugerido por el SEEDS2 ⇒ faltante. Conversión de unidades exacta y registrada.
- **Escenario / previsión / realización / tiempo** (`cenario.py`): tipos separados; la realización nunca llega a la
  proyección; oráculo solo declarado; malla 3A N/N+1 reutilizada; horizonte de planeamiento reservado.
- **Proyección** (`projecao.py`) a `EntradaModeloEMS` validada por `validar_entrada` sin relajación.
- **Plan → ejecución → estado** (`execucao.py`): plan solo de resultado aceptado; ejecución contra la realización;
  estado con índice global e instante; checkpoints sellados y encadenados; retomada bit a bit; desvíos.
- **Preflight** (`preflight.py`), **registro sellado** con costo realizado ≠ valor futuro (`registro.py`) e
  **instrumentación** (`instrumentacao.py`).
- **Lector real** (`ems_v2/ponte_seeds2/leitor.py`), solo lectura, por el catálogo.

### 2. Hallazgos iniciales relevantes

- El inventario del Piso 1 no registra procedencia por parámetro, η de baterías, potencias en la barra,
  autodescarga, P_min/curva H₂ de la PEMFC, permanencias ni costos de parada. El V1.6 obtiene η, P_min, curva y rampa
  de la PEMFC **identificándolos de series simuladas** del propio modelo (no aprobado como fuente del EMS V2).
- Los límites de SOC 20/80 % y la suciedad 0 % pueden ser solo **valores sugeridos** del SEEDS2.
- El escenario declara disponibilidad por registro (usina FV), no por arreglo (C-3C0-02, resuelta con herencia
  explícita).
- Dos tests 3A/3B-P impedían toda relación `ems_v2 ↔ seeds2` (C-3C0-01).

### 3. Resultado sobre una microrred real

La microrred de prueba equivalente al V1.6 (2 usinas FV con 1 arreglo cada una, 2 bloques PEMFC 3 + 1, 2 bancos)
se lee como 8 dispositivos; la matriz da 16 disponibles, 4 derivables, 6 opcionales y **26 faltantes**. El preflight
`operacional` la **bloquea**: 18 `parametro_obrigatorio_ausente` (η, P en barra, autodescarga, P_min y curva PEMFC)
+ previsión ausente; 12 avisos `necessario_3C1`. Conclusión: **ninguna microrred real puede ejecutar el EMS V2 hoy**,
y el sistema explica por qué (BRECHAS_3C0).

### 4. Cadena de ensayo (sintética, rotulada)

preflight `ensaio` → `EntradaModeloEMS` 3B-P → HiGHS (`aceito_otimo`) → plan (descarga 10 kW en t = 2, valor
analítico) → ejecución algébrica con oráculo declarado (desvío 0; costo realizado = objetivo = R$ 0,025) → registro
sellado, grabado y releído. Con realización distinta de la previsión, la ejecución se interrumpe en el primer
intervalo inexequible (`balanco_realizado_violado`) sin recortar, y el costo realizado cubre solo lo ejecutado.

### 5. Pruebas

Ver `EVIDENCIA_3C0.md` (comandos y resultados). 79 tests nuevos en 4 archivos `tests/ems_v2/test_ems_v2_ponte_*.py`;
un test 3B-P modificado (excepción nominal C-3C0-01, guardia sustitutiva más estricta).

### 6. Decisiones y contradicciones (requieren conocimiento/aprobación)

D-3C0-01..09 y C-3C0-01/02 en `PONTE_3C0.md` §5 y §8. Destacan: tipo de procedencia aditivo `declarado_seeds2`
(no altera hashes 3A); sugerido ⇒ faltante; C·E = potencia terminal, no de barra; métodos de identificación del V1.6
no son fuente; registro en archivo JSON inmutable (no en el banco de la microrred); ejecutor algébrico no es físico.

### 6b. Corrección de la auditoría independiente del PR #13 (favorable con correcciones)

| ID | Antes (`4b77788`) | Después |
|---|---|---|
| H-01 | Previsión numéricamente igual a la realización ⇒ **error** aunque no hubiera fuga | Clasificación por serie: coincidencia sin evidencia ⇒ advertencia; procedencia compartida ⇒ advertencia de sospecha; **bloqueo solo con evidencia** (procedencia que apunta al SHA-256 del contenido realizado, mismo objeto, oráculo falso). Emisión causal sigue bloqueante |
| H-02 | Preflight sin políticas podía terminar «aceptado» | `finalidade` `diagnostico` (parcial, nunca autoriza) × `otimizacao` (por defecto): exige políticas, proyección existente y aceptada, formulación 3B-P y `preflight_3bp`; propiedad `apto_para_otimizacao` |
| H-03 | `exists()` + temporal fijo + `os.replace()` ⇒ sobrescritura concurrente | Publicación exclusiva por `os.link` de un temporal único completo (fallback `O_EXCL`), limpieza garantizada. Arnés multiproceso contra el código anterior: **8/10 rondas violaron la inmutabilidad**; con la corrección, 0 |
| H-04 | Realización exigida para toda la misión | `Realizacao.modo` (`completa_offline` / `incremental_online`) + `observado_ate_utc`; cobertura y causalidad solo hasta τ_k; ejecución que nunca pasa de τ_k y se reanuda. Lo que falta para 3C-2: brecha **K6** (bloqueante) |
| C-3C0-01 | Pendiente | **Aceptada condicionalmente**; no mutación verificada sobre el árbol completo de archivos |

Pruebas: 31 nuevas (`test_ems_v2_ponte_auditoria_pr13.py`); 3A 268 y 3B-P 148 sin cambios; `tests/ems_v2` **526
passed**; regresión completa **980 passed, 7 warnings, 128 subtests** (392 s) = 949 + 31. Tabla de hallazgos → pruebas: `EVIDENCIA_3C0.md` §5. Diff confinado a la
puente, sus fixtures/tests y documentación; V1.6 y núcleo 3A/3B-P sin cambios.

### 6c. Cierre de la segunda auditoría (base `d74f883`: H-01, H-02 y C-3C0-01 aprobados; H-03 mejorado)

| ID | Antes (`d74f883`) | Después |
|---|---|---|
| C-01 | Online con `observado_ate_utc = τ_0` exigía series realizadas inexistentes | k = 0 ⇒ válido para preparar la optimización (advertencia `nenhum_intervalo_observado`); k ≥ 1 y offline siguen exigiendo series coherentes |
| C-02 | No pasar de τ_k dependía de que faltaran datos en las series (y se rotulaba como inexequible) | Barrera del contrato en `executar` antes de cualquier `ExecutorPasso`; situaciones `pausada_aguardando_observacoes` (reanudable), `interrompida_inexequivel` y `erro_dados` (`PassoAplicado.falha`). Probado con un ejecutor que NO consulta el entorno |
| C-03 | Ruta sin hard link escribía directamente en el destino (lectura parcial posible) | Reserva `O_EXCL` + `os.replace` del temporal completo; reserva huérfana ⇒ `RegistroReservaOrfaError`. Lector concurrente: 17 097/89 053 lecturas parciales con el código anterior × 0/68 418 con la corrección |

Pruebas: `test_ems_v2_ponte_auditoria_pr13.py` 40 passed; 3A 268 y 3B-P 148 sin cambios; `tests/ems_v2` **535 passed**;
regresión completa **989 passed, 7 warnings, 128 subtests** (370 s) = 980 + 9. Limitaciones: Windows no ejecutado; recuperación manual de una reserva huérfana.
Detalle: `EVIDENCIA_3C0.md` §6, `PONTE_3C0.md` §9b.

### 7. Rollback

Revertir el PR elimina `ems_v2/ponte/`, `ems_v2/ponte_seeds2/`, `ems_v2/fixtures_3c0.py`, los tests
`test_ems_v2_ponte_*`, la documentación 3C-0 y el tipo `declarado_seeds2`; restaura la aserción original del test
3B-P. Nada en V1.6, en la aplicación ni en los bancos depende de ello.

---

## Entrega 9 — SEEDS2 Piso 3C-1 · EMS MILP V2: Unit Commitment dinámico, rampas, permanencias y memoria operativa

> Redactada en español. Detalle: `docs/ems_v2/FORMULACAO_3C1.md` (formulación, pruebas matemáticas, decisiones y
> contradicciones), `MATRIZ_3C1.md`, `EVIDENCIA_3C1.md`, `BRECHAS_3C1.md` y `TRANSICAO_3C1_3C2.md`.

### Punto de continuidad

| Campo | Valor |
|---|---|
| Rama | `claude/sweet-heisenberg-v0opgu` (desde `main`) |
| Base | `main` `81aa09cfb5ee4bd7ff66ec6eec8fa4ccc049fc44` (merge del PR #13); verificada idéntica a `origin/main` al iniciar |
| PR | [#14](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/14) contra `main`, **sin merge** |
| Pendientes | Auditoría del PR #14: A-01..A-03 (§5b), B-01/B-02 (§5c) y B-03 (§5d) corregidas; listo para la aprobación final de integración; hipótesis aceptadas provisionalmente para ensayos; **no iniciar 3C-2 sin autorización** |

### 1. Resumen

El MILP decide, **por unidad física** (`eq-…#k`), arranque, parada, permanencia, potencia y rampas con restricciones
temporales explícitas y verificables por un auditor independiente:

- **Perfil nuevo `v1.1-3C-1`** como contrato EMBRULHO (`ems_v2/compromisso/contrato.py`): base = `EntradaModeloEMS`
  3B-P intacta + rampas R⁺/R⁻, T_on/T_off, límites de arranque/parada (declarados o `R·Δ`), abstracción de transición,
  memoria (tiempo en el estado + obligación residual), política terminal de permanencia y término `eventos`.
  `contracts.py`, `audit.py`, `reference.py` y los archivos 3B-P de `ems_v2/milp/` **sin cambios byte a byte**;
  hashes 3A/3B-P idénticos; una `EntradaModeloEMS` no puede declarar 3C-1.
- **MILP** (`milp/modelo_3c1.py`, `solver_3c1.py`): reutiliza el constructor 3B-P, libera u y agrega M09 (y/z,
  y + z ≤ 1, u ≤ a), M11a/b con p_{−1} (tabla de exactitud por transición, sin Big-M), M12 con U/D = ⌈T/Δ⌉,
  obligaciones heredadas, política terminal y costos de evento (R$/evento, sin h). Lineal, sin SOS, sin holguras.
- **Auditor independiente** (`compromisso/auditor.py`, sin Pyomo ni `discretizar`): núcleo 3B-P reimplementado +
  M09–M12 (M12 en dos formas: sumas en ventana y longitud de corridas) + costos; rechaza soluciones adulteradas
  después de HiGHS; un resultado rechazado nunca se convierte en plan 3C-0.
- **Memoria y continuidad** (`ponte/compromisso.py`): plan 3C-1, ejecutor algébrico que rechaza transiciones contra
  la memoria, transporte de estado/memoria a la ventana siguiente, costo de eventos incurrido ≠ planificado.

### 2. Hallazgos relevantes

- Dos guardias de pisos anteriores impedían por construcción agregar el MILP 3C-1 (C-3C1-01): ajustadas
  nominalmente (solo **adiciones** en `ems_v2/milp`; todo archivo de la base sigue verificado sin cambios).
- Defecto latente del 3C-0 (C-3C1-02): la reinterpretación "Custo de partida" R$ ≡ R$/evento no pasa el verificador
  de cadena 3A al primer uso real; tratado solo en la proyección 3C-1 (3C-0/3A intactos).
- En la UI del Piso 1, "Rampa máxima" vacía significa "sin límite": el EMS V2 la trata como **faltante** (bloqueante).
- Caso D: el óptimo real (apagar en t = 0 y religar tras exactamente D = 3) era mejor que la expectativa inicial de la
  docstring; se corrigió la docstring (el modelo y el auditor coinciden con la enumeración manual de alternativas).

### 3. Validación (casos A–L) — ver `MATRIZ_3C1.md`

A transiciones · B rampa · C T_on · D T_off · E obligación heredada · F borde (dos políticas) · G unidades del mismo
bloque · **H óptimo idéntico a la enumeración exhaustiva independiente** (2⁸ programas × simplex racional exacto:
R$ 12,7, mismos u/y/z/p, segundo mejor R$ 14,7) · I inviabilidad verdadera sin holguras · J continuidad (ejecución
continua = partida por checkpoint; la memoria transportada admite exactamente la continuación del plan continuo) ·
K auditoría adversarial (14 adulteraciones sin solver + 4 tras HiGHS + constructor saboteado) · L retrocompatibilidad
(API 3B-P intacta; 3C-1 con estado mantenido reproduce el 3B-P en 6 fixtures).

### 4. Pruebas

| Ejecución | Resultado |
|---|---|
| `tests/ems_v2/test_ems_v2_3c1_*.py` (6 archivos) | **110 passed** (contrato 30, auditor 28, MILP 32, continuidad 7, puente 7, perfil 6) |
| `tests/ems_v2` con Pyomo/HiGHS | **645 passed** (= 535 anteriores + 110) |
| `tests/ems_v2` con Pyomo/HiGHS bloqueados | **463 passed, 9 skipped** (omitidos explícitamente) |
| Suite completa `tests/` | **1099 passed, 7 warnings, 128 subtests** (503 s) = 989 de `main` + 110 |

Comandos, entorno, tiempos (indicativos) y tabla de evidencia: `EVIDENCIA_3C1.md`.

### 5. Decisiones y contradicciones

D-3C1-01..10, C-3C1-01 y C-3C1-02 en `FORMULACAO_3C1.md` §9. Requieren conocimiento del auditor en especial:
D-3C1-02 (S := R·Δ cuando solo hay rampa), D-3C1-03 (transición no representable ⇒ bloqueada), D-3C1-05 (obligación =
derivada), D-3C1-06 (dos políticas terminales sin defecto), D-3C1-08 (PEMFC instantánea solo como abstracción) y
D-3C1-09 (rampa única ⇒ R⁺ = R⁻).

### 5b. Cierre de la auditoría independiente del PR #14 (base `540ac1b`: arquitectura, M09–M12 y auditor aprobados)

| ID | Antes (`540ac1b`, reproducido) | Después |
|---|---|---|
| A-01 | El ejecutor 3C-1 omitía la verificación de disponibilidad del generador si la observación no existía (ON ejecutado); 0,5 se rotulaba como inviabilidad física | `FonteDisponibilidadeExecucao` obligatoria por unidad (`observada` × `estatica_declarada` con procedencia y justificativa); ausente/inválida/contradictoria/de otro recurso ⇒ `erro_dados`; efectiva 0 con ON ⇒ `inexequivel`; sin defecto 1 |
| A-02 | El H₂ de arranque/parada estaba en el objetivo pero no en la contabilidad realizada (R$ 0,30 en vez de R$ 0,33) | `contabilidade_realizada_3c1`: 3C-0 sin cambios (base + H₂ continuo) + c_H·(m_SU·partidas + m_SD·paradas) y C_SU/C_SD de las transiciones APLICADAS; parcial/interrumpida solo lo aplicado; sin doble conteo; sellable en el registro; valor futuro separado |
| A-03 | Declaraciones por unidad indexadas antes de validar: duplicata contradictoria sobrescribía en silencio; UID desconocido ignorado | Validación previa: duplicatas (aun idénticas), UID ajenos (otra microrred, inexistente, `#k` fuera de rango, registro de bloque), procedencia/unidad/dominio; declaración vinculada a microrred y escenario; origen de la condición en la procedencia |

Pruebas: `test_ems_v2_3c1_auditoria_pr14.py` **36 passed**; casos A–L (110) sin cambios de aserciones; `tests/ems_v2`
**681 passed** (sin Pyomo: 494 passed, 14 skipped); suite completa **1135 passed, 7 warnings, 128 subtests** (435 s) = 1099 + 36. Guardias C-3C1-01, hashes 3A/3B-P y
ausencia de cambios en V1.6/3A/3B-P/3C-0 verificados de nuevo (mismos tests). Detalle: `FORMULACAO_3C1.md` §9b,
`EVIDENCIA_3C1.md` §2 y §6, `MATRIZ_3C1.md`.

### 5c. Segunda auditoría del PR #14 (base `20243aa`: A-01, A-02 y el rechazo de duplicados/UID de A-03 aprobados)

| ID | Antes (`20243aa`, reproducido) | Después |
|---|---|---|
| B-01 | Bloque q = 2 con `unidades_ligadas = 1` y dos unidades ON declaradas, o potencia del registro 10 kW con Σ por unidad 25 kW: **aceptados** | `coerencia_agregado_unidades` antes de proyectar: cantidad ON, estado discreto y potencia del registro (tolerancia D07); `unidades_ligadas_incoerente`, `estado_agregado_incoerente`, `potencia_agregada_incoerente`; agregado no declarado no se infiere; nada se reparte |
| B-02 | Declaración de la versión 1 aplicada a la versión 2 del mismo escenario, o a otra revisión del inventario: **aceptada**; la fuente de disponibilidad estática no quedaba en la evidencia | `VinculoDeclaracao3C1` (reutiliza `ReferenciaInventario` + versión/impresión del escenario) con igualdad exacta; `hash_declaracao` en la procedencia de la entrada; `ponte/registro_3c1.py`: hashes 3C-1 en `RegistroExecucaoEMS.hashes` (esquema 3C-0 intacto) + `AnexoExecucao3C1` sellado con el CONTENIDO (fuentes, declaración, disponibilidad efectiva por paso, H₂ por unidad), verificable contra el registro |

Pruebas: `test_ems_v2_3c1_auditoria_pr14_b.py` **18 passed**; A-01/A-02/A-03 (36) y casos A–L conservados;
`tests/ems_v2` **699 passed** (sin Pyomo: 509 passed, 17 skipped); suite completa **1153 passed, 7 warnings, 128 subtests** (429 s) = 1135 + 18. Detalle:
`FORMULACAO_3C1.md` §9c, `EVIDENCIA_3C1.md` §2 y §7, `MATRIZ_3C1.md`.

### 5d. Corrección final B-03 (base `1b953db`: B-01 y vinculación de revisiones B-02 aprobadas)

| Antes (`1b953db`, reproducido) | Después |
|---|---|
| El registro solo comprometía fuentes, declaración y entrada: un anexo con `disponibilidade_efetiva`, `detalhe_h2` o `eventos_aplicados` alterados y re-sellado era **aceptado** | `ConteudoAnexo3C1` (payload verificable, sin vinculación ni sellos) con `anexo_3c1_conteudo = SHA-256` en `RegistroExecucaoEMS.hashes` antes de sellar el registro (esquema 3C-0 intacto); tres fases para resolver la dependencia circular; verificación conjunta con `verificar_registro`, compromiso recalculado, hashes B-02 y coherencia con los metadatos del registro (ejecución, entrada, unidades, pasos, paridad de eventos, H₂ del costo realizado, origen de la declaración). SHA-256 declarado como detección de alteración frente a una referencia confiable, **no** firma |

Pruebas: `test_ems_v2_3c1_auditoria_pr14_c.py` **18 passed** (13 adulteraciones re-selladas rechazadas); A-01..A-03,
B-01/B-02 y casos A–L conservados (182 tests 3C-1); `tests/ems_v2` **717 passed** (sin Pyomo: 509 passed, 18 skipped);
suite completa **1171 passed, 7 warnings, 128 subtests** (432 s) = 1153 + 18. Detalle: `FORMULACAO_3C1.md` §9d, `EVIDENCIA_3C1.md` §2 y §8, `MATRIZ_3C1.md`.

### 6. Rollback

Revertir el PR elimina `ems_v2/compromisso/`, `ems_v2/milp/*_3c1.py`, `ems_v2/ponte/compromisso.py`,
`ems_v2/fixtures_3c1.py`, los tests `test_ems_v2_3c1_*` y `enumeracao_3c1.py`, las columnas 3C-1 del catálogo,
`CAPACIDADES_3C1`, los parámetros aditivos de `requisitos`/`projecao`/`preflight` (por defecto inactivos) y restaura
las dos guardias. Nada en V1.6, en la aplicación ni en los bancos depende de ello.

---

## Entrega 10 — SEEDS2 Piso 3C-2 · MPC de horizonte recedente (M23), K6 y primer lazo cerrado reproducible

> Redactada en español. Detalle: `docs/ems_v2/FORMULACAO_3C2.md` (M23, política de información, decisiones D-3C2-*,
> contradicciones C-3C2-*), `MATRIZ_3C2.md`, `BRECHAS_3C2.md`, `TRANSICAO_3C2_3C3_3C4.md`, `EVIDENCIA_3C2.md` y
> `EVIDENCIA_3C2_EJECUCION.md`. Este apartado resume y remite.

### Punto de continuidad

| Campo | Valor |
|---|---|
| Rama | `ccr-2529baa8-16lz1j` (desde `main`) |
| Base | `main` `55440f4bda17ec2b14cdf4235bdb924bf97159b0` (merge del PR #14, 3C-1 integrado); verificado idéntico a `origin/main` al iniciar |
| PR | [#15](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/15) contra `main`, **sin merge** (entregado para auditoría independiente) |
| Pendientes | Correcciones C-01/C-02 de la auditoría del PR #15 aplicadas (§5b); aprobación final; decisiones D-3C2-01..13 y contradicciones C-3C2-01..05 a revisión; **no iniciar 3C-3/3C-4 sin autorización** |

### 1. Resumen

Primer lazo cerrado MPC de SEEDS2, **simulación causal algebraica** (planta = dublé 3C-1), en `ems_v2/mpc/` (núcleo
solo biblioteca estándar; el solver se alcanza solo por el adaptador explícito `adaptador_milp.ResolvedorMILP3C1` →
`resolver_3c1`, import tardío):

- **Contratos temporales** (`contrato`, `relogio`): `MalhaTemporal` reutilizada (Δ, N, m, K_M, H_f obligatorio),
  ventanas τ_k/N_k/m_k (último bloque < m), contador global monotónico, política terminal **declarada**
  (`janela_reduzida` × `horizonte_estendido_declarado` con cobertura posmisión verificada) y política de permanencia
  intermedia/final; obligaciones al final **reportadas** (nunca desaparecen).
- **K6** (`observacoes`): libro append-only por recurso/magnitud con tiempo físico × recepción, evento, secuencia,
  revisiones, conflictos (clave conflictiva), duplicados, fuera de secuencia, otra microrred, inválidas (incl. recibida
  antes del fin del intervalo), cadena SHA-256, cortes sellados (recepción retroactiva rechazada) e instantáneo
  informacional = prefijo comprometido.
- **Previsión por ventana** (`previsao`, `provedores`): pedido solo con el instantáneo; validación causal 3C-0 +
  claves exactas + **vínculo informacional** (sha256 del instantáneo) + oráculo solo en ablación + independencia del
  proveedor; proveedores sintéticos (tabla declarada; corrección por la última observación) y oráculo rotulado.
- **Orquestador** (`orquestrador`): decidir → emitir comandos → recibir confirmaciones/observaciones → conciliar con
  `executar`/`retomar` 3C-0 y el ejecutor 3C-1 (barrera **C-02 intacta**; modo 2 pausa y reanuda desde el checkpoint)
  → cerrar. Estado y memoria **ejecutados** transportados (nunca el terminal planificado). Aceptación con política
  explícita (no óptimo solo con gap/terminación declarados); fallas clasificadas (14 clases) con
  `interromper`/`suspender`; sin despacho de reserva ni reutilización del plan anterior.
- **Registros** (`registro`, `persistencia`): por ventana, registro 3C-0 + anexo 3C-1 (esquemas intactos) +
  `RegistroJanelaMPC` determinista encadenado (contenido, sellos, vínculo explícito al checkpoint anterior);
  `RegistroMissaoMPC` con costo realizado acumulado (sin doble conteo), obligaciones pendientes, valor futuro no
  implementado e impresión determinista; gravación exclusiva/atómica y `PontoRetomada` sellado con reanudación
  verificada.
- **Auditoría independiente** (`auditoria`): temporal, causal (instantáneos recalculados del libro), estado (M07,
  memoria, permanencias en toda la misión), balance, costos recomputados, aceptación, separación previsión ×
  realización y **no anticipatividad por intervención**. **Métricas** y **comparadores** con condiciones comparables y
  sin veredicto.

### 2. Hallazgos relevantes

- **C-3C2-01 (incompatibilidad no ocultada):** el ejecutor 3C-0/3C-1 exige balance exacto con la demanda realizada y no
  hay recurso de equilibrio; en lazo cerrado cualquier error de demanda (o sobreestimación renovable) en un intervalo
  aplicado vuelve la consigna inexequible ⇒ interrupción clasificada (sin recorte ni contingencia). Los experimentos
  usan errores absorbibles (subestimación FV ⇒ vertimiento). Requiere recurso de equilibrio declarado (3C-3/3D).
- **C-3C2-02:** con horizonte extendido, la entrada de la ventana declara `intervalos_missao = N_k` (3A intacto).
- Miopía documentada: sin valor terminal el MPC drena el banco en cada ventana (E2/E4); E4 m = 1 termina con la PEMFC
  arrancada en el último intervalo y 1800 s de obligación pendiente reportada.
- Límite de confianza: un proveedor malicioso con referencia oculta a la verdad pasa las verificaciones estructurales
  en ejecución; la intervención lo detecta (test con fuga deliberada).

### 3. Experimentos (fixtures sintéticas; ver `EVIDENCIA_3C2_EJECUCION.md`)

| Exp. | Resultado |
|---|---|
| E1 oráculo (ablación) | MPC N = 4/m = 2 y horizonte completo: R$ 2,075 ambos (referencia, excluida de comparaciones causales) |
| E2 previsión reemitida | FV prevista 10 → 25 tras observar el escalón; R$ 12,9 = cálculo a mano por ventana (1,7 / 2,0 / 6,125 / 3,075) |
| E3 open-loop × MPC | OL R$ 18,7 (E_final 0 kWh) × MPC R$ 12,9 (E_final 2,5 kWh; obligación 900 s pendiente) — sin veredicto |
| E4 m ∈ {1, 2, 4} | R$ 7,2625 / 12,9 / 12,9 con 8 / 4 / 2 resoluciones |
| E5 memoria | u = [0,0,0,1,1,1,0,0]: T_on (U = 3) cumplido a través de 3 ventanas N = 2; memoria descartada ⇒ planta rechaza |
| E6 batería | Ventana 0 planifica e_N = 0; ejecutado en τ_2 = 10 kWh inicia la ventana 1; SOC ∈ [0, 1] |
| E7 fallas | Sin solución / excepción / rechazo del auditor ⇒ ningún comando; no óptimo solo con política |
| E8 tardías | Revisión tras τ_2 no altera instantáneo ni plan de τ_0/τ_2; `interromper` ⇒ parada en τ_4; modo 2 pausa C-02 y reanuda |

### 4. Pruebas

| Ejecución | Resultado |
|---|---|
| `tests/ems_v2/test_ems_v2_3c2_*.py` (6 archivos) | **83 passed** (contrato 19, observaciones 8, previsión 7, lazo sin solver 16, MILP 29, aislamiento 4) |
| `tests/ems_v2` con Pyomo/HiGHS | **800 passed** (= 717 anteriores + 83) |
| `tests/ems_v2` con Pyomo/HiGHS bloqueados | **563 passed, 19 skipped** (solo el archivo MILP 3C-2 se salta; el lazo sin solver corre) |
| Suite completa `tests/` | **1254 passed, 7 warnings, 128 subtests** (378,9 s) = 1171 de `main` + 83 |

Comandos, entorno y tiempos: `EVIDENCIA_3C2.md`.

### 5. Decisiones y contradicciones

D-3C2-01..13 y C-3C2-01..05 en `FORMULACAO_3C2.md` §8–§9. Requieren conocimiento del auditor en especial: D-3C2-01
(corte inclusivo), D-3C2-05 (estado = propagación algebraica con confirmación + observación), D-3C2-06 (modo 1 sin
decisión tardía), D-3C2-08 (costo planificado del prefijo) y C-3C2-01 (sin recurso de equilibrio).

### 5b. Auditoría independiente del PR #15 (base `d97f831`): correcciones C-01 y C-02

Arquitectura aprobada provisionalmente (ciclo de ventanas, reutilización 3C-1, transporte del estado ejecutado,
contabilidad, limitaciones documentadas). Ambos defectos fueron **reproducidos antes de corregir**:

| ID | Antes (`d97f831`, reproducido) | Después |
|---|---|---|
| C-01 | Un evento **rechazado** con recepción 45 min posterior a τ_2 entraba en el prefijo de τ_2 (n = 2; hash dependiente), el corte τ_2 se sellaba y la auditoría causal no detectaba nada | Libro principal con marca de agua sobre TODA entrada (cualquier clasificación) y recepciones no decrecientes; **cuarentena** append-only con cadena propia para recepciones retroactivas/ilegibles (sin hora inventada; nunca en un prefijo causal); corte imposible con recepción posterior registrada; I_k = prefijo con recepción ≤ τ_k; auditoría temporal de todas las entradas del prefijo y de cada conciliación; `verificar_cadeia_livro` verifica orden y cortes; la misión compromete la cadena de cuarentena (libro esquema v2) |
| C-02 | Reanudación aceptada con registro 3C-0 eliminado/alterado o anexo 3C-1 eliminado; históricos 0/0 | `verificar_artefatos_janela` por ventana ejecutada (`execucao_uid` determinista en `ConteudoJanelaMPC`): `verificar_registro`, `verificar_anexo_3c1`, sellos referenciados, identidad/misión/posición, ventana, plan, entrada, estados, checkpoint, previsión, instantáneo, costo e intervalos; ventana sin plan no exige artefactos; libro del punto de retomada × instantáneos comprometidos; `ContratoInvalido` estructurado; históricos `registros_3c0`/`anexos_3c1` restaurados |

Pruebas: `test_ems_v2_3c2_auditoria_pr15.py` **24 passed**; 3C-2 completo **107 passed** (83 + 24); `tests/ems_v2`
**824 passed** (sin Pyomo: 587 passed, 19 skipped); suite completa **1278 passed, 7 warnings, 128 subtests** (384,3 s) = 1254 + 24. E1–E8 repetidos con resultados
idénticos. Modelo físico, solver y políticas económicas sin cambios; 3A/3B-P/3C-0/3C-1/V1.6 intactos (guardia).
Nueva brecha B3C2-13 (tiempo de ingestión confiable). Detalle: `FORMULACAO_3C2.md` §4 y §10, `MATRIZ_3C2.md`,
`EVIDENCIA_3C2.md` §5b.

### 6. Rollback

Revertir el PR elimina `ems_v2/mpc/`, `ems_v2/fixtures_3c2.py`, los tests `test_ems_v2_3c2_*` y `mpc_util.py` y los
documentos 3C-2. Ningún archivo existente de `ems_v2`, V1.6, `seeds2`, aplicación ni requirements fue modificado
(guardia `test_pisos_anteriores_v16_e_aplicacao_sem_alteracao_desde_o_merge_do_pr14`).

---

## Entrega 11 — SEEDS2 Piso 3C-3 · Red eléctrica, intercambio económico y recurso explícito de equilibrio

> Redactada en español. Detalle: `docs/ems_v2/FORMULACAO_3C3.md` (formulación, ejecución programado × realizado,
> decisiones D-3C3-*, contradicciones C-3C3-*), `MATRIZ_3C3.md` (trazabilidad + hashes protegidos), `BRECHAS_3C3.md`,
> `TRANSICAO_3C3_3C4.md` y `EVIDENCIA_3C3_EJECUCION.md`. Este apartado resume y remite.

### Punto de continuidad

| Campo | Valor |
|---|---|
| Rama | `ccr-a53cad36-86uep6` (desde `main`) |
| Base | `main` `a4c6b1c1a5e9be86b7b20556f91ec3a753dfb225` (merge del PR #15, 3C-2 integrado) |
| PR | [#16](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/16) contra `main`, **sin merge** (entregado para auditoría independiente) |
| Pendientes | Correcciones C-01/C-02 (§4b) y C-03 (§4c) de la auditoría del PR #16 aplicadas; aprobación final; **no iniciar 3C-4 sin autorización** |

### 1. Resumen

Perfil **`v1.1-3C-3`** (embrulho `EntradaRede3C3` sobre el núcleo 3C-1 validado sin relajación), modelo
**algebraico agregado** del Punto de Acoplamiento Común (no flujo AC, no control primario, tarifas sintéticas):

- **Contratos** (`ems_v2/rede/contrato.py`): PCC versionado (modo `conectado` × `isolado_declarado`, sentidos
  permitidos, límites contratados por intervalo, disponibilidad binaria, medidores) — sin defectos: PCC ausente ≠
  ilimitado, capacidad cero ≠ intercambio; perfiles tarifarios por bloques (naturaleza contractual/prevista/liquidación,
  revisión, emisión, regla del bloque que contiene el intervalo, hash, precio desconocido explícito); política
  económica (importación exige tarifa; exportación exige remuneración declarada); selección causal de la revisión
  vigente en τ_k.
- **MILP** (`ems_v2/milp/*_3c3.py`): composición sobre el constructor 3C-1 **inalterado**; exclusividad por binaria
  con coeficientes = límites contratados (sin Big-M arbitrario); M02 extendido reconstruido y **verificado término a
  término** contra el M02 del núcleo; objetivo + gasto de importación − crédito de exportación; isolado ⇒ modelo
  idéntico al 3C-1.
- **Auditor independiente** (`rede/auditor.py`): auditor 3C-1 completo + sustitución SOLO del balance (con PCC) +
  familias del PCC y costos de red con alineación propia; "optimal" nunca basta.
- **Ejecución** (`rede/execucao.py`): intercambio **programado** (plan de red ligado al plan) × **realizado** × desvío;
  política de ajuste declarada (`sem_ajuste` × `ajuste_local_algebrico`), inyección renovable limitada por el potencial
  observado (desvío físico registrado; exceso no inyectado), saturación/sentido prohibido/PCC indisponible ⇒ falla
  clasificada sin respaldo oculto; liquidación realizada (`energia_medida_tarifa_aplicavel` × `desvio_diferenciado`).
- **MPC conectado** (`rede/mpc.py`): punto de extensión mínimo auditado — 11 métodos del orquestrador 3C-2 con la
  implementación 3C-2 por defecto (E1–E8 idénticos a la base); `ControladorMPCConectado` solo los sobrescribe:
  tarifas causales por ventana, comandos con intercambio programado, medición del PCC obligatoria en la conciliación
  (evidencia del ajuste), anexo 3C-3 sellado, vínculo de red por punto de retomada, registro de misión de red;
  planta conectada; retomada verificada (`rede/persistencia.py`); auditoría de misión compuesta (`rede/auditoria.py`);
  comparador con condiciones de red (`rede/comparadores.py`).

### 2. Hallazgos relevantes

- **C-3C3-01:** el contrato 3A solo admite topología "isolada"; en 3C-3 se lee como bus interno y el PCC vive solo en
  el embrulho (contrato 3A intacto).
- **C-3C3-02:** tres guardias anteriores impedían el 3C-3 por construcción; ajuste nominal mínimo (`ADICOES_3C3`,
  única modificación `ems_v2/mpc/orquestrador.py`) + nueva guardia desde `a4c6b1c`.
- **C-3C3-04:** con exportación prohibida y excedente realizado ningún recurso declarado lo absorbe ⇒ falla
  clasificada (FV nunca recortada sin política).
- El recurso de equilibrio cierra B3C2-01 para errores absorbibles por el PCC: G5–G7 y G11 completan con desvíos
  registrados; G8 (saturación) y G6 sin exportación se detienen de forma segura.

### 3. Experimentos (sintéticos; `EVIDENCIA_3C3_EJECUCION.md`)

| Exp. | Resultado |
|---|---|
| G1–G4 | importa 20 kW exactos (R$ 8,0); exporta 20 kW (−R$ 3,0 remunerada / R$ 0 sin remuneración declarada); exportación prohibida ⇒ carga/vierte (R$ 0,875); PCC indisponible ⇒ inviable sin banco / sin intercambio con banco |
| G5–G8 | +4 kW ⇒ 24 vs 20 programados (R$ 12,6); −4 kW ⇒ 16 (R$ 11,4); 5 kW ⇒ exporta 5 (R$ 8,75) o interrumpe si exportación prohibida; FV 4 kW ⇒ inyección 4, PCC 26 (R$ 12,9); saturación ⇒ `consigna_inexequivel` en k = 1 |
| G9, G10 | perfiles distintos ⇒ decisiones intercambiadas (R$ 1,25 ambos); arbitraje: sin exclusividad −10, w relajado −5, MILP 0 sin flujo simultáneo |
| G11 | 4 ventanas, demanda/FV perturbadas, previsión reemitida, revisión tarifaria usada solo desde su emisión (τ_4), auditoría aprobada, reproducción determinista |
| G12 | conectado × isolado: mismo costo sin error (R$ 16,7; conectado con 900 s de obligación pendiente); con error de demanda el isolado se interrumpe y el conectado concluye — contraste de topología, no superioridad |
| G13 | interrupción + retomada ⇒ impresión, totales y anexos idénticos; adulteración/otro modelo/otra política ⇒ rechazo |
| G14 | P_imp, costos, flujos simultáneos, disponibilidad, tarifa, liquidación, intercambio registrado y disponibilidad observada adulterados ⇒ rechazados |
| G15 | E1–E8 del 3C-2 idénticos (12 misiones, igualdad exacta con los pins de la base) |
| §13 | open-loop R$ 20,95 × MPC R$ 15,9 con E_final 0 kWh y obligaciones 0 s en ambos — una instancia sintética, sin afirmación general |

### 4. Pruebas

| Ejecución | Resultado |
|---|---|
| `tests/ems_v2/test_ems_v2_3c3_*.py` (6 archivos) | **79 passed** (contrato 15, ejecución 15, MILP 15, MPC 18, G15 13, aislamiento 3) |
| `tests/ems_v2` con Pyomo/HiGHS | **903 passed** (= 824 anteriores + 79) |
| `tests/ems_v2` con Pyomo/HiGHS bloqueados | **620 passed, 22 skipped** |
| Suite completa `tests/` | **1357 passed, 7 warnings, 128 subtests** (370,8 s) = 1278 de `main` + 79 |

Hashes de los perfiles protegidos y conteo de módulos idénticos: `MATRIZ_3C3.md`.

### 4b. Auditoría independiente del PR #16 (commit auditado `d7da6c5`): correcciones C-01 y C-02

Aprobados estructuralmente el MILP del PCC, la exclusividad, la integración MPC por puntos de extensión, la contabilidad
y el aislamiento. Ambos defectos fueron **reproducidos sobre `d7da6c5` antes de corregir** (salida literal en
`EVIDENCIA_3C3_EJECUCION.md` §7):

| ID | Antes (reproducido) | Después |
|---|---|---|
| C-01 | `P_imp = NaN` ⇒ `PassoAplicado` exequible (NaN aplicado en `sem_ajuste`; `abs(a − b) > tol` no detecta NaN); consigna parcial ignorada con programa; `plano_de_resultado_3c3` recortaba `max(0, v)` (−3 ⇒ 0; NaN ⇒ 0) | Programado validado ANTES de toda operación física/económica: real finito ≥ 0 (sin bool/texto/NaN/Inf/negativos, sin recorte ni conversión); ambas consignas o ninguna; comando = programa (igualdad exacta); programa explícito validado al construir; caso legítimo "solo programa" (conciliación) preservado; defecto ⇒ falla de **datos** (`erro_dados`) en el ejecutor y de **integridad** en el plan; nunca `PassoAplicado` exitoso |
| C-02 | `auditar_missao_conectada` sin anexos/registros 3C-0/registro de red ⇒ `aceito = True`; modelo PCC con límites más amplios y política económica sustituida ⇒ aceptados | Escopos explícitos: **integral** (artefactos obligatorios; verificación por posición de registro 3C-0 + anexo 3C-3 de cada ventana ejecutada con el verificador puro compartido con la retomada; `RegistroMissaoRede3C3` y su vínculo; `hash_modelo_3c3`/`hash_configuracao_rede` contra los objetos suministrados) × **analítica parcial** rotulada (`integridade_documental_certificada = False`) |

Evidencia adversarial después (auditoría integral sobre G11): válida ⇒ aceptada; sin anexos / sin registros 3C-0 /
sin registro de red / registro de otra ventana / anexo alterado y resellado / sello de ventana distinto / evidencias de
dos ventanas intercambiadas / PCC con P̄_imp + 10 kW (mismo núcleo) / configuración de red sustituida con los mismos
costos ⇒ **rechazadas con balance y costos numéricamente correctos**; ventana sin plan ⇒ aceptada sin artefactos.

| Ejecución | Resultado |
|---|---|
| `test_ems_v2_3c3_auditoria_pr16.py` | **132 passed** (C-01: 120; C-02: 12) |
| 79 tests 3C-3 originales (incl. G15 13) | **79 passed** |
| `tests/ems_v2` | **1035 passed** (= 903 + 132); sin Pyomo/HiGHS: **736 passed, 38 skipped** |
| Suite completa `tests/` | **1489 passed, 7 warnings, 128 subtests** (375,0 s) = 1357 + 132 |
| Perfiles protegidos | 65/66 módulos `ems_v2` de `a4c6b1c` idénticos (git blob); solo `mpc/orquestrador.py` (refactorización ya auditada); V1.6/`seeds2`/aplicación/requirements sin diff |

G1–G15 regenerados (`EVIDENCIA_3C3_EJECUCION.md`) con los mismos valores; E1–E8 idénticos a la base.

### 4c. Corrección final C-03 (commit auditado `7b8da5d`: C-01 y C-02 aprobados)

**Antes (reproducido sobre `7b8da5d`):** un `RegistroMissaoRede3C3` re-sellado con `totais = {}`, esquema 99, perfil
`v1.1-3C-1` o sin una métrica pasaba `verificar_registro_rede` **y** la auditoría integral (`aceito = True`); una
métrica extra solo fallaba con valor ≠ 0; `finalizar()` leía métrica ausente como 0.

**Después:** esquema/perfil/rótulo exactos; las 9 métricas de `METRICAS_REDE` obligatorias (ausente ⇒ rechazo, nunca
cero), métricas inesperadas rechazadas aun valiendo 0, valores reales finitos e iguales (exactos) a los impuestos por
el registro de misión (`totais_rede_esperados`: ausencia con intervalos aplicados ⇒ inconsistencia; 0 solo derivado de
`intervalos_aplicados = 0`); `finalizar` usa la misma regla; NaN/Inf en memoria ⇒ rechazo, no excepción. Ceros exactos
válidos (misión isolada) y misión sin intervalos aplicados siguen aceptados. Detalle: `FORMULACAO_3C3.md` §10c;
antes × después: `EVIDENCIA_3C3_EJECUCION.md` §7b.

| Ejecución | Resultado |
|---|---|
| `test_ems_v2_3c3_auditoria_pr16_c03.py` | **45 passed** |
| Todos los tests 3C-3 (79 + 132 + 45) | **256 passed** |
| E1–E8 (G15) | **13 passed**, impresiones idénticas a la base |
| `tests/ems_v2` | **1080 passed** (= 1035 + 45); sin Pyomo/HiGHS: **736 passed, 39 skipped** |
| Suite completa `tests/` | **1534 passed, 7 warnings, 128 subtests** (375,1 s) = 1489 + 45 |
| Perfiles protegidos | 65/66 módulos `ems_v2` de `a4c6b1c` idénticos (solo `mpc/orquestrador.py`, ya auditado); V1.6/`seeds2`/aplicación/requirements sin diff |

### 5. Rollback

Revertir el PR elimina `ems_v2/rede/`, `ems_v2/fixtures_3c3.py`, `ems_v2/milp/*_3c3.py`, los tests
`test_ems_v2_3c3_*`, `tests/ems_v2/dados/` y los documentos 3C-3, y restaura `ems_v2/mpc/orquestrador.py` y las tres
guardias. V1.6, `seeds2`, aplicación y requirements no fueron tocados.

---

## Histórico de entregas

| Entrega | Data | Missão | Rama / PR | Estado |
|---|---|---|---|---|
| 1 | 2026-11-06 | Piso 2A — Centro de Operação (fundação operacional) | `claude/seeds2-piso2a-centro-operacao` / [#6](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/6) | **Integrado** em `main` (merge `4709f0c`), após auditoria favorável e correção C-01 (§15) |
| 2 | 2026-11-06 | Piso 2B — Previsões e Dados | `ccr-68eaae98-0rs4e4` / [#7](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/7) | **Integrado** em `main` (merge `43ee6f5`) |
| 3 | 2026-11-06/07 | Piso 2C — Execução EMS e Persistência Científica (+ correção de auditoria C-02, §17) | `ccr-21b1e00e-u5u64z` / [#8](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/8) | **Integrado** em `main` (merge `34a8b52`), após auditoria favorável e correção C-02 |
| 4 | 2026-11-07 | Piso 2D-A — Arquivo Científico Portátil (+ correção C-03) | `ccr-dea994b8-wl7tp3` / [#9](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/9) | **Integrado** em `main` (merge `3b73971`) |
| 5 | 2026-11-07 | Piso 2D-B — Relatórios Científicos, Excel e Figuras (+ correção de auditoria C-04, §21) | `claude/seeds2-piso2db-relatorios-9k1qph` / [#10](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/10) | **Integrado** em `main` (merge `8556b71`) |
| 6 | 2026-11-08 | Piso 3A — Fundações do EMS MILP–MPC (contratos, referência, auditor; sem solver) | `ccr-fb5b5eb8-bvbyw2` / [#11](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/11) (sem merge) | **Integrado** em `main` (merge `f6d009d`), após auditoria favorável e correções C-3A-01..04 |
| 7 | 2026-11-08 | Piso 3B-P — Primeiro MILP executável (Pyomo + HiGHS), uma janela, sem integração | `claude/seeds2-piso3b-milp-highs` / [#12](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/12) | **Integrado** em `main` (merge `3c65d98`), após correções C-3B-01..03 |
| 8 | 2026-11-08 | Piso 3C-0 — Ponte científica EMS MILP ↔ microrredes (contratos, sem integração) | `ccr-0cc9677c-ydyfl7` / [#13](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/13) | **Integrado** em `main` (merge `81aa09c`), após H-01..H-04 (§6b) e C-01..C-03 (§6c); C-3C0-01 aceita condicionalmente |
| 9 | 2026-11-09 | Piso 3C-1 — Unit Commitment dinâmico (M09–M12), rampas, permanências e memória operativa | `claude/sweet-heisenberg-v0opgu` / [#14](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/14) | **Integrado** em `main` (merge `55440f4`), após correções A-01..A-03 (§5b), B-01/B-02 (§5c) e B-03 (§5d) |
| 10 | 2026-11-09 | Piso 3C-2 — MPC de horizonte recedente (M23), K6 e primeiro laço fechado reproduzível (algébrico) | `ccr-2529baa8-16lz1j` / [#15](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/15) (sem merge) | **Integrado** em `main` (merge `a4c6b1c`), após correções C-01/C-02 (§5b) |
| 11 | 2026-11-09 | Piso 3C-3 — Red eléctrica, intercâmbio econômico e recurso explícito de equilíbrio (PCC, tarifas, MPC conectado algébrico) | `ccr-a53cad36-86uep6` / [#16](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/16) (sem merge) | Auditoria: aprovação estrutural; correções C-01/C-02 (§4b) e C-03 (§4c) aplicadas; aguardando aprovação final |
