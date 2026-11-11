"""Piso 3D-B0 — marco de dados TRAMA de uma rodada V2 (somente leitura).

Converte a evidência PERSISTIDA de uma rodada concluída do motor V2 (``v2/intervalos.csv``, ``v2/fronteiras.csv``,
``v2/janelas.csv``, ``v2/renovaveis.json``, ``v2/pemfc.json``, ``v2/pemfc_dinamica.json``, resumo e manifesto) no documento
``seeds2-trama-frame`` consumido pelo motor gráfico Trama (``seeds2/ui/trama.py``).

Regras:

* só LÊ (``source.run_data``): nunca grava, nunca importa Pyomo/HiGHS nem modelos físicos, nunca recalcula despacho;
* os valores são os gravados, sem arredondamento; célula vazia/ausente vira ``None`` (a interface mostra N/D) — nenhuma
  série é sintetizada para preencher um gráfico;
* identidade por UID; valores de INTERVALO (médias de [τ_g, τ_g+1)) e estados de FRONTEIRA (N + 1 pontos) ficam em
  campos separados e nunca são misturados;
* agregações por tecnologia e somas acumuladas NÃO são feitas aqui: são derivadas no navegador e rotuladas como tais.

``source`` é um ``MicrogridStore`` ou um estudo arquivado (mesmo contrato ``run_data``).
"""
from __future__ import annotations

import hashlib
import json
import math

from . import registro as RG

FORMATO, VERSAO = "seeds2-trama-frame", 1
ROTULOS_TECNOLOGIA = {"fv": "Solar fotovoltaica", "eolica": "Eólica"}


def _v(x):
    """Valor JSON de uma célula: ``None`` para ausente/NaN; bool/int/float/str preservados."""
    if x is None:
        return None
    if isinstance(x, str):
        return x
    try:
        if isinstance(x, bool):
            return x
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _col(df, nome: str):
    """Coluna gravada como lista, ou ``None`` quando a coluna NÃO existe no arquivo (dado não persistido)."""
    if nome not in df.columns:
        return None
    return [_v(x) for x in df[nome].tolist()]


def _opcional(source, run, nome: str):
    if not isinstance(run.data, dict) or nome not in run.data:
        return None
    return RG.ler_json(source, run, nome)


def _janelas(ja) -> list[dict]:
    campos = {"j": "janela", "k": "k", "Nk": "N_k", "mk": "m_k", "ap": "intervalos_aplicados",
              "classe": "solver_classificacao", "terminacao": "solver_terminacao", "objetivo": "objetivo_R",
              "limite_dual": "limite_dual_R", "gap_rel": "gap_rel", "variaveis": "variaveis",
              "binarias": "binarias_livres", "restricoes": "restricoes",
              "custo_operativo_previsto": "custo_operativo_previsto_janela_R",
              "custo_futuro_estimado": "custo_futuro_estimado_R", "planejado_prefixo": "planejado_prefixo_R",
              "realizado": "realizado_R", "sinal_situacao": "sinal_situacao", "sinal_qualidade": "sinal_qualidade",
              "sinal_motivo": "sinal_motivo", "sinal_fronteira": "sinal_fronteira",
              "sinal_erro_interpolacao_max": "sinal_erro_interpolacao_max_R", "avaliacoes_planejador": "avaliacoes_planejador",
              "termo_terminal": "termo_terminal_aplicado"}
    cols = {k: _col(ja, c) for k, c in campos.items()}
    return [{k: (None if v is None else v[i]) for k, v in cols.items()} for i in range(len(ja))]


