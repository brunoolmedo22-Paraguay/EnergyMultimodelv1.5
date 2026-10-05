function eta = fc_efficiency(P_kW, eff_P_kW, eff_eta_pct)
%FC_EFFICIENCY Interpola a curva eta_fc(P) (por stack). eff_P_kW/
%eff_eta_pct vem de carregar_curva_eficiencia_fc.m -- trocar de fonte de
%dados (tabela digitalizada vs. modelo analitico) nao muda esta funcao.
    P_c = min(max(P_kW, min(eff_P_kW)), max(eff_P_kW));
    eta = max(interp1(eff_P_kW, eff_eta_pct, P_c, 'pchip'), 1e-3) / 100;
end
