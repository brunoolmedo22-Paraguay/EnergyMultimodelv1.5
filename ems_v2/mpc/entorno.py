"""Protocolo de passo do entorno e planta ALGÉBRICA simulada (3C-2, modo 1). Só biblioteca padrão.

Distinções explícitas (cada uma é um tipo/evento próprio):

* **Plano calculado** — ``PlanoDespacho`` (3C-0) de uma janela;
* **Comando emitido** — ``ComandoIntervalo``: as consignas de UM intervalo global g, ligadas ao hash do plano;
* **Ação confirmada** — ``ConfirmacaoAcao`` recebida do entorno executor (aplicada / recusada), com instante de recepção;
* **Observação recebida** — ``observacoes.Observacao`` registrada no livro K6;
* **Estado reconstruído** — conciliação 3C-0/3C-1 (propagação ALGÉBRICA) feita pelo controlador a partir de comandos
  confirmados + observações (nunca o estado interno da planta);
* **Custo confirmado** — contabilidade dos intervalos conciliados.

``EntornoSimuladoAlgebrico`` encapsula a VERDADE sintética completa (``Realizacao`` offline) e o executor algébrico 3C-1
como planta. Protocolo causal: o intervalo g só é realizado DEPOIS de receber o comando de g (em ordem, sem saltos); a
resposta imediata é apenas um RECIBO; confirmações e observações só chegam ao controlador por ``entregar_ate(T)``,
em ordem de recepção, com a latência DECLARADA por grandeza (sem padrão) e perturbações declaradas para ensaios
(omissão, atraso, duplicata, revisão, conflito, outra microrrede, valor inválido, sequência reutilizada).

Não é modelo físico: a planta é o dublê algébrico 3C-1 (natureza ``algebrico_referencia``).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Protocol

from ..compromisso.contrato import EntradaCommitment3C1
from ..diagnostics import ContratoInvalido, erro
from ..ponte.canonico import sha256
from ..ponte.cenario import Realizacao
from ..ponte.compromisso import ExecutorAlgebricoCommitment3C1
from ..ponte.execucao import EstadoMicrorrede, entorno_realizado
from ..provenance import Procedencia
from ..timegrid import ler_instante_utc
from .observacoes import GRANDEZAS_OBSERVAVEIS, Observacao

SITUACOES_CONFIRMACAO = {
    "aplicada": "Consigna aplicada pelo entorno executor",
    "rejeitada_inexequivel": "Consigna inexequível nas condições reais do intervalo (nada aplicado, sem recorte)",
    "rejeitada_dados": "Entorno sem dados para avaliar a consigna (nada aplicado)",
    "rejeitada_protocolo": "Comando fora de ordem, de outra missão/instante ou entorno parado (nada aplicado)",
}
TIPOS_PERTURBACAO = ("omitir", "atrasar", "duplicar", "revisar", "conflitar", "outra_microrrede", "valor_invalido",
                     "reutilizar_sequencia")


@dataclass(frozen=True)
class ComandoIntervalo:
    missao_uid: str
    indice_janela: int
    indice_global: int                      # g: intervalo [τ_g, τ_{g+1})
    inicio_utc: str
    hash_plano: str
    indice_plano: int
    consignas: dict[str, float]             # "uid|grandeza" → valor
    emitido_utc: str                        # instante lógico da decisão que o emitiu (τ_k)


@dataclass(frozen=True)
class ConfirmacaoAcao:
    missao_uid: str
    hash_comando: str
    indice_global: int
    situacao: str                           # SITUACOES_CONFIRMACAO
    recebido_utc: str
    executor: str                           # "identificador:natureza"
    detalhe: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReciboComando:
    hash_comando: str
    indice_global: int
    aceito_para_execucao: bool


class EntornoPasso(Protocol):
    identificador: str
    natureza: str

    def aplicar(self, comando: ComandoIntervalo) -> ReciboComando: ...

    def entregar_ate(self, instante_utc: str) -> tuple: ...


def hash_comando(c: ComandoIntervalo) -> str:
    return sha256(c)


@dataclass(frozen=True)
class PerturbacaoCanal:
    """Perturbação DECLARADA de ensaio para a observação (recurso, grandeza) do intervalo global g."""
    tipo: str                               # TIPOS_PERTURBACAO
    recurso_uid: str
    grandeza: str
    indice_global: int
    atraso_s: int = 0                       # atrasar / revisar (recepção da revisão após o fim do intervalo)
    valor: float | None = None              # revisar / conflitar / valor_invalido


class CanalObservacao:
    """Gera as observações de cada intervalo realizado (sequência por fonte atribuída na TRANSMISSÃO) e as entrega em
    ordem de recepção. ``latencias_s`` exige uma latência declarada para cada (recurso, grandeza) da verdade."""

    def __init__(self, fonte: str, latencias_s: dict, latencia_confirmacao_s: int, procedencia: Procedencia,
                 perturbacoes: tuple[PerturbacaoCanal, ...] = ()):
        for p in perturbacoes:
            if p.tipo not in TIPOS_PERTURBACAO:
                raise ContratoInvalido([erro("perturbacao_invalida", "canal", f"{p.tipo!r}.")])
        self.fonte, self.latencias_s, self.lat_conf = fonte, dict(latencias_s), int(latencia_confirmacao_s)
        self.procedencia, self.perturbacoes = procedencia, tuple(perturbacoes)
        self._seq = 0
        self._fila: list[tuple] = []         # (recebido, ordem, evento)
        self._ordem = 0

    def _enfileirar(self, recebido, evento) -> None:
        self._fila.append((recebido, self._ordem, evento))
        self._ordem += 1

    def _pert(self, uid, gr, g, tipo):
        return [p for p in self.perturbacoes if (p.recurso_uid, p.grandeza, p.indice_global, p.tipo) == (uid, gr, g, tipo)]

    def transmitir(self, missao_uid: str, microrrede_uid: str, g: int, ini, fim, entorno: dict) -> None:
        for chave in sorted(entorno):
            uid, _, gr = chave.partition("|")
            if gr not in GRANDEZAS_OBSERVAVEIS:
                continue
            if (uid, gr) not in self.latencias_s:
                raise ContratoInvalido([erro("latencia_nao_declarada", f"canal[{uid}:{gr}]",
                                             "Latência de observação não declarada (sem padrão).")])
            if self._pert(uid, gr, g, "omitir"):
                self._seq += 1                    # a sequência foi consumida: a perda aparece como lacuna
                continue
            atraso = sum(p.atraso_s for p in self._pert(uid, gr, g, "atrasar"))
            rec = fim + timedelta(seconds=int(self.latencias_s[(uid, gr)]) + atraso)
            mg = microrrede_uid + "-outra" if self._pert(uid, gr, g, "outra_microrrede") else microrrede_uid
            inval = self._pert(uid, gr, g, "valor_invalido")
            val = float(inval[0].valor) if inval else float(entorno[chave])
            ev = f"{self.fonte}:g{g}:{uid}:{gr}:r0"
            o = Observacao(ev, self.fonte, self._seq, mg, uid, gr, GRANDEZAS_OBSERVAVEIS[gr], ini.isoformat(),
                           fim.isoformat(), val, rec.isoformat(), self.procedencia)
            self._seq += 1
            self._enfileirar(rec, o)
            if self._pert(uid, gr, g, "duplicar"):
                self._enfileirar(rec, o)          # retransmissão: mesmo evento, mesma sequência
            for p in self._pert(uid, gr, g, "conflitar"):
                o2 = replace(o, evento_uid=ev + ":conflito", sequencia=self._seq, valor=float(p.valor),
                             recebido_utc=(rec + timedelta(seconds=p.atraso_s)).isoformat())
                self._seq += 1
                self._enfileirar(rec + timedelta(seconds=p.atraso_s), o2)
            for r, p in enumerate(self._pert(uid, gr, g, "revisar"), start=1):
                tr = fim + timedelta(seconds=p.atraso_s)
                o3 = replace(o, evento_uid=f"{self.fonte}:g{g}:{uid}:{gr}:r{r}", sequencia=self._seq,
                             valor=float(p.valor), recebido_utc=tr.isoformat(), revisao=r, revisa_evento_uid=ev)
                self._seq += 1
                self._enfileirar(tr, o3)
            for p in self._pert(uid, gr, g, "reutilizar_sequencia"):
                o4 = replace(o, evento_uid=ev + ":reuso", valor=float(entorno[chave]))
                self._enfileirar(rec + timedelta(seconds=p.atraso_s), replace(
                    o4, recebido_utc=(rec + timedelta(seconds=p.atraso_s)).isoformat()))

    def confirmar(self, c: ConfirmacaoAcao, recebido) -> None:
        self._enfileirar(recebido, c)

    def entregar_ate(self, instante) -> tuple:
        self._fila.sort(key=lambda x: (x[0], x[1]))
        prontos = [x for x in self._fila if x[0] <= instante]
        self._fila = [x for x in self._fila if x[0] > instante]
        return tuple(x[2] for x in prontos)

    def pendentes(self) -> int:
        return len(self._fila)


class EntornoSimuladoAlgebrico:
    """Planta algébrica de ENSAIO (verdade encapsulada + executor 3C-1). Não é modelo físico."""
    natureza = "planta_algebrica_3C1"

    def __init__(self, *, identificador: str, missao_uid: str, verdade: Realizacao, modelo: EntradaCommitment3C1,
                 fontes_disponibilidade: dict, estado_inicial: EstadoMicrorrede, canal: CanalObservacao,
                 inicio_missao_utc: str, delta_s: int, intervalos_missao: int):
        if verdade.modo != "completa_offline":
            raise ContratoInvalido([erro("verdade_nao_completa", "entorno.verdade",
                                         "A planta simulada exige a realização COMPLETA (modo offline).")])
        self.identificador = identificador
        self._missao, self._verdade, self._canal = missao_uid, verdade, canal
        self._exec = ExecutorAlgebricoCommitment3C1(modelo, fontes_disponibilidade, identificador=identificador)
        self._estado = estado_inicial
        self._t0 = ler_instante_utc(inicio_missao_utc, "inicio")[0]
        self._d, self._K = int(delta_s), int(intervalos_missao)
        self._prox = estado_inicial.indice_fronteira
        self._parado = False
        self._mg = estado_inicial.microrrede_uid
        self._aplicados: list[str] = []

    @property
    def proximo_indice(self) -> int:
        return self._prox

    @property
    def parado(self) -> bool:
        return self._parado

    def impressao_verdade(self) -> str:
        """Usado SÓ pela auditoria/comparadores após a missão (nunca entregue ao controlador)."""
        return sha256(self._verdade)

    def comandos_aplicados(self) -> tuple[str, ...]:
        return tuple(self._aplicados)

    def aplicar(self, comando: ComandoIntervalo) -> ReciboComando:
        hc = hash_comando(comando)
        g = comando.indice_global
        ini = self._t0 + timedelta(seconds=self._d * g)
        fim = ini + timedelta(seconds=self._d)
        ident = f"{self.identificador}:{self.natureza}"
        tc = ler_instante_utc(comando.inicio_utc, "comando")[0]
        if self._parado or comando.missao_uid != self._missao or g != self._prox or g >= self._K or tc != ini:
            self._canal.confirmar(ConfirmacaoAcao(self._missao, hc, g, "rejeitada_protocolo", fim.isoformat(), ident,
                                                  ("comando fora de ordem/missão/instante ou planta parada",)),
                                  fim + timedelta(seconds=self._canal.lat_conf))
            return ReciboComando(hc, g, False)
        ent, ce = entorno_realizado(self._verdade, ini.isoformat(), self._d)   # verdade do intervalo g, SÓ agora
        passo = self._exec.avancar(self._estado, dict(comando.consignas), ent, self._d) if not ce else None
        if passo is not None and passo.exequivel:
            self._estado = passo.estado_final
            sit, det = "aplicada", ()
            self._aplicados.append(hc)
        else:
            sit = "rejeitada_dados" if (ce or (passo is not None and passo.falha == "dados")) else "rejeitada_inexequivel"
            det = tuple(f"[{c.codigo}] {c.caminho}" for c in (ce or list(passo.constatacoes)))
            self._parado = True                   # parada segura: nenhum comando posterior é aplicado
        self._prox = g + 1
        self._canal.transmitir(self._missao, self._mg, g, ini, fim, ent)
        rec = fim + timedelta(seconds=self._canal.lat_conf)
        self._canal.confirmar(ConfirmacaoAcao(self._missao, hc, g, sit, rec.isoformat(), ident, det), rec)
        return ReciboComando(hc, g, sit == "aplicada")

    def entregar_ate(self, instante_utc: str) -> tuple:
        return self._canal.entregar_ate(ler_instante_utc(instante_utc, "entrega")[0])

    def reconstituir(self, comandos: tuple[ComandoIntervalo, ...], entregue_ate_utc: str) -> None:
        """Reproduz deterministicamente comandos já aplicados (retomada de uma missão interrompida no lado do
        controlador) e descarta as entregas já feitas até ``entregue_ate_utc`` (o livro persistido já as contém)."""
        for c in comandos:
            if not self.aplicar(c).aceito_para_execucao:
                raise ContratoInvalido([erro("reconstituicao_divergente", "entorno", "Comando não reaplicável.")])
        self._canal.entregar_ate(ler_instante_utc(entregue_ate_utc, "entregue_ate")[0])


__all__ = ["CanalObservacao", "ComandoIntervalo", "ConfirmacaoAcao", "EntornoPasso", "EntornoSimuladoAlgebrico",
           "PerturbacaoCanal", "ReciboComando", "SITUACOES_CONFIRMACAO", "TIPOS_PERTURBACAO", "hash_comando"]
