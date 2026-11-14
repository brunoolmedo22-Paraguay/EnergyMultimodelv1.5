"""UI-RESULTADOS-02 — exceção NOMINAL das guardas para as visualizações científicas e o relatório PDF visual da rodada V2.

Pedido do responsável (14/11/2026): tarifa como curva escalonada, demanda de referência nas fontes, aba Carga líquida,
lente Visão Geral e relatório PDF que reproduz a Partitura. Mesmo mecanismo das exceções anteriores (nomes EXATOS e
status ``M`` × ``A``), encadeada no fim da política EXEMPLOS-PERSISTENTES-01. Nenhuma guarda global é removida ou
enfraquecida. Ficam INTOCADOS: ``ems_v2/``, modelos físicos, motor V1.6, runner, armazenamento, contratos de dados, o marco
Trama (``integracao_v2/trama_frame.py``), os geradores 2D-B (``seeds2/report``), o painel do 2D-B
(``seeds2/ui/report_exports.py``) e ``integracao_v2/documentos.py`` (o relatório técnico e o diagnóstico continuam iguais).

Código protegido alterado, com restrição EXTRA sobre as linhas REMOVIDAS desde a base (lista explícita ``REMOVIDAS``):

* ``integracao_v2/ui.py``: a Partitura recebe o estado do pedido do relatório e devolve o pacote desenhado pelo gatilho
  «relatorio»; o painel de exportações da rodada V2 com a Partitura pede o PDF à Partitura (mesmos botões e chaves);
* ``seeds2/ui/trama.py`` NÃO é alterado (a guarda do 3D-B mantém visível qualquer «M» nele): ``integracao_v2/ui.py`` chama o
  MESMO componente (``trama.component``) com o gatilho «relatorio».

``tests/ems_v2/exemplos01_guard_policy.py`` recebe só o gancho (encadeamento e auditoria). Sete asserções antigas dos testes da
Partitura (``tests/test_piso3db_{trama,nd,lentes}.py``) fixavam exatamente a lista de recursos do explorador e a de lentes
percorridas pela bancada; o pedido acrescenta «Carga líquida» e «Visão Geral», então só essas linhas mudam (lista explícita).

Este módulo não gera nem atualiza hashes e não consulta a rede.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

BASE = "e765028"                                     # main no início da missão (merge do PR #32)
MODIFICADOS = frozenset({"integracao_v2/ui.py", "seeds2/ui/static/trama/partitura.js",
                         "seeds2/ui/static/trama/trama.js", "seeds2/ui/static/trama/trama.css",
                         "tests/ems_v2/exemplos01_guard_policy.py",
                         # asserções ANTIGAS que fixavam exatamente a lista de recursos do explorador (o pedido acrescenta a aba
                         # «Carga líquida»): só essas linhas mudam (``REMOVIDAS``)
                         "tests/test_piso3db_trama.py", "tests/test_piso3db_nd.py", "tests/test_piso3db_lentes.py"})
ADICIONADOS = frozenset({"integracao_v2/relatorio_visual.py", "integracao_v2/svg_pdf.py", "tests/test_ui_resultados02.py",
                         "tests/ems_v2/ui_resultados02_guard_policy.py", "tests/ems_v2/test_ui_resultados02_guardas.py"})
REMOVIDAS = {
    "integracao_v2/ui.py": {
        "cache[chave] = TF.montar(source, run, verificacao=v, nomes=_nomes_do_inventario(source, run))",
        'TR.partitura(cache[chave], key=f"{key}_partitura")',
        "exportacoes(source, run, key)                 # UI-FINISH-01: área de exportações VISÍVEL (não dentro da vista clássica)",
        "def exportacoes(source, run, key: str) -> None:",
        'página) com os geradores V2 de ``documentos`` (dossiê, figuras e escritores do 2D-B sobre o contrato ``v2/…``)."""', ""},
    "tests/ems_v2/exemplos01_guard_policy.py": {"return [row for row in changes if not (len(row) == 2 and (", ""},
    "tests/test_piso3db_trama.py": {'self.assertEqual(js["ord"], ["fv", "wt", "bat", "fc", "grid", "dem", "eco"])', ""},
    "tests/test_piso3db_nd.py": {
        'self.assertEqual(r["ord"], ["fv", "bat", "grid", "dem", "eco"])',
        'self.assertEqual(sorted(k for k in v if k.startswith("painel:")), ["painel:Carga", "painel:Custos", "painel:Solar:arr-fv1"])', ""},
    "tests/test_piso3db_lentes.py": {
        'self.assertEqual(js, [["bat", "grid", "dem", "eco"], "__undefined__", "__undefined__", "__undefined__", []])',
        'self.assertEqual(js[:4], [["bat", "dem", "eco"], "__undefined__", "__undefined__", "__undefined__"])',
        'self.assertEqual(sorted(k.split(":")[1] for k in v if k.startswith("painel:")), ["Bateria", "Carga", "Custos", "Rede"])',
        'self.assertEqual(sorted(k.split(":")[1] for k in v if k.startswith("painel:")), ["Bateria", "Carga", "Custos"])',
        '{"lente:operacao", "lente:decisao", "lente:economia", "lente:evidencia"})', ""},
}
INTOCADOS = ("ems_v2", "models", "h2_pemfc", "simulation", "config", "ems_integration", "reference_models", "visualization",
             "integracao_v2/execucao.py", "integracao_v2/registro.py", "integracao_v2/montagem.py", "integracao_v2/preflight.py",
             "integracao_v2/estrategia.py", "integracao_v2/renovaveis.py", "integracao_v2/curva_h2.py",
             "integracao_v2/pemfc_dinamica.py", "integracao_v2/trama_frame.py", "integracao_v2/documentos.py",
             "seeds2/report", "seeds2/operation", "seeds2/microgrid", "seeds2/archive", "seeds2/ui/main.py",
             "seeds2/ui/operations.py", "seeds2/ui/report_exports.py", "seeds2/ui/trama.py", "app.py", "orchestrator_runtime.py", "orchestrator_app.py",
             "requirements.txt", "requirements-ems_v2.txt", ".github")


def _removidas(root: Path, base: str, arq: str) -> set[str] | None:
    try:
        out = subprocess.run(["git", "diff", "-U0", base, "--", arq], cwd=root, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None                                   # clone sem a base: a auditoria explícita é feita no PR
    return {ln[1:].strip() for ln in out.splitlines() if ln.startswith("-") and not ln.startswith("---")}


def remocoes_nao_conformes(root: Path, base: str = BASE) -> dict:
    """{arquivo: linhas removidas desde ``base`` fora de ``REMOVIDAS``} (vazio = alteração conforme)."""
    out = {}
    for arq, ok in REMOVIDAS.items():
        rem = _removidas(root, base, arq)
        if rem and (rem - ok):
            out[arq] = sorted(rem - ok)
    return out


def filter_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
    """Política pura: nomes E status exatos; código protegido só se as remoções forem as listadas."""
    ruins = remocoes_nao_conformes(root)
    return [row for row in changes if not (len(row) == 2 and (
        (row[0] == "M" and row[1] in MODIFICADOS and row[1] not in ruins) or (row[0] == "A" and row[1] in ADICIONADOS)))]


def auditar_missao(root: Path, base: str = BASE) -> dict:
    """Auditoria EXPLÍCITA do diff desta missão (base → árvore de trabalho)."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout

    linhas = [ln.split("\t") for ln in git("diff", "--name-status", "--no-renames", base).splitlines() if ln.strip()]
    linhas += [["A", p] for p in git("ls-files", "--others", "--exclude-standard").split()]
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
