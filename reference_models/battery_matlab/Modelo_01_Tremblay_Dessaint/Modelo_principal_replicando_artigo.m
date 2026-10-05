% =========================================================================
%  BATTERY DYNAMIC MODEL — Tremblay & Dessaint (2009)
% =========================================================================

clear; clc; close all;

% =========================================================================
%  SECTION 1 — BATTERY PARAMETERS  
% =========================================================================
%
%  Each battery is stored as a struct with the following fields:
%
%   name  : descriptive label
%   type  : chemistry identifier used in the voltage equations
%   E0    : battery constant voltage [V]  — open-circuit voltage offset
%   R     : internal resistance [Ohm]    — causes immediate voltage drop
%   K     : polarisation constant [V/Ah] or [Ohm] — models SOC-dependent
%             voltage behaviour (rises as battery depletes)
%   A     : exponential zone amplitude [V] — height of the initial
%             steep voltage drop at the beginning of discharge
%   B     : exponential zone time constant inverse [(Ah)^-1] — how
%             quickly the exponential zone ends
%   Q     : maximum battery capacity [Ah]
%   Vnom  : nominal voltage [V] — used for axis scaling only
%   SOC0  : initial state of charge (1.0 = 100% charged)

batteries = struct();

% --- Battery 1: Lead-Acid, 12V 7.2Ah ---
batteries(1).name  = 'Lead-Acid (12V, 7.2Ah)';
batteries(1).type  = 'lead_acid';   % uses hysteresis Exp model
batteries(1).E0    = 12.4659;  % V
batteries(1).R     = 0.04;     % Ohm
batteries(1).K     = 0.047;    % V/Ah (polarisation constant)
batteries(1).A     = 0.83;     % V
batteries(1).B     = 125;      % (Ah)^-1
batteries(1).Q     = 7.2;      % Ah
batteries(1).Vnom  = 12.0;     % V
batteries(1).SOC0  = 1.0;

% --- Battery 2: NiCd, 1.2V 2.3Ah ---
batteries(2).name  = 'NiCd (1.2V, 2.3Ah)';
batteries(2).type  = 'nimh_nicd';  % uses hysteresis Exp model
batteries(2).E0    = 1.2705;
batteries(2).R     = 0.003;
batteries(2).K     = 0.0037;
batteries(2).A     = 0.127;
batteries(2).B     = 4.98;
batteries(2).Q     = 2.3;
batteries(2).Vnom  = 1.2;
batteries(2).SOC0  = 1.0;

% --- Battery 3: Li-Ion, 3.3V 2.3Ah ---
batteries(3).name  = 'Li-Ion (3.3V, 2.3Ah)';
batteries(3).type  = 'li_ion';     % no hysteresis; Exp = A*exp(-B*it)
batteries(3).E0    = 3.366;
batteries(3).R     = 0.01;
batteries(3).K     = 0.0076;
batteries(3).A     = 0.26422;
batteries(3).B     = 26.5487;
batteries(3).Q     = 2.3;
batteries(3).Vnom  = 3.3;
batteries(3).SOC0  = 1.0;

% --- Battery 4: NiMH, 1.2V 6.5Ah ---
batteries(4).name  = 'NiMH (1.2V, 6.5Ah)';
batteries(4).type  = 'nimh_nicd';  % uses hysteresis Exp model
batteries(4).E0    = 1.2816;
batteries(4).R     = 0.002;
batteries(4).K     = 0.0014;
batteries(4).A     = 0.111;
batteries(4).B     = 2.3077;
batteries(4).Q     = 6.5;
batteries(4).Vnom  = 1.2;
batteries(4).SOC0  = 1.0;

% =========================================================================
%  SECTION 2 — SIMULATION SETTINGS
% =========================================================================

dt  = 1;    % integration time step [seconds]
            % Small enough to capture pulse dynamics accurately

tau = 30;   % Time constant of the filtered current i* [seconds]
            % This is NOT given in battery datasheets; it was determined
            % experimentally by the authors for all four battery types.
            % It models the slow dynamic voltage response to current steps.
            % The filter equation is:  tau * d(i*)/dt + i* = i(t)
            % Discretised (Euler forward): i*(k) = i*(k-1) + dt/tau*(i(k)-i*(k-1))

% =========================================================================
%  SECTION 3 — COMMAND WINDOW: HEADER AND ENTRY DATA
% =========================================================================

fprintf('\n');
fprintf('=================================================================\n');
fprintf('  BATTERY DYNAMIC MODEL — Tremblay & Dessaint (2009)\n');
fprintf('  EVS24 — Stavanger, Norway\n');
fprintf('=================================================================\n\n');

