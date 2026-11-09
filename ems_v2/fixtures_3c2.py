"""Fixtures SINTÉTICAS do Piso 3C-2 (MPC recedente) — só biblioteca padrão.

Todos os números são dados de TESTE (procedência ``sintetico``): nenhum representa equipamento, previsão ou medição do
SEEDS2. A "verdade" é uma realização sintética completa ENCAPSULADA na planta algébrica; as tabelas dos provedores são
declaradas SEPARADAMENTE (não são derivadas do objeto da verdade). Microrrede de ensaio:

* demanda crítica ``syn-carga``; FV ``syn-fv`` (potencial antes da disponibilidade, c_curt = 0,2 R$/kWh);
* banco ``syn-bess`` (C = 100 kWh, SOC 0–1, η = 1 declarado para aritmética exata, P̄ = ``pmax_bess``, c_thr = 0,05);
* PEMFC ``syn-fc`` (P 10–40 kW; curva sintética linear (10; 0,7)–(40; 2,2) kg/h; c_H = 10 R$/kg; R = 2 kW/min;
  limites por rampa convencional (S = RΔ = 30 kW >= P_min); T_on = 45 min, T_off = 30 min (Δ = 15 ⇒ U = 3, D = 2);
  C_SU = 2, C_SD = 1 R$/evento; m_SU = 0,05 kg, m_SD = 0,02 kg). Transição INSTANTÂNEA = abstração declarada, não
  validação física da PEMFC.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timedelta

from . import FORMULACAO_3BP
from .contracts import (ClasseDemanda, CurvaPWL, Disponibilidade, EspecBateria, EspecGerador, EstadoBateria,
                        EstadoGerador, PotencialRenovavel, UIDRecurso)
from .fixtures import entrada, par
from .fixtures_3c1 import embrulhar, memoria, unidade
from .mpc import ESQUEMA_MPC
from .mpc.contrato import (CLASSES_FALHA, ConfiguracaoMPC, IdentidadeMissao, PoliticaAceitacao, PoliticaFalhas,
                           PoliticaTerminalMissao)
from .ponte.cenario import Realizacao, SerieRecurso
from .ponte.compromisso import FonteDisponibilidadeExecucao
from .provenance import Procedencia
from .series import SerieTemporal
from .timegrid import MalhaTemporal

INICIO = "2026-01-01T00:00:00+00:00"
DELTA = 15
FONTE_VERDADE = "Verdade sintética do simulador 3C-2 (ems_v2/fixtures_3c2.py) — encapsulada na planta"
FONTE_PREV = "Tabela de previsão sintética declarada (ems_v2/fixtures_3c2.py) — independente da verdade"
FONTE_CANAL = "Canal de observação sintético 3C-2"
CURVA = ((10.0, 0.7), (40.0, 2.2))
DEM, FV, BESS, FC = "syn-carga", "syn-fv", "syn-bess", "syn-fc"
CENARIO = "syn-cenario-3c2"


def proc(caso: str, obs: str = "", fonte: str = "Fixture sintética 3C-2 (ems_v2/fixtures_3c2.py)") -> Procedencia:
    return Procedencia("sintetico", fonte, caso, observacoes=obs)


def h64(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def missao_uid(nome: str) -> str:
    return h64("missao-3c2:" + nome)[:32]


def _t(i: int) -> str:
    return (datetime.fromisoformat(INICIO) + timedelta(minutes=DELTA * i)).isoformat()


def serie(gr: str, vals, caso: str, *, inicio: str = INICIO, emissao: str | None = INICIO, fonte: str | None = None):
    un = {"potencia": "kW", "disponibilidade": "1"}[gr]
    return SerieTemporal(gr, un, "media_intervalo", inicio, DELTA * 60, tuple(float(v) for v in vals),
                         proc(caso, fonte=fonte or "Fixture sintética 3C-2 (ems_v2/fixtures_3c2.py)"),
                         fronteira="barramento_liquido" if gr == "potencia" else None, emissao_utc=emissao)


def modelo(caso: str, K: int, L, pv, *, e0: float = 20.0, pmax_bess: float = 20.0, fc_ligado: bool = True,
           fc_p: float = 20.0, fc_tempo_s: int = 7200, Ton: float = 45.0, Toff: float = 30.0, R: float = 2.0,
           a_fc=None, com_fc: bool = True, eventos: bool = True):
    """Entrada 3C-1 MODELO da missão (parâmetros declarados; séries = perfis declarados em τ_0, substituídos pela
    previsão de cada janela). ``K`` intervalos de 15 min a partir de ``INICIO``."""
    m = MalhaTemporal(INICIO, DELTA, K, K, K, horizonte_previsao_min=DELTA * K)
    dem = ClasseDemanda(UIDRecurso(DEM), "Carga crítica (fixture)", "critica", serie("potencia", L, caso))
    ren = PotencialRenovavel(UIDRecurso(FV), "fv", serie("potencia", pv, caso), "antes_da_disponibilidade",
                             Disponibilidade(serie("disponibilidade", [1] * K, caso)), par(0.2, "R$/kWh", caso))
    bt = EspecBateria(UIDRecurso(BESS), par(100.0, "kWh", caso), par(0.0, "1", caso), par(1.0, "1", caso),
                      par(1.0, "1", caso, "η = 1 declarado (aritmética exata)"), par(1.0, "1", caso),
                      par(pmax_bess, "kW", caso), par(pmax_bess, "kW", caso), "nao_modelada_alpha_1",
                      Disponibilidade(serie("disponibilidade", [1] * K, caso)), custo_throughput=par(0.05, "R$/kWh", caso))
    eb = EstadoBateria(UIDRecurso(BESS), par(e0, "kWh", caso, "estado inicial declarado"))
    gers, ests, uns, mems = [], [], [], []
    termos = ("curtailment_operacional", "throughput_bess")
    if com_fc:
        g = EspecGerador(UIDRecurso(FC), "pemfc", par(10.0, "kW", caso), par(40.0, "kW", caso),
                         Disponibilidade(serie("disponibilidade", a_fc or [1] * K, caso)), "instantanea",
                         CurvaPWL(CURVA, "sintetica_exata", proc(caso)), par(10.0, "R$/kg", caso))
        gers.append(g)
        ests.append(EstadoGerador(UIDRecurso(FC), fc_ligado, par(fc_p if fc_ligado else 0.0, "kW", caso,
                                                                  "estado anterior declarado")))
        uns.append(unidade(UIDRecurso(FC), caso, R=R, Ton=Ton, Toff=Toff, csu=2.0 if eventos else None,
                           csd=1.0 if eventos else None, msu=0.05, msd=0.02))
        mems.append(memoria(UIDRecurso(FC), caso, tempo_s=fc_tempo_s, T_estado_min=Ton if fc_ligado else Toff))
        termos = termos + ("combustivel_h2",)
    b = entrada(caso, m, formulacao=FORMULACAO_3BP, demandas=[dem], renovaveis=[ren], baterias=[bt],
                estados_baterias=[eb], geradores=gers, estados_geradores=ests, termos=termos,
                variante_combustivel="instantanea" if com_fc else None)
    b = replace(b, cenario_uid=CENARIO)
    return embrulhar(b, uns, mems, caso, termos=("eventos",) if (com_fc and eventos) else ())


def verdade(caso: str, L, pv, *, a_fc=None, a_fv=None, com_fc: bool = True) -> Realizacao:
    """Realização sintética COMPLETA (modo offline) — só a planta a conhece."""
    K = len(L)
    s = [SerieRecurso(DEM, "potencia", serie("potencia", L, caso, emissao=None, fonte=FONTE_VERDADE)),
         SerieRecurso(FV, "potencia", serie("potencia", pv, caso, emissao=None, fonte=FONTE_VERDADE)),
         SerieRecurso(FV, "disponibilidade", serie("disponibilidade", a_fv or [1] * K, caso, emissao=None,
                                                   fonte=FONTE_VERDADE)),
         SerieRecurso(BESS, "disponibilidade", serie("disponibilidade", [1] * K, caso, emissao=None,
                                                     fonte=FONTE_VERDADE))]
    if com_fc:
        s.append(SerieRecurso(FC, "disponibilidade", serie("disponibilidade", a_fc or [1] * K, caso, emissao=None,
                                                            fonte=FONTE_VERDADE)))
    return Realizacao(f"syn-verdade-{caso.lower()}", "sintetica", tuple(s), proc(caso, fonte=FONTE_VERDADE))


def tabela(caso: str, L, pv, *, a_fc=None, com_fc: bool = True, emissao: str = INICIO) -> dict:
    """Tabela de previsão DECLARADA (independente do objeto da verdade)."""
    K = len(L)
    t = {(DEM, "potencia"): serie("potencia", L, caso, emissao=emissao, fonte=FONTE_PREV),
         (FV, "potencia"): serie("potencia", pv, caso, emissao=emissao, fonte=FONTE_PREV),
         (FV, "disponibilidade"): serie("disponibilidade", [1] * K, caso, emissao=emissao, fonte=FONTE_PREV),
         (BESS, "disponibilidade"): serie("disponibilidade", [1] * K, caso, emissao=emissao, fonte=FONTE_PREV)}
    if com_fc:
        t[(FC, "disponibilidade")] = serie("disponibilidade", a_fc or [1] * K, caso, emissao=emissao, fonte=FONTE_PREV)
    return t


BASES = {FV: "antes_da_disponibilidade"}


def identidade(nome: str, *, microrrede: str = "syn-microrrede-fixture", cenario: str | None = None) -> IdentidadeMissao:
    return IdentidadeMissao(missao_uid(nome), microrrede, None, 1, h64("config"), h64("inventario"), h64("inventario-ems"),
                            cenario or CENARIO, 1, h64("cenario"))


def politica_falhas(suspender=()) -> PoliticaFalhas:
    return PoliticaFalhas({k: ("suspender" if k in suspender else "interromper") for k in CLASSES_FALHA},
                          "Ensaio sintético: toda falha encerra a missão salvo as declaradas suspensíveis", proc("falhas"))


def aceitacao(aceitar_nao_otimo: bool = False, gap: float | None = None, term=()) -> PoliticaAceitacao:
    return PoliticaAceitacao(aceitar_nao_otimo, gap, tuple(term),
                             "Ensaio sintético: só ótimo (ou não ótimo dentro do gap declarado)", proc("aceitacao"))


def configuracao(nome: str, K: int, N: int, m: int, *, terminal: str = "janela_reduzida",
                 perm_inter: str = "obrigacao_residual_vinculante", perm_final: str = "obrigacao_residual_vinculante",
                 cobertura: float | None = None, rotulo: str = "causal", modo: str = "simulacao_causal_laco_fechado",
                 aceit: PoliticaAceitacao | None = None, falhas: PoliticaFalhas | None = None,
                 revisao: str = "registrar_sem_reconciliar", cenario: str | None = None, H_f: float | None = None
                 ) -> ConfiguracaoMPC:
    m_ = MalhaTemporal(INICIO, DELTA, N, m, K, horizonte_previsao_min=H_f if H_f is not None else DELTA * N)
    pt = PoliticaTerminalMissao(terminal, perm_inter, perm_final, "Ensaio sintético 3C-2: política terminal declarada",
                                proc("terminal"), cobertura)
    return ConfiguracaoMPC(ESQUEMA_MPC, identidade(nome, cenario=cenario), m_, modo, rotulo, pt,
                           aceit or aceitacao(), falhas or politica_falhas(), revisao, proc(nome))


def fontes(com_fc: bool = True) -> dict:
    return {FC: FonteDisponibilidadeExecucao(FC, "observada")} if com_fc else {}


def latencias(com_fc: bool = True, lat: int = 0) -> dict:
    d = {(DEM, "potencia"): lat, (FV, "potencia"): lat, (FV, "disponibilidade"): lat, (BESS, "disponibilidade"): lat}
    if com_fc:
        d[(FC, "disponibilidade")] = lat
    return d


# ------------------------------------------------------------------------------------------------ cenários
L_E2 = [30.0] * 8
PV_PRIOR_E2 = [10.0] * 8
PV_REAL_E2 = [10.0, 10.0] + [25.0] * 6
"""E2/E3: demanda constante 30 kW (prevista = realizada); FV prevista 10 kW (perfil base conservador); FV realizada
sobe para 25 kW a partir do intervalo 2 e assim permanece (degrau sintético). Previsões nunca superam a realização ⇒
consignas P_R sempre exequíveis (o excedente é vertido)."""
L_E5 = [10.0, 10.0, 10.0, 45.0, 10.0, 10.0, 10.0, 10.0]
PV_E5 = [10.0] * 8
"""E5: pico de 45 kW em g = 3 com FV 10 kW e banco limitado a 20 kW ⇒ a PEMFC (OFF há 2 h) DEVE partir em g = 3;
T_on = 45 min (U = 3) obriga ON em g = 3, 4, 5 mesmo sem demanda líquida (o excedente carrega o banco)."""


__all__ = ["BASES", "BESS", "CENARIO", "CURVA", "DELTA", "DEM", "FC", "FONTE_CANAL", "FONTE_PREV", "FONTE_VERDADE", "FV", "INICIO",
           "L_E2", "L_E5", "PV_E5", "PV_PRIOR_E2", "PV_REAL_E2", "aceitacao", "configuracao", "fontes", "h64",
           "identidade", "latencias", "missao_uid", "modelo", "politica_falhas", "proc", "serie", "tabela", "verdade"]
_ = _t
