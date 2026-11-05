# CLAUDE.md — SEEDS2 v2.0 (Piso 1) sobre Energy MultiModel V1.6

Aplicação Streamlit para modelos energéticos (Solar, Eólica, Térmica, Bateria, H₂/PEMFC) integrados a um EMS de despacho ótimo. Projeto SEEDS2. **Uma instalação do SEEDS2 administra uma única microrrede** (sem projetos, seletor de microrredes ou multi-inquilino).

## Arquitetura

- `app.py` — ponto de entrada (`python -m streamlit run app.py`). Roteia por `st.session_state["energy_source"]`: `None` → shell SEEDS2 (`seeds2/ui/main.py`); `"solar"|"wind"|"thermal"|"battery"|"h2"|"mix"` → bancada individual; `"ems"` (sessão legada V1.5) → volta ao shell. `legacy_css()` (CSS V1.6) só é aplicado às telas V1.6. A UI solar está no próprio `app.py`.
- `seeds2/` — Piso 1 (sem ciência): `microgrid/` (`references.py` leitura dos catálogos, `config.py` documento v2/validação, `migrations.py` migração versionada do documento, `derived.py` estimativas nominais FV/bateria, `modellab.py` importação validada do PEMFC ModelLab, `store.py` SQLite em `SEEDS2_DATA_DIR`, `adapter.py` inventário → `model_spec` V1.6), `report/pdf.py` (relatório técnico PDF local) e `ui/` (shell, comissionamento, Gestão, diálogo de equipamentos `equipment.py`, exportações `exports.py`, ponte `operations.py` com o console V1.6, componentes `st.components.v2` em `ui/static/`). Detalhes: `docs/seeds2/ARQUITETURA_PISO1.md`, `docs/seeds2/ARMAZENAMENTO.md`.
- Navegação SEEDS2: Comissionamento (1º acesso) → Início · Gestão da Microrrede · Simulação · Resultados · Alcance. Simulação/Resultados renderizam o console V1.6 com a configuração **salva** transferida pelo adaptador.
- `orchestrator_app.py` — console V1.6 (UI). Páginas: Visão Geral → Módulo de Carga → Modelos → Otimizador → Resultados do Otimizador → Resultados dos Modelos → Exportar Resultados. Bancadas individuais: página **Modelos** (expander) e Início (expander). Respeita `orq_run_gate`, grava `origem` na rodada e chama `orq_after_run` (registro de procedência).
- `orchestrator_runtime.py` — integração sem UI: modelos físicos → pacote de troca → EMS.
- `*_app.py` (`wind_app`, `thermal_app`, `battery_app`, `h2_app`, `mix_app`) — UIs das bancadas. `ems_app.py` é legado, não roteado.
- **Modelos científicos**: `models/` (FV: `irradiance_model`, `temperature_model`, `single_diode`, `pv_module`; `wind_model`; `thermal_model`; `battery_model`), `h2_pemfc/` (stack, balance of plant, dinâmica), `simulation/` (`multimodel`, `solver`, `mpp`, `mix_engine`, `orchestrator_demo`), `config/` (bancos de dados de equipamentos).
- **EMS / otimizador**: `ems_integration/` — `despacho.py` (custo, restrições, receding horizon, refino SLSQP), `metaheuristicas.py` (GA/GWO/NGO), `fontes.py`, `contrato.py`, `ponte.py` (plataforma → CSV do EMS), `executor.py`.
- `reference_models/` — protótipos MATLAB originais (referência; não executados).
- `visualization/` — gráficos Plotly. `Dados_exemplo/` — CSVs de exemplo.

## Testes

```bash
pip install -r requirements.txt pytest
python -m pytest tests/ -q          # executar a partir da raiz do repositório
```

- Requer Streamlit 1.66.1 (`st.components.v2`). `tests/conftest.py` aponta `SEEDS2_DATA_DIR` para um diretório temporário: a suíte **nunca** usa o armazenamento real (`~/.seeds2`).
- `tests/test_app_smoke.py` e `EMSAppSmokeTest` usam `streamlit.testing.v1.AppTest`. `tests/apptest_utils.abrir()` cria uma microrrede comissionada equivalente à configuração padrão V1.6 (`tests/seeds2_fixtures.py`) e abre a vista Simulação.
- `tests/apptest_utils.py` contorna limitações do AppTest (não são defeitos da app): widgets obsoletos após `st.rerun()` e (no 1.49) `st.segmented_control` com valor string. Use `continuar(app)` para seguir a navegação após um clique que dispara `st.rerun()`.
- `tests/test_seeds2_microgrid.py` (backend, persistência com reabertura em novo processo, backup, adaptador, rodada EMS real), `tests/test_seeds2_refinamento.py` (FV por arranjos, bateria/eólica/ModelLab, migrações a partir de dados v1 reais em `tests/fixtures/`, PDF, geolocalização) e `tests/test_seeds2_app.py` (UI SEEDS2). Não regenerar as fixtures v1: foram produzidas pelo código anterior ao documento v2.
- Navegador real: `tools/e2e/e2e_piso1_microrrede.js` (fases comissionar → reinício do servidor → reabrir → tablet); ver `docs/seeds2/VERIFICACAO_PISO1.md`.
- Os testes de UI devem refletir a navegação real; não remova nem enfraqueça asserções para fazê-los passar.

