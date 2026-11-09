"""Piso 3C-4 — auditor INDEPENDENTE do termo terminal (adversarial, SEM solver).

O auditor recalcula V̂ no estado terminal do candidato (energia e(N), memória terminal recalculada dos geradores) a
partir SÓ da entrada e do despacho: termo, total, domínio, modo e seleção alterados são rejeitados (H16).
"""
from __future__ import annotations

import pytest

from ems_v2 import fixtures_3c4 as F
from ems_v2.hierarquia.auditor import CandidatoTerminal3C4, auditar_terminal_3c4
from ems_v2.hierarquia.contrato import ParametroBateria, TermoTerminal3C4
from test_ems_v2_3c4_apoio import entrada, entrada4, ger, modo, ref, sinal, termo

pytestmark = pytest.mark.synthetic_algebraic
CH = "custo_futuro_estimado"


def cand(E_N=15.0, theta=None, total=None, u=None, p=None, selecao=None, chave=CH):
    ger_ = {} if u is None else {F.FC: {"u": tuple(u), "p": tuple(p)}}
    rep = {} if chave is None else {chave: theta}
    return CandidatoTerminal3C4({F.BESS: {"e": (10.0, 12.0, 14.0, E_N)}}, ger_, rep, total, selecao or {})


def cods(r):
    return {c.codigo for c in r.constatacoes}


S1 = sinal(modos=(modo(((0, 35.0), (10, 30.0), (20, 25.0))),))


def test_pwl_correto_aceito_e_alteracoes_rejeitadas():
    e4 = entrada4(entrada(), termo(S1))
    ok = auditar_terminal_3c4(e4, cand(15.0, 27.5, 12.5 + 27.5), 12.5)
    assert ok.aceito and ok.valor_recalculado_R == pytest.approx(27.5) and ok.modo == 0
    r = auditar_terminal_3c4(e4, cand(15.0, 27.0, 12.5 + 27.0), 12.5)
    assert not r.aceito and "termo_terminal_divergente" in cods(r)
    r = auditar_terminal_3c4(e4, cand(15.0, 27.5, 41.0), 12.5)
    assert not r.aceito and "objetivo_total_divergente" in cods(r)
    r = auditar_terminal_3c4(e4, cand(15.0, 27.5, 40.0), None)
    assert not r.aceito and "total_3c3_nao_reconstruido" in cods(r)
    r = auditar_terminal_3c4(e4, cand(15.0, None, 40.0, chave=None), 12.5)
    assert not r.aceito and "termo_terminal_ausente" in cods(r)
    r = auditar_terminal_3c4(e4, CandidatoTerminal3C4({F.BESS: {"e": (10.0, 12.0, 14.0, 15.0)}}, {},
                                                      {CH: 27.5, "valor_residual_declarado": -1.0}, 39.0, {}), 12.5)
    assert not r.aceito and "termo_terminal_inesperado" in cods(r)
    r = auditar_terminal_3c4(e4, cand(15.0, 27.5, 40.0, selecao={"s": (0.6,)}), 12.5)
    assert not r.aceito and "selecao_terminal_nao_inteira" in cods(r)
    r = auditar_terminal_3c4(e4, CandidatoTerminal3C4({F.BESS: {"e": (10.0, 12.0, float("nan"))}}, {}, {CH: 27.5},
                                                      40.0, {}), 12.5)
    assert not r.aceito and "energia_terminal_ausente" in cods(r)


def test_fora_do_dominio_de_validade():
    s = sinal(modos=(modo(((15, 27.5), (20, 25.0))),))          # domínio [15, 20] (p. ex. reserva de factibilidade)
    e4 = entrada4(entrada(), termo(s))
    r = auditar_terminal_3c4(e4, cand(12.0, 29.0, 41.5), 12.5)
    assert not r.aceito and "estado_terminal_fora_do_dominio" in cods(r)


