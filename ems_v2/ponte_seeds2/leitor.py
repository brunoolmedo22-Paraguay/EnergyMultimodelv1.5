"""Leitura de microrredes e cenários REAIS do SEEDS2 para os contratos da ponte 3C-0 (somente leitura).

* ``inventario_de_documento`` — documento v2 de configuração (dict) → ``InventarioMicrorrede`` POR DISPOSITIVO:
  cada registro ``eq-…`` e cada arranjo ``arr-…`` com seus valores, unidade da fonte, caminho no documento e
  procedência. Reutiliza as especificações de parâmetros do Piso 1 (``seeds2.microgrid.config.PARAM_SPECS`` /
  ``ARRAY_SPECS``), as derivações nominais (``derived``), os catálogos (``references``) e as impressões digitais do
  Piso 2A (``seeds2.operation.scenarios``). NÃO usa o adaptador V1.6 (``adapter.build_plan``): nenhuma agregação.
* ``ler_inventario`` — abre a microrrede PELO CATÁLOGO (``MicrogridRegistry.open``: incarnação conferida,
  ``must_exist``) e lê revisão atual + incarnação num ÚNICO instantâneo (``MicrogridStore.snapshot``), ou uma revisão
  fixada (``get_revision``).
* ``cenario_de_versao`` / ``ler_cenario`` — versão IMUTÁVEL do cenário → ``CenarioEMS`` (referência ao inventário +
  condições iniciais declaradas, SOC em % convertido explicitamente para fração).
* ``constatacoes_previsoes_seeds2`` — o que impede hoje usar as previsões do Piso 2B no EMS V2 (sem converter nada).
"""
from __future__ import annotations

import hashlib
from typing import Any

from seeds2.microgrid import config as C
from seeds2.microgrid.derived import battery_derived, pv_array_nominal
from seeds2.microgrid.references import PEMFC_REF_KEY, wind_references
from seeds2.operation import scenarios as SC

from ..diagnostics import Constatacao, aviso, pendente
from ..parameters import Parametro
from ..provenance import Procedencia
from ..ponte import CONTRATO_VERSAO
from ..ponte.cenario import CenarioEMS, CondicaoInicialDispositivo, ReferenciaInventario
from ..ponte.inventario import (AssociacaoModelo, DispositivoInventario, IdentidadeMicrorrede, InventarioMicrorrede,
                                ValorInventario)

TIPO_POR_KIND = {"pv": "pv_usina", "wind": "eolica", "battery": "bateria", "pemfc": "pemfc", "thermal": "termica"}
MODELO_POR_TIPO = {
    "pv_usina": ("(agrupador de arranjos)", "agrupador", None),
    "pv_arranjo": ("models.pv_module / simulate_noct_efficiency_model", "renovavel", "fv"),
    "eolica": ("models.wind_model / run_wind_model", "renovavel", "eolica"),
    "bateria": ("models.battery_model", "armazenamento", None),
    "pemfc": ("h2_pemfc (Equivalent65kWHorizonDynamicModel)", "gerador", "pemfc"),
    "termica": ("models.thermal_model (pequena unidade geradora)", "gerador", "termica"),
}
_COSMETICO_ARRANJO = ("name", "notes")


def _proc_doc(uid: str, revisao: int, caminho: str, impressao: str) -> Procedencia:
    return Procedencia("declarado_seeds2", f"SEEDS2 · microrrede {uid} · documento de configuração", caminho,
                       sha256=impressao, observacoes=f"revisão {revisao}")


def _valor(chave: str, unidade: str, caminho: str, bruto: Any, proc: Procedencia, *, sugerido: bool = False) -> ValorInventario:
    if bruto is None:
        return ValorInventario(chave, unidade, caminho, "ausente", None)
    if sugerido:
        p = Procedencia("nao_declarado", "SEEDS2 · valor inicial sugerido (não confirmado pelo usuário)", caminho)
        origem = "inventario_sugerido_seeds2"
    else:
        p, origem = proc, "inventario_declarado"
    if isinstance(bruto, bool):
        return ValorInventario(chave, unidade, caminho, origem, p, logico=bruto)
    if isinstance(bruto, (int, float)):
        return ValorInventario(chave, unidade, caminho, origem, p, numero=float(bruto))
    return ValorInventario(chave, unidade, caminho, origem, p, texto=str(bruto))


