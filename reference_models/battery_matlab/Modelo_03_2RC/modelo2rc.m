%% =========================================================
%  Replicação: Zhang et al., Appl. Sci. 2017, 7, 1002
%  "Comparative Research on RC Equivalent Circuit Models
%   for Lithium-Ion Batteries of Electric Vehicles"
%
%  Modelos:  1ª ordem RC  e  2ª ordem RC
%  Métodos:  Simulação via Euler explícito (sem Simulink)
%            EKF para estimação de SOC (2ª ordem)
%  Testes:   (1) Constant Current Discharge 1C (2.35 A)
%            (2) Perfil UDDS sintético
%
%  Célula:   18650 | 2350 mAh | 3.7 V nominal
%  =========================================================

clear; clc; close all;
fprintf('=======================================================\n');
fprintf('  Modelos RC de Bateria Li-Ion – Zhang et al. 2017\n');
fprintf('=======================================================\n\n');

%% ----------------------------------------------------------
%  1. OCV vs SOC  (digitalizado da Figura 3 do artigo)
%     Curva monotonicamente crescente 3.45..4.18 V
% -----------------------------------------------------------
SOC_ocv = [0.00, 0.05, 0.10, 0.15,0.20, 0.30, 0.40, 0.50, ...
           0.60, 0.70, 0.80, 0.90, 1.00];
OCV_data = [3.465, 3.5, 3.560, 3.62,3.680, 3.770, 3.780, 3.810, ...
            3.870, 3.920, 4.010, 4.100, 4.180];

% Polinômio grau 6 ajustado à curva
p_ocv = polyfit(SOC_ocv, OCV_data, 6);

get_OCV = @(soc) polyval(p_ocv, min(max(soc, 0), 1));

%% ----------------------------------------------------------
%  2. R0 vs SOC  (digitalizado da Figura 6)
%     Valores em Ω; figura mostra ~50–80 mΩ
% -----------------------------------------------------------
SOC_bp = [0.00, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, ...
          0.60, 0.70, 0.80, 0.90, 1.00];

% mΩ → Ω  (leitura cuidadosa da Figura 6)
R0_data = [0.0660, 0.0730, 0.0705, 0.0670, 0.0560, 0.0630, ...
           0.0600, 0.0610, 0.0590, 0.060, 0.0575, 0.058, 0.056];

get_R0 = @(soc) interp1(SOC_bp, R0_data, min(max(soc,0),1), 'linear');

%% ----------------------------------------------------------
%  3. PARÂMETROS RC  (Tabelas 2 e 3 do artigo)
% -----------------------------------------------------------

% ---- Tabela 2: Modelo 1ª Ordem ----
R1_1o = [0.0382, 0.0263, 0.0226, 0.0244, 0.0237, 0.0203, 0.0204, ...
         0.0211, 0.0267, 0.0242, 0.0272, 0.0235, 0.0240];
C1_1o = [1.4743, 1.6265, 2.2758, 1.9491, 2.3622, 1.7126, 1.7612, ...
         1.9919, 1.4049, 1.6798, 1.4178, 1.5878, 1.9287] * 1e3;

% ---- Tabela 3: Modelo 2ª Ordem ----
R1_2o = [0.0334, 0.0051, 0.0041, 0.0043, 0.0040, 0.0072, 0.0045, ...
         0.0025, 0.0047, 0.0052, 0.0047, 0.0049, 0.0043];
C1_2o = [0.0442, 1.0871, 1.2881, 1.8020, 1.3375, 2.6151, 3.4769, ...
         1.1805, 1.5090, 1.2954, 0.9950, 1.0819, 2.5064] * 1e3;
R2_2o = [0.0169, 0.0091, 0.0085, 0.0079, 0.0091, 0.0023, 0.0048, ...
         0.0086, 0.0087, 0.0102, 0.0102, 0.0433, 0.0070];
C2_2o = [0.3044, 0.6801, 0.7804, 1.0314, 0.7719, 3.5084, 1.4490, ...
         0.5300, 0.6500, 0.5897, 0.4634, 0.8196, 1.3357] * 1e4;

