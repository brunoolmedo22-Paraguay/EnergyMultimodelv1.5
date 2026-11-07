"""Prepara um SEEDS2_DATA_DIR VAZIO (instalação de ORIGEM) para o E2E do Piso 2D-B (``e2e_piso2db_relatorios.js``).

Mesma origem do E2E 2D-A (``seed_piso2da.py``): microrrede FICTÍCIA "Industrial A — E2E 2D-B" (inventário equivalente
à configuração padrão V1.6), cenário "Alta demanda E2E" com uma rodada REAL concluída (v2) e uma rodada falha (v3,
otimizador sabotado NESTE script). Grava em ``<dir>/e2e_origem.json`` o custo (formato da interface), os UIDs e o
resumo persistido da rodada concluída, para a conferência dos documentos baixados (``check_piso2db_downloads.py``).

Uso:  python tools/e2e/seed_piso2db.py <SEEDS2_DATA_DIR vazio>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

import orchestrator_runtime as RT  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.operation import runner  # noqa: E402
from seeds2.ui.forms import fmt  # noqa: E402
from seeds2_fixtures import v16_equivalent_config  # noqa: E402
from test_seeds2_piso2c import edit, ready  # noqa: E402


def main(data_dir: str) -> None:
    reg = MicrogridRegistry(data_dir)
    if reg.entries():
        raise SystemExit("O diretório não está vazio: use um SEEDS2_DATA_DIR novo para o E2E.")
    cfg = v16_equivalent_config("Industrial A — E2E 2D-B")
    reg.create(cfg, origin="commissioning")
    st = reg.open(cfg["installation"]["uid"])
    sc = ready(st, name="Alta demanda E2E")
    done = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
    assert done.state == "concluida", done.error
    sc3 = edit(st, sc, lambda d: d["ems_strategy"].update(seed=7), note="semente 7")
    with mock.patch.object(RT, "run_optimizer", side_effect=RuntimeError("otimizador indisponível (falha simulada no E2E)")):
        failed = runner.submit(st, sc3.scenario_uid, sc3.version, runner.new_request_id(), background=False)
    assert failed.state == "falhou"
    info = {"cost": f"R$ {fmt(done.summary['custo_total_rs'], 2)}", "microgrid_uid": cfg["installation"]["uid"],
            "scenario_uid": sc.scenario_uid, "run_uid": done.run_uid, "failed_run_uid": failed.run_uid,
            "summary": done.summary, "data": {k: v["sha256"] for k, v in done.data.items()},
            "scenario_fingerprint": done.scenario_fingerprint, "config_fingerprint": done.config_fingerprint,
            "incarnation": done.incarnation}
    (Path(data_dir) / "e2e_origem.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    (Path(data_dir) / "custo_origem.txt").write_text(info["cost"], encoding="utf-8")
    print(cfg["installation"]["uid"], sc.scenario_uid, done.run_uid, failed.run_uid)


if __name__ == "__main__":
    main(sys.argv[1])
