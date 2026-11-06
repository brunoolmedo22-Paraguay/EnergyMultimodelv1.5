"""Previsões e Dados (Piso 2B) — séries temporais de entrada de um cenário operativo.

Uma previsão é uma descrição temporal de condições FUTURAS do experimento (demanda, clima). Não é medição do
estado inicial dos equipamentos (isso é a Inicialização) nem saída de modelo: nenhuma potência FV/eólica é
calculada aqui.

Princípios (ver ``PARAMIJEFE.md`` — Entrega 2):

* **Base temporal original preservada.** A série guardada mantém os instantes e a resolução dos dados de origem;
  nada é recortado para a janela da missão nem reamostrado para a grade de 1 min do EMS. A seleção do período
  experimental, a discretização do motor e o horizonte móvil pertencem ao Piso 2C.
* **Representação normalizada canônica** (``to_csv_bytes``): CSV UTF-8 ``timestamp,<variáveis>`` com instantes ISO
  8601 sem fuso (relógio de parede do fuso declarado na entrada) e valores em unidades canônicas (``VARIABLES``)
  escritos com ``repr(float)`` (ida e volta exata); célula vazia = ausente. Bytes determinísticos → SHA-256
  estável → integridade verificável e reprodutibilidade (``forecast_sources.rederive``).
* **Nada é preenchido em silêncio:** ausentes continuam ausentes (nunca zero), duplicatas exigem política explícita,
  fusos não declarados ficam identificados como tais, e toda transformação aplicada é registrada (``transforms``).
* Constatações nas mesmas categorias da Inicialização: ``erro`` (impede incorporar/salvar), ``aviso``
  (permitido), ``pendente`` (capacidade que o motor EMS V1.6 ainda não interpreta) e ``incompleto``.
"""
from __future__ import annotations

import io
import math
import re
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any, Callable, Mapping

import numpy as np
import pandas as pd

from .initialization import ERROR, INCOMPLETE, LEVEL_LABELS, PENDING, WARNING

FORMAT_VERSION = 1
EMS_STEP_S = 60                    # discretização atual do EMS V1.6 (Ts_min = 1) — apenas informada, nunca imposta
GAP_FACTOR = 1.5                   # intervalo > 1,5 × passo típico = intervalo ausente (descontinuidade)
MIN_POINTS = 2
SOLAR_CONSTANT_W_M2 = 1361.0       # irradiância no topo da atmosfera: acima disso, GHI provavelmente em outra unidade


@dataclass(frozen=True)
class Variable:
    key: str
    slot: str
    label: str
    unit: str
    short: str


# Ordem canônica das colunas da representação normalizada.
VARIABLES: dict[str, Variable] = {v.key: v for v in (
    Variable("demand_kW", "demand", "Demanda elétrica (potência)", "kW", "Demanda"),
    Variable("ghi_W_m2", "climate", "Irradiância global horizontal (GHI)", "W/m²", "GHI"),
    Variable("temperature_C", "climate", "Temperatura ambiente", "°C", "Temperatura"),
    Variable("wind_speed_m_s", "climate", "Velocidade do vento", "m/s", "Vento"),
    Variable("wind_direction_deg", "climate", "Direção do vento", "°", "Direção"),
    Variable("pressure_hPa", "climate", "Pressão atmosférica", "hPa", "Pressão"),
    Variable("humidity_pct", "climate", "Umidade relativa", "%", "Umidade"),
)}
SLOT_VARIABLES = {"demand": ("demand_kW",),
                  "climate": ("ghi_W_m2", "temperature_C", "wind_speed_m_s", "wind_direction_deg", "pressure_hPa",
                              "humidity_pct")}
EDITABLE_SLOTS = ("demand", "climate")        # "resources" permanece reservado (sem contrato científico consumidor)
ANGULAR = ("wind_direction_deg",)

# Conversões de unidade → unidade canônica: valor_canônico = valor × fator + deslocamento.
UNITS: dict[str, dict[str, tuple[float, float]]] = {
    "demand_kW": {"kW": (1.0, 0.0), "W": (1e-3, 0.0), "MW": (1e3, 0.0)},
    "ghi_W_m2": {"W/m²": (1.0, 0.0), "kW/m²": (1e3, 0.0)},
    "temperature_C": {"°C": (1.0, 0.0), "K": (1.0, -273.15), "°F": (5.0 / 9.0, -160.0 / 9.0)},
    "wind_speed_m_s": {"m/s": (1.0, 0.0), "km/h": (1.0 / 3.6, 0.0), "nó (kn)": (1852.0 / 3600.0, 0.0)},
    "wind_direction_deg": {"°": (1.0, 0.0)},
    "pressure_hPa": {"hPa": (1.0, 0.0), "mbar": (1.0, 0.0), "kPa": (10.0, 0.0), "Pa": (0.01, 0.0)},
    "humidity_pct": {"%": (1.0, 0.0), "fração (0–1)": (100.0, 0.0)},
}
# Sufixos de cabeçalho que identificam a unidade sem ambiguidade (nome normalizado: minúsculas, '_').
_UNIT_SUFFIX: dict[str, tuple[tuple[str, str], ...]] = {
    "demand_kW": (("_kw", "kW"), ("_mw", "MW"), ("_w", "W")),
    "ghi_W_m2": (("_kw_m2", "kW/m²"), ("_kw_m_2", "kW/m²"), ("_w_m2", "W/m²"), ("_w_m_2", "W/m²"), ("_wm2", "W/m²")),
    "temperature_C": (("_degc", "°C"), ("_celsius", "°C"), ("_c", "°C"), ("_kelvin", "K"), ("_k", "K"),
                      ("_degf", "°F"), ("_f", "°F")),
    "wind_speed_m_s": (("_mps", "m/s"), ("_m_s", "m/s"), ("_kmh", "km/h"), ("_km_h", "km/h"), ("_knots", "nó (kn)"),
                       ("_kn", "nó (kn)"), ("_kt", "nó (kn)")),
    "wind_direction_deg": (("_deg", "°"), ("_graus", "°"), ("_grados", "°")),
    "pressure_hPa": (("_hpa", "hPa"), ("_mbar", "mbar"), ("_kpa", "kPa"), ("_pa", "Pa")),
    "humidity_pct": (("_pct", "%"), ("_percent", "%"), ("_porcento", "%")),
}
DUPLICATE_POLICIES = {"recusar": "Recusar (corrigir o arquivo)", "primeira": "Manter a primeira ocorrência",
                      "ultima": "Manter a última ocorrência", "media": "Média das ocorrências"}
