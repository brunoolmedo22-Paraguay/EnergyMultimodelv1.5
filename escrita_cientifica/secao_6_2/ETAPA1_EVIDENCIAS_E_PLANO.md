# Seção 6.2 — Etapa 1: evidências, interpretações e plano editorial

**Manuscrito:** SEEDS2 (Google Docs mestre, não editado nesta etapa). **Data:** 16/11/2026.
**Fontes:** os dez arquivos fornecidos pelo autor (relatórios PDF e ZIP de figuras das rodadas C1 `4f7da832`,
C2 `dbccd121`, C3 `7252f033`, C4 `14d8e5b3`, C5 `055096cf`) e a Partitura de C4 exportada em PNG
(`seeds2_14d8e5b3_Partitura_da_operacao_lente_Operacao_claro.png`). Seções 5 e 6.1 do manuscrito e identidade
autoral (`escrita_cientifica/identidade_autoral/`, branch `docs/escrita-cientifica-15nov`) lidas integralmente.
Nenhuma instantânea, banco, simulação ou execução anterior foi consultada.

**Rótulos de evidência.** **[R]** registrado no PDF (página indicada). **[D]** calculado a partir dos registros
(séries dos SVG do ZIP ou tabelas do PDF; ver `evidencias/LEIA-ME.md`). **[I]** interpretação física ou econômica.
Horários em hora local (America/Sao_Paulo); as figuras do ZIP usam UTC (= local + 3 h).

---

## A. Matriz de resultados

### A.1 CT-046 — indicadores selados (C1–C4)

| Indicador | C1 · rede | C2 · FV + rede | C3 · bateria + rede | C4 · FV + bateria + rede | Fonte |
|---|---:|---:|---:|---:|---|
| Energia demandada = atendida [kWh] | 1.967,2 | 1.967,2 | 1.967,2 | 1.967,2 | [R] C1 p.6 · C2 p.10 · C3 p.7 · C4 p.11 |
| Déficit [kWh] · intervalos com déficit | 0,00 · 0/96 | 0,00 · 0/96 | 0,00 · 0/96 | 0,00 · 0/96 | [R] p.3 de cada PDF |
| FV aproveitada · vertida [kWh] | — | 387,4 · 0,0 | — | 387,4 · 0,0 | [R] C2 p.13 · C4 p.14 |
| Importação [kWh] · exportação | 1.967,2 · 0,0 | 1.579,7 · 0,0 | 1.941,3 · 0,0 | 1.553,8 · 0,0 | [R] C1 p.5 · C2 p.9 · C3 p.6 · C4 p.10 |
| Bateria carregada · descarregada [kWh] | — | — | 124,3 · 150,1 | 124,3 · 150,1 | [R] C3 p.4 · C4 p.8 |
| Energia armazenada inicial → final [kWh] (SOC) | — | — | 60,0 → 20,0 (30 → 10 %) | 60,0 → 20,0 (30 → 10 %) | [R] C3 p.4 · C4 p.8 |
| Custo realizado [R$] | 1.274,25 | 1.100,97 | 1.038,31 | 865,03 | [R] C1 p.5 · C2 p.9 · C3 p.6 · C4 p.10 |
| Preço médio pago na importação [R$/kWh] | 0,648 | 0,697 | 0,535 | 0,557 | [R] (derivado no PDF) mesmas páginas |
| Potência máxima importada | 100,0 kW às 14:00 | 92,8 kW às 18:00 | 149,6 kW às 15:00 | 134,4 kW às 17:00 | [R] C1 p.11 · C2 p.15 · C3 p.12 · C4 p.16 |
| Intervalos no limite de 200 kW | 0/96 | 0/96 | 0/96 | 0/96 | [R] mesmas páginas |
| Carga líquida mínima (demanda − FV) | — | 45,4 kW às 12:45 | — | 45,4 kW às 12:45 · 0/96 negativos | [R] C2 p.11 · C4 p.12 |
| Decisões · com valor futuro válido · ótimas | 96 · 96 · 96 | 96 · 96 · 96 | 96 · 96 · 96 | 96 · 96 · 96 | [R] C1 p.12 · C2 p.16 · C3 p.13 · C4 p.17 |
| Objetivo da 1ª janela = operativo + valor futuro [R$] | 54,34 + 1.219,91 = 1.274,25 | 54,34 + 1.046,63 = 1.100,97 | 54,34 + 983,97 = 1.038,31 | 54,34 + 810,68 = 865,02 | [R] C1 p.28 · C2 p.32 · C3 p.38 · C4 p.42 |
| Evidência verificada ao gerar o PDF | 16/16 | 20/20 | 16/16 | 20/20 | [R] p.3 |

