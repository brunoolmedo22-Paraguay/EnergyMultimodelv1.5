"""Correções da auditoria independente do PR #12 (C-3B-01, C-3B-02 e robustez a exceções do solver).

Testes ADVERSARIAIS: cada um falha no código anterior (a8e3426) — com exceção não controlada ou com despacho
indevidamente aceito — e passa com a correção. Sintético/algébrico.
"""
import math

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

from ems_v2 import fixtures_3b as X  # noqa: E402
from ems_v2.audit import CandidatoDespacho, auditar  # noqa: E402
from ems_v2.milp import solver as S  # noqa: E402
from ems_v2.milp.config import CONFIG_ANALITICA as CFG  # noqa: E402
from ems_v2.milp.integridade import verificar_testemunho  # noqa: E402
from ems_v2.milp.solver import resolver  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
NAN, INF = float("nan"), float("inf")


def _nunca(*a):
    raise AssertionError("o solver não deveria ser chamado")


# ----------------------------------------------------------------------------- C-3B-01
@pytest.mark.parametrize("prog", [
    {"syn-ger": (NAN,)}, {"syn-ger": (INF,)}, {"syn-ger": (-INF,)}, {"syn-ger": (None,)}, {"syn-ger": ("abc",)},
    {"syn-ger": ("1",)}, {"syn-ger": (0.7,)}, {"syn-ger": (1.0,)}, {"syn-ger": (True,)}, {"syn-ger": (2,)},
    {"syn-ger": 1}, {"syn-ger": None}, {"syn-ger": ((1,),)}, {"syn-ger": ()}, {"syn-ger": (1, 1)},
    {"syn-ger": {"0": 1}}, [("syn-ger", (1,))], "syn-ger", 1, {1: (1,)}, {("syn-ger",): (1,)},
], ids=lambda p: repr(p)[:30])
def test_c3b01_programa_invalido_bloqueia_sem_excecao(prog):
    e, _ = X.a07()
    r = resolver(e, CFG, prog, _executor=_nunca)
    assert r.classificacao == "bloqueado_validacao" and not r.aceito and r.despacho is None
    assert r.codigos() & {"compromisso_invalido", "compromisso_uid_desconhecido", "compromisso_livre_nao_suportado_3BP"}
    assert r.hash_compromisso is None or len(r.hash_compromisso) == 64


def test_c3b01_hash_sem_perda_deterministico_e_independente_da_ordem():
    h = S._hash_compromisso
    assert h({"syn-ger": (1,)}) == h({"syn-ger": (1,)}) == h({"syn-ger": [1]})
    assert len({h({"g": (1,)}), h({"g": (1.0,)}), h({"g": (True,)}), h({"g": ("1",)})}) == 4    # sem conversão
    assert h({"a": (1, 0), "b": (0, 0)}) == h({"b": (0, 0), "a": (1, 0)})
    assert h({"g": (NAN,)}) == h({"g": (NAN,)}) and h({"g": (INF,)}) != h({"g": (-INF,)})
    for estranho in (object(), {"g": (object(),)}, {1: 2, "1": 2}):
        assert h(estranho) is not None
    assert h({1: 2}) != h({"1": 2})


def test_c3b01_programa_valido_inalterado_e_hash_registrado():
    e, cp = X.multi_uid()
    r = resolver(e, CFG, cp)
    assert r.aceito and r.hash_compromisso == S._hash_compromisso(cp)
    e, cp = X.a07()
    assert resolver(e, CFG, cp).classificacao == "inviavel"


def test_c3b01_auditor_tambem_exige_inteiros_estritos():
    e, _ = X.a07()
    c = CandidatoDespacho(demandas={"syn-carga": {"ell": (0.0,)}}, geradores={"syn-ger": {"u": (1.0,), "p": (5.0,)}})
    for prog in ({"syn-ger": (1.0,)}, {"syn-ger": (True,)}, {"syn-ger": (NAN,)}, ["x"]):
        r = auditar(e, c, compromisso_fixo=prog)
        assert not r.aceito and "compromisso_invalido" in r.codigos()


