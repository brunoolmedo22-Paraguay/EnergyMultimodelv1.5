"""Experimentos E1–E8 do Piso 3C-2 sobre as fixtures SINTÉTICAS ``ems_v2.fixtures_3c2``.

Importar este módulo NÃO importa Pyomo/HiGHS; executar um experimento usa o adaptador ``ResolvedorMILP3C1`` (import
tardio de ``resolver_3c1``) e exige ``pip install -r requirements-ems_v2.txt``. Tudo é simulação causal de laço
fechado ALGÉBRICA (planta = dublê 3C-1): nenhum resultado aqui é validação física nem afirma desempenho de tempo real.

* E1 — previsão perfeita DECLARADA (oráculo, ablação): MPC e plano único de horizonte completo como referência;
* E2 — previsão imperfeita reemitida por observação: o controlador adapta-se sem consultar realizações futuras;
* E3 — open-loop (uma decisão, N = m = K_M) × MPC (N = 4, m = 2) com a MESMA informação/planta/regras;
* E4 — frequência de reotimização m ∈ {1, 2, 4} com o mesmo Δ, N e critérios;
* E5 — memória de commitment: T_on cruzando 3 janelas (N = 2, m = 1) e contraprova com memória descartada;
* E6 — banco: continuidade da energia EXECUTADA × terminal PLANEJADO, limites;
* E7 — falhas do solver/auditor: nada é executado sem plano aceito;
* E8 — observações tardias/revisões: decisões passadas inalteradas (modo 1) e pausa/retomada C-02 (modo 2).
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import fixtures_3c2 as F
from ..ponte.compromisso import estado_inicial_3c1
from .adaptador_milp import ResolvedorMILP3C1
from .entorno import CanalObservacao, EntornoSimuladoAlgebrico
from .orquestrador import ControladorMPC, ResultadoMissaoMPC, executar_missao_simulada
from .provedores import ProvedorCorrecaoPorObservacao, ProvedorOraculoAblacao, ProvedorTabelaDeclarada

CASO = "3C2"
PLANTA = "planta-algebrica-3c2"


def config_solver():
    from ..milp.config import CONFIG_ANALITICA
    return CONFIG_ANALITICA


@dataclass
class Execucao:
    resultado: ResultadoMissaoMPC
    modelo: object
    verdade: object
    entorno: EntornoSimuladoAlgebrico
    controlador: ControladorMPC


def provedor(tipo: str, L, pv_prev, *, pv_real=None, a_fc=None, com_fc=True):
    tab = F.tabela(CASO, L, pv_prev, a_fc=a_fc, com_fc=com_fc)
    pr = F.proc("provedor", fonte=F.FONTE_PREV)
    if tipo == "tabela":
        return ProvedorTabelaDeclarada("prov-tabela-3c2", tab, pr, bases=F.BASES)
    if tipo == "correcao":
        return ProvedorCorrecaoPorObservacao("prov-correcao-3c2", tab, pr, corrigidas=[(F.FV, "potencia")],
                                             bases=F.BASES)
    if tipo == "oraculo":
        return ProvedorOraculoAblacao("prov-oraculo-3c2", F.verdade(CASO, L, pv_real, a_fc=a_fc, com_fc=com_fc),
                                      "Ablação E1: previsão perfeita DECLARADA como referência (não causal)",
                                      F.proc("oraculo"), bases=F.BASES)
    raise ValueError(tipo)


def montar(nome: str, *, K: int = 8, N: int = 4, m: int = 2, L=None, pv_prev=None, pv_real=None, tipo="correcao",
           latencia: int = 0, perturbacoes=(), resolvedor=None, cfg_kw=None, modelo_kw=None, a_fc_real=None,
           a_fc_prev=None, diretorio=None, provedor_obj=None, verdade_obj=None
           ) -> tuple[ControladorMPC, EntornoSimuladoAlgebrico, object, object]:
    L = list(L or F.L_E2)
    pv_prev = list(pv_prev or F.PV_PRIOR_E2)
    pv_real = list(pv_real or F.PV_REAL_E2)
    cfg_kw = dict(cfg_kw or {})
    if tipo == "oraculo":
        cfg_kw.setdefault("rotulo", "ablacao_oraculo")
    cfg = F.configuracao(nome, K, N, m, **cfg_kw)
    mkw = dict(modelo_kw or {})
    fc = mkw.get("com_fc", True)
    mod = F.modelo(CASO, K, L, pv_prev, **mkw)
    ver = verdade_obj or F.verdade(CASO, L, pv_real, a_fc=a_fc_real, com_fc=fc)
    prov = provedor_obj or provedor(tipo, L, pv_prev, pv_real=pv_real, a_fc=a_fc_prev, com_fc=fc)
    canal = CanalObservacao(F.FONTE_CANAL, F.latencias(com_fc=fc, lat=latencia), latencia,
                            F.proc("canal", fonte=F.FONTE_CANAL), tuple(perturbacoes))
    ent = EntornoSimuladoAlgebrico(identificador=PLANTA, missao_uid=cfg.identidade.missao_uid, verdade=ver, modelo=mod,
                                   fontes_disponibilidade=F.fontes(fc), estado_inicial=estado_inicial_3c1(mod),
                                   canal=canal, inicio_missao_utc=F.INICIO, delta_s=F.DELTA * 60, intervalos_missao=K)
    ctrl = ControladorMPC(cfg, mod, prov, resolvedor or ResolvedorMILP3C1(config_solver()), F.fontes(fc),
                          identificadores_verdade=(PLANTA,), fontes_verdade=(F.FONTE_VERDADE,), diretorio=diretorio)
    return ctrl, ent, mod, ver


def executar(nome: str, **kw) -> Execucao:
    ctrl, ent, mod, ver = montar(nome, **kw)
    return Execucao(executar_missao_simulada(ctrl, ent), mod, ver, ent, ctrl)


# ---------------------------------------------------------------------------------------- experimentos
def e1_oraculo() -> dict:
    mpc = executar("e1-oraculo-mpc", tipo="oraculo", N=4, m=2)
    ref = executar("e1-oraculo-horizonte-completo", tipo="oraculo", N=8, m=8)
    return {"mpc": mpc, "horizonte_completo": ref}


def e2_previsao_reemitida() -> dict:
    return {"mpc": executar("e2-mpc", tipo="correcao", N=4, m=2)}


def e3_open_loop_vs_mpc() -> dict:
    return {"open_loop": executar("e3-open-loop", tipo="correcao", N=8, m=8),
            "mpc": executar("e3-mpc", tipo="correcao", N=4, m=2)}


def e4_frequencia() -> dict:
    return {m: executar(f"e4-m{m}", tipo="correcao", N=4, m=m) for m in (1, 2, 4)}


def e5_memoria(**kw) -> Execucao:
    return executar("e5-memoria", tipo="tabela", N=2, m=1, L=F.L_E5, pv_prev=F.PV_E5, pv_real=F.PV_E5,
                    modelo_kw={"fc_ligado": False, "fc_p": 0.0, "fc_tempo_s": 7200, "e0": 20.0, "pmax_bess": 20.0},
                    **kw)


class ResolvedorComFalha:
    """Embrulho de ENSAIO (E7): na chamada ``n`` (0-based) devolve o resultado de ``falha(e3)`` em vez de resolver."""
    natureza = "ensaio_falha_injetada"

    def __init__(self, base, n: int, falha):
        self.base, self.n, self.falha, self.identificador = base, n, falha, f"falha-injetada@{n}"
        self.chamadas = 0

    def resolver(self, e3, compromisso_parcial=None):
        i = self.chamadas
        self.chamadas += 1
        return self.falha(e3) if i == self.n else self.base.resolver(e3, compromisso_parcial)

    def configuracao_registro(self) -> dict:
        return {**self.base.configuracao_registro(), "falha_injetada_na_chamada": self.n}


def e7_falha_na_janela(n: int, falha, **kw) -> Execucao:
    base = ResolvedorMILP3C1(config_solver())
    return executar(f"e7-falha-{n}", resolvedor=ResolvedorComFalha(base, n, falha), **kw)


def resultado_sem_solucao(e3):
    """Resultado de ensaio: limite de tempo SEM incumbente (classificação 'sem_solucao')."""
    from types import SimpleNamespace
    return SimpleNamespace(aceito=False, despacho=None, classificacao="sem_solucao", estado_despacho="sem_despacho",
                           terminacao="maxTimeLimit", status_solucao="noSolution", objetivo=None, limite_dual=None,
                           gap_abs=None, gap_rel=None, hash_entrada=None, tamanho={}, garantia_permanencia=None,
                           obrigacoes_residuais_s={}, eventos={}, auditoria=None, custos_modelo={}, tempos_s={},
                           configuracao={}, ambiente={}, codigos=lambda: {"sem_solucao_injetada"})


def e8_revisao_tardia(politica: str, atraso_s: int = 1200) -> Execucao:
    """Revisão do potencial FV do intervalo 1 recebida em τ_2 + ``atraso_s`` − Δ (DEPOIS da decisão em τ_2)."""
    from .entorno import PerturbacaoCanal
    p = PerturbacaoCanal("revisar", F.FV, "potencia", 1, atraso_s=atraso_s, valor=12.0)
    return executar(f"e8-revisao-{politica}", tipo="correcao", N=4, m=2, perturbacoes=(p,),
                    cfg_kw={"revisao": politica})


__all__ = ["CASO", "Execucao", "PLANTA", "ResolvedorComFalha", "config_solver", "e1_oraculo", "e2_previsao_reemitida",
           "e3_open_loop_vs_mpc", "e4_frequencia", "e5_memoria", "e7_falha_na_janela", "e8_revisao_tardia", "executar",
           "montar", "provedor", "resultado_sem_solucao"]
