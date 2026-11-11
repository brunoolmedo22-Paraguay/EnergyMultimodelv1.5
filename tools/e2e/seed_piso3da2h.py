"""Prepara um SEEDS2_DATA_DIR VAZIO para o E2E do Piso 3D-A2-H (``e2e_piso3da2h.js``).

Cria no catálogo UMA microrrede comissionada FICTÍCIA com bateria, PCC e um registro PEMFC (perfil real
EQUIVALENT_65KW_HORIZON_CONSTRAINED do SEEDS2) e um cenário V2.

* ``bloqueio`` (padrão): declarações PEMFC de TESTE já preenchidas; a política B04 do repositório continua pendente e o
  E2E verifica o BLOQUEIO explicado;
* ``fluxo``: as declarações PEMFC ficam VAZIAS (o E2E as preenche pela interface); demanda 40 kW e importação limitada
  a 25 kW para que a PEMFC seja despachada. Usado com a aprovação SIMULADA de ``tools/e2e/aprovacao_b04_simulada``.

Uso: python tools/e2e/seed_piso3da2h.py <dir> [bloqueio|fluxo]
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

import piso3da2h_util as H  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402


def main(data_dir: str, modo: str = "bloqueio") -> None:
    reg = MicrogridRegistry(data_dir)
    if reg.entries():
        raise SystemExit("O diretório não está vazio: use um SEEDS2_DATA_DIR novo para o E2E.")
    cfg = H.config_pemfc("Microrrede E2E 3D-A2-H")
    reg.create(cfg, origin="commissioning")
    store = reg.open(cfg["installation"]["uid"])
    if modo == "bloqueio":
        H.criar_cenario_pemfc(store, nome="PEMFC V2 (curva do modelo)", demanda_kW=30.0)
    elif modo == "fluxo":
        def vazio(doc):
            b = doc[E.CHAVE_BLOCO]
            eid = H.pemfc_id(doc)
            b["pemfc"][eid] = E._pemfc_vazia(E.pemfc_do_cenario(doc)[eid])     # declarações PEMFC VAZIAS
            b["pcc"]["limite_importacao_kW"] = 25.0
        H.criar_cenario_pemfc(store, nome="PEMFC V2 (fluxo completo)", demanda_kW=40.0, mutar=vazio)
    else:
        raise SystemExit(__doc__)
    print(f"OK: {data_dir} — microrrede {cfg['installation']['uid']} ({modo})")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
