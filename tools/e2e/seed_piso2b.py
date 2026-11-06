"""Prepara um SEEDS2_DATA_DIR VAZIO para o E2E do Piso 2B (``e2e_piso2b_previsoes.js``).

Cria no catálogo UMA microrrede comissionada FICTÍCIA (fixture de teste ``tests/seeds2_fixtures.py``: inventário
equivalente à configuração padrão V1.6 — FV, PEMFC, baterias) acrescida de UM aerogerador de catálogo, para que a
previsão climática exija o conjunto compartilhado FV + eólica. Grava também, num diretório de arquivos de entrada,
CSVs SINTÉTICOS gerados aqui (nenhum dado de instalação real):

* ``demanda_e2e.csv``      — demanda 2 h a 1 min, ``timestamp;P_kW`` com vírgula decimal e fuso -03:00;
* ``clima_e2e.csv``        — clima 6 h a 10 min, cabeçalhos SEM unidade para GHI/vento (o usuário confirma);
* ``malformado_e2e.csv``   — arquivo com uma única coluna (deve ser recusado com mensagem).

Uso:  python tools/e2e/seed_piso2b.py <SEEDS2_DATA_DIR vazio> <diretório dos CSVs>
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

from seeds2.microgrid import config as C  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2_fixtures import v16_equivalent_config  # noqa: E402


def write_csvs(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    t = pd.date_range("2026-09-01 10:00", periods=121, freq="1min")
    p = 140 + 25 * np.sin(np.arange(121) / 12.0)
    p[60:66] += 55                                     # ponta explícita para a inspeção gráfica
    lines = ["timestamp;P_kW"] + [f"{x:%Y-%m-%dT%H:%M:%S}-03:00;{v:.2f}".replace(".", ",") for x, v in zip(t, p)]
    (out / "demanda_e2e.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    tc = pd.date_range("2026-09-01 08:00", periods=37, freq="10min")
    h = tc.hour + tc.minute / 60
    ghi = np.clip(900 * np.sin(np.pi * (h - 6) / 12), 0, None)
    clima = pd.DataFrame({"timestamp": tc.strftime("%Y-%m-%d %H:%M"), "GHI": ghi.round(1),
                          "temperatura_C": (24 + 4 * np.sin(np.pi * (h - 9) / 12)).round(2),
                          "vento": (7 + np.sin(np.arange(37) / 4)).round(2),
                          "direcao_vento_deg": ((350 + 5 * np.arange(37)) % 360).round(1)})
    clima.to_csv(out / "clima_e2e.csv", index=False)
    (out / "malformado_e2e.csv").write_text("apenas_uma_coluna\n1\n2\n3\n", encoding="utf-8")


def main(data_dir: str, csv_dir: str) -> None:
    reg = MicrogridRegistry(data_dir)
    if reg.entries():
        raise SystemExit("O diretório não está vazio: use um SEEDS2_DATA_DIR novo para o E2E.")
    cfg = v16_equivalent_config("Microrrede E2E Piso 2B")
    C.add_equipment(cfg, C.new_equipment("wind", "Aerogerador E2E", tag="WT-01",
                                         params={"reference": "EWT DW61-1MW", "count": 1}))
    reg.create(cfg, origin="commissioning")
    write_csvs(Path(csv_dir))
    print(cfg["installation"]["uid"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
