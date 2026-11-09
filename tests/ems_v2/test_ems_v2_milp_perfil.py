"""Piso 3B-P — extensão CONTROLADA do contrato e do auditor, catálogo 3B-P e isolamento (núcleo sem Pyomo).

Os testes de contrato/auditor/catálogo não exigem solver; só a verificação de componentes do modelo usa Pyomo.
"""
import ast
import dataclasses
from pathlib import Path

import pytest

from ems_v2 import FORMULACAO_3BP, FORMULACAO_VERSAO
from ems_v2 import fixtures as F
from ems_v2 import fixtures_3b as X
from ems_v2.audit import CandidatoDespacho, auditar
from ems_v2.capabilities import CAPACIDADES, CAPACIDADES_3BP, capacidades, status_equacao
from ems_v2.catalog import carregar_equacoes, carregar_simbolos
from ems_v2.contracts import validar_entrada

pytestmark = pytest.mark.synthetic_algebraic
RAIZ = Path(__file__).resolve().parents[2]


# ----------------------------------------------------------------------------- perfil de formulação (obstáculo A)
def test_perfil_3A_inalterado_e_3BP_explicito():
    assert validar_entrada(F.a05_opt_entrada()).codigos("pendente") == {"termo_objetivo_nao_suportado_3A"}
    assert validar_entrada(X.a05_opt()[0]).aceito
    e = X.a05_opt()[0]
    for termo, cod in (("geracao_termica", "termo_objetivo_nao_suportado_3BP"),
                       ("terminal", "termo_objetivo_nao_suportado_3BP")):
        e2 = dataclasses.replace(e, politica_objetivo=dataclasses.replace(e.politica_objetivo, termos=(termo,)))
        assert cod in validar_entrada(e2).codigos("pendente")
    e3 = dataclasses.replace(e, versao_formulacao="v9")
    assert "formulacao_incompativel" in validar_entrada(e3).codigos()


@pytest.mark.parametrize("mutar,codigo", [
    (lambda e: dataclasses.replace(e, baterias=(dataclasses.replace(e.baterias[0], custo_throughput=None),)),
     "parametro_ausente"),
    (lambda e: dataclasses.replace(e, renovaveis=(dataclasses.replace(e.renovaveis[0], custo_curtailment=None),)),
     "parametro_ausente"),
])
def test_coeficientes_obrigatorios_nunca_presumidos(mutar, codigo):
    assert codigo in validar_entrada(mutar(X.a05_opt()[0])).codigos("erro")


def test_regras_de_combustivel_e_ens_no_3BP():
    e = X.a06(preco_h2=10.0)[0]
    assert validar_entrada(e).aceito
    sem_var = dataclasses.replace(e, politica_objetivo=dataclasses.replace(e.politica_objetivo, variante_combustivel=None))
    assert "variante_combustivel_ausente" in validar_entrada(sem_var).codigos()
    multimodo = dataclasses.replace(e, politica_objetivo=dataclasses.replace(e.politica_objetivo,
                                                                             variante_combustivel="multimodo"))
    assert "variante_combustivel_nao_suportada_3BP" in validar_entrada(multimodo).codigos("pendente")
    sem_preco = dataclasses.replace(e, geradores=(dataclasses.replace(e.geradores[0], preco_h2=None),))
    assert "parametro_ausente" in validar_entrada(sem_preco).codigos()
    sem_termo = dataclasses.replace(e, politica_objetivo=dataclasses.replace(e.politica_objetivo, termos=(),
                                                                             variante_combustivel=None))
    assert "coeficiente_sem_termo" in validar_entrada(sem_termo).codigos()
    t = X.a07()[0]
    t2 = dataclasses.replace(t, geradores=(dataclasses.replace(t.geradores[0], preco_h2=F.par(1.0, "R$/kg", "x")),))
    assert "preco_h2_em_nao_pemfc" in validar_entrada(t2).codigos()
    d = X.a08(True)[0]
    assert validar_entrada(d).aceito
    d2 = dataclasses.replace(d, demandas=(dataclasses.replace(d.demandas[0], custo_energia_nao_suprida=None),))
    assert "parametro_ausente" in validar_entrada(d2).codigos()


# SHA-256 canônicos das fixtures 3A medidos em main f6d009d (código 3A, antes do Piso 3B-P)
HASHES_3A_MAIN = {"a01": "b87454a153ca415b", "b01b": "84c4eef103465c06"}


