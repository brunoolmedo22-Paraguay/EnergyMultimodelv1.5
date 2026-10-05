function validar_arch(arch, P_load_kW_original, Ppv_kW)
%VALIDAR_ARCH Checagem rapida do config de arquitetura antes
%de rodar o NMPC: campos obrigatorios presentes + viabilidade fisica
%basica (potencia instalada vs. pico de carga). Roda para QUALQUER
%embarcacao/cenario 
    campos_obrigatorios = {'fc','bat','pv','conv','motor','inverter','ship','ems'};
    for i = 1:numel(campos_obrigatorios)
        if ~isfield(arch, campos_obrigatorios{i})
            error('validar_arch:campoFaltando', ...
                'arch.%s nao encontrado -- confira o arquivo arquitetura_*.m do cenario.', campos_obrigatorios{i});
        end
    end

    P_pico_kW = max(P_load_kW_original);
    P_instalada_kW = arch.fc.P_max_tot_kW + arch.bat.P_max_discharge_kW + arch.pv.P_rated_kWp;
    if P_instalada_kW < P_pico_kW
        warning('validar_arch:capacidadeInsuficiente', ...
            ['Potencia instalada total (FC+Bateria+PV = %.0f kW) e menor que ' ...
             'o pico de carga (%.0f kW) -- o EMS pode nao ter folga suficiente ' ...
             'em alguns instantes.'], P_instalada_kW, P_pico_kW);
    end

    if max(Ppv_kW) > arch.pv.P_rated_kWp * 1.01
        warning('validar_arch:pvAcimaDoNominal', ...
            'PV interpolado (%.1f kW) excede a potencia nominal declarada (%.1f kWp).', ...
            max(Ppv_kW), arch.pv.P_rated_kWp);
    end
end
