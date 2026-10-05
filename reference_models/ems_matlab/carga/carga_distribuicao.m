% =========================================================================
% Script: Leitura de Dados da COPEL e Geração de Curva de Carga Diária
% =========================================================================

clear; clc; close all;

nome_arquivo = 'b0418edb-038d-4fde-b624-c318d376a734_útil.csv'; % Certifique-se que o nome do arquivo está correto

% 1. Detectar as opções de importação automática do arquivo
opts = detectImportOptions(nome_arquivo, 'FileType', 'text');
opts.VariableNamingRule = 'preserve';

% 2. Corrigir o erro do MATLAB configurando a Demanda (VlrDmd)
% O tipo correto no MATLAB é 'double' e o separador decimal é a vírgula ','
opts = setvaropts(opts, 'VlrDmd', 'Type', 'double', 'DecimalSeparator', ',');

% Garantir que os horários sejam lidos como texto e depois convertidos para duration
opts = setvaropts(opts, {'HorInicial', 'HorFinal'}, 'Type', 'char');

% 3. Ler o arquivo CSV usando as configurações ajustadas
dados = readtable(nome_arquivo, opts);

% 4. Definir os Filtros de Escopo para isolar apenas UM cenário/dia
companhia_alvo = 'COPEL';
subgrupo_alvo  = 'B1';            % Ex: B1, B2, B3
simulacao_alvo = 'Simulação 5';    % Ex: Simulação 3, Simulação 5
tipo_dia_alvo  = 'Dia Útil';      % Opções: 'Dia Útil', 'Sábado', 'Domingo'

% 5. Aplicar os filtros na tabela com os nomes exatos das colunas
dados_filtrados = dados(strcmp(dados.SigCcs, companhia_alvo) & ...
                        strcmp(dados.NomSubGrupoTarifario, subgrupo_alvo) & ...
                        strcmp(dados.DscPrcCal, simulacao_alvo) & ...
                        strcmp(dados.DscTipoDia, tipo_dia_alvo), :);

% Verificar se o filtro retornou registros
if isempty(dados_filtrados)
    error('Nenhum dado encontrado para os filtros selecionados. Verifique os termos digitados.');
end
   

% 5. Aplicar os filtros
dados_filtrados = dados(strcmp(dados.SigCcs, companhia_alvo) & ...
                        strcmp(dados.NomSubGrupoTarifario, subgrupo_alvo) & ...
                        strcmp(dados.DscPrcCal, simulacao_alvo) & ...
                        strcmp(dados.DscTipoDia, tipo_dia_alvo), :);

if isempty(dados_filtrados)
    error('Nenhum dado encontrado para os filtros selecionados.');
end

% 6. Organizar cronologicamente os intervalos de 15 minutos do dia
dados_filtrados = sortrows(dados_filtrados, 'HorInicial');

% 7. Converter as strings de horário para o formato 'duration' do MATLAB
horarios = duration(dados_filtrados.HorInicial);
demanda_kw = dados_filtrados.VlrDmd;

% =========================================================================
% SALVAMENTO: Exportação das variáveis para arquivo .mat (96 Pontos)
% =========================================================================

% Criar uma tabela organizada para facilitar o reuso futuro
tabela_96p = table(horarios, demanda_kw, ...
    'VariableNames', {'Horario', 'Demanda_kW'});

% Salvar no arquivo 'curva_carga_96h.mat' as variáveis soltas e estruturadas
save('curva_carga_96h.mat', 'horarios', 'demanda_kw', 'tabela_96p');
fprintf('Sucesso! Arquivo "curva_carga_96h.mat" salvo com os %d pontos do dia.\n', length(demanda_kw));

% =========================================================================
% PLOTAGEM DO GRÁFICO (96 Pontos)
% =========================================================================
figure('Color', 'w');
plot(horarios, demanda_kw, 'LineWidth', 2.5, 'Color', [0 0.4470 0.7410]);
grid on;

% Customização e Títulos do Gráfico
title(sprintf('Curva de Carga Real - %s (%s)', companhia_alvo, simulacao_alvo), 'FontSize', 12);
subtitle(sprintf('Subgrupo Tarifário: %s | Tipo de Dia: %s (%d Pontos)', subgrupo_alvo, tipo_dia_alvo, length(demanda_kw)), 'FontSize', 10);
xlabel('Horário do Dia (Intervalos de 15 min)', 'FontSize', 11);
ylabel('Demanda Média (kW)', 'FontSize', 11);

% Forçar o eixo X a exibir o formato de horas e minutos (HH:MM)
xtickformat('hh:mm');

