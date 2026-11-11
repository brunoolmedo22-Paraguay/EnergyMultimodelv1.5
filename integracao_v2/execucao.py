"""Runner V2 (Piso 3D-A) — execução do EMS hierárquico MILP–MPC sobre a versão SALVA de um cenário do SEEDS2.

Mesmo ciclo de vida e as MESMAS garantias de armazenamento do runner V1.6 (``seeds2.operation.runner``, inalterado):
manifesto imutável gravado ao abrir a rodada, ``request_id`` idempotente, uma rodada ativa por microrrede, thread
própria, progresso real no banco, conclusão ATÔMICA (dados + resumo + estado) e recuperação de processos mortos. O
registro de rodadas vivas, o dono do processo e a exclusão mútua do motor são os do runner V1.6 (uma única fonte de
verdade para ``owner_is_dead``): nada é duplicado.

Fluxo (``submit``): preflight V2 (bloqueado ⇒ ``PreflightV2Error``, nada é aberto) → ``start_run`` com o manifesto →
thread: controlador hierárquico 3C-4 × planta algébrica, UMA janela por vez (``executar_missao_simulada`` do próprio
motor, com ``max_janelas = 1`` — o laço auditado não é reimplementado) → auditoria INTEGRAL independente → gravação.

Estados finais:

* ``concluida`` — missão COMPLETA (todos os intervalos aplicados) e auditoria integral aprovada; dados em
  ``scenario_run_data`` (``registro.dados_da_rodada``);
* ``interrompida`` — o controlador encerrou a missão por uma falha classificada (inviável, consigna inexequível…):
  nenhum dado de rodada concluída; evidência PARCIAL rotulada no ``outcome``; custo parcial nunca é custo da missão;
* ``falhou`` — solver indisponível, exceção, auditoria reprovada ou evidência incoerente (sem resultados concluídos);
* processo morto ⇒ ``interrompida`` pela recuperação existente (``runner.recover``), sem resultados.

Nunca há recaída para o motor V1.6.
"""
from __future__ import annotations

import hashlib
import platform
import threading
import time
import traceback
import uuid
from dataclasses import asdict
from pathlib import Path

from ems_v2 import FORMULACAO_3BP, FORMULACAO_3C1
from ems_v2.hierarquia import FORMULACAO_3C4
from ems_v2.milp.ambiente import verificar_ambiente
from ems_v2.rede import FORMULACAO_3C3

from seeds2.microgrid.store import MicrogridDeletedError, MissingStoreError, RunStateError, StoreError
from seeds2.operation import contracts
from seeds2.operation import runner as R16

from . import estrategia as E
from . import montagem as MT
from . import preflight as PF
from . import registro as RG

ROOT = Path(__file__).resolve().parents[1]
OWNER = R16.OWNER
# Código e dados que determinam uma rodada V2 (impressão própria: a do motor V1.6 NÃO cobre o pacote experimental e
# não é reinterpretada). Diretórios: todo ``.py``/``.csv``/``.json``.
SCIENCE_PATHS_V2 = ("ems_v2", "integracao_v2", "seeds2/operation/forecasts.py", "seeds2/operation/mission.py",
                    "seeds2/operation/scenarios.py", "seeds2/operation/strategy.py", "seeds2/microgrid/config.py",
                    "seeds2/microgrid/derived.py", "seeds2/microgrid/references.py",
                    # 3D-A2-R: modelos físicos e catálogos que derivam o potencial renovável
                    "simulation/multimodel.py", "models/pv_module.py", "models/temperature_model.py",
                    "models/irradiance_model.py", "models/wind_model.py", "config/pv_database.py",
                    "config/wind_turbine_database.py")
