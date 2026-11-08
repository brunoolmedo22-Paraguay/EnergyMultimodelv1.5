"""Procedência das fontes (``SourceProvenance``) e cadeia de transformações.

Toda grandeza física, série ou política do contrato canônico carrega a sua procedência. Uma fonte sem procedência
é rejeitada (ordem executiva 3A.1). As categorias ampliam as do Piso 1 (``seeds2.microgrid.config.PROVENANCE_KINDS``)
sem importá-lo: ``sintetico`` nunca é "medido"; ``nao_declarado`` não sustenta um valor físico.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .diagnostics import Constatacao, erro

TIPOS_PROCEDENCIA = {
    "sintetico": "Sintético / fixture gerada para teste (não medido, não calibrado)",
    "medido": "Medido na instalação",
    "fabricante": "Documentado pelo fabricante (ficha técnica)",
    "referencia": "Conjunto de referência incluído no software (não medido nesta instalação)",
    "identificado": "Identificado/calibrado a partir de dados, com método registrado",
    "decisao_responsavel": "Decisão explícita do responsável científico (política, não medição)",
    # 3C-0 (extensão aditiva): valor digitado pelo usuário no SEEDS2 (inventário ou cenário de UMA microrrede),
    # rastreável à revisão/versão e ao caminho no documento, SEM documento de origem registrado (não é ficha técnica
    # conferida nem medição).
    "declarado_seeds2": "Declarado no SEEDS2 (inventário/cenário), rastreável à revisão/versão; sem documento de origem",
    "nao_declarado": "Procedência não declarada",
}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Procedencia:
    """Origem de um dado. ``fonte`` identifica o documento/arquivo/pessoa; ``referencia`` o item dentro dele."""
    tipo: str
    fonte: str
    referencia: str = ""
    data: str | None = None
    sha256: str | None = None
    observacoes: str = ""


@dataclass(frozen=True)
class Transformacao:
    """Um passo da cadeia bruto → normalizado. ``fator`` é texto exato (``Fraction``) quando há conversão linear."""
    etapa: str
    descricao: str
    unidade_origem: str | None = None
    unidade_destino: str | None = None
    fator: str | None = None


def validar_procedencia(p: Procedencia | None, caminho: str, *, sustenta_valor: bool = True) -> list[Constatacao]:
    """``sustenta_valor``: a procedência sustenta um valor numérico (então ``nao_declarado`` não é aceito)."""
    if p is None:
        return [erro("sem_procedencia", caminho, "Fonte sem procedência declarada.")]
    out: list[Constatacao] = []
    if p.tipo not in TIPOS_PROCEDENCIA:
        out.append(erro("procedencia_invalida", caminho, f"Tipo de procedência desconhecido: {p.tipo!r}."))
    elif sustenta_valor and p.tipo == "nao_declarado":
        out.append(erro("procedencia_nao_declarada", caminho,
                        "Valor numérico com procedência 'não declarada' não é aceito (deixe o valor ausente)."))
    if not str(p.fonte or "").strip():
        out.append(erro("procedencia_sem_fonte", caminho, "Procedência sem fonte identificada."))
    if p.sha256 is not None and not _HEX64.fullmatch(str(p.sha256)):
        out.append(erro("procedencia_hash_invalido", caminho, "SHA-256 da procedência inválido."))
    return out


__all__ = ["Procedencia", "TIPOS_PROCEDENCIA", "Transformacao", "validar_procedencia"]
