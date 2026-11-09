"""Fixtures SINTÉTICAS do Piso 3C-1 (commitment dinâmico) — só biblioteca padrão.

Todos os números são dados de TESTE (procedência ``sintetico``), declarados caso a caso; nenhum representa equipamento
do SEEDS2. Rampas, permanências, limites de partida/parada, custos e massas de evento NÃO existem no inventário real
(brechas em ``docs/ems_v2/BRECHAS_3C1.md``): aparecem aqui só para exercitar a formulação. Os resultados esperados
estão nas docstrings, obtidos por raciocínio analítico ou por enumeração independente nos testes — nunca pelo Pyomo.
"""
from __future__ import annotations

from . import FORMULACAO_3BP, FORMULACAO_3C1
from .compromisso.contrato import (ESQUEMA_3C1, EntradaCommitment3C1, EspecCommitmentUnidade, MemoriaCommitmentUnidade,
                                   PoliticaPermanenciaTerminal, obrigacao_derivada_s, tempo_s_exato)
from .contracts import ClasseDemanda, CurvaPWL, EspecGerador, EstadoBateria, EstadoGerador, PoliticaServico, UIDRecurso
from .fixtures import bateria, demanda, disp, entrada, fv, malha, par, pot, proc, serie

JUST = "Caso analítico 3C-1: unidade quente, transição dentro de um intervalo (hipótese B05 instantânea declarada)"


def uid(equip: str, k: int | None = None) -> UIDRecurso:
    return UIDRecurso(equip, k)


def gerador(u: UIDRecurso, tecnologia: str, pmin: float, pmax: float, N: int, delta: float, caso: str, *,
            ligado: bool, p_ant: float, curva=None, preco_h2=None, a=None):
    g = EspecGerador(u, tecnologia, par(pmin, "kW", caso), par(pmax, "kW", caso), disp(a or [1] * N, delta, caso),
                     "instantanea", None if curva is None else CurvaPWL(tuple(curva), "sintetica_exata", proc(caso)),
                     None if preco_h2 is None else par(preco_h2, "R$/kg", caso))
    return g, EstadoGerador(u, ligado, par(p_ant if ligado else 0.0, "kW", caso, "estado anterior declarado"))


def unidade(u: UIDRecurso, caso: str, *, R=100.0, Rd=None, Ton=0.0, Toff=0.0, limites="rampa_convencional", Sp=None,
            Sd=None, abstracao="instantanea_unidade_quente", csu=None, csd=None, msu=None, msd=None,
            sem_rampa=False, sem_tempos=False) -> EspecCommitmentUnidade:
    return EspecCommitmentUnidade(
        u, abstracao, limites, None if sem_rampa else par(R, "kW/min", caso),
        None if sem_rampa else par(R if Rd is None else Rd, "kW/min", caso),
        None if sem_tempos else par(Ton, "min", caso), None if sem_tempos else par(Toff, "min", caso),
        None if Sp is None else par(Sp, "kW", caso), None if Sd is None else par(Sd, "kW", caso),
        None if csu is None else par(csu, "R$/evento", caso), None if csd is None else par(csd, "R$/evento", caso),
        None if msu is None else par(msu, "kg", caso), None if msd is None else par(msd, "kg", caso),
        JUST if abstracao == "instantanea_unidade_quente" else "Estado mantido na janela (sem transição representável)")


def memoria(u: UIDRecurso, caso: str, *, tempo_s: int, T_estado_min: float) -> MemoriaCommitmentUnidade:
    """Memória DECLARADA na fixture: a obrigação é calculada aqui pela regra pública ⌈max(0, T − tempo)⌉ (s)."""
    ob = obrigacao_derivada_s(tempo_s_exato(par(T_estado_min, "min", caso)), tempo_s)
    return MemoriaCommitmentUnidade(u, tempo_s, ob, proc(caso, "memória operativa declarada na fixture"))


def embrulhar(base, unidades, memorias, caso: str, *, politica="obrigacao_residual_vinculante", termos=()):
    return EntradaCommitment3C1(
        ESQUEMA_3C1, FORMULACAO_3C1, base, tuple(unidades), tuple(memorias),
        PoliticaPermanenciaTerminal(politica, f"Política terminal declarada para o caso {caso}", proc(caso)),
        tuple(termos), proc(caso, "Entrada 3C-1 sintética; não é estudo físico."))


