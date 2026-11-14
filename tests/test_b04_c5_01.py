"""B04-C5-01 — admissibilidade DINÂMICA a priori da PEMFC × certificado B04 (caso C5 EMB-H2-120, HIPOTÉTICO).

Missão autorizada pelo responsável (P1): só o DIAGNÓSTICO (texto) do bloqueio ``pemfc_transitorio_incompativel`` mudou.
Física, tolerâncias, abstrações, critérios e decisões do EMS ficam inalterados — estes testes FIXAM o veredito e os números
com um oráculo INDEPENDENTE (trajetória discreta reescrita aqui a partir das taxas do manual e do modelo ESTÁTICO) e
verificam a coerência entre a análise a priori, o preflight e uma missão real (HiGHS) nos Δ admissíveis.

Configuração física do C5 (declarações de TESTE, procedência sintética): condições nominais (353,15 K; 140/120 kPa(g);
101,325 kPa), P_mín 10 kW, T_amb 25 °C, rampa 120 kW/min, T_on = T_off = 0, H₂ R$ 10/kg, unidade em operação a 30 kW há
15 min, ``transicoes_bloqueadas``; BESS 150 kWh / 75 kW, SOC 50 %; FV; PCC isolado; missão de 120 min.
"""
from __future__ import annotations

import copy
import io
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import piso3da2h_util as H  # noqa: E402
import piso3da2r_util as R  # noqa: E402
import piso3da_util as U  # noqa: E402
from ems_v2.compromisso.contrato import discretizar  # noqa: E402
from ems_v2.milp.ambiente import verificar_ambiente  # noqa: E402
from integracao_v2 import curva_h2 as CH  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import execucao as X  # noqa: E402
from integracao_v2 import pemfc_dinamica as DY  # noqa: E402
from integracao_v2 import preflight as PF  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.operation import forecast_sources as FS  # noqa: E402
from seeds2.operation import service as SV  # noqa: E402

SOLVER = bool(verificar_ambiente().get("disponivel"))
requer_solver = pytest.mark.skipif(not SOLVER, reason="Pyomo/HiGHS não instalados (pip install -r requirements-ems_v2.txt)")

COND = CH.CondicoesPEMFC(353.15, 140.0, 120.0, 101.325)        # = H.NOMINAL (condições declaradas do C5)
P_MIN, T_AMB, DURACAO = 10.0, 25.0, 120
SUBIDA_KW_S, DESCIDA_KW_S = 2.0, 3.5                           # manual Horizon, Tabela 4.2 (lidos do modelo e conferidos)
TOL = {"energia_rel": 0.02, "potencia_media_abs_kW": 0.5, "h2_rel": 0.02, "vazao_media_abs_kg_h": 0.02}
BLOQ, INST = "transicoes_bloqueadas", "instantanea_unidade_quente"
LIGADA_30 = ("em_operacao", 30.0, 15.0)
DESLIGADA = ("desligada", 0.0, 600.0)


# ------------------------------------------------------------------------------------------------ oráculo independente
@lru_cache(maxsize=1)
def _estatico():
    from h2_pemfc import Equivalent65kWHorizonPowerRequestModel
    return Equivalent65kWHorizonPowerRequestModel()


def _q(p) -> np.ndarray:
    """H₂ SUPRIDO em regime [kg/h] pelo modelo ESTÁTICO (instância própria, condições declaradas; sem pemfc_dinamica)."""
    df = _estatico().solve_requested_power(np.atleast_1d(np.asarray(p, dtype=float)), **COND.kwargs())
    return df["hydrogen_supplied_kg_h"].to_numpy(dtype=float)


def _trajetoria(pa: float, pb: float, taxa_kW_s: float, passo_s: float = 1.0) -> np.ndarray:
    """Alvos do modelo dinâmico após a consigna pa → pb, reescritos AQUI: retenção de ordem zero com passo interno de 1 s,
    a 1ª amostra (no instante da consigna) já aplica um passo de rampa; o último alvo é pb (regime)."""
    out, p = [], pa
    while abs(p - pb) > 1e-12:
        p = max(p - taxa_kW_s * passo_s, pb) if pb < pa else min(p + taxa_kW_s * passo_s, pb)
        out.append(p)
    return np.asarray(out)