def _derivado(chave: str, unidade: str, caminho: str, numero: float | None, proc: Procedencia, relacao: str,
              origem: str = "derivado") -> ValorInventario | None:
    if numero is None:
        return None
    return ValorInventario(chave, unidade, caminho, origem, proc, numero=float(numero), derivacao=relacao)


def _fp_arranjo(a: dict) -> str:
    phys = {k: v for k, v in a.items() if k not in _COSMETICO_ARRANJO}
    return hashlib.sha256(C.canonical_json(phys).encode("utf-8")).hexdigest()


def _dispositivo(uid_mg: str, eq_id: str, tipo: str, nome: str, tag: str, habilitado: bool, pai: str | None,
                 quantidade: int | None, referencia: str | None, valores: list, impressao: str) -> DispositivoInventario:
    mod, papel, tec = MODELO_POR_TIPO[tipo]
    return DispositivoInventario(eq_id, uid_mg, tipo, nome, tag, habilitado, "presente", pai, quantidade,
                                 AssociacaoModelo(mod, referencia, papel, tec),
                                 tuple(v for v in valores if v is not None), impressao)


def inventario_de_documento(config: dict, *, revisao: int, impressao_config: str,
                            incarnacao: str | None) -> InventarioMicrorrede:
    inst = config.get("installation") or {}
    uid = str(inst.get("uid", ""))
    disp: list[DispositivoInventario] = []

    def proc(caminho: str) -> Procedencia:
        return _proc_doc(uid, revisao, caminho, impressao_config)

    for eq in config.get("equipment", []):
        kind, eid, params = eq["kind"], eq["id"], eq.get("params") or {}
        tipo = TIPO_POR_KIND[kind]
        base = f"equipment[{eid}].params"
        vals: list = []
        for spec in C.PARAM_SPECS[kind]:
            cam = f"{base}.{spec.name}"
            sug = kind == "battery" and spec.name in ("soc_min_pct", "soc_max_pct") \
                and (params.get("soc_limits_source") or "sugerido") == "sugerido"
            vals.append(_valor(spec.name, spec.unit, cam, params.get(spec.name), proc(cam), sugerido=sug))
        quantidade, referencia = None, params.get("reference")
        if kind == "battery":
            referencia = params.get("model_reference")
            e_mod = C.battery_model_energy_kWh(eq)
            d = battery_derived(params, e_mod)
            e, base_e, rel = d["energy_kWh"]
            if base_e == "derivada":
                vals.append(_derivado("energy_kWh_derivada", "kWh", f"{base}.voltage_V×capacity_Ah", e,
                                      proc(f"{base}.voltage_V,capacity_Ah"), rel))
            if e_mod is not None:
                vals.append(_derivado("energy_kWh_modelo", "kWh", f"{base}.model_*", e_mod,
                                      Procedencia("referencia", "models/battery_model.py (célula de referência)",
                                                  str(params.get("model_reference")),
                                                  observacoes="Parametrização do modelo científico; não é datasheet."),
                                      "E = V_célula·Q_célula·Ns·Np/1000", origem="catalogo_referencia"))
            e_ef = e if e is not None else e_mod
            for lado, chave in (("charge", "p_carga_terminal_kW"), ("discharge", "p_descarga_terminal_kW")):
                c_rate = d[f"c_{lado}"][0]
                if c_rate is not None and e_ef is not None:
                    vals.append(_derivado(chave, "kW", f"{base}.c_{lado}_max", c_rate * e_ef, proc(f"{base}.c_{lado}_max"),
                                          "P_terminal = C·E (terminal CC do banco; NÃO é potência no barramento)"))
        elif kind == "wind":
            q = params.get("count")
            quantidade = q if isinstance(q, int) and not isinstance(q, bool) else None
            ref = wind_references().get(params.get("reference") or "")
            if ref is not None:
                vals.append(_derivado("p_nominal_unidade_kW", "kW", f"{base}.reference", ref.summary["P_nominal [kW]"],
                                      Procedencia("referencia", "config/wind_turbine_database.py", ref.key,
                                                  observacoes=ref.provenance), "Potência nominal do catálogo (por turbina)",
                                      origem="catalogo_referencia"))
        elif kind == "pemfc":
            q = params.get("quantity")
            quantidade = q if isinstance(q, int) and not isinstance(q, bool) else None
            if params.get("reference") == PEMFC_REF_KEY:
                from seeds2.microgrid.references import pemfc_max_net_power_kW
                vals.append(_derivado("p_max_liquida_unidade_kW", "kW", f"{base}.reference", pemfc_max_net_power_kW(),
                                      Procedencia("referencia", "h2_pemfc · Equivalent65kWHorizonDynamicModel",
                                                  PEMFC_REF_KEY, observacoes="Perfil APROXIMADO; sem validação em "
                                                  "equipamento instalado (MODEL_CARD_HORIZON_APPROX)."),
                                      "P_max líquida física de UM sistema, calculada pelo modelo dinâmico de referência",
                                      origem="catalogo_referencia"))
        elif kind == "thermal":
            quantidade = None
            referencia = params.get("dynamic")
        if kind == "pv":
            disp.append(_dispositivo(uid, eid, "pv_usina", eq.get("name", ""), eq.get("tag", ""),
                                     bool(eq.get("enabled", True)), None, None, None, vals,
                                     SC.equipment_fingerprint(eq)))
            for a in eq.get("arrays") or []:
                abase = f"equipment[{eid}].arrays[{a['id']}]"
                avals = []
                for spec in C.ARRAY_SPECS:
                    cam = f"{abase}.{spec.name}"
                    sug = spec.name == "soiling_pct" and bool(a.get("soiling_default"))
                    avals.append(_valor(spec.name, spec.unit, cam, a.get(spec.name), proc(cam), sugerido=sug))
                nom = pv_array_nominal(a)
                if nom is not None:
                    avals.append(_derivado("p_stc_kW", "kW", f"{abase}.reference", nom["P_STC_kW"],
                                           Procedencia("referencia", "config/pv_database.py (datasheet STC)",
                                                       str(a.get("reference")), observacoes=nom["assumptions"]),
                                           "P_STC = P_mód·Ns·Np/1000 (STC; sem perdas)", origem="catalogo_referencia"))
                disp.append(_dispositivo(uid, a["id"], "pv_arranjo", f"{eq.get('name', '')} · {a.get('name', '')}",
                                         eq.get("tag", ""), bool(eq.get("enabled", True)), eid, None,
                                         a.get("reference"), avals, _fp_arranjo(a)))
            continue
        disp.append(_dispositivo(uid, eid, tipo, eq.get("name", ""), eq.get("tag", ""), bool(eq.get("enabled", True)),
                                 None, quantidade, referencia, vals, SC.equipment_fingerprint(eq)))
    obs = ("Valores do inventário SEEDS2 não registram documento de origem por parâmetro: procedência "
           "'declarado_seeds2' (rastreável à revisão), não ficha técnica conferida.",
           "Opções com valor padrão do Piso 1 (p. ex. base de potência PEMFC, perda genérica eólica) não distinguem "
           "escolha do usuário de padrão aceito.")
    return InventarioMicrorrede(
        CONTRATO_VERSAO,
        IdentidadeMicrorrede(uid, incarnacao, int(revisao), str(impressao_config), SC.inventory_fingerprint(config),
                             str(inst.get("name", ""))),
        inst.get("operation_mode"), (config.get("energy_balance") or {}).get("grid_connection"), tuple(disp),
        tuple(r.get("id") for r in config.get("retired", []) if isinstance(r, dict)),
        Procedencia("declarado_seeds2", f"SEEDS2 · microrrede {uid}", f"revisão {revisao}", sha256=impressao_config),
        obs)


