"""Gera a evidência reproduzível do Piso 3C-3 (PCC + MPC conectado sobre fixtures sintéticas, Pyomo + HiGHS).

Uso: python -m ems_v2.milp.evidencia_3c3 [saida.md] [repeticoes]   (a partir da raiz do repositório)

G1–G4, G9, G10, G12 (estático): MILP de uma janela com valores analíticos esperados; G5–G8, G11–G13: missões MPC
conectadas auditadas pela auditoria INDEPENDENTE; G14: adulterações rejeitadas; G15: impressões E1–E8 da base;
comparação open-loop × MPC (§13) e campanha de tempos (n declarado). Sintético/algébrico: não é validação física,
fluxo AC, controle primário, fatura real nem prova de tempo real.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
# Saída LITERAL da reprodução de C-03 sobre o commit auditado 7b8da5d (antes da correção de verificar_registro_rede).
ANTES_7B8DA5D_C03 = """
== C-03 (commit 7b8da5d )
original: [] (True, [])
totais={}                        verificar_registro_rede=[] auditoria_integral(aceito, erros)=(True, [])
esquema=99                       verificar_registro_rede=[] auditoria_integral(aceito, erros)=(True, [])
perfil='v1.1-3C-1'               verificar_registro_rede=[] auditoria_integral(aceito, erros)=(True, [])
totais sem gasto_importacao_R    verificar_registro_rede=[] auditoria_integral(aceito, erros)=(True, [])
totais + metrica_extra           verificar_registro_rede=['totais_rede_divergentes'] auditoria_integral(aceito, erros)=(False, ['totais_rede_divergentes'])
"""
# Saída LITERAL do script de reprodução executado sobre o commit auditado d7da6c5 (antes das correções C-01/C-02).
ANTES_D7DA6C5 = """
== C-01 (commit d7da6c5 )
sem_ajuste               programa=False NaN      exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': nan} cod=[]
sem_ajuste               programa=False parcial  exequivel=False aplicado_pcc={} cod=['programa_pcc_ausente']
sem_ajuste               programa=True  NaN      exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': nan} cod=[]
sem_ajuste               programa=True  parcial  exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': 20.0} cod=[]
ajuste_local_algebrico   programa=False NaN      exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': 20.0} cod=[]
ajuste_local_algebrico   programa=False parcial  exequivel=False aplicado_pcc={} cod=['programa_pcc_ausente']
ajuste_local_algebrico   programa=True  NaN      exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': 20.0} cod=[]
ajuste_local_algebrico   programa=True  parcial  exequivel=True aplicado_pcc={'syn-pcc|P_exp': 0.0, 'syn-pcc|P_imp': 20.0} cod=[]
plano com imp (-3, NaN) aceito? (0.0, 0.0)
plano com imp (-3, 20) => RECORTADO para (0.0, 20.0)
== C-02
sem anexos/registros_3c0/registro de rede: aceito = True ['aceitacao', 'balanco', 'cadeia_registros', 'causal', 'custos', 'estado_e_permanencias', 'livro_observacoes', 'separacao_previsao_realizacao', 'temporal']
modelo PCC substituido (P_imp_max 60): aceito = True
politica economica substituida: aceito = True
"""


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
        rel = auditar_missao_conectada(r.registro_missao, r.registros, r.livro, ex.modelo, ex.configuracao_rede,
                                       verdade=ex.verdade, anexos=r.anexos_3c3, registros_3c0=r.registros_3c0,
                                       registro_rede=r.registro_rede)
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
    # ------------------------------------------------------------------ auditoria do PR #16 (C-01, C-02)
    L += ["## 7. Auditoria independente do PR #16 (commit auditado `d7da6c5`) — C-01 e C-02", "",
          "**Antes (reproduzido sobre `d7da6c5`, ANTES de qualquer correção; saída literal do script de reprodução):**",
          "", "```", *ANTES_D7DA6C5.strip("\n").splitlines(), "```", "",
          "**Depois (esta execução):**", "", "| Ensaio | Política | Programa explícito | Resultado |", "|---|---|---|---|"]
    import sys as _s
    _s.path.insert(0, str(RAIZ / "tests" / "ems_v2"))
    from test_ems_v2_3c3_execucao import pol as _pol, real as _real, res_g1 as _res
    from ..ponte.execucao import entorno_realizado, estado_inicial_de_entrada
    from ..rede.execucao import ExecutorAlgebricoConectado3C3, plano_de_resultado_3c3, programa_de_plano
    eg = F.caso_g1()
    pg, prg = plano_de_resultado_3c3(_res(eg), eg)
    ent, _ = entorno_realizado(_real(), pg.inicio_utc, pg.delta_s)
    cons = {f"{x.uid}|{x.grandeza}": float(x.valores[0]) for x in pg.consignas}
    for tipo in ("sem_ajuste", "ajuste_local_algebrico"):
        for comprog in (False, True):
            for nome, extra in (("P_imp = NaN", {f"{PCC}|P_imp": float("nan"), f"{PCC}|P_exp": 0.0}),
                                ("só P_imp (parcial)", {f"{PCC}|P_imp": 20.0})):
                exg = ExecutorAlgebricoConectado3C3(eg, {}, _pol(tipo=tipo),
                                                    programa=programa_de_plano(prg) if comprog else None)
                ps = exg.avancar(estado_inicial_de_entrada(eg.base), {**cons, **extra}, ent, pg.delta_s)
                L.append(f"| {nome} | `{tipo}` | {comprog} | exequível = {ps.exequivel}, falha `{ps.falha}`, "
                         f"{sorted(c.codigo for c in ps.constatacoes)} |")
    from types import SimpleNamespace as _NS
    for imp in ((-3.0, 20.0), (float("nan"), 20.0)):
        try:
            plano_de_resultado_3c3(_NS(**{**vars(_res(eg)), "intercambio": {"P_imp": imp, "P_exp": (0.0, 0.0)}}), eg)
            L.append(f"| plano com P_imp = {imp} | — | — | ACEITO |")
        except Exception as exc:  # noqa: BLE001
            L.append(f"| plano com P_imp = {imp} | — | — | recusado: {sorted(exc.codigos)} (sem recorte) |")
    from ..rede.auditoria import auditar_missao_conectada_analitica
    r = g11.resultado
    base_kw = dict(registros=r.registros, livro=r.livro, modelo=g11.modelo, configuracao_rede=g11.configuracao_rede,
                   verdade=g11.verdade, anexos=r.anexos_3c3, registros_3c0=r.registros_3c0, registro_rede=r.registro_rede)
    m = g11.modelo
    largo = replace(m, pcc=replace(m.pcc, limite_importacao=replace(
        m.pcc.limite_importacao, valores=tuple(v + 10.0 for v in m.pcc.limite_importacao.valores))))
    crd = g11.configuracao_rede
    sub = replace(crd, tarifas_decisao=tuple(p for p in crd.tarifas_decisao if p.revisao == 0))
    an, r0 = list(r.anexos_3c3), list(r.registros_3c0)
    casos_c02 = [("missão G11 válida", {}), ("sem anexos", {"anexos": None}), ("sem registros 3C-0", {"registros_3c0": None}),
                 ("sem registro de missão de rede", {"registro_rede": None}),
                 ("registro 3C-0 de outra janela", {"registros_3c0": (r0[1],) + tuple(r0[1:])}),
                 ("evidências de duas janelas trocadas", {"anexos": (an[1], an[0], *an[2:]),
                                                          "registros_3c0": (r0[1], r0[0], *r0[2:])}),
                 ("modelo PCC com P̄_imp + 10 kW (mesmo núcleo)", {"modelo": largo}),
                 ("configuração de rede sem a revisão r1 (mesmos custos realizados)", {"configuracao_rede": sub})]
    L += ["", "| Auditoria INTEGRAL — caso | aceito | integridade certificada | balanço / custos | Constatações (erro) |",
          "|---|---|---|---|---|"]
    for nome, kw in casos_c02:
        rel = auditar_missao_conectada(r.registro_missao, **{**base_kw, **kw})
        L.append(f"| {nome} | {rel.aceito} | {rel.integridade_documental_certificada} | "
                 f"{rel.verificacoes['balanco']} / {rel.verificacoes['custos']} | "
                 f"{sorted({c.codigo for c in rel.constatacoes if c.severidade == 'erro'})[:5]} |")
    ra = auditar_missao_conectada_analitica(r.registro_missao, r.registros, r.livro, largo, crd, verdade=g11.verdade)
    L += ["", f"Auditoria ANALÍTICA PARCIAL com o modelo de limites mais amplos: aceito = {ra.aceito}, escopo "
              f"`{ra.escopo}`, integridade documental certificada = {ra.integridade_documental_certificada} — reproduz "
              "os números, mas nunca certifica integridade.", ""]
    # ------------------------------------------------------------------ C-03 (verificar_registro_rede)
    from ..mpc.registro import selar as _selar
    from ..rede.mpc import METRICAS_REDE, verificar_registro_rede
    rr = r.registro_rede
    L += ["## 7b. Correção C-03 (commit auditado `7b8da5d`) — `verificar_registro_rede`", "",
          "**Antes (reproduzido sobre `7b8da5d`; saída literal):**", "", "```",
          *ANTES_7B8DA5D_C03.strip("\n").splitlines(), "```", "", "**Depois (esta execução, missão G11):**", "",
          "| Registro de rede re-selado | `verificar_registro_rede` | Auditoria integral aceita | balanço / custos |",
          "|---|---|---|---|"]
    casos_c03 = [("original", rr), ("totais = {}", _selar(replace(rr, totais={}, selo=""))),
                 ("esquema = 99", _selar(replace(rr, esquema=99, selo=""))),
                 ("perfil = 'v1.1-3C-1'", _selar(replace(rr, perfil="v1.1-3C-1", selo=""))),
                 ("sem gasto_importacao_R", _selar(replace(rr, totais={k: v for k, v in rr.totais.items()
                                                                        if k != "gasto_importacao_R"}, selo=""))),
                 ("métrica extra = 0.0", _selar(replace(rr, totais={**rr.totais, "metrica_extra": 0.0}, selo=""))),
                 ("E_exportada_kWh + 1 ulp", _selar(replace(rr, totais={
                     **rr.totais, "E_exportada_kWh": math.nextafter(rr.totais["E_exportada_kWh"], math.inf)}, selo="")))]
    for nome, rrx in casos_c03:
        cs = sorted({c.codigo for c in verificar_registro_rede(rrx, r.registro_missao, r.anexos_3c3)})
        rel = auditar_missao_conectada(r.registro_missao, **{**base_kw, "registro_rede": rrx})
        L.append(f"| {nome} | {cs or 'aprovado'} | {rel.aceito} | {rel.verificacoes['balanco']} / "
                 f"{rel.verificacoes['custos']} |")
    L += ["", f"Métricas obrigatórias do esquema {rr.esquema} ({len(METRICAS_REDE)}): {list(METRICAS_REDE)}.", ""]
    L += ["## 8. Campanha de tempos (indicativa)", "",
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