def _oraculo_rampa(pa: float, pb: float) -> tuple[float, float]:
    """ΔH₂ [kg] e ΔE [kWh] da rampa em operação contínua em relação ao regime no destino (o que o MILP contabiliza)."""
    ps = _trajetoria(pa, pb, DESCIDA_KW_S if pb < pa else SUBIDA_KW_S)
    return float(np.sum(_q(ps) - _q([pb])[0])) / 3600.0, float(np.sum(ps - pb)) / 3600.0


@lru_cache(maxsize=4)
def _curva():
    return CH.obter_curva(COND, P_MIN)


def _analise(t_amb: float = T_AMB) -> dict:
    return DY.analise_transitoria(COND, t_amb, P_MIN, float(_curva().p_max_kW))


def _violacoes_esperadas(delta_min: float) -> set[tuple[str, str]]:
    """Critérios de rampa violados segundo o ORÁCULO e as tolerâncias DECLARADAS reescritas aqui (sem pemfc_dinamica)."""
    h = delta_min / 60.0
    curva = _curva()
    out = set()
    for pa, pb in ((P_MIN, curva.p_max_kW), (curva.p_max_kW, P_MIN)):
        dm, de = _oraculo_rampa(pa, pb)
        m_ems = float(curva.q_pwl([pb])[0]) * h
        m_din = float(_q([pb])[0]) * h + dm
        if abs(de) > max(TOL["energia_rel"] * pb * h, TOL["potencia_media_abs_kW"] * h):
            out.add((f"{pb:g}", "energia_kWh"))
        if abs(m_ems - m_din) > max(TOL["h2_rel"] * m_ems, TOL["vazao_media_abs_kg_h"] * h):
            out.add((f"{pb:g}", "h2_kg"))
    return out


# ------------------------------------------------------------------------------------------------ cenário C5 (catálogo)
def _loja(raiz: Path):
    reg = MicrogridRegistry(raiz / "dados", adopt_legacy=False)
    cfg = H.config_pemfc("C5 EMB-H2-120 (teste, HIPOTÉTICO)", fv=True, eolica=False, energia_kWh=150.0, modo="isolada",
                         ns=6, np_=2)
    reg.create(cfg)
    return reg, reg.open(cfg["installation"]["uid"])


def _clima(doc):
    n = DURACAO // 5
    return R.clima_tabela(doc, {"ghi_W_m2": [800.0] * n, "temperature_C": [25.0] * n, "wind_speed_m_s": [0.0] * n},
                          passo_s=300)


