"""Auditor algébrico INDEPENDENTE do perfil 3C-3 (PCC) — sem Pyomo/HiGHS, sem ``ems_v2.reference``.

Composição explícita, sem desativar nada do 3C-1:

1. ``auditar_3c1`` (inalterado) audita o núcleo — renováveis M03-v1.1, serviço/descarte M04, BESS M06–M08, M09–M12,
   M10, PWL M15/M16, KPIs e custos dos termos 3C-1 (com o ``total`` 3C-1);
2. no modo ``conectado`` o resíduo de balanço M02 do 3C-1 (que NÃO conhece o PCC) é SUBSTITUÍDO pelo balanço M02-3C3
   reconstruído AQUI de forma independente (gen + P_imp = carga + P_exp, com a tolerância de potência D07 sobre uma
   escala que inclui os limites do PCC). No modo ``isolado_declarado`` o balanço 3C-1 é mantido E o 3C-3 é acrescentado.
   Nenhuma outra família 3C-1 é filtrada;
3. famílias do PCC: domínio (P >= 0), capacidade contratada × disponibilidade (P_imp <= a P̄_imp, P_exp <= a P̄_exp),
   exclusividade de sentidos (min(P_imp, P_exp) = 0 e, se houver, integralidade/coerência do indicador w), sentido
   proibido, PCC indisponível, intercâmbio em operação isolada;
4. custos: importação (gasto), exportação (crédito, sinal negativo) e total = total 3C-1 + J_imp + J_exp; preços
   recalculados aqui com a MESMA regra declarada (bloco que contém o intervalo) por aritmética inteira de segundos,
   sem usar ``rede.contrato.precos_na_malha`` (que alimenta o MILP): uma conversão errada num dos dois é detectada.

Nunca aceita uma candidata só porque o solver declarou "optimal". Tolerâncias: as MESMAS provisórias D07.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from ..audit import (CandidatoDespacho, RelatorioAuditoria, Residuo, Tolerancias, _Coletor, _tol_custo, _vetor,
                     validar_tolerancias)
from ..compromisso.auditor import RECONSTRUTIVEIS_3C1, auditar_3c1
from ..diagnostics import Constatacao, erro, pendente
from ..timegrid import ler_instante_utc
from .contrato import EntradaRede3C3
from .preflight import preflight_3c3

RECONSTRUTIVEIS_3C3 = {**RECONSTRUTIVEIS_3C1, "importacao_rede": "PCC-J", "exportacao_rede": "PCC-J"}
NAO_MODELADAS_3C3 = ("fluxo_AC", "tensao", "potencia_reativa", "frequencia", "protecao", "transitorios",
                     "termica_alimentadores", "dinamica_conversores", "valor_futuro")


@dataclass(frozen=True)
class CandidatoRede3C3:
    """Candidata 3C-3: candidata do núcleo 3C-1 (``base``) + intercâmbio no PCC + custos reportados de TODOS os termos.

    ``pcc = {"P_imp": N, "P_exp": N}`` (+ ``"w": N`` quando os dois sentidos são permitidos); ``None`` no modo isolado."""
    base: CandidatoDespacho
    pcc: dict[str, tuple[float, ...]] | None
    custos_reportados: dict[str, float] = field(default_factory=dict)


def _seg(texto: str) -> int:
    t, _ = ler_instante_utc(texto, "t")
    return int(t.timestamp())


def _serie_idx(s, ini_s: int, delta_s: int, N: int) -> list[float] | None:
    """Alinhamento INDEPENDENTE (inteiros de segundos): valores da série nos N intervalos a partir de ``ini_s``."""
    if s is None or s.passo_s != delta_s:
        return None
    d = ini_s - _seg(s.inicio_utc)
    if d < 0 or d % delta_s:
        return None
    i0 = d // delta_s
    if i0 + N > len(s.valores):
        return None
    return [float(v) for v in s.valores[i0:i0 + N]]


def _precos_idx(perfil, ini_s: int, delta_s: int, N: int) -> list[float] | None:
    blocos = [(_seg(b.inicio_utc), b.duracao_s, b.valor) for b in perfil.blocos]
    out = []
    for t in range(N):
        a = ini_s + t * delta_s
        z = a + delta_s
        v = next((x for (b0, dur, x) in blocos if b0 <= a and z <= b0 + dur), "ausente")
        if v == "ausente" or v is None:
            return None
        out.append(float(v))
    return out


def auditar_3c3(e: EntradaRede3C3, cand: CandidatoRede3C3, tol: Tolerancias = Tolerancias(),
                compromisso_parcial: dict | None = None) -> RelatorioAuditoria:
    col = _Coletor()
    ct = validar_tolerancias(tol)
    if ct:
        col.constatacoes += ct
        return _fim(col, None, [], {}, {})
    pf = preflight_3c3(e, compromisso_parcial)
    col.constatacoes += pf
    if any(c.severidade in ("erro", "pendente") for c in pf):
        return _fim(col, None, [], {}, {})
    b, m = e.base, e.base.malha
    N, ds = m.N, m.delta_s
    h = ds / 3600.0
    termos1 = tuple(e.compromisso.termos)
    rep = dict(cand.custos_reportados)
    for nome in sorted(rep):
        if nome not in RECONSTRUTIVEIS_3C3:
            col.constatacoes.append(pendente("custo_nao_reconstruivel_3C3", f"custos_reportados[{nome}]",
                                             "Termo de custo sem reconstrução independente."))
    rep1 = {k: v for k, v in rep.items() if k in termos1}
    if "total" in rep and all(t in rep for t in termos1):
        rep1["total"] = math.fsum(rep[t] for t in termos1)
    rel1 = auditar_3c1(e.compromisso, replace(cand.base, custos_reportados=rep1), tol, compromisso_parcial)
    # ------------------------------------------------ reconstrução independente do barramento
    ini_s = _seg(m.inicio_utc)
    L = {str(d.uid): _serie_idx(d.potencia, ini_s, ds, N) for d in b.demandas}
    A = {str(r.uid): _serie_idx(r.potencial, ini_s, ds, N) for r in b.renovaveis}
    gen, carga, completo = [0.0] * N, [0.0] * N, True

    def vec(dic, uid, chave, n=N):
        v = (dic.get(uid) or {}).get(chave) if isinstance(dic, dict) else None
        if v is None or len(v) != n or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
                                           for x in v):
            return None
        return [float(x) for x in v]
    c = cand.base
    for r in b.renovaveis:
        P = vec(c.renovaveis, str(r.uid), "P_R")
        completo &= P is not None
        for t in range(N if P else 0):
            gen[t] += P[t]
    for x in b.baterias:
        Pc, Pd = vec(c.baterias, str(x.uid), "P_c"), vec(c.baterias, str(x.uid), "P_d")
        completo &= Pc is not None and Pd is not None
        for t in range(N if (Pc and Pd) else 0):
            gen[t] += Pd[t] - Pc[t]
    for g in b.geradores:
        p = vec(c.geradores, str(g.uid), "p")
        completo &= p is not None
        for t in range(N if p else 0):
            gen[t] += p[t]
    for d in b.demandas:
        ell = vec(c.demandas, str(d.uid), "ell")
        completo &= ell is not None and L[str(d.uid)] is not None
        for t in range(N if (ell and L[str(d.uid)]) else 0):
            carga[t] += L[str(d.uid)][t] - ell[t]
    if c.descarte is not None and len(c.descarte) == N:
        for t in range(N):
            carga[t] += float(c.descarte[t])
    # ------------------------------------------------ PCC
    p_ = e.pcc
    uid = str(p_.uid)
    custos: dict[str, float] = {}
    kpis: dict[str, dict[str, float]] = {}
    if e.conectado:
        a = _serie_idx(p_.disponibilidade.serie, ini_s, ds, N)
        imax = _serie_idx(p_.limite_importacao, ini_s, ds, N) if e.importa else [0.0] * N
        emax = _serie_idx(p_.limite_exportacao, ini_s, ds, N) if e.exporta else [0.0] * N
        if None in (a, imax, emax):
            col.constatacoes.append(erro("pcc_nao_alinhavel_no_auditor", "pcc", "Séries do PCC não alinhadas à malha."))
            return _fim(col, rel1, [], custos, kpis)
        P_scale = max([1.0] + [sum(L[k][t] for k in L if L[k]) for t in range(N)]
                      + [sum(A[k][t] for k in A if A[k]) for t in range(N)]
                      + [max(float(x.p_carga_max_kW.valor), float(x.p_descarga_max_kW.valor)) for x in b.baterias]
                      + [float(g.p_max_kW.valor) for g in b.geradores] + imax + emax)
        tolP = tol.potencia_abs_kW + tol.potencia_rel_escala * P_scale
        pc = cand.pcc if isinstance(cand.pcc, dict) else {}
        if cand.pcc is None:
            col.constatacoes.append(erro("variavel_candidata_ausente", "pcc", "PCC conectado sem intercâmbio na candidata."))
        Pi = _vetor(pc, "P_imp", N, f"pcc[{uid}].P_imp", col, N + 1)
        Pe = _vetor(pc, "P_exp", N, f"pcc[{uid}].P_exp", col, N + 1)
        w = _vetor(pc, "w", N, f"pcc[{uid}].w", col, N + 1) if (e.importa and e.exporta) else None
        if not (e.importa and e.exporta) and pc.get("w") is not None:
            col.constatacoes.append(erro("indicador_sentido_sem_dois_sentidos", f"pcc[{uid}].w",
                                         "Indicador de sentido informado com um único sentido permitido."))
        if Pi is None or Pe is None:
            return _fim(col, rel1, ["balanco"], custos, kpis)
        for t in range(N):
            col.limite_inferior("pcc_dominio", "PCC1", uid, t, Pi[t], 0.0, "kW", tolP)
            col.limite_inferior("pcc_dominio", "PCC1", uid, t, Pe[t], 0.0, "kW", tolP)
            col.limite_superior("pcc_capacidade", "PCC1", uid, t, Pi[t], a[t] * imax[t], "kW", tolP)
            col.limite_superior("pcc_capacidade", "PCC1", uid, t, Pe[t], a[t] * emax[t], "kW", tolP)
            col.r("pcc_exclusividade", "PCC2", uid, t, min(abs(Pi[t]), abs(Pe[t])), "kW", tolP)
            if w is not None:
                col.r("integralidade", "PCC2", uid, t, min(abs(w[t]), abs(w[t] - 1.0)), "1", tol.binario)
                col.limite_superior("pcc_sentido", "PCC2", uid, t, Pi[t], a[t] * imax[t] * w[t], "kW", tolP)
                col.limite_superior("pcc_sentido", "PCC2", uid, t, Pe[t], a[t] * emax[t] * (1.0 - w[t]), "kW", tolP)
            if not e.importa and Pi[t] > tolP:
                col.constatacoes.append(erro("importacao_proibida", f"pcc[{uid}].P_imp[{t}]", "Sentido proibido."))
            if not e.exporta and Pe[t] > tolP:
                col.constatacoes.append(erro("exportacao_proibida", f"pcc[{uid}].P_exp[{t}]", "Sentido proibido."))
            if a[t] == 0.0 and max(Pi[t], Pe[t]) > tolP:
                col.constatacoes.append(erro("intercambio_com_pcc_indisponivel", f"pcc[{uid}][{t}]", "a = 0."))
            if completo:
                col.r("balanco", "M02-3C3", "barramento", t, gen[t] + Pi[t] - carga[t] - Pe[t], "kW", tolP)
        kpis = {"E_importada_kWh": {uid: h * math.fsum(Pi)}, "E_exportada_kWh": {uid: h * math.fsum(Pe)}}
        ok = True
        if "importacao_rede" in e.economia.termos:
            ci = _precos_idx(e.economia.tarifa_importacao, ini_s, ds, N)
            if ci is None:
                ok = False
            else:
                custos["importacao_rede"] = h * math.fsum(ci[t] * Pi[t] for t in range(N))
        if "exportacao_rede" in e.economia.termos:
            ce = _precos_idx(e.economia.tarifa_exportacao, ini_s, ds, N)
            if ce is None:
                ok = False
            else:
                custos["exportacao_rede"] = -h * math.fsum(ce[t] * Pe[t] for t in range(N))
        if not ok:
            col.constatacoes.append(erro("preco_nao_reconstruivel", "economia", "Preço sem bloco que contenha o intervalo."))
        filtrar = ["balanco"]
    else:
        if cand.pcc is not None and any(abs(float(v)) > tol.potencia_abs_kW for vs in cand.pcc.values() for v in vs):
            col.constatacoes.append(erro("intercambio_em_operacao_isolada", "pcc",
                                         "Operação isolada declarada: nenhum intercâmbio pode existir."))
        filtrar = []
    tot1 = rel1.custos_reconstruidos.get("total")
    if tot1 is not None and all(t in custos for t in e.economia.termos):
        custos["total"] = math.fsum([tot1] + [custos[t] for t in e.economia.termos])
    for nome in ("importacao_rede", "exportacao_rede", "total"):
        if nome not in rep:
            continue
        if nome not in custos:
            col.constatacoes.append(erro("custo_nao_reconstruivel", f"custos_reportados[{nome}]",
                                         "Custo reportado não pode ser conferido."))
            continue
        col.r("custo", RECONSTRUTIVEIS_3C3[nome], nome, None, float(rep[nome]) - custos[nome], "R$",
              _tol_custo(tol, custos[nome]))
    return _fim(col, rel1, filtrar, custos, kpis)


def _fim(col: _Coletor, rel1: RelatorioAuditoria | None, filtrar, custos, kpis) -> RelatorioAuditoria:
    herdados: tuple[Residuo, ...] = ()
    maximos: dict = {}
    consts: list[Constatacao] = []
    verif: set[str] = set(col.verificadas)
    nao_sup: tuple = ()
    c1, k1 = {}, {}
    if rel1 is not None:
        herdados = tuple(r for r in rel1.reprovados if r.familia not in filtrar)
        maximos = {k: v for k, v in rel1.maximos.items() if k not in filtrar}
        consts = list(rel1.constatacoes)
        verif |= set(f for f in rel1.familias_verificadas if f not in filtrar)
        nao_sup = rel1.familias_nao_suportadas
        c1 = {k: v for k, v in rel1.custos_reconstruidos.items() if k != "total"}
        k1 = dict(rel1.kpis_reconstruidos)
    proprios = tuple(r for r in col.residuos if not r.aprovado)
    for r in col.residuos:
        cur = maximos.get(r.familia)
        if cur is None or abs(r.valor) > cur[0]:
            maximos[r.familia] = (abs(r.valor), r.unidade, r.tolerancia)
    todas = []
    seen = set()
    for x in consts + list(col.constatacoes):
        chave = (x.codigo, x.caminho, x.mensagem)
        if chave not in seen:
            seen.add(chave)
            todas.append(x)
    reprov = herdados + proprios
    bloqueia = any(x.severidade in ("erro", "pendente") for x in todas)
    return RelatorioAuditoria(aceito=not reprov and not bloqueia and not nao_sup and rel1 is not None,
                              reprovados=reprov, maximos=maximos, constatacoes=tuple(todas),
                              familias_verificadas=tuple(sorted(verif)), familias_nao_suportadas=tuple(nao_sup),
                              custos_reconstruidos={**c1, **custos}, kpis_reconstruidos={**k1, **kpis},
                              familias_nao_modeladas=tuple(NAO_MODELADAS_3C3))


__all__ = ["CandidatoRede3C3", "NAO_MODELADAS_3C3", "RECONSTRUTIVEIS_3C3", "auditar_3c3"]
