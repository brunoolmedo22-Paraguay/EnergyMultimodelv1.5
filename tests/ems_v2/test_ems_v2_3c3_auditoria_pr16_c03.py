"""Piso 3C-3 — correção C-03 da auditoria do PR #16 (commit auditado ``7b8da5d``): ``verificar_registro_rede``.

Reproduzido sobre ``7b8da5d`` antes de corrigir (EVIDENCIA_3C3_EJECUCION §7b): um ``RegistroMissaoRede3C3`` re-selado
com ``totais = {}``, com esquema 99, com perfil ``v1.1-3C-1`` ou sem uma métrica passava em ``verificar_registro_rede``
E na auditoria INTEGRAL (``aceito = True``); ``finalizar`` lia métrica ausente como 0 (``ind.get(k, 0.0)``).
"""
from __future__ import annotations

import math
from dataclasses import replace
from types import SimpleNamespace

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

from ems_v2.diagnostics import ContratoInvalido  # noqa: E402
from ems_v2.mpc.registro import selar  # noqa: E402
from ems_v2.rede import ESQUEMA_3C3, FORMULACAO_3C3  # noqa: E402
from ems_v2.rede import experimentos as X  # noqa: E402
from ems_v2.rede.auditoria import auditar_missao_conectada  # noqa: E402
from ems_v2.rede.mpc import METRICAS_REDE, totais_rede_esperados, verificar_registro_rede  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic


@pytest.fixture(scope="module")
def g11():
    return X.g11_mpc_conectado()


def resel(rr, **kw):
    return selar(replace(rr, selo="", **kw))


def ver(ex, rr):
    r = ex.resultado
    return {c.codigo for c in verificar_registro_rede(rr, r.registro_missao, r.anexos_3c3)}


def integral(ex, rr):
    r = ex.resultado
    return auditar_missao_conectada(r.registro_missao, r.registros, r.livro, ex.modelo, ex.configuracao_rede,
                                    verdade=ex.verdade, anexos=r.anexos_3c3, registros_3c0=r.registros_3c0,
                                    registro_rede=rr)


def reprovado(ex, rr, codigo):
    assert codigo in ver(ex, rr)
    rel = integral(ex, rr)
    assert not rel.aceito and not rel.integridade_documental_certificada
    assert rel.verificacoes["balanco"] and rel.verificacoes["custos"] and not rel.verificacoes["documental"]
    assert codigo in {c.codigo for c in rel.constatacoes if c.severidade == "erro"}


def test_c03_registro_valido_tem_exatamente_as_nove_metricas(g11):
    rr = g11.resultado.registro_rede
    assert set(rr.totais) == set(METRICAS_REDE) and len(METRICAS_REDE) == 9
    assert ver(g11, rr) == set() and integral(g11, rr).aceito


def test_c03_totais_vazios_resselados(g11):
    reprovado(g11, resel(g11.resultado.registro_rede, totais={}), "totais_rede_metrica_ausente")


@pytest.mark.parametrize("metrica", METRICAS_REDE)
def test_c03_cada_metrica_ausente(g11, metrica):
    rr = g11.resultado.registro_rede
    reprovado(g11, resel(rr, totais={k: v for k, v in rr.totais.items() if k != metrica}), "totais_rede_metrica_ausente")


@pytest.mark.parametrize("metrica", METRICAS_REDE)
def test_c03_cada_metrica_alterada(g11, metrica):
    rr = g11.resultado.registro_rede
    v = rr.totais[metrica]
    alt = math.nextafter(v, math.inf)                          # 1 ulp: nenhuma tolerância esconde a alteração
    reprovado(g11, resel(rr, totais={**rr.totais, metrica: alt}), "totais_rede_divergentes")


@pytest.mark.parametrize("ruim", [float("nan"), float("inf"), -float("inf"), True, "1.0", None], ids=repr)
def test_c03_valor_nao_numerico_ou_nao_finito(g11, ruim):
    rr = g11.resultado.registro_rede
    rr2 = replace(rr, totais={**rr.totais, "E_importada_kWh": ruim})      # NaN/Inf não são seláveis (JSON canônico)
    assert "totais_rede_valor_invalido" in ver(g11, rr2)
    rel = integral(g11, rr2)
    assert not rel.aceito and "totais_rede_valor_invalido" in {c.codigo for c in rel.constatacoes}


@pytest.mark.parametrize("extra", [0.0, 1.0])
def test_c03_metrica_inesperada_rejeitada_mesmo_com_valor_zero(g11, extra):
    rr = g11.resultado.registro_rede
    reprovado(g11, resel(rr, totais={**rr.totais, "metrica_nao_prevista": extra}), "totais_rede_metrica_inesperada")


