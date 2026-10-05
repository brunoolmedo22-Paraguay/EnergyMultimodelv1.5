function mH2_bat = battery_h2_equiv(delta, Pbat_kW_abs, a_ratio, Ts)
%BATTERY_H2_EQUIV  - Massa de H2 equivalente ao ciclo de carga/descarga da
%bateria (Eq.9-13, Zhang et al. 2025). 'delta' ja incorpora as
%eficiencias de carga/descarga da bateria (calculadas em bateria_step,
%pois dependem do sinal de Pbat). 'a_ratio' [kg/kWh] e a taxa media de
%consumo de H2 da FC = 1/(Elow*eta_fc) -- NUNCA usar so 1/Elow, isso
%assume FC 100% eficiente 
    mH2_bat = delta * Pbat_kW_abs * a_ratio / 3600 * Ts; % kg no passo Ts
end
