"""Piso 3C-1 — auditor INDEPENDENTE do commitment (sem Pyomo/HiGHS): candidatas analíticas e adulterações (Caso K).

As candidatas são escritas À MÃO a partir das soluções analíticas das docstrings de ``fixtures_3c1`` (não vêm do
solver). Cada adulteração viola exatamente uma família e deve ser rejeitada.
"""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from ems_v2 import fixtures_3c1 as Y
from ems_v2.audit import CandidatoDespacho, Tolerancias
from ems_v2.compromisso.auditor import _discretizacao_independente, auditar_3c1
from ems_v2.compromisso.contrato import discretizar

pytestmark = pytest.mark.synthetic_algebraic
RAIZ = Path(__file__).resolve().parents[2]


def cand_ger(N, ger, *, dem=None, bat=None, custos=None):
    return CandidatoDespacho(demandas={"syn-carga": {"ell": tuple([0.0] * N)}} if dem is None else dem,
                             geradores={k: {kk: tuple(float(x) for x in v) for kk, v in d.items()} for k, d in ger.items()},
                             baterias=bat or {}, custos_reportados=custos or {})


def cand_a(**mud):
    g = dict(u=[0, 1, 1, 0], p=[0, 30, 30, 0], y=[0, 1, 0, 0], z=[0, 0, 0, 1])
    g.update(mud)
    return cand_ger(4, {"syn-ter": g}, custos={"eventos": 7.0, "total": 7.0})


def bat(pc, pd, e0, h=0.25):
    e = [e0]
    for a, b in zip(pc, pd):
        e.append(e[-1] + h * (a - b))
    return {"syn-bess": {"P_c": tuple(map(float, pc)), "P_d": tuple(map(float, pd)), "e": tuple(e)}}


def test_caso_a_analitico_aceito_e_custos_sem_h():
    r = auditar_3c1(Y.caso_a(), cand_a())
    assert r.aceito, (r.familias_reprovadas(), r.codigos())
    assert r.custos_reconstruidos["eventos"] == 7.0 and r.custos_reconstruidos["total"] == 7.0
    assert {"transicao_M09", "eventos_simultaneos", "rampa_M11a", "rampa_M11b", "integralidade",
            "permanencia_corridas", "balanco"} <= set(r.familias_verificadas)
    assert "multimodo_M20" in r.familias_nao_modeladas


@pytest.mark.parametrize("mud,familia", [
    (dict(y=[0, 0, 0, 0]), "transicao_M09"),                          # partida apagada
    (dict(y=[1, 1, 0, 0], z=[1, 0, 0, 1]), "eventos_simultaneos"),    # evento fictício duplo em t = 0
    (dict(z=[0, 0, 1, 1], u=[0, 1, 1, 0]), "transicao_M09"),          # parada fictícia
    (dict(u=[0, 1, 0.5, 0]), "integralidade"),
    (dict(u=[0, 1, 1, 1], p=[0, 30, 30, 0], z=[0, 0, 0, 0]), "dominio_on_off"),   # ON com p = 0 < P_min
])
def test_caso_k_adulteracoes_de_estado_e_evento(mud, familia):
    r = auditar_3c1(Y.caso_a(), cand_a(**mud))
    assert not r.aceito and familia in r.familias_reprovadas(), (r.familias_reprovadas(), r.codigos())


def test_caso_k_evento_ficticio_explicito():
    # y = z = 1 no mesmo intervalo sem transição real: M09 fecha (1 − 1 = 0), mas o auditor acusa
    r = auditar_3c1(Y.caso_a(), cand_a(y=[1, 1, 0, 0], z=[1, 0, 0, 1]))
    assert "evento_ficticio" in r.codigos() and "evento_ficticio" in r.familias_reprovadas()


def test_caso_k_custo_de_evento_adulterado():
    r = auditar_3c1(Y.caso_a(), dataclasses.replace(cand_a(), custos_reportados={"eventos": 7.0 * 0.25, "total": 1.75}))
    assert not r.aceito and "custo" in r.familias_reprovadas()          # custo multiplicado por h é rejeitado


