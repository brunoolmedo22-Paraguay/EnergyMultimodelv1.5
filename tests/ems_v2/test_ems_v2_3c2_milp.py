"""Piso 3C-2 — MPC recedente de ponta a ponta com Pyomo + HiGHS (``resolver_3c1`` pelo adaptador explícito).

Experimentos E1–E8 e itens obrigatórios da missão sobre a microrrede SINTÉTICA ``ems_v2.fixtures_3c2`` (FV + banco +
PEMFC com transição instantânea DECLARADA como abstração). Simulação causal de laço fechado ALGÉBRICA: não é validação
física da planta. Sem Pyomo/HiGHS: pulados explicitamente.

Valores analíticos de E2 (MPC N = 4, m = 2; Δ = 15 min, h = 0,25 h; c_thr = 0,05; c_curt = 0,2; c_H = 10 R$/kg;
q(p) = 0,2 + 0,05 p kg/h; C_SU = 2, C_SD = 1; m_SU = 0,05 kg, m_SD = 0,02 kg), conferidos à mão contra o
despacho aplicado:
  janela k=0: banco 20 kW em g=0,1 (R$ 0,5) + parada da PEMFC em g=0 (C_SD 1 + 0,02·10) ⇒ R$ 1,7;
  janela k=2: banco 20 kW em g=2,3 (R$ 0,5) + vertimento 15 kW × 2 × 0,25 × 0,2 = R$ 1,5 ⇒ R$ 2,0;
  janela k=4: partida em g=4 (2 + 0,05·10) + combustível 2 × 0,25 × 10 × 0,7 = 3,5 + carga 5 kW × 2 (R$ 0,125)
             ⇒ R$ 6,125;
  janela k=6: ON em g=6 (1,75 + 0,0625) + parada em g=7 (1,2) + descarga 5 kW (0,0625) ⇒ R$ 3,075.
  Total R$ 12,9. Open-loop (N = m = 8): plano com FV 10 kW; vertimento realizado de 15 kW em 6 intervalos ⇒ R$ 18,7.
"""
from __future__ import annotations

import dataclasses

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

from ems_v2 import fixtures_3c2 as F  # noqa: E402
from ems_v2.compromisso.contrato import MemoriaCommitmentUnidade  # noqa: E402
from ems_v2.diagnostics import ContratoInvalido  # noqa: E402
from ems_v2.milp.config import CONFIG_ANALITICA as C  # noqa: E402
from ems_v2.milp.solver import _executar_highs  # noqa: E402
from ems_v2.mpc import experimentos as X  # noqa: E402
from ems_v2.mpc import orquestrador as O  # noqa: E402
from ems_v2.mpc.adaptador_milp import ResolvedorMILP3C1  # noqa: E402
from ems_v2.mpc.auditoria import auditar_missao, verificar_nao_antecipatividade  # noqa: E402
from ems_v2.mpc.comparadores import comparar_missoes, condicoes_comparaveis  # noqa: E402
from ems_v2.mpc.entorno import PerturbacaoCanal  # noqa: E402
from ems_v2.mpc.metricas import metricas_missao  # noqa: E402
from ems_v2.mpc.provedores import ProvedorCorrecaoPorObservacao  # noqa: E402
from ems_v2.ponte.cenario import Realizacao, SerieRecurso  # noqa: E402
from ems_v2.ponte.registro_3c1 import verificar_anexo_3c1  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic


def aud(ex):
    r = ex.resultado
    return auditar_missao(r.registro_missao, r.registros, r.livro, ex.modelo, verdade=ex.verdade)


def erros(rel):
    return [c.codigo for c in rel.constatacoes if c.severidade == "erro"]


@pytest.fixture(scope="module")
def e2():
    return X.e2_previsao_reemitida()["mpc"]


@pytest.fixture(scope="module")
def e3():
    return X.e3_open_loop_vs_mpc()


