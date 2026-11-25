# Roteiro da defesa — mapa de slides (versão vigente)

Defesa de TCC · 30 min (22 min de slides + 6 min de demonstração + 2 min de margem).
Fio condutor: **"Um mesmo gerenciamento energético consegue operar microrredes de composições diferentes, considerando o valor futuro da energia armazenada?"** (pergunta do slide 6, respondida no slide 26). Metáfora: custo futuro da água no SIN (slides 4, 11, 22, 26).
Contribuições: **A** plataforma modular · **B** EMS hierárquico MILP–MPC.
Detalhamento anterior (falas e justificativas, numeração antiga): `ROTEIRO_DETALHADO_v1.md`.

| Nº | Título | Conteúdo essencial | Vínculo |
|---|---|---|---|
| 1 | Capa | aprovada (`capa/`) | — |
| 2 | Sumário | 7 seções; pergunta central | barra de progresso |
| **I** | **Contexto e objetivos (4:20)** | | |
| 3 | Contexto ✔ aprovado | LCOE −90 % / −70 % [1]; eólica + solar 2011–2025, 0,5 % → 26,4 % [3]; cargas pequenas com várias fontes [3–6]; «Várias fontes … exigem coordenação» | → 4 |
| 4 | Decisões com consequências futuras ✔ aprovado (S4v6_H1) | «Conceito de valor da água» (custo imediato × futuro, adaptado ONS 2020 Fig. 3.15; eixo = usar agora ← → guardar depois) + NEWAVE→DECOMP→DESSEM; «Na microrrede, o mesmo dilema»: energia → falta na ponta (tarifa), célula → tempo mínimo; conectada × isolada | → 11, 16, 22, 26 |
| 5 | Trabalhos relacionados ✔ aprovado (S5v4_E1) | três cartões: EMS MILP–MPC em tabela (glifo · referência · como trata a energia no fim da janela: Parisio [17] sem valor final, Fan [20] limite mínimo fixo, Vivas [21] estado final imposto, Kopka [6] custo predefinido, Aaslid [22] exige convexidade) · SEEDS no centro (gerenciamento + composição «integrados em uma mesma plataforma») · ambientes e simuladores (estratégias predefinidas: HOMER [31], pymgrid [27]; foco no planejamento: PyPSA, oemof, Calliope, ETHOS.FINE); «A lacuna» em três partes com o texto do artigo | ← 4 · → 6 · aux. literatura |
| 6 | Objetivos ✔ aprovado (S6v3_final; título sem «e contribuições») | objetivo geral em largura total (Gelasio negrito, texto do artigo) sobre filete do gradiente; embaixo, à esquerda, a pergunta num cartão navy (trechos-chave em lima) e, à direita, os 4 objetivos específicos com caixa vazia (a marcar no slide 26); sem ícones nem rótulos A/B | ← 5 · → 26 |
| 7 | O SEEDS ✔ aprovado (S7v3_K3_ficha) | cartão navy (logo, «Uma bancada experimental, no navegador, para compor sistemas elétricos e testar o seu gerenciamento energético», barramento vertical com Solar/Eólica/H₂ → barramento ← Bateria/Rede) + ficha: O que resolve · Como · O que oferece · Para quem; apresenta as contribuições (plataforma modular, EMS hierárquico MILP–MPC) | ← 5, 6 · → 12, 25, 26 |
| **II** | **Fundamentação e SEEDS (8:00)** | | |
| 8 | Modelagem dos recursos energéticos ✔ aprovado em dois slides (S8v2_a + S8v2_b: geração 3 + armazenamento/rede 2) | FV, eólica, bateria, PEMFC, PCC → o que entregam ao EMS | → 13 |
| 9 | Programação linear inteira mista (MILP) | eq. 11 e 13; contínuas × binárias | → 10 |
| 10 | Controle preditivo baseado em modelo (MPC) | janela N/m; eq. 15; miopia sem valor terminal | → 11 |
| 11 | Coordenação hierárquica e valor futuro (B) | eq. 17–18; V(E) PWL; por que não duais | → 14 |
| 12 | Arquitetura do SEEDS (A) | Fig. 5.1 simplificada | → 25 |
| 13 | Representação energética comum (A) | o que cada recurso entrega ao MILP; verificação de compatibilidade | ← 8 |
| 14 | Gerenciamento energético hierárquico no SEEDS (B) | Fig. 5.2: planejador → sinal de valor futuro → MPC | → 22 |
| 15 | Verificação e fluxo de execução | Pyomo + HiGHS → verificação independente → auditoria; 5 etapas | → 19 |
| **III** | **Estudos de caso (2:30)** | | |
| 16 | Estudos de caso | CT-046 × EMB-H2-120; o que varia; condições declaradas | ← 4 |
| 17 | Microrrede industrial CT-046 (C1–C4) | demanda ANEEL, tarifa A4 Verde (ponta 4,4×), recursos | → 20 |
| 18 | Embarcação híbrida EMB-H2-120 (C5–C6) | perfil R2, recursos; C5 × C6 | → 19 |
| **IV** | **Demonstração (6:00)** | | |
| 19 | Demonstração do SEEDS | objetivo: reproduzir o C6 ao vivo (4,163 kg) | → aplicativo |
| — | (aplicativo) | abrir C4 sem solver → C6 preparado → EXECUTAR → 4,163 kg | → 20, 23 |
| **V** | **Resultados (6:00)** | | |
| 20 | Resultados — custos operacionais (C1–C4) | R$ 1.274 → 865 (−32,1 %); ponta −56 % | ← 17 |
| 21 | Resultados — operação do armazenamento | 178,04 kWh; 50 kW na ponta; R$ 0,49 × 1,94 | → 22 |
| 22 | Resultados — coordenação hierárquica (B) | ponta entra no horizonte às 16:15; 50,3 % da carga antes; R$ 865,02 × 865,03 | ← 11, 14 |
| 23 | Resultados — embarcação híbrida (C5) | PEMFC 10–19,9 kW; bateria segue a demanda; 45,00 kWh; 2,156 kg | ← 18 |
| 24 | Resultados — papel do armazenamento (C4, C5 e C6) | 2,156 → 4,163 kg; deslocamento × suporte de potência | ← 19 |
| 25 | Expansibilidade e desempenho computacional (A) | 7 → 217 variáveis; 168 janelas ótimas; ≤ 5 s | ← 12, 13 |
| **VI** | **Encerramento (2:00)** | | |
| 26 | Conclusões | resposta à pergunta, objetivo × evidência; fecho com o SIN | ← 6 |
| 27 | Perspectivas | tom construtivo: a plataforma está pronta para avançar em… | ← 16 |
| 28 | Agradecimentos | CNPq 460014/2025-0, orientadores, banca, QR do repositório | — |

