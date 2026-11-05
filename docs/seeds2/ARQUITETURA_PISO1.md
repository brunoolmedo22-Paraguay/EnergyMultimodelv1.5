# SEEDS2 v2.0 — Piso 1: arquitetura da configuração e instalação de uma microrrede

> Escopo: comissionamento, inventário, topologia, demanda, persistência local e integração com o
> console V1.6. **Não** altera modelos científicos, contrato de troca nem o otimizador EMS.

## 1. Princípio: uma instalação do SEEDS2 administra UMA microrrede

- Não há gestor de projetos, seleção de microrredes, duplicação nem multi-inquilino.
- O banco local aceita uma única linha em `microgrid` (`CHECK (id = 1)`); a identidade
  (`installation.uid`, 32 hex) é criada no comissionamento e **preservada** em todas as edições.
- Trocar de identidade só é possível por restauração de backup de outra instalação, com
  confirmação explícita (o histórico anterior é mantido).

## 2. Camadas

```
app.py ──(energy_source=None)──► seeds2/ui/main.py (shell)
   │                                 ├─ comissionamento   (assistente 5 etapas)
   │                                 ├─ inicio             (identidade, resumo, áreas, bancadas)
   │                                 ├─ gestao             (inventário, topologia, demanda, instalação, histórico/backups)
   │                                 ├─ simulacao/resultados ─► operations.py ─► orchestrator_app (console V1.6)
   │                                 └─ alcance            (capacidades e limitações)
   └──(energy_source=wind|…)──► bancadas individuais V1.6 (inalteradas)

seeds2/microgrid/  (sem Streamlit)
   references.py  visões somente-leitura dos catálogos (config/*, models/battery_model, h2_pemfc)
   config.py      documento da configuração, especificação de parâmetros, validação, impressão digital
   store.py       SQLite: revisões, concorrência, blobs, rodadas, backup/restauração, migrações
   adapter.py     inventário → model_spec agregado do orchestrator_runtime (+ carga/clima)
```

`seeds2/ui/static/` contém o kit visual (`kit.css`) e componentes `st.components.v2`
(barra superior, stepper, inventário, topologia, áreas), no mesmo padrão do PEMFC ModelLab.
Ações que alteram dados usam widgets nativos (formulários, `st.dialog`) para serem testáveis.

## 3. Modelo científico × referência técnica × equipamento instalado

| Conceito | Onde | Pode mudar no Piso 1? |
|---|---|---|
| Modelo científico (equações) | `models/`, `h2_pemfc/`, `simulation/`, `ems_integration/` | **Não** |
| Referência técnica (catálogo + procedência) | `config/*_database.py`, `TREMBLAY_BATTERIES`, perfil PEMFC | Somente leitura |
| Equipamento instalado (unidade/agrupamento) | documento da microrrede (`equipment[]`) | Sim (Gestão) |

Cada equipamento tem `id` estável (`eq-` + 12 hex), tecnologia imutável, nome, TAG, nº de série,
estado habilitado/desabilitado, parâmetros e observações. Retirar move o registro para
`retired[]` (auditoria), sem apagar as revisões anteriores.

**Três níveis de estado** exibidos na interface:
1. *Registrado* — nome + tecnologia (parâmetros podem estar vazios: nada é presumido);
2. *Tecnicamente configurado* — todos os parâmetros obrigatórios para simular declarados e válidos;
3. *Compatível com a simulação* — representável no contrato atual do EMS (decisão do adaptador).

Parâmetros por tecnologia (`config.PARAM_SPECS`) trazem unidade, faixa física e se são obrigatórios
para simular. Únicos valores pré-preenchidos são **opções de modelagem** já padronizadas na V1.6
(base de potência PEMFC "entregue", perda genérica eólica desligada, perfil PEMFC único).

## 4. Adaptador para o orquestrador V1.6

O runtime aceita **uma configuração agregada por tecnologia**. Regras (`adapter.build_plan`):

| Tecnologia | Agregação exata permitida | Caso não representável |
|---|---|---|
| Solar FV | mesma referência, mesmo `n_series`, mesma sujeira → soma `n_parallel` | arranjos heterogêneos |
| Eólica | mesma turbina e mesma opção de perda → soma `turbine_count` | turbinas diferentes |
| Bateria | mesma célula/modelo, Ns, SOC0/mín/máx e taxas C → soma `Np` | bancos diferentes |
| PEMFC | mesmo perfil e mesma base → soma `N_fc` | — |
| Térmica | **uma** pequena unidade geradora | >1 unidade; usina de grande porte |

