"""Piso 3C-0 — isolamento da ponte e preservação do V1.6 (guarda que acompanha a exceção C-3C0-01).

* só ``ems_v2/ponte_seeds2/leitor.py`` importa ``seeds2``, e apenas módulos de LEITURA (whitelist);
* o leitor não chama nenhuma API de gravação do SEEDS2 (análise estática);
* nenhum módulo da ponte importa Streamlit, Pyomo/HiGHS, ``ems_integration``, ``orchestrator_runtime`` ou a UI;
* a aplicação continua sem referenciar ``ems_v2`` (o teste 3A ``test_aplicacao_nao_referencia_ems_v2`` é mantido);
* EMS V1.6, modelos, runtime, ``seeds2`` e ``requirements.txt`` sem alteração em relação à base auditada.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.synthetic_algebraic
RAIZ = Path(__file__).resolve().parents[2]
WHITELIST_SEEDS2 = {"seeds2.microgrid", "seeds2.microgrid.config", "seeds2.microgrid.derived",
                    "seeds2.microgrid.references", "seeds2.operation", "seeds2.operation.scenarios"}
ESCRITA = {"save", "create", "create_scenario", "save_scenario", "delete", "put_blob", "record_run", "start_run",
           "finish_run", "fail_run", "heartbeat_run", "restore_backup", "import_inspected", "revert_to",
           "stamp_incarnation", "import_new", "import_copy", "restore_into", "adopt_legacy", "recover", "recover_runs",
           "update_equipment", "add_equipment", "retire_equipment", "rebase", "_tx"}
BASE_AUDITADA = "3c65d98"


def _imports(p: Path) -> set[str]:
    arv = ast.parse(p.read_text(encoding="utf-8"))
    return ({n.module or "" for n in ast.walk(arv) if isinstance(n, ast.ImportFrom) and n.level == 0}
            | {a.name for n in ast.walk(arv) if isinstance(n, ast.Import) for a in n.names})


def test_so_o_leitor_importa_seeds2_e_apenas_modulos_de_leitura():
    usam = {}
    for p in sorted((RAIZ / "ems_v2").rglob("*.py")):
        s2 = {m for m in _imports(p) if m.split(".")[0] == "seeds2"}
        if s2:
            usam[p.relative_to(RAIZ / "ems_v2").as_posix()] = s2
    assert set(usam) == {"ponte_seeds2/leitor.py"}, usam
    assert usam["ponte_seeds2/leitor.py"] <= WHITELIST_SEEDS2, usam


def test_leitor_nao_chama_api_de_gravacao():
    arv = ast.parse((RAIZ / "ems_v2/ponte_seeds2/leitor.py").read_text(encoding="utf-8"))
    chamadas = {n.func.attr for n in ast.walk(arv) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not chamadas & ESCRITA, chamadas & ESCRITA


def test_ponte_sem_ui_motor_legado_ou_solver():
    proibidos = ("streamlit", "pyomo", "highspy", "ems_integration", "orchestrator_runtime", "orchestrator_app", "app")
    for d in ("ponte", "ponte_seeds2"):
        for p in sorted((RAIZ / "ems_v2" / d).rglob("*.py")):
            assert not any(m.split(".")[0] in proibidos for m in _imports(p)), p
    assert not any(m.split(".")[0] in proibidos + ("seeds2",) for m in _imports(RAIZ / "ems_v2/fixtures_3c0.py"))


# 3C-1 (contradição C-3C1-01, docs/ems_v2/FORMULACAO_3C1.md §9): o 3C-1 precisa ACRESCENTAR módulos ao subpacote
# ``ems_v2/milp`` (único autorizado a importar Pyomo/HiGHS). A guarda continua exigindo que TODO arquivo existente na
# base auditada esteja byte a byte inalterado (nenhuma modificação, renomeação ou remoção) e passa a admitir apenas as
# ADIÇÕES nominais abaixo — nunca em V1.6, modelos, runtime, ``seeds2``, aplicação ou requirements.
ADICOES_3C1 = {"ems_v2/milp/modelo_3c1.py", "ems_v2/milp/solver_3c1.py", "ems_v2/milp/resultado_3c1.py",
               "ems_v2/milp/evidencia_3c1.py"}


def test_v16_e_aplicacao_sem_alteracao_desde_a_base_auditada():
    try:
        subprocess.run(["git", "cat-file", "-e", BASE_AUDITADA], cwd=RAIZ, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip(f"Histórico git sem a base {BASE_AUDITADA} (clone raso): verificação feita no PR.")
    alvos = ["ems_integration", "models", "h2_pemfc", "simulation", "config", "reference_models", "seeds2",
             "orchestrator_runtime.py", "orchestrator_app.py", "app.py", "ems_app.py", "requirements.txt",
             "requirements-ems_v2.txt", "ems_v2/milp", "ems_v2/contracts.py", "ems_v2/audit.py", "ems_v2/reference.py"]
    out = subprocess.run(["git", "diff", "--name-status", "--no-renames", BASE_AUDITADA, "--", *alvos], cwd=RAIZ,
                         capture_output=True, text=True, check=True).stdout
    linhas = [ln.split("\t") for ln in out.strip().splitlines() if ln.strip()]
    modificados = [ln for ln in linhas if ln[0] != "A"]
    adicionados = {ln[1] for ln in linhas if ln[0] == "A"}
    assert modificados == [], modificados                    # nenhum arquivo da base alterado ou removido
    assert adicionados <= ADICOES_3C1, adicionados - ADICOES_3C1
    nao_rastreados = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "--", *alvos], cwd=RAIZ,
                                    capture_output=True, text=True, check=True).stdout.split()
    assert set(nao_rastreados) <= ADICOES_3C1, set(nao_rastreados) - ADICOES_3C1
