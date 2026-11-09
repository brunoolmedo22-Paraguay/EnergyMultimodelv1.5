"""Piso 3C-4 — MILP de UMA janela com termo terminal contra HiGHS real (sintético/algébrico; sem Pyomo: pulados).

Valores esperados ANALÍTICOS (raciocínio nas docstrings). Cobre: termo 'nenhum' ≡ 3C-3 (mesmo despacho e objetivo),
Φ linear e energia mínima, PWL 1D NÃO convexo (exato por segmentos), envoltória 2D, seleção de modo da PEMFC com
memória terminal, aproximação local, referências, região inválida (H11), adulteração pós-solver (H16) e o plano a partir
da visão núcleo (C-3C4-01).
"""
from __future__ import annotations

from dataclasses import replace

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

from ems_v2 import fixtures_3c3 as F3  # noqa: E402
from ems_v2 import fixtures_3c4 as F  # noqa: E402
from ems_v2.diagnostics import ContratoInvalido  # noqa: E402
from ems_v2.hierarquia.contrato import ParametroBateria, TermoTerminal3C4  # noqa: E402
from ems_v2.hierarquia.mpc import plano_de_resultado_3c4  # noqa: E402
from ems_v2.hierarquia.valor import interpolar_1d  # noqa: E402
from ems_v2.milp.config import CONFIG_ANALITICA  # noqa: E402
from ems_v2.milp.solver_3c3 import resolver_3c3  # noqa: E402
from ems_v2.milp.solver_3c4 import resolver_3c4, visao_nucleo_3c3  # noqa: E402
from ems_v2.rede.execucao import plano_de_resultado_3c3  # noqa: E402
from test_ems_v2_3c4_apoio import entrada, entrada4, ger, modo, ref, sens, sinal, termo  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
CH = "custo_futuro_estimado"


def declarado(tipo, **kw):
    lin = tuple(ParametroBateria(u, v) for u, v in kw.get("lin", {}).items())
    em = tuple(ParametroBateria(u, v) for u, v in kw.get("emin", {}).items())
    return TermoTerminal3C4(tipo, lin, em, None, "declarado no teste", F.proc("t"))


def res(e4):
    return resolver_3c4(e4, CONFIG_ANALITICA)


def E_N(r, uid=F.BESS):
    return r.despacho["baterias"][uid]["e"][-1]


@pytest.mark.parametrize("caso", [F3.caso_g1, F3.caso_g3, lambda: F3.caso_g9("A"), lambda: F3.caso_g4(True)])
def test_termo_nenhum_equivale_ao_3c3(caso):
    e = caso()
    r3 = resolver_3c3(e, CONFIG_ANALITICA)
    r4 = res(entrada4(e, declarado("nenhum_declarado")))
    assert r3.aceito and r4.aceito
    assert r4.objetivo == pytest.approx(r3.objetivo, abs=1e-9)
    assert r4.despacho["baterias"] == r3.despacho["baterias"] and r4.intercambio == r3.intercambio
    assert r4.custo_futuro_estimado_R is None and "custo_futuro_estimado" not in r4.custos_modelo


def test_phi_linear_e_energia_minima_analiticos():
    """G9A (c_imp = 0,2; 1,0; e0 = 45 kWh; P̄ = 20 kW; h = 0,25): Φ = −2 E ⇒ carregar 20 kW nos dois intervalos
    (custo marginal 0,25 e 1,05 < 2 R$/kWh): E(N) = 55, J = 2,0 + 10,0 + 0,5 − 110 = −97,5. Ē = 45 ⇒ arbitragem
    que devolve o banco a 45: carrega 20 kW em t = 0 (0,2) e descarrega 20 kW em t = 1 (1,0):
    J = 0,25·0,2·40 + 0,05·0,25·40 = 2,0 + 0,5 = 2,5 (E(N) = 45 exatamente)."""
    e = F3.caso_g9("A")
    r = res(entrada4(e, declarado("valor_linear_declarado", lin={"syn-bess": 2.0})))
    assert r.aceito and E_N(r) == pytest.approx(55.0)
    assert r.custos_modelo["valor_residual_declarado"] == pytest.approx(-110.0)
    assert r.objetivo == pytest.approx(-97.5) and r.custo_operativo_previsto_R == pytest.approx(12.5)
    r = res(entrada4(e, declarado("energia_minima_declarada", emin={"syn-bess": 45.0})))
    assert r.aceito and E_N(r) == pytest.approx(45.0) and r.objetivo == pytest.approx(2.5)


