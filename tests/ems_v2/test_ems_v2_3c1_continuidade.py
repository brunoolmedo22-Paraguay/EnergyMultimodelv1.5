"""Piso 3C-1 — memória e continuidade entre janelas (Caso J) pela ponte 3C-0: plano → execução → checkpoint →
estado → entrada da janela seguinte. Sem MPC (nenhuma reotimização recedente): só o TRANSPORTE de estados é provado.

O executor é o dublê ALGÉBRICO 3C-1 (não é modelo físico). Sintético/algébrico.
"""
from __future__ import annotations

import dataclasses

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

from ems_v2 import fixtures_3c1 as Y  # noqa: E402
from ems_v2.audit import CandidatoDespacho  # noqa: E402
from ems_v2.compromisso.auditor import auditar_3c1  # noqa: E402
from ems_v2.diagnostics import ContratoInvalido  # noqa: E402
from ems_v2.fixtures import proc  # noqa: E402
from ems_v2.milp.config import CONFIG_ANALITICA as C  # noqa: E402
from ems_v2.milp.solver_3c1 import resolver_3c1  # noqa: E402
from ems_v2.ponte.cenario import Realizacao, SerieRecurso  # noqa: E402
from ems_v2.ponte.compromisso import (ExecutorAlgebricoCommitment3C1, custo_eventos_realizado,  # noqa: E402
                                      entrada_de_continuacao, estado_inicial_3c1, memorias_do_estado,
                                      plano_de_resultado_3c1)
from ems_v2.ponte.execucao import (estado_inicial_de_entrada, executar, retomar, verificar_checkpoint)  # noqa: E402
from ems_v2.ponte.registro import CustoRealizado, ComponenteCusto  # noqa: E402
from ems_v2.series import SerieTemporal  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
L = [5, 25, 30, 35, 10, 5, 30, 30]
INICIO = "2026-01-01T00:00:00+00:00"


def realizacao(L_=L):
    s = SerieTemporal("potencia", "kW", "media_intervalo", INICIO, 900, tuple(float(x) for x in L_), proc("3C1-J-real"),
                      fronteira="barramento_liquido")
    return Realizacao("syn-real-3c1", "sintetica", (SerieRecurso("syn-carga", "potencia", s),), proc("3C1-J-real"))


def _plano_continuo():
    e = Y.caso_j()
    r = resolver_3c1(e, C)
    assert r.aceito, r.codigos()
    p, pc = plano_de_resultado_3c1(r, e)
    return e, r, p, pc, estado_inicial_3c1(e)


def test_caso_j_execucao_continua_igual_a_dividida_por_checkpoint():
    e, r, p, pc, est0 = _plano_continuo()
    ex = ExecutorAlgebricoCommitment3C1(e)
    cont = executar(p, est0, ex, realizacao(), execucao_uid="exec-j")
    assert cont.situacao == "concluida" and len(cont.passos) == 8
    a = executar(p, est0, ex, realizacao(), execucao_uid="exec-j", intervalos=4)
    cp = a.checkpoints[-1]
    assert not verificar_checkpoint(cp) and cp.estado.gerador("syn-ter").tempo_no_estado_s is not None
    b = retomar(cp, p, ExecutorAlgebricoCommitment3C1(e), realizacao())
    assert a.estados + b.estados[1:] == cont.estados
    assert b.checkpoints[-1].hash_aplicado == cont.checkpoints[-1].hash_aplicado
    # memória ao fim = memória planejada (plano ↔ execução coerentes)
    mf = memorias_do_estado(e, cont.estados[-1])[0]
    mp = pc.memorias_terminais[0]
    assert (mf.ligado, mf.tempo_no_estado_s, mf.obrigacao_residual_s) == (mp.ligado, mp.tempo_no_estado_s,
                                                                          mp.obrigacao_residual_s)


