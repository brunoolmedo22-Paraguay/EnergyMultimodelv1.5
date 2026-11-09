"""Orquestrador do MPC de horizonte recedente (3C-2, M23). Só biblioteca padrão.

``ControladorMPC`` implementa o ciclo para cada τ_k (determinístico e testável passo a passo):

1. **decidir** — sela o corte informacional τ_k no livro K6 e obtém o ``InstantaneoInformacional``; exige o estado
   EXECUTADO e conciliado em τ_k (nunca o terminal planejado); pede ao provedor declarado uma previsão própria da
   janela (só com o instantâneo) e a valida (causalidade, cobertura, UIDs, vínculo, independência); monta a entrada
   3C-1 (``janela.montar_entrada_janela``); resolve pelo ADAPTADOR (``ResolvedorJanela``); aplica a política de
   aceitação; cria o plano (``plano_de_resultado_3c1``) e EMITE os m_k comandos (``ComandoIntervalo``);
2. **receber** — confirmações (``ConfirmacaoAcao``) e observações (``Observacao`` → livro append-only);
3. **conciliar(T)** — sela o corte T; só intervalos com confirmação ``aplicada`` recebida até T e observações
   obrigatórias no instantâneo de T são reconstruídos, pelo contrato 3C-0 ``executar``/``retomar`` com o executor
   algébrico 3C-1 e uma realização ``incremental_online`` (barreira C-02 intacta: falta de observação ⇒ pausa);
4. **fechar** — janela integralmente aplicada ⇒ registros selados (3C-0 + anexo 3C-1 + ``RegistroJanelaMPC``
   encadeado), estado/memória transportados, contador global avança m_k.

Falhas são CLASSIFICADAS (``contrato.CLASSES_FALHA``) e tratadas pela política declarada (interromper/suspender): nenhuma
solução sem incumbente, rejeitada pelo auditor/integridade, fora da política, de estado não reconstruível ou com dados
inválidos vira despacho; não há plano de reserva nem reaproveitamento do plano anterior.

``executar_missao_simulada`` é o laço do MODO 1 (planta algébrica encapsulada): comandos → recibos → entregas em
ordem de recepção → conciliação. No MODO 2 (preparação online) os mesmos métodos são chamados pelo operador do ensaio.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from ..compromisso.contrato import EntradaCommitment3C1, hash_entrada_3c1, validar_entrada_3c1
from ..diagnostics import Constatacao, ContratoInvalido, aviso, erro
from ..ponte import CONTRATO_VERSAO
from ..ponte.canonico import sha256
from ..ponte.cenario import ConjuntoPrevisao, Realizacao, SerieRecurso, hash_previsao
from ..ponte.compromisso import (ExecutorAlgebricoCommitment3C1, contabilidade_realizada_3c1, estado_inicial_3c1,
                                 hash_plano_commitment, memorias_do_estado, plano_de_resultado_3c1,
                                 validar_fontes_disponibilidade)
from ..ponte.execucao import (EstadoMicrorrede, TrajetoriaExecutada, executar, hash_plano, verificar_checkpoint)
from ..ponte.instrumentacao import classificar_desfecho
from ..ponte.registro import (ComponenteCusto, CustoRealizado, Discretizacao, RegistroExecucaoEMS, ResumoSolver,
                              selar_registro, valor_futuro_nao_implementado)
from ..ponte.registro_3c1 import hashes_para_registro_3c1, montar_anexo_3c1, preparar_conteudo_anexo_3c1
from ..provenance import Procedencia
from ..series import SerieTemporal
from ..timegrid import ler_instante_utc
from . import ESQUEMA_MPC, MPC_VERSAO
from .contrato import ConfiguracaoMPC, avaliar_aceitacao, hash_configuracao, validar_configuracao_mpc
from .entorno import ComandoIntervalo, ConfirmacaoAcao, hash_comando
from .janela import montar_entrada_janela, verificar_identidade
from .observacoes import GRANDEZAS_OBSERVAVEIS, LivroObservacoes, Observacao, realizacao_de_instantaneo
from .previsao import PedidoPrevisao, chaves_de_previsao, validar_previsao_janela
from .registro import (ConteudoJanelaMPC, ConteudoMissaoMPC, CustosJanela, PassoExecutado, RegistroMissaoMPC,
                       ResumoResolucaoJanela, RevisaoTardia, custo_acumulado, genese_cadeia, montar_registro_janela,
                       selar)
from .relogio import JanelaMPC, RelogioMissao, instante_fronteira

SITUACOES_MISSAO = ("em_andamento", "interrompida", "suspensa", "encerrada")


@dataclass(frozen=True)
class DecisaoJanela:
    janela: JanelaMPC
    hash_plano: str
    comandos: tuple[ComandoIntervalo, ...]


@dataclass
class _Aberta:
    jan: JanelaMPC
    t_decisao: str
    inst_hash: str
    inst_n: int
    prev: ConjuntoPrevisao
    e3: EntradaCommitment3C1
    res: object
    categoria: str
    just: str
    plano: object
    pc: object
    comandos: tuple[ComandoIntervalo, ...]
    execucao_uid: str
    estado_inicial: EstadoMicrorrede
    estado_atual: EstadoMicrorrede
    cursor: int = 0
    ultimo_cp: object = None
    partes: list = field(default_factory=list)
    passos: list = field(default_factory=list)
    conciliacoes: list = field(default_factory=list)
    confirmacoes: list = field(default_factory=list)
    tempos: dict = field(default_factory=dict)
    constatacoes: list = field(default_factory=list)


@dataclass
class ResultadoMissaoMPC:
    configuracao: ConfiguracaoMPC
    registros: tuple
    registro_missao: RegistroMissaoMPC | None
    livro: LivroObservacoes
    confirmacoes: tuple
    comandos: tuple
    registros_3c0: tuple
    anexos_3c1: tuple
    situacao: str
    classe_falha: str | None
    entorno: dict = field(default_factory=dict)          # preenchido pelo laço simulado APÓS a missão (auditoria)
    trajetorias: tuple = ()


def _num(v) -> float | None:
    """Número finito ou None (tempos relatados por terceiros podem não ser numéricos)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if math.isfinite(float(v)) else None


