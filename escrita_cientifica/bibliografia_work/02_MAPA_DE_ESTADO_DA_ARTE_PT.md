# Estado da arte e correspondência com a implementação
## Dossiê técnico da missão WORK-BIBLIO-SEEDS2-01

**Português do Brasil · corte em 12/11/2026 UTC.** Repositório: brunoolmedo22-Paraguay/EnergyMultimodelv1.5. Main fixada em 724d2351ebe4213ed3aa93675c137f7170d260bd. Este é um dossiê de auditoria e pesquisa, sem redação do manuscrito. Referências identificadas por REF têm a mesma chave nas matrizes, fichas e arquivos BibTeX/RIS. Os links nos identificadores apontam à fonte conferida.

## 1. Método, critérios e limitações de cobertura

A leitura inicial do repositório distinguiu bancadas físicas, legado V1.6, EMS V2 e ponte de integração. Equações, classes, dados e referências declaradas orientaram buscas por títulos e DOI e prospecção temática em inglês. Foram usados Crossref, DOAJ, busca web dirigida a editoras, repositórios e documentação primária, além das referências dos trabalhos selecionados. As estratégias originais para WoS e Scopus estão preservadas, mas as barreiras de acesso impediram sua execução nativa. ResearchGate foi usado somente para descoberta.

A deduplicação normaliza DOI e compara identidade por título/autores/ano. Preprints e publicações foram vinculados em famílias. Os 369 registros são um universo de descoberta, não um conjunto inteiramente pertinente; 165 receberam triagem focal e 121 foram priorizados. Os candidatos rejeitados e reservas continuam visíveis. As 95 arestas internas do grafo foram extraídas de relações DOI citante–citado depositadas nos metadados. Os 3.744 apontamentos externos são pistas, não documentos lidos nem candidatos já aprovados. A busca forward é parcial e não representa cobertura bibliométrica global.

F significa texto/primário disponível com leitura focal de trechos registrados; A significa resumo; M significa identidade bibliográfica. A existência de 34 itens F não significa 34 papers integralmente lidos página a página. Há documentos técnicos/dados nesse grupo. Das 30 fichas, 24 são F e seis A/M. As métricas cumprem o protocolo nas condições declaradas, com a meta aspiracional de 200–300 candidatos pertinentes ainda não demonstrada. Não se trata de revisão sistemática PRISMA, e a ausência de aviso editorial consultado não certifica ausência de retratação.

P0 indica origem matemática/documental alegada ou usada no código. P1 indica proximidade com as contribuições. P2 reúne fundamentos específicos, P3 ferramentas/reprodução, P4 contexto. As 10 P0 e 43 P1 têm prioridade de leitura, mas nem todas foram acessadas integralmente. Nenhum DOI foi criado por inferência. O manual Horizon não obtido ficou fora das exportações. A formulação-base OTEKON tem identidade corroborada; o artigo próprio ENCOM documenta a implementação e identificação efetivamente realizadas.

## 2. Plataformas: o que comparar e o que evitar

O conjunto abaixo oferece 16 comparadores. A comparação é funcional e limitada à publicação/versão consultada. Um recurso disponível atualmente não deve ser atribuído automaticamente a um artigo antigo. O objetivo é localizar o SEEDS2 entre ferramentas existentes e definir evidência de contribuição, e não classificar uma interface como superior por preferência visual.

| Plataforma / nível | Fonte | Escopo e diferença essencial |
| --- | --- | --- |
| PyPSA / F | REF0104 | Modelos de sistemas de potência e otimização multiperíodo. Rede elétrica e planejamento mais amplos; interface e contratos de MPC diferentes. |
| oemof / F | REF0355 | Grafo genérico de componentes/barramentos e ferramentas em camadas. Framework de construção de modelos, não a mesma aplicação ou controlador. |
| oemof.solph / M | REF0134 | Geração de modelos LP/MILP de sistemas energéticos. Não inferir da descrição de solph um EMS recedente completo. |
| Calliope / F | REF0353 | Modelos multiescala e separação dados–modelo. Escala espacial/planejamento não significa hierarquia temporal MPC. |
| ETHOS.FINE / F | REF0343 | Classes de componentes, Pyomo e persistência netCDF. Foco em avaliação/planejamento; contratos e instantes causais próprios do SEEDS2. |
| pandapower / F | REF0321 | Análises elétricas estáticas/quase-estáticas por elementos. Fluxo AC/curto-circuito não estão no núcleo energético examinado. |
| GridLAB-D / M | REF0105 | Ambiente aberto de simulação de sistemas de potência. Não é equivalente a um EMS MILP–MPC integrado. |
| REopt / A | REF0136 | Planejamento multitecnologia e custos/tarifas locais. Recursos da edição atual não podem ser atribuídos integralmente ao paper de 2014. |
| HOMER / M | REF0137 | Modelagem de sistemas híbridos para análise de projeto. Projeto e avaliação diferem da execução causal por janelas auditada. |
| pymgrid / F | REF0357 | Simulador, gerador de microrredes e baselines de controle. Versão consultada é preprint; previsão perfeita do benchmark precisa ser distinguida. |
| SpineOpt / M | REF0110 | Framework aberto e flexível de modelagem energética. MPC/funcionalidades atuais devem ser checados por versão, além do artigo. |
| OSeMOSYS / M | REF0135 | Sistema transparente de modelagem energética. Escala e propósito de planejamento diferem da bancada e do EMS causal. |
| EnergyScope TD / M | REF0108 | Planejamento regional multienergético com dias típicos. Agregação temporal e dimensionamento têm objetivo diferente do despacho recedente. |
| OpenEMS / F técnico | REF0361 | Plataforma com Edge, Backend, UI e APIs de componentes. Opera componentes reais; SEEDS2 V2 está em ensaio algébrico offline. |
| IESopt / M | REF0001 | Framework modular de otimização energética, conforme identidade bibliográfica. Necessária leitura integral antes de comparação de recursos e tempos. |
| Backbone aplicado a MPC / A | REF0292 | Controle econômico preditivo de aquecimento via framework energético. Dinâmica e demanda térmica não correspondem aos dois casos elétricos principais. |

### 2.1 Critérios que produzem uma comparação verificável

**Representação e extensibilidade.** Definir quais tipos de componentes podem ser cadastrados, quais contratos/adaptadores existem e qual desenvolvimento é necessário para uma tecnologia nova. Registry e catálogos permitem reconfiguração dentro de um domínio explícito. “Plug-and-play” irrestrito exigiria uma interface demonstrada para componentes externos. oemof e FINE oferecem precedentes de separação entre topologia, componentes e formulação (REF0355; REF0343).

