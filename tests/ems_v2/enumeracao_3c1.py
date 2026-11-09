"""Enumeração EXAUSTIVA independente (Caso H do 3C-1) — sem Pyomo, sem HiGHS, sem o auditor nem o construtor MILP.

Para cada programa binário ``u`` (2^(|G|·N) programas) deriva y/z, aplica as regras de commitment escritas AQUI a
partir dos parâmetros brutos da entrada (disponibilidade, transições representáveis, permanências por corridas,
obrigação herdada, política terminal) e resolve o subproblema contínuo por um SIMPLEX RACIONAL EXATO (``Fraction``,
duas fases, regra de Bland). Escopo: geradores térmicos/PEMFC (curva PWL de UM segmento), renováveis com
curtailment, demandas críticas em serviço duro, sem baterias — exatamente a estrutura do ``fixtures_3c1.caso_h``.
"""
from __future__ import annotations

import itertools
from fractions import Fraction as Fr

from ems_v2.series import alinhar_a_malha


def _F(x) -> Fr:
    return Fr(repr(float(x))) if not isinstance(x, int) else Fr(x)


def simplex(c, A_eq, b_eq, A_ub, b_ub):
    """min cᵀx s.a. A_eq x = b_eq, A_ub x <= b_ub, x >= 0 (Fractions). Devolve (valor, x) ou None se inviável."""
    n = len(c)
    rows, rhs = [], []
    for a, b in zip(A_ub, b_ub):
        rows.append(list(a)), rhs.append(b)
    n_s = len(rows)
    for a, b in zip(A_eq, b_eq):
        rows.append(list(a)), rhs.append(b)
    m = len(rows)
    nv = n + n_s + m                                    # x, folgas, artificiais
    T = []
    for i in range(m):
        r = rows[i] + [Fr(1) if (i < n_s and j == i) else Fr(0) for j in range(n_s)] + [Fr(0)] * m
        b = rhs[i]
        if b < 0:
            r, b = [-v for v in r], -b
        r[n + n_s + i] = Fr(1)
        T.append(r + [b])
    base = [n + n_s + i for i in range(m)]

    def pivot(i, j):
        pv = T[i][j]
        T[i] = [v / pv for v in T[i]]
        for k in range(m):
            if k != i and T[k][j] != 0:
                f = T[k][j]
                T[k] = [a - f * b for a, b in zip(T[k], T[i])]
        base[i] = j

    def otimizar(custo, permitidas):
        while True:
            cb = [custo[base[i]] for i in range(m)]
            red = [custo[j] - sum(cb[i] * T[i][j] for i in range(m)) for j in range(nv)]
            ent = next((j for j in range(nv) if j in permitidas and red[j] < 0), None)
            if ent is None:
                return
            cand = [(T[i][-1] / T[i][ent], base[i], i) for i in range(m) if T[i][ent] > 0]
            if not cand:
                raise ValueError("ilimitado")
            _, _, i = min(cand)
            pivot(i, ent)
    fase1 = [Fr(0)] * (n + n_s) + [Fr(1)] * m
    otimizar(fase1, set(range(nv)))
    if sum(T[i][-1] for i in range(m) if base[i] >= n + n_s) != 0:
        return None
    for i in range(m):                                   # retira artificiais degeneradas da base
        if base[i] >= n + n_s:
            j = next((j for j in range(n + n_s) if T[i][j] != 0), None)
            if j is not None:
                pivot(i, j)
    custo = list(c) + [Fr(0)] * (n_s + m)
    otimizar(custo, set(range(n + n_s)))
    x = [Fr(0)] * nv
    for i in range(m):
        x[base[i]] = T[i][-1]
    return sum(c[j] * x[j] for j in range(n)), x[:n]


