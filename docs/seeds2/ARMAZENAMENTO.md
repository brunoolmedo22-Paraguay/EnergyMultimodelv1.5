# SEEDS2 — Armazenamento local, backups e implantação

## Decisão

**SQLite** local, no servidor onde o SEEDS2 está instalado (`seeds2/microgrid/store.py`).
Motivos: arquivo único, transações ACID, sem serviço externo, adequado a uma única microrrede
com poucas escritas e algumas sessões simultâneas. Nada é guardado só no navegador ou só no
`st.session_state`.

## Localização

| Variável | Padrão | Observação |
|---|---|---|
| `SEEDS2_DATA_DIR` | `~/.seeds2` | diretório do banco `seeds2.db`, fora do código versionado |

O `.gitignore` bloqueia `*.db`, `*.sqlite*`, `*.seeds2backup.zip`, `seeds2_data/` e `.seeds2/`.
A interface mostra o caminho em uso (comissionamento, Gestão → Instalação, Alcance).

## Esquema (v1)

| Tabela | Conteúdo |
|---|---|
| `microgrid` | **uma** linha (`CHECK (id = 1)`): documento atual, revisão, impressão digital, uid |
| `revisions` | snapshots completos imutáveis (triggers bloqueiam UPDATE/DELETE), nota e origem (`commissioning`, `edit`, `restore`, `revert`) |
| `blobs` | CSVs importados (conteúdo + SHA-256 verificado na leitura) |
| `simulation_runs` | procedência de cada rodada: revisão, impressões digitais, origem, exclusões, resumo |
| `meta` | registro de migrações |

## Garantias

- **Transações:** `BEGIN IMMEDIATE` + WAL + `busy_timeout`; validação completa antes de gravar.
- **Concorrência otimista:** cada sessão salva sobre a revisão-base; se outra sessão gravou antes,
  `ConflictError` — nada é sobrescrito; a interface oferece recarregar a revisão salva.
- **Sem revisões vazias:** salvar conteúdo idêntico não cria revisão.
- **Proteção contra perda:** histórico imutável + "Reverter" (cria nova revisão com o conteúdo antigo).
- **Integridade referencial:** a configuração não pode referenciar blobs inexistentes.
- **Migrações:** `PRAGMA user_version` + lista ordenada `MIGRATIONS`; antes de migrar um banco
  existente é feita a cópia `seeds2.db.bak-v<N>`; banco de versão mais nova que o software é recusado.
- **Documento versionado:** `schema_version` do documento (v1); versões desconhecidas são rejeitadas.

## Backup (`.seeds2backup.zip`)

```
manifest.json      formato, versões (backup/banco/documento/app), uid, revisão, impressão digital,
                   SHA-256 de cada arquivo, metadados dos blobs
configuration.json documento da configuração
history.json       metadados das revisões (sem documentos)
blobs/<sha256>     CSVs importados
```

Nome do arquivo ASCII (acentos transliterados) para portabilidade.

## Restauração

1. **Inspeção de arquivo não confiável** (`inspect_backup`, nunca levanta exceção — todo defeito vira
   mensagem de rejeição):
   - limites: ≤ 16 entradas; ≤ 8 MiB por JSON; ≤ 50 MiB por CSV; ≤ 124 MiB descomprimidos no total,
     **contados lendo os dados em blocos** (o tamanho declarado no ZIP não é confiável — proteção
     contra *zip bombs*); arquivo de entrada ≤ 124 MiB;
   - estrutura: nomes permitidos apenas (`manifest.json`, `configuration.json`, `history.json`,
     `blobs/<sha256>`), sem duplicatas, diretórios, caminhos externos, criptografia ou compressão
     diferente de *stored/deflate*;
   - manifesto: tipo e formato de **todos** os campos validados antes do uso (versões inteiras, uid e
     hashes hexadecimais, textos limitados, `files`/`blobs` com estrutura esperada);
   - conteúdo: hashes de todas as entradas, impressão digital, uid do manifesto = uid da configuração,
     validação estrutural e física da configuração (estruturas inesperadas viram erro, não exceção),
     somente blobs referenciados e todos presentes.
2. Confirmação explícita obrigatória; se o backup for de **outra instalação**, segunda confirmação
   (troca de identidade).
3. **Atômica:** dados de entrada e configuração são gravados na **mesma transação** (`_write_revision`).
   Conflito de revisão, troca de identidade não confirmada ou qualquer falha de gravação desfazem tudo
   (nenhum blob órfão). Em caso de sucesso, grava nova revisão (`origin = restore`), preservando o histórico.
4. Importações inválidas ou incompatíveis são rejeitadas sem alterar nada.
5. Textos vindos do backup (nome da instalação, versão, mensagens) são exibidos como texto literal.

## Implantação empresarial — limitações conhecidas

- **Sem autenticação nem perfis** neste piso: qualquer pessoa com acesso à aplicação pode alterar a
  configuração. Recomenda-se publicar o Streamlit apenas na rede interna, atrás de proxy reverso
  com autenticação (ou VPN), e restringir permissões do diretório `SEEDS2_DATA_DIR` ao usuário do
  serviço.
- Faça backups periódicos (Gestão → Histórico e backups) e guarde-os fora do servidor.
- Não publique o banco, backups ou CSVs da empresa em repositórios.
- Uma instância por microrrede: para outra instalação, use outro `SEEDS2_DATA_DIR` em outro
  servidor/serviço (não há seletor de microrredes por desenho).
