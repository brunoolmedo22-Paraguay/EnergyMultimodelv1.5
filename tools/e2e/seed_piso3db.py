"""Prepara um SEEDS2_DATA_DIR VAZIO para o E2E do Piso 3D-B (``e2e_piso3db_partitura.js``) — Partitura / motor Trama.

Cria no catálogo (dados FICTÍCIOS, sintéticos e rotulados; motores e modelos reais do código):

* «Campus Piloto H₂ (SINTÉTICA)»: FV + eólica + bateria + PEMFC + PCC, cenário V2 «Dia útil · m = 2» (24 h, demanda e clima
  declarados ponto a ponto, tarifa em três patamares, importação limitada) e UMA missão real concluída (HiGHS); mais um
  segundo cenário, «Dia nublado · m = 2» (irradiância reduzida), com a sua própria missão concluída (troca de rodada);
* «Industrial A (SINTÉTICA · padrão V1.6)» com uma rodada V1.6 concluída (compatibilidade do motor anterior);
* o cenário V2 arquivado no Arquivo Científico da instalação (estudo somente leitura).

Escreve ``<dir>/../seed_piso3db.json`` com os UIDs. Uso: python tools/e2e/seed_piso3db.py <dir>   (python COM Pyomo/HiGHS)
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

import piso3da2h_util as H  # noqa: E402
import piso3da2r_util as R  # noqa: E402
import piso3da_util as U  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import execucao as X  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from seeds2.archive import service as AS  # noqa: E402
from seeds2.archive.store import ArchiveStore  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.operation import forecast_sources as FS  # noqa: E402
from seeds2.operation import runner  # noqa: E402
from seeds2.operation import service as SV  # noqa: E402
from seeds2.operation import strategy as SG  # noqa: E402
from seeds2_fixtures import v16_equivalent_config  # noqa: E402
from test_seeds2_piso2c import ready  # noqa: E402

DEM = [30, 28, 27, 27, 29, 34, 42, 50, 55, 53, 50, 48, 49, 51, 52, 54, 58, 66, 74, 76, 70, 58, 44, 34]
GHI = [0, 0, 0, 0, 0, 0, 60, 240, 470, 690, 860, 960, 990, 930, 790, 590, 360, 140, 10, 0, 0, 0, 0, 0]
TEMP = [19, 18, 18, 17, 17, 18, 19, 21, 23, 25, 27, 28, 29, 29, 28, 27, 25, 23, 22, 21, 20, 20, 19, 19]
VENTO = [6.5, 7.0, 7.5, 7.0, 6.0, 5.0, 4.5, 4.0, 3.5, 3.0, 3.0, 3.5, 4.0, 4.0, 4.5, 5.0, 5.0, 4.5, 4.0, 4.5, 5.5, 6.5, 7.0, 7.0]
TARIFA = [0.38] * 6 + [0.62] * 12 + [1.65] * 3 + [0.62] * 3


def cenario(st, nome: str, *, f_ghi: float = 1.0):
    sc = SV.create(st, name=nome)
    doc = copy.deepcopy(sc.document)
    for eid in E.baterias_do_cenario(doc):
        doc["initialization"]["equipment"][eid]["soc0_pct"] = 50.0
    tab = FS.regular_table(("demand_kW",), U.INICIO_LOCAL, 3600, 24, {"demand_kW": [float(v) for v in DEM]})
    dem = FS.manual_candidate(tab, "demand", timezone="UTC", inventory_ref=doc["inventory_ref"], provenance="sintetico")
    assert dem.ok, [f.message for f in dem.analysis.findings]
    cl = R.clima_tabela(doc, {"ghi_W_m2": [float(v) * f_ghi for v in GHI], "temperature_C": [float(v) for v in TEMP],
                              "wind_speed_m_s": VENTO})
    doc["forecasts"]["demand"], doc["forecasts"]["climate"] = dem.entry, cl.entry
    doc["mission"] = SG.default_mission(U.INICIO_LOCAL, "UTC", 24 * 60)
    doc[E.CHAVE_MOTOR] = E.MOTOR_V2
    b = R.declarar_renovaveis(U.bloco_h2(doc, K=24, N=6, m=2, H_L=12, tarifa=TARIFA, pc_max=30.0, pd_max=40.0), doc)
    est = [("desligada", 0.0, 600.0)]
    b = H.declarar_pemfc(b, doc, estados=est, preco=14.0)
    H.estado_cenario(doc, est)
    b["pcc"]["limite_importacao_kW"] = 35.0
    doc[E.CHAVE_BLOCO] = b
    return SV.save(st, doc, sc.version, new_blobs={**dem.blobs, **cl.blobs})


def main(data_dir: str) -> None:
    reg = MicrogridRegistry(data_dir)
    if reg.entries():
        raise SystemExit("O diretório não está vazio: use um SEEDS2_DATA_DIR novo para o E2E.")
    cfg = H.config_pemfc("Campus Piloto H₂ (SINTÉTICA)", fv=True, eolica=True, energia_kWh=120.0, ns=10, np_=16)
    reg.create(cfg, origin="commissioning")
    st = reg.open(cfg["installation"]["uid"])
    sc = cenario(st, "Dia útil · m = 2")
    run = X.submit(st, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    if run.state != "concluida":
        raise SystemExit(f"missão V2 não concluiu: {run.error}")
    sc2 = cenario(st, "Dia nublado · m = 2", f_ghi=0.35)
    run2 = X.submit(st, sc2.scenario_uid, sc2.version, X.new_request_id(), background=False)
    if run2.state != "concluida":
        raise SystemExit(f"segunda missão V2 não concluiu: {run2.error}")
    c16 = v16_equivalent_config("Industrial A (SINTÉTICA · padrão V1.6)")
    reg.create(c16, origin="commissioning")
    s16 = reg.open(c16["installation"]["uid"])
    sc16 = ready(s16, name="Alta demanda")
    r16 = runner.submit(s16, sc16.scenario_uid, sc16.version, runner.new_request_id(), background=False)
    if r16.state != "concluida":
        raise SystemExit(f"rodada V1.6 não concluiu: {r16.error}")
    estudo = AS.archive_scenario(st, ArchiveStore(data_dir), sc.scenario_uid).study
    it = json.loads(json.dumps(run.summary["mission"]))
    ja = RG.ler_csv(st, run, RG.N_JANELAS)
    validas = [int(j) for j, q in zip(ja["janela"], ja["sinal_qualidade"], strict=True) if q == "valido"]
    sem = [int(j) for j, q in zip(ja["janela"], ja["sinal_qualidade"], strict=True) if q != "valido"]
    if not validas or not sem:
        raise SystemExit("a missão de referência deve ter janelas com e sem sinal de valor futuro válido")
    info = {"mg": cfg["installation"]["uid"], "sc": sc.scenario_uid, "run": run.run_uid, "cenario": sc.name,
            "custo_R": it["custo_realizado_total_R"], "demanda_18h_kW": float(DEM[18]),
            "janelas": len(ja), "j_com": validas[0], "j_sem": sem[0], "n_validas": len(validas),
            "arquivos": len(run.data), "linhas_planos": len(RG.ler_csv(st, run, RG.N_PLANOS)),
            "sc2": sc2.scenario_uid, "run2": run2.run_uid, "cenario2": sc2.name,
            "custo2_R": run2.summary["mission"]["custo_realizado_total_R"],
            "v16": {"mg": c16["installation"]["uid"], "sc": sc16.scenario_uid, "run": r16.run_uid},
            "estudo": estudo.archive_uid}
    (Path(data_dir).resolve().parent / "seed_piso3db.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(f"OK: {data_dir} — microrrede {info['mg']} · rodadas V2 {run.run_uid[:8]}… e {run2.run_uid[:8]}… · V1.6 {r16.run_uid[:8]}… · estudo "
          f"{estudo.archive_uid[:8]}…")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
