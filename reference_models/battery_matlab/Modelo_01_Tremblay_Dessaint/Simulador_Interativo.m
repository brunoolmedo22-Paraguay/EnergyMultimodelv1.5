% =========================================================================
%  INTERACTIVE BATTERY SIMULATOR — Tremblay & Dessaint (2009)
%  
%  PURPOSE:
%    This script provides an interactive Command Window interface that allows
%    the user to choose a battery chemistry and define a custom, sequential
%    current profile over time (combining multiple charge/discharge stages).
% =========================================================================

clear; clc; close all;

% =========================================================================
%  SECTION 1 — BATTERY PARAMETERS  (Table 1 of the paper)
% =========================================================================
batteries = struct();

batteries(1).name  = 'Lead-Acid (12V, 7.2Ah)';
batteries(1).type  = 'lead_acid';   
batteries(1).E0    = 12.4659;  batteries(1).R     = 0.04;     
batteries(1).K     = 0.047;     batteries(1).A     = 0.83;     
batteries(1).B     = 125;       batteries(1).Q     = 7.2;      
batteries(1).Vnom  = 12.0;

batteries(2).name  = 'NiCd (1.2V, 2.3Ah)';
batteries(2).type  = 'nimh_nicd';  
batteries(2).E0    = 1.2705;    batteries(2).R     = 0.003;
batteries(2).K     = 0.0037;    batteries(2).A     = 0.127;
batteries(2).B     = 4.98;      batteries(2).Q     = 2.3;
batteries(2).Vnom  = 1.2;

batteries(3).name  = 'Li-Ion (3.3V, 2.3Ah)';
batteries(3).type  = 'li_ion';     
batteries(3).E0    = 3.366;     batteries(3).R     = 0.01;
batteries(3).K     = 0.0076;    batteries(3).A     = 0.26422;
batteries(3).B     = 26.5487;   batteries(3).Q     = 2.3;
batteries(3).Vnom  = 3.3;

batteries(4).name  = 'NiMH (1.2V, 6.5Ah)';
batteries(4).type  = 'nimh_nicd';  
batteries(4).E0    = 1.2816;    batteries(4).R     = 0.002;
batteries(4).K     = 0.0014;    batteries(4).A     = 0.111;
batteries(4).B     = 2.3077;    batteries(4).Q     = 6.5;
batteries(4).Vnom  = 1.2;

dt  = 1;   % Passo de integração fixo em 1 segundo
tau = 30;  % Constante de filtro do modelo

% =========================================================================
%  INTERFACE INTERATIVA DO USUÁRIO (COMMAND WINDOW)
% =========================================================================
fprintf('=================================================================\n');
fprintf('       SIMULADOR INTERATIVO DE BATERIAS (Tremblay-Dessaint)      \n');
fprintf('=================================================================\n\n');

% 1. Escolha da Bateria
fprintf('Escolha o tipo de bateria para a simulação:\n');
for idx = 1:4
    fprintf('  [%d] %s\n', idx, batteries(idx).name);
end
fprintf('\n');

escolha = 0;
while escolha < 1 || escolha > 4
    escolha = input('Digite o número correspondente (1-4): ');
    if escolha < 1 || escolha > 4
        fprintf('Opção inválida! Escolha um número entre 1 e 4.\n');
    end
end

bat = batteries(escolha);
fprintf('\n-> Você selecionou a bateria: %s\n', bat.name);
fprintf('-----------------------------------------------------------------\n\n');

% 2. Coleta das Condições Temporais de Corrente
i_profile_blocks = []; % Armazena o valor da corrente de cada bloco
t_profile_blocks = []; % Armazena a duração de cada bloco em segundos

adicionar_mais = true;
bloco_id = 1;

while adicionar_mais
    fprintf('--- CONFIGURAÇÃO DO BLOCO %d ---\n', bloco_id);
    
    % Input da Corrente
    current_val = input('Injete o valor da corrente em Amperes (Carga = Negativo | Descarga = Positivo): ');
    
    % Input do Tempo
    time_val = input('Injete o tempo de duração dessa condição (em segundos): ');
    while time_val <= 0
        fprintf('O tempo deve ser maior que zero!\n');
        time_val = input('Injete o tempo de duração dessa condição (em segundos): ');
    end
    
    % Salva os dados informados
    i_profile_blocks = [i_profile_blocks; current_val];
    t_profile_blocks = [t_profile_blocks; time_val];
    
    fprintf('\nBlodo %d adicionado com sucesso!\n', bloco_id);
    fprintf('-----------------------------------------------------------------\n');
    
    % Pergunta se deseja adicionar mais uma etapa
    resposta = '';
    while ~strcmpi(resposta, 'S') && ~strcmpi(resposta, 'N')
        resposta = input('Deseja adicionar outra condição? [S/N]: ', 's');
        if ~strcmpi(resposta, 'S') && ~strcmpi(resposta, 'N')
            fprintf('Resposta inválida! Digite S para Sim ou N para Não.\n');
        end
    end
    
    if strcmpi(resposta, 'N')
        adicionar_mais = false;
    else
        bloco_id = bloco_id + 1;
        fprintf('\n');
    end
