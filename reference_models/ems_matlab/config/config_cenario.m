function cenario = config_cenario(nome, opts)
%CONFIG_CENÁRIO Ponto ÚNICO de configuração por aplicação/cenário.
%PARA RODAR O EMS EM OUTRA EMBARCACAO / OUTRO PERFIL DE CARGA: adicione
%um novo 'case' (copie o template 'exemplo_csv_generico' abaixo).
%Nenhum outro arquivo do projeto precisa ser tocado -> main.m só troca
% o NOME_CENARIO na linha 23.
%
%'opts' (opcional) -- struct usada por cenarios PARAMETRIZAVEIS (ex.:
%'walkforward_2h', que precisa saber qual scenario/profile/start_hour
%escolher dentro do CSV walk-forward). Cenarios fixos ignoram 'opts'.

if nargin < 2 || isempty(opts); opts = struct(); end
DADOS_DIR = fullfile(fileparts(mfilename('fullpath')), '..', 'dados');

switch nome

    case 'artigo_zhang_12am'
        cenario.tag  = '12am';
        cenario.N_fc = 2;
        cenario.arch_fn = @arquitetura_embarcacao_h2;
        cenario.pv_csv = fullfile(DADOS_DIR, 'Modelo_solar_12am.csv'); % muda a hora a cada cenario: 7am, 12am, 16pm, 18pm
        cenario.perfil.tipo    = 'mat_artigo';
        cenario.perfil.arquivo = fullfile(DADOS_DIR, 'layer1_data_artg1.mat'); % curva de carga (fig 4a/4b) + curva eff FC
        cenario.eff_fc.tipo    = 'tabela_mat';
        cenario.eff_fc.arquivo = fullfile(DADOS_DIR, 'layer1_data_artg1.mat');
        cenario.fonte_extra_csv = fullfile(DADOS_DIR, 'sua_fonte_extra.csv'); % colunas: t_min, P_kW - CRIAR CSV
        cenario.nmpc.N  = 3;  % horizonte
        cenario.nmpc.Ts = 60; % [s] 1 minuto
        cenario.conting = struct('ativa', false, 'motores_falhos', 1, 'corte_hotel_frac', 0.5);

    case 'artigo_zhang_7am'
        cenario = config_cenario('artigo_zhang_12am');
        cenario.tag = '7am';
        cenario.pv_csv = fullfile(DADOS_DIR, 'Modelo_solar_7am.csv');

    case 'artigo_zhang_16pm'
        cenario = config_cenario('artigo_zhang_12am');
        cenario.tag = '16pm';
        cenario.pv_csv = fullfile(DADOS_DIR, 'Modelo_solar_16pm.csv');

    case 'artigo_zhang_18pm'
        cenario = config_cenario('artigo_zhang_12am');
        cenario.tag = '18pm';
        cenario.pv_csv = fullfile(DADOS_DIR, 'Modelo_solar_18pm.csv');

    case 'artigo_zhang_12am_contingencia'
        cenario = config_cenario('artigo_zhang_12am');
        cenario.tag = '12am_conting';
        cenario.conting = struct('ativa', true, 'motores_falhos', 1, 'corte_hotel_frac', 0.5);

    case 'exemplo_csv_generico'
        % TEMPLATE para uma nova aplicacao: perfil de carga generico via
        % CSV proprio (sem a referencia de FC do artigo -- ver
        % arch.ems.usa_referencia_fc = false na arquitetura), curva de
        % eficiencia da FC via modelo analitico. Copie este bloco,
        % ajuste os caminhos/nomes e a arquitetura.
        cenario.tag  = 'nova_app';
        cenario.N_fc = 2;
        cenario.arch_fn = @arquitetura_embarcacao_h2; % troque p/ sua propria arquitetura_*.m

        cenario.pv_csv = fullfile(DADOS_DIR, 'pv_nova_app.csv');

        cenario.perfil.tipo    = 'csv_generico';
        cenario.perfil.arquivo = fullfile(DADOS_DIR, 'carga_nova_app.csv'); % colunas: t_min, P_kW [, Pfc_req]
        cenario.perfil.Ts_min  = 1; % reamostra para grade uniforme de 1 min

        cenario.eff_fc.tipo    = 'modelo_analitico';

        cenario.nmpc.N  = 3;
        cenario.nmpc.Ts = 60;

        cenario.conting = struct('ativa', false, 'motores_falhos', 1, 'corte_hotel_frac', 0.5);

        case 'rede_copel_b1_util'
    cenario.tag  = 'copel_b1_util';
    cenario.N_fc = 2;
    cenario.arch_fn = @arquitetura_embarcacao_h2;
    cenario.pv_csv = fullfile(DADOS_DIR, 'pv_foz_agosto_1min.csv');
    cenario.perfil.tipo    = 'csv_generico';
    cenario.perfil.arquivo = fullfile(DADOS_DIR, 'carga_copel_b1_util.csv');
    cenario.perfil.Ts_min  = 1;
    cenario.eff_fc.tipo    = 'modelo_analitico';
    cenario.nmpc.N  = 3;
    cenario.nmpc.Ts = 60;
    cenario.conting = struct('ativa', false, 'motores_falhos', 1, 'corte_hotel_frac', 0.5);