def _base(caso, m, **kw):
    return entrada(caso, m, formulacao=FORMULACAO_3BP, **kw)


def _bat(N, d, caso, *, e0=50.0, c_thr=1.0, pmax=50.0, C=100.0):
    b = bateria("syn-bess", N, d, caso, C=C, pcmax=pmax, pdmax=pmax, c_thr=c_thr, eta_c=1.0, eta_d=1.0,
                obs="η = 1 declarado na fixture (aritmética exata)")
    return b, EstadoBateria(UIDRecurso("syn-bess"), par(e0, "kWh", caso))


G = uid("syn-ter")


# ------------------------------------------------------------------------- Caso A — transições binárias
def caso_a(csu=5.0, csd=2.0):
    """Térmica única (P_min 10, P_max 50) OFF; demanda [0, 30, 30, 0] (Δ = 15 min). O balanço FORÇA
    u = [0, 1, 1, 0], p = [0, 30, 30, 0], y = [0, 1, 0, 0], z = [0, 0, 0, 1]; custo de eventos = C_SU + C_SD = R$ 7."""
    c, N, d = "3C1-A", 4, 15
    m = malha(d, N)
    g, st = gerador(G, "termica", 10.0, 50.0, N, d, c, ligado=False, p_ant=0.0)
    b = _base(c, m, demandas=[demanda("syn-carga", [0, 30, 30, 0], d, c)], geradores=[g], estados_geradores=[st])
    return embrulhar(b, [unidade(G, c, csu=csu, csd=csd)], [memoria(G, c, tempo_s=7200, T_estado_min=0.0)], c,
                     termos=("eventos",))


# ------------------------------------------------------------------------- Caso B — rampa
def caso_b(com_bateria=True, R=1.0, d=5):
    """Térmica ON em p^{-1} = 10 kW, R⁺ = R⁻ = 1 kW/min, Δ = 5 min ⇒ variação máxima 5 kW por intervalo. Demanda 30 kW
    constante; o banco (c_thr = 1 R$/kWh) cobre o déficit. Ótimo ÚNICO: p = [15, 20, 25, 30], P_d = [15, 10, 5, 0];
    custo throughput = (15 + 10 + 5)·(5/60) = R$ 2,5. Sem banco: inviável (30 − 10 > 5 kW)."""
    c, N = "3C1-B", 4
    m = malha(d, N)
    g, st = gerador(G, "termica", 10.0, 50.0, N, d, c, ligado=True, p_ant=10.0)
    kw = {}
    if com_bateria:
        bt, eb = _bat(N, d, c)
        kw = dict(baterias=[bt], estados_baterias=[eb], termos=("throughput_bess",))
    b = _base(c, m, demandas=[demanda("syn-carga", [30] * N, d, c)], geradores=[g], estados_geradores=[st], **kw)
    return embrulhar(b, [unidade(G, c, R=R)], [memoria(G, c, tempo_s=7200, T_estado_min=0.0)], c)


# ------------------------------------------------------------------------- Caso C — tempo mínimo ON
def caso_c(Ton=45.0):
    """Térmica OFF (P_min 10); demanda [20, 0, 0, 0]; banco vazio (e0 = 0) absorve excedente com c_thr = 1. Δ = 15 min.
    T_on = 45 min ⇒ U = 3: a unidade parte em t = 0 e fica ON em t = 1, 2 a P_min carregando o banco (P_c = 10);
    para em t = 3. u = [1, 1, 1, 0]; custo = 1·(10 + 10)·0,25 = R$ 5. Com T_on = 0: u = [1, 0, 0, 0], custo R$ 0."""
    c, N, d = "3C1-C", 4, 15
    m = malha(d, N)
    g, st = gerador(G, "termica", 10.0, 50.0, N, d, c, ligado=False, p_ant=0.0)
    bt, eb = _bat(N, d, c, e0=0.0)
    b = _base(c, m, demandas=[demanda("syn-carga", [20, 0, 0, 0], d, c)], geradores=[g], estados_geradores=[st],
              baterias=[bt], estados_baterias=[eb], termos=("throughput_bess",))
    return embrulhar(b, [unidade(G, c, Ton=Ton)], [memoria(G, c, tempo_s=7200, T_estado_min=0.0)], c)


