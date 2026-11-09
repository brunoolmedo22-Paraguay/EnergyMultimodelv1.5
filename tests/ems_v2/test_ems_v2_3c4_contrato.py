"""Piso 3C-4 — contratos (termo terminal, sinal, entrada hierárquica, planejador) e avaliação exata. SEM solver.

Sintético/algébrico: não é validação física. Cobre as rejeições exigidas pelo MPC (H11/H16 estruturais): outra
microrrede, outra fronteira/janela (caducidade), não causal, não finito, incompleto, fora do domínio, memória
incompatível, selo adulterado, unidades/convenção, e as regras do planejador (H_L > H_S, H_L <= H_f, sem padrão).
"""
from __future__ import annotations

import math
from dataclasses import replace

import pytest

from ems_v2 import fixtures_3c4 as F
from ems_v2.compromisso.contrato import validar_entrada_3c1
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.hierarquia.contrato import (ParametroBateria, TermoTerminal3C4, entrada_3c4_de_json, hash_entrada_3c4,
                                        json_canonico_3c4, selar_sinal, validar_configuracao_planejador,
                                        validar_entrada_3c4, validar_sinal, validar_sinal_para_janela)
from ems_v2.hierarquia.planejador import rampa_inativa_na_fronteira
from ems_v2.hierarquia.valor import (avaliar_modo, convexidade_verificada_na_amostra, envoltoria_convexa, inclinacoes_1d,
                                     interpolar_1d, modos_compativeis, valor_termo_declarado)
from ems_v2.rede.contrato import hash_entrada_3c3, validar_entrada_3c3
from test_ems_v2_3c4_apoio import (H, MISSAO, entrada, entrada4, ger, instante, modo, ref, sens, sinal, termo)

pytestmark = pytest.mark.synthetic_algebraic


def cod(rel):
    return {c.codigo for c in (rel.constatacoes if hasattr(rel, "constatacoes") else rel) if c.severidade == "erro"}


# ------------------------------------------------------------------------------------------------ entrada
def test_entrada_valida_roundtrip_e_nucleo_intacto():
    e = entrada()
    e4 = entrada4(e, termo(sinal()))
    assert validar_entrada_3c4(e4).aceito
    assert hash_entrada_3c4(entrada_3c4_de_json(json_canonico_3c4(e4))) == hash_entrada_3c4(e4)
    assert hash_entrada_3c3(e4.rede) == hash_entrada_3c3(e)        # embrulho não altera o núcleo 3C-3
    assert not validar_entrada_3c3(e4).aceito                      # perfis históricos recusam o embrulho
    assert not validar_entrada_3c1(e4).aceito


def test_perfil_e_esquema_versionados():
    e4 = entrada4(entrada(), termo(sinal()))
    assert "formulacao_nao_3c4" in cod(validar_entrada_3c4(replace(e4, versao_formulacao="v1.1-3C-3")))
    assert "versao_esquema_3c4_incompativel" in cod(validar_entrada_3c4(replace(e4, versao_esquema_3c4=2)))


@pytest.mark.parametrize("tipo,kw,codigo", [
    ("nenhum_declarado", {"just": ""}, "termo_terminal_sem_justificativa"),
    ("valor_linear_declarado", {"lin": -1.0}, "termo_terminal_valor_invalido"),
    ("valor_linear_declarado", {"lin": float("nan")}, "termo_terminal_valor_invalido"),
    ("energia_minima_declarada", {"emin": 25.0}, "energia_minima_inalcancavel"),
    ("valor_linear_declarado", {"lin": 1.0, "uid": "outro"}, "termo_terminal_bancos_divergentes"),
    ("nenhum_declarado", {"lin": 1.0}, "termo_terminal_ambiguo"),
    ("sinal_valor_futuro", {}, "sinal_ausente"),
    ("inventado", {}, "termo_terminal_tipo_invalido"),
])
def test_termo_declarado_sem_padrao(tipo, kw, codigo):
    uid = kw.get("uid", F.BESS)
    lin = (ParametroBateria(uid, kw["lin"]),) if "lin" in kw else ()
    em = (ParametroBateria(uid, kw["emin"]),) if "emin" in kw else ()
    t = TermoTerminal3C4(tipo, lin, em, None, kw.get("just", "justificativa"), F.proc("t"))
    assert codigo in cod(validar_entrada_3c4(entrada4(entrada(), t)))


