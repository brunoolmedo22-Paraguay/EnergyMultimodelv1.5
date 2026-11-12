"""Apoio dos testes do Piso 3D-B (sem testes): missões V2 reais (HiGHS) sobre microrredes FICTÍCIAS do catálogo, um marco
SINTÉTICO para exercitar o JavaScript sem solver e os executores Node/navegador.

Tudo aqui é dado de TESTE, sintético e rotulado. A microrrede (FV + eólica + bateria + PEMFC + PCC) e o cenário reutilizam
os utilitários dos Pisos 3D-A2-R/H; a rodada é executada pelo caminho normal e depois só LIDA pelos testes.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import piso3da2h_util as H
import piso3da2r_util as R
import piso3da_util as U
from integracao_v2 import estrategia as E
from integracao_v2 import execucao as X
from integracao_v2 import registro as RG
from integracao_v2 import trama_frame as TF
from seeds2.microgrid import config as C
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.operation import forecast_sources as FS
from seeds2.operation import service as SV
from seeds2.operation import strategy as SG

SOLVER = importlib.util.find_spec("pyomo") is not None and importlib.util.find_spec("highspy") is not None
GHI = [0, 0, 0, 0, 0, 0, 100, 350, 600, 800, 950, 1000]
VENTO = [2, 3, 9, 10, 11, 12, 12, 10, 4, 3, 2.5, 2]


def missao_hibrida(data_dir: str, nome: str = "Microrrede 3D-B (teste)"):
    """Cria a microrrede, o cenário e executa a missão (12 h). Devolve (uid, store, rodada concluída)."""
    cfg = H.config_pemfc(nome, fv=True, eolica=True)
    MicrogridRegistry(data_dir).create(cfg)
    uid = cfg["installation"]["uid"]
    st = MicrogridRegistry(data_dir).open(uid)
    clima = lambda doc: R.clima_tabela(doc, {"ghi_W_m2": [float(v) for v in GHI], "temperature_C": [20.0] * 12,  # noqa: E731
                                             "wind_speed_m_s": [float(v) for v in VENTO]})
    sc = H.criar_cenario_pemfc(st, demanda_kW=40.0, renov=True, clima=clima, pemfc_kw={"preco": 10.0},
                               mutar=lambda doc: doc[E.CHAVE_BLOCO]["pcc"].update(limite_importacao_kW=25.0))
    run = X.submit(st, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    if run.state != "concluida":
        raise AssertionError(f"missão de teste não concluiu: {run.error}")
    return uid, st, run


# ---------------------------------------------------------------------------------------------- variantes (Piso 3D-B3)
def _abrir(data_dir: str, cfg: dict):
    MicrogridRegistry(data_dir).create(cfg)
    uid = cfg["installation"]["uid"]
    return uid, MicrogridRegistry(data_dir).open(uid)


def _executar(st, sc, versao: int | None = None):
    """Executa pelo caminho normal; ``versao`` grava EXATAMENTE no contrato de dados de um piso anterior (1 ou 2)."""
    atual = RG.VERSAO
    if versao is not None:
        RG.VERSAO = versao
    try:
        run = X.submit(st, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    finally:
        RG.VERSAO = atual
    if run.state != "concluida":
        raise AssertionError(f"missão de teste não concluiu: {run.error}")
    return run


def missao_dois_bancos(data_dir: str, nome: str = "Dois bancos 3D-B (teste)"):
    """Dois bancos de baterias (o máximo do contrato V2) + PCC, 12 h."""
    extra = C.new_equipment("battery", "Banco 02", tag="BAT-02", params={
        "energy_kWh": 30.0, "soc_min_pct": 0.0, "soc_max_pct": 100.0, "soc_limits_source": "instalacao"})
    uid, st = _abrir(data_dir, U.config_bateria(nome, extras=[extra]))
    return uid, st, _executar(st, U.criar_cenario_v2(st, soc0=50.0, demanda_kW=12.0))


def missao_duas_pemfc(data_dir: str, nome: str = "Duas PEMFC 3D-B (teste)"):
    """UM registro PEMFC com DUAS unidades (``eq-…#1`` e ``eq-…#2``) + bateria + PCC, 12 h."""
    uid, st = _abrir(data_dir, H.config_pemfc(nome, quantidade=2))
    return uid, st, _executar(st, H.criar_cenario_pemfc(st, demanda_kW=60.0, pemfc_kw={"preco": 10.0}))


def missao_passo_30(data_dir: str, nome: str = "Passo 30 min 3D-B (teste)"):
    """Malha de 30 min: 6 h = 12 intervalos (demanda sintética de 30 min)."""
    uid, st = _abrir(data_dir, U.config_bateria(nome))
    sc = U.criar_cenario_v2(st, soc0=50.0)
    doc = copy.deepcopy(sc.document)
    doc[E.CHAVE_BLOCO]["malha"]["delta_min"] = 30
    cand = FS.synthetic_candidate("demanda_constante", {"t0": U.INICIO_LOCAL, "step_s": 1800, "duration_s": 6 * 3600,
                                                        "value_kW": 10.0}, timezone="UTC", inventory_ref=doc["inventory_ref"])
    doc["forecasts"]["demand"] = cand.entry
    doc["mission"] = SG.default_mission(U.INICIO_LOCAL, "UTC", 6 * 60)
    return uid, st, _executar(st, SV.save(st, doc, sc.version, new_blobs=cand.blobs))


def missao_24h(data_dir: str, nome: str = "Dia 3D-B (teste)"):
    """24 h, N = 4, m = 2 (12 decisões), tarifa em dois níveis."""
    uid, st = _abrir(data_dir, U.config_bateria(nome))
    sc = U.criar_cenario_v2(st, soc0=50.0, horas=24, N=4, m=2, H_L=8, tarifa=[0.5] * 16 + [1.5] * 4 + [0.5] * 4)
    return uid, st, _executar(st, sc)


def missao_legada_v1(data_dir: str, nome: str = "Legado v1 3D-B (teste)"):
    """Rodada gravada no contrato de dados v1 (Piso 3D-A): sem renováveis, sem PEMFC, sem campos opcionais."""
    uid, st = _abrir(data_dir, U.config_bateria(nome))
    return uid, st, _executar(st, U.criar_cenario_v2(st), versao=1)


def marco(st, run) -> dict:
    return TF.montar(st, run, verificacao=RG.verificar(st, run))


# ------------------------------------------------------------------------------------- marco SINTÉTICO (sem solver)
def marco_sintetico(*, K: int = 6, bancos: int = 1, eolicas: int = 2, pemfc: int = 1, conectado: bool = True) -> dict:
    """Marco ``seeds2-trama-frame`` FICTÍCIO, coerente por construção, para exercitar o JavaScript sem solver nem
    missão: números redondos de teste (não são resultado de microrrede). Balanço: eólica + FV + descarga + PEMFC +
    importação = demanda + carga."""
    fl = lambda v: [float(x) for x in v]  # noqa: E731
    it = list(range(K))
    wt = [f"eq-wt{n}" for n in range(1, eolicas + 1)]
    bt = [f"eq-bat{n}" for n in range(1, bancos + 1)]
    fc = [f"eq-fc#{n}" for n in range(1, pemfc + 1)]
    ren = {u: {"tecnologia": "eolica", "A_prevista_kW": fl([10] * K), "A_observada_kW": fl([10] * K),
               "A_utilizavel_kW": fl([10] * K), "P_R_kW": fl([8] * K), "vertimento_kW": fl([2] * K),
               "E_aproveitada_acum_kWh": fl([8 * (i + 1) for i in it]),
               "resumo": {"energia_aproveitada_kWh": 8.0 * K, "energia_utilizavel_kWh": 10.0 * K,
                          "energia_vertida_kWh": 2.0 * K, "pico_aproveitado_kW": 8.0},
               "modelo": "modelo de teste", "parametros": {}, "diagnostico": {}} for u in wt}
    ren["arr-fv1"] = {"tecnologia": "fv", "A_prevista_kW": fl([4] * K), "A_observada_kW": fl([4] * K),
                      "A_utilizavel_kW": fl([4] * K), "P_R_kW": fl([4] * K), "vertimento_kW": fl([0] * K),
                      "E_aproveitada_acum_kWh": fl([4 * (i + 1) for i in it]), "resumo": {}, "modelo": "modelo de teste",
                      "parametros": {}, "diagnostico": {}}
    bat = {u: {"P_c_kW": fl([0] * K), "P_d_kW": fl([1] * K), "energia_kWh": fl([20 - i for i in range(K + 1)]),
               "soc": fl([(20 - i) / 20 for i in range(K + 1)]),
               "resumo": {"capacidade_kWh": 20.0, "energia_inicial_kWh": 20.0, "energia_final_kWh": 20.0 - K,
                          "energia_carregada_kWh": 0.0, "energia_descarregada_kWh": float(K), "soc_inicial": 1.0,
                          "soc_final": (20 - K) / 20},
               "declaracao": {"p_carga_barramento_kW": 5.0, "p_descarga_barramento_kW": 5.0, "eta_carga": 1.0,
                              "eta_descarga": 1.0, "custo_throughput_R_kWh": 0.01}} for u in bt}
    pem = {u: {"registro": "eq-fc", "u": fl([1] * K), "p_kW": fl([10] * K), "partida": fl([0] * K), "parada": fl([0] * K),
               "q_h2_kg_h": fl([0.6] * K), "m_h2_kg": fl([0.6] * K), "m_h2_acum_kg": fl([0.6 * (i + 1) for i in it]),
               "custo_h2_R": fl([6] * K), "custo_eventos_R": fl([0] * K), "dinamica": None, "curva": None,
               "declaracao": {"p_min_kW": 10.0, "preco_h2_R_kg": 10.0}, "massas_eventos": {}, "resumo": {},
               "resumo_dinamica": {}} for u in fc}
    inj = 8.0 * eolicas + 4.0 + 1.0 * bancos + 10.0 * pemfc
    imp = 5.0 if conectado else 0.0
    dem = inj + imp
    cimp, ch2, cthr = 0.5 * imp, 6.0 * pemfc, 0.01 * bancos
    cint = cimp + ch2 + cthr
    inter = {"janela": fl([i // 2 for i in it]), "indice_no_plano": fl([i % 2 for i in it]),
             "demanda_prevista_kW": fl([dem] * K), "demanda_realizada_kW": fl([dem] * K),
             "demanda_nao_atendida_kW": fl([0] * K), "demanda_atendida_kW": fl([dem] * K),
             "custo_throughput_R": fl([cthr] * K), "custo_realizado_intervalo_R": fl([cint] * K),
             "custo_realizado_acumulado_R": fl([cint * (i + 1) for i in it]), "residuo_balanco_kW": fl([0] * K)}
    if conectado:
        inter.update({"pcc_importacao_programada_kW": fl([imp] * K), "pcc_importacao_realizada_kW": fl([imp] * K),
                      "pcc_exportacao_programada_kW": fl([0] * K), "pcc_exportacao_realizada_kW": fl([0] * K),
                      "tarifa_importacao_decisao_R_kWh": fl([0.5] * K), "preco_importacao_liquidacao_R_kWh": fl([0.5] * K),
                      "custo_importacao_R": fl([cimp] * K), "receita_exportacao_R": fl([0] * K),
                      "custo_desvio_rede_R": fl([0] * K)})
    jan, planos, coords = [], [], []
    for j in range(K // 2):
        k, n = 2 * j, min(4, K - 2 * j)
        valido = j % 2 == 1
        jan.append({"j": float(j), "k": float(k), "Nk": float(n), "mk": 2.0, "ap": 2.0, "classe": "otimo",
                    "terminacao": "teste", "objetivo": cint * n, "limite_dual": cint * n, "gap_rel": 0.0,
                    "variaveis": 10.0, "binarias": 2.0, "restricoes": 8.0, "custo_operativo_previsto": cint * n,
                    "custo_futuro_estimado": 0.0 if valido else None, "planejado_prefixo": cint * 2, "realizado": cint * 2,
                    "sinal_situacao": "valido" if valido else "degradado_sem_valor_futuro",
                    "sinal_qualidade": "valido" if valido else "indisponivel",
                    "sinal_motivo": "" if valido else "tolerância de interpolação não atingida (teste)",
                    "sinal_fronteira": float(k + n), "termo_terminal": "sinal_valor_futuro" if valido else "nenhum_declarado"})
        series = {f"{u}|P_R": fl([8] * n) for u in wt} | {"arr-fv1|P_R": fl([4] * n)} | {f"{u}|p": fl([10] * n) for u in fc}
        for u in bt:
            series |= {f"{u}|P_d": fl([1] * n), f"{u}|P_c": fl([0] * n), f"{u}|e_inicio": fl([20 - k - i for i in range(n)]),
                       f"{u}|e_fim": fl([19 - k - i for i in range(n)])}
        if conectado:
            series |= {"pcc_importacao_programada_kW": fl([imp] * n), "pcc_exportacao_programada_kW": fl([0] * n)}
        planos.append({"janela": float(j), "intervalo": fl(range(k, k + n)), "aplicado": fl([1, 1] + [0] * (n - 2)),
                       "demanda_prevista_kW": fl([dem] * n), "series": series})
        modos = [{"indice": 0, "geradores": [{"uid": u, "ligado": False, "obrigacao_residual_s": 0,
                                              "potencia_fixada_kW": None} for u in fc],
                  "representacao": "teste", "energias_inviaveis": [], "dominio_min_kWh": [0.0] * bancos,
                  "dominio_max_kWh": [20.0] * bancos, "convexidade_verificada_na_amostra": True,
                  "pontos": [{"energias_kWh": [e] * bancos, "valor_R": 20.0 - e, "limite_inferior_R": 20.0 - e,
                              "classificacao": "otimo"} for e in (0.0, 10.0, 20.0)]}]
        coords.append({"posicao": j, "janela": j, "k": k, "situacao": jan[-1]["sinal_situacao"],
                       "origem_sinal": "planejado_nesta_janela", "motivo": jan[-1]["sinal_motivo"],
                       "termo_aplicado": jan[-1]["termo_terminal"], "tempos_s": {},
                       "decomposicao": {"modo": 0 if valido else None, "objetivo_total_R": cint * n,
                                        "energias_fronteira_kWh": {u: float(20 - k - n) for u in bt}},
                       "sinal": {"tipo": "custo_futuro_pwl", "indice_fronteira": k + n, "baterias": list(bt),
                                 "geradores": list(fc), "referencia": {"energias_kWh": [10.0] * bancos, "origem": "plano_longo"},
                                 "qualidade": {"estado": jan[-1]["sinal_qualidade"], "motivo": jan[-1]["sinal_motivo"],
                                               "erro_interpolacao_max_R": 0.0 if valido else 0.5,
                                               "tolerancia_interpolacao_R": 1e-6, "avaliacoes": 7,
                                               "validacoes": [{"energias_kWh": [5.0] * bancos, "modo": 0,
                                                               "valor_reotimizado_R": 15.0, "valor_aproximado_R": 15.0,
                                                               "erro_R": 0.0}]},
                                 "modos": modos},
                       "plano_longo": {"k": k, "indice_fim": K, "classificacao": "otimo", "objetivo_R": cint * (K - k),
                                       "energias_kWh": {u: fl([20 - i for i in range(k, K + 1)]) for u in bt},
                                       "compromisso": {}, "potencias_kW": {}}})
    f = {"formato": TF.FORMATO, "versao": TF.VERSAO,
         "rodada": {"uid": "0" * 31 + "a", "estado": "concluida", "cenario": "Marco sintético de teste", "versao_cenario": 1,
                    "microrrede_uid": "m" * 32, "revisao_inventario": 1, "motor": "milp_mpc_v1", "versao_dados": 3, "N": 4,
                    "m": 2, "H_L": K, "delta_min": 60.0, "K": K, "fuso": "UTC", "sintetico": True, "contexto": "ensaio"},
         "fronteiras": {"indice": list(range(K + 1)), "utc": [f"2026-01-01T{h:02d}:00:00+00:00" for h in range(K + 1)],
                        "local": [f"2026-01-01T{h:02d}:00:00" for h in range(K + 1)]},
         "intervalos": inter,
         "recursos": {"fv": [{"uid": "arr-fv1", "nome": "Arranjo de teste", "tag": None}],
                      "wt": [{"uid": u, "nome": f"Aerogerador {n + 1}", "tag": None} for n, u in enumerate(wt)],
                      "bat": [{"uid": u, "nome": f"Banco {n + 1}", "tag": f"BAT-0{n + 1}"} for n, u in enumerate(bt)],
                      "fc": [{"uid": u, "nome": f"PEMFC unidade {n + 1}", "tag": None} for n, u in enumerate(fc)]},
         "renovaveis": ren, "baterias": bat, "pemfc": pem,
         "pcc": {"modo": "conectado" if conectado else "isolado_declarado", "sentidos": "somente_importacao",
                 "limite_importacao_kW": 8.0 if conectado else None, "limite_exportacao_kW": None, "ajuste": "teste",
                 "rotulo_tarifa": "SINTÉTICA — teste", "procedencia": "sintetico"},
         "demanda": {"criticidade": "critica", "semantica": "media_intervalo"}, "clima": {},
         "janelas": jan, "planos": planos, "coordenacoes": coords,
         "auditoria": {"aceito": True, "metodo": "teste", "verificacoes": {"hierarquica": True}, "constatacoes": 0},
         "procedencia": {"motor": "milp_mpc_v1", "software": {}}, "limitacoes": ["Marco sintético de teste."],
         "convencoes": {"potencia": "kW líquidos"},
         "tabelas": {"v2/intervalos.csv": {"colunas": list(inter), "linhas": [[inter[c][i] for c in inter] for i in it]}},
         "resumo": {"custo_realizado_total_R": cint * K, "componentes_R": {"importacao_rede": cimp * K, "combustivel_h2": ch2 * K,
                                                                          "throughput_bess": cthr * K},
                    "energia_demanda_kWh": dem * K, "energia_atendida_kWh": dem * K, "energia_nao_atendida_kWh": 0.0,
                    "energia_importada_kWh": imp * K, "energia_exportada_kWh": 0.0, "gasto_importacao_R": cimp * K,
                    "receita_exportacao_R": 0.0, "indicadores_selados": {},
                    "sinal_valor_futuro": {"valido": sum(1 for w in jan if w["sinal_qualidade"] == "valido")},
                    "solver": {"janelas_resolvidas": len(jan), "janelas_otimas": len(jan), "gap_rel_max": 0.0},
                    "missao_completa": True},
         "aceitacao": {"algebrica": {"estado": "aprovada", "criterio": "teste"}, "dinamica": {"estado": "nao_aplicavel"},
                       "fisica": {"estado": "nao_validada"}, "rotulo": "teste"},
         "avisos": ["Dados SINTÉTICOS de teste."], "verificacao": {"ok": True, "itens": [[True, "verificação de teste"]]},
         "arquivos": [["v2/intervalos.csv", "0" * 64, 1]],
         "fontes": {"intervalos": "v2/intervalos.csv", "fronteiras": "v2/fronteiras.csv", "janelas": "v2/janelas.csv",
                    "renovaveis": "v2/renovaveis.json", "pemfc": "v2/pemfc.json", "pemfc_dinamica": "v2/pemfc_dinamica.json",
                    "planos": "v2/planos.csv", "coordenacoes": "v2/coordenacoes.json", "auditoria": "v2/auditoria.json"}}
    if not conectado:
        f["resumo"]["componentes_R"].pop("importacao_rede")
    f["hash"] = "sintetico-" + hashlib.sha256(json.dumps(f, sort_keys=True).encode()).hexdigest()[:16]
    return f


# --------------------------------------------------------------------------------------------------- Node / navegador
RAIZ = Path(__file__).resolve().parents[1]
ESTATICO = RAIZ / "seeds2" / "ui" / "static" / "trama"
NODE = shutil.which("node")
PUROS = ("modelo, balancoDe, planoPorTipo, agg, el, mais, vezes, menos, razao, nfu, mapa, conta, somaT, acum, opc, teto, "
         "maxv, agruparAvisos, nf")


def node(corpo: str, *marcos: dict):
    """Executa ``corpo`` (JavaScript; ``api`` = funções puras do componente, ``Fs`` = marcos, ``F`` = o primeiro) em Node
    e devolve o JSON de ``return``. Sem DOM: só o modelo de vista."""
    harness = ("const fs = require('fs');"
               f"const src = fs.readFileSync({json.dumps(str(ESTATICO / 'trama.js'))}, 'utf8') + '\\n' + "
               f"fs.readFileSync({json.dumps(str(ESTATICO / 'partitura.js'))}, 'utf8')"
               ".replace('export default function', 'function __componente');"
               f"const api = new Function(src + '\\nreturn {{ {PUROS} }};')();"
               "const Fs = JSON.parse(fs.readFileSync(process.argv[1], 'utf8')), F = Fs[0];"
               f"const out = (function () {{ {corpo} }})();"
               "console.log(JSON.stringify(out === undefined ? '__undefined__' : out, (k, v) => (v === undefined ? '__undefined__' : v)));")
    with tempfile.TemporaryDirectory() as d:
        arq = Path(d) / "marcos.json"
        arq.write_text(json.dumps(list(marcos), allow_nan=False), encoding="utf-8")
        r = subprocess.run([NODE, "-e", harness, str(arq)], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


def navegador_disponivel() -> bool:
    """Chromium + Playwright (Node) presentes? Os testes de DOM são pulados explicitamente quando não estão."""
    if not NODE:
        return False
    r = subprocess.run([NODE, "-e", "require('playwright')"], capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def bancada(marcos: dict, *, passos=None, largura: int = 1400, altura: int = 900, outros: dict | None = None) -> dict:
    """Monta o componente REAL (sem Streamlit) numa página local para cada marco e percorre lentes e painéis num
    navegador de verdade (``tools/e2e/bancada_piso3db.js``). Devolve, por marco, erros de página e o texto de cada vista."""
    import importlib.util as iu
    spec = iu.spec_from_file_location("bancada_piso3db", RAIZ / "tools" / "e2e" / "bancada_piso3db.py")
    mod = iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as d:
        paginas = {}
        for nome, f in marcos.items():
            p = Path(d) / f"{nome}.html"
            p.write_text(mod.pagina(f, outros), encoding="utf-8")
            paginas[nome] = str(p)
        plano = Path(d) / "plano.json"
        plano.write_text(json.dumps({"paginas": paginas, "passos": passos, "largura": largura, "altura": altura}), encoding="utf-8")
        r = subprocess.run([NODE, str(RAIZ / "tools" / "e2e" / "bancada_piso3db.js"), str(plano)], capture_output=True,
                           text=True, timeout=600, cwd=str(RAIZ / "tools" / "e2e"))
    if r.returncode != 0:
        raise AssertionError(r.stderr or r.stdout)
    return json.loads(r.stdout)
