"""Construção do MILP Pyomo do perfil ``v1.1-3C-3`` (PCC + intercâmbio econômico) — UMA janela.

COMPOSIÇÃO sobre o construtor 3C-1 (``modelo_3c1.construir_modelo_3c1``, inalterado), que por sua vez reutiliza o
construtor 3B-P: todo o núcleo (M03–M12, M14–M16 e os termos 3B-P/3C-1) é EXATAMENTE o do 3C-1. No modo
``conectado`` acrescentam-se (ver ``docs/ems_v2/FORMULACAO_3C3.md``):

* ``P_imp_t, P_exp_t >= 0`` [kW];
* PCC1  ``P_imp_t <= a_t P̄_imp_t (w_t)``, ``P_exp_t <= a_t P̄_exp_t (1 − w_t)`` — ``w_t`` binária SÓ quando os dois
  sentidos são permitidos (exclusividade MILP; coeficientes = limites CONTRATADOS declarados × disponibilidade, nunca
  um Big-M arbitrário); sentido proibido ⇒ variável fixada em 0;
* M02-3C3  ``Σ P_R + Σ (P_d − P_c) + Σ p + P_imp_t = Σ L − Σ ℓ + d + P_exp_t`` — SUBSTITUI o M02 do 3C-1. Construída a
  partir dos componentes do modelo e VERIFICADA termo a termo contra o corpo do M02 original
  (``_verificar_extensao_m02``): sem o PCC as duas equações são idênticas (mesmos coeficientes e constante);
* objetivo ``J = J_3C-1 + h Σ c_imp P_imp − h Σ c_exp P_exp`` (só os termos de rede declarados).

No modo ``isolado_declarado`` NADA é acrescentado: o modelo é o do 3C-1 (mesmo M02, mesmo objetivo).
Modelo linear (grau <= 1), sem SOS, sem variáveis de folga no balanço.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pyomo.environ as pe
from pyomo.core.expr import identify_variables
from pyomo.repn import generate_standard_repn

from ..rede.contrato import EntradaRede3C3, series_pcc
from ..series import alinhar_a_malha
from .modelo_3c1 import ModeloConstruido3C1, construir_modelo_3c1


class ExtensaoM02Incoerente(RuntimeError):
    """Invariante de construção: a M02-3C3 sem o PCC não coincide com o M02 do núcleo (nunca deveria ocorrer)."""


@dataclass
class ModeloConstruido3C3:
    nucleo: ModeloConstruido3C1
    conectado: bool
    dois_sentidos: bool = False
    termos: tuple[str, ...] = ()
    expr_termos: dict = field(default_factory=dict)
    series: dict = field(default_factory=dict)

    @property
    def modelo(self) -> pe.ConcreteModel:
        return self.nucleo.modelo

    @property
    def base(self):
        return self.nucleo.base

    @property
    def transicoes_bloqueadas(self):
        return self.nucleo.transicoes_bloqueadas

    @property
    def discretizacao(self):
        return self.nucleo.discretizacao


def _repn(expr):
    r = generate_standard_repn(expr, compute_values=False)
    lin = {}
    for v, c in zip(r.linear_vars, r.linear_coefs):
        lin[id(v)] = lin.get(id(v), 0.0) + float(pe.value(c))
    return {k: round(v, 12) for k, v in lin.items() if v != 0.0}, round(float(pe.value(r.constant)), 9), r.is_linear()


def _verificar_extensao_m02(m, t: int, sem_pcc) -> None:
    """Sem o PCC, a expressão reconstruída deve ser IDÊNTICA a (corpo − limite) do M02 do núcleo."""
    if t not in m.M02:
        livres = [] if isinstance(sem_pcc, (int, float)) else [v for v in identify_variables(sem_pcc) if not v.fixed]
        if livres:
            raise ExtensaoM02Incoerente(f"M02[{t}] ausente no núcleo, mas a reconstrução tem variáveis livres.")
        return
    c = m.M02[t]
    orig = c.body - c.upper
    a, b = _repn(orig), _repn(sem_pcc)
    if a != b:
        raise ExtensaoM02Incoerente(f"M02-3C3[{t}] sem o PCC ≠ M02 do núcleo: {a} × {b}.")


def construir_modelo_3c3(e: EntradaRede3C3, compromisso_parcial: dict | None = None) -> ModeloConstruido3C3:
    """Supõe entrada validada (``preflight_3c3`` sem bloqueios)."""
    nuc = construir_modelo_3c1(e.compromisso, compromisso_parcial)
    m = nuc.modelo
    termos = tuple(e.termos)
    expr = dict(nuc.expr_termos)
    if not e.conectado:
        m.name = "seeds2_milp_3c3_isolado"
        return ModeloConstruido3C3(nuc, False, False, termos, expr, {})
    m.name = "seeds2_milp_3c3"
    b, mcb = e.base, nuc.base
    N, h = mcb.N, mcb.h
    sp = series_pcc(e)
    dois = e.importa and e.exporta
    m.P_imp = pe.Var(m.T, domain=pe.NonNegativeReals)
    m.P_exp = pe.Var(m.T, domain=pe.NonNegativeReals)
    if dois:
        m.w_pcc = pe.Var(m.T, domain=pe.Binary)
        m.PCC1_imp = pe.Constraint(m.T, rule=lambda m, t: m.P_imp[t] <= sp["a"][t] * sp["imp_max"][t] * m.w_pcc[t])
        m.PCC1_exp = pe.Constraint(m.T, rule=lambda m, t: m.P_exp[t] <= sp["a"][t] * sp["exp_max"][t] * (1 - m.w_pcc[t]))
    else:
        for t in range(N):
            if not e.importa:
                m.P_imp[t].fix(0.0)
            if not e.exporta:
                m.P_exp[t].fix(0.0)
        m.PCC1_imp = pe.Constraint(m.T, rule=lambda m, t: m.P_imp[t] <= sp["a"][t] * sp["imp_max"][t]
                                   if e.importa else pe.Constraint.Skip)
        m.PCC1_exp = pe.Constraint(m.T, rule=lambda m, t: m.P_exp[t] <= sp["a"][t] * sp["exp_max"][t]
                                   if e.exporta else pe.Constraint.Skip)
    # ------------------------------------------------ M02-3C3 (reconstruída dos componentes e verificada)
    L = {str(d.uid): list(alinhar_a_malha(d.potencia, b.malha, "")[0]) for d in b.demandas}

    def lado_sem_pcc(t):
        gen = sum(m.P_R[r, t] for r in mcb.renovaveis) + sum(m.P_d[x, t] - m.P_c[x, t] for x in mcb.baterias) \
            + sum(m.p[g, t] for g in mcb.geradores)
        cons = sum(L[k][t] for k in L) - sum(m.ell[l, t] for l in mcb.demandas_autorizadas)
        if mcb.com_descarte:
            cons = cons + m.d[t]
        return gen - cons
    for t in range(N):
        _verificar_extensao_m02(m, t, lado_sem_pcc(t))
    if hasattr(m, "M02"):
        m.M02.deactivate()
    m.M02_3c3 = pe.Constraint(m.T, rule=lambda m, t: lado_sem_pcc(t) + m.P_imp[t] - m.P_exp[t] == 0)
    mcb.balanco_trivial_inviavel = []      # com o PCC nenhum intervalo é "sem decisão"
    # ------------------------------------------------ objetivo
    if "importacao_rede" in e.economia.termos:
        expr["importacao_rede"] = h * sum(sp["c_imp"][t] * m.P_imp[t] for t in range(N))
    if "exportacao_rede" in e.economia.termos:
        expr["exportacao_rede"] = -h * sum(sp["c_exp"][t] * m.P_exp[t] for t in range(N))
    m.del_component(m.J)
    m.J = pe.Objective(expr=sum(expr[x] for x in termos) if termos else 0, sense=pe.minimize)
    return ModeloConstruido3C3(nuc, True, dois, termos, expr, sp)


__all__ = ["ExtensaoM02Incoerente", "ModeloConstruido3C3", "construir_modelo_3c3"]