def ler_inventario(registry, microrrede_uid: str, *, revisao: int | None = None) -> InventarioMicrorrede:
    """Instantâneo de UMA microrrede do catálogo (somente leitura; nada é gravado)."""
    store = registry.open(microrrede_uid)
    if revisao is None:
        with store.snapshot() as snap:
            stored, inc = snap.current(), snap.meta("incarnation")
        if stored is None:
            raise LookupError("Microrrede sem configuração salva.")
    else:
        stored, inc = store.get_revision(revisao), store.incarnation
    return inventario_de_documento(stored.config, revisao=stored.revision, impressao_config=stored.fingerprint,
                                   incarnacao=inc)


def _par(valor: Any, unidade: str, proc: Procedencia) -> Parametro | None:
    if valor is None or isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    if unidade == "%":
        return Parametro.de_bruto(float(valor), "%", proc)
    return Parametro(float(valor), unidade, proc)


def cenario_de_versao(stored) -> CenarioEMS:
    """``seeds2.microgrid.store.StoredScenario`` (versão imutável) → ``CenarioEMS``."""
    doc = stored.document
    ref = doc["inventory_ref"]
    mg = doc.get("microgrid") or {}
    conds = []
    for eid, st in sorted((doc.get("initialization") or {}).get("equipment", {}).items()):
        cam = f"initialization.equipment[{eid}]"
        p = Procedencia("declarado_seeds2", f"SEEDS2 · cenário {stored.scenario_uid}", cam, sha256=stored.fingerprint,
                        observacoes=f"versão {stored.version}")
        units = st.get("units_on")
        conds.append(CondicaoInicialDispositivo(
            eid, st.get("availability"), soc=_par(st.get("soc0_pct"), "%", p), estado_discreto=st.get("state"),
            unidades_ligadas=units if isinstance(units, int) and not isinstance(units, bool) else None,
            potencia_kW=_par(st.get("power_kW"), "kW", p)))
    return CenarioEMS(
        CONTRATO_VERSAO, stored.scenario_uid, int(stored.version), stored.fingerprint,
        ReferenciaInventario(str(mg.get("uid")), mg.get("incarnation"), int(ref["config_revision"]),
                             ref["config_fingerprint"], ref["inventory_fingerprint"]),
        tuple(conds), tuple(sorted(((doc.get("initialization") or {}).get("orphaned") or {}).keys())),
        Procedencia("declarado_seeds2", f"SEEDS2 · cenário {stored.scenario_uid}", f"versão {stored.version}",
                    sha256=stored.fingerprint))


