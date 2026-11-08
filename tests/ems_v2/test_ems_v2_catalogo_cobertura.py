"""Cobertura do catálogo M01–M23 + adenda v1.1 (adenda B03; condição B da fiscalização).

* etiquetas ``\\tag{…}`` das especificações VERSIONADAS são extraídas automaticamente (verificação real);
* a relação equação → símbolos é um MANIFESTO revisado à mão (não há analisador exaustivo de LaTeX);
* nenhum símbolo usado fica indefinido; nenhum símbolo futuro é apresentado como capacidade implementada;
* símbolos exclusivos das variantes instantânea/multimodo nunca se misturam (adenda B05).
"""
import csv
import hashlib
import importlib
import re
from pathlib import Path

import pytest

from ems_v2.capabilities import CAPACIDADES, MOTORES, status_equacao
from ems_v2.catalog import STATUS_EQUACAO, STATUS_SIMBOLO, VARIANTES, carregar_equacoes, carregar_simbolos

pytestmark = pytest.mark.synthetic_algebraic
RAIZ = Path(__file__).resolve().parents[2]
REFS = RAIZ / "docs" / "ems_v2" / "referencias"
HASHES = {
    "02_Especificacion_matematica.md": "bd60029b26d7c5544796ec62c0a15bf2a50b255a6108e9bb3ac95a1af0da8745",
    "01_ADDENDA_MATEMATICA_v1.1.md": "36fbbb69fa0aada845b56566ca4c3a819ee64eac8467326cb7a0a9b88815ca8a",
    "06_CATALOGO_SIMBOLOS_v1.1.csv": "850a1c2c4a4b93e7cdc2d8b9976f0f11d488641822cc993ca50aad2ec5c07d6a",
    "05_FIXTURES_Y_PUERTAS.md": "30ae40ba60c46f8e55eca01fba539c22679527a5f15ed803b8da3c1c4a0a47c2",
}
SIM = {s["id"]: s for s in carregar_simbolos()}
EQ = {e["id"]: e for e in carregar_equacoes()}


def test_referencias_versionadas_integras():
    for nome, h in HASHES.items():
        assert hashlib.sha256((REFS / nome).read_bytes()).hexdigest() == h, nome
        assert h in (REFS / "PROCEDENCIA.md").read_text(encoding="utf-8")


def test_todas_as_etiquetas_das_especificacoes_cobertas():
    tags = set()
    for nome in ("02_Especificacion_matematica.md", "01_ADDENDA_MATEMATICA_v1.1.md"):
        tags |= set(re.findall(r"\\tag\{([^}]+)\}", (REFS / nome).read_text(encoding="utf-8")))
    esperadas = {f"M{i:02d}" for i in range(1, 24) if i != 11} | {"M11a", "M11b", "M20b", "M20c", "M03-v1.1"}
    assert tags == esperadas                     # o documento tem exatamente estas etiquetas
    cobertas = {e["tag"] for e in EQ.values() if e["tag"]}
    assert tags == cobertas


def test_ids_unicos_e_campos_validos():
    assert len(SIM) == len(carregar_simbolos()) and len(EQ) == len(carregar_equacoes())
    for e in EQ.values():
        assert e["status"] in STATUS_EQUACAO and e["variante"] in VARIANTES and e["simbolos"], e["id"]
        assert len(set(e["simbolos"])) == len(e["simbolos"]), e["id"]
        if e["status"] == "substituida":
            assert e.get("substituida_por") in EQ, e["id"]
    for s in SIM.values():
        assert s["status"] in STATUS_SIMBOLO and s["variante"] in VARIANTES, s["id"]
        assert s["tipo"] in ("conjunto", "parametro", "variavel", "derivado"), s["id"]
        for campo in ("indices", "dominio", "unidade", "fronteira_ou_sinal", "opcional", "habilitado_se", "origem"):
            assert s[campo].strip(), (s["id"], campo)
        assert s["opcional"] in ("sim", "nao")


def test_nenhum_simbolo_usado_indefinido_e_nenhum_orfao():
    usados = {x for e in EQ.values() for x in e["simbolos"]}
    assert usados - set(SIM) == set(), "símbolos usados sem definição"
    assert set(SIM) - usados == set(), "símbolos declarados sem equação"


def test_coluna_equacoes_coincide_com_o_manifesto():
    for sid, s in SIM.items():
        manif = [e["id"] for e in EQ.values() if sid in e["simbolos"]]
        assert s["equacoes"].split(";") == manif, sid