# ------------------------------------------------------------------------------------------- 1, 2, 5, 16, 17
def test_e2_varias_janelas_previsao_reemitida_valores_analiticos(e2):
    r = e2.resultado
    assert r.situacao == "encerrada" and r.registro_missao.conteudo.desfecho == "concluida_com_obrigacoes_pendentes"
    c = [x.conteudo for x in r.registros]
    assert [(x.janela.k, x.janela.N_k, x.janela.m_k, x.janela.reduzida) for x in c] == [
        (0, 4, 2, False), (2, 4, 2, False), (4, 4, 2, False), (6, 2, 2, True)]
    fv = [x.previsao.serie(F.FV, "potencia").serie.valores for x in c]
    assert fv == [(10.0,) * 4, (10.0,) * 4, (25.0,) * 4, (25.0,) * 2]           # reemitida após observar o degrau
    assert len({x.hash_previsao for x in c}) == 4 and all(x.aceitacao == "aceito_otimo" for x in c)
    assert [round(x.custos.realizado.total_R, 9) for x in c] == [1.7, 2.0, 6.125, 3.075]
    assert r.registro_missao.conteudo.custo_realizado_acumulado.total_R == pytest.approx(12.9, abs=1e-9)
    assert [round(p.aplicado[f"{F.FC}|u"]) for x in c for p in x.passos] == [0, 0, 0, 0, 1, 1, 1, 0]
    assert r.registro_missao.conteudo.obrigacoes_pendentes_fim_s == {F.FC: 900}     # T_off além de T_M: REPORTADA
    rel = aud(e2)
    assert rel.aceito, erros(rel)


def test_e2_registros_3c0_e_anexos_3c1_verificaveis_e_ligados_a_cadeia(e2):
    r = e2.resultado
    assert len(r.registros_3c0) == len(r.anexos_3c1) == 4
    for reg, anexo, jan in zip(r.registros_3c0, r.anexos_3c1, r.registros):
        assert verificar_anexo_3c1(anexo, reg) == []
        assert jan.selo_registro_3c0 == reg.selo and jan.selo_anexo_3c1 == anexo.selo
        assert reg.plano.indice_fronteira_inicial == jan.conteudo.janela.k
        assert reg.custo_realizado.total_R == pytest.approx(jan.conteudo.custos.realizado.total_R, abs=1e-12)
        assert reg.valor_futuro.contabilizado_como_custo is False


def test_custo_sem_dupla_contagem_e_planejado_de_janelas_nunca_somado(e2):
    r = e2.resultado
    acc = r.registro_missao.conteudo.custo_realizado_acumulado
    assert acc.intervalos == 8 and acc.total_R == pytest.approx(sum(x.conteudo.custos.realizado.total_R
                                                                    for x in r.registros), abs=1e-12)
    soma_obj = sum(x.conteudo.custos.planejado_janela_R["total"] for x in r.registros)
    assert soma_obj != pytest.approx(acc.total_R)
    assert aud(e2).detalhes["custos"]["acumulado_recomputado"] == pytest.approx(12.9, abs=1e-9)


def test_missao_de_uma_janela_igual_ao_fluxo_3c1_direto(e3):
    from ems_v2.milp.solver_3c1 import resolver_3c1
    from ems_v2.ponte.compromisso import (ExecutorAlgebricoCommitment3C1, contabilidade_realizada_3c1,
                                          estado_inicial_3c1, plano_de_resultado_3c1)
    from ems_v2.ponte.execucao import executar
    ol = e3["open_loop"]
    assert len(ol.resultado.registros) == 1
    mod = ol.modelo
    res = resolver_3c1(mod, C)
    p, _ = plano_de_resultado_3c1(res, mod)
    traj = executar(p, estado_inicial_3c1(mod), ExecutorAlgebricoCommitment3C1(mod, F.fontes()), ol.verdade,
                    execucao_uid="direto")
    cont = contabilidade_realizada_3c1(mod, p, traj, ol.verdade)
    assert traj.estados[-1] == ol.resultado.registro_missao.conteudo.estado_final
    assert cont.custo.total_R == pytest.approx(ol.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R,
                                               abs=1e-9) == pytest.approx(18.7, abs=1e-9)


