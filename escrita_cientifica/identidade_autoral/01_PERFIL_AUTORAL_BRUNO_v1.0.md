# Identidade de escrita científica — Bruno Olmedo
## Perfil autoral analítico v1.0 | 12 de novembro de 2026

**Status:** versão calibrada com as respostas explícitas do autor em 12/11/2026. Evidências documentais continuam limitadas aos quatro PDFs analisados; futuras versões podem ser refinadas por revisão do autor.  
**Finalidade:** orientar a redação acadêmica original do projeto SEEDS2 em português brasileiro, preservando padrões de raciocínio observáveis nos trabalhos fornecidos.  
**Não é:** teste de autoria, detector de IA, reconstrução psicológica, presunção de que todas as passagens de trabalhos coletivos pertencem a Bruno, nem licença para reproduzir imprecisões metodológicas dos trabalhos de graduação.

## 1. Corpus e peso das evidências

| Identificador | Trabalho | Idioma predominante | Páginas | Peso para perfil | Motivo |
|---|---|---|---:|---|---|
| H | `DOC-20261112-WA0036.pdf` — *Estudio hidroenergético preliminar* (2025) | Espanhol técnico com léxico misto | 41 | **Muito alto** | Autoria integral, palavra por palavra, confirmada pelo autor; cálculos, alternativas e justificativas |
| E | `DOC-20261112-WA0037.pdf` — *Análise estatística do vento* (2025) | Espanhol técnico com léxico misto | 35 | **Muito alto** | Autoria integral, palavra por palavra, confirmada pelo autor; análise quantitativa, figuras e interpretações |
| B | `DOC-20261112-WA0038.pdf` — biocombustíveis HEFA/HDO (2024) | Português brasileiro, com interferências do espanhol | 23 | Complementar | Coautoria; não é possível atribuir passagens individuais sem confirmação |
| S | `DOC-20261112-WA0039.pdf` — coletor solar híbrido PVT (2024) | Português brasileiro, com interferências do espanhol | 12 | Complementar | Coautoria; testemunho útil de didática física e declaração de resultados insatisfatórios |

**Nota de interpretação:** o autor confirmou ter redigido integralmente os documentos individuais H e E, palavra por palavra. A origem detalhada de cada trecho dos trabalhos em coautoria B e S permanece não confirmada. Não atribuir estes últimos textos exclusivamente a Bruno. As primeiras páginas podem apresentar registro mais formal que as seções de cálculo; não inferir assistência de IA a partir dessa diferença. Elementos padronizados do curso, normas, tabelas copiadas e citações literais foram excluídos da inferência de estilo.

## 2. Diagnóstico central

A característica mais consistente é a **escrita de engenharia orientada ao percurso do cálculo e à interpretação do resultado**. O autor frequentemente organiza a explicação segundo uma cadeia próxima de:

**problema físico ou pergunta prática → dados disponíveis → escolha do modelo ou método → operação matemática/computacional → resultado numérico ou gráfico → interpretação de engenharia → ressalva ou próxima decisão.**

Não se trata somente de expor um modelo formal: o texto procura acompanhar o leitor e tornar explícito *por que* determinada operação foi realizada. O melhor aproveitamento para SEEDS2 consiste em **preservar essa explicação causal**, dando-lhe concisão, linguagem acadêmica em português e rigor de verificação.

### Traço A — Explica por que um cálculo é necessário, não apenas como executá-lo

- **H, pp. 3–5:** a introdução estabelece relação entre registros históricos, caracterização de vazões e dimensionamento; o capítulo passa diretamente à necessidade de transposição da vazão para o ponto do projeto.
- **E, pp. 4–7:** apresenta o que a distribuição Weibull representa, esclarece os parâmetros `k` e `c`, deriva a linearização e interpreta a frequência acumulada antes de calcular a disponibilidade.
- **S, pp. 6–9 (coautoria):** explica a analogia entre resistência térmica e elétrica para motivar o circuito térmico.

**Regra:** antes de uma equação importante, expor o problema específico que ela resolve; depois da equação, dizer o que significam suas variáveis, como é aplicada e o que o resultado permite avaliar. Não introduzir uma equação apenas por ornamentação.

### Traço B — Prefere a progressão concreta e sequencial

