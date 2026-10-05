function econ = parametros_economicos()
%PARAMETROS_ECONOMICOS Unico lugar com precos que NENHUM CSV da plataforma
%traz. Termica e eolica vem com custo pronto (variable_cost_rs,
%startup_cost_rs); FC e bateria nao, porque a plataforma delas descreve
%fisica (kg de H2, kWh de capacidade), nao R$. A conversao para a mesma
%moeda do resto do sistema e uma decisao de negocio, nao de modelagem --
%por isso fica aqui, isolada, em vez de dentro de contrato_fonte.m ou
%montar_fontes.m.
%
%Os quatro valores abaixo sao PLACEHOLDER. O despacho roda com eles, mas
%o resultado economico so vale o que esses numeros valerem.

    % ------------------------------------------------------------- H2 / FC
    % R$/kg de H2. Usado para converter a curva de eficiencia da FC
    % (kg H2 / kWh entregue) em custo (R$ / kWh entregue).
    econ.preco_H2_rs_kg = 25.0;   % TODO: confirmar preco de contrato/mercado

    % ------------------------------------------------------------ bateria
    % R$ por kWh MOVIMENTADO (carga+descarga), nao por kWh de capacidade.
    % E o unico parametro que arbitra "usar bateria" vs "usar combustivel"
    % no custo -- se ficar baixo demais, o otimizador cicla a bateria sem
    % necessidade; se ficar alto demais, ela vira reserva que nunca e usada.
    % Estimativa usual: custo_troca_pacote_rs / (2 * ciclos_vida * E_kWh_util).
    econ.c_deg_bateria_rs_kWh = 0.08;   % TODO: derivar do custo real do pacote

    % ------------------------------------------------------------ folgas
    % Preco da energia NAO ATENDIDA e da energia VERTIDA. Regra usada em
    % restricoes_despacho.m/custo_despacho.m: nao sao pesos a calibrar,
    % sao PRECOS -- devem ficar 10x-100x acima do maior custo variavel do
    % sistema, senao o otimizador "compra" deficit quando o combustivel
    % fica caro em vez de tratar deficit como ultimo recurso.
    econ.pen_deficit_rs_kWh = 50.0;   % TODO: ajustar apos ver o maior c_var do sistema
    econ.pen_excesso_rs_kWh = 0.5;    % verter custa pouco, mas deve ser > 0
                                        % (senao o otimizador fica indiferente
                                        % entre verter e nao gerar)
end
