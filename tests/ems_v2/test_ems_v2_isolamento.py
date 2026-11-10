"""Isolamento do pacote ``ems_v2`` e ausência de integração com a aplicação (política de dois motores, 3A)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.synthetic_algebraic
RAIZ = Path(__file__).resolve().parents[2]
PROIBIDOS = ["streamlit", "pyomo", "highspy", "seeds2", "ems_integration", "orchestrator_runtime", "models",
             "h2_pemfc", "simulation", "config", "numpy", "scipy", "pandas"]


def test_ems_v2_so_usa_biblioteca_padrao():
    codigo = (
        "import sys, json, importlib, pkgutil, ems_v2\n"
        "mods = [m.name for m in pkgutil.iter_modules(ems_v2.__path__, 'ems_v2.')]\n"
        "[importlib.import_module(m) for m in mods]\n"
        f"print(json.dumps({{'mods': mods, 'carregados': [p for p in {PROIBIDOS!r} if p in sys.modules]}}))\n")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, env=env, check=True)
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert len(res["mods"]) >= 10
    assert res["carregados"] == [], res


def test_aplicacao_nao_referencia_ems_v2():
    """3A: nenhum arquivo Python fora de ems_v2/ e tests/ems_v2/ menciona o pacote.

    Piso 3D-A (contradição C-3DA-01): a integração operacional foi AUTORIZADA. A varredura continua global; a única
    exceção é NOMINAL — a camada de integração ``integracao_v2/`` e os seus testes listados em
    ``piso3da_guard_policy`` (nenhum outro arquivo da aplicação, de ``seeds2`` ou do V1.6 pode mencionar o motor)."""
    from piso3da_guard_policy import referencia_autorizada
    achados = []
    for p in RAIZ.rglob("*.py"):
        rel = p.relative_to(RAIZ).as_posix()
        if rel.startswith(("ems_v2/", "tests/ems_v2/", "reference_models/")) or "/." in "/" + rel:
            continue
        if referencia_autorizada(rel):
            continue
        try:
            if "ems_v2" in p.read_text(encoding="utf-8", errors="ignore"):
                achados.append(rel)
        except OSError:
            continue
    assert achados == []


def test_sem_dependencia_nova_em_requirements():
    req = (RAIZ / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pyomo" not in req and "highs" not in req and "pydantic" not in req
