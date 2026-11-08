"""Auditor algébrico INDEPENDENTE (especificação v1.0 §17; requisito R32; ordem executiva 3A.4).

Recebe a entrada canônica e uma atribuição CANDIDATA explícita (valores por UID) e mede resíduos, em unidades
físicas, de: compatibilidade temporal (N intervalos, N+1 estados), balanço M02, renováveis M03-v1.1, serviço e
descarte M04, exclusividade/limites BESS M06, recorrência M07, limites e estado inicial M08, KPIs de
indisponibilidade/curtailment e custo de curtailment operacional (M21-v1.1). Domínio ON/OFF e vazão PWL (M10,
M15/M16) são auditados em ``auditar_pwl`` (caso A06).

**Não é solver, não gera despacho, não corrige valores.** Nunca recorta (clip); toda violação acima da tolerância
rejeita a candidata. Famílias não implementadas no Piso 3A (commitment M09/M11/M12, auxiliares M05, multimodo,
terminal, H2 em estoque) → ``nao_suportado`` e rejeição.

Independência (condição A): implementação em ponto flutuante, com durações em SEGUNDOS (h = Δs/3600), busca
binária na PWL e sem importar ``ems_v2.reference`` (verificado por teste de AST). As tolerâncias são PROVISÓRIAS
(dossiê v1.0 "Métricas algébricas", propostas pré-registráveis; decisão D07 pendente) e separadas por grandeza.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field

from . import ROTULO_EVIDENCIA
from .contracts import EntradaModeloEMS, EspecGerador, validar_entrada, validar_gerador
from .diagnostics import Constatacao, erro, pendente
from .series import alinhar_a_malha
from .timegrid import MalhaTemporal


@dataclass(frozen=True)
class Tolerancias:
    """Tolerâncias PROVISÓRIAS por grandeza (nunca uma tolerância única para grandezas heterogêneas)."""
    potencia_abs_kW: float = 1e-5          # balanço/potência: 1e-5 kW + 1e-7 P_scale
    potencia_rel_escala: float = 1e-7
    energia_abs_kWh: float = 1e-6          # recorrência por banco: 1e-6 kWh + 1e-8 C_b
    energia_rel_capacidade: float = 1e-8
    soc_fracao: float = 1e-6               # violação de cotas de SOC (fração)
    custo_abs_R: float = 1e-4              # custo: 1e-4 R$ + 1e-7 max(1 R$, |J|)
    custo_rel: float = 1e-7
    binario: float = 1e-6                  # distância ao inteiro
    vazao_abs_kg_h: float = 1e-6           # PROPOSTA 3A (o dossiê não fixa valor): 1e-6 kg/h + 1e-8 Q_max
    vazao_rel_qmax: float = 1e-8
    massa_abs_kg: float = 1e-9             # PROPOSTA 3A: 1e-9 kg + 1e-8 massa
    status: str = "provisoria"
    origem: str = ("dossiê v1.0, Campanha de validação — Métricas algébricas (propostas pré-registráveis); "
                   "vazão/massa: proposta do Piso 3A; decisão D07 pendente")


CAMPOS_TOLERANCIA = ("potencia_abs_kW", "potencia_rel_escala", "energia_abs_kWh", "energia_rel_capacidade", "soc_fracao",
                     "custo_abs_R", "custo_rel", "binario", "vazao_abs_kg_h", "vazao_rel_qmax", "massa_abs_kg")


def validar_tolerancias(tol) -> list[Constatacao]:
    """C-3A-02: toda tolerância deve ser número real finito e >= 0. Inválida ⇒ rejeição explícita (nunca aprova
    a candidata nem causa falha não controlada). Os valores provisórios não são alterados aqui."""
    if not isinstance(tol, Tolerancias):
        return [erro("tolerancia_invalida", "tolerancias", f"Esperado Tolerancias; recebido {type(tol).__name__}.")]
    out: list[Constatacao] = []
    for nome in CAMPOS_TOLERANCIA:
        v = getattr(tol, nome)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            out.append(erro("tolerancia_invalida", f"tolerancias.{nome}", f"Não numérica: {v!r}."))
        elif not math.isfinite(v):
            out.append(erro("tolerancia_invalida", f"tolerancias.{nome}", f"Não finita: {v!r}."))
        elif v < 0:
            out.append(erro("tolerancia_invalida", f"tolerancias.{nome}", f"Negativa: {v!r}."))
    return out


@dataclass(frozen=True)
class Residuo:
    familia: str
    equacao: str
    uid: str
    indice: int | None
    valor: float
    unidade: str
    tolerancia: float

    @property
    def aprovado(self) -> bool:
        return math.isfinite(self.valor) and abs(self.valor) <= self.tolerancia


@dataclass(frozen=True)
class RelatorioAuditoria:
    aceito: bool
    reprovados: tuple[Residuo, ...]
    maximos: dict[str, tuple[float, str, float]]        # família → (|resíduo| máx., unidade, tolerância)
    constatacoes: tuple[Constatacao, ...]
    familias_verificadas: tuple[str, ...]
    familias_nao_suportadas: tuple[str, ...]
    custos_reconstruidos: dict[str, float] = field(default_factory=dict)
    kpis_reconstruidos: dict[str, dict[str, float]] = field(default_factory=dict)
    rotulo: str = ROTULO_EVIDENCIA
    familias_nao_modeladas: tuple[str, ...] = ()   # fora da formulação auditada (declaradas, não certificadas)

    def codigos(self) -> set[str]:
        return {c.codigo for c in self.constatacoes}

    def familias_reprovadas(self) -> set[str]:
        return {r.familia for r in self.reprovados}


@dataclass(frozen=True)
class CandidatoDespacho:
    """Atribuição candidata explícita por UID (todas as chaves exigidas; ausência = rejeição, não zero).

    * ``renovaveis[uid] = {"P_R": N, "C_oper": N}`` [kW]
    * ``baterias[uid] = {"P_c": N, "P_d": N, "e": N+1}`` [kW, kWh]
    * ``demandas[uid] = {"ell": N}`` [kW] carga efetivamente desconectada
    * ``descarte``: N valores [kW] — só se existir dispositivo físico declarado
    * ``custos_reportados``: p. ex. ``{"curtailment_operacional": R$}``
    * ``kpis_reportados``: p. ex. ``{"E_indisp_kWh": {uid: kWh}, "E_curt_oper_kWh": {uid: kWh}}``
    """
    renovaveis: dict[str, dict[str, tuple[float, ...]]] = field(default_factory=dict)
    baterias: dict[str, dict[str, tuple[float, ...]]] = field(default_factory=dict)
    demandas: dict[str, dict[str, tuple[float, ...]]] = field(default_factory=dict)
    descarte: tuple[float, ...] | None = None
    geradores: dict[str, dict[str, tuple[float, ...]]] = field(default_factory=dict)
    auxiliares: tuple[float, ...] | None = None
    custos_reportados: dict[str, float] = field(default_factory=dict)
    kpis_reportados: dict[str, dict[str, float]] = field(default_factory=dict)


class _Coletor:
    def __init__(self) -> None:
        self.residuos: list[Residuo] = []
        self.constatacoes: list[Constatacao] = []
        self.verificadas: set[str] = set()

    def r(self, familia, equacao, uid, i, valor, unidade, tol) -> None:
        self.verificadas.add(familia)
        self.residuos.append(Residuo(familia, equacao, uid, i, float(valor), unidade, float(tol)))

    def limite_superior(self, familia, equacao, uid, i, valor, limite, unidade, tol) -> None:
        """Registra só o EXCESSO acima do limite (resíduo 0 se dentro)."""
        self.r(familia, equacao, uid, i, max(0.0, valor - limite), unidade, tol)

    def limite_inferior(self, familia, equacao, uid, i, valor, limite, unidade, tol) -> None:
        self.r(familia, equacao, uid, i, max(0.0, limite - valor), unidade, tol)


def _vetor(cand: dict, chave: str, n: int, caminho: str, col: _Coletor, terminal: int | None = None) -> list[float] | None:
    if not isinstance(cand, dict) or chave not in cand or cand[chave] is None:
        col.constatacoes.append(erro("variavel_candidata_ausente", caminho,
                                     f"'{chave}' ausente na candidata (ausência nunca vira zero)."))
        return None
    v = cand[chave]
    try:
        m = len(v)
    except TypeError:
        col.constatacoes.append(erro("vetor_invalido", caminho, "Vetor não sequencial."))
        return None
    if m != n:
        cod = "instante_terminal_como_intervalo" if terminal is not None and m == terminal else "comprimento_incompativel"
        col.constatacoes.append(erro(cod, caminho, f"Esperados {n} valores; recebidos {m}."))
        return None
    out = []
    for i, x in enumerate(v):
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
            col.constatacoes.append(erro("valor_ausente_ou_nao_finito", f"{caminho}[{i}]", "NaN/Inf/não numérico."))
            return None
        out.append(float(x))
    return out


def _dur_h(malha: MalhaTemporal) -> float:
    return malha.delta_s / 3600.0


def _tol_custo(tol: Tolerancias, J: float) -> float:
    return tol.custo_abs_R + tol.custo_rel * max(1.0, abs(J))


def _finalizar(col: _Coletor, nao_suportadas: list[str], custos=None, kpis=None, nao_modeladas=()) -> RelatorioAuditoria:
    reprov = tuple(r for r in col.residuos if not r.aprovado)
    maximos: dict[str, tuple[float, str, float]] = {}
    for r in col.residuos:
        cur = maximos.get(r.familia)
        if cur is None or abs(r.valor) > cur[0]:
            maximos[r.familia] = (abs(r.valor), r.unidade, r.tolerancia)
    bloqueia = any(c.severidade in ("erro", "pendente") for c in col.constatacoes)
    return RelatorioAuditoria(aceito=not reprov and not bloqueia and not nao_suportadas, reprovados=reprov,
                              maximos=maximos, constatacoes=tuple(col.constatacoes),
                              familias_verificadas=tuple(sorted(col.verificadas)),
                              familias_nao_suportadas=tuple(nao_suportadas),
                              custos_reconstruidos=custos or {}, kpis_reconstruidos=kpis or {},
                              familias_nao_modeladas=tuple(nao_modeladas))


def auditar(entrada: EntradaModeloEMS, cand: CandidatoDespacho, tol: Tolerancias = Tolerancias(),
            compromisso_fixo: dict | None = None) -> RelatorioAuditoria:
    """``compromisso_fixo`` (perfil 3B-P): programa u por gerador, que DEVE ser constante e igual ao estado inicial.
    Sem ele, geradores continuam ``nao_suportado`` (comportamento 3A). Com ele, o auditor verifica de forma
    independente: fidelidade ao programa e integralidade de u, domínio ON/OFF (M10), vazão PWL (M15/M16) e a
    contribuição de p ao balanço. Rampas (M11) e permanências (M12) NÃO são verificadas e são declaradas em
    ``familias_nao_modeladas``."""
    col = _Coletor()
    ct = validar_tolerancias(tol)
    if ct:
        col.constatacoes += ct
        return _finalizar(col, [])
    rel = validar_entrada(entrada)
    col.constatacoes += [c for c in rel.constatacoes]
    if not rel.aceito:
        return _finalizar(col, [])
    nao_sup: list[str] = []
    if (entrada.geradores or cand.geradores) and compromisso_fixo is None:
        nao_sup.append("commitment_M09_M12")
        col.constatacoes.append(pendente("commitment_nao_suportado_3A", "geradores",
                                         "Transições/rampas/permanências (M09–M12) não são auditáveis no Piso 3A; "
                                         "domínio PWL isolado: usar auditar_pwl."))
    if cand.auxiliares is not None:
        nao_sup.append("auxiliares_M05")
        col.constatacoes.append(pendente("auxiliares_nao_suportados_3A", "auxiliares", "M05 é futuro."))
    if nao_sup:
        return _finalizar(col, nao_sup)

    m = entrada.malha
    N, h = m.N, _dur_h(m)
    # ------------------------------------------------ dados exógenos alinhados (contrato já validado)
    L = {str(d.uid): alinhar_a_malha(d.potencia, m, "")[0] for d in entrada.demandas}
    chi = {}
    for d in entrada.demandas:
        if entrada.politica_servico.modo == "duro" or d.criticidade == "critica" or d.fracao_interrompivel is None:
            chi[str(d.uid)] = [0.0] * N
        else:
            chi[str(d.uid)] = list(alinhar_a_malha(d.fracao_interrompivel, m, "")[0])
    A = {str(r.uid): alinhar_a_malha(r.potencial, m, "")[0] for r in entrada.renovaveis}
    aR = {str(r.uid): alinhar_a_malha(r.disponibilidade.serie, m, "")[0] for r in entrada.renovaveis}
    aB = {str(b.uid): alinhar_a_malha(b.disponibilidade.serie, m, "")[0] for b in entrada.baterias}
    P_scale = max([1.0] + [sum(L[k][t] for k in L) for t in range(N)] + [sum(A[k][t] for k in A) for t in range(N)]
                  + [max(float(b.p_carga_max_kW.valor), float(b.p_descarga_max_kW.valor)) for b in entrada.baterias]
                  + [float(g.p_max_kW.valor) for g in entrada.geradores])
    tolP = tol.potencia_abs_kW + tol.potencia_rel_escala * P_scale

    # ------------------------------------------------ chaves esperadas × fornecidas (por UID)
    for nome, esperados, dados in (("renovaveis", set(A), cand.renovaveis), ("baterias", set(aB), cand.baterias),
                                   ("demandas", set(L), cand.demandas)):
        for k in sorted(set(dados) - esperados):
            col.constatacoes.append(erro("uid_desconhecido_na_candidata", f"{nome}[{k}]", "UID inexistente na entrada."))
        for k in sorted(esperados - set(dados)):
            col.constatacoes.append(erro("variavel_candidata_ausente", f"{nome}[{k}]", "UID sem valores na candidata."))

    gen = [0.0] * N
    carga = [0.0] * N
    # ------------------------------------------------ renováveis M03-v1.1
    kpi_ind: dict[str, float] = {}
    kpi_cur: dict[str, float] = {}
    custo_curt = 0.0
    custo_curt_ok = True
    for r in entrada.renovaveis:
        k = str(r.uid)
        c = cand.renovaveis.get(k, {})
        P = _vetor(c, "P_R", N, f"renovaveis[{k}].P_R", col, N + 1)
        C = _vetor(c, "C_oper", N, f"renovaveis[{k}].C_oper", col, N + 1)
        Ak, ak = A[k], aR[k]
        kpi_ind[k] = sum((1.0 - ak[t]) * Ak[t] for t in range(N)) * h
        if P is None or C is None:
            continue
        for t in range(N):
            gen[t] += P[t]
            disp = ak[t] * Ak[t]
            res = P[t] + C[t] - disp
            col.r("renovavel", "M03-v1.1", k, t, res, "kW", tolP)
            col.limite_inferior("renovavel", "M03-v1.1", k, t, P[t], 0.0, "kW", tolP)
            col.limite_inferior("renovavel", "M03-v1.1", k, t, C[t], 0.0, "kW", tolP)
            if ak[t] == 0.0 and C[t] > tolP:
                col.constatacoes.append(erro("indisponibilidade_registrada_como_curtailment",
                                             f"renovaveis[{k}].C_oper[{t}]",
                                             "a = 0: potência indisponível não é vertimento operacional (B01)."))
        kpi_cur[k] = sum(C) * h
        if r.custo_curtailment is not None and r.custo_curtailment.valor is not None:
            custo_curt += float(r.custo_curtailment.valor) * kpi_cur[k]
        else:
            custo_curt_ok = False
    # ------------------------------------------------ demanda e serviço M04
    for d in entrada.demandas:
        k = str(d.uid)
        ell = _vetor(cand.demandas.get(k, {}), "ell", N, f"demandas[{k}].ell", col, N + 1)
        if ell is None:
            continue
        for t in range(N):
            carga[t] += L[k][t] - ell[t]
            col.limite_inferior("servico", "M04", k, t, ell[t], 0.0, "kW", tolP)
            lim = chi[k][t] * L[k][t]
            col.limite_superior("servico", "M04", k, t, ell[t], lim, "kW", tolP)
            if ell[t] > lim + tolP and lim == 0.0:
                col.constatacoes.append(erro("interrupcao_nao_autorizada", f"demandas[{k}].ell[{t}]",
                                             "Carga desconectada sem autorização (crítica ou serviço duro)."))
    # ------------------------------------------------ descarte M04: 0 <= d <= D̄ SEMPRE (C-3A-01)
    # D̄ = 0 sem dispositivo físico declarado (adenda v1.1; D03). d é CONSUMO no barramento (lado direito de M02):
    # d < 0 seria geração fictícia e é rejeitado com ou sem dispositivo.
    desc = entrada.politica_servico.descarte
    if desc is not None and cand.descarte is None:
        col.constatacoes.append(erro("variavel_candidata_ausente", "descarte",
                                     "Dispositivo de descarte declarado: a candidata deve informar d (ausência ≠ zero)."))
    elif cand.descarte is not None:
        dv = _vetor({"d": cand.descarte}, "d", N, "descarte", col, N + 1)
        if dv is not None:
            Dmax = 0.0 if desc is None else float(desc.p_max_kW.valor)
            uid_d = "-" if desc is None else str(desc.uid)
            for t in range(N):
                carga[t] += dv[t]
                col.limite_inferior("descarte", "M04", uid_d, t, dv[t], 0.0, "kW", tolP)
                col.limite_superior("descarte", "M04", uid_d, t, dv[t], Dmax, "kW", tolP)
            if any(x < -tolP for x in dv):
                col.constatacoes.append(erro("descarte_negativo", "descarte",
                                             "d < 0: descarte negativo atuaria como geração fictícia (M04 exige d >= 0)."))
            if desc is None and any(x > tolP for x in dv):
                col.constatacoes.append(erro("descarte_sem_dispositivo_fisico", "descarte",
                                             "D̄ = 0: não existe sumidouro físico declarado (energia fictícia)."))
    # ------------------------------------------------ BESS M06–M08
    estados = {str(s.uid): s for s in entrada.estados_baterias}
    for b in entrada.baterias:
        k = str(b.uid)
        c = cand.baterias.get(k, {})
        Pc = _vetor(c, "P_c", N, f"baterias[{k}].P_c", col, N + 1)
        Pd = _vetor(c, "P_d", N, f"baterias[{k}].P_d", col, N + 1)
        e = _vetor(c, "e", N + 1, f"baterias[{k}].e", col)
        if Pc is None or Pd is None or e is None:
            continue
        Cb = float(b.capacidade_kWh.valor)
        smin, smax = float(b.soc_min.valor), float(b.soc_max.valor)
        ec, ed = float(b.eta_carga.valor), float(b.eta_descarga.valor)
        pcm, pdm = float(b.p_carga_max_kW.valor), float(b.p_descarga_max_kW.valor)
        alpha = 1.0 if b.hipotese_autodescarga == "nao_modelada_alpha_1" else math.exp(
            -float(b.autodescarga_1_h.valor) * h)
        tolE = tol.energia_abs_kWh + tol.energia_rel_capacidade * Cb
        tolS = tol.soc_fracao * Cb       # violação de SOC expressa em kWh equivalentes
        for t in range(N):
            gen[t] += Pd[t] - Pc[t]
            col.limite_inferior("bess_potencia", "M06", k, t, Pc[t], 0.0, "kW", tolP)
            col.limite_inferior("bess_potencia", "M06", k, t, Pd[t], 0.0, "kW", tolP)
            col.limite_superior("bess_potencia", "M06", k, t, Pc[t], aB[k][t] * pcm, "kW", tolP)
            col.limite_superior("bess_potencia", "M06", k, t, Pd[t], aB[k][t] * pdm, "kW", tolP)
            col.r("bess_exclusividade", "M06", k, t, min(Pc[t], Pd[t]), "kW", tolP)
            prev = alpha * e[t] + h * ec * Pc[t] - h * Pd[t] / ed
            col.r("bess_energia", "M07", k, t, e[t + 1] - prev, "kWh", tolE)
        col.r("bess_estado_inicial", "M08", k, 0, e[0] - float(estados[k].energia_kWh.valor), "kWh", tolE)
        for i, x in enumerate(e):
            col.limite_inferior("bess_soc", "M08", k, i, x, Cb * smin, "kWh", tolS)
            col.limite_superior("bess_soc", "M08", k, i, x, Cb * smax, "kWh", tolS)
    # ------------------------------------------------ geradores com compromisso FIXO (perfil 3B-P)
    nao_modeladas: tuple[str, ...] = ()
    vazoes: dict[str, list[float]] = {}
    if entrada.geradores or cand.geradores:
        nao_modeladas = ("rampas_M11", "permanencias_M12")
        _auditar_geradores(entrada, cand, compromisso_fixo or {}, col, N, gen, tolP, tol, vazoes)
    # ------------------------------------------------ balanço M02
    for t in range(N):
        col.r("balanco", "M02", "barramento", t, gen[t] - carga[t], "kW", tolP)
    # ------------------------------------------------ custos e KPIs reconstruídos
    custos: dict[str, float] = {}
    if custo_curt_ok and entrada.renovaveis:
        custos["curtailment_operacional"] = custo_curt
    custos.update(_custos_3bp(entrada, cand, h, N, vazoes))
    termos = entrada.politica_objetivo.termos
    if all(t in custos for t in termos):
        custos["total"] = sum(custos[t] for t in termos)
    for nome, rep in cand.custos_reportados.items():
        if nome not in RECONSTRUTIVEIS:
            col.constatacoes.append(pendente("custo_nao_reconstruivel_3A", f"custos_reportados[{nome}]",
                                             "Termo de custo sem reconstrução independente."))
        elif nome not in custos:
            col.constatacoes.append(erro("custo_nao_reconstruivel", f"custos_reportados[{nome}]",
                                         "Coeficiente ausente: custo reportado não pode ser conferido."))
        else:
            col.r("custo", RECONSTRUTIVEIS[nome], nome, None, float(rep) - custos[nome], "R$",
                  _tol_custo(tol, custos[nome]))
    if "curtailment_operacional" in entrada.politica_objetivo.termos and \
            "curtailment_operacional" not in cand.custos_reportados:
        col.constatacoes.append(Constatacao("custo_nao_reportado", "custos_reportados",
                                            "Termo no objetivo sem valor reportado: só reconstruído.", "aviso"))
    kpis = {"E_indisp_kWh": kpi_ind, "E_curt_oper_kWh": kpi_cur}
    for nome, por_uid in cand.kpis_reportados.items():
        if nome not in kpis:
            col.constatacoes.append(erro("kpi_desconhecido", f"kpis_reportados[{nome}]", "KPI não reconstruível."))
            continue
        for k, v in por_uid.items():
            if k not in kpis[nome]:
                col.constatacoes.append(erro("kpi_uid_desconhecido", f"kpis_reportados[{nome}][{k}]", "UID sem KPI."))
                continue
            col.r("kpi_energia", "B01", k, None, float(v) - kpis[nome][k], "kWh",
                  tol.energia_abs_kWh + tol.energia_rel_capacidade * max(1.0, abs(kpis[nome][k])))
    return _finalizar(col, [], custos, kpis, nao_modeladas)


RECONSTRUTIVEIS = {"curtailment_operacional": "M21-v1.1", "throughput_bess": "M21-v1.1",
                   "energia_nao_suprida": "M21-v1.1", "combustivel_h2": "B05-INST", "total": "M21-v1.1"}


def _custos_3bp(entrada, cand, h, N, vazoes) -> dict[str, float]:
    """Reconstrução independente (R$) dos termos do perfil 3B-P a partir da candidata e dos coeficientes declarados.
    Um termo só é reconstruído se TODOS os coeficientes necessários existirem (nunca zero presumido)."""
    out: dict[str, float] = {}
    if entrada.baterias and all(b.custo_throughput is not None and b.custo_throughput.valor is not None
                                for b in entrada.baterias):
        tot = 0.0
        for b in entrada.baterias:
            c = cand.baterias.get(str(b.uid), {})
            if c.get("P_c") is None or c.get("P_d") is None:
                break
            tot += float(b.custo_throughput.valor) * h * (sum(c["P_c"]) + sum(c["P_d"]))
        else:
            out["throughput_bess"] = tot
    elif not entrada.baterias:
        out["throughput_bess"] = 0.0
    inter = [d for d in entrada.demandas if d.criticidade == "interrompivel"]
    if all(d.custo_energia_nao_suprida is not None and d.custo_energia_nao_suprida.valor is not None for d in inter):
        tot = 0.0
        for d in inter:
            ell = cand.demandas.get(str(d.uid), {}).get("ell")
            if ell is None:
                break
            tot += float(d.custo_energia_nao_suprida.valor) * h * sum(ell)
        else:
            out["energia_nao_suprida"] = tot
    pem = [g for g in entrada.geradores if g.tecnologia == "pemfc"]
    if all(g.preco_h2 is not None and g.preco_h2.valor is not None and str(g.uid) in vazoes for g in pem):
        out["combustivel_h2"] = sum(float(g.preco_h2.valor) * h * sum(vazoes[str(g.uid)]) for g in pem)
    return out


def _auditar_geradores(entrada, cand, prog_all, col, N, gen, tolP, tol, vazoes) -> None:
    estados = {str(s.uid): s for s in entrada.estados_geradores}
    m = entrada.malha
    for k in sorted(set(cand.geradores) - {str(g.uid) for g in entrada.geradores}):
        col.constatacoes.append(erro("uid_desconhecido_na_candidata", f"geradores[{k}]", "UID inexistente na entrada."))
    for g in entrada.geradores:
        k = str(g.uid)
        prog = prog_all.get(k)
        if not isinstance(prog, (list, tuple)) or len(prog) != N or any(
                isinstance(x, bool) or x not in (0, 1) for x in prog):
            col.constatacoes.append(erro("compromisso_invalido", f"compromisso[{k}]",
                                         f"Programa ausente ou inválido (exigidos {N} valores em {{0, 1}})."))
            continue
        if any(x != int(bool(estados[k].ligado)) for x in prog):
            col.constatacoes.append(pendente("transicao_nao_modelada_3BP", f"compromisso[{k}]",
                                             "Programa com transição: M09/M11/M12 não auditáveis no 3B-P."))
            continue
        a = alinhar_a_malha(g.disponibilidade.serie, m, "")[0]
        c = cand.geradores.get(k, {})
        u = _vetor(c, "u", N, f"geradores[{k}].u", col, N + 1)
        p = _vetor(c, "p", N, f"geradores[{k}].p", col, N + 1)
        curva = g.curva_h2
        q = _vetor(c, "q", N, f"geradores[{k}].q", col, N + 1) if curva is not None else None
        if curva is None and isinstance(c, dict) and c.get("q") is not None:
            col.constatacoes.append(erro("vazao_sem_curva", f"geradores[{k}].q", "Vazão informada sem curva PWL."))
        if u is None or p is None or (curva is not None and q is None):
            continue
        pmin, pmax = float(g.p_min_kW.valor), float(g.p_max_kW.valor)
        Ps = [float(v[0]) for v in curva.vertices] if curva is not None else []
        Qs = [float(v[1]) for v in curva.vertices] if curva is not None else []
        tolQ = tol.vazao_abs_kg_h + tol.vazao_rel_qmax * (max(Qs) if Qs else 0.0)
        for t in range(N):
            gen[t] += p[t]
            col.r("integralidade", "M09", k, t, min(abs(u[t]), abs(u[t] - 1.0)), "1", tol.binario)
            col.r("compromisso_fixo", "M09", k, t, u[t] - prog[t], "1", tol.binario)
            if prog[t] == 1 and a[t] != 1.0:
                col.constatacoes.append(erro("on_indisponivel", f"geradores[{k}].u[{t}]", "Unidade ON com a = 0."))
            if prog[t] == 0:
                col.r("dominio_on_off", "M10", k, t, p[t], "kW", tolP)
                if q is not None:
                    col.r("vazao_pwl", "M16", k, t, q[t], "kg/h", tolQ)
                continue
            lo, hi = (max(pmin, Ps[0]), min(pmax, Ps[-1])) if Ps else (pmin, pmax)
            col.limite_inferior("dominio_on_off", "M10", k, t, p[t], lo, "kW", tolP)
            col.limite_superior("dominio_on_off", "M10", k, t, p[t], hi, "kW", tolP)
            if p[t] < lo - tolP or p[t] > hi + tolP:
                col.constatacoes.append(erro("on_fora_do_dominio", f"geradores[{k}].p[{t}]",
                                             f"ON em {p[t]} kW fora de [{lo}, {hi}] kW."))
            elif q is not None:
                col.r("vazao_pwl", "M16", k, t, q[t] - _interp_bisect(Ps, Qs, min(max(p[t], Ps[0]), Ps[-1])),
                      "kg/h", tolQ)
        if q is not None:
            vazoes[k] = q


# =============================================================================== PWL (A06)
def _interp_bisect(Ps: list[float], Qs: list[float], p: float) -> float:
    j = bisect.bisect_right(Ps, p) - 1
    j = min(max(j, 0), len(Ps) - 2)
    w = (p - Ps[j]) / (Ps[j + 1] - Ps[j])
    return Qs[j] * (1.0 - w) + Qs[j + 1] * w


def auditar_pwl(g: EspecGerador, malha: MalhaTemporal, u: list, p: list, q: list, massa_kg: list | None = None,
                tol: Tolerancias = Tolerancias()) -> RelatorioAuditoria:
    """Domínio ON/OFF (M10) e vazão PWL (M15/M16) por intervalo; massa operacional h·q (sem eventos).
    Só confere valores PREPARADOS: não escolhe u, p nem q."""
    col = _Coletor()
    ct = validar_tolerancias(tol)
    if ct:
        col.constatacoes += ct
        return _finalizar(col, [])
    col.constatacoes += [c for c in validar_gerador(g, malha, "gerador")]
    if any(c.severidade in ("erro", "pendente") for c in col.constatacoes) or g.curva_h2 is None:
        if g.curva_h2 is None:
            col.constatacoes.append(pendente("curva_h2_ausente", "gerador.curva_h2", "Sem curva PWL."))
        return _finalizar(col, [])
    N, h = malha.N, _dur_h(malha)
    uu = _vetor({"u": u}, "u", N, "u", col, N + 1)
    pp = _vetor({"p": p}, "p", N, "p", col, N + 1)
    qq = _vetor({"q": q}, "q", N, "q", col, N + 1)
    mm = None if massa_kg is None else _vetor({"m": massa_kg}, "m", N, "massa_kg", col, N + 1)
    if uu is None or pp is None or qq is None:
        return _finalizar(col, [])
    Ps = [float(v[0]) for v in g.curva_h2.vertices]
    Qs = [float(v[1]) for v in g.curva_h2.vertices]
    pmin, pmax = float(g.p_min_kW.valor), float(g.p_max_kW.valor)
    P_scale = max(1.0, pmax)
    tolP = tol.potencia_abs_kW + tol.potencia_rel_escala * P_scale
    tolQ = tol.vazao_abs_kg_h + tol.vazao_rel_qmax * max(Qs)
    disp = alinhar_a_malha(g.disponibilidade.serie, malha, "")[0]
    for t in range(N):
        col.r("integralidade", "M09", str(g.uid), t, min(abs(uu[t]), abs(uu[t] - 1.0)), "1", tol.binario)
        on = uu[t] > 0.5
        if on and disp[t] == 0.0:
            col.constatacoes.append(erro("on_indisponivel", f"u[{t}]", "Unidade ON com a = 0."))
        if not on:
            col.r("dominio_on_off", "M10", str(g.uid), t, pp[t], "kW", tolP)
            col.r("vazao_pwl", "M16", str(g.uid), t, qq[t], "kg/h", tolQ)
            if mm is not None:
                col.r("massa_h2", "M17", str(g.uid), t, mm[t], "kg", tol.massa_abs_kg)
            continue
        lo, hi = max(pmin, Ps[0]), min(pmax, Ps[-1])
        col.limite_inferior("dominio_on_off", "M10", str(g.uid), t, pp[t], lo, "kW", tolP)
        col.limite_superior("dominio_on_off", "M10", str(g.uid), t, pp[t], hi, "kW", tolP)
        if pp[t] < lo - tolP or pp[t] > hi + tolP:
            col.constatacoes.append(erro("on_fora_do_dominio", f"p[{t}]",
                                         f"ON em {pp[t]} kW fora de [{lo}, {hi}] kW (sem segmento até zero)."))
            continue
        col.r("vazao_pwl", "M16", str(g.uid), t, qq[t] - _interp_bisect(Ps, Qs, pp[t]), "kg/h", tolQ)
        if mm is not None:
            alvo = qq[t] * h
            col.r("massa_h2", "M17", str(g.uid), t, mm[t] - alvo, "kg", tol.massa_abs_kg + 1e-8 * abs(alvo))
    return _finalizar(col, [])


__all__ = ["CAMPOS_TOLERANCIA", "CandidatoDespacho", "RelatorioAuditoria", "Residuo", "Tolerancias", "auditar",
           "auditar_pwl", "validar_tolerancias"]
