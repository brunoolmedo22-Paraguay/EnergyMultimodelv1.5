"""Piso 3C-2 — previsão por janela: protocolo causal e provedores sintéticos (SEM solver)."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

import pytest

from ems_v2 import fixtures_3c2 as F
from ems_v2.mpc.observacoes import LivroObservacoes, Observacao
from ems_v2.mpc.previsao import PedidoPrevisao, chaves_de_previsao, validar_previsao_janela
from ems_v2.mpc.provedores import ProvedorCorrecaoPorObservacao, ProvedorOraculoAblacao, ProvedorTabelaDeclarada
from ems_v2.mpc.relogio import janela_em

pytestmark = pytest.mark.synthetic_algebraic
T0 = datetime.fromisoformat(F.INICIO)
D = timedelta(minutes=15)
MOD = F.modelo("3C2", 8, F.L_E2, F.PV_PRIOR_E2)
CFG = F.configuracao("prev", 8, 4, 2)


def livro():
    rec = {}
    for c in chaves_de_previsao(MOD):
        rec.setdefault(c.recurso_uid, set()).add(c.grandeza)
    return LivroObservacoes(CFG.identidade.missao_uid, CFG.identidade.microrrede_uid,
                            {k: tuple(sorted(v)) for k, v in rec.items()})


def pedido(k: int, lv: LivroObservacoes):
    jan = janela_em(CFG, k // 2, k)
    lv.selar_corte(jan.inicio_utc)
    return jan, PedidoPrevisao(CFG.identidade.missao_uid, CFG.identidade.microrrede_uid, jan.indice_janela, k,
                               jan.inicio_utc, 900, jan.N_k, chaves_de_previsao(MOD), lv.instantaneo(jan.inicio_utc))


def prov_tabela():
    return ProvedorTabelaDeclarada("prov-t", F.tabela("3C2", F.L_E2, F.PV_PRIOR_E2), F.proc("p", fonte=F.FONTE_PREV),
                                   bases=F.BASES)


def prov_corr():
    return ProvedorCorrecaoPorObservacao("prov-c", F.tabela("3C2", F.L_E2, F.PV_PRIOR_E2),
                                         F.proc("p", fonte=F.FONTE_PREV), corrigidas=[(F.FV, "potencia")], bases=F.BASES)


def val(prev, jan, ped, nat="sintetico_conhecido", rot="causal", **kw):
    return {c.codigo for c in validar_previsao_janela(prev, ped, jan.malha(CFG.malha), provedor_id="prov-t",
                                                      provedor_natureza=nat, rotulo_informacao=rot, **kw)}


def test_chaves_por_uid_exigidas_pela_entrada():
    assert [(c.recurso_uid, c.grandeza, c.base_potencial) for c in chaves_de_previsao(MOD)] == [
        (F.BESS, "disponibilidade", None), (F.DEM, "potencia", None), (F.FC, "disponibilidade", None),
        (F.FV, "disponibilidade", None), (F.FV, "potencia", "antes_da_disponibilidade")]


def test_previsao_valida_vinculada_ao_instantaneo():
    lv = livro()
    jan, ped = pedido(2, lv)
    p = prov_tabela().emitir(ped)
    assert val(p, jan, ped) == set()
    assert p.procedencia.sha256 == ped.instantaneo.hash and p.emissao_utc == jan.inicio_utc
    assert all(len(s.serie.valores) == 4 and s.serie.inicio_utc == jan.inicio_utc for s in p.series)


def test_previsao_emitida_tarde_serie_apos_conjunto_e_sem_vinculo():
    lv = livro()
    jan, ped = pedido(2, lv)
    p = prov_tabela().emitir(ped)
    tarde = dataclasses.replace(p, emissao_utc=(T0 + 2 * D + timedelta(seconds=1)).isoformat())
    assert "previsao_nao_causal" in val(tarde, jan, ped)
    s0 = p.series[0]
    s_tarde = dataclasses.replace(s0, serie=dataclasses.replace(s0.serie, emissao_utc=(T0 + 3 * D).isoformat()))
    cs = val(dataclasses.replace(p, series=(s_tarde,) + p.series[1:]), jan, ped)
    assert {"serie_emitida_depois_do_conjunto", "previsao_nao_causal"} & cs
    sem = dataclasses.replace(p, procedencia=dataclasses.replace(p.procedencia, sha256="0" * 64))
    assert "previsao_sem_vinculo_informacional" in val(sem, jan, ped)


def test_cobertura_resolucao_e_uids():
    lv = livro()
    jan, ped = pedido(2, lv)
    p = prov_tabela().emitir(ped)
    s0 = p.series[0]
    curta = dataclasses.replace(s0, serie=dataclasses.replace(s0.serie, valores=s0.serie.valores[:3]))
    assert "cobertura_insuficiente" in val(dataclasses.replace(p, series=(curta,) + p.series[1:]), jan, ped)
    res = dataclasses.replace(s0, serie=dataclasses.replace(s0.serie, passo_s=300))
    assert "resolucao_incompativel" in val(dataclasses.replace(p, series=(res,) + p.series[1:]), jan, ped)
    assert "previsao_chave_ausente" in val(dataclasses.replace(p, series=p.series[1:]), jan, ped)
    alheia = dataclasses.replace(s0, uid="syn-outro")
    assert "previsao_chave_nao_solicitada" in val(dataclasses.replace(p, series=p.series + (alheia,)), jan, ped)


def test_oraculo_so_em_ablacao_e_independencia_do_provedor():
    lv = livro()
    jan, ped = pedido(0, lv)
    ver = F.verdade("3C2", F.L_E2, F.PV_REAL_E2)
    o = ProvedorOraculoAblacao("orac", ver, "ablação de teste", F.proc("o"), bases=F.BASES).emitir(ped)
    assert "oraculo_em_missao_causal" in val(o, jan, ped, nat="oraculo_ablacao")
    assert val(o, jan, ped, nat="oraculo_ablacao", rot="ablacao_oraculo") == set()
    p = prov_tabela().emitir(ped)
    assert "ablacao_sem_oraculo_declarado" in val(p, jan, ped, rot="ablacao_oraculo")
    assert "provedor_nao_independente" in val(p, jan, ped, identificadores_verdade=("prov-t",))
    assert "provedor_nao_independente" in val(p, jan, ped, fontes_verdade=(F.FONTE_PREV,))


def test_provedor_reemite_quando_a_informacao_muda_e_so_com_o_instantaneo():
    """A correção usa SÓ o instantâneo: mesmo instantâneo ⇒ mesma previsão; observação nova ⇒ nova emissão."""
    lv = livro()
    jan, ped = pedido(0, lv)
    pc = prov_corr()
    a, a2 = pc.emitir(ped), pc.emitir(ped)
    assert a == a2 and a.serie(F.FV, "potencia").serie.valores == (10.0,) * 4
    for g, v in ((0, 10.0), (1, 25.0)):
        lv.registrar(Observacao(f"o{g}", "c", g, CFG.identidade.microrrede_uid, F.FV, "potencia", "kW",
                                (T0 + g * D).isoformat(), (T0 + (g + 1) * D).isoformat(), v,
                                (T0 + (g + 1) * D).isoformat(), F.proc("obs")))
    jan2, ped2 = pedido(2, lv)
    b = pc.emitir(ped2)
    assert b.serie(F.FV, "potencia").serie.valores == (25.0,) * 4           # δ = 25 − 10 pela última observação
    assert b.serie(F.FV, "potencia").serie.emissao_utc == jan2.inicio_utc
    assert b.serie(F.DEM, "potencia").serie.valores == (30.0,) * 4           # chave não corrigida: perfil declarado
    assert val(b, jan2, ped2, nat="sintetico_reemitido_por_observacao") == set()
    assert pc.impressao() != prov_tabela().impressao()


def test_previsao_reemitida_em_cada_janela_tem_hash_proprio():
    from ems_v2.ponte.cenario import hash_previsao
    lv = livro()
    hs = set()
    for k in (0, 2, 4, 6):
        jan, ped = pedido(k, lv)
        hs.add(hash_previsao(prov_tabela().emitir(ped)))
    assert len(hs) == 4
