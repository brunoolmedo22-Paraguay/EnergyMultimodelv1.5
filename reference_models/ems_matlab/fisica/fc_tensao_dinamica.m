function V_fc_lag = fc_tensao_dinamica(V_fc_estatica, V_fc_prev, Ts_s, tau_v_s)
%FC_TENSAO_DINAMICA Atraso de tensao da celula (PILAR 2): a tensao
%terminal da FC nao acompanha instantaneamente a corrente/potencia --
%fenomenos de dupla camada eletroquimica e difusao de gases nos canais
%fazem a tensao real convergir para a curva estatica (fc_tensao_estatica.m)
%somente apos um transiente de aproximadamente 3*tau - Trinh et al., 2022 https://doi.org/10.1007/s40684-022-00498-w
%
%Modelado com a mesma estrutura de 1a ordem usada na potencia (Pilar 1,
%fc_dinamica.m), com tau_v_s = arch.fc.tau_FC_s (a constante de tempo
%termica/eletroquimica "lenta" da FC -- a tensao acompanha a mesma
%dinamica fisica que a potencia entregue, nao a dinamica rapida de
%atuador tau_f usada so dentro da predicao do NMPC).
%
%Uso tipico (ver constraints_hibrido.m): propagar V_fc_lag passo a passo
%ao longo do horizonte e usa-la (em vez da tensao estatica) nas
%restricoes de sub/sobretensao -- isso IMPEDE que o otimizador aceite
%rampas de potencia tao rapidas que a tensao real cairia fora da faixa
%segura antes de estabilizar, mesmo que a potencia media fique dentro do
%range V_out_range_V em regime permanente.
%
%Entradas:
%   V_fc_estatica tensao-alvo em regime permanente no passo atual [V]
%                  (fc_tensao_estatica.m aplicada a Pfc do passo)
%   V_fc_prev tensao efetiva (com atraso) no inicio do passo [V]
%   Ts_s duracao do passo [s]
%   tau_v_s constante de tempo do atraso de tensao [s]
%
%Saida:
%   V_fc_lag tensao efetiva (com atraso) ao FINAL do passo [V]

    if tau_v_s <= 0
        V_fc_lag = V_fc_estatica;
        return
    end
    alpha = exp(-Ts_s/tau_v_s);
    V_fc_lag = V_fc_estatica + (V_fc_prev - V_fc_estatica)*alpha;
end
