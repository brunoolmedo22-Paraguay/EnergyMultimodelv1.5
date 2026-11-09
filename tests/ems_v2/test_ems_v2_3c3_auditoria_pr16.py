"""Piso 3C-3 — correções C-01 e C-02 da auditoria independente do PR #16 (commit auditado ``d7da6c5``).

Ambos os defeitos foram REPRODUZIDOS sobre ``d7da6c5`` antes de corrigir (EVIDENCIA_3C3_EJECUCION §8):

* C-01 — uma consigna ``NaN`` do PCC produzia ``PassoAplicado`` exequível (com ``P_imp = NaN`` aplicado em
  ``sem_ajuste``); uma consigna PARCIAL era ignorada em silêncio quando havia programa; ``plano_de_resultado_3c3``
  recortava ``max(0, v)`` (−3 ⇒ 0; NaN ⇒ 0);
* C-02 — ``auditar_missao_conectada`` sem anexos/registros 3C-0/registro de rede devolvia ``aceito = True``; um modelo
  PCC com limites mais amplos ou uma política econômica substituída também eram aceitos.

C-01 roda SEM solver (plano analítico do G1); C-02 usa missões conectadas com HiGHS real (pulado sem Pyomo).
"""
from __future__ import annotations

import math
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ems_v2 import fixtures_3c3 as F
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.ponte.execucao import entorno_realizado, estado_inicial_de_entrada, executar
from ems_v2.rede.execucao import (ExecutorAlgebricoConectado3C3, PoliticaAjustePCC, plano_de_resultado_3c3,
                                  programa_de_plano)

from test_ems_v2_3c3_execucao import UID, pol, real, res_g1  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
PCC = F.PCC
POLITICAS = ("sem_ajuste", "ajuste_local_algebrico")
INVALIDOS = [float("nan"), float("inf"), -float("inf"), -1.0, -1e-12, True, False, "20", None, [20.0], object()]


def passo(tipo, com_programa, extra, e=None, programa=None):
    e = e or F.caso_g1()
    p, pr = plano_de_resultado_3c3(res_g1(e), e)
    prog = programa if programa is not None else (programa_de_plano(pr) if com_programa else None)
    ex = ExecutorAlgebricoConectado3C3(e, {}, pol(tipo=tipo), programa=prog)
    ent, _ = entorno_realizado(real(), p.inicio_utc, p.delta_s)
    cons = {f"{x.uid}|{x.grandeza}": float(x.valores[0]) for x in p.consignas}
    return ex.avancar(estado_inicial_de_entrada(e.base), {**cons, **extra}, ent, p.delta_s)


def cods(ps):
    return {c.codigo for c in ps.constatacoes}


# ------------------------------------------------------------------------------------------- C-01
@pytest.mark.parametrize("tipo", POLITICAS)
@pytest.mark.parametrize("com_programa", (False, True))
@pytest.mark.parametrize("ruim", INVALIDOS, ids=repr)
@pytest.mark.parametrize("sentido", ("P_imp", "P_exp"))
def test_c01_consigna_do_pcc_invalida_nunca_produz_passo_aplicado(tipo, com_programa, ruim, sentido):
    extra = {f"{PCC}|P_imp": 20.0, f"{PCC}|P_exp": 0.0}
    extra[f"{PCC}|{sentido}"] = ruim
    ps = passo(tipo, com_programa, extra)
    assert not ps.exequivel and ps.falha == "dados" and ps.aplicado == {}
    assert cods(ps) == {"intercambio_programado_invalido"}


@pytest.mark.parametrize("tipo", POLITICAS)
@pytest.mark.parametrize("com_programa", (False, True))
@pytest.mark.parametrize("so", ("P_imp", "P_exp"))
def test_c01_consigna_parcial_do_pcc_rejeitada(tipo, com_programa, so):
    ps = passo(tipo, com_programa, {f"{PCC}|{so}": 20.0 if so == "P_imp" else 0.0})
    assert not ps.exequivel and ps.falha == "dados" and cods(ps) == {"intercambio_programado_incompleto"}


@pytest.mark.parametrize("tipo", POLITICAS)
def test_c01_comando_e_programa_devem_coincidir(tipo):
    ps = passo(tipo, True, {f"{PCC}|P_imp": 21.0, f"{PCC}|P_exp": 0.0})
    assert not ps.exequivel and cods(ps) == {"programa_pcc_contraditorio"}
    ok = passo(tipo, True, {f"{PCC}|P_imp": 20.0, f"{PCC}|P_exp": 0.0})
    assert ok.exequivel and ok.aplicado[f"{PCC}|P_imp"] == 20.0


