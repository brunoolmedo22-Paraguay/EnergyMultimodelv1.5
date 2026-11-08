"""Fixtures SINTÉTICAS do Piso 3B-P (formulação ``v1.1-3B-P``) — só biblioteca padrão.

Todos os coeficientes econômicos e físicos são DECLARADOS aqui, caso a caso, com procedência sintética; o motor não
tem valores padrão. Resultados esperados são analíticos (comentados em cada caso) ou obtidos por enumeração
independente nos testes — nunca pelo próprio Pyomo.

Cada função devolve ``(entrada, compromisso_fixo)``; o compromisso é o programa u por gerador (constante e igual
ao estado inicial, exigência do perfil 3B-P).
"""
from __future__ import annotations

from . import FORMULACAO_3BP
from .contracts import (ClasseDemanda, CurvaPWL, EspecGerador, EstadoBateria, EstadoGerador, PoliticaServico,
                        UIDRecurso)
from .fixtures import bateria, demanda, disp, entrada, fv, malha, par, pot, proc, serie

F3 = FORMULACAO_3BP


def _e(caso, m, **kw):
    return entrada(caso, m, formulacao=F3, **kw)


def _estado_bat(uid, e0, caso):
    return EstadoBateria(UIDRecurso(uid), par(e0, "kWh", caso))


def gerador(uid, tecnologia, pmin, pmax, N, delta, caso, *, curva=None, preco_h2=None, ligado=True, p_ant=None):
    g = EspecGerador(UIDRecurso(uid), tecnologia, par(pmin, "kW", caso), par(pmax, "kW", caso),
                     disp([1] * N, delta, caso), "instantanea",
                     None if curva is None else CurvaPWL(tuple(curva), "sintetica_exata", proc(caso)),
                     None if preco_h2 is None else par(preco_h2, "R$/kg", caso))
    p0 = (pmin if p_ant is None else p_ant) if ligado else 0.0
    st = EstadoGerador(UIDRecurso(uid), ligado, par(p0, "kW", caso, "estado anterior declarado da fixture"))
    return g, st


# ------------------------------------------------------------------------- A01–A04, B01
def a01(N=60):
    m = malha(1, N)
    return _e("A01-3B", m, demandas=[demanda("syn-carga", [60] * N, 1, "A01-3B")],
              renovaveis=[fv("syn-fv", [60] * N, [1] * N, 1, "A01-3B")]), {}


def a02():
    m = malha(1, 1)
    return _e("A02-3B", m, demandas=[demanda("syn-carga", [10], 1, "A02-3B")],
              renovaveis=[fv("syn-fv", [10], [1], 1, "A02-3B")]), {}


def a03(delta=60, N=1):
    """Só a bateria atende 9 kW: P_d = 9 forçado pelo balanço e pela exclusividade ⇒ e_N = 60 − 9/0,9 = 50 kWh."""
    m = malha(delta, N)
    b = bateria("syn-bess", N, delta, "A03-3B", pcmax=9.0, pdmax=9.0,
                obs="η^c, SOC 0–1 e P̄ declarados na fixture (P^c = 0 por exclusividade)")
    return _e("A03-3B", m, demandas=[demanda("syn-carga", [9] * N, delta, "A03-3B")], baterias=[b],
              estados_baterias=[_estado_bat("syn-bess", 60.0, "A03-3B")]), {}


def a04():
    """FV 10 kW, demanda 0, c_curt = 1 R$/kWh DECLARADO (sem ele a carga não seria única): ótimo P_c = 10,
    e_1 = 60 + 0,9·10 = 69 kWh, custo 0."""
    m = malha(60, 1)
    b = bateria("syn-bess", 1, 60, "A04-3B", pcmax=10.0, pdmax=10.0, obs="η^d e P̄^d declarados na fixture")
    return _e("A04-3B", m, demandas=[demanda("syn-carga", [0], 60, "A04-3B")],
              renovaveis=[fv("syn-fv", [10], [1], 60, "A04-3B", c_curt=1.0)], baterias=[b],
              estados_baterias=[_estado_bat("syn-bess", 60.0, "A04-3B")], termos=("curtailment_operacional",)), {}


def b01a():
    m = malha(60, 1)
    return _e("B01A-3B", m, demandas=[demanda("syn-carga", [0], 60, "B01A-3B")],
              renovaveis=[fv("syn-fv", [100], [0], 60, "B01A-3B", c_curt=0.5)], termos=("curtailment_operacional",)), {}


