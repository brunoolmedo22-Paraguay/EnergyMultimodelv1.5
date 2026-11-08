"""Auditor algébrico independente: aceita as candidatas analíticas e REJEITA mutações explícitas de potência,
disponibilidade e estado (ordem 3A.4; condição A). Sintético/algébrico — não é validação física."""
import ast
from dataclasses import replace
from pathlib import Path

import pytest

from ems_v2 import fixtures as F
from ems_v2.audit import CandidatoDespacho, Tolerancias, auditar, auditar_pwl
from ems_v2.contracts import DispositivoDescarte, PoliticaServico, UIDRecurso
from ems_v2.parameters import Parametro

pytestmark = pytest.mark.synthetic_algebraic
REF = {"A01": F.a01, "A02": F.a02, "A03": F.a03, "A04": F.a04, "B01A": F.b01a, "B01B": F.b01b,
       "A03-60": lambda: F.a03(1, 60)}
TOL = Tolerancias()


@pytest.mark.parametrize("caso", sorted(REF))
def test_candidatas_analiticas_aceitas(caso):
    e, c = REF[caso]()
    r = auditar(e, c)
    assert r.aceito, (caso, r.reprovados[:3], r.constatacoes)
    assert r.rotulo.startswith("sintetico/algebrico") and "não é validação física" in r.rotulo


def test_b01_custos_e_kpis_reconstruidos():
    ra, rb = auditar(*F.b01a()), auditar(*F.b01b())
    assert ra.custos_reconstruidos["curtailment_operacional"] == 0.0
    assert ra.kpis_reconstruidos["E_indisp_kWh"]["syn-fv"] == 100.0
    assert rb.custos_reconstruidos["curtailment_operacional"] == 10.0
    assert rb.kpis_reconstruidos["E_curt_oper_kWh"]["syn-fv"] == 20.0


def test_a05_feas_carregar_e_verter_ambos_factiveis():
    """Balanço sozinho não determina o despacho (B02): nenhuma otimalidade é inferida."""
    e, carregar, verter = F.a05_feas()
    assert auditar(e, carregar).aceito and auditar(e, verter).aceito


def _mutacoes(c: CandidatoDespacho):
    for grupo in ("renovaveis", "baterias", "demandas"):
        for uid, d in getattr(c, grupo).items():
            for var, vals in d.items():
                for i in range(len(vals)):
                    yield grupo, uid, var, i


def _mutar(c, grupo, uid, var, i, delta):
    d = dict(getattr(c, grupo))
    vs = list(d[uid][var])
    vs[i] += delta
    d[uid] = {**d[uid], var: tuple(vs)}
    return replace(c, **{grupo: d})


@pytest.mark.parametrize("caso", ["A01", "A02", "A03", "A04", "B01A", "B01B", "A05-FEAS"])
def test_toda_mutacao_isolada_acima_da_tolerancia_e_rejeitada(caso):
    if caso == "A05-FEAS":
        e, c, _ = F.a05_feas()
    else:
        e, c = REF[caso]()
    n = 0
    for grupo, uid, var, i in _mutacoes(c):
        for delta in (1e-3, -1e-3):
            r = auditar(e, _mutar(c, grupo, uid, var, i, delta))
            assert not r.aceito, (caso, grupo, uid, var, i, delta)
            n += 1
    assert n > 0


def test_mutacao_dentro_da_tolerancia_provisoria_aceita():
    """Tolerância por grandeza (1e-5 kW + 1e-7 P_scale): perturbação de 1e-7 kW é aceita; 1e-3 kW não."""
    e, c = F.b01b()
    dentro = _mutar(_mutar(c, "renovaveis", "syn-fv", "P_R", 0, 1e-7), "renovaveis", "syn-fv", "C_oper", 0, -1e-7)
    r = auditar(e, dentro)
    assert r.aceito
    tolP = TOL.potencia_abs_kW + TOL.potencia_rel_escala * 100      # P_scale = max(1, ΣL, ΣA_pot) = 100 kW
    assert r.maximos["balanco"][2] == pytest.approx(tolP)
    fora = _mutar(_mutar(c, "renovaveis", "syn-fv", "P_R", 0, 1e-3), "renovaveis", "syn-fv", "C_oper", 0, -1e-3)
    assert auditar(e, fora).familias_reprovadas() == {"balanco", "custo", "kpi_energia"}   # KPI reportado também diverge
    assert TOL.status == "provisoria" and "D07" in TOL.origem


