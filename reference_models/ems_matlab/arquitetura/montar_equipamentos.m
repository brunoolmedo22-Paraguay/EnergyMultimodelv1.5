function [fc, bat, conv, nmpc, extra] = montar_equipamentos(arch, cenario)
%MONTAR_EQUIPAMENTOS Traduz arch (fisica/parametros da embarcacao) +
%cenario (horizonte NMPC etc.) nas structs fc/bat/conv/nmpc usadas pelo
%otimizador. E o UNICO lugar que aplica o limite de capacidade eletrica
%do conversor (V x I) sobre os limites de potencia declarados em arch.
    fc.Elow = arch.fc.Elow_H2_kWh_per_kg;
    fc.Nfc = arch.fc.N_fc;
    fc.P_min_tot = arch.fc.P_min_tot_kW;
    fc.P_max_tot = arch.fc.P_max_tot_kW;
    fc.ramp_limit_kWps = arch.fc.ramp.dP_max_kW / 60;

    % PILAR 1 (dinamica 1a ordem) e PILAR 2 (atraso de tensao / FC)
    fc.tau_FC_s = arch.fc.tau_FC_s;
    fc.tau_f_mpc_s = arch.fc.tau_f_mpc_s;
    fc.kf = getfield_default(arch.fc, 'kf', 1);
    fc.tau_v_s = arch.fc.tau_v_s;
    fc.V_range = arch.fc.V_range;

    % PILARES 3/4 (MLD + DP offline): piso minimo por stack ligado
    fc.P_min_stack_kW = arch.fc.P_min_stack_kW;
    bat.Qbat_kWh = arch.bat.Q_kWh;
    bat.SOC_min = arch.bat.SOC_min;
    bat.SOC_max = arch.bat.SOC_max;
    bat.SOC_ini = arch.bat.SOC_ini;
    bat.Voc = arch.bat.V_rated_V;
    bat.Rint = arch.bat.Rint_ohm;
    bat.V_min = getfield_default(arch.bat, 'V_min_V', -Inf);
    bat.V_max = getfield_default(arch.bat, 'V_max_V',  Inf);
    bat.P_min = -arch.bat.P_max_charge_kW;
    bat.P_max =  arch.bat.P_max_discharge_kW;
    bat.eta_chg = 0.95; % consistente com Jiang et al., eta_bat_chg_avg
    bat.eta_dis = 0.94; % consistente com Jiang et al., eta_bat_dis_avg
    bat.Q_cap_Ah = (bat.Qbat_kWh * 1000) / bat.Voc;
    bat.deg_param = struct('D',0.01115,'E',3.899,'F',-65.49,'G',8310,'H',141,'I',0.422,'J',-0.6476); % ref 33 (Zhang et al.)
    bat.deg_T_K = 296.15;
    bat.deg_scale = 1/4.6;

    conv.eta_dc = arch.conv.eta_dc;
    conv.eta_dc1 = arch.conv.eta_dc1;
    conv.eta_dc2 = arch.conv.eta_dc2;

    % Capacidade eletrica do conversor (V x I), quando informada em arch
    % (ver arquitetura_embarcacao_h2.m, secao 6). So aperta o limite se
    % a capacidade do conversor for MENOR que o P_max/P_min declarado
    if isfield(arch.conv,'I_max_fc_A')
        P_conv_fc_kW = (arch.ship.dc_bus_voltage_V * arch.conv.I_max_fc_A)/1000;
        fc.P_max_tot = min(fc.P_max_tot, P_conv_fc_kW);
    end
    if isfield(arch.conv,'I_max_bat_A')
        P_conv_bat_kW = (arch.ship.dc_bus_voltage_V * arch.conv.I_max_bat_A)/1000;
        bat.P_max = min(bat.P_max,  P_conv_bat_kW);
        bat.P_min = max(bat.P_min, -P_conv_bat_kW);
    end

    nmpc.N = cenario.nmpc.N;
    nmpc.Ts = cenario.nmpc.Ts;
    nmpc.S_base = arch.fc.P_max_tot_kW; % potencia de base para o p.u. = P_max_tot do MFCS (nominal, antes do corte por conversor)
    nmpc.pesos = arch.ems.pesos.modo(3).base; % valor inicial qualquer; sobrescrito por passo dentro do loop
    nmpc.options = optimoptions('fmincon','Algorithm','sqp','Display','off','MaxFunctionEvaluations',3000);

    % PILAR 2 (Frequency Decoupling / LPF) e PILARES 3/4 (MLD + DP offline)
    nmpc.T_lpf_s = arch.ems.T_lpf_s;
    nmpc.dp_cfg = arch.ems.dp;

    %% Fonte extra
    extra.usa = isfield(arch,'fonte_extra') && isfield(arch.fonte_extra,'usa') && arch.fonte_extra.usa;
    if extra.usa
        extra.eta_conv = arch.fonte_extra.eta_conv;
        extra.custo_kg_por_kWh = getfield_default(arch.fonte_extra, 'custo_kg_por_kWh', 0);
        extra.P_rated_kWp = getfield_default(arch.fonte_extra, 'P_rated_kWp', inf);
    end
    
end
