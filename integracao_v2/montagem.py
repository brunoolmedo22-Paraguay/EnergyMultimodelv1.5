"""Montagem da missão V2 (Piso 3D-A): cenário versionado do SEEDS2 → contratos do motor ``milp_mpc_v1``.

Construtores PUROS (nenhuma validação é relaxada, nada é gravado): cada função recebe valores já lidos do
``MicrogridStore`` e devolve contratos do ``ems_v2``; as validações são as dos próprios contratos (chamadas pelo
``preflight``). Decisões de integração registradas em ``docs/ems_v2/INTEGRACAO_3DA.md``:

* **Inventário EFETIVO da missão** = instantâneo POR DISPOSITIVO do leitor 3C-0 (``ponte_seeds2.leitor``) com:
  (1) as declarações do bloco ``milp_mpc`` acrescentadas ao próprio dispositivo como ``ValorInventario`` de origem
  ``cenario`` (ou ``sintetico`` quando a procedência declarada é sintética), com a procedência POR CAMPO;
  (2) equipamentos declarados INDISPONÍVEIS no cenário como não participantes (``habilitado = False`` só no instantâneo
  efetivo; inventário permanente intocado — mesma regra do Piso 2C);
  (3) ``modo_operacao = "isolada"`` — a base 3B-P declara o BARRAMENTO INTERNO; a interconexão existe exclusivamente
  no embrulho 3C-3 (interpretação C-3C3-01 do próprio ``ems_v2``; contradição C-3DA-02).
* **Identidades sem equipamento no inventário** (classe de demanda agregada, PCC, medidores virtuais, contrato) usam o
  espaço ``syn-…`` do contrato 3A: são entidades DECLARADAS na estratégia, não registros ``eq-…`` do inventário.
* **Previsão × realização**: a previsão disponível ao controlador é a série de demanda GRAVADA no cenário (tabela
  declarada antecipadamente, com a emissão declarada); a realização é uma série SEPARADA, entregue só à planta
  algébrica. O provedor da previsão nunca recebe a realização (verificado estruturalmente pelo MPC 3C-2).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from ems_v2 import FORMULACAO_3BP
from ems_v2.compromisso.contrato import EntradaCommitment3C1, PoliticaPermanenciaTerminal
from ems_v2.contracts import Disponibilidade, PoliticaObjetivo, PoliticaServico, PoliticaTerminal, UIDRecurso
from ems_v2.hierarquia import ESQUEMA_3C4, FORMULACAO_3C4
from ems_v2.hierarquia.contrato import ConfiguracaoPlanejador3C4, ParametroBateria, TermoTerminal3C4
from ems_v2.milp.config import ConfiguracaoSolver
from ems_v2.mpc import ESQUEMA_MPC
from ems_v2.mpc.contrato import (CLASSES_FALHA, ConfiguracaoMPC, IdentidadeMissao, PoliticaAceitacao, PoliticaFalhas,
                                 PoliticaTerminalMissao)
from ems_v2.ponte import cenario as CN
from ems_v2.ponte import inventario as IV
from ems_v2.ponte import projecao as PJ
from ems_v2.ponte.compromisso import DeclaracaoCommitment3C1, vinculo_do_instantaneo
from ems_v2.provenance import Procedencia
from ems_v2.rede import ESQUEMA_3C3, FORMULACAO_3C3
from ems_v2.rede.contrato import BlocoTarifario, EntradaRede3C3, EspecPCC, PerfilTarifario, PoliticaEconomicaRede
from ems_v2.rede.execucao import PoliticaAjustePCC
from ems_v2.rede.mpc import ConfiguracaoRedeMPC
from ems_v2.series import SerieTemporal
from ems_v2.timegrid import MalhaTemporal

from . import estrategia as E

UID_DEMANDA = "syn-demanda-agregada"
UID_PCC = "syn-pcc"
UID_MED_IMP, UID_MED_EXP = "syn-pcc-med-imp", "syn-pcc-med-exp"
UID_CONTRATO = "syn-contrato-pcc-declarado"
ID_PROVEDOR = "provedor-tabela-declarada-do-cenario"
ID_PLANTA = "planta-algebrica-de-ensaio-3d"
FONTE_CANAL = "Canal de observação SIMULADO da planta algébrica 3D-A (latência 0 declarada)"
# Políticas FIXAS da integração 3D-A (declaradas aqui, gravadas no manifesto de cada rodada; nenhuma é física):
FIXOS = {
    "modo_experimental": "simulacao_causal_laco_fechado",
    "rotulo_informacao": "causal",
    "politica_servico": "duro",
    "politica_terminal_nucleo_3bp": "nenhuma (o termo terminal efetivo é o do embrulho 3C-4)",
    "politica_terminal_missao": "janela_reduzida",
    "permanencia_janelas": "cumprir_na_janela",
    "politica_falhas": "interromper (toda classe de falha encerra a missão; nenhuma contingência nem despacho de reserva)",
    "aceitacao": "somente solução ótima dentro dos gaps declarados, aprovada pelo auditor independente",
    "politica_revisao_tardia": "registrar_sem_reconciliar",
    "cobertura_fim_missao": "reduzido_ao_fim_da_missao",
    "injecao_renovavel": "limitada_pela_disponibilidade (sem renováveis no modelo 3D-A)",
    "latencia_observacao_s": 0,
    "geradores_despachaveis": "nenhum (PEMFC e térmica não são representáveis no Piso 3D-A)",
}
JUST_PERMANENCIA = "Missão 3D-A sem geradores despacháveis: nenhuma permanência a cumprir"
JUST_TERMINAL = "Missão 3D-A: janela reduzida ao fim da missão (nenhuma previsão pós-missão é usada)"


@dataclass(frozen=True)
class Tempo:
    inicio_utc: str                      # τ_0 (ISO 8601, +00:00)
    delta_min: int
    K: int                               # intervalos da missão
    N: int
    m: int
    H_L: int
    fuso: str                            # fuso declarado da missão (apresentação)
    inicio_local: str                    # relógio de parede declarado

    @property
    def delta_s(self) -> int:
        return self.delta_min * 60

    def instante(self, k: int) -> str:
        return (datetime.fromisoformat(self.inicio_utc) + timedelta(seconds=self.delta_s * k)).isoformat()

    def malha_missao(self) -> MalhaTemporal:
        return MalhaTemporal(self.inicio_utc, self.delta_min, self.N, self.m, self.K,
                             horizonte_previsao_min=self.delta_min * self.K)

    def malha_modelo(self) -> MalhaTemporal:
        return MalhaTemporal(self.inicio_utc, self.delta_min, self.K, self.K, self.K,
                             horizonte_previsao_min=self.delta_min * self.K)


@dataclass
class Montagem:
    """Tudo o que uma rodada V2 precisa, montado UMA vez pelo preflight sobre a versão salva do cenário."""
    tempo: Tempo
    inventario: IV.InventarioMicrorrede            # instantâneo REAL (revisão referenciada)
    inventario_efetivo: IV.InventarioMicrorrede
    cenario: CN.CenarioEMS
    excluidos: list[dict]
    representados: list[dict]
    demanda_prevista_kW: tuple[float, ...]
    demanda_realizada_kW: tuple[float, ...]
    tabela: dict                                    # provedor: {(uid, grandeza): SerieTemporal}
    verdade: CN.Realizacao                          # só a planta a recebe
    fonte_verdade: str
    politicas: PJ.PoliticasDeclaradas
    nucleo: EntradaCommitment3C1 | None = None
    modelo: EntradaRede3C3 | None = None
    politica_ajuste: PoliticaAjustePCC | None = None
    configuracao_rede: ConfiguracaoRedeMPC | None = None
    configuracao_planejador: ConfiguracaoPlanejador3C4 | None = None
    solver: ConfiguracaoSolver | None = None
    proc_politicas: Procedencia | None = None
    tarifas: dict = field(default_factory=dict)     # grandeza → lista de R$/kWh (decisão = liquidação declarada)
    hashes: dict = field(default_factory=dict)


# ------------------------------------------------------------------------------------------------ procedências
def proc_declarada(p: dict, caminho: str, stored) -> Procedencia:
    """Procedência de um valor DECLARADO no bloco ``milp_mpc`` (por campo: ``caminho`` é o caminho no documento)."""
    return Procedencia(p["tipo"], str(p["fonte"]).strip(), f"{E.CHAVE_BLOCO}.{caminho}", sha256=stored.fingerprint,
                       observacoes=f"cenário {stored.scenario_uid} · versão {stored.version}")


# ------------------------------------------------------------------------------------------------ inventário efetivo
def inventario_efetivo(inv: IV.InventarioMicrorrede, bloco: dict, stored, excluidos: set[str]) -> IV.InventarioMicrorrede:
    novos = []
    for d in inv.dispositivos:
        if d.uid in excluidos or (d.pai is not None and d.pai in excluidos):
            novos.append(replace(d, habilitado=False))
            continue
        decl = bloco["baterias"].get(d.uid) if d.tipo == "bateria" else None
        if decl is not None and E.procedencia_declarada(decl["procedencia"]):
            sint = decl["procedencia"]["tipo"] == "sintetico"
            vals = list(d.valores)
            for campo, (_rot, un, chave, _dom) in E.CAMPOS_BATERIA.items():
                if decl[campo] is None:
                    continue
                cam = f"baterias.{d.uid}.{campo}"
                vals.append(IV.ValorInventario(chave, un, f"{E.CHAVE_BLOCO}.{cam}", "sintetico" if sint else "cenario",
                                               proc_declarada(decl["procedencia"], cam, stored), numero=float(decl[campo])))
            if decl["hipotese_autodescarga"] is not None:
                cam = f"baterias.{d.uid}.hipotese_autodescarga"
                vals.append(IV.ValorInventario("hipotese_autodescarga", "", f"{E.CHAVE_BLOCO}.{cam}",
                                               "sintetico" if sint else "cenario",
                                               proc_declarada(decl["procedencia"], cam, stored),
                                               texto=str(decl["hipotese_autodescarga"])))
            d = replace(d, valores=tuple(vals))
        novos.append(d)
    obs = inv.observacoes + (
        "Inventário EFETIVO da missão V2 (3D-A): declarações do bloco milp_mpc acrescentadas por dispositivo; "
        "indisponíveis no cenário como não participantes; modo_operacao = 'isolada' = barramento interno da base 3B-P "
        f"(instalação declarada: {inv.modo_operacao!r}; a interconexão existe só no embrulho 3C-3 — C-3C3-01).",)
    return replace(inv, modo_operacao="isolada", dispositivos=tuple(novos), observacoes=obs)


# ------------------------------------------------------------------------------------------------ séries
def serie(grandeza: str, t: Tempo, valores, proc: Procedencia, emissao: str | None) -> SerieTemporal:
    return SerieTemporal(grandeza, {"potencia": "kW", "disponibilidade": "1"}[grandeza], "media_intervalo", t.inicio_utc,
                         t.delta_s, tuple(float(v) for v in valores), proc,
                         fronteira="barramento_liquido" if grandeza == "potencia" else None, emissao_utc=emissao)


def politicas(bloco: dict, proc: Procedencia) -> PJ.PoliticasDeclaradas:
    d = bloco["demanda"]
    return PJ.PoliticasDeclaradas(
        FORMULACAO_3BP, PoliticaServico("duro", proc),
        PoliticaTerminal("nenhuma", "Núcleo 3B-P sem termo terminal próprio: o tratamento terminal é o termo declarado "
                                    "do embrulho 3C-4 (sinal de valor futuro ou degradação declarada)", proc),
        PoliticaObjetivo(tuple(bloco["objetivo"]["termos"]), proc, None),
        (PJ.ClasseDemandaDeclarada(UID_DEMANDA, str(d["nome"]).strip(), d["criticidade"]),), None, proc)


def declaracao_commitment(inv_ef, cen, proc: Procedencia) -> DeclaracaoCommitment3C1:
    return DeclaracaoCommitment3C1(vinculo_do_instantaneo(inv_ef, cen),
                                   PoliticaPermanenciaTerminal("cumprir_na_janela", JUST_PERMANENCIA, proc), (), {}, {},
                                   JUST_PERMANENCIA, (), proc)


# ------------------------------------------------------------------------------------------------ PCC e tarifas
def perfil(grandeza: str, valores, natureza: str, emitido: str, t: Tempo, uid: str, proc: Procedencia,
           rotulo: str) -> PerfilTarifario:
    blocos = tuple(BlocoTarifario(t.instante(i), t.delta_s, float(v)) for i, v in enumerate(valores))
    return PerfilTarifario(uid, grandeza, natureza, "R$/kWh", blocos, 0, emitido, "valor_do_bloco_que_contem_o_intervalo",
                           UID_CONTRATO, proc, rotulo)


def rede(nucleo: EntradaCommitment3C1, bloco: dict, t: Tempo, microrrede_uid: str, stored
         ) -> tuple[EntradaRede3C3, PoliticaAjustePCC, ConfiguracaoRedeMPC, dict]:
    c = bloco["pcc"]
    proc = proc_declarada(c["procedencia"], "pcc", stored)
    just = str(c["justificativa"]).strip()
    if c["modo"] != "conectado":
        pcc = EspecPCC(UIDRecurso(UID_PCC), microrrede_uid, c["modo"], c["sentidos"], UID_CONTRATO, None, None, None, None,
                       None, proc, just)
        eco = PoliticaEconomicaRede((), "nao_aplicavel", None, None, "causal", proc, just)
        pol = PoliticaAjustePCC(c["ajuste"], "limitada_pela_disponibilidade", "energia_medida_tarifa_aplicavel", None,
                                None, None, None, proc, just)
        return (EntradaRede3C3(ESQUEMA_3C3, FORMULACAO_3C3, nucleo, pcc, eco, proc), pol,
                ConfiguracaoRedeMPC(ESQUEMA_3C3, pol, (), proc, just), {})
    imp = c["sentidos"] in ("importacao_e_exportacao", "somente_importacao")
    exp = c["sentidos"] in ("importacao_e_exportacao", "somente_exportacao")
    emit, rot = c["tarifa_emissao_utc"], str(c["rotulo_tarifa"]).strip()
    um = [1.0] * t.K
    pcc = EspecPCC(UIDRecurso(UID_PCC), microrrede_uid, "conectado", c["sentidos"], UID_CONTRATO,
                   serie("potencia", t, [c["limite_importacao_kW"]] * t.K, proc, emit) if imp else None,
                   serie("potencia", t, [c["limite_exportacao_kW"]] * t.K, proc, emit) if exp else None,
                   Disponibilidade(serie("disponibilidade", t, um, proc, emit)), UIDRecurso(UID_MED_IMP),
                   UIDRecurso(UID_MED_EXP), proc, just)
    rem = c["remuneracao_exportacao"] if exp else "nao_aplicavel"
    ti = perfil("importacao", c["tarifa_importacao_R_kWh"], "contratual_conhecida", emit, t, "syn-tarifa-importacao", proc,
                rot) if imp else None
    te = perfil("exportacao", c["tarifa_exportacao_R_kWh"], "contratual_conhecida", emit, t, "syn-tarifa-exportacao", proc,
                rot) if exp and rem == "remunerada" else None
    termos = (("importacao_rede",) if ti is not None else ()) + (("exportacao_rede",) if te is not None else ())
    eco = PoliticaEconomicaRede(termos, rem, ti, te, "causal", proc, just)
    # Liquidação pela MESMA tarifa declarada (regra ``igual_a_tarifa_declarada``): perfis próprios de natureza
    # "aplicavel_liquidacao", com os mesmos valores — nunca entregues à decisão.
    li = perfil("importacao", c["tarifa_importacao_R_kWh"], "aplicavel_liquidacao", t.inicio_utc, t,
                "syn-liquidacao-importacao", proc, rot) if imp else None
    le = perfil("exportacao", c["tarifa_exportacao_R_kWh"], "aplicavel_liquidacao", t.inicio_utc, t,
                "syn-liquidacao-exportacao", proc, rot) if te is not None else None
    pol = PoliticaAjustePCC(c["ajuste"], "limitada_pela_disponibilidade", "energia_medida_tarifa_aplicavel", li, le, None,
                            None, proc, just)
    cfg = ConfiguracaoRedeMPC(ESQUEMA_3C3, pol, tuple(x for x in (ti, te) if x is not None), proc, just)
    tar = {}
    if imp:
        tar["importacao"] = [float(v) for v in c["tarifa_importacao_R_kWh"]]
    if te is not None:
        tar["exportacao"] = [float(v) for v in c["tarifa_exportacao_R_kWh"]]
    return EntradaRede3C3(ESQUEMA_3C3, FORMULACAO_3C3, nucleo, pcc, eco, proc), pol, cfg, tar


# ------------------------------------------------------------------------------------------------ MPC e planejador
def identidade(mont: Montagem, missao_uid: str, stored) -> IdentidadeMissao:
    i = mont.inventario.identidade
    return IdentidadeMissao(missao_uid, i.uid, i.incarnacao, i.revisao_config, i.impressao_config, i.impressao_inventario,
                            IV.hash_inventario(mont.inventario_efetivo), stored.scenario_uid, int(stored.version),
                            stored.fingerprint)


def configuracao_mpc(mont: Montagem, missao_uid: str, stored) -> ConfiguracaoMPC:
    p = mont.proc_politicas
    pt = PoliticaTerminalMissao("janela_reduzida", "cumprir_na_janela", "cumprir_na_janela", JUST_TERMINAL, p)
    return ConfiguracaoMPC(
        ESQUEMA_MPC, identidade(mont, missao_uid, stored), mont.tempo.malha_missao(), "simulacao_causal_laco_fechado",
        "causal", pt,
        PoliticaAceitacao(False, None, (), "Integração 3D-A: só solução ótima nos gaps declarados (aprovada pelo auditor)", p),
        PoliticaFalhas({k: "interromper" for k in CLASSES_FALHA},
                       "Integração 3D-A: toda falha encerra a missão (sem contingência nem despacho de reserva)", p),
        "registrar_sem_reconciliar", p)


def configuracao_planejador(bloco: dict, t: Tempo, proc: Procedencia) -> ConfiguracaoPlanejador3C4:
    g = bloco["planejador"]
    tl = g["termo_longo"]
    vs = tuple(ParametroBateria(u, float(v)) for u, v in sorted(tl["valores"].items()))
    termo = TermoTerminal3C4(tl["tipo"], vs if tl["tipo"] == "valor_linear_declarado" else (),
                             vs if tl["tipo"] == "energia_minima_declarada" else (), None, str(tl["justificativa"]).strip(),
                             proc)
    return ConfiguracaoPlanejador3C4(
        ESQUEMA_3C4, FORMULACAO_3C4, int(t.H_L), "reduzido_ao_fim_da_missao", termo, "cumprir_na_janela",
        g["politica_atualizacao"], int(g["periodo_janelas"]), g["tipo_sinal"], int(g["pontos_iniciais"]),
        int(g["pontos_max"]), float(g["tolerancia_interpolacao_R"]), float(g["tolerancia_dominio_kWh"]),
        None if g["delta_sensibilidade_kWh"] is None else float(g["delta_sensibilidade_kWh"]),
        None if g["penalidade_branda_R_kWh"] is None else float(g["penalidade_branda_R_kWh"]), int(g["max_modos"]),
        g["degradacao"], str(g["justificativa"]).strip(), proc)


def configuracao_solver(bloco: dict) -> ConfiguracaoSolver:
    s = bloco["solver"]
    return ConfiguracaoSolver(time_limit_s=float(s["time_limit_s"]), threads=int(s["threads"]), rel_gap=float(s["rel_gap"]),
                              abs_gap=float(s["abs_gap"]), semente=int(s["semente"]))


def construir_missao(mont: Montagem, missao_uid: str, stored, *, diretorio=None):
    """Controlador hierárquico + planta algébrica da missão ``missao_uid`` (= ``run_uid`` da rodada). Não resolve nada:
    os resolvedores só importam Pyomo/HiGHS quando chamados."""
    from ems_v2.hierarquia.mpc import ControladorMPCHierarquico, ResolvedorMILP3C4
    from ems_v2.hierarquia.planejador import ResolvedorPlanejador3C4
    from ems_v2.mpc.entorno import CanalObservacao
    from ems_v2.ponte.compromisso import estado_inicial_3c1
    from ems_v2.mpc.provedores import ProvedorTabelaDeclarada
    from ems_v2.rede.mpc import EntornoSimuladoConectado

    cfg = configuracao_mpc(mont, missao_uid, stored)
    prov_proc = next(s.procedencia for (u, g), s in mont.tabela.items() if (u, g) == (UID_DEMANDA, "potencia"))
    provedor = ProvedorTabelaDeclarada(ID_PROVEDOR, mont.tabela, prov_proc)
    lat = {(s.uid, s.grandeza): 0 for s in mont.verdade.series}
    if mont.modelo.conectado:
        lat.update({(UID_MED_IMP, "potencia"): 0, (UID_MED_EXP, "potencia"): 0})
    canal = CanalObservacao(FONTE_CANAL, lat, 0, Procedencia("sintetico", FONTE_CANAL, "canal de observação simulado"))
    entorno = EntornoSimuladoConectado(
        modelo_rede=mont.modelo, politica_ajuste=mont.politica_ajuste, identificador=ID_PLANTA, missao_uid=missao_uid,
        verdade=mont.verdade, fontes_disponibilidade={}, estado_inicial=estado_inicial_3c1(mont.modelo.compromisso),
        canal=canal, inicio_missao_utc=mont.tempo.inicio_utc, delta_s=mont.tempo.delta_s, intervalos_missao=mont.tempo.K)
    ctrl = ControladorMPCHierarquico(
        cfg, mont.modelo, provedor, ResolvedorMILP3C4(mont.solver), {}, mont.configuracao_rede,
        mont.configuracao_planejador, ResolvedorPlanejador3C4(mont.solver), identificadores_verdade=(ID_PLANTA,),
        fontes_verdade=(mont.fonte_verdade,), diretorio=diretorio)
    return ctrl, entorno, cfg


def utc_iso(segundos: float) -> str:
    return datetime.fromtimestamp(float(segundos), tz=timezone.utc).isoformat()


__all__ = ["FIXOS", "FONTE_CANAL", "ID_PLANTA", "ID_PROVEDOR", "Montagem", "Tempo", "UID_CONTRATO", "UID_DEMANDA",
           "UID_MED_EXP", "UID_MED_IMP", "UID_PCC", "configuracao_mpc", "configuracao_planejador", "configuracao_solver",
           "construir_missao", "declaracao_commitment", "identidade", "inventario_efetivo", "perfil", "politicas",
           "proc_declarada", "rede", "serie", "utc_iso"]
