"""Integridade do TESTEMUNHO auxiliar do MILP (correção C-3B-02) — biblioteca padrão, sem Pyomo.

A auditoria algébrica (``ems_v2.audit``) confere a física do despacho a partir de grandezas físicas (potências,
energia, vazão) e NÃO enxerga as variáveis auxiliares da formulação MILP. Esta camada SEPARADA confere, a partir
dos valores extraídos, que o testemunho auxiliar entregue pelo solver respeita seus domínios e as relações da
formulação 3B-P — sem substituir a auditoria:

* ``z_b`` (M06): finito, inteiro dentro de ``Tolerancias.binario`` e coerente com as potências:
  ``P_c <= a·P̄^c·z`` e ``P_d <= a·P̄^d·(1 − z)``;
* ``δ`` (M14): finito e inteiro; ``Σ_s δ_s = u``; no máximo um segmento ativo;
* ``θ`` (M14): finito, em ``[0, 1]`` e ``θ_s <= δ_s`` (θ não pode viver fora do segmento selecionado);
* (M15/M16): ``p`` e ``q`` reconstruídos de (δ, θ) coincidem com os valores entregues;
* segmento reportado (``segmento_ativo``) coerente com δ.

Tolerâncias: as MESMAS tolerâncias provisórias do auditor (binária adimensional; potência; vazão) — nada é relaxado.
"""
from __future__ import annotations

import math

from ..audit import RelatorioAuditoria, Tolerancias, _Coletor, _finalizar, validar_tolerancias
from ..contracts import EntradaModeloEMS
from ..diagnostics import erro
from ..series import alinhar_a_malha


def _fin(x) -> bool:
    return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x)


def _seq(d: dict, chave: str, n: int, cam: str, col: _Coletor):
    v = d.get(chave) if isinstance(d, dict) else None
    if not isinstance(v, (list, tuple)) or len(v) != n:
        col.constatacoes.append(erro("testemunho_ausente", cam, f"'{chave}' ausente ou com comprimento ≠ {n}."))
        return None
    if not all(_fin(x) for x in v):
        col.constatacoes.append(erro("testemunho_nao_finito", cam, f"'{chave}' com valor ausente/NaN/Inf."))
        return None
    return [float(x) for x in v]


def verificar_testemunho(e: EntradaModeloEMS, despacho: dict, tol: Tolerancias = Tolerancias()) -> RelatorioAuditoria:
    col = _Coletor()
    ct = validar_tolerancias(tol)
    if ct:
        col.constatacoes += ct
        return _finalizar(col, [])
    N = e.malha.N
    tb = tol.binario
    pmax = max([1.0] + [float(b.p_carga_max_kW.valor) for b in e.baterias]
               + [float(b.p_descarga_max_kW.valor) for b in e.baterias] + [float(g.p_max_kW.valor) for g in e.geradores])
    tolP = tol.potencia_abs_kW + tol.potencia_rel_escala * pmax
    bats = (despacho or {}).get("baterias", {}) or {}
    for b in e.baterias:
        k = str(b.uid)
        d = bats.get(k)
        cam = f"testemunho.baterias[{k}]"
        if not isinstance(d, dict):
            col.constatacoes.append(erro("testemunho_ausente", cam, "Banco sem testemunho."))
            continue
        z = _seq(d, "z_b", N, cam + ".z_b", col)
        pc = _seq(d, "P_c", N, cam + ".P_c", col)
        pd = _seq(d, "P_d", N, cam + ".P_d", col)
        if z is None or pc is None or pd is None:
            continue
        a = alinhar_a_malha(b.disponibilidade.serie, e.malha, "")[0]
        pcm, pdm = float(b.p_carga_max_kW.valor), float(b.p_descarga_max_kW.valor)
        for t in range(N):
            col.r("integralidade_z_b", "M06", k, t, min(abs(z[t]), abs(z[t] - 1.0)), "1", tb)
            col.limite_superior("coerencia_z_b", "M06", k, t, pc[t], a[t] * pcm * z[t], "kW", tolP)
            col.limite_superior("coerencia_z_b", "M06", k, t, pd[t], a[t] * pdm * (1.0 - z[t]), "kW", tolP)
    gers = (despacho or {}).get("geradores", {}) or {}
    for g in e.geradores:
        if g.curva_h2 is None:
            continue
        k = str(g.uid)
        cam = f"testemunho.geradores[{k}]"
        d = gers.get(k)
        if not isinstance(d, dict):
            col.constatacoes.append(erro("testemunho_ausente", cam, "Gerador PWL sem testemunho."))
            continue
        V = [(float(P), float(Q)) for P, Q in g.curva_h2.vertices]
        S = len(V) - 1
        u = _seq(d, "u", N, cam + ".u", col)
        p = _seq(d, "p", N, cam + ".p", col)
        q = _seq(d, "q", N, cam + ".q", col)
        delta, theta = d.get("delta"), d.get("theta")
        ok = True
        for nome, mat in (("delta", delta), ("theta", theta)):
            if not isinstance(mat, (list, tuple)) or len(mat) != N or any(
                    not isinstance(r, (list, tuple)) or len(r) != S for r in mat):
                col.constatacoes.append(erro("testemunho_ausente", f"{cam}.{nome}", f"Exigida matriz {N}×{S}."))
                ok = False
            elif not all(_fin(x) for r in mat for x in r):
                col.constatacoes.append(erro("testemunho_nao_finito", f"{cam}.{nome}", "Valor ausente/NaN/Inf."))
                ok = False
        if not ok or u is None or p is None or q is None:
            continue
        tolQ = tol.vazao_abs_kg_h + tol.vazao_rel_qmax * max(Q for _, Q in V)
        rep = d.get("segmento_ativo")
        for t in range(N):
            dl, th = [float(x) for x in delta[t]], [float(x) for x in theta[t]]
            for s in range(S):
                col.r("integralidade_delta", "M14", k, t, min(abs(dl[s]), abs(dl[s] - 1.0)), "1", tb)
                col.limite_inferior("dominio_theta", "M14", k, t, th[s], 0.0, "1", tb)
                col.limite_superior("dominio_theta", "M14", k, t, th[s], 1.0, "1", tb)
                col.limite_superior("theta_no_segmento", "M14", k, t, th[s], dl[s], "1", tb)
            col.r("selecao_segmento", "M14", k, t, sum(dl) - u[t], "1", tb)
            p_rec = sum(V[s][0] * dl[s] + (V[s + 1][0] - V[s][0]) * th[s] for s in range(S))
            q_rec = sum(V[s][1] * dl[s] + (V[s + 1][1] - V[s][1]) * th[s] for s in range(S))
            col.r("reconstrucao_pwl", "M15", k, t, p[t] - p_rec, "kW", tolP)
            col.r("reconstrucao_pwl", "M16", k, t, q[t] - q_rec, "kg/h", tolQ)
            ativos = [s for s in range(S) if dl[s] > 0.5]
            esperado = ativos[0] if len(ativos) == 1 else None
            if isinstance(rep, (list, tuple)) and len(rep) == N and rep[t] != esperado:
                col.constatacoes.append(erro("segmento_reportado_incoerente", f"{cam}.segmento_ativo[{t}]",
                                             f"Reportado {rep[t]!r}; δ indica {esperado!r}."))
            elif not (isinstance(rep, (list, tuple)) and len(rep) == N):
                col.constatacoes.append(erro("testemunho_ausente", f"{cam}.segmento_ativo", "Segmento não reportado."))
                break
    return _finalizar(col, [])


__all__ = ["verificar_testemunho"]