OBJETIVO = {
    "key": "custo_operativo_janela_mais_custo_futuro_3c4",
    "label": "MILP de cada janela: custo operativo previsto no horizonte curto + custo de continuação V̂ do planejador de "
             "longo prazo (instrumento de decisão; nunca contabilizado como custo realizado)",
    "terms": ["Importação da rede: h · c_imp · P_imp (tarifa declarada)", "Exportação remunerada: −h · c_exp · P_exp",
              "Throughput das baterias: h · c_thr · (P_c + P_d)", "Custo futuro estimado V̂(E) na fronteira terminal da janela"],
}
_FP: dict | None = None


class PreflightV2Error(StoreError):
    """O cenário não é executável pelo motor V2 (relatório em ``preflight``). Nada foi iniciado."""

    def __init__(self, pf: PF.PreflightV2):
        errs = [i.message for i in pf.items if i.level == PF.ERROR]
        super().__init__(f"{len(errs)} bloqueio(s) do preflight V2: " + " | ".join(errs[:3]))
        self.preflight = pf


# ====================================================================== procedência
def science_fingerprint() -> dict:
    """SHA-256 do código do motor V2 e da camada de integração efetivamente usados (mesma forma da impressão V1.6)."""
    global _FP
    if _FP is None:
        h = hashlib.sha256()
        n = 0
        for rel in SCIENCE_PATHS_V2:
            p = ROOT / rel
            items = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file() and "__pycache__" not in x.parts
                                                   and x.suffix in (".py", ".csv", ".json"))
            for f in items:
                h.update(str(f.relative_to(ROOT).as_posix()).encode())
                h.update(f.read_bytes())
                n += 1
        _FP = {"sha256": h.hexdigest(), "files": n, "paths": list(SCIENCE_PATHS_V2)}
    return dict(_FP)


def software_versions(ambiente: dict | None = None) -> dict:
    import numpy as np
    import pandas as pd

    from seeds2 import APP_NAME, APP_VERSION

    amb = ambiente if ambiente is not None else verificar_ambiente()
    v = amb.get("versoes") or {}
    return {"app": f"{APP_NAME} {APP_VERSION}",
            "runtime": "EMS V2 milp_mpc_v1 — ponte 3C-0/3C-1, rede 3C-3, MPC 3C-2 e hierarquia 3C-4 via integracao_v2 "
                       "(Piso 3D-A)",
            "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
            "pyomo": v.get("pyomo"), "highspy": v.get("highspy"), "highs": amb.get("versao_highs"),
            "solver_interface": amb.get("interface"), "solver_pinned": amb.get("fixadas"),
            "solver_divergences": amb.get("divergencias"), "science": science_fingerprint()}


def build_manifest(pf: PF.PreflightV2, run_uid: str, request_id: str) -> dict:
    stored = pf.scenario
    doc = stored.document
    fc = doc.get("forecasts") or {}
    keys = ("data", "blob", "source_type", "provenance", "label", "timezone", "timezone_source", "t0", "t_end", "step_s",
            "n_points", "variables", "transforms")
    ei = pf.engine_inputs()
    return R16._json_safe({
        "format": R16.RUN_FORMAT, "format_version": R16.RUN_FORMAT_VERSION, "run_uid": run_uid, "request_id": request_id,
        "reference": asdict(contracts.run_reference(stored)),
        "scenario": {"name": doc.get("name"), "description": doc.get("description"), "version": stored.version,
                     "fingerprint": stored.fingerprint},
        "engine": {"id": E.MOTOR_V2, "label": E.MOTORES[E.MOTOR_V2], "integration": "3D-A",
                   "formulations": {"nucleo": FORMULACAO_3BP, "commitment": FORMULACAO_3C1, "rede": FORMULACAO_3C3,
                                    "hierarquia": FORMULACAO_3C4},
                   "data_format": RG.FORMATO, "data_version": RG.VERSAO, "context": "ensaio", "synthetic": True},
        "software": software_versions(pf.ambiente or None),
        "objective": dict(OBJETIVO),
        "strategy": doc.get(E.CHAVE_BLOCO), "engine_fixed": dict(MT.FIXOS),
        "mission": {**(doc.get("mission") or {}), **(ei.get("grid") or {})},
        "forecasts": {slot: {k: e.get(k) for k in keys} for slot, e in fc.items()},
        "engine_inputs": ei, "preflight": pf.report(), "scope": PF.ESCOPO,
    })


