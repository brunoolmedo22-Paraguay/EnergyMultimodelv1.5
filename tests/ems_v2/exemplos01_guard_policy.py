"""EXEMPLOS-PERSISTENTES-01 — exceção NOMINAL das guardas para a instantânea completa e os exemplos persistentes.

Decisão do responsável (14/11/2026): botão GUARDAR COMPLETO no Gestor (instantânea ``.seeds2snapshot.zip`` = banco
inteiro da microrrede) e restauração automática, ao iniciar, das instantâneas versionadas em ``seeds2/exemplos/`` (o
disco do Streamlit Cloud é efímero). Mesmo mecanismo das exceções anteriores (nomes EXATOS e status ``M`` × ``A``),
encadeada no fim da política do UI-FINISH-01. Nenhuma guarda global é removida ou enfraquecida; ``ems_v2/``,
``integracao_v2/``, modelos físicos, motor V1.6, runner, ``seeds2/ui/main.py``/``operations.py`` e contratos ficam
intocados.

``seeds2/microgrid/registry.py`` NÃO é alterado (a restauração usa o ``_commit_new`` existente a partir de
``snapshot.restore_snapshot``). Dois arquivos de código protegido entram, com restrição EXTRA sobre as linhas removidas:

* ``seeds2/ui/session.py``: ``_registry_for`` passa a chamar ``exemplos.garantir_na_inicializacao`` (uma linha removida,
  listada);
* ``seeds2/ui/gestor.py``: botão GUARDAR COMPLETO, selo «Exemplo» e aviso de falhas (duas linhas removidas, listadas).

``tests/conftest.py`` ganha só ``SEEDS2_EXEMPLOS=0`` por padrão; ``ui_finish01_guard_policy.py`` (encadeamento e
auditoria) e ``piso3db_guard_policy.py`` (auditoria) recebem só o gancho; ``.gitignore`` ignora instantâneas fora da
pasta de exemplos.
Instantâneas ``seeds2/exemplos/*.seeds2snapshot.zip`` são ADIÇÕES autorizadas (exceção à regra 8 do ``CLAUDE.md``).

Este módulo não gera nem atualiza hashes e não consulta a rede.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

BASE = "c807a28"                                     # main no início da missão
MODIFICADOS = frozenset({"seeds2/ui/session.py", "seeds2/ui/gestor.py",
                         "tests/conftest.py", "tests/ems_v2/ui_finish01_guard_policy.py",
                         "tests/ems_v2/piso3db_guard_policy.py", ".gitignore"})
ADICIONADOS = frozenset({"seeds2/microgrid/snapshot.py", "seeds2/microgrid/exemplos.py", "seeds2/exemplos/README.md",
                         "tests/test_seeds2_snapshot.py", "tests/ems_v2/exemplos01_guard_policy.py",
                         "tests/ems_v2/test_exemplos01_guardas.py"})
PASTA_EXEMPLOS = "seeds2/exemplos/"
SUFIXO_EXEMPLO = ".seeds2snapshot.zip"
MOVIDO_SO: frozenset[str] = frozenset()                   # (nenhum arquivo nesta missão)
REMOVIDAS = {
    "seeds2/ui/session.py": {"return MicrogridRegistry(path)", ""},
    "seeds2/ui/gestor.py": {
        "f'<span class=\"gc-chip e-{escape(ems_key)}\" title=\"{escape(ems_detail)}\">{escape(EMS_LABELS[ems_key])}</span></div>'",
        "origin = ORIGIN_LABELS.get(entry.origin, entry.origin)", ""},
    "tests/conftest.py": {""},
}


def _diff(root: Path, base: str, arq: str) -> tuple[set[str], set[str]] | None:
    try:
        out = subprocess.run(["git", "diff", "-U0", base, "--", arq], cwd=root, capture_output=True, text=True,
                             check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None                                   # clone sem a base: a auditoria explícita é feita no PR
    rem = {ln[1:].strip() for ln in out.splitlines() if ln.startswith("-") and not ln.startswith("---")}
    add = {ln[1:].strip() for ln in out.splitlines() if ln.startswith("+") and not ln.startswith("+++")}
    return rem, add


def remocoes_nao_conformes(root: Path, base: str = BASE) -> dict:
    """{arquivo: linhas removidas desde ``base`` fora do permitido} (vazio = alteração conforme)."""
    out = {}
    for arq in MOVIDO_SO:
        d = _diff(root, base, arq)
        if d and (d[0] - d[1]):
            out[arq] = sorted(d[0] - d[1])
    for arq, ok in REMOVIDAS.items():
        d = _diff(root, base, arq)
        if d and (d[0] - ok):
            out[arq] = sorted(d[0] - ok)
    return out


def _exemplo(path: str) -> bool:
    return (path.startswith(PASTA_EXEMPLOS) and path.endswith(SUFIXO_EXEMPLO)
            and "/" not in path[len(PASTA_EXEMPLOS):])


def filter_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
    """Política pura: nomes E status exatos; código protegido só se as remoções forem conformes."""
    ruins = remocoes_nao_conformes(root)
    changes = filter_ponte_zero_autorizado(root, changes)
    return [row for row in changes if not (len(row) == 2 and (
        (row[0] == "M" and row[1] in MODIFICADOS and row[1] not in ruins)
        or (row[0] == "A" and (row[1] in ADICIONADOS or _exemplo(row[1])))))]


INTOCADOS = ("ems_v2", "integracao_v2", "models", "h2_pemfc", "simulation", "config", "ems_integration",
             "reference_models", "visualization", "orchestrator_runtime.py", "orchestrator_app.py", "app.py",
             "requirements.txt", "requirements-ems_v2.txt", "seeds2/operation", "seeds2/archive", "seeds2/report",
             "seeds2/ui/main.py", "seeds2/ui/operations.py", "seeds2/microgrid/store.py", "seeds2/microgrid/registry.py", "seeds2/microgrid/config.py",
             "seeds2/microgrid/adapter.py", ".github")


# ÚNICA exceção histórica autorizada após a missão: correção do zero FV do PR #30.
# O SHA é o blob Git EXATO do arquivo aprovado em main c807a28; qualquer modificação posterior
# torna a exceção inválida. Não enfraquece as guardas do motor nem autoriza outros caminhos.
FV_ZERO_BLOB_SHA = "855b0ee3fa8a49260cc0f03f2117ff4b348425b3"


def filter_fv_zero_autorizado(root: Path, linhas: list[list[str]]) -> list[list[str]]:
    """Ignora só 'M integracao_v2/renovaveis.py' quando o conteúdo coincide byte a byte com o PR #30."""
    try:
        sha_atual = subprocess.run(
            ["git", "hash-object", "integracao_v2/renovaveis.py"],
            cwd=root, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return linhas
    if sha_atual != FV_ZERO_BLOB_SHA:
        return linhas
    return [ln for ln in linhas if ln != ["M", "integracao_v2/renovaveis.py"]]


# Exceção científica estrita autorizada: aceitação de hipótese FV 0% no leitor
# da matriz de parâmetros da ponte 3C-0. Somente este blob aprovado.
FV_PONTE_ZERO_BLOB_SHA = "1c39495b7020d7988d99e3f9983fd4ab4a2852f5"


def filter_ponte_zero_autorizado(root: Path, linhas: list[list[str]]) -> list[list[str]]:
    """Aceita exclusivamente M ems_v2/ponte/requisitos.py com conteúdo do hotfix FV 0%."""
    alvo = ["M", "ems_v2/ponte/requisitos.py"]
    if alvo not in linhas:
        return linhas
    try:
        sha_atual = subprocess.run(
            ["git", "hash-object", alvo[1]], cwd=root, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return linhas
    return [ln for ln in linhas if ln != alvo] if sha_atual == FV_PONTE_ZERO_BLOB_SHA else linhas


def auditar_missao(root: Path, base: str = BASE) -> dict:
    """Auditoria EXPLÍCITA do diff desta missão (base → árvore de trabalho)."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout

    linhas = [ln.split("\t") for ln in git("diff", "--name-status", "--no-renames", base).splitlines() if ln.strip()]
    linhas += [["A", p] for p in git("ls-files", "--others", "--exclude-standard").split()]
    linhas = filter_ponte_zero_autorizado(root, linhas)
    intocados = [ln for ln in linhas if any(ln[1] == p or ln[1].startswith(p.rstrip("/") + "/") for p in INTOCADOS)]
    ruins = remocoes_nao_conformes(root, base)
    return {"base": base, "alterados": sorted(map(tuple, linhas)), "intocados_violados": intocados,
            "remocoes_nao_conformes": ruins, "ok": not intocados and not ruins}


__all__ = ["ADICIONADOS", "BASE", "INTOCADOS", "MODIFICADOS", "REMOVIDAS", "auditar_missao", "filter_changes",
           "remocoes_nao_conformes"]

if __name__ == "__main__":
    import json

    rel = auditar_missao(Path(__file__).resolve().parents[2])
    print(json.dumps(rel, ensure_ascii=False, indent=1))
    raise SystemExit(0 if rel["ok"] else 1)