fprintf('--- SIMULATION SETTINGS ---\n');
fprintf('  Time step   dt  = %d s\n', dt);
fprintf('  Filter constant tau = %d s  (experimentally determined, same\n', tau);
fprintf('                              for all 4 battery types)\n\n');

fprintf('--- ENTRY DATA: BATTERY PARAMETERS (Table 1 of the paper) ---\n');
fprintf('%-10s %12s %12s %12s %12s\n', 'Parameter', 'Lead-Acid', 'NiCd', 'Li-Ion', 'NiMH');
fprintf('%s\n', repmat('-',1,62));
fields  = {'E0','R','K','A','B','Q'};
units   = {'V','Ohm','V/Ah or Ohm','V','(Ah)^-1','Ah'};
for f = 1:length(fields)
    fprintf('%-10s', [fields{f} ' [' units{f} ']']);
    for b = 1:4
        fprintf(' %12.4f', batteries(b).(fields{f}));
    end
    fprintf('\n');
end
fprintf('%s\n\n', repmat('-',1,62));

% =========================================================================
%  SECTION 4 — COMMAND WINDOW: MODEL EQUATIONS
% =========================================================================

fprintf('--- GOVERNING EQUATIONS (from the paper) ---\n\n');

fprintf('  DISCHARGE (i > 0):\n');
fprintf('    Vbatt = E0 - R*i - K*(Q/(Q-it))*it       [polarisation voltage]\n');
fprintf('                     - K*(Q/(Q-it))*i* [polarisation resistance]\n');
fprintf('                     + Exp(t)                 [exponential zone]\n\n');

fprintf('  CHARGE (i < 0) — Lead-Acid & Li-Ion:\n');
fprintf('    Vbatt = E0 - R*i - K*(Q/(it-0.1Q))*i* [modified pol. resistance]\n');
fprintf('                     - K*(Q/(Q-it))*it        [polarisation voltage]\n');
fprintf('                     + Exp(t)\n\n');

fprintf('  CHARGE (i < 0) — NiMH & NiCd:\n');
fprintf('    Vbatt = E0 - R*i - K*(Q/(|it|-0.1Q))*i* [absolute value denom.]\n');
fprintf('                     - K*(Q/(Q-it))*it\n');
fprintf('                     + Exp(t)\n\n');

fprintf('  FILTERED CURRENT (first-order low-pass filter, tau = 30 s):\n');
fprintf('    tau * d(i*)/dt + i* = i(t)\n');
fprintf('    Discrete: i*(k) = i*(k-1) + (dt/tau)*(i(k) - i*(k-1))\n\n');

fprintf('  EXPONENTIAL ZONE:\n');
fprintf('    Li-Ion  : Exp(t) = A * exp(-B * it)         [no hysteresis]\n');
fprintf('    Others  : dExp/dt = B*|i|*(-Exp + A*u(t))   [hysteresis, eq.2]\n');
fprintf('              u(t) = 1 during CHARGE, u(t) = 0 during DISCHARGE\n\n');

fprintf('  STATE OF CHARGE:\n');
fprintf('    SOC(t) = 1 - it/Q      [it = integral of i dt, in Ah]\n\n');

fprintf('  VARIABLE LEGEND:\n');
fprintf('    E0  = battery constant voltage (V)\n');
fprintf('    R   = internal resistance (Ohm)\n');
fprintf('    K   = polarisation constant (V/Ah)\n');
fprintf('    Q   = battery capacity (Ah)\n');
fprintf('    it  = accumulated charge withdrawn (Ah)  [0=full, Q=empty]\n');
fprintf('    i   = instantaneous battery current (A)\n');
fprintf('    i* = filtered current (A)  — slow dynamic state variable\n');
fprintf('    A   = exponential zone amplitude (V)\n');
fprintf('    B   = exponential zone time constant inverse (Ah^-1)\n');
fprintf('    Exp = exponential zone voltage (V)\n\n');

% =========================================================================
%  CRIANDO A JANELA PRINCIPAL COM ABAS (TABS)
% =========================================================================
main_fig = figure('Name', 'Resultados: Modelo de Bateria (Tremblay & Dessaint)', ...
                  'NumberTitle', 'off', ...
                  'Units', 'normalized', 'Position', [0.05, 0.05, 0.9, 0.85]);
tgroup = uitabgroup('Parent', main_fig);


% =========================================================================
%  SECTION 5 — MAIN SIMULATION LOOP: ALL FOUR BATTERIES
% =========================================================================
%
%  For each battery we run TWO separate simulations:
%    (a) A DISCHARGE-only pulse sequence (Fig. 5a–8a style)
%    (b) A CHARGE-only pulse sequence, starting from a depleted state
%        (Fig. 5b–8b style)
%  Then we plot them in separate figures so the reader can compare
%  charge vs. discharge behaviour clearly.