A agregação é exata porque os modelos existentes escalam linearmente com essas quantidades
(`P_array = p_module·n_modules`, `p_gross = p_unit·turbine_count`, bateria/PEMFC caracterizadas por
unidade e escaladas por Np/N_fc). Nunca se escolhe um equipamento "principal": em grupos
heterogêneos **todos** ficam *não representáveis* com o motivo.

Nada é omitido silenciosamente: cada equipamento recebe um estado (`representado`, `desabilitado`,
`incompleto`, `incompativel`). Se algum habilitado ficar fora, a rodada exige confirmação explícita
e a lista de exclusões é gravada na rodada. Bloqueios (sem despachável, demanda indefinida)
impedem a execução.

Teste de equivalência: um inventário dividido em unidades idênticas que reproduz a configuração
padrão da V1.6 gera **o mesmo `model_spec` e o mesmo despacho** (`tests/test_seeds2_microgrid.py::
RodadaIntegradaTest`).

## 5. Configuração salva × edição pendente × configuração aplicada

- **Salva:** última revisão no SQLite (lida a cada execução; visível a todas as sessões).
- **Edição pendente:** cópia de trabalho da sessão em Gestão; indicador "Alterações pendentes (n)"
  com lista das mudanças; "Salvar alterações" grava nova revisão, "Descartar" volta à salva.
  No comissionamento cada etapa é salva imediatamente.
- **Aplicada a uma simulação:** `operations.prepare` transfere ao console V1.6 apenas a configuração
  **salva** e registra a procedência (`revisão`, impressão digital da configuração e da
  especificação). Alterações manuais nas páginas V1.6 (Modelos/Carga) são detectadas por hash de
  estado: a origem passa a "manual" e o resultado não é atribuído à microrrede.
- Cada rodada grava `simulation_runs` (revisão, impressões digitais, origem, exclusões, resumo).
  Se a configuração salva mudar, os resultados antigos são marcados como **"Resultado de
  configuração anterior"** (mantidos só para consulta). O ZIP de exportação inclui
  `origem_configuracao` no resumo.

## 6. Topologia

Barramento comum único (CA, CC ou não declarado), tensão nominal declarada (informativa),
estado de conexão com a rede e tipo de acoplamento de cada equipamento e da demanda. O esquema
SVG é gerado a partir desses dados. **Não** há fluxo de potência, tensões, proteções ou
transitórios. Declarar conexão à rede **não** habilita importação/exportação no EMS (identificado
na interface como não implementado).

## 7. Demanda e dados

Fontes: walk-forward (referência, embarcação 2 h), COPEL B1 (curva típica de referência) e CSV da
instalação. O CSV original é armazenado como blob (SHA-256) e a janela (início/duração) é
guardada; a carga é reconstruída pelas **mesmas funções da V1.6** (`ponte.carga_de_dataframe`,
`ponte.recortar`). Procedência declarada (`medido`, `sintético`, `referência`, `não declarado`);
perfis de referência e clima sintético **não podem** ser declarados como medidos. Convenções:
potência consumida positiva em kW, grade de 1 min do EMS, fuso horário declarado (opcional).

## 8. Alterações em arquivos existentes (mínimas)

- `app.py`: `APP_CSS` passou a ser injetado só nas telas V1.6 (`legacy_css`); sem bancada aberta,
  entra no shell SEEDS2; título da página.
- `orchestrator_app.py`: respeita `orq_run_gate`, grava `origem` na rodada e chama `orq_after_run`.
- `orchestrator_runtime.py`: `origem_configuracao` no resumo do ZIP exportado.
- `requirements.txt`: `streamlit==1.66.1` (mesma versão do ModelLab; necessário para
  `st.components.v2`). `numpy`, `scipy`, `pandas` e `plotly` inalterados.

## 9. Preparado para os próximos pisos (não implementado)

- **Centro de Operação:** nova vista no shell (`shell.NAV_ACTIVE`), consumindo `MicrogridStore` e
  `adapter` sem reconstruir a Gestão.
- **Perfis calibrados do PEMFC ModelLab:** novas referências em `references.py` + regra no adaptador,
  somente quando o motor puder consumir os parâmetros sem inventar dinâmica/BoP.
- **Equipamentos heterogêneos no EMS:** exige decisão metodológica (Marília) — não contornado aqui.
