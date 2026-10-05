function [t_min, P_load_kW, Pfc_req_kW] = carregar_perfil_csv(csv_path, perfil_cfg)
%CARREGAR_PERFIL_CSV Loader generico de perfil de carga a partir de um
%CSV com colunas de tempo e potencia. Mesmo CONTRATO de
%preparar_carga_artigo.m ([t_min, P_load_kW, Pfc_req_kW]) -- e o que
%permite trocar de aplicacao so mudando o config, sem tocar em
%carregar_perfil_carga.m, processar_carga.m, ems_dispatch.m, etc.
%
%Colunas esperadas: "t_min"/"tempo"/"time" e "P_kW"/"potencia"/"power"/
%"load". Coluna opcional "Pfc_req"/"fc_ref" para a referencia de FC (so
%usada se arch.ems.usa_referencia_fc = true); se ausente, devolve zeros.
    if ~isfile(csv_path)
        error('Arquivo de perfil de carga nao encontrado: %s', csv_path);
    end
    T = readtable(csv_path);
    nomes = lower(string(T.Properties.VariableNames));
    idx_t = find(contains(nomes,"t_min")|contains(nomes,"tempo")|contains(nomes,"time"),1);
    idx_p = find(contains(nomes,"p_kw")|contains(nomes,"potencia")|contains(nomes,"power")|contains(nomes,"load"),1);
    if isempty(idx_t)||isempty(idx_p)
        error('Renomeie as colunas do CSV %s para algo como "t_min" e "P_kW".', csv_path);
    end
    t_min     = double(T{:,idx_t});
    P_load_kW = double(T{:,idx_p});

    idx_ref = find(contains(nomes,"pfc_req")|contains(nomes,"fc_ref"),1);
    if ~isempty(idx_ref)
        Pfc_req_kW = double(T{:,idx_ref});
    else
        Pfc_req_kW = zeros(size(P_load_kW));
    end

    if isfield(perfil_cfg,'Ts_min') && perfil_cfg.Ts_min > 0
        % reamostra para grade uniforme de Ts_min, se pedido no config
        t_uniforme = (min(t_min):perfil_cfg.Ts_min:max(t_min))';
        P_load_kW  = interp1(t_min, P_load_kW,  t_uniforme, 'linear');
        Pfc_req_kW = interp1(t_min, Pfc_req_kW, t_uniforme, 'linear');
        t_min = t_uniforme;
    end
end
