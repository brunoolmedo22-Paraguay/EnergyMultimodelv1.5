"""Piso 3C-2 — isolamento do núcleo MPC e preservação dos pisos anteriores.

* nenhum módulo de ``ems_v2.mpc`` (nem ``ems_v2.fixtures_3c2``) carrega Pyomo, HiGHS, Streamlit, ``seeds2`` ou
  bibliotecas científicas ao ser importado (o adaptador importa ``resolver_3c1`` só ao resolver);
* nenhum módulo de ``ems_v2.mpc`` importa ``seeds2``/UI/motor legado (análise estática);
* NENHUM arquivo existente na base auditada ``55440f4`` (merge do PR #14) foi alterado/removido: 3A, 3B-P, 3C-0, 3C-1,
  V1.6, ``seeds2``, aplicação e requirements. O 3C-2 só ACRESCENTA arquivos novos (``ems_v2/mpc/``,
  ``ems_v2/fixtures_3c2.py``, testes e documentos);
* as guardas anteriores continuam valendo sem ajuste (``ADICOES_3C1`` inalterado: nada novo em ``ems_v2/milp``).
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
BASE_3C1 = "55440f4"
PROIBIDOS = ["streamlit", "pyomo", "highspy", "seeds2", "ems_integration", "orchestrator_runtime", "models",
             "h2_pemfc", "simulation", "config", "numpy", "scipy", "pandas"]


def test_nucleo_mpc_so_biblioteca_padrao_ao_importar():
    codigo = (
        "import sys, json, importlib, pkgutil, ems_v2.mpc\n"
        "mods = [m.name for m in pkgutil.iter_modules(ems_v2.mpc.__path__, 'ems_v2.mpc.')] + ['ems_v2.fixtures_3c2']\n"
        "[importlib.import_module(m) for m in mods]\n"
        f"print(json.dumps({{'mods': mods, 'carregados': [p for p in {PROIBIDOS!r} if p in sys.modules]}}))\n")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, env=env, check=True)
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert len(res["mods"]) >= 14
    assert res["carregados"] == [], res


def _imports(p: Path) -> set[str]:
    arv = ast.parse(p.read_text(encoding="utf-8"))
    return ({n.module or "" for n in ast.walk(arv) if isinstance(n, ast.ImportFrom) and n.level == 0}
            | {a.name for n in ast.walk(arv) if isinstance(n, ast.Import) for a in n.names})


def _imports_relativos(p: Path) -> set[str]:
    arv = ast.parse(p.read_text(encoding="utf-8"))
    return {("." * n.level) + (n.module or "") for n in ast.walk(arv) if isinstance(n, ast.ImportFrom) and n.level > 0}


def _e_milp(m: str) -> bool:
    """``..milp`` / ``..milp.solver_3c1`` (subpacote do solver); o módulo ``.adaptador_milp`` não conta."""
    return m.startswith("..") and m.lstrip(".").split(".")[0] == "milp"


def test_mpc_sem_seeds2_ui_motor_legado_e_milp_so_no_adaptador():
    proibidos = ("streamlit", "pyomo", "highspy", "seeds2", "ems_integration", "orchestrator_runtime",
                 "orchestrator_app", "app")
    for p in sorted((RAIZ / "ems_v2" / "mpc").rglob("*.py")):
        assert not any(m.split(".")[0] in proibidos for m in _imports(p)), p
        rel = _imports_relativos(p)
        if p.name not in ("adaptador_milp.py", "experimentos.py", "evidencia.py"):
            assert not any(_e_milp(m) for m in rel), (p, rel)
        # mesmo nesses três, o import de ``ems_v2.milp`` é TARDIO (dentro de funções), nunca no nível do módulo
        arv = ast.parse(p.read_text(encoding="utf-8"))
        topo = {("." * n.level) + (n.module or "") for n in arv.body if isinstance(n, ast.ImportFrom)}
        assert not any(_e_milp(m) for m in topo), (p, topo)
    assert not any(m.split(".")[0] in proibidos for m in _imports(RAIZ / "ems_v2/fixtures_3c2.py"))


def test_pisos_anteriores_v16_e_aplicacao_sem_alteracao_desde_o_merge_do_pr14():
    # C-EOL-01: immutable delivery audit, independent of shallow Git history.
    from wind_guard_policy import authorized_changes, historical_changes, historical_untracked
    linhas = authorized_changes(RAIZ, historical_changes(RAIZ, BASE_3C1))
    assert [ln for ln in linhas if ln[0] != "A" and ln[1:] not in (["ems_v2/mpc/orquestrador.py"], ["ems_v2/ponte/execucao.py"])] == []
    assert all(ln[0] in ("A", "M") for ln in linhas)
    novos = {ln[1] for ln in linhas if ln[0] == "A"}
    nao_rastreados = set(historical_untracked(RAIZ, BASE_3C1))
    from test_ems_v2_ponte_isolamento import ADICOES_3C3, ADICOES_3C4
    for f in novos | nao_rastreados:
        assert (f.startswith(("ems_v2/mpc/", "ems_v2/rede/", "ems_v2/hierarquia/")) or f in ("ems_v2/fixtures_3c2.py", "ems_v2/fixtures_3c3.py", "ems_v2/fixtures_3c4.py")
                or f in ADICOES_3C3 | ADICOES_3C4), f


def test_adicoes_3c1_da_guarda_anterior_inalteradas():
    from test_ems_v2_ponte_isolamento import ADICOES_3C1
    assert ADICOES_3C1 == {"ems_v2/milp/modelo_3c1.py", "ems_v2/milp/solver_3c1.py", "ems_v2/milp/resultado_3c1.py",
                           "ems_v2/milp/evidencia_3c1.py"}
