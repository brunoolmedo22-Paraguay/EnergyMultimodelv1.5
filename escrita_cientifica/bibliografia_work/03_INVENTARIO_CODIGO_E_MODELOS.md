# Inventário de código e modelos

## Corte auditado

- Repositório: https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5
- Ramo: main. SHA completo: `724d2351ebe4213ed3aa93675c137f7170d260bd`.
- Commit: 2026-11-11T16:27:39Z; merge do PR #23 (PEMFC/H2).
- Auditoria por GET em 12/11/2026 UTC, antes da pesquisa temática em lote. O cabeçalho consultado não foi atualizado silenciosamente depois.
- PR #24: aberto, draft, ramo `claude/stoic-meitner-2vs91m`, HEAD `15c0b1cde526e653abf31b2dbf0721e96610c950`, base `724d2351ebe4213ed3aa93675c137f7170d260bd`. Foram listados 76 arquivos e lidos exemplos de UI/Trama. Não se atribuem esses recursos a main.
- 112 arquivos Python tiveram símbolos indexados por AST. 53 relações científicas foram analisadas nesta matriz. Índice de símbolos não significa revisão semântica integral de cada função.
- Não houve execução do solver, testes ou casos. Contagens históricas em documentos/PRs são declarações do projeto, sem reprodução independente nesta missão.

## Arquitetura e versões

`models/` e `simulation/` contêm bancadas físicas. `h2_pemfc/` separa célula, stack, BoP, inversão potência–corrente e dinâmica. `seeds2/microgrid/` contém cadastro e persistência. `ems_integration/` é legado V1.6 (GA/GWO/NGO + SQP). `ems_v2/` contém contratos, MILP, MPC, rede e hierarquia. `integracao_v2/` faz a ponte com dados de cenários e modelos físicos. A interface exibe e configura; não deve ser confundida com o construtor matemático.

As dependências declaradas são Python/Streamlit, NumPy, pandas, SciPy e outras bibliotecas de interface/exportação. O arquivo separado do V2 fixa Pyomo 6.10.1 e highspy 1.15.1. A auditoria registra requisitos, sem afirmar que cada execução anterior usou exatamente esse ambiente. Streamlit está fixado em 1.66.1; NumPy 2.2.6; pandas 2.2.3; SciPy 1.15.3 no requirements consultado.

Persistência SQLite com cenários/versões append-only, rodadas, manifestos e dados associados aparece no código. Há suporte à reconfiguração de tecnologias previstas nos tipos/adaptadores, mas não foi demonstrada uma API irrestrita para acrescentar qualquer nova tecnologia sem desenvolvimento.

## Formulação do EMS V2

Índices: intervalos t=0,…,N−1 e fronteiras de energia k=0,…,N. Potências líquidas em kW, energias em kWh, duração h em horas, custos em reais. Variáveis: potência renovável/corte, Pc/Pd e z BESS, energia e, potência p/estado u de gerador, partida y/parada z de commitment, segmentos PWL, Pimp/Pexp e sentido do PCC. O contexto de cada variável evita confundir z BESS com z de parada.

Objetivo: soma dos termos operativos declarados (importação/exportação, H2, curtailment, throughput, eventos e demais parcelas autorizadas) e política terminal explícita. Não há objetivo único universal independente do cenário. J_oper planejado, custo realizado e custo futuro estimado são grandezas diferentes. Critérios de aceitação guardam terminação, gaps, integridade e auditoria. CONFIG_ANALITICA declara 60 s, uma thread, gaps relativos/absolutos zero e semente zero; outras configurações são possíveis e devem ser registradas.

O MPC sela o instante informacional, pede previsão validada, resolve a janela, aplica um bloco de ações e concilia o estado executado antes de continuar. O planejador resolve uma janela longa e caudas paramétricas a partir da fronteira curta, sem incluir novamente o custo do trecho curto. Modos terminais incluem ON/OFF, obrigação residual e, quando necessário, potência fixada. Horizontes são parâmetros de configuração; não se atribui um valor universal a todos os ensaios.

Em 1D, o interpolante por segmentos consecutivos pode ser não convexo e é representado por binárias. Em 2D, a formulação é uma envoltória inferior, aceita após verificação convexa amostral e validação nos centros; não é prova global. O sinal marginal local vem de diferenças entre reotimizações de cauda: lambda=−ΔV/ΔE. Não é preço dual diretamente retornado pelo solver.

## Diferenças tecnológicas decisivas

FV: bancada oferece proporcional, NOCT/eficiência e SDM. A ponte V2 usa NOCT/eficiência, GHI=POA e eficiência de conversão declarada. Bateria: bancada elétrica Tremblay/2RC; despacho usa modelo energético. Eólica: curvas, densidade e limites; quantidade multiplica a potência sem estela. Térmica: bancada agrega CVU e eventos, mas geração despachável é bloqueada na integração V2. H2: consumo é contabilizado, sem tanque M18 no núcleo auditado. PCC é energético agregado, sem rede AC/EMT.

