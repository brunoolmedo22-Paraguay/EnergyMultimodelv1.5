"""Piso 3C-2 — contratos temporais, políticas declaradas e aceitação (SEM solver). Sintético/algébrico."""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from ems_v2 import fixtures_3c2 as F
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.mpc import contrato as CT
from ems_v2.mpc.relogio import RelogioMissao, cronograma_nominal, janela_em
from ems_v2.timegrid import MalhaTemporal

pytestmark = pytest.mark.synthetic_algebraic


def codigos(cs):
    return {c.codigo for c in cs if c.severidade == "erro"}


def test_configuracao_valida_e_cada_politica_sem_padrao():
    cfg = F.configuracao("c1", 8, 4, 2)
    assert codigos(CT.validar_configuracao_mpc(cfg)) == set()
    ruins = {
        "modo_experimental_invalido": dataclasses.replace(cfg, modo="tempo_real"),
        "rotulo_informacao_invalido": dataclasses.replace(cfg, rotulo_informacao=""),
        "politica_revisao_tardia_invalida": dataclasses.replace(cfg, politica_revisao_tardia="reescrever"),
        "politica_terminal_invalida": dataclasses.replace(cfg, politica_terminal=dataclasses.replace(
            cfg.politica_terminal, tipo="corte_silencioso")),
        "politica_permanencia_invalida": dataclasses.replace(cfg, politica_terminal=dataclasses.replace(
            cfg.politica_terminal, permanencia_janela_final="")),
        "politica_sem_justificativa": dataclasses.replace(cfg, politica_aceitacao=dataclasses.replace(
            cfg.politica_aceitacao, justificativa=" ")),
        "missao_uid_invalido": dataclasses.replace(cfg, identidade=dataclasses.replace(cfg.identidade, missao_uid="x")),
    }
    for cod, c in ruins.items():
        assert cod in codigos(CT.validar_configuracao_mpc(c)), cod


def test_malha_m_maior_que_N_e_H_f_obrigatorio():
    cfg = F.configuracao("c2", 8, 4, 2)
    m5 = MalhaTemporal(F.INICIO, F.DELTA, 4, 5, 8, F.DELTA * 4)
    assert "reotimizacao_maior_que_horizonte" in codigos(CT.validar_configuracao_mpc(dataclasses.replace(cfg, malha=m5)))
    sem_hf = MalhaTemporal(F.INICIO, F.DELTA, 4, 2, 8, None)
    assert "horizonte_previsao_obrigatorio_mpc" in codigos(CT.validar_configuracao_mpc(dataclasses.replace(cfg, malha=sem_hf)))
    hf_curto = MalhaTemporal(F.INICIO, F.DELTA, 4, 2, 8, F.DELTA * 3)
    assert "horizonte_previsao_insuficiente" in codigos(CT.validar_configuracao_mpc(dataclasses.replace(cfg, malha=hf_curto)))


def test_politica_de_falhas_completa_sem_contingencia_e_classes_so_interromper():
    cfg = F.configuracao("c3", 8, 4, 2)
    acoes = dict(cfg.politica_falhas.acoes)
    del acoes["inviavel"]
    c = dataclasses.replace(cfg, politica_falhas=dataclasses.replace(cfg.politica_falhas, acoes=acoes))
    assert "acao_falha_nao_declarada" in codigos(CT.validar_configuracao_mpc(c))
    for k, a, cod in (("falha_solver", "despacho_de_reserva", "acao_falha_invalida"),
                      ("integridade", "suspender", "acao_falha_nao_admitida"),
                      ("consigna_inexequivel", "suspender", "acao_falha_nao_admitida")):
        ac = {**cfg.politica_falhas.acoes, k: a}
        c = dataclasses.replace(cfg, politica_falhas=dataclasses.replace(cfg.politica_falhas, acoes=ac))
        assert cod in codigos(CT.validar_configuracao_mpc(c)), (k, a)


