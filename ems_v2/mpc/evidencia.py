"""Gera a evidência reproduzível do Piso 3C-2 (MPC recedente sobre as fixtures sintéticas, Pyomo + HiGHS).

Uso: python -m ems_v2.mpc.evidencia [saida.md] [repeticoes]   (a partir da raiz do repositório)

Executa E1–E8, audita cada missão com a auditoria INDEPENDENTE, compara E3/E4 em condições comparáveis e mede uma
campanha de tempos de resolução (n declarado; percentil de posto mais próximo). Os imports do solver são tardios
(importar este módulo não carrega Pyomo). Sintético/algébrico: não é validação física nem prova de tempo real.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _f(x, nd=6):
    if x is None:
        return "—"
    return f"{x:.{nd}g}" if isinstance(x, float) else str(x)


def main(saida: str | None = None, rep: int = 5) -> str:
    from .. import fixtures_3c2 as F
    from ..milp.ambiente import verificar_ambiente
    from ..ponte.instrumentacao import estatisticas
    from . import experimentos as X
    from .auditoria import auditar_missao, verificar_nao_antecipatividade
    from .comparadores import comparar_missoes
    from .metricas import metricas_missao
    from .orquestrador import ambiente_execucao

    amb = verificar_ambiente()
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    ae = ambiente_execucao()
    L = ["# Evidência executada — Piso 3C-2 (gerada por `python -m ems_v2.mpc.evidencia`)", "",
         f"- Data (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')} · commit: `{sha}`",
         f"- Python {ae['python']} · {ae['plataforma']} · {ae['cpus']} CPUs · {ae['processador']}",
         f"- Pyomo {amb['versoes'].get('pyomo')} · highspy {amb['versoes'].get('highspy')} · HiGHS {amb['versao_highs']} "
         f"· interface `{amb['interface']}` · configuração `CONFIG_ANALITICA` (gaps nulos, 1 thread, semente 0)",
         "", "Simulação causal de laço fechado **ALGÉBRICA** (planta = dublê 3C-1) sobre fixtures sintéticas — **não é "
         "validação física** nem afirmação de desempenho de tempo real.", ""]

    def linha(nome, ex, nota=""):
        r = ex.resultado
        rm = r.registro_missao
        rel = auditar_missao(rm, r.registros, r.livro, ex.modelo, verdade=ex.verdade)
        m = metricas_missao(r, ex.modelo)
        return (f"| {nome} | {r.configuracao.malha.intervalos_otimizacao}/{r.configuracao.malha.intervalos_reotimizacao} "
                f"| `{rm.conteudo.desfecho}` | {r.classe_falha or '—'} | {len(r.registros)} | "
                f"{rm.conteudo.intervalos_aplicados} | {_f(rm.conteudo.custo_realizado_acumulado.total_R)} | "
                f"{_f(m.operacao.get(f'E_final_kWh[{F.BESS}]'))} | {rm.conteudo.obrigacoes_pendentes_fim_s or '—'} | "
                f"{'aprovada' if rel.aceito else 'REPROVADA ' + str(sorted(c.codigo for c in rel.constatacoes if c.severidade == 'erro'))} | {nota} |")
    L += ["## 1. Experimentos E1–E8", "",
          "| Exp. | N/m | Desfecho | Classe de falha | Registros | Aplicados | Custo realizado (R$) | E_final banco (kWh) | "
          "Obrigações pendentes no fim (s) | Auditoria independente | Nota |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    e1 = X.e1_oraculo()
    L.append(linha("E1 oráculo MPC (ablação)", e1["mpc"], "previsão perfeita DECLARADA"))
    L.append(linha("E1 oráculo horizonte completo", e1["horizonte_completo"], "referência de ablação"))
    e2 = X.e2_previsao_reemitida()["mpc"]
    L.append(linha("E2 previsão reemitida", e2, "FV prevista 10 → 25 após observar o degrau"))
    e3 = X.e3_open_loop_vs_mpc()
    L.append(linha("E3 open-loop", e3["open_loop"], "uma decisão em τ_0"))
    L.append(linha("E3 MPC", e3["mpc"], "mesma informação/planta/regras"))
    e4 = X.e4_frequencia()
    for m_, ex in e4.items():
        L.append(linha(f"E4 m = {m_}", ex, f"{len(ex.resultado.registros)} resoluções"))
    e5 = X.e5_memoria()
    L.append(linha("E5 memória (T_on em 3 janelas)", e5, "u = " + str([round(p.aplicado[f'{F.FC}|u']) for x in
                                                                     e5.resultado.registros for p in x.conteudo.passos])))
    for n_, f_ in ((1, X.resultado_sem_solucao),):
        ex = X.e7_falha_na_janela(n_, f_)
        L.append(linha("E7 sem solução na janela 1", ex, f"planta parada em g = {ex.entorno.proximo_indice}"))
    for pol in ("registrar_sem_reconciliar", "interromper"):
        L.append(linha(f"E8 revisão tardia ({pol})", X.e8_revisao_tardia(pol), "revisão do FV de g = 1 após τ_2"))
    L += ["", "## 2. Comparações (sem veredito; energia final e obrigações não valoradas — 3C-4)", ""]
    for rot, (a, b, ra, rb) in {"E3 open-loop × MPC": (e3["open_loop"], e3["mpc"], "open_loop", "mpc"),
                                "E4 m = 2 × m = 1": (e4[2], e4[1], "m2", "m1"),
                                "E1 oráculo N = 8 × oráculo MPC (referência)": (e1["horizonte_completo"], e1["mpc"],
                                                                              "orac_N8", "orac_mpc")}.items():
        c = comparar_missoes(a.resultado, b.resultado, b.modelo, rotulo_a=ra, rotulo_b=rb)
        L += [f"### {rot} — comparável: {c.comparavel} ({c.tipo})", "", f"| Grandeza | {ra} | {rb} | {rb} − {ra} |",
              "|---|---|---|---|"]
        for k, v in c.linhas.items():
            if k.startswith(("custo", "E_final", "E_curt", "E_geracao", "partidas", "paradas", "resolucoes",
                             "intervalos")):
                L.append(f"| {k} | {_f(v[0])} | {_f(v[1])} | {_f(v[2])} |")
        L += ["", c.observacao, ""]
    va, vb = F.verdade(X.CASO, F.L_E2, F.PV_REAL_E2), F.verdade(X.CASO, F.L_E2, F.PV_REAL_E2[:2] + [20.0] * 6)
    ri = verificar_nao_antecipatividade(lambda v: X.executar("ev-intervencao", verdade_obj=v).resultado, va, vb, 2)
    L += ["## 3. Não antecipatividade por intervenção", "",
          f"Verdades iguais até τ_2 e diferentes depois: {ri.janelas_comparadas} decisão(ões) com k <= 2 comparadas; "
          f"divergências: {list(ri.divergencias) or 'nenhuma'} ⇒ não antecipativo: **{ri.nao_antecipativo}**.", ""]
    # ---------------------------------------------------------------- campanha de tempos
    L += ["## 4. Campanha de tempos de resolução (indicativa)", "",
          f"Cada missão executada {rep} vez(es) nesta máquina; estatísticas por PERCENTIL DE POSTO MAIS PRÓXIMO sobre "
          "TODAS as resoluções (n = tamanho da amostra). Sem caráter de garantia de tempo real.", "",
          "| Missão | K/N/m | n resoluções | Var. / bin. / restr. (máx.) | solver p50 / p95 / p99 / máx. (s) | "
          "total resolução p50 / p95 / p99 / máx. (s) |", "|---|---|---|---|---|---|"]
    cenarios = {"E2 (K = 8, N = 4, m = 2)": dict(K=8, N=4, m=2),
                "K = 32, N = 8, m = 2": dict(K=32, N=8, m=2, L=[30.0] * 32, pv_prev=[10.0] * 32,
                                             pv_real=[10.0, 10.0] + [25.0] * 30),
                "K = 32, N = 16, m = 4": dict(K=32, N=16, m=4, L=[30.0] * 32, pv_prev=[10.0] * 32,
                                              pv_real=[10.0, 10.0] + [25.0] * 30)}
    for nome, kw in cenarios.items():
        sol, tot, vs, bs, rs = [], [], [], [], []
        for i in range(rep):
            ex = X.executar(f"ev-tempo-{nome}", **kw)
            for r in ex.resultado.registros:
                sol.append(r.tempos_s.get("solver_solver_s"))
                tot.append(r.tempos_s.get("solver_total_s"))
                t = r.conteudo.resolucao.tamanho
                vs.append(t.get("variaveis", 0)), bs.append(t.get("binarias_livres", 0)), rs.append(t.get("restricoes", 0))
        es, et = estatisticas([x for x in sol if x is not None]), estatisticas([x for x in tot if x is not None])
        L.append(f"| {nome} | {kw['K']}/{kw['N']}/{kw['m']} | {es.n} | {max(vs)} / {max(bs)} / {max(rs)} | "
                 f"{es.p50:.4f} / {es.p95:.4f} / {es.p99:.4f} / {es.maximo:.4f} | "
                 f"{et.p50:.4f} / {et.p95:.4f} / {et.p99:.4f} / {et.maximo:.4f} |")
    texto = "\n".join(L) + "\n"
    if saida:
        Path(saida).write_text(texto, encoding="utf-8")
    print(texto)
    return texto


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None, int(sys.argv[2]) if len(sys.argv) > 2 else 5)
