"""Estratégia EMS V2 do cenário (Piso 3D-A): seleção EXPLÍCITA do motor e bloco declarativo ``milp_mpc``.

Duas chaves OPCIONAIS do documento do cenário (``seeds2-scenario`` v1; documentos anteriores não as têm e conservam a
impressão digital):

* ``engine`` — ``"legacy_v16"`` (ou ausente) × ``"milp_mpc_v1"``: qual motor executa as rodadas DESTE cenário;
* ``milp_mpc`` — bloco versionado (``format_version`` 1) com TUDO o que o EMS hierárquico exige e o inventário do Piso 1
  não tem. Fica na versão IMUTÁVEL do cenário: cada rodada referencia a declaração exata que usou.

Regra central (sem valor padrão científico): parâmetros físicos, econômicos e de política começam VAZIOS (``None``) e
só valem quando DECLARADOS com procedência (``tipo`` + ``fonte``). Um bloco incompleto é gravável (o cenário continua
editável), mas o preflight V2 BLOQUEIA a execução listando cada campo ausente. Só os parâmetros NUMÉRICOS de software
do planejador/solver têm valores iniciais — os dos ensaios 3C-4 auditados (``REFERENCIA_NUMERICA``), rotulados como tal.

Estrutura (``novo_bloco``)::

    {"format_version": 2, "contexto": "ensaio",
     "declarante": {"tipo", "fonte"},                       # quem declara políticas e montagem
     "malha": {"delta_min", "N", "m", "H_L"},               # Δ [min]; horizonte curto, bloco aplicado, horizonte longo
     "demanda": {"nome", "criticidade", "semantica", "emissao_utc"},
     "clima": {"semantica", "emissao_utc"},                 # formato 2 (3D-A2-R): previsão climática do cenário
     "renovaveis": {<eq-… usina FV>: {"tecnologia": "fv", "eta_conversao_barramento", "custo_curtailment_R_kWh",
                                      "procedencia"},
                    <eq-… eólica>: {"tecnologia": "eolica", "hipotese_densidade", "custo_curtailment_R_kWh",
                                    "procedencia"}},
     "realizacao": {"tipo", "demanda_kW", "procedencia"},   # realização SIMULADA posterior (nunca entregue ao controlador)
     "baterias": {<eq-…>: {"eta_carga", "eta_descarga", "p_carga_barramento_kW", "p_descarga_barramento_kW",
                           "hipotese_autodescarga", "custo_throughput_R_kWh", "procedencia"}},
     "pcc": {"modo", "sentidos", "limite_importacao_kW", "limite_exportacao_kW", "disponibilidade",
             "tarifa_importacao_R_kWh", "tarifa_exportacao_R_kWh", "remuneracao_exportacao", "tarifa_emissao_utc",
             "tarifa_liquidacao", "ajuste", "rotulo_tarifa", "justificativa", "procedencia"},
     "objetivo": {"termos": [...]},
     "planejador": {"tipo_sinal", "politica_atualizacao", "periodo_janelas", "pontos_iniciais", "pontos_max",
                    "tolerancia_interpolacao_R", "tolerancia_dominio_kWh", "delta_sensibilidade_kWh",
                    "penalidade_branda_R_kWh", "max_modos", "degradacao",
                    "termo_longo": {"tipo", "valores", "justificativa"}, "justificativa"},
     "solver": {"time_limit_s", "threads", "rel_gap", "abs_gap", "semente"}}

Só biblioteca padrão + vocabulários do núcleo ``ems_v2`` (que também só usa a biblioteca padrão): importar este módulo
não carrega Pyomo/HiGHS, Streamlit, numpy nem ``seeds2``.
"""
from __future__ import annotations

import copy
import math
from typing import Any

from ems_v2 import MOTOR_ID
from ems_v2.hierarquia.contrato import DEGRADACOES, POLITICAS_ATUALIZACAO, TERMOS_DECLARADOS, TIPOS_SINAL
from ems_v2.provenance import TIPOS_PROCEDENCIA
from ems_v2.rede.contrato import MODOS_CONEXAO, REMUNERACOES_EXPORTACAO, SENTIDOS
from ems_v2.rede.execucao import TIPOS_AJUSTE
from ems_v2.timegrid import ler_instante_utc

FORMATO = 3                                           # 3 = 3D-A2-H (PEMFC); 2 = 3D-A2-R (clima + renováveis); 1 = 3D-A
FORMATOS_LEGIVEIS = (1, 2, 3)
MOTOR_V16 = "legacy_v16"
MOTOR_V2 = MOTOR_ID                                   # "milp_mpc_v1"
CHAVE_MOTOR, CHAVE_BLOCO = "engine", "milp_mpc"
MOTORES = {
    MOTOR_V16: "EMS V1.6 — despacho com metaheurística + refino SQP (motor operacional)",
    MOTOR_V2: "EMS V2 EXPERIMENTAL — MILP–MPC hierárquico (Pyomo + HiGHS; simulação offline de ensaio)",
}
CONTEXTOS = {"ensaio": "Ensaio: simulação OFFLINE contra planta algébrica; dados sintéticos permitidos e ROTULADOS"}
CONTEXTO_NAO_SUPORTADO = ("O Piso 3D-A executa apenas simulações offline de ENSAIO: não existe fonte de realização medida "
                          "nem operação online; o contexto 'operacional' da ponte 3C-0 exige ambos.")
TIPOS_DECLARAVEIS = {k: v for k, v in TIPOS_PROCEDENCIA.items() if k != "nao_declarado"}
CRITICIDADES = {"critica": "Crítica — sem interrupção (serviço duro; déficit ⇒ inviável, nunca ENS inventada)"}
SEMANTICAS = {"media_intervalo": "Cada valor é a MÉDIA do intervalo [t, t + Δ) que começa no seu instante"}
REALIZACOES = {
    "igual_a_previsao": "Realização simulada = valores da previsão declarada (simulação SEM erro de previsão; o "
                        "controlador continua recebendo só a previsão)",
    "serie_declarada": "Realização simulada declarada intervalo a intervalo (lista de kW, um valor por intervalo da "
                       "missão)",
}
HIPOTESES_AUTODESCARGA = {"nao_modelada_alpha_1": "Autodescarga NÃO modelada: hipótese declarada α = 1"}
DISPONIBILIDADES_PCC = {"disponivel_em_toda_a_missao": "PCC disponível (a = 1) em todos os intervalos — DECLARADO"}
LIQUIDACOES = {"igual_a_tarifa_declarada": "Liquidação da energia MEDIDA pela MESMA tarifa declarada (contratual "
                                            "conhecida)"}
