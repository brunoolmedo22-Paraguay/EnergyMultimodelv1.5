# SEEDS2 — Verificação do Piso 1

Ambiente da verificação: Linux, Python 3.13.18, `requirements.txt` desta branch (Streamlit 1.66.1,
reportlab 4.4.10, pypdf 6.21.4), Chromium/Playwright para os testes em navegador. Data: 2026-11-05.

## G. Gestor de microrredes (verificação atual)

**Suíte:** `python -m pytest tests/ -q` → **208 passed, 0 failed, 0 skipped** (+105 subtests; 7 avisos SLSQP
pré-existentes). 163 testes anteriores (adaptados à navegação pelo Gestor, sem enfraquecer asserções) +
`test_seeds2_gestor.py` (32, backend) + `test_seeds2_gestor_app.py` (13, interface).

| Requisito da missão | Onde é verificado |
|---|---|
| 1 início sem microrredes | `CatalogoTest.test_inicio_sem_microrredes`, `GestorPaginaTest.test_inicio_sem_microrredes`, E2E `multi` |
| 2–4 criar uma / várias; listar após reinício | `test_criar_varias_e_listar_apos_reinicio_em_novo_processo` (novo processo), `test_criar_varias_pelo_gestor...`, E2E `multi` → reinício → `reinicio` |
| 5–7 isolamento de equipamentos, revisões, blobs, rodadas e procedência | `IsolamentoTest` (snapshot lógico completo de B inalterado), `RodadaPorMicrorredeTest`, `SimulacaoPorMicrorredeTest` |
| 8–9 troca na mesma sessão / sessões diferentes | `IsolamentoSessaoTest` (todas as chaves `mg_*`/`orq_*`/diálogos/console V1.6 limpas; duas sessões simultâneas), E2E (A não mostra equipamentos de B) |
| 10 especificação idêntica sem misturar resultados | cópia independente com a MESMA `spec_fingerprint`: procedência com UIDs distintos; rodada de A não aparece em B; resultado de A injetado em B é sinalizado "de OUTRA microrrede" |
| 11 comissionamento incompleto retomado | `test_criar_varias_pelo_gestor_e_retomar_comissionamento`, `test_comissionamento_retomado_apos_reinicio`, E2E (A reabre na etapa 02) |
| 12–13 ZIP e PDF pelo Gestor sem abrir | `test_zip_contem_somente_a_microrrede_escolhida`, `test_pdf_de_microrrede_nao_ativa_sem_abri_la`, `test_zip_e_pdf_pelo_gestor_sem_abrir...`, E2E (downloads; barra continua "Nenhuma microrrede aberta") |
| 14–15 importação com nova identidade; duplicada com escolha explícita | `ExportacaoImportacaoTest` (nova, cópia com `copied_from`, restauração com histórico, recusa de sobrescrita), E2E (diálogo de conflito → cópia) |
| 16–17 exclusão definitiva; A não altera B | `ExclusaoTest`, `test_restaurar_reverter_e_excluir_A_nao_alteram_B`, `test_exclusao_exige_nome_exato...`, `test_exclusao_protegida_por_credencial`, `test_exclusao_desativada_por_padrao`, E2E (nome errado não libera; diretório removido) |
| 18 microrrede excluída por outra sessão | `test_microrrede_excluida_por_outra_sessao_volta_ao_gestor`, `test_sessao_com_armazenamento_em_cache_nao_recria...` |
| 19–21 migração do banco anterior, interrupção, WAL | `AdocaoLegadoTest` (v2 e v1 reais, original byte a byte intacto, WAL pendente + leitor aberto, interrupção na verificação e no rename, concorrência, arquivo corrompido, banco vazio), E2E `legado` |
| 22 backups formato 1 e 2 | `test_backups_formato_1_e_2` (fixture v1 real) |
| 23 regressão do Piso 1 | suíte completa + E2E `e2e_piso1_microrrede.js` (66/66) |
| 24–25 rodada EMS real numa microrrede selecionada; preservação numérica | `test_duas_microrredes_identicas...` (despacho e custo = V1.6), `test_rodada_ems_real_e_resultados_nao_vazam...`, E2E `reabrir` |

