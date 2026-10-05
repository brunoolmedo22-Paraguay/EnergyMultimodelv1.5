function Ppv_kW = carregar_pv(pv_csv, t_min, arch, t0_datetime)
%CARREGAR_PV Le a serie de potencia PV e satura na potencia nominal do
%arranjo (arch.pv.P_rated_kWp). Reescrito para usar ler_serie_csv.m em vez
%de carregar_fonte_csv.m (removido).
%
%MOTIVO da reescrita, nao so troca de chamada: os CSVs de PV do projeto
%NAO tem um schema unico --
%   Modelo_solar_*.csv    -> colunas timestamp, potencia_gerada_W  (absoluto, W)
%   pv_foz_agosto_1min.csv-> colunas t_min, P_kW                   (relativo, kW)
%carregar_fonte_csv.m escondia isso atras de contains() e SEMPRE dividia
%por 1000 (assumindo Watts) -- errado para qualquer CSV que ja venha em kW.
%Aqui os dois schemas sao reconhecidos explicitamente; um terceiro schema
%gera erro claro em vez de silenciosamente casar a coluna errada.
%
%t0_datetime: mesmo t0 absoluto usado em montar_fontes.m, para alinhar o
%schema "timestamp" a grade t_min da simulacao. Nao usado no schema
%"t_min" (ja vem relativo).

    fprintf('Carregando PV de: %s\n', pv_csv);
    if ~isfile(pv_csv)
        error('carregar_pv:arquivo', 'Arquivo nao encontrado: %s', pv_csv);
    end
    T = readtable(pv_csv, 'VariableNamingRule', 'preserve');
    nomes = strtrim(string(T.Properties.VariableNames));

    if any(strcmpi(nomes,'timestamp')) && any(strcmpi(nomes,'potencia_gerada_W'))
        if nargin < 4 || isempty(t0_datetime)
            error('carregar_pv:t0', ...
                'CSV "%s" usa timestamp absoluto: informe t0_datetime.', pv_csv);
        end
        t_abs = T{:, strcmpi(nomes,'timestamp')};
        if ~isdatetime(t_abs), t_abs = datetime(string(t_abs)); end
        tn = minutes(t_abs(:) - t0_datetime);
        Ppv_kW = ler_serie_csv(T, 'potencia_gerada_W', 'W', tn, t_min, 'linear', false);

    elseif any(strcmpi(nomes,'t_min')) && any(strcmpi(nomes,'P_kW'))
        tn = T{:, strcmpi(nomes,'t_min')};
        Ppv_kW = ler_serie_csv(T, 'P_kW', 'kW', tn, t_min, 'linear', false);

    else
        error('carregar_pv:schema', ...
            ['CSV "%s" nao bate com nenhum schema conhecido de PV. ' ...
             'Esperado "timestamp,potencia_gerada_W" ou "t_min,P_kW". ' ...
             'Colunas encontradas: %s'], pv_csv, strjoin(cellstr(nomes), ', '));
    end

    % fora da janela do CSV: NaN -> 0 (sem geracao), nunca extrapolado.
    % Comportamento antigo extrapolava linear -- podia inventar potencia
    % fora do horizonte coberto pelo CSV.
    Ppv_kW(isnan(Ppv_kW)) = 0;
    Ppv_kW = min(max(Ppv_kW(:), 0), arch.pv.P_rated_kWp);

    Ts_h = (t_min(2)-t_min(1))/60;
    fprintf('PV integrado: pico=%.1f kW | media=%.1f kW | total=%.2f kWh\n', ...
        max(Ppv_kW), mean(Ppv_kW), sum(Ppv_kW)*Ts_h);
end
