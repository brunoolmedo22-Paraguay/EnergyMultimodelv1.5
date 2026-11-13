"""Piso 3D-B — guardas da Partitura / motor Trama: exceção nominal C-3DB-01, isolamento do componente e do marco de dados."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import piso3db_guard_policy as POL  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
ESTATICOS = [RAIZ / p for p in POL.COMPONENTE if not p.endswith(".py")]


def test_politica_e_nominal_e_nao_cobre_diretorios():
    for nome in POL.MODIFICADOS | POL.ADICIONADOS:
        assert not nome.endswith("/") and "*" not in nome and Path(nome).suffix, nome
    assert not (POL.MODIFICADOS & POL.ADICIONADOS)
    assert not any(n.startswith("ems_v2/") for n in POL.MODIFICADOS | POL.ADICIONADOS)
    assert POL.filter_changes(RAIZ, [["M", "seeds2/ui/trama.py"], ["A", "seeds2/ui/outro.py"], ["D", "seeds2/ui/trama.py"],
                                     ["A", "seeds2/ui/trama.py"]]) == [["M", "seeds2/ui/trama.py"],
                                                                       ["A", "seeds2/ui/outro.py"], ["D", "seeds2/ui/trama.py"]]


def test_componente_nao_menciona_o_motor_nem_importa_alem_do_streamlit():
    fonte = (RAIZ / "seeds2/ui/trama.py").read_text(encoding="utf-8")
    assert "ems" + "_v2" not in fonte and "integracao" + "_v2" not in fonte
    mods = {n.names[0].name.split(".")[0] if isinstance(n, ast.Import) else (n.module or "").split(".")[0]
            for n in ast.walk(ast.parse(fonte)) if isinstance(n, (ast.Import, ast.ImportFrom))}
    assert mods <= {"__future__", "pathlib", "streamlit"}, mods


def test_marco_de_dados_nao_importa_solver_interface_nem_modelos():
    fonte = (RAIZ / "integracao_v2/trama_frame.py").read_text(encoding="utf-8")
    mods = {n.names[0].name.split(".")[0] if isinstance(n, ast.Import) else (n.module or "").split(".")[0]
            for n in ast.walk(ast.parse(fonte)) if isinstance(n, (ast.Import, ast.ImportFrom))}
    assert mods <= {"__future__", "hashlib", "json", "math", ""}, mods          # "" = import relativo (registro)
    assert not re.search(r"\b(pyomo|highspy|streamlit|sqlite3|h2_pemfc|models|simulation)\b", fonte)
    # O marco só acrescenta a si próprio ao que a leitura da evidência (registro) já carrega; nunca solver nem interface.
    cod = ("import sys; from integracao_v2 import registro; antes = set(sys.modules); "
           "from integracao_v2 import trama_frame; novos = set(sys.modules) - antes - {'integracao_v2.trama_frame'}; "
           "ruins = sorted(novos) + [m for m in ('pyomo', 'highspy', 'streamlit') if m in sys.modules]; "
           "print(ruins); raise SystemExit(1 if ruins else 0)")
    r = subprocess.run([sys.executable, "-c", cod], cwd=RAIZ, capture_output=True, text=True,
                       env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert r.returncode == 0, r.stdout + r.stderr


def test_estaticos_sem_recursos_externos_e_estilos_sob_o_prefixo():
    for arq in ESTATICOS:
        texto = arq.read_text(encoding="utf-8")
        urls = set(re.findall(r"https?://[^\s\"'`)]+", texto)) - {"http://www.w3.org/2000/svg"}
        assert not urls, (arq.name, urls)                       # nenhum CDN, fonte ou serviço externo
        assert "@import" not in texto and "eval(" not in texto and "innerHTML = data" not in texto
    css = (RAIZ / "seeds2/ui/static/trama/trama.css").read_text(encoding="utf-8")
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    corpo = re.sub(r"@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", sem_comentarios)
    corpo = re.sub(r"@media[^{]*\{", "", corpo)
    for seletor in re.findall(r"(?:^|\})\s*([^{}@]+)\{", corpo):
        for parte in seletor.split(","):
            assert parte.strip().startswith(".pt"), parte.strip()   # nenhuma regra fora do instrumento


def test_auditoria_explicita_do_diff_da_missao():
    try:
        subprocess.run(["git", "cat-file", "-e", POL.BASE + "^{commit}"], cwd=RAIZ, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("base do Piso 3D-B indisponível neste clone")
    rel = POL.auditar_missao(RAIZ)
    assert not rel["intocados_violados"], rel["intocados_violados"]
