"""Métricas científicas da missão MPC (3C-2) — derivadas SÓ dos registros selados e do livro K6. Só biblioteca padrão.

Definições (h = Δ/60 h; Σ sobre os intervalos APLICADOS e conciliados; potências = consignas aplicadas; entorno =
valores OBSERVADOS efetivamente usados na conciliação):

* operação — E_dem = Σ h·L; E_ENS = Σ h·ℓ; E_servida = E_dem − E_ENS; E_curt = Σ h·(A·a − P_R); E_ren = Σ h·P_R;
  E_ger[i] = Σ h·p_i; E_carga/E_desc = Σ h·P_c / Σ h·P_d; SOC_k = e_k / C nas fronteiras executadas;
* commitment — partidas/paradas aplicadas, maior |p_t − p_{t−1}| por unidade (inclui p^{-1}), menor corrida ON/OFF
  COMPLETA dentro da missão (intervalos), obrigação herdada no início e pendente no fim (s);
* economia — custo realizado por componente e total (Σ janelas), custo planejado do PREFIXO aplicado de cada janela,
  custo planejado da janela inteira (informativo, NUNCA somado) e diferença realizado − planejado do prefixo;
* previsão — para cada chave (recurso, grandeza) e antecedência ℓ = t − k (0 <= ℓ < N_k), erro e = previsto −
  observado só quando o intervalo k+ℓ tem valor VÁLIDO no livro final; n, erro médio (viés), EAM = média |e|,
  REQM = sqrt(média e²), máx |e|. Sem observação válida o par é omitido (nunca tratado como erro 0);
* computação — por resolução: tempos de construção/solver/total (``ResultadoResolucao.tempos_s``), variáveis,
  binárias livres, restrições; estatísticas n/média/p50/p95/p99/máx por PERCENTIL DE POSTO MAIS PRÓXIMO (3C-0
  ``instrumentacao.estatisticas``); terminações e gaps. Tempos NÃO entram na impressão determinística;
* confiabilidade — janelas por desfecho/aceitação, falhas por classe, entradas do livro por classificação,
  observações tardias (``tardia_apos_corte``), revisões tardias, pausas por falta de observação.

Nenhuma métrica afirma desempenho de tempo real: os tempos são medições indicativas do ambiente registrado.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import timedelta

from ..compromisso.contrato import EntradaCommitment3C1
from ..ponte.instrumentacao import estatisticas
from ..timegrid import ler_instante_utc
from .observacoes import LivroObservacoes, resumo_classificacoes


@dataclass(frozen=True)
class MetricasMissao:
    operacao: dict
    trajetoria_soc: dict
    commitment: dict
    economia: dict
    previsao: dict
    computacao: dict
    confiabilidade: dict
    definicoes: str = field(default=__doc__ or "")


def _stats(vs):
    e = estatisticas([v for v in vs if v is not None])
    return {"n": e.n, "media": e.media, "p50": e.p50, "p95": e.p95, "p99": e.p99, "max": e.maximo}


def metricas_missao(resultado, modelo: EntradaCommitment3C1) -> MetricasMissao:
    regs = list(resultado.registros)
    cfg = resultado.configuracao
    b = modelo.base
    h = cfg.malha.delta_s / 3600.0
    passos = [p for r in regs for p in r.conteudo.passos]
    # ---------------------------------------------------------------- operação
    op: dict[str, float] = {}
    op["E_demanda_kWh"] = math.fsum(h * p.entorno_observado[f"{d.uid}|potencia"] for p in passos for d in b.demandas)
    op["E_nao_suprida_kWh"] = math.fsum(h * p.aplicado[f"{d.uid}|ell"] for p in passos for d in b.demandas)
    op["E_servida_kWh"] = op["E_demanda_kWh"] - op["E_nao_suprida_kWh"]
    curt, ren = [], []
    for p in passos:
        for r in b.renovaveis:
            u = str(r.uid)
            A, a = p.entorno_observado[f"{u}|potencia"], p.entorno_observado[f"{u}|disponibilidade"]
            util = A * a if r.base_potencial == "antes_da_disponibilidade" else A
            curt.append(h * (util - p.aplicado[f"{u}|P_R"]))
            ren.append(h * p.aplicado[f"{u}|P_R"])
    op["E_curtailment_kWh"], op["E_renovavel_usada_kWh"] = math.fsum(curt), math.fsum(ren)
    for g in b.geradores:
        op[f"E_geracao_kWh[{g.uid}]"] = math.fsum(h * p.aplicado[f"{g.uid}|p"] for p in passos)
    for x in b.baterias:
        op[f"E_carga_kWh[{x.uid}]"] = math.fsum(h * p.aplicado[f"{x.uid}|P_c"] for p in passos)
        op[f"E_descarga_kWh[{x.uid}]"] = math.fsum(h * p.aplicado[f"{x.uid}|P_d"] for p in passos)
    estados = []
    for r in regs:
        for e in r.conteudo.estados:
            if not estados or e.indice_fronteira != estados[-1].indice_fronteira:
                estados.append(e)
    soc = {}
    for x in b.baterias:
        C = float(x.capacidade_kWh.valor)
        soc[str(x.uid)] = tuple(e.bateria(str(x.uid)).energia_kWh / C for e in estados)
        if soc[str(x.uid)]:
            op[f"SOC_min[{x.uid}]"], op[f"SOC_max[{x.uid}]"] = min(soc[str(x.uid)]), max(soc[str(x.uid)])
            op[f"SOC_final[{x.uid}]"] = soc[str(x.uid)][-1]
            op[f"E_final_kWh[{x.uid}]"] = estados[-1].bateria(str(x.uid)).energia_kWh
    # ---------------------------------------------------------------- commitment
    com: dict = {}
    for g in b.geradores:
        u = str(g.uid)
        seq = [(e.gerador(u).ligado, e.gerador(u).potencia_kW) for e in estados]
        part = sum(1 for a, z in zip(seq, seq[1:]) if z[0] and not a[0])
        par = sum(1 for a, z in zip(seq, seq[1:]) if a[0] and not z[0])
        ramp = max([abs(z[1] - a[1]) for a, z in zip(seq, seq[1:])] or [0.0])
        corridas: dict[bool, list[int]] = {True: [], False: []}
        i = 1
        while i < len(seq):
            j = i
            while j + 1 < len(seq) and seq[j + 1][0] == seq[i][0]:
                j += 1
            if seq[i][0] != seq[i - 1][0] and j + 1 < len(seq):      # corrida completa iniciada E terminada na missão
                corridas[seq[i][0]].append(j - i + 1)
            i = j + 1
        com[u] = {"partidas": part, "paradas": par, "rampa_max_kW": ramp,
                  "menor_corrida_on_completa": min(corridas[True]) if corridas[True] else None,
                  "menor_corrida_off_completa": min(corridas[False]) if corridas[False] else None}
    if resultado.registro_missao is not None:
        for u, s in resultado.registro_missao.conteudo.obrigacoes_pendentes_fim_s.items():
            com.setdefault(u, {})["obrigacao_pendente_fim_s"] = s
    for m in modelo.memorias:
        com.setdefault(str(m.uid), {})["obrigacao_herdada_inicio_s"] = m.obrigacao_residual_s
    # ---------------------------------------------------------------- economia
    comp: dict[str, float] = {}
    por_janela = []
    for r in regs:
        c = r.conteudo
        cr, pp = c.custos.realizado, c.custos.planejado_prefixo
        if cr is not None:
            for x in cr.componentes:
                comp[x.termo] = comp.get(x.termo, 0.0) + x.valor_R
        por_janela.append({"posicao": c.posicao, "k": c.janela.k, "aplicados": c.intervalos_aplicados,
                           "realizado_R": None if cr is None else cr.total_R,
                           "planejado_prefixo_R": None if pp is None else pp.total_R,
                           "planejado_janela_R": c.custos.planejado_janela_R.get("total"),
                           "diferenca_R": c.custos.diferenca_realizado_menos_planejado_R})
    eco = {"realizado_total_R": math.fsum(x["realizado_R"] or 0.0 for x in por_janela),
           "componentes_R": dict(sorted(comp.items())),
           "planejado_prefixos_total_R": math.fsum(x["planejado_prefixo_R"] or 0.0 for x in por_janela),
           "por_janela": por_janela,
           "nota": "planejado_janela_R é a função objetivo de janelas SOBREPOSTAS: nunca é somado."}
    eco["diferenca_total_R"] = eco["realizado_total_R"] - eco["planejado_prefixos_total_R"]
    # ---------------------------------------------------------------- previsão
    livro = resultado.livro if isinstance(resultado.livro, LivroObservacoes) else LivroObservacoes.importar(resultado.livro)
    final = livro.instantaneo(max((e.observacao.recebido_utc for e in livro.entradas), default=cfg.malha.inicio_utc,
                                  key=lambda x: ler_instante_utc(x, "t")[0]))
    erros: dict[str, dict[int, list[float]]] = {}
    for r in regs:
        pv = r.conteudo.previsao
        if pv is None:
            continue
        for s in pv.series:
            t0 = ler_instante_utc(s.serie.inicio_utc, "t")[0]
            for ell, v in enumerate(s.serie.valores):
                ti = t0 + ell * timedelta(seconds=s.serie.passo_s)
                ob = final.valor(s.uid, s.grandeza, ti.isoformat())
                if ob is None or ob.valor is None:
                    continue
                erros.setdefault(f"{s.uid}|{s.grandeza}", {}).setdefault(ell, []).append(float(v) - ob.valor)
    prev = {}
    for k, por in sorted(erros.items()):
        prev[k] = {ell: {"n": len(es), "erro_medio": math.fsum(es) / len(es),
                         "eam": math.fsum(abs(e) for e in es) / len(es),
                         "reqm": math.sqrt(math.fsum(e * e for e in es) / len(es)),
                         "max_abs": max(abs(e) for e in es)} for ell, es in sorted(por.items())}
    # ---------------------------------------------------------------- computação
    tc, ts, tt, tam_v, tam_b, tam_r, terms, gaps = [], [], [], [], [], [], {}, []
    for r in regs:
        rs = r.conteudo.resolucao
        if rs is None:
            continue
        tc.append(r.tempos_s.get("solver_construcao_s"))
        ts.append(r.tempos_s.get("solver_solver_s"))
        tt.append(r.tempos_s.get("solver_total_s"))
        tam_v.append(rs.tamanho.get("variaveis"))
        tam_b.append(rs.tamanho.get("binarias_livres"))
        tam_r.append(rs.tamanho.get("restricoes"))
        terms[f"{rs.terminacao}/{rs.status_solucao}"] = terms.get(f"{rs.terminacao}/{rs.status_solucao}", 0) + 1
        gaps.append(rs.gap_rel)
    comp_ = {"resolucoes": len(tt), "construcao_s": _stats(tc), "solver_s": _stats(ts), "total_resolucao_s": _stats(tt),
             "variaveis": _stats(tam_v), "binarias_livres": _stats(tam_b), "restricoes": _stats(tam_r),
             "terminacoes": dict(sorted(terms.items())), "gap_rel_max": max([g for g in gaps if g is not None],
                                                                            default=None),
             "nota": "tempos indicativos do ambiente registrado; nenhuma restrição de tempo real foi validada"}
    # ---------------------------------------------------------------- confiabilidade
    desf, acc, fal = {}, {}, {}
    pausas = 0
    for r in regs:
        c = r.conteudo
        desf[c.desfecho] = desf.get(c.desfecho, 0) + 1
        acc[c.aceitacao] = acc.get(c.aceitacao, 0) + 1
        if c.classe_falha:
            fal[c.classe_falha] = fal.get(c.classe_falha, 0) + 1
        pausas += sum(1 for x in c.constatacoes if x.codigo == "conciliacao_pausada_C02")
    ent = livro.entradas
    conf = {"janelas": len(regs), "por_desfecho": desf, "por_aceitacao": acc, "falhas_por_classe": fal,
            "livro_por_classificacao": resumo_classificacoes(ent),
            "observacoes_tardias_apos_corte": sum(1 for e in ent if e.tardia_apos_corte is not None),
            "revisoes_tardias": len({x.posicao_livro for r in regs for x in r.conteudo.revisoes_tardias}),
            "pausas_por_falta_de_observacao": pausas,
            "inviabilidades": fal.get("inviavel", 0), "falhas_integridade": fal.get("integridade", 0)}
    return MetricasMissao(op, soc, com, eco, prev, comp_, conf)


__all__ = ["MetricasMissao", "metricas_missao"]