def test_politica_de_aceitacao_nao_otimo_exige_gap_e_terminacoes():
    cfg = F.configuracao("c4", 8, 4, 2, aceit=F.aceitacao(True, None, ()))
    cs = codigos(CT.validar_configuracao_mpc(cfg))
    assert {"gap_maximo_nao_declarado", "terminacoes_admitidas_invalidas"} <= cs
    cfg = F.configuracao("c4b", 8, 4, 2, aceit=F.aceitacao(False, 0.01, ()))
    assert "politica_aceitacao_contraditoria" in codigos(CT.validar_configuracao_mpc(cfg))


def _res(**kw):
    base = dict(aceito=True, despacho={}, classificacao="otimo", estado_despacho="aceito_otimo", gap_rel=0.0,
                terminacao="convergenceCriteriaSatisfied")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("res,cat", [
    (None, "falha_solver"),
    (_res(aceito=False, despacho=None, classificacao="sem_solucao", estado_despacho="sem_despacho"), "falha_solver"),
    (_res(aceito=False, despacho=None, classificacao="inviavel", estado_despacho="sem_despacho"), "inviavel"),
    (_res(aceito=False, estado_despacho="rejeitado_auditoria"), "rejeitado_auditoria"),
    (_res(aceito=False, estado_despacho="rejeitado_integridade"), "rejeitado_integridade"),
    (_res(aceito=False, despacho=None, classificacao="bloqueado_validacao", estado_despacho="sem_despacho"),
     "bloqueado_validacao"),
    (_res(), "aceito_otimo"),
])
def test_aceitacao_nunca_aceita_sem_incumbente_ou_rejeitado(res, cat):
    d = CT.avaliar_aceitacao(res, F.aceitacao())
    assert d.categoria == cat and d.aceito == (cat == "aceito_otimo")


def test_aceitacao_de_factivel_nao_otimo_so_dentro_da_politica():
    r = _res(classificacao="factivel_nao_otimo", estado_despacho="aceito_factivel_nao_otimo", terminacao="maxTimeLimit",
             gap_rel=0.004)
    assert CT.avaliar_aceitacao(r, F.aceitacao()).categoria == "fora_politica_aceitacao"
    assert CT.avaliar_aceitacao(r, F.aceitacao(True, 0.01, ("maxTimeLimit",))).categoria == \
        "aceito_factivel_dentro_da_politica"
    assert CT.avaliar_aceitacao(r, F.aceitacao(True, 0.001, ("maxTimeLimit",))).categoria == "fora_politica_aceitacao"
    assert CT.avaliar_aceitacao(r, F.aceitacao(True, 0.01, ("iterationLimit",))).categoria == "fora_politica_aceitacao"
    sem_gap = _res(classificacao="factivel_nao_otimo", estado_despacho="aceito_factivel_nao_otimo",
                   terminacao="maxTimeLimit", gap_rel=None)
    assert CT.avaliar_aceitacao(sem_gap, F.aceitacao(True, 0.01, ("maxTimeLimit",))).categoria == "fora_politica_aceitacao"


def test_terminacoes_limite_coincidem_com_o_3bp():
    from ems_v2.milp.resultado import LIMITES
    assert set(CT.TERMINACOES_LIMITE) == LIMITES


# ------------------------------------------------------------------------------------------- relógio e janelas
def test_cronograma_m_menor_que_N_e_ultimo_bloco_curto():
    cfg = F.configuracao("r1", 7, 4, 2)
    js = cronograma_nominal(cfg)
    assert [(j.k, j.N_k, j.m_k) for j in js] == [(0, 4, 2), (2, 4, 2), (4, 3, 2), (6, 1, 1)]
    assert [j.reduzida for j in js] == [False, False, True, True]
    assert js[-1].final and js[-1].m_k == 1 < 2          # último bloco com menos de m intervalos
    assert sum(j.m_k for j in js) == 7                   # nunca excede K_M
    assert [j.politica_permanencia for j in js] == ["obrigacao_residual_vinculante"] * 4


