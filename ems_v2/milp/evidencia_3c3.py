"""Gera a evidência reproduzível do Piso 3C-3 (PCC + MPC conectado sobre fixtures sintéticas, Pyomo + HiGHS).

Uso: python -m ems_v2.milp.evidencia_3c3 [saida.md] [repeticoes]   (a partir da raiz do repositório)

G1–G4, G9, G10, G12 (estático): MILP de uma janela com valores analíticos esperados; G5–G8, G11–G13: missões MPC
conectadas auditadas pela auditoria INDEPENDENTE; G14: adulterações rejeitadas; G15: impressões E1–E8 da base;
comparação open-loop × MPC (§13) e campanha de tempos (n declarado). Sintético/algébrico: não é validação física,
fluxo AC, controle primário, fatura real nem prova de tempo real.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _f(x, nd=6):
    if x is None:
        return "—"
    return f"{x:.{nd}g}" if isinstance(x, float) else str(x)


def main(saida: str | None = None, rep: int = 5) -> str:
    from .. import fixtures_3c3 as F
    from ..mpc import experimentos as X2
    from ..mpc.orquestrador import ambiente_execucao, executar_missao_simulada
    from ..mpc.persistencia import comandos_aplicados
    from ..ponte.canonico import sha256
    from ..ponte.instrumentacao import estatisticas
    from ..rede import experimentos as X
    from ..rede.auditor import CandidatoRede3C3, auditar_3c3
    from ..rede.auditoria import auditar_missao_conectada
    from ..rede.comparadores import comparar_missoes_3c3
    from ..rede.mpc import ResolvedorMILP3C3
    from ..rede.persistencia import retomar_controlador_conectado
    from .ambiente import verificar_ambiente
    from .config import CONFIG_ANALITICA as C
    from .solver_3c3 import resolver_3c3

    amb = verificar_ambiente()
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    ae = ambiente_execucao()
    L = ["# Evidência executada — Piso 3C-3 (gerada por `python -m ems_v2.milp.evidencia_3c3`)", "",
         f"- Data (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')} · commit: `{sha}`",
         f"- Python {ae['python']} · {ae['plataforma']} · {ae['cpus']} CPUs · {ae['processador']}",
         f"- Pyomo {amb['versoes'].get('pyomo')} · highspy {amb['versoes'].get('highspy')} · HiGHS {amb['versao_highs']} "
         f"· configuração `CONFIG_ANALITICA` (gaps nulos, 1 thread, semente 0)", "",
         "Modelo ALGÉBRICO agregado do PCC sobre fixtures e tarifas **SINTÉTICAS** — não é fluxo AC, validação física, "
         "controle primário de frequência, fatura elétrica real nem afirmação de tempo real.", ""]
    # ------------------------------------------------------------------ MILP
    L += ["## 1. MILP de uma janela (G1–G4, G9, G10, isolado)", "",
          "| Caso | Esperado (analítico) | Classificação | Estado | P_imp | P_exp | J (R$) | Gasto imp. | Receita exp. | "
          "Auditor 3C-3 |", "|---|---|---|---|---|---|---|---|---|---|"]
    casos = [("G1", F.caso_g1(), "P_imp = 20, J = 8,0"), ("G2 remunerada", F.caso_g2(), "P_exp = 20, J = −3,0"),
             ("G2 sem remuneração", F.caso_g2("sem"), "P_exp = 20, J = 0"), ("G3", F.caso_g3(), "P_exp = 0, J = 0,875"),
             ("G4 sem banco", F.caso_g4(), "inviável"), ("G4 com banco", F.caso_g4(True), "sem intercâmbio, J = 0,5"),
             ("G9 perfil A", F.caso_g9("A"), "P_imp = (20; 0), J = 1,25"),
             ("G9 perfil B", F.caso_g9("B"), "P_imp = (0; 20), J = 1,25"),
             ("G10", F.caso_g10(), "sem fluxo simultâneo, J = 0"),
             ("Isolado declarado", F.caso_isolado_equivalente(), "= 3C-1, J = 0,875")]
    for nome, e, esp in casos:
        r = resolver_3c3(e, C)
        ic = r.intercambio or {}
        L.append(f"| {nome} | {esp} | {r.classificacao} | {r.estado_despacho} | {ic.get('P_imp', '—')} | "
                 f"{ic.get('P_exp', '—')} | {_f(r.objetivo)} | {_f(r.economia_rede.get('gasto_importacao_R'))} | "
                 f"{_f(r.economia_rede.get('receita_exportacao_R'))} | "
                 f"{'—' if r.auditoria is None else ('aprovada' if r.auditoria.aceito else 'REPROVADA')} |")
    from .modelo_3c3 import construir_modelo_3c3, contraprova_relaxacao_sentido
    rx = contraprova_relaxacao_sentido(construir_modelo_3c3(F.caso_g10()), C)
    L += ["", f"G10 contraprova: com o indicador de sentido RELAXADO a [0, 1] o mesmo modelo dá J = "
              f"{_f(rx['objetivo'])} R$ (P_imp = {rx['P_imp']}, P_exp = {rx['P_exp']}) com fluxos simultâneos (importa e exporta ao mesmo tempo); a binária o "
              "impede e o auditor rejeita a candidata relaxada (`pcc_exclusividade`).", ""]
    # ------------------------------------------------------------------ G14 (MILP)
    L += ["## 2. G14 — adulteração após o solver", "", "| Adulteração | Estado | Famílias reprovadas |", "|---|---|---|"]
    for nome, f in (("P_imp[0] + 1 kW", lambda cr: replace(cr, pcc={**cr.pcc, "P_imp": (cr.pcc["P_imp"][0] + 1.0,)
                                                                     + cr.pcc["P_imp"][1:]})),
                    ("custo de importação − R$ 0,5", lambda cr: replace(cr, custos_reportados={
                        **cr.custos_reportados, "importacao_rede": cr.custos_reportados["importacao_rede"] - 0.5,
                        "total": cr.custos_reportados["total"] - 0.5})),
                    ("fluxo simultâneo + 3 kW", lambda cr: replace(cr, pcc={
                        **cr.pcc, "P_imp": tuple(x + 3 for x in cr.pcc["P_imp"]),
                        "P_exp": tuple(x + 3 for x in cr.pcc["P_exp"])}))):
        r = resolver_3c3(F.caso_g1(), C, _adulterar=f)
        L.append(f"| {nome} | {r.estado_despacho} | {sorted(r.auditoria.familias_reprovadas())} |")
    e1 = F.caso_g1()
    r = resolver_3c3(e1, C)
    cr = CandidatoRede3C3(r.candidato, dict(r.intercambio), dict(r.custos_modelo))
    ind = replace(e1, pcc=replace(e1.pcc, disponibilidade=replace(e1.pcc.disponibilidade, serie=replace(
        e1.pcc.disponibilidade.serie, valores=(0.0, 1.0)))))
    a = auditar_3c3(ind, cr)
    L += [f"| mesma solução com PCC indisponível em t = 0 | {'aceita' if a.aceito else 'rejeitada'} | "
          f"{sorted(a.familias_reprovadas())} |", ""]
    # ------------------------------------------------------------------ MPC
    L += ["## 3. Missões MPC conectadas (G5–G8, G11, G12, comparação)", "",
          "| Missão | N/m | Desfecho | Falha | Aplicados | Importação aplicada por intervalo (kW) | Exportação (kW) | "
          "Custo realizado (R$) | Planejado prefixos (R$) | E_imp / E_imp prog. (kWh) | Desvio +/− (kWh) | Auditoria |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    PCC = F.PCC

    def lin(nome, ex):
        r = ex.resultado
        rm = r.registro_missao.conteudo
        t = r.registro_rede.totais
        rel = auditar_missao_conectada(r.registro_missao, r.registros, r.livro, ex.modelo, ex.politica,
                                       verdade=ex.verdade, anexos=r.anexos_3c3, registros_3c0=r.registros_3c0)
        pi = [round(p.aplicado.get(f"{PCC}|P_imp", 0.0), 6) for x in r.registros for p in x.conteudo.passos]
        pe_ = [round(p.aplicado.get(f"{PCC}|P_exp", 0.0), 6) for x in r.registros for p in x.conteudo.passos]
        return (f"| {nome} | {r.configuracao.malha.intervalos_otimizacao}/{r.configuracao.malha.intervalos_reotimizacao}"
                f" | `{rm.desfecho}` | {r.classe_falha or '—'} | {rm.intervalos_aplicados} | {pi} | {pe_} | "
                f"{_f(rm.custo_realizado_acumulado.total_R)} | {_f(rm.custo_planejado_prefixos_R)} | "
                f"{_f(t['E_importada_kWh'])} / {_f(t['E_importada_programada_kWh'])} | "
                f"{_f(t['E_desvio_positivo_kWh'])} / {_f(t['E_desvio_negativo_kWh'])} | "
                f"{'aprovada' if rel.aceito else 'REPROVADA ' + str(sorted(c.codigo for c in rel.constatacoes if c.severidade == 'erro'))} |")
    L.append(lin("G5 erro +4 kW em g=1 (esp. R$ 12,6)", X.g5_erro_positivo_demanda()))
    L.append(lin("G6 erro −4 kW (esp. R$ 11,4)", X.g6_erro_negativo_demanda()))
    L.append(lin("G6 demanda 5 kW, exportação permitida (esp. R$ 8,75)", X.g6_erro_negativo_demanda(L1=5.0)))
    L.append(lin("G6 demanda 5 kW, exportação PROIBIDA", X.g6_erro_negativo_demanda("somente_importacao", 5.0)))
    L.append(lin("G7 FV realizada 4 kW (esp. R$ 12,9)", X.g7_renovavel_superestimado()))
    L.append(lin("G8 saturação P̄_imp = 22 kW", X.g8_saturacao_pcc()))
    g11 = X.g11_mpc_conectado()
    L.append(lin("G11 MPC conectado (revisão tarifária em τ_4)", g11))
    g12 = X.g12_rede_vs_isolado()
    L.append(lin("G12 conectado (demanda = prevista)", g12["conectado"]))
    L.append(lin("G12 isolado (demanda = prevista)", g12["isolado"]))
    g12e = X.g12_rede_vs_isolado(L_real=X.L_G11)
    L.append(lin("G12 conectado (demanda com erro)", g12e["conectado"]))
    L.append(lin("G12 isolado (demanda com erro)", g12e["isolado"]))
    cmp = X.comparacao_open_loop_vs_mpc()
    L.append(lin("Open-loop (N = m = 8)", cmp["open_loop"]))
    L.append(lin("MPC (N = 4, m = 2)", cmp["mpc"]))
    hs = [a.conteudo.plano_rede.hash_tarifas_decisao["importacao"][:12] for a in g11.resultado.anexos_3c3]
    L += ["", f"G11 — hash do perfil de importação usado em cada decisão (τ_0, τ_2, τ_4, τ_6): {hs} (r1 só a partir da "
              "sua emissão em τ_4).", ""]
    # ------------------------------------------------------------------ comparação
    c = comparar_missoes_3c3(cmp["open_loop"], cmp["mpc"], rotulo_a="open-loop", rotulo_b="MPC")
    L += ["## 4. Comparação open-loop × MPC (§13)", "",
          f"Tipo `{c.tipo}` · comparável: {c.comparavel} · comparável para superioridade (energia final e obrigações "
          f"iguais): {c.comparavel_para_superioridade}", "", "| Grandeza | Open-loop | MPC | MPC − OL |", "|---|---|---|---|"]
    for k in ("custo_realizado_total_R", "E_final_kWh[syn-bess]", "obrigacoes_pendentes_s", "E_importada_kWh",
              "E_exportada_kWh", "E_importada_programada_kWh", "E_desvio_positivo_kWh", "E_desvio_negativo_kWh",
              "gasto_importacao_R", "receita_exportacao_R", "partidas[syn-fc]", "resolucoes"):
        v = c.linhas.get(k, (None, None, None))
        L.append(f"| {k} | {_f(v[0])} | {_f(v[1])} | {_f(v[2])} |")
    L += ["", f"> {c.observacao} Uma única instância sintética: NÃO se afirma que o MPC sempre reduz custos.", ""]
    t = comparar_missoes_3c3(g12["isolado"], g12["conectado"], rotulo_a="isolado", rotulo_b="conectado")
    L += [f"G12 isolado × conectado: tipo `{t.tipo}` (contraste de factibilidade/uso da rede, não benefício econômico); "
          f"custos {_f(t.linhas['custo_realizado_total_R'][0])} × {_f(t.linhas['custo_realizado_total_R'][1])} R$, "
          f"E_final {_f(t.linhas['E_final_kWh[syn-bess]'][0])} × {_f(t.linhas['E_final_kWh[syn-bess]'][1])} kWh, "
          f"obrigações {t.linhas['obrigacoes_pendentes_s'][0]} × {t.linhas['obrigacoes_pendentes_s'][1]} s.", ""]
    # ------------------------------------------------------------------ G13
    kw = dict(L_real=X.L_G11, pv_real=X.PV_REAL_G11, tarifas=F.tarifas_decisao(8, revisao_1_em="2026-01-01T01:00:00+00:00"))
    with tempfile.TemporaryDirectory() as d:
        ctrl, ent, mod, ver, pol, crd = X.montar("g11-mpc-conectado", diretorio=d, **kw)
        executar_missao_simulada(ctrl, ent, max_janelas=2, finalizar=False)
        c2, pt = retomar_controlador_conectado(d, ctrl.cfg, mod, ctrl.provedor, ResolvedorMILP3C3(C), ctrl.fontes, crd,
                                               identificadores_verdade=ctrl.id_verdade,
                                               fontes_verdade=ctrl.fontes_verdade)
        _, ent2, *_ = X.montar("g11-mpc-conectado", **kw)
        ent2.reconstituir(comandos_aplicados(pt), c2.instante_atual)
        res = executar_missao_simulada(c2, ent2)
        arquivos = sorted(p.name.split(".", 1)[1] for p in Path(d).iterdir())
    ok = res.registro_missao.impressao_deterministica == g11.resultado.registro_missao.impressao_deterministica
    L += ["## 5. G13 — interrupção após 2 janelas e retomada verificada", "",
          f"- Impressão determinística da missão retomada = contínua: **{ok}** "
          f"(`{res.registro_missao.impressao_deterministica[:16]}…`); totais de rede iguais: "
          f"{res.registro_rede.totais == g11.resultado.registro_rede.totais}; anexos 3C-3 iguais: "
          f"{[a.conteudo for a in res.anexos_3c3] == [a.conteudo for a in g11.resultado.anexos_3c3]}",
          f"- Tipos de artefato gravados: {sorted(set(arquivos))}", ""]
    # ------------------------------------------------------------------ G15
    pins = json.loads((RAIZ / "tests/ems_v2/dados/pins_3c2_base_a4c6b1c.json").read_text(encoding="utf-8"))
    e2 = X2.e2_previsao_reemitida()["mpc"].resultado
    L += ["## 6. G15 — retrocompatibilidade 3C-2", "",
          f"- E2: impressão atual `{e2.registro_missao.impressao_deterministica[:16]}…` = base "
          f"`{pins['E2']['missao'][:16]}…`: {e2.registro_missao.impressao_deterministica == pins['E2']['missao']}; "
          f"anexos 3C-1: {[sha256(a.conteudo) for a in e2.anexos_3c1] == pins['E2']['anexos']}. Os 12 conjuntos E1–E8 "
          "são comparados por igualdade exata em `tests/ems_v2/test_ems_v2_3c3_regressao_3c2.py`.", ""]
    # ------------------------------------------------------------------ tempos
    tempos = []
    for _ in range(rep):
        t0 = time.perf_counter()
        X.g11_mpc_conectado()
        tempos.append(time.perf_counter() - t0)
    est = estatisticas(tempos)
    L += ["## 7. Campanha de tempos (indicativa)", "",
          f"Missão G11 completa (4 janelas, MILP 3C-3 + auditorias + registros), n = {rep}: "
          f"{json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in vars(est).items()}, sort_keys=True)} s. "
          "Uma máquina, sem restrição operacional: nenhuma afirmação de tempo real.", ""]
    texto = "\n".join(L) + "\n"
    if saida:
        Path(saida).write_text(texto, encoding="utf-8")
    return texto


if __name__ == "__main__":
    a = sys.argv[1:]
    print(main(a[0] if a else None, int(a[1]) if len(a) > 1 else 5))
