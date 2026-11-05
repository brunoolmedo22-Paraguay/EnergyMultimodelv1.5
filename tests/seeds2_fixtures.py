"""Fixtures de teste do SEEDS2 (NÃO são dados de nenhuma instalação real).

``v16_equivalent_config`` monta uma microrrede (documento v2) cujo inventário reproduz exatamente a
configuração padrão do console V1.6 (``orchestrator_runtime.default_model_spec``), dividindo os
equipamentos em unidades físicas idênticas para exercitar a agregação do adaptador:

* duas usinas FV, cada uma com UM arranjo CS7L-590MS 2 × 5;
* dois blocos PEMFC (3 + 1 sistemas);
* dois bancos Tremblay Li-ion 200 × 66 (limites de SOC 20/90 %, taxas 1C/0,5C), SOC inicial 60 % nas
  condições da rodada (fora do inventário).
"""
from __future__ import annotations

from pathlib import Path

from seeds2.microgrid import config as C

FIXTURES = Path(__file__).resolve().parent / "fixtures"
V1_CONFIG = FIXTURES / "seeds2_config_v1.json"        # documento v1 real (gerado pelo código do main 67a7a6f)
V1_BACKUP = FIXTURES / "seeds2_backup_v1_piso1.zip"   # backup v1 real (mesma origem)


def battery_params(np_: int = 66, **over) -> dict:
    p = {"model_reference": "tremblay:liion_3p3v_2p3ah", "model_n_series": 200, "model_n_parallel": np_,
         "soc_min_pct": 20.0, "soc_max_pct": 90.0, "soc_limits_source": "instalacao",
         "c_discharge_max": 1.0, "c_charge_max": 0.5}
    p.update(over)
    return p


def pv_plant(name: str, *arrays: dict, **fields) -> dict:
    return C.new_equipment("pv", name, arrays=list(arrays), **fields)


def module_array(name: str = "Arranjo 01", reference: str = "CS7L-590MS", ns: int = 2, np_: int = 5, soiling: float = 0.0) -> dict:
    return C.new_array(name, mode="modulo", reference=reference, n_series=ns, n_parallel=np_, soiling_pct=soiling)


def v16_equivalent_config(name: str = "Microrrede de teste") -> dict:
    cfg = C.new_config(name)
    inst = cfg["installation"]
    inst.update(description="Fixture de teste automatizado", nature="laboratorio", operation_mode="isolada")
    inst["location"]["address"] = "Laboratório de teste"
    for i in (1, 2):
        C.add_equipment(cfg, pv_plant(f"Arranjo FV {i}", module_array(), tag=f"PV-0{i}"))
    C.add_equipment(cfg, C.new_equipment("pemfc", "Bloco PEMFC A", tag="FC-A", params={"quantity": 3}))
    C.add_equipment(cfg, C.new_equipment("pemfc", "Bloco PEMFC B", tag="FC-B", params={"quantity": 1}))
    for i in (1, 2):
        b = C.add_equipment(cfg, C.new_equipment("battery", f"Banco de baterias {i}", tag=f"BAT-0{i}",
                                                 params=battery_params()))
        cfg["run_conditions"]["battery_soc0_pct"][b["id"]] = 60.0
    cfg["energy_balance"]["grid_connection"] = "isolada"
    cfg["demand"].update(source="walkforward", provenance="referencia",
                         walkforward={"scenario": "Ideal", "profile": "Normal", "start_hour": 12})
    cfg["climate"].update(source="sintetico", provenance="sintetico")
    cfg["commissioning"].update(completed=True, step=5, completed_at=C.utc_now())
    return cfg
