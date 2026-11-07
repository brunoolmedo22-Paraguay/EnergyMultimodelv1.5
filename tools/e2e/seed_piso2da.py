"""Prepara um SEEDS2_DATA_DIR VAZIO (instalação de ORIGEM) para o E2E do Piso 2D-A (``e2e_piso2da_arquivo.js``).

Cria no catálogo UMA microrrede comissionada FICTÍCIA ("Industrial A — E2E 2D-A"; fixture ``tests/seeds2_fixtures.py``,
inventário equivalente à configuração padrão V1.6) com UM cenário "Alta demanda E2E" que tem histórico científico real:

* v1 (criação) e v2 (estados, previsões de demanda e clima da V1.6, estratégia padrão, janela de 30 min) →
  rodada REAL do Piso 2C (``runner.submit``: modelos físicos + otimizador V1.6) → **concluída**;
* v3 (semente 7) → rodada com o otimizador sabotado NESTE script → **falhou** (sem resultados, motivo gravado).

O custo da rodada concluída é escrito em ``<dir>/custo_origem.txt`` (formato da interface) para a comparação no E2E.
Nenhum dado real; nenhum serviço externo.

Uso:  python tools/e2e/seed_piso2da.py <SEEDS2_DATA_DIR vazio>
"""
from __future__ import annotations

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
    cfg = v16_equivalent_config("Industrial A — E2E 2D-A")
    reg.create(cfg, origin="commissioning")
    st = reg.open(cfg["installation"]["uid"])
    sc = ready(st, name="Alta demanda E2E")
    done = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
    assert done.state == "concluida", done.error
    sc3 = edit(st, sc, lambda d: d["ems_strategy"].update(seed=7), note="semente 7")
    with mock.patch.object(RT, "run_optimizer", side_effect=RuntimeError("otimizador indisponível (falha simulada no E2E)")):
        failed = runner.submit(st, sc3.scenario_uid, sc3.version, runner.new_request_id(), background=False)
    assert failed.state == "falhou"
    (Path(data_dir) / "custo_origem.txt").write_text(f"R$ {fmt(done.summary['custo_total_rs'], 2)}", encoding="utf-8")
    print(cfg["installation"]["uid"], sc.scenario_uid, done.run_uid, failed.run_uid)


if __name__ == "__main__":
    main(sys.argv[1])
