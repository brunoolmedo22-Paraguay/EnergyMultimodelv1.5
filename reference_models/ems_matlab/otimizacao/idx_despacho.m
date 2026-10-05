function ix = idx_despacho(N, m)
%IDX_DESPACHO Layout do vetor de decisao, generico em numero de fontes.
%
%   x = [ P_1(1:N) ; P_2(1:N) ; ... ; P_m(1:N) ; s_def(1:N) ; s_exc(1:N) ]
%
%Todas as potencias em p.u. de cfg.S_base. As folgas s_def (demanda nao
%atendida) e s_exc (energia vertida) sao variaveis de PRIMEIRA CLASSE, nao
%tratamento de erro: com must-run no sistema, excesso e um estado de
%operacao legitimo e precisa sair no relatorio como kWh, nao como warning.

    ix.N = N; ix.m = m;
    ix.fonte = cell(m,1);
    for j = 1:m
        ix.fonte{j} = (j-1)*N + (1:N);
    end
    ix.s_def   = m*N + (1:N);
    ix.s_exc   = (m+1)*N + (1:N);
    ix.n_total = (m+2)*N;
end