%% CONVERTER_CURVAS_COPEL_3DIAS.M
% Gera 3 CSVs de carga (dia util, sabado, domingo) direto dos arquivos
% brutos exportados pela COPEL e gera o arquivo .MAT do perfil solar
% típico de Foz do Iguaçu em Agosto.
%
% Adaptado para resolução de 1 minuto (1440 pontos/dia).

clear; clc;

arquivos = struct( ...
    'util',    struct('arq','b0418edb-038d-4fde-b624-c318d376a734_util.csv',    'tipo','Dia Útil'), ...
    'sabado',  struct('arq','b0418edb-038d-4fde-b624-c318d376a734_sabado.csv',  'tipo','Sábado'), ...
    'domingo', struct('arq','b0418edb-038d-4fde-b624-c318d376a734_domingo.csv', 'tipo','Domingo') ...
);

companhia_alvo = 'COPEL';
subgrupo_alvo  = 'B1';
simulacao_alvo = 'Simulação 5';

% Definição do novo grid de tempo em minutos (1440 pontos: 0 a 1439)
n_pontos_alvo = 1440;
t_min_1min = (0:n_pontos_alvo-1)';

tags = fieldnames(arquivos);

for i = 1:numel(tags)
    tag = tags{i};
    info = arquivos.(tag);
    
    opts = detectImportOptions(info.arq, 'FileType', 'text');
    opts.VariableNamingRule = 'preserve';
    opts = setvaropts(opts, 'VlrDmd', 'Type', 'double', 'DecimalSeparator', ',');
    opts = setvaropts(opts, {'HorInicial','HorFinal'}, 'Type', 'char');
    
    dados = readtable(info.arq, opts);
    
    f = dados(strcmp(dados.SigCcs, companhia_alvo) & ...
              strcmp(dados.NomSubGrupoTarifario, subgrupo_alvo) & ...
              strcmp(dados.DscPrcCal, simulacao_alvo) & ...
              strcmp(dados.DscTipoDia, info.tipo), :);
          
    if isempty(f)
        error('Nenhum dado para %s (tipo=%s).', tag, info.tipo);
    end

    % Agrupa por horario e tira a media entre os Demandantes/ciclos
    [horarios_u, ~, ic] = unique(f.HorInicial);
    media_kW_96 = accumarray(ic, f.VlrDmd, [], @mean);
    [~, idx_sort] = sort(horarios_u); % ordem cronologica do dia
    media_kW_96 = media_kW_96(idx_sort);
    
    n_original = numel(media_kW_96);
    if n_original ~= 96
        warning('%s: esperado 96 horarios (15 min), obtido %d -- confira o arquivo.', tag, n_original);
    end
    
    % Tempo original em minutos (ex: 0, 15, 30, ..., 1425)
    t_min_original = (0:n_original-1)' * (24*60/n_original);
    
    % Interpolação Pchip para curva suave de 1440 pontos sem overshooting
    media_kW_1440 = interp1(t_min_original, media_kW_96, t_min_1min, 'pchip');
    
    T = table(t_min_1min, media_kW_1440, 'VariableNames', {'t_min','P_kW'});
    nome_saida = sprintf('carga_copel_b1_%s.csv', tag);
    writetable(T, nome_saida);
    
    fprintf('%-8s -> %s | pico=%.1f kW | media=%.1f kW | min=%.1f kW\n', ...
        tag, nome_saida, max(media_kW_1440), mean(media_kW_1440), min(media_kW_1440));
end

%% ----- GERACÃO PV REAL/TIPICA - FOZ DO IGUAÇU (AGOSTO) -----
file_ninja = 'ninja_pv_-25.5304_-54.5831_uncorrected (1).csv';
P_rated_kWp = 50.0; % Potência nominal instalada do sistema fotovoltaico (kWp)

if exist(file_ninja, 'file')
    % Leitura do CSV do Renewables.ninja ignorando linhas de comentário '#'
    opts_pv = detectImportOptions(file_ninja, 'FileType', 'text');
    opts_pv.CommentStyle = '#';
    dados_pv = readtable(file_ninja, opts_pv);
    
    % Conversão do horário UTC para Horário Local de Foz do Iguaçu (UTC-3)
    t_utc = datetime(dados_pv.time, 'InputFormat', 'yyyy-MM-dd HH:mm');
    t_local = t_utc - hours(3);
    
    % Filtrar apenas dados do mês de Agosto (Mês 8)
    idx_agosto = (month(t_local) == 8);
    t_agosto = t_local(idx_agosto);
    p_agosto = dados_pv.electricity(idx_agosto);
    
    % Média horária de Agosto para obter o perfil típico de 24h
    horas_agosto = hour(t_agosto);
    pv_pu_24h = zeros(24, 1);
    cap_ninja = 50000; % Capacidade base do arquivo Ninja (50.000 kW)
    for h_idx = 0:23
        pv_pu_24h(h_idx + 1) = mean(p_agosto(horas_agosto == h_idx)) / cap_ninja;
    end
else
    warning('Arquivo %s não encontrado. Utilizando valores típicos pré-calculados de Agosto.', file_ninja);
    % Perfil p.u. típico pré-calculado de Foz do Iguaçu em Agosto (0h a 23h)
    pv_pu_24h = [0; 0; 0; 0; 0; 0; 0; 0.0577; 0.2672; 0.4539; 0.5850; 0.6551; ...
                 0.6778; 0.6519; 0.5727; 0.4572; 0.3016; 0.1030; 0; 0; 0; 0; 0; 0];
end

% Interpolação suave Pchip para 1440 pontos (1 minuto)
h_centros = (0:23)' + 0.5;
h_ext = [-0.5; h_centros; 24.5];
pv_ext = [0; pv_pu_24h; 0];

h_1min = t_min_1min / 60;
pv_pu_1440 = interp1(h_ext, pv_ext, h_1min, 'pchip');
pv_pu_1440 = max(0, pv_pu_1440); % Limpa pequenos valores negativos da interpolação

% Dimensionamento em kW
P_pv_kW = pv_pu_1440 * P_rated_kWp;

% --- SALVAR ARQUIVO .MAT ---
mat_saida = 'pv_foz_agosto_1min.mat';
save(mat_saida, 't_min_1min', 'P_pv_kW', 'pv_pu_1440', 'P_rated_kWp');

% --- SALVAR ARQUIVO .CSV COMPATÍVEL ---
Tpv = table(t_min_1min, P_pv_kW, 'VariableNames', {'t_min','P_kW'});
writetable(Tpv, 'pv_foz_agosto_1min.csv');

fprintf('\n---------------- PV SOLAR (Foz do Iguaçu - Agosto) ----------------\n');
fprintf('Arquivo .MAT gerado: %s\n', mat_saida);
fprintf('Arquivo .CSV gerado: pv_foz_agosto_1min.csv\n');
fprintf('Potência Instalada: %.1f kWp | Pico: %.2f kW | Produção: %.2f kWh/dia (Yield: %.2f kWh/kWp/dia)\n', ...
    P_rated_kWp, max(P_pv_kW), sum(P_pv_kW)*(1/60), (sum(P_pv_kW)*(1/60))/P_rated_kWp);