**Reprodução de experimentos.** Verificar se um terceiro pode recuperar dados de entrada, cenário/versionamento, estado inicial, previsões por cutoff, configuração do solver e decisões efetivamente executadas. Hashes identificam conteúdo, mas não recuperam sozinhos um arquivo nem resolvem licença. As práticas de Wilson e os princípios FAIR orientam esses requisitos (REF0354; REF0141; REF0142; REF0143). O armazenamento append-only do SEEDS2 é um mecanismo favorável, ainda sujeito à verificação por rodada.

**Domínio físico e temporal.** PyPSA e pandapower incluem representações elétricas que não podem ser atribuídas ao balanço energético agregado do V2 (REF0104; REF0321). Calliope trata escalas de modelagem; isso não implica o mesmo mecanismo de coordenação temporal por MPC (REF0353). pymgrid aproxima a avaliação de controladores por arquiteturas reutilizáveis, mas o preprint e as condições de previsão de seu benchmark devem ser explicitados (REF0357).

**Duas contribuições equilibradas.** A arquitetura e a formulação do EMS precisam de descrições e evidências próprias. O artigo poderá relacioná-las pela reconfiguração dos mesmos casos e pela rastreabilidade das decisões, evitando uma primeira metade apenas ilustrativa e uma segunda metade exclusivamente matemática. Caderno/Folha/Trama do PR draft não são funcionalidades de main no corte adotado.

## 3. EMS hierárquico: famílias de métodos e precedentes

### 3.1 MILP, MPC e hierarquia são qualificadores diferentes

MILP descreve a classe do problema de otimização; MPC descreve o procedimento de resolver horizontes móveis e aplicar decisões com atualização de estado; hierarquia descreve a coordenação entre níveis/horizontes. Um sistema pode ter qualquer combinação. A palavra hierarchical no título de uma referência não prova que ela utiliza valor futuro, assim como a palavra MPC não garante causalidade das entradas de um benchmark.

No SEEDS2 V2, o MILP incorpora balanço agregado, limites energéticos, exclusividade de fluxos e decisões de operação. O MPC pede previsões compatíveis com o cutoff, aplica um bloco e reconcilia o estado executado. A hierarquia calcula informação de continuação além da fronteira curta. A redação deve descrever esses mecanismos separadamente e depois explicar seu acoplamento. O legado V1.6 utiliza outros algoritmos e não fundamenta a formulação atual.

| Família | Referência e evidência consultada | Relação e limite frente ao V2 |
| --- | --- | --- |
| MPC operacional de microrrede | REF0349, Parisio et al., A. Resumo primário. | Precedente central de otimização recedente com restrições; equações completas ainda pendentes. |
| Hierarquia temporal por estágios | REF0156, Fan et al., F. DAS/HAS/RTS. | Estrutura de coordenação comparável; problema e restrições elétricas não são os mesmos. |
| Dois níveis com objetivo econômico | REF0216, Vivas et al., A; REF0350, A. | Apoiam contraste entre tracking e coordenação econômica; não sustentam percentuais para SEEDS2. |
| MPC estocástico validado experimentalmente | REF0351, Polimeni et al., A. | Distinguir simulação própria de validação experimental dos autores. |
| Valor além do horizonte de previsão | REF0338, Aaslid et al., A. | Aproxima a questão econômica do armazenamento; formulação estocástica não equivale à cauda determinística. |
| Duas camadas H2–bateria robustas | REF0221, A. | Proximidade tecnológica e temporal; robustez não está demonstrada pelo determinismo do V2. |
| Controle naval modular e distribuído | REF0094, Kopka et al., A. | Resumo descreve decomposição dual e MPC com hardware de controle; V2 centralizado não reproduz essa arquitetura. |
| Teoria geral de MPC | REF0365, texto primário F. | Define função de valor, horizonte recedente e condições terminais; garantias dependem de hipóteses adicionais. |

### 3.2 Valor futuro: semântica, estados e aproximação

Uma função de continuação V(s) resume o custo ótimo do trecho posterior, condicionado ao estado na fronteira. Para ser coerente, o estado deve conter informação suficiente para as restrições futuras. No código examinado, energia armazenada é uma coordenada, mas ON/OFF, obrigação residual e potência anterior/fixada podem determinar modos distintos. Desconsiderar esses modos mistura trajetórias com viabilidades diferentes.

A hierarquia reotimiza caudas que começam na fronteira curta e terminam no fim do horizonte longo sob uma política terminal comum. O trecho curto não deve ser contado novamente. O problema curto usa J_oper + V_aprox(s_fronteira), e o custo realizado deve ser computado sobre ações aplicadas, sem somar o estimador V como se fosse uma despesa paga.

Em 1D, segmentos consecutivos e variáveis de seleção preservam um interpolante não convexo. Formulações PWL têm fundamentos em REF0083. Em 2D, a envoltória inferior e os testes amostrais de consistência convexa são uma escolha mais restritiva. Testar vértices/centros não prova convexidade global. Se uma função verdadeira não convexa for substituída por sua envoltória, o custo previsto pode ser otimista entre pontos. Deve-se documentar domínio, malha, modos aceitos/rejeitados e erro de interpolação.

O sinal local lambda=−[V(E_hi)−V(E_lo)]/[E_hi−E_lo] tem unidades monetárias por kWh e deriva de diferenças de reotimização. Não é automaticamente o multiplicador dual de uma restrição. Um sinal marginal local também não equivale a uma função de valor completa. O SEEDS2 não deve ser rotulado como SDDP, programação dinâmica aproximada aprendida ou RL apenas por utilizar informação futura; cada denominação requer os algoritmos correspondentes.

### 3.3 Níveis de garantia

Viabilidade matemática de um plano, auditoria numérica do executor, reconstrução da trajetória, adequação do modelo físico e validação experimental são perguntas diferentes. Solver com gap zero configurado não garante optimalidade se houver limite de tempo ou outra terminação. O relato deve informar status, incumbent/bound/gap aceito, tolerâncias físicas e eventual diagnóstico. A configuração analítica auditada declara 60 s, uma thread, semente zero e gaps alvo zero, mas cada experimento precisa do seu próprio manifesto.

REF0356 fundamenta o dual simplex usado no ecossistema HiGHS, sem constituir prova de cada modelo MILP. REF0111 fundamenta Pyomo. O artigo “Parallelizing the dual revised simplex method” não deve ser confundido com trabalhos de título semelhante de 2012. Dependências fixadas no repositório são evidência de intenção de ambiente, não verificação do ambiente de todas as rodadas históricas.

## 4. Modelos tecnológicos: origens e divergências

### 4.1 Fotovoltaica

A bancada contém modelo proporcional, correção térmica NOCT/eficiência e diodo único. A equação implícita SDM é I=IL−I0[exp((V+I Rs)/a)−1]−(V+I Rs)/Rsh. O código oferece Lambert W e métodos escalares Brent/Newton para solução, além de extração de cinco parâmetros por least_squares, com resíduos de curto, circuito aberto, MPP, derivada em MPP e beta_Voc por diferença finita. É necessário diferenciar a forma física do diodo, a transferência de parâmetros e o algoritmo particular de extração.

