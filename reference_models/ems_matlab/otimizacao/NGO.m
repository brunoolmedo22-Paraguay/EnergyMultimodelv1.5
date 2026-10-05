function [bestX, bestF] = NGO(fun, LB, UB, nPop, nIter)
% NGO - Northern Goshawk Optimization (Dehghani et al., 2021)
% Usado no artigo de Zhang et al. (2025) como busca global da Camada 1
% (NMPC-NGO), refinado depois por SQP.

    dim = numel(LB);
    LB = LB(:)'; UB = UB(:)';

    X = repmat(LB, nPop, 1) + rand(nPop, dim) .* repmat(UB-LB, nPop, 1);
    F = zeros(nPop,1);
    for i = 1:nPop
        F(i) = fun(X(i,:)');
    end

    for t = 1:nIter
        for i = 1:nPop
            %% Estagio 1: identificacao da presa (exploracao)
            prey_idx = randi(nPop);
            p = X(prey_idx,:);
            Fp = F(prey_idx);

            I = randi([1,2]);
            r = rand;
            if Fp < F(i)
                Xnew1 = X(i,:) + r .* (p - I .* X(i,:));
            else
                Xnew1 = X(i,:) + r .* (X(i,:) - p);
            end
            Xnew1 = max(min(Xnew1, UB), LB);
            Fnew1 = fun(Xnew1');
            if Fnew1 < F(i)
                X(i,:) = Xnew1;
                F(i) = Fnew1;
            end

            %% Estagio 2: perseguicao e fuga (explotacao)
            R = 0.02 * (1 - t/nIter);
            r = rand;
            Xnew2 = X(i,:) - R .* (2*r - 1) .* X(i,:);
            Xnew2 = max(min(Xnew2, UB), LB);
            Fnew2 = fun(Xnew2');
            if Fnew2 < F(i)
                X(i,:) = Xnew2;
                F(i) = Fnew2;
            end
        end
    end

    [bestF, idxBest] = min(F);
    bestX = X(idxBest,:)';
end
