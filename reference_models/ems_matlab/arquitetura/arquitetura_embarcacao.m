function arch = arquitetura_embarcacao(N_fc)
%ARQUITETURA_WALKFORWARD Mesma embarcacao/EMS de arquitetura_embarcacao_h2.m
%(motores, PV, pesos, dinamica, etc.), mas com FC e bateria REDIMENSIONADAS
%para o perfil de carga walk-forward (2h, ver dados/ems_walkforward.csv),
%que e bem mais leve que o perfil do artigo original (pico ~214 kW contra
%~402 kW do artigo). Mantem arquitetura_embarcacao_h2.m intocada para nao
%perder a validacao/comparacao contra Zhang et al./Jiang et al.
%
%Dimensionamento (baseado nas 135 janelas de 2h do CSV walk-forward):
%   - pico de carga (pior combo, Pessimista x Maxima): 214,5 kW
%   - maior salto de carga entre passos de 1 min (manobra->cruzeiro): ~151 kW
%
%   FC: 2 x 140 kW = 280 kW total -> margem de 1,3x sobre o pior pico
%       (mesma logica de margem do artigo original: 500/402 = 1,24x)
%   Bateria: energia reduzida de 1806 -> 200 kWh (a carga de uma janela de
%       2h nunca chega perto de precisar de tanta energia armazenada); a
%       POTENCIA de descarga/carga NAO foi cortada na mesma proporcao,
%       porque o perfil tem transientes rapidos (manobra<->cruzeiro) de
%       ate ~151 kW/min que a FC nao acompanha por causa do limite de
%       rampa (dP_max=20 kW/passo) -- e a bateria quem absorve isso.

    arch = arquitetura_embarcacao_h2(N_fc);

    % FC: 250 -> 140 kW por stack (total 500 -> 280 kW)
    arch.fc.P_rated_each_kW = 140;
    arch.fc.P_max_tot_kW = arch.fc.N_fc * arch.fc.P_rated_each_kW;
    arch.fc.P_min_stack_kW = 0.10 * arch.fc.P_rated_each_kW; % mantem 10% (agora 14 kW)

    % Bateria: energia 1806 -> 200 kWh; potencia de descarga mantida perto
    % do original (cobre os transientes de manobra), carga um pouco maior
    % (absorve quedas bruscas que a rampa da FC nao acompanha)
    arch.bat.Q_kWh = 200;
    arch.bat.P_max_discharge_kW = 150;
    arch.bat.P_max_charge_kW = 80;
end