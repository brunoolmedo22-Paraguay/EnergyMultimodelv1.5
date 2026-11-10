"""Exact maintenance exceptions; all scientific and historical guards stay active.

The four corrected application files are pinned, including their retained base
bytes. No EMS path, mathematical model, dataset, old fixture or directory is
exempted. This module never regenerates evidence or fetches Git history.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = '5d6ed4ee75978467339b5323a44e892c2a060ee2adcb7a30f1915ce8d8fdf881'
BASE = '5e6267833538716678125ab962fc645cfee53eb0'
CI01_POLICY_SHA256 = '6ede487888579c3e4138f2e086615a5e16f0744b65b74aea6f014aefb9ff4b1d'
CI01_PIN_INSERTION = (
    '    if path == "tests/test_wind_catalog_expansion.py":\n'
    '        from stabilization_guard_policy import assert_ci01_context\n'
    '        assert_ci01_context(root, expected_sha256)\n'
    '        return\n'
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def expected_wind_support(original: bytes) -> bytes:
    text = original.decode()
    old = '    return filter_changes(changes, assert_context(root))'
    new = ('    from stabilization_guard_policy import filter_maintenance_changes\n'
           '    return filter_maintenance_changes(root, filter_changes(changes, assert_context(root)))')
    assert text.count(old) == 1
    text = text.replace(old, new)
    old = '    return [path for path in paths if path not in allowed]'
    new = ('    from stabilization_guard_policy import filter_maintenance_changes\n'
           '    return [row[1] for row in filter_maintenance_changes(root,\n'
           '        [["A", path] for path in paths if path not in allowed])]')
    assert text.count(old) == 1
    text = text.replace(old, new)
    old = '    assert _sha(file.read_bytes()) == expected_sha256, f"edição não autorizada dentro de {path}"'
    assert text.count(old) == 1
    return text.replace(old, CI01_PIN_INSERTION + old).encode()


def assert_ci01_context(root: Path, old_expected=None):
    path = root/'tests/ems_v2/ci01_guard_policy.py'
    assert path.is_file() and not path.is_symlink(), 'CI-01 policy missing'
    assert sha(path.read_bytes()) == CI01_POLICY_SHA256, 'CI-01 policy changed'
    # Import only after checking the approved implementation bytes.
    from ci01_guard_policy import assert_context
    if old_expected is None:
        assert_context(root)
    else:
        assert_context(root, old_expected)


def read_policy(root: Path) -> dict:
    raw = (root/'tests/fixtures/stabilization_scope_v1.json').read_bytes()
    assert sha(raw) == MANIFEST_SHA256, 'evidência de estabilização alterada'
    policy = json.loads(raw)
    assert policy['base_commit'] == BASE
    for path, pins in policy['modified_files'].items():
        assert sha(base64.b64decode(pins['original_base64'], validate=True)) == pins['original_sha256']
        actual = root/path
        assert not actual.is_symlink() and actual.is_file(), path
        assert sha(actual.read_bytes()) == pins['approved_sha256'], f'correção de estabilização alterada: {path}'
    original = base64.b64decode(policy['wind_support_original_base64'], validate=True)
    assert sha(original) == policy['wind_support_original_sha256']
    assert (root/'tests/ems_v2/wind_guard_policy.py').read_bytes() == expected_wind_support(original), 'suporte eólico alterado'
    return policy


def filter_maintenance_changes(root: Path, changes: list[list[str]]) -> list[list[str]]:
    policy = read_policy(root)
    # Names AND statuses. Rename, deletion and changes to old test assertions
    # remain visible to the original isolation guard.
    retained = [row for row in changes if not (len(row) == 2 and (
        (row[0] == 'M' and row[1] in policy['modified_files']) or
        (row[0] == 'A' and row[1] in policy['added_files'])))]
    assert_ci01_context(root)
    from ci01_guard_policy import filter_changes
    retained = filter_changes(root, retained)
    # Piso 3D-A (C-3DA-01): exceção NOMINAL da integração operacional autorizada — nomes e status exatos; nenhuma
    # das exceções anteriores (eólica, estabilização, CI-01) é alterada e os arquivos fixados continuam fixados.
    from piso3da_guard_policy import filter_changes as filter_piso3da
    return filter_piso3da(root, retained)
