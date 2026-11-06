"""Prepara um SEEDS2_DATA_DIR VAZIO para o E2E do Piso 2A (``e2e_piso2a_centro_operacao.js``).

Cria no catálogo UMA microrrede comissionada FICTÍCIA (fixture de teste ``tests/seeds2_fixtures.py``: inventário
equivalente à configuração padrão V1.6) acrescida de uma unidade térmica local, para exercitar os estados iniciais
de bateria, PEMFC, térmica e FV. Nenhum dado de instalação real. O comissionamento pela interface é coberto por
``e2e_piso1_microrrede.js``.

Uso:  python tools/e2e/seed_piso2a.py <SEEDS2_DATA_DIR vazio>
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

from seeds2.microgrid import config as C  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2_fixtures import v16_equivalent_config  # noqa: E402


def main(data_dir: str) -> None:
    reg = MicrogridRegistry(data_dir)
    if reg.entries():
        raise SystemExit("O diretório não está vazio: use um SEEDS2_DATA_DIR novo para o E2E.")
    cfg = v16_equivalent_config("Microrrede E2E Piso 2A")
    C.add_equipment(cfg, C.new_equipment("thermal", "Gerador local", tag="GL-01", params={
        "dynamic": "local_generator", "pmax_kW": 100.0, "pmin_kW": 20.0, "cvu_rs_MWh": 900.0, "startup_cost_rs": 50.0}))
    reg.create(cfg, origin="commissioning")
    print(cfg["installation"]["uid"])


if __name__ == "__main__":
    main(sys.argv[1])
