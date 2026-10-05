function fontes = montar_fontes(cenario, arch, t_min, t0_datetime, econ, incluir_bateria)
%MONTAR_FONTES Substitui spec_fontes.m + carregar_fontes.m (obsoletos).
%Le os 4 CSVs da plataforma + o PV e devolve um array de contrato_fonte,
%pronto para despacho.m. E o UNICO lugar que sabe os nomes dos arquivos e
%das colunas -- despacho.m/custo_despacho.m/restricoes_despacho.m nunca
%veem "termica", "eolica", "fc" ou "bateria", so contrato_fonte generico.
%
%ALINHAMENTO DE TEMPO: cada uma das 4 fontes e alinhada ao SEU PROPRIO
%primeiro timestamp (tn = t_abs - t_abs(1)), nao a um t0_datetime
%compartilhado. Isso NAO e so uma correcao de fuso/data: as 4 fontes tem
%DURACOES incompativeis entre si (termica ~24h, eolica ~41h, FC 6 min,
%bateria 10 min, contra uma missao de 2h) -- sao claramente rodadas
%independentes de cada modelo, nao uma execucao conjunta sincronizada no
%relogio real. Alinhar por timestamp absoluto nunca faria sentido aqui.
%t0_datetime E MANTIDO no parametro so por compatibilidade de assinatura
%(carregar_pv.m ainda usa alinhamento absoluto, que faz sentido para o PV
%pois o horario do dia importa para irradiacao solar); nao e mais usado
%dentro desta funcao para termica/eolica/FC/bateria.
%
%DURACAO INCOMPATIVEL COM A MISSAO: mesmo com alinhamento relativo
%corrigido, FC (6 min) e bateria (10 min) NAO cobrem os 120 min da missao
%-- diag_cobertura() vai avisar "cobertura parcial" e os instantes fora
%da janela do CSV viram envelope ZERO (fonte indisponivel), nunca
%extrapolados. Isso e SEGURO (nao inventa capacidade) mas provavelmente
%NAO E O QUE VOCE QUER: FC/bateria apareceriam disponiveis so nos
%primeiros minutos da simulacao. Se a intencao e ter FC/bateria
%disponiveis pela missao inteira, os CSVs delas precisam ser regerados
%cobrindo os 120 min, ou voce me diz explicitamente qual politica usar
%para preencher o resto (repetir o ultimo estado? assumir disponivel sem
%teto conhecido? etc.) -- nao vou assumir nenhuma dessas sozinho.
%
%Chamar em main.m depois de carregar_perfil_carga (que define t_min) e
%antes de despacho().

    DADOS_DIR = fullfile(fileparts(mfilename('fullpath')), '..', 'dados');
    Nt = numel(t_min);
    fontes = repmat(contrato_fonte('nome','_vazio','P_max_unid_kW',zeros(Nt,1)), 0, 0);
    if nargin < 6 || isempty(incluir_bateria), incluir_bateria = true; end
    % incluir_bateria=false pula o bloco inteiro (calibracao de Rint
    % inclusive) -- usar enquanto bateria.csv nao tiver corrente/tensao
    % suficientes para calibrar com confianca. NAO inventa nenhum valor
    % no lugar: o despacho simplesmente roda sem essa fonte.

    %% ---------------------------------------------------------- TERMICA
    Tt = readtable(fullfile(DADOS_DIR,'termica.csv'), 'VariableNamingRule','preserve');
    t_abs = tempo_csv(Tt,'timestamp');
    tn = minutes(t_abs - t_abs(1));   % relativo ao PROPRIO inicio -- ver nota de cabecalho
    diag_cobertura('termica', tn, t_min);
    P_max = ler_serie_csv(Tt,'contractual_target_mw','MW', tn, t_min, 'previous');
    P_min = ler_serie_csv(Tt,'inflexibility_mw',      'MW', tn, t_min, 'previous');
    rmp   = ler_serie_csv(Tt,'ramp_rate_mw_min',       'MW', tn, t_min, 'previous');
    c_rs  = ler_serie_csv(Tt,'variable_cost_rs',    'nenhuma', tn, t_min, 'previous');
    e_mwh = ler_serie_csv(Tt,'energy_delivered_mwh','nenhuma', tn, t_min, 'previous');
    c_start = ler_serie_csv(Tt,'startup_cost_rs',   'nenhuma', tn, t_min, 'previous');

    fora = isnan(P_max) | isnan(P_min);
    P_max(fora) = 0; P_min(fora) = 0;
    c_kWh = custo_por_kwh(c_rs, e_mwh*1000);   % MWh->kWh dentro da funcao

    fontes(end+1) = contrato_fonte('nome','termica', 'tipo','geracao', ...
        'n_unid', 1, 'n_ini', double(P_min(1) > 0), ...
        'P_max_unid_kW', P_max, 'P_min_unid_kW', P_min, ...
        'c_var_rs_kWh', c_kWh, ...
        'c_start_unid_rs', mediana_positiva(c_start), ...
        'ramp_kW_min', mediana_positiva(rmp), ...
        'eta', 1.0);
        % eta=1.0: nao ha, em termica.csv nem em arch, um dado de perda de
        % conversao especifica da termica ate o barramento. NAO estou mais
        % assumindo um numero de catalogo (usava 0.97 antes, sem base). Se
        % existir uma etapa de conversao real com perda conhecida, informe-a.

    %% ----------------------------------------------------------- EOLICA
    Tw = readtable(fullfile(DADOS_DIR,'eolica.csv'), 'VariableNamingRule','preserve');
    t_abs = tempo_csv(Tw,'timestamp');
    tn = minutes(t_abs - t_abs(1));
    diag_cobertura('eolica', tn, t_min);
    P_net = ler_serie_csv(Tw,'power_net_kw','kW', tn, t_min, 'linear');
    P_net(isnan(P_net)) = 0;

    fontes(end+1) = contrato_fonte('nome','eolica', 'tipo','nao_despachavel', ...
        'n_unid', 1, ...
        'P_max_unid_kW', max(P_net,0), 'P_min_unid_kW', zeros(Nt,1), ...
        'c_var_rs_kWh', zeros(Nt,1), 'eta', 1.0);
        % custo 0: recurso sem combustivel. Se houver PPA/contrato de compra
        % de energia eolica, o R$/kWh entra aqui.

    %% ---------------------------------------------------------------- FC
    % Config de equipamento que continua vindo de arch (nao e "modelo
    % inventado", e especificacao de hardware, igual N_fc = quantidade de
    % motores instalados): numero de unidades e eficiencia de conversao
    % ate o barramento (arch.conv.eta_dc1). TUDO o mais -- teto, piso,
    % rampa, custo -- vem agora do proprio fc.csv.
    N_fc = arch.fc.N_fc;

    Tf = readtable(fullfile(DADOS_DIR,'fc.csv'), 'VariableNamingRule','preserve');
    t_abs = tempo_csv(Tf,'timestamp');
    tn = minutes(t_abs - t_abs(1));
    diag_cobertura('fc', tn, t_min);

    nomes_fc = strtrim(string(Tf.Properties.VariableNames));
    raw_state = string(Tf{:, strcmpi(nomes_fc,'state')});
    fprintf('[fc] valores brutos unicos de "state": %s\n', strjoin(unique(raw_state), ' | '));
    % Dicionario real observado: FAULT_LIMITED | IDLE | RUN | STARTUP.
    % So FAULT_LIMITED fecha o envelope (indisponivel) -- IDLE/STARTUP nao
    % indicam falha, so que a unidade nao estava sendo despachada naquele
    % instante do historico, o que nao significa incapacidade.
    Tf.disp_flag_tmp = double(~strcmpi(raw_state, 'FAULT_LIMITED'));
    st = ler_serie_csv(Tf,'disp_flag_tmp','nenhuma', tn, t_min, 'previous', false);
    disp_fc = ones(Nt,1);
    if ~isempty(st)
        disp_fc(isnan(st)) = 0;      % fora da janela do CSV -> indisponivel (nunca extrapola)
        disp_fc(st == 0) = 0;        % FAULT_LIMITED
    end

    P_deliv_raw   = ler_serie_csv(Tf,'P_FC_delivered_kW','kW', tn, t_min, 'previous', false);
    P_stack_raw   = ler_serie_csv(Tf,'P_stack_kW','kW', tn, t_min, 'previous', false);
    h2_kg_h_raw   = ler_serie_csv(Tf,'hydrogen_supplied_kg_h','nenhuma', tn, t_min, 'previous', false);

    % ---- envelope: OBSERVADO no CSV, nunca inventado. Constante no tempo
    % (nao ha coluna de capacidade nominal) ate o CSV cobrir a missao
    % inteira -- combinado que o teto sera reajustado depois disso.
    valido_op = isfinite(P_stack_raw) & isfinite(P_deliv_raw) & isfinite(h2_kg_h_raw) & (P_deliv_raw > 0);
    if sum(valido_op) < 3
        error('montar_fontes:fcSemOperacao', ...
            'fc.csv: menos de 3 pontos com P_FC_delivered_kW>0 e dados completos -- nao da pra derivar envelope/custo do CSV.');
    end
    Pmax_stack_obs = max(P_stack_raw(valido_op));
    Pmin_stack_obs = min(P_stack_raw(valido_op & P_stack_raw > 1e-6));
    fprintf('[fc] envelope por stack observado no CSV: [%.2f, %.2f] kW (de %d pontos em operacao)\n', ...
        Pmin_stack_obs, Pmax_stack_obs, sum(valido_op));

    % ---- rampa: derivada do proprio historico de P_stack_kW, nao de arch.
    idx_op = find(valido_op);
    dP = diff(P_stack_raw(idx_op)); dt_min = diff(t_min(idx_op));
    ramp_obs = abs(dP) ./ max(dt_min,eps);
    ramp_obs = ramp_obs(isfinite(ramp_obs) & ramp_obs > 0);
    if isempty(ramp_obs)
        ramp_kW_min_fc = inf;
        warning('montar_fontes:fcRampaIndefinida', ...
            'Sem pontos suficientes em fc.csv para estimar rampa: usando Inf (sem limite) ate haver mais dados.');
    else
        ramp_kW_min_fc = max(ramp_obs);   % pior caso observado, nao mediana -- poucos pontos ainda
    end

    % ---- custo/consumo: curva EMPIRICA kg_H2/kWh x potencia por stack,
    % ajustada direto nos dados (hydrogen_supplied_kg_h / P_FC_delivered_kW),
    % SEM Elow nem curva de eficiencia de arch -- o CSV ja da a massa de
    % H2 diretamente, entao nao precisa nem de LHV nem de eta assumido.
    x_obs = P_stack_raw(valido_op);
    kg_kWh_obs = h2_kg_h_raw(valido_op) ./ P_deliv_raw(valido_op);   % (kg/h)/kW = kg/kWh
    [x_u, ~, ic] = unique(round(x_obs,4));
    y_u = accumarray(ic, kg_kWh_obs, [], @median);
    [x_u, ord] = sort(x_u); y_u = y_u(ord);
    fprintf('[fc] curva kg_H2/kWh construida com %d pontos unicos de potencia por stack\n', numel(x_u));

    curva_fc = struct('x', x_u, 'y', y_u);
    kg_por_kwh_fn = @(P_por_stack) interp_clamp(curva_fc, P_por_stack);
    custo_fn_fc = @(P_kW, n, ~) kg_por_kwh_fn(abs(P_kW)/max(n,1)) * econ.preco_H2_rs_kg;
    qtd_fn_fc   = @(P_kW, n, ~) kg_por_kwh_fn(abs(P_kW)/max(n,1));

    fontes(end+1) = contrato_fonte('nome','fc', 'tipo','geracao', ...
        'n_unid', N_fc, 'n_ini', N_fc, 'dn_max', 1, ...
        'P_max_unid_kW', Pmax_stack_obs * disp_fc, ...
        'P_min_unid_kW', Pmin_stack_obs * disp_fc, ...
        'custo_fn', custo_fn_fc, ...
        'qtd_fisica_fn', qtd_fn_fc, 'qtd_fisica_unidade', 'kg_H2', ...
        'c_start_unid_rs', 0, ...   % TODO: sem coluna de custo de partida no CSV
        'ramp_kW_min', ramp_kW_min_fc, ...
        'eta', arch.conv.eta_dc1);

    %% ----------------------------------------------------------- BATERIA
    if incluir_bateria
    Tb = readtable(fullfile(DADOS_DIR,'bateria.csv'), 'VariableNamingRule','preserve');
    t_abs = tempo_csv(Tb,'timestamp');
    tn = minutes(t_abs - t_abs(1));
    diag_cobertura('bateria', tn, t_min);
    P_ext = ler_serie_csv(Tb,'power_W','W', tn, t_min, 'linear');
    fl    = ler_serie_csv(Tb,'limit_flag','nenhuma', tn, t_min, 'nearest');
    V_ext = ler_serie_csv(Tb,'voltage_V','nenhuma', tn, t_min, 'linear');
    I_ext = ler_serie_csv(Tb,'current_A','nenhuma', tn, t_min, 'linear');
    soc_pct = ler_serie_csv(Tb,'soc_percent','pct', tn, t_min, 'linear', false);
    if isempty(soc_pct) || all(isnan(soc_pct))
        error('montar_fontes:bateriaSemSOC', 'bateria.csv sem soc_percent valido no primeiro instante.');
    end
    SOC_ini_csv = soc_pct(find(~isnan(soc_pct),1,'first'));
    fprintf('[bateria] SOC inicial vindo do CSV: %.1f%%\n', 100*SOC_ini_csv);

    % Teto/piso de potencia: OBSERVADO em power_W, nao mais uma base de
    % arch apertada pelo CSV. Constante no tempo (nao ha coluna de
    % capacidade nominal instantanea) ate o CSV cobrir a missao inteira.
    if isempty(P_ext) || all(~isfinite(P_ext))
        error('montar_fontes:bateriaSemPower', 'bateria.csv sem power_W valido: sem isso nao da pra derivar o envelope do CSV.');
    end
    Pdis_obs = max(P_ext(isfinite(P_ext) & P_ext > 0), [], 'omitnan');
    Pchg_obs = min(P_ext(isfinite(P_ext) & P_ext < 0), [], 'omitnan');
    if isempty(Pdis_obs), Pdis_obs = 0; end
    if isempty(Pchg_obs), Pchg_obs = 0; end
    fprintf('[bateria] envelope de potencia observado: descarga ate %.2f kW, carga ate %.2f kW\n', Pdis_obs, Pchg_obs);
    Pdis_max = Pdis_obs * ones(Nt,1);
    Pchg_max = Pchg_obs * ones(Nt,1);
    if ~isempty(fl)
        satur_pos = (fl ~= 0) & (P_ext > 0);
        satur_neg = (fl ~= 0) & (P_ext < 0);
        Pdis_max(satur_pos) = min(Pdis_max(satur_pos), P_ext(satur_pos));
        Pchg_max(satur_neg) = max(Pchg_max(satur_neg), P_ext(satur_neg));
    end

    % eta_carga/eta_descarga CALIBRADOS a partir de voltage_V x current_A
    % do proprio CSV -- nao ha mais nenhum valor de catalogo/literatura
    % aqui. Regressao V = Voc - Rint*I (convencao: I>0 descarga, coerente
    % com o sinal de power_W ja usado acima). A partir de Voc/Rint,
    % eficiencia instantanea = V/Voc na descarga (P_entregue/P_interna) e
    % Voc/V na carga (P_armazenada/P_fornecida); tomamos a mediana sobre
    % os pontos REAIS observados de cada sentido, nao um unico I "tipico".
    if isempty(V_ext) || isempty(I_ext)
        error('montar_fontes:bateriaSemVI', ...
            ['bateria.csv nao tem voltage_V e/ou current_A: sem eles nao ha ' ...
             'como calibrar eficiencia de carga/descarga a partir do dado real, ' ...
             'e este projeto nao aceita mais valor de catalogo como substituto.']);
    end
    ok = isfinite(V_ext) & isfinite(I_ext);
    if sum(ok) < 10
        error('montar_fontes:bateriaPoucosPontos', ...
            ['Apenas %d pontos validos de voltage_V/current_A apos alinhar ao t0_datetime ' ...
             '(de %d no total). Se o aviso "sem sobreposicao"/"cobertura parcial" acima ' ...
             'apareceu para "bateria", o problema NAO e a coluna -- e cenario_t0_datetime ' ...
             'em main.m nao bater com o instante inicial real de bateria.csv. Confira o ' ...
             'primeiro timestamp do arquivo e ajuste cenario_t0_datetime para esse valor.'], ...
             sum(ok), numel(V_ext));
    end
    A = [ones(sum(ok),1), t_min(ok), -I_ext(ok)];
    theta = A \ V_ext(ok);
    Voc_cal = theta(1); deriva_V_min = theta(2); Rint_cal = theta(3);
    res = V_ext(ok) - A*theta;
    R2 = 1 - var(res)/var(V_ext(ok));
    std_I = std(I_ext(ok)); std_V = std(V_ext(ok));
    fprintf('[bateria] diagnostico bruto: I_ext em [%.3f, %.3f] A (std=%.4f) | V_ext em [%.3f, %.3f] V (std=%.4f), N=%d pontos\n', ...
        min(I_ext(ok)), max(I_ext(ok)), std_I, min(V_ext(ok)), max(V_ext(ok)), std_V, sum(ok));
    fprintf('[bateria] regressao com deriva temporal: Voc0=%.3f V, deriva=%.4f V/min, Rint=%.5f ohm, R2=%.3f\n', ...
        Voc_cal, deriva_V_min, Rint_cal, R2);
    if std_I < 1e-6
        error('montar_fontes:bateriaCorrenteConstante', ...
            ['current_A praticamente CONSTANTE (std=%.2e A) nos %d pontos observados: ' ...
             'Rint fica matematicamente indeterminado (nao ha variacao de corrente para ' ...
             'separar o efeito de Voc do de Rint na queda de tensao). Isso e esperado numa ' ...
             'janela de teste curta/sintetica com um unico ponto de operacao -- nao e como ' ...
             'calibrar Rint de verdade. Precisa de um trecho do CSV com corrente variando ' ...
             '(idealmente cobrindo carga e descarga em niveis diferentes).'], std_I, sum(ok));
    end
    if Rint_cal <= 0
        error('montar_fontes:bateriaRintNegativo', ...
            ['Rint calibrado = %.5f ohm (nao positivo): mesmo separando a deriva temporal ' ...
             'de Voc, a regressao nao encontra queda de tensao coerente com a corrente. Com ' ...
             'so %d pontos em 10 min isso pode ser ruido -- precisa de mais pontos e/ou ' ...
             'maior variacao de corrente para identificar Rint com confianca.'], Rint_cal, sum(ok));
    end
    if R2 < 0.5
        warning('montar_fontes:bateriaCalibFraca', ...
            ['Ajuste com deriva temporal: R2=%.2f (Rint=%.5f ohm). Ainda fraco, mas Rint ' ...
             'saiu positivo e fisicamente plausivel -- prosseguindo com ele. Com mais dados ' ...
             '(2h completas) essa calibracao deve melhorar; reavalie R2 quando trocar o CSV.'], ...
             R2, Rint_cal);
    end

    I_dis = I_ext(ok & I_ext > 0); V_dis = V_ext(ok & I_ext > 0);
    I_chg = I_ext(ok & I_ext < 0); V_chg = V_ext(ok & I_ext < 0);
    if isempty(I_dis) || isempty(I_chg)
        error('montar_fontes:bateriaSemAmbosSentidos', ...
            ['bateria.csv precisa ter pontos de carga E descarga (current_A ' ...
             'positivo e negativo) para calibrar eta_descarga e eta_carga ' ...
             'separadamente. Encontrados: %d descarga, %d carga.'], numel(I_dis), numel(I_chg));
    end
    eta_descarga_cal = median(V_dis ./ Voc_cal);
    eta_carga_cal    = median(Voc_cal ./ V_chg);
    fprintf(['[bateria] calibracao: Voc=%.2f V, Rint=%.5f ohm (R2=%.3f) | ' ...
             'eta_descarga=%.4f, eta_carga=%.4f (de %d/%d pontos)\n'], ...
             Voc_cal, Rint_cal, R2, eta_descarga_cal, eta_carga_cal, numel(I_dis), numel(I_chg));

    fontes(end+1) = contrato_fonte('nome','bateria', 'tipo','armazenamento', ...
        'P_max_unid_kW', Pdis_max, 'P_min_unid_kW', Pchg_max, ...
        'eta', arch.conv.eta_dc2, 'eta_carga', eta_carga_cal, 'eta_descarga', eta_descarga_cal, ...
        'E_kWh', arch.bat.Q_kWh, ...            % PENDENTE: ver nota abaixo
        'SOC_ini', SOC_ini_csv, ...              % agora vem do CSV (soc_percent)
        'SOC_min', arch.bat.SOC_min, 'SOC_max', arch.bat.SOC_max, ...  % PENDENTES: ver nota abaixo
        'SOC_alvo', SOC_ini_csv, ...
        'c_deg_rs_kWh', econ.c_deg_bateria_rs_kWh);
    else
        fprintf('[bateria] incluir_bateria=false -- fonte pulada, despacho roda sem ela.\n');
    end