def _pemfc(source, run, unidades: list[str], it) -> dict:
    """Por unidade PEMFC: séries gravadas + curva/certificado do REGISTRO + verificação dinâmica por intervalo."""
    if not unidades:
        return {}
    doc = _opcional(source, run, RG.N_PEMFC) or {}
    din = _opcional(source, run, RG.N_PEMFC_DIN) or {}
    regs, uni_din = doc.get("registros") or {}, din.get("unidades") or {}
    decl = ((run.manifest.get("strategy") or {}).get("pemfc") or {}) if isinstance(run.manifest, dict) else {}
    resumo = (((run.summary or {}).get("mission") or {}).get("pemfc")) or {}
    resumo_din = (((run.summary or {}).get("execution") or {}).get("pemfc_dinamica")) or {}
    out = {}
    for u in unidades:
        reg = u.split("#")[0]
        r = regs.get(reg) or {}
        c, cert, d = r.get("curva") or {}, r.get("certificado_b04") or {}, uni_din.get(u) or {}
        aj = c.get("ajuste") or {}
        b04 = c.get("b04") or {}
        dcl = {k: v for k, v in (decl.get(reg) or {}).items() if not isinstance(v, (dict, list))}
        curva = None
        if aj.get("P_kW"):
            curva = {"P_kW": aj.get("P_kW"), "q_suprido_kg_h": aj.get("q_suprido_kg_h"),
                     "q_consumido_kg_h": aj.get("q_consumido_kg_h"), "corrente_A": aj.get("corrente_A"),
                     "vertices": cert.get("vertices") or c.get("vertices_kW_kg_h"), "validacao": cert.get("validacao"),
                     "dominio_kW": c.get("dominio_kW"), "condicoes": (c.get("identidade") or {}).get("condicoes"),
                     "metricas": c.get("metricas"), "hipoteses": c.get("hipoteses"), "sha_curva": c.get("sha_curva"),
                     "sha_certificado": r.get("hash_certificado_b04"),
                     "b04": {"estado": b04.get("estado"), "politica": b04.get("politica"),
                             "situacao_politica": b04.get("situacao_politica"), "criterios": b04.get("criterios"),
                             "nota": b04.get("nota")},
                     "fonte": (cert.get("procedencia") or {}).get("fonte")}
        mev = r.get("massas_eventos") or {}
        out[u] = {
            "registro": reg, "u": _col(it, f"{u}|u"), "p_kW": _col(it, f"{u}|p_kW"), "partida": _col(it, f"{u}|partida"),
            "parada": _col(it, f"{u}|parada"), "q_h2_kg_h": _col(it, f"{u}|q_h2_kg_h"), "m_h2_kg": _col(it, f"{u}|m_h2_kg"),
            "m_h2_acum_kg": _col(it, f"{u}|m_h2_acum_kg"), "custo_h2_R": _col(it, f"{u}|custo_h2_R"),
            "custo_eventos_R": _col(it, f"{u}|custo_eventos_R"),
            "dinamica": None if not d else {
                "coerente": d.get("coerente"), "tolerancias": din.get("tolerancias"), "modelo": din.get("modelo"),
                "intervalos": [{"p_entregue_media_kW": x.get("p_entregue_media_kW"),
                                "energia_solicitada_kWh": x.get("energia_solicitada_kWh"),
                                "energia_entregue_kWh": x.get("energia_entregue_kWh"),
                                "h2_modelo_dinamico_kg": x.get("h2_modelo_dinamico_kg"), "h2_ems_kg": x.get("h2_ems_kg"),
                                "estados": x.get("estados"), "evento": x.get("evento"),
                                "coerente_energia": x.get("coerente_energia"), "coerente_h2": x.get("coerente_h2"),
                                "tolerancia_energia_kWh": x.get("tolerancia_energia_kWh"),
                                "tolerancia_h2_kg": x.get("tolerancia_h2_kg"), "limitacoes": x.get("limitacoes")}
                               for x in (d.get("intervalos") or [])]},
            "curva": curva, "declaracao": dcl, "temperatura_ambiente_C": r.get("temperatura_ambiente_C"),
            "massas_eventos": {"m_partida_kg": mev.get("m_partida_kg"), "m_parada_kg": mev.get("m_parada_kg"),
                               "modelo_dinamico": (mev.get("analise") or {}).get("parametros_modelo_dinamico")},
            "resumo": resumo.get(u), "resumo_dinamica": resumo_din.get(u)}
    return out


