"""Caderno de Ensaios (Piso 3D-B2-C) — ``tab = caderno`` do Centro de Operação.

Todos os cenários e TODAS as rodadas desta microrrede (qualquer cenário, versão e motor — V1.6 e V2), com versão, motor,
estado, datas, revisão do inventário, resultado rotulado pelo motor e dados gravados; e os estudos do Arquivo Científico.
Somente leitura: lista o que está persistido, não altera cenários, rodadas nem estudos, e nunca chama o otimizador. Abrir
uma rodada, um cenário (Folha de Ensaio) ou um estudo usa os fluxos existentes. Nada de outra microrrede é listado.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

from seeds2.microgrid.store import StoreError
from seeds2.operation import contracts

from . import session, shell

TAB = "caderno"
TOM = {"concluida": "ok", "falhou": "b", "interrompida": "w", "em_execucao": "i", "preparada": "i"}
CMP_KEY = "cd_cmp"                      # rodadas A e B escolhidas no comparador (estado de navegação da sessão)
NA = "na"                               # «não aplicável» com evidência (distinto de None = N/D)


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _duracao_s(r) -> float | None:
    import pandas as pd

    try:
        if not r.created_at or not r.finished_at:
            return None
        d = (pd.Timestamp(r.finished_at) - pd.Timestamp(r.created_at)).total_seconds()
        return d if d >= 0 else None
    except (TypeError, ValueError):
        return None


def _utc(v) -> str | None:
    """Instante para COMPARAÇÃO (o mesmo instante escrito de formas diferentes pelos manifestos V1.6 e V2)."""
    import pandas as pd

    if not v:
        return None
    try:
        t = pd.Timestamp(str(v))
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


def indicadores(r) -> dict:
    """Indicadores PERSISTIDOS de uma rodada (V2: ``integracao_v2.ui.indicadores_rodada``; V1.6: o resumo do runner).
    Métricas próprias do EMS V2 (m, H_L, PCC, sinal de valor futuro) são «não aplicáveis» ao motor V1.6 — nunca zero;
    o custo é rotulado pela NATUREZA (V1.6: função objetivo do otimizador; V2: custo realizado da missão)."""
    from . import execution_ui

    if execution_ui._is_v2_run(r):
        x = dict(execution_ui._v2().indicadores_rodada(r))
    else:
        sm = r.summary if isinstance(r.summary, dict) else {}
        mis = (r.manifest or {}).get("mission") if isinstance((r.manifest or {}).get("mission"), dict) else {}
        conc = r.state == "concluida"
        x = {"motor": "V1.6", "delta_min": None, "N": sm.get("N") if conc else None, "m": NA, "H_L": NA,
             "intervalos": mis.get("n_steps"), "passo_s": _num(mis.get("step_s", sm.get("Ts_s"))),
             "inicio_utc": mis.get("start_utc"), "duracao_min": _num(mis.get("duration_min")), "pcc": NA,
             "custo": _num(sm.get("custo_total_rs")) if conc else None, "custo_natureza": "funcao_objetivo_v16",
             "energia_importada_kWh": None, "energia_exportada_kWh": None,
             "energia_demanda_kWh": _num(sm.get("energia_demanda_kWh")) if conc else None,
             "energia_nao_atendida_kWh": _num(sm.get("energia_nao_atendida_kWh")) if conc else None,
             "h2_kg": _num(sm.get("h2_kg")) if conc else None, "sinal": NA, "auditoria": NA, "aceitacao": None,
             "formulacao": None, "contrato_dados": None}
    x["inicio_utc"] = _utc(x.get("inicio_utc"))
    x["duracao_exec_s"] = _duracao_s(r)
    x["dados"] = len(r.data or {})
    return x


def dados(store, *, ativo: str | None = None) -> dict:
    """Linhas do Caderno a partir do armazenamento da microrrede (e do Arquivo Científico, se existir)."""
    from . import execution_ui

    cenarios = store.list_scenarios()
    nomes = {s.scenario_uid: s.name for s in cenarios}
    rodadas = store.list_runs(limit=2000)
    por_cenario: dict[str, dict[str, int]] = {}
    linhas = []
    for r in rodadas:
        c = por_cenario.setdefault(r.scenario_uid, {})
        c[r.state] = c.get(r.state, 0) + 1
        linhas.append({"uid": r.run_uid, "cenario_uid": r.scenario_uid,
                       "cenario": ((r.manifest or {}).get("scenario") or {}).get("name") or nomes.get(r.scenario_uid) or "—",
                       "versao": r.scenario_version, "motor": "V2" if execution_ui._is_v2_run(r) else "V1.6",
                       "estado": r.state, "estado_rotulo": contracts.RUN_STATE_LABELS.get(r.state, r.state),
                       "tom": TOM.get(r.state, ""), "criada": shell.fmt_time(r.created_at),
                       "finalizada": shell.fmt_time(r.finished_at) or "—", "revisao": r.config_revision,
                       "resultado": execution_ui.run_cost_text(r), "dados": len(r.data or {}),
                       "cenario_existe": r.scenario_uid in nomes, "ind": _ind_seguro(r)})
    cen = [{"uid": s.scenario_uid, "nome": s.name, "versao": s.version, "motor": "V2" if execution_ui._is_v2_doc(s.document) else "V1.6",
            "atualizado": shell.fmt_time(s.updated_at), "revisao": s.base_revision, "rodadas": por_cenario.get(s.scenario_uid, {}),
            "atual": s.scenario_uid == ativo} for s in reversed(cenarios)]
    return {"cenarios": cen, "rodadas": linhas, "estudos": _estudos(store), "rotulos": dict(contracts.RUN_STATE_LABELS)}


def _ind_seguro(r) -> dict:
    try:
        return indicadores(r)
    except Exception as exc:  # noqa: BLE001 — um resumo ilegível nunca impede a listagem (fica N/D, com o motivo)
        return {"erro": str(exc)[:160]}


# ----------------------------------------------------------------------------------------------- comparação A × B
LINHAS_CMP = (("custo", "Custo da missão", "R$"), ("energia_demanda_kWh", "Energia demandada", "kWh"),
              ("energia_nao_atendida_kWh", "Energia não atendida", "kWh"), ("energia_importada_kWh", "Energia importada (PCC)", "kWh"),
              ("energia_exportada_kWh", "Energia exportada (PCC)", "kWh"), ("h2_kg", "Consumo de H₂", "kg"),
              ("duracao_exec_s", "Duração da execução (relógio de parede)", "s"))
NATUREZA_CUSTO = {"custo_realizado_v2": "custo realizado (V2)", "funcao_objetivo_v16": "função objetivo (V1.6)"}


def _celula(v):
    return "na" if v == NA else (_num(v) if v is not None else None)


def _condicoes(ra, ia, rb, ib) -> list[dict]:
    def it(item, a, b):
        return {"item": item, "a": a, "b": b, "igual": a == b}
    def cen(r):
        return f"{((r.manifest or {}).get('scenario') or {}).get('name') or '—'} ({r.scenario_uid[:8]})"
    out = [it("Motor", ia["motor"], ib["motor"]), {"item": "Cenário", "a": cen(ra), "b": cen(rb), "igual": ra.scenario_uid == rb.scenario_uid},
           it("Versão do cenário", ra.scenario_version, rb.scenario_version), it("Revisão do inventário", ra.config_revision, rb.config_revision),
           it("Início da missão (UTC)", ia.get("inicio_utc"), ib.get("inicio_utc")),
           it("Duração da missão [min]", ia.get("duracao_min"), ib.get("duracao_min"))]
    if ia["motor"] == ib["motor"] == "V2":
        out += [it("Passo Δ [min]", ia.get("delta_min"), ib.get("delta_min")), it("Horizonte curto N", ia.get("N"), ib.get("N")),
                it("Bloco aplicado m", ia.get("m"), ib.get("m")), it("Horizonte longo H_L", ia.get("H_L"), ib.get("H_L")),
                it("Modo do PCC", ia.get("pcc"), ib.get("pcc")), it("Contrato de dados", ia.get("contrato_dados"), ib.get("contrato_dados"))]
    elif ia["motor"] == ib["motor"] == "V1.6":
        out += [it("Passo [s]", ia.get("passo_s"), ib.get("passo_s")), it("Horizonte N [passos]", ia.get("N"), ib.get("N"))]
    return out


def comparar(store, a_uid: str, b_uid: str) -> dict:
    """Comparação científica de DUAS rodadas desta microrrede a partir dos registros PERSISTIDOS (sem solver nem modelos).

    * diferença absoluta (B − A) só entre números do MESMO motor e da MESMA natureza; relativa só com |A| > 0;
    * motores diferentes ⇒ valores lado a lado, sem diferença (custo V1.6 = função objetivo × V2 = custo realizado; as
      convenções de integração da energia também diferem — PARAMIJEFE Entrega 5 §16);
    * condições experimentais (cenário, versão, inventário, janela, malha, PCC) conferidas e as distintas ADVERTIDAS;
    * comparação TEMPORAL só entre rodadas V2 concluídas com a MESMA malha (mesmos instantes de início de intervalo):
      nada é alinhado, reamostrado nem interpolado."""
    ra, rb = store.get_run(a_uid), store.get_run(b_uid)
    ia, ib = indicadores(ra), indicadores(rb)
    mesmo_motor = ia["motor"] == ib["motor"]
    cond = _condicoes(ra, ia, rb, ib)
    linhas = []
    for k, rot, un in LINHAS_CMP:
        va, vb = _celula(ia.get(k)), _celula(ib.get(k))
        nota, dabs, drel = "", None, None
        if k == "custo":
            na_, nb_ = NATUREZA_CUSTO.get(ia["custo_natureza"], "—"), NATUREZA_CUSTO.get(ib["custo_natureza"], "—")
            rot = f"{rot} · {na_}" if na_ == nb_ else f"{rot} · A: {na_} · B: {nb_}"
        if isinstance(va, float) and isinstance(vb, float):
            if not mesmo_motor and k != "duracao_exec_s":
                nota = "motores diferentes: grandezas não equivalentes — diferença não calculada"
            else:
                dabs = vb - va
                if abs(va) > 0:
                    drel = dabs / abs(va)
                else:
                    nota = "diferença relativa indefinida (A = 0)"
        linhas.append({"chave": k, "rotulo": rot, "unidade": un, "a": va, "b": vb, "dif_abs": dabs, "dif_rel": drel, "nota": nota})
    if ia["motor"] == ib["motor"] == "V2":
        for k, rot in (("sinal", "Sinal de valor futuro"), ("auditoria", "Auditoria integral")):
            linhas.append({"chave": k, "rotulo": rot, "unidade": "", "a": _txt_ind(k, ia.get(k)), "b": _txt_ind(k, ib.get(k)),
                           "dif_abs": None, "dif_rel": None, "nota": ""})
    adv = []
    if not mesmo_motor:
        adv.append("Motores diferentes (V1.6 × V2): os indicadores são mostrados lado a lado, sem diferenças calculadas.")
    distintas = [c["item"] for c in cond if not c["igual"] and c["item"] != "Motor"]
    if distintas:
        adv.append("Condições experimentais NÃO equivalentes (" + ", ".join(distintas) + "): as diferenças não isolam o "
                   "efeito de um único fator.")
    if ra.state != "concluida" or rb.state != "concluida":
        adv.append("Só rodadas CONCLUÍDAS têm indicadores de missão; as demais aparecem como N/D.")
    temporal = _temporal(store, ra, ia, rb, ib)
    return {"a": _meta(ra, ia), "b": _meta(rb, ib), "condicoes": cond, "linhas": linhas, "advertencias": adv,
            "temporal": temporal, "mesmo_motor": mesmo_motor}


def _txt_ind(k, v) -> str | None:
    if v is None:
        return None
    if k == "sinal" and isinstance(v, dict):
        return f"{v.get('valido')} válido(s) · {v.get('degradado')} degradado(s) em {v.get('janelas')} janela(s)"
    if k == "auditoria":
        return "aprovada (registrada)" if v is True else "não aprovada" if v is False else str(v)
    return str(v)


def _meta(r, i) -> dict:
    return {"uid": r.run_uid, "cenario": ((r.manifest or {}).get("scenario") or {}).get("name") or "—", "cenario_uid": r.scenario_uid,
            "versao": r.scenario_version, "motor": i["motor"], "estado": r.state,
            "estado_rotulo": contracts.RUN_STATE_LABELS.get(r.state, r.state), "criada": shell.fmt_time(r.created_at),
            "revisao": r.config_revision}


def _temporal(store, ra, ia, rb, ib) -> dict:
    if not (ia["motor"] == ib["motor"] == "V2"):
        return {"ok": False, "motivo": "comparação temporal disponível só entre duas rodadas V2 concluídas com a mesma malha"}
    if ra.state != "concluida" or rb.state != "concluida":
        return {"ok": False, "motivo": "as duas rodadas precisam estar concluídas (séries completas gravadas)"}
    from . import execution_ui

    V2 = execution_ui._v2()
    sa, sb = V2.series_rodada(store, ra), V2.series_rodada(store, rb)
    if sa is None or sb is None:
        return {"ok": False, "motivo": "séries de intervalos não gravadas em uma das rodadas"}
    if sa["inicio_utc"] != sb["inicio_utc"]:
        return {"ok": False, "motivo": f"malhas temporais diferentes ({len(sa['inicio_utc'])} × {len(sb['inicio_utc'])} intervalos, "
                                       f"início {ia.get('inicio_utc')} × {ib.get('inicio_utc')}, Δ {ia.get('delta_min')} × "
                                       f"{ib.get('delta_min')} min): nenhuma série é alinhada nem interpolada"}
    series = [{"chave": c, "rotulo": rot, "unidade": un, "a": sa["series"][c], "b": sb["series"][c]}
              for c, rot, un in V2.SERIES_COMPARAVEIS if c in sa["series"] and c in sb["series"]]
    return {"ok": True, "instantes": sa["inicio_utc"], "series": series}


def _estudos(store) -> list[dict]:
    """Estudos do Arquivo Científico da instalação (somente leitura). O banco do Arquivo NÃO é criado por esta consulta."""
    from seeds2.microgrid.store import resolve_data_dir

    if not (Path(str(resolve_data_dir())) / "scientific_archive" / "archive.db").is_file():
        return []
    try:
        estudos = list(reversed(session.archive().list_studies()))
    except StoreError:
        return []
    mg = session.active_uid()
    return [{"uid": e.archive_uid, "nome": e.scenario_name, "origem": e.origin_microgrid_name or "—", "versoes": e.n_versions,
             "rodadas": e.n_runs, "verificado": bool((e.verification or {}).get("ok")), "content_id": e.content_id[:16],
             "desta": bool(mg and e.origin_microgrid_uid == mg), "importado": shell.fmt_time(e.imported_at)} for e in estudos]


def _on_action() -> None:
    a = shell.payload("seeds_caderno")
    if not a:
        return
    ss = st.session_state
    if a.get("type") == "abrir_rodada" and a.get("run"):
        from . import execution_ui

        execution_ui.open_run(str(a["run"]))
    elif a.get("type") == "abrir_cenario" and a.get("sc"):
        from . import operation_center as OC

        if ss.get(shell.SCENARIO_KEY) != a["sc"]:
            if OC.is_dirty():                               # uma edição pendente nunca é descartada em silêncio
                ss["op_flash"] = ("warn", "Há alterações não salvas no cenário aberto: salve-as ou descarte-as antes de "
                                          "abrir outro cenário.")
                return
            OC._clear_selection()
            ss[shell.SCENARIO_KEY] = str(a["sc"])
        shell.go("operacao", a.get("tab") or "inicializacao")
    elif a.get("type") == "abrir_estudo" and a.get("study"):
        from . import archive_ui

        archive_ui.open_study(str(a["study"]), "operacao")
    elif a.get("type") == "comparar":
        ss[CMP_KEY] = (str(a.get("a") or ""), str(a.get("b") or ""))
    elif a.get("type") == "nav":
        shell.go(a.get("view") or "operacao", a.get("tab"))


def render(store, cur) -> None:
    from . import trama

    saved = session.saved()
    d = dados(store, ativo=cur.scenario_uid if cur is not None else None)
    d["microrrede"] = {"nome": (saved.config.get("installation") or {}).get("name") or "", "revisao": saved.revision}
    sel = st.session_state.get(CMP_KEY)
    uids = {r["uid"] for r in d["rodadas"]}
    if sel and sel[0] in uids and sel[1] in uids and sel[0] != sel[1]:   # só rodadas DESTA microrrede
        try:
            d["comparacao"] = comparar(store, sel[0], sel[1])
        except Exception as exc:  # noqa: BLE001 — falha de leitura vira mensagem, nunca resultado
            d["comparacao"] = {"erro": f"Não foi possível comparar: {exc}"[:300]}
        d["comparacao"]["sel"] = list(sel)
    c1, _ = st.columns([1, 3])
    with c1:
        if st.button("← Centro de Operação", key="cd_back"):
            shell.go("operacao")
            st.rerun()
    st.html(f'<h1 class="sd-section" style="font-size:1.5rem;margin:.2rem 0 .1rem">Caderno de ensaios · {escape(d["microrrede"]["nome"])}</h1>'
            '<div class="sd-muted" style="margin-bottom:.5rem">Cenários, versões e rodadas desta microrrede (motores V1.6 e V2) e os '
            'estudos do Arquivo Científico. Somente leitura: abrir uma rodada não executa modelos nem o otimizador.</div>')
    trama.pagina("caderno", d, key="seeds_caderno", on_action=_on_action)


__all__ = ["TAB", "dados", "render"]
