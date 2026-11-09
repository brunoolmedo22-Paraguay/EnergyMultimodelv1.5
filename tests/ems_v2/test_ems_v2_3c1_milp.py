"""Piso 3C-1 — MILP de commitment dinâmico contra HiGHS REAL: casos A–I, ótimo por enumeração (H), auditoria
adversarial sobre a saída do solver (K) e retrocompatibilidade com o 3B-P (L).

Sem Pyomo/HiGHS estes testes são PULADOS explicitamente (nunca contados como executados). Sintético/algébrico.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

from ems_v2 import FORMULACAO_3C1  # noqa: E402
from ems_v2 import fixtures_3b as X  # noqa: E402
from ems_v2 import fixtures_3c1 as Y  # noqa: E402
from ems_v2.compromisso import contrato as CT  # noqa: E402
from ems_v2.diagnostics import ContratoInvalido  # noqa: E402
from ems_v2.milp import modelo_3c1 as M3  # noqa: E402
from ems_v2.milp.config import CONFIG_ANALITICA as C  # noqa: E402
from ems_v2.milp.solver import _executar_highs, resolver  # noqa: E402
from ems_v2.milp.solver_3c1 import resolver_3c1  # noqa: E402
from ems_v2.ponte.compromisso import plano_de_resultado_3c1  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enumeracao_3c1 import enumerar  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
TOL = 1e-6


def _ok(r):
    assert r.aceito and r.estado_despacho == "aceito_otimo", (r.classificacao, r.estado_despacho, r.codigos(),
                                                             r.auditoria and r.auditoria.familias_reprovadas())
    return r


def _g(r, k="syn-ter"):
    d = r.despacho["geradores"][k]
    return ([round(x) for x in d["u"]], [round(x, 6) for x in d["p"]], [round(x) for x in d["y"]],
            [round(x) for x in d["z"]])


def _vec(r, k, campo):
    return [round(x, 6) for x in r.despacho["baterias"][k][campo]]


# ----------------------------------------------------------------------------- Caso A — transições binárias
def test_caso_a_transicoes_e_eventos():
    r = _ok(resolver_3c1(Y.caso_a(), C))
    assert _g(r) == ([0, 1, 1, 0], [0, 30, 30, 0], [0, 1, 0, 0], [0, 0, 0, 1])
    assert abs(r.objetivo - 7.0) < TOL and r.custos_modelo["eventos"] == pytest.approx(7.0)
    assert r.eventos == {"syn-ter": {"partidas": 1, "paradas": 1}} and r.versao_formulacao == FORMULACAO_3C1
    assert {"transicao_M09", "rampa_M11a", "permanencia_corridas"} <= set(r.auditoria.familias_verificadas)


def test_caso_a_custo_de_evento_nao_e_multiplicado_por_h():
    for d in (1, 60):                              # Δ diferente, mesmo número de eventos ⇒ mesmo custo
        e = Y.caso_a()
        m = dataclasses.replace(e.base.malha, delta_min=d, horizonte_previsao_min=4 * d)

        def ss(s):
            return dataclasses.replace(s, passo_s=d * 60)
        b = e.base
        dem = tuple(dataclasses.replace(x, potencia=ss(x.potencia)) for x in b.demandas)
        ger = tuple(dataclasses.replace(g, disponibilidade=dataclasses.replace(g.disponibilidade,
                                                                              serie=ss(g.disponibilidade.serie)))
                    for g in b.geradores)
        e2 = dataclasses.replace(e, base=dataclasses.replace(b, malha=m, demandas=dem, geradores=ger))
        r = _ok(resolver_3c1(e2, C))
        assert r.custos_modelo["eventos"] == pytest.approx(7.0)


def test_caso_a_sem_termo_eventos_transicoes_restritas_sem_custo():
    e = Y.caso_a()
    e = dataclasses.replace(e, termos_adicionais=(), unidades=(dataclasses.replace(e.unidades[0], custo_partida=None,
                                                                                    custo_parada=None),))
    r = _ok(resolver_3c1(e, C))
    assert "eventos" not in r.custos_modelo and r.objetivo == 0.0 and _g(r)[2] == [0, 1, 0, 0]


# ----------------------------------------------------------------------------- Caso B — rampa
def test_caso_b_rampa_desde_p_anterior():
    r = _ok(resolver_3c1(Y.caso_b(), C))
    assert _g(r)[1] == [15, 20, 25, 30] and _vec(r, "syn-bess", "P_d") == [15, 10, 5, 0]
    assert r.objetivo == pytest.approx(2.5) and set(r.transicoes_bloqueadas) == {"syn-ter:partida", "syn-ter:parada"}


def test_caso_b_rampa_mais_lenta_reduz_a_contribuicao():
    r = _ok(resolver_3c1(Y.caso_b(R=0.4), C))      # 2 kW por intervalo de 5 min
    assert _g(r)[1] == [12, 14, 16, 18]


# ----------------------------------------------------------------------------- Caso C / D — permanências
def test_caso_c_tempo_minimo_on():
    r = _ok(resolver_3c1(Y.caso_c(), C))
    assert _g(r) == ([1, 1, 1, 0], [20, 10, 10, 0], [1, 0, 0, 0], [0, 0, 0, 1]) and r.objetivo == pytest.approx(5.0)
    r0 = _ok(resolver_3c1(Y.caso_c(0.0), C))
    assert _g(r0)[0] == [1, 0, 0, 0] and r0.objetivo == pytest.approx(0.0)


def test_caso_d_tempo_minimo_off():
    r = _ok(resolver_3c1(Y.caso_d(), C))
    assert _g(r) == ([0, 0, 0, 1], [0, 0, 0, 20], [0, 0, 0, 1], [1, 0, 0, 0]) and r.objetivo == pytest.approx(3.5)
    r0 = _ok(resolver_3c1(Y.caso_d(0.0), C))
    assert _g(r0)[0] == [1, 0, 0, 1] and r0.objetivo == pytest.approx(1.0)


# ----------------------------------------------------------------------------- Caso E — obrigação herdada
def test_caso_e_obrigacao_herdada_desde_t0():
    r = _ok(resolver_3c1(Y.caso_e(), C))
    assert _g(r)[0] == [0, 0, 1, 1] and r.objetivo == pytest.approx(10.0)
    r = _ok(resolver_3c1(Y.caso_e(ligado=True), C))
    assert _g(r)[0] == [1, 1, 0, 0] and _vec(r, "syn-bess", "P_c") == [10, 10, 0, 0] and r.objetivo == pytest.approx(5.0)


def test_caso_e_obrigacao_maior_que_a_janela_e_transportada():
    r = _ok(resolver_3c1(Y.caso_e(tempo_s=0, T=120.0), C))
    assert _g(r)[0] == [0, 0, 0, 0] and r.obrigacoes_residuais_s == {"syn-ter": 3600}
    assert r.garantia_permanencia == "residual_vinculante"


# ----------------------------------------------------------------------------- Caso F — borda do horizonte
def test_caso_f_borda_cumprir_na_janela():
    r = _ok(resolver_3c1(Y.caso_f("cumprir_na_janela"), C))
    assert _g(r)[0] == [0, 1, 1, 1] and r.objetivo == pytest.approx(5.0)
    assert r.garantia_permanencia == "completa_na_janela" and r.obrigacoes_residuais_s == {}


def test_caso_f_borda_obrigacao_residual_vinculante():
    r = _ok(resolver_3c1(Y.caso_f("obrigacao_residual_vinculante"), C))
    assert _g(r)[0] == [0, 0, 0, 1] and r.objetivo == pytest.approx(0.0)
    assert r.garantia_permanencia == "residual_vinculante" and r.obrigacoes_residuais_s == {"syn-ter": 1800}
    mt = r.memoria_terminal[0]
    assert (mt.ligado, mt.tempo_no_estado_s, mt.obrigacao_residual_s) == (True, 900, 1800)


# ----------------------------------------------------------------------------- Caso G — várias unidades
def test_caso_g_unidades_do_mesmo_bloco_independentes():
    r = _ok(resolver_3c1(Y.caso_g(), C))
    assert _g(r, "syn-ter#1")[0] == [1, 1, 1, 1] and _g(r, "syn-ter#2")[0] == [0, 0, 1, 1]
    assert r.eventos == {"syn-ter#1": {"partidas": 0, "paradas": 0}, "syn-ter#2": {"partidas": 1, "paradas": 0}}
    assert r.obrigacoes_residuais_s == {"syn-ter#2": 900} and r.objetivo == pytest.approx(1.0)
    mem = {m.uid: m for m in r.memoria_terminal}
    assert mem["syn-ter#1"].tempo_no_estado_s == 3600 + 3600 and mem["syn-ter#2"].tempo_no_estado_s == 1800


# ----------------------------------------------------------------------------- Caso H — enumeração exaustiva
def test_caso_h_otimo_igual_a_enumeracao_exaustiva_independente():
    sol = enumerar(Y.caso_h())
    assert sol, "enumeração sem programa factível"
    melhor, segundo = sol[0], sol[1]
    assert float(segundo[0]) - float(melhor[0]) > 1e-3                # ótimo único (diferença 2,0)
    r = _ok(resolver_3c1(Y.caso_h(), C))
    assert abs(r.objetivo - float(melhor[0])) < 1e-6 and abs(r.auditoria.custos_reconstruidos["total"] - 12.7) < 1e-6
    for k in ("syn-ter", "syn-fc"):
        u, p, y, z = _g(r, k)
        assert tuple(u) == melhor[1][k] and y == melhor[2][k] and z == melhor[3][k], k
        assert all(abs(a - float(b)) < 1e-6 for a, b in zip(p, melhor[4][k])), k
    assert r.gap_rel == pytest.approx(0.0, abs=1e-9)


# ----------------------------------------------------------------------------- Caso I — inviabilidade verdadeira
@pytest.mark.parametrize("f", [Y.caso_i_rampa, Y.caso_i_permanencia])
def test_caso_i_inviabilidade_sem_folgas(f):
    r = resolver_3c1(f(), C)
    assert r.classificacao == "inviavel" and r.despacho is None and not r.aceito and r.estado_despacho == "sem_despacho"
    with pytest.raises(ContratoInvalido):
        plano_de_resultado_3c1(r, f())


def test_modelo_sem_variaveis_de_folga_linear_e_sem_sos():
    import pyomo.environ as pe
    mc = M3.construir_modelo_3c1(Y.caso_h())
    m = mc.modelo
    nomes = {v.parent_component().name for v in m.component_data_objects(pe.Var)}
    # só variáveis físicas/decisão (caso H: sem banco, sem descarte, serviço duro ⇒ ℓ inexistente); nenhuma folga
    assert nomes == {"P_R", "C_oper", "u", "p", "delta", "theta", "q", "y", "z"}, nomes
    assert all(c.body.polynomial_degree() <= 1 for c in m.component_data_objects(pe.Constraint, active=True))
    assert m.J.expr.polynomial_degree() <= 1
    assert not list(m.component_objects(pe.SOSConstraint))
    for v in m.component_data_objects(pe.Var):
        if v.parent_component().name in ("u", "y", "z", "delta"):
            assert v.is_binary() and not v.fixed


# ----------------------------------------------------------------------------- PEMFC (abstração instantânea)
def test_pemfc_abstracao_instantanea_com_massas_de_evento():
    r = _ok(resolver_3c1(Y.pemfc_instantanea(), C))
    assert _g(r, "syn-fc")[0] == [0, 1, 1, 0]
    # q(15) = 0,9 kg/h; h = 1/60; 2 intervalos: 0,03 kg + m^SU 0,002 + m^SD 0,001 = 0,033 kg × 10 R$/kg
    assert r.custos_modelo["combustivel_h2"] == pytest.approx(0.33)
    assert "pemfc_abstracao_instantanea" in r.codigos()


# ----------------------------------------------------------------------------- compromisso parcial
def test_compromisso_parcial_fixado_respeitado_e_bloqueios():
    r = _ok(resolver_3c1(Y.caso_c(0.0), C, {"syn-ter": (1, 1, None, None)}))
    assert _g(r)[0][:2] == [1, 1]
    r = resolver_3c1(Y.caso_b(), C, {"syn-ter": (1, 0, None, None)})
    assert r.classificacao == "bloqueado_validacao" and "transicao_fixada_nao_representavel" in r.codigos()
    r = resolver_3c1(Y.caso_a(), C, {"syn-ter": (True, 0, 0, 0)})
    assert r.classificacao == "bloqueado_validacao" and "compromisso_invalido" in r.codigos()
    r = resolver_3c1(Y.caso_c(), C, {"syn-ter": (1, 0, None, None)})        # viola U = 3 ⇒ inviável (não relaxa)
    assert r.classificacao == "inviavel"


# ----------------------------------------------------------------------------- Caso K — adulteração após o HiGHS
def _executor_adulterado(alterar):
    def exe(modelo, config):
        out = _executar_highs(modelo, config)
        carregar = out["carregar"]

        def carregar_e_adulterar():
            carregar()
            alterar(modelo)
        out["carregar"] = carregar_e_adulterar
        return out
    return exe


@pytest.mark.parametrize("caso,alterar,familia", [
    (Y.caso_a, lambda m: m.y["syn-ter", 1].set_value(0), "transicao_M09"),                     # arranque apagado
    (Y.caso_a, lambda m: (m.u["syn-ter", 2].set_value(0), m.p["syn-ter", 2].set_value(0)), "balanco"),   # estado
    (Y.caso_b, lambda m: m.p["syn-ter", 0].set_value(30.0), "rampa_M11a"),                     # rampa
    (Y.caso_c, lambda m: (m.u["syn-ter", 1].set_value(0), m.u["syn-ter", 2].set_value(0),
                          m.z["syn-ter", 1].set_value(1), m.z["syn-ter", 3].set_value(0)), "permanencia_M12"),
])
def test_caso_k_solucao_adulterada_apos_highs_rejeitada_e_sem_plano(caso, alterar, familia):
    e = caso()
    r = resolver_3c1(e, C, _executor=_executor_adulterado(alterar))
    assert not r.aceito and r.estado_despacho == "rejeitado_auditoria", r.estado_despacho
    assert familia in r.auditoria.familias_reprovadas(), r.auditoria.familias_reprovadas()
    with pytest.raises(ContratoInvalido) as exc:
        plano_de_resultado_3c1(r, e)
    assert "plano_de_solucao_nao_aceita" in exc.value.codigos


def test_caso_k_discretizacao_sabotada_no_milp_e_detectada_pelo_auditor(monkeypatch):
    real = CT.discretizar

    def sabotada(e):
        return {k: dataclasses.replace(d, U=1) for k, d in real(e).items()}    # U = 3 → 1 (só no construtor MILP)
    monkeypatch.setattr(M3, "discretizar", sabotada)
    r = resolver_3c1(Y.caso_c(), C)
    assert r.classificacao == "otimo" and not r.aceito and r.estado_despacho == "rejeitado_auditoria"
    assert {"permanencia_M12", "permanencia_corridas"} & r.auditoria.familias_reprovadas()


def test_objetivo_incoerente_e_terminacoes_sem_despacho():
    def exe_lim(modelo, config):
        out = _executar_highs(modelo, config)
        out["terminacao"], out["status_solucao"] = "maxTimeLimit", "noSolution"
        return out
    r = resolver_3c1(Y.caso_h(), C, _executor=exe_lim)
    assert r.classificacao == "sem_solucao" and r.despacho is None

    def exe_obj(modelo, config):
        out = _executar_highs(modelo, config)
        out["incumbente"] = out["incumbente"] + 1.0
        return out
    r = resolver_3c1(Y.caso_h(), C, _executor=exe_obj)
    assert not r.aceito and "objetivo_incoerente" in r.codigos()

    def exe_falha(modelo, config):
        raise RuntimeError("falha simulada")
    r = resolver_3c1(Y.caso_a(), C, _executor=exe_falha)
    assert r.classificacao == "erro" and "falha_solver" in r.codigos()


def test_limite_de_tempo_real_e_configuracao_invalida():
    r = resolver_3c1(Y.caso_h(), dataclasses.replace(C, time_limit_s=0.0))
    assert r.classificacao in ("sem_solucao", "factivel_nao_otimo") and r.estado_despacho != "aceito_otimo"
    r = resolver_3c1(Y.caso_a(), "x")
    assert r.classificacao == "bloqueado_validacao" and "configuracao_invalida" in r.codigos()


# ----------------------------------------------------------------------------- Caso L — retrocompatibilidade
def test_caso_l_api_3bp_inalterada_rejeita_transicoes_e_3c1():
    e, _ = X.a07()
    r = resolver(e, C, {"syn-ger": (0,)})
    assert r.classificacao == "bloqueado_validacao" and "transicao_nao_modelada_3BP" in r.codigos()
    r = resolver(e, C, {})
    assert "compromisso_livre_nao_suportado_3BP" in r.codigos()
    r = resolver_3c1(e, C)
    assert r.classificacao == "bloqueado_validacao" and "formulacao_nao_3c1" in r.codigos()


@pytest.mark.parametrize("nome", ["a06", "pwl_com_bateria", "multi_uid", "a08_d", "a07", "instancia_maior"])
def test_caso_l_3c1_com_estado_mantido_reproduz_o_3bp(nome):
    f = (lambda: X.a08(True)) if nome == "a08_d" else getattr(X, nome)
    e, cp = f()
    r2 = resolver(e, C, cp)
    r3 = resolver_3c1(Y.de_3bp(e), C)
    assert r2.classificacao == r3.classificacao and r2.estado_despacho == r3.estado_despacho
    if r2.aceito:
        assert r3.objetivo == pytest.approx(r2.objetivo, abs=1e-6)
        for k, d in r2.despacho["geradores"].items():
            assert [round(x) for x in r3.despacho["geradores"][k]["u"]] == [round(x) for x in d["u"]]
        assert r3.auditoria.custos_reconstruidos["total"] == pytest.approx(r2.auditoria.custos_reconstruidos["total"],
                                                                          abs=1e-6)
