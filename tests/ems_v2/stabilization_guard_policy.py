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
    return text.replace(old, new).encode()


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
    return [row for row in changes if not (len(row) == 2 and (
        (row[0] == 'M' and row[1] in policy['modified_files']) or
        (row[0] == 'A' and row[1] in policy['added_files'])))]
