# SEEDS — Roteiro da defesa, bloco a bloco e slide a slide (proposta v1)

**Base:** artigo final aprovado (PDF completo, 56 p.) + plano estrutural (`SEEDS_Plano_Estrutural_Defesa.md`).
**Duração:** 30 min · **Slides principais:** capa + 24 · **Auxiliares:** A1–A15 (só para a arguição).

---

## 0. O fio condutor

A defesa inteira responde a UMA pergunta, apresentada no slide 4 e respondida no slide 22:

> **Um mesmo gerenciamento energético consegue operar microrredes de composições diferentes, levando em conta o valor futuro da energia armazenada?**

A pergunta tem duas metades, e cada uma corresponde a uma contribuição do trabalho:

| Metade da pergunta | Contribuição | Marcador visual |
|---|---|---|
| "...microrredes de composições diferentes..." | **A — Plataforma modular** (representação energética comum) | ícone A |
| "...valor futuro da energia armazenada..." | **B — EMS hierárquico MILP–MPC** (planejador + sinal de valor futuro) | ícone B |

**Metáfora de abertura e de fechamento:** o custo futuro da água no SIN (NEWAVE → DECOMP → DESSEM).
"A água turbinada hoje pode obrigar o despacho de uma térmica amanhã" ↔ "a energia descarregada da bateria agora pode faltar na ponta". Ela aparece no slide 2, volta no slide 8 (Bellman) e no slide 18 (evidência) e fecha a defesa no slide 22. É o que dá unidade à história.

**Arco narrativo (o "porque" de cada parte):**

```
Problema ──► Por que é difícil ──► O que falta ──► O que fiz (A + B) ──► Em que sistemas testei
  (I)            (I)                  (I)              (II)                     (III)
                                                                                  │
   O que respondi e o que não ◄── O que os resultados mostram ◄── Vejam funcionando
          (VI)                              (V)                         (IV)
```

## 1. Regras de construção dos slides

1. **Títulos-afirmação:** o título diz a conclusão do slide ("A bateria carregou antes de a ponta entrar no horizonte"), não o tema ("Resultados C3").
2. **Uma ideia por slide.** Se precisar de duas, são dois slides.
3. **As cores dos slides são as cores do aplicativo:** Solar âmbar, Bateria violeta, Rede vermelho, PEMFC verde-azulado, Demanda preto ou branco. Assim, a passagem slides → app → slides parece contínua, e a banca reconhece no app o que viu nos slides.
4. **Barra de progresso** discreta com os 6 blocos (I–VI) e os ícones **A/B** quando o slide sustenta uma contribuição.
5. **Equações no corpo principal: só 11, 13, 15, 17 e 18.** O resto vai para os auxiliares.
6. **Números grandes, poucos e com unidade.** As tabelas completas ficam nos auxiliares.
7. **A "Fala" é um guia, não um texto para decorar.** Treinar a ideia e as frases-ponte, não as palavras.

## 2. Distribuição do tempo

| Bloco | Slides | Tempo | Acumulado |
|---|---|---:|---:|
| Capa | 0 | 0:20 | 0:20 |
| I — Problema, lacuna e objetivo | 1–4 | 3:30 | 3:50 |
| II — Fundamentos e SEEDS | 5–12 | 8:00 | 11:50 |
| III — Estudos de caso | 13–15 | 2:30 | 14:20 |
| IV — Hands-on | (app) | 6:00 | 20:20 |
| V — Resultados | 16–21 | 6:00 | 26:20 |
| VI — Conclusões | 22–24 | 2:00 | 28:20 |
| Margem | | 1:40 | 30:00 |

---

## CAPA

### Slide 0 · Capa (0:20)
**Na tela:** título completo; nome; orientador e coorientador; UNILA / ILATIT / Engenharia de Energia; data (9/12/2026). Nenhum outro elemento.
**Fala:** "Bom dia. Vou apresentar o SEEDS, um simulador modular de microrredes com gerenciamento energético hierárquico, desenvolvido com o professor Jorge e com o Daniel."

---

## BLOCO I — Problema, lacuna e objetivo (3:30)

> **Função do bloco:** a banca sai daqui sabendo QUAL problema existe, POR QUE ele é difícil, O QUE falta na literatura e QUAL pergunta o trabalho responde.

### Slide 1 · «As fontes se diversificaram — e chegaram aos sistemas pequenos» (0:40)
**Por que aqui:** estabelece que o problema é real e atual, não acadêmico.
**Na tela:**
- Lado esquerdo, dois números grandes: LCOE 2010–2024 da FV **−90 %** e da eólica terrestre **−70 %** [1]; Brasil em 2025, FV **64,8 GW** (+33,7 %) e eólica **34,7 GW**, juntas **26,4 %** da geração [3].
- Lado direito, três ícones de sistemas pequenos com várias fontes: edificação (bateria + H₂), localidade isolada (eólica + FV + célula + bateria), embarcação (célula + bateria).

**Fala:** "As renováveis ficaram competitivas e se expandiram rapidamente. A diversificação deixou de ser uma questão só do planejamento nacional: hoje, sistemas pequenos — edificações, comunidades isoladas e até embarcações — reúnem várias fontes ao mesmo tempo."
**Ponte →** "Ter várias fontes cria uma pergunta: a cada instante, quanto usar de cada uma?"

