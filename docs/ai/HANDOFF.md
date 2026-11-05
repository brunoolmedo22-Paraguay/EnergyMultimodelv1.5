# SEEDS2 — Cuaderno de relevo entre agentes (HANDOFF)

> **Fuente de continuidad operativa.** Leer junto con [CLAUDE.md](../../CLAUDE.md) antes de comenzar cualquier sesión. Mantener breve, con hechos verificables, fecha y referencias a PRs. El código y los tests son la fuente de verdad funcional.

**Actualización:** 2026-11-05 · **rama objetivo:** `main` · **estado:** base V1.6, primera consolidación de pruebas integrada.

## 1. Estado actual (confirmado en GitHub)

- Repositorio: `brunoolmedo22-Paraguay/EnergyMultimodelv1.5`; aplicación Streamlit con console unificado V1.6.
- Arquitectura principal: `app.py`, `orchestrator_app.py`, `orchestrator_runtime.py`, `models/`, `h2_pemfc/`, `ems_integration/`, `config/`.
- EMS existente: núcleo de despacho con SLSQP y heurísticas GA/GWO/NGO; preservar métodos, parámetros e hipóteses científicas sin autorización.
- La aplicación actual permite simular modelos físicos y ejecutar una rodada integrada del EMS. No presentar esto como operação em tempo real ou validação física experimental já concluída.

## 2. Última entrega integrada

- **PR [#1](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/1):** testes de interface atualizados para o fluxo V1.6, helper `tests/apptest_utils.py` e `CLAUDE.md`. Merge confirmado em 2026-11-05 (`5ffe2eedf96727cbc3edb8b30875db8cfa97117d`).
- **Resultado comunicado por Claude Code:** `python -m pytest tests/ -q` → 63 passed, 0 failed, 0 skipped, +36 subtests, 7 avisos SLSQP; repetido duas vezes no ambiente de Claude. **Não reexecutado independentemente por ChatGPT; sem CI confirmado para esse commit.**
- Arquivos científicos, algoritmos, parâmetros e aplicação não foram alterados no PR #1.

## 3. Decisões aprovadas / responsabilidades

- **Dono do projeto:** define objetivos, revê resultados e autoriza integração.
- **ChatGPT:** traduz objetivos em missões verificáveis, prepara prompts mestres, revisa diffs e recomenda aprovar/rejeitar.
- **Claude Code:** lê o Git, implementa escopos aprovados, executa testes, atualiza este cuaderno e abre PR.
- A colaboração é **por turnos**, com pessoa supervisionando e transmitindo os prompts; não automatizar tarefas de programação pelo GitHub Actions. GitHub Actions pode futuramente executar **CI de testes**, não disparar agentes de forma autônoma.
- **Nenhum agente faz merge sem aprovação explícita do responsável.** Nunca push direto para `main`. Trabalhar em branch + PR.
- Modelos físicos e seus catálogos são responsabilidade principal do dono do projeto; decisões metodológicas do otimizador EMS envolvem Marilia. Não refatorar o EMS científico por conveniência arquitetural.

## 4. Pendências / observações

- MIX (`mix_app.py`) não é acessível na navegação unificada V1.6; decidir sua recuperação na arquitetura nova.
- `README.md` ainda se apresenta como V1.5, embora haja fluxo V1.6.
- `__pycache__/` versionado (53 arquivos segundo diagnóstico do PR #1); planejar limpeza com cuidado.
- `tests/apptest_utils.py` contorna limitações reportadas de AppTest 1.49; isso **não equivale** a cobertura end-to-end em navegador real. Considerar CI GitHub Actions e testes de browser adequados.
- Questões científicas e metodológicas do EMS: ver `EMS_TO_TALK_ABOUT.md` e levantar evidências antes de qualquer alteração.
- No estado atual, o excedente solar/eólico é abatido da carga e pode ser limitado antes de permitir carregamento de bateria; isso merece avaliação em fase específica, **não corrigir silenciosamente**.

## 5. Próxima missão proposta — Piso 1, gestão persistente de microrrede

**Ainda não implementada nem autorizada para mudanças de código por este documento.**

- Criar ambiente de **Gestão da Microrrede** (cadastro/seleção/edição e persistência segura de configurações), separado do futuro **Centro de Operação**.
- Inventário/catálogo e alocação de equipamentos (solar, eólica, bateria, PEMFC e térmica); aproveitar cadastros e modelos científicos já existentes.
- Definir contratos de unidades, timestamps, perfis de carga, disponibilidade e resultados que permitam conectar equipamentos e EMS com rastreabilidade.
- Experiência visual moderna **junto** com o backend, testes e documentação; incremento funcional completo (não apenas scaffold).
- Não confundir importação futura de calibração PEMFC do ModelLab com parâmetros completos de dinâmica/BoP validados.
- Só executar após o responsável aprovar o prompt mestre e critérios de aceitação; abrir PR específico.

## 6. Ritual de atualização ao final de cada missão

Atualizar **este arquivo no mesmo PR** com: data, versão/ramo, PR e commit, escopo e arquivos, testes realmente executados e resultados, decisões confirmadas, limitações/pendências, próxima missão recomendada. Separar claramente **implementado**, **validado**, **proposto** e **bloqueado**; substituir o relato anterior resumidamente, preservando links históricos. Nunca incluir senhas, tokens ou dados sensíveis.

**Leitura obrigatória ao entrar:** `CLAUDE.md` → este `HANDOFF.md` → estado real de `main` e PRs recentes. Em caso de conflito, reportar; não improvisar decisão científica.