def _tempos(d: dict) -> dict[str, float]:
    return {k: _num(v) for k, v in sorted(d.items()) if _num(v) is not None}


def _agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ambiente_execucao(registros=()) -> dict:
    """Hardware/versões do ambiente da execução (as estatísticas de tempo só valem para ele)."""
    import os
    import platform
    vs = next((json.loads(r.conteudo.resolucao.versoes_ambiente_json) for r in registros
               if r.conteudo.resolucao is not None), {})
    return {"python": platform.python_version(), "plataforma": platform.platform(), "cpus": os.cpu_count(),
            "processador": platform.processor() or platform.machine(), "solver": vs}


def chaves_conciliacao(modelo: EntradaCommitment3C1, fontes: dict) -> tuple[tuple[str, str], ...]:
    """Observações OBRIGATÓRIAS para reconstruir um intervalo com o executor 3C-1 (nunca presumidas)."""
    b = modelo.base
    ch = [(str(d.uid), "potencia") for d in b.demandas]
    ch += [x for r in b.renovaveis for x in ((str(r.uid), "potencia"), (str(r.uid), "disponibilidade"))]
    ch += [(str(g.uid), "disponibilidade") for g in b.geradores if fontes[str(g.uid)].fonte == "observada"]
    return tuple(sorted(ch))


def _juntar(partes: list[TrajetoriaExecutada], uid: str, hp: str, ex: str, estado0) -> TrajetoriaExecutada:
    if not partes:
        return TrajetoriaExecutada(uid, hp, ex, 0, 0, "concluida", (estado0,), (), (), (), ())
    est = [partes[0].estados[0]]
    for p in partes:
        est += list(p.estados[1:])
    return TrajetoriaExecutada(uid, hp, ex, partes[0].cursor_inicial, partes[-1].cursor_final, partes[-1].situacao,
                               tuple(est), tuple(x for p in partes for x in p.passos),
                               tuple(x for p in partes for x in p.desvios), tuple(x for p in partes for x in p.checkpoints),
                               tuple(x for p in partes for x in p.constatacoes))


def _realizacao_de_valores(linhas: list[dict], chaves, inicio_utc: str, delta_s: int, proc: Procedencia,
                           uid: str) -> Realizacao:
    series = []
    if linhas:
        for (r, g) in chaves:
            s = SerieTemporal(g, GRANDEZAS_OBSERVAVEIS[g], "media_intervalo", inicio_utc, delta_s,
                              tuple(float(x[f"{r}|{g}"]) for x in linhas), proc,
                              fronteira="barramento_liquido" if g == "potencia" else None)
            series.append(SerieRecurso(r, g, s))
    return Realizacao(uid, "sintetica", tuple(series), proc)


def _realizacao_da_previsao(prev: ConjuntoPrevisao) -> Realizacao:
    """A previsão vista como 'entorno' do plano (só para o custo PLANEJADO do prefixo aplicado)."""
    return Realizacao(f"prev-como-entorno-{hash_previsao(prev)[:16]}", "sintetica",
                      tuple(replace(s, serie=replace(s.serie, emissao_utc=None)) for s in prev.series), prev.procedencia)


def _com_base(c: CustoRealizado | None, base: str) -> CustoRealizado | None:
    if c is None:
        return None
    return CustoRealizado(tuple(replace(x, base=base) for x in c.componentes), c.total_R, c.intervalos)


def _resumo(res, resolvedor) -> ResumoResolucaoJanela | None:
    if res is None:
        return None
    aud = getattr(res, "auditoria", None)
    amb = getattr(res, "ambiente", None) or {}
    vers = {"versoes": amb.get("versoes"), "versao_highs": amb.get("versao_highs"), "interface": amb.get("interface")}

    def f(x):
        return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x)) else None
    return ResumoResolucaoJanela(
        getattr(resolvedor, "identificador", "?"), getattr(res, "classificacao", None),
        getattr(res, "estado_despacho", None), bool(getattr(res, "aceito", False)), getattr(res, "terminacao", None),
        getattr(res, "status_solucao", None), f(getattr(res, "objetivo", None)), f(getattr(res, "limite_dual", None)),
        f(getattr(res, "gap_abs", None)), f(getattr(res, "gap_rel", None)), getattr(res, "hash_entrada", None),
        {k: int(v) for k, v in (getattr(res, "tamanho", None) or {}).items()},
        getattr(res, "garantia_permanencia", None),
        {k: int(v) for k, v in (getattr(res, "obrigacoes_residuais_s", None) or {}).items()},
        {k: {kk: int(vv) for kk, vv in v.items()} for k, v in (getattr(res, "eventos", None) or {}).items()},
        tuple(sorted(aud.familias_reprovadas())) if aud is not None else (),
        tuple(sorted(res.codigos())) if hasattr(res, "codigos") else (),
        json.dumps(getattr(res, "configuracao", None) or {}, sort_keys=True, default=str),
        json.dumps(vers, sort_keys=True, default=str))