# ------------------------------------------------------------------------------------------- 3, 4 (terminal)
def test_ultimo_bloco_menor_que_m():
    ex = X.executar("t3-k7", K=7, L=F.L_E2[:7], pv_prev=F.PV_PRIOR_E2[:7], pv_real=F.PV_REAL_E2[:7])
    c = [x.conteudo for x in ex.resultado.registros]
    assert [(x.janela.k, x.janela.N_k, x.janela.m_k) for x in c] == [(0, 4, 2), (2, 4, 2), (4, 3, 2), (6, 1, 1)]
    assert sum(x.intervalos_aplicados for x in c) == 7 and aud(ex).aceito


def test_horizonte_estendido_declarado_planeja_mas_nunca_aplica_pos_missao():
    L, pv = F.L_E2 + [30.0, 30.0], F.PV_PRIOR_E2 + [10.0, 10.0]                # tabelas cobrem 2 intervalos pós-missão
    prov = ProvedorCorrecaoPorObservacao("prov-est", F.tabela(X.CASO, L, pv), F.proc("p", fonte=F.FONTE_PREV),
                                         corrigidas=[(F.FV, "potencia")], bases=F.BASES)
    ex = X.executar("t4-est", provedor_obj=prov, cfg_kw={"terminal": "horizonte_estendido_declarado",
                                                         "cobertura": 30.0})
    c = [x.conteudo for x in ex.resultado.registros]
    assert [(x.janela.N_k, x.janela.intervalos_pos_missao, x.intervalos_aplicados) for x in c] == [
        (4, 0, 2), (4, 0, 2), (4, 0, 2), (4, 2, 2)]
    assert max(p.indice_global for x in c for p in x.passos) == 7 and aud(ex).aceito
    assert ex.resultado.registro_missao.conteudo.custo_realizado_acumulado.intervalos == 8
    # sem cobertura pós-missão na previsão: falha classificada, nenhuma extrapolação
    sem = X.executar("t4-est-sem", cfg_kw={"terminal": "horizonte_estendido_declarado", "cobertura": 30.0})
    assert sem.resultado.classe_falha == "previsao_invalida" and sem.resultado.registros[-1].conteudo.janela.k == 6
    assert sem.entorno.proximo_indice == 6


def test_politica_cumprir_na_janela_final_e_obrigacoes_nunca_desaparecem():
    ex = X.executar("t4-cumprir", cfg_kw={"perm_final": "cumprir_na_janela"})
    rm = ex.resultado.registro_missao.conteudo
    assert [x.conteudo.janela.politica_permanencia for x in ex.resultado.registros] == [
        "obrigacao_residual_vinculante", "obrigacao_residual_vinculante", "cumprir_na_janela", "cumprir_na_janela"]
    assert rm.desfecho in ("concluida", "concluida_com_obrigacoes_pendentes")
    assert (rm.desfecho == "concluida") == (rm.obrigacoes_pendentes_fim_s == {})


# ------------------------------------------------------------------------------------------- 6, 7, 20 (causalidade)
class ProvedorTardio(ProvedorCorrecaoPorObservacao):
    def emitir(self, pedido):
        p = super().emitir(pedido)
        from datetime import datetime, timedelta
        return dataclasses.replace(p, emissao_utc=(datetime.fromisoformat(pedido.inicio_utc)
                                                   + timedelta(seconds=1)).isoformat())


def test_previsao_emitida_tarde_bloqueia_sem_comando():
    prov = ProvedorTardio("prov-tardio", F.tabela(X.CASO, F.L_E2, F.PV_PRIOR_E2), F.proc("p", fonte=F.FONTE_PREV),
                          corrigidas=[(F.FV, "potencia")], bases=F.BASES)
    ex = X.executar("t6", provedor_obj=prov)
    assert ex.resultado.classe_falha == "previsao_invalida" and ex.entorno.proximo_indice == 0
    assert "previsao_nao_causal" in {c.codigo for c in ex.resultado.registros[0].conteudo.constatacoes}


