function [c, ceq] = restricoes_despacho(x, fontes, ix, cfg, SOC_ini, P_prev, Pl_h, n_cand)
%RESTRICOES_DESPACHO Restricoes do despacho, sem nenhum modelo de equipamento.
%
%Sao exatamente tres familias, e nenhuma delas depende de que tecnologia
%esta por tras da fonte:
%
%  (1) BALANCO com folgas explicitas. Nao e igualdade pura: com must-run
%      (P_min>0) o total minimo gerado pode EXCEDER a carga, e sem folga
%      de excesso o problema fica inviavel e o solver reporta isso como
%      erro numerico em vez de como energia vertida. s_def e s_exc sao
%      penalizadas no custo com preco muito acima de qualquer geracao,
%      entao so aparecem quando realmente nao ha alternativa -- e ai
%      aparecem como NUMERO no relatorio, nao como falha.
%
%  (2) SOC do armazenamento dentro da faixa ao longo do horizonte, e no
%      alvo ao fim dele. E o unico estado propagado internamente, porque
%      depende da decisao que ainda vai ser tomada.
%
%  (3) RAMPA, que precisa de P(t-1). O limite em si (kW/min) e dado
%      externo; so a avaliacao mora aqui.
%
%A caixa de envelope (P_min <= P <= P_max por instante) NAO aparece aqui:
%ela ja esta em LB/UB, que o fmincon trata mais barato que inequacao.

    N = ix.N; S = cfg.S_base; Ts_h = cfg.Ts_s/3600; Ts_min = cfg.Ts_s/60;
    m = numel(fontes);
    c = [];

    % ------------------------------------------------- (1) balanco
    soma = zeros(N,1);
    for j = 1:m
        Pj = x(ix.fonte{j}) * S;
        if fontes(j).armazena
            % eficiencia direcional: descarregando o barramento recebe menos;
            % carregando, o barramento precisa fornecer mais.
            dir = (Pj >= 0)*fontes(j).eta + (Pj < 0)/fontes(j).eta;
            soma = soma + dir(:).*Pj(:);
        else
            soma = soma + fontes(j).eta * Pj(:);
        end
    end
    s_def = x(ix.s_def)*S; s_exc = x(ix.s_exc)*S;
    ceq = Pl_h(:)*S - (soma + s_def(:) - s_exc(:));

    % ------------------------------------------------- (2) SOC
    for j = 1:m
        if ~fontes(j).armazena, continue; end
        f = fontes(j);
        Pj = x(ix.fonte{j}) * S;
        soc = SOC_ini(j); soc_h = zeros(N,1);
        for i = 1:N
            if Pj(i) >= 0
                dE = Pj(i)*Ts_h / f.eta_descarga;
            else
                dE = Pj(i)*Ts_h * f.eta_carga;
            end
            soc = soc - dE/f.E_kWh;
            soc_h(i) = soc;
        end
        c = [c; soc_h - f.SOC_max];
        c = [c; f.SOC_min - soc_h];
        if ~isempty(f.SOC_alvo)
            % alvo como banda, nao igualdade: igualdade no fim de cada
            % horizonte movel engessa o despacho a cada passo.
            tol = 0.05;
            c = [c; soc_h(end) - (f.SOC_alvo + tol)];
            c = [c; (f.SOC_alvo - tol) - soc_h(end)];
        end
    end

    % ------------------------------------------------- (3) rampa
    for j = 1:numel(fontes)
        f = fontes(j);
        if ~isfinite(f.ramp_kW_min), continue; end
        nj = n_cand(j);
        if nj == 0, continue; end
        % A rampa e por UNIDADE: n unidades ligadas rampeiam n vezes mais
        % rapido em potencia total. O limite escalar vindo do contrato e
        % sempre por unidade.
        dmax = nj * f.ramp_kW_min * Ts_min;
        Pj = x(ix.fonte{j}) * S;
        % Comutacao NAO e modulacao de carga. Se a configuracao mudou neste
        % passo, o salto de potencia e um evento de partida/parada, governado
        % pelo piso tecnico (n*P_min_unid) e nao pela rampa. Aplicar a rampa
        % aqui tornaria impossivel religar qualquer unidade cujo piso seja
        % maior que o incremento permitido por passo -- que e o caso tipico.
        mudou_config = abs(nj - n_prev_de(f, P_prev(j))) > 0;
        if abs(P_prev(j)) > 1e-6 && ~mudou_config
            c = [c; Pj(1) - P_prev(j) - dmax; P_prev(j) - Pj(1) - dmax];
        end
        if N > 1
            d = diff(Pj);
            c = [c; d(:) - dmax; -d(:) - dmax];
        end
    end

    c = real(double(c)); ceq = real(double(ceq));
end

function n = n_prev_de(f, P_prev_j)
% Infere a configuracao anterior a partir da potencia anterior e do piso
% por unidade. Evita carregar n_prev como mais um argumento so para a
% rampa; o unico uso e distinguir "mudou de configuracao" de "modulou
% dentro da mesma configuracao".
    if abs(P_prev_j) < 1e-6, n = 0; return; end
    piso = max(f.P_min_unid_kW(1), eps);
    n = max(1, min(f.n_unid, round(abs(P_prev_j)/max(f.P_max_unid_kW(1), eps))));
    if piso > 0
        n = max(n, 1);
    end
end
