# Roteiro de citações para as sete seções

Documento de planejamento bibliográfico; não é redação do artigo. O texto principal futuro deve ser autônomo, com hipóteses e equações essenciais, sem delegá-las ao suplemento.

## 1. Introdução

| claim_id | afirmacao_que_pode_ser_escrita | referencias_adequadas | status |
| --- | --- | --- | --- |
| CLM0001 | Microrredes exigem coordenação de recursos heterogêneos e restrições temporais. | REF0121;REF0157;REF0213 | Fundamentável |
| CLM0002 | Há plataformas abertas consolidadas de simulação e otimização energética. | REF0104;REF0355;REF0353;REF0343 | Fundamentável |
| CLM0003 | Reprodução de estudos requer código, dados, configurações e versões. | REF0354;REF0142;REF0143 | Fundamentável |
| CLM0004 | A integração FC–bateria é estudada para aplicações navais. | REF0324;REF0094;REF0278 | Fundamentável |

**Fontes ligadas:** [REF0094](https://doi.org/10.1109/ojies.2026.3710800); [REF0104](https://doi.org/10.5334/jors.188); [REF0121](https://doi.org/10.3390/app9183854); [REF0142](https://doi.org/10.1371/journal.pcbi.1003285); [REF0143](https://doi.org/10.1038/sdata.2016.18); [REF0157](https://doi.org/10.3390/en16083362); [REF0213](https://doi.org/10.3390/en16165935); [REF0278](https://doi.org/10.3390/en19112636); [REF0324](https://doi.org/10.1016/j.jpowsour.2016.07.007); [REF0343](https://doi.org/10.21105/joss.06274); [REF0353](https://doi.org/10.21105/joss.00825); [REF0354](https://doi.org/10.1371/journal.pbio.1001745); [REF0355](https://doi.org/10.1016/j.esr.2018.07.001).

## 2. Fundamentação teórica e trabalhos relacionados

| claim_id | afirmacao_que_pode_ser_escrita | referencias_adequadas | status |
| --- | --- | --- | --- |
| CLM0005 | A comparação de frameworks deve incluir formulação matemática e arquitetura. | REF0312;REF0355;REF0343 | Fundamentável |
| CLM0006 | MPC e hierarquia temporal são precedentes estabelecidos em microrredes. | REF0349;REF0156;REF0216;REF0350 | Fundamentável |
| CLM0007 | Controle primário/secundário/terciário difere de coordenação longo/curto prazo. | REF0119;REF0229;REF0213 | Fundamentável |
| CLM0008 | Valor futuro e custo terminal representam consequências além do horizonte curto. | REF0365;REF0338 | Parcial: detalhes de Aaslid no texto integral pendentes |
| CLM0009 | A hierarquia pode apresentar custos computacionais e dependência de previsões/pesos. | REF0216;REF0221;REF0158 | Fundamentável com ressalvas de leitura |

**Fontes ligadas:** [REF0119](https://doi.org/10.1109/iecon.2009.5414926); [REF0156](https://doi.org/10.3390/en11051111); [REF0158](https://doi.org/10.1016/s0005-1098(99)00214-9); [REF0213](https://doi.org/10.3390/en16165935); [REF0216](https://doi.org/10.1016/j.ecmx.2025.101027); [REF0221](https://doi.org/10.1016/j.ijepes.2025.111516); [REF0229](https://doi.org/10.3390/en13102454); [REF0312](https://doi.org/10.1016/j.adapen.2024.100190); [REF0338](https://doi.org/10.1109/tste.2022.3156069); [REF0343](https://doi.org/10.21105/joss.06274); [REF0349](https://doi.org/10.1109/tcst.2013.2295737); [REF0350](https://doi.org/10.1016/j.apenergy.2020.116420); [REF0355](https://doi.org/10.1016/j.esr.2018.07.001); [REF0365](https://sites.engineering.ucsb.edu/~jbraw/mpc/MPC-book-2nd-edition-5th-printing.pdf).

## 3. Arquitetura e desenvolvimento da plataforma SEEDS2

| claim_id | afirmacao_que_pode_ser_escrita | referencias_adequadas | status |
| --- | --- | --- | --- |
| CLM0010 | A plataforma usa separação entre cadastro, modelos, integração, solver e interface. | REF0355;REF0343;REF0354 | Sustentada por inspeção de main |
| CLM0011 | A reconfiguração observada cobre os tipos de equipamento e adaptadores suportados. | REF0353;REF0355;REF0104 | Sustentada com escopo limitado |
| CLM0012 | Cenários e rodadas têm identidade e histórico persistente. | REF0141;REF0142;REF0143 | Inspeção estática; ensaio de reabertura não reexecutado |
| CLM0013 | Streamlit fornece a camada de interface científica. | REF0362 | Detalhes de execução da documentação pendentes |
| CLM0014 | Pyomo e HiGHS são ferramentas identificadas na formulação/solução V2. | REF0111;REF0356 | Sustentada por código e requirements |
| CLM0015 | Trama, Caderno e Folha pertencem ao draft #24 no corte auditado. | REF0142 | Sustentada por arquivos do PR, não por sua descrição desatualizada |

**Fontes ligadas:** [REF0104](https://doi.org/10.5334/jors.188); [REF0111](https://doi.org/10.1007/s12532-011-0026-8); [REF0141](https://doi.org/10.1371/journal.pcbi.1005510); [REF0142](https://doi.org/10.1371/journal.pcbi.1003285); [REF0143](https://doi.org/10.1038/sdata.2016.18); [REF0343](https://doi.org/10.21105/joss.06274); [REF0353](https://doi.org/10.21105/joss.00825); [REF0354](https://doi.org/10.1371/journal.pbio.1001745); [REF0355](https://doi.org/10.1016/j.esr.2018.07.001); [REF0356](https://doi.org/10.1007/s12532-017-0130-5); [REF0362](https://docs.streamlit.io/develop/concepts/architecture).

## 4. Modelagem matemática e sistema de gerenciamento energético hierárquico

| claim_id | afirmacao_que_pode_ser_escrita | referencias_adequadas | status |
| --- | --- | --- | --- |
| CLM0016 | A bancada FV possui três modelos de complexidade distinta. | REF0319;REF0113;REF0123 | Sustentada pelo código |
| CLM0017 | O V2 deriva potencial FV por NOCT e correção linear de eficiência. | REF0113;REF0125;REF0368 | Sustentada com hipótese explícita |
| CLM0018 | A translação SDM é atribuída a De Soto; a extração numérica é adaptada. | REF0319;REF0320;REF0368;REF0138 | Parcial: fonte original completa pendente |
| CLM0019 | A função térmica Sandia implementa relação exponencial com vento. | REF0123 | Correspondência direta |
| CLM0020 | O modelo eólico usa curvas documentadas e correção de densidade. | REF0328;REF0366;REF0367 | Parcial por equipamento |
| CLM0021 | A simulação de múltiplas turbinas não calcula estelas. | REF0328 | Sustentada por inspeção do modelo |
| CLM0022 | A bancada 2RC porta parâmetros de Zhang com interpolação e Euler explícito. | REF0147 | Correspondência de tabela conferida; discrepância tau2 aberta |
| CLM0023 | Tremblay–Dessaint fundamenta a bancada genérica de carga/descarga. | REF0352;REF0126 | Correspondência estrutural |
| CLM0024 | O BESS do EMS é um modelo energético e não um circuito 2RC. | REF0156;REF0349 | Sustentada por código |
| CLM0025 | O modelo PEMFC incorpora a implementação e identificação paramétrica próprias de Chavez et al., baseadas em Altıntaş–Ertan. | REF0369;REF0358;REF0341;REF0151 | Fonte própria consultada e parâmetros-base conferidos. |
| CLM0026 | O stack equivalente combina prior, dados de outro stack e limites de fabricante. | REF0369;REF0358;REF0359;REF0360 | Parcial: tabelas Chen/manual pendentes |
| CLM0027 | O suprimento de H2 é calculado pela lei de Faraday e fator de utilização. | REF0151;REF0152 | Sustentada estruturalmente |
| CLM0028 | A rampa nominal de subida registrada é 2 kW/s, equivalente a 120 kW/min. | REF0360 | Fonte externa pendente |
| CLM0029 | A curva H2 usada pelo MILP é uma aproximação PWL da potência líquida do modelo. | REF0083 | Sustentada pelo código |
| CLM0030 | Commitment inclui transições, rampas e permanências com memória. | REF0117;REF0349 | Correspondência estrutural |
| CLM0031 | O PCC é agregado e a função econômica usa tarifas por energia importada/exportada. | REF0363;REF0364;REF0136 | Sustentada com limites |
| CLM0032 | O valor local de energia é obtido por diferenças de custos de caudas reotimizadas. | REF0365;REF0338 | Sustentada por código; apoio conceitual |
| CLM0033 | A representação 2D usa uma envoltória inferior e verificação convexa amostral. | REF0083 | Sustentada com limitação matemática |

**Fontes ligadas:** [REF0083](https://doi.org/10.1287/opre.1090.0721); [REF0113](https://doi.org/10.21105/joss.00884); [REF0117](https://doi.org/10.1109/tpwrs.2006.876672); [REF0123](https://doi.org/10.2172/919131); [REF0125](https://doi.org/10.1002/pip.813); [REF0126](https://doi.org/10.1109/vppc.2007.4544139); [REF0136](https://doi.org/10.1115/es2014-6570); [REF0138](https://doi.org/10.1038/s41592-019-0686-2); [REF0147](https://doi.org/10.3390/app7101002); [REF0151](https://doi.org/10.1016/s0378-7753(99)00484-x); [REF0152](https://doi.org/10.3390/en7020670); [REF0156](https://doi.org/10.3390/en11051111); [REF0319](https://doi.org/10.1016/j.solener.2005.06.010); [REF0320](https://doi.org/10.1016/j.solener.2006.05.001); [REF0328](https://doi.org/10.1016/j.rser.2013.10.030); [REF0338](https://doi.org/10.1109/tste.2022.3156069); [REF0341](https://doi.org/10.1149/1.2043866); [REF0349](https://doi.org/10.1109/tcst.2013.2295737); [REF0352](https://doi.org/10.3390/wevj3020289); [REF0358](https://www.uludag.edu.tr/dosyalar/fenbilimleri/TEZ%20BA%C5%9EARI%20H%C4%B0KAYELER%C4%B0/2024%20Tez%20Ba%C5%9Far%C4%B1%20Hikayeleri.pdf); [REF0359](https://doi.org/10.11949/0438-1157.20230745); REF0360 (fonte não obtida; sem URL primária confirmada); [REF0363](https://www.copel.com/site/copel-distribuicao/tarifas-de-energia-eletrica/); [REF0364](https://www.gov.br/aneel/pt-br/assuntos/tarifas/entenda-a-tarifa/modalidades-tarifarias); [REF0365](https://sites.engineering.ucsb.edu/~jbraw/mpc/MPC-book-2nd-edition-5th-printing.pdf); [REF0366](https://www.vergnet.com/wp-content/uploads/2023/06/DC-11-00-01-EN_GEV_MP-C_275_kW.pdf); [REF0367](https://github.com/NatLabRockies/turbine-models/blob/e9e4ccc6a87f50c0c65d236154a2897e752c47c9/turbine_models/data/Distributed/BergeyExcel10_8.9kW_7.csv); [REF0368](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.pvsystem.calcparams_desoto.html).

## 5. Metodologia de avaliação e estudos de caso

| claim_id | afirmacao_que_pode_ser_escrita | referencias_adequadas | status |
| --- | --- | --- | --- |
| CLM0034 | C1–C4 são quatro composições do mesmo estudo industrial hipotético. | REF0348;REF0136 | Protocolo proposto; não há resultados nesta missão |
| CLM0035 | O efeito da hierarquia exige mesma configuração física e informação equivalente. | REF0349;REF0216;REF0357 | Protocolo de ablação necessário |
| CLM0036 | COPEL B1 já implementado e CT-046 destinado a futura microrrede são usos independentes. | REF0364;REF0363 | Interpretação anterior corrigida; nenhuma inconsistência de código identificada. |
| CLM0037 | A reamostragem 96→1440 não aumenta a resolução das medições originais. | REF0142;REF0298 | Sustentada por processamento documentado |
| CLM0038 | O caso naval é ensaio de microrrede eletricamente isolada. | REF0093;REF0278;REF0094 | Estudo hipotético a executar |
| CLM0039 | Precisão algébrica, dinâmica do modelo e validade física são verificações diferentes. | REF0354;REF0152;REF0351 | Fundamentável |
| CLM0040 | As hipóteses principais devem ser submetidas a sensibilidade. | REF0294;REF0159;REF0221 | Planejado |

**Fontes ligadas:** [REF0093](https://doi.org/10.3390/math11122728); [REF0094](https://doi.org/10.1109/ojies.2026.3710800); [REF0136](https://doi.org/10.1115/es2014-6570); [REF0142](https://doi.org/10.1371/journal.pcbi.1003285); [REF0152](https://doi.org/10.3390/en7020670); [REF0159](https://doi.org/10.3390/en13071629); [REF0216](https://doi.org/10.1016/j.ecmx.2025.101027); [REF0221](https://doi.org/10.1016/j.ijepes.2025.111516); [REF0278](https://doi.org/10.3390/en19112636); [REF0294](https://doi.org/10.12688/openreseurope.15461.1); [REF0298](https://doi.org/10.1088/2753-3751/ae2870); [REF0348](https://doi.org/10.1049/rpg2.12433); [REF0349](https://doi.org/10.1109/tcst.2013.2295737); [REF0351](https://doi.org/10.1016/j.adapen.2021.100028); [REF0354](https://doi.org/10.1371/journal.pbio.1001745); [REF0357](https://arxiv.org/abs/2011.08004); [REF0363](https://www.copel.com/site/copel-distribuicao/tarifas-de-energia-eletrica/); [REF0364](https://www.gov.br/aneel/pt-br/assuntos/tarifas/entenda-a-tarifa/modalidades-tarifarias).

## 6. Resultados e discussão

| claim_id | afirmacao_que_pode_ser_escrita | referencias_adequadas | status |
| --- | --- | --- | --- |
| CLM0041 | Economia por composição e economia por estratégia devem ser apresentadas separadamente. | REF0348;REF0216 | Depende de resultados próprios |
| CLM0042 | A comparação com literatura deve controlar período, tecnologia, tarifa e métrica. | REF0357;REF0312;REF0094 | Depende de resultados próprios |
| CLM0043 | Reconfigurabilidade deve ser avaliada por repetição de um protocolo em dois casos. | REF0353;REF0343;REF0355 | Depende de resultados próprios |
| CLM0044 | Resultados de degradação ou estabilidade elétrica não são saídas do V2 atual. | REF0159;REF0278;REF0321 | Afirmações fora do escopo atual |

**Fontes ligadas:** [REF0094](https://doi.org/10.1109/ojies.2026.3710800); [REF0159](https://doi.org/10.3390/en13071629); [REF0216](https://doi.org/10.1016/j.ecmx.2025.101027); [REF0278](https://doi.org/10.3390/en19112636); [REF0312](https://doi.org/10.1016/j.adapen.2024.100190); [REF0321](https://doi.org/10.1109/tpwrs.2018.2829021); [REF0343](https://doi.org/10.21105/joss.06274); [REF0348](https://doi.org/10.1049/rpg2.12433); [REF0353](https://doi.org/10.21105/joss.00825); [REF0355](https://doi.org/10.1016/j.esr.2018.07.001); [REF0357](https://arxiv.org/abs/2011.08004).

## 7. Conclusões e trabalhos futuros

| claim_id | afirmacao_que_pode_ser_escrita | referencias_adequadas | status |
| --- | --- | --- | --- |
| CLM0045 | Conclusões devem se limitar às condições e hipóteses ensaiadas. | REF0354;REF0142 | Aguardando resultados |
| CLM0046 | Trabalhos futuros podem incluir tanque H2, degradação, fluxo elétrico e incerteza explícita. | REF0159;REF0221;REF0321;REF0094 | Fundamentável como lacuna |

**Fontes ligadas:** [REF0094](https://doi.org/10.1109/ojies.2026.3710800); [REF0142](https://doi.org/10.1371/journal.pcbi.1003285); [REF0159](https://doi.org/10.3390/en13071629); [REF0221](https://doi.org/10.1016/j.ijepes.2025.111516); [REF0321](https://doi.org/10.1109/tpwrs.2018.2829021); [REF0354](https://doi.org/10.1371/journal.pbio.1001745).


## Matriz operacional detalhada

O CSV 12 e a aba Mapa_citacoes da planilha 06 contêm as 46 relações com questão, claim, fonte, nível F/A/M, limite, leitura ainda faltante e resultado próprio necessário. REF0360 é um marcador de manual não obtido, sem identidade externa conferida e fora das exportações BibTeX/RIS.

## Revisão 01 — artigo próprio PEMFC e escopos COPEL

Fonte P0/F incorporada: [REF0369](https://doi.org/10.5281/zenodo.22978126). Citar Chavez et al. para implementação/identificação e Altıntaş–Ertan para a base. B1 já implementado e CT-046 de microrrede futura são usos distintos; retirou-se a interpretação de discrepância.
