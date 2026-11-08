"""Unidades canônicas e conversões EXPLÍCITAS (adenda v1.1 §A).

Canônicas do contrato: potência em kW (líquida no barramento), energia em kWh, massa de H2 em kg, vazão em kg/h,
moeda em R$, frações adimensionais em ``"1"``. Toda conversão é linear, exata (``Fraction``) e devolve a
``Transformacao`` correspondente para a cadeia bruto → normalizado. Unidade desconhecida é rejeitada; percentual
nunca é tratado como fração sem conversão declarada.
"""
from __future__ import annotations

import math
from fractions import Fraction

from .diagnostics import ContratoInvalido, erro
from .provenance import Transformacao

UNIDADES_CANONICAS = frozenset({
    "kW", "kWh", "h", "min", "s", "kg", "kg/h", "R$", "R$/kWh", "R$/kg", "R$/h", "R$/evento", "R$/kW",
    "kW/min", "1/h", "1",
})

# unidade de origem → (unidade canônica, fator exato: valor_canônico = fator × valor_origem)
CONVERSOES: dict[str, tuple[str, Fraction]] = {
    "W": ("kW", Fraction(1, 1000)),
    "MW": ("kW", Fraction(1000)),
    "Wh": ("kWh", Fraction(1, 1000)),
    "MWh": ("kWh", Fraction(1000)),
    "R$/MWh": ("R$/kWh", Fraction(1, 1000)),     # CVU: dividir por 1000 (especificação v1.0 M19)
    "%": ("1", Fraction(1, 100)),
    "kg/s": ("kg/h", Fraction(3600)),
    "kg/min": ("kg/h", Fraction(60)),
    "kW/s": ("kW/min", Fraction(60)),
}


def exato(x: float | int | Fraction | str) -> Fraction:
    """Converte para ``Fraction`` a partir da representação DECIMAL (0.9 → 9/10). Rejeita bool, NaN e Inf."""
    if isinstance(x, bool):
        raise TypeError("Valor booleano não é grandeza numérica.")
    if isinstance(x, Fraction):
        return x
    if isinstance(x, int):
        return Fraction(x)
    if isinstance(x, float):
        if not math.isfinite(x):
            raise ValueError("Valor não finito (NaN/Inf).")
        return Fraction(repr(x))
    if isinstance(x, str):
        return Fraction(x)
    raise TypeError(f"Tipo numérico não suportado: {type(x).__name__}")


def eh_canonica(unidade: str) -> bool:
    return unidade in UNIDADES_CANONICAS


def para_canonica(valor: float | int, unidade: str, caminho: str = "valor") -> tuple[float, str, Transformacao | None]:
    """Converte ``valor`` para a unidade canônica. Já canônico → sem transformação. Desconhecida → rejeição."""
    if unidade in UNIDADES_CANONICAS:
        return float(valor), unidade, None
    if unidade not in CONVERSOES:
        raise ContratoInvalido([erro("unidade_desconhecida", caminho, f"Unidade desconhecida: {unidade!r}.")])
    destino, fator = CONVERSOES[unidade]
    novo = float(exato(valor) * fator)
    return novo, destino, Transformacao("conversao_unidade", f"{unidade} → {destino} (× {fator})", unidade, destino,
                                        str(fator))


def fator_conversao(origem: str, destino: str) -> Fraction:
    if origem == destino:
        return Fraction(1)
    if origem in CONVERSOES and CONVERSOES[origem][0] == destino:
        return CONVERSOES[origem][1]
    raise ContratoInvalido([erro("conversao_inexistente", f"{origem}->{destino}",
                                 f"Não há conversão declarada de {origem!r} para {destino!r}.")])


__all__ = ["CONVERSOES", "UNIDADES_CANONICAS", "eh_canonica", "exato", "fator_conversao", "para_canonica"]