TERMOS_BASE = {"throughput_bess": "Custo de throughput das baterias: c_thr (P_c + P_d) h",
               "curtailment_operacional": "Custo de vertimento operacional das renováveis: c_curt (a·A − P_R) h "
                                          "(exige c_curt DECLARADO por recurso renovável)"}
# ---- Piso 3D-A2-R: clima previsto e recursos renováveis (vocabulários também usados por ``renovaveis``)
SEMANTICAS_CLIMA = {
    "media_intervalo": "Cada amostra climática é a MÉDIA de [t, t + passo): o modelo é aplicado à média do clima de cada "
                       "subpasso (função não linear ⇒ P(média) ≠ média de P: aproximação DECLARADA)",
    "amostra_instantanea": "Cada amostra climática é INSTANTÂNEA em t: a média do intervalo é aproximada pela média das "
                           "potências nas subamostras (retângulo à esquerda; aproximação DECLARADA)",
}
HIPOTESES_DENSIDADE = {
    "calculada_do_clima_previsto": "ρ calculada pelo modelo eólico a partir de temperatura e pressão previstas (e umidade, "
                                   "quando prevista); qualquer amostra que recaísse no ar de referência BLOQUEIA",
    "referencia_do_catalogo": "ρ de referência da curva do catálogo (ar padrão) em todas as amostras — hipótese DECLARADA; "
                              "temperatura/pressão previstas NÃO são usadas",
}
TECNOLOGIAS_RENOVAVEIS = {"pv": "fv", "wind": "eolica"}       # kind do inventário → tecnologia do contrato 3A
# ---- Piso 3D-A2-H: PEMFC (curva do modelo físico; commitment 3C-1 por unidade; nada tem valor padrão)
TERMOS_BASE["combustivel_h2"] = ("Custo do H₂ SUPRIDO: c_H [R$/kg] × q(P) [kg/h] × h — q = curva do modelo físico "
                                 "(PWL certificada); obrigatório com PEMFC participante (sem preço zero presumido)")
TERMOS_BASE["eventos"] = "Custos por evento de partida/parada C_SU·y + C_SD·z [R$/evento] (commitment 3C-1)"
CONDICOES_PEMFC = {
    "temperatura_stack_K": ("Temperatura de operação do STACK", "K"),
    "pressao_anodo_kPag": ("Pressão do ânodo (manométrica)", "kPa(g)"),
    "pressao_catodo_kPag": ("Pressão do cátodo (manométrica)", "kPa(g)"),
    "pressao_ambiente_kPa": ("Pressão ambiente (absoluta)", "kPa"),
}
CAMPOS_PEMFC = {      # campo: (rótulo, unidade, domínio)
    "p_min_kW": ("Potência mínima técnica por unidade (ON)", "kW", "positivo"),
    "rampa_kW_min": ("Rampa máxima (aplicada à subida E à descida pela ponte 3C-1)", "kW/min", "positivo"),
    "t_on_min": ("Tempo mínimo em operação", "min", "nao_negativo"),
    "t_off_min": ("Tempo mínimo em repouso", "min", "nao_negativo"),
    "temperatura_ambiente_C": ("Temperatura AMBIENTE (só o modelo dinâmico: durações de partida/parada)", "°C", "real"),
    "preco_h2_R_kg": ("Preço do hidrogênio", "R$/kg", "nao_negativo"),
    "custo_partida_R": ("Custo por partida", "R$/evento", "nao_negativo"),
    "custo_parada_R": ("Custo por parada", "R$/evento", "nao_negativo"),
}
ABSTRACOES_PEMFC = {"instantanea_unidade_quente": "OFF↔ON dentro de UM intervalo (abstração DECLARADA; a partida física "
                                                  "é avaliada a posteriori pelo modelo dinâmico)",
                    "transicoes_bloqueadas": "Estado inicial mantido em toda a missão (nenhuma partida/parada)"}
LIMITES_PEMFC = {"rampa_convencional": "S⁺ := R·Δ e S⁻ := R·Δ (a ponte 3C-1 não transporta S⁺/S⁻ declarados)"}
ESTADOS_UNIDADE = {"desligada": "Desligada", "em_operacao": "Em operação"}
CAMPOS_RENOVAVEL = {
    "fv": {"eta_conversao_barramento": ("Conversão CC → barramento η (o modelo FV não representa inversor/MPPT)", "1",
                                        "eficiencia")},
    "eolica": {},
}
# Valores NUMÉRICOS de software (não físicos) usados nos ensaios 3C-4 auditados (ems_v2/fixtures_3c4.py,
# ems_v2/milp/config.CONFIG_ANALITICA). São o ponto de partida do formulário; nunca um parâmetro de equipamento.
REFERENCIA_NUMERICA = {
    "planejador": {"tipo_sinal": "custo_futuro_pwl", "politica_atualizacao": "a_cada_janela", "periodo_janelas": 1,
                   "pontos_iniciais": 5, "pontos_max": 9, "tolerancia_interpolacao_R": 1e-6,
                   "tolerancia_dominio_kWh": 0.5, "delta_sensibilidade_kWh": None, "penalidade_branda_R_kWh": None,
                   "max_modos": 4},
    "solver": {"time_limit_s": 60.0, "threads": 1, "rel_gap": 0.0, "abs_gap": 0.0, "semente": 0},
}
ROTULO_REFERENCIA = "valores numéricos de referência dos ensaios 3C-4 auditados (software; não são dados de equipamento)"
CAMPOS_BATERIA = {
    # campo do bloco: (rótulo, unidade, chave do instantâneo da ponte 3C-0, domínio)
    "eta_carga": ("Eficiência de carga (barramento → energia interna)", "1", "eta_carga", "eficiencia"),
    "eta_descarga": ("Eficiência de descarga (energia interna → barramento)", "1", "eta_descarga", "eficiencia"),
    "p_carga_barramento_kW": ("Potência máxima de carga NO BARRAMENTO", "kW", "p_carga_barramento_kW", "positivo"),
    "p_descarga_barramento_kW": ("Potência máxima de descarga NO BARRAMENTO", "kW", "p_descarga_barramento_kW",
                                 "positivo"),
    "custo_throughput_R_kWh": ("Custo de throughput", "R$/kWh", "custo_throughput", "nao_negativo"),
}
LIMITES = {"N": (1, 96), "m": (1, 96), "H_L": (2, 336), "intervalos_missao": 336}
_CHAVES = {
    "": {"format_version", "contexto", "declarante", "malha", "demanda", "realizacao", "baterias", "pcc", "objetivo",
         "planejador", "solver"},
    "declarante": {"tipo", "fonte"},
    "malha": {"delta_min", "N", "m", "H_L"},
    "demanda": {"nome", "criticidade", "semantica", "emissao_utc"},
    "realizacao": {"tipo", "demanda_kW", "procedencia"},
    "pcc": {"modo", "sentidos", "limite_importacao_kW", "limite_exportacao_kW", "disponibilidade",
            "tarifa_importacao_R_kWh", "tarifa_exportacao_R_kWh", "remuneracao_exportacao", "tarifa_emissao_utc",
            "tarifa_liquidacao", "ajuste", "rotulo_tarifa", "justificativa", "procedencia"},
    "objetivo": {"termos"},
    "planejador": {"tipo_sinal", "politica_atualizacao", "periodo_janelas", "pontos_iniciais", "pontos_max",
                   "tolerancia_interpolacao_R", "tolerancia_dominio_kWh", "delta_sensibilidade_kWh",
                   "penalidade_branda_R_kWh", "max_modos", "degradacao", "termo_longo", "justificativa"},
    "termo_longo": {"tipo", "valores", "justificativa"},
    "solver": {"time_limit_s", "threads", "rel_gap", "abs_gap", "semente"},
    "bateria": set(CAMPOS_BATERIA) | {"hipotese_autodescarga", "procedencia"},
    "clima": {"semantica", "emissao_utc"},
    "fv": {"tecnologia", "eta_conversao_barramento", "custo_curtailment_R_kWh", "procedencia"},
    "eolica": {"tecnologia", "hipotese_densidade", "custo_curtailment_R_kWh", "procedencia"},
}
_CHAVES["2"] = _CHAVES[""] | {"clima", "renovaveis"}
_CHAVES["3"] = _CHAVES["2"] | {"pemfc"}
_CHAVES["pemfc"] = {"condicoes", "abstracao", "limites_transicao", "unidades", "procedencia"} | set(CAMPOS_PEMFC)
_CHAVES["unidade_pemfc"] = {"estado", "potencia_kW", "tempo_no_estado_min"}


