"""Auditoria independente do PR #14 (Piso 3C-1) — correções A-01, A-02 e A-03.

* A-01: disponibilidade EFETIVA do gerador na execução só por fonte declarada (observada × estática declarada);
  ausente/inválida/contraditória ⇒ erro de DADOS; indisponível com ON ⇒ inexequível; nunca 1 por omissão.
* A-02: contabilidade REALIZADA do 3C-1 = contabilidade 3C-0 (inalterada) + H₂ e custos dos eventos EFETIVAMENTE
  aplicados, sem dupla contagem e separada do valor futuro.
* A-03: declarações por unidade validadas ANTES de indexar (duplicatas, UIDs desconhecidos/de outra microrrede,
  procedência), sem sobrescrita silenciosa e com origem verificável.

Sintético/algébrico (dublê algébrico; não é validação física).
"""
from __future__ import annotations

import dataclasses
import math

import pytest

from ems_v2 import fixtures_3c0 as F0
from ems_v2 import fixtures_3c1 as Y
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.fixtures import proc
from ems_v2.parameters import Parametro
from ems_v2.ponte import registro as RG
from ems_v2.ponte.cenario import Realizacao, SerieRecurso
from ems_v2.ponte.compromisso import (CondicaoInicialUnidade, ExecutorAlgebricoCommitment3C1,
                                      FonteDisponibilidadeExecucao as FD, estado_inicial_3c1, montar_entrada_3c1,
                                      validar_fontes_disponibilidade)
from ems_v2.series import SerieTemporal

pytestmark = pytest.mark.synthetic_algebraic
INICIO = "2026-01-01T00:00:00+00:00"
JUST = "Ensaio sintético: condição de disponibilidade declarada do cenário"


def est(uid="syn-ter", v=1):
    return FD(uid, "estatica_declarada", v, proc("A01"), JUST)


# =============================================================================== A-01 (sem solver: um passo)
def _passo(fonte, entorno_extra, u=1.0, p=30.0, carga=30.0):
    e = Y.caso_a()
    ex = ExecutorAlgebricoCommitment3C1(e, {"syn-ter": fonte})
    consignas = {"syn-ter|u": u, "syn-ter|p": p, "syn-carga|ell": 0.0}
    entorno = {"syn-carga|potencia": carga, **entorno_extra}
    return ex.avancar(estado_inicial_3c1(e), consignas, entorno, 900)


def _cods(passo):
    return {c.codigo for c in passo.constatacoes}


def test_a01_observada_disponivel_executa():
    r = _passo(FD("syn-ter", "observada"), {"syn-ter|disponibilidade": 1.0})
    assert r.exequivel and r.estado_final.gerador("syn-ter").ligado


def test_a01_observada_indisponivel_com_ON_inexequivel():
    r = _passo(FD("syn-ter", "observada"), {"syn-ter|disponibilidade": 0.0})
    assert not r.exequivel and r.falha == "inexequivel" and "consigna_inexequivel_indisponivel" in _cods(r)
    off = _passo(FD("syn-ter", "observada"), {"syn-ter|disponibilidade": 0.0}, u=0.0, p=0.0, carga=0.0)
    assert off.exequivel                                     # indisponível e OFF: nada a objetar


def test_a01_observada_ausente_e_erro_de_dados_nao_inviabilidade():
    r = _passo(FD("syn-ter", "observada"), {})
    assert not r.exequivel and r.falha == "dados" and "disponibilidade_realizada_ausente" in _cods(r)
    r = _passo(FD("syn-ter", "observada"), {}, u=0.0, p=0.0, carga=0.0)
    assert not r.exequivel and r.falha == "dados"            # a observação é exigida mesmo com a unidade OFF


@pytest.mark.parametrize("v", [0.5, math.nan, 2.0, -1.0])
def test_a01_observacao_invalida_e_erro_de_dados(v):
    r = _passo(FD("syn-ter", "observada"), {"syn-ter|disponibilidade": v})
    assert not r.exequivel and r.falha == "dados" and "disponibilidade_realizada_invalida" in _cods(r)


def test_a01_estatica_declarada_e_contradicao():
    assert _passo(est(v=1), {}).exequivel                    # sem observação: a condição declarada vale
    assert _passo(est(v=1), {"syn-ter|disponibilidade": 1.0}).exequivel
    r = _passo(est(v=1), {"syn-ter|disponibilidade": 0.0})
    assert not r.exequivel and r.falha == "dados" and "disponibilidade_contraditoria" in _cods(r)
    r = _passo(est(v=0), {})
    assert not r.exequivel and r.falha == "inexequivel" and "consigna_inexequivel_indisponivel" in _cods(r)