# ----------------------------------------------------------------------------- C-3B-02
def _adulterar(f):
    def run(modelo, config):
        exe = S._executar_highs(modelo, config)
        real = exe["carregar"]

        def carregar():
            real()
            f(modelo)
        exe["carregar"] = carregar
        return exe
    return run


def _set(comp, idx, v):
    def f(m):
        var = getattr(m, comp)[idx]
        if var.fixed:
            var.unfix()
        var.set_value(v, skip_validation=True)
    return f


def _rejeitado_integridade(r, familia_ou_cod):
    assert r.classificacao == "otimo" and r.solucao_primal
    assert not r.aceito and r.estado_despacho == "rejeitado_integridade"
    assert "testemunho_milp_invalido" in r.codigos()
    assert familia_ou_cod in r.integridade.familias_reprovadas() | r.integridade.codigos()


def test_c3b02_z_b_fracionario_com_potencias_e_energia_preservadas():
    e, cp = X.a05_opt()
    r = resolver(e, CFG, cp, _executor=_adulterar(_set("z_b", ("syn-bess", 0), 0.5)))
    _rejeitado_integridade(r, "integralidade_z_b")
    assert r.auditoria.aceito                      # a auditoria física sozinha não vê z_b: daí a camada separada
    b = r.despacho["baterias"]["syn-bess"]
    assert b["P_c"] == pytest.approx((10.0,)) and b["e"] == pytest.approx((50.0, 59.0))


def test_c3b02_z_b_incoerente_com_a_carga():
    e, cp = X.a05_opt()
    r = resolver(e, CFG, cp, _executor=_adulterar(_set("z_b", ("syn-bess", 0), 0.0)))
    _rejeitado_integridade(r, "coerencia_z_b")


CURVA = X.CURVA_NAO_CONVEXA          # 15 kW está no segmento 1 (14–16 kW)


def _a06():
    return X.a06(carga=15.0, curva=CURVA, preco_h2=7.0)


def test_c3b02_segmento_pwl_correto_reportado():
    e, cp = _a06()
    r = resolver(e, CFG, cp)
    g = r.despacho["geradores"]["syn-fc"]
    assert r.aceito and r.integridade.aceito and g["segmento_ativo"] == (1,)
    assert g["delta"][0] == pytest.approx((0.0, 1.0, 0.0)) and g["theta"][0][1] == pytest.approx(0.5)


def test_c3b02_delta_em_segmento_errado():
    def mover(m):
        for s in range(3):
            m.delta["syn-fc", s, 0].set_value(1.0 if s == 0 else 0.0, skip_validation=True)
    e, cp = _a06()
    r = resolver(e, CFG, cp, _executor=_adulterar(mover))
    _rejeitado_integridade(r, "reconstrucao_pwl")
    assert "theta_no_segmento" in r.integridade.familias_reprovadas()


def test_c3b02_delta_fracionario():
    e, cp = _a06()
    r = resolver(e, CFG, cp, _executor=_adulterar(_set("delta", ("syn-fc", 1, 0), 0.5)))
    _rejeitado_integridade(r, "integralidade_delta")


def test_c3b02_theta_fora_do_segmento_selecionado():
    e, cp = _a06()
    r = resolver(e, CFG, cp, _executor=_adulterar(_set("theta", ("syn-fc", 0, 0), 0.3)))
    _rejeitado_integridade(r, "theta_no_segmento")


def test_c3b02_theta_fora_de_0_1():
    e, cp = _a06()
    r = resolver(e, CFG, cp, _executor=_adulterar(_set("theta", ("syn-fc", 1, 0), 1.7)))
    _rejeitado_integridade(r, "dominio_theta")


@pytest.mark.parametrize("comp,idx,v", [("theta", ("syn-fc", 2, 0), None), ("delta", ("syn-fc", 1, 0), NAN),
                                        ("delta", ("syn-fc", 0, 0), None), ("z_b", ("syn-bess", 0), INF)])
def test_c3b02_auxiliar_sem_valor_ou_nao_finito(comp, idx, v):
    e, cp = (_a06() if comp != "z_b" else X.a05_opt())
    r = resolver(e, CFG, cp, _executor=_adulterar(_set(comp, idx, v)))
    assert not r.aceito and r.despacho is None and r.estado_despacho == "sem_despacho"
    assert "valor_nao_carregado" in r.codigos()