TECH_VARIABLES = {
    # tecnologia → (obrigatórias, opcionais) para os modelos existentes (V1.6), sem reformulá-los:
    # FV: modelo NOCT + eficiência (G, Tamb) — orchestrator_runtime._simulate_solar;
    # eólica: velocidade obrigatória; direção, temperatura, pressão e umidade opcionais (densidade do ar com
    # retorno à densidade de referência) — models/wind_model.prepare_wind_profile/calculate_air_density.
    "pv": (("ghi_W_m2", "temperature_C"), ()),
    "wind": (("wind_speed_m_s",), ("wind_direction_deg", "temperature_C", "pressure_hPa", "humidity_pct")),
}
TECH_LABELS = {"pv": "Solar fotovoltaica", "wind": "Eólica"}


class ForecastDataError(ValueError):
    """Dados de previsão ilegíveis, ausentes ou corrompidos (mensagem apresentável)."""


@dataclass(frozen=True)
class Finding:
    level: str
    variable: str | None
    code: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Analysis:
    findings: list[Finding] = field(default_factory=list)
    temporal: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        out = {ERROR: 0, WARNING: 0, PENDING: 0, INCOMPLETE: 0}
        for f in self.findings:
            out[f.level] += 1
        return out

    @property
    def ok(self) -> bool:
        return not any(f.level == ERROR for f in self.findings)


# ====================================================================== requisitos a partir do inventário
def technologies(inventory_ref: Mapping) -> dict[str, list[str]]:
    """Tecnologias renováveis HABILITADAS no inventário de referência do cenário → nomes dos equipamentos."""
    out: dict[str, list[str]] = {}
    for ref in sorted((inventory_ref.get("equipment") or {}).values(), key=lambda r: r.get("position", 1 << 30)):
        if ref.get("kind") in TECH_VARIABLES and ref.get("enabled", True):
            out.setdefault(ref["kind"], []).append(ref.get("name") or ref["kind"])
    return out


def climate_requirements(inventory_ref: Mapping) -> dict[str, dict]:
    """Variável climática → {"required": bool, "techs": [...]} (apenas as pertinentes aos equipamentos)."""
    techs = technologies(inventory_ref)
    out: dict[str, dict] = {}
    for tech in ("pv", "wind"):
        if tech not in techs:
            continue
        req, opt = TECH_VARIABLES[tech]
        for v in req + opt:
            e = out.setdefault(v, {"required": False, "techs": []})
            e["required"] = e["required"] or v in req
            e["techs"].append(tech)
    return {k: out[k] for k in SLOT_VARIABLES["climate"] if k in out}


def required_variables(slot: str, inventory_ref: Mapping) -> tuple[str, ...]:
    if slot == "demand":
        return ("demand_kW",)
    return tuple(k for k, v in climate_requirements(inventory_ref).items() if v["required"])


def relevant_variables(slot: str, inventory_ref: Mapping) -> tuple[str, ...]:
    if slot == "demand":
        return ("demand_kW",)
    return tuple(climate_requirements(inventory_ref))


# ====================================================================== unidades e colunas
def normalize_name(value: Any) -> str:
    from simulation.mix_engine import _normalize_name      # mesma normalização de cabeçalhos do MIX V1.6

    return _normalize_name(value)


def detect_unit(variable: str, header: Any) -> str | None:
    """Unidade inequivocamente indicada pelo cabeçalho (sufixo), ou ``None`` (o usuário deve confirmá-la)."""
    name = "_" + normalize_name(header)
    for suffix, unit in _UNIT_SUFFIX.get(variable, ()):
        if name.endswith(suffix):
            return unit
    return None


def convert(variable: str, values: np.ndarray, unit: str) -> np.ndarray:
    factor, offset = UNITS[variable][unit]
    return np.asarray(values, dtype=float) * factor + offset


def numeric(series: pd.Series) -> pd.Series:
    """Conversão numérica tolerante a vírgula decimal (mesma regra do MIX V1.6). Não numérico → NaN."""
    from simulation.mix_engine import _numeric

    return _numeric(series)


# ====================================================================== fusos horários
# Deslocamento de fuso APÓS um horário (evita confundir "21-03-2026" com "-2026").
_OFFSET_RE = re.compile(r"\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?\s*(Z|[+-]\d{2}:?\d{2})$")


def valid_timezone(tz: str | None) -> bool:
    if tz is None:
        return True
    if tz == "UTC" or re.fullmatch(r"UTC[+-]\d{2}:\d{2}", tz):
        return True
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(tz)
        return True
    except Exception:
        return False


def offset_label(minutes: int) -> str:
    if minutes == 0:
        return "UTC"
    sign = "+" if minutes > 0 else "-"
    m = abs(int(minutes))
    return f"UTC{sign}{m // 60:02d}:{m % 60:02d}"


# ====================================================================== instantes
DATE_ORDERS = {"auto": "Automático (ISO 8601 ou formato inequívoco)", "dia_mes": "Dia/mês/ano", "mes_dia": "Mês/dia/ano"}
_DM = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d.%m.%Y %H:%M:%S",
       "%d.%m.%Y %H:%M", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y")
_MD = tuple(f.replace("%d", "§").replace("%m", "%d").replace("§", "%m") for f in _DM)


