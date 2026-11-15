# Registro de decisões editoriais e assuntos pendentes

**Data de corte:** 12/11/2026, horário do Paraguai.  
**Propósito:** impedir que propostas sejam confundidas com resultados ou que decisões aprovadas sejam reabertas sem motivo.

## A. Decisões autorais confirmadas

| ID | Decisão | Consequência para Claude |
|---|---|---|
| D-01 | Título de trabalho definido com «simulação operacional e otimização do despacho ... por meio de um EMS hierárquico baseado em MILP–MPC» | Preservar ambos os objetos e atribuir EMS ao método, não à microrrede |
| D-02 | SEEDS significa **Smart Energy Ecosystem for Decision Support** | Expandir o acrônimo quando pertinente, sem explicar o número 2 |
| D-03 | SEEDS2 é apoio a decisões por simulação/visualização, não atuação autônoma em planta real | Não descrever sistema físico automático de controle |
| D-04 | Duas contribuições, **plataforma e EMS**, com peso equivalente | Não relegar arquitetura ou método a apêndice |
| D-05 | A contribuição reside nas escolhas e integração do sistema; não reivindicar invenção de MILP, MPC nem «primeiro» | Fazer comparação honesta com literatura afim |
| D-06 | Estrutura de **sete seções** aprovada | Não acrescentar capítulo principal que quebre esta lógica |
| D-07 | Seção 3 é arquitetura/modelos/plataforma; 4 é EMS/formulação; após 4 o sistema está descrito | Seção 5 inicia avaliação, não novo desenvolvimento |
| D-08 | Estudos de caso são demonstrações computacionais, **não validação experimental integrada** | Vocabulário e conclusões devem refletir isso |
| D-09 | **Dois estudos**, não cinco | Industrial com quatro tratamentos + embarcação isolada |
| D-10 | Estudo I usa C1 rede, C2 rede+FV, C3 rede+bateria, C4 rede+FV+bateria | Comparar C1–C4 por fenômenos, não como quatro miniartigos |
| D-11 | Estudo industrial pode ocupar **mais espaço** que o embarcado | Dar densidade às comparações adicionais |
| D-12 | Efeito da composição física ≠ efeito da estratégia EMS | Manter topologia fixa ao comparar controladores |
| D-13 | Estudo II focaliza distribuição de energia PEMFC/FV/bateria, SOC, restrições e H₂ consumido | Não discutir alcance/autonomia/quilometragem |
| D-14 | No estudo embarcado, H₂ **não é limitante no horizonte** | Declarar hipótese; não criar dinâmica de esgotamento de tanque |
| D-15 | Valor futuro é aproximação importante a explicar/avaliar, não valor exato garantido | Fundamento matemático, testes e limitações claros |
| D-16 | Claude dispõe de liberdade para buscar outras fontes e escolher citações | Não usar lista fechada nem referência imposta por parágrafo |
| D-17 | Texto inicial em português brasileiro, voz impessoal, conciso e progressivo; guia autoral v1.0 | Não copiar vícios de IA ou prolongar derivações |
| D-18 | Resultados: observação numérica → explicação física → alcance operacional | Prosa de discussão deve seguir lógica, sem virar fórmula mecânica |
| D-19 | Texto principal autossuficiente; apêndices e dados complementares | Não esconder elementos centrais apenas em ZIP |
| D-20 | LaTeX/Overleaf como fluxo de trabalho, estilo `elsarticle` visual `3p` | Confirmar exigências finais antes da submissão |
| D-21 | Sem texto definitivo antes de concluir software e dados necessários; nenhum resultado inventado | Trabalhar por auditoria e redação autorizada |

## B. Itens que ainda dependem de evidência ou auditoria

| ID | Questão | Como resolver |
|---|---|---|
| P-01 | Commit e versão de SEEDS2 usados como base do artigo | Fixar hash e lista de módulos/testes disponíveis |
| P-02 | Descrição exata da função objetivo, estados, limites e valor futuro | Ler código, testes, logs e contratos do EMS |
| P-03 | Relação entre modelos de bancada e envoltórias de despacho | Rastrear código e documentar aproximações |
| P-04 | Referência original exata da PEMFC e proveniência dos parâmetros | Verificar artigo primário, manuscrito próprio, código e dados do catálogo |
| P-05 | Parâmetros definitivos do Estudo I, fonte COPEL, tarifa e meteorologia | Abrir pacote final de cenário, validar fontes e cálculos |
| P-06 | Parâmetros definitivos da embarcação, rampa/estado/30 kW e curvas | Auditar configuração final, resolução e unidades |
| P-07 | Baseline metodológico para comparação hierárquica | Confirmar implementação e igualdade das condições |
| P-08 | Indicadores, gráficos e tabelas finais | Produzir simulações e avaliar o que é de fato medido |
| P-09 | Auditoria de consistência, repetibilidade, factibilidade e solver | Executar procedimentos em ambiente reproduzível |
| P-10 | Condições editoriais da revista escolhida | Conferir guia específico e situação editorial atual |
| P-11 | Referências científicas efetivamente utilizadas | Seleção independente e checagem de conteúdo/DOI |
| P-12 | Afirmações de melhoria ou limitações quantificadas | Somente após análise de resultados verificados |

## C. Decisões que NÃO estão fechadas

- Tamanho final de abstract, quantidade de figuras e número de páginas; dependem de requisitos editoriais confirmados.
- Subtítulos secundários além da organização de 6.1–6.4; Claude pode propor.
- Formato exato de cada figura, layout e critérios de compressão editorial.
- Estrutura final do baseline contra a hierarquia e horizonte de análise, até confirmar código.
- Valores finais dos parâmetros e custos dos dois estudos.
- Comparações quantitativas, direção e magnitude dos resultados.

## D. Princípio de atualizações

Quando uma condição muda em SEEDS2, Claude deve registrar: **qual decisão mudou, por quê, qual arquivo/commit a confirma e como a alteração afeta o manuscrito**. Nunca alterar silenciosamente um valor para fazer caber uma narrativa anteriormente imaginada.