def test_c3b02_verificador_direto_rejeita_testemunho_ausente_ou_incoerente():
    e, cp = _a06()
    r = resolver(e, CFG, cp)
    d = r.despacho
    g = dict(d["geradores"]["syn-fc"])
    sem_delta = {**d, "geradores": {"syn-fc": {k: v for k, v in g.items() if k != "delta"}}}
    assert "testemunho_ausente" in verificar_testemunho(e, sem_delta).codigos()
    seg_errado = {**d, "geradores": {"syn-fc": {**g, "segmento_ativo": (0,)}}}
    assert "segmento_reportado_incoerente" in verificar_testemunho(e, seg_errado).codigos()
    e2, _ = X.a05_opt()
    d2 = resolver(e2, CFG, {}).despacho
    sem_z = {**d2, "baterias": {"syn-bess": {k: v for k, v in d2["baterias"]["syn-bess"].items() if k != "z_b"}}}
    assert "testemunho_ausente" in verificar_testemunho(e2, sem_z).codigos()


@pytest.mark.parametrize("f", [X.a01, X.a05_opt, X.duas_baterias, X.exclusividade, X.multi_uid, X.pwl_com_bateria,
                               X.instancia_maior])
def test_c3b02_testemunho_integro_nas_solucoes_legitimas(f):
    e, cp = f()
    r = resolver(e, CFG, cp)
    assert r.aceito and r.integridade is not None and r.integridade.aceito


def test_c3b02_integridade_usa_as_tolerancias_provisorias_sem_relaxar():
    e, cp = X.a05_opt()
    r = resolver(e, CFG, cp, _executor=_adulterar(_set("z_b", ("syn-bess", 0), 1.0 - 2e-6)))
    assert r.estado_despacho == "rejeitado_integridade"          # 2e-6 > tolerância binária provisória 1e-6
    r = resolver(e, CFG, cp, _executor=_adulterar(_set("z_b", ("syn-bess", 0), 1.0 - 5e-7)))
    assert r.aceito                                              # dentro da tolerância declarada


# ----------------------------------------------------------------------------- robustez a exceções
def test_opcao_highs_invalida_vira_erro_controlado():
    import dataclasses
    e, cp = X.b01b()
    for opc in ({"opcao_inexistente_xyz": 1}, {"mip_max_nodes": "abc"}, {"mip_feasibility_tolerance": -1.0}):
        r = resolver(e, dataclasses.replace(CFG, opcoes_highs=opc), cp)
        assert r.classificacao == "erro" and "opcao_highs_invalida" in r.codigos()
        assert not r.aceito and r.despacho is None and r.objetivo is None and not r.solucao_primal


@pytest.mark.parametrize("executor,codigo", [
    (lambda m, c: (_ for _ in ()).throw(RuntimeError("falha simulada do HiGHS")), "falha_solver"),
    (lambda m, c: (_ for _ in ()).throw(MemoryError("sem memória (simulado)")), "falha_solver"),
    (lambda m, c: None, "falha_solver"),
])
def test_excecao_do_solver_vira_erro_controlado(executor, codigo):
    e, cp = X.b01b()
    r = resolver(e, CFG, cp, _executor=executor)
    assert r.classificacao == "erro" and codigo in r.codigos() and r.terminacao == "excecao"
    assert not r.aceito and r.despacho is None and r.estado_despacho == "sem_despacho"


def test_excecao_do_carregador_vira_erro_controlado():
    def run(modelo, config):
        exe = S._executar_highs(modelo, config)

        def falha():
            raise RuntimeError("falha simulada do carregador")
        exe["carregar"] = falha
        return exe
    e, cp = X.b01b()
    r = resolver(e, CFG, cp, _executor=run)
    assert r.classificacao == "erro" and "falha_carregamento" in r.codigos()
    assert not r.aceito and r.despacho is None and r.objetivo is None
    assert r.terminacao == "convergenceCriteriaSatisfied"          # terminação original registrada, sem despacho
    assert not math.isnan(r.tempos_s["total_s"])