def _try_formats(s: pd.Series, formats: tuple[str, ...]) -> pd.Series | None:
    for fmt in formats:
        out = pd.to_datetime(s, format=fmt, errors="coerce")
        if out.notna().all():
            return out
    return None


@dataclass
class ParsedTime:
    ts: pd.Series | None                 # instantes ingênuos (relógio de parede do fuso indicado)
    timezone: str | None = None
    timezone_source: str = "nao_declarado"   # arquivo | arquivo_utc | usuario | nao_declarado
    findings: list[Finding] = field(default_factory=list)
    transforms: list[str] = field(default_factory=list)
    detected_order: str | None = None


def _rows(mask: np.ndarray, limit: int = 4) -> str:
    idx = np.flatnonzero(mask)[:limit] + 2              # +1 (base 1) +1 (cabeçalho)
    more = "…" if int(mask.sum()) > limit else ""
    return ", ".join(str(i) for i in idx) + more


def parse_absolute(values: pd.Series, *, date_order: str = "auto", timezone: str | None = None) -> ParsedTime:
    """Instantes absolutos. Com deslocamento explícito no texto (``Z``/``±hh:mm``) o fuso vem do ARQUIVO; sem ele,
    do ``timezone`` declarado pelo usuário (``None`` = não declarado, identificado como tal)."""
    s = values.astype(str).str.strip()
    s = s.where(~values.isna(), "")
    has_off = s.map(lambda x: bool(_OFFSET_RE.search(x)))
    out = ParsedTime(ts=None)
    if has_off.any() and not has_off.all():
        out.findings.append(Finding(ERROR, None, "fuso_misto",
                                    f"Instantes com e sem fuso horário misturados (linhas sem fuso: {_rows(~has_off.to_numpy())})."))
        return out
    if has_off.all() and len(s):
        parsed = pd.to_datetime(s, format="ISO8601", errors="coerce", utc=True)
        bad = parsed.isna().to_numpy()
        if bad.any():
            out.findings.append(Finding(ERROR, None, "timestamp_invalido",
                                        f"{int(bad.sum())} instante(s) inválido(s) (linhas {_rows(bad)})."))
            return out
        offsets = set()
        for txt in s:
            m = _OFFSET_RE.search(txt).group(1)
            offsets.add(0 if m == "Z" else (1 if m[0] == "+" else -1) * (int(m[1:3]) * 60 + int(m[-2:])))
        if len(offsets) == 1:
            off = offsets.pop()
            out.ts = (parsed + pd.Timedelta(minutes=off)).dt.tz_localize(None)
            out.timezone, out.timezone_source = offset_label(off), "arquivo"
        else:
            out.ts = parsed.dt.tz_localize(None)
            out.timezone, out.timezone_source = "UTC", "arquivo_utc"
            out.transforms.append(f"Instantes com {len(offsets)} deslocamentos de fuso distintos (p. ex. horário de "
                                  "verão) convertidos para UTC.")
        if timezone not in (None, out.timezone):
            out.findings.append(Finding(WARNING, None, "fuso_ignorado",
                                        f"O arquivo declara o fuso {out.timezone}; o fuso escolhido ({timezone}) não foi aplicado."))
        out.detected_order = "iso"
        return out
    # Instantes sem fuso: formato ISO ou ordem de data explícita.
    iso = pd.to_datetime(s, format="ISO8601", errors="coerce")
    if date_order == "auto" and iso.notna().all() and len(s):
        out.ts, out.detected_order = iso, "iso"
    elif date_order in ("dia_mes", "mes_dia"):
        got = _try_formats(s, _DM if date_order == "dia_mes" else _MD)
        if got is None and iso.notna().all():
            got = iso
        if got is None:
            bad = (_best_effort(s, date_order)).isna().to_numpy()
            out.findings.append(Finding(ERROR, None, "timestamp_invalido",
                                        f"{int(bad.sum()) or len(s)} instante(s) não interpretável(is) como "
                                        f"{DATE_ORDERS[date_order].lower()} (linhas {_rows(bad if bad.any() else np.ones(len(s), bool))})."))
            return out
        out.ts, out.detected_order = got, date_order
    else:
        dm, md = _try_formats(s, _DM), _try_formats(s, _MD)
        if dm is not None and md is not None and not dm.equals(md):
            out.findings.append(Finding(ERROR, None, "data_ambigua",
                                        "Datas ambíguas (dia/mês ou mês/dia): escolha a ordem da data no mapeamento."))
            return out
        got = dm if dm is not None else md
        if got is None:
            bad = iso.isna().to_numpy()
            out.findings.append(Finding(ERROR, None, "timestamp_invalido",
                                        f"{int(bad.sum())} instante(s) inválido(s) ou em formato não reconhecido "
                                        f"(linhas {_rows(bad)}). Use ISO 8601 (AAAA-MM-DD HH:MM[:SS]) ou escolha a ordem da data."))
            return out
        out.ts, out.detected_order = got, ("dia_mes" if dm is not None else "mes_dia")
    out.timezone = timezone
    out.timezone_source = "usuario" if timezone else "nao_declarado"
    return out


def _best_effort(s: pd.Series, order: str) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", dayfirst=(order == "dia_mes"), format="mixed")


TIME_UNITS_S = {"s": 1.0, "min": 60.0, "h": 3600.0}