# ------------------------------------------------------------------------------------------------ sinal
def test_selo_adulterado_e_nao_finito():
    s = sinal()
    m = s.modos[0]
    s2 = replace(s, modos=(replace(m, pontos=(replace(m.pontos[0], valor_R=1.0),) + m.pontos[1:]),))
    assert "sinal_adulterado" in cod(validar_sinal(s2))
    s3 = replace(s, modos=(replace(m, pontos=(replace(m.pontos[0], valor_R=math.nan),) + m.pontos[1:]),))
    c3 = cod(validar_sinal(s3))
    assert "sinal_adulterado" in c3 and "ponto_valor_invalido" in c3     # NaN não é serializável nem finito


@pytest.mark.parametrize("mut,codigo", [
    (lambda s: replace(s, unidade_valor="USD"), "sinal_unidade_ou_convencao_divergente"),
    (lambda s: replace(s, convencao="lambda = dV/dE"), "sinal_unidade_ou_convencao_divergente"),
    (lambda s: replace(s, perfil="v1.1-3C-3"), "sinal_perfil_incompativel"),
    (lambda s: replace(s, instante_emissao_utc=instante(2)), "sinal_nao_causal"),
    (lambda s: replace(s, intervalos_cauda=3), "sinal_horizonte_incoerente"),
    (lambda s: replace(s, tipo="penalidade_soc"), "sinal_tipo_invalido"),
])
def test_sinal_estrutura(mut, codigo):
    assert codigo in cod(validar_sinal(selar_sinal(mut(sinal()))))


@pytest.mark.parametrize("kw,codigo", [
    (dict(modos=(modo(((0, 35.0), (20, 25.0), (10, 30.0))),)), "pontos_nao_crescentes"),
    (dict(modos=(modo(((0, 35.0), (30, 25.0))),)), "dominio_fora_dos_limites_fisicos"),
    (dict(modos=(modo(((5, 35.0), (20, 25.0)), dom=((0.0,), (20.0,))),)), "dominio_nao_coberto"),
    (dict(microrrede="outra-mg"), "sinal_de_outra_microrrede"),
    (dict(N=4), "sinal_de_outra_fronteira"),
    (dict(baterias=("outro-banco",)), "sinal_recursos_divergentes"),
    (dict(estado="indisponivel"), "sinal_valor_futuro_indisponivel"),
    (dict(modos=(modo(((0, 3.0), (20, 1.0)), rep="envoltoria_convexa_nd"),)), "representacao_incompativel"),
    (dict(modos=(modo((((0, 1), 3.0), ((20, 0), 1.0)), rep="envoltoria_convexa_nd"),)), "modo_dominio_invalido"),
    (dict(tipo="valor_marginal_local", modos=(modo(((10, 30.0),), rep="linear_local", dom=((8.0,), (12.0,))),)),
     "sinal_local_invalido"),
    (dict(tipo="referencia_energia_branda", modos=(), referencia=ref()), "penalidade_branda_invalida"),
    (dict(tipo="referencia_energia_dura", modos=(), referencia=ref((25.0,))), "referencia_inalcancavel"),
    (dict(modos=()), "sinal_sem_modos"),
])
def test_sinal_contra_entrada(kw, codigo):
    e4 = entrada4(entrada(), termo(sinal(**kw)))
    assert codigo in cod(validar_entrada_3c4(e4))


def test_sinal_local_e_referencias_validos():
    for s in (sinal(tipo="valor_marginal_local", modos=(modo(((10, 30.0),), rep="linear_local",
                                                             dom=((8.0,), (12.0,))),), sens=sens()),
              sinal(tipo="referencia_energia_dura", modos=(), referencia=ref()),
              sinal(tipo="referencia_energia_branda", modos=(), referencia=ref(), rho=1.0)):
        assert validar_entrada_3c4(entrada4(entrada(), termo(s))).aceito, cod(validar_entrada_3c4(entrada4(entrada(),
                                                                                                         termo(s))))


def test_dois_bancos_exige_convexidade_verificada_na_amostra():
    bancos = (F.Banco(F.BESS, 10.0, 5.0, 5.0), F.Banco(F.BESS2, 10.0, 5.0, 5.0))
    e = entrada(bancos=bancos)
    pts = tuple((((x, y)), 10.0 - 0.5 * x - 0.3 * y) for x in (0.0, 10.0) for y in (0.0, 10.0))
    ok = sinal(baterias=(F.BESS, F.BESS2), modos=(modo(pts, rep="envoltoria_convexa_nd", conv=True),))
    assert validar_entrada_3c4(entrada4(e, termo(ok))).aceito
    nao = sinal(baterias=(F.BESS, F.BESS2), modos=(modo(pts, rep="envoltoria_convexa_nd", conv=False),))
    assert "convexidade_nao_verificada" in cod(validar_entrada_3c4(entrada4(e, termo(nao))))


# ------------------------------------------------------------------------------------------------ modos × memória
def _e_pemfc(**kw):
    return entrada(pemfc=F.Pemfc(**kw))