def ler_cenario(registry, microrrede_uid: str, scenario_uid: str, version: int | None = None) -> CenarioEMS:
    return cenario_de_versao(registry.open(microrrede_uid).get_scenario(scenario_uid, version))


def constatacoes_previsoes_seeds2(doc: dict) -> list[Constatacao]:
    """Brechas entre as previsões do Piso 2B e o contrato de séries do EMS V2 (nada é convertido aqui)."""
    out: list[Constatacao] = []
    fc = doc.get("forecasts") or {}
    if not fc:
        out.append(pendente("previsoes_ausentes", "forecasts", "Cenário sem previsões gravadas."))
    for slot, e in sorted(fc.items()):
        cam = f"forecasts.{slot}"
        out.append(pendente("semantica_previsao_nao_declarada", cam,
                            "O Piso 2B não declara se os valores são média de intervalo ou amostra instantânea "
                            "(3A ``SEMANTICAS``); o EMS V2 não presume."))
        if e.get("step_s") != 60 or not e.get("regular"):
            out.append(pendente("resolucao_previsao_incompativel", cam,
                                f"Passo {e.get('step_s')!r} s / regular={e.get('regular')!r}: sem reamostragem no 3C-0."))
        if not e.get("timezone"):
            out.append(pendente("fuso_previsao_nao_declarado", cam, "Fuso não declarado: instantes UTC indeterminados."))
        if not e.get("created_at"):
            out.append(aviso("emissao_previsao_nao_registrada", cam,
                             "Instante de emissão da previsão não registrado: causalidade não verificável."))
        if slot == "climate":
            out.append(pendente("potencial_renovavel_requer_modelo_fisico", cam,
                                "Clima → potencial no barramento exige os modelos físicos (models/) por arranjo/turbina: "
                                "adaptador não implementado no 3C-0."))
    out.append(pendente("demanda_sem_uid_e_criticidade", "forecasts.demand",
                        "A demanda do SEEDS2 é um agregado sem UID de classe nem criticidade (decisão D01)."))
    return out


__all__ = ["cenario_de_versao", "constatacoes_previsoes_seeds2", "inventario_de_documento", "ler_cenario",
           "ler_inventario"]
