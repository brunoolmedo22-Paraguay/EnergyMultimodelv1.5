# SEEDS2 v2.0 — Piso 1: arquitetura da configuração e instalação de uma microrrede

> Escopo: comissionamento, inventário, esquema lógico do balanço energético, demanda, persistência local,
> exportações e integração com o console V1.6. **Não** altera modelos científicos, contrato de troca nem o
> otimizador EMS. Atualizado no **refinamento do Piso 1** (documento v2; ver seção 10).

## 1. Princípio: uma instalação do SEEDS2 administra UMA microrrede

- Não há gestor de projetos, seleção de microrredes, duplicação nem multi-inquilino.
- O banco local aceita uma única linha em `microgrid` (`CHECK (id = 1)`); a identidade
  (`installation.uid`, 32 hex) é criada no comissionamento e **preservada** em todas as edições.
- Trocar de identidade só é possível por restauração de backup de outra instalação, com
  confirmação explícita (o histórico anterior é mantido).

## 2. Camadas

```
app.py ──(energy_source=None)──► seeds2/ui/main.py (shell)
   │                                 ├─ comissionamento   (assistente 5 etapas; exportações na etapa 05)
   │                                 ├─ inicio             (identidade, resumo, áreas, bancadas)
   │                                 ├─ gestao             (inventário, balanço energético, demanda, instalação,
   │                                 │                      relatório/histórico/backups)
   │                                 ├─ simulacao/resultados ─► operations.py ─► orchestrator_app (console V1.6)
   │                                 └─ alcance            (capacidades e limitações)
   └──(energy_source=wind|…)──► bancadas individuais V1.6 (inalteradas)

seeds2/microgrid/  (sem Streamlit)
   references.py  visões somente-leitura dos catálogos (config/*, models/battery_model, h2_pemfc)
   config.py      documento da configuração (v2), especificação de parâmetros, validação, impressão digital
   migrations.py  migração versionada do DOCUMENTO (v1 → v2), sem perda de dados
   derived.py     grandezas nominais verificáveis (STC por arranjo FV; estimativas de bateria por datasheet)
   modellab.py    leitura/validação de pacotes do PEMFC ModelLab (.pmldevice.zip / profile.json)
   store.py       SQLite: revisões, concorrência, blobs, rodadas, backup/restauração, migrações
   adapter.py     inventário → model_spec agregado do orchestrator_runtime (+ carga/clima/condições da rodada)

seeds2/report/pdf.py   relatório técnico PDF (reportlab), gerado localmente da configuração SALVA
seeds2/ui/equipment.py diálogo de equipamento (catálogo → configuração → confirmação) e editores por tecnologia
seeds2/ui/exports.py   ações "EXPORTAR CONFIGURAÇÃO (ZIP)" e "GERAR RELATÓRIO TÉCNICO (PDF)"
```

`seeds2/ui/static/` contém o kit visual (`kit.css`) e componentes `st.components.v2`
(barra superior, stepper, inventário, catálogo de tecnologias `techpicker`, localização automática
`geolocate`, esquema lógico `balance`, áreas), no mesmo padrão do PEMFC ModelLab.
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
para simular. Valores pré-preenchidos são apenas **opções de modelagem** já padronizadas na V1.6
(base de potência PEMFC "entregue", perda genérica eólica desligada, perfil PEMFC equivalente) e duas
hipóteses **sinalizadas** como padrão: sujeira FV 0 % e limites de SOC 20 %/80 % (origem "sugerido").

**Registro de equipamento (diálogo).** "Adicionar equipamento" abre o catálogo visual de 5 tecnologias →
configuração → confirmação; nada é registrado antes de confirmar ("Voltar às tecnologias" descarta o
rascunho). Editar um equipamento existente abre o editor diretamente. Três situações:
falta de dado de *registro* (nome) **bloqueia**; faltam parâmetros de *simulação* → confirmação
"Equipamento com configuração pendente…" (**Salvar como pendente** / **Voltar à configuração**);
valores fisicamente inválidos **bloqueiam** com a explicação.