def test_modos_memoria_permanencia_e_obrigacao_herdada():
    e = _e_pemfc()
    ok = sinal(geradores=(F.FC,), modos=(modo(((0, 30.0), (20, 20.0)), geradores=(ger(ligado=False),)),
                                         modo(((0, 25.0), (20, 15.0)), i=1, geradores=(ger(ligado=True),))))
    assert validar_entrada_3c4(entrada4(e, termo(ok))).aceito
    # política de permanência que deixa obrigação residual ⇒ memória terminal ≠ a do modo
    e_res = replace(e, compromisso=replace(e.compromisso, politica_permanencia=replace(
        e.compromisso.politica_permanencia, tipo="obrigacao_residual_vinculante")))
    assert "permanencia_incompativel_com_sinal" in cod(validar_entrada_3c4(entrada4(e_res, termo(ok))))
    # obrigação HERDADA além da janela (ligada há 0 s, T_on = 3 h, N = 3 h ⇒ obrigação na fronteira = 0) —
    # com T_on = 5 h a obrigação na fronteira é 2 h = 7200 s e só um modo FIXO é compatível
    e5 = _e_pemfc(ligado=True, p0=10.0, tempo_s=0, Ton_min=300.0)
    errado = sinal(geradores=(F.FC,), modos=(modo(((0, 30.0), (20, 20.0)), geradores=(ger(ligado=True),)),))
    assert "modo_memoria_incompativel" in cod(validar_entrada_3c4(entrada4(e5, termo(errado))))
    certo = sinal(geradores=(F.FC,), modos=(modo(((0, 30.0), (20, 20.0)), geradores=(ger(ligado=True, obrig=7200),)),))
    assert validar_entrada_3c4(entrada4(e5, termo(certo))).aceito
    falso = sinal(geradores=(F.FC,), modos=(modo(((0, 30.0), (20, 20.0)), geradores=(ger(ligado=True, obrig=3600),)),))
    assert "modo_memoria_incompativel" in cod(validar_entrada_3c4(entrada4(e5, termo(falso))))


def test_rampa_inativa_lema():
    from ems_v2.compromisso.contrato import discretizar
    d = discretizar(_e_pemfc().compromisso)[F.FC]              # RΔ = 60 kW ≥ 20 − 5
    assert rampa_inativa_na_fronteira(d)
    d2 = discretizar(_e_pemfc(R=0.1).compromisso)[F.FC]        # RΔ = 6 kW < 15
    assert not rampa_inativa_na_fronteira(d2)


# ------------------------------------------------------------------------------------------------ janela (MPC)
def _jan(s, **kw):
    a = dict(missao_uid=MISSAO, indice_janela=0, k=0, instante_utc=instante(0), fronteira=3, hash_modelo_rede=H,
             hash_configuracao=H, hash_instantaneo_emissao=H)
    a.update(kw)
    return cod(validar_sinal_para_janela(s, **a))


def test_sinal_para_janela_caducidade_e_causalidade():
    s = sinal()
    assert _jan(s) == set()
    assert "sinal_caducado" in _jan(s, indice_janela=1, k=1, instante_utc=instante(1), fronteira=4)
    assert "sinal_de_outra_fronteira" in _jan(s, fronteira=4)
    assert "sinal_de_outra_missao" in _jan(s, missao_uid="c" * 32)
    assert "sinal_nao_causal" in _jan(s, hash_instantaneo_emissao="d" * 64)
    assert "sinal_nao_causal" in _jan(s, hash_instantaneo_emissao=None)
    assert "sinal_de_outro_modelo" in _jan(s, hash_modelo_rede="e" * 64)
    assert "sinal_de_outra_configuracao" in _jan(s, hash_configuracao="f" * 64)


# ------------------------------------------------------------------------------------------------ planejador
def _cfg_mpc(N=3, H_f=12, perm="cumprir_na_janela"):
    return F.configuracao_mpc("contrato", F.h2_pico_futuro(), N, 1, H_f=H_f, perm_inter=perm)


@pytest.mark.parametrize("kw,mpc_kw,codigo", [
    (dict(H_L=3), {}, "horizonte_longo_nao_maior"),
    (dict(H_L=10), dict(H_f=8), "horizonte_longo_alem_da_previsao"),
    (dict(H_L=10, degradacao="ignorar"), {}, "degradacao_invalida"),
    (dict(H_L=10, tipo_sinal="valor_marginal_local"), {}, "delta_sensibilidade_invalido"),
    (dict(H_L=10, tipo_sinal="referencia_energia_branda"), {}, "penalidade_branda_invalida"),
    (dict(H_L=10, pontos=5, pontos_max=3), {}, "planejador_parametro_invalido"),
    (dict(H_L=10, tol_dom=0.0), {}, "planejador_parametro_invalido"),
    (dict(H_L=10, termo=TermoTerminal3C4("nenhum_declarado", (), (), None, "", F.proc("x"))), {},
     "termo_terminal_sem_justificativa"),
])
def test_configuracao_planejador_sem_padrao(kw, mpc_kw, codigo):
    c = F.configuracao_planejador(**kw)
    assert codigo in cod(validar_configuracao_planejador(c, _cfg_mpc(**mpc_kw), F.modelo(F.h2_pico_futuro())))