@pytest.mark.parametrize("tipo", POLITICAS)
def test_c01_caso_legitimo_so_programa_explicito_e_so_comando(tipo):
    so_prog = passo(tipo, True, {})                     # conciliação: o plano 3C-0 não tem consignas do PCC
    assert so_prog.exequivel and so_prog.aplicado[f"{PCC}|P_imp"] == 20.0
    so_cmd = passo(tipo, False, {f"{PCC}|P_imp": 20.0, f"{PCC}|P_exp": 0})   # planta: int 0 é real finito válido
    assert so_cmd.exequivel and math.isfinite(so_cmd.aplicado[f"{PCC}|P_imp"])
    nada = passo(tipo, False, {})
    assert not nada.exequivel and cods(nada) == {"programa_pcc_ausente"}


@pytest.mark.parametrize("ruim", [float("nan"), -1.0, True, "20", None])
def test_c01_programa_explicito_invalido_recusado_na_construcao(ruim):
    e = F.caso_g1()
    with pytest.raises(ContratoInvalido) as exc:
        ExecutorAlgebricoConectado3C3(e, {}, pol(), programa={0: (ruim, 0.0), 1: (20.0, 0.0)})
    assert exc.value.codigos == {"programa_pcc_invalido"}
    with pytest.raises(ContratoInvalido):
        ExecutorAlgebricoConectado3C3(e, {}, pol(), programa={"0": (20.0, 0.0)})


@pytest.mark.parametrize("imp", [(-3.0, 20.0), (float("nan"), 20.0), (20.0, float("inf")), (True, 20.0), ("20", 20.0),
                                 (20.0,), None])
def test_c01_plano_de_resultado_sem_recorte_silencioso(imp):
    e = F.caso_g1()
    r = res_g1(e)
    r = SimpleNamespace(**{**vars(r), "intercambio": ({"P_imp": imp, "P_exp": (0.0, 0.0)} if imp is not None
                                                      else {"P_exp": (0.0, 0.0)})})
    with pytest.raises(ContratoInvalido) as exc:
        plano_de_resultado_3c3(r, e)
    assert exc.value.codigos == {"intercambio_programado_invalido"}


def test_c01_isolado_nao_admite_consigna_ou_programa_de_intercambio():
    e = F.caso_isolado_equivalente()
    p = PoliticaAjustePCC("sem_ajuste", "limitada_pela_disponibilidade", "energia_medida_tarifa_aplicavel", None, None,
                          None, None, F.economia("x", isolado=True).procedencia, "isolado")
    ex = ExecutorAlgebricoConectado3C3(e, {}, p, programa={0: (5.0, 0.0)})
    est = estado_inicial_de_entrada(e.base)
    ps = ex.avancar(est, {f"{PCC}|P_imp": 0.0, f"{PCC}|P_exp": 0.0}, {}, 900)
    assert not ps.exequivel and ps.falha == "dados" and "intercambio_programado_em_operacao_isolada" in cods(ps)
    r = SimpleNamespace(**{**vars(res_g1(e)), "intercambio": {"P_imp": (1.0, 0.0), "P_exp": (0.0, 0.0)}})
    with pytest.raises(ContratoInvalido):
        plano_de_resultado_3c3(r, e)


def test_c01_executar_com_programa_valido_e_consignas_validas_continua_exato():
    e = F.caso_g1()
    p, pr = plano_de_resultado_3c3(res_g1(e), e)
    for tipo in POLITICAS:
        ex = ExecutorAlgebricoConectado3C3(e, {}, pol(tipo=tipo), programa=programa_de_plano(pr))
        t = executar(p, estado_inicial_de_entrada(e.base), ex, real(), execucao_uid=UID)
        assert t.situacao == "concluida" and [x.aplicado[f"{PCC}|P_imp"] for x in t.passos] == [20.0, 20.0]


# ------------------------------------------------------------------------------------------- C-02 (HiGHS)
def _solver():
    pytest.importorskip("pyomo", exc_type=ImportError)
    pytest.importorskip("highspy", exc_type=ImportError)


@pytest.fixture(scope="module")
def g11():
    _solver()
    from ems_v2.rede import experimentos as X
    return X.g11_mpc_conectado()


def integral(ex, **kw):
    from ems_v2.rede.auditoria import auditar_missao_conectada
    r = ex.resultado
    a = dict(registros=r.registros, livro=r.livro, modelo=ex.modelo, configuracao_rede=ex.configuracao_rede,
             verdade=ex.verdade, anexos=r.anexos_3c3, registros_3c0=r.registros_3c0, registro_rede=r.registro_rede)
    a.update(kw)
    return auditar_missao_conectada(r.registro_missao, **a)


