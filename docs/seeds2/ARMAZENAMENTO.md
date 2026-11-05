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

## Esquema do banco (`PRAGMA user_version` = 2)

| Tabela | Conteúdo |
|---|---|
| `microgrid` | **uma** linha (`CHECK (id = 1)`): documento atual, revisão, impressão digital, uid |
| `revisions` | snapshots completos imutáveis (triggers bloqueiam UPDATE/DELETE), nota e origem (`commissioning`, `edit`, `restore`, `revert`, `migration`, `run_conditions`) |
| `blobs` | CSVs importados e pacotes originais do PEMFC ModelLab (conteúdo + SHA-256 verificado na leitura) |
| `simulation_runs` | procedência de cada rodada: revisão, impressões digitais, origem, exclusões, resumo |
| `meta` | registro de migrações |

## Garantias

- **Transações:** `BEGIN IMMEDIATE` + WAL + `busy_timeout`; validação completa antes de gravar.
- **Concorrência otimista:** cada sessão salva sobre a revisão-base; se outra sessão gravou antes,
  `ConflictError` — nada é sobrescrito; a interface oferece recarregar a revisão salva.
- **Sem revisões vazias:** salvar conteúdo idêntico não cria revisão.
- **Proteção contra perda:** histórico imutável + "Reverter" (cria nova revisão com o conteúdo antigo).
- **Integridade referencial:** a configuração não pode referenciar blobs inexistentes.
- **Migrações do banco:** `PRAGMA user_version` + lista ordenada `MIGRATIONS` (+ passos Python em
  `MIGRATION_STEPS`); banco de versão mais nova que o software é recusado sem alteração. Uma única
  transação `BEGIN IMMEDIATE` cobre cópia + todas as migrações pendentes: a versão é relida sob o bloqueio
  (aberturas concorrentes migram uma única vez) e qualquer falha desfaz tudo.
  - **Cópia `seeds2.db.bak-v<N>`** antes de migrar um banco existente: feita pela **API de backup do SQLite**
    (`Connection.backup`, um único passo/instantâneo) numa conexão própria, enquanto a migração mantém o
    bloqueio de escrita — inclui o conteúdo ainda no `-wal` (uma cópia do arquivo `.db` não incluiria) e é
    exatamente o estado migrado. Leitores abertos não bloqueiam (WAL); a espera por bloqueios é limitada
    (`BACKUP_COPY_TIMEOUT_S`); a cópia é um arquivo autossuficiente (journal `DELETE`, sem `-wal`/`-shm`),
    verificada com `PRAGMA integrity_check` e publicada atomicamente (`.tmp` → `os.replace`).
  - **v1 → v2 (refinamento do Piso 1):** sem mudança de tabelas; o documento atual é migrado (v1 → v2) e
    gravado como **nova revisão** (origem `migration`, nota com o resumo). Se a migração ou a validação
    falhar, a transação é desfeita e o banco permanece na v1 (`StoreError`, nada corrompido). Revisões
    antigas continuam intactas (imutáveis) e são migradas **na leitura** (histórico, reverter, backup).
- **Documento versionado:** `schema_version` do documento (atual: 2; v1 aceito e migrado por
  `seeds2/microgrid/migrations.py`); versões desconhecidas são rejeitadas. A migração nunca descarta valores
  conhecidos: o que não pode ser reinterpretado (topologia v1) vai para `legacy` e é sinalizado.

## Backup (`.seeds2backup.zip`) — formato 2

```
manifest.json      formato, versões (backup/banco/documento/app), uid, revisão, impressão digital,
                   SHA-256 de cada arquivo, metadados dos blobs
configuration.json documento da configuração (v2)
history.json       metadados das revisões (sem documentos)
blobs/<sha256>     CSVs importados e pacotes originais do PEMFC ModelLab referenciados pela configuração
```

O mesmo arquivo é oferecido como "EXPORTAR CONFIGURAÇÃO DA MICRORREDE (ZIP)" na etapa 05 e em Gestão.
Backups do **formato 1** (Piso 1 original, documento v1) continuam aceitos: a configuração é migrada para
v2 na inspeção (`BackupInspection.migrated`) e a restauração grava o documento já migrado. Verificado com um
backup v1 real (`tests/fixtures/seeds2_backup_v1_piso1.zip`).

Nome do arquivo ASCII (acentos transliterados) para portabilidade.

## Restauração

1. **Inspeção de arquivo não confiável** (`inspect_backup`, nunca levanta exceção — todo defeito vira
   mensagem de rejeição):
   - limites: ≤ 64 entradas; ≤ 8 MiB por JSON; ≤ 50 MiB por blob; ≤ 256 MiB descomprimidos no total,
     **contados lendo os dados em blocos** (o tamanho declarado no ZIP não é confiável — proteção
     contra *zip bombs*); arquivo de entrada ≤ 256 MiB;
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

## Importação de dispositivos do PEMFC ModelLab

`seeds2/microgrid/modellab.py` trata o arquivo como não confiável: `.pmldevice.zip` (≤ 25 MiB, ≤ 2000
entradas, ≤ 20 MiB por entrada, ≤ 80 MiB descomprimidos contados em blocos, nomes `records/<tipo>/<id>.json`
e `blobs/<sha256>`, hashes canônicos dos registros conferidos com o manifesto `pemfc-modellab/workspace`)
ou `profile.json` (`pemfc-modellab/profile`). O original é gravado como blob somente ao confirmar o
equipamento e passa a fazer parte dos backups. Nenhuma sincronização ou conexão com o ModelLab.