def b01b():
    m = malha(60, 1)
    return _e("B01B-3B", m, demandas=[demanda("syn-carga", [80], 60, "B01B-3B")],
              renovaveis=[fv("syn-fv", [100], [1], 60, "B01B-3B", c_curt=0.5)], termos=("curtailment_operacional",)), {}


# ------------------------------------------------------------------------- A05
def a05_feas():
    """Sem termo no objetivo (problema de factibilidade declarado): carregar 10 kW e verter 10 kW são ambos
    factíveis — o balanço não determina o despacho (adenda B02)."""
    m = malha(60, 1)
    b = bateria("syn-bess", 1, 60, "A05-FEAS-3B", pcmax=10.0, pdmax=10.0, obs="η^d e P̄^d declarados na fixture")
    return _e("A05-FEAS-3B", m, demandas=[demanda("syn-carga", [10], 60, "A05-FEAS-3B")],
              renovaveis=[fv("syn-fv", [20], [1], 60, "A05-FEAS-3B")], baterias=[b],
              estados_baterias=[_estado_bat("syn-bess", 50.0, "A05-FEAS-3B")]), {}


def a05_opt():
    """A05-OPT (adenda B02): c_curt = 1 R$/kWh, c_thr = 0, e0 = 50/100, SOC 0–1, η^c = 0,9, terminal 'nenhuma'.
    Ótimo esperado: P_c = 10 kW, C_oper = 0, e_1 = 59 kWh, custo de curtailment R$ 0."""
    m = malha(60, 1)
    b = bateria("syn-bess", 1, 60, "A05-OPT-3B", pcmax=10.0, pdmax=10.0, c_thr=0.0,
                obs="η^d e P̄^d declarados na fixture (descarga não intervém)")
    return _e("A05-OPT-3B", m, demandas=[demanda("syn-carga", [10], 60, "A05-OPT-3B")],
              renovaveis=[fv("syn-fv", [20], [1], 60, "A05-OPT-3B", c_curt=1.0)], baterias=[b],
              estados_baterias=[_estado_bat("syn-bess", 50.0, "A05-OPT-3B")],
              termos=("curtailment_operacional", "throughput_bess")), {}


# ------------------------------------------------------------------------- A06 (PWL sintética)
CURVA_A06 = ((10.0, 0.7), (20.0, 1.1))
CURVA_NAO_CONVEXA = ((10.0, 0.50), (14.0, 1.00), (16.0, 1.05), (20.0, 1.60))   # inclinações 0,125 / 0,025 / 0,1375


def a06(carga=15.0, curva=CURVA_A06, preco_h2=None, delta=1, N=1, ligado=True, p_ant=None):
    """PEMFC ON (programa fixo) como única fonte: p = carga ⇒ q = curva(p). A06: 15 kW → 0,9 kg/h; 0,015 kg/1 min."""
    m = malha(delta, N)
    caso = "A06-3B"
    pcur = [P for P, _ in curva]
    g, st = gerador("syn-fc", "pemfc", pcur[0], pcur[-1], N, delta, caso, curva=curva, preco_h2=preco_h2,
                    ligado=ligado, p_ant=(carga if p_ant is None else p_ant) if ligado else None)
    termos = ("combustivel_h2",) if preco_h2 is not None else ()
    e = _e(caso, m, demandas=[demanda("syn-carga", [carga] * N, delta, caso)], geradores=[g], estados_geradores=[st],
           termos=termos, variante_combustivel="instantanea" if preco_h2 is not None else None)
    return e, {"syn-fc": tuple([int(ligado)] * N)}


def pwl_com_bateria(carga=18.0, c_h2=10.0, c_thr=1.0, pdmax=6.0):
    """Enumeração independente: p ∈ [carga − P̄^d, 20] ∩ domínio; custo(p) = h[c_H q(p) + c_thr (carga − p)] é
    linear por partes ⇒ o mínimo está em um ponto de quebra. Com os valores padrão da fixture o ótimo é o vértice
    interno p = 16 kW (q = 1,05 kg/h; P_d = 2 kW; custo R$ 12,5) — uma formulação de envoltória convexa erraria."""
    m = malha(60, 1)
    caso = "PWL-NC-3B"
    g, st = gerador("syn-fc", "pemfc", 10.0, 20.0, 1, 60, caso, curva=CURVA_NAO_CONVEXA, preco_h2=c_h2, p_ant=16.0)
    b = bateria("syn-bess", 1, 60, caso, pcmax=pdmax, pdmax=pdmax, c_thr=c_thr)
    e = _e(caso, m, demandas=[demanda("syn-carga", [carga], 60, caso)], geradores=[g], estados_geradores=[st],
           baterias=[b], estados_baterias=[_estado_bat("syn-bess", 50.0, caso)],
           termos=("combustivel_h2", "throughput_bess"), variante_combustivel="instantanea")
    return e, {"syn-fc": (1,)}


