"""MPC conectado (3C-3): o laço recedente 3C-2 com PCC, intercâmbio programado × realizado e liquidação.

Só biblioteca padrão. Extensão MÍNIMA (auditada antes de implementar — FORMULACAO_3C3 §8): o ``ControladorMPC`` 3C-2
dependia do 3C-1 em exatamente estes pontos — chaves de previsão, montagem/validação/hash da entrada da janela, plano a
partir do resultado, consignas dos comandos, executor da conciliação e do custo planejado do prefixo, contabilidade,
hash do plano complementar e artefatos do registro. Esses pontos viraram métodos de extensão do orquestrador (com a
implementação 3C-2 como padrão, impressões E1–E8 idênticas); ``ControladorMPCConectado`` substitui SÓ eles.
Continua igual (reutilizado sem cópia): relógio, livro K6 (cortes, prefixos, quarentena, revisões), previsão causal,
aceitação, falhas classificadas, confirmações, conciliação 3C-0 (barreira C-02), estado/memória EXECUTADOS e
transportados, registros encadeados, custo acumulado, obrigações pendentes e valor futuro "não implementado".

O que o conectado ACRESCENTA (tipos/evidências próprios):

* livro K6 com a disponibilidade OBSERVADA do PCC e as MEDIÇÕES dos registros de importação/exportação (obrigatórias na
  conciliação: o intercâmbio reconstruído pela álgebra deve coincidir com o medido — evidência do ajuste);
* tarifas de DECISÃO selecionadas causalmente em cada τ_k (maior revisão emitida até τ_k; nunca o preço de liquidação
  salvo ablação rotulada) e tarifas de LIQUIDAÇÃO só na contabilidade realizada;
* comandos com o intercâmbio PROGRAMADO (``<pcc>|P_imp``, ``<pcc>|P_exp``); planta e conciliação com o executor
  conectado e a política de ajuste DECLARADA;
* anexo 3C-3 selado por janela (``<uid>.ems3c3.json``), vínculo de rede por ponto de retomada e registro de missão de
  rede (configuração de rede, modelo 3C-3, totais de intercâmbio e desvio).

Uma missão iniciada ``isolado_declarado`` nunca passa a conectada: o modo é do modelo da missão (hash comprometido) e
toda entrada de janela herda o mesmo PCC; observações do PCC numa missão isolada são ``rejeitada_recurso_desconhecido``.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

from ..compromisso.contrato import hash_entrada_3c1
from ..contracts import Disponibilidade
from ..diagnostics import Constatacao, ContratoInvalido, erro
from ..mpc.entorno import EntornoSimuladoAlgebrico
from ..mpc.observacoes import LivroObservacoes
from ..mpc.orquestrador import ControladorMPC, ResultadoMissaoMPC, _agora_utc
from ..mpc.previsao import ChavePrevisao, chaves_de_previsao
from ..mpc.registro import montar_registro_janela, selar, selo_confere
from ..ponte.canonico import sha256
from ..ponte.execucao import entorno_realizado
from ..provenance import Procedencia, validar_procedencia
from ..timegrid import ler_instante_utc
from . import ESQUEMA_3C3, FORMULACAO_3C3, ROTULO_REDE
from .contrato import (EntradaRede3C3, PerfilTarifario, hash_entrada_3c3, selecionar_perfil_causal,
                       validar_entrada_3c3, validar_perfil)
from .execucao import (ExecutorAlgebricoConectado3C3, PoliticaAjustePCC, contabilidade_realizada_3c3, hash_plano_rede,
                       hash_politica_ajuste, plano_de_resultado_3c3, programa_de_plano, validar_politica_ajuste)
from .registro import gravar_anexo_3c3, hashes_para_registro_3c3, montar_anexo_3c3, preparar_conteudo_anexo_3c3


# ------------------------------------------------------------------------------------------------ configuração
@dataclass(frozen=True)
class ConfiguracaoRedeMPC:
    """Configuração de rede da missão (versionada; sem padrão): política de ajuste/liquidação e o CONJUNTO de perfis
    tarifários de decisão (todas as revisões; a seleção em cada τ_k é causal)."""
    esquema: int
    politica_ajuste: PoliticaAjustePCC
    tarifas_decisao: tuple[PerfilTarifario, ...]
    procedencia: Procedencia | None
    justificativa: str


def hash_configuracao_rede(c: ConfiguracaoRedeMPC) -> str:
    return sha256(c)


def validar_configuracao_rede(c: ConfiguracaoRedeMPC, modelo: EntradaRede3C3, rotulo_informacao: str) -> list[Constatacao]:
    if not isinstance(c, ConfiguracaoRedeMPC):
        return [erro("configuracao_rede_invalida", "configuracao_rede", type(c).__name__)]
    out: list[Constatacao] = []
    if c.esquema != ESQUEMA_3C3:
        out.append(erro("versao_esquema_3c3_incompativel", "configuracao_rede.esquema", f"{c.esquema!r}."))
    out += validar_procedencia(c.procedencia, "configuracao_rede.procedencia")
    if not c.justificativa.strip():
        out.append(erro("configuracao_rede_sem_justificativa", "configuracao_rede.justificativa", "Exigida."))
    out += validar_politica_ajuste(c.politica_ajuste, modelo)
    oraculo = rotulo_informacao == "ablacao_oraculo"
    if (modelo.economia.rotulo_informacao == "ablacao_oraculo") != oraculo:
        out.append(erro("rotulo_tarifa_incoerente", "modelo.economia.rotulo_informacao",
                        "Rótulo de informação das tarifas ≠ rótulo da missão (oráculo só em ablação rotulada)."))
    for i, p in enumerate(c.tarifas_decisao):
        out += validar_perfil(p, f"configuracao_rede.tarifas_decisao[{i}]", contrato_uid=modelo.pcc.contrato_uid)
        if p.natureza == "aplicavel_liquidacao" and not oraculo:
            out.append(erro("preco_de_liquidacao_na_decisao", f"configuracao_rede.tarifas_decisao[{i}]",
                            "Preço de liquidação entre os perfis de decisão de uma missão causal."))
    chaves = [(p.uid, p.revisao) for p in c.tarifas_decisao]
    if len(set(chaves)) != len(chaves):
        out.append(erro("revisao_tarifaria_duplicada", "configuracao_rede.tarifas_decisao", "(uid, revisão) repetido."))
    if modelo.conectado:
        if modelo.pcc.medidor_importacao_uid is None:
            out.append(erro("medidores_nao_declarados", "modelo.pcc", "MPC conectado exige os registros (medidores) do "
                                                                      "PCC como evidência do ajuste."))
        for gr, exig in (("importacao", modelo.importa), ("exportacao", modelo.exporta and
                                                        modelo.economia.remuneracao_exportacao == "remunerada")):
            if exig and not any(p.grandeza == gr for p in c.tarifas_decisao):
                out.append(erro("tarifa_decisao_ausente", f"configuracao_rede.tarifas_decisao[{gr}]",
                                f"Nenhum perfil de decisão de {gr}."))
    return out


class ResolvedorMILP3C3:
    """Adaptador EXPLÍCITO para ``ems_v2.milp.solver_3c3.resolver_3c3`` (import TARDIO, dentro de ``resolver``)."""
    natureza = "milp_3c3_pyomo_highs"

    def __init__(self, configuracao, *, tolerancias=None, identificador: str = "resolver_3c3", _executor=None):
        self.configuracao, self.tolerancias, self.identificador = configuracao, tolerancias, identificador
        self._executor = _executor

    def resolver(self, entrada, compromisso_parcial: dict | None = None):
        from ..audit import Tolerancias
        from ..milp.solver_3c3 import resolver_3c3
        return resolver_3c3(entrada, self.configuracao, compromisso_parcial,
                            tolerancias=self.tolerancias or Tolerancias(), _executor=self._executor)

    def configuracao_registro(self) -> dict:
        c = self.configuracao
        reg = dataclasses.asdict(c) if dataclasses.is_dataclass(c) else {"tipo_recebido": type(c).__name__}
        return {"resolvedor": self.identificador, "natureza": self.natureza, "configuracao": reg,
                "executor_substituido": self._executor is not None}


# ------------------------------------------------------------------------------------------------ evidência por passo
def registros_passos_pcc(e: EntradaRede3C3, plano, pr, traj, real, fontes, politica, *, exigir_medicao: bool):
    """Recalcula, passo a passo, a evidência do PCC pela MESMA regra do executor (reprodução determinística da
    conciliação); o aplicado recalculado deve coincidir com o da trajetória (senão: integridade)."""
    ex = ExecutorAlgebricoConectado3C3(e, fontes, politica, programa=programa_de_plano(pr), exigir_medicao=exigir_medicao,
                                       identificador="evidencia-3c3")
    t0 = ler_instante_utc(plano.inicio_utc, "plano")[0]
    out = []
    for i, p in enumerate(traj.passos):
        ent, c = entorno_realizado(real, (t0 + timedelta(seconds=plano.delta_s * p.indice_plano)).isoformat(),
                                   plano.delta_s)
        if c:
            raise ContratoInvalido(c)
        cons = {f"{x.uid}|{x.grandeza}": float(x.valores[p.indice_plano]) for x in plano.consignas}
        passo = ex.avancar(traj.estados[i], cons, ent, plano.delta_s)
        if not passo.exequivel or passo.aplicado != p.aplicado:
            raise ContratoInvalido([erro("evidencia_pcc_nao_reproduzida", f"passos[{p.indice_plano}]",
                                         "Reexecução do passo conectado ≠ trajetória conciliada.")])
        out.append(ex.ultimo)
    return tuple(out)


# ------------------------------------------------------------------------------------------------ registros de rede
@dataclass(frozen=True)
class VinculoRede3C3:
    """Selado a cada ponto de retomada: amarra o ponto 3C-2 ao modelo 3C-3 e à configuração de rede da missão."""
    esquema: int
    missao_uid: str
    posicao: int
    selo_ultima_janela: str
    hash_modelo_3c3: str
    hash_configuracao_rede: str
    selo: str = ""


@dataclass(frozen=True)
class RegistroMissaoRede3C3:
    esquema: int
    perfil: str
    missao_uid: str
    selo_registro_missao: str
    impressao_missao: str
    hash_modelo_3c3: str
    hash_configuracao_rede: str
    modo_conexao: str
    selos_anexos_3c3: tuple[str, ...]
    totais: dict[str, float]                 # energias importada/exportada/programadas/desvios e liquidação (Σ janelas)
    rotulo: str = ROTULO_REDE
    selo: str = ""


def nome_vinculo(missao_uid: str, posicao: int) -> str:
    return f"{missao_uid}.p{posicao:04d}.rede.mpc3c3.json"


@dataclass
class ResultadoMissaoConectada(ResultadoMissaoMPC):
    anexos_3c3: tuple = ()
    registro_rede: RegistroMissaoRede3C3 | None = None


# ------------------------------------------------------------------------------------------------ controlador
class ControladorMPCConectado(ControladorMPC):
    def __init__(self, cfg, modelo: EntradaRede3C3, provedor, resolvedor, fontes_disponibilidade: dict,
                 configuracao_rede: ConfiguracaoRedeMPC, *, livro: LivroObservacoes | None = None, **kw):
        c = [x for x in validar_entrada_3c3(modelo).constatacoes if x.severidade != "aviso"]
        if not c:
            c += validar_configuracao_rede(configuracao_rede, modelo, cfg.rotulo_informacao)
            if modelo.pcc.microrrede_uid != cfg.identidade.microrrede_uid:
                c.append(erro("identidade_divergente", "modelo.pcc.microrrede_uid", "PCC de outra microrrede."))
        if c:
            raise ContratoInvalido(c)
        self.modelo_rede, self.cfg_rede = modelo, configuracao_rede
        self.anexos_3c3: list = []
        self.registro_rede: RegistroMissaoRede3C3 | None = None
        if livro is None:
            rec: dict[str, set] = {}
            for k_ in self._chaves_previsao_de(modelo):
                rec.setdefault(k_.recurso_uid, set()).add(k_.grandeza)
            for med in self._medidores():
                rec.setdefault(med, set()).add("potencia")
            livro = LivroObservacoes(cfg.identidade.missao_uid, cfg.identidade.microrrede_uid,
                                     {k: tuple(sorted(v)) for k, v in rec.items()})
        super().__init__(cfg, modelo.compromisso, provedor, resolvedor, fontes_disponibilidade, livro=livro, **kw)
        if modelo.conectado:
            extra = [(str(modelo.pcc.uid), "disponibilidade")] + [(m, "potencia") for m in self._medidores()]
            self.chaves_conc = tuple(sorted(set(self.chaves_conc) | set(extra)))

    # ---------------------------------------------------------------- utilidades
    def _medidores(self) -> list[str]:
        p = self.modelo_rede.pcc
        return [str(x) for x in (p.medidor_importacao_uid, p.medidor_exportacao_uid) if x is not None] \
            if self.modelo_rede.conectado else []

    @staticmethod
    def _chaves_previsao_de(modelo: EntradaRede3C3):
        ch = list(chaves_de_previsao(modelo.compromisso))
        if modelo.conectado:
            ch.append(ChavePrevisao(str(modelo.pcc.uid), "disponibilidade"))
        return tuple(sorted(ch, key=lambda c: (c.recurso_uid, c.grandeza)))

    # ---------------------------------------------------------------- pontos de extensão
    def _chaves_previsao(self):
        return self._chaves_previsao_de(self.modelo_rede)

    def _montar_entrada_janela(self, jan, prev, hash_instantaneo: str, proc: Procedencia):
        e3 = super()._montar_entrada_janela(jan, prev, hash_instantaneo, proc)
        m = self.modelo_rede
        if not m.conectado:
            return replace(m, compromisso=e3)
        s = prev.serie(str(m.pcc.uid), "disponibilidade")
        if s is None:
            raise ContratoInvalido([erro("previsao_chave_ausente", f"previsao[{m.pcc.uid}:disponibilidade]",
                                         "Disponibilidade prevista do PCC ausente.")])
        orc = self.cfg.rotulo_informacao == "ablacao_oraculo"
        sel, c = {}, []
        for gr, exig in (("importacao", m.importa), ("exportacao", m.exporta and
                                                    m.economia.remuneracao_exportacao == "remunerada")):
            if exig:
                p, cc = selecionar_perfil_causal(self.cfg_rede.tarifas_decisao, gr, jan.inicio_utc, oraculo=orc)
                sel[gr] = p
                c += cc
        if c:
            raise ContratoInvalido(c)
        ec = replace(m.economia, tarifa_importacao=sel.get("importacao"), tarifa_exportacao=sel.get("exportacao"))
        return replace(m, compromisso=e3, pcc=replace(m.pcc, disponibilidade=Disponibilidade(s.serie)), economia=ec)

    def _validar_entrada_janela(self, e):
        return validar_entrada_3c3(e)

    def _hash_entrada(self, e) -> str:
        return hash_entrada_3c3(e)

    def _plano_de_resultado(self, res, e, k: int):
        return plano_de_resultado_3c3(res, e, indice_fronteira_inicial=k)

    def _consignas_comando(self, plano, pc, i: int) -> dict[str, float]:
        out = super()._consignas_comando(plano, pc, i)
        if self.modelo_rede.conectado:
            out[f"{pc.pcc_uid}|P_imp"] = float(pc.importacao_programada_kW[i])
            out[f"{pc.pcc_uid}|P_exp"] = float(pc.exportacao_programada_kW[i])
        return out

    def _executor_conciliacao(self, ab, identificador: str, *, conciliacao: bool):
        return ExecutorAlgebricoConectado3C3(ab.e3, self.fontes, self.cfg_rede.politica_ajuste,
                                             programa=programa_de_plano(ab.pc), exigir_medicao=conciliacao,
                                             identificador=identificador)

    def _politica_planejada(self, e: EntradaRede3C3) -> PoliticaAjustePCC:
        """Custo PLANEJADO do prefixo: plano × previsão com as tarifas de DECISÃO da janela (o que o plano esperava)."""
        p = self.cfg_rede.politica_ajuste
        rem = e.exporta and e.economia.remuneracao_exportacao == "remunerada"
        return replace(p, liquidacao="energia_medida_tarifa_aplicavel", tarifa_liquidacao_importacao=(
            e.economia.tarifa_importacao if e.importa else None), tarifa_liquidacao_exportacao=(
            e.economia.tarifa_exportacao if rem else None), tarifa_desvio_positivo=None, tarifa_desvio_negativo=None)

    def _contabilidade(self, ab, traj, real, *, planejado: bool = False):
        pol = self._politica_planejada(ab.e3) if planejado else self.cfg_rede.politica_ajuste
        return contabilidade_realizada_3c3(ab.e3, ab.plano, ab.pc, traj, real, pol)

    def _hash_plano_complementar(self, pc) -> str:
        return hash_plano_rede(pc)

    def _artefatos_registro(self, ab, traj, real, contab):
        passos = registros_passos_pcc(ab.e3, ab.plano, ab.pc, traj, real, self.fontes, self.cfg_rede.politica_ajuste,
                                      exigir_medicao=self.modelo_rede.conectado)
        cont = preparar_conteudo_anexo_3c3(ab.e3, ab.plano, ab.pc, traj, real, self.fontes,
                                           self.cfg_rede.politica_ajuste, passos, contab)
        hashes = {"plano_rede_3c3": hash_plano_rede(ab.pc), "nucleo_3c1": hash_entrada_3c1(ab.e3.compromisso),
                  **hashes_para_registro_3c3(cont)}
        return hashes, (lambda reg0: montar_anexo_3c3(reg0, cont))

    def _registrar_anexo(self, anexo) -> None:
        self.anexos_3c3.append(anexo)

    def _selar_e_gravar(self, conteudo, reg0, anexo, tempos) -> None:
        ant = self.registros[-1] if self.registros else None
        r = montar_registro_janela(conteudo, ant, selo_3c0=reg0.selo if reg0 else None,
                                   selo_3c1=anexo.selo if anexo else None, tempos_s=tempos, criado_utc=_agora_utc())
        self.registros.append(r)
        if self.diretorio is not None:
            from ..mpc.persistencia import gravar_exclusivo, gravar_janela_e_retomada
            from ..ponte.canonico import json_canonico
            from ..ponte.registro import gravar_registro
            if reg0 is not None:
                gravar_registro(self.diretorio, reg0)
            if anexo is not None:
                gravar_anexo_3c3(self.diretorio, anexo)
            gravar_janela_e_retomada(self.diretorio, self, r, None, None)
            v = VinculoRede3C3(ESQUEMA_3C3, self.cfg.identidade.missao_uid, r.conteudo.posicao, r.selo,
                               hash_entrada_3c3(self.modelo_rede), hash_configuracao_rede(self.cfg_rede))
            gravar_exclusivo(self.diretorio, nome_vinculo(v.missao_uid, v.posicao), json_canonico(selar(v)))

    # ---------------------------------------------------------------- missão
    def finalizar(self, *, ambiente: dict | None = None):
        rm = super().finalizar(ambiente=ambiente)
        ind = rm.conteudo.indicadores_acumulados
        chaves = ("E_importada_kWh", "E_exportada_kWh", "E_importada_programada_kWh", "E_exportada_programada_kWh",
                  "E_desvio_positivo_kWh", "E_desvio_negativo_kWh", "gasto_importacao_R", "receita_exportacao_R",
                  "custo_desvio_rede_R")
        rr = selar(RegistroMissaoRede3C3(ESQUEMA_3C3, FORMULACAO_3C3, self.cfg.identidade.missao_uid, rm.selo,
                                         rm.impressao_deterministica, hash_entrada_3c3(self.modelo_rede),
                                         hash_configuracao_rede(self.cfg_rede), self.modelo_rede.pcc.modo,
                                         tuple(a.selo for a in self.anexos_3c3),
                                         {k: float(ind.get(k, 0.0)) for k in chaves}))
        self.registro_rede = rr
        if self.diretorio is not None:
            from ..mpc.persistencia import gravar_exclusivo
            from ..ponte.canonico import json_canonico
            gravar_exclusivo(self.diretorio, f"{rr.missao_uid}.rede.missao.mpc3c3.json", json_canonico(rr))
        return rm

    def resultado(self, registro_missao, entorno: dict | None = None) -> ResultadoMissaoConectada:
        b = super().resultado(registro_missao, entorno)
        return ResultadoMissaoConectada(**{f.name: getattr(b, f.name) for f in dataclasses.fields(ResultadoMissaoMPC)},
                                        anexos_3c3=tuple(self.anexos_3c3), registro_rede=self.registro_rede)


def verificar_registro_rede(rr: RegistroMissaoRede3C3, rm, anexos) -> list[Constatacao]:
    out = []
    if not selo_confere(rr):
        out.append(erro("registro_rede_adulterado", "missao_rede.selo", "Selo não confere."))
    if rr.selo_registro_missao != rm.selo or rr.impressao_missao != rm.impressao_deterministica:
        out.append(erro("registro_rede_de_outra_missao", "missao_rede", "Não vinculado ao registro da missão."))
    if rr.selos_anexos_3c3 != tuple(a.selo for a in anexos):
        out.append(erro("anexos_3c3_divergentes", "missao_rede.selos_anexos_3c3", "Sequência de anexos divergente."))
    ind = rm.conteudo.indicadores_acumulados
    for k, v in rr.totais.items():
        if abs(float(ind.get(k, 0.0)) - v) > 1e-9 * max(1.0, abs(v)):
            out.append(erro("totais_rede_divergentes", f"missao_rede.totais[{k}]", "≠ Σ indicadores das janelas."))
    return out


# ------------------------------------------------------------------------------------------------ planta
class EntornoSimuladoConectado(EntornoSimuladoAlgebrico):
    """Planta algébrica de ENSAIO conectada (verdade encapsulada + executor conectado + MEDIÇÃO dos registros do PCC).
    Não é modelo físico nem controle primário: o ajuste do PCC é a regra algébrica DECLARADA na política."""
    natureza = "planta_algebrica_3C3"

    def __init__(self, *, modelo_rede: EntradaRede3C3, politica_ajuste: PoliticaAjustePCC, **kw):
        super().__init__(modelo=modelo_rede.compromisso, **kw)
        self._rede = modelo_rede
        self._exec = ExecutorAlgebricoConectado3C3(modelo_rede, kw["fontes_disponibilidade"], politica_ajuste,
                                                   identificador=kw["identificador"])
        self.passos_pcc: list = []

    def aplicar(self, comando):
        self._exec.ultimo = None
        rec = super().aplicar(comando)
        if rec.aceito_para_execucao and self._rede.conectado:
            u = self._exec.ultimo
            self.passos_pcc.append(u)
            g = comando.indice_global
            ini = self._t0 + timedelta(seconds=self._d * g)
            p = self._rede.pcc
            self._canal.transmitir(self._missao, self._mg, g, ini, ini + timedelta(seconds=self._d),
                                   {f"{p.medidor_importacao_uid}|potencia": u.importacao_realizada_kW,
                                    f"{p.medidor_exportacao_uid}|potencia": u.exportacao_realizada_kW})
        return rec


__all__ = ["ConfiguracaoRedeMPC", "ControladorMPCConectado", "EntornoSimuladoConectado", "RegistroMissaoRede3C3",
           "ResolvedorMILP3C3", "ResultadoMissaoConectada", "VinculoRede3C3", "hash_configuracao_rede", "nome_vinculo",
           "registros_passos_pcc", "validar_configuracao_rede", "verificar_registro_rede"]
_ = (math, Path)
