"""Piso 3C-1 — perfil de capacidades, catálogo (colunas 3C-1) e isolamento dos módulos novos (sem Pyomo)."""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ems_v2 import FORMULACAO_3BP, FORMULACAO_3C1, FORMULACAO_VERSAO
from ems_v2.capabilities import CAPACIDADES, CAPACIDADES_3BP, CAPACIDADES_3C1, PERFIS, capacidades, status_equacao
from ems_v2.catalog import carregar_equacoes, carregar_simbolos

pytestmark = pytest.mark.synthetic_algebraic
RAIZ = Path(__file__).resolve().parents[2]
SIM = {s["id"]: s for s in carregar_simbolos()}
EQ = {e["id"]: e for e in carregar_equacoes()}


def test_perfis_anteriores_intactos_e_3c1_explicito():
    assert PERFIS[FORMULACAO_VERSAO] is CAPACIDADES and PERFIS[FORMULACAO_3BP] is CAPACIDADES_3BP
    assert capacidades(formulacao=FORMULACAO_3C1) == CAPACIDADES_3C1
    assert status_equacao("M09", FORMULACAO_3BP) == "nao_suportado" and status_equacao("M09") == "nao_suportado"
    for eq in ("M09", "M11a", "M11b", "M12"):
        assert status_equacao(eq, FORMULACAO_3C1) == "implementado_3C1", eq
    for eq in ("M11-EXT", "M20", "M23", "M05", "TERM-SOFT"):
        assert status_equacao(eq, FORMULACAO_3C1) in ("nao_suportado", "apenas_especificacao"), eq


def test_capacidades_3c1_coerentes_com_o_manifesto():
    mapa = {"implementado_3C1": {"implementado_3C1"}, "parcial_3C1": {"parcial_3C1"},
            "futuro": {"apenas_especificacao", "nao_suportado"}}
    vistos = {}
    for c in CAPACIDADES_3C1:
        for eq in c.equacoes:
            assert eq in EQ and eq not in vistos, eq
            vistos[eq] = c
    for e in EQ.values():
        if e["status_3C1"] == "substituida":
            assert e["id"] not in vistos
        else:
            assert vistos[e["id"]].status in mapa[e["status_3C1"]], e["id"]
            assert vistos[e["id"]].familia == e["familia"], e["id"]


def _resolver(cod: str):
    partes = cod.split(".")
    for i in range(len(partes), 0, -1):
        try:
            obj = importlib.import_module(".".join(partes[:i]))
        except ModuleNotFoundError:
            continue
        for nome in partes[i:]:
            obj = getattr(obj, nome) if hasattr(obj, nome) else obj.__dataclass_fields__[nome]
        return obj
    raise ModuleNotFoundError(cod)


def test_catalogo_3c1_sem_simbolo_futuro_em_equacao_implementada_e_codigo_resolvivel():
    for e in EQ.values():
        if e["status_3C1"] == "implementado_3C1":
            for x in e["simbolos"]:
                assert SIM[x]["status_3C1"] in ("ativo_3C1", "decidido_3C1"), (e["id"], x)
        if e["status_3C1"] == "parcial_3C1":
            assert e.get("obs_3C1"), e["id"]
    for sid, s in SIM.items():
        if s["status_3C1"] in ("ativo_3C1", "decidido_3C1"):
            assert s["codigo_3C1"], sid
            if not s["codigo_3C1"].startswith("pyomo:") and "milp" not in s["codigo_3C1"]:
                _resolver(s["codigo_3C1"])
        else:
            assert not s["codigo_3C1"], sid
    for sid in ("w_end", "p_bar", "m_mode", "v_arc", "kappa", "xi", "y_start", "z_stop"):
        assert SIM[sid]["status_3C1"] == "futuro", sid
    # colunas 3B-P preservadas (histórico): transições continuam futuras no perfil 3B-P
    for sid in ("y", "z", "R_up", "S_up", "T_up"):
        assert SIM[sid]["status_3BP"] == "futuro", sid


def test_catalogo_3c1_codigo_pyomo_existe_no_modelo():
    pytest.importorskip("pyomo", exc_type=ImportError)
    from ems_v2 import fixtures_3c1 as Y
    from ems_v2.milp.modelo_3c1 import construir_modelo_3c1
    m = construir_modelo_3c1(Y.caso_h()).modelo
    for sid, s in SIM.items():
        if s["codigo_3C1"].startswith("pyomo:"):
            nome = s["codigo_3C1"].split(":", 1)[1]
            assert hasattr(m, nome) or nome in ("P_c", "P_d", "z_b", "e", "ell", "d"), sid


def test_modulos_3c1_sem_pyomo_seeds2_ou_ui():
    mods = ["ems_v2.compromisso", "ems_v2.compromisso.contrato", "ems_v2.compromisso.memoria", "ems_v2.compromisso.preflight", "ems_v2.compromisso.auditor",
            "ems_v2.ponte.compromisso", "ems_v2.fixtures_3c1", "ems_v2.milp.resultado_3c1"]
    proib = ["pyomo", "highspy", "seeds2", "streamlit", "ems_integration", "numpy", "pandas", "scipy"]
    codigo = (f"import sys, json, importlib\n[importlib.import_module(m) for m in {mods!r}]\n"
              f"print(json.dumps([p for p in {proib!r} if p in sys.modules]))\n")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, env=env, check=True)
    assert json.loads(out.stdout.strip().splitlines()[-1]) == []


def test_nucleo_3a_3bp_nao_conhece_o_3c1():
    for mod in ("contracts.py", "audit.py", "reference.py", "milp/modelo.py", "milp/solver.py", "milp/config.py",
                "milp/integridade.py", "milp/resultado.py"):
        txt = (RAIZ / "ems_v2" / mod).read_text(encoding="utf-8")
        assert "3c1" not in txt.lower() and "compromisso." not in txt, mod
