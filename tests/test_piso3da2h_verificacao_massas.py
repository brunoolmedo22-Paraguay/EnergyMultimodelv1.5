"""Piso 3D-A2-H — verificação INDEPENDENTE das massas adicionais por evento (decisão do responsável no PR #23, item 3A).

Roda ``tests/verificacao_massas_3da2h.py`` (intervalos COMPLETOS de 60 min, integração própria, malha densa) na configuração
nominal e confronta com a análise a priori do preflight. O roteiro completo (seis configurações, malha de 0,5 kW e pares
a cada 2,5 kW) gera a evidência ``docs/ems_v2/evidencia_3da2h/verificacao_massas_eventos.json``.

Conclusões verificadas (sem garantia global baseada em 9 pontos):
* partidas, paradas e rampas de SUBIDA: a massa contabilizada pelo EMS nunca é menor que a do modelo dinâmico;
* rampas de DESCIDA em operação contínua: o modelo dinâmico consome MAIS do que a abstração instantânea conta (não há
  termo de rampa no MILP) — subestimação LIMITADA, máxima na rampa P_máx → P_mín, igual à da análise a priori e dentro
  da tolerância dinâmica declarada.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verificacao_massas_3da2h as V  # noqa: E402

from integracao_v2 import curva_h2 as CH  # noqa: E402
from integracao_v2 import pemfc_dinamica as DY  # noqa: E402


@pytest.fixture(scope="module")
def nominal():
    return V.verificar_configuracao(V.CONFIGURACOES[0], passo_eventos_kW=1.0, passo_rampas_kW=5.0)


def test_partidas_paradas_e_rampas_de_subida_nunca_subestimam(nominal):
    assert nominal["admissivel_a_priori"] and nominal["n_partidas"] == 41 and nominal["n_rampas"] >= 72
    for caso in ("partida", "parada", "rampa_subida"):
        assert nominal[caso]["casos_com_subestimacao"] == 0, (caso, nominal[caso])
        assert nominal[caso]["residuo_min_kg"] >= -1e-12
    # a parada atinge a igualdade em P_máx (m_SD = δ_SD(P_máx)); a partida tem folga em todo o domínio (m_SU = 0)
    assert nominal["parada"]["caso"]["p_kW"] == pytest.approx(nominal["p_max_kW"])
    assert nominal["partida"]["residuo_min_kg"] > 0 and nominal["m_partida_kg"] == 0.0


def test_rampas_de_descida_subestimam_de_forma_limitada_e_igual_a_analise_a_priori(nominal):
    d = nominal["rampa_descida"]
    assert d["casos_com_subestimacao"] > 0                                   # subestimação EXISTE: sem garantia global
    assert d["caso"]["de_kW"] == pytest.approx(nominal["p_max_kW"]) and d["caso"]["para_kW"] == pytest.approx(10.0)
    curva = CH.obter_curva(CH.CondicoesPEMFC(*V.CONFIGURACOES[0]["cond"]), 10.0)
    an = DY.analise_transitoria(CH.CondicoesPEMFC(*V.CONFIGURACOES[0]["cond"]), 25.0, 10.0, curva.p_max_kW)
    desc = an["rampas"][1]                                                   # P_máx → P_mín da análise a priori
    a_priori = desc["delta_m_kg"] - (float(curva.q_pwl([10.0])[0]) - desc["q_regime_destino_kg_h"])
    assert d["subestimacao_max_kg"] == pytest.approx(a_priori, rel=1e-9, abs=1e-12)   # dois caminhos independentes
    assert d["subestimacao_max_kg"] <= DY.tolerancia_h2_kg(d["caso"]["ems_kg"], 3600.0)
    assert d["subestimacao_max_rel"] < 0.01


def test_energia_dos_transitorios_dentro_das_tolerancias(nominal):
    assert nominal["energia_partida_deficit_max_kWh"] <= DY.tolerancia_energia_kWh(nominal["p_max_kW"], 3600.0)
    assert nominal["energia_parada_excesso_max_kWh"] <= DY.tolerancia_energia_kWh(0.0, 3600.0)
    assert nominal["energia_rampa_desvio_max_kWh"] <= DY.tolerancia_energia_kWh(10.0, 3600.0)
