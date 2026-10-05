function out = bateria_step(Pbat_kW, bat, SOC_in, n_cum_in, Ts)
%BATERIA_STEP Um unico passo da dinamica da bateria (modelo Rint, Eq.6-8
%de Zhang et al. 2025), usado tanto na funcao custo do NMPC quanto nas
%restricoes e no loop principal de despacho -- posteriormente não será
%utilizado
% Entradas:
%   Pbat_kW potencia de bateria no passo (kW, >0 = descarga)
%   bat struct com Voc, Rint, eta_chg, eta_dis, Q_cap_Ah
%   SOC_in SOC no inicio do passo
%   n_cum_in numero de ciclos acumulado no inicio do passo
%   Ts duracao do passo (s)
%
% Saida (struct):
%   out.SOC SOC ao final do passo
%   out.V_bat tensao terminal prevista (V) -- usar em restricoes
%   out.Ibat corrente (A)
%   out.n_cum numero de ciclos acumulado atualizado
%   out.delta_equiv fator de consumo equivalente de H2 (Eq.11-13),
%                   ja considerando o sentido de carga/descarga

    Uoc = bat.Voc; R = bat.Rint;
    ds = Uoc^2 - 4*R*Pbat_kW*1000;
    Ib = (ds<0)*(Uoc/(2*R)) + (ds>=0)*((Uoc - sqrt(max(ds,0)))/(2*R));
    V_bat = Uoc - Ib*R;

    if Pbat_kW >= 0
        SOC_new = SOC_in - (Ib/bat.eta_dis) * Ts / (bat.Q_cap_Ah*3600);
        eta_d = 0.5*(1+sqrt(max(1-(4*R*Pbat_kW*1000)/(Uoc^2),0)));
        delta = 1/(bat.eta_dis*eta_d);
    else
        SOC_new = SOC_in - (Ib*bat.eta_chg) * Ts / (bat.Q_cap_Ah*3600);
        eta_c = 2/(1+sqrt(1+(4*R*abs(Pbat_kW)*1000)/(Uoc^2)));
        delta = eta_c * bat.eta_chg;
    end

    dn = abs(Ib)*Ts/3600/(2*bat.Q_cap_Ah);

    out.SOC = SOC_new;
    out.V_bat = V_bat;
    out.Ibat = Ib;
    out.n_cum = n_cum_in + dn;
    out.delta_equiv = delta;
end
