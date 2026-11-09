"""Piso 3C-2 — K6: livro de observações APPEND-ONLY e instantâneo informacional causal (SEM solver)."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

import pytest

from ems_v2 import fixtures_3c2 as F
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.mpc.observacoes import (LivroObservacoes, Observacao, instantaneo_de_prefixo, realizacao_de_instantaneo,
                                    verificar_cadeia_livro)
from ems_v2.ponte.canonico import de_json, json_canonico
from ems_v2.ponte.execucao import limite_observado
from ems_v2.mpc.observacoes import DocumentoLivro

pytestmark = pytest.mark.synthetic_algebraic
MG = "syn-microrrede-fixture"
MISSAO = F.missao_uid("k6")
T0 = datetime.fromisoformat(F.INICIO)
D = timedelta(minutes=15)


def t(i, s=0):
    return (T0 + i * D + timedelta(seconds=s)).isoformat()


def obs(g, uid=F.DEM, gr="potencia", valor=30.0, *, rec=0, seq=None, ev=None, rev=0, revisa=None, mg=MG, un=None):
    _obs_seq[0] += 1
    return Observacao(ev or f"c:g{g}:{uid}:{gr}:r{rev}", "canal-k6", _obs_seq[0] if seq is None else seq, mg, uid, gr,
                      un or {"potencia": "kW", "disponibilidade": "1"}[gr], t(g), t(g + 1), valor, t(g + 1, rec),
                      F.proc("k6"), rev, revisa)


_obs_seq = [0]


def livro():
    _obs_seq[0] = 0
    return LivroObservacoes(MISSAO, MG, {F.DEM: ("potencia",), F.FV: ("disponibilidade", "potencia")})


def test_aceita_e_instantaneo_e_prefixo_por_recepcao():
    lv = livro()
    a = lv.registrar(obs(0, valor=30.0))
    b = lv.registrar(obs(1, valor=31.0, rec=600))           # recebida 10 min após o fim do intervalo 1
    assert (a.classificacao, b.classificacao, b.atraso_s) == ("aceita", "aceita", 600)
    i2 = lv.instantaneo(t(2))
    assert i2.n_entradas == 1 and i2.valor(F.DEM, "potencia", t(0)).valor == 30.0
    assert i2.valor(F.DEM, "potencia", t(1)) is None         # ainda não recebida em τ_2: AUSENTE (não zero)
    i3 = lv.instantaneo(t(3))
    assert i3.n_entradas == 2 and i3.valor(F.DEM, "potencia", t(1)).valor == 31.0
    assert i2.hash != i3.hash and lv.instantaneo(t(2)) == i2  # determinístico


def test_invalidas_outra_microrrede_recurso_e_informacao_futura():
    lv = livro()
    c = [lv.registrar(x).classificacao for x in (
        obs(0, valor=float("nan")), obs(0, valor=-1.0), obs(0, uid=F.FV, gr="disponibilidade", valor=0.5),
        obs(0, un="W"), obs(0, mg="syn-outra"), obs(0, uid="syn-desconhecido"))]
    assert c == ["rejeitada_invalida"] * 4 + ["rejeitada_outra_microrrede", "rejeitada_recurso_desconhecido"]
    assert lv.instantaneo(t(5)).valores == ()                  # nada rejeitado entra no conjunto de informação
    lv2 = livro()                                              # recebida ANTES do fim do intervalo (livro novo)
    e = lv2.registrar(dataclasses.replace(obs(1), recebido_utc=t(1, 60)))
    assert e.classificacao == "rejeitada_invalida" and "informação futura" in e.detalhe


def test_duplicatas_conflito_de_evento_e_sequencia():
    lv = livro()
    o = obs(0)
    assert lv.registrar(o).classificacao == "aceita"
    assert lv.registrar(o).classificacao == "duplicata_identica"            # retransmissão
    assert lv.registrar(dataclasses.replace(o, valor=99.0)).classificacao == "rejeitada_conflito_evento_uid"
    o2 = obs(1, seq=o.sequencia, ev="e-o2")                                  # outro evento, mesma sequência
    assert lv.registrar(o2).classificacao == "rejeitada_conflito_sequencia"
    assert lv.registrar(dataclasses.replace(o2, sequencia=99)).classificacao == "rejeitada_conflito_evento_uid"
    o3 = obs(1, seq=10, ev="e-o3")
    e3 = lv.registrar(o3)
    assert e3.classificacao == "aceita" and "lacuna" in e3.detalhe
    o4 = obs(2, seq=5, ev="e-o4")                                             # reordenada: aceita, sinalizada
    assert lv.registrar(o4).classificacao == "aceita_fora_de_sequencia"
    assert lv.instantaneo(t(5)).valor(F.DEM, "potencia", t(2)).valor == 30.0


def test_revisoes_append_only_conflitos_e_resolucao():
    lv = livro()
    o = obs(0, valor=30.0)
    lv.registrar(o)
    r1 = obs(0, valor=32.0, rec=300, rev=1, revisa=o.evento_uid)
    assert lv.registrar(r1).classificacao == "aceita_revisao"
    assert lv.registrar(obs(0, valor=33.0, rec=301, rev=1, revisa=o.evento_uid, ev="x-r1b")).classificacao == \
        "rejeitada_conflito_revisao"                                          # mesmo número de revisão
    assert lv.registrar(obs(0, valor=33.0, rec=302, rev=3, revisa=o.evento_uid, ev="x-r3")).classificacao == \
        "rejeitada_conflito_revisao"                                          # salto
    assert lv.registrar(obs(1, valor=1.0, rec=303, rev=1, revisa="inexistente", ev="x-sem")).classificacao == \
        "rejeitada_revisao_sem_original"
    assert lv.instantaneo(t(1, 200)).valor(F.DEM, "potencia", t(0)).valor == 30.0   # antes da revisão
    assert lv.instantaneo(t(1, 300)).valor(F.DEM, "potencia", t(0)).valor == 32.0   # depois: maior revisão
    assert lv.entradas[0].observacao.valor == 30.0                                    # original preservado
    # conflito entre ORIGINAIS ⇒ chave conflitante (sem valor) até revisão explícita
    a = obs(3, valor=10.0, rec=10)
    lv.registrar(a)
    assert lv.registrar(obs(3, valor=10.0, rec=11, ev="dup-sem")).classificacao == "duplicata_semantica"
    assert lv.registrar(obs(3, valor=12.0, rec=12, ev="outro-orig")).classificacao == "aceita_original_conflitante"
    v = lv.instantaneo(t(5)).valor(F.DEM, "potencia", t(3))
    assert v.estado == "conflitante" and v.valor is None
    lv.registrar(obs(3, valor=11.0, rec=1000, rev=1, revisa=a.evento_uid, ev="resolve"))
    assert lv.instantaneo(t(6)).valor(F.DEM, "potencia", t(3)).valor == 11.0


def test_corte_selado_e_recepcao_retroativa_recusada():
    lv = livro()
    lv.registrar(obs(0))
    lv.selar_corte(t(2))
    i = lv.instantaneo(t(2))
    tardia = obs(1, rec=0, ev="e-tardia")                     # recebida exatamente em τ_2 (= corte já selado)
    assert lv.registrar(tardia).classificacao == "quarentena_recepcao_retroativa"            # C-01: quarentena
    assert lv.instantaneo(t(2)).valores == i.valores           # o conjunto da decisão não muda
    ok = obs(1, rec=60, ev="e-ok")
    e = lv.registrar(ok)
    assert e.classificacao == "aceita" and e.tardia_apos_corte == t(2)       # chegou depois da decisão
    with pytest.raises(ContratoInvalido):
        lv.selar_corte(t(1))                                   # corte retroativo
    with pytest.raises(ContratoInvalido):
        lv.selar_corte(t(2, 30))                              # recepção já registrada depois deste corte


def test_realizacao_de_instantaneo_faltantes_e_barreira_c02():
    lv = livro()
    for g in (0, 1, 2):
        lv.registrar(obs(g, valor=30.0))
        if g < 2:                                              # FV (potência) de g = 2 nunca chega
            lv.registrar(obs(g, uid=F.FV, gr="potencia", valor=10.0))
        lv.registrar(obs(g, uid=F.FV, gr="disponibilidade", valor=1.0, rec=1))
    i = lv.instantaneo(t(5))
    ch = ((F.DEM, "potencia"), (F.FV, "disponibilidade"), (F.FV, "potencia"))
    ro = realizacao_de_instantaneo(i, ch, t(0), 4, 900)
    assert ro.intervalos_observados == 2 and ro.realizacao.modo == "incremental_online"
    assert ro.realizacao.observado_ate_utc == t(2)
    assert {(f.recurso_uid, f.grandeza, f.indice) for f in ro.faltantes} >= {(F.FV, "potencia", 2)}
    assert limite_observado(ro.realizacao)[0] == datetime.fromisoformat(t(2))
    assert all(len(s.serie.valores) == 2 for s in ro.realizacao.series)     # nada após a lacuna (sem imputação)


def test_exportar_importar_reproduz_e_detecta_adulteracao():
    lv = livro()
    lv.registrar(obs(0))
    lv.selar_corte(t(1))
    lv.registrar(obs(1, rec=5))
    lv.registrar(obs(1, valor=float("inf"), ev="ruim"))
    doc = lv.exportar()
    doc2 = de_json(DocumentoLivro, json_canonico(doc))
    assert doc2 == doc and verificar_cadeia_livro(doc2) == []
    lv2 = LivroObservacoes.importar(doc2)
    assert lv2.hash_cadeia() == lv.hash_cadeia() and lv2.instantaneo(t(3)) == lv.instantaneo(t(3))
    ent = list(doc.entradas)
    ent[1] = dataclasses.replace(ent[1], observacao=dataclasses.replace(ent[1].observacao, valor=999.0))
    adul = dataclasses.replace(doc, entradas=tuple(ent))
    assert verificar_cadeia_livro(adul)
    with pytest.raises(ContratoInvalido):
        LivroObservacoes.importar(adul)
    ent = list(doc.entradas)
    ent[0], ent[1] = ent[1], ent[0]                                     # reordenação
    assert verificar_cadeia_livro(dataclasses.replace(doc, entradas=tuple(ent)))


def test_instantaneo_de_prefixo_e_funcao_pura_do_prefixo():
    lv = livro()
    lv.registrar(obs(0))
    lv.registrar(obs(1, rec=3))
    i = lv.instantaneo(t(1))
    j = instantaneo_de_prefixo(MISSAO, MG, i.corte_utc, lv.entradas[:i.n_entradas], i.hash_cadeia_prefixo)
    assert j == i
