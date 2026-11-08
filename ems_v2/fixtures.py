"""Fixtures SINTÉTICAS de referência (pacote mestre 3A: ``05_FIXTURES_Y_PUERTAS.md``, ordem executiva §Tests).

Todos os números são dados de teste, NÃO parâmetros físicos de SEEDS2. Os resultados ``esperado`` são os valores
ANALÍTICOS literais dos documentos (não são calculados por ``reference`` nem por ``audit``).

* ``referencia_3A``: verificados agora por cálculo de referência e auditoria algébrica (A01–A04, B01A/B,
  A05-FEAS, A06).
* ``especificacao_3B`` / ``especificacao_3C``: A05-OPT, A07, A08 e B05A — RESULTADO TEÓRICO esperado do futuro
  solver/autômato; ``executado_por_solver = False`` sempre no Piso 3A (condição F da fiscalização).

Parâmetros que um caso não fornece mas o contrato exige (p. ex. η^c em A03, onde só η^d intervém) são DECLARADOS
explicitamente aqui como valores de fixture, com procedência sintética e observação — nunca presumidos pelo código.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import ESQUEMA_VERSAO, FORMULACAO_VERSAO, MOTOR_ID
from .audit import CandidatoDespacho
from .contracts import (CONVENCAO_POTENCIA, ClasseDemanda, CurvaPWL, Disponibilidade, EntradaModeloEMS, EspecBateria,
                        EspecGerador, EstadoBateria, EstadoGerador, FronteiraBarramento, PoliticaObjetivo,
                        PoliticaServico, PoliticaTerminal, PotencialRenovavel, UIDRecurso)
from .parameters import Parametro
from .provenance import Procedencia
from .series import SerieTemporal
from .timegrid import MalhaTemporal

FONTE = "Pacote mestre Piso 3A (2026-11-08) — 05_FIXTURES_Y_PUERTAS.md / 03_ORDEN_EJECUTIVA_3A.md"
INICIO = "2026-01-01T00:00:00+00:00"
ETAPAS = ("referencia_3A", "especificacao_3B", "especificacao_3C")


def proc(caso: str, obs: str = "") -> Procedencia:
    return Procedencia("sintetico", FONTE, caso, observacoes=obs)


def par(v: float, u: str, caso: str, obs: str = "") -> Parametro:
    return Parametro(v, u, proc(caso, obs))


def serie(grandeza: str, unidade: str, valores, delta_min: float, caso: str, fronteira: str | None = None) -> SerieTemporal:
    return SerieTemporal(grandeza, unidade, "media_intervalo", INICIO, int(delta_min * 60), tuple(float(v) for v in valores),
                         proc(caso), fronteira=fronteira, emissao_utc=INICIO)


def pot(valores, delta_min, caso) -> SerieTemporal:
    return serie("potencia", "kW", valores, delta_min, caso, "barramento_liquido")


def disp(valores, delta_min, caso) -> Disponibilidade:
    return Disponibilidade(serie("disponibilidade", "1", valores, delta_min, caso))


def malha(delta_min: float, N: int) -> MalhaTemporal:
    return MalhaTemporal(INICIO, delta_min, N, 1, N, horizonte_previsao_min=delta_min * N)


def demanda(uid: str, valores, delta_min, caso) -> ClasseDemanda:
    return ClasseDemanda(UIDRecurso(uid), "Demanda agregada (fixture)", "critica", pot(valores, delta_min, caso))


def fv(uid: str, A, a, delta_min, caso, c_curt: float | None = None) -> PotencialRenovavel:
    return PotencialRenovavel(UIDRecurso(uid), "fv", pot(A, delta_min, caso), "antes_da_disponibilidade",
                              disp(a, delta_min, caso),
                              None if c_curt is None else par(c_curt, "R$/kWh", caso))


def bateria(uid: str, N: int, delta_min, caso, *, C=100.0, smin=0.0, smax=1.0, eta_c=0.9, eta_d=0.9, pcmax, pdmax,
            c_thr: float | None = None, obs: str = "") -> EspecBateria:
    return EspecBateria(UIDRecurso(uid), par(C, "kWh", caso), par(smin, "1", caso, obs), par(smax, "1", caso, obs),
                        par(eta_c, "1", caso, obs), par(eta_d, "1", caso, obs), par(pcmax, "kW", caso, obs),
                        par(pdmax, "kW", caso, obs), "nao_modelada_alpha_1", disp([1] * N, delta_min, caso),
                        custo_throughput=None if c_thr is None else par(c_thr, "R$/kWh", caso))


def entrada(caso: str, m: MalhaTemporal, *, demandas=(), renovaveis=(), baterias=(), estados_baterias=(),
            geradores=(), estados_geradores=(), termos=()) -> EntradaModeloEMS:
    return EntradaModeloEMS(
        ESQUEMA_VERSAO, MOTOR_ID, FORMULACAO_VERSAO, "syn-microrrede-fixture", f"syn-{caso.lower()}", m,
        FronteiraBarramento("barramento_equivalente_unico", "isolada", CONVENCAO_POTENCIA, proc(caso)),
        tuple(demandas), tuple(renovaveis), tuple(baterias), tuple(estados_baterias), tuple(geradores),
        tuple(estados_geradores),
        PoliticaServico("duro", proc(caso, "Serviço duro (07_DECISIONES_Y_RIESGOS: D01 regra temporária)")),
        PoliticaTerminal("nenhuma", f"Caso analítico {caso}: terminal não vinculante (adenda v1.1 'Temporalidad')",
                         proc(caso)),
        PoliticaObjetivo(tuple(termos), proc(caso)),
        proc(caso, "Entrada sintética para teste algébrico; não é estudo físico."))


@dataclass(frozen=True)
class CasoAnalitico:
    id: str
    etapa: str
    descricao: str
    esperado: dict
    executado_por_solver: bool = False
    dados: dict = field(default_factory=dict)
    observacao: str = ""


# =============================================================================== referência 3A
def a01():
    m = malha(1, 60)
    e = entrada("A01", m, demandas=[demanda("syn-carga", [60] * 60, 1, "A01")],
                renovaveis=[fv("syn-fv", [60] * 60, [1] * 60, 1, "A01")])
    c = CandidatoDespacho(renovaveis={"syn-fv": {"P_R": (60.0,) * 60, "C_oper": (0.0,) * 60}},
                          demandas={"syn-carga": {"ell": (0.0,) * 60}})
    return e, c


def a02():
    m = malha(1, 1)
    e = entrada("A02", m, demandas=[demanda("syn-carga", [10], 1, "A02")],
                renovaveis=[fv("syn-fv", [10], [1], 1, "A02")])
    c = CandidatoDespacho(renovaveis={"syn-fv": {"P_R": (10.0,), "C_oper": (0.0,)}}, demandas={"syn-carga": {"ell": (0.0,)}})
    return e, c


def a03(delta_min: float = 60, N: int = 1):
    obs = "A03: só η^d intervém (P^c = 0); η^c, SOC 0–1 e P̄ declarados como valores da fixture"
    m = malha(delta_min, N)
    b = bateria("syn-bess", N, delta_min, "A03", pcmax=9.0, pdmax=9.0, obs=obs)
    e = entrada("A03", m, demandas=[demanda("syn-carga", [9] * N, delta_min, "A03")], baterias=[b],
                estados_baterias=[EstadoBateria(UIDRecurso("syn-bess"), par(60.0, "kWh", "A03"))])
    traj = tuple(60.0 - 10.0 * t / N for t in range(N + 1))   # analítico: 9/0,9 = 10 kWh retirados em 1 h
    c = CandidatoDespacho(baterias={"syn-bess": {"P_c": (0.0,) * N, "P_d": (9.0,) * N, "e": traj}},
                          demandas={"syn-carga": {"ell": (0.0,) * N}})
    return e, c


def a04():
    obs = "A04: só η^c intervém (P^d = 0); η^d, SOC 0–1 e P̄ declarados como valores da fixture"
    m = malha(60, 1)
    b = bateria("syn-bess", 1, 60, "A04", pcmax=10.0, pdmax=10.0, obs=obs)
    e = entrada("A04", m, demandas=[demanda("syn-carga", [0], 60, "A04")],
                renovaveis=[fv("syn-fv", [10], [1], 60, "A04")], baterias=[b],
                estados_baterias=[EstadoBateria(UIDRecurso("syn-bess"), par(60.0, "kWh", "A04"))])
    c = CandidatoDespacho(renovaveis={"syn-fv": {"P_R": (10.0,), "C_oper": (0.0,)}},
                          baterias={"syn-bess": {"P_c": (10.0,), "P_d": (0.0,), "e": (60.0, 69.0)}},
                          demandas={"syn-carga": {"ell": (0.0,)}})
    return e, c


def b01a():
    m = malha(60, 1)
    e = entrada("B01A", m, demandas=[demanda("syn-carga", [0], 60, "B01A")],
                renovaveis=[fv("syn-fv", [100], [0], 60, "B01A", c_curt=0.5)], termos=("curtailment_operacional",))
    c = CandidatoDespacho(renovaveis={"syn-fv": {"P_R": (0.0,), "C_oper": (0.0,)}}, demandas={"syn-carga": {"ell": (0.0,)}},
                          custos_reportados={"curtailment_operacional": 0.0},
                          kpis_reportados={"E_indisp_kWh": {"syn-fv": 100.0}, "E_curt_oper_kWh": {"syn-fv": 0.0}})
    return e, c


def b01b():
    m = malha(60, 1)
    e = entrada("B01B", m, demandas=[demanda("syn-carga", [80], 60, "B01B")],
                renovaveis=[fv("syn-fv", [100], [1], 60, "B01B", c_curt=0.5)], termos=("curtailment_operacional",))
    c = CandidatoDespacho(renovaveis={"syn-fv": {"P_R": (80.0,), "C_oper": (20.0,)}}, demandas={"syn-carga": {"ell": (0.0,)}},
                          custos_reportados={"curtailment_operacional": 10.0},
                          kpis_reportados={"E_indisp_kWh": {"syn-fv": 0.0}, "E_curt_oper_kWh": {"syn-fv": 20.0}})
    return e, c


def a05_feas():
    obs = "A05-FEAS: e0 = 50 kWh, η^d e P̄^d declarados como valores da fixture (não intervêm)"
    m = malha(60, 1)
    b = bateria("syn-bess", 1, 60, "A05-FEAS", pcmax=10.0, pdmax=10.0, obs=obs)
    e = entrada("A05-FEAS", m, demandas=[demanda("syn-carga", [10], 60, "A05-FEAS")],
                renovaveis=[fv("syn-fv", [20], [1], 60, "A05-FEAS")], baterias=[b],
                estados_baterias=[EstadoBateria(UIDRecurso("syn-bess"), par(50.0, "kWh", "A05-FEAS", obs))])
    carregar = CandidatoDespacho(renovaveis={"syn-fv": {"P_R": (20.0,), "C_oper": (0.0,)}},
                                 baterias={"syn-bess": {"P_c": (10.0,), "P_d": (0.0,), "e": (50.0, 59.0)}},
                                 demandas={"syn-carga": {"ell": (0.0,)}})
    verter = CandidatoDespacho(renovaveis={"syn-fv": {"P_R": (10.0,), "C_oper": (10.0,)}},
                               baterias={"syn-bess": {"P_c": (0.0,), "P_d": (0.0,), "e": (50.0, 50.0)}},
                               demandas={"syn-carga": {"ell": (0.0,)}})
    return e, carregar, verter


def a05_opt_entrada():
    """Mesma física + custos declarados. Validação 3A marca 'throughput_bess' como pendente (termo do Piso 3B)."""
    m = malha(60, 1)
    b = bateria("syn-bess", 1, 60, "A05-OPT", pcmax=10.0, pdmax=10.0, c_thr=0.0,
                obs="A05-OPT: η^d e P̄^d declarados como valores da fixture (descarga não intervém)")
    return entrada("A05-OPT", m, demandas=[demanda("syn-carga", [10], 60, "A05-OPT")],
                   renovaveis=[fv("syn-fv", [20], [1], 60, "A05-OPT", c_curt=1.0)], baterias=[b],
                   estados_baterias=[EstadoBateria(UIDRecurso("syn-bess"), par(50.0, "kWh", "A05-OPT"))],
                   termos=("curtailment_operacional", "throughput_bess"))


def a06_gerador(N: int = 1, delta_min: float = 1) -> tuple[EspecGerador, EstadoGerador, MalhaTemporal]:
    m = malha(delta_min, N)
    g = EspecGerador(UIDRecurso("syn-fc"), "pemfc", par(10.0, "kW", "A06"), par(20.0, "kW", "A06"),
                     disp([1] * N, delta_min, "A06"), "instantanea",
                     CurvaPWL(((10.0, 0.7), (20.0, 1.1)), "sintetica_exata", proc("A06")))
    st = EstadoGerador(UIDRecurso("syn-fc"), True, par(15.0, "kW", "A06", "estado anterior declarado da fixture"))
    return g, st, m


CASOS: dict[str, CasoAnalitico] = {c.id: c for c in (
    CasoAnalitico("A01", "referencia_3A", "60 kW constantes em 60 intervalos de 1 min",
                  {"energia_kWh": "60", "intervalos": 60, "fronteiras": 61}),
    CasoAnalitico("A02", "referencia_3A", "10 kW durante 1 min", {"energia_kWh": "1/6", "intervalos": 1}),
    CasoAnalitico("A03", "referencia_3A", "BESS 100 kWh, e0 = 60, descarga 9 kW, η^d = 0,9, 1 h",
                  {"e1_kWh": "50", "soc1": "1/2"}),
    CasoAnalitico("A04", "referencia_3A", "BESS 100 kWh, e0 = 60, carga 10 kW, η^c = 0,9, 1 h",
                  {"e1_kWh": "69", "soc1": "69/100"}),
    CasoAnalitico("B01A", "referencia_3A", "FV A_pot = 100 kW, a = 0, P = 0, 1 h, c_curt = 0,5",
                  {"C_oper_kW": "0", "E_indisp_kWh": "100", "E_curt_oper_kWh": "0", "custo_R": "0"}),
    CasoAnalitico("B01B", "referencia_3A", "FV A_pot = 100 kW, a = 1, P = 80 kW, 1 h, c_curt = 0,5",
                  {"C_oper_kW": "20", "E_indisp_kWh": "0", "E_curt_oper_kWh": "20", "custo_R": "10"}),
    CasoAnalitico("A05-FEAS", "referencia_3A", "FV 20 kW, carga 10 kW, BESS carrega 10 kW, η^c = 0,9, 1 h",
                  {"residuo_balanco_kW": "0", "delta_e_kWh": "9", "otimalidade": "nao_inferida"},
                  observacao="Factibilidade física; verter 10 kW também é factível — nenhuma otimalidade é afirmada."),
    CasoAnalitico("A06", "referencia_3A", "PWL sintética (10 kW; 0,7 kg/h)–(20 kW; 1,1 kg/h) a 15 kW, 1 min",
                  {"q_kg_h": "9/10", "massa_kg": "3/200", "on_5kW": "invalido", "off": "p = q = 0"},
                  observacao="Referência 3A; a resolução por MILP (segmentos binários M14) é do Piso 3B."),
    CasoAnalitico("A05-OPT", "especificacao_3B", "A05 + c_curt = 1 R$/kWh, c_thr = 0, e0 = 50/100, SOC 0–1, η^c = 0,9",
                  {"P_c_kW": "10", "C_oper_kW": "0", "e1_kWh": "59", "custo_curt_R": "0"},
                  observacao="Resultado TEÓRICO do futuro solver; não executado no Piso 3A."),
    CasoAnalitico("A07", "especificacao_3B", "Gerador forçado ON, P_min = 20 kW, demanda 5 kW, sem BESS nem descarte",
                  {"resultado": "inviavel_servico_duro", "vertimento_ficticio": "proibido"},
                  dados={"p_min_kW": 20, "demanda_kW": 5, "descarte": None},
                  observacao="Resultado TEÓRICO; nenhum solver executado."),
    CasoAnalitico("A08", "especificacao_3B", "Geração útil máx. 5 kW, carga 10 kW, 1 h",
                  {"chi_0": "inviavel", "chi_1_ENS_kWh": "5"}, dados={"p_max_kW": 5, "demanda_kW": 10, "duracao_h": 1},
                  observacao="Resultado TEÓRICO; nenhum solver executado."),
    CasoAnalitico("B05A", "especificacao_3C", "PEMFC em STARTUP, q^mode = 0,02 kg/h por 10 min, sem ON",
                  {"massa_kg": "1/300", "m_SU_adicional": "proibido"}, dados={"q_mode_kg_h": 0.02, "duracao_min": 10},
                  observacao="Variante multimodo (M20): só aritmética de referência; autômato não construído."),
)}

__all__ = ["CASOS", "CasoAnalitico", "ETAPAS", "a01", "a02", "a03", "a04", "a05_feas", "a05_opt_entrada",
           "a06_gerador", "b01a", "b01b", "entrada"]