# ====================================================================== execução
def prepare(store, scenario_uid: str, version: int | None = None) -> PF.PreflightV2:
    return PF.preparar(store, store.get_scenario(scenario_uid, version))


def submit(store, scenario_uid: str, version: int, request_id: str, *, background: bool = True):
    """Inicia a rodada V2 da versão ``version`` (gravada). Devolve a ``StoredRun`` (a existente, se o mesmo
    ``request_id`` já foi submetido). ``PreflightV2Error`` se bloqueado; ``RunBusyError`` se outra rodada está ativa."""
    pf = prepare(store, scenario_uid, version)
    if not pf.ok:
        raise PreflightV2Error(pf)
    run_uid = uuid.uuid4().hex                        # = missao_uid dos registros selados do motor
    with R16._LIVE_LOCK:
        R16._LIVE[run_uid] = None                     # registrada antes do INSERT: a recuperação não a julga morta
    try:
        run, created = store.start_run(run_uid=run_uid, request_id=request_id, scenario_uid=scenario_uid,
                                       scenario_version=int(version), scenario_fingerprint=pf.scenario.fingerprint,
                                       manifest=build_manifest(pf, run_uid, request_id), owner=OWNER,
                                       is_dead=R16.owner_is_dead)
    except BaseException:
        with R16._LIVE_LOCK:
            R16._LIVE.pop(run_uid, None)
        raise
    if not created:
        with R16._LIVE_LOCK:
            R16._LIVE.pop(run_uid, None)
        return run
    if background:
        t = threading.Thread(target=_executar, args=(store, run_uid, pf), name=f"seeds2-v2-run-{run_uid[:8]}", daemon=True)
        with R16._LIVE_LOCK:
            R16._LIVE[run_uid] = t
        t.start()
    else:
        with R16._LIVE_LOCK:
            R16._LIVE[run_uid] = threading.current_thread()
        try:
            _executar(store, run_uid, pf)
        finally:
            with R16._LIVE_LOCK:
                R16._LIVE.pop(run_uid, None)
    return store.get_run(run_uid)


def verificacao_dinamica(ev, mont) -> dict:
    """Consignas APLICADAS de cada unidade PEMFC avaliadas pelo modelo dinâmico (a posteriori; não altera nada)."""
    from . import pemfc_dinamica as DY
    base = ev.modelo.base
    est = {str(e.uid): e for e in base.estados_geradores}
    passos = sorted((p for r in ev.registros for p in r.conteudo.passos), key=lambda p: p.indice_global)
    out = {}
    for g in base.geradores:
        u = str(g.uid)
        x = mont.pemfc[u.split("#")[0]]
        e0 = est.get(u)
        sp = ev.modelo.compromisso.unidade(u)
        massas = (float(sp.massa_h2_partida_kg.valor) if sp.massa_h2_partida_kg is not None else 0.0,
                  float(sp.massa_h2_parada_kg.valor) if sp.massa_h2_parada_kg is not None else 0.0)
        out[u] = DY.verificar_despacho(x["condicoes"], x["curva"], float(x["temperatura_ambiente_C"]), ev.cfg.malha.delta_s,
                                       [float(p.aplicado[f"{u}|u"]) for p in passos],
                                       [float(p.aplicado[f"{u}|p"]) for p in passos],
                                       bool(e0.ligado) if e0 is not None else False,
                                       float(e0.p_anterior_kW.valor) if e0 is not None else 0.0, massas)
    return {"formato": "seeds2-milp-mpc-pemfc-dinamica", "versao": 2, "tolerancias": dict(DY.TOLERANCIAS),
            "modelo": "h2_pemfc.Equivalent65kWHorizonDynamicModel (condições declaradas por adaptador; passo interno 1 s)",
            "unidades": out, "coerente": all(v["coerente"] for v in out.values()),
            "nota": "Avaliação A POSTERIORI das consignas do EMS (abstração instantânea) pelo modelo dinâmico aproximado; "
                    "H₂ do EMS = q̂(p)·Δ·u + m_SU·y + m_SD·z (a contabilidade do MILP). Não é validação física e não "
                    "altera o despacho nem a planta algébrica."}


