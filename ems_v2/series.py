"""Séries temporais tipadas (requisitos R02/R03; especificação v1.0 §14).

Uma série declara a sua SEMÂNTICA: ``media_intervalo`` (valor médio em ``[t, t+passo)``; energia = valor × duração)
ou ``amostra_instantanea`` (valor num instante). São contratos diferentes: o Piso 3A NÃO converte um no outro e
NÃO reamostra. Uma série só é usada numa malha se for média de intervalo, com o MESMO passo, alinhada e cobrindo
todos os intervalos — caso contrário, rejeição explícita. Ausentes (NaN/Inf) nunca viram zero.

A série é regular por construção (início + passo + valores). ``de_instantes`` constrói a partir de instantes
explícitos e rejeita fuso ambíguo, duplicatas, ordem não monotônica e passo irregular.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Sequence

from .diagnostics import Constatacao, ContratoInvalido, aviso, erro
from .provenance import Procedencia, Transformacao, validar_procedencia
from .timegrid import MalhaTemporal, ler_instante_utc
from .units import UNIDADES_CANONICAS, exato, fator_conversao

SEMANTICAS = {
    "media_intervalo": "interval_mean — média do intervalo [t, t+passo)",
    "amostra_instantanea": "instant_sample — valor num instante",
}
FRONTEIRAS_POTENCIA = {"barramento_liquido": "kW líquidos no barramento equivalente (convenção do contrato)"}


@dataclass(frozen=True)
class SerieTemporal:
    grandeza: str                   # "potencia" | "disponibilidade" | "fracao_interrompivel"
    unidade: str                    # canônica
    semantica: str                  # chave de SEMANTICAS (obrigatória, sem padrão)
    inicio_utc: str
    passo_s: int
    valores: tuple[float, ...]
    procedencia: Procedencia | None
    fronteira: str | None = None    # obrigatória para potência: "barramento_liquido"
    valores_brutos: tuple[float, ...] | None = None
    unidade_bruta: str | None = None
    transformacoes: tuple[Transformacao, ...] = field(default_factory=tuple)
    emissao_utc: str | None = None  # emissão da previsão (causalidade)

    @classmethod
    def de_instantes(cls, instantes: Sequence[str], valores: Sequence[float], **kw) -> "SerieTemporal":
        c: list[Constatacao] = []
        if len(instantes) != len(valores):
            raise ContratoInvalido([erro("comprimento_incompativel", "serie", "Instantes e valores com tamanhos distintos.")])
        if len(instantes) < 1:
            raise ContratoInvalido([erro("serie_vazia", "serie", "Série sem valores.")])
        ts = []
        for i, txt in enumerate(instantes):
            dt, ci = ler_instante_utc(txt, f"serie.instantes[{i}]")
            c += ci
            ts.append(dt)
        if c:
            raise ContratoInvalido(c)
        passos = [(b - a).total_seconds() for a, b in zip(ts, ts[1:])]
        for i, p in enumerate(passos):
            if p == 0:
                c.append(erro("instante_duplicado", f"serie.instantes[{i + 1}]", "Instante duplicado (período repetido)."))
            elif p < 0:
                c.append(erro("instantes_nao_monotonos", f"serie.instantes[{i + 1}]", "Instantes fora de ordem."))
        if c:
            raise ContratoInvalido(c)
        if len(set(passos)) > 1:
            raise ContratoInvalido([erro("passo_irregular", "serie.instantes",
                                         f"Passos distintos {sorted(set(passos))[:5]} s: reamostragem não é feita no Piso 3A.")])
        passo = passos[0] if passos else kw.pop("passo_s", None)
        if passo is None or float(passo) != int(passo) or int(passo) <= 0:
            raise ContratoInvalido([erro("passo_invalido", "serie.passo_s", "Passo em segundos inteiros > 0 exigido.")])
        kw.pop("passo_s", None)
        return cls(inicio_utc=ts[0].isoformat(), passo_s=int(passo), valores=tuple(float(v) for v in valores), **kw)


def validar_serie(s: SerieTemporal, caminho: str, *, unidade: str, grandeza: str) -> list[Constatacao]:
    out: list[Constatacao] = []
    if s.grandeza != grandeza:
        out.append(erro("grandeza_incompativel", caminho, f"Grandeza {s.grandeza!r}; esperada {grandeza!r}."))
    if s.semantica not in SEMANTICAS:
        out.append(erro("semantica_nao_declarada", caminho + ".semantica",
                        "Declarar 'media_intervalo' ou 'amostra_instantanea' (sem padrão implícito)."))
    if s.unidade not in UNIDADES_CANONICAS:
        out.append(erro("unidade_nao_canonica", caminho + ".unidade", f"Unidade {s.unidade!r} não canônica."))
    elif s.unidade != unidade:
        out.append(erro("unidade_incompativel", caminho + ".unidade", f"Unidade {s.unidade!r}; esperada {unidade!r}."))
    if grandeza == "potencia":
        if s.fronteira is None:
            out.append(erro("fronteira_incerta", caminho + ".fronteira", "Potência sem fronteira declarada."))
        elif s.fronteira not in FRONTEIRAS_POTENCIA:
            out.append(erro("potencia_fora_do_barramento", caminho + ".fronteira",
                            f"Fronteira {s.fronteira!r}: só potência líquida no barramento é aceita no contrato "
                            "normalizado (conversão de fronteira não implementada no Piso 3A)."))
    _, c = ler_instante_utc(s.inicio_utc, caminho + ".inicio_utc")
    out += c
    if isinstance(s.passo_s, bool) or not isinstance(s.passo_s, int) or s.passo_s <= 0:
        out.append(erro("passo_invalido", caminho + ".passo_s", "Passo em segundos inteiros > 0 exigido."))
    if not s.valores:
        out.append(erro("serie_vazia", caminho + ".valores", "Série sem valores."))
    ruins = [i for i, v in enumerate(s.valores)
             if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)]
    if ruins:
        out.append(erro("valor_ausente_ou_nao_finito", caminho + ".valores",
                        f"{len(ruins)} valor(es) NaN/Inf/não numéricos (índices {ruins[:8]}): ausente nunca vira zero."))
    out += validar_procedencia(s.procedencia, caminho + ".procedencia")
    if s.emissao_utc is not None:
        out += ler_instante_utc(s.emissao_utc, caminho + ".emissao_utc")[1]
    if s.valores_brutos is not None or s.unidade_bruta is not None:
        try:
            f = fator_conversao(str(s.unidade_bruta), s.unidade)
            if s.valores_brutos is None or len(s.valores_brutos) != len(s.valores) or any(
                    exato(b) * f != exato(v) for b, v in zip(s.valores_brutos, s.valores) if not ruins):
                out.append(erro("cadeia_transformacao_inconsistente", caminho,
                                "Valores normalizados não correspondem aos brutos com a conversão declarada."))
            if f != 1 and not s.transformacoes:
                out.append(erro("transformacao_nao_registrada", caminho, "Conversão aplicada sem registro."))
        except Exception as exc:  # noqa: BLE001
            out.append(erro("cadeia_transformacao_inconsistente", caminho, str(exc)))
    return out


def alinhar_a_malha(s: SerieTemporal, malha: MalhaTemporal, caminho: str) -> tuple[tuple[float, ...] | None, list[Constatacao]]:
    """Extrai os N valores da janela. Sem conversão de semântica, sem reamostragem, sem extrapolação."""
    out: list[Constatacao] = []
    if s.semantica != "media_intervalo":
        out.append(erro("amostra_instantanea_como_media", caminho + ".semantica",
                        "Série de amostras instantâneas não pode ser usada como média de intervalo sem reconstrução "
                        "declarada (não implementada no Piso 3A)."))
    if s.passo_s != malha.delta_s:
        out.append(erro("resolucao_incompativel", caminho + ".passo_s",
                        f"Passo {s.passo_s} s ≠ Δ = {malha.delta_s} s: reamostragem não é feita no Piso 3A."))
    t_s, c1 = ler_instante_utc(s.inicio_utc, caminho + ".inicio_utc")
    out += c1
    if out:
        return None, out
    t_m = malha.inicio()
    desloc = (t_m - t_s).total_seconds()
    if desloc < 0:
        return None, [erro("cobertura_insuficiente", caminho, "A série começa depois do início da janela.")]
    if desloc % s.passo_s:
        return None, [erro("serie_desalinhada", caminho, "Intervalos da série não coincidem com os da malha.")]
    i0 = int(desloc // s.passo_s)
    if i0 + malha.N > len(s.valores):
        return None, [erro("cobertura_insuficiente", caminho,
                           f"A série cobre {max(len(s.valores) - i0, 0)} de {malha.N} intervalos: sem extrapolação.")]
    if s.emissao_utc is None:
        out.append(aviso("emissao_nao_declarada", caminho + ".emissao_utc",
                         "Emissão da previsão não declarada: causalidade não verificável."))
    else:
        e, _ = ler_instante_utc(s.emissao_utc, caminho + ".emissao_utc")
        if e is not None and e > t_m:
            out.append(erro("previsao_nao_causal", caminho + ".emissao_utc",
                            "Previsão emitida depois do início da janela (informação futura)."))
    vals = s.valores[i0:i0 + malha.N]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vals):
        out.append(erro("valor_ausente_ou_nao_finito", caminho, "Valor NaN/Inf na janela."))
        return None, out
    return tuple(float(v) for v in vals), out


def fim_utc(s: SerieTemporal):
    t, _ = ler_instante_utc(s.inicio_utc, "serie")
    return None if t is None else t + timedelta(seconds=s.passo_s * len(s.valores))


__all__ = ["FRONTEIRAS_POTENCIA", "SEMANTICAS", "SerieTemporal", "alinhar_a_malha", "fim_utc", "validar_serie"]