def _c5(store, delta_min: int, *, abstracao: str = BLOQ, t_amb: float = T_AMB, estado=LIGADA_30, rampa: float = 120.0,
        demanda=None, N: int | None = None, H_L: int | None = None):
    """Cenário V2 do C5 SALVO: demanda no passo Δ (o motor não agrega), clima de 5 min (divide Δ), malha declarada."""
    sc0 = H.criar_cenario_pemfc(store, renov=True, horas=DURACAO // 60, clima=_clima, estados=[estado],
                                pemfc_kw={"preco": 10.0, "rampa": rampa, "t_on": 0.0, "t_off": 0.0, "abstracao": abstracao,
                                          "t_amb": t_amb})
    doc = copy.deepcopy(sc0.document)
    K = DURACAO // delta_min
    b = doc[E.CHAVE_BLOCO]
    b["malha"] = {"delta_min": delta_min, "N": N or max(2, 60 // delta_min), "m": 1, "H_L": H_L or K}
    b["pcc"].update(modo="isolado_declarado", sentidos="nenhum", ajuste="sem_ajuste",
                    justificativa="Operação ISOLADA declarada (C5 hipotético, teste)")
    for eid in b["baterias"]:
        b["baterias"][eid].update(p_carga_barramento_kW=75.0, p_descarga_barramento_kW=75.0)
    dem = list(demanda) if demanda is not None else [110.0 if i % 2 else 20.0 for i in range(K)]
    tab = FS.regular_table(("demand_kW",), U.INICIO_LOCAL, delta_min * 60, K, {"demand_kW": dem})
    cand = FS.manual_candidate(tab, "demand", timezone="UTC", inventory_ref=doc["inventory_ref"], provenance="sintetico")
    assert cand.ok, [f.message for f in cand.analysis.findings]
    doc["forecasts"]["demand"] = cand.entry
    return SV.save(store, doc, sc0.version, new_blobs=cand.blobs)


def _codigos(pf, nivel=PF.ERROR):
    return {i.code for i in pf.items if i.level == nivel}


def _msg(pf, code="pemfc_transitorio_incompativel") -> str:
    (m,) = [i.message for i in pf.items if i.code == code]
    return m


def _ok_dinamica(pf) -> str:
    (m,) = [i.message for i in pf.items if i.level == PF.OK and "restrições do modelo dinâmico compatíveis" in i.message]
    return m


# ====================================================================== 1. física e números (sem solver, sem catálogo)
def test_parametros_do_manual_lidos_do_modelo_e_tolerancias_inalteradas():
    par = DY.parametros_dinamicos(COND, T_AMB)
    assert (par["rampa_subida_kW_s"], par["rampa_descida_kW_s"], par["idle_kW"]) == (SUBIDA_KW_S, DESCIDA_KW_S, 10.0)
    assert (par["partida_s"], par["parada_s"], par["partida_fria"], par["rampa_max_kW_min"]) == (30.0, 60.0, False, 120.0)
    fria = DY.parametros_dinamicos(COND, 0.0)
    assert fria["partida_fria"] and fria["partida_s"] == 600.0
    assert {k: DY.TOLERANCIAS[k] for k in TOL} == TOL                  # P1 não toca tolerâncias


def test_oraculo_independente_reproduz_a_analise_a_priori_das_rampas():
    an, curva = _analise(), _curva()
    assert curva.p_max_kW == 50.0
    sobe, desce = an["rampas"]
    assert (sobe["de_kW"], sobe["para_kW"], desce["de_kW"], desce["para_kW"]) == (10.0, 50.0, 50.0, 10.0)
    dm_d, de_d = _oraculo_rampa(50.0, 10.0)
    dm_s, de_s = _oraculo_rampa(10.0, 50.0)
    assert desce["delta_m_kg"] == pytest.approx(dm_d, rel=1e-9) and desce["delta_E_kWh"] == pytest.approx(de_d, rel=1e-9)
    assert sobe["delta_m_kg"] == pytest.approx(dm_s, rel=1e-9) and sobe["delta_E_kWh"] == pytest.approx(de_s, rel=1e-9)
    # números do bloqueio dos ensaios A/B (4 algarismos significativos, como na mensagem)
    assert f"{dm_d:.4g}" == "0.004346" and f"{de_d:.4g}" == "0.05806"
    assert f"{dm_s:.4g}" == "-0.009151" and f"{de_s:.4g}" == "-0.1056"
    # a extremidade da PWL coincide com o modelo: o desvio é TODO do transitório, nada da linearização (B04)
    assert float(curva.q_pwl([10.0])[0]) == pytest.approx(float(_q([10.0])[0]), rel=1e-12)
    assert float(curva.q_pwl([50.0])[0]) == pytest.approx(float(_q([50.0])[0]), rel=1e-12)


def test_desvio_e_conservativo_fisicamente_e_nao_artefato_do_passo_interno():
    """O H₂ adicional da descida paga a energia adicional entregue (consumo específico entre os de regime nos extremos);
    o passo interno de 1 s SUBESTIMA o transitório contínuo — o bloqueio não é artefato numérico."""
    dm, de = _oraculo_rampa(50.0, 10.0)
    assert dm > 0 and de > 0
    q10, q50 = float(_q([10.0])[0]), float(_q([50.0])[0])
    assert q10 / 10.0 < dm / de < q50 / 50.0
    t = np.linspace(0.0, 40.0 / DESCIDA_KW_S, 201)
    continuo = float(np.trapezoid(_q(50.0 - DESCIDA_KW_S * t) - q10, t)) / 3600.0
    assert continuo > dm and continuo == pytest.approx(0.004785, abs=5e-6)


@pytest.mark.parametrize("delta_min, n", [(5, 4), (10, 1), (15, 0), (20, 0)])
def test_matriz_de_veredictos_rampas_por_delta_igual_ao_oraculo(delta_min, n):
    adm = DY.admissibilidade(_analise(), _curva(), delta_min * 60.0, BLOQ)
    assert {v["caso"] for v in adm} <= {"rampa"} and len(adm) == n
    assert {(f"{v['p_kW']:g}", v["grandeza"]) for v in adm} == _violacoes_esperadas(delta_min)
    for v in adm:                                                       # tolerância = fórmula declarada, recomputada aqui
        h = delta_min / 60.0
        if v["grandeza"] == "h2_kg":
            m_ems = float(_curva().q_pwl([v["p_kW"]])[0]) * h
            assert v["tolerancia"] == pytest.approx(max(TOL["h2_rel"] * m_ems, TOL["vazao_media_abs_kg_h"] * h), rel=1e-12)
        else:
            assert v["tolerancia"] == pytest.approx(
                max(TOL["energia_rel"] * v["p_kW"] * h, TOL["potencia_media_abs_kW"] * h), rel=1e-12)


def test_limiar_de_delta_do_criterio_dominante():
    """Descida P_máx → P_mín, H₂: 0,004346 kg ≤ 0,02 kg/h · Δ ⇔ Δ ≥ 13,04 min (q(10)·2 % < 0,02 kg/h)."""
    dm, _de = _oraculo_rampa(50.0, 10.0)
    assert dm / TOL["vazao_media_abs_kg_h"] * 60.0 == pytest.approx(13.04, abs=0.01)
    assert TOL["h2_rel"] * float(_q([10.0])[0]) < TOL["vazao_media_abs_kg_h"]


def test_transicoes_bloqueadas_nao_avaliam_partida_nem_parada():
    """Com transições bloqueadas, partida fria (600 s) ou quente (30 s) dá o MESMO veredito: só as rampas contam."""
    quente, fria = _analise(25.0), _analise(0.0)
    assert quente["rampas"] == fria["rampas"]
    for d in (5, 10, 15, 20, 60):
        a, b = DY.admissibilidade(quente, _curva(), d * 60.0, BLOQ), DY.admissibilidade(fria, _curva(), d * 60.0, BLOQ)
        assert a == b and {v["caso"] for v in a} <= {"rampa"}
    for d in (15, 20, 60):                                              # a abstração instantânea avalia a partida fria
        adm = DY.admissibilidade(fria, _curva(), d * 60.0, INST)
        assert {"partida"} <= {v["caso"] for v in adm}


@pytest.mark.parametrize("delta_min, admissivel", [(5, False), (10, False), (15, False), (20, False), (40, True),
                                                   (60, True)])
def test_instantanea_partida_quente_por_delta(delta_min, admissivel):
    adm = DY.admissibilidade(_analise(), _curva(), delta_min * 60.0, INST)
    assert (not adm) is admissivel
    if not admissivel:
        assert {"partida", "parada"} & {v["caso"] for v in adm}


def test_deltas_admissiveis_mesma_analise_e_regras_da_malha():
    an, curva = _analise(), _curva()
    assert PF.deltas_admissiveis_pemfc(an, curva, BLOQ, 120) == [15, 20, 24, 30, 40, 60]
    assert PF.deltas_admissiveis_pemfc(an, curva, INST, 120) == [40, 60]
    assert not DY.admissibilidade(an, curva, 120 * 60.0, BLOQ)          # admissível, mas K_M = 1 < 2 (H_L > N >= 1)
    for dur in (None, "x", 0, -60):
        assert PF.deltas_admissiveis_pemfc(an, curva, BLOQ, dur) == []
    bruto = [d for d in range(1, 121) if 120 % d == 0 and 120 // d >= 2
             and not DY.admissibilidade(an, curva, d * 60.0, BLOQ)]
    assert PF.deltas_admissiveis_pemfc(an, curva, BLOQ, 120) == bruto


# ====================================================================== 2. preflight real no catálogo (sem solver)
@pytest.mark.parametrize("delta_min, n, tol", [(5, 4, "0.001667"), (10, 1, "0.003333")])
def test_preflight_c5_bloqueia_com_diagnostico_contextual(tmp_path, delta_min, n, tol):
    _r, store = _loja(tmp_path)
    pf = PF.preparar(store, _c5(store, delta_min))
    assert "pemfc_transitorio_incompativel" in _codigos(pf) and not pf.ok
    assert _codigos(pf) <= {"pemfc_transitorio_incompativel", "solver_indisponivel"}
    assert any(i.level == PF.OK and "curva q(P) do modelo físico" in i.message for i in pf.items)   # B04 aprovado antes
    m = _msg(pf)
    assert "ADMISSIBILIDADE DINÂMICA a priori NÃO atendida" in m and "Não é o certificado B04" in m
    assert "a partida NÃO é avaliada" in m and "(10 ↔ 50 kW)" in m
    assert "partida quente de" not in m and "limiar de partida fria" not in m
    assert f"{n} violação(ões) a priori em rampa; pior caso rampa em P = 10 kW: desvio 0.004346 > tolerância {tol} " \
           "(h2_kg; razão" in m
    assert f"R·Δ = {120 * delta_min:g} kW ≥ 40 kW" in m and "ALCANÇÁVEL" in m
    assert "declarar Δ = 15, 20, 24, 30, 40 e 60 min" in m and "a unidade indisponível no cenário" in m
    assert "transições bloqueadas," not in m and "'transicoes_bloqueadas' (estado inicial" not in m    # já declaradas
    assert "C-3DA2H-12" in m


@pytest.mark.parametrize("delta_min", [15, 20])
def test_preflight_c5_admissivel_com_mensagem_de_rampas_e_conversao_da_rampa(tmp_path, delta_min):
    _r, store = _loja(tmp_path)
    pf = PF.preparar(store, _c5(store, delta_min))
    assert not ({"pemfc_transitorio_incompativel", "b04_reprovada", "b04_aguardando_aprovacao"} & _codigos(pf))
    assert _codigos(pf) <= {"solver_indisponivel"}, [i.message for i in pf.items if i.level == PF.ERROR]
    m = _ok_dinamica(pf)
    assert f"admissibilidade DINÂMICA a priori atendida em Δ = {delta_min:g} min" in m
    assert "não há partida nem parada" in m and "pior déficit de energia numa partida" not in m
    reg = next(iter(pf.montagem.doc_pemfc["registros"].values()))
    assert reg["admissibilidade"]["violacoes"] == [] and reg["admissibilidade"]["abstracao"] == BLOQ
    # rampa 120 kW/min → R·Δ por intervalo no MILP 3C-1 (subida E descida); estado inicial ligado a 30 kW
    (dz,) = discretizar(pf.montagem.modelo.compromisso).values()
    assert dz.rampa_subida_kW == dz.rampa_descida_kW == 120.0 * delta_min
    assert dz.abstracao == BLOQ and dz.u_anterior == 1 and dz.p_anterior_kW == 30.0


def test_mensagem_da_abstracao_instantanea_cita_partida_e_alternativas(tmp_path):
    _r, store = _loja(tmp_path)
    m = _msg(PF.preparar(store, _c5(store, 15, abstracao=INST, estado=DESLIGADA)))
    assert "Com 'instantanea_unidade_quente' são avaliadas a partida (quente de 30 s), a parada (60 s)" in m
    assert "Não é o certificado B04" in m and "declarar Δ = 40 e 60 min" in m
    assert "'transicoes_bloqueadas' (estado inicial mantido em toda a missão), admissível em Δ = 15, 20, 24, 30, 40 e 60 " \
           "min" in m
    assert "limiar de partida fria" not in m                            # partida quente: alternativa irrelevante omitida


def test_partida_fria_continua_bloqueando_a_instantanea_e_sugere_so_condicao_real(tmp_path):
    _r, store = _loja(tmp_path)
    pf = PF.preparar(store, _c5(store, 20, abstracao=INST, estado=DESLIGADA, t_amb=0.0))
    assert "pemfc_transitorio_incompativel" in _codigos(pf)
    m = _msg(pf)
    assert "FRIA de 600 s" in m and "somente se for a condição real do ensaio" in m
    assert "nenhum Δ que divida a missão (120 min) é admissível com esta abstração" in m


def test_rampa_declarada_menor_registra_conservadorismo_sem_mudar_o_veredito(tmp_path):
    """P2 NÃO implementada: com R·Δ < P_máx − P_mín o degrau inteiro não é alcançável, mas o veredito é o mesmo."""
    _r, store = _loja(tmp_path)
    pf = PF.preparar(store, _c5(store, 5, rampa=4.0))
    m = _msg(pf)
    assert "4 violação(ões) a priori em rampa" in m and "desvio 0.004346 > tolerância 0.001667" in m
    assert "R·Δ = 20 kW < 40 kW" in m and "CONSERVADORA" in m and "P2 de B04-C5-01" in m and "ALCANÇÁVEL" not in m


def test_unidade_inicialmente_desligada_com_transicoes_bloqueadas(tmp_path):
    _r, store = _loja(tmp_path)
    pf = PF.preparar(store, _c5(store, 10, estado=DESLIGADA, demanda=[30.0] * 12))
    m = _msg(pf)                                                         # mesmo veredito (independe do estado inicial)
    assert "1 violação(ões) a priori em rampa" in m and "Todas as unidades começam DESLIGADAS" in m
    assert "CONSERVADORA" in m and "ALCANÇÁVEL" not in m
    pf = PF.preparar(store, _c5(store, 15, estado=DESLIGADA, demanda=[30.0] * 8))
    assert "pemfc_transitorio_incompativel" not in _codigos(pf)
    (dz,) = discretizar(pf.montagem.modelo.compromisso).values()
    assert dz.u_anterior == 0 and dz.p_anterior_kW == 0.0 and dz.abstracao == BLOQ


def test_execucao_recusada_nos_deltas_inadmissiveis_sem_criar_rodada(tmp_path):
    _r, store = _loja(tmp_path)
    for d in (5, 10):
        sc = _c5(store, d)
        with pytest.raises(X.PreflightV2Error):
            X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    assert store.list_runs() == []


# ====================================================================== 3. execução real (HiGHS): a priori × a posteriori
def _ints(store, run) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(store.run_data(run.run_uid, RG.N_INTERVALOS)), float_precision="round_trip")


@pytest.fixture(scope="module", params=[15, 20])
def missao_ligada(request, tmp_path_factory):
    if not SOLVER:
        pytest.skip("Pyomo/HiGHS não instalados")
    _r, store = _loja(tmp_path_factory.mktemp(f"c5_{request.param}"))
    sc = _c5(store, request.param)
    return request.param, store, X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)