ROTULOS_ACEITACAO = {
    "algebrica_aprovada_dinamica_coerente": "Despacho ALGEBRICAMENTE aprovado e COERENTE com o modelo dinâmico aproximado "
                                            "nas tolerâncias declaradas (não é validação física).",
    "algebrica_aprovada_dinamica_incoerente": "Despacho ALGEBRICAMENTE aprovado, mas DINAMICAMENTE INCOERENTE: o modelo "
                                              "dinâmico NÃO segue as consignas aplicadas nas tolerâncias declaradas. A rodada "
                                              "NÃO representa operação executável do equipamento modelado.",
    "algebrica_aprovada_sem_pemfc": "Despacho ALGEBRICAMENTE aprovado (sem PEMFC: não há verificação dinâmica aplicável; "
                                    "não é validação física).",
}


def aceitacao(din: dict | None) -> dict:
    """Critérios de aceitação SEPARADOS e explícitos (auditoria do PR #23, ponto B). ``concluida`` no armazenamento só
    significa evidência algébrica completa e auditada; a coerência dinâmica e a validação física são estados próprios."""
    alg = {"estado": "aprovada", "criterio": "missão completa + auditoria integral independente (sem solver) aprovada"}
    fis = {"estado": "nao_validada", "criterio": "medições do equipamento real",
           "motivo": "Modelos estacionário e dinâmico APROXIMADOS, sem validação no equipamento; simulação offline "
                     "algébrica de ensaio."}
    if din is None:
        dyn = {"estado": "nao_aplicavel", "criterio": "sem PEMFC na missão"}
        cls = "algebrica_aprovada_sem_pemfc"
    else:
        inc = {u: v["incoerencias"] for u, v in din["unidades"].items() if not v["coerente"]}
        dyn = {"estado": "coerente" if din["coerente"] else "incoerente",
               "criterio": "por intervalo: |E_entregue − E_solicitada| ≤ máx(2 %, 0,5 kW·Δ) e |m_H₂ dinâmico − m_H₂ do "
                           "EMS| ≤ máx(2 %, 0,02 kg/h·Δ) (v2/pemfc_dinamica.json)",
               "intervalos_incoerentes": {u: len(v) for u, v in inc.items()}}
        cls = "algebrica_aprovada_dinamica_coerente" if din["coerente"] else "algebrica_aprovada_dinamica_incoerente"
    return {"algebrica": alg, "dinamica": dyn, "fisica": fis, "classificacao": cls, "rotulo": ROTULOS_ACEITACAO[cls]}


def executar_janela_a_janela(ctrl, entorno, ao_avancar=None):
    """Laço da missão com o orquestrador DO MOTOR (``executar_missao_simulada``), uma janela por chamada, para relatar
    progresso real entre janelas. Equivalente a uma única chamada (o laço do motor não guarda estado entre iterações)."""
    from ems_v2.mpc.orquestrador import executar_missao_simulada

    while ctrl.situacao == "em_andamento" and not ctrl.relogio.encerrado:
        antes = (ctrl.k, len(ctrl.registros))
        executar_missao_simulada(ctrl, entorno, max_janelas=1, finalizar=False)
        if ao_avancar is not None:
            ao_avancar()
        if (ctrl.k, len(ctrl.registros)) == antes and ctrl.situacao == "em_andamento":
            raise RuntimeError("O controlador MPC não avançou nem encerrou a missão (estado inesperado).")
    return executar_missao_simulada(ctrl, entorno, max_janelas=0, finalizar=True)


