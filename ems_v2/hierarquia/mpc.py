"""MPC HIERÁRQUICO (3C-4): o laço recedente 3C-3 conectado + planejador de longo prazo + custo de continuação.

Só biblioteca padrão. ``ControladorMPCHierarquico`` é subclasse de ``ControladorMPCConectado`` e substitui SÓ os pontos
de extensão do orquestrador 3C-2 (a máquina MPC — K6, observações tardias, confirmações, suspensão, checkpoints,
conciliação 3C-0, transporte do estado/memória EXECUTADOS — não é duplicada nem alterada). Ciclo em cada τ_k:

1. selar o corte I_k (orquestrador); 2. estado executado x_k; 3. previsão da janela curta (orquestrador) e previsão
LONGA [τ_k, τ_k + H_L,k) emitida pelo MESMO provedor a partir do MESMO instantâneo e validada (``_montar_entrada_janela``);
4. executar/atualizar o planejador (política declarada) ou usar o sinal do lote vigente para ESTA janela; 5. verificar o
sinal (selo, identidade, janela/fronteira — caducidade —, causalidade contra o livro K6, modelo/configuração, domínio,
modos × memória herdada); 6. resolver o MILP curto 3C-4 (``custo_futuro_estimado`` separado) — auditor 3C-3 + auditor
terminal; 7–9. aplicar os m_k primeiros intervalos, conciliar e contabilizar SÓ custos realizados (contabilidade 3C-3:
o valor futuro NUNCA entra no custo realizado), transportar estado e memória; 10. replanejar conforme a política.

Registro por decisão: ``RegistroCoordenacao3C4`` selado (sinal ou indisponibilidade, degradação aplicada, plano longo
resumido, decomposição do objetivo previsto × futuro × total), comprometido no registro 3C-0 da janela executada
(``hashes['coordenacao_3c4']``) ANTES do selo; por ponto de retomada, ``VinculoHierarquico3C4`` (inclui o lote pendente);
no fim, ``RegistroMissaoHierarquica3C4``.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, replace

from ..diagnostics import Constatacao, ContratoInvalido, aviso, erro
from ..mpc.previsao import PedidoPrevisao, validar_previsao_janela
from ..mpc.registro import selar, selo_confere
from ..ponte.canonico import sha256
from ..ponte.cenario import hash_previsao
from ..provenance import Procedencia
from ..rede.contrato import EntradaRede3C3, hash_entrada_3c3
from ..rede.mpc import ControladorMPCConectado, ResultadoMissaoConectada, hash_configuracao_rede
from ..timegrid import MalhaTemporal
from . import ESQUEMA_3C4, FORMULACAO_3C4, ROTULO_HIERARQUIA
from .contrato import (ConfiguracaoPlanejador3C4, EntradaHierarquica3C4, ParametroBateria, SinalValorFuturo,
                       TermoTerminal3C4, hash_configuracao_planejador, hash_entrada_3c4, validar_configuracao_planejador,
                       validar_entrada_3c4, validar_sinal_para_entrada, validar_sinal_para_janela)
from .planejador import JanelaAlvo, ResumoPlanoLongo, alvos_do_lote, horizonte_longo_em, planejar
from .valor import valor_termo_declarado

SITUACOES_COORDENACAO = {
    "valido": "Sinal do planejador verificado e aplicado ao MILP curto",
    "degradado_sem_valor_futuro": "Sinal indisponível/inválido: janela resolvida SEM valor futuro (rotulada)",
    "degradado_referencia": "Sinal indisponível/inválido: referência dura do plano longo aplicada (rotulada)",
    "indisponivel_interrompe": "Sinal indisponível/inválido e política 'interromper': janela recusada",
    "sem_coordenacao": "A decisão falhou antes da coordenação (previsão/estado/integridade)",
}


# ------------------------------------------------------------------------------------------------ registros
@dataclass(frozen=True)
class DecomposicaoObjetivo:
    tipo_terminal: str
    chave_terminal: str | None
    custo_operativo_previsto_R: float | None        # J_S: termos 3C-3 da janela (previsão)
    custo_futuro_estimado_R: float | None           # V̂(x_{k+N}) (instrumento de decisão)
    objetivo_total_R: float | None                  # objetivo do solver
    energias_fronteira_kWh: dict[str, float]
    modo: int | None
    classificacao: str | None
    estado_despacho: str | None
    gap_rel: float | None


@dataclass(frozen=True)
class RegistroCoordenacao3C4:
    esquema: int
    perfil: str
    missao_uid: str
    posicao: int
    indice_janela: int
    k: int
    instante_decisao_utc: str
    situacao: str                                   # SITUACOES_COORDENACAO
    origem_sinal: str                               # planejado_nesta_janela | lote_periodico | nenhuma
    sinal: SinalValorFuturo | None
    termo_aplicado: TermoTerminal3C4 | None
    hash_entrada_3c4: str | None
    hash_entrada_nucleo_3c3: str | None
    lote: tuple[SinalValorFuturo, ...]              # sinais EMITIDOS nesta decisão (inclui o da janela)
    plano_longo: ResumoPlanoLongo | None
    avaliacoes_planejador: int
    hash_previsao_longa: str | None
    decomposicao: DecomposicaoObjetivo | None
    classe_falha: str | None
    motivo: str
    constatacoes: tuple[Constatacao, ...]
    tempos_s: dict[str, float]
    selo: str = ""


def impressao_coordenacao(r: RegistroCoordenacao3C4) -> str:
    """Impressão DETERMINÍSTICA (sem tempos de relógio nem selo)."""
    return sha256(replace(r, tempos_s={}, selo=""))


@dataclass(frozen=True)
class VinculoHierarquico3C4:
    esquema: int
    missao_uid: str
    posicao: int
    selo_ultima_janela: str
    selo_coordenacao: str
    hash_modelo_rede: str
    hash_configuracao_rede: str
    hash_configuracao_planejador: str
    lote_pendente: tuple[SinalValorFuturo, ...]
    selo: str = ""


@dataclass(frozen=True)
class RegistroMissaoHierarquica3C4:
    esquema: int
    perfil: str
    missao_uid: str
    selo_registro_missao: str
    impressao_missao: str
    selo_registro_rede: str
    hash_modelo_rede: str
    hash_configuracao_rede: str
    hash_configuracao_planejador: str
    selos_coordenacao: tuple[str, ...]
    impressoes_coordenacao: tuple[str, ...]
    contagens: dict[str, int]                       # janelas por situação, avaliações do planejador
    valoracao_terminal_declarada_R: float | None    # Φ_L no estado final EXECUTADO (nunca custo)
    energias_finais_kWh: dict[str, float]
    tempos_planejador_s: dict[str, float]
    rotulo: str = ROTULO_HIERARQUIA
    selo: str = ""


def nome_coordenacao(missao_uid: str, posicao: int) -> str:
    return f"{missao_uid}.p{posicao:04d}.coord.mpc3c4.json"


def nome_vinculo_hier(missao_uid: str, posicao: int) -> str:
    return f"{missao_uid}.p{posicao:04d}.hier.mpc3c4.json"


def nome_missao_hier(missao_uid: str) -> str:
    return f"{missao_uid}.hier.missao.mpc3c4.json"


@dataclass
class ResultadoMissaoHierarquica(ResultadoMissaoConectada):
    coordenacoes: tuple = ()
    registro_hierarquico: RegistroMissaoHierarquica3C4 | None = None


# ------------------------------------------------------------------------------------------------ adaptador
class ResolvedorMILP3C4:
    """Adaptador EXPLÍCITO do MPC para ``resolver_3c4`` (import TARDIO). Resultado aceito ⇒ VISÃO núcleo 3C-3 que
    carrega o resultado 3C-4 (C-3C4-01); não aceito ⇒ o próprio resultado 3C-4 (nenhum plano é criado)."""
    natureza = "milp_3c4_pyomo_highs"

    def __init__(self, configuracao, *, tolerancias=None, identificador: str = "resolver_3c4", _executor=None,
                 _adulterar=None):
        self.configuracao, self.tolerancias, self.identificador = configuracao, tolerancias, identificador
        self._executor, self._adulterar = _executor, _adulterar

    def resolver(self, entrada, compromisso_parcial: dict | None = None):
        from ..audit import Tolerancias
        from ..milp.solver_3c4 import resolver_3c4, visao_nucleo_3c3
        r = resolver_3c4(entrada, self.configuracao, compromisso_parcial, tolerancias=self.tolerancias or Tolerancias(),
                         _executor=self._executor, _adulterar=self._adulterar)
        return visao_nucleo_3c3(r, entrada) if r.aceito else r

    def configuracao_registro(self) -> dict:
        c = self.configuracao
        reg = dataclasses.asdict(c) if dataclasses.is_dataclass(c) else {"tipo_recebido": type(c).__name__}
        return {"resolvedor": self.identificador, "natureza": self.natureza, "configuracao": reg,
                "executor_substituido": self._executor is not None, "adulteracao_de_ensaio": self._adulterar is not None}


def plano_de_resultado_3c4(res, e: EntradaHierarquica3C4, *, indice_fronteira_inicial: int):
    """Plano 3C-0 + plano de rede do NÚCLEO a partir da visão de um resultado 3C-4 ACEITO e verificado: perfil e hash
    3C-4 da entrada, hash núcleo, mesmo despacho e auditoria terminal aprovada. Qualquer divergência ⇒ nenhum plano."""
    from ..rede.execucao import plano_de_resultado_3c3
    r4 = getattr(res, "resultado_3c4", None)
    c = []
    if r4 is None or getattr(r4, "versao_formulacao", None) != FORMULACAO_3C4 or not getattr(r4, "aceito", False):
        c.append(erro("visao_nucleo_sem_resultado_3c4", "resultado", "Plano 3C-4 só de resultado 3C-4 aceito."))
    elif r4.hash_entrada != hash_entrada_3c4(e) or res.hash_entrada != hash_entrada_3c3(e.rede) or \
            getattr(res, "hash_entrada_3c4", None) != r4.hash_entrada:
        c.append(erro("plano_entrada_divergente", "resultado.hash_entrada", "Resultado de outra entrada 3C-4/núcleo."))
    elif res.despacho is not r4.despacho or res.custos_modelo is not r4.custos_modelo:
        c.append(erro("visao_nucleo_incoerente", "resultado", "Visão núcleo ≠ resultado 3C-4 que a originou."))
    elif r4.auditoria_terminal is None or not r4.auditoria_terminal.aceito:
        c.append(erro("termo_terminal_nao_auditado", "resultado.auditoria_terminal", "Termo terminal sem aprovação."))
    if c:
        raise ContratoInvalido(c)
    return plano_de_resultado_3c3(res, e.rede, indice_fronteira_inicial=indice_fronteira_inicial)


# ------------------------------------------------------------------------------------------------ controlador
class ControladorMPCHierarquico(ControladorMPCConectado):
    _PERFIL_JANELA = "3C-4"

    def __init__(self, cfg, modelo: EntradaRede3C3, provedor, resolvedor, fontes_disponibilidade: dict,
                 configuracao_rede, configuracao_planejador: ConfiguracaoPlanejador3C4, planejador_resolvedor, **kw):
        c = [x for x in validar_configuracao_planejador(configuracao_planejador, cfg, modelo) if x.severidade != "aviso"]
        if c:
            raise ContratoInvalido(c)
        self.cfg_plan, self.res_plan = configuracao_planejador, planejador_resolvedor
        self.coordenacoes: list[RegistroCoordenacao3C4] = []
        self._lote: dict[int, SinalValorFuturo] = {}
        self._coord: dict | None = None
        self._coord_aberto: RegistroCoordenacao3C4 | None = None
        self.registro_hierarquico: RegistroMissaoHierarquica3C4 | None = None
        self._tempos_plan: dict[str, float] = {}
        super().__init__(cfg, modelo, provedor, resolvedor, fontes_disponibilidade, configuracao_rede, **kw)
        self._hash_modelo = hash_entrada_3c3(self.modelo_rede)
        self._hash_cfg_plan = hash_configuracao_planejador(configuracao_planejador)

    # ---------------------------------------------------------------- coordenação
    def _previsao_longa(self, jan, hash_inst: str):
        inst = self.livro.instantaneo(jan.inicio_utc)
        if inst.hash != hash_inst:
            raise ContratoInvalido([erro("instantaneo_divergente", "planejador", "Instantâneo ≠ o da decisão.")])
        H = horizonte_longo_em(self.cfg, self.cfg_plan, jan.k)
        m = self.cfg.malha
        malha_l = MalhaTemporal(jan.inicio_utc, m.delta_min, H, 1, H, m.horizonte_previsao_min)
        ped = PedidoPrevisao(self.cfg.identidade.missao_uid, self.cfg.identidade.microrrede_uid, jan.indice_janela,
                             jan.k, jan.inicio_utc, m.delta_s, H, self._chaves_previsao(), inst)
        prev = self.provedor.emitir(ped)
        cp = validar_previsao_janela(prev, ped, malha_l, provedor_id=self.provedor.identificador,
                                     provedor_natureza=self.provedor.natureza,
                                     rotulo_informacao=self.cfg.rotulo_informacao,
                                     identificadores_verdade=self.id_verdade, fontes_verdade=self.fontes_verdade)
        if cp:
            raise ContratoInvalido(cp)
        return prev

    def _contexto_validacao(self, jan, s: SinalValorFuturo, e3r: EntradaRede3C3) -> list[Constatacao]:
        try:
            hi = self.livro.instantaneo(s.instante_emissao_utc).hash
        except ContratoInvalido:
            hi = None
        c = validar_sinal_para_janela(s, missao_uid=self.cfg.identidade.missao_uid, indice_janela=jan.indice_janela,
                                      k=jan.k, instante_utc=jan.inicio_utc, fronteira=jan.k + jan.N_k,
                                      hash_modelo_rede=self._hash_modelo, hash_configuracao=self._hash_cfg_plan,
                                      hash_instantaneo_emissao=hi)
        return c + validar_sinal_para_entrada(s, e3r)

    def _montar_entrada_janela(self, jan, prev, hash_instantaneo: str, proc: Procedencia):
        e3r = super()._montar_entrada_janela(jan, prev, hash_instantaneo, proc)
        t0 = self._clock()
        co = {"jan": jan, "origem": "nenhuma", "sinal": None, "lote": (), "plano": None, "avaliacoes": 0,
              "hash_prev_longa": None, "constatacoes": [], "tempos": {}, "situacao": None, "termo": None,
              "he4": None, "hen": hash_entrada_3c3(e3r), "motivo": ""}
        self._coord = co
        sinal = self._lote.pop(jan.indice_janela, None)
        if sinal is not None:
            cs = self._contexto_validacao(jan, sinal, e3r)
            if cs:
                co["constatacoes"].append(aviso("sinal_do_lote_invalido_replanejado", "coordenacao",
                                                "; ".join(f"[{x.codigo}]" for x in cs[:4])))
                sinal = None
            else:
                co["origem"] = "lote_periodico"
        if sinal is None:
            self._lote = {}
            try:
                prev_l = self._previsao_longa(jan, hash_instantaneo)
                co["hash_prev_longa"] = hash_previsao(prev_l)
                from .planejador import ContextoPlanejamento
                alvos = alvos_do_lote(self.cfg, jan.k, jan.indice_janela, self.cfg_plan.periodo_janelas)
                if not alvos or alvos[0] != JanelaAlvo(jan.indice_janela, jan.k, jan.N_k):
                    raise ContratoInvalido([erro("lote_incoerente", "planejador", "Janela atual ≠ 1º alvo do lote.")])
                ctx = ContextoPlanejamento(self.modelo_rede, self.cfg, self.cfg_rede, self.cfg_plan, jan.k,
                                           jan.inicio_utc, self.estado, prev_l, hash_instantaneo, alvos, e3r)
                rp = planejar(ctx, self.res_plan, relogio=self._clock)
                co.update(plano=rp.plano_longo, avaliacoes=rp.avaliacoes, lote=tuple(rp.sinais[a.indice_janela]
                                                                                     for a in alvos))
                co["constatacoes"] += list(rp.constatacoes)
                co["tempos"].update({f"planejador_{k}": v for k, v in rp.tempos_s.items()})
                for k_, v in rp.tempos_s.items():
                    self._tempos_plan[k_] = self._tempos_plan.get(k_, 0.0) + v
                sinal = rp.sinais[jan.indice_janela]
                self._lote = {a.indice_janela: rp.sinais[a.indice_janela] for a in alvos[1:]}
                co["origem"] = "planejado_nesta_janela"
            except ContratoInvalido as exc:
                co["constatacoes"] += list(exc.constatacoes)
                co["motivo"] = "previsão longa/planejamento recusado: " + "; ".join(sorted(exc.codigos)[:4])
        co["sinal"] = sinal
        cs = [erro("sinal_valor_futuro_indisponivel", "coordenacao", co["motivo"] or "sem sinal")] if sinal is None \
            else self._contexto_validacao(jan, sinal, e3r)
        if not cs:
            termo = TermoTerminal3C4("sinal_valor_futuro", (), (), sinal,
                                     "Custo de continuação do planejador de longo prazo (instrumento de decisão)",
                                     Procedencia("sintetico", "Planejador 3C-4", f"janela {jan.indice_janela}"))
            co["situacao"] = "valido"
        else:
            co["constatacoes"] += cs
            co["motivo"] = co["motivo"] or "; ".join(f"[{x.codigo}] {x.mensagem}" for x in cs[:3])
            termo = self._degradar(co, e3r)
        co["termo"] = termo
        co["tempos"]["coordenacao_s"] = self._clock() - t0
        if termo is None:
            raise ContratoInvalido([erro("sinal_valor_futuro_indisponivel", "coordenacao",
                                         f"Política 'interromper': {co['motivo']}")])
        e4 = EntradaHierarquica3C4(ESQUEMA_3C4, FORMULACAO_3C4, e3r, termo, proc)
        co["he4"] = hash_entrada_3c4(e4)
        return e4

    def _degradar(self, co: dict, e3r) -> TermoTerminal3C4 | None:
        pol = self.cfg_plan.degradacao
        proc = Procedencia("sintetico", "Planejador 3C-4 — degradação declarada", f"política {pol}")
        if pol == "sem_valor_futuro_rotulado":
            co["situacao"] = "degradado_sem_valor_futuro"
            return TermoTerminal3C4("nenhum_declarado", (), (), None,
                                    f"DEGRADADO (sinal indisponível: {co['motivo'][:160]}); janela sem valor futuro", proc)
        if pol == "referencia_terminal_do_plano_longo":
            pl = co.get("plano")
            i = co["jan"].N_k
            if pl is not None and pl.objetivo_R is not None and all(len(v) > i for v in pl.energias_kWh.values()) \
                    and pl.energias_kWh:
                co["situacao"] = "degradado_referencia"
                return TermoTerminal3C4("energia_minima_declarada", (), tuple(
                    ParametroBateria(u, float(v[i])) for u, v in sorted(pl.energias_kWh.items())), None,
                    f"DEGRADADO: referência dura E(N) >= E_ref do plano longo ({co['motivo'][:120]})", proc)
        co["situacao"] = "indisponivel_interrompe"
        return None

    # ---------------------------------------------------------------- pontos de extensão
    def _validar_entrada_janela(self, e):
        return validar_entrada_3c4(e)

    def _hash_entrada(self, e) -> str:
        return hash_entrada_3c3(e.rede) if isinstance(e, EntradaHierarquica3C4) else super()._hash_entrada(e)

    def _plano_de_resultado(self, res, e, k: int):
        out = plano_de_resultado_3c4(res, e, indice_fronteira_inicial=k)
        self._finalizar_coordenacao(None, res=res)
        return out

    @staticmethod
    def _nucleo(ab):
        return replace(ab, e3=ab.e3.rede) if isinstance(ab.e3, EntradaHierarquica3C4) else ab

    def _executor_conciliacao(self, ab, identificador: str, *, conciliacao: bool):
        return super()._executor_conciliacao(self._nucleo(ab), identificador, conciliacao=conciliacao)

    def _contabilidade(self, ab, traj, real, *, planejado: bool = False):
        return super()._contabilidade(self._nucleo(ab), traj, real, planejado=planejado)

    def _artefatos_registro(self, ab, traj, real, contab):
        hashes, fechar = super()._artefatos_registro(self._nucleo(ab), traj, real, contab)
        co = self._coord_aberto
        extra = {"coordenacao_3c4": co.selo, "coordenacao_3c4_impressao": impressao_coordenacao(co),
                 "entrada_3c4": co.hash_entrada_3c4 or ""}
        if co.sinal is not None:
            extra["sinal_valor_futuro"] = co.sinal.selo
        return {**hashes, **{k: v for k, v in extra.items() if v}}, fechar

    def _falhar_sem_plano(self, jan, tk, inst, classe, motivo, *, prev=None, constat=(), he=None, res=None):
        self._finalizar_coordenacao((jan, tk), res=res, classe=classe, motivo=motivo)
        return super()._falhar_sem_plano(jan, tk, inst, classe, motivo, prev=prev, constat=constat, he=he, res=res)

    def _finalizar_coordenacao(self, jan_tk, *, res=None, classe=None, motivo=""):
        co = self._coord
        self._coord = None
        if co is None:
            jan, tk = jan_tk
            co = {"jan": jan, "origem": "nenhuma", "sinal": None, "lote": (), "plano": None, "avaliacoes": 0,
                  "hash_prev_longa": None, "constatacoes": [], "tempos": {}, "situacao": "sem_coordenacao",
                  "termo": None, "he4": None, "hen": None, "motivo": motivo}
        jan = co["jan"]
        r4 = getattr(res, "resultado_3c4", res)
        dec = None
        if r4 is not None and getattr(r4, "versao_formulacao", None) == FORMULACAO_3C4:
            tt = getattr(r4, "termo_terminal", {}) or {}
            dec = DecomposicaoObjetivo(getattr(r4, "tipo_terminal", "?") or "?", tt.get("chave"),
                                       r4.custo_operativo_previsto_R, r4.custo_futuro_estimado_R,
                                       (r4.custos_modelo or {}).get("total"),
                                       {k: float(v) for k, v in (tt.get("energias_kWh") or {}).items()}, tt.get("modo"),
                                       r4.classificacao, r4.estado_despacho, r4.gap_rel)
        reg = RegistroCoordenacao3C4(
            ESQUEMA_3C4, FORMULACAO_3C4, self.cfg.identidade.missao_uid, len(self.registros), jan.indice_janela, jan.k,
            jan.inicio_utc, co["situacao"] or "sem_coordenacao", co["origem"], co["sinal"], co["termo"], co["he4"],
            co["hen"], tuple(co["lote"]), co["plano"], int(co["avaliacoes"]), co["hash_prev_longa"], dec, classe,
            (co["motivo"] or motivo or "")[:400], tuple(x for x in co["constatacoes"] if isinstance(x, Constatacao)),
            {k: float(v) for k, v in sorted(co["tempos"].items()) if isinstance(v, (int, float)) and math.isfinite(v)})
        self._coord_aberto = selar(reg)

    def _selar_e_gravar(self, conteudo, reg0, anexo, tempos) -> None:
        super()._selar_e_gravar(conteudo, reg0, anexo, tempos)
        r = self.registros[-1]
        co = self._coord_aberto
        self._coord_aberto = None
        if co is None or co.posicao != r.conteudo.posicao:
            raise ContratoInvalido([erro("coordenacao_dessincronizada", "coordenacao",
                                         "Registro de coordenação ausente/de outra posição.")])
        self.coordenacoes.append(co)
        if self.diretorio is not None:
            from ..mpc.persistencia import gravar_exclusivo
            from ..ponte.canonico import json_canonico
            m = self.cfg.identidade.missao_uid
            gravar_exclusivo(self.diretorio, nome_coordenacao(m, co.posicao), json_canonico(co))
            v = selar(VinculoHierarquico3C4(ESQUEMA_3C4, m, r.conteudo.posicao, r.selo, co.selo, self._hash_modelo,
                                            hash_configuracao_rede(self.cfg_rede), self._hash_cfg_plan,
                                            tuple(self._lote[j] for j in sorted(self._lote))))
            gravar_exclusivo(self.diretorio, nome_vinculo_hier(m, v.posicao), json_canonico(v))

    # ---------------------------------------------------------------- missão
    def contagens(self) -> dict[str, int]:
        out = {k: 0 for k in SITUACOES_COORDENACAO}
        for c in self.coordenacoes:
            out[c.situacao] = out.get(c.situacao, 0) + 1
        out["avaliacoes_planejador"] = sum(c.avaliacoes_planejador for c in self.coordenacoes)
        out["execucoes_planejador"] = sum(1 for c in self.coordenacoes if c.origem_sinal == "planejado_nesta_janela"
                                          or c.plano_longo is not None)
        out["sinais_de_lote"] = sum(1 for c in self.coordenacoes if c.origem_sinal == "lote_periodico")
        return out

    def finalizar(self, *, ambiente: dict | None = None):
        rm = super().finalizar(ambiente=ambiente)
        en = {x.uid: float(x.energia_kWh) for x in self.estado.armazenamento}
        val = valor_termo_declarado(self.cfg_plan.termo_longo, en) if en or self.cfg_plan.termo_longo.tipo == \
            "nenhum_declarado" else None
        rh = selar(RegistroMissaoHierarquica3C4(
            ESQUEMA_3C4, FORMULACAO_3C4, self.cfg.identidade.missao_uid, rm.selo, rm.impressao_deterministica,
            self.registro_rede.selo, self._hash_modelo, hash_configuracao_rede(self.cfg_rede), self._hash_cfg_plan,
            tuple(c.selo for c in self.coordenacoes), tuple(impressao_coordenacao(c) for c in self.coordenacoes),
            self.contagens(), val, en, dict(sorted(self._tempos_plan.items()))))
        self.registro_hierarquico = rh
        if self.diretorio is not None:
            from ..mpc.persistencia import gravar_exclusivo
            from ..ponte.canonico import json_canonico
            gravar_exclusivo(self.diretorio, nome_missao_hier(rh.missao_uid), json_canonico(rh))
        return rm

    def resultado(self, registro_missao, entorno: dict | None = None) -> ResultadoMissaoHierarquica:
        b = super().resultado(registro_missao, entorno)
        return ResultadoMissaoHierarquica(**{f.name: getattr(b, f.name) for f in dataclasses.fields(
            ResultadoMissaoConectada)}, coordenacoes=tuple(self.coordenacoes),
            registro_hierarquico=self.registro_hierarquico)


def verificar_registro_hierarquico(rh: RegistroMissaoHierarquica3C4, rm, rr, coordenacoes) -> list[Constatacao]:
    """Selo, esquema/perfil/rótulo, vínculo aos registros de missão MPC e de rede, sequência de coordenações (selos e
    impressões) e contagens recalculadas."""
    out = []
    if not isinstance(rh, RegistroMissaoHierarquica3C4):
        return [erro("registro_hierarquico_invalido", "missao_hier", type(rh).__name__)]
    try:
        ok = selo_confere(rh)
    except (TypeError, ValueError):
        ok = False
    if not ok:
        out.append(erro("registro_hierarquico_adulterado", "missao_hier.selo", "Selo não confere."))
    if rh.esquema != ESQUEMA_3C4 or type(rh.esquema) is not int or rh.perfil != FORMULACAO_3C4 or \
            rh.rotulo != ROTULO_HIERARQUIA:
        out.append(erro("registro_hierarquico_incompativel", "missao_hier", "Esquema/perfil/rótulo ≠ 3C-4."))
    if rh.selo_registro_missao != rm.selo or rh.impressao_missao != rm.impressao_deterministica or \
            rr is None or rh.selo_registro_rede != rr.selo:
        out.append(erro("registro_hierarquico_de_outra_missao", "missao_hier", "Não vinculado aos registros da missão."))
    if rh.selos_coordenacao != tuple(c.selo for c in coordenacoes) or rh.impressoes_coordenacao != tuple(
            impressao_coordenacao(c) for c in coordenacoes):
        out.append(erro("coordenacoes_divergentes", "missao_hier.selos_coordenacao", "Sequência de coordenações ≠."))
    return out


__all__ = ["ControladorMPCHierarquico", "DecomposicaoObjetivo", "RegistroCoordenacao3C4",
           "RegistroMissaoHierarquica3C4", "ResolvedorMILP3C4", "ResultadoMissaoHierarquica", "SITUACOES_COORDENACAO",
           "VinculoHierarquico3C4", "impressao_coordenacao", "nome_coordenacao", "nome_missao_hier",
           "nome_vinculo_hier", "plano_de_resultado_3c4", "verificar_registro_hierarquico"]
