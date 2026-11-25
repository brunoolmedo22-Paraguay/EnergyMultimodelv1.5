# Roteiro da defesa — mapa de slides (versão vigente)

Defesa de TCC · 30 min (22 min de slides + 6 min de demonstração + 2 min de margem).
Fio condutor: **"Um mesmo gerenciamento energético consegue operar microrredes de composições diferentes, considerando o valor futuro da energia armazenada?"** (pergunta do slide 6, respondida no slide 25). Metáfora: custo futuro da água no SIN (slides 4, 10, 21, 25).
Contribuições: **A** plataforma modular · **B** EMS hierárquico MILP–MPC.
Detalhamento anterior (falas e justificativas, numeração antiga): `ROTEIRO_DETALHADO_v1.md`.

| Nº | Título | Conteúdo essencial | Vínculo |
|---|---|---|---|
| 1 | Capa | aprovada (`capa/`) | — |
| 2 | Sumário | 7 seções; pergunta central | barra de progresso |
| **I** | **Contexto e objetivos (3:30)** | | |
| 3 | Contexto ✔ aprovado | LCOE −90 % / −70 % [1]; eólica + solar 2011–2025, 0,5 % → 26,4 % [3]; cargas pequenas com várias fontes [3–6]; «Várias fontes … exigem coordenação» | → 4 |
| 4 | Decisões com consequências futuras ✔ aprovado (S4v6_H1) | «Conceito de valor da água» (custo imediato × futuro, adaptado ONS 2020 Fig. 3.15; eixo = usar agora ← → guardar depois) + NEWAVE→DECOMP→DESSEM; «Na microrrede, o mesmo dilema»: energia → falta na ponta (tarifa), célula → tempo mínimo; conectada × isolada | → 10, 15, 21, 25 |
| 5 | Trabalhos relacionados ✔ aprovado (S5v4_E1) | três cartões: EMS MILP–MPC em tabela (glifo · referência · como trata a energia no fim da janela: Parisio [17] sem valor final, Fan [20] limite mínimo fixo, Vivas [21] estado final imposto, Kopka [6] custo predefinido, Aaslid [22] exige convexidade) · SEEDS no centro (gerenciamento + composição «integrados em uma mesma plataforma») · ambientes e simuladores (estratégias predefinidas: HOMER [31], pymgrid [27]; foco no planejamento: PyPSA, oemof, Calliope, ETHOS.FINE); «A lacuna» em três partes com o texto do artigo | ← 4 · → 6 · aux. literatura |
| 6 | Objetivos e contribuições | pergunta, objetivo geral, específicos, pilares A e B | → 25 |
| **II** | **Fundamentação e SEEDS (8:00)** | | |
| 7 | Modelagem dos recursos energéticos | FV, eólica, bateria, PEMFC, PCC → o que entregam ao EMS | → 12 |
| 8 | Programação linear inteira mista (MILP) | eq. 11 e 13; contínuas × binárias | → 9 |
| 9 | Controle preditivo baseado em modelo (MPC) | janela N/m; eq. 15; miopia sem valor terminal | → 10 |
| 10 | Coordenação hierárquica e valor futuro (B) | eq. 17–18; V(E) PWL; por que não duais | → 13 |
| 11 | Arquitetura do SEEDS (A) | Fig. 5.1 simplificada | → 24 |
| 12 | Representação energética comum (A) | o que cada recurso entrega ao MILP; verificação de compatibilidade | ← 7 |
| 13 | Gerenciamento energético hierárquico no SEEDS (B) | Fig. 5.2: planejador → sinal de valor futuro → MPC | → 21 |
| 14 | Verificação e fluxo de execução | Pyomo + HiGHS → verificação independente → auditoria; 5 etapas | → 18 |
| **III** | **Estudos de caso (2:30)** | | |
| 15 | Estudos de caso | CT-046 × EMB-H2-120; o que varia; condições declaradas | ← 4 |
| 16 | Microrrede industrial CT-046 (C1–C4) | demanda ANEEL, tarifa A4 Verde (ponta 4,4×), recursos | → 19 |
| 17 | Embarcação híbrida EMB-H2-120 (C5–C6) | perfil R2, recursos; C5 × C6 | → 18 |
| **IV** | **Demonstração (6:00)** | | |
| 18 | Demonstração do SEEDS | objetivo: reproduzir o C6 ao vivo (4,163 kg) | → aplicativo |
| — | (aplicativo) | abrir C4 sem solver → C6 preparado → EXECUTAR → 4,163 kg | → 20, 23 |
| **V** | **Resultados (6:00)** | | |
| 19 | Resultados — custos operacionais (C1–C4) | R$ 1.274 → 865 (−32,1 %); ponta −56 % | ← 16 |
| 20 | Resultados — operação do armazenamento | 178,04 kWh; 50 kW na ponta; R$ 0,49 × 1,94 | → 21 |
| 21 | Resultados — coordenação hierárquica (B) | ponta entra no horizonte às 16:15; 50,3 % da carga antes; R$ 865,02 × 865,03 | ← 10, 13 |
| 22 | Resultados — embarcação híbrida (C5) | PEMFC 10–19,9 kW; bateria segue a demanda; 45,00 kWh; 2,156 kg | ← 17 |
| 23 | Resultados — papel do armazenamento (C4, C5 e C6) | 2,156 → 4,163 kg; deslocamento × suporte de potência | ← 18 |
| 24 | Expansibilidade e desempenho computacional (A) | 7 → 217 variáveis; 168 janelas ótimas; ≤ 5 s | ← 11, 12 |
| **VI** | **Encerramento (2:00)** | | |
| 25 | Conclusões | resposta à pergunta, objetivo × evidência; fecho com o SIN | ← 6 |
| 26 | Perspectivas | tom construtivo: a plataforma está pronta para avançar em… | ← 15 |
| 27 | Agradecimentos | CNPq 460014/2025-0, orientadores, banca, QR do repositório | — |

Slides auxiliares (arguição): ver `ROTEIRO_DETALHADO_v1.md` (A1–A15), a reorganizar.