end

% =========================================================================
%  CONSTRUÇÃO DOS VETORES TEMPORAIS CONTINUOS
% =========================================================================
fprintf('\nProcessando e construindo o perfil temporal unificado...\n');

total_time_seconds = sum(t_profile_blocks);
t_real = (0:dt:total_time_seconds)';
N_total = length(t_real);
i_real = zeros(N_total, 1);

% Preenche o vetor continuo de corrente baseado nos blocos informados
current_index = 1;
for b = 1:length(t_profile_blocks)
    steps_in_block = round(t_profile_blocks(b) / dt);
    end_index = current_index + steps_in_block;
    
    % Evita estourar o tamanho do vetor por aproximações de ponto flutuante
    if end_index > N_total
        end_index = N_total; 
    end
    
    i_real(current_index:end_index) = i_profile_blocks(b);
    current_index = end_index + 1;
end

% Ensure the last element matches the last block current
if current_index <= N_total
    i_real(current_index:end_index) = i_profile_blocks(end);
end

% =========================================================================
%  EXECUÇÃO DA SIMULAÇÃO TEMPORAL
% =========================================================================
fprintf('Executando simulação temporal dinâmica... Por favor, aguarde.\n');

Vbatt_total  = zeros(N_total, 1);
SOC_total    = zeros(N_total, 1);
Exp_total    = zeros(N_total, 1);
istar_total  = zeros(N_total, 1);

% Condições Iniciais: Bateria começa 100% carregada
it_total       = 0; 
Exp_total(1)   = bat.A; 
istar_total(1) = 0;
SOC_total(1)   = 1.0;
Vbatt_total(1) = battery_voltage(bat, it_total, 0, Exp_total(1), i_real(1));

for k = 2:N_total
    i_k = i_real(k);
    
    % 1. Filtro da corrente i*
    istar_total(k) = istar_total(k-1) + (dt/tau) * (i_k - istar_total(k-1));
    
    % 2. Termo exponencial dinâmico com tratamento de histerese
    if strcmp(bat.type, 'li_ion')
        Exp_total(k) = bat.A * exp(-bat.B * it_total);
    else
        if i_k >= 0
            % Descarga direciona o termo Exp para 0
            dExp = bat.B * abs(i_k) * (-Exp_total(k-1) + bat.A * 0);
        else
            % Carga direciona o termo Exp para bat.A
            dExp = bat.B * abs(i_k) * (-Exp_total(k-1) + bat.A * 1);
        end
        Exp_total(k) = Exp_total(k-1) + dExp * dt;
        Exp_total(k) = max(0, min(bat.A, Exp_total(k)));
    end
    
    % 3. Cálculo da Tensão do Terminal
    Vbatt_total(k) = battery_voltage(bat, it_total, istar_total(k), Exp_total(k), i_k);
    
    % 4. Integração de Coulomb (Cálculo do SOC)
    it_total = it_total + i_k * (dt/3600);
    it_total = max(0, min(bat.Q, it_total)); % Salvaguarda física da capacidade
    
    SOC_total(k) = max(0, 1 - it_total / bat.Q);
    
    % Interrupção de segurança se a bateria zerar por completo antes do tempo programado
    if SOC_total(k) <= 0.001 && i_k > 0
        fprintf('  [AVISO]: A bateria descarregou totalmente em t = %d s. Encerrando simulação prematuramente.\n', t_real(k));
        N_total = k;
        t_real = t_real(1:N_total);
        Vbatt_total = Vbatt_total(1:N_total);
        i_real = i_real(1:N_total);
        SOC_total = SOC_total(1:N_total);
        break;
    end
end

% =========================================================================
%  COMPLEMENTO: SIMULAÇÃO STEADY-STATE (CURVA PADRÃO PARA COMPARAÇÃO)
% =========================================================================
% Gera curvas de referência a 1C para plotar na aba de comparação
Ic_ref = 1.0 * bat.Q;
dt_ss = 0.5;
max_steps = ceil((bat.Q / Ic_ref) * 3600 / dt_ss * 1.1);
V_ss_ref = zeros(max_steps, 1); Q_ss_ref = zeros(max_steps, 1);
it_ss = 0; Exp_ss = bat.A; istar_ss = 0;
V_ss_ref(1) = battery_voltage(bat, 0, 0, bat.A, Ic_ref);

for k = 2:max_steps
    istar_ss = istar_ss + (dt_ss/tau) * (Ic_ref - istar_ss);
    if strcmp(bat.type, 'li_ion')
        Exp_ss = bat.A * exp(-bat.B * it_ss);
    else
        dExp = bat.B * Ic_ref * (-Exp_ss + bat.A * 0);
        Exp_ss = Exp_ss + dExp * dt_ss;   Exp_ss = max(0, Exp_ss);
    end
    V_ss_ref(k) = battery_voltage(bat, it_ss, istar_ss, Exp_ss, Ic_ref);
    it_ss = it_ss + Ic_ref * (dt_ss / 3600);
    Q_ss_ref(k) = it_ss;
    if it_ss >= 0.99 * bat.Q || V_ss_ref(k) < 0.5 * bat.Vnom; break; end
