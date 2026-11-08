"""Contratos de cenário, condições iniciais, definição temporal e PREVISÃO × REALIZAÇÃO (3C-0 §3.3).

Separação explícita (cada uma é um tipo próprio; nenhuma é derivada implicitamente de outra):

* **Configuração da microrrede** — ``inventario.InventarioMicrorrede`` (física permanente; nunca editada aqui);
* **Cenário** — ``CenarioEMS``: condições experimentais referenciando UMA revisão do inventário (identidade +
  impressões digitais), disponibilidade por dispositivo e condições iniciais na fronteira k = 0;
* **Previsões disponíveis ao controlador** — ``ConjuntoPrevisao``: séries EMITIDAS num instante (causalidade);
* **Condições reais ou simuladas do entorno** — ``Realizacao``: o que de fato ocorre (medido/simulado/sintético).
  Nunca é entregue ao controlador. Uma previsão idêntica à realização só é aceita como ORÁCULO declarado
  (``previsao_perfeita=True`` + justificativa), rótulo indispensável para avaliar o MPC com erro de predição;
* **Horizontes e resolução** — ``DefinicaoTemporal``: reutiliza ``MalhaTemporal`` (3A: Δ, N intervalos e N+1
  fronteiras, ρ = mΔ, missão T_M, H_f). Horizonte de CONTROLE (janela do MPC de curto prazo) = H_o = NΔ;
  aplicação/reotimização = ρ; horizonte de PLANEJAMENTO (planejador de longo prazo, 3C-4) é campo reservado:
  declará-lo no 3C-0 é ``pendente`` (planejamento hierárquico não ativo).

Instantes: ISO 8601 com fuso explícito, normalizados para UTC (3A ``timegrid``). Unidades canônicas (3A ``units``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..contracts import RE_EQUIPAMENTO
from ..diagnostics import Constatacao, RelatorioValidacao, aviso, erro, pendente
from ..parameters import Parametro, validar_parametro
from ..provenance import Procedencia, validar_procedencia
from ..series import SerieTemporal, alinhar_a_malha, validar_serie
from ..timegrid import MalhaTemporal, ler_instante_utc, validar_malha
from . import CONTRATO_VERSAO
from .canonico import sha256
from .inventario import RE_MICRORREDE, InventarioMicrorrede

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
DISPONIBILIDADES = {"disponivel": "Disponível", "indisponivel": "Indisponível (excluído SÓ desta execução)"}
ESTADOS_DISCRETOS = {"desligada": "Desligada", "em_partida": "Em partida (rótulo; sem física de partida)",
                     "em_operacao": "Em operação"}
GRANDEZAS_SERIE = {"potencia": "kW", "disponibilidade": "1", "fracao_interrompivel": "1"}
NATUREZAS_REALIZACAO = {"medida": "Medida na instalação", "simulada": "Simulada por modelo físico declarado",
                        "sintetica": "Sintética (ensaio)"}


# ------------------------------------------------------------------------------------------------ cenário
@dataclass(frozen=True)
class ReferenciaInventario:
    """Revisão do inventário sobre a qual o cenário foi definido (o cenário NUNCA contém a configuração)."""
    microrrede_uid: str
    incarnacao: str | None
    revisao_config: int
    impressao_config: str
    impressao_inventario: str


@dataclass(frozen=True)
class CondicaoInicialDispositivo:
    """Condição na fronteira k = 0 declarada pelo cenário. Valores ausentes ficam ``None`` (nunca inferidos):
    p. ex. ``ligado`` não é deduzido da potência."""
    uid: str
    disponibilidade: str
    soc: Parametro | None = None                   # fração [1] (de % por conversão explícita registrada)
    estado_discreto: str | None = None             # rótulo declarado (desligada/em_partida/em_operacao)
    unidades_ligadas: int | None = None            # PEMFC: unidades em operação declaradas no registro
    potencia_kW: Parametro | None = None           # potência líquida anterior à janela (registro inteiro)
    tempo_no_estado_s: int | None = None           # memória operativa (3C-1); None = não declarado


@dataclass(frozen=True)
class CenarioEMS:
    versao_contrato: int
    cenario_uid: str
    versao_cenario: int
    impressao_cenario: str
    referencia_inventario: ReferenciaInventario
    condicoes_iniciais: tuple[CondicaoInicialDispositivo, ...]
    orfaos: tuple[str, ...]                        # UIDs com estado preservado de equipamentos retirados
    procedencia: Procedencia | None
    instante_condicoes_utc: str | None = None      # instante da fronteira k = 0 a que as condições se referem

    def condicao(self, uid: str) -> CondicaoInicialDispositivo | None:
        return next((c for c in self.condicoes_iniciais if c.uid == uid), None)


def condicao_efetiva(c: CenarioEMS, d) -> tuple[CondicaoInicialDispositivo | None, bool]:
    """Condição do dispositivo ou, para um arranjo FV sem condição própria, a da USINA que o contém (o SEEDS2 declara
    a disponibilidade por registro ``eq-…``; os arranjos são partes desse registro). Devolve (condição, herdada)."""
    propria = c.condicao(d.uid)
    if propria is not None or d.pai is None:
        return propria, False
    pai = c.condicao(d.pai)
    return pai, pai is not None


def validar_cenario(c: CenarioEMS) -> RelatorioValidacao:
    out: list[Constatacao] = []
    if c.versao_contrato != CONTRATO_VERSAO:
        out.append(erro("versao_contrato_incompativel", "versao_contrato", f"{c.versao_contrato!r}."))
    if not isinstance(c.cenario_uid, str) or not RE_MICRORREDE.fullmatch(c.cenario_uid):
        out.append(erro("cenario_uid_invalido", "cenario_uid", f"{c.cenario_uid!r}."))
    if isinstance(c.versao_cenario, bool) or not isinstance(c.versao_cenario, int) or c.versao_cenario < 1:
        out.append(erro("versao_cenario_invalida", "versao_cenario", f"{c.versao_cenario!r}."))
    if not _HEX64.fullmatch(str(c.impressao_cenario)):
        out.append(erro("impressao_invalida", "impressao_cenario", "SHA-256 inválido."))
    r = c.referencia_inventario
    if not RE_MICRORREDE.fullmatch(str(r.microrrede_uid)):
        out.append(erro("microrrede_uid_invalido", "referencia_inventario.microrrede_uid", f"{r.microrrede_uid!r}."))
    for nome in ("impressao_config", "impressao_inventario"):
        if not _HEX64.fullmatch(str(getattr(r, nome))):
            out.append(erro("impressao_invalida", f"referencia_inventario.{nome}", "SHA-256 inválido."))
    out += validar_procedencia(c.procedencia, "procedencia", sustenta_valor=False)
    if c.instante_condicoes_utc is not None:
        out += ler_instante_utc(c.instante_condicoes_utc, "instante_condicoes_utc")[1]
    vistos: set[str] = set()
    for ci in c.condicoes_iniciais:
        cam = f"condicoes_iniciais[{ci.uid}]"
        if not RE_EQUIPAMENTO.fullmatch(str(ci.uid)):
            out.append(erro("uid_invalido", cam, f"{ci.uid!r}."))
        if ci.uid in vistos:
            out.append(erro("condicao_duplicada", cam, "Mais de uma condição inicial para o mesmo UID."))
        vistos.add(ci.uid)
        if ci.disponibilidade not in DISPONIBILIDADES:
            out.append(erro("disponibilidade_invalida", cam + ".disponibilidade", f"{ci.disponibilidade!r}."))
        if ci.soc is not None:
            out += validar_parametro(ci.soc, cam + ".soc", unidade="1", dominio="fracao")
        if ci.potencia_kW is not None:
            out += validar_parametro(ci.potencia_kW, cam + ".potencia_kW", unidade="kW", dominio="nao_negativo")
        if ci.estado_discreto is not None and ci.estado_discreto not in ESTADOS_DISCRETOS:
            out.append(erro("estado_discreto_invalido", cam + ".estado_discreto", f"{ci.estado_discreto!r}."))
        for nome in ("unidades_ligadas", "tempo_no_estado_s"):
            v = getattr(ci, nome)
            if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
                out.append(erro("inteiro_invalido", f"{cam}.{nome}", f"Exigido inteiro >= 0; recebido {v!r}."))
    return RelatorioValidacao(tuple(out))


def coerencia_cenario_inventario(c: CenarioEMS, inv: InventarioMicrorrede) -> list[Constatacao]:
    """Dados inconsistentes entre microrrede e cenário (identidade, revisão, UIDs referenciados)."""
    out: list[Constatacao] = []
    r, idt = c.referencia_inventario, inv.identidade
    if r.microrrede_uid != idt.uid:
        out.append(erro("cenario_de_outra_microrrede", "referencia_inventario.microrrede_uid",
                        f"Cenário da microrrede {r.microrrede_uid!r} aplicado ao inventário de {idt.uid!r}."))
        return out
    if r.incarnacao is not None and idt.incarnacao is not None and r.incarnacao != idt.incarnacao:
        out.append(erro("incarnacao_divergente", "referencia_inventario.incarnacao",
                        "Cenário de uma incarnação anterior da microrrede (excluída e reimportada com o mesmo UID)."))
    if r.impressao_inventario != idt.impressao_inventario:
        out.append(erro("inventario_divergente", "referencia_inventario.impressao_inventario",
                        f"O cenário referencia a revisão {r.revisao_config} cujo inventário físico difere do instantâneo "
                        f"(revisão {idt.revisao_config}): atualize a referência (rebase explícito)."))
    elif r.revisao_config != idt.revisao_config:
        out.append(aviso("revisao_diferente_mesmo_inventario", "referencia_inventario.revisao_config",
                         f"Revisão {r.revisao_config} ≠ {idt.revisao_config}, com o mesmo inventário físico."))
    uids = inv.uids()
    for ci in c.condicoes_iniciais:
        d = inv.dispositivo(ci.uid)
        if d is None:
            cod = "condicao_para_dispositivo_retirado" if ci.uid in inv.retirados else "referencia_uid_inexistente"
            out.append(erro(cod, f"condicoes_iniciais[{ci.uid}]", f"UID {ci.uid} não está no inventário ativo."))
        elif not d.habilitado and ci.disponibilidade == "disponivel":
            out.append(aviso("condicao_para_dispositivo_desabilitado", f"condicoes_iniciais[{ci.uid}]",
                             "Dispositivo desabilitado no inventário: a condição não será aplicada."))
    for d in inv.dispositivos:
        if not d.habilitado or d.modelo.papel_ems == "agrupador":
            continue
        ci, herdada = condicao_efetiva(c, d)
        if ci is None:
            out.append(erro("condicao_inicial_ausente", f"condicoes_iniciais[{d.uid}]",
                            "Dispositivo habilitado sem condição inicial/disponibilidade declarada (não se parte de zero)."))
        elif herdada:
            out.append(aviso("disponibilidade_herdada_do_agrupador", f"condicoes_iniciais[{d.uid}]",
                             f"Arranjo sem condição própria: aplica-se a disponibilidade declarada para a usina {d.pai}."))
    for u in c.orfaos:
        if u in uids:
            out.append(erro("orfao_presente", f"orfaos[{u}]", "UID órfão consta no inventário ativo."))
    return out


# ------------------------------------------------------------------------------------------------ tempo
@dataclass(frozen=True)
class DefinicaoTemporal:
    malha: MalhaTemporal                           # Δ, N (controle), m (aplicação), K_M (missão), H_f
    horizonte_planejamento_min: float | None = None  # planejador de longo prazo (3C-4); reservado


def validar_definicao_temporal(dt: DefinicaoTemporal) -> list[Constatacao]:
    out = validar_malha(dt.malha)
    if dt.horizonte_planejamento_min is not None:
        out.append(pendente("planejamento_hierarquico_nao_ativo_3C0", "horizonte_planejamento_min",
                            "Horizonte de planejamento declarado: a coordenação planejador × MPC é do 3C-4."))
    return out


# ------------------------------------------------------------------------------------------------ séries
@dataclass(frozen=True)
class SerieRecurso:
    """Série associada a UM recurso (``str(UIDRecurso)``) e grandeza. ``base_potencial`` (renováveis) declara se o
    potencial é anterior à disponibilidade ou já utilizável (3A ``BASES_POTENCIAL``)."""
    uid: str
    grandeza: str
    serie: SerieTemporal
    base_potencial: str | None = None


@dataclass(frozen=True)
class ConjuntoPrevisao:
    conjunto_uid: str
    emissao_utc: str
    series: tuple[SerieRecurso, ...]
    procedencia: Procedencia | None
    previsao_perfeita: bool = False                # ORÁCULO declarado (ablação), nunca implícito
    justificativa_oraculo: str = ""

    def serie(self, uid: str, grandeza: str) -> SerieRecurso | None:
        return next((s for s in self.series if s.uid == uid and s.grandeza == grandeza), None)


@dataclass(frozen=True)
class Realizacao:
    realizacao_uid: str
    natureza: str
    series: tuple[SerieRecurso, ...]
    procedencia: Procedencia | None

    def serie(self, uid: str, grandeza: str) -> SerieRecurso | None:
        return next((s for s in self.series if s.uid == uid and s.grandeza == grandeza), None)


def _series(items: tuple[SerieRecurso, ...], nome: str) -> list[Constatacao]:
    out: list[Constatacao] = []
    chaves: set[tuple[str, str]] = set()
    for i, s in enumerate(items):
        cam = f"{nome}[{s.uid}:{s.grandeza}]"
        if (s.uid, s.grandeza) in chaves:
            out.append(erro("serie_duplicada", cam, "Mais de uma série para o mesmo recurso e grandeza."))
        chaves.add((s.uid, s.grandeza))
        if s.grandeza not in GRANDEZAS_SERIE:
            out.append(erro("grandeza_desconhecida", cam, f"{s.grandeza!r}."))
            continue
        out += validar_serie(s.serie, cam, unidade=GRANDEZAS_SERIE[s.grandeza], grandeza=s.grandeza)
    return out


def validar_previsao(p: ConjuntoPrevisao, dt: DefinicaoTemporal) -> list[Constatacao]:
    """Cada série cobre a janela de CONTROLE (N intervalos), alinhada e causal (emitida até τ_0)."""
    out = _series(p.series, "previsao")
    out += validar_procedencia(p.procedencia, "previsao.procedencia", sustenta_valor=False)
    e, c = ler_instante_utc(p.emissao_utc, "previsao.emissao_utc")
    out += c
    t0 = dt.malha.inicio()
    if e is not None and e > t0:
        out.append(erro("previsao_nao_causal", "previsao.emissao_utc", "Conjunto emitido depois do início da janela."))
    if p.previsao_perfeita and not p.justificativa_oraculo.strip():
        out.append(erro("oraculo_sem_justificativa", "previsao.justificativa_oraculo",
                        "Previsão perfeita (oráculo) exige justificativa explícita (ablação rotulada)."))
    for s in p.series:
        cam = f"previsao[{s.uid}:{s.grandeza}]"
        if s.serie.emissao_utc is None:
            out.append(erro("emissao_serie_ausente", cam, "Série de previsão sem instante de emissão."))
        else:
            es, _ = ler_instante_utc(s.serie.emissao_utc, cam + ".emissao_utc")
            if es is not None and e is not None and es > e:
                out.append(erro("serie_emitida_depois_do_conjunto", cam, "Série emitida depois do conjunto."))
        if s.grandeza in GRANDEZAS_SERIE and not any(x.severidade == "erro" for x in out if x.caminho.startswith(cam)):
            out += [x for x in alinhar_a_malha(s.serie, dt.malha, cam)[1] if x.codigo != "emissao_nao_declarada"]
    return out


def validar_realizacao(r: Realizacao, dt: DefinicaoTemporal) -> list[Constatacao]:
    """A realização cobre a MISSÃO inteira (K_M intervalos) a partir de τ_0. Não é emitida: não tem emissão."""
    out = _series(r.series, "realizacao")
    out += validar_procedencia(r.procedencia, "realizacao.procedencia", sustenta_valor=False)
    if r.natureza not in NATUREZAS_REALIZACAO:
        out.append(erro("natureza_realizacao_invalida", "realizacao.natureza", f"{r.natureza!r}."))
    m = dt.malha
    missao = MalhaTemporal(m.inicio_utc, m.delta_min, m.intervalos_missao, 1, m.intervalos_missao, None)
    for s in r.series:
        cam = f"realizacao[{s.uid}:{s.grandeza}]"
        if s.serie.emissao_utc is not None:
            out.append(erro("realizacao_com_emissao", cam, "Realização não é previsão: não tem instante de emissão."))
        if s.grandeza in GRANDEZAS_SERIE and not any(x.severidade == "erro" for x in out if x.caminho.startswith(cam)):
            out += [x for x in alinhar_a_malha(s.serie, missao, cam)[1] if x.codigo != "emissao_nao_declarada"]
    return out


def validar_separacao(p: ConjuntoPrevisao, r: Realizacao, dt: DefinicaoTemporal) -> list[Constatacao]:
    """Previsão ≠ realização: mesma série (valores da janela) sem oráculo declarado ⇒ erro; oráculo ⇒ aviso."""
    out: list[Constatacao] = []
    janela = dt.malha
    for s in p.series:
        rs = r.serie(s.uid, s.grandeza)
        if rs is None:
            continue
        vp, _ = alinhar_a_malha(s.serie, janela, "p")
        vr, _ = alinhar_a_malha(SerieTemporal(rs.serie.grandeza, rs.serie.unidade, rs.serie.semantica,
                                              rs.serie.inicio_utc, rs.serie.passo_s, rs.serie.valores,
                                              rs.serie.procedencia, rs.serie.fronteira, emissao_utc=janela.inicio_utc),
                                janela, "r")
        if vp is not None and vr is not None and vp == vr:
            if p.previsao_perfeita:
                out.append(aviso("previsao_perfeita_declarada", f"previsao[{s.uid}:{s.grandeza}]",
                                 "Oráculo declarado: resultados NÃO medem desempenho com erro de predição."))
            else:
                out.append(erro("previsao_igual_realizacao_nao_declarada", f"previsao[{s.uid}:{s.grandeza}]",
                                "Previsão idêntica à realização na janela sem declaração de oráculo: previsão e "
                                "realização confundidas."))
        if s.serie is rs.serie:
            out.append(erro("mesmo_objeto_previsao_realizacao", f"previsao[{s.uid}:{s.grandeza}]",
                            "O mesmo objeto de série foi usado como previsão e como realização."))
    return out


def hash_cenario(c: CenarioEMS) -> str:
    return sha256(c)


def hash_previsao(p: ConjuntoPrevisao) -> str:
    return sha256(p)


def hash_realizacao(r: Realizacao) -> str:
    return sha256(r)


__all__ = ["CenarioEMS", "CondicaoInicialDispositivo", "ConjuntoPrevisao", "DISPONIBILIDADES", "DefinicaoTemporal",
           "ESTADOS_DISCRETOS", "GRANDEZAS_SERIE", "NATUREZAS_REALIZACAO", "Realizacao", "ReferenciaInventario",
           "SerieRecurso", "coerencia_cenario_inventario", "condicao_efetiva", "hash_cenario", "hash_previsao", "hash_realizacao",
           "validar_cenario", "validar_definicao_temporal", "validar_previsao", "validar_realizacao", "validar_separacao"]
