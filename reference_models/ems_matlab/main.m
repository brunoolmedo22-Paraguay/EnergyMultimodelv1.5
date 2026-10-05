%% MAIN.M -> EMS: despacho independente de modelo entre fontes externas
%
% A fisica de cada fonte (FC, bateria, termica, eolica) e responsabilidade
% da PLATAFORMA DE MODELAGEM, fora deste projeto -- os 4 CSVs em dados/ sao
% a interface. Este main so: (1) monta o array de fontes no formato
% contrato_fonte, (2) roda o despacho, (3) apresenta o resultado.
%
% Este arquivo SUBSTITUI o main.m original. As diferencas:
%   - nao chama mais montar_equipamentos/ems_dispatch (removidos)
%   - chama montar_fontes.m (novo) em vez de carregar_pv+carregar_fonte_extra
%   - chama despacho.m (novo) em vez de ems_dispatch.m
%   - carga/, config/config_cenario.m e pos_processamento/ mantidos,
%     mas a parte de pos_processamento AINDA NAO foi adaptada ao formato
%     novo de 'res' (ver aviso no fim deste arquivo)

clc; clear; close all
addpath(genpath(fileparts(mfilename('fullpath'))));

%% CONFIGURACAO
NOME_CENARIO = 'perfis_2h';
ID_ALGORITMO = 2;   % 1=GA 2=GWO 3=NGO 0=so SQP (sem metaheuristica)

opts.scenario   = 'Ideal';
opts.profile    = 'Normal';
opts.start_hour = 12;

% t0 absoluto de referencia -- OBRIGATORIO agora porque os 4 CSVs da
% plataforma trazem timestamp absoluto e podem cobrir janelas diferentes.
% Ajuste para o instante real do seu cenario.
cenario_t0_datetime = datetime(2016,9,1,16,0,0);

%% MONTAGEM
cenario = config_cenario(NOME_CENARIO, opts);
arch = cenario.arch_fn(cenario.N_fc);
nome_alg = nome_algoritmo(ID_ALGORITMO);
fprintf('Cenario: %s | Algoritmo: %s\n', cenario.tag, nome_alg);

econ = parametros_economicos();

%% ENTRADAS
[t_min, P_load_kW, ~] = carregar_perfil_carga(cenario);
% Enquanto bateria.csv nao tiver corrente/tensao suficientes para calibrar
% Rint com confianca (poucos minutos de dado, sem os dois sentidos de
% corrente bem representados), rode sem ela em vez de travar o resto do
% pipeline. Volte para true assim que o CSV completo (2h) estiver pronto.
INCLUIR_BATERIA = false;

fontes = montar_fontes(cenario, arch, t_min, cenario_t0_datetime, econ, INCLUIR_BATERIA);

% PV mantido como estava: reduz a carga liquida diretamente (nao e
% despachavel nem tem custo, entao nao precisa virar contrato_fonte;
% se quiser curtailment de PV tambem, trate-o como a eolica).
Ppv_kW = carregar_pv(cenario.pv_csv, t_min, arch, cenario_t0_datetime);
P_load_liquida_kW = max(P_load_kW - arch.conv.eta_dc*Ppv_kW, 0);

%% CONFIG DO DESPACHO
cfg.Ts_s = cenario.nmpc.Ts;
cfg.N    = cenario.nmpc.N;
cfg.S_base = max([fontes.P_max_unid_kW] .* arrayfun(@(f) f.n_unid, fontes), [], 'all');
cfg.pen_deficit = econ.pen_deficit_rs_kWh;
cfg.pen_excesso = econ.pen_excesso_rs_kWh;
cfg.algoritmo = ID_ALGORITMO;
cfg.options = optimoptions('fmincon','Algorithm','sqp','Display','off','MaxFunctionEvaluations',3000);
cfg.teto_combos = 64;

fprintf('S_base = %.1f kW | horizonte N=%d passos de %d s\n', cfg.S_base, cfg.N, cfg.Ts_s);

%% DESPACHO
res = despacho(fontes, P_load_liquida_kW, cfg);
rel = relatorio_despacho(res, fontes, cfg);

%% AVISO -- pos-processamento
% gerar_graficos.m, calcular_indicadores.m, imprimir_balanco.m e
% gerar_tabela_resultados.m foram escritos para os campos de res.* do
% ems_dispatch.m antigo (Pfc_hist, Pbat_hist, SOC_hist, mH2_hist, ...),
% que nao existem mais. res.* agora e generico (res.P_kW, res.n_unid,
% res.SOC, indexados por res.nomes). Esses 4 arquivos precisam ser
% reescritos para o formato novo antes de voltarem a ser chamados aqui --
% NAO fiz isso ainda porque depende de que graficos/indicadores voce quer
% manter. Peca essa reescrita como proximo passo se for util.