# ------------------------------------------------------------------------------------------------ seleção do motor
def motor_selecionado(doc: Any) -> str:
    """Motor das rodadas do cenário: ``legacy_v16`` quando a chave ``engine`` está ausente (todo cenário anterior ao
    Piso 3D-A) — nunca há troca implícita de motor."""
    v = doc.get(CHAVE_MOTOR) if isinstance(doc, dict) else None
    return MOTOR_V16 if v is None else v


def baterias_do_cenario(doc: dict) -> dict[str, dict]:
    """Bancos HABILITADOS na revisão do inventário referenciada pelo cenário (instantâneo ``inventory_ref``)."""
    eqs = ((doc.get("inventory_ref") or {}).get("equipment") or {}) if isinstance(doc, dict) else {}
    return {eid: r for eid, r in sorted(eqs.items(), key=lambda kv: kv[1].get("position", 0))
            if isinstance(r, dict) and r.get("kind") == "battery" and r.get("enabled", True)}


def renovaveis_do_cenario(doc: dict) -> dict[str, dict]:
    """Usinas FV e registros eólicos HABILITADOS na revisão do inventário referenciada pelo cenário."""
    eqs = ((doc.get("inventory_ref") or {}).get("equipment") or {}) if isinstance(doc, dict) else {}
    return {eid: r for eid, r in sorted(eqs.items(), key=lambda kv: kv[1].get("position", 0))
            if isinstance(r, dict) and r.get("kind") in TECNOLOGIAS_RENOVAVEIS and r.get("enabled", True)}


def renovaveis_participantes(doc: dict) -> dict[str, dict]:
    """Renováveis habilitadas e NÃO declaradas indisponíveis no cenário (as que exigem declarações e clima)."""
    ini = ((doc.get("initialization") or {}).get("equipment") or {}) if isinstance(doc, dict) else {}
    return {eid: r for eid, r in renovaveis_do_cenario(doc).items()
            if (ini.get(eid) or {}).get("availability") != "indisponivel"}


def pemfc_do_cenario(doc: dict) -> dict[str, dict]:
    """Registros PEMFC HABILITADOS na revisão do inventário referenciada pelo cenário."""
    eqs = ((doc.get("inventory_ref") or {}).get("equipment") or {}) if isinstance(doc, dict) else {}
    return {eid: r for eid, r in sorted(eqs.items(), key=lambda kv: kv[1].get("position", 0))
            if isinstance(r, dict) and r.get("kind") == "pemfc" and r.get("enabled", True)}


def pemfc_participantes(doc: dict) -> dict[str, dict]:
    ini = ((doc.get("initialization") or {}).get("equipment") or {}) if isinstance(doc, dict) else {}
    return {eid: r for eid, r in pemfc_do_cenario(doc).items() if (ini.get(eid) or {}).get("availability") != "indisponivel"}


def _quantidade(ref: dict) -> int:
    q = ref.get("quantity")
    return q if isinstance(q, int) and not isinstance(q, bool) and q >= 1 else 1


def _pemfc_vazia(ref: dict) -> dict:
    return {"condicoes": {k: None for k in CONDICOES_PEMFC}, **{k: None for k in CAMPOS_PEMFC}, "abstracao": None,
            "limites_transicao": None,
            "unidades": [{"estado": None, "potencia_kW": None, "tempo_no_estado_min": None} for _ in range(_quantidade(ref))],
            "procedencia": {"tipo": None, "fonte": ""}}


def _renovavel_vazia(kind: str) -> dict:
    tec = TECNOLOGIAS_RENOVAVEIS[kind]
    base = {"tecnologia": tec, "custo_curtailment_R_kWh": None, "procedencia": {"tipo": None, "fonte": ""}}
    if tec == "fv":
        base["eta_conversao_barramento"] = None
    else:
        base["hipotese_densidade"] = None
    return base


def atualizar_bloco(b: dict, doc: dict) -> dict:
    """Cópia do bloco no formato ATUAL: um bloco formato 1 (Piso 3D-A) ganha as seções ``clima`` e ``renovaveis`` VAZIAS
    (nada é preenchido); renováveis do inventário ainda sem declaração ganham uma entrada vazia."""
    n = copy.deepcopy(b)
    if n.get("format_version") == 1:
        n["clima"] = {"semantica": None, "emissao_utc": None}
        n["renovaveis"] = {}
    if n.get("format_version") in (1, 2):
        n["format_version"] = FORMATO
        n["pemfc"] = {}
    if isinstance(n.get("renovaveis"), dict):
        for eid, r in renovaveis_do_cenario(doc).items():
            n["renovaveis"].setdefault(eid, _renovavel_vazia(r["kind"]))
    if isinstance(n.get("pemfc"), dict):
        for eid, r in pemfc_do_cenario(doc).items():
            n["pemfc"].setdefault(eid, _pemfc_vazia(r))
    return n


