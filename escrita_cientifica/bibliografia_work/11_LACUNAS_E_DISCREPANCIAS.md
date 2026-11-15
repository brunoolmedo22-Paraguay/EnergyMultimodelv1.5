# Achados, esclarecimentos e pendências

Revisão 01: a procedência própria PEMFC foi documentada e a associação indevida B1–CT-046 foi corrigida. Os IDs foram preservados para rastreabilidade.

## LAC0001 — Documental

Procedência PEMFC esclarecida: artigo próprio ENCOM de Chavez et al. documenta implementação e identificação baseada em Altıntaş–Ertan.

**Evidência:** REF0369, pp. 295–298; Tabelas I–II; coeficientes-base conferidos com parameters.py.

**Interpretação:** Omitir a contribuição própria e atribuir a adaptação diretamente a OTEKON.

**Encaminhamento:** Citar o artigo próprio como fonte imediata e OTEKON como base. Manter explícito o alcance de ajuste numérico às curvas de referência.

## LAC0002 — Alta

Tabela 3 de Zhang contém incompatibilidade interna tau2=R2C2.

**Evidência:** REF0147 p. 8; SOC 0,9: 354,8868 s calculado versus 89,7116 s impresso.

**Interpretação:** Reprodução de parâmetro publicado inconsistente ser apresentada como ausência de erro.

**Encaminhamento:** Conferir erratas/dados dos autores; não alterar o código nesta missão; documentar escolha e sensibilidade.

## LAC0003 — Esclarecida

COPEL B1 implementado e CT-046 de futura microrrede são finalidades distintas.

**Evidência:** Código carga_copel/Simulação 5 para B1; esclarecimento do autor sobre o futuro cenário CT-046.

**Interpretação:** A auditoria anterior associou indevidamente o perfil existente ao caso industrial proposto. Não há inconsistência identificada no código.

**Encaminhamento:** Manter B1 no seu uso atual; cadastrar e documentar CT-046 separadamente quando o novo cenário for implementado.

## LAC0004 — Alta

V2 FV usa NOCT e trata GHI como irradiância no plano do módulo.

**Evidência:** integracao_v2/renovaveis.py derivar_fv.

**Interpretação:** Atribuir ao despacho fidelidade de SDM, transposição ou inversor detalhado.

**Encaminhamento:** Descrever a hipótese e avaliar sensibilidade ou usar dados já no plano do módulo quando aplicável.

## LAC0005 — Alta

H2 é contabilizado sem dinâmica/limite de tanque no núcleo auditado.

**Evidência:** ems_v2/capabilities.py: estoque_h2 nao_suportado.

**Interpretação:** Concluir autonomia da embarcação sem orçamento de massa.

**Encaminhamento:** Apresentar consumo e verificar massa disponível externamente; não afirmar tanque otimizado.

## LAC0006 — Alta

Modelo equivalente Horizon usa dados de outro stack e área assumida.

**Evidência:** REF0359; h2_pemfc/docs/MODEL_CARD_HORIZON_APPROX.md.

**Interpretação:** Apresentar calibração equivalente como ensaio do fabricante/equipamento real.

**Encaminhamento:** Manter rotulagem de aproximação; obter dados do stack específico e registrar incerteza.

## LAC0007 — Alta

Manual Horizon não consultado externamente nesta missão.

**Evidência:** REF0360; specifications.csv aponta Tabela 4.2.

**Interpretação:** Declarar validação externa da rampa e das condições de partida.

**Encaminhamento:** Obter manual V1.3 legítimo; conferir 2 kW/s subida e 3,5 kW/s descida, limites e unidades.

## LAC0008 — Alta

Errata de De Soto identificada sem leitura de seu conteúdo.

**Evidência:** REF0319 e REF0320.

**Interpretação:** Tratar translação/extração SDM como reprodução integralmente conferida.

**Encaminhamento:** Ler a errata e cotejar as expressões implementadas antes da redação final.

## LAC0009 — Alta

Custo de continuação é aproximado; convexidade 2D é amostral.

**Evidência:** hierarquia/planejador.py e milp/modelo_3c4.py.

**Interpretação:** Afirmar função de valor global exata, SDDP ou prova global de convexidade.

**Encaminhamento:** Relatar domínio, modo, erro em validação e falta de garantia fora dos pontos consultados.

## LAC0010 — Alta

Estado inicial de 30 kW e cenário naval persistido não foram confirmados.

