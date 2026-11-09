"""Auditoria INDEPENDENTE da missão MPC conectada (3C-3) — só biblioteca padrão; não usa o solver nem o executor.

Composição explícita sobre ``mpc.auditoria.auditar_missao`` (3C-2, inalterada): cadeia de registros, livro K6
(prefixos, quarentena), temporal, causal, estado/memória/permanências, aceitação e separação previsão × realização são
mantidas INTEGRALMENTE. Duas seções 3C-2 desconhecem o PCC por construção e são SUBSTITUÍDAS (não omitidas) por
versões que o conhecem — as constatações dessas seções no relatório 3C-2 (``balanco_observado_violado``,
``renovavel_acima_do_observado``, ``custo_realizado_nao_reproduzido``, ``custo_com_intervalos_nao_aplicados``,
``custo_acumulado_nao_reproduzido``) são recalculadas aqui:

* **balanço com PCC** — M02-3C3 em cada passo com a demanda/potencial OBSERVADOS e o intercâmbio APLICADO; renovável
  efetiva <= potencial observado; exclusividade de sentidos; PCC indisponível observado ⇒ nenhum fluxo; sentidos
  proibidos; limites contratados (série do modelo, alinhamento próprio por inteiros de segundos); intercâmbio aplicado
  = MEDIDO pelos registros do PCC (evidência do ajuste);
* **custos** — custo realizado de cada janela = termos 3C-1 (``custo_realizado_independente``, 3C-2) + gasto de
  importação e crédito de exportação RECALCULADOS com os perfis de liquidação da política (lookup próprio) e, com
  ``desvio_diferenciado``, o desvio a partir do programado do anexo; Σ = acumulado da missão.

Com os anexos 3C-3 (``anexos``), verifica também cada anexo contra o seu registro 3C-0 (selo/compromissos/coerência),
a política ``sem_ajuste`` (realizado = programado) e os desvios programado × realizado. Com a verdade (só após a
missão), a separação previsão × realização 3C-0 continua aplicada (inclui a disponibilidade do PCC).
"""
from __future__ import annotations

import math

from ..audit import Tolerancias
from ..diagnostics import Constatacao, erro
from ..mpc.auditoria import RelatorioAuditoriaMissao, auditar_missao, custo_realizado_independente
from .auditor import _precos_idx, _seg, _serie_idx
from .contrato import EntradaRede3C3
from .execucao import PoliticaAjustePCC

SUBSTITUIDAS = {"balanco_observado_violado", "renovavel_acima_do_observado", "custo_realizado_nao_reproduzido",
                "custo_com_intervalos_nao_aplicados", "custo_acumulado_nao_reproduzido"}


def _v(serie, ini_s: int, ds: int):
    x = _serie_idx(serie, ini_s, ds, 1) if serie is not None else None
    return None if x is None else x[0]


def _p(perfil, ini_s: int, ds: int):
    x = _precos_idx(perfil, ini_s, ds, 1) if perfil is not None else None
    return None if x is None else x[0]


