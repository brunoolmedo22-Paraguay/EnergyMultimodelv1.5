"""Piso 3C-1 — contrato, discretização, preflight e memória do commitment dinâmico (SEM Pyomo/HiGHS).

Sintético/algébrico: não é validação física.
"""
from __future__ import annotations

import dataclasses
import math

import pytest

from ems_v2 import FORMULACAO_3BP, FORMULACAO_3C1, FORMULACOES
from ems_v2 import fixtures as F
from ems_v2 import fixtures_3b as X
from ems_v2 import fixtures_3c1 as Y
from ems_v2.compromisso.contrato import (ABSTRACOES_TRANSICAO, EntradaCommitment3C1, discretizar, entrada_3c1_de_json,
                                         hash_entrada_3c1, json_canonico_3c1, obrigacao_derivada_s, tempo_s_exato,
                                         validar_entrada_3c1)
from ems_v2.compromisso.memoria import garantia, memoria_apos
from ems_v2.compromisso.preflight import preflight_3c1, programa_parcial_valido
from ems_v2.contracts import ErroSerializacao, hash_entrada, json_canonico, validar_entrada

pytestmark = pytest.mark.synthetic_algebraic
R = dataclasses.replace

# SHA-256 das fixtures 3B-P medidos na base 81aa09c (antes do 3C-1) — o esquema v1 não foi tocado
HASHES_3BP_BASE = {"a06": "eea0aab30f19bd90", "multi_uid": "409c68715d1e1909", "instancia_maior": "21c863e4b9875258",
                   "pwl_com_bateria": "0d39a801c196919b"}


def _codigos(e, **kw):
    return validar_entrada_3c1(e).codigos(**kw)


def _un(e, **mud):
    return R(e, unidades=(R(e.unidades[0], **mud),) + e.unidades[1:])


# ----------------------------------------------------------------------------- perfil e retrocompatibilidade
def test_perfil_3c1_explicito_e_contratos_anteriores_sem_capacidades_novas():
    assert FORMULACAO_3C1 == "v1.1-3C-1" and FORMULACAO_3C1 not in FORMULACOES
    e, _ = X.a07()
    assert "formulacao_incompativel" in validar_entrada(R(e, versao_formulacao=FORMULACAO_3C1)).codigos()
    for nome, pref in HASHES_3BP_BASE.items():
        assert hash_entrada(getattr(X, nome)()[0]).startswith(pref), nome


def test_json_canonico_proprio_e_base_identica_ao_3bp():
    e3 = Y.caso_h()
    s = json_canonico_3c1(e3)
    assert entrada_3c1_de_json(s) == e3 and json_canonico_3c1(entrada_3c1_de_json(s)) == s
    import json
    assert json.dumps(json.loads(s)["base"], sort_keys=True, separators=(",", ":"), ensure_ascii=False) \
        == json_canonico(e3.base)
    assert hash_entrada_3c1(e3) != hash_entrada(e3.base)
    e3b = _un(e3, tempo_min_ligado_min=F.par(121.0, "min", "x"))
    assert hash_entrada_3c1(e3b) != hash_entrada_3c1(e3) and hash_entrada(e3b.base) == hash_entrada(e3.base)
    with pytest.raises(ErroSerializacao):
        entrada_3c1_de_json(s.replace('"versao_esquema_3c1":1', '"versao_esquema_3c1":1,"extra":2'))
    with pytest.raises(ErroSerializacao):
        entrada_3c1_de_json(s.replace('"tempo_no_estado_s":7200', '"tempo_no_estado_s":NaN'))


def test_base_deve_ser_3bp_e_formulacao_3c1():
    e3 = Y.caso_a()
    assert validar_entrada_3c1(e3).aceito
    assert "base_nao_3bp" in _codigos(R(e3, base=R(e3.base, versao_formulacao="v1.1-3A")))
    assert "formulacao_nao_3c1" in _codigos(R(e3, versao_formulacao=FORMULACAO_3BP))
    assert "versao_esquema_3c1_incompativel" in _codigos(R(e3, versao_esquema_3c1=2))
    assert "entrada_3c1_invalida" in validar_entrada_3c1(e3.base).codigos()


