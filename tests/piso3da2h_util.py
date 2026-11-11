"""Apoio dos testes do Piso 3D-A2-H (sem testes): microrredes do CATÁLOGO com PEMFC (+ FV, eólica, bateria e PCC).

Dados de TESTE, sintéticos e rotulados: o registro PEMFC usa o perfil REAL do SEEDS2 (``EQUIVALENT_65KW_HORIZON_
CONSTRAINED``, modelo físico aproximado); as condições físicas, P_min, rampa, permanências, preço do H₂ e estados
iniciais são DECLARAÇÕES de teste (procedência sintética). A política B04 do repositório (``b04-proposta-2``) foi APROVADA
pelo responsável (PR #23): os testes usam o caminho NORMAL. ``politica_pendente_no_teste`` simula a REVOGAÇÃO (situação
pendente no registro do núcleo) SÓ dentro de um teste, para provar que uma política não aprovada continua bloqueando.
"""
from __future__ import annotations

import contextlib
import copy

from integracao_v2 import curva_h2 as CH
from integracao_v2 import estrategia as E
from seeds2.microgrid import config as C
from seeds2.microgrid.references import PEMFC_REF_KEY

import piso3da2r_util as R
from piso3da_util import FONTE

NOMINAL = {"temperatura_stack_K": 353.15, "pressao_anodo_kPag": 140.0, "pressao_catodo_kPag": 120.0,
           "pressao_ambiente_kPa": 101.325}


def config_pemfc(nome: str = "Microrrede 3D-A2-H (teste)", *, quantidade: int = 1, fv: bool = False,
                 eolica: bool = False, **kw) -> dict:
    cfg = R.config_hibrida(nome, fv=fv, eolica=eolica, **kw)
    cfg["commissioning"]["completed"] = False
    C.add_equipment(cfg, C.new_equipment("pemfc", "PEMFC 01", tag="FC-01", params={
        "reference": PEMFC_REF_KEY, "quantity": quantidade, "power_basis": "entregue"}))
    cfg["commissioning"].update(completed=True, step=5, completed_at=C.utc_now())
    return cfg


def pemfc_id(doc: dict) -> str:
    return next(iter(E.pemfc_do_cenario(doc)))


def declarar_pemfc(bloco: dict, doc: dict, *, condicoes: dict | None = None, p_min: float = 10.0, preco: float = 40.0,
                   rampa: float = 120.0, t_on: float = 0.0, t_off: float = 0.0, abstracao: str = "instantanea_unidade_quente",
                   estados=None, eventos: tuple | None = None, t_amb: float = 25.0) -> dict:
    """Declarações PEMFC de TESTE (sintéticas) + termo combustivel_h2 (e 'eventos' se ``eventos`` = (C_SU, C_SD))."""
    b = E.atualizar_bloco(bloco, doc)
    eid = pemfc_id(doc)
    q = len(b["pemfc"][eid]["unidades"])
    est = estados or [("desligada", 0.0, 600.0)] * q
    b["pemfc"][eid].update(
        condicoes=dict(condicoes or NOMINAL), p_min_kW=p_min, rampa_kW_min=rampa, t_on_min=t_on, t_off_min=t_off,
        temperatura_ambiente_C=t_amb, preco_h2_R_kg=preco, abstracao=abstracao, limites_transicao="rampa_convencional",
        custo_partida_R=None if eventos is None else eventos[0], custo_parada_R=None if eventos is None else eventos[1],
        unidades=[{"estado": e, "potencia_kW": p, "tempo_no_estado_min": t} for e, p, t in est],
        procedencia={"tipo": "sintetico", "fonte": FONTE})
    termos = list(b["objetivo"]["termos"])
    for t in ("combustivel_h2",) + (("eventos",) if eventos is not None else ()):
        if t not in termos:
            termos.append(t)
    b["objetivo"]["termos"] = termos
    return b


def estado_cenario(doc: dict, estados) -> None:
    """Estado inicial AGREGADO do registro no cenário (Piso 2A), coerente com os estados por unidade declarados."""
    eid = pemfc_id(doc)
    on = [e for e in estados if e[0] == "em_operacao"]
    doc["initialization"]["equipment"][eid].update(
        state="em_operacao" if on else "desligada", units_on=len(on), power_kW=sum(p for _e, p, _t in on))


def criar_cenario_pemfc(store, *, estados=None, renov: bool = False, pemfc_kw: dict | None = None, mutar=None, **kw):
    """Cenário V2 completo com PEMFC declarada (e renováveis declaradas quando o inventário as tiver)."""
    estados_ = estados

    def mut(doc):
        q = len(E.pemfc_do_cenario(doc) and doc[E.CHAVE_BLOCO]["pemfc"][pemfc_id(doc)]["unidades"]) \
            if E.CHAVE_BLOCO in doc and "pemfc" in doc[E.CHAVE_BLOCO] else 1
        est = estados_ or [("desligada", 0.0, 600.0)] * max(q, 1)
        doc[E.CHAVE_BLOCO] = declarar_pemfc(doc[E.CHAVE_BLOCO], doc, estados=est, **(pemfc_kw or {}))
        estado_cenario(doc, est)
        if mutar is not None:
            mutar(doc)
    if not renov:
        kw.setdefault("clima", lambda doc: R.clima_tabela(doc, {"ghi_W_m2": [0.0] * 12, "temperature_C": [25.0] * 12,
                                                                "wind_speed_m_s": [0.0] * 12}))
    return R.criar_cenario_hibrido(store, mutar=mut, **kw)


@contextlib.contextmanager
def politica_pendente_no_teste():
    """REVOGAÇÃO SIMULADA da aprovação B04 (só no teste; restaurada ao sair). A autoridade é o registro do NÚCLEO
    (``ems_v2.contracts.POLITICAS_B04_NUCLEO``): a situação da política CONGELADA volta a pendente lá, pela identidade do
    seu conteúdo; o dicionário da integração acompanha (o certificado declara a mesma situação que o núcleo)."""
    from ems_v2 import contracts as K
    original = copy.deepcopy(CH.POLITICA_B04)
    h = CH.hash_politica_nucleo()
    reg = K.POLITICAS_B04_NUCLEO[h]                 # KeyError ⇒ a política da integração não é a congelada no núcleo
    sit0 = reg["situacao"]
    reg["situacao"] = "proposta_congelada_pendente_de_aprovacao"
    CH.POLITICA_B04["situacao"] = "proposta_congelada_pendente_de_aprovacao"
    try:
        yield
    finally:
        reg["situacao"] = sit0
        CH.POLITICA_B04.clear()
        CH.POLITICA_B04.update(original)


__all__ = ["NOMINAL", "config_pemfc", "criar_cenario_pemfc", "declarar_pemfc", "estado_cenario", "pemfc_id",
           "politica_pendente_no_teste"]
