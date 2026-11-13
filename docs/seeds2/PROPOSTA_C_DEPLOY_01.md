# Proposta C-DEPLOY-01 — regularização nominal de `requirements.txt` (commit `f523035`)

**Situação: PROPOSTA, não aplicada.** Nenhuma guarda foi alterada no PR #27. Este documento só descreve, com o patch
pronto e verificado, como regularizar a alteração histórica — se e quando o responsável aprovar.

## 1. O fato

O commit `f523035333ba88b72d7fb92d21915b585b5b9d7b` (13/11/2026, autor: o responsável; «fix(deploy): install EMS V2
solver on Streamlit Cloud»), já em `main`, acrescentou três linhas ao fim de `requirements.txt`:

```
<linha vazia>
# Instalar também o solver MILP–MPC do EMS V2 no ambiente de deploy Streamlit.
-r requirements-ems_v2.txt
```

`requirements.txt` é um caminho protegido por duas guardas, que por isso falham em `main` desde então (falhas
anteriores ao PR #27, reproduzidas num worktree de `main` puro):

| Guarda | Por que falha |
|---|---|
| `tests/ems_v2/test_ems_v2_3c4_isolamento.py::test_pisos_anteriores_v16_e_aplicacao_sem_alteracao_desde_o_merge_do_pr16` | `git diff 10365c5` mostra `M requirements.txt`, ausente das exceções nominais (`AssertionError: {'requirements.txt'}`). |
| `tests/ems_v2/test_piso3db_guardas.py::test_auditoria_explicita_do_diff_da_missao` | `requirements.txt` está em `INTOCADOS` da auditoria do 3D-B (`[['M', 'requirements.txt']]`). |

## 2. O que a proposta faz (e o que não faz)

* **Um módulo novo** `tests/ems_v2/deploy_requirements_guard_policy.py` com o SHA-256 LITERAL do conteúdo de
  `requirements.txt` em `f523035` (`6d85fa26…482c0c`; o anterior, `f523035^`, é `9003cece…51fc1c`). A função
  `filter_changes` remove **uma única linha** do diff — `["M", "requirements.txt"]` — e **só** quando o arquivo atual é,
  byte a byte, aquele conteúdo. Nada é recalculado a partir da árvore de trabalho nem do Git.
* **Dois pontos de encaixe**, ambos arquivos de política de missões de interface (não fixados por hash):
  1. fim da cadeia nominal (`ui_running01_guard_policy.filter_changes`), por onde passam as guardas de isolamento
     permanentes; o teste do 3C-4 não pode ser editado (o fonte está fixado em `tests/fixtures/wind_3c4_integration_v1.json`);
  2. `piso3db_guard_policy.auditar_missao`, filtrando `linhas` antes de `intocados` (filtrar só `intocados` empurraria a
     linha para `fora_da_politica`).
* **Não muda:** nenhuma guarda global, nenhum teste existente, `INTOCADOS` de nenhuma missão, as exceções anteriores
  (eólica, estabilização, CI-01, 3D-A…3D-B, UI-REDESIGN-01, UI-RUNNING-01); `requirements-ems_v2.txt` continua
  protegido; o escopo do PR #27 (modal) não é ampliado — por isso a proposta não está nele.

## 3. Verificação (num worktree separado, descartado; a branch do PR não foi tocada)

| Cenário | Resultado das 2 guardas |
|---|---|
| Proposta aplicada; `requirements.txt` = `f523035` | **2 passed** |
| `requirements.txt` com UMA linha a mais (`numpy`) | **2 failed** |
| `requirements.txt` sem a linha `-r requirements-ems_v2.txt` | **2 failed** |
| `requirements-ems_v2.txt` alterado (`highspy==1.16.0`) | **2 failed** |
| Todas as guardas (`tests/ems_v2` + `tests/estabilizacao`, `-k isolamento/guard/guarda/scope/fingerprint/wind/policy/nominais`) | **223 passed, 2 skipped, 0 failed** |

`auditar_missao` do 3D-B continua com `ok: false` por `fora_da_politica` (arquivos de missões POSTERIORES ao 3D-B, que
a lista dele não conhece — já era assim antes); o teste só verifica `intocados_violados`, que fica vazio.

## 4. Ponto que exige decisão além da guarda

`test_ems_v2_isolamento.py::test_sem_dependencia_nova_em_requirements` verifica só o TEXTO de `requirements.txt`
(`pyomo`/`highs` ausentes) e continua passando; mas, com `-r requirements-ems_v2.txt`, a instalação de deploy passa a
incluir Pyomo + HiGHS — o que o cabeçalho de `requirements-ems_v2.txt` («NÃO fazem parte da aplicação V1.6») e o
`CLAUDE.md` não refletem. A regularização da guarda **não** decide isso; registra o fato. Opções para o responsável:
(a) aceitar o solver no deploy e atualizar a documentação; (b) mover a inclusão para um arquivo de deploy separado
(se a plataforma permitir), mantendo `requirements.txt` intacto.

## 5. Patch proposto

Aplicar com `git apply` sobre a branch que o responsável indicar (depois do merge do PR #27, que cria
`ui_running01_guard_policy.py`):

```diff
diff --git a/tests/ems_v2/deploy_requirements_guard_policy.py b/tests/ems_v2/deploy_requirements_guard_policy.py
new file mode 100644
index 0000000..725aa43
--- /dev/null
+++ b/tests/ems_v2/deploy_requirements_guard_policy.py
@@ -0,0 +1,35 @@
+"""C-DEPLOY-01 (PROPOSTA) — regularização NOMINAL da alteração histórica de ``requirements.txt`` feita pelo responsável
+no commit ``f523035`` («fix(deploy): install EMS V2 solver on Streamlit Cloud»).
+
+Admite UMA linha de diff — ``["M", "requirements.txt"]`` — e SÓ quando o conteúdo atual do arquivo é, byte a byte, o
+conteúdo daquele commit (SHA-256 fixado abaixo, literal; nada é recalculado a partir da árvore). Qualquer outra
+alteração de ``requirements.txt`` (outra linha, outra versão, remoção) volta a falhar em TODAS as guardas;
+``requirements-ems_v2.txt`` continua protegido como antes. Não gera nem atualiza hashes; não consulta a rede.
+"""
+from __future__ import annotations
+
+import hashlib
+from pathlib import Path
+
+COMMIT = "f523035333ba88b72d7fb92d21915b585b5b9d7b"
+ARQUIVO = "requirements.txt"
+SHA256_AUTORIZADO = "6d85fa2686f4160522920b1078b0b4f6ec6d146788420f76d5ace1153d482c0c"   # requirements.txt em f523035
+SHA256_ANTERIOR = "9003ceceddaf2b8a7f4d23b443b4620343fdab9f0cb445c087d3f7405551fc1c"     # requirements.txt em f523035^
+LINHAS_ACRESCENTADAS = ("", "# Instalar também o solver MILP–MPC do EMS V2 no ambiente de deploy Streamlit.",
+                        "-r requirements-ems_v2.txt")
+
+
+def autorizado(root: Path) -> bool:
+    try:
+        return hashlib.sha256((Path(root) / ARQUIVO).read_bytes()).hexdigest() == SHA256_AUTORIZADO
+    except OSError:
+        return False
+
+
+def filter_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
+    """Remove SÓ ``["M", "requirements.txt"]`` e só com o conteúdo exato de ``f523035``."""
+    ok = autorizado(root)
+    return [row for row in changes if not (ok and len(row) == 2 and row[0] == "M" and row[1] == ARQUIVO)]
+
+
+__all__ = ["ARQUIVO", "COMMIT", "LINHAS_ACRESCENTADAS", "SHA256_ANTERIOR", "SHA256_AUTORIZADO", "autorizado", "filter_changes"]
diff --git a/tests/ems_v2/piso3db_guard_policy.py b/tests/ems_v2/piso3db_guard_policy.py
index 2a9ea53..62a6197 100644
--- a/tests/ems_v2/piso3db_guard_policy.py
+++ b/tests/ems_v2/piso3db_guard_policy.py
@@ -78,6 +78,8 @@ def auditar_missao(root: Path, base: str = BASE, head: str = "HEAD", *, incluir_
     linhas = [ln.split("\t") for ln in git("diff", "--name-status", "--no-renames", base, *alvo).splitlines() if ln.strip()]
     if incluir_arvore_de_trabalho:
         linhas += [["A", p] for p in git("ls-files", "--others", "--exclude-standard").split()]
+    from deploy_requirements_guard_policy import filter_changes as filter_deploy      # C-DEPLOY-01: só f523035, byte a byte
+    linhas = filter_deploy(root, linhas)
     intocados = [ln for ln in linhas if any(ln[1] == p or ln[1].startswith(p.rstrip("/") + "/") for p in INTOCADOS)]
     fora = [ln for ln in linhas if not (
         (ln[0] == "M" and ln[1] in MODIFICADOS) or (ln[0] == "A" and ln[1] in ADICIONADOS)
diff --git a/tests/ems_v2/ui_running01_guard_policy.py b/tests/ems_v2/ui_running01_guard_policy.py
index 9a81933..c25315b 100644
--- a/tests/ems_v2/ui_running01_guard_policy.py
+++ b/tests/ems_v2/ui_running01_guard_policy.py
@@ -16,14 +16,15 @@ from pathlib import Path
 BASE = "9d2bcf0"                                        # main no início da missão (merge do PR #26)
 MODIFICADOS: frozenset = frozenset()
 ADICIONADOS = frozenset({"seeds2/ui/static/trama/execucao.js", "tests/test_ui_running01.py",
-                         "tests/ems_v2/ui_running01_guard_policy.py"})
+                         "tests/ems_v2/ui_running01_guard_policy.py", "tests/ems_v2/deploy_requirements_guard_policy.py"})
 
 
 def filter_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
     """Política pura: nomes E status exatos. Remoção, renomeação ou qualquer outro arquivo continuam visíveis."""
-    _ = root
-    return [row for row in changes if not (len(row) == 2 and (
+    restantes = [row for row in changes if not (len(row) == 2 and (
         (row[0] == "M" and row[1] in MODIFICADOS) or (row[0] == "A" and row[1] in ADICIONADOS)))]
+    from deploy_requirements_guard_policy import filter_changes as filter_deploy      # C-DEPLOY-01 (fim da cadeia)
+    return filter_deploy(root, restantes)
 
 
 INTOCADOS = ("ems_v2", "models", "h2_pemfc", "simulation", "config", "ems_integration", "reference_models", "visualization",
```
