"""Fixtures SINTÉTICAS do Piso 3C-4 (EMS hierárquico) — só biblioteca padrão.

Todos os números são dados de TESTE (procedência ``sintetico``): nenhum representa equipamento, previsão, medição,
tarifa (ANDE/distribuidora/mercado) ou contrato reais; perfis tarifários com o rótulo ``SINTÉTICA — não é tarifa real``.
Δ = 60 min (h = 1 h) para que horizontes de 12–24 h tenham poucos intervalos e a aritmética seja exata (η = 1 declarado
salvo indicação). Microrrede de ensaio: carga crítica ``syn-carga``, FV opcional ``syn-fv`` (c_curt declarado), bancos
``syn-bess`` (e ``syn-bess-2`` em H17), PEMFC opcional ``syn-fc`` (curva sintética, T_on/T_off, custos de evento),
PCC conectado com medidores.

``Cenario3C4`` declara TUDO o que define um experimento: perfis previstos (tabela do provedor, independente da verdade),
verdade sintética (só a planta a conhece), tarifas de decisão e de liquidação, limites/disponibilidade do PCC,
parâmetros dos recursos e estado inicial. ``montar`` constrói os objetos de uma missão para uma ESTRATÉGIA (open-loop,
MPC sem sinal, MPC encolhido, hierárquico com cada tipo de sinal, oráculo rotulado) com condições idênticas.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from . import FORMULACAO_3BP
from . import fixtures_3c2 as F2
from . import fixtures_3c3 as F3
from .contracts import (ClasseDemanda, CurvaPWL, Disponibilidade, EspecBateria, EspecGerador, EstadoBateria,
                        EstadoGerador, PotencialRenovavel, UIDRecurso)
from .fixtures import entrada, par
from .fixtures_3c1 import embrulhar, memoria, unidade
from .hierarquia import ESQUEMA_3C4, FORMULACAO_3C4
from .hierarquia.contrato import ConfiguracaoPlanejador3C4, ParametroBateria, TermoTerminal3C4
from .mpc import ESQUEMA_MPC
from .mpc.contrato import ConfiguracaoMPC, PoliticaTerminalMissao
from .ponte.cenario import Realizacao, SerieRecurso
from .ponte.compromisso import FonteDisponibilidadeExecucao
from .provenance import Procedencia
from .series import SerieTemporal
from .timegrid import MalhaTemporal

INICIO = F2.INICIO
DELTA = 60
DEM, FV, FC = F2.DEM, F2.FV, F2.FC
BESS, BESS2 = "syn-bess", "syn-bess-2"
PCC, MED_IMP, MED_EXP = F3.PCC, F3.MED_IMP, F3.MED_EXP
FONTE_VERDADE = "Verdade sintética do simulador 3C-4 (ems_v2/fixtures_3c4.py) — encapsulada na planta"
FONTE_PREV = "Tabela de previsão sintética declarada 3C-4 (ems_v2/fixtures_3c4.py) — independente da verdade"
FONTE_CANAL = "Canal de observação sintético 3C-4"
EMISSAO_R0 = "2025-12-31T12:00:00+00:00"
CURVA_FC = ((5.0, 0.35), (20.0, 1.4))


def proc(caso: str, obs: str = "", fonte: str = "Fixture sintética 3C-4 (ems_v2/fixtures_3c4.py)") -> Procedencia:
    return Procedencia("sintetico", fonte, caso, observacoes=obs)


def serie(gr: str, vals, caso: str, *, emissao: str | None = INICIO, fonte: str | None = None) -> SerieTemporal:
    un = {"potencia": "kW", "disponibilidade": "1"}[gr]
    return SerieTemporal(gr, un, "media_intervalo", INICIO, DELTA * 60, tuple(float(v) for v in vals),
                         proc(caso, fonte=fonte or "Fixture sintética 3C-4 (ems_v2/fixtures_3c4.py)"),
                         fronteira="barramento_liquido" if gr == "potencia" else None, emissao_utc=emissao)


@dataclass(frozen=True)
class Banco:
    uid: str = BESS
    C: float = 20.0
    e0: float = 20.0
    pmax: float = 10.0
    smin: float = 0.0
    smax: float = 1.0
    eta: float = 1.0
    c_thr: float = 0.01
    pcmax: float | None = None          # potência máxima de CARGA (padrão = pmax)


@dataclass(frozen=True)
class Pemfc:
    pmin: float = 5.0
    pmax: float = 20.0
    ligado: bool = False
    p0: float = 0.0
    tempo_s: int = 36000
    Ton_min: float = 180.0
    Toff_min: float = 120.0
    R: float = 1.0
    csu: float = 5.0
    csd: float = 2.0
    msu: float = 0.05
    msd: float = 0.02
    preco_h2: float = 10.0


@dataclass(frozen=True)
class Cenario3C4:
    nome: str
    K: int
    L_prev: tuple[float, ...]
    c_imp: tuple[float, ...]
    L_real: tuple[float, ...] | None = None
    pv_prev: tuple[float, ...] | None = None
    pv_real: tuple[float, ...] | None = None
    c_curt: float = 0.05
    bancos: tuple[Banco, ...] = (Banco(),)
    pemfc: Pemfc | None = None
    imp: tuple[float, ...] | None = None             # limite contratado de importação (padrão do CENÁRIO: 50 kW)
    a_pcc_prev: tuple[float, ...] | None = None
    a_pcc_real: tuple[float, ...] | None = None
    c_exp: tuple[float, ...] | None = None           # None ⇒ somente_importacao
    c_imp_r1: tuple[float, ...] | None = None        # revisão tarifária 1 (decisão)
    emissao_r1: str | None = None
    c_liq_imp: tuple[float, ...] | None = None       # liquidação (padrão: = c_imp)
    a_fc_prev: tuple[float, ...] | None = None
    descricao: str = ""


def _vec(x, K, padrao):
    return tuple(float(v) for v in (x if x is not None else [padrao] * K))


def modelo(c: Cenario3C4, *, rotulo: str = "causal"):
    """Modelo 3C-3 da missão (núcleo 3C-1 + PCC + tarifas de decisão revisão 0)."""
    K, caso = c.K, c.nome
    m = MalhaTemporal(INICIO, DELTA, K, K, K, horizonte_previsao_min=DELTA * K)
    dem = ClasseDemanda(UIDRecurso(DEM), "Carga crítica (fixture 3C-4)", "critica", serie("potencia", c.L_prev, caso))
    ren = []
    termos = ["throughput_bess"]
    if c.pv_prev is not None:
        ren.append(PotencialRenovavel(UIDRecurso(FV), "fv", serie("potencia", c.pv_prev, caso), "antes_da_disponibilidade",
                                      Disponibilidade(serie("disponibilidade", [1] * K, caso)),
                                      par(c.c_curt, "R$/kWh", caso)))
        termos.insert(0, "curtailment_operacional")
    bts, ebs = [], []
    for b in c.bancos:
        bts.append(EspecBateria(UIDRecurso(b.uid), par(b.C, "kWh", caso), par(b.smin, "1", caso), par(b.smax, "1", caso),
                                par(b.eta, "1", caso, "η declarado"), par(b.eta, "1", caso),
                                par(b.pcmax if b.pcmax is not None else b.pmax, "kW", caso), par(b.pmax, "kW", caso),
                                "nao_modelada_alpha_1",
                                Disponibilidade(serie("disponibilidade", [1] * K, caso)),
                                custo_throughput=par(b.c_thr, "R$/kWh", caso)))
        ebs.append(EstadoBateria(UIDRecurso(b.uid), par(b.e0, "kWh", caso, "estado inicial declarado")))
    gers, ests, uns, mems = [], [], [], []
    f = c.pemfc
    if f is not None:
        gers.append(EspecGerador(UIDRecurso(FC), "pemfc", par(f.pmin, "kW", caso), par(f.pmax, "kW", caso),
                                 Disponibilidade(serie("disponibilidade", _vec(c.a_fc_prev, K, 1.0), caso)), "instantanea",
                                 CurvaPWL(CURVA_FC, "sintetica_exata", proc(caso)), par(f.preco_h2, "R$/kg", caso)))
        ests.append(EstadoGerador(UIDRecurso(FC), f.ligado, par(f.p0 if f.ligado else 0.0, "kW", caso,
                                                                 "estado anterior declarado")))
        uns.append(unidade(UIDRecurso(FC), caso, R=f.R, Ton=f.Ton_min, Toff=f.Toff_min, csu=f.csu, csd=f.csd,
                           msu=f.msu, msd=f.msd))
        mems.append(memoria(UIDRecurso(FC), caso, tempo_s=f.tempo_s, T_estado_min=f.Ton_min if f.ligado else f.Toff_min))
        termos.append("combustivel_h2")
    b = entrada(caso, m, formulacao=FORMULACAO_3BP, demandas=[dem], renovaveis=ren, baterias=bts, estados_baterias=ebs,
                geradores=gers, estados_geradores=ests, termos=tuple(termos),
                variante_combustivel="instantanea" if f is not None else None)
    b = replace(b, cenario_uid=F2.CENARIO)
    nuc = embrulhar(b, uns, mems, caso, politica="cumprir_na_janela", termos=("eventos",) if f is not None else ())
    sent = "importacao_e_exportacao" if c.c_exp is not None else "somente_importacao"
    p = F3.pcc(K, caso, sentidos=sent, imp=list(_vec(c.imp, K, 50.0)), exp=50.0, a=list(_vec(c.a_pcc_prev, K, 1.0)),
               medidores=True, delta=DELTA)
    ti = F3.tarifa("importacao", list(c.c_imp), caso, emitido=EMISSAO_R0, delta=DELTA)
    te = F3.tarifa("exportacao", list(c.c_exp), caso, emitido=EMISSAO_R0, delta=DELTA) if c.c_exp is not None else None
    ec = F3.economia(caso, tarifa_imp=ti, tarifa_exp=te, rotulo=rotulo,
                     remuneracao="remunerada" if te is not None else "nao_aplicavel")
    return F3.rede(nuc, p, ec, caso)


def tarifas_decisao(c: Cenario3C4) -> tuple:
    out = [F3.tarifa("importacao", list(c.c_imp), c.nome, emitido=EMISSAO_R0, delta=DELTA)]
    if c.c_imp_r1 is not None:
        out.append(F3.tarifa("importacao", list(c.c_imp_r1), c.nome, emitido=c.emissao_r1, revisao=1, delta=DELTA))
    if c.c_exp is not None:
        out.append(F3.tarifa("exportacao", list(c.c_exp), c.nome, emitido=EMISSAO_R0, delta=DELTA))
    return tuple(out)


def politica_ajuste(c: Cenario3C4):
    from .rede.execucao import PoliticaAjustePCC
    K = c.K
    li = F3.tarifa("importacao", list(c.c_liq_imp or c.c_imp), f"{c.nome}-liq", natureza="aplicavel_liquidacao",
                   uid="syn-liquidacao-importacao", delta=DELTA)
    le = F3.tarifa("exportacao", list(c.c_exp), f"{c.nome}-liq", natureza="aplicavel_liquidacao",
                   uid="syn-liquidacao-exportacao", delta=DELTA) if c.c_exp is not None else None
    _ = K
    return PoliticaAjustePCC("ajuste_local_algebrico", "limitada_pela_disponibilidade", "energia_medida_tarifa_aplicavel",
                             li, le, None, None, proc("ajuste", "política SINTÉTICA de ensaio"),
                             "Ensaio 3C-4: ajuste algébrico local do PCC declarado (não é controle primário)")


def configuracao_rede(c: Cenario3C4):
    return F3.configuracao_rede(politica_ajuste(c), tarifas_decisao(c))


def configuracao_mpc(nome: str, c: Cenario3C4, N: int, m: int, *, rotulo: str = "causal", H_f: int | None = None,
                     perm_inter: str = "cumprir_na_janela", perm_final: str = "cumprir_na_janela") -> ConfiguracaoMPC:
    mal = MalhaTemporal(INICIO, DELTA, N, m, c.K, horizonte_previsao_min=DELTA * (H_f if H_f is not None else c.K))
    pt = PoliticaTerminalMissao("janela_reduzida", perm_inter, perm_final,
                                "Ensaio 3C-4: janela reduzida ao fim da missão; permanência declarada", proc("terminal"))
    return ConfiguracaoMPC(ESQUEMA_MPC, F2.identidade(nome), mal, "simulacao_causal_laco_fechado", rotulo, pt,
                           F2.aceitacao(), F2.politica_falhas(), "registrar_sem_reconciliar", proc(nome))


def termo_longo(tipo: str = "nenhum_declarado", *, valores: dict | None = None) -> TermoTerminal3C4:
    j = {"nenhum_declarado": "Fim da missão experimental: energia/estado residuais avaliados em ZERO por declaração "
                             "explícita, igual para todas as estratégias comparadas (miopia terminal reconhecida)",
         "valor_linear_declarado": "Valor residual linear DECLARADO para o ensaio (sintético)",
         "energia_minima_declarada": "Energia mínima terminal DECLARADA para o ensaio (sintética)"}[tipo]
    vs = tuple(ParametroBateria(u, float(v)) for u, v in sorted((valores or {}).items()))
    return TermoTerminal3C4(tipo, vs if tipo == "valor_linear_declarado" else (),
                            vs if tipo == "energia_minima_declarada" else (), None, j, proc("phi_l"))


def configuracao_planejador(*, H_L: int, tipo_sinal: str = "custo_futuro_pwl", termo=None, periodo: int = 1,
                            pontos: int = 5, pontos_max: int = 9, tol_R: float = 1e-6, tol_dom: float = 0.5,
                            delta: float | None = None, rho: float | None = None, max_modos: int = 4,
                            degradacao: str = "sem_valor_futuro_rotulado",
                            permanencia_fim: str = "cumprir_na_janela") -> ConfiguracaoPlanejador3C4:
    return ConfiguracaoPlanejador3C4(
        ESQUEMA_3C4, FORMULACAO_3C4, H_L, "reduzido_ao_fim_da_missao", termo or termo_longo(), permanencia_fim,
        "a_cada_janela" if periodo == 1 else "periodica", periodo, tipo_sinal, pontos, pontos_max, tol_R, tol_dom,
        delta if tipo_sinal == "valor_marginal_local" else None,
        rho if tipo_sinal == "referencia_energia_branda" else None, max_modos, degradacao,
        "Ensaio 3C-4: parâmetros do planejador DECLARADOS (sintéticos)", proc("planejador"))


def _series_recursos(c: Cenario3C4, real: bool, *, emissao, fonte):
    K = c.K
    L = c.L_real if (real and c.L_real is not None) else c.L_prev
    out = {(DEM, "potencia"): serie("potencia", L, c.nome, emissao=emissao, fonte=fonte)}
    if c.pv_prev is not None:
        pv = c.pv_real if (real and c.pv_real is not None) else c.pv_prev
        out[(FV, "potencia")] = serie("potencia", pv, c.nome, emissao=emissao, fonte=fonte)
        out[(FV, "disponibilidade")] = serie("disponibilidade", [1] * K, c.nome, emissao=emissao, fonte=fonte)
    for b in c.bancos:
        out[(b.uid, "disponibilidade")] = serie("disponibilidade", [1] * K, c.nome, emissao=emissao, fonte=fonte)
    if c.pemfc is not None:
        out[(FC, "disponibilidade")] = serie("disponibilidade", _vec(c.a_fc_prev, K, 1.0), c.nome, emissao=emissao,
                                             fonte=fonte)
    a = c.a_pcc_real if (real and c.a_pcc_real is not None) else c.a_pcc_prev
    out[(PCC, "disponibilidade")] = serie("disponibilidade", _vec(a, K, 1.0), c.nome, emissao=emissao, fonte=fonte)
    return out


def tabela(c: Cenario3C4) -> dict:
    """Tabela DECLARADA do provedor (perfis previstos; independente do objeto da verdade)."""
    return _series_recursos(c, False, emissao=INICIO, fonte=FONTE_PREV)


def verdade(c: Cenario3C4) -> Realizacao:
    s = _series_recursos(c, True, emissao=None, fonte=FONTE_VERDADE)
    return Realizacao(f"syn-verdade-{c.nome.lower()}", "sintetica",
                      tuple(SerieRecurso(u, g, x) for (u, g), x in sorted(s.items())), proc(c.nome, fonte=FONTE_VERDADE))


def latencias(c: Cenario3C4, lat: int = 0) -> dict:
    d = {k: lat for k in _series_recursos(c, True, emissao=None, fonte=FONTE_VERDADE)}
    d.update({(MED_IMP, "potencia"): lat, (MED_EXP, "potencia"): lat})
    return d


def fontes(c: Cenario3C4) -> dict:
    return {FC: FonteDisponibilidadeExecucao(FC, "observada")} if c.pemfc is not None else {}


BASES = {FV: "antes_da_disponibilidade"}

# ------------------------------------------------------------------------------------------------ cenários
PLANO_12 = (0.5,) * 8 + (1.5, 1.5) + (0.5, 0.5)


def h2_pico_futuro(**kw) -> Cenario3C4:
    """H2 — demanda 10 kW constante (12 h); banco C = 20 kWh, e0 = 20, P̄ = 10 kW, η = 1, c_thr = 0,01; PCC só
    importação (50 kW); tarifa 0,5 R$/kWh salvo PICO 1,5 R$/kWh nas horas 8–9 (fora do horizonte curto em τ_0).
    Analítico: sem coordenação (N = 3) o MPC descarrega nas horas 0–1 (economiza 0,49/kWh dentro da janela; nada vale
    guardar) e importa no pico: custo = 0,5·(6·10) + 1,5·20 + 0,5·20 + 0,01·20 = R$ 70,2. Com custo de continuação
    (H_L = 10) o banco é preservado até o pico: 0,5·80 + 0,5·20 + 0,01·20 = R$ 50,2. Energia final 0 nos dois casos
    (condições terminais comparáveis)."""
    kw.setdefault("bancos", (Banco(pcmax=5.0),))
    return Cenario3C4("H2", 12, (10.0,) * 12, PLANO_12, **kw)


def h1_tarifa_plana(**kw) -> Cenario3C4:
    """H1 — igual a H2 com tarifa plana 0,5: nenhum incentivo a deslocar energia; a coordenação não deve alterar o custo
    (custo = 0,5·100 + 0,01·20 = R$ 50,2 para todas as estratégias que esvaziam o banco)."""
    return Cenario3C4("H1", 12, (10.0,) * 12, (0.5,) * 12, **kw)


def h3_pico_no_horizonte_curto(**kw) -> Cenario3C4:
    """H3 — pico nas horas 1–2 (dentro do horizonte curto N = 3 já em τ_0): os dois MPC enxergam o evento."""
    return Cenario3C4("H3", 12, (10.0,) * 12, (0.5, 1.5, 1.5) + (0.5,) * 9, **kw)


def h4_pico_deslocado(hora: int = 6, **kw) -> Cenario3C4:
    """H4 — pico de 2 h começando em ``hora`` (previsão causal desloca o evento)."""
    c = [0.5] * 12
    c[hora] = c[hora + 1] = 1.5
    return Cenario3C4(f"H4h{hora}", 12, (10.0,) * 12, tuple(c), **kw)


def h7_limite_importacao(**kw) -> Cenario3C4:
    """H7 — tarifa PLANA 0,5; PCC limitado a 0 kW nas horas 8–9 (limite contratado declarado). Sem coordenação o banco
    é esvaziado cedo e a janela de τ_6 é INVIÁVEL (sem energia inventada); com custo de continuação o domínio da
    cauda exige E >= 20 kWh na fronteira (valor de reserva por restrição FÍSICA, não por preço)."""
    imp = (50.0,) * 8 + (0.0, 0.0) + (50.0, 50.0)
    kw.setdefault("bancos", (Banco(pcmax=5.0),))
    return Cenario3C4("H7", 12, (10.0,) * 12, (0.5,) * 12, imp=imp, **kw)


def h8_indisponibilidade_pcc(**kw) -> Cenario3C4:
    """H8 — tarifa plana; indisponibilidade PREVISTA do PCC (a = 0) nas horas 8–9 (também realizada)."""
    a = (1.0,) * 8 + (0.0, 0.0) + (1.0, 1.0)
    kw.setdefault("bancos", (Banco(pcmax=5.0),))
    return Cenario3C4("H8", 12, (10.0,) * 12, (0.5,) * 12, a_pcc_prev=a, a_pcc_real=a, **kw)


def h9_pemfc(**kw) -> Cenario3C4:
    """H9 — PEMFC (5–20 kW, T_on 3 h, T_off 2 h, C_SU 5, C_SD 2 R$/evento, H₂ 10 R$/kg) + banco 10 kWh; pico 2,5
    R$/kWh nas horas 7–10 com demanda 25 kW (PCC 50 kW). O planejador avalia a cauda por MODO (PEMFC ligada/desligada
    na fronteira) — o valor de estar ligado (memória/partida) NÃO é atribuído ao banco."""
    c = (0.5,) * 7 + (2.5,) * 4 + (0.5,)
    L = (10.0,) * 7 + (25.0,) * 4 + (10.0,)
    return Cenario3C4("H9", 12, L, c, bancos=(Banco(C=10.0, e0=10.0, pmax=10.0),), pemfc=Pemfc(), **kw)


def h17_dois_bancos(**kw) -> Cenario3C4:
    """H17 — dois bancos (10 kWh / 5 kW e 10 kWh / 5 kW) com o pico de H2: valor de continuação 2D por envoltória
    convexa VERIFICADA (sem presumir separabilidade)."""
    return Cenario3C4("H17", 12, (10.0,) * 12, PLANO_12, bancos=(Banco(BESS, 10.0, 10.0, 5.0), Banco(BESS2, 10.0, 10.0,
                                                                                                        5.0)), **kw)


__all__ = ["BASES", "BESS", "BESS2", "Banco", "Cenario3C4", "DELTA", "DEM", "FC", "FONTE_CANAL", "FONTE_PREV",
           "FONTE_VERDADE", "FV", "INICIO", "MED_EXP", "MED_IMP", "PCC", "PLANO_12", "Pemfc", "configuracao_mpc",
           "configuracao_planejador", "configuracao_rede", "fontes", "h17_dois_bancos", "h1_tarifa_plana",
           "h2_pico_futuro", "h3_pico_no_horizonte_curto", "h4_pico_deslocado", "h7_limite_importacao",
           "h8_indisponibilidade_pcc", "h9_pemfc", "latencias", "modelo", "politica_ajuste", "proc", "serie", "tabela",
           "tarifas_decisao", "termo_longo", "verdade"]
_ = (EspecGerador, field)