def novo_bloco(doc: dict) -> dict:
    """Bloco inicial: campos científicos VAZIOS para os bancos do cenário; numéricos de software = referência 3C-4."""
    return {
        "format_version": FORMATO, "contexto": "ensaio",
        "clima": {"semantica": None, "emissao_utc": None},
        "renovaveis": {eid: _renovavel_vazia(r["kind"]) for eid, r in renovaveis_do_cenario(doc).items()},
        "pemfc": {eid: _pemfc_vazia(r) for eid, r in pemfc_do_cenario(doc).items()},
        "declarante": {"tipo": None, "fonte": ""},
        "malha": {"delta_min": None, "N": None, "m": None, "H_L": None},
        "demanda": {"nome": "Demanda agregada da microrrede", "criticidade": None, "semantica": None, "emissao_utc": None},
        "realizacao": {"tipo": None, "demanda_kW": None, "procedencia": {"tipo": "sintetico", "fonte": ""}},
        "baterias": {eid: {**{k: None for k in CAMPOS_BATERIA}, "hipotese_autodescarga": None,
                           "procedencia": {"tipo": None, "fonte": ""}} for eid in baterias_do_cenario(doc)},
        "pcc": {"modo": None, "sentidos": None, "limite_importacao_kW": None, "limite_exportacao_kW": None,
                "disponibilidade": None, "tarifa_importacao_R_kWh": None, "tarifa_exportacao_R_kWh": None,
                "remuneracao_exportacao": None, "tarifa_emissao_utc": None, "tarifa_liquidacao": None, "ajuste": None,
                "rotulo_tarifa": "", "justificativa": "", "procedencia": {"tipo": None, "fonte": ""}},
        "objetivo": {"termos": []},
        "planejador": {**copy.deepcopy(REFERENCIA_NUMERICA["planejador"]), "degradacao": None,
                       "termo_longo": {"tipo": None, "valores": {}, "justificativa": ""}, "justificativa": ""},
        "solver": copy.deepcopy(REFERENCIA_NUMERICA["solver"]),
    }


