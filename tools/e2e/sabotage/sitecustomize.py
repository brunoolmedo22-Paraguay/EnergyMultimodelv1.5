"""Motor SABOTADO para E2E de consulta/exportação (Pisos 2D-A/2D-B) — NUNCA usar em produção.

Ativado só quando este diretório está no ``PYTHONPATH`` do servidor de teste. Substitui as funções que executariam o
motor (``orchestrator_runtime.run_optimizer`` / ``build_exchange_package`` e ``seeds2.operation.runner.submit``) por
funções que REGISTRAM a chamada em ``$SEEDS2_E2E_ENGINE_LOG`` e falham. Ao fim do E2E o arquivo de registro deve estar
vazio/inexistente: prova de que abrir, consultar e exportar não executam o motor.
"""
import os
import sys

_LOG = os.environ.get("SEEDS2_E2E_ENGINE_LOG")
if _LOG:
    root = os.environ.get("SEEDS2_E2E_ROOT") or os.getcwd()
    if root not in sys.path:
        sys.path.insert(0, root)

    def _boom(name):
        def f(*a, **k):
            with open(_LOG, "a", encoding="utf-8") as fh:
                fh.write(name + "\n")
            raise RuntimeError(f"E2E: {name} chamado com o motor sabotado")
        return f

    import orchestrator_runtime as _RT  # noqa: E402
    from seeds2.operation import runner as _runner  # noqa: E402

    _RT.run_optimizer = _boom("run_optimizer")
    _RT.build_exchange_package = _boom("build_exchange_package")
    _runner.submit = _boom("runner.submit")
