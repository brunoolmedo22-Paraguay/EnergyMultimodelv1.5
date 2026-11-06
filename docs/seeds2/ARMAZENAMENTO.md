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
├── .quarantine/<uid>-<t>/            diretórios sem linha no catálogo (preservados; nunca apagados sozinhos)
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

## Catálogo (`registry.db`, `PRAGMA user_version` = 2)

| Tabela | Conteúdo |
|---|---|
| `microgrids` | `uid` (PK, CHECK 32 hex), `state` (`ready` / `deleting`), `origin` (`new`, `legacy`, `import`, `copy`), `created_at`, `source_uid` e `source_fingerprint` (cópias), `note`, `incarnation` (v2 — hotfix H-01) |
| `meta` | `legacy_adoption` (resultado da adoção do armazenamento anterior: `done` / `empty`, com contagens) |

O catálogo não guarda dados técnicos: tarjetas do Gestor são calculadas da configuração salva de cada
microrrede (`registry.card_summary`).

### Operações com vários arquivos (recuperáveis)

Não existe transação única entre bancos SQLite e o sistema de arquivos; por isso cada operação tem
**preparação** e **confirmação**, e `MicrogridRegistry.recover()` conclui qualquer interrupção na abertura:

| Operação | Preparação | Confirmação | Interrupção |
|---|---|---|---|
| Criar (etapa 01 do comissionamento) | banco montado, verificado e com `meta.incarnation` em `.staging/<op>` | sob L1: checagem de UID duplicado → `rename(.staging → microgrids/<uid>)` → `INSERT` (com incarnação) → COMMIT; falha no INSERT/COMMIT desfaz o rename | antes do COMMIT: nada no catálogo; diretório sem linha → `.quarantine` (preservado) |
| Importar como nova / cópia | `inspect_backup_data` + `import_inspected` em `.staging` | idem (o UID é revalidado sob L1: duas importações simultâneas do mesmo UID → uma única entrada) | idem |
| Restaurar na existente | — | nova revisão na própria microrrede (transação L2 com checagem de lápide/incarnação) | rollback |
| Adotar o `seeds2.db` anterior | cópia somente leitura + migração + verificação em `.staging` | sob L1, como "criar" + `meta.legacy_adoption` | nada confirmado; original intacto; nova tentativa na próxima abertura |
| Excluir (H-01) | — | lápide (L2) → `deleting` (L1) → `rename → .trash` + `DELETE` (L1) → esvaziar `.trash` | `recover()` conclui somente exclusões com lápide confirmada |

Preparações abandonadas em `.staging` são descartadas após 1 h (nunca as de outra operação em curso).
`recover()` é idempotente: reexecutá-la (reinícios repetidos, vários processos) não remove nada além do que
já estava em exclusão confirmada. Sessões abertas em OUTRAS microrredes durante a recuperação não são afetadas.

### H-01 — Exclusão concorrente de microrredes

