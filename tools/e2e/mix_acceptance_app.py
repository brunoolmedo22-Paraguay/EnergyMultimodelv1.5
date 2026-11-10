"""Test entry point for the implemented legacy MIX bench (no current shell link).

This only selects its existing router state, once per session. The production
entry point and physics are executed unchanged. Not an application feature.
"""
from pathlib import Path
import runpy
import sys
import streamlit as st

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
if '_acceptance_mix_selected' not in st.session_state:
    st.session_state['_acceptance_mix_selected'] = True
    st.session_state['energy_source'] = 'mix'
runpy.run_path(str(root/'app.py'), run_name='__main__')
