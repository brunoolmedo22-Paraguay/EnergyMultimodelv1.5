# SEEDS2 — Relevo do Piso 3D-A2 (integração multitecnologia do EMS V2)

**Data:** 2026-11-11 · **Módulo autorizado:** só **3D-A2-R** (FV + eólica). **3D-A2-H** (PEMFC/H₂), **3D-A2-T** (térmica)
e **3D-B** (dashboard) **NÃO** foram iniciados e exigem nova autorização após a auditoria externa. **Sem merge.**

## 1. Identificação

| Dado | Valor |
|---|---|
| Base | `main` `7eb29e590a75f79ef7ab2a608727645c73960f50` (merge do PR #21, Piso 3D-A) |
| Rama | `claude/adoring-newton-jzfmfx` (reiniciada a partir de `main` após o merge do PR #21) |
| PR | ver `docs/ai/HANDOFF.md` (aberto contra `main`, sem merge) |
| Checkpoints | `db7ca7e` (adaptador, preflight, persistência), `e3e87b6` (testes), `16938ec` (UI e guarda), `4b6c1fd` (E2E), `a2bf8ae` (docs) + commit final de relevo |
| `ems_v2/` | árvore `58cc13b6de0abff0f0cff824d469f2fb3f4ed3d7`, idêntica à base |
| Modelos físicos | `models/`, `simulation/`, `config/`, `h2_pemfc/`, `ems_integration/` idênticos à base |

## 2. Arquivos

**Novos**

- `integracao_v2/renovaveis.py`
- `tests/piso3da2r_util.py`
- `tests/test_piso3da2r_renovaveis.py`
- `tests/test_piso3da2r_execucao.py`
- `tests/test_piso3da2r_app.py`
- `tests/ems_v2/piso3da2r_guard_policy.py`
- `tests/ems_v2/test_piso3da2r_guardas.py`
- `tools/e2e/seed_piso3da2r.py`
- `tools/e2e/e2e_piso3da2r.js`
- `tools/e2e/run_piso3da2r.sh`
- `docs/ems_v2/INTEGRACAO_3DA2R.md`
- `docs/ems_v2/evidencia_3da2r/`
- este arquivo

**Modificados**

- `integracao_v2/estrategia.py` — formato 2
- `integracao_v2/montagem.py` — c_curt, bases
- `integracao_v2/preflight.py` — renováveis por UID
- `integracao_v2/registro.py` — contrato v2
- `integracao_v2/execucao.py` — grava `v2/renovaveis.json`; impressão científica
- `integracao_v2/ui.py` — formulário e rodada
- `tests/ems_v2/piso3da_guard_policy.py` — encadeia a exceção C-3DA2R-01
- `tools/e2e/sabotage_v2/sitecustomize.py` — sabota também os modelos físicos
- `CLAUDE.md`, `PARAMIJEFE.md` (Entrega 14), `docs/ai/HANDOFF.md`

`seeds2/` não foi tocado.

## 3. O que já opera

1. Estratégia formato 2 com clima previsto (semântica e emissão) e declarações por renovável:
   - η de conversão FV;
   - hipótese de densidade do ar;
   - c_curt;
   - procedência.

   Nenhum desses campos tem valor padrão. O formato 1 do 3D-A continua legível e a interface o atualiza com seções vazias.
2. Potencial por UID calculado pelos modelos REAIS sobre o clima do cenário:
   - FV por arranjo (`arr-…`) com `simulate_noct_efficiency_model`;
   - eólica por registro (`eq-…`) com `run_wind_model`.

   O clima é usado nos instantes exatos e a média de subamostras é exata; não há interpolação nem preenchimento.
3. Preflight V2 com FV/eólica representáveis. Os bloqueios são legíveis e listados em `INTEGRACAO_3DA2R.md` §5. Missões
   só com bateria + PCC continuam aptas.
4. Execução real com HiGHS. O potencial entra no MILP (P_R ≤ a·A, vertimento) e na planta (`limitada_pela_disponibilidade`).
5. Persistência v2 por UID e intervalo:
   - colunas A prevista/observada, a, A utilizável, P_R, vertimento e energia acumulada;
   - resumo por UID conferido contra os indicadores selados;
   - `v2/renovaveis.json` comprometido no manifesto antes da execução.
6. Reabertura sem modelos nem solver. O potencial previsto e o realizado são conferidos bit a bit contra os registros
   selados. As rodadas v1 (3D-A) continuam legíveis.
7. Arquivo Científico: exportação e importação, com consulta sem modelos.
8. UI mínima: formulário da etapa 03; tabela e figura por UID na rodada.

## 4. Último E2E completo (navegador real)

Executado com `bash tools/e2e/run_piso3da2r.sh <py-solver> <py-sem-solver> <pasta>`: **43 verificações, exit 0**.

| Fase | Verificações |
|---|---:|
| operar | 22 |
| reinício do servidor | 6 |
| tablet | 7 |
| importar | 8 |

Na fase importar, a instalação está limpa, SEM solver e com os motores e os MODELOS físicos sabotados. O registro de
chamadas a motor/modelos ficou VAZIO. A rodada foi `57dc2b19549249c59938b0580cfc8075`, com custo realizado R$ 146,35
(diretório temporário; UID regenerado a cada execução). Os registros estão em `docs/ems_v2/evidencia_3da2r/`; as capturas
PNG não são versionadas.

## 5. Evidência de reabertura sem reotimização

- `test_caso8_reabertura_sem_modelos_fisicos_nem_otimizador` sabota:
  - `simulate_noct_efficiency_model` e `run_wind_model`;
  - `derivar_fv` e `derivar_eolica`;
  - `submit` e `preparar`;
  - os imports de `pyomo`/`highspy`.

  A verificação foi aprovada.
- `test_caso8_adulteracao_da_derivacao_renovavel_e_detectada`: um valor alterado em `v2/renovaveis.json` ⇒ verificação
  REPROVADA (SHA ≠ manifesto).
- A interface (`test_piso3da2r_app`) reabre em sessão nova com os mesmos componentes sabotados.

## 6. Estado dos testes

| Bateria | Com solver | Sem solver |
|---|---|---|
| `tests/test_piso3da2r_renovaveis.py` | 20 passed | 20 passed |
| `tests/test_piso3da2r_execucao.py` | 13 passed | 13 skipped (explícito) |
| `tests/test_piso3da2r_app.py` + `tests/test_piso3da_app.py` | 7 passed | — |
| 3D-A focalizados + guardas | 40 passed, 1 skipped | — |
| Guardas de isolamento (`tests/ems_v2 -k isolamento/guarda/…`) | 203 passed, 2 skipped | — |
| Regressão completa `tests/` | <<REG_SOLVER>> | <<REG_NOSOLVER>> |
| CI remoto (`SEEDS2 regression`, solver true/false) | ver PR | ver PR |

## 7. Comandos

Instalar dependências (sem solver):

```bash
pip install -r requirements.txt pytest
```

Para o solver, acrescentar:

```bash
pip install -r requirements-ems_v2.txt
```

Testes focalizados do 3D-A2-R:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_piso3da2r_renovaveis.py tests/test_piso3da2r_execucao.py tests/test_piso3da2r_app.py tests/ems_v2/test_piso3da2r_guardas.py -q -p no:cacheprovider
```

Regressão completa:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ -q -p no:cacheprovider
```

Auditoria explícita do diff da missão:

```bash
python tests/ems_v2/piso3da2r_guard_policy.py
```

E2E em navegador real:

```bash
bash tools/e2e/run_piso3da2r.sh <python com Pyomo/HiGHS> <python sem solver> <pasta vazia>
```

## 8. Falhas conhecidas e causas

- Nenhum teste falhando no que foi executado.
- **`__pycache__/*.pyc` versionados.** Qualquer `python -c` sem `PYTHONDONTWRITEBYTECODE=1` regenera esses arquivos em
  `config/` e `models/`, e a guarda 3C-4 de diff falha. Não é alteração da missão: rode sempre com a variável. Os `.pyc`
  regenerados nesta sessão foram guardados em stashes rotulados, não descartados nem commitados.
- **Realização renovável = previsão** (C-3DA2R-04). O cenário não tem fonte de clima REALIZADO.
- **Limitações da física.** Ver `INTEGRACAO_3DA2R.md` §9: GHI no plano, vento no cubo, sem esteira, η de inversor
  declarado.

## 9. Sem publicar

Só as capturas PNG do E2E e o pacote `.seeds2study.zip` exportado, no diretório temporário da sessão; regeneráveis com o
roteiro. Todo o código, os testes e a documentação estão na rama.

## 10. Próximos passos exatos

1. Auditoria externa do PR do 3D-A2-R e decisão sobre a exceção nominal **C-3DA2R-01**.
2. Conferir o CI remoto (matriz solver true/false). Se falhar, reproduzir localmente antes de corrigir.
3. Só com autorização, **3D-A2-H** (PEMFC). Ponto de partida: a matriz em `INTEGRACAO_3DA2R.md` §10. Primeiro aprovar
   os limiares B04; depois construir e certificar q(P) sobre o modelo aproximado (hash/versão); declarar P_min, preço do
   H₂, permanências, abstração de transição e estado inicial; resolver D05.
4. Só com autorização específica, **3D-A2-T** (térmica: termo M19 no perfil + MILP + auditor + contabilidade, em PR
   separado de mudança de formulação).
5. **3D-B** (dashboard): consome o contrato de §6 de `INTEGRACAO_3DA2R.md`.

**Proibido na continuação:**

- modificar `ems_v2/`, os modelos físicos ou o V1.6;
- relaxar guardas globais;
- preencher parâmetros físicos ausentes;
- apresentar dados sintéticos como resultados de microrrede;
- `git reset --hard` / `git clean`;
- merge.
