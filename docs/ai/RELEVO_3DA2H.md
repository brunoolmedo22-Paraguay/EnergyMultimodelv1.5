# SEEDS2 — Relevo do Piso 3D-A2-H (PEMFC/H₂ no EMS V2)

**Data:** 2026-11-11. **Módulo autorizado:** 3D-A2-H (PEMFC/H₂). **3D-A2-T** (térmica) e **3D-B** (dashboard) **NÃO**
foram iniciados. **Sem merge.**

## 1. Identificação

| Dado | Valor |
|---|---|
| Base | `main` `0c9df80ec7a759d90227453cbd7b1eb3f3e25d40` (merge do PR #22, Piso 3D-A2-R) |
| Rama | `claude/adoring-newton-jzfmfx` (reiniciada a partir de `main` após o merge do PR #22) |
| PR | **#23** — https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/pull/23 (Draft, contra `main`, sem merge) |
| Checkpoints | `01d2533`, `9022198`, `068bcb6` e `b41b69d` (gates H1–H3); `56e8d92` (E2E + KPI B04); `71bd089` (contrato v3 nos testes 3D-A2-R); `68fd055` (docs); **auditoria do PR #23:** `0a2a6e5` (C), `0055e68` (A/B/D), `d0bee62` (E2E do fluxo completo), `b473cda`/`9a6d43a` (docs); **decisão do responsável:** `8be5de4` (APROVAÇÃO B04, commit independente), `efa05c8` (testes/bancada no estado aprovado + verificação A), `0058902` (verificação B: E2E sem aprovação simulada) + commit de documentação |
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
- **Política B04 `b04-proposta-2` APROVADA pelo responsável** (commit independente `8be5de4`; limiares, identidade
  `412863021aee…` e versão inalterados). Alcance: certificação MATEMÁTICA da PWL contra o modelo PEMFC existente; NÃO é
  validação experimental do modelo Horizon nem certificação de operação física. Cada curva continua sujeita à sua própria
  verificação B04 (critérios recomputados pelo núcleo).
- **Caminho normal** em testes e E2E: `politica_aprovada_no_teste` foi REMOVIDA; `politica_pendente_no_teste` simula a
  revogação para provar que uma política pendente continua bloqueando.
- **Verificação A** (malha densa, 6 configurações): partidas, paradas e rampas de subida nunca subestimam; rampas de
  DESCIDA em operação contínua subestimam de forma limitada (≤ 0,0044 kg/rampa, ≤ 0,72 % do intervalo; pior caso =
  P_máx → P_mín, o mesmo da análise a priori). Sem garantia global de não subestimação; reportado por rodada.
  Decisão nova C-3DA2H-12.
- **Verificação B** (fluxo completo, B04 realmente aprovada, sem aprovação simulada): bancada 6 + fluxo 20 + reabertura
  16 + conferência quantitativa 18 verificações; registro de chamadas ao motor/modelos VAZIO.

## 2b. Auditoria externa do PR #23 (revisão de `68fd055`) — correções aplicadas

| Ponto | Correção | Evidência |
|---|---|---|
| A — massa de H₂ por evento (B05) | m_SU/m_SD = massas ADICIONAIS pela integração TEMPORAL do modelo dinâmico (intervalo com evento − mesmo intervalo em regime), m = máx(0, máx_p δ). Partida: δ < 0 em todo o domínio ⇒ m_SU = 0 (antes 0,00233 kg: dupla contagem). Parada: m_SD = 0,0064 kg. Decomposição M_EMS − M_din = (q̂ − q)Δ + (m − δ) exata e ≥ 0 | `tests/test_piso3da2h_auditoria_pr23.py` (partida, parada, permanência ligada com degraus) |
| B — aceitação algébrica × dinâmica | `summary.execution.aceitacao` com estados SEPARADOS (algébrica, dinâmica, física sempre `nao_validada`), classificação e rótulo; verificação dinâmica com a contabilidade exata do MILP; reabertura recalcula a coerência e confere rótulo e H₂ do EMS; UI com alerta «DINAMICAMENTE INCOERENTE» | testes negativos (IDLE, partida fria, Δ curto); missão incoerente forçada (bloqueio a priori desligado só no teste); rótulo/coerência adulterados detectados; AppTest |
| C — autoridade B04 | núcleo reconhece SÓ políticas congeladas em `POLITICAS_B04_NUCLEO` (SHA-256 do conteúdo, sem `situacao`); desconhecida/alterada/situação divergente ⇒ erro; aprovação = commit no núcleo | `tests/ems_v2/test_ems_v2_b04_certificado.py` (18), `tests/test_piso3da2h_curva.py` |
| D — restrições físicas | P_mín < IDLE, rampa > 120 kW/min e transitórios incompatíveis com Δ/T_amb (análise a priori) BLOQUEIAM o preflight | `test_pmin_…`, `test_rampa_…`, `test_partida_fria_…` |
| E2E com política aprovada | aprovação SIMULADA só no servidor de teste (`tools/e2e/aprovacao_b04_simulada`): declarações PEMFC pela interface → missão → rodada → reabertura em servidor novo SEM solver com modelos sabotados | 8 + 14 + 9 verificações; registro de chamadas VAZIO |

Na época da auditoria a B04 estava pendente; a aprovação veio depois, por decisão do responsável (`8be5de4`).

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
| Verificação A — `python tests/verificacao_massas_3da2h.py` (6 configurações, malha 0,5 kW, pares a cada 2,5 kW) | sem subestimação em partidas, paradas e rampas de subida; rampas de descida ≤ 0,0044 kg (`docs/ems_v2/evidencia_3da2h/verificacao_massas_eventos.*`) |
| Verificação B — `bash tools/e2e/run_piso3da2h.sh <py solver> <pasta> <py sem solver>` (política do repositório, aprovada) | bancada 6 + fluxo 20 + reabrir 16 + conferência 18; chamadas ao motor/modelos VAZIO |
| Suítes 3D-A2-H após a aprovação (certificado, curva, execução, app, auditoria, verificação A) | 77 passed; guardas 190 passed, 2 skipped; auditoria da missão aprovada |
| Regressão completa sobre o código final após a decisão (`0058902`; depois só documentação) | com solver **2234 passed, 2 skipped**, 9 warnings (887 s); sem solver **1741 passed, 150 skipped**, 9 warnings (586 s); 0 falhas |
| Regressão completa com e sem solver sobre `d0bee62` (antes da aprovação) | com solver **2229 passed, 2 skipped**, 9 warnings (885 s); sem solver **1736 passed, 150 skipped**, 9 warnings (578 s); 0 falhas (as 2 omitidas com solver são as auditorias explícitas de diff condicionadas por variável) |

## 5. Decisões do responsável (PR #23)

Detalhes em `INTEGRACAO_3DA2H.md` §9.

- **Aprovadas:** B04 (`b04-proposta-2`, certificação matemática); C-3DA2H-02 (`massas_h2_eventos`); C-3DA2H-03 (rampa
  única simétrica, sem exceder o modelo dinâmico); C-3DA2H-04 (D05 só em «ensaio»; multimodo pendente); C-3DA2H-05
  (bloqueio P_mín < IDLE); C-3DA2H-08 a 11.
- **Nova, a decidir:** **C-3DA2H-12** — rampas de DESCIDA em operação contínua: subestimação limitada do H₂ do EMS,
  não representável sem termo de rampa no MILP (formulação não autorizada); hoje reportada por rodada e dentro da
  tolerância dinâmica. Opções: aceitar como resíduo identificado, ou autorizar um termo de rampa.
- **Integração em `main`:** pendente da revisão final do responsável. NÃO fazer merge.

## 6. Cuidados para quem continuar

- Sempre `PYTHONDONTWRITEBYTECODE=1`: os `.pyc` versionados regenerados quebram a guarda 3C-4. Os regenerados nesta sessão
  ficaram em `git stash` e nunca foram commitados.
- Não alterar `POLITICA_B04`/`POLITICAS_B04_NUCLEO` sem nova decisão explícita. `politica_pendente_no_teste` só em testes.
- As auditorias explícitas 3D-A e 3D-A2-R são por missão: acusam, corretamente, os arquivos do C-3DA2H-01 quando rodadas
  sobre este ramo. A auditoria vigente é a do 3D-A2-H.
- Um servidor Streamlit antigo na porta 8631 fazia o E2E falhar: o roteiro agora recusa porta ocupada e encerra o servidor
  por `trap`.

## 7. Próximo passo

1. Revisão final do PR #23 pelo responsável e decisão de integração em `main` (sem merge automático).
2. Decisão C-3DA2H-12.
3. Só então 3D-A2-T ou 3D-B, com nova autorização.