O CSV Horizon do projeto registra rampa de subida 2 kW/s e descida 3,5 kW/s. O manual externo não foi recuperado. ON e 30 kW como estado anterior da embarcação são decisões do protocolo, não configuração persistida confirmada nesta auditoria. O futuro cenário CT-046 é independente do perfil B1 já implementado. A massa disponível de H2 deve ser documentada no caso naval pertinente.

## Procedência esclarecida da PEMFC

A implementação e identificação paramétrica próprias estão publicadas em REF0369. A formulação-base é Altıntaş–Ertan (REF0358); o código auditado incorpora os coeficientes-base documentados no artigo ENCOM. O equivalente Horizon é uma adaptação posterior. B1 e CT-046 são contextos independentes, sem inconsistência identificada no código.

## Mapa detalhado

### MOD0001 — FV: diodo único

`models/single_diode.py` · `sdm_residual` · linhas 72-82. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/single_diode.py#L72).

I = IL − I0[exp((V+I Rs)/a)−1] − (V+I Rs)/Rsh

Unidades: A, V, ohm. Hipóteses: Modelo implícito de um diodo, sem mismatch.

Fontes: REF0319; REF0113. Relação: Estrutura equivalente; origem declarada no código. Observação: Texto De Soto e sua errata ainda não cotejados integralmente.

### MOD0002 — FV: solução I–V

`models/single_diode.py` · `current_from_voltage` · linhas 145-160. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/single_diode.py#L145).

Solução por Lambert W, Brent ou Newton, conforme método declarado.

Unidades: A, V. Hipóteses: Regularização de exponenciais e fallback numérico.

Fontes: REF0138; REF0319. Relação: Adaptação numérica. Observação: A biblioteca SciPy não valida o ajuste físico.

### MOD0003 — FV: translação SDM

`simulation/solver.py` · `translate_params` · linhas 64-97. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/simulation/solver.py#L64).

a=a_ref T/T_ref; IL=(G/G_ref)[IL_ref+alpha_Isc(Tc−25)]; I0∝(T/T_ref)^3 exp(Eg_ref/kT_ref−Eg/kT); Rsh=Rsh_ref G_ref/G; Rs constante.

Unidades: K, °C, W/m², A, ohm. Hipóteses: G limitado inferiormente; Eg depende de T.

Fontes: REF0319; REF0320. Relação: Fonte direta declarada; adaptação. Observação: Errata localizada; efeito matemático não verificado.

### MOD0004 — FV: extração SDM

`simulation/solver.py` · `extract_sdm_params` · linhas 161-215. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/simulation/solver.py#L161).

least_squares de cinco resíduos: curto, circuito aberto, MPP, dP/dV=0 e beta_Voc por diferença finita.

Unidades: A, V, %/°C. Hipóteses: Log-escalas I0/Rsh, limites físicos e tentativas de ajuste.

Fontes: REF0319; REF0138. Relação: Adaptação compatível. Observação: Não é reprodução literal de algoritmo da publicação.

### MOD0005 — FV: temperatura NOCT

`models/temperature_model.py` · `cell_temperature_noct` · linhas 30-51. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/temperature_model.py#L30).

Tc = Tamb + (NOCT−20) G/800.

Unidades: °C, W/m². Hipóteses: Aproximação empírica; sem dinâmica térmica.

Fontes: REF0125; REF0113. Relação: Apoio indireto. Observação: Faiman é contraste de modelo, não fonte exata da fórmula NOCT.

### MOD0006 — FV: temperatura Sandia

`models/temperature_model.py` · `cell_temperature_sandia` · linhas 54-68. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/temperature_model.py#L54).

Tm = Tamb + G exp(a+b ws); Tc=Tm+(G/1000) ΔT.

Unidades: °C, m/s, W/m². Hipóteses: a,b,ΔT dependem da montagem.

Fontes: REF0123. Relação: Fonte direta declarada e equação compatível. Observação: Função disponível; não é o modelo fixado pela ponte V2.

### MOD0007 — FV: proporcional

`simulation/multimodel.py` · `simulate_irradiance_model` · linhas 301-324. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/simulation/multimodel.py#L301).

P = P_STC G_ef/G_ref Ns Np.

Unidades: W. Hipóteses: Eficiência STC constante.

Fontes: REF0113. Relação: Apoio metodológico. Observação: Modelo simplificado da bancada; não inclui temperatura.

### MOD0008 — FV: NOCT e eficiência

`simulation/multimodel.py` · `simulate_noct_efficiency_model` · linhas 327-361. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/simulation/multimodel.py#L327).

