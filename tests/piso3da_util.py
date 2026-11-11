"""Apoio dos testes do Piso 3D-A (sem testes): microrredes do CATÁLOGO em diretório temporário e cenários V2.

Tudo aqui é dado de TESTE, sintético e rotulado (nenhuma instalação, tarifa, contrato ou medição real). A microrrede
mínima reproduz, sobre uma microrrede REGISTRADA pelo Gestor (documento v2 + ``MicrogridRegistry``), as condições do
experimento sintético H2 do Piso 3C-4 (demanda 10 kW; banco 20 kWh; PCC só importação 50 kW; tarifa 0,5 R$/kWh com pico
1,5 nas horas 8–9) — o resultado analítico conhecido (R$ 50,2 com custo de continuação; R$ 70,2 sem) serve de oráculo
INDEPENDENTE do código: a integração não usa ``ems_v2.fixtures_3c4`` em nenhum ponto.
"""
from __future__ import annotations

import copy

from integracao_v2 import estrategia as E
from seeds2.microgrid import config as C
from seeds2.operation import forecast_sources as FS
from seeds2.operation import service as SV
from seeds2.operation import strategy as SG

INICIO_LOCAL = "2026-01-01T00:00:00"
TARIFA_H2 = [0.5] * 8 + [1.5, 1.5] + [0.5, 0.5]
FONTE = "Declaração SINTÉTICA de teste do Piso 3D-A (não é dado de equipamento)"


def config_bateria(nome: str = "Microrrede 3D-A (teste)", *, modo: str = "conectada", energia_kWh: float = 20.0,
                   soc_fonte: str = "instalacao", extras=()) -> dict:
    """Microrrede comissionada com UM banco (limites de SOC 0–100 % definidos pela instalação) + equipamentos extras."""
    cfg = C.new_config(nome)
    cfg["installation"].update(description="Fixture de teste automatizado (3D-A)", nature="laboratorio", operation_mode=modo)
    C.add_equipment(cfg, C.new_equipment("battery", "Banco 01", tag="BAT-01", params={
        "energy_kWh": energia_kWh, "soc_min_pct": 0.0, "soc_max_pct": 100.0, "soc_limits_source": soc_fonte}))
    for eq in extras:
        C.add_equipment(cfg, eq)
    cfg["energy_balance"]["grid_connection"] = "conectada" if modo != "isolada" else "isolada"
    cfg["commissioning"].update(completed=True, step=5, completed_at=C.utc_now())
    return cfg


def bateria_id(cfg_ou_doc: dict) -> str:
    if "equipment" in cfg_ou_doc:
        return next(e["id"] for e in cfg_ou_doc["equipment"] if e["kind"] == "battery")
    return next(iter(E.baterias_do_cenario(cfg_ou_doc)))


