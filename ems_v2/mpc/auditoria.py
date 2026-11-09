"""Auditoria temporal, causal, de estado e contábil da missão MPC — INDEPENDENTE do solver (3C-2). Só biblioteca padrão.

Trabalha sobre os REGISTROS selados (e o livro K6), não sobre objetos internos do orquestrador, e RECALCULA:

* **temporal** — τ_k = τ_0 + kΔ, N_k e m_k pela política terminal declarada (fórmula própria), decisão em τ_k,
  contador global contíguo, último bloco <= m, nenhum intervalo aplicado além de K_M;
* **causal** — instantâneo da decisão recalculado do PREFIXO do livro (hash), nenhuma entrada aceita com recepção
  posterior ao corte dentro do prefixo, vínculo previsão ↔ instantâneo, emissões <= τ_k, entorno usado em cada passo =
  valores efetivos de algum instantâneo de conciliação com corte >= fim do intervalo, confirmação por passo aplicado;
  com a verdade (só após a missão), separação previsão × realização 3C-0 (fuga com evidência ⇒ erro);
* **estado** — recorrência M07 dos bancos com os parâmetros DECLARADOS (``fsum``), limites de SOC, ON/OFF e potência
  dos geradores = consignas, tempo no estado, permanências mínimas em TODA a missão (inclusive memória inicial);
* **balanço** — M02 em cada passo com a demanda/potencial OBSERVADOS; P_R <= potencial utilizável observado;
* **custos** — custo realizado de cada janela recomputado (curtailment, throughput, H₂ h·q PWL própria + massas de
  evento, eventos C_SU/C_SD, ENS) e Σ = custo acumulado da missão; nenhum termo de valor futuro;
* **aceitação** — nenhum passo aplicado sem plano aceito (ótimo ou não ótimo dentro da política declarada).

``verificar_nao_antecipatividade`` é o teste por INTERVENÇÃO: duas verdades iguais até a fronteira k* e diferentes
depois ⇒ toda decisão em τ_k com k <= k* deve ser idêntica (instantâneo, previsão, entrada, plano). Um provedor com
acesso oculto à verdade futura é detectado sempre que o valor vazado difira entre as duas verdades (limite de
confiança: vazamentos que coincidam nas duas verdades, ou que dependam de partes não perturbadas, não são detectados).
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from datetime import timedelta
from fractions import Fraction

from ..audit import Tolerancias
from ..compromisso.contrato import EntradaCommitment3C1, hash_entrada_3c1
from ..diagnostics import Constatacao, aviso, erro
from ..ponte.cenario import DefinicaoTemporal, Realizacao, validar_separacao
from ..timegrid import ler_instante_utc
from .contrato import ConfiguracaoMPC
from .observacoes import ACEITAS, DocumentoLivro, LivroObservacoes, instantaneo_de_prefixo, verificar_cadeia_livro
from .registro import RegistroMissaoMPC, verificar_cadeia_janelas, verificar_registro_missao


@dataclass(frozen=True)
class RelatorioAuditoriaMissao:
    aceito: bool
    verificacoes: dict[str, bool]
    constatacoes: tuple[Constatacao, ...]
    detalhes: dict = field(default_factory=dict)

    def codigos(self) -> set[str]:
        return {c.codigo for c in self.constatacoes}


def _t(x):
    return ler_instante_utc(x, "t")[0]


def _N_m_esperados(cfg: ConfiguracaoMPC, k: int) -> tuple[int, int]:
    m = cfg.malha
    resto = m.intervalos_missao - k
    N = min(m.intervalos_otimizacao, resto) if cfg.politica_terminal.tipo == "janela_reduzida" else m.intervalos_otimizacao
    return N, min(m.intervalos_reotimizacao, resto)


def _q_pwl(vertices, p: float, tol: float) -> Fraction:
    Ps = [Fraction(str(v[0])) for v in vertices]
    Qs = [Fraction(str(v[1])) for v in vertices]
    x = Fraction(repr(float(p)))
    if x < Ps[0]:
        x = Ps[0] if Ps[0] - x <= Fraction(repr(tol)) else x
    if x > Ps[-1]:
        x = Ps[-1] if x - Ps[-1] <= Fraction(repr(tol)) else x
    if not Ps[0] <= x <= Ps[-1]:
        raise ValueError(f"p = {p} fora do domínio PWL")
    i = min(max(bisect.bisect_right(Ps, x) - 1, 0), len(Ps) - 2)
    return Qs[i] + (Qs[i + 1] - Qs[i]) * (x - Ps[i]) / (Ps[i + 1] - Ps[i])


def custo_realizado_independente(modelo: EntradaCommitment3C1, passos, estado_inicial, delta_s: int,
                                 tol: Tolerancias = Tolerancias()) -> dict[str, float]:
    """Custo REALIZADO de uma sequência de passos (aplicado × entorno observado) com os coeficientes DECLARADOS."""
    b = modelo.base
    h = delta_s / 3600.0
    termos = set(modelo.termos)
    acc: dict[str, list[float]] = {t: [] for t in termos if t in ("curtailment_operacional", "throughput_bess",
                                                                   "energia_nao_suprida", "combustivel_h2", "eventos")}
    lig = {g.uid: g.ligado for g in estado_inicial.geracao}
    for p in passos:
        ap, en = p.aplicado, p.entorno_observado
        for r in b.renovaveis:
            u = str(r.uid)
            A, a = en[f"{u}|potencia"], en[f"{u}|disponibilidade"]
            util = A * a if r.base_potencial == "antes_da_disponibilidade" else A
            if "curtailment_operacional" in acc:
                acc["curtailment_operacional"].append(float(r.custo_curtailment.valor) * h * (util - ap[f"{u}|P_R"]))
        for x in b.baterias:
            u = str(x.uid)
            if "throughput_bess" in acc:
                acc["throughput_bess"].append(float(x.custo_throughput.valor) * h * (ap[f"{u}|P_c"] + ap[f"{u}|P_d"]))
        for d in b.demandas:
            u = str(d.uid)
            if "energia_nao_suprida" in acc and d.custo_energia_nao_suprida is not None:
                acc["energia_nao_suprida"].append(float(d.custo_energia_nao_suprida.valor) * h * ap[f"{u}|ell"])
        for g in b.geradores:
            u = str(g.uid)
            on = ap[f"{u}|u"] > 0.5
            su, sd = on and not lig[u], lig[u] and not on
            lig[u] = on
            sp = modelo.unidade(u)
            if "combustivel_h2" in acc and g.tecnologia == "pemfc" and g.curva_h2 is not None:
                cH = float(g.preco_h2.valor)
                q = float(_q_pwl(g.curva_h2.vertices, ap[f"{u}|p"], 1e-6)) if on else 0.0
                m_ev = (float(sp.massa_h2_partida_kg.valor) if su and sp.massa_h2_partida_kg else 0.0) + \
                       (float(sp.massa_h2_parada_kg.valor) if sd and sp.massa_h2_parada_kg else 0.0)
                acc["combustivel_h2"].append(cH * (h * q + m_ev))
            if "eventos" in acc and sp.custo_partida is not None:
                acc["eventos"].append(float(sp.custo_partida.valor) * su + float(sp.custo_parada.valor) * sd)
    return {k: math.fsum(v) for k, v in sorted(acc.items())}


def auditar_missao(registro_missao: RegistroMissaoMPC, registros, livro: DocumentoLivro | LivroObservacoes,
                   modelo: EntradaCommitment3C1, *, verdade: Realizacao | None = None,
                   tol: Tolerancias = Tolerancias()) -> RelatorioAuditoriaMissao:
    cfg = registro_missao.conteudo.configuracao
    doc = livro.exportar() if isinstance(livro, LivroObservacoes) else livro
    out: list[Constatacao] = []
    ver: dict[str, bool] = {}
    det: dict = {}

    def secao(nome, cs):
        cs = list(cs)
        ver[nome] = not any(x.severidade == "erro" for x in cs)
        out.extend(cs)

    secao("cadeia_registros", verificar_registro_missao(registro_missao, registros))
    cl = verificar_cadeia_livro(doc)
    try:
        LivroObservacoes.importar(doc)
    except Exception as exc:  # noqa: BLE001
        cl.append(erro("livro_nao_reproduzivel", "livro", str(exc)[:300]))
    if registro_missao.conteudo.hash_cadeia_livro != (doc.entradas[-1].hash_cadeia if doc.entradas else None) and \
            doc.entradas:
        cl.append(erro("livro_divergente_da_missao", "livro", "Cabeça da cadeia ≠ registrada na missão."))
    secao("livro_observacoes", cl)
    secao("temporal", _temporal(cfg, registros))
    secao("causal", _causal(cfg, registros, doc))
    secao("estado_e_permanencias", _estado(cfg, modelo, registros, tol))
    secao("balanco", _balanco(modelo, registros, tol))
    cc, det["custos"] = _custos(cfg, modelo, registros, registro_missao, tol)
    secao("custos", cc)
    secao("aceitacao", _aceitacao(cfg, registros))
    if verdade is not None:
        secao("separacao_previsao_realizacao", _separacao(cfg, registros, verdade))
    if hash_entrada_3c1(modelo) != registro_missao.conteudo.hash_modelo_3c1:
        out.append(erro("modelo_divergente", "modelo", "O modelo auditado não é o da missão."))
        ver["modelo"] = False
    return RelatorioAuditoriaMissao(all(ver.values()), ver, tuple(out), det)


def _temporal(cfg, registros) -> list[Constatacao]:
    m = cfg.malha
    t0, d, K = m.inicio(), timedelta(seconds=m.delta_s), m.intervalos_missao
    out = []
    total = 0
    for p, r in enumerate(registros):
        c, j = r.conteudo, r.conteudo.janela
        cam = f"janelas[{p}]"
        N, mk = _N_m_esperados(cfg, j.k)
        if _t(j.inicio_utc) != t0 + j.k * d or _t(c.instante_decisao_utc) != t0 + j.k * d:
            out.append(erro("instante_janela_incoerente", cam, "τ_k ≠ τ_0 + kΔ ou decisão fora de τ_k."))
        if (j.N_k, j.m_k) != (N, mk):
            out.append(erro("janela_fora_da_politica", cam, f"(N_k, m_k) = {(j.N_k, j.m_k)}; esperado {(N, mk)}."))
        if j.reduzida != (j.N_k < m.intervalos_otimizacao) or j.final != (j.k + j.m_k == K):
            out.append(erro("rotulo_janela_incoerente", cam, "reduzida/final incoerentes."))
        if c.passos and c.passos[-1].indice_global >= K:
            out.append(erro("aplicacao_alem_da_missao", cam, "Intervalo aplicado depois de T_M."))
        if c.intervalos_comprometidos > j.m_k:
            out.append(erro("comprometido_alem_de_m", cam, "Mais comandos que m_k."))
        total += c.intervalos_aplicados
    if total > K:
        out.append(erro("missao_excedida", "janelas", f"{total} > K_M = {K}."))
    return out


def _causal(cfg, registros, doc: DocumentoLivro) -> list[Constatacao]:
    out = []
    ent = doc.entradas
    m_uid, mg = doc.missao_uid, doc.microrrede_uid

    def snap(corte, n):
        return instantaneo_de_prefixo(m_uid, mg, _t(corte).isoformat(), ent[:n],
                                      ent[n - 1].hash_cadeia if n else _genese(doc))

    def aceito_e_tr(e):
        return (e.classificacao in ACEITAS or e.classificacao == "duplicata_semantica"), _t(e.observacao.recebido_utc)
    for p, r in enumerate(registros):
        c = r.conteudo
        cam = f"janelas[{p}]"
        tk = _t(c.instante_decisao_utc)
        if c.n_entradas_instantaneo > len(ent):
            out.append(erro("instantaneo_alem_do_livro", cam, "Prefixo maior que o livro."))
            continue
        s = snap(c.instante_decisao_utc, c.n_entradas_instantaneo)
        if s.hash != c.hash_instantaneo:
            out.append(erro("instantaneo_nao_reproduzido", cam, "Hash do instantâneo ≠ recalculado do prefixo do livro."))
        for e in ent[:c.n_entradas_instantaneo]:
            ok, tr = aceito_e_tr(e)
            if ok and tr > tk:
                out.append(erro("informacao_futura_no_instantaneo", cam, f"Entrada {e.posicao} recebida depois de τ_k."))
        for e in ent[c.n_entradas_instantaneo:]:
            ok, tr = aceito_e_tr(e)
            if ok and tr <= tk:
                out.append(erro("informacao_disponivel_omitida", cam, f"Entrada {e.posicao} disponível em τ_k fora do prefixo."))
        pv = c.previsao
        if pv is not None:
            if pv.procedencia is None or pv.procedencia.sha256 != c.hash_instantaneo:
                out.append(erro("previsao_sem_vinculo_informacional", cam, "Previsão não vinculada ao instantâneo da decisão."))
            if _t(pv.emissao_utc) > tk or any(x.serie.emissao_utc is None or _t(x.serie.emissao_utc) > _t(pv.emissao_utc)
                                             for x in pv.series):
                out.append(erro("previsao_nao_causal", cam, "Emissão posterior a τ_k (ou série após o conjunto)."))
            if pv.previsao_perfeita and cfg.rotulo_informacao != "ablacao_oraculo":
                out.append(erro("oraculo_em_missao_causal", cam, "Previsão perfeita numa missão causal."))
        snaps = []
        for corte, hs, n in c.conciliacoes:
            if n > len(ent):
                out.append(erro("instantaneo_alem_do_livro", cam, "Conciliação além do livro."))
                continue
            sc = snap(corte, n)
            if sc.hash != hs:
                out.append(erro("instantaneo_nao_reproduzido", cam, f"Instantâneo de conciliação em {corte} divergente."))
            snaps.append((_t(corte), sc))
        d = timedelta(seconds=cfg.malha.delta_s)
        t0 = cfg.malha.inicio()
        for x in c.passos:
            ini = t0 + x.indice_global * d
            ok = False
            for corte, sc in snaps:
                if corte < ini + d:
                    continue
                vals = {}
                for k_ in x.entorno_observado:
                    uid, _, gr = k_.partition("|")
                    v = sc.valor(uid, gr, ini.isoformat())
                    vals[k_] = None if v is None else v.valor
                if vals == x.entorno_observado:
                    ok = True
                    break
            if not ok:
                out.append(erro("entorno_conciliado_nao_rastreavel", f"{cam}.passos[{x.indice_global}]",
                                "Valores usados não correspondem a nenhum instantâneo de conciliação com corte >= fim."))
        if len(c.confirmacoes) != len(c.passos):
            out.append(erro("passo_sem_confirmacao", cam, "Passo aplicado sem confirmação registrada."))
    return out


def _genese(doc: DocumentoLivro) -> str:
    return LivroObservacoes(doc.missao_uid, doc.microrrede_uid, {}).hash_cadeia()


def _estado(cfg, modelo: EntradaCommitment3C1, registros, tol: Tolerancias) -> list[Constatacao]:
    out = []
    b = modelo.base
    h = cfg.malha.delta_s / 3600.0
    bat = {str(x.uid): x for x in b.baterias}
    ds = cfg.malha.delta_s
    regs = [r for r in registros if r.conteudo.estados]
    if not regs:
        return out
    est0 = regs[0].conteudo.estados[0]
    mem = {g.uid: (g.ligado, g.tempo_no_estado_s) for g in est0.geracao}
    for r in regs:
        c = r.conteudo
        for i, x in enumerate(c.passos):
            a, z = c.estados[i], c.estados[i + 1]
            cam = f"janelas[{c.posicao}].passos[{x.indice_global}]"
            for u, spec in bat.items():
                C = float(spec.capacidade_kWh.valor)
                alfa = 1.0 if spec.hipotese_autodescarga == "nao_modelada_alpha_1" else math.exp(
                    -float(spec.autodescarga_1_h.valor) * h)
                e1 = math.fsum([alfa * a.bateria(u).energia_kWh, h * float(spec.eta_carga.valor) * x.aplicado[f"{u}|P_c"],
                                -h * x.aplicado[f"{u}|P_d"] / float(spec.eta_descarga.valor)])
                tolE = tol.energia_abs_kWh + tol.energia_rel_capacidade * C
                if abs(e1 - z.bateria(u).energia_kWh) > tolE:
                    out.append(erro("recorrencia_bess_violada", cam, f"{u}: e = {z.bateria(u).energia_kWh} ≠ {e1}."))
                if not float(spec.soc_min.valor) * C - tolE <= z.bateria(u).energia_kWh <= float(spec.soc_max.valor) * C + tolE:
                    out.append(erro("soc_fora_dos_limites", cam, f"{u}: e = {z.bateria(u).energia_kWh}."))
            for g in b.geradores:
                u = str(g.uid)
                on = x.aplicado[f"{u}|u"] > 0.5
                if z.gerador(u).ligado != on or abs(z.gerador(u).potencia_kW - x.aplicado[f"{u}|p"]) > tol.potencia_abs_kW:
                    out.append(erro("estado_gerador_incoerente", cam, f"{u}: estado ≠ consigna aplicada."))
                lig0, tempo0 = mem[u]
                sp = modelo.unidade(u)
                if on != lig0:
                    Tm = sp.tempo_min_ligado_min if lig0 else sp.tempo_min_desligado_min
                    T = None if Tm is None or Tm.valor is None else Fraction(str(Tm.valor)) * 60
                    if T is not None and T > 0 and (tempo0 is None or tempo0 < T):
                        out.append(erro("permanencia_minima_violada_na_missao", cam,
                                        f"{u}: transição após {tempo0} s no estado; mínimo {T} s."))
                    novo = ds
                else:
                    novo = None if tempo0 is None else tempo0 + ds
                mem[u] = (on, novo)
                if z.gerador(u).tempo_no_estado_s != novo:
                    out.append(erro("memoria_executada_incoerente", cam,
                                    f"{u}: tempo no estado {z.gerador(u).tempo_no_estado_s} ≠ {novo} recalculado."))
    return out


def _balanco(modelo, registros, tol: Tolerancias) -> list[Constatacao]:
    out = []
    b = modelo.base
    for r in registros:
        for x in r.conteudo.passos:
            ap, en = x.aplicado, x.entorno_observado
            inj = math.fsum([ap[f"{r_.uid}|P_R"] for r_ in b.renovaveis] + [ap[f"{y.uid}|P_d"] - ap[f"{y.uid}|P_c"]
                                                                            for y in b.baterias]
                            + [ap[f"{g.uid}|p"] for g in b.geradores])
            dem = math.fsum([en[f"{d.uid}|potencia"] - ap[f"{d.uid}|ell"] for d in b.demandas]
                            + [v for k, v in ap.items() if k.endswith("|d")])
            esc = max([1.0] + [abs(v) for v in ap.values()] + [abs(v) for v in en.values()])
            if abs(inj - dem) > tol.potencia_abs_kW + tol.potencia_rel_escala * esc:
                out.append(erro("balanco_observado_violado", f"passos[{x.indice_global}]", f"{inj} ≠ {dem} kW."))
            for r_ in b.renovaveis:
                u = str(r_.uid)
                util = en[f"{u}|potencia"] * (en[f"{u}|disponibilidade"] if r_.base_potencial == "antes_da_disponibilidade"
                                              else 1.0)
                if ap[f"{u}|P_R"] > util + tol.potencia_abs_kW + tol.potencia_rel_escala * esc:
                    out.append(erro("renovavel_acima_do_observado", f"passos[{x.indice_global}]", f"{u}."))
    return out


def _custos(cfg, modelo, registros, rm, tol: Tolerancias) -> tuple[list[Constatacao], dict]:
    out, det = [], {}
    soma = []
    for r in registros:
        c = r.conteudo
        if c.custos.realizado is None:
            continue
        rec = custo_realizado_independente(modelo, c.passos, c.estados[0], cfg.malha.delta_s, tol)
        tot = math.fsum(rec.values())
        det[c.posicao] = (tot, c.custos.realizado.total_R)
        if abs(tot - c.custos.realizado.total_R) > tol.custo_abs_R + tol.custo_rel * max(1.0, abs(tot)):
            out.append(erro("custo_realizado_nao_reproduzido", f"janelas[{c.posicao}]",
                            f"Registrado R$ {c.custos.realizado.total_R!r}; recomputado R$ {tot!r} ({rec})."))
        if c.custos.realizado.intervalos != c.intervalos_aplicados:
            out.append(erro("custo_com_intervalos_nao_aplicados", f"janelas[{c.posicao}]", "Intervalos ≠ aplicados."))
        soma.append(tot)
    acc = rm.conteudo.custo_realizado_acumulado.total_R
    if abs(math.fsum(soma) - acc) > tol.custo_abs_R + tol.custo_rel * max(1.0, abs(acc)):
        out.append(erro("custo_acumulado_nao_reproduzido", "missao", f"{acc!r} ≠ Σ recomputado {math.fsum(soma)!r}."))
    det["acumulado_recomputado"] = math.fsum(soma)
    return out, det


def _aceitacao(cfg, registros) -> list[Constatacao]:
    out = []
    pol = cfg.politica_aceitacao
    for r in registros:
        c = r.conteudo
        if not c.passos:
            continue
        rs = c.resolucao
        if rs is None or not rs.aceito or c.aceitacao not in ("aceito_otimo", "aceito_factivel_dentro_da_politica"):
            out.append(erro("aplicacao_sem_plano_aceito", f"janelas[{c.posicao}]", "Passos sem resultado aceito."))
            continue
        if c.aceitacao == "aceito_factivel_dentro_da_politica" and (
                not pol.aceitar_factivel_nao_otimo or rs.terminacao not in pol.terminacoes_admitidas
                or rs.gap_rel is None or rs.gap_rel > pol.gap_rel_max):
            out.append(erro("nao_otimo_fora_da_politica", f"janelas[{c.posicao}]", "Gap/terminação fora da política."))
        if c.aceitacao == "aceito_otimo" and (rs.classificacao != "otimo" or rs.estado_despacho != "aceito_otimo"):
            out.append(erro("aceitacao_incoerente", f"janelas[{c.posicao}]", "Rótulo ótimo sem classificação ótima."))
    return out


def _separacao(cfg, registros, verdade: Realizacao) -> list[Constatacao]:
    out = []
    for r in registros:
        c = r.conteudo
        if c.previsao is None:
            continue
        dt = DefinicaoTemporal(c.janela.malha(cfg.malha))
        for x in validar_separacao(c.previsao, verdade, dt):
            if x.severidade == "erro":
                out.append(erro(x.codigo, f"janelas[{c.posicao}].{x.caminho}", x.mensagem))
            elif cfg.rotulo_informacao == "causal" and x.codigo == "previsao_perfeita_declarada":
                out.append(erro("oraculo_em_missao_causal", f"janelas[{c.posicao}]", x.mensagem))
            else:
                out.append(aviso(x.codigo, f"janelas[{c.posicao}].{x.caminho}", x.mensagem))
    return out


@dataclass(frozen=True)
class ResultadoIntervencao:
    k_corte: int
    janelas_comparadas: int
    divergencias: tuple[tuple[int, int, str], ...]       # (posição, k, artefato divergente)
    constatacoes: tuple[Constatacao, ...]

    @property
    def nao_antecipativo(self) -> bool:
        return not any(c.severidade == "erro" for c in self.constatacoes)


def verdades_iguais_ate(va: Realizacao, vb: Realizacao, k_corte: int, delta_s: int) -> bool:
    for s in va.series:
        o = vb.serie(s.uid, s.grandeza)
        if o is None or o.serie.inicio_utc != s.serie.inicio_utc or o.serie.passo_s != s.serie.passo_s:
            return False
        if tuple(s.serie.valores[:k_corte]) != tuple(o.serie.valores[:k_corte]):
            return False
    return {(s.uid, s.grandeza) for s in va.series} == {(s.uid, s.grandeza) for s in vb.series}


def verificar_nao_antecipatividade(executar_com_verdade, verdade_a: Realizacao, verdade_b: Realizacao,
                                   k_corte: int) -> ResultadoIntervencao:
    """``executar_com_verdade(verdade) -> ResultadoMissaoMPC`` deve montar a MESMA missão (configuração, modelo,
    provedor, canal) variando só a verdade. Toda decisão em τ_k com k <= k_corte depende apenas de observações de
    intervalos < k_corte ⇒ instantâneo, previsão, entrada e plano idênticos nas duas execuções."""
    c: list[Constatacao] = []
    if not verdades_iguais_ate(verdade_a, verdade_b, k_corte, 0):
        c.append(erro("intervencao_invalida", "verdades", "As verdades diferem antes da fronteira de corte."))
        return ResultadoIntervencao(k_corte, 0, (), tuple(c))
    ra, rb = executar_com_verdade(verdade_a), executar_com_verdade(verdade_b)
    div = []
    n = 0
    for xa, xb in zip(ra.registros, rb.registros):
        a, b = xa.conteudo, xb.conteudo
        if a.janela.k != b.janela.k or a.janela.k > k_corte:
            break
        n += 1
        for nome in ("hash_instantaneo", "hash_previsao", "hash_entrada_3c1", "hash_plano"):
            if getattr(a, nome) != getattr(b, nome):
                div.append((a.posicao, a.janela.k, nome))
                c.append(erro("dependencia_de_informacao_futura", f"janelas[{a.posicao}].{nome}",
                              f"Decisão em τ_{a.janela.k} mudou quando só a realização a partir de τ_{k_corte} mudou."))
    return ResultadoIntervencao(k_corte, n, tuple(div), tuple(c))


__all__ = ["RelatorioAuditoriaMissao", "ResultadoIntervencao", "auditar_missao", "custo_realizado_independente",
           "verdades_iguais_ate", "verificar_nao_antecipatividade"]
_ = verificar_cadeia_janelas
