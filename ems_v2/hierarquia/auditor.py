"""Auditor algébrico INDEPENDENTE do termo terminal 3C-4 — sem Pyomo/HiGHS.

Composição explícita (nada do 3C-3 é desativado):

1. ``rede.auditor.auditar_3c3`` (inalterado) audita o núcleo inteiro — física, commitment, PCC, custos 3C-3 — com os
   custos 3C-3 reportados (o termo terminal NÃO entra no total 3C-3);
2. ``auditar_terminal_3c4`` (este módulo) verifica, a partir SÓ do despacho candidato e da entrada:

   * a energia terminal ``E_b(N)`` de cada banco (trajetória ``e`` do candidato);
   * a memória terminal dos geradores recalculada (``compromisso.memoria.memoria_terminal``: ligado, obrigação
     residual, potência do último intervalo) e o MODO do sinal compatível com ela — exatamente um; zero ⇒
     ``estado_terminal_fora_dos_modos`` (memória incompatível nunca é aceita);
   * o domínio de validade do modo (``estado_terminal_fora_do_dominio``);
   * o valor V̂ recalculado pela avaliação exata ``valor.avaliar_modo`` (interpolante 1D, envoltória 2D por
     enumeração, linear local) e comparado ao termo reportado pelo modelo (tolerância de custo D07);
   * referências (dura: E >= E_ref; branda: ρ max(0, E_ref − E)) e termos declarados (linear, energia mínima);
   * integralidade da seleção de modo/segmento reportada;
   * total do objetivo = total 3C-3 RECONSTRUÍDO + termo terminal recalculado;
   * vínculo: o sinal da entrada tem selo válido (o hash da entrada 3C-4 o compromete).

"optimal" do HiGHS nunca basta: um termo terminal alterado depois do solver é rejeitado (H16).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..audit import Tolerancias, _tol_custo
from ..compromisso.memoria import memoria_terminal
from ..diagnostics import Constatacao, erro
from .contrato import EntradaHierarquica3C4, modo_condicionado, sinal_selado, validar_entrada_3c4
from .valor import avaliar_modo, modos_compativeis, penalidade_branda, valor_termo_declarado

CHAVES_TERMINAIS = {"custo_futuro_estimado": "V̂ do sinal do planejador (instrumento de decisão) [R$]",
                    "valor_residual_declarado": "Φ declarado linear (−Σ λ E) [R$]"}


@dataclass(frozen=True)
class CandidatoTerminal3C4:
    """Despacho candidato (núcleo) + o que o modelo reportou sobre o termo terminal."""
    baterias: dict                      # uid → {"e": N+1, ...}
    geradores: dict                     # uid → {"u": N, "p": N, ...}
    termo_reportado: dict[str, float]   # chave terminal → valor (vazio se não há termo de custo)
    total_reportado: float | None       # objetivo total reportado (3C-3 + terminal)
    selecao: dict = field(default_factory=dict)   # "s": (…), "segmentos": (…) — integralidade


@dataclass(frozen=True)
class RelatorioTerminal3C4:
    aceito: bool
    constatacoes: tuple[Constatacao, ...]
    tipo: str
    chave: str | None
    valor_recalculado_R: float | None
    energias_terminais_kWh: dict[str, float]
    estado_terminal: dict[str, tuple]
    modo: int | None
    total_recalculado_R: float | None


def chave_terminal(e: EntradaHierarquica3C4) -> str | None:
    t = e.terminal
    if t.tipo == "valor_linear_declarado":
        return "valor_residual_declarado"
    if t.tipo == "sinal_valor_futuro" and t.sinal is not None and t.sinal.tipo != "referencia_energia_dura":
        return "custo_futuro_estimado"
    return None


def _finito(x) -> bool:
    return type(x) in (int, float) and math.isfinite(x)


def auditar_terminal_3c4(e: EntradaHierarquica3C4, cand: CandidatoTerminal3C4, total_3c3_reconstruido: float | None,
                         tol: Tolerancias = Tolerancias()) -> RelatorioTerminal3C4:
    c: list[Constatacao] = []
    rel = validar_entrada_3c4(e)
    tipo = getattr(getattr(e, "terminal", None), "tipo", "?")
    if not rel.aceito:
        return RelatorioTerminal3C4(False, tuple(rel.bloqueantes()), tipo, None, None, {}, {}, None, None)
    b = e.base
    N = b.malha.N
    t = e.terminal
    s = t.sinal
    chave = chave_terminal(e)
    E: dict[str, float] = {}
    for x in b.baterias:
        u = str(x.uid)
        tr = (cand.baterias.get(u) or {}).get("e")
        if tr is None or len(tr) != N + 1 or not _finito(tr[N]):
            c.append(erro("energia_terminal_ausente", f"terminal.baterias[{u}]", "Trajetória e(N) ausente/não finita."))
        else:
            E[u] = float(tr[N])
    est: dict[str, tuple] = {}
    if b.geradores:
        try:
            uu = {g: [1 if float(v) > 0.5 else 0 for v in cand.geradores[g]["u"]] for g in cand.geradores}
            pp = {g: [float(v) for v in cand.geradores[g]["p"]] for g in cand.geradores}
            for mf in memoria_terminal(e.compromisso, uu, pp):
                est[mf.uid] = (mf.ligado, mf.obrigacao_residual_s, mf.potencia_kW)
        except (KeyError, TypeError, ValueError) as exc:
            c.append(erro("memoria_terminal_nao_reconstruivel", "terminal.geradores", f"{type(exc).__name__}: {exc}"))
    for k in cand.termo_reportado:
        if k != chave:
            c.append(erro("termo_terminal_inesperado", f"terminal.reportado[{k}]",
                          f"Termo {k!r} reportado; a entrada declara {chave!r}."))
    if chave is not None and chave not in cand.termo_reportado:
        c.append(erro("termo_terminal_ausente", f"terminal.reportado[{chave}]", "Termo declarado não reportado."))
    for nome, vals in (cand.selecao or {}).items():
        for i, v in enumerate(vals):
            if not _finito(v) or min(abs(v), abs(v - 1.0)) > tol.binario:
                c.append(erro("selecao_terminal_nao_inteira", f"terminal.selecao.{nome}[{i}]", f"{v!r}."))
    val, modo = None, None
    if len(E) == len(b.baterias) and not c:
        bats = tuple(sorted(E)) if s is None else s.baterias
        en = tuple(E[u] for u in bats)
        if t.tipo in ("nenhum_declarado", "valor_linear_declarado", "energia_minima_declarada"):
            val = valor_termo_declarado(t, E)
            if val is None:
                c.append(erro("energia_minima_violada", "terminal", f"E(N) = {E} < Ē declarada."))
        elif s.tipo == "referencia_energia_dura":
            val = 0.0
            for u, r, x in zip(bats, s.referencia.energias_kWh, en):
                if x < r - (tol.energia_abs_kWh + 1e-6 * max(1.0, abs(r))):
                    c.append(erro("referencia_terminal_violada", f"terminal[{u}]", f"E(N) = {x} < E_ref = {r}."))
        elif s.tipo == "referencia_energia_branda":
            val = penalidade_branda(s, en)
        else:
            if not sinal_selado(s):
                c.append(erro("sinal_adulterado", "terminal.sinal", "Selo do sinal não confere."))
            comp = modos_compativeis(s, est) if modo_condicionado(s) else [m.indice for m in s.modos]
            if len(comp) != 1:
                c.append(erro("estado_terminal_fora_dos_modos", "terminal",
                              f"Estado terminal {est} compatível com {len(comp)} modos do sinal (exigido 1): memória/"
                              "commitment terminal incompatível com o valor de continuação."))
            else:
                modo = comp[0]
                rep_s = (cand.selecao or {}).get("s")
                if rep_s is not None and len(rep_s) == len(s.modos) and max(range(len(rep_s)),
                                                                             key=lambda i: rep_s[i]) != modo:
                    c.append(erro("modo_reportado_divergente", "terminal.selecao.s",
                                  f"Modo selecionado pelo modelo ≠ modo compatível {modo}."))
                val = avaliar_modo(s, s.modos[modo], en, 1e-6)
                if val is None:
                    c.append(erro("estado_terminal_fora_do_dominio", "terminal",
                                  f"E(N) = {dict(zip(bats, en))} fora do domínio de validade do modo {modo}."))
    if val is not None and chave is not None and chave in cand.termo_reportado:
        r = cand.termo_reportado[chave]
        if not _finito(r) or abs(r - val) > _tol_custo(tol, val):
            c.append(erro("termo_terminal_divergente", f"terminal.reportado[{chave}]",
                          f"Reportado {r!r} ≠ recalculado {val!r}."))
    tot = None
    if val is not None and total_3c3_reconstruido is not None:
        tot = math.fsum([total_3c3_reconstruido, val if chave is not None else 0.0])
        if cand.total_reportado is None or not _finito(cand.total_reportado) or abs(
                cand.total_reportado - tot) > _tol_custo(tol, tot):
            c.append(erro("objetivo_total_divergente", "terminal.total",
                          f"Total reportado {cand.total_reportado!r} ≠ 3C-3 reconstruído + terminal = {tot!r}."))
    elif val is not None and total_3c3_reconstruido is None:
        c.append(erro("total_3c3_nao_reconstruido", "terminal.total", "Total 3C-3 não reconstruído pelo auditor."))
    return RelatorioTerminal3C4(not c, tuple(c), tipo, chave, val, E, est, modo, tot)


__all__ = ["CHAVES_TERMINAIS", "CandidatoTerminal3C4", "RelatorioTerminal3C4", "auditar_terminal_3c4",
           "chave_terminal"]
