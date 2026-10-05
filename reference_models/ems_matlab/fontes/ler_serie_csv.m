function y = ler_serie_csv(T, col, unidade, t_nativo_min, t_min, metodo, permitir_extrap)
%LER_SERIE_CSV Extrai UMA coluna de uma tabela ja lida e a reamostra na
%grade de simulacao t_min (minutos desde o inicio da simulacao).
%
%SUBSTITUI o casamento por contains() de carregar_fonte_csv.m. Ali,
%find(contains(nomes,"power"),1) pega power_unit_kw na eolica e
%power_requested_mw na termica -- sempre a coluna errada, e sem erro.
%Aqui o nome da coluna e EXPLICITO e a funcao falha alto se nao existir.
%
%Entradas:
%   T         table ja lida (readtable com 'VariableNamingRule','preserve')
%   col       nome EXATO da coluna (char). '' -> retorna [] (campo opcional)
%   unidade   'W' | 'kW' | 'MW' | 'pu_none' | 'pct' | 'A' | 'V' | 'nenhuma'
%             converte tudo para kW (potencia) ou fracao (pct -> 0..1).
%             'nenhuma' passa o valor cru (custos em R$, rampas, etc.)
%   t_nativo_min  vetor de tempo NATIVO do CSV, em minutos, ja alinhado
%             ao mesmo t0 da simulacao (ver alinhar_tempo.m embutida)
%   t_min     grade de simulacao (minutos)
%   metodo    'linear'  -> series continuas (vento, corrente de bateria)
%             'previous'-> series em degrau/ZOH (limites horarios da
%                          termica, inflexibilidade, custo por bloco)
%             'nearest' -> flags e estados discretos
%   permitir_extrap  logical. false (default) => NaN fora da janela do CSV,
%             que e detectado depois em carregar_fontes.m. O 'extrap'
%             linear do loader antigo inventa potencia fora do horizonte.

    if nargin < 7 || isempty(permitir_extrap); permitir_extrap = false; end
    if isempty(col); y = []; return; end

    nomes = string(T.Properties.VariableNames);
    idx = find(strcmpi(strtrim(nomes), strtrim(string(col))), 1);
    if isempty(idx)
        error('ler_serie_csv:colunaAusente', ...
            ['Coluna "%s" nao existe no CSV.\nColunas disponiveis:\n  %s'], ...
            col, strjoin(cellstr(nomes), '\n  '));
    end

    v = T{:, idx};
    if ~isnumeric(v)
        v = double(categorical(string(v)));  % estados/flags textuais -> codigo
    end
    v = double(v(:));

    % ---- conversao de unidade -> kW (potencia) ou fracao ----
    switch lower(string(unidade))
        case "w",       v = v / 1e3;
        case "kw",      % ja esta em kW
        case "mw",      v = v * 1e3;
        case "pct",     v = v / 100;
        case {"a","v","pu_none","nenhuma",""}  % passa cru
        otherwise
            error('ler_serie_csv:unidade', 'Unidade "%s" desconhecida.', unidade);
    end

    % ---- reamostragem para a grade de simulacao ----
    t_nativo_min = double(t_nativo_min(:));
    [t_u, ia] = unique(t_nativo_min, 'stable');
    v = v(ia);
    [t_u, ord] = sort(t_u); v = v(ord);

    if numel(t_u) == 1
        y = repmat(v, numel(t_min), 1);
        return;
    end

    if permitir_extrap
        y = interp1(t_u, v, t_min(:), metodo, 'extrap');
    else
        y = interp1(t_u, v, t_min(:), metodo, NaN);
    end
    y = y(:);
end