class ProvedorVazamento(ProvedorCorrecaoPorObservacao):
    """MALICIOSO: guarda referência à verdade e copia o FV FUTURO, declarando o vínculo informacional corretamente."""

    def __init__(self, verdade, *a, **kw):
        super().__init__(*a, **kw)
        self._verdade = verdade

    def emitir(self, pedido):
        from ems_v2.mpc.provedores import _recorte
        p = super().emitir(pedido)
        s = p.serie(F.FV, "potencia")
        vals = _recorte(self._verdade.serie(F.FV, "potencia").serie, pedido.inicio_utc, pedido.N_k, pedido.delta_s)
        novo = dataclasses.replace(s, serie=dataclasses.replace(s.serie, valores=vals))
        return dataclasses.replace(p, series=tuple(novo if x is s else x for x in p.series))


def _verdade_b():
    pv = F.PV_REAL_E2[:2] + [20.0] * 6                       # igual até k* = 2; diferente depois
    return F.verdade(X.CASO, F.L_E2, pv)


def test_fuga_deliberada_de_informacao_futura_detectada_por_intervencao():
    va, vb = F.verdade(X.CASO, F.L_E2, F.PV_REAL_E2), _verdade_b()

    def honesto(v):
        return X.executar("t7-honesto", verdade_obj=v).resultado

    def malicioso(v):
        prov = ProvedorVazamento(v, "prov-mal", F.tabela(X.CASO, F.L_E2, F.PV_PRIOR_E2), F.proc("p", fonte=F.FONTE_PREV),
                                 corrigidas=[(F.FV, "potencia")], bases=F.BASES)
        return X.executar("t7-mal", verdade_obj=v, provedor_obj=prov).resultado
    rh = verificar_nao_antecipatividade(honesto, va, vb, 2)
    assert rh.nao_antecipativo and rh.janelas_comparadas == 2
    rm = verificar_nao_antecipatividade(malicioso, va, vb, 2)
    assert not rm.nao_antecipativo
    assert (1, 2, "hash_previsao") in rm.divergencias                       # decisão em τ_2 usou o futuro
    # a fuga passou pelas verificações estruturais em tempo de execução (limite de confiança documentado)
    assert malicioso(va).registros[1].conteudo.aceitacao == "aceito_otimo"


def test_fuga_com_evidencia_de_hash_bloqueada_pela_auditoria_de_separacao():
    va = F.verdade(X.CASO, F.L_E2, F.PV_REAL_E2)

    class ProvedorHash(ProvedorCorrecaoPorObservacao):
        def emitir(self, pedido):
            from ems_v2.ponte.canonico import sha256
            p = super().emitir(pedido)
            s = p.serie(F.FV, "potencia")
            pr = dataclasses.replace(s.serie.procedencia, sha256=sha256(va.serie(F.FV, "potencia").serie))
            n = dataclasses.replace(s, serie=dataclasses.replace(s.serie, procedencia=pr))
            return dataclasses.replace(p, series=tuple(n if x is s else x for x in p.series))
    prov = ProvedorHash("prov-hash", F.tabela(X.CASO, F.L_E2, F.PV_PRIOR_E2), F.proc("p", fonte=F.FONTE_PREV),
                        corrigidas=[(F.FV, "potencia")], bases=F.BASES)
    ex = X.executar("t7-hash", verdade_obj=va, provedor_obj=prov)
    rel = aud(ex)
    assert not rel.aceito and "previsao_derivada_da_realizacao" in erros(rel)


