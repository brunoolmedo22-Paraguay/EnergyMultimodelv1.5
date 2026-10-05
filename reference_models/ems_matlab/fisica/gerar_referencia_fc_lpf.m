function [Pfc_LF_kW, Pdelta_HF_kW] = gerar_referencia_fc_lpf(P_deficit_kW, Ts_s, T_lpf_s)
%GERAR_REFERENCIA_FC_LPF Desacoplamento de Frequencia (PILAR 2) via
%Filtro Passa-Baixa (LPF) de 1a ordem: separa o deficit de potencia do
%barramento DC (carga - PV) em
%
%   Pfc_LF_kW componente de BAIXA frequencia -> referencia de rastreio
%                da FC (lenta, cara de ciclar/degradar)
%   Pdelta_HF_kW residuo de ALTA frequencia -> fica para bateria
%                (respondem rapido, penalidade de ciclagem menor)
%
% a FC so precisa acompanhar a tendencia lenta da carga, nao os transientes.
%
%Implementado como EMA (media movel exponencial) causal -- discretizacao
%do LPF continuo H(s) = 1/(1+s*T_lpf) sob ZOH, aplicada sobre o
%PERFIL DE CARGA COMPLETO (a mesma logica "offline"
%usada no Pilar 4: o perfil de missao e conhecido de ponta a ponta antes
%do despacho, carregado em main.m/processar_carga.m). Isso e DIFERENTE e
%COMPLEMENTAR ao atraso FISICO real da FC (Pilar 1, fc_dinamica.m): aqui
%é decidido o que a FC deve tentar seguir (uma curva ja suavizada); la
%é modelado como a FC fisicamente responde (com atraso) a esse alvo.
%Trinh et al., 2022 https://doi.org/10.1007/s40684-022-00498-w
%
%Entradas:
%   P_deficit_kW  vetor Nx1, deficit de potencia no barramento DC
%                 (P_load - eta_dc*Ppv), tipicamente ja calculado em main.m
%   Ts_s passo de amostragem do vetor de entrada [s]
%   T_lpf_s constante de tempo do LPF [s]. Deve ser >> tau_FC (Pilar 1) para que o "baixa frequencia" da FC nao brigue com a
%           propria dinamica fisica dela.
%
%Saidas:
%   Pfc_LF_kW referencia de baixa frequencia p/ a FC (>=0, sem regen na FC)
%   Pdelta_HF_kW residuo de alta frequencia (pode ser negativo -> carga
%                 da bateria/regen) = P_deficit - Pfc_LF

P_deficit_kW = P_deficit_kW(:);
N = numel(P_deficit_kW);
Pfc_LF_kW = zeros(N,1);

if T_lpf_s <= 0
    Pfc_LF_kW = max(P_deficit_kW, 0);
else
    beta = 1 - exp(-Ts_s/T_lpf_s); % ganho do EMA equivalente ao LPF continuo
    Pfc_LF_kW(1) = max(P_deficit_kW(1), 0);
    for k = 2:N
        Pfc_LF_kW(k) = Pfc_LF_kW(k-1) + beta*(P_deficit_kW(k) - Pfc_LF_kW(k-1));
    end
    Pfc_LF_kW = max(Pfc_LF_kW, 0);
end

Pdelta_HF_kW = P_deficit_kW - Pfc_LF_kW;
end
