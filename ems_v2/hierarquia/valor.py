"""Avaliação EXATA e independente das representações do valor terminal (3C-4) — só biblioteca padrão.

Usada pelo auditor (recalcula V̂ no estado terminal do despacho), pelo planejador (erro de aproximação nos pontos de
validação) e pela auditoria de missão. Não usa o solver nem o modelo Pyomo:

* ``constante_0d`` — V̂ = V do modo;
* ``intervalos_consecutivos_1d`` — interpolante linear por partes entre pontos consecutivos (contínuo; o valor num
  ponto de quebra é o do ponto; fora do domínio ⇒ ``None``);
* ``envoltoria_convexa_nd`` (2 bancos) — envoltória convexa INFERIOR dos pontos: min Σ λ_j V_j sujeito a Σ λ_j x_j = x,
  λ >= 0, Σ λ = 1. Pelo teorema de Carathéodory basta enumerar subconjuntos de até 3 pontos (2D) — enumeração exata
  (O(n³), grades pequenas declaradas). É exatamente o que a formulação λ do MILP representa;
* ``linear_local`` — V(E_ref) − Σ λ_b (E_b − E_ref,b) no domínio declarado;
* referências — dura: 0 (restrição); branda: ρ Σ max(0, E_ref − E).
"""
from __future__ import annotations

import itertools
import math

TOL = 1e-7


def interpolar_1d(pontos, E: float, tol: float = TOL) -> float | None:
    es = [p.energias_kWh[0] for p in pontos]
    vs = [p.valor_R for p in pontos]
    if E < es[0] - tol or E > es[-1] + tol:
        return None
    if len(es) == 1:
        return vs[0]
    E = min(max(E, es[0]), es[-1])
    for i in range(len(es) - 1):
        if E <= es[i + 1]:
            a, b = es[i], es[i + 1]
            w = (E - a) / (b - a)
            return vs[i] + w * (vs[i + 1] - vs[i])
    return vs[-1]


def _resolver_3x3(a):
    """Eliminação de Gauss com pivotamento parcial (3×3, 4 colunas). None se singular."""
    m = [list(r) for r in a]
    n = 3
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            return None
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def envoltoria_convexa(pontos, x, tol: float = TOL) -> float | None:
    """Envoltória convexa inferior (dimensão 1 ou 2) no ponto ``x``; None se ``x`` fora do fecho convexo."""
    d = len(x)
    P = [(tuple(p.energias_kWh), p.valor_R) for p in pontos]
    melhor = None

    def cand(v):
        nonlocal melhor
        if melhor is None or v < melhor:
            melhor = v
    for (xi, vi) in P:
        if all(abs(a - b) <= tol for a, b in zip(xi, x)):
            cand(vi)
    for (x1, v1), (x2, v2) in itertools.combinations(P, 2):
        dx = [b - a for a, b in zip(x1, x2)]
        n2 = sum(t * t for t in dx)
        if n2 <= tol * tol:
            continue
        w = sum((xx - a) * t for xx, a, t in zip(x, x1, dx)) / n2
        if -tol <= w <= 1 + tol and all(abs(a + w * t - xx) <= 1e-6 * max(1.0, abs(xx))
                                        for a, t, xx in zip(x1, dx, x)):
            cand(v1 + min(max(w, 0.0), 1.0) * (v2 - v1))
    if d == 2:
        for (x1, v1), (x2, v2), (x3, v3) in itertools.combinations(P, 3):
            sol = _resolver_3x3([[x1[0], x2[0], x3[0], x[0]], [x1[1], x2[1], x3[1], x[1]], [1.0, 1.0, 1.0, 1.0]])
            if sol is None or any(w < -1e-9 for w in sol):
                continue
            cand(sum(w * v for w, v in zip(sol, (v1, v2, v3))))
    elif d > 2:
        return None
    return melhor


def convexidade_verificada(pontos, dim: int, tol: float) -> tuple[bool, float]:
    """Amostra convexo-consistente: nenhum ponto acima da envoltória convexa dos DEMAIS (máximo excesso [R$])."""
    if dim == 0 or len(pontos) <= 2 and dim == 1:
        return True, 0.0
    exc = 0.0
    for i, p in enumerate(pontos):
        outros = [q for j, q in enumerate(pontos) if j != i]
        v = envoltoria_convexa(outros, p.energias_kWh, TOL) if dim <= 2 else None
        if v is not None:
            exc = max(exc, p.valor_R - v)
    return exc <= tol, exc


def inclinacoes_1d(pontos) -> list[float]:
    """dV/dE [R$/kWh] em cada segmento (λ_E = −inclinação)."""
    return [(b.valor_R - a.valor_R) / (b.energias_kWh[0] - a.energias_kWh[0]) for a, b in zip(pontos, pontos[1:])]


def avaliar_modo(sinal, modo, energias, tol: float = TOL) -> float | None:
    """V̂ do modo em ``energias`` (None fora do domínio ou representação não suportada)."""
    if any(e < lo - tol or e > hi + tol for e, lo, hi in zip(energias, modo.dominio_min_kWh, modo.dominio_max_kWh)):
        return None
    r = modo.representacao
    if r == "constante_0d":
        return modo.pontos[0].valor_R
    if r == "intervalos_consecutivos_1d":
        return interpolar_1d(modo.pontos, energias[0], tol)
    if r == "envoltoria_convexa_nd":
        return envoltoria_convexa(modo.pontos, tuple(energias), tol)
    if r == "linear_local":
        s = sinal.sensibilidade
        return s.valor_referencia_R - math.fsum(l * (e - e0) for l, e, e0 in zip(s.lambdas_R_kWh, energias,
                                                                                  s.energias_referencia_kWh))
    return None


def modos_compativeis(sinal, estados: dict[str, tuple[bool, int, float]], tol_p: float = 1e-6) -> list[int]:
    """Modos cujo estado terminal coincide com ``estados`` (uid → (ligado, obrigação residual [s], p [kW]))."""
    out = []
    for m in sinal.modos:
        if not m.geradores:
            out.append(m.indice)
            continue
        ok = True
        for x in m.geradores:
            st = estados.get(x.uid)
            if st is None or bool(st[0]) != x.ligado or int(st[1]) != x.obrigacao_residual_s:
                ok = False
            elif x.potencia_fixada_kW is not None and abs(st[2] - x.potencia_fixada_kW) > tol_p * max(1.0, abs(st[2])):
                ok = False
        if ok:
            out.append(m.indice)
    return out


def valor_termo_declarado(termo, energias: dict[str, float]) -> float | None:
    """Φ declarado no estado: nenhum ⇒ 0; linear ⇒ −Σ λ_b E_b; energia mínima ⇒ 0 se E >= Ē (None se violada)."""
    if termo.tipo == "nenhum_declarado":
        return 0.0
    if termo.tipo == "valor_linear_declarado":
        return -math.fsum(p.valor * energias[p.uid] for p in termo.lineares)
    if termo.tipo == "energia_minima_declarada":
        return 0.0 if all(energias[p.uid] >= p.valor - 1e-6 for p in termo.energias_minimas) else None
    return None


def penalidade_branda(sinal, energias) -> float:
    return sinal.penalidade_branda_R_kWh * math.fsum(max(0.0, r - e) for r, e in zip(sinal.referencia.energias_kWh,
                                                                                      energias))


__all__ = ["avaliar_modo", "convexidade_verificada", "envoltoria_convexa", "inclinacoes_1d", "interpolar_1d",
           "modos_compativeis", "penalidade_branda", "valor_termo_declarado"]