def test_adversarial_registro_e_livro_adulterados_e_comando_fora_de_ordem(e2):
    r = e2.resultado
    regs = list(r.registros)
    c = regs[1].conteudo
    falso = dataclasses.replace(regs[1], conteudo=dataclasses.replace(c, hash_instantaneo="0" * 64))
    rel = auditar_missao(r.registro_missao, [regs[0], falso] + regs[2:], r.livro, e2.modelo)
    assert {"instantaneo_nao_reproduzido", "conteudo_janela_adulterado"} <= set(erros(rel))
    doc = r.livro.exportar()
    ent = list(doc.entradas)
    i = next(j for j, e in enumerate(ent) if e.observacao.recurso_uid == F.FV and e.observacao.grandeza == "potencia")
    ent[i] = dataclasses.replace(ent[i], observacao=dataclasses.replace(ent[i].observacao, valor=99.0))
    rel = auditar_missao(r.registro_missao, regs, dataclasses.replace(doc, entradas=tuple(ent)), e2.modelo)
    assert not rel.aceito and "livro_cadeia_quebrada" in erros(rel)
    ctrl, ent2, _, _ = X.montar("t20")
    dec = ctrl.decidir()
    assert not ent2.aplicar(dec.comandos[1]).aceito_para_execucao               # fora de ordem: recusado
    assert ent2.proximo_indice == 0


# ------------------------------------------------------------------------------------------- 8, 9 (observações)
def test_e8_revisao_tardia_nao_altera_decisao_passada():
    """Mesma missão (mesma identidade) com e sem a revisão do FV de g = 1 recebida em τ_2 + 5 min."""
    base = X.executar("e8-revisao-registrar_sem_reconciliar", cfg_kw={"revisao": "registrar_sem_reconciliar"})
    reg = X.e8_revisao_tardia("registrar_sem_reconciliar")
    a, b = base.resultado.registros, reg.resultado.registros
    assert [x.conteudo.hash_instantaneo for x in a[:2]] == [x.conteudo.hash_instantaneo for x in b[:2]]
    assert [x.conteudo.hash_plano for x in a[:2]] == [x.conteudo.hash_plano for x in b[:2]]
    assert a[2].conteudo.hash_instantaneo != b[2].conteudo.hash_instantaneo       # a revisão entra só depois
    rv = [e for e in reg.resultado.livro.entradas if e.classificacao == "aceita_revisao"]
    assert len(rv) == 1 and rv[0].tardia_apos_corte is not None and rv[0].observacao.revisao == 1
    orig = next(e for e in reg.resultado.livro.entradas if e.observacao.evento_uid == rv[0].observacao.revisa_evento_uid)
    assert orig.observacao.valor == 10.0 and rv[0].observacao.valor == 12.0       # original preservado (append-only)
    # recebida durante a execução da janela τ_2 ⇒ registrada no registro DESSA janela; nada é reconciliado
    assert [x.evento_uid for x in b[1].conteudo.revisoes_tardias] == [rv[0].observacao.evento_uid]
    assert b[1].conteudo.estados == a[1].conteudo.estados
    assert reg.resultado.situacao == "encerrada" and aud(reg).aceito
    intr = X.e8_revisao_tardia("interromper")
    assert intr.resultado.classe_falha == "revisao_tardia" and intr.entorno.proximo_indice == 4


def test_disponibilidade_do_gerador_omitida_parada_segura():
    ex = X.executar("t9", perturbacoes=(PerturbacaoCanal("omitir", F.FC, "disponibilidade", 2),))
    r = ex.resultado
    assert r.classe_falha == "estado_nao_reconstruivel" and ex.entorno.proximo_indice == 4
    assert r.registros[-1].conteudo.intervalos_aplicados == 0 and aud(ex).aceito


# ------------------------------------------------------------------------------------------- 10, 11 (estado e memória)
def test_e6_soc_transportado_do_executado_nunca_do_terminal_planejado(e2):
    r = e2.resultado
    regs = r.registros
    plano0 = r.registros_3c0[0].plano
    e_plan_terminal = dict((t.uid, t.valores) for t in plano0.estados_planejados)[F.BESS][-1]
    e_exec_tau2 = regs[0].conteudo.estados[-1].bateria(F.BESS).energia_kWh
    assert e_plan_terminal == pytest.approx(0.0, abs=1e-6) and e_exec_tau2 == pytest.approx(10.0, abs=1e-9)
    assert regs[1].conteudo.estados[0].bateria(F.BESS).energia_kWh == e_exec_tau2
    m = metricas_missao(r, e2.modelo)
    assert 0.0 - 1e-9 <= m.operacao[f"SOC_min[{F.BESS}]"] and m.operacao[f"SOC_max[{F.BESS}]"] <= 1.0 + 1e-9
    assert m.trajetoria_soc[F.BESS][0] == 0.2 and len(m.trajetoria_soc[F.BESS]) == 9