for b = 1:4
    bat = batteries(b);

    % ------------------------------------------------------------------
    %  CURRENT PROFILE DESIGN
    %  The paper uses a pulsed current profile measured with a
    %  "current-controlled load" and "chart recorder". We reproduce
    %  a representative pulsed waveform for each chemistry.
    %  Pulse amplitudes are chosen as multiples of the 1C rate (i.e.,
    %  the current that would discharge the battery in 1 hour = Q [A]).
    % ------------------------------------------------------------------

    I_1C = bat.Q;   % 1C discharge current [A]

    switch bat.type
        case 'lead_acid'
            % Paper Fig. 8: pulses around 20-60 A for a 7.2 Ah battery
            % We use 0.5C for a clean educational representation
            I_dis    = 0.5 * I_1C;   % discharge pulse amplitude
            I_chg    = 0.5 * I_1C;   % charge pulse amplitude (used in charge sim)
            T_dis    = 7000;          % total discharge simulation time [s]
            T_chg    = 6000;          % total charge simulation time [s]
            t_on     = 400;           % pulse ON duration [s]
            t_off    = 200;           % pulse OFF (rest) duration [s]

        case 'li_ion'
            % Paper Fig. 6 & 9: pulses of ~5-10 A for a 2.3 Ah battery
            I_dis    = 2 * I_1C;
            I_chg    = 1 * I_1C;
            T_dis    = 2500;
            T_chg    = 6500;
            t_on     = 200;
            t_off    = 100;

        otherwise   % NiMH and NiCd
            % Paper Fig. 5 & 7: pulses of 2-4 A for 2.3/6.5 Ah batteries
            I_dis    = 0.5 * I_1C;
            I_chg    = 0.5 * I_1C;
            T_dis    = 9000;
            T_chg    = 5000;
            t_on     = 500;
            t_off    = 200;
    end

    % ------------------------------------------------------------------
    %  BUILD CURRENT VECTORS
    %  Discharge: positive pulses alternating with rest periods
    %  Charge:    negative pulses alternating with rest periods
    % ------------------------------------------------------------------
    t_dis = (0:dt:T_dis)';
    N_dis = length(t_dis);
    i_dis_vec = zeros(N_dis, 1);
    period = t_on + t_off;
    for k = 1:N_dis
        phase = mod(t_dis(k), period);
        if phase < t_on
            i_dis_vec(k) = I_dis;   % positive = discharge
        end
        % else: rest (i = 0)
    end

    t_chg = (0:dt:T_chg)';
    N_chg = length(t_chg);
    i_chg_vec = zeros(N_chg, 1);
    for k = 1:N_chg
        phase = mod(t_chg(k), period);
        if phase < t_on
            i_chg_vec(k) = -I_chg;  % negative = charge
        end
    end

    % ------------------------------------------------------------------
    %  (a) DISCHARGE SIMULATION
    %  Start from it=0 (fully charged), discharge until SOC ~ 5%
    % ------------------------------------------------------------------
    Vbatt_d  = zeros(N_dis, 1);
    SOC_d    = zeros(N_dis, 1);
    Exp_d    = zeros(N_dis, 1);
    istar_d  = zeros(N_dis, 1);

    it_d        = 0;                % Ah withdrawn so far (0 = fully charged)
    Exp_d(1)    = bat.A;            % at full charge, exponential zone is at max
    istar_d(1)  = 0;                % filter starts at rest
    SOC_d(1)    = 1.0;
    Vbatt_d(1)  = battery_voltage(bat, it_d, 0, Exp_d(1), 0);

    for k = 2:N_dis
        i_k = i_dis_vec(k);

        % Update filtered current i* — first-order Euler discretisation
        % of:  tau * d(i*)/dt + i* = i
        istar_d(k) = istar_d(k-1) + (dt/tau) * (i_k - istar_d(k-1));

        % Update exponential zone voltage
        if strcmp(bat.type, 'li_ion')
            % Li-Ion: no hysteresis, purely a function of it
            Exp_d(k) = bat.A * exp(-bat.B * it_d);
        else
            % Lead-Acid, NiMH, NiCd: dynamic hysteresis equation (Eq. 2)
            % u(t) = 0 during discharge → equation drives Exp toward 0
            dExp     = bat.B * abs(i_k) * (-Exp_d(k-1) + bat.A * 0);
            Exp_d(k) = Exp_d(k-1) + dExp * dt;
            Exp_d(k) = max(0, min(bat.A, Exp_d(k)));  % physical clamp
        end

        % Compute battery terminal voltage using the discharge equation
        Vbatt_d(k) = battery_voltage(bat, it_d, istar_d(k), Exp_d(k), i_k);

        % Coulomb counting: integrate current to get charge withdrawn
        it_d   = it_d + i_k * (dt/3600);   % dt/3600 converts seconds to hours
        it_d   = max(0, min(bat.Q, it_d)); % clamp: can't exceed capacity

        % State of charge: 1 when full, 0 when empty
        SOC_d(k) = max(0, 1 - it_d / bat.Q);

        % Stop early if battery is nearly empty (SOC < 5%)
        if SOC_d(k) < 0.05; break; end
    end
    k_end_d = k;  % last valid index

    % ------------------------------------------------------------------
    %  (b) CHARGE SIMULATION
    %  Start from it = 0.9*Q (nearly depleted), charge back up
    % ------------------------------------------------------------------
    Vbatt_c  = zeros(N_chg, 1);
    SOC_c    = zeros(N_chg, 1);
    Exp_c    = zeros(N_chg, 1);
    istar_c  = zeros(N_chg, 1);

    it_c       = 0.9 * bat.Q;   % start at 10% SOC (almost empty)
    Exp_c(1)   = 0;             % nearly depleted: exponential zone near 0
    istar_c(1) = 0;
    SOC_c(1)   = 1 - it_c / bat.Q;
    Vbatt_c(1) = battery_voltage(bat, it_c, 0, Exp_c(1), 0);

    for k = 2:N_chg
        i_k = i_chg_vec(k);   % negative value (charging)

        % Update filtered current
        istar_c(k) = istar_c(k-1) + (dt/tau) * (i_k - istar_c(k-1));

        % Update exponential zone voltage
        if strcmp(bat.type, 'li_ion')
            Exp_c(k) = bat.A * exp(-bat.B * max(0, it_c));
        else
            % u(t) = 1 during charge → equation drives Exp toward A
            dExp     = bat.B * abs(i_k) * (-Exp_c(k-1) + bat.A * 1);
            Exp_c(k) = Exp_c(k-1) + dExp * dt;
            Exp_c(k) = max(0, min(bat.A, Exp_c(k)));
        end

        % Compute battery terminal voltage using the CHARGE equation
        Vbatt_c(k) = battery_voltage(bat, it_c, istar_c(k), Exp_c(k), i_k);

        % Coulomb counting: during charge i<0, so it decreases
        it_c   = it_c + i_k * (dt/3600);
        it_c   = max(0, min(bat.Q, it_c));

        SOC_c(k) = max(0, 1 - it_c / bat.Q);

        % Stop if fully charged (SOC > 98%)
        if SOC_c(k) > 0.98; break; end
    end
    k_end_c = k;

    % ------------------------------------------------------------------
    %  STORE RESULTS FOR LATER USE (Vbatt vs Q plots)
    % ------------------------------------------------------------------
    batteries(b).sim_dis.t      = t_dis(1:k_end_d);
    batteries(b).sim_dis.V      = Vbatt_d(1:k_end_d);
    batteries(b).sim_dis.I      = i_dis_vec(1:k_end_d);
    batteries(b).sim_dis.SOC    = SOC_d(1:k_end_d);
    batteries(b).sim_chg.t      = t_chg(1:k_end_c);
    batteries(b).sim_chg.V      = Vbatt_c(1:k_end_c);
    batteries(b).sim_chg.I      = i_chg_vec(1:k_end_c);
    batteries(b).sim_chg.SOC    = SOC_c(1:k_end_c);

    % ------------------------------------------------------------------
    %  COMMAND WINDOW: KEY RESULTS FOR THIS BATTERY
    % ------------------------------------------------------------------
    fprintf('=================================================================\n');
    fprintf('  BATTERY: %s\n', bat.name);
    fprintf('=================================================================\n');
    fprintf('  Discharge current I_dis = %.3f A  (= %.1fC)\n', I_dis, I_dis/I_1C);
    fprintf('  Charge current    I_chg = %.3f A  (= %.1fC)\n', I_chg, I_chg/I_1C);
    fprintf('\n');

    % Key time moments during DISCHARGE
    fprintf('  --- DISCHARGE KEY MOMENTS ---\n');
    fprintf('  %-8s  %-10s  %-12s  %-12s  %-10s\n', ...
            'Time(s)', 'Vbatt(V)', 'Current(A)', 'Power(W)', 'SOC(%)');
    t_snap = round(linspace(1, k_end_d, 6));  % 6 evenly spaced snapshots
    for s = t_snap
        P_s = Vbatt_d(s) * i_dis_vec(s);
        fprintf('  %-8d  %-10.4f  %-12.3f  %-12.4f  %-10.2f\n', ...
                t_dis(s), Vbatt_d(s), i_dis_vec(s), P_s, SOC_d(s)*100);
    end
    fprintf('\n');

    % Key time moments during CHARGE
    fprintf('  --- CHARGE KEY MOMENTS ---\n');
    fprintf('  %-8s  %-10s  %-12s  %-12s  %-10s\n', ...
            'Time(s)', 'Vbatt(V)', 'Current(A)', 'Power(W)', 'SOC(%)');
    t_snap_c = round(linspace(1, k_end_c, 6));
    for s = t_snap_c
        P_s = Vbatt_c(s) * i_chg_vec(s);
        fprintf('  %-8d  %-10.4f  %-12.3f  %-12.4f  %-10.2f\n', ...
                t_chg(s), Vbatt_c(s), i_chg_vec(s), P_s, SOC_c(s)*100);
    end
    fprintf('\n');

    % ------------------------------------------------------------------
    %  FIGURE A — DISCHARGE (one figure per battery)
    %  Layout matches Figs 5a–8a of the paper:
    %    Subplot 1: Vbatt vs time
    %    Subplot 2: Current vs time
    %    Subplot 3: SOC vs time
    %    Subplot 4: Instantaneous power vs time
    % ------------------------------------------------------------------
    tab_d = uitab('Parent', tgroup, 'Title', ['DISCHARGE: ' bat.name]);

    % Subplot 1: Battery voltage
    ax1 = subplot(4,1,1, 'Parent', tab_d);
    area(t_dis(1:k_end_d), Vbatt_d(1:k_end_d), ...
         'FaceColor',[0.85 0.92 1.0], 'EdgeColor',[0.1 0.3 0.8], 'LineWidth',1.4);
    ylabel('V_{batt} (V)');
    title('Battery Terminal Voltage');
    grid on;
    ylim([bat.Vnom * 0.65,  bat.E0 + bat.A + 0.05]);
    set(ax1,'XTickLabel',[]);

    % Subplot 2: Current
    ax2 = subplot(4,1,2, 'Parent', tab_d);
    area(t_dis(1:k_end_d), i_dis_vec(1:k_end_d), ...
         'FaceColor',[1.0 0.90 0.85], 'EdgeColor',[0.8 0.2 0.1], 'LineWidth',1.2);
    ylabel('I_{batt} (A)');
    title('Applied Current  (+ = Discharge)');
    grid on;
    set(ax2,'XTickLabel',[]);

    % Subplot 3: State of charge
    ax3 = subplot(4,1,3, 'Parent', tab_d);
    plot(t_dis(1:k_end_d), SOC_d(1:k_end_d)*100, ...
         'Color',[0.1 0.6 0.1], 'LineWidth',1.6);
    ylabel('SOC (%)');
    title('State of Charge');
    ylim([0 105]);
    grid on;
    set(ax3,'XTickLabel',[]);

    % Subplot 4: Instantaneous power delivered to load
    ax4 = subplot(4,1,4, 'Parent', tab_d);
    P_d = Vbatt_d(1:k_end_d) .* i_dis_vec(1:k_end_d);
    plot(t_dis(1:k_end_d), P_d, ...
         'Color',[0.6 0.1 0.6], 'LineWidth',1.2);
    ylabel('Power (W)');
    title('Instantaneous Power Output');
    grid on;
    xlabel('Time (s)');

    % sgtitle('DISCHARGE', 'FontWeight','bold','FontSize',12); % Removido para evitar erro de incompatibilidade com tabs no sgtitle

    % ------------------------------------------------------------------
    %  FIGURE B — CHARGE (one figure per battery)
    %  Layout matches Figs 5b–8b of the paper:
    %    Subplot 1: Vbatt vs time
    %    Subplot 2: Current vs time (negative)
    %    Subplot 3: SOC vs time
    %    Subplot 4: Instantaneous power absorbed from charger
    % ------------------------------------------------------------------
    tab_c = uitab('Parent', tgroup, 'Title', ['CHARGE: ' bat.name]);

    ax1c = subplot(4,1,1, 'Parent', tab_c);
    area(t_chg(1:k_end_c), Vbatt_c(1:k_end_c), ...
         'FaceColor',[1.0 0.95 0.80], 'EdgeColor',[0.8 0.55 0.0], 'LineWidth',1.4);
    ylabel('V_{batt} (V)');
    title('Battery Terminal Voltage');
    grid on;
    ylim([bat.Vnom * 0.65, bat.E0 + bat.A + 0.05]);
    set(ax1c,'XTickLabel',[]);

    ax2c = subplot(4,1,2, 'Parent', tab_c);
    area(t_chg(1:k_end_c), i_chg_vec(1:k_end_c), ...
         'FaceColor',[0.85 1.0 0.88], 'EdgeColor',[0.0 0.55 0.2], 'LineWidth',1.2);
    ylabel('I_{batt} (A)');
    title('Applied Current  (− = Charge)');
    grid on;
    set(ax2c,'XTickLabel',[]);

    ax3c = subplot(4,1,3, 'Parent', tab_c);
    plot(t_chg(1:k_end_c), SOC_c(1:k_end_c)*100, ...
         'Color',[0.0 0.45 0.74], 'LineWidth',1.6);
    ylabel('SOC (%)');
    title('State of Charge');
    ylim([0 105]);
    grid on;
    set(ax3c,'XTickLabel',[]);

    ax4c = subplot(4,1,4, 'Parent', tab_c);
    % Power absorbed = V * |i| (positive number means energy flowing in)
    P_c = Vbatt_c(1:k_end_c) .* abs(i_chg_vec(1:k_end_c));
    plot(t_chg(1:k_end_c), P_c, ...
         'Color',[0.6 0.1 0.6], 'LineWidth',1.2);
    ylabel('Power (W)');
    title('Instantaneous Power Absorbed from Charger');
    grid on;
    xlabel('Time (s)');

