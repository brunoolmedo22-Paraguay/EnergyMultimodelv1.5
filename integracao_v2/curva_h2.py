"""Curva estacionária q_H₂(P_net) da PEMFC derivada do MODELO FÍSICO existente — Piso 3D-A2-H.

Decisão do responsável (fechada): a curva de consumo de hidrogênio em função da potência elétrica líquida é obtida
DIRETAMENTE do modelo PEMFC do SEEDS2, com os parâmetros físicos de inicialização declarados; gerada UMA vez por
configuração física, validada, armazenada e reutilizada em toda a missão (planejador longo e todas as janelas do MPC).

Nada aqui reescreve equações: a curva vem de ``h2_pemfc``:

* ``Equivalent65kWHorizonPowerRequestModel.analyze_operational_branch`` → rama operacional estritamente crescente e o
  domínio de potência líquida;
* ``Equivalent65kWHorizonPowerRequestModel.solve_requested_power`` → para cada P_net, a corrente (brentq na rama) e o
  balanço completo do sistema (``Equivalent65kWHorizonSystemModel``: stack + DC/DC + auxiliares + hidrogênio pela lei de
  Faraday com utilização). A grandeza usada é ``hydrogen_supplied_kg_h`` (H₂ SUPRIDO, base de custo e do balanço de
  combustível do modelo); o H₂ estequiometricamente consumido é guardado só como referência.

Procedimento (determinístico):

1. condições físicas declaradas (temperatura do stack, pressões de ânodo/cátodo, pressão ambiente) e P_min declarado;
2. rama operacional e P_max = min(máximo da rama, pico declarado do manual) — sem extrapolação;
3. extremos P_min/P_max invertidos pelo PRÓPRIO solucionador do modelo (``solve_requested_power``, brentq na rama) e
   avaliação VETORIZADA do sistema (``Equivalent65kWHorizonSystemModel.evaluate``) numa grade de AJUSTE em CORRENTE entre
   as duas correntes — cada ponto (P_net, q) é uma avaliação exata do modelo;
4. PWL por refinamento: vértices nas extremidades; insere-se o ponto de maior erro relativo até o alvo ou o limite de
   vértices (sem presumir convexidade; não há vértice em (0, 0): OFF é estado separado no MILP, M14–M16);
5. VALIDAÇÃO com pontos INDEPENDENTES (correntes nos meios dos subintervalos da grade + vizinhanças dos extremos),
   avaliados de novo pelo modelo; métricas da adenda B04 (erro absoluto/relativo, subestimação, massa acumulada, extremos, monotonia,
   continuidade, domínio);
6. impressão digital SHA-256 da identidade (condições, P_min, política, versão/fonte do modelo e do gerador, parâmetros
   do modelo) ⇒ REUTILIZAÇÃO: mesma identidade = mesma curva (cache por processo); nunca regenerada por intervalo,
   janela, potência, ON/OFF ou replanejamento.

O modelo Horizon é uma representação física parametrizada APROXIMADA (``h2_pemfc/docs/MODEL_CARD_HORIZON_APPROX.md``),
não caracterização experimental do equipamento da embarcação. Distinguem-se: (a) a certificação MATEMÁTICA da PWL contra
o modelo (B04, aqui), (b) a validação do modelo aproximado e (c) a validação física do equipamento — só (a) é avaliada.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

GERADOR_VERSAO = "curva-h2-pwl-v1"
PERFIL_MODELO = "EQUIVALENT_65KW_HORIZON_CONSTRAINED"   # = seeds2.microgrid.references.PEMFC_REF_KEY
CLASSIFICACAO_CONTRATO = "real"                          # ems_v2.contracts.CLASSIFICACOES_CURVA (nunca "sintetica_exata")
RAIZ = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------------------------- adenda B04
# Política de aceitação PROPOSTA — declarada (e versionada neste arquivo) ANTES de qualquer avaliação definitiva. A
# adenda B04 exige que os limiares sejam APROVADOS pelo responsável antes de avaliar os dados: enquanto
# ``situacao == "proposta_pendente_de_aprovacao"`` uma curva conforme NÃO é "certificada".
POLITICA_B04 = {
    "versao": "b04-proposta-1",
    "situacao": "proposta_pendente_de_aprovacao",
    "erro_rel_max": 0.005,
    "erro_abs_max_kg_h": 0.02,
    "subestimacao_rel_max": 0.001,
    "erro_massa_rel_max": 0.002,
    "pontos_validacao_min": 200,
    "justificativa": {
        "erro_rel_max": "0,5 % — um sexto da incerteza de suprimento associada à utilização mínima do manual (97 %, ±3 %): "
                        "o erro da APROXIMAÇÃO deve ser desprezível frente às incertezas do próprio modelo.",
        "erro_abs_max_kg_h": "0,02 kg/h ≈ 0,4 % do consumo máximo do manual (4,8 kg/h).",
        "subestimacao_rel_max": "0,1 % — o custo do combustível não pode ser materialmente SUBESTIMADO pela PWL.",
        "erro_massa_rel_max": "0,2 % — massa acumulada sobre o domínio (perfil uniforme de potência).",
        "pontos_validacao_min": "Pontos independentes dos de ajuste (meios dos subintervalos) + vizinhanças de P_min/P_max.",
    },
}


@dataclass(frozen=True)
class CondicoesPEMFC:
    """Condições físicas ESTACIONÁRIAS da missão (hipótese do responsável: constantes durante toda a missão)."""
    temperatura_stack_K: float
    pressao_anodo_kPag: float
    pressao_catodo_kPag: float
    pressao_ambiente_kPa: float

    def kwargs(self) -> dict:
        return {"temperature_K": float(self.temperatura_stack_K), "anode_pressure_kPag": float(self.pressao_anodo_kPag),
                "cathode_pressure_kPag": float(self.pressao_catodo_kPag),
                "ambient_pressure_kPa": float(self.pressao_ambiente_kPa)}

    def erros(self) -> list[str]:
        out = []
        for nome, v in asdict(self).items():
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(float(v)):
                out.append(f"{nome}: valor ausente ou não finito.")
        if out:
            return out
        if self.temperatura_stack_K <= 0:
            out.append("temperatura_stack_K deve ser > 0 K.")
        if self.pressao_anodo_kPag < 0 or self.pressao_catodo_kPag < 0:
            out.append("pressões manométricas de ânodo/cátodo devem ser >= 0 kPa(g).")
        if self.pressao_ambiente_kPa <= 0:
            out.append("pressao_ambiente_kPa deve ser > 0.")
        return out


@dataclass(frozen=True)
class PoliticaAproximacao:
    """Parâmetros NUMÉRICOS do gerador (software; não são parâmetros do equipamento)."""
    pontos_ajuste: int = 401
    pontos_validacao: int = 400
    erro_rel_alvo: float = 0.001
    vertices_max: int = 48
    tolerancia_potencia_kW: float = 1e-6


@dataclass
class CurvaH2:
    impressao: str
    identidade: dict
    p_min_kW: float
    p_max_kW: float
    vertices: tuple                       # ((P [kW], q [kg/h H₂ suprido]), …)
    ajuste: dict                          # grade de ajuste: P, q_suprido, q_consumido, corrente
    validacao: dict                       # pontos independentes: P, q_modelo, q_pwl
    metricas: dict
    b04: dict
    diagnostico_rama: dict
    hipoteses: list = field(default_factory=list)

    @property
    def sha_curva(self) -> str:
        return hashlib.sha256(json.dumps([[float(p), float(q)] for p, q in self.vertices],
                                         separators=(",", ":")).encode()).hexdigest()

    def q_pwl(self, p_kW):
        """Vazão da PWL [kg/h] DENTRO do domínio [P_min, P_max]; fora dele ⇒ erro (sem extrapolação)."""
        p = np.atleast_1d(np.asarray(p_kW, dtype=float))
        tol = 1e-9 * max(1.0, self.p_max_kW)
        if (p < self.p_min_kW - tol).any() or (p > self.p_max_kW + tol).any():
            raise ValueError(f"Potência fora do domínio validado [{self.p_min_kW:g}, {self.p_max_kW:g}] kW.")
        P = np.array([v[0] for v in self.vertices])
        Q = np.array([v[1] for v in self.vertices])
        return np.interp(np.clip(p, P[0], P[-1]), P, Q)

    def doc(self) -> dict:
        return {"formato": "seeds2-pemfc-curva-h2", "versao": 1, "impressao": self.impressao, "sha_curva": self.sha_curva,
                "classificacao_contrato": CLASSIFICACAO_CONTRATO, "identidade": self.identidade,
                "dominio_kW": [self.p_min_kW, self.p_max_kW], "vertices_kW_kg_h": [list(v) for v in self.vertices],
                "unidade_q": "kg/h de H₂ SUPRIDO", "ajuste": self.ajuste, "validacao": self.validacao,
                "metricas": self.metricas, "b04": self.b04, "diagnostico_rama": self.diagnostico_rama,
                "hipoteses": list(self.hipoteses)}


# ---------------------------------------------------------------------------------------------- identidade
def _sha_arquivos(base: Path, sufixos=(".py", ".csv", ".json", ".txt")) -> str:
    h = hashlib.sha256()
    for f in sorted(x for x in base.rglob("*") if x.is_file() and x.suffix in sufixos and "__pycache__" not in x.parts
                    and "docs" not in x.relative_to(base).parts):
        h.update(f.relative_to(RAIZ).as_posix().encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)


def _modelo():
    from h2_pemfc import Equivalent65kWHorizonPowerRequestModel
    return Equivalent65kWHorizonPowerRequestModel()


def _parametros_modelo(pr) -> dict:
    sm = pr.system_model
    spec = sm.stack_model.specification
    return {"stack": {k: (float(v) if isinstance(v, (int, float)) else str(v)) for k, v in asdict(spec).items()},
            "balance_of_plant": [r.to_dict() for r in sm.parameter_records],
            "limites_operacionais": {k: (float(v) if isinstance(v, (int, float)) else str(v))
                                     for k, v in asdict(pr.operating_limits).items()},
            "perfil": PERFIL_MODELO, "system_model_id": "VLIIPro50_22_APPROX_BOP_STAGE5"}


def identidade(cond: CondicoesPEMFC, p_min_kW: float, politica: PoliticaAproximacao | None = None,
               *, _pr=None) -> dict:
    pol = politica or PoliticaAproximacao()
    pr = _pr or _modelo()
    return {"gerador": GERADOR_VERSAO, "gerador_fonte_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "modelo_fonte_sha256": _sha_arquivos(RAIZ / "h2_pemfc"), "perfil_modelo": PERFIL_MODELO,
            "condicoes": {k: float(v) for k, v in asdict(cond).items()}, "p_min_kW": float(p_min_kW),
            "politica_aproximacao": asdict(pol), "politica_b04": POLITICA_B04["versao"],
            "parametros_modelo": _parametros_modelo(pr)}


def impressao(ident: dict) -> str:
    return hashlib.sha256(_canon(ident).encode()).hexdigest()


# ---------------------------------------------------------------------------------------------- geração
_CACHE: dict[str, CurvaH2] = {}
GERACOES = {"n": 0}                   # contador de GERAÇÕES (não de consultas): evidência de reutilização


class CurvaInvalida(ValueError):
    """A curva não pode ser gerada sem relaxar o contrato (mensagem apresentável)."""


def _avaliar_potencias(pr, cond: CondicoesPEMFC, p_kW, tol: float):
    """P_net → (q suprido, q consumido, corrente) pelo solucionador do PRÓPRIO modelo (brentq na rama)."""
    p_kW = np.asarray(p_kW, dtype=float)
    df = pr.solve_requested_power(p_kW, **cond.kwargs())
    entregue = df["P_FC_delivered_kW"].to_numpy(dtype=float)
    if np.max(np.abs(entregue - p_kW)) > tol:
        raise CurvaInvalida("O modelo saturou uma potência dentro do domínio declarado (rama inconsistente).")
    return _colunas(df)


def _avaliar_correntes(pr, cond: CondicoesPEMFC, i_A):
    """Corrente → balanço do SISTEMA (avaliação vetorizada do modelo): (P_net, q suprido, q consumido)."""
    df = pr.system_model.evaluate(np.asarray(i_A, dtype=float), **cond.kwargs())
    q, qc, _i = _colunas(df)
    return df["P_net_kW"].to_numpy(dtype=float), q, qc


def _colunas(df):
    q = df["hydrogen_supplied_kg_h"].to_numpy(dtype=float)
    qc = df["hydrogen_consumed_kg_h"].to_numpy(dtype=float) if "hydrogen_consumed_kg_h" in df else np.full_like(q, np.nan)
    i = df["current_A"].to_numpy(dtype=float)
    if not (np.isfinite(q).all() and np.isfinite(i).all()) or (q < 0).any():
        raise CurvaInvalida("O modelo produziu vazão de H₂ ou corrente não finita/negativa.")
    return q, qc, i


def obter_curva(cond: CondicoesPEMFC, p_min_kW, politica: PoliticaAproximacao | None = None) -> CurvaH2:
    """Curva da configuração física (gerada uma vez; reutilizada para a mesma impressão digital)."""
    errs = cond.erros()
    if p_min_kW is None or not isinstance(p_min_kW, (int, float)) or isinstance(p_min_kW, bool) \
            or not math.isfinite(float(p_min_kW)) or float(p_min_kW) <= 0:
        errs.append("P_min declarado ausente ou <= 0 (OFF = (0, 0) é estado separado; não há vértice em zero).")
    if errs:
        raise CurvaInvalida("Parâmetros de inicialização da PEMFC incompletos: " + "; ".join(errs))
    pol = politica or PoliticaAproximacao()
    pr = _modelo()
    ident = identidade(cond, float(p_min_kW), pol, _pr=pr)
    imp = impressao(ident)
    if imp in _CACHE:
        return _CACHE[imp]
    curva = _gerar(pr, cond, float(p_min_kW), pol, ident, imp)
    _CACHE[imp] = curva
    return curva


def _gerar(pr, cond: CondicoesPEMFC, p_min: float, pol: PoliticaAproximacao, ident: dict, imp: str) -> CurvaH2:
    GERACOES["n"] += 1
    try:
        _rama, diag = pr.analyze_operational_branch(**cond.kwargs())
    except (ValueError, RuntimeError) as exc:
        raise CurvaInvalida(f"O modelo recusou as condições declaradas: {exc}") from None
    pico = float(pr.operating_limits.system_peak_power_kW)
    p_max = min(float(diag.net_power_max_kW), pico)
    if not p_min < p_max:
        raise CurvaInvalida(f"P_min = {p_min:g} kW não é menor que o máximo da rama operacional ({p_max:g} kW).")
    if p_min < float(diag.net_power_min_kW):
        raise CurvaInvalida("P_min abaixo do início da rama operacional.")
    tol = pol.tolerancia_potencia_kW
    q_ext, qc_ext, i_ext = _avaliar_potencias(pr, cond, [p_min, p_max], tol)
    corrente = np.linspace(i_ext[0], i_ext[1], int(pol.pontos_ajuste))
    P, q, qc = _avaliar_correntes(pr, cond, corrente)
    P[0], P[-1], q[0], q[-1], qc[0], qc[-1] = p_min, p_max, q_ext[0], q_ext[1], qc_ext[0], qc_ext[1]
    if (np.diff(P) <= 0).any():
        raise CurvaInvalida("A potência líquida do modelo não é estritamente crescente na grade de corrente da rama.")
    if (np.diff(q) <= 0).any():
        raise CurvaInvalida("A vazão de H₂ do modelo não é estritamente crescente na rama: PWL não construída.")
    idx = [0, len(P) - 1]
    while True:
        pwl = np.interp(P, P[idx], q[idx])
        rel = np.abs(pwl - q) / q
        j = int(np.argmax(rel))
        if rel[j] <= pol.erro_rel_alvo or len(idx) >= pol.vertices_max:
            break
        idx = sorted(set(idx) | {j})
    vertices = tuple((float(P[k]), float(q[k])) for k in idx)
    # ---- validação INDEPENDENTE (nenhum ponto coincide com a grade de ajuste)
    n = int(pol.pontos_validacao)
    i0, i1 = float(corrente[0]), float(corrente[-1])
    iv = i0 + (i1 - i0) * (np.arange(n) + 0.5) / n
    iv = np.concatenate([[i0 + 1e-6 * (i1 - i0)], iv, [i1 - 1e-6 * (i1 - i0)]])
    Pv, qv, _qcv = _avaliar_correntes(pr, cond, iv)
    Vp, Vq = np.array([v[0] for v in vertices]), np.array([v[1] for v in vertices])
    qpv = np.interp(Pv, Vp, Vq)
    dif = qpv - qv
    massa_m = float(np.trapezoid(qv, Pv)) if hasattr(np, "trapezoid") else float(np.trapz(qv, Pv))
    massa_p = float(np.trapezoid(qpv, Pv)) if hasattr(np, "trapezoid") else float(np.trapz(qpv, Pv))
    seg2 = np.diff(q, 2)
    metricas = {
        "vertices": len(vertices), "pontos_ajuste": int(len(P)), "pontos_validacao": int(len(Pv)),
        "erro_abs_max_kg_h": float(np.max(np.abs(dif))), "erro_rel_max": float(np.max(np.abs(dif) / qv)),
        "subestimacao_rel_max": float(max(0.0, np.max((qv - qpv) / qv))),
        "sobrestimacao_rel_max": float(max(0.0, np.max((qpv - qv) / qv))),
        "erro_massa_rel": abs(massa_p - massa_m) / massa_m,
        "erro_rel_extremo_inferior": float(abs(dif[0]) / qv[0]), "erro_rel_extremo_superior": float(abs(dif[-1]) / qv[-1]),
        "modelo_estritamente_crescente": bool((np.diff(q) > 0).all()),
        "pwl_estritamente_crescente": bool((np.diff(Vq) > 0).all()),
        "convexa_na_amostra": bool((seg2 >= -1e-12 * float(np.max(q))).all()),
        "continua": True, "dominio_fechado": bool(vertices[0][0] == p_min and vertices[-1][0] == p_max),
        "erro_rel_alvo_ajuste": pol.erro_rel_alvo,
        "q_pmin_kg_h": float(q[0]), "q_pmax_kg_h": float(q[-1]),
        "consumo_especifico_pmin_kg_kWh": float(q[0] / P[0]), "consumo_especifico_pmax_kg_kWh": float(q[-1] / P[-1]),
        "corrente_pmin_A": float(corrente[0]), "corrente_pmax_A": float(corrente[-1]),
    }
    return CurvaH2(
        impressao=imp, identidade=ident, p_min_kW=p_min, p_max_kW=p_max, vertices=vertices,
        ajuste={"P_kW": [float(x) for x in P], "q_suprido_kg_h": [float(x) for x in q],
                "q_consumido_kg_h": [float(x) for x in qc], "corrente_A": [float(x) for x in corrente]},
        validacao={"P_kW": [float(x) for x in Pv], "q_modelo_kg_h": [float(x) for x in qv],
                   "q_pwl_kg_h": [float(x) for x in qpv]},
        metricas=metricas, b04=avaliar_b04(metricas),
        diagnostico_rama={"corrente_min_A": float(diag.current_min_A), "corrente_max_A": float(diag.current_max_A),
                          "potencia_min_rama_kW": float(diag.net_power_min_kW),
                          "potencia_max_rama_kW": float(diag.net_power_max_kW), "pico_declarado_kW": pico,
                          "rama_truncada_por_nao_monotonia": bool(diag.branch_truncated_due_non_monotonicity)},
        hipoteses=["Condições físicas (temperatura do stack, pressões) CONSTANTES durante toda a missão (decisão do "
                   "responsável): uma inicialização física ⇒ uma curva estacionária",
                   "Modelo físico parametrizado APROXIMADO (escala Horizon VLIIPro50-22); não é caracterização "
                   "experimental do equipamento instalado",
                   "q = H₂ SUPRIDO (consumo estequiométrico ÷ utilização do modelo); base do custo e do balanço",
                   "Domínio [P_min declarado, min(máximo da rama operacional, pico declarado)] — sem extrapolação; OFF = "
                   "(0, 0) é estado separado no MILP (não há segmento entre 0 e P_min)",
                   "Curva estacionária: rampas, partida/parada e estados do controlador pertencem ao modelo dinâmico"])


def avaliar_b04(m: dict, politica: dict | None = None) -> dict:
    """Critérios da adenda B04 contra a política DECLARADA. Conformidade ≠ certificação enquanto os limiares não forem
    aprovados pelo responsável."""
    pol = politica or POLITICA_B04
    crit = [
        ("erro_rel_max", m["erro_rel_max"] <= pol["erro_rel_max"], m["erro_rel_max"], pol["erro_rel_max"]),
        ("erro_abs_max_kg_h", m["erro_abs_max_kg_h"] <= pol["erro_abs_max_kg_h"], m["erro_abs_max_kg_h"],
         pol["erro_abs_max_kg_h"]),
        ("subestimacao_rel_max", m["subestimacao_rel_max"] <= pol["subestimacao_rel_max"], m["subestimacao_rel_max"],
         pol["subestimacao_rel_max"]),
        ("erro_massa_rel_max", m["erro_massa_rel"] <= pol["erro_massa_rel_max"], m["erro_massa_rel"],
         pol["erro_massa_rel_max"]),
        ("pontos_validacao_min", m["pontos_validacao"] >= pol["pontos_validacao_min"], m["pontos_validacao"],
         pol["pontos_validacao_min"]),
        ("monotonia", m["modelo_estritamente_crescente"] and m["pwl_estritamente_crescente"], True, True),
        ("dominio_fechado_sem_extrapolacao", m["dominio_fechado"], True, True),
        ("continuidade", m["continua"], True, True),
    ]
    conforme = all(ok for _n, ok, _v, _l in crit)
    aprovada = pol.get("situacao") == "aprovada_pelo_responsavel"
    return {"politica": pol["versao"], "situacao_politica": pol["situacao"],
            "criterios": [{"criterio": n, "atendido": bool(ok), "valor": v, "limiar": lim} for n, ok, v, lim in crit],
            "conforme_aos_limiares": bool(conforme),
            "estado": ("certificada" if conforme and aprovada else
                       "conforme_limiares_pendentes_de_aprovacao" if conforme else "reprovada"),
            "nota": "Certificação MATEMÁTICA da PWL contra o modelo aproximado; não valida o modelo nem o equipamento."}


__all__ = ["CLASSIFICACAO_CONTRATO", "CondicoesPEMFC", "CurvaH2", "CurvaInvalida", "GERACOES", "GERADOR_VERSAO",
           "PERFIL_MODELO", "POLITICA_B04", "PoliticaAproximacao", "avaliar_b04", "identidade", "impressao",
           "obter_curva"]
