"""Piso 3C-3 — G15: retrocompatibilidade. Os experimentos 3C-2 (E1–E8) reproduzem EXATAMENTE as impressões registradas
na base ``a4c6b1c`` (merge do PR #15) ANTES da refatoração controlada do orquestrador (pontos de extensão).

``tests/ems_v2/dados/pins_3c2_base_a4c6b1c.json`` foi gerado na base, sem nenhuma alteração do 3C-3, e contém por
experimento: impressão determinística da missão, hash do conteúdo de cada janela, SHA-256 do CONTEÚDO de cada anexo
3C-1, SHA-256 de cada plano 3C-0 e o custo realizado acumulado. Nenhum valor é tolerado: igualdade exata.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

from ems_v2.mpc import experimentos as X  # noqa: E402
from ems_v2.ponte.canonico import sha256  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
PINS = json.loads((Path(__file__).parent / "dados" / "pins_3c2_base_a4c6b1c.json").read_text(encoding="utf-8"))


def _imp(ex):
    r = ex.resultado
    return {"missao": r.registro_missao.impressao_deterministica if r.registro_missao else None,
            "janelas": [x.hash_conteudo for x in r.registros], "anexos": [sha256(a.conteudo) for a in r.anexos_3c1],
            "planos": [x.plano and sha256(x.plano) for x in r.registros_3c0],
            "custo": r.registro_missao.conteudo.custo_realizado_acumulado.total_R if r.registro_missao else None}


@pytest.fixture(scope="module")
def atual():
    out = {}
    e1 = X.e1_oraculo()
    out["E1_mpc"], out["E1_hc"] = _imp(e1["mpc"]), _imp(e1["horizonte_completo"])
    out["E2"] = _imp(X.e2_previsao_reemitida()["mpc"])
    e3 = X.e3_open_loop_vs_mpc()
    out["E3_ol"], out["E3_mpc"] = _imp(e3["open_loop"]), _imp(e3["mpc"])
    for m, ex in X.e4_frequencia().items():
        out[f"E4_m{m}"] = _imp(ex)
    out["E5"] = _imp(X.e5_memoria())
    out["E7"] = _imp(X.e7_falha_na_janela(1, X.resultado_sem_solucao))
    for p in ("registrar_sem_reconciliar", "interromper"):
        out[f"E8_{p}"] = _imp(X.e8_revisao_tardia(p))
    return out


@pytest.mark.parametrize("nome", sorted(PINS))
def test_g15_experimentos_3c2_identicos_a_base(atual, nome):
    assert atual[nome] == PINS[nome]


def test_g15_pins_cobrem_e1_a_e8():
    assert {k.split("_")[0] for k in PINS} == {"E1", "E2", "E3", "E4", "E5", "E7", "E8"}
    assert PINS["E2"]["custo"] == pytest.approx(12.9) and PINS["E3_ol"]["custo"] == pytest.approx(18.7)