def parse_relative(values: pd.Series, *, unit: str, t0: str | None, timezone: str | None) -> ParsedTime:
    """Tempo relativo (p. ex. ``t_min``): exige o instante inicial explícito (nada de data presumida)."""
    out = ParsedTime(ts=None)
    if not t0:
        out.findings.append(Finding(ERROR, None, "sem_referencia",
                                    "Dados com tempo relativo e sem referência temporal: informe a data e a hora do "
                                    "instante inicial (t = 0)."))
        return out
    try:
        base = pd.Timestamp(t0)
    except (ValueError, TypeError):
        out.findings.append(Finding(ERROR, None, "t0_invalido", f"Instante inicial inválido: {str(t0)[:40]!r}."))
        return out
    if base.tzinfo is not None:
        out.findings.append(Finding(ERROR, None, "t0_invalido", "Informe o instante inicial sem fuso; o fuso é declarado à parte."))
        return out
    num = numeric(values).to_numpy(dtype=float)
    bad = ~np.isfinite(num)
    if bad.any():
        out.findings.append(Finding(ERROR, None, "tempo_invalido",
                                    f"{int(bad.sum())} valor(es) de tempo relativo inválido(s) (linhas {_rows(bad)})."))
        return out
    out.ts = pd.Series(base + pd.to_timedelta(num * TIME_UNITS_S[unit], unit="s"))
    out.timezone, out.timezone_source = timezone, ("usuario" if timezone else "nao_declarado")
    out.transforms.append(f"Tempo relativo ({unit}) convertido em instantes a partir de {base.isoformat()}.")
    return out


# ====================================================================== série normalizada
@dataclass
class Normalized:
    df: pd.DataFrame | None                    # timestamp + variáveis canônicas (ordem canônica)
    timezone: str | None
    timezone_source: str
    findings: list[Finding]
    transforms: list[str]
    detected_order: str | None = None


def assemble(parsed: ParsedTime, columns: Mapping[str, np.ndarray], *, duplicates: str = "recusar",
             conversions: Mapping[str, str] | None = None) -> Normalized:
    """Monta a série a partir dos instantes já interpretados e das colunas JÁ em unidade canônica: ordena (registrado),
    aplica a política explícita de duplicatas e preserva ausentes como NaN."""
    findings, transforms = list(parsed.findings), list(parsed.transforms)
    if parsed.ts is None:
        return Normalized(None, parsed.timezone, parsed.timezone_source, findings, transforms, parsed.detected_order)
    for var, unit in (conversions or {}).items():
        if unit != VARIABLES[var].unit:
            transforms.append(f"{VARIABLES[var].short}: unidade {unit} convertida para {VARIABLES[var].unit}.")
    keys = [k for k in VARIABLES if k in columns]
    df = pd.DataFrame({"timestamp": pd.to_datetime(parsed.ts).reset_index(drop=True)})
    for k in keys:
        df[k] = np.asarray(columns[k], dtype=float)
    if len(df) and not df["timestamp"].is_monotonic_increasing:
        df = df.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
        transforms.append("Linhas reordenadas cronologicamente (o arquivo não estava em ordem crescente de tempo).")
        findings.append(Finding(WARNING, None, "fora_de_ordem", "Os instantes não estavam em ordem cronológica; as linhas "
                                                                "foram reordenadas (registrado nas transformações)."))
    dup = df["timestamp"].duplicated(keep=False).to_numpy()
    if dup.any():
        n_ts = int(df.loc[dup, "timestamp"].nunique())
        examples = ", ".join(t.isoformat(sep=" ") for t in df.loc[dup, "timestamp"].drop_duplicates()[:3])
        if duplicates == "recusar":
            findings.append(Finding(ERROR, None, "duplicados",
                                    f"{n_ts} instante(s) repetido(s) ({examples}{'…' if n_ts > 3 else ''}). Escolha "
                                    "explicitamente como tratá-los (primeira, última ou média) ou corrija os dados."))
            return Normalized(df, parsed.timezone, parsed.timezone_source, findings, transforms, parsed.detected_order)
        if duplicates in ("primeira", "ultima"):
            df = df.drop_duplicates("timestamp", keep="first" if duplicates == "primeira" else "last").reset_index(drop=True)
        else:
            agg = {k: (_circular_mean if k in ANGULAR else "mean") for k in keys}
            df = df.groupby("timestamp", sort=True, as_index=False).agg(agg) if keys else df.drop_duplicates("timestamp")
            df = df.reset_index(drop=True)
        transforms.append(f"{n_ts} instante(s) repetido(s) tratado(s): {DUPLICATE_POLICIES[duplicates].lower()}"
                          + (" (direção do vento: média circular)" if duplicates == "media" and "wind_direction_deg" in keys else "")
                          + ".")
        findings.append(Finding(WARNING, None, "duplicados_tratados",
                                f"{n_ts} instante(s) repetido(s) tratado(s) pela política escolhida "
                                f"({DUPLICATE_POLICIES[duplicates].lower()})."))
    return Normalized(df[["timestamp", *keys]], parsed.timezone, parsed.timezone_source, findings, transforms,
                      parsed.detected_order)


def _circular_mean(x: pd.Series) -> float:
    v = np.deg2rad(x.to_numpy(dtype=float))
    v = v[np.isfinite(v)]
    if v.size == 0:
        return float("nan")
    return float(np.rad2deg(np.arctan2(np.sin(v).mean(), np.cos(v).mean())) % 360.0)


# ====================================================================== análise de qualidade
def _fmt(v: float, nd: int = 2) -> str:
    return f"{v:,.{nd}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_duration(seconds: float) -> str:
    s = float(seconds)
    if s < 60 or (s < 120 and s % 60):
        return f"{_fmt(s, 0 if s == int(s) else 1)} s"
    if s < 2 * 3600:
        return f"{_fmt(s / 60, 1 if s % 60 else 0)} min"
    if s < 2 * 86400:
        return f"{_fmt(s / 3600, 2 if s % 3600 else 0)} h"
    return f"{_fmt(s / 86400, 0 if s % 86400 == 0 else 2)} dias"


def gap_mask(ts: pd.Series) -> tuple[np.ndarray, float]:
    """``mask[i]`` verdadeiro se o intervalo (i → i+1) é uma descontinuidade (> GAP_FACTOR × passo típico)."""
    t = pd.to_datetime(ts).to_numpy(dtype="datetime64[ns]").astype("int64") / 1e9
    if t.size < 2:
        return np.zeros(0, bool), float("nan")
    d = np.diff(t)
    step = float(np.median(d[d > 0])) if (d > 0).any() else float("nan")
    return (d > GAP_FACTOR * step) if math.isfinite(step) else np.zeros(d.size, bool), step