**Defeito original (PR #5 até `ad1d736`).** `delete()` verificava gravações em andamento com
`BEGIN IMMEDIATE` + `ROLLBACK` no banco da microrrede e soltava o bloqueio; só depois marcava `deleting` e
movia o diretório. Uma gravação de outra sessão nesse intervalo era **confirmada e depois perdida em silêncio**
(reproduzido: `save()` devolveu a revisão 2 e a microrrede desapareceu). Além disso, `deleting` impedia novas
aberturas pelo catálogo, mas instâncias `MicrogridStore` já abertas (cache das sessões) continuavam operando;
e uma microrrede excluída e reimportada com o MESMO UID podia receber a edição pendente de uma sessão antiga.

**Mecanismo corretivo — lápide transacional + incarnação.** O único ponto de serialização das gravações de
uma microrrede é o bloqueio de escrita do SEU banco (L2). A exclusão grava a **lápide** `meta.lifecycle` sob
esse mesmo bloqueio, e TODA transação do `MicrogridStore` (salvar, restaurar, reverter, blobs, rodadas,
migração) verifica lápide e incarnação **depois** de `BEGIN IMMEDIATE`, na mesma transação. Leituras também
recusam microrredes com lápide. Conexões de microrredes do catálogo usam `mode=rw` (o SQLite nunca recria um
banco vazio). Cada entrada tem `incarnation` (catálogo + `meta` do banco); a sessão fica ligada à incarnação
que abriu.

**Protocolo e ordem de aquisição de bloqueios** (L1 = escrita do `registry.db`; L2 = escrita de uma microrrede;
nunca aninhados — sem impasse; excluir A não toma L2 de nenhuma outra microrrede):

1. checagem: a entrada existe e está `ready`;
2. **lápide (L2)**: `BEGIN IMMEDIATE` espera as gravações em andamento (até `DELETE_LOCK_TIMEOUT_S` = 30 s)
   → `INSERT meta.lifecycle` → COMMIT. Este é o início efetivo da exclusão. Se o bloqueio não for obtido,
   `RegistryError` e **nada** muda;
3. **reivindicação (L1)**: `UPDATE ... SET state = 'deleting' WHERE state = 'ready'` — exatamente um excluidor
   vence; os demais recebem `MicrogridNotFound`;
4. **remoção física (L1)**: `rename(microgrids/<uid> → .trash)` + `DELETE` da linha → COMMIT; `.trash` esvaziado.

**Comportamento diante de falhas**: interrupção após 2 (linha `ready` com lápide), após 3 (`deleting`) ou no
meio de 4 (diretório já em `.trash`, linha `deleting`) → a microrrede já está inacessível; `recover()` (na
próxima abertura do catálogo, em qualquer processo) conclui. Linhas `deleting` sem lápide (versão anterior)
recebem a lápide antes da remoção; se uma gravação longa impedir, a remoção espera a próxima abertura.

**Garantias**: (a) nenhuma gravação é confirmada em silêncio numa microrrede excluída — ou termina antes da
lápide (e a exclusão espera) ou é recusada com `MicrogridDeletedError`; (b) gravações e leituras posteriores,
inclusive de referências antigas e de outros processos, são recusadas sem recriar arquivos; (c) duas exclusões
simultâneas → uma efetiva; (d) restauração concorrente: inteira antes da lápide ou recusada; (e) importações
simultâneas do mesmo UID → uma entrada; (f) referência antiga após excluir e reimportar o mesmo UID → recusada;
(g) a interface volta ao Gestor quando a microrrede aberta é excluída ou substituída, inclusive no meio da
execução de uma página. Provas: `tests/test_seeds2_concorrencia.py` (ver `VERIFICACAO_PISO1.md` §H-01).

**Limites**: a exclusão espera no máximo 30 s por uma gravação em andamento (depois desiste sem alterar nada);
uma sessão que estava editando recebe o erro na próxima ação e volta ao Gestor — a edição pendente não é
gravada (comportamento pretendido: a microrrede deixou de existir).

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

### H-02 — Exclusão vinculada à incarnação (auditoria do PR #5)

**Defeito (reproduzido em `b8f721c`).** `delete(X)` validava X no catálogo e só depois gravava a lápide,
reivindicava e removia — sem conferir QUAL incarnação de X estava tocando. Intercalação: A valida X (incarnação
I1) e para; B exclui X por completo; C reimporta X (incarnação I2); A continua → a lápide caía no banco NOVO, a
reivindicação marcava a NOVA linha e a remoção apagava a microrrede reimportada.

**Correção.** Toda exclusão é vinculada a uma incarnação — a que o usuário via no diálogo
(`expected_incarnation`) ou a atual do catálogo no início:
1. **lápide (L2)**: sob `BEGIN IMMEDIATE` do banco, confere `meta.incarnation`; divergência →
   `StaleDeletionError` (subclasse de `MicrogridNotFound`) e nada é gravado. A lápide registra a incarnação;
2. **reivindicação (L1)**: `UPDATE ... WHERE state = 'ready' AND incarnation = ?`; linha de outra incarnação →
   `StaleDeletionError`;
3. **remoção física (L1)**: só se a linha é `deleting` DESSA incarnação e o banco do diretório é dessa
   incarnação (ou já ausente); `DELETE ... AND incarnation IS ?`;
4. **recuperação**: lápide de linhas `deleting` conferida com a incarnação da linha; linha `ready` só é
   concluída se o banco tem lápide E a mesma incarnação; tudo reconferido sob L1 antes de mover. Lápides
   gravadas pela versão anterior (sem o campo de incarnação) continuam recuperáveis (vale a incarnação do banco).
   Divergência — que o protocolo não produz — nunca resulta em remoção.

Enquanto existe a linha de X (`ready` ou `deleting`), nenhuma importação de X é aceita (UID duplicado conferido
sob L1); por isso a reimportação só acontece depois da remoção completa, e a exclusão tardia de A ou falha
(`StaleDeletionError`) ou encontra a sua incarnação já removida (sucesso, sem tocar na nova). Sem bloqueios
aninhados e sem bloqueio global.

### H-03 — Leituras em transação de instantâneo único

**Defeito (reproduzido em `b8f721c`).** `_read()` verificava a lápide numa consulta em modo autocommit e
consultava os dados em outra: com uma revisão e a lápide confirmadas no meio, a leitura que verificara a
revisão 1 sem lápide devolveu a revisão 2 de um banco já com lápide. `export_backup` lia configuração, blobs,
histórico e versão em cinco conexões distintas (o manifesto podia divergir do `history.json`).

**Política.** `_read()` abre uma **transação de leitura** (`BEGIN` DEFERRED); em WAL o instantâneo é fixado na
primeira consulta — a própria verificação de lápide/incarnação — e todas as consultas daquela leitura veem o
mesmo estado. Leitura cujo instantâneo é anterior à lápide termina sobre esse **estado anterior válido**;
leitura iniciada depois do COMMIT da lápide é **recusada**. Leituras não bloqueiam gravações nem a exclusão
(WAL). `export_backup` usa um único instantâneo.

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
