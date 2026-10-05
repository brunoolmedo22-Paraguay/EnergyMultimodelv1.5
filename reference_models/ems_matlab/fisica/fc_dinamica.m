function out = fc_dinamica(Pfc_d_kW, Pfc_s_prev_kW, Ts_s, tau_s, kf)
%FC_DINAMICA Resposta de 1a ordem da celula a combustivel (PILAR 1).
%baseada em Dash (2020) e Luo et al. (2024) - DOI no arch
% G_FC(s) = kf / (1 + s*tau)
%   1) "Planta real" simulada no loop de despacho (ems_dispatch.m):
%      tau = arch.fc.tau_FC_s = 4 s (constante de tempo termica/de
%      membrana da PEMFC completa).
%   2) Modelo linearizado usado dentro da predicao do NMPC
%      (cost_function_hibrido.m / constraints_hibrido.m):
%      tau = arch.fc.tau_f_mpc_s = 0.2 s, na forma diferencial
%           tau_f * dPfc_s/dt = kf*Pfc_d - Pfc_s
%      (dinamica RAPIDA do atuador/controlador de corrente da FC,
%      distinta da dinamica termica mais lenta usada na planta real --
%      ver nota no cabecalho de arquitetura_embarcacao_h2.m).
%
%Discretizacao sob ZOH (Pfc_d constante dentro do passo Ts, o que e
%consistente com o NMPC que otimiza um setpoint por passo): a EDO linear
%tau*dPfc_s/dt = kf*Pfc_d - Pfc_s tem solucao analitica exponencial, entao
%NAO ha necessidade de sub-passos numericos -- inclusive para o valor
%MEDIO de potencia fornecida dentro do passo (integral fechada), usado
%para o balanco de H2/energia em vez do valor instantaneo no fim do
%passo (que superestimaria o consumo assumindo que a rampa de subida ja
%terminou).
%
%Entradas:
%   Pfc_d_kW potencia DEMANDADA (setpoint/decisao do otimizador)
%   Pfc_s_prev_kW potencia efetivamente FORNECIDA no INICIO do passo (estado)
%   Ts_s duracao do passo [s]
%   tau_s constante de tempo [s] (tau_FC=4 planta real | tau_f=0.2 MPC)
%   kf ganho estatico em regime permanente (1)
%
%Saida (struct):
%   out.Pfc_s_end potencia fornecida ao final do passo (novo estado, usar
%                  para propagar Pfc_s_prev no proximo passo)
%   out.Pfc_s_avg potencia edia fornecida durante o passo (integral
%                 da exponencial) -- usar no calculo de mH2/energia
%   out.alpha fator de decaimento exp(-Ts/tau) (diagnostico)

if nargin < 5 || isempty(kf)
    kf = 1;
end

if tau_s <= 0
    % Compatibilidade/degenerado: resposta instantanea (tau -> 0)
    out.Pfc_s_end = kf*Pfc_d_kW;
    out.Pfc_s_avg = kf*Pfc_d_kW;
    out.alpha = 0;
    return
end

alpha = exp(-Ts_s/tau_s);
Pfc_ss = kf*Pfc_d_kW; % setpoint em regime permanente (t -> infinito)

out.Pfc_s_end = Pfc_ss + (Pfc_s_prev_kW - Pfc_ss)*alpha;

if Ts_s > 0
    % Integral fechada de Pfc_s(t) = Pfc_ss + (Pfc_s_prev-Pfc_ss)*exp(-t/tau)
    % em [0,Ts], dividida por Ts:
    out.Pfc_s_avg = Pfc_ss + (Pfc_s_prev_kW - Pfc_ss) * (tau_s/Ts_s) * (1 - alpha);
else
    out.Pfc_s_avg = out.Pfc_s_end;
end

out.alpha = alpha;
end
