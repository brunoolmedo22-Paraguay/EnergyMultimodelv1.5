"""Experimentos do Piso 3C-3 sobre fixtures SINTÉTICAS (``ems_v2.fixtures_3c3``).

Importar este módulo NÃO importa Pyomo/HiGHS; executar usa o adaptador ``ResolvedorMILP3C3`` (import tardio) e exige
``pip install -r requirements-ems_v2.txt``. Simulação causal de laço fechado ALGÉBRICA conectada: nenhum resultado aqui
é validação física, fluxo de potência AC, controle primário de frequência, fatura elétrica real nem desempenho de
tempo real.

* G5 — erro POSITIVO de demanda absorvido pelo ajuste local do PCC (importação realizada > programada);
* G6 — erro NEGATIVO de demanda (importação reduzida; com exportação proibida e excedente ⇒ falha classificada);
* G7 — renovável superestimado: injeção limitada pelo potencial observado; o PCC compensa;
* G8 — saturação do PCC: desbalanço > limite contratado ⇒ consigna inexequível (sem respaldo oculto);
* G11 — MPC conectado de várias janelas: previsões reemitidas, demanda perturbada, revisão tarifária causal,
  ajustes e continuidade de banco/commitment;
* G12 — rede disponível × operação isolada (factibilidade ≠ benefício econômico);
* G13 — interrupção e retomada de uma missão conectada a partir do checkpoint;
* comparação open-loop × MPC com os MESMOS: estado inicial, planta, tarifas, PCC, limites, verdade, liquidação e K_M.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import fixtures_3c2 as F2
from .. import fixtures_3c3 as F
from ..mpc.entorno import CanalObservacao
from ..mpc.orquestrador import executar_missao_simulada
from ..mpc.provedores import ProvedorCorrecaoPorObservacao, ProvedorTabelaDeclarada
from ..ponte.compromisso import estado_inicial_3c1
from .mpc import ControladorMPCConectado, EntornoSimuladoConectado, ResolvedorMILP3C3

PLANTA = "planta-algebrica-3c3"


def config_solver():
    from ..milp.config import CONFIG_ANALITICA
    return CONFIG_ANALITICA


@dataclass
class ExecucaoConectada:
    resultado: object
    modelo: object
    verdade: object
    entorno: EntornoSimuladoConectado
    controlador: ControladorMPCConectado
    politica: object
    configuracao_rede: object


def provedor(tipo: str, L, pv, *, a_pcc=None, com_fc=True, corrigir_demanda=True):
    tab = F.tabela_mpc(L, pv, a_pcc=a_pcc, com_fc=com_fc)
    pr = F2.proc("provedor", fonte=F2.FONTE_PREV)
    if tipo == "tabela":
        return ProvedorTabelaDeclarada("prov-tabela-3c3", tab, pr, bases=F2.BASES)
    corr = [(F2.FV, "potencia")] + ([(F2.DEM, "potencia")] if corrigir_demanda else [])
    return ProvedorCorrecaoPorObservacao("prov-correcao-3c3", tab, pr, corrigidas=corr, bases=F2.BASES)


def montar(nome: str, *, K: int = 8, N: int = 4, m: int = 2, L_prev=None, pv_prev=None, L_real=None, pv_real=None,
           a_pcc_real=None, tipo: str = "correcao", modelo_kw=None, politica=None, tarifas=None, cfg_kw=None,
           latencia: int = 0, perturbacoes=(), diretorio=None, resolvedor=None, corrigir_demanda: bool = True,
           com_fc: bool = True):
    L_prev = list(L_prev or [30.0] * K)
    pv_prev = list(pv_prev or [10.0] * K)
    L_real = list(L_real or L_prev)
    pv_real = list(pv_real or pv_prev)
    mkw = dict(modelo_kw or {})
    mkw.setdefault("com_fc", com_fc)
    mod = F.modelo_mpc(K, L_prev, pv_prev, **mkw)
    con = mod.conectado
    com_exp = mod.exporta and mod.economia.remuneracao_exportacao == "remunerada"
    pol = politica or F.politica_ajuste(K=K, com_exp=com_exp, isolado=not con)
    tar = tarifas if tarifas is not None else (F.tarifas_decisao(K, com_exp=com_exp) if con else ())
    cfg = F2.configuracao(nome, K, N, m, **(cfg_kw or {}))
    crd = F.configuracao_rede(pol, tar)
    ver = F.verdade_mpc(L_real, pv_real, a_pcc=a_pcc_real, com_fc=mkw["com_fc"], com_pcc=con)
    prov = provedor(tipo, L_prev, pv_prev, com_fc=mkw["com_fc"], corrigir_demanda=corrigir_demanda)
    canal = CanalObservacao(F2.FONTE_CANAL, F.latencias_mpc(latencia, com_fc=mkw["com_fc"], conectado=con), latencia,
                            F2.proc("canal", fonte=F2.FONTE_CANAL), tuple(perturbacoes))
    ent = EntornoSimuladoConectado(modelo_rede=mod, politica_ajuste=pol, identificador=PLANTA,
                                   missao_uid=cfg.identidade.missao_uid, verdade=ver,
                                   fontes_disponibilidade=F2.fontes(mkw["com_fc"]),
                                   estado_inicial=estado_inicial_3c1(mod.compromisso), canal=canal,
                                   inicio_missao_utc=F2.INICIO, delta_s=F2.DELTA * 60, intervalos_missao=K)
    ctrl = ControladorMPCConectado(cfg, mod, prov, resolvedor or ResolvedorMILP3C3(config_solver()),
                                   F2.fontes(mkw["com_fc"]), crd, identificadores_verdade=(PLANTA,),
                                   fontes_verdade=(F2.FONTE_VERDADE, F.FONTE_VERDADE), diretorio=diretorio)
    return ctrl, ent, mod, ver, pol, crd


def executar(nome: str, **kw) -> ExecucaoConectada:
    ctrl, ent, mod, ver, pol, crd = montar(nome, **kw)
    return ExecucaoConectada(executar_missao_simulada(ctrl, ent), mod, ver, ent, ctrl, pol, crd)


# ---------------------------------------------------------------------------------------- G5 … G8 (sem PEMFC)
_SIMPLES = dict(K=4, N=2, m=1, com_fc=False, modelo_kw={"e0": 0.0}, tipo="tabela")
"""Missões curtas analíticas: sem PEMFC; banco com e0 = 0 (s_min = 0: não descarrega; carregar da rede sem valor
terminal nunca compensa ⇒ fora do plano); FV prevista 10 kW; demanda prevista 30 kW; c_imp = 0,6 nos 4 intervalos
(revisão 0), c_exp = 0,2. O plano importa 20 kW em cada intervalo; os desvios vêm só da realização."""


def g5_erro_positivo_demanda(**kw) -> ExecucaoConectada:
    """Demanda realizada (30; 34; 30; 30): o PCC importa 24 kW em g = 1 (programado 20). Custo realizado =
    0,25·0,6·(20 + 24 + 20 + 20) = R$ 12,6; planejado dos prefixos = R$ 12,0; desvio +4 kW."""
    return executar("g5-erro-positivo", L_real=[30.0, 34.0, 30.0, 30.0], **{**_SIMPLES, **kw})


def g6_erro_negativo_demanda(sentidos: str = "importacao_e_exportacao", L1: float = 26.0) -> ExecucaoConectada:
    """Demanda realizada (30; L1; 30; 30). L1 = 26: importação reduzida a 16 kW (custo R$ 11,4). L1 = 5 com
    exportação permitida: exporta 5 kW (crédito 0,25·0,2·5 = R$ 0,25 ⇒ custo R$ 8,75); com 'somente_importacao':
    exportação proibida ⇒ ``consigna_inexequivel`` em g = 1 (o FV não é recortado por nenhuma política declarada)."""
    mk = {"e0": 0.0, "sentidos": sentidos}
    if sentidos == "somente_importacao":
        mk["remuneracao"] = "nao_aplicavel"
    return executar(f"g6-erro-negativo-{sentidos}-{L1}", L_real=[30.0, L1, 30.0, 30.0],
                    **{**_SIMPLES, "modelo_kw": mk})


def g7_renovavel_superestimado(**kw) -> ExecucaoConectada:
    """FV realizada (10; 4; 10; 10) com consigna 10: injeção efetiva 4 kW em g = 1 (desvio físico −6 registrado), o PCC
    importa 26 kW. Custo = 0,25·0,6·(20 + 26 + 20 + 20) = R$ 12,9; curtailment 0."""
    return executar("g7-renovavel-superestimado", pv_real=[10.0, 4.0, 10.0, 10.0], **{**_SIMPLES, **kw})


def g8_saturacao_pcc() -> ExecucaoConectada:
    """P̄_imp = 22 kW; demanda realizada 34 kW em g = 1 exigiria 24 kW ⇒ ``pcc_saturado_importacao``: a planta recusa,
    a missão é interrompida (``consigna_inexequivel``) no estado k = 1, sem importação extra, ENS ou alteração do banco."""
    return executar("g8-saturacao", L_real=[30.0, 34.0, 30.0, 30.0], **{**_SIMPLES, "modelo_kw": {"e0": 0.0,
                                                                                              "imp": 22.0}})


# ---------------------------------------------------------------------------------------- G11 … G13 (com PEMFC)
L_G11 = [30.0, 33.0, 27.0, 30.0, 36.0, 30.0, 24.0, 30.0]
PV_REAL_G11 = [10.0, 10.0, 25.0, 25.0, 6.0, 25.0, 25.0, 25.0]


def g11_mpc_conectado(**kw) -> ExecucaoConectada:
    """K = 8, N = 4, m = 2, PEMFC + banco + FV + PCC; demanda e FV perturbadas; previsão reemitida por observação
    (demanda e FV); revisão tarifária r1 emitida em τ_4 (01:00): as decisões em τ_0, τ_2 usam r0 e em τ_4, τ_6 usam r1."""
    return executar("g11-mpc-conectado", L_real=L_G11, pv_real=PV_REAL_G11,
                    tarifas=F.tarifas_decisao(8, revisao_1_em="2026-01-01T01:00:00+00:00"), **kw)


def g12_rede_vs_isolado(L_real=None) -> dict:
    """Mesmo núcleo, mesma verdade (demanda = prevista por padrão): conectado × isolado declarado."""
    kw = dict(L_real=L_real, pv_real=[10.0] * 8, tipo="tabela")
    return {"conectado": executar("g12-conectado", **kw),
            "isolado": executar("g12-isolado", modelo_kw={"modo": "isolado_declarado"}, **kw)}


def comparacao_open_loop_vs_mpc() -> dict:
    """§13: erros reais de previsão de DEMANDA com recurso de equilíbrio declarado (PCC); open-loop (uma decisão,
    N = m = K_M = 8) × MPC (N = 4, m = 2), mesmas condições. Sem veredito: energia final e obrigações reportadas."""
    kw = dict(L_real=L_G11, pv_real=PV_REAL_G11)
    return {"open_loop": executar("cmp-open-loop", N=8, m=8, **kw), "mpc": executar("cmp-mpc", N=4, m=2, **kw)}


__all__ = ["ExecucaoConectada", "L_G11", "PLANTA", "PV_REAL_G11", "comparacao_open_loop_vs_mpc", "config_solver",
           "executar", "g11_mpc_conectado", "g12_rede_vs_isolado", "g5_erro_positivo_demanda",
           "g6_erro_negativo_demanda", "g7_renovavel_superestimado", "g8_saturacao_pcc", "montar", "provedor"]
