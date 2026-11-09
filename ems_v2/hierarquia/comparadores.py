"""Comparadores científicos do Piso 3C-4 — separação dos efeitos e tratamento EXPLÍCITO das condições terminais.

Só biblioteca padrão. Três efeitos distintos (FORMULACAO_3C4 §12), cada um medido entre estratégias que diferem num
ÚNICO fator, com estado inicial, microrrede, verdade, tarifas de liquidação, PCC, serviço, horizonte de avaliação K_M,
regras de custo e aceitação IDÊNTICOS:

* **reotimização** = custo(open-loop, N = m = K_M) − custo(MPC encolhido, N = K_M, m) — mesma informação de horizonte,
  difere só a realimentação;
* **antecipação** = custo(MPC sem sinal, N, m) − custo(hierárquico, N, m, H_L) — mesma política de reotimização e
  mesmo N; difere só a informação terminal de longo prazo;
* **informação perfeita** = custo(estratégia) − custo(oráculo) — o oráculo é ablação ROTULADA (não causal).

Superioridade econômica só é afirmada quando as condições terminais são COMPARÁVEIS (energia final, estados ON/OFF e
obrigações pendentes iguais, missões concluídas). Caso contrário o comparador reporta o custo ajustado por uma
VALORAÇÃO TERMINAL DECLARADA [R$/kWh] numa faixa de preços (análise de sensibilidade) e só declara robusta uma ordenação
que não muda em toda a faixa — nunca a partir do custo acumulado observado sozinho.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

TOL_E = 1e-6


@dataclass(frozen=True)
class LinhaEstrategia:
    estrategia: str
    causal: bool
    situacao: str
    classe_falha: str | None
    intervalos_aplicados: int
    intervalos_missao: int
    custo_realizado_R: float | None
    energias_finais_kWh: dict[str, float]
    geradores_finais: dict[str, bool]
    obrigacoes_pendentes_s: dict[str, int]
    janelas: int
    janelas_degradadas: int
    avaliacoes_planejador: int
    tempo_decisao_s: float | None
    tempo_planejador_s: float | None
    custo_futuro_inicial_R: float | None = None      # V̂ da 1ª janela (instrumento de decisão; nunca custo)

    @property
    def concluida(self) -> bool:
        return self.situacao == "encerrada" and self.intervalos_aplicados == self.intervalos_missao


def resumo(x) -> LinhaEstrategia:
    r = x.resultado
    rm = r.registro_missao
    ctrl = x.controlador
    est = ctrl.estado
    cont = rm.conteudo if rm is not None else None
    coords = getattr(r, "coordenacoes", ()) or ()
    obr, _ = ctrl.obrigacoes_pendentes()
    tm = getattr(rm, "tempos_s", None) if rm is not None else None
    from .mpc import tempos_planejador_de
    tp = tempos_planejador_de(coords)
    v0 = coords[0].decomposicao.custo_futuro_estimado_R if coords and coords[0].decomposicao else None
    return LinhaEstrategia(
        x.estrategia, x.estrategia != "oraculo", r.situacao, r.classe_falha,
        cont.intervalos_aplicados if cont else 0, ctrl.cfg.malha.intervalos_missao,
        cont.custo_realizado_acumulado.total_R if cont else None,
        {b.uid: float(b.energia_kWh) for b in est.armazenamento}, {g.uid: bool(g.ligado) for g in est.geracao},
        dict(obr), len(r.registros), sum(1 for c in coords if c.situacao.startswith("degradado")),
        sum(c.avaliacoes_planejador for c in coords),
        math.fsum((tm or {}).values()) if tm else None, tp.get("total_s"), v0)


def terminais_iguais(a: LinhaEstrategia, b: LinhaEstrategia) -> bool:
    return (set(a.energias_finais_kWh) == set(b.energias_finais_kWh)
            and all(abs(a.energias_finais_kWh[u] - b.energias_finais_kWh[u]) <= TOL_E for u in a.energias_finais_kWh)
            and a.geradores_finais == b.geradores_finais and not a.obrigacoes_pendentes_s
            and not b.obrigacoes_pendentes_s)


@dataclass(frozen=True)
class Efeito:
    nome: str
    estrategia_a: str
    estrategia_b: str
    diferenca_R: float | None                         # custo(a) − custo(b): > 0 ⇒ b mais barata
    comparavel: bool
    motivo: str
    ajustado_por_preco: dict[str, float] = field(default_factory=dict)   # preço [R$/kWh] → diferença ajustada
    ordenacao_robusta: bool | None = None


def efeito(nome: str, a: LinhaEstrategia | None, b: LinhaEstrategia | None, precos=(0.0, 0.5, 1.0, 1.5, 2.0)) -> Efeito:
    if a is None or b is None:
        return Efeito(nome, getattr(a, "estrategia", "?"), getattr(b, "estrategia", "?"), None, False,
                      "estratégia ausente")
    if not (a.concluida and b.concluida):
        return Efeito(nome, a.estrategia, b.estrategia, None, False,
                      f"missão não concluída ({a.estrategia}: {a.situacao}/{a.classe_falha}; {b.estrategia}: "
                      f"{b.situacao}/{b.classe_falha}): custos acumulados NÃO comparáveis")
    d = a.custo_realizado_R - b.custo_realizado_R
    if terminais_iguais(a, b):
        return Efeito(nome, a.estrategia, b.estrategia, d, True, "condições terminais iguais (energia, ON/OFF, "
                                                                 "obrigações): diferença de custo comparável")
    dE = math.fsum(a.energias_finais_kWh.values()) - math.fsum(b.energias_finais_kWh.values())
    aj = {f"{p:g}": d + p * dE for p in precos}              # custo − p·E_final ⇒ (Ca − pEa) − (Cb − pEb)
    sinais = {(v > 1e-9) - (v < -1e-9) for v in aj.values()}
    ger = a.geradores_finais != b.geradores_finais or a.obrigacoes_pendentes_s or b.obrigacoes_pendentes_s
    return Efeito(nome, a.estrategia, b.estrategia, d, False,
                  "condições terminais DIFERENTES: diferença ajustada por valoração terminal declarada (faixa de "
                  "preços)" + ("; estados ON/OFF/obrigações diferentes (não valorados)" if ger else ""), aj,
                  len(sinais) == 1 and not ger)


def comparar(execucoes: dict, *, precos=(0.0, 0.5, 1.0, 1.5, 2.0)) -> dict:
    linhas = {k: resumo(x) for k, x in execucoes.items()}
    g = linhas.get
    hier = next((k for k in ("hier_pwl", "hier_local", "hier_ref_dura", "hier_ref_branda") if k in linhas), None)
    efs = [efeito("reotimizacao", g("open_loop"), g("mpc_encolhido"), precos),
           efeito("antecipacao", g("mpc_sem_sinal"), g(hier) if hier else None, precos)]
    for k in ("hier_local", "hier_ref_dura", "hier_ref_branda"):
        if k in linhas and "hier_pwl" in linhas:
            efs.append(efeito(f"metodo_{k}_vs_pwl", g(k), g("hier_pwl"), precos))
    if "oraculo" in linhas:
        for k in linhas:
            if k != "oraculo":
                efs.append(efeito(f"informacao_perfeita_{k}", g(k), g("oraculo"), precos))
    return {"linhas": linhas, "efeitos": {e.nome: e for e in efs},
            "nota": "Oráculo = ablação rotulada (informação perfeita), nunca controlador causal. Uma instância "
                    "sintética não estabelece superioridade geral."}


__all__ = ["Efeito", "LinhaEstrategia", "comparar", "efeito", "resumo", "terminais_iguais"]
