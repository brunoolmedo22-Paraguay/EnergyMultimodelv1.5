function rel = relatorio_despacho(res, fontes, cfg)
%RELATORIO_DESPACHO Traduz a saida generica de despacho.m (R$, kW, p.u.)
%de volta para as grandezas que o relatorio antigo (ems_dispatch.m)
%entregava: energia por fonte, % de atendimento, consumo fisico (kg H2),
%SOC final, custo por fonte. Fica FORA do otimizador de proposito -- nada
%aqui influencia a decisao de despacho, e por isso pode crescer (novos
%indicadores, novos graficos) sem arriscar o nucleo de otimizacao.
%
%ENTRADA: res (saida de despacho.m), fontes (o mesmo array passado a ele),
%cfg (mesmo cfg do despacho, usa Ts_s).
%
%SAIDA rel:
%  .energia_por_fonte_kWh   (1 x m) energia positiva entregue por fonte
%  .pct_atendimento         (1 x m) % da energia total servida, por fonte
%  .consumo_fisico          struct por fonte com campo qtd_fisica_unidade
%                           preenchido (ex: rel.consumo_fisico.fc = struct(
%                           'valor', 12.3, 'unidade','kg_H2')) -- so para
%                           fontes que declararam qtd_fisica_por_kWh
%  .SOC_final                (1 x m) NaN para fontes nao-armazenamento
%  .custo_por_fonte_rs        (1 x m) inclui degradacao e partida
%  .custo_total_rs, .energia_nao_atendida_kWh, .energia_vertida_kWh
%                            (repassados de res, para nao obrigar o
%                             usuario a olhar dois structs)

    Ts_h = cfg.Ts_s/3600;
    m = numel(fontes);
    rel.nomes = res.nomes;

    E = zeros(1,m); PCT = zeros(1,m); SOCf = nan(1,m); custoF = zeros(1,m);
    rel.consumo_fisico = struct();

    for j = 1:m
        f = fontes(j);
        Pj = res.P_kW(:,j);
        E(j) = sum(max(Pj,0)) * Ts_h;

        % custo variavel + degradacao dessa fonte, no historico completo
        Nt = size(res.P_kW,1);
        c = zeros(Nt,1);
        for t = 1:Nt
            col = max(res.n_unid(t,j), 1);
            if ~isempty(f.custo_fn)
                c(t) = f.custo_fn(Pj(t), res.n_unid(t,j), t);
            else
                col = min(col, size(f.c_var_rs_kWh,2));
                c(t) = f.c_var_rs_kWh(t, col);
            end
        end
        custoF(j) = sum(c .* abs(Pj) * Ts_h);
        if f.armazena
            custoF(j) = custoF(j) + f.c_deg_rs_kWh * sum(abs(Pj) * Ts_h);
            if ~all(isnan(res.SOC(:,j)))
                idx_ult = find(~isnan(res.SOC(:,j)), 1, 'last');
                SOCf(j) = res.SOC(idx_ult, j);
            end
        end

        if ~isempty(f.qtd_fisica_por_kWh) || ~isempty(f.qtd_fisica_fn)
            qtd = 0;
            for t = 1:Nt
                if ~isempty(f.qtd_fisica_fn)
                    qf = f.qtd_fisica_fn(Pj(t), res.n_unid(t,j), t);
                else
                    col = max(res.n_unid(t,j), 1);
                    col = min(col, size(f.qtd_fisica_por_kWh,2));
                    qf = f.qtd_fisica_por_kWh(t, col);
                end
                qtd = qtd + qf * max(Pj(t),0) * Ts_h;
            end
            rel.consumo_fisico.(f.nome) = struct('valor', qtd, 'unidade', f.qtd_fisica_unidade);
        end
    end

    E_total = sum(E);
    if E_total > 1e-9
        PCT = 100 * E / E_total;
    else
        warning('relatorio_despacho:semEnergia', ...
            'Energia total entregue ~0: % de atendimento por fonte nao e informativo.');
    end

    rel.energia_por_fonte_kWh = E;
    rel.pct_atendimento = PCT;
    rel.SOC_final = SOCf;
    rel.custo_por_fonte_rs = custoF;
    rel.custo_total_rs = res.custo_total_rs;
    rel.energia_nao_atendida_kWh = res.energia_nao_atendida_kWh;
    rel.energia_vertida_kWh = res.energia_vertida_kWh;
    rel.partidas = res.partidas;

    % ------------------------------------------------------------ impressao
    fprintf('\n=== RELATORIO DE DESPACHO ===\n');
    fprintf('Custo total: R$ %.2f\n', rel.custo_total_rs);
    fprintf('Energia nao atendida: %.2f kWh | vertida: %.2f kWh\n', ...
        rel.energia_nao_atendida_kWh, rel.energia_vertida_kWh);
    fprintf('\n%-10s %10s %8s %12s %8s\n', 'fonte','kWh','%','R$','partidas');
    for j = 1:m
        fprintf('%-10s %10.1f %7.1f%% %12.2f %8d\n', ...
            fontes(j).nome, E(j), PCT(j), custoF(j), res.partidas(j));
        if isfield(rel.consumo_fisico, fontes(j).nome)
            cf = rel.consumo_fisico.(fontes(j).nome);
            fprintf('%-10s   consumo: %.2f %s\n', '', cf.valor, cf.unidade);
        end
        if ~isnan(SOCf(j))
            fprintf('%-10s   SOC final: %.1f%%\n', '', 100*SOCf(j));
        end
    end
    fprintf('==============================\n\n');
end