**Chromium real:**
* `tools/e2e/e2e_gestor_microrredes.js` (servidor com `SEEDS2_DEV_MODE=1`, diretório vazio): `multi` 39 +
  `reinicio` (após reiniciar o servidor) 6 + `tablet` 2 + `legado` 5 = **52 verificações aprovadas**, sem
  exceções nem erros de JavaScript. Percurso: Gestor vazio → Criar A → configurar A → TROCAR → Criar B →
  configurar B → Abrir A → Exportar A (ZIP) → PDF de B → Importar A como cópia → Excluir B → Reabrir A.
* `tools/e2e/e2e_piso1_microrrede.js` (agora a partir do Gestor): `comissionar` 41 + `reabrir` 21 + `tablet` 4
  = **66 aprovadas** (rodada EMS real, backup/restauração, resultado obsoleto, tablet, tema escuro).

Defeitos encontrados e corrigidos nesta verificação: troca simultânea de `journal_mode=WAL` em base nova
respondia "database is locked" sem passar pelo `busy_timeout` (aberturas concorrentes) → `ensure_wal` com espera
limitada; teste do PR #4 dependente do instante da migração (instável em suíte lenta); botão IMPORTAR truncado
em tablet; ponto vazio do indicador de salvamento no Gestor; cor do botão de exclusão.

Limitações: as capturas `fullPage` registram só a área visível (Streamlit rola num contêiner interno);
o AppTest não executa o JavaScript dos componentes (o botão TROCAR é simulado pelo mesmo sinal do componente
nos testes de interface e clicado de verdade no E2E) nem permite upload (importação pela interface coberta
no E2E e no backend). Duas falhas intermitentes de sincronização do roteiro E2E (clique durante re-renderização,
servidor recém-reiniciado) foram tratadas com esperas explícitas pelo estado esperado — sem afrouxar asserções.

## 0. Refinamento do Piso 1

**Suíte:** `python -m pytest tests/ -q` → **163 passed, 0 failed, 0 skipped** (+105 subtests; 7 avisos SLSQP
pré-existentes).

| Arquivo | Testes | Cobertura principal |
|---|---|---|
| testes V1.6 pré-existentes | 63 | modelos, EMS, ponte, console V1.6 (sem alteração de tolerâncias) |
| `test_seeds2_microgrid.py` | 40 | persistência, backups maliciosos, restauração atômica, adaptador, rodada EMS real (portados para o documento v2) |
| `test_seeds2_refinamento.py` | 33 | FV por arranjo (STC, heterogêneos, kWp declarado sem módulo inventado, sujeira padrão), curvas eólicas dos dados originais, bateria por datasheet (estimativas, SOC 20/80 sugerido, taxa C só com I+Ah, SOC0 como condição da rodada), importação ModelLab (pacote real, adulterado/inválido rejeitado, blob no backup, pendente de integração), balanço lógico (sem acoplamentos; usina parcial), **migrações a partir de dados v1 reais** (documento, backup formato 1, banco SQLite v1 com `.bak-v1` e histórico, documento inválido não corrompe; cópia `.bak-v1` consistente com WAL, leitor aberto, falha/rollback, concorrência, espera limitada), **rodada EMS com config migrada = V1.6**, PDF (seções, valores exatos, "Não declarado", PRELIMINAR, sem `None`/`nan`), geolocalização (concedida, negada, indisponível, insegura, tempo esgotado, coordenadas inválidas, procedência navegador × manual) |
| `test_seeds2_app.py` | 27 | AppTest: cartões da etapa 01, catálogo → editor → confirmação de pendência, FV com vários arranjos, edição direta, balanço sem acoplamentos e aviso de compra da rede, exportações, Gestão, Simulação/condições da rodada, inserções HTML |

**Navegador real (Chromium)**, `tools/e2e/e2e_piso1_microrrede.js`, a partir de diretório de dados vazio,
com reinício do servidor entre `comissionar` e `reabrir`: **64 verificações aprovadas** (40 + 20 + 4), sem
exceções Streamlit nem erros de JavaScript. Inclui: geolocalização concedida (uma única leitura, só após o
clique, precisão ±28 m, cidade/endereço não inferidos, edição manual), negada e indisponível (emuladas);
catálogo com 5 cartões e "Voltar às tecnologias"; usina com arranjo por módulos (11,80 kWp STC) + arranjo
declarado (total 15,30 kWp); curva eólica Plotly com pontos tabulados × interpolação e curva digitalizada
rotulada; bateria por datasheet com SOC 20/80 e confirmação "Equipamento com configuração pendente" (voltar
preserva os dados; salvar como pendente); link do ModelLab (`target=_blank`); balanço lógico sem
topologia e aviso "déficit ≠ compra da rede"; ZIP e PDF PRELIMINAR baixados na etapa 05; após reinício,
edição direta da bateria (configuração avançada), SOC inicial como condição da rodada, rodada EMS real com
exclusão confirmada (arranjo declarado), PDF ativado, backup/restauração, arquivo inválido rejeitado,
resultado obsoleto após mudança; tablet retrato/paisagem sem rolagem horizontal (Início, Gestão, Balanço);
tema escuro. Capturas inspecionadas visualmente; o PDF foi revisado página a página.