def _motivo(res) -> str:
    for r in reversed(res.registros):
        c = r.conteudo
        if c.classe_falha is not None:
            det = "; ".join(f"[{x.codigo}] {x.mensagem}" for x in c.constatacoes[:3])
            return f"janela {c.janela.indice_janela} (k = {c.janela.k}): classe '{c.classe_falha}'" + (f" — {det}" if det else "")
    return f"classe '{res.classe_falha}'"


def _executar(store, run_uid: str, pf: PF.PreflightV2) -> None:
    state = {"last": 0.0}

    def beat(progress: dict, force: bool = False) -> None:
        now = time.monotonic()
        if force or now - state["last"] >= R16.HEARTBEAT_EVERY_S:
            state["last"] = now
            if not store.heartbeat_run(run_uid, OWNER, progress):
                raise RunStateError("A rodada deixou de estar em execução por este processo.")

    outcome: dict = {"engine": {"id": E.MOTOR_V2}, "mission": None}
    try:
        beat({"phase": "fila"}, force=True)
        with R16._ENGINE_LOCK:
            t0 = time.perf_counter()
            beat({"phase": "montagem"}, force=True)
            amb = verificar_ambiente()
            outcome["solver_environment"] = amb
            if not amb.get("disponivel"):
                store.fail_run(run_uid, OWNER, {
                    "kind": "solver_indisponivel", "message": "Pyomo/HiGHS indisponíveis no momento da execução ("
                    + str(amb.get("erro")) + "): nenhuma janela foi resolvida e o motor V1.6 NÃO foi usado como substituto."},
                    outcome=R16._json_safe(outcome))
                return
            mont, stored = pf.montagem, pf.scenario
            K, fuso = mont.tempo.K, mont.tempo.fuso
            ctrl, entorno, cfg = MT.construir_missao(mont, run_uid, stored)
            beat({"phase": "missao", "k": 0, "n": K, "janelas": 0}, force=True)
            res = executar_janela_a_janela(ctrl, entorno, lambda: beat(
                {"phase": "missao", "k": int(ctrl.k), "n": K, "janelas": len(ctrl.registros)}, force=True))
            beat({"phase": "auditoria"}, force=True)
            if res.registro_missao is None:
                raise RuntimeError(f"Missão em situação '{res.situacao}' sem registro de missão selado.")
            ev = RG.evidencia_do_resultado(res, mont)
            rel = RG.auditar(ev, verdade=mont.verdade)
            rm = res.registro_missao.conteudo
            completa = res.situacao == "encerrada" and rm.desfecho == "concluida" and rm.intervalos_aplicados == rm.K_M
            outcome["mission"] = {"situacao": res.situacao, "desfecho": rm.desfecho, "classe_falha": rm.classe_falha,
                                  "intervalos_aplicados": rm.intervalos_aplicados, "intervalos_missao": rm.K_M,
                                  "janelas": len(res.registros)}
            outcome["audit"] = {"aceito": bool(rel.aceito), "verificacoes": dict(rel.verificacoes),
                                "codigos": sorted(rel.codigos())}
            outcome["elapsed_s"] = time.perf_counter() - t0
            if completa and rel.aceito:
                beat({"phase": "gravando"}, force=True)
                origem = {"microgrid_uid": stored.microgrid_uid, "scenario_uid": stored.scenario_uid,
                          "scenario_version": stored.version, "scenario_fingerprint": stored.fingerprint,
                          "config_revision": stored.base_revision, "config_fingerprint": stored.base_fingerprint}
                pdoc = {**pf.report(), "engine_inputs": pf.engine_inputs()}
                din = verificacao_dinamica(ev, mont) if mont.pemfc else None
                data = RG.dados_da_rodada(ev, cfg, rel, R16._json_safe(pdoc), run_uid, fuso, origem, mont.doc_renovaveis,
                                          mont.doc_pemfc, din)
                summary = {"engine": E.MOTOR_V2, "mission": RG.resumo(ev, fuso),
                           "execution": {"elapsed_s": outcome["elapsed_s"], "auditoria_integral_aprovada": True,
                                         "avisos": [i.message for i in pf.items if i.level == PF.WARNING],
                                         "aceitacao": aceitacao(din)}}
                if din is not None:
                    summary["execution"]["pemfc_dinamica"] = {u: {"coerente": x["coerente"],
                                                                  "intervalos_incoerentes": len(x["incoerencias"]),
                                                                  "energia_solicitada_kWh": x["energia_solicitada_kWh"],
                                                                  "energia_entregue_kWh": x["energia_entregue_kWh"],
                                                                  "h2_modelo_dinamico_kg": x["h2_modelo_dinamico_kg"],
                                                                  "h2_ems_kg": x["h2_ems_kg"],
                                                                  "h2_subestimacao_max_kg": x["h2_subestimacao_max_kg"],
                                                                  "h2_subestimacao_total_kg":
                                                                      x["h2_subestimacao_total_kg"]}
                                                              for u, x in din["unidades"].items()}
                outcome["warnings"] = summary["execution"]["avisos"]
                store.finish_run(run_uid, OWNER, outcome=R16._json_safe(outcome), summary=R16._json_safe(summary),
                                 data=data)
                return
            outcome["evidence"] = RG.evidencia_parcial_doc(ev, cfg, rel, fuso, mont.doc_renovaveis, mont.doc_pemfc)
            if completa:                              # missão completa, mas a auditoria independente NÃO aprovou
                store.fail_run(run_uid, OWNER, {
                    "kind": "auditoria_reprovada", "message": "A missão terminou, mas a auditoria integral independente "
                    f"reprovou a evidência ({sorted(rel.codigos())[:5]}): nenhum resultado foi gravado como concluído."},
                    outcome=R16._json_safe(outcome))
                return
            store.fail_run(run_uid, OWNER, {
                "kind": "missao_interrompida", "classe_falha": rm.classe_falha or res.classe_falha,
                "intervalos_aplicados": rm.intervalos_aplicados, "intervalos_missao": rm.K_M,
                "message": f"Missão INTERROMPIDA pelo controlador após {rm.intervalos_aplicados} de {rm.K_M} intervalo(s) — "
                           f"{_motivo(res)}. A evidência parcial fica no diagnóstico da rodada; o custo parcial não é o "
                           "custo da missão."}, state="interrompida", outcome=R16._json_safe(outcome))
    except (MicrogridDeletedError, MissingStoreError):
        return                                        # microrrede excluída durante a execução: nada a registrar
    except RunStateError:
        return
    except BaseException as exc:                      # noqa: BLE001 — registrar a falha sem resultados parciais
        try:
            store.fail_run(run_uid, OWNER, {"kind": "falha", "type": type(exc).__name__, "message": str(exc)[:2000],
                                            "traceback": traceback.format_exc()[-4000:]},
                           outcome=R16._json_safe({k: v for k, v in outcome.items() if k != "evidence"}))
        except Exception:                             # noqa: BLE001 — a recuperação marcará 'interrompida'
            pass
        if not isinstance(exc, Exception):
            raise


def new_request_id() -> str:
    return uuid.uuid4().hex


recover = R16.recover
is_running_here = R16.is_running_here
wait = R16.wait

__all__ = ["OBJETIVO", "OWNER", "PreflightV2Error", "SCIENCE_PATHS_V2", "build_manifest", "executar_janela_a_janela",
           "is_running_here", "new_request_id", "prepare", "recover", "science_fingerprint", "software_versions", "submit",
           "wait"]
