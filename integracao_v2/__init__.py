"""Piso 3D-A — camada de INTEGRAÇÃO operacional do motor experimental ``milp_mpc_v1`` (pacote ``ems_v2``) com o SEEDS2.

É o ÚNICO pacote fora de ``ems_v2/`` que importa o motor experimental, e o único ponto em que o Centro de Operação
(``seeds2``) alcança o EMS hierárquico MILP–MPC. Dependências num só sentido::

    seeds2 (aplicação, sem ciência)  ──►  integracao_v2 (coordenação)  ──►  ems_v2 (motor auditado, INALTERADO)
                                                   │
                                                   └──►  seeds2.microgrid / seeds2.operation (leitura do cenário,
                                                         gravação da rodada SÓ pelo ``MicrogridStore``)

Nada aqui altera a formulação MILP, o planejador, o MPC, o custo futuro, políticas numéricas, fixtures ou referências
do ``ems_v2`` (o pacote ``ems_v2/`` é byte a byte o de ``main``), nem o EMS V1.6. A integração só:

* lê o inventário POR DISPOSITIVO (``ems_v2.ponte_seeds2.leitor``) e a versão IMUTÁVEL do cenário;
* acrescenta ao instantâneo as DECLARAÇÕES explícitas da estratégia MILP–MPC do cenário (com procedência por campo) —
  nenhum parâmetro físico ausente é preenchido;
* projeta pela ponte 3C-0/3C-1 (``montar_entrada_3c1``), embrulha no perfil 3C-3 (PCC/tarifas declarados) e executa o
  ``ControladorMPCHierarquico`` (3C-4) contra a planta ALGÉBRICA de ensaio com Pyomo/HiGHS reais;
* grava a evidência selada e as vistas derivadas em ``scenario_runs``/``scenario_run_data`` (JSON/CSV/ZIP da whitelist
  do pacote ``seeds2-study`` v1) e reabre a rodada SEM chamar o otimizador (reauditoria independente, sem solver).

ESCOPO CIENTÍFICO: simulação OFFLINE de laço fechado, algébrica, em contexto de ENSAIO. Não é controle de hardware,
telemetria SCADA, validação física nem fatura real. Limites e contradições: ``docs/ems_v2/INTEGRACAO_3DA.md``.

Módulos: ``estrategia`` (bloco ``milp_mpc`` do cenário; só biblioteca padrão), ``montagem`` (cenário → contratos do
motor), ``preflight`` (preflight V2, distinto do V1.6), ``execucao`` (runner), ``registro`` (evidência persistida e
reabertura), ``ui`` (controles mínimos Streamlit; importado só pela interface).
"""
from __future__ import annotations

from .estrategia import CHAVE_BLOCO, CHAVE_MOTOR, MOTOR_V16, MOTOR_V2, MOTORES, motor_selecionado

PISO = "3D-A"
__all__ = ["CHAVE_BLOCO", "CHAVE_MOTOR", "MOTOR_V16", "MOTOR_V2", "MOTORES", "PISO", "motor_selecionado"]