**Auditoria do PR #4 — cópia `.bak-v1` com WAL.** `MigracaoWalTest` (5 testes) monta um banco v1 realista (fixture v1 + CSV)
com todas as transações ainda no `-wal` (gravador aberto, checkpoint desligado) e verifica: o `.db` sozinho não contém os dados
(pré-condição do defeito); com um **leitor com transação aberta**, a migração conclui em < 5 s, a cópia aberta sozinha em outro
diretório passa em `integrity_check`, está em journal `delete`, `user_version = 1`, contém microrrede, revisões 1–2, blob (SHA-256)
e rodada, e restaurada é migrada pelo SEEDS2 para o mesmo estado; o leitor mantém seu instantâneo e depois vê a migração; o
gravador original volta a gravar (sem bloqueio residual); falha injetada após a cópia → rollback completo, cópia íntegra, nova
abertura migra uma vez; 3 aberturas concorrentes → uma única revisão `migration`, reabrir não reescreve a cópia; gravador
concorrente é serializado e seu commit consta na cópia; espera da cópia limitada (erro em ~0,5 s, sem `.tmp`). Com o código
anterior (`shutil.copy2`) estes testes falham.
Após a correção, a suíte completa (163 passed) e o E2E completo em Chromium (64/64, com reinício do servidor) foram
reexecutados.

Defeitos encontrados e corrigidos nesta verificação: mensagem de geolocalização duplicada (componente JS +
Python); usina parcialmente representada rotulada como "Configuração incompleta" no esquema lógico (novo
estado "Parcialmente representado"); título de seção órfão no fim de página do PDF; textos truncados sem
reticências no PDF; `st.rerun(scope="fragment")` inválido dentro do diálogo.

Limitação conhecida das capturas: a página Streamlit rola num contêiner interno, então `fullPage` registra
apenas a área visível; partes longas foram capturadas por elemento (p. ex. a curva eólica).

