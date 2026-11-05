"""Fixtures de teste do SEEDS2 (NÃO são dados de nenhuma instalação real).

``v16_equivalent_config`` monta uma microrrede cujo inventário reproduz exatamente a
configuração padrão do console V1.6 (``orchestrator_runtime.default_model_spec``), dividindo
os equipamentos em unidades físicas idênticas para exercitar a agregação do adaptador.
"""
from __future__ import annotations

from seeds2.microgrid import config as C


def v16_equivalent_config(name: str = "Microrrede de teste") -> dict:
    cfg = C.new_config(name)
    inst = cfg["installation"]
    inst.update(description="Fixture de teste automatizado", nature="laboratorio", operation_mode="isolada",
                location="Laboratório de teste")
    # Solar: CS7L-590MS 2 × 10 → dois arranjos idênticos de 2 × 5
    for i in (1, 2):
        C.add_equipment(cfg, C.new_equipment("pv", f"Arranjo FV {i}", tag=f"PV-0{i}", params={
            "reference": "CS7L-590MS", "n_series": 2, "n_parallel": 5, "soiling_pct": 0.0}))
    # PEMFC: 4 sistemas → 3 + 1
    C.add_equipment(cfg, C.new_equipment("pemfc", "Bloco PEMFC A", tag="FC-A", params={"quantity": 3}))
    C.add_equipment(cfg, C.new_equipment("pemfc", "Bloco PEMFC B", tag="FC-B", params={"quantity": 1}))
    # Bateria: Tremblay Li-ion 200 × 132 → dois bancos de 200 × 66
    for i in (1, 2):
        C.add_equipment(cfg, C.new_equipment("battery", f"Banco de baterias {i}", tag=f"BAT-0{i}", params={
            "reference": "tremblay:liion_3p3v_2p3ah", "n_series": 200, "n_parallel": 66, "soc0_pct": 60.0,
            "soc_min_pct": 20.0, "soc_max_pct": 90.0, "c_discharge": 1.0, "c_charge": 0.5}))
    cfg["topology"].update(bus_kind="CC", grid_connection="isolada", load_coupling="conversor_cc_cc")
    for eq in cfg["equipment"]:
        cfg["topology"]["couplings"][eq["id"]] = {"pv": "conversor_cc_cc", "pemfc": "conversor_cc_cc",
                                                  "battery": "conversor_bidirecional"}[eq["kind"]]
    cfg["demand"].update(source="walkforward", provenance="referencia",
                         walkforward={"scenario": "Ideal", "profile": "Normal", "start_hour": 12})
    cfg["climate"].update(source="sintetico", provenance="sintetico")
    cfg["commissioning"].update(completed=True, step=5, completed_at=C.utc_now())
    return cfg