De Soto (REF0319) é a origem declarada da translação. A errata REF0320 foi identificada, sem acesso ao seu conteúdo. A documentação oficial pvlib calcparams_desoto foi consultada (REF0368), mas não substitui a conferência da publicação e da errata. SciPy (REF0138) fundamenta a ferramenta numérica, sem validar os parâmetros físicos. A API e a arquitetura do pvlib são comparadores (REF0113); sua citação não significa que o pacote é utilizado internamente pelo SEEDS2.

O modelo térmico Sandia implementado, Tm=Tamb+G exp(a+b v) e Tc=Tm+(G/1000)deltaT, tem correspondência com o relatório de King, Boyson e Kratochvil (REF0123). Entretanto, a ponte V2 executa NOCT/eficiência, trata GHI como POA e aplica eficiência de conversão declarada. Não foram identificados transposição, mismatch e inversor/MPPT detalhado nessa ponte. Essa é uma hipótese física material, principalmente se os casos forem descritos como instalações inclinadas reais.

### 4.2 Eólica

A geração usa interpolação de curvas e correção por densidade, com velocidade equivalente v_eq=v(rho/rho_ref)^(1/3), quando aplicável. Há curvas dependentes de densidade e checagem de domínio; limites de operação utilizam a velocidade real. A multiplicidade de turbinas multiplica a produção individual. Não foram encontrados modelos de estela Jensen/Park/Werle no trecho auditado. Não cabe acrescentar suas referências como se fundamentassem cálculo de wake já executado.

A ficha primária Vergnet GEV MP C 275 kW (REF0366), p. 7, fornece tabela de curva e condições de referência. Já curvas de pequenas turbinas obtidas de arquivo NREL/NatLabRockies são fonte arquivada (REF0367), com status de análise e necessidade de ensaio primário adicional. Valores negativos em baixa velocidade devem ser entendidos conforme a convenção do dado original, sem simples substituição silenciosa por uma curva ideal. A equação de pressão de saturação emprega coeficientes 18,678/234,5 e exige identificação da revisão específica de Buck; não se atribui automaticamente essa parametrização inteira ao artigo de 1981.

### 4.3 Bateria: circuito equivalente e energia de despacho

O modelo Tremblay–Dessaint (REF0352) combina termos de polarização, corrente filtrada e zona exponencial. A implementação acrescenta integração, regularizações e clips de SOC/tensão. O 2RC usa estados de polarização e tabelas dependentes de SOC de Zhang et al. (REF0147). Os parâmetros copiados foram comparados ponto a ponto com a Tabela 3, p. 8. O erro interno em tau2 não demonstra um erro de transcrição do código: os quatro parâmetros coincidem. Demonstra que a publicação de origem precisa de tratamento crítico.

Para SOC 0,9: R2=0,0433 ohm e C2=0,8196×10^4 F produzem 354,8868 s, contra 89,7116 s impressos. Para SOC 0,3: o produto é 80,6932 s, contra 86,1204 s. A planilha 05 contém os 13 pontos e os desvios. O script de conferência independente está incluído, exigindo somente os arquivos de entrada legitimamente obtidos nas localizações documentadas.

O BESS do MILP é outro modelo: e[t+1]=alpha[t]e[t]+h[t](eta_c Pc[t]−Pd[t]/eta_d), com limites e exclusividade. Ele não reproduz diretamente a tensão do circuito equivalente nem atualiza SOH por ciclagem. Uma penalidade de throughput declarada é custo agregado, não dinâmica física de envelhecimento; REF0159 ajuda a delimitar essa diferença. O executor possui tolerâncias e projeção numérica de escala epsilon=min(tol_E,16×2^−53×S), de modo que “nenhuma projeção de estado” seria uma descrição excessiva.

### 4.4 PEMFC/H2: fonte, curva equivalente e dinâmica

A formulação-base de Altıntaş e Ertan (REF0358, OTEKON 2024) foi implementada e submetida a identificação paramétrica por Chavez et al. no artigo próprio ENCOM 2026 (REF0369, DOI 10.5281/zenodo.22978126), agora consultado em texto completo. A cadeia documental correta é fonte-base, implementação/identificação própria e incorporação no SEEDS2. O original OTEKON permanece não consultado diretamente nesta missão; isso não significa ausência de metodologia publicada para a adaptação.

O artigo próprio descreve nove parâmetros efetivos identificados conjuntamente por mínimos quadrados, com 16 inicializações e limites físicos. Os nove valores da Tabela II, p. 297, coincidem com os parâmetros-base do código ao arredondamento publicado. A geometria-base é A=232 cm² e N=41; Uf é aproximadamente 0,6962. O RMSE de 1,411 mV relatado refere-se às curvas de tensão digitalizadas. O trabalho discute a correlação entre parâmetros e não representa ensaios independentes do equipamento Horizon.

A Nernst implementada combina pO2=0,21 p_air com um denominador sqrt(p_air). Isso faz a pressão total do ar cancelar nesse termo específico. A pressão continua afetando a ativação. A observação é uma questão estrutural para cotejo, não uma conclusão de bug sem original. REF0152 oferece contraponto de modelagem/validação de outra PEMFC, sem validar o mesmo stack ou as mesmas condições.

O equivalente próximo de 65 kW combina a base própria Chavez/Altıntaş–Ertan, dados atribuídos ao stack de Chen et al. (REF0359) e limites nominais Horizon. O DOI de Chen foi confirmado no editor CIESC, embora a consulta Crossref tenha falhado; o resumo é A, e as Tabelas 1–2 não foram conferidas. O manual VLIIPro50-22 V1.3 de 07/11/2025 foi apenas citado pelo código, sem recuperação externa. Portanto, “modelo equivalente de engenharia” é uma descrição adequada; “modelo experimentalmente validado do Horizon” não é.

A vazão fundamental é N I/(2F), convertida em massa e corrigida conforme utilização/fornecimento. A curva q(P) do EMS usa potência líquida e segmentos PWL com seleção explícita, preservando a curva aproximada não convexa e o estado OFF separado. Partidas/paradas e rampas acrescentam massa/eventos ao termo estacionário q(P)Δt. A massa total deve incluir as parcelas efetivamente implementadas. A verificação interna B04 avalia aproximação, não validação experimental. O estoque de tanque M18 não está suportado no núcleo.

### 4.5 Térmica, PCC e domínios não representados

A bancada térmica usa alvo de geração, mínimo inflexível, teto de potência, CVU e eventos. O preflight V2 rejeita sua representação econômica por ausência de M19/CVU integrado. Um recurso funcional no legado não fundamenta a alegação de despacho térmico econômico no novo EMS.

