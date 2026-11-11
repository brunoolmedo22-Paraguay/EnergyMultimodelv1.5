"""Piso 3D-A2-H — curva estacionária q_H₂(P_net) derivada do modelo físico PEMFC existente (sem solver EMS).

Oráculo INDEPENDENTE da PWL: o solucionador de potência do PRÓPRIO modelo (``solve_requested_power``, brentq na rama) em
potências escolhidas no teste — pontos que o gerador não usou. Nenhum valor esperado é digitado: a curva é comparada ao
modelo e às propriedades exigidas pela adenda B04.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from integracao_v2 import curva_h2 as CH  # noqa: E402
import piso3da2h_util as H  # noqa: E402

NOMINAL = CH.CondicoesPEMFC(353.15, 140.0, 120.0, 101.325)
OUTRA = CH.CondicoesPEMFC(343.15, 100.0, 80.0, 101.325)


def _modelo_q(cond, P):
    from h2_pemfc import Equivalent65kWHorizonPowerRequestModel
    df = Equivalent65kWHorizonPowerRequestModel().solve_requested_power(np.asarray(P, float), **cond.kwargs())
    return df["hydrogen_supplied_kg_h"].to_numpy(float), df["P_FC_delivered_kW"].to_numpy(float)


def test_curva_concorda_com_o_modelo_em_pontos_independentes():
    c = CH.obter_curva(NOMINAL, 10.0)
    P = np.array([10.4, 13.7, 21.05, 29.9, 37.3, 44.44, 49.6])
    q, entregue = _modelo_q(NOMINAL, P)
    assert np.allclose(entregue, P, atol=1e-6)
    rel = np.abs(c.q_pwl(P) - q) / q
    assert rel.max() <= CH.POLITICA_B04["erro_rel_max"]
    assert (c.q_pwl(P) >= q * (1 - CH.POLITICA_B04["subestimacao_rel_max"])).all()   # sem subestimação material
    # extremos = avaliações exatas do modelo (vértices nas extremidades do domínio)
    qe, _ = _modelo_q(NOMINAL, [c.p_min_kW, c.p_max_kW])
    assert c.vertices[0] == (c.p_min_kW, pytest.approx(qe[0], rel=1e-12))
    assert c.vertices[-1][1] == pytest.approx(qe[1], rel=1e-12)


def test_dominio_sem_zero_sem_extrapolacao_e_monotonia():
    c = CH.obter_curva(NOMINAL, 10.0)
    assert c.p_min_kW == 10.0 and c.vertices[0][0] == 10.0 and c.vertices[0][0] > 0      # OFF = estado separado
    assert c.p_max_kW == pytest.approx(min(c.diagnostico_rama["potencia_max_rama_kW"],
                                           c.diagnostico_rama["pico_declarado_kW"]))
    Q = [v[1] for v in c.vertices]
    assert all(b > a for a, b in zip(Q, Q[1:])) and all(b[0] > a[0] for a, b in zip(c.vertices, c.vertices[1:]))
    with pytest.raises(ValueError):
        c.q_pwl([c.p_max_kW + 0.5])
    with pytest.raises(ValueError):
        c.q_pwl([5.0])
    assert c.metricas["dominio_fechado"] and c.metricas["continua"]


def test_duas_inicializacoes_fisicas_produzem_curvas_coerentes_e_distintas():
    a, b = CH.obter_curva(NOMINAL, 10.0), CH.obter_curva(OUTRA, 10.0)
    assert a.impressao != b.impressao and a.sha_curva != b.sha_curva
    for c, cond in ((a, NOMINAL), (b, OUTRA)):
        P = np.linspace(c.p_min_kW + 0.3, c.p_max_kW - 0.3, 9)
        q, _ = _modelo_q(cond, P)
        assert (np.abs(c.q_pwl(P) - q) / q).max() <= CH.POLITICA_B04["erro_rel_max"]
        assert c.b04["conforme_aos_limiares"] is True
    assert b.p_max_kW != a.p_max_kW            # condições diferentes ⇒ rama diferente (sem valor fixo presumido)


def test_inicializacao_identica_reutiliza_a_curva_sem_regenerar():
    a = CH.obter_curva(NOMINAL, 12.0)
    n = CH.GERACOES["n"]
    for _ in range(25):                        # p. ex. 25 janelas MPC / replanejamentos com a mesma configuração
        b = CH.obter_curva(CH.CondicoesPEMFC(353.15, 140.0, 120.0, 101.325), 12.0)
        assert b is a
        b.q_pwl(np.linspace(12.0, 40.0, 7))   # potências distintas consultam a MESMA curva
    assert CH.GERACOES["n"] == n
    c = CH.obter_curva(NOMINAL, 13.0)          # um parâmetro da identidade mudou ⇒ nova curva
    assert c is not a and CH.GERACOES["n"] == n + 1


def test_identidade_cobre_condicoes_pmin_politica_e_versao_do_modelo():
    ident = CH.identidade(NOMINAL, 10.0)
    assert set(ident) >= {"gerador", "gerador_fonte_sha256", "modelo_fonte_sha256", "condicoes", "p_min_kW",
                          "politica_aproximacao", "politica_b04", "parametros_modelo"}
    assert ident["condicoes"] == {"temperatura_stack_K": 353.15, "pressao_anodo_kPag": 140.0,
                                  "pressao_catodo_kPag": 120.0, "pressao_ambiente_kPa": 101.325}
    assert CH.impressao(ident) == CH.impressao(CH.identidade(NOMINAL, 10.0))
    pol = CH.PoliticaAproximacao(erro_rel_alvo=0.0005)
    assert CH.impressao(CH.identidade(NOMINAL, 10.0, pol)) != CH.impressao(ident)
    assert any(r["parameter_id"] == "hydrogen_utilization" for r in ident["parametros_modelo"]["balance_of_plant"]) \
        or ident["parametros_modelo"]["balance_of_plant"]


@pytest.mark.parametrize("cond, pmin, trecho", [
    (CH.CondicoesPEMFC(353.15, 140.0, 120.0, float("nan")), 10.0, "pressao_ambiente_kPa"),
    (NOMINAL, None, "P_min"),
    (NOMINAL, 0.0, "P_min"),
    (NOMINAL, 60.0, "não é menor"),
])
def test_nenhuma_curva_com_parametros_ausentes_ou_incoerentes(cond, pmin, trecho):
    with pytest.raises(CH.CurvaInvalida) as e:
        CH.obter_curva(cond, pmin)
    assert trecho in str(e.value)


def test_politica_do_repositorio_aprovada_com_limiares_e_identidade_exatos():
    """Decisão do responsável no PR #23: b04-proposta-2 APROVADA sem alterar limiares, identidade nem versão."""
    from ems_v2 import contracts as K
    pol = CH.POLITICA_B04
    assert pol["versao"] == "b04-proposta-2" and pol["situacao"] == K.SITUACAO_B04_APROVADA
    assert (pol["erro_rel_max"], pol["erro_abs_max_kg_h"], pol["subestimacao_rel_max"],
            pol["erro_massa_temporal_rel_max"], pol["pontos_validacao_min"]) == (0.005, 0.02, 0.001, 0.002, 200)
    h = CH.hash_politica_nucleo()
    assert h == "412863021aee9d29e1972760e4a5469e509e0de9260ffe9bf62096d932071c9a"     # identidade = a congelada
    reg = K.POLITICAS_B04_NUCLEO[h]
    assert reg["situacao"] == K.SITUACAO_B04_APROVADA and reg["versao"] == "b04-proposta-2" and reg["aprovada_em"]
    assert "NÃO é validação experimental" in reg["alcance"] and "não é validação experimental" in pol["alcance_aprovacao"]
    assert list(K.POLITICAS_B04_NUCLEO) == [h]                                      # nenhuma outra política reconhecida