P = eta_STC max(0,1+gamma(Tc−25)) G_ef A Ns Np.

Unidades: W. Hipóteses: Exige temperatura completa; perdas por sujeira.

Fontes: REF0125; REF0113. Relação: Adaptação de potência corrigida por temperatura. Observação: Não representa curva I–V nem um inversor.

### MOD0009 — FV: modelo usado no V2

`integracao_v2/renovaveis.py` · `derivar_fv` · linhas 165-216. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/integracao_v2/renovaveis.py#L165).

P_barra,k = eta_conv média_j[P_NOCT(GHI_kj,Tamb_kj)]/1000.

Unidades: kW, W/m². Hipóteses: GHI tratada como irradiância no plano; sem transposição; eta constante.

Fontes: REF0113; REF0125. Relação: Adaptação explicitamente declarada. Observação: Não atribuir ao despacho o SDM da bancada. Sem MPPT, clipping de inversor, sombras ou mismatch.

### MOD0010 — Eólica: ar úmido

`models/wind_model.py` · `calculate_air_density` · linhas 208-247. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/wind_model.py#L208).

rho = pd/(Rd T)+pv/(Rv T), pv=RH es(T); es=6,1121 exp[(18,678−Tc/234,5)Tc/(257,14+Tc)].

Unidades: kg/m³, K, hPa. Hipóteses: Fallback de densidade identificado; dados inválidos tratados conforme schema.

Fontes: REF0132. Relação: Aproximação compatível; versão de coeficientes pendente. Observação: Buck 1981 não confirma sozinho a revisão exata desses coeficientes.

### MOD0011 — Eólica: curva estrita

`models/wind_model.py` · `_strict_power` · linhas 348-369. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/wind_model.py#L348).

v_eq = v (rho/rho_ref)^(1/3); P = interpolante da curva documentada, com cut-in/out sobre v real.

Unidades: m/s, kW. Hipóteses: Domínio real e equivalente verificados; sem extrapolação.

Fontes: REF0328; REF0366; REF0367. Relação: Apoio metodológico e fontes por equipamento. Observação: A origem e fronteira de cada tabela de equipamento precisam ser verificadas individualmente.

### MOD0012 — Eólica: tabela de densidade

`models/wind_model.py` · `_power_from_manufacturer_density_table` · linhas 256-284. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/wind_model.py#L256).

Interpolação por velocidade e entre curvas de diferentes densidades.

Unidades: m/s, kg/m³, kW. Hipóteses: Preserva tabelas de fabricante para o equipamento aplicável.

Fontes: REF0328. Relação: Adaptação compatível. Observação: Documentação Nordex citada no catálogo não foi recuperada nesta missão.

### MOD0013 — Eólica: parque e perdas

`models/wind_model.py` · `run_wind_model` · linhas 372-510. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/wind_model.py#L372).

P_total = n P_unidade (1−perda_opcional); E = Σ P Δt.

Unidades: kW, kWh. Hipóteses: Sem modelo de estela; multiplicação do número de turbinas.

Fontes: REF0328. Relação: Modelo de curva compatível. Observação: Não atribuir Jensen/Park/Werle ao cálculo examinado; perda genérica opcional não substitui wake.

### MOD0014 — Bateria: Tremblay

`models/battery_model.py` · `_tremblay_voltage` · linhas 142-161. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/battery_model.py#L142).

V = E0 − Ri − K Q/(Q−it) it − K Q/(Q−it) i* + A exp(−B it), com ramo específico para carga.

Unidades: V, A, Ah. Hipóteses: Corrente positiva descarga; filtros e denominadores regularizados.

Fontes: REF0352; REF0126. Relação: Fonte direta e adaptação numérica. Observação: Clip de tensão e estados é decisão do código; não transfere validação experimental.

### MOD0015 — Bateria: circuito 2RC

`models/battery_model.py` · `simulate_2rc` · linhas 262-351. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/battery_model.py#L262).

V=OCV(SOC)−IR0−V1−V2; Vj+=h(I/Cj−Vj/(Rj Cj)); SOC+=−Ih/(3600Q).

Unidades: V, A, F, ohm, s. Hipóteses: Euler explícito; subpassos; OCV polinomial grau 6; parâmetros interpolados.

Fontes: REF0147. Relação: Fonte direta: 13 linhas R1/C1/R2/C2 reproduzidas. Observação: Tabela 3 tem incompatibilidade tau2 ≠ R2 C2 em SOC 0,9; ver conferência própria.

### MOD0016 — Bateria: parâmetros 2RC

`models/battery_model.py` · `RC_SOC` · linhas 68-68. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/battery_model.py#L68).

Tabela de 13 níveis SOC; C1 escalado por 10³, C2 por 10⁴.

