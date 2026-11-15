"""B04-C5-01 (P1) — a exceção nominal das guardas é ESTRITA: nomes, status e linhas removidas listadas; o veredito da
admissibilidade dinâmica continua sendo ``pemfc_dinamica.admissibilidade`` (só o TEXTO do preflight mudou)."""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from unittest import mock

import pytest

import b04c501_guard_policy as G

RAIZ = Path(__file__).resolve().parents[2]


def _base_disponivel() -> bool:
    try:
        subprocess.run(["git", "cat-file", "-e", G.BASE + "^{commit}"], cwd=RAIZ, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def test_politica_estrita_por_nome_e_status():
    for nome in G.MODIFICADOS | G.ADICIONADOS:
        assert not nome.endswith("/") and "*" not in nome and Path(nome).suffix, nome
    assert not (G.MODIFICADOS & G.ADICIONADOS) and G.REFERENCIAM_O_MOTOR <= G.ADICIONADOS
    assert not any(n.startswith(("ems_v2/", "seeds2/", "models/", "h2_pemfc/")) for n in G.MODIFICADOS | G.ADICIONADOS)
    assert not ({"integracao_v2/pemfc_dinamica.py", "integracao_v2/curva_h2.py"} & G.MODIFICADOS)
    linhas = [["M", "integracao_v2/preflight.py"], ["D", "integracao_v2/preflight.py"],
              ["M", "integracao_v2/pemfc_dinamica.py"], ["M", "integracao_v2/curva_h2.py"],
              ["A", "tests/test_b04_c5_01.py"], ["M", "tests/test_b04_c5_01.py"], ["M", "integracao_v2/ui.py"]]
    with mock.patch.object(G, "remocoes_nao_conformes", return_value={}):
        assert G.filter_changes(RAIZ, linhas) == [
            ["D", "integracao_v2/preflight.py"], ["M", "integracao_v2/pemfc_dinamica.py"],
            ["M", "integracao_v2/curva_h2.py"], ["M", "tests/test_b04_c5_01.py"], ["M", "integracao_v2/ui.py"]]
    with mock.patch.object(G, "remocoes_nao_conformes", return_value={"integracao_v2/preflight.py": ["x"]}):
        assert ["M", "integracao_v2/preflight.py"] in G.filter_changes(RAIZ, linhas)


def test_referencia_ao_motor_so_nominal_e_alcancada_pela_cadeia_da_guarda_3a():
    from piso3da_guard_policy import referencia_autorizada
    assert referencia_autorizada("tests/test_b04_c5_01.py")
    assert not referencia_autorizada("tests/test_b04_c5_01_outro.py") and not referencia_autorizada("seeds2/ui/main.py")


def test_veredito_da_pemfc_continua_sendo_a_admissibilidade_e_os_textos_sao_funcoes_puras():
    arvore = ast.parse((RAIZ / "integracao_v2/preflight.py").read_text(encoding="utf-8"))
    funcs = {n.name: n for n in arvore.body if isinstance(n, ast.FunctionDef)}
    pemfc = ast.unparse(funcs["_pemfc"])
    assert pemfc.count("DY.admissibilidade(mev['analise'], curva, delta_s, decl['abstracao'])") == 1
    assert pemfc.count("code='pemfc_transitorio_incompativel'") == 1 and "if adm:" in pemfc
    for nome in ("mensagem_transitorio_pemfc", "mensagem_dinamica_compativel_pemfc", "deltas_admissiveis_pemfc",
                 "_lista_deltas"):
        f = funcs[nome]
        nomes = {n.id for n in ast.walk(f) if isinstance(n, ast.Name)}
        assert "pf" not in nomes and "ERROR" not in nomes and "OK" not in nomes, nome      # só texto, nenhum veredito
        assert not any(isinstance(n, (ast.Global, ast.Nonlocal)) for n in ast.walk(f)), nome


def test_excecao_dos_exemplos_persistentes_e_estrita():
    """Só NOVAS instantâneas na raiz de ``seeds2/exemplos/`` e o README dessa pasta (exceção já autorizada à regra 8)."""
    assert G.exemplo_persistente(["A", "seeds2/exemplos/C5_EMB_H2_120_Embarcacao_hibrida.seeds2snapshot.zip"])
    assert G.exemplo_persistente(["M", "seeds2/exemplos/README.md"])
    for row in (["M", "seeds2/exemplos/C4_Carga_CT046_Solar_Bateria_Rede.seeds2snapshot.zip"],   # nunca alterar um exemplo
                ["D", "seeds2/exemplos/C4_Carga_CT046_Solar_Bateria_Rede.seeds2snapshot.zip"],
                ["A", "seeds2/exemplos/sub/X.seeds2snapshot.zip"], ["A", "seeds2/exemplos/x.py"],
                ["A", "seeds2/microgrid/X.seeds2snapshot.zip"], ["A", "seeds2/exemplos/X.seeds2backup.zip"],
                ["M", "seeds2/microgrid/exemplos.py"], ["A", "seeds2/exemplos/README.md"]):
        assert not G.exemplo_persistente(row), row


@pytest.mark.skipif(not _base_disponivel(), reason="base da missão indisponível neste clone")
def test_auditoria_explicita_da_missao():
    rel = G.auditar_missao(RAIZ)
    assert rel["remocoes_nao_conformes"] == {}, rel["remocoes_nao_conformes"]
    assert rel["intocados_violados"] == [], rel["intocados_violados"]
    with mock.patch.dict(G.REMOVIDAS, {"integracao_v2/preflight.py": {""}}):
        assert "integracao_v2/preflight.py" in G.remocoes_nao_conformes(RAIZ)
