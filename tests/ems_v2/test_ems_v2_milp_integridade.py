"""Piso 3B-P — integridade do resultado: terminações (reais e simuladas no adaptador), ausência de solução,
estados desconhecidos, bloqueios por parâmetros ausentes, adulteração pós-resolução e reprodutibilidade."""
import dataclasses

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

import pyomo.environ as pe  # noqa: E402

from ems_v2 import fixtures_3b as X  # noqa: E402
from ems_v2 import fixtures as F  # noqa: E402
from ems_v2.contracts import hash_entrada, json_canonico  # noqa: E402
from ems_v2.milp import solver as S  # noqa: E402
from ems_v2.milp.config import CONFIG_ANALITICA as CFG  # noqa: E402
from ems_v2.milp.config import ConfiguracaoSolver  # noqa: E402
from ems_v2.milp.resultado import CLASSIFICACOES, classificar, gaps  # noqa: E402
from ems_v2.milp.solver import resolver  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic


# ----------------------------------------------------------------------------- classificação (função pura)
def test_classificacao_exaustiva_sobre_os_enums_do_pyomo():
    from pyomo.contrib.solver.common.results import SolutionStatus, TerminationCondition
    despachaveis = set()
    for tc in TerminationCondition:
        for ss in SolutionStatus:
            c = classificar(tc.name, ss.name)
            assert c in CLASSIFICACOES
            if c in S.DESPACHAVEIS:
                despachaveis.add((tc.name, ss.name))
                assert ss.name in ("optimal", "feasible")
    assert ("convergenceCriteriaSatisfied", "optimal") in despachaveis
    assert ("maxTimeLimit", "feasible") in despachaveis and ("maxTimeLimit", "noSolution") not in despachaveis
    assert classificar("unbounded", "feasible") == "ilimitado"            # ponto factível de problema ilimitado ≠ despacho
    assert classificar("convergenceCriteriaSatisfied", "noSolution") == "desconhecido"
    assert classificar("algoNovo", "optimal") == "desconhecido" and classificar(None, None) == "desconhecido"


def test_convencao_de_gap():
    assert gaps(100.0, 99.0) == (1.0, 0.01)
    assert gaps(0.0, 0.0) == (0.0, 0.0) and gaps(0.0, -1.0) == (1.0, None)
    assert gaps(None, 1.0) == (None, None) and gaps(1.0, float("inf")) == (None, None)


# ----------------------------------------------------------------------------- terminações REAIS
def test_limite_de_tempo_real_sem_incumbente_nenhum_despacho():
    e, cp = X.instancia_maior()
    r = resolver(e, dataclasses.replace(CFG, time_limit_s=0.0), cp)
    assert (r.classificacao, r.terminacao, r.status_solucao) == ("sem_solucao", "maxTimeLimit", "noSolution")
    assert not r.solucao_primal and r.despacho is None and r.candidato is None and r.objetivo is None
    assert r.estado_despacho == "sem_despacho" and not r.aceito and r.auditoria is None


def test_limite_de_nos_real_sem_incumbente():
    e, cp = X.duas_baterias()
    r = resolver(e, dataclasses.replace(CFG, opcoes_highs={"mip_max_nodes": 0}), cp)
    assert r.classificacao == "sem_solucao" and r.terminacao == "iterationLimit" and r.despacho is None


def test_incumbente_real_nao_otimo_e_auditado():
    """mip_max_improving_sols = 1 interrompe no 1º incumbente (determinístico com 1 thread e semente fixa)."""
    e, cp = X.instancia_maior()
    otimo = resolver(e, CFG, cp)
    r = resolver(e, dataclasses.replace(CFG, opcoes_highs={"mip_max_improving_sols": 1}), cp)
    assert otimo.classificacao == "otimo" and otimo.aceito
    assert r.classificacao == "factivel_nao_otimo" and r.terminacao == "iterationLimit" and r.status_solucao == "feasible"
    assert r.solucao_primal and r.auditoria.aceito and r.estado_despacho == "aceito_factivel_nao_otimo" and r.aceito
    assert r.objetivo > otimo.objetivo + 1e-6 and r.limite_dual <= r.objetivo
    assert r.gap_rel is not None and r.gap_rel > 0 and r.gap_abs == pytest.approx(r.objetivo - r.limite_dual)
    assert r.configuracao["opcoes_highs"] == {"mip_max_improving_sols": 1}