def analyze(df: pd.DataFrame | None, slot: str, *, required: tuple[str, ...] = (), relevant: tuple[str, ...] = (),
            timezone: str | None = None) -> Analysis:
    """Qualidade e resumo temporal de uma série normalizada (sem modificá-la)."""
    a = Analysis()
    if df is None:
        return a
    keys = [k for k in df.columns if k != "timestamp"]
    n = len(df)
    if n < MIN_POINTS:
        a.findings.append(Finding(ERROR, None, "poucos_pontos", f"São necessárias pelo menos {MIN_POINTS} observações "
                                                               f"(encontrada(s): {n})."))
    if not keys:
        a.findings.append(Finding(ERROR, None, "sem_variaveis", "Nenhuma variável mapeada."))
    for k in keys:
        if VARIABLES[k].slot != slot:
            a.findings.append(Finding(ERROR, k, "variavel_de_outro_slot", f"{VARIABLES[k].label} não pertence a esta previsão."))
    for k in required:
        if k not in keys:
            a.findings.append(Finding(INCOMPLETE, k, "obrigatoria_ausente",
                                      f"{VARIABLES[k].label} ({VARIABLES[k].unit}) é necessária para os equipamentos "
                                      "instalados e não foi fornecida."))
    for k in keys:
        if slot == "climate" and relevant and k not in relevant:
            a.findings.append(Finding(WARNING, k, "variavel_sem_uso",
                                      f"{VARIABLES[k].label}: nenhuma tecnologia habilitada no inventário de referência a "
                                      "utiliza (mantida apenas como registro)."))
    if n == 0:
        return a
    ts = pd.to_datetime(df["timestamp"])
    t_ns = ts.to_numpy(dtype="datetime64[ns]").astype("int64")
    gaps, step = gap_mask(ts)
    d = np.diff(t_ns) / 1e9
    a.temporal = {"start": ts.iloc[0].isoformat(), "end": ts.iloc[-1].isoformat(), "n_points": n,
                  "duration_s": float((t_ns[-1] - t_ns[0]) / 1e9), "step_s": step if math.isfinite(step) else None,
                  "step_min_s": float(d.min()) if d.size else None, "step_max_s": float(d.max()) if d.size else None,
                  "regular": bool(d.size and np.allclose(d, step, rtol=0, atol=1e-3)),
                  "gaps": int(gaps.sum()), "largest_gap_s": float(d[gaps].max()) if gaps.any() else 0.0,
                  "timezone": timezone}
    if d.size and (d <= 0).any():                     # não deveria ocorrer após ``assemble`` (defesa)
        a.findings.append(Finding(ERROR, None, "ordem", "Instantes repetidos ou fora de ordem após a normalização."))
    if timezone is None:
        a.findings.append(Finding(WARNING, None, "fuso_nao_declarado",
                                  "Fuso horário não declarado: os instantes são relógio de parede sem referência "
                                  "(UTC/offset). Alinhamentos futuros com outras séries assumirão o mesmo relógio."))
    if gaps.any():
        idx = np.flatnonzero(gaps)
        first = ts.iloc[int(idx[0])]
        a.findings.append(Finding(WARNING, None, "intervalos_ausentes",
                                  f"{int(gaps.sum())} intervalo(s) ausente(s) (descontinuidade > {GAP_FACTOR:g} × passo "
                                  f"típico de {fmt_duration(step)}); o maior tem {fmt_duration(a.temporal['largest_gap_s'])} "
                                  f"(primeiro após {first.isoformat(sep=' ')}). Nada foi preenchido."))
    elif d.size and not a.temporal["regular"]:
        a.findings.append(Finding(WARNING, None, "resolucao_irregular",
                                  f"Resolução temporal irregular: passos de {fmt_duration(d.min())} a {fmt_duration(d.max())}."))
    if math.isfinite(step) and abs(step - EMS_STEP_S) > 1e-6:
        sense = "mais grossa" if step > EMS_STEP_S else "mais fina"
        a.findings.append(Finding(PENDING, None, "grade_ems",
                                  f"Resolução de {fmt_duration(step)}, {sense} que a discretização de 1 min do EMS V1.6. "
                                  "A conversão para a grade do motor (método e janela) será definida pelo runner do "
                                  "Piso 2C; os dados originais são preservados."))
    for k in keys:
        v = df[k].to_numpy(dtype=float)
        a.stats[k] = _stats(ts, v, k, gaps)
        a.findings += _value_findings(k, v, required=(k in required) or slot == "demand")
    return a


def _stats(ts: pd.Series, v: np.ndarray, key: str, gaps: np.ndarray) -> dict:
    fin = np.isfinite(v)
    out: dict[str, Any] = {"n_valid": int(fin.sum()), "missing": int(np.isnan(v).sum()),
                           "non_finite": int(np.isinf(v).sum())}
    if fin.any():
        vf = v.copy()
        vf[~fin] = np.nan
        imin, imax = int(np.nanargmin(vf)), int(np.nanargmax(vf))
        out.update(min=float(vf[imin]), max=float(vf[imax]), mean=float(np.nanmean(vf)),
                   t_min=ts.iloc[imin].isoformat(), t_max=ts.iloc[imax].isoformat())
        if key in ANGULAR:
            out["mean"] = _circular_mean(pd.Series(v))
        dv = np.diff(vf)
        valid = np.isfinite(dv) & ~gaps
        if key not in ANGULAR and valid.any():
            j = int(np.flatnonzero(valid)[np.argmax(np.abs(dv[valid]))])
            out["max_jump"] = float(dv[j])
            out["t_max_jump"] = ts.iloc[j + 1].isoformat()
    if key == "demand_kW":
        out["energy_kWh"] = energy_kWh(ts, v, gaps)
    return out


