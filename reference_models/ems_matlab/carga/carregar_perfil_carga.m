function [t_min, P_load_kW, Pfc_req_kW] = carregar_perfil_carga(cenario)
%CARREGAR_PERFIL_CARGA Ponto UNICO de entrada da carga
%Para trocar perfil de carga editar cenario.perfil (em config_cenario.m) 
%nenhum outro arquivo do projeto precisa mudar, porque tudo daqui pra frente so
%conhece o contrato [t_min, P_load_kW, Pfc_req_kW].

    switch cenario.perfil.tipo
        case 'mat_artigo'
            [t_min, P_load_kW, Pfc_req_kW] = preparar_carga_artigo(cenario.perfil.arquivo);
        case 'csv_generico'
            [t_min, P_load_kW, Pfc_req_kW] = carregar_perfil_csv(cenario.perfil.arquivo, cenario.perfil);
        case 'csv_walkforward'
            [t_min, P_load_kW, Pfc_req_kW] = carregar_perfil_walkforward(cenario.perfil.arquivo, cenario.perfil);
        otherwise
            error('Tipo de perfil de carga desconhecido: %s (ver config_cenario.m)', cenario.perfil.tipo);
    end
end
