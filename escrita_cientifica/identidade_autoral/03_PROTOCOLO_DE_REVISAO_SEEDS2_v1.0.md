# Protocolo de revisão autoral e científica — SEEDS2
## v1.0 | Preparação para TCC / eventual submissão a periódico

## 1. Objetivo

Verificar que cada trecho assistido por IA: (i) preserva o raciocínio de engenharia documentado do autor, (ii) representa fielmente a implementação matemática e os dados, (iii) respeita as normas do português científico, (iv) apresenta contribuições do SEEDS2 sem extrapolação, e (v) permanece compreensível de forma autônoma no artigo principal.

**A finalidade não é enganar detectores de IA.** O texto deve resultar de supervisão e responsabilidade científica do autor, com a transparência editorial cabível.

## 2. Fluxo de revisão em quatro passagens

### Passagem I — Fundamentação e exatidão

- Para **cada afirmativa técnica**, identificar sua fonte: (a) artigo original, (b) código/commit auditado, (c) dado de caso, (d) resultado numérico identificado, (e) definição matemática, ou (f) interpretação explicitamente rotulada.
- Conferir cada parâmetro, unidade, convenção de sinal, fator de conversão, horizonte, índice temporal e condição inicial em sua evidência de origem.
- Não atribuir a um artigo de literatura uma equação que foi alterada no código sem explicitar a adaptação.
- Não apresentar hipótese, expectativa, simplificação de caso hipotético ou tendência não medida como resultado demonstrado.
- Conferir DOI e correspondência entre autores, título, ano e contribuição citada.
- Diferenciar validação física, verificação numérica, teste de software, comparação analítica, auditoria de solver e reprodutibilidade documental.

**Bloqueio:** se uma afirmação decisiva não tem evidência, interromper a redação desse ponto, registrar `[PENDENTE: fonte / dado / resultado]` e propor como saná-lo.

### Passagem II — Estilo autoral e clareza técnica

Verificar se o parágrafo responde, quando aplicável:

1. Qual problema físico ou operacional está sendo estudado?
2. Por que o método ou dado foi escolhido?
3. Quais condições e parâmetros delimitam a resposta?
4. O que realmente mostram equação, tabela ou figura?
5. Qual interpretação é justificada por esses dados?
6. Que hipótese ou limitação impede extrapolação?

Não forçar seis perguntas em todos os parágrafos. Avaliar o conjunto da seção e manter progressão natural.

**Sinais positivos do estilo do autor:** relações de causa e efeito explícitas; esclarecimento de parâmetros; comparação de métodos; interpretação de números com contexto físico; justificativa de escolhas; reconhecimento objetivo de problemas; figuras usadas como evidência.

**Sinais de descaracterização:** passagens vagas sobre “desafios contemporâneos”; listas de capacidades sem ligação com problema; frases intercambiáveis com qualquer artigo; resultados adjetivados sem métricas; ausência de mecanismo físico.

### Passagem III — Edição científica em português

- Concordância e regência adequadas; remoção de calques ES→PT que não são termos técnicos.
- Termos consistentes: microrrede, despacho, armazenamento, estado de carga, potência, energia, custo operacional, sinal de valor futuro, PEMFC, hidrogênio, ponto de conexão comum.
- Impessoalidade como padrão **provisório**; ajustar à preferência do autor e ao guia da revista.
- Parágrafos estruturados sem generalidades; evitar repetir “observa-se” e “dessa forma” no início de toda frase.
- Notação, siglas e símbolos definidos na primeira ocorrência; legendas com unidades; chamadas corretas para figuras e tabelas.
- Substituir adjetivos emotivos por caracterização de condições: “inconsistente com o balanço”, “não convergiu”, “não foi avaliado”, “fora do domínio de aplicação”.
- Manter expressões pessoais somente se forem uma escolha deliberada do autor e forem adequadas ao gênero do documento.

### Passagem IV — Coerência editorial e escopo

- **Duas contribuições centrais:** plataforma modular + EMS hierárquico, sem subordinar uma à outra.
- **Dois estudos:** microrrede industrial comparativa C1–C4 e embarcação isolada; não dividir o industrial em quatro estudos.
- Controlar variáveis em comparações destinadas a avaliar contribuição do algoritmo.
- Resultados científicamente autossuficientes no manuscrito; arquivos complementares auxiliam reprodução.
- Não incluir no texto principal capturas meramente promocionais ou extensas instruções de interface.
- Resumo, palavras-chave, referências, anonimização, figuras e declarações devem obedecer **às exigências específicas verificadas da revista**, não a suposições do assistente.
- Versão portuguesa do TCC e eventual versão inglesa para Elsevier são produtos editoriais distintos; preservar equivalência científica.

## 3. Tabela operacional de avaliação (0–2 por item)

| Critério | 0 — Falha | 1 — Parcial | 2 — Satisfatório |
|---|---|---|---|
| Precisão factual | Contradição, parâmetro inventado ou dado sem origem | Alguns pontos pendentes | Afirmações rastreáveis e compatíveis |
| Mecanismo de engenharia | Apenas descrição | Causa apresentada parcialmente | Vínculo entre modelo, fenômeno e decisão |
| Justificativa do método | Método afirmado sem critério | Critério genérico | Razão e limites explicitados |
| Interpretação quantitativa | Números repetidos ou adornados | Interpretação incompleta | Dados interpretados sem extrapolação |
| Comparação controlada | Confusão entre topologia e controle | Controle parcial | Condições comparáveis e atribuição prudente |
| Integridade das citações | Ausentes/inventadas/erradas | Algumas verificações pendentes | Origem, DOI e afirmação compatíveis |
| Linguagem PT-BR | Inadequada ou afetada | Correções localizadas | Técnica, clara e natural |
| Identidade autoral | Genérica e promocional | Parte da didática preservada | Causal, concreta, crítica e acessível |
| Limitações | Omitidas ou escondidas | Apenas listadas | Consequências para resultados explicitadas |
| Independência do artigo | Depende de ZIP/apêndice para entender método | Falta contexto em pontos | Artigo compreensível sem complementos |