Unidades: F, ohm, fração. Hipóteses: OCV/R0 têm origem gráfica/protótipo; quatro parâmetros RC tabulados conferidos.

Fontes: REF0147. Relação: Correspondência exata dos quatro parâmetros tabulados. Observação: Não confundir correspondência de tabela com ausência de inconsistência no paper.

### MOD0017 — BESS no MILP

`ems_v2/milp/modelo.py` · `construir_modelo` · linhas 57-200. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/milp/modelo.py#L57).

e_(t+1)=alpha e_t+h(eta_c Pc−Pd/eta_d); C s_min ≤ e ≤ C s_max; e0 declarado.

Unidades: kW, kWh, h. Hipóteses: alpha=1 ou exp(−lambda h); sem tensão, temperatura ou SOH.

Fontes: REF0156; REF0349. Relação: Equação energética equivalente. Observação: Não é o modelo elétrico 2RC/Tremblay; throughput não é envelhecimento físico.

### MOD0018 — BESS: exclusividade

`ems_v2/milp/modelo.py` · `construir_modelo` · linhas 57-200. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/milp/modelo.py#L57).

0≤Pc≤a Pc_max z; 0≤Pd≤a Pd_max(1−z), z binária.

Unidades: kW. Hipóteses: Cotas físicas por dispositivo e disponibilidade.

Fontes: REF0312; REF0156. Relação: Formulação MILP equivalente. Observação: Exclusividade não implica modelo de perdas dependentes de carga.

### MOD0019 — PEMFC: Nernst

`h2_pemfc/models/pemfc_model.py` · `PEMFCModel.nernst_voltage` · linhas 27-38. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/h2_pemfc/models/pemfc_model.py#L27).

E=E0−0,00085(T−Tref)+(RT/2F) ln[pH2 sqrt(0,21 pair)/(pH2O sqrt(pair))].

Unidades: V/célula, K, atm. Hipóteses: pH2 e pH2O constantes no perfil.

Fontes: REF0369; REF0358; REF0152; REF0341. Relação: Implementação própria publicada, baseada em Altıntaş–Ertan; forma global documentada no ENCOM.. Observação: O cancelamento de pair nesta expressão permanece uma propriedade do código; o artigo próprio descreve a identificação conjunta e o efeito de pressão. Cotejo literal da expressão original OTEKON é complementar.

### MOD0020 — PEMFC: ativação

`h2_pemfc/models/pemfc_model.py` · `PEMFCModel.activation_overpotential` · linhas 45-63. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/h2_pemfc/models/pemfc_model.py#L45).

Vact=max[−(xi1+xi2 T+xi3 T ln(1000j_safe)+xi4 T ln(CO2)),0].

Unidades: V, A/cm², mA/cm². Hipóteses: j_safe≥0,01; coeficientes efetivos identificados em conjunto e publicados na Tabela II de REF0369.

Fontes: REF0369; REF0358; REF0151. Relação: Quatro coeficientes de ativação coincidem ao arredondamento publicado com a Tabela II de Chavez et al.. Observação: Citar Chavez et al. para a identificação; Altıntaş–Ertan fundamenta a formulação-base. Não apresentar os coeficientes como transcrição literal de OTEKON.

### MOD0021 — PEMFC: perdas ôhmicas

`h2_pemfc/models/pemfc_model.py` · `PEMFCModel.membrane_resistance` · linhas 85-87. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/h2_pemfc/models/pemfc_model.py#L85).

sigma=F² DH CH/(RT); Rmem=tm/sigma; Vohm=j Rmem.

Unidades: S/cm, ohm cm². Hipóteses: Fechamento efetivo do projeto; Rmem,ref e expoente nR identificados e publicados em REF0369.

Fontes: REF0369; REF0358; REF0151. Relação: Parâmetros Rmem,ref/nR conferidos com a Tabela II do artigo próprio.. Observação: O artigo ENCOM documenta a identificação; não expande todas as correlações eletroquímicas da fonte OTEKON.

### MOD0022 — PEMFC: concentração

`h2_pemfc/models/pemfc_model.py` · `PEMFCModel.concentration_overpotential` · linhas 100-105. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/h2_pemfc/models/pemfc_model.py#L100).

Vconc=max(a_ref+a_T(T−Tref),0) exp(b j).

Unidades: V, A/cm². Hipóteses: Coeficientes aref, aT e b identificados por mínimos quadrados e publicados na Tabela II de REF0369.

Fontes: REF0369; REF0358; REF0152. Relação: Três coeficientes conferidos com a Tabela II ao arredondamento publicado.. Observação: A evidência pertence à base própria; o perfil equivalente Horizon é uma adaptação posterior.

### MOD0023 — PEMFC: potência e eficiência

`h2_pemfc/models/pemfc_model.py` · `PEMFCModel.stack_power` · linhas 133-136. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/h2_pemfc/models/pemfc_model.py#L133).

