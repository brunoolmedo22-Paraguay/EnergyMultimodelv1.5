"""Resultado da resolução do perfil 3C-4 (sem Pyomo; testável isoladamente).

``ResultadoResolucao3C4`` ESTENDE ``ResultadoResolucao3C3`` com a DECOMPOSIÇÃO do objetivo — custo operativo previsto
da janela (termos 3C-3), custo futuro estimado (termo terminal, instrumento de decisão) e objetivo total do solver —, o
estado terminal (energias, modo) e o relatório do auditor INDEPENDENTE do termo terminal. ``hash_entrada`` é o SHA-256
da entrada 3C-4 e ``versao_formulacao`` é ``v1.1-3C-4``: ``plano_de_resultado_3c3`` recusa este resultado (não se faz
passar por 3C-3).

``ResultadoNucleo3C3De3C4`` é a VISÃO do mesmo despacho sobre a entrada NÚCLEO 3C-3 (contradição C-3C4-01,
FORMULACAO_3C4 §10): o despacho satisfaz todas as restrições 3C-3 (o auditor 3C-3 o aprovou na própria resolução 3C-4) e
o plano 3C-0 é o do núcleo, mas o ÓTIMO refere-se ao problema 3C-4 (``perfil_resolucao``); ``custos_modelo`` conserva
o termo ``custo_futuro_estimado`` SEPARADO e ``total`` = objetivo do solver. Só é produzida a partir de um resultado
3C-4 aceito e carrega-o (``resultado_3c4``) para a verificação do plano (``plano_de_resultado_3c4``).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .resultado_3c3 import ResultadoResolucao3C3


@dataclass(frozen=True)
class ResultadoResolucao3C4(ResultadoResolucao3C3):
    hash_entrada_nucleo_3c3: str | None = None
    tipo_terminal: str | None = None
    termo_terminal: dict = field(default_factory=dict)     # chave, valor_R, energias_kWh, modo, estado terminal
    custo_operativo_previsto_R: float | None = None       # J_S (termos 3C-3)
    custo_futuro_estimado_R: float | None = None          # θ (termo terminal; nunca custo realizado)
    auditoria_terminal: object = None
    hash_sinal: str | None = None


@dataclass(frozen=True)
class ResultadoNucleo3C3De3C4(ResultadoResolucao3C3):
    perfil_resolucao: str = "v1.1-3C-4"
    hash_entrada_3c4: str | None = None
    resultado_3c4: object = None


__all__ = ["ResultadoNucleo3C3De3C4", "ResultadoResolucao3C4"]
