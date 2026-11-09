"""Utilidades de ENSAIO do Piso 3C-2 (não fazem parte do pacote).

``ResolvedorRegraAnalitica`` é um DUBLÊ DE TESTE sem solver para microrredes SEM gerador (FV + banco + demanda): a cada
intervalo usa toda a FV utilizável até a demanda, descarrega o déficit e carrega o excedente (o vertimento é mais caro
que o throughput nas fixtures), e submete o candidato ao AUDITOR INDEPENDENTE 3C-1 (sem Pyomo). Só se o auditor aprova
o resultado é marcado aceito; o rótulo "otimo" existe apenas para exercitar o fluxo de aceitação do orquestrador — não
é afirmação de otimalidade de solver. Permite provar o laço MPC (relógio, K6, conciliação, registros, retomada) mesmo
sem Pyomo/HiGHS instalados.
"""
from __future__ import annotations

from types import SimpleNamespace

from ems_v2 import FORMULACAO_3C1, MOTOR_ID
from ems_v2.audit import CandidatoDespacho
from ems_v2.compromisso.auditor import auditar_3c1
from ems_v2.compromisso.contrato import hash_entrada_3c1
from ems_v2.series import alinhar_a_malha


class ResolvedorRegraAnalitica:
    natureza = "duble_regra_analitica_auditada"

    def __init__(self, identificador: str = "duble-regra-3c2"):
        self.identificador = identificador
        self.chamadas = 0

    def configuracao_registro(self) -> dict:
        return {"resolvedor": self.identificador, "natureza": self.natureza}

    def resolver(self, e3, compromisso_parcial=None):
        self.chamadas += 1
        b = e3.base
        assert not b.geradores, "dublê só para microrredes sem gerador"
        m, h = b.malha, b.malha.delta_s / 3600.0
        L = alinhar_a_malha(b.demandas[0].potencia, m, "")[0]
        r = b.renovaveis[0]
        A = alinhar_a_malha(r.potencial, m, "")[0]
        a = alinhar_a_malha(r.disponibilidade.serie, m, "")[0]
        bt, eb = b.baterias[0], b.estados_baterias[0]
        e = [float(eb.energia_kWh.valor)]
        C = float(bt.capacidade_kWh.valor)
        pr, pc, pd, cop = [], [], [], []
        for t in range(m.N):
            util = A[t] * a[t]
            if util >= L[t]:
                c = min(float(bt.p_carga_max_kW.valor), util - L[t], (C * float(bt.soc_max.valor) - e[-1]) / h)
                pr.append(L[t] + c), pc.append(c), pd.append(0.0)
            else:
                d = L[t] - util
                pr.append(util), pc.append(0.0), pd.append(d)
            cop.append(util - pr[-1])
            e.append(e[-1] + h * (pc[-1] - pd[-1]))
        cand = CandidatoDespacho(renovaveis={str(r.uid): {"P_R": tuple(pr), "C_oper": tuple(cop)}},
                                 baterias={str(bt.uid): {"P_c": tuple(pc), "P_d": tuple(pd), "e": tuple(e)}},
                                 demandas={str(b.demandas[0].uid): {"ell": (0.0,) * m.N}})
        aud = auditar_3c1(e3, cand)
        custos = dict(aud.custos_reconstruidos)
        custos["total"] = sum(custos.values())
        ok = aud.aceito
        desp = {"renovaveis": cand.renovaveis, "baterias": cand.baterias, "demandas": cand.demandas,
                "descarte": None, "geradores": {}}
        return SimpleNamespace(
            motor_id=MOTOR_ID, versao_formulacao=FORMULACAO_3C1, hash_entrada=hash_entrada_3c1(e3),
            microrrede_uid=b.microrrede_uid, cenario_uid=b.cenario_uid, classificacao="otimo" if ok else "inviavel",
            terminacao="convergenceCriteriaSatisfied" if ok else "provenInfeasible",
            status_solucao="optimal" if ok else "noSolution", objetivo=custos["total"] if ok else None,
            limite_dual=custos["total"] if ok else None, gap_abs=0.0 if ok else None, gap_rel=0.0 if ok else None,
            tamanho={}, garantia_permanencia="completa_na_janela", obrigacoes_residuais_s={}, eventos={},
            auditoria=aud, custos_modelo=custos if ok else {}, tempos_s={"total_s": 0.0}, configuracao={},
            ambiente={}, despacho=desp if ok else None, aceito=ok,
            estado_despacho="aceito_otimo" if ok else "sem_despacho", memoria_terminal=(),
            codigos=lambda: set())