# ------------------------------------------------------------------------- Caso D — tempo mínimo OFF
def caso_d(Toff=45.0):
    """Térmica ON a 10 kW; demanda [10, 0, 0, 20]; banco (e0 = 50, c_thr = 1); C_SU = C_SD = 0,5; Δ = 15 min.
    Sem T_off: manter ON em t = 0, desligar em t = 1 e religar em t = 3 custa R$ 1 (ótimo: u = [1, 0, 0, 1]).
    Com T_off = 45 min (D = 3) esse religamento é PROIBIDO (só 2 intervalos OFF). Enumeração das alternativas:
    desligar em t = 0 (banco serve 10 kW: R$ 2,5) e religar em t = 3 após EXATAMENTE D = 3 intervalos OFF
    (R$ 1 de eventos) ⇒ R$ 3,5 — ótimo único: u = [0, 0, 0, 1], z_0 = 1, y_3 = 1. (Manter ON custa R$ 5;
    desligar em t = 1 e servir t = 3 pelo banco custa R$ 5,5.)"""
    c, N, d = "3C1-D", 4, 15
    m = malha(d, N)
    g, st = gerador(G, "termica", 10.0, 50.0, N, d, c, ligado=True, p_ant=10.0)
    bt, eb = _bat(N, d, c, e0=50.0)
    b = _base(c, m, demandas=[demanda("syn-carga", [10, 0, 0, 20], d, c)], geradores=[g], estados_geradores=[st],
              baterias=[bt], estados_baterias=[eb], termos=("throughput_bess",))
    return embrulhar(b, [unidade(G, c, Toff=Toff, csu=0.5, csd=0.5)], [memoria(G, c, tempo_s=7200, T_estado_min=0.0)],
                     c, termos=("eventos",))


# ------------------------------------------------------------------------- Caso E — obrigação herdada
def caso_e(ligado=False, tempo_s=900, T=45.0):
    """Obrigação herdada (Δ = 15 min). OFF há 15 min com T_off = 45 ⇒ obrigação 1800 s ⇒ u_0 = u_1 = 0; demanda
    20 kW servida pelo banco (c_thr = 1) até a unidade poder partir: u = [0, 0, 1, 1], custo 2·20·0,25 = R$ 10.
    ON há 15 min com T_on = 45 e demanda 0: u_0 = u_1 = 1 a P_min (banco carrega 10 kW), u = [1, 1, 0, 0], R$ 5."""
    c, N, d = "3C1-E", 4, 15
    m = malha(d, N)
    g, st = gerador(G, "termica", 10.0, 50.0, N, d, c, ligado=ligado, p_ant=10.0)
    bt, eb = _bat(N, d, c, e0=50.0)
    L = [0] * N if ligado else [20] * N
    b = _base(c, m, demandas=[demanda("syn-carga", L, d, c)], geradores=[g], estados_geradores=[st], baterias=[bt],
              estados_baterias=[eb], termos=("throughput_bess",))
    un = unidade(G, c, Ton=T if ligado else 0.0, Toff=0.0 if ligado else T)
    return embrulhar(b, [un], [memoria(G, c, tempo_s=tempo_s, T_estado_min=T)], c)