def test_tolerancias_heterogeneas_por_familia():
    r = auditar(*F.a03())
    unid = {f: u for f, (_, u, _) in r.maximos.items()}
    assert unid["balanco"] == "kW" and unid["bess_energia"] == "kWh" and unid["bess_soc"] == "kWh"
    tols = {f: t for f, (_, _, t) in r.maximos.items()}
    assert tols["bess_energia"] == pytest.approx(TOL.energia_abs_kWh + TOL.energia_rel_capacidade * 100)
    assert tols["bess_soc"] == pytest.approx(TOL.soc_fracao * 100)


def test_mutacao_de_disponibilidade_na_entrada():
    e, c = F.b01b()
    r = e.renovaveis[0]
    e0 = replace(e, renovaveis=(replace(r, disponibilidade=replace(r.disponibilidade, serie=replace(
        r.disponibilidade.serie, valores=(0.0,)))),))
    rel = auditar(e0, c)
    assert not rel.aceito and "renovavel" in rel.familias_reprovadas()


def test_mutacao_do_estado_inicial_na_entrada():
    e, c = F.a03()
    st = replace(e.estados_baterias[0], energia_kWh=Parametro(61.0, "kWh", F.proc("A03")))
    rel = auditar(replace(e, estados_baterias=(st,)), c)
    assert not rel.aceito and "bess_estado_inicial" in rel.familias_reprovadas()


def test_indisponibilidade_cobrada_como_vertimento():
    e, c = F.b01a()
    c1 = replace(c, renovaveis={"syn-fv": {"P_R": (0.0,), "C_oper": (100.0,)}},
                 custos_reportados={"curtailment_operacional": 50.0})
    r = auditar(e, c1)
    assert not r.aceito and "indisponibilidade_registrada_como_curtailment" in r.codigos()
    assert "renovavel" in r.familias_reprovadas()        # M03-v1.1: P + C_oper ≠ a·A_pot = 0
    c2 = replace(c, custos_reportados={"curtailment_operacional": 50.0})   # custo inflado com C_oper = 0
    r2 = auditar(e, c2)
    assert not r2.aceito and r2.familias_reprovadas() == {"custo"}
    c3 = replace(c, kpis_reportados={"E_indisp_kWh": {"syn-fv": 0.0}})
    assert not auditar(e, c3).aceito


def test_soc_saturado_por_recorte_rejeitado():
    """Descarga que levaria e < C s_min: a candidata 'recortada' viola M07; a não recortada viola M08."""
    e, _ = F.a03()
    st = replace(e.estados_baterias[0], energia_kWh=Parametro(5.0, "kWh", F.proc("A03")))
    e5 = replace(e, estados_baterias=(st,))
    recortada = CandidatoDespacho(baterias={"syn-bess": {"P_c": (0.0,), "P_d": (9.0,), "e": (5.0, 0.0)}},
                                  demandas={"syn-carga": {"ell": (0.0,)}})
    r = auditar(e5, recortada)
    assert not r.aceito and "bess_energia" in r.familias_reprovadas()
    honesta = replace(recortada, baterias={"syn-bess": {"P_c": (0.0,), "P_d": (9.0,), "e": (5.0, -5.0)}})
    r2 = auditar(e5, honesta)
    assert not r2.aceito and r2.familias_reprovadas() == {"bess_soc"}


def test_carga_e_descarga_simultaneas_rejeitadas_mesmo_com_energia_coerente():
    e, _, _ = F.a05_feas()
    # P_c = 10, P_d = 9 (η = 0,9): e_1 = 50 + 9 − 10 = 49; balanço 20 + 9 − 10 − 10 = 9 ≠ 0 → corrigir com vertimento
    c = CandidatoDespacho(renovaveis={"syn-fv": {"P_R": (11.0,), "C_oper": (9.0,)}},
                          baterias={"syn-bess": {"P_c": (10.0,), "P_d": (9.0,), "e": (50.0, 49.0)}},
                          demandas={"syn-carga": {"ell": (0.0,)}})
    r = auditar(e, c)
    assert not r.aceito and r.familias_reprovadas() == {"bess_exclusividade"}


def test_demanda_critica_falsamente_interrompida():
    e, c = F.b01b()
    c1 = replace(c, renovaveis={"syn-fv": {"P_R": (70.0,), "C_oper": (30.0,)}}, demandas={"syn-carga": {"ell": (10.0,)}},
                 custos_reportados={}, kpis_reportados={})
    r = auditar(e, c1)
    assert not r.aceito and "interrupcao_nao_autorizada" in r.codigos()
    assert r.familias_reprovadas() == {"servico"}           # balanço fecha: só a autorização falha