### Slide 2 · «Cada decisão de despacho muda o que será possível depois» (1:10)
**Por que aqui:** é o coração conceitual da defesa. Planta a metáfora da água e as duas filosofias de operação, que voltam no Bloco III.
**Na tela:**
- **Esquerda, SIN:** reservatório → NEWAVE (médio/longo prazo) → DECOMP (curto) → DESSEM (diário), com setas "custo futuro da água" descendo de um modelo para o outro.
- **Direita, microrrede:** bateria (energia armazenada), PEMFC (ligada ou desligada, combustível), rede (tarifa variável).
- **Faixa inferior:** "Conectada → reduzir o custo de aquisição" | "Isolada → garantir o atendimento com os recursos locais".

**Fala:** "No Sistema Interligado Nacional, a água turbinada hoje pode obrigar a acionar uma térmica mais cara amanhã. Por isso a cadeia do CEPEL atribui um custo futuro à água armazenada, e os modelos de horizonte maior orientam os de horizonte menor. Numa microrrede acontece o mesmo em escala menor: a energia retirada da bateria agora deixa de estar disponível na ponta; ligar uma célula a combustível impõe tempo mínimo de operação. E a filosofia muda com o sistema: conectado à rede, buscamos custo; isolado, garantir a demanda."
**Ponte →** "Existem ferramentas para isso? Existem, mas separadas."

### Slide 3 · «As peças existem, mas não foram avaliadas em conjunto» (0:55)
**Por que aqui:** situa o trabalho e mostra a lacuna em vez de apenas afirmá-la.
**Na tela:** duas colunas.
- **EMS MILP–MPC** (Parisio [17]; Fan [20]; Vivas [21]; Kopka [6]; Aaslid [22]): decisões discretas e coordenação de horizontes, mas **sobre uma microrrede de composição fixa**. Valor terminal ausente [17], limite mínimo fixo [20], estado imposto por igualdade [21], custo predefinido [6] ou exigência de convexidade [22].
- **Ambientes e simuladores** (HOMER [31]; pymgrid [27]; PyPSA, oemof, Calliope, ETHOS.FINE): mudam a composição, mas com **estratégias predefinidas, modelos simplificados ou foco em planejamento**.
- **Faixa da lacuna**, com a frase do artigo: *"não se identificou uma abordagem que reunisse a composição de diferentes microrredes a partir de modelos dos equipamentos e sua avaliação operacional sob um mesmo gerenciamento hierárquico, preservando a rastreabilidade entre configurações, cenários e resultados."*

**Fala:** "De um lado, há EMS sofisticados, mas cada um é avaliado numa microrrede de composição fixa, e a energia que sobra no fim do horizonte é tratada com um limite fixo, por igualdade ou com um custo predefinido. Do outro, há ambientes que trocam a composição, mas com estratégias predefinidas ou modelos simplificados. A lacuna não é uma peça isolada; é reunir essas capacidades e avaliá-las em conjunto."
**Cuidado:** não dizer "ninguém fez". Dizer "entre os trabalhos analisados".
**Ponte →** "Daí vem a pergunta deste trabalho."

### Slide 4 · «Pergunta, objetivo e duas contribuições» (0:45)
**Por que aqui:** é o contrato com a banca. Tudo o que vem depois serve para cumpri-lo.
**Na tela:**
- **Pergunta** (em destaque): a do item 0.
- **Objetivo geral** (texto do artigo): "apresentar o desenvolvimento do SEEDS e avaliar, por meio de estudos computacionais, sua capacidade de representar diferentes configurações de microrredes e coordenar o despacho energético sob restrições operacionais."
- **Objetivos específicos** (derivados do artigo; **conferir a redação com o orientador**):
  1. integrar modelos físicos dos equipamentos numa representação energética comum;
  2. integrar um EMS hierárquico MILP–MPC com sinal de valor futuro;
  3. avaliar o SEEDS numa microrrede industrial conectada (C1–C4) e numa embarcação isolada (C5–C6);
  4. verificar a expansibilidade e o desempenho computacional.
- **Dois pilares:** **A** Plataforma modular · **B** EMS hierárquico. Os ícones passam a ser usados como marcadores daqui em diante.

**Fala:** "A pergunta tem duas metades, e cada uma virou uma contribuição. A primeira é a plataforma, onde diferentes microrredes são compostas a partir de modelos de equipamentos. A segunda, de igual importância, é o EMS hierárquico, em que um planejador de horizonte longo informa ao controle de curto prazo quanto vale a energia armazenada."
**Ponte →** "Para responder, preciso de três coisas: saber o que cada equipamento faz, saber como decidir e juntar as duas numa plataforma. É a ordem do próximo bloco."

---

## BLOCO II — Fundamentos e desenvolvimento do SEEDS (8:00)

> **Função do bloco:** construir, do físico ao matemático e do matemático ao software, tudo o que a banca precisa para entender a demonstração e os resultados. Ao final, a banca deve saber o que é o "sinal de valor futuro" e por que cada solução é verificada.

### Parte A — Modelos físicos (1:30)

### Slide 5 · «Cada equipamento entrega ao EMS só o que a otimização precisa» (1:30)
**Por que aqui:** mostra o domínio físico e já prepara a ideia de modularidade, porque o modelo é separado da decisão.
**Na tela:** cinco blocos com entrada → modelo → **saída para o EMS**:

| Recurso | Modelo | Entrega ao EMS |
|---|---|---|
| FV | Temperatura NOCT (Ross) + potência com correção térmica (eq. 1–2) | potência disponível por intervalo |
| Eólica | Curva do fabricante + correção por densidade (eq. 3) | potência disponível |
| Bateria | Balanço energético (EPRI), SOC (eq. 4–5) | energia, limites e eficiências |
| PEMFC | Eletroquímico semiempírico (Altıntaş e Ertan), Faraday (eq. 6–7) | curva consumo de H₂ × potência |
| Rede (PCC) | Importação e exportação com tarifas (eq. 8) | sentidos, limites e custo |

