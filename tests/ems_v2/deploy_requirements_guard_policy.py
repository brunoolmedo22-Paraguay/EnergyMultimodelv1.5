"""C-DEPLOY-01: exceção NOMINAL, sem enfraquecer as guardas históricas.

requirements.txt corresponde byte a byte ao commit autorizado f523035 (SHA-256 LITERAL).
A mudança do workflow é uma única inserção de linhas, comparada com a base do PR #28.
Qualquer outra mudança, inclusive em requirements-ems_v2.txt, continua detectável.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ARQUIVO = "requirements.txt"
SHA256_AUTORIZADO = "6d85fa2686f4160522920b1078b0b4f6ec6d146788420f76d5ace1153d482c0c"
COMMIT_REQUIREMENTS = "f523035333ba88b72d7fb92d21915b585b5b9d7b"
WORKFLOW = ".github/workflows/regression.yml"
BASE_WORKFLOW = "1f8b0f62ea28417e658a8a130dda0072c5416f13"
ANCORA = "      - name: Verify absence of optional solver"
INSERCAO = (
    "      - name: Remove solver for solver-free regression\n"
    "        if: ${{ !matrix.solver }}\n"
    "        run: python -m pip uninstall --yes pyomo highspy\n"
)


def requirements_autorizado(root: Path) -> bool:
    try:
        return hashlib.sha256((Path(root) / ARQUIVO).read_bytes()).hexdigest() == SHA256_AUTORIZADO
    except OSError:
        return False


def workflow_esperado(base: str) -> str | None:
    """Toda a versão anterior precisa permanecer idêntica; só se insere o passo necessário."""
    return base.replace(ANCORA, INSERCAO + ANCORA, 1) if base.count(ANCORA) == 1 else None


def workflow_autorizado(root: Path) -> bool:
    try:
        original = subprocess.run(
            ["git", "show", f"{BASE_WORKFLOW}:{WORKFLOW}"], cwd=root,
            capture_output=True, text=True, check=True,
        ).stdout
        esperado = workflow_esperado(original)
        return esperado is not None and (Path(root) / WORKFLOW).read_text("utf-8") == esperado
    except (OSError, subprocess.CalledProcessError):
        return False


def filter_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
    """Ignora só M requirements.txt e M regression.yml quando os conteúdos são exatos."""
    req_ok = requirements_autorizado(root)
    ci_ok = workflow_autorizado(root)
    return [row for row in changes if not (
        len(row) == 2 and row[0] == "M" and (
            (row[1] == ARQUIVO and req_ok) or (row[1] == WORKFLOW and ci_ok)
        )
    )]


__all__ = [
    "ARQUIVO", "SHA256_AUTORIZADO", "COMMIT_REQUIREMENTS", "WORKFLOW", "BASE_WORKFLOW",
    "ANCORA", "INSERCAO", "requirements_autorizado", "workflow_esperado",
    "workflow_autorizado", "filter_changes",
]
