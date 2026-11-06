"""Janela da missão e preparação temporal das previsões (Piso 2C).

Separa explicitamente:

* **horizonte disponível** dos perfis (cobertura comum das séries necessárias, em UTC);
* **início e duração da missão** (bloco ``mission`` do cenário: relógio de parede + fuso declarado);
* **passo temporal da simulação** — 60 s, FIXO no runtime V1.6 (grade de 1 min; não é ampliado aqui);
* **horizonte móvel N** do otimizador (bloco ``ems_strategy``; não interfere na grade).

Regras:

* Todas as séries são convertidas para UTC ANTES de serem combinadas (fuso IANA com horário de verão, ``UTC``
  ou ``UTC±hh:mm``). Nunca se comparam relógios locais de fusos diferentes.
* Série sem fuso declarado: só é aceita se a missão também não declara fuso e — havendo mais de uma série — o
  usuário declarou EXPLICITAMENTE que elas compartilham o mesmo relógio (``undeclared_clock``), registrado na rodada.
  Mistura declarado × não declarado é recusada.
* Instantes ambíguos/inexistentes (mudança de horário) perto da janela → recusa.
* Conversão para a grade: amostras coincidentes são usadas sem transformação; entre amostras, interpolação
  LINEAR (circular para a direção do vento), sempre registrada. Sem extrapolação: a janela precisa estar dentro da
  cobertura de cada série. Dentro de uma descontinuidade (> 1,5 × passo típico) ou junto a um valor ausente o
  ponto da grade fica AUSENTE — e ausente em variável usada pelo modelo bloqueia a execução (nunca vira zero).
* As séries originais do cenário não são alteradas: a grade é um produto derivado gravado na rodada.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd

from . import forecasts as F
from . import strategy as SG

ERROR, WARNING, INFO = "erro", "aviso", "info"
# Variável canônica do cenário → coluna reconhecida por mix_engine.detect_climate_columns (runtime V1.6).
RUNTIME_CLIMATE = {"ghi_W_m2": "GHI", "temperature_C": "temperature_C", "wind_speed_m_s": "wind_speed_mps",
                   "wind_direction_deg": "wind_direction_deg", "pressure_hPa": "pressure_hPa", "humidity_pct": "humidity_pct"}
DST_MARGIN_S = 2 * 3600


@dataclass(frozen=True)
class Note:
    level: str
    code: str
    message: str

    def as_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "message": self.message}


@dataclass
class Series:
    slot: str
    entry: dict
    df: pd.DataFrame
    t_utc: np.ndarray            # segundos (UTC ou relógio não declarado), ordenados
    declared: bool
    notes: list[Note] = field(default_factory=list)
    bad_wall_s: np.ndarray = field(default_factory=lambda: np.zeros(0))   # instantes ambíguos (relógio de parede)


@dataclass
class Window:
    ok: bool
    notes: list[Note]
    timezone: str | None = None
    start_wall: pd.Timestamp | None = None
    start_utc: pd.Timestamp | None = None
    duration_min: int = 0
    grid_utc: pd.DatetimeIndex | None = None          # instantes reais (UTC ingênuo; ou relógio não declarado)
    grid_wall: pd.DatetimeIndex | None = None         # relógio de parede do fuso da missão (pode ser não uniforme)
    runtime_times: pd.DatetimeIndex | None = None     # grade UNIFORME entregue ao runtime (início local + k min)
    demand_kW: np.ndarray | None = None
    climate: dict[str, np.ndarray] = field(default_factory=dict)
    resampling: dict[str, dict] = field(default_factory=dict)
    horizon: dict | None = None

    def errors(self) -> list[Note]:
        return [n for n in self.notes if n.level == ERROR]


# ------------------------------------------------------------------ fusos
def _offset_minutes(tz: str) -> int | None:
    if tz == "UTC":
        return 0
    m = re.fullmatch(r"UTC([+-])(\d{2}):(\d{2})", tz)
    if m:
        return (1 if m.group(1) == "+" else -1) * (int(m.group(2)) * 60 + int(m.group(3)))
    return None


def _epoch_s(ts: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    return pd.DatetimeIndex(ts).to_numpy(dtype="datetime64[ns]").astype("int64") / 1e9


def wall_to_utc(ts: pd.Series, tz: str | None) -> tuple[np.ndarray, np.ndarray]:
    """Relógio de parede ingênuo → segundos UTC. Devolve (segundos, máscara de instantes ambíguos/inexistentes).
    ``tz=None``: o relógio não declarado é mantido como está (só comparável com séries do MESMO relógio)."""
    ts = pd.to_datetime(pd.Series(ts)).reset_index(drop=True)
    if tz is None:
        return _epoch_s(ts), np.zeros(len(ts), bool)
    off = _offset_minutes(tz)
    if off is not None:
        return _epoch_s(ts) - off * 60.0, np.zeros(len(ts), bool)
    loc = ts.dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
    bad = loc.isna().to_numpy()
    out = np.full(len(ts), np.nan)
    good = ~bad
    if good.any():
        out[good] = _epoch_s(loc[good].dt.tz_convert("UTC").dt.tz_localize(None))
    return out, bad


def utc_to_wall(utc_s: np.ndarray, tz: str | None) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(np.asarray(utc_s) * 1e9))
    if tz is None:
        return idx
    off = _offset_minutes(tz)
    if off is not None:
        return idx + pd.Timedelta(minutes=off)
    return idx.tz_localize("UTC").tz_convert(tz).tz_localize(None)


def tz_label(tz: str | None) -> str:
    return tz if tz else "fuso não declarado"


# ------------------------------------------------------------------ séries do cenário
def load_series(slot: str, entry: Mapping, get_blob) -> Series:
    """Série gravada (SHA-256 verificado por ``forecasts.load``) convertida para a referência temporal comum."""
    df = F.load(entry, get_blob)
    tz = entry.get("timezone")
    t, bad = wall_to_utc(df["timestamp"], tz)
    s = Series(slot, dict(entry), df, t, tz is not None)
    if bad.any():
        s.bad_wall_s = _epoch_s(df["timestamp"][bad])
        keep = ~bad
        s.df = df[keep].reset_index(drop=True)
        s.t_utc = t[keep]
    order = np.argsort(s.t_utc, kind="stable")
    if (np.diff(s.t_utc) < 0).any():       # horário de verão (relógio local) — a ordem real é a do UTC
        s.df = s.df.iloc[order].reset_index(drop=True)
        s.t_utc = s.t_utc[order]
    return s


def coverage(series: list[Series]) -> tuple[float, float] | None:
    """Período comum (segundos) das séries, ou ``None``."""
    if not series:
        return None
    lo = max(float(s.t_utc[0]) for s in series)
    hi = min(float(s.t_utc[-1]) for s in series)
    return (lo, hi) if lo <= hi else None


def resample(t: np.ndarray, v: np.ndarray, grid: np.ndarray, *, angular: bool = False) -> tuple[np.ndarray, dict]:
    """Valores da série nos instantes ``grid`` (todos em segundos da MESMA referência). Pressupõe a grade dentro da
    cobertura (verificado antes). Sem extrapolação; ausente em descontinuidades e junto a valores ausentes."""
    n = len(t)
    if n == 1:
        exact = np.abs(grid - t[0]) < 1e-6
        return np.where(exact, v[0], np.nan), {"exact": int(exact.sum()), "interpolated": 0}
    d = np.diff(t)
    step = float(np.median(d[d > 0])) if (d > 0).any() else float("nan")
    gaps = d > F.GAP_FACTOR * step if math.isfinite(step) else np.zeros(d.size, bool)
    j = np.clip(np.searchsorted(t, grid, side="right") - 1, 0, n - 2)
    span = t[j + 1] - t[j]
    w = np.where(span > 0, (grid - t[j]) / np.where(span > 0, span, 1.0), 0.0)
    a, b = v[j], v[j + 1]
    if angular:
        ra, rb = np.deg2rad(a), np.deg2rad(b)
        out = np.rad2deg(np.arctan2((1 - w) * np.sin(ra) + w * np.sin(rb), (1 - w) * np.cos(ra) + w * np.cos(rb))) % 360.0
        out = np.where(out >= 360.0, 0.0, out)        # −1e-15 % 360 arredonda para 360.0: mesmo ângulo, faixa [0, 360)
    else:
        out = (1 - w) * a + w * b
    at_a = np.abs(grid - t[j]) < 1e-6
    at_b = np.abs(grid - t[j + 1]) < 1e-6
    bad = (gaps[j] & ~(at_a | at_b)) | ~np.isfinite(a) | ~np.isfinite(b)
    bad &= ~(at_a & np.isfinite(a))
    bad &= ~(at_b & np.isfinite(b))
    out = np.where(at_a, a, np.where(at_b, b, out))
    out[bad] = np.nan
    exact = at_a | at_b
    return out, {"exact": int(exact.sum()), "interpolated": int((~exact & ~bad).sum()), "missing": int(bad.sum()),
                 "original_step_s": step if math.isfinite(step) else None}


def _fmt_s(x: float, tz: str | None, declared: bool) -> str:
    w = utc_to_wall(np.array([x]), tz if declared else None)[0]
    return w.strftime("%d/%m/%Y %H:%M") + (f" ({tz_label(tz)})" if declared else " (relógio não declarado)")


def available_horizon(series: list[Series], tz: str | None) -> dict | None:
    cov = coverage(series)
    if cov is None:
        return None
    declared = all(s.declared for s in series)
    lo, hi = cov
    lo_min = math.ceil(lo / 60.0) * 60.0                     # primeiro minuto inteiro coberto
    return {"start_utc_s": lo, "end_utc_s": hi, "first_start_s": lo_min,
            "max_duration_min": int(max((hi - lo_min) // 60, 0)),
            "start_text": _fmt_s(lo, tz, declared), "end_text": _fmt_s(hi, tz, declared),
            "start_wall": utc_to_wall(np.array([lo_min]), tz if declared else None)[0]}


# ------------------------------------------------------------------ janela
def build_window(mission: Mapping | None, series: dict[str, Series], needs: dict[str, tuple[tuple[str, ...], tuple[str, ...]]]) -> Window:
    """Prepara a grade da missão. ``needs[slot] = (variáveis obrigatórias, variáveis opcionais presentes)``."""
    notes: list[Note] = []
    used = [series[s] for s in needs if s in series]
    w = Window(ok=False, notes=notes)
    if mission is None:
        notes.append(Note(ERROR, "sem_janela", "Janela da missão não definida (início e duração)."))
        return w
    errs = SG.mission_errors(mission)
    if errs:
        notes += [Note(ERROR, "janela_invalida", e) for e in errs]
        return w
    tz = mission.get("timezone")
    w.timezone, w.duration_min = tz, int(mission["duration_min"])
    missing_slots = [s for s in needs if s not in series]
    for s in missing_slots:
        notes.append(Note(ERROR, "sem_previsao", f"Previsão de {'demanda' if s == 'demand' else 'clima'} ausente no "
                                                 "cenário (necessária para esta execução)."))
    if missing_slots:
        return w
    # ---- fusos: referência temporal comum
    undeclared = [s for s in used if not s.declared]
    if tz is not None and undeclared:
        notes.append(Note(ERROR, "fuso_indefinido", "Série(s) sem fuso declarado ("
                          + ", ".join(_slot_label(s.slot) for s in undeclared) + ") não podem ser alinhadas a uma missão no "
                          f"fuso {tz}: declare o fuso da série em Previsões ou use uma missão sem fuso declarado."))
        return w
    if tz is None:
        declared = [s for s in used if s.declared]
        if declared:
            notes.append(Note(ERROR, "fuso_misto", "A missão não declara fuso, mas a(s) série(s) "
                              + ", ".join(f"{_slot_label(s.slot)} ({s.entry.get('timezone')})" for s in declared)
                              + " têm fuso declarado: informe o fuso da missão."))
            return w
        if len(used) > 1 and mission.get("undeclared_clock") != SG.UNDECLARED_CLOCK:
            notes.append(Note(ERROR, "relogio_ambiguo", "Demanda e clima sem fuso declarado: o alinhamento só é inequívoco se "
                              "declarar explicitamente que ambos usam o MESMO relógio local (opção na janela da missão), ou "
                              "se declarar o fuso de cada série em Previsões."))
            return w
        notes.append(Note(WARNING, "relogio_nao_declarado", "Instantes sem fuso declarado: a missão usa o relógio de parede "
                          "das séries" + (" (declaração explícita de relógio comum, registrada na rodada)." if len(used) > 1 else ".")))
    else:
        tzs = sorted({s.entry.get("timezone") for s in used})
        if len(tzs) > 1 or tzs != [tz]:
            notes.append(Note(INFO, "fusos_convertidos", "Séries em fusos " + ", ".join(tzs) + f" convertidas para UTC e "
                              f"alinhadas; instantes apresentados no fuso da missão ({tz})."))
    # ---- início em UTC
    start_wall = pd.Timestamp(str(mission["start"]))
    s_utc, s_bad = wall_to_utc(pd.Series([start_wall]), tz)
    if s_bad.any():
        notes.append(Note(ERROR, "inicio_ambiguo", f"Início {start_wall:%d/%m/%Y %H:%M} ambíguo ou inexistente no fuso {tz} "
                                                   "(mudança de horário): escolha outro instante."))
        return w
    D = w.duration_min
    grid = s_utc[0] + 60.0 * np.arange(D + 1)
    w.start_wall, w.start_utc = start_wall, pd.Timestamp(s_utc[0] * 1e9)
    w.grid_utc = pd.DatetimeIndex(pd.to_datetime(grid * 1e9))
    w.grid_wall = utc_to_wall(grid, tz)
    w.runtime_times = pd.DatetimeIndex(start_wall + pd.to_timedelta(np.arange(D + 1), unit="min"))
    if tz is not None and _offset_minutes(tz) is None and not w.grid_wall.equals(w.runtime_times):
        notes.append(Note(WARNING, "horario_de_verao", "A janela atravessa uma mudança de horário: o runtime recebe a grade "
                          "uniforme a partir do início local; os instantes UTC e locais reais de cada passo são gravados."))
    w.horizon = available_horizon(used, tz)
    if D > SG.LONG_DURATION_MIN:
        notes.append(Note(WARNING, "janela_longa", f"Janela de {D} min (> {SG.LONG_DURATION_MIN} min): tempo de cálculo "
                                                   "elevado (um despacho otimizado por minuto)."))
    # ---- cobertura, mudança de horário e conversão para a grade
    for slot, (required, optional) in needs.items():
        s = series[slot]
        if s.bad_wall_s.size:
            near = utc_to_wall(np.array([grid[0] - DST_MARGIN_S, grid[-1] + DST_MARGIN_S]), s.entry.get("timezone"))
            lo, hi = _epoch_s(near)
            if ((s.bad_wall_s >= lo) & (s.bad_wall_s <= hi)).any():
                notes.append(Note(ERROR, "instante_ambiguo", f"{_slot_label(slot)}: instantes ambíguos ou inexistentes "
                                  "(mudança de horário) próximos da janela; o alinhamento não é inequívoco."))
                continue
            notes.append(Note(INFO, "instante_ambiguo_fora", f"{_slot_label(slot)}: {s.bad_wall_s.size} instante(s) ambíguo(s) "
                              "de mudança de horário fora da janela (não usados)."))
        t0s, t1s = float(s.t_utc[0]), float(s.t_utc[-1])
        if grid[0] < t0s - 1e-6 or grid[-1] > t1s + 1e-6:
            decl = s.declared
            notes.append(Note(ERROR, "sem_cobertura", f"{_slot_label(slot)}: a série cobre {_fmt_s(t0s, tz, decl)} → "
                              f"{_fmt_s(t1s, tz, decl)}; a janela ({_fmt_s(grid[0], tz, decl)} → {_fmt_s(grid[-1], tz, decl)}) "
                              "sai da cobertura. Nada é extrapolado: ajuste o início/duração."))
            continue
        for var in (*required, *optional):
            vals, info = resample(s.t_utc, s.df[var].to_numpy(dtype=float), grid, angular=var in F.ANGULAR)
            miss = ~np.isfinite(vals)
            label = F.VARIABLES[var].label
            if miss.any():
                first = utc_to_wall(grid[miss][:3], tz)
                kind = "obrigatória" if var in required else "opcional presente no perfil"
                notes.append(Note(ERROR, "dado_ausente", f"{label} ({kind}): {int(miss.sum())} instante(s) da grade sem dado "
                                  f"(lacuna ou valor ausente), p. ex. {', '.join(x.strftime('%d/%m %H:%M') for x in first)}. "
                                  "Ausentes nunca viram zero: escolha uma janela com dados completos."))
                continue
            method = ("identidade (amostras coincidem com a grade de 1 min)" if info["interpolated"] == 0 else
                      ("interpolação linear circular (menor arco)" if var in F.ANGULAR else "interpolação linear")
                      + f" em {info['interpolated']} de {len(grid)} instantes, sem extrapolação")
            step = info.get("original_step_s")
            if info["interpolated"] and step and step < SG.STEP_S:
                method += " — passo original menor que 60 s: valores pontuais nos instantes da grade (sem média)"
            w.resampling[var] = {"slot": slot, "method": method, "original_step_s": step, "exact": info["exact"],
                                 "interpolated": info["interpolated"]}
            if slot == "demand":
                w.demand_kW = vals
            else:
                w.climate[var] = vals
    w.ok = not any(n.level == ERROR for n in notes)
    return w


def _slot_label(slot: str) -> str:
    return {"demand": "Demanda", "climate": "Clima"}.get(slot, slot)


def climate_frame(w: Window) -> pd.DataFrame | None:
    """Clima na grade UNIFORME do runtime, com os nomes de colunas que ``mix_engine.detect_climate_columns`` reconhece.
    Variáveis ausentes do perfil não são criadas (o runtime as trata como ausentes — densidade do ar de referência)."""
    if not w.climate:
        return None
    out = pd.DataFrame({"timestamp": w.runtime_times.strftime("%Y-%m-%d %H:%M:%S")})
    for var, vals in w.climate.items():
        out[RUNTIME_CLIMATE[var]] = vals
    return out


__all__ = ["ERROR", "INFO", "Note", "RUNTIME_CLIMATE", "Series", "WARNING", "Window", "available_horizon", "build_window",
           "climate_frame", "coverage", "load_series", "resample", "tz_label", "utc_to_wall", "wall_to_utc"]
