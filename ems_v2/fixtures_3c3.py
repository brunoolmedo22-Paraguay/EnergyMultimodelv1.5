"""Fixtures SINTÉTICAS do Piso 3C-3 (PCC, tarifas, intercâmbio) — só biblioteca padrão.

Todos os números são dados de TESTE (procedência ``sintetico``): nenhum representa a rede, a concessionária, tarifas da
ANDE ou de qualquer distribuidora, preços spot, contratos ou regras regulatórias reais. Os perfis tarifários levam o
rótulo ``SINTÉTICA — não é tarifa real``. Resultados esperados nas docstrings: obtidos por raciocínio analítico (nunca
pelo Pyomo). Δ = 15 min ⇒ h = 0,25 h.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from . import FORMULACAO_3BP
from .contracts import Disponibilidade, EstadoBateria, UIDRecurso
from .fixtures import INICIO, bateria, demanda, disp, entrada, fv, malha, par, pot, proc
from .fixtures_3c1 import embrulhar
from .rede import ESQUEMA_3C3, FORMULACAO_3C3
from .rede.contrato import BlocoTarifario, EntradaRede3C3, EspecPCC, PerfilTarifario, PoliticaEconomicaRede

DELTA = 15
PCC = "syn-pcc"
MED_IMP, MED_EXP = "syn-pcc-imp", "syn-pcc-exp"
CONTRATO = "syn-contrato-pcc-3c3"
ROTULO_TARIFA = "SINTÉTICA — não é tarifa real (nenhuma tarifa da ANDE/distribuidora/mercado foi usada)"


def _t(i: int, inicio: str = INICIO, delta: float = DELTA) -> str:
    return (datetime.fromisoformat(inicio) + timedelta(minutes=delta * i)).isoformat()


def tarifa(grandeza: str, valores, caso: str, *, natureza: str = "contratual_conhecida", emitido: str = INICIO,
           revisao: int = 0, inicio: str = INICIO, delta: float = DELTA, uid: str | None = None,
           contrato: str = CONTRATO, blocos_min: float | None = None) -> PerfilTarifario:
    """Um bloco por valor, de ``blocos_min`` (padrão Δ) minutos cada, a partir de ``inicio``."""
    dur = int((blocos_min or delta) * 60)
    bl = tuple(BlocoTarifario(_t(0, inicio, 0) if i == 0 else (datetime.fromisoformat(inicio)
                                                                 + timedelta(seconds=dur * i)).isoformat(), dur,
                              None if v is None else float(v)) for i, v in enumerate(valores))
    return PerfilTarifario(uid or f"syn-tarifa-{grandeza}-{caso.lower()}", grandeza, natureza, "R$/kWh", bl, revisao,
                           emitido, "valor_do_bloco_que_contem_o_intervalo", contrato,
                           proc(caso, "tarifa SINTÉTICA de ensaio"), ROTULO_TARIFA)


def pcc(N: int, caso: str, *, modo: str = "conectado", sentidos: str = "importacao_e_exportacao", imp=50.0,
        exp=50.0, a=None, medidores: bool = False, microrrede: str = "syn-microrrede-fixture",
        delta: float = DELTA, inicio_series: str | None = None, n_series: int | None = None) -> EspecPCC:
    if modo == "isolado_declarado":
        return EspecPCC(UIDRecurso(PCC), microrrede, modo, "nenhum", CONTRATO, None, None, None, None, None,
                        proc(caso, "operação isolada declarada"), f"Caso {caso}: operação ISOLADA declarada")
    n = n_series or N
    imp_ok = sentidos in ("importacao_e_exportacao", "somente_importacao")
    exp_ok = sentidos in ("importacao_e_exportacao", "somente_exportacao")

    def serie_k(v):
        vals = list(v) if isinstance(v, (list, tuple)) else [v] * n
        s = pot(vals, delta, caso)
        return s if inicio_series is None else replace(s, inicio_utc=inicio_series, emissao_utc=inicio_series)
    dsp = disp(a if a is not None else [1] * n, delta, caso)
    if inicio_series is not None:
        dsp = Disponibilidade(replace(dsp.serie, inicio_utc=inicio_series, emissao_utc=inicio_series))
    return EspecPCC(UIDRecurso(PCC), microrrede, modo, sentidos, CONTRATO, serie_k(imp) if imp_ok else None,
                    serie_k(exp) if exp_ok else None, dsp,
                    UIDRecurso(MED_IMP) if medidores else None, UIDRecurso(MED_EXP) if medidores else None,
                    proc(caso, "PCC sintético: limites contratados de ensaio"),
                    f"Caso {caso}: PCC conectado SINTÉTICO (limites e disponibilidade declarados)")


def economia(caso: str, *, c_imp=None, c_exp=None, remuneracao: str | None = None, rotulo: str = "causal",
             tarifa_imp: PerfilTarifario | None = None, tarifa_exp: PerfilTarifario | None = None, N: int = 2,
             isolado: bool = False) -> PoliticaEconomicaRede:
    if isolado:
        return PoliticaEconomicaRede((), "nao_aplicavel", None, None, rotulo, proc(caso), f"Caso {caso}: isolado")
    ti = tarifa_imp or (None if c_imp is None else tarifa("importacao", c_imp if isinstance(c_imp, (list, tuple))
                                                          else [c_imp] * N, caso))
    te = tarifa_exp or (None if c_exp is None else tarifa("exportacao", c_exp if isinstance(c_exp, (list, tuple))
                                                          else [c_exp] * N, caso))
    termos = (("importacao_rede",) if ti is not None else ()) + (("exportacao_rede",) if te is not None else ())
    rem = remuneracao or ("remunerada" if te is not None else "nao_aplicavel")
    return PoliticaEconomicaRede(termos, rem, ti, te, rotulo, proc(caso, "política econômica SINTÉTICA"),
                                 f"Caso {caso}: tarifas sintéticas rotuladas; liquidação de ensaio")


def rede(nucleo, p: EspecPCC, ec: PoliticaEconomicaRede, caso: str) -> EntradaRede3C3:
    return EntradaRede3C3(ESQUEMA_3C3, FORMULACAO_3C3, nucleo, p, ec, proc(caso, "Entrada 3C-3 sintética; não é estudo "
                                                                                  "físico nem fatura real."))


def _nucleo(caso: str, N: int, L, A, *, bess=None, c_curt=0.2):
    m = malha(DELTA, N)
    kw = dict(demandas=[demanda("syn-carga", L, DELTA, caso)],
              renovaveis=[fv("syn-fv", A, [1] * N, DELTA, caso, c_curt)] if A is not None else [])
    termos = ("curtailment_operacional",) if A is not None else ()
    if bess is not None:
        C, e0, pmax, smin = bess
        b = bateria("syn-bess", N, DELTA, caso, C=C, smin=smin, pcmax=pmax, pdmax=pmax, c_thr=0.05, eta_c=1.0, eta_d=1.0,
                    obs="η = 1 declarado (aritmética exata)")
        kw.update(baterias=[b], estados_baterias=[EstadoBateria(UIDRecurso("syn-bess"), par(e0, "kWh", caso))])
        termos = termos + ("throughput_bess",)
    base = entrada(caso, m, formulacao=FORMULACAO_3BP, termos=termos, **kw)
    return embrulhar(base, [], [], caso)


# ------------------------------------------------------------------------------------------------ G1 … G4, G9, G10
def caso_g1():
    """G1 — importação necessária. N = 2, L = 30, FV = 10 (c_curt 0,2), P̄_imp = 25, c_imp = 0,8, c_exp = 0,1.
    Ótimo: FV inteira (vertê-la custa), P_imp = 20 kW em cada intervalo (diferença EXATA, < 25), P_exp = 0.
    J = 0,25·0,8·40 = R$ 8,0 (gasto R$ 8,0; receita 0)."""
    n = _nucleo("G1", 2, [30, 30], [10, 10])
    return rede(n, pcc(2, "G1", imp=25.0), economia("G1", c_imp=0.8, c_exp=0.1), "G1")


def caso_g2(remuneracao: str = "remunerada", c_exp: float = 0.3):
    """G2 — exportação autorizada. N = 2, L = 10, FV = 30 (c_curt 0,2), P̄_exp = 50.
    Remunerada c_exp = 0,3: exportar o excedente de 20 kW rende 0,3 > custo evitado de vertimento 0,2 ⇒ P_exp = 20,
    J = −0,25·0,3·40 = −R$ 3,0. Sem remuneração DECLARADA: exportar (crédito 0) ainda evita o vertimento (0,2/kWh) ⇒
    P_exp = 20 e J = 0 (decisão econômica explícita, não presumida)."""
    n = _nucleo("G2", 2, [10, 10], [30, 30])
    if remuneracao == "remunerada":
        ec = economia("G2", c_imp=0.8, c_exp=c_exp)
    else:
        ec = economia("G2", c_imp=0.8, remuneracao="sem_remuneracao")
    return rede(n, pcc(2, "G2"), ec, "G2")


def caso_g3():
    """G3 — exportação proibida (somente_importacao). N = 2, L = 10, FV = 30, BESS C = 100, e0 = 50, P̄ = 15, c_thr 0,05.
    Excedente 20 kW: carregar 15 (0,05·0,25·15 = 0,1875) e verter 5 (0,2·0,25·5 = 0,25) por intervalo ⇒ J = R$ 0,875;
    P_exp ≡ 0, P_imp = 0 (importar só aumentaria o custo)."""
    n = _nucleo("G3", 2, [10, 10], [30, 30], bess=(100.0, 50.0, 15.0, 0.0))
    return rede(n, pcc(2, "G3", sentidos="somente_importacao"), economia("G3", c_imp=0.8), "G3")


def caso_g4(com_bess: bool = False):
    """G4 — PCC indisponível (a = 0 em todos os intervalos). L = 30, FV = 10.
    Sem banco: P_imp = P_exp = 0 e o balanço exige 20 kW inexistentes ⇒ INVIÁVEL (nenhuma energia inventada).
    Com banco (e0 = 50, P̄ = 20, s_min = 0): descarga 20 kW nos 2 intervalos (10 kWh) ⇒ J = 0,05·0,25·40 = R$ 0,5."""
    n = _nucleo("G4", 2, [30, 30], [10, 10], bess=(100.0, 50.0, 20.0, 0.0) if com_bess else None)
    return rede(n, pcc(2, "G4", a=[0, 0]), economia("G4", c_imp=0.8, c_exp=0.1), "G4")


def caso_g9(perfil: str):
    """G9 — mudança tarifária com condições físicas IGUAIS. N = 2, L = 20, sem FV, BESS C = 100, e0 = 45, s_min = 0,4
    (5 kWh utilizáveis), P̄ = 20, c_thr 0,05; P̄_imp = 50.
    Perfil A c_imp = (0,2; 1,0): descarga 20 kW em t = 1, importa (20; 0) ⇒ J = 0,25·0,2·20 + 0,05·0,25·20 = R$ 1,25.
    Perfil B c_imp = (1,0; 0,2): descarga em t = 0, importa (0; 20) ⇒ J = R$ 1,25. Mesmo custo, decisões trocadas."""
    c = {"A": [0.2, 1.0], "B": [1.0, 0.2]}[perfil]
    n = _nucleo(f"G9{perfil}", 2, [20, 20], None, bess=(100.0, 45.0, 20.0, 0.4))
    return rede(n, pcc(2, f"G9{perfil}", sentidos="somente_importacao"), economia(f"G9{perfil}", c_imp=c), f"G9{perfil}")


def caso_g10():
    """G10 — arbitragem artificial. N = 2, L = 10, FV = 10 (c_curt 0,2), c_imp = 0,1 < c_exp = 0,5, P̄ = 50.
    SEM exclusividade (só os limites), importar 50 e exportar 50 no mesmo intervalo renderia 0,25·(0,5 − 0,1)·50·2 =
    R$ 10 sem nenhuma energia útil; com w RELAXADO a [0, 1] (envoltória linear) ainda renderia R$ 5 (25 + 25 kW). COM a exclusividade (w binária): P_imp·P_exp = 0 e, como não há excedente, o ótimo é
    P_imp = P_exp = 0, J = 0."""
    n = _nucleo("G10", 2, [10, 10], [10, 10])
    return rede(n, pcc(2, "G10"), economia("G10", c_imp=0.1, c_exp=0.5), "G10")


def caso_isolado_equivalente():
    """G12/retrocompatibilidade: mesmo núcleo do G3 com PCC ``isolado_declarado`` ⇒ modelo idêntico ao 3C-1."""
    n = _nucleo("G12", 2, [10, 10], [30, 30], bess=(100.0, 50.0, 15.0, 0.0))
    return rede(n, pcc(2, "G12", modo="isolado_declarado"), economia("G12", isolado=True), "G12")


# ------------------------------------------------------------------------------------------------ MPC conectado
INICIO_MPC = INICIO
EMISSAO_R0 = "2025-12-31T12:00:00+00:00"
FONTE_VERDADE = "Verdade sintética do simulador 3C-3 (ems_v2/fixtures_3c3.py) — encapsulada na planta"
C_IMP_R0 = (0.6, 0.6, 0.6, 0.6, 1.2, 1.2, 1.2, 1.2)
C_IMP_R1 = (0.6, 0.6, 0.6, 0.6, 0.9, 0.9, 0.9, 0.9)
C_EXP = 0.2


def modelo_mpc(K: int, L, pv, *, modo: str = "conectado", sentidos: str = "importacao_e_exportacao", imp=50.0,
               exp=50.0, com_fc: bool = True, e0: float = 20.0, fc_ligado: bool = True, fc_p: float = 20.0,
               remuneracao: str = "remunerada", c_imp=C_IMP_R0, c_exp: float = C_EXP, rotulo: str = "causal"):
    """Modelo 3C-3 da missão: núcleo 3C-1 = ``fixtures_3c2.modelo`` (FV, banco e, opcionalmente, PEMFC — parâmetros e
    termos DECLARADOS do 3C-2) + PCC sintético com medidores + tarifas de decisão revisão 0."""
    from . import fixtures_3c2 as F2
    nuc = F2.modelo("3C3", K, L, pv, e0=e0, com_fc=com_fc, fc_ligado=fc_ligado, fc_p=fc_p if fc_ligado else 0.0)
    if modo == "isolado_declarado":
        return rede(nuc, pcc(K, "MPC3C3", modo=modo), economia("MPC3C3", isolado=True, rotulo=rotulo), "MPC3C3")
    p = pcc(K, "MPC3C3", sentidos=sentidos, imp=imp, exp=exp, medidores=True)
    ti = tarifa("importacao", list(c_imp)[:K], "MPC3C3", emitido=EMISSAO_R0) if p.limite_importacao is not None else None
    exp_ok = p.limite_exportacao is not None
    te = tarifa("exportacao", [c_exp] * K, "MPC3C3", emitido=EMISSAO_R0) \
        if exp_ok and remuneracao == "remunerada" else None
    ec = economia("MPC3C3", tarifa_imp=ti, tarifa_exp=te, rotulo=rotulo,
                  remuneracao=(remuneracao if exp_ok else "nao_aplicavel"))
    return rede(nuc, p, ec, "MPC3C3")


def tarifas_decisao(K: int = 8, *, revisao_1_em: str | None = None, c_exp: float = C_EXP, com_exp: bool = True):
    """Perfis de DECISÃO: revisão 0 emitida antes da missão; revisão 1 (preço do 2º bloco 1,2 → 0,9) emitida em
    ``revisao_1_em`` (só disponível nas decisões em τ_k >= emissão)."""
    out = [tarifa("importacao", list(C_IMP_R0)[:K], "MPC3C3", emitido=EMISSAO_R0)]
    if revisao_1_em is not None:
        out.append(tarifa("importacao", list(C_IMP_R1)[:K], "MPC3C3", emitido=revisao_1_em, revisao=1))
    if com_exp:
        out.append(tarifa("exportacao", [c_exp] * K, "MPC3C3", emitido=EMISSAO_R0))
    return tuple(out)


def politica_ajuste(tipo: str = "ajuste_local_algebrico", injecao: str = "limitada_pela_disponibilidade", *,
                    liquidacao: str = "energia_medida_tarifa_aplicavel", K: int = 8, c_liq_imp=C_IMP_R0,
                    c_exp: float = C_EXP, com_exp: bool = True, isolado: bool = False):
    from .rede.execucao import PoliticaAjustePCC
    if isolado:
        return PoliticaAjustePCC("sem_ajuste", injecao, liquidacao, None, None, None, None, proc("ajuste"),
                                 "Operação isolada declarada: nenhum ajuste do PCC")
    li = tarifa("importacao", list(c_liq_imp)[:K], "MPC3C3-liq", natureza="aplicavel_liquidacao",
                uid="syn-liquidacao-importacao")
    le = tarifa("exportacao", [c_exp] * K, "MPC3C3-liq", natureza="aplicavel_liquidacao",
                uid="syn-liquidacao-exportacao") if com_exp else None
    dp = dn = None
    if liquidacao == "desvio_diferenciado":
        dp = tarifa("desvio_positivo", [1.5] * K, "MPC3C3-liq", natureza="contratual_conhecida")
        dn = tarifa("desvio_negativo", [0.1] * K, "MPC3C3-liq", natureza="contratual_conhecida")
    return PoliticaAjustePCC(tipo, injecao, liquidacao, li, le, dp, dn, proc("ajuste", "política SINTÉTICA de ensaio"),
                             "Ensaio 3C-3: ajuste algébrico local do PCC declarado (não é controle primário)")


def configuracao_rede(pol, tarifas):
    from .rede import ESQUEMA_3C3 as E
    from .rede.mpc import ConfiguracaoRedeMPC
    return ConfiguracaoRedeMPC(E, pol, tuple(tarifas), proc("configuracao-rede"),
                               "Ensaio 3C-3: tarifas sintéticas de decisão (todas as revisões) e liquidação declarada")


def verdade_mpc(L, pv, *, a_pcc=None, com_fc: bool = True, com_pcc: bool = True):
    """Realização completa (só a planta a conhece); ``com_pcc=False`` na operação isolada (nenhum PCC existe)."""
    from . import fixtures_3c2 as F2
    from .ponte.cenario import SerieRecurso
    v = F2.verdade("3C3", L, pv, com_fc=com_fc)
    if not com_pcc:
        return v
    K = len(L)
    s = SerieRecurso(PCC, "disponibilidade", F2.serie("disponibilidade", a_pcc or [1] * K, "3C3", emissao=None,
                                                       fonte=FONTE_VERDADE))
    return replace(v, series=v.series + (s,))


def tabela_mpc(L, pv, *, a_pcc=None, com_fc: bool = True) -> dict:
    from . import fixtures_3c2 as F2
    t = F2.tabela("3C3", L, pv, com_fc=com_fc)
    t[(PCC, "disponibilidade")] = F2.serie("disponibilidade", a_pcc or [1] * len(L), "3C3", fonte=F2.FONTE_PREV)
    return t


def latencias_mpc(lat: int = 0, com_fc: bool = True, conectado: bool = True) -> dict:
    from . import fixtures_3c2 as F2
    d = F2.latencias(com_fc=com_fc, lat=lat)
    if conectado:
        d.update({(PCC, "disponibilidade"): lat, (MED_IMP, "potencia"): lat, (MED_EXP, "potencia"): lat})
    return d


__all__ = ["CONTRATO", "C_EXP", "C_IMP_R0", "C_IMP_R1", "DELTA", "EMISSAO_R0", "MED_EXP", "MED_IMP", "PCC",
           "ROTULO_TARIFA", "caso_g1", "caso_g10", "caso_g2", "caso_g3", "caso_g4", "caso_g9", "caso_isolado_equivalente",
           "configuracao_rede", "economia", "latencias_mpc", "modelo_mpc", "pcc", "politica_ajuste", "rede", "tabela_mpc",
           "tarifa", "tarifas_decisao", "verdade_mpc"]
