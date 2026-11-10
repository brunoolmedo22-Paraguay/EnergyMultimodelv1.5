"""Fault injection on the real prepare path; never modifies physics or stored data."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from seeds2.ui import operations as O


def plan(uid='B',fingerprint='B'):
    p=SimpleNamespace(microgrid_uid=uid,spec_fingerprint=fingerprint,config_revision=2,
                      config_fingerprint=fingerprint,load_descriptor=None,climate_descriptor=None,
                      spec={'identity':uid},runnable=True,needs_ack=False,blockers=[],excluded=[])
    p.provenance=lambda:{'origin':'microrrede','microgrid_uid':uid,'config_revision':2,'config_fingerprint':fingerprint}
    return p


@pytest.fixture
def state(monkeypatch):
    ss={'orchestrator_page':'Otimizador','orq_model_spec':{'identity':'A'},'orq_load':'old-A-load',
        'orq_result_item':{'id':1,'origem':{'microgrid_uid':'A'}},'orq_history':[{'id':1}]}
    monkeypatch.setattr(O.st,'session_state',ss)
    monkeypatch.setattr(O,'_sync_view_with_page',lambda v:v)
    monkeypatch.setattr(O.session,'saved',lambda:SimpleNamespace(config={},revision=2,fingerprint='B'))
    monkeypatch.setattr(O.session,'active_uid',lambda:'B')
    monkeypatch.setattr(O.A,'build_plan',lambda *a,**k:plan())
    monkeypatch.setattr(O,'_state_hash',lambda:str(ss.get('orq_model_spec'))+str(ss.get('orq_load')))
    ss['orq_mg_applied']={'microgrid_uid':'A','spec_fingerprint':'A','state_hash':O._state_hash()}
    return ss


def test_unsolicited_partial_transfer_error_cannot_enable_manual_execution(state,monkeypatch):
    before=deepcopy(state['orq_result_item'])
    def fail(p):
        state['orq_model_spec']=p.spec
        raise OSError('controlled B transfer error')
    monkeypatch.setattr(O,'_apply',fail)
    O.prepare('simulacao')
    assert not state['orq_run_gate']['ok']
    assert state['orq_spec_origin']['origin']!='manual'
    assert not state.get('orq_manual')
    assert state['orq_result_item']==before
    O.prepare('simulacao')
    assert not state['orq_run_gate']['ok']


@pytest.mark.parametrize('stage', ['load', 'climate'])
def test_real_apply_rolls_back_partial_state_and_preserves_history(state, monkeypatch, stage):
    p = plan()
    p.load_descriptor = {'source': 'csv'}
    p.climate_descriptor = {'source': 'csv'}
    monkeypatch.setattr(O.A, 'build_plan', lambda *a, **k: p)
    monkeypatch.setattr(O.session, 'store', lambda: SimpleNamespace(get_blob=lambda x: b''))
    before = deepcopy(state)
    def fail(*args):
        raise OSError('controlled unreadable blob')
    monkeypatch.setattr(O.A, 'build_load', fail if stage == 'load' else lambda *args: 'B load')
    monkeypatch.setattr(O.A, 'build_climate_raw', fail)
    O.prepare('simulacao')
    assert not state['orq_run_gate']['ok']
    for key in before:
        assert state[key] == before[key], key
    assert 'orq_climate_raw' not in state
    assert 'orq_load_mode' not in state


def successful_transfer(state):
    def apply(p):
        state['orq_model_spec'] = deepcopy(p.spec)
        state['orq_mg_applied'] = {k: getattr(p, k) for k in (
            'microgrid_uid', 'spec_fingerprint', 'config_revision', 'config_fingerprint')}
        state['orq_mg_applied']['state_hash'] = O._state_hash()
        state.pop('orq_manual', None)
    return apply


def test_failed_target_is_latched_until_explicit_retry(state, monkeypatch):
    calls = []
    def fail(p):
        calls.append(p)
        raise OSError('B unavailable')
    monkeypatch.setattr(O, '_apply', fail)
    O.prepare('simulacao')
    state['orq_model_spec'] = {'manual edit': 'cannot bypass failed transfer'}
    state['orq_manual'] = True
    for view in ('simulacao', 'resultados', 'simulacao'):
        O.prepare(view)
        assert not state['orq_run_gate']['ok']
        assert state['orq_spec_origin']['origin'] == 'indisponivel'
    assert len(calls) == 1
    monkeypatch.setattr(O, '_apply', successful_transfer(state))
    O.prepare('simulacao')
    assert not state['orq_run_gate']['ok']
    state['mg_retry_transfer'] = True
    O.prepare('simulacao')
    assert state['orq_run_gate']['ok']
    assert state['orq_spec_origin']['microgrid_uid'] == 'B'
    assert not state.get('mg_apply_error')
    assert not state.get('mg_retry_transfer')


def test_new_saved_target_retries_while_same_target_does_not(state, monkeypatch):
    monkeypatch.setattr(O, '_apply', lambda p: (_ for _ in ()).throw(OSError('B missing')))
    O.prepare('simulacao')
    p = plan('C', 'C')
    monkeypatch.setattr(O.A, 'build_plan', lambda *a, **k: p)
    monkeypatch.setattr(O.session, 'active_uid', lambda: 'C')
    monkeypatch.setattr(O, '_apply', successful_transfer(state))
    O.prepare('simulacao')
    assert state['orq_run_gate']['ok']
    assert state['orq_spec_origin']['microgrid_uid'] == 'C'
    assert not state.get('mg_failed_transfer')


@pytest.mark.parametrize('uid', [None, 'B'])
def test_session_without_saved_config_is_manual_only_without_microgrid(state, monkeypatch, uid):
    state.clear()
    monkeypatch.setattr(O.session, 'saved', lambda: None)
    monkeypatch.setattr(O.session, 'active_uid', lambda: uid)
    O.prepare('simulacao')
    assert state['orq_run_gate']['ok'] == (uid is None)
    assert state['orq_spec_origin']['origin'] == ('manual' if uid is None else 'indisponivel')


def test_intentional_console_edit_remains_manual_without_microgrid_attribution(state, monkeypatch):
    monkeypatch.setattr(O, '_apply', successful_transfer(state))
    O.prepare('simulacao')
    assert state['orq_spec_origin']['origin'] == 'microrrede'
    state['orq_model_spec']['identity'] = 'user edited spec'
    O.prepare('simulacao')
    assert state['orq_run_gate']['ok']
    assert state['orq_spec_origin']['origin'] == 'manual'
    assert not state['orq_spec_origin'].get('microgrid_uid')


@pytest.mark.parametrize('runnable,needs_ack,ack,expected', [
    (True,False,False,True), (False,False,False,False),
    (True,True,False,False), (True,True,True,True)])
def test_valid_transfer_retains_existing_preflight_and_ack_gate(state, monkeypatch, runnable, needs_ack, ack, expected):
    p = plan()
    p.runnable, p.needs_ack = runnable, needs_ack
    p.blockers = ['missing compatible demand'] if not runnable else []
    p.excluded = ['thermal'] if needs_ack else []
    monkeypatch.setattr(O.A, 'build_plan', lambda *a, **k: p)
    monkeypatch.setattr(O, '_apply', successful_transfer(state))
    if ack: state['mg_ack_fp'] = O._ack_token(p)
    O.prepare('simulacao')
    assert state['orq_run_gate']['ok'] is expected
    assert state['orq_spec_origin']['microgrid_uid'] == 'B'


@pytest.mark.parametrize('origin,active,planned,records', [
    ('manual','B','B',0), ('microrrede','C','B',0),
    ('microrrede','B','C',0), ('microrrede','B','B',1)])
def test_after_run_never_records_manual_or_cross_grid_results(state, monkeypatch, origin, active, planned, records):
    calls = []
    monkeypatch.setattr(O.session, 'active_uid', lambda: active)
    def record(**kw):
        calls.append(kw)
        return 7
    monkeypatch.setattr(O.session, 'store', lambda: SimpleNamespace(record_run=record))
    item = {'origem': {'origin': origin, 'microgrid_uid': 'B'}, 'resultado': {
        'rel': {'custo_total_rs': 1, 'energia_nao_atendida_kWh': 0, 'energia_vertida_kWh': 0}, 'k_validos': 2}}
    O._after_run_hook(plan(planned))(item)
    assert len(calls) == records
    assert bool(item['origem'].get('run_id')) == bool(records)
    assert state['orq_history'] == [{'id': 1}]


def test_switch_microgrid_reset_clears_transfer_references_only(monkeypatch):
    ss = {'orq_mg_applied': {'microgrid_uid': 'A'}, 'orq_model_spec': {'A': 1},
          'mg_failed_transfer': ('A',), 'mg_apply_error': 'A failure', 'orq_after_run': object(),
          'mg_active_uid': 'A', 'seeds_route': 'gestor', 'mg_flash': 'preserved navigation'}
    monkeypatch.setattr(O.session.st, 'session_state', ss)
    O.session.reset_state()
    assert ss == {'seeds_route': 'gestor', 'mg_flash': 'preserved navigation'}


@pytest.mark.parametrize('failure', [PermissionError('storage is not writable'),
    __import__('sqlite3').OperationalError('database is readonly')])
def test_unwritable_storage_has_a_controlled_startup_error(monkeypatch, failure):
    from streamlit.testing.v1 import AppTest
    from seeds2.ui import session
    def unavailable():
        raise failure
    monkeypatch.setattr(session, 'registry', unavailable)
    app = AppTest.from_string('from seeds2.ui.main import render\nrender(lambda: None)').run()
    assert not app.exception
    assert len(app.error) == 1
    assert 'Armazenamento do SEEDS2 indisponível' in app.error[0].value
    assert str(failure) in app.error[0].value


def test_invalid_thermal_input_does_not_show_traceback_or_residual_results(monkeypatch):
    import pandas as pd
    import thermal_app
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string("import streamlit as st\nst.session_state['thermal_page'] = 'Simulação'\n"
                              "from thermal_app import render_thermal_app\nrender_thermal_app()").run()
    next(b for b in app.button if b.label == '▶ CALCULAR MODELO TÉRMICO').click().run()
    assert not app.exception
    original = app.session_state['thermal_result'].copy(deep=True)
    monkeypatch.setattr(thermal_app, 'read_thermal_csv', lambda *a: pd.DataFrame({
        'timestamp': ['invalid','invalid'], 'power_requested_mw': [1.,2.]}))
    next(b for b in app.button if b.label == '▶ CALCULAR MODELO TÉRMICO').click().run()
    assert not app.exception
    assert any('Não foi possível avaliar o programa' in e.value for e in app.error)
    assert not app.main.metric
    pd.testing.assert_frame_equal(app.session_state['thermal_result'], original, check_exact=True)


def test_changed_revision_cannot_reuse_exclusion_consent_for_identical_engine_spec(state, monkeypatch):
    a = plan()
    a.needs_ack, a.excluded = True, ['large thermal A']
    monkeypatch.setattr(O.A, 'build_plan', lambda *a_, **k: a)
    monkeypatch.setattr(O, '_apply', successful_transfer(state))
    state['mg_ack_fp'] = O._ack_token(a)
    O.prepare('simulacao')
    assert state['orq_run_gate']['ok']
    b = deepcopy(a)
    b.config_revision = 3
    b.config_fingerprint = 'B-new-excluded-equipment'
    b.excluded = ['large thermal A', 'large thermal B']
    monkeypatch.setattr(O.A, 'build_plan', lambda *a_, **k: b)
    O.prepare('simulacao')
    assert not state['orq_run_gate']['ok'], 'a new exclusion requires new conscious consent'
    assert O._ack_token(a) != O._ack_token(b), 'checkbox identity must also change'


def test_real_inventories_with_new_exclusions_have_equal_effective_spec_but_distinct_consent():
    from seeds2_fixtures import v16_equivalent_config
    from seeds2.microgrid import config as C
    from seeds2.microgrid.adapter import build_plan
    cfg = v16_equivalent_config('exclusion consent fixture')
    def add(name):
        C.add_equipment(cfg, C.new_equipment('thermal', name, params={
            'dynamic':'thermal_plant','pmax_kW':500.,'pmin_kW':100.,'cvu_rs_MWh':420.,'startup_cost_rs':0.}))
    add('excluded A')
    a = build_plan(cfg, revision=1, fingerprint='config A')
    add('excluded B')
    b = build_plan(cfg, revision=2, fingerprint='config B')
    assert a.spec_fingerprint == b.spec_fingerprint
    assert len(a.excluded) == 1 and len(b.excluded) == 2
    assert O._ack_token(a) != O._ack_token(b)
