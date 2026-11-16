# Seção 6.2 — figuras, tabelas, rastreabilidade dos números e pendências

Complemento de `SECAO_6_2_TEXTO.md` (Etapa 2, não integrado ao Google Docs). Rótulos: **[R]** valor impresso no
relatório PDF da rodada (página indicada). **[D]** valor derivado dos registros, seja das séries reconstruídas dos SVG do
ZIP de figuras (`evidencias/dados/*_series.csv`, `*_fronteiras.csv`), seja das tabelas de decisão extraídas dos PDFs
(`evidencias/dados/*_decisoes.csv`), seja de operação aritmética sobre valores [R]. **[P]** parâmetro declarado na
Seção 5.

## 1. Arquivos de origem (fornecidos pelo autor em 16/11/2026)

| Caso | Rodada | Relatório PDF (SHA-256, 16 primeiros) | ZIP de figuras (SHA-256, 16 primeiros) |
|---|---|---|---|
| C1 | `4f7da832ace7444183bfd68190c43618` | `seeds2_relatorio_C1_CT_046_Somente_Rede_02_10_2026_v2_4f7da832_1.pdf` (`aa920107b206bfdd`, 42 p.) | `seeds2_figuras_C1_…_4f7da832.zip` (`7e2cb603201533d2`) |
| C2 | `dbccd121535945ecb6c45fd4d1d1b977` | `seeds2_relatorio_C2_CT_046_Solar_Rede_02_10_2026_v2_dbccd121_1.pdf` (`c5be45eeb4a7e401`, 47 p.) | `seeds2_figuras_C2_…_dbccd121.zip` (`8a08afb33018af2a`) |
| C3 | `7252f033c31c44918f7ec2e5174ba788` | `seeds2_relatorio_C3_CT_046_Bateria_Rede_02_10_2026_v2_7252f033_1.pdf` (`1448af7a7afc215a`, 52 p.) | `seeds2_figuras_C3_…_7252f033.zip` (`b0c0483a9e1a696f`) |
| C4 | `14d8e5b374044f9da57ecb72db2d5401` | `seeds2_relatorio_C4_CT_046_Solar_Bateria_Rede_02_10_2026_v9_14d8e5b3_2.pdf` (`2cf7f78d9b7c6e99`, 57 p.) | `seeds2_figuras_C4_…_14d8e5b3.zip` (`2af24170341ac029`) |
| C5 | `055096cf0d67491a89571be8144b79b1` | `seeds2_relatorio_C5_EMB_H2_120_Missao_R2_02_10_2026_v13_055096cf_1.pdf` (`1af18f1753c2e657`, 28 p.) | `seeds2_figuras_C5_…_055096cf_1.zip` (`43f943c52b67130e`) |

Partitura de C4: `seeds2_14d8e5b3_Partitura_da_operacao_lente_Operacao_claro.png` (2000 × 1856 px, SHA-256
`c63dbfd91b7e24c8…`), copiada sem alteração para `figuras/`.

## 2. Figuras

| Figura | Arquivo a inserir no manuscrito | Origem | Subseção e argumento |
|---|---|---|---|
| **6.3** | `figuras/seeds2_14d8e5b3_Partitura_da_operacao_lente_Operacao_claro.png` | Exportação ORIGINAL da Partitura (lente Operação, tema claro, hora local), rodada 14d8e5b3. Não recriada nem recortada. | 6.2.2: coexistência dos recursos em C4, carga antes da ponta, descarga de 50 kW, custo por intervalo. |
| **6.4** | `figuras/figura_6_4_energia_armazenada_C3_C4.png` (300 ppp; também `.svg` e `.pdf` vetoriais) | Figura DERIVADA. Energia nas 97 fronteiras de C3 e C4, reconstruída dos SVG `02_bateria_eq-e21ff4bbc46d.svg` dos ZIP (SHA-256 `2ea7e6da0ec3a8fd…` em C3 e `7b5f5cb1fbab6447…` em C4). Elementos de referência calculados só de parâmetros da Seção 5. Gerador: `evidencias/scripts/figura_energia_c3_c4.py`. | 6.2.2: carga "a tempo" em C3, carga das 12h45 em C4, mesmas energias e trajetórias distintas, decisões anteriores à entrada da ponta no horizonte do MPC. |
| **6.5** | `figuras/seeds2_055096cf_Partitura_da_operacao_lente_Operacao_claro.png` (2313 × 1956 px, SHA-256 `fd28a10315fabc3b…`) | Exportação ORIGINAL da Partitura fornecida pelo autor em 16/11/2026 (lente Operação, tema claro, hora local, rodada 055096cf, C5 v13, 12:00–14:00). Conferida contra a legenda: as seis faixas descritas estão presentes. O rótulo «14:00» do eixo aparece parcialmente cortado na própria exportação (não alterado). | 6.2.3: repartição PEMFC × bateria, carga às 13h, segundo ciclo e reserva. |

