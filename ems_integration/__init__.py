"""Integração Energy MultiModel ↔ EMS de despacho ótimo (100 % Python).

Fluxo: módulos da plataforma → ``ponte`` (pacote de troca nos esquemas de CSV
do EMS) → ``executor`` (montar_fontes → despacho → relatório). Na V1.6, a UI principal consome essa cadeia através de ``orchestrator_runtime``; ``ems_app`` fica apenas como referência legada.
O EMS MATLAB original, do qual o núcleo foi portado, está em
``reference_models/ems_matlab``.
"""
from .executor import executar_pacote, validar_fc_dinamico
from .ponte import (PerfilCarga, caracterizar_bateria, caracterizar_fc, carga_copel, carga_de_dataframe,
                    carga_walkforward, disponibilidade_termica, escrever_pacote, opcoes_walkforward, recortar)

__all__ = [
    "PerfilCarga", "caracterizar_bateria", "caracterizar_fc", "carga_copel", "carga_de_dataframe",
    "carga_walkforward", "disponibilidade_termica", "escrever_pacote", "executar_pacote",
    "opcoes_walkforward", "recortar", "validar_fc_dinamico",
]