@requer_solver
def test_c5_ligada_conclui_coerente_com_conservacao_e_h2_exatos(missao_ligada):
    delta_min, store, run = missao_ligada
    h = delta_min / 60.0
    assert run.state == "concluida", (run.error, (run.outcome or {}).get("mission"))
    assert run.summary["execution"]["aceitacao"]["classificacao"] == "algebrica_aprovada_dinamica_coerente"
    assert RG.verificar(store, run).ok
    df = _ints(store, run)
    doc = RG.ler_json(store, run, RG.N_PEMFC)
    (eid, x), = doc["registros"].items()
    u, p = df[f"{eid}|u"], df[f"{eid}|p_kW"]
    # transições bloqueadas: ligada em toda a missão, sem eventos; potência no domínio declarado
    assert (u == 1).all() and (df[f"{eid}|partida"] == 0).all() and (df[f"{eid}|parada"] == 0).all()
    assert ((p >= P_MIN - 1e-6) & (p <= 50.0 + 1e-6)).all()
    dp = np.diff(np.concatenate([[30.0], p.to_numpy()]))
    assert dp.max() > 15.0 and dp.min() < -15.0                         # rampas de subida E descida exercitadas
    assert np.abs(dp).max() <= 120.0 * delta_min                        # M11 (inativa: R·Δ ≫ domínio)
    # conservação de energia por intervalo (barramento isolado: FV + bateria + PEMFC = demanda)
    bat = [c[:-len("|P_d_kW")] for c in df.columns if c.endswith("|P_d_kW")]
    fv = [c for c in df.columns if c.endswith("|P_R_kW")]
    oferta = p + sum(df[f"{b}|P_d_kW"] - df[f"{b}|P_c_kW"] for b in bat) + sum(df[c] for c in fv)
    assert np.allclose(oferta, df["demanda_atendida_kW"], atol=1e-6) and (df["demanda_nao_atendida_kW"] == 0).all()
    assert df["residuo_balanco_kW"].abs().max() < 1e-6
    # H₂ do EMS = q̂(p)·Δ exatamente (PWL certificada; sem termo de evento); custo = R$ 10/kg
    v = np.array(x["curva"]["vertices_kW_kg_h"])
    m_esp = np.interp(p, v[:, 0], v[:, 1]) * h
    assert np.allclose(df[f"{eid}|m_h2_kg"], m_esp, rtol=1e-12, atol=1e-12)
    assert np.allclose(df[f"{eid}|custo_h2_R"], 10.0 * m_esp, rtol=1e-12, atol=1e-12)
    r = run.summary["mission"]["pemfc"][eid]
    assert r["massa_h2_kg"] == pytest.approx(float(m_esp.sum())) and r["partidas"] == r["paradas"] == 0