def test_pwl_nao_convexo_exato_e_minimo_sobre_pontos():
    """Janela de 3 h, demanda 10 kW a 0,5 R$/kWh, banco 20 kWh (e0 = 10, P̄ = 10). V NÃO convexo:
    (0; 10), (5; 4), (10; 8), (20; 0). O despacho aceito satisfaz V̂ = interpolante EXATO em E(N) e o objetivo não
    excede o de nenhum ponto de quebra imposto isoladamente."""
    pts = ((0, 10.0), (5, 4.0), (10, 8.0), (20, 0.0))
    s = sinal(modos=(modo(pts),))
    r = res(entrada4(entrada(), termo(s)))
    assert r.aceito and r.auditoria_terminal.aceito
    En = E_N(r)
    assert r.custo_futuro_estimado_R == pytest.approx(interpolar_1d(s.modos[0].pontos, En), abs=1e-7)
    for E, V in pts:
        r1 = res(entrada4(entrada(), termo(sinal(modos=(modo(((E, V),)),)))))
        if r1.aceito:
            assert r.objetivo <= r1.objetivo + 1e-7


def test_envoltoria_2d_dois_bancos():
    bancos = (F.Banco(F.BESS, 10.0, 5.0, 5.0), F.Banco(F.BESS2, 10.0, 5.0, 5.0))
    lin = lambda x, y: 20.0 - 0.8 * x - 0.3 * y          # noqa: E731 — convexa (linear)
    pts = tuple((((x, y)), lin(x, y)) for x in (0.0, 5.0, 10.0) for y in (0.0, 5.0, 10.0))
    s = sinal(baterias=(F.BESS, F.BESS2), modos=(modo(pts, rep="envoltoria_convexa_nd"),))
    r = res(entrada4(entrada(bancos=bancos), termo(s)))
    assert r.aceito and r.auditoria_terminal.aceito
    x, y = E_N(r, F.BESS), E_N(r, F.BESS2)
    assert r.custo_futuro_estimado_R == pytest.approx(lin(x, y), abs=1e-6)
    # λ_1 = 0,8 > 0,5 + 0,01 (carregar da rede vale a pena) ⇒ banco 1 cheio; λ_2 = 0,3 < 0,5 − 0,01 ⇒ banco 2 vazio
    assert x == pytest.approx(10.0, abs=1e-6) and y == pytest.approx(0.0, abs=1e-6)


def test_selecao_de_modo_pemfc_e_memoria():
    """PEMFC desligada há 10 h (T_on = 3 h ⇒ U = 3 = N). Modo LIGADO na fronteira muito mais barato ⇒ a única forma é
    partir em t = 0 (cumprir_na_janela proíbe partida com t + U > N): u = (1, 1, 1), obrigação residual 0."""
    e = entrada(pemfc=F.Pemfc())
    s = sinal(geradores=(F.FC,), modos=(modo(((0, 500.0), (20, 490.0)), geradores=(ger(ligado=False),)),
                                        modo(((0, 30.0), (20, 20.0)), i=1, geradores=(ger(ligado=True),))))
    r = res(entrada4(e, termo(s)))
    assert r.aceito and r.termo_terminal["modo"] == 1
    assert [round(v) for v in r.despacho["geradores"][F.FC]["u"]] == [1, 1, 1]
    assert dict(r.obrigacoes_residuais_s) == {}
    # PEMFC indisponível no último intervalo: só o modo desligado é alcançável
    e2 = entrada(pemfc=F.Pemfc(), a_fc_prev=(1.0, 1.0, 0.0))
    r2 = res(entrada4(e2, termo(s)))
    assert r2.aceito and r2.termo_terminal["modo"] == 0


