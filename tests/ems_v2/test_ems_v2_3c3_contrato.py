"""Piso 3C-3 — contrato do PCC, tarifas e política econômica (SEM solver).

Rejeições obrigatórias (missão §12): limites nulos/insuficientes, parâmetros negativos inválidos, tarifas faltantes,
séries desalinhadas, intercâmbio de outra microrrede, dados futuros filtrados (tarifa emitida depois da decisão / preço
de liquidação na decisão causal), formulação que se faz passar por 3C-1, PCC ausente ≠ conexão ilimitada.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from ems_v2 import FORMULACAO_3C1
from ems_v2 import fixtures_3c3 as F
from ems_v2.compromisso.contrato import validar_entrada_3c1
from ems_v2.contracts import UIDRecurso, validar_entrada
from ems_v2.rede import FORMULACAO_3C3
from ems_v2.rede.contrato import (BlocoTarifario, entrada_3c3_de_json, hash_entrada_3c3, json_canonico_3c3,
                                  precos_na_malha, selecionar_perfil_causal, validar_entrada_3c3)
from ems_v2.rede.preflight import preflight_3c3

pytestmark = pytest.mark.synthetic_algebraic


def cods(e, sev=("erro", "pendente")):
    return {c.codigo for c in validar_entrada_3c3(e).constatacoes if c.severidade in sev}


def test_casos_validos_sem_bloqueio():
    for e in (F.caso_g1(), F.caso_g2(), F.caso_g2("sem"), F.caso_g3(), F.caso_g4(), F.caso_g9("A"), F.caso_g10(),
              F.caso_isolado_equivalente()):
        assert validar_entrada_3c3(e).aceito, cods(e)


def test_perfil_nao_se_faz_passar_por_3c1_nem_por_entrada_anterior():
    e = F.caso_g1()
    assert e.versao_formulacao == FORMULACAO_3C3 != FORMULACAO_3C1
    assert "formulacao_nao_3c3" in cods(replace(e, versao_formulacao=FORMULACAO_3C1))
    # o núcleo continua 3C-1 válido e a base continua 3B-P: nenhuma capacidade implícita
    assert validar_entrada_3c1(e.compromisso).aceito
    b = replace(e.base, versao_formulacao=FORMULACAO_3C3)
    assert "formulacao_incompativel" in validar_entrada(b).codigos()


def test_json_canonico_e_hash_proprios_reproduziveis():
    e = F.caso_g2()
    t = json_canonico_3c3(e)
    assert entrada_3c3_de_json(t) == e and json_canonico_3c3(entrada_3c3_de_json(t)) == t
    assert hash_entrada_3c3(e) != hash_entrada_3c3(F.caso_g1())
    e2 = replace(e, economia=replace(e.economia, tarifa_exportacao=replace(
        e.economia.tarifa_exportacao, blocos=(BlocoTarifario(F.tarifa("exportacao", [0.3], "x").blocos[0].inicio_utc,
                                                             900, 0.31),) + e.economia.tarifa_exportacao.blocos[1:])))
    assert hash_entrada_3c3(e2) != hash_entrada_3c3(e)        # tarifa adulterada muda o hash


def test_pcc_de_outra_microrrede_rejeitado():
    e = F.caso_g1()
    assert "pcc_de_outra_microrrede" in cods(replace(e, pcc=replace(e.pcc, microrrede_uid="syn-outra")))


def test_modo_e_sentidos_sem_padrao_e_pcc_ausente_nao_e_ilimitado():
    e = F.caso_g1()
    assert "modo_conexao_invalido" in cods(replace(e, pcc=replace(e.pcc, modo="")))
    assert "sentidos_invalidos" in cods(replace(e, pcc=replace(e.pcc, sentidos_permitidos="ambos")))
    assert "limite_pcc_ausente" in cods(replace(e, pcc=replace(e.pcc, limite_importacao=None)))
    assert "disponibilidade_pcc_ausente" in cods(replace(e, pcc=replace(e.pcc, disponibilidade=None)))
    assert "limite_de_sentido_proibido" in cods(replace(F.caso_g3(), pcc=replace(F.caso_g3().pcc,
                                                                                 limite_exportacao=F.caso_g1().pcc.limite_exportacao)))


def test_limites_negativos_e_nulos():
    e = F.caso_g1()
    neg = replace(e, pcc=replace(e.pcc, limite_importacao=replace(e.pcc.limite_importacao, valores=(-1.0, 25.0))))
    assert "limite_pcc_negativo" in cods(neg)
    nulo = replace(e, pcc=replace(e.pcc, limite_importacao=replace(e.pcc.limite_importacao, valores=(0.0, 0.0))))
    rel = validar_entrada_3c3(nulo)
    assert rel.aceito and "capacidade_contratada_nula" in rel.codigos("aviso")


def test_series_desalinhadas_e_cobertura_insuficiente():
    e = F.caso_g1()
    curta = replace(e, pcc=replace(e.pcc, limite_importacao=replace(e.pcc.limite_importacao, valores=(25.0,))))
    assert "cobertura_insuficiente" in cods(curta)
    passo = replace(e, pcc=replace(e.pcc, limite_importacao=replace(e.pcc.limite_importacao, passo_s=600)))
    assert "resolucao_incompativel" in cods(passo)
    desl = replace(e, pcc=replace(e.pcc, limite_importacao=replace(e.pcc.limite_importacao,
                                                                   inicio_utc="2025-12-31T23:50:00+00:00")))
    assert "serie_desalinhada" in cods(desl)


def test_tarifas_faltantes_negativas_desconhecidas_e_blocos():
    e = F.caso_g1()
    ec = e.economia
    assert "tarifa_importacao_ausente" in cods(replace(e, economia=replace(ec, tarifa_importacao=None)))
    assert "importacao_sem_custo" in cods(replace(e, economia=replace(ec, termos=("exportacao_rede",))))
    neg = F.tarifa("importacao", [0.8, -0.1], "x")
    assert "preco_negativo" in cods(replace(e, economia=replace(ec, tarifa_importacao=neg)))
    desc = F.tarifa("importacao", [0.8, None], "x")
    assert "preco_desconhecido" in cods(replace(e, economia=replace(ec, tarifa_importacao=desc)))
    atravessa = F.tarifa("importacao", [0.8, 0.8], "x", blocos_min=10)
    assert "intervalo_atravessa_blocos" in cods(replace(e, economia=replace(ec, tarifa_importacao=atravessa)))
    curta = F.tarifa("importacao", [0.8], "x")
    assert "tarifa_sem_cobertura" in cods(replace(e, economia=replace(ec, tarifa_importacao=curta)))
    outro = F.tarifa("importacao", [0.8, 0.8], "x", contrato="syn-outro-contrato")
    assert "tarifa_de_outro_contrato" in cods(replace(e, economia=replace(ec, tarifa_importacao=outro)))
    un = replace(F.tarifa("importacao", [0.8, 0.8], "x"), unidade="R$/MWh")
    assert "unidade_preco_incompativel" in cods(replace(e, economia=replace(ec, tarifa_importacao=un)))


def test_dados_futuros_filtrados_na_tarifa():
    e = F.caso_g1()
    ec = e.economia
    futura = F.tarifa("importacao", [0.8, 0.8], "x", emitido="2026-01-01T00:10:00+00:00")
    assert "tarifa_nao_causal" in cods(replace(e, economia=replace(ec, tarifa_importacao=futura)))
    liq = F.tarifa("importacao", [0.8, 0.8], "x", natureza="aplicavel_liquidacao")
    assert "preco_de_liquidacao_na_decisao" in cods(replace(e, economia=replace(ec, tarifa_importacao=liq)))
    # só a ablação ROTULADA admite o preço de liquidação na decisão
    assert validar_entrada_3c3(replace(e, economia=replace(ec, tarifa_importacao=liq,
                                                           rotulo_informacao="ablacao_oraculo"))).aceito


def test_selecao_causal_da_revisao_tarifaria():
    r0 = F.tarifa("importacao", [0.5] * 4, "s", revisao=0, emitido="2025-12-31T00:00:00+00:00")
    r1 = F.tarifa("importacao", [0.9] * 4, "s", revisao=1, emitido="2026-01-01T00:30:00+00:00")
    liq = F.tarifa("importacao", [2.0] * 4, "s", natureza="aplicavel_liquidacao")
    p, c = selecionar_perfil_causal((r0, r1, liq), "importacao", "2026-01-01T00:15:00+00:00")
    assert p == r0 and not c                                  # r1 ainda não emitida em τ
    p, c = selecionar_perfil_causal((r0, r1, liq), "importacao", "2026-01-01T00:30:00+00:00")
    assert p == r1                                            # emissão inclusiva em τ
    p, c = selecionar_perfil_causal((liq,), "importacao", "2026-01-01T00:30:00+00:00")
    assert p is None and {x.codigo for x in c} == {"tarifa_indisponivel_na_decisao"}


def test_exportacao_exige_remuneracao_declarada():
    e = F.caso_g2()
    ec = e.economia
    assert "remuneracao_exportacao_nao_declarada" in cods(replace(e, economia=replace(
        ec, remuneracao_exportacao="nao_aplicavel", termos=("importacao_rede",), tarifa_exportacao=None)))
    assert "remuneracao_contraditoria" in cods(replace(e, economia=replace(ec, remuneracao_exportacao="sem_remuneracao")))
    assert "remuneracao_de_sentido_proibido" in cods(replace(F.caso_g3(), economia=replace(
        F.caso_g3().economia, remuneracao_exportacao="sem_remuneracao")))


def test_isolado_declarado_nao_admite_dados_de_intercambio():
    e = F.caso_isolado_equivalente()
    assert "isolado_com_dados_de_intercambio" in cods(replace(e, pcc=replace(e.pcc, disponibilidade=F.caso_g1().pcc.disponibilidade)))
    assert "isolado_com_tarifa" in cods(replace(e, economia=F.caso_g1().economia))
    assert "isolado_com_sentido_permitido" in cods(replace(e, pcc=replace(e.pcc, sentidos_permitidos="somente_importacao")))


def test_uid_do_pcc_nao_colide_e_disponibilidade_fracionaria_pendente():
    e = F.caso_g3()
    assert "uid_duplicado" in cods(replace(e, pcc=replace(e.pcc, uid=UIDRecurso("syn-bess"))))
    fr = replace(e.pcc.disponibilidade.serie, valores=(1.0, 0.5))
    assert "disponibilidade_pcc_fracionaria" in cods(replace(e, pcc=replace(e.pcc, disponibilidade=replace(
        e.pcc.disponibilidade, serie=fr))))


def test_aviso_de_arbitragem_simultanea_e_precos_na_malha():
    e = F.caso_g10()
    assert "remuneracao_maior_que_importacao" in validar_entrada_3c3(e).codigos("aviso")
    v, c = precos_na_malha(e.economia.tarifa_importacao, e.base.malha, "x")
    assert v == (0.1, 0.1) and not c


def test_preflight_inclui_compromisso_parcial_do_nucleo():
    e = F.caso_g1()
    assert not [c for c in preflight_3c3(e) if c.severidade != "aviso"]
    assert {c.codigo for c in preflight_3c3(e, {"syn-x": (1, 1)})} == {"compromisso_uid_desconhecido"}