O PCC agrega importação e exportação exclusivas e integra J_rede=Σ h(c_imp P_imp−c_exp P_exp). Sem um termo explícito de demanda e demais parcelas, esse é um custo de energia transacionada, não a fatura industrial completa. Sem fluxo AC, conversores e equações eletromagnéticas, as curvas de balanço não demonstram tensão, frequência ou estabilidade. O artigo naval REF0278 inclui análise dinâmica/conversores que o V2 não herda.

## 5. Equações e rastreabilidade de implementação

A matriz 05 é a referência detalhada para todas as 53 entradas. Cada linha registra caminho, símbolo, intervalo de linhas, SHA, expressão/lógica, unidades, hipóteses, fontes e grau de correspondência. O quadro abaixo seleciona mecanismos centrais e evita atribuir uma equação ao paper apenas por afinidade temática.

| Modelo / localização | Expressão ou mecanismo e unidade | Fontes / correspondência |
| --- | --- | --- |
| MOD0007 simulation/multimodel.py : simulate_irradiance_model L301-324 | P = P_STC G_ef/G_ref Ns Np. Unidade: W | REF0113. Apoio metodológico. Modelo simplificado da bancada; não inclui temperatura. |
| MOD0010 models/wind_model.py : calculate_air_density L208-247 | rho = pd/(Rd T)+pv/(Rv T), pv=RH es(T); es=6,1121 exp[(18,678−Tc/234,5)Tc/(257,14+Tc)]. Unidade: kg/m³, K, hPa | REF0132. Aproximação compatível; versão de coeficientes pendente. Buck 1981 não confirma sozinho a revisão exata desses coeficientes. |
| MOD0015 models/battery_model.py : simulate_2rc L262-351 | V=OCV(SOC)−IR0−V1−V2; Vj+=h(I/Cj−Vj/(Rj Cj)); SOC+=−Ih/(3600Q). Unidade: V, A, F, ohm, s | REF0147. Fonte direta: 13 linhas R1/C1/R2/C2 reproduzidas. Tabela 3 tem incompatibilidade tau2 ≠ R2 C2 em SOC 0,9; ver conferência própria. |
| MOD0019 h2_pemfc/models/pemfc_model.py : PEMFCModel.nernst_voltage L27-38 | E=E0−0,00085(T−Tref)+(RT/2F) ln[pH2 sqrt(0,21 pair)/(pH2O sqrt(pair))]. Unidade: V/célula, K, atm | REF0369; REF0358; REF0152; REF0341. Implementação própria publicada, baseada em Altıntaş–Ertan; forma global documentada no ENCOM.. O cancelamento de pair nesta expressão permanece uma propriedade do código; o artigo próprio descreve a identificação conjunta e o efeito de pressão. Cotejo literal da expressão original OTEKON é complementar. |
| MOD0021 h2_pemfc/models/pemfc_model.py : PEMFCModel.membrane_resistance L85-87 | sigma=F² DH CH/(RT); Rmem=tm/sigma; Vohm=j Rmem. Unidade: S/cm, ohm cm² | REF0369; REF0358; REF0151. Parâmetros Rmem,ref/nR conferidos com a Tabela II do artigo próprio.. O artigo ENCOM documenta a identificação; não expande todas as correlações eletroquímicas da fonte OTEKON. |
| MOD0025 h2_pemfc/balance_of_plant/hydrogen.py : HydrogenConsumptionModel.evaluate L21-47 | nH2=N I/(2F); m_suprida=nH2 M_H2/Uf; kg/h=3600 kg/s; Pquim=mdot PCI. Unidade: mol/s, kg/h, kW | REF0151; REF0152. Equação fisicamente compatível; adaptação de sistema. Separar consumo eletroquímico, suprimento e purgas; sem atribuir perdas a uma fonte não lida. |
| MOD0029 ems_v2/milp/modelo.py : construir_modelo L57-200 | Σ delta_s=u; 0≤theta_s≤delta_s; p=Σ[P_s delta_s+ΔP_s theta_s]; q=Σ[Q_s delta_s+ΔQ_s theta_s]. Unidade: kW, kg/h | REF0083; REF0312. Formulação MILP equivalente. Curva pode ser não convexa; relaxação convexa global não é substituto exato. |
| MOD0031 integracao_v2/pemfc_dinamica.py : massas_eventos L196-205 | m_SU=max(0,max delta_SU(P)); m_SD=max delta_SD(P), integrais dinâmicas adicionais à q_hat(P)Δ. Unidade: kg/evento | REF0270. Derivação própria; apoio indireto sobre transientes. Ensaios de outro equipamento não fornecem estas massas. Apresentar a derivação e a integral do modelo do projeto. |
| MOD0033 integracao_v2/preflight.py : NAO_REPRESENTAVEL L67-70 | Térmica despachável bloqueada: M19/CVU não implementado no núcleo integrado. Unidade: Não aplicável | REF0312. Lacuna implementacional documentada. Não afirmar que toda a bancada térmica é otimizada pelo V2. |
| MOD0035 ems_v2/milp/modelo_3c3.py : construir_modelo_3c3 L84-137 | J_rede = h Σ(cimp Pimp−cexp Pexp). Unidade: R$, R$/kWh | REF0363; REF0364; REF0136. Adaptação de insumo oficial. Não equivale a fatura completa: cobrança de demanda, tributos e encargos precisam de escopo explícito. |
| MOD0038 ems_v2/milp/modelo_3c1.py : construir_modelo_3c1 L44-149 | Σ y_j≤u_t em janela U; Σ z_j≤1−u_t em D; obrigação herdada e política terminal. Unidade: intervalos, s | REF0117; REF0158. Equação equivalente; adaptação temporal. Tempos mínimos não são parâmetros universais; dependem do cenário. |
| MOD0041 ems_v2/hierarquia/planejador.py : Planejador3C4 L200-688 | V_tail(E,sigma)=min J_cauda, da fronteira da janela curta até fim longo, com mesmo termo terminal longo. Unidade: R$, kWh | REF0338; REF0365; REF0216. Compatibilidade conceitual; derivação própria. Não é SDDP, ADP aprendido, decomposição dual ou preço sombra extraído do solver. |
| MOD0045 ems_v2/milp/config.py : ConfiguracaoSolver L23-29 | time_limit, threads, rel_gap, abs_gap, semente e opções explícitas. Unidade: s, fração, R$ | REF0111; REF0356. Ferramentas primárias identificadas. Versões do requirements não provam ambiente de toda rodada; guardar metadados reais. |
| MOD0047 ems_v2/ponte/execucao.py : projecao_numerica_energia L271-279 | epsilon=min(tolE,16·2^−53·S); projeção no limite apenas dentro da margem de arredondamento. Unidade: kWh | REF0139; REF0354. Tratamento numérico próprio. Não descrever o executor como totalmente sem projeção: existe esta exceção explícita. |
| MOD0050 ems_v2/series.py : alinhar_a_malha L115-151 | Séries por intervalos e fronteiras verificadas contra UTC e N/N+1; alinhamento exige cobertura. Unidade: UTC, kW, kWh | REF0142; REF0155. Processamento temporal próprio. Reamostragem não cria informação física e requer semântica média/instantânea. |