end   % end of main battery loop

% =========================================================================
%  SECTION 6 — VBATT vs CAPACITY (Ah)  — replicates Fig. 4 of the paper
%
%  This is a steady-state discharge at CONSTANT current (no pulses).
%  X-axis = charge withdrawn (Ah), Y-axis = terminal voltage.
%  Multiple C-rates are shown on each subplot.
%  This is the "datasheet curve" that manufacturers provide, and from
%  which the model parameters were originally extracted.
% =========================================================================

fprintf('=================================================================\n');
fprintf('  STEADY-STATE DISCHARGE CURVES  (Vbatt vs Capacity)\n');
fprintf('  Replicates Fig. 4 of the paper — no pulses, constant current\n');
fprintf('=================================================================\n\n');

C_rates     = [0.2, 1, 2, 5];
line_colors = {[0.1 0.3 0.9], [0.9 0.1 0.1], [0.0 0.65 0.0], [0.7 0.0 0.7]};
line_styles = {'-', '--', '-.', ':'};

tab_ss = uitab('Parent', tgroup, 'Title', 'Steady-State (All)');

for b = 1:4
    bat = batteries(b);
    subplot(2, 2, b, 'Parent', tab_ss);
    hold on; grid on;

    for c = 1:length(C_rates)
        Ic    = C_rates(c) * bat.Q;     % current for this C-rate [A]
        dt_ss = 0.5;                    % finer time step for smooth curve

        % Pre-allocate to max possible length (full discharge at 0.2C)
        max_steps = ceil((bat.Q / Ic) * 3600 / dt_ss * 1.1) + 10;
        V_ss  = zeros(max_steps, 1);
        Q_ss  = zeros(max_steps, 1);    % capacity withdrawn at each step

        it_ss    = 0;      % charge withdrawn [Ah]
        Exp_ss   = bat.A;  % start fully charged
        istar_ss = 0;

        V_ss(1) = battery_voltage(bat, 0, 0, bat.A, Ic);
        Q_ss(1) = 0;

        for k = 2:max_steps
            % Filtered current: at steady state i* → i, but we evolve it
            istar_ss = istar_ss + (dt_ss/tau) * (Ic - istar_ss);

            % Exponential zone
            if strcmp(bat.type, 'li_ion')
                Exp_ss = bat.A * exp(-bat.B * it_ss);
            else
                dExp   = bat.B * Ic * (-Exp_ss + bat.A * 0); % discharge u=0
                Exp_ss = Exp_ss + dExp * dt_ss;
                Exp_ss = max(0, Exp_ss);
            end

            V_ss(k) = battery_voltage(bat, it_ss, istar_ss, Exp_ss, Ic);
            it_ss   = it_ss + Ic * (dt_ss / 3600);
            Q_ss(k) = it_ss;

            % Stop at 98% of capacity withdrawn or if voltage collapses
            if it_ss >= 0.98 * bat.Q || V_ss(k) < 0.5 * bat.Vnom
                break;
            end
        end
        k_end_ss = k;

        plot(Q_ss(1:k_end_ss), V_ss(1:k_end_ss), ...
             'Color', line_colors{c}, 'LineStyle', line_styles{c}, ...
             'LineWidth', 1.6, 'DisplayName', [num2str(C_rates(c)) 'C']);

        fprintf('  %s @ %.1fC: Vstart=%.4fV  Vend=%.4fV  Q_disch=%.3fAh\n', ...
                bat.name, C_rates(c), V_ss(1), V_ss(k_end_ss), Q_ss(k_end_ss));
    end

    xlabel('Discharged Capacity (Ah)');
    ylabel('V_{batt} (V)');
    title(bat.name);
    legend('Location','southwest','FontSize',8);
    xlim([0 bat.Q * 1.02]);
    ylim([bat.Vnom * 0.65, bat.E0 + bat.A + 0.05]);