def test_e5_memoria_de_commitment_atravessa_tres_janelas():
    ex = X.e5_memoria()
    r = ex.resultado
    c = [x.conteudo for x in r.registros]
    assert [x.janela.N_k for x in c] == [2] * 7 + [1] and r.situacao == "encerrada"
    u = [round(p.aplicado[f"{F.FC}|u"]) for x in c for p in x.passos]
    assert u == [0, 0, 0, 1, 1, 1, 0, 0]                                         # ON exatamente U = 3 intervalos
    # as janelas τ_4 e τ_5 herdam a obrigação pela memória EXECUTADA (900 s e 1800 s no estado)
    assert [x.estados[0].gerador(F.FC).tempo_no_estado_s for x in c[4:6]] == [900, 1800]
    # τ_3: parte em t = 0 com U = 3 > N = 2 ⇒ obrigação exportada; τ_4: cumpre a herdada DENTRO da janela;
    # τ_5: para em g = 6 ⇒ nova obrigação OFF (T_off) exportada para τ_6
    assert [x.resolucao.garantia_permanencia for x in c[3:6]] == ["residual_vinculante", "completa_na_janela",
                                                                  "residual_vinculante"]
    m = metricas_missao(r, ex.modelo)
    assert m.commitment[F.FC]["menor_corrida_on_completa"] == 3 and aud(ex).aceito


def test_e5_contraprova_memoria_descartada_e_recusada_pela_planta(monkeypatch):
    real = O.montar_entrada_janela

    def sem_memoria(modelo, cfg, jan, prev, estado, **kw):
        e3 = real(modelo, cfg, jan, prev, estado, **kw)
        if jan.k != 4:
            return e3
        return dataclasses.replace(e3, memorias=tuple(MemoriaCommitmentUnidade(m.uid, 7200, 0, m.procedencia)
                                                      for m in e3.memorias))
    monkeypatch.setattr(O, "montar_entrada_janela", sem_memoria)
    ex = X.e5_memoria()
    r = ex.resultado
    assert r.classe_falha == "consigna_inexequivel" and ex.entorno.parado
    ult = r.registros[-1].conteudo
    assert ult.janela.k == 4 and ult.intervalos_aplicados == 0
    assert "permanencia_minima_violada" in " ".join(c.mensagem for c in ult.constatacoes)


# ------------------------------------------------------------------------------------------- 12, 13, 14 (falhas)
def test_e7_falha_do_solver_nao_reaproveita_plano_anterior():
    ex = X.e7_falha_na_janela(1, X.resultado_sem_solucao)
    r = ex.resultado
    assert r.classe_falha == "falha_solver" and r.situacao == "interrompida"
    assert [x.conteudo.desfecho for x in r.registros] == ["executada", "sem_plano"]
    assert ex.entorno.proximo_indice == 2                                       # o sufixo do plano 0 NÃO foi usado
    assert r.registros[-1].conteudo.comandos == () and aud(ex).aceito


def test_e7_excecao_do_solver_na_primeira_janela():
    def explode(modelo, config):
        raise RuntimeError("falha simulada do HiGHS")
    ex = X.executar("t13", resolvedor=ResolvedorMILP3C1(C, _executor=explode))
    assert ex.resultado.classe_falha == "falha_solver" and ex.entorno.proximo_indice == 0


def _adulterado(modelo, config):
    out = _executar_highs(modelo, config)
    carregar = out["carregar"]

    def car():
        carregar()
        g = next(iter(modelo.p.keys()))
        modelo.p[g].set_value(modelo.p[g].value + 3.0)                      # quebra o balanço após o HiGHS
    out["carregar"] = car
    return out


