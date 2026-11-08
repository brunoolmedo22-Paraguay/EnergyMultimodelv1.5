"""Registro de resultados, persistência e reprodutibilidade (3C-0 §3.6).

``RegistroExecucaoEMS`` é IMUTÁVEL e SELADO (SHA-256 do JSON canônico sem o selo). Reúne identidade de origem
(microrrede/incarnação/revisão/impressões, cenário/versão), versões, hashes de TODAS as entradas (inventário EMS,
matriz de parâmetros, preflight, previsão, realização, entrada canônica, plano), discretização, resumo do solver,
plano (decisões), estados inicial e final, checkpoint final, indicadores físicos, custos, diagnósticos, tempos e
informação de reprodução.

**Custo realizado × valor futuro (separação obrigatória):**

* ``CustoRealizado`` — o que efetivamente se incorre na execução, recalculado a partir do que foi APLICADO e do
  entorno REALIZADO, só com termos do objetivo declarados e coeficientes declarados. Não pode conter termo terminal.
* ``custo_objetivo_planejado`` — termos do objetivo do PLANO (otimizador); não é custo pago.
* ``AvaliacaoValorFuturo`` — avaliação econômica de um estado terminal usada por um planejador (3C-4). No 3C-0 é
  sempre ``nao_implementado_3C0`` com ``valor_R = None``; ``contabilizado_como_custo`` é SEMPRE falso (invariante).

Persistência: arquivo JSON por execução, criado de forma EXCLUSIVA e publicado atomicamente (hard link de um temporário
completo; sem hard link, reserva ``O_EXCL`` + ``os.replace``); regravar o mesmo UID com conteúdo diferente é recusado mesmo entre processos concorrentes (H-03). A integração com o banco de cada microrrede (``MicrogridStore``) NÃO é feita no 3C-0.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

from .. import ROTULO_EVIDENCIA
from ..contracts import EntradaModeloEMS
from ..diagnostics import Constatacao, ContratoInvalido, erro
from ..reference import vazao_pwl
from . import CONTRATO_VERSAO
from .canonico import de_json, json_canonico, sha256
from .cenario import Realizacao
from .execucao import Checkpoint, EstadoMicrorrede, PlanoDespacho, TrajetoriaExecutada, entorno_realizado
from .instrumentacao import DESFECHOS

_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
TERMOS_PROIBIDOS_NO_REALIZADO = ("terminal", "valor_futuro")
METODOS_VALOR_FUTURO = {"nao_implementado_3C0": "Função de valor futuro ainda não implementada (3C-4: reotimização "
                                                "paramétrica do MILP; duais de MILP NÃO são tomados como preços-sombra)"}
SUFIXO_ARQUIVO = ".ems3c0.json"


@dataclass(frozen=True)
class ComponenteCusto:
    termo: str
    valor_R: float
    base: str                       # "realizado" (aplicado + entorno realizado)
    detalhe: str = ""


@dataclass(frozen=True)
class CustoRealizado:
    componentes: tuple[ComponenteCusto, ...]
    total_R: float
    intervalos: int                 # intervalos efetivamente executados


@dataclass(frozen=True)
class AvaliacaoValorFuturo:
    metodo: str
    indice_fronteira_terminal: int | None
    valor_R: float | None
    contabilizado_como_custo: bool
    observacao: str = ""


def valor_futuro_nao_implementado(indice_fronteira_terminal: int | None) -> AvaliacaoValorFuturo:
    return AvaliacaoValorFuturo("nao_implementado_3C0", indice_fronteira_terminal, None, False,
                                METODOS_VALOR_FUTURO["nao_implementado_3C0"])


@dataclass(frozen=True)
class ReferenciaOrigem:
    microrrede_uid: str
    incarnacao: str | None
    revisao_config: int
    impressao_config: str
    impressao_inventario: str
    hash_inventario_ems: str
    cenario_uid: str
    versao_cenario: int
    impressao_cenario: str


@dataclass(frozen=True)
class Discretizacao:
    inicio_utc: str
    delta_s: int
    N: int                          # intervalos da janela de controle
    m: int                          # intervalos aplicados por reotimização
    K_M: int                        # intervalos da missão
    horizonte_planejamento_min: float | None = None


@dataclass(frozen=True)
class ResumoSolver:
    classificacao: str
    estado_despacho: str
    terminacao: str | None
    objetivo: float | None
    limite_dual: float | None
    gap_abs: float | None
    gap_rel: float | None
    configuracao_json: str          # configuração do solver como recebida (JSON canônico)
    ambiente_json: str              # versões de Pyomo/HiGHS/Python registradas pelo 3B-P


@dataclass(frozen=True)
class RegistroExecucaoEMS:
    versao_contrato: int
    execucao_uid: str
    criado_utc: str
    origem: ReferenciaOrigem
    versoes: dict[str, str]
    hashes: dict[str, str]          # inventario, matriz_parametros, preflight, previsao, realizacao, entrada, plano…
    discretizacao: Discretizacao
    solver: ResumoSolver | None
    plano: PlanoDespacho | None
    estado_inicial: EstadoMicrorrede | None
    estado_final: EstadoMicrorrede | None
    situacao_execucao: str | None
    checkpoint_final: Checkpoint | None
    indicadores: dict[str, float]
    custo_realizado: CustoRealizado | None
    custo_objetivo_planejado: dict[str, float]
    valor_futuro: AvaliacaoValorFuturo
    desfecho: str
    justificativa_desfecho: str
    tempos_s: dict[str, float]
    constatacoes: tuple[Constatacao, ...]
    reproducao: dict[str, str]
    rotulo: str = ROTULO_EVIDENCIA
    selo: str = ""


# ------------------------------------------------------------------------------------------------ cálculo
def _passos_com_entorno(traj: TrajetoriaExecutada, real: Realizacao, plano: PlanoDespacho):
    from datetime import timedelta

    from ..timegrid import ler_instante_utc
    t0 = ler_instante_utc(plano.inicio_utc, "plano")[0]
    for p in traj.passos:
        t = (t0 + timedelta(seconds=plano.delta_s * p.indice_plano)).isoformat()
        ent, c = entorno_realizado(real, t, plano.delta_s)
        if c:
            raise ContratoInvalido(c)
        yield p, ent


def indicadores_e_custo(entrada: EntradaModeloEMS, plano: PlanoDespacho, traj: TrajetoriaExecutada,
                        real: Realizacao) -> tuple[dict[str, float], CustoRealizado]:
    """Indicadores físicos e CUSTO REALIZADO sobre os intervalos efetivamente executados (energia = potência média ×
    h; o estado terminal não é integrado). Coeficientes: os DECLARADOS na entrada; termos: os do objetivo."""
    h = plano.delta_s / 3600.0
    termos = set(entrada.politica_objetivo.termos)
    acc = {k: [] for k in ("E_demanda_realizada_kWh", "E_renovavel_usada_kWh", "E_curtailment_kWh", "E_indisponivel_kWh",
                           "E_bess_carga_kWh", "E_bess_descarga_kWh", "E_geracao_kWh", "E_nao_suprida_kWh",
                           "E_descarte_kWh")}
    custo = {t: [] for t in ("curtailment_operacional", "throughput_bess", "energia_nao_suprida", "combustivel_h2")}
    ren = {str(r.uid): r for r in entrada.renovaveis}
    bat = {str(b.uid): b for b in entrada.baterias}
    dem = {str(d.uid): d for d in entrada.demandas}
    gen = {str(g.uid): g for g in entrada.geradores}
    for p, ent in _passos_com_entorno(traj, real, plano):
        ap = p.aplicado
        for uid, r in ren.items():
            A, a, pr = ent[f"{uid}|potencia"], ent[f"{uid}|disponibilidade"], ap[f"{uid}|P_R"]
            util = A * a if r.base_potencial == "antes_da_disponibilidade" else A
            cop = util - pr
            acc["E_renovavel_usada_kWh"].append(h * pr)
            acc["E_curtailment_kWh"].append(h * cop)
            acc["E_indisponivel_kWh"].append(h * (A - util))
            if "curtailment_operacional" in termos:
                custo["curtailment_operacional"].append(float(r.custo_curtailment.valor) * h * cop)
        for uid, b in bat.items():
            pc, pd = ap[f"{uid}|P_c"], ap[f"{uid}|P_d"]
            acc["E_bess_carga_kWh"].append(h * pc)
            acc["E_bess_descarga_kWh"].append(h * pd)
            if "throughput_bess" in termos:
                custo["throughput_bess"].append(float(b.custo_throughput.valor) * h * (pc + pd))
        for uid, d in dem.items():
            ell = ap[f"{uid}|ell"]
            acc["E_demanda_realizada_kWh"].append(h * ent[f"{uid}|potencia"])
            acc["E_nao_suprida_kWh"].append(h * ell)
            if "energia_nao_suprida" in termos and d.custo_energia_nao_suprida is not None:
                custo["energia_nao_suprida"].append(float(d.custo_energia_nao_suprida.valor) * h * ell)
        for uid, g in gen.items():
            pg, u = ap[f"{uid}|p"], ap[f"{uid}|u"]
            acc["E_geracao_kWh"].append(h * pg)
            if "combustivel_h2" in termos and g.curva_h2 is not None and g.preco_h2 is not None:
                q = float(vazao_pwl(g.curva_h2.vertices, pg, u > 0.5)) if u > 0.5 else 0.0
                custo["combustivel_h2"].append(float(g.preco_h2.valor) * h * q)
        acc["E_descarte_kWh"] += [h * v for k, v in ap.items() if k.endswith("|d")]
    ind = {k: math.fsum(v) for k, v in acc.items()}
    comps = tuple(ComponenteCusto(t, math.fsum(v), "realizado", f"{len(traj.passos)} intervalo(s) executado(s)")
                  for t, v in custo.items() if t in termos)
    return ind, CustoRealizado(comps, math.fsum(c.valor_R for c in comps), len(traj.passos))


# ------------------------------------------------------------------------------------------------ validação/selo
def validar_registro(r: RegistroExecucaoEMS) -> list[Constatacao]:
    out: list[Constatacao] = []
    if r.versao_contrato != CONTRATO_VERSAO:
        out.append(erro("versao_contrato_incompativel", "versao_contrato", f"{r.versao_contrato!r}."))
    if not _HEX32.fullmatch(str(r.execucao_uid)):
        out.append(erro("execucao_uid_invalido", "execucao_uid", "Exigido UID de 32 hexadecimais."))
    if r.desfecho not in DESFECHOS:
        out.append(erro("desfecho_invalido", "desfecho", f"{r.desfecho!r}."))
    for k, v in r.hashes.items():
        if not _HEX64.fullmatch(str(v)):
            out.append(erro("hash_invalido", f"hashes[{k}]", "SHA-256 inválido."))
    vf = r.valor_futuro
    if vf.contabilizado_como_custo is not False:
        out.append(erro("valor_futuro_contabilizado_como_custo", "valor_futuro.contabilizado_como_custo",
                        "O valor futuro de um estado terminal nunca é custo efetivamente incorrido."))
    if vf.metodo not in METODOS_VALOR_FUTURO:
        out.append(erro("metodo_valor_futuro_nao_suportado_3C0", "valor_futuro.metodo",
                        f"{vf.metodo!r}: função de valor futuro é do 3C-4."))
    elif vf.valor_R is not None:
        out.append(erro("valor_futuro_sem_metodo", "valor_futuro.valor_R",
                        "Valor futuro numérico sem método implementado (3C-4)."))
    cr = r.custo_realizado
    if cr is not None:
        for c in cr.componentes:
            if c.termo in TERMOS_PROIBIDOS_NO_REALIZADO:
                out.append(erro("valor_futuro_contabilizado_como_custo", f"custo_realizado[{c.termo}]",
                                "Termo terminal/valor futuro não pode compor o custo realizado."))
            if c.base != "realizado":
                out.append(erro("custo_planejado_como_realizado", f"custo_realizado[{c.termo}]",
                                f"Base {c.base!r}: o custo realizado vem do que foi aplicado."))
        soma = math.fsum(c.valor_R for c in cr.componentes)
        if abs(soma - cr.total_R) > 1e-9 * max(1.0, abs(soma)):
            out.append(erro("total_incoerente", "custo_realizado.total_R", f"{cr.total_R} ≠ Σ componentes {soma}."))
    if "terminal" in r.custo_objetivo_planejado or "valor_futuro" in r.custo_objetivo_planejado:
        out.append(erro("termo_futuro_no_plano_3C0", "custo_objetivo_planejado", "Termo terminal não existe no 3C-0."))
    return out


def selar_registro(r: RegistroExecucaoEMS) -> RegistroExecucaoEMS:
    c = validar_registro(r)
    if c:
        raise ContratoInvalido(c)
    return replace(r, selo=sha256(replace(r, selo="")))


def verificar_registro(r: RegistroExecucaoEMS) -> list[Constatacao]:
    out = validar_registro(r)
    if r.selo != sha256(replace(r, selo="")):
        out.append(erro("registro_adulterado", "selo", "Selo não confere com o conteúdo do registro."))
    return out


# ------------------------------------------------------------------------------------------------ persistência
class RegistroImutavelError(ContratoInvalido):
    pass


_ESPERA_RESERVA_S = 2.0          # fallback: tempo máximo à espera da publicação pelo detentor da reserva


class RegistroReservaOrfaError(ContratoInvalido):
    """Reserva de publicação sem registro publicado após a espera (escritor interrompido no fallback sem hard link).
    Nada é sobrescrito; a recuperação é MANUAL (conferir e remover o arquivo de reserva)."""


def _fsync_diretorio(d: Path) -> None:
    """Durabilidade da entrada de diretório (POSIX). No Windows diretórios não abrem para fsync: ignorado."""
    try:
        fd = os.open(d, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _ja_existente(alvo: Path, texto: str) -> Path:
    """O UID já tem registro (sempre COMPLETO: as duas rotas publicam atomicamente). Idêntico ⇒ idempotente;
    diferente ⇒ ``RegistroImutavelError``."""
    if alvo.read_text(encoding="utf-8") == texto:
        return alvo
    raise RegistroImutavelError([erro("registro_imutavel", alvo.name,
                                      "Já existe registro desta execução com conteúdo diferente.")])


def _publicar_sem_hard_link(tmp: Path, alvo: Path, texto: str) -> Path:
    """Rota alternativa (C-03): RESERVA exclusiva + publicação ATÔMICA.

    1. ``O_CREAT | O_EXCL`` em ``.<arquivo>.reserva`` — um único escritor por UID (exclusão mútua portável);
    2. com a reserva: alvo já existente ⇒ comparação; senão ``os.replace(temporario_completo, alvo)`` — o alvo surge
       inteiro (rename atômico no mesmo diretório; ``MoveFileEx`` no Windows), nunca parcialmente escrito;
    3. a reserva é removida só DEPOIS da publicação; quem não obteve a reserva espera o alvo aparecer (até
       ``_ESPERA_RESERVA_S``) e compara; se não aparecer, ``RegistroReservaOrfaError`` (nada é sobrescrito)."""
    import time
    reserva = alvo.with_name(f".{alvo.name}.reserva")
    try:
        fdr = os.open(reserva, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        limite = time.monotonic() + _ESPERA_RESERVA_S
        while not alvo.exists():
            if time.monotonic() >= limite:
                raise RegistroReservaOrfaError([erro("reserva_orfa", reserva.name,
                                                     "Reserva de publicação sem registro publicado (escritor interrompido?)."
                                                     " Nada foi sobrescrito; conferir e remover a reserva manualmente.")])
            time.sleep(0.005)
        return _ja_existente(alvo, texto)
    try:
        os.close(fdr)
        if alvo.exists():
            return _ja_existente(alvo, texto)
        os.replace(tmp, alvo)
        return alvo
    finally:
        reserva.unlink(missing_ok=True)


def gravar_registro(diretorio: str | os.PathLike, r: RegistroExecucaoEMS) -> Path:
    """Criação EXCLUSIVA e publicação ATÔMICA de ``<execucao_uid>.ems3c0.json`` (H-03, C-03): nunca sobrescreve e
    nunca expõe arquivo parcial.

    1. O conteúdo canônico (selo conferido) é escrito e sincronizado num temporário ÚNICO no mesmo diretório;
    2. publicação por ``os.link(temporario, alvo)``, que FALHA se o alvo já existir (POSIX e NTFS);
    3. sistemas de arquivos sem hard link: reserva ``O_EXCL`` + ``os.replace`` (``_publicar_sem_hard_link``);
    4. o temporário (e a reserva, se obtida) é sempre removido.

    Mesmo UID e mesmo conteúdo ⇒ idempotente; conteúdo diferente ⇒ ``RegistroImutavelError``, inclusive entre
    processos concorrentes (exatamente um conteúdo vence). Supõe-se que todos os escritores de um diretório usam a
    mesma rota (o suporte a hard link é propriedade do sistema de arquivos)."""
    import tempfile
    c = verificar_registro(r)
    if c:
        raise ContratoInvalido(c)
    d = Path(diretorio)
    d.mkdir(parents=True, exist_ok=True)
    alvo = d / f"{r.execucao_uid}{SUFIXO_ARQUIVO}"
    texto = json_canonico(r)
    fd, nome_tmp = tempfile.mkstemp(prefix=f".{r.execucao_uid}.", suffix=".tmp", dir=d)
    tmp = Path(nome_tmp)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(texto.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, alvo)
        except FileExistsError:
            return _ja_existente(alvo, texto)
        except (OSError, NotImplementedError, AttributeError):
            _publicar_sem_hard_link(tmp, alvo, texto)
        _fsync_diretorio(d)
        return alvo
    finally:
        tmp.unlink(missing_ok=True)


def ler_registro(caminho: str | os.PathLike) -> RegistroExecucaoEMS:
    r = de_json(RegistroExecucaoEMS, Path(caminho).read_text(encoding="utf-8"))
    c = verificar_registro(r)
    if c:
        raise ContratoInvalido(c)
    return r


__all__ = ["AvaliacaoValorFuturo", "ComponenteCusto", "CustoRealizado", "Discretizacao", "METODOS_VALOR_FUTURO",
           "ReferenciaOrigem", "RegistroExecucaoEMS", "RegistroImutavelError", "RegistroReservaOrfaError", "ResumoSolver", "gravar_registro",
           "indicadores_e_custo", "ler_registro", "selar_registro", "validar_registro", "valor_futuro_nao_implementado",
           "verificar_registro"]