tau1_1o = R1_1o .* C1_1o;
tau1_2o = R1_2o .* C1_2o;
tau2_2o = R2_2o .* C2_2o;

% Lookup functions
get_R1_1 = @(s) interp1(SOC_bp, R1_1o, clip(s), 'linear');
get_C1_1 = @(s) interp1(SOC_bp, C1_1o, clip(s), 'linear');
get_R1_2 = @(s) interp1(SOC_bp, R1_2o, clip(s), 'linear');
get_C1_2 = @(s) interp1(SOC_bp, C1_2o, clip(s), 'linear');
get_R2_2 = @(s) interp1(SOC_bp, R2_2o, clip(s), 'linear');
get_C2_2 = @(s) interp1(SOC_bp, C2_2o, clip(s), 'linear');

%% ----------------------------------------------------------
%  4. IMPRESSÃO DAS TABELAS
% -----------------------------------------------------------
fprintf('-------------------------------------------------------\n');
fprintf(' TABELA 2 – Parâmetros Modelo 1ª Ordem RC\n');
fprintf('-------------------------------------------------------\n');
fprintf('  SOC  |  tau1 (s) |  R1 (mΩ) |  C1 (kF)\n');
fprintf(' ------|-----------|----------|----------\n');
for i = 1:length(SOC_bp)
    fprintf('  %.2f |   %7.4f |  %7.3f | %8.4f\n', ...
        SOC_bp(i), tau1_1o(i), R1_1o(i)*1000, C1_1o(i)/1e3);
end

fprintf('\n-------------------------------------------------------\n');
fprintf(' TABELA 3 – Parâmetros Modelo 2ª Ordem RC\n');
fprintf('-------------------------------------------------------\n');
fprintf('  SOC  | tau1(s) | R1(mΩ) |  C1(kF) | tau2(s) | R2(mΩ) | C2(×10kF)\n');
fprintf(' ------|---------|--------|---------|---------|--------|----------\n');
for i = 1:length(SOC_bp)
    fprintf('  %.2f | %7.4f | %6.3f | %7.4f | %7.4f | %6.3f | %8.4f\n', ...
        SOC_bp(i), tau1_2o(i), R1_2o(i)*1000, C1_2o(i)/1e3, ...
        tau2_2o(i), R2_2o(i)*1000, C2_2o(i)/1e4);
end
fprintf('\n');

%% ----------------------------------------------------------
%  5. SIMULAÇÃO: DESCARGA CC 1C
% -----------------------------------------------------------
fprintf('=======================================================\n');
fprintf(' TESTE 1: Descarga CC 1C (I = 2.35 A)\n');
fprintf('=======================================================\n');

C_nom = 2.350;      % Ah
Cn_As = C_nom * 3600;  % A·s
I_cc  = 2.350;      % A  (1C de descarga, positivo)
V_cut = 2.700;      % V
dt    = 1;          % s

% Tempo máximo conservador (bateria dura ~1h = 3600 s)
t_max = 5000;
t_vec = (0:dt:t_max)';
N     = length(t_vec);

% Pré-alocação
SOC1 = zeros(N,1);  Ut1 = zeros(N,1);
SOC2 = zeros(N,1);  Ut2 = zeros(N,1);
Vc1_a = 0;                  % estado capacitor – 1ª ordem
Vc1_b = 0;  Vc2_b = 0;     % estados capacitores – 2ª ordem

SOC1(1) = 1.0;  SOC2(1) = 1.0;
Ut1(1)  = get_OCV(1.0) - I_cc*get_R0(1.0);   % tensão inicial com queda ôhmica
Ut2(1)  = Ut1(1);

idx1 = N;  idx2 = N;  % índices de corte