### A.2 CT-046 — decomposição por posto tarifário e por recurso

Ponta = 18:00–21:00 (12 intervalos), tarifa R$ 1,93894/kWh; fora da ponta R$ 0,44234/kWh. Custos por posto
obtidos somando os blocos realizados da tabela de decisões de cada PDF **e**, independentemente, das séries do ZIP
(coincidem no centavo). Energias por posto: séries do ZIP.

| Grandeza [D] | C1 | C2 | C3 | C4 |
|---|---:|---:|---:|---:|
| Importação na ponta [kWh] | 270,01 | 268,74 | 120,01 | 118,74 |
| Importação fora da ponta [kWh] | 1.697,14 | 1.310,96 | 1.821,26 | 1.435,08 |
| Custo na ponta [R$] (tabela do PDF) | 523,54 | 521,08 | 232,70 | 230,24 |
| Custo fora da ponta [R$] | 750,71 | 579,89 | 805,61 | 634,79 |
| Participação da ponta no custo | 41,1 % | 47,3 % | 22,4 % | 26,6 % |
| FV na ponta [kWh] | — | 1,27 (18:00–18:45) | — | 1,27 |
| Descarga na ponta · fora [kWh] | — | — | 150,00 · 0,14 (21:00) | 150,00 · 0,14 (21:00) |
| Carga (toda fora da ponta) [kWh] | — | — | 124,26 | 124,26 |
| Redução de custo frente a C1 [R$] | — | 173,28 (13,6 %) | 235,94 (18,5 %) | 409,22 (32,1 %) |
| Custo ajustado pela reposição do estoque (ver E-4) [R$] | 1.274,25 | 1.100,97 | 1.056,94 | 883,66 |
| Redução ajustada frente a C1 [R$] | — | 173,28 | 217,31 (17,1 %) | 390,60 (30,7 %) |

Relações exatas verificadas [D]:
- ΔC2 + ΔC3 = 173,28 + 235,94 = 409,22 = ΔC4 (nas séries: 409,2228 × 409,2237; diferença < R$ 0,001).
- ΔC2 = 386,18 kWh × 0,44234 + 1,27 kWh × 1,93894 = 170,82 + 2,46 = 173,28.
- ΔC3 = 150,00 kWh × 1,93894 (ponta evitada, 290,84) − 124,11 kWh × 0,44234 (carga líquida fora da ponta, 54,90) = 235,94.
- Estoque: 40,0 kWh internos consumidos (60 → 20) entregam 38,0 kWh ao barramento; a energia ciclada entrega
  124,26 × 0,95² = 112,14 kWh; 38,0 + 112,14 = 150,14 kWh descarregados. Repor 40,0 kWh fora da ponta custaria
  40,0 / 0,95 × 0,44234 = R$ 18,62.

### A.3 CT-046 — trajetória da bateria em C3 e C4 [D]