def test_caso_k_rampa_violada():
    e = Y.caso_b()
    pd = [15, 10, 5, 0]
    ok = cand_ger(4, {"syn-ter": dict(u=[1] * 4, p=[15, 20, 25, 30], y=[0] * 4, z=[0] * 4)}, bat=bat([0] * 4, pd, 50.0, 5 / 60),
                  custos={"throughput_bess": 2.5, "total": 2.5})
    r = auditar_3c1(e, ok)
    assert r.aceito, (r.familias_reprovadas(), r.codigos())
    salto = cand_ger(4, {"syn-ter": dict(u=[1] * 4, p=[30, 30, 30, 30], y=[0] * 4, z=[0] * 4)},
                     bat=bat([0] * 4, [0] * 4, 50.0, 5 / 60))
    r = auditar_3c1(e, salto)
    assert not r.aceito and "rampa_M11a" in r.familias_reprovadas()     # 10 → 30 kW com RΔ = 5 kW (inclusive t = 0)
    desc = cand_ger(4, {"syn-ter": dict(u=[1] * 4, p=[15, 20, 25, 10], y=[0] * 4, z=[0] * 4)},
                    bat=bat([0] * 4, [15, 10, 5, 20], 50.0, 5 / 60))
    assert "rampa_M11b" in auditar_3c1(e, desc).familias_reprovadas()


def test_caso_k_transicao_nao_representavel():
    e = Y.caso_b()                                    # S⁺ = S⁻ = 5 kW < P_min = 10 kW
    c = cand_ger(4, {"syn-ter": dict(u=[0, 0, 0, 0], p=[0] * 4, y=[0] * 4, z=[1, 0, 0, 0])},
                 bat=bat([0] * 4, [30] * 4, 50.0, 5 / 60))
    r = auditar_3c1(e, c)
    assert not r.aceito and "transicao_nao_representavel" in r.familias_reprovadas()


def test_caso_k_permanencia_ON_violada_nas_duas_formas():
    e = Y.caso_c()                                    # U = 3
    ok = cand_ger(4, {"syn-ter": dict(u=[1, 1, 1, 0], p=[20, 10, 10, 0], y=[1, 0, 0, 0], z=[0, 0, 0, 1])},
                  bat=bat([0, 10, 10, 0], [0] * 4, 0.0), custos={"throughput_bess": 5.0, "total": 5.0})
    assert auditar_3c1(e, ok).aceito
    viol = cand_ger(4, {"syn-ter": dict(u=[1, 0, 0, 0], p=[20, 0, 0, 0], y=[1, 0, 0, 0], z=[0, 1, 0, 0])},
                    bat=bat([0] * 4, [0] * 4, 0.0))
    r = auditar_3c1(e, viol)
    assert not r.aceito and {"permanencia_M12", "permanencia_corridas"} <= r.familias_reprovadas()


def test_caso_k_permanencia_OFF_violada():
    e = Y.caso_d()                                    # D = 3; desligar em t = 1 e religar em t = 3 é proibido
    viol = cand_ger(4, {"syn-ter": dict(u=[1, 0, 0, 1], p=[10, 0, 0, 20], y=[0, 0, 0, 1], z=[0, 1, 0, 0])},
                    bat=bat([0] * 4, [0] * 4, 50.0))
    r = auditar_3c1(e, viol)
    assert not r.aceito and {"permanencia_M12", "permanencia_corridas"} <= r.familias_reprovadas()
    ok = cand_ger(4, {"syn-ter": dict(u=[0, 0, 0, 1], p=[0, 0, 0, 20], y=[0, 0, 0, 1], z=[1, 0, 0, 0])},
                  bat=bat([0] * 4, [10, 0, 0, 0], 50.0), custos={"throughput_bess": 2.5, "eventos": 1.0, "total": 3.5})
    assert auditar_3c1(e, ok).aceito


def test_caso_k_obrigacao_herdada_violada_desde_t0():
    e = Y.caso_e()                                    # OFF obrigado em t = 0, 1
    viol = cand_ger(4, {"syn-ter": dict(u=[0, 1, 1, 1], p=[0, 20, 20, 20], y=[0, 1, 0, 0], z=[0] * 4)},
                    bat=bat([0] * 4, [20, 0, 0, 0], 50.0))
    r = auditar_3c1(e, viol)
    assert not r.aceito and {"obrigacao_herdada_M12", "permanencia_corridas"} <= r.familias_reprovadas()