Equações sem fonte original externamente conferida devem ser apresentadas como formulação/derivação do projeto com hipóteses explícitas, ou ter a fonte obtida antes de sua atribuição. A literatura pode fundamentar a classe de uma restrição sem ser origem literal do código. A auditoria estática confirma o texto implementado, não sua execução correta em todos os domínios.

## 6. Desenho dos dois estudos e evidência necessária

### 6.1 Estudo I: COPEL, quatro configurações do mesmo consumidor hipotético

As configurações pertencem a um único caso industrial hipotético: C1 rede; C2 rede + FV; C3 rede + bateria; C4 rede + FV + bateria. Elas podem mostrar efeitos da composição tecnológica sob a mesma carga/tarifa. Alterar a composição não isola o algoritmo de controle. A hierarquia deve ser avaliada em C4 idêntica, com e sem sinal de continuação, usando o mesmo horizonte curto, passo, previsão, estado inicial, custo, capacidades, restrições e condições de solver.

O perfil B1/Simulação 5 incorporado ao SEEDS2 e o futuro perfil CT-046 industrial têm finalidades independentes. Não se identificou troca de categoria no código nem utilização alegada de B1 como CT-046. A futura microrrede CT-046 deverá registrar sua fonte, tipologia, escala, transformação e tarifa em cenário próprio. Essa preparação não exige substituir o perfil B1 existente. A página tarifária COPEL consultada indica REH 3.592/2026 e vigência de 24/06/2026 a 23/06/2027 (REF0363); a modalidade aplicável deverá ser associada ao cenário efetivamente avaliado.

### 6.2 Estudo II: embarcação isolada

Informar perfil de propulsão/carga, composição FC–BESS, limites de conversão, energia e estado de gerador iniciais, frequência/intervalo da curva e massa de H2 disponível. ON com potência anterior de 30 kW exige a versão de cenário correspondente. Uma rampa de 2 kW/s equivale a 120 kW/min; esse valor é taxa de variação, não potência mínima de operação. A interpretação depende da especificação externa ainda pendente.

As referências navais REF0093, REF0094 e REF0278 diferem entre dimensionamento, programação da viagem, controle distribuído, degradação e estabilidade. Seus resultados não são comparáveis por percentual isolado. É necessário alinhar fronteira de energia, previsão, custos, perfil, tamanhos e política terminal. O uso do modelo equivalente não permite concluir desempenho real do fabricante.

### 6.3 Plano comparativo mínimo

| Comparação ou métrica | Configuração e interpretação |
| --- | --- |
| Composição C1–C4 | Mesma carga/tarifa e período; atribuir diferenças à composição e à operação conjunta, sem isolar o EMS. |
| Ablação em C4 | Sem valor futuro e com valor futuro, física e informações iguais; declarar política terminal de ambos. |
| Referência informacional | Solução com previsão perfeita, quando calculada, rotulada como limite/benchmark privilegiado, não como controle causal equivalente. |
| Custo | Somar parcelas operativas realizadas e declarar exclusões; separar valor futuro, plano e realização. |
| Energia e atendimento | Balanços por intervalo, integração em kWh, importação/exportação, curtailment e eventual carga não atendida. |
| Recursos finais | SOC/energia final, H2 e eventos. Evitar economia artificial por esvaziar um recurso sem valor terminal comparável. |
| Restrições e auditoria | Maior resíduo e unidade, tolerância, rampas/commitment/exclusividade, aceitação/rejeição, estados planejados/executados. |
| Computação | Tempo por janela, distribuição, hardware, threads, limite de tempo, terminação/bound/gap; mesma configuração nas ablações. |
| Sensibilidade | Horizontes, malha de V, erros de previsão, preço H2, eficiências, estado inicial e parâmetros físicos incertos. |

Reanálise ERA5/ERA5-Land (REF0155) pode fundamentar condições históricas se os dados forem efetivamente usados, mas não é previsão causal. Séries sintéticas precisam de regra/seed e não devem ser descritas como medição. Comparar somente um dia pode evidenciar funcionamento, sem estabelecer robustez sazonal ou populacional.

## 7. Perguntas de auditoria respondidas

**Qual é o objeto auditado?** Main no SHA informado, após merge #23. PR #24 draft foi separado. Não se tomou a descrição narrativa do PR como verdade quando arquivos indicavam estado diferente.

**Todos os modelos disponíveis alimentam o EMS?** Não. Bancadas e modelos de despacho são camadas diferentes. NOCT alimenta FV V2; a existência do SDM não demonstra seu uso nos casos. A térmica possui uma lacuna de integração econômica.

**A origem de todas as equações foi encontrada?** Foram rastreadas fontes diretas e fundamentos, com a fonte própria ENCOM agora consultada. OTEKON original permanece complementar; manual Horizon, errata De Soto, partes de Chen e revisão específica de Buck seguem como pendências distintas. A matriz registra isso individualmente.

**Há confirmação experimental independente?** Esta missão não realizou experimentos, executou casos ou reexecutou testes. A concordância com uma tabela e os auditores internos são evidência numérica/documental, não validação de equipamento real.

**O EMS é realmente recedente?** O código implementa janelas e aplicação/reconciliação de blocos com cutoff. Isso é evidência estática do procedimento. O caso publicado ainda deve fornecer manifestos e trajetórias executadas.

**O termo futuro é exato?** É uma aproximação derivada de caudas reotimizadas, condicionada a domínio, modo e terminal. A representação 2D não estabelece uma prova global e deve ser avaliada contra novos pontos/soluções independentes.

**O preço da energia é dual?** O sinal auditado é uma diferença finita de V com sinal negativo e unidades monetárias/kWh. Não foi identificado como preço dual retornado diretamente pelo solver.

**C1–C4 comprovam o efeito da hierarquia?** Não isoladamente. Composição e controle precisam de comparações distintas. A ablação na mesma C4 responde à pergunta causal do método.

**Como se relacionam B1 e CT-046?** B1 é um perfil já implementado para uso próprio. CT-046 será utilizado em uma futura microrrede independente. A associação entre os dois como uma discrepância de código foi uma interpretação indevida da auditoria, agora corrigida.

**O caso naval demonstra autonomia e estabilidade?** O consumo é calculado, mas tanque não está modelado no núcleo e o balanço agregado não representa estabilidade elétrica. Essas conclusões exigem evidências adicionais próprias.

## 8. Plano de citações para sete seções

