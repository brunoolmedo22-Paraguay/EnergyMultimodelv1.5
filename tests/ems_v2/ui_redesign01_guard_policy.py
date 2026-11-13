"""UI-REDESIGN-01 — exceção NOMINAL das guardas de isolamento para a revisão de navegação, etapas e Planta.

Mesmo mecanismo das exceções C-3DA-01, C-3DA2R-01, C-3DA2H-00 e C-3DB-01: nomes EXATOS e status (``M`` × ``A``),
encadeada no fim da política do Piso 3D-B; nenhuma guarda global é removida ou enfraquecida. A missão é de APRESENTAÇÃO:
``ems_v2/``, modelos físicos, motor V1.6, armazenamento, contratos e os arquivos fixados por SHA-256 ficam intocados.
Os arquivos de interface alterados (``seeds2/ui/shell.py``, ``operation_center.py``, ``trama.py`` e os estáticos de
``static/trama/``) já estão na política do 3D-B com o mesmo status e por isso não aparecem aqui.

Este módulo não gera nem atualiza hashes e não consulta a rede.
"""
from __future__ import annotations

from pathlib import Path

BASE = "8cbd15c7d15b4e698d2ae1a3fb17bceb089fbcee"       # main no início da missão (merge do PR #24)
# Teste ANTIGO com UMA asserção adaptada à decisão do responsável: o texto do Centro de Operação deixou de apontar a
# «Simulação (console V1.6)», retirada da navegação; agora aponta as bancadas (barra lateral).
MODIFICADOS = frozenset({"tests/test_seeds2_piso2a_app.py"})
ADICIONADOS = frozenset({"tests/test_ui_redesign01.py", "tests/ems_v2/ui_redesign01_guard_policy.py"})


def filter_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
    """Política pura: nomes E status exatos. Remoção, renomeação ou qualquer outro arquivo continuam visíveis."""
    _ = root
    return [row for row in changes if not (len(row) == 2 and (
        (row[0] == "M" and row[1] in MODIFICADOS) or (row[0] == "A" and row[1] in ADICIONADOS)))]


INTOCADOS = ("ems_v2", "models", "h2_pemfc", "simulation", "config", "ems_integration", "reference_models", "visualization",
             "integracao_v2", "orchestrator_runtime.py", "orchestrator_app.py", "app.py", "ems_app.py", "wind_app.py",
             "thermal_app.py", "battery_app.py", "h2_app.py", "mix_app.py", "requirements.txt", "requirements-ems_v2.txt",
             "seeds2/operation", "seeds2/microgrid", "seeds2/archive", "seeds2/report", "seeds2/ui/main.py",
             "seeds2/ui/operations.py", "seeds2/ui/static/inventory.js", "seeds2/ui/static/techpicker.js",
             "seeds2/ui/static/kit.css", "seeds2/ui/gestor.py", "seeds2/ui/home.py", ".github")


def auditar_missao(root: Path, base: str = BASE) -> dict:
    """Auditoria EXPLÍCITA do diff desta missão (base → árvore de trabalho): nada nos caminhos intocados."""
    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout

    linhas = [ln.split("\t") for ln in git("diff", "--name-status", "--no-renames", base).splitlines() if ln.strip()]
    linhas += [["A", p] for p in git("ls-files", "--others", "--exclude-standard").split()]
    intocados = [ln for ln in linhas if any(ln[1] == p or ln[1].startswith(p.rstrip("/") + "/") for p in INTOCADOS)]
    return {"base": base, "alterados": sorted(map(tuple, linhas)), "intocados_violados": intocados, "ok": not intocados}


__all__ = ["ADICIONADOS", "BASE", "INTOCADOS", "MODIFICADOS", "auditar_missao", "filter_changes"]

if __name__ == "__main__":
    import json

    print(json.dumps(auditar_missao(Path(__file__).resolve().parents[2]), ensure_ascii=False, indent=1))
