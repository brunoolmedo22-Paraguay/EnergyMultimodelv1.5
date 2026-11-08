"""Constatações de validação e rejeição controlada.

Severidades:

* ``erro`` — dado incoerente ou proibido (UID duplicado, NaN, unidade incompatível, eficiência fora de (0, 1] …);
* ``pendente`` — capacidade científica que o Piso 3A não representa ou dado ausente exigido por ela; também
  BLOQUEIA (nunca é ignorada em silêncio nem substituída por um valor presumido);
* ``aviso`` — informação registrada que não impede o uso (p. ex. emissão da previsão não declarada).
"""
from __future__ import annotations

from dataclasses import dataclass, field

SEVERIDADES = ("erro", "pendente", "aviso")
BLOQUEANTES = ("erro", "pendente")


@dataclass(frozen=True)
class Constatacao:
    codigo: str
    caminho: str
    mensagem: str
    severidade: str = "erro"

    def __post_init__(self) -> None:
        if self.severidade not in SEVERIDADES:
            raise ValueError(f"Severidade desconhecida: {self.severidade!r}")


@dataclass(frozen=True)
class RelatorioValidacao:
    constatacoes: tuple[Constatacao, ...] = field(default_factory=tuple)

    @property
    def aceito(self) -> bool:
        return not any(c.severidade in BLOQUEANTES for c in self.constatacoes)

    def codigos(self, severidade: str | None = None) -> set[str]:
        return {c.codigo for c in self.constatacoes if severidade is None or c.severidade == severidade}

    def bloqueantes(self) -> tuple[Constatacao, ...]:
        return tuple(c for c in self.constatacoes if c.severidade in BLOQUEANTES)


class ContratoInvalido(ValueError):
    """Rejeição controlada: carrega as constatações que impediram a construção/uso do objeto."""

    def __init__(self, constatacoes: list[Constatacao] | tuple[Constatacao, ...]):
        self.constatacoes = tuple(constatacoes)
        resumo = "; ".join(f"[{c.codigo}] {c.caminho}: {c.mensagem}" for c in self.constatacoes[:6])
        super().__init__(resumo or "contrato inválido")

    @property
    def codigos(self) -> set[str]:
        return {c.codigo for c in self.constatacoes}


def erro(codigo: str, caminho: str, mensagem: str) -> Constatacao:
    return Constatacao(codigo, caminho, mensagem, "erro")


def pendente(codigo: str, caminho: str, mensagem: str) -> Constatacao:
    return Constatacao(codigo, caminho, mensagem, "pendente")


def aviso(codigo: str, caminho: str, mensagem: str) -> Constatacao:
    return Constatacao(codigo, caminho, mensagem, "aviso")
