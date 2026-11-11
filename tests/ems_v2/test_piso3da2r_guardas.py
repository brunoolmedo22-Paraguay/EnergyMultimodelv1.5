"""Piso 3D-A2-R — guardas da exceção nominal C-3DA2R-01 (mesmo mecanismo da C-3DA-01).

Verifica que a integração das renováveis não alterou o motor auditado nem os modelos físicos que só LÊ, que a exceção
é nominal (nomes e status exatos) e que a camada de integração não carrega Pyomo/HiGHS ao ser importada.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import piso3da2r_guard_policy as P  # noqa: E402


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True).stdout


def _base_disponivel() -> bool:
    try:
        subprocess.run(["git", "cat-file", "-e", P.BASE], cwd=RAIZ, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def test_politica_e_nominal_e_nao_cobre_diretorios():
    assert all(not x.endswith("/") and "*" not in x for x in P.MODIFICADOS | P.ADICIONADOS)
    assert not any(x.startswith(("ems_v2/", "models/", "simulation/", "config/", "h2_pemfc/", "ems_integration/"))
                   for x in P.MODIFICADOS | P.ADICIONADOS)
    assert P.filter_changes(RAIZ, [["D", "tests/piso3da2r_util.py"], ["R100", "a", "b"], ["M", "tests/piso3da2r_util.py"]]) \
        == [["D", "tests/piso3da2r_util.py"], ["R100", "a", "b"], ["M", "tests/piso3da2r_util.py"]]
    assert P.filter_changes(RAIZ, [["A", "tests/piso3da2r_util.py"]]) == []


@pytest.mark.skipif(not _base_disponivel(), reason="Histórico git sem a base do 3D-A2-R (clone raso)")
def test_motor_auditado_e_modelos_fisicos_identicos_a_base():
    for alvo in ("ems_v2", "models", "simulation", "config", "h2_pemfc", "ems_integration"):
        assert _git("rev-parse", f"{P.BASE}:{alvo}") == _git("rev-parse", f"HEAD:{alvo}"), alvo


def test_aplicacao_continua_sem_o_literal_do_motor():
    for p in (RAIZ / "seeds2").rglob("*.py"):
        assert "ems_v2" not in p.read_text(encoding="utf-8"), p


def test_adaptador_renovavel_nao_carrega_solver_nem_streamlit_no_import():
    arv = ast.parse((RAIZ / "integracao_v2" / "renovaveis.py").read_text(encoding="utf-8"))
    topo = {a.name for n in arv.body if isinstance(n, ast.Import) for a in n.names} | {
        n.module or "" for n in arv.body if isinstance(n, ast.ImportFrom)}
    assert not any(m.split(".")[0] in ("pyomo", "highspy", "streamlit", "ems_v2", "seeds2") for m in topo), topo


@pytest.mark.skipif(os.environ.get("SEEDS2_AUDITORIA_PISO3DA2R") != "1",
                    reason="Auditoria explícita do diff da missão: python tests/ems_v2/piso3da2r_guard_policy.py")
def test_auditoria_explicita_do_diff_da_missao():
    rel = P.auditar_missao(RAIZ)
    assert rel["ems_v2_base"] == rel["ems_v2_head"]