# ------------------------------------------------------------------------- A07, A08
def a07():
    """Gerador forçado ON com P_min = 20 kW, demanda 5 kW, sem BESS nem descarte ⇒ inviável (sem sumidouro)."""
    m = malha(60, 1)
    g, st = gerador("syn-ger", "termica", 20.0, 50.0, 1, 60, "A07-3B", p_ant=20.0)
    return _e("A07-3B", m, demandas=[demanda("syn-carga", [5], 60, "A07-3B")], geradores=[g],
              estados_geradores=[st]), {"syn-ger": (1,)}


def a08(degradado: bool, V=2.0):
    """Geração máx. 5 kW, demanda 10 kW, 1 h. Duro ⇒ inviável. Degradado (classe interrompível, χ = 1, autorização
    declarada) com critério EXPLÍCITO de mínima ENS: termo 'energia_nao_suprida' com V = 2 R$/kWh declarado ⇒
    ℓ = 5 kW, ENS = 5 kWh, custo R$ 10."""
    m = malha(60, 1)
    caso = "A08-3B-" + ("degradado" if degradado else "duro")
    g, st = gerador("syn-ger", "termica", 0.0, 5.0, 1, 60, caso, p_ant=5.0)
    if degradado:
        d = ClasseDemanda(UIDRecurso("syn-carga"), "Carga interrompível (fixture)", "interrompivel",
                          pot([10], 60, caso), serie("fracao_interrompivel", "1", [1.0], 60, caso),
                          par(V, "R$/kWh", caso))
        serv = PoliticaServico("degradado", proc(caso), "Autorização sintética de interrupção total (fixture A08)")
        return _e(caso, m, demandas=[d], geradores=[g], estados_geradores=[st], servico=serv,
                  termos=("energia_nao_suprida",)), {"syn-ger": (1,)}
    return _e(caso, m, demandas=[demanda("syn-carga", [10], 60, caso)], geradores=[g],
              estados_geradores=[st]), {"syn-ger": (1,)}


# ------------------------------------------------------------------------- casos de integridade
def duas_baterias():
    """Dois bancos heterogêneos (UIDs, C, η, e0 e c_thr distintos). FV 15 kW excedente, demanda 0, c_curt = 1.
    Analítico: banco 2 (c_thr 0,05) até encher: P_c2 = (100 − 95)/0,8 = 6,25 kW; banco 1 (c_thr 0,1) absorve o
    resto: P_c1 = 8,75 kW; C_oper = 0; e1 = (57,875; 100); custo = 0,1·8,75 + 0,05·6,25 = R$ 1,1875."""
    m = malha(60, 1)
    c = "2BESS-3B"
    b1 = bateria("syn-bess-a", 1, 60, c, C=100.0, eta_c=0.9, eta_d=0.9, pcmax=10.0, pdmax=10.0, c_thr=0.1)
    b2 = bateria("syn-bess-b", 1, 60, c, C=100.0, eta_c=0.8, eta_d=0.85, pcmax=10.0, pdmax=10.0, c_thr=0.05)
    return _e(c, m, demandas=[demanda("syn-carga", [0], 60, c)],
              renovaveis=[fv("syn-fv", [15], [1], 60, c, c_curt=1.0)], baterias=[b1, b2],
              estados_baterias=[_estado_bat("syn-bess-a", 50.0, c), _estado_bat("syn-bess-b", 95.0, c)],
              termos=("curtailment_operacional", "throughput_bess")), {}


def exclusividade():
    """FV 20 kW, demanda 0, banco quase cheio (e0 = 99/100, η = 0,9), c_curt = 1, c_thr = 0. COM exclusividade:
    P_c = 1/0,9 kW, C_oper = 20 − 1/0,9 kW, custo = 18,888… R$. Ciclar carga e descarga simultâneas 'absorveria'
    mais excedente (custo 17,2) — a formulação MILP deve impedi-lo."""
    m = malha(60, 1)
    c = "EXCL-3B"
    b = bateria("syn-bess", 1, 60, c, pcmax=10.0, pdmax=10.0, c_thr=0.0)
    return _e(c, m, demandas=[demanda("syn-carga", [0], 60, c)],
              renovaveis=[fv("syn-fv", [20], [1], 60, c, c_curt=1.0)], baterias=[b],
              estados_baterias=[_estado_bat("syn-bess", 99.0, c)], termos=("curtailment_operacional", "throughput_bess")), {}


