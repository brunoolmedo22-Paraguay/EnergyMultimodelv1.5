"""Piso 3D-A — guardas PERMANENTES da camada de integração (invariantes sem commit-base) e política nominal.

* só a camada ``integracao_v2`` (e seus testes nominais) referencia o motor ``ems_v2``; ``seeds2`` e as entradas V1.6
  nunca o mencionam e só importam a camada de integração TARDIAMENTE (cenários V1.6 não a carregam);
* a camada de integração não importa Pyomo/HiGHS (só o motor o faz, tardiamente) e nunca grava bancos por fora do
  ``MicrogridStore``;
* a exceção das guardas anteriores é por nome exato e status; os arquivos fixados por políticas anteriores não constam;
* a auditoria EXPLÍCITA do diff da missão (``piso3da_guard_policy.auditar_missao``) roda quando a base está no histórico.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import piso3da_guard_policy as G

RAIZ = Path(__file__).resolve().parents[2]
NUCLEO = ("estrategia", "montagem", "preflight", "registro", "execucao")


def _imports(p: Path, *, so_topo: bool = False) -> set[str]:
    arv = ast.parse(p.read_text(encoding="utf-8"))
    nos = arv.body if so_topo else list(ast.walk(arv))
    return ({n.module or "" for n in nos if isinstance(n, ast.ImportFrom) and n.level == 0}
            | {a.name for n in nos if isinstance(n, ast.Import) for a in n.names})


def _sub(codigo: str) -> dict:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, env=env, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_politica_nominal_sem_diretorios_nem_arquivos_fixados():
    for rel in G.MODIFICADOS | G.ADICIONADOS | G.REFERENCIAM_O_MOTOR:
        assert (RAIZ / rel).is_file() and not rel.endswith("/") and "*" not in rel, rel
    fixados = {"seeds2/operation/runner.py", "seeds2/ui/main.py", "seeds2/ui/operations.py", "thermal_app.py",
               "seeds2/microgrid/config.py", "seeds2/microgrid/references.py", "seeds2/ui/equipment.py"}
    assert not (G.MODIFICADOS | G.ADICIONADOS) & fixados
    assert not any(x.startswith("ems_v2/") for x in G.MODIFICADOS | G.ADICIONADOS)
    linhas = [["M", "seeds2/operation/scenarios.py"], ["A", "tests/piso3da_util.py"], ["D", "seeds2/operation/scenarios.py"],
              ["A", "seeds2/operation/scenarios.py"], ["M", "tests/piso3da_util.py"], ["M", "ems_v2/hierarquia/mpc.py"],
              ["A", "seeds2/novo.py"], ["M", "seeds2/operation/runner.py"], ["R100", "seeds2/ui/archive_ui.py", "x.py"]]
    assert G.filter_changes(RAIZ, linhas) == linhas[2:]                 # só nome E status exatos são filtrados


def test_seeds2_e_v16_nunca_mencionam_o_motor_e_so_importam_a_integracao_tardiamente():
    for p in [*sorted((RAIZ / "seeds2").rglob("*.py")), *(RAIZ / n for n in (
            "app.py", "orchestrator_app.py", "orchestrator_runtime.py", "ems_app.py"))]:
        txt = p.read_text(encoding="utf-8")
        assert "ems_v2" not in txt, p
        assert not any(m.split(".")[0] == "integracao_v2" for m in _imports(p, so_topo=True)), p
    usam = {p.relative_to(RAIZ).as_posix() for p in (RAIZ / "seeds2").rglob("*.py")
            if any(m.split(".")[0] == "integracao_v2" for m in _imports(p))}
    assert usam == {x for x in G.MODIFICADOS if x.startswith("seeds2/")} - {"seeds2/operation/preflight.py"}, usam


def test_fluxo_v16_nao_carrega_a_integracao_nem_o_motor():
    res = _sub("import sys, json\n"
               "from seeds2.operation import scenarios, preflight, runner, strategy, mission\n"
               "from seeds2.archive import exporter, store, view\n"
               "from seeds2.report import dossier\n"
               "doc = {'schema': 'seeds2-scenario', 'schema_version': 1}\n"
               "scenarios.structural_errors(doc); scenarios.strategy_status({'ems_strategy': None})\n"
               "print(json.dumps([m for m in ('integracao_v2', 'ems_v2', 'pyomo', 'highspy') if m in sys.modules]))\n")
    assert res == []


def test_integracao_nao_importa_solver_ui_nem_sqlite():
    for nome in NUCLEO:
        imp = _imports(RAIZ / "integracao_v2" / f"{nome}.py")
        assert not any(m.split(".")[0] in ("pyomo", "highspy", "streamlit", "sqlite3", "orchestrator_runtime",
                                           "ems_integration") for m in imp), (nome, imp)
    assert "streamlit" in _imports(RAIZ / "integracao_v2" / "ui.py")
    assert not any(m.split(".")[0] in ("pyomo", "highspy", "sqlite3") for m in _imports(RAIZ / "integracao_v2" / "ui.py"))
    res = _sub("import sys, json, importlib\n"
               f"[importlib.import_module('integracao_v2.' + m) for m in {NUCLEO!r}]\n"
               "print(json.dumps([m for m in ('pyomo', 'highspy', 'streamlit') if m in sys.modules]))\n")
    assert res == []                                                  # Pyomo/HiGHS só pelo motor, tardiamente


def test_estrategia_so_usa_a_biblioteca_padrao_e_o_nucleo_do_motor():
    res = _sub("import sys, json, integracao_v2.estrategia\n"
               "print(json.dumps([m for m in ('seeds2', 'numpy', 'pandas', 'pyomo', 'streamlit') if m in sys.modules]))\n")
    assert res == []


def test_runner_v2_grava_somente_pelo_microgridstore():
    arv = ast.parse((RAIZ / "integracao_v2" / "execucao.py").read_text(encoding="utf-8"))
    chamadas = {n.func.attr for n in ast.walk(arv) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert {"start_run", "finish_run", "fail_run", "heartbeat_run"} <= chamadas
    assert not chamadas & {"execute", "executemany", "executescript", "_tx", "put_blob", "save_scenario", "save",
                           "create_scenario", "record_run"}
    for nome in ("montagem", "preflight", "registro", "estrategia"):
        arv = ast.parse((RAIZ / "integracao_v2" / f"{nome}.py").read_text(encoding="utf-8"))
        ch = {n.func.attr for n in ast.walk(arv) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        assert not ch & {"start_run", "finish_run", "fail_run", "save_scenario", "create_scenario", "put_blob", "_tx",
                         "execute", "save"}, (nome, ch)


def test_impressao_cientifica_v2_cobre_motor_e_integracao_sem_tocar_a_do_v16(tmp_path, monkeypatch):
    from integracao_v2 import execucao as X
    from seeds2.operation import runner as R16
    assert "ems_v2" in X.SCIENCE_PATHS_V2 and "integracao_v2" in X.SCIENCE_PATHS_V2
    assert not any("ems" + "_v2" in p or "integracao_v2" in p for p in R16.SCIENCE_PATHS)
    for rel in X.SCIENCE_PATHS_V2:
        p = tmp_path / rel
        if Path(rel).suffix:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("base")
        else:
            p.mkdir(parents=True, exist_ok=True)
            (p / "m.py").write_text("base")
    monkeypatch.setattr(X, "ROOT", tmp_path)
    monkeypatch.setattr(X, "_FP", None)
    antes = X.science_fingerprint()["sha256"]
    (tmp_path / "ems_v2" / "m.py").write_text("alterado")
    monkeypatch.setattr(X, "_FP", None)
    assert X.science_fingerprint()["sha256"] != antes


def test_auditoria_explicita_do_diff_da_missao():
    """Diff base → árvore de trabalho: ``ems_v2`` idêntico, V1.6 e arquivos protegidos intocados, alterações nominais.
    Auditoria desta entrega (não restrição sobre pisos futuros): só roda enquanto a base da missão é o ponto de partida
    do ramo — depois da integração em ``main`` novas missões têm a sua própria auditoria."""
    def git(*a):
        return subprocess.run(["git", *a], cwd=RAIZ, capture_output=True, text=True)
    if git("cat-file", "-e", G.BASE).returncode != 0:
        pytest.skip(f"Histórico git sem a base {G.BASE[:7]} (clone raso): auditoria feita no PR.")
    if os.environ.get("SEEDS2_AUDITORIA_PISO3DA") != "1":
        pytest.skip("Auditoria explícita da missão 3D-A: defina SEEDS2_AUDITORIA_PISO3DA=1 (ou execute "
                    "python tests/ems_v2/piso3da_guard_policy.py).")
    rel = G.auditar_missao(RAIZ)
    assert rel["ems_v2_base"] == rel["ems_v2_head"]