def test_a01_serie_de_outro_recurso_rejeitada_sem_heranca():
    r = _passo(FD("syn-ter", "observada"), {"syn-ter|disponibilidade": 1.0, "syn-ter#9|disponibilidade": 1.0})
    assert not r.exequivel and r.falha == "dados" and "disponibilidade_de_outro_recurso" in _cods(r)
    g = Y.caso_g()                                           # bloco com 2 unidades: série do REGISTRO não vale
    ex = ExecutorAlgebricoCommitment3C1(g, {"syn-ter#1": FD("syn-ter#1", "observada"),
                                            "syn-ter#2": FD("syn-ter#2", "observada")})
    cons = {"syn-ter#1|u": 1.0, "syn-ter#1|p": 20.0, "syn-ter#2|u": 0.0, "syn-ter#2|p": 0.0, "syn-carga|ell": 0.0}
    r = ex.avancar(estado_inicial_3c1(g), cons, {"syn-carga|potencia": 20.0, "syn-ter|disponibilidade": 1.0}, 900)
    assert not r.exequivel and {"disponibilidade_de_outro_recurso", "disponibilidade_realizada_ausente"} <= _cods(r)


@pytest.mark.parametrize("fontes,cod", [
    ({}, "fonte_disponibilidade_nao_declarada"),
    ({"syn-ter": FD("syn-ter", "padrao")}, "fonte_disponibilidade_invalida"),
    ({"syn-ter": FD("syn-ter#1", "observada")}, "fonte_disponibilidade_invalida"),
    ({"syn-ter": FD("syn-ter", "observada", 1)}, "fonte_disponibilidade_contraditoria"),
    ({"syn-ter": FD("syn-ter", "estatica_declarada", True, proc("x"), JUST)}, "disponibilidade_estatica_invalida"),
    ({"syn-ter": FD("syn-ter", "estatica_declarada", 1.0, proc("x"), JUST)}, "disponibilidade_estatica_invalida"),
    ({"syn-ter": FD("syn-ter", "estatica_declarada", None, proc("x"), JUST)}, "disponibilidade_estatica_invalida"),
    ({"syn-ter": FD("syn-ter", "estatica_declarada", 1, None, JUST)}, "sem_procedencia"),
    ({"syn-ter": FD("syn-ter", "estatica_declarada", 1, proc("x"), " ")}, "disponibilidade_estatica_sem_justificativa"),
    ({"syn-ter": est(), "syn-outro": est("syn-outro")}, "fonte_disponibilidade_uid_desconhecido"),
    ("x", "fontes_disponibilidade_invalidas"),
])
def test_a01_fonte_sem_padrao_e_estrita(fontes, cod):
    assert cod in {c.codigo for c in validar_fontes_disponibilidade(Y.caso_a(), fontes)}
    with pytest.raises(ContratoInvalido):
        ExecutorAlgebricoCommitment3C1(Y.caso_a(), fontes)


# =============================================================================== A-01/A-02 com plano real (HiGHS)
def _real_pemfc(a=(1, 1, 1, 1), L=(0, 15, 15, 0)):
    s = SerieTemporal("potencia", "kW", "media_intervalo", INICIO, 60, tuple(map(float, L)), proc("PEMFC-real"),
                      fronteira="barramento_liquido")
    d = SerieTemporal("disponibilidade", "1", "media_intervalo", INICIO, 60, tuple(map(float, a)), proc("PEMFC-real"))
    return Realizacao("syn-real-pemfc", "sintetica", (SerieRecurso("syn-carga", "potencia", s),
                                                      SerieRecurso("syn-fc", "disponibilidade", d)), proc("PEMFC-real"))


def _plano_pemfc():
    pytest.importorskip("pyomo", exc_type=ImportError)
    from ems_v2.milp.config import CONFIG_ANALITICA
    from ems_v2.milp.solver_3c1 import resolver_3c1
    from ems_v2.ponte.compromisso import plano_de_resultado_3c1
    e = Y.pemfc_instantanea(eventos=True)
    r = resolver_3c1(e, CONFIG_ANALITICA)
    assert r.aceito, r.codigos()
    p, pc = plano_de_resultado_3c1(r, e)
    return e, r, p, pc