**Evidência:** Campos existem, mas a auditoria não acessa o banco pessoal de cenários do usuário.

**Interpretação:** Converter decisão de projeto em resultado ou configuração já executada.

**Encaminhamento:** Anexar versão do cenário e manifesto da rodada que efetivamente use estado ON/P_anterior=30 kW.

## LAC0011 — Alta

PCC não calcula fatura industrial completa nem fluxo elétrico AC.

**Evidência:** J_rede integra R$/kWh; sem termo explícito de demanda na formulação examinada.

**Interpretação:** Chamar custo de energia de redução da fatura total ou estabilidade elétrica.

**Encaminhamento:** Delimitar custo operacional e documentar termos tributários/tarifários realmente incluídos.

## LAC0012 — Média

Bateria de bancada tem clips; BESS MILP tem restrições e projeção apenas numérica no executor.

**Evidência:** models/battery_model.py e ponte/execucao.py.

**Interpretação:** Apresentar todas as camadas como mesmo modelo matemático.

**Encaminhamento:** Separar modelos, convenções, integradores e política de tolerância.

## LAC0013 — Média

A pressão do ar cancela no potencial Nernst implementado.

**Evidência:** PEMFCModel.nernst_voltage: pO2=0,21 p_air e denominador sqrt(p_air).

**Interpretação:** Atribuir sensibilidade direta de Nernst à pressão sem derivação.

**Encaminhamento:** Conferir equação original e condições; pressão ainda afeta termo de ativação.

## LAC0014 — Média

Curvas de pequenas eólicas incluem fontes arquivadas sem ensaio primário confirmado.

**Evidência:** REF0367; docs/eolica/RASTREABILIDAD_7_EQUIPOS.md.

**Interpretação:** Reclassificar arquivo secundário como curva certificada pelo fabricante.

**Encaminhamento:** Obter relatórios SWCC/NREL originais; respeitar status curve_analysis_only.

## LAC0015 — Média

A equação de saturação usa coeficientes que exigem identificação da revisão de Buck.

**Evidência:** models/wind_model.py _saturation_vapor_pressure_hpa.

**Interpretação:** Atribuir todos os coeficientes à publicação de 1981 sem confirmação.

**Encaminhamento:** Rastrear a revisão da expressão 18,678/234,5 antes de citar origem exata.

## LAC0016 — Média

Descrição do PR #24 está parcialmente desatualizada em relação aos arquivos presentes.

**Evidência:** PR draft inclui caderno_ui.py/folha_ui.py apesar da descrição B2 ainda não iniciado.

**Interpretação:** Usar narrativa do PR como estado consolidado do software.

**Encaminhamento:** Citar SHA e arquivos efetivos; manter telas do draft separadas de main.

## LAC0017 — Média

Térmica é funcional na bancada, mas custo M19/CVU não está integrado ao V2.

**Evidência:** integracao_v2/preflight.py NAO_REPRESENTAVEL.

**Interpretação:** Alegar otimização econômica V2 da térmica usando capacidade do legado.

**Encaminhamento:** Excluir essa alegação; manter tecnologia fora dos casos V2 enquanto a lacuna existir.

## LAC0018 — Média

Não foi reexecutada a suíte científica nem uma rodada de casos.

**Evidência:** Auditoria exclusivamente estática e bibliográfica.

**Interpretação:** Converter logs históricos do projeto em verificação independente desta missão.

**Encaminhamento:** Planejar ensaios próprios em tarefa separada, com SHA e dependências fixados.

## LAC0019 — Média

WoS/Scopus/Scholar e APIs abertas tiveram barreiras de acesso ou limitação de taxa.

**Evidência:** WoS 403; Scopus 403/Site Unavailable; Scholar 429/inacessível; OpenAlex e Semantic Scholar 429.

**Interpretação:** Afirmar busca nativa ou cobertura sistemática nessas bases.

**Encaminhamento:** Reexecutar consultas institucionais por acesso legítimo e exportar resultados para atualizar o corpus.

## LAC0020 — Média

C1–C4 variam a composição tecnológica e não isolam o efeito do EMS.

**Evidência:** Protocolo recebido e mapa de claims, seção 5.

**Interpretação:** Atribuir diferença entre C1 e C4 à hierarquia.

**Encaminhamento:** Comparar controladores em C4 idêntica, previsões e estados iniciais iguais, com e sem sinal futuro.