def analitica(ex, **kw):
    from ems_v2.rede.auditoria import auditar_missao_conectada_analitica
    r = ex.resultado
    a = dict(modelo=ex.modelo, configuracao_rede=ex.configuracao_rede, verdade=ex.verdade)
    a.update(kw)
    return auditar_missao_conectada_analitica(r.registro_missao, r.registros, r.livro, **a)


def erros(rel):
    return {c.codigo for c in rel.constatacoes if c.severidade == "erro"}


def reprovada_so_documental(rel, *codigos):
    """A falha é DOCUMENTAL: balanço e custos continuam numericamente corretos."""
    assert not rel.aceito and not rel.integridade_documental_certificada and rel.escopo == "integral"
    assert rel.verificacoes["balanco"] and rel.verificacoes["custos"] and not rel.verificacoes["documental"]
    assert set(codigos) <= erros(rel), (codigos, erros(rel))


def test_c02_missao_valida_aceita_pela_auditoria_integral(g11):
    rel = integral(g11)
    assert rel.aceito and rel.escopo == "integral" and rel.integridade_documental_certificada, erros(rel)
    assert rel.verificacoes["documental"]


def test_c02_modo_analitico_parcial_rotulado_nunca_certifica(g11):
    rel = analitica(g11)
    assert rel.aceito and rel.escopo == "analitica_parcial" and rel.integridade_documental_certificada is False
    assert "documental" not in rel.verificacoes


@pytest.mark.parametrize("falta", ("anexos", "registros_3c0", "registro_rede"))
def test_c02_integral_sem_artefatos_reprova(g11, falta):
    reprovada_so_documental(integral(g11, **{falta: None}), "auditoria_integral_incompleta")


def test_c02_auditoria_integral_exige_os_argumentos_documentais():
    from ems_v2.rede.auditoria import auditar_missao_conectada
    with pytest.raises(TypeError):
        auditar_missao_conectada(None, (), None, None, None)          # keyword obrigatórios, sem padrão


def test_c02_registro_3c0_de_outra_execucao(g11):
    r0 = list(g11.resultado.registros_3c0)
    reprovada_so_documental(integral(g11, registros_3c0=(r0[1],) + tuple(r0[1:])), "artefato_de_outra_execucao",
                            "selo_registro_3c0_divergente")
    from ems_v2.rede import experimentos as X
    outra = X.g5_erro_positivo_demanda().resultado.registros_3c0[0]
    reprovada_so_documental(integral(g11, registros_3c0=(outra,) + tuple(r0[1:])), "artefato_de_outra_execucao")


def test_c02_anexo_alterado_e_reselado(g11):
    from ems_v2.ponte.canonico import sha256
    an = list(g11.resultado.anexos_3c3)
    c = an[1].conteudo
    p0 = replace(c.passos_pcc[0], importacao_medida_kW=(c.passos_pcc[0].importacao_medida_kW or 0.0) + 0.5)
    a2 = replace(an[1], conteudo=replace(c, passos_pcc=(p0,) + c.passos_pcc[1:]))
    a2 = replace(a2, selo=sha256(replace(a2, selo="")))
    reprovada_so_documental(integral(g11, anexos=(an[0], a2, *an[2:])), "anexo_3c3_invalido",
                            "selo_anexo_3c3_divergente")


def test_c02_selo_de_janela_diferente_do_registro_historico(g11):
    from ems_v2.ponte.registro import selar_registro
    r0 = list(g11.resultado.registros_3c0)
    outro = selar_registro(replace(r0[2], selo="", criado_utc="2030-01-01T00:00:00+00:00"))   # válido isoladamente
    rel = integral(g11, registros_3c0=(*r0[:2], outro, *r0[3:]))
    reprovada_so_documental(rel, "selo_registro_3c0_divergente")


def test_c02_modelo_pcc_substituido_por_limites_mais_amplos(g11):
    m = g11.modelo
    largo = replace(m, pcc=replace(m.pcc, limite_importacao=replace(
        m.pcc.limite_importacao, valores=tuple(v + 10.0 for v in m.pcc.limite_importacao.valores))))
    assert largo.compromisso == m.compromisso                         # mesmo núcleo 3C-1
    assert analitica(g11, modelo=largo).aceito                        # os mesmos fluxos continuam reproduzíveis
    reprovada_so_documental(integral(g11, modelo=largo), "modelo_3c3_divergente")


