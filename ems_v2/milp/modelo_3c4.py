"""Construção do MILP Pyomo do perfil ``v1.1-3C-4`` (termo terminal / custo de continuação) — UMA janela.

COMPOSIÇÃO sobre ``modelo_3c3.construir_modelo_3c3`` (inalterado; que compõe o 3C-1 e o 3B-P): todo o núcleo físico,
de commitment e do PCC é EXATAMENTE o do 3C-3. Acrescenta-se SÓ o termo terminal declarado na entrada
(``docs/ems_v2/FORMULACAO_3C4.md`` §5):

* ``valor_linear_declarado``     ``Φ = −Σ_b λ_b e_{b,N}`` (termo ``valor_residual_declarado``);
* ``energia_minima_declarada``   ``e_{b,N} >= Ē_b``;
* ``referencia_energia_dura``    ``e_{b,N} >= E_ref,b`` (sem custo);
* ``referencia_energia_branda``  ``σ_b >= E_ref,b − e_{b,N}``, ``σ_b >= 0``; ``ρ Σ σ_b`` (termo ``custo_futuro_estimado``);
* ``custo_futuro_pwl`` / ``valor_marginal_local`` — seleção EXATA do modo terminal ``s_i ∈ {0,1}``, ``Σ s_i = 1``,
  ``u_{g,N−1} = Σ_{i: g ligado no modo i} s_i``; potência fixada no modo (se exigida):
  ``P_fix s_i <= p_{g,N−1} <= P_fix + (P_max − P_fix)(1 − s_i)`` (coeficientes = limites físicos DECLARADOS, nenhum
  Big-M arbitrário); valor:

  - 0D: ``θ = Σ_i V_i s_i``;
  - 1D: segmentos consecutivos com binárias explícitas (sem SOS, como M14–M16): ``Σ_j δ_ij = s_i``, ``φ_ij <= δ_ij``,
    ``e_{b,N} = Σ_ij [E_j δ_ij + (E_{j+1} − E_j) φ_ij]``, ``θ = Σ_ij [V_j δ_ij + (V_{j+1} − V_j) φ_ij]`` —
    representação EXATA do interpolante (convexo ou não) e do domínio;
  - 2D: ``λ_ij >= 0``, ``Σ_j λ_ij = s_i``, ``e_{b,N} = Σ λ_ij x_jb``, ``θ = Σ λ_ij V_j`` (envoltória convexa: só com
    convexidade verificada);
  - linear local: modo único fixado, ``E_lo <= e_{b,N} <= E_hi``, ``θ = V_ref − Σ_b λ_b (e_{b,N} − E_ref,b)``.

Objetivo: ``J = J_3C-3 + θ``. A memória terminal (obrigação residual 0 com ``cumprir_na_janela`` ou a herdada) é
garantida pelas restrições M12 do núcleo e CONFERIDA pelo auditor (não reformulada aqui). Modelo linear, sem SOS.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pyomo.environ as pe

from ..hierarquia.contrato import EntradaHierarquica3C4
from .modelo_3c3 import ModeloConstruido3C3, construir_modelo_3c3


@dataclass
class ModeloConstruido3C4:
    rede: ModeloConstruido3C3
    termos: tuple[str, ...] = ()
    expr_termos: dict = field(default_factory=dict)
    chave_terminal: str | None = None
    n_modos: int = 0
    segmentos: dict = field(default_factory=dict)     # modo → [(j, ...)]

    @property
    def modelo(self) -> pe.ConcreteModel:
        return self.rede.modelo

    @property
    def base(self):
        return self.rede.base

    @property
    def nucleo(self):
        return self.rede.nucleo

    @property
    def discretizacao(self):
        return self.rede.discretizacao

    @property
    def transicoes_bloqueadas(self):
        return self.rede.transicoes_bloqueadas


def construir_modelo_3c4(e: EntradaHierarquica3C4, compromisso_parcial: dict | None = None) -> ModeloConstruido3C4:
    """Supõe entrada validada (``validar_entrada_3c4`` + ``preflight_3c3`` sem bloqueios)."""
    mc3 = construir_modelo_3c3(e.rede, compromisso_parcial)
    m = mc3.modelo
    m.name = "seeds2_milp_3c4"
    mcb = mc3.base
    N = mcb.N
    t = e.terminal
    expr = dict(mc3.expr_termos)
    termos = list(mc3.termos)
    out = ModeloConstruido3C4(mc3)
    gesp = {str(g.uid): g for g in e.base.geradores}
    chave = None
    if t.tipo == "valor_linear_declarado":
        lam = {p.uid: float(p.valor) for p in t.lineares}
        chave = "valor_residual_declarado"
        expr[chave] = -sum(lam[b] * m.e[b, N] for b in mcb.baterias)
    elif t.tipo == "energia_minima_declarada":
        emin = {p.uid: float(p.valor) for p in t.energias_minimas}
        m.T4_emin = pe.Constraint(m.B, rule=lambda m, b: m.e[b, N] >= emin[b])
    elif t.tipo == "sinal_valor_futuro":
        s = t.sinal
        bats = list(s.baterias)
        if s.tipo in ("referencia_energia_dura", "referencia_energia_branda"):
            ref = dict(zip(bats, s.referencia.energias_kWh))
            if s.tipo == "referencia_energia_dura":
                m.T4_ref = pe.Constraint(m.B, rule=lambda m, b: m.e[b, N] >= ref[b])
            else:
                m.T4_folga = pe.Var(m.B, domain=pe.NonNegativeReals)
                m.T4_branda = pe.Constraint(m.B, rule=lambda m, b: m.T4_folga[b] >= ref[b] - m.e[b, N])
                chave = "custo_futuro_estimado"
                expr[chave] = float(s.penalidade_branda_R_kWh) * sum(m.T4_folga[b] for b in mcb.baterias)
        else:
            chave = "custo_futuro_estimado"
            expr[chave] = _valor_por_modos(m, s, bats, N, gesp, out)
    if chave is not None:
        termos.append(chave)
    m.del_component(m.J)
    m.J = pe.Objective(expr=sum(expr[x] for x in termos) if termos else 0, sense=pe.minimize)
    out.termos, out.expr_termos, out.chave_terminal = tuple(termos), expr, chave
    return out


def _valor_por_modos(m, s, bats, N, gesp, out: ModeloConstruido3C4):
    modos = list(s.modos)
    I = range(len(modos))
    out.n_modos = len(modos)
    m.T4_I = pe.Set(initialize=list(I), ordered=True)
    m.T4_s = pe.Var(m.T4_I, domain=pe.Binary)
    m.T4_um = pe.Constraint(expr=sum(m.T4_s[i] for i in I) == 1)
    cond = bool(modos[0].geradores)
    if cond:
        for g in s.geradores:
            liga = [i for i in I if next(x for x in modos[i].geradores if x.uid == g).ligado]
            m.add_component(f"T4_u_{_n(g)}", pe.Constraint(expr=m.u[g, N - 1] == sum(m.T4_s[i] for i in liga)))
            pmax = float(gesp[g].p_max_kW.valor)
            for i in I:
                x = next(y for y in modos[i].geradores if y.uid == g)
                if x.potencia_fixada_kW is not None:
                    pf = float(x.potencia_fixada_kW)
                    m.add_component(f"T4_pfix_lo_{_n(g)}_{i}", pe.Constraint(expr=m.p[g, N - 1] >= pf * m.T4_s[i]))
                    m.add_component(f"T4_pfix_hi_{_n(g)}_{i}", pe.Constraint(
                        expr=m.p[g, N - 1] <= pf + (pmax - pf) * (1 - m.T4_s[i])))
    dim = len(bats)
    if s.tipo == "valor_marginal_local":
        sl = s.sensibilidade
        m.T4_fixo = pe.Constraint(expr=m.T4_s[0] == 1)
        for j, b in enumerate(bats):
            lo, hi = modos[0].dominio_min_kWh[j], modos[0].dominio_max_kWh[j]
            m.add_component(f"T4_dom_{_n(b)}", pe.Constraint(expr=pe.inequality(lo, m.e[b, N], hi)))
        return sl.valor_referencia_R - sum(sl.lambdas_R_kWh[j] * (m.e[b, N] - sl.energias_referencia_kWh[j])
                                           for j, b in enumerate(bats))
    if dim == 0:
        return sum(modos[i].pontos[0].valor_R * m.T4_s[i] for i in I)
    if dim == 1:
        b = bats[0]
        seg = [(i, j) for i in I for j in range(max(0, len(modos[i].pontos) - 1))]
        out.segmentos = {i: [j for (ii, j) in seg if ii == i] for i in I}
        m.T4_S = pe.Set(initialize=seg, dimen=2, ordered=True)
        m.T4_delta = pe.Var(m.T4_S, domain=pe.Binary)
        m.T4_phi = pe.Var(m.T4_S, bounds=(0.0, 1.0))
        m.T4_seg = pe.Constraint(m.T4_I, rule=lambda m, i: (sum(m.T4_delta[i, j] for j in out.segmentos[i]) == m.T4_s[i])
                                 if out.segmentos[i] else pe.Constraint.Skip)
        m.T4_phi_d = pe.Constraint(m.T4_S, rule=lambda m, i, j: m.T4_phi[i, j] <= m.T4_delta[i, j])

        def contrib(i, k):           # k = 0 energia, 1 valor
            P = modos[i].pontos
            if len(P) == 1:
                return (P[0].energias_kWh[0] if k == 0 else P[0].valor_R) * m.T4_s[i]
            g = (lambda p: p.energias_kWh[0]) if k == 0 else (lambda p: p.valor_R)
            return sum(g(P[j]) * m.T4_delta[i, j] + (g(P[j + 1]) - g(P[j])) * m.T4_phi[i, j]
                       for j in out.segmentos[i])
        m.T4_E = pe.Constraint(expr=m.e[b, N] == sum(contrib(i, 0) for i in I))
        return sum(contrib(i, 1) for i in I)
    pts = [(i, j) for i in I for j in range(len(modos[i].pontos))]
    m.T4_P = pe.Set(initialize=pts, dimen=2, ordered=True)
    m.T4_lam = pe.Var(m.T4_P, domain=pe.NonNegativeReals)
    m.T4_conv = pe.Constraint(m.T4_I, rule=lambda m, i: sum(m.T4_lam[i, j] for j in range(len(modos[i].pontos)))
                              == m.T4_s[i])
    for d, b in enumerate(bats):
        m.add_component(f"T4_E_{_n(b)}", pe.Constraint(expr=m.e[b, N] == sum(
            modos[i].pontos[j].energias_kWh[d] * m.T4_lam[i, j] for (i, j) in pts)))
    return sum(modos[i].pontos[j].valor_R * m.T4_lam[i, j] for (i, j) in pts)


def _n(uid: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in uid)


__all__ = ["ModeloConstruido3C4", "construir_modelo_3c4"]