P=N Vcell j A; Vcell=max(E−Vact−Vohm−Vconc,0).

Unidades: W, V, A. Hipóteses: Escalonamento por número de células e área.

Fontes: REF0369; REF0358; REF0359. Relação: Eqs. (2)–(3) do artigo próprio e geometria-base A=232 cm², N=41 documentadas.. Observação: N=41 e A=232 cm² pertencem à reconstrução-base do artigo próprio; a geometria do equivalente de 65 kW é outra configuração.

### MOD0024 — PEMFC: eficiência de referência

`h2_pemfc/models/pemfc_model.py` · `PEMFCModel.efficiency_percent` · linhas 138-141. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/h2_pemfc/models/pemfc_model.py#L138).

eta_ref = 100 Uf Vcell/E0.

Unidades: %. Hipóteses: Definição publicada na Eq. (4) de REF0369; Uf identificado pela escala de eficiência.

Fontes: REF0369; REF0358. Relação: Equação equivalente à publicação própria; N=41 confirmado e Uf aproximadamente 0,6962.. Observação: Preservar valores de máquina do código e valores resumidos do artigo; não confundir eficiência de referência com eficiência líquida sobre H2 suprido.

### MOD0025 — H2: lei de Faraday

`h2_pemfc/balance_of_plant/hydrogen.py` · `HydrogenConsumptionModel.evaluate` · linhas 21-47. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/h2_pemfc/balance_of_plant/hydrogen.py#L21).

nH2=N I/(2F); m_suprida=nH2 M_H2/Uf; kg/h=3600 kg/s; Pquim=mdot PCI.

Unidades: mol/s, kg/h, kW. Hipóteses: Utilização, PCI e constantes declarados.

Fontes: REF0151; REF0152. Relação: Equação fisicamente compatível; adaptação de sistema. Observação: Separar consumo eletroquímico, suprimento e purgas; sem atribuir perdas a uma fonte não lida.

### MOD0026 — PEMFC: stack equivalente

`h2_pemfc/models/equivalent_65kw_stack.py` · `Equivalent65kWHorizonStackModel` · linhas 99-326. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/h2_pemfc/models/equivalent_65kw_stack.py#L99).

Modelo de célula + geometria 210 células/300 cm² e restrições nominais.

Unidades: kW, V, A. Hipóteses: Adaptação posterior: base própria Chavez/Altıntaş–Ertan, dados equivalentes Chen e limites Horizon.

Fontes: REF0369; REF0358; REF0359; REF0360. Relação: Adaptação justificada no repositório; verificação externa incompleta. Observação: Área ativa assumida e calibração não constituem identificação experimental do Horizon.

### MOD0027 — PEMFC: balance of plant

`h2_pemfc/models/equivalent_65kw_system.py` · `Equivalent65kWHorizonSystemModel` · linhas 29-190. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/h2_pemfc/models/equivalent_65kw_system.py#L29).

P_liquida = conversão CC/CC da potência bruta − consumo auxiliar modelado.

Unidades: kW, kg/h. Hipóteses: Auxiliares calibrados e condições de operação declaradas.

Fontes: REF0152; REF0360. Relação: Adaptação de sistema. Observação: Distinguir stack de sistema e potência nominal/efetivamente entregue.

### MOD0028 — PEMFC: curva para EMS

`integracao_v2/curva_h2.py` · `CurvaH2` · linhas 132-168. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/integracao_v2/curva_h2.py#L132).

q_hat(P) = interpolante linear dos vértices (kW líquidos, kg/h H2 suprido); fora do domínio ⇒ erro.

Unidades: kW, kg/h. Hipóteses: Pontos vêm da inversão do modelo físico; certificação B04 interna.

Fontes: REF0369; REF0083; REF0359. Relação: Aproximação PWL do modelo próprio. Observação: B04 não equivale a validação em bancada real.

### MOD0029 — PEMFC: PWL no MILP

`ems_v2/milp/modelo.py` · `construir_modelo` · linhas 57-200. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/milp/modelo.py#L57).

Σ delta_s=u; 0≤theta_s≤delta_s; p=Σ[P_s delta_s+ΔP_s theta_s]; q=Σ[Q_s delta_s+ΔQ_s theta_s].

Unidades: kW, kg/h. Hipóteses: Segmentos consecutivos; OFF não liga artificialmente a (0,0).

Fontes: REF0083; REF0312. Relação: Formulação MILP equivalente. Observação: Curva pode ser não convexa; relaxação convexa global não é substituto exato.

### MOD0030 — PEMFC: rampas e estados

`h2_pemfc/models/equivalent_65kw_dynamic.py` · `Equivalent65kWHorizonDynamicModel` · linhas 136-567. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/h2_pemfc/models/equivalent_65kw_dynamic.py#L136).