def _cand_fatia(r, a, b, N):
    d = r.despacho
    g = {k: {kk: tuple(v[a:b]) for kk, v in x.items() if kk in ("u", "p", "y", "z")} for k, x in d["geradores"].items()}
    bat = {k: {"P_c": tuple(x["P_c"][a:b]), "P_d": tuple(x["P_d"][a:b]), "e": tuple(x["e"][a:b + 1])}
           for k, x in d["baterias"].items()}
    return CandidatoDespacho(demandas={"syn-carga": {"ell": (0.0,) * N}}, geradores=g, baterias=bat)


def test_caso_j_memoria_transportada_admite_exatamente_a_continuacao_do_plano_continuo():
    e, r, p, pc, est0 = _plano_continuo()
    traj = executar(p, est0, ExecutorAlgebricoCommitment3C1(e), realizacao(), execucao_uid="exec-j2", intervalos=4)
    est4 = traj.estados[-1]
    e2 = entrada_de_continuacao(Y.caso_j(N=4, inicio_indice=4), est4, procedencia=proc("3C1-J-transporte"))
    assert e2.base.estados_geradores[0].ligado == est4.gerador("syn-ter").ligado
    assert e2.memorias[0].tempo_no_estado_s == est4.gerador("syn-ter").tempo_no_estado_s
    # 1) a continuação do plano contínuo (intervalos 4..7) é aceita pelo auditor da 2ª janela
    cand = _cand_fatia(r, 4, 8, 4)
    rel = auditar_3c1(e2, cand)
    assert rel.aceito, (rel.familias_reprovadas(), rel.codigos())
    # 2) a 2ª janela resolvida com o mesmo programa u fixado é factível e auditada
    u = tuple(int(round(x)) for x in r.despacho["geradores"]["syn-ter"]["u"][4:8])
    r2 = resolver_3c1(e2, C, {"syn-ter": u})
    assert r2.aceito and [round(x) for x in r2.despacho["geradores"]["syn-ter"]["u"]] == list(u)


def test_caso_j_borda_residual_vinculante_obriga_a_janela_seguinte():
    """Partida no último intervalo da janela 1 (política residual) ⇒ a janela 2 herda u = 1 em t = 0, 1."""
    e1 = Y.caso_f("obrigacao_residual_vinculante")
    r1 = resolver_3c1(e1, C)
    p1, pc1 = plano_de_resultado_3c1(r1, e1)
    assert pc1.garantia_permanencia == "residual_vinculante" and pc1.obrigacoes_residuais_s == {"syn-ter": 1800}
    real = Realizacao("syn-real-f", "sintetica", (SerieRecurso("syn-carga", "potencia", SerieTemporal(
        "potencia", "kW", "media_intervalo", INICIO, 900, (0.0, 0.0, 0.0, 30.0), proc("3C1-F-real"),
        fronteira="barramento_liquido")),), proc("3C1-F-real"))
    traj = executar(p1, estado_inicial_3c1(e1), ExecutorAlgebricoCommitment3C1(e1), real,
                    execucao_uid="exec-f")
    est4 = traj.estados[-1]
    assert memorias_do_estado(e1, est4)[0].obrigacao_residual_s == 1800
    # janela 2: demanda nula (desligar seria o ótimo SEM a memória) — a obrigação herdada força u = 1 em t = 0, 1
    j2 = Y.caso_j(N=4, inicio_indice=4, L=[0] * 8, e0=50.0)
    j2 = dataclasses.replace(j2, unidades=(dataclasses.replace(j2.unidades[0], tempo_min_ligado_min=Y.par(45.0, "min", "x"),
                                                                rampa_subida_kW_min=Y.par(100.0, "kW/min", "x"),
                                                                rampa_descida_kW_min=Y.par(100.0, "kW/min", "x")),))
    e2 = entrada_de_continuacao(j2, est4, procedencia=proc("3C1-F-transporte"))
    assert e2.memorias[0].obrigacao_residual_s == 1800
    r2 = resolver_3c1(e2, C)
    assert r2.aceito and [round(x) for x in r2.despacho["geradores"]["syn-ter"]["u"]][:2] == [1, 1]
    # e um candidato que desliga em t = 0 é rejeitado pelo auditor da janela 2 (obrigação herdada)
    viol = CandidatoDespacho(demandas={"syn-carga": {"ell": (0.0,) * 4}},
                             geradores={"syn-ter": {"u": (0.0,) * 4, "p": (0.0,) * 4, "y": (0.0,) * 4,
                                                    "z": (1.0, 0.0, 0.0, 0.0)}},
                             baterias={"syn-bess": {"P_c": (0.0,) * 4, "P_d": (0.0,) * 4, "e": (50.0,) * 5}})
    assert "obrigacao_herdada_M12" in auditar_3c1(e2, viol).familias_reprovadas()