**Fotovoltaica = usina → arranjos.** Cada arranjo é *módulos identificados* (referência do catálogo,
Ns, Np, sujeira) ou *potência nominal declarada* (kWp + procedência, sem módulo inventado). Para cada
arranjo homogêneo o editor mostra estimativas STC (P = P_mód·Ns·Np, Voc = Voc_mód·Ns, Isc = Isc_mód·Np,
Vmp, Imp) com as hipóteses declaradas; a usina soma **apenas potências** (nunca Voc/Isc entre arranjos).
Potência instalada (Σ arranjos) ≠ potência simulada (Σ arranjos representáveis): ambas são exibidas.

**Bateria = datasheet primeiro.** Fabricante, modelo, química, energia, capacidade, tensão, potência,
correntes e taxas C (todos opcionais). Grandezas faltantes são *estimativas* derivadas e rotuladas
(`derived.battery_derived`, p. ex. Q = E·1000/V; taxa C só com I e Ah); divergências > 5 % geram aviso.
A parametrização do modelo científico (célula de referência, Ns, Np) fica em "Configuração avançada do
modelo científico"; a interface distingue *registrado fisicamente* × *parametrizado para o modelo*.
O **SOC inicial** não é dado do banco: é condição da rodada (`run_conditions.battery_soc0_pct`, editado em
Simulação → "Condições da rodada" e gravado na procedência).

**Eólica.** Curva de potência (Plotly) desenhada a partir dos pontos originais de
`config/wind_turbine_database.py`: pontos tabulados (marcadores) × interpolação linear apenas visual
(tracejado); curva digitalizada de gráfico × tabela do fabricante rotulada; dados da turbina exibidos.

**PEMFC.** Origem "perfil equivalente do catálogo SEEDS2" (padrão) ou "dispositivo importado do PEMFC
ModelLab": pacote `.pmldevice.zip`/`profile.json` validado (`modellab.py`: esquema, hashes canônicos,
limites), resumo com estado e validação de cada calibração; o arquivo original é guardado como blob
(SHA-256) e incluído nos backups. O dispositivo importado fica **pendente de integração científica**:
o adaptador o marca como não representável (o motor atual não consome o perfil V–I calibrado).
"CRIAR DISPOSITIVO NO PEMFC MODELLAB" apenas abre https://pemfc-modelab.streamlit.app/?view=home em nova
aba — não há sincronização entre as aplicações.

**Identificação e localização (etapa 01).** Dois cartões: identificação (nome*, descrição, natureza*,
modo de operação*) e localização (país, região, cidade, endereço, latitude, longitude, fuso — todos
opcionais). "LOCALIZAÇÃO AUTOMÁTICA" faz **uma** leitura `navigator.geolocation.getCurrentPosition`
somente após o clique (sem `watchPosition`), mostra a precisão estimada, oferece o fuso do navegador só
como sugestão e informa negação/indisponibilidade/contexto inseguro; cidade/estado/endereço nunca são
inferidos e não há geocodificação externa. Os valores só são gravados ao confirmar o formulário; a
procedência fica `navegador` (com precisão e instante) se as coordenadas forem aceitas sem alteração,
senão `manual` (`forms.location_source`). Instalações antigas sem natureza/modo recebem um aviso em
Gestão com o botão "Completar identificação".

## 4. Adaptador para o orquestrador V1.6

O runtime aceita **uma configuração agregada por tecnologia**. Regras (`adapter.build_plan`):

| Tecnologia | Agregação exata permitida | Caso não representável |
|---|---|---|
| Solar FV | **por arranjo**: mesma referência, mesmo `n_series`, mesma sujeira → soma `n_parallel` (também entre usinas) | arranjos heterogêneos; arranjo só com kWp declarado |
| Eólica | mesma turbina e mesma opção de perda → soma `turbine_count` | turbinas diferentes |
| Bateria | mesma célula/modelo, Ns, SOC0 (da rodada)/mín/máx e taxas C → soma `Np` | bancos diferentes; SOC0 não definido ou fora dos limites |
| PEMFC importada | — | sempre (pendente de integração científica) |
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