**Precisão da figura derivada.** As coordenadas dos SVG têm 6 casas decimais em pontos tipográficos (resolução de cerca
de 10⁻⁶ kWh). A energia inicial de 60,000 kWh, a final de 20,000 kWh e as somas de carga e descarga das séries de
potência coincidem com os valores selados dos relatórios (C3 p.4 e C4 p.8). Entre fronteiras, a potência é constante,
de modo que ligá-las por segmentos retos é exato. O eixo está em hora local, obtido do eixo UTC dos SVG com o fuso
America/Sao_Paulo (UTC−3) declarado nas rodadas.

**Posição no Google Docs.** Cada figura vai após o parágrafo de sua primeira citação: 6.3 após o primeiro parágrafo de
6.2.2, 6.4 após o parágrafo que começa por "Em C3, a bateria" e 6.5 após o primeiro parágrafo de 6.2.3. As
Tabelas 6.5 e 6.6 já estão na posição de inserção.

## 3. Tabelas

**Tabela 6.5.**
- [R]: demanda e atendida, C1 p.41, C2 p.46, C3 p.51 e C4 p.56.
- [R], com duas casas por [D] nas séries:
  - FV: C2 p.13 e C4 p.14.
  - Importação total: C1 p.5, C2 p.9, C3 p.6 e C4 p.10.
  - Carga, descarga e energia inicial e final: C3 p.4 e C4 p.8.
- [R]: custo realizado (mesmas páginas) e preço médio pago (C1 p.5, C2 p.9, C3 p.6 e C4 p.10).
- [D]: importação por posto (séries). Custo na ponta pela soma dos blocos 18h–20h45 das tabelas de decisão (C1 p.28–30,
  C2 p.32–34, C3 p.38–40 e C4 p.42–44), coincidente com as séries ao centavo.
- [D]: reduções e percentuais por operação sobre [R].
- Déficit, exportação, vertimento e limite de importação nulos: [R], p.3, p.10 e p.11–16 de cada relatório.

**Tabela 6.6.**
- Potências por intervalo: [D], `evidencias/dados/C5_series.csv`.
- Energia ao fim: [D], `C5_fronteiras.csv`. Inicial e final [R] p.5.
- H₂ por intervalo: [D], custo realizado do bloco (tabela de decisões, p.19) ÷ R$ 10/kg. Total [R] p.6.
- Totais de energia: [R] p.6, p.12 e p.13. FV em [D], com duas casas (impresso 6,1 kWh).

## 4. Rastreabilidade das afirmações quantitativas

