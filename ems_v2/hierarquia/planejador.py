"""Planejador de LONGO PRAZO (3C-4) e estimação do custo de continuação — só biblioteca padrão.

O planejador NUNCA é executado na planta: orienta o MPC curto. Em τ_k (instante de EMISSÃO) ele recebe o estado
EXECUTADO e conciliado x_k, a previsão LONGA validada (emitida a partir do instantâneo selado em τ_k, cobrindo
[τ_k, τ_k + H_L,k), H_L,k = min(H_L, K_M − k): nenhuma extrapolação) e os perfis tarifários de decisão disponíveis em
τ_k (``selecionar_perfil_causal`` NO INSTANTE DE EMISSÃO — nunca no início da cauda, o que vazaria revisões futuras).

1. **Plano longo** — o MILP 3C-4 (núcleo 3C-3 inalterado: física, commitment, PCC) sobre [τ_k, fim) a partir de x_k
   com o termo terminal DECLARADO Φ_L. Fornece a referência terminal (E_ref, modo de referência) e diagnósticos.
2. **Cauda paramétrica** — para a fronteira b da janela curta, ``V^tail(E, σ)`` = valor ÓTIMO auditado do MILP 3C-4
   sobre [τ_b, fim) com estado inicial (E, σ) e o MESMO Φ_L: por construção a cauda começa na fronteira e não inclui
   nenhum intervalo da janela curta (sem dupla contagem). Cada avaliação é uma resolução completa com auditor 3C-3 +
   auditor terminal; só ``aceito_otimo`` certifica um ponto; ``inviavel`` é EVIDÊNCIA de domínio (energia insuficiente
   para a cauda ser factível); qualquer outra classificação torna o sinal indisponível (nada é presumido).
3. **Representação** (``ConfiguracaoPlanejador3C4.tipo_sinal``): PWL por modo (1D com refinamento adaptativo por
   bissecção dos segmentos cujo erro no ponto médio excede a tolerância; 2D em grade com convexidade verificada e
   validação nos centros), sensibilidade local por diferença central, ou referências energéticas experimentais.

Modos terminais: por gerador, (ligado, obrigação residual). Com obrigação herdada além da janela, o modo é FIXO
(fato conhecido em τ_k); sem ela, {desligado, ligado} com obrigação 0 (garantida por ``cumprir_na_janela``) filtrado
pela disponibilidade PREVISTA no último intervalo. A memória da cauda usa tempo no estado = ⌈T⌉ − ρ: qualquer tempo
>= T dá a MESMA cauda (a M12 só depende da obrigação residual — FORMULACAO_3C4 §4.3). Potência do último intervalo:
irrelevante para a cauda quando as rampas de transição são inativas no domínio ON (lema §4.4); caso contrário é
FIXADA no modo (p do plano longo, ou P_on_min se o plano longo não liga o gerador) e o MPC curto a respeita.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, replace
from datetime import timedelta

from ..compromisso.contrato import discretizar, tempo_s_exato
from ..contracts import Disponibilidade
from ..diagnostics import Constatacao, ContratoInvalido, aviso, erro
from ..mpc.janela import montar_entrada_janela
from ..mpc.relogio import JanelaMPC, instante_fronteira
from ..ponte.canonico import sha256
from ..ponte.cenario import hash_previsao
from ..ponte.execucao import EstadoArmazenamento, EstadoGeracao, EstadoMicrorrede
from ..provenance import Procedencia
from ..rede.contrato import EntradaRede3C3, hash_entrada_3c3, hash_perfil, selecionar_perfil_causal
from ..timegrid import ler_instante_utc
from . import ESQUEMA_3C4, FORMULACAO_3C4
from .contrato import (CONVENCAO_SINAIS, ConfiguracaoPlanejador3C4, DiagnosticoModo, EntradaHierarquica3C4, EstadoTerminalGerador,
                       ModoValor, PontoValidacao, PontoValor, QualidadeSinal, ReferenciaTerminal, SensibilidadeLocal,
                       SinalValorFuturo, hash_configuracao_planejador, hash_termo, limites_energia,
                       residuo_terminal_herdado, selar_sinal)
from .valor import convexidade_verificada_na_amostra, envoltoria_convexa, interpolar_1d, valor_termo_declarado


# ================================================================================================ adaptador
class ResolvedorPlanejador3C4:
    """Adaptador EXPLÍCITO para ``ems_v2.milp.solver_3c4.resolver_3c4`` (import TARDIO, dentro de ``resolver``)."""
    natureza = "milp_3c4_pyomo_highs_planejador"

    def __init__(self, configuracao, *, tolerancias=None, identificador: str = "planejador_3c4", _executor=None):
        self.configuracao, self.tolerancias, self.identificador = configuracao, tolerancias, identificador
        self._executor = _executor

    def resolver(self, entrada):
        from ..audit import Tolerancias
        from ..milp.solver_3c4 import resolver_3c4
        return resolver_3c4(entrada, self.configuracao, None, tolerancias=self.tolerancias or Tolerancias(),
                            _executor=self._executor)

    def resolver_cobertura(self, entrada, faixas: dict) -> dict:
        from ..milp.solver_3c4 import resolver_cobertura_3c4
        return resolver_cobertura_3c4(entrada, self.configuracao, faixas)

    def configuracao_registro(self) -> dict:
        import dataclasses
        c = self.configuracao
        reg = dataclasses.asdict(c) if dataclasses.is_dataclass(c) else {"tipo_recebido": type(c).__name__}
        return {"resolvedor": self.identificador, "natureza": self.natureza, "configuracao": reg,
                "executor_substituido": self._executor is not None}


# ================================================================================================ contexto
@dataclass(frozen=True)
class JanelaAlvo:
    indice_janela: int
    k: int
    N_k: int

    @property
    def fronteira(self) -> int:
        return self.k + self.N_k


@dataclass
class ContextoPlanejamento:
    modelo_rede: EntradaRede3C3
    cfg: object                      # ConfiguracaoMPC
    cfg_rede: object                 # ConfiguracaoRedeMPC
    cfg_plan: ConfiguracaoPlanejador3C4
    k: int
    instante_utc: str                # τ_k = instante de EMISSÃO
    estado: EstadoMicrorrede         # estado EXECUTADO em τ_k
    previsao_longa: object           # ConjuntoPrevisao validado [τ_k, τ_k + H_L,k)
    hash_instantaneo: str
    alvos: tuple[JanelaAlvo, ...]
    entrada_janela_atual: EntradaRede3C3 | None = None   # para a obrigação herdada (só a janela atual)


@dataclass(frozen=True)
class ResumoPlanoLongo:
    k: int
    indice_fim: int
    classificacao: str | None
    estado_despacho: str | None
    objetivo_R: float | None
    hash_entrada_3c4: str | None
    energias_kWh: dict[str, tuple[float, ...]]       # trajetória e (fronteiras k..fim)
    compromisso: dict[str, tuple[int, ...]]          # u por intervalo
    potencias_kW: dict[str, tuple[float, ...]]
    codigos: tuple[str, ...]


@dataclass
class ResultadoPlanejamento:
    sinais: dict[int, SinalValorFuturo]
    plano_longo: ResumoPlanoLongo | None
    avaliacoes: int
    tempos_s: dict[str, float] = field(default_factory=dict)
    constatacoes: list = field(default_factory=list)
    avaliacoes_detalhe: list = field(default_factory=list)   # (fronteira, modo, energias, classificação, valor, s)


def horizonte_longo_em(cfg, cfg_plan: ConfiguracaoPlanejador3C4, k: int) -> int:
    return min(cfg_plan.horizonte_longo_intervalos, cfg.malha.intervalos_missao - k)


# ================================================================================================ entradas
def entrada_rede_planejamento(ctx: ContextoPlanejamento, k_ini: int, N: int, estado: EstadoMicrorrede,
                              proc: Procedencia) -> EntradaRede3C3:
    """Entrada 3C-3 de [τ_{k_ini}, τ_{k_ini+N}) com a previsão LONGA e as tarifas selecionadas em τ_k (EMISSÃO)."""
    cfg = ctx.cfg
    inicio = instante_fronteira(cfg.malha, k_ini)
    jan = JanelaMPC(-1, k_ini, inicio, N, 1, N, 0, False, False, True, ctx.cfg_plan.permanencia_fim_planejamento, N)
    m = ctx.modelo_rede
    e3 = montar_entrada_janela(m.compromisso, cfg, jan, ctx.previsao_longa, estado,
                               hash_instantaneo=ctx.hash_instantaneo, procedencia=proc)
    if not m.conectado:
        return replace(m, compromisso=e3)
    s = ctx.previsao_longa.serie(str(m.pcc.uid), "disponibilidade")
    if s is None:
        raise ContratoInvalido([erro("previsao_chave_ausente", f"previsao_longa[{m.pcc.uid}:disponibilidade]",
                                     "Disponibilidade prevista do PCC ausente.")])
    orc = cfg.rotulo_informacao == "ablacao_oraculo"
    sel, c = {}, []
    for gr, exig in (("importacao", m.importa), ("exportacao", m.exporta and
                                                m.economia.remuneracao_exportacao == "remunerada")):
        if exig:
            p, cc = selecionar_perfil_causal(ctx.cfg_rede.tarifas_decisao, gr, ctx.instante_utc, oraculo=orc)
            sel[gr] = p
            c += cc
    if c:
        raise ContratoInvalido(c)
    ec = replace(m.economia, tarifa_importacao=sel.get("importacao"), tarifa_exportacao=sel.get("exportacao"))
    return replace(m, compromisso=e3, pcc=replace(m.pcc, disponibilidade=Disponibilidade(s.serie)), economia=ec)


def _envolver(ctx, rede: EntradaRede3C3, proc) -> EntradaHierarquica3C4:
    return EntradaHierarquica3C4(ESQUEMA_3C4, FORMULACAO_3C4, rede, ctx.cfg_plan.termo_longo, proc)


def _tempo_no_estado(sp, ligado: bool, obrig_s: int) -> int:
    T = tempo_s_exato(sp.tempo_min_ligado_min if ligado else sp.tempo_min_desligado_min)
    if T is None:
        return 0
    return int(math.ceil(T)) - int(obrig_s)


def estado_na_fronteira(ctx: ContextoPlanejamento, b: int, energias: dict[str, float],
                        geradores: tuple[EstadoTerminalGerador, ...], p_ref: dict[str, float]) -> EstadoMicrorrede:
    m = ctx.modelo_rede.compromisso
    ger = []
    for x in geradores:
        p = (x.potencia_fixada_kW if x.potencia_fixada_kW is not None else p_ref[x.uid]) if x.ligado else 0.0
        ger.append(EstadoGeracao(x.uid, x.ligado, float(p), _tempo_no_estado(m.unidade(x.uid), x.ligado,
                                                                              x.obrigacao_residual_s)))
    return EstadoMicrorrede(ctx.estado.microrrede_uid, b, instante_fronteira(ctx.cfg.malha, b),
                            tuple(sorted((EstadoArmazenamento(u, float(v)) for u, v in energias.items()),
                                         key=lambda z: z.uid)),
                            tuple(sorted(ger, key=lambda z: z.uid)))


def rampa_inativa_na_fronteira(d) -> bool:
    """Lema §4.4: com ``u_{b−1} = 1`` a potência do último intervalo não restringe a cauda se toda variação ON→ON cabe
    nas rampas e a parada a partir de qualquer p ON é representável no limite de parada."""
    amp = d.p_on_max_kW - d.p_on_min_kW
    sobe = d.rampa_subida_kW is None or d.rampa_subida_kW >= amp - 1e-9
    desce = d.rampa_descida_kW is None or d.rampa_descida_kW >= amp - 1e-9
    para = (not d.parada_representavel) or (d.limite_parada_kW is not None and d.limite_parada_kW >= d.p_on_max_kW - 1e-9)
    return sobe and desce and para


# ================================================================================================ planejador
class Planejador3C4:
    def __init__(self, ctx: ContextoPlanejamento, resolvedor, relogio=time.perf_counter):
        self.ctx, self.res, self._clock = ctx, resolvedor, relogio
        self.cache: dict = {}
        self.avaliacoes = 0
        self.detalhe: list = []
        self.tempos: dict[str, float] = {"plano_longo_s": 0.0, "cauda_s": 0.0}
        cp = ctx.cfg_plan
        self.fim = ctx.k + horizonte_longo_em(ctx.cfg, cp, ctx.k)
        self.bats = tuple(sorted(str(x.uid) for x in ctx.modelo_rede.base.baterias))
        self.gers = tuple(sorted(str(g.uid) for g in ctx.modelo_rede.base.geradores))
        self.lim = limites_energia(ctx.modelo_rede)
        self.proc = Procedencia("sintetico", f"Planejador 3C-4 missão {ctx.cfg.identidade.missao_uid}",
                                f"emissão k = {ctx.k}", observacoes="previsão longa e tarifas disponíveis em τ_k")
        self.plano = None
        self.res_longo = None

    # ------------------------------------------------------------------------------------- plano longo
    def plano_longo(self) -> ResumoPlanoLongo | None:
        ctx = self.ctx
        t0 = self._clock()
        try:
            rede = entrada_rede_planejamento(ctx, ctx.k, self.fim - ctx.k, ctx.estado, self.proc)
            r = self.res.resolver(_envolver(ctx, rede, self.proc))
        except ContratoInvalido as exc:
            self.tempos["plano_longo_s"] += self._clock() - t0
            self.plano = ResumoPlanoLongo(ctx.k, self.fim, None, None, None, None, {}, {}, {}, tuple(exc.codigos))
            return self.plano
        self.tempos["plano_longo_s"] += self._clock() - t0
        self.avaliacoes += 1
        self.res_longo = r
        en, uu, pp = {}, {}, {}
        if r.aceito:
            for u, d in r.despacho.get("baterias", {}).items():
                en[u] = tuple(float(x) for x in d["e"])
            for g, d in r.despacho.get("geradores", {}).items():
                uu[g] = tuple(1 if float(x) > 0.5 else 0 for x in d["u"])
                pp[g] = tuple(float(x) for x in d["p"])
        self.plano = ResumoPlanoLongo(ctx.k, self.fim, r.classificacao, r.estado_despacho,
                                      r.custos_modelo.get("total") if r.aceito else None, r.hash_entrada, en, uu, pp,
                                      tuple(sorted(r.codigos())))
        return self.plano

    # ------------------------------------------------------------------------------------- cauda
    def avaliar(self, b: int, modo: tuple[EstadoTerminalGerador, ...], energias: tuple[float, ...],
                p_ref: dict[str, float]):
        """(situação, V, limite_inferior) da cauda [b, fim) a partir de (E, modo). Situação: ok | inviavel | falha."""
        chave = (b, tuple((x.uid, x.ligado, x.obrigacao_residual_s, x.potencia_fixada_kW) for x in modo),
                 tuple(round(e, 9) for e in energias))
        if chave in self.cache:
            return self.cache[chave]
        ctx = self.ctx
        t0 = self._clock()
        est = estado_na_fronteira(ctx, b, dict(zip(self.bats, energias)), modo, p_ref)
        try:
            rede = entrada_rede_planejamento(ctx, b, self.fim - b, est, self.proc)
            r = self.res.resolver(_envolver(ctx, rede, self.proc))
            self.avaliacoes += 1
            if r.aceito and r.classificacao == "otimo":
                out = ("ok", float(r.custos_modelo["total"]), r.limite_dual)
            elif r.classificacao == "inviavel":
                out = ("inviavel", None, None)
            else:
                out = ("falha", None, f"{r.classificacao}/{r.estado_despacho}: {sorted(r.codigos())[:4]}")
        except ContratoInvalido as exc:
            out = ("falha", None, f"entrada da cauda recusada: {sorted(exc.codigos)[:4]}")
        self.tempos["cauda_s"] += self._clock() - t0
        self.cache[chave] = out
        self.detalhe.append((b, chave[1], tuple(energias), out[0], out[1]))
        return out

    # ------------------------------------------------------------------------------------- modos
    def modos(self, alvo: JanelaAlvo) -> tuple[list[tuple[EstadoTerminalGerador, ...]], dict[str, float], list]:
        ctx = self.ctx
        c: list[Constatacao] = []
        if not self.gers:
            return [()], {}, c
        disc = discretizar(ctx.modelo_rede.compromisso)
        her = residuo_terminal_herdado(ctx.entrada_janela_atual) if (
            ctx.entrada_janela_atual is not None and alvo.k == ctx.k) else {}
        opcoes, p_ref = [], {}
        for g in self.gers:
            d = disc[g]
            p_ref[g] = d.p_on_min_kW
            fix = None
            if not rampa_inativa_na_fronteira(d):
                pl = self.plano
                if pl is not None and g in pl.compromisso and pl.compromisso[g][alvo.fronteira - 1 - ctx.k] == 1:
                    fix = pl.potencias_kW[g][alvo.fronteira - 1 - ctx.k]
                else:
                    fix = d.p_on_min_kW
            u0, r, res = her.get(g, (None, 0, 0))
            if res > 0:
                ops = [EstadoTerminalGerador(g, bool(u0), int(res), fix if u0 else None)]
            else:
                a = self.ctx.previsao_longa.serie(g, "disponibilidade")
                idx = alvo.fronteira - 1 - ctx.k
                disp_ult = None if a is None else a.serie.valores[idx] if idx < len(a.serie.valores) else None
                ops = [EstadoTerminalGerador(g, False, 0, None)]
                if disp_ult is None or disp_ult >= 1.0:
                    ops.append(EstadoTerminalGerador(g, True, 0, fix))
            opcoes.append(ops)
        combos = [()]
        for ops in opcoes:
            combos = [cmb + (o,) for cmb in combos for o in ops]
        if len(combos) > ctx.cfg_plan.max_modos:
            c.append(erro("modos_excedem_limite", "planejador.max_modos",
                          f"{len(combos)} combinações de estados terminais > {ctx.cfg_plan.max_modos} declaradas."))
        return combos, p_ref, c

    # ------------------------------------------------------------------------------------- sinais
    def sinal(self, alvo: JanelaAlvo) -> SinalValorFuturo:
        ctx = self.ctx
        cp = ctx.cfg_plan
        b = alvo.fronteira
        cauda = max(0, self.fim - b)
        ref = self._referencia(alvo)
        if cauda == 0 or b >= self.fim:
            return self._sinal_cauda_vazia(alvo, ref)
        combos, p_ref, cm = self.modos(alvo)
        if cm:
            return self._indisponivel(alvo, "; ".join(x.mensagem for x in cm), ref)
        if cp.tipo_sinal in ("referencia_energia_dura", "referencia_energia_branda"):
            if ref is None:
                return self._indisponivel(alvo, "plano longo sem solução aceita: referência terminal inexistente", None)
            return self._montar(alvo, (), ref, None, QualidadeSinal("valido", "referência do plano longo", None,
                                                                    cp.tolerancia_interpolacao_R, None, 0, ()))
        if cp.tipo_sinal == "valor_marginal_local":
            return self._sinal_local(alvo, ref, combos, p_ref)
        return self._sinal_pwl(alvo, ref, combos, p_ref)

    def _referencia(self, alvo: JanelaAlvo) -> ReferenciaTerminal | None:
        pl = self.plano
        if pl is None or pl.objetivo_R is None:
            return None
        i = alvo.fronteira - self.ctx.k
        if any(i >= len(pl.energias_kWh.get(u, ())) for u in self.bats):
            return None
        ger = tuple(EstadoTerminalGerador(g, bool(pl.compromisso[g][i - 1]), 0, None) for g in self.gers)
        return ReferenciaTerminal(tuple(pl.energias_kWh[u][i] for u in self.bats), ger, None, "plano_longo")

    def _sinal_cauda_vazia(self, alvo, ref):
        """b >= fim do planejamento: V^tail = Φ_L (exato, sem resolver), modo não condicionado."""
        cp = self.ctx.cfg_plan
        t = cp.termo_longo
        if cp.tipo_sinal in ("referencia_energia_dura", "referencia_energia_branda"):
            if ref is None:
                return self._indisponivel(alvo, "plano longo sem referência", None)
            return self._montar(alvo, (), ref, None, QualidadeSinal("valido", "referência (cauda vazia)", None,
                                                                    cp.tolerancia_interpolacao_R, None, 0, ()))
        lo = [self.lim[u][0] for u in self.bats]
        hi = [self.lim[u][1] for u in self.bats]
        if t.tipo == "energia_minima_declarada":
            em = {p.uid: p.valor for p in t.energias_minimas}
            lo = [max(lo[i], em[u]) for i, u in enumerate(self.bats)]
        dim = len(self.bats)
        cantos = [()]
        for i in range(dim):
            cantos = [c + (v,) for c in cantos for v in sorted({lo[i], hi[i]})]
        pts = []
        for x in cantos:
            v = valor_termo_declarado(t, dict(zip(self.bats, x)))
            pts.append(PontoValor(tuple(x), float(v), float(v), "phi_l_declarado"))
        if cp.tipo_sinal == "valor_marginal_local":
            e0 = tuple(lo)
            v0 = valor_termo_declarado(t, dict(zip(self.bats, e0)))
            lam = tuple(p.valor for p in t.lineares) if t.tipo == "valor_linear_declarado" else tuple(0.0 for _ in e0)
            if t.tipo == "valor_linear_declarado":
                lm = {p.uid: p.valor for p in t.lineares}
                lam = tuple(lm[u] for u in self.bats)
            sl = SensibilidadeLocal(0, e0, 0.0, e0, tuple(hi), float(v0), (), (), lam, "phi_l_declarado_exato")
            modo = ModoValor(0, (), "linear_local", (PontoValor(e0, float(v0), float(v0), "phi_l_declarado"),), (),
                             tuple(lo), tuple(hi), True)
            return self._montar(alvo, (modo,), ref, sl, QualidadeSinal("valido", "cauda vazia: Φ_L exato", 0.0,
                                                                       cp.tolerancia_interpolacao_R, 0.0, 0, ()))
        rep = {0: "constante_0d", 1: "intervalos_consecutivos_1d"}.get(dim, "envoltoria_convexa_nd")
        if dim == 0:
            pts = [PontoValor((), 0.0, 0.0, "phi_l_declarado")]
        modo = ModoValor(0, (), rep, tuple(pts), (), tuple(lo), tuple(hi), True)
        return self._montar(alvo, (modo,), ref, None, QualidadeSinal("valido", "cauda vazia: Φ_L exato", 0.0,
                                                                     cp.tolerancia_interpolacao_R, 0.0, 0, ()))

    def _sinal_local(self, alvo, ref, combos, p_ref):
        cp = self.ctx.cfg_plan
        if ref is None:
            return self._indisponivel(alvo, "plano longo sem solução aceita: sem estado de referência", None)
        modo_ref = tuple(EstadoTerminalGerador(x.uid, x.ligado, 0, None) for x in ref.geradores)
        cand = [m for m in combos if tuple((x.uid, x.ligado) for x in m) == tuple((x.uid, x.ligado) for x in modo_ref)]
        if not cand:
            cand = [m for m in combos if tuple(x.uid for x in m) == tuple(x.uid for x in modo_ref)]
            if len(cand) != 1:
                return self._indisponivel(alvo, "modo de referência do plano longo não admissível na fronteira", ref)
        modo = cand[0]
        b, d = alvo.fronteira, cp.delta_sensibilidade_kWh
        e0 = tuple(min(max(x, self.lim[u][0]), self.lim[u][1]) for u, x in zip(self.bats, ref.energias_kWh))
        s0, v0, lb0 = self.avaliar(b, modo, e0, p_ref)
        if s0 != "ok":
            return self._indisponivel(alvo, f"cauda no estado de referência: {s0} ({lb0})", ref)
        lam, el, eh, vl, vh = [], [], [], [], []
        for i, u in enumerate(self.bats):
            lo_, hi_ = max(self.lim[u][0], e0[i] - d), min(self.lim[u][1], e0[i] + d)
            xl = tuple(lo_ if j == i else e0[j] for j in range(len(e0)))
            xh = tuple(hi_ if j == i else e0[j] for j in range(len(e0)))
            sl_, vl_, _ = self.avaliar(b, modo, xl, p_ref) if lo_ < e0[i] else (s0, v0, lb0)
            sh_, vh_, _ = self.avaliar(b, modo, xh, p_ref) if hi_ > e0[i] else (s0, v0, lb0)
            if sl_ != "ok" or sh_ != "ok" or hi_ - lo_ <= 0:
                return self._indisponivel(alvo, f"perturbação ±δ não factível/degenerada no banco {u}", ref)
            lam.append(-(vh_ - vl_) / (hi_ - lo_))
            el.append(lo_)
            eh.append(hi_)
            vl.append(vl_)
            vh.append(vh_)
        met = "diferenca_central" if all(abs((h - x) - (x - l)) < 1e-9 for h, x, l in zip(eh, e0, el)) \
            else "diferenca_unilateral_no_limite"
        sl = SensibilidadeLocal(0, e0, float(d), tuple(el), tuple(eh), v0, tuple(vl), tuple(vh), tuple(lam), met)
        val = []
        for i in range(len(e0)):             # validação: linear × reotimizado nos extremos do domínio (por banco)
            for x, vv in ((el[i], vl[i]), (eh[i], vh[i])):
                aprox = v0 - lam[i] * (x - e0[i])
                ee = tuple(x if j == i else e0[j] for j in range(len(e0)))
                val.append(PontoValidacao(0, ee, vv, aprox, abs(vv - aprox)))
        erro_max = max((v.erro_R for v in val), default=0.0)
        mv = ModoValor(0, modo, "linear_local", (PontoValor(e0, v0, lb0, "otimo"),), (), tuple(el), tuple(eh), True)
        estado = "valido" if erro_max <= cp.tolerancia_interpolacao_R + 1e-9 else "indisponivel"
        q = QualidadeSinal(estado, "aproximação LOCAL (diferenças de reotimizações paramétricas)" if estado == "valido"
                           else f"aproximação linear local NÃO defensável: V não linear em [E_ref − δ, E_ref + δ] (erro "
                                f"{erro_max:.6g} R$ > tolerância; quebra/descontinuidade ou não separável)",
                           erro_max, cp.tolerancia_interpolacao_R,
                           None if lb0 is None else abs(v0 - lb0), self.avaliacoes, tuple(val))
        return self._montar(alvo, (mv,), ref, sl, q)

    def _sinal_pwl(self, alvo, ref, combos, p_ref):
        """C-3C4-A02: cada estado terminal recebe um DIAGNÓSTICO (``ESTADOS_MODO``). Só um modo ``inviavel`` com
        justificativa (certificado de cobertura sobre a faixa inteira) é excluído; um modo ``dominio_indeterminado``
        ou ``indisponivel`` torna o SINAL indisponível (nenhuma alternativa possivelmente mais barata é omitida em
        silêncio). O método é CONSERVADOR: o domínio de cada modo é uma aproximação INTERNA (bissecção) e a cobertura
        depende do certificado do solver — não há afirmação de exaustividade além disso."""
        cp = self.ctx.cfg_plan
        dim = len(self.bats)
        modos, val, diag, motivos = [], [], [], []
        gap = 0.0
        faixas = tuple(self.lim[u] for u in self.bats)
        for modo in combos:
            if dim == 0:
                s, v, lb = self.avaliar(alvo.fronteira, modo, (), p_ref)
                if s == "inviavel":     # sem banco não há amostragem: a própria resolução cobre o único estado
                    diag.append(DiagnosticoModo(modo, "inviavel", "cauda inviável (estado único, sem banco: a "
                                                "resolução auditada cobre todo o domínio)", (), ("avaliacao:inviavel",)))
                    continue
                if s != "ok":
                    diag.append(DiagnosticoModo(modo, "indisponivel", f"avaliação falhou: {lb}", (), ()))
                    continue
                gap = max(gap, 0.0 if lb is None else abs(v - lb))
                diag.append(DiagnosticoModo(modo, "valido", "estado único avaliado", (), (), len(modos)))
                modos.append(ModoValor(len(modos), modo, "constante_0d", (PontoValor((), v, lb, "otimo"),), (), (), (),
                                       True))
                continue
            r = self._modo_1d(alvo, modo, p_ref) if dim == 1 else self._modo_2d(alvo, modo, p_ref)
            estado, msg, cert = r[0], r[1], r[-1]
            if estado != "valido":
                diag.append(DiagnosticoModo(modo, estado, msg, faixas, tuple(cert)))
                if estado == "inviavel":
                    motivos.append(msg)
                continue
            _, mv, vv, g, _c = r
            just = (f"domínio [{', '.join(f'{x:g}' for x in mv.dominio_min_kWh)}] – "
                    f"[{', '.join(f'{x:g}' for x in mv.dominio_max_kWh)}] kWh (aproximação interna conservadora)")
            diag.append(DiagnosticoModo(modo, "valido", just, faixas, tuple(cert), len(modos)))
            modos.append(replace(mv, indice=len(modos)))
            val += [replace(x, modo=len(modos) - 1) for x in vv]
            gap = max(gap, g)
        nao_resolvidos = [d for d in diag if d.estado in ("dominio_indeterminado", "indisponivel")]
        if nao_resolvidos:
            d = nao_resolvidos[0]
            return self._indisponivel(alvo, f"{d.estado}: modo {[(x.uid, x.ligado) for x in d.geradores]} — "
                                            f"{d.justificativa}", ref, tuple(diag))
        if not modos:
            return self._indisponivel(alvo, "nenhum estado terminal admite cauda factível (todos INVIÁVEIS com "
                                            "certificado): " + "; ".join(motivos), ref, tuple(diag))
        erro_max = max((x.erro_R for x in val), default=0.0)
        ok = erro_max <= cp.tolerancia_interpolacao_R + 1e-9
        q = QualidadeSinal("valido" if ok else "indisponivel",
                           ("PWL por reotimização paramétrica auditada (domínio = aproximação interna conservadora); "
                            + "; ".join(motivos)).strip("; ") if ok else
                           f"tolerância de interpolação não atingida com pontos_max = {cp.pontos_max} "
                           f"(erro {erro_max:.6g} R$ > {cp.tolerancia_interpolacao_R})",
                           erro_max, cp.tolerancia_interpolacao_R, gap, self.avaliacoes, tuple(val))
        return self._montar(alvo, tuple(modos), ref, None, q, tuple(diag))

    def _cobertura(self, b, modo, p_ref, faixas: tuple[tuple[float, float], ...]):
        """Certificado sobre a FAIXA inteira (energia inicial livre). ('inviavel'|'factivel'|'indeterminado', E*, cert)."""
        rot = "cobertura[" + ";".join(f"{lo:g},{hi:g}" for lo, hi in faixas) + "]"
        f = getattr(self.res, "resolver_cobertura", None)
        if f is None:
            return "indeterminado", None, f"{rot}:resolvedor_sem_certificado"
        ctx = self.ctx
        t0 = self._clock()
        est = estado_na_fronteira(ctx, b, {u: lo for u, (lo, _) in zip(self.bats, faixas)}, modo, p_ref)
        try:
            rede = entrada_rede_planejamento(ctx, b, self.fim - b, est, self.proc)
            r = f(_envolver(ctx, rede, self.proc), {u: fx for u, fx in zip(self.bats, faixas)})
        except ContratoInvalido as exc:
            r = {"classificacao": "bloqueado_validacao", "constatacoes": exc.constatacoes}
        self.avaliacoes += 1
        self.tempos["cauda_s"] += self._clock() - t0
        cl = r.get("classificacao")
        cert = f"{rot}:{cl}/{r.get('terminacao')}"
        self.detalhe.append((b, tuple((x.uid, x.ligado) for x in modo), faixas, "cobertura:" + str(cl), None))
        if cl == "inviavel":
            return "inviavel", None, cert
        if cl in ("otimo", "factivel_nao_otimo") and r.get("energias"):
            return "factivel", tuple(float(r["energias"][u]) for u in self.bats), cert
        return "indeterminado", None, cert

    def _modo_1d(self, alvo, modo, p_ref):
        """Grade + certificados de cobertura. Retorna ('valido', ModoValor, validações, gap, certificados) ou
        (estado, mensagem, certificados) com estado em {'inviavel', 'dominio_indeterminado', 'indisponivel'}."""
        cp = self.ctx.cfg_plan
        u = self.bats[0]
        lo, hi = self.lim[u]
        b = alvo.fronteira
        n = cp.pontos_iniciais
        nome = [(x.uid, x.ligado, x.obrigacao_residual_s) for x in modo]
        certs: list[str] = []
        amostras = {x: self.avaliar(b, modo, (x,), p_ref)
                    for x in ([lo + (hi - lo) * i / (n - 1) for i in range(n)] if hi > lo else [lo])}
        falha = sorted(x for x, r in amostras.items() if r[0] == "falha")
        if falha:
            return ("indisponivel", f"avaliação da cauda falhou em E = {falha[0]}: {amostras[falha[0]][2]}", certs)
        if not any(r[0] == "ok" for r in amostras.values()):
            st, Ex, cert = self._cobertura(b, modo, p_ref, ((lo, hi),))
            certs.append(cert)
            if st == "inviavel":
                return ("inviavel", f"modo {nome}: cauda inviável em TODA a faixa [{lo:g}, {hi:g}] kWh (certificado de "
                                    "cobertura do solver com energia inicial livre; não só na grade)", certs)
            if st == "indeterminado":
                return ("dominio_indeterminado", f"modo {nome}: grade sem ponto factível e certificado inconclusivo "
                                                 f"({cert})", certs)
            r = self.avaliar(b, modo, Ex, p_ref)
            if r[0] != "ok":
                return ("dominio_indeterminado", f"modo {nome}: ponto factível proposto pela cobertura E* = {Ex[0]!r} "
                                                 f"não confirmado pela resolução auditada ({r[0]})", certs)
            amostras[Ex[0]] = r
            certs.append(f"ponto_factivel_encontrado_fora_da_grade:E*={Ex[0]!r}")
        xs = sorted(amostras)
        fact = [i for i, x in enumerate(xs) if amostras[x][0] == "ok"]
        if fact != list(range(fact[0], fact[-1] + 1)):
            return ("indisponivel", f"modo {nome}: domínio factível NÃO CONEXO (ponto inviável entre pontos factíveis "
                                    "na amostra): não representável por um intervalo", certs)
        pontos = {xs[i]: amostras[xs[i]] for i in fact}
        lim_inv = {"inf": xs[fact[0] - 1] if fact[0] > 0 else None,
                   "sup": xs[fact[-1] + 1] if fact[-1] < len(xs) - 1 else None}
        for lado in ("inf", "sup"):          # bissecção da fronteira de factibilidade (aproximação INTERNA)
            a = lim_inv[lado]
            if a is None:
                continue
            z = min(pontos) if lado == "inf" else max(pontos)
            while abs(z - a) > cp.tolerancia_dominio_kWh:
                mid = (a + z) / 2
                r = self.avaliar(b, modo, (mid,), p_ref)
                if r[0] == "falha":
                    return ("indisponivel", f"avaliação da cauda falhou em E = {mid}: {r[2]}", certs)
                if r[0] == "ok":
                    z = mid
                    pontos[mid] = r
                else:
                    a = mid
            lim_inv[lado] = a
            faixa = (lo, a) if lado == "inf" else (a, hi)        # certificar que NÃO há outra componente factível
            st, Ex, cert = self._cobertura(b, modo, p_ref, (faixa,))
            certs.append(cert)
            if st == "factivel":
                return ("indisponivel", f"modo {nome}: componente factível adicional em E = {Ex[0]!r} além da "
                                        "fronteira encontrada (domínio não conexo): não representável", certs)
            if st == "indeterminado":
                return ("dominio_indeterminado", f"modo {nome}: exclusão de [{faixa[0]:g}, {faixa[1]:g}] kWh não "
                                                 f"certificada ({cert})", certs)
        inv = tuple(sorted((x,) for x in xs if amostras[x][0] == "inviavel"))
        es = sorted(pontos)
        val = []
        pend = list(zip(es, es[1:]))
        while pend:
            a, z = pend.pop(0)
            mid = (a + z) / 2
            r = self.avaliar(b, modo, (mid,), p_ref)
            if r[0] != "ok":
                return ("indisponivel", f"modo {nome}: ponto médio E = {mid} {r[0]} dentro do domínio (domínio não "
                                        "conexo/avaliação falhou)", certs)
            aprox = pontos[a][1] + (pontos[z][1] - pontos[a][1]) * 0.5
            err = abs(r[1] - aprox)
            if err > cp.tolerancia_interpolacao_R and len(pontos) < cp.pontos_max:
                pontos[mid] = r
                pend = [(a, mid), (mid, z)] + pend
            else:
                val.append(PontoValidacao(0, (mid,), r[1], aprox, err))
        es = sorted(pontos)
        pts = tuple(PontoValor((x,), pontos[x][1], pontos[x][2], "otimo") for x in es)
        conv, _ = convexidade_verificada_na_amostra(pts, 1, cp.tolerancia_interpolacao_R + 1e-9)
        gap = max((0.0 if p.limite_inferior_R is None else abs(p.valor_R - p.limite_inferior_R)) for p in pts)
        return ("valido", ModoValor(0, modo, "intervalos_consecutivos_1d", pts, inv, (es[0],), (es[-1],), conv), val,
                gap, certs)

    def _modo_2d(self, alvo, modo, p_ref):
        cp = self.ctx.cfg_plan
        n = cp.pontos_iniciais
        eixos = []
        for u in self.bats:
            lo, hi = self.lim[u]
            eixos.append([lo + (hi - lo) * i / (n - 1) for i in range(n)])
        grade = [(x, y) for x in eixos[0] for y in eixos[1]]
        b = alvo.fronteira
        av = {x: self.avaliar(b, modo, x, p_ref) for x in grade}
        nome = [(x.uid, x.ligado) for x in modo]
        certs: list[str] = []
        if any(av[x][0] == "falha" for x in grade):
            return ("indisponivel", f"modo {nome}: avaliação falhou na grade 2D", certs)
        if all(av[x][0] == "inviavel" for x in grade):
            st, Ex, cert = self._cobertura(b, modo, p_ref, tuple(self.lim[u] for u in self.bats))
            certs.append(cert)
            if st == "inviavel":
                return ("inviavel", f"modo {nome}: cauda inviável em TODA a caixa de energias (certificado de "
                                    "cobertura do solver)", certs)
            if st == "factivel":
                return ("indisponivel", f"modo {nome}: região factível em E* = {Ex!r} não contida na grade 2D (domínio "
                                        "não retangular: não suportado)", certs)
            return ("dominio_indeterminado", f"modo {nome}: grade 2D sem ponto factível e certificado inconclusivo",
                    certs)
        if any(av[x][0] == "inviavel" for x in grade):
            return ("indisponivel", f"modo {nome}: domínio 2D não retangular na grade (não suportado; declarado)", certs)
        pts = tuple(PontoValor(x, av[x][1], av[x][2], "otimo") for x in grade)
        conv, exc = convexidade_verificada_na_amostra(pts, 2, cp.tolerancia_interpolacao_R + 1e-9)
        if not conv:
            return ("indisponivel", f"modo {nome}: amostra NÃO convexa (excesso {exc:.6g} R$): envoltória convexa "
                                    "inválida", certs)
        val = []
        for i in range(n - 1):
            for j in range(n - 1):
                c = ((eixos[0][i] + eixos[0][i + 1]) / 2, (eixos[1][j] + eixos[1][j + 1]) / 2)
                r = self.avaliar(b, modo, c, p_ref)
                if r[0] != "ok":
                    return ("indisponivel", f"modo {nome}: centro {c} {r[0]}", certs)
                ap = envoltoria_convexa(pts, c)
                val.append(PontoValidacao(0, c, r[1], ap, abs(r[1] - ap)))
        gap = max((0.0 if p.limite_inferior_R is None else abs(p.valor_R - p.limite_inferior_R)) for p in pts)
        return ("valido", ModoValor(0, modo, "envoltoria_convexa_nd", pts, (), (eixos[0][0], eixos[1][0]),
                                    (eixos[0][-1], eixos[1][-1]), True), val, gap,
                certs + ["convexidade_verificada_NA_AMOSTRA (grade + centros; não é prova global)"])

    # ------------------------------------------------------------------------------------- montagem
    def _hashes(self) -> dict[str, str]:
        ctx = self.ctx
        h = {"previsao_longa": hash_previsao(ctx.previsao_longa), "instantaneo": ctx.hash_instantaneo,
             "modelo_rede": hash_entrada_3c3(ctx.modelo_rede), "estado_emissao": sha256(ctx.estado),
             "configuracao_planejador": hash_configuracao_planejador(ctx.cfg_plan),
             "termo_longo": hash_termo(ctx.cfg_plan.termo_longo),
             "resolvedor": sha256(self.res.configuracao_registro())}
        m = ctx.modelo_rede
        if m.conectado:
            orc = ctx.cfg.rotulo_informacao == "ablacao_oraculo"
            for gr in ("importacao", "exportacao"):
                p, c = selecionar_perfil_causal(ctx.cfg_rede.tarifas_decisao, gr, ctx.instante_utc, oraculo=orc)
                if p is not None and not c:
                    h[f"tarifa_{gr}"] = hash_perfil(p)
        if self.plano is not None and self.plano.hash_entrada_3c4:
            h["plano_longo"] = self.plano.hash_entrada_3c4
        return h

    def _montar(self, alvo: JanelaAlvo, modos, ref, sl, q, diag=()) -> SinalValorFuturo:
        ctx = self.ctx
        cp = ctx.cfg_plan
        ident = ctx.cfg.identidade
        return selar_sinal(SinalValorFuturo(
            ESQUEMA_3C4, FORMULACAO_3C4, cp.tipo_sinal, ident.missao_uid, ident.microrrede_uid, ident.cenario_uid,
            alvo.indice_janela, alvo.k, instante_fronteira(ctx.cfg.malha, alvo.k), ctx.instante_utc, alvo.fronteira,
            instante_fronteira(ctx.cfg.malha, alvo.fronteira), max(self.fim, alvo.fronteira),
            max(0, self.fim - alvo.fronteira), self.bats, self.gers, "R$", "kWh", CONVENCAO_SINAIS, tuple(modos), ref,
            sl, cp.penalidade_branda_R_kWh if cp.tipo_sinal == "referencia_energia_branda" else None, cp.termo_longo,
            q, self._hashes(), self.proc, diagnostico_modos=tuple(diag)))

    def _indisponivel(self, alvo, motivo: str, ref, diag=()) -> SinalValorFuturo:
        cp = self.ctx.cfg_plan
        return self._montar(alvo, (), ref, None, QualidadeSinal("indisponivel", motivo, None,
                                                                cp.tolerancia_interpolacao_R, None, self.avaliacoes, ()),
                            diag)


def planejar(ctx: ContextoPlanejamento, resolvedor, *, relogio=time.perf_counter) -> ResultadoPlanejamento:
    """Executa o planejamento em τ_k: plano longo + um sinal por janela-alvo (lote)."""
    t0 = relogio()
    p = Planejador3C4(ctx, resolvedor, relogio)
    c: list[Constatacao] = []
    pl = p.plano_longo()
    if pl.objetivo_R is None:
        c.append(aviso("plano_longo_sem_solucao", "planejador.plano_longo",
                       f"{pl.classificacao}/{pl.estado_despacho}: {list(pl.codigos)[:4]}"))
    sinais = {}
    for a in ctx.alvos:
        sinais[a.indice_janela] = p.sinal(a)
    tempos = {**p.tempos, "total_s": relogio() - t0}
    return ResultadoPlanejamento(sinais, pl, p.avaliacoes, tempos, c, list(p.detalhe))


def alvos_do_lote(cfg, k: int, indice_janela: int, periodo: int) -> tuple[JanelaAlvo, ...]:
    """Janelas do cronograma nominal a partir de (k, j): P janelas (se todo bloco for integralmente aplicado)."""
    from ..mpc.relogio import janela_em
    out, kk, j = [], k, indice_janela
    while len(out) < periodo and kk < cfg.malha.intervalos_missao:
        jan = janela_em(cfg, j, kk)
        out.append(JanelaAlvo(j, kk, jan.N_k))
        kk, j = kk + jan.m_k, j + 1
    return tuple(out)


def instante_mais(inicio_utc: str, segundos: int) -> str:
    return (ler_instante_utc(inicio_utc, "t")[0] + timedelta(seconds=segundos)).isoformat()


__all__ = ["ContextoPlanejamento", "JanelaAlvo", "Planejador3C4", "ResolvedorPlanejador3C4", "ResultadoPlanejamento",
           "ResumoPlanoLongo", "alvos_do_lote", "entrada_rede_planejamento", "estado_na_fronteira",
           "horizonte_longo_em", "planejar", "rampa_inativa_na_fronteira"]
