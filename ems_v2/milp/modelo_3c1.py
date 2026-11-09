"""Construção do MILP Pyomo do perfil ``v1.1-3C-1`` (commitment dinâmico de UMA janela).

Reutiliza INTEGRALMENTE o construtor 3B-P (``modelo.construir_modelo``) para o núcleo contínuo/econômico (M02–M08,
M10, M14–M16 e termos 3B-P) e, sobre o mesmo modelo, LIBERA ``u`` e acrescenta (ver ``docs/ems_v2/FORMULACAO_3C1.md``):

* M09   ``u_{i,t} − u_{i,t−1} = y_{i,t} − z_{i,t}`` (``u_{i,−1}`` declarado); ``y + z <= 1``; ``u <= a``;
* M11a  ``p_{i,t} − p_{i,t−1} <= R⁺Δ·u_{i,t−1} + S⁺·y_{i,t}``;
* M11b  ``p_{i,t−1} − p_{i,t} <= R⁻Δ·u_{i,t} + S⁻·z_{i,t}`` (``p_{i,−1}`` declarado; no t = 0 os termos com
  ``u_{−1}``/``p_{−1}`` são constantes);
* M11-REP transições não representáveis (S < mínimo ON, ou abstração ``transicoes_bloqueadas``): ``y = 0`` / ``z = 0``;
* M12   ``Σ_{j=max(0,t−U+1)}^{t} y_j <= u_t``; ``Σ_{j=max(0,t−D+1)}^{t} z_j <= 1 − u_t``; obrigação herdada
  ``u_t = u_{−1}`` para ``t < min(r, N)``;
* M12-TERM (só política ``cumprir_na_janela``): ``y_t = 0`` se ``t + U > N``; ``z_t = 0`` se ``t + D > N``;
* compromisso parcial: ``u_t = valor`` nos intervalos fixados;
* objetivo: termos 3B-P + combustível de evento ``c_H (m^SU y + m^SD z)`` (PEMFC com transições, B05) + termo
  ``eventos`` ``Σ C_SU y + C_SD z`` (R$/evento, SEM h) quando declarado.

Todos os coeficientes vêm de parâmetros físicos/econômicos DECLARADOS (nenhum Big-M): R⁺Δ, R⁻Δ, S⁺, S⁻ e as cotas
M10. Modelo linear (grau <= 1) e sem SOS.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pyomo.environ as pe

from ..compromisso.contrato import DiscretizacaoUnidade, EntradaCommitment3C1, discretizar, disponibilidade
from .modelo import ModeloConstruido, construir_modelo


@dataclass
class ModeloConstruido3C1:
    base: ModeloConstruido
    discretizacao: dict[str, DiscretizacaoUnidade]
    termos: tuple[str, ...] = ()
    expr_termos: dict = field(default_factory=dict)
    transicoes_bloqueadas: tuple[str, ...] = ()

    @property
    def modelo(self) -> pe.ConcreteModel:
        return self.base.modelo


def construir_modelo_3c1(e: EntradaCommitment3C1, compromisso_parcial: dict | None = None) -> ModeloConstruido3C1:
    """Supõe entrada validada (``preflight_3c1`` sem bloqueios)."""
    b = e.base
    N = b.malha.N
    G = [str(g.uid) for g in b.geradores]
    mcb = construir_modelo(b, {g: tuple([0] * N) for g in G})     # u provisoriamente fixado; liberado abaixo
    m = mcb.modelo
    m.name = "seeds2_milp_3c1"
    for g in G:
        for t in range(N):
            m.u[g, t].unfix()
            m.u[g, t].set_value(None, skip_validation=True)
    disc = discretizar(e)
    gesp = {str(g.uid): g for g in b.geradores}
    a = {g: disponibilidade(gesp[g], b.malha) for g in G}
    m.y = pe.Var(m.G, m.T, domain=pe.Binary)
    m.z = pe.Var(m.G, m.T, domain=pe.Binary)

    def u_ant(g, t):
        return disc[g].u_anterior if t == 0 else m.u[g, t - 1]

    def p_ant(g, t):
        return disc[g].p_anterior_kW if t == 0 else m.p[g, t - 1]

    m.M09 = pe.Constraint(m.G, m.T, rule=lambda m, g, t: m.u[g, t] - u_ant(g, t) == m.y[g, t] - m.z[g, t])
    m.M09ex = pe.Constraint(m.G, m.T, rule=lambda m, g, t: m.y[g, t] + m.z[g, t] <= 1)
    m.M09a = pe.Constraint(m.G, m.T, rule=lambda m, g, t: m.u[g, t] <= a[g][t])

    def m11a(m, g, t):
        dz = disc[g]
        if dz.rampa_subida_kW is None:      # só unidade OFF sem partida representável (validação): p ≡ 0 por M10
            return pe.Constraint.Skip
        lim = dz.rampa_subida_kW * u_ant(g, t) + ((dz.limite_partida_kW or 0.0) * m.y[g, t])
        return m.p[g, t] - p_ant(g, t) <= lim

    def m11b(m, g, t):
        dz = disc[g]
        if dz.rampa_descida_kW is None:
            return pe.Constraint.Skip
        return p_ant(g, t) - m.p[g, t] <= dz.rampa_descida_kW * m.u[g, t] + (dz.limite_parada_kW or 0.0) * m.z[g, t]
    m.M11a = pe.Constraint(m.G, m.T, rule=m11a)
    m.M11b = pe.Constraint(m.G, m.T, rule=m11b)
    bloq: list[str] = []
    for g in G:
        if not disc[g].partida_representavel:
            bloq.append(f"{g}:partida")
        if not disc[g].parada_representavel:
            bloq.append(f"{g}:parada")
    m.M11rep_y = pe.Constraint(m.G, m.T, rule=lambda m, g, t: m.y[g, t] == 0 if not disc[g].partida_representavel
                               else pe.Constraint.Skip)
    m.M11rep_z = pe.Constraint(m.G, m.T, rule=lambda m, g, t: m.z[g, t] == 0 if not disc[g].parada_representavel
                               else pe.Constraint.Skip)

    def m12on(m, g, t):
        U = disc[g].U or 0
        if U <= 0:
            return pe.Constraint.Skip
        return sum(m.y[g, j] for j in range(max(0, t - U + 1), t + 1)) <= m.u[g, t]

    def m12off(m, g, t):
        D = disc[g].D or 0
        if D <= 0:
            return pe.Constraint.Skip
        return sum(m.z[g, j] for j in range(max(0, t - D + 1), t + 1)) <= 1 - m.u[g, t]
    m.M12on = pe.Constraint(m.G, m.T, rule=m12on)
    m.M12off = pe.Constraint(m.G, m.T, rule=m12off)
    m.M12ini = pe.Constraint(m.G, m.T, rule=lambda m, g, t: m.u[g, t] == disc[g].u_anterior
                             if t < disc[g].intervalos_forcados else pe.Constraint.Skip)
    cumprir = e.politica_permanencia.tipo == "cumprir_na_janela"

    def m12term_y(m, g, t):
        U = disc[g].U or 0
        return m.y[g, t] == 0 if cumprir and U > 0 and t + U > N else pe.Constraint.Skip

    def m12term_z(m, g, t):
        D = disc[g].D or 0
        return m.z[g, t] == 0 if cumprir and D > 0 and t + D > N else pe.Constraint.Skip
    m.M12term_y = pe.Constraint(m.G, m.T, rule=m12term_y)
    m.M12term_z = pe.Constraint(m.G, m.T, rule=m12term_z)
    cp = compromisso_parcial or {}
    m.M09fix = pe.Constraint(m.G, m.T, rule=lambda m, g, t: m.u[g, t] == cp[g][t]
                             if g in cp and cp[g][t] is not None else pe.Constraint.Skip)

    # ---------------------------------------------------------------- objetivo
    termos = set(e.termos)
    expr = dict(mcb.expr_termos)
    if "combustivel_h2" in termos:
        extra = 0
        for g in G:
            sp = e.unidade(g)
            if gesp[g].tecnologia == "pemfc" and sp.massa_h2_partida_kg is not None:
                cH = float(gesp[g].preco_h2.valor)
                extra = extra + cH * sum(float(sp.massa_h2_partida_kg.valor) * m.y[g, t]
                                         + float(sp.massa_h2_parada_kg.valor) * m.z[g, t] for t in range(N))
        expr["combustivel_h2"] = expr["combustivel_h2"] + extra
    if "eventos" in termos:
        ev = 0
        for g in G:
            sp = e.unidade(g)
            if sp.custo_partida is not None and sp.custo_parada is not None:
                ev = ev + sum(float(sp.custo_partida.valor) * m.y[g, t] + float(sp.custo_parada.valor) * m.z[g, t]
                              for t in range(N))
        expr["eventos"] = ev
    m.del_component(m.J)
    m.J = pe.Objective(expr=sum(expr[t] for t in e.termos) if e.termos else 0, sense=pe.minimize)
    return ModeloConstruido3C1(mcb, disc, tuple(e.termos), expr, tuple(bloq))


__all__ = ["ModeloConstruido3C1", "construir_modelo_3c1"]