def _balanco_3c3(cfg, e: EntradaRede3C3, registros, tol: Tolerancias) -> list[Constatacao]:
    out = []
    b, p = e.base, e.pcc
    pcc = str(p.uid)
    ds = cfg.malha.delta_s
    t0 = _seg(cfg.malha.inicio_utc)
    for r in registros:
        for x in r.conteudo.passos:
            ap, en = x.aplicado, x.entorno_observado
            cam = f"passos[{x.indice_global}]"
            ini = t0 + x.indice_global * ds
            imp, exp = ap.get(f"{pcc}|P_imp", 0.0), ap.get(f"{pcc}|P_exp", 0.0)
            li = _v(p.limite_importacao, ini, ds) if e.importa else 0.0
            le = _v(p.limite_exportacao, ini, ds) if e.exporta else 0.0
            esc = max([1.0, abs(li or 0.0), abs(le or 0.0)] + [abs(v) for v in ap.values()] + [abs(v) for v in en.values()])
            tolP = tol.potencia_abs_kW + tol.potencia_rel_escala * esc
            inj = math.fsum([ap[f"{q.uid}|P_R"] for q in b.renovaveis] + [ap[f"{y.uid}|P_d"] - ap[f"{y.uid}|P_c"]
                                                                          for y in b.baterias]
                            + [ap[f"{g.uid}|p"] for g in b.geradores] + [imp])
            dem = math.fsum([en[f"{d.uid}|potencia"] - ap[f"{d.uid}|ell"] for d in b.demandas]
                            + [v for k, v in ap.items() if k.endswith("|d")] + [exp])
            if abs(inj - dem) > tolP:
                out.append(erro("balanco_observado_violado", cam, f"Com o PCC: {inj} ≠ {dem} kW."))
            for q in b.renovaveis:
                u = str(q.uid)
                util = en[f"{u}|potencia"] * (en[f"{u}|disponibilidade"] if q.base_potencial == "antes_da_disponibilidade"
                                              else 1.0)
                if ap[f"{u}|P_R"] > util + tolP:
                    out.append(erro("renovavel_acima_do_observado", cam, f"{u}: injeção > potencial observado."))
            if min(imp, exp) > tolP or imp < -tolP or exp < -tolP:
                out.append(erro("pcc_sentidos_simultaneos_ou_negativos", cam, f"P_imp = {imp}, P_exp = {exp} kW."))
            if not e.conectado:
                if max(abs(imp), abs(exp)) > tolP:
                    out.append(erro("intercambio_em_operacao_isolada", cam, "Operação isolada declarada."))
                continue
            a = en.get(f"{pcc}|disponibilidade")
            if a is None:
                out.append(erro("disponibilidade_pcc_nao_observada", cam, "Passo conectado sem disponibilidade observada."))
            elif a == 0.0 and max(imp, exp) > tolP:
                out.append(erro("intercambio_com_pcc_indisponivel", cam, "Fluxo com a = 0 observado."))
            if (imp > tolP and not e.importa) or (exp > tolP and not e.exporta):
                out.append(erro("sentido_proibido_no_pcc", cam, "Fluxo num sentido proibido."))
            if li is None or le is None or imp > li + tolP or exp > le + tolP:
                out.append(erro("pcc_acima_do_limite_contratado", cam, f"P_imp {imp} / P_exp {exp} × limites {li}/{le}."))
            mi = en.get(f"{p.medidor_importacao_uid}|potencia")
            me = en.get(f"{p.medidor_exportacao_uid}|potencia")
            if mi is None or me is None or abs(mi - imp) > tolP or abs(me - exp) > tolP:
                out.append(erro("intercambio_nao_corresponde_a_medicao", cam,
                                f"Aplicado (imp {imp}, exp {exp}) × medido (imp {mi}, exp {me})."))
    return out


def custo_rede_independente(cfg, e: EntradaRede3C3, politica: PoliticaAjustePCC, passos, programado=None
                            ) -> tuple[dict[str, float], list[Constatacao]]:
    """Gasto de importação (+), crédito de exportação (−) e desvio, com os perfis de LIQUIDAÇÃO declarados."""
    out: dict[str, float] = {}
    c: list[Constatacao] = []
    if not e.conectado:
        return out, c
    ds, h = cfg.malha.delta_s, cfg.malha.delta_s / 3600.0
    t0 = _seg(cfg.malha.inicio_utc)
    pcc = str(e.pcc.uid)
    rem = e.exporta and e.economia.remuneracao_exportacao == "remunerada"
    dif = politica.liquidacao == "desvio_diferenciado"
    gi, gr, gd = [], [], []
    for x in passos:
        ini = t0 + x.indice_global * ds
        imp, exp = x.aplicado.get(f"{pcc}|P_imp", 0.0), x.aplicado.get(f"{pcc}|P_exp", 0.0)
        if dif:
            if programado is None or x.indice_global not in programado:
                c.append(erro("programado_indisponivel_para_desvio", f"passos[{x.indice_global}]",
                              "Liquidação diferenciada exige o programado (anexo 3C-3)."))
                continue
            bi, bx = programado[x.indice_global]
        else:
            bi, bx = imp, exp
        ci = _p(politica.tarifa_liquidacao_importacao, ini, ds) if e.importa else 0.0
        ce = _p(politica.tarifa_liquidacao_exportacao, ini, ds) if rem else 0.0
        if ci is None or ce is None:
            c.append(erro("preco_liquidacao_nao_reconstruivel", f"passos[{x.indice_global}]", "Sem bloco tarifário."))
            continue
        gi.append(h * ci * bi)
        gr.append(h * ce * bx)
        if dif:
            dv = (imp - exp) - (bi - bx)
            cp = _p(politica.tarifa_desvio_positivo, ini, ds)
            cn = _p(politica.tarifa_desvio_negativo, ini, ds)
            if cp is None or cn is None:
                c.append(erro("preco_desvio_nao_reconstruivel", f"passos[{x.indice_global}]", "Sem bloco tarifário."))
                continue
            gd.append(h * (cp * max(0.0, dv) - cn * max(0.0, -dv)))
    if e.importa:
        out["importacao_rede"] = math.fsum(gi)
    if rem:
        out["exportacao_rede"] = -math.fsum(gr)
    if dif:
        out["desvio_rede"] = math.fsum(gd)
    return out, c