def multi_uid(N=3):
    """Vários UIDs: 2 FV, 2 classes críticas, 2 bancos, 1 PEMFC ON (curva A06) e 1 térmica OFF; Δ = 15 min."""
    c = "MULTI-3B"
    d = 15
    m = malha(d, N)
    b1 = bateria("syn-bess-a", N, d, c, C=50.0, eta_c=0.95, eta_d=0.95, pcmax=20.0, pdmax=20.0, c_thr=0.02)
    b2 = bateria("syn-bess-b", N, d, c, C=80.0, eta_c=0.9, eta_d=0.92, pcmax=15.0, pdmax=15.0, c_thr=0.03)
    fc, sfc = gerador("syn-fc", "pemfc", 10.0, 20.0, N, d, c, curva=CURVA_A06, preco_h2=8.0, p_ant=12.0)
    th, sth = gerador("syn-ter", "termica", 5.0, 30.0, N, d, c, ligado=False)
    e = _e(c, m, demandas=[demanda("syn-carga-a", [20, 25, 30][:N], d, c), demanda("syn-carga-b", [10, 5, 15][:N], d, c)],
           renovaveis=[fv("syn-fv-a", [12, 18, 6][:N], [1] * N, d, c, c_curt=0.3),
                       fv("syn-fv-b", [8, 0, 20][:N], [1, 0, 1][:N], d, c, c_curt=0.4)],
           baterias=[b1, b2], estados_baterias=[_estado_bat("syn-bess-a", 25.0, c), _estado_bat("syn-bess-b", 40.0, c)],
           geradores=[fc, th], estados_geradores=[sfc, sth],
           termos=("curtailment_operacional", "throughput_bess", "combustivel_h2"), variante_combustivel="instantanea")
    return e, {"syn-fc": (1,) * N, "syn-ter": (0,) * N}


def instancia_maior(N=16):
    """Instância sintética maior (3 PEMFC com curvas não convexas ON fixo, 3 bancos, FV e demanda senoidais; Δ = 15
    min) para exercitar terminações INCOMPLETAS reais (``mip_max_improving_sols = 1`` ⇒ incumbente não ótimo).
    Nenhum valor representa equipamento real."""
    import math
    c = "MAIOR-3B"
    d = 15
    m = malha(d, N)
    curvas = [CURVA_NAO_CONVEXA, ((5.0, 0.3), (9.0, 0.9), (12.0, 0.95), (15.0, 1.5)),
              ((8.0, 0.4), (11.0, 0.5), (13.0, 1.1), (18.0, 1.2))]
    gs, sts = [], []
    for i, cv in enumerate(curvas):
        g, st = gerador(f"syn-fc{i}", "pemfc", cv[0][0], cv[-1][0], N, d, c, curva=cv, preco_h2=9.0 + i, p_ant=cv[1][0])
        gs.append(g)
        sts.append(st)
    bs = [bateria(f"syn-b{i}", N, d, c, C=40.0 + 20 * i, eta_c=0.9 - 0.03 * i, eta_d=0.92, pcmax=15.0, pdmax=15.0,
                  c_thr=0.02 * (i + 1)) for i in range(3)]
    est = [_estado_bat(f"syn-b{i}", 20.0 + 5 * i, c) for i in range(3)]
    L = [45 + 12 * math.sin(t / 3.0) + 6 * math.cos(t / 1.7) for t in range(N)]
    A = [max(0.0, 20 * math.sin(t / 7.0)) for t in range(N)]
    e = _e(c, m, demandas=[demanda("syn-carga", L, d, c)], renovaveis=[fv("syn-fv", A, [1] * N, d, c, c_curt=0.2)],
           baterias=bs, estados_baterias=est, geradores=gs, estados_geradores=sts,
           termos=("curtailment_operacional", "throughput_bess", "combustivel_h2"), variante_combustivel="instantanea")
    return e, {f"syn-fc{i}": (1,) * N for i in range(3)}


__all__ = ["CURVA_A06", "CURVA_NAO_CONVEXA", "a01", "a02", "a03", "a04", "a05_feas", "a05_opt", "a06", "a07", "a08",
           "b01a", "b01b", "duas_baterias", "exclusividade", "gerador", "instancia_maior", "multi_uid",
           "pwl_com_bateria"]
