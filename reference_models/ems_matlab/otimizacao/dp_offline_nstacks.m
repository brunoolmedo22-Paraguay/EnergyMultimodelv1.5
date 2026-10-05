function mapa = dp_offline_nstacks(sinais, arch, fc, bat, conv, eff_P_kW, eff_eta_pct, dp_cfg)
%DP_OFFLINE_NSTACKS Programacao Dinamica OFFLINE (PILAR 4) para decidir o
%NUMERO OTIMO DE STACKS DE FC ATIVOS (n_st in {0,...,N_fc}) em funcao da
%POSICAO na rota e do SOC da bateria, penalizando eventos de partida/
%parada com p*|n_st(l+1)-n_st(l)|. Gera 2 mapas 2D (posicao x SOC):
%   mapa.n_st_opt(ip,isoc)  decisao otima (numero de stacks) -- p/ cada
%                            n_st_prev possivel (3a dimensao)
%   mapa.J_opt(ip,isoc)     custo otimo [kg H2 equivalente]
%usados ONLINE em lookup_nstacks_dp.m para restringir o espaco de busca
%do MLD (Pilar 3) a uma vizinhanca pequena da sugestao offline, tornando
%o problema misto-inteiro tratavel em tempo real (2-level real-time EMS,
% Jiang et al. 2025: camada offline decide quantos stacks e a camada tatica
% online (NMPC) que decide a potência de cada equipamento a cada passo

%NOTA - "POSICAO NA ROTA": este pipeline nao possui um modelo de
%rota/distancia percorrida (so tem o perfil de carga vs. tempo,
%carregado por inteiro a priori em main.m). Aqui a "posicao" e
%aproximada pelo progresso normalizado no tempo da missao (0..1) ao
%longo do perfil conhecido. S e a aplicação vier a ter uma rota
%georreferenciada, passe um vetor real em dp_cfg.posicao_km (mesmo
%tamanho de sinais.P_load_kW) que a DP usa no lugar do tempo, sem mudar
%mais nada no pipeline.
%
%ESTADO AUMENTADO: para que a penalidade de start/stop seja tratada
%corretamente pela recursao (o custo de mudar de stack depende de QUAL
%era o stack anterior), o estado da DP e (posicao, SOC, n_st_prev) --
%isto e, para cada n_st_prev possivel existe um mapa 2D (posicao x SOC)
%proprio. mapa.n_st_opt/J_opt sao portanto arrays 3D
%(Npos x Nsoc x (N_fc+1)); lookup_nstacks_dp.m escolhe a fatia certa
%pelo n_st_prev real no instante da consulta.
%baseado em Kofler et al 2024 https://doi.org/10.1016/j.apenergy.2024.124513
%Entradas:
%   sinais struct com P_load_kW, Ppv_kW, t_min (perfil completo, conhecido a priori)
%   arch,fc,bat,conv, eff_P_kW, eff_eta_pct   mesmos structs/curvas do NMPC
%   dp_cfg    struct opcional:
%       .Npos numero de estagios/posicoes da DP (default 120)
%       .dSOC resolucao da grade de SOC (default 0.005)
%       .p_switch_kg penalidade de start/stop [kg H2 equiv. por evento]
%                     (default 0.01 )
%       .posicao_km  vetor de posicao real (opcional, ver nota acima)
%
%Saida: struct 'mapa' com pos_grid, soc_grid, nprev_grid, n_st_opt, J_opt

if nargin < 8, dp_cfg = struct(); end
Npos = getfield_default(dp_cfg, 'Npos', 20);
dSOC = getfield_default(dp_cfg, 'dSOC', 0.005);
p_kg = getfield_default(dp_cfg, 'p_switch_kg', 0.01);

N_fc = fc.Nfc;
P_max_stack = fc.P_max_tot/N_fc;
P_min_stack = fc.P_min_stack_kW;

soc_grid = (bat.SOC_min:dSOC:bat.SOC_max)';
Nsoc = numel(soc_grid);
Nnprev = N_fc + 1; % n_st_prev in {0,...,N_fc}

t_min = sinais.t_min(:);
P_load = sinais.P_load_kW(:);
Ppv = sinais.Ppv_kW(:);
Ntempo = numel(P_load);

if isfield(dp_cfg,'posicao_km') && ~isempty(dp_cfg.posicao_km)
    eixo_pos = dp_cfg.posicao_km(:);
else
    eixo_pos = (t_min - t_min(1)) / max(t_min(end)-t_min(1), eps); % 0..1
end

% Discretiza o perfil continuo em Npos estagios (media por estagio) e
% guarda a duracao real [s] de cada estagio (para integrar H2/SOC)
edges = linspace(min(eixo_pos), max(eixo_pos), Npos+1);
P_load_stage = zeros(Npos,1); Ppv_stage = zeros(Npos,1); Ts_stage = zeros(Npos,1);
t_s = t_min*60;
for ip = 1:Npos
    if ip < Npos
        idx = eixo_pos >= edges(ip) & eixo_pos < edges(ip+1);
    else
        idx = eixo_pos >= edges(ip) & eixo_pos <= edges(ip+1);
    end
    if ~any(idx), idx = max(1,round((ip-0.5)/Npos*Ntempo)); end
    P_load_stage(ip) = mean(P_load(idx));
    Ppv_stage(ip) = mean(Ppv(idx));
    t_idx = t_s(idx);
    if numel(t_idx) > 1
        Ts_stage(ip) = max(t_idx) - min(t_idx);
    else
        Ts_stage(ip) = (t_s(end)-t_s(1))/Npos;
    end
    Ts_stage(ip) = max(Ts_stage(ip), 1);
end

J_opt = inf(Npos, Nsoc, Nnprev);
n_st_opt = zeros(Npos, Nsoc, Nnprev);

% ----- Estagio terminal: penaliza desvio do SOC final em relacao ao SOC
% inicial (missao "fecha" proxima de onde comecou -- AJUSTAR se a
% aplicacao tiver um alvo de SOC final diferente)
SOC_alvo_final = bat.SOC_ini;
w_soc_final = 50; % kg-equivalente por unidade^2 de desvio 

for isoc = 1:Nsoc
    custo_terminal = w_soc_final*(soc_grid(isoc)-SOC_alvo_final)^2;
    J_opt(Npos, isoc, :) = custo_terminal;
    n_st_opt(Npos, isoc, :) = 0;
end

% Recursao backward
for ip = Npos-1:-1:1
    Ts_i = Ts_stage(ip+1); % custo de TRANSITAR do estagio ip para ip+1
    P_deficit_i = max(P_load_stage(ip) - conv.eta_dc*Ppv_stage(ip), 0);

    for isoc = 1:Nsoc
        SOC_i = soc_grid(isoc);

        for in_prev = 1:Nnprev
            n_prev = in_prev - 1;

            melhores_J = inf(N_fc+1,1);
            melhores_n = zeros(N_fc+1,1);

            for n_st = 0:N_fc
                % Regra de despacho REPRESENTATIVA (estrategica, nao a
                % otimizacao tatica completa): FC entrega ate seu teto
                % disponivel com n_st stacks; o restante fica com a
                % bateria (convencao: Pbat>0 descarrega).
                Pfc_disp = min(P_deficit_i, n_st*P_max_stack);
                if n_st > 0
                    Pfc_disp = max(Pfc_disp, min(n_st*P_min_stack, P_deficit_i));
                end
                Pbat_stage = P_deficit_i - Pfc_disp;
                Pbat_stage = min(max(Pbat_stage, bat.P_min), bat.P_max);

                step = bateria_step(Pbat_stage, bat, SOC_i, 0, Ts_i);
                SOC_next = min(max(step.SOC, bat.SOC_min), bat.SOC_max);

                if Pfc_disp > 0
                    eta = fc_efficiency(Pfc_disp/N_fc, eff_P_kW, eff_eta_pct);
                    dmH2_fc = Pfc_disp/(fc.Elow*eta*3600) * Ts_i;
                    a_ratio = 1/(fc.Elow*eta);
                else
                    dmH2_fc = 0;
                    a_ratio = 1/(fc.Elow*0.5); % eficiencia de referencia p/ custo equiv. da bateria quando FC desligada
                end
                dmH2_bat = battery_h2_equiv(step.delta_equiv, abs(Pbat_stage), a_ratio, Ts_i);

                custo_switch = p_kg * abs(n_st - n_prev);

                % custo-a-ir do proximo estagio: interpola no SOC_next,
                % com n_st_prev = n_st (o candidato que estamos avaliando
                % agora vira o "anterior" no proximo estagio)
                J_next = interp1(soc_grid, squeeze(J_opt(ip+1,:,n_st+1))', SOC_next, 'linear', 'extrap');

                melhores_J(n_st+1) = dmH2_fc + dmH2_bat + custo_switch + J_next;
                melhores_n(n_st+1) = n_st;
            end

            [Jmin, idxmin] = min(melhores_J);
            J_opt(ip, isoc, in_prev) = Jmin;
            n_st_opt(ip, isoc, in_prev) = melhores_n(idxmin);
        end
    end
end

mapa.pos_grid = edges(1:end-1)' + diff(edges)'/2;
mapa.soc_grid = soc_grid;
mapa.nprev_grid = (0:N_fc)';
mapa.J_opt = J_opt;
mapa.n_st_opt = n_st_opt;
mapa.dp_cfg = struct('Npos', Npos, 'dSOC', dSOC, 'p_switch_kg', p_kg);
end