for k = 1:N-1
    %--- 1ª Ordem ---
    s1 = SOC1(k);
    R0 = get_R0(s1);  R1 = get_R1_1(s1);  C1 = get_C1_1(s1);
    % Dinâmica do capacitor (Euler): dVc/dt = I/C1 - Vc/(R1*C1)
    Vc1_a = Vc1_a + dt*(I_cc/C1 - Vc1_a/(R1*C1));
    % SOC por integração coulombica
    SOC1(k+1) = max(s1 - (I_cc*dt)/Cn_As, 0);
    % Tensão terminal
    Ut1(k+1) = get_OCV(SOC1(k+1)) - I_cc*R0 - Vc1_a;
    if Ut1(k+1) <= V_cut && idx1 == N, idx1 = k+1; end

    %--- 2ª Ordem ---
    s2 = SOC2(k);
    R0 = get_R0(s2);
    R1 = get_R1_2(s2);  C1 = get_C1_2(s2);
    R2 = get_R2_2(s2);  C2 = get_C2_2(s2);
    Vc1_b = Vc1_b + dt*(I_cc/C1 - Vc1_b/(R1*C1));
    Vc2_b = Vc2_b + dt*(I_cc/C2 - Vc2_b/(R2*C2));
    SOC2(k+1) = max(s2 - (I_cc*dt)/Cn_As, 0);
    Ut2(k+1) = get_OCV(SOC2(k+1)) - I_cc*R0 - Vc1_b - Vc2_b;
    if Ut2(k+1) <= V_cut && idx2 == N, idx2 = k+1; end
end

% Trunca nas tensões de corte
t1_cc  = t_vec(1:idx1);  V1_cc = Ut1(1:idx1);
t2_cc  = t_vec(1:idx2);  V2_cc = Ut2(1:idx2);

% Erro entre modelos (proxy do erro real – artigo: max 1.65% / 1.22%)
n_min = min(idx1, idx2);
err_cc = V1_cc(1:n_min) - V2_cc(1:n_min);
rel_err1 = max(abs(err_cc)) / mean(V2_cc(1:n_min)) * 100;

fprintf(' 1ª Ordem: corte em %d s  |  V_final = %.4f V\n', t1_cc(end), V1_cc(end));
fprintf(' 2ª Ordem: corte em %d s  |  V_final = %.4f V\n', t2_cc(end), V2_cc(end));
fprintf(' Diff máx entre modelos: %.4f V  (%.2f %%)\n\n', max(abs(err_cc)), rel_err1);

%% ----------------------------------------------------------
%  6. SIMULAÇÃO: PERFIL UDDS SINTÉTICO
%     Corrente extraída de perfil HEV-UDDS padrão (sintético)
%     Características: bidirecional, picos ±2C, ~4500 s total
% -----------------------------------------------------------
fprintf('=======================================================\n');
fprintf(' TESTE 2: Ciclo UDDS Sintético\n');
fprintf('=======================================================\n');

dt_u = 1;
% Ciclo base de ~1372 s com padrão urbano realista
% Positivo = descarga | Negativo = carga regenerativa
seg = [...
%  t_ini  t_fim   I(A)
    0,     5,     0.000;   % parada
    5,     35,    2.820;   % aceleração (1.2C)
    35,    90,    1.645;   % velocidade cruzeiro (0.7C)
    90,    115,  -0.940;   % frenagem regen
    115,   135,   0.000;
    135,   175,   3.525;   % aceleração forte (1.5C)
    175,   260,   1.880;   % cruzeiro
    260,   295,  -1.175;
    295,   325,   0.000;
    325,   380,   4.700;   % pico aceleração (2C)
    380,   460,   2.350;   % cruzeiro (1C)
    460,   500,  -1.410;
    500,   540,   0.000;
    540,   600,   3.055;   % (1.3C)
    600,   680,   1.645;
    680,   715,  -0.940;
    715,   750,   0.000;
    750,   810,   2.350;
    810,   880,   1.410;
    880,   910,  -0.705;
    910,   950,   0.000;
    950,  1010,   3.760;
   1010,  1090,   2.115;
   1090,  1130,  -1.175;
   1130,  1185,   0.000;
   1185,  1250,   2.350;
   1250,  1320,   1.175;
   1320,  1360,  -0.940;
   1360,  1372,   0.000];

t_seg = (0:dt_u:1372)';
I_seg = zeros(length(t_seg), 1);
for s = 1:size(seg,1)
    mask = t_seg >= seg(s,1) & t_seg < seg(s,2);
    I_seg(mask) = seg(s,3);
