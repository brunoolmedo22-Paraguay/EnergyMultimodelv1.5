"""Projeção inventário + cenário + previsão + políticas DECLARADAS → ``EntradaModeloEMS`` (contrato 3A/3B-P).

É o ponto em que a ponte encontra o núcleo científico: o resultado é validado por ``contracts.validar_entrada``
SEM nenhuma relaxação. Regras:

* só parâmetros classificados como disponíveis/deriváveis (ou sintéticos em ensaio) viram ``Parametro``; a cadeia
  bruto → canônico é preservada (``valor_bruto``/``unidade_bruta``/``transformacoes``);
* qualquer requisito bloqueante ⇒ NENHUMA entrada é construída (``entrada=None``) e as constatações explicam o que falta;
* políticas (serviço, terminal, objetivo, classes de demanda, variante de commitment) NUNCA têm valor padrão: são
  argumentos obrigatórios declarados por quem executa (decisões D01/D02 continuam do responsável);
* disponibilidade estática do cenário vira série constante com a transformação registrada na procedência;
* indisponível ⇒ o recurso entra com ``a = 0`` (B01: indisponibilidade não é curtailment), inventário intacto;
* estado por UNIDADE de geradores com ``quantidade > 1`` não é inventado: só "todas OFF" é representável sem
  declaração por unidade; qualquer outra combinação é ``pendente``.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from .. import ESQUEMA_VERSAO, MOTOR_ID
from ..contracts import (CONVENCAO_POTENCIA, ClasseDemanda, Disponibilidade, EntradaModeloEMS, EspecBateria, EspecGerador,
                         EstadoBateria, EstadoGerador, FronteiraBarramento, PoliticaObjetivo, PoliticaServico,
                         PoliticaTerminal, PotencialRenovavel, UIDRecurso, validar_entrada)
from ..diagnostics import Constatacao, aviso, erro, pendente
from ..parameters import Parametro
from ..provenance import Procedencia
from ..series import SerieTemporal
from .cenario import (CenarioEMS, ConjuntoPrevisao, DefinicaoTemporal, coerencia_cenario_inventario, condicao_efetiva,
                      hash_cenario, hash_previsao, validar_cenario, validar_definicao_temporal, validar_previsao)
from .inventario import InventarioMicrorrede, hash_inventario, recursos_ems, validar_inventario
from .requisitos import MatrizParametros, constatacoes as constatacoes_matriz, hash_matriz, matriz_parametros

TOPOLOGIAS_INVENTARIO = {"isolada": "isolada", "conectada": "conectada", "conectada_ilhamento": "conectada"}


@dataclass(frozen=True)
class ClasseDemandaDeclarada:
    uid: str                                   # UID da classe (o inventário SEEDS2 não tem UID de demanda)
    nome: str
    criticidade: str
    custo_energia_nao_suprida: Parametro | None = None


@dataclass(frozen=True)
class PoliticasDeclaradas:
    versao_formulacao: str
    servico: PoliticaServico
    terminal: PoliticaTerminal
    objetivo: PoliticaObjetivo
    demandas: tuple[ClasseDemandaDeclarada, ...]
    variante_commitment: str | None            # obrigatória quando houver gerador
    procedencia: Procedencia | None            # quem declarou as políticas e a montagem


@dataclass(frozen=True)
class ResultadoProjecao:
    entrada: EntradaModeloEMS | None
    constatacoes: tuple[Constatacao, ...]
    matriz: MatrizParametros | None
    recursos: dict[str, str] = field(default_factory=dict)      # str(UIDRecurso) → UID do dispositivo
    hashes: dict[str, str] = field(default_factory=dict)

    @property
    def aceito(self) -> bool:
        return self.entrada is not None and not any(c.severidade in ("erro", "pendente") for c in self.constatacoes)


def _par(m: MatrizParametros, uid: str, simbolo: str) -> Parametro | None:
    c = m.de(uid, simbolo)
    if c is None or c.numero is None or c.bloqueia:
        return None
    return Parametro(c.numero, c.unidade, c.procedencia, c.numero_bruto, c.unidade_bruta, c.transformacoes)


def _texto(m: MatrizParametros, uid: str, simbolo: str) -> str | None:
    c = m.de(uid, simbolo)
    return None if c is None or c.bloqueia else c.texto


def _disponibilidade(uid_rec: str, disp_inv, cen: CenarioEMS, prev: ConjuntoPrevisao,
                     dt: DefinicaoTemporal) -> tuple[Disponibilidade | None, list[Constatacao]]:
    uid_disp = disp_inv.uid
    s = prev.serie(uid_rec, "disponibilidade") or prev.serie(uid_disp, "disponibilidade")
    if s is not None:
        return Disponibilidade(s.serie), []
    ci, herdada = condicao_efetiva(cen, disp_inv)
    if ci is None:
        return None, [erro("condicao_inicial_ausente", f"condicoes_iniciais[{uid_disp}]", "Sem disponibilidade declarada.")]
    a = 1.0 if ci.disponibilidade == "disponivel" else 0.0
    base = cen.procedencia or Procedencia("nao_declarado", "cenário")
    proc = replace(base, referencia=f"{base.referencia} · condicoes_iniciais[{uid_disp}].disponibilidade".strip(" ·"),
                   observacoes=f"Série constante a = {a:g} derivada da disponibilidade ESTÁTICA do cenário "
                               f"({ci.disponibilidade}{', herdada da usina ' + str(disp_inv.pai) if herdada else ''})"
                               " — transformação da ponte 3C-0.")
    m = dt.malha
    serie = SerieTemporal("disponibilidade", "1", "media_intervalo", m.inicio_utc, m.delta_s, tuple([a] * m.N), proc,
                          emissao_utc=prev.emissao_utc)
    return Disponibilidade(serie), []


def _estado_gerador(uid_rec: UIDRecurso, q: int, ci) -> tuple[EstadoGerador | None, list[Constatacao]]:
    cam = f"condicoes_iniciais[{uid_rec.equipamento}]"
    if ci is None or ci.estado_discreto is None:
        return None, [erro("estado_inicial_ausente", cam + ".estado_discreto",
                           "Estado ON/OFF anterior não declarado: não é inferido da potência.")]
    if ci.estado_discreto == "em_partida":
        return None, [pendente("estado_em_partida_nao_representavel", cam,
                               "'Em partida' não tem física de partida representada (multimodo/M20: 3C+).")]
    ligado = ci.estado_discreto == "em_operacao"
    if q > 1:
        k = ci.unidades_ligadas
        if k is None:
            return None, [erro("unidades_ligadas_ausente", cam + ".unidades_ligadas",
                               f"Registro com {q} unidades: declarar quantas estão em operação.")]
        if k == 0 and not ligado:
            if ci.potencia_kW is None:
                return None, [erro("potencia_inicial_ausente", cam + ".potencia_kW", "Potência anterior não declarada.")]
            if ci.potencia_kW.valor != 0.0:
                return None, [erro("off_com_potencia", cam, "Todas as unidades OFF com potência anterior ≠ 0.")]
            return EstadoGerador(uid_rec, False, ci.potencia_kW), []
        return None, [pendente("estado_por_unidade_nao_declarado", cam,
                               f"{k} de {q} unidades em operação: o estado e a potência POR UNIDADE não são declarados "
                               "no cenário (atribuir unidades ou dividir a potência seria inventar).")]
    if ci.potencia_kW is None:
        return None, [erro("potencia_inicial_ausente", cam + ".potencia_kW", "Potência anterior não declarada.")]
    return EstadoGerador(uid_rec, ligado, ci.potencia_kW), []


def montar_entrada(inv: InventarioMicrorrede, cen: CenarioEMS, prev: ConjuntoPrevisao, dt: DefinicaoTemporal,
                   pol: PoliticasDeclaradas, *, contexto: str = "operacional") -> ResultadoProjecao:
    c: list[Constatacao] = []
    c += list(validar_inventario(inv).constatacoes)
    c += list(validar_cenario(cen).constatacoes)
    c += coerencia_cenario_inventario(cen, inv)
    c += validar_definicao_temporal(dt)
    if any(x.severidade == "erro" for x in c):
        return ResultadoProjecao(None, tuple(c), None)
    c += validar_previsao(prev, dt)
    termos = frozenset(pol.objetivo.termos)
    mat = matriz_parametros(inv, termos=termos, contexto=contexto)
    c += constatacoes_matriz(mat)
    topo = TOPOLOGIAS_INVENTARIO.get(inv.modo_operacao or "")
    if topo is None:
        c.append(erro("topologia_nao_declarada", "inventario.modo_operacao",
                      f"Modo de operação {inv.modo_operacao!r}: declarar isolada/conectada (nenhuma topologia é presumida)."))
    if not pol.demandas:
        c.append(erro("classes_demanda_nao_declaradas", "politicas.demandas",
                      "Nenhuma classe de demanda declarada (criticidade é decisão do responsável — D01)."))
    recursos: dict[str, str] = {}
    demandas, renov, bats, ebats, gers, egers = [], [], [], [], [], []
    for d in inv.dispositivos:
        if not d.habilitado or d.modelo.papel_ems == "agrupador":
            continue
        ci = cen.condicao(d.uid)
        for r in recursos_ems(d):
            k = str(r)
            recursos[k] = d.uid
            disp, cd = _disponibilidade(k, d, cen, prev, dt)
            c += cd
            if disp is None:
                continue
            if d.modelo.papel_ems == "renovavel":
                s = prev.serie(k, "potencia")
                if s is None:
                    c.append(pendente("potencial_renovavel_sem_serie", f"previsao[{k}:potencia]",
                                      "Sem série de potencial no barramento: derivá-la exige o modelo físico (models/) "
                                      "aplicado ao clima previsto — adaptador não implementado no 3C-0."))
                    continue
                if s.base_potencial is None:
                    c.append(erro("base_potencial_nao_declarada", f"previsao[{k}:potencia].base_potencial",
                                  "Declarar se o potencial é anterior à disponibilidade ou já utilizável."))
                    continue
                renov.append(PotencialRenovavel(r, d.modelo.tecnologia_ems, s.serie, s.base_potencial, disp,
                                                _par(mat, d.uid, "c_curt")))
            elif d.modelo.papel_ems == "armazenamento":
                g = {s: _par(mat, d.uid, s) for s in ("C_b", "s_min", "s_max", "eta_c", "eta_d", "Pc_max", "Pd_max")}
                hip = _texto(mat, d.uid, "hipotese_autodescarga")
                if any(v is None for v in g.values()) or hip is None:
                    continue                                   # já constatado pela matriz
                bats.append(EspecBateria(r, g["C_b"], g["s_min"], g["s_max"], g["eta_c"], g["eta_d"], g["Pc_max"],
                                         g["Pd_max"], hip, disp, custo_throughput=_par(mat, d.uid, "c_thr")))
                if ci is None or ci.soc is None:
                    c.append(erro("soc_inicial_ausente", f"condicoes_iniciais[{d.uid}].soc", "SOC inicial não declarado."))
                    continue
                e0 = ci.soc.valor * g["C_b"].valor
                p = ci.soc.procedencia
                proc_e0 = replace(p, observacoes=(f"e0 = SOC0 × C_b = {ci.soc.valor!r} × {g['C_b'].valor!r} kWh "
                                                  f"(C_b: {g['C_b'].procedencia.referencia if g['C_b'].procedencia else '?'})"
                                                  )) if p is not None else None
                ebats.append(EstadoBateria(r, Parametro(e0, "kWh", proc_e0), ci.soc))
            elif d.modelo.papel_ems == "gerador":
                pmin, pmax = _par(mat, d.uid, "P_min"), _par(mat, d.uid, "P_max")
                if d.tipo == "termica" and _texto(mat, d.uid, "dinamica_termica") not in (None, "local_generator"):
                    c.append(pendente("dinamica_termica_nao_suportada", f"dispositivos[{d.uid}].dinamica_termica",
                                      "Só a pequena unidade geradora é representável."))
                    continue
                if pmin is None or pmax is None:
                    continue
                if pol.variante_commitment is None:
                    c.append(erro("variante_commitment_nao_declarada", "politicas.variante_commitment",
                                  "Gerador presente: declarar a variante de commitment (sem padrão)."))
                    continue
                gers.append(EspecGerador(r, d.modelo.tecnologia_ems, pmin, pmax, disp, pol.variante_commitment))
                est, ce = _estado_gerador(r, d.quantidade or 1, ci)
                c += ce
                if est is not None:
                    egers.append(est)
    for cd in pol.demandas:
        s = prev.serie(cd.uid, "potencia")
        if s is None:
            c.append(erro("serie_demanda_ausente", f"previsao[{cd.uid}:potencia]", "Classe de demanda sem série prevista."))
            continue
        chi = prev.serie(cd.uid, "fracao_interrompivel")
        demandas.append(ClasseDemanda(UIDRecurso(cd.uid), cd.nome, cd.criticidade, s.serie,
                                      chi.serie if chi else None, cd.custo_energia_nao_suprida))
    hashes = {"inventario": hash_inventario(inv), "cenario": hash_cenario(cen), "previsao": hash_previsao(prev),
              "matriz_parametros": hash_matriz(mat)}
    if any(x.severidade in ("erro", "pendente") for x in c):
        return ResultadoProjecao(None, tuple(c), mat, recursos, hashes)
    entrada = EntradaModeloEMS(
        ESQUEMA_VERSAO, MOTOR_ID, pol.versao_formulacao, inv.identidade.uid, cen.cenario_uid, dt.malha,
        FronteiraBarramento("barramento_equivalente_unico", topo, CONVENCAO_POTENCIA, inv.procedencia
                            if inv.procedencia and inv.procedencia.tipo != "nao_declarado" else pol.procedencia),
        tuple(demandas), tuple(renov), tuple(bats), tuple(ebats), tuple(gers), tuple(egers), pol.servico, pol.terminal,
        pol.objetivo, pol.procedencia, dict(hashes))
    rel = validar_entrada(entrada)
    c += list(rel.constatacoes)
    if not rel.aceito:
        return ResultadoProjecao(None, tuple(c), mat, recursos, hashes)
    if contexto == "ensaio":
        c.append(aviso("entrada_de_ensaio", "contexto", "Entrada montada em contexto de ENSAIO: não é estudo físico."))
    return ResultadoProjecao(entrada, tuple(c), mat, recursos, hashes)


__all__ = ["ClasseDemandaDeclarada", "PoliticasDeclaradas", "ResultadoProjecao", "TOPOLOGIAS_INVENTARIO", "montar_entrada"]