# ----------------------------------------------------------------------------- parâmetros: ausência ≠ sem restrição
@pytest.mark.parametrize("campo,cod", [("rampa_subida_kW_min", "parametro_ausente"),
                                       ("rampa_descida_kW_min", "parametro_ausente"),
                                       ("tempo_min_ligado_min", "parametro_ausente"),
                                       ("tempo_min_desligado_min", "parametro_ausente")])
def test_parametro_temporal_ausente_bloqueia(campo, cod):
    r = validar_entrada_3c1(_un(Y.caso_a(), **{campo: None}))
    assert not r.aceito and cod in r.codigos("erro")


def test_unidades_e_dominio_dos_parametros():
    e = Y.caso_a()
    assert "unidade_incompativel" in _codigos(_un(e, rampa_subida_kW_min=F.par(1.0, "kW", "x")))
    assert "quantidade_negativa" in _codigos(_un(e, tempo_min_ligado_min=F.par(-1.0, "min", "x")))
    assert "valor_nao_finito" in _codigos(_un(e, rampa_subida_kW_min=F.par(math.inf, "kW/min", "x")))
    assert "unidade_incompativel" in _codigos(_un(e, custo_partida=F.par(1.0, "R$", "x")))
    # kW/s convertido explicitamente (cadeia registrada) é aceito
    from ems_v2.parameters import Parametro
    p = Parametro.de_bruto(1.0, "kW/s", F.proc("x"))
    assert p.valor == 60.0 and validar_entrada_3c1(_un(e, rampa_subida_kW_min=p)).aceito


def test_abstracao_limites_e_justificativa_sem_padrao():
    e = Y.caso_a()
    assert "abstracao_transicao_invalida" in _codigos(_un(e, abstracao_transicao="multimodo"))
    assert "abstracao_sem_justificativa" in _codigos(_un(e, justificativa_abstracao=" "))
    assert "limites_transicao_invalidos" in _codigos(_un(e, limites_transicao="padrao"))
    assert "limite_transicao_contraditorio" in _codigos(_un(e, potencia_partida_max_kW=F.par(20.0, "kW", "x")))
    d = _un(e, limites_transicao="declarados")
    assert "parametro_ausente" in _codigos(d)
    assert set(ABSTRACOES_TRANSICAO) == {"instantanea_unidade_quente", "transicoes_bloqueadas"}


def test_multimodo_continua_pendente():
    e = Y.caso_a()
    g = R(e.base.geradores[0], variante_commitment="multimodo")
    r = validar_entrada_3c1(R(e, base=R(e.base, geradores=(g,))))
    assert not r.aceito and "multimodo_nao_suportado_3A" in r.codigos("pendente")


def test_custos_de_evento_exigem_termo_e_coeficientes():
    e = Y.caso_a()
    assert validar_entrada_3c1(e).aceito
    assert "parametro_ausente" in _codigos(_un(e, custo_partida=None))
    assert "coeficiente_sem_termo" in _codigos(R(e, termos_adicionais=()))
    assert "termo_3c1_desconhecido" in _codigos(R(e, termos_adicionais=("eventos", "regularizador_rampa")))
    assert "termo_objetivo_duplicado" in _codigos(R(e, termos_adicionais=("eventos", "eventos")))
    sem = _un(R(e, termos_adicionais=()), custo_partida=None, custo_parada=None)
    assert validar_entrada_3c1(sem).aceito      # sem termo: transições continuam restritas, sem custo implícito


def test_pemfc_com_transicoes_e_combustivel_exige_massas_de_evento():
    e = Y.pemfc_instantanea()
    r = validar_entrada_3c1(e)
    assert r.aceito and "pemfc_abstracao_instantanea" in r.codigos("aviso")
    assert "parametro_ausente" in validar_entrada_3c1(Y.pemfc_instantanea(com_massas=False)).codigos("erro")
    t = Y.caso_a()
    assert "coeficiente_sem_termo" in _codigos(_un(t, massa_h2_partida_kg=F.par(0.1, "kg", "x")))


