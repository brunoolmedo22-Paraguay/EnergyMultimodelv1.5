"""Apoio dos testes do Piso 3D-B (sem testes): UMA missão V2 real (HiGHS) sobre uma microrrede FICTÍCIA do catálogo.

Tudo aqui é dado de TESTE, sintético e rotulado. A microrrede (FV + eólica + bateria + PEMFC + PCC) e o cenário reutilizam
os utilitários dos Pisos 3D-A2-R/H; a rodada é executada pelo caminho normal e depois só LIDA pelos testes.
"""
from __future__ import annotations

import importlib.util

import piso3da2h_util as H
import piso3da2r_util as R
from integracao_v2 import estrategia as E
from integracao_v2 import execucao as X
from seeds2.microgrid.registry import MicrogridRegistry

SOLVER = importlib.util.find_spec("pyomo") is not None and importlib.util.find_spec("highspy") is not None
GHI = [0, 0, 0, 0, 0, 0, 100, 350, 600, 800, 950, 1000]
VENTO = [2, 3, 9, 10, 11, 12, 12, 10, 4, 3, 2.5, 2]


def missao_hibrida(data_dir: str, nome: str = "Microrrede 3D-B (teste)"):
    """Cria a microrrede, o cenário e executa a missão (12 h). Devolve (uid, store, rodada concluída)."""
    cfg = H.config_pemfc(nome, fv=True, eolica=True)
    MicrogridRegistry(data_dir).create(cfg)
    uid = cfg["installation"]["uid"]
    st = MicrogridRegistry(data_dir).open(uid)
    clima = lambda doc: R.clima_tabela(doc, {"ghi_W_m2": [float(v) for v in GHI], "temperature_C": [20.0] * 12,  # noqa: E731
                                             "wind_speed_m_s": [float(v) for v in VENTO]})
    sc = H.criar_cenario_pemfc(st, demanda_kW=40.0, renov=True, clima=clima, pemfc_kw={"preco": 10.0},
                               mutar=lambda doc: doc[E.CHAVE_BLOCO]["pcc"].update(limite_importacao_kW=25.0))
    run = X.submit(st, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    if run.state != "concluida":
        raise AssertionError(f"missão de teste não concluiu: {run.error}")
    return uid, st, run
