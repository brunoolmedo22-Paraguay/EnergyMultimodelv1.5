"""Piso 3C-4 — isolamento do EMS hierárquico e preservação dos pisos anteriores (base ``10365c5``, merge do PR #16).

* nenhum módulo de ``ems_v2.hierarquia`` (nem ``ems_v2.fixtures_3c4``) carrega Pyomo, HiGHS, Streamlit, ``seeds2`` ou
  bibliotecas científicas ao ser importado; o MILP só é alcançado TARDIAMENTE pelos adaptadores;
* desde a base, NENHUM arquivo existente foi alterado ou removido, exceto os ajustes NOMINAIS das guardas de testes
  anteriores (contradição C-3C4-02: admitir as ADIÇÕES 3C-4); ``ems_v2/mpc``, ``ems_v2/rede``, ``ems_v2/milp`` (3B-P,
  3C-1, 3C-3), contratos 3A/3C-0/3C-1, V1.6, ``seeds2``, aplicação e requirements intactos byte a byte;
* adições só nos caminhos autorizados do 3C-4.
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
BASE_3C3 = "10365c5"
PROIBIDOS = ["streamlit", "pyomo", "highspy", "seeds2", "ems_integration", "orchestrator_runtime", "models",
             "h2_pemfc", "simulation", "config", "numpy", "scipy", "pandas"]
MODIFICADOS_3C4 = {"tests/ems_v2/test_ems_v2_3c2_isolamento.py", "tests/ems_v2/test_ems_v2_3c3_isolamento.py",
                   "tests/ems_v2/test_ems_v2_ponte_isolamento.py", "tests/ems_v2/test_ems_v2_milp_perfil.py"}
# B3C4-01 — hotfix AUTORIZADO na auditoria do PR #17 (FORMULACAO_3C4 §10b): ÚNICOS arquivos protegidos de código
# modificados; diffs restritos à projeção numérica da energia (função compartilhada) — verificado abaixo.
HOTFIX_B3C4_01 = {"ems_v2/ponte/execucao.py", "ems_v2/rede/execucao.py"}
MODIFICADOS_3C4 = MODIFICADOS_3C4 | HOTFIX_B3C4_01


def test_nucleo_hierarquico_so_biblioteca_padrao_ao_importar():
    codigo = (
        "import sys, json, importlib, pkgutil, ems_v2.hierarquia\n"
        "mods = [m.name for m in pkgutil.iter_modules(ems_v2.hierarquia.__path__, 'ems_v2.hierarquia.')]"
        " + ['ems_v2.fixtures_3c4', 'ems_v2.milp.resultado_3c4']\n"
        "[importlib.import_module(m) for m in mods]\n"
        f"print(json.dumps({{'mods': mods, 'carregados': [p for p in {PROIBIDOS!r} if p in sys.modules]}}))\n")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, env=env, check=True)
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert len(res["mods"]) >= 10 and res["carregados"] == [], res


def test_hierarquia_importa_milp_so_tardiamente():
    for p in sorted((RAIZ / "ems_v2" / "hierarquia").rglob("*.py")):
        arv = ast.parse(p.read_text(encoding="utf-8"))
        topo = {("." * n.level) + (n.module or "") for n in arv.body if isinstance(n, ast.ImportFrom)}
        assert not any(m.lstrip(".").split(".")[0] == "milp" for m in topo), (p, topo)
        nomes = {n.module or "" for n in ast.walk(arv) if isinstance(n, ast.ImportFrom)} | {
            a.name for n in ast.walk(arv) if isinstance(n, ast.Import) for a in n.names}
        assert not any(x.split(".")[0] in ("pyomo", "highspy", "streamlit", "seeds2", "ems_integration") for x in nomes), p


def test_aplicacao_nao_importa_o_ems_hierarquico():
    for alvo in ("app.py", "orchestrator_app.py", "orchestrator_runtime.py", "ems_app.py"):
        txt = (RAIZ / alvo).read_text(encoding="utf-8")
        assert "ems_v2" not in txt, alvo
    for p in (RAIZ / "seeds2").rglob("*.py"):
        assert "ems_v2" not in p.read_text(encoding="utf-8"), p


def test_pisos_anteriores_v16_e_aplicacao_sem_alteracao_desde_o_merge_do_pr16():
    try:
        subprocess.run(["git", "cat-file", "-e", BASE_3C3], cwd=RAIZ, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip(f"Histórico git sem a base {BASE_3C3} (clone raso): verificação feita no PR.")
    alvos = ["ems_v2", "tests", "ems_integration", "models", "h2_pemfc", "simulation", "config", "reference_models",
             "seeds2", "orchestrator_runtime.py", "orchestrator_app.py", "app.py", "ems_app.py", "requirements.txt",
             "requirements-ems_v2.txt"]
    out = subprocess.run(["git", "diff", "--name-status", "--no-renames", BASE_3C3, "--", *alvos], cwd=RAIZ,
                         capture_output=True, text=True, check=True).stdout
    linhas = [ln.split("\t") for ln in out.strip().splitlines() if ln.strip()]
    alterados = {ln[1] for ln in linhas if ln[0] != "A"}
    assert alterados <= MODIFICADOS_3C4, alterados - MODIFICADOS_3C4
    assert all(ln[0] in ("A", "M") for ln in linhas)
    novos = {ln[1] for ln in linhas if ln[0] == "A"} | set(subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", *alvos], cwd=RAIZ, capture_output=True, text=True,
        check=True).stdout.split())
    from test_ems_v2_ponte_isolamento import ADICOES_3C4
    for f in novos:
        assert (f.startswith(("ems_v2/hierarquia/", "tests/ems_v2/test_ems_v2_3c4_"))
                or f in ADICOES_3C4 or f == "ems_v2/fixtures_3c4.py"), f


def test_adicoes_3c4_nominais():
    from test_ems_v2_ponte_isolamento import ADICOES_3C1, ADICOES_3C3, ADICOES_3C4
    assert ADICOES_3C4 == {"ems_v2/milp/modelo_3c4.py", "ems_v2/milp/solver_3c4.py", "ems_v2/milp/resultado_3c4.py",
                           "ems_v2/milp/evidencia_3c4.py"}
    assert ADICOES_3C1 == {"ems_v2/milp/modelo_3c1.py", "ems_v2/milp/solver_3c1.py", "ems_v2/milp/resultado_3c1.py",
                           "ems_v2/milp/evidencia_3c1.py"}
    assert ADICOES_3C3 == {"ems_v2/milp/modelo_3c3.py", "ems_v2/milp/solver_3c3.py", "ems_v2/milp/resultado_3c3.py",
                           "ems_v2/milp/evidencia_3c3.py"}


# Linhas REMOVIDAS admitidas pelo hotfix B3C4-01 (recorrência M07 movida para ``energia_apos_intervalo``, verificação
# de limites reescrita com os mesmos limites, transporte do valor projetado, avisos no passo, import) — nada mais.
REMOVIDAS_B3C4_01 = {
    'alfa = 1.0 if b.hipotese_autodescarga == "nao_modelada_alpha_1" else math.exp(',
    '-float(b.autodescarga_1_h.valor) * h)',
    'e1 = alfa * st.energia_kWh + h * (float(b.eta_carga.valor) * pc - pd / float(b.eta_descarga.valor))',
    'if not (float(b.soc_min.valor) * C - tolE <= e1 <= float(b.soc_max.valor) * C + tolE):',
    'novos_b.append(EstadoArmazenamento(uid, e1))',
    'return PassoAplicado({k_: float(v) for k_, v in sorted(consignas.items())}, novo, True, ())',
    'PlanoDespacho, TrajetoriaExecutada, TrajetoriaPlanejada, hash_plano, validar_plano)',
    'alfa = 1.0 if x.hipotese_autodescarga == "nao_modelada_alpha_1" else math.exp(',
    '-float(x.autodescarga_1_h.valor) * h)',
    'e1 = alfa * st.energia_kWh + h * (float(x.eta_carga.valor) * pc - pd / float(x.eta_descarga.valor))',
    'if not (float(x.soc_min.valor) * C - tolE <= e1 <= float(x.soc_max.valor) * C + tolE):',
    'return PassoAplicado(dict(sorted(aplicado.items())), novo, True, ())',
}


def test_hotfix_b3c4_01_restrito_a_projecao_numerica():
    try:
        subprocess.run(["git", "cat-file", "-e", BASE_3C3], cwd=RAIZ, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip(f"Histórico git sem a base {BASE_3C3} (clone raso): verificação feita no PR.")
    out = subprocess.run(["git", "diff", "-U0", BASE_3C3, "--", *sorted(HOTFIX_B3C4_01)], cwd=RAIZ,
                         capture_output=True, text=True, check=True).stdout
    removidas = {ln[1:].strip() for ln in out.splitlines() if ln.startswith("-") and not ln.startswith("---")}
    assert removidas <= REMOVIDAS_B3C4_01, removidas - REMOVIDAS_B3C4_01
    adicionadas = "\n".join(ln[1:] for ln in out.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    assert "energia_apos_intervalo" in adicionadas and "projecao_numerica_energia" in adicionadas
    for proibido in ("min(max(", "max(min(", "clip(", "soc_min.valor) * C - tolE - ", "tolE * "):
        assert proibido not in adicionadas, proibido