def auditar_missao_conectada(registro_missao, registros, livro, modelo: EntradaRede3C3, politica: PoliticaAjustePCC, *,
                             verdade=None, anexos=None, registros_3c0=None,
                             tol: Tolerancias = Tolerancias()) -> RelatorioAuditoriaMissao:
    base = auditar_missao(registro_missao, registros, livro, modelo.compromisso, verdade=verdade, tol=tol)
    cfg = registro_missao.conteudo.configuracao
    cons = [x for x in base.constatacoes if x.codigo not in SUBSTITUIDAS]
    ver = dict(base.verificacoes)
    det = dict(base.detalhes)

    def secao(nome, cs):
        cs = list(cs)
        ver[nome] = not any(x.severidade == "erro" for x in cs)
        cons.extend(cs)
    secao("balanco", _balanco_3c3(cfg, modelo, registros, tol))
    prog_global: dict[int, tuple[float, float]] = {}
    ca: list[Constatacao] = []
    if anexos is not None:
        from .registro import verificar_anexo_3c3
        regs0 = {r.execucao_uid: r for r in (registros_3c0 or ())}
        for a in anexos:
            r0 = regs0.get(a.conteudo.execucao_uid)
            if r0 is None:
                ca.append(erro("anexo_3c3_sem_registro", f"anexos[{a.conteudo.execucao_uid}]", "Registro 3C-0 ausente."))
                continue
            ca += [erro("anexo_3c3_invalido", f"anexos[{a.conteudo.execucao_uid}]", f"[{x.codigo}] {x.mensagem}")
                   for x in verificar_anexo_3c3(a, r0)]
            pr = a.conteudo.plano_rede
            for x in a.conteudo.passos_pcc:
                j = x.indice_global - pr.indice_fronteira_inicial
                prog_global[x.indice_global] = (pr.importacao_programada_kW[j], pr.exportacao_programada_kW[j])
                if politica.tipo == "sem_ajuste" and (abs(x.importacao_realizada_kW - x.importacao_programada_kW) > 1e-9 or
                                                     abs(x.exportacao_realizada_kW - x.exportacao_programada_kW) > 1e-9):
                    ca.append(erro("ajuste_sem_politica", f"passos[{x.indice_global}]", "Realizado ≠ programado com "
                                                                                       "a política 'sem_ajuste'."))
        selos = [r.selo_anexo_3c1 for r in registros if r.selo_anexo_3c1 is not None]
        if selos != [a.selo for a in anexos]:
            ca.append(erro("anexos_3c3_nao_ligados_a_cadeia", "anexos", "Selos dos anexos ≠ referenciados pelas janelas."))
        secao("anexos_3c3", ca)
    custos_c: list[Constatacao] = []
    soma = []
    dj = {}
    for r in registros:
        c = r.conteudo
        if c.custos.realizado is None:
            continue
        r1 = custo_realizado_independente(modelo.compromisso, c.passos, c.estados[0], cfg.malha.delta_s, tol)
        rr, cc = custo_rede_independente(cfg, modelo, politica, c.passos, prog_global if anexos is not None else None)
        custos_c += cc
        tot = math.fsum(list(r1.values()) + list(rr.values()))
        dj[c.posicao] = (tot, c.custos.realizado.total_R)
        if abs(tot - c.custos.realizado.total_R) > tol.custo_abs_R + tol.custo_rel * max(1.0, abs(tot)):
            custos_c.append(erro("custo_realizado_nao_reproduzido", f"janelas[{c.posicao}]",
                                 f"Registrado R$ {c.custos.realizado.total_R!r}; recomputado R$ {tot!r} ({r1}, {rr})."))
        comp = {x.termo: x.valor_R for x in c.custos.realizado.componentes}
        for t, v in rr.items():
            if abs(comp.get(t, float("nan")) - v) > tol.custo_abs_R + tol.custo_rel * max(1.0, abs(v)) or t not in comp:
                custos_c.append(erro("custo_rede_nao_reproduzido", f"janelas[{c.posicao}].{t}",
                                     f"Registrado {comp.get(t)!r}; recomputado {v!r}."))
        if c.custos.realizado.intervalos != c.intervalos_aplicados:
            custos_c.append(erro("custo_com_intervalos_nao_aplicados", f"janelas[{c.posicao}]", "Intervalos ≠ aplicados."))
        soma.append(tot)
    acc = registro_missao.conteudo.custo_realizado_acumulado.total_R
    if abs(math.fsum(soma) - acc) > tol.custo_abs_R + tol.custo_rel * max(1.0, abs(acc)):
        custos_c.append(erro("custo_acumulado_nao_reproduzido", "missao", f"{acc!r} ≠ Σ recomputado {math.fsum(soma)!r}."))
    det["custos"] = {**dj, "acumulado_recomputado": math.fsum(soma)}
    secao("custos", custos_c)
    return RelatorioAuditoriaMissao(all(ver.values()), ver, tuple(cons), det)


__all__ = ["SUBSTITUIDAS", "auditar_missao_conectada", "custo_rede_independente"]