@requer_solver
def test_c5_ligada_verificacao_dinamica_dentro_das_tolerancias_e_da_cota_a_priori(missao_ligada):
    delta_min, store, run = missao_ligada
    h = delta_min / 60.0
    din = RG.ler_json(store, run, RG.N_PEMFC_DIN)
    (_u, v), = din["unidades"].items()
    assert v["coerente"] is True and v["pre_condicionamento_s"] == DY.PRE_CONDICIONAMENTO_S
    for x in v["intervalos"]:
        assert not ({"STARTUP", "SHUTDOWN", "OFF"} & set(x["estados"]))   # começa e permanece em RUN/IDLE (ligada a 30 kW)
        te = max(TOL["energia_rel"] * x["energia_solicitada_kWh"], TOL["potencia_media_abs_kW"] * h)
        tm = max(TOL["h2_rel"] * x["h2_ems_kg"], TOL["vazao_media_abs_kg_h"] * h)
        assert abs(x["energia_entregue_kWh"] - x["energia_solicitada_kWh"]) <= te
        assert abs(x["h2_modelo_dinamico_kg"] - x["h2_ems_kg"]) <= tm
    pior = _analise()["rampas"][1]["delta_m_kg"]                         # P_máx → P_mín (pior caso a priori)
    assert 0.0 < v["h2_subestimacao_max_kg"] <= pior + 1e-9            # resíduo das descidas reportado e limitado
    assert v["h2_subestimacao_max_kg"] <= TOL["vazao_media_abs_kg_h"] * h