| Seção | Âncora bibliográfica sugerida | Evidência e limite |
| --- | --- | --- |
| 1 Introdução | REF0121; REF0157; REF0213; REF0354 | Motivação por heterogeneidade, variabilidade e reprodução. Evitar promessa de benefício sem resultado próprio. |
| 2 Fundamentação teórica e trabalhos relacionados | REF0104; REF0355; REF0094; REF0216; REF0338 | Plataformas e famílias de controle. Não confundir arquitetura, modelo e hierarquia. |
| 3 Arquitetura e desenvolvimento da plataforma SEEDS2 | REF0354; REF0142; REF0143; REF0111; REF0356 | Contratos, dados, versões, motores e evidência por SHA. Não transformar em manual de telas. |
| 4 Modelagem matemática e sistema de gerenciamento energético hierárquico | REF0319; REF0147; REF0352; REF0358; REF0359; REF0083; REF0365 | Equações efetivas, unidades, hipóteses, modos e aproximações. Pendências originais explicitadas. |
| 5 Metodologia de avaliação e estudos de caso | REF0363; REF0364; REF0093; REF0278; REF0142 | Dois estudos, C1–C4 como um caso, ablação C4 e proveniência de dados. |
| 6 Resultados e discussão | REF0094; REF0216; REF0338; REF0278 | Resultados próprios com métricas alinhadas. Literatura contextualiza mecanismos, sem transferir percentuais. |
| 7 Conclusões e trabalhos futuros | REF0159; REF0143; evidência própria | Conclusões limitadas ao observado e trabalho futuro orientado às lacunas. |

O arquivo 06 contém 46 claims com a fonte apropriada, o que ela não sustenta e o resultado próprio ainda necessário. O arquivo 12 detalha questão, afirmação provável, tipo de evidência, observação e fontes faltantes. As referências não substituem os resultados nas seções 6 e 7. Discussões de superioridade precisam de comparações homogêneas, e conclusões numéricas devem apontar a rodadas/figuras próprias reproduzíveis.

## 9. Pendências e prioridades de fechamento

| Registro | Achado / esclarecimento | Próxima ação |
| --- | --- | --- |
| LAC0001 / Documental | Procedência PEMFC esclarecida: artigo próprio ENCOM de Chavez et al. documenta implementação e identificação baseada em Altıntaş–Ertan. | Citar o artigo próprio como fonte imediata e OTEKON como base. Manter explícito o alcance de ajuste numérico às curvas de referência. |
| LAC0002 / Alta | Tabela 3 de Zhang contém incompatibilidade interna tau2=R2C2. | Conferir erratas/dados dos autores; não alterar o código nesta missão; documentar escolha e sensibilidade. |
| LAC0003 / Esclarecida | COPEL B1 implementado e CT-046 de futura microrrede são finalidades distintas. | Manter B1 no seu uso atual; cadastrar e documentar CT-046 separadamente quando o novo cenário for implementado. |
| LAC0004 / Alta | V2 FV usa NOCT e trata GHI como irradiância no plano do módulo. | Descrever a hipótese e avaliar sensibilidade ou usar dados já no plano do módulo quando aplicável. |
| LAC0005 / Alta | H2 é contabilizado sem dinâmica/limite de tanque no núcleo auditado. | Apresentar consumo e verificar massa disponível externamente; não afirmar tanque otimizado. |
| LAC0006 / Alta | Modelo equivalente Horizon usa dados de outro stack e área assumida. | Manter rotulagem de aproximação; obter dados do stack específico e registrar incerteza. |
| LAC0007 / Alta | Manual Horizon não consultado externamente nesta missão. | Obter manual V1.3 legítimo; conferir 2 kW/s subida e 3,5 kW/s descida, limites e unidades. |
| LAC0008 / Alta | Errata de De Soto identificada sem leitura de seu conteúdo. | Ler a errata e cotejar as expressões implementadas antes da redação final. |
| LAC0009 / Alta | Custo de continuação é aproximado; convexidade 2D é amostral. | Relatar domínio, modo, erro em validação e falta de garantia fora dos pontos consultados. |
| LAC0010 / Alta | Estado inicial de 30 kW e cenário naval persistido não foram confirmados. | Anexar versão do cenário e manifesto da rodada que efetivamente use estado ON/P_anterior=30 kW. |
| LAC0011 / Alta | PCC não calcula fatura industrial completa nem fluxo elétrico AC. | Delimitar custo operacional e documentar termos tributários/tarifários realmente incluídos. |
| LAC0012 / Média | Bateria de bancada tem clips; BESS MILP tem restrições e projeção apenas numérica no executor. | Separar modelos, convenções, integradores e política de tolerância. |
| LAC0013 / Média | A pressão do ar cancela no potencial Nernst implementado. | Conferir equação original e condições; pressão ainda afeta termo de ativação. |
| LAC0014 / Média | Curvas de pequenas eólicas incluem fontes arquivadas sem ensaio primário confirmado. | Obter relatórios SWCC/NREL originais; respeitar status curve_analysis_only. |
| LAC0015 / Média | A equação de saturação usa coeficientes que exigem identificação da revisão de Buck. | Rastrear a revisão da expressão 18,678/234,5 antes de citar origem exata. |
| LAC0016 / Média | Descrição do PR #24 está parcialmente desatualizada em relação aos arquivos presentes. | Citar SHA e arquivos efetivos; manter telas do draft separadas de main. |
| LAC0017 / Média | Térmica é funcional na bancada, mas custo M19/CVU não está integrado ao V2. | Excluir essa alegação; manter tecnologia fora dos casos V2 enquanto a lacuna existir. |
| LAC0018 / Média | Não foi reexecutada a suíte científica nem uma rodada de casos. | Planejar ensaios próprios em tarefa separada, com SHA e dependências fixados. |
| LAC0019 / Média | WoS/Scopus/Scholar e APIs abertas tiveram barreiras de acesso ou limitação de taxa. | Reexecutar consultas institucionais por acesso legítimo e exportar resultados para atualizar o corpus. |
| LAC0020 / Média | C1–C4 variam a composição tecnológica e não isolam o efeito do EMS. | Comparar controladores em C4 idêntica, previsões e estados iniciais iguais, com e sem sinal futuro. |

As pendências de acesso não autorizam preencher equações ou números plausíveis. Para atualização institucional, executar as estratégias recebidas por acesso legítimo, importar RIS/CSV, deduplicar por DOI/família e preservar os IDs existentes. O corpus aberto atual pode fundamentar a preparação científica, com as limitações indicadas; afirmações sobre originais ainda não consultados devem aguardar o cotejo.

## 10. Referências prioritárias e tipo de consulta

A lista completa de 121 itens está na matriz 04 e nas duas exportações bibliográficas. A seleção abaixo reúne as 30 prioridades de leitura, incluindo originais cuja obtenção ainda é necessária. A inclusão de um item M ou A nesta lista indica urgência, sem promovê-lo a evidência integral.