def test_local_dominio_e_referencias():
    loc = sinal(tipo="valor_marginal_local", modos=(modo(((10, 30.0),), rep="linear_local", dom=((8.0,), (12.0,))),),
                sens=sens(E0=10.0, d=2.0, V0=30.0, lam=5.0))
    r = res(entrada4(entrada(), termo(loc)))
    assert r.aceito and 8.0 - 1e-7 <= E_N(r) <= 12.0 + 1e-7
    assert E_N(r) == pytest.approx(12.0)           # λ = 5 > custo de carregar da rede (0,5 + 0,01)
    dura = sinal(tipo="referencia_energia_dura", modos=(), referencia=ref((15.0,)))
    r = res(entrada4(entrada(), termo(dura)))
    assert r.aceito and E_N(r) >= 15.0 - 1e-7 and "custo_futuro_estimado" not in r.custos_modelo
    branda = sinal(tipo="referencia_energia_branda", modos=(), referencia=ref((15.0,)), rho=0.1)
    r = res(entrada4(entrada(), termo(branda)))
    # ρ = 0,1 < 0,5: a penalidade não compensa carregar; o banco é DESCARREGADO (dentro da janela vale 0,49)
    assert r.aceito and r.custo_futuro_estimado_R == pytest.approx(0.1 * max(0.0, 15.0 - E_N(r)))


def test_h11_regiao_invalida_inalcancavel_e_inviavel():
    """e0 = 0, carga máxima 5 kW em 3 h ⇒ E(N) <= 15: domínio [18, 20] do sinal é inalcançável ⇒ INVIÁVEL (sem
    despacho, sem plano), nunca recorte."""
    e = entrada(bancos=(F.Banco(C=20.0, e0=0.0, pmax=10.0, pcmax=5.0),))
    s = sinal(modos=(modo(((18, 5.0), (20, 4.0))),))
    r = res(entrada4(e, termo(s)))
    assert not r.aceito and r.classificacao == "inviavel" and r.despacho is None


def test_h16_adulteracao_pos_solver_rejeitada():
    s = sinal(modos=(modo(((0, 35.0), (10, 30.0), (20, 25.0))),))
    e4 = entrada4(entrada(), termo(s))

    def theta(cr, ct):
        return cr, replace(ct, termo_reportado={CH: ct.termo_reportado[CH] - 1.0})

    def energia(cr, ct):
        b = dict(ct.baterias)
        b[F.BESS] = {**b[F.BESS], "e": b[F.BESS]["e"][:-1] + (b[F.BESS]["e"][-1] + 1.0,)}
        return cr, replace(ct, baterias=b)

    def total(cr, ct):
        return cr, replace(ct, total_reportado=ct.total_reportado - 0.5)
    for f in (theta, energia, total):
        r = resolver_3c4(e4, CONFIG_ANALITICA, _adulterar=f)
        assert not r.aceito and r.estado_despacho == "rejeitado_auditoria"


def test_plano_pela_visao_nucleo_e_recusas():
    e4 = entrada4(entrada(), termo(sinal()))
    r = res(e4)
    v = visao_nucleo_3c3(r, e4)
    assert v.versao_formulacao == "v1.1-3C-3" and v.perfil_resolucao == "v1.1-3C-4" and v.resultado_3c4 is r
    p, pr = plano_de_resultado_3c4(v, e4, indice_fronteira_inicial=0)
    assert p.hash_entrada == v.hash_entrada and pr.hash_entrada_3c3 == v.hash_entrada
    with pytest.raises(ContratoInvalido):
        plano_de_resultado_3c3(r, e4.rede, indice_fronteira_inicial=0)       # o resultado 3C-4 não passa por 3C-3
    with pytest.raises(ContratoInvalido):
        plano_de_resultado_3c4(replace(v, despacho=dict(v.despacho)), e4, indice_fronteira_inicial=0)
    outro = entrada4(entrada(), termo(sinal(modos=(modo(((0, 36.0), (20, 25.0))),))))
    with pytest.raises(ContratoInvalido):
        plano_de_resultado_3c4(v, outro, indice_fronteira_inicial=0)
    with pytest.raises(ContratoInvalido):
        visao_nucleo_3c3(r, outro)


def test_resolvedores_historicos_recusam_entrada_3c4():
    from ems_v2.milp.solver_3c1 import resolver_3c1
    e4 = entrada4(entrada(), termo(sinal()))
    assert resolver_3c3(e4, CONFIG_ANALITICA).classificacao == "bloqueado_validacao"
    assert resolver_3c1(e4, CONFIG_ANALITICA).classificacao == "bloqueado_validacao"
    assert resolver_3c4(e4.rede, CONFIG_ANALITICA).classificacao == "bloqueado_validacao"