- **E, pp. 12–16:** separa dados, agrupa registros por mês, explica o procedimento e, em seguida, apresenta as curvas e parâmetros.
- **H, pp. 5–8:** apresenta transposição por área e mínimos quadrados, compara as respostas e escolhe um caminho para a etapa seguinte.
- Expressões recorrentes: “Con esto”, “De esta forma”, “Procedemos”, “Ahora”, “Para este caso”, “A partir de”.

**Regra:** conservar a sequência lógica das ações, mas não repetir conectores automaticamente. Preferir transições que nomeiem a consequência concreta: “Com os parâmetros estimados, calculou-se...”, “A comparação entre os métodos indica...”.

### Traço C — Transforma números em significado físico ou operacional

- **E, p. 7:** interpreta numericamente a frequência de disponibilidade, em vez de deixar apenas a integral.
- **E, p. 30:** separa o tempo de indisponibilidade por baixa velocidade daquele por velocidade excessiva.
- **E, p. 34:** explica o fator de capacidade relativamente baixo a partir da distribuição do tempo nos diferentes regimes operacionais.
- **H, pp. 26–27:** traduz a regularização de vazão em operação ao longo do tempo; destaca que preservar a média não significa manter vazão constante.

**Regra:** após reportar uma métrica, explicar sua causa física ou operacional, com referência aos dados disponíveis. Não parafrasear o número; interpretar o mecanismo.

### Traço D — Gosta de comparações explícitas entre alternativas

- **H, pp. 6–8:** transposição por área versus mínimos quadrados, incluindo diferenças percentuais.
- **E, pp. 29–34:** duas formas de estimar parâmetros de Weibull e respostas de geração anual; discute diferenças pequenas, não apenas a condição “vencedora”.
- **H, pp. 32–35:** alternativas de configuração das turbinas e consequências operacionais.

**Regra:** quando houver alternativas, apresentar premissas comuns, medidas de comparação, diferenças observadas e as razões para adotar cada uma. Em SEEDS2, distinguir mudança de topologia de mudança da estratégia de controle.

### Traço E — Assume posições de engenharia e justifica escolhas

- **H, pp. 32–34:** discute configuração de turbinas e compromissos entre operação, disponibilidade e número de polos.
- **E, p. 27:** declara escolha de uma abordagem mais trabalhosa para corrigir diretamente registros de velocidade antes de recalcular parâmetros.

**Regra:** conservar decisões argumentadas. Na linguagem científica, substituir preferências pessoais ou intuitivas por **critério, hipótese e evidência**: “Adotou-se a configuração X devido a...”, deixando claro quando é uma decisão de projeto e não uma otimização provada.

### Traço F — Não esconde problemas e limitações

- **E, p. 17:** reconhece deslocamento sistemático entre distribuições e frequência relativa, oferece hipótese explicativa e relata não ter resolvido integralmente o problema.
- **H, pp. 37–39:** observa inconsistência em cálculo de cota hidráulica e reconhece alturas determinadas arbitrariamente por falta de estudo estatístico específico.
- **S, pp. 10–11 (coautoria):** informa que a simulação apresentou eficiências fisicamente inaceitáveis e, portanto, não sustentava conclusões úteis.

**Regra calibrada:** o autor prefere postura impessoal e responsável, sem linguagem confessional ou autodepreciativa. Descrever escolhas, seu domínio de aplicação, limitações e melhorias futuras de modo tecnicamente fundamentado. **Elevar o rigor**: separar anomalia observada, hipótese de causa, diagnóstico confirmado, correção efetuada, pendência e efeito sobre as conclusões. Se houver erro material demonstrado, corrigir ou explicitar sua consequência; jamais converter uma justificativa retórica em evidência nem ocultar problemas que afetem a validade. Não declarar um modelo validado apenas porque duas ferramentas produziram o mesmo número.

### Traço G — Apoia a narrativa em figuras e tabelas

- **E, pp. 14–20, 28–34:** usa rosas dos ventos, histogramas, distribuições, tabelas de `k/c`, disponibilidade e geração para articular comparações.
- **H, pp. 12–27, 32–39:** apresenta fluviogramas, permanência de vazões, Rippl, Conti Varlet, tabelas dimensionais e figura do projeto.
- **S, pp. 6–9 (coautoria):** diagramas físicos e circuitos para explicar o fluxo térmico.

