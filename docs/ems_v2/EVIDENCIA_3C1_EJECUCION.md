# Evidência executada — Piso 3C-1 (gerada por `python -m ems_v2.milp.evidencia_3c1`)

- Data (UTC): 2026-11-09T02:17:14+00:00 · commit: `dae4e23acb124883dd046d93f7c32c9f62abf3fd`
- Python 3.13.18 · Linux-6.18.44-fc-v310-x86_64-with-glibc2.39 · 4 CPUs · x86_64
- Pyomo 6.10.1 · highspy 1.15.1 · HiGHS 1.15.1 · interface `pyomo.contrib.solver:highs` · divergências das versões fixadas: nenhuma
- Configuração: `{'time_limit_s': 60.0, 'threads': 1, 'rel_gap': 0.0, 'abs_gap': 0.0, 'semente': 0, 'opcoes_highs': {}}` (gaps nulos, 1 thread, semente 0)
- Tempos: mediana e máximo de 5 execuções por caso nesta máquina (amostra pequena; SEM caráter estatístico).

Sintético/algébrico — **não é validação física**.

| Caso | Esperado (analítico/enumeração) | Classificação | Despacho | Objetivo (R$) | Eventos | Garantia | Var. / bin. / restr. | Construção med. (s) | Solver med./máx. (s) |
|---|---|---|---|---|---|---|---|---|---|
| A transições | u = [0,1,1,0]; y_1 = z_3 = 1; R$ 7 (eventos) | `otimo` | `aceito_otimo` | 7 | syn-ter: 1↑/1↓ | completa_na_janela | 16 / 12 / 32 | 0.004 | 0.006 / 0.014 |
| B rampa | p = [15,20,25,30]; R$ 2,5 | `otimo` | `aceito_otimo` | 2.5 | syn-ter: 0↑/0↓ | completa_na_janela | 33 / 16 / 53 | 0.003 | 0.006 / 0.010 |
| C T_on = 45 | u = [1,1,1,0]; R$ 5 | `otimo` | `aceito_otimo` | 5 | syn-ter: 1↑/1↓ | completa_na_janela | 33 / 16 / 49 | 0.003 | 0.006 / 0.008 |
| C T_on = 0 | u = [1,0,0,0]; R$ 0 | `otimo` | `aceito_otimo` | 0 | syn-ter: 1↑/1↓ | completa_na_janela | 33 / 16 / 45 | 0.003 | 0.011 / 0.012 |
| D T_off = 45 | u = [0,0,0,1]; R$ 3,5 | `otimo` | `aceito_otimo` | 3.5 | syn-ter: 1↑/1↓ | completa_na_janela | 33 / 16 / 49 | 0.003 | 0.013 / 0.014 |
| D T_off = 0 | u = [1,0,0,1]; R$ 1 | `otimo` | `aceito_otimo` | 1 | syn-ter: 1↑/1↓ | completa_na_janela | 33 / 16 / 45 | 0.004 | 0.016 / 0.016 |
| E obrigação OFF herdada | u = [0,0,1,1]; R$ 10 | `otimo` | `aceito_otimo` | 10 | syn-ter: 1↑/0↓ | completa_na_janela | 33 / 16 / 51 | 0.003 | 0.014 / 0.015 |
| E obrigação ON herdada | u = [1,1,0,0]; R$ 5 | `otimo` | `aceito_otimo` | 5 | syn-ter: 0↑/1↓ | completa_na_janela | 33 / 16 / 51 | 0.004 | 0.013 / 0.014 |
| F cumprir_na_janela | u = [0,1,1,1]; R$ 5; garantia completa | `otimo` | `aceito_otimo` | 5 | syn-ter: 1↑/0↓ | completa_na_janela | 33 / 16 / 51 | 0.003 | 0.013 / 0.014 |
| F residual vinculante | u = [0,0,0,1]; R$ 0; obrigação 1800 s | `otimo` | `aceito_otimo` | 0 | syn-ter: 1↑/0↓ | residual_vinculante | 33 / 16 / 49 | 0.003 | 0.012 / 0.013 |
| G 2 unidades do bloco | u#1 = 1111, u#2 = 0011; R$ 1 | `otimo` | `aceito_otimo` | 1 | syn-ter#1: 0↑/0↓; syn-ter#2: 1↑/0↓ | residual_vinculante | 32 / 24 / 78 | 0.003 | 0.006 / 0.007 |
| H enumeração | R$ 12,7 (= enumeração exaustiva 2⁸ × LP racional) | `otimo` | `aceito_otimo` | 12.7 | syn-fc: 0↑/1↓; syn-ter: 1↑/0↓ | completa_na_janela | 52 / 28 / 96 | 0.004 | 0.015 / 0.020 |
| I rampa inviável | inviável | `inviavel` | `sem_despacho` | — | — | — | 16 / 12 / 40 | 0.003 | 0.005 / 0.006 |
| I permanência inviável | inviável | `inviavel` | `sem_despacho` | — | — | — | 16 / 12 / 38 | 0.003 | 0.005 / 0.005 |
| J contínuo N = 8 | aceito | `otimo` | `aceito_otimo` | 2.625 | syn-ter: 1↑/0↓ | completa_na_janela | 65 / 32 / 105 | 0.004 | 0.024 / 0.033 |
| PEMFC instantânea (abstração) | R$ 0,33 (h·q + massas de evento) | `otimo` | `aceito_otimo` | 0.33 | syn-fc: 1↑/1↓ | completa_na_janela | 28 / 16 / 48 | 0.003 | 0.005 / 0.006 |
| J N = 32 (escala) | aceito (tempo) | `otimo` | `aceito_otimo` | 4.875 | syn-ter: 1↑/0↓ | completa_na_janela | 257 / 128 / 417 | 0.005 | 0.041 / 0.046 |
| J N = 96 (escala) | aceito (tempo) | `otimo` | `aceito_otimo` | 10.875 | syn-ter: 1↑/0↓ | completa_na_janela | 769 / 384 / 1249 | 0.010 | 0.113 / 0.125 |
