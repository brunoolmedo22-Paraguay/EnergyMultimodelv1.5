"""Pré-verificação do perfil 3C-3 ANTES do solver (sem Pyomo).

``preflight_3c3`` = ``validar_entrada_3c3`` (núcleo 3C-1 sem relaxação + PCC + tarifas + política econômica) +
``preflight_3c1`` do núcleo (compromisso parcial, obrigações × disponibilidade, transições fixadas). Nada é alterado:
só constata. Constatações do núcleo aparecem com o prefixo ``compromisso.``.
"""
from __future__ import annotations

from ..compromisso.preflight import preflight_3c1
from ..diagnostics import Constatacao
from .contrato import EntradaRede3C3, validar_entrada_3c3


def preflight_3c3(e: EntradaRede3C3, compromisso_parcial: dict | None = None) -> list[Constatacao]:
    rel = validar_entrada_3c3(e)
    out = list(rel.constatacoes)
    if not rel.aceito:
        return out
    # preflight_3c1 repete validar_entrada_3c1 (já incluída com prefixo): só acrescenta o que é do compromisso parcial
    ja = {(c.codigo, c.caminho.removeprefix("compromisso.")) for c in out}
    out += [Constatacao(c.codigo, "compromisso." + c.caminho, c.mensagem, c.severidade)
            for c in preflight_3c1(e.compromisso, compromisso_parcial) if (c.codigo, c.caminho) not in ja]
    return out


__all__ = ["preflight_3c3"]
