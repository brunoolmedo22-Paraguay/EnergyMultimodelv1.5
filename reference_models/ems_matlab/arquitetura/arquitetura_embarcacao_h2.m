function arch = arquitetura_embarcacao_h2(N_fc)
% ARQUITETURA_EMBARCACAO_H2  -- Define a arquitetura/topologia da embarcacao
%hibrida H2 (MFCS) + Bateria (LB) + PV, com base nos dados reais do
%navio "Three Gorges Hydrogen Boat 1", conforme:
% Jiang, J., Zou, L., Liu, X., Han, Z., Wang, R. (2025). https://doi.org/10.1016/j.enconman.2025.120032
% (Tabelas 1, 2 e 3)
%
% Esta funcao retorna um struct unico 'arch' com todos os subsistemas
% (nau, MFCS, bateria, PV, conversores, EMS) para ser usado como fonte
% unica de parametros por qualquer script/pipeline de EMS.
%
% USO:
% arch = arquitetura_embarcacao_h2(); % usa N_fc = 2 (navio real)
% arch = arquitetura_embarcacao_h2(4); % generaliza para 4 FC (Zhang et al
% 2025)
%
% PARA UMA NOVA EMBARCACAO/APLICACAO: crie um novo arquivo com a mesma assinatura 
% (recebe N_fc ou não, devolve um struct 'arch' com os mesmos campos-chave usados abaixo em
% arch.ems) e aponte para ele em config_cenario.m. Nenhum outro arquivo
% precisa ser alterado.
%
% Dados não reportados:
% - Resistencia interna da bateria (Rint) NAO é informada em nenhum dos artigos
% estimada em 0,1 Ohm


if nargin < 1 || isempty(N_fc)
    N_fc = 2; % configuracao do Three Gorges Hydrogen Boat 1 (Jiang et al., Table 2)
end

%% =====================================================================
%% 1) CASCO / OPERACAO (Jiang et al., Table 2)
%% =====================================================================
arch.ship.length_m = 49.9;
arch.ship.width_m = 10.4;
arch.ship.height_m = 3.2;
arch.ship.cruise_speed_kmh = 20;
arch.ship.dc_bus_voltage_V = 650; % tensao nominal do barramento DC principal

%% =====================================================================
%% 2) MFCS - Multi Fuel Cell Stack System (Jiang et al., Tables 1-3)
%% =====================================================================
arch.fc.N_fc = N_fc;

% Potencia nominal por FC. Navio real (N_fc=2): 250 kW cada.
arch.fc.P_rated_each_kW = 250;
arch.fc.P_max_tot_kW = N_fc * arch.fc.P_rated_each_kW;
arch.fc.P_min_tot_kW = 0; % Jiang et al. nao trunca por baixo (diferente de Zhang et al.)

arch.fc.V_out_range_V = [200 380]; % tensao de saida de cada PEMFC

% Curva de eficiencia: eta_PEMFC(P) = a*exp(b*P) + c*exp(d*P)   [Eq.2]
% Coeficientes por stack (Table 1). 
coefs_base = [ 0.6232, -0.0011581, -0.4744, -0.05673; % PEMFC1
               0.5889, -0.0009227, -0.5784, -0.07832]; % PEMFC2

if N_fc <= 2
    arch.fc.eff_coefs = coefs_base(1:max(N_fc,1), :);
else
    extra = repmat(coefs_base(2,:), N_fc-2, 1);
    arch.fc.eff_coefs = [coefs_base; extra];
end

arch.fc.Elow_H2_kWh_per_kg = 33.33; % PCI do H2 