def montar(source, run, *, verificacao=None, nomes: dict | None = None) -> dict:
    """Marco Trama de uma rodada V2 CONCLUÍDA. ``verificacao`` = resultado de ``registro.verificar`` (opcional);
    ``nomes`` = {uid: (nome, tag)} do inventário de referência, quando o chamador os conhece."""
    if not RG.e_v2(run) or run.state != "concluida":
        raise RG.IntegridadeV2Error("O marco Trama só é montado para rodadas V2 concluídas.")
    m = run.manifest
    s = (run.summary or {}).get("mission") or {}
    ex = (run.summary or {}).get("execution") or {}
    it, fr, ja = (RG.ler_csv(source, run, n) for n in (RG.N_INTERVALOS, RG.N_FRONTEIRAS, RG.N_JANELAS))
    mis, est = m.get("mission") or {}, m.get("strategy") or {}
    nomes = nomes or {}
    ren_doc = _opcional(source, run, RG.N_RENOV) or {}
    ren_rec = {r.get("uid"): r for r in (ren_doc.get("recursos") or [])}
    bats, rens, gers = list(s.get("baterias") or {}), list(s.get("renovaveis") or {}), list(s.get("pemfc") or {})

    def rotulo(uid: str, padrao: str) -> dict:
        nome, tag = nomes.get(uid.split("#")[0]) or (None, None)
        return {"uid": uid, "nome": nome or padrao, "tag": tag}

    recursos = {"fv": [], "wt": [], "bat": [], "fc": []}
    renov = {}
    for u in rens:
        info, rr = s["renovaveis"][u], ren_rec.get(u) or {}
        tipo = "fv" if info.get("tecnologia") == "fv" else "wt"
        recursos[tipo].append(rotulo(u, rr.get("nome") or ROTULOS_TECNOLOGIA.get(info.get("tecnologia"), "Renovável")))
        renov[u] = {"tecnologia": info.get("tecnologia"), "A_prevista_kW": _col(it, f"{u}|A_prevista_kW"),
                    "A_observada_kW": _col(it, f"{u}|A_observada_kW"), "A_utilizavel_kW": _col(it, f"{u}|A_utilizavel_kW"),
                    "P_R_kW": _col(it, f"{u}|P_R_kW"), "vertimento_kW": _col(it, f"{u}|vertimento_kW"),
                    "E_aproveitada_acum_kWh": _col(it, f"{u}|E_aproveitada_acum_kWh"), "resumo": info,
                    "modelo": rr.get("rotulo_modelo"), "parametros": rr.get("parametros"),
                    "diagnostico": rr.get("diagnostico"), "hipoteses": rr.get("hipoteses"),
                    "energia_potencial_kWh": rr.get("energia_potencial_kWh")}
    bat_decl = est.get("baterias") or {}
    baterias = {}
    for u in bats:
        recursos["bat"].append(rotulo(u, "Banco de baterias"))
        d = bat_decl.get(u) or {}
        baterias[u] = {"P_c_kW": _col(it, f"{u}|P_c_kW"), "P_d_kW": _col(it, f"{u}|P_d_kW"),
                       "energia_kWh": _col(fr, f"{u}|energia_kWh"), "soc": _col(fr, f"{u}|soc"), "resumo": s["baterias"][u],
                       "declaracao": {k: v for k, v in d.items() if not isinstance(v, (dict, list))}}
    for u in gers:
        recursos["fc"].append(rotulo(u, "PEMFC"))
    pcc = est.get("pcc") or {}
    clima = ren_doc.get("clima") or {}
    frame = {
        "formato": FORMATO, "versao": VERSAO,
        "rodada": {"uid": run.run_uid, "estado": run.state, "cenario": (m.get("scenario") or {}).get("name"),
                   "versao_cenario": run.scenario_version, "microrrede_uid": (m.get("reference") or {}).get("microgrid_uid"),
                   "revisao_inventario": run.config_revision, "criada": run.created_at, "finalizada": run.finished_at,
                   "motor": (m.get("engine") or {}).get("id"), "versao_dados": (m.get("engine") or {}).get("data_version"),
                   "N": s.get("N"), "m": s.get("m"), "H_L": s.get("H_L"), "delta_min": s.get("delta_min"),
                   "K": len(it), "fuso": mis.get("timezone"), "inicio_utc": mis.get("start_utc"),
                   "sintetico": bool(s.get("dados_sinteticos")), "contexto": s.get("contexto")},
        "fronteiras": {"indice": _col(fr, "fronteira"), "utc": _col(fr, "instante_utc"), "local": _col(fr, "instante_local")},
        "intervalos": {
            "janela": _col(it, "janela"), "indice_no_plano": _col(it, "indice_no_plano"),
            "demanda_prevista_kW": _col(it, "demanda_prevista_kW"), "demanda_realizada_kW": _col(it, "demanda_realizada_kW"),
            "demanda_nao_atendida_kW": _col(it, "demanda_nao_atendida_kW"),
            "demanda_atendida_kW": _col(it, "demanda_atendida_kW"),
            "pcc_importacao_programada_kW": _col(it, "pcc_importacao_programada_kW"),
            "pcc_importacao_realizada_kW": _col(it, "pcc_importacao_realizada_kW"),
            "pcc_exportacao_programada_kW": _col(it, "pcc_exportacao_programada_kW"),
            "pcc_exportacao_realizada_kW": _col(it, "pcc_exportacao_realizada_kW"),
            "pcc_desvio_liquido_kW": _col(it, "pcc_desvio_liquido_kW"),
            "tarifa_importacao_decisao_R_kWh": _col(it, "tarifa_importacao_decisao_R_kWh"),
            "tarifa_exportacao_decisao_R_kWh": _col(it, "tarifa_exportacao_decisao_R_kWh"),
            "preco_importacao_liquidacao_R_kWh": _col(it, "preco_importacao_liquidacao_R_kWh"),
            "custo_importacao_R": _col(it, "custo_importacao_R"), "receita_exportacao_R": _col(it, "receita_exportacao_R"),
            "custo_desvio_rede_R": _col(it, "custo_desvio_rede_R"), "custo_throughput_R": _col(it, "custo_throughput_R"),
            "custo_realizado_intervalo_R": _col(it, "custo_realizado_intervalo_R"),
            "custo_realizado_acumulado_R": _col(it, "custo_realizado_acumulado_R"),
            "residuo_balanco_kW": _col(it, "residuo_balanco_kW")},
        "recursos": recursos, "renovaveis": renov, "baterias": baterias, "pemfc": _pemfc(source, run, gers, it),
        "pcc": {"modo": s.get("pcc_modo") or pcc.get("modo"), "sentidos": pcc.get("sentidos"),
                "limite_importacao_kW": pcc.get("limite_importacao_kW"), "limite_exportacao_kW": pcc.get("limite_exportacao_kW"),
                "ajuste": pcc.get("ajuste"), "liquidacao": pcc.get("tarifa_liquidacao"), "rotulo_tarifa": pcc.get("rotulo_tarifa"),
                "procedencia": (pcc.get("procedencia") or {}).get("tipo")},
        "demanda": {k: v for k, v in (est.get("demanda") or {}).items() if not isinstance(v, (dict, list))},
        "clima": {"sha256_serie": clima.get("sha256_serie_normalizada"), "rotulo": clima.get("rotulo"),
                  "procedencia": clima.get("procedencia"), "realizacao": (ren_doc.get("realizacao") or {}).get("tipo")},
        "janelas": _janelas(ja),
        "resumo": {"custo_realizado_total_R": s.get("custo_realizado_total_R"),
                   "componentes_R": s.get("custo_realizado_componentes_R") or {},
                   "energia_demanda_kWh": s.get("energia_demanda_kWh"), "energia_atendida_kWh": s.get("energia_atendida_kWh"),
                   "energia_nao_atendida_kWh": s.get("energia_nao_atendida_kWh"),
                   "energia_importada_kWh": s.get("energia_importada_kWh"), "energia_exportada_kWh": s.get("energia_exportada_kWh"),
                   "gasto_importacao_R": s.get("gasto_importacao_R"), "receita_exportacao_R": s.get("receita_exportacao_R"),
                   "indicadores_selados": s.get("indicadores_selados") or {}, "sinal_valor_futuro": s.get("sinal_valor_futuro"),
                   "solver": s.get("solver"), "missao_completa": s.get("missao_completa")},
        "aceitacao": ex.get("aceitacao"), "avisos": list(ex.get("avisos") or []),
        "verificacao": None if verificacao is None else {"ok": bool(verificacao.ok),
                                                         "itens": [[bool(ok), str(t)] for ok, t in verificacao.itens]},
        "arquivos": [[n, d.get("sha256"), d.get("size")] for n, d in (run.data or {}).items()],
        "fontes": {"intervalos": RG.N_INTERVALOS, "fronteiras": RG.N_FRONTEIRAS, "janelas": RG.N_JANELAS,
                   "renovaveis": RG.N_RENOV, "pemfc": RG.N_PEMFC, "pemfc_dinamica": RG.N_PEMFC_DIN},
    }
    frame["hash"] = hashlib.sha256(json.dumps(frame, sort_keys=True, ensure_ascii=False, allow_nan=False)
                                   .encode("utf-8")).hexdigest()
    return frame


__all__ = ["FORMATO", "VERSAO", "montar"]