def _ceil(x: Fr) -> int:
    return -((-x.numerator) // x.denominator)


def enumerar(e3):
    b = e3.base
    m = b.malha
    N, ds = m.N, m.delta_s
    h = Fr(ds, 3600)
    dmin = Fr(ds, 60)
    G = [str(g.uid) for g in b.geradores]
    gesp = {str(g.uid): g for g in b.geradores}
    est = {str(s.uid): s for s in b.estados_geradores}
    a = {k: [_F(v) for v in alinhar_a_malha(gesp[k].disponibilidade.serie, m, "")[0]] for k in G}
    L = [sum(_F(alinhar_a_malha(d.potencia, m, "")[0][t]) for d in b.demandas) for t in range(N)]
    R = [(str(r.uid), [_F(v) for v in alinhar_a_malha(r.potencial, m, "")[0]],
          [_F(v) for v in alinhar_a_malha(r.disponibilidade.serie, m, "")[0]], _F(r.custo_curtailment.valor))
         for r in b.renovaveis]
    termos = set(e3.termos)
    par = {}
    for k in G:
        g, sp, mem = gesp[k], e3.unidade(k), e3.memoria(k)
        lo, hi = _F(g.p_min_kW.valor), _F(g.p_max_kW.valor)
        q0 = q1 = None
        if g.curva_h2 is not None:
            (P0, Q0), (P1, Q1) = g.curva_h2.vertices                    # só curva de 1 segmento neste escopo
            lo, hi = max(lo, _F(P0)), min(hi, _F(P1))
            q0, q1 = (_F(P0), _F(Q0)), (_F(P1), _F(Q1))
        Rs, Rd = _F(sp.rampa_subida_kW_min.valor) * dmin, _F(sp.rampa_descida_kW_min.valor) * dmin
        if sp.limites_transicao == "declarados":
            Sp, Sd = _F(sp.potencia_partida_max_kW.valor), _F(sp.potencia_parada_max_kW.valor)
        else:
            Sp, Sd = Rs, Rd
        U = _ceil(_F(sp.tempo_min_ligado_min.valor) * 60 / ds)
        D = _ceil(_F(sp.tempo_min_desligado_min.valor) * 60 / ds)
        r0 = _ceil(Fr(mem.obrigacao_residual_s, ds)) if mem.obrigacao_residual_s else 0
        par[k] = dict(lo=lo, hi=hi, Rs=Rs, Rd=Rd, Sp=Sp, Sd=Sd, U=U, D=D, r0=r0, u0=int(est[k].ligado),
                      p0=_F(est[k].p_anterior_kW.valor), q0=q0, q1=q1, cH=None if g.preco_h2 is None else _F(g.preco_h2.valor),
                      csu=_F(sp.custo_partida.valor) if sp.custo_partida else Fr(0),
                      csd=_F(sp.custo_parada.valor) if sp.custo_parada else Fr(0),
                      msu=_F(sp.massa_h2_partida_kg.valor) if sp.massa_h2_partida_kg else Fr(0),
                      msd=_F(sp.massa_h2_parada_kg.valor) if sp.massa_h2_parada_kg else Fr(0))
    cumprir = e3.politica_permanencia.tipo == "cumprir_na_janela"

    def commitment_ok(k, u):
        P = par[k]
        seq = [P["u0"]] + list(u)
        if any(u[t] == 1 and a[k][t] != 1 for t in range(N)):
            return False
        for t in range(N):
            if seq[t] == 0 and seq[t + 1] == 1 and P["Sp"] < P["lo"]:
                return False
            if seq[t] == 1 and seq[t + 1] == 0 and P["Sd"] < P["lo"]:
                return False
        # corridas
        t = 0
        while t < N:
            s = t
            while t + 1 < N and u[t + 1] == u[s]:
                t += 1
            comp, v = t - s + 1, u[s]
            if s == 0 and v == P["u0"]:
                if comp < min(P["r0"], N):
                    return False
            else:
                exig = P["U"] if v == 1 else P["D"]
                if s + comp < N or cumprir:
                    if comp < exig:
                        return False
            t += 1
        return True

    melhor = []
    for prog in itertools.product((0, 1), repeat=len(G) * N):
        u = {k: prog[i * N:(i + 1) * N] for i, k in enumerate(G)}
        if not all(commitment_ok(k, u[k]) for k in G):
            continue
        y = {k: [int(([par[k]["u0"]] + list(u[k]))[t] == 0 and u[k][t] == 1) for t in range(N)] for k in G}
        z = {k: [int(([par[k]["u0"]] + list(u[k]))[t] == 1 and u[k][t] == 0) for t in range(N)] for k in G}
        # variáveis: p'_{k,t} (= p − lo, só ON) e C_{r,t}
        idx = {}
        for k in G:
            for t in range(N):
                if u[k][t]:
                    idx[("p", k, t)] = len(idx)
        for r, *_ in R:
            for t in range(N):
                idx[("C", r, t)] = len(idx)
        n = len(idx)
        c = [Fr(0)] * n
        const = Fr(0)
        A_eq, b_eq, A_ub, b_ub = [], [], [], []

        def linha():
            return [Fr(0)] * n
        for t in range(N):                                # balanço
            row, rhs = linha(), L[t]
            for k in G:
                if u[k][t]:
                    row[idx[("p", k, t)]] += 1
                    rhs -= par[k]["lo"]
            for r, A, ar, cc in R:
                row[idx[("C", r, t)]] -= 1
                rhs -= A[t] * ar[t]
            A_eq.append(row), b_eq.append(rhs)
        for k in G:
            P = par[k]
            for t in range(N):
                if u[k][t]:                                # p' <= hi − lo
                    row = linha()
                    row[idx[("p", k, t)]] = Fr(1)
                    A_ub.append(row), b_ub.append(P["hi"] - P["lo"])

                def pexp(tt):                              # p_tt = coef·x + const
                    if tt < 0:
                        return None, P["p0"]
                    if u[k][tt]:
                        return idx[("p", k, tt)], P["lo"]
                    return None, Fr(0)
                ua = P["u0"] if t == 0 else u[k][t - 1]
                (j1, c1), (j0, c0) = pexp(t), pexp(t - 1)
                lim_s = P["Rs"] * ua + P["Sp"] * y[k][t]
                lim_d = P["Rd"] * u[k][t] + P["Sd"] * z[k][t]
                for sinal, lim in ((1, lim_s), (-1, lim_d)):   # sinal·(p_t − p_{t−1}) <= lim
                    row = linha()
                    if j1 is not None:
                        row[j1] += sinal
                    if j0 is not None:
                        row[j0] -= sinal
                    A_ub.append(row), b_ub.append(lim - sinal * (c1 - c0))
            for t in range(N):                             # custos dos geradores
                const += P["csu"] * y[k][t] + P["csd"] * z[k][t] if "eventos" in termos else 0
                if P["cH"] is not None and "combustivel_h2" in termos:
                    const += P["cH"] * (P["msu"] * y[k][t] + P["msd"] * z[k][t])
                    if u[k][t]:
                        (P0, Q0), (P1, Q1) = P["q0"], P["q1"]
                        inc = (Q1 - Q0) / (P1 - P0)
                        const += P["cH"] * h * (Q0 + inc * (P["lo"] - P0))
                        c[idx[("p", k, t)]] += P["cH"] * h * inc
        for r, A, ar, cc in R:
            for t in range(N):
                row = linha()
                row[idx[("C", r, t)]] = Fr(1)
                A_ub.append(row), b_ub.append(A[t] * ar[t])
                if "curtailment_operacional" in termos:
                    c[idx[("C", r, t)]] += cc * h
        sol = simplex(c, A_eq, b_eq, A_ub, b_ub)
        if sol is None:
            continue
        val, x = sol
        p = {k: [(x[idx[("p", k, t)]] + par[k]["lo"]) if u[k][t] else Fr(0) for t in range(N)] for k in G}
        melhor.append((val + const, u, y, z, p))
    melhor.sort(key=lambda s: s[0])
    return melhor


__all__ = ["enumerar", "simplex"]
