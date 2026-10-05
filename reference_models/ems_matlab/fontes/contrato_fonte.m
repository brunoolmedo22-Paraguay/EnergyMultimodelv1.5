function f = contrato_fonte(varargin)
%CONTRATO_FONTE Interface UNICA entre a plataforma de modelagem e o
%otimizador. O otimizador nao conhece FC, bateria, termica ou vento --
%conhece apenas objetos que obedecem a este contrato.
%
%TODA fonte e MODULAR: composta de n_unid unidades identicas que podem ser
%ligadas ou desligadas individualmente. Termica e vento sao o caso n_unid=1.
%Um MFCS de 4 stacks e n_unid=4. O otimizador decide, a cada passo, QUANTAS
%unidades ficam ligadas (inteiro) e QUANTO entregam (continuo) -- sem saber
%o que ha dentro de cada unidade.
%
%---------------------------------------------------------------- CAMPOS
%OBRIGATORIOS
%  nome            char
%  tipo            'geracao' | 'nao_despachavel' | 'armazenamento'
%  P_max_unid_kW   (Nt,1) teto de UMA unidade ligada, por instante
%                  0 num instante = unidade indisponivel ali
%  eta             eficiencia do conversor dessa fonte ate o barramento
%
%MODULARIDADE (default = 1 unidade sempre ligada)
%  n_unid          numero de unidades instaladas. default 1
%  n_ini           unidades ligadas no instante inicial. default n_unid
%  dn_max          variacao maxima de unidades por passo. default Inf.
%                  Generaliza a vizinhanca truncada de mld_fc_estado.m:
%                  dn_max=1 reproduz o branch-and-bound de 3 candidatos.
%  P_min_unid_kW   (Nt,1) piso de UMA unidade ligada (tecnico minimo).
%                  default zeros. >0 e o que torna a decisao inteira
%                  nao-trivial: com n ligadas, o piso total e n*P_min_unid.
%  c_start_unid_rs custo de ligar UMA unidade. default 0
%
%CUSTO -- o campo que faz a escolha de n_unid ser informada
%  c_var_rs_kWh    (Nt , n_unid) MATRIZ. Coluna n = custo por kWh entregue
%                  no instante t COM n UNIDADES LIGADAS. E aqui que a curva
%                  de eficiencia da plataforma entra, ja convertida em moeda.
%                  Aceita (Nt,1) por compatibilidade: replica em todas as
%                  colunas, mas emite aviso -- nesse caso o otimizador fica
%                  indiferente a eficiencia e sempre escolhe o menor n viavel.
%
%RELATORIO -- opcional, NAO usado pela otimizacao, so por relatorio_despacho.m
%  qtd_fisica_por_kWh  (Nt , n_unid) MATRIZ. Quantidade fisica (kg de H2,
%                  litros de diesel, kgCO2...) por kWh entregue, com n
%                  unidades ligadas. Ignorado se qtd_fisica_fn for dado.
%  qtd_fisica_unidade  char, rotulo para o relatorio (ex: 'kg_H2', 'L_diesel').
%
%CUSTO DINAMICO (alternativa a matriz, quando o custo por kWh depende da
%POTENCIA de operacao, nao so de quantas unidades estao ligadas -- caso da
%FC, cuja eficiencia varia com a carga por stack)
%  custo_fn        function_handle @(P_kW_total, n_unid_ligadas, indice_t)
%                  -> R$/kWh. Quando dado, TEM PRIORIDADE sobre
%                  c_var_rs_kWh: o otimizador avalia o custo na potencia
%                  REAL que esta testando em cada iteracao, em vez de um
%                  ponto de operacao fixo assumido de antemao (que e uma
%                  aproximacao arbitraria, nao um dado). c_var_rs_kWh fica
%                  opcional quando custo_fn e dado.
%  qtd_fisica_fn   mesma assinatura, R$/kWh trocado por unidade fisica/kWh.
%                  Usado so pelo relatorio, nunca pela otimizacao.
%
%SO PARA tipo='armazenamento'   (n_unid e forcado a 1)
%  E_kWh, SOC_ini, SOC_min, SOC_max, SOC_alvo, eta_carga, eta_descarga
%  c_deg_rs_kWh    custo por kWh movimentado. default 0
%  P_min_unid_kW   aqui e o limite de CARGA, valor NEGATIVO
%
%--------------------------------------------------------------- EXEMPLOS
%  % MFCS de 4 stacks de 140 kW, piso tecnico de 10%, custo por configuracao
%  fc = contrato_fonte('nome','mfcs', 'tipo','geracao', ...
%        'n_unid', 4, 'n_ini', 2, 'dn_max', 1, ...
%        'P_max_unid_kW', 140*teto_disp, 'P_min_unid_kW', 14*ones(Nt,1), ...
%        'c_var_rs_kWh', C, ...      % Nt x 4, vinda da curva de eficiencia
%        'c_start_unid_rs', 12, 'eta', 0.97);
%
%  % Termica: 1 unidade, must-run via piso
%  tg = contrato_fonte('nome','termica', 'tipo','geracao', ...
%        'P_max_unid_kW', Pmax_kW, 'P_min_unid_kW', inflex_kW, ...
%        'c_var_rs_kWh', c_kWh, 'c_start_unid_rs', 4200, ...
%        'ramp_kW_min', 8.5, 'eta', 0.97);

    p = inputParser;
    addParameter(p, 'nome', '');
    addParameter(p, 'tipo', 'geracao');
    addParameter(p, 'P_max_unid_kW', []);
    addParameter(p, 'P_min_unid_kW', []);
    addParameter(p, 'eta', 1.0);
    addParameter(p, 'n_unid', 1);
    addParameter(p, 'n_ini', []);
    addParameter(p, 'dn_max', inf);
    addParameter(p, 'c_var_rs_kWh', []);
    addParameter(p, 'custo_fn', []);
    addParameter(p, 'qtd_fisica_por_kWh', []);
    addParameter(p, 'qtd_fisica_fn', []);
    addParameter(p, 'qtd_fisica_unidade', '');
    addParameter(p, 'c_start_unid_rs', 0);
    addParameter(p, 'ramp_kW_min', inf);
    addParameter(p, 'E_kWh', []);
    addParameter(p, 'SOC_ini', []);
    addParameter(p, 'SOC_min', 0);
    addParameter(p, 'SOC_max', 1);
    addParameter(p, 'SOC_alvo', []);
    addParameter(p, 'eta_carga', 1.0);
    addParameter(p, 'eta_descarga', 1.0);
    addParameter(p, 'c_deg_rs_kWh', 0);
    parse(p, varargin{:});
    f = p.Results;

    if isempty(f.nome),          error('contrato_fonte:nome','Campo "nome" obrigatorio.'); end
    if isempty(f.P_max_unid_kW), error('contrato_fonte:Pmax','Fonte "%s": P_max_unid_kW obrigatorio.', f.nome); end

    f.P_max_unid_kW = f.P_max_unid_kW(:);
    Nt = numel(f.P_max_unid_kW);
    f.armazena = strcmpi(f.tipo,'armazenamento');

    if f.armazena
        f.n_unid = 1;
        if isempty(f.P_min_unid_kW), error('contrato_fonte:armazPmin', ...
            'Fonte "%s": armazenamento exige P_min_unid_kW (limite de carga, negativo).', f.nome); end
    end
    if isempty(f.P_min_unid_kW), f.P_min_unid_kW = zeros(Nt,1); end
    if isscalar(f.P_min_unid_kW), f.P_min_unid_kW = f.P_min_unid_kW*ones(Nt,1); end
    f.P_min_unid_kW = f.P_min_unid_kW(:);
    if isempty(f.n_ini), f.n_ini = f.n_unid; end

    % ---------------- custo: matriz Nt x n_unid, OU funcao dinamica ----------------
    if ~isempty(f.custo_fn) && ~isa(f.custo_fn,'function_handle')
        error('contrato_fonte:custoFnTipo', 'Fonte "%s": custo_fn deve ser function_handle.', f.nome);
    end
    if isempty(f.c_var_rs_kWh)
        f.c_var_rs_kWh = zeros(Nt, f.n_unid);   % placeholder; ignorado se custo_fn existir
    elseif isscalar(f.c_var_rs_kWh)
        f.c_var_rs_kWh = f.c_var_rs_kWh * ones(Nt, f.n_unid);
    elseif isvector(f.c_var_rs_kWh)
        if f.n_unid > 1 && isempty(f.custo_fn)
            warning('contrato_fonte:custoSemConfig', ...
                ['Fonte "%s" tem %d unidades mas custo dado como vetor: o custo ' ...
                 'por kWh nao depende de quantas unidades estao ligadas. O ' ...
                 'otimizador ficara CEGO ao ganho de eficiencia e escolhera ' ...
                 'sempre o menor n viavel. Para a escolha de n ser informada, ' ...
                 'entregue custo_fn (recomendado, se o custo depende da ' ...
                 'potencia de operacao) ou c_var_rs_kWh como matriz %dx%d.'], ...
                 f.nome, f.n_unid, Nt, f.n_unid);
        end
        f.c_var_rs_kWh = repmat(f.c_var_rs_kWh(:), 1, f.n_unid);
    end

    % ---------------- validacoes ----------------
    if size(f.c_var_rs_kWh,1) ~= Nt || size(f.c_var_rs_kWh,2) ~= f.n_unid
        error('contrato_fonte:custoDim', ...
            'Fonte "%s": c_var_rs_kWh deve ser %dx%d, veio %dx%d.', ...
            f.nome, Nt, f.n_unid, size(f.c_var_rs_kWh,1), size(f.c_var_rs_kWh,2));
    end

    % ---------------- quantidade fisica: mesma forma do custo ----------------
    if ~isempty(f.qtd_fisica_fn) && ~isa(f.qtd_fisica_fn,'function_handle')
        error('contrato_fonte:qtdFisicaFnTipo', 'Fonte "%s": qtd_fisica_fn deve ser function_handle.', f.nome);
    end
    if ~isempty(f.qtd_fisica_por_kWh)
        if isscalar(f.qtd_fisica_por_kWh)
            f.qtd_fisica_por_kWh = f.qtd_fisica_por_kWh * ones(Nt, f.n_unid);
        elseif isvector(f.qtd_fisica_por_kWh)
            f.qtd_fisica_por_kWh = repmat(f.qtd_fisica_por_kWh(:), 1, f.n_unid);
        end
        if size(f.qtd_fisica_por_kWh,1) ~= Nt || size(f.qtd_fisica_por_kWh,2) ~= f.n_unid
            error('contrato_fonte:qtdFisicaDim', ...
                'Fonte "%s": qtd_fisica_por_kWh deve ser %dx%d, veio %dx%d.', ...
                f.nome, Nt, f.n_unid, size(f.qtd_fisica_por_kWh,1), size(f.qtd_fisica_por_kWh,2));
        end
        if isempty(f.qtd_fisica_unidade)
            warning('contrato_fonte:qtdFisicaSemUnidade', ...
                'Fonte "%s": qtd_fisica_por_kWh dado sem qtd_fisica_unidade (rotulo).', f.nome);
        end
    end
    if any(~isfinite(f.P_max_unid_kW)) || any(~isfinite(f.P_min_unid_kW))
        error('contrato_fonte:naoFinito', ...
            ['Fonte "%s": envelope com NaN/Inf. Fora da janela coberta pelo modelo ' ...
             'externo declare P_max_unid=0 (indisponivel), nunca NaN -- ' ...
             'extrapolar envelope inventa capacidade.'], f.nome);
    end
    if ~f.armazena && any(f.P_min_unid_kW > f.P_max_unid_kW + 1e-9)
        error('contrato_fonte:pisoTeto', ...
            ['Fonte "%s": piso > teto por unidade em %d instantes. Se vieram de ' ...
             'colunas diferentes, confira a unidade (MW vs kW) das duas.'], ...
             f.nome, sum(f.P_min_unid_kW > f.P_max_unid_kW + 1e-9));
    end
    if f.n_ini < 0 || f.n_ini > f.n_unid
        error('contrato_fonte:nIni','Fonte "%s": n_ini=%d fora de [0, %d].', f.nome, f.n_ini, f.n_unid);
    end
    if f.armazena && ~isempty(f.SOC_ini) && (f.SOC_ini < f.SOC_min || f.SOC_ini > f.SOC_max)
        error('contrato_fonte:soc','Fonte "%s": SOC_ini=%.3f fora de [%.3f, %.3f].', ...
            f.nome, f.SOC_ini, f.SOC_min, f.SOC_max);
    end
    if strcmpi(f.tipo,'nao_despachavel') && any(f.P_min_unid_kW > 0)
        warning('contrato_fonte:naoDespMustRun', ...
            ['Fonte "%s" e nao-despachavel mas tem piso > 0: isso proibe ' ...
             'curtailment e pode inviabilizar o balanco em horas de sobra.'], f.nome);
    end

    % envelope efetivo para uma dada configuracao n (usado pelo otimizador)
    f.envelope = @(n, h) deal(max(n,0)*f.P_min_unid_kW(h), max(n,0)*f.P_max_unid_kW(h));
end