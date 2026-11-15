# Fundamentação científica do SEEDS2
## Relatório executivo da missão WORK-BIBLIO-SEEDS2-01

**Corte: 12 de novembro de 2026.** Auditoria estática em somente leitura e investigação bibliográfica. Este documento avalia as bases disponíveis para a futura redação. Não contém o artigo, resultados inéditos de simulação ou uma certificação de validação experimental.

## Parecer principal

A literatura permite fundamentar duas contribuições com peso equivalente: a plataforma modular de experimentação energética e seu EMS hierárquico. O argumento científico deve explicitar quais modelos são usados em cada camada, como a informação passa entre horizontes e como a execução é auditada. Há precedentes próximos de plataformas abertas, MPC de microrredes e controle naval FC–bateria. Assim, a novidade não pode ser apresentada como ausência de soluções semelhantes. Deve resultar de uma comparação funcional documentada e de ensaios próprios controlados.

A implementação principal foi fixada no commit **724d2351ebe4213ed3aa93675c137f7170d260bd**, de 11/11/2026, 16:27:39 UTC. O PR #24 foi tratado separadamente como draft, no HEAD **15c0b1cde526e653abf31b2dbf0721e96610c950**. Não houve alteração do repositório nem execução de sua suíte ou de seus casos. A investigação identificou 53 relações código–modelo–fonte e indexou símbolos de 112 arquivos Python.

## Cobertura obtida e alcance de leitura

[COVERAGE]

| Etapa | Resultado e interpretação |
| --- | --- |
| Descoberta | 369 registros distintos por DOI/título, organizados em 362 famílias após vincular versões. Incluem falsos positivos, reservas e exclusões. Não equivalem a 369 referências relevantes. |
| Triagem focal | 165 registros examinados por título, resumo quando disponível e aderência ao código/protocolo. |
| Biblioteca final | 121 identidades bibliográficas conferidas, com 111 DOI e fontes primárias/institucionais para os itens sem DOI. |
| Alta prioridade | 10 itens P0, de origem documental/matemática, e 43 P1, próximos da contribuição. Prioridade não indica nível de leitura. |
| Leitura | 34 itens F, 46 A e 41 M. F inclui documentação técnica e dados primários, além de artigos; significa texto acessível e leitura focal dos trechos registrados. |
| Fichas | 30 fichas críticas: 24 com leitura focal F e 6 explicitamente limitadas a A/M. |
| Rastreabilidade | 53 mapeamentos, 46 afirmações candidatas em sete seções, 142 registros de consultas/tentativas e 95 relações internas de citação depositadas em metadados. |

A biblioteca alcança 121 identidades verificadas após a inclusão do artigo próprio fornecido pelo autor, uma referência além da faixa inicialmente prevista de 80–120. As metas de pelo menos 100 triagens e 20–30 fichas de leitura focal foram atendidas nas condições acima. A prospecção aspiracional de 200–300 candidatos pertinentes não foi demonstrada pelos 369 registros de descoberta. A cobertura nativa de WoS/Scopus/Scholar permanece pendente por barreiras de acesso.

## O que o código efetivamente implementa

| Camada | Evidência e implicação para a redação |
| --- | --- |
| Bancadas tecnológicas | Modelos FV proporcional/NOCT/diodo único, eólica por curvas/densidade, bateria elétrica Tremblay/2RC, PEMFC eletroquímica equivalente e térmica com custo variável/eventos. Não são todos utilizados pelo despacho V2. |
| Integração V2 | FV por NOCT/eficiência; eólica por curva; BESS por recorrência energética; PEMFC por curva de consumo PWL e estados/eventos; PCC agregado. Geração térmica não está representada economicamente no V2 examinado. |
| Otimização | Pyomo/HiGHS, LP/MILP, exclusividade de fluxos, restrições de energia, commitment e rampas. GA/GWO/NGO + SQP pertencem ao legado V1.6. |
| MPC | Previsões seladas pelo instante informacional, resolução por janela, aplicação de bloco de decisões e reconciliação com o estado executado. O estado deve ser causal, não apenas o estado planejado da janela anterior. |
| Hierarquia | Caudas reotimizadas estimam custo de continuação além da fronteira curta. Há representação por modos e PWL. O sinal marginal local é obtido por diferenças de valores, não diretamente como preço dual. |
| Proveniência | Registry, SQLite, versões append-only, manifestos e hashes. São mecanismos de reprodução; a auditoria não reexecutou resultados nem demonstrou suporte irrestrito a qualquer componente novo. |

## Seis achados que condicionam as afirmações

**1. A procedência PEMFC inclui o artigo próprio.** Chavez et al. (REF0369, ENCOM 2026, DOI 10.5281/zenodo.22978126) documentam a implementação baseada em Altıntaş–Ertan e a identificação por mínimos quadrados com 16 inicializações. Os nove coeficientes da Tabela II coincidem ao arredondamento publicado com a base do código; N=41 e Uf aproximadamente 0,6962 também estão documentados. A fonte imediata da adaptação é o artigo próprio; OTEKON é a formulação-base. O equivalente Horizon constitui uma adaptação posterior, com pendências documentais específicas de Chen/manual.

