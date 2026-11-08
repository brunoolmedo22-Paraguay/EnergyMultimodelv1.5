"""Adaptador SOMENTE LEITURA SEEDS2 → contratos da ponte 3C-0 (``ems_v2.ponte``).

Único subpacote de ``ems_v2`` que importa ``seeds2`` (assim como ``ems_v2.milp`` é o único que importa Pyomo/HiGHS).
Este ``__init__`` não importa ``seeds2``: o módulo ``leitor`` o faz sob demanda. Nada aqui grava em bancos de
microrrede, altera o catálogo, chama o EMS V1.6 ou é chamado pela aplicação (a aplicação continua sem referenciar
``ems_v2``; teste ``test_aplicacao_nao_referencia_ems_v2``).
"""
