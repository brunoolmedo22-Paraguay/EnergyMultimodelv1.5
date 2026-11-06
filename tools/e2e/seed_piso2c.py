"""Prepara um SEEDS2_DATA_DIR VAZIO para o E2E do Piso 2C (``e2e_piso2c_execucao.js``).

Cria no catálogo UMA microrrede comissionada FICTÍCIA (fixture ``tests/seeds2_fixtures.py``: inventário equivalente
à configuração padrão V1.6 — FV, PEMFC, baterias) com UM cenário "Experimento 2C E2E" cujos estados iniciais e
previsões já estão gravados (etapas 01 e 02 cobertas pelos E2E dos Pisos 2A/2B):

* estados: baterias com SOC 60 %; PEMFC em operação com todas as unidades e potência inicial 0;
* demanda: walk-forward de referência da V1.6 repetido por 12 h (1 min), fuso America/Sao_Paulo;
* clima: clima sintético V1.6 a cada 10 min, gravado em UTC (os instantes físicos são os mesmos da demanda) —
  exercita a conversão de fusos e a interpolação registrada.

Estratégia EMS e janela da missão NÃO são definidas aqui: o E2E as define pela interface. Nenhum dado real.

Uso:  python tools/e2e/seed_piso2c.py <SEEDS2_DATA_DIR vazio>
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

import orchestrator_runtime as RT  # noqa: E402
from ems_integration import ponte  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.operation import forecast_sources as FS  # noqa: E402
from seeds2.operation import service  # noqa: E402
from seeds2_fixtures import v16_equivalent_config  # noqa: E402

TZ = "America/Sao_Paulo"


def main(data_dir: str) -> None:
    reg = MicrogridRegistry(data_dir)
    if reg.entries():
        raise SystemExit("O diretório não está vazio: use um SEEDS2_DATA_DIR novo para o E2E.")
    cfg = v16_equivalent_config("Microrrede E2E Piso 2C")
    reg.create(cfg, origin="commissioning")
    st = reg.open(cfg["installation"]["uid"])
    sc = service.create(st, name="Experimento 2C E2E", description="Cenário fictício para o E2E do Piso 2C.")
    doc = copy.deepcopy(sc.document)
    for eid, r in doc["inventory_ref"]["equipment"].items():
        s = doc["initialization"]["equipment"][eid]
        if r["kind"] == "battery":
            s["soc0_pct"] = 60.0
        elif r["kind"] == "pemfc":
            s.update(state="em_operacao", units_on=r["quantity"], power_kW=0.0)
    ref = doc["inventory_ref"]
    base = ponte.carga_walkforward("Ideal", "Normal", 12)                       # 2 h a 1 min, início 12:00
    n = 12 * 60 + 1
    p = np.resize(base.P_kW[:-1], n)
    ts = pd.date_range(base.t0, periods=n, freq="1min")
    dem = FS.manual_candidate(pd.DataFrame({"timestamp": ts, "demand_kW": p}), "demand", timezone=TZ, inventory_ref=ref,
                              provenance="referencia", construction={"origem": "walk-forward V1.6 repetido (E2E)"})
    carga = ponte.PerfilCarga(np.arange(n, dtype=float), p, base.t0, "grade do clima")
    c = RT.synthetic_climate(carga).iloc[::10].reset_index(drop=True)
    clima = pd.DataFrame({"timestamp": pd.to_datetime(c["timestamp"]) + pd.Timedelta(hours=3),   # mesmo instante em UTC
                          "ghi_W_m2": c["GHI_W_m2"], "temperature_C": c["temperature_C"]})
    cli = FS.manual_candidate(clima, "climate", timezone="UTC", inventory_ref=ref, provenance="sintetico",
                              construction={"origem": "clima sintético V1.6 (E2E)"})
    assert dem.ok and cli.ok
    doc["forecasts"] = {"demand": dem.entry, "climate": cli.entry}
    service.save(st, doc, sc.version, new_blobs={**dem.blobs, **cli.blobs}, note="Preparação do E2E (estados e previsões)")
    print(cfg["installation"]["uid"])


if __name__ == "__main__":
    main(sys.argv[1])