def test_b04_aprovada_certifica_so_curva_conforme_e_nunca_por_autodeclaracao():
    c = CH.obter_curva(NOMINAL, 10.0)
    assert CH.CLASSIFICACAO_CONTRATO == "real"            # nunca rotulada "sintetica_exata"
    assert CH.avaliar_b04(c.metricas)["estado"] == "certificada" and c.b04["conforme_aos_limiares"]
    # a aprovação da política não aprova qualquer curva: uma curva fora dos limiares é REPROVADA
    m = dict(c.metricas, erro_rel_max=0.006)
    assert CH.avaliar_b04(m)["estado"] == "reprovada"
    # limiares alterados ⇒ política não reconhecida pelo núcleo (nunca "certificada" contra limiares forjados)
    for forjada in (dict(CH.POLITICA_B04, erro_rel_max=1e-6), dict(CH.POLITICA_B04, erro_rel_max=1.0)):
        assert CH.avaliar_b04(c.metricas, forjada)["estado"] == "politica_nao_reconhecida_pelo_nucleo"
    with H.politica_pendente_no_teste():                  # REVOGAÇÃO simulada: conformidade ≠ certificação
        assert CH.avaliar_b04(c.metricas)["estado"] == "conforme_limiares_pendentes_de_aprovacao"
        autodeclarada = dict(CH.POLITICA_B04, situacao="aprovada_pelo_responsavel")   # autodeclaração sem autoridade
        assert CH.avaliar_b04(c.metricas, autodeclarada)["estado"] == "conforme_limiares_pendentes_de_aprovacao"


