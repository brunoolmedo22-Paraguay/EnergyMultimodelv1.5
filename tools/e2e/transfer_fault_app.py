"""Test-only fault injector around the real app; storage must be disposable.

The button saves a real revision B (one fewer PEMFC unit) and raises after the
transfer has written its state. No production hook or physical model is changed.
"""
from pathlib import Path
import copy
import runpy
import sys
import streamlit as st

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from seeds2.ui import operations, session
from seeds2.microgrid import config as C

if not hasattr(operations, '_acceptance_original_apply'):
    operations._acceptance_original_apply = operations._apply


def controlled_apply(plan):
    operations._acceptance_original_apply(plan)
    if st.session_state.pop('_acceptance_fail_transfer', False):
        raise OSError('controlled failure after transfer of revision B')


operations._apply = controlled_apply
runpy.run_path(str(root/'app.py'), run_name='__main__')
if session.active_uid() and st.button('ACEPTACIÓN: guardar B y fallar transferencia'):
    saved = session.saved()
    config = copy.deepcopy(saved.config)
    fc = next(e for e in config['equipment'] if e['kind'] == 'pemfc')
    fc['params']['quantity'] -= 1
    session.store().save(config, expected_revision=saved.revision, note='Synthetic acceptance revision B')
    st.session_state['_acceptance_fail_transfer'] = True
    st.rerun()
if session.active_uid() and st.button('ACEPTACIÓN: agregar equipo excluido'):
    saved = session.saved()
    config = copy.deepcopy(saved.config)
    C.add_equipment(config, C.new_equipment('thermal', f'Exclusión de prueba rev. {saved.revision}', params={
        'dynamic':'thermal_plant', 'pmax_kW':500., 'pmin_kW':100., 'cvu_rs_MWh':420., 'startup_cost_rs':0.}))
    session.store().save(config, expected_revision=saved.revision, note='Synthetic excluded equipment')
    st.rerun()
