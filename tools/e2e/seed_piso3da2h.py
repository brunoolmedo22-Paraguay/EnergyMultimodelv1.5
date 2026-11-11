"""Prepara um SEEDS2_DATA_DIR VAZIO para o E2E do Piso 3D-A2-H (``e2e_piso3da2h.js``), com a política B04 do
REPOSITÓRIO (``b04-proposta-2``, aprovada pelo responsável no PR #23) — nenhuma aprovação simulada.

Cria no catálogo (dados FICTÍCIOS, sintéticos e rotulados; modelos físicos reais do código):

* «Microrrede E2E 3D-A2-H»: FV + eólica + bateria + PEMFC (perfil EQUIVALENT_65KW_HORIZON_CONSTRAINED) + PCC, com um
  cenário V2 cujas declarações PEMFC e RENOVÁVEIS ficam VAZIAS (o E2E as preenche pela interface); demanda 40 kW,
  importação limitada a 25 kW, previsões de demanda e clima sintéticas;
* duas microrredes com rodadas gravadas EXATAMENTE nos contratos ANTERIORES (o gravador é fixado na versão antiga, como
  nos testes ``test_caso9_…`` e ``test_rodada_renovavel_gravada_no_contrato_v2_…``): v1 (3D-A, só bateria) e v2
  (3D-A2-R, FV + eólica). O E2E confere que continuam legíveis e verificáveis depois do 3D-A2-H.

Escreve ``<dir>/../seed_piso3da2h.json`` com os UIDs das rodadas legadas. Uso: python tools/e2e/seed_piso3da2h.py <dir>
"""
from __future__ import annotations

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
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402

GHI = [0, 0, 0, 0, 0, 0, 100, 350, 600, 800, 950, 1000]
VENTO = [2.0, 3.0, 9.0, 10.0, 11.0, 12.0, 12.0, 10.0, 4.0, 3.0, 2.5, 2.0]


def _clima(doc):
    return R.clima_tabela(doc, {"ghi_W_m2": GHI, "temperature_C": [20.0] * 12, "wind_speed_m_s": VENTO})


def _rodada_no_contrato(store, sc, versao: int):
    atual = RG.VERSAO
    RG.VERSAO = versao                      # grava EXATAMENTE como o piso anterior gravava
    try:
        run = X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    finally:
        RG.VERSAO = atual
    if run.state != "concluida":
        raise SystemExit(f"rodada legada v{versao} não concluiu: {run.error}")
    return run


def main(data_dir: str) -> None:
    reg = MicrogridRegistry(data_dir)
    if reg.entries():
        raise SystemExit("O diretório não está vazio: use um SEEDS2_DATA_DIR novo para o E2E.")
    cfg = H.config_pemfc("Microrrede E2E 3D-A2-H", fv=True, eolica=True)
    reg.create(cfg, origin="commissioning")

    def vazio(doc):
        b = doc[E.CHAVE_BLOCO]
        eid = H.pemfc_id(doc)
        b["pemfc"][eid] = E._pemfc_vazia(E.pemfc_do_cenario(doc)[eid])          # declarações PEMFC VAZIAS
        for rid, ref in E.renovaveis_do_cenario(doc).items():                   # declarações renováveis VAZIAS
            b["renovaveis"][rid] = E._renovavel_vazia(ref["kind"])
        b["pcc"]["limite_importacao_kW"] = 25.0
    H.criar_cenario_pemfc(reg.open(cfg["installation"]["uid"]), nome="Híbrido FV + eólica + bateria + PEMFC + PCC",
                          demanda_kW=40.0, renov=True, clima=_clima, mutar=vazio)

    legado = {}
    c1 = U.config_bateria("Microrrede E2E legado 3D-A (contrato v1)")
    reg.create(c1, origin="commissioning")
    s1 = reg.open(c1["installation"]["uid"])
    r1 = _rodada_no_contrato(s1, U.criar_cenario_v2(s1, nome="Rodada legada 3D-A"), 1)
    legado["v1"] = {"mg": c1["installation"]["uid"], "run": r1.run_uid}
    c2 = R.config_hibrida("Microrrede E2E legado 3D-A2-R (contrato v2)")
    reg.create(c2, origin="commissioning")
    s2 = reg.open(c2["installation"]["uid"])
    r2 = _rodada_no_contrato(s2, R.criar_cenario_hibrido(s2, nome="Rodada legada 3D-A2-R", demanda_kW=40.0,
                                                          clima=_clima), 2)
    legado["v2"] = {"mg": c2["installation"]["uid"], "run": r2.run_uid}
    info = {"pemfc_mg": cfg["installation"]["uid"], "legado": legado}
    (Path(data_dir).resolve().parent / "seed_piso3da2h.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(f"OK: {data_dir} — microrrede híbrida {cfg['installation']['uid']}; rodadas legadas v1 {r1.run_uid[:8]}…, "
          f"v2 {r2.run_uid[:8]}…")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
