"""SEEDS2 — Piso 3C-1: commitment dinâmico verificável (M09–M12) do EMS ``milp_mpc_v1``.

Só biblioteca padrão (como o núcleo 3A). Este subpacote NÃO resolve nada: define o contrato do perfil
``v1.1-3C-1``, a discretização auditável dos parâmetros temporais, a memória operativa entre janelas, o preflight do
commitment e o AUDITOR INDEPENDENTE (sem Pyomo/HiGHS). O MILP correspondente está em ``ems_v2.milp.modelo_3c1`` /
``ems_v2.milp.solver_3c1``.

Módulos:

* ``contrato``      — ``EntradaCommitment3C1`` (embrulho versionado de uma ``EntradaModeloEMS`` perfil 3B-P + dados
  de commitment POR UNIDADE + memória + política terminal de permanência + termos adicionais), validação e JSON
  canônico/hash próprios. As entradas 3A/3B-P NÃO mudam (nem texto canônico, nem SHA-256);
* discretização (em ``contrato``) — conversão EXPLÍCITA e exata (``Fraction``) dos parâmetros declarados para a malha:
  U = ⌈T_on/Δ⌉, D = ⌈T_off/Δ⌉, R⁺Δ, R⁻Δ, limites efetivos de partida/parada S⁺/S⁻, representabilidade das
  transições e obrigações iniciais;
* ``memoria``       — memória terminal (tempo no estado, obrigação residual) e transporte entre janelas;
* ``preflight``     — verificação antes do solver (compromisso parcial, obrigações × disponibilidade, transições
  fixadas não representáveis);
* ``auditor``       — auditor algébrico independente do perfil 3C-1 (M02–M08, M09–M12, M10, M14–M16 e custos).

Testes deste subpacote são sintéticos/algébricos: não constituem validação física de nenhum equipamento.
"""
from __future__ import annotations

__all__: list[str] = []
