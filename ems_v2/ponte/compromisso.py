"""Integração do commitment dinâmico 3C-1 com a ponte 3C-0 (plano → execução → estado → janela seguinte).

Só biblioteca padrão. Nenhum tipo 3C-0 foi alterado (planos, estados, checkpoints e registros 3C-0 conservam o mesmo
JSON canônico e os mesmos selos); o 3C-1 acrescenta tipos PRÓPRIOS:

* ``plano_de_resultado_3c1`` — resultado 3C-1 ACEITO → ``PlanoDespacho`` (consignas u, p, …; ``hash_entrada`` = SHA-256
  da entrada 3C-1) + ``PlanoCommitment3C1`` (memória terminal PLANEJADA, obrigações residuais, garantia, eventos e
  custo de eventos PLANEJADO). Resultado rejeitado/sem despacho ⇒ ``ContratoInvalido`` (nunca vira plano);
* ``ExecutorAlgebricoCommitment3C1`` — dublê ALGÉBRICO (não físico) que, antes de delegar ao executor 3C-0, recusa
  consignas inexequíveis pelo commitment: transição com permanência mínima não cumprida (pela MEMÓRIA do estado),
  transição não representável, rampa M11 violada, unidade ON com disponibilidade EFETIVA nula. A disponibilidade de
  cada unidade vem SÓ da fonte declarada (``FonteDisponibilidadeExecucao``: ``observada`` × ``estatica_declarada``;
  A-01); observação ausente/inválida/contraditória e memória ausente ⇒ falha de DADOS (nunca presumida);
* ``memorias_do_estado`` / ``entrada_de_continuacao`` — transporte EXPLÍCITO da memória (u, p, tempo no estado,
  obrigação residual derivada) e dos estados de armazenamento de uma fronteira para a janela seguinte;
* ``custo_eventos_realizado`` / ``contabilidade_realizada_3c1`` — custos efetivamente INCORRIDOS (A-02): contabilidade
  3C-0 inalterada + H₂ (m_SU/m_SD) e C_SU/C_SD das transições APLICADAS, separados do planejado e do valor futuro;
* ``DeclaracaoCommitment3C1`` / ``montar_entrada_3c1`` — projeção inventário + cenário + declarações POR UNIDADE →
  ``EntradaCommitment3C1`` (requisitos 3C-1 bloqueantes; estado por unidade nunca distribuído de um agregado;
  declarações por unidade validadas antes de indexar — duplicatas, UIDs alheios e procedência; A-03; coerência com a
  condição AGREGADA do registro no cenário — B-01; declaração vinculada ao instantâneo inventário × versão do cenário
  por ``VinculoDeclaracao3C1`` — B-02). Evidência da execução 3C-1: ``ponte.registro_3c1`` (anexo selado).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .. import FORMULACAO_3BP, FORMULACAO_3C1
from ..audit import Tolerancias
from ..compromisso.contrato import (ESQUEMA_3C1, EntradaCommitment3C1, EspecCommitmentUnidade, MemoriaCommitmentUnidade,
                                    PoliticaPermanenciaTerminal, discretizar, hash_entrada_3c1, obrigacao_derivada_s,
                                    tempo_s_exato, validar_entrada_3c1)
from ..compromisso.memoria import MemoriaFronteira, garantia
from ..contracts import EstadoBateria, EstadoGerador, UIDRecurso
from ..diagnostics import Constatacao, ContratoInvalido, aviso, erro, pendente
from ..parameters import Parametro
from ..provenance import Procedencia
from ..timegrid import ler_instante_utc
from . import CONTRATO_VERSAO
from .canonico import sha256
from .cenario import CenarioEMS, ConjuntoPrevisao, DefinicaoTemporal, ReferenciaInventario
from .execucao import (ConsignaRecurso, EstadoMicrorrede, ExecutorAlgebricoReferencia, PassoAplicado, PlanoDespacho,
                       TrajetoriaExecutada, TrajetoriaPlanejada, hash_plano, validar_plano)
from .inventario import InventarioMicrorrede, recursos_ems
from .projecao import PoliticasDeclaradas, ResultadoProjecao, _par, montar_entrada
from .registro import ComponenteCusto


# ------------------------------------------------------------------------------------------------ plano
@dataclass(frozen=True)
class PlanoCommitment3C1:
    versao_contrato: int
    hash_plano: str                              # SHA-256 do PlanoDespacho associado
    hash_entrada_3c1: str
    politica_permanencia: str
    garantia_permanencia: str                    # compromisso.memoria.GARANTIAS
    memorias_terminais: tuple[MemoriaFronteira, ...]
    obrigacoes_residuais_s: dict[str, int]
    eventos_planejados: dict[str, dict[str, int]]
    custo_eventos_planejado_R: float | None      # termo "eventos" do OBJETIVO (não é custo incorrido)


def plano_de_resultado_3c1(res, e3: EntradaCommitment3C1, *,
                           indice_fronteira_inicial: int = 0) -> tuple[PlanoDespacho, PlanoCommitment3C1]:
    if not getattr(res, "aceito", False) or getattr(res, "despacho", None) is None:
        raise ContratoInvalido([erro("plano_de_solucao_nao_aceita", "resultado",
                                     f"Estado {getattr(res, 'estado_despacho', '?')!r}: nenhum plano é criado de solução "
                                     "não aceita (auditoria 3C-1/integridade).")])
    he = hash_entrada_3c1(e3)
    if res.hash_entrada != he or getattr(res, "versao_formulacao", None) != FORMULACAO_3C1:
        raise ContratoInvalido([erro("plano_entrada_divergente", "resultado.hash_entrada",
                                     "O resultado não corresponde à entrada 3C-1 fornecida.")])
    desp, m = res.despacho, e3.base.malha
    cons: list[ConsignaRecurso] = []
    est: list[TrajetoriaPlanejada] = []
    for uid in sorted(desp.get("renovaveis", {})):
        cons.append(ConsignaRecurso(uid, "P_R", "kW", tuple(desp["renovaveis"][uid]["P_R"])))
    for uid in sorted(desp.get("baterias", {})):
        b = desp["baterias"][uid]
        cons += [ConsignaRecurso(uid, "P_c", "kW", tuple(b["P_c"])), ConsignaRecurso(uid, "P_d", "kW", tuple(b["P_d"]))]
        est.append(TrajetoriaPlanejada(uid, "e", "kWh", tuple(b["e"])))
    for uid in sorted(desp.get("geradores", {})):
        g = desp["geradores"][uid]
        u = tuple(float(round(x)) for x in g["u"])           # binária já auditada (tolerância D07): consigna exata
        cons += [ConsignaRecurso(uid, "u", "1", u), ConsignaRecurso(uid, "p", "kW", tuple(g["p"]))]
    for uid in sorted(desp.get("demandas", {})):
        cons.append(ConsignaRecurso(uid, "ell", "kW", tuple(desp["demandas"][uid]["ell"])))
    if desp.get("descarte") is not None and e3.base.politica_servico.descarte is not None:
        cons.append(ConsignaRecurso(str(e3.base.politica_servico.descarte.uid), "d", "kW", tuple(desp["descarte"])))
    p = PlanoDespacho(CONTRATO_VERSAO, e3.base.microrrede_uid, e3.base.cenario_uid, he, res.motor_id,
                      res.versao_formulacao, res.classificacao, res.estado_despacho, m.inicio().isoformat(), m.delta_s,
                      m.N, indice_fronteira_inicial, tuple(cons), tuple(est), dict(res.custos_modelo))
    c = validar_plano(p)
    if c:
        raise ContratoInvalido(c)
    mem = tuple(replace(x, indice_fronteira=indice_fronteira_inicial + m.N) for x in res.memoria_terminal)
    gar, obr = garantia(mem)
    pc = PlanoCommitment3C1(CONTRATO_VERSAO, hash_plano(p), he, e3.politica_permanencia.tipo, gar, mem, dict(obr),
                            dict(res.eventos), res.custos_modelo.get("eventos"))
    return p, pc


# ------------------------------------------------------------------------------------------------ executor
FONTES_DISPONIBILIDADE = {
    "observada": "Observação REALIZADA obrigatória: série ``<uid>|disponibilidade`` da realização, alinhada à malha, com "
                 "valor em {0, 1} e o UID EXATO da unidade (nenhuma herança do registro); ausente ⇒ erro de DADOS",
    "estatica_declarada": "Condição ESTÁTICA declarada (valor 0/1 com procedência e justificativa) válida para toda a "
                          "execução; uma observação realizada do mesmo UID, se existir, deve coincidir (senão: dados "
                          "contraditórios ⇒ erro de DADOS)",
}


@dataclass(frozen=True)
class FonteDisponibilidadeExecucao:
    """De onde vem a disponibilidade EFETIVA de UMA unidade geradora durante a execução (A-01). Sem padrão: toda unidade
    da entrada exige uma declaração; nenhuma disponibilidade 1 é presumida."""
    uid: str                                    # str(UIDRecurso) da unidade, p. ex. "eq-…#2"
    fonte: str                                  # FONTES_DISPONIBILIDADE
    valor: int | None = None                    # só "estatica_declarada": 0 ou 1 (int estrito)
    procedencia: Procedencia | None = None      # só "estatica_declarada"
    justificativa: str = ""                     # só "estatica_declarada"


def validar_fontes_disponibilidade(e3: EntradaCommitment3C1, fontes) -> list[Constatacao]:
    from ..provenance import validar_procedencia
    out: list[Constatacao] = []
    if not isinstance(fontes, dict):
        return [erro("fontes_disponibilidade_invalidas", "disponibilidade",
                     f"Esperado dicionário UID → FonteDisponibilidadeExecucao; recebido {type(fontes).__name__}.")]
    ger = {str(g.uid) for g in e3.base.geradores}
    for k in sorted((x for x in fontes if x not in ger), key=repr):
        out.append(erro("fonte_disponibilidade_uid_desconhecido", f"disponibilidade[{k!r}]",
                        "UID não é unidade geradora da entrada."))
    for k in sorted(ger):
        f = fontes.get(k)
        cam = f"disponibilidade[{k}]"
        if f is None:
            out.append(erro("fonte_disponibilidade_nao_declarada", cam,
                            "Fonte da disponibilidade da unidade na execução não declarada (nenhuma disponibilidade 1 é "
                            "presumida)."))
            continue
        if not isinstance(f, FonteDisponibilidadeExecucao) or f.uid != k:
            out.append(erro("fonte_disponibilidade_invalida", cam, "Declaração de outro UID ou de tipo inválido."))
            continue
        if f.fonte not in FONTES_DISPONIBILIDADE:
            out.append(erro("fonte_disponibilidade_invalida", cam + ".fonte", f"{f.fonte!r}."))
        elif f.fonte == "observada":
            if f.valor is not None or f.procedencia is not None:
                out.append(erro("fonte_disponibilidade_contraditoria", cam,
                                "Fonte 'observada' não aceita valor estático (a observação vem da realização)."))
        else:
            if type(f.valor) is not int or f.valor not in (0, 1):
                out.append(erro("disponibilidade_estatica_invalida", cam + ".valor",
                                f"Exigido int 0 ou 1 (sem bool/float); recebido {f.valor!r}."))
            out += validar_procedencia(f.procedencia, cam + ".procedencia")
            if not f.justificativa.strip():
                out.append(erro("disponibilidade_estatica_sem_justificativa", cam + ".justificativa",
                                "Condição estática exige justificativa explícita de admissibilidade."))
    return out


class ExecutorAlgebricoCommitment3C1:
    """Dublê ALGÉBRICO (natureza ``algebrico_referencia``; NÃO é modelo físico) do commitment 3C-1.

    ``disponibilidade`` (obrigatório, A-01): ``{uid: FonteDisponibilidadeExecucao}`` para TODA unidade geradora. A
    disponibilidade efetiva de cada passo é obtida só pela fonte declarada; falta/valor inválido/contradição = erro de
    DADOS (``falha = "dados"``); unidade efetivamente indisponível com consigna ON = inexequível (física)."""
    natureza = "algebrico_referencia"

    def __init__(self, e3: EntradaCommitment3C1, disponibilidade: dict, tol: Tolerancias = Tolerancias(),
                 identificador: str = "ref-alg-3C1"):
        c = validar_fontes_disponibilidade(e3, disponibilidade)
        if c:
            raise ContratoInvalido(c)
        self.e3, self.tol, self.identificador = e3, tol, identificador
        self.fontes = dict(disponibilidade)
        self._base = ExecutorAlgebricoReferencia(e3.base, tol, identificador)
        self._disc = discretizar(e3)
        self._recursos = ({str(r.uid) for r in e3.base.renovaveis} | {str(b.uid) for b in e3.base.baterias}
                          | {str(g.uid) for g in e3.base.geradores})

    def _T_s(self, uid: str, ligado: bool):
        sp = self.e3.unidade(uid)
        return tempo_s_exato(sp.tempo_min_ligado_min if ligado else sp.tempo_min_desligado_min)

    def disponibilidade_efetiva(self, uid: str, entorno: dict) -> tuple[int | None, list[Constatacao]]:
        """Disponibilidade efetiva no intervalo: (0|1, []) ou (None, [erro de dados])."""
        f = self.fontes[uid]
        obs = entorno.get(f"{uid}|disponibilidade")
        valido = not isinstance(obs, bool) and isinstance(obs, (int, float)) and math.isfinite(obs) and obs in (0, 1)
        if obs is not None and not valido:
            return None, [erro("disponibilidade_realizada_invalida", uid,
                               f"Disponibilidade realizada {obs!r} ∉ {{0, 1}} (fracionária/NaN não é interpretada).")]
        if f.fonte == "observada":
            if obs is None:
                return None, [erro("disponibilidade_realizada_ausente", uid,
                                   "Fonte 'observada': a realização não contém a série de disponibilidade desta unidade "
                                   "para o intervalo (nada é presumido; nenhuma herança do registro).")]
            return int(obs), []
        if obs is not None and int(obs) != f.valor:
            return None, [erro("disponibilidade_contraditoria", uid,
                               f"Condição estática declarada a = {f.valor} contradiz a observação realizada a = {obs:g}.")]
        return f.valor, []

    def avancar(self, estado, consignas, entorno, delta_s) -> PassoAplicado:
        c: list[Constatacao] = []
        dados = False
        for k in sorted(entorno):
            uid, _, grandeza = k.partition("|")
            if grandeza == "disponibilidade" and uid not in self._recursos:
                c.append(erro("disponibilidade_de_outro_recurso", k,
                              "Série de disponibilidade para UID que não é recurso da entrada (outra unidade/registro?)."))
                dados = True
        escala = max([1.0] + [float(g.p_max_kW.valor) for g in self.e3.base.geradores])
        tolP = self.tol.potencia_abs_kW + self.tol.potencia_rel_escala * max(escala, 1.0)
        for uid, dz in sorted(self._disc.items()):
            st = estado.gerador(uid)
            u, p = consignas.get(f"{uid}|u"), consignas.get(f"{uid}|p")
            a, ca = self.disponibilidade_efetiva(uid, entorno)
            if ca:
                c += ca
                dados = True
            if st is None or u is None or p is None:
                continue                                      # o executor 3C-0 constata a ausência
            lig, lig0, p0 = u > 0.5, st.ligado, st.potencia_kW
            if lig and a == 0:
                c.append(erro("consigna_inexequivel_indisponivel", uid,
                              f"u = 1 com disponibilidade efetiva 0 (fonte {self.fontes[uid].fonte!r})."))
            y, z = (lig and not lig0), (lig0 and not lig)
            if y or z:
                if (y and not dz.partida_representavel) or (z and not dz.parada_representavel):
                    c.append(erro("transicao_nao_representavel", uid,
                                  f"{'Partida' if y else 'Parada'} não representável com os parâmetros declarados."))
                T = self._T_s(uid, lig0)
                if T is not None and T > 0:
                    if st.tempo_no_estado_s is None:
                        c.append(erro("memoria_ausente", uid, "Transição comandada sem memória do tempo no estado: "
                                                              "nada é presumido."))
                        dados = True
                    elif obrigacao_derivada_s(T, st.tempo_no_estado_s) > 0:
                        c.append(erro("permanencia_minima_violada", uid,
                                      f"{'Partida' if y else 'Parada'} após {st.tempo_no_estado_s} s no estado; "
                                      f"permanência mínima {T} s."))
            sup = (dz.rampa_subida_kW or 0.0) * lig0 + (dz.limite_partida_kW or 0.0) * y
            inf = (dz.rampa_descida_kW or 0.0) * lig + (dz.limite_parada_kW or 0.0) * z
            if p - p0 > sup + tolP or p0 - p > inf + tolP:
                c.append(erro("rampa_violada", uid, f"p {p0} → {p} kW fora de [−{inf}, +{sup}] kW (M11)."))
        if c:
            return PassoAplicado({}, estado, False, tuple(c), "dados" if dados else "inexequivel")
        return self._base.avancar(estado, consignas, entorno, delta_s)


# ------------------------------------------------------------------------------------------------ transporte
def estado_inicial_3c1(e3: EntradaCommitment3C1, *, indice_fronteira: int = 0) -> EstadoMicrorrede:
    """Estado na fronteira inicial com a MEMÓRIA declarada da entrada 3C-1 (tempo no estado por UID da unidade)."""
    from .execucao import estado_inicial_de_entrada
    return estado_inicial_de_entrada(e3.base, indice_fronteira=indice_fronteira,
                                     memoria={str(m.uid): m.tempo_no_estado_s for m in e3.memorias
                                              if m.tempo_no_estado_s is not None})


def memorias_do_estado(e3: EntradaCommitment3C1, estado: EstadoMicrorrede, origem: str = "execucao"
                       ) -> tuple[MemoriaFronteira, ...]:
    """Memória por unidade na fronteira do ``estado``: u, p e tempo no estado vêm do estado (checkpoint); a
    obrigação é DERIVADA dos tempos mínimos declarados (⌈max(0, T − tempo)⌉), nunca da potência."""
    out = []
    for g in sorted(e3.base.geradores, key=lambda x: str(x.uid)):
        k = str(g.uid)
        st = estado.gerador(k)
        if st is None:
            raise ContratoInvalido([erro("estado_ausente", k, "Gerador sem estado na fronteira.")])
        sp = e3.unidade(k)
        T = tempo_s_exato(sp.tempo_min_ligado_min if st.ligado else sp.tempo_min_desligado_min)
        ob = obrigacao_derivada_s(T, st.tempo_no_estado_s) if T is not None else (
            0 if sp.abstracao_transicao == "transicoes_bloqueadas" else None)
        out.append(MemoriaFronteira(k, estado.indice_fronteira, st.ligado, st.potencia_kW, st.tempo_no_estado_s, ob,
                                    origem))
    return tuple(out)


def entrada_de_continuacao(e3: EntradaCommitment3C1, estado: EstadoMicrorrede, *, procedencia: Procedencia
                           ) -> EntradaCommitment3C1:
    """Substitui, na entrada da JANELA SEGUINTE ``e3`` (malha começando em τ_k), os estados iniciais de geradores e
    bancos e as memórias pelos do ``estado`` transportado (checkpoint/plano). Recusa microrrede, instante ou UIDs
    divergentes. Nenhum valor é completado: o que falta no estado bloqueia."""
    b = e3.base
    c: list[Constatacao] = []
    if estado.microrrede_uid != b.microrrede_uid:
        c.append(erro("estado_de_outra_microrrede", "estado.microrrede_uid", "Estado de outra microrrede."))
    te, ce = ler_instante_utc(estado.instante_utc, "estado.instante_utc")
    if ce or te != b.malha.inicio():
        c.append(erro("estado_dessincronizado", "estado.instante_utc",
                      f"Estado em {estado.instante_utc}; a janela seguinte começa em {b.malha.inicio_utc}."))
    if {x.uid for x in estado.geracao} != {str(g.uid) for g in b.geradores} or \
            {x.uid for x in estado.armazenamento} != {str(x.uid) for x in b.baterias}:
        c.append(erro("estado_incompativel_com_entrada", "estado", "UIDs do estado ≠ recursos com estado na entrada."))
    if c:
        raise ContratoInvalido(c)
    obs = f"transportado da fronteira k = {estado.indice_fronteira} ({estado.instante_utc})"
    proc = replace(procedencia, observacoes=(procedencia.observacoes + " · " + obs).strip(" ·"))
    egs = tuple(EstadoGerador(g.uid, estado.gerador(str(g.uid)).ligado,
                              Parametro(estado.gerador(str(g.uid)).potencia_kW, "kW", proc)) for g in b.geradores)
    ebs = tuple(EstadoBateria(x.uid, Parametro(estado.bateria(str(x.uid)).energia_kWh, "kWh", proc)) for x in b.baterias)
    mems = memorias_do_estado(e3, estado)
    ger = {str(g.uid): g.uid for g in b.geradores}
    memorias = tuple(MemoriaCommitmentUnidade(ger[x.uid], x.tempo_no_estado_s, x.obrigacao_residual_s, proc)
                     for x in mems)
    return replace(e3, base=replace(b, estados_geradores=egs, estados_baterias=ebs), memorias=memorias)


def _eventos_aplicados(traj: TrajetoriaExecutada) -> dict[str, dict[str, int]]:
    """Partidas/paradas EFETIVAMENTE aplicadas: comparação dos estados de fronteiras consecutivas da trajetória
    executada (só intervalos aplicados; planos não executados não contam)."""
    out: dict[str, dict[str, int]] = {}
    for a, b in zip(traj.estados, traj.estados[1:]):
        for g in b.geracao:
            ga = a.gerador(g.uid)
            if ga is None:
                continue
            d = out.setdefault(g.uid, {"partidas": 0, "paradas": 0})
            if g.ligado and not ga.ligado:
                d["partidas"] += 1
            elif ga.ligado and not g.ligado:
                d["paradas"] += 1
    return out


def custo_eventos_realizado(e3: EntradaCommitment3C1, traj: TrajetoriaExecutada) -> ComponenteCusto | None:
    """Custo de eventos INCORRIDO: transições entre estados consecutivos efetivamente aplicados (C_SU, C_SD declarados).
    ``None`` se o termo "eventos" não está no objetivo (nenhum custo não declarado aparece)."""
    if "eventos" not in e3.termos:
        return None
    tot, n_su, n_sd = [], 0, 0
    for uid, ev in sorted(_eventos_aplicados(traj).items()):
        sp = e3.unidade(uid)
        if sp is None or sp.custo_partida is None:
            continue
        tot += [float(sp.custo_partida.valor)] * ev["partidas"] + [float(sp.custo_parada.valor)] * ev["paradas"]
        n_su, n_sd = n_su + ev["partidas"], n_sd + ev["paradas"]
    return ComponenteCusto("eventos", math.fsum(tot), "realizado", f"{n_su} partida(s), {n_sd} parada(s) aplicadas")


@dataclass(frozen=True)
class DetalheH2Realizado:
    uid: str
    massa_continua_kg: float                    # Σ_t h·q(p_t) aplicado (via contabilidade 3C-0)
    partidas: int
    paradas: int
    massa_eventos_kg: float                     # m_SU·partidas + m_SD·paradas (B05 instantânea)
    custo_continuo_R: float
    custo_eventos_R: float


@dataclass(frozen=True)
class ContabilidadeRealizada3C1:
    """Extensão do perfil 3C-1 sobre a contabilidade REALIZADA do 3C-0 (A-02). ``custo`` é um ``CustoRealizado`` 3C-0
    (componentes de base "realizado"), utilizável sem mudança em ``RegistroExecucaoEMS``; ``combustivel_h2`` =
    contínuo (3C-0) + massas de evento aplicadas (sem dupla contagem); ``eventos`` = C_SU/C_SD aplicados."""
    indicadores: dict[str, float]
    custo: object                               # registro.CustoRealizado
    eventos_aplicados: dict[str, dict[str, int]]
    h2: tuple[DetalheH2Realizado, ...]


def contabilidade_realizada_3c1(e3: EntradaCommitment3C1, plano: PlanoDespacho, traj: TrajetoriaExecutada,
                                real) -> ContabilidadeRealizada3C1:
    """Indicadores e custos INCORRIDOS de uma execução 3C-1 (intervalos efetivamente aplicados, entorno realizado).

    1. Reutiliza SEM ALTERAÇÃO ``registro.indicadores_e_custo`` (3C-0) para os termos da base: curtailment, throughput,
       ENS e a parte CONTÍNUA do H₂ (c_H·Σ h·q(p) aplicado — a 3C-0 não conhece eventos, logo não os conta);
    2. acrescenta ao componente ``combustivel_h2`` a massa dos eventos EFETIVAMENTE aplicados:
       c_H·(m_SU·partidas + m_SD·paradas) — só para PEMFC com massas declaradas e o termo no objetivo;
    3. acrescenta o componente ``eventos`` (C_SU·partidas + C_SD·paradas) só com o termo declarado.
    Valor futuro nunca entra (3C-0: ``AvaliacaoValorFuturo`` separado)."""
    from .registro import CustoRealizado, indicadores_e_custo
    ind, base = indicadores_e_custo(e3.base, plano, traj, real)
    ev = _eventos_aplicados(traj)
    termos = set(e3.termos)
    h2s: list[DetalheH2Realizado] = []
    h = plano.delta_s / 3600.0
    for g in sorted(e3.base.geradores, key=lambda x: str(x.uid)):
        k = str(g.uid)
        if g.tecnologia != "pemfc" or g.curva_h2 is None or "combustivel_h2" not in termos:
            continue
        sp = e3.unidade(k)
        from ..reference import vazao_pwl
        mc = math.fsum(h * float(vazao_pwl(g.curva_h2.vertices, p.aplicado[f"{k}|p"], True))
                       for p in traj.passos if p.aplicado[f"{k}|u"] > 0.5)
        n = ev.get(k, {"partidas": 0, "paradas": 0})
        me = 0.0 if sp.massa_h2_partida_kg is None else math.fsum(
            [float(sp.massa_h2_partida_kg.valor)] * n["partidas"] + [float(sp.massa_h2_parada_kg.valor)] * n["paradas"])
        cH = float(g.preco_h2.valor)
        h2s.append(DetalheH2Realizado(k, mc, n["partidas"], n["paradas"], me, cH * mc, cH * me))
    comps = []
    for c in base.componentes:
        if c.termo == "combustivel_h2":
            extra = math.fsum(x.custo_eventos_R for x in h2s)
            c = ComponenteCusto(c.termo, math.fsum([c.valor_R, extra]), "realizado",
                                f"{c.detalhe}; contínuo R$ {c.valor_R!r} + eventos R$ {extra!r} (m_SU/m_SD aplicados)")
        comps.append(c)
    ce = custo_eventos_realizado(e3, traj)
    if ce is not None:
        comps.append(ce)
    ind = dict(ind)
    ind["H2_continuo_kg"] = math.fsum(x.massa_continua_kg for x in h2s)
    ind["H2_eventos_kg"] = math.fsum(x.massa_eventos_kg for x in h2s)
    ind["partidas_aplicadas"] = float(sum(v["partidas"] for v in ev.values()))
    ind["paradas_aplicadas"] = float(sum(v["paradas"] for v in ev.values()))
    custo = CustoRealizado(tuple(comps), math.fsum(c.valor_R for c in comps), len(traj.passos))
    return ContabilidadeRealizada3C1(ind, custo, ev, tuple(h2s))


# ------------------------------------------------------------------------------------------------ projeção
@dataclass(frozen=True)
class CondicaoInicialUnidade:
    """Estado inicial de UMA unidade física (``uid`` = ``str(UIDRecurso)``, p. ex. ``eq-…#2``). Lacuna D9: o cenário do
    SEEDS2 não tem estes campos — hoje só existem em declarações sintéticas de ensaio."""
    uid: str
    estado_discreto: str                       # "desligada" | "em_operacao" ("em_partida" não representável)
    potencia_kW: Parametro | None
    tempo_no_estado_s: int | None
    procedencia: Procedencia | None


@dataclass(frozen=True)
class VinculoDeclaracao3C1:
    """Instantâneo de dados que SUSTENTA as condições iniciais declaradas (B-02). Reutiliza os identificadores já
    existentes nos contratos — nenhuma identidade nova: ``ReferenciaInventario`` (microrrede, incarnação, revisão e
    impressões SHA-256 da configuração e do inventário físico) + cenário (UID, versão e impressão SHA-256)."""
    inventario: ReferenciaInventario
    cenario_uid: str
    versao_cenario: int
    impressao_cenario: str


def vinculo_do_instantaneo(inv: InventarioMicrorrede, cen: CenarioEMS) -> VinculoDeclaracao3C1:
    """Vínculo com o instantâneo REALMENTE usado (inventário + versão do cenário) para compor a declaração."""
    i = inv.identidade
    return VinculoDeclaracao3C1(ReferenciaInventario(i.uid, i.incarnacao, i.revisao_config, i.impressao_config,
                                                     i.impressao_inventario),
                                cen.cenario_uid, cen.versao_cenario, cen.impressao_cenario)


@dataclass(frozen=True)
class DeclaracaoCommitment3C1:
    """Decisões de modelagem do commitment declaradas por quem executa (nenhuma tem valor padrão). Vinculada ao
    instantâneo EXATO (``vinculo``: microrrede, incarnação, revisão/impressões do inventário, versão/impressão do
    cenário; A-03/B-02): aplicada a outro inventário, revisão, incarnação, cenário ou versão ⇒ erro."""
    vinculo: VinculoDeclaracao3C1
    politica_permanencia: PoliticaPermanenciaTerminal
    termos_adicionais: tuple[str, ...]
    abstracao_por_equipamento: dict[str, str]  # UID do registro (eq-…) → ABSTRACOES_TRANSICAO
    limites_por_equipamento: dict[str, str]    # UID do registro → LIMITES_TRANSICAO
    justificativa: str
    unidades: tuple[CondicaoInicialUnidade, ...]
    procedencia: Procedencia | None


def _par3c1(mat, uid: str, simbolo: str) -> Parametro | None:
    """Como ``projecao._par``, mas uma REINTERPRETAÇÃO semântica declarada (p. ex. "Custo de partida" em R$ ≡ R$/evento,
    ``requisitos.unidades_equivalentes``) não é conversão linear: o verificador de cadeia 3A (``units.fator_conversao``)
    não a reconhece. O valor é mantido, a ``Transformacao`` de reinterpretação fica registrada em ``transformacoes`` e
    ``valor_bruto``/``unidade_bruta`` NÃO são preenchidos (não há cadeia numérica a conferir: fator 1 declarado)."""
    p = _par(mat, uid, simbolo)
    if p is not None and any(t.etapa == "reinterpretacao_declarada" for t in p.transformacoes):
        return Parametro(p.valor, p.unidade, p.procedencia, None, None, p.transformacoes)
    return p


def _num(p: Parametro | None):
    return None if p is None else p.valor


def _com_origem(cu: CondicaoInicialUnidade, origem: str) -> CondicaoInicialUnidade:
    """Anota a ORIGEM da condição usada na procedência (da potência e da condição) — verificável no contrato."""
    def anota(pr: Procedencia | None) -> Procedencia | None:
        return None if pr is None else replace(pr, observacoes=(f"{pr.observacoes} · origem: {origem}").strip(" ·"))
    pot = None if cu.potencia_kW is None else replace(cu.potencia_kW, procedencia=anota(cu.potencia_kW.procedencia))
    return replace(cu, potencia_kW=pot, procedencia=anota(cu.procedencia))


def hash_declaracao(decl: DeclaracaoCommitment3C1) -> str:
    """SHA-256 do JSON canônico da declaração (referência verificável; o conteúdo é serializável por
    ``canonico.json_canonico`` e relido por ``declaracao_de_json`` — o hash sozinho não reconstrói nada)."""
    return sha256(decl)


def declaracao_de_json(texto: str) -> DeclaracaoCommitment3C1:
    from .canonico import de_json
    return de_json(DeclaracaoCommitment3C1, texto)


def verificar_vinculo(v: VinculoDeclaracao3C1, inv: InventarioMicrorrede, cen: CenarioEMS) -> list[Constatacao]:
    """B-02: a declaração só se aplica ao instantâneo que a sustenta. Qualquer divergência BLOQUEIA (mesmo com o mesmo
    UID de cenário: outra versão, outra revisão do inventário com o mesmo conteúdo físico ou outra incarnação)."""
    c: list[Constatacao] = []
    if not isinstance(v, VinculoDeclaracao3C1) or not isinstance(v.inventario, ReferenciaInventario):
        return [erro("declaracao_sem_vinculo", "declaracao.vinculo", "Declaração sem vínculo ao instantâneo de dados.")]
    i, r = inv.identidade, v.inventario
    if r.microrrede_uid != i.uid:
        c.append(erro("declaracao_de_outra_microrrede", "declaracao.vinculo.inventario.microrrede_uid",
                      f"Declaração da microrrede {r.microrrede_uid!r} aplicada ao inventário de {i.uid!r}."))
        return c
    if r.incarnacao != i.incarnacao:
        c.append(erro("declaracao_de_outra_incarnacao", "declaracao.vinculo.inventario.incarnacao",
                      "Declaração feita para outra incarnação da microrrede (excluída e reimportada com o mesmo UID)."))
    if (r.revisao_config, r.impressao_config, r.impressao_inventario) != (i.revisao_config, i.impressao_config,
                                                                         i.impressao_inventario):
        c.append(erro("declaracao_de_outra_revisao_do_inventario", "declaracao.vinculo.inventario",
                      f"Declaração sustentada pela revisão {r.revisao_config} (config {r.impressao_config[:12]}…, "
                      f"inventário {r.impressao_inventario[:12]}…); o instantâneo é a revisão {i.revisao_config} "
                      f"(config {i.impressao_config[:12]}…, inventário {i.impressao_inventario[:12]}…): declaração obsoleta."))
    if v.cenario_uid != cen.cenario_uid:
        c.append(erro("declaracao_de_outro_cenario", "declaracao.vinculo.cenario_uid",
                      f"Declaração do cenário {v.cenario_uid!r} aplicada ao cenário {cen.cenario_uid!r}."))
    elif (v.versao_cenario, v.impressao_cenario) != (cen.versao_cenario, cen.impressao_cenario):
        c.append(erro("declaracao_de_outra_versao_do_cenario", "declaracao.vinculo",
                      f"Declaração sustentada pela versão {v.versao_cenario} do cenário ({v.impressao_cenario[:12]}…); "
                      f"aplicada à versão {cen.versao_cenario} ({cen.impressao_cenario[:12]}…): declaração obsoleta."))
    return c


def coerencia_agregado_unidades(d, ci, declaradas: dict[str, CondicaoInicialUnidade], tol: Tolerancias = Tolerancias()
                                ) -> list[Constatacao]:
    """B-01: estados POR UNIDADE × condição AGREGADA do registro no cenário (bloco com ``quantidade`` q > 1).

    Só compara o que o cenário DECLARA (nada é inferido nem distribuído):
    * ``unidades_ligadas`` = k ⇒ ON declaradas = k (todas as q declaradas) ou ON <= k e OFF <= q − k (parcial);
    * ``estado_discreto`` do registro: ``desligada`` ⇒ nenhuma unidade ON; ``em_operacao`` ⇒ ao menos uma ON (com as q
      declaradas); ``em_partida`` ⇒ incompatível com estados estacionários por unidade;
    * ``potencia_kW`` do registro (potência líquida do REGISTRO INTEIRO, semântica de ``CondicaoInicialDispositivo``)
      ⇒ Σ potências por unidade = agregado (todas declaradas) ou <= agregado (parcial), na tolerância provisória D07
      de potência (``potencia_abs_kW + potencia_rel_escala·max(1, agregado)``)."""
    if ci is None:
        return []
    q = d.quantidade or 1
    cam = f"cenario.condicoes_iniciais[{d.uid}]"
    lig = [k for k, x in declaradas.items() if x.estado_discreto == "em_operacao"]
    des = [k for k, x in declaradas.items() if x.estado_discreto == "desligada"]
    n, todas = len(declaradas), len(declaradas) == q
    out: list[Constatacao] = []
    k = ci.unidades_ligadas
    if k is not None and not isinstance(k, bool) and isinstance(k, int):
        if (todas and len(lig) != k) or len(lig) > k or len(des) > q - k:
            out.append(erro("unidades_ligadas_incoerente", cam + ".unidades_ligadas",
                            f"Cenário declara {k} de {q} unidades em operação; declarações por unidade: {len(lig)} ON, "
                            f"{len(des)} OFF ({n} de {q} declaradas)."))
    e = ci.estado_discreto
    if e == "desligada" and lig:
        out.append(erro("estado_agregado_incoerente", cam + ".estado_discreto",
                        f"Registro 'desligada' no cenário com unidade(s) ON declarada(s): {sorted(lig)}."))
    elif e == "em_operacao" and todas and not lig:
        out.append(erro("estado_agregado_incoerente", cam + ".estado_discreto",
                        "Registro 'em_operacao' no cenário, mas todas as unidades declaradas OFF."))
    elif e == "em_partida" and declaradas:
        out.append(erro("estado_agregado_incoerente", cam + ".estado_discreto",
                        "Registro 'em_partida' no cenário (transitório, não representável) × estados estacionários "
                        "declarados por unidade."))
    pa = ci.potencia_kW
    if pa is not None and pa.valor is not None and declaradas and all(
            x.potencia_kW is not None and x.potencia_kW.valor is not None for x in declaradas.values()):
        soma = math.fsum(float(x.potencia_kW.valor) for x in declaradas.values())
        agg = float(pa.valor)
        t = tol.potencia_abs_kW + tol.potencia_rel_escala * max(1.0, abs(agg))
        if (todas and abs(soma - agg) > t) or soma > agg + t:
            out.append(erro("potencia_agregada_incoerente", cam + ".potencia_kW",
                            f"Potência do registro no cenário = {agg} kW; Σ potências por unidade = {soma} kW ({n} de {q} "
                            f"declaradas; tolerância {t} kW). Nenhuma potência é redistribuída."))
    return out


def _condicoes_por_unidade(inv: InventarioMicrorrede, cen: CenarioEMS, decl: DeclaracaoCommitment3C1, gers
                           ) -> tuple[dict[str, CondicaoInicialUnidade], list[Constatacao]]:
    """A-03: valida as declarações por unidade ANTES de indexá-las. Duplicatas (mesmo idênticas), UIDs que não são
    unidades geradoras habilitadas DESTA microrrede (outra microrrede, recurso inexistente, outro índice de unidade,
    UID do registro de um bloco com várias unidades) e procedência inválida são rejeitados; nada é sobrescrito."""
    from collections import Counter
    from ..parameters import validar_parametro
    from ..provenance import validar_procedencia
    c: list[Constatacao] = []
    c += verificar_vinculo(decl.vinculo, inv, cen)
    c += validar_procedencia(decl.procedencia, "declaracao.procedencia", sustenta_valor=False)
    esperados = {str(r): d for d, r in gers}
    outros = {str(r): d for d in inv.dispositivos for r in recursos_ems(d)} | {d.uid: d for d in inv.dispositivos}
    cont = Counter(x.uid for x in decl.unidades)
    for k, n in sorted(cont.items(), key=lambda kv: repr(kv[0])):
        if n > 1:
            c.append(erro("condicao_unidade_duplicada", f"declaracao.unidades[{k}]",
                          f"{n} declarações para a mesma unidade (rejeitadas mesmo se idênticas: nenhuma é escolhida)."))
    ok: dict[str, CondicaoInicialUnidade] = {}
    for i, x in enumerate(decl.unidades):
        cam = f"declaracao.unidades[{i}:{x.uid}]"
        if x.uid not in esperados:
            if x.uid in outros:
                det = (f"o UID pertence a {outros[x.uid].tipo!r} {outros[x.uid].uid!r}, que não é unidade geradora "
                       "habilitada (ou é o registro de um bloco com várias unidades: declarar eq-…#k)")
            else:
                det = "não existe nesta microrrede (outra microrrede ou recurso inexistente)"
            c.append(erro("condicao_unidade_uid_desconhecido", cam, f"UID {x.uid!r}: {det}."))
            continue
        cp = validar_procedencia(x.procedencia, cam + ".procedencia")
        if x.potencia_kW is not None:
            cp += validar_parametro(x.potencia_kW, cam + ".potencia_kW", unidade="kW", dominio="nao_negativo")
        if x.tempo_no_estado_s is not None and (isinstance(x.tempo_no_estado_s, bool)
                                                or not isinstance(x.tempo_no_estado_s, int) or x.tempo_no_estado_s < 0):
            cp.append(erro("memoria_invalida", cam + ".tempo_no_estado_s", f"{x.tempo_no_estado_s!r}."))
        c += cp
        if cont[x.uid] == 1 and not cp:
            v = decl.vinculo
            ok[x.uid] = _com_origem(x, f"DeclaracaoCommitment3C1.unidades[{i}] (cenário {v.cenario_uid} v{v.versao_cenario}"
                                       f", inventário rev. {v.inventario.revisao_config}; declaração "
                                       f"{hash_declaracao(decl)[:16]})")
    return ok, c


@dataclass(frozen=True)
class ResultadoProjecao3C1:
    entrada: EntradaCommitment3C1 | None
    constatacoes: tuple[Constatacao, ...]
    base: ResultadoProjecao

    @property
    def aceito(self) -> bool:
        return self.entrada is not None and not any(c.severidade in ("erro", "pendente") for c in self.constatacoes)


def montar_entrada_3c1(inv: InventarioMicrorrede, cen: CenarioEMS, prev: ConjuntoPrevisao, dt: DefinicaoTemporal,
                       pol: PoliticasDeclaradas, decl: DeclaracaoCommitment3C1, *, contexto: str = "operacional"
                       ) -> tuple[EntradaCommitment3C1 | None, tuple[Constatacao, ...], ResultadoProjecao]:
    c: list[Constatacao] = []
    if pol.versao_formulacao != FORMULACAO_3BP:
        c.append(erro("base_nao_3bp", "politicas.versao_formulacao",
                      f"O núcleo do 3C-1 é declarado {FORMULACAO_3BP!r} (recebido {pol.versao_formulacao!r})."))
    gers = [(d, r) for d in inv.dispositivos if d.habilitado and d.modelo.papel_ems == "gerador" for r in recursos_ems(d)]
    cond_u, cu_c = _condicoes_por_unidade(inv, cen, decl, gers)
    c += cu_c
    for d in inv.dispositivos:                      # B-01: agregado do cenário × estados por unidade
        if d.habilitado and d.modelo.papel_ems == "gerador" and (d.quantidade or 1) > 1:
            decl_d = {str(r): cond_u[str(r)] for r in recursos_ems(d) if str(r) in cond_u}
            c += coerencia_agregado_unidades(d, cen.condicao(d.uid), decl_d)
    if any(x.severidade in ("erro", "pendente") for x in c):
        return None, tuple(c), ResultadoProjecao(None, tuple(c), None)
    estados: dict[str, EstadoGerador] = {}
    usadas: dict[str, CondicaoInicialUnidade] = {}
    for d, r in gers:
        k = str(r)
        cu = cond_u.get(k)
        ci = cen.condicao(d.uid)
        if (d.quantidade or 1) == 1 and ci is not None and ci.estado_discreto in ("desligada", "em_operacao") \
                and ci.potencia_kW is not None:
            # registro de UMA unidade: a condição do registro no cenário É a da unidade
            do_cen = CondicaoInicialUnidade(k, ci.estado_discreto, ci.potencia_kW, ci.tempo_no_estado_s,
                                            ci.potencia_kW.procedencia)
            if cu is None:
                cu = _com_origem(do_cen, f"condição do registro {d.uid} no cenário {cen.cenario_uid} v{cen.versao_cenario}"
                                         " (registro de uma unidade)")
            elif (cu.estado_discreto, _num(cu.potencia_kW), cu.tempo_no_estado_s) != (
                    do_cen.estado_discreto, _num(do_cen.potencia_kW),
                    cu.tempo_no_estado_s if do_cen.tempo_no_estado_s is None else do_cen.tempo_no_estado_s):
                c.append(erro("condicao_unidade_contradiz_cenario", f"declaracao.unidades[{k}]",
                              "Condição declarada por unidade difere da condição do registro no cenário (nenhuma das duas "
                              "é escolhida em silêncio)."))
                continue
            else:
                c.append(aviso("condicao_unidade_redundante_com_cenario", f"declaracao.unidades[{k}]",
                               "Condição por unidade idêntica à do registro no cenário; usada a declaração por unidade."))
        if cu is None:
            continue                                # montar_entrada constata (estado ausente / por unidade)
        if cu.estado_discreto not in ("desligada", "em_operacao"):
            c.append(pendente("estado_em_partida_nao_representavel", f"unidades[{k}]",
                              "'Em partida' exige o autômato multimodo (M20), não habilitado."))
            continue
        if cu.potencia_kW is None:
            c.append(erro("potencia_inicial_ausente", f"unidades[{k}].potencia_kW", "Potência anterior não declarada."))
            continue
        usadas[k] = cu
        estados[k] = EstadoGerador(r, cu.estado_discreto == "em_operacao", cu.potencia_kW)
    proj = montar_entrada(inv, cen, prev, dt, pol, contexto=contexto, estados_por_unidade=estados, perfil=FORMULACAO_3C1)
    c += list(proj.constatacoes)
    termos = frozenset(pol.objetivo.termos) | frozenset(decl.termos_adicionais)
    if proj.entrada is None:
        return None, tuple(c), proj
    from .requisitos import matriz_parametros
    mat = matriz_parametros(inv, termos=termos, contexto=contexto, perfil=FORMULACAO_3C1)
    from .requisitos import constatacoes as constatacoes_matriz
    c += [x for x in constatacoes_matriz(mat) if x not in c]
    unidades, memorias = [], []
    for d, r in gers:
        k = str(r)
        abst = decl.abstracao_por_equipamento.get(d.uid)
        lim = decl.limites_por_equipamento.get(d.uid)
        if abst is None or lim is None:
            c.append(erro("declaracao_commitment_ausente", f"declaracao[{d.uid}]",
                          "Abstração de transição e limites de partida/parada não declarados para o registro."))
            continue
        if d.tipo == "pemfc" and abst == "instantanea_unidade_quente" and contexto == "operacional":
            c.append(pendente("pemfc_partida_nao_representavel_D05", f"declaracao[{d.uid}]",
                              "PEMFC real com transição instantânea: os parâmetros de partida (D05) não estão "
                              "declarados e a abstração não é validação física; use 'transicoes_bloqueadas' ou ensaio."))
        rampa = _par3c1(mat, d.uid, "rampa")
        if rampa is not None:
            rampa = replace(rampa, procedencia=replace(rampa.procedencia, observacoes=(
                (rampa.procedencia.observacoes or "") + " · rampa única do inventário aplicada à subida E à descida "
                "(interpretação do campo 'Rampa máxima')").strip(" ·"))) if rampa.procedencia else rampa
        unidades.append(EspecCommitmentUnidade(
            r, abst, lim, rampa, rampa, _par3c1(mat, d.uid, "t_on_min"), _par3c1(mat, d.uid, "t_off_min"),
            custo_partida=_par3c1(mat, d.uid, "C_SU") if "eventos" in termos else None,
            custo_parada=_par3c1(mat, d.uid, "C_SD") if "eventos" in termos else None,
            justificativa_abstracao=decl.justificativa))
        cu = usadas.get(k)
        tempo = cu.tempo_no_estado_s if cu is not None else None
        st = estados.get(k)
        sp = unidades[-1]
        T = tempo_s_exato(sp.tempo_min_ligado_min if (st is not None and st.ligado) else sp.tempo_min_desligado_min)
        ob = obrigacao_derivada_s(T, tempo)
        procm = cu.procedencia if cu is not None else None
        memorias.append(MemoriaCommitmentUnidade(r, tempo, ob, procm))
    procd = None if decl.procedencia is None else replace(
        decl.procedencia, sha256=hash_declaracao(decl), observacoes=(
            f"{decl.procedencia.observacoes} · declaração 3C-1 vinculada ao cenário {decl.vinculo.cenario_uid} "
            f"v{decl.vinculo.versao_cenario} e ao inventário rev. {decl.vinculo.inventario.revisao_config}").strip(" ·"))
    e3 = EntradaCommitment3C1(ESQUEMA_3C1, FORMULACAO_3C1, proj.entrada, tuple(unidades), tuple(memorias),
                              decl.politica_permanencia, tuple(decl.termos_adicionais), procd)
    if any(x.severidade in ("erro", "pendente") for x in c):
        return None, tuple(c), proj
    rel = validar_entrada_3c1(e3)
    c += list(rel.constatacoes)
    if not rel.aceito:
        return None, tuple(c), proj
    if contexto == "ensaio":
        c.append(aviso("entrada_de_ensaio", "contexto", "Entrada 3C-1 de ENSAIO: não é estudo físico."))
    return e3, tuple(c), proj


def hash_plano_commitment(p: PlanoCommitment3C1) -> str:
    return sha256(p)


__all__ = ["VinculoDeclaracao3C1", "coerencia_agregado_unidades", "declaracao_de_json", "hash_declaracao",
           "verificar_vinculo", "vinculo_do_instantaneo", "ContabilidadeRealizada3C1", "DetalheH2Realizado", "FONTES_DISPONIBILIDADE", "FonteDisponibilidadeExecucao",
           "contabilidade_realizada_3c1", "validar_fontes_disponibilidade",
           "CondicaoInicialUnidade", "DeclaracaoCommitment3C1", "ResultadoProjecao3C1", "ExecutorAlgebricoCommitment3C1", "PlanoCommitment3C1",
           "custo_eventos_realizado", "entrada_de_continuacao", "estado_inicial_3c1", "hash_plano_commitment", "memorias_do_estado",
           "montar_entrada_3c1", "plano_de_resultado_3c1"]