def test_unidades_por_uid_sem_agregacao():
    e = Y.caso_g()
    assert validar_entrada_3c1(e).aceito
    assert "commitment_unidade_ausente" in _codigos(R(e, unidades=e.unidades[:1]))
    assert "commitment_uid_duplicado" in _codigos(R(e, unidades=e.unidades + e.unidades[:1]))
    alheia = R(e.unidades[0], uid=Y.uid("syn-ter", 3))
    assert "commitment_uid_desconhecido" in _codigos(R(e, unidades=e.unidades + (alheia,)))


# ----------------------------------------------------------------------------- memória declarada
def test_memoria_obrigatoria_quando_necessaria_e_coerente():
    e = Y.caso_e()
    assert validar_entrada_3c1(e).aceito
    assert "memoria_ausente" in _codigos(R(e, memorias=()))
    m = e.memorias[0]
    assert "memoria_ausente" in _codigos(R(e, memorias=(R(m, tempo_no_estado_s=None),)))
    assert "obrigacao_residual_inconsistente" in _codigos(R(e, memorias=(R(m, obrigacao_residual_s=900),)))
    assert "memoria_invalida" in _codigos(R(e, memorias=(R(m, tempo_no_estado_s=1.5),)))
    assert "memoria_invalida" in _codigos(R(e, memorias=(R(m, tempo_no_estado_s=True),)))
    assert "sem_procedencia" in _codigos(R(e, memorias=(R(m, procedencia=None),)))
    # T do estado vigente = 0 ⇒ memória não é necessária (nenhuma obrigação possível)
    a = Y.caso_a()
    assert validar_entrada_3c1(R(a, memorias=())).aceito


def test_obrigacao_derivada_regra_conservadora():
    assert obrigacao_derivada_s(tempo_s_exato(F.par(45.0, "min", "x")), 900) == 1800
    assert obrigacao_derivada_s(tempo_s_exato(F.par(45.0, "min", "x")), 4000) == 0
    assert obrigacao_derivada_s(tempo_s_exato(F.par(0.01, "min", "x")), 0) == 1      # 0,6 s ⇒ 1 s (para cima)


# ----------------------------------------------------------------------------- discretização
def test_discretizacao_exata_e_arredondamento_conservador():
    e = Y.caso_c()
    d = discretizar(e)["syn-ter"]
    assert (d.U, d.D, d.arredondamento) == (3, 0, "exato") and d.rampa_subida_kW == 1500.0
    e40 = _un(e, tempo_min_ligado_min=F.par(40.0, "min", "x"))
    r = validar_entrada_3c1(e40)
    d = discretizar(e40)["syn-ter"]
    assert d.U == 3 and d.arredondamento == "para_cima_conservador" and "permanencia_arredondada_para_cima" in r.codigos()
    b = discretizar(Y.caso_b())["syn-ter"]      # R = 1 kW/min, Δ = 5 min
    assert b.rampa_subida_kW == 5.0 and b.limite_partida_kW == 5.0 and b.origem_limites == "derivado_rampa_convencional"
    assert not b.partida_representavel and not b.parada_representavel     # 5 kW < P_min = 10 kW
    h = discretizar(Y.caso_h())
    assert h["syn-fc"].origem_limites == "declarados" and h["syn-fc"].limite_partida_kW == 20.0
    assert h["syn-ter"].exato["R_sub_x_delta_kW"] == "30"


def test_discretizacao_obrigacao_herdada_e_alem_da_janela():
    d = discretizar(Y.caso_e())["syn-ter"]
    assert d.obrigacao_inicial_intervalos == 2 and d.intervalos_forcados == 2 and d.obrigacao_alem_da_janela_s == 0
    e = Y.caso_e(tempo_s=0, T=120.0)              # 7200 s de obrigação > 4·900 s
    r = validar_entrada_3c1(e)
    d = discretizar(e)["syn-ter"]
    assert d.intervalos_forcados == 4 and d.obrigacao_alem_da_janela_s == 3600
    assert "obrigacao_herdada_alem_da_janela" in r.codigos("aviso") and "permanencia_maior_que_janela" in r.codigos()


