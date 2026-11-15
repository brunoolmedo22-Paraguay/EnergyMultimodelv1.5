# Exemplos persistentes do SEEDS2

Instantâneas completas (`.seeds2snapshot.zip`) das microrredes de exemplo entregues com o SEEDS2 — previstas: os casos
C1–C5 do caderno de roteiros. Ao iniciar, o SEEDS2 restaura no catálogo toda instantânea desta pasta cuja microrrede
não esteja presente (`seeds2/microgrid/exemplos.py`). O disco do Streamlit Cloud é efímero: sem isso, os exemplos
sumiriam a cada reinício.

- **Como gerar:** Gestor de Microrredes → cartão da microrrede → **GUARDAR COMPLETO** → baixar a instantânea.
- **Conteúdo:** o banco inteiro da microrrede (configuração, inventário, cenários e versões, previsões, estratégias,
  rodadas e todos os dados gravados das rodadas). Formato e verificações: `seeds2/microgrid/snapshot.py` e
  `docs/seeds2/ARMAZENAMENTO.md`.
- **Comportamento:** exemplos EDITÁVEIS. Alterações feitas durante a execução valem até o próximo reinício; então a
  microrrede volta ao estado guardado. Um exemplo já presente no catálogo nunca é sobrescrito nem duplicado.
- **Desligar:** `SEEDS2_EXEMPLOS=0` (a suíte de testes e os roteiros E2E os desligam por padrão).

## Exemplos incluídos

| Arquivo | Microrrede | Conteúdo | SHA-256 |
|---|---|---|---|
| `C4_Carga_CT046_Solar_Bateria_Rede.seeds2snapshot.zip` | Carga CT-046 — Solar + Bateria + Rede (`ef5bc710…`) | FV 58 kWp (4 × 5S×5P, CS7L-580MS) + BESS 200 kWh / 50 kW; cenário «C4 — CT-046 · Solar + Bateria + Rede · 02-10-2026» (versão 9, motor V2); 3 rodadas concluídas | `d8d71cfa…6318ed` |
| `C5_EMB_H2_120_Embarcacao_hibrida.seeds2snapshot.zip` | EMB-H2-120 \| Embarcação híbrida hipotética (`085e4418…`) | PEMFC Horizon equivalente (1 unidade, EQUIVALENT_65KW_HORIZON_CONSTRAINED) + BESS 150 kWh / 75 kW (SOC 10–90 %) + FV 3,48 kWp (6S×1P, CS7L-580MS), isolada; cenário «C5 — EMB-H2-120 · Missão R2 · 02-10-2026» (versão 13, motor V2, Δ = 15 min, N = 4, m = 1, H_L = 8; planejador com 50 pontos e tolerância de R$ 0,05 = referência EXPERIMENTAL atual, sem análise de sensibilidade); 1 rodada concluída (v13: 8/8 intervalos, auditoria aceita, coerência dinâmica; H₂ 2,156 kg, R$ 21,56) + 3 interrompidas (v10–v12, histórico da B04-C5-02) | `14e61065…dcdc1f2ebb` |

Instantâneas geradas pelo responsável no deploy (GUARDAR COMPLETO) e versionadas sem alteração de conteúdo.

**Exceção autorizada à regra 8 do `CLAUDE.md`** (responsável, 14/11/2026): só esta pasta pode versionar instantâneas,
e só de microrredes HIPOTÉTICAS de exemplo (nenhum dado real de instalação, empresa ou medição). Não coloque aqui
instantâneas de microrredes reais nem cópias de `SEEDS2_DATA_DIR`.
