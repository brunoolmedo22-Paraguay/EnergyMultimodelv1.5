"""Potencial renovável NO BARRAMENTO por UID (Piso 3D-A2-R): modelos físicos REAIS do SEEDS2 sobre o clima previsto.

Nenhum modelo novo e nenhum perfil arbitrário: cada recurso usa o modelo que o V1.6 e o SEEDS2 já usam para o mesmo
equipamento, com os parâmetros da revisão do inventário referenciada pelo cenário.

* **FV — por ARRANJO** (``arr-…``; a usina ``eq-…`` é só o agrupador, a identidade de cada arranjo é preservada):
  ``simulation.multimodel.simulate_noct_efficiency_model`` (Modelo 2: temperatura NOCT + eficiência corrigida por
  γ_Pmax; módulo de ``config/pv_database.py``; N_s × N_p e perdas por sujeira do inventário). A saída do modelo é a
  potência CC do arranjo; a conversão para o barramento é o fator η DECLARADO na estratégia (sem padrão; o modelo não
  representa inversor/MPPT). Irradiância de entrada = GHI prevista (mesma convenção do V1.6: sem transposição ao plano).
* **Eólica — por REGISTRO** (``eq-…``; ``count`` aerogeradores idênticos): ``models.wind_model.run_wind_model`` com a
  curva do catálogo (``config/wind_turbine_database.py``), cortes cut-in/cut-out, limites e correção de densidade do
  PRÓPRIO modelo; a única perda é a opção do inventário (``apply_grid_loss``) — nenhuma perda é aplicada duas vezes.
  Curvas ``curve_analysis_only`` são recusadas pelo próprio modelo (não estão habilitadas para energia).

Semântica temporal (sem interpolação, deslocamento nem preenchimento):

* o clima é usado nos instantes EXATOS da série gravada no cenário (Piso 2B), convertidos para UTC pelo fuso declarado;
* o passo da série tem de dividir Δ: n = Δ / passo subamostras por intervalo, todas presentes e com o passo uniforme;
* o modelo é aplicado a CADA subamostra e o potencial do intervalo é a MÉDIA ARITMÉTICA das n potências
  (``REGRA_AGREGACAO``) — transformação registrada; a média de uma função não linear do clima é uma aproximação
  declarada (registrada em ``hipoteses``), nunca apresentada como medição.

O resultado (séries por UID + parâmetros + hipóteses + diagnóstico do modelo) é PERSISTIDO na rodada
(``v2/renovaveis.json``); a reabertura nunca reexecuta modelo nem otimizador.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .estrategia import HIPOTESES_DENSIDADE, SEMANTICAS_CLIMA

FV_MODELO = "simulation.multimodel.simulate_noct_efficiency_model"
FV_ROTULO = "Modelo FV 2 — temperatura NOCT + eficiência corrigida por γ_Pmax (models.pv_module · config/pv_database.py)"
EOL_MODELO = "models.wind_model.run_wind_model"
EOL_ROTULO = "Curva do catálogo (config/wind_turbine_database.py) com cortes, limites e correção de densidade do modelo"
REGRA_AGREGACAO = "media_aritmetica_das_subamostras"
VARIAVEIS_FV = ("ghi_W_m2", "temperature_C")
VARIAVEIS_EOL = ("wind_speed_m_s",)
ATMOSFERA = ("temperature_C", "pressure_hPa", "humidity_pct")
class DerivacaoInvalida(ValueError):
    """O potencial de um recurso não pode ser derivado sem relaxar o contrato (mensagem apresentável)."""


@dataclass
class Clima:
    """Clima previsto alinhado à malha da missão: K·n subamostras nos instantes EXATOS da série gravada."""
    passo_s: float
    n: int
    t_utc: np.ndarray
    valores: dict
    entrada: dict
    semantica: str
    emissao_utc: str

    def doc(self) -> dict:
        return {"slot": "climate", "sha256_serie_normalizada": self.entrada.get("data"),
                "sha256_arquivo_original": self.entrada.get("blob"), "rotulo": self.entrada.get("label"),
                "origem": self.entrada.get("source_type"), "procedencia": self.entrada.get("provenance"),
                "fuso_da_serie": self.entrada.get("timezone"), "passo_s": self.passo_s, "subamostras_por_intervalo": self.n,
                "variaveis_usadas": sorted(k for k, v in self.valores.items() if np.isfinite(v).any()),
                "semantica_declarada": self.semantica, "semantica": SEMANTICAS_CLIMA[self.semantica],
                "emissao_declarada_utc": self.emissao_utc, "regra_agregacao": REGRA_AGREGACAO,
                "primeira_subamostra_utc": _iso(float(self.t_utc[0])), "ultima_subamostra_utc": _iso(float(self.t_utc[-1]))}


@dataclass
class Derivacao:
    """Potencial derivado de UM recurso renovável (série de K médias de intervalo, kW no barramento)."""
    uid: str
    registro: str
    tecnologia: str                     # "fv" | "eolica"
    nome: str
    modelo: str
    rotulo_modelo: str
    parametros: dict
    hipoteses: list
    potencia_kW: tuple
    diagnostico: dict = field(default_factory=dict)

    def energia_kWh(self, h: float) -> float:
        return math.fsum(v * h for v in self.potencia_kW)

    def doc(self, h: float) -> dict:
        return {"uid": self.uid, "registro": self.registro, "tecnologia": self.tecnologia, "nome": self.nome,
                "modelo": self.modelo, "rotulo_modelo": self.rotulo_modelo, "parametros": self.parametros,
                "hipoteses": list(self.hipoteses), "potencial_kW": [float(v) for v in self.potencia_kW],
                "energia_potencial_kWh": self.energia_kWh(h), "pico_kW": max(self.potencia_kW) if self.potencia_kW else None,
                "diagnostico": self.diagnostico}


def _iso(seg: float) -> str:
    return pd.Timestamp(seg, unit="s", tz="UTC").isoformat()


def _media(amostras: np.ndarray, K: int, n: int) -> tuple:
    """Média aritmética EXATA por intervalo (``math.fsum``: independente da ordem/vetorização da plataforma)."""
    a = np.asarray(amostras, dtype=float).reshape(K, n)
    return tuple(math.fsum(float(x) for x in linha) / n for linha in a)


# ====================================================================== clima → malha
def alinhar_clima(serie, entrada: dict, inicio_utc_s: float, delta_s: int, K: int, obrigatorias: set,
                  opcionais: set, semantica: str, emissao_utc: str) -> Clima:
    """Subamostras do clima nos instantes EXATOS da missão. Erro ⇒ ``DerivacaoInvalida`` (nada é completado)."""
    passo = entrada.get("step_s")
    if not isinstance(passo, (int, float)) or isinstance(passo, bool) or not passo > 0 or not entrada.get("regular", True):
        raise DerivacaoInvalida(f"A série climática não tem passo regular declarado (passo {passo!r} s): sem reamostragem.")
    razao = delta_s / float(passo)
    n = int(round(razao))
    if n < 1 or abs(razao - n) > 1e-9:
        raise DerivacaoInvalida(f"O passo da série climática ({float(passo):g} s) não divide Δ = {delta_s} s: o potencial "
                                "médio do intervalo exigiria interpolação ou recorte — não é feito. Use Δ múltiplo do passo.")
    alvo = inicio_utc_s + float(passo) * np.arange(K * n)
    t = np.asarray(serie.t_utc, dtype=float)
    idx = np.searchsorted(t, alvo - 1e-6)
    ok = idx < len(t)
    ok[ok] &= np.abs(t[idx[ok]] - alvo[ok]) < 1e-6
    if not ok.all():
        falt = int((~ok).sum())
        prim = _iso(float(alvo[~ok][0]))
        raise DerivacaoInvalida(f"A série climática não cobre a missão: faltam {falt} de {K * n} subamostra(s) exigidas "
                                f"(primeira ausente em {prim}; passo {float(passo):g} s). Nenhum valor é interpolado, "
                                "deslocado ou completado.")
    if K * n > 1 and (np.diff(idx) != 1).any():
        raise DerivacaoInvalida("A série climática tem amostras intermediárias dentro da missão (passo não uniforme): "
                                "o passo registrado não descreve a série — nada é reamostrado.")
    df = serie.df
    vals: dict = {}
    for var in sorted(obrigatorias):
        if var not in df.columns:
            raise DerivacaoInvalida(f"Variável climática exigida ausente da previsão: {var}.")
        v = df[var].to_numpy(dtype=float)[idx]
        if not np.isfinite(v).all():
            raise DerivacaoInvalida(f"{var}: {int((~np.isfinite(v)).sum())} subamostra(s) ausente(s) dentro da missão — "
                                    "ausente nunca vira zero nem é interpolado.")
        vals[var] = v
    for var in sorted(opcionais - obrigatorias):
        vals[var] = df[var].to_numpy(dtype=float)[idx] if var in df.columns else np.full(K * n, np.nan)
    if "ghi_W_m2" in vals and (vals["ghi_W_m2"] < 0).any():
        raise DerivacaoInvalida("GHI negativa na previsão climática dentro da missão.")
    if "wind_speed_m_s" in vals and (vals["wind_speed_m_s"] < 0).any():
        raise DerivacaoInvalida("Velocidade do vento negativa na previsão climática dentro da missão.")
    return Clima(float(passo), n, alvo, vals, dict(entrada), semantica, emissao_utc)


def _indice(clima: Clima) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(clima.t_utc, unit="s"))


def _hipotese_semantica(clima: Clima) -> str:
    base = SEMANTICAS_CLIMA[clima.semantica]
    if clima.n == 1:
        return base + "; UMA subamostra por intervalo: P̄_k ≈ P(clima_k)"
    return base + f"; {clima.n} subamostras por intervalo: P̄_k = (1/{clima.n}) Σ_j P(clima_k,j)"


# ====================================================================== FV
def derivar_fv(eq: dict, eta: float, clima: Clima, K: int) -> list:
    """Uma ``Derivacao`` por ARRANJO da usina ``eq`` (modo 'modulo'); erro ⇒ ``DerivacaoInvalida``."""
    from config.pv_database import MODULE_DB, get_module
    from simulation.multimodel import simulate_noct_efficiency_model

    out = []
    arranjos = eq.get("arrays") or []
    if not arranjos:
        raise DerivacaoInvalida("Usina FV sem arranjos: não há potencial a derivar.")
    for a in arranjos:
        rot = f"arranjo {a.get('name') or a.get('id')}"
        if a.get("mode") != "modulo":
            raise DerivacaoInvalida(f"{rot}: cadastrado por potência declarada (sem módulo do catálogo) — o modelo físico "
                                    "não o representa (exige módulo, N_s, N_p e sujeira).")
        ref = a.get("reference")
        if ref not in MODULE_DB:
            raise DerivacaoInvalida(f"{rot}: módulo {ref!r} ausente do catálogo config/pv_database.py.")
        ns, npar, suj = a.get("n_series"), a.get("n_parallel"), a.get("soiling_pct")
        if not all(isinstance(x, int) and not isinstance(x, bool) and x >= 1 for x in (ns, npar)):
            raise DerivacaoInvalida(f"{rot}: N_s/N_p não declarados.")
        if a.get("soiling_default", False) or not isinstance(suj, (int, float)) or isinstance(suj, bool):
            raise DerivacaoInvalida(f"{rot}: perdas por sujeira NÃO declaradas (0 % aplicado só como hipótese padrão do "
                                    "Piso 1): declare o valor no inventário — nenhum valor é presumido.")
        mod = get_module(ref)
        perfil = pd.DataFrame({"G": clima.valores["ghi_W_m2"], "Tamb": clima.valores["temperature_C"]}, index=_indice(clima))
        res = simulate_noct_efficiency_model(mod, perfil, n_series=ns, n_parallel=npar, soiling_losses=float(suj) / 100.0)
        p_w = res["P_array"].to_numpy(dtype=float)
        if not np.isfinite(p_w).all() or (p_w < 0).any():
            raise DerivacaoInvalida(f"{rot}: o modelo FV produziu potência não finita ou negativa.")
        medias_cc_kW = _media(p_w / 1000.0, K, clima.n)
        pot = tuple(float(eta) * v for v in medias_cc_kW)
        st = mod.stc
        out.append(Derivacao(
            uid=a["id"], registro=eq["id"], tecnologia="fv", nome=f"{eq.get('name') or eq['id']} · {a.get('name') or a['id']}",
            modelo=FV_MODELO, rotulo_modelo=FV_ROTULO,
            parametros={"modulo": ref, "fabricante": st.manufacturer, "modelo_modulo": st.model,
                        "p_nominal_modulo_W": st.p_nom, "area_modulo_m2": st.area, "eficiencia_stc": st.efficiency_stc,
                        "noct_C": res.attrs.get("noct"), "gamma_pmax_pct_C": st.gamma_pmax_pct, "n_series": ns,
                        "n_parallel": npar, "n_modulos": ns * npar, "p_stc_arranjo_kW": st.p_nom * ns * npar / 1000.0,
                        "sujeira_pct": float(suj), "eta_conversao_barramento": float(eta),
                        "fonte_parametros": f"inventário · equipment[{eq['id']}].arrays[{a['id']}] + catálogo de módulos"},
            hipoteses=[_hipotese_semantica(clima),
                       "Irradiância de entrada = GHI prevista tratada como irradiância no plano do módulo (sem "
                       "transposição; mesma convenção do modelo V1.6)",
                       "Saída do modelo = potência CC do arranjo; inversor/MPPT NÃO representados pelo modelo: "
                       f"P_barramento = η declarado ({float(eta):g}) × P_CC",
                       "Sem degradação anual, sombreamento, mismatch ou limite de inversor (não representados)"],
            potencia_kW=pot,
            diagnostico={"subamostras": int(len(p_w)), "potencia_cc_max_subamostra_kW": float(p_w.max() / 1000.0),
                         "temperatura_celula_max_C": float(np.max(res["Tc"].to_numpy(dtype=float))),
                         "ghi_max_W_m2": float(np.max(clima.valores["ghi_W_m2"]))}))
    return out


# ====================================================================== eólica
def derivar_eolica(eq: dict, hipotese_densidade: str, clima: Clima, K: int) -> Derivacao:
    from config.wind_turbine_database import get_turbine
    from models.wind_model import GENERATOR_TO_GRID_GENERIC_LOSS, run_wind_model

    p = eq.get("params") or {}
    ref, n_t, perda = p.get("reference"), p.get("count"), p.get("apply_grid_loss")
    try:
        entrada = get_turbine(ref)
    except Exception:                                   # noqa: BLE001 — catálogo: chave desconhecida
        raise DerivacaoInvalida(f"Aerogerador {ref!r} ausente do catálogo config/wind_turbine_database.py.") from None
    if entrada.get("integration_status") == "curve_analysis_only":
        raise DerivacaoInvalida(f"A curva de {ref!r} está habilitada só para ANÁLISE de pontos (não para simulação "
                                f"energética): {entrada.get('integration_limitation') or 'ver catálogo'}.")
    if not (isinstance(n_t, int) and not isinstance(n_t, bool) and n_t >= 1):
        raise DerivacaoInvalida("Quantidade de aerogeradores não declarada no inventário.")
    if not isinstance(perda, bool):
        raise DerivacaoInvalida("Opção de perda genérica gerador→rede não declarada no inventário.")
    vento = clima.valores["wind_speed_m_s"]
    nan = np.full(len(vento), np.nan)
    if hipotese_densidade == "calculada_do_clima_previsto":
        t, pr = clima.valores.get("temperature_C", nan), clima.valores.get("pressure_hPa", nan)
        if not (np.isfinite(t).all() and np.isfinite(pr).all()):
            raise DerivacaoInvalida("Densidade declarada 'calculada do clima previsto', mas temperatura e pressão não estão "
                                    "previstas em todas as subamostras da missão (nenhum ar padrão é usado em silêncio).")
        u = clima.valores.get("humidity_pct", nan)
    elif hipotese_densidade == "referencia_do_catalogo":
        t, pr, u = nan, nan, nan
    else:
        raise DerivacaoInvalida(f"Hipótese de densidade {hipotese_densidade!r} desconhecida.")
    perfil = pd.DataFrame({"wind_speed_mps": vento, "temperature_c": t, "pressure_hpa": pr, "humidity_pct": u,
                           "wind_direction_deg": nan}, index=_indice(clima))
    perfil.attrs["timestep_hours"] = clima.passo_s / 3600.0
    perfil.attrs["timestep_minutes"] = clima.passo_s / 60.0
    try:
        res, kpis, dens = run_wind_model(perfil, ref, n_t, perda)
    except ValueError as exc:
        raise DerivacaoInvalida(f"O modelo eólico recusou o clima previsto para {ref!r}: {exc}") from None
    if hipotese_densidade == "calculada_do_clima_previsto" and dens.reference_count:
        raise DerivacaoInvalida(f"Densidade calculada inválida em {dens.reference_count} subamostra(s): o modelo recairia no "
                                "ar de referência — bloqueado (declare a hipótese de referência ou corrija o clima).")
    spec, curva = entrada["spec"], entrada["curve"]
    if entrada.get("schema_version") != 2:
        # Curva legada: np.interp mantém o último ponto além do domínio. Fora do domínio (e sem corte conhecido) seria
        # extrapolação silenciosa ⇒ bloqueio.
        vmax = max(float(x[0]) for x in curva["points"])
        parado = vento < float(spec["cut_in_mps"]) if spec.get("cut_in_mps") is not None else np.zeros(len(vento), bool)
        if spec.get("cut_out_mps") is not None:
            parado |= vento >= float(spec["cut_out_mps"])
        fora = ~parado & (res["equivalent_wind_speed_mps"].to_numpy(dtype=float) > vmax)
        if fora.any():
            raise DerivacaoInvalida(f"Vento (equivalente) acima do último ponto da curva de {ref!r} ({vmax:g} m/s) em "
                                    f"{int(fora.sum())} subamostra(s) sem corte documentado nesse ponto: extrapolação "
                                    "da curva — bloqueado.")
    p_kw = res["power_net_kw"].to_numpy(dtype=float)
    if not np.isfinite(p_kw).all() or (p_kw < 0).any():
        raise DerivacaoInvalida(f"O modelo eólico produziu potência não finita ou negativa para {ref!r}.")
    pot = _media(p_kw, K, clima.n)
    q = entrada.get("quality") or {}
    return Derivacao(
        uid=eq["id"], registro=eq["id"], tecnologia="eolica", nome=str(eq.get("name") or eq["id"]), modelo=EOL_MODELO,
        rotulo_modelo=EOL_ROTULO,
        parametros={"aerogerador": ref, "fabricante": spec.get("manufacturer"), "modelo_aerogerador": spec.get("model"),
                    "quantidade": n_t, "potencia_nominal_unidade_kW": float(spec["rated_power_kw"]),
                    "cut_in_m_s": spec.get("cut_in_mps"), "cut_out_m_s": spec.get("cut_out_mps"),
                    "limite_operacional_unidade_kW": spec.get("operating_power_limit_kw", spec["rated_power_kw"]),
                    "dominio_curva_m_s": curva.get("curve_valid_wind_range_mps"),
                    "densidade_referencia_curva_kg_m3": curva.get("reference_density_kg_m3"),
                    "situacao_integracao": entrada.get("integration_status", "legacy"),
                    "limitacao_integracao": entrada.get("integration_limitation"),
                    "qualidade_curva": q.get("power_curve"), "procedencia_curva": (entrada.get("source") or {}).get("reference"),
                    "perda_generica_aplicada": perda,
                    "fracao_perda_generica": GENERATOR_TO_GRID_GENERIC_LOSS if perda else 0.0,
                    "hipotese_densidade": hipotese_densidade, "metodo_densidade": kpis.get("density_correction_method"),
                    "fonte_parametros": f"inventário · equipment[{eq['id']}].params + catálogo de aerogeradores"},
        hipoteses=[_hipotese_semantica(clima),
                   "Velocidade prevista tratada como velocidade na altura do cubo (o modelo não aplica cisalhamento)",
                   "Curva do catálogo = potência elétrica nos terminais do gerador; a única perda adicional é a opção do "
                   "inventário (" + ("perda genérica APLICADA" if perda else "nenhuma perda genérica") + ")",
                   HIPOTESES_DENSIDADE[hipotese_densidade],
                   f"{n_t} aerogerador(es) idêntico(s) no registro: potência = {n_t} × curva (sem efeito esteira)"],
        potencia_kW=pot,
        diagnostico={"subamostras": int(len(p_kw)), "vento_max_m_s": float(np.max(vento)),
                     "vento_medio_m_s": float(np.mean(vento)),
                     "densidade": {"umido": dens.moist_count, "seco": dens.dry_count, "referencia": dens.reference_count,
                                   "media_kg_m3": dens.mean_kg_m3},
                     "horas_abaixo_cut_in": kpis.get("below_cut_in_hours"), "horas_acima_cut_out": kpis.get("above_cut_out_hours"),
                     "potencia_liquida_max_subamostra_kW": float(p_kw.max())})


# ====================================================================== persistência
def documento(derivacoes: list, clima: Clima | None, realizacao: dict, delta_s: int) -> dict:
    """Conteúdo de ``v2/renovaveis.json`` (determinístico; comprometido no manifesto ANTES da execução)."""
    h = delta_s / 3600.0
    return {"formato": "seeds2-milp-mpc-renovaveis", "versao": 1,
            "clima": None if clima is None else clima.doc(),
            "base_potencial": "antes_da_disponibilidade",
            "realizacao": dict(realizacao),
            "recursos": [d.doc(h) for d in sorted(derivacoes, key=lambda x: x.uid)],
            "nota": "Séries DERIVADAS pelos modelos físicos do SEEDS2 no preflight da rodada (ensaio offline). A reabertura "
                    "lê estas séries e as confere contra a previsão e a realização seladas; nenhum modelo é reexecutado."}


def bytes_documento(doc: dict) -> bytes:
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False).encode("utf-8")


def sha_documento(doc: dict) -> str:
    return hashlib.sha256(bytes_documento(doc)).hexdigest()


__all__ = ["ATMOSFERA", "Clima", "Derivacao", "DerivacaoInvalida", "EOL_MODELO", "FV_MODELO", "HIPOTESES_DENSIDADE",
           "REGRA_AGREGACAO", "SEMANTICAS_CLIMA", "VARIAVEIS_EOL", "VARIAVEIS_FV", "alinhar_clima", "bytes_documento",
           "derivar_eolica", "derivar_fv", "documento", "sha_documento"]
