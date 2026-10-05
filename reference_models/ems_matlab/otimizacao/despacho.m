function res = despacho(fontes, P_load_kW, cfg)
%DESPACHO Nucleo do otimizador, INDEPENDENTE DE MODELO.
%
%Nao ha aqui nenhuma referencia a celula a combustivel, bateria, termica ou
%vento. Ha apenas objetos que obedecem a contrato_fonte.m. Trocar a
%plataforma de modelagem, o equipamento ou a aplicacao nao exige tocar
%neste arquivo -- so o que entra em 'fontes'.
%
%DECIDE, a cada passo:
%   (a) INTEIRO   -- quantas unidades de cada fonte ficam ligadas
%   (b) CONTINUO  -- quanto cada fonte entrega, dentro do envelope de (a)
%
%NAO FAZ: dinamica de 1a ordem, tensao de stack, degradacao eletroquimica,
%curva de eficiencia. Tudo isso ja veio resolvido dentro de
%P_max_unid_kW / P_min_unid_kW / c_var_rs_kWh(:,n).
%
%ESTRUTURA do MINLP por passo (identica a de ems_dispatch.m, generalizada):
%   para cada configuracao inteira candidata -> resolve a NLP continua com
%   a caixa travada por ela -> soma o custo de comutacao -> vence o menor
%   custo total entre as viaveis. Candidatos vem de candidatos_config.m
%   (vizinhanca da configuracao anterior), nao da enumeracao completa.
%
%cfg: .Ts_s .N .S_base .pen_deficit .pen_excesso .algoritmo .options
%     .teto_combos (default 64)

    Nt = numel(P_load_kW); m = numel(fontes);
    N = cfg.N; Ts_h = cfg.Ts_s/3600; S = cfg.S_base;
    if ~isfield(cfg,'teto_combos'), cfg.teto_combos = 64; end

    ix  = idx_despacho(N, m);
    arm = [fontes.armazena];

    % --- unico estado propagado internamente: SOC, config e P anteriores ---
    SOC = zeros(1,m);
    for j = 1:m, if arm(j), SOC(j) = fontes(j).SOC_ini; end, end
    n_prev = arrayfun(@(f) f.n_ini, fontes);
    P_prev = zeros(1,m);

    res.P_kW = zeros(Nt,m); res.n_unid = zeros(Nt,m); res.SOC = nan(Nt,m);
    res.deficit_kW = zeros(Nt,1); res.excesso_kW = zeros(Nt,1);
    res.custo_rs = zeros(Nt,1); res.custo_partida_rs = zeros(Nt,1);

    for k = 1:Nt-N+1
        h = k:k+N-1;
        Pl_h = P_load_kW(h)/S;

        [combos, c_switch] = candidatos_config(fontes, n_prev, cfg.teto_combos);

        melhor = struct('J',inf,'x',[],'n',n_prev,'viol',inf,'cs',0);
        achou_viavel = false;

        for ic = 1:size(combos,1)
            n_cand = combos(ic,:);

            % ---- caixa: 100% envelope externo, escalado pela configuracao ----
            LB = zeros(ix.n_total,1); UB = zeros(ix.n_total,1);
            caixa_ok = true;
            for j = 1:m
                nj = n_cand(j);
                lo = nj * fontes(j).P_min_unid_kW(h);
                hi = nj * fontes(j).P_max_unid_kW(h);
                if nj == 0, lo(:) = 0; hi(:) = 0; end
                if any(lo > hi + 1e-12), caixa_ok = false; break; end
                LB(ix.fonte{j}) = lo/S; UB(ix.fonte{j}) = hi/S;
            end
            if ~caixa_ok, continue; end
            LB(ix.s_def) = 0; UB(ix.s_def) = inf;
            LB(ix.s_exc) = 0; UB(ix.s_exc) = inf;

            objFun = @(x) custo_despacho(x, fontes, ix, cfg, h, n_cand);
            nlc    = @(x) restricoes_despacho(x, fontes, ix, cfg, SOC, P_prev, Pl_h, n_cand);

            x0 = min(max((LB+UB)/2, LB), UB); x0(~isfinite(x0)) = 0;
            UBm = min(UB, 1e3);   % metaheuristicas precisam de caixa limitada
            switch cfg.algoritmo
                case 1, x0 = executar_ga(objFun, LB, UBm);
                case 2, x0 = gwo(objFun, LB, UBm, 10, 55);
                case 3, x0 = NGO(objFun, LB, UBm, 10, 15);
            end
            x0 = min(max(x0(:), LB), UB);

            [x, J, flag, out] = fmincon(objFun, x0, [], [], [], [], LB, UB, nlc, cfg.options);
            Jt = J + c_switch(ic);
            viavel = (flag > 0) && (out.constrviolation <= 1e-6);

            aceita = (viavel && ~achou_viavel) ...
                  || (viavel && achou_viavel && Jt < melhor.J) ...
                  || (~viavel && ~achou_viavel && out.constrviolation < melhor.viol);
            if aceita
                melhor = struct('J',Jt,'x',x,'n',n_cand,'viol',out.constrviolation,'cs',c_switch(ic));
                achou_viavel = achou_viavel || viavel;
            end
        end

        if ~achou_viavel
            warning('despacho:inviavel', ...
                ['Passo k=%d sem configuracao viavel (violacao %.3g). Como deficit ' ...
                 'e excesso sao variaveis de folga, inviabilidade aqui indica ' ...
                 'envelope inconsistente (piso acima do teto, SOC encurralado ou ' ...
                 'rampa impossivel), nao falta de capacidade.'], k, melhor.viol);
        end

        x = melhor.x; n_prev = melhor.n;

        % ---- aplica so o PRIMEIRO passo do horizonte (recuo movel) ----
        custo_k = 0;
        for j = 1:m
            Pj = x(ix.fonte{j}(1)) * S;
            res.P_kW(k,j) = Pj; res.n_unid(k,j) = n_prev(j); P_prev(j) = Pj;
            col = max(n_prev(j), 1);
            custo_k = custo_k + fontes(j).c_var_rs_kWh(k, col) * abs(Pj) * Ts_h;
            if arm(j)
                custo_k = custo_k + fontes(j).c_deg_rs_kWh * abs(Pj) * Ts_h;
                SOC(j) = atualiza_soc(SOC(j), Pj, fontes(j), Ts_h);
                res.SOC(k,j) = SOC(j);
            end
        end
        res.deficit_kW(k) = x(ix.s_def(1)) * S;
        res.excesso_kW(k) = x(ix.s_exc(1)) * S;
        res.custo_partida_rs(k) = melhor.cs;
        res.custo_rs(k) = custo_k + melhor.cs ...
            + cfg.pen_deficit * res.deficit_kW(k) * Ts_h ...
            + cfg.pen_excesso * res.excesso_kW(k) * Ts_h;
    end

    res.ix = ix; res.nomes = {fontes.nome};
    res.custo_total_rs = sum(res.custo_rs);
    res.energia_nao_atendida_kWh = sum(res.deficit_kW)*Ts_h;
    res.energia_vertida_kWh = sum(res.excesso_kW)*Ts_h;
    res.partidas = sum(max(diff([arrayfun(@(f) f.n_ini, fontes); res.n_unid]), 0), 1);
end

% ----------------------------------------------------------------- locais
function SOC = atualiza_soc(SOC, P_kW, f, Ts_h)
% Contabilidade de energia -- NAO modelo de bateria. A fisica (capacidade
% util, etas, limites) veio pronta da plataforma externa.
    if P_kW >= 0
        dE = P_kW * Ts_h / f.eta_descarga;
    else
        dE = P_kW * Ts_h * f.eta_carga;
    end
    SOC = min(max(SOC - dE/f.E_kWh, 0), 1);
end