def energy_kWh(ts: pd.Series, p_kW: np.ndarray, gaps: np.ndarray | None = None) -> float | None:
    """Energia estimada (kWh) = integral trapezoidal da POTÊNCIA (kW) no tempo real dos instantes. Intervalos
    ausentes (descontinuidades) e intervalos com extremo ausente NÃO são integrados (nada é presumido)."""
    t = pd.to_datetime(ts).to_numpy(dtype="datetime64[ns]").astype("int64") / 3.6e12     # horas
    p = np.asarray(p_kW, dtype=float)
    if p.size < 2:
        return None
    dt = np.diff(t)
    ok = np.isfinite(p[:-1]) & np.isfinite(p[1:])
    if gaps is not None and gaps.size == ok.size:
        ok &= ~gaps
    if not ok.any():
        return None
    return float(np.sum(0.5 * (p[:-1] + p[1:])[ok] * dt[ok]))


def _value_findings(k: str, v: np.ndarray, *, required: bool) -> list[Finding]:
    out: list[Finding] = []
    lab = VARIABLES[k].label
    inf = np.isinf(v)
    nan = np.isnan(v)
    if inf.any():
        out.append(Finding(ERROR, k, "nao_finito", f"{lab}: {int(inf.sum())} valor(es) infinito(s) (linhas {_rows(inf)})."))
    if nan.any():
        msg = (f"{lab}: {int(nan.sum())} valor(es) ausente(s) ou não numérico(s) (linhas {_rows(nan)}). Ausentes não "
               "são preenchidos com zero.")
        out.append(Finding(ERROR if required else WARNING, k, "ausentes", msg + ("" if not required else
                                                                               " Variável obrigatória: corrija os dados.")))
    f = v[np.isfinite(v)]
    if f.size == 0:
        return out

    def chk(mask: np.ndarray, level: str, code: str, msg: str) -> None:
        if mask.any():
            out.append(Finding(level, k, code, f"{lab}: {int(mask.sum())} valor(es) {msg}"))

    if k == "demand_kW":
        chk(f < 0, ERROR, "negativo", "negativo(s): a demanda é potência consumida (≥ 0).")
    elif k == "ghi_W_m2":
        chk(f < 0, ERROR, "negativo", "negativo(s): irradiância não pode ser negativa.")
        chk(f > SOLAR_CONSTANT_W_M2, WARNING, "acima_constante_solar",
            f"acima da constante solar ({SOLAR_CONSTANT_W_M2:g} W/m²): verifique a unidade.")
    elif k == "wind_speed_m_s":
        chk(f < 0, ERROR, "negativo", "negativo(s): velocidade do vento não pode ser negativa.")
        chk(f > 60, WARNING, "implausivel", "acima de 60 m/s: verifique a unidade (km/h? nós?).")
    elif k == "wind_direction_deg":
        chk((f < 0) | (f > 360), ERROR, "fora_faixa", "fora de 0–360°.")
    elif k == "humidity_pct":
        chk((f < 0) | (f > 100), ERROR, "fora_faixa", "fora de 0–100 %.")
    elif k == "pressure_hPa":
        chk(f <= 0, ERROR, "nao_positivo", "não positivo(s): pressão absoluta deve ser > 0.")
        chk((f > 0) & ((f < 500) | (f > 1100)), WARNING, "implausivel", "fora de 500–1100 hPa: verifique a unidade (Pa? kPa?).")
    elif k == "temperature_C":
        chk(f < -273.15, ERROR, "abaixo_zero_absoluto", "abaixo do zero absoluto (−273,15 °C).")
        chk((f >= -273.15) & ((f < -60) | (f > 60)), WARNING, "implausivel",
            "fora de −60…60 °C: verifique a unidade (K? °F?).")
    return out


# ====================================================================== representação canônica (blob)
def _ts_text(t: pd.Timestamp) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S") + (f".{t.microsecond:06d}" if t.microsecond else "")