**Fala:** "Cada tecnologia tem seu modelo físico. Nenhum deles entra inteiro no otimizador: cada um entrega ao EMS apenas o que a decisão precisa. A FV e a eólica entregam a potência disponível; a bateria, sua energia e seus limites; a célula a combustível, a curva de consumo de hidrogênio. O modelo da PEMFC foi implementado e parametrizado num trabalho anterior nosso [36]."
**Ponte →** "Com isso definido, a pergunta passa a ser: como decidir?"

### Parte B — Fundamentos do gerenciamento (3:00)

### Slide 6 · «MILP: potências contínuas e decisões liga/desliga no mesmo problema» (1:00)
**Por que aqui:** justifica a escolha do MILP. As decisões reais são discretas.
**Na tela:**
- Diagrama do barramento equivalente com a convenção de sinais.
- **Eq. 11 (balanço):** P_ren + P_d − P_c + P_g + P_imp = P_L + P_exp.
- **Eq. 13 (unidade despachável):** P_min·u ≤ P_g ≤ P_max·u; u_t − u_{t−1} = y_t − z_t.
- Rótulos: "contínuas: potências, energia" | "binárias: ligar e desligar, carregar ou descarregar, importar ou exportar".

**Fala:** "As decisões reais têm duas naturezas: quanto (potências, energia) e sim ou não (ligar uma unidade, carregar ou descarregar, importar ou exportar). A programação linear inteira mista representa as duas no mesmo modelo. O balanço do barramento garante o atendimento, e as binárias representam, por exemplo, a potência mínima de uma PEMFC ligada e suas partidas e paradas."
**Ponte →** "Mas o futuro só é conhecido por previsões, e elas mudam. Por isso o MILP é resolvido repetidamente."

### Slide 7 · «MPC: planejar N intervalos, aplicar m, recomeçar» (1:00)
**Por que aqui:** introduz o controle de curto prazo e o seu defeito, a miopia, que motiva a hierarquia.
**Na tela:**
- Animação da janela deslizante: N intervalos planejados, m aplicados, o estado atualizado volta.
- **Eq. 15** simplificada: min Σ ℓ + V_f(x_{k+N}).
- Alerta em destaque: **"sem custo terminal, a otimização tende a esvaziar a bateria no fim da janela"**.

**Fala:** "O controle preditivo resolve o problema numa janela, aplica só a parte inicial, atualiza o estado e repete. Isso incorpora a realimentação. Mas o horizonte é finito: se nada atribui valor à energia que sobra no fim da janela, a otimização a gasta, porque para ela essa energia não vale nada. O controlador fica míope."
**Ponte →** "É aqui que volta a água do SIN."

### Slide 8 · «O valor futuro corrige a miopia do horizonte» (1:00) — ícone B
**Por que aqui:** é o fundamento teórico da contribuição B.
**Na tela:**
- **Eq. 17:** J*_k = min { Σ ℓ + V_{k+N}(x_{k+N}) }.
- **Eq. 18:** μ = −∂V/∂E [R$/kWh].
- Gráfico V(E) **linear por partes** (ilustrativo), com a inclinação rotulada "valor marginal do kWh guardado".
- Nota: "com binárias, V pode ser não convexa ou descontínua → a derivada pode não existir".

**Fala:** "Se o termo terminal for o custo de continuação, o custo ótimo de seguir operando a partir daquele estado, a janela curta enxerga o resto do horizonte. É o mesmo princípio do custo futuro da água. A inclinação dessa função é o valor de um kWh guardado. Só que, com decisões inteiras, essa função pode ser não convexa e sua derivada pode nem existir. Por isso não usamos os duais do MILP como preço, e sim uma aproximação construída de outra forma, que mostro adiante."
**Ponte →** "Esses são os fundamentos. Agora, como eles viraram uma plataforma."

### Parte C — Desenvolvimento do SEEDS (3:30)

### Slide 9 · «O SEEDS separa o sistema físico da estratégia de gerenciamento» (1:00) — ícone A
**Por que aqui:** é a tese da contribuição A.
**Na tela:** a Figura 5.1 simplificada, em três camadas:
1. **Modularidade:** modelos e catálogos → configuração da microrrede (revisões) → cenário operativo.
2. **Integração:** representação energética comum → verificação de compatibilidade.
3. **EMS hierárquico:** planejador → MPC → simulação em malha fechada → resultados e evidência.

Rodapé: **"Acrescentar um recurso altera a instância do problema, não a formulação."**

**Fala:** "Uma estratégia formulada para uma composição fixa precisa ser reescrita sempre que um equipamento muda. O SEEDS foi concebido para evitar isso. Os modelos e catálogos descrevem os equipamentos; a configuração diz quais estão nesta microrrede; o cenário define as condições do estudo. Tudo isso é traduzido numa representação comum, e só ela chega ao EMS."
**Ponte →** "O que é essa representação comum?"

### Slide 10 · «Cada recurso entra no problema com o que ele é — nada é presumido» (1:00) — ícone A
**Por que aqui:** mostra como a modularidade foi implementada e a postura metodológica (sem valores inventados).
**Na tela:**
- **Renováveis →** limite superior exógeno; média das amostras, sem interpolação; a diferença é registrada como vertimento.
- **Bateria →** balanço da eq. 4, cada banco separado (sem equivalente único).
- **PEMFC →** curva H₂ × potência linear por partes, **gerada uma vez** pelo modelo estacionário e aceita só se o erro ficar dentro do limite; o modelo dinâmico confere o despacho **depois**.
- **PCC →** sentidos, limites e tarifas declarados; **ausência ≠ ilimitado**.
- Caixa à direita: **verificação de compatibilidade** com três classes, *representável · excluído · impeditivo*. Pendência ⇒ não executa.

