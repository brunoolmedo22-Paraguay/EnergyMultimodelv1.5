"""Piso 3C-3 — MPC conectado de ponta a ponta com HiGHS real (G5–G8, G11–G14 e comparação open-loop × MPC).

Simulação causal de laço fechado ALGÉBRICA conectada sobre fixtures SINTÉTICAS (``ems_v2.fixtures_3c3``): não é
validação física, fluxo AC, controle primário nem fatura real. Valores esperados de G5–G8: docstrings de
``ems_v2.rede.experimentos`` (analíticos). Sem Pyomo/HiGHS: pulados.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

from ems_v2 import fixtures_3c2 as F2  # noqa: E402
from ems_v2 import fixtures_3c3 as F  # noqa: E402
from ems_v2.diagnostics import ContratoInvalido  # noqa: E402
from ems_v2.mpc.auditoria import verificar_nao_antecipatividade  # noqa: E402
from ems_v2.mpc.entorno import PerturbacaoCanal  # noqa: E402
from ems_v2.mpc.orquestrador import executar_missao_simulada  # noqa: E402
from ems_v2.mpc.persistencia import comandos_aplicados  # noqa: E402
from ems_v2.rede import experimentos as X  # noqa: E402
from ems_v2.rede.auditoria import auditar_missao_conectada, auditar_missao_conectada_analitica  # noqa: E402
from ems_v2.rede.comparadores import comparar_missoes_3c3  # noqa: E402
from ems_v2.rede.mpc import ControladorMPCConectado, ResolvedorMILP3C3, verificar_registro_rede  # noqa: E402
from ems_v2.rede.persistencia import retomar_controlador_conectado  # noqa: E402
from ems_v2.rede.registro import verificar_anexo_3c3  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
PCC = F.PCC


def aud(ex, **kw):
    r = ex.resultado
    a = dict(registros=r.registros, livro=r.livro, modelo=ex.modelo, configuracao_rede=ex.configuracao_rede,
             verdade=ex.verdade, anexos=r.anexos_3c3, registros_3c0=r.registros_3c0, registro_rede=r.registro_rede)
    a.update(kw)
    return auditar_missao_conectada(r.registro_missao, **a)


def erros(rel):
    return [c.codigo for c in rel.constatacoes if c.severidade == "erro"]


def imp_exp(ex):
    return [(p.aplicado[f"{PCC}|P_imp"], p.aplicado[f"{PCC}|P_exp"]) for r in ex.resultado.registros
            for p in r.conteudo.passos]


def custo(ex):
    return ex.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R


@pytest.fixture(scope="module")
def g11():
    return X.g11_mpc_conectado()


# ------------------------------------------------------------------------------------------- G5 … G8
def test_g5_erro_positivo_de_demanda_ajuste_programado_x_realizado():
    ex = X.g5_erro_positivo_demanda()
    r = ex.resultado
    assert r.situacao == "encerrada" and r.registro_missao.conteudo.desfecho == "concluida"
    assert imp_exp(ex) == [(20.0, 0.0), (24.0, 0.0), (20.0, 0.0), (20.0, 0.0)]
    assert custo(ex) == pytest.approx(12.6) and r.registro_missao.conteudo.custo_planejado_prefixos_R == pytest.approx(12.0)
    a1 = r.anexos_3c3[1].conteudo
    assert (a1.desvios[0].liquido_programado_kW, a1.desvios[0].liquido_realizado_kW) == (20.0, 24.0)
    assert a1.passos_pcc[0].ajuste == "ajuste_local_algebrico" and a1.passos_pcc[0].importacao_medida_kW == 24.0
    assert r.registro_rede.totais["E_desvio_positivo_kWh"] == pytest.approx(1.0)
    rel = aud(ex)
    assert rel.aceito, erros(rel)


def test_g6_erro_negativo_reduz_importacao_e_exporta_quando_autorizado():
    ex = X.g6_erro_negativo_demanda()
    assert imp_exp(ex)[1] == (16.0, 0.0) and custo(ex) == pytest.approx(11.4)
    ex = X.g6_erro_negativo_demanda(L1=5.0)
    assert imp_exp(ex)[1] == (0.0, 5.0) and custo(ex) == pytest.approx(8.75)
    assert ex.resultado.registro_rede.totais["receita_exportacao_R"] == pytest.approx(0.25)
    assert aud(ex).aceito


def test_g6_exportacao_proibida_interrompe_classificada():
    ex = X.g6_erro_negativo_demanda("somente_importacao", 5.0)
    r = ex.resultado
    assert r.situacao == "interrompida" and r.classe_falha == "consigna_inexequivel"
    assert r.registro_missao.conteudo.intervalos_aplicados == 1 and r.registro_missao.conteudo.estado_final.indice_fronteira == 1
    conf = [c for c in r.confirmacoes if c.situacao != "aplicada"]
    assert any("exportacao_proibida" in d for c in conf for d in c.detalhe)
    assert aud(ex).aceito


def test_g7_renovavel_superestimado_injecao_limitada_e_pcc_compensa():
    ex = X.g7_renovavel_superestimado()
    assert imp_exp(ex)[1] == (26.0, 0.0) and custo(ex) == pytest.approx(12.9)
    p1 = ex.resultado.registros[1].conteudo.passos[0]
    assert p1.aplicado["syn-fv|P_R"] == 4.0 and p1.entorno_observado["syn-fv|potencia"] == 4.0
    a = ex.resultado.anexos_3c3[1].conteudo.passos_pcc[0]
    assert (a.renovavel_consigna_kW, a.renovavel_efetiva_kW) == (10.0, 4.0)
    assert aud(ex).aceito


def test_g8_saturacao_do_pcc_sem_respaldo_oculto():
    ex = X.g8_saturacao_pcc()
    r = ex.resultado
    assert r.situacao == "interrompida" and r.classe_falha == "consigna_inexequivel"
    assert any("pcc_saturado_importacao" in d for c in r.confirmacoes for d in c.detalhe)
    assert r.registro_missao.conteudo.intervalos_aplicados == 1 and custo(ex) == pytest.approx(3.0)
    assert ex.entorno.parado and aud(ex).aceito


# ------------------------------------------------------------------------------------------- G11
def test_g11_mpc_conectado_varias_janelas(g11):
    r = g11.resultado
    assert r.situacao == "encerrada" and len(r.registros) == 4 and all(
        x.conteudo.aceitacao == "aceito_otimo" for x in r.registros)
    rel = aud(g11)
    assert rel.aceito, erros(rel)
    assert verificar_registro_rede(r.registro_rede, r.registro_missao, r.anexos_3c3) == []
    for a, r0 in zip(r.anexos_3c3, r.registros_3c0):
        assert verificar_anexo_3c3(a, r0) == []
    # revisão tarifária CAUSAL: r0 nas decisões em τ_0, τ_2; r1 (emitida em τ_4) em τ_4, τ_6
    revs = [a.conteudo.plano_rede for a in r.anexos_3c3]
    h = [x.hash_tarifas_decisao["importacao"] for x in revs]
    assert h[0] == h[1] != h[2] == h[3]
    # previsões reemitidas (demanda corrigida pela observação) e desvios = erro de demanda/FV no intervalo aplicado
    assert len({x.conteudo.hash_previsao for x in r.registros}) == 4
    for x in r.registros:
        for p in x.conteudo.passos:
            en, ap = p.entorno_observado, p.aplicado
            exigido = en["syn-carga|potencia"] - ap["syn-fv|P_R"] - ap["syn-bess|P_d"] + ap["syn-bess|P_c"] - ap["syn-fc|p"]
            assert ap[f"{PCC}|P_imp"] - ap[f"{PCC}|P_exp"] == pytest.approx(exigido, abs=1e-9)
    # continuidade: estado inicial de cada janela = final EXECUTADO da anterior (banco e memória da PEMFC)
    c = [x.conteudo for x in r.registros]
    for a, b in zip(c, c[1:]):
        assert a.estados[-1] == b.estados[0]
    assert rel.verificacoes["estado_e_permanencias"] and rel.verificacoes["balanco"] and rel.verificacoes["custos"]
    t = [e.gerador(F2.FC).tempo_no_estado_s for e in [c[0].estados[0]] + [e for x in c for e in x.estados[1:]]]
    u = [c[0].estados[0].gerador(F2.FC).ligado] + [e.gerador(F2.FC).ligado for x in c for e in x.estados[1:]]
    for i in range(1, len(t)):                      # memória transportada: +Δ no mesmo estado, Δ após transição
        assert t[i] == (t[i - 1] + 900 if u[i] == u[i - 1] else 900)
    # custo realizado ≠ planejado; planejado de janelas inteiras nunca somado; valor futuro não contabilizado
    rm = r.registro_missao.conteudo
    assert rm.valor_futuro.contabilizado_como_custo is False and rm.valor_futuro.valor_R is None
    assert rm.custo_realizado_acumulado.total_R == pytest.approx(sum(x.custos.realizado.total_R for x in c))
    termos = {x.termo for x in rm.custo_realizado_acumulado.componentes}
    assert {"importacao_rede", "exportacao_rede"} <= termos


def test_g11_reproducao_determinista(g11):
    ex2 = X.g11_mpc_conectado()
    assert ex2.resultado.registro_missao.impressao_deterministica == g11.resultado.registro_missao.impressao_deterministica


def test_g11_nao_antecipatividade_por_intervencao():
    va = F.verdade_mpc(X.L_G11, X.PV_REAL_G11)
    L2 = X.L_G11[:4] + [10.0, 50.0, 10.0, 40.0]
    vb = F.verdade_mpc(L2, X.PV_REAL_G11)

    def run(v):
        ctrl, ent, *_ = X.montar("g11-intervencao", L_real=[s for s in v.serie("syn-carga", "potencia").serie.valores],
                                 pv_real=X.PV_REAL_G11)
        return executar_missao_simulada(ctrl, ent)
    res = verificar_nao_antecipatividade(run, va, vb, 4)
    assert res.nao_antecipativo and res.janelas_comparadas >= 3


# ------------------------------------------------------------------------------------------- G12
def test_g12_rede_disponivel_versus_isolado_factibilidade_nao_e_beneficio():
    r = X.g12_rede_vs_isolado()
    c, i = r["conectado"].resultado, r["isolado"].resultado
    assert c.situacao == i.situacao == "encerrada"
    assert i.registro_rede.totais["E_importada_kWh"] == 0.0 and all(
        p.aplicado.get(f"{PCC}|P_imp", 0.0) == 0.0 for x in i.registros for p in x.conteudo.passos)
    assert aud(r["isolado"]).aceito and aud(r["conectado"]).aceito
    cmp = comparar_missoes_3c3(r["isolado"], r["conectado"], rotulo_a="isolado", rotulo_b="conectado")
    assert cmp.tipo == "contraste_de_topologia" and not cmp.comparavel_para_superioridade
    assert "E_final_kWh[syn-bess]" in cmp.linhas and "obrigacoes_pendentes_s" in cmp.linhas
    # com erro de demanda: o isolado é interrompido (nenhum recurso de equilíbrio), o conectado conclui
    r2 = X.g12_rede_vs_isolado(L_real=X.L_G11)
    assert r2["isolado"].resultado.classe_falha == "consigna_inexequivel"
    assert r2["conectado"].resultado.situacao == "encerrada"


def test_missao_isolada_nao_vira_conectada_e_observacao_do_pcc_rejeitada():
    ex = X.g12_rede_vs_isolado()["isolado"]
    ctrl = ex.controlador
    assert PCC not in ctrl.livro.recursos
    from ems_v2.mpc.observacoes import Observacao
    o = Observacao("ev-x", "fonte-x", 999, ctrl.cfg.identidade.microrrede_uid, PCC, "disponibilidade", "1",
                   "2026-01-01T00:00:00+00:00", "2026-01-01T00:15:00+00:00", 1.0, "2026-01-01T03:00:00+00:00",
                   F2.proc("x"))
    assert ctrl.livro.registrar(o).classificacao == "rejeitada_recurso_desconhecido"
    # trocar o modelo para conectado na retomada é recusado (hash do modelo 3C-3 comprometido no vínculo)


# ------------------------------------------------------------------------------------------- G13
def test_g13_retomada_de_checkpoint_identidade_custos_observacoes_e_estados(tmp_path, g11):
    kw = dict(L_real=X.L_G11, pv_real=X.PV_REAL_G11, tarifas=F.tarifas_decisao(8, revisao_1_em="2026-01-01T01:00:00+00:00"))
    ctrl, ent, mod, ver, pol, crd = X.montar("g11-mpc-conectado", diretorio=tmp_path, **kw)
    executar_missao_simulada(ctrl, ent, max_janelas=2, finalizar=False)
    assert ctrl.k == 4
    ctrl2, pt = retomar_controlador_conectado(tmp_path, ctrl.cfg, mod, ctrl.provedor, ResolvedorMILP3C3(X.config_solver()),
                                              ctrl.fontes, crd, identificadores_verdade=ctrl.id_verdade,
                                              fontes_verdade=ctrl.fontes_verdade)
    assert len(ctrl2.anexos_3c3) == 2 and len(ctrl2.registros_3c0) == 2 and ctrl2.estado == ctrl.estado
    _, ent2, *_ = X.montar("g11-mpc-conectado", **kw)
    ent2.reconstituir(comandos_aplicados(pt), ctrl2.instante_atual)
    res = executar_missao_simulada(ctrl2, ent2)
    rc = g11.resultado
    assert res.registro_missao.impressao_deterministica == rc.registro_missao.impressao_deterministica
    assert res.registro_rede.totais == rc.registro_rede.totais
    assert [a.conteudo for a in res.anexos_3c3] == [a.conteudo for a in rc.anexos_3c3]
    assert (tmp_path / f"{ctrl.cfg.identidade.missao_uid}.rede.missao.mpc3c3.json").exists()


def test_g13_retomada_recusa_artefatos_adulterados_e_troca_de_configuracao(tmp_path):
    ctrl, ent, mod, ver, pol, crd = X.montar("g13-adulteracao", diretorio=tmp_path, L_real=X.L_G11)
    executar_missao_simulada(ctrl, ent, max_janelas=2, finalizar=False)
    args = (tmp_path, ctrl.cfg, mod, ctrl.provedor, ResolvedorMILP3C3(X.config_solver()), ctrl.fontes)
    # outra configuração de rede (outra política) ⇒ recusa
    crd2 = replace(crd, politica_ajuste=replace(crd.politica_ajuste, tipo="sem_ajuste"))
    with pytest.raises(ContratoInvalido) as exc:
        retomar_controlador_conectado(*args, crd2)
    assert "identidade_divergente" in exc.value.codigos
    # outro modo/PCC (isolado) ⇒ recusa
    with pytest.raises(ContratoInvalido):
        retomar_controlador_conectado(tmp_path, ctrl.cfg, replace(mod, pcc=replace(mod.pcc, contrato_uid="outro")),
                                      *args[3:], crd)
    # anexo 3C-3 adulterado ⇒ recusa
    alvo = next(Path(tmp_path).glob("*.ems3c3.json"))
    d = json.loads(alvo.read_text())
    d["conteudo"]["passos_pcc"][0]["importacao_realizada_kW"] += 1.0
    alvo.write_text(json.dumps(d))
    with pytest.raises(ContratoInvalido) as exc:
        retomar_controlador_conectado(*args, crd)
    assert "anexo_3c3_invalido" in exc.value.codigos


# ------------------------------------------------------------------------------------------- G14 (missão)
def test_g14_auditoria_rejeita_intercambio_tarifa_disponibilidade_e_custos_adulterados(g11):
    r = g11.resultado
    regs = list(r.registros)
    c = regs[1].conteudo
    p0 = c.passos[0]
    # intercâmbio aplicado alterado no conteúdo da janela (re-selado conteúdo, mas cadeia/selos quebram)
    p_alt = replace(p0, aplicado={**p0.aplicado, f"{PCC}|P_imp": p0.aplicado[f"{PCC}|P_imp"] + 2.0})
    regs_alt = regs[:1] + [replace(regs[1], conteudo=replace(c, passos=(p_alt,) + c.passos[1:]))] + regs[2:]
    rel = aud(g11, registros=regs_alt)
    assert not rel.aceito and {"conteudo_janela_adulterado", "balanco_observado_violado"} <= set(erros(rel))
    # tarifa de liquidação trocada: custo realizado não se reproduz
    pol2 = replace(g11.politica, tarifa_liquidacao_importacao=F.tarifa(
        "importacao", [0.7] * 8, "x", natureza="aplicavel_liquidacao"))
    rel = auditar_missao_conectada_analitica(r.registro_missao, r.registros, r.livro, g11.modelo,
                                             replace(g11.configuracao_rede, politica_ajuste=pol2))
    assert not rel.aceito and "custo_rede_nao_reproduzido" in erros(rel) and rel.escopo == "analitica_parcial"
    # disponibilidade observada do PCC adulterada para 0 num passo com fluxo
    for i, x in enumerate(regs):
        for j, p in enumerate(x.conteudo.passos):
            if max(p.aplicado[f"{PCC}|P_imp"], p.aplicado[f"{PCC}|P_exp"]) > 0:
                pa = replace(p, entorno_observado={**p.entorno_observado, f"{PCC}|disponibilidade": 0.0})
                cc = x.conteudo
                ra = regs[:i] + [replace(x, conteudo=replace(cc, passos=cc.passos[:j] + (pa,) + cc.passos[j + 1:]))] + \
                    regs[i + 1:]
                rel = aud(g11, registros=ra)
                assert "intercambio_com_pcc_indisponivel" in erros(rel)
                break
        else:
            continue
        break
    # anexo 3C-3 com liquidação adulterada
    a = r.anexos_3c3[0]
    l0 = replace(a.conteudo.liquidacao[0], receita_exportacao_R=9.0)
    a_alt = replace(a, conteudo=replace(a.conteudo, liquidacao=(l0,) + a.conteudo.liquidacao[1:]))
    rel = aud(g11, anexos=(a_alt,) + r.anexos_3c3[1:])
    assert not rel.aceito and "anexo_3c3_invalido" in erros(rel)


def test_g14_medicao_divergente_na_conciliacao_e_integridade():
    p = PerturbacaoCanal("conflitar", F.MED_IMP, "potencia", 1, atraso_s=0, valor=99.0)
    ex = X.executar("g14-medicao", L_real=[30.0, 34.0, 30.0, 30.0], perturbacoes=(p,), **{
        "K": 4, "N": 2, "m": 1, "com_fc": False, "modelo_kw": {"e0": 0.0}, "tipo": "tabela"})
    r = ex.resultado
    # observação original e conflitante do mesmo intervalo ⇒ chave conflitante ⇒ sem estado reconstruível
    assert r.situacao == "interrompida" and r.classe_falha in ("estado_nao_reconstruivel", "integridade")
    p2 = PerturbacaoCanal("valor_invalido", F.MED_IMP, "potencia", 1, valor=-1.0)
    ex2 = X.executar("g14-medicao-invalida", L_real=[30.0, 34.0, 30.0, 30.0], perturbacoes=(p2,), **{
        "K": 4, "N": 2, "m": 1, "com_fc": False, "modelo_kw": {"e0": 0.0}, "tipo": "tabela"})
    assert ex2.resultado.situacao == "interrompida" and ex2.resultado.registro_missao.conteudo.intervalos_aplicados == 1


# ------------------------------------------------------------------------------------------- comparação §13
def test_comparacao_open_loop_vs_mpc_mesmas_condicoes_sem_veredito():
    c = X.comparacao_open_loop_vs_mpc()
    ol, mpc = c["open_loop"], c["mpc"]
    for ex in (ol, mpc):
        assert ex.resultado.situacao == "encerrada" and aud(ex).aceito
    cmp = comparar_missoes_3c3(ol, mpc, rotulo_a="open-loop", rotulo_b="MPC")
    assert cmp.comparavel and cmp.tipo == "causal"
    for k in ("custo_realizado_total_R", "E_final_kWh[syn-bess]", "obrigacoes_pendentes_s", "E_importada_kWh",
              "E_exportada_kWh", "E_desvio_positivo_kWh"):
        assert k in cmp.linhas
    assert "Sem veredito" in cmp.observacao
    if cmp.linhas["E_final_kWh[syn-bess]"][2] != 0:
        assert not cmp.comparavel_para_superioridade


def test_comparador_recusa_tarifas_ou_pcc_diferentes():
    a = X.g5_erro_positivo_demanda()
    b = X.g5_erro_positivo_demanda(modelo_kw={"e0": 0.0, "imp": 30.0})
    cmp = comparar_missoes_3c3(a, b, rotulo_a="a", rotulo_b="b")
    assert not cmp.comparavel and "rede_nao_comparavel" in {x.codigo for x in cmp.constatacoes}


def test_construcao_recusa_configuracoes_invalidas():
    ctrl, ent, mod, ver, pol, crd = X.montar("cfg-invalida", K=4, N=2, m=1, com_fc=False, modelo_kw={"e0": 0.0},
                                             tipo="tabela")
    liq = F.tarifa("importacao", [0.6] * 4, "x", natureza="aplicavel_liquidacao")
    with pytest.raises(ContratoInvalido) as exc:
        ControladorMPCConectado(ctrl.cfg, mod, ctrl.provedor, ctrl.resolvedor, ctrl.fontes,
                                replace(crd, tarifas_decisao=crd.tarifas_decisao + (liq,)))
    assert "preco_de_liquidacao_na_decisao" in exc.value.codigos
    sem_med = replace(mod, pcc=replace(mod.pcc, medidor_importacao_uid=None, medidor_exportacao_uid=None))
    with pytest.raises(ContratoInvalido) as exc:
        ControladorMPCConectado(ctrl.cfg, sem_med, ctrl.provedor, ctrl.resolvedor, ctrl.fontes, crd)
    assert "medidores_nao_declarados" in exc.value.codigos
    outro = replace(mod, pcc=replace(mod.pcc, microrrede_uid="syn-outra"))
    with pytest.raises(ContratoInvalido) as exc:
        ControladorMPCConectado(ctrl.cfg, outro, ctrl.provedor, ctrl.resolvedor, ctrl.fontes, crd)
    assert "pcc_de_outra_microrrede" in exc.value.codigos


def test_tarifa_de_decisao_ausente_na_janela_bloqueia_sem_comando():
    tar = (F.tarifa("importacao", [0.6] * 4, "MPC3C3", emitido="2026-01-01T00:30:00+00:00"),
           F.tarifa("exportacao", [0.2] * 4, "MPC3C3", emitido=F.EMISSAO_R0))
    ex = X.executar("tarifa-futura", K=4, N=2, m=1, com_fc=False, modelo_kw={"e0": 0.0}, tipo="tabela", tarifas=tar)
    r = ex.resultado
    assert r.situacao == "interrompida" and r.classe_falha == "bloqueado_validacao" and not r.comandos
    assert "tarifa_indisponivel_na_decisao" in {c.codigo for c in r.registros[0].conteudo.constatacoes}