end

fprintf('\n');

% =========================================================================
%  SECTION 7 — LI-ION REPEATED CHARGE/DISCHARGE CYCLES  (Fig. 9 style)
%
%  The paper shows four complete discharge-charge cycles for a Li-Ion cell.
%  This section alternates between discharge and charge to replicate that.
% =========================================================================

fprintf('=================================================================\n');
fprintf('  LI-ION REPEATED CHARGE/DISCHARGE CYCLES  (Fig. 9 style)\n');
fprintf('=================================================================\n\n');

bat_li  = batteries(3);   % Li-Ion 2.3 Ah
I_cyc   = 2 * bat_li.Q;  % 2C rate — same order as Fig. 9 in the paper
T_total = 8000;           % total simulation time [s]
dt_li   = 1;

t_li   = (0:dt_li:T_total)';
N_li   = length(t_li);

% Build alternating current: discharge 700s / charge 700s / repeat
% The block length is chosen so ~4 full cycles fit in T_total
block = 700;   % seconds per half-cycle
i_li  = zeros(N_li, 1);
for k = 1:N_li
    half_idx = floor(t_li(k) / block);
    if mod(half_idx, 2) == 0
        i_li(k) =  I_cyc;   % positive → discharge
    else
        i_li(k) = -I_cyc;   % negative → charge
    end
