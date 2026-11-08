"""SEEDS2 — fundações do EMS MILP–MPC experimental (Piso 3A).

Este pacote contém SOMENTE contratos canônicos, unidades, malha temporal, cálculo algébrico de referência,
auditor algébrico independente, registro declarativo de capacidades, fixtures sintéticas e o catálogo de símbolos
M01–M23 (+ adenda v1.1). **Não há solver, não há despacho, não há integração com a interface.** Pyomo/HiGHS
pertencem ao Piso 3B (não autorizado nesta etapa).

Regras do pacote:

* nenhuma importação de Streamlit, Pyomo, HiGHS, ``seeds2``, ``ems_integration`` ou dos modelos científicos
  (verificado em ``tests/ems_v2/test_isolamento.py``); só a biblioteca padrão do Python;
* o EMS V1.6 (``legacy_v16``, pacote ``ems_integration``) continua sendo o ÚNICO motor operacional da aplicação;
* testes deste pacote são **sintéticos/algébricos**: não constituem validação física;
* dados ausentes nunca viram zero, um, infinito ou Big-M: produzem constatação explícita ou rejeição controlada.

Versões independentes (contrato mestre §4): ``ESQUEMA_VERSAO`` (formato da entrada canônica), ``MOTOR_ID``
(identidade do motor) e ``FORMULACAO_VERSAO`` (versão da formulação matemática de referência).
"""
from __future__ import annotations

ESQUEMA_VERSAO = 1
MOTOR_ID = "milp_mpc_v1"
MOTOR_LEGADO_ID = "legacy_v16"
FORMULACAO_VERSAO = "v1.1-3A"
ESTADO_MOTOR = "experimental_sem_solver"   # nenhuma capacidade de despacho existe no Piso 3A
ROTULO_EVIDENCIA = "sintetico/algebrico — não é validação física"

__all__ = ["ESQUEMA_VERSAO", "ESTADO_MOTOR", "FORMULACAO_VERSAO", "MOTOR_ID", "MOTOR_LEGADO_ID", "ROTULO_EVIDENCIA"]