# ------------------------------------------------------------------------- Caso F — borda do horizonte
def caso_f(politica="cumprir_na_janela", N=4):
    """Borda (Δ = 15 min, N = 4): térmica OFF (P_min 10), T_on = 45 (U = 3); demanda [0, 0, 0, 30]; banco (c_thr = 1).
    ``cumprir_na_janela``: partidas em t = 2 e t = 3 proibidas (t + 3 > 4). Opções: banco serve 30 kW em t = 3
    (R$ 7,5) ou partir em t = 1 e completar U = 3 dentro da janela (P_c = 10 em t = 1, 2 ⇒ R$ 5): ótimo
    u = [0, 1, 1, 1], obrigação residual nula, garantia ``completa_na_janela``.
    ``obrigacao_residual_vinculante``: partir em t = 3 (custo R$ 0) e exportar obrigação residual de 2 intervalos
    (1800 s) — garantia ``residual_vinculante``, nunca "completa"."""
    c, d = "3C1-F", 15
    m = malha(d, N)
    g, st = gerador(G, "termica", 10.0, 50.0, N, d, c, ligado=False, p_ant=0.0)
    bt, eb = _bat(N, d, c, e0=50.0)
    L = [0] * (N - 1) + [30]
    b = _base(c, m, demandas=[demanda("syn-carga", L, d, c)], geradores=[g], estados_geradores=[st], baterias=[bt],
              estados_baterias=[eb], termos=("throughput_bess",))
    return embrulhar(b, [unidade(G, c, Ton=45.0)], [memoria(G, c, tempo_s=7200, T_estado_min=0.0)], c, politica=politica)


# ------------------------------------------------------------------------- Caso G — várias unidades do mesmo bloco
def caso_g():
    """Bloco ``syn-ter`` com 2 unidades (#1, #2), Δ = 15 min, T_on = T_off = 45 (U = D = 3), C_SU = 1, C_SD = 0,5.
    #1 ON a 20 kW há 1 h (sem obrigação); #2 OFF há 15 min (obrigação OFF 1800 s ⇒ u_0 = u_1 = 0). Demanda
    [20, 20, 45, 45]; P_max = 30 por unidade; sem banco. #2 só pode partir em t = 2 (e precisa: 45 > 30):
    u#1 = [1, 1, 1, 1], u#2 = [0, 0, 1, 1]; eventos: 1 partida de #2; custo R$ 1. Nenhuma potência agregada é
    distribuída: cada unidade tem estado e memória próprios."""
    c, N, d = "3C1-G", 4, 15
    m = malha(d, N)
    u1, u2 = uid("syn-ter", 1), uid("syn-ter", 2)
    g1, s1 = gerador(u1, "termica", 10.0, 30.0, N, d, c, ligado=True, p_ant=20.0)
    g2, s2 = gerador(u2, "termica", 10.0, 30.0, N, d, c, ligado=False, p_ant=0.0)
    b = _base(c, m, demandas=[demanda("syn-carga", [20, 20, 45, 45], d, c)], geradores=[g1, g2],
              estados_geradores=[s1, s2])
    un = [unidade(x, c, Ton=45.0, Toff=45.0, csu=1.0, csd=0.5) for x in (u1, u2)]
    mem = [memoria(u1, c, tempo_s=3600, T_estado_min=45.0), memoria(u2, c, tempo_s=900, T_estado_min=45.0)]
    return embrulhar(b, un, mem, c, termos=("eventos",))


# ------------------------------------------------------------------------- Caso H — ótimo por enumeração
CURVA_H = ((5.0, 0.4), (20.0, 1.3))