**Fala:** "Todos os recursos são expressos no mesmo barramento, em kW líquidos e na mesma malha temporal. Os modelos não lineares ficam fora do MILP: são avaliados antes, sobre as previsões, e entregam séries e curvas. Antes de cada execução, a plataforma verifica se tudo é representável; se faltar um dado, ela aponta a pendência em vez de seguir com um valor presumido."
**Ponte →** "Com o problema montado, entram os dois níveis do EMS."

### Slide 11 · «Dois níveis de decisão, uma mesma física» (1:00) — ícone B
**Por que aqui:** mostra a implementação da contribuição B e responde ao "como vocês aproximam V?".
**Na tela:** a Figura 5.2 simplificada, em duas colunas.
- **Planejador (H_L):** a partir do estado executado → plano longo (**nunca aplicado**) → **reotimizações paramétricas**: o trecho após a janela é resolvido várias vezes, com energia inicial fixa → **sinal de valor futuro** (linear por partes, por modo das unidades despacháveis, com domínio viável).
- **MPC (N, aplica m):** verifica o sinal (janela, causalidade, domínio, modos) → MILP = custo da janela + custo futuro → aplica m → estado executado.
- Nota: "custo futuro é registrado separadamente — nunca somado ao custo realizado".

**Fala:** "O planejador olha o horizonte longo e responde a uma pergunta: se a janela terminar com tanta energia, quanto custa o resto da operação? Para isso, ele resolve o trecho seguinte várias vezes, cada vez com uma energia inicial diferente, e refina os pontos até atingir a tolerância. O resultado é uma função linear por partes, calculada separadamente para cada modo das unidades: ligada ou desligada, com ou sem obrigação de permanência. O MPC recebe essa função como custo terminal. O plano longo nunca é aplicado; ele só informa."
**Ponte →** "E nenhuma solução é aceita só porque o solver disse que é ótima."

### Slide 12 · «Cada decisão é verificada antes de ser aplicada — e o estudo inteiro, ao fim» (0:30)
**Por que aqui:** sustenta a confiabilidade e prepara o hands-on (as 5 etapas são as que a banca vai ver no app).
**Na tela:**
- Faixa superior: MILP (Pyomo + HiGHS) → **verificação independente** (sem solver: balanço, limites, permanência, termo terminal) → aplica m → … → **auditoria integral** → registros vinculados à revisão do inventário e à versão do cenário.
- Faixa inferior: a Figura 5.3, com as etapas 0–4 (Microrrede · Inicialização · Previsões · Estratégia EMS · Execução).

**Fala:** "Cada solução é conferida por uma verificação independente do solver antes de ser aplicada, e ao fim uma auditoria integral refaz o balanço, os custos e a coerência dos sinais. Todo estudo segue estas cinco etapas, que são exatamente as que vou mostrar no aplicativo."
**Ponte →** "Com a plataforma pronta, a pergunta é: ela funciona em sistemas diferentes?"

---

## BLOCO III — Estudos de caso (2:30)

> **Função do bloco:** a banca sai sabendo O QUE varia em cada experimento e POR QUÊ, e quais são as hipóteses. Ser franco aqui desarma metade das perguntas depois.

### Slide 13 · «Dois sistemas com filosofias opostas, uma mesma formulação» (1:00)
**Por que aqui:** liga com o slide 2 (as duas filosofias) e mostra a lógica experimental.
**Na tela:** duas colunas espelhadas.

| | Microrrede industrial CT-046 | Embarcação EMB-H2-120 |
|---|---|---|
| Conexão | conectada (só importação) | isolada |
| Objetivo | custo de importação | consumo de H₂ |
| Duração · Δ | 24 h · 15 min | 120 min · 15 min |
| MPC · planejador | N = 8 (2 h), m = 1 · H_L = 96 | N = 4 (1 h), m = 1 · H_L = 8 |
| O que varia | **composição** (C1–C4) | **condição**: SOC inicial e reserva (C5–C6) |

Faixa inferior, **"O que estes estudos são"**: sistemas hipotéticos · demanda e renovável realizadas = previstas · clima sintético · simulação computacional, **sem validação experimental**.

**Fala:** "Escolhemos dois sistemas com filosofias opostas, as mesmas do início. Na microrrede industrial, a energia que falta vem da rede, e o EMS minimiza o custo de importação; variamos a composição. Na embarcação, não há fonte externa, e o EMS minimiza o hidrogênio; variamos o estado da bateria. Deixo claro desde já: são estudos computacionais, com previsão igual à realização. Avaliamos o comportamento da plataforma e do EMS sob hipóteses declaradas, não um sistema real."
**Ponte →** "Primeiro, a microrrede."

### Slide 14 · «CT-046: mesma demanda, mesma tarifa, quatro composições» (0:45)
**Por que aqui:** dá à banca os dados necessários para ler a Tabela 7.1.
**Na tela:**
- A Figura 6.1: demanda (pico de 100 kW, energia de 1.967,15 kWh) + tarifa A4 Verde da COPEL; **ponta 18–21 h: 1,93894 vs 0,44234 R$/kWh (4,4×)**.
- Os chips C1–C4 (Fig. 6.2).
- Mini-tabela: FV 58 kWp (100 × CS7L-580MS) · bateria 200 kWh / 50 kW, SOC inicial de 30 % · PCC de 200 kW · **sem condição terminal**.

