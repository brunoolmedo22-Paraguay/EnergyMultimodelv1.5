function nome_alg = nome_algoritmo(ID_ALGORITMO)
%NOME_ALGORITMO Traduz o ID numerico do algoritmo em string, so para
%titulos de grafico / nomes de arquivo. Adicionar um 4o otimizador:
%acrescente aqui e em ems_dispatch.m (switch ID_ALGORITMO).
    switch ID_ALGORITMO
        case 1, nome_alg = 'GA';
        case 2, nome_alg = 'GWO';
        case 3, nome_alg = 'NGO';
        otherwise
            error('ID_ALGORITMO invalido: %d (valores validos: 1=GA, 2=GWO, 3=NGO)', ID_ALGORITMO);
    end
end
