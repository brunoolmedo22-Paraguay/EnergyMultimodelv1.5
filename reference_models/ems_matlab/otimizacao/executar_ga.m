% GA
function [Best_pos, Best_score, histBest] = executar_ga(fun, LB, UB)
% Dimensão
num_variaveis = numel(LB);
LB = LB(:)'; UB = UB(:)';
max_gen = 20;
histBest = zeros(max_gen,1);
gen_atual = 0;

    function [state, options, optchanged] = registrar_geracao(options, state, flag)
        optchanged = false;
        if strcmp(flag, 'iter')
            gen_atual = gen_atual +1;
            if gen_atual <= max_gen
                histBest(gen_atual) = state.Best(end);
            end
        end
    end

% Configurações GA
options = optimoptions('ga', 'PopulationType', 'doubleVector', 'PopulationSize', 15, ...
    'MaxGenerations',20,'EliteCount',5, 'CrossoverFraction', 0.8, 'ConstraintTolerance', 1e-3, ...
    'FunctionTolerance', 1e-1, 'OutputFcn', @registrar_geracao, 'Display', 'none');

[Best_pos, Best_score, exitflag] = ga(fun, num_variaveis, [],[],[],[], LB, UB, [], options);


if exitflag > 0
    fprintf('Otimização GA concluída com sucesso.\n');
else
    fprintf('GA finalizado - atingiu limite de gerações ou tolerância.\n');
end

end
