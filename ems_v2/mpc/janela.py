"""Entrada 3C-1 de cada janela do MPC (3C-2): modelo declarado + previsão da janela + estado EXECUTADO. Só biblioteca
padrão.

``montar_entrada_janela`` NÃO reformula nada: parte do ``modelo`` (uma ``EntradaCommitment3C1`` válida com os
parâmetros, políticas e termos DECLARADOS da missão) e substitui somente

1. a malha pela da janela (τ_k, Δ, N_k, m_k; H_f declarado da missão);
2. as séries exógenas pelas séries do ``ConjuntoPrevisao`` da janela (demanda, potencial/disponibilidade renovável,
   disponibilidade de bancos e geradores) — nunca pela realização;
3. a política de permanência 3C-1 pela da janela (intermediária × final, declaradas na política terminal da missão);
4. estados iniciais de bancos/geradores e memórias pelos do estado EXECUTADO na fronteira τ_k (reutiliza
   ``ponte.compromisso.entrada_de_continuacao``: microrrede, instante e UIDs conferidos; nada completado).

O estado terminal PLANEJADO de uma janela nunca é usado: só o estado conciliado da execução.
Os hashes da previsão e do instantâneo informacional entram em ``base.hashes_fontes`` (compromisso no SHA-256 da
entrada 3C-1).
"""
from __future__ import annotations

from dataclasses import replace

from ..compromisso.contrato import EntradaCommitment3C1, PoliticaPermanenciaTerminal
from ..contracts import Disponibilidade
from ..diagnostics import ContratoInvalido, erro
from ..ponte.cenario import ConjuntoPrevisao, hash_previsao
from ..ponte.compromisso import entrada_de_continuacao
from ..ponte.execucao import EstadoMicrorrede
from ..provenance import Procedencia
from .contrato import ConfiguracaoMPC
from .relogio import JanelaMPC


def _serie(prev: ConjuntoPrevisao, uid: str, gr: str):
    s = prev.serie(uid, gr)
    if s is None:
        raise ContratoInvalido([erro("previsao_chave_ausente", f"previsao[{uid}:{gr}]", "Série ausente na previsão.")])
    return s.serie


def verificar_identidade(cfg: ConfiguracaoMPC, modelo: EntradaCommitment3C1, estado: EstadoMicrorrede | None = None
                         ) -> list:
    i, b = cfg.identidade, modelo.base
    out = []
    if b.microrrede_uid != i.microrrede_uid:
        out.append(erro("identidade_divergente", "modelo.base.microrrede_uid",
                        f"Modelo da microrrede {b.microrrede_uid!r}; missão de {i.microrrede_uid!r}."))
    if b.cenario_uid != i.cenario_uid:
        out.append(erro("identidade_divergente", "modelo.base.cenario_uid",
                        f"Modelo do cenário {b.cenario_uid!r}; missão do cenário {i.cenario_uid!r}."))
    if estado is not None and estado.microrrede_uid != i.microrrede_uid:
        out.append(erro("identidade_divergente", "estado.microrrede_uid", "Estado de outra microrrede."))
    return out


def montar_entrada_janela(modelo: EntradaCommitment3C1, cfg: ConfiguracaoMPC, jan: JanelaMPC, prev: ConjuntoPrevisao,
                          estado: EstadoMicrorrede, *, hash_instantaneo: str, procedencia: Procedencia
                          ) -> EntradaCommitment3C1:
    c = verificar_identidade(cfg, modelo, estado)
    if c:
        raise ContratoInvalido(c)
    b = modelo.base
    malha = jan.malha(cfg.malha)
    dem = tuple(replace(d, potencia=_serie(prev, str(d.uid), "potencia"),
                        fracao_interrompivel=(None if d.fracao_interrompivel is None
                                              else _serie(prev, str(d.uid), "fracao_interrompivel")))
                for d in b.demandas)
    ren = tuple(replace(r, potencial=_serie(prev, str(r.uid), "potencia"),
                        disponibilidade=Disponibilidade(_serie(prev, str(r.uid), "disponibilidade")))
                for r in b.renovaveis)
    bat = tuple(replace(x, disponibilidade=Disponibilidade(_serie(prev, str(x.uid), "disponibilidade")))
                for x in b.baterias)
    ger = tuple(replace(g, disponibilidade=Disponibilidade(_serie(prev, str(g.uid), "disponibilidade")))
                for g in b.geradores)
    hp = hash_previsao(prev)
    obs = f"janela {jan.indice_janela} (k = {jan.k}, N_k = {jan.N_k}, m_k = {jan.m_k}); previsão {hp[:16]}"
    base = replace(b, malha=malha, demandas=dem, renovaveis=ren, baterias=bat, geradores=ger,
                   procedencia=None if b.procedencia is None else replace(
                       b.procedencia, observacoes=f"{b.procedencia.observacoes} · {obs}".strip(" ·")),
                   hashes_fontes={**b.hashes_fontes, "previsao_janela": hp, "instantaneo_informacional": hash_instantaneo})
    pt = cfg.politica_terminal
    pol = PoliticaPermanenciaTerminal(jan.politica_permanencia,
                                      f"Política terminal da missão {pt.tipo!r} — {pt.justificativa}", pt.procedencia)
    e3 = replace(modelo, base=base, politica_permanencia=pol)
    return entrada_de_continuacao(e3, estado, procedencia=procedencia)


__all__ = ["montar_entrada_janela", "verificar_identidade"]
