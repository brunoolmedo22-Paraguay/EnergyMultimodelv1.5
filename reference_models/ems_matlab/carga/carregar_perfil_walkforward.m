function [t_min, P_load_kW, Pfc_req_kW] = carregar_perfil_walkforward(csv_path, perfil_cfg)
%CARREGAR_PERFIL_WALKFORWARD Loader do CSV de walk-forward (janelas de 2h
%de carga), que empilha VARIOS cenarios num unico arquivo (colunas
%"scenario", "profile", "start_hour"). Mesmo CONTRATO de
%carregar_perfil_csv.m ([t_min, P_load_kW, Pfc_req_kW]) -- filtra o CSV
%para a combinacao (scenario, profile, start_hour) pedida em
%perfil_cfg e devolve so essa janela de 2h, com t_min reiniciando em 0.
%
%perfil_cfg esperado (definido em config_cenario.m):
%   .scenario   -- 'Otimista' | 'Ideal' | 'Pessimista'
%   .profile    -- 'Econômico' | 'Normal' | 'Máxima'
%   .start_hour -- hora de inicio da janela (inteiro, ex.: 8, 9, ..., 22)
    if ~isfile(csv_path)
        error('Arquivo de perfil walk-forward nao encontrado: %s', csv_path);
    end
    T = readtable(csv_path, 'TextType', 'string', 'Encoding', 'UTF-8');

    campos_obrig = {'scenario','profile','start_hour'};
    for i = 1:numel(campos_obrig)
        if ~isfield(perfil_cfg, campos_obrig{i})
            error(['carregar_perfil_walkforward: perfil_cfg.%s nao definido ' ...
                '(ver config_cenario.m, case walk-forward).'], campos_obrig{i});
        end
    end

    % Casamento de colunas tolerante a BOM/maiusculas (mesmo padrao de
    % carregar_perfil_csv.m), pois o MATLAB pode sanitizar "t_min" com
    % BOM na frente do CSV para algo como "xT_min".
    nomes = lower(string(T.Properties.VariableNames));
    col_t     = T.Properties.VariableNames{find(contains(nomes,"t_min"),1)};
    col_p     = T.Properties.VariableNames{find(contains(nomes,"p_total_kw"),1)};
    col_scen  = T.Properties.VariableNames{find(contains(nomes,"scenario"),1)};
    col_prof  = T.Properties.VariableNames{find(contains(nomes,"profile"),1)};
    col_hora  = T.Properties.VariableNames{find(contains(nomes,"start_hour"),1)};

    mask = (T.(col_scen) == string(perfil_cfg.scenario)) & ...
           (T.(col_prof) == string(perfil_cfg.profile))  & ...
           (T.(col_hora) == perfil_cfg.start_hour);

    if ~any(mask)
        opcoes_scenario = unique(T.(col_scen));
        opcoes_profile  = unique(T.(col_prof));
        opcoes_hora     = unique(T.(col_hora));
        error(['carregar_perfil_walkforward: nenhuma linha encontrada para ' ...
            'scenario="%s", profile="%s", start_hour=%d.\nOpcoes disponiveis -> ' ...
            'scenario: %s | profile: %s | start_hour: %s'], ...
            string(perfil_cfg.scenario), string(perfil_cfg.profile), perfil_cfg.start_hour, ...
            strjoin(opcoes_scenario, ', '), strjoin(opcoes_profile, ', '), ...
            strjoin(string(opcoes_hora), ', '));
    end

    Tj = T(mask, :);
    Tj = sortrows(Tj, col_t);

    t_min     = double(Tj.(col_t)(:)) - double(Tj.(col_t)(1)); % reinicia em 0
    P_load_kW = double(Tj.(col_p)(:));
    Pfc_req_kW = zeros(size(P_load_kW)); % CSV nao traz referencia de FC do artigo

    if isfield(perfil_cfg,'Ts_min') && perfil_cfg.Ts_min > 0
        t_uniforme = (min(t_min):perfil_cfg.Ts_min:max(t_min))';
        P_load_kW  = interp1(t_min, P_load_kW,  t_uniforme, 'linear');
        Pfc_req_kW = interp1(t_min, Pfc_req_kW, t_uniforme, 'linear');
        t_min = t_uniforme;
    end
end
