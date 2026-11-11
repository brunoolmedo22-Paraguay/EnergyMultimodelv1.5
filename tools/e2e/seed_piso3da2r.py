"""Prepara um SEEDS2_DATA_DIR VAZIO para o E2E do Piso 3D-A2-R (``e2e_piso3da2r.js``).

Cria no catálogo UMA microrrede comissionada FICTÍCIA (apoio ``tests/piso3da2r_util.py``; dados sintéticos de teste):
**Microrrede E2E 3D-A2-R** — usina FV (1 arranjo de 10 × 2 módulos CS6K-275P do catálogo), aerogerador Vergnet GEV MP C
275 kW (catálogo, ``restricted_domain``), banco de 20 kWh e PCC só importação (50 kW, tarifa SINTÉTICA com pico nas horas
8–9). Cenário "Híbrida V2 (renováveis)": demanda sintética 40 kW × 12 h, clima SINTÉTICO declarado ponto a ponto (GHI,
temperatura, vento forte no meio da missão e fraco no fim) e estratégia V2 completa com as renováveis declaradas.

Nenhum dado real; nenhuma rodada é executada aqui. Uso:  python tools/e2e/seed_piso3da2r.py <SEEDS2_DATA_DIR vazio>
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

import piso3da2r_util as R  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402

GHI = [0, 0, 0, 0, 0, 0, 100, 350, 600, 800, 950, 1000]
TAMB = [20, 20, 20, 21, 21, 22, 23, 25, 27, 29, 30, 31]
VENTO = [2.0, 3.0, 9.0, 10.0, 11.0, 12.0, 12.0, 10.0, 4.0, 3.0, 2.5, 2.0]


def main(data_dir: str) -> None:
    reg = MicrogridRegistry(data_dir)
    if reg.entries():
        raise SystemExit("O diretório não está vazio: use um SEEDS2_DATA_DIR novo para o E2E.")
    cfg = R.config_hibrida("Microrrede E2E 3D-A2-R")
    reg.create(cfg, origin="commissioning")
    store = reg.open(cfg["installation"]["uid"])
    R.criar_cenario_hibrido(store, nome="Híbrida V2 (renováveis)", demanda_kW=40.0,
                            clima=lambda doc: R.clima_tabela(doc, {"ghi_W_m2": GHI, "temperature_C": TAMB,
                                                                   "wind_speed_m_s": VENTO}))
    print(f"OK: {data_dir} — microrrede {cfg['installation']['uid']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
