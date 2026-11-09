"""SEEDS2 — Piso 3C-4: EMS HIERÁRQUICO MILP–MPC (planejamento de longo prazo, custo de continuação e valor futuro).

Núcleo só com a biblioteca padrão (como 3A/3C-0…3C-3): nenhum módulo deste subpacote importa Pyomo, HiGHS, Streamlit
nem ``seeds2``. O MILP do perfil vive em ``ems_v2/milp/*_3c4.py`` (composição sobre o construtor 3C-3, inalterado) e é
alcançado SÓ por adaptadores com import tardio.

Dois níveis coordenados (ver ``docs/ems_v2/FORMULACAO_3C4.md``):

* **planejador de longo prazo** (``planejador``) — a partir do estado EXECUTADO em τ_k, das previsões e tarifas
  causalmente disponíveis e do PCC 3C-3, resolve o horizonte longo H_L (plano de referência, nunca aplicado) e estima,
  por REOTIMIZAÇÕES PARAMÉTRICAS auditadas, a função de custo de continuação V_k^tail(x) na fronteira terminal do MPC
  curto (k + N_k), condicionada ao estado discreto terminal dos geradores (modo) e linear por partes na energia
  armazenada;
* **MPC curto** (``mpc``) — o laço recedente 3C-3 sem alterações, cujo MILP de janela recebe o termo
  ``custo_futuro_estimado`` = V̂(x_{k+N}) declarado por um ``SinalValorFuturo`` selado e verificado (identidade,
  fronteira, causalidade, domínio, modos, memória), sem somar duas vezes os intervalos de horizontes sobrepostos.

Módulos: ``contrato`` (termo terminal, sinal, entrada embrulho ``EntradaHierarquica3C4``, configuração do
planejador), ``valor`` (avaliação exata independente das representações), ``auditor`` (auditor INDEPENDENTE do termo
terminal, compondo ``auditar_3c3``), ``planejador``, ``mpc`` (controlador hierárquico, registros de coordenação,
retomada), ``auditoria`` (auditoria integral da missão), ``comparadores`` e ``experimentos`` (H1–H18).

Rótulo obrigatório: o custo futuro é um INSTRUMENTO DE DECISÃO (estimativa do planejador sob as previsões de τ_k), nunca
um custo monetário incorrido nem receita realizada; nada aqui é integrado à aplicação (o EMS V1.6 continua sendo o
único motor operacional). Modelo algébrico agregado sobre fixtures/tarifas SINTÉTICAS.
"""
from __future__ import annotations

FORMULACAO_3C4 = "v1.1-3C-4"
ESQUEMA_3C4 = 1
ESTADO_MOTOR_3C4 = "experimental_milp_mpc_hierarquico_algebrico"
ROTULO_HIERARQUIA = ("EMS hierárquico ALGÉBRICO (planejador longo + MPC curto) — sintético; o custo futuro é uma "
                     "estimativa de decisão sob previsões causais, nunca custo realizado nem receita; não é validação "
                     "física nem desempenho de tempo real")

__all__ = ["ESQUEMA_3C4", "ESTADO_MOTOR_3C4", "FORMULACAO_3C4", "ROTULO_HIERARQUIA"]
