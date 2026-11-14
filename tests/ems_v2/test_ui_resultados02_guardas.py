"""UI-RESULTADOS-02 — a exceção nominal das guardas é ESTRITA: nomes, status e linhas removidas listadas em
``integracao_v2/ui.py`` e no gancho da política anterior; caminhos científicos intocados."""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from unittest import mock

import pytest

import ui_resultados02_guard_policy as G

RAIZ = Path(__file__).resolve().parents[2]


def _base_disponivel() -> bool:
    try:
        subprocess.run(["git", "cat-file", "-e", G.BASE + "^{commit}"], cwd=RAIZ, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def test_politica_estrita_por_nome_e_status():
    for nome in G.MODIFICADOS | G.ADICIONADOS:
        assert not nome.endswith("/") and "*" not in nome and Path(nome).suffix, nome
    assert not (G.MODIFICADOS & G.ADICIONADOS)
    assert not any(n.startswith(("ems_v2/", "seeds2/report/", "models/")) for n in G.MODIFICADOS | G.ADICIONADOS)
    linhas = [["M", "integracao_v2/ui.py"], ["D", "integracao_v2/ui.py"], ["M", "integracao_v2/trama_frame.py"],
              ["A", "integracao_v2/relatorio_visual.py"], ["M", "integracao_v2/relatorio_visual.py"],
              ["M", "seeds2/ui/report_exports.py"], ["M", "integracao_v2/documentos.py"]]
    with mock.patch.object(G, "remocoes_nao_conformes", return_value={}):
        assert G.filter_changes(RAIZ, linhas) == [
            ["D", "integracao_v2/ui.py"], ["M", "integracao_v2/trama_frame.py"], ["M", "integracao_v2/relatorio_visual.py"],
            ["M", "seeds2/ui/report_exports.py"], ["M", "integracao_v2/documentos.py"]]
    with mock.patch.object(G, "remocoes_nao_conformes", return_value={"integracao_v2/ui.py": ["x"]}):
        assert ["M", "integracao_v2/ui.py"] in G.filter_changes(RAIZ, linhas)


def test_componente_continua_sem_importar_alem_do_streamlit_e_sem_o_motor():
    fonte = (RAIZ / "seeds2/ui/trama.py").read_text(encoding="utf-8")
    mods = {n.names[0].name.split(".")[0] if isinstance(n, ast.Import) else (n.module or "").split(".")[0]
            for n in ast.walk(ast.parse(fonte)) if isinstance(n, (ast.Import, ast.ImportFrom))}
    assert mods <= {"__future__", "pathlib", "streamlit"}, mods
    for arq in ("integracao_v2/relatorio_visual.py", "integracao_v2/svg_pdf.py"):
        texto = (RAIZ / arq).read_text(encoding="utf-8")
        assert "ems" + "_v2" not in texto.replace("ems" + "_v2_", ""), arq     # nunca o pacote do motor
        assert not any(m in texto for m in ("import pyomo", "import highspy", "import streamlit")), arq


@pytest.mark.skipif(not _base_disponivel(), reason="base da missão indisponível neste clone")
def test_auditoria_explicita_da_missao():
    rel = G.auditar_missao(RAIZ)
    assert rel["remocoes_nao_conformes"] == {}, rel["remocoes_nao_conformes"]
    assert rel["intocados_violados"] == [], rel["intocados_violados"]
    with mock.patch.dict(G.REMOVIDAS, {"integracao_v2/ui.py": {""}}):
        assert "integracao_v2/ui.py" in G.remocoes_nao_conformes(RAIZ)
