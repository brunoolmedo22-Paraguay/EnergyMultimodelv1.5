"""SEEDS2 — Piso 3C-2: Model Predictive Control de horizonte recedente (M23) do EMS ``milp_mpc_v1``.

Primeiro laço fechado MPC cientificamente reproduzível. NÚCLEO só com a biblioteca padrão (como 3A/3C-0/3C-1): não
importa Pyomo, HiGHS, Streamlit nem ``seeds2``; a resolução de cada janela passa por um ADAPTADOR explícito
(``adaptador_milp.ResolvedorMILP3C1``) que importa ``ems_v2.milp.solver_3c1`` só no momento da chamada.

Módulos:

* ``contrato``      — configuração versionada da missão (identidade, malha N/m/K_M/H_f, modo experimental, rótulo de
  informação, políticas terminal/aceitação/falhas/revisões tardias), sem valores padrão;
* ``relogio``       — janelas τ_k, N_k, m_k (último bloco curto), contador global monotônico, política terminal;
* ``observacoes``   — K6: livro de observações APPEND-ONLY por recurso/grandeza (tempo físico × recepção, eventos,
  sequência, revisões, conflitos, cadeia SHA-256, cortes selados) e instantâneo informacional causal;
* ``previsao``      — pedido de previsão por janela e validação causal do ``ConjuntoPrevisao`` (vínculo ao instantâneo);
* ``provedores``    — provedores SINTÉTICOS reproduzíveis (tabela declarada; correção por observação; oráculo de ablação);
* ``entorno``       — protocolo de passo do entorno (comando → confirmação/observações) e planta ALGÉBRICA simulada;
* ``janela``        — construção da entrada 3C-1 de cada janela (previsão + estado EXECUTADO + memória transportada);
* ``adaptador_milp``— adaptador explícito para ``resolver_3c1`` (import tardio);
* ``orquestrador``  — ``ControladorMPC`` (decidir → emitir → conciliar → fechar) e o laço simulado (modo 1);
* ``registro``      — registros SELADOS por janela e da missão (cadeia verificável; custo realizado ≠ planejado);
* ``persistencia``  — gravação exclusiva/atômica da evidência e retomada verificada;
* ``auditoria``     — auditoria temporal/causal/contábil INDEPENDENTE do solver e teste de não antecipatividade;
* ``metricas`` / ``comparadores`` — indicadores científicos e comparação de missões em condições comparáveis;
* ``experimentos``  — experimentos E1–E8 sobre as fixtures ``ems_v2.fixtures_3c2`` (exigem Pyomo/HiGHS ao executar).

Rótulo obrigatório: simulação causal de laço fechado ALGÉBRICA — o executor é o dublê 3C-1, não um modelo físico da
planta. Valor futuro (3C-4) não é implementado nem contabilizado. Nada aqui é integrado à aplicação.
"""
from __future__ import annotations

MPC_VERSAO = "3C-2"
ESQUEMA_MPC = 1
ESTADO_MOTOR_3C2 = "experimental_mpc_recedente_laco_fechado_algebrico"
ROTULO_MPC = ("simulação causal de laço fechado ALGÉBRICA (dublê 3C-1) — sintético; não é validação física da "
              "planta nem controle de equipamentos reais")

__all__ = ["ESQUEMA_MPC", "ESTADO_MOTOR_3C2", "MPC_VERSAO", "ROTULO_MPC"]