Uma usina FV com parte dos arranjos representável é **parcialmente simulada**: os arranjos fora da rodada
aparecem como exclusões (com o motivo) e a usina é rotulada "Parcialmente representado" no esquema lógico.

Teste de equivalência: um inventário dividido em unidades idênticas que reproduz a configuração
padrão da V1.6 gera **o mesmo `model_spec` e o mesmo despacho** (`tests/test_seeds2_microgrid.py::
RodadaIntegradaTest`); o mesmo vale para o documento v1 real migrado para v2
(`tests/test_seeds2_refinamento.py::MigracaoTest`).

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

## 6. Esquema lógico do balanço energético (substitui a "topologia" do Piso 1 original)

O SEEDS2 integra os modelos num **balanço agregado de potência/energia** (passo de 1 min). A etapa 03 e a
aba "Balanço energético" mostram fontes e armazenamento → balanço agregado → atendimento da demanda,
com o estado de cada equipamento no EMS. **Não** é esquema unifilar: não há barramentos, tensões,
conversores, acoplamentos, proteções ou fluxo de potência. Resta apenas a **declaração de conexão com a
rede** (`energy_balance.grid_connection`); quando declarada, a interface avisa que o EMS não modela
importação/exportação nem tarifas e que um déficit do EMS **não** equivale a compra de energia da rede.
A topologia declarada em documentos v1 é preservada em `legacy.topology_v1` (somente rastreabilidade,
expansor em Gestão) e nunca reinterpretada como conexões verificadas.

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

## 9. Exportações (etapa 05 e Gestão → "Relatório, histórico e backups")

- **EXPORTAR CONFIGURAÇÃO DA MICRORREDE (ZIP):** o mesmo backup verificável (`store.export_backup`,
  formato 2, compatível com a importação de backups do formato 1).
- **GERAR RELATÓRIO TÉCNICO (PDF):** `seeds2/report/pdf.py` (reportlab, local, sem serviços externos)
  a partir da configuração **salva**: resumo executivo, identificação/localização, inventário, FV por
  arranjo, eólica (curva vetorial dos pontos originais), baterias, PEMFC/térmica, esquema lógico,
  compatibilidade com a simulação, demanda/dados, rastreabilidade (revisão, impressão digital, catálogos,
  migrações). Campos ausentes = "Não declarado"; antes da ativação o documento é marcado **PRELIMINAR**;
  declara explicitamente que não é certificação, laudo ou validação experimental.

## 10. Documento v2 e migração

`schema_version = 2`. Migração explícita `migrations.migrate_document` (v1 → v2): localização texto →
`location.address`; FV plana → usina com um arranjo equivalente (id determinístico); bateria → grupo
"modelo" + limites de SOC preservados (origem "migrado") e **SOC inicial → `run_conditions`**; topologia →
`legacy.topology_v1`; `migrations[]` registra de/para, data e notas. Equivalência numérica verificada com o
documento v1 real gerado pelo código do `main` anterior (`tests/fixtures/`). Armazenamento: ver
`ARMAZENAMENTO.md`.

## 11. Preparado para os próximos pisos (não implementado)

- **Centro de Operação:** nova vista no shell (`shell.NAV_ACTIVE`), consumindo `MicrogridStore` e
  `adapter` sem reconstruir a Gestão.
- **Perfis calibrados do PEMFC ModelLab na simulação:** a importação já guarda o pacote validado; falta a
  regra no adaptador/motor, somente quando o motor puder consumir os parâmetros sem inventar dinâmica/BoP
  (decisão científica pendente).
- **Equipamentos heterogêneos no EMS:** exige decisão metodológica (Marília) — não contornado aqui.