def test_e7_rejeicao_do_auditor_nada_e_executado():
    ex = X.e7_falha_na_janela(1, lambda e3: ResolvedorMILP3C1(C, _executor=_adulterado).resolver(e3))
    r = ex.resultado
    assert r.classe_falha == "rejeitado_auditoria" and ex.entorno.proximo_indice == 2
    rs = r.registros[-1].conteudo.resolucao
    assert rs.estado_despacho == "rejeitado_auditoria" and not rs.aceito and rs.familias_reprovadas


def test_e7_incumbente_nao_otimo_so_com_politica_declarada():
    def limite(modelo, config):
        out = _executar_highs(modelo, config)
        out["terminacao"], out["status_solucao"] = "maxTimeLimit", "feasible"
        return out
    sem = X.executar("t7-sem", resolvedor=ResolvedorMILP3C1(C, _executor=limite))
    assert sem.resultado.classe_falha == "fora_politica_aceitacao" and sem.entorno.proximo_indice == 0
    com = X.executar("t7-com", resolvedor=ResolvedorMILP3C1(C, _executor=limite),
                     cfg_kw={"aceit": F.aceitacao(True, 1e-6, ("maxTimeLimit",))})
    assert com.resultado.situacao == "encerrada"
    assert {x.conteudo.aceitacao for x in com.resultado.registros} == {"aceito_factivel_dentro_da_politica"}
    assert aud(com).aceito


def test_retomada_de_checkpoint_com_highs(tmp_path):
    from ems_v2.mpc.persistencia import comandos_aplicados, retomar_controlador
    cont = X.executar("t12").resultado
    ctrl, ent, mod, ver = X.montar("t12", diretorio=tmp_path)
    O.executar_missao_simulada(ctrl, ent, max_janelas=2, finalizar=False)
    novo, ent2, _, _ = X.montar("t12")
    c2, pt = retomar_controlador(tmp_path, novo.cfg, novo.modelo, novo.provedor, novo.resolvedor, F.fontes(),
                                 identificadores_verdade=(X.PLANTA,), fontes_verdade=(F.FONTE_VERDADE,))
    ent2.reconstituir(comandos_aplicados(pt), O.instante_fronteira(novo.cfg.malha, pt.k))
    fim = O.executar_missao_simulada(c2, ent2)
    assert pt.k == 4 and fim.registro_missao.impressao_deterministica == cont.registro_missao.impressao_deterministica


# ------------------------------------------------------------------------------------------- 18, 19 + E1, E3, E4
def test_reproducao_determinista_com_highs(e2):
    b = X.e2_previsao_reemitida()["mpc"].resultado
    assert b.registro_missao.impressao_deterministica == e2.resultado.registro_missao.impressao_deterministica


def test_e3_open_loop_versus_mpc_em_condicoes_comparaveis(e3):
    ol, mpc = e3["open_loop"], e3["mpc"]
    c = comparar_missoes(ol.resultado, mpc.resultado, mpc.modelo, rotulo_a="open_loop", rotulo_b="mpc")
    assert c.comparavel and c.tipo == "causal" and not [x for x in c.constatacoes if x.severidade == "erro"]
    assert c.linhas["custo_realizado_total_R"][:2] == (pytest.approx(18.7, abs=1e-9), pytest.approx(12.9, abs=1e-9))
    assert c.linhas[f"E_final_kWh[{F.BESS}]"][:2] == (pytest.approx(0.0, abs=1e-9), pytest.approx(2.5, abs=1e-9))
    assert c.linhas["resolucoes"][:2] == (1, 4) and "Sem veredito" in c.observacao
    assert aud(ol).aceito and aud(mpc).aceito


def test_e3_comparador_recusa_condicoes_diferentes(e3, e2):
    outro = X.executar("e3-outra-verdade", pv_real=[10.0, 10.0] + [20.0] * 6).resultado
    cs = {x.codigo for x in condicoes_comparaveis(e3["mpc"].resultado, outro)}
    assert "realizacao_nao_comparavel" in cs
    tab = X.executar("e3-tabela", tipo="tabela").resultado
    assert "informacao_nao_comparavel" in {x.codigo for x in condicoes_comparaveis(e3["mpc"].resultado, tab)}


