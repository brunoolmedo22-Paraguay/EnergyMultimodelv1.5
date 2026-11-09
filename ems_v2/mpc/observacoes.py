"""K6 — Livro de observações APPEND-ONLY e estado informacional causal (3C-2). Só biblioteca padrão.

Cada observação tem identidade por RECURSO (``str(UIDRecurso)``) e GRANDEZA, o INTERVALO FÍSICO a que se refere
([início, fim), semântica ``media_intervalo``, sem reamostragem), valor/unidade canônica, procedência, instante de
RECEPÇÃO, identificador de evento, número de sequência por fonte e, quando houver, revisão do evento original.

Dois tempos distintos: **tempo físico** (o intervalo observado) e **tempo de disponibilidade** (``recebido_utc``). O
instantâneo informacional num corte τ contém exatamente as entradas RECEBIDAS em ou antes de τ (corte inclusivo,
convenção declarada). Como o livro registra em ordem de recepção e recusa recepções retroativas, o instantâneo em τ é um
PREFIXO do livro, comprometido pelo hash da cadeia nesse prefixo: um corte selado (decisão) nunca muda depois.

Regras explícitas (classificação gravada em cada entrada; nada é sobrescrito):

* **inválida** — grandeza/unidade desconhecida, valor ausente/NaN/fora do domínio, instantes ambíguos, fim <= início,
  RECEBIDA ANTES DO FIM do intervalo (seria informação futura), procedência inválida ⇒ ``rejeitada_invalida``;
* **outra microrrede** ⇒ ``rejeitada_outra_microrrede``; **recurso/grandeza não declarados** ⇒
  ``rejeitada_recurso_desconhecido``;
* **duplicata** (mesmo ``evento_uid``): conteúdo idêntico ⇒ ``duplicata_identica`` (sem nova informação); conteúdo
  diferente ⇒ ``rejeitada_conflito_evento_uid``;
* **sequência** (por fonte): lacuna ⇒ aceita com nota (possível perda); número menor que o máximo visto com evento novo
  ⇒ ``aceita_fora_de_sequencia`` (disponível só a partir da SUA recepção); número já usado por outro evento ⇒
  ``rejeitada_conflito_sequencia``;
* **recepção retroativa** (antes da última recepção registrada ou em/antes de um corte selado) ⇒
  ``rejeitada_recepcao_retroativa`` — ninguém altera um conjunto de informação já usado numa decisão;
* **revisões** chegam como eventos NOVOS (``revisao`` = r, ``revisa_evento_uid`` = original): r deve ser exatamente a
  próxima revisão da chave; revisão sem original aceito ⇒ ``rejeitada_revisao_sem_original``; número repetido/salto ⇒
  ``rejeitada_conflito_revisao``. O valor efetivo de uma chave num corte é o da maior revisão recebida até o corte;
* **conflito entre originais** (segunda observação original do mesmo intervalo com valor diferente) ⇒
  ``aceita_original_conflitante``: a chave fica CONFLITANTE (sem valor utilizável) até uma revisão explícita; com o
  mesmo valor ⇒ ``duplicata_semantica`` (sem efeito);
* **atraso** — ``atraso_s`` = recepção − fim do intervalo; ``tardia_apos_corte`` = corte selado (decisão) que já cobria
  o intervalo e precedeu a recepção (a observação nunca altera aquela decisão).

Ausência de informação obrigatória NÃO é zero, nem última medição conhecida, nem disponibilidade plena: o consumidor
recebe a lista de faltantes. Nenhuma política de imputação existe aqui.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from ..diagnostics import Constatacao, ContratoInvalido, erro
from ..ponte.canonico import json_canonico, sha256
from ..ponte.cenario import Realizacao, SerieRecurso
from ..provenance import Procedencia, validar_procedencia
from ..series import SerieTemporal
from ..timegrid import ler_instante_utc

ESQUEMA_LIVRO = 1
GRANDEZAS_OBSERVAVEIS = {"potencia": "kW", "disponibilidade": "1", "fracao_interrompivel": "1"}
CLASSIFICACOES = {
    "aceita": "Observação original aceita",
    "aceita_fora_de_sequencia": "Aceita; número de sequência menor que o máximo já recebido (reordenação/atraso)",
    "aceita_revisao": "Revisão explícita aceita (novo evento; o original é preservado)",
    "aceita_original_conflitante": "Segunda original do mesmo intervalo com valor diferente: chave CONFLITANTE",
    "duplicata_identica": "Mesmo evento e mesmo conteúdo: idempotente (sem nova informação)",
    "duplicata_semantica": "Outra original do mesmo intervalo com o mesmo valor: sem efeito",
    "rejeitada_invalida": "Estrutura/valor/instantes/procedência inválidos",
    "rejeitada_outra_microrrede": "Observação de outra microrrede",
    "rejeitada_recurso_desconhecido": "Recurso/grandeza não declarados para esta missão",
    "rejeitada_conflito_evento_uid": "Mesmo evento_uid com conteúdo diferente",
    "rejeitada_conflito_sequencia": "Número de sequência já usado por outro evento da mesma fonte",
    "rejeitada_recepcao_retroativa": "Recepção anterior à última registrada ou a um corte selado",
    "rejeitada_revisao_sem_original": "Revisão de evento inexistente/rejeitado ou de outra chave",
    "rejeitada_conflito_revisao": "Número de revisão repetido ou fora de ordem",
}
ACEITAS = ("aceita", "aceita_fora_de_sequencia", "aceita_revisao", "aceita_original_conflitante")


@dataclass(frozen=True)
class Observacao:
    evento_uid: str
    fonte: str                              # canal/fonte (escopo da sequência)
    sequencia: int
    microrrede_uid: str
    recurso_uid: str                        # str(UIDRecurso)
    grandeza: str                           # GRANDEZAS_OBSERVAVEIS
    unidade: str
    inicio_utc: str                         # intervalo físico [início, fim)
    fim_utc: str
    valor: float | None                     # None = valor ausente/não finito recebido (registrado como inválido)
    recebido_utc: str                       # instante de disponibilidade para o controlador
    procedencia: Procedencia | None
    revisao: int = 0                        # 0 = original
    revisa_evento_uid: str | None = None    # obrigatório para revisao >= 1


@dataclass(frozen=True)
class EntradaLivro:
    posicao: int
    observacao: Observacao
    hash_evento: str
    classificacao: str
    detalhe: str
    atraso_s: int | None
    tardia_apos_corte: str | None
    hash_anterior: str
    hash_cadeia: str


@dataclass(frozen=True)
class ValorEfetivo:
    recurso_uid: str
    grandeza: str
    inicio_utc: str
    fim_utc: str
    valor: float | None                     # None ⇔ conflitante
    estado: str                             # "valido" | "conflitante"
    evento_uid: str
    revisao: int
    recebido_utc: str


@dataclass(frozen=True)
class InstantaneoInformacional:
    """Conjunto de informação disponível num corte (prefixo do livro). ``hash`` compromete todo o conteúdo."""
    esquema: int
    missao_uid: str
    microrrede_uid: str
    corte_utc: str
    n_entradas: int                         # tamanho do prefixo (aceitas e rejeitadas)
    hash_cadeia_prefixo: str
    valores: tuple[ValorEfetivo, ...]
    hash: str = ""

    def valor(self, recurso_uid: str, grandeza: str, inicio_utc: str) -> ValorEfetivo | None:
        t = _ts(inicio_utc)
        return next((v for v in self.valores if v.recurso_uid == recurso_uid and v.grandeza == grandeza
                     and _ts(v.inicio_utc) == t), None)


@dataclass(frozen=True)
class DocumentoLivro:
    """Serialização verificável do livro (entradas + posições dos cortes selados)."""
    esquema: int
    missao_uid: str
    microrrede_uid: str
    recursos: dict[str, tuple[str, ...]]
    cortes: tuple[tuple[int, str], ...]     # (tamanho do livro no selo, instante do corte)
    entradas: tuple[EntradaLivro, ...]


def _ts(texto: str):
    return ler_instante_utc(texto, "t")[0]


def _h(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def hash_instantaneo(i: InstantaneoInformacional) -> str:
    return sha256(replace(i, hash=""))


class LivroObservacoes:
    """Registro append-only. ``recursos`` = {recurso_uid: grandezas admitidas} (observações de outros recursos são
    rejeitadas)."""

    def __init__(self, missao_uid: str, microrrede_uid: str, recursos: dict[str, tuple[str, ...]]):
        self.missao_uid, self.microrrede_uid = missao_uid, microrrede_uid
        self.recursos = {k: tuple(sorted(v)) for k, v in sorted(recursos.items())}
        self._entradas: list[EntradaLivro] = []
        self._cortes: list[tuple[int, str]] = []
        self._gen = _h(json_canonico({"livro_observacoes": ESQUEMA_LIVRO, "missao": missao_uid,
                                      "microrrede": microrrede_uid}))
        self._por_evento: dict[str, EntradaLivro] = {}
        self._seqs: dict[str, dict[int, str]] = {}
        self._rev: dict[tuple, int] = {}             # chave física → maior revisão aceita
        self._orig: dict[tuple, list[EntradaLivro]] = {}
        self._ult_rec = None

    # -------------------------------------------------------------------------------- leitura
    @property
    def entradas(self) -> tuple[EntradaLivro, ...]:
        return tuple(self._entradas)

    @property
    def cortes(self) -> tuple[tuple[int, str], ...]:
        return tuple(self._cortes)

    def hash_cadeia(self) -> str:
        return self._entradas[-1].hash_cadeia if self._entradas else self._gen

    # -------------------------------------------------------------------------------- escrita
    def selar_corte(self, instante_utc: str) -> None:
        t, c = ler_instante_utc(instante_utc, "corte")
        if c:
            raise ContratoInvalido(c)
        if self._cortes and t < _ts(self._cortes[-1][1]):
            raise ContratoInvalido([erro("corte_retroativo", "livro.corte",
                                         f"Corte {instante_utc} anterior ao último selado {self._cortes[-1][1]}.")])
        if self._ult_rec is not None and t < self._ult_rec:
            raise ContratoInvalido([erro("corte_antes_de_recepcao_registrada", "livro.corte",
                                         "Corte anterior a uma recepção já registrada (o prefixo não seria estável).")])
        self._cortes.append((len(self._entradas), t.isoformat()))

    def _chave(self, o: Observacao) -> tuple:
        return (o.recurso_uid, o.grandeza, _ts(o.inicio_utc), _ts(o.fim_utc))

    def _validar(self, o: Observacao) -> list[str]:
        p: list[str] = []
        if not isinstance(o, Observacao):
            return ["tipo de observação inválido"]
        for nome in ("evento_uid", "fonte", "recurso_uid"):
            v = getattr(o, nome)
            if not isinstance(v, str) or not v.strip() or len(v) > 200:
                p.append(f"{nome} inválido")
        if isinstance(o.sequencia, bool) or not isinstance(o.sequencia, int) or o.sequencia < 0:
            p.append("sequência inválida")
        if o.grandeza not in GRANDEZAS_OBSERVAVEIS:
            p.append(f"grandeza {o.grandeza!r} desconhecida")
        elif o.unidade != GRANDEZAS_OBSERVAVEIS[o.grandeza]:
            p.append(f"unidade {o.unidade!r} ≠ {GRANDEZAS_OBSERVAVEIS[o.grandeza]!r}")
        v = o.valor
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            p.append("valor ausente/não finito (ausente nunca vira zero)")
        elif o.grandeza == "potencia" and v < 0:
            p.append("potência negativa no barramento")
        elif o.grandeza == "disponibilidade" and v not in (0, 1):
            p.append("disponibilidade ∉ {0, 1}")
        elif o.grandeza == "fracao_interrompivel" and not 0 <= v <= 1:
            p.append("fração ∉ [0, 1]")
        ti, ci = ler_instante_utc(o.inicio_utc, "inicio")
        tf, cf = ler_instante_utc(o.fim_utc, "fim")
        tr, cr = ler_instante_utc(o.recebido_utc, "recebido")
        if ci or cf or cr:
            p.append("instante ausente/ambíguo")
        else:
            if tf <= ti:
                p.append("fim <= início")
            if tr < tf:
                p.append("recebida ANTES do fim do intervalo observado (informação futura)")
        if isinstance(o.revisao, bool) or not isinstance(o.revisao, int) or o.revisao < 0:
            p.append("revisão inválida")
        elif (o.revisao == 0) != (o.revisa_evento_uid is None):
            p.append("revisão >= 1 exige revisa_evento_uid (e só ela)")
        if validar_procedencia(o.procedencia, "procedencia"):
            p.append("procedência inválida")
        return p

    def _classificar(self, o: Observacao, he: str) -> tuple[str, str]:
        prob = self._validar(o)
        if prob:
            return "rejeitada_invalida", "; ".join(prob)
        if o.microrrede_uid != self.microrrede_uid:
            return "rejeitada_outra_microrrede", f"{o.microrrede_uid!r} ≠ {self.microrrede_uid!r}"
        if o.grandeza not in self.recursos.get(o.recurso_uid, ()):
            return "rejeitada_recurso_desconhecido", f"{o.recurso_uid}:{o.grandeza} não declarado"
        ant = self._por_evento.get(o.evento_uid)
        if ant is not None:
            if ant.hash_evento == he:
                return "duplicata_identica", f"evento já registrado na posição {ant.posicao}"
            return "rejeitada_conflito_evento_uid", f"evento {o.evento_uid!r} já registrado com outro conteúdo"
        tr = _ts(o.recebido_utc)
        if self._ult_rec is not None and tr < self._ult_rec:
            return "rejeitada_recepcao_retroativa", f"recebido {o.recebido_utc} < última recepção {self._ult_rec.isoformat()}"
        if self._cortes and tr <= _ts(self._cortes[-1][1]):
            return "rejeitada_recepcao_retroativa", f"recebido {o.recebido_utc} <= corte selado {self._cortes[-1][1]}"
        seqs = self._seqs.get(o.fonte, {})
        if o.sequencia in seqs:
            return "rejeitada_conflito_sequencia", f"sequência {o.sequencia} já usada por {seqs[o.sequencia]!r}"
        ch = self._chave(o)
        nota = ""
        if seqs and o.sequencia < max(seqs):
            nota = f"fora de sequência (máximo visto {max(seqs)})"
        elif seqs and o.sequencia > max(seqs) + 1:
            nota = f"lacuna de sequência ({max(seqs) + 1}..{o.sequencia - 1} não recebidos)"
        if o.revisao >= 1:
            orig = self._por_evento.get(o.revisa_evento_uid)
            if orig is None or orig.classificacao not in ACEITAS or orig.observacao.revisao != 0 \
                    or self._chave(orig.observacao) != ch:
                return "rejeitada_revisao_sem_original", f"original {o.revisa_evento_uid!r} inexistente/rejeitado/outra chave"
            if o.revisao != self._rev.get(ch, 0) + 1:
                return "rejeitada_conflito_revisao", f"revisão {o.revisao}; esperada {self._rev.get(ch, 0) + 1}"
            return "aceita_revisao", nota
        origs = [e for e in self._orig.get(ch, []) if e.classificacao in ACEITAS]
        if origs:
            if all(e.observacao.valor == o.valor for e in origs):
                return "duplicata_semantica", "outra original com o mesmo valor"
            return "aceita_original_conflitante", "valor difere da(s) original(is) já recebida(s): chave conflitante"
        return ("aceita_fora_de_sequencia" if nota.startswith("fora") else "aceita"), nota

    def registrar(self, o: Observacao) -> EntradaLivro:
        """Registra a recepção (aceita ou rejeitada — toda recepção fica no livro). Nunca altera entradas anteriores.
        Um valor não finito/não numérico é registrado como ``None`` (o JSON canônico proíbe NaN/Inf) e rejeitado."""
        if isinstance(o, Observacao) and (isinstance(o.valor, bool) or not isinstance(o.valor, (int, float))
                                          or not math.isfinite(o.valor)):
            o = replace(o, valor=None)
        try:
            he = sha256(o)
        except Exception as exc:  # noqa: BLE001 — conteúdo não serializável: rejeição controlada
            he = _h(f"nao_serializavel:{type(exc).__name__}")
        cl, det = self._classificar(o, he)
        atraso, tardia = None, None
        if cl in ACEITAS or cl.startswith("duplicata"):
            tr, tf = _ts(o.recebido_utc), _ts(o.fim_utc)
            atraso = int((tr - tf).total_seconds())
            cob = [c for _, c in self._cortes if tf <= _ts(c) < tr]
            tardia = cob[0] if cob else None
        pos = len(self._entradas)
        ant = self.hash_cadeia()
        cad = _h(f"{ant}|{he}|{cl}|{pos}")
        ent = EntradaLivro(pos, o, he, cl, det, atraso, tardia, ant, cad)
        self._entradas.append(ent)
        if cl not in ("rejeitada_invalida", "rejeitada_outra_microrrede", "rejeitada_recurso_desconhecido",
                      "rejeitada_conflito_evento_uid", "duplicata_identica", "rejeitada_recepcao_retroativa",
                      "rejeitada_conflito_sequencia"):
            self._seqs.setdefault(o.fonte, {})[o.sequencia] = o.evento_uid
        if isinstance(o, Observacao) and isinstance(o.evento_uid, str):
            self._por_evento.setdefault(o.evento_uid, ent)       # a 1ª recepção de um evento define a sua identidade
        if cl in ACEITAS or cl == "duplicata_semantica":
            tr = _ts(o.recebido_utc)
            self._ult_rec = tr if self._ult_rec is None else max(self._ult_rec, tr)
            ch = self._chave(o)
            if cl == "aceita_revisao":
                self._rev[ch] = o.revisao
            else:
                self._orig.setdefault(ch, []).append(ent)
        return ent

    def registrar_varios(self, obs) -> tuple[EntradaLivro, ...]:
        return tuple(self.registrar(o) for o in obs)

    # -------------------------------------------------------------------------------- instantâneo
    def instantaneo(self, corte_utc: str) -> InstantaneoInformacional:
        tc, c = ler_instante_utc(corte_utc, "corte")
        if c:
            raise ContratoInvalido(c)
        n = 0
        for e in self._entradas:                    # prefixo: recepções aceitas em ordem não decrescente
            if (e.classificacao in ACEITAS or e.classificacao == "duplicata_semantica") and _recebido_depois(e, tc):
                break
            n += 1
        return instantaneo_de_prefixo(self.missao_uid, self.microrrede_uid, tc.isoformat(), self._entradas[:n],
                                      self._entradas[n - 1].hash_cadeia if n else self._gen)

    # -------------------------------------------------------------------------------- serialização
    def exportar(self) -> DocumentoLivro:
        return DocumentoLivro(ESQUEMA_LIVRO, self.missao_uid, self.microrrede_uid, dict(self.recursos),
                              tuple(self._cortes), tuple(self._entradas))

    @classmethod
    def importar(cls, doc: DocumentoLivro) -> "LivroObservacoes":
        """Reconstrói REPRODUZINDO cada recepção e cada corte na ordem gravada; qualquer divergência de classificação,
        hash de evento ou cadeia ⇒ ``ContratoInvalido`` (livro adulterado)."""
        if doc.esquema != ESQUEMA_LIVRO:
            raise ContratoInvalido([erro("esquema_livro_incompativel", "livro.esquema", f"{doc.esquema!r}.")])
        lv = cls(doc.missao_uid, doc.microrrede_uid, {k: tuple(v) for k, v in doc.recursos.items()})
        cortes = list(doc.cortes)
        for i, e in enumerate(doc.entradas):
            while cortes and cortes[0][0] == i:
                lv.selar_corte(cortes.pop(0)[1])
            r = lv.registrar(e.observacao)
            if r != e:
                raise ContratoInvalido([erro("livro_adulterado", f"livro.entradas[{i}]",
                                             "Entrada não reproduz a recepção registrada (classificação/hash/cadeia).")])
        for _, t in cortes:
            lv.selar_corte(t)
        if [(p, _ts(t)) for p, t in lv.cortes] != [(p, _ts(t)) for p, t in doc.cortes]:
            raise ContratoInvalido([erro("livro_adulterado", "livro.cortes", "Cortes selados divergentes.")])
        return lv


def _recebido_depois(e: EntradaLivro, tc) -> bool:
    o = e.observacao
    if not isinstance(o, Observacao):
        return False
    tr, c = ler_instante_utc(o.recebido_utc, "r")
    return not c and tr > tc


def instantaneo_de_prefixo(missao_uid: str, microrrede_uid: str, corte_utc: str, prefixo, hash_cadeia: str
                           ) -> InstantaneoInformacional:
    """Valores efetivos a partir de um prefixo do livro (função pura; também usada pela auditoria independente)."""
    orig: dict[tuple, list[EntradaLivro]] = {}
    rev: dict[tuple, EntradaLivro] = {}
    for e in prefixo:
        if e.classificacao not in ACEITAS:
            continue
        o = e.observacao
        ch = (o.recurso_uid, o.grandeza, _ts(o.inicio_utc), _ts(o.fim_utc))
        if e.classificacao == "aceita_revisao":
            if ch not in rev or o.revisao > rev[ch].observacao.revisao:
                rev[ch] = e
        else:
            orig.setdefault(ch, []).append(e)
    vals: list[ValorEfetivo] = []
    for ch in sorted(set(orig) | set(rev), key=lambda x: (x[0], x[1], x[2], x[3])):
        if ch in rev:
            o = rev[ch].observacao
            vals.append(ValorEfetivo(ch[0], ch[1], ch[2].isoformat(), ch[3].isoformat(), float(o.valor), "valido",
                                     o.evento_uid, o.revisao, o.recebido_utc))
            continue
        es = orig[ch]
        o = es[0].observacao
        confl = any(e.classificacao == "aceita_original_conflitante" for e in es)
        vals.append(ValorEfetivo(ch[0], ch[1], ch[2].isoformat(), ch[3].isoformat(), None if confl else float(o.valor),
                                 "conflitante" if confl else "valido", o.evento_uid, 0,
                                 es[-1].observacao.recebido_utc if confl else o.recebido_utc))
    inst = InstantaneoInformacional(ESQUEMA_LIVRO, missao_uid, microrrede_uid, corte_utc, len(prefixo), hash_cadeia,
                                    tuple(vals))
    return replace(inst, hash=hash_instantaneo(inst))


# ------------------------------------------------------------------------------------------------ realização observada
@dataclass(frozen=True)
class Faltante:
    recurso_uid: str
    grandeza: str
    indice: int                              # índice do intervalo relativo ao início pedido
    motivo: str                              # "ausente" | "conflitante"


@dataclass(frozen=True)
class RealizacaoObservada:
    realizacao: Realizacao                   # incremental_online, observado_ate_utc = fronteira contígua observada
    intervalos_observados: int               # c: intervalos [0, c) com TODAS as chaves válidas
    faltantes: tuple[Faltante, ...]
    hash_instantaneo: str
    valores: tuple[dict[str, float], ...] = field(default_factory=tuple)   # entorno observado por intervalo [0, c)


def realizacao_de_instantaneo(inst: InstantaneoInformacional, chaves, inicio_utc: str, n_intervalos: int, delta_s: int,
                              *, natureza: str = "sintetica") -> RealizacaoObservada:
    """Realização OBSERVADA (modo ``incremental_online``) para os ``n_intervalos`` a partir de ``inicio_utc``, só com
    valores efetivos válidos do instantâneo e só para intervalos com EXATAMENTE a duração Δ (sem reamostragem).
    ``observado_ate_utc`` = última fronteira até a qual TODAS as chaves estão observadas de forma contígua; o resto
    fica em ``faltantes`` (nunca zero, nunca a última medição)."""
    t0, c = ler_instante_utc(inicio_utc, "inicio")
    if c:
        raise ContratoInvalido(c)
    d = timedelta(seconds=delta_s)
    falt: list[Faltante] = []
    contig = None
    vals: list[dict[str, float]] = []
    for i in range(n_intervalos):
        ti = t0 + i * d
        linha: dict[str, float] = {}
        for (uid, gr) in chaves:
            v = inst.valor(uid, gr, ti.isoformat())
            if v is None or _ts(v.fim_utc) != ti + d:
                falt.append(Faltante(uid, gr, i, "ausente"))
            elif v.estado != "valido" or v.valor is None:
                falt.append(Faltante(uid, gr, i, "conflitante"))
            else:
                linha[f"{uid}|{gr}"] = v.valor
        if contig is None and len(linha) != len(chaves):
            contig = i
        if contig is None:
            vals.append(linha)
    cnt = n_intervalos if contig is None else contig
    proc = Procedencia("sintetico" if natureza == "sintetica" else "medido", f"LivroObservacoes:{inst.missao_uid}",
                       f"instantâneo em {inst.corte_utc}", sha256=inst.hash,
                       observacoes="valores efetivos do livro (recepção <= corte); sem imputação")
    series = []
    for (uid, gr) in chaves:
        if cnt == 0:
            continue
        s = SerieTemporal(gr, GRANDEZAS_OBSERVAVEIS[gr], "media_intervalo", t0.isoformat(), delta_s,
                          tuple(vals[i][f"{uid}|{gr}"] for i in range(cnt)), proc,
                          fronteira="barramento_liquido" if gr == "potencia" else None)
        series.append(SerieRecurso(uid, gr, s))
    real = Realizacao(f"obs-{inst.hash[:24]}", natureza, tuple(series), proc, modo="incremental_online",
                      observado_ate_utc=(t0 + cnt * d).isoformat())
    return RealizacaoObservada(real, cnt, tuple(falt), inst.hash, tuple(vals))


def resumo_classificacoes(entradas) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in entradas:
        out[e.classificacao] = out.get(e.classificacao, 0) + 1
    return dict(sorted(out.items()))


def verificar_cadeia_livro(doc: DocumentoLivro) -> list[Constatacao]:
    """Verificação independente da cadeia (sem reproduzir classificações): posições, hashes e encadeamento."""
    out: list[Constatacao] = []
    gen = _h(json_canonico({"livro_observacoes": ESQUEMA_LIVRO, "missao": doc.missao_uid,
                            "microrrede": doc.microrrede_uid}))
    ant = gen
    for i, e in enumerate(doc.entradas):
        if e.posicao != i or e.hash_anterior != ant or e.hash_evento != sha256(e.observacao) or \
                e.hash_cadeia != _h(f"{ant}|{e.hash_evento}|{e.classificacao}|{i}"):
            out.append(erro("livro_cadeia_quebrada", f"livro.entradas[{i}]", "Posição/hash/encadeamento não conferem."))
            break
        ant = e.hash_cadeia
    return out


__all__ = ["ACEITAS", "CLASSIFICACOES", "DocumentoLivro", "ESQUEMA_LIVRO", "EntradaLivro", "Faltante",
           "GRANDEZAS_OBSERVAVEIS", "InstantaneoInformacional", "LivroObservacoes", "Observacao", "RealizacaoObservada",
           "ValorEfetivo", "hash_instantaneo", "instantaneo_de_prefixo", "realizacao_de_instantaneo",
           "resumo_classificacoes", "verificar_cadeia_livro"]
_ = datetime