def test_documento_persistivel_e_deterministico():
    c = CH.obter_curva(NOMINAL, 10.0)
    d = c.doc()
    txt = json.dumps(d, sort_keys=True, allow_nan=False)
    assert d["classificacao_contrato"] == "real" and d["unidade_q"].startswith("kg/h")
    assert len(d["validacao"]["P_kW"]) == c.metricas["pontos_validacao"] >= CH.POLITICA_B04["pontos_validacao_min"]
    assert not set(d["validacao"]["P_kW"]) & set(d["ajuste"]["P_kW"])       # validação independente do ajuste
    assert json.loads(txt)["sha_curva"] == c.sha_curva


try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class BancadaH2CurvaTest(unittest.TestCase):
    def test_bancada_mostra_modelo_pwl_vertices_dominio_e_erro(self):
        from apptest_utils import APP_PATH
        with tempfile.TemporaryDirectory() as d:
            os.environ["SEEDS2_DATA_DIR"] = d
            app = AppTest.from_file(str(APP_PATH), default_timeout=180)
            app.session_state["energy_source"] = "h2"
            app.session_state["h2_page"] = "Caracterização"
            app.run()
            self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
            specs = [json.loads(c.proto.spec) for c in app.get("plotly_chart")]
            fig = next(s for s in specs if s["layout"].get("title", {}).get("text") == "Consumo de hidrogênio × potência líquida")
            nomes = [t["name"] for t in fig["data"]]
            self.assertIn("Modelo físico (H₂ suprido)", nomes)
            self.assertIn("PWL usada pelo EMS", nomes)
            self.assertIn("Vértices da PWL", nomes)
            self.assertIn("H₂ estequiométrico consumido (referência)", nomes)
            self.assertIn("g/s", fig["layout"]["yaxis"]["title"]["text"])
            self.assertTrue(fig["layout"].get("shapes"))                   # faixa P_mín–P_máx
            self.assertTrue(any("Erro da aproximação" in s["layout"].get("title", {}).get("text", "") for s in specs))
            metr = {m.label: m.value for m in app.metric}
            self.assertEqual(metr["Potência máxima admissível"], "50.00 kW")
            self.assertEqual(metr["Certificação B04 (matemática)"], "Certificada")   # política aprovada (PR #23)
            m04 = next(m for m in app.metric if m.label == "Certificação B04 (matemática)")
            self.assertIn("NÃO é validação experimental", m04.proto.help)
            txt = "\n".join([c.value for c in app.caption] + [m.value for m in app.markdown] +
                             ["\n".join(h.proto.body for h in app.get("html"))])
            self.assertIn("modelo físico APROXIMADO", txt) and self.assertIn("verificada MATEMATICAMENTE", txt)
            app.radio(key="h2_cv_un").set_value("kg/h").run()
            specs = [json.loads(c.proto.spec) for c in app.get("plotly_chart")]
            fig = next(s for s in specs if s["layout"].get("title", {}).get("text") == "Consumo de hidrogênio × potência líquida")
            self.assertIn("kg/h", fig["layout"]["yaxis"]["title"]["text"])


