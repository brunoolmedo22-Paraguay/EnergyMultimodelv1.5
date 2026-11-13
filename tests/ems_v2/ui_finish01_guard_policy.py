"""UI-FINISH-01 — exceção NOMINAL das guardas para o acabamento de interface e as exportações científicas V2.

Mesmo mecanismo das exceções anteriores (nomes EXATOS e status ``M`` × ``A``), encadeada no fim da política do
UI-RUNNING-01. Nenhuma guarda global é removida ou enfraquecida; ``ems_v2/``, o runner V2 (``integracao_v2/execucao.py``),
modelos físicos, motor V1.6, armazenamento e contratos ficam intocados.

Dois arquivos FORA das áreas de interface entram, por pedido explícito do responsável («se indispensável, componentes do
gerador documental com teste»), com uma restrição EXTRA: as linhas REMOVIDAS desde a base têm de pertencer a uma lista
explícita (``REMOVIDAS``) — qualquer outra alteração que apague código volta a falhar:

* ``seeds2/report/dossier.py``: o dossiê passa a conhecer o motor da rodada (contrato de dados ``v2/…`` para rodadas V2) e
  ``require_complete(d, engine=…)`` recusa explicitamente gerar documentos de um motor sobre a rodada do outro;
* ``seeds2/ui/report_exports.py``: o MESMO painel aceita, opcionalmente, o gerador, os rótulos e as ajudas do chamador
  (página da rodada V2); sem eles, o comportamento V1.6 é idêntico.

Asserções ANTIGAS atualizadas porque o pedido muda exatamente o que fixavam (bancadas sem microrrede e no
comissionamento; botões do Gestor vazio; o dossiê 2D-B que não lia rodadas V2 — a recusa dos geradores V1.6 continua):
``tests/test_ui_redesign01.py``, ``tests/test_piso3db_plataforma.py``, ``tests/test_seeds2_gestor_app.py``,
``tests/test_piso3da_execucao.py``. As políticas anteriores ``ui_running01_guard_policy.py`` (encadeamento) e
``piso3db_guard_policy.py`` (a auditoria do 3D-B consulta esta exceção para os caminhos intocados) recebem só o gancho.

Este módulo não gera nem atualiza hashes e não consulta a rede.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

BASE = "c29e600"                                       # main no início da missão (merge do PR #27)
MODIFICADOS = frozenset({"seeds2/report/dossier.py", "seeds2/ui/report_exports.py",
                         "tests/test_ui_redesign01.py", "tests/test_piso3db_plataforma.py", "tests/test_seeds2_gestor_app.py",
                         "tests/test_piso3da_execucao.py",
                         "tests/ems_v2/ui_running01_guard_policy.py", "tests/ems_v2/piso3db_guard_policy.py"})
ADICIONADOS = frozenset({"integracao_v2/documentos.py", "tests/test_ui_finish01.py", "tests/ems_v2/ui_finish01_guard_policy.py",
                         "tests/ems_v2/test_ui_finish01_guardas.py"})
# linhas que PODEM ter saído dos dois arquivos fora da interface (substituídas pelas versões cientes do motor)
REMOVIDAS = {
    "seeds2/report/dossier.py": {
        '"""Recursos essenciais ausentes do índice ORIGINAL de uma rodada concluída (falha/interrupção: nenhum exigido)."""',
        "return [n for n in REQUIRED_CONCLUDED if n not in (run.data or {})]",
        "def require_complete(d: RunDossier) -> None:",
        '"""Barreira dos geradores (PDF, Excel, figuras): rodada concluída sem um recurso essencial → recusa explícita."""',
        '__all__ = ["ARCHIVED", "DERIVED_NOTE", "DossierError", "DossierIntegrityError", "Indicator", "LOCAL",',
        '"ORIGIN_LABELS", "REQUIRED_CONCLUDED", "RunDossier", "generator_info", "identity_for_manifest",', ""},
    "seeds2/ui/report_exports.py": {
        "def render(source, run, *, key: str) -> None:",
        '"""Painel EXPORTAR (PDF / Excel / figuras) da rodada ``run`` lida de ``source``."""',
        'labels = {"pdf": "EXPORTAR RELATÓRIO PDF" if done else "EXPORTAR DIAGNÓSTICO PDF",',
        '"xlsx": "EXPORTAR DADOS EXCEL" if done else "EXPORTAR DIAGNÓSTICO EXCEL",',
        '"fig": "EXPORTAR FIGURAS"}',
        'for col, kind in zip(cols, ("pdf", "xlsx", "fig")):',
        "ss[_key(run.run_uid, clicked)] = generate(source, run.run_uid, clicked, progress=box.write)", ""},
}
INTOCADOS_NOMINAIS = frozenset({"seeds2/report/dossier.py"})   # caminho intocado do 3D-B admitido por esta exceção


def removidas_fora_da_lista(root: Path, base: str = BASE) -> dict:
    """{arquivo: linhas removidas desde ``base`` que NÃO estão em ``REMOVIDAS``} (vazio = alteração conforme)."""
    out = {}
    for arq, ok in REMOVIDAS.items():
        try:
            diff = subprocess.run(["git", "diff", "-U0", base, "--", arq], cwd=root, capture_output=True, text=True,
                                  check=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue                                     # clone sem a base: a auditoria explícita é feita no PR
        fora = {ln[1:].strip() for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---")} - ok
        if fora:
            out[arq] = sorted(fora)
    return out


def filter_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
    """Política pura: nomes E status exatos; os dois arquivos fora da interface só se as remoções forem as listadas."""
    conforme = not removidas_fora_da_lista(root)
    return [row for row in changes if not (len(row) == 2 and (
        (row[0] == "M" and row[1] in MODIFICADOS and (conforme or row[1] not in REMOVIDAS))
        or (row[0] == "A" and row[1] in ADICIONADOS)))]


def filter_intocados(root: Path, linhas: list[list[str]]) -> list[list[str]]:
    """Para auditorias de missões anteriores: retira SÓ ``M seeds2/report/dossier.py`` e só se a alteração for conforme."""
    if removidas_fora_da_lista(root):
        return linhas
    return [ln for ln in linhas if not (len(ln) == 2 and ln[0] == "M" and ln[1] in INTOCADOS_NOMINAIS)]


INTOCADOS = ("ems_v2", "models", "h2_pemfc", "simulation", "config", "ems_integration", "reference_models", "visualization",
             "integracao_v2/execucao.py", "integracao_v2/registro.py", "integracao_v2/montagem.py", "integracao_v2/preflight.py",
             "integracao_v2/estrategia.py", "integracao_v2/renovaveis.py", "integracao_v2/curva_h2.py",
             "integracao_v2/pemfc_dinamica.py", "integracao_v2/trama_frame.py", "orchestrator_runtime.py", "orchestrator_app.py",
             "app.py", "requirements.txt", "requirements-ems_v2.txt", "seeds2/operation", "seeds2/microgrid", "seeds2/archive",
             "seeds2/report/run_pdf.py", "seeds2/report/xlsx.py", "seeds2/report/figures.py", "seeds2/report/pdf.py",
             "seeds2/ui/main.py", "seeds2/ui/operations.py", ".github")


def auditar_missao(root: Path, base: str = BASE) -> dict:
    """Auditoria EXPLÍCITA do diff desta missão (base → árvore de trabalho): nada nos caminhos intocados; remoções conformes."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout

    linhas = [ln.split("\t") for ln in git("diff", "--name-status", "--no-renames", base).splitlines() if ln.strip()]
    linhas += [["A", p] for p in git("ls-files", "--others", "--exclude-standard").split()]
    intocados = [ln for ln in linhas if any(ln[1] == p or ln[1].startswith(p.rstrip("/") + "/") for p in INTOCADOS)]
    fora = removidas_fora_da_lista(root, base)
    return {"base": base, "alterados": sorted(map(tuple, linhas)), "intocados_violados": intocados,
            "remocoes_fora_da_lista": fora, "ok": not intocados and not fora}


__all__ = ["ADICIONADOS", "BASE", "INTOCADOS", "MODIFICADOS", "REMOVIDAS", "auditar_missao", "filter_changes",
           "filter_intocados", "removidas_fora_da_lista"]

if __name__ == "__main__":
    import json

    print(json.dumps(auditar_missao(Path(__file__).resolve().parents[2]), ensure_ascii=False, indent=1))
