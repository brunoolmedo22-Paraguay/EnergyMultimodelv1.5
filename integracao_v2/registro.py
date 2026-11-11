"""Evidência PERSISTIDA de uma rodada V2 (Piso 3D-A) e sua reabertura SEM otimizador.

Contrato de dados de uma rodada ``concluida`` do motor ``milp_mpc_v1`` (itens de ``scenario_run_data``; nomes na
whitelist do pacote ``seeds2-study`` v1 — só ``.csv``/``.json``/``.zip``; nenhum formato novo):

* ``v2/registros_selados.zip`` — FONTE CANÔNICA: o texto canônico EXATO (``ems_v2.ponte.canonico.json_canonico``) de todo
  registro selado da missão, com os nomes nativos do motor: janelas MPC (cadeia), registros 3C-0, anexos 3C-3,
  coordenações 3C-4, livro de observações K6 e os registros de missão MPC / rede / hierárquico. ZIP determinístico;
* ``v2/modelo.json`` — modelo 3C-3 da missão (parâmetros efetivos com procedência por campo) e configurações (MPC, rede,
  planejador), reconstruíveis por ``de_dict`` e CONFERIDOS pelos hashes dos registros selados;
* VISTAS DERIVADAS (função determinística dos registros selados + modelo; regeneradas e comparadas byte a byte na
  reabertura): ``v2/intervalos.csv`` (N intervalos aplicados), ``v2/fronteiras.csv`` (N + 1 estados de fronteira),
  ``v2/janelas.csv`` (decisões por janela: solver, gap, custos, sinal de valor futuro, tempos), ``v2/planos.csv``
  (previsto × aplicado por janela), ``v2/coordenacoes.json`` (sinais V(E), modos, qualidade, degradações);
* ``v2/auditoria.json`` (auditoria INTEGRAL independente, sem solver), ``v2/preflight.json`` (preflight V2 + matriz
  fonte → transformação → validação → registro → vista) e ``v2/indice.json`` (índice: papéis, SHA-256, dicionário de
  colunas com unidade/sinal/tipo de amostra, convenções e limitações).

Uma missão INTERROMPIDA pelo controlador não é ``concluida``: o formato ``seeds2-study`` v1 não admite dados em rodadas
não concluídas, por isso a evidência parcial (mesmos textos canônicos + vistas, rotulada ``parcial``) é gravada no
``outcome`` da rodada. O custo parcial nunca é apresentado como custo da missão.

``verificar`` reabre uma rodada (``MicrogridStore`` ou estudo arquivado — mesmo contrato ``run_data``): confere os hashes,
reconstrói os registros, regenera as vistas e o resumo e reexecuta a auditoria integral. NUNCA importa Pyomo/HiGHS.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from ems_v2.contracts import de_dict, para_dict
from ems_v2.hierarquia import FORMULACAO_3C4
from ems_v2.hierarquia.auditoria import auditar_missao_hierarquica
from ems_v2.hierarquia.contrato import ConfiguracaoPlanejador3C4, hash_configuracao_planejador
from ems_v2.hierarquia.mpc import (RegistroCoordenacao3C4, RegistroMissaoHierarquica3C4, nome_coordenacao,
                                   nome_missao_hier)
from ems_v2.mpc.contrato import ConfiguracaoMPC
from ems_v2.mpc.observacoes import DocumentoLivro, LivroObservacoes
from ems_v2.mpc.persistencia import nome_janela
from ems_v2.mpc.registro import RegistroJanelaMPC, RegistroMissaoMPC
from ems_v2.ponte.canonico import de_json, json_canonico
from ems_v2.ponte.registro import SUFIXO_ARQUIVO, RegistroExecucaoEMS
from ems_v2.rede.contrato import EntradaRede3C3, hash_entrada_3c3
from ems_v2.rede.mpc import ConfiguracaoRedeMPC, RegistroMissaoRede3C3, hash_configuracao_rede
from ems_v2.reference import vazao_pwl
from ems_v2.rede.registro import SUFIXO_ANEXO_3C3, AnexoExecucao3C3

from seeds2.microgrid.store import StoreError
from seeds2.operation import mission as M

from . import estrategia as E

FORMATO, VERSAO = "seeds2-milp-mpc-run-data", 3
# Versão 1 = Piso 3D-A (sem renováveis). Versão 2 = Piso 3D-A2-R: colunas por recurso renovável e ``v2/renovaveis.json``
# quando o modelo tem renováveis; sem renováveis, as vistas e o resumo da versão 2 são IDÊNTICOS aos da versão 1.
VERSOES_LEGIVEIS = (1, 2, 3)
# Versão 3 = Piso 3D-A2-H: colunas por unidade PEMFC, ``v2/pemfc.json`` (curva + certificado B04, comprometido no
# manifesto) e ``v2/pemfc_dinamica.json`` (verificação dinâmica a posteriori); sem PEMFC, idêntica à versão 2.
PREFIXO = "v2/"
N_SELADOS, N_MODELO, N_INDICE = "v2/registros_selados.zip", "v2/modelo.json", "v2/indice.json"
N_INTERVALOS, N_FRONTEIRAS, N_JANELAS, N_PLANOS = ("v2/intervalos.csv", "v2/fronteiras.csv", "v2/janelas.csv",
                                                   "v2/planos.csv")
N_COORD, N_AUDITORIA, N_PREFLIGHT = "v2/coordenacoes.json", "v2/auditoria.json", "v2/preflight.json"
N_RENOV = "v2/renovaveis.json"                        # só quando o modelo tem renováveis (versão 2)
N_PEMFC, N_PEMFC_DIN = "v2/pemfc.json", "v2/pemfc_dinamica.json"   # só com PEMFC (versão 3)
VISTAS = (N_INTERVALOS, N_FRONTEIRAS, N_JANELAS, N_PLANOS, N_COORD)
OBRIGATORIOS = (N_INDICE, N_SELADOS, N_MODELO, *VISTAS, N_AUDITORIA, N_PREFLIGHT)
_NOME_SELADO = re.compile(r"[0-9a-f]{32}\.[A-Za-z0-9._\-]{1,80}\.json")
MAX_SELADOS, MAX_BYTES_SELADOS = 20_000, 256 * 1024 * 1024
TOL_CUSTO = (1e-6, 1e-9)                              # absoluta [R$], relativa — só para conferir a decomposição derivada
CONVENCOES = {
    "potencia": "kW LÍQUIDOS no barramento equivalente; valores de intervalo são MÉDIAS do intervalo [início, fim)",
    "sinais": "descarga, importação e geração INJETAM no barramento (>= 0); carga da bateria, exportação e demanda "
              "CONSOMEM (>= 0). Carga de bateria nunca é geração; potência e energia nunca se somam",
    "indices": "N intervalos de decisão (intervalo g = [τ_g, τ_{g+1})) e N + 1 estados de fronteira (fronteira k = τ_k); o "
               "estado terminal NÃO é um intervalo",
    "energia": "energia [kWh] = potência média [kW] × Δ [h]; estado de energia das baterias em kWh na fronteira",
    "custos": "custo REALIZADO = aplicado × realização simulada, liquidado pela tarifa declarada; NUNCA inclui o custo "
              "futuro estimado (instrumento de decisão) nem custos planejados de janelas",
    "tempo": "instantes em UTC (ISO 8601); a coluna local usa o fuso DECLARADO da missão, só para apresentação",
}
LIMITACOES = (
    "Simulação offline ALGÉBRICA em contexto de ensaio: não é controle de equipamentos, SCADA, validação física nem fatura.",
    "Planta = executor algébrico de referência do ems_v2 (balanço ativo agregado): sem fluxo AC, tensão, reativo ou perdas.",
    "Demanda agregada crítica + baterias + FV/eólica (potencial dos modelos físicos do SEEDS2) + PEMFC (curva do modelo "
    "físico aproximado com certificado B04 verificado) + PCC declarado; térmica NÃO representável (M19).",
    "PEMFC: commitment INSTANTÂNEO (abstração declarada D05); a partida física é avaliada a posteriori pelo modelo "
    "dinâmico (v2/pemfc_dinamica.json) — o despacho MILP não é declarado fisicamente executável fora das tolerâncias.",
    "Potencial renovável REALIZADO = previsto (mesmo modelo e clima): a simulação não tem erro de previsão renovável.",
    "Trajetória de convergência do HiGHS NÃO é registrada: só terminação, objetivo, limite dual, gap e tamanho do modelo.",
    "Restrições ativas/preços duais NÃO são registrados (duais de MILP não são preços-sombra).",
    "SHA-256 detecta alteração frente ao conteúdo conservado; não é assinatura digital.",
    "Tempos de relógio não são reprodutíveis; a impressão determinística dos registros os exclui.",
)


class IntegridadeV2Error(StoreError):
    """A evidência persistida de uma rodada V2 está ausente, incoerente ou adulterada (mensagem apresentável)."""


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False).encode("utf-8")


# ====================================================================== evidência (objetos selados da missão)
@dataclass
class Evidencia:
    missao_uid: str
    modelo: EntradaRede3C3
    configuracao_rede: ConfiguracaoRedeMPC
    configuracao_planejador: ConfiguracaoPlanejador3C4
    registro_missao: RegistroMissaoMPC
    registros: tuple
    livro: LivroObservacoes
    registros_3c0: tuple
    anexos_3c3: tuple
    registro_rede: RegistroMissaoRede3C3 | None
    coordenacoes: tuple
    registro_hierarquico: RegistroMissaoHierarquica3C4 | None
    textos: dict = field(default_factory=dict)        # nome nativo → texto canônico

    @property
    def cfg(self) -> ConfiguracaoMPC:
        return self.registro_missao.conteudo.configuracao


def textos_selados(res) -> dict[str, str]:
    """Texto canônico de cada registro selado do resultado, com o nome de arquivo NATIVO do motor."""
    m = res.registro_missao.conteudo.identidade.missao_uid
    out: dict[str, str] = {}
    for r in res.registros:
        out[nome_janela(m, r.conteudo.posicao)] = json_canonico(r)
    for r0 in res.registros_3c0:
        out[f"{r0.execucao_uid}{SUFIXO_ARQUIVO}"] = json_canonico(r0)
    for a in res.anexos_3c3:
        out[f"{a.conteudo.execucao_uid}{SUFIXO_ANEXO_3C3}"] = json_canonico(a)
    for co in res.coordenacoes:
        out[nome_coordenacao(m, co.posicao)] = json_canonico(co)
    out[f"{m}.livro.mpc3c2.json"] = json_canonico(res.livro.exportar())
    out[f"{m}.missao.mpc3c2.json"] = json_canonico(res.registro_missao)
    if res.registro_rede is not None:
        out[f"{m}.rede.missao.mpc3c3.json"] = json_canonico(res.registro_rede)
    if res.registro_hierarquico is not None:
        out[nome_missao_hier(m)] = json_canonico(res.registro_hierarquico)
    return dict(sorted(out.items()))


def empacotar(textos: dict[str, str]) -> bytes:
    """ZIP determinístico (nomes ordenados, data fixa) dos textos canônicos."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome in sorted(textos):
            info = zipfile.ZipInfo(nome, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, textos[nome].encode("utf-8"))
    return buf.getvalue()


