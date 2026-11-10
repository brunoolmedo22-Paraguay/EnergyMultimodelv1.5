"""CI-01 adversaries: rounding is allowed only within a fixed independent bound."""
from copy import deepcopy
import gzip
import hashlib
from pathlib import Path
import shutil

import numpy as np
import pytest

import ci01_guard_policy as G
from config.wind_turbine_database import get_turbine
from models import wind_model as W
from tools.ci import wind_historical_comparison as C

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT/'docs/estabilizacao/ci01_evidencia'


@pytest.fixture(scope='module')
def experiment():
    raw = W.read_wind_csv(ROOT/'Dados_exemplo/perfil_eolico_sintetico_ceara_1_semana_10min.csv')
    cols = W.detect_columns(raw.columns)
    profile = W.prepare_wind_profile(raw, W.WindInputMapping(**{
        key: cols[key] for key in W.WindInputMapping.__annotations__}))
    import json
    historical = json.loads((ROOT/'tests/fixtures/wind_historical_v1.json').read_text())
    return profile, historical


@pytest.mark.parametrize('index', range(6))
def test_canonical_and_controlled_portable_arrays_are_both_protected(experiment, index):
    profile, historical = experiment
    key = list(historical['entries'])[index]
    for name in ('formal-solver', 'formal-no-solver', 'formal-no-avx512'):
        with np.load(EVIDENCE/name/'arrays.npz') as data:
            C.assert_historical_power(data[f'weather_{index}_power'], key, 'weather', profile,
                                      get_turbine(key), historical['weather'][key]['power_sha256'])


@pytest.mark.parametrize('mutation', ['point', 'gain', 'energy_cancel', 'ulp_budget', 'dtype', 'nan', 'inf', 'shape', 'negative', 'hash', 'entry'])
def test_significant_or_structural_changes_fail_even_if_kpis_are_not_recomputed(experiment, mutation):
    profile, historical = experiment
    key = list(historical['entries'])[0]
    with np.load(EVIDENCE/'formal-no-avx512/arrays.npz') as data:
        power = data['weather_0_power'].copy()
    entry = deepcopy(get_turbine(key))
    expected = historical['weather'][key]['power_sha256']
    if mutation == 'point': power[16, 0] += 1e-6
    elif mutation == 'gain': power *= 1+1e-10
    elif mutation == 'energy_cancel':
        power[16, 2] += 1e-6
        power[17, 2] -= 1e-6  # Conservation of total energy cannot conceal altered dispatch.
    elif mutation == 'ulp_budget': power[16, 0] += 32*np.spacing(power[16, 0])
    elif mutation == 'dtype': power = power.astype('float32')
    elif mutation == 'nan': power[16, 0] = np.nan
    elif mutation == 'inf': power[16, 0] = np.inf
    elif mutation == 'shape': power = power[:-1]
    elif mutation == 'negative': power[16, 0] = -0.0
    elif mutation == 'hash': expected = hashlib.sha256(power.tobytes()).hexdigest()
    elif mutation == 'entry': entry['spec']['rated_power_kw'] += .001
    with pytest.raises(AssertionError):
        C.assert_historical_power(power, key, 'weather', profile, entry, expected)


def test_boundaries_always_require_the_original_hash(experiment):
    _, historical = experiment
    key = list(historical['entries'])[0]
    with np.load(EVIDENCE/'formal-solver/arrays.npz') as data:
        power = data['boundaries_0_power'].copy()
    power[100, 0] = np.nextafter(power[100, 0], np.inf)
    with pytest.raises(AssertionError, match='boundary hash'):
        C.assert_historical_power(power, key, 'boundaries', None, get_turbine(key),
                                  historical['boundaries'][key]['power_sha256'])


def test_retained_arrays_cannot_redefine_the_original_hash(tmp_path, monkeypatch, experiment):
    profile, historical = experiment
    key = list(historical['entries'])[0]
    fixture = tmp_path/'tests/fixtures/wind_historical_v1.json'
    fixture.parent.mkdir(parents=True)
    shutil.copyfile(ROOT/'tests/fixtures/wind_historical_v1.json', fixture)
    retained_path = tmp_path/'docs/estabilizacao/ci01_evidencia/formal-solver/arrays.npz'
    retained_path.parent.mkdir(parents=True)
    with np.load(EVIDENCE/'formal-solver/arrays.npz') as source:
        changed = source['weather_0_power'].copy()
    changed[16, 0] += 1e-6
    np.savez_compressed(retained_path, weather_0_power=changed)
    with np.load(EVIDENCE/'formal-no-avx512/arrays.npz') as source:
        actual = source['weather_0_power']
    monkeypatch.setattr(C, 'ROOT', tmp_path)
    with pytest.raises(AssertionError, match='retained historical bytes'):
        C.assert_historical_power(actual, key, 'weather', profile, get_turbine(key),
                                  historical['weather'][key]['power_sha256'])


@pytest.mark.parametrize('path', list(C.SOURCE_SHA256))
def test_changes_to_scientific_sources_or_original_fixture_are_rejected(tmp_path, path):
    for source in C.SOURCE_SHA256:
        target = tmp_path/source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/source, target)
    C.assert_sources(tmp_path)
    with (tmp_path/path).open('ab') as file:
        file.write(b'\n# unauthorized edit\n')
    with pytest.raises(AssertionError, match='protected source'):
        C.assert_sources(tmp_path)


def copy_context(target):
    for path in (G.TEST, G.ORIGINAL, *G.SUPPORT_SHA256):
        file = target/path
        file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/path, file)


@pytest.mark.parametrize('path', [G.TEST, G.ORIGINAL, *G.SUPPORT_SHA256])
def test_extra_edits_inside_explicitly_allowed_files_are_rejected(tmp_path, path):
    copy_context(tmp_path)
    G.assert_context(tmp_path)
    with (tmp_path/path).open('ab') as file:
        file.write(b'\n# unauthorized budget/oracle/assertion edit\n')
    with pytest.raises(AssertionError):
        G.assert_context(tmp_path)


def test_all_other_original_assertions_remain_byte_identical():
    original = gzip.decompress((ROOT/G.ORIGINAL).read_bytes())
    expected = G.expected_test(original)
    assert expected == (ROOT/G.TEST).read_bytes()
    assert expected.replace(G.NEW_ASSERTION.encode(), G.OLD_ASSERTION.encode()) == original
    assert b"assert k == BASE[mode][key]['kpis']" in expected


def test_ci01_exceptions_are_exact_names_and_statuses():
    wanted = [['M', 'ems_v2/planejador_3c4.py'], ['M', 'models/wind_model.py'],
              ['A', 'tools/ci/unapproved.py'], ['D', 'tools/ci/wind_historical_comparison.py'],
              ['R100', G.TEST, 'renamed.py'], ['M', 'tests/test_wind_model.py']]
    allowed = [['A', path] for path in G.ADDITIONS]
    assert G.filter_changes(ROOT, wanted+allowed) == wanted


def test_ci01_guard_implementation_itself_is_pinned(tmp_path):
    import stabilization_guard_policy as maintenance
    target = tmp_path/'tests/ems_v2/ci01_guard_policy.py'
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT/'tests/ems_v2/ci01_guard_policy.py').read_bytes()+b'\n# altered\n')
    with pytest.raises(AssertionError, match='CI-01 policy'):
        maintenance.assert_ci01_context(tmp_path)
