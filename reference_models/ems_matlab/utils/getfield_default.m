function v = getfield_default(s, f, default)
%GETFIELD_DEFAULT Le s.(f) se existir, senao devolve default. Usado para
%campos opcionais de arch (ex.: limites de tensao de bateria, limites de
%corrente de conversor) sem quebrar cenarios que ainda nao os definem.
    if isfield(s, f)
        v = s.(f);
    else
        v = default;
    end
end
