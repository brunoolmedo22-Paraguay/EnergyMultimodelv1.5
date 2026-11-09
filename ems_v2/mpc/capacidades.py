"""Registro DECLARATIVO de capacidades do perfil MPC 3C-2 (M23). Não executa nada; não altera ``ems_v2.capabilities``.

O 3C-2 não cria nova formulação de janela: cada janela continua sendo uma ``EntradaCommitment3C1`` (perfil
``v1.1-3C-1``). O que muda é a família ``mpc`` (M23): horizonte recedente, propagação do estado APLICADO e política de
informação — implementados com o executor ALGÉBRICO (Φ_phys = dublê 3C-1; modelo físico pendente).
"""
from __future__ import annotations

from ..capabilities import CAPACIDADES_3C1, MOTOR_ID, CapacidadeMotor

STATUS_3C2 = {
    "implementado_3C2": "Implementado no orquestrador MPC E verificado pela auditoria temporal/causal independente",
    "parcial_3C2": "Parte da família implementada; o restante é bloqueado ou declarado não modelado",
}
_MPC = (
    CapacidadeMotor(MOTOR_ID, "mpc", ("M23",), "parcial_3C2", "3C-2",
                    "Horizonte recedente (N, m, K_M, política terminal), K6 append-only, previsão reemitida por janela, "
                    "estado/memória EXECUTADOS transportados, registros encadeados. Φ_phys = dublê ALGÉBRICO 3C-1 "
                    "(x_state/u_applied/w_dist implementados; modelo físico com memória interna pendente: 3D)."),
    CapacidadeMotor(MOTOR_ID, "planejamento_hierarquico", ("TERM-SOFT", "TERM-HARD"), "nao_suportado", "3C-4",
                    "Valor futuro/referência terminal e planejador de longo prazo: não implementados nem contabilizados."),
)
CAPACIDADES_3C2: tuple[CapacidadeMotor, ...] = tuple(c for c in CAPACIDADES_3C1 if c.familia != "mpc") + _MPC[:1]

__all__ = ["CAPACIDADES_3C2", "STATUS_3C2"]