| Hora | C3: potência (+ descarga / − carga) | C3: E fim [kWh] | C4: potência | C4: E fim [kWh] | C4: FV [kW] |
|---|---|---:|---|---:|---:|
| 00:00–12:30 | 0 | 60,00 | 0 | 60,00 | 0–49 |
| 12:45 | 0 | 60,00 | −50,0 | 71,88 | 51,46 (máx.) |
| 13:00–15:00 | 0 | 60,00 | 0 | 71,88 | — |
| 15:00–16:30 | −50,0 de 15:00 a 16:00 (5 intervalos); 0 às 16:15 | 119,38 (16:30) | 0 às 15:00; −50,0 de 15:15 a 16:15 (5 intervalos) | 131,25 (16:30) | 35,3–24,0 |
| 16:30–18:00 | −50,0 em 16:30, 16:45, 17:15, 17:30; −47,0 em 17:45 | 178,04 (18:00) | −50,0 em 16:45, 17:00, 17:15; −46,9 em 17:30; −0,14 em 17:45 | 178,04 (18:00) | 24,0–11,1 |
| 18:00–20:45 | +50,0 (12 intervalos) | 20,15 (21:00) | +50,0 (12 intervalos) | 20,15 (21:00) | 1,27 até 18:45 |
| 21:00 | +0,56 | 20,00 | +0,56 | 20,00 | 0 |
| 21:15–24:00 | 0 | 20,00 | 0 | 20,00 | 0 |

- Energia necessária em 18:00 para descarregar 50 kW durante as 3 h de ponta e terminar no limite de 20 kWh:
  20 + 150/0,95 = 177,89 kWh; registrada 178,04 kWh (SOC 89,0 %; limite 90 %).
- Carga decidida em janelas cujo horizonte de 2 h ainda não alcançava a ponta (τ ≤ 16:00): 62,50 kWh de
  124,26 kWh (50,3 %) em C3 e em C4.
- Energia terminal planejada pelo MPC (PDF C3 p.33–34; C4 p.37–38): 71,1 → 83,0 → 94,8 → … → 166,1 kWh nas
  fronteiras 15:45 → 17:45. Os valores coincidem com o mínimo "a tempo", isto é, a energia que ainda permite atingir
  177,89 kWh às 18:00 carregando a 50 kW (71,0 → 166,0 kWh) [D].
- C4: a janela de 12:45 planejou 140,0 kWh na fronteira de 14:45; a janela seguinte (13:00) planejou 71,9 kWh, sem
  nova carga [R] C4 p.37.

### A.4 EMB-H2-120 — indicadores selados (C5)

| Indicador | Valor | Fonte |
|---|---|---|
| Energia demandada = atendida · déficit | 68,2 kWh · 0,00 kWh · 0/8 intervalos | [R] p.3, p.10, p.13 |
| Demanda: pico · mínimo (médias de 15 min) | 58,8 kW às 12:00 · 7,2 kW às 13:00 | [R] p.10 |
| FV aproveitada · vertida · pico | 6,1 kWh · 0,0 kWh · 3,1 kW | [R] p.4 |
| Bateria descarregada · carregada | 29,8 kWh · 1,5 kWh | [R] p.5 |
| Energia armazenada inicial → final (SOC) | 75,0 → 45,0 kWh (50 → 30 %) | [R] p.5 |
| Comportamento da bateria por intervalo | descarga, preserva, descarga, descarga, **carga**, descarga, descarga, descarga | [R] p.5 |
| PEMFC: energia · potência média · partidas/paradas | 33,8 kWh · 16,9 kW · 0/0 (ON nos 8 intervalos) | [R] p.6 |
| H₂ (EMS) · H₂ (modelo dinâmico) · subestimação máx. | 2,156 kg · 2,156 kg · 0,0002 kg | [R] p.6, p.9 |
| Custo realizado (100 % hidrogênio) · consumo específico | R$ 21,56 · 0,0638 kg/kWh | [R] p.6, p.21 |
| Consumo específico da curva em P mín · P máx | 0,0603 · 0,0768 kg/kWh | [R] p.8 |
| Estados no modelo dinâmico | RUN ×4, **IDLE (13:00)**, RUN ×3; coerente 8/8 | [R] p.9 |
| Decisões · com valor futuro · ótimas | 8 · 8 · 8 | [R] p.16 |
| Objetivo da 1ª janela | 12,00 + 9,55 = 21,56 (= custo realizado) | [R] p.19 |
| Energia planejada na fronteira 13:00 pela janela 0 | 56,3 kWh (registrada: 56,25 kWh) | [R] p.19 · [D] |
| Participação nas injeções | FV 8,7 % · descarga 42,8 % · PEMFC 48,5 % | [R] p.13 |