end
k_end_ss = k;

% =========================================================================
%  INTERFACE GRÁFICA EM ABAS (OUTPUT)
% =========================================================================
main_fig = figure('Name', ['Simulação Customizada — ' bat.name], ...
                  'NumberTitle', 'off', ...
                  'Units', 'normalized', 'Position', [0.1, 0.1, 0.8, 0.8]);
tgroup = uitabgroup('Parent', main_fig);

% --- ABA 1: COMPORTAMENTO TEMPORAL CUSTOMIZADO ---
tab_time = uitab('Parent', tgroup, 'Title', 'Análise Temporal Customizada');

ax1 = subplot(4,1,1, 'Parent', tab_time);
plot(t_real, Vbatt_total, 'b-', 'LineWidth', 1.6);
ylabel('V_{batt} (V)'); title(['Resposta de Tensão Temporal — ' bat.name]); grid on;
ylim([bat.Vnom * 0.6, max(Vbatt_total)*1.1]); set(ax1,'XTickLabel',[]);

ax2 = subplot(4,1,2, 'Parent', tab_time);
plot(t_real, i_real, 'r-', 'LineWidth', 1.4);
ylabel('I_{batt} (A)'); title('Perfil de Corrente Injetado/Consumido'); grid on;
set(ax2,'XTickLabel',[]);

ax3 = subplot(4,1,3, 'Parent', tab_time);
plot(t_real, SOC_total*100, 'g-', 'LineWidth', 1.6);
ylabel('SOC (%)'); title('Estado de Carga'); grid on; ylim([-5 105]);
set(ax3,'XTickLabel',[]);

ax4 = subplot(4,1,4, 'Parent', tab_time);
Power_total = Vbatt_total .* i_real;
plot(t_real, Power_total, 'm-', 'LineWidth', 1.2);
ylabel('Potência (W)'); title('Potência Instantânea (Positiva = Saída | Negativa = Entrada)'); 
grid on; xlabel('Tempo (segundos)');

% --- ABA 2: VISUALIZAÇÃO NO REGIME PERMANENTE ---
tab_ss = uitab('Parent', tgroup, 'Title', 'Posicionamento na Curva Estática');
ax_ss = axes('Parent', tab_ss);
plot(ax_ss, Q_ss_ref(1:k_end_ss), V_ss_ref(1:k_end_ss), 'k--', 'LineWidth', 1.5, 'DisplayName', 'Referência Descarga Constante (1C)');
hold(ax_ss, 'on'); grid(ax_ss, 'on');

% Converte a carga retirada na simulação temporal em Ah acumulado para plotar em cima da estática
Q_sim_ah = (1 - SOC_total) * bat.Q;
plot(ax_ss, Q_sim_ah, Vbatt_total, 'r-', 'LineWidth', 2.0, 'DisplayName', 'Sua Operação Customizada');
xlabel(ax_ss, 'Capacidade Retirada / Descarga Acumulada (Ah)');
ylabel(ax_ss, 'Tensão de Terminal V_{batt} (V)');
title(ax_ss, ['Trajetória da sua Simulação vs. Curva Estática Padrão — ' bat.name]);
legend(ax_ss, 'Location', 'southwest');
xlim(ax_ss, [0 bat.Q * 1.05]); ylim(ax_ss, [bat.Vnom * 0.6, max([V_ss_ref; Vbatt_total])*1.1]);

fprintf('\n=================================================================\n');
fprintf('  SIMULAÇÃO CONCLUÍDA COM SUCESSO!\n');
fprintf('  Gráficos gerados na janela unificada com abas.\n');
fprintf('=================================================================\n\n');

% =========================================================================
%  FUNÇÃO LOCAL: EQUAÇÃO MATEMÁTICA DO MODELO
% =========================================================================
function V = battery_voltage(bat, it, i_star, Exp, i)
    E0  = bat.E0;    R   = bat.R;    K   = bat.K;    Q   = bat.Q;
    eps_v = 1e-5;    

    if i >= 0
        denom = Q - it;
        if denom < eps_v; denom = eps_v; end
        pol_voltage    = K * (Q / denom) * it;
        pol_resistance = K * (Q / denom) * i_star;
        V = E0 - R*i - pol_voltage - pol_resistance + Exp;
    else
        denom_V = Q - it;
        if denom_V < eps_v; denom_V = eps_v; end
        pol_voltage = K * (Q / denom_V) * it;

        switch bat.type
            case {'lead_acid', 'li_ion'}
                denom_R = it - 0.1*Q;
            case 'nimh_nicd'
                denom_R = abs(it) - 0.1*Q;
            otherwise
                denom_R = it - 0.1*Q;
        end
        if abs(denom_R) < eps_v; denom_R = sign(denom_R) * eps_v; end

        pol_resistance = K * (Q / denom_R) * i_star;
        V = E0 - R*i - pol_resistance - pol_voltage + Exp;
    end
    V = max(0, min(2*E0, V));
end