def test_campos_novos_nao_alteram_o_json_nem_o_hash_das_entradas_3A():
    from ems_v2.contracts import entrada_de_json, hash_entrada, json_canonico
    for nome, pref in HASHES_3A_MAIN.items():
        e = getattr(F, nome)()[0]
        assert hash_entrada(e).startswith(pref), nome
        s = json_canonico(e)
        assert "custo_energia_nao_suprida" not in s and "preco_h2" not in s
        assert entrada_de_json(s) == e
    e = X.a08(True)[0]                                  # presentes ⇒ serializados e relidos sem perda
    s = json_canonico(e)
    assert '"custo_energia_nao_suprida"' in s and entrada_de_json(s) == e and json_canonico(entrada_de_json(s)) == s


# ----------------------------------------------------------------------------- auditor com compromisso fixo (obstáculo B)
def _cand_a07(p=20.0, u=1.0):
    return CandidatoDespacho(demandas={"syn-carga": {"ell": (0.0,)}}, geradores={"syn-ger": {"u": (u,), "p": (p,)}})


def test_auditor_sem_programa_continua_nao_suportado():
    e, _ = X.a07()
    r = auditar(e, _cand_a07())
    assert not r.aceito and "commitment_M09_M12" in r.familias_nao_suportadas


def test_auditor_com_programa_verifica_balanco_dominio_e_programa():
    e, cp = X.a07()
    r = auditar(e, _cand_a07(p=20.0), compromisso_fixo=cp)          # 20 kW contra demanda 5: balanço violado
    assert not r.aceito and r.familias_reprovadas() == {"balanco"}
    assert set(r.familias_nao_modeladas) == {"rampas_M11", "permanencias_M12"}
    r = auditar(e, _cand_a07(p=5.0), compromisso_fixo=cp)           # balanço ok, mas ON abaixo de P_min
    assert not r.aceito and "on_fora_do_dominio" in r.codigos()
    r = auditar(e, _cand_a07(p=20.0, u=0.0), compromisso_fixo=cp)   # u diverge do programa fixo
    assert not r.aceito and "compromisso_fixo" in r.familias_reprovadas()
    r = auditar(e, _cand_a07(), compromisso_fixo={"syn-ger": (0,)})
    assert not r.aceito and "transicao_nao_modelada_3BP" in r.codigos()
    r = auditar(e, _cand_a07(), compromisso_fixo={})
    assert not r.aceito and "compromisso_invalido" in r.codigos()


def test_auditor_custos_3BP_so_com_coeficientes_declarados():
    e, cp = X.a08(True)
    c = CandidatoDespacho(demandas={"syn-carga": {"ell": (5.0,)}}, geradores={"syn-ger": {"u": (1.0,), "p": (5.0,)}},
                          custos_reportados={"energia_nao_suprida": 10.0, "total": 10.0})
    r = auditar(e, c, compromisso_fixo=cp)
    assert r.aceito and r.custos_reconstruidos["energia_nao_suprida"] == 10.0 and r.custos_reconstruidos["total"] == 10.0
    r = auditar(e, dataclasses.replace(c, custos_reportados={"total": 9.0}), compromisso_fixo=cp)
    assert not r.aceito and "custo" in r.familias_reprovadas()


def test_auditor_nao_importa_pyomo_nem_o_motor():
    for mod in ("audit.py", "reference.py", "contracts.py"):
        arv = ast.parse((RAIZ / "ems_v2" / mod).read_text(encoding="utf-8"))
        nomes = {n.module or "" for n in ast.walk(arv) if isinstance(n, ast.ImportFrom)} | {
            a.name for n in ast.walk(arv) if isinstance(n, ast.Import) for a in n.names}
        assert not any(x.startswith(("pyomo", "highspy")) or "milp" in x for x in nomes), (mod, nomes)


# ----------------------------------------------------------------------------- isolamento
def test_so_o_subpacote_milp_importa_pyomo_ou_highspy():
    for p in sorted((RAIZ / "ems_v2").rglob("*.py")):
        rel = p.relative_to(RAIZ / "ems_v2").as_posix()
        arv = ast.parse(p.read_text(encoding="utf-8"))
        nomes = {n.module or "" for n in ast.walk(arv) if isinstance(n, ast.ImportFrom)} | {
            a.name for n in ast.walk(arv) if isinstance(n, ast.Import) for a in n.names}
        usa = any(x.split(".")[0] in ("pyomo", "highspy") for x in nomes)
        # 3C-1 (contradição C-3C1-01, ver docs/ems_v2/FORMULACAO_3C1.md §9): os DOIS módulos novos do MILP 3C-1 são
        # acrescentados nominalmente; a regra "só o subpacote milp importa Pyomo/HiGHS" é preservada.
        if rel in ("milp/modelo.py", "milp/solver.py", "milp/ambiente.py", "milp/modelo_3c1.py", "milp/solver_3c1.py"):
            continue
        assert not usa, rel
        assert not any(x.split(".")[0] in ("streamlit", "ems_integration") for x in nomes), rel
        # 3C-0 (contradição C-3C0-01, ver docs/ems_v2/PONTE_3C0.md §8): ÚNICA exceção nominal para ``seeds2`` é o
        # adaptador SOMENTE LEITURA ``ponte_seeds2/leitor.py``; whitelist e ausência de escrita verificadas em
        # tests/ems_v2/test_ems_v2_ponte_isolamento.py.
        if rel != "ponte_seeds2/leitor.py":
            assert not any(x.split(".")[0] == "seeds2" for x in nomes), rel


