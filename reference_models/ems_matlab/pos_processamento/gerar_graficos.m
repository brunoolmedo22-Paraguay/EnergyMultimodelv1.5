function gerar_graficos(res, sinais, nmpc, cenario, nome_alg, varargin)
%GERAR_GRAFICOS Reproduz os graficos do main_hibrido.m original (perfil
%solar, despacho, comparacao meta-heuristica x refino SQP, e
%contingencia se ativa), a partir dos structs res/sinais.
    p = inputParser;
    addParameter(p, 'mostrar_atraso_fc', false);
    addParameter(p, 'janela_passos', 8);
    parse(p, varargin{:});
    mostrar_atraso_fc = p.Results.mostrar_atraso_fc;
    janela_passos     = p.Results.janela_passos;

    t_sim = res.t_sim; t_min = sinais.t_min;
    Pfc_kW_plot       = res.Pfc_s_real_hist(t_sim);      % PILAR 1: potencia REALMENTE entregue
    Pfc_setpoint_plot = res.Pfc_hist(t_sim) * nmpc.S_base; % setpoint demandado (referencia, mostra o atraso)
    Pbat_kW_plot = res.Pbat_hist(t_sim) * nmpc.S_base;
    Ppv_kW_plot  = sinais.Ppv_kW(t_sim);
    P_load_plot  = sinais.P_load_kW(t_sim);
    if isfield(res, 'Pext_hist')
        Pext_kW_plot = res.Pext_hist(t_sim);
    else
        Pext_kW_plot = zeros(size(t_sim(:)));
    end
    tmax = max(t_min(t_sim));

    %% Perfil solar
    figure('Color','w','Position',[100 100 600 350]);
    plot(t_min(t_sim), Ppv_kW_plot, 'g', 'LineWidth', 1.8);
    grid off; box off;
    ax = gca; ax.Color='white'; ax.FontName='Times New Roman'; ax.FontSize=12;
    ax.XColor='k'; ax.YColor='k'; ax.LineWidth=1; xlim([0 tmax]);
    xlabel('Tempo (min)'); ylabel('Potencia (kW)');
    title('Perfil de Geracao Fotovoltaica', 'Color', 'k', 'FontSize',12, 'FontName','Times New Roman');
    set(gcf,'Color','w');
    %exportgraphics(gcf, sprintf('Perfil_solar_%s_%s.emf', nome_alg, cenario.tag), 'ContentType','vector');

    %% Despacho de potencia
    figure('Color','w','Position',[100 100 600 350]);
    plot(t_min(t_sim), P_load_plot,'k','LineWidth',1.5,'DisplayName','Carga'); hold on;
    plot(t_min(t_sim), Ppv_kW_plot,'g','LineWidth',1.2,'DisplayName','PV');
    plot(t_min(t_sim), Pfc_kW_plot,'r','LineWidth',1.2,'DisplayName','FC (entregue)');
    plot(t_min(t_sim), Pfc_setpoint_plot,'r--','LineWidth',0.9,'DisplayName','FC (setpoint)');
    plot(t_min(t_sim), Pbat_kW_plot,'b','LineWidth',1.2,'DisplayName','Bateria');
    plot(t_min(t_sim), Pext_kW_plot,'m-.','LineWidth',1.2,'DisplayName','Fonte extra');
    hold off; grid off; box off;
    ax = gca; ax.Color='white'; ax.FontName='Times New Roman'; ax.FontSize=12;
    ax.XColor='k'; ax.YColor='k'; ax.LineWidth=1;
    xlabel('Tempo (min)'); ylabel('Potencia (kW)'); xlim([0 tmax]);
    title(sprintf('Despacho de potência'),'Color', 'k', 'FontSize',12, 'FontName','Times New Roman');
    lgd = legend('Location','northwest');
    lgd.FontName='Times New Roman'; lgd.FontSize=10; lgd.TextColor='k';
    lgd.Color='w'; lgd.EdgeColor='k'; lgd.Box='off';
    set(gcf,'Color','w');
    %exportgraphics(gcf, sprintf('Despacho_%s_%s.emf', nome_alg, cenario.tag), 'ContentType','vector');

    %% Comparacao meta-heuristica x refino SQP
    figure('Color','w','Position',[100 100 600 350]);
    plot(t_min(t_sim), res.Pfc_meta_hist(t_sim),'k-','LineWidth',1.5,'DisplayName','Metaheuristica'); hold on
    plot(t_min(t_sim), res.Pfc_refino_hist(t_sim),'r','LineWidth',1.2, 'DisplayName','Refinamento');
    yline(0,'k:','HandleVisibility','off');
    hold off; grid off; box off;
    ax = gca; ax.Color='white'; ax.FontName='Times New Roman'; ax.FontSize=12;
    ax.XColor='k'; ax.YColor='k'; ax.LineWidth=1;
    xlabel('Tempo (min)'); ylabel('Potencia (kW)'); xlim([0 tmax]);
    title(sprintf('Algoritmos'),'Color', 'k', 'FontSize',12, 'FontName','Times New Roman');
    lgd = legend('Location','southeast');
    lgd.FontName='Times New Roman'; lgd.FontSize=12; lgd.TextColor='k';
    lgd.Color='w'; lgd.EdgeColor='k'; lgd.Box='off';
    set(gcf,'Color','w');
    %exportgraphics(gcf, sprintf('Algoritmos_%s_%s.emf', nome_alg, cenario.tag), 'ContentType','vector');

    %% Contingencia (so se ativa) -- carga original x carga efetiva
    if sinais.conting.ativa
        figure('Color','w','Position',[100 100 600 350]);
        plot(t_min(t_sim), sinais.P_load_kW_original(t_sim),'k--','LineWidth',1.3,'DisplayName','Carga original (sem falha)'); hold on;
        plot(t_min(t_sim), P_load_plot,'r','LineWidth',1.5,'DisplayName','Carga efetiva (com falha de motor)');
        yline(sinais.P_prop_max_kW,'b:','LineWidth',1.2, ...
            'DisplayName',sprintf('Limite propulsao (%d motor(es) ok)', sinais.N_motores_ok));
        hold off; grid off; box off;
        ax = gca; ax.Color='white'; ax.FontName='Times New Roman'; ax.FontSize=12;
        ax.XColor='k'; ax.YColor='k'; ax.LineWidth=1;
        xlabel('Tempo (min)'); ylabel('Potencia (kW)'); xlim([0 tmax]);
        title(sprintf('Contingencia: %d motor(es) falho(s)', sinais.conting.motores_falhos), ...
            'Color','k','FontSize',12,'FontName','Times New Roman');
        lgd = legend('Location','best');
        lgd.FontName='Times New Roman'; lgd.FontSize=10; lgd.TextColor='k';
        lgd.Color='w'; lgd.EdgeColor='k'; lgd.Box='off';
        set(gcf,'Color','w');
        %exportgraphics(gcf, sprintf('Contingencia_%s_%s.emf', nome_alg, cenario.tag), 'ContentType','vector');
    end

    %% Atraso da FC (Pilar 1) x compensacao da bateria -- zoom no maior
    % transiente de setpoint da simulacao real (opcional, so se pedido)
    if mostrar_atraso_fc
        % t_sim comeca em k=2 (ver ems_dispatch.m); dPfc so faz sentido a
        % partir do 2o passo simulado em diante.
        idx_validos = t_sim(2:end);
        dPfc_kW = abs(diff(res.Pfc_hist(idx_validos))) * nmpc.S_base;
        if isempty(dPfc_kW) || all(dPfc_kW == 0)
            warning('gerar_graficos:semTransiente', ...
                ['Nao foi encontrada variacao de setpoint da FC na simulacao ' ...
                 '-- pulando a figura de atraso da FC (Pilar 1).']);
        else
            [dPfc_max, imax] = max(dPfc_kW);
            k_transiente = idx_validos(imax+1); % indice absoluto do passo com maior salto

            k_ini = max(idx_validos(1),   k_transiente - janela_passos);
            k_fim = min(idx_validos(end), k_transiente + janela_passos);
            janela = k_ini:k_fim;

            Pfc_set_j = res.Pfc_hist(janela) * nmpc.S_base;
            Pfc_ent_j = res.Pfc_s_real_hist(janela);
            Pbat_ot_j = res.Pbat_setpoint_hist(janela) * nmpc.S_base; % decisao original do otimizador
            Pbat_ap_j = res.Pbat_hist(janela) * nmpc.S_base; % valor CORRIGIDO/aplicado

            figure('Color','w','Position',[100 100 600 350]);
            subplot(2,1,1);
            plot(t_min(janela), Pfc_set_j, 'r--', 'LineWidth',1.3, 'DisplayName','FC setpoint'); hold on;
            plot(t_min(janela), Pfc_ent_j, 'r-',  'LineWidth',2.0, 'DisplayName','FC entregue (real, \tau_{FC})');
            xline(t_min(k_transiente), 'Color',[0.85 0.6 0.2], 'LineWidth',1.2, 'HandleVisibility','off');
            hold off; grid off; box off;
            ax = gca; ax.Color='white'; ax.FontName='Times New Roman'; ax.FontSize=12;
            ax.XColor='k'; ax.YColor='k'; ax.LineWidth=1;
            ylabel('Potencia FC (kW)');
            title(sprintf('Pilar 1 -- Atraso da FC | maior \\DeltaPfc = %.1f kW em t=%.1f min', ...
               dPfc_max, t_min(k_transiente)), ...
                'Color','k','FontSize',11,'FontName','Times New Roman');
            lgd = legend('Location','best');
            lgd.FontName='Times New Roman'; lgd.FontSize=10; lgd.TextColor='k';
            lgd.Color='w'; lgd.EdgeColor='k'; lgd.Box='off';

            subplot(2,1,2);
            plot(t_min(janela), Pbat_ot_j, 'b--', 'LineWidth',1.3, 'DisplayName','Pbat decidido (otimizador)'); hold on;
            plot(t_min(janela), Pbat_ap_j, 'b-',  'LineWidth',2.0, 'DisplayName','Pbat aplicado (corrigido)');
            yline(0,'k:','HandleVisibility','off');
            xline(t_min(k_transiente), 'Color',[0.85 0.6 0.2], 'LineWidth',1.2, 'HandleVisibility','off');
            hold off; grid off; box off;
            ax = gca; ax.Color='white'; ax.FontName='Times New Roman'; ax.FontSize=12;
            ax.XColor='k'; ax.YColor='k'; ax.LineWidth=1;
            xlabel('Tempo (min)'); ylabel('Potencia Bateria (kW)');
            lgd = legend('Location','best');
            lgd.FontName='Times New Roman'; lgd.FontSize=10; lgd.TextColor='k';
            lgd.Color='w'; lgd.EdgeColor='k'; lgd.Box='off';

            set(gcf,'Color','w');
            %exportgraphics(gcf, sprintf('AtrasoFC_%s_%s.emf', nome_alg, cenario.tag), 'ContentType','vector');
        end
    end
end