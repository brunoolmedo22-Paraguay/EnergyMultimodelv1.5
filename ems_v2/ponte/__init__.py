"""SEEDS2 — Piso 3C-0: ponte científica entre o EMS MILP (``ems_v2``) e a plataforma de microrredes.

Este subpacote define CONTRATOS verificáveis — não executa o EMS na aplicação, não decide commitment, não roda MPC e
não avalia valor futuro. Ver ``docs/ems_v2/PONTE_3C0.md``.

Módulos (núcleo: só biblioteca padrão, como o restante do núcleo 3A):

* ``canonico``        — JSON canônico + SHA-256 e reconstrução estrita (reutiliza ``contracts.para_dict``/``de_dict``);
* ``inventario``      — instantâneo do inventário de UMA microrrede por UID, com procedência por valor (sem agregação);
* ``requisitos``      — matriz declarativa de parâmetros exigidos por papel e sua classificação por dispositivo;
* ``cenario``         — cenário, condições iniciais, definição temporal e separação PREVISÃO × REALIZAÇÃO;
* ``projecao``        — inventário + cenário + previsão + políticas declaradas → ``EntradaModeloEMS`` (contrato 3A);
* ``execucao``        — contrato plano → execução → estado, checkpoints e desvios planejado × realizado;
* ``preflight``       — verificação científica estruturada (bloqueante / advertência / aceitável);
* ``registro``        — registro imutável e selado da execução; custo REALIZADO separado do VALOR FUTURO;
* ``instrumentacao``  — cronometria por fase, desfechos e estatísticas de campanha (p95/p99/máx).

O adaptador que LÊ microrredes reais do SEEDS2 fica em ``ems_v2.ponte_seeds2`` (único lugar de ``ems_v2`` que importa
``seeds2``; somente leitura). Testes deste subpacote são contratuais/sintéticos: NÃO constituem validação física.
"""
from __future__ import annotations

PONTE_VERSAO = "3C-0"
CONTRATO_VERSAO = 1

__all__ = ["CONTRATO_VERSAO", "PONTE_VERSAO"]
