# Checklist de consistência científica e editorial

Use para cada etapa de escrita/revisão. Se a resposta for «não», resolver ou registrar a pendência em vez de preenchê-la com especulação.

## Identidade e arquitetura

- [ ] O título descreve **simulação operacional e despacho energético**, não outras modalidades de simulação não implementadas?
- [ ] O acrônimo SEEDS é apresentado corretamente e sem explicações externas à identidade científica?
- [ ] O texto caracteriza SEEDS2 como **apoio a decisões**, sem comandar instalação física real?
- [ ] A plataforma e o EMS aparecem com **importância semelhante**?
- [ ] O artigo diferencia integração própria de métodos e modelos tomados da literatura?
- [ ] A descrição do software confere com um commit conhecido e os resultados da auditoria?
- [ ] O texto diferencia modelos detalhados e abstrações empregadas no despacho?

## Fluxo de seções

- [ ] Há sete seções principais, na sequência aprovada?
- [ ] A introdução parte de problema concreto, sem prólogo genérico?
- [ ] Os trabalhos relacionados comparam evidências e não apenas enumeram citações?
- [ ] A seção 3 trata de arquitetura científica, não de manual de interface?
- [ ] A seção 4 contém a formulação efetiva, curta mas suficiente, sem equações inventadas?
- [ ] As seções 3 e 4 encerram o desenvolvimento antes de iniciar os estudos?
- [ ] A seção 5 fixa entrada, hipóteses, baseline, horizontes e métricas antes da seção 6?
- [ ] As conclusões respondem às duas contribuições com evidência e limites?

## Estudo I

- [ ] C1, C2, C3 e C4 são **tratamentos do mesmo estudo**?
- [ ] A comparação é organizada por fenômenos em figuras/tabelas integradas?
- [ ] As quatro variantes compartilham perfil, temporalidade e premissas comparáveis?
- [ ] Tarifa, demanda, clima, FV, bateria e PCC têm fontes e hipóteses descritas?
- [ ] Custos são chamados pelo que realmente representam, sem extrapolação econômica?
- [ ] Qualquer inferência sobre a hierarquia usa topologia física e condições controladas?

## Estudo II

- [ ] O sistema é explicitamente isolado da rede?
- [ ] PEMFC, bateria, FV e demanda correspondem à configuração final?
- [ ] O H₂ é assumido não limitante **no horizonte**, sem argumento de autonomia física?
- [ ] SOC, rampa, consumo H₂ e estados têm unidades e interpretação verificadas?
- [ ] A análise respeita a função objetivo, sem exigir intuitivamente certa operação da bateria?
- [ ] Não foram incluídos alcance, quilômetros ou esgotamento de tanque como objetivos do estudo?

## Matemática, evidência e bibliografia

- [ ] Toda equação central corresponde a código e testes ou é explicitamente uma hipótese?
- [ ] As convenções de sinal, unidades, índices, horizontes e tolerâncias são consistentes?
- [ ] A informação de valor futuro foi explicada como aproximação e vinculada à implementação?
- [ ] Os resultados são reais, reproduzíveis e com origem identificável?
- [ ] A descrição distingue verificação computacional de validação experimental?
- [ ] Nenhuma melhoria quantitativa ou conclusão comparativa apareceu antes dos dados?
- [ ] Toda referência utilizada foi verificada quanto à alegação que sustenta?
- [ ] Claude teve liberdade de pesquisar novas fontes, sem recitar apenas o acervo Work?

## Redação e entrega

- [ ] O texto está em português acadêmico natural e impessoal?
- [ ] A prosa progride por causa, método, observação, explicação e consequência, conforme o contexto?
- [ ] As descrições de resultados começam pela observação e depois interpretam?
- [ ] Não há excesso de explicações monográficas de equações?
- [ ] Não há linguagem publicitária, introduções vazias ou burocratês repetitivo?
- [ ] O texto principal contém as informações essenciais sem exigir anexos para ser compreendido?
- [ ] As fontes LaTeX, BibTeX, figuras, dados e condições da execução foram arquivadas?

## Declaração final de escopo

Se o artigo só demonstrar a solução computacional de cenários hipotéticos, a conclusão deve ser compatível com **essa** evidência. Pode-se sustentar funcionamento computacional, integração de modelos, consistência, reprodutibilidade e comportamento de despacho **na representação modelada**; não se pode, sem dados adicionais, afirmar validação física integrada, economias reais garantidas ou segurança operacional de um sistema implantado.