@pytest.mark.parametrize("esquema", [0, 2, 99, "1", True, 1.0], ids=repr)
def test_c03_esquema_incompativel(g11, esquema):
    reprovado(g11, resel(g11.resultado.registro_rede, esquema=esquema), "registro_rede_esquema_incompativel")


@pytest.mark.parametrize("perfil", ["v1.1-3C-1", "v1.1-3C-2", "v1.1-3C-3 ", "", "v1.2-3C-3"])
def test_c03_perfil_incompativel(g11, perfil):
    reprovado(g11, resel(g11.resultado.registro_rede, perfil=perfil), "registro_rede_perfil_incompativel")


def test_c03_rotulo_e_tipo_dos_totais(g11):
    rr = g11.resultado.registro_rede
    reprovado(g11, resel(rr, rotulo="modelo físico validado"), "registro_rede_rotulo_alterado")
    assert "totais_rede_invalidos" in ver(g11, replace(rr, totais=[("E_importada_kWh", 1.0)]))
    assert ver(g11, replace(rr, totais={})) >= {"registro_rede_adulterado", "totais_rede_metrica_ausente"}


def test_c03_zero_exato_continua_valido():
    """Missão isolada: as nove métricas valem EXATAMENTE 0 (presentes e acumuladas) e o registro é aceito."""
    ex = X.g12_rede_vs_isolado()["isolado"]
    rr = ex.resultado.registro_rede
    assert set(rr.totais) == set(METRICAS_REDE) and all(v == 0.0 for v in rr.totais.values())
    assert ver(ex, rr) == set() and integral(ex, rr).aceito


def test_c03_missao_sem_intervalo_aplicado_zero_derivado_e_nao_padrao():
    """Primeira janela sem plano: nenhum intervalo aplicado ⇒ as métricas são 0 por FATO (não por ausência)."""
    from ems_v2.mpc.experimentos import ResolvedorComFalha, resultado_sem_solucao
    ex = X.executar("c03-sem-intervalos", K=4, N=2, m=1, com_fc=False, modelo_kw={"e0": 0.0}, tipo="tabela",
                    resolvedor=ResolvedorComFalha(X.ResolvedorMILP3C3(X.config_solver()), 0, resultado_sem_solucao))
    r = ex.resultado
    assert r.registro_missao.conteudo.intervalos_aplicados == 0
    assert not set(METRICAS_REDE) & set(r.registro_missao.conteudo.indicadores_acumulados)
    assert r.registro_rede.totais == {k: 0.0 for k in METRICAS_REDE} and ver(ex, r.registro_rede) == set()
    assert integral(ex, r.registro_rede).aceito


def test_c03_ausencia_com_intervalos_aplicados_nunca_vira_zero(g11):
    rm = g11.resultado.registro_missao
    ind = {k: v for k, v in rm.conteudo.indicadores_acumulados.items() if k != "gasto_importacao_R"}
    falso = SimpleNamespace(conteudo=SimpleNamespace(indicadores_acumulados=ind,
                                                     intervalos_aplicados=rm.conteudo.intervalos_aplicados))
    tot, c = totais_rede_esperados(falso)
    assert "gasto_importacao_R" not in tot and {x.codigo for x in c} == {"indicador_rede_ausente_no_registro_missao"}
    ind2 = {**rm.conteudo.indicadores_acumulados, "E_exportada_kWh": float("nan")}
    _, c2 = totais_rede_esperados(SimpleNamespace(conteudo=SimpleNamespace(indicadores_acumulados=ind2,
                                                                          intervalos_aplicados=8)))
    assert {x.codigo for x in c2} == {"indicador_rede_invalido"}


def test_c03_finalizar_recusa_metrica_ausente(monkeypatch):
    """``finalizar`` não grava um registro de rede com métrica ausente lida como zero."""
    import ems_v2.rede.mpc as M
    ctrl, ent, *_ = X.montar("c03-finalizar", K=4, N=2, m=1, com_fc=False, modelo_kw={"e0": 0.0}, tipo="tabela")
    from ems_v2.mpc.orquestrador import executar_missao_simulada
    executar_missao_simulada(ctrl, ent, finalizar=False)
    orig = M.totais_rede_esperados

    def sem_uma(rm):
        t, c = orig(rm)
        t.pop("custo_desvio_rede_R")
        return t, c + [M.erro("indicador_rede_ausente_no_registro_missao", "x", "ensaio")]
    monkeypatch.setattr(M, "totais_rede_esperados", sem_uma)
    with pytest.raises(ContratoInvalido) as exc:
        ctrl.finalizar()
    assert "indicador_rede_ausente_no_registro_missao" in exc.value.codigos


def test_c03_constantes_do_esquema():
    assert ESQUEMA_3C3 == 1 and FORMULACAO_3C3 == "v1.1-3C-3"
