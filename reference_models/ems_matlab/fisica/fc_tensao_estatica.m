function V_fc_kW = fc_tensao_estatica(Pfc_kW, fc)
%FC_TENSAO_ESTATICA Curva de polarizacao V(P) em REGIME PERMANENTE da FC
%(aproximacao AFIM dentro do range V_out_range_V declarado em
%arquitetura_embarcacao_h2.m: tensao cai linearmente com a potencia/
%corrente, comportamento tipico de PEMFC na regiao ohmica da curva de
%polarizacao). Usada como entrada "alvo estatico" da dinamica de atraso
%de tensao (fc_tensao_dinamica.m, Pilar 2).
%
% Jiang et al. (2025) fornece so o range de tensao
%de saida (V_out_range_V = [200 380]), nao a
%curva de polarizacao completa V(I) por stack. 
% Para adiconar a curva troque o corpo desta funcao por
%uma interpolacao (mesmo padrao de fc_efficiency.m) sem alterar a
%assinatura 
%
%Entradas:
%   Pfc_kW potencia TOTAL do MFCS (ou por stack)
%   fc  struct com fc.P_max_tot e fc.V_range = [V_min V_max]
%
%Saida:
% V_fc_kW tensao terminal estatica estimada [V]

    Vmax = fc.V_range(2);
    Vmin = fc.V_range(1);
    frac = min(max(Pfc_kW / max(fc.P_max_tot, eps), 0), 1);
    V_fc_kW = Vmax - (Vmax - Vmin) * frac; % decai linearmente com a carga
end
