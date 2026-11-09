"""Registros SELADOS da missão MPC (3C-2): cadeia de janelas + registro da missão. Só biblioteca padrão.

Novos tipos versionados (os esquemas históricos 3C-0/3C-1 NÃO mudam): cada janela gera, além do
``RegistroExecucaoEMS`` 3C-0 e do anexo 3C-1 (quando houve plano executado), um ``RegistroJanelaMPC``:

* ``ConteudoJanelaMPC`` — conteúdo DETERMINÍSTICO (sem tempos de relógio): janela, instantâneo informacional da
  decisão (hash + tamanho do prefixo do livro), previsão completa, hash da entrada 3C-1, resumo do solver e auditoria,
  aceitação, plano/compromisso, comandos emitidos, confirmações usadas, conciliações, passos aplicados com o entorno
  OBSERVADO usado, estados executados, checkpoint final, custos (planejado da janela, planejado do prefixo aplicado,
  realizado) e desfecho;
* ``RegistroJanelaMPC`` — conteúdo + ``hash_conteudo`` + ``cadeia_conteudo`` (encadeamento determinístico) +
  ``selo_janela_anterior`` (encadeamento dos selos) + selos 3C-0/3C-1 + tempos medidos + selo próprio.

``RegistroMissaoMPC`` fecha a cadeia: identidade, configuração, hashes do modelo/provedor/resolvedor, sequência de
janelas, cabeça da cadeia do livro de observações, custo REALIZADO acumulado = Σ dos custos realizados das janelas
(cada um só com intervalos efetivamente aplicados; o custo planejado de janelas sobrepostas NUNCA é somado), estados
inicial/final, obrigações de permanência pendentes no fim e valor futuro "não implementado" (nunca contabilizado).
``impressao_deterministica`` = SHA-256 do conteúdo sem tempos: duas execuções da mesma missão devem coincidir.

SHA-256 detecta alteração frente a um registro CONFIÁVEL conservado; NÃO é assinatura digital (brecha K10).
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, replace

from .. import ROTULO_EVIDENCIA
from ..diagnostics import Constatacao, erro
from ..ponte.canonico import sha256
from ..ponte.cenario import ConjuntoPrevisao
from ..ponte.execucao import EstadoMicrorrede
from ..ponte.registro import AvaliacaoValorFuturo, ComponenteCusto, CustoRealizado
from . import ESQUEMA_MPC, ROTULO_MPC
from .contrato import ConfiguracaoMPC, IdentidadeMissao
from .relogio import JanelaMPC

DESFECHOS_JANELA = {
    "executada": "Plano aceito; os m_k intervalos foram aplicados, confirmados e conciliados",
    "executada_parcial": "Plano aceito; menos de m_k intervalos aplicados/conciliados (falha classificada ou suspensão)",
    "sem_plano": "Nenhum plano aceito (falha classificada): nenhum comando emitido",
}
DESFECHOS_MISSAO = {
    "concluida": "K_M intervalos aplicados e conciliados; nenhuma obrigação de permanência pendente no fim",
    "concluida_com_obrigacoes_pendentes": "K_M intervalos aplicados; obrigações de permanência além de T_M REPORTADAS",
    "interrompida": "Encerrada por falha classificada (política 'interromper'): estado final = último conciliado",
    "suspensa": "Suspensa por falha classificada (política 'suspender'): retomável do último checkpoint selado",
    "em_andamento": "Missão ainda não encerrada (registro parcial)",
}


@dataclass(frozen=True)
class ResumoResolucaoJanela:
    resolvedor: str
    classificacao: str | None
    estado_despacho: str | None
    aceito: bool
    terminacao: str | None
    status_solucao: str | None
    objetivo: float | None
    limite_dual: float | None
    gap_abs: float | None
    gap_rel: float | None
    hash_entrada: str | None
    tamanho: dict[str, int]
    garantia_permanencia: str | None
    obrigacoes_residuais_s: dict[str, int]
    eventos_planejados: dict[str, dict[str, int]]
    familias_reprovadas: tuple[str, ...]
    codigos: tuple[str, ...]
    configuracao_json: str
    versoes_ambiente_json: str


@dataclass(frozen=True)
class PassoExecutado:
    indice_global: int
    indice_plano: int
    aplicado: dict[str, float]               # consignas aplicadas (confirmadas e conciliadas)
    entorno_observado: dict[str, float]      # valores efetivos do livro usados na conciliação deste passo


@dataclass(frozen=True)
class CustosJanela:
    planejado_janela_R: dict[str, float]     # termos do objetivo da janela inteira (N_k) — NUNCA somados
    planejado_prefixo: CustoRealizado | None  # plano × previsão nos intervalos aplicados (base "planejado_previsao")
    realizado: CustoRealizado | None         # aplicado × entorno observado (só intervalos conciliados)
    diferenca_realizado_menos_planejado_R: float | None


@dataclass(frozen=True)
class RevisaoTardia:
    posicao_livro: int
    evento_uid: str
    recurso_uid: str
    grandeza: str
    inicio_utc: str
    recebido_utc: str
    classificacao: str
    politica: str


@dataclass(frozen=True)
class ConteudoJanelaMPC:
    esquema: int
    missao_uid: str
    posicao: int                              # posição na cadeia de registros (janelas re-tentadas têm nova posição)
    janela: JanelaMPC
    instante_decisao_utc: str
    hash_instantaneo: str
    n_entradas_instantaneo: int
    provedor: str
    previsao: ConjuntoPrevisao | None
    hash_previsao: str | None
    hash_entrada_3c1: str | None
    resolucao: ResumoResolucaoJanela | None
    aceitacao: str
    justificativa_aceitacao: str
    hash_plano: str | None
    hash_plano_commitment: str | None
    comandos: tuple[str, ...]
    confirmacoes: tuple[str, ...]
    intervalos_comprometidos: int
    intervalos_aplicados: int
    conciliacoes: tuple[tuple[str, str, int], ...]   # (corte, hash do instantâneo, tamanho do prefixo)
    passos: tuple[PassoExecutado, ...]
    estados: tuple[EstadoMicrorrede, ...]
    selo_checkpoint_origem: str | None       # checkpoint final da janela executada ANTERIOR (vínculo explícito)
    selo_checkpoint_final: str | None
    situacao_execucao: str | None
    custos: CustosJanela
    indicadores: dict[str, float]
    revisoes_tardias: tuple[RevisaoTardia, ...]
    desfecho: str
    classe_falha: str | None
    constatacoes: tuple[Constatacao, ...]
    execucao_uid: str | None = None          # C-02: localiza SEM ambiguidade o registro 3C-0/anexo 3C-1 da janela


@dataclass(frozen=True)
class RegistroJanelaMPC:
    conteudo: ConteudoJanelaMPC
    hash_conteudo: str
    cadeia_conteudo: str
    selo_janela_anterior: str | None
    selo_registro_3c0: str | None
    selo_anexo_3c1: str | None
    tempos_s: dict[str, float]
    criado_utc: str
    rotulo: str = ROTULO_MPC
    selo: str = ""


@dataclass(frozen=True)
class ConteudoMissaoMPC:
    esquema: int
    identidade: IdentidadeMissao
    configuracao: ConfiguracaoMPC
    hash_configuracao: str
    hash_modelo_3c1: str
    provedor: str
    impressao_provedor: str
    resolvedor_json: str
    K_M: int
    intervalos_aplicados: int
    janelas: tuple[tuple[int, int, str], ...]       # (posição, índice da janela, hash do conteúdo)
    cadeia_conteudo_final: str
    hash_cadeia_livro: str
    n_entradas_livro: int
    hash_cadeia_quarentena: str                     # C-01: cadeia própria das recepções não ordenáveis
    n_quarentena: int
    desfecho: str
    classe_falha: str | None
    estado_inicial: EstadoMicrorrede
    estado_final: EstadoMicrorrede
    custo_realizado_acumulado: CustoRealizado
    custo_planejado_prefixos_R: float               # Σ dos planejados dos PREFIXOS aplicados (comparável ao realizado)
    indicadores_acumulados: dict[str, float]
    obrigacoes_pendentes_fim_s: dict[str, int]
    valor_futuro: AvaliacaoValorFuturo
    constatacoes: tuple[Constatacao, ...]


@dataclass(frozen=True)
class RegistroMissaoMPC:
    conteudo: ConteudoMissaoMPC
    impressao_deterministica: str
    selos_janelas: tuple[str, ...]
    tempos_s: dict[str, float]
    ambiente_json: str
    criado_utc: str
    rotulo: str = ROTULO_MPC
    rotulo_evidencia: str = ROTULO_EVIDENCIA
    selo: str = ""


def _h(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def genese_cadeia(missao_uid: str) -> str:
    return _h(f"mpc3c2|{ESQUEMA_MPC}|{missao_uid}")


def encadear(anterior: str, hash_conteudo: str) -> str:
    return _h(f"{anterior}|{hash_conteudo}")


def selar(r):
    return replace(r, selo=sha256(replace(r, selo="")))


def selo_confere(r) -> bool:
    return r.selo == sha256(replace(r, selo=""))


def montar_registro_janela(conteudo: ConteudoJanelaMPC, anterior: RegistroJanelaMPC | None, *, selo_3c0: str | None,
                           selo_3c1: str | None, tempos_s: dict[str, float], criado_utc: str) -> RegistroJanelaMPC:
    hc = sha256(conteudo)
    cad = encadear(anterior.cadeia_conteudo if anterior else genese_cadeia(conteudo.missao_uid), hc)
    return selar(RegistroJanelaMPC(conteudo, hc, cad, anterior.selo if anterior else None, selo_3c0, selo_3c1,
                                   {k: float(v) for k, v in sorted(tempos_s.items()) if isinstance(v, (int, float))
                                    and not isinstance(v, bool) and math.isfinite(float(v))}, criado_utc))


def custo_acumulado(registros) -> CustoRealizado:
    """Σ por termo dos custos REALIZADOS das janelas (cada um só com intervalos aplicados): sem dupla contagem."""
    termos: dict[str, list[float]] = {}
    n = 0
    for r in registros:
        cr = r.conteudo.custos.realizado
        if cr is None:
            continue
        n += cr.intervalos
        for c in cr.componentes:
            termos.setdefault(c.termo, []).append(c.valor_R)
    comps = tuple(ComponenteCusto(t, math.fsum(v), "realizado", f"Σ de {len(v)} janela(s)") for t, v in sorted(termos.items()))
    return CustoRealizado(comps, math.fsum(c.valor_R for c in comps), n)


def verificar_cadeia_janelas(registros, cfg: ConfiguracaoMPC | None = None) -> list[Constatacao]:
    """Integridade e continuidade INDEPENDENTES da execução: selos, hashes de conteúdo, cadeia determinística, cadeia
    de selos, posições, contador global (k_{p+1} = k_p + aplicados_p), continuidade de estados e Σ aplicados <= K_M."""
    out: list[Constatacao] = []
    ant = None
    total = 0
    for p, r in enumerate(registros):
        cam = f"janelas[{p}]"
        c = r.conteudo
        if not selo_confere(r):
            out.append(erro("registro_janela_adulterado", cam + ".selo", "Selo não confere."))
        if r.hash_conteudo != sha256(c):
            out.append(erro("conteudo_janela_adulterado", cam + ".hash_conteudo", "Hash do conteúdo não confere."))
        esperado = encadear(ant.cadeia_conteudo if ant else genese_cadeia(c.missao_uid), r.hash_conteudo)
        if r.cadeia_conteudo != esperado:
            out.append(erro("cadeia_janelas_quebrada", cam + ".cadeia_conteudo", "Encadeamento determinístico violado."))
        if r.selo_janela_anterior != (ant.selo if ant else None):
            out.append(erro("cadeia_janelas_quebrada", cam + ".selo_janela_anterior", "Vínculo ao registro anterior."))
        if c.posicao != p:
            out.append(erro("posicao_janela_incoerente", cam + ".posicao", f"{c.posicao} ≠ {p}."))
        if len(c.estados) != c.intervalos_aplicados + 1 or len(c.passos) != c.intervalos_aplicados:
            out.append(erro("trajetoria_janela_incoerente", cam, "estados ≠ aplicados + 1 ou passos ≠ aplicados."))
        if c.intervalos_aplicados > c.janela.m_k or c.intervalos_aplicados > c.intervalos_comprometidos:
            out.append(erro("aplicados_alem_do_comprometido", cam, "Intervalos aplicados > m_k/comandos emitidos."))
        if c.estados and (c.estados[0].indice_fronteira != c.janela.k or
                          any(e.indice_fronteira != c.janela.k + i for i, e in enumerate(c.estados))):
            out.append(erro("indice_fronteira_incoerente", cam + ".estados", "Fronteiras não contíguas desde k."))
        if any(x.indice_global != c.janela.k + i for i, x in enumerate(c.passos)):
            out.append(erro("indice_global_incoerente", cam + ".passos", "Passos não contíguos desde k."))
        if ant is not None:
            a = ant.conteudo
            if c.janela.k != a.janela.k + a.intervalos_aplicados:
                out.append(erro("contador_global_incoerente", cam + ".janela.k",
                                f"k = {c.janela.k} ≠ {a.janela.k} + {a.intervalos_aplicados} (o contador nunca retrocede "
                                "nem salta)."))
            if a.estados and c.estados and a.estados[-1] != c.estados[0]:
                out.append(erro("estado_descontinuo", cam + ".estados[0]",
                                "Estado inicial ≠ estado final EXECUTADO da janela anterior."))
        origem = next((x.conteudo.selo_checkpoint_final for x in reversed(registros[:p])
                       if x.conteudo.selo_checkpoint_final is not None), None)
        if c.selo_checkpoint_origem != origem:
            out.append(erro("vinculo_checkpoint_quebrado", cam + ".selo_checkpoint_origem",
                            "A janela não referencia o checkpoint final da última janela executada."))
        if c.passos and c.aceitacao not in ("aceito_otimo", "aceito_factivel_dentro_da_politica"):
            out.append(erro("aplicacao_sem_plano_aceito", cam, "Intervalos aplicados sem plano aceito."))
        total += c.intervalos_aplicados
        ant = r
    if cfg is not None and total > cfg.malha.intervalos_missao:
        out.append(erro("missao_excedida", "janelas", f"Σ aplicados {total} > K_M {cfg.malha.intervalos_missao}."))
    return out


def verificar_registro_missao(rm: RegistroMissaoMPC, registros) -> list[Constatacao]:
    out = list(verificar_cadeia_janelas(registros, rm.conteudo.configuracao))
    c = rm.conteudo
    if not selo_confere(rm):
        out.append(erro("registro_missao_adulterado", "missao.selo", "Selo não confere."))
    if rm.impressao_deterministica != sha256(c):
        out.append(erro("conteudo_missao_adulterado", "missao.impressao_deterministica", "Impressão não confere."))
    if rm.selos_janelas != tuple(r.selo for r in registros):
        out.append(erro("janelas_da_missao_divergentes", "missao.selos_janelas", "Sequência de selos ≠ registros."))
    if c.janelas != tuple((r.conteudo.posicao, r.conteudo.janela.indice_janela, r.hash_conteudo) for r in registros):
        out.append(erro("janelas_da_missao_divergentes", "missao.janelas", "Sequência de conteúdos ≠ registros."))
    if registros and c.cadeia_conteudo_final != registros[-1].cadeia_conteudo:
        out.append(erro("cadeia_janelas_quebrada", "missao.cadeia_conteudo_final", "Cabeça da cadeia divergente."))
    if c.intervalos_aplicados != sum(r.conteudo.intervalos_aplicados for r in registros):
        out.append(erro("intervalos_aplicados_incoerentes", "missao.intervalos_aplicados", "≠ Σ das janelas."))
    acc = custo_acumulado(registros)
    if abs(acc.total_R - c.custo_realizado_acumulado.total_R) > 1e-9 * max(1.0, abs(acc.total_R)) or \
            {x.termo for x in acc.componentes} != {x.termo for x in c.custo_realizado_acumulado.componentes}:
        out.append(erro("custo_acumulado_incoerente", "missao.custo_realizado_acumulado",
                        f"{c.custo_realizado_acumulado.total_R!r} ≠ Σ realizados das janelas {acc.total_R!r}."))
    if any(x.termo in ("terminal", "valor_futuro") for x in c.custo_realizado_acumulado.componentes):
        out.append(erro("valor_futuro_contabilizado_como_custo", "missao.custo_realizado_acumulado", "Proibido."))
    if c.valor_futuro.contabilizado_como_custo is not False or c.valor_futuro.valor_R is not None:
        out.append(erro("valor_futuro_contabilizado_como_custo", "missao.valor_futuro", "Valor futuro não implementado."))
    if registros:
        if registros[0].conteudo.estados and registros[0].conteudo.estados[0] != c.estado_inicial:
            out.append(erro("estado_inicial_divergente", "missao.estado_inicial", "≠ estado inicial da 1ª janela."))
        ult = [r for r in registros if r.conteudo.estados]
        if ult and ult[-1].conteudo.estados[-1] != c.estado_final:
            out.append(erro("estado_final_divergente", "missao.estado_final", "≠ último estado executado."))
    return out


__all__ = ["ConteudoJanelaMPC", "ConteudoMissaoMPC", "CustosJanela", "DESFECHOS_JANELA", "DESFECHOS_MISSAO",
           "PassoExecutado", "RegistroJanelaMPC", "RegistroMissaoMPC", "ResumoResolucaoJanela", "RevisaoTardia",
           "custo_acumulado", "encadear", "genese_cadeia", "montar_registro_janela", "selar", "selo_confere",
           "verificar_cadeia_janelas", "verificar_registro_missao"]
