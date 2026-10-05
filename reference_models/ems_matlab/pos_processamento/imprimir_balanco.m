function imprimir_balanco(ind, res, nome_alg)
%IMPRIMIR_BALANCO no command window
fprintf('\n=============================================================\n');
fprintf('                      BALANÇO FINAL                          \n');
fprintf('=============================================================\n');
fprintf('Algoritmo:                      %s\n', nome_alg);
fprintf('Consumo Total da Carga:     %10.2f kWh\n', ind.E_load);
fprintf('-------------------------------------------------------------\n');
fprintf('DISTRIBUIÇÃO POR TIPO DE CARGA\n');
fprintf('Propulsão:                  %10.2f kWh (%5.1f%%)\n', ind.E_prop,  100*ind.E_prop/ind.E_load);
fprintf('Hotelaria:                  %10.2f kWh (%5.1f%%)\n', ind.E_hotel, 100*ind.E_hotel/ind.E_load);
fprintf('Auxiliares:                 %10.2f kWh (%5.1f%%)\n', ind.E_aux,   100*ind.E_aux/ind.E_load);
fprintf('-------------------------------------------------------------\n');
fprintf('FONTES\n');
fprintf('Célula a Combustível:       %10.2f kWh (%5.1f%%)\n', ind.E_fc,    100*ind.E_fc/ind.E_load);
fprintf('Solar (PV):                 %10.2f kWh (%5.1f%%)\n', ind.E_pv,    100*ind.E_pv/ind.E_load);
if isfield(ind, 'E_extra')
fprintf('Fonte extra:                %10.2f kWh (%5.1f%%)\n', ind.E_extra, 100*ind.E_extra/ind.E_load);
end
fprintf('Bateria (descarga):         %10.2f kWh (%5.1f%%)\n', ind.E_bat_d, 100*ind.E_bat_d/ind.E_load);
fprintf('Bateria (recarga):          %10.2f kWh (%5.1f%%)\n', ind.E_bat_c, 100*ind.E_bat_c/ind.E_load);
fprintf('---------------------------------------------------------------\n');
fprintf('INDICADORES\n');
fprintf('H2 total consumido:                    %10.4f kg\n', ind.H2_total);
fprintf('Degradação acumulada:                   %10.2e\n',    ind.Dbat_tot);
fprintf('Erro médio de balanco DC (resíduo NMPC):%6.2f kW\n', mean(abs(ind.erro_total)));
fprintf('Atraso FC Pilar 1 (setpoint x entregue):%6.2f kW\n', ind.erro_lag_pilar1_medio);
fprintf('Diferença média meta. vs refino:          %5.3f kW\n', ind.diff_media);
fprintf('Diferenca máxima meta. vs refino:         %5.3f kW\n', ind.diff_maxima);
fprintf('SOC final:                          %10.1f %%\n', res.SOC_final*100);
fprintf('Tempo de otimização:                %10.1f s\n',  res.tempo_total);
fprintf('------------------------------------------------------------------\n');
fprintf('ATENDIMENTO DA DEMANDA (após compensação da bateria)\n');
if ind.deficit_total_kWh <= 1e-6 && ind.deficit_n_passos == 0
    fprintf('Demanda 100%% atendida em todos os passos simulados.\n');
else
    fprintf('Demanda NÃO foi 100%% atendida.\n');
    fprintf('Energia total não atendida:        %10.2f kWh\n', ind.deficit_total_kWh);
    fprintf('Déficit instântaneo máximo:         %10.2f kW\n', ind.deficit_max_kW);
    fprintf('Número de passos com déficit:   %10d de %d\n', ind.deficit_n_passos, numel(ind.deficit_kW));
end
fprintf('==================================================================\n\n');
end