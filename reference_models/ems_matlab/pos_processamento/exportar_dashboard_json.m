function exportar_dashboard_json(res, sinais, nmpc, conv, cenario, nome_alg, caminho_json)
%EXPORTAR_DASHBOARD_JSON Exporta series temporais + indicadores da
%simulacao (res/sinais) para um arquivo .json, no formato lido pelo
%dashboard_ems.html.
%
%USO (depois de rodar main.m ate o fim, com res/sinais/nmpc/arch.conv
%ja calculados):
%
%   exportar_dashboard_json(res, sinais, nmpc, arch.conv, cenario, ...
%                            nome_alg, 'dashboard_data.json');
%
%   Depois, abra dashboard_ems.html e carregue o arquivo
%   'dashboard_data.json' pelo botao "Carregar dados" (ou arraste o
%   arquivo para a pagina).
%
%   Se caminho_json for omitido, salva como 'dashboard_data.json' na
%   pasta atual.

    if nargin < 7 || isempty(caminho_json)
        caminho_json = 'dashboard_data.json';
    end

    t_sim = res.t_sim;
    S  = nmpc.S_base;
    Ts = nmpc.Ts;

    ind = calcular_indicadores(res, sinais, conv, nmpc);

    %% ----- series temporais (uma amostra por passo simulado) -----------
    d = struct();
    d.t_min             = sinais.t_min(t_sim);
    d.P_load_kW         = sinais.P_load_kW(t_sim);
    d.Ppv_kW            = sinais.Ppv_kW(t_sim);
    d.Pfc_setpoint_kW   = res.Pfc_hist(t_sim) * S;
    d.Pfc_entregue_kW   = res.Pfc_s_real_hist(t_sim);
    d.Pbat_setpoint_kW  = res.Pbat_setpoint_hist(t_sim) * S;
    d.Pbat_kW           = res.Pbat_hist(t_sim) * S;
    d.SOC               = res.SOC_hist(t_sim);
    d.n_st              = res.n_st_hist(t_sim);
    d.mH2_kg            = res.mH2_hist(t_sim);
    d.mH2_acum_kg       = cumsum(d.mH2_kg);
    d.Dbat_acum         = cumsum(res.Dbat_hist(t_sim));
    d.modo              = res.modo_hist(t_sim);
    d.deficit_kW        = ind.deficit_kW(:)';
    d.Pfc_meta_kW       = res.Pfc_meta_hist(t_sim);
    d.Pfc_refino_kW     = res.Pfc_refino_hist(t_sim);

    % Garantir vetores linha simples (evita estrutura de coluna estranha no JSON)
    campos = fieldnames(d);
    for i = 1:numel(campos)
        d.(campos{i}) = double(d.(campos{i})(:))';
    end

    %% ----- indicadores agregados (KPIs) --------------------------------
    kpi = struct( ...
        'E_load_kWh',   ind.E_load, ...
        'E_pv_kWh',     ind.E_pv, ...
        'E_fc_kWh',     ind.E_fc, ...
        'E_bat_desc_kWh', ind.E_bat_d, ...
        'E_bat_carga_kWh', ind.E_bat_c, ...
        'E_prop_kWh',   ind.E_prop, ...
        'E_hotel_kWh',  ind.E_hotel, ...
        'E_aux_kWh',    ind.E_aux, ...
        'H2_total_kg',  ind.H2_total, ...
        'Dbat_total',   ind.Dbat_tot, ...
        'erro_balanco_medio_kW', mean(abs(ind.erro_total)), ...
        'diff_meta_refino_media_kW', ind.diff_media, ...
        'diff_meta_refino_max_kW',   ind.diff_maxima, ...
        'atraso_pilar1_medio_kW',    ind.erro_lag_pilar1_medio, ...
        'deficit_total_kWh', ind.deficit_total_kWh, ...
        'deficit_max_kW',    ind.deficit_max_kW, ...
        'deficit_n_passos',  ind.deficit_n_passos, ...
        'SOC_final', d.SOC(end), ...
        'SOC_inicial', d.SOC(1), ...
        'n_st_max', max(d.n_st) ...
    );

    %% ----- metadados -----------------------------------------------------
    meta = struct( ...
        'cenario', string(cenario.tag), ...
        'algoritmo', string(nome_alg), ...
        'N_fc', double(max(d.n_st)), ...
        'Ts_s', double(Ts), ...
        'horizonte_min', double(d.t_min(end) - d.t_min(1)), ...
        'gerado_em', string(datestr(now, 'yyyy-mm-dd HH:MM:SS')) ...
    );

    saida = struct('meta', meta, 'kpi', kpi, 'series', d);

    txt = jsonencode(saida, 'PrettyPrint', true);
    fid = fopen(caminho_json, 'w');
    if fid == -1
        error('exportar_dashboard_json:arquivo', 'Nao foi possivel criar %s', caminho_json);
    end
    fwrite(fid, txt, 'char');
    fclose(fid);

    fprintf('[dashboard] Dados exportados para: %s\n', caminho_json);
end