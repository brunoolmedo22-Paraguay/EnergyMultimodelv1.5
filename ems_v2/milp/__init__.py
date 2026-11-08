"""Piso 3B-P — primeiro MILP executável do EMS ``milp_mpc_v1`` (Pyomo + HiGHS).

Único subpacote de ``ems_v2`` que importa Pyomo/HiGHS (o núcleo 3A continua só com a biblioteca padrão e o auditor
continua independente do Pyomo). Escopo: UMA janela determinística (sem MPC/realimentação), formulação
``v1.1-3B-P`` declarada na entrada, compromisso dos geradores FIXADO explicitamente e constante (sem transições:
M09/M11/M12 não são modelados). Ver ``docs/ems_v2/FORMULACAO_3BP.md``.

Módulos: ``ambiente`` (versões/disponibilidade), ``config`` (configuração do solver e pré-verificação 3B-P, sem
Pyomo), ``modelo`` (construção Pyomo), ``resultado`` (classificação e estrutura do resultado, sem Pyomo) e
``solver`` (API ``resolver``). Este ``__init__`` não importa Pyomo.
"""