def test_e1_oraculo_rotulado_e_excluido_das_comparacoes_causais(e3):
    e1 = X.e1_oraculo()
    mpc, ref = e1["mpc"], e1["horizonte_completo"]
    for ex in (mpc, ref):
        assert ex.resultado.configuracao.rotulo_informacao == "ablacao_oraculo"
        assert all(x.conteudo.previsao.previsao_perfeita for x in ex.resultado.registros) and aud(ex).aceito
    assert "informacao_nao_comparavel" in {x.codigo for x in condicoes_comparaveis(mpc.resultado, e3["mpc"].resultado)}
    c = comparar_missoes(ref.resultado, mpc.resultado, mpc.modelo, rotulo_a="oraculo_N8", rotulo_b="oraculo_mpc")
    assert c.comparavel and c.tipo == "referencia_oraculo"
    assert c.linhas["custo_realizado_total_R"][0] == pytest.approx(2.075, abs=1e-9)
    assert c.linhas["custo_realizado_total_R"][1] == pytest.approx(2.075, abs=1e-9)


def test_e4_frequencia_de_reotimizacao():
    e4 = X.e4_frequencia()
    tot = {m: e4[m].resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R for m in e4}
    assert {m: len(e4[m].resultado.registros) for m in e4} == {1: 8, 2: 4, 4: 2}
    assert tot[1] == pytest.approx(7.2625, abs=1e-9) and tot[2] == pytest.approx(12.9, abs=1e-9) == tot[4]
    assert e4[1].resultado.registro_missao.conteudo.obrigacoes_pendentes_fim_s == {F.FC: 1800}
    for m in e4:
        assert aud(e4[m]).aceito
    c = comparar_missoes(e4[2].resultado, e4[1].resultado, e4[1].modelo, rotulo_a="m2", rotulo_b="m1")
    assert c.comparavel


def test_metricas_de_previsao_computacao_e_confiabilidade(e2):
    m = metricas_missao(e2.resultado, e2.modelo)
    fv = m.previsao[f"{F.FV}|potencia"]
    assert fv[0]["n"] == 4 and fv[0]["erro_medio"] == pytest.approx(-15.0 / 4)    # só τ_2 erra (10 previsto × 25)
    assert fv[0]["max_abs"] == 15.0 and fv[3]["n"] == 3                           # ℓ = 3 só existe em janelas N_k = 4
    assert m.computacao["resolucoes"] == 4 and m.computacao["solver_s"]["n"] == 4
    assert m.confiabilidade["por_aceitacao"] == {"aceito_otimo": 4} and m.confiabilidade["inviabilidades"] == 0


def test_realizacao_inviavel_por_falta_de_bateria_e_classificada():
    ex = X.executar("t-inv", modelo_kw={"e0": 0.0, "pmax_bess": 1.0, "fc_ligado": False, "fc_p": 0.0,
                                        "fc_tempo_s": 900})
    r = ex.resultado
    assert r.classe_falha == "inviavel" and ex.entorno.proximo_indice == 0
    assert r.registros[0].conteudo.resolucao.classificacao == "inviavel"


def test_construcao_com_identidade_divergente_no_meio_da_missao():
    ctrl, ent, _, _ = X.montar("t15")
    O.executar_missao_simulada(ctrl, ent, max_janelas=1, finalizar=False)
    ctrl.estado = dataclasses.replace(ctrl.estado, microrrede_uid="syn-outra-microrrede")
    O.executar_missao_simulada(ctrl, ent)
    assert ctrl.classe_falha == "identidade_divergente" and ent.proximo_indice == 2
    with pytest.raises(ContratoInvalido):
        O.ControladorMPC(ctrl.cfg, ctrl.modelo, ctrl.provedor, ctrl.resolvedor, F.fontes(),
                         estado_inicial=ctrl.estado)
    _ = (Realizacao, SerieRecurso)
