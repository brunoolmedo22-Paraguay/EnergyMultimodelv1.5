# Módulos Bateria e H₂ / PEMFC — Energy MultiModel V1.3

## 1. Bateria

O módulo de bateria foi portado para Python a partir dos dois protótipos MATLAB fornecidos ao projeto. Os arquivos originais foram mantidos em `reference_models/battery_matlab/` para rastreabilidade.

### Modelo 01 — Tremblay–Dessaint / Shepherd

Implementa o modelo dinâmico genérico de bateria usado no protótipo `Simulador_Interativo.m`.

Entradas principais:

- `timestamp`;
- `current_A`, com **corrente positiva para descarga** e **negativa para carga**;
- química/célula de referência;
- `Ns` células em série;
- `Np` strings em paralelo;
- SOC inicial.

Químicas parametrizadas conforme o script fornecido:

- Lead-Acid 12 V / 7,2 Ah;
- NiCd 1,2 V / 2,3 Ah;
- Li-Ion 3,3 V / 2,3 Ah;
- NiMH 1,2 V / 6,5 Ah.

O núcleo preserva a corrente filtrada `i*`, o termo exponencial e a integração coulômbica do protótipo.

### Modelo 03 — circuito equivalente de 2 RC

Porta o modelo de Zhang et al. (2017) implementado em `modelo2rc.m` para uma célula Li-Ion 18650 de 2,35 Ah. Usa:

- `OCV(SOC)` ajustada por polinômio de grau 6;
- `R0(SOC)`;
- dois ramos dinâmicos `R1-C1` e `R2-C2`;
- integração explícita de Euler;
- integração coulômbica do SOC.

A tensão de célula é calculada por:

```text
Vt = OCV(SOC) - I·R0 - VRC1 - VRC2
```

### Escalonamento do banco

As equações permanecem no nível de célula e a interface faz apenas o escalonamento elétrico:

```text
I_célula = I_banco / Np
V_banco  = Ns · V_célula
P_banco  = V_banco · I_banco
```

Esta versão ainda não modela temperatura, SOH, envelhecimento, balanceamento, limites do BMS ou conversor DC/DC.

---

## 2. H₂ / PEMFC

O módulo H₂ incorpora o núcleo do projeto `FC-PEM-66-KW-main` dentro de `h2_pemfc/`, sem depender da aplicação Streamlit original.

A cadeia preservada é:

```text
modelo eletroquímico
→ stack equivalente
→ balance of plant
→ inversão potência solicitada → corrente
→ dinâmica temporal / máquina de estados
```

### Entrada mínima do EMS

```csv
timestamp,P_FC_requested_kW
2026-08-03 13:00:00,10
2026-08-03 13:01:00,30
```

Colunas opcionais:

- `FC_enable`;
- `T_ambient_C`;
- `T_coolant_in_C`;
- `V_bus_V`.

### Saídas principais

- potência solicitada, dinâmica e entregue;
- déficit e excesso;
- estado operacional (`OFF`, `STARTUP`, `IDLE`, `RUN`, etc.);
- corrente e tensão do stack;
- potência bruta e líquida;
- consumo de H₂ em kg/h;
- consumo de ar;
- eficiência elétrica líquida baseada no PCI;
- calor rejeitado;
- flags e motivos de limitação.

### Status científico

O perfil integrado é o `EQUIVALENT_65KW_HORIZON_CONSTRAINED`: uma representação aproximada/restringida de um sistema Horizon da faixa de 65–66 kW, construída para estudos preliminares de EMS. Não equivale a uma validação experimental do equipamento físico instalado na embarcação.

Os documentos científicos originais do modelo foram preservados em `h2_pemfc/docs/`.
