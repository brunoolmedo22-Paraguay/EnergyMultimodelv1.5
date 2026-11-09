"""Contrato da missão MPC (3C-2) — identidade, malha, modo experimental e políticas DECLARADAS (sem padrão).

Reutiliza ``MalhaTemporal`` (3A): Δ, N (otimização), m (reotimização), K_M (missão) e H_f (previsão) continuam campos
DISTINTOS; ``1 <= m <= N``. Toda política que muda o comportamento científico do laço é declarada com justificativa e
procedência:

* ``PoliticaTerminalMissao`` — o que acontece quando H_o = NΔ ultrapassa o fim da missão (``janela_reduzida`` ×
  ``horizonte_estendido_declarado``) e qual política de permanência 3C-1 vale nas janelas intermediárias e nas que
  alcançam o fim da missão (obrigações nunca desaparecem: são reportadas no fim);
* ``PoliticaAceitacao`` — quando um incumbente FACTÍVEL NÃO ÓTIMO (aprovado pelo auditor) pode virar plano (gap e
  terminações explícitas); sem solução, rejeitado ou fora da política ⇒ nenhum despacho;
* ``PoliticaFalhas`` — ação (``interromper`` × ``suspender``) por CLASSE de falha; não existe ação de contingência,
  reaproveitamento silencioso do plano anterior nem despacho de reserva;
* ``politica_revisao_tardia`` — revisão recebida depois de o intervalo ter sido conciliado: ``interromper`` ou
  ``registrar_sem_reconciliar`` (nunca reescreve o passado).

Identidade (``IdentidadeMissao``) reaproveita os campos da ``registro.ReferenciaOrigem`` 3C-0: microrrede,
incarnação, revisão e impressões do inventário, cenário/versão/impressão.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from ..compromisso.contrato import POLITICAS_PERMANENCIA
from ..diagnostics import Constatacao, aviso, erro
from ..ponte.canonico import sha256
from ..ponte.inventario import RE_MICRORREDE
from ..ponte.registro import ReferenciaOrigem
from ..provenance import Procedencia, validar_procedencia
from ..timegrid import MalhaTemporal, validar_malha
from ..units import exato
from . import ESQUEMA_MPC

_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

MODOS_EXPERIMENTAIS = {
    "simulacao_causal_laco_fechado": "Modo 1: a verdade sintética fica ENCAPSULADA num entorno de passo; o controlador "
                                     "só recebe confirmações/observações DEPOIS de emitir cada comando (simulação causal "
                                     "de laço fechado — não é validação de planta física)",
    "preparacao_online": "Modo 2: planos e comandos emitidos com os dados conhecidos; confirmações e observações chegam "
                         "depois (incremental_online + observado_ate_utc); conciliação pausada pela barreira C-02 até "
                         "haver observações suficientes. Nenhum equipamento real é acionado",
}
ROTULOS_INFORMACAO = {
    "causal": "Previsões causais (proveedor declarado independente da verdade); entra nas comparações principais",
    "ablacao_oraculo": "Previsão PERFEITA declarada (oráculo) — só referência de ablação, excluída das comparações causais",
}
POLITICAS_TERMINAL_MISSAO = {
    "janela_reduzida": "N_k = min(N, K_M − k): a janela termina no fim da missão; nenhuma previsão pós-missão é usada "
                       "(especificação v1.0 §13). Cada redução é registrada",
    "horizonte_estendido_declarado": "N_k = N: a janela pode ultrapassar T_M SÓ com cobertura de previsão pós-missão "
                                     "declarada e verificada em cada emissão; intervalos pós-missão nunca são aplicados "
                                     "nem contabilizados",
}
ACOES_FALHA = {
    "interromper": "Encerra a missão (estado final = último estado executado e conciliado); nenhum comando adicional",
    "suspender": "Suspende a missão no último estado conciliado; pode ser retomada (checkpoint selado) quando a causa "
                 "for removida — sem nenhum comando emitido durante a suspensão",
}
CLASSES_FALHA = {
    "previsao_invalida": "Previsão não causal, sem cobertura, de outra resolução/UID, sem vínculo ao instantâneo, oráculo "
                         "em missão causal, provedor não independente ou exceção do provedor",
    "bloqueado_validacao": "Entrada 3C-1 da janela recusada pelo contrato/preflight (antes de resolver)",
    "identidade_divergente": "Microrrede, cenário, incarnação ou missão divergentes em qualquer artefato",
    "solver_indisponivel": "Pyomo/HiGHS indisponível: nada foi resolvido",
    "falha_solver": "Erro/terminação desconhecida/ilimitado/limite SEM incumbente: nenhum despacho",
    "inviavel": "Inviabilidade provada (ou inviável-ou-ilimitado): nenhum despacho",
    "rejeitado_auditoria": "Solução rejeitada pelo auditor independente 3C-1",
    "rejeitado_integridade": "Testemunho auxiliar do MILP inconsistente",
    "fora_politica_aceitacao": "Incumbente factível não ótimo fora da política declarada (gap/terminação)",
    "consigna_inexequivel": "Consigna recusada pelo entorno ou inexequível na conciliação com a realização observada",
    "estado_nao_reconstruivel": "Confirmações/observações obrigatórias ausentes no instante da decisão: estado não "
                                "estimável (não se inventa estimador)",
    "erro_dados": "Observação inválida/ausente/conflitante na conciliação, memória ausente ou disponibilidade inválida",
    "revisao_tardia": "Revisão de intervalo já conciliado com política ``interromper``",
    "integridade": "Selo, cadeia, checkpoint, sincronização ou coerência confirmação × conciliação violados",
}
SO_INTERROMPER = ("identidade_divergente", "integridade", "consigna_inexequivel", "revisao_tardia")
POLITICAS_REVISAO_TARDIA = {
    "interromper": "Revisão de um intervalo já conciliado encerra a missão (o estado reconstruído deixou de ser "
                   "sustentado pela informação disponível)",
    "registrar_sem_reconciliar": "A revisão é registrada (append-only) e sinalizada; o estado já reconstruído e as "
                                 "decisões passadas NÃO são reescritos (não há reconciliação retroativa)",
}
TERMINACOES_LIMITE = ("maxTimeLimit", "iterationLimit", "objectiveLimit", "minStepLength", "interrupted")


@dataclass(frozen=True)
class IdentidadeMissao:
    missao_uid: str                         # 32 hexadecimais
    microrrede_uid: str
    incarnacao: str | None
    revisao_config: int
    impressao_config: str
    impressao_inventario: str
    hash_inventario_ems: str
    cenario_uid: str
    versao_cenario: int
    impressao_cenario: str

    def referencia_origem(self) -> ReferenciaOrigem:
        return ReferenciaOrigem(self.microrrede_uid, self.incarnacao, self.revisao_config, self.impressao_config,
                                self.impressao_inventario, self.hash_inventario_ems, self.cenario_uid,
                                self.versao_cenario, self.impressao_cenario)


@dataclass(frozen=True)
class PoliticaTerminalMissao:
    tipo: str                               # POLITICAS_TERMINAL_MISSAO
    permanencia_janelas_intermediarias: str  # POLITICAS_PERMANENCIA (3C-1)
    permanencia_janela_final: str           # vale nas janelas cujo horizonte alcança/ultrapassa o fim da missão
    justificativa: str
    procedencia: Procedencia | None
    cobertura_pos_missao_min: float | None = None   # só horizonte_estendido: previsão declarada além de T_M [min]


@dataclass(frozen=True)
class PoliticaAceitacao:
    aceitar_factivel_nao_otimo: bool
    gap_rel_max: float | None               # obrigatório (finito >= 0) se aceitar_factivel_nao_otimo
    terminacoes_admitidas: tuple[str, ...]  # ⊆ TERMINACOES_LIMITE; vazio se não aceita
    justificativa: str
    procedencia: Procedencia | None


@dataclass(frozen=True)
class PoliticaFalhas:
    acoes: dict[str, str]                   # CLASSES_FALHA → ACOES_FALHA (todas declaradas)
    justificativa: str
    procedencia: Procedencia | None


@dataclass(frozen=True)
class ConfiguracaoMPC:
    versao_esquema: int
    identidade: IdentidadeMissao
    malha: MalhaTemporal                    # τ_0, Δ, N, m, K_M, H_f
    modo: str                               # MODOS_EXPERIMENTAIS
    rotulo_informacao: str                  # ROTULOS_INFORMACAO
    politica_terminal: PoliticaTerminalMissao
    politica_aceitacao: PoliticaAceitacao
    politica_falhas: PoliticaFalhas
    politica_revisao_tardia: str            # POLITICAS_REVISAO_TARDIA
    procedencia: Procedencia | None


def cobertura_pos_missao_exigida_min(malha: MalhaTemporal) -> float:
    """Maior extensão além de T_M exigida por uma janela com N_k = N no cronograma nominal (k = 0, m, 2m, …) [min]."""
    N, m, K = malha.intervalos_otimizacao, malha.intervalos_reotimizacao, malha.intervalos_missao
    k, mx = 0, 0
    while k < K:
        mx = max(mx, k + N - K)
        k += min(m, K - k)
    return float(mx * exato(malha.delta_min))


def validar_configuracao_mpc(c) -> list[Constatacao]:
    if not isinstance(c, ConfiguracaoMPC):
        return [erro("configuracao_mpc_invalida", "configuracao", f"Esperada ConfiguracaoMPC; recebido {type(c).__name__}.")]
    out: list[Constatacao] = []
    if c.versao_esquema != ESQUEMA_MPC:
        out.append(erro("versao_esquema_mpc_incompativel", "versao_esquema", f"{c.versao_esquema!r}."))
    i = c.identidade
    if not isinstance(i, IdentidadeMissao):
        return out + [erro("identidade_invalida", "identidade", "IdentidadeMissao exigida.")]
    if not _HEX32.fullmatch(str(i.missao_uid)):
        out.append(erro("missao_uid_invalido", "identidade.missao_uid", "Exigidos 32 hexadecimais."))
    if not RE_MICRORREDE.fullmatch(str(i.microrrede_uid)):
        out.append(erro("microrrede_uid_invalido", "identidade.microrrede_uid", f"{i.microrrede_uid!r}."))
    if not RE_MICRORREDE.fullmatch(str(i.cenario_uid)):
        out.append(erro("cenario_uid_invalido", "identidade.cenario_uid", f"{i.cenario_uid!r}."))
    for nome in ("impressao_config", "impressao_inventario", "hash_inventario_ems", "impressao_cenario"):
        if not _HEX64.fullmatch(str(getattr(i, nome))):
            out.append(erro("impressao_invalida", f"identidade.{nome}", "SHA-256 inválido."))
    for nome in ("revisao_config", "versao_cenario"):
        v = getattr(i, nome)
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            out.append(erro("versao_invalida", f"identidade.{nome}", f"{v!r}."))
    m = c.malha
    if not isinstance(m, MalhaTemporal):
        return out + [erro("malha_invalida", "malha", "MalhaTemporal exigida.")]
    for x in validar_malha(m):
        if x.codigo == "horizonte_alem_da_missao":          # resolvido pela política terminal DECLARADA (abaixo)
            out.append(aviso("horizonte_alem_da_missao_tratado_pela_politica_terminal", x.caminho,
                             f"N > K_M: tratado por {getattr(c.politica_terminal, 'tipo', '?')!r}."))
        elif x.codigo == "horizonte_previsao_nao_declarado":
            out.append(erro("horizonte_previsao_obrigatorio_mpc", x.caminho,
                            "O MPC exige H_f declarado (cada emissão deve cobrir N_k intervalos)."))
        else:
            out.append(x)
    if c.modo not in MODOS_EXPERIMENTAIS:
        out.append(erro("modo_experimental_invalido", "modo", f"{c.modo!r}: declarar um de {sorted(MODOS_EXPERIMENTAIS)}."))
    if c.rotulo_informacao not in ROTULOS_INFORMACAO:
        out.append(erro("rotulo_informacao_invalido", "rotulo_informacao", f"{c.rotulo_informacao!r}."))
    out += _validar_terminal(c.politica_terminal, m)
    out += _validar_aceitacao(c.politica_aceitacao)
    out += _validar_falhas(c.politica_falhas)
    if c.politica_revisao_tardia not in POLITICAS_REVISAO_TARDIA:
        out.append(erro("politica_revisao_tardia_invalida", "politica_revisao_tardia",
                        f"{c.politica_revisao_tardia!r}: declarar uma de {sorted(POLITICAS_REVISAO_TARDIA)}."))
    out += validar_procedencia(c.procedencia, "procedencia", sustenta_valor=False)
    return out


def _validar_terminal(p, m: MalhaTemporal) -> list[Constatacao]:
    cam = "politica_terminal"
    if not isinstance(p, PoliticaTerminalMissao):
        return [erro("politica_terminal_invalida", cam, "PoliticaTerminalMissao exigida.")]
    out: list[Constatacao] = []
    if p.tipo not in POLITICAS_TERMINAL_MISSAO:
        out.append(erro("politica_terminal_invalida", cam + ".tipo", f"{p.tipo!r}: sem padrão."))
    for nome in ("permanencia_janelas_intermediarias", "permanencia_janela_final"):
        if getattr(p, nome) not in POLITICAS_PERMANENCIA:
            out.append(erro("politica_permanencia_invalida", f"{cam}.{nome}", f"{getattr(p, nome)!r}: sem padrão."))
    if not str(p.justificativa).strip():
        out.append(erro("politica_sem_justificativa", cam + ".justificativa", "Justificativa explícita exigida."))
    out += validar_procedencia(p.procedencia, cam + ".procedencia", sustenta_valor=False)
    cob = p.cobertura_pos_missao_min
    if p.tipo == "janela_reduzida" and cob is not None:
        out.append(erro("cobertura_pos_missao_contraditoria", cam + ".cobertura_pos_missao_min",
                        "Janela reduzida não usa previsões pós-missão."))
    if p.tipo == "horizonte_estendido_declarado":
        exig = cobertura_pos_missao_exigida_min(m) if isinstance(m, MalhaTemporal) else None
        if cob is None or isinstance(cob, bool) or not isinstance(cob, (int, float)) or not math.isfinite(cob) or cob < 0:
            out.append(erro("cobertura_pos_missao_nao_declarada", cam + ".cobertura_pos_missao_min",
                            "Horizonte estendido exige a cobertura pós-missão DECLARADA [min]."))
        elif exig is not None and cob < exig:
            out.append(erro("cobertura_pos_missao_insuficiente", cam + ".cobertura_pos_missao_min",
                            f"Declarada {cob} min < exigida {exig} min pelo cronograma nominal (sem extrapolação)."))
    return out


def _validar_aceitacao(p) -> list[Constatacao]:
    cam = "politica_aceitacao"
    if not isinstance(p, PoliticaAceitacao):
        return [erro("politica_aceitacao_invalida", cam, "PoliticaAceitacao exigida.")]
    out: list[Constatacao] = []
    if not isinstance(p.aceitar_factivel_nao_otimo, bool):
        out.append(erro("politica_aceitacao_invalida", cam + ".aceitar_factivel_nao_otimo", "bool exigido."))
    g = p.gap_rel_max
    if p.aceitar_factivel_nao_otimo is True:
        if g is None or isinstance(g, bool) or not isinstance(g, (int, float)) or not math.isfinite(g) or g < 0:
            out.append(erro("gap_maximo_nao_declarado", cam + ".gap_rel_max",
                            "Aceitar incumbente não ótimo exige gap relativo máximo finito >= 0."))
        if not p.terminacoes_admitidas or not set(p.terminacoes_admitidas) <= set(TERMINACOES_LIMITE):
            out.append(erro("terminacoes_admitidas_invalidas", cam + ".terminacoes_admitidas",
                            f"Declarar subconjunto não vazio de {list(TERMINACOES_LIMITE)}."))
    elif g is not None or p.terminacoes_admitidas:
        out.append(erro("politica_aceitacao_contraditoria", cam, "Gap/terminações declarados sem aceitar não ótimos."))
    if not str(p.justificativa).strip():
        out.append(erro("politica_sem_justificativa", cam + ".justificativa", "Justificativa explícita exigida."))
    out += validar_procedencia(p.procedencia, cam + ".procedencia", sustenta_valor=False)
    return out


def _validar_falhas(p) -> list[Constatacao]:
    cam = "politica_falhas"
    if not isinstance(p, PoliticaFalhas) or not isinstance(p.acoes, dict):
        return [erro("politica_falhas_invalida", cam, "PoliticaFalhas com dicionário de ações exigida.")]
    out: list[Constatacao] = []
    for k in sorted(set(p.acoes) - set(CLASSES_FALHA), key=repr):
        out.append(erro("classe_falha_desconhecida", f"{cam}.acoes[{k!r}]", "Classe não definida."))
    for k in CLASSES_FALHA:
        a = p.acoes.get(k)
        if a is None:
            out.append(erro("acao_falha_nao_declarada", f"{cam}.acoes[{k}]", "Toda classe exige ação declarada (sem padrão)."))
        elif a not in ACOES_FALHA:
            out.append(erro("acao_falha_invalida", f"{cam}.acoes[{k}]", f"{a!r}: {sorted(ACOES_FALHA)} (sem contingência)."))
        elif k in SO_INTERROMPER and a != "interromper":
            out.append(erro("acao_falha_nao_admitida", f"{cam}.acoes[{k}]", f"{k}: só 'interromper' é admitido."))
    if not str(p.justificativa).strip():
        out.append(erro("politica_sem_justificativa", cam + ".justificativa", "Justificativa explícita exigida."))
    out += validar_procedencia(p.procedencia, cam + ".procedencia", sustenta_valor=False)
    return out


def hash_configuracao(c: ConfiguracaoMPC) -> str:
    return sha256(c)


@dataclass(frozen=True)
class DecisaoAceitacao:
    aceito: bool
    categoria: str                          # "aceito_otimo" | "aceito_factivel_dentro_da_politica" | classe de falha
    justificativa: str


_FALHA_POR_CLASSIFICACAO = {"inviavel": "inviavel", "inviavel_ou_ilimitado": "inviavel",
                            "bloqueado_validacao": "bloqueado_validacao", "solver_indisponivel": "solver_indisponivel"}


def avaliar_aceitacao(res, pol: PoliticaAceitacao) -> DecisaoAceitacao:
    """Aplica o contrato existente (``aceito`` do 3B-P/3C-1) e a política declarada. Nunca aceita sem incumbente nem
    solução rejeitada pela auditoria/integridade; ``aceito_factivel_nao_otimo`` só dentro do gap/terminações declarados."""
    if res is None:
        return DecisaoAceitacao(False, "falha_solver", "Nenhum resultado produzido.")
    est, cl = getattr(res, "estado_despacho", None), getattr(res, "classificacao", None)
    if est == "rejeitado_auditoria":
        return DecisaoAceitacao(False, "rejeitado_auditoria", f"Classificação {cl!r} rejeitada pelo auditor 3C-1.")
    if est == "rejeitado_integridade":
        return DecisaoAceitacao(False, "rejeitado_integridade", f"Classificação {cl!r}: testemunho inconsistente.")
    if not getattr(res, "aceito", False) or getattr(res, "despacho", None) is None:
        return DecisaoAceitacao(False, _FALHA_POR_CLASSIFICACAO.get(cl, "falha_solver"),
                                f"Sem despacho aceito (classificação {cl!r}, estado {est!r}).")
    if est == "aceito_otimo" and cl == "otimo":
        return DecisaoAceitacao(True, "aceito_otimo", "Ótimo dentro dos gaps configurados, aprovado pelo auditor.")
    if est == "aceito_factivel_nao_otimo":
        g, term = getattr(res, "gap_rel", None), getattr(res, "terminacao", None)
        if not pol.aceitar_factivel_nao_otimo:
            return DecisaoAceitacao(False, "fora_politica_aceitacao", "Incumbente não ótimo: a política não o admite.")
        if term not in pol.terminacoes_admitidas:
            return DecisaoAceitacao(False, "fora_politica_aceitacao", f"Terminação {term!r} não admitida pela política.")
        if g is None or not math.isfinite(float(g)) or float(g) > float(pol.gap_rel_max):
            return DecisaoAceitacao(False, "fora_politica_aceitacao",
                                    f"Gap relativo {g!r} indefinido ou acima do máximo declarado {pol.gap_rel_max}.")
        return DecisaoAceitacao(True, "aceito_factivel_dentro_da_politica",
                                f"Incumbente não ótimo ({term}), gap {g} <= {pol.gap_rel_max}, aprovado pelo auditor.")
    return DecisaoAceitacao(False, "falha_solver", f"Estado de despacho não reconhecido {est!r}.")


__all__ = ["ACOES_FALHA", "CLASSES_FALHA", "ConfiguracaoMPC", "DecisaoAceitacao", "IdentidadeMissao",
           "MODOS_EXPERIMENTAIS", "POLITICAS_REVISAO_TARDIA", "POLITICAS_TERMINAL_MISSAO", "PoliticaAceitacao",
           "PoliticaFalhas", "PoliticaTerminalMissao", "ROTULOS_INFORMACAO", "SO_INTERROMPER", "TERMINACOES_LIMITE",
           "avaliar_aceitacao", "cobertura_pos_missao_exigida_min", "hash_configuracao", "validar_configuracao_mpc"]