### 6.2.2 — CT-046
| Afirmação | Valor | Fonte |
|---|---|---|
| C1: importação = demanda em todos os intervalos | máx. diferença < 10⁻⁶ kW | [D] C1_series |
| Ponta em C1: energia e custo | 270,01 kWh (13,7 %); R$ 523,54 (41,1 %) | [D] séries; [D] tabela de decisões, C1 p.28–30 |
| Razão entre tarifas | 1,93894 / 0,44234 = 4,4 | [P] Seção 5.2.1 |
| C2: FV aproveitada, redução de custo | 387,45 kWh (19,7 %); R$ 173,28 (13,6 %) | [R] C2 p.13 e p.9 |
| Carga líquida mínima | 45,43 kW às 12h45 | [R] C2 p.11 (45,4) · [D] |
| Período e máximo FV | 6h–19h; 51,46 kW às 12h45 | [D] C2_series (pico por arranjo 12,9 kW, [R] p.4–7) |
| FV na ponta | 1,27 kWh | [D] C2_series |
| Importação na ponta de C2 | 268,74 kWh | [D] |
| Preço médio pago, C1 e C2 | 0,648 → 0,697 R$/kWh | [R] C1 p.5 e C2 p.9 |
| C3: E = 60,00 até 15h; carga de 124,26 kWh entre 15h e 18h; 178,04 kWh às 18h; 20,15 kWh às 21h | — | [D] C3_fronteiras e C3_series · [R] C3 p.4 |
| Descarga de 50 kW em 12 intervalos; importação na ponta de 270,01 para 120,01 kWh | — | [D] C3_series |
| Energia necessária às 18h | 20 + 150/0,95 = 177,89 kWh | [D] sobre [P] |
| Custo do kWh deslocado | 0,44234/0,9025 = R$ 0,490 | [D] sobre [P] |
| Início da carga e folga | 12 intervalos restantes; 9,9 necessários; folga ≤ 2,07 intervalos | [D] C3_fronteiras e [P] |
| Carga decidida em janelas sem ponta no horizonte (τ ≤ 16h) | 62,50 kWh (50,3 %) | [D] C3_series + [P] N = 8 (2 h) |
| Sinal válido | 96 de 96 | [R] C3 p.13 |
| Energias planejadas no fim das janelas (fronteiras 15h45–17h45) | 71,1 → 166,1 kWh | [R] C3 p.33–34 (C4 p.37–38) |
| Trajetória mais tardia nas mesmas fronteiras | 71,0 → 166,0 kWh | [D] sobre [P] |
| Redução em C3 e componentes | R$ 235,94 = 290,84 − 54,90 | [R] C3 p.6 · [D] C3 p.38–40 |
| Estoque: 40,00 kWh → 38,00 kWh entregues; 112,14 kWh do ciclo | — | [R] C3 p.4 · [D] |
| Estimativa de reposição (complementar) | 40/0,95 × 0,44234 = R$ 18,62 → R$ 217,31 | [D], hipótese explícita no texto |
| C4: mesmas energias de C3; custo; redução de 409,22 = 173,28 + 235,94 | — | [R] C4 p.8, p.10 e p.14 |
| Custo por intervalo na ponta em C4; importação remanescente | R$ 16,62–20,77; 34,29–42,85 kW | [D] C4_series (blocos [R] C4 p.43–44) |
| Ponta no custo de C4 | 26,6 % (230,24/865,03) | [D] C4 p.42–44 |
| Carga das 12h45 em C4; 71,88 kWh até 15h15; trajetórias iguais desde 18h | — | [D] C4_series e C4_fronteiras |
| Importação às 12h45 em C4 | 95,43 kW (carga líquida de 45,43 kW) | [D] C4_series |
| Plano da janela das 12h45 e da seguinte | 140,0 kWh às 14h45; 71,9 kWh às 15h | [R] C4 p.37 |
| Redução da importação em C3 | 25,88 kWh = 150,14 − 124,26 | [D] |
| Objetivo da 1ª decisão de C4 | 54,34 + 810,68 = 865,02 | [R] C4 p.42 (C1 p.28, C2 p.32, C3 p.38) |

