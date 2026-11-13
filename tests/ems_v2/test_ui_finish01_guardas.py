"""UI-FINISH-01 — a exceção nominal das guardas é ESTRITA: nomes, status e a lista explícita de linhas removidas de
``seeds2/report/dossier.py`` e ``seeds2/ui/report_exports.py`` (qualquer outra remoção volta a falhar)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

import ui_finish01_guard_policy as G

RAIZ = Path(__file__).resolve().parents[2]


def _base_disponivel() -> bool:
    try:
        subprocess.run(["git", "cat-file", "-e", G.BASE + "^{commit}"], cwd=RAIZ, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.mark.skipif(not _base_disponivel(), reason="base do UI-FINISH-01 indisponível neste clone")
def test_remocoes_conformes_e_politica_estrita():
    assert G.removidas_fora_da_lista(RAIZ) == {}
    with mock.patch.dict(G.REMOVIDAS, {"seeds2/report/dossier.py": {""}}):
        assert "seeds2/report/dossier.py" in G.removidas_fora_da_lista(RAIZ)
        assert G.filter_intocados(RAIZ, [["M", "seeds2/report/dossier.py"]]) == [["M", "seeds2/report/dossier.py"]]
        assert G.filter_changes(RAIZ, [["M", "seeds2/report/dossier.py"]]) == [["M", "seeds2/report/dossier.py"]]
    assert G.filter_changes(RAIZ, [["M", "seeds2/report/dossier.py"], ["D", "seeds2/report/dossier.py"],
                                   ["M", "seeds2/report/run_pdf.py"]]) == [["D", "seeds2/report/dossier.py"],
                                                                            ["M", "seeds2/report/run_pdf.py"]]


@pytest.mark.skipif(not _base_disponivel(), reason="base do UI-FINISH-01 indisponível neste clone")
def test_auditoria_explicita_da_missao():
    rel = G.auditar_missao(RAIZ)
    assert rel["remocoes_fora_da_lista"] == {}
    assert [ln for ln in rel["intocados_violados"] if ln[1] != "requirements.txt"] == []   # C-DEPLOY-01: não aplicada
