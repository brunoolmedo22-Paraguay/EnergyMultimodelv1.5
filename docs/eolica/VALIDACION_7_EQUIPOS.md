# Validação da ampliação eólica

Execute da raiz, com Python 3.12 e dependências do repositório:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m tools.validate_wind_catalog --output docs/eolica/RESULTADOS_VALIDACAO_CATALOGO.json
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_wind_catalog_expansion.py -q
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ -q -rs
```

Auditoria numérica não é certificação física. Exit 0 do validador significa integridade do catálogo; `reference_approval` e `integration_status` registram as quatro pendências primárias. Tolerância de 1% no filtro secundário não é incerteza experimental publicada.

## Mapa de aceitação

| Requisito | Evidência |
|---|---|
| E-01 | SHA-256 dos seis registros completos; hash exato das três colunas de potência e igualdade de TODOS os KPIs para semana meteorológica e grade 0..30 m/s, 601 pontos |
| E-02/E-08/E-09 | Sete CSV lidos independentemente do ZIP, todos os nós, pontos médios, unidades, ordem e finitude; blob Git dos quatro NREL |
| E-03..E-06 | Picos 12,555; 20,611; 3,025; 1,430 kW e ramo decrescente SWIFT sem recorte |
| E-07 | Referência em velocidade separada de pico; erro relativo, sem tolerância absoluta 10 kW; contradições rejeitadas |
| E-10 | Todos os negativos preservados; balanço G-A; pequenos rejeitados em simulação e plano da microrrede |
| E-11..E-13 | Extremos, truncamento, cut-in/cut-out reais, ambos domínios real/equivalente; nenhuma extrapolação inventada |
| E-14..E-16 | Quantidade, energias e perdas uma vez, importações não descontadas, FC >100% permitido e denominador explícito |
| E-17/E-18 | Formatação kW, gráficos de pequenos em kW, AppTest dos sete, seletor e referências exatamente com 13 |
| E-19 | Variantes fixas V47/V52, SHA dos três PDF e rejeição adversarial de fabricante/modelo/variante/geometria divergentes |
| E-20 | Regressão completa e proteção explícita de arquivos EMS/solar/bateria/PEMFC; resultado em RESULTADOS_REGRESION.md |

110 testes novos passaram na execução dedicada. Há testes parametrizados adversariais de dados não finitos, curvas truncadas, potências contraditórias, unidades erradas, parâmetros faltantes, densidade inválida, auxiliares e identidade. Interface testada com Streamlit AppTest; sem alegação de execução JavaScript de navegador ou ensaio de campo.

A fixture `tests/fixtures/wind_historical_v1.json` foi capturada ANTES das mudanças na base `10365c5`, após os 9 testes eólicos existentes passarem. Não foi regravada para adaptar resultados novos. Sem alteração das seis entradas originais. Somente as duas provas antigas que contavam/iteravam o catálogo foram delimitadas aos históricos com autorização explícita do usuário; as asserções físicas originais foram conservadas.

## Continuação autorizada das três guardias

Somente as três guardias históricas afetadas foram ajustadas com filtros nominais e hashes fixos, preservando todas as asserções. Ver [guardias, hashes e adversariais](GUARDIAS_REGRESION_EOLICA.md). Suite completa final: **1758 passed, 0 failed, 0 skipped, 7 warnings**. Os 110 testes novos da ampliação e as referências numéricas dos seis históricos permanecem intactos.
