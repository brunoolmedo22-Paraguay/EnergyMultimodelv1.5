"""Contratos de cenário, condições iniciais, definição temporal e PREVISÃO × REALIZAÇÃO (3C-0 §3.3).

Separação explícita (cada uma é um tipo próprio; nenhuma é derivada implicitamente de outra):

* **Configuração da microrrede** — ``inventario.InventarioMicrorrede`` (física permanente; nunca editada aqui);
* **Cenário** — ``CenarioEMS``: condições experimentais referenciando UMA revisão do inventário (identidade +
  impressões digitais), disponibilidade por dispositivo e condições iniciais na fronteira k = 0;
* **Previsões disponíveis ao controlador** — ``ConjuntoPrevisao``: séries EMITIDAS num instante (causalidade);
* **Condições reais ou simuladas do entorno** — ``Realizacao``: o que de fato ocorre (medido/simulado/sintético).
  Nunca é entregue ao controlador. Dois modos (H-04): ``completa_offline`` (simulação: cobre a missão inteira) e
  ``incremental_online`` (operação: só os intervalos já observados até ``observado_ate_utc``; nada além dele);
* **Separação previsão × realização (H-01)** — classificada POR SÉRIE: independente; coincidente sem evidência de
  fuga (advertência); oráculo declarado (``previsao_perfeita=True`` + justificativa; advertência); procedência
  compartilhada suspeita (advertência); e, BLOQUEANTES só com evidência: previsão derivada do conteúdo da
  realização (hash), o mesmo objeto de série, ou oráculo declarado que difere da realização. Igualdade numérica
  sozinha não é fuga de informação. A causalidade por instante de emissão continua bloqueante (``validar_previsao``);
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
MODOS_REALIZACAO = {
    "completa_offline": "Realização completa da missão (simulação offline; disponível só ao executor/avaliação)",
    "incremental_online": "Observações acumuladas até ``observado_ate_utc`` (operação online; o futuro ainda não existe)",
}
CATEGORIAS_SEPARACAO = {
    "independente": "Previsão causal com valores diferentes da realização em ao menos um intervalo comparado",
    "coincidente_sem_evidencia": "Valores iguais nos intervalos comparados, sem evidência de fuga (advertência)",
    "procedencia_compartilhada": "Mesma procedência declarada para previsão e realização (suspeita; advertência)",
    "oraculo_declarado": "Previsão perfeita declarada (ablação rotulada; advertência)",
    "derivada_da_realizacao": "Procedência da previsão aponta o SHA-256 do conteúdo realizado (fuga; bloqueante)",
    "mesmo_objeto": "O mesmo objeto de série usado como previsão e como realização (fuga; bloqueante)",
    "oraculo_inconsistente": "Declarada perfeita, mas difere da realização (rótulo falso; bloqueante)",
    "sem_realizacao": "Sem série realizada correspondente para comparar",
}


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
    modo: str = "completa_offline"                 # MODOS_REALIZACAO (H-04)
    observado_ate_utc: str | None = None           # obrigatório (e só) no modo incremental_online: fronteira τ_k

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


def _malha_missao(dt: DefinicaoTemporal, n: int | None = None) -> MalhaTemporal:
    m = dt.malha
    k = m.intervalos_missao if n is None else n
    return MalhaTemporal(m.inicio_utc, m.delta_min, k, 1, k, None)


def intervalos_observados(r: Realizacao, dt: DefinicaoTemporal) -> tuple[int | None, list[Constatacao]]:
    """Número de intervalos da missão já realizados: K_M (offline) ou k tal que τ_k = ``observado_ate_utc`` (online).
    O instante observado deve cair EXATAMENTE numa fronteira da malha, entre τ_0 e o fim da missão."""
    m = dt.malha
    if r.modo == "completa_offline":
        if r.observado_ate_utc is not None:
            return None, [erro("observado_ate_em_modo_offline", "realizacao.observado_ate_utc",
                               "Realização completa offline não declara instante de observação.")]
        return m.intervalos_missao, []
    if r.modo != "incremental_online":
        return None, [erro("modo_realizacao_invalido", "realizacao.modo", f"{r.modo!r}.")]
    t, c = ler_instante_utc(r.observado_ate_utc, "realizacao.observado_ate_utc")
    if c:
        return None, c
    d = (t - m.inicio()).total_seconds()
    if d < 0 or d % m.delta_s:
        return None, [erro("observado_ate_fora_da_malha", "realizacao.observado_ate_utc",
                           "O instante observado deve ser uma fronteira τ_k = τ_0 + kΔ (k ≥ 0).")]
    k = int(d // m.delta_s)
    if k > m.intervalos_missao:
        return None, [erro("observado_ate_alem_da_missao", "realizacao.observado_ate_utc",
                           f"k = {k} > K_M = {m.intervalos_missao}.")]
    return k, []


def validar_realizacao(r: Realizacao, dt: DefinicaoTemporal) -> list[Constatacao]:
    """Offline: a realização cobre a MISSÃO inteira (K_M intervalos) a partir de τ_0. Online (H-04): cobre EXATAMENTE
    os k intervalos já observados [τ_0, τ_k) — cobertura verificada só até τ_k, e qualquer valor depois de τ_k é
    informação futura (erro), nunca completada nem extrapolada. Não é emitida: não tem instante de emissão."""
    out = _series(r.series, "realizacao")
    out += validar_procedencia(r.procedencia, "realizacao.procedencia", sustenta_valor=False)
    if r.natureza not in NATUREZAS_REALIZACAO:
        out.append(erro("natureza_realizacao_invalida", "realizacao.natureza", f"{r.natureza!r}."))
    k, c = intervalos_observados(r, dt)
    out += c
    if k is None:
        return out
    janela = _malha_missao(dt, k) if k > 0 else None
    for s in r.series:
        cam = f"realizacao[{s.uid}:{s.grandeza}]"
        if s.serie.emissao_utc is not None:
            out.append(erro("realizacao_com_emissao", cam, "Realização não é previsão: não tem instante de emissão."))
        if s.grandeza not in GRANDEZAS_SERIE or any(x.severidade == "erro" for x in out if x.caminho.startswith(cam)):
            continue
        if janela is not None:
            out += [x for x in alinhar_a_malha(s.serie, janela, cam)[1] if x.codigo != "emissao_nao_declarada"]
        if r.modo == "incremental_online":
            ts, _ = ler_instante_utc(s.serie.inicio_utc, cam)
            fim = ts.timestamp() + s.serie.passo_s * len(s.serie.valores) if ts is not None else None
            lim = ler_instante_utc(r.observado_ate_utc, cam)[0]
            if fim is not None and lim is not None and fim > lim.timestamp():
                out.append(erro("realizacao_alem_do_observado", cam,
                                f"Valores depois de observado_ate_utc ({r.observado_ate_utc}): numa observação online "
                                "isso é informação futura (dados offline usados como online?)."))
    return out


@dataclass(frozen=True)
class SeparacaoSerie:
    uid: str
    grandeza: str
    categoria: str                                  # chave de CATEGORIAS_SEPARACAO (a mais grave)
    intervalos_comparados: int
    intervalos_iguais: int
    evidencias: tuple[str, ...]


def _valores_realizados_na_janela(serie: SerieTemporal, janela: MalhaTemporal) -> dict[int, float]:
    """Valores realizados disponíveis para os intervalos da janela (alinhados, mesmo passo); ausentes ficam fora."""
    ts, c = ler_instante_utc(serie.inicio_utc, "r")
    if c or serie.passo_s != janela.delta_s:
        return {}
    d = (janela.inicio() - ts).total_seconds()
    if d % serie.passo_s:
        return {}
    i0 = int(d // serie.passo_s)
    return {t: float(serie.valores[i0 + t]) for t in range(janela.N) if 0 <= i0 + t < len(serie.valores)}


def _mesma_procedencia(a: Procedencia | None, b: Procedencia | None) -> bool:
    return a is not None and b is not None and (a.tipo, a.fonte, a.referencia, a.sha256) == (b.tipo, b.fonte,
                                                                                          b.referencia, b.sha256)


def classificar_separacao(p: ConjuntoPrevisao, r: Realizacao, dt: DefinicaoTemporal) -> tuple[SeparacaoSerie, ...]:
    janela = dt.malha
    hashes_real = {sha256(x.serie) for x in r.series} | {sha256(x) for x in r.series} | {sha256(r)}
    out: list[SeparacaoSerie] = []
    for s in p.series:
        rs = r.serie(s.uid, s.grandeza)
        if rs is None:
            out.append(SeparacaoSerie(s.uid, s.grandeza, "sem_realizacao", 0, 0, ()))
            continue
        ev: list[str] = []
        vp, _ = alinhar_a_malha(s.serie, janela, "p")
        vr = _valores_realizados_na_janela(rs.serie, janela)
        comp = [t for t in vr if vp is not None]
        iguais = [t for t in comp if vp[t] == vr[t]]
        if s.serie is rs.serie:
            ev.append("mesmo_objeto")
        sp = s.serie.procedencia
        if sp is not None and sp.sha256 is not None and sp.sha256 in hashes_real:
            ev.append("derivada_da_realizacao")
        if _mesma_procedencia(sp, rs.serie.procedencia):
            ev.append("procedencia_compartilhada")
        coincide = bool(comp) and len(iguais) == len(comp)
        if p.previsao_perfeita:
            cat = "oraculo_declarado" if coincide or not comp else "oraculo_inconsistente"
        elif "mesmo_objeto" in ev:
            cat = "mesmo_objeto"
        elif "derivada_da_realizacao" in ev:
            cat = "derivada_da_realizacao"
        elif "procedencia_compartilhada" in ev:
            cat = "procedencia_compartilhada"
        elif coincide:
            cat = "coincidente_sem_evidencia"
        else:
            cat = "independente"
        out.append(SeparacaoSerie(s.uid, s.grandeza, cat, len(comp), len(iguais), tuple(ev)))
    return tuple(out)


_SEV_SEPARACAO = {"coincidente_sem_evidencia": "aviso", "procedencia_compartilhada": "aviso", "oraculo_declarado": "aviso",
                  "derivada_da_realizacao": "erro", "mesmo_objeto": "erro", "oraculo_inconsistente": "erro"}
_COD_SEPARACAO = {"coincidente_sem_evidencia": "previsao_coincide_com_realizacao",
                  "procedencia_compartilhada": "procedencia_compartilhada_suspeita",
                  "oraculo_declarado": "previsao_perfeita_declarada",
                  "derivada_da_realizacao": "previsao_derivada_da_realizacao",
                  "mesmo_objeto": "mesmo_objeto_previsao_realizacao",
                  "oraculo_inconsistente": "oraculo_diferente_da_realizacao"}


def validar_separacao(p: ConjuntoPrevisao, r: Realizacao, dt: DefinicaoTemporal) -> list[Constatacao]:
    """Constatações da separação (ver ``CATEGORIAS_SEPARACAO``): só evidência de fuga ou rótulo falso bloqueia.
    Uma coincidência numérica sem evidência é advertência (pode haver previsões independentes idênticas, p. ex.
    séries constantes). Procedência compartilhada é advertência adicional mesmo quando os valores coincidem."""
    out: list[Constatacao] = []
    for c in classificar_separacao(p, r, dt):
        cam = f"previsao[{c.uid}:{c.grandeza}]"
        msg = (f"{CATEGORIAS_SEPARACAO[c.categoria]} — {c.intervalos_iguais}/{c.intervalos_comparados} intervalo(s) "
               f"iguais; evidências: {list(c.evidencias) or 'nenhuma'}.")
        if c.categoria in _SEV_SEPARACAO:
            out.append((erro if _SEV_SEPARACAO[c.categoria] == "erro" else aviso)(_COD_SEPARACAO[c.categoria], cam, msg))
        if c.categoria == "procedencia_compartilhada" and c.intervalos_comparados and \
                c.intervalos_iguais == c.intervalos_comparados:
            out.append(aviso("previsao_coincide_com_realizacao", cam, msg))
    return out


def hash_cenario(c: CenarioEMS) -> str:
    return sha256(c)


def hash_previsao(p: ConjuntoPrevisao) -> str:
    return sha256(p)


def hash_realizacao(r: Realizacao) -> str:
    return sha256(r)


__all__ = ["CenarioEMS", "CondicaoInicialDispositivo", "ConjuntoPrevisao", "DISPONIBILIDADES", "DefinicaoTemporal",
           "CATEGORIAS_SEPARACAO", "ESTADOS_DISCRETOS", "GRANDEZAS_SERIE", "MODOS_REALIZACAO", "NATUREZAS_REALIZACAO",
           "Realizacao", "ReferenciaInventario", "SeparacaoSerie", "classificar_separacao", "intervalos_observados",
           "SerieRecurso", "coerencia_cenario_inventario", "condicao_efetiva", "hash_cenario", "hash_previsao", "hash_realizacao",
           "validar_cenario", "validar_definicao_temporal", "validar_previsao", "validar_realizacao", "validar_separacao"]