def test_caso_k_politica_terminal_e_residual():
    c3 = cand_ger(4, {"syn-ter": dict(u=[0, 0, 0, 1], p=[0, 0, 0, 30], y=[0, 0, 0, 1], z=[0] * 4)},
                  bat=bat([0] * 4, [0] * 4, 50.0))
    r = auditar_3c1(Y.caso_f("cumprir_na_janela"), c3)
    assert not r.aceito and "politica_terminal_M12" in r.familias_reprovadas()
    r = auditar_3c1(Y.caso_f("obrigacao_residual_vinculante"), c3)
    assert r.aceito and r.kpis_reconstruidos["obrigacao_residual_intervalos"] == {"syn-ter": 2.0}


def test_caso_k_compromisso_parcial_e_indisponibilidade():
    e = Y.caso_a()
    r = auditar_3c1(e, cand_a(), compromisso_parcial={"syn-ter": (0, 1, 1, 1)})
    assert not r.aceito and "compromisso_parcial" in r.familias_reprovadas()
    g = dataclasses.replace(e.base.geradores[0], disponibilidade=Y.disp([1, 1, 0, 1], 15, "x"))
    r = auditar_3c1(dataclasses.replace(e, base=dataclasses.replace(e.base, geradores=(g,))), cand_a())
    assert not r.aceito and "disponibilidade_commitment" in r.familias_reprovadas() and "on_indisponivel" in r.codigos()


def test_caso_k_unidades_independentes():
    e = Y.caso_g()
    base = {"syn-ter#1": dict(u=[1] * 4, p=[20, 20, 15, 15], y=[0] * 4, z=[0] * 4),
            "syn-ter#2": dict(u=[0, 0, 1, 1], p=[0, 0, 30, 30], y=[0, 0, 1, 0], z=[0] * 4)}
    assert auditar_3c1(e, cand_ger(4, base, custos={"eventos": 1.0, "total": 1.0})).aceito
    troca = dict(base)                                 # #2 parte em t = 1 (obrigação OFF dela) com #1 cobrindo t = 2
    troca["syn-ter#2"] = dict(u=[0, 1, 1, 1], p=[0, 10, 30, 30], y=[0, 1, 0, 0], z=[0] * 4)
    troca["syn-ter#1"] = dict(u=[1] * 4, p=[20, 10, 15, 15], y=[0] * 4, z=[0] * 4)
    r = auditar_3c1(e, cand_ger(4, troca))
    assert not r.aceito and "obrigacao_herdada_M12" in r.familias_reprovadas()


def test_candidata_sem_y_z_ou_com_uid_estranho_rejeitada():
    c = cand_a()
    sem = dataclasses.replace(c, geradores={"syn-ter": {k: v for k, v in c.geradores["syn-ter"].items() if k != "y"}})
    assert "variavel_candidata_ausente" in auditar_3c1(Y.caso_a(), sem).codigos()
    extra = dataclasses.replace(c, geradores={**c.geradores, "syn-x": c.geradores["syn-ter"]})
    assert "uid_desconhecido_na_candidata" in auditar_3c1(Y.caso_a(), extra).codigos()
    assert not auditar_3c1(Y.caso_a(), c, Tolerancias(binario=-1.0)).aceito


@pytest.mark.parametrize("fx", ["caso_a", "caso_b", "caso_c", "caso_d", "caso_e", "caso_f", "caso_g", "caso_h",
                                "caso_j", "pemfc_instantanea"])
def test_discretizacao_do_auditor_independente_coincide_com_a_do_contrato(fx):
    e = getattr(Y, fx)()
    a, c = _discretizacao_independente(e), discretizar(e)
    for k, d in c.items():
        assert (a[k]["U"], a[k]["D"]) == (d.U or 0, d.D or 0), k
        assert a[k]["r"] == d.intervalos_forcados or a[k]["r"] >= e.base.malha.N, k
        assert (a[k]["rep_p"], a[k]["rep_z"]) == (d.partida_representavel, d.parada_representavel), k
        assert a[k]["rs"] == d.rampa_subida_kW and a[k]["Sp"] == d.limite_partida_kW, k


def test_auditor_3c1_sem_pyomo_sem_reference_sem_discretizar():
    arv = ast.parse((RAIZ / "ems_v2/compromisso/auditor.py").read_text(encoding="utf-8"))
    nomes = {n.module or "" for n in ast.walk(arv) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(arv) if isinstance(n, ast.Import) for a in n.names}
    assert not any(x.startswith(("pyomo", "highspy")) or "milp" in x or "reference" in x for x in nomes), nomes
    usados = {n.id for n in ast.walk(arv) if isinstance(n, ast.Name)} | {
        a.name for n in ast.walk(arv) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "discretizar" not in usados
