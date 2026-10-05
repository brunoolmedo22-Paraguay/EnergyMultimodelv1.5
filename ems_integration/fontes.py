"""Port Python de ``montar_fontes.m``, ``ler_serie_csv.m`` e ``carregar_pv.m``.

Lê exatamente os mesmos CSVs da pasta de troca que o backend MATLAB lê, com
as mesmas regras (alinhamento relativo ao próprio início, NaN fora da janela →
indisponível, envelope e curva de H2 *observados* no CSV) e as mesmas opções
novas (``opts``) adicionadas ao ``montar_fontes.m`` para a integração.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .contrato import CurvaEmpirica, Fonte


class ErroFonte(ValueError):
    """Erro de montagem de fonte com a mesma semântica dos ``error()`` do MATLAB."""


@dataclass
class Log:
    linhas: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def info(self, msg: str) -> None:
        self.linhas.append(msg)

    def aviso(self, msg: str) -> None:
        self.avisos.append(msg)
        self.linhas.append("AVISO: " + msg)


# --------------------------------------------------------------------- leitura
def ler_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _coluna(df: pd.DataFrame, col: str) -> pd.Series:
    for c in df.columns:
        if c.strip().lower() == col.strip().lower():
            return df[c]
    raise ErroFonte(f'Coluna "{col}" não existe no CSV. Disponíveis: {", ".join(df.columns)}')


def tempo_relativo_min(df: pd.DataFrame, col: str = "timestamp") -> np.ndarray:
    t = pd.to_datetime(_coluna(df, col))
    return ((t - t.iloc[0]).dt.total_seconds() / 60.0).to_numpy(dtype=float)


def ler_serie(df, col, unidade, tn, t_min, metodo, permitir_extrap=False) -> np.ndarray | None:
    """Equivalente a ``ler_serie_csv.m`` (interp1 com NaN fora da janela)."""
    if not col:
        return None
    v = _coluna(df, col)
    if not pd.api.types.is_numeric_dtype(v) or pd.api.types.is_bool_dtype(v):
        if pd.api.types.is_bool_dtype(v):
            v = v.astype(float)
        else:
            cats = sorted(pd.unique(v.astype(str)))   # double(categorical(...)) → códigos 1..K
            v = v.astype(str).map({c: i + 1 for i, c in enumerate(cats)})
    v = pd.to_numeric(v, errors="coerce").to_numpy(dtype=float)
    u = unidade.lower()
    if u == "w":
        v = v / 1e3
    elif u == "mw":
        v = v * 1e3
    elif u == "pct":
        v = v / 100.0
    elif u not in ("kw", "a", "v", "pu_none", "nenhuma", ""):
        raise ErroFonte(f'Unidade "{unidade}" desconhecida.')

    tn = np.asarray(tn, dtype=float)
    _, ia = np.unique(tn, return_index=True)      # unique 'stable' + sort
    ia = np.sort(ia)
    t_u, v = tn[ia], v[ia]
    ordem = np.argsort(t_u, kind="stable")
    t_u, v = t_u[ordem], v[ordem]
    t = np.asarray(t_min, dtype=float)
    if t_u.size == 1:
        return np.full(t.size, v[0])

    fora = (t < t_u[0]) | (t > t_u[-1])
    if metodo == "linear":
        ok = np.isfinite(v)
        y = np.interp(t, t_u, v) if ok.all() else _interp_linear_nan(t, t_u, v)
    elif metodo == "previous":
        idx = np.clip(np.searchsorted(t_u, t, side="right") - 1, 0, t_u.size - 1)
        y = v[idx]
    elif metodo == "nearest":
        idx = np.clip(np.searchsorted(t_u, t), 1, t_u.size - 1)
        esq = t - t_u[idx - 1] < t_u[idx] - t
        idx = np.where(esq, idx - 1, idx)
        y = v[idx]
    else:
        raise ErroFonte(f"Método {metodo} desconhecido.")
    y = np.asarray(y, dtype=float).copy()
    if not permitir_extrap:
        y[fora] = np.nan
    return y


def _interp_linear_nan(t, t_u, v):
    # interp1 linear propaga NaN dos vizinhos; reproduz isso ponto a ponto.
    idx = np.clip(np.searchsorted(t_u, t, side="right") - 1, 0, t_u.size - 2)
    x0, x1 = t_u[idx], t_u[idx + 1]
    w = np.where(x1 > x0, (t - x0) / (x1 - x0), 0.0)
    return v[idx] * (1 - w) + v[idx + 1] * w


def _mediana_positiva(x) -> float:
    if x is None:
        return 0.0
    pos = x[np.isfinite(x) & (x > 0)]
    return float(np.median(pos)) if pos.size else 0.0


def _custo_por_kwh(custo_rs, energia_kwh) -> np.ndarray:
    den = np.where(np.isfinite(energia_kwh) & (energia_kwh > 1e-9), energia_kwh, np.nan)
    c = custo_rs / den
    if np.all(np.isnan(c)):
        return np.zeros_like(custo_rs)
    c[np.isnan(c)] = np.nanmedian(c)
    return c


def _diag_cobertura(nome, tn, t_min, log: Log) -> None:
    tn = tn[np.isfinite(tn)]
    if tn.size == 0:
        log.aviso(f'Fonte "{nome}": coluna de tempo ilegível.')
        return
    cobre = tn[0] <= t_min[0] + 1e-6 and tn[-1] >= t_min[-1] - 1e-6
    sobrepoe = tn[-1] >= t_min[0] and tn[0] <= t_min[-1]
    if not sobrepoe:
        log.aviso(f'Fonte "{nome}": janela do CSV [{tn[0]:.1f}, {tn[-1]:.1f}] min sem sobreposição com a simulação.')
    elif not cobre:
        log.aviso(
            f'Fonte "{nome}": janela do CSV [{tn[0]:.1f}, {tn[-1]:.1f}] min cobre só parte da simulação '
            f"[{t_min[0]:.1f}, {t_min[-1]:.1f}] min — fora dela a fonte fica indisponível."
        )


# ------------------------------------------------------------- montar_fontes
def montar_fontes(dados_dir: Path, t_min: np.ndarray, arch: dict, econ: dict, opts: dict, log: Log) -> list[Fonte]:
    dados_dir = Path(dados_dir)
    nt = t_min.size
    lista = [s.lower() for s in opts.get("fontes", ["termica", "fc", "bateria"])]
    fc_base = str(opts.get("fc_base_potencia", "stack")).lower()
    fontes: list[Fonte] = []

    # ------------------------------------------------------------ TÉRMICA
    if "termica" in lista:
        Tt = ler_csv(dados_dir / "termica.csv")
        tn = tempo_relativo_min(Tt)
        _diag_cobertura("termica", tn, t_min, log)
        P_max = ler_serie(Tt, "contractual_target_mw", "MW", tn, t_min, "previous")
        P_min = ler_serie(Tt, "inflexibility_mw", "MW", tn, t_min, "previous")
        rmp = ler_serie(Tt, "ramp_rate_mw_min", "MW", tn, t_min, "previous")
        c_rs = ler_serie(Tt, "variable_cost_rs", "nenhuma", tn, t_min, "previous")
        e_mwh = ler_serie(Tt, "energy_delivered_mwh", "nenhuma", tn, t_min, "previous")
        c_start = ler_serie(Tt, "startup_cost_rs", "nenhuma", tn, t_min, "previous")
        fora = np.isnan(P_max) | np.isnan(P_min)
        P_max[fora] = 0.0
        P_min[fora] = 0.0
        if opts.get("termica_Pmin_kW") is not None:
            P_min = np.minimum(np.maximum(P_min, opts["termica_Pmin_kW"] * (P_max > 0)), P_max)
        c_kWh = _custo_por_kwh(c_rs, e_mwh * 1000.0)
        if np.all(c_kWh == 0) and opts.get("termica_cvu_rs_kWh") is not None:
            c_kWh[:] = opts["termica_cvu_rs_kWh"]
            log.info(f"[termica] custo do CSV indisponível → CVU da plataforma: {opts['termica_cvu_rs_kWh']:.4f} R$/kWh")
        ramp = _mediana_positiva(rmp)
        if ramp <= 0:
            ramp = opts.get("termica_ramp_kW_min") or np.inf
            log.info(f"[termica] sem rampa observada no CSV → rampa = {ramp:g} kW/min")
        fontes.append(Fonte(
            nome="termica", tipo="geracao", n_unid=1, n_ini=int(P_min[0] > 0),
            P_max_unid_kW=P_max, P_min_unid_kW=P_min, c_var_rs_kWh=c_kWh,
            c_start_unid_rs=_mediana_positiva(c_start), ramp_kW_min=ramp, eta=1.0,
        ))

    # EÓLICA: não entra aqui. É não despachável, como a solar — a série inteira é
    # descontada da carga antes da otimização (ver carregar_eolica / executor).

    # ----------------------------------------------------------------- FC
    if "fc" in lista:
        N_fc = int(arch["N_fc"])
        Tf = ler_csv(dados_dir / "fc.csv")
        tn = tempo_relativo_min(Tf)
        _diag_cobertura("fc", tn, t_min, log)
        raw_state = _coluna(Tf, "state").astype(str).str.strip()
        log.info(f'[fc] valores únicos de "state": {" | ".join(sorted(raw_state.unique()))}')
        Tf = Tf.assign(disp_flag_tmp=(raw_state.str.upper() != "FAULT_LIMITED").astype(float))
        st = ler_serie(Tf, "disp_flag_tmp", "nenhuma", tn, t_min, "previous")
        disp = np.ones(nt)
        disp[np.isnan(st)] = 0.0
        disp[st == 0] = 0.0
        P_deliv = ler_serie(Tf, "P_FC_delivered_kW", "kW", tn, t_min, "previous")
        P_stack = ler_serie(Tf, "P_stack_kW", "kW", tn, t_min, "previous")
        h2 = ler_serie(Tf, "hydrogen_supplied_kg_h", "nenhuma", tn, t_min, "previous")
        ok = np.isfinite(P_stack) & np.isfinite(P_deliv) & np.isfinite(h2) & (P_deliv > 0)
        if ok.sum() < 3:
            raise ErroFonte("fc.csv: menos de 3 pontos com P_FC_delivered_kW>0 — não dá pra derivar envelope/custo.")
        base = P_deliv if fc_base == "entregue" else P_stack
        Pmax_obs = float(np.max(base[ok]))
        Pmin_obs = float(np.min(base[ok & (base > 1e-6)]))
        log.info(f"[fc] envelope por stack ({fc_base}) observado: [{Pmin_obs:.2f}, {Pmax_obs:.2f}] kW ({ok.sum()} pontos)")
        idx = np.flatnonzero(ok)
        dP = np.diff(base[idx])
        dt = np.diff(t_min[idx])
        r = np.abs(dP) / np.maximum(dt, np.finfo(float).eps)
        r = r[np.isfinite(r) & (r > 0)]
        ramp_fc = float(np.max(r)) if r.size else np.inf
        if not r.size:
            log.aviso("fc.csv sem pontos para estimar rampa: usando Inf.")
        x_obs = np.round(base[ok], 4)
        kg_kWh = h2[ok] / P_deliv[ok]
        x_u, inv = np.unique(x_obs, return_inverse=True)
        y_u = np.array([np.median(kg_kWh[inv == i]) for i in range(x_u.size)])
        log.info(f"[fc] curva kg_H2/kWh com {x_u.size} pontos únicos; rampa observada {ramp_fc:.2f} kW/min")
        # Se o envelope usa P_FC_delivered_kW, a potência já é líquida no barramento
        # (auxiliares e DC/DC já foram descontados pelo modelo PEMFC). Aplicar eta_dc1
        # novamente seria uma dupla penalização. A eficiência do conversor só pertence
        # ao caminho legado baseado em potência bruta do stack.
        eta_fc = 1.0 if fc_base == "entregue" else float(arch["eta_dc1"])
        if fc_base == "entregue":
            log.info("[fc] base entregue: eta no balanço = 1,0 (P_FC_delivered_kW já é líquida no barramento).")
        fontes.append(Fonte(
            nome="fc", tipo="geracao", n_unid=N_fc, n_ini=N_fc, dn_max=1,
            P_max_unid_kW=Pmax_obs * disp, P_min_unid_kW=Pmin_obs * disp,
            curva=CurvaEmpirica(x_u, y_u, float(econ["preco_H2_rs_kg"])), qtd_fisica_unidade="kg_H2",
            c_start_unid_rs=0.0, ramp_kW_min=ramp_fc, eta=eta_fc,
            meta={"curva_x": x_u.tolist(), "curva_y": y_u.tolist(), "base_potencia": fc_base,
                  "eta_balanco": eta_fc},
        ))

    # ------------------------------------------------------------ BATERIA
    if "bateria" in lista:
        fontes.append(_montar_bateria(dados_dir, t_min, arch, econ, opts, log))
    return fontes


def _montar_bateria(dados_dir, t_min, arch, econ, opts, log) -> Fonte:
    nt = t_min.size
    Tb = ler_csv(dados_dir / "bateria.csv")
    tn = tempo_relativo_min(Tb)
    _diag_cobertura("bateria", tn, t_min, log)
    P_ext = ler_serie(Tb, "power_W", "W", tn, t_min, "linear")
    fl = ler_serie(Tb, "limit_flag", "nenhuma", tn, t_min, "nearest")
    V = ler_serie(Tb, "voltage_V", "nenhuma", tn, t_min, "linear")
    I = ler_serie(Tb, "current_A", "nenhuma", tn, t_min, "linear")
    soc = ler_serie(Tb, "soc_percent", "pct", tn, t_min, "linear")
    if soc is None or np.all(np.isnan(soc)):
        raise ErroFonte("bateria.csv sem soc_percent válido.")
    soc_ini = float(soc[np.flatnonzero(~np.isnan(soc))[0]])
    Pdis = P_ext[np.isfinite(P_ext) & (P_ext > 0)]
    Pchg = P_ext[np.isfinite(P_ext) & (P_ext < 0)]
    Pdis_obs = float(Pdis.max()) if Pdis.size else 0.0
    Pchg_obs = float(Pchg.min()) if Pchg.size else 0.0
    log.info(f"[bateria] envelope observado: descarga até {Pdis_obs:.2f} kW, carga até {Pchg_obs:.2f} kW")
    Pdis_max = np.full(nt, Pdis_obs)
    Pchg_max = np.full(nt, Pchg_obs)
    if fl is not None:
        flag = ~(fl == 0)                       # NaN ~= 0 é verdadeiro no MATLAB
        sp = flag & (P_ext > 0)
        sn = flag & (P_ext < 0)
        Pdis_max[sp] = np.minimum(Pdis_max[sp], P_ext[sp])
        Pchg_max[sn] = np.maximum(Pchg_max[sn], P_ext[sn])

    ok = np.isfinite(V) & np.isfinite(I)
    if ok.sum() < 10:
        raise ErroFonte(f"bateria.csv: apenas {ok.sum()} pontos válidos de V/I na janela de simulação.")
    A = np.column_stack([np.ones(ok.sum()), t_min[ok], -I[ok]])
    theta, *_ = np.linalg.lstsq(A, V[ok], rcond=None)
    Voc, deriva, Rint = map(float, theta)
    resid = V[ok] - A @ theta
    R2 = 1 - np.var(resid, ddof=1) / np.var(V[ok], ddof=1)
    if np.std(I[ok], ddof=1) < 1e-6:
        raise ErroFonte("current_A praticamente constante: Rint indeterminado.")
    if Rint <= 0:
        raise ErroFonte(f"Rint calibrado = {Rint:.5f} Ω (não positivo).")
    if R2 < 0.5:
        log.aviso(f"Calibração da bateria fraca: R²={R2:.2f} (Rint={Rint:.5f} Ω).")
    I_dis, V_dis = I[ok & (I > 0)], V[ok & (I > 0)]
    V_chg = V[ok & (I < 0)]
    if not I_dis.size or not V_chg.size:
        raise ErroFonte("bateria.csv precisa ter pontos de carga E descarga para calibrar as eficiências.")
    eta_d = float(np.median(V_dis / Voc))
    eta_c = float(np.median(Voc / V_chg))
    log.info(f"[bateria] Voc={Voc:.2f} V, Rint={Rint:.5f} Ω (R²={R2:.3f}) | eta_desc={eta_d:.4f}, eta_carga={eta_c:.4f}")
    E = float(opts.get("bateria_E_kWh") or arch["bat_Q_kWh"])
    smin = float(opts.get("bateria_SOC_min", arch["bat_SOC_min"]))
    smax = float(opts.get("bateria_SOC_max", arch["bat_SOC_max"]))
    return Fonte(
        nome="bateria", tipo="armazenamento", P_max_unid_kW=Pdis_max, P_min_unid_kW=Pchg_max,
        eta=float(arch["eta_dc2"]), eta_carga=eta_c, eta_descarga=eta_d, E_kWh=E,
        SOC_ini=soc_ini, SOC_min=smin, SOC_max=smax, SOC_alvo=soc_ini,
        c_deg_rs_kWh=float(econ["c_deg_bateria_rs_kWh"]),
        meta={"Voc": Voc, "Rint": Rint, "R2": R2},
    )


def carregar_pv(path: Path, t_min: np.ndarray, P_rated_kWp: float, log: Log) -> np.ndarray:
    """Schema ``t_min,P_kW`` (o que a ponte escreve); NaN → 0, satura no nominal."""
    T = ler_csv(Path(path))
    tn = _coluna(T, "t_min").to_numpy(dtype=float)
    p = ler_serie(T, "P_kW", "kW", tn, t_min, "linear")
    p[np.isnan(p)] = 0.0
    p = np.clip(p, 0.0, P_rated_kWp)
    ts_h = (t_min[1] - t_min[0]) / 60.0
    log.info(f"PV: pico={p.max():.1f} kW | média={p.mean():.1f} kW | total={p.sum() * ts_h:.2f} kWh")
    return p


def carregar_eolica(path: Path, t_min: np.ndarray, log: Log) -> np.ndarray:
    """Saída do módulo Eólica (``power_net_kw``) → série de potência não despachável.

    Mesma leitura que o ``montar_fontes.m`` fazia para a eólica (linear, NaN → 0,
    sem valores negativos), mas agora ela abate a carga como a solar em vez de
    virar uma variável de decisão."""
    T = ler_csv(Path(path))
    tn = tempo_relativo_min(T)
    _diag_cobertura("eolica", tn, t_min, log)
    p = ler_serie(T, "power_net_kw", "kW", tn, t_min, "linear")
    p[np.isnan(p)] = 0.0
    p = np.maximum(p, 0.0)
    ts_h = (t_min[1] - t_min[0]) / 60.0
    log.info(f"Eólica: pico={p.max():.1f} kW | média={p.mean():.1f} kW | total={p.sum() * ts_h:.2f} kWh")
    return p
