"""Piso 3C-3 — isolamento do núcleo de rede e preservação dos pisos anteriores (base ``a4c6b1c``, merge do PR #15).

* nenhum módulo de ``ems_v2.rede`` (nem ``ems_v2.fixtures_3c3``) carrega Pyomo, HiGHS, Streamlit, ``seeds2`` ou
  bibliotecas científicas ao ser importado; o MILP só é importado TARDIAMENTE pelo adaptador/experimentos;
* desde a base, nenhum arquivo existente foi alterado ou removido, EXCETO a refatoração controlada nominal de
  ``ems_v2/mpc/orquestrador.py`` (pontos de extensão; regressão G15) e os ajustes NOMINAIS das guardas de testes
  anteriores (contradição C-3C3-02); V1.6, ``seeds2``, aplicação e requirements sem nenhuma mudança;
* adições só nos caminhos autorizados do 3C-3.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.synthetic_algebraic
RAIZ = Path(__file__).resolve().parents[2]
BASE_3C2 = "a4c6b1c"
PROIBIDOS = ["streamlit", "pyomo", "highspy", "seeds2", "ems_integration", "orchestrator_runtime", "models",
             "h2_pemfc", "simulation", "config", "numpy", "scipy", "pandas"]
MODIFICADOS_3C3 = {"ems_v2/mpc/orquestrador.py", "tests/ems_v2/test_ems_v2_3c2_isolamento.py",
                   "tests/ems_v2/test_ems_v2_ponte_isolamento.py", "tests/ems_v2/test_ems_v2_milp_perfil.py"}


def test_nucleo_rede_so_biblioteca_padrao_ao_importar():
    codigo = (
        "import sys, json, importlib, pkgutil, ems_v2.rede\n"
        "mods = [m.name for m in pkgutil.iter_modules(ems_v2.rede.__path__, 'ems_v2.rede.')] + ['ems_v2.fixtures_3c3']\n"
        "[importlib.import_module(m) for m in mods]\n"
        f"print(json.dumps({{'mods': mods, 'carregados': [p for p in {PROIBIDOS!r} if p in sys.modules]}}))\n")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, env=env, check=True)
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert len(res["mods"]) >= 11 and res["carregados"] == [], res


def test_rede_importa_milp_so_tardiamente():
    for p in sorted((RAIZ / "ems_v2" / "rede").rglob("*.py")):
        arv = ast.parse(p.read_text(encoding="utf-8"))
        topo = {("." * n.level) + (n.module or "") for n in arv.body if isinstance(n, ast.ImportFrom)}
        assert not any(m.lstrip(".").split(".")[0] == "milp" for m in topo), (p, topo)
        nomes = {n.module or "" for n in ast.walk(arv) if isinstance(n, ast.ImportFrom)} | {
            a.name for n in ast.walk(arv) if isinstance(n, ast.Import) for a in n.names}
        assert not any(x.split(".")[0] in ("pyomo", "highspy", "streamlit", "seeds2", "ems_integration") for x in nomes), p


def test_pisos_anteriores_v16_e_aplicacao_sem_alteracao_desde_o_merge_do_pr15():
    try:
        subprocess.run(["git", "cat-file", "-e", BASE_3C2], cwd=RAIZ, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip(f"Histórico git sem a base {BASE_3C2} (clone raso): verificação feita no PR.")
    alvos = ["ems_v2", "tests", "ems_integration", "models", "h2_pemfc", "simulation", "config", "reference_models",
             "seeds2", "orchestrator_runtime.py", "orchestrator_app.py", "app.py", "ems_app.py", "requirements.txt",
             "requirements-ems_v2.txt"]
    out = subprocess.run(["git", "diff", "--name-status", "--no-renames", BASE_3C2, "--", *alvos], cwd=RAIZ,
                         capture_output=True, text=True, check=True).stdout
    linhas = [ln.split("\t") for ln in out.strip().splitlines() if ln.strip()]
    from wind_guard_policy import authorized_changes, authorized_additions
    linhas = authorized_changes(RAIZ, linhas)  # missão eólica: arquivos/pins exatos
    alterados = {ln[1] for ln in linhas if ln[0] != "A"}
    assert alterados <= MODIFICADOS_3C3, alterados - MODIFICADOS_3C3
    assert all(ln[0] in ("A", "M") for ln in linhas)
    novos = {ln[1] for ln in linhas if ln[0] == "A"} | set(subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", *alvos], cwd=RAIZ, capture_output=True, text=True,
        check=True).stdout.split())
    from test_ems_v2_ponte_isolamento import ADICOES_3C3
    novos = set(authorized_additions(RAIZ, novos))
    for f in novos:
        assert (f.startswith(("ems_v2/rede/", "tests/ems_v2/test_ems_v2_3c3_", "tests/ems_v2/dados/"))
                or f in ADICOES_3C3 or f == "ems_v2/fixtures_3c3.py"), f