def _exec(e, p, real, n=None, uid="0123456789abcdef0123456789abcdef"):
    from ems_v2.ponte.execucao import executar
    ex = ExecutorAlgebricoCommitment3C1(e, {"syn-fc": FD("syn-fc", "observada")})
    return executar(p, estado_inicial_3c1(e), ex, real, execucao_uid=uid, intervalos=n)


def test_a01_execucao_interrompida_por_indisponibilidade_realizada_e_por_dado_ausente():
    e, r, p, pc = _plano_pemfc()
    t = _exec(e, p, _real_pemfc(a=(1, 1, 0, 1)))
    assert t.situacao == "interrompida_inexequivel" and len(t.passos) == 2
    sem = Realizacao("syn-real-sem", "sintetica", (_real_pemfc().series[0],), proc("PEMFC-real"))
    t = _exec(e, p, sem)
    assert t.situacao == "erro_dados" and len(t.passos) == 0
    assert "disponibilidade_realizada_ausente" in {c.codigo for c in t.constatacoes}


def test_a02_custo_realizado_pemfc_completo_analitico():
    from ems_v2.ponte.compromisso import contabilidade_realizada_3c1
    e, r, p, pc = _plano_pemfc()
    real = _real_pemfc()
    t = _exec(e, p, real)
    assert t.situacao == "concluida"
    cont = contabilidade_realizada_3c1(e, p, t, real)
    comp = {c.termo: c for c in cont.custo.componentes}
    # contínuo: 2 intervalos × q(15) = 0,9 kg/h × 1/60 h = 0,03 kg; eventos: 0,002 + 0,001 kg; c_H = 10 R$/kg
    assert cont.indicadores["H2_continuo_kg"] == pytest.approx(0.03, abs=1e-12)
    assert cont.indicadores["H2_eventos_kg"] == pytest.approx(0.003, abs=1e-12)
    assert comp["combustivel_h2"].valor_R == pytest.approx(0.33, abs=1e-12)
    assert comp["eventos"].valor_R == pytest.approx(2.0, abs=1e-12)                 # 1,5 + 0,5 (R$/evento, sem h)
    assert cont.custo.total_R == pytest.approx(2.33, abs=1e-12)
    assert cont.eventos_aplicados == {"syn-fc": {"partidas": 1, "paradas": 1}}
    # plano (oráculo) × incorrido coincidem termo a termo; nenhum termo de valor futuro
    assert comp["combustivel_h2"].valor_R == pytest.approx(r.custos_modelo["combustivel_h2"], abs=1e-9)
    assert comp["eventos"].valor_R == pytest.approx(r.custos_modelo["eventos"], abs=1e-9)
    assert all(c.base == "realizado" and c.termo not in ("terminal", "valor_futuro") for c in cont.custo.componentes)


def test_a02_sem_dupla_contagem_e_3c0_inalterado():
    from ems_v2.ponte.compromisso import contabilidade_realizada_3c1
    e, r, p, pc = _plano_pemfc()
    real = _real_pemfc()
    t = _exec(e, p, real)
    _, base = RG.indicadores_e_custo(e.base, p, t, real)                          # 3C-0: só o contínuo
    b = {c.termo: c.valor_R for c in base.componentes}
    assert b == {"combustivel_h2": pytest.approx(0.3, abs=1e-12)}
    cont = contabilidade_realizada_3c1(e, p, t, real)
    h2 = cont.h2[0]
    assert h2.custo_continuo_R == pytest.approx(b["combustivel_h2"], abs=1e-12)
    total_h2 = {c.termo: c.valor_R for c in cont.custo.componentes}["combustivel_h2"]
    assert total_h2 == pytest.approx(h2.custo_continuo_R + h2.custo_eventos_R, abs=1e-12)   # uma única vez cada parte


def test_a02_execucao_parcial_e_interrompida_so_eventos_aplicados():
    from ems_v2.ponte.compromisso import contabilidade_realizada_3c1
    e, r, p, pc = _plano_pemfc()
    for real, n in ((_real_pemfc(), 2), (_real_pemfc(a=(1, 1, 0, 1)), None)):
        t = _exec(e, p, real, n)
        assert len(t.passos) == 2
        cont = contabilidade_realizada_3c1(e, p, t, real)
        comp = {c.termo: c.valor_R for c in cont.custo.componentes}
        # t = 0 OFF, t = 1 partida a 15 kW: 0,015 kg contínuo + 0,002 kg de partida; parada (t = 3) NÃO aplicada
        assert cont.eventos_aplicados == {"syn-fc": {"partidas": 1, "paradas": 0}}
        assert comp["combustivel_h2"] == pytest.approx(10 * (0.015 + 0.002), abs=1e-12)
        assert comp["eventos"] == pytest.approx(1.5, abs=1e-12) and cont.custo.intervalos == 2
    t0 = _exec(e, p, _real_pemfc(), 0)
    cont = contabilidade_realizada_3c1(e, p, t0, _real_pemfc())
    assert cont.custo.total_R == 0.0 and cont.eventos_aplicados == {}


