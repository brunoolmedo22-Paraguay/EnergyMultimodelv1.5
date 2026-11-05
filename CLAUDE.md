# CLAUDE.md — Energy MultiModel (V1.6)

Aplicação Streamlit para modelos energéticos (Solar, Eólica, Térmica, Bateria, H₂/PEMFC) integrados a um EMS de despacho ótimo. Projeto SEEDS2.

## Arquitetura

- `app.py` — ponto de entrada (`python -m streamlit run app.py`). Roteia por `st.session_state["energy_source"]`: `None` → console unificado; `"solar"|"wind"|"thermal"|"battery"|"h2"|"mix"` → bancada individual; `"ems"` (sessão legada V1.5) → volta ao console. A UI solar está no próprio `app.py`.
- `orchestrator_app.py` — console V1.6 (UI). Páginas: Visão Geral → Módulo de Carga → Modelos → Otimizador → Resultados do Otimizador → Resultados dos Modelos → Exportar Resultados. Bancadas individuais: página **Modelos**, expander "Bancadas individuais".
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

- `tests/test_app_smoke.py` e `EMSAppSmokeTest` usam `streamlit.testing.v1.AppTest` (ignorados se o Streamlit não estiver instalado).
- `tests/apptest_utils.py` contorna duas limitações do AppTest 1.49 (não são defeitos da app): widgets obsoletos após `st.rerun()` e `st.segmented_control` com valor string. Use `continuar(app)` para seguir a navegação após um clique que dispara `st.rerun()`.
- Os testes de UI devem refletir a navegação V1.6 real; não remova nem enfraqueça asserções para fazê-los passar.

## Regras de proteção dos modelos científicos

1. **Não alterar** equações, algoritmos, parâmetros, constantes, curvas ou bancos de dados em `models/`, `h2_pemfc/`, `simulation/`, `config/`, `ems_integration/` e `reference_models/` sem pedido explícito e justificativa técnica.
2. Mudanças de UI, testes ou documentação não podem alterar resultados numéricos. Se um teste numérico falhar, investigue e reporte; não ajuste a tolerância nem o valor esperado.
3. Qualquer correção funcional na aplicação deve ser descrita e aprovada antes de ser implementada.
4. Pendências metodológicas do EMS estão em `EMS_TO_TALK_ABOUT.md`: não "corrigi-las" por conta própria.
5. Não fazer push direto para `main`; trabalhar em branch e abrir PR.

## Observações conhecidas (não corrigidas)

- `render_source_landing()` em `app.py` não é mais chamado na V1.6; o módulo **MIX** (`mix_app.py`) não é acessível pela interface (só via `energy_source="mix"`).
- `__pycache__/` está versionado no repositório.
- `README.md` ainda se intitula "V1.5".

## Protocolo de colaboração e passagem de turno (ChatGPT ↔ Claude Code)

- **Direção humana:** o responsável pelo projeto define prioridades, aprova decisões técnicas/científicas e autoriza cada integração. ChatGPT prepara escopos/prompts e revisa os PRs; Claude Code implementa, testa e documenta. Não é necessário automatizar a execução das tarefas por GitHub Actions.
- **Antes de qualquer tarefa:** ler este `CLAUDE.md` e `docs/ai/HANDOFF.md`, conferir `main` e o PR mais recente, entender decisões aprovadas, dependências e limites da missão. Se a documentação divergir do código, verificar e registrar a divergência; não presumir.
- **Durante a tarefa:** trabalhar em branch própria, preservar as regras de proteção científica acima, manter mudanças restritas ao escopo e comunicar bloqueios ou decisões que exijam autorização. Não executar dois agentes alterando a mesma branch simultaneamente.
- **Ao concluir:** executar e relatar testes realmente realizados (com comando, resultado e limitações); atualizar `docs/ai/HANDOFF.md` na **mesma branch e no mesmo PR**, informando o que mudou, estado verificado, pendências, decisões e próximo passo. Referenciar PRs/commits em vez de duplicar relatórios longos.
- **Integração:** abrir PR para `main`, aguardar revisão e autorização humana. **Nunca efetuar merge automaticamente ou por iniciativa própria**. Não fazer push diretamente para `main`.
- **Cuaderno compacto:** `HANDOFF.md` é um resumo de continuidade, não um diário de raciocínio; manter fatos verificáveis, contexto suficiente para retomar e distinguir implementado de planejado. Não sobrescrever decisões anteriores sem registrar motivo e aprovação.
- **Segurança:** nunca registrar credenciais, tokens, dados sensíveis, chaves ou material corporativo não autorizado no repositório ou nos prompts; conferir a visibilidade do repositório antes de publicar.