### A.5 EMB-H2-120 — série por intervalo [D]

| Intervalo | Demanda | FV | PEMFC | Bateria (+desc / −carga) | E no fim [kWh] | H₂ [kg] | kg/kWh |
|---|---:|---:|---:|---:|---:|---:|---:|
| 12:00 | 58,77 | 3,09 | 19,45 | +36,23 | 65,47 | 0,315 | 0,0647 |
| 12:15 | 20,44 | 3,09 | 17,36 | 0,00 | 65,47 | 0,277 | 0,0638 |
| 12:30 | 31,01 | 3,09 | 19,90 | +8,02 | 63,36 | 0,323 | 0,0648 |
| 12:45 | 47,97 | 3,09 | 17,88 | +27,00 | 56,25 | 0,286 | 0,0640 |
| 13:00 | 7,16 | 2,96 | **10,00** | **−5,80** | 57,63 | 0,151 | 0,0603 |
| 13:15 | 56,06 | 2,96 | 14,83 | +38,27 | 47,56 | 0,232 | 0,0627 |
| 13:30 | 22,92 | 2,96 | 17,88 | +2,07 | 47,01 | 0,286 | 0,0640 |
| 13:45 | 28,49 | 2,96 | 17,88 | +7,64 | **45,00** | 0,286 | 0,0640 |
| **Energia [kWh]** | **68,21** | **6,05** | **33,80** | **+28,36** (29,81 − 1,45) | — | **2,156** | 0,0638 |

Potências em kW (médias de intervalo); H₂ = custo do intervalo / R$ 10/kg (único termo de custo).
Estatísticas [D]: desvio-padrão da demanda 17,18 kW, da bateria 16,04 kW e da PEMFC 2,97 kW (1,52 kW sem o
intervalo das 13:00); correlação demanda × bateria 0,986. Nos três intervalos de demanda acima de 47 kW
(12:00, 12:45, 13:15; 40,70 kWh), a bateria entregou 25,37 kWh (62 %) e a PEMFC 13,04 kWh. Nos quatro de menor
demanda (12:15, 13:00, 13:30, 13:45; 19,75 kWh), a PEMFC entregou 15,78 kWh e a bateria, em termos líquidos, 0,98 kWh.

---

## B. Mapa de interpretações