Estado OFF/STARTUP/IDLE/RUN/SHUTDOWN e limites de variação por segundo.

Unidades: kW/s, s. Hipóteses: CSV do projeto: subida 2 kW/s, descida 3,5 kW/s; condições de partida.

Fontes: REF0360; REF0270. Relação: Manual alegado e hipóteses próprias. Observação: Manual não recuperado. 120 kW/min é conversão da rampa de subida, não potência mínima.

### MOD0031 — PEMFC: massa por evento

`integracao_v2/pemfc_dinamica.py` · `massas_eventos` · linhas 196-205. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/integracao_v2/pemfc_dinamica.py#L196).

m_SU=max(0,max delta_SU(P)); m_SD=max delta_SD(P), integrais dinâmicas adicionais à q_hat(P)Δ.

Unidades: kg/evento. Hipóteses: Evita dupla contagem entre regime e transientes.

Fontes: REF0270. Relação: Derivação própria; apoio indireto sobre transientes. Observação: Ensaios de outro equipamento não fornecem estas massas. Apresentar a derivação e a integral do modelo do projeto.

### MOD0032 — Térmica: bancada

`models/thermal_model.py` · `evaluate_thermal_dispatch` · linhas 214-342. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/models/thermal_model.py#L214).

P_alvo=max(P_req,inflex); P_ent=min(P_alvo,Pmax); custo=CVU E+startup por evento.

Unidades: MW, MWh, R$/MWh. Hipóteses: Rampas sinalizam violações; não simulam combustão.

Fontes: REF0117. Relação: Modelo econômico agregado. Observação: CVU do catálogo é preset acadêmico editável, não preço oficial.

### MOD0033 — Térmica: V2

`integracao_v2/preflight.py` · `NAO_REPRESENTAVEL` · linhas 67-70. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/integracao_v2/preflight.py#L67).

Térmica despachável bloqueada: M19/CVU não implementado no núcleo integrado.

Unidades: Não aplicável. Hipóteses: Separação explícita de capacidade legada e V2.

Fontes: REF0312. Relação: Lacuna implementacional documentada. Observação: Não afirmar que toda a bancada térmica é otimizada pelo V2.

### MOD0034 — PCC: intercâmbio

`ems_v2/milp/modelo_3c3.py` · `construir_modelo_3c3` · linhas 84-137. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/milp/modelo_3c3.py#L84).

Σ ger+Σ(Pd−Pc)+Pimp−Pexp=Σ carga−corte+descarte; sentidos mutuamente exclusivos.

Unidades: kW. Hipóteses: PCC agregado, sem fluxo AC e sem tensão/frequência.

Fontes: REF0156; REF0349. Relação: Modelo energético equivalente. Observação: Não comprova estabilidade elétrica ou atendimento a limites de tensão.

### MOD0035 — PCC: custo

`ems_v2/milp/modelo_3c3.py` · `construir_modelo_3c3` · linhas 84-137. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/milp/modelo_3c3.py#L84).

J_rede = h Σ(cimp Pimp−cexp Pexp).

Unidades: R$, R$/kWh. Hipóteses: Perfis tarifários por instante de emissão; só termos declarados.

Fontes: REF0363; REF0364; REF0136. Relação: Adaptação de insumo oficial. Observação: Não equivale a fatura completa: cobrança de demanda, tributos e encargos precisam de escopo explícito.

### MOD0036 — MILP: commitment

`ems_v2/milp/modelo_3c1.py` · `construir_modelo_3c1` · linhas 44-149. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/milp/modelo_3c1.py#L44).

u_t−u_(t−1)=y_t−z_t; y+z≤1; Pmin u≤p≤Pmax u; u≤a.

Unidades: binário, kW. Hipóteses: Estados anteriores declarados; transições não representáveis bloqueadas.

Fontes: REF0117; REF0349. Relação: Equação equivalente; origem direta não demonstrada. Observação: Fonte fundamenta formulação, não certifica adequação de parâmetros.

### MOD0037 — MILP: rampas

`ems_v2/milp/modelo_3c1.py` · `construir_modelo_3c1` · linhas 44-149. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/milp/modelo_3c1.py#L44).

p_t−p_prev≤Rup Δ u_prev+Sup y; p_prev−p_t≤Rdown Δ u_t+Sdown z.

Unidades: kW/intervalo. Hipóteses: Conversão de unidades e limites de partida/parada.

Fontes: REF0117. Relação: Estrutura equivalente. Observação: Duração do intervalo influencia representabilidade de transientes.

### MOD0038 — MILP: permanência

`ems_v2/milp/modelo_3c1.py` · `construir_modelo_3c1` · linhas 44-149. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/milp/modelo_3c1.py#L44).