def caso_h():
    """Problema pequeno (N = 4, Δ = 60 min) com ótimo obtido por ENUMERAÇÃO EXAUSTIVA independente (2⁸ programas ×
    LP racional exato; ``tests/ems_v2/enumeracao_3c1.py``):

    * térmica ``syn-ter`` (P 10–40 kW; R = 0,5 kW/min ⇒ 30 kW/h; ``rampa_convencional``; T_on = 120 ⇒ U = 2;
      T_off = 60; C_SU = 6, C_SD = 1), OFF há 2 h;
    * PEMFC ``syn-fc`` (curva sintética linear (5; 0,4)–(20; 1,3) kg/h; c_H = 4 R$/kg; R = 1 kW/min; S⁺ = S⁻ = 20
      declarados; T_on = T_off = 60; C_SU = 1; C_SD = 0,5; m^SU = 0,1 kg; m^SD = 0,05 kg), ON a 10 kW há 1 h;
    * FV potencial [30, 10, 0, 25] kW (c_curt = 0,2 R$/kWh); demanda [20, 35, 40, 15] kW; serviço duro."""
    c, N, d = "3C1-H", 4, 60
    m = malha(d, N)
    gt, st_t = gerador(uid("syn-ter"), "termica", 10.0, 40.0, N, d, c, ligado=False, p_ant=0.0)
    gf, st_f = gerador(uid("syn-fc"), "pemfc", 5.0, 20.0, N, d, c, ligado=True, p_ant=10.0, curva=CURVA_H, preco_h2=4.0)
    b = _base(c, m, demandas=[demanda("syn-carga", [20, 35, 40, 15], d, c)],
              renovaveis=[fv("syn-fv", [30, 10, 0, 25], [1] * N, d, c, c_curt=0.2)], geradores=[gt, gf],
              estados_geradores=[st_t, st_f], termos=("curtailment_operacional", "combustivel_h2"),
              variante_combustivel="instantanea")
    ut = unidade(uid("syn-ter"), c, R=0.5, Ton=120.0, Toff=60.0, csu=6.0, csd=1.0)
    uf = unidade(uid("syn-fc"), c, R=1.0, Ton=60.0, Toff=60.0, limites="declarados", Sp=20.0, Sd=20.0, csu=1.0,
                 csd=0.5, msu=0.1, msd=0.05)
    mem = [memoria(uid("syn-ter"), c, tempo_s=7200, T_estado_min=60.0),
           memoria(uid("syn-fc"), c, tempo_s=3600, T_estado_min=60.0)]
    return embrulhar(b, [ut, uf], mem, c, termos=("eventos",))


# ------------------------------------------------------------------------- Caso I — inviabilidade verdadeira
def caso_i_rampa():
    """Térmica ON a 10 kW, rampa 1 kW/min × 5 min = 5 kW; demanda 30 kW; nenhuma outra fonte ⇒ INVIÁVEL."""
    return caso_b(com_bateria=False)


def caso_i_permanencia():
    """Térmica OFF há 15 min com T_off = 45 (obrigação 1800 s); demanda 20 kW em todos os intervalos; sem outra
    fonte ⇒ INVIÁVEL (sem folgas ocultas: nenhuma variável de déficit existe em serviço duro)."""
    c, N, d = "3C1-I", 4, 15
    m = malha(d, N)
    g, st = gerador(G, "termica", 10.0, 50.0, N, d, c, ligado=False, p_ant=0.0)
    b = _base(c, m, demandas=[demanda("syn-carga", [20] * N, d, c)], geradores=[g], estados_geradores=[st])
    return embrulhar(b, [unidade(G, c, Toff=45.0)], [memoria(G, c, tempo_s=900, T_estado_min=45.0)], c)