Slides auxiliares (arguição): ver `ROTEIRO_DETALHADO_v1.md` (A1–A15), a reorganizar.

## Ordem do deck (37 slides; fonte: `pptx/deck.py`)

A tabela acima é o roteiro por conteúdo (numeração antiga). A numeração **vigente** do deck, com os separadores de seção, é esta:

| Nº | Slide | Seção | Estado |
|---|---|---|---|
| 1 | Capa | — | ✔ aprovado |
| 2 | Sumário | — | ✔ aprovado |
| 3 | Contexto e objetivos | 01 | ✔ aprovado |
| 4 | Contexto | 01 | ✔ aprovado |
| 5 | Decisões com consequências futuras | 01 | ✔ aprovado |
| 6 | Trabalhos relacionados | 01 | ✔ aprovado |
| 7 | Objetivos | 01 | ✔ aprovado |
| 8 | O SEEDS | 01 | ✔ aprovado |
| 9 | Fundamentação teórica | 02 | ✔ aprovado |
| 10 | Modelagem dos recursos energéticos | 02 | ✔ aprovado |
| 11 | Modelagem dos recursos energéticos (2/2) | 02 | ✔ aprovado |
| 12 | Programação linear inteira mista (MILP) | 02 | ✔ aprovado |
| 13 | O MILP da microrrede | 02 | ✔ aprovado |
| 14 | Controle preditivo baseado em modelo (MPC) | 02 | ✔ aprovado |
| 15 | Coordenação hierárquica e valor futuro | 02 | ✔ aprovado |
| 16 | Desenvolvimento do SEEDS | 03 | ✔ aprovado |
| 17 | Arquitetura do SEEDS | 03 | a desenhar |
| 18 | Representação energética comum | 03 | a desenhar |
| 19 | Gerenciamento energético hierárquico no SEEDS | 03 | a desenhar |
| 20 | Verificação e fluxo de execução | 03 | a desenhar |
| 21 | Estudos de caso | 04 | ✔ aprovado |
| 22 | Estratégia de avaliação | 04 | a desenhar |
| 23 | Microrrede industrial CT-046 (C1–C4) | 04 | a desenhar |
| 24 | Embarcação híbrida EMB-H2-120 (C5–C6) | 04 | a desenhar |
| 25 | Demonstração do SEEDS | 05 | ✔ aprovado |
| 26 | Demonstração do SEEDS — roteiro | 05 | a desenhar |
| 27 | Resultados | 06 | ✔ aprovado |
| 28 | Resultados — custos operacionais (C1–C4) | 06 | a desenhar |
| 29 | Resultados — operação do armazenamento | 06 | a desenhar |
| 30 | Resultados — coordenação hierárquica | 06 | a desenhar |
| 31 | Resultados — embarcação híbrida (C5) | 06 | a desenhar |
| 32 | Resultados — papel do armazenamento (C4, C5 e C6) | 06 | a desenhar |
| 33 | Expansibilidade e desempenho computacional | 06 | a desenhar |
| 34 | Conclusões e perspectivas | 07 | ✔ aprovado |
| 35 | Conclusões | 07 | a desenhar |
| 36 | Perspectivas | 07 | a desenhar |
| 37 | Agradecimentos | 07 | a desenhar |