def test_executor_recusa_transicao_contra_a_memoria_e_memoria_ausente():
    e = Y.caso_d()                                   # D = 3 (T_off 45 min)
    r = resolver_3c1(Y.caso_d(0.0), C)               # plano que religa após 2 intervalos OFF (válido só sem T_off)
    p, _ = plano_de_resultado_3c1(r, Y.caso_d(0.0))
    real = Realizacao("syn-real-d", "sintetica", (SerieRecurso("syn-carga", "potencia", SerieTemporal(
        "potencia", "kW", "media_intervalo", INICIO, 900, (10.0, 0.0, 0.0, 20.0), proc("3C1-D-real"),
        fronteira="barramento_liquido")),), proc("3C1-D-real"))
    est0 = estado_inicial_de_entrada(e.base, memoria={"syn-ter": 7200})
    t = executar(p, est0, ExecutorAlgebricoCommitment3C1(e), real, execucao_uid="exec-d")
    assert t.situacao == "interrompida_inexequivel" and len(t.passos) == 3
    assert "permanencia_minima_violada" in {c.codigo for c in t.constatacoes}
    est_sem = estado_inicial_de_entrada(e.base, memoria={})        # memória não declarada
    t = executar(p, est_sem, ExecutorAlgebricoCommitment3C1(e), real, execucao_uid="exec-d2")
    assert t.situacao == "erro_dados" and "memoria_ausente" in {c.codigo for c in t.constatacoes}


def test_custo_de_eventos_realizado_separado_do_planejado():
    e, r, p, pc, est0 = _plano_continuo()
    traj = executar(p, est0, ExecutorAlgebricoCommitment3C1(e), realizacao(), execucao_uid="exec-j3")
    c = custo_eventos_realizado(e, traj)
    assert c.base == "realizado" and c.valor_R == pytest.approx(pc.custo_eventos_planejado_R)
    parcial = executar(p, est0, ExecutorAlgebricoCommitment3C1(e), realizacao(), execucao_uid="exec-j4", intervalos=0)
    assert custo_eventos_realizado(e, parcial).valor_R == 0.0         # nada aplicado ⇒ nada incorrido
    cr = CustoRealizado((c, ComponenteCusto("throughput_bess", 0.1, "realizado")), c.valor_R + 0.1, 8)
    assert cr.total_R == pytest.approx(c.valor_R + 0.1)
    e_sem = dataclasses.replace(e, termos_adicionais=(), unidades=(dataclasses.replace(
        e.unidades[0], custo_partida=None, custo_parada=None),))
    assert custo_eventos_realizado(e_sem, traj) is None


def test_continuacao_recusa_estado_dessincronizado_ou_de_outra_microrrede():
    e, r, p, pc, est0 = _plano_continuo()
    with pytest.raises(ContratoInvalido):
        entrada_de_continuacao(Y.caso_j(N=4, inicio_indice=4), est0, procedencia=proc("x"))   # τ_0 ≠ τ_4
    est_x = dataclasses.replace(est0, microrrede_uid="syn-outra", instante_utc="2026-01-01T01:00:00+00:00")
    with pytest.raises(ContratoInvalido):
        entrada_de_continuacao(Y.caso_j(N=4, inicio_indice=4), est_x, procedencia=proc("x"))


def test_plano_3c1_e_recusado_com_a_entrada_base():
    from ems_v2.ponte.execucao import plano_de_resultado
    e, r, p, pc, est0 = _plano_continuo()
    with pytest.raises(ContratoInvalido):
        plano_de_resultado(r, e.base)            # hash da base ≠ hash da entrada 3C-1
    assert p.hash_entrada == r.hash_entrada and pc.hash_plano
