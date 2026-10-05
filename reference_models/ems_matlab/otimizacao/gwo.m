%% GWO
function [Best_pos, Best_score, histBest] = gwo(fun, LB, UB, nWolves, nIters)
    dim = numel(LB);
    LB = LB(:)'; UB = UB(:)';
    X = repmat(LB, nWolves, 1) + rand(nWolves, dim).*repmat((UB-LB), nWolves,1);
    F = inf(nWolves,1);

    for i=1:nWolves
        F(i) = fun(X(i,:)');
    end

    [Fsort, idx] = sort(F);
    alpha = X(idx(1),:);  Falfa = Fsort(1);
    beta = X(idx(2),:);  Fbeta = Fsort(2);
    delta = X(idx(3),:);  Fdelta= Fsort(3);

    histBest = zeros(nIters,1);

    for t=1:nIters
        a = 2 - 2*(t-1)/(nIters-1);

        for i=1:nWolves
            for d=1:dim
                r1 = rand; r2 = rand;
                A1 = 2*a*r1 - a; C1 = 2*r2;
                Dalpha = abs(C1*alpha(d) - X(i,d));
                X1 = alpha(d) - A1*Dalpha;

                r1 = rand; r2 = rand;
                A2 = 2*a*r1 - a; C2 = 2*r2;
                Dbeta = abs(C2*beta(d) - X(i,d));
                X2 = beta(d) - A2*Dbeta;

                r1 = rand; r2 = rand;
                A3 = 2*a*r1 - a; C3 = 2*r2;
                Ddelta = abs(C3*delta(d) - X(i,d));
                X3 = delta(d) - A3*Ddelta;

                X(i,d) = (X1 + X2 + X3)/3;
            end

            X(i,:) = max(X(i,:), LB);
            X(i,:) = min(X(i,:), UB);
        end

        for i=1:nWolves
            Fi = fun(X(i,:)');
            if Fi < Falfa
                delta = beta;  Fdelta = Fbeta;
                beta  = alpha; Fbeta  = Falfa;
                alpha = X(i,:);Falfa  = Fi;
            elseif Fi < Fbeta
                delta = beta;  Fdelta = Fbeta;
                beta  = X(i,:);Fbeta  = Fi;
            elseif Fi < Fdelta
                delta = X(i,:);Fdelta = Fi;
            end
        end

        histBest(t) = Falfa;
    end

    Best_pos = alpha(:);
    Best_score = Falfa;
end
