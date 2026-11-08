"""Serialização canônica dos contratos da ponte (3C-0).

Reutiliza a serialização ESTRITA do contrato 3A (``contracts.para_dict`` / ``contracts.de_dict``): dataclasses →
dicionários, tuplas → listas, reconstrução com tipos e comprimentos exatos, sem ``eval``/``pickle``. NaN/Inf são
proibidos no JSON (``allow_nan=False``): um valor ausente é ``None``, nunca um número especial.
"""
from __future__ import annotations

import hashlib
import json

from ..contracts import ErroSerializacao, _constante_proibida, de_dict, para_dict


def json_canonico(obj) -> str:
    return json.dumps(para_dict(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256(obj) -> str:
    return hashlib.sha256(json_canonico(obj).encode("utf-8")).hexdigest()


def de_json(cls, texto: str):
    """JSON estrito → dataclass ``cls`` (campos desconhecidos/ausentes/tipos errados ⇒ ``ErroSerializacao``)."""
    try:
        dado = json.loads(texto, parse_constant=_constante_proibida)
    except json.JSONDecodeError as exc:
        raise ErroSerializacao(f"JSON inválido: {exc}") from None
    return de_dict(cls, dado, cls.__name__)


__all__ = ["ErroSerializacao", "de_json", "json_canonico", "sha256"]
