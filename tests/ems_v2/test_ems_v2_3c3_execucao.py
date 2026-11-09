"""Piso 3C-3 — executor conectado, política de ajuste do PCC, liquidação e anexo selado (SEM solver).

O plano é ANALÍTICO (despacho do caso G1 escrito à mão: FV 10 kW, importação programada 20 kW; Δ = 15 min, h = 0,25):
não depende do Pyomo. A planta é o dublê ALGÉBRICO conectado — não é modelo físico nem controle primário.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from ems_v2 import MOTOR_ID
from ems_v2 import fixtures_3c3 as F
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.fixtures import disp, pot, proc
from ems_v2.ponte.cenario import Realizacao, SerieRecurso
from ems_v2.ponte.compromisso import plano_de_resultado_3c1
from ems_v2.ponte.execucao import estado_inicial_de_entrada, executar
from ems_v2.ponte.registro import (Discretizacao, ReferenciaOrigem, RegistroExecucaoEMS, selar_registro,
                                   valor_futuro_nao_implementado)
from ems_v2.ponte.registro_3c1 import verificar_anexo_3c1
from ems_v2.rede import FORMULACAO_3C3
from ems_v2.rede.contrato import hash_entrada_3c3
from ems_v2.rede.execucao import (ExecutorAlgebricoConectado3C3, PoliticaAjustePCC, contabilidade_realizada_3c3,
                                  desvios_intercambio, plano_de_resultado_3c3, programa_de_plano,
                                  validar_politica_ajuste)
from ems_v2.rede.mpc import registros_passos_pcc
from ems_v2.rede.registro import (hashes_para_registro_3c3, montar_anexo_3c3, preparar_conteudo_anexo_3c3,
                                  verificar_anexo_3c3)

pytestmark = pytest.mark.synthetic_algebraic
UID = "0" * 32


def res_g1(e, imp=(20.0, 20.0), exp=(0.0, 0.0)):
    return SimpleNamespace(aceito=True, estado_despacho="aceito_otimo", classificacao="otimo", motor_id=MOTOR_ID,
                           versao_formulacao=FORMULACAO_3C3, hash_entrada=hash_entrada_3c3(e),
                           despacho={"renovaveis": {"syn-fv": {"P_R": (10.0, 10.0), "C_oper": (0.0, 0.0)}},
                                     "baterias": {}, "geradores": {}, "demandas": {"syn-carga": {"ell": (0.0, 0.0)}},
                                     "descarte": None},
                           custos_modelo={"curtailment_operacional": 0.0, "importacao_rede": 8.0,
                                          "exportacao_rede": 0.0, "total": 8.0},
                           memoria_terminal=(), eventos={}, intercambio={"P_imp": imp, "P_exp": exp}, hash_tarifas={})


def pol(tipo="ajuste_local_algebrico", inj="limitada_pela_disponibilidade", liq="energia_medida_tarifa_aplicavel",
        c_liq=(0.8, 0.8), c_exp=(0.1, 0.1)):
    dp = dn = None
    if liq == "desvio_diferenciado":
        dp = F.tarifa("desvio_positivo", [1.5, 1.5], "liq")
        dn = F.tarifa("desvio_negativo", [0.1, 0.1], "liq")
    return PoliticaAjustePCC(tipo, inj, liq, F.tarifa("importacao", list(c_liq), "liq", natureza="aplicavel_liquidacao"),
                             F.tarifa("exportacao", list(c_exp), "liq", natureza="aplicavel_liquidacao"), dp, dn,
                             proc("ajuste"), "ensaio")


def real(L=(30, 30), A=(10, 10), a=(1, 1), med=None):
    s = [SerieRecurso("syn-carga", "potencia", pot(list(L), 15, "r")),
         SerieRecurso("syn-fv", "potencia", pot(list(A), 15, "r")),
         SerieRecurso("syn-fv", "disponibilidade", disp([1, 1], 15, "r").serie),
         SerieRecurso("syn-pcc", "disponibilidade", disp(list(a), 15, "r").serie)]
    if med is not None:
        s += [SerieRecurso(F.MED_IMP, "potencia", pot(list(med[0]), 15, "r")),
              SerieRecurso(F.MED_EXP, "potencia", pot(list(med[1]), 15, "r"))]
    return Realizacao("syn-r", "sintetica", tuple(s), proc("r"))


def rodar(e=None, politica=None, medicao=False, **kw):
    e = e or F.caso_g1()
    if medicao:
        e = replace(e, pcc=F.pcc(2, "G1", imp=25.0, medidores=True))
    p, pr = plano_de_resultado_3c3(res_g1(e), e)
    ex = ExecutorAlgebricoConectado3C3(e, {}, politica or pol(), programa=programa_de_plano(pr), exigir_medicao=medicao)
    r = real(**kw)
    t = executar(p, estado_inicial_de_entrada(e.base), ex, r, execucao_uid=UID)
    return e, p, pr, t, r


def cods(t):
    return {c.codigo for c in t.constatacoes}


# ------------------------------------------------------------------------------------------- plano
def test_plano_3c3_nao_se_faz_passar_por_3c1():
    e = F.caso_g1()
    p, pr = plano_de_resultado_3c3(res_g1(e), e)
    assert p.versao_formulacao == FORMULACAO_3C3 and p.hash_entrada == hash_entrada_3c3(e)
    assert pr.importacao_programada_kW == (20.0, 20.0) and pr.hash_plano and pr.modo_conexao == "conectado"
    with pytest.raises(ContratoInvalido) as exc:
        plano_de_resultado_3c1(res_g1(e), e.compromisso)
    assert "plano_entrada_divergente" in exc.value.codigos
    with pytest.raises(ContratoInvalido):
        plano_de_resultado_3c3(SimpleNamespace(**{**vars(res_g1(e)), "aceito": False}), e)


# ------------------------------------------------------------------------------------------- G5 … G8 (passo)
def test_realizacao_igual_ao_previsto_intercambio_realizado_igual_ao_programado():
    e, p, pr, t, r = rodar()
    assert t.situacao == "concluida"
    assert [x.aplicado["syn-pcc|P_imp"] for x in t.passos] == [20.0, 20.0]
    assert [d.desvio_kW for d in desvios_intercambio(pr, t)] == [0.0, 0.0]


def test_g5_erro_positivo_de_demanda_absorvido_pelo_ajuste_do_pcc():
    e, p, pr, t, r = rodar(L=(34, 30))
    assert t.situacao == "concluida" and t.passos[0].aplicado["syn-pcc|P_imp"] == 24.0
    d = desvios_intercambio(pr, t)
    assert (d[0].liquido_programado_kW, d[0].liquido_realizado_kW, d[0].desvio_kW) == (20.0, 24.0, 4.0)
    c = contabilidade_realizada_3c3(e, p, pr, t, r, pol())
    assert c.custo.total_R == pytest.approx(0.25 * 0.8 * 44) and c.indicadores["E_desvio_positivo_kWh"] == 1.0


def test_g6_erro_negativo_reduz_importacao_ou_exporta_se_autorizado():
    _, _, _, t, _ = rodar(L=(26, 30))
    assert t.passos[0].aplicado["syn-pcc|P_imp"] == 16.0
    e, p, pr, t, r = rodar(L=(5, 30))
    assert (t.passos[0].aplicado["syn-pcc|P_imp"], t.passos[0].aplicado["syn-pcc|P_exp"]) == (0.0, 5.0)
    c = contabilidade_realizada_3c3(e, p, pr, t, r, pol())
    comp = {x.termo: x.valor_R for x in c.custo.componentes}
    assert comp["importacao_rede"] == pytest.approx(0.25 * 0.8 * 20) and comp["exportacao_rede"] == pytest.approx(
        -0.25 * 0.1 * 5)
    assert c.indicadores["gasto_importacao_R"] == pytest.approx(4.0) and c.indicadores["receita_exportacao_R"] == \
        pytest.approx(0.125)


def test_g6_exportacao_proibida_falha_classificada_sem_recorte_do_fv():
    e1 = F.caso_g1()
    e1 = replace(e1, pcc=replace(e1.pcc, sentidos_permitidos="somente_importacao", limite_exportacao=None),
                 economia=replace(e1.economia, termos=("importacao_rede",), tarifa_exportacao=None,
                                  remuneracao_exportacao="nao_aplicavel"))
    po = replace(pol(), tarifa_liquidacao_exportacao=None)
    _, _, _, t, _ = rodar(e1, po, L=(5, 30))
    assert t.situacao == "interrompida_inexequivel" and "exportacao_proibida" in cods(t) and not t.passos
    assert t.estados[-1].indice_fronteira == 0                         # nada aplicado, nenhum estado alterado


def test_g7_renovavel_superestimado_injecao_limitada_e_desvio_fisico_registrado():
    e, p, pr, t, r = rodar(A=(6, 10))
    x = t.passos[0]
    assert x.aplicado["syn-fv|P_R"] == 6.0 and x.aplicado["syn-pcc|P_imp"] == 24.0
    dv = [d for d in t.desvios if d.grandeza == "P_R" and d.indice == 0][0]
    assert (dv.planejado, dv.realizado, dv.desvio) == (10.0, 6.0, -4.0)
    c = contabilidade_realizada_3c3(e, p, pr, t, r, pol())
    assert c.indicadores["E_curtailment_kWh"] == 0.0                   # não vira vertimento nem energia criada
    # política 'consigna_exata' (regra 3C-0): a mesma realização é inexequível
    _, _, _, t2, _ = rodar(politica=pol(inj="consigna_exata"), A=(6, 10))
    assert t2.situacao == "interrompida_inexequivel" and "consigna_inexequivel_renovavel" in cods(t2)


def test_renovavel_acima_da_consigna_nao_e_injetado_automaticamente():
    _, _, _, t, _ = rodar(A=(25, 10))
    assert t.passos[0].aplicado["syn-fv|P_R"] == 10.0 and t.passos[0].aplicado["syn-pcc|P_imp"] == 20.0


def test_g8_saturacao_e_pcc_indisponivel_sem_respaldo_oculto():
    _, _, _, t, _ = rodar(L=(50, 30))                                 # exigiria 40 > P̄_imp = 25
    assert t.situacao == "interrompida_inexequivel" and "pcc_saturado_importacao" in cods(t)
    _, _, _, t, _ = rodar(a=(0, 1))
    assert t.situacao == "interrompida_inexequivel" and "pcc_indisponivel" in cods(t)


def test_sem_ajuste_qualquer_desvio_e_inexequivel():
    _, _, _, t, _ = rodar(politica=pol(tipo="sem_ajuste"), L=(34, 30))
    assert t.situacao == "interrompida_inexequivel" and "balanco_realizado_violado" in cods(t)
    _, _, _, t, _ = rodar(politica=pol(tipo="sem_ajuste"))
    assert t.situacao == "concluida"


def test_dados_ausentes_ou_invalidos_do_pcc_sao_erro_de_dados():
    e = F.caso_g1()
    p, pr = plano_de_resultado_3c3(res_g1(e), e)
    ex = ExecutorAlgebricoConectado3C3(e, {}, pol(), programa=programa_de_plano(pr))
    r = real()
    sem = replace(r, series=tuple(s for s in r.series if s.uid != "syn-pcc"))
    t = executar(p, estado_inicial_de_entrada(e.base), ex, sem, execucao_uid=UID)
    assert t.situacao == "erro_dados" and "realizacao_ausente" in cods(t)
    ex2 = ExecutorAlgebricoConectado3C3(e, {}, pol(), programa={})          # sem programa: nada é presumido
    t = executar(p, estado_inicial_de_entrada(e.base), ex2, r, execucao_uid=UID)
    assert t.situacao == "erro_dados" and "programa_pcc_ausente" in cods(t)


def test_medicao_obrigatoria_na_conciliacao_e_divergencia_detectada():
    _, _, _, t, _ = rodar(medicao=True)
    assert t.situacao == "erro_dados" and "medicao_ausente" in cods(t)
    _, _, _, t, _ = rodar(medicao=True, L=(34, 30), med=((24, 20), (0, 0)))
    assert t.situacao == "concluida"
    _, _, _, t, _ = rodar(medicao=True, L=(34, 30), med=((20, 20), (0, 0)))
    assert t.situacao == "interrompida_inexequivel" and "intercambio_medido_divergente" in cods(t)


def test_isolado_nenhum_intercambio_e_politica_sem_ajuste_obrigatoria():
    e = F.caso_isolado_equivalente()
    assert "ajuste_em_operacao_isolada" in {c.codigo for c in validar_politica_ajuste(pol(), e)}
    assert not validar_politica_ajuste(PoliticaAjustePCC("sem_ajuste", "limitada_pela_disponibilidade",
                                                         "energia_medida_tarifa_aplicavel", None, None, None, None,
                                                         proc("x"), "isolado"), e)


def test_politica_de_liquidacao_validada_sem_padrao():
    e = F.caso_g1()
    c = {x.codigo for x in validar_politica_ajuste(replace(pol(), tarifa_liquidacao_importacao=None), e)}
    assert "tarifa_liquidacao_ausente" in c
    prev = F.tarifa("importacao", [0.8, 0.8], "liq", natureza="prevista")
    c = {x.codigo for x in validar_politica_ajuste(replace(pol(), tarifa_liquidacao_importacao=prev), e)}
    assert "preco_previsto_na_liquidacao" in c
    c = {x.codigo for x in validar_politica_ajuste(replace(pol(), tipo="automatico"), e)}
    assert "tipo_ajuste_invalido" in c
    c = {x.codigo for x in validar_politica_ajuste(replace(pol(), liquidacao="desvio_diferenciado"), e)}
    assert "tarifa_liquidacao_ausente" in c                                   # desvios exigem perfis declarados


def test_liquidacao_desvio_diferenciado_valores_analiticos():
    e, p, pr, t, r = rodar(politica=pol(liq="desvio_diferenciado"), L=(34, 26))
    c = contabilidade_realizada_3c3(e, p, pr, t, r, pol(liq="desvio_diferenciado"))
    comp = {x.termo: x.valor_R for x in c.custo.componentes}
    assert comp["importacao_rede"] == pytest.approx(0.25 * 0.8 * 40)              # programado aos preços de liquidação
    assert comp["desvio_rede"] == pytest.approx(0.25 * (1.5 * 4 - 0.1 * 4))        # +4 kW e −4 kW


# ------------------------------------------------------------------------------------------- anexo 3C-3
def _registro(e, p, t, c, hashes):
    o = ReferenciaOrigem("syn-microrrede-fixture", None, 1, "a" * 64, "b" * 64, "c" * 64, e.base.cenario_uid, 1, "d" * 64)
    return selar_registro(RegistroExecucaoEMS(1, UID, "2026-01-01T00:00:00+00:00", o, {}, hashes,
                                              Discretizacao(p.inicio_utc, p.delta_s, p.N, p.N, p.N), None, p,
                                              t.estados[0], t.estados[-1], t.situacao, t.checkpoints[-1], {},
                                              c.custo, dict(p.custo_objetivo_planejado),
                                              valor_futuro_nao_implementado(p.N), "exito", "ensaio",
                                              {}, (), {}))


def test_anexo_3c3_selado_comprometido_e_adulteracao_detectada():
    e, p, pr, t, r = rodar(medicao=True, L=(34, 30), med=((24, 20), (0, 0)))
    po = pol()
    c = contabilidade_realizada_3c3(e, p, pr, t, r, po)
    passos = registros_passos_pcc(e, p, pr, t, r, {}, po, exigir_medicao=True)
    cont = preparar_conteudo_anexo_3c3(e, p, pr, t, r, {}, po, passos, c)
    reg = _registro(e, p, t, c, hashes_para_registro_3c3(cont))
    a = montar_anexo_3c3(reg, cont)
    assert verificar_anexo_3c3(a, reg) == []
    assert [x.importacao_realizada_kW for x in a.conteudo.passos_pcc] == [24.0, 20.0]
    # liquidação alterada e re-selada: compromisso do registro detecta
    from ems_v2.ponte.canonico import sha256
    l0 = replace(a.conteudo.liquidacao[0], gasto_importacao_R=0.0)
    a2 = replace(a, conteudo=replace(a.conteudo, liquidacao=(l0,) + a.conteudo.liquidacao[1:]))
    a2 = replace(a2, selo=sha256(replace(a2, selo="")))
    assert "conteudo_anexo_divergente" in {x.codigo for x in verificar_anexo_3c3(a2, reg)}
    # política de ajuste trocada
    a3 = replace(a, conteudo=replace(a.conteudo, politica_ajuste=replace(po, tipo="sem_ajuste")))
    assert {"hash_3c3_divergente", "anexo_adulterado"} <= {x.codigo for x in verificar_anexo_3c3(a3, reg)}
    # registro sem compromisso
    reg2 = _registro(e, p, t, c, {})
    with pytest.raises(ContratoInvalido):
        montar_anexo_3c3(reg2, cont)
    # nunca um anexo 3C-1 para um plano 3C-3 (o verificador 3C-1 recusa)
    from ems_v2.ponte.registro_3c1 import AnexoExecucao3C1, ConteudoAnexo3C1
    falso = AnexoExecucao3C1(ConteudoAnexo3C1(2, "v1.1-3C-1", UID, p.hash_entrada, (), None, (), (), {}), reg.selo)
    assert "anexo_de_outra_entrada" in {x.codigo for x in verificar_anexo_3c1(falso, reg)}
