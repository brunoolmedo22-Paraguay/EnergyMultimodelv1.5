"""Prepara um SEEDS2_DATA_DIR VAZIO para o E2E do Piso 3D-A2-H (``e2e_piso3da2h.js``).

Cria no catálogo UMA microrrede comissionada FICTÍCIA com bateria, PCC e um registro PEMFC (perfil real
EQUIVALENT_65KW_HORIZON_CONSTRAINED do SEEDS2) e um cenário V2 com as declarações PEMFC de TESTE (sintéticas). A política
B04 do repositório continua pendente: o E2E verifica o BLOQUEIO explicado. Uso: python tools/e2e/seed_piso3da2h.py <dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

import piso3da2h_util as H  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402


def main(data_dir: str) -> None:
    reg = MicrogridRegistry(data_dir)
    if reg.entries():
        raise SystemExit("O diretório não está vazio: use um SEEDS2_DATA_DIR novo para o E2E.")
    cfg = H.config_pemfc("Microrrede E2E 3D-A2-H")
    reg.create(cfg, origin="commissioning")
    H.criar_cenario_pemfc(reg.open(cfg["installation"]["uid"]), nome="PEMFC V2 (curva do modelo)", demanda_kW=30.0)
    print(f"OK: {data_dir} — microrrede {cfg['installation']['uid']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
