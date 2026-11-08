"""Fixtures SINTÉTICAS da ponte 3C-0 (inventário, cenário, previsão, realização e políticas de ENSAIO).

Todos os números são dados de teste (procedência ``sintetico``), NÃO parâmetros de nenhuma microrrede do SEEDS2.
Servem para exercitar os contratos plano → execução → estado e a compatibilidade com o 3A/3B-P. Os parâmetros que
o inventário do Piso 1 não possui (η, potências no barramento, hipótese de autodescarga, custos) aparecem aqui sob as
chaves PROPOSTAS de ``ponte.requisitos``.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace

from . import FORMULACAO_3BP
from .contracts import PoliticaObjetivo, PoliticaServico, PoliticaTerminal
from .parameters import Parametro
from .ponte import CONTRATO_VERSAO
from .ponte.cenario import (CenarioEMS, CondicaoInicialDispositivo, ConjuntoPrevisao, DefinicaoTemporal, Realizacao,
                            ReferenciaInventario, SerieRecurso)
from .ponte.inventario import (AssociacaoModelo, DispositivoInventario, IdentidadeMicrorrede, InventarioMicrorrede,
                               ValorInventario)
from .ponte.projecao import ClasseDemandaDeclarada, PoliticasDeclaradas
from .provenance import Procedencia
from .series import SerieTemporal
from .timegrid import MalhaTemporal

FONTE = "Fixture sintética da ponte 3C-0 (ems_v2/fixtures_3c0.py) — não é dado de instalação"
INICIO = "2026-01-01T00:00:00+00:00"
DELTA_MIN = 15
N = 4
DEMANDA_PREV = (30.0, 40.0, 50.0, 20.0)
PV_PREV = (20.0, 30.0, 10.0, 0.0)
COMPROMISSO = {"syn-ter1": [1, 1, 1, 1]}


def proc(caso: str = "3C0", obs: str = "") -> Procedencia:
    return Procedencia("sintetico", FONTE, caso, observacoes=obs)


def h64(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def num(chave: str, unidade: str, valor: float, mg: str, uid: str) -> ValorInventario:
    return ValorInventario(chave, unidade, f"{mg}/{uid}/{chave}", "sintetico", proc(), numero=float(valor))


def txt(chave: str, valor: str, mg: str, uid: str) -> ValorInventario:
    return ValorInventario(chave, "", f"{mg}/{uid}/{chave}", "sintetico", proc(), texto=valor)


def _disp(mg, uid, tipo, papel, tec, valores, *, pai=None, quantidade=None, habilitado=True, ref=None):
    return DispositivoInventario(uid, mg, tipo, f"{tipo} {uid}", "", habilitado, "presente", pai, quantidade,
                                 AssociacaoModelo("(sintético)", ref, papel, tec), tuple(valores), h64(mg + uid))


def bateria(mg: str, uid: str = "syn-bat1", *, C=100.0, smin_pct=10.0, smax_pct=90.0, eta=0.95, pmax=20.0,
            c_thr=0.01) -> DispositivoInventario:
    return _disp(mg, uid, "bateria", "armazenamento", None, [
        num("energy_kWh", "kWh", C, mg, uid), num("soc_min_pct", "%", smin_pct, mg, uid),
        num("soc_max_pct", "%", smax_pct, mg, uid), num("eta_carga", "1", eta, mg, uid),
        num("eta_descarga", "1", eta, mg, uid), num("p_carga_barramento_kW", "kW", pmax, mg, uid),
        num("p_descarga_barramento_kW", "kW", pmax, mg, uid), txt("hipotese_autodescarga", "nao_modelada_alpha_1", mg, uid),
        num("custo_throughput", "R$/kWh", c_thr, mg, uid)])


def usina(mg: str, uid: str = "syn-usina1") -> DispositivoInventario:
    return _disp(mg, uid, "pv_usina", "agrupador", None, [])


def arranjo(mg: str, uid: str = "syn-pv1", pai: str = "syn-usina1", c_curt=0.5) -> DispositivoInventario:
    return _disp(mg, uid, "pv_arranjo", "renovavel", "fv", [
        txt("reference", "SYN-MODULO", mg, uid), num("n_series", "módulos", 2, mg, uid),
        num("n_parallel", "strings", 5, mg, uid), num("soiling_pct", "%", 0.0, mg, uid),
        num("custo_curtailment", "R$/kWh", c_curt, mg, uid)], pai=pai, ref="SYN-MODULO")


def termica(mg: str, uid: str = "syn-ter1", pmin=5.0, pmax=30.0) -> DispositivoInventario:
    return _disp(mg, uid, "termica", "gerador", "termica", [
        txt("dynamic", "local_generator", mg, uid), num("pmin_kW", "kW", pmin, mg, uid), num("pmax_kW", "kW", pmax, mg, uid),
        num("cvu_rs_MWh", "R$/MWh", 1100.0, mg, uid)], ref="local_generator")


def inventario(mg: str = "syn-mg-a", dispositivos=None, *, revisao: int = 1, modo: str = "isolada") -> InventarioMicrorrede:
    ds = tuple(dispositivos) if dispositivos is not None else (bateria(mg), usina(mg), arranjo(mg), termica(mg))
    return InventarioMicrorrede(CONTRATO_VERSAO, IdentidadeMicrorrede(mg, "inc-syn", revisao, h64(f"cfg{mg}{revisao}"),
                                                                      h64("inv" + "".join(d.impressao_digital for d in ds)),
                                                                      f"Microrrede sintética {mg}"),
                                modo, "isolada", ds, (), proc())


def referencia(inv: InventarioMicrorrede) -> ReferenciaInventario:
    i = inv.identidade
    return ReferenciaInventario(i.uid, i.incarnacao, i.revisao_config, i.impressao_config, i.impressao_inventario)


def cenario(inv: InventarioMicrorrede, *, soc_pct=50.0, ter_estado="em_operacao", ter_p=10.0,
            disponibilidade=None) -> CenarioEMS:
    disponibilidade = disponibilidade or {}
    conds = []
    for d in inv.dispositivos:
        if d.modelo.papel_ems == "agrupador" or not d.habilitado:
            continue
        a = disponibilidade.get(d.uid, "disponivel")
        if d.tipo == "bateria":
            conds.append(CondicaoInicialDispositivo(d.uid, a, soc=Parametro.de_bruto(soc_pct, "%", proc())))
        elif d.modelo.papel_ems == "gerador":
            conds.append(CondicaoInicialDispositivo(d.uid, a, estado_discreto=ter_estado,
                                                    potencia_kW=Parametro(ter_p, "kW", proc()),
                                                    unidades_ligadas=None, tempo_no_estado_s=3600))
        else:
            conds.append(CondicaoInicialDispositivo(d.uid, a))
    return CenarioEMS(CONTRATO_VERSAO, "syn-cenario-3c0", 1, h64("cenario"), referencia(inv), tuple(conds), (), proc(),
                      INICIO)


def definicao(*, n: int = N, m: int | None = None, missao: int | None = None) -> DefinicaoTemporal:
    return DefinicaoTemporal(MalhaTemporal(INICIO, DELTA_MIN, n, m or n, missao or n, horizonte_previsao_min=DELTA_MIN * n))


def _serie(grandeza, unidade, valores, *, emissao=INICIO, inicio=INICIO, fronteira=None) -> SerieTemporal:
    return SerieTemporal(grandeza, unidade, "media_intervalo", inicio, DELTA_MIN * 60, tuple(float(v) for v in valores),
                         proc(), fronteira=fronteira, emissao_utc=emissao)


def previsao(demanda=DEMANDA_PREV, pv=PV_PREV, *, oraculo: bool = False) -> ConjuntoPrevisao:
    return ConjuntoPrevisao("syn-prev-1", INICIO, (
        SerieRecurso("syn-carga", "potencia", _serie("potencia", "kW", demanda, fronteira="barramento_liquido")),
        SerieRecurso("syn-pv1", "potencia", _serie("potencia", "kW", pv, fronteira="barramento_liquido"),
                     "antes_da_disponibilidade")), proc(), oraculo,
        "Teste de continuidade plano → execução (oráculo rotulado; não mede erro de predição)" if oraculo else "")


def realizacao(demanda=DEMANDA_PREV, pv=PV_PREV, disp_pv=(1, 1, 1, 1)) -> Realizacao:
    return Realizacao("syn-real-1", "sintetica", (
        SerieRecurso("syn-carga", "potencia", _serie("potencia", "kW", demanda, emissao=None, fronteira="barramento_liquido")),
        SerieRecurso("syn-pv1", "potencia", _serie("potencia", "kW", pv, emissao=None, fronteira="barramento_liquido")),
        SerieRecurso("syn-pv1", "disponibilidade", _serie("disponibilidade", "1", disp_pv, emissao=None))), proc())


def politicas(termos=("curtailment_operacional", "throughput_bess")) -> PoliticasDeclaradas:
    return PoliticasDeclaradas(
        FORMULACAO_3BP, PoliticaServico("duro", proc(obs="Serviço duro (D01, regra temporária)")),
        PoliticaTerminal("nenhuma", "Ensaio contratual 3C-0: sem termo terminal (valor futuro é 3C-4)", proc()),
        PoliticaObjetivo(tuple(termos), proc()),
        (ClasseDemandaDeclarada("syn-carga", "Carga agregada (sintética)", "critica"),), "instantanea", proc())


def com_valor(d: DispositivoInventario, chave: str, novo: ValorInventario | None) -> DispositivoInventario:
    """Cópia do dispositivo com o valor ``chave`` substituído (ou removido, se ``novo`` é None)."""
    vals = tuple(v for v in d.valores if v.chave != chave) + ((novo,) if novo is not None else ())
    return replace(d, valores=vals)


__all__ = ["COMPROMISSO", "DELTA_MIN", "DEMANDA_PREV", "INICIO", "N", "PV_PREV", "arranjo", "bateria", "cenario",
           "com_valor", "definicao", "h64", "inventario", "num", "politicas", "previsao", "proc", "realizacao",
           "referencia", "termica", "txt", "usina"]