def test_descarte_sem_dispositivo_fisico_e_com_dispositivo():
    e, c = F.b01b()
    c1 = replace(c, renovaveis={"syn-fv": {"P_R": (100.0,), "C_oper": (0.0,)}}, descarte=(20.0,), custos_reportados={},
                 kpis_reportados={})
    r = auditar(e, c1)
    assert not r.aceito and "descarte_sem_dispositivo_fisico" in r.codigos()
    dev = DispositivoDescarte(UIDRecurso("syn-dump"), Parametro(25.0, "kW", F.proc("teste")))
    e2 = replace(e, politica_servico=PoliticaServico("duro", F.proc("teste"), descarte=dev))
    assert auditar(e2, c1).aceito
    assert not auditar(e2, replace(c1, descarte=None)).aceito     # dispositivo declarado exige o vetor


def test_vetores_temporais_incompativeis_e_ausentes():
    e, c = F.a01()
    longo = replace(c, renovaveis={"syn-fv": {"P_R": (60.0,) * 61, "C_oper": (0.0,) * 60}})
    assert "instante_terminal_como_intervalo" in auditar(e, longo).codigos()
    falta = replace(c, demandas={})
    assert "variavel_candidata_ausente" in auditar(e, falta).codigos()
    nan = replace(c, renovaveis={"syn-fv": {"P_R": (float("nan"),) * 60, "C_oper": (0.0,) * 60}})
    assert "valor_ausente_ou_nao_finito" in auditar(e, nan).codigos()
    estranho = replace(c, renovaveis={**c.renovaveis, "syn-x": {"P_R": (0.0,) * 60, "C_oper": (0.0,) * 60}})
    assert "uid_desconhecido_na_candidata" in auditar(e, estranho).codigos()
    e3, c3 = F.a03()
    curto = replace(c3, baterias={"syn-bess": {"P_c": (0.0,), "P_d": (9.0,), "e": (60.0,)}})
    assert "comprimento_incompativel" in auditar(e3, curto).codigos()


def test_familias_nao_suportadas_rejeitadas():
    g, st, _ = F.a06_gerador(1, 60)
    e, c = F.a05_feas()[:2]
    r = auditar(replace(e, geradores=(g,), estados_geradores=(st,)), c)
    assert not r.aceito and "commitment_M09_M12" in r.familias_nao_suportadas
    r2 = auditar(e, replace(c, auxiliares=(0.0,)))
    assert not r2.aceito and "auxiliares_M05" in r2.familias_nao_suportadas


def test_entrada_invalida_nao_e_auditada():
    e, c = F.a03()
    e2 = replace(e, baterias=(replace(e.baterias[0], eta_descarga=Parametro(None, "1", F.proc("x"))),))
    r = auditar(e2, c)
    assert not r.aceito and "parametro_ausente" in r.codigos() and r.familias_verificadas == ()


# ----------------------------------------------------------------------------- A06 (PWL)
def test_a06_valores_preparados_aceitos():
    g, _, m = F.a06_gerador()
    r = auditar_pwl(g, m, [1], [15.0], [0.9], [0.015])
    assert r.aceito and {"vazao_pwl", "massa_h2", "dominio_on_off", "integralidade"} <= set(r.familias_verificadas)
    g2, _, m2 = F.a06_gerador(2)
    assert auditar_pwl(g2, m2, [0, 1], [0.0, 20.0], [0.0, 1.1], [0.0, 1.1 / 60]).aceito


@pytest.mark.parametrize("u,p,q,m,cod_ou_fam", [
    ([1], [5.0], [0.5], None, "on_fora_do_dominio"),
    ([0], [5.0], [0.0], None, "dominio_on_off"),
    ([0], [0.0], [0.1], None, "vazao_pwl"),
    ([1], [15.0], [0.95], None, "vazao_pwl"),
    ([1], [15.0], [0.9], [0.9], "massa_h2"),       # kg/h confundido com kg/intervalo
    ([0.5], [15.0], [0.9], None, "integralidade"),
    ([1], [25.0], [1.3], None, "on_fora_do_dominio"),
])
def test_a06_valores_adulterados_rejeitados(u, p, q, m, cod_ou_fam):
    g, _, mal = F.a06_gerador()
    r = auditar_pwl(g, mal, u, p, q, m)
    assert not r.aceito and (cod_ou_fam in r.codigos() or cod_ou_fam in r.familias_reprovadas())


def test_a06_curva_real_bloqueada_b04():
    g, _, m = F.a06_gerador()
    g2 = replace(g, curva_h2=replace(g.curva_h2, classificacao="real"))
    r = auditar_pwl(g2, m, [1], [15.0], [0.9])
    assert not r.aceito and "pwl_real_requer_certificacao_estatica" in r.codigos()