% Coeficientes de degradacao (Eq.4-7, Table 3)
arch.fc.deg.mu_c_uV_per_kW = 0.0441; % degradacao por flutuacao de potencia
arch.fc.deg.mu_h_uV_per_h = 23.48; % degradacao por operacao em alta carga
arch.fc.deg.mu_l_uV_per_h = 20.34; % degradacao por operacao em baixa carga
arch.fc.deg.mu_s_V_per_cycle = 1.4e-5; % degradacao por partida/parada
arch.fc.deg.U_limit_V = diff(arch.fc.V_out_range_V); % 380-200 = 180 V 
arch.fc.deg.high_load_frac = 0.9; % limiar de "alta carga": 0.9*P_max (Eq.5)
arch.fc.deg.low_load_frac = 0.1;  % limiar de "baixa carga": 0.1*P_max (Eq.6)

arch.fc.ramp.dP_max_kW = 20; % DeltaP_max (Table 3) -- limite de rampa

% PILAR 1: dinamica de 1a ordem G_FC(s) = kf/(1+s*tau) 
% Duas instancias da MESMA estrutura (ver fc_dinamica.m):
%   tau_FC_s    "planta real" (termica/membrana, dinamica LENTA, usada no
%               loop real de ems_dispatch.m) -- literatura tipica p/ MFCS
%               naval de porte medio, AJUSTAR com dado real do stack.
%   tau_f_mpc_s dinamica RAPIDA do atuador/controlador de corrente,
%               usada so DENTRO da predicao do NMPC (linearizada).
arch.fc.tau_FC_s = 4;    % [s] (planta real) Dash 2020 https://doi.org/10.48550/arXiv.2004.05776
arch.fc.tau_f_mpc_s = 0.2;  % [s] (modelo linearizado do NMPC) Lu et al 2024 https://doi.org/10.3390/wevj15040151
arch.fc.kf = 1;    % ganho estatico em regime permanente Lu et al 2024 https://doi.org/10.3390/wevj15040151

% PILAR 2: atraso de tensao (mesma dinamica lenta da potencia) 
arch.fc.tau_v_s = arch.fc.tau_FC_s; % tensao acompanha a dinamica termica/
% eletroquimica "lenta" da FC, nao a dinamica rapida de atuador tau_f_mpc_s
arch.fc.V_range = arch.fc.V_out_range_V; 

% Constante de tempo do LPF de desacoplamento de frequencia (Frequency
% Decoupling, Pilar 2): deve ser >> tau_FC para que a referencia "baixa
% frequencia" da FC nao brigue com a propria dinamica fisica dela.
arch.ems.T_lpf_s = 300; % [s] Pan Das 2014 http://dx.doi.org/10.1016/j.isatra.2015.03.003

% PILARES 3/4: MLD (numero de stacks) + DP offline
% Piso minimo de operacao por stack ligado (evita operar uma PEMFC em
% carga parcial demais, ruim para eficiencia/degradacao) 
%arch.fc.P_min_stack_kW = 0.10 * arch.fc.P_rated_each_kW; % considerado 10 % da potência nominal
arch.fc.P_min_stack_kW = 0;
% Jiang et al 2025 https://doi.org/10.1016/j.enconman.2025.120032

% Config da Programacao Dinamica offline (dp_offline_nstacks.m): 
arch.ems.dp.Npos = 120; % numero de segmentos da rota Kofler et al 2024 https://doi.org/10.1016/j.apenergy.2024.124513
arch.ems.dp.dSOC = 0.005; % resolução da grade de SOC Kofler et al 2024 https://doi.org/10.1016/j.apenergy.2024.124513
arch.ems.dp.p_switch_kg = 0.01; % penalidade de start/stop FC Kofler et al 2024 https://doi.org/10.1016/j.apenergy.2024.124513

%% =====================================================================
%% 3) BATERIA / LB (Jiang et al., Tables 2-3)
%% =====================================================================
arch.bat.Q_kWh = 1806;
arch.bat.V_rated_V = 537.6;
arch.bat.SOC_min = 0.30;
arch.bat.SOC_max = 0.80;
arch.bat.SOC_ini = 0.60;

arch.bat.W_LB_USD_per_kWh = 140.84; % preco de venda da bateria (Table 3)
arch.bat.mu_LB = 15.18;  % coeficiente de equilibrio p/ degradacao (Eq.15)
arch.bat.M_max_cycles = []; % numero maximo de ciclos (nao consta no artigo) 