def test_a02_custo_realizado_selado_no_registro_separado_do_valor_futuro(tmp_path):
    from ems_v2.ponte import canonico
    from ems_v2.ponte.compromisso import contabilidade_realizada_3c1
    from ems_v2.ponte.execucao import hash_plano
    e, r, p, pc = _plano_pemfc()
    real = _real_pemfc()
    t = _exec(e, p, real)
    cont = contabilidade_realizada_3c1(e, p, t, real)
    h = "0" * 64
    reg = RG.selar_registro(RG.RegistroExecucaoEMS(
        1, "0123456789abcdef0123456789abcdef", "2026-11-09T00:00:00+00:00",
        RG.ReferenciaOrigem(e.base.microrrede_uid, None, 1, h, h, h, e.base.cenario_uid, 1, h),
        {"ponte": "3C-0", "perfil": "v1.1-3C-1"}, {"entrada": r.hash_entrada, "plano": hash_plano(p)},
        RG.Discretizacao(e.base.malha.inicio_utc, e.base.malha.delta_s, 4, 4, 4),
        RG.ResumoSolver(r.classificacao, r.estado_despacho, r.terminacao, r.objetivo, r.limite_dual, r.gap_abs,
                        r.gap_rel, "{}", canonico.json_canonico(r.ambiente)),
        p, t.estados[0], t.estados[-1], t.situacao, t.checkpoints[-1], cont.indicadores, cont.custo,
        dict(p.custo_objetivo_planejado), RG.valor_futuro_nao_implementado(t.estados[-1].indice_fronteira),
        "exito", "ensaio 3C-1", {}, (), {}))
    lido = RG.ler_registro(RG.gravar_registro(tmp_path, reg))
    assert lido == reg and lido.custo_realizado.total_R == pytest.approx(2.33, abs=1e-12)
    assert lido.valor_futuro.contabilizado_como_custo is False and lido.valor_futuro.valor_R is None
    falso = dataclasses.replace(cont.custo, componentes=cont.custo.componentes + (
        RG.ComponenteCusto("valor_futuro", 1.0, "realizado"),))
    assert "valor_futuro_contabilizado_como_custo" in {c.codigo for c in RG.validar_registro(
        dataclasses.replace(reg, custo_realizado=falso, selo=""))}


# =============================================================================== A-03 (sem solver)
MG = "syn-mg-a"


def _inventario(q=2):
    d = F0.termica(MG)
    for k, (un, v) in dict(ramp_kW_min=("kW/min", 2.0), t_on_min=("min", 30.0), t_off_min=("min", 15.0)).items():
        d = F0.com_valor(d, k, F0.num(k, un, v, MG, d.uid))
    if q is not None:
        d = dataclasses.replace(d, quantidade=q)
    return F0.inventario(MG, (F0.bateria(MG), F0.usina(MG), F0.arranjo(MG), d))


def _decl(unidades, mg=MG, cen="syn-cenario-3c0"):
    from ems_v2.compromisso.contrato import PoliticaPermanenciaTerminal
    from ems_v2.ponte.compromisso import DeclaracaoCommitment3C1
    return DeclaracaoCommitment3C1(mg, cen, PoliticaPermanenciaTerminal("obrigacao_residual_vinculante", "ensaio",
                                                                        F0.proc()), (),
                                   {"syn-ter1": "instantanea_unidade_quente"}, {"syn-ter1": "rampa_convencional"},
                                   "Ensaio A-03", tuple(unidades), F0.proc())


def _cu(uid, estado="em_operacao", p=10.0, tempo=3600, pr=True):
    return CondicaoInicialUnidade(uid, estado, Parametro(p, "kW", F0.proc()), tempo, F0.proc() if pr else None)


def _montar(unidades, q=2, **kw):
    inv = _inventario(q)
    cen = F0.cenario(inv)
    if q and q > 1:
        cen = dataclasses.replace(cen, condicoes_iniciais=tuple(
            dataclasses.replace(c, unidades_ligadas=1) if c.uid == "syn-ter1" else c for c in cen.condicoes_iniciais))
    return montar_entrada_3c1(inv, cen, F0.previsao(), F0.definicao(), F0.politicas(), _decl(unidades, **kw),
                              contexto="ensaio")


