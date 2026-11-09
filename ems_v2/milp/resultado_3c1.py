"""Resultado da resolução do perfil 3C-1 (sem Pyomo; testável isoladamente).

``ResultadoResolucao3C1`` ESTENDE ``ResultadoResolucao`` (mesmos campos, mesma classificação e mesmos estados de
despacho do 3B-P) com o que o commitment dinâmico acrescenta: discretização por unidade, eventos, memória terminal
planejada, obrigações residuais, garantia de permanência e transições bloqueadas. ``hash_entrada`` é o SHA-256 da
ENTRADA 3C-1 (``compromisso.contrato.hash_entrada_3c1``), nunca o da base: um plano 3C-0 não pode ser criado a partir
deste resultado com a entrada base (``plano_de_resultado`` recusa a divergência de hash).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .resultado import ResultadoResolucao


@dataclass(frozen=True)
class ResultadoResolucao3C1(ResultadoResolucao):
    discretizacao: dict = field(default_factory=dict)          # uid → parâmetros discretos (dict serializável)
    eventos: dict = field(default_factory=dict)                # uid → {"partidas": n, "paradas": n}
    memoria_terminal: tuple = ()                               # compromisso.memoria.MemoriaFronteira (fronteira N)
    obrigacoes_residuais_s: dict = field(default_factory=dict)  # uid → s (> 0) além da janela
    garantia_permanencia: str | None = None                    # "completa_na_janela" | "residual_vinculante"
    transicoes_bloqueadas: tuple[str, ...] = ()
    politica_permanencia: str | None = None


__all__ = ["ResultadoResolucao3C1"]