end
% Suavização leve (simula inércia mecânica)
I_seg = filtfilt(ones(5,1)/5, 1, I_seg);

% Repete e trunca em 4500 s
n_rep  = ceil(4500 / length(t_seg)) + 1;
I_udds = repmat(I_seg, n_rep, 1);
t_udds = (0:dt_u:length(I_udds)-1)';
mk     = t_udds <= 4500;
t_udds = t_udds(mk);
I_udds = I_udds(mk);
Nu     = length(t_udds);

fprintf(' Perfil UDDS: %d amostras | I_max=%.3fA | I_min=%.3fA\n', ...
    Nu, max(I_udds), min(I_udds));

% Simulação UDDS
SOCu1 = zeros(Nu,1);  Utu1 = zeros(Nu,1);
SOCu2 = zeros(Nu,1);  Utu2 = zeros(Nu,1);
SOCu1(1) = 1.0;  SOCu2(1) = 1.0;
Utu1(1)  = get_OCV(1.0);
Utu2(1)  = get_OCV(1.0);
Vc1_u1 = 0;
Vc1_u2 = 0;  Vc2_u2 = 0;

for k = 1:Nu-1
    Ik = I_udds(k);

    % 1ª Ordem
    s = SOCu1(k);
    R0 = get_R0(s);  R1 = get_R1_1(s);  C1 = get_C1_1(s);
    Vc1_u1    = Vc1_u1 + dt_u*(Ik/C1 - Vc1_u1/(R1*C1));
    SOCu1(k+1)= max(min(s - (Ik*dt_u)/Cn_As, 1.0), 0);
    Utu1(k+1) = get_OCV(SOCu1(k+1)) - Ik*R0 - Vc1_u1;

    % 2ª Ordem
    s = SOCu2(k);
    R0 = get_R0(s);
    R1 = get_R1_2(s);  C1 = get_C1_2(s);
    R2 = get_R2_2(s);  C2 = get_C2_2(s);
    Vc1_u2    = Vc1_u2 + dt_u*(Ik/C1 - Vc1_u2/(R1*C1));
    Vc2_u2    = Vc2_u2 + dt_u*(Ik/C2 - Vc2_u2/(R2*C2));
    SOCu2(k+1)= max(min(s - (Ik*dt_u)/Cn_As, 1.0), 0);
    Utu2(k+1) = get_OCV(SOCu2(k+1)) - Ik*R0 - Vc1_u2 - Vc2_u2;
end

err_udds = Utu1 - Utu2;
fprintf(' Diff máx (1ª–2ª): %.4f V | RMS: %.4f V\n\n', ...
    max(abs(err_udds)), rms(err_udds));

%% ----------------------------------------------------------
%  7. EKF – Estimação de SOC  (Modelo 2ª Ordem, ciclo UDDS)
%     Estado: x = [SOC; Vc1; Vc2]
% -----------------------------------------------------------
fprintf('=======================================================\n');
fprintf(' EKF – Estimação de SOC (2ª Ordem RC, UDDS)\n');
fprintf('=======================================================\n');

Q_ekf = diag([1e-6, 5e-5, 5e-5]);
R_ekf = 4e-4;
P_ekf = diag([0.010, 5e-4, 5e-4]);

SOC_ekf = zeros(Nu,1);
% Erro inicial proposital: SOC_0 = 0.80 (real = 1.0)
x_est = [0.80; 0; 0];
SOC_ekf(1) = x_est(1);

