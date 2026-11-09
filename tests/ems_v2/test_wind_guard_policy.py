"""Authorized guard scope: adverse edits must fail, not just the happy path.

All mutations use copies, in-memory records or temporary Git repositories.
No production file, original hash or golden output is modified by these tests.
"""
from copy import deepcopy
from pathlib import Path
import json
import subprocess

import pytest

from wind_guard_policy import (SUPPORT_ADDITIONS, assert_context, assert_ems_unchanged,
                               assert_guard_file, assert_historical_records, assert_original_hashes,
                               assert_pinned_file, authorized_additions, authorized_changes,
                               expected_guard_source, filter_changes, read_policy)

ROOT = Path(__file__).resolve().parents[2]
POLICY = read_policy(ROOT)
OLD = ('Nordex N117/2400', 'Vestas V164-7.0 MW', 'Siemens SWT-3.6-120', 'Vestas V90-3.0 MW',
       'EWT DW61-1MW', 'WEG AGW 147 / 4.2')


def test_only_three_guards_changed_and_no_ems_code_exception():
    assert set(POLICY['original_guards']) == {
        'tests/ems_v2/test_ems_v2_ponte_isolamento.py',
        'tests/ems_v2/test_ems_v2_3c2_isolamento.py',
        'tests/ems_v2/test_ems_v2_3c3_isolamento.py',
    }
    paths = set(POLICY['modified_files']) | set(POLICY['added_files']) | SUPPORT_ADDITIONS
    assert all('*' not in p and not p.endswith('/') for p in paths)
    assert not any(p.startswith('ems_v2/') for p in paths)
    assert_context(ROOT)


def test_original_hashes_reconstructable_from_frozen_commits():
    assert POLICY['base_commit'] == '10365c5478b4dd137906b58819cd7f71d8de9cea'
    assert POLICY['approved_wind_commit'] == '5bc42834e03b6206e88d987f58dbc1b1eae7f5df'
    assert_original_hashes(ROOT, POLICY)
    assert_historical_records(ROOT)


@pytest.mark.parametrize('path', sorted(POLICY['modified_files']))
def test_every_authorized_existing_file_rejects_even_an_internal_extra_edit(tmp_path, path):
    file = tmp_path / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes((ROOT / path).read_bytes())
    digest = POLICY['modified_files'][path]['approved_sha256']
    assert_pinned_file(tmp_path, path, digest)
    file.write_bytes(file.read_bytes() + b'\n# unsolicited edit inside a nominally authorized file\n')
    with pytest.raises(AssertionError, match='edição não autorizada'):
        assert_pinned_file(tmp_path, path, digest)


@pytest.mark.parametrize('key', OLD)
@pytest.mark.parametrize('target', ['parameter', 'curve'])
def test_each_historical_record_is_protected_inside_the_authorized_database(key, target):
    from config.wind_turbine_database import TURBINE_DB
    entries = deepcopy(TURBINE_DB)
    if target == 'parameter':
        entries[key]['spec']['rated_power_kw'] += 0.001
    else:
        v,p = entries[key]['curve']['points'][0]
        entries[key]['curve']['points'][0] = (v,p + 0.001)
    with pytest.raises(AssertionError, match='históricos alterados'):
        assert_historical_records(ROOT, entries)


def test_historical_density_family_is_protected_too():
    from config.wind_turbine_database import TURBINE_DB
    entries = deepcopy(TURBINE_DB)
    entries['Nordex N117/2400']['curve']['density_curves'][1.0][0] = (3.0, 100.)
    with pytest.raises(AssertionError, match='históricos alterados'):
        assert_historical_records(ROOT, entries)


@pytest.mark.parametrize('path', ['ems_v2/compromisso/auditor.py', 'ems_v2/mpc/orquestrador.py',
                                  'ems_v2/rede/mpc.py', 'ems_v2/planejador_3c4.py',
                                  'models/single_diode.py', 'models/battery_model.py',
                                  'h2_pemfc/model.py', 'seeds2/microgrid/registry.py',
                                  'config/wind_curves/intruder.csv', 'tests/test_unapproved.py'])
