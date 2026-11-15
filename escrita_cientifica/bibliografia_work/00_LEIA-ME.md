# SEEDS2 — Auditoria e biblioteca bibliográfica

Missão WORK-BIBLIO-SEEDS2-01. Corte: 12/11/2026. Informes e interpretações em português do Brasil. Repositório mantido em somente leitura.

## Começar pelos arquivos

1. `01_RELATORIO_EXECUTIVO_PT.pdf`: conclusões, prioridades e metas reais.
2. `02_MAPA_DE_ESTADO_DA_ARTE_PT.pdf`: plataformas, EMS, valor futuro, tecnologias e avaliação.
3. `03_INVENTARIO_CODIGO_E_MODELOS.md`: auditoria fixada em `724d2351ebe4213ed3aa93675c137f7170d260bd`.
4. `04_MATRIZ_REFERENCIAS.xlsx`: 121 itens priorizados e universo de descoberta com decisões.
5. `05_CODIGO_VS_LITERATURA.xlsx`: 53 relações, linhas/SHA, lacunas e conferência numérica da Tabela 3 de Zhang.
6. `06_CLAIMS_PARA_O_ARTIGO.xlsx`: 46 afirmações planejadas, sete seções e fontes/limites.
7. `07_REFERENCIAS_VERIFICADAS.bib` e `08_REFERENCIAS_VERIFICADAS.ris`: os mesmos 121 IDs para importação. UTF-8, sem DOI inventado e sem manual Horizon não consultado.
8. `09_FICHAS_NUCLEARES_PT`: 30 fichas; 24 com leitura focal de texto e 6 de evidência limitada A/M.
9. `10_BUSCAS_E_PROVENIENCIA`: consultas, barreiras, DOI, metadados, decisões, inventário e grafo de citações observadas.
10. `11_LACUNAS_E_DISCREPANCIAS.md`, `12_ROTEIRO_CITACOES_ARTIGO_PT.md`, `13_LISTA_PRIORITARIA_DE_LEITURA.md` e `14_MANIFESTO_E_VALIDACOES.md`.

CSV equivalentes permitem uso fora do Excel. GraphML e as relações DOI citante→citado representam somente citações observadas, sem inferir relações por semelhança temática. Fichas, códigos e claims usam IDs estáveis REF/MOD/CLM/BUS.

## Como interpretar evidência

P0: fonte de origem usada/alegada pela implementação. P1: proximidade com a contribuição. P2: fundamento técnico. P3: ferramentas, verificação/reprodução. P4: contexto/revisão. F: texto/primário consultado e trecho relevante conferido. A: resumo consultado. M: identidade bibliográfica, sem conferência integral. Prioridade alta não significa leitura profunda ou validação do código.

## Pendências materiais

O artigo próprio PEMFC foi incorporado como REF0369, fonte P0/F da implementação e identificação paramétrica baseada em Altıntaş–Ertan. O original OTEKON permanece complementar para cotejo literal; as pendências específicas do equivalente Horizon/Chen e da errata De Soto permanecem separadas. B1 é um perfil COPEL já implementado; CT-046 é destinado a uma futura microrrede independente. Não há inconsistência identificada entre ambos. As barreiras de WoS/Scopus/Scholar permanecem documentadas.

Nenhum artigo, resultado SEEDS2, commit ou PR foi redigido/criado/modificado. Não foram incluídos PDFs de terceiros nem espelho do repositório. Os arquivos entregues são a base de evidência para uma redação posterior.

## Dados para reutilização

`04_REFERENCIAS_PRIORIZADAS.csv` replica as 121 entradas da aba Referencias. O CSV 12 e a aba Mapa_citacoes contêm 46 rotas detalhadas de citação; o resumo de sete seções está na aba Mapa_secoes. `conferencia_identidades.csv` discrimina 109 conferências Crossref, uma pelo editor CIESC, uma em Zenodo/DataCite e dez fontes sem DOI. `triagem_focal.csv` lista exatamente os 165 registros examinados. `SHA256SUMS.txt` permite conferir a integridade dos arquivos.