## Regras de proteção dos modelos científicos

1. **Não alterar** equações, algoritmos, parâmetros, constantes, curvas ou bancos de dados em `models/`, `h2_pemfc/`, `simulation/`, `config/`, `ems_integration/` e `reference_models/` sem pedido explícito e justificativa técnica.
2. Mudanças de UI, testes ou documentação não podem alterar resultados numéricos. Se um teste numérico falhar, investigue e reporte; não ajuste a tolerância nem o valor esperado.
3. Qualquer correção funcional na aplicação deve ser descrita e aprovada antes de ser implementada.
4. Pendências metodológicas do EMS estão em `EMS_TO_TALK_ABOUT.md`: não "corrigi-las" por conta própria.
5. Não fazer push direto para `main`; trabalhar em branch e abrir PR.
6. `seeds2/` só **adapta** configurações: nunca reformule o EMS ou os modelos para "caber" equipamentos. Agregue apenas o que é fisicamente equivalente no modelo existente; o resto é marcado como não representável (nunca omitido em silêncio).
7. Não inventar fichas técnicas, fabricantes, preços, procedências ou validações; valores desconhecidos ficam vazios ("não declarado"). Perfis de referência e clima sintético nunca são "medidos".
8. Nunca versionar bancos (`*.db`), backups (`*.seeds2backup.zip`) ou dados da instalação.

## Observações conhecidas (não corrigidas)

- `render_source_landing()` em `app.py` não é mais chamado na V1.6; o módulo **MIX** (`mix_app.py`) não é acessível pela interface (só via `energy_source="mix"`).
- `__pycache__/` está versionado no repositório (novo `.gitignore` evita novos arquivos; limpeza dos já versionados pendente).
- `README.md` ainda se intitula "V1.5" (há um aviso SEEDS2 no topo).
- Sem autenticação/perfis de acesso (Piso 1); ver `docs/seeds2/ARMAZENAMENTO.md`.

## Protocolo de colaboração e passagem de turno (ChatGPT ↔ Claude Code)

- **Direção humana:** o responsável pelo projeto define prioridades, aprova decisões técnicas/científicas e autoriza cada integração. ChatGPT prepara escopos/prompts e revisa os PRs; Claude Code implementa, testa e documenta. Não é necessário automatizar a execução das tarefas por GitHub Actions.
- **Antes de qualquer tarefa:** ler este `CLAUDE.md` e `docs/ai/HANDOFF.md`, conferir `main` e o PR mais recente, entender decisões aprovadas, dependências e limites da missão. Se a documentação divergir do código, verificar e registrar a divergência; não presumir.
- **Durante a tarefa:** trabalhar em branch própria, preservar as regras de proteção científica acima, manter mudanças restritas ao escopo e comunicar bloqueios ou decisões que exijam autorização. Não executar dois agentes alterando a mesma branch simultaneamente.
- **Ao concluir:** executar e relatar testes realmente realizados (com comando, resultado e limitações); atualizar `docs/ai/HANDOFF.md` na **mesma branch e no mesmo PR**, informando o que mudou, estado verificado, pendências, decisões e próximo passo. Referenciar PRs/commits em vez de duplicar relatórios longos.
- **Integração:** abrir PR para `main`, aguardar revisão e autorização humana. **Nunca efetuar merge automaticamente ou por iniciativa própria**. Não fazer push diretamente para `main`.
- **Cuaderno compacto:** `HANDOFF.md` é um resumo de continuidade, não um diário de raciocínio; manter fatos verificáveis, contexto suficiente para retomar e distinguir implementado de planejado. Não sobrescrever decisões anteriores sem registrar motivo e aprovação.
- **Segurança:** nunca registrar credenciais, tokens, dados sensíveis, chaves ou material corporativo não autorizado no repositório ou nos prompts; conferir a visibilidade do repositório antes de publicar.
