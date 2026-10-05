"""Metaheurísticas do EMS portadas de ``gwo.m``, ``NGO.m`` e ``executar_ga.m``.

As funções recebem ``fun_lote(X) -> F`` que avalia uma *população* (linhas de
``X``) de uma vez — só por desempenho em Python; a sequência de operações e os
parâmetros (10 lobos x 55 iterações, 10 gaviões x 15 iterações, GA 15 x 20) são
os mesmos do MATLAB.

GWO e NGO: transcrição direta. GA: o ``ga`` do MATLAB (Global Optimization
Toolbox) não tem equivalente idêntico em SciPy; aqui ele é aproximado com a
mesma configuração (população 15, 20 gerações, 5 elites, cruzamento 0,8,
cruzamento *scattered* e mutação gaussiana adaptativa dentro da caixa). Os
resultados de GA dos dois backends não devem ser comparados número a número.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

FunLote = Callable[[np.ndarray], np.ndarray]


def gwo(fun: FunLote, LB, UB, n_wolves: int, n_iters: int, rng: np.random.Generator):
    LB = np.asarray(LB, float)
    UB = np.asarray(UB, float)
    dim = LB.size
    X = LB + rng.random((n_wolves, dim)) * (UB - LB)
    F = fun(X)
    idx = np.argsort(F, kind="stable")
    alpha, Fa = X[idx[0]].copy(), F[idx[0]]
    beta, Fb = X[idx[1]].copy(), F[idx[1]]
    delta, Fd = X[idx[2]].copy(), F[idx[2]]
    hist = np.zeros(n_iters)
    for t in range(n_iters):
        a = 2 - 2 * t / (n_iters - 1)
        # o MATLAB sorteia r1,r2 por (lobo, dimensão, líder): mesma distribuição
        r = rng.random((6, n_wolves, dim))
        A1, C1 = 2 * a * r[0] - a, 2 * r[1]
        A2, C2 = 2 * a * r[2] - a, 2 * r[3]
        A3, C3 = 2 * a * r[4] - a, 2 * r[5]
        X1 = alpha - A1 * np.abs(C1 * alpha - X)
        X2 = beta - A2 * np.abs(C2 * beta - X)
        X3 = delta - A3 * np.abs(C3 * delta - X)
        X = np.clip((X1 + X2 + X3) / 3, LB, UB)
        F = fun(X)
        for i in range(n_wolves):          # atualização sequencial dos líderes
            Fi = F[i]
            if Fi < Fa:
                delta, Fd = beta, Fb
                beta, Fb = alpha, Fa
                alpha, Fa = X[i].copy(), Fi
            elif Fi < Fb:
                delta, Fd = beta, Fb
                beta, Fb = X[i].copy(), Fi
            elif Fi < Fd:
                delta, Fd = X[i].copy(), Fi
        hist[t] = Fa
    return alpha, float(Fa), hist


def ngo(fun: FunLote, LB, UB, n_pop: int, n_iter: int, rng: np.random.Generator):
    LB = np.asarray(LB, float)
    UB = np.asarray(UB, float)
    dim = LB.size
    X = LB + rng.random((n_pop, dim)) * (UB - LB)
    F = fun(X)
    um = lambda x: float(fun(x[None, :])[0])
    for t in range(1, n_iter + 1):
        for i in range(n_pop):
            # Estágio 1: identificação da presa (exploração)
            k = rng.integers(n_pop)
            p, Fp = X[k].copy(), F[k]
            I = rng.integers(1, 3)
            r = rng.random()
            if Fp < F[i]:
                xn = X[i] + r * (p - I * X[i])
            else:
                xn = X[i] + r * (X[i] - p)
            xn = np.clip(xn, LB, UB)
            fn = um(xn)
            if fn < F[i]:
                X[i], F[i] = xn, fn
            # Estágio 2: perseguição (explotação)
            R = 0.02 * (1 - t / n_iter)
            r = rng.random()
            xn = np.clip(X[i] - R * (2 * r - 1) * X[i], LB, UB)
            fn = um(xn)
            if fn < F[i]:
                X[i], F[i] = xn, fn
    b = int(np.argmin(F))
    return X[b].copy(), float(F[b]), None


def ga(fun: FunLote, LB, UB, rng: np.random.Generator, pop: int = 15, gens: int = 20,
       elite: int = 5, crossover_fraction: float = 0.8):
    LB = np.asarray(LB, float)
    UB = np.asarray(UB, float)
    dim = LB.size
    span = np.where(UB > LB, UB - LB, 0.0)
    X = LB + rng.random((pop, dim)) * span
    F = fun(X)
    hist = np.zeros(gens)
    for g in range(gens):
        ordem = np.argsort(F, kind="stable")
        X, F = X[ordem], F[ordem]
        filhos = [X[:elite].copy()]
        n_rest = pop - elite
        n_cross = int(round(crossover_fraction * n_rest))
        n_mut = n_rest - n_cross

        def torneio(n):
            a = rng.integers(pop, size=(n, 2))
            return np.where(F[a[:, 0]] < F[a[:, 1]], a[:, 0], a[:, 1])

        if n_cross:
            p1, p2 = X[torneio(n_cross)], X[torneio(n_cross)]
            mask = rng.random((n_cross, dim)) < 0.5          # crossover "scattered"
            filhos.append(np.where(mask, p1, p2))
        if n_mut:
            escala = 0.1 * (1 - g / gens)                     # mutação adaptativa
            base = X[torneio(n_mut)]
            filhos.append(np.clip(base + rng.normal(0, 1, (n_mut, dim)) * escala * span, LB, UB))
        X = np.vstack(filhos)
        F = np.concatenate([F[:elite], fun(X[elite:])])
        hist[g] = F.min()
    b = int(np.argmin(F))
    return X[b].copy(), float(F[b]), hist