def test_modelo_inviavel_trivial_sem_chamar_o_solver():
    """Demanda sem nenhuma fonte: nenhuma decisão no intervalo ⇒ inviável na construção (sem folga criada)."""
    m = F.malha(60, 1)
    e = F.entrada("SEM-FONTE", m, demandas=[F.demanda("syn-carga", [5], 60, "SEM-FONTE")], formulacao=X.F3)
    chamado = []
    r = resolver(e, CFG, {}, _executor=lambda *a: chamado.append(1))
    assert r.classificacao == "inviavel" and r.terminacao == "trivialmente_inviavel_na_construcao"
    assert "balanco_trivialmente_inviavel" in r.codigos() and not chamado and r.despacho is None


# ----------------------------------------------------------------------------- terminações SIMULADAS no adaptador
def _executor(term=None, status=None, incumbente="real", adulterar=None, carregar=True):
    """Resolve de verdade com HiGHS e, opcionalmente, sobrescreve a terminação ou adultera os valores carregados."""
    def run(modelo, config):
        exe = S._executar_highs(modelo, config)
        carregar_real = exe["carregar"]
        chamadas = []

        def carregar_fn():
            chamadas.append(1)
            if carregar:
                carregar_real()
            if adulterar:
                adulterar(modelo)
        exe["carregar"] = carregar_fn
        exe["_chamadas"] = chamadas
        if term is not None:
            exe["terminacao"] = term
        if status is not None:
            exe["status_solucao"] = status
        if incumbente != "real":
            exe["incumbente"] = incumbente
        run.exe = exe
        return exe
    return run


def test_limite_de_tempo_simulado_com_incumbente_aceito_como_nao_otimo():
    e, cp = X.a05_opt()
    ex = _executor(term="maxTimeLimit", status="feasible")
    r = resolver(e, CFG, cp, _executor=ex)
    assert r.classificacao == "factivel_nao_otimo" and r.estado_despacho == "aceito_factivel_nao_otimo" and r.aceito
    assert r.auditoria.aceito and r.despacho["baterias"]["syn-bess"]["P_c"] == pytest.approx((10.0,), abs=1e-6)


def test_limite_de_tempo_simulado_sem_incumbente_nao_carrega_valores():
    e, cp = X.a05_opt()
    ex = _executor(term="maxTimeLimit", status="noSolution")
    r = resolver(e, CFG, cp, _executor=ex)
    assert r.classificacao == "sem_solucao" and r.despacho is None and not r.aceito
    assert ex.exe["_chamadas"] == []                                  # nenhum valor foi carregado


@pytest.mark.parametrize("term,status,classe", [("algoNovo", "optimal", "desconhecido"),
                                                ("unbounded", "feasible", "ilimitado"),
                                                ("error", "noSolution", "erro"),
                                                ("licensingProblems", "noSolution", "erro"),
                                                ("infeasibleOrUnbounded", "noSolution", "inviavel_ou_ilimitado"),
                                                ("convergenceCriteriaSatisfied", "noSolution", "desconhecido")])
def test_estados_nao_despachaveis(term, status, classe):
    e, cp = X.a05_opt()
    ex = _executor(term=term, status=status)
    r = resolver(e, CFG, cp, _executor=ex)
    assert r.classificacao == classe and r.despacho is None and r.objetivo is None and not r.aceito
    assert r.estado_despacho == "sem_despacho" and ex.exe["_chamadas"] == []


def test_valores_nao_carregados_nunca_viram_nan_no_despacho():
    e, cp = X.a05_opt()
    r = resolver(e, CFG, cp, _executor=_executor(carregar=False))
    assert r.classificacao == "otimo" and r.despacho is None and not r.aceito
    assert "valor_nao_carregado" in r.codigos() and r.estado_despacho == "sem_despacho"


def _set(comp, idx, v):
    def f(m):
        getattr(m, comp)[idx].set_value(v, skip_validation=True)
    return f