def test_transicao_nao_representavel_bloqueada_com_aviso():
    r = validar_entrada_3c1(Y.caso_b())
    assert r.aceito and {"partida_nao_representavel_bloqueada", "parada_nao_representavel_bloqueada"} <= r.codigos("aviso")


# ----------------------------------------------------------------------------- preflight
@pytest.mark.parametrize("prog", [(1, 0, None), (True, 0, 0, 0), (1.0, 0, 0, 0), ("1", 0, 0, 0), (math.nan, 0, 0, 0),
                                  None, 1, [[1], 0, 0, 0]])
def test_compromisso_parcial_invalido(prog):
    c = {x.codigo for x in preflight_3c1(Y.caso_a(), {"syn-ter": prog})}
    assert "compromisso_invalido" in c


def test_compromisso_parcial_validacoes():
    assert programa_parcial_valido((None, 1, 0, None), 4) and not programa_parcial_valido((None, 1, 0), 4)
    c = {x.codigo for x in preflight_3c1(Y.caso_a(), "x")}
    assert "compromisso_invalido" in c
    c = {x.codigo for x in preflight_3c1(Y.caso_a(), {"syn-outro": (None,) * 4})}
    assert "compromisso_uid_desconhecido" in c
    c = {x.codigo for x in preflight_3c1(Y.caso_e(), {"syn-ter": (None, 1, None, None)})}
    assert "compromisso_parcial_viola_obrigacao" in c
    c = {x.codigo for x in preflight_3c1(Y.caso_b(), {"syn-ter": (1, 0, None, None)})}
    assert "transicao_fixada_nao_representavel" in c
    assert not [x for x in preflight_3c1(Y.caso_a(), {"syn-ter": (0, None, 1, None)}) if x.severidade != "aviso"]


def test_obrigacao_herdada_com_indisponibilidade_e_parada_forcada():
    e = Y.caso_e(ligado=True)
    g = R(e.base.geradores[0], disponibilidade=F.disp([1, 0, 1, 1], 15, "x"))
    c = {x.codigo for x in preflight_3c1(R(e, base=R(e.base, geradores=(g,))))}
    assert "obrigacao_ligado_com_indisponibilidade" in c
    b = Y.caso_b()                                # ON a 10 kW, parada não representável, a_0 = 0
    g = R(b.base.geradores[0], disponibilidade=F.disp([0, 1, 1, 1], 5, "x"))
    c = {x.codigo for x in preflight_3c1(R(b, base=R(b.base, geradores=(g,))))}
    assert "parada_forcada_nao_representavel" in c


# ----------------------------------------------------------------------------- memória terminal
def test_memoria_apos_programa_e_garantia():
    e = Y.caso_f("obrigacao_residual_vinculante")
    m = memoria_apos(e, "syn-ter", [0, 0, 0, 1], [0, 0, 0, 30])
    assert (m.ligado, m.tempo_no_estado_s, m.obrigacao_residual_s, m.indice_fronteira) == (True, 900, 1800, 4)
    m2 = memoria_apos(e, "syn-ter", [0, 0, 0, 0], [0, 0, 0, 0])
    assert (m2.ligado, m2.tempo_no_estado_s, m2.obrigacao_residual_s) == (False, 7200 + 3600, 0)
    assert garantia((m,))[0] == "residual_vinculante" and garantia((m2,)) == ("completa_na_janela", {})
    herd = Y.caso_e(tempo_s=0, T=120.0)           # obrigação herdada 7200 s; janela 3600 s
    m3 = memoria_apos(herd, "syn-ter", [0, 0, 0, 0], [0, 0, 0, 0])
    assert (m3.tempo_no_estado_s, m3.obrigacao_residual_s) == (3600, 3600)


def test_entradas_3c1_sao_frozen_e_hash_deterministico():
    e1, e2 = Y.caso_g(), Y.caso_g()
    assert e1 == e2 and hash_entrada_3c1(e1) == hash_entrada_3c1(e2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        e1.versao_formulacao = "x"                # type: ignore[misc]
    assert isinstance(e1, EntradaCommitment3C1)