Σ y_j≤u_t em janela U; Σ z_j≤1−u_t em D; obrigação herdada e política terminal.

Unidades: intervalos, s. Hipóteses: Tempos discretizados e memória entre janelas.

Fontes: REF0117; REF0158. Relação: Equação equivalente; adaptação temporal. Observação: Tempos mínimos não são parâmetros universais; dependem do cenário.

### MOD0039 — MPC: ciclo causal

`ems_v2/mpc/orquestrador.py` · `ControladorMPC.decidir` · linhas 323-416. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/mpc/orquestrador.py#L323).

Corte informacional τk → previsão validada → resolver janela → aplicar m_k ações → observar/conciliar estado executado.

Unidades: UTC, intervalos. Hipóteses: Não transporta o estado terminal previsto como se fosse executado.

Fontes: REF0349; REF0365. Relação: MPC equivalente com contratos próprios. Observação: Planta algébrica offline na integração; não afirmar controle físico online.

### MOD0040 — MPC: continuidade

`ems_v2/mpc/janela.py` · `montar_entrada_janela` · linhas 55-84. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/mpc/janela.py#L55).

Inicialização da janela recebe energia e memória executadas; previsão cobre N_k intervalos.

Unidades: kWh, kW, s. Hipóteses: Limites de missão e consistência de UID/malha.

Fontes: REF0365; REF0349. Relação: Adaptação de horizonte recedente. Observação: Verificações estáticas não substituem reprodução de uma rodada.

### MOD0041 — Hierarquia: custo de continuação

`ems_v2/hierarquia/planejador.py` · `Planejador3C4` · linhas 200-688. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/hierarquia/planejador.py#L200).

V_tail(E,sigma)=min J_cauda, da fronteira da janela curta até fim longo, com mesmo termo terminal longo.

Unidades: R$, kWh. Hipóteses: Cada ponto requer solução ótima auditada; sem dupla contagem da janela curta.

Fontes: REF0338; REF0365; REF0216. Relação: Compatibilidade conceitual; derivação própria. Observação: Não é SDDP, ADP aprendido, decomposição dual ou preço sombra extraído do solver.

### MOD0042 — Hierarquia: sensibilidade local

`ems_v2/hierarquia/planejador.py` · `Planejador3C4._sinal_local` · linhas 387-434. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/hierarquia/planejador.py#L387).

lambda_b = −[V(E_hi)−V(E_lo)]/(E_hi−E_lo); V_hat=Vref−Σ lambda_b(E_b−Eref_b).

Unidades: R$/kWh, R$. Hipóteses: Diferença central ou unilateral no limite, modo fixo e domínio local.

Fontes: REF0338; REF0365. Relação: Adaptação por reotimizações paramétricas. Observação: Não denominar lambda preço dual do MILP; mudança de modo pode gerar não suavidade.

### MOD0043 — Hierarquia: 1D/2D

`ems_v2/milp/modelo_3c4.py` · `_valor_por_modos` · linhas 110-169. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/milp/modelo_3c4.py#L110).

1D: segmentos consecutivos binários; 2D: min Σ lambda_j Vj, Σ lambda=1, E=Σ lambda_j Ej, por modo.

Unidades: R$, kWh. Hipóteses: 0–2 bancos; 2D usa envoltória inferior após consistência convexa amostral.

Fontes: REF0083; REF0365. Relação: Formulação exata do aproximante, não da função verdadeira. Observação: Convexidade em grade/centros não é prova de convexidade global nem garantia de erro em todo o domínio.

### MOD0044 — Hierarquia: alternativas terminais

`ems_v2/milp/modelo_3c4.py` · `construir_modelo_3c4` · linhas 67-107. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/milp/modelo_3c4.py#L67).

Phi=−Σ lambda E_N; energia mínima dura; referência branda rho Σ max(0,Eref−E_N); ou sinal PWL.

Unidades: R$, kWh. Hipóteses: Tipo terminal declarado; custo total J=J_oper+Phi.

Fontes: REF0158; REF0365. Relação: Equações compatíveis; políticas próprias. Observação: Não somar custo futuro estimado ao custo realizado da missão como se fosse desembolso.

### MOD0045 — Solver: configuração

`ems_v2/milp/config.py` · `ConfiguracaoSolver` · linhas 23-29. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/milp/config.py#L23).

time_limit, threads, rel_gap, abs_gap, semente e opções explícitas.

Unidades: s, fração, R$. Hipóteses: Config analítica: 60 s, 1 thread, gaps 0, semente 0; parâmetros alteráveis.

Fontes: REF0111; REF0356. Relação: Ferramentas primárias identificadas. Observação: Versões do requirements não provam ambiente de toda rodada; guardar metadados reais.

### MOD0046 — Auditoria algébrica

