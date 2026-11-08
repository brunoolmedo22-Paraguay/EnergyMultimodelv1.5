"""Contrato canônico de entrada do EMS MILP–MPC (Piso 3A) — dados por UID, sem agregação V1.6.

Convenção de sinais (fixa, ordem executiva 3A.1): toda potência do balanço é kW LÍQUIDO no barramento equivalente;
``P_positivo = injeta no barramento``; ``P_carga >= 0`` CONSOME do barramento; ``P_descarga >= 0`` INJETA.
Demanda e potencial renovável são séries de média de intervalo no barramento.

Nenhum parâmetro físico, custo, eficiência, estado inicial ou política terminal é presumido: todos os campos
científicos são obrigatórios e explícitos; ausência → constatação (``erro``/``pendente``). O único valor fixado
por política aprovada é a capacidade de descarte nula quando NÃO existe dispositivo de descarte declarado
(adenda v1.1: "D̄=0 por defecto"; decisão D03).

Nomes em PT-BR; aliases com os nomes da ordem executiva no fim do módulo (``TimeGrid`` …).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import types
import typing
from dataclasses import MISSING, dataclass, field, fields, is_dataclass

from . import ESQUEMA_VERSAO, FORMULACAO_VERSAO, MOTOR_ID
from .diagnostics import Constatacao, RelatorioValidacao, aviso, erro, pendente
from .parameters import Parametro, validar_parametro
from .provenance import Procedencia, Transformacao, validar_procedencia
from .series import SerieTemporal, alinhar_a_malha, validar_serie
from .timegrid import MalhaTemporal, validar_malha

RE_EQUIPAMENTO = re.compile(r"^(eq-[0-9a-f]{12}|arr-[0-9a-f]{12}|syn-[a-z0-9][a-z0-9_-]{0,39})$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


# =============================================================================== identidade
@dataclass(frozen=True)
class UIDRecurso:
    """Identidade de um recurso. ``equipamento`` segue o inventário (``eq-…``, ``arr-…``) ou é sintético
    (``syn-…``); ``unidade`` (>= 1) distingue unidades físicas de um equipamento com ``quantity > 1`` sem
    inventar identificadores (expansão feita pelo adaptador do Piso 3D)."""
    equipamento: str
    unidade: int | None = None

    def __str__(self) -> str:
        return self.equipamento if self.unidade is None else f"{self.equipamento}#{self.unidade}"


def validar_uid(u: UIDRecurso, caminho: str) -> list[Constatacao]:
    if not isinstance(u, UIDRecurso) or not isinstance(u.equipamento, str) or not RE_EQUIPAMENTO.fullmatch(u.equipamento):
        return [erro("uid_invalido", caminho, f"UID inválido: {u!r}.")]
    if u.unidade is not None and (isinstance(u.unidade, bool) or not isinstance(u.unidade, int) or u.unidade < 1):
        return [erro("uid_invalido", caminho, "Índice de unidade deve ser inteiro >= 1.")]
    return []


# =============================================================================== fronteira e disponibilidade
TIPOS_FRONTEIRA = {"barramento_equivalente_unico": "Barramento elétrico equivalente único (adenda v1.1 §A)"}
TOPOLOGIAS = {"isolada": "Microrrede isolada (único escopo do Piso 3A)"}
CONVENCAO_POTENCIA = "kW_liquido_no_barramento"


@dataclass(frozen=True)
class FronteiraBarramento:
    tipo: str
    topologia: str
    convencao_potencia: str
    procedencia: Procedencia | None


@dataclass(frozen=True)
class Disponibilidade:
    """``a_{x,t} ∈ {0, 1}`` exógena por intervalo (variante binária). Fracionária → pendente (adenda B01)."""
    serie: SerieTemporal


# =============================================================================== demanda e renováveis
CRITICIDADES = {"critica": "Crítica — sem interrupção (χ = 0)", "interrompivel": "Interrompível com autorização (χ ∈ [0, 1])"}


@dataclass(frozen=True)
class ClasseDemanda:
    uid: UIDRecurso
    nome: str
    criticidade: str
    potencia: SerieTemporal                          # L_{ℓ,t} [kW barramento]
    fracao_interrompivel: SerieTemporal | None = None  # χ_{ℓ,t}; obrigatória se interrompível; proibida (>0) se crítica


TECNOLOGIAS_RENOVAVEIS = {"fv": "Fotovoltaica", "eolica": "Eólica"}
BASES_POTENCIAL = {
    "antes_da_disponibilidade": "A_pot antes da disponibilidade (A_utilizável = a × A_pot)",
    "utilizavel_apos_disponibilidade": "Série já caracterizada como utilizável: A_pot := A_utilizável e a = 1",
}


@dataclass(frozen=True)
class PotencialRenovavel:
    uid: UIDRecurso
    tecnologia: str
    potencial: SerieTemporal                 # A^pot_{r,t} [kW barramento]
    base_potencial: str                      # chave de BASES_POTENCIAL (sem padrão)
    disponibilidade: Disponibilidade         # a_{r,t}
    custo_curtailment: Parametro | None = None   # c^curt_{r} [R$/kWh]; exigido só se o termo estiver no objetivo


# =============================================================================== armazenamento
HIPOTESES_AUTODESCARGA = {
    "nao_modelada_alpha_1": "Autodescarga não modelada: hipótese declarada α_b = 1 (M07)",
    "lambda_declarado": "Autodescarga λ_b [1/h] declarada: α_b = exp(−λ_b h)",
}


@dataclass(frozen=True)
class EspecBateria:
    uid: UIDRecurso
    capacidade_kWh: Parametro            # C_b
    soc_min: Parametro                   # s_min [1]
    soc_max: Parametro                   # s_max [1]
    eta_carga: Parametro                 # η^c barramento → energia interna
    eta_descarga: Parametro              # η^d energia interna → barramento
    p_carga_max_kW: Parametro            # P̄^c [kW barramento]
    p_descarga_max_kW: Parametro         # P̄^d [kW barramento]
    hipotese_autodescarga: str           # chave de HIPOTESES_AUTODESCARGA (sem padrão)
    disponibilidade: Disponibilidade     # a_{b,t}
    autodescarga_1_h: Parametro | None = None   # λ_b; só com "lambda_declarado"
    custo_throughput: Parametro | None = None   # c^thr_b [R$/kWh] — declarável; termo do objetivo é FUTURO (3B)


@dataclass(frozen=True)
class EstadoBateria:
    uid: UIDRecurso
    energia_kWh: Parametro               # e_b^0 (estado inicial medido/declarado)
    soc: Parametro | None = None         # opcional; se presente deve ser coerente com e_b^0 / C_b


# =============================================================================== geração controlável
TECNOLOGIAS_GERADOR = {"pemfc": "Célula a combustível PEM", "termica": "Térmica"}
CLASSIFICACOES_CURVA = {
    "sintetica_exata": "PWL sintética de solução analítica conhecida (permitida para 3A/3B)",
    "real": "Curva derivada de modelo/equipamento real — exige certificação estática (adenda B04) antes de uso",
}
VARIANTES_COMMITMENT = {
    "instantanea": "OFF/ON instantâneo (M09–M12; adenda B05 variante INSTANTÂNEA)",
    "multimodo": "Autômato multimodo (M20/M20b/M20c; adenda B05) — NÃO suportado no Piso 3A",
}


@dataclass(frozen=True)
class CurvaPWL:
    """Vértices consecutivos (P [kW barramento líquido], Q [kg/h H2 SUPRIDO]) — M14–M16."""
    vertices: tuple[tuple[float, float], ...]
    classificacao: str
    procedencia: Procedencia | None


@dataclass(frozen=True)
class EspecGerador:
    uid: UIDRecurso
    tecnologia: str
    p_min_kW: Parametro
    p_max_kW: Parametro
    disponibilidade: Disponibilidade
    variante_commitment: str
    curva_h2: CurvaPWL | None = None


@dataclass(frozen=True)
class EstadoGerador:
    """Estado discreto e potência ANTERIORES à janela (u_i^{-1}, p_i^{-1}); nunca inferidos da potência."""
    uid: UIDRecurso
    ligado: bool | None
    p_anterior_kW: Parametro


# =============================================================================== políticas
MODOS_SERVICO = {"duro": "Serviço duro: ℓ = 0 para toda carga (déficit ⇒ inviável)",
                 "degradado": "Serviço degradado: 0 <= ℓ <= χL só com autorização explícita"}


@dataclass(frozen=True)
class DispositivoDescarte:
    uid: UIDRecurso
    p_max_kW: Parametro                  # D̄ — só com existência física declarada


@dataclass(frozen=True)
class PoliticaServico:
    modo: str
    procedencia: Procedencia | None
    autorizacao_interrupcao: str = ""
    descarte: DispositivoDescarte | None = None   # None ⇒ D̄ = 0 (sem sumidouro físico; decisão D03)


TIPOS_TERMINAL = {
    "nenhuma": "Sem termo terminal — só para casos analíticos ou ablação rotulada",
    "referencia_suave": "Referência suave de energia (κ, ξ) — FUTURO",
    "minimo_duro": "Mínimo terminal duro — FUTURO",
}


@dataclass(frozen=True)
class PoliticaTerminal:
    tipo: str
    justificativa: str
    procedencia: Procedencia | None


TERMOS_OBJETIVO = {
    "curtailment_operacional": ("implementado_3A", "h Σ c^curt C^oper (M21-v1.1, B01)"),
    "geracao_termica": ("futuro", "Ċ_g (M19)"),
    "combustivel_h2": ("futuro", "c_H m (B05: variante instantânea ou multimodo)"),
    "throughput_bess": ("futuro", "c^thr (P^c + P^d)"),
    "energia_nao_suprida": ("futuro", "V_ℓ ℓ"),
    "descarte": ("futuro", "c^dump d"),
    "eventos": ("futuro", "C^SU y + C^SD z / custos de modo"),
    "terminal": ("futuro", "κ ξ"),
    "regularizador_rampa": ("futuro", "γ v"),
}
TERMOS_PROIBIDOS = {"indisponibilidade_como_curtailment": "Indisponibilidade não é vertimento (adenda B01)"}


@dataclass(frozen=True)
class PoliticaObjetivo:
    termos: tuple[str, ...]
    procedencia: Procedencia | None
    variante_combustivel: str | None = None
    lexicografica: bool = False


# =============================================================================== entrada canônica
@dataclass(frozen=True)
class EntradaModeloEMS:
    versao_esquema: int
    motor_id: str
    versao_formulacao: str
    microrrede_uid: str
    cenario_uid: str
    malha: MalhaTemporal
    fronteira: FronteiraBarramento
    demandas: tuple[ClasseDemanda, ...]
    renovaveis: tuple[PotencialRenovavel, ...]
    baterias: tuple[EspecBateria, ...]
    estados_baterias: tuple[EstadoBateria, ...]
    geradores: tuple[EspecGerador, ...]
    estados_geradores: tuple[EstadoGerador, ...]
    politica_servico: PoliticaServico
    politica_terminal: PoliticaTerminal
    politica_objetivo: PoliticaObjetivo
    procedencia: Procedencia | None
    hashes_fontes: dict[str, str] = field(default_factory=dict)


# =============================================================================== validação
def _disp(d: Disponibilidade, malha: MalhaTemporal, cam: str) -> tuple[tuple[float, ...] | None, list[Constatacao]]:
    out = validar_serie(d.serie, cam, unidade="1", grandeza="disponibilidade")
    if out:
        return None, out
    vals, c = alinhar_a_malha(d.serie, malha, cam)
    out += c
    if vals is not None:
        frac = [i for i, v in enumerate(vals) if v not in (0.0, 1.0)]
        if frac:
            out.append(pendente("disponibilidade_fracionaria_nao_suportada", cam,
                                f"a ∉ {{0, 1}} nos intervalos {frac[:8]}: derating fracionário exige caracterização "
                                "e contrato próprio (adenda B01)."))
    return vals, out


def _serie_potencia(s: SerieTemporal, malha: MalhaTemporal, cam: str) -> tuple[tuple[float, ...] | None, list[Constatacao]]:
    out = validar_serie(s, cam, unidade="kW", grandeza="potencia")
    if any(c.severidade == "erro" for c in out):
        return None, out
    vals, c = alinhar_a_malha(s, malha, cam)
    out += c
    if vals is not None:
        neg = [i for i, v in enumerate(vals) if v < 0]
        if neg:
            out.append(erro("quantidade_negativa", cam, f"Potência negativa nos intervalos {neg[:8]}."))
    return vals, out


def validar_demanda(d: ClasseDemanda, malha: MalhaTemporal, servico: PoliticaServico, cam: str) -> list[Constatacao]:
    out = validar_uid(d.uid, cam + ".uid")
    if d.criticidade not in CRITICIDADES:
        out.append(erro("criticidade_invalida", cam + ".criticidade", f"Criticidade {d.criticidade!r}."))
    out += _serie_potencia(d.potencia, malha, cam + ".potencia")[1]
    if d.fracao_interrompivel is not None:
        out += validar_serie(d.fracao_interrompivel, cam + ".fracao_interrompivel", unidade="1",
                             grandeza="fracao_interrompivel")
        chi, c = alinhar_a_malha(d.fracao_interrompivel, malha, cam + ".fracao_interrompivel")
        out += c
        if chi is not None:
            if any(not 0 <= v <= 1 for v in chi):
                out.append(erro("fracao_fora_do_dominio", cam + ".fracao_interrompivel", "χ exige [0, 1]."))
            if d.criticidade == "critica" and any(v > 0 for v in chi):
                out.append(erro("carga_critica_com_interrupcao", cam + ".fracao_interrompivel",
                                "Carga crítica não admite χ > 0 (interrupção sem permissão)."))
            if d.criticidade == "interrompivel" and servico.modo == "duro" and any(v > 0 for v in chi):
                out.append(aviso("interrupcao_ignorada_em_servico_duro", cam,
                                 "Serviço duro: χ efetivo = 0 para esta classe."))
    elif d.criticidade == "interrompivel":
        out.append(erro("fracao_interrompivel_ausente", cam + ".fracao_interrompivel",
                        "Carga interrompível sem χ declarado."))
    return out


def validar_renovavel(r: PotencialRenovavel, malha: MalhaTemporal, objetivo: PoliticaObjetivo, cam: str) -> list[Constatacao]:
    out = validar_uid(r.uid, cam + ".uid")
    if r.tecnologia not in TECNOLOGIAS_RENOVAVEIS:
        out.append(erro("tecnologia_invalida", cam + ".tecnologia", f"Tecnologia {r.tecnologia!r}."))
    if r.base_potencial not in BASES_POTENCIAL:
        out.append(erro("base_potencial_nao_declarada", cam + ".base_potencial",
                        "Declarar se A_pot é anterior à disponibilidade ou já utilizável."))
    out += _serie_potencia(r.potencial, malha, cam + ".potencial")[1]
    a, c = _disp(r.disponibilidade, malha, cam + ".disponibilidade")
    out += c
    if r.base_potencial == "utilizavel_apos_disponibilidade" and a is not None and any(v != 1.0 for v in a):
        out.append(erro("disponibilidade_aplicada_duas_vezes", cam + ".disponibilidade",
                        "Potencial já utilizável exige a = 1 (não multiplicar duas vezes)."))
    if "curtailment_operacional" in objetivo.termos or r.custo_curtailment is not None:
        out += validar_parametro(r.custo_curtailment, cam + ".custo_curtailment", unidade="R$/kWh",
                                 dominio="nao_negativo")
    return out


def validar_bateria(b: EspecBateria, malha: MalhaTemporal, cam: str) -> list[Constatacao]:
    out = validar_uid(b.uid, cam + ".uid")
    out += validar_parametro(b.capacidade_kWh, cam + ".capacidade_kWh", unidade="kWh", dominio="positivo")
    out += validar_parametro(b.soc_min, cam + ".soc_min", unidade="1", dominio="fracao")
    out += validar_parametro(b.soc_max, cam + ".soc_max", unidade="1", dominio="fracao")
    out += validar_parametro(b.eta_carga, cam + ".eta_carga", unidade="1", dominio="eficiencia")
    out += validar_parametro(b.eta_descarga, cam + ".eta_descarga", unidade="1", dominio="eficiencia")
    out += validar_parametro(b.p_carga_max_kW, cam + ".p_carga_max_kW", unidade="kW", dominio="positivo")
    out += validar_parametro(b.p_descarga_max_kW, cam + ".p_descarga_max_kW", unidade="kW", dominio="positivo")
    if b.hipotese_autodescarga not in HIPOTESES_AUTODESCARGA:
        out.append(erro("hipotese_autodescarga_nao_declarada", cam + ".hipotese_autodescarga",
                        "Declarar 'nao_modelada_alpha_1' ou 'lambda_declarado' (sem padrão implícito)."))
    elif b.hipotese_autodescarga == "lambda_declarado":
        out += validar_parametro(b.autodescarga_1_h, cam + ".autodescarga_1_h", unidade="1/h", dominio="nao_negativo")
    elif b.autodescarga_1_h is not None:
        out.append(erro("autodescarga_contraditoria", cam + ".autodescarga_1_h",
                        "λ declarado com hipótese 'não modelada'."))
    if b.custo_throughput is not None:
        out += validar_parametro(b.custo_throughput, cam + ".custo_throughput", unidade="R$/kWh", dominio="nao_negativo")
    smin, smax = (b.soc_min.valor if b.soc_min else None), (b.soc_max.valor if b.soc_max else None)
    if isinstance(smin, (int, float)) and isinstance(smax, (int, float)) and math.isfinite(smin) and math.isfinite(smax) \
            and not smin < smax:
        out.append(erro("limites_soc_incoerentes", cam, f"Exigido s_min < s_max; recebido {smin} >= {smax}."))
    out += _disp(b.disponibilidade, malha, cam + ".disponibilidade")[1]
    return out


def validar_estado_bateria(e: EstadoBateria, b: EspecBateria, cam: str) -> list[Constatacao]:
    out = validar_parametro(e.energia_kWh, cam + ".energia_kWh", unidade="kWh", dominio="nao_negativo")
    if e.soc is not None:
        if e.soc.unidade == "%":
            out.append(erro("soc_em_percentual_sem_conversao", cam + ".soc",
                            "SOC em % exige conversão explícita para fração (Parametro.de_bruto)."))
        else:
            out += validar_parametro(e.soc, cam + ".soc", unidade="1", dominio="fracao")
    if out:
        return out
    try:
        C, smin, smax, e0 = (float(b.capacidade_kWh.valor), float(b.soc_min.valor), float(b.soc_max.valor),
                             float(e.energia_kWh.valor))
    except (TypeError, AttributeError):
        return out   # constatações da especificação já registradas
    if not (math.isfinite(C) and C > 0 and math.isfinite(smin) and math.isfinite(smax)):
        return out   # especificação inválida: já rejeitada por validar_bateria (sem divisão por C)
    if e0 > C:
        out.append(erro("energia_maior_que_capacidade", cam + ".energia_kWh", f"e0 = {e0} kWh > C = {C} kWh."))
    if not (C * smin <= e0 <= C * smax):
        out.append(erro("soc_inicial_fora_dos_limites", cam + ".energia_kWh",
                        f"e0/C = {e0 / C} fora de [{smin}, {smax}] (sem recorte)."))
    if e.soc is not None and abs(float(e.soc.valor) * C - e0) > 1e-9 * max(1.0, C):
        out.append(erro("soc_e_energia_inconsistentes", cam + ".soc",
                        f"SOC × C = {float(e.soc.valor) * C} kWh ≠ e0 = {e0} kWh."))
    return out


def validar_curva(cv: CurvaPWL, pmin: float | None, pmax: float | None, cam: str) -> list[Constatacao]:
    out: list[Constatacao] = []
    if cv.classificacao not in CLASSIFICACOES_CURVA:
        out.append(erro("classificacao_curva_invalida", cam + ".classificacao", f"{cv.classificacao!r}."))
    elif cv.classificacao == "real":
        out.append(pendente("pwl_real_requer_certificacao_estatica", cam,
                            "Curva real q(P_net) exige validação estática aprovada (adenda B04) antes de uso."))
    out += validar_procedencia(cv.procedencia, cam + ".procedencia")
    vs = cv.vertices
    if not isinstance(vs, tuple) or len(vs) < 2:
        return out + [erro("curva_insuficiente", cam + ".vertices", "Exigidos >= 2 vértices.")]
    try:
        P = [float(v[0]) for v in vs]
        Q = [float(v[1]) for v in vs]
    except (TypeError, ValueError, IndexError):
        return out + [erro("curva_invalida", cam + ".vertices", "Vértices devem ser pares (P, Q).")]
    if not all(math.isfinite(x) for x in P + Q):
        return out + [erro("valor_nao_finito", cam + ".vertices", "Vértice NaN/Inf.")]
    if any(b <= a for a, b in zip(P, P[1:])):
        out.append(erro("curva_nao_crescente", cam + ".vertices", "P deve ser estritamente crescente."))
    if P[0] <= 0:
        out.append(erro("curva_inclui_zero", cam + ".vertices",
                        "O primeiro vértice deve ter P > 0: não se interpola entre (0, 0) e P_min (M14–M16)."))
    if any(q < 0 for q in Q):
        out.append(erro("quantidade_negativa", cam + ".vertices", "Vazão negativa."))
    if pmin is not None and P[0] < pmin:
        out.append(erro("curva_abaixo_do_minimo", cam + ".vertices", f"P_0 = {P[0]} < P_min = {pmin}."))
    if pmax is not None and P[-1] > pmax:
        out.append(erro("curva_acima_do_maximo", cam + ".vertices", f"P_último = {P[-1]} > P_max = {pmax}."))
    return out


def validar_gerador(g: EspecGerador, malha: MalhaTemporal, cam: str) -> list[Constatacao]:
    out = validar_uid(g.uid, cam + ".uid")
    if g.tecnologia not in TECNOLOGIAS_GERADOR:
        out.append(erro("tecnologia_invalida", cam + ".tecnologia", f"{g.tecnologia!r}."))
    c1 = validar_parametro(g.p_min_kW, cam + ".p_min_kW", unidade="kW", dominio="nao_negativo")
    c2 = validar_parametro(g.p_max_kW, cam + ".p_max_kW", unidade="kW", dominio="positivo")
    out += c1 + c2
    pmin = None if c1 else float(g.p_min_kW.valor)
    pmax = None if c2 else float(g.p_max_kW.valor)
    if pmin is not None and pmax is not None and pmin > pmax:
        out.append(erro("limites_potencia_incoerentes", cam, f"P_min {pmin} > P_max {pmax}."))
    if g.variante_commitment not in VARIANTES_COMMITMENT:
        out.append(erro("variante_commitment_invalida", cam + ".variante_commitment", f"{g.variante_commitment!r}."))
    elif g.variante_commitment == "multimodo":
        out.append(pendente("multimodo_nao_suportado_3A", cam + ".variante_commitment",
                            "Autômato multimodo (M20) não é construído no Piso 3A."))
    if g.curva_h2 is not None:
        out += validar_curva(g.curva_h2, pmin, pmax, cam + ".curva_h2")
    elif g.tecnologia == "pemfc":
        out.append(pendente("curva_h2_ausente", cam + ".curva_h2",
                            "PEMFC sem curva q(P_net) — perfil V–I importado não basta (adenda B04)."))
    out += _disp(g.disponibilidade, malha, cam + ".disponibilidade")[1]
    return out


def validar_estado_gerador(e: EstadoGerador, g: EspecGerador, cam: str) -> list[Constatacao]:
    out: list[Constatacao] = []
    if not isinstance(e.ligado, bool):
        out.append(erro("estado_inicial_ausente", cam + ".ligado",
                        "Estado ON/OFF anterior não declarado: não é inferido da potência."))
    out += validar_parametro(e.p_anterior_kW, cam + ".p_anterior_kW", unidade="kW", dominio="nao_negativo")
    if out:
        return out
    p = float(e.p_anterior_kW.valor)
    try:
        pmin, pmax = float(g.p_min_kW.valor), float(g.p_max_kW.valor)
    except (TypeError, AttributeError):
        return out
    if not e.ligado and p != 0.0:
        out.append(erro("off_com_potencia", cam, f"OFF implica potência anterior 0; recebido {p} kW."))
    if e.ligado and not pmin <= p <= pmax:
        out.append(erro("on_fora_do_dominio", cam, f"ON exige P_min <= p <= P_max; recebido {p} kW."))
    return out


def validar_politicas(e: EntradaModeloEMS) -> list[Constatacao]:
    out: list[Constatacao] = []
    s, t, o = e.politica_servico, e.politica_terminal, e.politica_objetivo
    if s.modo not in MODOS_SERVICO:
        out.append(erro("modo_servico_invalido", "politica_servico.modo", f"{s.modo!r}."))
    out += validar_procedencia(s.procedencia, "politica_servico.procedencia")
    if s.modo == "degradado":
        if not s.autorizacao_interrupcao.strip():
            out.append(erro("interrupcao_sem_autorizacao", "politica_servico.autorizacao_interrupcao",
                            "Serviço degradado exige autorização explícita de interrupção."))
        if not any(d.criticidade == "interrompivel" for d in e.demandas):
            out.append(erro("degradado_sem_carga_interrompivel", "politica_servico",
                            "Serviço degradado sem classe interrompível declarada."))
    if s.descarte is not None:
        out += validar_uid(s.descarte.uid, "politica_servico.descarte.uid")
        out += validar_parametro(s.descarte.p_max_kW, "politica_servico.descarte.p_max_kW", unidade="kW",
                                 dominio="positivo")
    if t.tipo not in TIPOS_TERMINAL:
        out.append(erro("politica_terminal_invalida", "politica_terminal.tipo", f"{t.tipo!r}."))
    elif t.tipo != "nenhuma":
        out.append(pendente("politica_terminal_nao_suportada_3A", "politica_terminal.tipo",
                            "Referência suave/mínimo duro exigem E_ref/κ aprovados (D02) e o Piso 3B."))
    elif not t.justificativa.strip():
        out.append(erro("terminal_nenhuma_sem_justificativa", "politica_terminal.justificativa",
                        "'nenhuma' só é aceita com justificativa explícita (caso analítico/ablação rotulada)."))
    out += validar_procedencia(t.procedencia, "politica_terminal.procedencia")
    out += validar_procedencia(o.procedencia, "politica_objetivo.procedencia")
    for termo in o.termos:
        if termo in TERMOS_PROIBIDOS:
            out.append(erro("termo_objetivo_proibido", f"politica_objetivo.termos[{termo}]", TERMOS_PROIBIDOS[termo]))
        elif termo not in TERMOS_OBJETIVO:
            out.append(erro("termo_objetivo_desconhecido", f"politica_objetivo.termos[{termo}]", f"{termo!r}."))
        elif TERMOS_OBJETIVO[termo][0] != "implementado_3A":
            out.append(pendente("termo_objetivo_nao_suportado_3A", f"politica_objetivo.termos[{termo}]",
                                f"{termo}: {TERMOS_OBJETIVO[termo][1]} — previsto para piso posterior."))
    if len(set(o.termos)) != len(o.termos):
        out.append(erro("termo_objetivo_duplicado", "politica_objetivo.termos", "Termo repetido."))
    if o.lexicografica:
        out.append(pendente("lexicografica_nao_suportada_3A", "politica_objetivo.lexicografica", "M22 é futuro."))
    if o.variante_combustivel is not None:
        out.append(pendente("variante_combustivel_nao_suportada_3A", "politica_objetivo.variante_combustivel",
                            "Custo de combustível (B05) é futuro."))
    return out


def validar_entrada(e: EntradaModeloEMS) -> RelatorioValidacao:
    out: list[Constatacao] = []
    if e.versao_esquema != ESQUEMA_VERSAO:
        out.append(erro("versao_esquema_incompativel", "versao_esquema", f"{e.versao_esquema!r} ≠ {ESQUEMA_VERSAO}."))
    if e.motor_id != MOTOR_ID:
        out.append(erro("motor_incompativel", "motor_id", f"{e.motor_id!r}: este contrato é de {MOTOR_ID}."))
    if e.versao_formulacao != FORMULACAO_VERSAO:
        out.append(erro("formulacao_incompativel", "versao_formulacao", f"{e.versao_formulacao!r}."))
    for nome in ("microrrede_uid", "cenario_uid"):
        if not isinstance(getattr(e, nome), str) or not getattr(e, nome).strip():
            out.append(erro("identidade_ausente", nome, "Identidade de origem ausente."))
    out += validar_procedencia(e.procedencia, "procedencia")
    for k, v in (e.hashes_fontes or {}).items():
        if not _HEX64.fullmatch(str(v)):
            out.append(erro("hash_fonte_invalido", f"hashes_fontes[{k}]", "SHA-256 inválido."))
    mc = validar_malha(e.malha)
    out += mc
    if any(c.severidade == "erro" for c in mc):
        return RelatorioValidacao(tuple(out))
    f = e.fronteira
    if f.tipo not in TIPOS_FRONTEIRA:
        out.append(erro("fronteira_nao_suportada", "fronteira.tipo", f"{f.tipo!r}."))
    if f.topologia not in TOPOLOGIAS:
        out.append(pendente("topologia_nao_suportada_3A", "fronteira.topologia",
                            f"{f.topologia!r}: só microrrede isolada no Piso 3A."))
    if f.convencao_potencia != CONVENCAO_POTENCIA:
        out.append(erro("fronteira_incerta", "fronteira.convencao_potencia",
                        f"Convenção {f.convencao_potencia!r}; exigida {CONVENCAO_POTENCIA!r}."))
    out += validar_procedencia(f.procedencia, "fronteira.procedencia")
    # UIDs únicos em TODO o contrato
    uids: dict[str, str] = {}
    grupos = [("demandas", e.demandas), ("renovaveis", e.renovaveis), ("baterias", e.baterias),
              ("geradores", e.geradores)]
    if e.politica_servico.descarte is not None:
        grupos.append(("descarte", (e.politica_servico.descarte,)))
    for nome, itens in grupos:
        for i, it in enumerate(itens):
            k = str(it.uid)
            if k in uids:
                out.append(erro("uid_duplicado", f"{nome}[{i}].uid", f"UID {k} repetido (já usado em {uids[k]})."))
            else:
                uids[k] = f"{nome}[{i}]"
    for i, d in enumerate(e.demandas):
        out += validar_demanda(d, e.malha, e.politica_servico, f"demandas[{i}]")
    for i, r in enumerate(e.renovaveis):
        out += validar_renovavel(r, e.malha, e.politica_objetivo, f"renovaveis[{i}]")
    out += _validar_estados(e.baterias, e.estados_baterias, "baterias", "estados_baterias",
                            lambda b, i: validar_bateria(b, e.malha, f"baterias[{i}]"), validar_estado_bateria)
    out += _validar_estados(e.geradores, e.estados_geradores, "geradores", "estados_geradores",
                            lambda g, i: validar_gerador(g, e.malha, f"geradores[{i}]"), validar_estado_gerador)
    out += validar_politicas(e)
    return RelatorioValidacao(tuple(out))


def _validar_estados(specs, estados, nome_s, nome_e, val_spec, val_estado) -> list[Constatacao]:
    out: list[Constatacao] = []
    por_uid: dict[str, list] = {}
    for j, st in enumerate(estados):
        por_uid.setdefault(str(st.uid), []).append((j, st))
    conhecidos = {str(s.uid) for s in specs}
    for i, s in enumerate(specs):
        out += val_spec(s, i)
        lst = por_uid.get(str(s.uid), [])
        if not lst:
            out.append(erro("estado_inicial_ausente", f"{nome_e}[{s.uid}]",
                            "Estado inicial do equipamento não declarado (não se parte de zero)."))
        elif len(lst) > 1:
            out.append(erro("estado_inicial_duplicado", f"{nome_e}[{s.uid}]", "Mais de um estado inicial."))
        else:
            j, st = lst[0]
            out += val_estado(st, s, f"{nome_e}[{j}]")
    for k, lst in por_uid.items():
        if k not in conhecidos:
            out.append(erro("estado_orfao", f"{nome_e}[{lst[0][0]}]", f"Estado para UID inexistente {k}."))
    return out


# =============================================================================== serialização canônica
def para_dict(obj):
    """Serialização determinística (dataclasses → dict; tuplas → listas)."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: para_dict(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, (tuple, list)):
        return [para_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): para_dict(v) for k, v in obj.items()}
    return obj


