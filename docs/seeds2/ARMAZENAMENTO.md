# SEEDS2 — Armazenamento local, backups e implantação

## Decisão

**SQLite** local, no servidor onde o SEEDS2 está instalado. Motivos: arquivos únicos, transações ACID, sem
serviço externo, adequado a poucas escritas e algumas sessões simultâneas. Nada é guardado só no navegador ou
só no `st.session_state`.

**Gestor de microrredes (várias microrredes por instalação):** um **catálogo central** + **um banco SQLite
independente por microrrede**. Cada banco de microrrede é o mesmo `MicrogridStore` do Piso 1 (com a garantia
`CHECK (id = 1)`), apenas num diretório próprio — nenhum contrato SQLite foi reconstruído. Editar, restaurar,
reverter ou excluir a microrrede A nunca toca os arquivos da microrrede B.

```
SEEDS2_DATA_DIR/                      (padrão ~/.seeds2; fora do repositório)
├── registry.db                       catálogo: uid, estado (ready/deleting), origem, data, procedência da cópia
├── microgrids/
│   ├── <uid-A>/seeds2.db             configuração, inventário, arranjos FV, CSV e dispositivos PEMFC (blobs),
│   │                                 revisões, condições da rodada, rodadas do EMS, cópias .bak-v<N>
│   ├── <uid-B>/seeds2.db
│   └── <uid-C>/seeds2.db
├── .staging/<op>/                    preparação de criar/importar/copiar/adotar (descartada se interrompida)
├── .trash/<uid>-<t>/                 exclusão em andamento (esvaziada na conclusão ou na próxima abertura)
└── seeds2.db                         armazenamento ANTERIOR ao Gestor (somente leitura; adotado uma vez)
```

* Identidade: `installation.uid` (32 hex, imutável) é a chave do catálogo e o nome do diretório. Nomes podem
  repetir-se (a interface mostra o ID). **Nenhum texto do usuário vira caminho**: diretórios são derivados só do
  UID validado; nomes fora do padrão em `microgrids/` nunca são tocados.
* `MicrogridStore(..., must_exist=True)` nunca recria uma microrrede excluída; `fixed_uid` recusa gravar o
  documento de outra microrrede (sem "troca de identidade" dentro de um armazenamento do catálogo).

## Localização

| Variável | Padrão | Observação |
|---|---|---|
| `SEEDS2_DATA_DIR` | `~/.seeds2` | diretório-base do catálogo e das microrredes, fora do código versionado |
| `SEEDS2_ADMIN_PASSWORD` | (vazio) | credencial exigida para a **exclusão definitiva** (ou `seeds2_admin_password` em Streamlit Secrets) |
| `SEEDS2_DEV_MODE` | (vazio) | `1` = modo de desenvolvimento LOCAL: exclusão sem credencial (somente se nenhuma credencial estiver configurada) |

O `.gitignore` bloqueia `*.db`, `*.sqlite*`, `*.seeds2backup.zip`, `seeds2_data/` e `.seeds2/`.
A interface mostra o caminho em uso (Gestor, comissionamento, Gestão → Instalação, Alcance).

## Catálogo (`registry.db`, `PRAGMA user_version` = 1)

| Tabela | Conteúdo |
|---|---|
| `microgrids` | `uid` (PK, CHECK 32 hex), `state` (`ready` / `deleting`), `origin` (`new`, `legacy`, `import`, `copy`), `created_at`, `source_uid` e `source_fingerprint` (cópias), `note` |
| `meta` | `legacy_adoption` (resultado da adoção do armazenamento anterior: `done` / `empty`, com contagens) |

O catálogo não guarda dados técnicos: tarjetas do Gestor são calculadas da configuração salva de cada
microrrede (`registry.card_summary`).

### Operações com vários arquivos (recuperáveis)

Não existe transação única entre bancos SQLite e o sistema de arquivos; por isso cada operação tem
**preparação** e **confirmação**, e `MicrogridRegistry.recover()` conclui qualquer interrupção na abertura:

