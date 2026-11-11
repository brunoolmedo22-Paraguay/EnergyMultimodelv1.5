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
    "versao": "b04-proposta-2",
    "situacao": "aprovada_pelo_responsavel",          # decisão do responsável no PR #23 (2026-11-11); ver o núcleo
    "congelada_em": "2026-11-11",
    "aprovada_em": "2026-11-11",
    "alcance_aprovacao": "Certificação MATEMÁTICA da PWL contra o modelo PEMFC existente (aproximado); não é validação "
                         "experimental do modelo Horizon nem certificação de operação física. Cada curva gerada precisa "
                         "passar na sua própria verificação B04.",
    "erro_rel_max": 0.005,
    "erro_abs_max_kg_h": 0.02,
    "subestimacao_rel_max": 0.001,
    "erro_massa_temporal_rel_max": 0.002,
    "pontos_validacao_min": 200,
    "justificativa": {
        "natureza": "Limiares de ENGENHARIA para o erro da LINEARIZAÇÃO (PWL × modelo de origem). Não derivam de incerteza "
                    "experimental — não há caracterização experimental do equipamento — nem da utilização de H₂ do "
                    "modelo (parâmetro do modelo, não incerteza).",
        "erro_rel_max": "0,5 % por ponto: o custo de H₂ atribuído pelo EMS a cada potência não difere do calculado pelo "
                        "modelo em mais de 0,5 %, duas ordens de grandeza abaixo da variação do consumo específico no "
                        "domínio (≈ 27 % entre P_mín e P_máx na configuração nominal).",
        "erro_abs_max_kg_h": "0,02 kg/h: escala de referência = consumo máximo do manual (4,8 kg/h) — 0,4 % dessa escala; "
                             "limita o erro absoluto onde a vazão é pequena.",
        "subestimacao_rel_max": "0,1 %: assimetria conservadora — o custo do combustível não pode ser materialmente "
                                "SUBESTIMADO pela PWL (sobrestimação é admitida até o limiar de erro relativo).",
        "erro_massa_temporal_rel_max": "0,2 % da massa acumulada Σ q(P(t))·Δt [kg] em cada perfil TEMPORAL independente "
                                       "(carga parcial, nominal e despachos variáveis).",
        "pontos_validacao_min": "Pontos independentes dos de ajuste (meios dos subintervalos) + vizinhanças de P_min/P_max.",
    },
}
# Condições físicas de GENERALIZAÇÃO: NÃO foram usadas para escolher os limiares (avaliadas depois de congelar a
# política b04-proposta-2). A configuração nominal e a de 343,15 K/100/80 kPa(g) foram as exploradas no ajuste.
CONDICOES_GENERALIZACAO = (
    (333.15, 140.0, 120.0, 101.325), (358.15, 140.0, 120.0, 101.325), (353.15, 160.0, 140.0, 101.325),
    (353.15, 120.0, 100.0, 95.0), (348.15, 130.0, 110.0, 100.0),
)


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
    perfis: list = field(default_factory=list)            # perfis TEMPORAIS de massa acumulada (B04)

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
                "perfis_temporais": self.perfis,
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
               *, _pr=None, p_max_limite_kW: float | None = None) -> dict:
    pol = politica or PoliticaAproximacao()
    pr = _pr or _modelo()
    return {"gerador": GERADOR_VERSAO, "gerador_fonte_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "modelo_fonte_sha256": _sha_arquivos(RAIZ / "h2_pemfc"), "perfil_modelo": PERFIL_MODELO,
            "condicoes": {k: float(v) for k, v in asdict(cond).items()}, "p_min_kW": float(p_min_kW),
            "p_max_limite_kW": None if p_max_limite_kW is None else float(p_max_limite_kW),
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


def obter_curva(cond: CondicoesPEMFC, p_min_kW, politica: PoliticaAproximacao | None = None, *,
                p_max_limite_kW: float | None = None) -> CurvaH2:
    """Curva da configuração física (gerada uma vez; reutilizada para a mesma impressão digital)."""
    errs = cond.erros()
    if p_min_kW is None or not isinstance(p_min_kW, (int, float)) or isinstance(p_min_kW, bool) \
            or not math.isfinite(float(p_min_kW)) or float(p_min_kW) <= 0:
        errs.append("P_min declarado ausente ou <= 0 (OFF = (0, 0) é estado separado; não há vértice em zero).")
    if errs:
        raise CurvaInvalida("Parâmetros de inicialização da PEMFC incompletos: " + "; ".join(errs))
    pol = politica or PoliticaAproximacao()
    pr = _modelo()
    ident = identidade(cond, float(p_min_kW), pol, _pr=pr, p_max_limite_kW=p_max_limite_kW)
    imp = impressao(ident)
    if imp in _CACHE:
        return _CACHE[imp]
    curva = _gerar(pr, cond, float(p_min_kW), pol, ident, imp, p_max_limite_kW)
    _CACHE[imp] = curva
    return curva


def _gerar(pr, cond: CondicoesPEMFC, p_min: float, pol: PoliticaAproximacao, ident: dict, imp: str,
           p_max_limite: float | None = None) -> CurvaH2:
    GERACOES["n"] += 1
    try:
        _rama, diag = pr.analyze_operational_branch(**cond.kwargs())
    except (ValueError, RuntimeError) as exc:
        raise CurvaInvalida(f"O modelo recusou as condições declaradas: {exc}") from None
    pico = float(pr.operating_limits.system_peak_power_kW)
    p_max = min(float(diag.net_power_max_kW), pico, float("inf") if p_max_limite is None else float(p_max_limite))
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
    integ = getattr(np, "trapezoid", None) or np.trapz
    massa_m, massa_p = float(integ(qv, Pv)), float(integ(qpv, Pv))     # ∫ q dP — métrica sobre o DOMÍNIO de potência
    perfis = _perfis_temporais(pr, cond, corrente, P, q, (Vp, Vq))
    seg2 = np.diff(q, 2)
    metricas = {
        "vertices": len(vertices), "pontos_ajuste": int(len(P)), "pontos_validacao": int(len(Pv)),
        "erro_abs_max_kg_h": float(np.max(np.abs(dif))), "erro_rel_max": float(np.max(np.abs(dif) / qv)),
        "subestimacao_rel_max": float(max(0.0, np.max((qv - qpv) / qv))),
        "sobrestimacao_rel_max": float(max(0.0, np.max((qpv - qv) / qv))),
        "erro_integral_dominio_potencia_rel": abs(massa_p - massa_m) / massa_m,
        "erro_massa_temporal_rel_max": max(x["erro_massa_rel"] for x in perfis),
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
                   "q_pwl_kg_h": [float(x) for x in qpv], "corrente_A": [float(x) for x in iv]},
        perfis=perfis,
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


def _perfis_temporais(pr, cond: CondicoesPEMFC, corrente, P, q, vertices) -> list:
    """Perfis TEMPORAIS independentes (passo de 1 min): cargas parciais constantes, potência nominal e dois despachos
    variáveis. Cada passo é uma avaliação EXATA do modelo numa corrente da rama (P_net e q do mesmo ponto); a massa é
    Σ q·Δt [kg] com Δt em HORAS — modelo × PWL."""
    i0, i1 = float(corrente[0]), float(corrente[-1])
    Vp, Vq = vertices
    passo_h = 1.0 / 60.0
    rng = np.random.default_rng(20261111)
    def corrente_de(pot):
        return float(np.interp(pot, P, corrente))
    frac = lambda f: float(P[0] + f * (P[-1] - P[0]))  # noqa: E731
    defs = [
        ("carga_parcial_25", np.full(240, corrente_de(frac(0.25)))),
        ("carga_parcial_50", np.full(240, corrente_de(frac(0.50)))),
        ("carga_parcial_75", np.full(240, corrente_de(frac(0.75)))),
        ("nominal_pmax", np.full(240, i1)),
        ("despacho_degraus_15min", np.repeat(rng.uniform(i0, i1, 96), 15)),
        ("despacho_continuo_senoidal", i0 + (i1 - i0) * 0.5 * (1 - np.cos(2 * np.pi * np.arange(1440) / 480.0))),
    ]
    out = []
    for nome, cs in defs:
        cs = np.clip(np.asarray(cs, dtype=float), i0, i1)
        un, inv = np.unique(cs, return_inverse=True)
        Pu, qu, _qc = _avaliar_correntes(pr, cond, un)
        if nome == "nominal_pmax":
            Pu, qu = np.array([P[-1]]), np.array([q[-1]])         # extremo exato (inversão do próprio modelo)
        pot, vaz = Pu[inv], qu[inv]
        mm = math.fsum(float(x) * passo_h for x in vaz)
        mp = math.fsum(float(x) * passo_h for x in np.interp(pot, Vp, Vq))
        out.append({"nome": nome, "passo_h": passo_h, "duracao_h": len(cs) * passo_h, "correntes_A": [float(x) for x in cs],
                    "potencias_kW": [float(x) for x in pot], "vazoes_modelo_kg_h": [float(x) for x in vaz],
                    "massa_modelo_kg": mm, "massa_pwl_kg": mp, "erro_massa_rel": abs(mp - mm) / mm})
    return out


def politica_nucleo(politica: dict | None = None):
    """``ems_v2.contracts.PoliticaB04`` com o conteúdo da política da integração (a situação é a DECLARADA aqui; quem a
    decide é o registro do núcleo, pela identidade do conteúdo)."""
    from ems_v2.contracts import PoliticaB04
    pol = politica or POLITICA_B04
    return PoliticaB04(pol["versao"], pol["situacao"], float(pol["erro_rel_max"]), float(pol["erro_abs_max_kg_h"]),
                       float(pol["subestimacao_rel_max"]), float(pol["erro_massa_temporal_rel_max"]),
                       int(pol["pontos_validacao_min"]))


def hash_politica_nucleo(politica: dict | None = None) -> str:
    from ems_v2.contracts import hash_politica_b04
    return hash_politica_b04(politica_nucleo(politica))


def certificado_b04(curva: CurvaH2, politica: dict | None = None):
    """``ems_v2.contracts.CertificadoB04`` da curva (dados verificáveis: vértices, validação independente, perfis
    temporais). O núcleo RECOMPUTA os critérios no registro; a aprovação vem da política declarada."""
    from ems_v2.contracts import CertificadoB04, PerfilMassaB04
    from ems_v2.provenance import Procedencia
    p = politica_nucleo(politica)
    val = tuple(zip(curva.validacao["P_kW"], curva.validacao["q_modelo_kg_h"]))
    perfis = tuple(PerfilMassaB04(x["nome"], float(x["passo_h"]), tuple(x["potencias_kW"]), tuple(x["vazoes_modelo_kg_h"]))
                   for x in curva.perfis)
    proc = Procedencia("referencia", "h2_pemfc · modelo físico parametrizado APROXIMADO (escala Horizon VLIIPro50-22)",
                       f"curva {curva.impressao}", sha256=curva.sha_curva,
                       observacoes="certificação MATEMÁTICA da PWL contra o modelo de origem (adenda B04); não valida o "
                                   "modelo nem o equipamento")
    return CertificadoB04(1, p, tuple((float(a), float(b)) for a, b in curva.vertices),
                          tuple((float(a), float(b)) for a, b in val), perfis, curva.impressao, proc)


def verificar_contra_modelo(doc: dict, tol_rel: float = 1e-12) -> list[str]:
    """Reavalia o MODELO nas correntes de validação e dos perfis do documento da curva: os valores "do modelo" do
    certificado têm de ser do modelo (não declarados). Exige o modelo — usado no preflight, nunca na reabertura."""
    pr = _modelo()
    c = doc["identidade"]["condicoes"]
    cond = CondicoesPEMFC(c["temperatura_stack_K"], c["pressao_anodo_kPag"], c["pressao_catodo_kPag"],
                          c["pressao_ambiente_kPa"])
    out = []
    P, q, _ = _avaliar_correntes(pr, cond, doc["validacao"]["corrente_A"])
    if not (np.allclose(P, doc["validacao"]["P_kW"], rtol=tol_rel, atol=0)
            and np.allclose(q, doc["validacao"]["q_modelo_kg_h"], rtol=tol_rel, atol=0)):
        out.append("pontos de validação não reproduzem o modelo")
    for x in doc["perfis_temporais"]:
        if x["nome"] == "nominal_pmax":
            continue
        P, q, _ = _avaliar_correntes(pr, cond, x["correntes_A"])
        if not (np.allclose(P, x["potencias_kW"], rtol=tol_rel, atol=0)
                and np.allclose(q, x["vazoes_modelo_kg_h"], rtol=tol_rel, atol=0)):
            out.append(f"perfil {x['nome']} não reproduz o modelo")
    return out


def avaliar_generalizacao(p_min_kW: float = 10.0) -> list[dict]:
    """B04 nas condições de GENERALIZAÇÃO (não usadas para escolher os limiares)."""
    out = []
    for t, pa, pc, pamb in CONDICOES_GENERALIZACAO:
        c = obter_curva(CondicoesPEMFC(t, pa, pc, pamb), p_min_kW)
        out.append({"condicoes": [t, pa, pc, pamb], "p_max_kW": c.p_max_kW, "vertices": len(c.vertices),
                    "erro_rel_max": c.metricas["erro_rel_max"], "subestimacao_rel_max": c.metricas["subestimacao_rel_max"],
                    "erro_massa_temporal_rel_max": c.metricas["erro_massa_temporal_rel_max"],
                    "conforme": c.b04["conforme_aos_limiares"]})
    return out


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
        ("erro_massa_temporal_rel_max", m["erro_massa_temporal_rel_max"] <= pol["erro_massa_temporal_rel_max"],
         m["erro_massa_temporal_rel_max"], pol["erro_massa_temporal_rel_max"]),
        ("pontos_validacao_min", m["pontos_validacao"] >= pol["pontos_validacao_min"], m["pontos_validacao"],
         pol["pontos_validacao_min"]),
        ("monotonia", m["modelo_estritamente_crescente"] and m["pwl_estritamente_crescente"], True, True),
        ("dominio_fechado_sem_extrapolacao", m["dominio_fechado"], True, True),
        ("continuidade", m["continua"], True, True),
    ]
    conforme = all(ok for _n, ok, _v, _l in crit)
    from ems_v2.contracts import SITUACAO_B04_APROVADA, situacao_politica_b04
    sit, cod = situacao_politica_b04(politica_nucleo(pol))     # AUTORIDADE = registro do núcleo, nunca a autodeclaração
    aprovada = cod == "conhecida" and sit == SITUACAO_B04_APROVADA and pol.get("situacao") == sit
    return {"politica": pol["versao"], "situacao_politica": pol["situacao"],
            "politica_no_nucleo": {"reconhecimento": cod, "situacao": sit},
            "criterios": [{"criterio": n, "atendido": bool(ok), "valor": v, "limiar": lim} for n, ok, v, lim in crit],
            "conforme_aos_limiares": bool(conforme),
            "estado": ("politica_nao_reconhecida_pelo_nucleo" if cod != "conhecida" else
                       "certificada" if conforme and aprovada else
                       "conforme_limiares_pendentes_de_aprovacao" if conforme else "reprovada"),
            "nota": "Certificação MATEMÁTICA da PWL contra o modelo aproximado; não valida o modelo nem o equipamento."}


__all__ = ["CLASSIFICACAO_CONTRATO", "CONDICOES_GENERALIZACAO", "CondicoesPEMFC", "CurvaH2", "CurvaInvalida", "GERACOES",
           "GERADOR_VERSAO", "PERFIL_MODELO", "POLITICA_B04", "PoliticaAproximacao", "avaliar_b04", "avaliar_generalizacao",
           "certificado_b04", "identidade", "impressao", "obter_curva", "verificar_contra_modelo"]