@pytest.mark.parametrize('status', ['A', 'M', 'D'])
def test_exact_names_never_authorize_another_file_or_directory(path, status):
    changes = [[status, path]]
    assert filter_changes(changes, POLICY) == changes
    assert authorized_changes(ROOT, changes) == changes
    assert authorized_additions(ROOT, [path]) == [path]


@pytest.mark.parametrize('path', sorted(POLICY['modified_files']))
@pytest.mark.parametrize('status', ['D', 'R100', 'T', 'A'])
def test_nominal_modified_file_does_not_authorize_deletion_rename_type_or_recreation(path, status):
    row = [status,path]
    assert filter_changes([row],POLICY) == [row]


@pytest.mark.parametrize('path', sorted(POLICY['original_guards']))
@pytest.mark.parametrize('mutation', ['append', 'remove_assertion'])
def test_guards_only_accept_exact_insertions_and_retain_every_original_assertion(tmp_path,path,mutation):
    original = subprocess.check_output(['git','show',POLICY['base_commit']+':'+path],cwd=ROOT)
    expected = expected_guard_source(path, original)
    file = tmp_path / path
    file.parent.mkdir(parents=True,exist_ok=True)
    file.write_bytes(expected)
    digest = POLICY['original_guards'][path]
    assert_guard_file(tmp_path,path,original,digest)
    bad = expected + b'\n# any other change\n' if mutation == 'append' else expected.replace(b'    assert ',b'    # removed assert ',1)
    assert bad != expected
    file.write_bytes(bad)
    with pytest.raises(AssertionError):
        assert_guard_file(tmp_path,path,original,digest)


def test_manifest_cannot_be_rewritten_to_accept_a_new_hash(tmp_path):
    file=tmp_path/'tests/fixtures/wind_guard_policy_v1.json'
    file.parent.mkdir(parents=True)
    modified=deepcopy(POLICY)
    modified['modified_files']['models/wind_model.py']['approved_sha256']='0'*64
    file.write_text(json.dumps(modified))
    with pytest.raises(AssertionError,match='manifesto fixo'):
        read_policy(tmp_path)


@pytest.mark.parametrize('path', ['ems_v2/compromisso/auditor.py', 'ems_v2/mpc/orquestrador.py',
                                  'ems_v2/rede/mpc.py', 'ems_v2/planejador_3c4.py'])
@pytest.mark.parametrize('mutation', ['modify', 'delete', 'add_staged', 'add_untracked'])
def test_real_git_diff_detects_edits_deletions_and_additions_in_all_ems_floors(tmp_path,path,mutation):
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=tmp_path,stderr=subprocess.STDOUT)
    git('init','-q')
    file=tmp_path/path
    file.parent.mkdir(parents=True)
    file.write_text('# original EMS sentinel\n')
    git('add',path)
    git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','original')
    base=git('rev-parse','HEAD').decode().strip()
    assert_ems_unchanged(tmp_path,base)
    if mutation=='delete': file.unlink()
    elif mutation=='modify': file.write_text('# unauthorized change\n')
    else:
        extra=file.with_name('unauthorized_3c4.py')
        extra.write_text('# unauthorized addition\n')
        if mutation=='add_staged': git('add',str(extra.relative_to(tmp_path)))
    with pytest.raises(AssertionError,match='EMS V2 alterado'):
        assert_ems_unchanged(tmp_path,base)


def test_symlink_with_correct_contents_is_not_an_authorized_replacement(tmp_path):
    path='models/wind_model.py'; file=tmp_path/path
    file.parent.mkdir(parents=True)
    file.symlink_to(ROOT/path)
    with pytest.raises(AssertionError,match='symlink'):
        assert_pinned_file(tmp_path,path,POLICY['modified_files'][path]['approved_sha256'])
