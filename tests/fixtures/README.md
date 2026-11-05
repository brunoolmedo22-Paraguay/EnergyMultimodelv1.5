# Fixtures de teste do SEEDS2

| Arquivo | Origem | Uso |
|---|---|---|
| `seeds2_config_v1.json` | Documento **v1 real**, gerado com o código do `main` em `67a7a6f` (Piso 1 original, antes do refinamento). | Migração do documento v1 → v2 e equivalência numérica da rodada EMS. |
| `seeds2_backup_v1_piso1.zip` | Backup **v1 real** (formato 1) exportado pelo mesmo código, com CSV de demanda armazenado. | Restauração de backups do formato anterior. |
| `modellab_profile_v020.json` | Cópia literal de `tests/fixtures/compat/profile_v020.json` do repositório PEMFC-MODELAB (`ab5fb03`, v0.5.0). | Importação de `profile.json` e montagem de pacotes `.pmldevice.zip` no formato de `workspace/project_io.py`. |

Nenhum destes arquivos contém dados de uma instalação real.

**Exceção à regra 8 do `CLAUDE.md` (fixtures sintéticas auditadas).** `seeds2_backup_v1_piso1.zip` é um backup
fictício mantido apenas para testes de regressão do formato v1. Conteúdo auditado (revisão do PR #4):
`manifest.json`, `configuration.json` (instalação "Laboratório de Microrredes — Bloco C (v1)", descrição
"Fixture de teste automatizado", coordenadas genéricas de cidade, equipamentos de teste), `history.json`
(2 revisões de teste) e um CSV de carga sintético (`blobs/<sha256>`). Não substituir por backups reais nem
regenerar com o código atual (deixaria de representar o formato v1).
