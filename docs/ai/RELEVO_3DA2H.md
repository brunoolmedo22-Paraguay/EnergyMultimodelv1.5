# SEEDS2 — Relevo do Piso 3D-A2-H (PEMFC/H₂ no EMS V2)

**Data:** 2026-11-11. **Módulo autorizado:** 3D-A2-H (PEMFC/H₂). **3D-A2-T** (térmica) e **3D-B** (dashboard) **NÃO**
foram iniciados. **Sem merge.**

## 1. Identificação

| Dado | Valor |
|---|---|
| Base | `main` `0c9df80ec7a759d90227453cbd7b1eb3f3e25d40` (merge do PR #22, Piso 3D-A2-R) |
| Rama | `claude/adoring-newton-jzfmfx` (reiniciada a partir de `main` após o merge do PR #22) |
| PR | **#23** — https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/23 (Draft, contra `main`, sem merge) |
| Checkpoints | `01d2533`, `9022198`, `068bcb6` e `b41b69d` (gates H1–H3); `56e8d92` (E2E + KPI B04); `71bd089` (contrato v3 nos testes 3D-A2-R); `68fd055` (docs); **auditoria do PR #23:** `0a2a6e5` (C), `0055e68` (A/B/D), `d0bee62` (E2E do fluxo completo) + commit de documentação |
| Núcleo `ems_v2/` | alterado SÓ nos 4 arquivos do C-3DA2H-01 (autorizado) |
| Modelos físicos | `models/`, `simulation/`, `config/`, `h2_pemfc/`, `ems_integration/` e `seeds2/` idênticos à base |

## 2. Estado real

- **Implementado e demonstrado:**
  - curva q_H₂(P_líq) do modelo físico, gerada UMA vez por configuração e reutilizada;
  - certificado B04 verificável no núcleo;
  - estratégia formato 3;
  - preflight com bloqueios legíveis;
  - missão real com HiGHS (FV + eólica + bateria + PEMFC + PCC);
  - verificação pelo modelo dinâmico;
  - persistência v3;
  - reabertura, exportação e importação sem modelo nem solver;
  - bancada H₂;
  - E2E em navegador.
- **BLOQUEIO REAL que impede declarar a integração concluída em produção:** a política B04 `b04-proposta-2` está
  CONGELADA e **pendente de aprovação** do responsável. Sem aprovação, o preflight bloqueia toda PEMFC
  (`b04_aguardando_aprovacao`). As missões com PEMFC só rodam nos testes, sob `politica_aprovada_no_teste` (aprovação
  SIMULADA).

## 2b. Auditoria externa do PR #23 (revisão de `68fd055`) — correções aplicadas

| Ponto | Correção | Evidência |
|---|---|---|
| A — massa de H₂ por evento (B05) | m_SU/m_SD = massas ADICIONAIS pela integração TEMPORAL do modelo dinâmico (intervalo com evento − mesmo intervalo em regime), m = máx(0, máx_p δ). Partida: δ < 0 em todo o domínio ⇒ m_SU = 0 (antes 0,00233 kg: dupla contagem). Parada: m_SD = 0,0064 kg. Decomposição M_EMS − M_din = (q̂ − q)Δ + (m − δ) exata e ≥ 0 | `tests/test_piso3da2h_auditoria_pr23.py` (partida, parada, permanência ligada com degraus) |
| B — aceitação algébrica × dinâmica | `summary.execution.aceitacao` com estados SEPARADOS (algébrica, dinâmica, física sempre `nao_validada`), classificação e rótulo; verificação dinâmica com a contabilidade exata do MILP; reabertura recalcula a coerência e confere rótulo e H₂ do EMS; UI com alerta «DINAMICAMENTE INCOERENTE» | testes negativos (IDLE, partida fria, Δ curto); missão incoerente forçada (bloqueio a priori desligado só no teste); rótulo/coerência adulterados detectados; AppTest |
| C — autoridade B04 | núcleo reconhece SÓ políticas congeladas em `POLITICAS_B04_NUCLEO` (SHA-256 do conteúdo, sem `situacao`); desconhecida/alterada/situação divergente ⇒ erro; aprovação = commit no núcleo | `tests/ems_v2/test_ems_v2_b04_certificado.py` (18), `tests/test_piso3da2h_curva.py` |
| D — restrições físicas | P_mín < IDLE, rampa > 120 kW/min e transitórios incompatíveis com Δ/T_amb (análise a priori) BLOQUEIAM o preflight | `test_pmin_…`, `test_rampa_…`, `test_partida_fria_…` |
| E2E com política aprovada | aprovação SIMULADA só no servidor de teste (`tools/e2e/aprovacao_b04_simulada`): declarações PEMFC pela interface → missão → rodada → reabertura em servidor novo SEM solver com modelos sabotados | 8 + 14 + 9 verificações; registro de chamadas VAZIO |

B04 continua PENDENTE (estado real); nenhuma aprovação foi gravada no repositório.

## 3. Arquivos

**Novos:**

- `integracao_v2/curva_h2.py`;
- `integracao_v2/pemfc_dinamica.py`;
- testes:
  - `tests/piso3da2h_util.py`;
  - `tests/test_piso3da2h_curva.py`;
  - `tests/test_piso3da2h_execucao.py`;
  - `tests/test_piso3da2h_app.py`;
  - `tests/ems_v2/test_ems_v2_b04_certificado.py`;
  - `tests/ems_v2/piso3da2h_guard_policy.py`;
- teste da auditoria: `tests/test_piso3da2h_auditoria_pr23.py`;
- E2E: `tools/e2e/{seed_piso3da2h.py,e2e_piso3da2h.js,run_piso3da2h.sh}` e `tools/e2e/aprovacao_b04_simulada/sitecustomize.py`;
- documentação:
  - `docs/ems_v2/INTEGRACAO_3DA2H.md`;
  - `docs/ems_v2/evidencia_3da2h/`;
  - este arquivo.

**Modificados:**

| Arquivo | Mudança |
|---|---|
| `ems_v2/contracts.py` | `real_certificada_b04`, `PoliticaB04`, `PerfilMassaB04`, `CertificadoB04`, verificação e registro |
| `ems_v2/ponte/{projecao,compromisso,preflight}.py` | `curvas_h2` opcional (autorizado) e `massas_h2_eventos` opcional (**a confirmar**) |
| `integracao_v2/estrategia.py` | formato 3 com PEMFC |
| `integracao_v2/montagem.py` | inventário efetivo PEMFC, declaração de commitment por unidade, fontes de disponibilidade |
| `integracao_v2/preflight.py` | curva, certificado, massas e documento `v2/pemfc.json` |
| `integracao_v2/registro.py` | contrato v3, colunas por unidade, verificação PEMFC |
| `integracao_v2/execucao.py` | verificação dinâmica |
| `integracao_v2/ui.py` | formulário PEMFC e resultados |
| `h2_app.py` | seção da curva do EMS na bancada |
| Testes/guardas do 3D-A2-R | ajustes NOMINAIS: versão/formato vigentes; versões anteriores continuam testadas |

## 4. Verificação (comandos realmente executados)

| Comando | Resultado |
|---|---|
| `pytest tests/ems_v2` com solver, após a alteração do núcleo | 1519 passed, 2 skipped |
| Focalizados 3D-A2-H + certificado + UI 3D-A/3D-A2-R | 53 passed |
| Guardas/isolamento (`tests/ems_v2 -k "guarda or isolamento or ci01 or estabiliz or wind_guard"`) | 190 passed, 2 skipped |
| `python tests/ems_v2/piso3da2h_guard_policy.py` | aprovada |
| `bash tools/e2e/run_piso3da2h.sh <py solver> <pasta> <py sem solver>` (após a auditoria) | bloqueio 8 + fluxo 14 + reabrir 9 verificações, exit 0, chamadas ao motor/modelos VAZIO (`docs/ems_v2/evidencia_3da2h/`) |
| Linha de base antes da auditoria (código de `68fd055`) | com solver 2204 passed, 2 skipped; sem solver 1716 passed, 145 skipped |
| Suítes focalizadas após a auditoria | auditoria PR #23 20 passed; curva + certificado + execução 48 passed; UI 3D-A2-H 4 passed; guardas 190 passed, 2 skipped |
| Regressão completa com solver, 1ª passagem (antes de `71bd089`) | 2 failed, 2201 passed, 2 skipped: asserções fixas «versão 2» em `test_piso3da2r_execucao.py`, corrigidas nominalmente em `71bd089` |
| Regressão completa com e sem solver sobre o código final (`d0bee62`; depois só documentação) | em execução no fechamento deste commit (resultado registrado no commit seguinte) |

## 5. Decisões pendentes do responsável

Detalhes em `INTEGRACAO_3DA2H.md` §9.

1. **Aprovação definitiva da política B04** (`b04-proposta-2`). Com ela, `real_certificada_b04` passa a ser habilitada:
   mudar a situação da entrada `412863021aee…` de `ems_v2.contracts.POLITICAS_B04_NUCLEO` (e o campo correspondente de
   `integracao_v2/curva_h2.POLITICA_B04`) para `aprovada_pelo_responsavel`, num commit próprio, revisado e com registro.
2. **C-3DA2H-02:** confirmar `massas_h2_eventos` (extensão opcional da ponte, além da autorização literal). Desde a
   auditoria, as massas transportadas são as ADICIONAIS (C-3DA2H-08).
3. **C-3DA2H-03:** rampa única do inventário aplicada à subida e à descida.
4. **C-3DA2H-04:** D05 = abstração instantânea em «ensaio» + verificação dinâmica a posteriori; o contexto operacional
   continua pendente.
5. **C-3DA2H-05:** IDLE de 10 kW do modelo dinâmico × P_mín declarado (agora bloqueia).
6. **C-3DA2H-08 … 11** (auditoria do PR #23): semântica das massas adicionais, aceitação separada, autoridade B04 no
   núcleo, tolerâncias dinâmicas por unidade de tempo.

## 6. Cuidados para quem continuar

- Sempre `PYTHONDONTWRITEBYTECODE=1`: os `.pyc` versionados regenerados quebram a guarda 3C-4. Os regenerados nesta sessão
  ficaram em `git stash` e nunca foram commitados.
- Não alterar `POLITICA_B04` sem aprovação explícita. Não usar `politica_aprovada_no_teste` fora de testes.
- As auditorias explícitas 3D-A e 3D-A2-R são por missão: acusam, corretamente, os arquivos do C-3DA2H-01 quando rodadas
  sobre este ramo. A auditoria vigente é a do 3D-A2-H.
- Um servidor Streamlit antigo na porta 8631 fazia o E2E falhar: o roteiro agora recusa porta ocupada e encerra o servidor
  por `trap`.

## 7. Próximo passo

1. Auditoria externa do PR.
2. Decisão B04 e das confirmações C-3DA2H-02…05.
3. Só então 3D-A2-T ou 3D-B, com nova autorização.
