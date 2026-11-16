# Evidências da Seção 6.2 — séries reconstruídas e tabelas de decisão

Material de apoio da etapa 1 da Seção 6.2 (`../ETAPA1_EVIDENCIAS_E_PLANO.md`). Não é dado de instalação: são valores
DERIVADOS dos dez arquivos fornecidos pelo autor em 16/11/2026 (cinco relatórios PDF e cinco ZIP de figuras das
rodadas de referência). Nenhum modelo, otimizador ou banco do SEEDS2 foi executado ou lido; nenhuma instantânea foi usada.

| Caso | Rodada | Relatório PDF (páginas) | ZIP de figuras |
|---|---|---|---|
| C1 | `4f7da832ace7444183bfd68190c43618` | 42 | 01 demanda/potência · 02 tarifas e custo |
| C2 | `dbccd121535945ecb6c45fd4d1d1b977` | 47 | 01 · 02 |
| C3 | `7252f033c31c44918f7ec2e5174ba788` | 52 | 01 · 02 bateria · 03 tarifas e custo |
| C4 | `14d8e5b374044f9da57ecb72db2d5401` | 57 | 01 · 02 bateria · 03 tarifas e custo |
| C5 | `055096cf0d67491a89571be8144b79b1` | 28 | 01 · 02 bateria · 03 custo |

## Arquivos

- `dados/Ck_series.csv` — séries por intervalo (médias de 15 min, kW; custo em R$) reconstruídas das coordenadas
  vetoriais dos SVG do ZIP (`01_demanda_potencia_por_recurso.svg` e `0x_tarifas_e_custo_realizado.svg`).
  `ini_utc` = início do intervalo em UTC (eixo das figuras); `ini_local` = America/Sao_Paulo (UTC−3, fuso declarado da missão).
- `dados/Ck_fronteiras.csv` — energia interna [kWh] e SOC [%] nas N + 1 fronteiras (`02_bateria_*.svg`).
- `dados/Ck_decisoes.csv` — tabela «Decisões do MPC — previsto × realizado por bloco aplicado» extraída do TEXTO do
  PDF, com a página de origem (valores em R$ com duas casas, como impressos).
- `scripts/` — extratores (`svgser.py`, `series.py`, `dec.py`), a análise da Etapa 1 (`analise.py`) e o gerador da
  Figura 6.4 derivada (`figura_energia_c3_c4.py`: `python -I figura_energia_c3_c4.py ../dados ../../figuras`, matplotlib).

## Como as séries foram reconstruídas e conferidas

Os SVG são vetoriais (matplotlib, coordenadas com 6 casas decimais em pontos tipográficos). Os valores dos ticks são
lidos dos comentários de texto do próprio SVG; cada intervalo é um segmento horizontal [t_k, t_k+1) e é convertido
para dados pela transformação linear dos ticks. Conferências realizadas:

- soma por recurso × valores SELADOS dos PDFs: importação, FV, carga, descarga, demanda e custo coincidem no
  arredondamento impresso (ex.: C4 importação 1.553,8233 × 1.553,8 kWh; custo 865,0309 × R$ 865,03);
- custo por intervalo × tabela de decisões do PDF: |Δ| ≤ R$ 0,005 (arredondamento a duas casas do PDF);
- balanço do barramento demanda − (importação + FV + descarga − carga + PEMFC) ≤ 1,5 × 10⁻⁶ kW;
- importação × tarifa × 0,25 h = custo do intervalo, |Δ| ≤ 10⁻⁵ R$.

A resolução da reconstrução (≈ 10⁻⁶ kW) é muito inferior às grandezas discutidas; ainda assim, os valores do texto
devem ser citados com a precisão dos PDFs (selados) ou rotulados como derivados.

Reprodução (a partir das pastas extraídas dos ZIP, `zips/Ck/figuras/svg/…`, e do texto dos PDFs por
`pdftotext -layout`): `python -I scripts/series.py` e `python -I scripts/dec.py Ck Ck_pag.txt Ck_decisoes.csv`.
