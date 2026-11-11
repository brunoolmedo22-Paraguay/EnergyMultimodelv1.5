"""Piso 3D-A (EM ANDAMENTO) — testes focalizados do que já está implementado: seleção explícita do motor, estratégia
declarativa ``milp_mpc`` e preflight V2 sobre microrredes REAIS do catálogo (diretório temporário; dados sintéticos de
teste). Nenhum destes testes chama o otimizador. Runner, persistência, reabertura e interface AINDA NÃO existem.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import piso3da_util as U  # noqa: E402

from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import preflight as PF  # noqa: E402
from seeds2.microgrid import config as C  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.operation import preflight as P16  # noqa: E402
from seeds2.operation import scenarios as S  # noqa: E402
from seeds2.operation import service as SV  # noqa: E402


def _loja(tmp_path, **kw):
    reg = MicrogridRegistry(tmp_path / "dados", adopt_legacy=False)
    cfg = U.config_bateria(**kw)
    reg.create(cfg)
    return reg.open(cfg["installation"]["uid"])


def _codigos(pf, nivel=PF.ERROR):
    return {i.code for i in pf.items if i.level == nivel}


def test_cenario_sem_chaves_3da_continua_no_motor_v16(tmp_path):
    sc = SV.create(_loja(tmp_path), name="Cenário V1.6")
    assert E.CHAVE_MOTOR not in sc.document and E.CHAVE_BLOCO not in sc.document
    assert S.engine(sc.document) == E.MOTOR_V16 == E.motor_selecionado(sc.document)
    assert S.structural_errors(sc.document) == []


def test_preflight_v2_monta_a_missao_de_uma_microrrede_do_catalogo(tmp_path):
    store = _loja(tmp_path)
    pf = PF.preparar(store, U.criar_cenario_v2(store))
    assert _codigos(pf) <= {"solver_indisponivel"}, [i.message for i in pf.items if i.level == PF.ERROR]
    mt = pf.montagem
    assert mt is not None and mt.modelo is not None and mt.modelo.conectado
    assert (mt.tempo.K, mt.tempo.N, mt.tempo.m, mt.tempo.H_L, mt.tempo.delta_min) == (12, 3, 1, 10, 60)
    assert mt.tempo.inicio_utc == "2026-01-01T00:00:00+00:00"
    assert mt.demanda_prevista_kW == (10.0,) * 12 == mt.demanda_realizada_kW
    assert [str(b.uid) for b in mt.modelo.base.baterias] == [U.bateria_id(pf.scenario.document)]
    assert pf.ponte["apto_para_otimizacao"] is True and len(pf.matriz) >= 10
    assert pf.ok is bool(pf.ambiente.get("disponivel"))        # sem Pyomo/HiGHS: bloqueado, nunca recaída no V1.6


def test_declaracao_ausente_bloqueia_sem_valor_de_respaldo(tmp_path):
    store = _loja(tmp_path)

    def mutar(doc):
        bid = U.bateria_id(doc)
        doc[E.CHAVE_BLOCO]["baterias"][bid]["eta_carga"] = None
    pf = PF.preparar(store, U.criar_cenario_v2(store, mutar=mutar))
    assert not pf.ok and "nao_declarado" in _codigos(pf)
    assert pf.montagem is None or pf.montagem.modelo is None    # nada chega ao motor


def test_limites_de_soc_apenas_sugeridos_bloqueiam_pela_ponte(tmp_path):
    store = _loja(tmp_path, soc_fonte="sugerido")
    pf = PF.preparar(store, U.criar_cenario_v2(store))
    assert not pf.ok and "valor_sugerido_nao_confirmado" in _codigos(pf)


def test_equipamento_disponivel_nao_representavel_bloqueia(tmp_path):
    termica = C.new_equipment("thermal", "Gerador diesel", tag="TER-01", params={
        "dynamic": "local_generator", "pmax_kW": 60.0, "pmin_kW": 15.0, "cvu_rs_MWh": 1200.0, "startup_cost_rs": 40.0})
    store = _loja(tmp_path, extras=[termica])
    pf = PF.preparar(store, U.criar_cenario_v2(store))
    assert not pf.ok and "nao_representavel_3da" in _codigos(pf)
    assert any("M19" in i.message for i in pf.items if i.level == PF.ERROR)


def test_motor_v16_recusa_cenario_que_seleciona_o_v2(tmp_path):
    store = _loja(tmp_path)
    pf16 = P16.prepare(store, U.criar_cenario_v2(store))
    assert not pf16.ok and any(E.MOTOR_V2 in i.message for i in pf16.items if i.level == P16.ERROR)


def test_valor_fora_do_dominio_impede_salvar_a_versao(tmp_path):
    store = _loja(tmp_path)

    def mutar(doc):
        doc[E.CHAVE_BLOCO]["baterias"][U.bateria_id(doc)]["eta_carga"] = 1.5
    with pytest.raises(S.ScenarioValidationError):
        U.criar_cenario_v2(store, mutar=mutar)