arch.bat.Rint_ohm = 0.1; 

% Limites de potencia 
arch.bat.P_max_discharge_kW = 150;
arch.bat.P_max_charge_kW = 50;

% Limites de TENSAO TERMINAL
arch.bat.V_min_V = 450; 
arch.bat.V_max_V = 600; 

% Piso de SOC relaxado sob contingencia (permite descarga mais profunda
% quando a prioridade passa a ser atender a carga)
arch.bat.SOC_min_contingencia = 0.15;

% Pesos do custo (Eq.31) -- valores default do artigo (modo "cruzeiro").
% Os pesos POR MODO de operacao (usados de fato pelo EMS) estao em
% arch.ems.pesos, abaixo.
arch.ems.a1 = 1; % peso do custo de energia (H2 + equivalente bateria)
arch.ems.a2 = 10; % peso do custo de degradacao

%% =====================================================================
%% 4) PROPULSAO (2 motores)
%% =====================================================================
% Motor + inversor reais: Danfoss Editron EM-PMI375-T800-3800 + EC-C1200-450
% Fonte: Danfoss Data Sheet EM-PMI375-T800 (AI269157546702, abr/2020) e
% pagina de produto "HV inverters" (danfoss.com/.../hv-inverters/).
% https://www.slimlinehydrotek.com/wp-content/uploads/2020/05/Electric-Machine-PMI375-T800.pdf
arch.motor.N_motors = 2;
arch.motor.P_rated_each_kW = 250; % EM-PMI375-T800-3800, classe H: 251 kW continuos @65degC coolant
arch.motor.P_rated_tot_kW = arch.motor.N_motors * arch.motor.P_rated_each_kW;
arch.motor.model = 'Danfoss Editron EM-PMI375-T800-3800';
arch.motor.V_nominal_VAC = 500;
arch.motor.eta_motor = 0.96; % eficiencia nominal do datasheet
arch.motor.weight_kg = 210;  % por unidade (sem opcoes)
arch.motor.marine_class_option = 'CL1(ABS)/CL2(BV)/CL3(DNVGL)/CL4(LR)/CL5(RINA)'; % opcional de fabrica

arch.inverter.model = 'Danfoss Editron EC-C1200-450';
arch.inverter.I_cont_Arms = 350; % continuo como inversor AC
arch.inverter.V_max_DC = 850;
arch.inverter.weight_kg = 14;
arch.inverter.eta_inv = 0.97; 

%% =====================================================================
%% 5) PV 
%% =====================================================================
% Utilizado o mesmo conversor mas está superdimensionada para este
% porte de PV
arch.pv.P_rated_kWp = 50; 
arch.pv.conv_model  = 'Danfoss Editron EC-C1200-450+DC + EC-LTS1200-410 (superdimensionado p/ este porte)';
arch.pv.curtailment = false; % PV sempre descontada integralmente (sem curtailment)

%% =====================================================================
%% 6) FONTE EXTRA (EX: EÓLICA)
%% =====================================================================
arch.fonte_extra.usa              = true; % true liga a fonte
arch.fonte_extra.eta_conv         = 0.97;  % eficiencia do conversor ate o barramento
arch.fonte_extra.custo_kg_por_kWh = 0;     % 0 = gratuita; >0 penaliza o uso

%% =====================================================================
%% 7) CONVERSORES / BARRAMENTO DC (do seu diagrama original)
%% =====================================================================
% Mesmo conversor Danfoss Editron para os tres ramos DC/DC (MFCS, BESS, PV):
% EC-C1200-450 com opcao +DC, combinado com indutor EC-LTS1200-410
% (ate 850VDC, 400 ADC continuo). Fonte: Danfoss PowerSource "DC/DC
% converters" e User Guide EC-C1200-450 (BC265735231757).
% P_deficit(t) = P_load(t) - eta_dc * P_pv(t)
% P_deficit(t) = eta_dc1 * P_fc(t) + eta_dc2 * P_bat(t)
arch.conv.dcdc_model = 'Danfoss Editron EC-C1200-450+DC + EC-LTS1200-410';
arch.conv.eta_dc_aux = 0.95; % Ramo DC -> cargas auxiliares
arch.conv.eta_dc  = 0.97; % conversor DC/DC do PV
arch.conv.eta_dc1 = 0.97; % conversor unidirecional MFCS -> barramento DC
arch.conv.eta_dc2 = 0.96; % conversor bidirecional LB <-> barramento DC

