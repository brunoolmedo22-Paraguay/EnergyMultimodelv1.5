"""EXEMPLOS-PERSISTENTES-01 — a exceção nominal das guardas é ESTRITA: nomes, status, remoções conformes em
``session.py`` e ``gestor.py`` (``registry.py`` intocado), e só instantâneas diretamente em ``seeds2/exemplos/``."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

import exemplos01_guard_policy as G

RAIZ = Path(__file__).resolve().parents[2]


def _base_disponivel() -> bool:
    try:
        subprocess.run(["git", "cat-file", "-e", G.BASE + "^{commit}"], cwd=RAIZ, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def test_politica_estrita_por_nome_e_status():
    linhas = [["M", "seeds2/ui/gestor.py"], ["D", "seeds2/ui/gestor.py"], ["M", "seeds2/microgrid/store.py"],
              ["A", "seeds2/exemplos/C1.seeds2snapshot.zip"], ["A", "seeds2/exemplos/sub/C1.seeds2snapshot.zip"],
              ["A", "seeds2/exemplos/C1.seeds2backup.zip"], ["M", "seeds2/exemplos/C1.seeds2snapshot.zip"],
              ["A", "seeds2/microgrid/snapshot.py"]]
    with mock.patch.object(G, "remocoes_nao_conformes", return_value={}):
        assert G.filter_changes(RAIZ, linhas) == [
            ["D", "seeds2/ui/gestor.py"], ["M", "seeds2/microgrid/store.py"],
            ["A", "seeds2/exemplos/sub/C1.seeds2snapshot.zip"], ["A", "seeds2/exemplos/C1.seeds2backup.zip"],
            ["M", "seeds2/exemplos/C1.seeds2snapshot.zip"]]


def test_remocao_nao_conforme_volta_a_falhar():
    with mock.patch.object(G, "remocoes_nao_conformes", return_value={"seeds2/ui/session.py": ["x"]}):
        assert G.filter_changes(RAIZ, [["M", "seeds2/ui/session.py"], ["M", "seeds2/ui/gestor.py"],
                                       ["M", "seeds2/microgrid/registry.py"]]) == [
            ["M", "seeds2/ui/session.py"], ["M", "seeds2/microgrid/registry.py"]]


def test_excecao_fv_so_para_blob_do_pr30():
    linhas = [["M", "integracao_v2/renovaveis.py"], ["M", "integracao_v2/preflight.py"],
              ["D", "integracao_v2/renovaveis.py"]]
    with mock.patch.object(G.subprocess, "run") as git:
        git.return_value.stdout = G.FV_ZERO_BLOB_SHA + "\n"
        assert G.filter_fv_zero_autorizado(RAIZ, linhas) == linhas[1:]
        git.return_value.stdout = "0000000000000000000000000000000000000000\n"
        assert G.filter_fv_zero_autorizado(RAIZ, linhas) == linhas


def test_excecao_da_ponte_fv_so_para_blob_autorizado():
    linhas = [["M", "ems_v2/ponte/requisitos.py"], ["M", "ems_v2/ponte/inventario.py"],
              ["D", "ems_v2/ponte/requisitos.py"]]
    with mock.patch.object(G.subprocess, "run") as git:
        git.return_value.stdout = G.FV_PONTE_ZERO_BLOB_SHA + "\n"
        assert G.filter_ponte_zero_autorizado(RAIZ, linhas) == linhas[1:]
        git.return_value.stdout = "0000000000000000000000000000000000000000\n"
        assert G.filter_ponte_zero_autorizado(RAIZ, linhas) == linhas


@pytest.mark.skipif(not _base_disponivel(), reason="base da missão indisponível neste clone")
def test_auditoria_explicita_da_missao():
    rel = G.auditar_missao(RAIZ)
    assert rel["remocoes_nao_conformes"] == {}, rel["remocoes_nao_conformes"]
    assert rel["intocados_violados"] == [], rel["intocados_violados"]
    with mock.patch.dict(G.REMOVIDAS, {"seeds2/ui/session.py": {""}}):
        assert "seeds2/ui/session.py" in G.remocoes_nao_conformes(RAIZ)
