# SEEDS2 — Pacote mestre de conteúdo científico para Claude

**Versão:** 1.0 · **Consolidação das decisões até 12/11/2026 (Paraguai)**  
**Natureza:** protocolo de conteúdo do artigo, não manuscrito, não implementação de software e não banco de referências.  
**Status:** estrutura e mensagem científicas aprovadas pelo autor; resultados, detalhes de código e parâmetros ainda dependem de conferência.

## Os três pacotes independentes

1. **Este ZIP — CONTEÚDO:** o que o artigo deve comunicar, em que sequência, com que alcance, hipóteses, estudos de caso, perguntas científicas e limites.
2. **ZIP — BIBLIOGRAFIA/WORK:** levantamento de referências, matrizes, BibTeX/RIS, fichas e trilhas de busca; Claude pode ampliar e substituir fontes.
3. **ZIP — IDENTIDADE AUTORAL v1.0:** como redigir no estilo acadêmico aprovado pelo autor (português técnico, impessoal, progressivo e orgânico).

Não confundir as responsabilidades. **O presente ZIP não pretende substituir os outros dois.**

## Por onde começar

- **01_PROTOCOLO_CIENTIFICO_MESTRE.md:** visão completa das decisões que não devem se perder.
- **02_NARRATIVA_E_SETE_SECOES.md:** roteiro substancial de cada seção e ligação entre elas.
- **03_ARQUITETURA_E_MODELOS.md:** delimitação do que apresentar sobre a plataforma e seus modelos.
- **04_EMS_HIERARQUICO_E_FORMULACAO.md:** contribuição matemática, coordenação entre horizontes e questões a auditar.
- **05_ESTUDOS_DE_CASO_E_METODOLOGIA.md:** ensaios computacionais industrial e embarcado.
- **06_RESULTADOS_E_EVIDENCIAS.md:** o que cada demonstração pode sustentar; como interpretar resultados.
- **07_PESQUISA_CITACOES_E_AUTONOMIA.md:** liberdade bibliográfica, qualidade das evidências e checagem do repositório.
- **08_INSTRUCOES_DE_EXECUCAO_CLAUDE.md:** protocolo operacional para iniciar a escrita quando autorizada.
- **09_REGISTRO_DE_DECISOES_E_PENDENCIAS.md:** decisões fechadas, provisórias e condições antes da redação.
- **10_CHECKLIST_DE_CONSISTENCIA.md:** revisão de coerência e rastreabilidade.

## O que NÃO é autorizado por este pacote

- Concluir que os experimentos já produziram melhoria mensurada, redução de custos ou validação experimental.
- Atribuir ao código funcionalidades apenas planejadas.
- Confundir a **plataforma de apoio a decisões** com controlador físico autônomo de uma instalação real.
- Acrescentar história institucional ou explicações sobre o número «2» no nome.
- Fixar uma lista fechada de artigos ou determinar citações parágrafo a parágrafo.
- Escrever o manuscrito final sem que o autor determine o momento de iniciar.

## Informação editorial de trabalho

- Idioma do TCC/manuscrito inicial: **português brasileiro**.
- Possível adaptação futura ao inglês para a revista **Measurement: Digitalization**; enquadramento e requisitos atuais devem ser confirmados separadamente.
- Fluxo preferido: **LaTeX/Overleaf**, modelo `elsarticle`, apresentação de trabalho próxima do estilo `3p`, duas colunas. Isso não é garantia das exigências finais da revista.
- Texto principal **autossuficiente**: método, hipóteses, equações essenciais, evidências, interpretação e referências indispensáveis devem estar no artigo; apêndices e repositórios ampliam a reprodutibilidade.

## Hierarquia de evidência

1. Decisões explícitas do autor neste protocolo.
2. Estado **efetivamente auditado** do repositório na revisão usada para escrever.
3. Resultados e dados produzidos e verificados.
4. Literatura consultada e verificada.
5. Propostas e hipóteses a confirmar — não podem ser narradas como fatos.

Se uma decisão editorial entrar em conflito com o código, **não inventar compatibilidade**: registrar o conflito, apontar o que precisa ser implementado ou retificado e pedir decisão científica. Nenhum resultado é conhecido previamente.
