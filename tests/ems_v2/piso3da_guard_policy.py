"""Piso 3D-A — exceção NOMINAL das guardas de isolamento (contradição C-3DA-01, docs/ems_v2/INTEGRACAO_3DA.md §7).

As guardas dos Pisos 3A–3C-4 afirmam que "a aplicação não referencia ``ems_v2``" e que ``seeds2`` não muda desde a
base de cada piso: eram verdadeiras enquanto a integração NÃO estava autorizada. O Piso 3D-A é exatamente a integração
operacional autorizada pelo responsável; sem exceção, nenhuma integração é possível. Regras desta exceção:

* nenhuma guarda global é removida nem enfraquecida: os mesmos testes continuam ativos sobre todo o repositório;
* a exceção é por NOME EXATO e STATUS (``M`` × ``A``) — nunca diretórios, padrões ou renomeações/remoções —, com uma
  única área própria: o pacote ``integracao_v2/`` (a camada de integração, fora dos alvos das guardas anteriores);
* ``ems_v2/`` não entra na exceção: o motor auditado continua byte a byte o da base (``test_piso3da_guardas``);
* ``seeds2`` continua sem o literal ``ems_v2`` (a guarda 3C-4 ``test_aplicacao_nao_importa_o_ems_hierarquico`` permanece
  IDÊNTICA e verdadeira): a aplicação só alcança o motor pela camada ``integracao_v2``, por import tardio;
* os arquivos fixados por hash pelas políticas anteriores (eólica, estabilização, CI-01) NÃO são tocados.

Este módulo não gera nem atualiza hashes e não consulta a rede.
"""
from __future__ import annotations

from pathlib import Path

BASE = "a636350271fa35a9e20d000f2d2121502c132913"          # main no início do Piso 3D-A (merge do PR #20)
PACOTE_INTEGRACAO = "integracao_v2/"
# Arquivos EXISTENTES na base alterados pelo 3D-A (nome exato; somente modificação).
MODIFICADOS = frozenset({
    "seeds2/operation/scenarios.py",        # chaves opcionais ``engine``/``milp_mpc`` do cenário; estado da etapa 03
    "seeds2/operation/preflight.py",        # o preflight V1.6 RECUSA cenários que selecionam o motor V2
    "seeds2/ui/execution_ui.py",            # despacho por motor nas etapas 03/04 e na leitura da rodada
    "seeds2/ui/archive_ui.py",              # estratégia V2 e custo rotulado na consulta de estudos arquivados
    "tests/ems_v2/test_ems_v2_isolamento.py",      # guarda 3A: exceção nominal para a camada de integração
    "tests/ems_v2/stabilization_guard_policy.py",  # encadeia este filtro (mesmo mecanismo do CI-01)
})
# Arquivos NOVOS do 3D-A dentro dos alvos das guardas anteriores (nome exato; somente adição).
ADICIONADOS = frozenset({
    "tests/piso3da_util.py", "tests/test_piso3da_preflight.py", "tests/test_piso3da_execucao.py",
    "tests/test_piso3da_app.py", "tests/ems_v2/piso3da_guard_policy.py", "tests/ems_v2/test_piso3da_guardas.py",
})
# Arquivos Python FORA de ``ems_v2/`` e ``tests/ems_v2/`` autorizados a mencionar o pacote do motor (guarda 3A).
REFERENCIAM_O_MOTOR = frozenset({"tests/piso3da_util.py", "tests/test_piso3da_preflight.py",
                                 "tests/test_piso3da_execucao.py", "tests/test_piso3da_app.py"})


def referencia_autorizada(rel: str) -> bool:
    """A guarda 3A continua varrendo TODO arquivo Python; só a camada de integração e seus testes nominais passam."""
    return rel.startswith(PACOTE_INTEGRACAO) or rel in REFERENCIAM_O_MOTOR


def filter_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
    """Política pura: nomes E status exatos. Remoção, renomeação ou qualquer outro arquivo continuam visíveis para a
    guarda de isolamento original."""
    _ = root
    return [row for row in changes if not (len(row) == 2 and (
        (row[0] == "M" and row[1] in MODIFICADOS) or (row[0] == "A" and row[1] in ADICIONADOS)))]


# ------------------------------------------------------------------------------------------------ auditoria explícita
# Caminhos que o 3D-A NÃO pode tocar (motor auditado, ciência e entradas do V1.6, dependências, runner V1.6 e demais
# arquivos fixados por políticas anteriores). Verificados SÓ pela auditoria explícita da missão (C-EOL-01: uma guarda
# permanente contra um commit-base congelaria pisos futuros autorizados).
INTOCADOS = ("ems_v2", "models", "h2_pemfc", "simulation", "config", "ems_integration", "reference_models", "visualization",
             "orchestrator_runtime.py", "orchestrator_app.py", "app.py", "ems_app.py", "wind_app.py", "thermal_app.py",
             "battery_app.py", "h2_app.py", "mix_app.py", "requirements.txt", "requirements-ems_v2.txt",
             "seeds2/operation/runner.py", "seeds2/operation/strategy.py", "seeds2/operation/mission.py",
             "seeds2/operation/forecasts.py", "seeds2/microgrid", "seeds2/archive", "seeds2/report", "seeds2/ui/main.py",
             "seeds2/ui/operations.py", "seeds2/ui/equipment.py", ".github")
OUTROS_PERMITIDOS = ("docs/", "tools/e2e/", "CLAUDE.md", "PARAMIJEFE.md")


def auditar_missao(root: Path, base: str = BASE, head: str = "HEAD", *, incluir_arvore_de_trabalho: bool = True) -> dict:
    """Auditoria EXPLÍCITA do diff da missão 3D-A (base → head). Nunca é restrição permanente sobre pisos futuros."""
    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout

    alvo = [head] if not incluir_arvore_de_trabalho else []
    linhas = [ln.split("\t") for ln in git("diff", "--name-status", "--no-renames", base, *alvo).splitlines() if ln.strip()]
    if incluir_arvore_de_trabalho:
        linhas += [["A", p] for p in git("ls-files", "--others", "--exclude-standard").split()]
    intocados = [ln for ln in linhas if any(ln[1] == p or ln[1].startswith(p.rstrip("/") + "/") for p in INTOCADOS)]
    assert not intocados, f"caminhos protegidos alterados pela missão 3D-A: {intocados}"
    fora = [ln for ln in linhas if not (
        (ln[0] == "M" and ln[1] in MODIFICADOS) or (ln[0] == "A" and ln[1] in ADICIONADOS)
        or (ln[0] == "A" and ln[1].startswith(PACOTE_INTEGRACAO)) or ln[1].startswith(OUTROS_PERMITIDOS))]
    assert not fora, f"alterações fora da lista nominal do 3D-A: {fora}"
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

    ap = argparse.ArgumentParser(description="Auditar explicitamente o diff da missão 3D-A; não congela pisos futuros.")
    ap.add_argument("--audit-mission-base", default=BASE)
    ap.add_argument("--head", default="HEAD")
    a = ap.parse_args()
    rel = auditar_missao(Path(__file__).resolve().parents[2], a.audit_mission_base, a.head)
    assert rel["ems_v2_base"] == rel["ems_v2_head"], "ems_v2 alterado nesta missão"
    print(json.dumps(rel, indent=1, ensure_ascii=False))
    print("Auditoria explícita 3D-A: ems_v2 idêntico à base; V1.6 e arquivos protegidos intocados; alterações nominais.")
