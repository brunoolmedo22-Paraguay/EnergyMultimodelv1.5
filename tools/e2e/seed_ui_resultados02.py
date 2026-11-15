"""Prepara o diretório de dados do E2E do UI-RESULTADOS-02: restaura o exemplo C4 (instantânea versionada em
``seeds2/exemplos/``) num catálogo NOVO e devolve os identificadores. Não altera a instantânea nem a evidência.

Uso: python tools/e2e/seed_ui_resultados02.py <dados> <saida.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ)]
C4_UID = "ef5bc710ef45428b86d492406acf5f30"            # microrrede da instantânea C4 (seeds2/exemplos/README.md)


def main(dados: str, saida: str) -> int:
    from seeds2.microgrid import exemplos
    from seeds2.microgrid.registry import MicrogridRegistry

    reg = MicrogridRegistry(dados)
    rel = exemplos.garantir(reg, RAIZ / "seeds2" / "exemplos")
    # a pasta tem VÁRIOS exemplos (C4, C5, …): o C4 é escolhido pela identidade fixa da sua instantânea
    uid = next(e.uid for e in reg.entries() if e.uid == C4_UID)
    st = reg.open(uid)
    run = next(r for r in st.list_runs() if r.state == "concluida")
    out = {"mg": uid, "sc": run.scenario_uid, "run": run.run_uid, "restaurados": rel.restaurados,
           "data": {n: d["sha256"] for n, d in run.data.items()}, "custo": run.summary["mission"]["custo_realizado_total_R"]}
    Path(saida).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("mg", "sc", "run")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:3]))
