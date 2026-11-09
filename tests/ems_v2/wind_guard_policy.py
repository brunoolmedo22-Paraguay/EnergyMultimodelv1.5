"""Nominal wind exceptions authorized by the user; no EMS exception is introduced.

Pins come from immutable commits, NOT from the current working tree. No code in
this module writes or refreshes hashes. Unexpected edits inside allowed files
fail just like edits to a forbidden path. The old delivery audits use retained, hashed evidence rather than the moving
working tree. Current wind data stay pinned; EMS PR diff auditing is explicit,
so an independently integrated EMS floor is not frozen against the wind base.
"""
from __future__ import annotations

import ast
import base64
import hashlib
import json
import subprocess
from pathlib import Path

EVIDENCE_SHA256 = "b3e81f4c658f07c97d242a1fa0ab2cd01b362bd22cea4f0363931d367f54c316"
AUDITED_WIND_HEAD = "96215438e0d4d57bcf600f62b5ae3f2d3c25da9d"
INTEGRATION_SHA256 = "662de6976b6ca7a6883442273d978bc6913b4547a34f9f0eb8ebd9b544439ce7"
INTEGRATION_BASE = "19aa3ac328f337e31ec4c36baa837c056299a57a"
MANIFEST_SHA256 = "4c9303ee2296e2edbc999cb28523382a3adc45bab47248150e7793d60f08926d"
# New verification support only; never directories/patterns or runtime EMS files.
SUPPORT_ADDITIONS = frozenset({
    "tests/ems_v2/wind_guard_policy.py",
    "tests/ems_v2/test_wind_guard_policy.py",
    "tests/fixtures/wind_guard_policy_v1.json",
    "tests/fixtures/wind_guard_evidence_v1.json",
    "tests/fixtures/wind_3c4_integration_v1.json",
    "tests/ems_v2/test_wind_3c4_integration.py",
})


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_policy(root: Path) -> dict:
    raw = (root / "tests/fixtures/wind_guard_policy_v1.json").read_bytes()
    assert _sha(raw) == MANIFEST_SHA256, "manifesto fixo da missão eólica alterado"
    return json.loads(raw)


def read_evidence(root: Path) -> dict:
    raw = (root / "tests/fixtures/wind_guard_evidence_v1.json").read_bytes()
    assert _sha(raw) == EVIDENCE_SHA256, "evidência histórica da missão alterada"
    evidence = json.loads(raw)
    assert evidence["mission_base"] == read_policy(root)["base_commit"]
    assert evidence["mission_head"] == AUDITED_WIND_HEAD
    return evidence


def original_bytes(root: Path, path: str) -> bytes:
    return base64.b64decode(read_evidence(root)["original_files"][path], validate=True)


def historical_changes(root: Path, base: str) -> list[list[str]]:
    """The old guards audit their fixed delivery, not all future integration work."""
    report = read_evidence(root)["guard_audits"][base]
    assert report["base_commit"].startswith(base) and report["head_commit"] == AUDITED_WIND_HEAD
    return [row.copy() for row in report["changes"]]


def historical_untracked(root: Path, base: str) -> list[str]:
    return list(read_evidence(root)["guard_audits"][base]["untracked"])