class ErroSerializacao(ValueError):
    """Estrutura JSON incompatível com o contrato (rejeição controlada; nada é truncado nem convertido)."""


_PRIMITIVOS = {str: (str,), bool: (bool,), int: (int,), float: (int, float)}


def _construir(tipo, dado, caminho: str):
    """Reconstrução ESTRITA: tipo e comprimento exatos; nenhum elemento descartado, nenhum valor convertido.
    (C-3A-03: ``zip`` em tuplas de comprimento fixo truncava silenciosamente elementos excedentes.)"""
    origem = typing.get_origin(tipo)
    args = typing.get_args(tipo)
    if origem in (typing.Union, types.UnionType):
        if dado is None:
            if type(None) in args:
                return None
            raise ErroSerializacao(f"{caminho}: valor nulo não admitido.")
        nao_nulos = [a for a in args if a is not type(None)]
        if len(nao_nulos) != 1:
            raise ErroSerializacao(f"{caminho}: união de tipos não suportada pelo contrato ({tipo}).")
        return _construir(nao_nulos[0], dado, caminho)
    if dado is None:
        raise ErroSerializacao(f"{caminho}: valor nulo não admitido.")
    if origem is tuple:
        if not isinstance(dado, (list, tuple)):
            raise ErroSerializacao(f"{caminho}: esperada lista JSON; recebido {type(dado).__name__}.")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_construir(args[0], x, f"{caminho}[{i}]") for i, x in enumerate(dado))
        if len(dado) != len(args):
            raise ErroSerializacao(f"{caminho}: esperados exatamente {len(args)} elementos; recebidos {len(dado)}.")
        return tuple(_construir(a, x, f"{caminho}[{i}]") for i, (a, x) in enumerate(zip(args, dado)))
    if origem is dict:
        if not isinstance(dado, dict):
            raise ErroSerializacao(f"{caminho}: esperado objeto JSON; recebido {type(dado).__name__}.")
        return {_construir(args[0], k, f"{caminho}.<chave>"): _construir(args[1], v, f"{caminho}[{k}]")
                for k, v in dado.items()}
    if isinstance(tipo, type) and is_dataclass(tipo):
        return de_dict(tipo, dado, caminho)
    if tipo in _PRIMITIVOS:
        aceitos = _PRIMITIVOS[tipo]
        if isinstance(dado, bool) and tipo is not bool or not isinstance(dado, aceitos):
            raise ErroSerializacao(f"{caminho}: esperado {tipo.__name__}; recebido {type(dado).__name__} ({dado!r}).")
        if isinstance(dado, float) and not math.isfinite(dado):
            raise ErroSerializacao(f"{caminho}: valor não finito.")
        return dado
    raise ErroSerializacao(f"{caminho}: tipo de contrato não suportado na desserialização ({tipo}).")