def test_auditor_independente_do_calculo_de_referencia():
    """Condição A: o auditor não importa o módulo de referência (verificação estática do código-fonte)."""
    src = (Path(__file__).resolve().parents[2] / "ems_v2" / "audit.py").read_text(encoding="utf-8")
    nomes = set()
    for no in ast.walk(ast.parse(src)):
        if isinstance(no, ast.ImportFrom):
            nomes.add((no.module or "") + ":" + ",".join(a.name for a in no.names))
        elif isinstance(no, ast.Import):
            nomes.update(a.name for a in no.names)
    assert not any("reference" in n for n in nomes), nomes
    assert "Fraction" not in src


# ----------------------------------------------------------------------------- auditoria do PR #11
def _b01b_com_descarte(d):
    """Contraejemplo C-3A-01: L = 80, P_R = 70, C_oper = 30; custo e KPIs coerentes com 30 kWh vertidos."""
    e, c = F.b01b()
    return e, replace(c, renovaveis={"syn-fv": {"P_R": (70.0,), "C_oper": (30.0,)}}, descarte=(d,),
                      custos_reportados={"curtailment_operacional": 15.0},
                      kpis_reportados={"E_curt_oper_kWh": {"syn-fv": 30.0}, "E_indisp_kWh": {"syn-fv": 0.0}})


def test_c3a01_descarte_negativo_sem_dispositivo_rejeitado():
    e, c = _b01b_com_descarte(-10.0)
    r = auditar(e, c)
    assert not r.aceito and "descarte_negativo" in r.codigos() and r.familias_reprovadas() == {"descarte"}
    assert r.maximos["descarte"][0] == pytest.approx(10.0)       # resíduo medido em kW, sem recorte


def test_c3a01_descarte_negativo_com_dispositivo_rejeitado():
    e, c = _b01b_com_descarte(-10.0)
    dev = DispositivoDescarte(UIDRecurso("syn-dump"), Parametro(25.0, "kW", F.proc("teste")))
    e2 = replace(e, politica_servico=PoliticaServico("duro", F.proc("teste"), descarte=dev))
    r = auditar(e2, c)
    assert not r.aceito and "descarte_negativo" in r.codigos() and r.familias_reprovadas() == {"descarte"}


def test_c3a01_descarte_nulo_sem_dispositivo_continua_aceito():
    """d = 0 explícito sem dispositivo é coerente (D̄ = 0); o balanço M02 não muda de convenção."""
    e, c = F.b01b()
    assert auditar(e, replace(c, descarte=(0.0,))).aceito


@pytest.mark.parametrize("campo", ["potencia_abs_kW", "potencia_rel_escala", "energia_abs_kWh",
                                   "energia_rel_capacidade", "soc_fracao", "custo_abs_R", "custo_rel", "binario",
                                   "vazao_abs_kg_h", "vazao_rel_qmax", "massa_abs_kg"])
@pytest.mark.parametrize("valor", [float("inf"), float("-inf"), float("nan"), -1e-9, "0.1", None, True])
def test_c3a02_tolerancia_invalida_rejeita_explicitamente(campo, valor):
    tol = replace(TOL, **{campo: valor})
    e, c = F.a01()
    adulterada = replace(c, renovaveis={"syn-fv": {"P_R": (61.0,) * 60, "C_oper": (0.0,) * 60}})
    for cand in (c, adulterada):
        r = auditar(e, cand, tol)
        assert not r.aceito and "tolerancia_invalida" in r.codigos() and r.familias_verificadas == ()
    g, _, m = F.a06_gerador()
    r = auditar_pwl(g, m, [1], [15.0], [0.9], [0.015], tol)
    assert not r.aceito and "tolerancia_invalida" in r.codigos()


def test_c3a02_tolerancias_provisorias_inalteradas_e_validas():
    from ems_v2.audit import validar_tolerancias
    assert validar_tolerancias(TOL) == []
    assert (TOL.potencia_abs_kW, TOL.potencia_rel_escala, TOL.energia_abs_kWh, TOL.energia_rel_capacidade,
            TOL.soc_fracao, TOL.custo_abs_R, TOL.custo_rel, TOL.binario, TOL.vazao_abs_kg_h, TOL.vazao_rel_qmax,
            TOL.massa_abs_kg) == (1e-5, 1e-7, 1e-6, 1e-8, 1e-6, 1e-4, 1e-7, 1e-6, 1e-6, 1e-8, 1e-9)
    assert "tolerancia_invalida" in {c.codigo for c in validar_tolerancias(object())}
