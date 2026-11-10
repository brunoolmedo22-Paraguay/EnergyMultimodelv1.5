"""CI-01 nominal comparison revision; immutable original evidence is retained.

Only one assertion is replaced, with its original bytes verified first. Every
other assertion in the original module must remain byte-identical. New support
is pinned separately, never by updating the old wind/stabilization manifests.
"""
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

TEST = 'tests/test_wind_catalog_expansion.py'
ORIGINAL = 'docs/estabilizacao/ci01_evidencia/test_wind_catalog_expansion_original.py.gz'
ORIGINAL_GZIP_SHA256 = 'd9e8749330a095bb8c8f54ba1b2bcb83f6205d619709914fd90bf90b6d13dff4'
ORIGINAL_SHA256 = '7ab1b71cf1b7328e404aeef49943cedf64e1a651effaaf30bb9b7d8548a4be2a'
SUPPORT_SHA256 = {
    'tools/ci/wind_historical_comparison.py': '6d6c0f456f8175f0ca54b4a252854ad838f94156e48ffa514f6b364eca997633',
    'tools/ci/wind_decimal_reference.py': '3290f1ae7068d8b8c409b92d17c04b730a885f084ba04fb02acb4b2c7f0897c5',
    'tests/ems_v2/test_ci01_wind_reproducibility.py': '575f3e090445edd38d69fc51609713da80f4cb1bd120105a63b7b25bf858dbfd',
}
ADDITIONS = frozenset({*SUPPORT_SHA256, 'tests/ems_v2/ci01_guard_policy.py'})
OLD_ASSERTION = "    assert hashlib.sha256(r[['power_unit_kw', 'power_gross_kw', 'power_net_kw']].to_numpy().tobytes()).hexdigest() == BASE[mode][key]['power_sha256']\n"
NEW_ASSERTION = (
    '    from tools.ci.wind_historical_comparison import assert_historical_power\n'
    "    assert_historical_power(r[['power_unit_kw', 'power_gross_kw', 'power_net_kw']].to_numpy(),\n"
    "                            key, mode, p, entry, BASE[mode][key]['power_sha256'])\n"
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def expected_test(original):
    assert sha(original) == ORIGINAL_SHA256, 'CI-01 original test evidence changed'
    assert original.count(OLD_ASSERTION.encode()) == 1
    return original.replace(OLD_ASSERTION.encode(), NEW_ASSERTION.encode())


def assert_context(root: Path, old_expected=ORIGINAL_SHA256):
    assert old_expected == ORIGINAL_SHA256, 'CI-01 cannot replace an original hash'
    source = root/ORIGINAL
    assert source.is_file() and not source.is_symlink()
    compressed = source.read_bytes()
    assert sha(compressed) == ORIGINAL_GZIP_SHA256, 'CI-01 documentary evidence changed'
    expected = expected_test(gzip.decompress(compressed))
    test = root/TEST
    assert test.is_file() and not test.is_symlink()
    assert test.read_bytes() == expected, 'CI-01 unauthorized historical assertion edit'
    for path, digest in SUPPORT_SHA256.items():
        file = root/path
        assert file.is_file() and not file.is_symlink(), path
        assert sha(file.read_bytes()) == digest, f'CI-01 support changed: {path}'


def filter_changes(root: Path, changes):
    assert_context(root)
    return [row for row in changes if not (len(row) == 2 and row[0] == 'A' and row[1] in ADDITIONS)]
