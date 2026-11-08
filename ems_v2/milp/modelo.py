"""Construção do MILP Pyomo (formulação ``v1.1-3B-P``) a partir de ``EntradaModeloEMS`` — UMA janela.

Índices: ``T = {0..N-1}`` (intervalos; potências) e ``K = {0..N}`` (fronteiras; energia BESS). ``h = Δ/60`` [h].
Convenção: kW líquidos no barramento; injeção positiva; ``P_c >= 0`` consome; ``P_d >= 0`` injeta.

Restrições (ver ``docs/ems_v2/FORMULACAO_3BP.md``):

* M02 balanço: Σ P_R + Σ p + Σ (P_d − P_c) = Σ L − Σ ℓ (só classes autorizadas) + d (só com dispositivo). Sem
  folgas livres.
* M03-v1.1: P_R + C_oper = a·A_pot; P_R, C_oper >= 0.
* M04: 0 <= ℓ <= χ_eff·L (χ_eff = 0 para crítica ou serviço duro ⇒ ℓ não existe); 0 <= d <= D̄.
* M06: 0 <= P_c <= a·P̄^c·z; 0 <= P_d <= a·P̄^d·(1 − z); z binária (exclusividade MILP).
* M07: e_{t+1} = α e_t + h(η^c P_c − P_d/η^d); α = 1 (hipótese declarada) ou exp(−λh).
* M08: C s_min <= e_k <= C s_max (k ∈ K); e_0 = e^0. Sem recorte.
* M10: P_min u <= p <= P_max u, com u FIXADO (programa constante = estado inicial).
* M14–M16 (PEMFC com curva sintética): Σ_s δ_s = u; 0 <= θ_s <= δ_s; p = Σ[P_s δ_s + ΔP_s θ_s];
  q = Σ[Q_s δ_s + ΔQ_s θ_s] — segmentos consecutivos com binárias explícitas (sem SOS; válido para curva não
  convexa); OFF ⇒ p = q = 0; não há segmento entre (0, 0) e P_0.
* Objetivo (min, R$): h Σ_t [Σ c^curt C_oper + Σ c^thr (P_c + P_d) + Σ V ℓ + Σ c_H q] — só os termos declarados.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pyomo.environ as pe
from pyomo.core.expr import identify_variables

from ..contracts import EntradaModeloEMS
from ..series import alinhar_a_malha


@dataclass
class ModeloConstruido:
    modelo: pe.ConcreteModel
    N: int
    h: float
    renovaveis: list[str] = field(default_factory=list)
    baterias: list[str] = field(default_factory=list)
    demandas: list[str] = field(default_factory=list)
    demandas_autorizadas: list[str] = field(default_factory=list)
    geradores: list[str] = field(default_factory=list)
    geradores_pwl: list[str] = field(default_factory=list)
    com_descarte: bool = False
    balanco_trivial_inviavel: list[int] = field(default_factory=list)
    termos: tuple[str, ...] = ()
    expr_termos: dict = field(default_factory=dict)


def _al(serie, e):
    v, c = alinhar_a_malha(serie, e.malha, "")
    if v is None:
        raise ValueError(f"série não alinhável (deveria ter sido rejeitada na validação): {c}")
    return list(v)


def construir_modelo(e: EntradaModeloEMS, compromisso: dict[str, tuple[int, ...]]) -> ModeloConstruido:
    """Supõe entrada validada (``validar_entrada`` + ``preflight_3bp``)."""
    N = e.malha.N
    h = float(e.malha.h_horas)
    m = pe.ConcreteModel(name="seeds2_milp_3bp")
    m.T = pe.Set(initialize=range(N), ordered=True)
    m.K = pe.Set(initialize=range(N + 1), ordered=True)
    mc = ModeloConstruido(m, N, h, termos=tuple(e.politica_objetivo.termos))
    termos = set(e.politica_objetivo.termos)
    gen = {t: 0 for t in range(N)}       # expressão do lado de injeção
    cons = {t: 0.0 for t in range(N)}    # lado de consumo (constantes + variáveis)
    custo = {t: {} for t in range(N)}

    # ---------------------------------------------------------------- renováveis M03-v1.1
    R = [str(r.uid) for r in e.renovaveis]
    mc.renovaveis = R
    m.R = pe.Set(initialize=R, ordered=True)
    m.P_R = pe.Var(m.R, m.T, domain=pe.NonNegativeReals)
    m.C_oper = pe.Var(m.R, m.T, domain=pe.NonNegativeReals)
    A = {str(r.uid): _al(r.potencial, e) for r in e.renovaveis}
    aR = {str(r.uid): _al(r.disponibilidade.serie, e) for r in e.renovaveis}
    m.M03 = pe.Constraint(m.R, m.T, rule=lambda m, r, t: m.P_R[r, t] + m.C_oper[r, t] == aR[r][t] * A[r][t])
    ccurt = {str(r.uid): (float(r.custo_curtailment.valor) if r.custo_curtailment is not None else None)
             for r in e.renovaveis}
    for t in range(N):
        gen[t] = gen[t] + sum(m.P_R[r, t] for r in R)
        if "curtailment_operacional" in termos:
            custo[t]["curtailment_operacional"] = sum(ccurt[r] * m.C_oper[r, t] for r in R)

    # ---------------------------------------------------------------- BESS M06–M08
    B = [str(b.uid) for b in e.baterias]
    mc.baterias = B
    m.B = pe.Set(initialize=B, ordered=True)
    esp = {str(b.uid): b for b in e.baterias}
    e0 = {str(s.uid): float(s.energia_kWh.valor) for s in e.estados_baterias}
    aB = {str(b.uid): _al(b.disponibilidade.serie, e) for b in e.baterias}

    def lim_e(m, b, k):
        x = esp[b]
        C = float(x.capacidade_kWh.valor)
        return (C * float(x.soc_min.valor), C * float(x.soc_max.valor))
    m.P_c = pe.Var(m.B, m.T, domain=pe.NonNegativeReals)
    m.P_d = pe.Var(m.B, m.T, domain=pe.NonNegativeReals)
    m.z_b = pe.Var(m.B, m.T, domain=pe.Binary)
    m.e = pe.Var(m.B, m.K, bounds=lim_e)
    m.M06c = pe.Constraint(m.B, m.T, rule=lambda m, b, t: m.P_c[b, t] <= aB[b][t] * float(
        esp[b].p_carga_max_kW.valor) * m.z_b[b, t])
    m.M06d = pe.Constraint(m.B, m.T, rule=lambda m, b, t: m.P_d[b, t] <= aB[b][t] * float(
        esp[b].p_descarga_max_kW.valor) * (1 - m.z_b[b, t]))
    m.M08ini = pe.Constraint(m.B, rule=lambda m, b: m.e[b, 0] == e0[b])

    def alpha(b):
        x = esp[b]
        return 1.0 if x.hipotese_autodescarga == "nao_modelada_alpha_1" else math.exp(-float(x.autodescarga_1_h.valor) * h)
    m.M07 = pe.Constraint(m.B, m.T, rule=lambda m, b, t: m.e[b, t + 1] == alpha(b) * m.e[b, t] + h * (
        float(esp[b].eta_carga.valor) * m.P_c[b, t] - m.P_d[b, t] / float(esp[b].eta_descarga.valor)))
    for t in range(N):
        gen[t] = gen[t] + sum(m.P_d[b, t] - m.P_c[b, t] for b in B)
        if "throughput_bess" in termos:
            custo[t]["throughput_bess"] = sum(float(esp[b].custo_throughput.valor) * (m.P_c[b, t] + m.P_d[b, t])
                                              for b in B)

    # ---------------------------------------------------------------- demanda e serviço M04
    mc.demandas = [str(d.uid) for d in e.demandas]
    L = {str(d.uid): _al(d.potencia, e) for d in e.demandas}
    chi = {}
    for d in e.demandas:
        k = str(d.uid)
        if e.politica_servico.modo == "degradado" and d.criticidade == "interrompivel" and d.fracao_interrompivel:
            chi[k] = _al(d.fracao_interrompivel, e)
            if any(x > 0 for x in chi[k]):
                mc.demandas_autorizadas.append(k)
    Lint = mc.demandas_autorizadas
    m.Lint = pe.Set(initialize=Lint, ordered=True)
    m.ell = pe.Var(m.Lint, m.T, domain=pe.NonNegativeReals, bounds=lambda m, l, t: (0.0, chi[l][t] * L[l][t]))
    V = {str(d.uid): float(d.custo_energia_nao_suprida.valor) for d in e.demandas
         if d.custo_energia_nao_suprida is not None}
    for t in range(N):
        cons[t] = cons[t] + sum(L[k][t] for k in L) - sum(m.ell[l, t] for l in Lint)
        if "energia_nao_suprida" in termos:
            custo[t]["energia_nao_suprida"] = sum(V[l] * m.ell[l, t] for l in Lint)

    # ---------------------------------------------------------------- descarte M04
    desc = e.politica_servico.descarte
    if desc is not None:
        mc.com_descarte = True
        m.d = pe.Var(m.T, bounds=(0.0, float(desc.p_max_kW.valor)))
        for t in range(N):
            cons[t] = cons[t] + m.d[t]

    # ---------------------------------------------------------------- geradores M10 (+ PWL M14–M16)
    G = [str(g.uid) for g in e.geradores]
    mc.geradores = G
    m.G = pe.Set(initialize=G, ordered=True)
    gesp = {str(g.uid): g for g in e.geradores}
    m.u = pe.Var(m.G, m.T, domain=pe.Binary)
    m.p = pe.Var(m.G, m.T, domain=pe.NonNegativeReals)
    for g in G:
        for t in range(N):
            m.u[g, t].fix(int(compromisso[g][t]))                 # programa fixo explícito (sem transições)
    m.M10min = pe.Constraint(m.G, m.T, rule=lambda m, g, t: float(gesp[g].p_min_kW.valor) * m.u[g, t] <= m.p[g, t])
    m.M10max = pe.Constraint(m.G, m.T, rule=lambda m, g, t: m.p[g, t] <= float(gesp[g].p_max_kW.valor) * m.u[g, t])
    GP = [g for g in G if gesp[g].curva_h2 is not None]
    mc.geradores_pwl = GP
    seg = [(g, s) for g in GP for s in range(len(gesp[g].curva_h2.vertices) - 1)]
    m.GS = pe.Set(initialize=seg, dimen=2, ordered=True)
    m.GP = pe.Set(initialize=GP, ordered=True)
    m.delta = pe.Var(m.GS, m.T, domain=pe.Binary)
    m.theta = pe.Var(m.GS, m.T, bounds=(0.0, 1.0))
    m.q = pe.Var(m.GP, m.T, domain=pe.NonNegativeReals)
    V_ = {g: [(float(P), float(Q)) for P, Q in gesp[g].curva_h2.vertices] for g in GP}
    m.M14a = pe.Constraint(m.GP, m.T, rule=lambda m, g, t: sum(
        m.delta[g, s, t] for s in range(len(V_[g]) - 1)) == m.u[g, t])
    m.M14b = pe.Constraint(m.GS, m.T, rule=lambda m, g, s, t: m.theta[g, s, t] <= m.delta[g, s, t])
    m.M15 = pe.Constraint(m.GP, m.T, rule=lambda m, g, t: m.p[g, t] == sum(
        V_[g][s][0] * m.delta[g, s, t] + (V_[g][s + 1][0] - V_[g][s][0]) * m.theta[g, s, t]
        for s in range(len(V_[g]) - 1)))
    m.M16 = pe.Constraint(m.GP, m.T, rule=lambda m, g, t: m.q[g, t] == sum(
        V_[g][s][1] * m.delta[g, s, t] + (V_[g][s + 1][1] - V_[g][s][1]) * m.theta[g, s, t]
        for s in range(len(V_[g]) - 1)))
    cH = {str(g.uid): float(g.preco_h2.valor) for g in e.geradores if g.preco_h2 is not None}
    for t in range(N):
        gen[t] = gen[t] + sum(m.p[g, t] for g in G)
        if "combustivel_h2" in termos:
            custo[t]["combustivel_h2"] = sum(cH[g] * m.q[g, t] for g in GP if gesp[g].tecnologia == "pemfc")

    # ---------------------------------------------------------------- balanço M02 (sem folgas)
    def bal(m, t):
        lhs, rhs = gen[t], cons[t]
        livre = [v for v in identify_variables(lhs - rhs) if not v.fixed] if not isinstance(
            lhs - rhs, (int, float)) else []
        if not livre:          # nenhuma decisão no intervalo: verificação constante, sem chamar o solver
            if abs(pe.value(lhs - rhs)) > 1e-9:
                mc.balanco_trivial_inviavel.append(t)
            return pe.Constraint.Skip
        return lhs == rhs
    m.M02 = pe.Constraint(m.T, rule=bal)

    # ---------------------------------------------------------------- objetivo (R$)
    for nome in mc.termos:
        mc.expr_termos[nome] = h * sum(custo[t].get(nome, 0) for t in range(N))
    total = sum(mc.expr_termos.values()) if mc.expr_termos else 0
    m.J = pe.Objective(expr=total, sense=pe.minimize)
    return mc


__all__ = ["ModeloConstruido", "construir_modelo"]