@pytest.mark.parametrize("adulterar,familia", [
    (_set("P_R", ("syn-fv", 0), 15.0), "renovavel"),                  # potência adulterada
    (_set("e", ("syn-bess", 1), 60.0), "bess_energia"),               # estado adulterado
    (_set("P_d", ("syn-bess", 0), 3.0), "bess_exclusividade"),        # carga e descarga simultâneas
])
def test_solucao_adulterada_apos_resolver_e_rejeitada(adulterar, familia):
    e, cp = X.a05_opt()
    r = resolver(e, CFG, cp, _executor=_executor(adulterar=adulterar))
    assert r.solucao_primal and not r.aceito and r.estado_despacho == "rejeitado_auditoria"
    assert familia in r.auditoria.familias_reprovadas()


def test_integralidade_violada_rejeitada():
    e, cp = X.a06(preco_h2=10.0)
    r = resolver(e, CFG, cp, _executor=_executor(adulterar=lambda m: (m.u["syn-fc", 0].unfix(),
                                                                       m.u["syn-fc", 0].set_value(0.5, skip_validation=True))))
    assert not r.aceito and {"integralidade", "compromisso_fixo"} <= r.auditoria.familias_reprovadas()


def test_pwl_com_segmento_errado_rejeitada():
    """q adulterado para a corda (10 kW; 0,5)–(20 kW; 1,6) num ponto da curva não convexa ⇒ auditor rejeita."""
    e, cp = X.a06(carga=14.0, curva=X.CURVA_NAO_CONVEXA, preco_h2=7.0)
    corda = 0.5 + (1.6 - 0.5) * (14.0 - 10.0) / 10.0
    r = resolver(e, CFG, cp, _executor=_executor(adulterar=_set("q", ("syn-fc", 0), corda)))
    assert not r.aceito and "vazao_pwl" in r.auditoria.familias_reprovadas()


def test_objetivo_incoerente_com_os_valores_rejeitado():
    e, cp = X.b01b()
    r = resolver(e, CFG, cp, _executor=_executor(incumbente=3.0))
    assert not r.aceito and "objetivo_incoerente" in r.codigos()


# ----------------------------------------------------------------------------- bloqueios antes de resolver
def _nunca(*a):
    raise AssertionError("o solver não deveria ser chamado")


def test_parametro_economico_ausente_bloqueia():
    e, cp = X.a05_opt()
    b = dataclasses.replace(e.baterias[0], custo_throughput=None)
    r = resolver(dataclasses.replace(e, baterias=(b,)), CFG, cp, _executor=_nunca)
    assert r.classificacao == "bloqueado_validacao" and "parametro_ausente" in r.codigos() and r.despacho is None


def test_parametro_fisico_ausente_bloqueia():
    e, cp = X.a05_opt()
    b = dataclasses.replace(e.baterias[0], eta_carga=dataclasses.replace(e.baterias[0].eta_carga, valor=None))
    r = resolver(dataclasses.replace(e, baterias=(b,)), CFG, cp, _executor=_nunca)
    assert r.classificacao == "bloqueado_validacao" and "parametro_ausente" in r.codigos()


def test_entrada_3A_nao_ganha_capacidades_implicitamente():
    r = resolver(F.a05_opt_entrada(), CFG, {}, _executor=_nunca)
    assert r.classificacao == "bloqueado_validacao"
    assert {"termo_objetivo_nao_suportado_3A", "formulacao_nao_3bp"} & r.codigos()
    r = resolver(F.b01b()[0], CFG, {}, _executor=_nunca)
    assert r.classificacao == "bloqueado_validacao" and "formulacao_nao_3bp" in r.codigos()


def test_degradado_sem_criterio_ens_bloqueia():
    e, cp = X.a08(True)
    e2 = dataclasses.replace(e, politica_objetivo=dataclasses.replace(e.politica_objetivo, termos=()),
                             demandas=(dataclasses.replace(e.demandas[0], custo_energia_nao_suprida=None),))
    r = resolver(e2, CFG, cp, _executor=_nunca)
    assert r.classificacao == "bloqueado_validacao" and "criterio_ens_ausente" in r.codigos()


@pytest.mark.parametrize("cp,codigo", [({}, "compromisso_livre_nao_suportado_3BP"),
                                       ({"syn-ger": (0,)}, "transicao_nao_modelada_3BP"),
                                       ({"syn-ger": (1, 1)}, "compromisso_invalido"),
                                       ({"syn-ger": (True,)}, "compromisso_invalido"),
                                       ({"syn-ger": (1,), "syn-x": (1,)}, "compromisso_uid_desconhecido")])