GUARD_BODIES = {
    "tests/ems_v2/test_ems_v2_ponte_isolamento.py": """def test_v16_e_aplicacao_sem_alteracao_desde_a_base_auditada():
    # C-EOL-01: immutable delivery audit; current wind data remain pinned separately.
    from wind_guard_policy import authorized_changes, authorized_additions, historical_changes, historical_untracked
    linhas = authorized_changes(RAIZ, historical_changes(RAIZ, BASE_AUDITADA))
    modificados = [ln for ln in linhas if ln[0] != "A"]
    adicionados = {ln[1] for ln in linhas if ln[0] == "A"}
    assert modificados == [], modificados                    # nenhum arquivo da base alterado ou removido
    assert adicionados <= ADICOES_3C1 | ADICOES_3C3 | ADICOES_3C4, adicionados - ADICOES_3C1 - ADICOES_3C3 - ADICOES_3C4
    nao_rastreados = authorized_additions(RAIZ, historical_untracked(RAIZ, BASE_AUDITADA))
    assert set(nao_rastreados) <= ADICOES_3C1 | ADICOES_3C3 | ADICOES_3C4, set(nao_rastreados) - ADICOES_3C1 - ADICOES_3C3 - ADICOES_3C4""",
    "tests/ems_v2/test_ems_v2_3c2_isolamento.py": """def test_pisos_anteriores_v16_e_aplicacao_sem_alteracao_desde_o_merge_do_pr14():
    # C-EOL-01: immutable delivery audit, independent of shallow Git history.
    from wind_guard_policy import authorized_changes, historical_changes, historical_untracked
    linhas = authorized_changes(RAIZ, historical_changes(RAIZ, BASE_3C1))
    assert [ln for ln in linhas if ln[0] != "A" and ln[1:] not in (["ems_v2/mpc/orquestrador.py"], ["ems_v2/ponte/execucao.py"])] == []
    assert all(ln[0] in ("A", "M") for ln in linhas)
    novos = {ln[1] for ln in linhas if ln[0] == "A"}
    nao_rastreados = set(historical_untracked(RAIZ, BASE_3C1))
    from test_ems_v2_ponte_isolamento import ADICOES_3C3, ADICOES_3C4
    for f in novos | nao_rastreados:
        assert (f.startswith(("ems_v2/mpc/", "ems_v2/rede/", "ems_v2/hierarquia/")) or f in ("ems_v2/fixtures_3c2.py", "ems_v2/fixtures_3c3.py", "ems_v2/fixtures_3c4.py")
                or f in ADICOES_3C3 | ADICOES_3C4), f""",
    "tests/ems_v2/test_ems_v2_3c3_isolamento.py": """def test_pisos_anteriores_v16_e_aplicacao_sem_alteracao_desde_o_merge_do_pr15():
    # C-EOL-01: later authorized floors are not changes to this frozen delivery.
    from wind_guard_policy import authorized_changes, authorized_additions, historical_changes, historical_untracked
    linhas = authorized_changes(RAIZ, historical_changes(RAIZ, BASE_3C2))
    alterados = {ln[1] for ln in linhas if ln[0] != "A"}
    assert alterados <= MODIFICADOS_3C3, alterados - MODIFICADOS_3C3
    assert all(ln[0] in ("A", "M") for ln in linhas)
    novos = {ln[1] for ln in linhas if ln[0] == "A"} | set(historical_untracked(RAIZ, BASE_3C2))
    from test_ems_v2_ponte_isolamento import ADICOES_3C3, ADICOES_3C4
    novos = set(authorized_additions(RAIZ, novos))
    for f in novos:
        assert (f.startswith(("ems_v2/rede/", "tests/ems_v2/test_ems_v2_3c3_", "tests/ems_v2/dados/", "ems_v2/hierarquia/", "tests/ems_v2/test_ems_v2_3c4_"))
                or f in ADICOES_3C3 | ADICOES_3C4 or f in ("ems_v2/fixtures_3c3.py", "ems_v2/fixtures_3c4.py")), f""",
}


def expected_guard_source(path: str, original: bytes) -> bytes:
    """Retain the entire original module except its explicitly scoped audit body."""
    text = original.decode("utf-8")
    replacement = GUARD_BODIES[path]
    name = replacement.split("(", 1)[0].removeprefix("def ")
    node, = [n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name]
    lines = text.splitlines(keepends=True)
    return ("".join(lines[:node.lineno - 1]) + replacement + "\n" + "".join(lines[node.end_lineno:])).encode("utf-8")


def assert_pinned_file(root: Path, path: str, expected_sha256: str) -> None:
    file = root / path
    assert not file.is_symlink(), f"symlink não autorizado: {path}"
    assert file.is_file(), f"arquivo autorizado ausente: {path}"
    assert _sha(file.read_bytes()) == expected_sha256, f"edição não autorizada dentro de {path}"


