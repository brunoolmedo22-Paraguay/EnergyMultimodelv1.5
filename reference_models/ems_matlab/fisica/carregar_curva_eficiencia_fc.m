function [eff_P_kW, eff_eta_pct] = carregar_curva_eficiencia_fc(cenario, arch)
%CARREGAR_CURVA_EFICIENCIA_FC Ponto UNICO para a curva eta_fc(P) usada
%por fc_efficiency.m. precisa ter: dois vetores de mesmo comprimento (kW),
%Trocar a fonte da curva (tabela digitalizada vs. modelo analitico
%Eq.2 de Jiang et al., em arch.fc.eff_coefs) so precisa mexer aqui.
    switch cenario.eff_fc.tipo
        case 'tabela_mat'
            D = load(cenario.eff_fc.arquivo);
            eff_P_kW    = D.eff_P_kW(:);
            eff_eta_pct = D.eff_eta_pct(:);
        case 'modelo_analitico'
            % eta_PEMFC(P) = a*exp(b*P) + c*exp(d*P)  (Eq.2, Jiang et al.)
            P = linspace(0, arch.fc.P_max_tot_kW/arch.fc.N_fc, 200)';
            coef = arch.fc.eff_coefs(1,:); % stack 1; adapte se quiser eff por-stack
            eff_frac = coef(1)*exp(coef(2)*P) + coef(3)*exp(coef(4)*P);
            eff_P_kW = P;
            eff_eta_pct = eff_frac*100;
        otherwise
            error('Tipo de curva de eficiencia da FC desconhecido: %s (ver config_cenario.m)', cenario.eff_fc.tipo);
    end
end