end

% State variables
Vli    = zeros(N_li, 1);
SOCli  = zeros(N_li, 1);
ist_li = 0;
it_li  = 0;

Vli(1)   = battery_voltage(bat_li, 0, 0, bat_li.A, i_li(1));
SOCli(1) = 1.0;

for k = 2:N_li
    i_k = i_li(k);

    % Filtered current
    ist_li = ist_li + (dt_li/tau) * (i_k - ist_li);

    % Exponential zone — Li-Ion uses static formula (no hysteresis)
    Exp_li = bat_li.A * exp(-bat_li.B * max(0, it_li));

    % Battery voltage (function handles discharge/charge internally)
    Vli(k) = battery_voltage(bat_li, it_li, ist_li, Exp_li, i_k);

    % Coulomb counting
    it_li   = it_li + i_k * (dt_li / 3600);
    it_li   = max(0, min(bat_li.Q, it_li));

    SOCli(k) = max(0, 1 - it_li / bat_li.Q);
end

% Instantaneous power: positive = delivered to load, negative = absorbed
P_li = Vli .* i_li;

% Command window output for Li-Ion cycles
fprintf('  Current amplitude: %.2f A (%.1fC)\n', I_cyc, I_cyc/bat_li.Q);
fprintf('  Cycle block: %d s discharge / %d s charge\n', block, block);
fprintf('\n  %-8s  %-10s  %-12s  %-10s  %-12s\n', ...
        'Time(s)', 'Vbatt(V)', 'Current(A)', 'SOC(%)', 'Power(W)');
