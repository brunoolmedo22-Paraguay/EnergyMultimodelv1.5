"""Adversarial coverage of the narrowly scoped maintenance evidence."""
from pathlib import Path
import importlib.util
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('maintenance_scope', ROOT/'tests/ems_v2/stabilization_guard_policy.py')
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def test_maintenance_exceptions_are_exact_names_and_statuses():
    wanted = [['M','ems_v2/hierarquia/planejador.py'], ['A','ems_v2/hierarquia/unapproved.py'],
              ['M','models/wind_model.py'], ['M','config/wind_turbine_database.py'],
              ['M','tests/test_wind_model.py'], ['D','seeds2/ui/operations.py'],
              ['R100','seeds2/ui/operations.py','renamed.py'], ['A','tests/estabilizacao/unapproved.py']]
    allowed = [['M','seeds2/ui/operations.py'], ['M','seeds2/operation/runner.py'], ['M','seeds2/ui/main.py'], ['M','thermal_app.py'],
               ['A','tests/estabilizacao/test_operations_fail_closed.py']]
    assert G.filter_maintenance_changes(ROOT, wanted + allowed) == wanted


@pytest.mark.parametrize('path', ['seeds2/ui/operations.py', 'seeds2/operation/runner.py', 'seeds2/ui/main.py', 'thermal_app.py',
                                'tests/ems_v2/wind_guard_policy.py', 'tests/fixtures/stabilization_scope_v1.json'])
def test_modification_inside_allowed_files_is_rejected(tmp_path, path):
    for source in ('seeds2/ui/operations.py', 'seeds2/operation/runner.py', 'seeds2/ui/main.py', 'thermal_app.py',
                   'tests/ems_v2/wind_guard_policy.py', 'tests/fixtures/stabilization_scope_v1.json'):
        target = tmp_path/source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/source, target)
    with (tmp_path/path).open('ab') as f:
        f.write(b'\n# unauthorized edit\n')
    with pytest.raises(AssertionError):
        G.filter_maintenance_changes(tmp_path, [])


def test_policy_and_original_evidence_work_without_git_history(tmp_path):
    for source in ('seeds2/ui/operations.py', 'seeds2/operation/runner.py', 'seeds2/ui/main.py', 'thermal_app.py',
                   'tests/ems_v2/wind_guard_policy.py', 'tests/fixtures/stabilization_scope_v1.json'):
        target = tmp_path/source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/source, target)
    assert G.read_policy(tmp_path)['base_commit'] == G.BASE
    assert not (tmp_path/'.git').exists()
