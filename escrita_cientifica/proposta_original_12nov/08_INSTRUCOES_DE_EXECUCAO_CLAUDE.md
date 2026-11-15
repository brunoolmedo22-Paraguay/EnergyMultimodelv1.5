# Instruções operacionais a entregar a Claude junto aos três ZIPs

## Mensagem de ativação — pronta para copiar

> Você receberá três pacotes independentes que, juntos, definem a preparação científica do artigo SEEDS2:
>
> **(1) CONTEÚDO MESTRE:** tese, título, sete seções, duas contribuições, dois estudos de caso, escopo, perguntas científicas e critérios de evidência;
> **(2) BIBLIOGRAFIA WORK:** referências candidatas, matrizes código–literatura, fichas e BibTeX/RIS;
> **(3) IDENTIDADE AUTORAL BRUNO v1.0:** padrões de escrita e revisão em português científico.
>
> Leia primeiro o `00_LEIA_PRIMEIRO.md` do pacote de conteúdo e o `01_PROTOCOLO_CIENTIFICO_MESTRE.md`, depois o roteiro de seções e os documentos específicos. Considere o pacote de conteúdo como as **decisões científicas e narrativas do autor**; considere a bibliografia como um **acervo aberto, não exaustivo e não vinculante**; e use a identidade autoral para a forma da prosa.
>
> O SEEDS2 é uma plataforma reconfigurável de simulação operacional e apoio a decisões de despacho energético com EMS hierárquico MILP–MPC. As contribuições **plataforma** e **EMS** têm peso equivalente. Há **dois** estudos: (I) uma microrrede industrial hipotética com configurações C1–C4 comparadas conjuntamente; (II) uma embarcação isolada com PEMFC, bateria e FV. Os estudos avaliam o comportamento computacional em cenários hipotéticos, não são validação física experimental integrada.
>
> Você terá liberdade para investigar novas referências em fontes científicas confiáveis, aprimorar a construção argumentativa, propor figuras e definir quais artigos citar. Não limite sua pesquisa à base entregue pela Work e não faça correspondências obrigatórias de citações por parágrafo. **Verifique referências e citações efetivamente utilizadas.**
>
> **Antes de redigir o manuscrito**, confirme o commit/estado do repositório e confronte com os recursos, equações, cenários e resultados disponíveis. Produza um breve diagnóstico dos dados presentes, pendências e eventuais divergências entre este protocolo e o código. Não invente equações, valores, resultados ou funcionalidades. Respeite a estrutura em sete seções e a escrita autoral impessoal e progressiva. Espere a autorização explícita do autor para começar a redação final de cada seção.
>
> Entregue documentos em português de Brasil; prepare fontes `LaTeX/BibTeX` quando a fase de redação estiver autorizada. Para afirmações científicas fortes, associe evidência e origem. Pergunte apenas quando uma decisão não puder ser resolvida de forma confiável a partir do código, dados ou deste protocolo.

## Fluxo de trabalho preferido

### Fase 0 — Conferência

Ler os três ZIPs. Identificar a versão do repositório e os arquivos efetivamente presentes. Registrar diferenças entre **decisão editorial**, **código atual**, **cenário preparado** e **resultado produzido**.

### Fase 1 — Preparação das evidências

Selecionar referências com liberdade, verificar fontes originais de modelos, preparar inventário de equações, estabelecer matriz de ensaios, identificar dados/parametrizações faltantes e avaliar quais gráficos podem ser produzidos. Não inferir resultados a partir da intenção do projeto.

### Fase 2 — Roteiro narrativo detalhado

Propor organização interna concisa de cada seção (e tabelas/figuras candidatas), preservando o roteiro de sete seções e a divisão de contribuição. Relacionar cada afirmação importante à evidência necessária. O autor revisa decisões sensíveis.

### Fase 3 — Redação por seções

Executar somente após autorização. Redigir em português acadêmico do Brasil, impessoal, com progressão causal e linguagem específica; não iniciar com «no contexto atual...». Manter as equações essenciais no texto e detalhamento adicional em apêndices. Não criar resultados para preencher lacunas.

### Fase 4 — Revisão crítica

Comparar texto com código e dados, conferir atribuições bibliográficas, consistência de símbolos e unidades, figuras, terminologia, títulos e afirmações de escopo. Executar o checklist `10_CHECKLIST_DE_CONSISTENCIA.md`.

### Fase 5 — Entrega de artefatos

Manuscrito LaTeX, BibTeX verificado, apêndices se houver, lista das modificações, material reprodutível e resumo das lacunas que permaneçam. Não substituir evidência por imagens promocionais.

## Regras de autonomia científica

- Pode alterar o modo de **expressar** uma ideia, não o sentido científico acordado.
- Pode discutir hipóteses alternativas e apontar riscos metodológicos, sem mudar silenciosamente o modelo.
- Pode introduzir fonte melhor do que a sugerida na biblioteca, após verificar o conteúdo.
- Pode propor análise ou figura adicional, mas não declarar que ela já foi executada.
- Não pode atribuir ao SEEDS2 o desenvolvimento de outro sistema, explicar o «2» nominal, desviar para métodos não implementados ou afirmar implantação operacional real.

## Dois exemplos de comportamento esperado

**Exemplo bom:** «A comparação entre C1 e C4 mede diferenças associadas à composição tecnológica. Para isolar o efeito da hierarquia, recomenda-se repetir C4 com uma referência de curto prazo sob as mesmas condições, caso esta modalidade esteja implementada.»

**Exemplo ruim:** «A arquitetura hierárquica reduziu o custo em 22% e comprovou o desempenho superior do SEEDS2», sem execução, dados, baseline e métrica verificáveis.
