"""Provedores de previsão SINTÉTICOS e reproduzíveis (3C-2). Só biblioteca padrão.

Nenhum destes provedores é um previsor meteorológico ou de demanda validado: são regras sintéticas declaradas para
exercitar o protocolo causal do MPC.

* ``ProvedorTabelaDeclarada`` (``sintetico_conhecido``) — perfis declarados ANTES da missão (programação conhecida);
  em cada janela recorta [τ_k, τ_k + N_kΔ) sem olhar observações. Previsões "constantes ou conhecidas".
* ``ProvedorCorrecaoPorObservacao`` (``sintetico_reemitido_por_observacao``) — perfil base declarado + correção
  ADITIVA δ = (último valor observado válido − base no mesmo intervalo) para as chaves declaradas, com piso 0 para
  potências. Reemite uma previsão nova sempre que o instantâneo informacional muda (função determinística dele).
* ``ProvedorOraculoAblacao`` (``oraculo_ablacao``) — recorta a REALIZAÇÃO completa recebida explicitamente na
  construção; ``previsao_perfeita=True`` com justificativa. Só para ablação rotulada (excluída das comparações causais).

Todos declaram em ``procedencia.sha256`` o hash do instantâneo recebido (vínculo informacional verificado pelo
orquestrador) e expõem ``impressao()`` = SHA-256 dos parâmetros declarados (comparabilidade entre missões).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from ..diagnostics import ContratoInvalido, erro
from ..ponte.canonico import sha256
from ..ponte.cenario import ConjuntoPrevisao, Realizacao, SerieRecurso
from ..provenance import Procedencia
from ..series import SerieTemporal
from ..timegrid import ler_instante_utc
from .previsao import PedidoPrevisao


def _recorte(s: SerieTemporal, inicio_utc: str, n: int, delta_s: int) -> tuple[float, ...]:
    """Valores de [início, início + nΔ) de uma série regular com o mesmo passo (o que existir; sem extrapolação)."""
    if s.passo_s != delta_s:
        raise ContratoInvalido([erro("resolucao_incompativel", "provedor", f"Passo {s.passo_s} s ≠ Δ = {delta_s} s.")])
    t0, ts = ler_instante_utc(inicio_utc, "i")[0], ler_instante_utc(s.inicio_utc, "s")[0]
    d = (t0 - ts).total_seconds()
    if d < 0 or d % delta_s:
        return ()
    i0 = int(d // delta_s)
    return tuple(float(v) for v in s.valores[i0:i0 + n])


def _serie(gr: str, un: str, inicio: str, delta_s: int, vals, proc: Procedencia, emissao: str) -> SerieTemporal:
    return SerieTemporal(gr, un, "media_intervalo", inicio, delta_s, tuple(vals), proc,
                         fronteira="barramento_liquido" if gr == "potencia" else None, emissao_utc=emissao)


class ProvedorTabelaDeclarada:
    natureza = "sintetico_conhecido"

    def __init__(self, identificador: str, tabela: dict, procedencia: Procedencia, *, bases: dict | None = None):
        """``tabela`` = {(recurso_uid, grandeza): SerieTemporal com ``emissao_utc`` declarada}; ``bases`` = {uid: base}."""
        self.identificador, self.procedencia = identificador, procedencia
        self.tabela = dict(sorted(tabela.items()))
        self.bases = dict(bases or {})

    def impressao(self) -> str:
        return sha256({"id": self.identificador, "natureza": self.natureza,
                       "tabela": [[list(k), v] for k, v in self.tabela.items()], "bases": self.bases,
                       "procedencia": self.procedencia})

    def emitir(self, pedido: PedidoPrevisao) -> ConjuntoPrevisao:
        series = []
        for ch in pedido.chaves:
            s = self.tabela.get((ch.recurso_uid, ch.grandeza))
            if s is None:
                continue                            # a validação da janela constata a ausência (nada inventado)
            vals = _recorte(s, pedido.inicio_utc, pedido.N_k, pedido.delta_s)
            series.append(SerieRecurso(ch.recurso_uid, ch.grandeza, _serie(
                ch.grandeza, s.unidade, pedido.inicio_utc, pedido.delta_s, vals, s.procedencia, s.emissao_utc),
                self.bases.get(ch.recurso_uid) if ch.grandeza == "potencia" else None))
        proc = replace(self.procedencia, sha256=pedido.instantaneo.hash,
                       observacoes=f"{self.procedencia.observacoes} · janela {pedido.indice_janela} (k = {pedido.k})".strip(" ·"))
        return ConjuntoPrevisao(f"prev-{pedido.missao_uid[:8]}-j{pedido.indice_janela}", pedido.inicio_utc,
                                tuple(series), proc)


class ProvedorCorrecaoPorObservacao(ProvedorTabelaDeclarada):
    natureza = "sintetico_reemitido_por_observacao"

    def __init__(self, identificador: str, tabela: dict, procedencia: Procedencia, *, corrigidas, bases=None,
                 piso: float = 0.0):
        super().__init__(identificador, tabela, procedencia, bases=bases)
        self.corrigidas = tuple(sorted(tuple(x) for x in corrigidas))
        self.piso = float(piso)

    def impressao(self) -> str:
        return sha256({"base": super().impressao(), "corrigidas": [list(x) for x in self.corrigidas], "piso": self.piso})

    def correcao(self, pedido: PedidoPrevisao, uid: str, gr: str) -> tuple[float, str | None]:
        """δ e o intervalo observado que o sustenta (o MAIS RECENTE válido, fim <= corte). Sem observação: δ = 0."""
        base = self.tabela[(uid, gr)]
        cands = [v for v in pedido.instantaneo.valores if v.recurso_uid == uid and v.grandeza == gr
                 and v.estado == "valido" and v.valor is not None]
        cands.sort(key=lambda v: ler_instante_utc(v.fim_utc, "f")[0])
        for v in reversed(cands):
            b = _recorte(base, v.inicio_utc, 1, pedido.delta_s)
            fim = ler_instante_utc(v.fim_utc, "f")[0]
            ini = ler_instante_utc(v.inicio_utc, "i")[0]
            if b and fim - ini == timedelta(seconds=pedido.delta_s):
                return v.valor - b[0], v.inicio_utc
        return 0.0, None

    def emitir(self, pedido: PedidoPrevisao) -> ConjuntoPrevisao:
        p = super().emitir(pedido)
        series = []
        for s in p.series:
            if (s.uid, s.grandeza) in self.corrigidas:
                d, ref = self.correcao(pedido, s.uid, s.grandeza)
                vals = tuple(max(self.piso, v + d) for v in s.serie.valores)
                proc = replace(s.serie.procedencia, observacoes=(
                    f"{s.serie.procedencia.observacoes} · correção δ = {d!r} pela observação do intervalo {ref} "
                    f"(instantâneo {pedido.instantaneo.hash[:16]})").strip(" ·"))
                s = replace(s, serie=replace(s.serie, valores=vals, procedencia=proc, emissao_utc=pedido.inicio_utc))
            series.append(s)
        return replace(p, series=tuple(series))


class ProvedorOraculoAblacao:
    natureza = "oraculo_ablacao"

    def __init__(self, identificador: str, verdade: Realizacao, justificativa: str, procedencia: Procedencia, *,
                 bases: dict | None = None):
        self.identificador, self.verdade, self.justificativa, self.procedencia = (identificador, verdade, justificativa,
                                                                                  procedencia)
        self.bases = dict(bases or {})

    def impressao(self) -> str:
        return sha256({"id": self.identificador, "natureza": self.natureza, "verdade": sha256(self.verdade),
                       "justificativa": self.justificativa})

    def emitir(self, pedido: PedidoPrevisao) -> ConjuntoPrevisao:
        series = []
        for ch in pedido.chaves:
            s = self.verdade.serie(ch.recurso_uid, ch.grandeza)
            if s is None:
                continue
            vals = _recorte(s.serie, pedido.inicio_utc, pedido.N_k, pedido.delta_s)
            proc = Procedencia("sintetico", f"oráculo de ablação {self.identificador}", "realização completa",
                               observacoes="PREVISÃO PERFEITA declarada (lê a realização)")
            series.append(SerieRecurso(ch.recurso_uid, ch.grandeza, _serie(
                ch.grandeza, s.serie.unidade, pedido.inicio_utc, pedido.delta_s, vals, proc, pedido.inicio_utc),
                self.bases.get(ch.recurso_uid) if ch.grandeza == "potencia" else None))
        return ConjuntoPrevisao(f"orac-{pedido.missao_uid[:8]}-j{pedido.indice_janela}", pedido.inicio_utc,
                                tuple(series), replace(self.procedencia, sha256=pedido.instantaneo.hash),
                                previsao_perfeita=True, justificativa_oraculo=self.justificativa)


__all__ = ["ProvedorCorrecaoPorObservacao", "ProvedorOraculoAblacao", "ProvedorTabelaDeclarada"]
