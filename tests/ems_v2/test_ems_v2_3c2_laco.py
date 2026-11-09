"""Piso 3C-2 — laço MPC completo SEM solver (dublê de regra analítica + auditor independente 3C-1).

Prova a máquina do horizonte recedente (relógio, K6, conciliação C-02, registros encadeados, retomada, reprodução)
independentemente de Pyomo/HiGHS. Microrrede SEM gerador: FV + banco + demanda. Sintético/algébrico.

Cenário NS (Δ = 15 min, h = 0,25 h): demanda 10 kW; FV prevista (perfil base) [5, 5, 15, 15, 5, 5]; FV realizada
[5, 6, 16, 16, 7, 6]; banco e0 = 20 kWh, P̄ = 20 kW, c_thr = 0,05; c_curt = 0,2. Provedor com correção aditiva pela
última observação. Valores ANALÍTICOS (N = 3, m = 2):
  janela k=0: previsão [5, 5, 15] → P_d = 5, 5 → realizado R$ 0,125 (throughput) + 0,05 (vertimento de 1 kW em g=1);
  janela k=2: δ = +1 → previsão [16, 16, 6] → P_c = 6, 6 → R$ 0,15;
  janela k=4: δ = +1 → previsão [6, 6] → P_d = 4, 4 → R$ 0,10 + 0,05 (vertimento de 1 kW em g=4).
  Total realizado R$ 0,475; energia final 20 − 2,5 + 3 − 2 = 18,5 kWh.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from ems_v2 import fixtures_3c2 as F
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.mpc import experimentos as X
from ems_v2.mpc import orquestrador as O
from ems_v2.mpc.auditoria import auditar_missao
from ems_v2.mpc.entorno import PerturbacaoCanal
from ems_v2.mpc.persistencia import comandos_aplicados, ler_missao, nome_retomada, retomar_controlador
from ems_v2.mpc.registro import verificar_registro_missao
from ems_v2.ponte.canonico import json_canonico
from ems_v2.ponte.compromisso import ExecutorAlgebricoCommitment3C1, estado_inicial_3c1, plano_de_resultado_3c1
from ems_v2.ponte.execucao import executar

from mpc_util import ResolvedorRegraAnalitica  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
NS = dict(K=6, N=3, m=2, L=[10.0] * 6, pv_prev=[5, 5, 15, 15, 5, 5], pv_real=[5, 6, 16, 16, 7, 6], tipo="correcao",
          modelo_kw={"com_fc": False})


def ns(nome="ns", **kw):
    a = {**NS, **kw}
    a.setdefault("resolvedor", ResolvedorRegraAnalitica())
    return X.executar(nome, **a)


def aud(ex):
    r = ex.resultado
    return auditar_missao(r.registro_missao, r.registros, r.livro, ex.modelo, verdade=ex.verdade)


def test_missao_de_varias_janelas_valores_analiticos_e_auditoria_independente():
    ex = ns()
    r = ex.resultado
    assert r.situacao == "encerrada" and r.registro_missao.conteudo.desfecho == "concluida"
    c = [x.conteudo for x in r.registros]
    assert [(x.janela.k, x.janela.N_k, x.janela.m_k, x.intervalos_aplicados) for x in c] == [(0, 3, 2, 2), (2, 3, 2, 2),
                                                                                           (4, 2, 2, 2)]
    assert [x.previsao.serie(F.FV, "potencia").serie.valores for x in c] == [(5.0, 5.0, 15.0), (16.0, 16.0, 6.0),
                                                                             (6.0, 6.0)]
    assert [round(x.custos.realizado.total_R, 9) for x in c] == [0.175, 0.15, 0.15]
    assert [round(x.custos.planejado_prefixo.total_R, 9) for x in c] == [0.125, 0.15, 0.1]
    assert r.registro_missao.conteudo.custo_realizado_acumulado.total_R == pytest.approx(0.475, abs=1e-12)
    assert r.registro_missao.conteudo.estado_final.bateria(F.BESS).energia_kWh == pytest.approx(18.5, abs=1e-12)
    rel = aud(ex)
    assert rel.aceito, [x.codigo for x in rel.constatacoes if x.severidade == "erro"]
    assert rel.detalhes["custos"]["acumulado_recomputado"] == pytest.approx(0.475, abs=1e-12)


def test_custo_acumulado_sem_dupla_contagem_de_janelas_sobrepostas():
    r = ns().resultado
    plan_janelas = sum(x.conteudo.custos.planejado_janela_R["total"] for x in r.registros)
    acc = r.registro_missao.conteudo.custo_realizado_acumulado
    assert acc.intervalos == 6 and sum(x.conteudo.intervalos_aplicados for x in r.registros) == 6
    assert plan_janelas > acc.total_R + 0.05      # somar objetivos de janelas sobrepostas contaria o sufixo não executado
    assert r.registro_missao.conteudo.valor_futuro.contabilizado_como_custo is False
    assert r.registro_missao.conteudo.valor_futuro.valor_R is None


def test_missao_de_uma_janela_igual_ao_fluxo_direto_3c1_3c0():
    ex = ns("ns-1", N=6, m=6)
    r = ex.resultado
    assert len(r.registros) == 1 and r.registros[0].conteudo.intervalos_aplicados == 6
    mod = ex.modelo
    res = ResolvedorRegraAnalitica().resolver(mod)
    p, _ = plano_de_resultado_3c1(res, mod)
    traj = executar(p, estado_inicial_3c1(mod), ExecutorAlgebricoCommitment3C1(mod, F.fontes(False)), ex.verdade,
                    execucao_uid="direto")
    assert traj.estados[-1] == r.registro_missao.conteudo.estado_final
    assert [dict(x.aplicado) for x in traj.passos] == [x.aplicado for x in r.registros[0].conteudo.passos]


def test_ultimo_bloco_menor_que_m_e_contador_global():
    ex = ns("ns-5", K=5, L=[10.0] * 5, pv_prev=[5, 5, 15, 15, 5], pv_real=[5, 6, 16, 16, 7])
    c = [x.conteudo for x in ex.resultado.registros]
    assert [(x.janela.k, x.janela.m_k, x.intervalos_aplicados, x.janela.final) for x in c] == [
        (0, 2, 2, False), (2, 2, 2, False), (4, 1, 1, True)]
    assert ex.resultado.registro_missao.conteudo.intervalos_aplicados == 5 and aud(ex).aceito


def test_consigna_inexequivel_interrompe_sem_recorte_nem_contingencia():
    """FV realizada (15) abaixo da prevista corrigida (16) em g = 3: a planta recusa; nada é recortado."""
    ex = ns("ns-inex", pv_real=[5, 6, 16, 15, 7, 6])
    r = ex.resultado
    assert r.situacao == "interrompida" and r.classe_falha == "consigna_inexequivel"
    ult = r.registros[-1].conteudo
    assert ult.desfecho == "executada_parcial" and ult.intervalos_aplicados == 1 and ult.intervalos_comprometidos == 2
    assert ex.entorno.parado and len(ex.entorno.comandos_aplicados()) == 3
    assert r.registro_missao.conteudo.estado_final == ult.estados[-1]
    assert aud(ex).aceito


def test_observacao_faltante_parada_segura_modo1():
    ex = ns("ns-falta", perturbacoes=(PerturbacaoCanal("omitir", F.FV, "potencia", 1),))
    r = ex.resultado
    assert r.situacao == "interrompida" and r.classe_falha == "estado_nao_reconstruivel"
    c = r.registros[-1].conteudo
    assert c.intervalos_aplicados == 1 and c.intervalos_comprometidos == 2      # g = 1 aplicado pela planta, não conciliado
    assert ex.entorno.proximo_indice == 2                                       # nenhum comando além do bloco
    assert not [e for e in r.livro.entradas if (e.observacao.recurso_uid, e.observacao.grandeza) == (F.FV, "potencia")
                and e.observacao.inicio_utc == O.instante_fronteira(r.configuracao.malha, 1)]   # ausente ≠ zero
    assert aud(ex).aceito


def test_observacao_de_outra_microrrede_e_rejeitada_e_nao_supre_a_falta():
    ex = ns("ns-outra", perturbacoes=(PerturbacaoCanal("outra_microrrede", F.DEM, "potencia", 0),))
    r = ex.resultado
    assert "rejeitada_outra_microrrede" in {e.classificacao for e in r.livro.entradas}
    assert r.classe_falha == "estado_nao_reconstruivel" and r.registros[-1].conteudo.intervalos_aplicados == 0


def test_valor_invalido_e_duplicata_no_canal():
    ex = ns("ns-inv", perturbacoes=(PerturbacaoCanal("duplicar", F.DEM, "potencia", 0),
                                    PerturbacaoCanal("valor_invalido", F.FV, "potencia", 3, valor=-5.0)))
    cls = [e.classificacao for e in ex.resultado.livro.entradas]
    assert "duplicata_identica" in cls and "rejeitada_invalida" in cls
    assert ex.resultado.classe_falha == "estado_nao_reconstruivel"


def test_modo2_comando_emitido_confirmacao_observacao_pausa_C02_e_retomada():
    """Modo 2: a observação de FV do intervalo 0 chega 5 min atrasada. Conciliação em τ_1 PAUSA (barreira C-02: nada
    aplicado retrospectivamente sem observação); em τ_1 + 5 min retoma do checkpoint; a decisão em τ_2 ocorre no prazo."""
    ctrl, ent, mod, ver = X.montar("ns-m2", **{**NS, "resolvedor": ResolvedorRegraAnalitica(),
                                               "cfg_kw": {"modo": "preparacao_online"},
                                               "perturbacoes": (PerturbacaoCanal("atrasar", F.FV, "potencia", 0,
                                                                                 atraso_s=300),)})
    dec = ctrl.decidir()
    assert len(dec.comandos) == 2 and ctrl.janela_aberta is not None        # plano calculado + comandos emitidos
    ent.aplicar(dec.comandos[0])
    t1 = O.instante_fronteira(ctrl.cfg.malha, 1)
    ctrl.receber(ent.entregar_ate(t1))
    assert ctrl.conciliar(t1) == "aguardando_observacoes"                     # confirmada, mas sem observação
    assert ctrl._aberta.cursor == 0 and ctrl.estado.indice_fronteira == 0     # estado NÃO avançou
    falt = ctrl.faltantes_atuais(t1)
    assert {(f.recurso_uid, f.grandeza, f.indice) for f in falt} >= {(F.FV, "potencia", 0)}
    ent.aplicar(dec.comandos[1])
    t1b = "2026-01-01T00:20:00+00:00"
    ctrl.receber(ent.entregar_ate(t1b))
    assert ctrl.conciliar(t1b) == "aguardando_confirmacoes"                   # g=0 conciliado; g=1 ainda em curso
    assert ctrl._aberta.cursor == 1
    t2 = O.instante_fronteira(ctrl.cfg.malha, 2)
    ctrl.receber(ent.entregar_ate(t2))
    assert ctrl.conciliar(t2) == "concluida" and ctrl.k == 2
    reg = ctrl.registros[-1].conteudo
    assert len(reg.conciliacoes) == 3 and "conciliacao_pausada_C02" in {c.codigo for c in reg.constatacoes}
    assert ctrl.decidir() is not None                                          # próxima decisão no prazo


def test_modo2_observacao_alem_do_prazo_suspende_sem_inventar_estado():
    ctrl, ent, mod, ver = X.montar("ns-m2b", **{**NS, "resolvedor": ResolvedorRegraAnalitica(),
                                                "cfg_kw": {"modo": "preparacao_online", "falhas": F.politica_falhas(
                                                    suspender=("estado_nao_reconstruivel",))},
                                                "perturbacoes": (PerturbacaoCanal("atrasar", F.FV, "potencia", 1,
                                                                                  atraso_s=600),)})
    dec = ctrl.decidir()
    for c in dec.comandos:
        ent.aplicar(c)
    t2 = O.instante_fronteira(ctrl.cfg.malha, 2)
    ctrl.receber(ent.entregar_ate(t2))
    assert ctrl.conciliar(t2) == "aguardando_observacoes"
    with pytest.raises(ContratoInvalido):
        ctrl.decidir()                                                        # sem estado conciliado em τ_2
    assert ctrl.falhar_janela_aberta("estado_nao_reconstruivel", "prazo da decisão em τ_2") == "estado_nao_reconstruivel"
    assert ctrl.situacao == "suspensa" and ctrl.estado.indice_fronteira == 1  # último estado CONCILIADO
    assert len(ctrl._comandos) == 2                                          # nenhum comando novo


def test_mudanca_de_identidade_de_microrrede_ou_cenario():
    mod = F.modelo("3C2", 6, [10.0] * 6, [5] * 6, com_fc=False)
    cfg = F.configuracao("ns-id", 6, 3, 2, cenario="syn-outro-cenario")
    with pytest.raises(ContratoInvalido) as e:
        O.ControladorMPC(cfg, mod, X.provedor("tabela", [10.0] * 6, [5] * 6, com_fc=False), ResolvedorRegraAnalitica(),
                         {})
    assert "identidade_divergente" in e.value.codigos
    ctrl, ent, _, _ = X.montar("ns-id2", **{**NS, "resolvedor": ResolvedorRegraAnalitica()})
    r = O.executar_missao_simulada(ctrl, ent, max_janelas=1, finalizar=False)
    ctrl.modelo = dataclasses.replace(ctrl.modelo, base=dataclasses.replace(ctrl.modelo.base, cenario_uid="syn-x"))
    O.executar_missao_simulada(ctrl, ent)
    assert ctrl.classe_falha == "identidade_divergente" and ctrl.situacao == "interrompida"
    assert ent.proximo_indice == 2 and r is not None


def test_integridade_da_cadeia_detecta_adulteracao_remocao_e_reordenacao():
    r = ns("ns-cad").resultado
    rm, regs = r.registro_missao, list(r.registros)
    assert verificar_registro_missao(rm, regs) == []
    c1 = regs[1].conteudo
    adul = dataclasses.replace(regs[1], conteudo=dataclasses.replace(c1, custos=dataclasses.replace(
        c1.custos, diferenca_realizado_menos_planejado_R=123.0)))
    assert {"conteudo_janela_adulterado", "registro_janela_adulterado"} & {
        x.codigo for x in verificar_registro_missao(rm, [regs[0], adul, regs[2]])}
    assert verificar_registro_missao(rm, [regs[0], regs[2]])                  # remoção
    c2 = regs[2].conteudo
    assert c2.selo_checkpoint_origem == regs[1].conteudo.selo_checkpoint_final is not None
    troca = dataclasses.replace(regs[2], conteudo=dataclasses.replace(c2, selo_checkpoint_origem=regs[0].conteudo
                                                                      .selo_checkpoint_final))
    assert "vinculo_checkpoint_quebrado" in {x.codigo for x in verificar_registro_missao(rm, [regs[0], regs[1], troca])}
    assert verificar_registro_missao(rm, [regs[1], regs[0], regs[2]])         # reordenação
    rm2 = dataclasses.replace(rm, conteudo=dataclasses.replace(rm.conteudo, custo_realizado_acumulado=dataclasses.replace(
        rm.conteudo.custo_realizado_acumulado, total_R=0.0)))
    assert verificar_registro_missao(rm2, regs)


def test_reproducao_determinista_da_mesma_missao():
    a, b = ns("ns-rep").resultado, ns("ns-rep").resultado
    assert a.registro_missao.impressao_deterministica == b.registro_missao.impressao_deterministica
    assert [x.hash_conteudo for x in a.registros] == [x.hash_conteudo for x in b.registros]
    assert a.livro.hash_cadeia() == b.livro.hash_cadeia()


def test_persistencia_retomada_de_checkpoint_identica_a_execucao_continua(tmp_path: Path):
    cont = ns("ns-ret").resultado
    d = tmp_path / "missao"
    ctrl, ent, mod, ver = X.montar("ns-ret", **{**NS, "resolvedor": ResolvedorRegraAnalitica(), "diretorio": d})
    O.executar_missao_simulada(ctrl, ent, max_janelas=1, finalizar=False)        # "processo" interrompido
    del ctrl, ent
    novo, ent2, _, _ = X.montar("ns-ret", **{**NS, "resolvedor": ResolvedorRegraAnalitica()})
    ctrl2, pt = retomar_controlador(d, novo.cfg, novo.modelo, novo.provedor, novo.resolvedor, F.fontes(False),
                                    identificadores_verdade=(X.PLANTA,), fontes_verdade=(F.FONTE_VERDADE,))
    assert pt.k == 2 and ctrl2.k == 2
    ent2.reconstituir(comandos_aplicados(pt), O.instante_fronteira(novo.cfg.malha, pt.k))
    fim = O.executar_missao_simulada(ctrl2, ent2)
    assert fim.registro_missao.impressao_deterministica == cont.registro_missao.impressao_deterministica
    rm, regs, livro = ler_missao(d, novo.cfg.identidade.missao_uid)
    assert rm == fim.registro_missao and verificar_registro_missao(rm, regs) == []
    assert livro.hash_cadeia() == cont.livro.hash_cadeia()


def test_retomada_recusa_ponto_adulterado_ou_de_outra_configuracao(tmp_path: Path):
    d = tmp_path / "m"
    ctrl, ent, mod, ver = X.montar("ns-ret2", **{**NS, "resolvedor": ResolvedorRegraAnalitica(), "diretorio": d})
    O.executar_missao_simulada(ctrl, ent, max_janelas=1, finalizar=False)
    outro = F.configuracao("ns-ret2", 6, 3, 1)                                   # mesma missão, m diferente
    with pytest.raises(ContratoInvalido) as e:
        retomar_controlador(d, outro, ctrl.modelo, ctrl.provedor, ctrl.resolvedor, F.fontes(False))
    assert "identidade_divergente" in e.value.codigos
    p = d / nome_retomada(ctrl.cfg.identidade.missao_uid, 0)
    dado = json.loads(p.read_text(encoding="utf-8"))
    dado["k"] = 1
    p.chmod(0o644)
    p.write_text(json.dumps(dado), encoding="utf-8")
    with pytest.raises(ContratoInvalido) as e:
        retomar_controlador(d, ctrl.cfg, ctrl.modelo, ctrl.provedor, ctrl.resolvedor, F.fontes(False))
    assert {"ponto_retomada_adulterado", "retomada_incoerente"} & e.value.codigos


def test_registros_sao_gravados_de_forma_exclusiva(tmp_path: Path):
    from ems_v2.mpc.persistencia import gravar_exclusivo
    from ems_v2.ponte.registro import RegistroImutavelError
    gravar_exclusivo(tmp_path, "x.json", "a")
    assert gravar_exclusivo(tmp_path, "x.json", "a").read_text() == "a"         # idempotente
    with pytest.raises(RegistroImutavelError):
        gravar_exclusivo(tmp_path, "x.json", "b")
    _ = json_canonico
