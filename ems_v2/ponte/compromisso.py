"""Integração do commitment dinâmico 3C-1 com a ponte 3C-0 (plano → execução → estado → janela seguinte).

Só biblioteca padrão. Nenhum tipo 3C-0 foi alterado (planos, estados, checkpoints e registros 3C-0 conservam o mesmo
JSON canônico e os mesmos selos); o 3C-1 acrescenta tipos PRÓPRIOS:

* ``plano_de_resultado_3c1`` — resultado 3C-1 ACEITO → ``PlanoDespacho`` (consignas u, p, …; ``hash_entrada`` = SHA-256
  da entrada 3C-1) + ``PlanoCommitment3C1`` (memória terminal PLANEJADA, obrigações residuais, garantia, eventos e
  custo de eventos PLANEJADO). Resultado rejeitado/sem despacho ⇒ ``ContratoInvalido`` (nunca vira plano);
* ``ExecutorAlgebricoCommitment3C1`` — dublê ALGÉBRICO (não físico) que, antes de delegar ao executor 3C-0, recusa
  consignas inexequíveis pelo commitment: transição com permanência mínima não cumprida (pela MEMÓRIA do estado),
  transição não representável, rampa M11 violada, unidade ON com disponibilidade REALIZADA nula. Memória ausente
  quando necessária ⇒ falha de DADOS (nunca presumida);
* ``memorias_do_estado`` / ``entrada_de_continuacao`` — transporte EXPLÍCITO da memória (u, p, tempo no estado,
  obrigação residual derivada) e dos estados de armazenamento de uma fronteira para a janela seguinte;
* ``custo_eventos_realizado`` — custo de eventos efetivamente INCORRIDO (transições aplicadas), separado do planejado;
* ``DeclaracaoCommitment3C1`` / ``montar_entrada_3c1`` — projeção inventário + cenário + declarações POR UNIDADE →
  ``EntradaCommitment3C1`` (requisitos 3C-1 bloqueantes; estado por unidade nunca distribuído de um agregado).
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
from .cenario import CenarioEMS, ConjuntoPrevisao, DefinicaoTemporal
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
class ExecutorAlgebricoCommitment3C1:
    """Dublê ALGÉBRICO (natureza ``algebrico_referencia``; NÃO é modelo físico) do commitment 3C-1."""
    natureza = "algebrico_referencia"

    def __init__(self, e3: EntradaCommitment3C1, tol: Tolerancias = Tolerancias(), identificador: str = "ref-alg-3C1"):
        self.e3, self.tol, self.identificador = e3, tol, identificador
        self._base = ExecutorAlgebricoReferencia(e3.base, tol, identificador)
        self._disc = discretizar(e3)

    def _T_s(self, uid: str, ligado: bool):
        sp = self.e3.unidade(uid)
        return tempo_s_exato(sp.tempo_min_ligado_min if ligado else sp.tempo_min_desligado_min)

    def avancar(self, estado, consignas, entorno, delta_s) -> PassoAplicado:
        c: list[Constatacao] = []
        dados = False
        escala = max([1.0] + [float(g.p_max_kW.valor) for g in self.e3.base.geradores])
        tolP = self.tol.potencia_abs_kW + self.tol.potencia_rel_escala * max(escala, 1.0)
        for uid, dz in sorted(self._disc.items()):
            st = estado.gerador(uid)
            u, p = consignas.get(f"{uid}|u"), consignas.get(f"{uid}|p")
            if st is None or u is None or p is None:
                continue                                      # o executor 3C-0 constata a ausência
            lig, lig0, p0 = u > 0.5, st.ligado, st.potencia_kW
            a = entorno.get(f"{uid}|disponibilidade")
            if lig and a is not None and a != 1.0:
                c.append(erro("consigna_inexequivel_indisponivel", uid, "u = 1 com disponibilidade REALIZADA nula."))
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


def custo_eventos_realizado(e3: EntradaCommitment3C1, traj: TrajetoriaExecutada) -> ComponenteCusto | None:
    """Custo de eventos INCORRIDO: transições entre estados consecutivos efetivamente aplicados (C_SU, C_SD declarados).
    ``None`` se o termo "eventos" não está no objetivo (nenhum custo não declarado aparece)."""
    if "eventos" not in e3.termos:
        return None
    tot, n_su, n_sd = [], 0, 0
    for a, b in zip(traj.estados, traj.estados[1:]):
        for g in b.geracao:
            ga = a.gerador(g.uid)
            sp = e3.unidade(g.uid)
            if ga is None or sp is None or sp.custo_partida is None:
                continue
            if g.ligado and not ga.ligado:
                tot.append(float(sp.custo_partida.valor))
                n_su += 1
            elif ga.ligado and not g.ligado:
                tot.append(float(sp.custo_parada.valor))
                n_sd += 1
    return ComponenteCusto("eventos", math.fsum(tot), "realizado", f"{n_su} partida(s), {n_sd} parada(s) aplicadas")


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
class DeclaracaoCommitment3C1:
    """Decisões de modelagem do commitment declaradas por quem executa (nenhuma tem valor padrão)."""
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
    estados: dict[str, EstadoGerador] = {}
    cond_u = {x.uid: x for x in decl.unidades}
    gers = [(d, r) for d in inv.dispositivos if d.habilitado and d.modelo.papel_ems == "gerador" for r in recursos_ems(d)]
    for d, r in gers:
        k = str(r)
        cu = cond_u.get(k)
        if cu is None and (d.quantidade or 1) == 1:
            ci = cen.condicao(d.uid)               # registro de UMA unidade: a condição do registro é a da unidade
            if ci is not None and ci.estado_discreto in ("desligada", "em_operacao") and ci.potencia_kW is not None:
                cu = CondicaoInicialUnidade(k, ci.estado_discreto, ci.potencia_kW, ci.tempo_no_estado_s,
                                            ci.potencia_kW.procedencia)
        if cu is None:
            continue                                # montar_entrada constata (estado ausente / por unidade)
        if cu.estado_discreto not in ("desligada", "em_operacao"):
            c.append(pendente("estado_em_partida_nao_representavel", f"unidades[{k}]",
                              "'Em partida' exige o autômato multimodo (M20), não habilitado."))
            continue
        if cu.potencia_kW is None:
            c.append(erro("potencia_inicial_ausente", f"unidades[{k}].potencia_kW", "Potência anterior não declarada."))
            continue
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
        cu = cond_u.get(k)
        tempo = cu.tempo_no_estado_s if cu is not None else (cen.condicao(d.uid).tempo_no_estado_s
                                                            if cen.condicao(d.uid) is not None else None)
        st = estados.get(k)
        sp = unidades[-1]
        T = tempo_s_exato(sp.tempo_min_ligado_min if (st is not None and st.ligado) else sp.tempo_min_desligado_min)
        ob = obrigacao_derivada_s(T, tempo)
        procm = (cu.procedencia if cu is not None else None) or decl.procedencia
        memorias.append(MemoriaCommitmentUnidade(r, tempo, ob, procm))
    e3 = EntradaCommitment3C1(ESQUEMA_3C1, FORMULACAO_3C1, proj.entrada, tuple(unidades), tuple(memorias),
                              decl.politica_permanencia, tuple(decl.termos_adicionais), decl.procedencia)
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


__all__ = ["CondicaoInicialUnidade", "DeclaracaoCommitment3C1", "ResultadoProjecao3C1", "ExecutorAlgebricoCommitment3C1", "PlanoCommitment3C1",
           "custo_eventos_realizado", "entrada_de_continuacao", "estado_inicial_3c1", "hash_plano_commitment", "memorias_do_estado",
           "montar_entrada_3c1", "plano_de_resultado_3c1"]
