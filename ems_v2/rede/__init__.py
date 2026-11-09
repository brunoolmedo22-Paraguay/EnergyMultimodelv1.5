"""SEEDS2 — Piso 3C-3: interconexão elétrica controlada (PCC), intercâmbio econômico e recurso EXPLÍCITO de equilíbrio.

Núcleo só com a biblioteca padrão (como 3A/3C-0/3C-1/3C-2): nenhum módulo deste subpacote importa Pyomo, HiGHS,
Streamlit nem ``seeds2``. O MILP do perfil vive em ``ems_v2/milp/*_3c3.py`` (único subpacote autorizado a importar o
solver) e o MPC conectado reutiliza o orquestrador 3C-2 por pontos de extensão explícitos.

Módulos:

* ``contrato``   — PCC versionado (modo, sentidos permitidos, limites contratados por intervalo, disponibilidade,
  medidores), perfis tarifários por blocos (natureza, revisão, emissão, regra de aplicação, hash), política econômica
  e o contrato EMBRULHO ``EntradaRede3C3`` (base = ``EntradaCommitment3C1`` validada SEM relaxação);
* ``preflight``  — condições do perfil antes do solver (sem Pyomo);
* ``auditor``    — auditor INDEPENDENTE do perfil (compõe o auditor 3C-1 e substitui o balanço M02 pelo balanço com PCC);
* ``execucao``   — política de ajuste local do PCC, injeção renovável limitada pela disponibilidade, executor algébrico
  conectado, plano de intercâmbio, desvios programado × realizado e liquidação econômica realizada;
* ``registro``   — anexo selado 3C-3 ao registro 3C-0 (esquemas históricos inalterados);
* ``mpc``        — controlador MPC conectado (subclasse de ``ControladorMPC`` pelos pontos de extensão), planta de ensaio
  conectada, persistência/retomada verificada e auditoria da missão conectada;
* ``experimentos`` / ``comparadores`` — G1–G15 e comparação open-loop × MPC.

Rótulo obrigatório: modelo ALGÉBRICO agregado do intercâmbio no PCC para experimentos de despacho energético. NÃO
representa fluxo AC, tensões, potência reativa, frequência, proteção, transitórios nem dinâmica de conversores; o
ajuste realizado NÃO é controle primário de frequência validado. Tarifas dos experimentos são SINTÉTICAS e rotuladas;
nenhuma função aqui representa uma fatura elétrica real. Nada é integrado à aplicação (o EMS V1.6 continua sendo o
único motor operacional).
"""
from __future__ import annotations

FORMULACAO_3C3 = "v1.1-3C-3"
ESQUEMA_3C3 = 1
ESTADO_MOTOR_3C3 = "experimental_milp_mpc_conectado_algebrico"
ROTULO_REDE = ("modelo ALGÉBRICO agregado do intercâmbio no PCC (balanço ativo em kW no barramento equivalente) — "
               "sintético; não é fluxo AC, tensão, reativo, frequência, proteção nem controle primário validado; "
               "tarifas sintéticas não são fatura real")

__all__ = ["ESQUEMA_3C3", "ESTADO_MOTOR_3C3", "FORMULACAO_3C3", "ROTULO_REDE"]
