"""Piso 3D-A2-R — exceção NOMINAL das guardas de isolamento para a integração das renováveis (C-3DA2R-01).

Mesmo mecanismo e mesmas regras da exceção C-3DA-01 (``piso3da_guard_policy``): nomes EXATOS e status (``M`` × ``A``),
nenhuma guarda global removida ou enfraquecida, ``ems_v2/`` fora da exceção (motor auditado byte a byte o da base),
``seeds2`` sem o literal do pacote do motor, arquivos fixados por hash das políticas anteriores intocados. A camada
``integracao_v2/`` não é alvo das guardas anteriores; os modelos físicos (``models/``, ``simulation/``, ``config/``) são só
LIDOS pelo adaptador ``integracao_v2/renovaveis.py`` e continuam INTOCADOS (auditoria explícita abaixo).

Este módulo não gera nem atualiza hashes e não consulta a rede.
"""
from __future__ import annotations

from pathlib import Path

BASE = "7eb29e590a75f79ef7ab2a608727645c73960f50"          # main no início do Piso 3D-A2-R (merge do PR #21)
PACOTE_INTEGRACAO = "integracao_v2/"
# Arquivos EXISTENTES na base, dentro dos alvos das guardas anteriores, alterados pelo 3D-A2-R (somente modificação).
MODIFICADOS = frozenset({
    "tests/ems_v2/piso3da_guard_policy.py",      # encadeia este filtro (regras do 3D-A inalteradas)
})
# Arquivos NOVOS do 3D-A2-R dentro dos alvos das guardas anteriores (somente adição).
ADICIONADOS = frozenset({
    "tests/piso3da2r_util.py", "tests/test_piso3da2r_renovaveis.py", "tests/test_piso3da2r_execucao.py",
    "tests/test_piso3da2r_app.py", "tests/ems_v2/piso3da2r_guard_policy.py", "tests/ems_v2/test_piso3da2r_guardas.py",
})
# Arquivos Python FORA de ``ems_v2/`` e ``tests/ems_v2/`` autorizados a mencionar o pacote do motor (guarda 3A).
REFERENCIAM_O_MOTOR = frozenset({"tests/piso3da2r_util.py", "tests/test_piso3da2r_renovaveis.py",
                                 "tests/test_piso3da2r_execucao.py", "tests/test_piso3da2r_app.py"})


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
             "seeds2/operation", "seeds2/microgrid", "seeds2/archive", "seeds2/report", "seeds2/ui/main.py",
             "seeds2/ui", ".github",
             "tests/ems_v2/wind_guard_policy.py", "tests/ems_v2/ci01_guard_policy.py",
             "tests/ems_v2/stabilization_guard_policy.py", "tests/ems_v2/test_ems_v2_isolamento.py")
OUTROS_PERMITIDOS = ("docs/", "tools/e2e/", "CLAUDE.md", "PARAMIJEFE.md")


def auditar_missao(root: Path, base: str = BASE, head: str = "HEAD", *, incluir_arvore_de_trabalho: bool = True) -> dict:
    """Auditoria EXPLÍCITA do diff da missão 3D-A2-R (base → head). Nunca é restrição permanente sobre pisos futuros."""
    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout

    alvo = [head] if not incluir_arvore_de_trabalho else []
    linhas = [ln.split("\t") for ln in git("diff", "--name-status", "--no-renames", base, *alvo).splitlines() if ln.strip()]
    if incluir_arvore_de_trabalho:
        linhas += [["A", p] for p in git("ls-files", "--others", "--exclude-standard").split()]
    intocados = [ln for ln in linhas if any(ln[1] == p or ln[1].startswith(p.rstrip("/") + "/") for p in INTOCADOS)]
    assert not intocados, f"caminhos protegidos alterados pela missão 3D-A2-R: {intocados}"
    fora = [ln for ln in linhas if not (
        (ln[0] == "M" and ln[1] in MODIFICADOS) or (ln[0] == "A" and ln[1] in ADICIONADOS)
        or ln[1].startswith(PACOTE_INTEGRACAO) or ln[1].startswith(OUTROS_PERMITIDOS))]
    assert not fora, f"alterações fora da lista nominal do 3D-A2-R: {fora}"
    assert all(ln[0] in ("A", "M") for ln in linhas), "remoção/renomeação não autorizada"
    return {"base": git("rev-parse", base).strip(), "head": git("rev-parse", head).strip(),
            "ems_v2_base": git("rev-parse", f"{base}:ems_v2").strip(), "ems_v2_head": git("rev-parse", f"{head}:ems_v2").strip(),
            "modificados": sorted(ln[1] for ln in linhas if ln[0] == "M"),
            "adicionados": sorted(ln[1] for ln in linhas if ln[0] == "A")}


__all__ = ["ADICIONADOS", "BASE", "INTOCADOS", "MODIFICADOS", "PACOTE_INTEGRACAO", "REFERENCIAM_O_MOTOR", "auditar_missao",
           "filter_changes", "referencia_autorizada"]

if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Auditar explicitamente o diff da missão 3D-A2-R; não congela pisos futuros.")
    ap.add_argument("--audit-mission-base", default=BASE)
    ap.add_argument("--head", default="HEAD")
    a = ap.parse_args()
    rel = auditar_missao(Path(__file__).resolve().parents[2], a.audit_mission_base, a.head)
    assert rel["ems_v2_base"] == rel["ems_v2_head"], "ems_v2 alterado nesta missão"
    print(json.dumps(rel, indent=1, ensure_ascii=False))
    print("Auditoria explícita 3D-A2-R: ems_v2 e modelos físicos idênticos à base; alterações nominais.")