class ControladorMPC:
    def __init__(self, cfg: ConfiguracaoMPC, modelo: EntradaCommitment3C1, provedor, resolvedor, fontes_disponibilidade:
                 dict, *, livro: LivroObservacoes | None = None, estado_inicial: EstadoMicrorrede | None = None,
                 identificadores_verdade=(), fontes_verdade=(), relogio=time.perf_counter, diretorio=None,
                 _registros=(), _confirmacoes=(), _comandos=(), _k: int = 0, _j: int = 0):
        c = validar_configuracao_mpc(cfg)
        c += [x for x in validar_entrada_3c1(modelo).constatacoes if x.severidade != "aviso"]
        c += verificar_identidade(cfg, modelo, estado_inicial)
        c += validar_fontes_disponibilidade(modelo, fontes_disponibilidade)
        bloq = [x for x in c if x.severidade != "aviso"]
        if bloq:
            raise ContratoInvalido(bloq)
        if modelo.base.malha.delta_s != cfg.malha.delta_s:
            raise ContratoInvalido([erro("delta_divergente", "modelo.base.malha", "Δ do modelo ≠ Δ da missão.")])
        self.cfg, self.modelo, self.provedor, self.resolvedor = cfg, modelo, provedor, resolvedor
        self.fontes = dict(fontes_disponibilidade)
        self.id_verdade, self.fontes_verdade = tuple(identificadores_verdade), tuple(fontes_verdade)
        self._clock, self.diretorio = relogio, diretorio
        ident = cfg.identidade
        rec = {}
        for k_ in chaves_de_previsao(modelo):
            rec.setdefault(k_.recurso_uid, set()).add(k_.grandeza)
        self.livro = livro or LivroObservacoes(ident.missao_uid, ident.microrrede_uid,
                                               {k: tuple(sorted(v)) for k, v in rec.items()})
        if (self.livro.missao_uid, self.livro.microrrede_uid) != (ident.missao_uid, ident.microrrede_uid):
            raise ContratoInvalido([erro("identidade_divergente", "livro", "Livro de outra missão/microrrede.")])
        self.estado = estado_inicial if estado_inicial is not None else estado_inicial_3c1(modelo)
        self.relogio = RelogioMissao(cfg, k=_k, indice_janela=_j)
        if self.estado.indice_fronteira != _k or ler_instante_utc(self.estado.instante_utc, "e")[0] != \
                ler_instante_utc(instante_fronteira(cfg.malha, _k), "t")[0]:
            raise ContratoInvalido([erro("estado_dessincronizado", "estado", "Estado inicial ≠ fronteira τ_k da missão.")])
        self.registros: list = list(_registros)
        self.registros_3c0: list = []
        self.anexos_3c1: list = []
        self.trajetorias: list = []
        self._conf: dict[str, ConfirmacaoAcao] = {sha256(x): x for x in _confirmacoes}
        self._conf_por_cmd: dict[str, ConfirmacaoAcao] = {x.hash_comando: x for x in _confirmacoes}
        self._comandos: list[ComandoIntervalo] = list(_comandos)
        self._aberta: _Aberta | None = None
        self.situacao, self.classe_falha = "em_andamento", None
        self._revisoes_pendentes: list[RevisaoTardia] = []
        self._g_conciliado = _k
        self._visto = len(self.livro.entradas)
        self._tempos_missao: dict[str, float] = {}
        self.chaves_conc = chaves_conciliacao(modelo, self.fontes)
        self._constatacoes_missao: list[Constatacao] = []
        self._falha_pendente: tuple[str, str] | None = None

    # ------------------------------------------------------------------------------------------- utilidades
    @property
    def k(self) -> int:
        return self.relogio.k

    @property
    def instante_atual(self) -> str:
        return self.relogio.instante_utc

    @property
    def janela_aberta(self) -> JanelaMPC | None:
        return None if self._aberta is None else self._aberta.jan

    def _t(self, nome: str, t0: float) -> float:
        dt = self._clock() - t0
        self._tempos_missao[nome] = self._tempos_missao.get(nome, 0.0) + dt
        return dt

    def _uid_execucao(self, posicao: int) -> str:
        return sha256({"missao": self.cfg.identidade.missao_uid, "posicao": posicao})[:32]

    # ------------------------------------------------------------------------------------------- recepção
    def receber(self, eventos) -> list:
        out = []
        for ev in eventos:
            if isinstance(ev, Observacao):
                out.append(self.livro.registrar(ev))
            elif isinstance(ev, ConfirmacaoAcao):
                out.append(self._receber_confirmacao(ev))
            else:
                self._constatacoes_missao.append(aviso("evento_desconhecido_ignorado", "receber", type(ev).__name__))
        self._examinar_revisoes()
        return out

    def _receber_confirmacao(self, c: ConfirmacaoAcao) -> str:
        if c.missao_uid != self.cfg.identidade.missao_uid:
            return "rejeitada_outra_missao"
        cmds = {hash_comando(x): x for x in self._comandos}
        cmd = cmds.get(c.hash_comando)
        if cmd is None:
            return "rejeitada_comando_desconhecido"
        fim = ler_instante_utc(cmd.inicio_utc, "c")[0] + timedelta(seconds=self.cfg.malha.delta_s)
        tr, cr = ler_instante_utc(c.recebido_utc, "r")
        if cr or tr < fim or c.indice_global != cmd.indice_global:
            return "rejeitada_invalida"
        ant = self._conf_por_cmd.get(c.hash_comando)
        if ant is not None:
            if ant == c:
                return "duplicata_identica"
            self._falha_pendente = ("integridade", "Confirmações contraditórias para o mesmo comando.")
            return "rejeitada_contraditoria"
        self._conf_por_cmd[c.hash_comando] = c
        self._conf[sha256(c)] = c
        return "aceita"

    def _examinar_revisoes(self) -> None:
        ent = self.livro.entradas
        lim = ler_instante_utc(instante_fronteira(self.cfg.malha, self._g_conciliado), "g")[0]
        for e in ent[self._visto:]:
            if e.classificacao in ("aceita_revisao", "aceita_original_conflitante"):
                fim = ler_instante_utc(e.observacao.fim_utc, "f")[0]
                if fim <= lim:
                    o = e.observacao
                    self._revisoes_pendentes.append(RevisaoTardia(e.posicao, o.evento_uid, o.recurso_uid, o.grandeza,
                                                                  o.inicio_utc, o.recebido_utc, e.classificacao,
                                                                  self.cfg.politica_revisao_tardia))
        self._visto = len(ent)

    # ------------------------------------------------------------------------------------------- decisão
    def decidir(self) -> DecisaoJanela | None:
        if self.situacao != "em_andamento":
            raise ContratoInvalido([erro("missao_nao_ativa", "decidir", f"Situação {self.situacao!r}.")])
        if self._aberta is not None:
            raise ContratoInvalido([erro("janela_aberta", "decidir", "Conciliar/fechar a janela aberta antes.")])
        if self.relogio.encerrado:
            raise ContratoInvalido([erro("missao_completa", "decidir", "K_M intervalos já aplicados.")])
        t_ini = self._clock()
        jan = self.relogio.janela_atual()
        tk = jan.inicio_utc
        pend, self._falha_pendente = self._falha_pendente, None
        if pend:
            return self._falhar_sem_plano(jan, tk, None, pend[0], pend[1])
        if self.cfg.politica_revisao_tardia == "interromper" and self._revisoes_pendentes:
            return self._falhar_sem_plano(jan, tk, None, "revisao_tardia",
                                          f"{len(self._revisoes_pendentes)} revisão(ões) de intervalo(s) já conciliado(s).")
        try:
            self.livro.selar_corte(tk)
        except ContratoInvalido as exc:
            return self._falhar_sem_plano(jan, tk, None, "integridade", str(exc))
        inst = self.livro.instantaneo(tk)
        e_t = ler_instante_utc(self.estado.instante_utc, "e")[0]
        if self.estado.indice_fronteira != jan.k or e_t != ler_instante_utc(tk, "t")[0]:
            return self._falhar_sem_plano(jan, tk, inst, "estado_nao_reconstruivel",
                                          f"Estado conciliado em k = {self.estado.indice_fronteira}; decisão em k = {jan.k}.")
        malha_j = jan.malha(self.cfg.malha)
        pedido = PedidoPrevisao(self.cfg.identidade.missao_uid, self.cfg.identidade.microrrede_uid, jan.indice_janela,
                                jan.k, tk, self.cfg.malha.delta_s, jan.N_k, self._chaves_previsao(), inst)
        t0 = self._clock()
        try:
            prev = self.provedor.emitir(pedido)
        except Exception as exc:  # noqa: BLE001 — exceção do provedor vira falha classificada
            return self._falhar_sem_plano(jan, tk, inst, "previsao_invalida", f"{type(exc).__name__}: {exc}")
        cp = validar_previsao_janela(prev, pedido, malha_j, provedor_id=self.provedor.identificador,
                                     provedor_natureza=self.provedor.natureza,
                                     rotulo_informacao=self.cfg.rotulo_informacao,
                                     identificadores_verdade=self.id_verdade, fontes_verdade=self.fontes_verdade)
        t_prev = self._t("previsao", t0)
        if cp:
            return self._falhar_sem_plano(jan, tk, inst, "previsao_invalida", "; ".join(
                f"[{x.codigo}] {x.caminho}" for x in cp[:6]), prev=prev, constat=cp)
        proc = Procedencia("sintetico", f"MPC {MPC_VERSAO} missão {self.cfg.identidade.missao_uid}",
                           f"janela {jan.indice_janela}", observacoes="estado EXECUTADO e conciliado (não o planejado)")
        t0 = self._clock()
        try:
            e3 = self._montar_entrada_janela(jan, prev, inst.hash, proc)
        except ContratoInvalido as exc:
            cl = "identidade_divergente" if any("identidade" in x or "outra_microrrede" in x for x in exc.codigos) \
                else "bloqueado_validacao"
            return self._falhar_sem_plano(jan, tk, inst, cl, str(exc), prev=prev, constat=list(exc.constatacoes))
        rel = self._validar_entrada_janela(e3)
        if not rel.aceito:
            return self._falhar_sem_plano(jan, tk, inst, "bloqueado_validacao", "Entrada da janela recusada.",
                                          prev=prev, constat=list(rel.bloqueantes()))
        he = self._hash_entrada(e3)
        t_ent = self._t("entrada", t0)
        t0 = self._clock()
        try:
            res = self.resolvedor.resolver(e3, None)
        except Exception as exc:  # noqa: BLE001
            return self._falhar_sem_plano(jan, tk, inst, "falha_solver", f"{type(exc).__name__}: {exc}", prev=prev, he=he)
        t_res = self._t("resolucao", t0)
        if getattr(res, "aceito", False) and (getattr(res, "hash_entrada", None) != he or
                                             getattr(res, "microrrede_uid", None) != self.cfg.identidade.microrrede_uid
                                             or getattr(res, "cenario_uid", None) != self.cfg.identidade.cenario_uid):
            return self._falhar_sem_plano(jan, tk, inst, "integridade", "Resultado de outra entrada/microrrede/cenário.",
                                          prev=prev, he=he, res=res)
        dec = avaliar_aceitacao(res, self.cfg.politica_aceitacao)
        if not dec.aceito:
            return self._falhar_sem_plano(jan, tk, inst, dec.categoria, dec.justificativa, prev=prev, he=he, res=res)
        try:
            plano, pc = self._plano_de_resultado(res, e3, jan.k)
        except ContratoInvalido as exc:
            return self._falhar_sem_plano(jan, tk, inst, "integridade", str(exc), prev=prev, he=he, res=res)
        hp = hash_plano(plano)
        t0g = ler_instante_utc(tk, "t")[0]
        d = timedelta(seconds=self.cfg.malha.delta_s)
        cmds = tuple(ComandoIntervalo(self.cfg.identidade.missao_uid, jan.indice_janela, jan.k + i,
                                      (t0g + i * d).isoformat(), hp, i,
                                      self._consignas_comando(plano, pc, i), tk)
                     for i in range(jan.m_k))
        self._comandos += list(cmds)
        pos = len(self.registros)
        self._aberta = _Aberta(jan, tk, inst.hash, inst.n_entradas, prev, e3, res, dec.categoria, dec.justificativa,
                               plano, pc, cmds, self._uid_execucao(pos), self.estado, self.estado,
                               tempos={"previsao_s": t_prev, "entrada_s": t_ent, "resolucao_total_s": t_res,
                                       **{f"solver_{k}": v for k, v in _tempos(getattr(res, "tempos_s", None) or {}).items()}})
        if self._revisoes_pendentes:
            self._aberta.constatacoes.append(aviso("revisao_tardia_registrada_sem_reconciliar", "livro",
                                                   f"{len(self._revisoes_pendentes)} revisão(ões) tardia(s) registrada(s);"
                                                   " estado e decisões passadas não reescritos."))
        self._aberta.tempos["decisao_total_s"] = self._clock() - t_ini
        return DecisaoJanela(jan, hp, cmds)

    # ------------------------------------------------------------------------------------------- conciliação
    def conciliar(self, instante_utc: str) -> str:
        """Reconstrói os intervalos confirmados e observados até ``instante_utc``. Devolve ``concluida`` (janela
        fechada), ``aguardando_observacoes``, ``aguardando_confirmacoes`` ou a classe de falha (janela fechada)."""
        ab = self._aberta
        if ab is None:
            raise ContratoInvalido([erro("sem_janela_aberta", "conciliar", "Nenhuma janela aberta.")])
        t0 = self._clock()
        pend, self._falha_pendente = self._falha_pendente, None
        if pend:
            return self._fechar(pend[0], pend[1])
        try:
            self.livro.selar_corte(instante_utc)
        except ContratoInvalido as exc:
            return self._fechar("integridade", str(exc))
        inst = self.livro.instantaneo(instante_utc)
        ab.conciliacoes.append((ler_instante_utc(instante_utc, "c")[0].isoformat(), inst.hash, inst.n_entradas))
        tT = ler_instante_utc(instante_utc, "c")[0]
        n_conf, rej = 0, None
        for cmd in ab.comandos:
            cf = self._conf_por_cmd.get(hash_comando(cmd))
            if cf is None or ler_instante_utc(cf.recebido_utc, "r")[0] > tT:
                break
            if cf.situacao != "aplicada":
                rej = cf
                break
            n_conf += 1
        ro = realizacao_de_instantaneo(inst, self.chaves_conc, ab.jan.inicio_utc, n_conf, self.cfg.malha.delta_s)
        n_exec = n_conf - ab.cursor
        if n_exec > 0:
            ex = self._executor_conciliacao(ab, f"conciliacao-{ab.execucao_uid[:8]}", conciliacao=True)
            try:
                traj = executar(ab.plano, ab.estado_atual, ex, ro.realizacao, execucao_uid=ab.execucao_uid,
                                intervalos=n_exec, cursor=ab.cursor, checkpoint_anterior=ab.ultimo_cp)
            except ContratoInvalido as exc:
                return self._fechar("integridade", str(exc))
            ab.partes.append(traj)
            for p in traj.passos:
                ab.passos.append(PassoExecutado(ab.jan.k + p.indice_plano, p.indice_plano, dict(p.aplicado),
                                                dict(sorted(ro.valores[p.indice_plano].items()))))
                cf = self._conf_por_cmd[hash_comando(ab.comandos[p.indice_plano])]
                ab.confirmacoes.append(sha256(cf))
            ab.cursor += len(traj.passos)
            ab.ultimo_cp = traj.checkpoints[-1]
            ab.estado_atual = traj.estados[-1]
            self._g_conciliado = ab.jan.k + ab.cursor
            ab.tempos["conciliacao_s"] = ab.tempos.get("conciliacao_s", 0.0) + (self._clock() - t0)
            if traj.situacao == "erro_dados":
                ab.constatacoes += list(traj.constatacoes)
                return self._fechar("erro_dados", "Dados realizados/memória inválidos na conciliação.")
            if traj.situacao == "interrompida_inexequivel":
                ab.constatacoes += list(traj.constatacoes)
                return self._fechar("integridade", "Entorno confirmou 'aplicada', mas a conciliação com as observações "
                                                   "recebidas é inexequível (confirmação × conciliação divergentes).")
            if traj.situacao == "pausada_aguardando_observacoes":
                ab.constatacoes.append(aviso("conciliacao_pausada_C02", "conciliacao",
                                             f"{len(ro.faltantes)} observação(ões) obrigatória(s) ausente(s)/conflitante(s)."))
        if rej is not None and ab.cursor == n_conf:
            ab.constatacoes.append(erro("consigna_recusada_pelo_entorno", f"intervalo[{rej.indice_global}]",
                                        f"{rej.situacao}: {'; '.join(rej.detalhe)}"))
            cl = {"rejeitada_dados": "erro_dados", "rejeitada_protocolo": "integridade"}.get(rej.situacao,
                                                                                            "consigna_inexequivel")
            return self._fechar(cl, f"Entorno recusou o comando do intervalo {rej.indice_global} ({rej.situacao}).")
        if ab.cursor == ab.jan.m_k:
            return self._fechar(None, "Janela integralmente aplicada e conciliada.")
        return "aguardando_observacoes" if ab.cursor < n_conf else "aguardando_confirmacoes"

    def faltantes_atuais(self, instante_utc: str):
        ab = self._aberta
        if ab is None:
            return ()
        n = len(ab.comandos)
        return realizacao_de_instantaneo(self.livro.instantaneo(instante_utc), self.chaves_conc, ab.jan.inicio_utc, n,
                                         self.cfg.malha.delta_s).faltantes

    def falhar_janela_aberta(self, classe: str, motivo: str) -> str:
        """Encerra a janela aberta com a falha classificada (p. ex. estado não reconstruível no instante da próxima
        decisão no modo 1). Nenhum comando adicional é emitido."""
        if self._aberta is None:
            raise ContratoInvalido([erro("sem_janela_aberta", "falhar", "Nenhuma janela aberta.")])
        return self._fechar(classe, motivo)

    # ------------------------------------------------------------------------------------------- fechamento
    def _aplicar_politica(self, classe: str | None) -> None:
        if classe is None:
            return
        self.classe_falha = classe
        self.situacao = "suspensa" if self.cfg.politica_falhas.acoes.get(classe) == "suspender" else "interrompida"

    def _falhar_sem_plano(self, jan, tk, inst, classe, motivo, *, prev=None, constat=(), he=None, res=None):
        if inst is None:
            inst = self.livro.instantaneo(tk)
        c = list(constat) + [erro(f"falha_{classe}", "janela", motivo)]
        conteudo = ConteudoJanelaMPC(
            ESQUEMA_MPC, self.cfg.identidade.missao_uid, len(self.registros), jan, tk, inst.hash, inst.n_entradas,
            f"{getattr(self.provedor, 'identificador', '?')}:{getattr(self.provedor, 'natureza', '?')}",
            prev if isinstance(prev, ConjuntoPrevisao) else None,
            hash_previsao(prev) if isinstance(prev, ConjuntoPrevisao) else None, he, _resumo(res, self.resolvedor),
            classe, motivo, None, None, (), (), 0, 0, (), (), (self.estado,), self._cp_origem(), None, None,
            CustosJanela({k: float(v) for k, v in (getattr(res, "custos_modelo", None) or {}).items()}, None, None,
                         None), {}, tuple(self._revisoes_pendentes), "sem_plano", classe,
            tuple(x for x in c if isinstance(x, Constatacao)))
        self._aplicar_politica(classe)
        self._selar_e_gravar(conteudo, None, None, {})
        return None

    def _fechar(self, classe: str | None, motivo: str) -> str:
        ab = self._aberta
        t0 = self._clock()
        ex_id = f"conciliacao-{ab.execucao_uid[:8]}:algebrico_referencia"
        traj = _juntar(ab.partes, ab.execucao_uid, hash_plano(ab.plano), ex_id, ab.estado_inicial)
        n = len(ab.passos)
        proc = Procedencia("sintetico", f"LivroObservacoes:{self.cfg.identidade.missao_uid}",
                           f"entorno conciliado da janela {ab.jan.indice_janela}",
                           observacoes="valores efetivos usados em cada conciliação (sem imputação)")
        real = _realizacao_de_valores([p.entorno_observado for p in ab.passos], self.chaves_conc, ab.jan.inicio_utc,
                                      self.cfg.malha.delta_s, proc, f"conc-{ab.execucao_uid[:16]}")
        contab = self._contabilidade(ab, traj, real)
        planejado = None
        if n:
            try:
                rp = _realizacao_da_previsao(ab.prev)
                tp = executar(ab.plano, ab.estado_inicial, self._executor_conciliacao(
                    ab, "plano-x-previsao", conciliacao=False), rp, execucao_uid=ab.execucao_uid + "-plan",
                    intervalos=n)
                if tp.situacao == "concluida":
                    planejado = _com_base(self._contabilidade(ab, tp, rp, planejado=True).custo, "planejado_previsao")
                else:
                    ab.constatacoes.append(aviso("custo_planejado_prefixo_indisponivel", "custos", tp.situacao))
            except ContratoInvalido as exc:
                ab.constatacoes.append(aviso("custo_planejado_prefixo_indisponivel", "custos", str(exc)))
        else:
            planejado = CustoRealizado((), 0.0, 0)
        dif = None if planejado is None else contab.custo.total_R - planejado.total_R
        custos = CustosJanela({k: float(v) for k, v in ab.res.custos_modelo.items()}, planejado, contab.custo, dif)
        # registros históricos (3C-0 + anexo 3C-1): esquemas inalterados
        hashes_extra, fechar_anexo = self._artefatos_registro(ab, traj, real, contab)
        r = ab.res
        rs = ResumoSolver(r.classificacao, r.estado_despacho, r.terminacao, r.objetivo, r.limite_dual, r.gap_abs,
                          r.gap_rel, json.dumps(getattr(r, "configuracao", {}) or {}, sort_keys=True, default=str),
                          json.dumps(getattr(r, "ambiente", {}) or {}, sort_keys=True, default=str))
        des, just = classificar_desfecho(r)
        cp_final = traj.checkpoints[-1] if traj.checkpoints else None
        hashes = {"previsao": hash_previsao(ab.prev), "instantaneo_decisao": ab.inst_hash, "plano": hash_plano(ab.plano),
                  "realizacao_conciliada": sha256(real), **hashes_extra}
        reg0 = selar_registro(RegistroExecucaoEMS(
            CONTRATO_VERSAO, ab.execucao_uid, _agora_utc(), self.cfg.identidade.referencia_origem(),
            {"mpc": MPC_VERSAO, "formulacao": ab.e3.versao_formulacao, "motor": r.motor_id},
            hashes, Discretizacao(ab.jan.inicio_utc, self.cfg.malha.delta_s, ab.jan.N_k, ab.jan.m_k,
                                  self.cfg.malha.intervalos_missao),
            rs, ab.plano, ab.estado_inicial, traj.estados[-1], traj.situacao, cp_final, dict(contab.indicadores),
            contab.custo, {k: float(v) for k, v in r.custos_modelo.items()},
            valor_futuro_nao_implementado(ab.jan.k + n), des, just,
            _tempos(ab.tempos),
            tuple(x for x in ab.constatacoes if isinstance(x, Constatacao)),
            {"missao_uid": self.cfg.identidade.missao_uid, "indice_janela": str(ab.jan.indice_janela),
             "posicao": str(len(self.registros))}))
        anexo = fechar_anexo(reg0)
        self.registros_3c0.append(reg0)
        self._registrar_anexo(anexo)
        self.trajetorias.append(traj)
        desf = "executada" if (classe is None and n == ab.jan.m_k) else "executada_parcial"
        c = list(ab.constatacoes)
        if classe is not None:
            c.append(erro(f"falha_{classe}", "janela", motivo))
        conteudo = ConteudoJanelaMPC(
            ESQUEMA_MPC, self.cfg.identidade.missao_uid, len(self.registros), ab.jan, ab.t_decisao, ab.inst_hash,
            ab.inst_n, f"{self.provedor.identificador}:{self.provedor.natureza}", ab.prev, hash_previsao(ab.prev),
            self._hash_entrada(ab.e3), _resumo(r, self.resolvedor), ab.categoria, ab.just, hash_plano(ab.plano),
            self._hash_plano_complementar(ab.pc), tuple(hash_comando(x) for x in ab.comandos), tuple(ab.confirmacoes),
            len(ab.comandos), n, tuple(ab.conciliacoes), tuple(ab.passos), tuple(traj.estados), self._cp_origem(),
            cp_final.selo if cp_final else None, traj.situacao, custos, dict(contab.indicadores),
            tuple(self._revisoes_pendentes), desf, classe, tuple(x for x in c if isinstance(x, Constatacao)),
            execucao_uid=ab.execucao_uid)
        ab.tempos["fechamento_s"] = self._clock() - t0
        self._revisoes_pendentes = [] if self.cfg.politica_revisao_tardia == "registrar_sem_reconciliar" \
            else self._revisoes_pendentes
        self.estado = ab.estado_atual
        self._aberta = None
        if n:
            self.relogio.avancar(n)
        if classe is not None:
            self._aplicar_politica(classe)
        elif self.relogio.encerrado:
            self.situacao = "encerrada"
        self._selar_e_gravar(conteudo, reg0, anexo, ab.tempos)      # ponto de retomada = estado JÁ transportado
        return classe if classe is not None else "concluida"

    def _cp_origem(self) -> str | None:
        """Selo do checkpoint final da última janela EXECUTADA (vínculo explícito entre janelas; cada plano novo tem
        execução própria e nunca reaproveita checkpoints ligados ao hash de outro plano)."""
        return next((r.conteudo.selo_checkpoint_final for r in reversed(self.registros)
                     if r.conteudo.selo_checkpoint_final is not None), None)

    def _selar_e_gravar(self, conteudo, reg0, anexo, tempos) -> None:
        ant = self.registros[-1] if self.registros else None
        r = montar_registro_janela(conteudo, ant, selo_3c0=reg0.selo if reg0 else None,
                                   selo_3c1=anexo.selo if anexo else None, tempos_s=tempos, criado_utc=_agora_utc())
        self.registros.append(r)
        if self.diretorio is not None:
            from .persistencia import gravar_janela_e_retomada
            gravar_janela_e_retomada(self.diretorio, self, r, reg0, anexo)

    # ------------------------------------------------------------------------------------------- pontos de extensão
    # Piso 3C-3: pontos de extensão EXPLÍCITOS do perfil da janela. As implementações abaixo são EXATAMENTE as
    # chamadas do 3C-2 (perfil v1.1-3C-1): o comportamento, os registros e os hashes do 3C-2 não mudam (regressão
    # ``test_ems_v2_3c3_regressao_3c2.py`` compara as impressões de E1–E8 com as da base ``a4c6b1c``). Uma subclasse
    # (``ems_v2.rede.mpc.ControladorMPCConectado``) substitui SÓ estes métodos.
    def _chaves_previsao(self):
        return chaves_de_previsao(self.modelo)

    def _montar_entrada_janela(self, jan, prev, hash_instantaneo: str, proc: Procedencia):
        return montar_entrada_janela(self.modelo, self.cfg, jan, prev, self.estado, hash_instantaneo=hash_instantaneo,
                                     procedencia=proc)

    def _validar_entrada_janela(self, e):
        return validar_entrada_3c1(e)

    def _hash_entrada(self, e) -> str:
        return hash_entrada_3c1(e)

    def _plano_de_resultado(self, res, e, k: int):
        return plano_de_resultado_3c1(res, e, indice_fronteira_inicial=k)

    def _consignas_comando(self, plano, pc, i: int) -> dict[str, float]:
        return {f"{x.uid}|{x.grandeza}": float(x.valores[i]) for x in plano.consignas}

    def _executor_conciliacao(self, ab, identificador: str, *, conciliacao: bool):
        return ExecutorAlgebricoCommitment3C1(ab.e3, self.fontes, identificador=identificador)

    def _contabilidade(self, ab, traj, real, *, planejado: bool = False):
        return contabilidade_realizada_3c1(ab.e3, ab.plano, traj, real)

    def _hash_plano_complementar(self, pc) -> str:
        return hash_plano_commitment(pc)

    def _artefatos_registro(self, ab, traj, real, contab):
        """(hashes a comprometer no registro 3C-0 ANTES do selo, função registro_selado → anexo selado)."""
        conteudo_3c1 = preparar_conteudo_anexo_3c1(ab.e3, ab.plano, traj, real, self.fontes, contabilidade=contab)
        hashes = {"plano_commitment_3c1": hash_plano_commitment(ab.pc), **hashes_para_registro_3c1(conteudo_3c1)}
        return hashes, (lambda reg0: montar_anexo_3c1(reg0, conteudo_3c1))

    def _registrar_anexo(self, anexo) -> None:
        self.anexos_3c1.append(anexo)

    # ------------------------------------------------------------------------------------------- missão
    def obrigacoes_pendentes(self) -> tuple[dict[str, int], list[Constatacao]]:
        out, c = {}, []
        for mf in memorias_do_estado(self.modelo, self.estado):
            if mf.obrigacao_residual_s is None:
                c.append(aviso("memoria_nao_rastreada_no_fim", f"memoria[{mf.uid}]", "Obrigação não derivável."))
            elif mf.obrigacao_residual_s > 0:
                out[mf.uid] = int(mf.obrigacao_residual_s)
        return out, c

    def finalizar(self, *, ambiente: dict | None = None) -> RegistroMissaoMPC:
        if self._aberta is not None:
            raise ContratoInvalido([erro("janela_aberta", "finalizar", "Feche ou falhe a janela aberta antes.")])
        obr, c = self.obrigacoes_pendentes()
        if self.situacao == "encerrada":
            desf = "concluida_com_obrigacoes_pendentes" if obr else "concluida"
        elif self.situacao in ("interrompida", "suspensa"):
            desf = self.situacao
        else:
            desf = "em_andamento"
        acc = custo_acumulado(self.registros)
        plan = math.fsum(r.conteudo.custos.planejado_prefixo.total_R for r in self.registros
                         if r.conteudo.custos.planejado_prefixo is not None)
        ind: dict[str, list[float]] = {}
        for r in self.registros:
            for k, v in r.conteudo.indicadores.items():
                ind.setdefault(k, []).append(v)
        e0 = self.registros[0].conteudo.estados[0] if self.registros else self.estado
        cont = ConteudoMissaoMPC(
            ESQUEMA_MPC, self.cfg.identidade, self.cfg, hash_configuracao(self.cfg), hash_entrada_3c1(self.modelo),
            f"{self.provedor.identificador}:{self.provedor.natureza}", self.provedor.impressao(),
            json.dumps(self.resolvedor.configuracao_registro(), sort_keys=True, default=str),
            self.cfg.malha.intervalos_missao, sum(r.conteudo.intervalos_aplicados for r in self.registros),
            tuple((r.conteudo.posicao, r.conteudo.janela.indice_janela, r.hash_conteudo) for r in self.registros),
            self.registros[-1].cadeia_conteudo if self.registros else genese_cadeia(self.cfg.identidade.missao_uid),
            self.livro.hash_cadeia(), len(self.livro.entradas), self.livro.hash_cadeia_quarentena(),
            len(self.livro.quarentena), desf, self.classe_falha, e0, self.estado, acc, plan,
            {k: math.fsum(v) for k, v in sorted(ind.items())}, obr, valor_futuro_nao_implementado(self.k),
            tuple(self._constatacoes_missao + c))
        amb = {**ambiente_execucao(self.registros), **(ambiente or {})}
        rm = selar(RegistroMissaoMPC(cont, sha256(cont), tuple(r.selo for r in self.registros),
                                     dict(sorted(self._tempos_missao.items())),
                                     json.dumps(amb, sort_keys=True, default=str), _agora_utc()))
        if self.diretorio is not None:
            from .persistencia import gravar_missao
            gravar_missao(self.diretorio, rm, self.livro)
        return rm

    def resultado(self, registro_missao: RegistroMissaoMPC | None, entorno: dict | None = None) -> ResultadoMissaoMPC:
        return ResultadoMissaoMPC(self.cfg, tuple(self.registros), registro_missao, self.livro,
                                  tuple(self._conf_por_cmd.values()), tuple(self._comandos), tuple(self.registros_3c0),
                                  tuple(self.anexos_3c1), self.situacao, self.classe_falha, dict(entorno or {}),
                                  tuple(self.trajetorias))

    def comandos_aplicados(self) -> tuple[ComandoIntervalo, ...]:
        aplic = {x.hash_comando for x in self._conf_por_cmd.values() if x.situacao == "aplicada"}
        return tuple(c for c in self._comandos if hash_comando(c) in aplic)

    def retomar_suspensa(self) -> None:
        """Reativa uma missão SUSPENSA (a causa deve ter sido removida pelo operador do ensaio, p. ex. novo resolvedor).
        Exige estado conciliado na fronteira corrente; nada é reaplicado."""
        if self.situacao != "suspensa":
            raise ContratoInvalido([erro("missao_nao_suspensa", "retomar", f"Situação {self.situacao!r}.")])
        self.situacao, self.classe_falha = "em_andamento", None


