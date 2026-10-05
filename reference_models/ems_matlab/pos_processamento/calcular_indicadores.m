function ind = calcular_indicadores(res, sinais, conv, nmpc, extra)
    if nargin < 5 || isempty(extra); extra.usa = false; end
%CALCULAR_INDICADORES Energia por fonte/carga, H2 total, degradacao
%acumulada e erro de balanco -- a partir dos historicos devolvidos por
%ems_dispatch.m. 
    t_sim = res.t_sim;
    S = nmpc.S_base; Ts = nmpc.Ts;

    ind.Pfc_kW = res.Pfc_s_real_hist(t_sim);  % PILAR 1: potencia REALMENTE ENTREGUE pela FC (planta real, tau_FC_s) 
    ind.Pfc_setpoint_kW = res.Pfc_hist(t_sim) * S; % setpoint (demanda) escolhido pelo otimizador
    ind.Pbat_kW = res.Pbat_hist(t_sim) * S;
    ind.Ppv_kW = sinais.Ppv_kW(t_sim);
    ind.P_load_kW = sinais.P_load_kW(t_sim);

    if isfield(res, 'Pext_hist')
        ind.Pext_kW = res.Pext_hist(t_sim);
    else
        ind.Pext_kW = zeros(size(t_sim(:)));
    end
    
    Pbat_desc = max(ind.Pbat_kW, 0);
    Pbat_carga = min(ind.Pbat_kW, 0);

    ind.E_load = sum(ind.P_load_kW) * Ts/3600;
    ind.E_fc = sum(ind.Pfc_kW)    * Ts/3600;
    ind.E_pv = sum(ind.Ppv_kW)    * Ts/3600;
    ind.E_bat_d = sum(Pbat_desc)     * Ts/3600;
    ind.E_bat_c = abs(sum(Pbat_carga)) * Ts/3600;
    ind.E_prop = sum(sinais.P_prop_est(t_sim))  * Ts/3600;
    ind.E_hotel = sum(sinais.P_hotel_est(t_sim)) * Ts/3600;
    ind.E_aux = sum(sinais.P_aux_est(t_sim))   * Ts/3600;
    ind.H2_total = sum(res.mH2_hist(t_sim));
    ind.Dbat_tot = sum(res.Dbat_hist(t_sim));
    ind.E_extra = sum(ind.Pext_kW) * Ts/3600;

    % Balanco no barramento DC (deve ser ~0, ja garantido pela restricao
    % de igualdade dentro do NMPC
    idx_v = t_sim(2:end);
    Pbat_idx = ind.Pbat_kW(idx_v);

    eta_dc2_dir = (Pbat_idx>=0)*conv.eta_dc2 + (Pbat_idx<0)/conv.eta_dc2;
    contrib_extra_idx = zeros(size(idx_v(:)));
    if isfield(extra,'usa') && extra.usa
        contrib_extra_idx = extra.eta_conv * ind.Pext_kW(idx_v);
    end
    ind.erro_total = (conv.eta_dc1*ind.Pfc_kW(idx_v) + eta_dc2_dir(:).*Pbat_idx(:) + conv.eta_dc*ind.Ppv_kW(idx_v) + contrib_extra_idx(:)) ...
                 - ind.P_load_kW(idx_v);

    diff_meta_refino = abs(res.Pfc_meta_hist(t_sim) - res.Pfc_refino_hist(t_sim));
    ind.diff_media  = mean(diff_meta_refino);
    ind.diff_maxima = max(diff_meta_refino);

    % PILAR 1: o quanto a potencia ENTREGUE atrasa em
    % relacao ao SETPOINT demandado 
    ind.erro_lag_pilar1_medio = mean(abs(ind.Pfc_setpoint_kW(2:end) - ind.Pfc_kW(2:end)));

    % Demanda real NAO atendida, apos a bateria compensar o que a
    % FC realmente conseguiu entregar 
    if isfield(res, 'deficit_nao_atendido_hist')
        ind.deficit_kW = res.deficit_nao_atendido_hist(t_sim);
        ind.deficit_total_kWh = sum(ind.deficit_kW) * Ts/3600;
        ind.deficit_max_kW = max(ind.deficit_kW);
        ind.deficit_n_passos = sum(ind.deficit_kW > 1e-6);
    else
        ind.deficit_kW = zeros(size(t_sim(:)));
        ind.deficit_total_kWh = 0; ind.deficit_max_kW = 0; ind.deficit_n_passos = 0;
    end
end
