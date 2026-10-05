# Documentação matemática dos modelos

## 1. Convenções comuns

Todos os modelos recebem o mesmo perfil temporal e a mesma configuração:

| Símbolo | Descrição | Unidade |
|---|---|---|
| `G` | irradiância fornecida na entrada | W/m² |
| `L` | fração de perdas ópticas | – |
| `G_ef = G(1-L)` | irradiância efetiva | W/m² |
| `Tamb` | temperatura ambiente | °C |
| `N = Ns·Np` | quantidade total de módulos | – |
| `A` | área bruta de um módulo | m² |
| `P_STC` | potência nominal do módulo | W |
| `G_STC` | irradiância de referência, 1000 W/m² | W/m² |
| `T_STC` | temperatura de célula de referência, 25 °C | °C |

A potência do arranjo é a potência de um módulo multiplicada por `N`.

O CSV é processado em janelas de 120 minutos. Para estudos sintéticos, a mesma
resolução de um minuto pode ser usada em uma janela de 120 minutos ou em um dia
completo de 1.440 amostras. A opção de irradiância perfeita usa apenas a
envoltória solar suave, sem perturbações aleatórias.

## 2. Modelo 1 — irradiância

O modelo supõe uma relação linear entre irradiância e potência:

```text
P_mod,1(t) = P_STC · G_ef(t) / G_STC
P_arr,1(t) = N · P_mod,1(t)
```

A eficiência usada apenas como indicador é constante:

```text
eta_STC = P_STC / (A · G_STC)
```

### Entradas mínimas

- timestamp;
- irradiância;
- potência nominal e quantidade de módulos.

### Limitação principal

Não representa perdas térmicas nem a não linearidade elétrica do módulo.

## 3. Modelo 2 — NOCT + eficiência

### 3.1 Temperatura de célula

```text
Tc(t) = Tamb(t) + [(NOCT - 20 °C) / 800 W/m²] · G_ef(t)
```

### 3.2 Eficiência dependente da temperatura

O coeficiente `gamma_Pmax` do datasheet é convertido de `%/°C` para `1/°C`:

```text
gamma = gamma_Pmax_pct / 100
eta(t) = eta_STC · [1 + gamma · (Tc(t) - T_STC)]
```

A potência resulta da eficiência e da área:

```text
P_mod,2(t) = eta(t) · G_ef(t) · A
P_arr,2(t) = N · P_mod,2(t)
```

### Entradas mínimas

- timestamp;
- irradiância;
- temperatura ambiente;
- P_STC, área, NOCT e gamma_Pmax do datasheet.

## 4. Modelo 3 — Single Diode Model

O circuito equivalente é descrito por:

```text
I = IL - I0·[exp((V + I·Rs)/a) - 1] - (V + I·Rs)/Rsh
a = n·Ncélulas·k·Tc/q
```

Os parâmetros de referência são `IL_ref`, `I0_ref`, `Rs`, `Rsh_ref` e `n`.
Quando não estão publicados, são estimados do datasheet impondo:

1. `I(0) = Isc`;
2. `I(Voc) = 0`;
3. `I(Vmp) = Imp`;
4. `dP/dV = 0` no MPP;
5. coeficiente de temperatura de `Voc` do datasheet.

### 4.1 Translação para as condições de operação

O software utiliza a formulação de De Soto para transladar os parâmetros de
referência a cada `(G_ef, Tc)`. A temperatura de célula é calculada pelo mesmo
modelo NOCT usado no modelo intermediário.

### 4.2 Solução e MPP

A corrente implícita é resolvida por Lambert W. O ponto de máxima potência é
obtido por varredura inicial e refinamento por minimização acotada de `-P(V)`.
O arranjo assume MPPT ideal:

```text
P_arr,3(t) = N · Pmp_mod(t)
```

Para resultados elétricos do arranjo:

```text
Vmp_arr = Ns · Vmp_mod
Imp_arr = Np · Imp_mod
Voc_arr = Ns · Voc_mod
Isc_arr = Np · Isc_mod
```

## 5. Integração energética e KPIs

Para um passo de um minuto, `Δt = 1/60 h`:

```text
E = Σ P_arr(t) · Δt / 1000                  [kWh]
H = Σ G_ef(t) · Δt / 1000                  [kWh/m²]
Yf = E / P_instalada                        [kWh/kWp]
PR = Yf / H                                 [-]
eta_energética = E / (H · A_arranjo)        [-]
```

## 6. Lógica de disponibilidade

| Condição da entrada | Modelo 1 | Modelo 2 | Modelo 3 |
|---|---:|---:|---:|
| G e Tamb completas | executa | executa | executa |
| G completa e Tamb ausente/incompleta | executa | indisponível | indisponível |
| G ausente ou janela irregular | entrada rejeitada | entrada rejeitada | entrada rejeitada |

A aplicação não estima silenciosamente uma temperatura ausente. Essa escolha
mantém explícita a diferença entre dado medido/predito e dado inexistente.

## 7. Escopo da comparação

A comparação interna mostra a sensibilidade à complexidade do modelo. Ela não
estabelece qual modelo é mais exato. Para validação experimental, uma etapa
posterior deve comparar cada potência estimada com potência medida e calcular,
por exemplo, MAE, RMSE e viés.

O usuário pode escolher qualquer modelo disponível como referência. Para cada
outro modelo `m`, a diferença temporal apresentada é:

```text
ΔP_m(t) = [P_m(t) - P_ref(t)] / P_ref(t) · 100 %
```

O cálculo é omitido nos instantes em que a potência da referência é menor ou
igual a 1 W, evitando divisões numericamente instáveis durante a noite.

---

## 6. Modelo térmico operacional-econômico V1.2

O módulo térmico não representa a termodinâmica interna da planta. Sua fronteira é operacional e econômica.

### 6.1 Usina termelétrica de grande porte

```text
P_alvo(t) = max[P_solicitada(t), P_inflex(t)]
P_entregue(t) = min[P_alvo(t), Pmax]
C_var(t) = P_entregue(t) · Δt · CVU
```

São reportadas violações de inflexibilidade, Pmax, mínimo técnico e rampas opcionais.
A potência solicitada original é preservada para diagnóstico; a aplicação mostra separadamente o alvo contratual e a potência considerada para energia/custo.

### 6.2 Pequena unidade geradora

```text
P_entregue(t) = min[P_solicitada(t), Pmax]
E_não_atendida = Σ max[P_solicitada(t)-Pmax, 0] · Δt
C_total = Σ P_entregue(t) · Δt · CVU + N_partidas · C_partida
```

Não há inflexibilidade por padrão. O recurso é tratado como backup rápido e cada transição desligado → ligado é contabilizada como partida.

### 6.3 Fator de capacidade do período

```text
FC_período = E_entregue / (Pmax · T_analisado)
```

Esse indicador pertence ao horizonte analisado e não é uma propriedade fixa do equipamento.
