"""Prepara um SEEDS2_DATA_DIR VAZIO para a verificação do UI-FINISH-01 (``e2e_ui_finish.js``).

Dados FICTÍCIOS, sintéticos e rotulados (apoio ``tests/piso3da_util.py`` e ``tools/e2e/seed_piso3db.py``); motores e modelos
reais do código:

* «LAB-01 — Bateria e Rede (SINTÉTICA)»: banco de 20 kWh conectado, com
  - «EXP-02 — Arbitragem tarifária SOC 50%» (12 h, N = 3, m = 1, H_L = 10, tarifa 0,50 → 1,50 R$/kWh das 08h às 10h) e
    UMA missão V2 real concluída (HiGHS);
  - «Missão longa (acompanhamento)» (240 h; para acompanhar o modal por muitos ciclos de progresso);
  - «Cenário incompleto (bloqueado)» (motor V2 escolhido, estratégia ausente: o preflight V2 bloqueia);
  - uma rodada FALHA (da missão longa) gravada pela API do armazenamento como o runner a grava (diagnóstico);
* «Campus Piloto H₂ (SINTÉTICA)»: FV + eólica + bateria + PEMFC + PCC, com uma missão real concluída (figuras com várias séries);
* «Rascunho (SINTÉTICA)»: microrrede em comissionamento (cartão sem comissionamento concluído);
* o cenário EXP-02 arquivado no Arquivo Científico da instalação (estudo somente leitura).

Escreve ``<dir>/../seed_ui_finish.json`` com os UIDs. Uso: python tools/e2e/seed_ui_finish.py <dir>   (python COM Pyomo/HiGHS)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests"), str(RAIZ / "tools" / "e2e")]

import piso3da2h_util as H  # noqa: E402
import piso3da_util as U  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import execucao as X  # noqa: E402
from seed_piso3db import cenario as cenario_campus  # noqa: E402
from seeds2.archive import service as AS  # noqa: E402
from seeds2.archive.store import ArchiveStore  # noqa: E402
from seeds2.microgrid import config as C  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402

TARIFA_EXP02 = [0.5] * 8 + [1.5, 1.5] + [0.5] * 2


def main(data_dir: str) -> None:
    reg = MicrogridRegistry(data_dir)
    if reg.entries():
        raise SystemExit("O diretório não está vazio: use um SEEDS2_DATA_DIR novo.")
    # 1. LAB-01 (bateria + rede)
    lab = U.config_bateria("LAB-01 — Bateria e Rede (SINTÉTICA)")
    lab["installation"]["description"] = "Microrrede hipotética para validação do EMS V2 (dados sintéticos de teste)"
    reg.create(lab, origin="commissioning")
    sl = reg.open(lab["installation"]["uid"])
    exp = U.criar_cenario_v2(sl, nome="EXP-02 — Arbitragem tarifária SOC 50%", soc0=50.0, horas=12, N=3, H_L=10,
                             tarifa=TARIFA_EXP02)
    run = X.submit(sl, exp.scenario_uid, exp.version, X.new_request_id(), background=False)
    if run.state != "concluida":
        raise SystemExit(f"missão EXP-02 não concluiu: {run.error}")
    longa = U.criar_cenario_v2(sl, nome="Missão longa (acompanhamento)", horas=240, N=6, H_L=24,
                               tarifa=([0.5] * 8 + [1.5, 1.5] + [0.5] * 14) * 10)
    bloq = U.criar_cenario_v2(sl, nome="Cenário incompleto (bloqueado)", com_estrategia=False,
                              mutar=lambda d: d.__setitem__(E.CHAVE_MOTOR, E.MOTOR_V2))
    falha, _ = sl.start_run(run_uid="f" * 32, request_id="seed-ui-finish-falha", scenario_uid=longa.scenario_uid,
                            scenario_version=longa.version, scenario_fingerprint=longa.fingerprint,
                            manifest={"engine": {"id": E.MOTOR_V2}, "scenario": {"name": longa.name}}, owner=X.OWNER)
    sl.fail_run(falha.run_uid, X.OWNER, {"kind": "falha", "message": "RuntimeError: falha SINTÉTICA de teste na montagem"})
    # 2. Campus (várias séries)
    cfg = H.config_pemfc("Campus Piloto H₂ (SINTÉTICA)", fv=True, eolica=True, energia_kWh=120.0, ns=10, np_=16)
    reg.create(cfg, origin="commissioning")
    sc = reg.open(cfg["installation"]["uid"])
    camp = cenario_campus(sc, "Dia útil · m = 2")
    run_c = X.submit(sc, camp.scenario_uid, camp.version, X.new_request_id(), background=False)
    if run_c.state != "concluida":
        raise SystemExit(f"missão do campus não concluiu: {run_c.error}")
    # 3. microrrede em comissionamento
    rasc = C.new_config("Rascunho (SINTÉTICA)")
    reg.create(rasc, origin="commissioning")
    # 4. estudo arquivado
    estudo = AS.archive_scenario(sl, ArchiveStore(data_dir), exp.scenario_uid).study
    info = {"lab": lab["installation"]["uid"], "exp": exp.scenario_uid, "run": run.run_uid, "longa": longa.scenario_uid,
            "bloq": bloq.scenario_uid, "falha": falha.run_uid, "campus": cfg["installation"]["uid"], "camp": camp.scenario_uid,
            "run_campus": run_c.run_uid, "rascunho": rasc["installation"]["uid"], "estudo": estudo.archive_uid,
            "custo_exp02_R": run.summary["mission"]["custo_realizado_total_R"]}
    (Path(data_dir).resolve().parent / "seed_ui_finish.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(f"OK: {data_dir} — LAB-01 {info['lab'][:8]}… (EXP-02 {run.run_uid[:8]}…), campus {info['campus'][:8]}…, "
          f"estudo {estudo.archive_uid[:8]}…")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
