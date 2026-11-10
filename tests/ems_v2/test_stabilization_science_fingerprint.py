"""The run provenance must cover preparation as well as the numerical engine."""
from pathlib import Path

import pytest

from seeds2.operation import runner as R


@pytest.mark.parametrize('path', [
    'seeds2/operation/mission.py', 'seeds2/operation/preflight.py',
    'seeds2/operation/runner.py', 'seeds2/microgrid/adapter.py',
    'seeds2/microgrid/config.py', 'seeds2/microgrid/references.py',
    'config/wind_curves/manifest.json', 'models/wind_model.py',
    'ems_integration/despacho.py'])
def test_each_execution_dependency_changes_the_fingerprint(tmp_path, monkeypatch, path):
    for rel in R.SCIENCE_PATHS:
        p = tmp_path / rel
        if Path(rel).suffix:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('baseline')
        else:
            p.mkdir(parents=True, exist_ok=True)
            (p/'module.py').write_text('baseline')
    p = tmp_path/path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('before')
    monkeypatch.setattr(R, 'ROOT', tmp_path)
    monkeypatch.setattr(R, '_SCIENCE_FP', None)
    before = R.science_fingerprint()
    p.write_text('after')
    monkeypatch.setattr(R, '_SCIENCE_FP', None)
    assert R.science_fingerprint()['sha256'] != before['sha256'], path


def test_experimental_ems_is_not_a_runtime_dependency(tmp_path, monkeypatch):
    monkeypatch.setattr(R, 'ROOT', tmp_path)
    monkeypatch.setattr(R, '_SCIENCE_FP', None)
    first = R.science_fingerprint()['sha256']
    (tmp_path/'ems_v2').mkdir()
    (tmp_path/'ems_v2/experimental.py').write_text('unrelated experimental floor')
    monkeypatch.setattr(R, '_SCIENCE_FP', None)
    assert R.science_fingerprint()['sha256'] == first