def executar_missao_simulada(ctrl: ControladorMPC, entorno, *, max_janelas: int | None = None,
                             ambiente: dict | None = None, finalizar: bool = True) -> ResultadoMissaoMPC:
    """MODO 1 — laço causal: em τ_k entrega ao controlador SÓ o que foi recebido até τ_k, decide, envia os comandos ao
    entorno (que só então realiza cada intervalo), entrega o recebido até o fim do bloco e concilia. Estado não
    reconstruível no instante da próxima decisão ⇒ falha classificada (nenhum estimador é inventado)."""
    n = 0
    while ctrl.situacao == "em_andamento" and not ctrl.relogio.encerrado:
        if max_janelas is not None and n >= max_janelas:
            break
        ctrl.receber(entorno.entregar_ate(ctrl.instante_atual))
        dec = ctrl.decidir()
        n += 1
        if dec is None:
            break
        for cmd in dec.comandos:
            entorno.aplicar(cmd)
        fim = instante_fronteira(ctrl.cfg.malha, dec.janela.k + len(dec.comandos))
        ctrl.receber(entorno.entregar_ate(fim))
        s = ctrl.conciliar(fim)
        if s in ("aguardando_observacoes", "aguardando_confirmacoes"):
            falt = ctrl.faltantes_atuais(fim)
            ctrl.falhar_janela_aberta("estado_nao_reconstruivel",
                                      f"No instante da próxima decisão ({fim}) faltam confirmações/observações "
                                      f"obrigatórias ({len(falt)}: {[f'{x.recurso_uid}:{x.grandeza}[{x.indice}]' for x in falt[:6]]}).")
    rm = None
    if finalizar and (ctrl.situacao != "em_andamento" or ctrl.relogio.encerrado):
        rm = ctrl.finalizar(ambiente=ambiente)
    ent = {"identificador": getattr(entorno, "identificador", "?"), "natureza": getattr(entorno, "natureza", "?")}
    if hasattr(entorno, "impressao_verdade"):
        ent["impressao_verdade"] = entorno.impressao_verdade()
    return ctrl.resultado(rm, ent)


__all__ = ["ControladorMPC", "DecisaoJanela", "ambiente_execucao", "ResultadoMissaoMPC", "SITUACOES_MISSAO", "chaves_conciliacao",
           "executar_missao_simulada"]
_ = (verificar_checkpoint, ComponenteCusto)