As seções 1–3 abaixo descrevem a verificação do Piso 1 original (PR #3) e permanecem como histórico.

## 1. Suíte automatizada

```bash
pip install -r requirements.txt pytest
python -m pytest tests/ -q
```

Resultado (revisão do PR #3, executado duas vezes, idêntico): **120 passed, 0 failed, 0 skipped**
(+94 subtests), 7 avisos `RuntimeWarning` do SLSQP (scipy), já existentes na base.

| Arquivo | Testes | Cobertura |
|---|---|---|
| testes V1.6 pré-existentes (9 arquivos) | 63 | modelos físicos, EMS, ponte, console V1.6 (agora dentro de Simulação) |
| `test_seeds2_microgrid.py` | 40 | persistência com reabertura (nova instância e **novo processo**), identidade única, conflitos, imutabilidade, migração recusada, blobs, rodadas, validação física/IDs/referências, inventário, backup/restauração (inclui 8 importações inválidas), adaptador, **rodada EMS real com config persistida = despacho V1.6**; backups maliciosos (ZIP malformado/truncado/criptografado, bombas, tamanho declarado falso, entradas demais/duplicadas, ~20 manifestos com tipos errados, configurações estruturalmente incorretas, entradas não declaradas); **restauração atômica** (conflito + blobs novos, identidade não confirmada, falha na gravação) |
| `test_seeds2_app.py` | 17 | AppTest: 1º acesso, comissionamento completo + reabertura, retomada após reinício, registro sem parâmetros, edição/descartar/conflito em Gestão, incorporar/retirar, validação na UI, backup, transferência ao orquestrador + rodada registrada, exclusões com confirmação, alteração manual detectada, bloqueio sem demanda, resultados obsoletos, bancadas; **inserção HTML/Markdown** (nome de equipamento e nome de CSV maliciosos exibidos como texto; testes falham com o código anterior) |

Proteções: `tests/conftest.py` redireciona `SEEDS2_DATA_DIR` para um diretório temporário — a suíte
nunca usa `~/.seeds2`.

Os resultados numéricos dos modelos não mudaram: os 63 testes originais (incluindo os numéricos)
passam sem alteração de tolerâncias, e `RodadaIntegradaTest` compara o despacho (`P_kW`) e o custo
total da rodada vinda do SQLite com os da configuração padrão da V1.6 (`assert_allclose`).

Com o helper de testes atualizado, os 63 testes V1.6 também passam com Streamlit 1.49.1 (antes da
inclusão do shell SEEDS2); a aplicação SEEDS2 exige 1.66.1 (`st.components.v2`).

## 2. Navegador real (Playwright/Chromium)

Script: `tools/e2e/e2e_piso1_microrrede.js` (fases `comissionar` → **reinício do servidor** →
`reabrir` → `tablet`). Executado a partir de um diretório de dados vazio:

```bash
export SEEDS2_DATA_DIR=$(mktemp -d)
streamlit run app.py --server.headless true --server.port 8601 &
node tools/e2e/e2e_piso1_microrrede.js http://localhost:8601/ comissionar tools/e2e/out
# parar e reiniciar o servidor com o MESMO SEEDS2_DATA_DIR, depois:
node tools/e2e/e2e_piso1_microrrede.js http://localhost:8601/ reabrir tools/e2e/out
node tools/e2e/e2e_piso1_microrrede.js http://localhost:8601/ tablet tools/e2e/out
```

Resultado: todas as verificações aprovadas, sem exceções Streamlit nem erros de JavaScript:

- 1º acesso abre o comissionamento; cartão "+" do componente de inventário abre o diálogo;
  procedência da referência exibida; stepper navega entre etapas; topologia gerada dos dados;
  ativação leva ao Início.
- Após **parar e reiniciar o servidor**: abre a mesma microrrede, sem repetir o assistente; Gestão
  mostra os equipamentos persistidos; indicador "Alterações pendentes" → "Salvo"; rodada EMS real
  com o resultado identificando a revisão; backup baixado (nome ASCII), inspecionado e restaurado;
  arquivo inválido rejeitado; conteúdo restaurado idêntico mantém o resultado válido; alteração
  posterior marca o resultado como "configuração anterior".
- Tablet 820×1180 e 1180×820 sem rolagem horizontal; capturas em tema escuro.

Revisão do PR #3: percurso repetido do zero (comissionar → reinício → reabrir → tablet), todas as
verificações aprovadas; o painel "Configuração aplicada" é aberto e verificado na Simulação. Capturas a
2× (deviceScaleFactor) entregues ao responsável. A captura lado a lado do PEMFC ModelLab não foi gerada
neste ambiente (execução do código de outro repositório não autorizada); pode ser feita localmente.

Defeitos encontrados e corrigidos durante a verificação em navegador: nome de backup com acentos
era salvo como `download` pelo Chromium (passou a ser ASCII); esquema de topologia ampliado além
do tamanho natural e rótulo do barramento sobreposto; avisos de procedência sem estilo sobre o
console V1.6.

## 3. Procedimento manual sugerido

1. `export SEEDS2_DATA_DIR=/caminho/fora/do/repositorio` e `streamlit run app.py`.
2. Comissionamento: cartões de identificação/localização (teste "LOCALIZAÇÃO AUTOMÁTICA") → equipamentos
   pelo catálogo (deixe um incompleto para ver a confirmação de pendência) → balanço lógico/conexão com a rede
   → demanda walk-forward → revisão (exporte ZIP e PDF) → ativar.
3. Feche o navegador, **reinicie o servidor**, abra de novo: deve entrar no Início da mesma microrrede.
4. Gestão → altere um parâmetro → observe "Alterações pendentes" → Salvar → Histórico mostra a revisão.
5. Adicione a uma usina FV um arranjo com outro módulo ou só com kWp declarado → Simulação mostra os
   arranjos fora da rodada e exige confirmação; rode e veja a exclusão registrada em Histórico → Rodadas.
6. Altere a configuração e volte a Resultados: aviso "Resultado de configuração anterior".
7. Relatório, histórico e backups → gere o PDF, exporte, altere algo, restaure; tente restaurar um arquivo qualquer (rejeitado).
8. Início → Bancadas individuais → abra uma bancada e volte por "← FONTES DE ENERGIA".