def de_dict(cls, dado: dict, caminho: str | None = None):
    """Reconstrói um dataclass do contrato a partir de ``para_dict`` (sem ``eval``/``pickle``), de forma estrita."""
    caminho = caminho or cls.__name__
    if not isinstance(dado, dict):
        raise ErroSerializacao(f"{caminho}: esperado objeto JSON ({cls.__name__}).")
    dicas = typing.get_type_hints(cls)
    campos = {f.name: f for f in fields(cls)}
    desconhecidos = set(dado) - set(campos)
    if desconhecidos:
        raise ErroSerializacao(f"{caminho}: campos desconhecidos {sorted(desconhecidos)}.")
    faltando = [n for n, f in campos.items() if n not in dado and f.default is MISSING and f.default_factory is MISSING]
    if faltando:
        raise ErroSerializacao(f"{caminho}: campos obrigatórios ausentes {faltando}.")
    return cls(**{k: _construir(dicas[k], v, f"{caminho}.{k}") for k, v in dado.items()})


def json_canonico(e: EntradaModeloEMS) -> str:
    return json.dumps(para_dict(e), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def hash_entrada(e: EntradaModeloEMS) -> str:
    """SHA-256 do JSON canônico (NaN/Inf proibidos: ``allow_nan=False`` levanta ``ValueError``)."""
    return hashlib.sha256(json_canonico(e).encode("utf-8")).hexdigest()


def _constante_proibida(nome: str):
    raise ErroSerializacao(f"Constante JSON não padrão proibida: {nome} (NaN/Infinity nunca são dados válidos).")


def entrada_de_json(texto: str) -> EntradaModeloEMS:
    """JSON estrito → contrato. Para toda entrada aceita, ``json_canonico(entrada_de_json(s))`` reemite os mesmos
    valores (sem truncamento nem conversão)."""
    try:
        dado = json.loads(texto, parse_constant=_constante_proibida)
    except json.JSONDecodeError as exc:
        raise ErroSerializacao(f"JSON inválido: {exc}") from None
    return de_dict(EntradaModeloEMS, dado, "EntradaModeloEMS")


# =============================================================================== aliases (nomes da ordem executiva)
ResourceUID = UIDRecurso
SourceProvenance = Procedencia
BusBoundary = FronteiraBarramento
Availability = Disponibilidade
DemandClass = ClasseDemanda
RenewablePotential = PotencialRenovavel
BatterySpec, BatteryState = EspecBateria, EstadoBateria
GeneratorSpec, GeneratorState = EspecGerador, EstadoGerador
ServicePolicy, TerminalPolicy, ObjectivePolicy = PoliticaServico, PoliticaTerminal, PoliticaObjetivo
EMSModelInput = EntradaModeloEMS
TimeGrid = MalhaTemporal

__all__ = [n for n in dir() if not n.startswith("_") and n not in {
    "annotations", "MISSING", "dataclass", "field", "fields", "is_dataclass", "hashlib", "json", "math", "re", "types", "typing"}]
_ = Transformacao  # reexportado para consumidores do contrato