t_snap_li = round(linspace(1, N_li, 8));
for s = t_snap_li
    fprintf('  %-8d  %-10.4f  %-12.3f  %-10.2f  %-12.4f\n', ...
            t_li(s), Vli(s), i_li(s), SOCli(s)*100, P_li(s));
end
fprintf('\n');

% Figure: four subplots matching Fig. 9 of the paper
tab_cyc = uitab('Parent', tgroup, 'Title', 'Li-Ion Cycles');

% Separate discharge and charge periods for colouring
i_pos = i_li;  i_pos(i_li <  0) = NaN;  % keep only discharge segments
i_neg = i_li;  i_neg(i_li >= 0) = NaN;  % keep only charge segments
V_dis_only = Vli; V_dis_only(i_li <  0) = NaN;
V_chg_only = Vli; V_chg_only(i_li >= 0) = NaN;

ax1li = subplot(4,1,1, 'Parent', tab_cyc);
plot(t_li, V_dis_only, 'Color',[0.1 0.3 0.9], 'LineWidth',1.3, 'DisplayName','Discharge');
hold on;
plot(t_li, V_chg_only, 'Color',[0.9 0.5 0.0], 'LineWidth',1.3, 'DisplayName','Charge');
ylabel('V_{batt} (V)');
title('Li-Ion Battery Voltage  (blue=discharge, orange=charge)');
legend('Location','best','FontSize',8);
grid on;
set(ax1li,'XTickLabel',[]);