def test_c02_politica_economica_substituida_com_os_mesmos_custos(g11):
    crd = g11.configuracao_rede
    # sem a revisão r1 entre as tarifas de decisão: o custo REALIZADO registrado (liquidação) não muda
    sub = replace(crd, tarifas_decisao=tuple(p for p in crd.tarifas_decisao if p.revisao == 0))
    assert analitica(g11, configuracao_rede=sub).aceito
    reprovada_so_documental(integral(g11, configuracao_rede=sub), "configuracao_rede_divergente")
    sub2 = replace(crd, politica_ajuste=replace(crd.politica_ajuste, justificativa="outra política declarada"))
    assert analitica(g11, configuracao_rede=sub2).aceito
    reprovada_so_documental(integral(g11, configuracao_rede=sub2), "configuracao_rede_divergente")


def test_c02_troca_de_evidencias_entre_duas_janelas(g11):
    r = g11.resultado
    an, r0 = list(r.anexos_3c3), list(r.registros_3c0)
    reprovada_so_documental(integral(g11, anexos=(an[1], an[0], *an[2:]), registros_3c0=(r0[1], r0[0], *r0[2:])),
                            "artefato_de_outra_execucao", "selo_anexo_3c3_divergente", "anexos_3c3_divergentes")
    reprovada_so_documental(integral(g11, anexos=tuple(an[:-1])), "anexos_3c3_em_numero_incoerente")


def test_c02_registro_de_missao_de_rede_adulterado(g11):
    from ems_v2.mpc.registro import selar
    rr = g11.resultado.registro_rede
    rr2 = selar(replace(rr, hash_modelo_3c3="0" * 64, selo=""))
    reprovada_so_documental(integral(g11, registro_rede=rr2), "modelo_3c3_divergente")
    rr3 = replace(rr, totais={**rr.totais, "E_importada_kWh": rr.totais["E_importada_kWh"] + 1})
    reprovada_so_documental(integral(g11, registro_rede=rr3), "registro_rede_adulterado")


def test_c02_janela_sem_plano_nao_exige_artefatos():
    _solver()
    from ems_v2.mpc.experimentos import ResolvedorComFalha, resultado_sem_solucao
    from ems_v2.rede import experimentos as X
    base = X.ResolvedorMILP3C3(X.config_solver())
    ex = X.executar("c02-sem-plano", K=4, N=2, m=1, com_fc=False, modelo_kw={"e0": 0.0}, tipo="tabela",
                    resolvedor=ResolvedorComFalha(base, 1, resultado_sem_solucao))
    r = ex.resultado
    assert [x.conteudo.hash_plano is None for x in r.registros] == [False, True]
    assert len(r.anexos_3c3) == len(r.registros_3c0) == 1
    rel = integral(ex)
    assert rel.aceito and rel.integridade_documental_certificada, erros(rel)
    # mas um artefato a mais (para a janela sem plano) é reprovado
    reprovada_so_documental(integral(ex, anexos=r.anexos_3c3 * 2), "anexos_3c3_em_numero_incoerente")


@pytest.mark.parametrize("ruim", (-5.0, True, "20"), ids=repr)
def test_c01_comando_invalido_na_planta_e_falha_de_dados_classificada(monkeypatch, ruim):
    """Na planta, um comando com consigna do PCC inválida (JSON-representável) é recusado como DADOS ⇒ ``erro_dados``.
    (NaN/Inf nem chegam a um comando: o JSON canônico do hash do comando os proíbe, e ``plano_de_resultado_3c3``
    recusa NaN/Inf/negativos/bool antes — ver ``test_c01_plano_de_resultado_sem_recorte_silencioso``.)"""
    _solver()
    from ems_v2.rede import experimentos as X
    from ems_v2.rede.mpc import ControladorMPCConectado
    orig = ControladorMPCConectado._consignas_comando

    def corromper(self, plano, pc, i):
        out = orig(self, plano, pc, i)
        out[f"{PCC}|P_imp"] = ruim
        return out
    monkeypatch.setattr(ControladorMPCConectado, "_consignas_comando", corromper)
    ex = X.executar(f"c01-planta-{ruim!r}", K=4, N=2, m=1, com_fc=False, modelo_kw={"e0": 0.0}, tipo="tabela")
    r = ex.resultado
    assert r.situacao == "interrompida" and r.classe_falha == "erro_dados"
    assert r.registro_missao.conteudo.intervalos_aplicados == 0 and ex.entorno.parado
    assert any("intercambio_programado_invalido" in d for c in r.confirmacoes for d in c.detalhe)


def test_c01_nan_nao_e_representavel_num_comando():
    from ems_v2.mpc.entorno import ComandoIntervalo, hash_comando
    c = ComandoIntervalo("m" * 32, 0, 0, "2026-01-01T00:00:00+00:00", "h" * 64, 0, {f"{PCC}|P_imp": float("nan")},
                         "2026-01-01T00:00:00+00:00")
    with pytest.raises(ValueError):
        hash_comando(c)