**Regra:** figura é evidência de um fenômeno, não ilustração decorativa. Toda referência a figura deve indicar o que observar, a causa provável ou confirmada e sua relevância para a pergunta científica.

### Traço H — Adota uma didática próxima ao interlocutor

- Marcadores como “Note que”, “Nótese”, “Observe”, “Podemos notar” convidam o leitor a acompanhar o raciocínio.
- **E, pp. 6–7:** exemplo de probabilidade acumulada usando valores simples para facilitar entendimento.
- **S, p. 9:** explicação física do circuito “passo a passo” (evidência complementar de coautoria).

**Regra:** não eliminar a acessibilidade e o esforço pedagógico. Num artigo científico, preferir formulações impessoais e objetivas sem perder a explicação intuitiva: “Esse resultado significa que...”; “A diferença decorre de...”; “A Figura 4 evidencia...”.

## 3. Padrões linguísticos observados (com nível de segurança)

| Padrão | Evidência | Confiança | Orientação de transferência |
|---|---|---|---|
| Primeira pessoa do plural em métodos | “utilizamos”, “obtenemos”, “presentamos”, “consideramos” em H/E | Alta nos textos anteriores | **Preferência atual expressa:** voz impessoal. Em PT, “adotou-se”, “calculou-se”, “foram considerados”, “observou-se”. Não usar “nós” por padrão |
| Conectivos de consequência | “Con esto”, “De esta forma”, “Por tanto” | Alta | “Com isso”, “Dessa forma”, “Portanto”, sem cadência mecânica |
| Conectivos de contraste | “En cambio”, “Aun así”, “Por otro lado” | Média/alta | “Em contrapartida”, “Ainda assim”, “Por outro lado”, quando necessários |
| Verbos de operação | calcular, estimar, comparar, apresentar, montar, corrigir, verificar | Alta | Preservar concretude; evitar verbos vazios como “potencializar” |
| Referências a gráfico/tabela | Frequentes e integradas ao raciocínio | Alta | Adotar chamadas localizadas, com observação específica e não redundante |
| Explicações parentéticas e exemplos | Frequentes, inclusive valores numéricos | Alta | Conservar quando esclareçam hipótese; reduzir parênteses longos |
| Linguagem avaliativa espontânea | “DATO INTERESANTE”, “Lastimosamente”, “lo ideal”, “carísimo” | Média | Converter avaliação em afirmação técnica precisa, sem descaracterizar a franqueza |
| Mistura ES/PT, calques e sintaxe oral | Especialmente em H/E e trabalhos coletivos PT | Alta | Tratar como **fenômeno linguístico**, não como assinatura a imitar |

## 4. Amostras literais de evidência

As citações abaixo são **curtas**, apenas para localizar o fenômeno estilístico. Não reutilizá-las como texto científico nem apresentá-las como prova de autoria individual nos documentos coletivos.

1. **E, p. 5:** “Con esto ya tenemos la linealización de la curva” — passagem do fundamento matemático à operação prática.
2. **E, p. 7:** “Otra forma de calcularla es calculando el área bajo la curva” — procura via alternativa de compreensão/verificação.
3. **E, p. 17:** “se asemeja más a un error sistemático” — diagnóstico crítico explícito, ainda hipotético.
4. **E, p. 30:** “DATO INTERESANTE. Note que la disponibilidad de casi 80%” — destaque interpretativo de leitura operacional.
5. **E, p. 34:** “Es un valor bajo considerando que los valores de Pinto, 2014” — confrontação com referência e necessidade de explicação.
6. **H, p. 7:** “Comparando los resultados obtenidos tanto por la relación de área” — comparação de métodos.
7. **H, p. 27:** “Es decir, la media es mantenida pero no se opera continuamente” — distinção física crucial extraída de resultados.
8. **H, p. 39:** “estos valores fueron determinados arbitrariamente, con un enfoque realista” — explicitação da natureza hipotética das premissas.
9. **S, p. 10 [coautoria]:** “no faz sentido termos uma eficiência maior de 100%” — teste de plausibilidade física e recusa de conclusão inconsistente.

## 5. O que NÃO devemos reproduzir no artigo SEEDS2