def assert_guard_file(root: Path, path: str, original: bytes, original_sha256: str) -> None:
    assert _sha(original) == original_sha256, f"original da guarda alterado: {path}"
    file = root / path
    assert not file.is_symlink(), path
    expected, = ast.parse(GUARD_BODIES[path]).body
    actual = [n for n in ast.parse(file.read_bytes()).body
              if isinstance(n, ast.FunctionDef) and n.name == expected.name]
    # Only the wind audit function is protected here. Other floors may add
    # independently reviewed tests without repinning a whole historical module.
    assert len(actual) == 1 and ast.dump(actual[0]) == ast.dump(expected), path


def assert_original_hashes(root: Path, policy: dict) -> None:
    # Same original SHA-256 values, verified from retained bytes even at depth 1.
    for path, pins in policy["modified_files"].items():
        assert _sha(original_bytes(root, path)) == pins["original_sha256"], path
    for path, digest in policy["original_guards"].items():
        assert _sha(original_bytes(root, path)) == digest, path


def _git_object_oid(kind: str, data: bytes) -> str:
    return hashlib.sha1(f"{kind} {len(data)}\0".encode() + data).hexdigest()


def _proved_ems_tree(evidence: dict, commit_oid: str) -> str:
    proof = evidence["git_proofs"][commit_oid]
    commit = base64.b64decode(proof["commit"], validate=True)
    tree = base64.b64decode(proof["root_tree"], validate=True)
    assert _git_object_oid("commit", commit) == commit_oid, "identidade do commit de auditoria inválida"
    assert commit.splitlines()[0] == ("tree " + proof["root_tree_oid"]).encode()
    assert _git_object_oid("tree", tree) == proof["root_tree_oid"], "árvore Git de auditoria inválida"
    pos, matches = 0, []
    while pos < len(tree):
        end = tree.index(b"\0", pos)
        mode, name = tree[pos:end].split(b" ", 1)
        oid = tree[end + 1:end + 21]
        assert len(oid) == 20
        if name == b"ems_v2":
            assert mode == b"40000"
            matches.append(oid.hex())
        pos = end + 21
    assert pos == len(tree) and len(matches) == 1
    return matches[0]


def assert_frozen_mission_ems(root: Path) -> str:
    # Git-object identities bind the EMS subtree to the two published commits;
    # no old object database, remote ref or network fetch is required.
    evidence = read_evidence(root)
    base_tree = _proved_ems_tree(evidence, evidence["mission_base"])
    assert base_tree == _proved_ems_tree(evidence, evidence["mission_head"]), "missão eólica registrada alterou EMS"
    return base_tree


def assert_historical_records(root: Path, entries: dict | None = None) -> None:
    # Fixture is itself pinned by assert_context. Independent numerical output
    # regression remains in test_wind_catalog_expansion, never in a regenerated pin.
    if entries is None:
        from config.wind_turbine_database import TURBINE_DB
        entries = TURBINE_DB
    expected = json.loads((root / "tests/fixtures/wind_historical_v1.json").read_bytes())["entries"]
    for key, digest in expected.items():
        value = json.dumps(entries[key], sort_keys=True, allow_nan=False).encode()
        assert _sha(value) == digest, f"parâmetros/curva históricos alterados: {key}"


def read_integration_evidence(root: Path) -> dict:
    raw = (root / "tests/fixtures/wind_3c4_integration_v1.json").read_bytes()
    assert _sha(raw) == INTEGRATION_SHA256, "evidência da integração 3C-4 alterada"
    record = json.loads(raw)
    assert record["main_commit"] == INTEGRATION_BASE
    assert _sha(record["guard_source"].encode()) == record["guard_sha256"]
    _proved_ems_tree(record, INTEGRATION_BASE)
    return record


def combined_3c4_guard_source(original: str) -> str:
    # All scientific assertions remain ACTIVE against the actual integrated EMS.
    marker = '    linhas = [ln.split("\\t") for ln in out.strip().splitlines() if ln.strip()]\n'
    assert original.count(marker) == 1
    combined = original.replace(marker, marker +
        '    from wind_guard_policy import authorized_changes, authorized_additions\n'
        '    linhas = authorized_changes(RAIZ, linhas)  # nominal wind exceptions only\n')
    return combined.replace('    for f in novos:\n',
                            '    novos = set(authorized_additions(RAIZ, novos))\n    for f in novos:\n')


