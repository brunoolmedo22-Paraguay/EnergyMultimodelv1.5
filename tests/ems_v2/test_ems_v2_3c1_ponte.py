"""Piso 3C-1 — integração com a ponte 3C-0: requisitos bloqueantes, projeção por UNIDADE, preflight, cadeia de ensaio
completa (HiGHS) e microrrede REAL do catálogo bloqueada com explicação (sem gravação; C-3C0-01 não estendida).
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

from ems_v2 import FORMULACAO_3C1
from ems_v2 import fixtures_3c0 as F
from ems_v2.compromisso.contrato import PoliticaPermanenciaTerminal
from ems_v2.parameters import Parametro
from ems_v2.ponte import requisitos as RQ
from ems_v2.ponte.compromisso import CondicaoInicialUnidade, DeclaracaoCommitment3C1, montar_entrada_3c1
from ems_v2.ponte.preflight import preflight_ems_v2
from ems_v2.provenance import Procedencia

pytestmark = pytest.mark.synthetic_algebraic
MG = "syn-mg-a"


def termica_3c1(**extra):
    d = F.termica(MG)
    vals = dict(ramp_kW_min=("kW/min", 2.0), t_on_min=("min", 30.0), t_off_min=("min", 15.0),
                startup_cost_rs=("R$", 3.0), shutdown_cost_rs=("R$/evento", 1.0))
    vals.update(extra)
    for k, v in vals.items():
        d = F.com_valor(d, k, None if v is None else F.num(k, v[0], v[1], MG, d.uid))
    return d


def inventario(ter=None, quantidade=None):
    t = ter or termica_3c1()
    if quantidade is not None:
        t = dataclasses.replace(t, quantidade=quantidade)
    return F.inventario(MG, (F.bateria(MG), F.usina(MG), F.arranjo(MG), t))


def declaracao(unidades=(), termos=("eventos",), abst="instantanea_unidade_quente"):
    return DeclaracaoCommitment3C1(
        PoliticaPermanenciaTerminal("obrigacao_residual_vinculante", "Ensaio 3C-1: continuidade após a janela",
                                    F.proc()),
        termos, {"syn-ter1": abst}, {"syn-ter1": "rampa_convencional"}, "Ensaio 3C-1 (unidade quente declarada)",
        tuple(unidades), F.proc())


# ----------------------------------------------------------------------------- requisitos 3C-1 bloqueantes
def test_requisitos_futuro_3C1_viram_bloqueantes_so_com_o_perfil():
    inv = inventario(termica_3c1(ramp_kW_min=None, t_on_min=None))
    sem = {(c.simbolo, c.codigo) for c in RQ.matriz_parametros(inv, contexto="ensaio").entradas if c.uid == "syn-ter1"}
    assert ("rampa", "necessario_3C1") in sem and ("t_on_min", "necessario_3C1") in sem      # 3C-0 inalterado
    m = RQ.matriz_parametros(inv, contexto="ensaio", perfil=FORMULACAO_3C1)
    ent = {c.simbolo: c for c in m.entradas if c.uid == "syn-ter1"}
    assert ent["rampa"].bloqueia and ent["rampa"].codigo == "parametro_obrigatorio_ausente"
    assert ent["t_on_min"].bloqueia and not ent["t_off_min"].bloqueia
    assert not ent["C_SU"].bloqueia and ent["C_SU"].codigo != "parametro_obrigatorio_ausente"
    m2 = RQ.matriz_parametros(inventario(termica_3c1(shutdown_cost_rs=None)), termos={"eventos"}, contexto="ensaio",
                              perfil=FORMULACAO_3C1)
    assert next(c for c in m2.entradas if c.uid == "syn-ter1" and c.simbolo == "C_SD").bloqueia
    with pytest.raises(ValueError):
        RQ.matriz_parametros(inv, perfil="v9")


# ----------------------------------------------------------------------------- projeção
def test_projecao_3c1_de_inventario_sintetico_e_preflight_apto():
    inv = inventario()
    cen, dt, pol, prev, real = F.cenario(inv), F.definicao(), F.politicas(), F.previsao(oraculo=True), F.realizacao()
    e3, cs, _ = montar_entrada_3c1(inv, cen, prev, dt, pol, declaracao(), contexto="ensaio")
    assert e3 is not None, [(c.codigo, c.caminho) for c in cs if c.severidade != "aviso"]
    u = e3.unidade("syn-ter1")
    assert u.rampa_subida_kW_min.valor == 2.0 == u.rampa_descida_kW_min.valor
    assert "subida E à descida" in u.rampa_subida_kW_min.procedencia.observacoes
    assert u.custo_partida.valor == 3.0 and u.custo_parada.valor == 1.0 and u.custo_partida.unidade == "R$/evento"
    assert [t.etapa for t in u.custo_partida.transformacoes] == ["reinterpretacao_declarada"]   # R$ ≡ R$/evento registrado
    assert e3.memoria("syn-ter1").tempo_no_estado_s == 3600 and e3.memoria("syn-ter1").obrigacao_residual_s == 0
    rel, proj = preflight_ems_v2(inv, cen, dt, prev, real, pol, contexto="ensaio", commitment_3c1=declaracao())
    assert rel.apto_para_otimizacao, rel.texto()
    assert proj.entrada == e3
    # sem a declaração o preflight continua o 3C-0 (perfil 3B-P exige compromisso fixo)
    rel0, _ = preflight_ems_v2(inv, cen, dt, prev, real, pol, contexto="ensaio")
    assert not rel0.apto_para_otimizacao and "compromisso_livre_nao_suportado_3BP" in rel0.codigos()


def test_projecao_3c1_parametro_ausente_bloqueia_nunca_ilimitado():
    inv = inventario(termica_3c1(ramp_kW_min=None))
    e3, cs, _ = montar_entrada_3c1(inv, F.cenario(inv), F.previsao(), F.definicao(), F.politicas(), declaracao(),
                                   contexto="ensaio")
    assert e3 is None and ("parametro_obrigatorio_ausente", "dispositivos[syn-ter1].rampa") in {(c.codigo, c.caminho)
                                                                                                for c in cs}


def test_projecao_por_unidade_sem_distribuir_agregado():
    inv = inventario(quantidade=2)
    cen = F.cenario(inv)
    cen = dataclasses.replace(cen, condicoes_iniciais=tuple(
        dataclasses.replace(c, unidades_ligadas=1) if c.uid == "syn-ter1" else c for c in cen.condicoes_iniciais))
    e3, cs, _ = montar_entrada_3c1(inv, cen, F.previsao(), F.definicao(), F.politicas(), declaracao(), contexto="ensaio")
    assert e3 is None and "estado_por_unidade_nao_declarado" in {c.codigo for c in cs}
    p = lambda v: Parametro(v, "kW", F.proc())  # noqa: E731
    un = (CondicaoInicialUnidade("syn-ter1#1", "em_operacao", p(10.0), 3600, F.proc()),
          CondicaoInicialUnidade("syn-ter1#2", "desligada", p(0.0), 300, F.proc()))
    e3, cs, _ = montar_entrada_3c1(inv, cen, F.previsao(), F.definicao(), F.politicas(), declaracao(un),
                                   contexto="ensaio")
    assert e3 is not None, [(c.codigo, c.caminho) for c in cs if c.severidade != "aviso"]
    est = {str(s.uid): s for s in e3.base.estados_geradores}
    assert est["syn-ter1#1"].ligado and not est["syn-ter1#2"].ligado
    assert e3.memoria("syn-ter1#2").obrigacao_residual_s == 600          # T_off 15 min − 300 s
    un_em_partida = (un[0], dataclasses.replace(un[1], estado_discreto="em_partida"))
    e3, cs, _ = montar_entrada_3c1(inv, cen, F.previsao(), F.definicao(), F.politicas(), declaracao(un_em_partida),
                                   contexto="ensaio")
    assert e3 is None and "estado_em_partida_nao_representavel" in {c.codigo for c in cs}


def test_declaracao_de_commitment_sem_padrao():
    inv = inventario()
    d = dataclasses.replace(declaracao(), abstracao_por_equipamento={})
    e3, cs, _ = montar_entrada_3c1(inv, F.cenario(inv), F.previsao(), F.definicao(), F.politicas(), d, contexto="ensaio")
    assert e3 is None and "declaracao_commitment_ausente" in {c.codigo for c in cs}


# ----------------------------------------------------------------------------- cadeia de ensaio com HiGHS
def test_cadeia_3c1_ensaio_completa_com_milp_real():
    pytest.importorskip("pyomo", exc_type=ImportError)
    from ems_v2.milp.config import CONFIG_ANALITICA
    from ems_v2.milp.solver_3c1 import resolver_3c1
    from ems_v2.ponte.compromisso import (ExecutorAlgebricoCommitment3C1, custo_eventos_realizado, estado_inicial_3c1,
                                          plano_de_resultado_3c1)
    from ems_v2.ponte.execucao import executar
    inv = inventario()
    cen, dt, pol, prev, real = F.cenario(inv), F.definicao(), F.politicas(), F.previsao(oraculo=True), F.realizacao()
    rel, proj = preflight_ems_v2(inv, cen, dt, prev, real, pol, contexto="ensaio", commitment_3c1=declaracao())
    assert rel.apto_para_otimizacao
    res = resolver_3c1(proj.entrada, CONFIG_ANALITICA)
    assert res.aceito, res.codigos()
    plano, pc = plano_de_resultado_3c1(res, proj.entrada)
    traj = executar(plano, estado_inicial_3c1(proj.entrada), ExecutorAlgebricoCommitment3C1(proj.entrada), real,
                    execucao_uid="0123456789abcdef0123456789abcdef")
    assert traj.situacao == "concluida" and len(traj.passos) == plano.N
    c = custo_eventos_realizado(proj.entrada, traj)
    assert c.valor_R == pytest.approx(pc.custo_eventos_planejado_R or 0.0)


# ----------------------------------------------------------------------------- microrrede REAL do catálogo
def test_microrrede_real_bloqueada_no_3c1_com_explicacao(tmp_path):
    pytest.importorskip("streamlit", exc_type=ImportError)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from seeds2_fixtures import battery_params  # noqa: F401
    from test_ems_v2_ponte_seeds2 import _config_b
    from ems_v2.ponte_seeds2 import leitor as L
    from seeds2.microgrid.registry import MicrogridRegistry
    from seeds2.operation import service as SV
    reg = MicrogridRegistry(tmp_path / "dados", adopt_legacy=False)
    b = _config_b()
    reg.create(b)
    ub = b["installation"]["uid"]
    st = reg.open(ub)
    sc = SV.create(st, name="Cenário B")
    db = Path(tmp_path / "dados" / "microgrids" / ub / "seeds2.db")
    antes = db.read_bytes()
    inv, cen = L.ler_inventario(reg, ub), L.ler_cenario(reg, ub, sc.scenario_uid)
    m = RQ.matriz_parametros(inv, termos={"eventos"}, contexto="operacional", perfil=FORMULACAO_3C1)
    ter = {c.simbolo: c for c in m.entradas if c.tipo == "termica"}
    for s in ("rampa", "t_on_min", "t_off_min", "C_SD"):
        assert ter[s].bloqueia and ter[s].codigo == "parametro_obrigatorio_ausente", s      # vazio ≠ sem limite
    assert not ter["C_SU"].bloqueia and ter["C_SU"].procedencia.tipo == "declarado_seeds2"
    pol = dataclasses.replace(F.politicas(), procedencia=Procedencia("decisao_responsavel", "teste"))
    d = dataclasses.replace(declaracao(), abstracao_por_equipamento={e: "instantanea_unidade_quente" for e in inv.uids()},
                            limites_por_equipamento={e: "rampa_convencional" for e in inv.uids()})
    e3, cs, _ = montar_entrada_3c1(inv, cen, F.previsao(), F.definicao(), pol, d, contexto="operacional")
    assert e3 is None
    cods = {(c.caminho.split(".")[-1], c.codigo) for c in cs}
    assert ("rampa", "parametro_obrigatorio_ausente") in cods and ("t_on_min", "parametro_obrigatorio_ausente") in cods
    assert db.read_bytes() == antes                                                       # somente leitura
