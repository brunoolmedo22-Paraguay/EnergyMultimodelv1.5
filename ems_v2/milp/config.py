"""Configuração explícita do solver e pré-verificação do perfil 3B-P (sem Pyomo).

Não há configuração implícita: ``resolver`` exige uma ``ConfiguracaoSolver`` declarada. ``CONFIG_ANALITICA`` é a
configuração dos casos analíticos (gaps nulos, 1 thread, semente fixa) — parâmetro de SOFTWARE, não físico.

Compromisso dos geradores (perfil 3B-P): o programa ``u_{i,t}`` é FIXADO explicitamente pelo chamador para todo
gerador e deve ser CONSTANTE e igual ao estado inicial declarado (``EstadoGerador.ligado``). Como M09 (transições),
M11 (rampas) e M12 (permanências) não são modelados no 3B-P, qualquer partida/parada na janela é bloqueada em vez de
ser ignorada.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .. import FORMULACAO_3BP
from ..contracts import EntradaModeloEMS
from ..diagnostics import Constatacao, erro, pendente
from ..series import alinhar_a_malha


@dataclass(frozen=True)
class ConfiguracaoSolver:
    time_limit_s: float | None          # None = sem limite de tempo (declarado)
    threads: int
    rel_gap: float                      # mip_rel_gap do HiGHS
    abs_gap: float                      # mip_abs_gap do HiGHS
    semente: int                        # random_seed do HiGHS (reprodutibilidade)
    opcoes_highs: dict[str, object] = field(default_factory=dict)   # opções adicionais EXPLÍCITAS (registradas)


CONFIG_ANALITICA = ConfiguracaoSolver(time_limit_s=60.0, threads=1, rel_gap=0.0, abs_gap=0.0, semente=0)
_OPCOES_RESERVADAS = {"time_limit", "threads", "mip_rel_gap", "mip_abs_gap", "random_seed"}


def validar_configuracao(c) -> list[Constatacao]:
    if not isinstance(c, ConfiguracaoSolver):
        return [erro("configuracao_invalida", "configuracao", "Esperada ConfiguracaoSolver explícita.")]
    out: list[Constatacao] = []
    if c.time_limit_s is not None and (isinstance(c.time_limit_s, bool) or not isinstance(c.time_limit_s, (int, float))
                                       or not math.isfinite(c.time_limit_s) or c.time_limit_s < 0):
        out.append(erro("configuracao_invalida", "configuracao.time_limit_s", f"{c.time_limit_s!r}."))
    if isinstance(c.threads, bool) or not isinstance(c.threads, int) or c.threads < 1:
        out.append(erro("configuracao_invalida", "configuracao.threads", f"{c.threads!r}."))
    for nome in ("rel_gap", "abs_gap"):
        v = getattr(c, nome)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            out.append(erro("configuracao_invalida", f"configuracao.{nome}", f"{v!r}."))
    if isinstance(c.semente, bool) or not isinstance(c.semente, int) or c.semente < 0:
        out.append(erro("configuracao_invalida", "configuracao.semente", f"{c.semente!r}."))
    if not isinstance(c.opcoes_highs, dict) or set(c.opcoes_highs) & _OPCOES_RESERVADAS:
        out.append(erro("configuracao_invalida", "configuracao.opcoes_highs",
                        f"Opções reservadas devem usar os campos próprios: {sorted(_OPCOES_RESERVADAS)}."))
    return out


def configuracao_registro(c, valida: bool | None = None) -> dict:
    """Metadados da configuração RECEBIDA, para diagnóstico (C-3B-03). Nunca levanta exceção e nunca reinterpreta
    valores inválidos: ``opcoes_highs`` só é copiado (cópia rasa) quando é ``dict``; qualquer outro valor (None,
    número, texto, lista de pares…) é preservado tal como recebido. ``valida=False`` marca o veredito
    negativo de ``validar_configuracao``, que é chamada ANTES deste registro em ``resolver``."""
    if not isinstance(c, ConfiguracaoSolver):
        return {"tipo_recebido": type(c).__name__, "valida": False}
    op = c.opcoes_highs
    reg = {"time_limit_s": c.time_limit_s, "threads": c.threads, "rel_gap": c.rel_gap, "abs_gap": c.abs_gap,
           "semente": c.semente, "opcoes_highs": dict(op) if isinstance(op, dict) else op}
    if valida is False:                   # só marcada quando inválida: o registro de uma configuração válida é inalterado
        reg["valida"] = False
    return reg


def programa_valido(prog, N: int) -> bool:
    """Programa u: lista/tupla de exatamente N inteiros 0/1 (tipo ``int`` estrito; ``bool``, ``float`` — mesmo 1.0 —,
    texto, NaN e None são rejeitados, sem conversão)."""
    return (isinstance(prog, (list, tuple)) and len(prog) == N
            and all(type(x) is int and x in (0, 1) for x in prog))


def preflight_3bp(e: EntradaModeloEMS, compromisso: dict | None) -> list[Constatacao]:
    """Condições do perfil 3B-P além de ``validar_entrada``."""
    out: list[Constatacao] = []
    if e.versao_formulacao != FORMULACAO_3BP:
        out.append(erro("formulacao_nao_3bp", "versao_formulacao",
                        f"O MILP 3B-P só resolve entradas declaradas '{FORMULACAO_3BP}' (recebido "
                        f"{e.versao_formulacao!r}); entradas 3A não ganham capacidades implicitamente."))
    if compromisso is None:
        compromisso = {}
    if not isinstance(compromisso, dict):
        return out + [erro("compromisso_invalido", "compromisso",
                           f"Esperado dicionário UID → programa; recebido {type(compromisso).__name__}.")]
    N = e.malha.N
    estados = {str(s.uid): s for s in e.estados_geradores}
    uids = {str(g.uid) for g in e.geradores}
    for k in sorted((x for x in compromisso if x not in uids), key=repr):
        out.append(erro("compromisso_uid_desconhecido", f"compromisso[{k!r}]",
                        "Chave não é UID (texto) de gerador da entrada."))
    for g in e.geradores:
        k = str(g.uid)
        if k not in compromisso:
            out.append(pendente("compromisso_livre_nao_suportado_3BP", f"compromisso[{k}]",
                                "Commitment livre exige M09/M11/M12 (Piso 3C): declarar programa fixo."))
            continue
        prog = compromisso[k]
        if not programa_valido(prog, N):
            out.append(erro("compromisso_invalido", f"compromisso[{k}]",
                            f"Exigida sequência de {N} inteiros em {{0, 1}} (sem bool, float, texto, NaN ou None)."))
            continue
        st = estados.get(k)
        if st is None or not isinstance(st.ligado, bool):
            continue                                  # já rejeitado por validar_entrada
        if any(x != int(st.ligado) for x in prog):
            out.append(pendente("transicao_nao_modelada_3BP", f"compromisso[{k}]",
                                "Programa com partida/parada ou diferente do estado inicial: transições (M09), "
                                "rampas (M11) e permanências (M12) não são modeladas no 3B-P."))
        if any(prog):
            a, _ = alinhar_a_malha(g.disponibilidade.serie, e.malha, f"geradores[{k}].disponibilidade")
            if a is not None and any(x == 1 and av != 1.0 for x, av in zip(prog, a)):
                out.append(erro("compromisso_com_indisponibilidade", f"compromisso[{k}]", "u = 1 com a = 0."))
    return out


__all__ = ["CONFIG_ANALITICA", "ConfiguracaoSolver", "configuracao_registro", "preflight_3bp", "programa_valido",
           "validar_configuracao"]
