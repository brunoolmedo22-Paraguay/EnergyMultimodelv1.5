"""Conferência QUANTITATIVA da rodada PEMFC produzida pelo E2E do Piso 3D-A2-H (só LÊ e VERIFICA o que foi gravado).

Roda no python SEM solver e, no roteiro, com o motor e os modelos sabotados (``tools/e2e/sabotage_v2``): nenhuma
otimização nem modelo físico é executado. Confere, a partir dos dados gravados da rodada:

* evidência íntegra (``registro.verificar``: hashes, vistas regeneradas, auditoria integral, certificado B04 re-registrado
  com a política do REPOSITÓRIO — aprovada — sem nenhuma aprovação simulada);
* balanço por intervalo (resíduo), energia não atendida e composição do atendimento;
* despacho da PEMFC no domínio [P_mín, P_máx] e H₂ por intervalo = q̂(p)·Δ·u + m_SU·y + m_SD·z (vértices gravados);
* custo do H₂ = preço declarado × massa; componente ``combustivel_h2`` do custo realizado;
* aceitação separada (algébrica aprovada · dinâmica coerente · física não validada) e subestimação reportada.

Uso: python tools/e2e/check_piso3da2h_rodada.py <SEEDS2_DATA_DIR> <seed_piso3da2h.json>
"""
from __future__ import annotations

import io
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from integracao_v2 import curva_h2 as CH  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402

N = 0


def ok(cond, msg):
    global N
    if not cond:
        raise SystemExit(f"FALHA: {msg}")
    N += 1
    print(f"[check] ok — {msg}")


def main(dados: str, info_path: str) -> None:
    info = json.loads(Path(info_path).read_text(encoding="utf-8"))
    reg = MicrogridRegistry(dados)
    store = reg.open(info["pemfc_mg"])
    runs = [r for r in store.list_runs() if r.state == "concluida"]
    ok(len(runs) == 1, "uma rodada concluída na microrrede híbrida (executada pela interface)")
    run = store.get_run(runs[0].run_uid)
    nuc = CH.POLITICA_B04
    ok(nuc["situacao"] == "aprovada_pelo_responsavel" and nuc["versao"] == "b04-proposta-2",
       "política B04 do REPOSITÓRIO: b04-proposta-2 aprovada (nenhuma aprovação simulada neste processo)")
    v = RG.verificar(store, run)
    ok(v.ok, f"evidência verificada sem solver nem modelos ({len(v.itens)} verificações; falhas: {v.falhas()[:2]})")
    ok(any("re-registrado" in t for _, t in v.itens), "certificado B04 re-registrado com critérios recomputados")
    df = pd.read_csv(io.BytesIO(store.run_data(run.run_uid, RG.N_INTERVALOS)), float_precision="round_trip")
    m = run.summary["mission"]
    ok(df["residuo_balanco_kW"].abs().max() < 1e-6, f"balanço fechado em todos os intervalos (|resíduo| máx. "
       f"{df['residuo_balanco_kW'].abs().max():.2e} kW)")
    ok(m["missao_completa"] and m["energia_nao_atendida_kWh"] == 0.0, "missão completa, energia não atendida = 0")
    pem = RG.ler_json(store, run, RG.N_PEMFC)
    (eid, x), = pem["registros"].items()
    cert = x["certificado_b04"]
    ok(cert["politica"]["situacao"] == "aprovada_pelo_responsavel" and cert["politica"]["versao"] == "b04-proposta-2",
       "certificado B04 gravado sob a política aprovada")
    ok(x["curva"]["b04"]["conforme_aos_limiares"], "a curva DESTA configuração atende aos limiares B04 (recomputados)")
    vs = np.array(x["curva"]["vertices_kW_kg_h"])
    lo, hi = x["curva"]["dominio_kW"]
    uid = next(c.split("|")[0] for c in df.columns if c.startswith(eid) and c.endswith("|u"))
    u, p = df[f"{uid}|u"].astype(int), df[f"{uid}|p_kW"].astype(float)
    ok(((u == 0) & (p == 0) | (u == 1) & (p >= lo - 1e-6) & (p <= hi + 1e-6)).all(),
       f"despacho PEMFC no domínio [{lo:g}, {hi:.4g}] kW quando ligada e 0 quando desligada")
    h = float(m["delta_min"]) / 60.0
    msu, msd = float(x["massas_eventos"]["m_partida_kg"]), float(x["massas_eventos"]["m_parada_kg"])
    q = np.where(u == 1, np.interp(p, vs[:, 0], vs[:, 1]), 0.0)
    m_esp = q * h + msu * df[f"{uid}|partida"] + msd * df[f"{uid}|parada"]
    ok(np.allclose(df[f"{uid}|m_h2_kg"], m_esp, rtol=1e-12, atol=1e-12),
       f"H₂ por intervalo = q̂(p)·Δ·u + m_SU·y + m_SD·z (m_SU = {msu:g} kg, m_SD = {msd:.4g} kg)")
    preco = float(x["declaracao"]["preco_h2_R_kg"])
    ok(np.allclose(df[f"{uid}|custo_h2_R"].astype(float), preco * m_esp, rtol=1e-12, atol=1e-12),
       f"custo do H₂ = {preco:g} R$/kg × massa, por intervalo")
    r = m["pemfc"][uid]
    ok(math.isclose(r["massa_h2_kg"], float(m_esp.sum()), rel_tol=1e-12) and
       math.isclose(m["custo_realizado_componentes_R"]["combustivel_h2"], r["custo_h2_R"], rel_tol=1e-12),
       f"resumo: H₂ {r['massa_h2_kg']:.4f} kg, custo H₂ R$ {r['custo_h2_R']:.2f} = componente do custo realizado")
    ok(r["energia_kWh"] > 0 and r["partidas"] >= 1, f"PEMFC despachada: {r['energia_kWh']:.2f} kWh, {r['partidas']} "
       f"partida(s), {r['paradas']} parada(s)")
    ren = m.get("renovaveis") or {}
    ok({z["tecnologia"] for z in ren.values()} == {"fv", "eolica"}, "FV e eólica despachadas com potencial derivado")
    acc = run.summary["execution"]["aceitacao"]
    ok(acc["classificacao"] == "algebrica_aprovada_dinamica_coerente" and acc["fisica"]["estado"] == "nao_validada",
       "aceitação: algébrica aprovada · dinâmica COERENTE · física NÃO validada")
    d = run.summary["execution"]["pemfc_dinamica"][uid]
    ok(d["coerente"] and "h2_subestimacao_max_kg" in d, f"verificação dinâmica: {d['energia_entregue_kWh']:.2f} de "
       f"{d['energia_solicitada_kWh']:.2f} kWh; H₂ dinâmico {d['h2_modelo_dinamico_kg']:.4f} × EMS {d['h2_ems_kg']:.4f} kg; "
       f"subestimação máx. por intervalo {d['h2_subestimacao_max_kg']:.4g} kg")
    print(f"[check] custo REALIZADO R$ {m['custo_realizado_total_R']:.2f} — componentes "
          + ", ".join(f"{k} {val:.2f}" for k, val in m["custo_realizado_componentes_R"].items()))
    for nome, leg in info["legado"].items():
        s = reg.open(leg["mg"])
        rr = s.get_run(leg["run"])
        vv = RG.verificar(s, rr)
        ok(vv.ok and RG.ler_json(s, rr, RG.N_INDICE)["versao"] == int(nome[1]),
           f"rodada legada no contrato {nome} continua legível e verificada")
    print(f"[check] CONCLUÍDO — {N} verificações")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
