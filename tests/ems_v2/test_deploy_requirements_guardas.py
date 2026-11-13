"""C-DEPLOY-01: testes positivos e negativos da autorização byte a byte."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import deploy_requirements_guard_policy as G

ROOT = Path(__file__).resolve().parents[2]


def test_requirements_exactos_e_fail_closed():
    assert G.requirements_autorizado(ROOT)
    assert "-r requirements-ems_v2.txt" in (ROOT / G.ARQUIVO).read_text("utf-8")
    with mock.patch.object(G, "SHA256_AUTORIZADO", "0" * 64):
        assert not G.requirements_autorizado(ROOT)


def test_workflow_so_recebe_uma_insercao_exata():
    base = subprocess.run(["git", "show", f"{G.BASE_WORKFLOW}:{G.WORKFLOW}"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    esperado = G.workflow_esperado(base)
    assert esperado == (ROOT / G.WORKFLOW).read_text("utf-8")
    assert G.workflow_autorizado(ROOT)
    assert "pip uninstall --yes pyomo highspy" in esperado
    assert G.workflow_esperado(base + "\n# mudança não autorizada") != esperado
    assert G.workflow_esperado(base.replace(G.ANCORA, "")) is None


def test_filtro_excecoes_nominais_sem_ocultar_outras_mudancas():
    linhas = [["M", G.ARQUIVO], ["M", G.WORKFLOW], ["D", G.ARQUIVO],
              ["A", G.ARQUIVO], ["M", "requirements-ems_v2.txt"], ["M", "ems_v2/milp/modelo_3c4.py"]]
    assert G.filter_changes(ROOT, linhas) == linhas[2:]
    with mock.patch.object(G, "requirements_autorizado", return_value=False):
        assert G.filter_changes(ROOT, linhas) == [linhas[0], *linhas[2:]]
    with mock.patch.object(G, "workflow_autorizado", return_value=False):
        assert G.filter_changes(ROOT, linhas) == [linhas[1], *linhas[2:]]
