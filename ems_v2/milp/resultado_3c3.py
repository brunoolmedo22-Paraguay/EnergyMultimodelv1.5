"""Resultado da resolução do perfil 3C-3 (sem Pyomo; testável isoladamente).

``ResultadoResolucao3C3`` ESTENDE ``ResultadoResolucao3C1`` (mesma classificação, mesmos estados de despacho) com o
intercâmbio PROGRAMADO no PCC e o detalhe econômico do objetivo (gasto de importação e crédito de exportação
SEPARADOS). ``hash_entrada`` é o SHA-256 da ENTRADA 3C-3 (``rede.contrato.hash_entrada_3c3``) e ``versao_formulacao`` é
``v1.1-3C-3``: o resultado nunca se faz passar por 3C-1 (``plano_de_resultado_3c1`` recusa a divergência).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .resultado_3c1 import ResultadoResolucao3C1


@dataclass(frozen=True)
class ResultadoResolucao3C3(ResultadoResolucao3C1):
    modo_conexao: str | None = None
    intercambio: dict = field(default_factory=dict)           # {"P_imp": N, "P_exp": N, "w"?: N} PROGRAMADO
    economia_rede: dict = field(default_factory=dict)         # gasto_importacao_R, receita_exportacao_R, liquido_R
    hash_tarifas: dict = field(default_factory=dict)          # grandeza → SHA-256 do perfil usado na decisão


__all__ = ["ResultadoResolucao3C3"]
