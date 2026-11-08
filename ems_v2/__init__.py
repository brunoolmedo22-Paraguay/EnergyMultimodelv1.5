"""SEEDS2 — fundações do EMS MILP–MPC experimental (Piso 3A).

Piso 3A: este pacote contém contratos canônicos, unidades, malha temporal, cálculo algébrico de referência,
auditor algébrico independente, registro declarativo de capacidades, fixtures sintéticas e o catálogo de símbolos
M01–M23 (+ adenda v1.1). Piso 3B-P: o subpacote ``ems_v2.milp`` (ÚNICO que importa Pyomo/HiGHS) constrói e resolve o primeiro MILP
a partir desses contratos, com perfil de capacidades explícito (``FORMULACAO_3BP``). Nenhuma integração com a
interface, o Centro de Operação ou o runtime V1.6.

Regras do pacote:

* o NÚCLEO (todos os módulos fora de ``ems_v2.milp``) não importa Streamlit, Pyomo, HiGHS, ``seeds2``,
  ``ems_integration`` nem os modelos científicos; só a biblioteca padrão (``tests/ems_v2/test_ems_v2_isolamento.py``);
  o auditor permanece independente do Pyomo;
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
FORMULACAO_VERSAO = "v1.1-3A"            # formulação do Piso 3A (contrato, referência, auditoria; sem solver)
FORMULACAO_3BP = "v1.1-3B-P"             # Piso 3B-P: primeiro MILP executável (Pyomo + HiGHS), perfil explícito
FORMULACOES = (FORMULACAO_VERSAO, FORMULACAO_3BP)
ESTADO_MOTOR = "experimental_sem_solver"   # estado no Piso 3A (registro); 3B-P: ver ESTADO_MOTOR_3BP
ESTADO_MOTOR_3BP = "experimental_milp_janela_unica"   # MILP só por API/testes; nunca integrado à aplicação
ROTULO_EVIDENCIA = "sintetico/algebrico — não é validação física"

__all__ = ["ESQUEMA_VERSAO", "ESTADO_MOTOR", "ESTADO_MOTOR_3BP", "FORMULACAO_3BP", "FORMULACAO_VERSAO", "FORMULACOES", "MOTOR_ID",
           "MOTOR_LEGADO_ID", "ROTULO_EVIDENCIA"]