def test_modo_e_memoria_terminal_do_gerador():
    e = entrada(pemfc=F.Pemfc())                                # OFF há 10 h; T_on 3 h ⇒ U = 3; Δ = 1 h, N = 3
    s = sinal(geradores=(F.FC,), modos=(modo(((0, 40.0), (20, 30.0)), geradores=(ger(ligado=False),)),
                                        modo(((0, 30.0), (20, 20.0)), i=1, geradores=(ger(ligado=True),))))
    e4 = entrada4(e, termo(s))
    r = auditar_terminal_3c4(e4, cand(10.0, 25.0, 35.0, u=(1, 1, 1), p=(5.0, 5.0, 5.0), selecao={"s": (0.0, 1.0)}), 10.0)
    assert r.aceito and r.modo == 1, cods(r)
    r = auditar_terminal_3c4(e4, cand(10.0, 35.0, 45.0, u=(0, 0, 0), p=(0.0, 0.0, 0.0), selecao={"s": (1.0, 0.0)}), 10.0)
    assert r.aceito and r.modo == 0
    # V do modo LIGADO reportado com a unidade desligada (benefício de commitment atribuído ao banco) ⇒ rejeitado
    r = auditar_terminal_3c4(e4, cand(10.0, 25.0, 35.0, u=(0, 0, 0), p=(0.0, 0.0, 0.0), selecao={"s": (0.0, 1.0)}), 10.0)
    assert not r.aceito and {"termo_terminal_divergente", "modo_reportado_divergente"} <= cods(r)
    # partida no último intervalo: obrigação residual 2 h na fronteira ⇒ nenhum modo do sinal (residual 0) é compatível
    r = auditar_terminal_3c4(e4, cand(10.0, 25.0, 35.0, u=(0, 0, 1), p=(0.0, 0.0, 5.0)), 10.0)
    assert not r.aceito and "estado_terminal_fora_dos_modos" in cods(r)


def test_referencias_e_termos_declarados():
    dura = entrada4(entrada(), termo(sinal(tipo="referencia_energia_dura", modos=(), referencia=ref((14.0,)))))
    assert auditar_terminal_3c4(dura, cand(15.0, None, 12.5, chave=None), 12.5).aceito
    r = auditar_terminal_3c4(dura, cand(13.0, None, 12.5, chave=None), 12.5)
    assert not r.aceito and "referencia_terminal_violada" in cods(r)
    branda = entrada4(entrada(), termo(sinal(tipo="referencia_energia_branda", modos=(), referencia=ref((18.0,)),
                                             rho=2.0)))
    assert auditar_terminal_3c4(branda, cand(15.0, 6.0, 18.5), 12.5).aceito
    assert not auditar_terminal_3c4(branda, cand(15.0, 5.0, 17.5), 12.5).aceito
    lin = entrada4(entrada(), TermoTerminal3C4("valor_linear_declarado", (ParametroBateria(F.BESS, 0.4),), (), None,
                                               "valor residual declarado", F.proc("t")))
    assert auditar_terminal_3c4(lin, cand(15.0, -6.0, 6.5, chave="valor_residual_declarado"), 12.5).aceito
    em = entrada4(entrada(), TermoTerminal3C4("energia_minima_declarada", (), (ParametroBateria(F.BESS, 16.0),), None,
                                              "energia mínima declarada", F.proc("t")))
    r = auditar_terminal_3c4(em, cand(15.0, None, 12.5, chave=None), 12.5)
    assert not r.aceito and "energia_minima_violada" in cods(r)


def test_sinal_adulterado_na_entrada_e_entrada_invalida():
    from dataclasses import replace
    m = S1.modos[0]
    s2 = replace(S1, modos=(replace(m, pontos=(replace(m.pontos[0], valor_R=1.0),) + m.pontos[1:]),))
    r = auditar_terminal_3c4(entrada4(entrada(), termo(s2)), cand(15.0, 27.5, 40.0), 12.5)
    assert not r.aceito and "sinal_adulterado" in cods(r)
