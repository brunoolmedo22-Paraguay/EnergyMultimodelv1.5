"""Interface de previsões POR JANELA e protocolo de informação (3C-2). Só biblioteca padrão.

Cada otimização usa um ``ConjuntoPrevisao`` (3C-0) PRÓPRIO, emitido por um provedor declarado a partir de um
``PedidoPrevisao`` que contém SOMENTE: identidade da missão, a janela (τ_k, Δ, N_k), as chaves exigidas e o
``InstantaneoInformacional`` selado em τ_k. O orquestrador nunca entrega ao provedor o entorno/verdade do simulador.

Verificações em tempo de execução (``validar_previsao_janela``), todas bloqueantes:

* 3C-0 ``validar_previsao``: emissão do conjunto <= τ_k; emissão de cada série <= emissão do conjunto; unidades,
  semântica, resolução = Δ, alinhamento e cobertura dos N_k intervalos (sem extrapolação);
* chaves EXATAMENTE as pedidas (UIDs/grandezas/base do potencial) e cada série começando em τ_k com N_k valores;
* VÍNCULO INFORMACIONAL: ``procedencia.sha256`` do conjunto = hash do instantâneo entregue no pedido;
* oráculo (``previsao_perfeita``) só em missão rotulada ``ablacao_oraculo`` (e vice-versa);
* independência: o provedor não pode ser o provedor de verdade do simulador (identificador e fontes declaradas).

LIMITE DE CONFIANÇA: estas verificações são estruturais. Um provedor malicioso que tenha obtido a verdade por outro
caminho (referência em memória) e declare o vínculo corretamente NÃO é detectado em tempo de execução; é detectado pela
auditoria posterior (``auditoria.verificar_nao_antecipatividade``: intervenção na verdade futura) e pela classificação
de separação 3C-0 com evidência (mesmo objeto / hash do conteúdo realizado). Ver ``docs/ems_v2/FORMULACAO_3C2.md``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..compromisso.contrato import EntradaCommitment3C1
from ..diagnostics import Constatacao, erro
from ..ponte.cenario import ConjuntoPrevisao, DefinicaoTemporal, validar_previsao
from ..timegrid import MalhaTemporal, ler_instante_utc
from .observacoes import InstantaneoInformacional

NATUREZAS_PROVEDOR = {
    "sintetico_conhecido": "Série sintética declarada antecipadamente (perfil conhecido/programado); não usa observações",
    "sintetico_reemitido_por_observacao": "Perfil base declarado + correção pela última observação válida do instantâneo "
                                          "(regra sintética reproduzível; NÃO é previsor meteorológico/de demanda validado)",
    "oraculo_ablacao": "Previsão perfeita declarada (lê a realização completa): só experimento de ablação rotulado",
}


@dataclass(frozen=True)
class ChavePrevisao:
    recurso_uid: str
    grandeza: str
    base_potencial: str | None = None       # só potência renovável


@dataclass(frozen=True)
class PedidoPrevisao:
    missao_uid: str
    microrrede_uid: str
    indice_janela: int
    k: int
    inicio_utc: str                         # τ_k
    delta_s: int
    N_k: int
    chaves: tuple[ChavePrevisao, ...]
    instantaneo: InstantaneoInformacional


class ProvedorPrevisao(Protocol):
    identificador: str
    natureza: str

    def emitir(self, pedido: PedidoPrevisao) -> ConjuntoPrevisao: ...

    def impressao(self) -> str: ...


def chaves_de_previsao(modelo: EntradaCommitment3C1) -> tuple[ChavePrevisao, ...]:
    """Séries exógenas que a entrada 3C-1 de cada janela exige (por UID): demanda (e fração interrompível), potencial e
    disponibilidade renováveis, disponibilidade de bancos e de geradores."""
    b = modelo.base
    out: list[ChavePrevisao] = []
    for d in b.demandas:
        out.append(ChavePrevisao(str(d.uid), "potencia"))
        if d.fracao_interrompivel is not None:
            out.append(ChavePrevisao(str(d.uid), "fracao_interrompivel"))
    for r in b.renovaveis:
        out += [ChavePrevisao(str(r.uid), "potencia", r.base_potencial), ChavePrevisao(str(r.uid), "disponibilidade")]
    for x in b.baterias:
        out.append(ChavePrevisao(str(x.uid), "disponibilidade"))
    for g in b.geradores:
        out.append(ChavePrevisao(str(g.uid), "disponibilidade"))
    return tuple(sorted(out, key=lambda c: (c.recurso_uid, c.grandeza)))


def validar_previsao_janela(prev, pedido: PedidoPrevisao, malha_janela: MalhaTemporal, *, provedor_id: str,
                            provedor_natureza: str, rotulo_informacao: str,
                            identificadores_verdade=(), fontes_verdade=()) -> list[Constatacao]:
    if not isinstance(prev, ConjuntoPrevisao):
        return [erro("previsao_tipo_invalido", "previsao", f"Esperado ConjuntoPrevisao; recebido {type(prev).__name__}.")]
    out = list(c for c in validar_previsao(prev, DefinicaoTemporal(malha_janela)) if c.severidade != "aviso")
    pedidas = {(c.recurso_uid, c.grandeza): c for c in pedido.chaves}
    vistas = {(s.uid, s.grandeza) for s in prev.series}
    for k in sorted(set(pedidas) - vistas):
        out.append(erro("previsao_chave_ausente", f"previsao[{k[0]}:{k[1]}]", "Série exigida pela janela ausente."))
    for k in sorted(vistas - set(pedidas)):
        out.append(erro("previsao_chave_nao_solicitada", f"previsao[{k[0]}:{k[1]}]", "Série não pedida (UID/grandeza)."))
    t0 = ler_instante_utc(pedido.inicio_utc, "pedido.inicio_utc")[0]
    for s in prev.series:
        cam = f"previsao[{s.uid}:{s.grandeza}]"
        ch = pedidas.get((s.uid, s.grandeza))
        if ch is not None and ch.base_potencial != s.base_potencial:
            out.append(erro("previsao_base_potencial_divergente", cam, f"{s.base_potencial!r} ≠ {ch.base_potencial!r}."))
        ts = ler_instante_utc(s.serie.inicio_utc, cam)[0]
        if ts != t0 or len(s.serie.valores) != pedido.N_k:
            out.append(erro("previsao_fora_da_janela", cam,
                            f"Série deve começar em τ_k = {pedido.inicio_utc} com N_k = {pedido.N_k} valores (recebido "
                            f"início {s.serie.inicio_utc}, {len(s.serie.valores)} valores)."))
    pr = prev.procedencia
    if pr is None or pr.sha256 != pedido.instantaneo.hash:
        out.append(erro("previsao_sem_vinculo_informacional", "previsao.procedencia.sha256",
                        "O conjunto deve declarar o hash do instantâneo informacional recebido no pedido."))
    if prev.previsao_perfeita and rotulo_informacao != "ablacao_oraculo":
        out.append(erro("oraculo_em_missao_causal", "previsao.previsao_perfeita",
                        "Previsão perfeita só em missão rotulada 'ablacao_oraculo' (excluída das comparações causais)."))
    if rotulo_informacao == "ablacao_oraculo" and not prev.previsao_perfeita:
        out.append(erro("ablacao_sem_oraculo_declarado", "previsao.previsao_perfeita",
                        "Missão de ablação exige o oráculo DECLARADO."))
    if (provedor_natureza == "oraculo_ablacao") != bool(prev.previsao_perfeita):
        out.append(erro("natureza_provedor_incoerente", "previsao", "Natureza do provedor × rótulo da previsão."))
    if provedor_natureza not in NATUREZAS_PROVEDOR:
        out.append(erro("natureza_provedor_desconhecida", "provedor.natureza", f"{provedor_natureza!r}."))
    if provedor_id in set(identificadores_verdade):
        out.append(erro("provedor_nao_independente", "provedor.identificador",
                        "O provedor de previsão é o próprio provedor de verdade do simulador."))
    fv = set(fontes_verdade)
    if not prev.previsao_perfeita and fv and ((pr is not None and pr.fonte in fv) or any(
            s.serie.procedencia is not None and s.serie.procedencia.fonte in fv for s in prev.series)):
        out.append(erro("provedor_nao_independente", "previsao.procedencia.fonte",
                        "Procedência da previsão aponta a fonte de verdade do simulador sem oráculo declarado."))
    return out


__all__ = ["ChavePrevisao", "NATUREZAS_PROVEDOR", "PedidoPrevisao", "ProvedorPrevisao", "chaves_de_previsao",
           "validar_previsao_janela"]