### 6.2.3 — EMB-H2-120
| Afirmação | Valor | Fonte |
|---|---|---|
| Atendimento; déficit | 68,21 kWh; 0 em 8 intervalos | [R] p.10 e p.27 |
| PEMFC, bateria líquida e FV | 33,80 (49,6 %); 28,36 (41,6 %); 6,05 kWh (8,9 %) | [R] p.6, p.5 e p.12 · [D] percentuais |
| Intervalos acima de 47 kW; mínimo | 12h, 12h45, 13h15; 7,16 kW às 13h | [D] C5_series · [R] p.10 |
| Faixa e desvio-padrão da bateria; correlação | −5,80 a +38,27 kW; 16,04 kW; 0,986 | [D] C5_series (desvio populacional) |
| Limite de potência da bateria | 75 kW | [P] Seção 5.3.1 · [R] p.5 |
| Desvio-padrão da demanda | 17,18 kW | [D] |
| Faixa e desvio-padrão da PEMFC | 10,00–19,90 kW (14,83–19,90 sem 13h); 2,97 kW | [D] · média de 16,9 kW [R] p.6 |
| Intervalos de maior demanda | bateria 25,37 de 40,70 kWh (62 %) | [D] |
| Intervalos de menor demanda | PEMFC 15,78 de 19,75 kWh; bateria líquida 0,98 kWh | [D] |
| Consumo específico | 0,0603 kg/kWh (10 kW); 0,0648 (19,90 kW); 0,0768 (P máx) | [D] custo por bloco ÷ energia · [R] p.8 (P mín e P máx) |
| Curva quase linear no trecho operado; efeito pequeno das diferenças de potência | (texto qualitativo desde a revisão final) | [D] inclinações secantes de 0,068 a 0,072 kg/h por kW entre os pontos da Tabela 6.6; efeito estimado da ordem de 10⁻³ kg. Mantidos aqui como suporte e não citados no texto |
| 13h: carga líquida de 4,20 kW; PEMFC em 10,00 kW; sobra de 5,80 kW; 1,45 kWh; sem vertimento; estado IDLE | — | [D] C5_series · [R] p.5, p.9 e p.4 |
| 12h15: PEMFC = carga líquida = 17,36 kW; bateria inativa ("preserva") | — | [D] · [R] p.5 |
| 13h15: bateria 38,27 kW (maior descarga); PEMFC 14,83 kW | — | [D] C5_series |
| Variação entre 13h e 13h15 | demanda +48,90 kW; bateria +44,07 kW (90 %); PEMFC +4,83 kW; FV 0 | [D] C5_series |
| Entrega da bateria de 13h15 a 14h | 11,99 kWh | [D] |
| Parcela associável à carga das 13h | ≤ 1,45 × 0,95² = 1,31 kWh | [D] |
| Energia acima da reserva às 13h | 56,25 − 45 = 11,25 kWh | [D] C5_fronteiras |
| Plano da janela 0 para 13h | 56,3 kWh; realizado 56,25 kWh | [R] p.19 · [D] |
| Planos intermediários × executado | janela 12h15: 56,3 kWh (13h15) × 57,63; janela 12h30: 48,8 (13h30) × 47,56; janela 12h45: 47,8 (13h45) × 47,01; janelas 13h–13h45: 45,0 (14h) × 45,00. Diferença máxima de 1,3 kWh | [R] p.19 · [D] C5_fronteiras |
| Reotimização a cada intervalo com aplicação do primeiro (m = 1) | 8 janelas, N = 4 | [R] p.16 e p.23–24 · [P] Seção 5.3.2 |
| Sinal válido | 8 de 8 | [R] p.16 |
| Energia final = reserva; 30 kWh internos | 45,00 kWh | [R] p.5 |
| H₂ do EMS e do modelo dinâmico; subestimação; coerência | 2,156 kg; 2,156 kg; 0,0002 kg; 8 de 8 | [R] p.6 e p.9 |
| Custo; consumo específico médio | R$ 21,56; 0,0638 kg/kWh | [R] p.6 e p.21 |
| Por regime | 0,151 kg / 2,50 kWh; 2,005 kg / 31,30 kWh | [D] |
| Partidas e paradas | 0 e 0 | [R] p.6 |

### 6.2.4
Não introduz números novos. As afirmações remetem a 6.2.2 e 6.2.3. O objetivo da primeira decisão difere do custo
realizado em R$ 0,01 em C4 e é igual nos demais ([R] C1 p.28, C2 p.32, C3 p.38, C4 p.42 e C5 p.19).

## 5. Pendências

Nenhuma pendência científica ou editorial. A Partitura de C5 foi recebida e integrada (seção 7).

## 6. Revisão autoral final (correções A a D)

| Correção | Local | Alteração |
|---|---|---|
| A | 6.2.4, 1º parágrafo, final | A frase que atribuía à condição terminal o uso do estoque nos dois estudos foi substituída. Em C3 e C4, sem condição terminal de energia, o banco termina no limite inferior porque a energia remanescente não tem valor na formulação. Em C5, a reserva final é uma restrição explícita, atendida exatamente. |
| B | 6.2.2, parágrafo de C4 («Em C4, a geração fotovoltaica…») | Removido «sem competição ou complementaridade entre eles». O texto afirma a aditividade econômica e a ausência de sinergia econômica adicional mensurável neste caso, sem negar a coordenação operacional (despacho conjunto em cada janela) nem a complementaridade em outras condições. |
| C | 6.2.3, novo parágrafo «A disponibilidade dessa energia…» · 6.2.4, 2º parágrafo | A primeira janela passa a ser descrita como referência para a fronteira das 13h, alcançada na operação. O texto registra a reotimização das oito janelas e as diferenças de até 1,3 kWh entre planos intermediários e o executado (PDF C5, p.19), e mantém «consistente com o sinal de valor futuro», sem causalidade exclusiva. |
| D | 6.2.3, ordem e conteúdo | A ordem passou a ser: repartição observada (com o limite de 75 kW) → carga forçada às 13h → segundo ciclo (13h15: 38,27 × 14,83 kW; a bateria assume 44,07 dos 48,90 kW de aumento; reserva de 45 kWh atingida) → referência inicial e reotimização → razão operacional (restrições da PEMFC e consumo específico) → consumo de H₂. Retiradas do texto as inclinações secantes e a ordem de grandeza de 10⁻³ kg, preservadas na seção 4 como suporte. |

