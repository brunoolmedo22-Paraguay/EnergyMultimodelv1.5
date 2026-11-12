"""Piso 3D-B — exceção NOMINAL das guardas de isolamento para a Partitura / motor gráfico Trama (C-3DB-01).

Mesmo mecanismo das exceções C-3DA-01, C-3DA2R-01 e C-3DA2H-00: nomes EXATOS e status (``M`` × ``A``), nenhuma guarda
global removida ou enfraquecida. O Piso 3D-B é de APRESENTAÇÃO: ``ems_v2/``, os modelos físicos, o motor V1.6, o
armazenamento e os contratos de dados ficam fora da exceção (e intocados). O marco de dados Trama
(``integracao_v2/trama_frame.py``) e a chamada em ``integracao_v2/ui.py`` vivem na camada de integração, que não é alvo das
guardas anteriores; o componente (``seeds2/ui/trama.py`` + ``seeds2/ui/static/trama/``) não menciona o pacote do motor.

Este módulo não gera nem atualiza hashes e não consulta a rede.
"""
from __future__ import annotations

from pathlib import Path

BASE = "724d2351ebe4213ed3aa93675c137f7170d260bd"          # main no início do Piso 3D-B (merge do PR #23)
PACOTE_INTEGRACAO = "integracao_v2/"
# Arquivos EXISTENTES na base, dentro dos alvos das guardas anteriores, alterados pelo 3D-B (somente modificação).
MODIFICADOS = frozenset({
    "tests/ems_v2/piso3da2h_guard_policy.py",    # encadeia este filtro (regras do 3D-A2-H inalteradas)
})
# Arquivos NOVOS do 3D-B dentro dos alvos das guardas anteriores (somente adição).
COMPONENTE = ("seeds2/ui/trama.py", "seeds2/ui/static/trama/trama.js", "seeds2/ui/static/trama/partitura.js",
              "seeds2/ui/static/trama/trama.css")
TESTES_3DB = ("tests/test_piso3db_trama.py", "tests/test_piso3db_app.py", "tests/piso3db_util.py",
              "tests/test_piso3db_nd.py", "tests/test_piso3db_lentes.py",          # 3D-B3: N/D e lentes
              "tests/test_piso3db_e2e_servidor.py")                                # limpeza dos servidores E2E
ADICIONADOS = frozenset({*COMPONENTE, *TESTES_3DB, "tests/ems_v2/piso3db_guard_policy.py",
                         "tests/ems_v2/test_piso3db_guardas.py"})
# Nenhum arquivo do 3D-B fora de ``ems_v2/`` e ``tests/ems_v2/`` menciona o pacote do motor (guarda 3A).
REFERENCIAM_O_MOTOR: frozenset = frozenset()


def referencia_autorizada(rel: str) -> bool:
    return rel in REFERENCIAM_O_MOTOR


def filter_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
    """Política pura: nomes E status exatos. Remoção, renomeação ou qualquer outro arquivo continuam visíveis."""
    _ = root
    return [row for row in changes if not (len(row) == 2 and (
        (row[0] == "M" and row[1] in MODIFICADOS) or (row[0] == "A" and row[1] in ADICIONADOS)))]


# ------------------------------------------------------------------------------------------------ auditoria explícita
INTOCADOS = ("ems_v2", "models", "h2_pemfc", "simulation", "config", "ems_integration", "reference_models", "visualization",
             "orchestrator_runtime.py", "orchestrator_app.py", "app.py", "ems_app.py", "wind_app.py", "thermal_app.py",
             "battery_app.py", "h2_app.py", "mix_app.py", "requirements.txt", "requirements-ems_v2.txt",
             "seeds2/operation", "seeds2/microgrid", "seeds2/archive", "seeds2/report", ".github",
             "integracao_v2/registro.py", "integracao_v2/execucao.py", "integracao_v2/montagem.py",
             "integracao_v2/preflight.py", "integracao_v2/estrategia.py", "integracao_v2/renovaveis.py",
             "integracao_v2/curva_h2.py", "integracao_v2/pemfc_dinamica.py")
INTEGRACAO_3DB = {"integracao_v2/ui.py": "M", "integracao_v2/trama_frame.py": "A"}
OUTROS_PERMITIDOS = ("docs/", "tools/e2e/", "CLAUDE.md", "PARAMIJEFE.md")


def auditar_missao(root: Path, base: str = BASE, head: str = "HEAD", *, incluir_arvore_de_trabalho: bool = True) -> dict:
    """Auditoria EXPLÍCITA do diff da missão 3D-B (base → head). Nunca é restrição permanente sobre pisos futuros."""
    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout

    alvo = [head] if not incluir_arvore_de_trabalho else []
    linhas = [ln.split("\t") for ln in git("diff", "--name-status", "--no-renames", base, *alvo).splitlines() if ln.strip()]
    if incluir_arvore_de_trabalho:
        linhas += [["A", p] for p in git("ls-files", "--others", "--exclude-standard").split()]
    intocados = [ln for ln in linhas if any(ln[1] == p or ln[1].startswith(p.rstrip("/") + "/") for p in INTOCADOS)]
    fora = [ln for ln in linhas if not (
        (ln[0] == "M" and ln[1] in MODIFICADOS) or (ln[0] == "A" and ln[1] in ADICIONADOS)
        or INTEGRACAO_3DB.get(ln[1]) == ln[0] or ln[1].startswith(OUTROS_PERMITIDOS)) and ln not in intocados]
    return {"base": base, "head": head, "alterados": sorted(map(tuple, linhas)), "intocados_violados": intocados,
            "fora_da_politica": fora, "ok": not intocados and not fora}


__all__ = ["ADICIONADOS", "BASE", "COMPONENTE", "INTEGRACAO_3DB", "INTOCADOS", "MODIFICADOS", "PACOTE_INTEGRACAO",
           "REFERENCIAM_O_MOTOR", "auditar_missao", "filter_changes", "referencia_autorizada"]

if __name__ == "__main__":
    import json

    rel = auditar_missao(Path(__file__).resolve().parents[2])
    print(json.dumps(rel, ensure_ascii=False, indent=1))
    raise SystemExit(0 if rel["ok"] else 1)