**Fala:** "A demanda vem de uma curva real de carga da ANEEL, a CT-046, escolhida porque mantém consumo alto na ponta, o que cria um sinal econômico para deslocar energia. A tarifa na ponta é 4,4 vezes maior. As quatro configurações compartilham tudo e diferem apenas nos recursos disponíveis: só rede, FV, bateria e FV mais bateria."
**Ponte →** "Agora, a embarcação."

### Slide 15 · «EMB-H2-120: atender a missão gastando o mínimo de hidrogênio» (0:45)
**Por que aqui:** apresenta o caso C5/C6, que a banca vai ver ao vivo.
**Na tela:**
- Perfil de propulsão (Fig. B.2), com picos de ~60 kW, vales de ~7 kW e 68,21 kWh na missão.
- Recursos: PEMFC ≈ 50 kW (mínimo de 10 kW, **sempre ligada**) · bateria 150 kWh / 75 kW · FV 3,48 kWp.
- **C5:** SOC inicial 50 % · reserva final ≥ 45 kWh (30 %).
- **C6:** SOC inicial **12 %** · **sem** reserva final.

**Fala:** "A embarcação é hipotética: o perfil de propulsão é real, repetido para completar duas horas. A PEMFC fica ligada a missão toda; o EMS decide sua potência. No C5, a bateria começa na metade e precisa terminar com 30 % de reserva. O C6 muda só duas coisas: começa quase vazia, com 12 %, e não tem reserva final."
**Ponte →** *(transição para o app; ver Bloco IV)*

---

## BLOCO IV — Hands-on (6:00)

> **Função do bloco:** provar que a plataforma existe, funciona e reproduz o artigo. Não é um tutorial.
> **Ideia central:** reproduzir AO VIVO um número do artigo.

**Transição de entrada (fala):** "Uma vez definidos os estudos, vou mostrar como eles são configurados e executados no SEEDS. E vou reproduzir aqui um dos resultados do artigo."

| Tempo | Ação no app | O que dizer |
|---|---|---|
| 0:00–0:30 | Gestor de Microrredes: as duas microrredes no catálogo | "Cada microrrede é uma instalação independente, com inventário e histórico próprios." |
| 0:30–1:45 | Abrir a **CT-046** → Centro de Operação → cenário **C4** → percorrer rapidamente as etapas 01–04 (SOC 30 %; previsões; régua N = 8, m = 1, H_L = 96) | "São as cinco etapas que mostrei. A estratégia do EMS é declarada aqui, com procedência." |
| 1:45–2:45 | Abrir a rodada **C4 `14d8e5b3`** → Partitura, lente Operação → apontar a carga antes da ponta e a descarga a 50 kW → apontar o selo **"evidência verificada sem solver"** | "Esta é a mesma operação da Figura 7.1. A rodada foi aberta sem chamar o solver: o SEEDS refez a verificação a partir dos registros." |
| 2:45–3:30 | Trocar para a **EMB-H2-120** → abrir o cenário **C6 preparado** → mostrar as **duas** diferenças para o C5 (SOC 12 %; condição terminal: nenhuma) | "Mudo só o estado da bateria e retiro a reserva final. Nada na formulação muda." |
| 3:30–4:45 | Preflight → **EXECUTAR** → modal de execução (janelas avançando, auditoria) | Enquanto roda: "A cada janela, o planejador emite o sinal, o MILP resolve, a solução é verificada e o primeiro intervalo é aplicado." |
| 4:45–5:45 | Resultado: **H₂ = 4,163 kg** → lente Operação: a PEMFC carrega a missão e a bateria faz ciclos curtos | "4,163 kg: o mesmo valor do artigo para o C6, quase o dobro do C5." |
| 5:45–6:00 | Voltar aos slides | Transição de retorno (abaixo). |

**Transição de retorno (fala):** "A demonstração mostrou como um estudo é executado. Agora vou interpretar os resultados de todas as configurações."

**Decisões e riscos do hands-on (resolver nos ensaios):**
- **Não executar o C4 ao vivo:** a missão levou 277 s. Ele só é ABERTO, porque já está executado na instantânea de exemplo.
- **C6 "preparado":** a instantânea do C5 em `seeds2/exemplos/` **não contém** o C6. Criar antes da defesa (duplicar C5 → SOC 12 % → condição terminal "nenhuma" → salvar) e só EXECUTAR ao vivo. Editar ao vivo é possível, mas a justificativa exigida para a condição terminal consome tempo.
- **Streamlit Cloud tem disco efêmero:** se o app hibernar e reiniciar, as alterações somem e a instantânea volta ao estado guardado. Criar o C6 no mesmo dia, acordar o app 30 min antes e não deixá-lo ocioso.
- **Confirmar no ensaio** que a execução reproduz 4,163 kg (rodada de referência `cb1d2da6`) e medir o tempo real.
- **Plano B:** (1) rodada C6 já executada noutro cenário de reserva; (2) instalação local com HiGHS; (3) vídeo gravado da sequência inteira.
- **PDF:** só mostrar o botão "Relatório PDF" se sobrar tempo; não é essencial.

---

## BLOCO V — Resultados e análise (6:00)

> **Função do bloco:** transformar números em respostas. Cada slide responde a "o que isto prova?". A ordem vai do custo ao comportamento, à evidência da hierarquia, à embarcação, ao contraste e à expansibilidade.

### Slide 16 · «Na CT-046, cada recurso atacou uma parcela diferente do custo» (1:15)
**Por que aqui:** é o resultado econômico principal e mostra que a composição muda o despacho.
**Na tela:**
- Barras do custo realizado: **C1 R$ 1.274,25 · C2 R$ 1.100,97 (−13,6 %) · C3 R$ 1.038,31 (−18,5 %) · C4 R$ 865,03 (−32,1 %)**.
- Linha secundária, importação na ponta: 270,01 → 268,74 → 120,01 → **118,74 kWh (−56 %)**.
- Duas anotações: "FV: produz 6–19 h, só 1,27 kWh na ponta → reduz o fora de ponta" | "Bateria: atua na ponta".
- Nota de honestidade: "C3 e C4 incluem 40 kWh do estoque inicial (60 → 20 kWh)".

