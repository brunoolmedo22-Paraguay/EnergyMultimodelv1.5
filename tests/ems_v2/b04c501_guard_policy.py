"""B04-C5-01 (P1) — exceção NOMINAL das guardas para o diagnóstico CONTEXTUAL da admissibilidade dinâmica da PEMFC.

Autorização do responsável (14/11/2026): implementar SOMENTE a P1 da missão B04-C5-01 — mensagens que distinguem o
certificado B04 (curva q(P)) da admissibilidade DINÂMICA a priori, descrevem só o que a abstração declarada avalia e listam
os Δ admissíveis pela MESMA análise. Física, tolerâncias, abstrações, critérios de aprovação e decisões do EMS ficam
INALTERADOS; a P2 (análise dependente da alcançabilidade) fica só documentada. Mesmo mecanismo das exceções anteriores
(nomes EXATOS e status ``M`` × ``A``), encadeada no fim da política UI-RESULTADOS-02. Nenhuma guarda global é removida ou
enfraquecida.

Código protegido alterado, com restrição EXTRA sobre as linhas REMOVIDAS desde a base (lista explícita ``REMOVIDAS``):

* ``integracao_v2/preflight.py``: só os dois TEXTOS da PEMFC em ``_pemfc`` (bloqueio ``pemfc_transitorio_incompativel`` e
  aprovação «restrições do modelo dinâmico compatíveis») passam a ser montados por funções puras novas no mesmo módulo; o
  veredito continua sendo exclusivamente ``pemfc_dinamica.admissibilidade``;
* ``tests/ems_v2/ui_resultados02_guard_policy.py`` (encadeamento e auditoria) e ``tests/ems_v2/piso3db_guard_policy.py``
  (fim da cadeia ``referencia_autorizada`` da guarda 3A) recebem só o gancho.

Ficam INTOCADOS: ``ems_v2/``, modelos físicos (``h2_pemfc`` inclusive), ``integracao_v2/pemfc_dinamica.py``,
``integracao_v2/curva_h2.py`` e todo o resto de ``integracao_v2/`` (inclusive a interface e o relatório visual do
UI-RESULTADOS-02), ``seeds2/``, o motor V1.6 e os requisitos.

Este módulo não gera nem atualiza hashes e não consulta a rede.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

BASE = "8dc5f6b5c7a25e7ce981c29efbeb15d1154d1509"     # main no início da missão (UI-RESULTADOS-02)
MODIFICADOS = frozenset({"integracao_v2/preflight.py", "tests/ems_v2/ui_resultados02_guard_policy.py",
                         "tests/ems_v2/piso3db_guard_policy.py"})
ADICIONADOS = frozenset({"tests/test_b04_c5_01.py", "tests/ems_v2/b04c501_guard_policy.py",
                         "tests/ems_v2/test_b04c501_guardas.py"})
# Arquivos Python FORA de ``ems_v2/`` e ``tests/ems_v2/`` autorizados a mencionar o pacote do motor (guarda 3A).
REFERENCIAM_O_MOTOR = frozenset({"tests/test_b04_c5_01.py"})
REMOVIDAS = {
    "integracao_v2/preflight.py": {
        '"condições ambientes que não impliquem partida fria, ou a unidade indisponível no cenário.", x["id"],',
        'an = mev["analise"]',
        'casos = sorted({v["caso"] for v in adm})',
        'code="pemfc_transitorio_incompativel")',
        'f" de {par[\'partida_s\']:g} s): {len(adm)} violação(ões) a priori em {\', \'.join(casos)}; pior caso "',
        'f"de partida/parada/rampa no domínio dentro das tolerâncias em Δ = {delta_s / 60:g} min (pior déficit de "',
        'f"em Δ = {delta_s / 60:g} min e T_amb = {t_amb:g} °C (partida {\'FRIA\' if par[\'partida_fria\'] else \'quente\'}"',
        'f"energia numa partida {min(v[\'delta_E_partida_kWh\'] for v in an[\'pontos\']):.3f} kWh). Massas ADICIONAIS "',
        'f"máx. {mev[\'superestimacao_max_partida_kg\']:.3g} / {mev[\'superestimacao_max_parada_kg\']:.3g} kg).", x["id"])',
        'f"por evento: partida {mev[\'m_partida_kg\']:.4g} kg, parada {mev[\'m_parada_kg\']:.4g} kg (superestimação "',
        'f"{par[\'idle_kW\']:g} kW; rampa {decl[\'rampa_kW_min\']:g} ≤ {par[\'rampa_max_kW_min\']:g} kW/min; transitórios "',
        'f"{pior[\'caso\']} em P = {pior[\'p_kW\']} kW: desvio {pior[\'desvio\']:.4g} > tolerância "',
        'f"{pior[\'tolerancia\']:.4g} ({pior[\'grandeza\']}). Alternativas: Δ maior, transições bloqueadas, "',
        'if adm:',
        'pf.add(ERROR, "pemfc", f"{x[\'name\']}: a abstração \'{decl[\'abstracao\']}\' NÃO é compatível com o modelo dinâmico "',
        'pf.add(OK, "pemfc", f"{x[\'name\']}: restrições do modelo dinâmico compatíveis — P_min {decl[\'p_min_kW\']:g} ≥ IDLE "',
        'pior = max(adm, key=lambda v: (v["desvio"] / v["tolerancia"]) if v["tolerancia"] else math.inf)',
        ""},
    "tests/ems_v2/ui_resultados02_guard_policy.py": {"return [row for row in changes if not (len(row) == 2 and (", ""},
    "tests/ems_v2/piso3db_guard_policy.py": {"return rel in REFERENCIAM_O_MOTOR", ""},
}
INTOCADOS = ("ems_v2", "integracao_v2", "models", "h2_pemfc", "simulation", "config", "ems_integration",
             "reference_models", "visualization", "seeds2", "app.py", "orchestrator_runtime.py", "orchestrator_app.py",
             "requirements.txt", "requirements-ems_v2.txt", ".github")


def _removidas(root: Path, base: str, arq: str) -> set[str] | None:
    try:
        out = subprocess.run(["git", "diff", "-U0", base, "--", arq], cwd=root, capture_output=True, text=True,
                             check=True).stdout
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


def referencia_autorizada(rel: str) -> bool:
    return rel in REFERENCIAM_O_MOTOR


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
    restantes = filter_changes(root, linhas)
    intocados = [ln for ln in restantes if any(ln[1] == p or ln[1].startswith(p.rstrip("/") + "/") for p in INTOCADOS)]
    ruins = remocoes_nao_conformes(root, base)
    return {"base": base, "alterados": sorted(map(tuple, linhas)), "intocados_violados": intocados,
            "remocoes_nao_conformes": ruins, "ok": not intocados and not ruins}


__all__ = ["ADICIONADOS", "BASE", "INTOCADOS", "MODIFICADOS", "REFERENCIAM_O_MOTOR", "REMOVIDAS", "auditar_missao",
           "filter_changes", "referencia_autorizada", "remocoes_nao_conformes"]

if __name__ == "__main__":
    import json

    rel = auditar_missao(Path(__file__).resolve().parents[2])
    print(json.dumps(rel, ensure_ascii=False, indent=1))
    raise SystemExit(0 if rel["ok"] else 1)
