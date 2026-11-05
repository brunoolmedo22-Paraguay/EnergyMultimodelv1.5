"""Proteção da suíte: os testes NUNCA usam o armazenamento real da instalação (~/.seeds2).

Cada teste que precisa de dados define ``SEEDS2_DATA_DIR`` explicitamente; este padrão de sessão garante
que nada escape para o diretório do usuário caso algum teste esqueça de fazê-lo.
"""
import os
import shutil
import tempfile

_SAFE = tempfile.mkdtemp(prefix="seeds2_pytest_")
os.environ["SEEDS2_DATA_DIR"] = _SAFE


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    shutil.rmtree(_SAFE, ignore_errors=True)
