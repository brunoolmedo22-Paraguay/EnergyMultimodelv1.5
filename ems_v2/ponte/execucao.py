"""Contrato PLANO → EXECUÇÃO → ESTADO (3C-0 §3.4).

Três conceitos distintos, cada um com seu tipo:

* **Plano** (``PlanoDespacho``) — decisões CALCULADAS pelo otimizador para uma janela (consignas por recurso e por
  intervalo, N valores; trajetórias de estado planejadas, N+1 valores). Só nasce de um resultado ACEITO (despacho
  aprovado pelo auditor 3A e pela integridade 3B-P) e é ligado ao SHA-256 da entrada que o gerou.
* **Execução** — aplicação das consignas por um ``ExecutorPasso``. O executor recebe a consigna do intervalo e as
  condições REALIZADAS do entorno (nunca a previsão) e devolve o que foi efetivamente aplicado e o estado seguinte.
  Nenhum executor pode "corrigir" uma consigna inexequível em silêncio: inexequível ⇒ execução interrompida, sem
  recorte (clip) e sem política de controle inventada.
* **Estado** (``EstadoMicrorrede``) — condição na fronteira k (instante τ_k = τ_0 + kΔ), com índice GLOBAL de
  fronteira, transportado entre intervalos, janelas e retomadas.

Checkpoints (``Checkpoint``) são selados (SHA-256 do conteúdo) e encadeados (hash do anterior + hash cumulativo dos
passos aplicados): retomar a partir de um checkpoint reproduz exatamente a execução contínua, ou é recusado.

``ExecutorAlgebricoReferencia`` é um DUBLÊ DE TESTE algébrico (recorrência M07 com os parâmetros declarados, limites
M06/M08/M10, balanço M02 com a demanda realizada): serve para provar a continuidade dos contratos. **Não é modelo
físico** (natureza ``algebrico_referencia``); a evolução física virá por adaptadores específicos (``modelo_fisico``)
validados em fases posteriores.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import Protocol

from ..audit import Tolerancias
from ..contracts import EntradaModeloEMS, hash_entrada
from ..diagnostics import Constatacao, ContratoInvalido, aviso, erro
from ..timegrid import ler_instante_utc
from . import CONTRATO_VERSAO
from .canonico import json_canonico, sha256
from .cenario import Realizacao

GRANDEZAS_CONSIGNA = {
    "P_R": ("kW", "renovavel", "Potência renovável usada (injeta no barramento)"),
    "P_c": ("kW", "armazenamento", "Potência de carga (consome do barramento)"),
    "P_d": ("kW", "armazenamento", "Potência de descarga (injeta no barramento)"),
    "u": ("1", "gerador", "Estado ON/OFF comandado"),
    "p": ("kW", "gerador", "Potência líquida do gerador"),
    "ell": ("kW", "demanda", "Corte de carga autorizado"),
    "d": ("kW", "descarte", "Descarte em dispositivo físico declarado"),
}
GRANDEZAS_ESTADO_PLANO = {"e": ("kWh", "armazenamento", "Energia armazenada na fronteira")}
NATUREZAS_EXECUTOR = {"algebrico_referencia": "Dublê algébrico de teste — NÃO é modelo físico",
                      "modelo_fisico": "Adaptador de modelo físico validado (fase posterior)"}
SITUACOES = {"concluida": "Todos os intervalos pedidos foram aplicados",
             "pausada_aguardando_observacoes": "Próximo intervalo termina depois de observado_ate_utc (online): pausa "
                                               "no último estado válido; retomar do checkpoint com nova observação. "
                                               "NÃO é inviabilidade",
             "interrompida_inexequivel": "Consigna inexequível nas condições realizadas: execução interrompida "
                                         "no último estado válido (nada foi recortado)",
             "erro_dados": "Dados realizados ausentes, desalinhados ou ilegíveis num intervalo que deveria estar "
                           "observado (integridade): execução parada no último estado válido"}


# ------------------------------------------------------------------------------------------------ plano
@dataclass(frozen=True)
class ConsignaRecurso:
    uid: str
    grandeza: str
    unidade: str
    valores: tuple[float, ...]          # N intervalos


@dataclass(frozen=True)
class TrajetoriaPlanejada:
    uid: str
    grandeza: str
    unidade: str
    valores: tuple[float, ...]          # N+1 fronteiras


@dataclass(frozen=True)
class PlanoDespacho:
    versao_contrato: int
    microrrede_uid: str
    cenario_uid: str
    hash_entrada: str
    motor_id: str
    versao_formulacao: str
    classificacao: str
    estado_despacho: str
    inicio_utc: str
    delta_s: int
    N: int
    indice_fronteira_inicial: int        # índice GLOBAL da fronteira em que o plano começa (0 na 1ª janela)
    consignas: tuple[ConsignaRecurso, ...]
    estados_planejados: tuple[TrajetoriaPlanejada, ...]
    custo_objetivo_planejado: dict[str, float]   # termos do OBJETIVO do plano — não é custo realizado

    def consigna(self, uid: str, grandeza: str) -> ConsignaRecurso | None:
        return next((c for c in self.consignas if c.uid == uid and c.grandeza == grandeza), None)


def _finito(v) -> bool:
    return not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)


def validar_plano(p: PlanoDespacho, tol: Tolerancias = Tolerancias()) -> list[Constatacao]:
    out: list[Constatacao] = []
    if p.versao_contrato != CONTRATO_VERSAO:
        out.append(erro("versao_contrato_incompativel", "plano.versao_contrato", f"{p.versao_contrato!r}."))
    if isinstance(p.N, bool) or not isinstance(p.N, int) or p.N < 1:
        return out + [erro("plano_N_invalido", "plano.N", f"{p.N!r}.")]
    if isinstance(p.delta_s, bool) or not isinstance(p.delta_s, int) or p.delta_s <= 0:
        out.append(erro("plano_delta_invalido", "plano.delta_s", f"{p.delta_s!r}."))
    if isinstance(p.indice_fronteira_inicial, bool) or not isinstance(p.indice_fronteira_inicial, int) \
            or p.indice_fronteira_inicial < 0:
        out.append(erro("indice_fronteira_invalido", "plano.indice_fronteira_inicial", f"{p.indice_fronteira_inicial!r}."))
    out += ler_instante_utc(p.inicio_utc, "plano.inicio_utc")[1]
    chaves: set[tuple[str, str]] = set()
    for c in p.consignas:
        cam = f"plano.consignas[{c.uid}:{c.grandeza}]"
        if (c.uid, c.grandeza) in chaves:
            out.append(erro("consigna_duplicada", cam, "Consigna repetida."))
        chaves.add((c.uid, c.grandeza))
        if c.grandeza not in GRANDEZAS_CONSIGNA:
            out.append(erro("grandeza_consigna_desconhecida", cam, f"{c.grandeza!r}."))
            continue
        if c.unidade != GRANDEZAS_CONSIGNA[c.grandeza][0]:
            out.append(erro("unidade_incompativel", cam, f"{c.unidade!r}; exigida {GRANDEZAS_CONSIGNA[c.grandeza][0]!r}."))
        if len(c.valores) == p.N + 1:
            out.append(erro("instante_terminal_como_intervalo", cam, "Consigna com N+1 valores: são N intervalos."))
        elif len(c.valores) != p.N:
            out.append(erro("comprimento_incompativel", cam, f"Esperados {p.N} valores; recebidos {len(c.valores)}."))
        if not all(_finito(v) for v in c.valores):
            out.append(erro("valor_nao_finito", cam, "Consigna NaN/Inf/não numérica (ausente nunca vira zero)."))
        elif c.grandeza == "u" and any(min(abs(v), abs(v - 1)) > tol.binario for v in c.valores):
            out.append(erro("consigna_binaria_fracionaria", cam, "u deve ser 0 ou 1."))
    for t in p.estados_planejados:
        cam = f"plano.estados_planejados[{t.uid}:{t.grandeza}]"
        if t.grandeza not in GRANDEZAS_ESTADO_PLANO or t.unidade != GRANDEZAS_ESTADO_PLANO[t.grandeza][0]:
            out.append(erro("estado_planejado_invalido", cam, f"{t.grandeza!r} [{t.unidade!r}]."))
        if len(t.valores) != p.N + 1:
            out.append(erro("comprimento_incompativel", cam, f"Esperados {p.N + 1} estados; recebidos {len(t.valores)}."))
        if not all(_finito(v) for v in t.valores):
            out.append(erro("valor_nao_finito", cam, "Estado planejado NaN/Inf."))
    return out


def hash_plano(p: PlanoDespacho) -> str:
    return sha256(p)


def plano_de_resultado(res, entrada: EntradaModeloEMS, *, indice_fronteira_inicial: int = 0) -> PlanoDespacho:
    """``ResultadoResolucao`` (3B-P) ACEITO → plano. Rejeitado, sem despacho ou de outra entrada ⇒ ``ContratoInvalido``.

    Só as decisões físicas viram consignas; variáveis auxiliares do MILP (``z_b``, ``δ``, ``θ``) e derivadas
    (``C_oper``, ``q``) ficam fora do plano (são reconstruídas pelo auditor/registro quando necessário)."""
    if not getattr(res, "aceito", False) or getattr(res, "despacho", None) is None:
        raise ContratoInvalido([erro("plano_de_solucao_nao_aceita", "resultado",
                                     f"Estado {getattr(res, 'estado_despacho', '?')!r}: nenhum plano é criado de solução "
                                     "não aceita (auditoria/integridade).")])
    he = hash_entrada(entrada)
    if res.hash_entrada != he:
        raise ContratoInvalido([erro("plano_entrada_divergente", "resultado.hash_entrada",
                                     "O resultado não corresponde à entrada fornecida.")])
    desp, m = res.despacho, entrada.malha
    cons: list[ConsignaRecurso] = []
    est: list[TrajetoriaPlanejada] = []
    for uid in sorted(desp.get("renovaveis", {})):
        cons.append(ConsignaRecurso(uid, "P_R", "kW", tuple(desp["renovaveis"][uid]["P_R"])))
    for uid in sorted(desp.get("baterias", {})):
        b = desp["baterias"][uid]
        cons += [ConsignaRecurso(uid, "P_c", "kW", tuple(b["P_c"])), ConsignaRecurso(uid, "P_d", "kW", tuple(b["P_d"]))]
        est.append(TrajetoriaPlanejada(uid, "e", "kWh", tuple(b["e"])))
    for uid in sorted(desp.get("geradores", {})):
        g = desp["geradores"][uid]
        cons += [ConsignaRecurso(uid, "u", "1", tuple(g["u"])), ConsignaRecurso(uid, "p", "kW", tuple(g["p"]))]
    for uid in sorted(desp.get("demandas", {})):
        cons.append(ConsignaRecurso(uid, "ell", "kW", tuple(desp["demandas"][uid]["ell"])))
    if desp.get("descarte") is not None and entrada.politica_servico.descarte is not None:
        cons.append(ConsignaRecurso(str(entrada.politica_servico.descarte.uid), "d", "kW", tuple(desp["descarte"])))
    p = PlanoDespacho(CONTRATO_VERSAO, entrada.microrrede_uid, entrada.cenario_uid, he, res.motor_id,
                      res.versao_formulacao, res.classificacao, res.estado_despacho, m.inicio().isoformat(), m.delta_s,
                      m.N, indice_fronteira_inicial, tuple(cons), tuple(est), dict(res.custos_modelo))
    c = validar_plano(p)
    if c:
        raise ContratoInvalido(c)
    return p


# ------------------------------------------------------------------------------------------------ estado
@dataclass(frozen=True)
class EstadoArmazenamento:
    uid: str
    energia_kWh: float


@dataclass(frozen=True)
class EstadoGeracao:
    uid: str
    ligado: bool
    potencia_kW: float
    tempo_no_estado_s: int | None = None          # memória operativa (3C-1); None = não rastreada


@dataclass(frozen=True)
class EstadoMicrorrede:
    microrrede_uid: str
    indice_fronteira: int                         # índice GLOBAL k
    instante_utc: str                             # τ_k (UTC, ISO 8601)
    armazenamento: tuple[EstadoArmazenamento, ...]
    geracao: tuple[EstadoGeracao, ...]

    def bateria(self, uid: str) -> EstadoArmazenamento | None:
        return next((b for b in self.armazenamento if b.uid == uid), None)

    def gerador(self, uid: str) -> EstadoGeracao | None:
        return next((g for g in self.geracao if g.uid == uid), None)


def estado_inicial_de_entrada(entrada: EntradaModeloEMS, *, indice_fronteira: int = 0,
                              memoria: dict[str, int] | None = None) -> EstadoMicrorrede:
    """Estado na fronteira inicial a partir dos estados DECLARADOS da entrada (nada inferido)."""
    memoria = memoria or {}
    return EstadoMicrorrede(
        entrada.microrrede_uid, indice_fronteira, entrada.malha.inicio().isoformat(),
        tuple(sorted((EstadoArmazenamento(str(e.uid), float(e.energia_kWh.valor)) for e in entrada.estados_baterias),
                     key=lambda x: x.uid)),
        tuple(sorted((EstadoGeracao(str(e.uid), bool(e.ligado), float(e.p_anterior_kW.valor), memoria.get(str(e.uid)))
                      for e in entrada.estados_geradores), key=lambda x: x.uid)))


def _mesmo_instante(a: str, b: str) -> bool:
    ta, ca = ler_instante_utc(a, "a")
    tb, cb = ler_instante_utc(b, "b")
    return not ca and not cb and ta == tb


# ------------------------------------------------------------------------------------------------ executor
@dataclass(frozen=True)
class PassoAplicado:
    aplicado: dict[str, float]                    # "uid|grandeza" → valor efetivamente aplicado
    estado_final: EstadoMicrorrede
    exequivel: bool
    constatacoes: tuple[Constatacao, ...] = field(default_factory=tuple)
    falha: str = "inexequivel"                    # quando exequivel=False: "inexequivel" (física) | "dados" (integridade)


class ExecutorPasso(Protocol):
    identificador: str
    natureza: str

    def avancar(self, estado: EstadoMicrorrede, consignas: dict[str, float], entorno: dict[str, float],
                delta_s: int) -> PassoAplicado: ...


class ExecutorAlgebricoReferencia:
    """Dublê algébrico (NÃO físico): aplica as consignas tal como planejadas se forem exequíveis nas condições
    REALIZADAS; caso contrário, devolve ``exequivel=False`` sem alterar o estado. Usa só os parâmetros DECLARADOS da
    entrada (nenhum valor presumido)."""
    natureza = "algebrico_referencia"

    def __init__(self, entrada: EntradaModeloEMS, tol: Tolerancias = Tolerancias(), identificador: str = "ref-alg-3C0"):
        self.entrada, self.tol, self.identificador = entrada, tol, identificador
        self._bat = {str(b.uid): b for b in entrada.baterias}
        self._gen = {str(g.uid): g for g in entrada.geradores}
        self._ren = {str(r.uid): r for r in entrada.renovaveis}
        self._dem = {str(d.uid): d for d in entrada.demandas}

    def avancar(self, estado, consignas, entorno, delta_s) -> PassoAplicado:
        tol, h = self.tol, delta_s / 3600.0
        c: list[Constatacao] = []

        def val(k: str, fonte: dict, nome: str) -> float | None:
            v = fonte.get(k)
            if v is None or not _finito(v):
                c.append(erro(f"{nome}_ausente", k, f"{nome} ausente para {k}: nada é presumido."))
                return None
            return float(v)

        escala = max([1.0] + [max(float(v) for v in r.potencial.valores) for r in self._ren.values()]
                     + [float(b.p_descarga_max_kW.valor) for b in self._bat.values()]
                     + [float(g.p_max_kW.valor) for g in self._gen.values()])
        tolP = tol.potencia_abs_kW + tol.potencia_rel_escala * escala
        injecao = 0.0
        for uid, r in self._ren.items():
            p = val(f"{uid}|P_R", consignas, "consigna")
            A, a = val(f"{uid}|potencia", entorno, "realizacao"), val(f"{uid}|disponibilidade", entorno, "realizacao")
            if None in (p, A, a):
                continue
            util = A * a if r.base_potencial == "antes_da_disponibilidade" else A
            if p < -tolP or p > util + tolP:
                c.append(erro("consigna_inexequivel_renovavel", uid,
                              f"P_R = {p} kW fora de [0, {util}] kW realizados (sem recorte)."))
            injecao += p
        novos_b = []
        for uid, b in sorted(self._bat.items()):
            pc, pd = val(f"{uid}|P_c", consignas, "consigna"), val(f"{uid}|P_d", consignas, "consigna")
            st = estado.bateria(uid)
            if st is None:
                c.append(erro("estado_ausente", uid, "Bateria sem estado na fronteira."))
                continue
            if None in (pc, pd):
                continue
            C = float(b.capacidade_kWh.valor)
            if pc < -tolP or pd < -tolP or pc > float(b.p_carga_max_kW.valor) + tolP \
                    or pd > float(b.p_descarga_max_kW.valor) + tolP or min(pc, pd) > tolP:
                c.append(erro("consigna_inexequivel_bateria", uid, f"P_c = {pc}, P_d = {pd} kW fora dos limites M06."))
            alfa = 1.0 if b.hipotese_autodescarga == "nao_modelada_alpha_1" else math.exp(
                -float(b.autodescarga_1_h.valor) * h)
            e1 = alfa * st.energia_kWh + h * (float(b.eta_carga.valor) * pc - pd / float(b.eta_descarga.valor))
            tolE = tol.energia_abs_kWh + tol.energia_rel_capacidade * C
            if not (float(b.soc_min.valor) * C - tolE <= e1 <= float(b.soc_max.valor) * C + tolE):
                c.append(erro("estado_fora_dos_limites", uid, f"e = {e1} kWh fora de [s_min C, s_max C] (sem recorte)."))
            novos_b.append(EstadoArmazenamento(uid, e1))
            injecao += pd - pc
        novos_g = []
        for uid, g in sorted(self._gen.items()):
            u, p = val(f"{uid}|u", consignas, "consigna"), val(f"{uid}|p", consignas, "consigna")
            st = estado.gerador(uid)
            if st is None or None in (u, p):
                if st is None:
                    c.append(erro("estado_ausente", uid, "Gerador sem estado na fronteira."))
                continue
            lig = u > 0.5
            pmin, pmax = float(g.p_min_kW.valor), float(g.p_max_kW.valor)
            if (lig and not pmin - tolP <= p <= pmax + tolP) or (not lig and abs(p) > tolP):
                c.append(erro("consigna_inexequivel_gerador", uid, f"u = {u}, p = {p} kW fora do domínio M10."))
            mem = None if st.tempo_no_estado_s is None else (st.tempo_no_estado_s + delta_s if lig == st.ligado else delta_s)
            novos_g.append(EstadoGeracao(uid, lig, p, mem))
            injecao += p
        demanda = 0.0
        for uid in sorted(self._dem):
            L = val(f"{uid}|potencia", entorno, "realizacao")
            ell = val(f"{uid}|ell", consignas, "consigna")
            if L is not None and ell is not None:
                demanda += L - ell
        desc = sum(float(v) for k, v in consignas.items() if k.endswith("|d"))
        if abs(injecao - demanda - desc) > tolP and not any(x.codigo.endswith("_ausente") for x in c):
            c.append(erro("balanco_realizado_violado", "M02",
                          f"Injeção {injecao} kW ≠ demanda realizada {demanda} kW + descarte {desc} kW: o plano não "
                          "fecha o balanço nas condições REALIZADAS."))
        if c:
            dados = any(x.codigo.endswith("_ausente") for x in c)    # valor/estado ausente = integridade, não física
            return PassoAplicado({}, estado, False, tuple(c), "dados" if dados else "inexequivel")
        k = estado.indice_fronteira + 1
        t1 = ler_instante_utc(estado.instante_utc, "estado")[0] + timedelta(seconds=delta_s)
        novo = EstadoMicrorrede(estado.microrrede_uid, k, t1.isoformat(), tuple(novos_b), tuple(novos_g))
        return PassoAplicado({k_: float(v) for k_, v in sorted(consignas.items())}, novo, True, ())


# ------------------------------------------------------------------------------------------------ checkpoint
@dataclass(frozen=True)
class Checkpoint:
    versao_contrato: int
    execucao_uid: str
    sequencia: int
    hash_plano: str
    cursor_plano: int                              # próximo intervalo do plano a aplicar
    estado: EstadoMicrorrede
    hash_anterior: str | None
    hash_aplicado: str                             # cadeia cumulativa dos passos aplicados
    executor: str                                  # "identificador:natureza"
    selo: str = ""


def selar_checkpoint(c: Checkpoint) -> Checkpoint:
    return replace(c, selo=sha256(replace(c, selo="")))


def verificar_checkpoint(c: Checkpoint) -> list[Constatacao]:
    if c.selo != sha256(replace(c, selo="")):
        return [erro("checkpoint_adulterado", "checkpoint.selo", "Selo não confere com o conteúdo do checkpoint.")]
    return []


def _encadear(anterior: str, obj) -> str:
    return hashlib.sha256((anterior + "|" + json_canonico(obj)).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------ execução
@dataclass(frozen=True)
class PassoRegistrado:
    indice_plano: int
    indice_fronteira: int                          # fronteira GLOBAL no início do intervalo
    aplicado: dict[str, float]


@dataclass(frozen=True)
class DesvioPlanoRealizado:
    uid: str
    grandeza: str
    indice: int                                    # intervalo (consigna) ou fronteira (estado), índice do plano
    planejado: float
    realizado: float
    desvio: float                                  # realizado − planejado


@dataclass(frozen=True)
class TrajetoriaExecutada:
    execucao_uid: str
    hash_plano: str
    executor: str
    cursor_inicial: int
    cursor_final: int
    situacao: str
    estados: tuple[EstadoMicrorrede, ...]          # cursor_final − cursor_inicial + 1 fronteiras
    passos: tuple[PassoRegistrado, ...]            # cursor_final − cursor_inicial intervalos
    desvios: tuple[DesvioPlanoRealizado, ...]
    checkpoints: tuple[Checkpoint, ...]
    constatacoes: tuple[Constatacao, ...] = field(default_factory=tuple)


def entorno_realizado(real: Realizacao, instante_utc: str, delta_s: int) -> tuple[dict[str, float], list[Constatacao]]:
    """Valores REALIZADOS do intervalo que começa em ``instante_utc`` ("uid|grandeza" → valor). Sem reamostragem."""
    t, c = ler_instante_utc(instante_utc, "instante")
    out: dict[str, float] = {}
    for s in real.series:
        ts, cs = ler_instante_utc(s.serie.inicio_utc, f"realizacao[{s.uid}]")
        c += cs
        if cs or t is None:
            continue
        if s.serie.passo_s != delta_s:
            c.append(erro("resolucao_incompativel", f"realizacao[{s.uid}:{s.grandeza}]",
                          f"Passo {s.serie.passo_s} s ≠ Δ = {delta_s} s (sem reamostragem)."))
            continue
        d = (t - ts).total_seconds()
        if d < 0 or d % delta_s or int(d // delta_s) >= len(s.serie.valores):
            c.append(erro("realizacao_sem_cobertura", f"realizacao[{s.uid}:{s.grandeza}]",
                          f"Sem valor realizado alinhado para {instante_utc} (sem extrapolação)."))
            continue
        out[f"{s.uid}|{s.grandeza}"] = float(s.serie.valores[int(d // delta_s)])
    return out, c


def limite_observado(real: Realizacao):
    """Fronteira até a qual o entorno foi OBSERVADO: ``None`` no modo ``completa_offline`` (sem limite além da
    cobertura); o instante UTC de ``observado_ate_utc`` no modo ``incremental_online``."""
    if real.modo == "completa_offline":
        if real.observado_ate_utc is not None:
            return None, [erro("observado_ate_em_modo_offline", "realizacao.observado_ate_utc",
                               "Realização offline não declara instante de observação.")]
        return None, []
    if real.modo != "incremental_online":
        return None, [erro("modo_realizacao_invalido", "realizacao.modo", f"{real.modo!r}.")]
    t, c = ler_instante_utc(real.observado_ate_utc, "realizacao.observado_ate_utc")
    return t, c


def executar(plano: PlanoDespacho, estado_inicial: EstadoMicrorrede, executor: ExecutorPasso, realizacao: Realizacao, *,
             execucao_uid: str, intervalos: int | None = None, cursor: int = 0, checkpoint_cada: int = 1,
             checkpoint_anterior: Checkpoint | None = None) -> TrajetoriaExecutada:
    """Aplica ``intervalos`` consignas do plano a partir de ``cursor``. Verifica sincronização (microrrede, índice
    global e instante de cada fronteira, conjunto de UIDs de estado) antes e depois de cada passo."""
    c = validar_plano(plano)
    if c:
        raise ContratoInvalido(c)
    hp = hash_plano(plano)
    n = plano.N - cursor if intervalos is None else intervalos
    if isinstance(cursor, bool) or not isinstance(cursor, int) or not 0 <= cursor <= plano.N or n < 0 \
            or cursor + n > plano.N or checkpoint_cada < 1:
        raise ContratoInvalido([erro("cursor_invalido", "execucao", f"cursor {cursor!r} + {n!r} fora de [0, {plano.N}].")])
    t0 = ler_instante_utc(plano.inicio_utc, "plano.inicio_utc")[0]
    dt = timedelta(seconds=plano.delta_s)

    def esperado(j: int) -> tuple[int, str]:
        return plano.indice_fronteira_inicial + j, (t0 + j * dt).isoformat()

    k_esp, t_esp = esperado(cursor)
    sinc: list[Constatacao] = []
    if estado_inicial.microrrede_uid != plano.microrrede_uid:
        sinc.append(erro("estado_de_outra_microrrede", "estado.microrrede_uid", "Estado e plano de microrredes diferentes."))
    if estado_inicial.indice_fronteira != k_esp or not _mesmo_instante(estado_inicial.instante_utc, t_esp):
        sinc.append(erro("estado_dessincronizado", "estado",
                         f"Estado em k = {estado_inicial.indice_fronteira} ({estado_inicial.instante_utc}); o cursor {cursor} "
                         f"do plano exige k = {k_esp} ({t_esp})."))
    uids_b = {t.uid for t in plano.estados_planejados}
    uids_g = {x.uid for x in plano.consignas if x.grandeza == "u"}
    if {b.uid for b in estado_inicial.armazenamento} != uids_b or {g.uid for g in estado_inicial.geracao} != uids_g:
        sinc.append(erro("estado_incompativel_com_plano", "estado", "UIDs de estado ≠ recursos com estado no plano."))
    ident = f"{executor.identificador}:{executor.natureza}"
    if executor.natureza not in NATUREZAS_EXECUTOR:
        sinc.append(erro("natureza_executor_desconhecida", "executor", f"{executor.natureza!r}."))
    if checkpoint_anterior is not None:
        sinc += verificar_checkpoint(checkpoint_anterior)
        if checkpoint_anterior.hash_plano != hp or checkpoint_anterior.cursor_plano != cursor \
                or checkpoint_anterior.estado != estado_inicial or checkpoint_anterior.execucao_uid != execucao_uid \
                or checkpoint_anterior.executor != ident:
            sinc.append(erro("retomada_incoerente", "checkpoint",
                             "Checkpoint não corresponde ao plano, cursor, estado, execução ou executor da retomada."))
    if sinc:
        raise ContratoInvalido(sinc)
    if checkpoint_anterior is None:
        cadeia, seq, ant = _encadear("inicio", {"execucao": execucao_uid, "plano": hp, "estado": estado_inicial}), 0, None
    else:
        cadeia, seq, ant = (checkpoint_anterior.hash_aplicado, checkpoint_anterior.sequencia,
                            checkpoint_anterior.selo)
    estados, passos, desvios, cps, cons = [estado_inicial], [], [], [], []
    plan_e = {t.uid: t.valores for t in plano.estados_planejados}
    situacao = "concluida"

    def ckpt(j: int, est: EstadoMicrorrede) -> None:
        nonlocal seq, ant
        seq += 1
        cp = selar_checkpoint(Checkpoint(CONTRATO_VERSAO, execucao_uid, seq, hp, j, est, ant, cadeia, ident))
        cps.append(cp)
        ant = cp.selo

    est = estado_inicial
    limite, cl = limite_observado(realizacao)
    if cl:                                           # modo/instante de observação ilegível: integridade
        cons += cl
        situacao, n = "erro_dados", 0
    for j in range(cursor, cursor + n):
        k, t = esperado(j)
        # C-02: limite temporal do CONTRATO, verificado antes de qualquer executor (inclusive futuros físicos):
        # nenhum intervalo cujo FIM ultrapasse a fronteira observada é aplicado.
        if limite is not None and t0 + (j + 1) * dt > limite:
            cons.append(aviso("aguardando_observacoes", f"intervalo[{j}]",
                              f"Intervalo [{t}, {(t0 + (j + 1) * dt).isoformat()}) termina depois de observado_ate_utc "
                              f"({realizacao.observado_ate_utc}): pausa até nova observação."))
            situacao = "pausada_aguardando_observacoes"
            break
        consignas = {f"{x.uid}|{x.grandeza}": float(x.valores[j]) for x in plano.consignas}
        entorno, ce = entorno_realizado(realizacao, t, plano.delta_s)
        if ce:
            cons += ce
            situacao = "erro_dados"
            break
        passo = executor.avancar(est, consignas, entorno, plano.delta_s)
        if not passo.exequivel:
            cons += list(passo.constatacoes)
            situacao = "erro_dados" if passo.falha == "dados" else "interrompida_inexequivel"
            break
        k1, t1 = esperado(j + 1)
        novo = passo.estado_final
        if novo.indice_fronteira != k1 or not _mesmo_instante(novo.instante_utc, t1) \
                or novo.microrrede_uid != plano.microrrede_uid:
            raise ContratoInvalido([erro("executor_dessincronizou", "executor",
                                         f"Executor devolveu k = {novo.indice_fronteira} ({novo.instante_utc}); "
                                         f"esperado k = {k1} ({t1}).")])
        reg = PassoRegistrado(j, k, dict(sorted(passo.aplicado.items())))
        passos.append(reg)
        cadeia = _encadear(cadeia, reg)
        for x in plano.consignas:
            chave = f"{x.uid}|{x.grandeza}"
            if chave in passo.aplicado:
                r = passo.aplicado[chave]
                desvios.append(DesvioPlanoRealizado(x.uid, x.grandeza, j, float(x.valores[j]), r, r - float(x.valores[j])))
        for b in novo.armazenamento:
            if b.uid in plan_e:
                pe = float(plan_e[b.uid][j + 1])
                desvios.append(DesvioPlanoRealizado(b.uid, "e", j + 1, pe, b.energia_kWh, b.energia_kWh - pe))
        estados.append(novo)
        est = novo
        if (j + 1 - cursor) % checkpoint_cada == 0 and j + 1 != cursor + n:
            ckpt(j + 1, novo)
    fim = cursor + len(passos)
    ckpt(fim, est)
    return TrajetoriaExecutada(execucao_uid, hp, ident, cursor, fim, situacao, tuple(estados), tuple(passos),
                               tuple(desvios), tuple(cps), tuple(cons))


def retomar(checkpoint: Checkpoint, plano: PlanoDespacho, executor: ExecutorPasso, realizacao: Realizacao, *,
            intervalos: int | None = None, checkpoint_cada: int = 1) -> TrajetoriaExecutada:
    """Retoma a execução EXATAMENTE de onde o checkpoint parou (mesmo plano, estado, execução e executor)."""
    return executar(plano, checkpoint.estado, executor, realizacao, execucao_uid=checkpoint.execucao_uid,
                    intervalos=intervalos, cursor=checkpoint.cursor_plano, checkpoint_cada=checkpoint_cada,
                    checkpoint_anterior=checkpoint)


__all__ = ["Checkpoint", "ConsignaRecurso", "DesvioPlanoRealizado", "EstadoArmazenamento", "EstadoGeracao",
           "EstadoMicrorrede", "ExecutorAlgebricoReferencia", "ExecutorPasso", "GRANDEZAS_CONSIGNA",
           "GRANDEZAS_ESTADO_PLANO", "NATUREZAS_EXECUTOR", "PassoAplicado", "PassoRegistrado", "PlanoDespacho",
           "SITUACOES", "TrajetoriaExecutada", "TrajetoriaPlanejada", "entorno_realizado", "estado_inicial_de_entrada",
           "executar", "hash_plano", "limite_observado", "plano_de_resultado", "retomar", "selar_checkpoint", "validar_plano",
           "verificar_checkpoint"]