**REF0104 · P1/F** Brown, Thomas; Hörsch, Jonas; Schlachtberger, David. PyPSA: Python for Power System Analysis. Journal of Open Research Software, 2018. DOI: 10.5334/jors.188. Evidência: Versão do autor, §II–III, pp. 2–5 do PDF; funções e otimização multiperíodo.

**REF0355 · P1/F** Hilpert, S.; Kaldemeyer, C.; Krien, U.; Günther, S.; Wingenbach, C.; Plessmann, G.. The Open Energy Modelling Framework (oemof) - A new approach to facilitate open science in energy system modelling. Energy Strategy Reviews, 2018. DOI: 10.1016/j.esr.2018.07.001. Evidência: §3.1, pp. 6–9 da versão do autor; grafo bipartido e separação da topologia.

**REF0134 · P1/M** Krien, Uwe; Schönfeldt, Patrik; Launer, Jann; Hilpert, Simon; Kaldemeyer, Cord; Pleßmann, Guido. oemof.solph—A model generator for linear and mixed-integer linear optimisation of energy systems. Software Impacts, 2020. DOI: 10.1016/j.simpa.2020.100028. Evidência: Metadados; conteúdo integral não verificado.

**REF0353 · P1/F** Pfenninger, Stefan; Pickering, Bryn. Calliope: a multi-scale energy systems modelling framework. Journal of Open Source Software, 2018. DOI: 10.21105/joss.00825. Evidência: Summary, p. 1: formulação genérica, separação dados–modelo e modelos multiescala.

**REF0343 · P1/F** Klütz, Theresa; Knosala, Kevin; Behrens, Johannes; Maier, Rachel; Hoffmann, Maximilian; Pflugradt, Noah; Stolten, Detlef. ETHOS.FINE: A Framework for Integrated Energy System Assessment. Journal of Open Source Software, 2025. DOI: 10.21105/joss.06274. Evidência: Methodology, pp. 2–3; classes, Pyomo, DataFrames e persistência netCDF.

**REF0321 · P1/F** Thurner, Leon; Scheidler, Alexander; Schafer, Florian; Menke, Jan-Hendrik; Dollichon, Julian; Meier, Friederike; Meinecke, Steffen; Braun, Martin. Pandapower—An Open-Source Python Tool for Convenient Modeling, Analysis, and Optimization of Electric Power Systems. IEEE Transactions on Power Systems, 2018. DOI: 10.1109/tpwrs.2018.2829021. Evidência: Versão do autor, §III, representação por elementos; seção de implementação e verificação.

**REF0094 · P1/A** Kopka, Timon; Coraddu, Andrea; Polinder, Henk. Modular Energy Management via Distributed and Predictive Optimization for Fuel Cell-Battery Shipboard Microgrids. IEEE Open Journal of the Industrial Electronics Society, 2026. DOI: 10.1109/ojies.2026.3710800. Evidência: Resumo consultado; equações não verificadas.

**REF0349 · P1/A** Parisio, Alessandra; Rikos, Evangelos; Glielmo, Luigi. A Model Predictive Control Approach to Microgrid Operation Optimization. IEEE Transactions on Control Systems Technology, 2014. DOI: 10.1109/tcst.2013.2295737. Evidência: Resumo consultado; equações não verificadas.

**REF0216 · P1/A** Vivas, F.J.; Pajares, A.; Blasco, X.; Herrero, J.M.; Segura, F.; Andújar, J.M.. A novel energy management system based on two-level hierarchical economic model predictive control for use in microgrid control. Energy Conversion and Management: X, 2025. DOI: 10.1016/j.ecmx.2025.101027. Evidência: Resumo consultado; equações não verificadas.

**REF0338 · P1/A** Aaslid, Per; Korpas, Magnus; Belsnes, Michael M; Fosso, Olav B. Stochastic Optimization of Microgrid Operation With Renewable Generation and Energy Storages. IEEE Transactions on Sustainable Energy, 2022. DOI: 10.1109/tste.2022.3156069. Evidência: Resumo consultado; equações não verificadas.

**REF0319 · P0/M** De Soto, W.; Klein, S.A.; Beckman, W.A.. Improvement and validation of a model for photovoltaic array performance. Solar Energy, 2006. DOI: 10.1016/j.solener.2005.06.010. Evidência: Metadados; conteúdo integral não verificado.

**REF0147 · P0/F** Zhang, Lijun; Peng, Hui; Ning, Zhansheng; Mu, Zhongqiang; Sun, Changyan. Comparative Research on RC Equivalent Circuit Models for Lithium-Ion Batteries of Electric Vehicles. Applied Sciences, 2017. DOI: 10.3390/app7101002. Evidência: §2.3.3, Tabela 3, p. 8; §3, p. 9. R1/R2/C1/C2 conferidos com os 13 níveis SOC do código.

**REF0352 · P0/F** Tremblay, Olivier; Dessaint, Louis-A.. Experimental Validation of a Battery Dynamic Model for EV Applications. World Electric Vehicle Journal, 2009. DOI: 10.3390/wevj3020289. Evidência: §2.1–2.3, Eqs. (1) e (3); Tabela 1 e hipóteses, pp. 2–4 do PDF.

**REF0369 · P0/F** Bruno Manuel O. Chavez; Marília Luiza B. Peruzzo; Ana Carolina da Silva Mota; Pedro Germano A. Cruz; Leandro A. Ensina; Oswaldo Hideo A. Junior; Joylan N. Maciel; Jorge Javier G. Ledesma. Desenvolvimento computacional e estimação de parâmetros de um modelo eletroquímico de célula a combustível PEM. ENCOM 2026, pp. 295–298. DOI: 10.5281/zenodo.22978126. Evidência: PDF fornecido, pp. 295–298; §II, Eqs. (1)–(7), p. 296; Tabelas I–II, p. 297; §III e conclusão, pp. 297–298.

**REF0359 · P0/A** Chen, Hong; Jiang, Kun; Tang, Tingjiang; Huang, Yiyuan; Chi, Bin; Liao, Shijun. Research on membrane electrode assembly consistency of high-power proton exchange membrane fuel cell stack. CIESC Journal, 2024. DOI: 10.11949/0438-1157.20230745. Evidência: Resumo consultado; equações não verificadas.

**REF0083 · P2/F** Vielma, Juan Pablo; Ahmed, Shabbir; Nemhauser, George. Mixed-Integer Models for Nonseparable Piecewise-Linear Optimization: Unifying Framework and Extensions. Operations Research, 2010. DOI: 10.1287/opre.1090.0721. Evidência: Manuscrito do autor, §3.1.1, Eq. (5a–c), p. 5 do PDF; formulação DCC.

