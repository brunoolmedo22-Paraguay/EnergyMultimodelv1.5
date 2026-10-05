"""Parâmetros de referência para o módulo térmico V1.2.

Os presets de CVU são deliberadamente acadêmicos e editáveis. Eles não devem
ser interpretados como custo oficial de uma usina específica. O CVU real depende
principalmente do combustível contratado, eficiência, logística, transporte,
armazenamento, O&M variável, tributos e condições comerciais/operacionais.

Para estudos no SIN, o usuário deve substituir o preset pelo CVU da usina e do
período analisado (por exemplo, valores publicados por ONS/CCEE).
"""

from __future__ import annotations

THERMAL_PLANT = "thermal_plant"
LOCAL_GENERATOR = "local_generator"

DYNAMIC_LABELS = {
    THERMAL_PLANT: "Usina termelétrica de grande porte",
    LOCAL_GENERATOR: "Pequena unidade geradora",
}

# Valores iniciais apenas para simulação acadêmica. O usuário pode editar todos.
CVU_PRESETS = {
    "Gás natural": {
        "cvu_rs_mwh": 420.0,
        "typical_use": "Usina a gás / ciclo simples ou combinado",
        "note": "Preset acadêmico. Substituir pelo CVU específico da usina/período.",
    },
    "Óleo diesel": {
        "cvu_rs_mwh": 1100.0,
        "typical_use": "Grupo gerador diesel / térmica de custo elevado",
        "note": "Preset acadêmico de alto custo marginal; fortemente sensível ao preço e à logística do diesel.",
    },
    "Óleo combustível": {
        "cvu_rs_mwh": 700.0,
        "typical_use": "Usina térmica a óleo combustível",
        "note": "Preset acadêmico. Custos reais podem variar substancialmente por contrato e logística.",
    },
    "Carvão mineral": {
        "cvu_rs_mwh": 250.0,
        "typical_use": "Usina termelétrica a carvão",
        "note": "Preset acadêmico. Não representa uma usina específica.",
    },
    "Biomassa": {
        "cvu_rs_mwh": 180.0,
        "typical_use": "Cogeração / usina a biomassa",
        "note": "Preset acadêmico. O custo depende fortemente da disponibilidade e do contrato do combustível.",
    },
    "Biogás": {
        "cvu_rs_mwh": 300.0,
        "typical_use": "Gerador local ou planta a biogás",
        "note": "Preset acadêmico. Ajustar conforme produção, tratamento e armazenamento do biogás.",
    },
    "GLP": {
        "cvu_rs_mwh": 900.0,
        "typical_use": "Gerador térmico local / contingência",
        "note": "Preset acadêmico de geração distribuída. Ajustar ao preço local e à eficiência do equipamento.",
    },
}

DEFAULT_CVU_BY_DYNAMIC = {
    THERMAL_PLANT: "Gás natural",
    LOCAL_GENERATOR: "Óleo diesel",
}

SOURCE_NOTE = (
    "Os presets servem somente como ponto de partida acadêmico. Para estudos reais, "
    "informe o CVU da usina/equipamento e do período analisado. ONS e CCEE publicam "
    "bases de CVU de usinas térmicas brasileiras, mas o valor aplicável é específico."
)


def get_cvu_preset(fuel: str) -> dict:
    if fuel not in CVU_PRESETS:
        raise KeyError(f"Combustível não cadastrado: {fuel}")
    return dict(CVU_PRESETS[fuel])


def list_fuels() -> list[str]:
    return list(CVU_PRESETS.keys())
