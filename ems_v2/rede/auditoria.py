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

**Dois escopos EXPLÍCITOS (C-02, auditoria do PR #16):**

* ``auditar_missao_conectada`` — auditoria **INTEGRAL** (certificação documental): exige registros 3C-0, anexos 3C-3
  e o ``RegistroMissaoRede3C3`` (argumentos obrigatórios; ausência ⇒ reprovação, nunca omissão). Verifica, para cada
  janela executada, registro 3C-0 + anexo 3C-3 em POSIÇÃO (selos, compromissos, UID determinístico, identidade, plano,
  plano de rede, estados, checkpoint, informação, custo — ``rede.persistencia.verificar_artefatos_carregados_3c3``),
  janelas sem plano sem artefatos, nenhum artefato excedente, o registro de missão de rede (selo, vínculo ao
  ``RegistroMissaoMPC``, sequência de anexos, totais) e a vinculação do MODELO 3C-3 e da CONFIGURAÇÃO de rede
  fornecidos à auditoria (``hash_modelo_3c3``/``hash_configuracao_rede``): um PCC com limites mais amplos ou uma
  política econômica substituída são reprovados mesmo que reproduzam os mesmos fluxos e custos;
* ``auditar_missao_conectada_analitica`` — auditoria **ANALÍTICA PARCIAL** (só reprodução numérica: balanço, PCC,
  custos, estado, causalidade). O relatório declara ``escopo = "analitica_parcial"`` e
  ``integridade_documental_certificada = False``: NUNCA é certificação de integridade.

Com a verdade (só após a missão), a separação previsão × realização 3C-0 continua aplicada (inclui o PCC).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import timedelta

from ..audit import Tolerancias
from ..diagnostics import Constatacao, erro
from ..mpc.auditoria import RelatorioAuditoriaMissao, auditar_missao, custo_realizado_independente
from .auditor import _precos_idx, _seg, _serie_idx
from .contrato import EntradaRede3C3
from ..timegrid import ler_instante_utc
from .execucao import (POLITICA_RESIDUO_PCC, NormalizacaoNumericaPCC, PoliticaAjustePCC, escala_balanco_pcc,
                       limiar_residuo_pcc)

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


ESCOPOS = {"integral": "Certificação documental + reprodução analítica (registros 3C-0, anexos 3C-3, registro de "
                       "missão de rede, vínculo do modelo e da configuração)",
           "analitica_parcial": "SÓ reprodução analítica (balanço, PCC, custos, estado, causalidade): NÃO certifica a "
                                "integridade documental da missão"}


@dataclass(frozen=True)
class RelatorioAuditoriaMissaoConectada(RelatorioAuditoriaMissao):
    escopo: str = "integral"                              # ESCOPOS
    integridade_documental_certificada: bool = False
    normalizacoes_pcc: tuple = ()                         # B3C4-10: normalizações RECONSTRUÍDAS (escopo integral)


# ------------------------------------------------------------------------------------------ B3C4-10 (A03)
CODIGO_NORMALIZACAO_PCC = "normalizacao_numerica_pcc"
_RE_NORMALIZACAO = re.compile(
    r"^bruto=(?P<bruto>\S+) normalizado=(?P<norm>\S+) diferenca=(?P<dif>\S+) limiar=(?P<lim>\S+) "
    r"escala=(?P<esc>\S+) origem=solver; (?P<motivo>.+)$")
_RE_CAMINHO_NORM = re.compile(r"^pcc\[(?P<uid>[^\]]+)\]\.(?P<g>P_imp|P_exp)\[(?P<t>\d+)\]$")


def reconstruir_normalizacoes_pcc(modelo_rede: EntradaRede3C3, registros, registros_3c0, anexos,
                                  tol: Tolerancias = Tolerancias()):
    """B3C4-10: verificador ÚNICO das normalizações de resíduos do solver no PCC (auditorias integrais 3C-3 e 3C-4).

    Por janela executada, TRÊS evidências seladas devem ser coerentes: (1) código ``normalizacao_numerica_pcc`` no
    resumo da RESOLUÇÃO da janela; (2) avisos com os dados de cada normalização no registro 3C-0; (3) hash
    ``normalizacoes_pcc_b3c4_10`` das normalizações, comprometido no registro 3C-0 antes do selo. As três AUSENTES =
    janela sem normalização (inclusive todo registro anterior a B3C4-10: nenhuma obrigação nova); qualquer outra
    combinação é rejeitada (A03-1). Cada normalização é então confrontada com a política: programa do anexo 3C-3 = 0.0;
    bruto < 0; diferença = −bruto; |bruto| <= limiar; motivo = política; escala S_t e limiar RECALCULADOS do plano 3C-0
    e dos limites do modelo fornecido. Os selos SHA-256 detectam alteração frente ao artefato selado; não são assinatura
    nem provam a procedência autêntica do solver (B3C4-08). Devolve (normalizações aceitas, constatações)."""
    from ..ponte.canonico import sha256
    from .contrato import valor_no_intervalo
    from .mpc import CHAVE_HASH_NORMALIZACOES_PCC
    r0 = {r.execucao_uid: r for r in (registros_3c0 or ())}
    an = {a.conteudo.execucao_uid: a for a in (anexos or ())}
    e, out, c = modelo_rede, [], []
    for r in registros:
        ct = r.conteudo
        reg0 = r0.get(ct.execucao_uid)
        if reg0 is None:
            continue                                   # janela sem execução: nada comprometido (seção documental)
        cam = f"janelas[{ct.posicao}]"
        avs = [x for x in reg0.constatacoes if x.codigo == CODIGO_NORMALIZACAO_PCC]
        tem_hash = CHAVE_HASH_NORMALIZACOES_PCC in reg0.hashes
        tem_codigo = CODIGO_NORMALIZACAO_PCC in (ct.resolucao.codigos if ct.resolucao else ())
        if not avs and not tem_hash and not tem_codigo:
            continue                                   # janela legítima sem normalização (inclui registros históricos)
        if not tem_codigo:
            c.append(erro("normalizacao_pcc_sem_origem_no_solver", cam,
                          "Avisos/hash de normalização sem o código na resolução selada da janela (origem no "
                          "resolvedor não declarada)."))
        if not avs and not tem_hash:
            c.append(erro("normalizacao_pcc_declarada_sem_registro", cam,
                          "A resolução selada declara normalização, mas o registro 3C-0 não tem avisos nem hash."))
            continue
        recs = []
        for x in avs:
            m, mc = _RE_NORMALIZACAO.match(x.mensagem), _RE_CAMINHO_NORM.match(x.caminho)
            if m is None or mc is None:
                c.append(erro("normalizacao_pcc_ilegivel", cam, f"{x.caminho}: {x.mensagem[:80]}"))
                continue
            try:
                recs.append(NormalizacaoNumericaPCC(mc["uid"], mc["g"], int(mc["t"]), float(m["bruto"]),
                                                    float(m["norm"]), float(m["dif"]), float(m["lim"]),
                                                    float(m["esc"]), m["motivo"]))
            except ValueError:
                c.append(erro("normalizacao_pcc_ilegivel", cam, x.mensagem[:80]))
        if not avs or not tem_hash or reg0.hashes[CHAVE_HASH_NORMALIZACOES_PCC] != sha256(tuple(recs)) or \
                len(recs) != len(avs):
            c.append(erro("normalizacao_pcc_nao_comprometida", cam,
                          "Avisos de normalização × hash comprometido no registro 3C-0 ausentes ou divergentes."))
        ax = an.get(ct.execucao_uid)
        pr = getattr(getattr(ax, "conteudo", None), "plano_rede", None)
        p = reg0.plano
        for n in recs:
            cn = f"{cam}.{n.grandeza}[{n.indice_janela}]"
            prog = None if pr is None else (pr.importacao_programada_kW if n.grandeza == "P_imp" else
                                            pr.exportacao_programada_kW)
            t = n.indice_janela
            ok = (prog is not None and t < len(prog) and prog[t] == 0.0 and n.valor_normalizado_kW == 0.0
                  and n.valor_bruto_kW < 0 and n.diferenca_kW == 0.0 - n.valor_bruto_kW
                  and -n.valor_bruto_kW <= n.limiar_kW and n.motivo == POLITICA_RESIDUO_PCC
                  and e.pcc is not None and n.pcc_uid == str(e.pcc.uid))
            if ok:
                ini = (ler_instante_utc(p.inicio_utc, "p")[0] + timedelta(seconds=p.delta_s * t)).isoformat()
                li = valor_no_intervalo(e.pcc.limite_importacao, ini, p.delta_s) if e.importa else 0.0
                le = valor_no_intervalo(e.pcc.limite_exportacao, ini, p.delta_s) if e.exporta else 0.0
                vals = {f"{x.uid}|{x.grandeza}": x.valores[t] for x in p.consignas}
                S = escala_balanco_pcc(vals, li or 0.0, le or 0.0)
                ok = S == n.escala_kW and limiar_residuo_pcc(S, tol) == n.limiar_kW
            if not ok:
                c.append(erro("normalizacao_pcc_fora_da_politica", cn,
                              f"Normalização não sustentada pela política/plano/modelo: {n!r}."))
            else:
                out.append(n)
    return tuple(out), c


def _analitica(registro_missao, registros, livro, modelo, politica, verdade, tol, prog_global):
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
    custos_c: list[Constatacao] = []
    soma = []
    dj = {}
    for r in registros:
        c = r.conteudo
        if c.custos.realizado is None:
            continue
        r1 = custo_realizado_independente(modelo.compromisso, c.passos, c.estados[0], cfg.malha.delta_s, tol)
        rr, cc = custo_rede_independente(cfg, modelo, politica, c.passos, prog_global)
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
    return ver, cons, det


def auditar_missao_conectada_analitica(registro_missao, registros, livro, modelo: EntradaRede3C3, configuracao_rede, *,
                                       verdade=None, tol: Tolerancias = Tolerancias()
                                       ) -> RelatorioAuditoriaMissaoConectada:
    """Escopo ANALÍTICO PARCIAL: reprodução numérica sem os artefatos históricos. Nunca certifica integridade."""
    ver, cons, det = _analitica(registro_missao, registros, livro, modelo, configuracao_rede.politica_ajuste, verdade,
                                tol, None)
    return RelatorioAuditoriaMissaoConectada(all(ver.values()), ver, tuple(cons), det, escopo="analitica_parcial",
                                             integridade_documental_certificada=False)


def _documental(registro_missao, registros, modelo, configuracao_rede, registros_3c0, anexos, registro_rede):
    """Seção documental da auditoria INTEGRAL (C-02). Devolve (constatações, programado por intervalo global)."""
    from .contrato import hash_entrada_3c3
    from .mpc import hash_configuracao_rede, validar_configuracao_rede, verificar_registro_rede
    from .persistencia import verificar_artefatos_carregados_3c3
    out: list[Constatacao] = []
    cfg = registro_missao.conteudo.configuracao
    falt = [n for n, v in (("registros_3c0", registros_3c0), ("anexos", anexos), ("registro_rede", registro_rede))
            if v is None]
    for n in falt:
        out.append(erro("auditoria_integral_incompleta", n,
                        f"Auditoria INTEGRAL sem {n}: a integridade documental não pode ser certificada "
                        "(use a auditoria analítica parcial, rotulada, para só reproduzir números)."))
    regs0, anx = tuple(registros_3c0 or ()), tuple(anexos or ())
    out += [erro(x.codigo, "configuracao_rede." + x.caminho, x.mensagem)
            for x in validar_configuracao_rede(configuracao_rede, modelo, cfg.rotulo_informacao) if x.severidade == "erro"]
    # ------------------------------------------------ registro de missão de rede × modelo/configuração FORNECIDOS
    if registro_rede is not None:
        rr = registro_rede
        out += list(verificar_registro_rede(rr, registro_missao, anx))
        if rr.missao_uid != cfg.identidade.missao_uid:
            out.append(erro("registro_rede_de_outra_missao", "missao_rede.missao_uid", "Missão divergente."))
        if rr.hash_modelo_3c3 != hash_entrada_3c3(modelo):
            out.append(erro("modelo_3c3_divergente", "missao_rede.hash_modelo_3c3",
                            "O modelo 3C-3 (PCC, limites, tarifas do modelo) fornecido à auditoria NÃO é o da missão."))
        if rr.hash_configuracao_rede != hash_configuracao_rede(configuracao_rede):
            out.append(erro("configuracao_rede_divergente", "missao_rede.hash_configuracao_rede",
                            "A configuração de rede (política de ajuste/liquidação, tarifas de decisão) fornecida NÃO é "
                            "a da missão."))
        if rr.modo_conexao != modelo.pcc.modo:
            out.append(erro("modo_conexao_divergente", "missao_rede.modo_conexao", "Modo do PCC ≠ registrado."))
    # ------------------------------------------------ artefatos por janela (posicionais)
    com_plano = [r for r in registros if r.conteudo.hash_plano is not None]
    for r in registros:
        c = r.conteudo
        if c.hash_plano is None and (r.selo_registro_3c0 is not None or r.selo_anexo_3c1 is not None or c.passos):
            out.append(erro("artefato_referenciado_sem_plano", f"janelas[{c.posicao}]",
                            "Janela sem plano não pode referenciar registro/anexo nem ter passos."))
    if registros_3c0 is not None and len(regs0) != len(com_plano):
        out.append(erro("registros_3c0_em_numero_incoerente", "registros_3c0",
                        f"{len(regs0)} registro(s) para {len(com_plano)} janela(s) executada(s)."))
    if anexos is not None and len(anx) != len(com_plano):
        out.append(erro("anexos_3c3_em_numero_incoerente", "anexos",
                        f"{len(anx)} anexo(s) para {len(com_plano)} janela(s) executada(s)."))
    prog: dict[int, tuple[float, float]] = {}
    for i, r in enumerate(com_plano):
        reg = regs0[i] if i < len(regs0) else None
        an = anx[i] if i < len(anx) else None
        if registros_3c0 is None or anexos is None:
            break
        cs = verificar_artefatos_carregados_3c3(cfg, r, reg, an)
        out += cs
        if an is not None and (an.conteudo.plano_rede.pcc_uid != str(modelo.pcc.uid) or
                               an.conteudo.plano_rede.modo_conexao != modelo.pcc.modo):
            out.append(erro("plano_rede_de_outro_pcc", f"janelas[{r.conteudo.posicao}]", "PCC/modo do plano ≠ modelo."))
        if an is not None and not cs:
            pr = an.conteudo.plano_rede
            for x in an.conteudo.passos_pcc:
                j = x.indice_global - pr.indice_fronteira_inicial
                prog[x.indice_global] = (pr.importacao_programada_kW[j], pr.exportacao_programada_kW[j])
                if configuracao_rede.politica_ajuste.tipo == "sem_ajuste" and (
                        x.importacao_realizada_kW != x.importacao_programada_kW or
                        x.exportacao_realizada_kW != x.exportacao_programada_kW):
                    out.append(erro("ajuste_sem_politica", f"passos[{x.indice_global}]",
                                    "Realizado ≠ programado com a política 'sem_ajuste'."))
    return out, prog


def auditar_missao_conectada(registro_missao, registros, livro, modelo: EntradaRede3C3, configuracao_rede, *,
                             registros_3c0, anexos, registro_rede, verdade=None,
                             tol: Tolerancias = Tolerancias()) -> RelatorioAuditoriaMissaoConectada:
    """Auditoria INTEGRAL da missão conectada (C-02). ``registros_3c0``, ``anexos`` e ``registro_rede`` são
    OBRIGATÓRIOS (keyword sem padrão); ``None`` ⇒ ``auditoria_integral_incompleta`` e ``aceito = False``."""
    docs, prog = _documental(registro_missao, registros, modelo, configuracao_rede, registros_3c0, anexos,
                             registro_rede)
    ver, cons, det = _analitica(registro_missao, registros, livro, modelo, configuracao_rede.politica_ajuste, verdade,
                                tol, prog)
    ver["documental"] = not any(x.severidade == "erro" for x in docs)
    cons += docs
    # B3C4-10 (A03-2): coerência das normalizações do solver, com o MESMO verificador da auditoria 3C-4
    nz, cz = reconstruir_normalizacoes_pcc(modelo, registros, registros_3c0, anexos, tol)
    ver["normalizacoes_pcc"] = not cz
    cons += cz
    ok = all(ver.values())
    return RelatorioAuditoriaMissaoConectada(ok, ver, tuple(cons), det, escopo="integral",
                                             integridade_documental_certificada=ok, normalizacoes_pcc=nz)


__all__ = ["CODIGO_NORMALIZACAO_PCC", "ESCOPOS", "RelatorioAuditoriaMissaoConectada", "SUBSTITUIDAS",
           "auditar_missao_conectada", "auditar_missao_conectada_analitica", "custo_rede_independente",
           "reconstruir_normalizacoes_pcc"]
