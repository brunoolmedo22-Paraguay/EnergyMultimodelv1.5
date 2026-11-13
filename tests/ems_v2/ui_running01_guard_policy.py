"""UI-RUNNING-01 — exceção NOMINAL das guardas de isolamento para o modal de acompanhamento da execução V2.

Mesmo mecanismo das exceções anteriores (nomes EXATOS e status ``M`` × ``A``), encadeada no fim da política do
UI-REDESIGN-01; nenhuma guarda global é removida ou enfraquecida. A missão é de APRESENTAÇÃO + um cancelamento
COOPERATIVO pela API EXISTENTE do armazenamento (``fail_run(estado='interrompida')``): ``ems_v2/``, o runner V2
(``integracao_v2/execucao.py``), modelos físicos, motor V1.6, armazenamento e contratos ficam intocados. Os arquivos de
interface alterados (``integracao_v2/ui.py``, ``seeds2/ui/execution_ui.py``, ``static/trama/trama.css``) já estão nas
políticas anteriores com o mesmo status e por isso não aparecem aqui.

Este módulo não gera nem atualiza hashes e não consulta a rede.
"""
from __future__ import annotations

from pathlib import Path

BASE = "9d2bcf0"                                        # main no início da missão (merge do PR #26)
MODIFICADOS: frozenset = frozenset()
ADICIONADOS = frozenset({"seeds2/ui/static/trama/execucao.js", "tests/test_ui_running01.py",
                         "tests/ems_v2/ui_running01_guard_policy.py"})


def filter_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
    """Política pura: nomes E status exatos. Remoção, renomeação ou qualquer outro arquivo continuam visíveis."""
    restantes = [row for row in changes if not (len(row) == 2 and (
        (row[0] == "M" and row[1] in MODIFICADOS) or (row[0] == "A" and row[1] in ADICIONADOS)))]
    from ui_finish01_guard_policy import filter_changes as filter_finish01          # exceção nominal UI-FINISH-01
    return filter_finish01(root, restantes)


INTOCADOS = ("ems_v2", "models", "h2_pemfc", "simulation", "config", "ems_integration", "reference_models", "visualization",
             "integracao_v2/execucao.py", "integracao_v2/registro.py", "integracao_v2/montagem.py", "integracao_v2/preflight.py",
             "integracao_v2/estrategia.py", "integracao_v2/renovaveis.py", "integracao_v2/curva_h2.py",
             "integracao_v2/pemfc_dinamica.py", "integracao_v2/trama_frame.py", "orchestrator_runtime.py", "orchestrator_app.py",
             "app.py", "requirements.txt", "requirements-ems_v2.txt", "seeds2/operation", "seeds2/microgrid", "seeds2/archive",
             "seeds2/report", "seeds2/ui/main.py", "seeds2/ui/operations.py", ".github")


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