def _num_text(x: float) -> str:
    return "" if math.isnan(x) else repr(float(x))


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Bytes canônicos e determinísticos da série normalizada (ver docstring do módulo)."""
    keys = [k for k in VARIABLES if k in df.columns]
    lines = [",".join(["timestamp", *keys])]
    cols = [df[k].to_numpy(dtype=float) for k in keys]
    for i, t in enumerate(pd.to_datetime(df["timestamp"])):
        lines.append(",".join([_ts_text(t), *(_num_text(c[i]) for c in cols)]))
    return ("\n".join(lines) + "\n").encode("utf-8")


def from_csv_bytes(data: bytes) -> pd.DataFrame:
    try:
        raw = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
    except Exception as exc:                                    # noqa: BLE001 — mensagem apresentável
        raise ForecastDataError(f"Série normalizada ilegível: {exc}") from None
    if not len(raw.columns) or raw.columns[0] != "timestamp" or any(c not in VARIABLES for c in raw.columns[1:]):
        raise ForecastDataError("Série normalizada com cabeçalho inesperado.")
    df = pd.DataFrame({"timestamp": pd.to_datetime(raw["timestamp"], format="ISO8601")})
    for k in raw.columns[1:]:
        df[k] = [float(x) if x != "" else float("nan") for x in raw[k]]
    return df


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


# ====================================================================== entrada do cenário
@dataclass
class Candidate:
    """Entrada pendente (pré-visualização) — ainda NÃO incorporada ao cenário."""
    slot: str
    entry: dict | None
    df: pd.DataFrame | None
    analysis: Analysis
    blobs: dict[str, tuple[bytes, dict]] = field(default_factory=dict)
    transforms: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.entry is not None and self.analysis.ok


def build(slot: str, norm: Normalized, *, source_type: str, provenance: str, label: str, inventory_ref: Mapping,
          params: dict | None = None, mapping: dict | None = None, original: tuple[bytes, dict] | None = None,
          notes: str = "") -> Candidate:
    """Análise + entrada (``contracts.ForecastInput``) + blobs (normalizado e, se houver, original)."""
    an = analyze(norm.df, slot, required=required_variables(slot, inventory_ref),
                 relevant=relevant_variables(slot, inventory_ref), timezone=norm.timezone)
    an.findings = list(norm.findings) + an.findings
    cand = Candidate(slot, None, norm.df, an, transforms=list(norm.transforms))
    if norm.df is None or not an.ok:
        return cand
    from seeds2.microgrid import config as C

    data = to_csv_bytes(norm.df)
    h = digest(data)
    cand.blobs[h] = (data, {"name": f"previsao-{slot}-normalizada.csv", "media_type": "text/csv"})
    orig = None
    if original is not None:
        content, meta = original
        orig = digest(content)
        cand.blobs[orig] = (content, {"name": str(meta.get("name") or "original.csv")[:200],
                                      "media_type": str(meta.get("media_type") or "text/csv")})
    t = an.temporal
    cand.entry = {
        "slot": slot, "format_version": FORMAT_VERSION, "source_type": source_type, "provenance": provenance,
        "label": str(label)[:300], "variables": [k for k in VARIABLES if k in norm.df.columns],
        "t0": t["start"], "t_end": t["end"], "step_s": t["step_s"], "horizon_s": t["duration_s"],
        "n_points": t["n_points"], "regular": t["regular"],
        "timezone": norm.timezone, "timezone_source": norm.timezone_source,
        "data": h, "blob": orig, "params": params or {}, "mapping": mapping, "transforms": list(norm.transforms),
        "quality": {**an.counts(), "items": [{"level": f.level, "variable": f.variable, "code": f.code,
                                               "message": f.message} for f in an.findings][:60]},
        "stats": an.stats, "notes": str(notes or "")[:2000], "created_at": C.utc_now(),
    }
    return cand


def entry_errors(slot: str, entry: Any) -> list[str]:
    """Completude de uma entrada GRAVÁVEL (além da validação estrutural de ``contracts.forecast_errors``)."""
    if slot not in EDITABLE_SLOTS:
        return [f"Previsão '{slot}': slot reservado; ainda sem contrato científico consumidor (não editável)."]
    if not isinstance(entry, dict):
        return [f"Previsão '{slot}' ilegível."]
    errs: list[str] = []
    p = f"Previsão '{slot}'"
    if entry.get("format_version") != FORMAT_VERSION:
        errs.append(f"{p}: formato de entrada não reconhecido.")
    if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("data") or "")):
        errs.append(f"{p}: série normalizada sem conteúdo armazenado (SHA-256).")
    vars_ = entry.get("variables")
    if not isinstance(vars_, list) or not vars_ or any(v not in SLOT_VARIABLES[slot] for v in vars_):
        errs.append(f"{p}: variáveis inválidas.")
    for k in ("t0", "t_end"):
        try:
            pd.Timestamp(str(entry.get(k)))
        except (ValueError, TypeError):
            errs.append(f"{p}: '{k}' inválido.")
    n = entry.get("n_points")
    if not isinstance(n, int) or isinstance(n, bool) or n < MIN_POINTS:
        errs.append(f"{p}: número de observações inválido.")
    if not valid_timezone(entry.get("timezone")):
        errs.append(f"{p}: fuso horário inválido.")
    q = entry.get("quality")
    if not isinstance(q, dict) or q.get(ERROR, 0) != 0:
        errs.append(f"{p}: a série contém erros de validação e não pode ser gravada.")
    st = entry.get("source_type")
    params = entry.get("params") if isinstance(entry.get("params"), dict) else {}
    if st == "csv" and not isinstance(entry.get("mapping"), dict):
        errs.append(f"{p}: CSV sem o mapeamento aplicado (necessário para a reprodução).")
    if st == "sintetico" and not (params.get("generator") and "generator_version" in params and "seed" in params):
        errs.append(f"{p}: perfil sintético sem gerador, versão e semente registrados.")
    if st == "referencia" and not params.get("dataset"):
        errs.append(f"{p}: perfil de referência sem identificação do conjunto.")
    if st in ("sintetico", "referencia") and entry.get("provenance") == "medido":
        errs.append(f"{p}: perfis sintéticos ou de referência nunca são medidos.")
    return errs


def referenced_blobs(doc: Any) -> set[str]:
    """SHA-256 referenciados pelas previsões de um documento de cenário (tolerante a estruturas inválidas)."""
    out: set[str] = set()
    fc = doc.get("forecasts") if isinstance(doc, dict) else None
    for entry in (fc.values() if isinstance(fc, dict) else []):
        if isinstance(entry, dict):
            for k in ("data", "blob"):
                v = entry.get(k)
                if isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v):
                    out.add(v)
    return out


def load(entry: Mapping, get_blob: Callable[[str], bytes]) -> pd.DataFrame:
    """Série normalizada de uma entrada gravada. Blob ausente/corrompido → ``ForecastDataError``."""
    try:
        data = get_blob(entry["data"])
    except Exception as exc:                                    # noqa: BLE001 — StoreError: ausente/corrompido
        raise ForecastDataError(f"Série da previsão indisponível: {exc}") from None
    if digest(data) != entry["data"]:
        raise ForecastDataError("Série da previsão corrompida (hash divergente).")
    df = from_csv_bytes(data)
    if list(df.columns[1:]) != list(entry.get("variables") or []) or len(df) != entry.get("n_points"):
        raise ForecastDataError("Série da previsão inconsistente com a entrada do cenário.")
    return df


# ====================================================================== visualização / preparação futura (2C)
def grid_view(df: pd.DataFrame, key: str, step_s: int = EMS_STEP_S) -> pd.DataFrame:
    """Série TRANSFORMADA para visualização na grade do EMS (1 min): interpolação linear dentro da cobertura
    (circular para a direção do vento), SEM extrapolação, e ausente dentro de descontinuidades ou junto a
    valores ausentes. Nunca substitui os dados originais."""
    ts = pd.to_datetime(df["timestamp"])
    if len(ts) < 2:
        return pd.DataFrame({"timestamp": ts, key: df[key]})
    t = ts.to_numpy(dtype="datetime64[ns]").astype("int64") / 1e9
    v = df[key].to_numpy(dtype=float)
    start = math.ceil(t[0] / step_s) * step_s
    grid = np.arange(start, t[-1] + 1e-9, step_s)
    gaps, _ = gap_mask(ts)
    j = np.clip(np.searchsorted(t, grid, side="right") - 1, 0, len(t) - 2)
    w = (grid - t[j]) / (t[j + 1] - t[j])
    a, b = v[j], v[j + 1]
    if key in ANGULAR:
        ra, rb = np.deg2rad(a), np.deg2rad(b)
        s = (1 - w) * np.sin(ra) + w * np.sin(rb)
        c = (1 - w) * np.cos(ra) + w * np.cos(rb)
        out = np.rad2deg(np.arctan2(s, c)) % 360.0
    else:
        out = (1 - w) * a + w * b
    at_a = np.abs(grid - t[j]) < 1e-6              # tolerância ABSOLUTA (instantes em segundos desde 1970)
    at_b = np.abs(grid - t[j + 1]) < 1e-6
    bad = (gaps[j] & ~(at_a | at_b)) | ~np.isfinite(a) | ~np.isfinite(b)
    bad &= ~(at_a & np.isfinite(a))
    bad &= ~(at_b & np.isfinite(b))
    out = np.where(at_a, a, np.where(at_b, b, out))
    out[bad] = np.nan
    return pd.DataFrame({"timestamp": pd.to_datetime(grid * 1e9), key: out})


def overlap(a: Mapping | None, b: Mapping | None) -> tuple[str, str] | None:
    """Período comum (início, fim) de duas entradas, ou ``None``."""
    if not a or not b:
        return None
    s, e = max(pd.Timestamp(a["t0"]), pd.Timestamp(b["t0"])), min(pd.Timestamp(a["t_end"]), pd.Timestamp(b["t_end"]))
    return (s.isoformat(), e.isoformat()) if s <= e else None


def scenario_findings(doc: Mapping) -> list[Finding]:
    """Constatações do conjunto de previsões do cenário (demanda × clima × inventário de referência)."""
    fc = doc.get("forecasts") or {}
    ref = doc.get("inventory_ref") or {}
    out: list[Finding] = []
    dem, cli = fc.get("demand"), fc.get("climate")
    if not dem:
        out.append(Finding(INCOMPLETE, "demand_kW", "sem_demanda", "Previsão de demanda não definida."))
    reqs = climate_requirements(ref)
    if reqs:
        if not cli:
            techs = ", ".join(TECH_LABELS[t] for t in technologies(ref))
            out.append(Finding(INCOMPLETE, None, "sem_clima", f"Previsão climática não definida ({techs} no inventário)."))
        else:
            missing = [k for k, r in reqs.items() if r["required"] and k not in (cli.get("variables") or [])]
            for k in missing:
                techs = ", ".join(TECH_LABELS[t] for t in reqs[k]["techs"])
                out.append(Finding(INCOMPLETE, k, "obrigatoria_ausente",
                                   f"{VARIABLES[k].label} ausente na previsão climática (necessária para {techs})."))
    if dem and cli:
        if (dem.get("timezone") or None) != (cli.get("timezone") or None):
            out.append(Finding(WARNING, None, "fusos_distintos",
                               f"Demanda e clima com fusos diferentes ({dem.get('timezone') or 'não declarado'} × "
                               f"{cli.get('timezone') or 'não declarado'}): o alinhamento será tratado no Piso 2C."))
        elif overlap(dem, cli) is None:
            out.append(Finding(WARNING, None, "sem_sobreposicao",
                               "Demanda e clima não têm período comum: uma simulação futura (Piso 2C) exigirá "
                               "sobreposição temporal."))
    return out


def stage_status(doc: Mapping) -> tuple[str, str, str]:
    """Estado da etapa Previsões para a prontidão do cenário (tom, rótulo, detalhe)."""
    fc = doc.get("forecasts") or {}
    errs = sum(int(((e or {}).get("quality") or {}).get(ERROR, 0)) for e in fc.values() if isinstance(e, dict))
    if errs:
        return "bad", "Com erros", f"{errs} erro(s) nos dados"
    fs = scenario_findings(doc)
    inc = [f for f in fs if f.level == INCOMPLETE]
    if inc:
        miss = [{"sem_demanda": "demanda", "sem_clima": "clima"}.get(f.code) or VARIABLES[f.variable].short
                for f in inc]
        return "warn", "Incompletas", "falta: " + ", ".join(miss)
    warns = sum(int(((e or {}).get("quality") or {}).get(WARNING, 0)) for e in fc.values() if isinstance(e, dict))
    warns += sum(1 for f in fs if f.level == WARNING)
    slots = " + ".join({"demand": "demanda", "climate": "clima"}[s] for s in EDITABLE_SLOTS if fc.get(s))
    return "ok", "Definidas", slots + (f" · {warns} aviso(s)" if warns else "")


__all__ = ["ANGULAR", "Analysis", "Candidate", "DATE_ORDERS", "DUPLICATE_POLICIES", "EDITABLE_SLOTS", "EMS_STEP_S",
           "FORMAT_VERSION", "Finding", "ForecastDataError", "LEVEL_LABELS", "Normalized", "ParsedTime", "SLOT_VARIABLES",
           "TECH_LABELS", "TIME_UNITS_S", "UNITS", "VARIABLES", "analyze", "assemble", "build", "climate_requirements",
           "convert", "detect_unit", "digest", "energy_kWh", "entry_errors", "fmt_duration", "from_csv_bytes", "gap_mask",
           "grid_view", "load", "numeric", "overlap", "parse_absolute", "parse_relative", "referenced_blobs",
           "relevant_variables", "required_variables", "scenario_findings", "stage_status", "technologies",
           "to_csv_bytes", "valid_timezone"]
