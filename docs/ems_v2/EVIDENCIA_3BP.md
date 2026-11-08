# Evidência executada — Piso 3B-P (gerada por `python -m ems_v2.milp.evidencia`)

- Data (UTC): 2026-11-08T17:03:38+00:00 · commit: `90439c94b5d8233b0944fefb7d77d357f9b6b825`
- Python 3.13.18 · Linux-6.18.44-fc-v310-x86_64-with-glibc2.39 · 4 CPUs · x86_64
- Pyomo 6.10.1 · highspy 1.15.1 · HiGHS 1.15.1 · interface `pyomo.contrib.solver:highs` · divergências das versões fixadas: nenhuma
- Configuração base: `{'time_limit_s': 60.0, 'threads': 1, 'rel_gap': 0.0, 'abs_gap': 0.0, 'semente': 0, 'opcoes_highs': {}}` (gaps nulos, 1 thread, semente 0)

Sintético/algébrico — **não é validação física**. Tempos de parede nesta máquina (indicativos).

| Caso | Esperado (analítico) | Classificação | Terminação / status | Objetivo (R$) | Limite | gap rel. | Var. / bin. / restr. | Construção (s) | Solver (s) | Despacho |
|---|---|---|---|---|---|---|---|---|---|---|
| A01 | 60 kW × 60 × 1 min; 60 kWh | `otimo` | convergenceCriteriaSatisfied / optimal | 0 | 0 | 0 | 120 / 0 / 120 | 0.0028 | 0.022 | `aceito_otimo` |
| A02 | 10 kW × 1 min; 1/6 kWh | `otimo` | convergenceCriteriaSatisfied / optimal | 0 | 0 | 0 | 2 / 0 / 2 | 0.0013 | 0.0069 | `aceito_otimo` |
| A03 (1×60 min) | e_N = 50 kWh | `otimo` | convergenceCriteriaSatisfied / optimal | 0 | 0 | 0 | 5 / 1 / 5 | 0.0015 | 0.0075 | `aceito_otimo` |
| A03 (60×1 min) | e_N = 50 kWh | `otimo` | convergenceCriteriaSatisfied / optimal | 0 | 0 | 0 | 241 / 60 / 241 | 0.0026 | 0.013 | `aceito_otimo` |
| A04 | P_c = 10 kW; e_1 = 69 kWh | `otimo` | convergenceCriteriaSatisfied / optimal | 0 | 0 | 0 | 7 / 1 / 6 | 0.0013 | 0.0075 | `aceito_otimo` |
| B01A | E_indisp = 100 kWh; custo R$ 0 | `otimo` | convergenceCriteriaSatisfied / optimal | 0 | 0 | 0 | 2 / 0 / 2 | 0.0012 | 0.0025 | `aceito_otimo` |
| B01B | C_oper = 20 kW; custo R$ 10 | `otimo` | convergenceCriteriaSatisfied / optimal | 10 | 10 | 0 | 2 / 0 / 2 | 0.0058 | 0.0025 | `aceito_otimo` |
| A05-FEAS | objetivo nulo declarado; carregar e verter factíveis | `otimo` | convergenceCriteriaSatisfied / optimal | 0 | 0 | 0 | 7 / 1 / 6 | 0.0013 | 0.0032 | `aceito_otimo` |
| A05-OPT | P_c = 10 kW; C_oper = 0; e_1 = 59 kWh; R$ 0 | `otimo` | convergenceCriteriaSatisfied / optimal | 0 | 0 | 0 | 7 / 1 / 6 | 0.0022 | 0.0082 | `aceito_otimo` |
| A06 | q = 0,9 kg/h; 0,015 kg/min; R$ 0,15 (c_H = 10 R$/kg) | `otimo` | convergenceCriteriaSatisfied / optimal | 0.15 | 0.15 | 0 | 5 / 1 / 7 | 0.0014 | 0.0028 | `aceito_otimo` |
| A06 ON a 5 kW | inviável (5 kW ∉ domínio ON) | `inviavel` | provenInfeasible / noSolution | — | — | — | 5 / 1 / 7 | 0.0013 | 0.0031 | `sem_despacho` |
| PWL não convexa + BESS | p = 16 kW; q = 1,05 kg/h; R$ 12,5 (enumeração) | `otimo` | convergenceCriteriaSatisfied / optimal | 12.5 | 12.5 | 0 | 14 / 4 / 13 | 0.0014 | 0.0045 | `aceito_otimo` |
| A07 | inviável (P_min 20 kW, demanda 5 kW, sem sumidouro) | `inviavel` | provenInfeasible / noSolution | — | — | — | 2 / 0 / 3 | 0.0012 | 0.0023 | `sem_despacho` |
| A08 duro | inviável | `inviavel` | provenInfeasible / noSolution | — | — | — | 2 / 0 / 3 | 0.0015 | 0.0024 | `sem_despacho` |
| A08 degradado | ℓ = 5 kW; ENS = 5 kWh; R$ 10 (V = 2 R$/kWh) | `otimo` | convergenceCriteriaSatisfied / optimal | 10 | 10 | 0 | 3 / 0 / 3 | 0.0013 | 0.0026 | `aceito_otimo` |
| 2 BESS heterogêneos | P_c = 8,75 / 6,25 kW; R$ 1,1875 | `otimo` | convergenceCriteriaSatisfied / optimal | 1.1875 | 1.1875 | 0 | 12 / 2 / 10 | 0.0016 | 0.0082 | `aceito_otimo` |
| Exclusividade | P_c = 1/0,9 kW; R$ 18,888… | `otimo` | convergenceCriteriaSatisfied / optimal | 18.8889 | 18.8889 | 0 | 7 / 1 / 6 | 0.0014 | 0.0048 | `aceito_otimo` |
| Vários UIDs | auditoria aceita | `otimo` | convergenceCriteriaSatisfied / optimal | 4.255 | 4.255 | 0 | 59 / 9 / 53 | 0.0035 | 0.012 | `aceito_otimo` |
| Maior N=16 (completo) | ótimo | `otimo` | convergenceCriteriaSatisfied / optimal | 49.3428 | 49.3428 | 0 | 659 / 192 / 563 | 0.0052 | 0.057 | `aceito_otimo` |
| Maior N=16 mip_max_improving_sols=1 | incumbente NÃO ótimo, auditado | `factivel_nao_otimo` | iterationLimit / feasible | 49.779 | 49.3428 | 0.00876 | 659 / 192 / 563 | 0.0082 | 0.052 | `aceito_factivel_nao_otimo` |
| Maior N=16 time_limit=0 | sem incumbente | `sem_solucao` | maxTimeLimit / noSolution | — | — | — | 659 / 192 / 563 | 0.0043 | 0.031 | `sem_despacho` |
| Maior N=48 time_limit=0,05 s (não determinístico) | limite de TEMPO; incumbente depende da máquina | `factivel_nao_otimo` | maxTimeLimit / feasible | 256.233 | 252.749 | 0.0136 | 1971 / 576 / 1683 | 0.013 | 0.13 | `aceito_factivel_nao_otimo` |
