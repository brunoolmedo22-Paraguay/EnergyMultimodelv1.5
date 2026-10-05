function exportar_dashboard_csv(res, sinais, nmpc, conv, cenario, nome_alg, caminho_csv)
%EXPORTAR_DASHBOARD_CSV Exporta series temporais da simulacao (res/sinais)
%para um arquivo .csv, uma linha por passo simulado -- mesmo padrao ja
%usado em gerar_tabela_resultados.m
%%----------------------------------------------------
% Posteriormente configurar conforme Pedro solicitar %
%%-----------------------------------------------------
    if nargin < 7 || isempty(caminho_csv)
        caminho_csv = 'dashboard_data.csv';
    end

    t_sim = res.t_sim;
    S = nmpc.S_base;

    %% series por passo
    t_min = sinais.t_min(t_sim)';
    P_load_kW = sinais.P_load_kW(t_sim)';
    Ppv_kW = sinais.Ppv_kW(t_sim)';
    Pfc_setpoint_kW = res.Pfc_hist(t_sim)' * S;
    Pfc_entregue_kW = res.Pfc_s_real_hist(t_sim)';
    Pbat_setpoint_kW = res.Pbat_setpoint_hist(t_sim)' * S;
    Pbat_kW = res.Pbat_hist(t_sim)' * S;
    SOC = res.SOC_hist(t_sim)';
    n_st = res.n_st_hist(t_sim)';
    mH2_kg = res.mH2_hist(t_sim)';
    mH2_acum_kg = cumsum(mH2_kg);
    Dbat_acum = cumsum(res.Dbat_hist(t_sim)');
    modo = res.modo_hist(t_sim)';
    Pfc_meta_kW = res.Pfc_meta_hist(t_sim)';
    Pfc_refino_kW = res.Pfc_refino_hist(t_sim)';

    if isfield(res, 'deficit_nao_atendido_hist')
        deficit_kW = res.deficit_nao_atendido_hist(t_sim)';
    else
        deficit_kW = zeros(size(t_min));
    end

    n = numel(t_min);

    %% metadados/constantes repetidas em toda linha 
    cenario_col = repmat(string(cenario.tag), n, 1);
    algoritmo_col = repmat(string(nome_alg), n, 1);
    N_fc_col = repmat(max(n_st), n, 1);
    Ts_s_col = repmat(nmpc.Ts, n, 1);

    %% monta a tabela e escreve 
    T = table(cenario_col, algoritmo_col, N_fc_col, Ts_s_col, ...
        t_min(:), P_load_kW(:), Ppv_kW(:), ...
        Pfc_setpoint_kW(:), Pfc_entregue_kW(:), ...
        Pbat_setpoint_kW(:), Pbat_kW(:), ...
        SOC(:), n_st(:), mH2_kg(:), mH2_acum_kg(:), Dbat_acum(:), modo(:), ...
        deficit_kW(:), Pfc_meta_kW(:), Pfc_refino_kW(:), ...
        'VariableNames', { ...
            'cenario','algoritmo','N_fc','Ts_s', ...
            't_min','P_load_kW','Ppv_kW', ...
            'Pfc_setpoint_kW','Pfc_entregue_kW', ...
            'Pbat_setpoint_kW','Pbat_kW', ...
            'SOC','n_st','mH2_kg','mH2_acum_kg','Dbat_acum','modo', ...
            'deficit_kW','Pfc_meta_kW','Pfc_refino_kW'});

    writetable(T, caminho_csv);
    fprintf('[dashboard] Dados exportados para: %s\n', caminho_csv);
end