| # | Observação | Valores | Explicação proposta [I] | Ressalvas | Situação |
|---|---|---|---|---|---|
| B1 | **C1: a ponta concentra o custo.** | 13,7 % da energia (270,01 kWh) responde por 41,1 % do custo (R$ 523,54). | A diferença de 4,4 vezes entre as tarifas faz da ponta o alvo econômico de qualquer recurso adicional. | Em C1 não há decisão: importação = demanda em todos os intervalos. | Confirmada |
| B2 | **Eixo A: o FV reduz a importação fora da ponta e quase não alcança a ponta.** | 387,45 kWh aproveitados, dos quais 1,27 kWh na ponta (0,3 %). Redução de R$ 173,28 (13,6 %). Preço médio pago sobe de 0,648 para 0,697 R$/kWh. Ponta passa a 47,3 % do custo. | Geração entre 06:00 e 18:45, com máximo de 51,46 kW às 12:45. A defasagem em relação à ponta faz o FV deslocar energia barata, e a parcela cara fica intacta. | Não há decisão do EMS em C2: FV sempre abaixo da demanda (carga líquida mínima 45,4 kW), sem exportação nem vertimento. O resultado é efeito da **composição**, não do gerenciamento. | Confirmada, com reenquadramento |
| B3 | **Eixo B: a bateria desloca exatamente 150 kWh da ponta.** | Descarga de 50 kW (limite de potência) nos 12 intervalos de ponta. Importação na ponta de 270,01 para 120,01 kWh. E(18:00) = 178,04 kWh contra 177,89 necessários. | O EMS carrega a energia que sustenta a potência máxima durante toda a ponta e chega ao piso de 20 kWh em seguida. Custo de 1 kWh entregue na ponta a partir da carga: 0,44234/0,9025 = 0,490 R$/kWh, contra 1,939 da rede. | O limite de 50 kW, e não a energia, restringe o benefício. | Confirmada |
| B4 | **Carga imediatamente antes da ponta.** | Toda a carga ocorre fora da ponta. C3: 15:00–17:45. C4: 12:45 e 15:15–17:45. Em C3, a carga começa às 15:00, quando restam 12 intervalos até a ponta e são necessários 9,9 intervalos a 50 kW. Daí em diante a folga fica entre 0 e 2 intervalos. | Com tarifa única fora da ponta, carregar às 3h ou às 15h custa o mesmo. O otimizador posterga a carga e a mantém próxima da trajetória mínima "a tempo". | **Não** escrever que o EMS escolheu os horários de menor tarifa dentro do período fora de ponta: a hora exata não tem conteúdo econômico (soluções equivalentes). | Confirmada, com reinterpretação |
| B5 | **Papel do sinal de valor futuro.** | 50,3 % da carga (62,50 kWh) foi decidida em janelas sem nenhum intervalo de ponta no horizonte de 2 h. As energias terminais planejadas coincidem com o mínimo "a tempo" (71,1 … 166,1 kWh). 96/96 sinais válidos. | Nessas janelas, o único termo que atribui valor à energia armazenada é V̂(E). A carga antecipada é coerente com o valor que o planejador transmite além do horizonte do MPC. A posição da quebra de inclinação de V̂ explica o plano "a tempo" (mecanismo já mostrado na Seção 6.1.3). | Indício, não prova de benefício: não houve rodada sem o sinal. Afirmar "coerente com", nunca "causado por". | Sustentada como indício |
| B6 | **Decomposição econômica de C3.** | +290,84 na ponta, −54,90 fora dela, saldo R$ 235,94. Estoque consumido: 40 kWh internos (38,0 kWh entregues). Reposição: R$ 18,62. Redução ajustada: R$ 217,31. | Parte da economia vem do esvaziamento do banco, permitido pela ausência de condição terminal. | A convenção de ajuste é decisão do autor (E-4). | Confirmada |
| B7 | **Eixo C: em C4 os efeitos se somam.** | ΔC4 = ΔC2 + ΔC3 (R$ 409,22). Mesmas energias de bateria de C3 (124,26/150,14, 60 → 20). Importação na ponta 118,74 = 120,01 − 1,27. | Sem excedente FV e com tarifa única fora da ponta, FV e bateria atuam sobre parcelas disjuntas: o FV reduz energia barata e a bateria desloca energia cara. Não há interação a explorar. | A hipótese de sinergia **não** se confirma. "Coordenação" em C4 = o EMS reproduz a mesma estratégia de armazenamento na presença do FV. Resultado restrito a este dimensionamento (FV abaixo da demanda mínima). | Hipótese refutada; comportamento descrito |
| B8 | **A carga das 12:45 em C4 não é "carga solar".** | Coincide com o máximo FV (51,46 kW), mas a carga líquida era de 45,43 kW e a importação subiu para 95,43 kW. O plano de 12:45 (140 kWh às 14:45) foi abandonado na janela seguinte. | Escolha entre ótimos equivalentes. O custo final é idêntico ao da soma C2 + C3. | **Não** escrever que a bateria armazenou excedente solar: não houve excedente. | Confirmada |
| B9 | **Custo realizado × valor futuro.** | Objetivo da 1ª janela = custo realizado em C1–C5 (C4: 865,02 contra 865,03). V̂ na 1ª janela de C4 = R$ 810,68. | Com previsão igual à realização, o plano inicial se cumpre. V̂ é a estimativa do custo de continuação, não uma despesa. | Coerência entre níveis, **não** desempenho. Sem erro de previsão, a resposta a incertezas não foi avaliada (Seção 5.4). | Confirmada |
| B10 | **C5: atendimento integral.** | 68,21 kWh, déficit 0. PEMFC 33,80 kWh (49,6 %), bateria líquida 28,36 kWh (41,6 %), FV 6,05 kWh (8,9 %). | A bateria é a segunda fonte de energia da missão, não apenas um amortecedor. | — | Confirmada |
| B11 | **C5: a bateria absorve a variação e a PEMFC permanece numa faixa estreita.** | Demanda 7,16–58,77 kW. Bateria −5,80 a +38,27 kW (correlação 0,986). PEMFC 10,0–19,9 kW (14,8–19,9 kW fora das 13:00). Nos intervalos acima de 47 kW, a bateria supre 62 %. | Coerente com a curva de consumo: o consumo específico cresce com a potência (0,0603 → 0,0648 kg/kWh no trecho operado), de modo que cobrir picos com a bateria economiza H₂. | Só na escala de 15 min: variações mais rápidas foram removidas pela agregação (Seção 5.3.1). A curva é quase linear no trecho (inclinações secantes de 0,068 a 0,072 kg/h por kW): **não** afirmar nivelamento ótimo. As diferenças entre 14,8 e 19,9 kW têm efeito de ordem de 10⁻³ kg. | Confirmada na escala de 15 min |
| B12 | **C5: carga somente na potência mínima.** | Única carga às 13:00. Carga líquida de 4,20 kW < P mín de 10 kW. PEMFC exatamente em 10,00 kW (IDLE no modelo dinâmico). Sobra de 5,80 kW → 1,45 kWh armazenados. Nos demais intervalos de baixa demanda, PEMFC ≤ carga líquida (às 12:15, igual; bateria parada). | A carga é imposta pela potência mínima com desligamento bloqueado. O EMS armazena também a parcela FV em vez de vertê-la. | A hipótese "PEMFC acima da demanda para preparar os períodos seguintes" **não** se confirma. O registro anterior dos acordos ("aumento da PEMFC para recuperar energia antes de nova fase de alta carga") não corresponde à rodada definitiva. | Hipótese refutada |
| B13 | **C5: reserva terminal ativa.** | E final = 45,00 kWh (exatamente a reserva). A janela 0 planejou 56,3 kWh às 13:00 (registrado: 56,25). | O EMS usa toda a energia que a reserva libera (30 kWh internos) e trata a bateria como fonte de energia até o limite declarado. O sinal transmite às janelas iniciais uma restrição situada além do seu horizonte de 1 h. | Mesma ressalva de B5 quanto à atribuição causal. | Confirmada |
| B14 | **C5: hidrogênio por regime.** | 2,156 kg no total. Potência mínima (13:00): 0,151 kg para 2,5 kWh (0,0603 kg/kWh). Faixa 14,8–19,9 kW: 2,005 kg para 31,30 kWh (0,0641 kg/kWh). | O custo da sobra forçada das 13:00 limita-se às perdas de ida e volta: 1,45 kWh armazenados devolvem no máximo 1,31 kWh. | Não há contrafactual de sobre-geração para custear: a estratégia não foi observada. | Quantificada |