`ems_v2/audit.py` · `Tolerancias` · linhas 31-46. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/audit.py#L31).

Potência: 1e−5+1e−7 escala; energia: 1e−6+1e−8 C; custo: 1e−4+1e−7 escala; binário 1e−6.

Unidades: kW, kWh, R$. Hipóteses: Tolerâncias provisórias e separadas por grandeza.

Fontes: REF0354; REF0142. Relação: Método de verificação próprio. Observação: Aceitação algébrica difere de aproximação física e de validação experimental.

### MOD0047 — Arredondamento de energia

`ems_v2/ponte/execucao.py` · `projecao_numerica_energia` · linhas 271-279. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/ponte/execucao.py#L271).

epsilon=min(tolE,16·2^−53·S); projeção no limite apenas dentro da margem de arredondamento.

Unidades: kWh. Hipóteses: Projeção registrada, reconstruível; não amplia domínio físico.

Fontes: REF0139; REF0354. Relação: Tratamento numérico próprio. Observação: Não descrever o executor como totalmente sem projeção: existe esta exceção explícita.

### MOD0048 — Plataforma: persistência

`seeds2/microgrid/store.py` · `MicrogridStore` · linhas 430-1348. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/seeds2/microgrid/store.py#L430).

SQLite, versões append-only, identidade imutável de rodada, manifestos e dados associados.

Unidades: IDs, versões, SHA256. Hipóteses: Migrações versionadas e concorrência otimista.

Fontes: REF0354; REF0141; REF0143. Relação: Arquitetura própria compatível com boas práticas. Observação: Hashes detectam alteração; não certificam fidelidade de modelos ou acesso completo aos insumos.

### MOD0049 — Plataforma: cadastro

`seeds2/microgrid/registry.py` · `MicrogridRegistry` · linhas 130-660. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/seeds2/microgrid/registry.py#L130).

Microrredes identificadas por UID; criação, duplicação, versões e resolução do armazenamento.

Unidades: UID. Hipóteses: Tipos e adaptadores suportados definidos no código.

Fontes: REF0355; REF0343; REF0353. Relação: Comparação arquitetural. Observação: Reconfigurável entre tipos suportados; plug-and-play arbitrário de novos dispositivos não demonstrado.

### MOD0050 — Dados: grade temporal

`ems_v2/series.py` · `alinhar_a_malha` · linhas 115-151. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/series.py#L115).

Séries por intervalos e fronteiras verificadas contra UTC e N/N+1; alinhamento exige cobertura.

Unidades: UTC, kW, kWh. Hipóteses: Sem reutilização silenciosa de dado de emissão futura.

Fontes: REF0142; REF0155. Relação: Processamento temporal próprio. Observação: Reamostragem não cria informação física e requer semântica média/instantânea.

### MOD0051 — Demanda: COPEL incorporada

`ems_integration/ponte.py` · `carga_copel` · linhas 80-83. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_integration/ponte.py#L80).

Leitura carga_copel_b1_{dia}.csv; conversor MATLAB seleciona COPEL, B1, Simulação 5 e interpola 96→1440 pontos por PCHIP.

Unidades: kW, min. Hipóteses: B1 é residencial; origem UUID no script, não CT-046 industrial.

Fontes: REF0364; REF0363. Relação: B1 implementado e CT-046 proposto são usos independentes, conforme esclarecimento do autor.. Observação: Nenhuma inconsistência identificada entre os perfis. CT-046 é uma futura microrrede, sem substituir ou reinterpretar o B1 existente.

### MOD0052 — Legado: GA/GWO/NGO

`ems_integration/despacho.py` · `despacho` · linhas 254-376. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_integration/despacho.py#L254).

Metaheurística produz ponto inicial; SQP refina parte contínua; enumeração de quantidades candidatas.

Unidades: kW, R$. Hipóteses: Backend V1.6 separado do EMS V2 MILP.

Fontes: REF0312. Relação: Capacidade legada; sem fonte original completa identificada. Observação: Não atribuir GA/GWO/NGO ao MILP V2. Bibliografia original do legado ainda deve ser vinculada.

### MOD0053 — H2: capacidade ausente

`ems_v2/capabilities.py` · `CAPACIDADES` · linhas 52-80. [Código fixado](https://github.com/brunoolmedo22-Paraguay/EnergyMultimodelv1.5/blob/724d2351ebe4213ed3aa93675c137f7170d260bd/ems_v2/capabilities.py#L52).

M18/estoque_h2 = nao_suportado; suprimento externo declarado.

Unidades: kg. Hipóteses: Consumo calculado sem dinâmica de tanque na integração auditada.

Fontes: REF0359; REF0324. Relação: Lacuna de escopo. Observação: Não concluir autonomia em H2 de uma embarcação sem orçamento de massa independente ou tanque modelado.