**REF0156 · P1/F** Fan, Songli; Ai, Qian; Piao, Longjian. Hierarchical Energy Management of Microgrids including Storage and Demand Response. Energies, 2018. DOI: 10.3390/en11051111. Evidência: §2 e Fig. 1, pp. 3–4; §3.1, custos/commitment/armazenamento.

**REF0350 · P1/A** Yassuda Yamashita, Daniela; Vechiu, Ionel; Gaubert, Jean-Paul. Two-level hierarchical model predictive control with an optimised cost function for energy management in building microgrids. Applied Energy, 2021. DOI: 10.1016/j.apenergy.2020.116420. Evidência: Resumo consultado; equações não verificadas.

**REF0351 · P1/A** Polimeni, Simone; Meraldi, Lorenzo; Moretti, Luca; Leva, Sonia; Manzolini, Giampaolo. Development and experimental validation of hierarchical energy management system based on stochastic model predictive control for Off-grid Microgrids. Advances in Applied Energy, 2021. DOI: 10.1016/j.adapen.2021.100028. Evidência: Resumo consultado; equações não verificadas.

**REF0221 · P1/A** Lim, Donghwan; Cha, Junsang; Seo, Chiwon; Jang, Gilsoo. A two-layer robust model predictive control-based energy management system for a zero-carbon DC microgrid with hybrid hydrogen-battery energy storage. International Journal of Electrical Power &amp; Energy Systems, 2026. DOI: 10.1016/j.ijepes.2025.111516. Evidência: Resumo consultado; equações não verificadas.

**REF0356 · P3/F** Huangfu, Q.; Hall, J. A. J.. Parallelizing the dual revised simplex method. Mathematical Programming Computation, 2018. DOI: 10.1007/s12532-017-0130-5. Evidência: §2–4; estratégias SIP/PAMI, paralelismo e comparação de métodos simplex.

**REF0111 · P3/M** Hart, William E.; Watson, Jean-Paul; Woodruff, David L.. Pyomo: modeling and solving mathematical programs in Python. Mathematical Programming Computation, 2011. DOI: 10.1007/s12532-011-0026-8. Evidência: Metadados; conteúdo integral não verificado.

**REF0354 · P3/F** Wilson, Greg; Aruliah, D. A.; Brown, C. Titus; Chue Hong, Neil P.; Davis, Matt; Guy, Richard T.; Haddock, Steven H. D.; Huff, Kathryn D.; Mitchell, Ian M.; Plumbley, Mark D.; Waugh, Ben; White, Ethan P.; Wilson, Paul. Best Practices for Scientific Computing. PLoS Biology, 2014. DOI: 10.1371/journal.pbio.1001745. Evidência: Box 1; seções de versionamento, testes, modularização e revisão.

**REF0142 · P3/F** Sandve, Geir Kjetil; Nekrutenko, Anton; Taylor, James; Hovig, Eivind. Ten Simple Rules for Reproducible Computational Research. PLoS Computational Biology, 2013. DOI: 10.1371/journal.pcbi.1003285. Evidência: Regras de registro de etapas, versões e preservação de entradas/saídas.

**REF0143 · P3/F** Wilkinson, Mark D.; Dumontier, Michel; Aalbersberg, IJsbrand Jan; Appleton, Gabrielle; Axton, Myles; Baak, Arie; Blomberg, Niklas; Boiten, Jan-Willem; da Silva Santos, Luiz Bonino; Bourne, Philip E.; Bouwman, Jildau; Brookes, Anthony J.; Clark, Tim; Crosas, Mercè; Dillo, Ingrid; Dumon, Olivier; Edmunds, Scott; Evelo, Chris T.; Finkers, Richard; Gonzalez-Beltran, Alejandra; Gray, Alasdair J.G.; Groth, Paul; Goble, Carole; Grethe, Jeffrey S.; Heringa, Jaap; ’t Hoen, Peter A.C; Hooft, Rob; Kuhn, Tobias; Kok, Ruben; Kok, Joost; Lusher, Scott J.; Martone, Maryann E.; Mons, Albert; Packer, Abel L.; Persson, Bengt; Rocca-Serra, Philippe; Roos, Marco; van Schaik, Rene; Sansone, Susanna-Assunta; Schultes, Erik; Sengstag, Thierry; Slater, Ted; Strawn, George; Swertz, Morris A.; Thompson, Mark; van der Lei, Johan; van Mulligen, Erik; Velterop, Jan; Waagmeester, Andra; Wittenburg, Peter; Wolstencroft, Katherine; Zhao, Jun; Mons, Barend. The FAIR Guiding Principles for scientific data management and stewardship. Scientific Data, 2016. DOI: 10.1038/sdata.2016.18. Evidência: The FAIR Guiding Principles, itens F1–F4, A1–A2, I1–I3, R1.

**REF0123 · P0/F** Kratochvil, Jay; Boyson, William; King, David. Photovoltaic array performance model.. , 2004. DOI: 10.2172/919131. Evidência: Seção de temperatura de módulo/célula, pp. 19–20 do PDF; relações exponenciais e ΔT.

**REF0278 · P1/F** Kotsampopoulos, Panos; Saridaki, Georgia; Kour, Jasdeep; Fayek, Hady Habib. Ship Electric Propulsion Based on Hydrogen Fuel Cell, Batteries, PVs and WASP: Energy Management, Dynamics and Converter-Driven Stability. Energies, 2026. DOI: 10.3390/en19112636. Evidência: §3.1–3.2, p. 6; §4.1, p. 12: CVO/TLBO e simulação EMT em RSCAD/RTDS.

**REF0093 · P1/F** Jin, Hao; Yang, Xinhang. Bilevel Optimal Sizing and Operation Method of Fuel Cell/Battery Hybrid All-Electric Shipboard Microgrid. Mathematics, 2023. DOI: 10.3390/math11122728. Evidência: §3.2, Eq. (3), p. 5; §4.1, Eq. (4), p. 5.

**REF0365 · P2/F** Rawlings, James B.; Mayne, David Q.; Diehl, Moritz M.. Model Predictive Control: Theory, Computation, and Design. 2nd edition, fifth printing. Nob Hill Publishing, 2024. Fonte sem DOI confirmado: https://sites.engineering.ucsb.edu/~jbraw/mpc/MPC-book-2nd-edition-5th-printing.pdf. Evidência: Cap. 2, §2.2, Eqs. (2.3)–(2.8), pp. 95–97 impressas; edição e impressão na folha de créditos.

**REF0366 · P0/F** Vergnet. GEV MP C 275 kW. Technical characteristics. DC-11-00-01-EN. Vergnet, 2014. Fonte sem DOI confirmado: https://www.vergnet.com/wp-content/uploads/2023/06/DC-11-00-01-EN_GEV_MP-C_275_kW.pdf. Evidência: Technical characteristics / Power curve, p. 7 do PDF; densidade 1,225 kg/m³ e tabela 2,5–25 m/s.