- **Não imitar erros de linguagem**: palavras espanholas em português, concordâncias imprecisas, acentuação inconsistente ou calques como “a modo de”. A voz autoral está no raciocínio, não nesses desvios.
- **Não imitar informalidades**: “caríssimo!”, “para facilitar nossa vida”, “lamentavelmente” repetido, títulos como “DATO INTERESANTE”. Converter a mensagem em linguagem acadêmica adequada.
- **Não imitar confirmações fracas**: coincidência entre Matlab e GeoGebra pode verificar uma conta sob as mesmas hipóteses, mas não constitui validação física ou independente de um modelo.
- **Não replicar ajustes empíricos para forçar concordância** sem protocolo, objetivo de ajuste e avaliação de erro declarados.
- **Não reproduzir citações longas** usadas nos trabalhos de revisão sem verificar a fonte original; preferir paráfrase própria e citações corretas.
- **Não declarar como universal** um resultado obtido em um estudo de caso hipotético.
- **Não atribuir separadamente** os capítulos de coautoria sem confirmação do autor.

## 6. Tradução de estilo: espanhol técnico → português científico

| Construção frequente no corpus | Tradução editorial recomendada |
|---|---|
| “Con esto obtenemos...” | “A partir desses parâmetros, obtém-se...” |
| “Podemos notar que...” | “Observa-se que...” **somente quando se indicar o que o dado mostra** |
| “Para nuestro caso...” | “Nas condições do caso estudado...” |
| “Es interesante destacar...” | “A diferença está associada a...”, quando sustentada |
| “No dispongo de tiempo para verificar” | “Esta hipótese não foi verificada no presente estudo e permanece como limitação.” |
| “Elegimos ese porque da mejores resultados” | “Adotou-se o método X em razão do critério Y, avaliado pela métrica Z.” |
| “La curva está bien” | “A curva apresenta concordância [quantificada] segundo a métrica [definida].” |
| “Nuestro modelo hace...” | “O modelo implementado considera...”, com referência à versão do código |

## 7. Aplicação por seção do artigo SEEDS2

1. **Introdução:** motivação técnica específica, não slogans de sustentabilidade; problema de sistemas heterogêneos e decisões intertemporais; contribuição de plataforma + EMS sem hipérboles.
2. **Fundamentação:** apresentar referência, explicar método, compará-lo ao requisito de SEEDS2 e explicitar lacuna de *integração/avaliação* quando demonstrável; não confundir “não encontramos” com “não existe”.
3. **Arquitetura:** como e por que os módulos e contratos foram organizados; fluxos verificáveis; desafios de configuração e persistência; sem manual de cliques.
4. **EMS:** problema físico/operacional antes de cada bloco de equações; estados, restrições e custo; função de valor futuro; diferenças entre termos calculados e custos realizados.
5. **Metodologia:** a mesma transparência do corpus sobre dados, escalas, procedimentos e hipóteses, mas com protocolo controlado e reproduzível.
6. **Resultados:** comparar padrões observados e mecanismos, não narrar cada caso isoladamente; estudo industrial com quatro configurações integradas e embarcação isolada como segundo estudo; distinguir efeito de topologia do efeito de algoritmo.
7. **Conclusões:** responder perguntas científicas com evidência quantificada; reconhecer limitações do solver, dos modelos, dos dados e da extrapolação física.

## 8. Diagnóstico global

**Força autoral dominante:** explicação causal acessível dos fenômenos e das decisões de engenharia, sustentada por cálculos, comparações, tabelas e figuras.  
**Segunda força:** franqueza ao indicar inconsistências e premissas simplificadoras.  
**Maior risco ao migrar para periódico internacional:** transferir para o português/inglês de artigo científico a informalidade da sala de aula e confundir verificações computacionais com validação independente.  
**Objetivo de edição:** texto com a lógica de Bruno, mas com maior concisão, precisão terminológica e níveis de evidência explicitados.

## 9. Incertezas para resolver com o autor

1. Qual seção dos documentos de coautoria foi escrita por Bruno?
2. Houve revisão ou reescrita extensa por IA, orientadores ou colegas nos textos individuais?
3. Bruno prefere redação impessoal ou primeira pessoa do plural no artigo em português?
4. Qual grau de detalhe didático ele deseja manter em seção matemática?
5. Como diferencia tom de TCC e tom de periódico internacional?
6. Quais construções considera representativas e quais deseja abandonar?