def bloco_h2(doc: dict, *, tarifa=None, K: int = 12, N: int = 3, m: int = 1, H_L: int = 10, isolado: bool = False,
             realizada=None, pc_max: float = 5.0, pd_max: float = 10.0) -> dict:
    """Estratégia V2 COMPLETA (todas as declarações com procedência sintética rotulada)."""
    b = E.novo_bloco(doc)
    proc = {"tipo": "sintetico", "fonte": FONTE}
    b["declarante"] = {"tipo": "decisao_responsavel", "fonte": "Responsável pelo ensaio de teste 3D-A"}
    b["malha"] = {"delta_min": 60, "N": N, "m": m, "H_L": H_L}
    b["demanda"].update(criticidade="critica", semantica="media_intervalo", emissao_utc="2025-12-31T12:00:00+00:00")
    b["realizacao"] = {"tipo": "igual_a_previsao" if realizada is None else "serie_declarada",
                       "demanda_kW": None if realizada is None else [float(v) for v in realizada],
                       "procedencia": {"tipo": "sintetico", "fonte": "Realização sintética de teste 3D-A"}}
    for eid in b["baterias"]:
        b["baterias"][eid].update(eta_carga=1.0, eta_descarga=1.0, p_carga_barramento_kW=pc_max,
                                  p_descarga_barramento_kW=pd_max, hipotese_autodescarga="nao_modelada_alpha_1",
                                  custo_throughput_R_kWh=0.01, procedencia=dict(proc))
    b["objetivo"]["termos"] = ["throughput_bess"]
    if isolado:
        b["pcc"].update(modo="isolado_declarado", sentidos="nenhum", ajuste="sem_ajuste",
                        justificativa="Operação ISOLADA declarada para o ensaio de teste", procedencia=dict(proc))
    else:
        b["pcc"].update(modo="conectado", sentidos="somente_importacao", limite_importacao_kW=50.0,
                        disponibilidade="disponivel_em_toda_a_missao",
                        tarifa_importacao_R_kWh=list(TARIFA_H2[:K] if tarifa is None else tarifa),
                        remuneracao_exportacao="nao_aplicavel", tarifa_emissao_utc="2025-12-31T12:00:00+00:00",
                        tarifa_liquidacao="igual_a_tarifa_declarada", ajuste="ajuste_local_algebrico",
                        rotulo_tarifa="SINTÉTICA — não é tarifa real",
                        justificativa="PCC SINTÉTICO de teste: limite e tarifa declarados para o ensaio",
                        procedencia=dict(proc))
    b["planejador"].update(degradacao="sem_valor_futuro_rotulado", justificativa="Parâmetros numéricos dos ensaios 3C-4",
                           termo_longo={"tipo": "nenhum_declarado", "valores": {},
                                        "justificativa": "Fim da missão de teste: energia residual avaliada em zero por "
                                                         "declaração explícita"})
    return b


def demanda_sintetica(doc: dict, *, kW: float = 10.0, horas: int = 12, passo_s: int = 3600, fuso: str | None = "UTC"):
    return FS.synthetic_candidate("demanda_constante", {"t0": INICIO_LOCAL, "step_s": passo_s, "duration_s": horas * 3600,
                                                        "value_kW": kW}, timezone=fuso, inventory_ref=doc["inventory_ref"])


def criar_cenario_v2(store, *, nome: str = "Cenário V2 de teste", soc0: float = 100.0, horas: int = 12, bloco=None,
                     motor: str | None = E.MOTOR_V2, demanda_kW: float = 10.0, fuso: str | None = "UTC",
                     mutar=None, com_estrategia: bool = True, **kw_bloco):
    """Cria e SALVA um cenário V2 (demanda sintética horária, missão de ``horas`` h, estratégia completa).
    ``com_estrategia=False``: só estados, previsão e janela (motor e estratégia ficam para a interface)."""
    sc = SV.create(store, name=nome)
    doc = copy.deepcopy(sc.document)
    for eid in E.baterias_do_cenario(doc):
        doc["initialization"]["equipment"][eid]["soc0_pct"] = float(soc0)
    cand = demanda_sintetica(doc, kW=demanda_kW, horas=horas, fuso=fuso)
    assert cand.ok, [f.message for f in cand.analysis.findings]
    doc["forecasts"]["demand"] = cand.entry
    doc["mission"] = SG.default_mission(INICIO_LOCAL, fuso, horas * 60)
    if com_estrategia:
        if motor is not None:
            doc[E.CHAVE_MOTOR] = motor
        doc[E.CHAVE_BLOCO] = bloco_h2(doc, K=horas, **kw_bloco) if bloco is None else bloco
    if mutar is not None:
        mutar(doc)
    return SV.save(store, doc, sc.version, new_blobs=cand.blobs)


def regravar(store, stored, mutar):
    """Nova versão do cenário com ``mutar(doc)`` aplicado (as versões anteriores permanecem imutáveis)."""
    doc = copy.deepcopy(stored.document)
    mutar(doc)
    return SV.save(store, doc, stored.version)


__all__ = ["FONTE", "INICIO_LOCAL", "TARIFA_H2", "bateria_id", "bloco_h2", "config_bateria", "criar_cenario_v2",
           "demanda_sintetica", "regravar"]