for k = 1:Nu-1
    Ik = I_udds(k);
    sk = min(max(x_est(1), 0), 1);

    R0 = get_R0(sk);
    R1 = get_R1_2(sk);  C1 = get_C1_2(sk);
    R2 = get_R2_2(sk);  C2 = get_C2_2(sk);

    a1 = 1 - dt_u/(R1*C1);
    a2 = 1 - dt_u/(R2*C2);

    % Predição de estado
    x_p = [x_est(1) - (dt_u/Cn_As)*Ik;
            a1*x_est(2) + (dt_u/C1)*Ik;
            a2*x_est(3) + (dt_u/C2)*Ik];
    x_p(1) = min(max(x_p(1), 0), 1);

    % Jacobiana F
    F = [1, 0, 0; 0, a1, 0; 0, 0, a2];
    P_p = F*P_ekf*F' + Q_ekf;

    % Gradiente dOCV/dSOC (diferenças finitas)
    h = 1e-4;
    sp = min(max(x_p(1), h), 1-h);
    dOCV = (get_OCV(sp+h) - get_OCV(sp-h)) / (2*h);

    % Saída estimada
    y_hat = get_OCV(sp) - R0*Ik - x_p(2) - x_p(3);

    % Jacobiana H
    H = [dOCV, -1, -1];
    S_k = H*P_p*H' + R_ekf;
    K_k = P_p*H' / S_k;

    % Medição = tensão modelo 2ª ordem + ruído
    y_meas = Utu2(k+1) + sqrt(R_ekf)*randn();

    % Atualização
    x_est = x_p + K_k*(y_meas - y_hat);
    x_est(1) = min(max(x_est(1), 0), 1);
    P_ekf = (eye(3) - K_k*H)*P_p*(eye(3) - K_k*H)' + K_k*R_ekf*K_k';

    SOC_ekf(k+1) = x_est(1);
end

err_soc = SOCu2 - SOC_ekf;
fprintf(' SOC_0 real=1.000 | SOC_0 EKF=0.800\n');
fprintf(' SOC final real: %.4f | EKF: %.4f\n', SOCu2(end), SOC_ekf(end));
fprintf(' Erro SOC – Máx: %.4f  |  RMS: %.6f\n\n', max(abs(err_soc)), rms(err_soc));

%% ----------------------------------------------------------
%  8. TABELA RESUMO DE ERROS
% -----------------------------------------------------------
fprintf('=======================================================\n');
fprintf(' TABELA RESUMO – Erros de Modelagem (valores do artigo)\n');
fprintf('=======================================================\n');
fprintf('\n Condição: CC 1C\n');
fprintf(' %-28s | Err Máx Abs (V) | Err Máx Rel | RMS (V)\n', 'Modelo');
fprintf(' %s\n', repmat('-',1,68));
fprintf(' %-28s | %15s | %11s | %7s\n', '1ª Ordem RC', '0.0610', '1.65%', '0.0221');
fprintf(' %-28s | %15s | %11s | %7s\n', '2ª Ordem RC', '0.0452', '1.22%', '0.0156');
fprintf('\n Condição: UDDS Cycle\n');
fprintf(' %-28s | Err Máx Abs (V) | Err Máx Rel | RMS (V)\n', 'Modelo');
fprintf(' %s\n', repmat('-',1,68));
fprintf(' %-28s | %15s | %11s | %7s\n', '1ª Ordem RC', '0.0695', '1.88%', '0.0298');
fprintf(' %-28s | %15s | %11s | %7s\n', '2ª Ordem RC', '0.0628', '1.69%', '0.0282');

fprintf('\n EKF – SOC Estimation (2ª Ordem RC, UDDS):\n');
fprintf('   Max |error_SOC| = %.4f  |  RMS = %.6f\n\n', max(abs(err_soc)), rms(err_soc));

%% ----------------------------------------------------------
%  9. FIGURAS
% -----------------------------------------------------------

% Fig 1 – OCV vs SOC
figure('Name','OCV vs SOC','Color','w');
soc_f = linspace(0,1,300);
plot(SOC_ocv, OCV_data, 'bx', 'MarkerSize', 9, 'LineWidth', 2); hold on;
plot(soc_f, polyval(p_ocv, soc_f), 'b-', 'LineWidth', 1.5);
xlabel('SOC','FontSize',12); ylabel('OCV (V)','FontSize',12);
title('OCV vs SOC – Curva Estacionária (Fig. 3 do artigo)','FontSize',13);
legend('Pontos medidos','Ajuste polinomial grau 6','Location','northwest');
xlim([0 1]); ylim([3.3 4.3]); grid on; set(gca,'FontSize',11);

% Fig 2 – R0 vs SOC
figure('Name','R0 vs SOC','Color','w');

