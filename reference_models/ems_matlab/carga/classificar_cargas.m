function [P_prop, P_hotel, P_aux] = classificar_cargas(P_load_k, modo_idx)
% CLASSIFICAR_CARGAS Divide a carga total em Propulsao, Hotelaria e Auxiliares
% Baseado em Marashian et al. (2025). Nao depende de modelo de fonte nenhum, so da fracao da
% carga total

    if modo_idx == 1 % Porto/Atracado
        f_prop = 0.06; f_hotel = 0.52; f_aux = 0.42;
    else % Cruzeiro ou Manobra (Navegacao ativa)
        f_prop = 0.69; f_hotel = 0.13; f_aux = 0.18;
    end
    P_prop = f_prop  * P_load_k;
    P_hotel = f_hotel * P_load_k;
    P_aux = f_aux   * P_load_k;
end