Preservado sem alteração: 6.2.1, demais parágrafos de 6.2.2, Tabelas 6.5 e 6.6, Figuras 6.3 e 6.4 (arquivos e legendas),
legenda da Figura 6.5, todos os valores já citados e as fontes da seção 4. Valores novos no texto (75 kW, 48,90, 44,07,
90 %, 4,83 kW e 1,3 kWh) decorrem dos mesmos registros (rastreados na seção 4). Nenhuma inconsistência objetiva foi
encontrada nos resultados.

## 7. Integração ao Google Docs (16/11/2026)

Manuscrito mestre `1PEeDRhVguqhdZPyB4YvHITjFbOT8DiczboQ413g9tdo`, revisão final
`AHj4eMSQ0PMnXSOh-aqdwBvS_OU9gGo77Ec3FbDJHF0sHlvT85AqIGtCmcKwQNOfSvHECUZcouMlhLhziAS5AlGH88nTybiJOyp9nn9RVXQ`.

- **Substituição:** os três marcadores preliminares («6.2 Resultados da avaliação operacional», «6.2.1 Microrrede industrial
  CT-046», «6.2.2 Embarcação híbrida isolada», com suas notas de redação e títulos vazios) foram trocados pela Seção 6.2
  aprovada. O título vazio que os precedia passou a ser o título 6.2 (Título 2), e as subseções usam Título 3, como na 6.1.
- **Conferência por leitura do documento:**
  - As Seções 1 a 6.1 e da 6.3 ao fim estão idênticas à leitura anterior à integração, em texto e estilos.
  - O texto corrido da 6.2 é idêntico, caractere a caractere, ao de `SECAO_6_2_TEXTO.md`.
  - As 210 células das Tabelas 6.5 e 6.6 são idênticas às aprovadas.
  - As três figuras estão incorporadas (451 pt de largura, proporções preservadas, centralizadas).
  - Todo o texto inserido tem o fundo amarelo-claro da regra de rastreabilidade (RGB 1; 0,949; 0,8, o mesmo da 6.1).
  - Não há marcadores Markdown nem ponto e vírgula, e cada título, tabela e figura aparece uma única vez.
- **Padrão visual da 6.1 reproduzido:**
  - Legenda acima e «Fonte» abaixo, em 10 pt, com rótulo em negrito.
  - Tabelas nativas com cabeçalho cinza-claro em negrito, corpo em 9 pt e preenchimento de 5 pt.
  - Colunas numéricas alinhadas à direita.
- **Figuras:** inseridas a partir de um Google Doc temporário de transporte (método já usado nas Figuras 6.1 e 6.2), em
  resolução original. As imagens do arquivo de transporte são byte a byte iguais às de `figuras/` (SHA-256 conferidos). O
  documento «SEEDS2 — Transporte temporário das Figuras 6.3–6.5 (pode ser excluído)» ficou na pasta «R03 — figuras
  finais (8 pt)» do Drive.
- **Ajustes editoriais de integração:**
  - 6.2.4: frase substituída conforme a autorização.
  - Na frase seguinte, «O uso do estoque inicial, porém, resultou de mecanismos distintos» passou a «O uso do estoque
    inicial também decorreu de mecanismos diferentes», ajuste de conectivo e de repetição sem mudança de sentido.
- **Limitação da API:** a opção «fixar linha de cabeçalho» das tabelas (presente nas Tabelas 6.1 a 6.4) não pode ser
  aplicada pela API. As Tabelas 6.5 e 6.6 atravessam uma quebra de página no PDF exportado (págs. 37–38 e 42–43). Para
  repetir o cabeçalho: botão direito na tabela → Propriedades da tabela → Linha → «Fixar linha de cabeçalho».