% Cambiado de 'bar' a 'plot' para gráfico de línea con marcadores circulares
plot(SOC_bp, R0_data*1000, '-o', ...
     'Color', [0.25 0.50 0.80], ...
     'LineWidth', 2, ...
     'MarkerSize', 6, ...
     'MarkerFaceColor', [0.25 0.50 0.80]);

xlabel('SOC','FontSize',12); ylabel('R0 (mΩ)','FontSize',12);
title('Resistência Ôhmica R0 vs SOC (Fig. 6 do artigo)','FontSize',13);
xlim([-0.05 1.05]); ylim([40 90]); grid on; set(gca,'FontSize',11);

% Fig 3 – Parâmetros 1ª Ordem
figure('Name','Parâmetros 1ª Ordem','Color','w');
subplot(3,1,1);
plot(SOC_bp, R1_1o*1000, 'ro-', 'LineWidth',2,'MarkerSize',7);
ylabel('R1 (mΩ)'); title('R1 vs SOC – 1ª Ordem'); grid on; xlim([0 1]);
subplot(3,1,2);
plot(SOC_bp, C1_1o/1e3, 'bs-', 'LineWidth',2,'MarkerSize',7);
ylabel('C1 (kF)'); title('C1 vs SOC – 1ª Ordem'); grid on; xlim([0 1]);
subplot(3,1,3);
plot(SOC_bp, tau1_1o, 'k^-', 'LineWidth',2,'MarkerSize',7);
xlabel('SOC'); ylabel('τ1 (s)'); title('τ1 vs SOC – 1ª Ordem'); grid on; xlim([0 1]);
sgtitle('Parâmetros Modelo 1ª Ordem RC','FontSize',13,'FontWeight','bold');

% Fig 4 – Parâmetros 2ª Ordem
figure('Name','Parâmetros 2ª Ordem','Color','w');
subplot(2,2,1);
plot(SOC_bp,R1_2o*1000,'r^-','LineWidth',2,'MarkerSize',7); hold on;
plot(SOC_bp,R2_2o*1000,'bs-','LineWidth',2,'MarkerSize',7);
ylabel('R (mΩ)'); title('R1, R2 vs SOC'); legend('R1','R2'); grid on; xlim([0 1]);
subplot(2,2,2);
plot(SOC_bp,C1_2o/1e3,'r^-','LineWidth',2,'MarkerSize',7); hold on;
plot(SOC_bp,C2_2o/1e4,'bs-','LineWidth',2,'MarkerSize',7);
ylabel('C (kF / ×10 kF)'); title('C1 (kF), C2 (×10kF) vs SOC');
legend('C1','C2'); grid on; xlim([0 1]);
subplot(2,2,3);
plot(SOC_bp,tau1_2o,'r^-','LineWidth',2,'MarkerSize',7);
xlabel('SOC'); ylabel('τ1 (s)'); title('τ1 vs SOC'); grid on; xlim([0 1]);
subplot(2,2,4);
plot(SOC_bp,tau2_2o,'bs-','LineWidth',2,'MarkerSize',7);
xlabel('SOC'); ylabel('τ2 (s)'); title('τ2 vs SOC'); grid on; xlim([0 1]);
sgtitle('Parâmetros Modelo 2ª Ordem RC','FontSize',13,'FontWeight','bold');

% Fig 5 – Tensão CC 1C (replica Fig 11 e 12 do artigo)
figure('Name','CC 1C – Tensão Terminal','Color','w');
plot(t1_cc, V1_cc, 'r--', 'LineWidth', 2, 'DisplayName', 'Modelo 1ª Ordem'); hold on;
plot(t2_cc, V2_cc, 'b-',  'LineWidth', 1.5, 'DisplayName', 'Modelo 2ª Ordem');
xlabel('Tempo (s)','FontSize',12); ylabel('Tensão (V)','FontSize',12);
title('Descarga CC 1C – Tensão Terminal (replica Figs 11–12)','FontSize',13);
legend('Location','southwest','FontSize',11); grid on;
xlim([0 4500]); ylim([2.7 4.3]); set(gca,'FontSize',11);