| Operação | Preparação | Confirmação (sob `BEGIN IMMEDIATE` do catálogo) | Interrupção |
|---|---|---|---|
| Criar (etapa 01 do comissionamento) | banco montado e verificado em `.staging/<op>` | `rename(.staging → microgrids/<uid>)` + `INSERT` | antes do COMMIT: nada no catálogo; diretório órfão → `.trash` |
| Importar (nova / cópia) | `inspect_backup_data` + `import_inspected` em `.staging` | idem | idem |
| Restaurar na existente | — | nova revisão na própria microrrede (transação SQLite) | rollback |
| Excluir | (aguarda gravação em andamento na microrrede) | `state = deleting` → `rename → .trash` → `DELETE` → esvaziar `.trash` | microrrede já invisível; `recover()` conclui |

Preparações abandonadas em `.staging` são descartadas após 1 h (nunca as de outra operação em curso).

### Adoção do armazenamento anterior ao Gestor

Na primeira abertura do catálogo, se existir `SEEDS2_DATA_DIR/seeds2.db` com uma microrrede:
1. cópia **somente leitura** e consistente com WAL pela API de backup do SQLite (o arquivo original não é
   alterado — nem checkpoint);
2. abertura da CÓPIA pelo `MicrogridStore` (migrações v1→v2 do banco/documento aplicadas na cópia, com
   `.bak-v1` dentro do diretório da microrrede);
3. verificação: mesma identidade, revisões ≥ originais, mesmos blobs e rodadas;
4. confirmação (rename + `INSERT origin = legacy` + `meta.legacy_adoption`) sob o bloqueio do catálogo.
Qualquer falha → erro claro, **nenhuma microrrede criada**, original intacto e nova tentativa na próxima
abertura. A adoção não se repete (nem depois de excluir a microrrede adotada). O `seeds2.db` original fica como
respaldo verificável; pode ser removido manualmente depois de conferido. Banco anterior vazio → catálogo vazio.

## Banco de cada microrrede (`PRAGMA user_version` = 2)

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
- Faça backups periódicos (Gestor → ZIP em cada tarjeta, ou Gestão → Relatório, histórico e backups) e guarde-os
  fora do servidor.
- **Exclusão definitiva** (Gestor): diálogo com nome, ID, equipamentos, revisões e rodadas, opção de baixar o ZIP
  antes, e confirmação digitando o nome exato. Em implantação compartilhada configure `SEEDS2_ADMIN_PASSWORD`
  (variável de ambiente) ou `seeds2_admin_password` em `.streamlit/secrets.toml` (fora do repositório): a
  credencial é verificada no servidor, em tempo constante, e nunca é enviada ao navegador. Sem credencial, a
  exclusão fica **desativada**, exceto com `SEEDS2_DEV_MODE=1` (uso local explícito).
- Não publique o banco, backups ou CSVs da empresa em repositórios.
- Uma instância do SEEDS2 administra várias microrredes (catálogo). Sem contas: todas as sessões veem o mesmo
  catálogo; a microrrede **ativa** é escolhida por sessão de navegador. Uma sessão que tinha aberta uma
  microrrede excluída por outra sessão volta ao Gestor sem recriá-la.

## Importação de dispositivos do PEMFC ModelLab

`seeds2/microgrid/modellab.py` trata o arquivo como não confiável: `.pmldevice.zip` (≤ 25 MiB, ≤ 2000
entradas, ≤ 20 MiB por entrada, ≤ 80 MiB descomprimidos contados em blocos, nomes `records/<tipo>/<id>.json`
e `blobs/<sha256>`, hashes canônicos dos registros conferidos com o manifesto `pemfc-modellab/workspace`)
ou `profile.json` (`pemfc-modellab/profile`). O original é gravado como blob somente ao confirmar o
equipamento e passa a fazer parte dos backups. Nenhuma sincronização ou conexão com o ModelLab.