def test_massa_acumulada_integrada_no_tempo_em_perfis_independentes():
    c = CH.obter_curva(NOMINAL, 10.0)
    nomes = {x["nome"] for x in c.perfis}
    assert {"carga_parcial_25", "carga_parcial_50", "carga_parcial_75", "nominal_pmax", "despacho_degraus_15min",
            "despacho_continuo_senoidal"} <= nomes
    for x in c.perfis:
        assert x["passo_h"] == pytest.approx(1 / 60) and len(x["potencias_kW"]) == len(x["vazoes_modelo_kg_h"])
        mm = sum(v * x["passo_h"] for v in x["vazoes_modelo_kg_h"])            # kg = Σ (kg/h)·h
        assert x["massa_modelo_kg"] == pytest.approx(mm, rel=1e-12)
        mp = sum(float(c.q_pwl([p])[0]) * x["passo_h"] for p in x["potencias_kW"])
        assert x["massa_pwl_kg"] == pytest.approx(mp, rel=1e-12)
        assert x["erro_massa_rel"] <= CH.POLITICA_B04["erro_massa_temporal_rel_max"]
    nom = next(x for x in c.perfis if x["nome"] == "nominal_pmax")
    assert nom["massa_modelo_kg"] == pytest.approx(c.metricas["q_pmax_kg_h"] * 4.0, rel=1e-12)   # 4 h a P_max
    assert "erro_integral_dominio_potencia_rel" in c.metricas      # ∫q dP: métrica sobre o DOMÍNIO, não massa


def test_generalizacao_em_condicoes_nao_usadas_para_os_limiares():
    res = CH.avaliar_generalizacao()
    assert len(res) == len(CH.CONDICOES_GENERALIZACAO) >= 5
    assert all(r["conforme"] for r in res), res
    assert len({round(r["p_max_kW"], 6) for r in res}) > 1                 # condições realmente diferentes


def test_certificado_do_nucleo_so_registra_com_politica_aprovada():
    from ems_v2 import contracts as K
    c = CH.obter_curva(NOMINAL, 10.0)
    with H.politica_pendente_no_teste():                                      # REVOGAÇÃO simulada
        h, cs = K.registrar_certificado_b04(CH.certificado_b04(c))
        assert {x.codigo for x in cs} == {"politica_b04_nao_aprovada"} and K.certificado_b04_registrado(h) is None
        autodeclarada = dict(CH.POLITICA_B04, situacao=K.SITUACAO_B04_APROVADA)   # o certificado "se aprova" sozinho
        h1, cs1 = K.registrar_certificado_b04(CH.certificado_b04(c, autodeclarada))
        assert h1 == "" and "politica_b04_situacao_divergente" in {x.codigo for x in cs1}
    assert CH.hash_politica_nucleo() in K.POLITICAS_B04_NUCLEO                # a política da integração é a congelada
    h2, cs2 = K.registrar_certificado_b04(CH.certificado_b04(c))                # caminho NORMAL (política aprovada)
    assert cs2 == [] and K.certificado_b04_registrado(h2).vertices == c.vertices
    pendente = dict(CH.POLITICA_B04, situacao="proposta_congelada_pendente_de_aprovacao")   # declara o contrário do núcleo
    h3, cs3 = K.registrar_certificado_b04(CH.certificado_b04(c, pendente))
    assert h3 == "" and "politica_b04_situacao_divergente" in {x.codigo for x in cs3}


def test_valores_do_modelo_no_certificado_sao_reverificados_contra_o_modelo():
    import copy
    c = CH.obter_curva(NOMINAL, 10.0)
    assert CH.verificar_contra_modelo(c.doc()) == []
    d = copy.deepcopy(c.doc())
    d["validacao"]["q_modelo_kg_h"][7] *= 1.0001                           # valor "do modelo" fabricado
    assert CH.verificar_contra_modelo(d)
    d = copy.deepcopy(c.doc())
    d["perfis_temporais"][4]["vazoes_modelo_kg_h"][3] *= 0.999
    assert any("despacho_degraus_15min" in x for x in CH.verificar_contra_modelo(d))