% Capacidade eletrica (V x I) dos conversores DC/DC de FC e bateria --
% OPCIONAL: se preenchido, montar_equipamentos.m aperta o P_max/P_min
% declarado acima para nunca exigir mais corrente do que o conversor
% aguenta na tensao nominal do barramento. Deixe comentado/ausente se
% ainda nao tiver o dado de placa; o pipeline funciona igual, so sem
% essa checagem extra.
arch.conv.I_max_fc_A  = 400; % ex.: EC-C1200-450, classe ~400 A continuo
arch.conv.I_max_bat_A = 400;

%% =====================================================================
%% 8) EMS - MODOS DE OPERACAO, PESOS E LIMIARES
%% =====================================================================
% Tudo que o EMS usa para decidir "que tipo de situacao e essa" e "o
% quanto priorizar H2 vs. degradacao vs. SOC" -- nao
% hardcoded em ems_dispatch.m/classificar_modo_simples.m/
% pesos_por_modo.m. Trocar de embarcacao/aplicacao = ajustar esta secao.

arch.ems.usa_referencia_fc = false; % true: usa Pfc_ref digitalizada do
% artigo (Fig.4b) como termo de rastreamento no custo (w2). Se a fonte
% de carga nao tiver essa referencia (caso mais comum daqui pra frente),
% deixe false -- o pipeline zera Pfc_ref automaticamente e o despacho
% passa a ser guiado so por H2 real + rampa + degradacao da bateria.

% Limiares de classificacao de modo/SOC (classificar_modo_simples.m)
arch.ems.modo.thresh_porto_kW = 5; % abaixo disso: modo "porto"
arch.ems.modo.thresh_delta_pu = 0.015; % |delta carga| acima disso: modo "transiente"
arch.ems.modo.soc_baixo = 0.35;
arch.ems.modo.soc_alto  = 0.70;

arch.ems.soc_desliga_fc_porto = 0.80; % em porto com SOC acima disso, desliga a FC

% Pesos [w1 mH2, w2 tracking, w3 degradacao bateria, w4 SOC final,
% w5 flutuacao FC (Pilar 5, Hamiltoniano a*(DeltaPfc)^2)] por modo
% (1=porto, 2=transiente, 3=cruzeiro, 4=emergencia/contingencia).
% w5 e pequeno pois multiplica (DeltaP em kW)^2 (grandeza ~1e2-1e4 kW^2);
% em transiente (modo 2) w5 e propositalmente baixo para nao competir com
% o rastreamento (w2); em cruzeiro (modo 3) w5 e maior para
% suavizar a rampa e reduzir ciclos start/stop desnecessarios.
arch.ems.pesos.modo(1).base = [900,   50,  200,  80, 0.05]; % porto
arch.ems.pesos.modo(1).override = struct('soc_idx',3,'w4',0.001); % SOC alto em porto: nao penaliza SOC final

arch.ems.pesos.modo(2).base = [180, 2500,    5, 0.001, 0.01]; % transiente (delta alto): prioriza rastreio

arch.ems.pesos.modo(3).base = [150,  800,   80,  0.01, 0.08]; % cruzeiro
arch.ems.pesos.modo(3).override = struct('soc_idx',[1 3],'w4',120); % SOC fora da faixa saudavel: penaliza mais

arch.ems.pesos.modo(4).base = [50,  5000,   10, 0.001, 0.005]; % emergencia/contingencia: so atender a carga importa

end