---

## C. Plano editorial da Seção 6.2

**6.2.1 Contextualização (2 parágrafos, sem números).** P1: CT-046 com quatro configurações sob as mesmas entradas
(conforme a Seção 5.2), C1 como referência de fornecimento exclusivo pela rede e C4 como configuração completa. P2:
EMB-H2-120 isolada, com custo dado pelo hidrogênio e reserva final (conforme a Seção 5.3), sem configuração de
referência.
*Mensagem:* duas naturezas de problema para a mesma formulação.

**6.2.2 CT-046 (núcleo comparativo; Tabela 6.5 e Figura 6.3).**
1. Estrutura de custo de C1 (B1). Em C1 e C2 não há grau de liberdade de despacho.
2. Eixo A (B2): o FV substitui energia barata e não a ponta. O aumento do preço médio pago mostra essa defasagem.
3. Eixo B (B3–B6): estratégia de armazenamento, carga "a tempo", papel do sinal sem atribuição causal, decomposição
   ponta/fora da ponta e ajuste pelo estoque consumido.
4. Eixo C (B7–B8, Figura 6.3): aditividade exata. A carga das 12:45 não é armazenamento solar. Custo realizado ×
   valor futuro (B9).

*Mensagem:* a economia decorre de dois mecanismos independentes. O FV reduz a energia fora da ponta, e o
armazenamento desloca 150 kWh da ponta, limitado pela potência do banco. O EMS realiza o deslocamento integralmente
e no último momento compatível com as restrições.

