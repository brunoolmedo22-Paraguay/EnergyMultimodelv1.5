function [t_min, P_load_kW_1min, Pfc_req_kW_1min] = preparar_carga_artigo(caminho_mat)
% Ajusta para minuto as cargas fig 4a e 4b de Zhang et al 2025, artigo considera de 1 em 1
% segundo

    D = load(caminho_mat);
    t_s = D.t_s(:);
    P_load_kW = D.P_load_kW(:);

    minuto = floor((t_s - t_s(1)) / 60); 
    n_min = max(minuto) + 1;
    t_min = (0:n_min-1)';

    P_load_kW_1min = reamostrar_por_minuto(P_load_kW, minuto, t_min);

    if nargout > 2
        if ~isfield(D, 'Pfc_req_kW')
            error('preparar_carga_artigo:semPfcReq', ...
                  ['%s nao tem a variavel Pfc_req_kW (Fig. 4b digitalizada). ' ...
                   'Regenere o .mat ou peca so 2 saidas desta funcao.'], caminho_mat);
        end
        Pfc_req_kW = D.Pfc_req_kW(:);
        Pfc_req_kW_1min = reamostrar_por_minuto(Pfc_req_kW, minuto, t_min);
    end
end

function serie_1min = reamostrar_por_minuto(serie_s, minuto, t_min)
% Média dentro de cada minuto 
    n_min = numel(t_min);
    serie_1min = nan(n_min,1);
    for m = 0:n_min-1
        idx = (minuto == m);
        if any(idx)
            serie_1min(m+1) = mean(serie_s(idx));
        end
    end
    faltando = isnan(serie_1min);
    if any(faltando)
        serie_1min(faltando) = interp1(t_min(~faltando), serie_1min(~faltando), t_min(faltando), 'linear', 'extrap');
    end
end
