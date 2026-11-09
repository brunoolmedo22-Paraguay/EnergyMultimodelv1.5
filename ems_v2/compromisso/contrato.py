"""Contrato do perfil ``v1.1-3C-1`` — commitment dinâmico POR UNIDADE (M09–M12) — só biblioteca padrão.

Extensão CONTROLADA e versionada, sem tocar o contrato 3A/3B-P (``ems_v2/contracts.py`` inalterado): a entrada 3C-1
é um EMBRULHO que contém uma ``EntradaModeloEMS`` declarada ``v1.1-3B-P`` (núcleo contínuo e econômico: M02–M08,
M10, M14–M16 e os termos do objetivo do 3B-P) e acrescenta, POR UNIDADE GERADORA, os dados que o commitment
dinâmico exige. Consequências verificáveis:

* toda entrada 3A/3B-P conserva exatamente o mesmo JSON canônico e o mesmo SHA-256 (o esquema v1 não foi tocado);
* uma ``EntradaModeloEMS`` não pode declarar ``v1.1-3C-1`` (``FORMULACOES`` inalterado ⇒ ``formulacao_incompativel``):
  nenhum contrato anterior ganha capacidades implicitamente;
* a entrada 3C-1 tem JSON canônico e SHA-256 PRÓPRIOS (``hash_entrada_3c1``), que incluem o texto canônico da base.

Regras científicas (sem valor padrão; ausência ⇒ constatação bloqueante, NUNCA "sem restrição"):

* rampas R⁺, R⁻ [kW/min] obrigatórias para toda unidade que possa estar ON na janela (ausente ≠ ilimitada);
* tempos mínimos T_on, T_off [min] obrigatórios quando a unidade pode transitar (T = 0 só se DECLARADO);
* limites de transição: ``declarados`` (S⁺, S⁻ [kW] com procedência) ou ``rampa_convencional`` (interpretação
  conservadora S⁺ := R⁺Δ, S⁻ := R⁻Δ — nenhum salto maior que a rampa, nem a partir de/para zero);
* abstração da transição: ``instantanea_unidade_quente`` (B05 variante INSTANTÂNEA; para PEMFC é ABSTRAÇÃO
  matemática declarada, não validação física) ou ``transicoes_bloqueadas`` (estado mantido na janela);
* memória por unidade: tempo no estado vigente e obrigação residual (s), com procedência — nunca inferidos da potência;
* termo ``eventos`` (C_SU y + C_SD z, R$/evento, sem h) só quando declarado, com TODOS os coeficientes; coeficiente
  declarado sem o termo é erro; PEMFC com transições e termo ``combustivel_h2`` exige massas de evento m^SU/m^SD (B05).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from fractions import Fraction

from .. import FORMULACAO_3BP, FORMULACAO_3C1
from ..contracts import (EntradaModeloEMS, ErroSerializacao, UIDRecurso, _constante_proibida, de_dict, para_dict,
                         validar_entrada, validar_uid)
from ..diagnostics import Constatacao, RelatorioValidacao, aviso, erro, pendente
from ..parameters import Parametro, validar_parametro
from ..provenance import Procedencia, validar_procedencia
from ..series import alinhar_a_malha
from ..units import exato

ESQUEMA_3C1 = 1
ABSTRACOES_TRANSICAO = {
    "instantanea_unidade_quente": "OFF↔ON dentro de UM intervalo (unidade quente; adenda B05, variante INSTANTÂNEA). "
                                  "Abstração matemática declarada — para PEMFC NÃO é validação física da partida",
    "transicoes_bloqueadas": "Nenhuma transição é representável nesta janela: u_t = u^{-1} para todo t "
                             "(estado mantido; sem física de partida/parada)",
}
LIMITES_TRANSICAO = {
    "declarados": "S⁺ (potência máxima no 1º intervalo ON após a partida) e S⁻ (potência máxima no último intervalo ON "
                  "antes da parada) declarados [kW], com procedência",
    "rampa_convencional": "Só a rampa convencional é conhecida: S⁺ := R⁺·Δ e S⁻ := R⁻·Δ (interpretação CONSERVADORA: "
                          "nenhum salto de potência maior que a rampa, inclusive a partir de/para zero)",
}
POLITICAS_PERMANENCIA = {
    "cumprir_na_janela": "Nenhuma partida/parada cuja permanência mínima não termine DENTRO da janela (y_t = 0 se "
                         "t + U > N; z_t = 0 se t + D > N). Garantia completa na janela para transições novas; "
                         "obrigações herdadas além da janela são transportadas",
    "obrigacao_residual_vinculante": "Transições perto do fim são permitidas; a parte da permanência que excede a "
                                     "janela é exportada como OBRIGAÇÃO RESIDUAL VINCULANTE da janela seguinte "
                                     "(não é garantia de cumprimento: depende da continuação)",
}
TERMOS_3C1 = {"eventos": "J_ev = Σ_i Σ_t (C_SU·y + C_SD·z) [R$/evento; NÃO multiplicado por h]"}
_RE_UID_UNIDADE = re.compile(r"^.+$")


# =============================================================================== dataclasses
@dataclass(frozen=True)
class EspecCommitmentUnidade:
    """Dados de commitment de UMA unidade geradora (``uid`` = UID de um gerador da base, p. ex. ``eq-…#2``)."""
    uid: UIDRecurso
    abstracao_transicao: str                      # ABSTRACOES_TRANSICAO (sem padrão)
    limites_transicao: str                        # LIMITES_TRANSICAO (sem padrão)
    rampa_subida_kW_min: Parametro | None         # R⁺ [kW/min] — ausente ⇒ erro (nunca ilimitada)
    rampa_descida_kW_min: Parametro | None        # R⁻ [kW/min]
    tempo_min_ligado_min: Parametro | None        # T_on [min]
    tempo_min_desligado_min: Parametro | None     # T_off [min]
    potencia_partida_max_kW: Parametro | None = None   # S⁺ — só com limites "declarados"
    potencia_parada_max_kW: Parametro | None = None    # S⁻ — só com limites "declarados"
    custo_partida: Parametro | None = None             # C_SU [R$/evento] — só com o termo "eventos"
    custo_parada: Parametro | None = None              # C_SD [R$/evento]
    massa_h2_partida_kg: Parametro | None = None       # m^SU [kg/evento] — PEMFC com transições e "combustivel_h2"
    massa_h2_parada_kg: Parametro | None = None        # m^SD [kg/evento]
    justificativa_abstracao: str = ""


@dataclass(frozen=True)
class MemoriaCommitmentUnidade:
    """Memória operativa na fronteira inicial da janela (k = 0), referida ao estado ``u^{-1}`` da base.

    ``tempo_no_estado_s``: tempo transcorrido no estado vigente (ON ou OFF) até τ_0; ``obrigacao_residual_s``: tempo
    durante o qual a unidade AINDA deve permanecer nesse estado a partir de τ_0. ``None`` = não declarado (bloqueia
    quando a informação é necessária). A obrigação deve coincidir com a derivada ⌈max(0, T_estado − tempo)⌉ (s)."""
    uid: UIDRecurso
    tempo_no_estado_s: int | None
    obrigacao_residual_s: int | None
    procedencia: Procedencia | None


@dataclass(frozen=True)
class PoliticaPermanenciaTerminal:
    tipo: str                                     # POLITICAS_PERMANENCIA (sem padrão)
    justificativa: str
    procedencia: Procedencia | None


@dataclass(frozen=True)
class EntradaCommitment3C1:
    versao_esquema_3c1: int
    versao_formulacao: str                        # == FORMULACAO_3C1
    base: EntradaModeloEMS                        # declarada FORMULACAO_3BP (núcleo contínuo/econômico)
    unidades: tuple[EspecCommitmentUnidade, ...]
    memorias: tuple[MemoriaCommitmentUnidade, ...]
    politica_permanencia: PoliticaPermanenciaTerminal
    termos_adicionais: tuple[str, ...]            # ⊆ TERMOS_3C1 (somados aos termos da base)
    procedencia: Procedencia | None

    def unidade(self, uid: str) -> EspecCommitmentUnidade | None:
        return next((u for u in self.unidades if str(u.uid) == uid), None)

    def memoria(self, uid: str) -> MemoriaCommitmentUnidade | None:
        return next((m for m in self.memorias if str(m.uid) == uid), None)

    @property
    def termos(self) -> tuple[str, ...]:
        """Termos do objetivo do perfil 3C-1 = termos da base (3B-P) + termos adicionais."""
        return tuple(self.base.politica_objetivo.termos) + tuple(self.termos_adicionais)


# =============================================================================== discretização (exata)
@dataclass(frozen=True)
class DiscretizacaoUnidade:
    """Parâmetros da unidade convertidos para a malha (Δ exato). Valores em kW/intervalos; textos exatos em ``exato``."""
    uid: str
    tecnologia: str
    abstracao: str
    u_anterior: int
    p_anterior_kW: float
    p_on_min_kW: float                            # mínimo efetivo ON: max(P_min, P_0 da curva)
    p_on_max_kW: float                            # máximo efetivo ON: min(P_max, P_último da curva)
    rampa_subida_kW: float | None                 # R⁺·Δ [kW por intervalo]
    rampa_descida_kW: float | None                # R⁻·Δ
    limite_partida_kW: float | None               # S⁺ efetivo
    limite_parada_kW: float | None                # S⁻ efetivo
    origem_limites: str                           # "declarados" | "derivado_rampa_convencional" | "nao_aplicavel"
    partida_representavel: bool
    parada_representavel: bool
    U: int | None                                 # ⌈T_on/Δ⌉
    D: int | None                                 # ⌈T_off/Δ⌉
    arredondamento: str                           # "exato" | "para_cima_conservador" | "nao_aplicavel"
    obrigacao_inicial_intervalos: int             # r = ⌈obrigação/Δ⌉ (0 se não há obrigação)
    intervalos_forcados: int                      # min(r, N): u_t = u^{-1} para t < este valor
    obrigacao_alem_da_janela_s: int               # max(0, obrigação − NΔ) (transportada, nunca truncada)
    exato: dict[str, str]                         # frações exatas usadas (auditoria da conversão)


def _f(p: Parametro | None) -> float | None:
    return None if p is None or p.valor is None else float(p.valor)


def _ceil_frac(x: Fraction) -> int:
    return -((-x.numerator) // x.denominator)


def tempo_s_exato(p: Parametro | None) -> Fraction | None:
    """T [min] → s, exato (Fraction da representação decimal × 60)."""
    if p is None or p.valor is None:
        return None
    return exato(p.valor) * 60


def obrigacao_derivada_s(T_s: Fraction | None, tempo_no_estado_s: int | None) -> int | None:
    """⌈max(0, T_estado − tempo_no_estado)⌉ em segundos (arredondamento conservador para cima)."""
    if T_s is None or tempo_no_estado_s is None:
        return None
    resto = T_s - tempo_no_estado_s
    return 0 if resto <= 0 else _ceil_frac(resto)


def _domino_on(g) -> tuple[float, float]:
    pmin, pmax = float(g.p_min_kW.valor), float(g.p_max_kW.valor)
    if g.curva_h2 is not None:
        Ps = [float(v[0]) for v in g.curva_h2.vertices]
        return max(pmin, Ps[0]), min(pmax, Ps[-1])
    return pmin, pmax


def precisa_transitar(spec: EspecCommitmentUnidade) -> bool:
    return spec.abstracao_transicao == "instantanea_unidade_quente"


def discretizar(e: EntradaCommitment3C1) -> dict[str, DiscretizacaoUnidade]:
    """Supõe entrada VALIDADA (``validar_entrada_3c1`` sem bloqueios)."""
    m = e.base.malha
    d_min, d_s, N = exato(m.delta_min), m.delta_s, m.N
    est = {str(s.uid): s for s in e.base.estados_geradores}
    out: dict[str, DiscretizacaoUnidade] = {}
    for g in e.base.geradores:
        k = str(g.uid)
        sp, mem = e.unidade(k), e.memoria(k)
        st = est[k]
        u0, p0 = int(bool(st.ligado)), float(st.p_anterior_kW.valor)
        lo, hi = _domino_on(g)
        ex: dict[str, str] = {"delta_min": str(d_min), "delta_s": str(d_s)}
        rs = rd = None
        if sp.rampa_subida_kW_min is not None and sp.rampa_subida_kW_min.valor is not None:
            x = exato(sp.rampa_subida_kW_min.valor) * d_min
            rs, ex["R_sub_x_delta_kW"] = float(x), str(x)
        if sp.rampa_descida_kW_min is not None and sp.rampa_descida_kW_min.valor is not None:
            x = exato(sp.rampa_descida_kW_min.valor) * d_min
            rd, ex["R_desc_x_delta_kW"] = float(x), str(x)
        transita = precisa_transitar(sp)
        if not transita:
            spt, spd, orig = None, None, "nao_aplicavel"
        elif sp.limites_transicao == "declarados":
            spt, spd, orig = _f(sp.potencia_partida_max_kW), _f(sp.potencia_parada_max_kW), "declarados"
        else:
            spt, spd, orig = rs, rd, "derivado_rampa_convencional"
        rep_p = transita and spt is not None and spt >= lo
        rep_z = transita and spd is not None and spd >= lo
        U = D = None
        arr = "nao_aplicavel"
        Ton, Toff = tempo_s_exato(sp.tempo_min_ligado_min), tempo_s_exato(sp.tempo_min_desligado_min)
        if transita and Ton is not None and Toff is not None:
            U, D = _ceil_frac(Ton / d_s), _ceil_frac(Toff / d_s)
            arr = "exato" if (Ton / d_s).denominator == 1 and (Toff / d_s).denominator == 1 else "para_cima_conservador"
            ex["T_on_s"], ex["T_off_s"] = str(Ton), str(Toff)
        obr = mem.obrigacao_residual_s if (transita and mem is not None and mem.obrigacao_residual_s is not None) else 0
        r = _ceil_frac(Fraction(obr, d_s)) if obr > 0 else 0
        out[k] = DiscretizacaoUnidade(
            k, g.tecnologia, sp.abstracao_transicao, u0, p0, lo, hi, rs, rd, spt, spd, orig, rep_p, rep_z, U, D, arr,
            r, min(r, N), max(0, obr - N * d_s), ex)
    return out


def disponibilidade(g, malha) -> list[float]:
    return list(alinhar_a_malha(g.disponibilidade.serie, malha, "")[0])


# =============================================================================== validação
def _validar_unidade(sp: EspecCommitmentUnidade, g, st, e: EntradaCommitment3C1, cam: str) -> list[Constatacao]:
    out: list[Constatacao] = list(validar_uid(sp.uid, cam + ".uid"))
    termos = set(e.termos)
    transita = sp.abstracao_transicao == "instantanea_unidade_quente"
    if sp.abstracao_transicao not in ABSTRACOES_TRANSICAO:
        out.append(erro("abstracao_transicao_invalida", cam + ".abstracao_transicao",
                        f"{sp.abstracao_transicao!r}: declarar uma de {sorted(ABSTRACOES_TRANSICAO)} (sem padrão)."))
        return out
    if not sp.justificativa_abstracao.strip():
        out.append(erro("abstracao_sem_justificativa", cam + ".justificativa_abstracao",
                        "A abstração de transição é decisão de modelagem: exige justificativa explícita."))
    if transita and g.tecnologia == "pemfc":
        out.append(aviso("pemfc_abstracao_instantanea", cam + ".abstracao_transicao",
                         "PEMFC com transição INSTANTÂNEA: abstração matemática para casos analíticos compatíveis com a "
                         "hipótese de unidade quente — NÃO é validação física da partida (multimodo M20 não habilitado)."))
    if g.variante_commitment != "instantanea":
        out.append(pendente("variante_commitment_nao_suportada_3C1", cam,
                            f"Variante {g.variante_commitment!r}: o 3C-1 só implementa a variante instantânea "
                            "(multimodo/M20 exige implementação e validação próprias)."))
    pode_ligar = bool(st.ligado) or transita
    for nome in ("rampa_subida_kW_min", "rampa_descida_kW_min"):
        p = getattr(sp, nome)
        if pode_ligar or p is not None:
            out += validar_parametro(p, f"{cam}.{nome}", unidade="kW/min", dominio="nao_negativo")
    for nome in ("tempo_min_ligado_min", "tempo_min_desligado_min"):
        p = getattr(sp, nome)
        if transita or p is not None:
            out += validar_parametro(p, f"{cam}.{nome}", unidade="min", dominio="nao_negativo")
    if sp.limites_transicao not in LIMITES_TRANSICAO:
        out.append(erro("limites_transicao_invalidos", cam + ".limites_transicao",
                        f"{sp.limites_transicao!r}: declarar uma de {sorted(LIMITES_TRANSICAO)} (sem padrão)."))
    elif sp.limites_transicao == "declarados":
        if transita:
            for nome in ("potencia_partida_max_kW", "potencia_parada_max_kW"):
                out += validar_parametro(getattr(sp, nome), f"{cam}.{nome}", unidade="kW", dominio="positivo")
    else:
        for nome in ("potencia_partida_max_kW", "potencia_parada_max_kW"):
            if getattr(sp, nome) is not None:
                out.append(erro("limite_transicao_contraditorio", f"{cam}.{nome}",
                                "S declarado com limites 'rampa_convencional' (S := R·Δ por definição)."))
    # custos de evento
    if "eventos" in termos:
        if transita:
            for nome in ("custo_partida", "custo_parada"):
                out += validar_parametro(getattr(sp, nome), f"{cam}.{nome}", unidade="R$/evento", dominio="nao_negativo")
        else:
            for nome in ("custo_partida", "custo_parada"):
                if getattr(sp, nome) is not None:
                    out += validar_parametro(getattr(sp, nome), f"{cam}.{nome}", unidade="R$/evento",
                                             dominio="nao_negativo")
    else:
        for nome in ("custo_partida", "custo_parada"):
            if getattr(sp, nome) is not None:
                out.append(erro("coeficiente_sem_termo", f"{cam}.{nome}",
                                "Custo de evento declarado sem o termo 'eventos' no objetivo (nenhum custo implícito)."))
    # massas de H2 por evento (B05 instantânea): exigidas só se PEMFC transita E o combustível está no objetivo
    exige_m = transita and g.tecnologia == "pemfc" and "combustivel_h2" in termos
    for nome in ("massa_h2_partida_kg", "massa_h2_parada_kg"):
        p = getattr(sp, nome)
        if exige_m:
            out += validar_parametro(p, f"{cam}.{nome}", unidade="kg", dominio="nao_negativo")
        elif p is not None:
            out.append(erro("coeficiente_sem_termo", f"{cam}.{nome}",
                            "m^SU/m^SD só se aplicam a PEMFC com transições e termo 'combustivel_h2'."))
    return out


def _validar_memoria(mem: MemoriaCommitmentUnidade | None, sp: EspecCommitmentUnidade, st, cam: str) -> list[Constatacao]:
    if sp.abstracao_transicao != "instantanea_unidade_quente":
        return []                                   # sem transições na janela: a memória não intervém
    T = tempo_s_exato(sp.tempo_min_ligado_min if st.ligado else sp.tempo_min_desligado_min)
    if T is None:
        return []                                   # já constatado (tempo mínimo ausente)
    necessaria = T > 0
    if mem is None:
        return [erro("memoria_ausente", cam, "Memória operativa da unidade não declarada (tempo no estado e "
                                             "obrigação residual): não é inferida da potência.")] if necessaria else []
    out: list[Constatacao] = []
    for nome in ("tempo_no_estado_s", "obrigacao_residual_s"):
        v = getattr(mem, nome)
        if v is None:
            if necessaria:
                out.append(erro("memoria_ausente", f"{cam}.{nome}", f"{nome} não declarado (permanência mínima "
                                                                    f"{T} s > 0 no estado vigente)."))
        elif isinstance(v, bool) or not isinstance(v, int) or v < 0:
            out.append(erro("memoria_invalida", f"{cam}.{nome}", f"Exigido inteiro >= 0 [s]; recebido {v!r}."))
    out += validar_procedencia(mem.procedencia, cam + ".procedencia")
    if out:
        return out
    if mem.tempo_no_estado_s is not None and mem.obrigacao_residual_s is not None:
        der = obrigacao_derivada_s(T, mem.tempo_no_estado_s)
        if der != mem.obrigacao_residual_s:
            out.append(erro("obrigacao_residual_inconsistente", cam + ".obrigacao_residual_s",
                            f"Obrigação declarada {mem.obrigacao_residual_s} s ≠ derivada ⌈max(0, T − tempo)⌉ = {der} s "
                            f"(T = {T} s, tempo no estado = {mem.tempo_no_estado_s} s): memória incoerente."))
    return out


def validar_entrada_3c1(e: EntradaCommitment3C1) -> RelatorioValidacao:
    out: list[Constatacao] = []
    if not isinstance(e, EntradaCommitment3C1):
        return RelatorioValidacao((erro("entrada_3c1_invalida", "entrada", f"Esperada EntradaCommitment3C1; recebido "
                                                                           f"{type(e).__name__}."),))
    if e.versao_esquema_3c1 != ESQUEMA_3C1:
        out.append(erro("versao_esquema_3c1_incompativel", "versao_esquema_3c1", f"{e.versao_esquema_3c1!r}."))
    if e.versao_formulacao != FORMULACAO_3C1:
        out.append(erro("formulacao_nao_3c1", "versao_formulacao",
                        f"{e.versao_formulacao!r}: o contrato embrulho exige {FORMULACAO_3C1!r}."))
    out += validar_procedencia(e.procedencia, "procedencia")
    if not isinstance(e.base, EntradaModeloEMS):
        return RelatorioValidacao(tuple(out + [erro("base_invalida", "base", "Base deve ser EntradaModeloEMS.")]))
    if e.base.versao_formulacao != FORMULACAO_3BP:
        out.append(erro("base_nao_3bp", "base.versao_formulacao",
                        f"O núcleo contínuo/econômico do 3C-1 é o perfil {FORMULACAO_3BP!r}; recebido "
                        f"{e.base.versao_formulacao!r}."))
    rel = validar_entrada(e.base)
    out += [Constatacao(c.codigo, "base." + c.caminho, c.mensagem, c.severidade) for c in rel.constatacoes]
    if not rel.aceito:
        return RelatorioValidacao(tuple(out))
    # termos adicionais
    vistos: set[str] = set()
    for t in e.termos_adicionais:
        if t not in TERMOS_3C1:
            out.append(erro("termo_3c1_desconhecido", f"termos_adicionais[{t}]",
                            f"{t!r}: termos adicionais do 3C-1 = {sorted(TERMOS_3C1)}."))
        if t in vistos or t in e.base.politica_objetivo.termos:
            out.append(erro("termo_objetivo_duplicado", f"termos_adicionais[{t}]", "Termo repetido."))
        vistos.add(t)
    # política terminal de permanência
    pp = e.politica_permanencia
    if pp.tipo not in POLITICAS_PERMANENCIA:
        out.append(erro("politica_permanencia_invalida", "politica_permanencia.tipo",
                        f"{pp.tipo!r}: declarar uma de {sorted(POLITICAS_PERMANENCIA)} (sem padrão)."))
    if not pp.justificativa.strip():
        out.append(erro("politica_permanencia_sem_justificativa", "politica_permanencia.justificativa",
                        "A política terminal de permanência exige justificativa explícita."))
    out += validar_procedencia(pp.procedencia, "politica_permanencia.procedencia")
    # unidades × geradores da base (por UID; nenhuma agregação)
    ger = {str(g.uid): g for g in e.base.geradores}
    est = {str(s.uid): s for s in e.base.estados_geradores}
    for nome, itens in (("unidades", e.unidades), ("memorias", e.memorias)):
        cont: dict[str, int] = {}
        for x in itens:
            cont[str(x.uid)] = cont.get(str(x.uid), 0) + 1
        for k, n in sorted(cont.items()):
            if k not in ger:
                out.append(erro("commitment_uid_desconhecido", f"{nome}[{k}]", "UID não é gerador da base."))
            if n > 1:
                out.append(erro("commitment_uid_duplicado", f"{nome}[{k}]", "UID repetido."))
    for k, g in ger.items():
        sp = e.unidade(k)
        cam = f"unidades[{k}]"
        if sp is None:
            out.append(erro("commitment_unidade_ausente", cam,
                            "Gerador sem dados de commitment por unidade (rampas, permanências, abstração)."))
            continue
        out += _validar_unidade(sp, g, est[k], e, cam)
        out += _validar_memoria(e.memoria(k), sp, est[k], f"memorias[{k}]")
    if any(c.severidade in ("erro", "pendente") for c in out):
        return RelatorioValidacao(tuple(out))
    # coerências que dependem da discretização (só sobre dados válidos)
    disc = discretizar(e)
    N = e.base.malha.N
    for k, dz in disc.items():
        sp = e.unidade(k)
        if sp.abstracao_transicao != "instantanea_unidade_quente":
            continue
        cam = f"unidades[{k}]"
        if not dz.partida_representavel:
            out.append(aviso("partida_nao_representavel_bloqueada", cam,
                             f"S⁺ = {dz.limite_partida_kW} kW < potência mínima ON {dz.p_on_min_kW} kW: a partida exige "
                             "mais de um intervalo (multietapa/M20). Partidas BLOQUEADAS nesta janela (y ≡ 0)."))
        if not dz.parada_representavel:
            out.append(aviso("parada_nao_representavel_bloqueada", cam,
                             f"S⁻ = {dz.limite_parada_kW} kW < potência mínima ON {dz.p_on_min_kW} kW: a parada exige "
                             "mais de um intervalo. Paradas BLOQUEADAS nesta janela (z ≡ 0)."))
        if sp.limites_transicao == "declarados" and dz.limite_partida_kW is not None and dz.limite_partida_kW > float(
                e.base.geradores[[str(g.uid) for g in e.base.geradores].index(k)].p_max_kW.valor):
            out.append(aviso("limite_partida_acima_de_pmax", cam, "S⁺ > P_max: M10 limita a potência a P_max."))
        if dz.arredondamento == "para_cima_conservador":
            out.append(aviso("permanencia_arredondada_para_cima", cam,
                             f"T não é múltiplo de Δ: U = {dz.U}, D = {dz.D} intervalos (⌈T/Δ⌉, conservador)."))
        if (dz.U or 0) > N or (dz.D or 0) > N:
            out.append(aviso("permanencia_maior_que_janela", cam,
                             f"U = {dz.U} ou D = {dz.D} > N = {N}: a janela não alcança a permanência (miopia)."))
        if dz.obrigacao_alem_da_janela_s > 0:
            out.append(aviso("obrigacao_herdada_alem_da_janela", cam,
                             f"Obrigação herdada excede a janela em {dz.obrigacao_alem_da_janela_s} s: transportada."))
    return RelatorioValidacao(tuple(out))


# =============================================================================== serialização canônica
def json_canonico_3c1(e: EntradaCommitment3C1) -> str:
    """Mesma regra canônica do 3A (``contracts.para_dict``): a base embutida tem EXATAMENTE o dicionário canônico 3B-P."""
    return json.dumps(para_dict(e), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def hash_entrada_3c1(e: EntradaCommitment3C1) -> str:
    return hashlib.sha256(json_canonico_3c1(e).encode("utf-8")).hexdigest()


def entrada_3c1_de_json(texto: str) -> EntradaCommitment3C1:
    try:
        dado = json.loads(texto, parse_constant=_constante_proibida)
    except json.JSONDecodeError as exc:
        raise ErroSerializacao(f"JSON inválido: {exc}") from None
    return de_dict(EntradaCommitment3C1, dado, "EntradaCommitment3C1")


def _finito(x) -> bool:
    return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x)


__all__ = ["ABSTRACOES_TRANSICAO", "DiscretizacaoUnidade", "ESQUEMA_3C1", "EntradaCommitment3C1",
           "EspecCommitmentUnidade", "LIMITES_TRANSICAO", "MemoriaCommitmentUnidade", "POLITICAS_PERMANENCIA",
           "PoliticaPermanenciaTerminal", "TERMOS_3C1", "discretizar", "disponibilidade", "entrada_3c1_de_json",
           "hash_entrada_3c1", "json_canonico_3c1", "obrigacao_derivada_s", "precisa_transitar", "tempo_s_exato",
           "validar_entrada_3c1"]