# ----------------------------------------------------------------------------- capacidades e catálogo 3B-P
SIM = {s["id"]: s for s in carregar_simbolos()}
EQ = {e["id"]: e for e in carregar_equacoes()}


def test_capacidades_3A_preservadas_e_3BP_coerentes_com_o_manifesto():
    assert capacidades(formulacao=FORMULACAO_VERSAO) == tuple(c for c in CAPACIDADES)
    assert status_equacao("M14") == "apenas_especificacao" and status_equacao("M14", FORMULACAO_3BP) == "implementado_3BP"
    mapa = {"implementado_3BP": {"implementado_3BP"}, "parcial_3BP": {"parcial_3BP"},
            "futuro": {"apenas_especificacao", "nao_suportado"}}
    vistos = {}
    for c in CAPACIDADES_3BP:
        for eq in c.equacoes:
            assert eq in EQ and eq not in vistos
            vistos[eq] = c
    for e in EQ.values():
        if e["status_3BP"] == "substituida":
            assert e["id"] not in vistos
        else:
            assert vistos[e["id"]].status in mapa[e["status_3BP"]], e["id"]
            assert vistos[e["id"]].familia == e["familia"], e["id"]


def test_catalogo_3BP_sem_simbolo_futuro_em_equacao_implementada():
    for e in EQ.values():
        if e["status_3BP"] == "implementado_3BP":
            for x in e["simbolos"]:
                assert SIM[x]["status_3BP"] in ("ativo_3BP", "decidido_3BP"), (e["id"], x)
        if e["status_3BP"] == "parcial_3BP":
            assert e.get("obs_3BP"), e["id"]
    for sid, s in SIM.items():
        eqs = [EQ[x] for x in s["equacoes"].split(";")]
        if s["status_3BP"] in ("ativo_3BP", "decidido_3BP"):
            assert s["codigo_3BP"], sid
            assert any(x["status_3BP"] in ("implementado_3BP", "parcial_3BP") for x in eqs), sid
        else:
            assert not s["codigo_3BP"], sid
        if s["status_3BP"] == "decidido_3BP":
            assert s["tipo"] == "variavel" and s["codigo_3BP"].startswith("pyomo:"), sid
    # variáveis de transição, rampas e modos continuam FUTURAS (não apresentadas como capacidade)
    for sid in ("y", "z", "y_start", "z_stop", "m_mode", "v_arc", "R_up", "S_up", "T_up", "kappa", "xi", "M_stock"):
        assert SIM[sid]["status_3BP"] == "futuro", sid


def test_catalogo_3BP_codigo_resolvivel():
    pytest.importorskip("pyomo", exc_type=ImportError)
    import importlib
    from ems_v2.milp.modelo import construir_modelo
    from ems_v2.contracts import DispositivoDescarte, PoliticaServico, UIDRecurso
    e, cp = X.multi_uid()
    dev = DispositivoDescarte(UIDRecurso("syn-dump"), F.par(5.0, "kW", "teste"))
    e = dataclasses.replace(e, politica_servico=PoliticaServico("duro", F.proc("teste"), descarte=dev))
    m = construir_modelo(e, cp).modelo
    for sid, s in SIM.items():
        cod = s["codigo_3BP"]
        if not cod:
            continue
        if cod.startswith("pyomo:"):
            assert hasattr(m, cod.split(":", 1)[1]), sid
            continue
        partes = cod.split(".")
        for i in range(len(partes), 0, -1):
            try:
                obj = importlib.import_module(".".join(partes[:i]))
            except ModuleNotFoundError:
                continue
            for nome in partes[i:]:
                obj = getattr(obj, nome) if hasattr(obj, nome) else obj.__dataclass_fields__[nome]
            break
        else:
            raise AssertionError(sid)