**6.2.3 EMB-H2-120 (Figura 6.4 e Tabela 6.6).** Ordem:
1. Atendimento (B10).
2. Repartição de potência (B11).
3. Única carga, forçada pela potência mínima (B12).
4. Resposta aos intervalos de alta demanda e cumprimento exato da reserva (B13).
5. Hidrogênio por regime (B14).

*Mensagem:* sem diferencial temporal de preço, a bateria funciona como fonte de energia até a reserva e como
amortecedor de potência. A PEMFC permanece numa faixa estreita, e o EMS não sobre-gera para recarregar.

**6.2.4 Discussão integrada (recomendação: manter, 2 parágrafos).** Acrescenta três interpretações novas que não
cabem em 6.2.2 ou 6.2.3:
- **(a)** O papel da bateria é definido pela estrutura de custo do objetivo. Em CT-046, a diferença entre postos
  produz arbitragem postergada até o limite. Em C5, a curva de H₂ quase linear e a reserva produzem uso como fonte
  e amortecedor. Em nenhum caso o EMS armazenou energia além do que o objetivo remunerava.
- **(b)** A condição terminal determina o uso do estoque inicial: o piso em CT-046 e exatamente a reserva em C5.
  Isso tem consequência metodológica para comparar custos.
- **(c)** Nos dois estudos, decisões tomadas antes de o evento relevante entrar no horizonte do MPC (a carga antes
  da ponta; a reserva respeitada na janela 0) mostram a informação transmitida pelo planejador. Ressalvas: previsão
  perfeita e ausência de rodada sem o sinal.

Se o autor preferir não manter a 6.2.4, (a) e (b) cabem num parágrafo final de 6.2 e (c) migra para a 6.3.

---

## D. Plano de figuras e tabelas

Numeração: o manuscrito já contém as Figuras 6.1–6.2 e as Tabelas 6.1–6.4.

| Elemento | Conteúdo | Argumento | Observações |
|---|---|---|---|
| **Tabela 6.5** | Indicadores C1–C4: A.1 + linhas de A.2 (importação e custo por posto, FV, carga/descarga, E inicial → final, custo, redução, custo ajustado). | B1–B3, B6, B7 | Valores selados com a precisão do PDF; linhas derivadas rotuladas na fonte da tabela. |
| **Figura 6.3** (obrigatória) | Partitura de C4, lente Operação, tema claro (PNG fornecido, hora local). | B3–B5, B7–B9 | Mostra demanda, FV, carga hachurada antes da ponta, descarga de 50 kW na ponta, energia armazenada, importação, tarifa e custo. Atenção ao subtítulo "Intervalos exibidos: 00:00–00:00", que pode confundir (ver E-9). |
| **Figura 6.4** (obrigatória) | Partitura de C5, lente Operação, tema claro. | B10–B13 | **Falta o PNG exportado** (só existe em vetor no PDF C5, p.3). Exportar como foi feito para C4. |
| **Tabela 6.6** | Série de C5 por intervalo (A.5). | B11, B12, B14 | Com 8 intervalos, a tabela dá valores que a figura não permite ler. Substitui um gráfico adicional. |
| Figura opcional | Energia armazenada de C3 e C4 com a trajetória mínima "a tempo". | B4, B5 | Figura NOVA derivada dos dados, não existe nos ZIP. Só com autorização (E-8). Sem ela, o argumento fica no texto com os números de A.3. |
| Não recomendados | Figuras do ZIP (eixo em UTC; quatro curvas FV idênticas por arranjo) e Partituras de C1–C3. | — | Redundantes com a Tabela 6.5 e a Figura 6.3. A hora UTC desloca a ponta para 21:00–24:00. |

