"""Contrato do perfil ``v1.1-3C-3`` — Ponto de Acoplamento Comum (PCC), tarifas e política econômica — só biblioteca padrão.

Extensão CONTROLADA e versionada, sem tocar nenhum contrato anterior: a entrada 3C-3 é um EMBRULHO (``EntradaRede3C3``)
que contém uma ``EntradaCommitment3C1`` (validada por ``validar_entrada_3c1`` SEM relaxação; sua base continua
declarada ``v1.1-3B-P``) e acrescenta o PCC e a política econômica do intercâmbio. Consequências verificáveis:

* nenhuma entrada 3A/3B-P/3C-1 ganha capacidades implicitamente: o PCC só existe dentro deste embrulho e a formulação
  ``v1.1-3C-3`` não é aceita por ``contracts.validar_entrada`` nem por ``validar_entrada_3c1`` (perfil próprio);
* JSON canônico e SHA-256 PRÓPRIOS (``hash_entrada_3c3``), que incluem o texto canônico do 3C-1 embutido;
* a base 3B-P continua declarando ``fronteira.topologia = "isolada"`` (único valor do contrato 3A). No 3C-3 essa
  fronteira é lida como o BARRAMENTO INTERNO da microrrede (recursos próprios, sem o PCC); a interconexão existe
  exclusivamente no embrulho (interpretação registrada — contradição C-3C3-01, FORMULACAO_3C3 §10).

Notação (kW líquidos no barramento equivalente, convenção do contrato 3A):

* ``P_imp_t >= 0`` importação (injeta no barramento), ``P_exp_t >= 0`` exportação (consome do barramento),
  ``P_net_t = P_imp_t − P_exp_t`` (positivo ao importar);
* ``P̄_imp_t``, ``P̄_exp_t`` limites CONTRATADOS por intervalo [kW] (séries declaradas; 0 é admitido e significa
  capacidade contratada nula — rede disponível NÃO garante intercâmbio);
* ``a_t ∈ {0, 1}`` disponibilidade do PCC (série declarada; fracionária não suportada);
* ``c_imp_t``, ``c_exp_t`` [R$/kWh] perfis tarifários por blocos (valor do bloco que CONTÉM o intervalo inteiro).

Regras científicas (sem valor padrão; ausência ⇒ constatação bloqueante, NUNCA "sem restrição"):

* PCC ausente do inventário NÃO é conexão ilimitada: o modo é declarado (``conectado`` × ``isolado_declarado``);
* cada sentido é permitido ou proibido por declaração (``sentidos_permitidos``); sentido permitido EXIGE limite
  declarado; sentido proibido não pode trazer limite (sem ambiguidade);
* importação permitida EXIGE o termo ``importacao_rede`` com perfil tarifário (a rede não é energia gratuita);
  exportação permitida exige remuneração DECLARADA: ``remunerada`` (termo ``exportacao_rede`` + perfil) ou
  ``sem_remuneracao`` (crédito nulo declarado, sem perfil);
* preços negativos não são suportados no 3C-3 (``preco_negativo``); preço desconhecido (``valor = None``) usado ⇒
  ``pendente``; intervalo que atravessa dois blocos ⇒ erro (nenhum rateio inventado);
* decisão causal: perfis de natureza ``contratual_conhecida`` ou ``prevista`` emitidos até o início da janela;
  ``aplicavel_liquidacao`` só em ablação oráculo ROTULADA.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import timedelta

from ..compromisso.contrato import EntradaCommitment3C1, validar_entrada_3c1
from ..contracts import (Disponibilidade, ErroSerializacao, UIDRecurso, _constante_proibida, de_dict, para_dict,
                         validar_uid)
from ..diagnostics import Constatacao, RelatorioValidacao, aviso, erro, pendente
from ..provenance import Procedencia, validar_procedencia
from ..series import SerieTemporal, alinhar_a_malha, validar_serie
from ..timegrid import MalhaTemporal, ler_instante_utc
from . import ESQUEMA_3C3, FORMULACAO_3C3

MODOS_CONEXAO = {
    "conectado": "Microrrede conectada ao PCC declarado (intercâmbio sujeito a limites, disponibilidade e sentidos)",
    "isolado_declarado": "Operação ISOLADA declarada: nenhum intercâmbio existe (P_imp = P_exp = 0 por construção)",
}
SENTIDOS = {
    "importacao_e_exportacao": "Importação e exportação permitidas (nunca simultâneas)",
    "somente_importacao": "Só importação; exportação PROIBIDA",
    "somente_exportacao": "Só exportação; importação PROIBIDA",
    "nenhum": "Nenhum sentido permitido (obrigatório no modo isolado)",
}
GRANDEZAS_PRECO = {
    "importacao": "Preço da energia importada [R$/kWh]",
    "exportacao": "Remuneração da energia exportada [R$/kWh]",
    "desvio_positivo": "Preço do desvio positivo (importação líquida realizada ACIMA da programada) [R$/kWh]",
    "desvio_negativo": "Crédito do desvio negativo (importação líquida realizada ABAIXO da programada) [R$/kWh]",
}
NATUREZAS_PRECO = {
    "contratual_conhecida": "Tarifa contratual conhecida por antecipação (vale para decisão e liquidação)",
    "prevista": "Preço PREVISTO (só decisão; nunca liquida)",
    "aplicavel_liquidacao": "Preço efetivamente aplicável à liquidação (na decisão, só em ablação oráculo rotulada)",
}
REGRAS_APLICACAO = {
    "valor_do_bloco_que_contem_o_intervalo": "Cada intervalo [t, t+Δ) deve estar INTEIRO dentro de um bloco; o preço é "
                                             "o valor desse bloco (nenhum rateio; intervalo que atravessa blocos ⇒ erro)",
}
REMUNERACOES_EXPORTACAO = {
    "remunerada": "Exportação remunerada pelo perfil declarado (termo 'exportacao_rede')",
    "sem_remuneracao": "Exportação permitida SEM remuneração (crédito nulo DECLARADO; sem perfil)",
    "nao_aplicavel": "Exportação proibida ou operação isolada",
}
TERMOS_REDE = {
    "importacao_rede": "J_imp = h Σ_t c_imp_t P_imp_t [R$] (gasto; >= 0)",
    "exportacao_rede": "J_exp = −h Σ_t c_exp_t P_exp_t [R$] (crédito; <= 0)",
}
ROTULOS_INFORMACAO_TARIFA = {"causal": "Só preços disponíveis na decisão (emitidos até τ_k; nunca o de liquidação)",
                             "ablacao_oraculo": "Ablação ROTULADA: admite o preço de liquidação na decisão"}


# =============================================================================== dataclasses
@dataclass(frozen=True)
class BlocoTarifario:
    inicio_utc: str
    duracao_s: int
    valor: float | None                   # R$/kWh; None = preço DESCONHECIDO (explícito)


@dataclass(frozen=True)
class PerfilTarifario:
    uid: str                              # identificador do perfil (estável entre revisões)
    grandeza: str                         # GRANDEZAS_PRECO
    natureza: str                         # NATUREZAS_PRECO
    unidade: str                          # "R$/kWh"
    blocos: tuple[BlocoTarifario, ...]
    revisao: int                          # >= 0
    emitido_utc: str                      # instante de emissão/disponibilidade
    regra_aplicacao: str                  # REGRAS_APLICACAO
    contrato_uid: str                     # contrato do PCC a que se refere
    procedencia: Procedencia | None
    rotulo: str = ""                      # p. ex. "SINTÉTICA — não é tarifa real"


@dataclass(frozen=True)
class EspecPCC:
    uid: UIDRecurso
    microrrede_uid: str
    modo: str                             # MODOS_CONEXAO
    sentidos_permitidos: str              # SENTIDOS
    contrato_uid: str
    limite_importacao: SerieTemporal | None   # P̄_imp [kW]; obrigatório se importação permitida
    limite_exportacao: SerieTemporal | None   # P̄_exp [kW]; obrigatório se exportação permitida
    disponibilidade: Disponibilidade | None   # a_t; obrigatória no modo conectado
    medidor_importacao_uid: UIDRecurso | None  # registro de energia importada (observação 'potencia' >= 0)
    medidor_exportacao_uid: UIDRecurso | None  # registro de energia exportada
    procedencia: Procedencia | None
    justificativa: str


@dataclass(frozen=True)
class PoliticaEconomicaRede:
    termos: tuple[str, ...]               # ⊆ TERMOS_REDE
    remuneracao_exportacao: str           # REMUNERACOES_EXPORTACAO
    tarifa_importacao: PerfilTarifario | None
    tarifa_exportacao: PerfilTarifario | None
    rotulo_informacao: str                # ROTULOS_INFORMACAO_TARIFA
    procedencia: Procedencia | None
    justificativa: str


@dataclass(frozen=True)
class EntradaRede3C3:
    versao_esquema_3c3: int
    versao_formulacao: str                # == FORMULACAO_3C3
    compromisso: EntradaCommitment3C1     # núcleo 3C-1 (validado sem relaxação)
    pcc: EspecPCC
    economia: PoliticaEconomicaRede
    procedencia: Procedencia | None

    @property
    def base(self):
        return self.compromisso.base

    @property
    def termos(self) -> tuple[str, ...]:
        return tuple(self.compromisso.termos) + tuple(self.economia.termos)

    @property
    def conectado(self) -> bool:
        return self.pcc.modo == "conectado"

    @property
    def importa(self) -> bool:
        return self.conectado and self.pcc.sentidos_permitidos in ("importacao_e_exportacao", "somente_importacao")

    @property
    def exporta(self) -> bool:
        return self.conectado and self.pcc.sentidos_permitidos in ("importacao_e_exportacao", "somente_exportacao")


# =============================================================================== tarifas
def _t(x):
    return ler_instante_utc(x, "t")[0]


def hash_perfil(p: PerfilTarifario) -> str:
    from ..ponte.canonico import sha256
    return sha256(p)


def validar_perfil(p: PerfilTarifario, cam: str, *, grandeza: str | None = None, contrato_uid: str | None = None
                   ) -> list[Constatacao]:
    if not isinstance(p, PerfilTarifario):
        return [erro("perfil_tarifario_invalido", cam, f"Esperado PerfilTarifario; recebido {type(p).__name__}.")]
    out: list[Constatacao] = []
    if not isinstance(p.uid, str) or not p.uid.strip():
        out.append(erro("perfil_tarifario_sem_uid", cam + ".uid", "Identificador do perfil ausente."))
    if p.grandeza not in GRANDEZAS_PRECO:
        out.append(erro("grandeza_preco_invalida", cam + ".grandeza", f"{p.grandeza!r}."))
    elif grandeza is not None and p.grandeza != grandeza:
        out.append(erro("grandeza_preco_incompativel", cam + ".grandeza", f"{p.grandeza!r}; esperada {grandeza!r}."))
    if p.natureza not in NATUREZAS_PRECO:
        out.append(erro("natureza_preco_invalida", cam + ".natureza", f"{p.natureza!r} (sem padrão)."))
    if p.unidade != "R$/kWh":
        out.append(erro("unidade_preco_incompativel", cam + ".unidade", f"{p.unidade!r}; exigida 'R$/kWh' (sem conversão)."))
    if p.regra_aplicacao not in REGRAS_APLICACAO:
        out.append(erro("regra_aplicacao_invalida", cam + ".regra_aplicacao", f"{p.regra_aplicacao!r} (sem padrão)."))
    if isinstance(p.revisao, bool) or not isinstance(p.revisao, int) or p.revisao < 0:
        out.append(erro("revisao_tarifa_invalida", cam + ".revisao", f"{p.revisao!r}."))
    out += ler_instante_utc(p.emitido_utc, cam + ".emitido_utc")[1]
    out += validar_procedencia(p.procedencia, cam + ".procedencia")
    if contrato_uid is not None and p.contrato_uid != contrato_uid:
        out.append(erro("tarifa_de_outro_contrato", cam + ".contrato_uid",
                        f"Perfil do contrato {p.contrato_uid!r}; o PCC declara {contrato_uid!r}."))
    if not p.blocos:
        out.append(erro("perfil_tarifario_vazio", cam + ".blocos", "Perfil sem blocos."))
    fim_ant = None
    for i, b in enumerate(p.blocos):
        cb = f"{cam}.blocos[{i}]"
        ti, ci = ler_instante_utc(b.inicio_utc, cb + ".inicio_utc")
        out += ci
        if isinstance(b.duracao_s, bool) or not isinstance(b.duracao_s, int) or b.duracao_s <= 0:
            out.append(erro("bloco_duracao_invalida", cb + ".duracao_s", f"{b.duracao_s!r}: segundos inteiros > 0."))
            continue
        if b.valor is not None:
            if isinstance(b.valor, bool) or not isinstance(b.valor, (int, float)) or not math.isfinite(b.valor):
                out.append(erro("preco_nao_finito", cb + ".valor", "Preço NaN/Inf/não numérico (ausente é None)."))
            elif b.valor < 0:
                out.append(erro("preco_negativo", cb + ".valor",
                                f"{b.valor} R$/kWh: preços negativos não são suportados no 3C-3 (exigiriam tratamento "
                                "próprio de arbitragem)."))
        if ti is None:
            continue
        if fim_ant is not None and ti < fim_ant:
            out.append(erro("blocos_sobrepostos_ou_desordenados", cb, "Blocos fora de ordem ou sobrepostos."))
        fim_ant = ti + timedelta(seconds=b.duracao_s)
    return out


def precos_na_malha(p: PerfilTarifario, malha: MalhaTemporal, cam: str) -> tuple[tuple[float, ...] | None,
                                                                                 list[Constatacao]]:
    """Preço de cada intervalo da malha: valor do bloco que CONTÉM o intervalo inteiro (sem rateio/extrapolação)."""
    blocos = []
    for b in p.blocos:
        ti, _ = ler_instante_utc(b.inicio_utc, "b")
        if ti is None:
            return None, [erro("bloco_ilegivel", cam, "Instante de bloco ilegível.")]
        blocos.append((ti, ti + timedelta(seconds=b.duracao_s), b.valor))
    out: list[Constatacao] = []
    vals: list[float] = []
    d = timedelta(seconds=malha.delta_s)
    for t, ini in enumerate(malha.inicios_intervalos_utc()):
        fim = ini + d
        cont = [v for (a, z, v) in blocos if a <= ini and fim <= z]
        if not cont:
            parcial = any(a < fim and ini < z for (a, z, _) in blocos)
            out.append(erro("intervalo_atravessa_blocos" if parcial else "tarifa_sem_cobertura", f"{cam}[{t}]",
                            f"Intervalo [{ini.isoformat()}, {fim.isoformat()}) "
                            f"{'atravessa blocos (nenhum rateio é inventado)' if parcial else 'sem bloco (sem extrapolação)'}."))
            continue
        if cont[0] is None:
            out.append(pendente("preco_desconhecido", f"{cam}[{t}]",
                                "Preço DESCONHECIDO declarado no bloco que contém o intervalo: nada é presumido."))
            continue
        vals.append(float(cont[0]))
    if out:
        return None, out
    return tuple(vals), out


def preco_no_intervalo(p: PerfilTarifario, inicio_utc: str, delta_s: int) -> float | None:
    """Preço do intervalo [início, início+Δ) pela regra do bloco que o contém; None se não coberto/desconhecido."""
    ini = _t(inicio_utc)
    if ini is None:
        return None
    fim = ini + timedelta(seconds=delta_s)
    for b in p.blocos:
        a = _t(b.inicio_utc)
        if a is not None and a <= ini and fim <= a + timedelta(seconds=b.duracao_s):
            return None if b.valor is None else float(b.valor)
    return None


def selecionar_perfil_causal(perfis, grandeza: str, instante_utc: str, *, oraculo: bool = False
                             ) -> tuple[PerfilTarifario | None, list[Constatacao]]:
    """Seleção CAUSAL do perfil de decisão em τ: dentre os perfis da grandeza com emissão <= τ (e natureza admissível
    na decisão), o de MAIOR revisão. Nenhum perfil emitido depois de τ é consultado (exceto ablação rotulada)."""
    tk = _t(instante_utc)
    nat = ("contratual_conhecida", "prevista") + (("aplicavel_liquidacao",) if oraculo else ())
    cand = [p for p in perfis if p.grandeza == grandeza and p.natureza in nat and (oraculo or _t(p.emitido_utc) <= tk)]
    if not cand:
        return None, [erro("tarifa_indisponivel_na_decisao", f"tarifas[{grandeza}]",
                           f"Nenhum perfil de {grandeza} disponível em {instante_utc} (emitido até τ e de natureza "
                           "admissível na decisão): nada é presumido.")]
    melhor = max(cand, key=lambda p: (p.revisao, _t(p.emitido_utc)))
    dup = [p for p in cand if p.revisao == melhor.revisao and p is not melhor and p != melhor]
    if dup:
        return None, [erro("revisao_tarifaria_ambigua", f"tarifas[{grandeza}]",
                           f"Dois perfis distintos com a revisão {melhor.revisao} disponíveis em {instante_utc}.")]
    return melhor, []


# =============================================================================== séries do PCC
def valor_no_intervalo(s: SerieTemporal, inicio_utc: str, delta_s: int) -> float | None:
    """Valor da série no intervalo [início, início+Δ) (mesmo passo, alinhado; sem reamostragem/extrapolação)."""
    if s is None or s.passo_s != delta_s or s.semantica != "media_intervalo":
        return None
    ts, ti = _t(s.inicio_utc), _t(inicio_utc)
    if ts is None or ti is None:
        return None
    dd = (ti - ts).total_seconds()
    if dd < 0 or dd % delta_s:
        return None
    i = int(dd // delta_s)
    if i >= len(s.valores):
        return None
    v = s.valores[i]
    return float(v) if not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) else None


def _limite(s: SerieTemporal | None, malha: MalhaTemporal, cam: str) -> tuple[tuple[float, ...] | None, list[Constatacao]]:
    if s is None:
        return None, [erro("limite_pcc_ausente", cam, "Sentido permitido sem limite contratado declarado (ausente ≠ "
                                                      "ilimitado).")]
    out = validar_serie(s, cam, unidade="kW", grandeza="potencia")
    if any(c.severidade == "erro" for c in out):
        return None, out
    v, c = alinhar_a_malha(s, malha, cam)
    out += [x for x in c if x.codigo != "emissao_nao_declarada"]
    if v is not None:
        neg = [i for i, x in enumerate(v) if x < 0]
        if neg:
            out.append(erro("limite_pcc_negativo", cam, f"Limite negativo nos intervalos {neg[:8]}."))
            return None, out
        if all(x == 0 for x in v):
            out.append(aviso("capacidade_contratada_nula", cam,
                             "Limite contratado 0 em todos os intervalos: rede disponível não garante intercâmbio."))
    return v, out


def series_pcc(e: EntradaRede3C3, malha: MalhaTemporal | None = None) -> dict:
    """Séries do PCC alinhadas à malha (supõe entrada validada). Modo isolado ⇒ dicionário vazio."""
    m = malha or e.base.malha
    if not e.conectado:
        return {}
    a, _ = alinhar_a_malha(e.pcc.disponibilidade.serie, m, "")
    out = {"a": list(a)}
    out["imp_max"] = list(alinhar_a_malha(e.pcc.limite_importacao, m, "")[0]) if e.importa else [0.0] * m.N
    out["exp_max"] = list(alinhar_a_malha(e.pcc.limite_exportacao, m, "")[0]) if e.exporta else [0.0] * m.N
    ec = e.economia
    out["c_imp"] = list(precos_na_malha(ec.tarifa_importacao, m, "")[0]) if ec.tarifa_importacao else None
    out["c_exp"] = list(precos_na_malha(ec.tarifa_exportacao, m, "")[0]) if ec.tarifa_exportacao else None
    return out


# =============================================================================== validação
def _validar_pcc(e: EntradaRede3C3) -> list[Constatacao]:
    p, b = e.pcc, e.base
    out: list[Constatacao] = []
    if not isinstance(p, EspecPCC):
        return [erro("pcc_invalido", "pcc", f"Esperado EspecPCC; recebido {type(p).__name__}.")]
    out += validar_uid(p.uid, "pcc.uid")
    if p.microrrede_uid != b.microrrede_uid:
        out.append(erro("pcc_de_outra_microrrede", "pcc.microrrede_uid",
                        f"PCC declarado para {p.microrrede_uid!r}; a entrada é da microrrede {b.microrrede_uid!r} "
                        "(nenhum intercâmbio entre microrredes)."))
    out += validar_procedencia(p.procedencia, "pcc.procedencia")
    if not p.justificativa.strip():
        out.append(erro("pcc_sem_justificativa", "pcc.justificativa", "O modo do PCC exige justificativa explícita."))
    if not isinstance(p.contrato_uid, str) or not p.contrato_uid.strip():
        out.append(erro("pcc_sem_contrato", "pcc.contrato_uid", "Identificador do contrato ausente."))
    if p.modo not in MODOS_CONEXAO:
        return out + [erro("modo_conexao_invalido", "pcc.modo", f"{p.modo!r}: declarar {sorted(MODOS_CONEXAO)} "
                                                                  "(PCC ausente não é conexão ilimitada).")]
    if p.sentidos_permitidos not in SENTIDOS:
        return out + [erro("sentidos_invalidos", "pcc.sentidos_permitidos", f"{p.sentidos_permitidos!r} (sem padrão).")]
    usados = {str(x.uid) for x in (*b.demandas, *b.renovaveis, *b.baterias, *b.geradores)}
    if b.politica_servico.descarte is not None:
        usados.add(str(b.politica_servico.descarte.uid))
    meds = [x for x in (p.medidor_importacao_uid, p.medidor_exportacao_uid) if x is not None]
    for nome, u in (("uid", p.uid), *(("medidor", x) for x in meds)):
        if str(u) in usados:
            out.append(erro("uid_duplicado", f"pcc.{nome}", f"UID {u} já usado por recurso da microrrede."))
    if len({str(x) for x in [p.uid, *meds]}) != 1 + len(meds):
        out.append(erro("uid_duplicado", "pcc.medidores", "Medidores com UID repetido ou igual ao do PCC."))
    for x in meds:
        out += validar_uid(x, "pcc.medidor")
    if p.modo == "isolado_declarado":
        if p.sentidos_permitidos != "nenhum":
            out.append(erro("isolado_com_sentido_permitido", "pcc.sentidos_permitidos",
                            "Operação isolada declarada exige sentidos 'nenhum'."))
        for nome in ("limite_importacao", "limite_exportacao", "disponibilidade", "medidor_importacao_uid",
                     "medidor_exportacao_uid"):
            if getattr(p, nome) is not None:
                out.append(erro("isolado_com_dados_de_intercambio", f"pcc.{nome}",
                                "Modo isolado não admite limites/disponibilidade/medidores (nenhum intercâmbio existe)."))
        return out
    if p.sentidos_permitidos == "nenhum":
        out.append(erro("conectado_sem_sentido", "pcc.sentidos_permitidos",
                        "Modo conectado com nenhum sentido permitido: declarar 'isolado_declarado'."))
    m = b.malha
    if e.importa:
        out += _limite(p.limite_importacao, m, "pcc.limite_importacao")[1]
    elif p.limite_importacao is not None:
        out.append(erro("limite_de_sentido_proibido", "pcc.limite_importacao", "Importação proibida com limite declarado."))
    if e.exporta:
        out += _limite(p.limite_exportacao, m, "pcc.limite_exportacao")[1]
    elif p.limite_exportacao is not None:
        out.append(erro("limite_de_sentido_proibido", "pcc.limite_exportacao", "Exportação proibida com limite declarado."))
    if p.disponibilidade is None:
        out.append(erro("disponibilidade_pcc_ausente", "pcc.disponibilidade",
                        "PCC conectado sem disponibilidade declarada (nunca presumida 1)."))
    else:
        c = validar_serie(p.disponibilidade.serie, "pcc.disponibilidade", unidade="1", grandeza="disponibilidade")
        out += c
        if not any(x.severidade == "erro" for x in c):
            a, ca = alinhar_a_malha(p.disponibilidade.serie, m, "pcc.disponibilidade")
            out += [x for x in ca if x.codigo != "emissao_nao_declarada"]
            if a is not None and any(v not in (0.0, 1.0) for v in a):
                out.append(pendente("disponibilidade_pcc_fracionaria", "pcc.disponibilidade",
                                    "a ∉ {0, 1}: disponibilidade fracionária do PCC não suportada."))
    if (p.medidor_importacao_uid is None) != (p.medidor_exportacao_uid is None):
        out.append(erro("medidores_incompletos", "pcc.medidores",
                        "Declarar os dois registros (importação e exportação) ou nenhum."))
    return out


def _validar_economia(e: EntradaRede3C3) -> list[Constatacao]:
    ec, p = e.economia, e.pcc
    out: list[Constatacao] = []
    if not isinstance(ec, PoliticaEconomicaRede):
        return [erro("politica_economica_invalida", "economia", type(ec).__name__)]
    out += validar_procedencia(ec.procedencia, "economia.procedencia")
    if not ec.justificativa.strip():
        out.append(erro("economia_sem_justificativa", "economia.justificativa", "Justificativa explícita exigida."))
    if ec.rotulo_informacao not in ROTULOS_INFORMACAO_TARIFA:
        out.append(erro("rotulo_informacao_tarifa_invalido", "economia.rotulo_informacao", f"{ec.rotulo_informacao!r}."))
    vistos: set[str] = set()
    for t in ec.termos:
        if t not in TERMOS_REDE:
            out.append(erro("termo_rede_desconhecido", f"economia.termos[{t}]", f"{t!r}: termos {sorted(TERMOS_REDE)}."))
        if t in vistos or t in e.compromisso.termos:
            out.append(erro("termo_objetivo_duplicado", f"economia.termos[{t}]", "Termo repetido."))
        vistos.add(t)
    if ec.remuneracao_exportacao not in REMUNERACOES_EXPORTACAO:
        out.append(erro("remuneracao_exportacao_invalida", "economia.remuneracao_exportacao",
                        f"{ec.remuneracao_exportacao!r} (sem padrão)."))
    termos = set(ec.termos)
    if not e.conectado:
        if termos or ec.tarifa_importacao is not None or ec.tarifa_exportacao is not None:
            out.append(erro("isolado_com_tarifa", "economia", "Operação isolada não admite termos/tarifas de rede."))
        if ec.remuneracao_exportacao != "nao_aplicavel":
            out.append(erro("remuneracao_incoerente", "economia.remuneracao_exportacao", "Isolado ⇒ 'nao_aplicavel'."))
        return out
    m = e.base.malha
    oraculo = ec.rotulo_informacao == "ablacao_oraculo"
    t0 = m.inicio()

    def perfil(pf, gr, nome):
        c = validar_perfil(pf, f"economia.{nome}", grandeza=gr, contrato_uid=p.contrato_uid)
        if not any(x.severidade == "erro" for x in c):
            if pf.natureza == "aplicavel_liquidacao" and not oraculo:
                c.append(erro("preco_de_liquidacao_na_decisao", f"economia.{nome}.natureza",
                              "Preço de LIQUIDAÇÃO na decisão de uma entrada causal (só em ablação oráculo rotulada)."))
            if not oraculo and _t(pf.emitido_utc) > t0:
                c.append(erro("tarifa_nao_causal", f"economia.{nome}.emitido_utc",
                              f"Perfil emitido em {pf.emitido_utc}, depois do início da janela {m.inicio_utc}."))
            c += precos_na_malha(pf, m, f"economia.{nome}")[1]
        return c
    if e.importa:
        if "importacao_rede" not in termos:
            out.append(erro("importacao_sem_custo", "economia.termos",
                            "Importação permitida exige o termo 'importacao_rede' (a rede não é energia gratuita)."))
        if ec.tarifa_importacao is None:
            out.append(erro("tarifa_importacao_ausente", "economia.tarifa_importacao", "Perfil de importação ausente."))
        else:
            out += perfil(ec.tarifa_importacao, "importacao", "tarifa_importacao")
    elif "importacao_rede" in termos or ec.tarifa_importacao is not None:
        out.append(erro("coeficiente_sem_sentido", "economia.tarifa_importacao", "Importação proibida com tarifa/termo."))
    if e.exporta:
        if ec.remuneracao_exportacao == "remunerada":
            if "exportacao_rede" not in termos:
                out.append(erro("remuneracao_sem_termo", "economia.termos", "Exportação remunerada exige 'exportacao_rede'."))
            if ec.tarifa_exportacao is None:
                out.append(erro("tarifa_exportacao_ausente", "economia.tarifa_exportacao", "Perfil de exportação ausente."))
            else:
                out += perfil(ec.tarifa_exportacao, "exportacao", "tarifa_exportacao")
        elif ec.remuneracao_exportacao == "sem_remuneracao":
            if "exportacao_rede" in termos or ec.tarifa_exportacao is not None:
                out.append(erro("remuneracao_contraditoria", "economia",
                                "'sem_remuneracao' declarado com termo/perfil de exportação."))
        else:
            out.append(erro("remuneracao_exportacao_nao_declarada", "economia.remuneracao_exportacao",
                            "Exportação permitida exige 'remunerada' ou 'sem_remuneracao' declarado."))
    else:
        if ec.remuneracao_exportacao != "nao_aplicavel" or "exportacao_rede" in termos or ec.tarifa_exportacao is not None:
            out.append(erro("remuneracao_de_sentido_proibido", "economia",
                            "Exportação proibida: remuneração 'nao_aplicavel', sem termo e sem perfil."))
    if not any(x.severidade == "erro" for x in out) and ec.tarifa_importacao and ec.tarifa_exportacao:
        ci = precos_na_malha(ec.tarifa_importacao, m, "")[0]
        ce = precos_na_malha(ec.tarifa_exportacao, m, "")[0]
        if ci and ce:
            arb = [t for t in range(m.N) if ce[t] > ci[t]]
            if arb:
                out.append(aviso("remuneracao_maior_que_importacao", "economia",
                                 f"c_exp > c_imp nos intervalos {arb[:8]}: sem a exclusividade de sentidos haveria "
                                 "arbitragem simultânea artificial (a formulação a impede)."))
    return out


def validar_entrada_3c3(e: EntradaRede3C3) -> RelatorioValidacao:
    if not isinstance(e, EntradaRede3C3):
        return RelatorioValidacao((erro("entrada_3c3_invalida", "entrada", f"Esperada EntradaRede3C3; recebido "
                                                                           f"{type(e).__name__}."),))
    out: list[Constatacao] = []
    if e.versao_esquema_3c3 != ESQUEMA_3C3:
        out.append(erro("versao_esquema_3c3_incompativel", "versao_esquema_3c3", f"{e.versao_esquema_3c3!r}."))
    if e.versao_formulacao != FORMULACAO_3C3:
        out.append(erro("formulacao_nao_3c3", "versao_formulacao",
                        f"{e.versao_formulacao!r}: o embrulho de rede exige {FORMULACAO_3C3!r}."))
    out += validar_procedencia(e.procedencia, "procedencia")
    if not isinstance(e.compromisso, EntradaCommitment3C1):
        return RelatorioValidacao(tuple(out + [erro("compromisso_invalido", "compromisso",
                                                    "Núcleo deve ser EntradaCommitment3C1.")]))
    rel = validar_entrada_3c1(e.compromisso)
    out += [Constatacao(c.codigo, "compromisso." + c.caminho, c.mensagem, c.severidade) for c in rel.constatacoes]
    if not rel.aceito:
        return RelatorioValidacao(tuple(out))
    if e.base.fronteira.topologia != "isolada":
        out.append(erro("topologia_base_incompativel", "compromisso.base.fronteira.topologia",
                        "A base descreve o barramento INTERNO (topologia 'isolada' do contrato 3A); o PCC só existe no "
                        "embrulho 3C-3 (C-3C3-01)."))
    out += _validar_pcc(e)
    out += _validar_economia(e)
    return RelatorioValidacao(tuple(out))


# =============================================================================== serialização canônica
def json_canonico_3c3(e: EntradaRede3C3) -> str:
    return json.dumps(para_dict(e), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def hash_entrada_3c3(e: EntradaRede3C3) -> str:
    return hashlib.sha256(json_canonico_3c3(e).encode("utf-8")).hexdigest()


def entrada_3c3_de_json(texto: str) -> EntradaRede3C3:
    try:
        dado = json.loads(texto, parse_constant=_constante_proibida)
    except json.JSONDecodeError as exc:
        raise ErroSerializacao(f"JSON inválido: {exc}") from None
    return de_dict(EntradaRede3C3, dado, "EntradaRede3C3")


__all__ = ["BlocoTarifario", "EntradaRede3C3", "EspecPCC", "GRANDEZAS_PRECO", "MODOS_CONEXAO", "NATUREZAS_PRECO",
           "PerfilTarifario", "PoliticaEconomicaRede", "REGRAS_APLICACAO", "REMUNERACOES_EXPORTACAO",
           "ROTULOS_INFORMACAO_TARIFA", "SENTIDOS", "TERMOS_REDE", "entrada_3c3_de_json", "hash_entrada_3c3",
           "hash_perfil", "json_canonico_3c3", "precos_na_malha", "preco_no_intervalo", "selecionar_perfil_causal",
           "series_pcc", "validar_entrada_3c3", "validar_perfil", "valor_no_intervalo"]