# ------------------------------------------------------------------------------------------------ utilidades
def _real(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _inteiro(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _lista_reais(v: Any) -> bool:
    return isinstance(v, list) and all(_real(x) for x in v)


def instante_valido(texto: Any) -> bool:
    """ISO 8601 com fuso/deslocamento EXPLÍCITO (mesma regra do contrato 3A: sem fuso = ambíguo)."""
    return isinstance(texto, str) and not ler_instante_utc(texto, "t")[1]


def _proc_erros(p: Any, cam: str, *, exigir: bool = False) -> list[str]:
    if not isinstance(p, dict) or set(p) - {"tipo", "fonte"}:
        return [f"{cam}: procedência ilegível (esperado tipo + fonte)."]
    out = []
    if p.get("tipo") is not None and p["tipo"] not in TIPOS_DECLARAVEIS:
        out.append(f"{cam}: tipo de procedência {str(p['tipo'])[:30]!r} desconhecido.")
    if not isinstance(p.get("fonte", ""), str) or len(p.get("fonte", "")) > 300:
        out.append(f"{cam}: fonte da procedência inválida (texto de até 300 caracteres).")
    if exigir and (p.get("tipo") is None or not str(p.get("fonte") or "").strip()):
        out.append(f"{cam}: procedência não declarada (tipo e fonte).")
    return out


def procedencia_declarada(p: Any) -> bool:
    return isinstance(p, dict) and p.get("tipo") in TIPOS_DECLARAVEIS and bool(str(p.get("fonte") or "").strip())


def _opcao(v: Any, vocab: dict, cam: str) -> list[str]:
    return [] if v is None or v in vocab else [f"{cam}: valor {str(v)[:40]!r} desconhecido (opções: {', '.join(vocab)})."]


def _chaves(d: Any, nome: str, cam: str) -> list[str]:
    if not isinstance(d, dict):
        return [f"{cam}: bloco ausente ou ilegível."]
    out = []
    if set(d) - _CHAVES[nome]:
        out.append(f"{cam}: campos desconhecidos {sorted(str(k)[:30] for k in set(d) - _CHAVES[nome])}.")
    if _CHAVES[nome] - set(d):
        out.append(f"{cam}: campos ausentes {sorted(_CHAVES[nome] - set(d))}.")
    return out


# ------------------------------------------------------------------------------------------------ validação estrutural
def erros_estruturais(b: Any, doc: dict | None = None) -> list[str]:
    """Estrutura, tipos, vocabulários e domínios do que FOI declarado (``None`` = ainda não declarado, gravável).
    Erro aqui impede salvar a versão do cenário; campo vazio não é erro (é pendência do preflight)."""
    p = "Estratégia MILP–MPC"
    if not isinstance(b, dict):
        return [f"{p}: bloco ilegível."]
    if b.get("format_version") not in FORMATOS_LEGIVEIS:
        return [f"{p}: formato não reconhecido."]
    out = _chaves(b, {1: "", 2: "2", 3: "3"}[b["format_version"]], p)
    if out:
        return out
    if b["format_version"] >= 3:
        out += _pemfc_erros(b["pemfc"], doc, p)
        if out:
            return out
    if b["format_version"] >= 2:
        out += _chaves(b["clima"], "clima", f"{p} · clima")
        if not out:
            out += _opcao(b["clima"]["semantica"], SEMANTICAS_CLIMA, f"{p} · clima · semântica")
            if b["clima"]["emissao_utc"] is not None and not instante_valido(b["clima"]["emissao_utc"]):
                out.append(f"{p} · clima · emissão: instante ISO 8601 com fuso explícito.")
        out += _renovaveis_erros(b["renovaveis"], doc, p)
        if out:
            return out
    for sec in ("declarante", "malha", "demanda", "realizacao", "pcc", "objetivo", "planejador", "solver"):
        out += _chaves(b[sec], sec, f"{p} · {sec}")
    if out:
        return out
    out += _opcao(b["contexto"], CONTEXTOS, f"{p} · contexto")
    if b["contexto"] is None:
        out.append(f"{p} · contexto: declare 'ensaio' (único contexto do Piso 3D-A).")
    out += _proc_erros(b["declarante"], f"{p} · declarante")
    m = b["malha"]
    if m["delta_min"] is not None and not (_inteiro(m["delta_min"]) and 1 <= m["delta_min"] <= 1440):
        out.append(f"{p} · Δ: inteiro de 1 a 1440 min.")
    for k in ("N", "m", "H_L"):
        lo, hi = LIMITES[k]
        if m[k] is not None and not (_inteiro(m[k]) and lo <= m[k] <= hi):
            out.append(f"{p} · {k}: inteiro de {lo} a {hi} intervalos.")
    d = b["demanda"]
    if not isinstance(d["nome"], str) or not d["nome"].strip() or len(d["nome"]) > 120:
        out.append(f"{p} · demanda: nome da classe obrigatório (até 120 caracteres).")
    out += _opcao(d["criticidade"], CRITICIDADES, f"{p} · demanda · criticidade")
    out += _opcao(d["semantica"], SEMANTICAS, f"{p} · demanda · semântica")
    if d["emissao_utc"] is not None and not instante_valido(d["emissao_utc"]):
        out.append(f"{p} · demanda · emissão: instante ISO 8601 com fuso explícito (p. ex. 2026-01-01T00:00:00+00:00).")
    r = b["realizacao"]
    out += _opcao(r["tipo"], REALIZACOES, f"{p} · realização")
    if r["demanda_kW"] is not None and not (_lista_reais(r["demanda_kW"]) and all(x >= 0 for x in r["demanda_kW"])
                                            and len(r["demanda_kW"]) <= LIMITES["intervalos_missao"]):
        out.append(f"{p} · realização: a série declarada deve ser uma lista de kW finitos >= 0.")
    if r["tipo"] == "igual_a_previsao" and r["demanda_kW"] is not None:
        out.append(f"{p} · realização: 'igual à previsão' não admite série declarada (ambíguo).")
    out += _proc_erros(r["procedencia"], f"{p} · realização")
    if isinstance(r["procedencia"], dict) and r["procedencia"].get("tipo") not in (None, "sintetico"):
        out.append(f"{p} · realização: a planta de ensaio é SIMULADA — a procedência da realização só pode ser "
                   "'sintetico' (nunca medida).")
    out += _baterias_erros(b["baterias"], doc, p)
    out += _pcc_erros(b["pcc"], p)
    t = b["objetivo"]["termos"]
    if not isinstance(t, list) or any(x not in TERMOS_BASE for x in t) or len(set(map(str, t))) != len(t):
        out.append(f"{p} · objetivo: termos desconhecidos ou repetidos (opções: {', '.join(TERMOS_BASE)}).")
    out += _planejador_erros(b["planejador"], p)
    out += _solver_erros(b["solver"], p)
    return out


def _baterias_erros(bs: Any, doc: dict | None, p: str) -> list[str]:
    if not isinstance(bs, dict):
        return [f"{p} · baterias: bloco ilegível."]
    out = []
    conhecidas = None if doc is None else baterias_do_cenario(doc)
    for eid, d in bs.items():
        cam = f"{p} · bateria {str(eid)[:20]}"
        if conhecidas is not None and eid not in conhecidas:
            out.append(f"{cam}: não é um banco habilitado do inventário de referência do cenário (declaração órfã).")
            continue
        e = _chaves(d, "bateria", cam)
        if e:
            out += e
            continue
        for campo, (rot, _un, _ch, dom) in CAMPOS_BATERIA.items():
            v = d[campo]
            if v is None:
                continue
            if not _real(v) or (dom == "eficiencia" and not 0 < v <= 1) or (dom == "positivo" and not v > 0) \
                    or (dom == "nao_negativo" and v < 0):
                faixa = {"eficiencia": "(0, 1]", "positivo": "> 0", "nao_negativo": ">= 0"}[dom]
                out.append(f"{cam} · {rot}: valor fora do domínio {faixa}.")
        out += _opcao(d["hipotese_autodescarga"], HIPOTESES_AUTODESCARGA, f"{cam} · autodescarga")
        out += _proc_erros(d["procedencia"], cam)
    return out


def _pemfc_erros(ps: Any, doc: dict | None, p: str) -> list[str]:
    if not isinstance(ps, dict):
        return [f"{p} · PEMFC: bloco ilegível."]
    out = []
    conhecidas = None if doc is None else pemfc_do_cenario(doc)
    for eid, d in ps.items():
        cam = f"{p} · PEMFC {str(eid)[:20]}"
        if conhecidas is not None and eid not in conhecidas:
            out.append(f"{cam}: não é um registro PEMFC habilitado do inventário de referência (declaração órfã).")
            continue
        e = _chaves(d, "pemfc", cam)
        if not e and (not isinstance(d["condicoes"], dict) or set(d["condicoes"]) != set(CONDICOES_PEMFC)):
            e = [f"{cam} · condições físicas: campos esperados {sorted(CONDICOES_PEMFC)}."]
        if e:
            out += e
            continue
        for k, v in d["condicoes"].items():
            if v is not None and not _real(v):
                out.append(f"{cam} · {CONDICOES_PEMFC[k][0]}: real finito.")
        for campo, (rot, _un, dom) in CAMPOS_PEMFC.items():
            v = d[campo]
            if v is None:
                continue
            if not _real(v) or (dom == "positivo" and not v > 0) or (dom == "nao_negativo" and v < 0):
                out.append(f"{cam} · {rot}: valor fora do domínio.")
        out += _opcao(d["abstracao"], ABSTRACOES_PEMFC, f"{cam} · abstração") + _opcao(
            d["limites_transicao"], LIMITES_PEMFC, f"{cam} · limites de partida/parada")
        us = d["unidades"]
        if not isinstance(us, list) or (conhecidas is not None and len(us) != _quantidade(conhecidas[eid])):
            out.append(f"{cam}: uma declaração de estado inicial por UNIDADE instalada.")
            continue
        for i, u in enumerate(us):
            eu = _chaves(u, "unidade_pemfc", f"{cam} · unidade {i + 1}")
            if eu:
                out += eu
                continue
            out += _opcao(u["estado"], ESTADOS_UNIDADE, f"{cam} · unidade {i + 1} · estado")
            for k in ("potencia_kW", "tempo_no_estado_min"):
                if u[k] is not None and not (_real(u[k]) and u[k] >= 0):
                    out.append(f"{cam} · unidade {i + 1} · {k}: real finito >= 0.")
        out += _proc_erros(d["procedencia"], cam)
    return out


def _renovaveis_erros(rs: Any, doc: dict | None, p: str) -> list[str]:
    if not isinstance(rs, dict):
        return [f"{p} · renováveis: bloco ilegível."]
    out = []
    conhecidas = None if doc is None else renovaveis_do_cenario(doc)
    for eid, d in rs.items():
        cam = f"{p} · renovável {str(eid)[:20]}"
        if conhecidas is not None and eid not in conhecidas:
            out.append(f"{cam}: não é uma usina FV/registro eólico habilitado do inventário de referência (declaração órfã).")
            continue
        tec = d.get("tecnologia") if isinstance(d, dict) else None
        if tec not in CAMPOS_RENOVAVEL:
            out.append(f"{cam}: tecnologia ilegível.")
            continue
        if conhecidas is not None and TECNOLOGIAS_RENOVAVEIS[conhecidas[eid]["kind"]] != tec:
            out.append(f"{cam}: tecnologia declarada '{tec}' difere do inventário.")
            continue
        e = _chaves(d, tec, cam)
        if e:
            out += e
            continue
        for campo, (rot, _un, dom) in CAMPOS_RENOVAVEL[tec].items():
            v = d[campo]
            if v is not None and (not _real(v) or (dom == "eficiencia" and not 0 < v <= 1)):
                out.append(f"{cam} · {rot}: valor fora do domínio (0, 1].")
        if tec == "eolica":
            out += _opcao(d["hipotese_densidade"], HIPOTESES_DENSIDADE, f"{cam} · densidade do ar")
        c = d["custo_curtailment_R_kWh"]
        if c is not None and not (_real(c) and c >= 0):
            out.append(f"{cam} · custo de vertimento: R$/kWh finito >= 0.")
        out += _proc_erros(d["procedencia"], cam)
    return out


def _pcc_erros(c: dict, p: str) -> list[str]:
    cam = f"{p} · PCC"
    out = _opcao(c["modo"], MODOS_CONEXAO, f"{cam} · modo") + _opcao(c["sentidos"], SENTIDOS, f"{cam} · sentidos")
    out += _opcao(c["disponibilidade"], DISPONIBILIDADES_PCC, f"{cam} · disponibilidade")
    out += _opcao(c["remuneracao_exportacao"], REMUNERACOES_EXPORTACAO, f"{cam} · remuneração da exportação")
    out += _opcao(c["tarifa_liquidacao"], LIQUIDACOES, f"{cam} · liquidação") + _opcao(c["ajuste"], TIPOS_AJUSTE, f"{cam} · ajuste")
    for k, rot in (("limite_importacao_kW", "limite de importação"), ("limite_exportacao_kW", "limite de exportação")):
        if c[k] is not None and not (_real(c[k]) and c[k] >= 0):
            out.append(f"{cam} · {rot}: kW finito >= 0.")
    for k, rot in (("tarifa_importacao_R_kWh", "tarifa de importação"), ("tarifa_exportacao_R_kWh", "tarifa de exportação")):
        if c[k] is not None and not (_lista_reais(c[k]) and all(x >= 0 for x in c[k])
                                     and len(c[k]) <= LIMITES["intervalos_missao"]):
            out.append(f"{cam} · {rot}: lista de R$/kWh finitos >= 0 (um valor por intervalo da missão; preço negativo "
                       "não é suportado).")
    if c["tarifa_emissao_utc"] is not None and not instante_valido(c["tarifa_emissao_utc"]):
        out.append(f"{cam} · emissão da tarifa: instante ISO 8601 com fuso explícito.")
    for k in ("rotulo_tarifa", "justificativa"):
        if not isinstance(c[k], str) or len(c[k]) > 300:
            out.append(f"{cam} · {k}: texto de até 300 caracteres.")
    return out + _proc_erros(c["procedencia"], cam)


def _planejador_erros(g: dict, p: str) -> list[str]:
    cam = f"{p} · planejador"
    out = _opcao(g["tipo_sinal"], TIPOS_SINAL, f"{cam} · sinal") + _opcao(g["degradacao"], DEGRADACOES, f"{cam} · degradação")
    out += _opcao(g["politica_atualizacao"], POLITICAS_ATUALIZACAO, f"{cam} · atualização")
    for k, lo in (("periodo_janelas", 1), ("pontos_iniciais", 2), ("pontos_max", 2), ("max_modos", 1)):
        if g[k] is not None and not (_inteiro(g[k]) and lo <= g[k] <= 200):
            out.append(f"{cam} · {k}: inteiro >= {lo}.")
    for k in ("tolerancia_interpolacao_R", "tolerancia_dominio_kWh", "delta_sensibilidade_kWh", "penalidade_branda_R_kWh"):
        if g[k] is not None and not (_real(g[k]) and g[k] >= 0):
            out.append(f"{cam} · {k}: real finito >= 0.")
    t = g["termo_longo"]
    e = _chaves(t, "termo_longo", f"{cam} · Φ_L")
    if e:
        return out + e
    out += _opcao(t["tipo"], {k: k for k in TERMOS_DECLARADOS}, f"{cam} · Φ_L")
    if not isinstance(t["valores"], dict) or any(not _real(v) or v < 0 for v in t["valores"].values()):
        out.append(f"{cam} · Φ_L: valores por banco devem ser reais finitos >= 0.")
    for k, alvo in (("justificativa", g), ("justificativa", t)):
        if not isinstance(alvo[k], str) or len(alvo[k]) > 500:
            out.append(f"{cam}: justificativa inválida (texto de até 500 caracteres).")
    return out


def _solver_erros(s: dict, p: str) -> list[str]:
    cam = f"{p} · solver"
    out = []
    if s["time_limit_s"] is not None and not (_real(s["time_limit_s"]) and 0 < s["time_limit_s"] <= 3600):
        out.append(f"{cam} · limite de tempo: (0, 3600] s por resolução.")
    if s["threads"] is not None and not (_inteiro(s["threads"]) and 1 <= s["threads"] <= 64):
        out.append(f"{cam} · threads: inteiro de 1 a 64.")
    for k in ("rel_gap", "abs_gap"):
        if s[k] is not None and not (_real(s[k]) and s[k] >= 0):
            out.append(f"{cam} · {k}: real finito >= 0.")
    if s["semente"] is not None and not (_inteiro(s["semente"]) and 0 <= s["semente"] <= 2 ** 31 - 1):
        out.append(f"{cam} · semente: inteiro >= 0.")
    return out


def erros_documento(doc: dict) -> list[str]:
    """Validação das chaves do Piso 3D-A no documento do cenário (chamada por ``scenarios.structural_errors``)."""
    out: list[str] = []
    motor = doc.get(CHAVE_MOTOR)
    if motor is not None and motor not in MOTORES:
        out.append(f"Motor de execução desconhecido: {str(motor)[:40]!r}.")
    b = doc.get(CHAVE_BLOCO)
    if b is not None:
        out += erros_estruturais(b, doc)
    return out


# ------------------------------------------------------------------------------------------------ pendências
def pendencias(b: dict, doc: dict) -> list[tuple[str, str]]:
    """O que AINDA não foi declarado e impede executar (caminho no bloco, mensagem). Supõe ``erros_estruturais`` vazio.
    Nenhum destes campos recebe valor de respaldo: a lista é exibida e a execução é bloqueada."""
    out: list[tuple[str, str]] = []

    def falta(cam: str, msg: str) -> None:
        out.append((cam, msg))
    if not procedencia_declarada(b["declarante"]):
        falta("declarante", "Procedência das políticas (quem declara a estratégia: tipo e fonte) não declarada.")
    m = b["malha"]
    for k, rot in (("delta_min", "passo Δ [min]"), ("N", "horizonte curto N [intervalos]"),
                   ("m", "bloco aplicado m [intervalos]"), ("H_L", "horizonte longo H_L [intervalos]")):
        if m[k] is None:
            falta(f"malha.{k}", f"Malha temporal: {rot} não declarado.")
    d = b["demanda"]
    if d["criticidade"] is None:
        falta("demanda.criticidade", "Criticidade da demanda não declarada (decisão D01 do responsável).")
    if d["semantica"] is None:
        falta("demanda.semantica", "Semântica da série de demanda não declarada: o Piso 2B não registra se os valores são "
              "médias de intervalo; o MILP só aceita médias de intervalo DECLARADAS (nada é presumido).")
    if d["emissao_utc"] is None:
        falta("demanda.emissao_utc", "Instante de EMISSÃO da previsão de demanda não declarado (a data de gravação da "
              "série no cenário não é tomada como emissão; sem ele a causalidade não é verificável).")
    r = b["realizacao"]
    if r["tipo"] is None:
        falta("realizacao.tipo", "Realização simulada não declarada (igual à previsão × série declarada).")
    elif r["tipo"] == "serie_declarada" and r["demanda_kW"] is None:
        falta("realizacao.demanda_kW", "Série da demanda REALIZADA não declarada.")
    if not procedencia_declarada(r["procedencia"]):
        falta("realizacao.procedencia", "Fonte da realização simulada não declarada.")
    for eid in baterias_do_cenario(doc):
        x = b["baterias"].get(eid)
        if x is None:
            continue                                   # declaração ausente do banco: constatada pelo preflight por UID
        for campo, (rot, un, _ch, _dom) in CAMPOS_BATERIA.items():
            if campo == "custo_throughput_R_kWh" and "throughput_bess" not in b["objetivo"]["termos"]:
                continue
            if x[campo] is None:
                falta(f"baterias.{eid}.{campo}", f"{rot} [{un}] não declarado(a).")
        if x["hipotese_autodescarga"] is None:
            falta(f"baterias.{eid}.hipotese_autodescarga", "Hipótese de autodescarga não declarada (sem padrão).")
        if not procedencia_declarada(x["procedencia"]):
            falta(f"baterias.{eid}.procedencia", "Procedência das declarações do banco não declarada (tipo e fonte).")
    out += _renovaveis_pendencias(b, doc)
    out += _pemfc_pendencias(b, doc)
    out += _pcc_pendencias(b["pcc"])
    g = b["planejador"]
    for k in ("tipo_sinal", "politica_atualizacao", "periodo_janelas", "pontos_iniciais", "pontos_max",
              "tolerancia_interpolacao_R", "tolerancia_dominio_kWh", "max_modos"):
        if g[k] is None:
            falta(f"planejador.{k}", f"Planejador: '{k}' não declarado.")
    if g["degradacao"] is None:
        falta("planejador.degradacao", "Política de DEGRADAÇÃO (sinal de valor futuro indisponível) não declarada.")
    if g["termo_longo"]["tipo"] is None:
        falta("planejador.termo_longo.tipo", "Termo terminal Φ_L do horizonte longo não declarado (nenhuma miopia é "
              "presumida).")
    if not str(g["termo_longo"]["justificativa"] or "").strip():
        falta("planejador.termo_longo.justificativa", "Justificativa do termo terminal Φ_L ausente.")
    if not str(g["justificativa"] or "").strip():
        falta("planejador.justificativa", "Justificativa dos parâmetros do planejador ausente.")
    for k, v in b["solver"].items():
        if v is None:
            falta(f"solver.{k}", f"Solver: '{k}' não declarado.")
    return out


def _renovaveis_pendencias(b: dict, doc: dict) -> list[tuple[str, str]]:
    part = renovaveis_participantes(doc)
    if not part:
        return []
    if b["format_version"] == 1:
        return [("renovaveis", f"Estratégia no formato 1 (Piso 3D-A), sem declarações de renováveis, mas {len(part)} "
                 "equipamento(s) FV/eólico(s) participa(m) da missão: atualize a estratégia (as seções de clima e "
                 "renováveis começam vazias) ou declare-os indisponíveis neste cenário.")]
    out: list[tuple[str, str]] = []
    cl = b["clima"]
    if cl["semantica"] is None:
        out.append(("clima.semantica", "Semântica da previsão CLIMÁTICA não declarada (média de intervalo × amostra "
                    "instantânea): o Piso 2B não a registra e o potencial médio do intervalo depende dela."))
    if cl["emissao_utc"] is None:
        out.append(("clima.emissao_utc", "Instante de EMISSÃO da previsão climática não declarado (sem ele a causalidade "
                    "do potencial renovável não é verificável)."))
    curt = "curtailment_operacional" in b["objetivo"]["termos"]
    for eid in part:
        x = b["renovaveis"].get(eid)
        if x is None:
            continue                                   # declaração ausente: constatada pelo preflight por UID
        for campo, (rot, un, _dom) in CAMPOS_RENOVAVEL[x["tecnologia"]].items():
            if x[campo] is None:
                out.append((f"renovaveis.{eid}.{campo}", f"{rot} [{un}] não declarado(a)."))
        if x["tecnologia"] == "eolica" and x["hipotese_densidade"] is None:
            out.append((f"renovaveis.{eid}.hipotese_densidade", "Hipótese de densidade do ar não declarada (calculada do "
                        "clima previsto × referência do catálogo; sem padrão)."))
        if curt and x["custo_curtailment_R_kWh"] is None:
            out.append((f"renovaveis.{eid}.custo_curtailment_R_kWh", "Custo de vertimento c_curt não declarado (termo "
                        "'curtailment_operacional' no objetivo)."))
        if not procedencia_declarada(x["procedencia"]):
            out.append((f"renovaveis.{eid}.procedencia", "Procedência das declarações do recurso renovável não declarada."))
    return out


def _pemfc_pendencias(b: dict, doc: dict) -> list[tuple[str, str]]:
    part = pemfc_participantes(doc)
    if not part:
        return []
    if b["format_version"] < 3:
        return [("pemfc", f"Estratégia no formato {b['format_version']} sem declarações PEMFC, mas {len(part)} registro(s) "
                 "PEMFC participa(m) da missão: atualize a estratégia (seção PEMFC vazia) ou declare-os indisponíveis.")]
    out: list[tuple[str, str]] = []
    termos = b["objetivo"]["termos"]
    if "combustivel_h2" not in termos:
        out.append(("objetivo.termos", "PEMFC participante exige o termo 'combustivel_h2' (o H₂ não é energia gratuita; "
                    "nenhum preço zero é presumido)."))
    for eid in part:
        x = b["pemfc"].get(eid)
        if x is None:
            continue                                   # declaração ausente: constatada pelo preflight por UID
        for k, (rot, un) in CONDICOES_PEMFC.items():
            if x["condicoes"][k] is None:
                out.append((f"pemfc.{eid}.condicoes.{k}", f"{rot} [{un}] não declarada (inicialização física da curva)."))
        for campo, (rot, un, _d) in CAMPOS_PEMFC.items():
            if campo in ("custo_partida_R", "custo_parada_R") and "eventos" not in termos:
                continue
            if x[campo] is None:
                out.append((f"pemfc.{eid}.{campo}", f"{rot} [{un}] não declarado(a)."))
        if x["abstracao"] is None:
            out.append((f"pemfc.{eid}.abstracao", "Abstração de partida/parada não declarada (decisão D05; sem padrão)."))
        if x["limites_transicao"] is None:
            out.append((f"pemfc.{eid}.limites_transicao", "Limites de partida/parada não declarados."))
        for i, u in enumerate(x["unidades"]):
            for k, rot in (("estado", "estado ON/OFF"), ("potencia_kW", "potência anterior [kW]"),
                           ("tempo_no_estado_min", "tempo no estado vigente [min]")):
                if u[k] is None:
                    out.append((f"pemfc.{eid}.unidades[{i}].{k}", f"Unidade {i + 1}: {rot} inicial não declarado(a)."))
        if not procedencia_declarada(x["procedencia"]):
            out.append((f"pemfc.{eid}.procedencia", "Procedência das declarações PEMFC não declarada."))
    return out


def _pcc_pendencias(c: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if c["modo"] is None:
        return [("pcc.modo", "Modo do PCC não declarado (conectado × isolado declarado): PCC ausente NÃO é conexão "
                 "ilimitada nem ilha presumida.")]
    if not procedencia_declarada(c["procedencia"]):
        out.append(("pcc.procedencia", "Procedência das declarações do PCC/tarifas não declarada (tipo e fonte)."))
    if not str(c["justificativa"] or "").strip():
        out.append(("pcc.justificativa", "Justificativa da declaração do PCC ausente."))
    if c["sentidos"] is None:
        out.append(("pcc.sentidos", "Sentidos permitidos do intercâmbio não declarados."))
    if c["ajuste"] is None:
        out.append(("pcc.ajuste", "Política de ajuste do PCC na execução não declarada."))
    if c["modo"] != "conectado":
        return out
    imp = c["sentidos"] in ("importacao_e_exportacao", "somente_importacao")
    exp = c["sentidos"] in ("importacao_e_exportacao", "somente_exportacao")
    if c["disponibilidade"] is None:
        out.append(("pcc.disponibilidade", "Disponibilidade do PCC não declarada."))
    if c["tarifa_emissao_utc"] is None and (imp or exp):
        out.append(("pcc.tarifa_emissao_utc", "Instante de emissão das tarifas de decisão não declarado."))
    if c["tarifa_liquidacao"] is None and (imp or exp):
        out.append(("pcc.tarifa_liquidacao", "Regra de liquidação não declarada."))
    if not str(c["rotulo_tarifa"] or "").strip() and (imp or exp):
        out.append(("pcc.rotulo_tarifa", "Rótulo da tarifa ausente (p. ex. 'SINTÉTICA — não é tarifa real')."))
    if imp:
        if c["limite_importacao_kW"] is None:
            out.append(("pcc.limite_importacao_kW", "Limite contratado de importação não declarado (rede disponível não "
                        "é importação ilimitada)."))
        if c["tarifa_importacao_R_kWh"] is None:
            out.append(("pcc.tarifa_importacao_R_kWh", "Tarifa de importação não declarada (a rede não é energia gratuita)."))
    if exp:
        if c["limite_exportacao_kW"] is None:
            out.append(("pcc.limite_exportacao_kW", "Limite contratado de exportação não declarado."))
        if c["remuneracao_exportacao"] is None:
            out.append(("pcc.remuneracao_exportacao", "Remuneração da exportação não declarada."))
        elif c["remuneracao_exportacao"] == "remunerada" and c["tarifa_exportacao_R_kWh"] is None:
            out.append(("pcc.tarifa_exportacao_R_kWh", "Tarifa de exportação não declarada."))
    return out


def status_estrategia(doc: dict) -> tuple[str, str, str]:
    """(tom, rótulo, detalhe) da etapa 03 quando o motor selecionado é o V2."""
    b = doc.get(CHAVE_BLOCO)
    if b is None:
        return "warn", "Não definida", "declare a estratégia MILP–MPC (motor V2 experimental)"
    errs = erros_estruturais(b, doc)
    if errs:
        return "bad", "Com erros", f"{len(errs)} problema(s)"
    pend = pendencias(b, doc)
    m = b["malha"]
    base = f"MILP–MPC · Δ = {m['delta_min']} min · N = {m['N']} · m = {m['m']} · H_L = {m['H_L']}"
    if pend:
        return "warn", "Incompleta", f"{len(pend)} declaração(ões) ausente(s)"
    return "ok", "Declarada", base


__all__ = ["CAMPOS_BATERIA", "CHAVE_BLOCO", "CHAVE_MOTOR", "CONTEXTOS", "CONTEXTO_NAO_SUPORTADO", "CRITICIDADES",
           "CAMPOS_RENOVAVEL", "DISPONIBILIDADES_PCC", "FORMATO", "FORMATOS_LEGIVEIS", "HIPOTESES_AUTODESCARGA",
           "HIPOTESES_DENSIDADE", "LIMITES", "LIQUIDACOES", "MOTORES", "MOTOR_V16", "MOTOR_V2", "REALIZACOES",
           "REFERENCIA_NUMERICA", "ROTULO_REFERENCIA", "SEMANTICAS", "SEMANTICAS_CLIMA", "TECNOLOGIAS_RENOVAVEIS",
           "TERMOS_BASE", "TIPOS_DECLARAVEIS", "atualizar_bloco", "baterias_do_cenario", "erros_documento",
           "erros_estruturais", "instante_valido", "motor_selecionado", "novo_bloco", "pendencias",
           "procedencia_declarada", "renovaveis_do_cenario", "renovaveis_participantes", "status_estrategia",
           "ABSTRACOES_PEMFC", "CAMPOS_PEMFC", "CONDICOES_PEMFC", "ESTADOS_UNIDADE", "LIMITES_PEMFC", "pemfc_do_cenario",
           "pemfc_participantes"]
