"""Testes do Piso 3A (``ems_v2``): todos SINTÉTICOS/ALGÉBRICOS — não constituem validação física.

Funcionam sem solver instalado (Pyomo/HiGHS não são dependências do Piso 3A).
"""


def pytest_configure(config):
    config.addinivalue_line("markers", "synthetic_algebraic: teste sintético/algébrico do Piso 3A (não é validação física)")
