"""Leitura do catálogo de símbolos e do manifesto de equações (``ems_v2/catalogo``).

Status de símbolo (condição B da fiscalização):

* ``ativo_3A`` — parâmetro/derivado/conjunto efetivamente usado pelo contrato, pela referência ou pelo auditor;
* ``auditado_3A`` — variável cujo valor CANDIDATO é conferido pelo auditor; nenhum otimizador o decide no 3A;
* ``futuro`` — declarado na formulação, sem capacidade implementada (``implementacao`` vazia ou só ``contrato``);
* ``substituido`` — símbolo da v1.0 trocado pela adenda v1.1 (B01).

``variante``: ``comum`` | ``instantanea`` | ``multimodo`` (exclusivas da adenda B05).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

DIR = Path(__file__).resolve().parent / "catalogo"
STATUS_SIMBOLO = ("ativo_3A", "auditado_3A", "futuro", "substituido")
STATUS_EQUACAO = ("implementado_3A", "parcial_3A", "futuro", "substituida")
VARIANTES = ("comum", "instantanea", "multimodo")


def carregar_simbolos() -> list[dict]:
    with open(DIR / "simbolos_v1_1.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def carregar_equacoes() -> list[dict]:
    with open(DIR / "equacoes.json", encoding="utf-8") as f:
        return json.load(f)["equacoes"]


__all__ = ["DIR", "STATUS_EQUACAO", "STATUS_SIMBOLO", "VARIANTES", "carregar_equacoes", "carregar_simbolos"]