**Fala:** "Em C1, a ponta concentrou 13,7 % da energia, mas 41 % do custo. A FV reduziu o custo em 13,6 %, quase todo fora da ponta, porque ela praticamente não produz entre 18 e 21 h. A bateria fez o oposto: atuou na ponta. Juntas, reduziram o custo em 32,1 % e a importação na ponta em 56 %. Um ponto importante: essa redução inclui o uso de 40 kWh que a bateria já tinha no início; o artigo separa esse efeito."
**Se perguntarem:** a soma de C2 e C3 é igual a C4 (173,28 + 235,94 = 409,22). Não houve sinergia porque a FV nunca superou a demanda e a tarifa fora de ponta é única (auxiliar A10).
**Ponte →** "Como a bateria fez isso?"

### Slide 17 · «A bateria carregou fora da ponta e descarregou na potência máxima durante a ponta» (1:00)
**Por que aqui:** mostra que o despacho é fisicamente e economicamente coerente.
**Na tela:** a Figura 7.2 (energia nas fronteiras, C3 e C4) + três números:
- **178,04 kWh** às 18:00 ≈ 20 + 150/0,95 = 177,89 kWh (o necessário exato).
- **50 kW × 12 intervalos** → −150 kWh na ponta.
- **R$ 0,490 vs R$ 1,939** por kWh entregue na ponta (com o rendimento de ida e volta de 0,9025).

**Fala:** "O banco ficou parado até as 15 h, carregou até 178 kWh, praticamente o exato necessário para descarregar a 50 kW durante as três horas de ponta e chegar ao limite inferior às 21 h. Cada kWh entregue na ponta, carregado fora dela, custou 49 centavos, contra R$ 1,94 da rede. O benefício foi limitado pela potência de 50 kW, não pela energia."
**Ponte →** "Mas há um detalhe neste carregamento que é a principal evidência da hierarquia."

### Slide 18 · «O MPC via só 2 horas, mas começou a carregar antes de a ponta entrar no horizonte» (1:15) — ícone B
**Por que aqui:** é **A** evidência da contribuição B. É o slide mais importante do bloco.
**Na tela:**
- Linha do tempo das 14:00 às 18:30, com a faixa da ponta e janelas do MPC desenhadas como retângulos deslizantes.
- Destaque: **"a ponta só entra no horizonte a partir de 16:15"**.
- Área sombreada 15:00–16:00: **62,50 kWh = 50,3 % da carga decidida ANTES**.
- Caixa: "único termo que valorizava a energia armazenada = **sinal de valor futuro**, válido em 96 de 96 decisões".
- Caixa de coerência: **1ª decisão do C4: objetivo do MILP R$ 865,02** (R$ 54,34 da janela + R$ 810,68 do custo de continuação) **vs custo realizado R$ 865,03**.

**Fala:** "Cada janela do MPC cobre duas horas. A ponta começa às 18 h, então só as decisões tomadas a partir de 16:15 a enxergavam. Mesmo assim, metade da carga foi decidida antes disso. Nessas janelas, carregar só aumentava o custo da própria janela. O único termo que dava valor à energia guardada era o sinal do planejador. É o mesmo mecanismo da água do SIN: o custo futuro fez o controle de curto prazo enxergar além do seu horizonte. E mais: já na primeira decisão do dia, a estimativa do planejador ficou a um centavo do custo que de fato se realizou."
**Ponte →** "Agora, o mesmo EMS num sistema completamente diferente."

### Slide 19 · «Na embarcação, a mesma formulação deu à bateria outro papel: cobrir os picos» (1:00)
**Por que aqui:** é a segunda metade da evidência. A mesma formulação produz um comportamento diferente, mas igualmente coerente.
**Na tela:** a Figura 7.3 (C5) + números:
- 68,21 kWh atendidos: **PEMFC 49,6 % · bateria 41,6 % · FV 8,9 %**.
- PEMFC numa faixa estreita, **10–19,9 kW**; bateria × demanda com correlação de **0,986**.
- Por quê: consumo específico **0,0603 → 0,0768 kg/kWh** do mínimo ao máximo.
- Fim da missão: **45,00 kWh = exatamente a reserva**.
- **2,156 kg de H₂** = objetivo do MILP na 1ª decisão; o modelo dinâmico confirma 2,156 kg (subestimação máxima de 0,0002 kg).

**Fala:** "A célula ficou numa faixa estreita, perto do mínimo, e a bateria acompanhou a demanda. A razão está na física: o hidrogênio por kWh cresce com a potência, então é mais barato cobrir os picos com a bateria e deixar a célula baixa. Às 13 h, quando a demanda caiu abaixo do mínimo da célula, o EMS a manteve em 10 kW e mandou a sobra para a bateria. A missão terminou com exatamente 45 kWh, a reserva exigida, e a energia para o segundo pico foi preservada por decisões de uma janela de uma hora que nem via o fim da missão."
**Ponte →** "E se a bateria não tiver de onde tirar? É o C6, que vimos ao vivo."