---

## E. Pontos que exigem decisão autoral

1. **Reenquadramento do Eixo A.** C1 e C2 não têm grau de liberdade de despacho: a diferença entre eles é efeito da
   composição física. Proposta: dizer isso explicitamente e não creditar ao EMS o aproveitamento do FV.
2. **Reenquadramento do Eixo C.** O benefício de C4 é a soma exata de C2 e C3. A narrativa de "coordenação que
   amplia a economia" não se sustenta. Proposta: apresentar a aditividade como resultado e explicá-la pela ausência
   de excedente FV e pela tarifa única fora da ponta.
3. **Hipótese de carga estratégica pela PEMFC (C5).** Refutada pela rodada definitiva (B12). O texto descreverá a
   carga forçada pela potência mínima. Confirmar que a expectativa registrada nos acordos de 15/11 deve ser abandonada.
4. **Correção pelo estoque consumido.** Opções:
   - (a) custo ajustado pela reposição fora da ponta (+R$ 18,62; reduções de 217,31 e 390,60), recomendada;
   - (b) apresentar ΔE ao lado do custo, sem monetizar;
   - (c) valorar os 38,0 kWh entregues pela tarifa de ponta (R$ 73,68), convenção que atribui toda a energia
     inicial à ponta.
5. **"Menor custo" no Eixo B.** A tarifa fora da ponta é única. Proposta: escrever "carga fora da ponta, concentrada
   nas horas que a antecedem", e não "nos períodos de menor tarifa".
6. **Grau de atribuição ao planejamento hierárquico.** Proposta: "coerente com o valor atribuído pelo sinal"
   (B5, B13). A Seção 6.1.3 já declara que o benefício do sinal não foi avaliado.
7. **Estrutura 6.2.4 × 6.3.** O manuscrito tem "6.2.1 Microrrede industrial CT-046", "6.2.2 Embarcação híbrida
   isolada" e "6.3 Discussão integrada dos resultados", cuja nota de redação abrange modularidade e coordenação
   (incluindo a 6.1). Proposta: 6.2 com quatro subseções, como na missão, e a 6.3 reservada à integração 6.1 + 6.2
   frente às duas contribuições, ou incorporada às Conclusões.
8. **Figura opcional derivada (C3 × C4).** Autorizar ou não uma figura nova a partir dos dados.
9. **Partituras.** Exportar a de C5 em PNG, nas mesmas condições da de C4. Decidir se o subtítulo
   "Intervalos exibidos: 00:00–00:00" deve ser explicado na legenda ("missão completa de 24 h") ou se a exportação
   deve ser refeita. A imagem não será alterada.
10. **Resíduo de 0,14 kWh descarregado às 21:00 (fora da ponta).** É economicamente desprezível (R$ < 0,01).
    Proposta: não mencionar no texto e manter apenas na tabela (descarga total 150,14 kWh, sendo 150,00 na ponta).
11. **Pendências no manuscrito fora do escopo desta etapa:**
    - A Seção 5.3.2 menciona as três rodadas interrompidas, o que contraria a regra desta missão.
    - A Tabela 5.4 remete à Tabela 5.2 para as rodadas C1–C4, mas esta não as identifica.
    - O título do artigo difere do registrado em `DECISOES_VIGENTES.md`.
12. **Precisão numérica no texto.** Proposta: energia e custo com duas casas, como na Seção 5; percentuais com uma.