def _codigos(r):
    return {c.codigo for c in r[1]}


def test_a03_duas_unidades_validas_com_estados_diferentes():
    e3, cs, _ = _montar([_cu("syn-ter1#1", "em_operacao", 12.0, 3600), _cu("syn-ter1#2", "desligada", 0.0, 300)])
    assert e3 is not None, [(c.codigo, c.caminho) for c in cs if c.severidade != "aviso"]
    st = {str(s.uid): s for s in e3.base.estados_geradores}
    assert (st["syn-ter1#1"].ligado, st["syn-ter1#1"].p_anterior_kW.valor) == (True, 12.0)
    assert (st["syn-ter1#2"].ligado, st["syn-ter1#2"].p_anterior_kW.valor) == (False, 0.0)
    assert (e3.memoria("syn-ter1#1").tempo_no_estado_s, e3.memoria("syn-ter1#2").tempo_no_estado_s) == (3600, 300)
    # origem verificável: a procedência da potência e da memória aponta a declaração usada
    assert "DeclaracaoCommitment3C1.unidades[1]" in st["syn-ter1#2"].p_anterior_kW.procedencia.observacoes
    assert "DeclaracaoCommitment3C1.unidades[0]" in e3.memoria("syn-ter1#1").procedencia.observacoes


@pytest.mark.parametrize("dup", [_cu("syn-ter1#1", "em_operacao", 12.0), _cu("syn-ter1#1", "desligada", 0.0, 10)])
def test_a03_duplicatas_rejeitadas_identicas_ou_contraditorias(dup):
    r = _montar([_cu("syn-ter1#1", "em_operacao", 12.0), _cu("syn-ter1#2", "desligada", 0.0), dup])
    assert r[0] is None and "condicao_unidade_duplicada" in _codigos(r)


@pytest.mark.parametrize("uid", ["syn-ter1#3", "syn-ter1", "syn-bat1", "eq-0123456789ab#1", "syn-ter9#1"])
def test_a03_uid_desconhecido_ou_de_outro_recurso_rejeitado(uid):
    r = _montar([_cu("syn-ter1#1"), _cu("syn-ter1#2", "desligada", 0.0), _cu(uid)])
    assert r[0] is None and "condicao_unidade_uid_desconhecido" in _codigos(r)


def test_a03_declaracao_de_outra_microrrede_ou_cenario():
    un = [_cu("syn-ter1#1"), _cu("syn-ter1#2", "desligada", 0.0)]
    assert "declaracao_de_outra_microrrede" in _codigos(_montar(un, mg="syn-mg-b"))
    assert "declaracao_de_outro_cenario" in _codigos(_montar(un, cen="syn-outro-cenario"))


def test_a03_procedencia_e_valores_da_condicao_verificados():
    r = _montar([_cu("syn-ter1#1", pr=False), _cu("syn-ter1#2", "desligada", 0.0)])
    assert r[0] is None and "sem_procedencia" in _codigos(r)
    ruim = CondicaoInicialUnidade("syn-ter1#2", "desligada", Parametro(0.0, "W", F0.proc()), 10, F0.proc())
    r = _montar([_cu("syn-ter1#1"), ruim])
    assert r[0] is None and "unidade_nao_canonica" in _codigos(r)
    r = _montar([_cu("syn-ter1#1"), _cu("syn-ter1#2", "desligada", 0.0, -5)])
    assert r[0] is None and "memoria_invalida" in _codigos(r)


def test_a03_registro_de_uma_unidade_declaracao_x_cenario():
    # registro de UMA unidade: a condição do cenário é a da unidade; declaração contraditória ⇒ erro (sem escolha)
    r = _montar([_cu("syn-ter1", "em_operacao", 11.0, 3600)], q=None)
    assert r[0] is None and "condicao_unidade_contradiz_cenario" in _codigos(r)
    e3, cs, _ = _montar([_cu("syn-ter1", "em_operacao", 10.0, 3600)], q=None)        # idêntica ⇒ aviso
    assert e3 is not None and "condicao_unidade_redundante_com_cenario" in {c.codigo for c in cs}
    e3, cs, _ = _montar([], q=None)                                                  # só o cenário
    assert e3 is not None
    p = e3.base.estados_geradores[0].p_anterior_kW
    assert "condição do registro syn-ter1 no cenário" in p.procedencia.observacoes
