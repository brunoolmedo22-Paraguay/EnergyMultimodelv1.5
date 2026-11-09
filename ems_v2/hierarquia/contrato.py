"""Contratos do perfil ``v1.1-3C-4`` — termo terminal, sinal de valor futuro, entrada hierárquica e planejador.

Só biblioteca padrão. Extensão CONTROLADA e versionada (nenhum contrato anterior é tocado): a entrada da janela 3C-4 é
um EMBRULHO (``EntradaHierarquica3C4``) que contém uma ``EntradaRede3C3`` validada SEM relaxação e acrescenta UM termo
terminal (``TermoTerminal3C4``). Uma ``EntradaRede3C3`` nunca ganha termo terminal implicitamente: o perfil 3C-3
histórico continua idêntico (mesmos hashes, mesmo modelo).

Convenções (unidades e sinais — sem padrão):

* ``V`` [R$] é CUSTO de continuação (a minimizar) a partir da fronteira terminal da janela; energia útil ⇒ ``V``
  decrescente em ``E``;
* ``λ_E = −∂V/∂E`` [R$/kWh] é o BENEFÍCIO marginal de dispor de mais energia armazenada na fronteira (positivo quando a
  energia é útil); a aproximação local é ``V̂(E) = V(E_ref) − λ_E (E − E_ref)`` (aproximação LOCAL, não identidade
  global);
* ``Φ_L`` é o termo terminal DECLARADO do próprio planejador no fim do horizonte longo (``nenhum_declarado`` exige
  justificativa: a miopia terminal é reconhecida, nunca presumida; ``valor_linear_declarado`` usa
  ``Φ_L(E) = −Σ_b λ_b E_b`` com λ_b >= 0 declarados; ``energia_minima_declarada`` impõe ``E_b >= Ē_b``).

Modos terminais: o valor de continuação depende do estado discreto dos geradores na fronteira. Cada ``ModoValor``
declara, por gerador, ``ligado`` e a OBRIGAÇÃO RESIDUAL de permanência na fronteira (e, se necessário, a potência
fixada no último intervalo). O MILP curto só pode terminar num modo do sinal (seleção binária exata, sem Big-M) e a
memória terminal efetiva tem de coincidir com a do modo (verificada pelo auditor). Prova de que tempo no estado além
de T não altera a cauda: ``FORMULACAO_3C4.md`` §4.3.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace

from ..compromisso.contrato import POLITICAS_PERMANENCIA, discretizar
from ..contracts import ErroSerializacao, _constante_proibida, de_dict, para_dict
from ..diagnostics import Constatacao, RelatorioValidacao, erro
from ..provenance import Procedencia, validar_procedencia
from ..rede.contrato import EntradaRede3C3, validar_entrada_3c3
from ..timegrid import ler_instante_utc
from . import ESQUEMA_3C4, FORMULACAO_3C4

TIPOS_TERMO_TERMINAL = {
    "nenhum_declarado": "Φ ≡ 0 DECLARADO (energia/estado terminais sem valor por declaração explícita e justificada)",
    "valor_linear_declarado": "Φ(E) = −Σ_b λ_b E_b, λ_b >= 0 [R$/kWh] declarados com procedência",
    "energia_minima_declarada": "E_b(N) >= Ē_b [kWh] (restrição dura declarada; Φ = 0)",
    "sinal_valor_futuro": "V̂ do SinalValorFuturo emitido pelo planejador de longo prazo (instrumento de decisão)",
}
TERMOS_DECLARADOS = ("nenhum_declarado", "valor_linear_declarado", "energia_minima_declarada")
TIPOS_SINAL = {
    "custo_futuro_pwl": "PRINCIPAL: V^tail por reotimização paramétrica auditada em pontos de energia, por modo terminal; "
                        "interpolante linear por partes (1D) ou envoltória convexa verificada (2D)",
    "valor_marginal_local": "V̂(E) = V(E_ref) − λ(E − E_ref) com λ por diferença central de reotimizações; válido só no "
                            "domínio [E_ref − δ, E_ref + δ] e no modo de referência",
    "referencia_energia_dura": "Referência EXPERIMENTAL: E(N) >= E_ref do plano longo (sem custo; não é valor econômico)",
    "referencia_energia_branda": "Referência EXPERIMENTAL: penalidade DECLARADA ρ·max(0, E_ref − E(N)) — heurística "
                                 "rotulada, não valor econômico derivado",
}
REPRESENTACOES = {
    "constante_0d": "Sem bancos: um valor por modo",
    "intervalos_consecutivos_1d": "1 banco: interpolante linear por partes entre pontos consecutivos (exato, convexo ou "
                                  "não), por modo",
    "envoltoria_convexa_nd": "2 bancos: envoltória convexa inferior dos pontos — só com convexidade verificada NA "
                             "AMOSTRA (pontos da grade; centros validados); não é prova de convexidade global de V",
    "linear_local": "Aproximação linear local (um modo, domínio de validade explícito)",
    "referencia": "Referência terminal energética (sem função de valor)",
}
ESTADOS_SINAL = {"valido": "Utilizável pelo MPC", "indisponivel": "Não utilizável (motivo registrado)"}
ESTADOS_MODO = {
    "valido": "Representação aceita: pontos auditados, domínio delimitado e tolerâncias declaradas atendidas",
    "inviavel": "Cauda INVIÁVEL em TODA a faixa de energia considerada — justificada por certificado de cobertura do "
                "solver com a energia inicial LIVRE na faixa (ou por avaliação única quando não há banco); só então o "
                "modo é excluído (C-3C4-A02)",
    "dominio_indeterminado": "Cobertura insuficiente para concluir (amostras inviáveis sem certificado, certificado "
                             "inconclusivo ou ponto proposto não confirmado): o modo NÃO pode ser excluído nem "
                             "representado ⇒ o sinal fica indisponível",
    "indisponivel": "Representação não sustentável cientificamente (domínio não conexo, tolerância não atingida, "
                    "2D não convexo na amostra, avaliação falha)",
}
POLITICAS_ATUALIZACAO = {
    "a_cada_janela": "O planejador é executado em cada τ_k (sinal para a fronteira k + N_k)",
    "periodica": "O planejador é executado a cada P janelas e emite, em τ_p, um LOTE de sinais para as fronteiras das P "
                 "janelas do cronograma nominal (informação de τ_p; fim do planejamento fixo em p + H_L). Um sinal só "
                 "vale para a SUA janela/fronteira (nunca reutilizado em outra); fronteira divergente ⇒ replanejamento",
}
COBERTURAS_FIM_MISSAO = {
    "reduzido_ao_fim_da_missao": "H_L,k = min(H_L, K_M − k): nenhum planejamento além de T_M (sem previsão inventada)",
}
DEGRADACOES = {
    "interromper": "Sinal indisponível ⇒ janela recusada (falha 'bloqueado_validacao', política de falhas da missão)",
    "sem_valor_futuro_rotulado": "Sinal indisponível ⇒ janela resolvida com o termo 'nenhum_declarado' e registrada como "
                                 "DEGRADADA (equivale ao MPC 3C-3 sem coordenação nesta janela)",
    "referencia_terminal_do_plano_longo": "Sinal indisponível ⇒ referência dura E(N) >= E_ref do plano longo (se o plano "
                                          "longo existir); senão interrompe",
}
CONVENCAO_SINAIS = ("V [R$] = custo de continuação a minimizar a partir da fronteira; λ_E = −∂V/∂E [R$/kWh] = benefício "
                    "marginal de mais energia armazenada; energia em kWh no barramento interno do banco")
TOL_E = 1e-6


# =============================================================================== dataclasses
@dataclass(frozen=True)
class ParametroBateria:
    uid: str
    valor: float


@dataclass(frozen=True)
class EstadoTerminalGerador:
    uid: str
    ligado: bool
    obrigacao_residual_s: int
    potencia_fixada_kW: float | None = None      # p no último intervalo fixado (só se a rampa da cauda não é inativa)


@dataclass(frozen=True)
class PontoValor:
    energias_kWh: tuple[float, ...]              # ordem = SinalValorFuturo.baterias
    valor_R: float                               # V^tail (objetivo ótimo auditado)
    limite_inferior_R: float | None              # limite dual do solver (gap)
    classificacao: str                           # classificação da reotimização


@dataclass(frozen=True)
class ModoValor:
    indice: int
    geradores: tuple[EstadoTerminalGerador, ...]  # vazio = sem condicionamento (só cauda vazia)
    representacao: str
    pontos: tuple[PontoValor, ...]
    energias_inviaveis: tuple[tuple[float, ...], ...]   # pontos amostrados com cauda INVIÁVEL (evidência do domínio)
    dominio_min_kWh: tuple[float, ...]
    dominio_max_kWh: tuple[float, ...]
    convexidade_verificada_na_amostra: bool      # verificação SOBRE A AMOSTRA (pontos/centros), não prova global


@dataclass(frozen=True)
class DiagnosticoModo:
    """Resultado do planejador para UM estado terminal (incluído ou não no sinal) — C-3C4-A02."""
    geradores: tuple[EstadoTerminalGerador, ...]
    estado: str                                  # ESTADOS_MODO
    justificativa: str
    faixas_kWh: tuple[tuple[float, float], ...]  # faixas consideradas por banco
    certificados: tuple[str, ...]                # p. ex. "cobertura[lo,hi]:inviavel/infeasible"
    indice_no_sinal: int | None = None


@dataclass(frozen=True)
class ReferenciaTerminal:
    energias_kWh: tuple[float, ...]
    geradores: tuple[EstadoTerminalGerador, ...]
    valor_R: float | None
    origem: str                                  # "plano_longo"


@dataclass(frozen=True)
class SensibilidadeLocal:
    modo: int
    energias_referencia_kWh: tuple[float, ...]
    delta_kWh: float
    energias_inferiores_kWh: tuple[float, ...]
    energias_superiores_kWh: tuple[float, ...]
    valor_referencia_R: float
    valores_inferiores_R: tuple[float, ...]
    valores_superiores_R: tuple[float, ...]
    lambdas_R_kWh: tuple[float, ...]             # λ_b = −(V⁺ − V⁻)/(E⁺ − E⁻)
    metodo: str                                  # "diferenca_central" | "diferenca_unilateral_no_limite"


@dataclass(frozen=True)
class PontoValidacao:
    modo: int
    energias_kWh: tuple[float, ...]
    valor_reotimizado_R: float
    valor_aproximado_R: float
    erro_R: float


@dataclass(frozen=True)
class QualidadeSinal:
    estado: str                                  # ESTADOS_SINAL
    motivo: str
    erro_interpolacao_max_R: float | None
    tolerancia_interpolacao_R: float
    gap_abs_max_R: float | None
    avaliacoes: int
    validacoes: tuple[PontoValidacao, ...]


@dataclass(frozen=True)
class TermoTerminal3C4:
    tipo: str                                    # TIPOS_TERMO_TERMINAL
    lineares: tuple[ParametroBateria, ...]       # λ_b [R$/kWh] (valor_linear_declarado)
    energias_minimas: tuple[ParametroBateria, ...]   # Ē_b [kWh] (energia_minima_declarada)
    sinal: SinalValorFuturo | None
    justificativa: str
    procedencia: Procedencia | None


@dataclass(frozen=True)
class SinalValorFuturo:
    esquema: int
    perfil: str
    tipo: str                                    # TIPOS_SINAL
    missao_uid: str
    microrrede_uid: str
    cenario_uid: str
    indice_janela: int                           # janela de APLICAÇÃO (única)
    k_aplicacao: int
    instante_aplicacao_utc: str                  # τ_k
    instante_emissao_utc: str                    # τ_p <= τ_k (informação usada)
    indice_fronteira: int                        # b = k + N_k (global)
    instante_fronteira_utc: str
    indice_fim_planejamento: int                 # p + H_L,p (global)
    intervalos_cauda: int                        # fim − b (0 ⇒ sinal = Φ_L)
    baterias: tuple[str, ...]
    geradores: tuple[str, ...]
    unidade_valor: str                           # "R$"
    unidade_energia: str                         # "kWh"
    convencao: str
    modos: tuple[ModoValor, ...]
    referencia: ReferenciaTerminal | None
    sensibilidade: SensibilidadeLocal | None
    penalidade_branda_R_kWh: float | None
    termo_longo: TermoTerminal3C4                # Φ_L declarado do planejador (sem sinal)
    qualidade: QualidadeSinal
    hashes: dict[str, str]                       # previsão longa, instantâneo, tarifas, modelo, estado, configuração
    procedencia: Procedencia | None
    selo: str = ""
    diagnostico_modos: tuple[DiagnosticoModo, ...] = ()     # todos os estados terminais avaliados (A02)


@dataclass(frozen=True)
class EntradaHierarquica3C4:
    versao_esquema_3c4: int
    versao_formulacao: str                       # == FORMULACAO_3C4
    rede: EntradaRede3C3                         # núcleo 3C-3 (validado sem relaxação)
    terminal: TermoTerminal3C4
    procedencia: Procedencia | None

    @property
    def base(self):
        return self.rede.base

    @property
    def compromisso(self):
        return self.rede.compromisso


@dataclass(frozen=True)
class ConfiguracaoPlanejador3C4:
    esquema: int
    perfil: str
    horizonte_longo_intervalos: int              # H_L (em Δ da missão); exige H_L > N e H_f >= H_L Δ
    cobertura_fim_missao: str                    # COBERTURAS_FIM_MISSAO
    termo_longo: TermoTerminal3C4                # Φ_L (tipo em TERMOS_DECLARADOS)
    permanencia_fim_planejamento: str            # POLITICAS_PERMANENCIA (fim do horizonte longo)
    politica_atualizacao: str                    # POLITICAS_ATUALIZACAO
    periodo_janelas: int                         # P (1 em a_cada_janela)
    tipo_sinal: str                              # TIPOS_SINAL
    pontos_iniciais: int                         # pontos de energia por banco (>= 2)
    pontos_max: int                              # limite do refinamento 1D (>= pontos_iniciais)
    tolerancia_interpolacao_R: float             # erro admitido nos pontos de validação
    tolerancia_dominio_kWh: float                # bissecção da fronteira de factibilidade
    delta_sensibilidade_kWh: float | None        # δ (valor_marginal_local)
    penalidade_branda_R_kWh: float | None        # ρ (referencia_energia_branda)
    max_modos: int                               # limite de combinações de estados de geradores
    degradacao: str                              # DEGRADACOES
    justificativa: str
    procedencia: Procedencia | None


# =============================================================================== hashes
def hash_sinal(s: SinalValorFuturo) -> str:
    from ..ponte.canonico import sha256
    return sha256(replace(s, selo=""))


def selar_sinal(s: SinalValorFuturo) -> SinalValorFuturo:
    return replace(s, selo=hash_sinal(s))


def sinal_selado(s: SinalValorFuturo) -> bool:
    try:
        return s.selo == hash_sinal(s)
    except (TypeError, ValueError):            # NaN/Inf/objeto não serializável
        return False


def hash_termo(t: TermoTerminal3C4) -> str:
    from ..ponte.canonico import sha256
    return sha256(t)


def hash_configuracao_planejador(c: ConfiguracaoPlanejador3C4) -> str:
    from ..ponte.canonico import sha256
    return sha256(c)


def json_canonico_3c4(e: EntradaHierarquica3C4) -> str:
    return json.dumps(para_dict(e), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def hash_entrada_3c4(e: EntradaHierarquica3C4) -> str:
    return hashlib.sha256(json_canonico_3c4(e).encode("utf-8")).hexdigest()


def entrada_3c4_de_json(texto: str) -> EntradaHierarquica3C4:
    try:
        dado = json.loads(texto, parse_constant=_constante_proibida)
    except json.JSONDecodeError as exc:
        raise ErroSerializacao(f"JSON inválido: {exc}") from None
    return de_dict(EntradaHierarquica3C4, dado, "EntradaHierarquica3C4")


# =============================================================================== utilidades
def _real(x) -> bool:
    return type(x) in (int, float) and math.isfinite(x)


def _inteiro(x) -> bool:
    return type(x) is int


def limites_energia(e: EntradaRede3C3) -> dict[str, tuple[float, float]]:
    """[C s_min, C s_max] por banco (limites físicos M08 declarados)."""
    out = {}
    for b in e.base.baterias:
        C = float(b.capacidade_kWh.valor)
        out[str(b.uid)] = (C * float(b.soc_min.valor), C * float(b.soc_max.valor))
    return out


def residuo_terminal_herdado(e: EntradaRede3C3) -> dict[str, tuple[int, int, int]]:
    """Por gerador: (u_anterior, intervalos forçados r, obrigação residual NA FRONTEIRA [s] se r >= N senão 0).
    A obrigação herdada que ultrapassa a janela é FATO conhecido em τ_k (nunca escolhida pelo MILP)."""
    disc = discretizar(e.compromisso)
    N = e.base.malha.N
    out = {}
    for g in e.base.geradores:
        d = disc[str(g.uid)]
        out[str(g.uid)] = (d.u_anterior, d.obrigacao_inicial_intervalos,
                           int(d.obrigacao_alem_da_janela_s) if d.obrigacao_inicial_intervalos > N else 0)
    return out


def modo_condicionado(s: SinalValorFuturo) -> bool:
    return s.tipo in ("custo_futuro_pwl", "valor_marginal_local")


# =============================================================================== validação do termo/sinal
def validar_termo_declarado(t: TermoTerminal3C4, e: EntradaRede3C3 | None, cam: str) -> list[Constatacao]:
    if not isinstance(t, TermoTerminal3C4):
        return [erro("termo_terminal_invalido", cam, f"Esperado TermoTerminal3C4; recebido {type(t).__name__}.")]
    out: list[Constatacao] = []
    if t.tipo not in TIPOS_TERMO_TERMINAL:
        return [erro("termo_terminal_tipo_invalido", cam + ".tipo", f"{t.tipo!r} (sem padrão).")]
    out += validar_procedencia(t.procedencia, cam + ".procedencia")
    if not isinstance(t.justificativa, str) or not t.justificativa.strip():
        out.append(erro("termo_terminal_sem_justificativa", cam + ".justificativa",
                        "O tratamento terminal exige justificativa explícita (nenhuma miopia é presumida)."))
    if t.tipo == "sinal_valor_futuro":
        if t.sinal is None:
            out.append(erro("sinal_ausente", cam + ".sinal", "Termo 'sinal_valor_futuro' sem sinal."))
        if t.lineares or t.energias_minimas:
            out.append(erro("termo_terminal_ambiguo", cam, "Sinal com parâmetros declarados adicionais."))
        return out
    if t.sinal is not None:
        out.append(erro("termo_terminal_ambiguo", cam + ".sinal", f"Termo {t.tipo!r} com sinal."))
    bats = None if e is None else {str(b.uid) for b in e.base.baterias}
    lim = None if e is None else limites_energia(e)
    for nome, lista, exig in (("lineares", t.lineares, t.tipo == "valor_linear_declarado"),
                              ("energias_minimas", t.energias_minimas, t.tipo == "energia_minima_declarada")):
        if not exig:
            if lista:
                out.append(erro("termo_terminal_ambiguo", f"{cam}.{nome}", f"{nome} só em seu tipo."))
            continue
        uids = [p.uid for p in lista]
        if len(set(uids)) != len(uids):
            out.append(erro("uid_duplicado", f"{cam}.{nome}", "Banco repetido."))
        if bats is not None and set(uids) != bats:
            out.append(erro("termo_terminal_bancos_divergentes", f"{cam}.{nome}",
                            f"Declarado para {sorted(uids)}; a entrada tem {sorted(bats)} (todo banco declarado, sem "
                            "padrão)."))
        for p in lista:
            if not _real(p.valor) or p.valor < 0:
                out.append(erro("termo_terminal_valor_invalido", f"{cam}.{nome}[{p.uid}]",
                                f"{p.valor!r}: exigido real finito >= 0."))
            elif nome == "energias_minimas" and lim is not None and p.uid in lim and p.valor > lim[p.uid][1] + TOL_E:
                out.append(erro("energia_minima_inalcancavel", f"{cam}.{nome}[{p.uid}]",
                                f"Ē = {p.valor} > C s_max = {lim[p.uid][1]}."))
    return out


def validar_sinal(s: SinalValorFuturo, cam: str = "sinal") -> list[Constatacao]:
    """Estrutura, selo, unidades, finitude, domínios e representação (independente de janela)."""
    if not isinstance(s, SinalValorFuturo):
        return [erro("sinal_invalido", cam, f"Esperado SinalValorFuturo; recebido {type(s).__name__}.")]
    out: list[Constatacao] = []
    if not sinal_selado(s):
        out.append(erro("sinal_adulterado", cam + ".selo", "Selo do sinal não confere (conteúdo alterado ou não "
                                                           "serializável)."))
    if type(s.esquema) is not int or s.esquema != ESQUEMA_3C4:
        out.append(erro("sinal_esquema_incompativel", cam + ".esquema", f"{s.esquema!r}."))
    if s.perfil != FORMULACAO_3C4:
        out.append(erro("sinal_perfil_incompativel", cam + ".perfil", f"{s.perfil!r}."))
    if s.tipo not in TIPOS_SINAL:
        return out + [erro("sinal_tipo_invalido", cam + ".tipo", f"{s.tipo!r}.")]
    if s.unidade_valor != "R$" or s.unidade_energia != "kWh" or s.convencao != CONVENCAO_SINAIS:
        out.append(erro("sinal_unidade_ou_convencao_divergente", cam, "Unidades/convenção de sinais ≠ do contrato."))
    if s.qualidade.estado not in ESTADOS_SINAL:
        out.append(erro("sinal_estado_invalido", cam + ".qualidade.estado", f"{s.qualidade.estado!r}."))
    for nome in ("indice_janela", "k_aplicacao", "indice_fronteira", "indice_fim_planejamento", "intervalos_cauda"):
        v = getattr(s, nome)
        if not _inteiro(v) or v < 0:
            out.append(erro("sinal_indice_invalido", f"{cam}.{nome}", f"{v!r}."))
    if not out and (s.indice_fronteira <= s.k_aplicacao or s.intervalos_cauda != s.indice_fim_planejamento
                    - s.indice_fronteira):
        out.append(erro("sinal_horizonte_incoerente", cam, "Fronteira <= k ou cauda ≠ fim − fronteira."))
    te, c1 = ler_instante_utc(s.instante_emissao_utc, cam + ".instante_emissao_utc")
    ta, c2 = ler_instante_utc(s.instante_aplicacao_utc, cam + ".instante_aplicacao_utc")
    tf, c3 = ler_instante_utc(s.instante_fronteira_utc, cam + ".instante_fronteira_utc")
    out += c1 + c2 + c3
    if te and ta and te > ta:
        out.append(erro("sinal_nao_causal", cam + ".instante_emissao_utc",
                        f"Emitido em {s.instante_emissao_utc}, depois da aplicação {s.instante_aplicacao_utc}."))
    if ta and tf and tf <= ta:
        out.append(erro("sinal_horizonte_incoerente", cam + ".instante_fronteira_utc", "Fronteira <= aplicação."))
    out += validar_termo_declarado(s.termo_longo, None, cam + ".termo_longo")
    if isinstance(s.termo_longo, TermoTerminal3C4) and s.termo_longo.tipo not in TERMOS_DECLARADOS:
        out.append(erro("termo_longo_invalido", cam + ".termo_longo.tipo", "Φ_L deve ser um termo DECLARADO."))
    dim = len(s.baterias)
    if len(set(s.baterias)) != dim or len(set(s.geradores)) != len(s.geradores):
        out.append(erro("uid_duplicado", cam, "Bancos/geradores repetidos."))
    for i, d in enumerate(s.diagnostico_modos):
        if not isinstance(d, DiagnosticoModo) or d.estado not in ESTADOS_MODO:
            out.append(erro("diagnostico_modo_invalido", f"{cam}.diagnostico_modos[{i}]", "Estado de modo inválido."))
    if s.qualidade.estado == "valido" and any(d.estado in ("dominio_indeterminado", "indisponivel")
                                              for d in s.diagnostico_modos if isinstance(d, DiagnosticoModo)):
        out.append(erro("sinal_valido_com_modo_nao_resolvido", cam + ".diagnostico_modos",
                        "Sinal válido não pode omitir um estado terminal de domínio indeterminado/indisponível."))
    if s.qualidade.estado != "valido":
        return out                               # sinal indisponível: só a estrutura é exigida
    if s.tipo in ("referencia_energia_dura", "referencia_energia_branda"):
        r = s.referencia
        if s.modos or r is None or len(r.energias_kWh) != dim or not all(_real(x) for x in r.energias_kWh):
            out.append(erro("sinal_referencia_invalida", cam + ".referencia", "Referência energética incompleta."))
        if s.tipo == "referencia_energia_branda" and not (_real(s.penalidade_branda_R_kWh)
                                                          and s.penalidade_branda_R_kWh > 0):
            out.append(erro("penalidade_branda_invalida", cam + ".penalidade_branda_R_kWh",
                            "ρ > 0 DECLARADO exigido (heurística rotulada)."))
        if dim == 0:
            out.append(erro("referencia_sem_banco", cam, "Referência energética sem banco."))
        return out
    if not s.modos:
        return out + [erro("sinal_sem_modos", cam + ".modos", "Sinal de valor sem nenhum modo terminal.")]
    if [m.indice for m in s.modos] != list(range(len(s.modos))):
        out.append(erro("sinal_modos_desordenados", cam + ".modos", "Índices de modo devem ser 0..n−1."))
    chaves = set()
    for m in s.modos:
        cm = f"{cam}.modos[{m.indice}]"
        if m.geradores:
            if tuple(x.uid for x in m.geradores) != tuple(s.geradores):
                out.append(erro("modo_geradores_divergentes", cm, "Geradores do modo ≠ geradores do sinal (ordem)."))
        elif s.geradores and s.intervalos_cauda > 0:
            out.append(erro("modo_sem_condicionamento", cm, "Modo não condicionado só com cauda vazia."))
        for x in m.geradores:
            if not _inteiro(x.obrigacao_residual_s) or x.obrigacao_residual_s < 0 or type(x.ligado) is not bool:
                out.append(erro("modo_memoria_invalida", f"{cm}[{x.uid}]", "Obrigação residual inteira >= 0."))
            if x.potencia_fixada_kW is not None and (not _real(x.potencia_fixada_kW) or not x.ligado):
                out.append(erro("modo_potencia_invalida", f"{cm}[{x.uid}]", "Potência fixada só ON e finita."))
        ch = tuple((x.uid, x.ligado, x.obrigacao_residual_s) for x in m.geradores)
        if ch in chaves:
            out.append(erro("modos_duplicados", cm, "Dois modos com o mesmo estado terminal."))
        chaves.add(ch)
        out += _validar_pontos(s, m, dim, cm)
    if s.tipo == "valor_marginal_local":
        if len(s.modos) != 1 or s.modos[0].representacao != "linear_local" or s.sensibilidade is None:
            out.append(erro("sinal_local_invalido", cam, "Sinal local exige um modo 'linear_local' e sensibilidade."))
        elif len(s.sensibilidade.lambdas_R_kWh) != dim or not all(_real(x) for x in s.sensibilidade.lambdas_R_kWh):
            out.append(erro("sinal_local_invalido", cam + ".sensibilidade", "λ incompleto/não finito."))
    return out


def _validar_pontos(s: SinalValorFuturo, m: ModoValor, dim: int, cm: str) -> list[Constatacao]:
    out = []
    if len(m.dominio_min_kWh) != dim or len(m.dominio_max_kWh) != dim or not all(
            _real(a) and _real(b) and a <= b + TOL_E for a, b in zip(m.dominio_min_kWh, m.dominio_max_kWh)):
        return [erro("modo_dominio_invalido", cm + ".dominio", "Domínio por banco incompleto/não finito/invertido.")]
    if not m.pontos:
        return [erro("modo_sem_pontos", cm + ".pontos", "Modo sem pontos.")]
    for i, p in enumerate(m.pontos):
        if len(p.energias_kWh) != dim or not all(_real(x) for x in p.energias_kWh) or not _real(p.valor_R) or (
                p.limite_inferior_R is not None and not _real(p.limite_inferior_R)):
            out.append(erro("ponto_valor_invalido", f"{cm}.pontos[{i}]", "Energias/valor não finitos ou dimensão errada."))
            return out
        if any(x < a - TOL_E or x > b + TOL_E for x, a, b in zip(p.energias_kWh, m.dominio_min_kWh, m.dominio_max_kWh)):
            out.append(erro("ponto_fora_do_dominio", f"{cm}.pontos[{i}]", "Ponto fora do domínio declarado."))
    rep = m.representacao
    esperado = {0: "constante_0d", 1: "intervalos_consecutivos_1d"}.get(dim, "envoltoria_convexa_nd")
    if s.tipo == "valor_marginal_local":
        esperado = "linear_local"
    if rep != esperado:
        out.append(erro("representacao_incompativel", cm + ".representacao", f"{rep!r}; esperada {esperado!r}."))
        return out
    if rep == "constante_0d" and len(m.pontos) != 1:
        out.append(erro("representacao_incompativel", cm, "0D exige exatamente um ponto por modo."))
    if rep == "intervalos_consecutivos_1d":
        es = [p.energias_kWh[0] for p in m.pontos]
        if any(b <= a for a, b in zip(es, es[1:])):
            out.append(erro("pontos_nao_crescentes", cm, "Energias 1D devem ser estritamente crescentes."))
        if abs(es[0] - m.dominio_min_kWh[0]) > TOL_E or abs(es[-1] - m.dominio_max_kWh[0]) > TOL_E:
            out.append(erro("dominio_nao_coberto", cm, "Primeiro/último ponto ≠ extremos do domínio."))
    if rep == "envoltoria_convexa_nd":
        if dim > 2:
            out.append(erro("dimensao_nao_suportada", cm, f"{dim} bancos: só 0D/1D/2D (declarado)."))
        if not m.convexidade_verificada_na_amostra:
            out.append(erro("convexidade_nao_verificada", cm, "Envoltória convexa só com convexidade VERIFICADA."))
    if rep == "linear_local" and len(m.pontos) != 1:
        out.append(erro("representacao_incompativel", cm, "Linear local exige o ponto de referência."))
    return out


def validar_sinal_para_entrada(s: SinalValorFuturo, e: EntradaRede3C3, cam: str = "terminal.sinal") -> list[Constatacao]:
    """Compatibilidade do sinal com a ENTRADA da janela: identidade, instantes de aplicação/fronteira (malha),
    recursos, domínios físicos, modos × memória herdada e política de permanência."""
    out = validar_sinal(s, cam)
    if any(c.severidade == "erro" for c in out):
        return out
    b = e.base
    if s.qualidade.estado != "valido":
        return out + [erro("sinal_valor_futuro_indisponivel", cam + ".qualidade",
                           f"Sinal indisponível: {s.qualidade.motivo}")]
    if (s.microrrede_uid, s.cenario_uid) != (b.microrrede_uid, b.cenario_uid):
        out.append(erro("sinal_de_outra_microrrede", cam, f"Sinal de {s.microrrede_uid!r}/{s.cenario_uid!r}."))
    m = b.malha
    t0 = m.inicio()
    tf = ler_instante_utc(s.instante_fronteira_utc, "f")[0]
    from datetime import timedelta
    if ler_instante_utc(s.instante_aplicacao_utc, "a")[0] != t0:
        out.append(erro("sinal_de_outra_janela", cam + ".instante_aplicacao_utc", "Aplicação ≠ início da janela."))
    if tf != t0 + timedelta(seconds=m.delta_s * m.N) or s.indice_fronteira - s.k_aplicacao != m.N:
        out.append(erro("sinal_de_outra_fronteira", cam + ".instante_fronteira_utc",
                        f"Fronteira {s.instante_fronteira_utc} ≠ fim da janela (N = {m.N})."))
    if tuple(sorted(s.baterias)) != tuple(sorted(str(x.uid) for x in b.baterias)) or tuple(s.baterias) != tuple(
            sorted(s.baterias)):
        out.append(erro("sinal_recursos_divergentes", cam + ".baterias", "Bancos do sinal ≠ bancos da entrada."))
    if tuple(s.geradores) != tuple(sorted(str(g.uid) for g in b.geradores)):
        out.append(erro("sinal_recursos_divergentes", cam + ".geradores", "Geradores do sinal ≠ geradores da entrada."))
    if out:
        return out
    lim = limites_energia(e)
    for m_ in s.modos:
        for i, u in enumerate(s.baterias):
            lo, hi = lim[u]
            if m_.dominio_min_kWh[i] < lo - TOL_E or m_.dominio_max_kWh[i] > hi + TOL_E:
                out.append(erro("dominio_fora_dos_limites_fisicos", f"{cam}.modos[{m_.indice}][{u}]",
                                f"Domínio [{m_.dominio_min_kWh[i]}, {m_.dominio_max_kWh[i]}] ⊄ [{lo}, {hi}]."))
    if s.referencia is not None and s.tipo.startswith("referencia_"):
        for i, u in enumerate(s.baterias):
            if s.referencia.energias_kWh[i] > lim[u][1] + TOL_E:
                out.append(erro("referencia_inalcancavel", f"{cam}.referencia[{u}]", "E_ref > C s_max."))
    if modo_condicionado(s) and s.intervalos_cauda > 0 and b.geradores:
        out += _validar_modos_memoria(s, e, cam)
    return out


def _validar_modos_memoria(s: SinalValorFuturo, e: EntradaRede3C3, cam: str) -> list[Constatacao]:
    out = []
    her = residuo_terminal_herdado(e)
    disc = discretizar(e.compromisso)
    pol = e.compromisso.politica_permanencia.tipo
    gesp = {str(g.uid): g for g in e.base.geradores}
    for m_ in s.modos:
        for x in m_.geradores:
            u0, r, res = her[x.uid]
            cm = f"{cam}.modos[{m_.indice}][{x.uid}]"
            if x.obrigacao_residual_s > 0:
                if x.obrigacao_residual_s != res or x.ligado != bool(u0):
                    out.append(erro("modo_memoria_incompativel", cm,
                                    f"Obrigação residual {x.obrigacao_residual_s} s/ligado {x.ligado} ≠ obrigação herdada "
                                    f"conhecida na fronteira ({res} s, u0 = {u0})."))
            else:
                if res > 0:
                    out.append(erro("modo_memoria_incompativel", cm,
                                    f"Modo sem obrigação, mas a obrigação herdada ({res} s) ultrapassa a janela."))
                d = disc[x.uid]
                if (d.U or 0) + (d.D or 0) > 0 and pol != "cumprir_na_janela":
                    out.append(erro("permanencia_incompativel_com_sinal", cm,
                                    f"Sinal condicionado a obrigação residual 0 exige 'cumprir_na_janela' (política "
                                    f"{pol!r}: a memória terminal não seria a do modo)."))
            if x.potencia_fixada_kW is not None:
                g = gesp[x.uid]
                if not float(g.p_min_kW.valor) - TOL_E <= x.potencia_fixada_kW <= float(g.p_max_kW.valor) + TOL_E:
                    out.append(erro("modo_potencia_invalida", cm, "Potência fixada fora de [P_min, P_max]."))
    return out


def validar_sinal_para_janela(s: SinalValorFuturo, *, missao_uid: str, indice_janela: int, k: int, instante_utc: str,
                              fronteira: int, hash_modelo_rede: str, hash_configuracao: str,
                              hash_instantaneo_emissao: str | None, cam: str = "sinal") -> list[Constatacao]:
    """Vínculo do sinal à JANELA de aplicação do MPC: missão, janela (um sinal NUNCA é reutilizado em outra janela —
    caducidade), k, τ_k, fronteira global, modelo de rede e configuração do planejador da missão, e CAUSALIDADE: emissão
    <= τ_k e hash do instantâneo informacional do sinal = hash do corte selado do livro K6 no instante de emissão."""
    out = []
    if not isinstance(s, SinalValorFuturo):
        return [erro("sinal_invalido", cam, type(s).__name__)]
    if s.missao_uid != missao_uid:
        out.append(erro("sinal_de_outra_missao", cam + ".missao_uid", f"{s.missao_uid!r}."))
    if s.indice_janela != indice_janela or s.k_aplicacao != k:
        out.append(erro("sinal_caducado", cam + ".indice_janela",
                        f"Sinal da janela {s.indice_janela} (k = {s.k_aplicacao}); decisão na janela {indice_janela} "
                        f"(k = {k}): reutilização em outra janela proibida."))
    ta, _ = ler_instante_utc(s.instante_aplicacao_utc, "a")
    tk, _ = ler_instante_utc(instante_utc, "k")
    if ta is None or tk is None or ta != tk:
        out.append(erro("sinal_caducado", cam + ".instante_aplicacao_utc", "Instante de aplicação ≠ τ_k."))
    if s.indice_fronteira != fronteira:
        out.append(erro("sinal_de_outra_fronteira", cam + ".indice_fronteira",
                        f"Fronteira {s.indice_fronteira} ≠ k + N_k = {fronteira}."))
    te, _ = ler_instante_utc(s.instante_emissao_utc, "e")
    if te is None or tk is None or te > tk:
        out.append(erro("sinal_nao_causal", cam + ".instante_emissao_utc", "Emissão posterior a τ_k."))
    hi = (s.hashes or {}).get("instantaneo")
    if hash_instantaneo_emissao is None or hi != hash_instantaneo_emissao:
        out.append(erro("sinal_nao_causal", cam + ".hashes.instantaneo",
                        "O instantâneo informacional do sinal ≠ corte selado do livro K6 no instante de emissão."))
    if (s.hashes or {}).get("modelo_rede") != hash_modelo_rede:
        out.append(erro("sinal_de_outro_modelo", cam + ".hashes.modelo_rede", "Modelo de rede ≠ o da missão."))
    if (s.hashes or {}).get("configuracao_planejador") != hash_configuracao:
        out.append(erro("sinal_de_outra_configuracao", cam + ".hashes.configuracao_planejador",
                        "Configuração do planejador ≠ a da missão."))
    return out


def validar_entrada_3c4(e: EntradaHierarquica3C4) -> RelatorioValidacao:
    if not isinstance(e, EntradaHierarquica3C4):
        return RelatorioValidacao((erro("entrada_3c4_invalida", "entrada",
                                        f"Esperada EntradaHierarquica3C4; recebido {type(e).__name__}."),))
    out: list[Constatacao] = []
    if e.versao_esquema_3c4 != ESQUEMA_3C4 or type(e.versao_esquema_3c4) is not int:
        out.append(erro("versao_esquema_3c4_incompativel", "versao_esquema_3c4", f"{e.versao_esquema_3c4!r}."))
    if e.versao_formulacao != FORMULACAO_3C4:
        out.append(erro("formulacao_nao_3c4", "versao_formulacao",
                        f"{e.versao_formulacao!r}: o embrulho hierárquico exige {FORMULACAO_3C4!r}."))
    out += validar_procedencia(e.procedencia, "procedencia")
    if not isinstance(e.rede, EntradaRede3C3):
        return RelatorioValidacao(tuple(out + [erro("rede_invalida", "rede", "Núcleo deve ser EntradaRede3C3.")]))
    rel = validar_entrada_3c3(e.rede)
    out += [Constatacao(c.codigo, "rede." + c.caminho, c.mensagem, c.severidade) for c in rel.constatacoes]
    if not rel.aceito:
        return RelatorioValidacao(tuple(out))
    t = e.terminal
    out += validar_termo_declarado(t, e.rede, "terminal")
    if isinstance(t, TermoTerminal3C4) and t.tipo == "sinal_valor_futuro" and t.sinal is not None:
        out += validar_sinal_para_entrada(t.sinal, e.rede)
    return RelatorioValidacao(tuple(out))


# =============================================================================== configuração do planejador
def validar_configuracao_planejador(c: ConfiguracaoPlanejador3C4, cfg_mpc=None, modelo: EntradaRede3C3 | None = None
                                    ) -> list[Constatacao]:
    if not isinstance(c, ConfiguracaoPlanejador3C4):
        return [erro("configuracao_planejador_invalida", "planejador", type(c).__name__)]
    out: list[Constatacao] = []
    cam = "planejador"
    if type(c.esquema) is not int or c.esquema != ESQUEMA_3C4:
        out.append(erro("versao_esquema_3c4_incompativel", cam + ".esquema", f"{c.esquema!r}."))
    if c.perfil != FORMULACAO_3C4:
        out.append(erro("formulacao_nao_3c4", cam + ".perfil", f"{c.perfil!r}."))
    out += validar_procedencia(c.procedencia, cam + ".procedencia")
    if not isinstance(c.justificativa, str) or not c.justificativa.strip():
        out.append(erro("planejador_sem_justificativa", cam + ".justificativa", "Exigida."))
    for nome, vmin in (("horizonte_longo_intervalos", 2), ("periodo_janelas", 1), ("pontos_iniciais", 2),
                       ("pontos_max", 2), ("max_modos", 1)):
        v = getattr(c, nome)
        if not _inteiro(v) or v < vmin:
            out.append(erro("planejador_parametro_invalido", f"{cam}.{nome}", f"{v!r}: inteiro >= {vmin} (sem padrão)."))
    if _inteiro(c.pontos_max) and _inteiro(c.pontos_iniciais) and c.pontos_max < c.pontos_iniciais:
        out.append(erro("planejador_parametro_invalido", cam + ".pontos_max", "pontos_max < pontos_iniciais."))
    for nome, positivo in (("tolerancia_interpolacao_R", False), ("tolerancia_dominio_kWh", True)):
        v = getattr(c, nome)
        if not _real(v) or v < 0 or (positivo and v == 0):
            out.append(erro("planejador_parametro_invalido", f"{cam}.{nome}", f"{v!r}."))
    if c.cobertura_fim_missao not in COBERTURAS_FIM_MISSAO:
        out.append(erro("cobertura_fim_missao_invalida", cam + ".cobertura_fim_missao", f"{c.cobertura_fim_missao!r}."))
    if c.permanencia_fim_planejamento not in POLITICAS_PERMANENCIA:
        out.append(erro("permanencia_invalida", cam + ".permanencia_fim_planejamento",
                        f"{c.permanencia_fim_planejamento!r}."))
    if c.politica_atualizacao not in POLITICAS_ATUALIZACAO:
        out.append(erro("politica_atualizacao_invalida", cam + ".politica_atualizacao", f"{c.politica_atualizacao!r}."))
    elif c.politica_atualizacao == "a_cada_janela" and c.periodo_janelas != 1:
        out.append(erro("planejador_parametro_invalido", cam + ".periodo_janelas", "'a_cada_janela' ⇒ P = 1."))
    if c.tipo_sinal not in TIPOS_SINAL:
        out.append(erro("tipo_sinal_invalido", cam + ".tipo_sinal", f"{c.tipo_sinal!r}."))
    if c.degradacao not in DEGRADACOES:
        out.append(erro("degradacao_invalida", cam + ".degradacao", f"{c.degradacao!r} (sem padrão)."))
    if c.tipo_sinal == "valor_marginal_local" and not (_real(c.delta_sensibilidade_kWh) and c.delta_sensibilidade_kWh > 0):
        out.append(erro("delta_sensibilidade_invalido", cam + ".delta_sensibilidade_kWh", "δ > 0 declarado."))
    if c.tipo_sinal != "valor_marginal_local" and c.delta_sensibilidade_kWh is not None:
        out.append(erro("planejador_parametro_ambiguo", cam + ".delta_sensibilidade_kWh", "Só no sinal local."))
    if c.tipo_sinal == "referencia_energia_branda" and not (_real(c.penalidade_branda_R_kWh)
                                                             and c.penalidade_branda_R_kWh > 0):
        out.append(erro("penalidade_branda_invalida", cam + ".penalidade_branda_R_kWh", "ρ > 0 declarado."))
    if c.tipo_sinal != "referencia_energia_branda" and c.penalidade_branda_R_kWh is not None:
        out.append(erro("planejador_parametro_ambiguo", cam + ".penalidade_branda_R_kWh", "Só na referência branda."))
    out += validar_termo_declarado(c.termo_longo, modelo, cam + ".termo_longo")
    if isinstance(c.termo_longo, TermoTerminal3C4) and c.termo_longo.tipo not in TERMOS_DECLARADOS:
        out.append(erro("termo_longo_invalido", cam + ".termo_longo.tipo", "Φ_L deve ser um termo DECLARADO."))
    if cfg_mpc is not None and _inteiro(c.horizonte_longo_intervalos):
        m = cfg_mpc.malha
        if c.horizonte_longo_intervalos <= m.intervalos_otimizacao:
            out.append(erro("horizonte_longo_nao_maior", cam + ".horizonte_longo_intervalos",
                            f"H_L = {c.horizonte_longo_intervalos} <= N = {m.intervalos_otimizacao}: exigido H_L > H_S."))
        hf = m.horizonte_previsao_min
        if hf is None or hf < c.horizonte_longo_intervalos * float(m.delta_min) - 1e-9:
            out.append(erro("horizonte_longo_alem_da_previsao", cam + ".horizonte_longo_intervalos",
                            f"H_L Δ = {c.horizonte_longo_intervalos * float(m.delta_min)} min > H_f = {hf} min "
                            "(nenhuma extrapolação oculta)."))
        if modelo is not None and modelo.base.geradores and c.tipo_sinal in ("custo_futuro_pwl",
                                                                              "valor_marginal_local"):
            pi = cfg_mpc.politica_terminal.permanencia_janelas_intermediarias
            if pi != "cumprir_na_janela":
                out.append(erro("permanencia_incompativel_com_sinal", "mpc.politica_terminal",
                                f"Sinal condicionado à memória terminal exige 'cumprir_na_janela' nas janelas "
                                f"intermediárias (declarado {pi!r})."))
    if modelo is not None and len(modelo.base.baterias) > 2 and c.tipo_sinal == "custo_futuro_pwl":
        out.append(erro("dimensao_nao_suportada", cam + ".tipo_sinal", "PWL só com até 2 bancos (declarado)."))
    return out


__all__ = ["COBERTURAS_FIM_MISSAO", "CONVENCAO_SINAIS", "DiagnosticoModo", "ESTADOS_MODO", "ConfiguracaoPlanejador3C4", "DEGRADACOES",
           "EntradaHierarquica3C4", "EstadoTerminalGerador", "ESTADOS_SINAL", "ModoValor", "ParametroBateria",
           "POLITICAS_ATUALIZACAO", "PontoValidacao", "PontoValor", "QualidadeSinal", "REPRESENTACOES",
           "ReferenciaTerminal", "SensibilidadeLocal", "SinalValorFuturo", "TERMOS_DECLARADOS", "TIPOS_SINAL",
           "TIPOS_TERMO_TERMINAL", "TermoTerminal3C4", "entrada_3c4_de_json", "hash_configuracao_planejador",
           "hash_entrada_3c4", "hash_sinal", "hash_termo", "json_canonico_3c4", "limites_energia", "modo_condicionado",
           "residuo_terminal_herdado", "selar_sinal", "sinal_selado", "validar_configuracao_planejador", "validar_sinal_para_janela",
           "validar_entrada_3c4", "validar_sinal", "validar_sinal_para_entrada", "validar_termo_declarado"]