**Próxima versão:** v1.0 após respostas ao questionário e uma pequena amostra nova de escrita espontânea, opcional.


## 8. Calibração autoral confirmada em 12/11/2026 — sete respostas

As declarações abaixo são **preferências explícitas atuais do autor**, distintas de características inferidas dos PDFs. Devem prevalecer quando houver conflito com o perfil descritivo de 2024–2025.

1. **Autoria principal confirmada:** os trabalhos de eólica e hidrelétrica foram integralmente redigidos pelo autor, palavra por palavra. As passagens de documentos coletivos não foram individualizadas.
2. **Voz:** usar **redação impessoal** no TCC e no artigo, mesmo quando o registro estudantil anterior utilizava primeira pessoa.
3. **Concisão:** os trabalhos analisados são monografias ou relatórios extensos. Para artigo científico, explicar a formulação com **brevidade e assertividade**, incluindo hipóteses e relações essenciais, sem derivação pedagógica longa.
4. **Resultados:** começar pelo **achado quantitativo ou padrão observado** e, depois, explicar o mecanismo físico/operacional compatível com os dados. Separar explicação causal comprovada de interpretação plausível.
5. **Postura crítica:** adotar tom **impessoal, responsável e justificativo** para escolhas de implementação e limitações. Evitar autopunição discursiva. Não esconder nem racionalizar erros materiais identificados; avaliá-los e corrigir antes de afirmar validade científica. Contribuições da banca podem orientar melhorias futuras.
6. **Naturalidade:** eliminar introduções genéricas, grandiloquência, repetições artificiais, prosa robótica e **uso sistemático de travessões duplos ou ponto e vírgula**. Ambos os sinais podem ser usados quando a sintaxe exigir, mas não como maneirismos.
7. **Motivação intelectual:** o SEEDS2 é concebido como **bancada virtual configurável**, em contraste com um otimizador fixo para uma microrrede predeterminada. O usuário monta sua própria bancada com os componentes adequados ao experimento; a configuração deve ser acompanhada de modelos físicos e resultados coerentes dentro das hipóteses declaradas. Trata-se de **imagem explicativa útil para orientar a argumentação**, não prova científica de superioridade ou fidelidade física universal.

### Como usar a analogia da bancada virtual

**Preservar como ideia-base:** a comparação entre uma bancada experimental configurável e outra previamente montada torna evidente a diferença de finalidade entre plataforma modular e otimização específica.

**Não reproduzir sem refinamento no artigo:** expressões espontâneas como “se contrastam de forma bruta”, “minha fraqueza por software”, “rigor físico” sem especificar validação, ou narrativas pessoais sobre criação de páginas web desde o colégio. Elas são informações de contexto para entender a motivação do autor, não evidência acadêmica nem justificativa de qualidade.

**Formulação conceitual (não trecho do artigo):** a motivação é permitir a composição e avaliação de diferentes configurações energéticas num mesmo ambiente; seus benefícios precisam ser demonstrados por contratos, modelos, testes e experimentos reproduzíveis. O esforço de desenvolver software, por si só, não mede a contribuição científica.

### Perfil de voz resultante

- **Clara sem ser rasa.** Evitar explicar fórmulas elementares extensamente, mas sempre explicitar o papel da equação central.
- **Impessoal sem ser burocrática.** Escrever “A simulação apresentou...”, não “Nós observamos...” nem “Foi possível observar, ao longo de uma extensa análise, que...”.
- **Numérica antes de explicativa.** Ao discutir resultados, começar com valor/padrão específico e passar à explicação física, sem afirmar causalidade não demonstrada.
- **Decidida sem ser defensiva.** Expor escolhas técnicas, hipóteses de escopo e limites com justificativas testáveis.
- **Orgânica sem marcas artificiais.** Frases de tamanhos variados, períodos curtos quando possível, pontuação natural, transições conduzidas pelo conteúdo.

### Prioridade em conflitos

Precisão científica e política editorial específica > evidência verificável > instruções de conteúdo do autor > preferências atuais de estilo > hábitos históricos dos PDFs. Preferências estéticas nunca autorizam omissões científicas.