end

% ----------------------------------------------------------------- locais
function t = tempo_csv(T, col)
    v = T{:, strcmpi(strtrim(string(T.Properties.VariableNames)), col)};
    if isdatetime(v), t = v; else, t = datetime(string(v)); end
    t = t(:);
end

function c = custo_por_kwh(custo_rs, energia_kwh)
    den = energia_kwh; den(~isfinite(den) | den <= 1e-9) = NaN;
    c = custo_rs ./ den;
    if all(isnan(c)), c = zeros(size(custo_rs)); return; end
    c(isnan(c)) = median(c(~isnan(c)));
end

function v = mediana_positiva(x)
    if isempty(x), v = 0; return; end
    pos = x(isfinite(x) & x > 0);
    if isempty(pos), v = 0; else, v = median(pos); end
end

function diag_cobertura(nome, tn, t_min)
% Avisa CEDO se a janela do CSV (tn, apos alinhar por t0_datetime) nao
% cobre a janela de simulacao (t_min) -- essa e a causa mais comum de
% "0 pontos validos" mais adiante: nao e falta de dado na coluna, e
% desalinhamento de t0_datetime (main.m) com o instante real do CSV.
    tn = tn(~isnan(tn));
    if isempty(tn)
        warning('montar_fontes:tempoIlegivel', ...
            ['Fonte "%s": a coluna de tempo nao pode ser interpretada como data/hora ' ...
             '(tudo virou NaT/NaN). Se o CSV usa tempo relativo (segundos ou minutos ' ...
             'desde o inicio, nao um timestamp absoluto), tempo_csv.m precisa ser ' ...
             'ajustado para esse formato em vez de tentar datetime(string(v)).'], nome);
        return;
    end
    cobre = tn(1) <= t_min(1) + 1e-6 && tn(end) >= t_min(end) - 1e-6;
    sobrepoe = tn(end) >= t_min(1) && tn(1) <= t_min(end);
    if ~sobrepoe
        warning('montar_fontes:semSobreposicao', ...
            ['Fonte "%s": janela do CSV [%.1f, %.1f] min NAO tem NENHUMA sobreposicao ' ...
             'com a janela de simulacao [%.1f, %.1f] min (tempo relativo ao t0_datetime ' ...
             'passado a montar_fontes). Toda serie desta fonte vira NaN -> 0 (ou erro, no ' ...
             'caso da bateria). Suspeito nº1: cenario_t0_datetime em main.m nao corresponde ' ...
             'ao instante inicial real deste CSV -- confira o primeiro timestamp do arquivo.'], ...
             nome, tn(1), tn(end), t_min(1), t_min(end));
    elseif ~cobre
        warning('montar_fontes:coberturaParcial', ...
            ['Fonte "%s": janela do CSV [%.1f, %.1f] min cobre so PARTE da janela de ' ...
             'simulacao [%.1f, %.1f] min. Os instantes fora ficam NaN -> tratados como ' ...
             'indisponibilidade nessa fonte.'], nome, tn(1), tn(end), t_min(1), t_min(end));
    end
end

function y = interp_clamp(curva, x)
% Interpola na curva empirica (x,y) construida a partir do CSV, com
% CLAMPING nas bordas em vez de extrapolar -- mesma filosofia do resto do
% projeto: nunca inventar valor fora do que foi observado. Fora da faixa
% [min(x_obs), max(x_obs)], usa o valor da borda mais proxima.
    if numel(curva.x) == 1
        y = curva.y(1); return;
    end
    x = min(max(x, curva.x(1)), curva.x(end));
    y = interp1(curva.x, curva.y, x, 'linear');
end