### Slide 20 · «Sem energia armazenada, a célula assume a missão; o EMS se adapta sem reformulação» (0:45)
**Por que aqui:** fecha o contraste e conecta com a demonstração.
**Na tela:**
- C5 vs C6 lado a lado (Fig. 7.3 × Fig. 7.4): **2,156 kg → 4,163 kg (1,93×)**; a PEMFC passa a **88 %**; a bateria faz ciclos curtos recarregados pela própria PEMFC.
- A Figura 7.5 (C4 vs C6 normalizados): **C4 descarrega 0,75 C_b em 24 h** (deslocamento no tempo) **vs C6 0,06 C_b em 2 h** (suporte de potência).

**Fala:** "No C6, com só 3 kWh acima do limite, a célula forneceu 88 % da energia e o hidrogênio quase dobrou: o número que vocês viram no aplicativo. Às 13 h, o EMS elevou a célula para recarregar a bateria, porque o pico seguinte, de 53 kW, passava da potência máxima da célula. Comparando os dois sistemas: na microrrede, a bateria desloca energia ao longo de horas; na embarcação, dá suporte de potência em minutos. É o mesmo gerenciamento; quem define o papel é a física e a condição de operação."
**Ponte →** "Falta a outra metade da pergunta: composições diferentes."

### Slide 21 · «Nove composições, o mesmo código — todas as janelas resolvidas até a otimalidade» (0:45) — ícone A
**Por que aqui:** é a evidência direta da contribuição A (modularidade e expansibilidade) e do desempenho.
**Na tela:**
- Gráfico de barras da Tabela 7.2: variáveis **7 → 217**, binárias **1 → 105** (de "Rede" a "Bateria, duas PEMFC e rede").
- Indicadores: **14 missões · 168 janelas ótimas** · MILP de janela **≤ 0,42 s** (C1–C5) · decisão com planejador **≤ 5 s** · 1 dia industrial em **277 s**.
- Verificações: reconstrução independente com resíduos de **~10⁻¹⁵** · curva H₂ com **15 vértices, erro máx. 0,087 %** (limite 0,5 %), nunca subestimou.

**Fala:** "Executamos nove composições com o mesmo código do EMS, da rede sozinha até bateria com duas PEMFC. O MILP cresceu de 7 para 217 variáveis, mas a formulação, os critérios e a auditoria não mudaram: incluir ou retirar um recurso exigiu apenas alterar a microrrede ou o cenário. Todas as 168 janelas chegaram ao ótimo. Um dia inteiro da microrrede foi simulado em menos de 5 minutos, e a reconstrução independente fechou o balanço com resíduos de arredondamento."
**Ponte →** "Volto, então, à pergunta do início."

---

## BLOCO VI — Conclusões, limitações e perspectivas (2:00)

> **Função do bloco:** fechar o contrato do slide 4 e separar com clareza o que foi demonstrado do que não foi.

### Slide 22 · «Sim — dentro das tecnologias representadas e das hipóteses declaradas» (1:00)
**Por que aqui:** responde à pergunta, objetivo por objetivo, e fecha a metáfora.
**Na tela:** a pergunta no topo e, abaixo, a tabela objetivo → evidência:

| Objetivo | Evidência |
|---|---|
| 1. Representação comum (A) | 9 composições sem reformulação; recursos alteram só a instância |
| 2. EMS hierárquico com valor futuro (B) | carga iniciada antes de a ponta entrar no horizonte; reserva de 45 kWh cumprida; plano × realizado a R$ 0,01 |
| 3. Dois sistemas distintos | −32,1 % de custo e −56 % na ponta; 68,21 kWh com 2,156 kg de H₂; papéis distintos do armazenamento |
| 4. Verificação e desempenho | 168 janelas ótimas; auditoria independente; resíduos de ~10⁻¹⁵; ≤ 5 s por decisão |

Frase de fecho: *"Assim como no SIN a água guardada tem custo futuro, no SEEDS a energia armazenada e o estado das unidades também têm, e é isso que orienta a decisão de curto prazo."*

**Fala:** "A resposta é sim, dentro do conjunto de tecnologias representadas e das hipóteses declaradas. O SEEDS separou a descrição física da estratégia de despacho, e essa separação se sustentou em nove composições. O planejador transmitiu ao controle de curto prazo um custo de continuação com significado econômico verificável, e as decisões foram coerentes com ele nos dois sistemas."

### Slide 23 · «O que este trabalho não demonstra — e os próximos passos» (0:45)
**Por que aqui:** antecipa as críticas com transparência; a banca valoriza isso.
**Na tela:** duas colunas.
- **Limites:** sistemas hipotéticos · realização = previsão (sem incerteza) · clima sintético · PEMFC com parametrização aproximada, sem calibração · barramento único, sem fluxo de potência · custo ≠ fatura · autodescarga desprezada · ON/OFF bloqueado no C5 · dois bancos: convexidade verificada só nos pontos amostrados.
- **Próximos passos** (do artigo): geração térmica no EMS · automatizar a malha e os parâmetros do planejador · melhorar o custo futuro para múltiplos bancos · diferenças entre previsão e realização · comparação com dados experimentais.

**Fala:** "Os resultados descrevem o comportamento da plataforma e do EMS sob hipóteses declaradas; não são validação experimental. O passo natural é introduzir diferenças entre previsão e realização, que é onde o MPC mostra todo o seu valor, e comparar com dados reais."

### Slide 24 · Encerramento (0:15)
**Na tela:** "Obrigado" · QR para o repositório [42] · agradecimento ao CNPq (projeto n.º 460014/2025-0) · contato.
**Fala:** "Agradeço ao CNPq, aos meus orientadores e à banca. Fico à disposição."

---

## SLIDES AUXILIARES (só na arguição)

