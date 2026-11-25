# Plano do bloco II — Fundamentação e desenvolvimento do SEEDS (slides 8–15 · 8:00)

Base: artigo final (`TCC_BRUNO_OLMEDO_COMPLETO_1.pdf`, Seções 3–5, Figuras 4.1 e 5.1–5.3), código (`models/`, `simulation/multimodel.py`,
`integracao_v2/`, `ems_v2/`) e roteiro (`guia/conteudo.py`). Tudo o que vai na tela sai do artigo; o código só confirma.

**Arco do bloco:** primeiro a teoria (8 → 11: o que cada peça faz), depois o SEEDS (12 → 15: como as peças foram juntadas).
Cada slide do SEEDS responde a um da teoria: 8 ↔ 13 (modelos → representação comum), 11 ↔ 14 (valor futuro → planejador),
9–10 ↔ 15 (MILP e MPC → verificação de cada janela).

| Nº | Título | Mensagem (o que a banca leva) | Na tela (fonte) | Ideia visual |
|---|---|---|---|---|
| 8 | Modelagem dos recursos energéticos (1:30) | Cada modelo físico entrega ao EMS só o que a decisão precisa. | FV: NOCT/Ross e correção térmica (eq. 1–2) → potência disponível · Eólica: curva do fabricante + densidade do ar (eq. 3) → potência disponível · Bateria: balanço EPRI e SOC (eq. 4–5) → energia, limites, eficiências · PEMFC: modelo eletroquímico de Altıntaş e Ertan [35], parametrizado por Chavez et al. [36] (trabalho anterior do autor), Faraday (eq. 6–7) → curva de H₂ · PCC (eq. 8) → sentidos, limites, tarifas | 5 linhas com a cor de cada recurso: ícone · equação-chave bem diagramada · seta → «o que entrega ao EMS» |
| 9 | Programação linear inteira mista (MILP) (1:00) | «Quanto» e «liga ou não» no mesmo problema. | eq. 9 (contínuas v, binárias w) · eq. 11 balanço no barramento · eq. 12 bateria com ω (não carrega e descarrega juntas) · eq. 13 PEMFC: P_mín·u ≤ P ≤ P_máx·u, partidas y e paradas z · custo cresce com as binárias | duas cores: contínuas × binárias; três «interruptores» (ω, u, w importar/exportar) sobre o barramento |
| 10 | Controle preditivo baseado em modelo (MPC) (1:00) | Janela curta aplicada aos poucos — e míope no fim. | eq. 15 com V_f em destaque · resolve N, aplica m, atualiza o estado, repete · «Sem custo terminal ou reserva mínima, a otimização tende a reduzir a energia armazenada ao fim do horizonte» (Seção 4.2) | janelas deslizantes empilhadas sobre a linha do tempo (1º bloco aplicado) + trajetória planejada da energia caindo no fim da janela (esquemático) |
| 11 | Coordenação hierárquica e valor futuro (1:00) | O custo futuro da água, aplicado à energia armazenada. | eq. 16–17 (Bellman; janela + custo de continuação) · eq. 18 μ = −∂V/∂E [R$/kWh] · com decisões inteiras V pode ser não convexa ou descontínua e a derivada pode não existir | volta a curva «custo futuro» do slide 4, agora com o eixo «energia armazenada E»; tangente = μ |
| 12 | Arquitetura do SEEDS (1:00) | Trocar um equipamento muda a instância, não a formulação. | Figura 5.1 em três camadas: Modularidade (modelos e catálogos → configuração com revisões → cenário operativo) · Integração (representação comum → verificação de compatibilidade) · EMS hierárquico (planejador → MPC → malha fechada → resultados e evidência), com os retornos (estado executado, pendências) | Figura 5.1 redesenhada na identidade; opcional: miniaturas reais do aplicativo (Anexo A: inventário, planta) |
| 13 | Representação energética comum (1:00) | Tudo no mesmo barramento, em kW líquidos e na mesma malha — nada presumido. | Renováveis → limite superior exógeno (média das amostras, sem interpolação; o que sobra é vertimento) · Bateria → balanço (eq. 4), cada banco separado · PEMFC → curva H₂ linear por partes, gerada uma vez e aceita só dentro do erro; modelo dinâmico confere depois · PCC → sentidos, limites e tarifas declarados (ausência ≠ ilimitado) · verificação: representável · excluído · impeditivo | barramento vertical do slide 7 com o que cada recurso entrega; convenção de sinais; três estados da verificação |
| 14 | Gerenciamento energético hierárquico no SEEDS (1:00) | O planejador diz ao MPC quanto vale a energia no fim da janela. | Figura 5.2 simplificada: planejamento (H_L) → plano longo nunca aplicado → reotimizações paramétricas por modo → sinal de valor futuro (função linear por partes no domínio viável) → MPC verifica o sinal → MILP da janela = operação + custo futuro → aplica m → estado executado · por que não os duais do MILP · custo futuro registrado à parte, nunca somado ao realizado | duas raias (planejamento × operação) com a seta azul do sinal; a curva V(E) montada por pontos |
| 15 | Verificação e fluxo de execução (0:30) | Cada decisão é conferida; cada resultado, rastreável. | MILP (Pyomo 6.10.1 + HiGHS 1.15.1) → verificação independente do solver → aplicação → auditoria integral · Figura 5.3: Etapas 0–4 (criação da microrrede, inicialização, previsões, estratégia EMS, execução) | as cinco etapas em cartões (as mesmas da demonstração) + a cadeia de verificação |

## Divergências encontradas (decidir antes de usar)

- **Pontos de validação da curva H₂:** o artigo diz «500 pontos que não participaram de sua construção» (Seção 7.4); o padrão do código é
  400 pontos médios + 2 extremos (`integracao_v2/curva_h2.py`). Confirmar a origem dos 500 antes de citá-los.
- **15 vértices** é resultado do refinamento adaptativo (alvo 0,1 %, máx. 48), não um parâmetro fixo. Erro máx. 0,087 % e subestimação 0
  conferem com `docs/ems_v2/INTEGRACAO_3DA2H.md`.
- **7 → 217 variáveis, 105 binárias, 168 janelas, 14 missões** estão no artigo (Tabela 7.2, Seção 7.4), mas nada no repositório gera essa
  tabela (vão para o bloco V; citar o artigo).
- **Eficiência de conversão FV** é declarada pelo usuário, não modelada (o artigo diz isso — manter a palavra «declarada»).
