"""Prepara um SEEDS2_DATA_DIR VAZIO para o E2E do Piso 3D-A (``e2e_piso3da_v2.js``).

Cria no catálogo DUAS microrredes comissionadas FICTÍCIAS (apoio ``tests/piso3da_util.py``; dados sintéticos de teste):

* **Microrrede E2E 3D-A** (banco de 20 kWh, conectada) com dois cenários:
  - "Experimento V2 pela interface": só estados iniciais (SOC 100 %), demanda sintética horária (10 kW, 12 h, UTC) e a
    janela da missão — o motor e TODA a estratégia MILP–MPC são declarados pelo E2E na interface;
  - "Missão longa V2 (interrupção)": estratégia completa com 48 intervalos (N = 6, H_L = 24), usada para derrubar o
    servidor DURANTE a rodada;
* **Microrrede E2E 3D-A · B** (banco de 10 kWh) com um cenário V2 completo de tarifa plana (isolamento entre microrredes).

Nenhum dado real; nenhuma rodada é executada aqui.

Uso:  python tools/e2e/seed_piso3da.py <SEEDS2_DATA_DIR vazio>
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

import piso3da_util as U  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402


def main(data_dir: str) -> None:
    reg = MicrogridRegistry(data_dir)
    if reg.entries():
        raise SystemExit("O diretório não está vazio: use um SEEDS2_DATA_DIR novo para o E2E.")
    a = U.config_bateria("Microrrede E2E 3D-A")
    reg.create(a, origin="commissioning")
    sa = reg.open(a["installation"]["uid"])
    U.criar_cenario_v2(sa, nome="Missão longa V2 (interrupção)", horas=48, N=6, H_L=24,
                       tarifa=([0.5] * 8 + [1.5, 1.5] + [0.5] * 14) * 2)
    U.criar_cenario_v2(sa, nome="Experimento V2 pela interface", com_estrategia=False)
    b = U.config_bateria("Microrrede E2E 3D-A · B", energia_kWh=10.0)
    reg.create(b, origin="commissioning")
    U.criar_cenario_v2(reg.open(b["installation"]["uid"]), nome="Tarifa plana V2 (B)", tarifa=[0.5] * 12)
    print(f"OK: {data_dir} — microrredes {a['installation']['uid']} e {b['installation']['uid']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