def test_variantes_exclusivas_derivadas_e_sem_mistura():
    for sid, s in SIM.items():
        vs = {EQ[e]["variante"] for e in s["equacoes"].split(";")}
        esperado = "comum" if len(vs) > 1 or vs == {"comum"} else vs.pop()
        assert s["variante"] == esperado, sid
    for e in EQ.values():
        for x in e["simbolos"]:
            v = SIM[x]["variante"]
            assert v in ("comum", e["variante"]), (e["id"], x)
    # B05: na variante multimodo ficam EXCLUÍDOS m^SU y + m^SD z e W^SU/W^SD (evita dupla contagem)
    excluidos = {"m_SU", "m_SD", "W_SU", "W_SD", "m_inst", "y", "z", "C_SU", "C_SD"}
    for e in EQ.values():
        if e["variante"] == "multimodo":
            assert not excluidos & set(e["simbolos"]), e["id"]
    assert {"y_start", "z_stop"} <= set(EQ["M21-MULTI"]["simbolos"])     # contadores usam y^start, não y^run
    assert "m_inst" in EQ["M21-v1.1"]["simbolos"] and "m_multi" in EQ["M21-MULTI"]["simbolos"]


def test_b01_substituicoes_explicitas():
    assert EQ["M03"]["status"] == "substituida" and EQ["M03"]["substituida_por"] == "M03-v1.1"
    assert EQ["M21"]["status"] == "substituida" and EQ["M21"]["substituida_por"] == "M21-v1.1"
    assert "C_R" not in EQ["M21-v1.1"]["simbolos"] and "C_oper" in EQ["M21-CURT"]["simbolos"]
    assert "E_indisp" not in {x for e in EQ.values() if e["id"].startswith("M21") for x in e["simbolos"]}
    for sid, s in SIM.items():
        if s["status"] == "substituido":
            assert all(EQ[e]["status"] == "substituida" for e in s["equacoes"].split(";")), sid


def _resolver(caminho: str):
    partes = caminho.split(".")
    for i in range(len(partes), 0, -1):
        try:
            obj = importlib.import_module(".".join(partes[:i]))
        except ModuleNotFoundError:
            continue
        for nome in partes[i:]:
            if hasattr(obj, nome):
                obj = getattr(obj, nome)
            elif nome in getattr(obj, "__dataclass_fields__", {}):
                obj = obj.__dataclass_fields__[nome]
            else:
                raise AttributeError(caminho)
        return obj
    raise ModuleNotFoundError(caminho)


def test_simbolos_ativos_tem_codigo_e_futuros_nao_se_passam_por_capacidade():
    for sid, s in SIM.items():
        eqs = [EQ[e] for e in s["equacoes"].split(";")]
        if s["status"] in ("ativo_3A", "auditado_3A"):
            assert s["codigo"] and s["implementacao"], sid
            _resolver(s["codigo"])
            assert any(e["status"] in ("implementado_3A", "parcial_3A") for e in eqs), sid
            if s["status"] == "auditado_3A":
                assert "auditoria" in s["implementacao"] and s["tipo"] == "variavel", sid
        else:
            assert s["implementacao"] in ("", "contrato"), sid       # no máximo declarável no contrato
            if s["codigo"]:
                assert s["implementacao"] == "contrato", sid
                _resolver(s["codigo"])
    # variáveis do MILP nunca são "ativas": no 3A só são candidatas auditadas ou futuras
    assert all(s["status"] != "ativo_3A" for s in SIM.values() if s["tipo"] == "variavel")


def test_semente_inteiramente_coberta():
    with open(REFS / "06_CATALOGO_SIMBOLOS_v1.1.csv", encoding="utf-8", newline="") as f:
        semente = [r["id"] for r in csv.DictReader(f)]
    cobertos = set(SIM) | {s["id_semente"] for s in SIM.values() if s["id_semente"]}
    assert set(semente) - cobertos == set()
    assert SIM["a"]["id_semente"] == "a_r"                         # resolução C2 registrada
    assert len(SIM) > len(semente)                                 # catálogo completado (semente não era exaustiva)


def test_capacidades_coerentes_com_o_manifesto():
    mapa = {"implementado_3A": {"implementado_3A"}, "parcial_3A": {"parcial_3A"},
            "futuro": {"apenas_especificacao", "nao_suportado"}}
    vistos = {}
    for c in CAPACIDADES:
        for eq in c.equacoes:
            assert eq in EQ, eq
            assert eq not in vistos, f"{eq} em duas capacidades"
            vistos[eq] = c
    for e in EQ.values():
        if e["status"] == "substituida":
            assert e["id"] not in vistos and status_equacao(e["id"]) is None
        else:
            assert e["id"] in vistos, e["id"]
            assert vistos[e["id"]].status in mapa[e["status"]], e["id"]
            assert vistos[e["id"]].familia == e["familia"], e["id"]
    assert MOTORES["legacy_v16"].estado == "unico_motor_operacional"
    assert MOTORES["milp_mpc_v1"].estado == "experimental_sem_solver"