def desempacotar(dados: bytes) -> dict[str, str]:
    """Lê o ZIP EM MEMÓRIA (nada é extraído em disco): só nomes planos esperados, tamanhos limitados, UTF-8."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile:
        raise IntegridadeV2Error("Registros selados ilegíveis (ZIP inválido).") from None
    infos = zf.infolist()
    if len(infos) > MAX_SELADOS or sum(i.file_size for i in infos) > MAX_BYTES_SELADOS:
        raise IntegridadeV2Error("Registros selados fora dos limites de tamanho.")
    out: dict[str, str] = {}
    for i in infos:
        if not _NOME_SELADO.fullmatch(i.filename) or i.filename in out:
            raise IntegridadeV2Error(f"Registro selado com nome inesperado: {i.filename[:60]!r}.")
        try:
            out[i.filename] = zf.read(i).decode("utf-8")
        except (UnicodeDecodeError, zipfile.BadZipFile, OSError):
            raise IntegridadeV2Error(f"Registro selado ilegível: {i.filename[:60]!r}.") from None
    return out


def modelo_doc(modelo, cfg_mpc, cfg_rede, cfg_plan) -> dict:
    return {"formato": FORMATO, "versao": VERSAO,
            "entrada_rede_3c3": para_dict(modelo), "configuracao_mpc": para_dict(cfg_mpc),
            "configuracao_rede": para_dict(cfg_rede), "configuracao_planejador": para_dict(cfg_plan),
            "hashes": {"modelo_rede_3c3": hash_entrada_3c3(modelo), "configuracao_rede": hash_configuracao_rede(cfg_rede),
                       "configuracao_planejador": hash_configuracao_planejador(cfg_plan)}}


def evidencia_do_resultado(res, mont) -> Evidencia:
    m = res.registro_missao.conteudo.identidade.missao_uid
    return Evidencia(m, mont.modelo, mont.configuracao_rede, mont.configuracao_planejador, res.registro_missao,
                     tuple(res.registros), res.livro, tuple(res.registros_3c0), tuple(res.anexos_3c3), res.registro_rede,
                     tuple(res.coordenacoes), res.registro_hierarquico, textos_selados(res))


def evidencia_de_textos(textos: dict[str, str], mdoc: dict, missao_uid: str) -> Evidencia:
    """Reconstrói os objetos selados a partir do texto canônico persistido (estrito; sem ``eval``/``pickle``)."""
    m = missao_uid

    def ler(cls, nome):
        if nome not in textos:
            raise IntegridadeV2Error(f"Registro selado ausente: {nome}.")
        try:
            return de_json(cls, textos[nome])
        except Exception as exc:                       # noqa: BLE001 — conteúdo ilegível/adulterado
            raise IntegridadeV2Error(f"Registro selado inválido ({nome}): {type(exc).__name__}: {str(exc)[:160]}") from None
    try:
        modelo = de_dict(EntradaRede3C3, mdoc["entrada_rede_3c3"], "EntradaRede3C3")
        cfg_rede = de_dict(ConfiguracaoRedeMPC, mdoc["configuracao_rede"], "ConfiguracaoRedeMPC")
        cfg_plan = de_dict(ConfiguracaoPlanejador3C4, mdoc["configuracao_planejador"], "ConfiguracaoPlanejador3C4")
    except Exception as exc:                           # noqa: BLE001
        raise IntegridadeV2Error(f"Modelo da missão ilegível: {type(exc).__name__}: {str(exc)[:160]}") from None
    rm = ler(RegistroMissaoMPC, f"{m}.missao.mpc3c2.json")
    livro = LivroObservacoes.importar(ler(DocumentoLivro, f"{m}.livro.mpc3c2.json"))
    regs, p = [], 0
    while nome_janela(m, p) in textos:
        regs.append(ler(RegistroJanelaMPC, nome_janela(m, p)))
        p += 1
    r0s, anexos = [], []
    for r in regs:
        u = r.conteudo.execucao_uid
        if u is not None and f"{u}{SUFIXO_ARQUIVO}" in textos:
            r0s.append(ler(RegistroExecucaoEMS, f"{u}{SUFIXO_ARQUIVO}"))
            anexos.append(ler(AnexoExecucao3C3, f"{u}{SUFIXO_ANEXO_3C3}"))
    coords, p = [], 0
    while nome_coordenacao(m, p) in textos:
        coords.append(ler(RegistroCoordenacao3C4, nome_coordenacao(m, p)))
        p += 1
    rr = ler(RegistroMissaoRede3C3, f"{m}.rede.missao.mpc3c3.json") if f"{m}.rede.missao.mpc3c3.json" in textos else None
    rh = ler(RegistroMissaoHierarquica3C4, nome_missao_hier(m)) if nome_missao_hier(m) in textos else None
    usados = ({nome_janela(m, i) for i in range(len(regs))} | {nome_coordenacao(m, i) for i in range(len(coords))}
              | {f"{x.execucao_uid}{SUFIXO_ARQUIVO}" for x in r0s}
              | {f"{x.conteudo.execucao_uid}{SUFIXO_ANEXO_3C3}" for x in anexos}
              | {f"{m}.missao.mpc3c2.json", f"{m}.livro.mpc3c2.json", f"{m}.rede.missao.mpc3c3.json", nome_missao_hier(m)})
    if set(textos) - usados:
        raise IntegridadeV2Error(f"Registros selados não referenciados pela missão: {sorted(set(textos) - usados)[:3]}.")
    return Evidencia(m, modelo, cfg_rede, cfg_plan, rm, tuple(regs), livro, tuple(r0s), tuple(anexos), rr, tuple(coords),
                     rh, dict(sorted(textos.items())))


def auditar(ev: Evidencia, verdade=None):
    """Auditoria INTEGRAL independente (3C-4 sobre 3C-3/3C-2): só biblioteca padrão, nenhum solver."""
    return auditar_missao_hierarquica(ev.registro_missao, ev.registros, ev.livro, ev.modelo, ev.configuracao_rede,
                                      ev.configuracao_planejador, registros_3c0=ev.registros_3c0, anexos=ev.anexos_3c3,
                                      registro_rede=ev.registro_rede, coordenacoes=ev.coordenacoes,
                                      registro_hierarquico=ev.registro_hierarquico, verdade=verdade)


def auditoria_doc(rel) -> dict:
    return {"aceito": bool(rel.aceito), "verificacoes": dict(rel.verificacoes),
            "constatacoes": [{"severidade": c.severidade, "codigo": c.codigo, "caminho": c.caminho, "mensagem": c.mensagem}
                             for c in rel.constatacoes],
            "projecoes_numericas_energia": [para_dict(x) for x in rel.projecoes_numericas],
            "normalizacoes_pcc": [para_dict(x) for x in rel.normalizacoes_pcc],
            "metodo": "ems_v2.hierarquia.auditoria.auditar_missao_hierarquica (independente do MILP; sem Pyomo/HiGHS)",
            "tolerancias": "provisórias (decisão D07 pendente)"}


# ====================================================================== vistas derivadas
def _num(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    return str(v)


def _csv(colunas: list[str], linhas: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(colunas)
    for ln in linhas:
        w.writerow([_num(ln.get(c)) for c in colunas])
    return buf.getvalue().encode("utf-8")


def _local(inst_utc: str, fuso: str | None) -> str:
    if not fuso:
        return ""
    t = datetime.fromisoformat(inst_utc).astimezone(timezone.utc).timestamp()
    return M.utc_to_wall([t], fuso)[0].strftime("%Y-%m-%dT%H:%M:%S")


def _preco(perfis, grandeza: str, inst_utc: str) -> float | None:
    """Preço de DECISÃO declarado do bloco que contém o instante (maior revisão)."""
    t = datetime.fromisoformat(inst_utc)
    for p in sorted((x for x in perfis if x.grandeza == grandeza), key=lambda x: -x.revisao):
        for b in p.blocos:
            ini = datetime.fromisoformat(b.inicio_utc)
            if ini <= t < ini + timedelta(seconds=b.duracao_s):
                return b.valor
    return None


def _proximo(a: float, b: float) -> bool:
    return abs(a - b) <= TOL_CUSTO[0] + TOL_CUSTO[1] * max(abs(a), abs(b))


def _contexto(ev: Evidencia) -> dict:
    base = ev.modelo.base
    if any(g.tecnologia != "pemfc" for g in base.geradores):
        raise IntegridadeV2Error("As vistas V2 não cobrem geradores térmicos (modelo fora do escopo: M19).")
    malha = ev.cfg.malha
    termos = set(ev.modelo.termos)
    uni = {str(u.uid): u for u in ev.modelo.compromisso.unidades}
    return {"dems": [str(d.uid) for d in base.demandas], "bats": [str(b.uid) for b in base.baterias],
            "rens": [str(r.uid) for r in base.renovaveis],
            "gers": [str(g.uid) for g in base.geradores],
            "curva": {str(g.uid): g.curva_h2.vertices for g in base.geradores if g.curva_h2 is not None},
            "cH": {str(g.uid): float(g.preco_h2.valor) for g in base.geradores
                   if g.preco_h2 is not None and "combustivel_h2" in termos},
            "u0": {str(e.uid): bool(e.ligado) for e in base.estados_geradores},
            "mev": {k: (0.0 if u.massa_h2_partida_kg is None else float(u.massa_h2_partida_kg.valor),
                        0.0 if u.massa_h2_parada_kg is None else float(u.massa_h2_parada_kg.valor)) for k, u in uni.items()},
            "cev": {k: (float(u.custo_partida.valor) if u.custo_partida is not None and "eventos" in termos else 0.0,
                        float(u.custo_parada.valor) if u.custo_parada is not None and "eventos" in termos else 0.0)
                    for k, u in uni.items()},
            "tec": {str(r.uid): r.tecnologia for r in base.renovaveis},
            "base": {str(r.uid): r.base_potencial for r in base.renovaveis},
            "cap": {str(b.uid): float(b.capacidade_kWh.valor) for b in base.baterias},
            "cthr": {str(b.uid): (float(b.custo_throughput.valor) if b.custo_throughput is not None
                                  and "throughput_bess" in ev.modelo.termos else None) for b in base.baterias},
            "pcc": str(ev.modelo.pcc.uid), "conectado": ev.modelo.conectado, "h": malha.delta_s / 3600.0,
            "delta_s": malha.delta_s, "inicio": malha.inicio(), "malha": malha,
            "r0": {x.execucao_uid: x for x in ev.registros_3c0},
            "anexo": {x.conteudo.execucao_uid: x for x in ev.anexos_3c3},
            "coord": {x.posicao: x for x in ev.coordenacoes}}


def _inst(cx: dict, k: int) -> str:
    return (cx["inicio"] + timedelta(seconds=cx["delta_s"] * k)).isoformat()


def _demanda_prevista(c, cx: dict, i: int) -> float | None:
    if c.previsao is None:
        return None
    tot = 0.0
    for d in cx["dems"]:
        s = c.previsao.serie(d, "potencia")
        if s is None or i >= len(s.serie.valores):
            return None
        tot += float(s.serie.valores[i])
    return tot


def linhas_intervalos(ev: Evidencia, fuso: str | None) -> tuple[list[str], list[dict]]:
    cx = _contexto(ev)
    h, pcc, bats, rens, gers = cx["h"], cx["pcc"], cx["bats"], cx["rens"], cx["gers"]
    col_b = [f"{b}|{g}" for b in bats for g in ("P_c_kW", "P_d_kW")] + [f"{r}|{g}" for r in rens for g in COLS_RENOV] + [
        f"{u}|{g}" for u in gers for g in COLS_GER]
    cols = (["intervalo", "janela", "indice_no_plano", "inicio_utc", "fim_utc", "inicio_local", "demanda_prevista_kW",
             "demanda_realizada_kW", "demanda_nao_atendida_kW", "demanda_atendida_kW"] + col_b +
            ["pcc_importacao_programada_kW", "pcc_importacao_realizada_kW", "pcc_exportacao_programada_kW",
             "pcc_exportacao_realizada_kW", "pcc_desvio_liquido_kW", "pcc_disponibilidade_observada",
             "pcc_importacao_medida_kW", "pcc_exportacao_medida_kW", "residuo_balanco_kW",
             "tarifa_importacao_decisao_R_kWh", "tarifa_exportacao_decisao_R_kWh", "preco_importacao_liquidacao_R_kWh",
             "preco_exportacao_liquidacao_R_kWh", "custo_importacao_R", "receita_exportacao_R", "custo_desvio_rede_R",
             "custo_throughput_R", "custo_realizado_intervalo_R", "custo_realizado_acumulado_R"])
    linhas: list[dict] = []
    acum = 0.0
    e_ren = {r: 0.0 for r in rens}
    u_ant = dict(cx["u0"])
    m_acum = {u: 0.0 for u in gers}
    for r in ev.registros:
        c = r.conteudo
        an = cx["anexo"].get(c.execucao_uid)
        passos_pcc = {x.indice_global: x for x in an.conteudo.passos_pcc} if an is not None else {}
        liq = {x.indice_global: x for x in an.conteudo.liquidacao} if an is not None else {}
        desv = {x.indice_global: x for x in an.conteudo.desvios} if an is not None else {}
        soma = 0.0
        for p in c.passos:
            g, ap, ob = p.indice_global, p.aplicado, p.entorno_observado
            real = sum(float(ob[f"{d}|potencia"]) for d in cx["dems"])
            ell = sum(float(ap.get(f"{d}|ell", 0.0)) for d in cx["dems"])
            ln = {"intervalo": g, "janela": c.janela.indice_janela, "indice_no_plano": p.indice_plano,
                  "inicio_utc": _inst(cx, g), "fim_utc": _inst(cx, g + 1), "inicio_local": _local(_inst(cx, g), fuso),
                  "demanda_prevista_kW": _demanda_prevista(c, cx, p.indice_plano), "demanda_realizada_kW": real,
                  "demanda_nao_atendida_kW": ell, "demanda_atendida_kW": real - ell}
            inj, thr, tem_thr = 0.0, 0.0, False
            for u in rens:
                A, a = float(ob[f"{u}|potencia"]), float(ob[f"{u}|disponibilidade"])
                util = A * a if cx["base"][u] == "antes_da_disponibilidade" else A
                pr = float(ap[f"{u}|P_R"])
                e_ren[u] += h * pr
                ln.update({f"{u}|A_prevista_kW": _renovavel_prevista(c, u, p.indice_plano, cx),
                           f"{u}|A_observada_kW": A, f"{u}|disponibilidade_observada": a, f"{u}|A_utilizavel_kW": util,
                           f"{u}|P_R_kW": pr, f"{u}|vertimento_kW": util - pr, f"{u}|E_aproveitada_acum_kWh": e_ren[u]})
                inj += pr
            c_h2 = c_ev = 0.0
            for u in gers:
                ug, pg = float(ap[f"{u}|u"]) > 0.5, float(ap[f"{u}|p"])
                part, par = int(ug and not u_ant.get(u, False)), int((not ug) and u_ant.get(u, False))
                u_ant[u] = ug
                q = float(vazao_pwl(cx["curva"][u], pg, True)) if ug and u in cx["curva"] else 0.0
                msu, msd = cx["mev"].get(u, (0.0, 0.0))
                m = h * q + msu * part + msd * par
                m_acum[u] += m
                ch = cx["cH"][u] * m if u in cx["cH"] else 0.0
                csu, csd = cx["cev"].get(u, (0.0, 0.0))
                ce = csu * part + csd * par
                c_h2 += ch
                c_ev += ce
                ln.update({f"{u}|u": int(ug), f"{u}|p_kW": pg, f"{u}|partida": part, f"{u}|parada": par,
                           f"{u}|q_h2_kg_h": q, f"{u}|m_h2_kg": m, f"{u}|m_h2_acum_kg": m_acum[u],
                           f"{u}|custo_h2_R": ch if u in cx["cH"] else None, f"{u}|custo_eventos_R": ce})
                inj += pg
            for b in bats:
                pc, pd_ = float(ap.get(f"{b}|P_c", 0.0)), float(ap.get(f"{b}|P_d", 0.0))
                ln[f"{b}|P_c_kW"], ln[f"{b}|P_d_kW"] = pc, pd_
                inj += pd_ - pc
                if cx["cthr"][b] is not None:
                    tem_thr = True
                    thr += h * cx["cthr"][b] * (pc + pd_)
            pimp, pexp = float(ap.get(f"{pcc}|P_imp", 0.0)), float(ap.get(f"{pcc}|P_exp", 0.0))
            ln["residuo_balanco_kW"] = inj + pimp - pexp - (real - ell)
            gasto = rec = cdes = 0.0
            if cx["conectado"]:
                pp, lq, dv = passos_pcc.get(g), liq.get(g), desv.get(g)
                if pp is None or lq is None:
                    raise IntegridadeV2Error(f"Intervalo {g} sem registro do PCC/liquidação no anexo 3C-3.")
                gasto, rec, cdes = float(lq.gasto_importacao_R), float(lq.receita_exportacao_R), float(lq.custo_desvio_R)
                ln.update({"pcc_importacao_programada_kW": pp.importacao_programada_kW,
                           "pcc_importacao_realizada_kW": pp.importacao_realizada_kW,
                           "pcc_exportacao_programada_kW": pp.exportacao_programada_kW,
                           "pcc_exportacao_realizada_kW": pp.exportacao_realizada_kW,
                           "pcc_desvio_liquido_kW": None if dv is None else dv.desvio_kW,
                           "pcc_disponibilidade_observada": pp.disponibilidade_observada,
                           "pcc_importacao_medida_kW": pp.importacao_medida_kW,
                           "pcc_exportacao_medida_kW": pp.exportacao_medida_kW,
                           "tarifa_importacao_decisao_R_kWh": _preco(ev.configuracao_rede.tarifas_decisao, "importacao",
                                                                     _inst(cx, g)),
                           "tarifa_exportacao_decisao_R_kWh": _preco(ev.configuracao_rede.tarifas_decisao, "exportacao",
                                                                     _inst(cx, g)),
                           "preco_importacao_liquidacao_R_kWh": lq.preco_importacao,
                           "preco_exportacao_liquidacao_R_kWh": lq.preco_exportacao,
                           "custo_importacao_R": gasto, "receita_exportacao_R": rec, "custo_desvio_rede_R": cdes})
            tot = gasto - rec + cdes + thr + c_h2 + c_ev
            soma += tot
            acum += tot
            ln.update({"custo_throughput_R": thr if tem_thr else None, "custo_realizado_intervalo_R": tot,
                       "custo_realizado_acumulado_R": acum})
            linhas.append(ln)
        selado = c.custos.realizado.total_R if c.custos is not None and c.custos.realizado is not None else None
        if c.passos and (selado is None or not _proximo(soma, float(selado))):
            raise IntegridadeV2Error(f"Janela {c.janela.indice_janela}: a decomposição por intervalo ({soma!r} R$) não "
                                     f"reproduz o custo realizado SELADO da janela ({selado!r} R$).")
    return cols, linhas


COLS_GER = ("u", "p_kW", "partida", "parada", "q_h2_kg_h", "m_h2_kg", "m_h2_acum_kg", "custo_h2_R", "custo_eventos_R")
COLS_RENOV = ("A_prevista_kW", "A_observada_kW", "disponibilidade_observada", "A_utilizavel_kW", "P_R_kW", "vertimento_kW",
              "E_aproveitada_acum_kWh")


def _renovavel_prevista(c, u: str, i: int, cx: dict) -> float | None:
    """Potencial UTILIZÁVEL previsto (a·A ou A já utilizável) disponível NA DECISÃO da janela, no índice ``i`` do plano."""
    if c.previsao is None:
        return None
    s, sa = c.previsao.serie(u, "potencia"), c.previsao.serie(u, "disponibilidade")
    if s is None or i >= len(s.serie.valores):
        return None
    A = float(s.serie.valores[i])
    if cx["base"][u] != "antes_da_disponibilidade":
        return A
    if sa is None or i >= len(sa.serie.valores):
        return None
    return A * float(sa.serie.valores[i])


def linhas_fronteiras(ev: Evidencia, fuso: str | None) -> tuple[list[str], list[dict]]:
    cx = _contexto(ev)
    estados = {}
    ei = ev.registro_missao.conteudo.estado_inicial
    if ei is not None:
        estados[ei.indice_fronteira] = ei
    for r in ev.registros:
        for e in r.conteudo.estados:
            ant = estados.get(e.indice_fronteira)
            if ant is not None and ant != e:
                raise IntegridadeV2Error(f"Estados divergentes na fronteira {e.indice_fronteira} entre janelas.")
            estados[e.indice_fronteira] = e
    cols = ["fronteira", "instante_utc", "instante_local"] + [f"{b}|{g}" for b in cx["bats"] for g in ("energia_kWh", "soc")]
    linhas = []
    for k in sorted(estados):
        e = estados[k]
        ln = {"fronteira": k, "instante_utc": e.instante_utc, "instante_local": _local(e.instante_utc, fuso)}
        for b in cx["bats"]:
            st = e.bateria(b)
            ln[f"{b}|energia_kWh"] = None if st is None else st.energia_kWh
            ln[f"{b}|soc"] = None if st is None else st.energia_kWh / cx["cap"][b]
        linhas.append(ln)
    return cols, linhas


def _col_tempo(prefixo: str, chave: str) -> str:
    return f"{prefixo}_{chave}" if chave.endswith("_s") else f"{prefixo}_{chave}_s"


def linhas_janelas(ev: Evidencia) -> tuple[list[str], list[dict]]:
    cx = _contexto(ev)
    chaves_t0 = sorted({k for x in ev.registros_3c0 for k in x.tempos_s})
    chaves_tc = sorted({k for x in ev.coordenacoes for k in x.tempos_s})
    cols = (["janela", "posicao", "k", "instante_decisao_utc", "N_k", "m_k", "reduzida", "final", "desfecho", "classe_falha",
             "aceitacao", "intervalos_aplicados", "solver_classificacao", "solver_terminacao", "solver_status",
             "objetivo_R", "limite_dual_R", "gap_abs_R", "gap_rel", "variaveis", "binarias_livres", "restricoes",
             "custo_operativo_previsto_janela_R", "custo_futuro_estimado_R", "planejado_prefixo_R", "realizado_R",
             "realizado_acumulado_R", "sinal_situacao", "sinal_origem", "termo_terminal_aplicado", "sinal_tipo",
             "sinal_qualidade", "sinal_motivo", "sinal_fronteira", "sinal_modos", "sinal_pontos",
             "sinal_erro_interpolacao_max_R", "avaliacoes_planejador", "plano_longo_objetivo_R", "coordenacao_motivo"]
            + [_col_tempo("tempo", k) for k in chaves_t0] + [_col_tempo("tempo_coordenacao", k) for k in chaves_tc])
    linhas, acum = [], 0.0
    for r in ev.registros:
        c, j = r.conteudo, r.conteudo.janela
        res, co = c.resolucao, cx["coord"].get(c.posicao)
        r0 = cx["r0"].get(c.execucao_uid)
        real = c.custos.realizado.total_R if c.custos is not None and c.custos.realizado is not None else None
        if real is not None:
            acum += float(real)
        ln = {"janela": j.indice_janela, "posicao": c.posicao, "k": j.k, "instante_decisao_utc": c.instante_decisao_utc,
              "N_k": j.N_k, "m_k": j.m_k, "reduzida": j.reduzida, "final": j.final, "desfecho": c.desfecho,
              "classe_falha": c.classe_falha, "aceitacao": c.aceitacao, "intervalos_aplicados": c.intervalos_aplicados,
              "realizado_R": real, "realizado_acumulado_R": acum if real is not None else None,
              "planejado_prefixo_R": c.custos.planejado_prefixo.total_R
              if c.custos is not None and c.custos.planejado_prefixo is not None else None}
        if res is not None:
            ln.update({"solver_classificacao": res.classificacao, "solver_terminacao": res.terminacao,
                       "solver_status": res.status_solucao, "objetivo_R": res.objetivo, "limite_dual_R": res.limite_dual,
                       "gap_abs_R": res.gap_abs, "gap_rel": res.gap_rel, "variaveis": res.tamanho.get("variaveis"),
                       "binarias_livres": res.tamanho.get("binarias_livres"), "restricoes": res.tamanho.get("restricoes")})
        if co is not None:
            d, s = co.decomposicao, co.sinal
            ln.update({"sinal_situacao": co.situacao, "sinal_origem": co.origem_sinal,
                       "termo_terminal_aplicado": None if co.termo_aplicado is None else co.termo_aplicado.tipo,
                       "avaliacoes_planejador": co.avaliacoes_planejador, "coordenacao_motivo": co.motivo,
                       "plano_longo_objetivo_R": None if co.plano_longo is None else co.plano_longo.objetivo_R})
            if d is not None:
                ln.update({"custo_operativo_previsto_janela_R": d.custo_operativo_previsto_R,
                           "custo_futuro_estimado_R": d.custo_futuro_estimado_R})
            if s is not None:
                ln.update({"sinal_tipo": s.tipo, "sinal_qualidade": s.qualidade.estado, "sinal_motivo": s.qualidade.motivo,
                           "sinal_fronteira": s.indice_fronteira, "sinal_modos": len(s.modos),
                           "sinal_pontos": sum(len(m.pontos) for m in s.modos),
                           "sinal_erro_interpolacao_max_R": s.qualidade.erro_interpolacao_max_R})
            for k in chaves_tc:
                ln[_col_tempo("tempo_coordenacao", k)] = co.tempos_s.get(k)
        if r0 is not None:
            for k in chaves_t0:
                ln[_col_tempo("tempo", k)] = r0.tempos_s.get(k)
        linhas.append(ln)
    return cols, linhas


def linhas_planos(ev: Evidencia) -> tuple[list[str], list[dict]]:
    cx = _contexto(ev)
    din: list[str] = []
    linhas = []
    for r in ev.registros:
        c = r.conteudo
        r0, an = cx["r0"].get(c.execucao_uid), cx["anexo"].get(c.execucao_uid)
        if r0 is None or r0.plano is None:
            continue
        pl = r0.plano
        pr = an.conteudo.plano_rede if an is not None else None
        for i in range(pl.N):
            ln = {"janela": c.janela.indice_janela, "indice_no_plano": i, "intervalo": pl.indice_fronteira_inicial + i,
                  "inicio_utc": _inst(cx, pl.indice_fronteira_inicial + i), "aplicado": i < c.intervalos_aplicados,
                  "demanda_prevista_kW": _demanda_prevista(c, cx, i)}
            for u in cx["rens"]:
                k = f"plano:{u}|A_prevista_kW"
                ln[k] = _renovavel_prevista(c, u, i, cx)
                if k not in din:
                    din.append(k)
            for cs in pl.consignas:
                k = f"plano:{cs.uid}|{cs.grandeza}"
                ln[k] = cs.valores[i]
                if k not in din:
                    din.append(k)
            for tr in pl.estados_planejados:
                for suf, v in (("inicio", tr.valores[i]), ("fim", tr.valores[i + 1])):
                    k = f"plano:{tr.uid}|{tr.grandeza}_{suf}"
                    ln[k] = v
                    if k not in din:
                        din.append(k)
            if pr is not None and cx["conectado"]:
                ln["plano:pcc_importacao_programada_kW"] = pr.importacao_programada_kW[i]
                ln["plano:pcc_exportacao_programada_kW"] = pr.exportacao_programada_kW[i]
            linhas.append(ln)
    cols = ["janela", "indice_no_plano", "intervalo", "inicio_utc", "aplicado", "demanda_prevista_kW"] + sorted(din) + (
        ["plano:pcc_importacao_programada_kW", "plano:pcc_exportacao_programada_kW"] if cx["conectado"] else [])
    return cols, linhas


def vistas(ev: Evidencia, fuso: str | None) -> dict[str, bytes]:
    """Vistas derivadas — função DETERMINÍSTICA da evidência selada (regenerável na reabertura)."""
    return {N_INTERVALOS: _csv(*linhas_intervalos(ev, fuso)), N_FRONTEIRAS: _csv(*linhas_fronteiras(ev, fuso)),
            N_JANELAS: _csv(*linhas_janelas(ev)), N_PLANOS: _csv(*linhas_planos(ev)),
            N_COORD: _json([para_dict(co) for co in ev.coordenacoes])}


# ====================================================================== resumo
def resumo(ev: Evidencia, fuso: str | None) -> dict:
    """Indicadores da missão lidos dos registros SELADOS (nunca recalculados pelo otimizador)."""
    rm, cx = ev.registro_missao.conteudo, _contexto(ev)
    ind = dict(rm.indicadores_acumulados)
    _cols, ints = linhas_intervalos(ev, fuso)
    h = cx["h"]
    bats = {}
    for b in cx["bats"]:
        e0 = rm.estado_inicial.bateria(b).energia_kWh if rm.estado_inicial is not None else None
        ef = rm.estado_final.bateria(b).energia_kWh if rm.estado_final is not None else None
        bats[b] = {"capacidade_kWh": cx["cap"][b], "energia_inicial_kWh": e0, "energia_final_kWh": ef,
                   "soc_inicial": None if e0 is None else e0 / cx["cap"][b],
                   "soc_final": None if ef is None else ef / cx["cap"][b],
                   "energia_carregada_kWh": h * sum(x[f"{b}|P_c_kW"] for x in ints),
                   "energia_descarregada_kWh": h * sum(x[f"{b}|P_d_kW"] for x in ints)}
    if ints and not (_proximo(sum(v["energia_carregada_kWh"] for v in bats.values()), ind.get("E_bess_carga_kWh", 0.0))
                     and _proximo(sum(v["energia_descarregada_kWh"] for v in bats.values()),
                                  ind.get("E_bess_descarga_kWh", 0.0))):
        raise IntegridadeV2Error("Energia carregada/descarregada por banco não reproduz os indicadores selados da missão.")
    ren = _resumo_renovaveis(cx, ints, ind)
    pem = _resumo_pemfc(cx, ints, ind)
    cr = rm.custo_realizado_acumulado
    gaps = [r.conteudo.resolucao.gap_rel for r in ev.registros
            if r.conteudo.resolucao is not None and r.conteudo.resolucao.gap_rel is not None]
    rh = ev.registro_hierarquico
    dem, ens = float(ind.get("E_demanda_realizada_kWh", 0.0)), float(ind.get("E_nao_suprida_kWh", 0.0))
    completa = rm.desfecho == "concluida" and rm.intervalos_aplicados == rm.K_M
    extra = {**({"renovaveis": ren} if ren else {}), **({"pemfc": pem} if pem else {})}
    return {**extra,
        "engine": E.MOTOR_V2, "formulacao": FORMULACAO_3C4, "missao_uid": ev.missao_uid,
        "situacao_missao": rm.desfecho, "classe_falha": rm.classe_falha, "missao_completa": completa,
        "intervalos_missao": rm.K_M, "intervalos_aplicados": rm.intervalos_aplicados, "fronteiras": rm.intervalos_aplicados + 1,
        "janelas": len(ev.registros), "delta_min": cx["delta_s"] / 60.0,
        "N": ev.cfg.malha.intervalos_otimizacao, "m": ev.cfg.malha.intervalos_reotimizacao,
        "H_L": ev.configuracao_planejador.horizonte_longo_intervalos,
        "energia_demanda_kWh": dem, "energia_atendida_kWh": dem - ens, "energia_nao_atendida_kWh": ens,
        "custo_realizado_total_R": None if cr is None else cr.total_R,
        "custo_realizado_componentes_R": {} if cr is None else {c.termo: c.valor_R for c in cr.componentes},
        "custo_realizado_parcial": not completa,
        "custo_realizado_inclui_valor_futuro": False,
        "energia_importada_kWh": ind.get("E_importada_kWh"), "energia_exportada_kWh": ind.get("E_exportada_kWh"),
        "gasto_importacao_R": ind.get("gasto_importacao_R"), "receita_exportacao_R": ind.get("receita_exportacao_R"),
        "baterias": bats, "indicadores_selados": ind,
        "sinal_valor_futuro": None if rh is None else dict(rh.contagens),
        "valoracao_terminal_declarada_R": None if rh is None else rh.valoracao_terminal_declarada_R,
        "solver": {"janelas_resolvidas": sum(1 for r in ev.registros if r.conteudo.resolucao is not None),
                   "janelas_otimas": sum(1 for r in ev.registros if r.conteudo.resolucao is not None
                                         and r.conteudo.resolucao.classificacao == "otimo"),
                   "gap_rel_max": max(gaps) if gaps else None},
        "pcc_modo": ev.modelo.pcc.modo, "obrigacoes_pendentes_fim_s": dict(rm.obrigacoes_pendentes_fim_s),
        "dados_sinteticos": True, "contexto": "ensaio",
    }


def _resumo_renovaveis(cx: dict, ints: list[dict], ind: dict) -> dict:
    """Energia por recurso renovável (disponível, utilizável, aproveitada, vertida), conferida contra os indicadores
    SELADOS da missão (E_renovavel_usada_kWh, E_curtailment_kWh). Vazio quando o modelo não tem renováveis."""
    if not cx["rens"]:
        return {}
    h = cx["h"]
    out = {}
    for u in cx["rens"]:
        def soma(g):
            return h * math.fsum(float(x[f"{u}|{g}"]) for x in ints)
        out[u] = {"tecnologia": cx["tec"][u], "energia_potencial_observada_kWh": soma("A_observada_kW"),
                  "energia_utilizavel_kWh": soma("A_utilizavel_kW"), "energia_aproveitada_kWh": soma("P_R_kW"),
                  "energia_vertida_kWh": soma("vertimento_kW"),
                  "pico_aproveitado_kW": max((float(x[f"{u}|P_R_kW"]) for x in ints), default=None)}
    if ints and not (_proximo(math.fsum(v["energia_aproveitada_kWh"] for v in out.values()),
                              float(ind.get("E_renovavel_usada_kWh", 0.0)))
                     and _proximo(math.fsum(v["energia_vertida_kWh"] for v in out.values()),
                                  float(ind.get("E_curtailment_kWh", 0.0)))):
        raise IntegridadeV2Error("Energia renovável aproveitada/vertida por recurso não reproduz os indicadores selados da "
                                 "missão.")
    return out


def _resumo_pemfc(cx: dict, ints: list[dict], ind: dict) -> dict:
    """Por unidade PEMFC: energia, H₂ (contínuo + eventos), custo, partidas/paradas — energia conferida contra o
    indicador SELADO ``E_geracao_kWh[uid]``. Vazio sem PEMFC."""
    out = {}
    h = cx["h"]
    for u in cx["gers"]:
        e = h * math.fsum(float(x[f"{u}|p_kW"]) for x in ints)
        sel = ind.get(f"E_geracao_kWh[{u}]")
        if ints and sel is not None and not _proximo(e, float(sel)):
            raise IntegridadeV2Error(f"Energia da PEMFC {u} não reproduz o indicador selado da missão.")
        on = [x for x in ints if x[f"{u}|u"]]
        out[u] = {"energia_kWh": e, "massa_h2_kg": math.fsum(float(x[f"{u}|m_h2_kg"]) for x in ints),
                  "custo_h2_R": math.fsum(float(x[f"{u}|custo_h2_R"] or 0.0) for x in ints),
                  "custo_eventos_R": math.fsum(float(x[f"{u}|custo_eventos_R"]) for x in ints),
                  "partidas": sum(int(x[f"{u}|partida"]) for x in ints), "paradas": sum(int(x[f"{u}|parada"]) for x in ints),
                  "horas_ligada": h * len(on),
                  "potencia_media_ligada_kW": (math.fsum(float(x[f"{u}|p_kW"]) for x in on) / len(on)) if on else None}
        out[u]["consumo_especifico_kg_kWh"] = out[u]["massa_h2_kg"] / e if e > 0 else None
    return out


# ====================================================================== dicionário de colunas e índice
def _dicionario(ev: Evidencia) -> dict:
    cx = _contexto(ev)
    S, D = "selado", "derivado 3D-A"

    def col(nome, unidade, amostra, descricao, origem):
        return {"nome": nome, "unidade": unidade, "amostra": amostra, "descricao": descricao, "origem": origem}
    ints = [
        col("intervalo", "", "intervalo", "índice GLOBAL g do intervalo aplicado [τ_g, τ_{g+1})", S),
        col("janela", "", "intervalo", "índice da janela MPC que decidiu e aplicou o intervalo", S),
        col("demanda_prevista_kW", "kW", "intervalo", "previsão disponível NA DECISÃO da janela (Σ classes de demanda)", S),
        col("demanda_realizada_kW", "kW", "intervalo", "realização simulada observada na conciliação (livro K6)", S),
        col("demanda_nao_atendida_kW", "kW", "intervalo", "déficit ℓ aplicado (serviço duro ⇒ 0)", S),
        col("demanda_atendida_kW", "kW", "intervalo", "realizada − não atendida", D),
        col("pcc_importacao_programada_kW", "kW", "intervalo", "importação do PLANO (consigna)", S),
        col("pcc_importacao_realizada_kW", "kW", "intervalo", "importação efetivamente trocada (>= 0; injeta)", S),
        col("pcc_exportacao_realizada_kW", "kW", "intervalo", "exportação efetivamente trocada (>= 0; consome)", S),
        col("pcc_desvio_liquido_kW", "kW", "intervalo", "líquido realizado − programado (positivo = mais importação)", S),
        col("residuo_balanco_kW", "kW", "intervalo", "Σ descarga − Σ carga + importação − exportação − demanda atendida "
            "(deve ser ~0)", D),
        col("tarifa_importacao_decisao_R_kWh", "R$/kWh", "intervalo", "tarifa DECLARADA disponível à decisão", S),
        col("preco_importacao_liquidacao_R_kWh", "R$/kWh", "intervalo", "preço aplicado na liquidação do intervalo", S),
        col("custo_importacao_R", "R$", "intervalo", "gasto de importação liquidado (energia medida × preço)", S),
        col("receita_exportacao_R", "R$", "intervalo", "receita de exportação liquidada (crédito; subtraída do custo)", S),
        col("custo_throughput_R", "R$", "intervalo", "h · c_thr · (P_c + P_d) por banco — decomposição linear conferida "
            "contra o custo selado da janela", D),
        col("custo_realizado_intervalo_R", "R$", "intervalo", "importação − receita + desvio + throughput (sem valor futuro)", D),
        col("custo_realizado_acumulado_R", "R$", "intervalo", "soma acumulada do custo realizado", D),
    ]
    for b in cx["bats"]:
        ints += [col(f"{b}|P_c_kW", "kW", "intervalo", f"potência de CARGA do banco {b} (>= 0; consome; nunca é geração)", S),
                 col(f"{b}|P_d_kW", "kW", "intervalo", f"potência de DESCARGA do banco {b} (>= 0; injeta)", S)]
    for u in cx["rens"]:
        tec = {"fv": "arranjo FV", "eolica": "registro eólico"}.get(cx["tec"][u], cx["tec"][u])
        ints += [col(f"{u}|A_prevista_kW", "kW", "intervalo", f"potencial UTILIZÁVEL previsto do {tec} {u} disponível NA "
                     "DECISÃO (modelo físico sobre o clima previsto)", S),
                 col(f"{u}|A_observada_kW", "kW", "intervalo", "potencial REALIZADO observado na conciliação (livro K6), "
                     "antes da disponibilidade", S),
                 col(f"{u}|disponibilidade_observada", "1", "intervalo", "disponibilidade a observada (indisponível ≠ "
                     "vertimento)", S),
                 col(f"{u}|A_utilizavel_kW", "kW", "intervalo", "a × A observado (potencial efetivamente utilizável)", D),
                 col(f"{u}|P_R_kW", "kW", "intervalo", "injeção renovável APLICADA (>= 0; injeta; <= a·A)", S),
                 col(f"{u}|vertimento_kW", "kW", "intervalo", "vertimento = a·A − P_R (potência disponível não "
                     "aproveitada)", D),
                 col(f"{u}|E_aproveitada_acum_kWh", "kWh", "intervalo (acumulado no fim)", "energia aproveitada acumulada "
                     "até o fim do intervalo (Σ P_R·Δ)", D)]
    for u in cx["gers"]:
        ints += [col(f"{u}|u", "0/1", "intervalo", f"commitment APLICADO da unidade PEMFC {u}", S),
                 col(f"{u}|p_kW", "kW", "intervalo", "potência líquida SOLICITADA/aplicada pelo EMS (>= 0; injeta)", S),
                 col(f"{u}|partida", "0/1", "intervalo", "partida (u_t = 1 e u_{t−1} = 0; u_{−1} = estado inicial)", D),
                 col(f"{u}|parada", "0/1", "intervalo", "parada (u_t = 0 e u_{t−1} = 1)", D),
                 col(f"{u}|q_h2_kg_h", "kg/h", "intervalo", "vazão de H₂ SUPRIDO prevista pela curva PWL certificada", D),
                 col(f"{u}|m_h2_kg", "kg", "intervalo", "massa de H₂ = q·Δt + m_SU·partida + m_SD·parada", D),
                 col(f"{u}|m_h2_acum_kg", "kg", "intervalo (acumulado no fim)", "massa de H₂ acumulada", D),
                 col(f"{u}|custo_h2_R", "R$", "intervalo", "c_H × massa de H₂ (termo combustivel_h2)", D),
                 col(f"{u}|custo_eventos_R", "R$", "intervalo", "C_SU·partida + C_SD·parada (termo eventos)", D)]
    fr = [col("fronteira", "", "fronteira", "índice GLOBAL k da fronteira de estado (N + 1 fronteiras)", S)]
    for b in cx["bats"]:
        fr += [col(f"{b}|energia_kWh", "kWh", "fronteira", f"energia armazenada EXECUTADA do banco {b}", S),
               col(f"{b}|soc", "1", "fronteira", "energia / capacidade C_b (fração)", D)]
    jan = [col("objetivo_R", "R$", "janela", "objetivo do MILP da janela (inclui custo futuro estimado; NÃO é custo)", S),
           col("limite_dual_R", "R$", "janela", "limite dual (bound) do HiGHS", S),
           col("gap_rel", "1", "janela", "gap relativo de otimalidade reportado", S),
           col("custo_operativo_previsto_janela_R", "R$", "janela", "termos operativos do objetivo na janela (previsão)", S),
           col("custo_futuro_estimado_R", "R$", "janela", "V̂ na fronteira terminal da janela (instrumento de decisão)", S),
           col("realizado_R", "R$", "janela", "custo REALIZADO nos intervalos aplicados da janela", S),
           col("sinal_situacao", "", "janela", "valido × degradado_* × indisponivel_interrompe × sem_coordenacao", S),
           col("tempo_*_s", "s", "janela", "tempos de relógio medidos (não reprodutíveis)", S)]
    pl = [col("aplicado", "0/1", "intervalo do plano", "1 = intervalo do plano efetivamente APLICADO (prefixo m_k)", S),
          col("plano:<uid>|<grandeza>", "kW", "intervalo do plano", "consigna PLANEJADA (não é execução)", S),
          col("plano:<uid>|e_inicio / e_fim", "kWh", "fronteiras do plano", "energia PLANEJADA nas fronteiras do intervalo", S)]
    if cx["rens"]:
        pl.append(col("plano:<uid>|A_prevista_kW", "kW", "intervalo do plano", "potencial renovável UTILIZÁVEL previsto "
                      "entregue à janela (previsão, não realização)", S))
    return {N_INTERVALOS: ints, N_FRONTEIRAS: fr, N_JANELAS: jan, N_PLANOS: pl}


PAPEIS = {
    N_SELADOS: ("fonte_canonica", "Registros selados da missão (texto canônico exato; cadeia de hashes do motor)"),
    N_MODELO: ("fonte_canonica", "Modelo 3C-3 da missão e configurações (parâmetros efetivos com procedência por campo)"),
    N_INTERVALOS: ("vista_derivada", "Um registro por intervalo APLICADO: demanda, baterias, PCC, tarifas, custos"),
    N_FRONTEIRAS: ("vista_derivada", "Um registro por fronteira de estado (N + 1): energia e SOC por banco"),
    N_JANELAS: ("vista_derivada", "Uma linha por janela MPC: solver, gap, custos, sinal de valor futuro, tempos"),
    N_PLANOS: ("vista_derivada", "Plano de cada janela × intervalo do horizonte (previsto × aplicado)"),
    N_COORD: ("vista_derivada", "Coordenações 3C-4 por janela: sinal V(E), modos, domínio, qualidade, degradação"),
    N_AUDITORIA: ("auditoria", "Auditoria integral independente da missão (sem solver)"),
    N_PREFLIGHT: ("contexto", "Preflight V2 e matriz fonte → transformação → validação → registro → vista"),
    N_PEMFC: ("contexto", "Curva q(P) da PEMFC derivada do modelo físico (inicialização, pontos do modelo, vértices, erros) "
                          "e certificado B04 do núcleo; comprometido no manifesto antes da execução"),
    N_PEMFC_DIN: ("verificacao", "Consignas aplicadas avaliadas a posteriori pelo modelo dinâmico da PEMFC (potência "
                                 "solicitada × entregue, H₂ do modelo × H₂ da PWL, estados, tolerâncias)"),
    N_RENOV: ("contexto", "Potencial renovável por UID derivado pelos modelos físicos do SEEDS2 (parâmetros, clima, "
                          "hipóteses, séries); conferido contra a previsão e a realização seladas"),
}


def indice_doc(ev: Evidencia, data: dict[str, tuple[bytes, str]], run_uid: str, fuso: str | None, origem: dict) -> dict:
    malha = ev.cfg.malha
    return {
        "formato": FORMATO, "versao": VERSAO, "motor": E.MOTOR_V2, "run_uid": run_uid, "missao_uid": ev.missao_uid,
        "origem": origem,
        "malha": {"inicio_utc": malha.inicio().isoformat(), "delta_s": malha.delta_s, "intervalos_missao": malha.intervalos_missao,
                  "N": malha.intervalos_otimizacao, "m": malha.intervalos_reotimizacao,
                  "H_L": ev.configuracao_planejador.horizonte_longo_intervalos, "fuso_apresentacao": fuso},
        "situacao_missao": ev.registro_missao.conteudo.desfecho,
        "arquivos": {n: {"papel": PAPEIS[n][0], "descricao": PAPEIS[n][1], "sha256": _sha(b), "bytes": len(b),
                         "media_type": mt} for n, (b, mt) in sorted(data.items())},
        "colunas": _dicionario(ev), "convencoes": dict(CONVENCOES), "limitacoes": list(LIMITACOES),
        "selos": {"registro_missao": ev.registro_missao.selo,
                  "registro_rede": None if ev.registro_rede is None else ev.registro_rede.selo,
                  "registro_hierarquico": None if ev.registro_hierarquico is None else ev.registro_hierarquico.selo},
    }


def dados_da_rodada(ev: Evidencia, cfg_mpc, auditoria, preflight_doc: dict, run_uid: str, fuso: str | None,
                    origem: dict, renovaveis_doc: dict | None = None, pemfc_doc: dict | None = None,
                    pemfc_dinamica_doc: dict | None = None) -> dict[str, tuple[bytes, str]]:
    """Todos os itens de ``scenario_run_data`` de uma rodada V2 concluída (nome → (bytes, media type))."""
    J, C_, Z = "application/json", "text/csv", "application/zip"
    data: dict[str, tuple[bytes, str]] = {
        N_SELADOS: (empacotar(ev.textos), Z),
        N_MODELO: (_json(modelo_doc(ev.modelo, cfg_mpc, ev.configuracao_rede, ev.configuracao_planejador)), J),
        N_AUDITORIA: (_json(auditoria_doc(auditoria)), J),
        N_PREFLIGHT: (_json(preflight_doc), J),
    }
    if ev.modelo.base.renovaveis:
        if renovaveis_doc is None:
            raise IntegridadeV2Error("Modelo com renováveis sem o documento de derivação do potencial (v2/renovaveis.json).")
        data[N_RENOV] = (_json(renovaveis_doc), J)
    if ev.modelo.base.geradores:
        if pemfc_doc is None or pemfc_dinamica_doc is None:
            raise IntegridadeV2Error("Modelo com PEMFC sem a curva/certificado (v2/pemfc.json) ou a verificação dinâmica.")
        data[N_PEMFC] = (_json(pemfc_doc), J)
        data[N_PEMFC_DIN] = (_json(pemfc_dinamica_doc), J)
    for nome, b in vistas(ev, fuso).items():
        data[nome] = (b, J if nome.endswith(".json") else C_)
    data[N_INDICE] = (_json(indice_doc(ev, data, run_uid, fuso, origem)), J)
    return data


def evidencia_parcial_doc(ev: Evidencia, cfg_mpc, auditoria, fuso: str | None, renovaveis_doc: dict | None = None,
                          pemfc_doc: dict | None = None) -> dict:
    """Evidência de uma missão NÃO concluída, para o ``outcome`` da rodada (rotulada parcial; mesmos textos canônicos)."""
    def tabela(cols, linhas):
        return {"colunas": cols, "linhas": [[ln.get(c) for c in cols] for ln in linhas]}
    v: dict = {}
    for nome, fn in (("intervalos", lambda: linhas_intervalos(ev, fuso)), ("fronteiras", lambda: linhas_fronteiras(ev, fuso)),
                     ("janelas", lambda: linhas_janelas(ev)), ("planos", lambda: linhas_planos(ev))):
        try:
            v[nome] = tabela(*fn())
        except IntegridadeV2Error as exc:
            v[nome] = {"erro": str(exc)}
    return {"formato": FORMATO, "versao": VERSAO, "parcial": True,
            "aviso": "Missão NÃO concluída: os valores cobrem só os intervalos aplicados antes da interrupção. O custo "
                     "parcial não é custo da missão nem é comparável ao de uma missão completa.",
            "selados": dict(ev.textos),
            "modelo": modelo_doc(ev.modelo, cfg_mpc, ev.configuracao_rede, ev.configuracao_planejador),
            "vistas": v, "coordenacoes": [para_dict(co) for co in ev.coordenacoes],
            "renovaveis": renovaveis_doc, "pemfc": pemfc_doc,
            "auditoria": None if auditoria is None else auditoria_doc(auditoria)}


# ====================================================================== reabertura (sem otimizador)
@dataclass
class Verificacao:
    ok: bool
    itens: list[tuple[bool, str]]
    evidencia: Evidencia | None = None
    auditoria: dict | None = None

    def falhas(self) -> list[str]:
        return [t for ok, t in self.itens if not ok]


def e_v2(run) -> bool:
    return isinstance(run.manifest, dict) and (run.manifest.get("engine") or {}).get("id") == E.MOTOR_V2


def ler_json(source, run, nome: str):
    try:
        return json.loads(source.run_data(run.run_uid, nome).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise IntegridadeV2Error(f"Dado '{nome}' da rodada ilegível.") from None


def ler_csv(source, run, nome: str):
    import pandas as pd

    return pd.read_csv(io.BytesIO(source.run_data(run.run_uid, nome)))


def _fuso(run) -> str | None:
    return ((run.manifest.get("mission") or {}).get("timezone")) if isinstance(run.manifest, dict) else None


def verificar(source, run) -> Verificacao:
    """Reabre e VERIFICA uma rodada V2 finalizada a partir do que está gravado (local ou estudo arquivado). Não chama o
    otimizador nem importa Pyomo/HiGHS: hashes, identidade, reconstrução dos registros selados, vistas regeneradas
    byte a byte, resumo e auditoria integral independente."""
    itens: list[tuple[bool, str]] = []

    def ver(cond: bool, texto: str) -> bool:
        itens.append((bool(cond), texto))
        return bool(cond)
    if not e_v2(run):
        return Verificacao(False, [(False, "A rodada não é do motor V2.")])
    try:
        if run.state != "concluida":
            return _verificar_parcial(run, itens, ver)
        falt = [n for n in OBRIGATORIOS if n not in run.data]
        if not ver(not falt, "Todos os dados obrigatórios da rodada V2 presentes" + (f" — AUSENTES: {falt}" if falt else "")):
            return Verificacao(False, itens)
        brutos = {n: source.run_data(run.run_uid, n) for n in run.data}      # SHA-256 de cada item conferido na leitura
        ver(True, f"{len(brutos)} itens lidos com SHA-256 conferido contra o registro da rodada")
        ind = json.loads(brutos[N_INDICE].decode("utf-8"))
        arqs = ind.get("arquivos") or {}
        ver(ind.get("formato") == FORMATO and ind.get("versao") in VERSOES_LEGIVEIS and ind.get("run_uid") == run.run_uid,
            f"Índice no formato esperado (versão {ind.get('versao')!r}) e vinculado a esta rodada")
        ver(set(arqs) == set(brutos) - {N_INDICE} and all(arqs[n]["sha256"] == _sha(brutos[n]) for n in arqs if n in brutos),
            "Índice lista exatamente os itens gravados, com os mesmos SHA-256")
        _pemfc_registrar(run, brutos.get(N_PEMFC), ver)
        ev = evidencia_de_textos(desempacotar(brutos[N_SELADOS]), json.loads(brutos[N_MODELO].decode("utf-8")), run.run_uid)
        _identidade(run, ev, ver)
        _renovaveis_verificar(run, ev, brutos, ind.get("versao"), ver)
        _pemfc_verificar(run, ev, brutos, ind.get("versao"), ver)
        fuso = _fuso(run)
        regen = vistas(ev, fuso)
        dif = [n for n in VISTAS if regen[n] != brutos[n]]
        ver(not dif, "Vistas derivadas regeneradas dos registros selados são idênticas byte a byte às gravadas"
            + (f" — DIFEREM: {dif}" if dif else ""))
        res = json.loads(json.dumps(resumo(ev, fuso), allow_nan=False))
        ver(res == (run.summary or {}).get("mission"), "Resumo gravado = resumo recalculado dos registros selados")
        rel = auditar(ev)
        ad = auditoria_doc(rel)
        ver(rel.aceito, "Auditoria integral independente (sem solver) APROVADA na reabertura"
            + ("" if rel.aceito else f" — reprovada: {sorted(rel.codigos())[:5]}"))
        grav = json.loads(brutos[N_AUDITORIA].decode("utf-8"))
        ver(grav.get("aceito") is True and grav.get("verificacoes") == ad["verificacoes"],
            "Veredito da auditoria gravada na execução coincide com a reauditoria")
        ver(ev.registro_missao.conteudo.desfecho == "concluida"
            and ev.registro_missao.conteudo.intervalos_aplicados == ev.registro_missao.conteudo.K_M,
            "Missão completa: todos os intervalos aplicados (estado 'concluída' coerente)")
        return Verificacao(all(ok for ok, _ in itens), itens, ev, ad)
    except (IntegridadeV2Error, StoreError) as exc:
        itens.append((False, str(exc)))
    except Exception as exc:                           # noqa: BLE001 — evidência ilegível: falha controlada
        itens.append((False, f"Evidência ilegível: {type(exc).__name__}: {str(exc)[:200]}"))
    return Verificacao(False, itens)


def _identidade(run, ev: Evidencia, ver) -> None:
    i = ev.cfg.identidade
    ver(i.missao_uid == run.run_uid, "missao_uid dos registros selados = run_uid da rodada")
    ver((i.microrrede_uid, i.cenario_uid, i.versao_cenario, i.impressao_cenario, i.revisao_config, i.impressao_config)
        == (run.microgrid_uid, run.scenario_uid, run.scenario_version, run.scenario_fingerprint, run.config_revision,
            run.config_fingerprint),
        "Microrrede, cenário/versão/impressão e revisão/impressão do inventário dos registros = os da rodada")
    ver(i.incarnacao in (None, run.incarnation) or run.incarnation is None,
        "Incarnação da microrrede coerente entre registros selados e rodada")
    h = ((run.manifest.get("engine_inputs") or {}).get("hashes")) or {}
    ver(h.get("modelo_rede_3c3") == hash_entrada_3c3(ev.modelo)
        and h.get("configuracao_rede") == hash_configuracao_rede(ev.configuracao_rede)
        and h.get("configuracao_planejador") == hash_configuracao_planejador(ev.configuracao_planejador),
        "Modelo e configurações gravados têm os hashes comprometidos no manifesto ANTES da execução")
    rh = ev.registro_hierarquico
    ver(rh is not None and rh.hash_modelo_rede == h.get("modelo_rede_3c3") and rh.selo_registro_missao == ev.registro_missao.selo,
        "Registro hierárquico selado vincula o modelo e o registro de missão")


def _renovaveis_verificar(run, ev: Evidencia, brutos: dict, versao, ver) -> None:
    """Potencial renovável persistido × manifesto × previsão e realização SELADAS (nenhum modelo é reexecutado)."""
    rens = [str(r.uid) for r in ev.modelo.base.renovaveis]
    if not rens:
        ver(N_RENOV not in brutos, "Modelo sem renováveis e sem documento de derivação renovável")
        return
    if not ver(versao in (2, 3) and N_RENOV in brutos,
               "Modelo com renováveis: documento v2/renovaveis.json presente (versão >= 2)"):
        return
    h = ((run.manifest.get("engine_inputs") or {}).get("hashes")) or {}
    try:
        doc = json.loads(brutos[N_RENOV].decode("utf-8"))
        from . import renovaveis as RN               # só biblioteca padrão + numpy/pandas; nenhum modelo é chamado
        ver(RN.sha_documento(doc) == h.get("renovaveis"),
            "Derivação renovável gravada = a comprometida no manifesto ANTES da execução (SHA-256)")
        serie = {x["uid"]: [float(v) for v in x["potencial_kW"]] for x in doc["recursos"]}
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        ver(False, "Documento de derivação renovável ilegível")
        return
    ver(sorted(serie) == sorted(rens), "Recursos renováveis do documento = os do modelo selado (por UID)")
    prev_ok, real_ok = True, True
    for r in ev.registros:
        c = r.conteudo
        k0 = c.janela.k
        for u in rens:
            s = c.previsao.serie(u, "potencia") if c.previsao is not None else None
            if s is not None and list(map(float, s.serie.valores)) != serie.get(u, [])[k0:k0 + len(s.serie.valores)]:
                prev_ok = False
        for p in c.passos:
            for u in rens:
                if float(p.entorno_observado[f"{u}|potencia"]) != serie.get(u, [None] * (p.indice_global + 1))[p.indice_global]:
                    real_ok = False
    ver(prev_ok, "Potencial PREVISTO entregue a cada janela = série derivada gravada (bit a bit)")
    tipo = (doc.get("realizacao") or {}).get("tipo")
    ver(tipo == "igual_a_previsao" and real_ok,
        "Potencial REALIZADO observado na conciliação = série derivada declarada como realização (bit a bit)")


def _pemfc_registrar(run, bruto, ver) -> dict | None:
    """Re-registra os certificados B04 persistidos ANTES da auditoria (que revalida a entrada): o contrato RECOMPUTA os
    critérios a partir destes dados — nenhum modelo é reexecutado e um rótulo/hash sozinho não basta."""
    if bruto is None:
        return None
    from ems_v2 import contracts as K
    try:
        doc = json.loads(bruto.decode("utf-8")) if isinstance(bruto, bytes) else bruto
        h_man = (((run.manifest.get("engine_inputs") or {}).get("hashes")) or {}).get("pemfc")
        from . import renovaveis as RN
        ver(RN.sha_documento(doc) == h_man, "Curva/certificado PEMFC gravados = os comprometidos no manifesto ANTES da "
                                            "execução (SHA-256)")
        oks = []
        for uid, x in doc["registros"].items():
            cert = K.de_dict(K.CertificadoB04, x["certificado_b04"], "CertificadoB04")
            h, cs = K.registrar_certificado_b04(cert)
            oks.append(not [c for c in cs if c.severidade in ("erro", "pendente")] and h == x["hash_certificado_b04"]
                       and [list(v) for v in cert.vertices] == x["curva"]["vertices_kW_kg_h"])
        ver(all(oks), f"Certificado(s) B04 re-registrado(s) com critérios RECOMPUTADOS dos dados gravados ({len(oks)})")
        return doc
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        ver(False, f"Curva/certificado PEMFC ilegíveis: {type(exc).__name__}")
        return None


def _pemfc_verificar(run, ev: Evidencia, brutos: dict, versao, ver) -> None:
    gers = {str(g.uid): g for g in ev.modelo.base.geradores}
    if not gers:
        ver(N_PEMFC not in brutos and N_PEMFC_DIN not in brutos, "Modelo sem PEMFC e sem documentos PEMFC")
        return
    if not ver(versao == 3 and N_PEMFC in brutos and N_PEMFC_DIN in brutos,
               "Modelo com PEMFC: v2/pemfc.json e v2/pemfc_dinamica.json presentes (versão 3)"):
        return
    try:
        doc = json.loads(brutos[N_PEMFC].decode("utf-8"))
        din = json.loads(brutos[N_PEMFC_DIN].decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        ver(False, "Documentos PEMFC ilegíveis")
        return
    reg_v = {u: [tuple(v) for v in x["curva"]["vertices_kW_kg_h"]] for u, x in doc["registros"].items()}
    ok = all(tuple((float(a), float(b)) for a, b in g.curva_h2.vertices) == tuple(reg_v.get(u.split("#")[0], ()))
             for u, g in gers.items())
    ver(ok, "Curva de cada unidade no modelo selado = curva certificada gravada (mesma curva para toda a missão)")
    aplicados = {}
    for r in ev.registros:
        for p in r.conteudo.passos:
            for u in gers:
                aplicados.setdefault(u, {})[p.indice_global] = (int(float(p.aplicado[f"{u}|u"]) > 0.5),
                                                                float(p.aplicado[f"{u}|p"]))
    ok = True
    for u, v in (din.get("unidades") or {}).items():
        for x in v["intervalos"]:
            uu, pp = aplicados.get(u, {}).get(x["intervalo"], (None, None))
            ok &= x["u"] == uu and (x["p_solicitada_kW"] == (pp if uu else 0.0))
    ver(ok and set(din.get("unidades") or {}) == set(gers),
        "Verificação dinâmica gravada avalia EXATAMENTE as consignas aplicadas seladas (por unidade e intervalo)")
    # Auditoria do PR #23 (A/B): H₂ do EMS na verificação = contabilidade SELADA do MILP (q̂·Δ·u + m_SU·y + m_SD·z, coluna
    # m_h2_kg das vistas regeneradas), coerência RECALCULADA dos números e das tolerâncias gravados, e o rótulo de aceitação
    # do resumo = o recalculado (uma rodada dinamicamente incoerente não pode ser apresentada como coerente).
    from .pemfc_dinamica import reavaliar_coerencia
    try:
        _cols, ints = linhas_intervalos(ev, None)
        por_g = {int(x["intervalo"]): x for x in ints}
        ok_m = all(_proximo(float(x["h2_ems_kg"]), float(por_g[x["intervalo"]][f"{u}|m_h2_kg"]))
                   for u, v in din["unidades"].items() for x in v["intervalos"])
        tol = din.get("tolerancias") or {}
        coer = {}
        ok_c = True
        for u, v in din["unidades"].items():
            c_u, inc = reavaliar_coerencia(v, tol)
            coer[u] = c_u
            ruins = {(i["intervalo"], i["criterio"]) for i in inc}
            ok_c &= c_u == bool(v["coerente"]) and all(
                x["coerente_energia"] == ((x["intervalo"], "energia") not in ruins)
                and x["coerente_h2"] == ((x["intervalo"], "h2") not in ruins) for x in v["intervalos"])
        ok_c &= bool(din.get("coerente")) == all(coer.values())
    except (KeyError, TypeError, ValueError) as exc:
        ver(False, f"Verificação dinâmica gravada ilegível: {type(exc).__name__}")
        return
    ver(ok_m, "H₂ do EMS na verificação dinâmica = contabilidade SELADA do MILP por intervalo (contínuo + massas por evento)")
    from .pemfc_dinamica import subestimacao_h2
    resumo_din = (((run.summary or {}).get("execution") or {}).get("pemfc_dinamica")) or {}
    ok_s = True
    for u, v in din["unidades"].items():
        sub = subestimacao_h2(v["intervalos"])
        for k in ("h2_subestimacao_max_kg", "h2_subestimacao_total_kg"):
            ok_s &= k not in v or (_proximo(float(v[k]), sub[k])
                                   and _proximo(float((resumo_din.get(u) or {}).get(k, sub[k])), sub[k]))
    ver(ok_s, "Subestimação de H₂ do EMS frente ao modelo dinâmico RECALCULADA dos intervalos gravados = a declarada")
    ver(ok_c, "Coerência dinâmica RECALCULADA dos valores e tolerâncias gravados = a gravada (por unidade e intervalo)")
    acc = (((run.summary or {}).get("execution") or {}).get("aceitacao")) or {}
    todas = all(coer.values())
    esperado = "algebrica_aprovada_dinamica_coerente" if todas else "algebrica_aprovada_dinamica_incoerente"
    ver(acc.get("classificacao") == esperado and (acc.get("dinamica") or {}).get("estado") == (
        "coerente" if todas else "incoerente") and (acc.get("fisica") or {}).get("estado") == "nao_validada"
        and (acc.get("algebrica") or {}).get("estado") == "aprovada",
        f"Aceitação SEPARADA no resumo = recalculada: algébrica aprovada · dinâmica {'coerente' if todas else 'INCOERENTE'}"
        " · física não validada")


def _verificar_parcial(run, itens, ver) -> Verificacao:
    evd = (run.outcome or {}).get("evidence")
    if not isinstance(evd, dict) or not evd.get("selados"):
        ver(not run.data, "Rodada sem resultados gravados (nenhum dado de rodada não concluída)")
        ver(True, "Sem evidência de missão: a falha ocorreu antes de qualquer janela (ver o diagnóstico da rodada)")
        return Verificacao(all(ok for ok, _ in itens), itens)
    ver(evd.get("parcial") is True and not run.data, "Evidência rotulada PARCIAL e fora dos dados de rodada concluída")
    if evd.get("pemfc"):
        _pemfc_registrar(run, evd["pemfc"], ver)
    ev = evidencia_de_textos(dict(evd["selados"]), evd["modelo"], run.run_uid)
    _identidade(run, ev, ver)
    rm = ev.registro_missao.conteudo
    ver(not (rm.desfecho == "concluida" and rm.intervalos_aplicados == rm.K_M),
        f"Missão NÃO completa nos registros selados ({rm.intervalos_aplicados} de {rm.K_M} intervalos; desfecho "
        f"'{rm.desfecho}', classe '{rm.classe_falha}')")
    rel = auditar(ev)
    ad = auditoria_doc(rel)
    ver(rel.aceito, "Auditoria integral independente da evidência parcial APROVADA"
        + ("" if rel.aceito else f" — reprovada: {sorted(rel.codigos())[:5]}"))
    return Verificacao(all(ok for ok, _ in itens), itens, ev, ad)


__all__ = ["CONVENCOES", "Evidencia", "FORMATO", "IntegridadeV2Error", "LIMITACOES", "N_AUDITORIA", "N_COORD",
           "N_FRONTEIRAS", "N_INDICE", "N_INTERVALOS", "N_JANELAS", "N_MODELO", "N_PEMFC", "N_PEMFC_DIN", "N_PLANOS",
           "N_PREFLIGHT", "N_RENOV",
           "N_SELADOS", "OBRIGATORIOS", "VERSAO", "VERSOES_LEGIVEIS", "VISTAS", "Verificacao", "auditar", "auditoria_doc", "dados_da_rodada",
           "desempacotar", "e_v2", "empacotar", "evidencia_de_textos", "evidencia_do_resultado", "evidencia_parcial_doc",
           "ler_csv", "ler_json", "linhas_fronteiras", "linhas_intervalos", "linhas_janelas", "linhas_planos", "modelo_doc",
           "resumo", "textos_selados", "verificar", "vistas"]
_ = replace