@requer_solver
def test_c5_desligada_com_transicoes_bloqueadas_permanece_desligada(tmp_path):
    _r, store = _loja(tmp_path)
    sc = _c5(store, 15, estado=DESLIGADA, demanda=[30.0] * 8)
    run = X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    assert run.state == "concluida", (run.error, (run.outcome or {}).get("mission"))
    df = _ints(store, run)
    (eid,) = RG.ler_json(store, run, RG.N_PEMFC)["registros"]
    assert (df[f"{eid}|u"] == 0).all() and (df[f"{eid}|p_kW"] == 0).all() and (df[f"{eid}|m_h2_kg"] == 0).all()
    (_u, v), = RG.ler_json(store, run, RG.N_PEMFC_DIN)["unidades"].items()
    assert v["coerente"] is True and v["h2_modelo_dinamico_kg"] == 0.0 and v["energia_entregue_kWh"] == 0.0


@requer_solver
def test_transicoes_permitidas_partida_quente_no_delta_admissivel(tmp_path):
    """Abstração instantânea com a unidade DESLIGADA em Δ = 40 min (admissível a priori): partida aplicada, STARTUP no
    modelo dinâmico, contabilidade q̂·Δ + m_SU·y + m_SD·z exata e coerência a posteriori."""
    _r, store = _loja(tmp_path)
    sc = _c5(store, 40, abstracao=INST, estado=DESLIGADA, demanda=[20.0, 110.0, 20.0], N=2, H_L=3)
    run = X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    assert run.state == "concluida", (run.error, (run.outcome or {}).get("mission"))
    df = _ints(store, run)
    doc = RG.ler_json(store, run, RG.N_PEMFC)
    (eid, x), = doc["registros"].items()
    assert df[f"{eid}|partida"].sum() >= 1 and df[f"{eid}|u"].iloc[1] == 1
    v = np.array(x["curva"]["vertices_kW_kg_h"])
    u, p = df[f"{eid}|u"], df[f"{eid}|p_kW"]
    me = x["massas_eventos"]
    m_esp = np.where(u == 1, np.interp(p, v[:, 0], v[:, 1]), 0.0) * (40 / 60) + me["m_partida_kg"] * df[f"{eid}|partida"] \
        + me["m_parada_kg"] * df[f"{eid}|parada"]
    assert np.allclose(df[f"{eid}|m_h2_kg"], m_esp, rtol=1e-12, atol=1e-12)
    (_u, vd), = RG.ler_json(store, run, RG.N_PEMFC_DIN)["unidades"].items()
    assert vd["coerente"] is True
    assert any("STARTUP" in it["estados"] and it["evento"] == "partida" for it in vd["intervalos"])
    assert run.summary["execution"]["aceitacao"]["classificacao"] == "algebrica_aprovada_dinamica_coerente"
