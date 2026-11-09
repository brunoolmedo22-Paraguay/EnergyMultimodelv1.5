"""Experimentos do Piso 3C-4 (H1–H17) sobre fixtures SINTÉTICAS (``ems_v2.fixtures_3c4``).

Importar este módulo NÃO importa Pyomo/HiGHS; executar usa os adaptadores (import tardio) e exige
``pip install -r requirements-ems_v2.txt``. Simulação causal de laço fechado ALGÉBRICA: nada aqui é validação física,
fatura real nem desempenho de tempo real.

Estratégias (``ESTRATEGIAS``) com condições IDÊNTICAS (estado inicial, microrrede, verdade, tarifas de liquidação,
PCC, serviço, horizonte de avaliação K_M, regras de custo, aceitação, tratamento terminal Φ_L = declarado):

* ``open_loop``         — uma decisão com N = m = K_M (horizonte completo, sem realimentação), sem sinal;
* ``mpc_sem_sinal``     — MPC 3C-3 (N, m) sem informação terminal (a referência do efeito de ANTECIPAÇÃO);
* ``mpc_encolhido``     — MPC 3C-3 de horizonte completo encolhido (N = K_M, m) — reotimização com informação longa;
* ``hier_pwl``          — hierárquico com custo de continuação PWL (método principal);
* ``hier_local``        — hierárquico com aproximação marginal local;
* ``hier_ref_dura`` / ``hier_ref_branda`` — referências terminais EXPERIMENTAIS;
* ``oraculo``           — PERFEITA (ablação rotulada ``ablacao_oraculo``, N = m = K_M): limite de informação perfeita,
  nunca um controlador causal.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import fixtures_3c2 as F2
from .. import fixtures_3c4 as F
from ..mpc.entorno import CanalObservacao
from ..mpc.orquestrador import executar_missao_simulada
from ..mpc.provedores import ProvedorCorrecaoPorObservacao, ProvedorOraculoAblacao, ProvedorTabelaDeclarada
from ..ponte.compromisso import estado_inicial_3c1
from ..rede.mpc import ControladorMPCConectado, EntornoSimuladoConectado, ResolvedorMILP3C3
from .mpc import ControladorMPCHierarquico, ResolvedorMILP3C4
from .planejador import ResolvedorPlanejador3C4

PLANTA = "planta-algebrica-3c4"
ESTRATEGIAS = ("open_loop", "mpc_sem_sinal", "mpc_encolhido", "hier_pwl", "hier_local", "hier_ref_dura",
               "hier_ref_branda", "oraculo")
TIPO_SINAL = {"hier_pwl": "custo_futuro_pwl", "hier_local": "valor_marginal_local",
              "hier_ref_dura": "referencia_energia_dura", "hier_ref_branda": "referencia_energia_branda"}


def config_solver():
    from ..milp.config import CONFIG_ANALITICA
    return CONFIG_ANALITICA


@dataclass
class ExecucaoHierarquica:
    estrategia: str
    cenario: object
    resultado: object
    controlador: object
    entorno: object
    modelo: object
    N: int
    m: int
    H_L: int | None


def provedor(c, tipo: str = "tabela"):
    pr = F.proc("provedor", fonte=F.FONTE_PREV)
    if tipo == "tabela":
        return ProvedorTabelaDeclarada("prov-tabela-3c4", F.tabela(c), pr, bases=F.BASES)
    if tipo == "correcao":
        return ProvedorCorrecaoPorObservacao("prov-correcao-3c4", F.tabela(c), pr, corrigidas=[(F.DEM, "potencia")],
                                             bases=F.BASES)
    if tipo == "oraculo":
        return ProvedorOraculoAblacao("prov-oraculo-3c4", F.verdade(c), "Ablação 3C-4: informação PERFEITA declarada "
                                      "(lê a realização completa) — limite, não controlador causal", F.proc("oraculo"),
                                      bases=F.BASES)
    raise ValueError(tipo)


def montar(c, estrategia: str, *, N: int = 3, m: int = 1, H_L: int = 10, nome: str | None = None, prov: str = "tabela",
           planejador_kw: dict | None = None, diretorio=None, resolvedor=None, planejador_resolvedor=None,
           latencia: int = 0, perturbacoes=()):
    if estrategia not in ESTRATEGIAS:
        raise ValueError(estrategia)
    K = c.K
    rot = "ablacao_oraculo" if estrategia == "oraculo" else "causal"
    if estrategia in ("open_loop", "oraculo"):
        N_, m_ = K, K
    elif estrategia == "mpc_encolhido":
        N_, m_ = K, m
    else:
        N_, m_ = N, m
    nome = nome or f"{c.nome}-{estrategia}-N{N_}-m{m_}" + (f"-HL{H_L}" if estrategia.startswith("hier") else "")
    mod = F.modelo(c, rotulo=rot)
    cfg = F.configuracao_mpc(nome, c, N_, m_, rotulo=rot)
    crd = F.configuracao_rede(c)
    pol = crd.politica_ajuste
    ver = F.verdade(c)
    pv = provedor(c, "oraculo" if estrategia == "oraculo" else prov)
    canal = CanalObservacao(F.FONTE_CANAL, F.latencias(c, latencia), latencia, F.proc("canal", fonte=F.FONTE_CANAL),
                            tuple(perturbacoes))
    ent = EntornoSimuladoConectado(modelo_rede=mod, politica_ajuste=pol, identificador=PLANTA,
                                   missao_uid=cfg.identidade.missao_uid, verdade=ver, fontes_disponibilidade=F.fontes(c),
                                   estado_inicial=estado_inicial_3c1(mod.compromisso), canal=canal,
                                   inicio_missao_utc=F.INICIO, delta_s=F.DELTA * 60, intervalos_missao=K)
    kw = dict(identificadores_verdade=(PLANTA,), fontes_verdade=(F.FONTE_VERDADE,), diretorio=diretorio)
    if estrategia.startswith("hier"):
        pk = dict(planejador_kw or {})
        pk.setdefault("tipo_sinal", TIPO_SINAL[estrategia])
        if pk["tipo_sinal"] == "valor_marginal_local":
            pk.setdefault("delta", 2.0)
        if pk["tipo_sinal"] == "referencia_energia_branda":
            pk.setdefault("rho", 1.0)
        cp = F.configuracao_planejador(H_L=H_L, **pk)
        ctrl = ControladorMPCHierarquico(cfg, mod, pv, resolvedor or ResolvedorMILP3C4(config_solver()), F.fontes(c),
                                         crd, cp, planejador_resolvedor or ResolvedorPlanejador3C4(config_solver()), **kw)
    else:
        ctrl = ControladorMPCConectado(cfg, mod, pv, resolvedor or ResolvedorMILP3C3(config_solver()), F.fontes(c), crd,
                                       **kw)
    return ctrl, ent, mod, N_, m_


def executar(c, estrategia: str, **kw) -> ExecucaoHierarquica:
    ctrl, ent, mod, N_, m_ = montar(c, estrategia, **kw)
    res = executar_missao_simulada(ctrl, ent)
    return ExecucaoHierarquica(estrategia, c, res, ctrl, ent, mod, N_, m_,
                               kw.get("H_L", 10) if estrategia.startswith("hier") else None)


def executar_varias(c, estrategias=ESTRATEGIAS, **kw) -> dict:
    return {e: executar(c, e, **kw) for e in estrategias}


__all__ = ["ESTRATEGIAS", "ExecucaoHierarquica", "PLANTA", "TIPO_SINAL", "config_solver", "executar",
           "executar_varias", "montar", "provedor"]
_ = F2