**Pontuação máxima:** 20. Não usar a nota como “detector de IA”. Um texto com 18/20 ainda é **inaceitável** se tiver erro factual ou citação inventada. Critérios de precisão e citações são eliminatórios.

## 4. Distinguir o que foi visto, inferido e demonstrado

Use a escala de evidência:

- **Observado:** o gráfico ou tabela apresenta uma característica mensurável, dentro dos dados analisados.
- **Interpretado:** explica-se o mecanismo mais plausível, com indicação de pressupostos.
- **Verificado numericamente:** demonstra-se um comportamento por teste definido, com tolerância e resultado.
- **Validado experimentalmente:** requer dados independentes e protocolo de validação física; **não** usar esse rótulo por mera simulação.
- **Hipótese:** previsão plausível ainda sem evidência suficiente.

Exemplo de revisão conceitual:

- **Evitar:** “A inclusão da bateria comprova que o EMS hierárquico sempre reduz o custo.”
- **Preferir, caso os dados permitam:** “Para a configuração e o perfil analisados, a inclusão da bateria alterou o despacho nas horas de maior tarifa. A contribuição específica do planejamento hierárquico foi avaliada separadamente, mantendo-se fixa a configuração física da microrrede.”

O segundo trecho também requer medidas reais antes de entrar como resultado definitivo.

## 5. Formato de devolutiva a cada seção

Quando o autor pedir revisão de um trecho, responder com:

1. **Texto revisado completo**, preservando a intenção científica.
2. **Mudanças de substância**, destacando onde a redação alteraria significado, hipótese, variável ou escopo.
3. **Questões para o autor**, apenas nos pontos de decisão real.
4. **Pendências de evidência**, identificando fontes, números ou resultados não conferidos.
5. **Registro breve de estilo**: quais traços da escrita original foram preservados e quais vícios foram corrigidos.

Não inventar citações apenas para preencher espaços. Manter `\cite{chave}` ou `\parencite{chave}` somente para chaves presentes no `.bib` ou marcadas para revisão.

## 6. Integração com Overleaf

- O autor mantém um projeto LaTeX versionado; assistentes editam arquivos `.tex`, `.bib`, figuras ou tabelas a partir de um ZIP fornecido.
- O orientador revisa o PDF; observações devem ser associadas à página, figura, equação ou trecho.
- Cada rodada registra versão, alterações, pendências resolvidas e pontos ainda em avaliação.
- A compilação do PDF verifica **formato**, não garante exatidão científica. Conferir visualmente referências cruzadas, equações extensas, tabelas e figuras.

## 7. Histórico de decisões

- 12/11/2026: v1.0 criada a partir de quatro PDFs, dois individuais e dois coletivos.
- Calibração concluída em sete pontos: autoria integral de eólica e hidrelétrica; voz impessoal; concisão de artigo; dados primeiro e explicação física depois; postura responsável sem culpa; prosa orgânica; motivação da bancada configurável. Coautoria de B e S continua não atribuída individualmente.


## 8. Revisão autoral calibrada (12/11/2026)

### Testes prioritários

1. **Voz:** todo o artigo deve privilegiar formulações impessoais, sem chamar atenção para a escolha gramatical.
2. **Concisão:** cortar definições extensas e derivações pedagógicas que não alterem a compreensão dos resultados; manter a formulação essencial no artigo.
3. **Resultado e explicação:** identificar primeiro o padrão numérico e o intervalo/condição; só então oferecer interpretação física sustentada. Se a explicação for hipótese, marcar claramente.
4. **Tom:** nenhuma linguagem confessional (“falhamos”, “não soubemos”, “esquecemos”) e nenhuma justificação retórica que tente transformar um erro material em escolha válida. Corrigir questões factuais e comunicar limitações relevantes.
5. **Naturalidade:** revisar aberturas vazias, sequências de frases com estrutura idêntica e uso excessivo de travessão, duplo hífen (`--`) e ponto e vírgula. Não sacrificar clareza ou gramática ao evitá-los.
6. **Foco intelectual:** quando pertinente, mostrar a distinção entre bancada reconfigurável e configuração fixa, respaldando a comparação com capacidades implementadas e testes; não usar analogia como demonstração empírica.

### Exemplo de feedback editorial sem inventar resultados

- **Revisão fraca:** “A ferramenta apresentou resultados inovadores, robustos e extremamente relevantes.”
- **Revisão tecnicamente adequada:** “[PENDENTE: inserir a métrica verificada]. Esse comportamento está relacionado a [PENDENTE: mecanismo físico ou lógico demonstrado]. A interpretação restringe-se a [PENDENTE: domínio efetivamente avaliado].”

O segundo formato é um **esqueleto de verificação**, não texto científico pronto para publicação. A presença de qualquer marcador bloqueia finalização.