def test_planejador_exige_cumprir_na_janela_com_geradores():
    c = F.configuracao_planejador(H_L=10)
    m9 = F.modelo(F.h9_pemfc())
    assert "permanencia_incompativel_com_sinal" in cod(validar_configuracao_planejador(
        c, _cfg_mpc(perm="obrigacao_residual_vinculante"), m9))
    assert not cod(validar_configuracao_planejador(c, _cfg_mpc(), m9))


def test_controlador_recusa_configuracao_invalida():
    from ems_v2.hierarquia.experimentos import montar
    with pytest.raises(ContratoInvalido):
        montar(F.h2_pico_futuro(), "hier_pwl", H_L=3)          # H_L <= N


# ------------------------------------------------------------------------------------------------ avaliação exata
def test_interpolacao_1d_e_dominio():
    m = modo(((0, 10.0), (5, 4.0), (10, 8.0), (20, 0.0)))      # NÃO convexo (exato por segmentos)
    assert interpolar_1d(m.pontos, 2.5) == pytest.approx(7.0)
    assert interpolar_1d(m.pontos, 7.5) == pytest.approx(6.0)
    assert interpolar_1d(m.pontos, 20.0) == 0.0
    assert interpolar_1d(m.pontos, 20.5) is None and interpolar_1d(m.pontos, -0.5) is None
    assert inclinacoes_1d(m.pontos) == pytest.approx([-1.2, 0.8, -0.8])
    assert not convexidade_verificada_na_amostra(m.pontos, 1, 1e-9)[0]
    mc = modo(((0, 25.0), (10, 10.1), (20, 5.2)))
    assert convexidade_verificada_na_amostra(mc.pontos, 1, 1e-9)[0]


def test_envoltoria_convexa_2d_exata():
    lin = lambda x, y: 10.0 - 0.5 * x - 0.3 * y          # noqa: E731
    m = modo(tuple((((x, y)), lin(x, y)) for x in (0.0, 5.0, 10.0) for y in (0.0, 5.0, 10.0)),
             rep="envoltoria_convexa_nd")
    for p in ((2.5, 7.5), (0.0, 10.0), (9.0, 1.0)):
        assert envoltoria_convexa(m.pontos, p) == pytest.approx(lin(*p))
    assert envoltoria_convexa(m.pontos, (11.0, 0.0)) is None
    assert convexidade_verificada_na_amostra(m.pontos, 2, 1e-9)[0]
    bico = modo((((0.0, 0.0), 0.0), ((10.0, 0.0), 0.0), ((0.0, 10.0), 0.0), ((10.0, 10.0), 0.0), ((5.0, 5.0), 3.0)),
                rep="envoltoria_convexa_nd")
    ok, exc = convexidade_verificada_na_amostra(bico.pontos, 2, 1e-9)
    assert not ok and exc == pytest.approx(3.0)


def test_modos_compativeis_e_termos_declarados():
    s = sinal(geradores=(F.FC,), modos=(modo(((0, 1.0), (20, 0.0)), geradores=(ger(ligado=False),)),
                                        modo(((0, 1.0), (20, 0.0)), i=1, geradores=(ger(ligado=True, pfix=10.0),))))
    assert modos_compativeis(s, {F.FC: (True, 0, 10.0)}) == [1]
    assert modos_compativeis(s, {F.FC: (True, 0, 12.0)}) == []      # potência fixada divergente
    assert modos_compativeis(s, {F.FC: (True, 3600, 10.0)}) == []   # obrigação residual divergente
    assert avaliar_modo(s, s.modos[0], (10.0,)) == pytest.approx(0.5)
    t = TermoTerminal3C4("valor_linear_declarado", (ParametroBateria(F.BESS, 0.3),), (), None, "j", None)
    assert valor_termo_declarado(t, {F.BESS: 10.0}) == pytest.approx(-3.0)
    t2 = TermoTerminal3C4("energia_minima_declarada", (), (ParametroBateria(F.BESS, 5.0),), None, "j", None)
    assert valor_termo_declarado(t2, {F.BESS: 4.0}) is None
