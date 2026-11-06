"""Inicialização — estados iniciais dos equipamentos de um cenário operativo (Piso 2A).

O estado inicial é uma CONDIÇÃO EXPERIMENTAL do cenário: não altera o inventário físico permanente da microrrede
nem os modelos científicos. Os controles da interface são construídos a partir do inventário salvo (Piso 1); cada
estado é indexado pelo identificador ESTÁVEL do equipamento (``eq-…``).

Três categorias de constatação, sempre explícitas (``Finding.level``):

* ``erro``      — **erro de coerência**: dados contraditórios ou impossíveis de interpretar (p. ex. PEMFC
  desligada entregando 25 kW, SOC fora de 0–100 %, mais unidades em operação do que instaladas). Impede salvar.
* ``aviso``     — **advertência técnica**: valor pouco recomendável, porém permitido (p. ex. SOC inicial fora do
  intervalo recomendado). NUNCA bloqueia.
* ``pendente``  — **capacidade científica pendente**: condição registrada no cenário que o EMS V1.6 ainda não
  interpreta (ou interpreta de modo incompatível). É preservada para integração futura e NUNCA é usada em
  silêncio como restrição do otimizador.

Além delas, ``incompleto`` indica um dado ainda não definido (prontidão do cenário; não é erro).

Hierarquia dos limites de SOC (decisão do responsável):

1. **limite físico** — 0–100 % (o modelo de bateria aceita SOC inicial em [0, 1]); fora dele → erro;
2. **restrição operacional deliberada** — ``soc_min_pct``/``soc_max_pct`` do inventário quando a origem é
   ``fabricante``, ``instalacao`` ou ``migrado``; fora dela → aviso (+ pendência: o EMS V1.6 a trata como
   restrição efetiva e o adaptador atual exclui o banco);
3. **intervalo recomendado** — os mesmos campos quando a origem é ``sugerido`` (valor inicial do SEEDS2, não do
   fabricante); fora dele → aviso (+ a mesma pendência do EMS V1.6).

Nenhuma física de partida é inventada: "em partida" é apenas um rótulo de estado registrado.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from seeds2.microgrid import config as C
from seeds2.microgrid.references import KIND_LABELS, KINDS

ERROR, WARNING, PENDING, INCOMPLETE = "erro", "aviso", "pendente", "incompleto"
LEVEL_LABELS = {ERROR: "Erro de coerência", WARNING: "Advertência técnica",
                PENDING: "Capacidade científica pendente", INCOMPLETE: "Não definido"}

AVAILABILITY = {"disponivel": "Disponível", "indisponivel": "Indisponível (manutenção, falha ou retirada temporária)"}
DISPATCH_STATES = {"desligada": "Desligada", "em_partida": "Em partida", "em_operacao": "Em operação"}
THERMAL_STATES = {"desligada": "Desligada", "em_partida": "Em partida", "em_operacao": "Em operação"}
# Campos aceitos por tipo de equipamento (qualquer outro campo é erro estrutural).
FIELDS = {
    "pv": ("availability", "note"),
    "wind": ("availability", "note"),
    "battery": ("availability", "soc0_pct", "note"),
    "pemfc": ("availability", "state", "units_on", "power_kW", "note"),
    "thermal": ("availability", "state", "power_kW", "note"),
}
SOC_OPERATIONAL_SOURCES = ("fabricante", "instalacao", "migrado")
EXTREME_SOC_PCT = 5.0            # abaixo/acima (100 − x) → aviso de extremo físico (permitido)
_EPS = 1e-9


@dataclass(frozen=True)
class Finding:
    level: str
    eq_id: str | None
    field: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ referência física do equipamento
def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def equipment_reference(eq: dict) -> dict:
    """Características físicas de referência (do inventário salvo) relevantes para o estado inicial.
    Somente valores registrados ou calculáveis pelo inventário; o desconhecido fica ``None``."""
    p = eq.get("params") or {}
    ref: dict[str, Any] = {"kind": eq["kind"], "name": eq.get("name", ""), "tag": eq.get("tag", ""),
                           "enabled": bool(eq.get("enabled", True)), "nominal_kW": C.installed_power_kW(eq)}
    if eq["kind"] == "battery":
        ref.update(energy_kWh=C.battery_energy_kWh(eq), soc_min_pct=_num(p.get("soc_min_pct")),
                   soc_max_pct=_num(p.get("soc_max_pct")), soc_limits_source=p.get("soc_limits_source") or "sugerido")
    elif eq["kind"] == "pemfc":
        q = p.get("quantity")
        ref.update(quantity=q if isinstance(q, int) and not isinstance(q, bool) else None,
                   unit_max_kW=(ref["nominal_kW"] / q) if ref["nominal_kW"] and isinstance(q, int) and q > 0 else None,
                   reference=p.get("reference"))
    elif eq["kind"] == "thermal":
        ref.update(pmax_kW=_num(p.get("pmax_kW")), pmin_kW=_num(p.get("pmin_kW")), dynamic=p.get("dynamic"))
    elif eq["kind"] == "wind":
        ref.update(count=p.get("count"), reference=p.get("reference"))
    elif eq["kind"] == "pv":
        ref.update(arrays=len(eq.get("arrays") or []))
    return ref


def default_state(kind: str) -> dict:
    """Estado inicial de um equipamento recém-incluído no cenário: disponível e com os demais campos NÃO
    definidos (o usuário declara; nada é inventado)."""
    st: dict[str, Any] = {"availability": "disponivel", "note": ""}
    if kind == "battery":
        st["soc0_pct"] = None
    elif kind == "pemfc":
        st.update(state=None, units_on=None, power_kW=None)
    elif kind == "thermal":
        st.update(state=None, power_kW=None)
    return st


# ------------------------------------------------------------------ validação
def structural_issues(eq_id: str, kind: str, state: Any) -> list[Finding]:
    """Tipos e campos do estado (dados impossíveis de interpretar → erro de coerência)."""
    out: list[Finding] = []
    if not isinstance(state, dict):
        return [Finding(ERROR, eq_id, "", "Estado inicial ilegível (não é um objeto).")]
    unknown = set(state) - set(FIELDS[kind])
    if unknown:
        out.append(Finding(ERROR, eq_id, "", f"Campos desconhecidos no estado inicial: {sorted(unknown)}."))
    if state.get("availability") not in AVAILABILITY:
        out.append(Finding(ERROR, eq_id, "availability", "Disponibilidade técnica inválida."))
    if not isinstance(state.get("note", ""), str) or len(state.get("note", "")) > 2000:
        out.append(Finding(ERROR, eq_id, "note", "Observação inválida (texto de até 2000 caracteres)."))
    for f in ("soc0_pct", "power_kW"):
        if f in state and state[f] is not None and _num(state[f]) is None:
            out.append(Finding(ERROR, eq_id, f, "Valor numérico inválido."))
    if "units_on" in state and state["units_on"] is not None and (
            not isinstance(state["units_on"], int) or isinstance(state["units_on"], bool)):
        out.append(Finding(ERROR, eq_id, "units_on", "Número de unidades em operação deve ser inteiro."))
    if "state" in state and state["state"] is not None and state["state"] not in DISPATCH_STATES:
        out.append(Finding(ERROR, eq_id, "state", "Estado operativo inválido."))
    return out


def _battery(eq_id: str, s: dict, ref: dict) -> list[Finding]:
    out: list[Finding] = []
    soc = _num(s.get("soc0_pct"))
    if soc is None:
        return [Finding(INCOMPLETE, eq_id, "soc0_pct", "SOC inicial não definido.")]
    if not 0.0 <= soc <= 100.0:
        return [Finding(ERROR, eq_id, "soc0_pct", f"SOC inicial {soc:g} % fora do limite físico (0–100 %).")]
    lo, hi, src = ref.get("soc_min_pct"), ref.get("soc_max_pct"), ref.get("soc_limits_source")
    if lo is not None and hi is not None and not lo - _EPS <= soc <= hi + _EPS:
        if src in SOC_OPERATIONAL_SOURCES:
            what = (f"da restrição operacional declarada no inventário [{lo:g}, {hi:g}] % "
                    f"({C.SOC_LIMIT_SOURCES.get(src, src).lower()})")
        else:
            what = f"do intervalo recomendado [{lo:g}, {hi:g}] % (valor sugerido pelo SEEDS2, não do fabricante)"
        out.append(Finding(WARNING, eq_id, "soc0_pct", f"SOC inicial {soc:g} % fora {what}. Permitido: "
                           "condição experimental deliberada."))
        out.append(Finding(PENDING, eq_id, "soc0_pct",
                           "O EMS V1.6 usa os limites de SOC do inventário como restrição efetiva do despacho: com SOC "
                           "inicial fora deles, o adaptador atual exclui o banco da rodada. Integração prevista para o "
                           "piso dedicado ao otimizador; o valor fica preservado no cenário."))
    if soc < EXTREME_SOC_PCT or soc > 100.0 - EXTREME_SOC_PCT:
        out.append(Finding(WARNING, eq_id, "soc0_pct", f"SOC inicial {soc:g} % próximo do extremo físico do banco."))
    if s.get("availability") == "indisponivel":
        out.append(Finding(PENDING, eq_id, "availability", "Indisponibilidade declarada no cenário ainda não é aplicada "
                           "pelo EMS V1.6 (a configuração salva determina o que entra na rodada)."))
    return out


def _pemfc(eq_id: str, s: dict, ref: dict) -> list[Finding]:
    out: list[Finding] = []
    state, units, power = s.get("state"), s.get("units_on"), _num(s.get("power_kW"))
    qty, unit_max = ref.get("quantity"), ref.get("unit_max_kW")
    if state is None:
        return [Finding(INCOMPLETE, eq_id, "state", "Estado operativo inicial não definido.")]
    if s.get("availability") == "indisponivel" and state != "desligada":
        out.append(Finding(ERROR, eq_id, "state", f"Sistema declarado indisponível não pode estar "
                           f"'{DISPATCH_STATES[state].lower()}' no instante inicial."))
    if power is not None and power < 0:
        out.append(Finding(ERROR, eq_id, "power_kW", "Potência inicial negativa."))
    if isinstance(units, int) and units < 0:
        out.append(Finding(ERROR, eq_id, "units_on", "Número de unidades em operação negativo."))
    if isinstance(units, int) and qty is not None and units > qty:
        out.append(Finding(ERROR, eq_id, "units_on", f"{units} unidade(s) em operação, mas o inventário registra "
                           f"{qty} instalada(s)."))
    if state == "desligada":
        if power is not None and power > _EPS:
            out.append(Finding(ERROR, eq_id, "power_kW", f"PEMFC declarada desligada não pode entregar {power:g} kW "
                               "no instante inicial."))
        if isinstance(units, int) and units > 0:
            out.append(Finding(ERROR, eq_id, "units_on", "PEMFC declarada desligada com unidades em operação."))
        return out
    if units is None:
        out.append(Finding(INCOMPLETE, eq_id, "units_on", "Número de unidades em operação não definido."))
    elif units == 0:
        out.append(Finding(ERROR, eq_id, "units_on", f"Estado '{DISPATCH_STATES[state].lower()}' exige ao menos uma "
                           "unidade em operação."))
    if state == "em_operacao" and power is None:
        out.append(Finding(INCOMPLETE, eq_id, "power_kW", "Potência inicial não definida."))
    if power is not None and power > _EPS and isinstance(units, int) and units > 0:
        if unit_max is not None and power > units * unit_max + 1e-6:
            out.append(Finding(ERROR, eq_id, "power_kW", f"Potência inicial {power:g} kW acima da potência máxima de "
                               f"{units} unidade(s) ({units * unit_max:.4g} kW, inventário)."))
        elif unit_max is None:
            out.append(Finding(WARNING, eq_id, "power_kW", "Potência máxima por unidade não conhecida no inventário: a "
                               "potência inicial não pôde ser verificada."))
    if state == "em_operacao" and power is not None and power <= _EPS:
        out.append(Finding(WARNING, eq_id, "power_kW", "Em operação sem entregar potência (operação em vazio)."))
    if state == "em_partida":
        out.append(Finding(WARNING, eq_id, "state", "O SEEDS2 não modela a física de partida da PEMFC: 'em partida' é "
                           "registrado apenas como rótulo de estado."))
    out.append(Finding(PENDING, eq_id, "state", "O EMS V1.6 não interpreta o estado inicial da PEMFC: o runtime assume "
                       "todas as unidades ligadas (n_ini = N_fc) e potência anterior nula."))
    return out


def _thermal(eq_id: str, s: dict, ref: dict) -> list[Finding]:
    out: list[Finding] = []
    state, power = s.get("state"), _num(s.get("power_kW"))
    pmax, pmin = ref.get("pmax_kW"), ref.get("pmin_kW")
    if state is None:
        return [Finding(INCOMPLETE, eq_id, "state", "Estado operativo inicial não definido.")]
    if s.get("availability") == "indisponivel" and state != "desligada":
        out.append(Finding(ERROR, eq_id, "state", f"Unidade declarada indisponível não pode estar "
                           f"'{THERMAL_STATES[state].lower()}' no instante inicial."))
    if power is not None and power < 0:
        out.append(Finding(ERROR, eq_id, "power_kW", "Potência inicial negativa."))
    if state == "desligada":
        if power is not None and power > _EPS:
            out.append(Finding(ERROR, eq_id, "power_kW", f"Unidade térmica declarada desligada não pode entregar "
                               f"{power:g} kW no instante inicial."))
        return out
    if state == "em_operacao" and power is None:
        out.append(Finding(INCOMPLETE, eq_id, "power_kW", "Potência inicial não definida."))
    if power is not None and pmax is not None and power > pmax + 1e-6:
        out.append(Finding(ERROR, eq_id, "power_kW", f"Potência inicial {power:g} kW acima da potência máxima "
                           f"registrada ({pmax:g} kW)."))
    if state == "em_operacao" and power is not None and pmin is not None and power < pmin - 1e-6:
        out.append(Finding(ERROR, eq_id, "power_kW", f"Em operação abaixo da potência mínima técnica registrada no "
                           f"inventário ({power:g} < {pmin:g} kW)."))
    if state == "em_partida":
        out.append(Finding(WARNING, eq_id, "state", "O SEEDS2 não modela tempos nem a física de partida da unidade "
                           "térmica: 'em partida' é registrado apenas como rótulo de estado."))
    out.append(Finding(PENDING, eq_id, "state", "O EMS V1.6 não interpreta o estado inicial da térmica: deriva-o da "
                       "potência mínima (n_ini = 1 se Pmin > 0) e começa com potência anterior nula."))
    return out


def _renewable(eq_id: str, s: dict, ref: dict) -> list[Finding]:
    if s.get("availability") == "indisponivel":
        return [Finding(PENDING, eq_id, "availability", "Indisponibilidade declarada no cenário ainda não é aplicada pelo "
                        "EMS V1.6 (a configuração salva determina o que entra na rodada).")]
    return []


_RULES = {"battery": _battery, "pemfc": _pemfc, "thermal": _thermal, "pv": _renewable, "wind": _renewable}


def validate_state(eq_id: str, kind: str, state: Any, ref: dict) -> list[Finding]:
    issues = structural_issues(eq_id, kind, state)
    if issues:
        return issues
    out = _RULES[kind](eq_id, state, ref)
    if kind in ("pemfc", "thermal") and state.get("availability") == "indisponivel" and state.get("state") == "desligada":
        out.append(Finding(PENDING, eq_id, "availability", "Indisponibilidade declarada no cenário ainda não é aplicada "
                           "pelo EMS V1.6 (a configuração salva determina o que entra na rodada)."))
    return out


def validate(initialization: dict, references: dict[str, dict]) -> list[Finding]:
    """Valida todos os estados iniciais contra as referências físicas (``inventory_ref.equipment``).

    * equipamento habilitado sem estado → ``incompleto``;
    * equipamento desabilitado no inventário → não exige estado (não entra na operação);
    * estado de equipamento inexistente na referência → erro (o cenário mantém estados órfãos em ``orphaned``);
    * entre bancos de baterias: SOC iniciais diferentes não são agregáveis pelo EMS V1.6 → pendência."""
    states = (initialization or {}).get("equipment") or {}
    out: list[Finding] = []
    for eq_id, st in states.items():
        if eq_id not in references:
            out.append(Finding(ERROR, eq_id, "", "Estado inicial para equipamento que não está no inventário de referência."))
    for eq_id, ref in references.items():
        if not ref.get("enabled", True):
            continue
        st = states.get(eq_id)
        if st is None:
            out.append(Finding(INCOMPLETE, eq_id, "", "Estado inicial ainda não definido."))
            continue
        out += validate_state(eq_id, ref["kind"], st, ref)
    socs = {round(float(states[e]["soc0_pct"]), 6) for e, r in references.items()
            if r.get("kind") == "battery" and r.get("enabled", True) and isinstance(states.get(e), dict)
            and _num(states[e].get("soc0_pct")) is not None}
    if len(socs) > 1:
        out.append(Finding(PENDING, None, "soc0_pct", "Bancos com SOC iniciais diferentes: o EMS V1.6 agrega bancos "
                           "idênticos com um único SOC inicial e marca configurações distintas como não representáveis. "
                           "Valores individuais preservados para integração futura."))
    return out


def summarize(findings: list[Finding]) -> dict[str, int]:
    out = {ERROR: 0, WARNING: 0, PENDING: 0, INCOMPLETE: 0}
    for f in findings:
        out[f.level] += 1
    return out


def by_equipment(findings: list[Finding]) -> dict[str | None, list[Finding]]:
    out: dict[str | None, list[Finding]] = {}
    for f in findings:
        out.setdefault(f.eq_id, []).append(f)
    return out


__all__ = ["AVAILABILITY", "DISPATCH_STATES", "ERROR", "FIELDS", "Finding", "INCOMPLETE", "KINDS", "KIND_LABELS",
           "LEVEL_LABELS", "PENDING", "THERMAL_STATES", "WARNING", "by_equipment", "default_state", "equipment_reference",
           "summarize", "validate", "validate_state"]
