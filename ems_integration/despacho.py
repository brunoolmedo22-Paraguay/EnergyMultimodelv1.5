"""Núcleo de otimização do EMS (Python).

Origem: ``despacho.m``, ``custo_despacho.m``, ``restricoes_despacho.m``,
``candidatos_config.m``, ``idx_despacho.m`` e ``relatorio_despacho.m`` do EMS
MATLAB (cópia de referência em ``reference_models/ems_matlab``).

Estrutura preservada — MINLP por passo com recuo móvel:
    para cada configuração inteira candidata (vizinhança da anterior)
      → metaheurística (GA/GWO/NGO) gera o ponto inicial
      → SQP refina a parte contínua
    → vence o menor custo viável; aplica-se só o 1º passo do horizonte.

Diferença de FORMULAÇÃO (não de problema): no MATLAB a bateria é uma variável
P ∈ [P_carga_max, P_desc_max] e o custo/balanço/SOC usam |P| e uma eficiência
que muda de sinal em P=0. Essas quinas fazem o SQP ziguezaguear (~60 iterações
por chamada). Aqui a bateria vira duas variáveis, P_desc ≥ 0 e P_carga ≤ 0, com
P = P_desc + P_carga. Todas as restrições ficam LINEARES (jacobiana constante por
configuração) e o SQP converge em poucas iterações. No ótimo as duas formulações
coincidem, porque carregar e descarregar ao mesmo tempo só acrescenta perda e
custo de degradação; o despacho mede e reporta qualquer simultaneidade.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from .contrato import Fonte
from .metaheuristicas import ga, gwo, ngo

NOMES_ALG = {0: "SQP (sem metaheurística)", 1: "GA", 2: "GWO", 3: "NGO"}
SIGLAS_ALG = {0: "SQP", 1: "GA", 2: "GWO", 3: "NGO"}
TOL_VIAVEL = 1e-6   # mesma tolerância de despacho.m (out.constrviolation <= 1e-6)


@dataclass
class CfgDespacho:
    Ts_s: float = 60.0
    N: int = 3
    S_base: float = 1.0
    pen_deficit: float = 50.0
    pen_excesso: float = 0.5
    algoritmo: int = 2
    teto_combos: int = 64
    meta_penalizada: bool = False
    soc_alvo_tol: float = 0.05
    seed: int | None = 0
    max_iter_sqp: int = 200


# ------------------------------------------------------------------ índices
class Idx:
    """x = [P_1(1:N); …; P_m(1:N); Pc_a(1:N); …; s_def(1:N); s_exc(1:N)]  (p.u. de S_base).

    Para uma fonte de armazenamento, o bloco ``fonte[j]`` é a DESCARGA (≥0) e
    ``carga[j]`` a CARGA (≤0). Para as demais, ``carga[j]`` é None."""

    def __init__(self, N: int, fontes: list[Fonte]):
        m = len(fontes)
        self.N, self.m = N, m
        self.fonte = [np.arange(j * N, (j + 1) * N) for j in range(m)]
        pos = m * N
        self.carga: list[np.ndarray | None] = []
        for f in fontes:
            if f.armazena:
                self.carga.append(np.arange(pos, pos + N))
                pos += N
            else:
                self.carga.append(None)
        self.s_def = np.arange(pos, pos + N)
        self.s_exc = np.arange(pos + N, pos + 2 * N)
        self.n_total = pos + 2 * N

    def potencia(self, X: np.ndarray, j: int) -> np.ndarray:
        """Potência líquida da fonte j (descarga + carga para armazenamento)."""
        P = X[..., self.fonte[j]]
        if self.carga[j] is not None:
            P = P + X[..., self.carga[j]]
        return P


# -------------------------------------------------------------- candidatos
def candidatos_config(fontes: list[Fonte], n_prev: np.ndarray, teto: int, avisos: set[str]):
    """``candidatos_config.m``: vizinhança |n − n_prev| ≤ dn_max, ordenada pelo custo de partida."""
    cand = []
    for j, f in enumerate(fontes):
        if f.armazena:
            cand.append(np.array([1]))
            continue
        lo = max(0, n_prev[j] - f.dn_max)
        hi = min(f.n_unid, n_prev[j] + f.dn_max)
        c = np.arange(int(np.ceil(lo)), int(np.floor(hi)) + 1)
        cand.append(c if c.size else np.array([n_prev[j]]))
    n_comb = int(np.prod([c.size for c in cand]))
    if n_comb > teto:
        for j in np.argsort([f.c_start_unid_rs for f in fontes], kind="stable"):
            if n_comb <= teto:
                break
            if cand[j].size > 1:
                cand[j] = np.array([n_prev[j]])
                n_comb = int(np.prod([c.size for c in cand]))
        avisos.add(f"Vizinhança excedia {teto} combinações; algumas fontes foram fixadas na configuração anterior.")
    grids = np.meshgrid(*cand, indexing="ij")
    combos = np.column_stack([g.ravel(order="F") for g in grids]).astype(int)
    custo = np.zeros(combos.shape[0])
    for j, f in enumerate(fontes):
        custo += np.maximum(combos[:, j] - n_prev[j], 0) * f.c_start_unid_rs
    ordem = np.argsort(custo, kind="stable")
    return combos[ordem], custo[ordem]


# -------------------------------------------------------------------- custo
def custo_lote(X, fontes, ix: Idx, cfg: CfgDespacho, h, n_cand) -> np.ndarray:
    """``custo_despacho.m`` (R$) avaliado para todas as linhas de X de uma vez."""
    S, Ts_h = cfg.S_base, cfg.Ts_s / 3600.0
    J = np.zeros(X.shape[0])
    for j, f in enumerate(fontes):
        if f.armazena:
            Pd = X[:, ix.fonte[j]] * S
            Pc = X[:, ix.carga[j]] * S
            c = f.c_var_rs_kWh[h, 0] + f.c_deg_rs_kWh
            J += np.sum(c * (Pd - Pc), axis=1) * Ts_h        # |P| = Pd − Pc
        else:
            P = X[:, ix.fonte[j]] * S                         # P ≥ 0 pela caixa
            J += np.sum(f.custo_por_kwh(P, n_cand[j], h) * P, axis=1) * Ts_h
    J += cfg.pen_deficit * np.sum(X[:, ix.s_def], axis=1) * S * Ts_h
    J += cfg.pen_excesso * np.sum(X[:, ix.s_exc], axis=1) * S * Ts_h
    return J


def grad_custo(x, fontes, ix: Idx, cfg: CfgDespacho, h, n_cand) -> np.ndarray:
    S, Ts_h = cfg.S_base, cfg.Ts_s / 3600.0
    g = np.zeros_like(x)
    for j, f in enumerate(fontes):
        if f.armazena:
            c = (f.c_var_rs_kWh[h, 0] + f.c_deg_rs_kWh) * S * Ts_h
            g[ix.fonte[j]] = c
            g[ix.carga[j]] = -c
            continue
        P = x[ix.fonte[j]] * S
        if f.curva is not None:
            n = max(n_cand[j], 1)
            u = P / n
            fu = f.curva(u)
            if f.curva.x.size > 1:
                k = np.clip(np.searchsorted(f.curva.x, u, side="right") - 1, 0, f.curva.x.size - 2)
                dx = np.diff(f.curva.x)[k]
                incl = np.diff(f.curva.y)[k] / np.where(dx > 0, dx, 1.0)
                incl = np.where((u < f.curva.x[0]) | (u > f.curva.x[-1]), 0.0, incl)
            else:
                incl = 0.0
            d = (fu + u * incl) * f.curva.fator_custo        # d[c(P)·P]/dP
        else:
            d = f.custo_por_kwh(P, n_cand[j], h)
        g[ix.fonte[j]] = d * S * Ts_h
    g[ix.s_def] = cfg.pen_deficit * S * Ts_h
    g[ix.s_exc] = cfg.pen_excesso * S * Ts_h
    return g


# --------------------------------------------------------------- restrições
def _n_prev_de(f: Fonte, P_prev_j: float) -> int:
    """Heurística de ``restricoes_despacho.m`` para saber se a configuração mudou."""
    if abs(P_prev_j) < 1e-6:
        return 0
    return max(1, min(f.n_unid, round(abs(P_prev_j) / max(f.P_max_unid_kW[0], np.finfo(float).eps))))


@dataclass
class Lineares:
    A_eq: np.ndarray
    b_eq: np.ndarray
    A_in: np.ndarray      # A_in x ≤ b_in
    b_in: np.ndarray

    def violacao(self, X: np.ndarray) -> np.ndarray:
        """Violação máxima por linha de X (kW no balanço, fração no SOC)."""
        X = np.atleast_2d(X)
        v = np.max(np.abs(X @ self.A_eq.T - self.b_eq), axis=1)
        if self.b_in.size:
            v = np.maximum(v, np.max(np.maximum(X @ self.A_in.T - self.b_in, 0), axis=1))
        return v

    def violacao_soma(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(X)
        v = np.sum(np.abs(X @ self.A_eq.T - self.b_eq), axis=1)
        if self.b_in.size:
            v += np.sum(np.maximum(X @ self.A_in.T - self.b_in, 0), axis=1)
        return v


def restricoes_lineares(fontes, ix: Idx, cfg: CfgDespacho, SOC_ini, P_prev, Pl_h, n_cand) -> Lineares:
    """As três famílias de ``restricoes_despacho.m``, na forma matricial.

    (1) balanço com folgas; (2) SOC na faixa e na banda do alvo ao fim do
    horizonte; (3) rampa por unidade (dispensada no passo em que a configuração
    muda, como no MATLAB)."""
    N, S, nx = ix.N, cfg.S_base, ix.n_total
    Ts_h, Ts_min = cfg.Ts_s / 3600.0, cfg.Ts_s / 60.0
    r = np.arange(N)
    # (1) Σ eta·P_gen + Σ(eta·Pd + Pc/eta) + s_def − s_exc = Pl
    A_eq = np.zeros((N, nx))
    for j, f in enumerate(fontes):
        A_eq[r, ix.fonte[j]] = f.eta * S
        if f.armazena:
            A_eq[r, ix.carga[j]] = S / f.eta
    A_eq[r, ix.s_def] = S
    A_eq[r, ix.s_exc] = -S
    b_eq = Pl_h * S

    linhas, lim = [], []
    # (2) soc_i = soc0 − Σ_{l≤i}(Pd/eta_d + Pc·eta_c)·Ts_h/E
    low = np.tril(np.ones((N, N)))
    for j, f in enumerate(fontes):
        if not f.armazena:
            continue
        D = np.zeros((N, nx))                                   # soc_h = soc0 + D·x
        D[:, ix.fonte[j]] = -low * S * Ts_h / f.eta_descarga / f.E_kWh
        D[:, ix.carga[j]] = -low * S * Ts_h * f.eta_carga / f.E_kWh
        s0 = SOC_ini[j]
        linhas += [D, -D]
        lim += [np.full(N, f.SOC_max - s0), np.full(N, s0 - f.SOC_min)]
        if f.SOC_alvo is not None:
            linhas += [D[-1:], -D[-1:]]
            lim += [np.array([f.SOC_alvo + cfg.soc_alvo_tol - s0]), np.array([s0 - (f.SOC_alvo - cfg.soc_alvo_tol)])]
    # (3) rampa
    for j, f in enumerate(fontes):
        if not np.isfinite(f.ramp_kW_min) or n_cand[j] == 0:
            continue
        dmax = n_cand[j] * f.ramp_kW_min * Ts_min
        blocos = [ix.fonte[j]] + ([ix.carga[j]] if f.armazena else [])
        mudou = abs(n_cand[j] - _n_prev_de(f, P_prev[j])) > 0
        if abs(P_prev[j]) > 1e-6 and not mudou:
            e = np.zeros((1, nx))
            for b in blocos:
                e[0, b[0]] = S
            linhas += [e, -e]
            lim += [np.array([P_prev[j] + dmax]), np.array([dmax - P_prev[j]])]
        if N > 1:
            Dd = np.zeros((N - 1, nx))
            for b in blocos:
                Dd[np.arange(N - 1), b[1:]] = S
                Dd[np.arange(N - 1), b[:-1]] = -S
            linhas += [Dd, -Dd]
            lim += [np.full(N - 1, dmax), np.full(N - 1, dmax)]
    A_in = np.vstack(linhas) if linhas else np.zeros((0, nx))
    b_in = np.concatenate(lim) if lim else np.zeros(0)
    return Lineares(A_eq, b_eq, A_in, b_in)


# ------------------------------------------------------------------ despacho
def despacho(fontes: list[Fonte], P_load_kW: np.ndarray, cfg: CfgDespacho, progresso=None) -> dict:
    rng = np.random.default_rng(cfg.seed)
    Nt, m, N = P_load_kW.size, len(fontes), cfg.N
    if Nt < 1:
        raise ValueError("Perfil de carga vazio.")
    S, Ts_h = cfg.S_base, cfg.Ts_s / 3600.0
    SOC = np.array([f.SOC_ini if f.armazena else 0.0 for f in fontes], dtype=float)
    n_prev = np.array([f.n_ini for f in fontes], dtype=int)
    P_prev = np.zeros(m)
    rho = 10 * cfg.pen_deficit * Ts_h          # penalidade exata p/ a meta (opcional)
    avisos: set[str] = set()

    res = {
        "P_kW": np.zeros((Nt, m)), "n_unid": np.zeros((Nt, m), dtype=int), "SOC": np.full((Nt, m), np.nan),
        "deficit_kW": np.zeros(Nt), "excesso_kW": np.zeros(Nt), "custo_rs": np.zeros(Nt),
        "custo_partida_rs": np.zeros(Nt), "J_meta": np.full(Nt, np.nan), "J_ref": np.full(Nt, np.nan),
        "viol_meta": np.full(Nt, np.nan), "viol_ref": np.full(Nt, np.nan), "P_meta_kW": np.full((Nt, m), np.nan),
        "n_combos": np.zeros(Nt, dtype=int), "t_meta_s": 0.0, "t_ref_s": 0.0, "n_inviaveis": 0,
        "simultaneo_max_kW": 0.0,
    }
    # Receding horizon até o último passo. No corpo da missão usa-se N; nos
    # últimos N-1 passos o horizonte encolhe (N-1, ..., 1) em vez de abandonar
    # o final da série. Assim cada minuto recebe uma decisão otimizada real.
    k_fim = Nt
    for k in range(k_fim):
        N_h = min(N, Nt - k)
        ix = Idx(N_h, fontes)
        h = np.arange(k, k + N_h)
        Pl_h = P_load_kW[h] / S
        combos, c_switch = candidatos_config(fontes, n_prev, cfg.teto_combos, avisos)
        res["n_combos"][k] = combos.shape[0]
        melhor = None
        achou = False
        for ic in range(combos.shape[0]):
            n_c = combos[ic]
            caixa = _caixa(fontes, ix, n_c, h, S)
            if caixa is None:
                continue
            LB, UB = caixa
            lin = restricoes_lineares(fontes, ix, cfg, SOC, P_prev, Pl_h, n_c)
            f_lote = lambda X, n_c=n_c: custo_lote(X, fontes, ix, cfg, h, n_c)
            if cfg.meta_penalizada:
                f_meta = lambda X, f_lote=f_lote, lin=lin: f_lote(X) + rho * lin.violacao_soma(X)
            else:
                f_meta = f_lote                                  # original: meta só vê custo

            x0 = np.clip((LB + UB) / 2, LB, UB)
            x0[~np.isfinite(x0)] = 0.0
            # Caixa da METAHEURÍSTICA: o despacho.m usa min(UB, 1e3) p.u., o que deixa as
            # folgas s_def/s_exc livres até 1000×S_base — a população é sorteada longe de
            # qualquer ponto balanceado. Déficit nunca passa da carga e excesso nunca passa
            # da geração máxima possível; o SQP continua com as folgas ilimitadas.
            UBm = np.minimum(UB, 1e3)
            UBm[ix.s_def] = Pl_h
            UBm[ix.s_exc] = sum(UB[ix.fonte[j]] for j in range(m))
            t0 = time.perf_counter()
            if cfg.algoritmo == 1:
                x0, _, _ = ga(f_meta, LB, UBm, rng)
            elif cfg.algoritmo == 2:
                x0, _, _ = gwo(f_meta, LB, UBm, 10, 55, rng)
            elif cfg.algoritmo == 3:
                x0, _, _ = ngo(f_meta, LB, UBm, 10, 15, rng)
            x0 = np.clip(x0, LB, UB)
            res["t_meta_s"] += time.perf_counter() - t0
            Jm = float(f_lote(x0[None])[0])
            vm = float(lin.violacao(x0)[0])

            t0 = time.perf_counter()
            x, J, convergiu, viol = _sqp(x0, f_lote, lin, LB, UB, fontes, ix, cfg, h, n_c)
            res["t_ref_s"] += time.perf_counter() - t0
            Jt = J + c_switch[ic]
            viavel = convergiu and viol <= TOL_VIAVEL
            if melhor is None or (viavel and not achou) or (viavel and achou and Jt < melhor["J"]) or \
                    (not viavel and not achou and viol < melhor["viol"]):
                melhor = dict(J=Jt, x=x, n=n_c.copy(), viol=viol, cs=c_switch[ic], Jm=Jm, vm=vm, xm=x0)
                achou = achou or viavel
        if melhor is None:
            raise RuntimeError(f"Passo {k + 1}: nenhuma configuração com envelope consistente (piso > teto).")
        if not achou:
            res["n_inviaveis"] += 1

        x, n_prev = melhor["x"], melhor["n"]
        res["J_meta"][k], res["J_ref"][k] = melhor["Jm"], melhor["J"] - melhor["cs"]
        res["viol_meta"][k], res["viol_ref"][k] = melhor["vm"], melhor["viol"]
        custo_k = 0.0
        for j, f in enumerate(fontes):
            Pj = float(ix.potencia(x, j)[0] * S)
            res["P_meta_kW"][k, j] = float(ix.potencia(melhor["xm"], j)[0] * S)
            res["P_kW"][k, j] = Pj
            res["n_unid"][k, j] = n_prev[j]
            P_prev[j] = Pj
            if f.armazena:
                Pd, Pc = x[ix.fonte[j][0]] * S, x[ix.carga[j][0]] * S
                res["simultaneo_max_kW"] = max(res["simultaneo_max_kW"], float(min(Pd, -Pc)))
                custo_k += (f.c_var_rs_kWh[k, 0] + f.c_deg_rs_kWh) * abs(Pj) * Ts_h
                dE = Pj * Ts_h / f.eta_descarga if Pj >= 0 else Pj * Ts_h * f.eta_carga
                SOC[j] = min(max(SOC[j] - dE / f.E_kWh, 0.0), 1.0)
                res["SOC"][k, j] = SOC[j]
            else:
                # custo_fn quando existe (FC) — corrige o placeholder zerado do MATLAB
                custo_k += float(f.custo_por_kwh(np.array([Pj]), n_prev[j], np.array([k]))[0]) * abs(Pj) * Ts_h
        res["deficit_kW"][k] = x[ix.s_def[0]] * S
        res["excesso_kW"][k] = x[ix.s_exc[0]] * S
        res["custo_partida_rs"][k] = melhor["cs"]
        res["custo_rs"][k] = custo_k + melhor["cs"] + (cfg.pen_deficit * res["deficit_kW"][k]
                                                       + cfg.pen_excesso * res["excesso_kW"][k]) * Ts_h
        if progresso is not None:
            progresso(k + 1, k_fim)

    if res["n_inviaveis"]:
        avisos.add(f"{res['n_inviaveis']} passo(s) sem configuração estritamente viável "
                   f"(violação > {TOL_VIAVEL:g}); usada a de menor violação.")
    if res["simultaneo_max_kW"] > 1e-3:
        avisos.add(f"Carga e descarga simultâneas de até {res['simultaneo_max_kW']:.3f} kW em algum passo.")
    res["nomes"] = [f.nome for f in fontes]
    res["custo_total_rs"] = float(res["custo_rs"].sum())
    res["energia_nao_atendida_kWh"] = float(res["deficit_kW"].sum() * Ts_h)
    res["energia_vertida_kWh"] = float(res["excesso_kW"].sum() * Ts_h)
    n_ini = np.array([f.n_ini for f in fontes])
    res["partidas"] = np.maximum(np.diff(np.vstack([n_ini, res["n_unid"][:k_fim]]), axis=0), 0).sum(axis=0)
    res["k_validos"] = k_fim
    res["avisos"] = sorted(avisos)
    return res


def _caixa(fontes, ix: Idx, n_c, h, S):
    LB = np.zeros(ix.n_total)
    UB = np.zeros(ix.n_total)
    for j, f in enumerate(fontes):
        if f.armazena:
            UB[ix.fonte[j]] = np.maximum(f.P_max_unid_kW[h], 0) / S
            LB[ix.carga[j]] = np.minimum(f.P_min_unid_kW[h], 0) / S
            continue
        if n_c[j] == 0:
            continue
        lo = n_c[j] * f.P_min_unid_kW[h]
        hi = n_c[j] * f.P_max_unid_kW[h]
        if np.any(lo > hi + 1e-12):
            return None
        LB[ix.fonte[j]] = lo / S
        UB[ix.fonte[j]] = hi / S
    UB[ix.s_def] = np.inf
    UB[ix.s_exc] = np.inf
    return LB, UB


def _sqp(x0, f_lote, lin: Lineares, LB, UB, fontes, ix, cfg, h, n_c):
    cons = [{"type": "eq", "fun": lambda x: lin.A_eq @ x - lin.b_eq, "jac": lambda x: lin.A_eq}]
    if lin.b_in.size:
        cons.append({"type": "ineq", "fun": lambda x: lin.b_in - lin.A_in @ x, "jac": lambda x: -lin.A_in})
    bounds = [(lo, hi if np.isfinite(hi) else None) for lo, hi in zip(LB, UB)]
    r = minimize(lambda x: float(f_lote(x[None])[0]), x0,
                 jac=lambda x: grad_custo(x, fontes, ix, cfg, h, n_c),
                 method="SLSQP", bounds=bounds, constraints=cons,
                 options={"maxiter": cfg.max_iter_sqp, "ftol": 1e-9})
    x = np.clip(r.x, LB, UB)
    # SLSQP 0 ≈ fmincon 1; SLSQP 8 (sem descida na busca linear, no ótimo) ≈ fmincon 2;
    # SLSQP 9 (limite de iterações) ≈ fmincon 0 → não conta como convergido.
    return x, float(f_lote(x[None])[0]), r.status in (0, 8), float(lin.violacao(x)[0])


# ---------------------------------------------------------------- relatório
def relatorio(res: dict, fontes: list[Fonte], cfg: CfgDespacho) -> dict:
    """``relatorio_despacho.m``: energia, % de atendimento, custo, SOC final e consumo físico."""
    Ts_h = cfg.Ts_s / 3600.0
    kv = res["k_validos"]
    m = len(fontes)
    tt = np.arange(kv)
    E, custo, socf = np.zeros(m), np.zeros(m), np.full(m, np.nan)
    consumo, h2_passo = {}, np.zeros(res["P_kW"].shape[0])
    for j, f in enumerate(fontes):
        P = res["P_kW"][:kv, j]
        n = res["n_unid"][:kv, j]
        E[j] = np.maximum(P, 0).sum() * Ts_h
        if f.curva is not None:
            c = f.custo_por_kwh(P, n, tt)
        else:
            cols = np.clip(np.maximum(n, 1), 1, f.c_var_rs_kWh.shape[1]) - 1
            c = f.c_var_rs_kWh[tt, cols]
        custo[j] = np.sum(c * np.abs(P)) * Ts_h
        if f.armazena:
            custo[j] += f.c_deg_rs_kWh * np.abs(P).sum() * Ts_h
            s = res["SOC"][:kv, j]
            if np.any(~np.isnan(s)):
                socf[j] = s[np.flatnonzero(~np.isnan(s))[-1]]
        q = f.qtd_por_kwh(P, n)
        if q is not None:
            passo = q * np.maximum(P, 0) * Ts_h
            consumo[f.nome] = {"valor": float(passo.sum()), "unidade": f.qtd_fisica_unidade}
            if f.nome == "fc":
                h2_passo[:kv] = passo
    Et = E.sum()
    return {
        "energia_por_fonte_kWh": E, "pct_atendimento": 100 * E / Et if Et > 1e-9 else np.zeros(m),
        "SOC_final": socf, "custo_por_fonte_rs": custo, "custo_total_rs": res["custo_total_rs"],
        "energia_nao_atendida_kWh": res["energia_nao_atendida_kWh"],
        "energia_vertida_kWh": res["energia_vertida_kWh"], "partidas": np.asarray(res["partidas"]),
        "consumo_fisico": consumo, "h2_kg_passo": h2_passo,
    }
