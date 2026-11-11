"""Motores SABOTADOS (V1.6 e V2) para o E2E de consulta do Piso 3D-A — NUNCA usar em produção.

Ativado só quando este diretório está no ``PYTHONPATH`` do servidor de teste. Além da sabotagem V1.6 existente
(``tools/e2e/sabotage``), substitui o runner do motor V2 e a montagem do controlador e BLOQUEIA a importação de Pyomo e
highspy; toda tentativa é registrada em ``$SEEDS2_E2E_ENGINE_LOG`` e falha. Ao fim do E2E o registro deve estar vazio:
prova de que importar, abrir e verificar um estudo V2 não executa nenhum motor nem carrega o solver.
"""
import importlib.abc
import os
import sys

_LOG = os.environ.get("SEEDS2_E2E_ENGINE_LOG")
if _LOG:
    root = os.environ.get("SEEDS2_E2E_ROOT") or os.getcwd()
    if root not in sys.path:
        sys.path.insert(0, root)

    def _registrar(nome):
        with open(_LOG, "a", encoding="utf-8") as fh:
            fh.write(nome + "\n")

    def _boom(nome):
        def f(*a, **k):
            _registrar(nome)
            raise RuntimeError(f"E2E: {nome} chamado com o motor sabotado")
        return f

    class _SemSolver(importlib.abc.MetaPathFinder):
        def find_spec(self, nome, path=None, target=None):
            if nome.split(".")[0] in ("pyomo", "highspy"):
                _registrar(f"import {nome}")
                raise ImportError(f"E2E: importação de {nome} bloqueada (motor sabotado)")
            return None

    sys.meta_path.insert(0, _SemSolver())

    import orchestrator_runtime as _RT  # noqa: E402
    from integracao_v2 import execucao as _X  # noqa: E402
    from integracao_v2 import montagem as _MT  # noqa: E402
    from seeds2.operation import runner as _runner  # noqa: E402

    _RT.run_optimizer = _boom("run_optimizer")
    _RT.build_exchange_package = _boom("build_exchange_package")
    _runner.submit = _boom("runner.submit")
    _X.submit = _boom("v2.submit")
    _X._executar = _boom("v2._executar")
    _MT.construir_missao = _boom("v2.construir_missao")
