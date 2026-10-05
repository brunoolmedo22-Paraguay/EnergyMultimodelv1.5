"""Execução do EMS sobre um pacote de troca.

    pacote (CSVs + ems_config.json)  →  montar_fontes  →  despacho  →  relatório

e, opcionalmente, validação dinâmica: o despacho da FC é reenviado ao modelo
PEMFC da plataforma para medir o H2 que a física consome.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .despacho import SIGLAS_ALG, CfgDespacho, despacho, relatorio
from .fontes import Log, carregar_eolica, carregar_pv, montar_fontes
from .ponte import ARCH_PADRAO, ECON_PADRAO


def executar_pacote(pasta: Path, progresso=None, sobrescrever: dict | None = None) -> dict:
    """``sobrescrever`` troca campos do ems_config.json só nesta execução (ex.: o
    algoritmo, para comparar metaheurísticas sobre as MESMAS entradas)."""
    pasta = Path(pasta)
    C = json.loads((pasta / "ems_config.json").read_text(encoding="utf-8"))
    C.update(sobrescrever or {})
    log = Log()
    t_ini = time.perf_counter()
    carga = pd.read_csv(pasta / "carga.csv")
    t_min = carga.t_min.to_numpy(float)
    P_load = carga.P_kW.to_numpy(float)

    arch = dict(ARCH_PADRAO)
    arch.update(C.get("eta_conv", {}))
    arch["N_fc"] = int(C.get("N_fc", 1))
    if C.get("pv_P_rated_kWp") is not None:
        arch["pv_P_rated_kWp"] = float(C["pv_P_rated_kWp"])
    econ = dict(ECON_PADRAO)
    econ.update(C.get("econ", {}))

    fontes = montar_fontes(pasta, t_min, arch, econ, C.get("opcoes_fontes", {}), log)
    if not fontes:
        raise ValueError("Ative pelo menos uma fonte despachável (H₂/PEMFC, bateria ou térmica).")
    # Renováveis NÃO despacháveis: toda a potência disponível é descontada da carga
    # antes da otimização; o EMS despacha FC, bateria e térmica só para o restante.
    P_pv = carregar_pv(pasta / "pv.csv", t_min, arch["pv_P_rated_kWp"], log) if C.get("usar_pv") \
        else np.zeros_like(t_min)
    P_eol = carregar_eolica(pasta / "eolica.csv", t_min, log) if C.get("usar_eolica") else np.zeros_like(t_min)
    P_renov = arch["eta_dc"] * P_pv + arch.get("eta_eol", 1.0) * P_eol
    P_liq = np.maximum(P_load - P_renov, 0.0)
    P_renov_vertida = np.maximum(P_renov - P_load, 0.0)
    if P_renov_vertida.sum() > 0:
        log.info(f"Renováveis acima da carga em {int((P_renov_vertida > 0).sum())} passos: "
                 f"{P_renov_vertida.sum() * (t_min[1] - t_min[0]) / 60:.2f} kWh não aproveitados.")

    cfg = CfgDespacho(
        Ts_s=float(C.get("Ts_s", 60)), N=int(C.get("N", 3)),
        S_base=float(max(np.max(f.P_max_unid_kW) * f.n_unid for f in fontes)),
        pen_deficit=econ["pen_deficit_rs_kWh"], pen_excesso=econ["pen_excesso_rs_kWh"],
        algoritmo=int(C.get("algoritmo", 2)), meta_penalizada=bool(C.get("meta_penalizada", False)),
        soc_alvo_tol=float(C.get("soc_alvo_tol", 0.05)), seed=C.get("seed", 0),
    )
    if cfg.S_base <= 0:
        raise ValueError("Todas as fontes têm teto zero na janela: nada a despachar.")
    log.info(f"[ems] {SIGLAS_ALG[cfg.algoritmo]} | {len(fontes)} fontes | S_base={cfg.S_base:.1f} kW | "
             f"N={cfg.N} | Ts={cfg.Ts_s:.0f} s | {t_min.size} passos")
    res = despacho(fontes, P_liq, cfg, progresso=progresso)
    kv = res["k_validos"]

    # Vertimento é vertimento independentemente da origem. O núcleo de despacho
    # contabiliza o excesso das fontes despacháveis; solar/eólica são abatidas
    # antes da otimização e, portanto, entram aqui no custo/KPI global. Como esse
    # excedente renovável é fixo na arquitetura atual (must-take), o termo é uma
    # constante para o solver, mas deve aparecer no custo efetivo da rodada.
    Ts_h = cfg.Ts_s / 3600.0
    E_vert_ren = float(P_renov_vertida[:kv].sum() * Ts_h)
    C_vert_ren = float(econ["pen_excesso_rs_kWh"] * E_vert_ren)
    if kv:
        res["custo_rs"][:kv] += econ["pen_excesso_rs_kWh"] * P_renov_vertida[:kv] * Ts_h
    res["custo_total_rs"] = float(res["custo_total_rs"] + C_vert_ren)

    rel = relatorio(res, fontes, cfg)
    E_vert_desp = float(rel["energia_vertida_kWh"])
    rel["energia_vertida_despachavel_kWh"] = E_vert_desp
    rel["energia_vertida_renovavel_kWh"] = E_vert_ren
    rel["energia_vertida_kWh"] = E_vert_desp + E_vert_ren
    rel["custo_vertimento_renovavel_rs"] = C_vert_ren

    tempo = time.perf_counter() - t_ini
    return {
        "algoritmo": SIGLAS_ALG[cfg.algoritmo], "config": C, "pasta": str(pasta),
        "t0": pd.Timestamp(C.get("t0", "2026-09-01")), "carga_descricao": C.get("carga_descricao", ""),
        "Ts_s": cfg.Ts_s, "N": cfg.N, "S_base_kW": cfg.S_base, "k_validos": kv,
        "t_min": t_min, "P_load_kW": P_load, "P_pv_kW": P_pv, "P_eol_kW": P_eol, "P_load_liq_kW": P_liq,
        "P_renov_kW": P_renov, "P_renov_vertida_kW": P_renov_vertida,
        "eta_pv": arch["eta_dc"], "eta_eol": arch.get("eta_eol", 1.0),
        "nomes": [f.nome for f in fontes], "tipos": [f.tipo for f in fontes],
        "eta": np.array([f.eta for f in fontes]), "n_unid_inst": np.array([f.n_unid for f in fontes]),
        "P_max_unid_kW": np.column_stack([f.P_max_unid_kW for f in fontes]),
        **{k: res[k] for k in ("P_kW", "n_unid", "SOC", "deficit_kW", "excesso_kW", "custo_rs",
                               "custo_partida_rs", "J_meta", "J_ref", "viol_meta", "viol_ref",
                               "P_meta_kW", "n_combos", "t_meta_s", "t_ref_s", "n_inviaveis")},
        "tempo_total_s": tempo, "rel": rel,
        "log": log.linhas, "avisos": log.avisos + res["avisos"],
        "fontes_meta": {f.nome: f.meta for f in fontes},
        "bateria": next(({"E_kWh": f.E_kWh, "SOC_ini": f.SOC_ini, "SOC_min": f.SOC_min, "SOC_max": f.SOC_max,
                          "soc_alvo_tol": cfg.soc_alvo_tol} for f in fontes if f.armazena), None),
    }


def validar_fc_dinamico(r: dict, passo_s: float = 2.0) -> dict | None:
    """Fecha o laço EMS → plataforma: cada stack ligado recebe P_fc/n e o modelo
    dinâmico PEMFC integra o H2 consumido (partida, idle, rampas e saturação
    incluídas). O EMS estima H2 por uma curva ESTÁTICA kg/kWh; a diferença entre
    os dois mede quanto a estimativa do otimizador se afasta da física."""
    if "fc" not in r["nomes"]:
        return None
    from h2_pemfc import Equivalent65kWHorizonDynamicModel
    from h2_pemfc.ems_input import prepare_ems_profile
    from models.numerics import trapezoid_integral

    j = r["nomes"].index("fc")
    kv = r["k_validos"]
    P = np.maximum(r["P_kW"][:kv, j], 0)
    n = r["n_unid"][:kv, j].astype(int)
    N_fc = int(r["n_unid_inst"][j])
    t_passos = r["t_min"][:kv]
    ts = r["t0"] + pd.to_timedelta(t_passos, unit="min")
    fronteiras = np.append(t_passos, t_passos[-1] + r["Ts_s"] / 60)
    modelo = Equivalent65kWHorizonDynamicModel()
    pmax = float(modelo._physical_max_power_kW)
    cache: dict = {}
    total = {"h2_kg": 0.0, "E_entregue_kWh": 0.0, "E_pedida_kWh": 0.0}
    serie = np.zeros(kv)
    por_stack = []
    for i in range(N_fc):
        ligado = n > i
        req = np.where(ligado, np.minimum(P / np.maximum(n, 1), pmax), 0.0)
        chave = ligado.tobytes() + np.round(req, 6).tobytes()
        if chave not in cache:
            raw = pd.DataFrame({"timestamp": ts, "P_FC_requested_kW": req, "FC_enable": ligado})
            sim = modelo.simulate_profile(prepare_ems_profile(raw, dynamic_model=modelo).profile,
                                          internal_time_step_s=passo_s)
            tm = (pd.to_datetime(sim.timestamp) - pd.to_datetime(sim.timestamp).iloc[0]).dt.total_seconds() / 60
            tm = tm.to_numpy(float)
            kgh = sim.hydrogen_supplied_kg_h.to_numpy(float)
            acum = np.concatenate([[0.0], np.cumsum(np.diff(tm) / 60 * (kgh[1:] + kgh[:-1]) / 2)])
            cache[chave] = {
                "h2_kg": float(acum[-1]),
                "E_entregue_kWh": trapezoid_integral(sim.P_FC_delivered_kW.to_numpy(float), tm / 60),
                "E_pedida_kWh": trapezoid_integral(sim.P_FC_requested_kW.to_numpy(float), tm / 60),
                "passo": np.diff(np.interp(fronteiras, tm, acum)),
            }
        c = cache[chave]
        for k in total:
            total[k] += c[k]
        serie += c["passo"]
        por_stack.append({"stack": i + 1, "h2_kg": c["h2_kg"], "E_entregue_kWh": c["E_entregue_kWh"],
                          "E_pedida_kWh": c["E_pedida_kWh"]})
    return {**total, "por_stack": por_stack, "h2_kg_passo": serie}
