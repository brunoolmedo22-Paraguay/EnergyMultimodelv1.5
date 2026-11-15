# Procedimento e alcance da pesquisa

Corte bibliográfico e auditoria: 12/11/2026. Os horários em logs de API são UTC; quando o mecanismo web não fornece horário, registra-se somente a data. A auditoria começou pelo SHA de main e precedeu a prospecção temática em lote.

1. Consulta de main e PRs por GET, árvore recursiva e arquivos fixados no SHA. O espelho temporário foi usado somente para leitura/AST, sem execução do SEEDS2 ou de testes.
2. Busca temática em inglês, busca por títulos e DOI em Crossref, busca temática no DOAJ, busca web em editoras/repositórios e rastreamento de nomes/equações. `buscas.csv` distingue tentativa de consulta bem-sucedida e quantidade retornada de total informado pelo índice.
3. Deduplicação por DOI normalizado, conferência por título e vínculo explícito de famílias preprint/publicação. Os IDs REF são estáveis e não foram renumerados para esconder exclusões. Famílias vinculadas são visíveis na matriz.
4. Triagem focal por título, resumo quando disponível e pertinência ao código/protocolo. Não se afirma que todos os 369 registros de descoberta sejam relevantes, nem que tenham sido lidos integralmente. 165 receberam triagem focal; 121 foram priorizados.
5. Identidade dos 121 itens priorizados conferida por metadados depositados pelo editor em Crossref ou pela fonte primária/institucional indicada. Conferência de identidade é diferente de leitura de conteúdo. F/A/M são independentes de P0–P4. P0 significa fonte usada/alegada no código, não que a equivalência exata esteja demonstrada.
6. Os 111 DOI da biblioteca têm tentativa de resolução registrada. HEAD/HTTP 200 atesta resolução, não acesso ao artigo; 403, 429, 500, redirecionamentos e cookies permanecem no log. Os registros Crossref e a página do CIESC são usados para identidade. Nenhum DOI foi completado por plausibilidade. A fonte OTEKON fica sem DOI, e o manual Horizon não integra os arquivos de referências verificadas.
7. Texto integral/primário acessível: leitura focal dos trechos documentados, não leitura linear exaustiva de cada página. Versões de autor foram vinculadas à publicação editorial sem contar como trabalhos adicionais. PDFs de terceiros não são redistribuídos.
8. Snowballing: consulta de referências nos artigos selecionados e extração do campo `reference/DOI` dos metadados. A rede tem 95 relações internas explícitas e 3744 apontamentos externos para prosseguimento. A busca forward é parcial: inversão das relações observadas e trabalhos que citam plataformas nas fontes lidas. OpenAlex/Semantic Scholar não forneceram grafo global por limitação de taxa. Não se apresentam contagens de citações globais como avaliação de qualidade.

## Bases e barreiras

WoS: 403. Scopus: 403 ou corpo `Site Unavailable`. Scholar: 429/inacessível. Nenhuma consulta nativa TS/TITLE-ABS-KEY nem exportação institucional é declarada como realizada. OpenAlex e Semantic Scholar: 429. Crossref e DOAJ responderam; tentativas Crossref malsucedidas também estão registradas. ResearchGate foi pista de descoberta, nunca fonte canônica. IEEE, Elsevier, Springer, MDPI, JOSS, PLOS, repositórios e documentação oficial foram usados conforme acesso efetivo. Não foi realizada busca nativa em todas as editoras citadas no protocolo.

## Correções, retratações e cobertura

Uma errata associada a De Soto foi identificada (REF0320), mas seu texto não foi obtido. Metadados de atualização/relação foram examinados quando presentes. Ausência de aviso não certifica ausência de retratação. Não houve auditoria completa em bases de retratação, de índices bibliométricos ou de todos os números editoriais.

Não se trata de revisão sistemática PRISMA. Não há contagem retrospectiva fabricada de resultados de WoS/Scopus/Scholar. A meta de 200–300 candidatos de alta pertinência não é comprovada pelos 369 registros brutos: estes contêm falsos positivos documentados. As metas de 100 triagens focais, meta inicial de 80–120 identidades, ampliada para 121 pelo artigo fornecido pelo autor verificadas, mínimo de 50 fontes de alta pertinência (53 P0/P1 priorizadas) e 20–30 fichas com leitura profunda foram atendidas na forma descrita pelas métricas: 165, 120, 53 P0/P1 e 24 fichas com nível F, respectivamente. As outras 6 fichas são críticas de evidência limitada, identificadas como A/M.

## Atualização institucional

As estratégias completas em inglês do protocolo recebido estão preservadas em `15_PROTOCOLO_RECEBIDO`. Executar TS no WoS e TITLE-ABS-KEY no Scopus por acesso institucional legítimo, exportar RIS/CSV com DOI e data, aplicar a mesma deduplicação e manter os IDs existentes. Não contornar autenticação, captcha ou paywall.

A lista exata dos 165 IDs triados está em triagem_focal.csv. A aba Candidatos distingue triagem focal de mera descoberta. Itens sem triagem focal não devem ser interpretados como exclusões após leitura.

## Adendo de procedência e escopo — revisão 01

O autor forneceu o artigo ENCOM REF0369. O DOI resolve, Zenodo/DataCite retornam registros correspondentes, e o MD5 do PDF é idêntico ao depósito. Os nove valores da Tabela II coincidem com os coeficientes-base ao arredondamento publicado. A biblioteca foi ampliada para 121 referências, preservando as 120 chaves anteriores; esse único acréscimo documental explica a extensão além da faixa inicial de 80–120. As trinta fichas passam a 24 F e seis A/M; a ficha limitada de OTEKON foi substituída pela fonte própria. B1 e CT-046 são escopos independentes; a interpretação anterior de discrepância foi retirada. Logs históricos e protocolo recebido foram preservados. O grafo de 95 relações depositadas não foi recalculado a partir das referências do novo PDF.