% Fig 6 – Erro CC 1C  (replica Fig 13 do artigo)
figure('Name','CC 1C – Erro','Color','w');
t_err = t_vec(1:n_min);
plot(t_err, err_cc, 'r--', 'LineWidth', 1.5, 'DisplayName', '1ª ordem RC'); hold on;
% 2ª ordem erro em relação a si mesmo = 0 (referência)
yline(0,'b-','LineWidth',1,'DisplayName','2ª ordem RC');
yline(0.06,'k:'); yline(-0.06,'k:');
xlabel('Tempo (s)','FontSize',12); ylabel('Erro de saída (V)','FontSize',12);
title('Erros de Saída – CC 1C (replica Fig. 13)','FontSize',13);
legend('Location','northeast','FontSize',11); grid on;
ylim([-0.08 0.08]); xlim([0 4500]); set(gca,'FontSize',11);

% Fig 7 – Perfil de corrente UDDS
figure('Name','Perfil Corrente UDDS','Color','w');
plot(t_udds, I_udds, 'k-', 'LineWidth', 0.8);
yline(0,'b--','LineWidth',1);
xlabel('Tempo (s)','FontSize',12); ylabel('Corrente (A)','FontSize',12);
title('Perfil de Corrente UDDS Sintético','FontSize',13);
grid on; set(gca,'FontSize',11);

% Fig 8 – Tensão UDDS (replica Figs 14–15)
figure('Name','UDDS – Tensão Terminal','Color','w');
plot(t_udds, Utu1, 'r--', 'LineWidth', 1.2, 'DisplayName', 'Modelo 1ª Ordem'); hold on;
plot(t_udds, Utu2, 'b-',  'LineWidth', 1.2, 'DisplayName', 'Modelo 2ª Ordem');
xlabel('Tempo (s)','FontSize',12); ylabel('Tensão (V)','FontSize',12);
title('UDDS – Tensão Terminal (replica Figs 14–15)','FontSize',13);
legend('Location','southwest','FontSize',11); grid on;
xlim([0 4500]); set(gca,'FontSize',11);

% Fig 9 – Erro UDDS (replica Fig 16)
figure('Name','UDDS – Erro','Color','w');
plot(t_udds, Utu1-Utu2, 'r--', 'LineWidth', 1.2, 'DisplayName', '1ª ordem RC'); hold on;
yline(0,'b-','LineWidth',1,'DisplayName','2ª ordem RC');
yline(0.06,'k:'); yline(-0.06,'k:');
xlabel('Tempo (s)','FontSize',12); ylabel('Erro de saída (V)','FontSize',12);
title('Erros de Saída – UDDS (replica Fig. 16)','FontSize',13);
legend('Location','northeast','FontSize',11); grid on;
ylim([-0.08 0.08]); xlim([0 4500]); set(gca,'FontSize',11);

% Fig 10 – EKF SOC
figure('Name','EKF – SOC Estimation','Color','w');
plot(t_udds, SOCu2*100, 'b-', 'LineWidth',2, 'DisplayName','SOC Real'); hold on;
plot(t_udds, SOC_ekf*100,'r--','LineWidth',1.5,'DisplayName','SOC EKF (SOC_0=80%)');
xlabel('Tempo (s)','FontSize',12); ylabel('SOC (%)','FontSize',12);
title('EKF – Estimação de SOC (Modelo 2ª Ordem RC)','FontSize',13);
legend('Location','southwest','FontSize',11); grid on; set(gca,'FontSize',11);

% Fig 11 – EKF Erro SOC
figure('Name','EKF – Erro SOC','Color','w');
plot(t_udds, err_soc*100, 'r-', 'LineWidth',1.5);
yline(0,'k--'); yline(1,'k:'); yline(-1,'k:');
xlabel('Tempo (s)','FontSize',12); ylabel('Erro SOC (%)','FontSize',12);
title('EKF – Erro de Estimação de SOC','FontSize',13);
grid on; set(gca,'FontSize',11);

fprintf('=======================================================\n');
fprintf('  Concluído. 11 figuras geradas.\n');
fprintf('=======================================================\n');

%% Função auxiliar
function y = clip(x)
    y = min(max(x, 0), 1);
end