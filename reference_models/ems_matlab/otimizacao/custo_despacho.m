function J = custo_despacho(x, fontes, ix, cfg, h, n_cand)
%CUSTO_DESPACHO Funcao objetivo do despacho -- tudo em R$, sem pesos.
%
%   J = custo variavel de geracao (por fonte, na configuracao n_cand)
%     + custo de degradacao do armazenamento (se declarado)
%     + penalidade de deficit
%     + penalidade de excesso
%
%Para cada fonte, o custo por kWh vem de UM dos dois lugares do contrato
%(nunca dos dois): se a fonte declarou custo_fn, ele e chamado NA POTENCIA
%REAL que esta sendo testada nesta iteracao (P_kW, n_unid, indice de
%tempo) -- e o caso certo quando o custo depende do PONTO DE OPERACAO, nao
%so de quantas unidades estao ligadas (ex: eficiencia da FC varia com a
%carga por stack). Sem custo_fn, usa a matriz c_var_rs_kWh(t,n) fixa por
%configuracao. NENHUM ponto de operacao e assumido por este arquivo --
%quem decide isso e a fonte, via o que ela entrega em contrato_fonte.m.
%
%pen_deficit NAO E PESO A CALIBRAR, e PRECO: deve ficar 10x-100x acima do
%maior custo variavel do sistema, senao o otimizador "compra" deficit
%quando o combustivel fica caro.

    S = cfg.S_base; Ts_h = cfg.Ts_s/3600;
    J = 0;

    for j = 1:numel(fontes)
        f  = fontes(j);
        Pj = x(ix.fonte{j}) * S;
        col = max(n_cand(j), 1);

        if ~isempty(f.custo_fn)
            cj = zeros(numel(h),1);
            for i = 1:numel(h)
                cj(i) = f.custo_fn(Pj(i), n_cand(j), h(i));
            end
        else
            cj = f.c_var_rs_kWh(h, col);
        end
        J = J + sum(cj(:) .* abs(Pj(:)) * Ts_h);

        if f.armazena
            J = J + f.c_deg_rs_kWh * sum(abs(Pj(:)) * Ts_h);
        end
    end

    J = J + cfg.pen_deficit * sum(x(ix.s_def)*S * Ts_h);
    J = J + cfg.pen_excesso * sum(x(ix.s_exc)*S * Ts_h);
    J = real(double(J));
end