ax2li = subplot(4,1,2, 'Parent', tab_cyc);
plot(t_li, i_pos, 'Color',[0.1 0.3 0.9], 'LineWidth',1.2, 'DisplayName','Discharge');
hold on;
plot(t_li, i_neg, 'Color',[0.9 0.5 0.0], 'LineWidth',1.2, 'DisplayName','Charge');
yline(0, 'k--', 'LineWidth', 0.8);
ylabel('I_{batt} (A)');
title('Battery Current  (+ discharge, − charge)');
grid on;
set(ax2li,'XTickLabel',[]);

ax3li = subplot(4,1,3, 'Parent', tab_cyc);
plot(t_li, SOCli*100, 'Color',[0.1 0.6 0.1], 'LineWidth',1.6);
ylabel('SOC (%)');
title('State of Charge');
ylim([0 105]);
grid on;
set(ax3li,'XTickLabel',[]);

ax4li = subplot(4,1,4, 'Parent', tab_cyc);
plot(t_li, P_li, 'Color',[0.6 0.0 0.6], 'LineWidth',1.0);
yline(0,'k--','LineWidth',0.8);
ylabel('Power (W)');
title('Instantaneous Power  (+ output / − input)');
grid on;
xlabel('Time (s)');


% =========================================================================
%  END OF SCRIPT
% =========================================================================

% =========================================================================
%  LOCAL FUNCTION: battery_voltage
%  =========================================================================
%
%  Computes the battery terminal voltage Vbatt given:
%    bat    : struct with battery parameters (E0, R, K, Q, A, B, type)
%    it     : charge withdrawn from battery [Ah]  (0=full, Q=empty)
%    i_star : filtered current [A]  (slow dynamic state)
%    Exp    : current value of the exponential zone voltage [V]
%    i      : instantaneous battery current [A]  (+ discharge, - charge)
%
%  DISCHARGE equation (i >= 0):
%    Vbatt = E0 - R*i - K*Q/(Q-it)*it  - K*Q/(Q-it)*i* + Exp
%                       ↑ pol. voltage    ↑ pol. resistance
%
%  CHARGE equation — Lead-Acid / Li-Ion (i < 0):
%    Vbatt = E0 - R*i - K*Q/(it-0.1Q)*i* - K*Q/(Q-it)*it  + Exp
%
%  CHARGE equation — NiMH / NiCd (i < 0):
%    Vbatt = E0 - R*i - K*Q/(|it|-0.1Q)*i* - K*Q/(Q-it)*it + Exp
%    (absolute value in denominator: models voltage drop at overcharge)
%
%  NOTE: The 0.1*Q offset in the charge denominator was found experimentally;
%  it corrects for the fact that the polarisation resistance does not go to
%  infinity exactly when it=0 but shifts by ~10% of capacity.

function V = battery_voltage(bat, it, i_star, Exp, i)

    E0  = bat.E0;
    R   = bat.R;
    K   = bat.K;
    Q   = bat.Q;
    eps_v = 1e-5;    % small guard to prevent exact division by zero

    if i >= 0
        % ---- DISCHARGE ----
        % Polarisation voltage term: K * Q/(Q-it) * it
        % Polarisation resistance term: K * Q/(Q-it) * i*
        % Both share the same denominator (Q - it), which → ∞ as battery empties
        denom = Q - it;
        if denom < eps_v; denom = eps_v; end

        pol_voltage    = K * (Q / denom) * it;
        pol_resistance = K * (Q / denom) * i_star;
        V = E0 - R*i - pol_voltage - pol_resistance + Exp;

    else
        % ---- CHARGE ----
        % Polarisation voltage term is the same as discharge
        denom_V = Q - it;
        if denom_V < eps_v; denom_V = eps_v; end
        pol_voltage = K * (Q / denom_V) * it;

        % Polarisation resistance denominator changes by chemistry:
        switch bat.type
            case {'lead_acid', 'li_ion'}
                % Denominator: it - 0.1*Q
                % As battery approaches full charge (it→0), this → -0.1Q,
                % making pol_resistance large → voltage rises steeply at EOC
                denom_R = it - 0.1*Q;

            case 'nimh_nicd'
                % Denominator: |it| - 0.1*Q
                % When overcharged (it < 0), |it| grows → denom grows →
                % pol_resistance shrinks → voltage drops (ΔV detection)
                denom_R = abs(it) - 0.1*Q;

            otherwise
                denom_R = it - 0.1*Q;
        end
        if abs(denom_R) < eps_v; denom_R = sign(denom_R) * eps_v; end

        pol_resistance = K * (Q / denom_R) * i_star;
        V = E0 - R*i - pol_resistance - pol_voltage + Exp;
    end

    % Hard physical limits: voltage cannot be negative or exceed 2*E0
    V = max(0, min(2*E0, V));
end