def assert_3c4_guards(root: Path) -> None:
    record = read_integration_evidence(root)
    expected = ast.parse(combined_3c4_guard_source(record["guard_source"]))
    actual = ast.parse((root / record["guard_path"]).read_bytes())
    # Every upstream function and constant is retained, not just the scope test.
    # Adding future independent tests is allowed; removing/changing a scientific
    # check (B3C4-01, B3C4-10, C-01, A03) requires its own reviewed revision.
    def members(tree):
        return {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef)}
    want, have = members(expected), members(actual)
    assert all(have.get(k) == v for k, v in want.items()), "guarda científica 3C-4 alterada"
    constants = lambda tree: [ast.dump(n) for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
    assert constants(actual) == constants(expected), "exceções científicas 3C-4 alteradas"


def assert_ems_unchanged(root: Path, base: str, head: str = "HEAD", *, include_worktree: bool = True) -> None:
    """Explicit PR/mission audit ONLY. Never a permanent constraint on future EMS.

    The caller supplies the base/head of the mission being audited. For PR #18,
    the retained proof also resolves its base in shallow clones. A later PR must
    supply its own base; committing an EMS edit inside the audited range fails.
    """
    def tree_at(ref: str) -> str:
        result = subprocess.run(["git", "rev-parse", "--verify", f"{ref}:ems_v2"], cwd=root, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        evidence = read_evidence(root)
        if ref == INTEGRATION_BASE:
            evidence = read_integration_evidence(root)
        assert ref in evidence["git_proofs"], f"base/head de missão indisponível: {ref}"
        return _proved_ems_tree(evidence, ref)
    assert tree_at(base) == tree_at(head), "EMS V2 alterado/adicionado/removido nesta missão eólica"
    if include_worktree:
        changes = subprocess.check_output(["git", "diff", "--name-status", "--no-renames", head, "--", "ems_v2"], cwd=root)
        untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", "ems_v2"], cwd=root)
        assert not changes and not untracked, "EMS V2 alterado/adicionado/removido nesta missão eólica"


def assert_curve_inventory(root: Path, policy: dict) -> None:
    expected = {p for p in policy["added_files"] if p.startswith("config/wind_curves/")}
    actual = {p.relative_to(root).as_posix() for p in (root / "config/wind_curves").rglob("*") if p.is_file() or p.is_symlink()}
    assert actual == expected, f"arquivo eólico não autorizado/ausente: {actual ^ expected}"


def assert_context(root: Path) -> dict:
    policy = read_policy(root)
    assert_original_hashes(root, policy)
    for path, pins in policy["modified_files"].items():
        assert_pinned_file(root, path, pins["approved_sha256"])
    for path, digest in policy["added_files"].items():
        assert_pinned_file(root, path, digest)
    for path, digest in policy["original_guards"].items():
        original = original_bytes(root, path)
        assert_guard_file(root, path, original, digest)
    assert_frozen_mission_ems(root)
    assert_3c4_guards(root)
    assert_curve_inventory(root, policy)
    assert_historical_records(root)
    return policy


def filter_changes(changes: list[list[str]], policy: dict) -> list[list[str]]:
    """Pure policy: exact names AND statuses; deletion/rename are never exempt."""
    modifications = set(policy["modified_files"]) | set(policy["original_guards"])
    additions = set(policy["added_files"]) | SUPPORT_ADDITIONS
    return [row for row in changes if not (
        len(row) == 2 and ((row[0] == "M" and row[1] in modifications)
                          or (row[0] == "A" and row[1] in additions)))]


def authorized_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
    return filter_changes(changes, assert_context(root))


def authorized_additions(root: Path, paths) -> list[str]:
    policy = assert_context(root)
    allowed = set(policy["added_files"]) | SUPPORT_ADDITIONS
    return [path for path in paths if path not in allowed]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Auditar explicitamente o diff EMS desta missão/PR; não congela versões futuras.")
    parser.add_argument("--audit-mission-base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    import sys
    sys.path.insert(0, str(root))
    assert_context(root)
    assert_ems_unchanged(root, args.audit_mission_base, args.head)
    print("Auditoria explícita da missão: EMS inalterado; catálogo e referências históricas íntegros.")