**2. A tabela de origem da bateria 2RC contém inconsistência interna.** Os 13 conjuntos R1/C1/R2/C2 da Tabela 3 de Zhang et al. (REF0147, p. 8) coincidem com os arrays do código. Para SOC 0,9, porém, o produto publicado R2×C2 resulta em 354,8868 s, enquanto tau2 está impresso como 89,7116 s. Para SOC 0,3, o desvio também supera 5%. A discrepância foi conferida por cálculo independente e inspeção da página. A missão não corrigiu fonte nem implementação. É necessário registrar o critério de uso e estudar sensibilidade antes de afirmar fidelidade experimental.

**3. B1 e CT-046 são usos distintos.** O perfil B1 residencial já está implementado no SEEDS2 para sua finalidade. CT-046 pertence ao planejamento de outra microrrede, de caráter industrial. A auditoria anterior associou indevidamente esses contextos; não foi identificada inconsistência no código nem necessidade de substituir B1. A fonte e a tarifa CT-046 serão documentadas no cenário próprio quando ele for implementado.

**4. A disponibilidade do SDM não significa que o EMS o executa.** A ponte V2 consultada usa NOCT/eficiência e trata GHI como irradiância no plano do módulo. Não foi encontrada transposição solar ou inversor/MPPT detalhado nessa ponte. A publicação de De Soto (REF0319) possui errata identificada (REF0320), ainda não lida. A descrição do artigo deve separar a biblioteca de modelos da cadeia executada no caso.

**5. O custo futuro é uma aproximação condicionada.** A formulação 1D permite segmentos não convexos; a construção 2D usa envoltória inferior após verificações amostrais. Isso não prova convexidade global ou exatidão da função de valor. O método não pode ser denominado SDDP, ADP aprendido ou preço dual sem formulação adicional. Custo planejado, realizado e estimado após o horizonte precisam permanecer separados.

**6. O caso naval exige um orçamento externo de H2.** O núcleo auditado contabiliza consumo e dinâmica/eventos, mas declara estoque/tanque M18 não suportado. O estado inicial ON e 30 kW foi identificado como decisão de projeto, sem confirmação no banco pessoal do cenário. Rampas registradas são 2 kW/s na subida e 3,5 kW/s na descida, com conferência externa do manual pendente. Consumo calculado não comprova autonomia física ou estabilidade elétrica da embarcação.

## Posicionamento científico recomendado

**Plataforma.** PyPSA (REF0104), oemof (REF0355), Calliope (REF0353), ETHOS.FINE (REF0343) e pymgrid (REF0357, preprint) são comparadores importantes. O contraste deve usar critérios observáveis: contrato dos componentes, separação dados–modelo, reconfiguração de cenários, persistência das entradas, baselines, execução recedente e auditoria. Interface visual é parte da ferramenta; sozinha não prova contribuição metodológica.

**EMS.** Parisio (REF0349), Fan (REF0156), Vivas (REF0216), Aaslid (REF0338) e os demais estudos hierárquicos delimitam precedentes. Kopka, Coraddu e Polinder (REF0094, 2026) é especialmente próximo da combinação modularidade–MPC–FC/bateria naval. O resumo institucional descreve controle distribuído por decomposição dual e execução em hardware de controle. O V2 examinado é centralizado MILP/PWL; a comparação detalhada das equações ainda requer o texto completo do precedente.

Nenhuma diferença arquitetural deve ser convertida automaticamente em superioridade. A contribuição poderá ser sustentada pela integração explicitamente documentada e pelo ganho demonstrado em condições iguais, com limites de generalização.

## Estudos de caso e avaliações indispensáveis

O **Estudo I** é uma microrrede industrial hipotética atendida pela COPEL: C1 rede; C2 rede + FV; C3 rede + bateria; C4 rede + FV + bateria. A alteração de equipamentos avalia composição tecnológica. Para isolar o EMS, comparar **a mesma C4** com e sem informação de continuação, preservando física, previsões, estados, restrições e solver. O **Estudo II** é a embarcação isolada. Não há quatro estudos industriais independentes.

Registrar custo realizado e suas parcelas, energia importada/exportada, curtailment, atendimento da carga, energia/SOC final, H2 total, partidas, rampas, violações e tempo de solução/terminação/gaps. Uma trajetória com informação futura perfeita deve ser chamada de referência informacional privilegiada, sem competir diretamente com um controlador causal como se tivessem a mesma informação. Resultados devem incluir política terminal e massa de combustível disponível quando se discutir autonomia.

## Acessos não concluídos e como o pacote os documenta

WoS retornou 403; Scopus retornou 403 ou “Site Unavailable”; Scholar ficou inacessível/429. Não foram declaradas consultas TS/TITLE-ABS-KEY ou exportações nativas dessas bases. OpenAlex e Semantic Scholar também apresentaram limitação de taxa. Crossref, DOAJ, editoras, repositórios e documentação oficial sustentam o corpus obtido. DOI resolvido não significa artigo lido; os códigos de resposta estão registrados.

O ZIP contém os dois relatórios, o inventário, três planilhas, versões CSV, BibTeX/RIS equivalentes, 30 fichas, o mapa de sete seções, o grafo observado, logs e o protocolo recebido. O arquivo de lacunas traz 20 registros de achados e esclarecimentos; a identificação própria PEMFC agora está documentada; manual Horizon, errata De Soto e futura documentação do cenário CT-046 têm escopos separados. A etapa de redação deve usar as permissões e limites de cada claim da matriz, preservando o mesmo SHA ou repetindo a auditoria se o código mudar.
