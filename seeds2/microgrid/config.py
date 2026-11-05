"""Documento de configuração da ÚNICA microrrede desta instalação.

A configuração é um documento JSON (dicionários simples) para garantir ida-e-volta exata
com o armazenamento. Este módulo define:

* a estrutura (``new_config``/``new_equipment``) e a versão do documento;
* a especificação de parâmetros por tecnologia (unidade, faixa, obrigatoriedade para simular);
* a validação estrutural e física (``validate``) e o estado de cada equipamento.

Não há aqui nenhuma equação dos modelos. Valores ausentes são PERMITIDOS (o usuário não é
obrigado a inventar dados): eles apenas impedem que o equipamento seja "tecnicamente configurado".
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .references import (KINDS, PEMFC_REF_KEY, THERMAL_DYNAMIC_KEYS, battery_references, pv_references,
                         thermal_fuel_presets, wind_references)

DOC_SCHEMA_VERSION = 1
EQUIPMENT_ID_RE = re.compile(r"^eq-[0-9a-f]{12}$")

NATURE_OPTIONS = {
    "industrial": "Industrial",
    "laboratorio": "Laboratório / pesquisa",
    "comercial": "Comercial / serviços",
    "rural": "Rural / agroindustrial",
    "transporte": "Embarcação / transporte",
    "comunitaria": "Comunitária / residencial",
    "outra": "Outra",
}
OPERATION_MODE_OPTIONS = {
    "isolada": "Isolada (off-grid)",
    "conectada": "Conectada à rede",
    "conectada_ilhamento": "Conectada, com capacidade declarada de ilhamento",
    "nao_definido": "Ainda não definido",
}
BUS_KIND_OPTIONS = {"CA": "Barramento CA", "CC": "Barramento CC", "nao_declarado": "Não declarado"}
GRID_CONNECTION_OPTIONS = {"isolada": "Sem conexão com a rede", "conectada": "Conectada à rede de distribuição",
                           "nao_declarada": "Não declarada"}
COUPLING_OPTIONS = {
    "inversor": "Inversor (CC→CA)",
    "conversor_cc_cc": "Conversor CC-CC",
    "conversor_bidirecional": "Conversor bidirecional",
    "retificador": "Retificador (CA→CC)",
    "direto": "Acoplamento direto",
    "nao_declarado": "Não declarado",
}
DEMAND_SOURCES = {
    "nao_definida": "Ainda não definida",
    "walkforward": "Perfil de referência walk-forward (embarcação, 2 h)",
    "copel": "Curva típica COPEL B1",
    "csv": "CSV importado pela instalação",
}
PROVENANCE_KINDS = {
    "medido": "Medido na instalação",
    "sintetico": "Sintético / gerado",
    "referencia": "Conjunto de referência incluído no software (não medido nesta instalação)",
    "nao_declarado": "Procedência não declarada",
}
CLIMATE_SOURCES = {"sintetico": "Sintético diário (explícito, para demonstração)", "csv": "CSV climático importado"}
PEMFC_POWER_BASIS = {"entregue": "Potência entregue (líquida)", "stack": "Potência do stack (legado)"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ======================================================== especificação de parâmetros
@dataclass(frozen=True)
class ParamSpec:
    name: str
    label: str
    unit: str
    type: str                       # "int" | "float" | "choice" | "bool"
    required: bool = True           # obrigatório para SIMULAR (não para registrar)
    min: float | None = None
    max: float | None = None
    min_exclusive: bool = False
    max_exclusive: bool = False
    help: str = ""
    default: Any = None             # usado SÓ para opções de modelagem, nunca para dados físicos


def _choices(kind: str, name: str) -> dict[str, str]:
    if kind == "pv" and name == "reference":
        return {k: r.label for k, r in pv_references().items()}
    if kind == "wind" and name == "reference":
        return {k: r.label for k, r in wind_references().items()}
    if kind == "battery" and name == "reference":
        return {k: r.label for k, r in battery_references().items()}
    if kind == "pemfc" and name == "reference":
        return {PEMFC_REF_KEY: "Sistema PEMFC equivalente · Horizon VLIIPro50-22 (aproximado)"}
    if kind == "pemfc" and name == "power_basis":
        return dict(PEMFC_POWER_BASIS)
    if kind == "thermal" and name == "dynamic":
        from .references import thermal_dynamics
        return thermal_dynamics()
    if kind == "thermal" and name == "fuel_preset":
        return {k: k for k in thermal_fuel_presets()}
    return {}


def choices(kind: str, name: str) -> dict[str, str]:
    return _choices(kind, name)


PARAM_SPECS: dict[str, tuple[ParamSpec, ...]] = {
    "pv": (
        ParamSpec("reference", "Módulo FV (referência)", "", "choice", help="Módulo do catálogo config/pv_database.py."),
        ParamSpec("n_series", "Módulos em série por string", "módulos", "int", min=1),
        ParamSpec("n_parallel", "Strings em paralelo", "strings", "int", min=1),
        ParamSpec("soiling_pct", "Perdas por sujeira", "%", "float", min=0, max=100, max_exclusive=True,
                  help="Declare 0 se nenhuma perda for considerada; não há valor presumido."),
    ),
    "wind": (
        ParamSpec("reference", "Aerogerador (referência)", "", "choice", help="Curva original de config/wind_turbine_database.py."),
        ParamSpec("count", "Quantidade de aerogeradores", "unidades", "int", min=1),
        ParamSpec("apply_grid_loss", "Aplicar perda genérica gerador→rede do módulo eólico", "", "bool", default=False,
                  help="Opção do modelo eólico existente (perda genérica fixa)."),
    ),
    "battery": (
        ParamSpec("reference", "Célula e modelo (referência)", "", "choice"),
        ParamSpec("n_series", "Células em série (Ns)", "células", "int", min=1),
        ParamSpec("n_parallel", "Ramos em paralelo (Np)", "ramos", "int", min=1),
        ParamSpec("soc0_pct", "SOC inicial", "%", "float", min=0, max=100),
        ParamSpec("soc_min_pct", "SOC mínimo operacional", "%", "float", min=0, max=100),
        ParamSpec("soc_max_pct", "SOC máximo operacional", "%", "float", min=0, max=100),
        ParamSpec("c_discharge", "Taxa máxima de descarga", "C", "float", min=0, min_exclusive=True),
        ParamSpec("c_charge", "Taxa máxima de carga", "C", "float", min=0, min_exclusive=True),
    ),
    "pemfc": (
        ParamSpec("reference", "Perfil PEMFC (referência)", "", "choice", default=PEMFC_REF_KEY),
        ParamSpec("quantity", "Sistemas/stacks instalados", "unidades", "int", min=1),
        ParamSpec("power_basis", "Base do envelope de potência no EMS", "", "choice", default="entregue",
                  help="Convenção do EMS V1.6: 'entregue' já é potência líquida (ηFC=1 no balanço)."),
    ),
    "thermal": (
        ParamSpec("dynamic", "Dinâmica operacional", "", "choice"),
        ParamSpec("fuel_preset", "Combustível (preset acadêmico de CVU)", "", "choice", required=False,
                  help="Apenas rótulo/origem do CVU sugerido; não representa usina real."),
        ParamSpec("pmax_kW", "Potência máxima", "kW", "float", min=0, min_exclusive=True),
        ParamSpec("pmin_kW", "Potência mínima técnica", "kW", "float", min=0),
        ParamSpec("cvu_rs_MWh", "CVU", "R$/MWh", "float", min=0),
        ParamSpec("ramp_kW_min", "Rampa máxima", "kW/min", "float", required=False, min=0, min_exclusive=True,
                  help="Vazio = sem limite de rampa declarado."),
        ParamSpec("startup_cost_rs", "Custo de partida", "R$", "float", min=0),
    ),
}

PARAM_INDEX = {kind: {p.name: p for p in specs} for kind, specs in PARAM_SPECS.items()}


# ======================================================== construção
def new_equipment_id() -> str:
    return f"eq-{uuid.uuid4().hex[:12]}"


def new_equipment(kind: str, name: str, **fields: Any) -> dict:
    if kind not in KINDS:
        raise ValueError(f"Tipo de equipamento desconhecido: {kind!r}")
    now = utc_now()
    params = {p.name: p.default for p in PARAM_SPECS[kind]}
    params.update(fields.pop("params", {}) or {})
    eq = {
        "id": fields.pop("id", None) or new_equipment_id(),
        "kind": kind,
        "name": str(name).strip(),
        "tag": fields.pop("tag", "") or "",
        "serial": fields.pop("serial", "") or "",
        "enabled": bool(fields.pop("enabled", True)),
        "params": params,
        "notes": fields.pop("notes", "") or "",
        "created_at": now,
        "updated_at": now,
    }
    if fields:
        raise ValueError(f"Campos desconhecidos para equipamento: {sorted(fields)}")
    return eq


def new_config(name: str = "") -> dict:
    now = utc_now()
    return {
        "schema_version": DOC_SCHEMA_VERSION,
        "installation": {
            "uid": uuid.uuid4().hex,
            "name": str(name).strip(),
            "description": "",
            "location": "",
            "latitude": None,
            "longitude": None,
            "timezone": "",
            "nature": None,
            "operation_mode": None,
            "created_at": now,
        },
        "commissioning": {"completed": False, "step": 1, "completed_at": None},
        "equipment": [],
        "retired": [],
        "topology": {
            "bus_kind": "nao_declarado",
            "bus_label": "Barramento principal",
            "nominal_voltage_V": None,
            "grid_connection": "nao_declarada",
            "couplings": {},
            "load_coupling": "nao_declarado",
        },
        "demand": {
            "source": "nao_definida",
            "walkforward": {"scenario": None, "profile": None, "start_hour": None},
            "copel": {"day": None, "start_h": None, "duration_min": None},
            # {"blob": sha256, "filename", "start_min", "duration_min", "rows", "columns", "t0"}
            "csv": None,
            "provenance": "nao_declarado",
            "timezone": "",
            "notes": "",
        },
        "climate": {"source": "sintetico", "csv": None, "provenance": "sintetico", "notes": ""},
    }


def find_equipment(config: dict, eq_id: str) -> dict | None:
    return next((e for e in config.get("equipment", []) if e.get("id") == eq_id), None)


def add_equipment(config: dict, eq: dict) -> dict:
    if find_equipment(config, eq["id"]) is not None:
        raise ValueError(f"Identificador duplicado: {eq['id']}")
    config.setdefault("equipment", []).append(eq)
    config["topology"].setdefault("couplings", {}).setdefault(eq["id"], "nao_declarado")
    return eq


def update_equipment(config: dict, eq_id: str, **changes: Any) -> dict:
    eq = find_equipment(config, eq_id)
    if eq is None:
        raise KeyError(f"Equipamento inexistente: {eq_id}")
    if "id" in changes or "kind" in changes:
        raise ValueError("Identificador e tipo de um equipamento são imutáveis.")
    params = changes.pop("params", None)
    for k, v in changes.items():
        if k not in ("name", "tag", "serial", "enabled", "notes"):
            raise ValueError(f"Campo não editável: {k}")
        eq[k] = v.strip() if isinstance(v, str) else v
    if params is not None:
        unknown = set(params) - set(PARAM_INDEX[eq["kind"]])
        if unknown:
            raise ValueError(f"Parâmetros desconhecidos para {eq['kind']}: {sorted(unknown)}")
        eq["params"].update(params)
    eq["updated_at"] = utc_now()
    return eq


def retire_equipment(config: dict, eq_id: str, reason: str = "") -> dict:
    """Retira o equipamento do inventário ativo; o registro fica em ``retired`` (auditoria)."""
    eq = find_equipment(config, eq_id)
    if eq is None:
        raise KeyError(f"Equipamento inexistente: {eq_id}")
    config["equipment"] = [e for e in config["equipment"] if e["id"] != eq_id]
    config["topology"].get("couplings", {}).pop(eq_id, None)
    rec = copy.deepcopy(eq)
    rec["retired_at"] = utc_now()
    rec["retired_reason"] = str(reason or "")
    config.setdefault("retired", []).append(rec)
    return rec


# ======================================================== validação
@dataclass(frozen=True)
class Issue:
    level: str          # "error" bloqueia o salvamento; "warning" apenas informa
    path: str
    message: str


def _num_ok(spec: ParamSpec, v: Any) -> str | None:
    if spec.type == "int":
        if isinstance(v, bool) or not (isinstance(v, int) or (isinstance(v, float) and v.is_integer())):
            return "deve ser um número inteiro"
    elif spec.type == "float":
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return "deve ser numérico"
        if v != v or v in (float("inf"), float("-inf")):
            return "deve ser finito"
    if spec.min is not None and (v < spec.min or (spec.min_exclusive and v == spec.min)):
        return f"deve ser {'>' if spec.min_exclusive else '≥'} {spec.min:g}{(' ' + spec.unit) if spec.unit else ''}"
    if spec.max is not None and (v > spec.max or (spec.max_exclusive and v == spec.max)):
        return f"deve ser {'<' if spec.max_exclusive else '≤'} {spec.max:g}{(' ' + spec.unit) if spec.unit else ''}"
    return None


def validate_param(kind: str, name: str, value: Any) -> str | None:
    spec = PARAM_INDEX[kind][name]
    if value is None:
        return None
    if spec.type == "choice":
        opts = _choices(kind, name)
        if not isinstance(value, str):
            return "deve ser um identificador de referência (texto)"
        return None if value in opts else f"valor {value[:80]!r} não pertence às referências disponíveis"
    if spec.type == "bool":
        return None if isinstance(value, bool) else "deve ser verdadeiro/falso"
    return _num_ok(spec, value)


def equipment_issues(eq: dict, prefix: str = "") -> list[Issue]:
    p = prefix or f"equipment[{eq.get('id')}]"
    out: list[Issue] = []
    kind = eq.get("kind")
    if kind not in KINDS:
        return [Issue("error", f"{p}.kind", f"Tipo desconhecido: {kind!r}")]
    if not EQUIPMENT_ID_RE.match(str(eq.get("id", ""))):
        out.append(Issue("error", f"{p}.id", "Identificador inválido (formato esperado eq-xxxxxxxxxxxx)."))
    if not str(eq.get("name", "")).strip():
        out.append(Issue("error", f"{p}.name", "Nome do equipamento é obrigatório."))
    for k in ("tag", "serial", "notes"):
        if not isinstance(eq.get(k, ""), str):
            out.append(Issue("error", f"{p}.{k}", "Deve ser texto."))
    if not isinstance(eq.get("enabled"), bool):
        out.append(Issue("error", f"{p}.enabled", "Estado habilitado deve ser verdadeiro/falso."))
    params = eq.get("params")
    if not isinstance(params, dict):
        return out + [Issue("error", f"{p}.params", "Parâmetros ausentes.")]
    unknown = set(params) - set(PARAM_INDEX[kind])
    for u in sorted(unknown):
        out.append(Issue("error", f"{p}.params.{u}", "Parâmetro desconhecido para este tipo."))
    for name, value in params.items():
        if name in PARAM_INDEX[kind]:
            msg = validate_param(kind, name, value)
            if msg:
                out.append(Issue("error", f"{p}.params.{name}", f"{PARAM_INDEX[kind][name].label}: {msg}."))
    # relações físicas entre parâmetros (só quando ambos foram declarados)
    g = params.get
    if kind == "battery":
        lo, hi, s0 = g("soc_min_pct"), g("soc_max_pct"), g("soc0_pct")
        if lo is not None and hi is not None and lo >= hi:
            out.append(Issue("error", f"{p}.params.soc_min_pct", "SOC mínimo deve ser menor que o SOC máximo."))
        if s0 is not None and lo is not None and s0 < lo:
            out.append(Issue("error", f"{p}.params.soc0_pct", "SOC inicial abaixo do SOC mínimo."))
        if s0 is not None and hi is not None and s0 > hi:
            out.append(Issue("error", f"{p}.params.soc0_pct", "SOC inicial acima do SOC máximo."))
    if kind == "thermal":
        if g("pmin_kW") is not None and g("pmax_kW") is not None and g("pmin_kW") > g("pmax_kW"):
            out.append(Issue("error", f"{p}.params.pmin_kW", "Potência mínima técnica não pode superar a potência máxima."))
    return out


def missing_required(eq: dict) -> list[str]:
    """Parâmetros obrigatórios para simulação ainda não declarados (rótulos)."""
    if eq.get("kind") not in PARAM_SPECS:
        return []
    params = eq.get("params") or {}
    return [s.label for s in PARAM_SPECS[eq["kind"]] if s.required and params.get(s.name) is None]


def is_configured(eq: dict) -> bool:
    return not missing_required(eq) and not [i for i in equipment_issues(eq) if i.level == "error"]


def _str_field(obj: dict, key: str, path: str, out: list[Issue], required: bool = False) -> None:
    v = obj.get(key)
    if v is None and not required:
        return
    if not isinstance(v, str):
        out.append(Issue("error", f"{path}.{key}", "Deve ser texto."))
    elif required and not v.strip():
        out.append(Issue("error", f"{path}.{key}", "Campo obrigatório."))


def validate(config: dict) -> list[Issue]:
    """Validação completa do documento. Erros impedem salvar; avisos são informativos.

    Nunca levanta exceção: documentos com estrutura inesperada (p. ex. vindos de um backup adulterado)
    resultam em erro de validação."""
    try:
        return _validate(config)
    except (TypeError, AttributeError, ValueError, KeyError, IndexError) as exc:
        return [Issue("error", "$", f"Estrutura do documento inválida ({type(exc).__name__}).")]


def _validate(config: dict) -> list[Issue]:
    out: list[Issue] = []
    if not isinstance(config, dict):
        return [Issue("error", "$", "Configuração deve ser um objeto.")]
    if config.get("schema_version") != DOC_SCHEMA_VERSION:
        out.append(Issue("error", "schema_version",
                         f"Versão de documento {config.get('schema_version')!r} não suportada (esperado {DOC_SCHEMA_VERSION})."))
    for section in ("installation", "commissioning", "topology", "demand", "climate"):
        if not isinstance(config.get(section), dict):
            out.append(Issue("error", section, "Seção ausente ou inválida."))
    if not isinstance(config.get("equipment"), list) or not isinstance(config.get("retired", []), list):
        out.append(Issue("error", "equipment", "Inventário ausente ou inválido."))
    if any(i.level == "error" for i in out):
        return out
    # tipos das subestruturas: um tipo errado "falso" (p. ex. lista vazia) não pode passar despercebido
    typed = [("commissioning.completed", config["commissioning"].get("completed"), bool),
             ("topology.couplings", config["topology"].get("couplings"), dict),
             ("demand.walkforward", config["demand"].get("walkforward"), dict),
             ("demand.copel", config["demand"].get("copel"), dict)]
    for path, val, typ in typed:
        if not isinstance(val, typ):
            out.append(Issue("error", path, "Estrutura inválida."))
    st = config["commissioning"].get("step")
    if isinstance(st, bool) or not isinstance(st, int) or not 1 <= st <= 5:
        out.append(Issue("error", "commissioning.step", "Etapa de comissionamento inválida."))
    for path, val in (("demand.csv", config["demand"].get("csv")), ("climate.csv", config["climate"].get("csv"))):
        if val is not None and not isinstance(val, dict):
            out.append(Issue("error", path, "Estrutura inválida."))
    for k in ("timezone", "notes"):
        if not isinstance(config["demand"].get(k, ""), str):
            out.append(Issue("error", f"demand.{k}", "Deve ser texto."))
    if not isinstance(config["topology"].get("bus_label", ""), str):
        out.append(Issue("error", "topology.bus_label", "Deve ser texto."))
    if any(i.level == "error" for i in out):
        return out

    inst = config["installation"]
    if not re.fullmatch(r"[0-9a-f]{32}", str(inst.get("uid", ""))):
        out.append(Issue("error", "installation.uid", "Identidade da instalação inválida."))
    _str_field(inst, "name", "installation", out, required=True)
    for k in ("description", "location", "timezone"):
        _str_field(inst, k, "installation", out)
    if inst.get("nature") is not None and inst["nature"] not in NATURE_OPTIONS:
        out.append(Issue("error", "installation.nature", "Natureza da instalação inválida."))
    if inst.get("operation_mode") is not None and inst["operation_mode"] not in OPERATION_MODE_OPTIONS:
        out.append(Issue("error", "installation.operation_mode", "Modo operativo inválido."))
    for k, lim in (("latitude", 90.0), ("longitude", 180.0)):
        v = inst.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not -lim <= v <= lim):
            out.append(Issue("error", f"installation.{k}", f"Deve estar entre −{lim:g}° e {lim:g}°."))
    tz = inst.get("timezone") or ""
    if tz:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(tz)
        except Exception:
            out.append(Issue("error", "installation.timezone", f"Fuso horário IANA desconhecido: {tz!r}."))

    ids: set[str] = set()
    for eq in config["equipment"]:
        if not isinstance(eq, dict):
            out.append(Issue("error", "equipment", "Equipamento inválido."))
            continue
        if eq.get("id") in ids:
            out.append(Issue("error", f"equipment[{eq.get('id')}].id", "Identificador duplicado."))
        ids.add(eq.get("id"))
        out.extend(equipment_issues(eq))
    names = [str(e.get("name", "")).strip().lower() for e in config["equipment"] if isinstance(e, dict)]
    for n in sorted({n for n in names if n and names.count(n) > 1}):
        out.append(Issue("warning", "equipment", f"Nome repetido no inventário: {n!r} (use o TAG para diferenciar)."))
    for r in config.get("retired", []):
        if isinstance(r, dict) and r.get("id") in ids:
            out.append(Issue("error", f"retired[{r.get('id')}]", "Equipamento retirado com identificador ainda ativo."))

    topo = config["topology"]
    if topo.get("bus_kind") not in BUS_KIND_OPTIONS:
        out.append(Issue("error", "topology.bus_kind", "Tipo de barramento inválido."))
    if topo.get("grid_connection") not in GRID_CONNECTION_OPTIONS:
        out.append(Issue("error", "topology.grid_connection", "Estado de conexão à rede inválido."))
    v = topo.get("nominal_voltage_V")
    if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0):
        out.append(Issue("error", "topology.nominal_voltage_V", "Tensão nominal declarada deve ser > 0 V."))
    for eid, c in (topo.get("couplings") or {}).items():
        if eid not in ids:
            out.append(Issue("error", f"topology.couplings.{eid}", "Acoplamento referencia equipamento inexistente."))
        elif c not in COUPLING_OPTIONS:
            out.append(Issue("error", f"topology.couplings.{eid}", "Tipo de acoplamento inválido."))
    if topo.get("load_coupling") not in COUPLING_OPTIONS:
        out.append(Issue("error", "topology.load_coupling", "Acoplamento da demanda inválido."))
    mode, grid = inst.get("operation_mode"), topo.get("grid_connection")
    if mode == "isolada" and grid == "conectada":
        out.append(Issue("warning", "topology.grid_connection",
                         "Modo operativo 'isolada' declarado, mas a topologia indica conexão à rede."))

    dem = config["demand"]
    if dem.get("source") not in DEMAND_SOURCES:
        out.append(Issue("error", "demand.source", "Fonte de demanda inválida."))
    if dem.get("provenance") not in PROVENANCE_KINDS:
        out.append(Issue("error", "demand.provenance", "Procedência da demanda inválida."))
    if dem.get("source") == "csv":
        csv = dem.get("csv") or {}
        if not re.fullmatch(r"[0-9a-f]{64}", str(csv.get("blob", ""))):
            out.append(Issue("error", "demand.csv", "Perfil CSV sem conteúdo armazenado (hash ausente)."))
    if dem.get("source") in ("walkforward", "copel") and dem.get("provenance") == "medido":
        out.append(Issue("error", "demand.provenance",
                         "Perfis de referência incluídos no software não podem ser declarados como medidos."))
    clim = config["climate"]
    if clim.get("source") not in CLIMATE_SOURCES:
        out.append(Issue("error", "climate.source", "Fonte climática inválida."))
    if clim.get("source") == "sintetico" and clim.get("provenance") == "medido":
        out.append(Issue("error", "climate.provenance", "Clima sintético não pode ser declarado como medido."))
    if clim.get("source") == "csv" and not re.fullmatch(r"[0-9a-f]{64}", str((clim.get("csv") or {}).get("blob", ""))):
        out.append(Issue("error", "climate.csv", "CSV climático sem conteúdo armazenado (hash ausente)."))
    return out


def errors(issues: Iterable[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == "error"]


# ======================================================== identidade de conteúdo
def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def fingerprint(config: dict) -> str:
    """SHA-256 do conteúdo canônico da configuração (identifica a versão usada por uma rodada)."""
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()


def installed_power_kW(eq: dict) -> float | None:
    """Potência nominal declarada (derivada da referência × quantidade). None se faltarem dados."""
    p = eq.get("params") or {}
    try:
        if eq["kind"] == "pv" and p.get("reference") and p.get("n_series") and p.get("n_parallel"):
            return pv_references()[p["reference"]].summary["P_STC [W]"] * p["n_series"] * p["n_parallel"] / 1000.0
        if eq["kind"] == "wind" and p.get("reference") and p.get("count"):
            return wind_references()[p["reference"]].summary["P_nominal [kW]"] * p["count"]
        if eq["kind"] == "thermal" and p.get("pmax_kW"):
            return float(p["pmax_kW"])
        if eq["kind"] == "pemfc" and p.get("quantity"):
            from .references import pemfc_max_net_power_kW
            return pemfc_max_net_power_kW() * p["quantity"]
    except KeyError:
        return None
    return None


def battery_energy_kWh(eq: dict) -> float | None:
    p = eq.get("params") or {}
    if eq.get("kind") != "battery" or not (p.get("reference") and p.get("n_series") and p.get("n_parallel")):
        return None
    from .references import battery_cell
    try:
        v, q = battery_cell(p["reference"])
    except KeyError:
        return None
    return v * q * p["n_series"] * p["n_parallel"] / 1000.0


THERMAL_DYNAMICS = THERMAL_DYNAMIC_KEYS
