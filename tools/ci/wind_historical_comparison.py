"""CI-01: strict historical evidence plus a CPU-portable weather calculation.

Production physics is never patched. The original fixture and all its hashes
remain immutable. Only noncanonical weather bytes receive the independent
80-digit check; boundary cases still require the original byte hash.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from tools.ci.wind_decimal_reference import weather_power

ROOT = Path(__file__).resolve().parents[2]
MAX_ULP = 16
SOURCE_SHA256 = {
    'models/wind_model.py': 'cde9fe0bdd4bf765fe0dc47bafd40b1b8a0a7aa30fa1f41efd86b61938d59721',
    'config/wind_turbine_database.py': 'a200c31db31ec60f8c224a9ed7400d44c93b4a28432829d4d338da0b58ec8915',
    'tests/fixtures/wind_historical_v1.json': 'd148d917cc5dd31271deff689a34117abb8c79f15348299f0c3322b86f686e00',
    'Dados_exemplo/perfil_eolico_sintetico_ceara_1_semana_10min.csv': 'cb0e7ec7261721279f313c097a1403737d894d5d4844de9778656c0eec4b84d1',
}


def assert_sources(root=ROOT):
    for path, expected in SOURCE_SHA256.items():
        file = root / path
        assert file.is_file() and not file.is_symlink(), path
        assert hashlib.sha256(file.read_bytes()).hexdigest() == expected, f'CI-01 protected source: {path}'


def assert_historical_power(power, key, mode, profile, entry, expected_sha256):
    assert_sources()
    historical = json.loads((ROOT/'tests/fixtures/wind_historical_v1.json').read_text())
    assert mode in ('weather', 'boundaries') and key in historical['entries']
    assert expected_sha256 == historical[mode][key]['power_sha256'], 'historical hash changed'
    assert hashlib.sha256(json.dumps(entry, sort_keys=True, allow_nan=False).encode()).hexdigest() == historical['entries'][key]
    assert power.dtype == np.dtype('float64'), 'historical dtype'
    assert power.shape == (1008 if mode == 'weather' else 601, 3), 'historical shape'
    assert np.isfinite(power).all(), 'nonfinite power'
    assert (power >= 0).all() and not np.signbit(power[power == 0]).any(), 'power/zero sign'
    if hashlib.sha256(power.tobytes()).hexdigest() == expected_sha256:
        return  # The original byte-for-byte evidence is still checked first.
    assert mode == 'weather', 'boundary hash must remain exact'
    # Recover the original bytes from the diagnostic export, authenticated by
    # the UNCHANGED historical fixture. This file cannot redefine expectations.
    index = list(historical['entries']).index(key)
    with np.load(ROOT/'docs/estabilizacao/ci01_evidencia/formal-solver/arrays.npz', allow_pickle=False) as retained:
        canonical = retained[f'weather_{index}_power']
    assert hashlib.sha256(canonical.tobytes()).hexdigest() == expected_sha256, 'retained historical bytes'
    reference = weather_power(profile, entry)
    for expected in (canonical, reference):
        assert np.array_equal(power[expected == 0].view('u8'), expected[expected == 0].view('u8')), 'zero representation'
        actual_bits, reference_bits = power.view('u8'), expected.view('u8')
        ulp = np.maximum(actual_bits, reference_bits) - np.minimum(actual_bits, reference_bits)
        assert int(ulp.max()) <= MAX_ULP, f'CI-01 weather exceeds {MAX_ULP} ULP: {int(ulp.max())}'
    # A separate integrated bound; the caller ALSO retains the original exact
    # KPI-dictionary assertion. No regenerated KPI or allclose is involved.
    assert profile.attrs['timestep_hours'] == 1/6
    for column in range(3):
        residual = abs(math.fsum(map(float, (power-reference)[:, column]))) / 6
        budget = MAX_ULP * math.fsum(map(float, np.spacing(reference[:, column]))) / 6
        assert residual <= budget, 'CI-01 integrated energy bound'
