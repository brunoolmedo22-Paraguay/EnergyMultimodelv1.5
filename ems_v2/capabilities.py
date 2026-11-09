"""Registro DECLARATIVO de capacidades por motor (``EngineCapability``) — política de dois motores.

Nenhuma entrada aqui executa nada. ``legacy_v16`` é só um DESCRITOR (o código está em ``ems_integration`` e
não é importado). ``milp_mpc_v1`` não tem solver no Piso 3A: o que está "implementado" é contrato, referência
algébrica e auditoria — nunca despacho. Capacidade não habilitada ⇒ ``nao_suportado`` e rejeição.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import ESTADO_MOTOR, FORMULACAO_3BP, FORMULACAO_3C1, FORMULACAO_VERSAO, MOTOR_ID, MOTOR_LEGADO_ID

STATUS_CAPACIDADE = {
    "implementado_3A": "Contrato + cálculo de referência e/ou auditoria algébrica (sem solver)",
    "parcial_3A": "Só parte da família (p. ex. domínio PWL do caso A06); restante futuro",
    "apenas_especificacao": "Fixture/resultado teórico registrado; implementação em piso posterior",
    "nao_suportado": "Rejeitado explicitamente no Piso 3A",
}


@dataclass(frozen=True)
class DescritorMotor:
    motor_id: str
    rotulo_ptbr: str
    estado: str
    pacote: str
    observacoes: str


@dataclass(frozen=True)
class CapacidadeMotor:
    motor_id: str
    familia: str
    equacoes: tuple[str, ...]
    status: str
    piso_previsto: str
    observacoes: str = ""


MOTORES = {
    MOTOR_LEGADO_ID: DescritorMotor(
        MOTOR_LEGADO_ID, "EMS V1.6 — Legado (GA/GWO/NGO + SLSQP)", "unico_motor_operacional", "ems_integration",
        "Único motor acessível na aplicação; comparador científico. Limitações conhecidas (dossiê C01–C19) não "
        "são corrigidas aqui; a aceitação da candidata de menor violação não certifica factibilidade física."),
    MOTOR_ID: DescritorMotor(
        MOTOR_ID, "EMS MILP–MPC (experimental)", ESTADO_MOTOR, "ems_v2",
        f"Formulação {FORMULACAO_VERSAO}: sem solver. Formulação {FORMULACAO_3BP}: MILP de UMA janela via "
        "ems_v2.milp (Pyomo + HiGHS), só por API/testes; sem MPC, sem seletor na interface (Piso 3D)."),
}

_C = CapacidadeMotor
CAPACIDADES: tuple[CapacidadeMotor, ...] = (
    _C(MOTOR_ID, "tempo", ("M01", "TEMP-13"), "implementado_3A", "3A", "N intervalos / N+1 fronteiras; H_f/H_o/ρ/T_M."),
    _C(MOTOR_ID, "conjuntos_e_contrato", ("CONJ-2", "EST-INI"), "implementado_3A", "3A",
       "Dados por UID; estado inicial declarado e coerente (sem inferência)."),
    _C(MOTOR_ID, "balanco", ("M02",), "implementado_3A", "3A", "Auditoria do balanço; P_aux (M05) não suportado."),
    _C(MOTOR_ID, "renovavel", ("M03-v1.1", "B01-KPI"), "implementado_3A", "3A",
       "Referência e auditoria; disponibilidade binária."),
    _C(MOTOR_ID, "servico_descarte", ("M04",), "implementado_3A", "3A", "Serviço duro/degradado; D̄ = 0 sem dispositivo."),
    _C(MOTOR_ID, "bess", ("M06", "M07", "M08"), "implementado_3A", "3A",
       "Exclusividade por min(P^c, P^d); z_b binária é do MILP (3B)."),
    _C(MOTOR_ID, "custo_curtailment", ("M21-CURT",), "implementado_3A", "3A",
       "Único termo econômico reconstruído no Piso 3A."),
    _C(MOTOR_ID, "pwl_pemfc_sintetica", ("M10", "M15", "M16"), "parcial_3A", "3B",
       "Avaliação/auditoria da PWL sintética num ponto (A06); M14 (segmentos binários) é do MILP."),
    _C(MOTOR_ID, "auxiliares", ("M05",), "nao_suportado", "3C", "Exige dados de eventos/standby."),
    _C(MOTOR_ID, "commitment", ("M09", "M11a", "M11b", "M11-EXT", "M12"), "nao_suportado", "3C"),
    _C(MOTOR_ID, "pwl_segmentos_milp", ("M14",), "apenas_especificacao", "3B"),
    _C(MOTOR_ID, "pemfc_faraday", ("M13",), "nao_suportado", "3D", "Curva real só após validação estática (B04)."),
    _C(MOTOR_ID, "combustivel_instantaneo", ("M17", "B05-INST"), "apenas_especificacao", "3B/3C"),
    _C(MOTOR_ID, "estoque_h2", ("M18",), "nao_suportado", "3D", "Sem tanque: suprimento externo declarado."),
    _C(MOTOR_ID, "termica_custo", ("M19",), "apenas_especificacao", "3B"),
    _C(MOTOR_ID, "multimodo", ("M20", "M20b", "M20c", "B05-MULTI-BAL", "B05-MULTI-H2", "M21-MULTI"), "nao_suportado",
       "3C", "Só com dados de transição."),
    _C(MOTOR_ID, "objetivo_economico", ("M21-v1.1", "M21-REG"), "apenas_especificacao", "3B"),
    _C(MOTOR_ID, "prioridade_lexicografica", ("M22",), "apenas_especificacao", "3C"),
    _C(MOTOR_ID, "terminal", ("TERM-SOFT", "TERM-HARD"), "nao_suportado", "3B/3C", "Decisão D02 pendente."),
    _C(MOTOR_ID, "conversao_fronteira_bess", ("BND-BESS",), "nao_suportado", "3D"),
    _C(MOTOR_ID, "mpc", ("M23",), "apenas_especificacao", "3C"),
)


# Perfil do Piso 3B-P (formulação v1.1-3B-P): o MILP Pyomo/HiGHS constrói as famílias abaixo e o auditor independente
# verifica cada uma que o solver declara suportada. O registro 3A (CAPACIDADES) permanece como histórico.
STATUS_CAPACIDADE.update({
    "implementado_3BP": "Construído no MILP (Pyomo + HiGHS) E verificado pelo auditor independente",
    "parcial_3BP": "Parte da família no MILP e no auditor; o restante é bloqueado ou declarado não modelado",
})
CAPACIDADES_3BP: tuple[CapacidadeMotor, ...] = (
    _C(MOTOR_ID, "tempo", ("M01",), "implementado_3BP", "3B-P", "Potências em T (N), energia em K (N+1)."),
    _C(MOTOR_ID, "tempo", ("TEMP-13",), "parcial_3BP", "3B-P",
       "Uma janela por resolução; sem MPC/reotimização (3C); δ_phys não modelado."),
    _C(MOTOR_ID, "conjuntos_e_contrato", ("EST-INI",), "implementado_3BP", "3B-P", "Estado inicial por UID."),
    _C(MOTOR_ID, "conjuntos_e_contrato", ("CONJ-2",), "parcial_3BP", "3B-P", "Sem depósitos de H2."),
    _C(MOTOR_ID, "balanco", ("M02",), "parcial_3BP", "3B-P", "Sem folgas; P_aux (M05) não modelado."),
    _C(MOTOR_ID, "renovavel", ("M03-v1.1", "B01-KPI"), "implementado_3BP", "3B-P"),
    _C(MOTOR_ID, "servico_descarte", ("M04",), "implementado_3BP", "3B-P",
       "Duro ⇒ ℓ inexistente; degradado exige critério ENS explícito; d só com dispositivo."),
    _C(MOTOR_ID, "bess", ("M06", "M07", "M08"), "implementado_3BP", "3B-P", "Exclusividade por binária z_b."),
    _C(MOTOR_ID, "custo_curtailment", ("M21-CURT",), "implementado_3BP", "3B-P"),
    _C(MOTOR_ID, "objetivo_economico", ("M21-v1.1",), "parcial_3BP", "3B-P",
       "Termos: curtailment, throughput, ENS (V_ℓ declarado), combustível h·q (c_H declarado)."),
    _C(MOTOR_ID, "objetivo_economico", ("M21-REG",), "apenas_especificacao", "3C"),
    _C(MOTOR_ID, "pwl_pemfc_sintetica", ("M10",), "parcial_3BP", "3B-P",
       "Compromisso FIXO (programa constante = estado inicial); u não é decidido pelo MILP no 3B-P."),
    _C(MOTOR_ID, "pwl_pemfc_sintetica", ("M15", "M16"), "implementado_3BP", "3B-P",
       "Interpolante exato da curva SINTÉTICA (B04: curva real exige certificação estática)."),
    _C(MOTOR_ID, "pwl_segmentos_milp", ("M14",), "implementado_3BP", "3B-P", "Binárias por segmento, sem SOS."),
    _C(MOTOR_ID, "combustivel_instantaneo", ("M17", "B05-INST"), "parcial_3BP", "3B-P",
       "Só h·q; eventos inexistentes porque transições são bloqueadas."),
    _C(MOTOR_ID, "auxiliares", ("M05",), "nao_suportado", "3C"),
    _C(MOTOR_ID, "commitment", ("M09", "M11a", "M11b", "M11-EXT", "M12"), "nao_suportado", "3C",
       "Programa livre ou com transições é BLOQUEADO; rampas/permanências não modeladas nem certificadas."),
    _C(MOTOR_ID, "pemfc_faraday", ("M13",), "nao_suportado", "3D"),
    _C(MOTOR_ID, "estoque_h2", ("M18",), "nao_suportado", "3D"),
    _C(MOTOR_ID, "termica_custo", ("M19",), "apenas_especificacao", "3C"),
    _C(MOTOR_ID, "multimodo", ("M20", "M20b", "M20c", "B05-MULTI-BAL", "B05-MULTI-H2", "M21-MULTI"), "nao_suportado", "3C"),
    _C(MOTOR_ID, "prioridade_lexicografica", ("M22",), "apenas_especificacao", "3C"),
    _C(MOTOR_ID, "terminal", ("TERM-SOFT", "TERM-HARD"), "nao_suportado", "3C", "Só 'nenhuma' em casos analíticos."),
    _C(MOTOR_ID, "conversao_fronteira_bess", ("BND-BESS",), "nao_suportado", "3D"),
    _C(MOTOR_ID, "mpc", ("M23",), "apenas_especificacao", "3C"),
)
# Perfil do Piso 3C-1 (formulação v1.1-3C-1, contrato embrulho ``ems_v2.compromisso``): commitment dinâmico de UMA
# janela no MILP (``ems_v2.milp.solver_3c1``) e no auditor independente (``ems_v2.compromisso.auditor``). Os registros
# 3A e 3B-P permanecem como histórico (não mudam).
STATUS_CAPACIDADE.update({
    "implementado_3C1": "Construído no MILP 3C-1 (Pyomo + HiGHS) E verificado pelo auditor independente 3C-1",
    "parcial_3C1": "Parte da família no MILP 3C-1 e no auditor; o restante é bloqueado ou declarado não modelado",
})
_SUBST_3C1 = {
    "M10": _C(MOTOR_ID, "pwl_pemfc_sintetica", ("M10",), "parcial_3C1", "3C-1",
              "u DECIDIDO pelo MILP (M09) com disponibilidade; n_f = Σ u por bloco é saída (não reportada como agregado)."),
    "commitment": _C(MOTOR_ID, "commitment", ("M09", "M11a", "M11b", "M12"), "implementado_3C1", "3C-1",
                     "Variante INSTANTÂNEA por unidade: transições y/z, rampas com p_{-1}, limites de partida/parada "
                     "declarados ou interpretação conservadora R·Δ, permanências U/D = ⌈T/Δ⌉, obrigações herdadas e "
                     "política terminal explícita; transição não representável ⇒ bloqueada com diagnóstico."),
    "M11-EXT": _C(MOTOR_ID, "commitment", ("M11-EXT",), "nao_suportado", "3C+",
                  "Potências de extremo não modeladas: M11 restringe consignas de intervalo (aproximação declarada)."),
    "combustivel": _C(MOTOR_ID, "combustivel_instantaneo", ("M17", "B05-INST"), "parcial_3C1", "3C-1",
                      "h·q + m^SU y + m^SD z (massas DECLARADAS, exigidas para PEMFC com transições); W^SU/W^SD "
                      "(energia elétrica de evento) não modelados."),
    "objetivo": _C(MOTOR_ID, "objetivo_economico", ("M21-v1.1",), "parcial_3C1", "3C-1",
                   "Termos 3B-P + 'eventos' Σ(C_SU y + C_SD z) [R$/evento, sem h]; geração térmica (M19), descarte, "
                   "terminal e regularizador continuam futuros."),
}


def _perfil_3c1() -> tuple[CapacidadeMotor, ...]:
    out = []
    for c in CAPACIDADES_3BP:
        if c.familia == "commitment":
            out += [_SUBST_3C1["commitment"], _SUBST_3C1["M11-EXT"]]
        elif c.equacoes == ("M10",):
            out.append(_SUBST_3C1["M10"])
        elif c.familia == "combustivel_instantaneo":
            out.append(_SUBST_3C1["combustivel"])
        elif c.familia == "objetivo_economico" and c.equacoes == ("M21-v1.1",):
            out.append(_SUBST_3C1["objetivo"])
        elif c.status in ("implementado_3BP", "parcial_3BP"):
            out.append(_C(c.motor_id, c.familia, c.equacoes, c.status.replace("3BP", "3C1"), "3B-P/3C-1", c.observacoes))
        else:
            out.append(c)
    return tuple(out)


CAPACIDADES_3C1: tuple[CapacidadeMotor, ...] = _perfil_3c1()
PERFIS = {FORMULACAO_VERSAO: CAPACIDADES, FORMULACAO_3BP: CAPACIDADES_3BP, FORMULACAO_3C1: CAPACIDADES_3C1}


def capacidades(motor_id: str = MOTOR_ID, formulacao: str = FORMULACAO_VERSAO) -> tuple[CapacidadeMotor, ...]:
    return tuple(c for c in PERFIS[formulacao] if c.motor_id == motor_id)


def status_equacao(eq: str, formulacao: str = FORMULACAO_VERSAO) -> str | None:
    for c in PERFIS[formulacao]:
        if eq in c.equacoes:
            return c.status
    return None


# alias com o nome da ordem executiva
EngineCapability = CapacidadeMotor

__all__ = ["CAPACIDADES", "CAPACIDADES_3BP", "CAPACIDADES_3C1", "PERFIS", "CapacidadeMotor", "DescritorMotor", "EngineCapability", "MOTORES", "STATUS_CAPACIDADE",
           "capacidades", "status_equacao"]
