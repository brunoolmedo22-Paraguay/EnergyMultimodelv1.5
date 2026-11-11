"""Piso 3D-A2-H — correções da auditoria externa do PR #23 (pontos A, B e D; o ponto C está em
``tests/ems_v2/test_ems_v2_b04_certificado.py`` e ``tests/test_piso3da2h_curva.py``).

A. Massa de H₂ por evento (B05): a contabilidade do MILP ``q̂(p)·Δ·u + m_SU·y + m_SD·z`` é confrontada com a integração
   TEMPORAL do modelo dinâmico em partida, parada e permanência ligada (com e sem degrau): a decomposição
   ``M_EMS − M_din = (q̂ − q)·Δ + (m − δ(p))`` é exata, o termo de evento nunca subestima e não há dupla contagem.
B. Aceitação algébrica × dinâmica: o modelo dinâmico que NÃO segue a consigna é detectado (testes negativos), a rodada
   algebricamente aprovada e dinamicamente incoerente é classificada como tal, nunca como validada, e o rótulo não pode
   ser adulterado sem que a verificação acuse.
D. Restrições físicas: P_min abaixo do IDLE, rampa acima do modelo dinâmico e transitórios incompatíveis com Δ/T_amb
   BLOQUEIAM o preflight (não são só avisos).

Dados sintéticos rotulados; modelos físicos reais do código. Missões só sob aprovação B04 SIMULADA no teste.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import piso3da2h_util as H  # noqa: E402

from ems_v2.milp.ambiente import verificar_ambiente  # noqa: E402
from integracao_v2 import curva_h2 as CH  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import execucao as X  # noqa: E402
from integracao_v2 import pemfc_dinamica as DY  # noqa: E402
from integracao_v2 import preflight as PF  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402

SOLVER = bool(verificar_ambiente().get("disponivel"))
requer_solver = pytest.mark.skipif(not SOLVER, reason="Pyomo/HiGHS não instalados (pip install -r requirements-ems_v2.txt)")
NOMINAL = CH.CondicoesPEMFC(353.15, 140.0, 120.0, 101.325)
D = 3600


@pytest.fixture(scope="module")
def curva():
    return CH.obter_curva(NOMINAL, 10.0)


@pytest.fixture(scope="module")
def analise(curva):
    return DY.analise_transitoria(NOMINAL, 25.0, 10.0, curva.p_max_kW)


def _loja(raiz: Path, **kw):
    reg = MicrogridRegistry(raiz / "dados", adopt_legacy=False)
    cfg = H.config_pemfc(**kw)
    reg.create(cfg)
    return reg, reg.open(cfg["installation"]["uid"])


def _codigos(pf, nivel=PF.ERROR):
    return {i.code for i in pf.items if i.level == nivel}


def _ponto(analise, p):
    return next(x for x in analise["pontos"] if abs(x["p_kW"] - p) < 1e-9)


# ====================================================================== A — massa por evento × integração temporal
def test_massa_adicional_da_partida_e_nula_porque_a_abstracao_ja_superconta(analise):
    """δ_SU(p) < 0 em TODO o domínio: o consumo do STARTUP (rampa até IDLE em 30 s) e da rampa até p é MENOR que o
    q(p)·Δ que a abstração instantânea já conta no intervalo inteiro. Qualquer m_SU > 0 seria contagem dupla."""
    assert all(x["delta_m_partida_kg"] < 0 for x in analise["pontos"])
    assert analise["m_partida_kg"] == 0.0
    assert analise["superestimacao_max_partida_kg"] == pytest.approx(-min(x["delta_m_partida_kg"] for x in analise["pontos"]))
    # a parada ocorre no intervalo DESLIGADO (contabilidade instantânea = 0) ⇒ massa adicional positiva, crescente com p
    msd = [x["m_parada_kg"] for x in analise["pontos"]]
    assert all(m > 0 for m in msd) and msd == sorted(msd) and analise["m_parada_kg"] == max(msd)
    assert analise["parametros_modelo_dinamico"]["partida_s"] == 30.0 and not analise["parametros_modelo_dinamico"]["partida_fria"]


@pytest.mark.parametrize("p", [10.0, 30.0, 50.0])
def test_partida_decomposicao_exata_contra_o_modelo_dinamico(curva, analise, p):
    m = (analise["m_partida_kg"], analise["m_parada_kg"])
    v = DY.verificar_despacho(NOMINAL, curva, 25.0, D, [1, 1], [p, p], False, 0.0, m)
    x0 = v["intervalos"][0]
    assert x0["evento"] == "partida" and "STARTUP" in x0["estados"]
    q_pwl, q_mod = float(curva.q_pwl([p])[0]), _ponto(analise, p)["q_regime_kg_h"]
    delta = _ponto(analise, p)["delta_m_partida_kg"]
    # M_din = q(p)·Δ + δ_SU(p) (transitório integrado no tempo) e M_EMS = q̂(p)·Δ + m_SU
    assert x0["h2_modelo_dinamico_kg"] == pytest.approx(q_mod + delta, rel=1e-12, abs=1e-12)
    assert x0["h2_ems_kg"] == pytest.approx(q_pwl + m[0], rel=1e-15)
    resid = x0["h2_ems_kg"] - x0["h2_modelo_dinamico_kg"]
    assert resid == pytest.approx((q_pwl - q_mod) + (m[0] - delta), rel=1e-9, abs=1e-12)
    assert resid >= 0                                                    # massa total NUNCA subestimada
    assert m[0] - delta <= analise["superestimacao_max_partida_kg"] + 1e-15
    # M_din JÁ inclui o consumo do estado STARTUP e mesmo assim é <= q̂(p)·Δ: somar a massa do STARTUP de novo (semântica
    # anterior, m_SU ≈ 0,00233 kg) seria contar duas vezes uma massa já coberta
    assert x0["h2_modelo_dinamico_kg"] <= q_pwl * (D / 3600)


@pytest.mark.parametrize("p", [10.0, 30.0, 50.0])
def test_parada_contabilizada_no_intervalo_desligado_sem_subestimar(curva, analise, p):
    m = (analise["m_partida_kg"], analise["m_parada_kg"])
    v = DY.verificar_despacho(NOMINAL, curva, 25.0, D, [1, 0], [p, 0.0], True, p, m)
    x1 = v["intervalos"][1]
    assert x1["evento"] == "parada" and "SHUTDOWN" in x1["estados"] and x1["energia_solicitada_kWh"] == 0.0
    assert x1["h2_modelo_dinamico_kg"] == pytest.approx(_ponto(analise, p)["m_parada_kg"], rel=1e-12, abs=1e-15)
    assert x1["h2_ems_kg"] == m[1] >= x1["h2_modelo_dinamico_kg"]
    assert m[1] - x1["h2_modelo_dinamico_kg"] <= analise["superestimacao_max_parada_kg"] + 1e-15
    assert v["coerente"]


def test_permanencia_ligada_so_carrega_o_erro_da_pwl_e_as_rampas(curva, analise):
    m = (analise["m_partida_kg"], analise["m_parada_kg"])
    v = DY.verificar_despacho(NOMINAL, curva, 25.0, D, [1, 1, 1], [30.0, 30.0, 30.0], True, 30.0, m)
    for x in v["intervalos"]:                                            # regime: só o erro B04 da PWL, ≥ 0
        assert x["evento"] == "ligada"
        resid = x["h2_ems_kg"] - x["h2_modelo_dinamico_kg"]
        assert resid == pytest.approx(float(curva.q_pwl([30.0])[0]) - _ponto(analise, 30.0)["q_regime_kg_h"], abs=1e-12)
        assert 0 <= resid <= curva.metricas["erro_abs_max_kg_h"] * 1.0 + 1e-12
    v = DY.verificar_despacho(NOMINAL, curva, 25.0, D, [1, 1, 1], [10.0, 50.0, 10.0], True, 10.0, m)
    sub, des = analise["rampas"]                                         # degraus P_mín → P_máx → P_mín
    for x, r in ((v["intervalos"][1], sub), (v["intervalos"][2], des)):
        resid = x["h2_ems_kg"] - x["h2_modelo_dinamico_kg"]
        q_pwl = float(curva.q_pwl([r["para_kW"]])[0])
        assert resid == pytest.approx(q_pwl - r["q_regime_destino_kg_h"] - r["delta_m_kg"], abs=1e-12)
    assert v["coerente"]


# ====================================================================== B — o modelo dinâmico não segue a consigna
def test_consigna_abaixo_do_idle_e_detectada_como_incoerente():
    """P_min = 5 kW (abaixo do IDLE de 10 kW — configuração que o preflight BLOQUEIA): forçada aqui, o modelo dinâmico
    entrega IDLE e não a consigna."""
    curva5 = CH.obter_curva(NOMINAL, 5.0)
    v = DY.verificar_despacho(NOMINAL, curva5, 25.0, D, [1, 1], [30.0, 5.0], True, 30.0)
    x = v["intervalos"][1]
    assert not v["coerente"] and "IDLE_MINIMUM_ENFORCED" in x["limitacoes"]
    assert x["p_entregue_media_kW"] > 9.9 and x["excesso_kWh"] > 4.9
    assert {(i["intervalo"], i["criterio"]) for i in v["incoerencias"]} >= {(1, "energia")}


def test_partida_fria_nao_e_seguida_pelo_modelo_dinamico(curva):
    an = DY.analise_transitoria(NOMINAL, 0.0, 10.0, curva.p_max_kW)
    v = DY.verificar_despacho(NOMINAL, curva, 0.0, D, [0, 1, 1], [0.0, 40.0, 40.0], False, 0.0,
                              (an["m_partida_kg"], an["m_parada_kg"]))
    x = v["intervalos"][1]
    assert x["evento"] == "partida" and an["parametros_modelo_dinamico"]["partida_s"] == 600.0
    assert x["deficit_kWh"] == pytest.approx(-_ponto(an, 40.0)["delta_E_partida_kWh"], rel=1e-9)     # = análise a priori
    assert x["deficit_kWh"] > 5 * x["tolerancia_energia_kWh"] and not x["coerente_energia"] and not v["coerente"]
    assert v["intervalos"][2]["coerente_energia"]                       # já em regime no intervalo seguinte


def test_delta_curto_torna_a_partida_quente_incompativel(curva, analise):
    assert DY.admissibilidade(analise, curva, 3600, "instantanea_unidade_quente") == []
    for d in (900, 300):
        viol = DY.admissibilidade(analise, curva, d, "instantanea_unidade_quente")
        assert viol and {v["caso"] for v in viol} >= {"partida"}
    assert DY.admissibilidade(analise, curva, 60, "instantanea_unidade_quente")[0]["caso"] == "delta_menor_que_o_transitorio"
    assert DY.admissibilidade(analise, curva, 900, "transicoes_bloqueadas") == []      # sem partida/parada: só rampas


def test_reavaliacao_sem_modelo_reproduz_a_coerencia():
    v = DY.verificar_despacho(NOMINAL, CH.obter_curva(NOMINAL, 5.0), 25.0, D, [1, 1], [30.0, 5.0], True, 30.0)
    ok, inc = DY.reavaliar_coerencia(v, dict(DY.TOLERANCIAS))
    assert ok is v["coerente"] is False and {(i["intervalo"], i["criterio"]) for i in inc} == \
        {(i["intervalo"], i["criterio"]) for i in v["incoerencias"]}


# ====================================================================== D — restrições físicas BLOQUEIAM
def test_pmin_abaixo_do_idle_bloqueia(tmp_path):
    _r, store = _loja(tmp_path)
    pf = PF.preparar(store, H.criar_cenario_pemfc(store, pemfc_kw={"p_min": 5.0}))
    assert "pemfc_pmin_abaixo_do_idle" in _codigos(pf) and not pf.ok
    assert not [i for i in pf.items if i.level == PF.WARNING and "IDLE" in i.message]   # não é mais só aviso


def test_rampa_acima_do_modelo_dinamico_bloqueia(tmp_path):
    _r, store = _loja(tmp_path)
    pf = PF.preparar(store, H.criar_cenario_pemfc(store, pemfc_kw={"rampa": 150.0}))
    assert "pemfc_rampa_acima_do_modelo_dinamico" in _codigos(pf) and not pf.ok
    pf = PF.preparar(store, H.criar_cenario_pemfc(store, pemfc_kw={"rampa": 120.0}))
    assert "pemfc_rampa_acima_do_modelo_dinamico" not in _codigos(pf)


def test_partida_fria_bloqueia_a_abstracao_instantanea_mas_nao_as_transicoes_bloqueadas(tmp_path):
    _r, store = _loja(tmp_path)
    pf = PF.preparar(store, H.criar_cenario_pemfc(store, pemfc_kw={"t_amb": 0.0}))
    assert "pemfc_transitorio_incompativel" in _codigos(pf) and not pf.ok
    assert any("FRIA" in i.message for i in pf.items if i.code == "pemfc_transitorio_incompativel")
    pf = PF.preparar(store, H.criar_cenario_pemfc(store, pemfc_kw={"t_amb": 0.0, "abstracao": "transicoes_bloqueadas"}))
    assert "pemfc_transitorio_incompativel" not in _codigos(pf)


def test_configuracao_nominal_e_admissivel_e_registra_a_analise(tmp_path):
    _r, store = _loja(tmp_path)
    pf = PF.preparar(store, H.criar_cenario_pemfc(store))
    assert not {"pemfc_pmin_abaixo_do_idle", "pemfc_rampa_acima_do_modelo_dinamico",
                "pemfc_transitorio_incompativel"} & _codigos(pf)
    assert any("restrições do modelo dinâmico compatíveis" in i.message for i in pf.items if i.level == PF.OK)
    reg = next(iter(pf.montagem.doc_pemfc["registros"].values()))
    assert reg["admissibilidade"]["violacoes"] == [] and reg["massas_eventos"]["m_partida_kg"] == 0.0
    sp = pf.montagem.modelo.compromisso.unidades[0]
    assert sp.massa_h2_partida_kg.valor == 0.0 and sp.massa_h2_parada_kg.valor == reg["massas_eventos"]["m_parada_kg"]


# ====================================================================== B — missão algebricamente aprovada × dinâmica
@pytest.fixture(scope="module")
def incoerente(tmp_path_factory):
    """Configuração INCOMPATÍVEL (partida fria) forçada além do preflight — o bloqueio a priori é DESLIGADO só aqui para
    provar a segunda linha de defesa: a rodada conclui algebricamente, mas é classificada dinamicamente INCOERENTE."""
    if not SOLVER:
        return None
    raiz = tmp_path_factory.mktemp("incoerente3da2h")
    reg, store = _loja(raiz)
    sc = H.criar_cenario_pemfc(store, demanda_kW=40.0, pemfc_kw={"t_amb": 0.0, "preco": 10.0},
                               mutar=lambda doc: doc[E.CHAVE_BLOCO]["pcc"].update(limite_importacao_kW=25.0))
    mp = pytest.MonkeyPatch()
    mp.setattr(DY, "admissibilidade", lambda *a, **k: [])
    try:
        run = X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    finally:
        mp.undo()
    return {"raiz": raiz, "store": store, "run": run}


@requer_solver
def test_rodada_algebricamente_aprovada_e_dinamicamente_incoerente_nunca_e_validada(incoerente):
    run, store = incoerente["run"], incoerente["store"]
    assert run.state == "concluida", run.error                           # evidência ALGÉBRICA completa e auditada
    acc = run.summary["execution"]["aceitacao"]
    assert acc["classificacao"] == "algebrica_aprovada_dinamica_incoerente"
    assert acc["algebrica"]["estado"] == "aprovada" and acc["dinamica"]["estado"] == "incoerente"
    assert acc["fisica"]["estado"] == "nao_validada" and "NÃO representa operação executável" in acc["rotulo"]
    din = RG.ler_json(store, run, RG.N_PEMFC_DIN)
    (u, v), = din["unidades"].items()
    assert not din["coerente"] and any(i["evento"] == "partida" and i["criterio"] == "energia" for i in v["incoerencias"])
    ver = RG.verificar(store, run)
    assert ver.ok, ver.falhas()                                          # evidência íntegra …
    assert any("dinâmica INCOERENTE" in t for ok, t in ver.itens if ok)  # … e classificada como tal


@requer_solver
def test_rotulo_de_aceitacao_adulterado_e_detectado(incoerente):
    run, store = incoerente["run"], incoerente["store"]
    falso = copy.deepcopy(run)
    acc = falso.summary["execution"]["aceitacao"]
    acc.update(classificacao="algebrica_aprovada_dinamica_coerente", rotulo=X.ROTULOS_ACEITACAO[
        "algebrica_aprovada_dinamica_coerente"])
    acc["dinamica"]["estado"] = "coerente"
    ver = RG.verificar(store, falso)
    assert not ver.ok and any("Aceitação SEPARADA" in t for t in ver.falhas())


@requer_solver
def test_coerencia_gravada_adulterada_e_detectada(incoerente):
    import json
    run, store = incoerente["run"], incoerente["store"]
    din = RG.ler_json(store, run, RG.N_PEMFC_DIN)
    (u, v), = din["unidades"].items()
    v["coerente"] = din["coerente"] = True
    v["incoerencias"] = []
    for x in v["intervalos"]:
        x["coerente_energia"] = x["coerente_h2"] = True

    class Fonte:
        def run_data(self, uid, nome):
            return json.dumps(din).encode() if nome == RG.N_PEMFC_DIN else store.run_data(uid, nome)
    ver = RG.verificar(Fonte(), run)
    assert not ver.ok and any("RECALCULADA" in t for t in ver.falhas())


@requer_solver
def test_h2_do_ems_na_verificacao_e_a_contabilidade_selada_do_milp(incoerente):
    run, store = incoerente["run"], incoerente["store"]
    df = RG.ler_csv(store, run, RG.N_INTERVALOS)
    din = RG.ler_json(store, run, RG.N_PEMFC_DIN)
    (u, v), = din["unidades"].items()
    assert np.allclose([x["h2_ems_kg"] for x in v["intervalos"]], df[f"{u}|m_h2_kg"].astype(float), rtol=1e-12, atol=1e-15)
