"""Preflight científico da ponte (3C-0 §3.5) — verificação ANTES de qualquer futura execução do EMS V2.

Agrega, sem relaxar nenhuma regra, as verificações dos contratos (inventário, cenário, coerência cenário ×
microrrede, definição temporal, previsões, realização, separação previsão × realização, matriz de parâmetros,
projeção para a entrada canônica 3A com ``validar_entrada``) e acrescenta:

* referências UID inexistentes (séries, compromisso) e recursos indisponíveis comandados;
* restrições/termos incompatíveis com os equipamentos disponíveis;
* dados SINTÉTICOS fora de contexto de ensaio (erro em ``operacional``; advertência rotulada em ``ensaio``).

Resultado ``RelatorioPreflightEMS``: itens estruturados com área, código, caminho, mensagem e severidade
``bloqueante`` (erro/pendente), ``advertencia`` (aviso) ou ``aceitavel`` (verificação realizada sem constatação).
Determinístico e com SHA-256. Nenhum valor de respaldo é usado para "passar".

**Finalidade (H-02):** ``diagnostico`` × ``otimizacao`` são distintos. ``diagnostico`` avalia os dados disponíveis
SEM exigir (nem inventar) políticas: o relatório pode não ter bloqueios de dados, mas ``apto_para_otimizacao`` é
sempre falso. ``otimizacao`` (padrão) só declara aptidão para o solver se: políticas fornecidas, previsão fornecida,
projeção EXISTENTE e ACEITA (``validar_entrada``), formulação com solver (``v1.1-3B-P``) e pré-verificação do perfil
3B-P (``ems_v2.milp.config.preflight_3bp``: compromisso fixo de cada gerador) sem bloqueios.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..diagnostics import Constatacao, aviso, erro
from ..provenance import Procedencia
from .canonico import sha256
from .cenario import (CenarioEMS, ConjuntoPrevisao, DefinicaoTemporal, Realizacao, coerencia_cenario_inventario,
                      intervalos_observados,
                      validar_cenario, validar_definicao_temporal, validar_previsao, validar_realizacao,
                      validar_separacao)
from .inventario import InventarioMicrorrede, recursos_ems, validar_inventario
from .projecao import PoliticasDeclaradas, ResultadoProjecao, montar_entrada
from .requisitos import CONTEXTOS, constatacoes as constatacoes_matriz, matriz_parametros

SEVERIDADES = {"bloqueante": "Impede a execução", "advertencia": "Registrada; não impede",
               "aceitavel": "Verificação realizada sem constatação"}
FINALIDADES = {"diagnostico": "Diagnóstico dos dados disponíveis (parcial; NUNCA autoriza otimizar)",
               "otimizacao": "Preparação para o solver (exige políticas, projeção aceita e perfil 3B-P)"}
AREAS = {"inventario": "Inventário da microrrede", "parametros": "Parâmetros obrigatórios",
         "cenario": "Cenário e coerência com a microrrede", "tempo": "Malha temporal N/N+1 e horizontes",
         "previsoes": "Previsões disponíveis ao controlador", "realizacao": "Realização do entorno",
         "separacao": "Separação previsão × realização", "referencias": "Referências UID",
         "restricoes": "Restrições × equipamentos disponíveis", "sinteticos": "Dados sintéticos × contexto",
         "contrato": "Entrada canônica 3A/3B-P (validar_entrada)", "politicas": "Políticas declaradas",
         "solver": "Preparação para o solver (perfil 3B-P)"}
_NIVEL = {"erro": "bloqueante", "pendente": "bloqueante", "aviso": "advertencia"}
TERMO_RECURSO = {"throughput_bess": "armazenamento", "combustivel_h2": "pemfc", "curtailment_operacional": "renovavel",
                 "geracao_termica": "termica"}


@dataclass(frozen=True)
class ItemPreflight:
    area: str
    codigo: str
    caminho: str
    mensagem: str
    severidade: str
    nivel_origem: str               # erro | pendente | aviso | ok


@dataclass(frozen=True)
class RelatorioPreflightEMS:
    microrrede_uid: str
    cenario_uid: str
    contexto: str
    finalidade: str
    itens: tuple[ItemPreflight, ...]

    @property
    def aceito(self) -> bool:
        """Sem itens bloqueantes PARA A FINALIDADE pedida (em diagnóstico: só os dados avaliados)."""
        return not any(i.severidade == "bloqueante" for i in self.itens)

    @property
    def apto_para_otimizacao(self) -> bool:
        """Único veredito que autoriza entregar a entrada ao solver (H-02)."""
        return self.finalidade == "otimizacao" and self.aceito

    def codigos(self, severidade: str | None = None) -> set[str]:
        return {i.codigo for i in self.itens if severidade is None or i.severidade == severidade}

    def por_area(self, area: str) -> tuple[ItemPreflight, ...]:
        return tuple(i for i in self.itens if i.area == area)

    def texto(self) -> str:
        veredito = ("APTO PARA OTIMIZAÇÃO" if self.apto_para_otimizacao else
                    "DIAGNÓSTICO PARCIAL — não autoriza otimização" if self.finalidade == "diagnostico" and self.aceito
                    else "BLOQUEADO")
        linhas = [f"Preflight EMS V2 (3C-0) — microrrede {self.microrrede_uid} · cenário {self.cenario_uid} · "
                  f"contexto {self.contexto} · finalidade {self.finalidade}: {veredito}"]
        for sev in ("bloqueante", "advertencia", "aceitavel"):
            itens = [i for i in self.itens if i.severidade == sev]
            if itens:
                linhas.append(f"[{sev.upper()}] {len(itens)}")
                linhas += [f"  - {AREAS[i.area]} · {i.codigo} · {i.caminho}: {i.mensagem}" for i in itens]
        return "\n".join(linhas)


def hash_preflight(r: RelatorioPreflightEMS) -> str:
    return sha256(r)


def _procs_sinteticas(inv, cen, prev, real, pol) -> list[str]:
    achados: list[str] = []

    def ver(p: Procedencia | None, onde: str) -> None:
        if p is not None and p.tipo == "sintetico":
            achados.append(onde)
    ver(inv.procedencia, "inventario.procedencia")
    ver(cen.procedencia, "cenario.procedencia")
    for ci in cen.condicoes_iniciais:
        for nome in ("soc", "potencia_kW"):
            par = getattr(ci, nome)
            ver(par.procedencia if par is not None else None, f"cenario.condicoes_iniciais[{ci.uid}].{nome}")
    if prev is not None:
        ver(prev.procedencia, "previsao.procedencia")
        for s in prev.series:
            ver(s.serie.procedencia, f"previsao[{s.uid}:{s.grandeza}]")
    if real is not None:
        if real.natureza == "sintetica":
            achados.append("realizacao.natureza")
        ver(real.procedencia, "realizacao.procedencia")
        for s in real.series:
            ver(s.serie.procedencia, f"realizacao[{s.uid}:{s.grandeza}]")
    if pol is not None:
        ver(pol.procedencia, "politicas.procedencia")
    return achados


def preflight_ems_v2(inv: InventarioMicrorrede, cen: CenarioEMS, dt: DefinicaoTemporal,
                     prev: ConjuntoPrevisao | None = None, real: Realizacao | None = None,
                     pol: PoliticasDeclaradas | None = None, *, contexto: str = "operacional",
                     compromisso: dict | None = None, finalidade: str = "otimizacao",
                     commitment_3c1=None, curvas_h2: dict | None = None, massas_h2_eventos: dict | None = None
                     ) -> tuple[RelatorioPreflightEMS, ResultadoProjecao | None]:
    """``commitment_3c1`` (3C-1, aditivo): ``ponte.compromisso.DeclaracaoCommitment3C1``. ``None`` = comportamento
    3C-0 INALTERADO. Com a declaração, a projeção é a do perfil ``v1.1-3C-1`` (requisitos M09–M12 bloqueantes,
    estado por unidade), ``compromisso`` é o compromisso PARCIAL (0/1/None) e a área "solver" aplica
    ``compromisso.preflight.preflight_3c1``; o segundo valor devolvido é ``ResultadoProjecao3C1``."""
    if contexto not in CONTEXTOS:
        raise ValueError(f"Contexto desconhecido: {contexto!r}")
    if finalidade not in FINALIDADES:
        raise ValueError(f"Finalidade desconhecida: {finalidade!r}")
    itens: list[ItemPreflight] = []
    vistos: set[tuple[str, str, str]] = set()

    def add(area: str, cs: list[Constatacao] | tuple[Constatacao, ...], ok: str | None = None) -> None:
        novos = 0
        for c in cs:
            chave = (c.codigo, c.caminho, c.severidade)
            if chave in vistos:
                continue
            vistos.add(chave)
            novos += 1
            itens.append(ItemPreflight(area, c.codigo, c.caminho, c.mensagem, _NIVEL[c.severidade], c.severidade))
        if not cs and ok:
            itens.append(ItemPreflight(area, "verificado", area, ok, "aceitavel", "ok"))

    add("inventario", validar_inventario(inv).constatacoes,
        f"{len(inv.dispositivos)} dispositivo(s) da microrrede {inv.identidade.uid} (revisão "
        f"{inv.identidade.revisao_config}), UIDs únicos e procedência por valor.")
    add("cenario", list(validar_cenario(cen).constatacoes) + coerencia_cenario_inventario(cen, inv),
        "Cenário referencia a mesma microrrede, incarnação e inventário físico; condições para todos os habilitados.")
    add("tempo", validar_definicao_temporal(dt),
        f"N = {dt.malha.N} intervalos e N+1 = {dt.malha.N + 1} fronteiras; Δ = {dt.malha.delta_s} s.")
    termos = frozenset(pol.objetivo.termos) if pol is not None else frozenset()
    mat = matriz_parametros(inv, termos=termos, contexto=contexto)
    from .projecao import sem_curva_declarada               # C-3DA2H-01 (curvas_h2 None = inalterado)
    cm = sem_curva_declarada(constatacoes_matriz(mat), curvas_h2)
    add("parametros", cm, f"{len(mat.entradas)} requisito(s) classificados sem bloqueio.")
    if prev is None:
        add("previsoes", [erro("previsao_ausente", "previsao", "Nenhum conjunto de previsões para o controlador.")])
    else:
        add("previsoes", validar_previsao(prev, dt), f"{len(prev.series)} série(s) causais cobrindo a janela de controle.")
    if real is None:
        add("realizacao", [aviso("realizacao_nao_fornecida", "realizacao",
                                 "Sem realização: a execução (plano → estado) não pode ser avaliada.")])
    else:
        add("realizacao", validar_realizacao(real, dt), f"{len(real.series)} série(s) cobrindo a missão.")
        if prev is not None:
            add("separacao", validar_separacao(prev, real, dt), "Previsão e realização distintas (ou oráculo declarado).")
    # referências UID
    refs: list[Constatacao] = []
    recursos = {str(r): d for d in inv.dispositivos if d.habilitado for r in recursos_ems(d)}
    uids_dem = {cd.uid for cd in pol.demandas} if pol is not None else set()
    for nome, conj in (("previsao", prev), ("realizacao", real)):
        if conj is None:
            continue
        for s in conj.series:
            alvo = s.uid
            if alvo in recursos or alvo in uids_dem or alvo in inv.uids():
                continue
            if pol is None:          # classes de demanda são declaradas pelas políticas: sem elas, não verificável
                refs.append(aviso("uid_nao_verificavel_sem_politicas", f"{nome}[{s.uid}:{s.grandeza}]",
                                  f"UID {s.uid} não é dispositivo desta microrrede; sem políticas não se sabe se é classe "
                                  "de demanda declarada."))
            else:
                refs.append(erro("referencia_uid_inexistente", f"{nome}[{s.uid}:{s.grandeza}]",
                                 f"UID {s.uid} não é recurso habilitado desta microrrede nem classe de demanda declarada."))
    if prev is not None and real is not None:
        # C-01: só se exige série realizada quando EXISTEM intervalos observados (offline: K_M; online: k de τ_k).
        # Online com observado_ate_utc = τ_0 (k = 0) é um estado válido: nada foi realizado ainda e nada é inventado.
        k_obs, _ = intervalos_observados(real, dt)       # erro de modo/instante já constatado em validar_realizacao
        if k_obs is not None and k_obs > 0:
            for s in prev.series:
                if s.grandeza in ("potencia", "disponibilidade") and real.serie(s.uid, s.grandeza) is None:
                    refs.append(erro("realizacao_ausente_para_recurso", f"realizacao[{s.uid}:{s.grandeza}]",
                                     f"Recurso previsto sem série realizada para os {k_obs} intervalo(s) observados."))
        elif k_obs == 0:
            refs.append(aviso("nenhum_intervalo_observado", "realizacao.observado_ate_utc",
                              "Observação online em τ_0: nenhum intervalo realizado ainda (válido para preparar a "
                              "otimização com previsões; nada é completado)."))
    if compromisso is not None:
        gers = {k for k, d in recursos.items() if d.modelo.papel_ems == "gerador"}
        for k, prog in compromisso.items():
            if k not in gers:
                refs.append(erro("compromisso_uid_inexistente", f"compromisso[{k!r}]",
                                 "Programa para UID que não é gerador habilitado desta microrrede."))
                continue
            ci = cen.condicao(recursos[k].uid)
            if ci is not None and ci.disponibilidade == "indisponivel" and any(x == 1 for x in prog):
                refs.append(erro("compromisso_com_indisponibilidade", f"compromisso[{k}]",
                                 "u = 1 para recurso indisponível no cenário."))
    add("referencias", refs, "Todas as referências UID resolvem para recursos desta microrrede.")
    # restrições × equipamentos
    rest: list[Constatacao] = []
    if pol is not None:
        papeis = {d.modelo.papel_ems for d in recursos.values()} | {d.modelo.tecnologia_ems for d in recursos.values()}
        for t in pol.objetivo.termos:
            if t in TERMO_RECURSO and TERMO_RECURSO[t] not in papeis:
                rest.append(erro("termo_sem_recurso", f"politicas.objetivo.termos[{t}]",
                                 f"Termo {t!r} sem nenhum recurso habilitado do tipo {TERMO_RECURSO[t]!r}."))
        if pol.servico.descarte is not None and str(pol.servico.descarte.uid) not in inv.uids():
            # o inventário do Piso 1 não tem tipo "descarte": fora de ensaio, um sumidouro declarado é inexistente
            rest.append((erro if contexto == "operacional" else aviso)(
                "descarte_sem_dispositivo", "politicas.servico.descarte",
                "Descarte declarado sem dispositivo físico no inventário (D03: sem dispositivo, D̄ = 0)."))
    add("restricoes", rest, "Termos e políticas compatíveis com os equipamentos habilitados.")
    sint = _procs_sinteticas(inv, cen, prev, real, pol)
    if contexto == "operacional":
        add("sinteticos", [erro("dado_sintetico_fora_de_ensaio", o, "Dado sintético em contexto operacional.")
                           for o in sint], "Nenhum dado sintético em contexto operacional.")
    else:
        add("sinteticos", [aviso("dado_sintetico_em_ensaio", o, "Dado sintético (ensaio rotulado).") for o in sint],
            "Nenhum dado sintético.")
    proj = None
    if pol is None:
        msg = "Políticas (serviço, terminal, objetivo, classes de demanda, variante de commitment) não fornecidas"
        add("politicas", [erro("politicas_ausentes", "politicas", msg + ": não há autorização para otimizar.")]
            if finalidade == "otimizacao" else
            [aviso("politicas_nao_fornecidas_diagnostico_parcial", "politicas",
                   msg + ": diagnóstico PARCIAL dos dados; nenhuma política é criada.")])
    if prev is not None and pol is not None and commitment_3c1 is not None:
        from .compromisso import ResultadoProjecao3C1, montar_entrada_3c1
        e3, cs3, pbase = montar_entrada_3c1(inv, cen, prev, dt, pol, commitment_3c1, contexto=contexto,
                                            curvas_h2=curvas_h2, massas_h2_eventos=massas_h2_eventos)
        proj = ResultadoProjecao3C1(e3, cs3, pbase)
        add("contrato", [c for c in cs3 if c.codigo != "entrada_de_ensaio"],
            "Entrada 3C-1 montada e aceita por validar_entrada_3c1 (base 3B-P + commitment por unidade).")
    elif prev is not None and pol is not None:
        proj = montar_entrada(inv, cen, prev, dt, pol, contexto=contexto, curvas_h2=curvas_h2)
        add("contrato", [c for c in proj.constatacoes if c.codigo != "entrada_de_ensaio"],
            "Entrada canônica montada e aceita por validar_entrada (3A/3B-P).")
    if finalidade == "otimizacao" and commitment_3c1 is not None:
        sv3: list[Constatacao] = []
        if proj is None or not proj.aceito:
            sv3.append(erro("projecao_nao_aceita", "projecao",
                            "Sem entrada 3C-1 aceita: o solver 3C-1 não pode ser chamado."))
        else:
            from ..compromisso.preflight import preflight_3c1
            sv3 += [c for c in preflight_3c1(proj.entrada, compromisso) if c.severidade != "aviso"]
        add("solver", sv3, "Entrada 3C-1 aceita e preflight do commitment dinâmico sem bloqueios.")
    elif finalidade == "otimizacao":
        sv: list[Constatacao] = []
        if proj is None or not proj.aceito:
            sv.append(erro("projecao_nao_aceita", "projecao",
                           "Sem entrada canônica aceita (previsão/políticas ausentes ou projeção rejeitada): o solver "
                           "não pode ser chamado."))
        else:
            from .. import FORMULACAO_3BP
            from ..milp.config import preflight_3bp      # sem Pyomo (só contratos)
            if proj.entrada.versao_formulacao != FORMULACAO_3BP:
                sv.append(erro("formulacao_sem_solver", "politicas.versao_formulacao",
                               f"Formulação {proj.entrada.versao_formulacao!r} não tem solver; o MILP exige "
                               f"{FORMULACAO_3BP!r}."))
            else:
                sv += preflight_3bp(proj.entrada, compromisso)
        add("solver", sv, "Entrada aceita e perfil 3B-P satisfeito (compromisso fixo coerente).")
    rel = RelatorioPreflightEMS(inv.identidade.uid, cen.cenario_uid, contexto, finalidade, tuple(itens))
    return rel, proj


__all__ = ["AREAS", "FINALIDADES", "ItemPreflight", "RelatorioPreflightEMS", "SEVERIDADES", "hash_preflight", "preflight_ems_v2"]