def test_compromisso_livre_ou_com_transicao_bloqueado(cp, codigo):
    e, _ = X.a07()
    r = resolver(e, CFG, cp, _executor=_nunca)
    assert r.classificacao == "bloqueado_validacao" and codigo in r.codigos()


@pytest.mark.parametrize("campo,valor", [("time_limit_s", -1.0), ("time_limit_s", float("nan")), ("threads", 0),
                                         ("rel_gap", float("inf")), ("abs_gap", -1e-9), ("semente", -1),
                                         ("opcoes_highs", {"time_limit": 5})])
def test_configuracao_invalida_bloqueia(campo, valor):
    e, cp = X.b01b()
    r = resolver(e, dataclasses.replace(CFG, **{campo: valor}), cp, _executor=_nunca)
    assert r.classificacao == "bloqueado_validacao" and "configuracao_invalida" in r.codigos()
    r = resolver(e, None, cp, _executor=_nunca)
    assert r.classificacao == "bloqueado_validacao"


def test_solver_indisponivel_sem_falha(monkeypatch):
    monkeypatch.setattr(S, "verificar_ambiente", lambda: {"disponivel": False, "erro": "simulado", "versoes": {}})
    e, cp = X.b01b()
    r = resolver(e, CFG, cp)
    assert r.classificacao == "solver_indisponivel" and r.despacho is None and not r.aceito


def test_highs_recusa_sos_e_nao_linearidade():
    """Capacidades REAIS da interface: SOS2 e termos bilineares são recusados — o 3B-P não usa nenhum dos dois."""
    from pyomo.contrib.solver.common.factory import SolverFactory
    opt = SolverFactory("highs")
    m = pe.ConcreteModel()
    m.z = pe.Var([1, 2, 3], bounds=(0, 1))
    m.s = pe.SOSConstraint(var=m.z, sos=2)
    m.o = pe.Objective(expr=m.z[1])
    with pytest.raises(Exception):
        opt.solve(m, load_solutions=False, raise_exception_on_nonoptimal_result=False)
    m2 = pe.ConcreteModel()
    m2.x, m2.y = pe.Var(bounds=(0, 1)), pe.Var(domain=pe.Binary)
    m2.c = pe.Constraint(expr=m2.x * m2.y <= 1)
    m2.o = pe.Objective(expr=m2.x)
    with pytest.raises(Exception):
        opt.solve(m2, load_solutions=False, raise_exception_on_nonoptimal_result=False)
    e, cp = X.multi_uid()
    from ems_v2.milp.modelo import construir_modelo
    mc = construir_modelo(e, cp)
    assert not list(mc.modelo.component_data_objects(pe.SOSConstraint))
    for c in mc.modelo.component_data_objects(pe.Constraint, active=True):
        assert c.body.polynomial_degree() <= 1, c.name
    assert mc.modelo.J.expr.polynomial_degree() <= 1


# ----------------------------------------------------------------------------- reprodutibilidade
def test_reprodutibilidade_das_fixtures_e_das_solucoes():
    for f in (X.a05_opt, X.duas_baterias, X.multi_uid, X.pwl_com_bateria):
        (e1, c1), (e2, c2) = f(), f()
        assert json_canonico(e1) == json_canonico(e2) and hash_entrada(e1) == hash_entrada(e2) and c1 == c2
        r1, r2 = resolver(e1, CFG, c1), resolver(e2, CFG, c2)
        assert r1.hash_entrada == r2.hash_entrada and r1.hash_compromisso == r2.hash_compromisso
        assert r1.despacho == r2.despacho and r1.objetivo == r2.objetivo and r1.classificacao == r2.classificacao


def test_tamanho_do_modelo_e_variaveis_por_intervalo():
    e, cp = X.multi_uid()
    r = resolver(e, CFG, cp)
    N = e.malha.N
    # variáveis por intervalo (T) e energia por fronteira (K = N + 1)
    assert all(len(v["e"]) == N + 1 and len(v["P_c"]) == N for v in r.despacho["baterias"].values())
    assert r.tamanho["binarias_livres"] == 2 * N + 1 * N   # z_b de 2 bancos + δ do único segmento da PEMFC
