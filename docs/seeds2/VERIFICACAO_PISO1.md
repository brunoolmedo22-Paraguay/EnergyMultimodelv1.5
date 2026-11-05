# SEEDS2 — Verificação do Piso 1

Ambiente da verificação: Linux, Python 3.13.18, `requirements.txt` desta branch (Streamlit 1.66.1),
Chromium/Playwright para os testes em navegador. Data: 2026-11-05.

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
2. Comissionamento: nome → equipamentos (deixe um sem parâmetros para ver "Faltam …") → barramento →
   demanda walk-forward → revisão → ativar.
3. Feche o navegador, **reinicie o servidor**, abra de novo: deve entrar no Início da mesma microrrede.
4. Gestão → altere um parâmetro → observe "Alterações pendentes" → Salvar → Histórico mostra a revisão.
5. Adicione um arranjo FV com outro módulo → Simulação mostra ambos como "Não representável" e exige
   confirmação; rode e veja a exclusão registrada em Histórico → Rodadas.
6. Altere a configuração e volte a Resultados: aviso "Resultado de configuração anterior".
7. Histórico e backups → exporte, altere algo, restaure; tente restaurar um arquivo qualquer (rejeitado).
8. Início → Bancadas individuais → abra uma bancada e volte por "← FONTES DE ENERGIA".
