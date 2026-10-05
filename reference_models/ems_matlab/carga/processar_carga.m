function sinais = processar_carga(~, P_load_kW_original, arch, conting)
%PROCESSAR_CARGA Classifica a carga (propulsao/hotelaria/auxiliares),
%aplica contingencia (falha de motor) e converte para o equivalente no
%barramento DC, descontando as perdas do lado da carga.
%define o perfil bruto (t_min, P_load_kW_original) e a demanda nos terminais 
%das cargas (motores/hotelaria via ramo AC, auxiliares via ramo DC)
% Não define o perfil no barramento DC. Para o balanco de potencia das fontes ser
%correto, converte-se para o equivalente no barramento DC:
% P_load_barramento = (P_prop + P_hotel)/eta_inv + P_aux/eta_dc_aux

    Nt = length(P_load_kW_original);

    % Estimativa de modo so para separar as fracoes de
    % carga via classificar_cargas
    modo_aprox = 3 * ones(Nt,1); % default: "cruzeiro/manobra"
    modo_aprox(P_load_kW_original < arch.ems.modo.thresh_porto_kW) = 1; % "porto/atracado"

    P_prop_est = zeros(Nt,1);
    P_hotel_est = zeros(Nt,1);
    P_aux_est = zeros(Nt,1);
    for kk = 1:Nt
        [P_prop_est(kk), P_hotel_est(kk), P_aux_est(kk)] = ...
            classificar_cargas(P_load_kW_original(kk), modo_aprox(kk));
    end

    % Capacidade de propulsao disponivel: vale tanto para operacao
    % normal quanto sob contingencia (sem falha, N_motores_ok =
    % arch.motor.N_motors).
    N_motores_ok = arch.motor.N_motors;
    if conting.ativa
        N_motores_ok = max(arch.motor.N_motors - conting.motores_falhos, 0);
    end
    P_prop_max_kW = N_motores_ok * arch.motor.P_rated_each_kW;

    if any(P_prop_est > P_prop_max_kW)
        n_viol = sum(P_prop_est > P_prop_max_kW);
        warning(['Demanda de propulsão excede a capacidade dos %d motor ' ...
            'disponivel (%.0f kW) em %d de %d passos -- sera saturada ' ...
            'no limite fisico do motor.'], ...
            N_motores_ok, P_prop_max_kW, n_viol, Nt);
    end
    % CRITICA, sempre saturada no limite fisico do motor
    % disponivel 
    P_prop_est = min(P_prop_est, P_prop_max_kW);

    if conting.ativa
        P_hotel_est = P_hotel_est * conting.corte_hotel_frac; % NAO-CRITICA, cortada
        % P_aux_est (CRITICA: sensores/controle/seguranca) mantida integral
        fprintf('CONTINGÊNCIA ATIVA: %d motor(es) falho(s) de %d. Propulsao limitada a %.0f kW.\n', ...
            conting.motores_falhos, arch.motor.N_motors, P_prop_max_kW);
    end

    P_load_kW = (P_prop_est + P_hotel_est)/arch.inverter.eta_inv + P_aux_est/arch.conv.eta_dc_aux;

    reducao_media_kW = mean(P_load_kW_original - P_load_kW);
    sufixo_msg = '';
    if conting.ativa, sufixo_msg = ' + contingência'; end
    fprintf('Perfil ajustado (perdas de carga%s): variacao media de %.1f kW (%.1f%%) vs. perfil digitalizado.\n', ...
        sufixo_msg, reducao_media_kW, 100*reducao_media_kW/mean(P_load_kW_original));

    sinais.P_load_kW = P_load_kW;
    sinais.P_load_kW_original = P_load_kW_original;
    sinais.P_prop_est = P_prop_est;
    sinais.P_hotel_est = P_hotel_est;
    sinais.P_aux_est = P_aux_est;
    sinais.N_motores_ok = N_motores_ok;
    sinais.P_prop_max_kW = P_prop_max_kW;
    sinais.conting = conting;
end
