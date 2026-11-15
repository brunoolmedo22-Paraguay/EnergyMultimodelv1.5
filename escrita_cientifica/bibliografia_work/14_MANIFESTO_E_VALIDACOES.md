# Manifesto e validações da entrega

Missão WORK-BIBLIO-SEEDS2-01. Corte e consultas: 12/11/2026 UTC. Repositório: brunoolmedo22-Paraguay/EnergyMultimodelv1.5, main no commit 724d2351ebe4213ed3aa93675c137f7170d260bd. Auditoria exclusivamente por leitura, sem execução do software, alterações remotas, commits, branches ou PRs.

## Conteúdo e rastreabilidade

O pacote inclui os relatórios acadêmicos em português (executivo: 4 páginas; dossiê: 16 páginas) e suas versões Markdown; três planilhas XLSX com tabelas filtráveis e cabeçalho congelado; CSV equivalentes; 121 referências nas exportações BibTeX/RIS; 30 fichas; 53 mapeamentos de modelo; 46 rotas detalhadas de citação em sete seções; comparação de 16 plataformas; 20 registros de achados e esclarecimentos; logs e metadados; grafo GraphML de 95 relações citante–citado observadas; e o protocolo de entrada preservado.

O universo de descoberta tem 369 registros/362 famílias, com 165 triagens focais. A biblioteca final possui 121 famílias distintas e 111 DOI, 34 F, 46 A, 41 M. As 30 fichas são 24 F e seis A/M de acesso limitado. Entre as prioridades há 10 P0 e 43 P1. Identidade bibliográfica, nível de leitura e validade de implementação são dimensões diferentes.

## Verificações realizadas

1. Igualdade de IDs entre matriz normalizada, BibTeX e RIS; 121 entradas, sem DOI ou famílias duplicadas na biblioteca. Chaves BibTeX balanceadas, campos DOI concordantes e datas de acesso nos 121 registros. A validação estrutural não substitui uma importação em cada gerenciador bibliográfico.
2. 111 DOI com tentativa de resolução registrada. Correspondência de título normalizado para os 109 DOI presentes em Crossref. Exceção CIESC/Chen conferida na página primária do editor, com DOI confirmado apesar de falha na consulta Crossref. Respostas HTTP de barreira/erro permanecem visíveis.
3. Caminhos, linhas e SHA dos 53 mapeamentos conferidos com o texto de código consultado. Hashes SHA-256 dos 145 arquivos temporariamente inspecionados disponíveis, sem redistribuir esse espelho.
4. Treze conjuntos de parâmetros R1/C1/R2/C2 comparados à Tabela 3 de Zhang. Dois desvios internos de tau2 acima de 5% registrados. Cálculo independente; nenhuma alteração de parâmetros.
5. 46 claims e sete seções com referências conhecidas, níveis F/A/M, limites e evidência adicional necessária. REF0360 é marcador de manual não obtido e não integra BibTeX/RIS.
6. Planilhas criadas, recalculadas, inspecionadas e renderizadas com Artifact Tool. Totais dinâmicos de 369/121/34/46/41 verificados. Leitura da estrutura OOXML exportada confirmou abas, tabelas e ausência de células de erro. Todas as abas foram revisadas visualmente em intervalos representativos. Não foi feita abertura em Microsoft Excel desktop.
7. Os dois PDFs foram extraídos e todas as páginas renderizadas e inspecionadas, incluindo a revisão 01. Verificados texto, tabelas, paginação e links de referências. Fichas, CSV/JSON e grafo conferidos estruturalmente. O JSON de validação registra cada verificação.

## Critérios atendidos e limitações explícitas

Atendidos: auditoria read-only com SHA e distinção main/draft; inventário por tecnologia; matriz código–literatura; pelo menos 100 triagens; 121 identidades conferidas, incluindo o artigo próprio acrescentado após a entrega inicial; 53 P0/P1 priorizadas; 20–30 fichas F com leitura focal; exportações reutilizáveis; mapa das sete seções; logs e organização em ZIP.

Parciais/pendentes: meta aspiracional de 200–300 candidatos pertinentes não demonstrada pelos registros brutos; nenhuma busca nativa ou exportação WoS/Scopus/Scholar por barreiras; busca forward global incompleta; artigo próprio PEMFC REF0369 consultado; original OTEKON e manual Horizon ainda não obtidos diretamente; tabelas Chen e errata De Soto pendentes; revisão específica de Buck pendente; CT-046 é cenário futuro independente, sem inconsistência com B1. Os 41 itens M e os 46 A não foram promovidos a leitura integral. Não houve auditoria global de retratações.

Nenhum artigo foi redigido. Resultados próprios, banco pessoal de cenários, reexecução de testes e validação empírica ficam fora desta missão. O pacote não contém PDFs de terceiros nem cópia do repositório. Os scripts próprios de conferência e seus dados derivados não alteram o software.

## Integridade

`SHA256SUMS.txt` lista o SHA-256 de todos os arquivos da entrega, inclusive este manifesto, excluindo somente a própria lista de hashes. O arquivo ZIP é verificado por CRC após a criação. Os nomes internos usam numeração que acompanha o protocolo. A ordem de leitura sugerida está no arquivo 00.

## Revisão 01

A nota 16 registra as correções de procedência PEMFC e escopo COPEL. Os nove coeficientes identificados do artigo ENCOM foram conferidos com a base do código. B1 e CT-046 são usos independentes; os registros LAC0001/LAC0003 foram reclassificados como esclarecimentos. O DOI específico do artigo próprio foi verificado em Zenodo e DataCite.

A revisão 01 passou por 50 verificações estruturais e de procedência, sem falhas registradas.
