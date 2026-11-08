"""Parâmetro físico/econômico com unidade, procedência e cadeia bruto → normalizado (requisito R46).

``valor`` é SEMPRE o valor normalizado, na unidade canônica ``unidade``. ``valor_bruto``/``unidade_bruta`` guardam
o dado como recebido; ``transformacoes`` registra a conversão. ``valor=None`` significa AUSENTE: gera constatação
(``erro`` se obrigatório, ``pendente`` se só a capacidade que o usa fica bloqueada) — nunca é presumido.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .diagnostics import Constatacao, erro, pendente
from .provenance import Procedencia, Transformacao, validar_procedencia
from .units import UNIDADES_CANONICAS, converter, fator_conversao, para_canonica

DOMINIOS = {
    "positivo": "> 0",
    "nao_negativo": ">= 0",
    "eficiencia": "(0, 1]",
    "fracao": "[0, 1]",
    "qualquer": "finito",
}


@dataclass(frozen=True)
class Parametro:
    valor: float | None
    unidade: str
    procedencia: Procedencia | None = None
    valor_bruto: float | None = None
    unidade_bruta: str | None = None
    transformacoes: tuple[Transformacao, ...] = field(default_factory=tuple)

    @classmethod
    def de_bruto(cls, valor_bruto: float, unidade_bruta: str, procedencia: Procedencia | None) -> "Parametro":
        """Normaliza com conversão EXPLÍCITA e registra a transformação (dado bruto preservado)."""
        v, u, t = para_canonica(valor_bruto, unidade_bruta, "parametro")
        return cls(v, u, procedencia, float(valor_bruto), unidade_bruta, (t,) if t else ())


def validar_parametro(p: Parametro | None, caminho: str, *, unidade: str, dominio: str,
                      obrigatorio: bool = True) -> list[Constatacao]:
    """Valida presença, unidade, finitude, domínio, procedência e coerência da cadeia bruto → normalizado."""
    marca = erro if obrigatorio else pendente
    if p is None or p.valor is None:
        return [marca("parametro_ausente", caminho, f"Parâmetro ausente (exigido em {unidade}, domínio "
                                                    f"{DOMINIOS[dominio]}); nenhum valor é presumido.")]
    out: list[Constatacao] = []
    if isinstance(p.valor, bool) or not isinstance(p.valor, (int, float)):
        return [erro("parametro_nao_numerico", caminho, "Parâmetro não numérico.")]
    v = float(p.valor)
    if not math.isfinite(v):
        return [erro("valor_nao_finito", caminho, "Parâmetro NaN/Inf.")]
    if p.unidade not in UNIDADES_CANONICAS:
        out.append(erro("unidade_nao_canonica", caminho,
                        f"Unidade {p.unidade!r} não canônica: converter explicitamente (Parametro.de_bruto)."))
    elif p.unidade != unidade:
        out.append(erro("unidade_incompativel", caminho, f"Unidade {p.unidade!r}; esperada {unidade!r}."))
    if dominio == "positivo" and not v > 0:
        out.append(erro("capacidade_nula" if v == 0 else "quantidade_negativa", caminho, f"Exigido > 0; recebido {v}."))
    elif dominio == "nao_negativo" and v < 0:
        out.append(erro("quantidade_negativa", caminho, f"Exigido >= 0; recebido {v}."))
    elif dominio == "eficiencia" and not (0 < v <= 1):
        out.append(erro("eficiencia_fora_do_dominio", caminho, f"Eficiência exige (0, 1]; recebido {v}."))
    elif dominio == "fracao" and not (0 <= v <= 1):
        out.append(erro("fracao_fora_do_dominio", caminho, f"Fração exige [0, 1]; recebido {v}."))
    out += validar_procedencia(p.procedencia, caminho + ".procedencia")
    if p.valor_bruto is not None or p.unidade_bruta is not None:
        out += verificar_cadeia((p.valor_bruto,), p.unidade_bruta, (v,), p.unidade, p.transformacoes, caminho)
    return out


def verificar_cadeia(brutos, unidade_bruta, normalizados, unidade: str, transformacoes, caminho: str) -> list[Constatacao]:
    """Confere a cadeia bruto → normalizado DECLARADA (parâmetros e séries; C-3A-04).

    Aceita exatamente o valor que a conversão declarada produz (``units.converter``: produto racional exato
    arredondado uma vez ao ``float`` representável) e REJEITA qualquer outro valor normalizado — inclusive uma
    alteração de 1 ulp. Não é tolerância física: as tolerâncias de ``audit.py`` não intervêm. Também exige que
    a transformação registrada corresponda à conversão (unidades e fator)."""
    out: list[Constatacao] = []
    try:
        f = fator_conversao(str(unidade_bruta), unidade)
        if brutos is None or len(brutos) != len(normalizados):
            return [erro("cadeia_transformacao_inconsistente", caminho, "Valores brutos ausentes ou com outro comprimento.")]
        ruins = [i for i, (b, v) in enumerate(zip(brutos, normalizados)) if converter(b, f) != v]
        if ruins:
            i = ruins[0]
            out.append(erro("cadeia_transformacao_inconsistente", caminho,
                            f"{len(ruins)} valor(es) normalizado(s) diferente(s) da conversão declarada (índice {i}: "
                            f"{normalizados[i]!r} {unidade} ≠ {converter(brutos[i], f)!r} {unidade} = "
                            f"{brutos[i]!r} {unidade_bruta} × {f})."))
        if f != 1:
            if not transformacoes:
                out.append(erro("transformacao_nao_registrada", caminho, "Conversão aplicada sem registro."))
            elif not any(t.unidade_origem == unidade_bruta and t.unidade_destino == unidade and t.fator == str(f)
                         for t in transformacoes):
                out.append(erro("transformacao_inconsistente", caminho,
                                f"Nenhuma transformação registrada corresponde a {unidade_bruta} → {unidade} (× {f})."))
    except Exception as exc:  # noqa: BLE001 — qualquer falha da cadeia é rejeição controlada
        out.append(erro("cadeia_transformacao_inconsistente", caminho, str(exc)))
    return out


__all__ = ["DOMINIOS", "Parametro", "validar_parametro", "verificar_cadeia"]