def test_janela_reduzida_x_horizonte_estendido():
    red = F.configuracao("r2", 6, 4, 2, perm_final="cumprir_na_janela")
    assert [(j.N_k, j.intervalos_pos_missao, j.politica_permanencia) for j in cronograma_nominal(red)] == \
        [(4, 0, "obrigacao_residual_vinculante"), (4, 0, "cumprir_na_janela"), (2, 0, "cumprir_na_janela")]
    est = F.configuracao("r3", 6, 4, 2, terminal="horizonte_estendido_declarado", cobertura=30.0)
    assert codigos(CT.validar_configuracao_mpc(est)) == set()
    js = cronograma_nominal(est)
    assert [(j.N_k, j.intervalos_pos_missao, j.m_k, j.intervalos_missao_entrada) for j in js] == \
        [(4, 0, 2, 6), (4, 0, 2, 4), (4, 2, 2, 4)]
    assert CT.cobertura_pos_missao_exigida_min(est.malha) == 30.0
    curto = F.configuracao("r4", 6, 4, 2, terminal="horizonte_estendido_declarado", cobertura=15.0)
    assert "cobertura_pos_missao_insuficiente" in codigos(CT.validar_configuracao_mpc(curto))
    sem = F.configuracao("r5", 6, 4, 2, terminal="horizonte_estendido_declarado")
    assert "cobertura_pos_missao_nao_declarada" in codigos(CT.validar_configuracao_mpc(sem))
    contra = F.configuracao("r6", 6, 4, 2, cobertura=15.0)
    assert "cobertura_pos_missao_contraditoria" in codigos(CT.validar_configuracao_mpc(contra))


def test_horizonte_maior_que_missao_tratado_pela_politica_e_malha_da_entrada_valida():
    from ems_v2.timegrid import validar_malha
    cfg = F.configuracao("r7", 3, 4, 2)                  # N = 4 > K_M = 3
    cs = CT.validar_configuracao_mpc(cfg)
    assert codigos(cs) == set() and "horizonte_alem_da_missao_tratado_pela_politica_terminal" in {c.codigo for c in cs}
    for j in cronograma_nominal(cfg):
        assert not [c for c in validar_malha(j.malha(cfg.malha)) if c.severidade != "aviso"]


def test_relogio_monotonico_e_avanco_limitado():
    cfg = F.configuracao("r8", 5, 4, 2)
    r = RelogioMissao(cfg)
    assert (r.k, r.indice_janela, r.instante_utc) == (0, 0, F.INICIO)
    for n in (0, 3, True, 2.0):
        with pytest.raises(ContratoInvalido):
            r.avancar(n)
    r.avancar(2)
    r.avancar(1)                                          # aplicação parcial ainda avança (nunca retrocede)
    assert (r.k, r.indice_janela) == (3, 2)
    r.avancar(2)
    assert r.encerrado and r.k == 5
    with pytest.raises(ContratoInvalido):
        janela_em(cfg, 9, 5)                              # nenhuma janela começa no fim da missão


def test_identidade_vira_referencia_origem_3c0():
    i = F.identidade("x")
    o = i.referencia_origem()
    assert (o.microrrede_uid, o.cenario_uid, o.versao_cenario) == (i.microrrede_uid, i.cenario_uid, 1)


def test_capacidade_m23_declarada_parcial_e_perfil_3c1_preservado():
    import json
    from pathlib import Path
    from ems_v2.capabilities import CAPACIDADES_3C1
    from ems_v2.mpc.capacidades import CAPACIDADES_3C2
    mpc = [c for c in CAPACIDADES_3C2 if c.familia == "mpc"]
    assert len(mpc) == 1 and mpc[0].equacoes == ("M23",) and mpc[0].status == "parcial_3C2"
    assert "ALGÉBRICO" in mpc[0].observacoes
    assert [c for c in CAPACIDADES_3C2 if c.familia != "mpc"] == [c for c in CAPACIDADES_3C1 if c.familia != "mpc"]
    eqs = json.loads((Path(__file__).resolve().parents[2] / "ems_v2/catalogo/equacoes.json").read_text("utf-8"))
    m23 = next(e for e in eqs["equacoes"] if e["id"] == "M23")
    assert {"x_state", "Phi_phys", "u_applied", "w_dist", "m_reopt"} <= set(m23["simbolos"])