| # | Título | Conteúdo | Pergunta que responde |
|---|---|---|---|
| A1 | Solver e configuração | Python; Streamlit 1.66.1; **Pyomo 6.10.1**, interface `pyomo.contrib.solver` "highs"; **highspy 1.15.1** (BSD/MIT); gap relativo e absoluto = 0; 1 thread; semente 0; limite de 60 s; `load_solutions=False` → classificação da terminação → auditor → aceitação | "Que solver? Com que parâmetros?" |
| A2 | Do inventário ao MILP: o caminho dos dados | `seeds2` (inventário + cenário) → `integracao_v2/montagem.py` (ponte, contrato da rede, configs do MPC e do planejador) → modelos físicos avaliados ANTES (FV NOCT, eólica, curva H₂) → `ems_v2` (MILP por janela) → planta algébrica → registros selados → auditoria integral | "Como o solver é alimentado?" |
| A3 | Formulação completa da janela | núcleo físico + commitment (rampas, permanências M09–M12) + exclusividade no PCC + termo terminal PWL com binárias explícitas, **sem SOS**, exato mesmo não convexo; 2D só por envoltória com convexidade verificada | "Como o custo futuro entra no MILP?" |
| A4 | Reotimização paramétrica | cada ponto = MILP completo auditado; refinamento por bissecção do erro no ponto médio; domínio viável por bissecção; uma função por modo terminal; **por que não duais** (não convexidade, inteiros) | "Por que não usar os duais?" |
| A5 | Curva H₂ da PEMFC | 15 vértices de 10 a 50 kW; 500 pontos fora da construção; erro máx. 0,087 % < 0,5 %; nunca subestima; gerada uma vez; dinâmica conferida a posteriori | "O MILP representa bem a célula?" |
| A6 | Parâmetros CT-046 | Tabelas 6.1 e 6.2 | dados |
| A7 | Parâmetros da embarcação | Tabela 6.3; condições da PEMFC (Tabela B.3) | dados |
| A8 | Literatura detalhada | tabela trabalho × (composição variável, decisões discretas, valor futuro, rastreabilidade), **só com o que o artigo afirma** | "Qual exatamente é a novidade?" |
| A9 | C3 e o estoque inicial | R$ 290,84 evitados na ponta − R$ 54,90 a mais fora; 38 kWh vindos do estoque; ciclo do dia ≈ **R$ 217,31** | "A economia não é só a bateria se esvaziando?" |
| A10 | Por que C4 = C2 + C3 | FV < demanda sempre; tarifa fora de ponta única; sem excedente para armazenar | "Não houve sinergia?" |
| A11 | Da V1.6 à V2 | EMS anterior: SLSQP + metaheurísticas (GA/GWO/NGO), sem garantia de ótimo nem decisões discretas exatas → MILP–MPC com auditoria | "Por que MILP e não metaheurísticas?" |
| A12 | Sinal do planejador (bancada) | inclinação de 1,416 R$/kWh até 10,53 kWh e de 0,466 acima (tarifas 1,50/0,50) = valor de 1 kWh entregue | "O sinal tem significado econômico?" |
| A13 | Mecanismo × formulação ideal (eq. 17) | previsão determinística única; interpolação nos pontos (não é cota); horizonte do planejador finito, com condição terminal declarada | "Isso é programação dinâmica exata?" |
| A14 | Rastreabilidade | IDs das rodadas (C1 `4f7da832`, C2 `dbccd121`, C3 `7252f033`, C4 `14d8e5b3`, C6 `cb1d2da6`); pacote `.seeds2study.zip`; reabertura verifica sem solver | "Como reproduzo?" |
| A15 | "Se a previsão é perfeita, por que MPC?" | horizonte finito exige coordenação mesmo sem incerteza; o estudo isola o efeito da hierarquia; a estrutura (registro causal, estado executado) já está pronta para previsão ≠ realização | (pergunta mais provável) |

## Perguntas prováveis — respostas curtas

1. **"Se a previsão é perfeita, para que MPC?"** → A15. Isolamos o efeito do horizonte finito e da coordenação; a incerteza é o próximo passo, e a arquitetura já separa previsão de realização.
2. **"Os 32,1 % não incluem o estoque inicial?"** → Sim, e o artigo diz isso. A estimativa do ciclo do dia em C3 é R$ 217,31 (A9).
3. **"Por que não houve sinergia em C4?"** → A10.
4. **"Por que reotimização e não duais?"** → Com inteiros, V pode ser não convexa e sem derivada; os duais do MILP não são preços (A4).
5. **"A PEMFC é validada?"** → Não. A parametrização é aproximada (Horizon); a curva PWL é certificada matematicamente contra o modelo (A5), não contra o equipamento.
6. **"Por que SEEDS e não SEEDS2?"** → O SEEDS2 é a versão 2 da plataforma SEEDS; o repositório guarda a história desde a V1.5.
7. **"Por que Δ = 15 min?"** → É a resolução da curva da ANEEL. Na embarcação, as variações mais rápidas ficam fora do alcance da otimização, o que o artigo declara.
8. **"Por que 58 kWp?"** → Próximo, mas abaixo, da demanda mínima (58,24 kW), para favorecer o autoconsumo; a não exportação é uma restrição do PCC.
9. **"Escala para sistemas maiores?"** → De 7 a 217 variáveis, com ≤ 5 s por decisão; o custo cresce com as binárias; múltiplos bancos são uma limitação declarada.

## Próximos passos de preparação

1. Validar com o orientador a redação dos objetivos específicos (slide 4).
2. Desenhar os slides 18 e 21, que **não existem como figura no artigo** e precisam ser criados.
3. Ensaio cronometrado só do Bloco IV (3×), incluindo a criação do C6 no Streamlit Cloud.
4. Gravar o vídeo de contingência do hands-on.
5. Ensaio completo cronometrado e ajuste fino do tempo.