# ------------------------------------------------------------------------- Caso J — janelas consecutivas
def caso_j(N=8, inicio_indice=0, L=None, estado=None, memoria_g=None, e0=50.0, termos_ev=True):
    """Missão de 8 intervalos de 15 min. Térmica (P 10–40; R = 1 kW/min ⇒ 15 kW/intervalo; T_on = 45, T_off = 30;
    C_SU = 2, C_SD = 1) + banco (c_thr = 0,1). Usada inteira (N = 8) ou em duas janelas de 4 com estado transportado.
    ``inicio_indice``/``estado``/``memoria_g`` permitem montar a 2ª janela a partir da fronteira k = 4."""
    from datetime import datetime, timedelta, timezone
    from .fixtures import INICIO
    from .timegrid import MalhaTemporal
    c, d = "3C1-J", 15
    L_all = L or [5, 25, 30, 35, 10, 5, 30, 30]
    Lw = L_all[inicio_indice:inicio_indice + N]
    t0 = (datetime.fromisoformat(INICIO) + timedelta(minutes=d * inicio_indice)).astimezone(timezone.utc).isoformat()
    m = MalhaTemporal(t0, d, N, N, N, horizonte_previsao_min=d * N)
    ligado, p_ant = (False, 0.0) if estado is None else estado[:2]

    def _ser(gr, un, vals, fr=None):
        from .series import SerieTemporal
        return SerieTemporal(gr, un, "media_intervalo", t0, d * 60, tuple(float(v) for v in vals), proc(c),
                             fronteira=fr, emissao_utc=t0)
    from .contracts import Disponibilidade, EspecBateria
    g = EspecGerador(G, "termica", par(10.0, "kW", c), par(40.0, "kW", c), Disponibilidade(_ser("disponibilidade", "1",
                     [1] * N)), "instantanea")
    st = EstadoGerador(G, ligado, par(p_ant, "kW", c, "estado transportado" if estado else "estado declarado"))
    bt = EspecBateria(UIDRecurso("syn-bess"), par(100.0, "kWh", c), par(0.0, "1", c), par(1.0, "1", c), par(1.0, "1", c),
                      par(1.0, "1", c), par(40.0, "kW", c), par(40.0, "kW", c), "nao_modelada_alpha_1",
                      Disponibilidade(_ser("disponibilidade", "1", [1] * N)), custo_throughput=par(0.1, "R$/kWh", c))
    eb = EstadoBateria(UIDRecurso("syn-bess"), par(e0 if estado is None else estado[2], "kWh", c))
    dem = ClasseDemanda(UIDRecurso("syn-carga"), "Carga (fixture)", "critica", _ser("potencia", "kW", Lw,
                                                                                    "barramento_liquido"))
    b = entrada(c, m, formulacao=FORMULACAO_3BP, demandas=[dem], geradores=[g], estados_geradores=[st], baterias=[bt],
                estados_baterias=[eb], termos=("throughput_bess",))
    mem = memoria_g or memoria(G, c, tempo_s=7200, T_estado_min=0.0)
    return embrulhar(b, [unidade(G, c, R=1.0, Ton=45.0, Toff=30.0, csu=2.0, csd=1.0)], [mem], c,
                     termos=("eventos",) if termos_ev else ())


# ------------------------------------------------------------------------- PEMFC (abstração instantânea)
def pemfc_instantanea(com_massas=True):
    """PEMFC (curva sintética A06) OFF; demanda [0, 15, 15, 0] (Δ = 1 min); c_H = 10 R$/kg; m^SU = 0,002 kg,
    m^SD = 0,001 kg. Abstração INSTANTÂNEA declarada (aviso: não é validação física)."""
    from .fixtures_3b import CURVA_A06
    c, N, d = "3C1-PEMFC", 4, 1
    m = malha(d, N)
    f = uid("syn-fc")
    g, st = gerador(f, "pemfc", 10.0, 20.0, N, d, c, ligado=False, p_ant=0.0, curva=CURVA_A06, preco_h2=10.0)
    b = _base(c, m, demandas=[demanda("syn-carga", [0, 15, 15, 0], d, c)], geradores=[g], estados_geradores=[st],
              termos=("combustivel_h2",), variante_combustivel="instantanea")
    un = unidade(f, c, R=20.0, limites="declarados", Sp=20.0, Sd=20.0, msu=0.002 if com_massas else None,
                 msd=0.001 if com_massas else None)
    return embrulhar(b, [un], [memoria(f, c, tempo_s=600, T_estado_min=0.0)], c)


# ------------------------------------------------------------------------- 3B-P embrulhado (retrocompatibilidade)
def de_3bp(e_3bp, caso="3C1-RETRO", abstracao="transicoes_bloqueadas"):
    """Embrulha uma entrada 3B-P com compromisso CONSTANTE: cada gerador recebe abstração ``transicoes_bloqueadas``
    (estado mantido) e rampas que não restringem (R = (P_max − 0)/Δ declarado). Serve para comparar com o 3B-P."""
    d = float(e_3bp.malha.delta_min)
    uns = []
    for g in e_3bp.geradores:
        R = float(g.p_max_kW.valor) / d * 2.0
        uns.append(unidade(g.uid, caso, R=R, abstracao=abstracao, sem_tempos=True))
    return embrulhar(e_3bp, uns, [], caso)


__all__ = ["CURVA_H", "G", "caso_a", "caso_b", "caso_c", "caso_d", "caso_e", "caso_f", "caso_g", "caso_h",
           "caso_i_permanencia", "caso_i_rampa", "caso_j", "de_3bp", "embrulhar", "gerador", "memoria",
           "pemfc_instantanea", "uid", "unidade"]
_ = (pot, serie, PoliticaServico, fv)
