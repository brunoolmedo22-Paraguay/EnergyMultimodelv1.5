"""Nominal wind exceptions authorized by the user; no EMS exception is introduced.

Pins come from immutable commits, NOT from the current working tree. No code in
this module writes or refreshes hashes. Unexpected edits inside allowed files
fail just like edits to a forbidden path. Original three guard bodies remain
byte-identical except for the exact filtering statements reconstructed below.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

MANIFEST_SHA256 = "4c9303ee2296e2edbc999cb28523382a3adc45bab47248150e7793d60f08926d"
# New verification support only; never directories/patterns or runtime EMS files.
SUPPORT_ADDITIONS = frozenset({
    "tests/ems_v2/wind_guard_policy.py",
    "tests/ems_v2/test_wind_guard_policy.py",
    "tests/fixtures/wind_guard_policy_v1.json",
})


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_policy(root: Path) -> dict:
    raw = (root / "tests/fixtures/wind_guard_policy_v1.json").read_bytes()
    assert _sha(raw) == MANIFEST_SHA256, "manifesto fixo da missão eólica alterado"
    return json.loads(raw)


def _git_bytes(root: Path, ref: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=root)


def expected_guard_source(path: str, original: bytes) -> bytes:
    """Only these literal insertions are permitted; every old assertion is retained."""
    text = original.decode("utf-8")
    marker = '    linhas = [ln.split("\\t") for ln in out.strip().splitlines() if ln.strip()]\n'
    assert text.count(marker) == 1, path
    text = text.replace(marker, marker +
        '    from wind_guard_policy import authorized_changes, authorized_additions\n'
        '    linhas = authorized_changes(RAIZ, linhas)  # missão eólica: arquivos/pins exatos\n')
    if path == "tests/ems_v2/test_ems_v2_ponte_isolamento.py":
        before = "    assert set(nao_rastreados) <= ADICOES_3C1 | ADICOES_3C3, set(nao_rastreados) - ADICOES_3C1 - ADICOES_3C3"
        assert before in text
        # Keep the original assertion verbatim; narrow its input, not its protection.
        text = text.replace(before,
            "    nao_rastreados = authorized_additions(RAIZ, nao_rastreados)\n" + before)
    elif path == "tests/ems_v2/test_ems_v2_3c3_isolamento.py":
        text = text.replace("    for f in novos:\n", "    novos = set(authorized_additions(RAIZ, novos))\n    for f in novos:\n")
    else:
        assert path == "tests/ems_v2/test_ems_v2_3c2_isolamento.py"
    return text.encode("utf-8")


def assert_pinned_file(root: Path, path: str, expected_sha256: str) -> None:
    file = root / path
    assert not file.is_symlink(), f"symlink não autorizado: {path}"
    assert file.is_file(), f"arquivo autorizado ausente: {path}"
    assert _sha(file.read_bytes()) == expected_sha256, f"edição não autorizada dentro de {path}"


def assert_guard_file(root: Path, path: str, original: bytes, original_sha256: str) -> None:
    assert _sha(original) == original_sha256, f"original da guarda alterado: {path}"
    file = root / path
    assert not file.is_symlink() and file.read_bytes() == expected_guard_source(path, original), path


def assert_original_hashes(root: Path, policy: dict) -> None:
    # Reconstructable Git references: no substituted remote tip, skip or auto-update.
    for path, pins in policy["modified_files"].items():
        assert _sha(_git_bytes(root, policy["base_commit"], path)) == pins["original_sha256"], path
        assert _sha(_git_bytes(root, policy["approved_wind_commit"], path)) == pins["approved_sha256"], path
    for path, digest in policy["added_files"].items():
        assert _sha(_git_bytes(root, policy["approved_wind_commit"], path)) == digest, path
    for path, digest in policy["original_guards"].items():
        assert _sha(_git_bytes(root, policy["base_commit"], path)) == digest, path


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


def assert_ems_unchanged(root: Path, base: str) -> None:
    changes = subprocess.check_output(["git", "diff", "--name-status", "--no-renames", base, "--", "ems_v2"], cwd=root)
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", "ems_v2"], cwd=root)
    assert not changes and not untracked, "EMS V2 alterado/adicionado/removido nesta missão eólica"


def assert_context(root: Path) -> dict:
    policy = read_policy(root)
    assert_original_hashes(root, policy)
    for path, pins in policy["modified_files"].items():
        assert_pinned_file(root, path, pins["approved_sha256"])
    for path, digest in policy["added_files"].items():
        assert_pinned_file(root, path, digest)
    for path, digest in policy["original_guards"].items():
        original = _git_bytes(root, policy["base_commit"], path)
        assert_guard_file(root, path, original, digest)
    assert_ems_unchanged(root, policy["base_commit"])
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
