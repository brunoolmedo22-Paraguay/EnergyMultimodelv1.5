function [combos, custo_switch] = candidatos_config(fontes, n_prev, teto_combos)
%CANDIDATOS_CONFIG Gera as configuracoes inteiras candidatas do passo atual
%(quantas unidades de cada fonte ficam ligadas) e o custo de comutacao de
%cada uma. Generaliza mld_fc_estado.m para qualquer numero de fontes
%modulares, preservando a ideia central dele: NAO enumerar todas as
%configuracoes possiveis, so uma VIZINHANCA da configuracao anterior.
%
%Por que vizinhanca: o problema completo e um MINLP. Enumerar
%prod_j (n_unid_j + 1) configuracoes por passo e resolver uma NLP para
%cada estoura o tempo real. Restringir a |n - n_prev| <= dn_max e o
%branch-and-bound truncado que ja estava em mld_fc_estado.m -- e tambem e
%fisicamente correto: ninguem liga 4 stacks de uma vez em um passo de 1 min.
%
%SAIDAS
%  combos        (nc x m) inteiro, unidades ligadas por fonte
%  custo_switch  (nc x 1) R$, soma de c_start_unid_rs * unidades ACENDIDAS
%                (desligar nao custa; so a partida custa)

    m = numel(fontes);
    if nargin < 3 || isempty(teto_combos), teto_combos = 64; end

    cand = cell(m,1);
    for j = 1:m
        f = fontes(j);
        if f.armazena
            cand{j} = 1;                      % armazenamento nao comuta
            continue;
        end
        lo = max(0, n_prev(j) - f.dn_max);
        hi = min(f.n_unid, n_prev(j) + f.dn_max);
        c  = unique(round(lo:hi));
        if isempty(c), c = n_prev(j); end
        cand{j} = c;
    end

    n_comb = prod(cellfun(@numel, cand));
    if n_comb > teto_combos
        % Degrada de forma previsivel: mantem fixas as fontes de menor
        % custo de partida (as baratas de comutar importam menos na
        % decisao inteira) ate caber no teto.
        [~, ordem] = sort(arrayfun(@(f) f.c_start_unid_rs, fontes));
        for j = ordem(:)'
            if n_comb <= teto_combos, break; end
            if numel(cand{j}) > 1
                cand{j} = n_prev(j);
                n_comb = prod(cellfun(@numel, cand));
            end
        end
        warning('candidatos_config:teto', ...
            ['Vizinhanca excedia %d combinacoes; algumas fontes foram fixadas ' ...
             'na configuracao anterior. Reduza dn_max ou mova o compromisso ' ...
             'para um nivel de decisao mais lento.'], teto_combos);
    end

    % produto cartesiano
    grids = cell(1,m);
    [grids{:}] = ndgrid(cand{:});
    combos = zeros(numel(grids{1}), m);
    for j = 1:m, combos(:,j) = grids{j}(:); end

    % custo de comutacao: so subidas
    custo_switch = zeros(size(combos,1),1);
    for j = 1:m
        acende = max(combos(:,j) - n_prev(j), 0);
        custo_switch = custo_switch + acende * fontes(j).c_start_unid_rs;
    end

    % ordena por custo de comutacao: o primeiro viavel ja e um bom incumbente
    [custo_switch, ord] = sort(custo_switch);
    combos = combos(ord,:);
end