case 'rede_copel_b1_sabado'
    cenario = config_cenario('rede_copel_b1_util');
    cenario.tag = 'copel_b1_sabado';
    cenario.perfil.arquivo = fullfile(DADOS_DIR, 'carga_copel_b1_sabado.csv');

case 'rede_copel_b1_domingo'
    cenario = config_cenario('rede_copel_b1_util');
    cenario.tag = 'copel_b1_domingo';
    cenario.perfil.arquivo = fullfile(DADOS_DIR, 'carga_copel_b1_domingo.csv');

    case 'perfis_2h'
        % Cenarios de carga de 2h (walk-forward): CSV empilha 3 cenarios
        % de operacao ('Otimista'/'Ideal'/'Pessimista') x 3 perfis de uso
        % ('Econômico'/'Normal'/'Máxima') x 15 horarios de inicio (8h..22h)
        % = 135 janelas de 2h. Escolha qual rodar passando 'opts' na
        % chamada, ex.:
        %   opts.scenario   = 'Ideal';       % 'Otimista' | 'Ideal' | 'Pessimista'
        %   opts.profile    = 'Econômico';   % 'Econômico' | 'Normal' | 'Máxima'
        %   opts.start_hour = 8;             % 8, 9, 10, ..., 22
        %   cenario = config_cenario('walkforward_2h', opts);
        wf_scenario = getfield_default(opts, 'scenario',   'Ideal');
        wf_profile  = getfield_default(opts, 'profile',    'Econômico');
        wf_start_h  = getfield_default(opts, 'start_hour', 8);

        cenario.tag  = sprintf('%s_%s_%02dh', wf_scenario, wf_profile, wf_start_h);
        cenario.N_fc = 2;
        cenario.arch_fn = @arquitetura_embarcacao;

        % PV: o CSV walk-forward nao traz geracao solar propria; usa-se
        % por padrao o perfil solar de meio-dia ja existente no projeto.
        % Troque para o Modelo_solar_*.csv mais proximo do wf_start_h
        % escolhido, se preferir.
        cenario.pv_csv = fullfile(DADOS_DIR, 'Modelo_solar_12am.csv');

        cenario.perfil.tipo       = 'csv_walkforward';
        cenario.perfil.arquivo    = fullfile(DADOS_DIR, 'ems_walkforward.csv');
        cenario.perfil.scenario   = wf_scenario;
        cenario.perfil.profile    = wf_profile;
        cenario.perfil.start_hour = wf_start_h;

        cenario.eff_fc.tipo = 'modelo_analitico';

        cenario.nmpc.N  = 3;
        cenario.nmpc.Ts = 60;
        cenario.conting = struct('ativa', false, 'motores_falhos', 1, 'corte_hotel_frac', 0.5);

        fprintf('Cenario walk-forward escolhido: %s x %s, inicio %02d:00 (tag: %s)\n', ...
            wf_scenario, wf_profile, wf_start_h, cenario.tag);

    otherwise
        error('config_cenario:desconhecido', ...
            'Cenario "%s" nao encontrado. Adicione um case em config_cenario.m.', nome);
end