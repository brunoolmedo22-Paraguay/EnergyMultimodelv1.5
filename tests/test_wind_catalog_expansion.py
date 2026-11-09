"""E-01..E-20: independent wind expansion acceptance and adversarial checks.

Original CSV bytes are read independently from the supplied evidence ZIP.
The six historical entry/output hashes were captured BEFORE implementation.
"""
import csv
import hashlib
import io
import json
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from config.wind_turbine_database import (HISTORICAL_TURBINE_KEYS, TURBINE_DB, get_turbine,
                                         list_models, validate_database, validate_turbine_entry)
from models.wind_model import (WindInputMapping, _strict_power, analyze_wind_curve, detect_columns,
                               evaluate_documented_curve, prepare_wind_profile, read_wind_csv, run_wind_model)

ROOT = Path(__file__).resolve().parents[1]
A = {'Vergnet GEV MP C 275 kW': 'vergnet275.csv', 'Vestas V47-660 kW': 'vestas47.csv',
     'Vestas V52-850 kW OptiSpeed': 'vestas52.csv'}
B = {'Bergey Excel 10': ('BergeyExcel10_8.9kW_7.csv', 12.555),
     'Bergey Excel 15': ('BergeyExcel15_15.6kW_9.6.csv', 20.611),
     'Kestrel e400nb': ('Kestrele400nb_2.5kW_4.csv', 3.025), 'SWIFT': ('SWIFT_1kW_2.1.csv', 1.430)}
OLD = ('Nordex N117/2400', 'Vestas V164-7.0 MW', 'Siemens SWT-3.6-120', 'Vestas V90-3.0 MW',
       'EWT DW61-1MW', 'WEG AGW 147 / 4.2')
BASE = json.loads((ROOT / 'tests/fixtures/wind_historical_v1.json').read_text())


def profile(speeds):
    return prepare_wind_profile(pd.DataFrame({'t': pd.date_range('2026-01-01', periods=len(speeds), freq='10min'),
                                              'v': speeds}), WindInputMapping('t', 'v'))


def test_e18_exact_thirteen_and_single_catalog():
    from seeds2.microgrid.references import wind_references
    from seeds2.microgrid.config import choices
    assert set(TURBINE_DB) == set(OLD) | set(A) | set(B)
    assert tuple(HISTORICAL_TURBINE_KEYS) == OLD
    assert set(list_models()) == set(wind_references()) == set(choices('wind', 'reference')) == set(TURBINE_DB)
    assert validate_database() == []


@pytest.mark.parametrize('key', OLD)
@pytest.mark.parametrize('mode', ['weather', 'boundaries'])
def test_e01_historical_entries_and_outputs_bit_for_bit(key, mode):
    entry = TURBINE_DB[key]
    digest = hashlib.sha256(json.dumps(entry, sort_keys=True, allow_nan=False).encode()).hexdigest()
    assert digest == BASE['entries'][key]
    if mode == 'weather':
        raw = read_wind_csv(ROOT / 'Dados_exemplo/perfil_eolico_sintetico_ceara_1_semana_10min.csv')
        cols = detect_columns(raw.columns)
        p = prepare_wind_profile(raw, WindInputMapping(**{k: cols[k] for k in WindInputMapping.__annotations__}))
    else:
        p = profile(np.linspace(0, 30, 601))
    r, k, _ = run_wind_model(p, key, 2, True)
    assert hashlib.sha256(r[['power_unit_kw', 'power_gross_kw', 'power_net_kw']].to_numpy().tobytes()).hexdigest() == BASE[mode][key]['power_sha256']
    assert k == BASE[mode][key]['kpis']


@pytest.mark.parametrize('key', [*A, *B])
def test_e02_e08_e09_original_csv_every_node_and_units(key):
    entry = get_turbine(key)
    filename = A.get(key) or B[key][0]
    member = ('curvas_potencia/' if key in A else 'evidencia/nrel_data/') + filename
    with ZipFile(ROOT / 'docs/eolica/evidencia/SEEDS2_CODEX_7_EOLICAS_INPUT.zip') as z:
        raw = z.read(member)
    assert raw == (ROOT / 'config/wind_curves' / filename).read_bytes()
    points = np.asarray([(float(r[0]), float(r[1])) for r in list(csv.reader(io.StringIO(raw.decode())))[1:]])
    np.testing.assert_array_equal(entry['curve']['points'], points)
    assert np.isfinite(points).all() and np.all(np.diff(points[:, 0]) > 0)
    assert entry['curve']['units'] == {'wind_speed': 'm/s', 'power': 'kW'}
    np.testing.assert_array_equal(evaluate_documented_curve(entry, points[:, 0]), points[:, 1])
    mid = (points[:-1, 0] + points[1:, 0]) / 2
    np.testing.assert_allclose(evaluate_documented_curve(entry, mid), (points[:-1, 1] + points[1:, 1]) / 2)
    if key in B:
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        assert blob == entry['source']['archive_blob_sha']


@pytest.mark.parametrize('key', B)
def test_e03_e06_e14_e15_e16_peak_scaling_and_accounting(key):
    e = get_turbine(key); pts = np.asarray(e['curve']['points']); speeds = pts[:, 0]
    r, k = analyze_wind_curve(key, speeds, timestep_hours=0.25)
    r3, k3 = analyze_wind_curve(key, speeds, timestep_hours=0.25, turbine_count=3, apply_generic_grid_loss=True)
    assert r['curve_net_power_unit_kw'].max() == B[key][1] > e['spec']['rated_power_kw']
    np.testing.assert_allclose(r3.generation_power_kw, r.generation_power_kw * 3)
    np.testing.assert_allclose(r3.observed_auxiliary_import_kw, r.observed_auxiliary_import_kw * 3)
    np.testing.assert_allclose(r3.net_exchange_kw, (r.generation_power_kw * .97 - r.observed_auxiliary_import_kw) * 3)
    assert k3['energy_generated_kwh'] == pytest.approx(3 * k['energy_generated_kwh'])
    assert k3['energy_net_kwh'] == pytest.approx(k3['energy_generated_kwh'] - k3['energy_consumed_kwh'] - k3['energy_external_loss_kwh'])
    assert k3['capacity_factor_generated'] == pytest.approx(k['capacity_factor_generated'])
    assert 'rated_power_kw' in k['capacity_factor_denominator']
    peak_v = speeds[np.argmax(pts[:, 1])]
    _, peak = analyze_wind_curve(key, np.array([peak_v]), timestep_hours=1)
    assert peak['capacity_factor_generated'] > 1
    if key == 'SWIFT':
        assert r.curve_net_power_unit_kw.iloc[-1] < r.curve_net_power_unit_kw.max()


@pytest.mark.parametrize('key', B)
def test_e10_no_silent_auxiliary_clipping_or_integration(key):
    from seeds2.microgrid import config as C
    from seeds2.microgrid.adapter import build_plan
    from seeds2_fixtures import v16_equivalent_config
    e = get_turbine(key);pts = np.asarray(e['curve']['points'])
    r, k = analyze_wind_curve(key, pts[:, 0], timestep_hours=1)
    np.testing.assert_array_equal(r.curve_net_power_unit_kw, pts[:, 1])
    assert k['energy_consumed_kwh'] == pytest.approx(-pts[pts[:, 1] < 0, 1].sum())
    assert e['spec']['reference_air_density_kg_m3'] is None
    assert e['spec']['cut_out_mps'] is None
    with pytest.raises(ValueError, match='Somente análise'):
        run_wind_model(profile([10.]), key)
    cfg = v16_equivalent_config()
    eq = C.new_equipment('wind', key, params={'reference': key, 'count': 2, 'apply_grid_loss': False})
    cfg['equipment'].append(eq)
    assert C.missing_required(eq)
    plan = build_plan(cfg)
    assert not plan.spec['wind']['active']


@pytest.mark.parametrize('key', [*A, *B])
@pytest.mark.parametrize('offset', [-0.001, 0.001])
def test_e11_outside_domain_rejected(key, offset):
    e = get_turbine(key);lo, hi = e['curve']['curve_valid_wind_range_mps']
    with pytest.raises(ValueError, match='não modelada'):
        evaluate_documented_curve(e, np.array([lo+offset if offset < 0 else hi+offset]))
    # Truncating the curve does not justify a constant extension.
    truncated = deepcopy(e); truncated['curve']['points'] = truncated['curve']['points'][:-1]
    assert validate_turbine_entry(truncated)


@pytest.mark.parametrize('key', A)
def test_e12_e13_controller_and_both_density_domains(key):
    e = get_turbine(key);ci, co = e['spec']['cut_in_mps'], e['spec']['cut_out_mps']
    r, k, _ = run_wind_model(profile([0., ci-0.01, ci, 12., 24., co, 30.]), key)
    np.testing.assert_array_equal(r.power_unit_kw.iloc[[0,1,5,6]], 0.)
    assert r.power_unit_kw.iloc[2] == evaluate_documented_curve(e, np.array([ci]))[0]
    assert k['installed_power_kw'] == e['spec']['rated_power_kw']
    assert k['installed_curve_peak_power_kw'] == e['spec']['curve_peak_power_kw']
    with pytest.raises(ValueError, match='não modelada'):
        _strict_power(e, np.array([24.9]), np.array([1.5]))
    # Actual wind is out of documented domain despite equivalent speed inside it.
    other = deepcopy(e); other['spec']['cut_out_mps'] = None
    with pytest.raises(ValueError, match='não modelada'):
        _strict_power(other, np.array([26.]), np.array([1.0]))
    with pytest.raises(ValueError, match='não modelada'):
        _strict_power(e, np.array([ci]), np.array([1.225 * (e["curve"]["min_wind_mps"] / ci * .99) ** 3]))


@pytest.mark.parametrize('key', A)
def test_e14_e15_physical_simulation_scaling_loss_and_no_internal_efficiency(key):
    p = profile([5., 7., 12., 18.]);e=get_turbine(key)
    r, k, _ = run_wind_model(p, key)
    np.testing.assert_array_equal(r.power_unit_kw, evaluate_documented_curve(e, p.wind_speed_mps.to_numpy()))
    r3,k3,_ = run_wind_model(p,key,3,True)
    np.testing.assert_allclose(r3.power_net_kw, r.power_gross_kw * 3 * .97)
    assert k3['energy_net_kwh'] == pytest.approx(k['energy_gross_kwh'] * 3 * .97)


@pytest.mark.parametrize('value', [np.nan, np.inf, -np.inf, -1.])
def test_adversarial_nonfinite_speed_and_density(value):
    e=get_turbine(next(iter(A)))
    with pytest.raises(ValueError):
        evaluate_documented_curve(e,np.array([value]))
    with pytest.raises(ValueError):
        _strict_power(e,np.array([10.]),np.array([value]))
    with pytest.raises(ValueError):
        p=profile([10.]);p['wind_speed_mps']=value;run_wind_model(p,next(iter(A)))


@pytest.mark.parametrize('mutate', [
    lambda e: e['curve'].update(points=[(1.,0.),(1.,1.)]),
    lambda e: e['curve'].update(points=[(1.,0.),(2.,np.inf)]),
    lambda e: e['curve'].update(units={'wind_speed':'mph','power':'W'}),
    lambda e: e['spec'].update(curve_peak_power_kw=999),
    lambda e: e['spec'].update(operating_power_limit_kw=100),
    lambda e: e['curve'].update(reference_density_kg_m3=None),
    lambda e: e['curve'].update(reference_density_kg_m3=-1),
    lambda e: e['spec'].pop('power_rating_basis'),
    lambda e: e['spec'].update(cut_out_mps=np.inf),
])
def test_e07_e09_adversarial_contracts(mutate):
    e=get_turbine(next(iter(A)));mutate(e)
    assert validate_turbine_entry(e)
    with pytest.raises(ValueError): evaluate_documented_curve(e,np.array([10.]))


def test_e07_reference_at_speed_not_peak_and_no_absolute_ten_kw_tolerance():
    e = get_turbine('Bergey Excel 10')
    assert validate_turbine_entry(e) == [] # admitted as secondary analysis, not certified
    p11 = float(evaluate_documented_curve(e,np.array([11.]))[0])
    e['spec']['rated_power_kw']=p11
    e['spec']['power_rating_basis']={'kind':'documented_reference_at_wind_speed','wind_speed_mps':11.,'relative_tolerance':.01}
    assert validate_turbine_entry(e)==[]
    e['spec']['rated_power_kw'] *= .9
    assert validate_turbine_entry(e)  # <1 kW discrepancy still fails, no absolute tolerance


def test_e19_exact_variants_and_source_document_hashes():
    expected = [('Vergnet GEV MP C 275 kW', 'vergnet275.pdf', None),
                ('Vestas V47-660 kW','vestas47spec.pdf','single_generator_690V_50Hz'),
                ('Vestas V52-850 kW OptiSpeed','vestas52.pdf','OptiSpeed_104.2_dBA')]
    with ZipFile(ROOT/'docs/eolica/evidencia/SEEDS2_CODEX_7_EOLICAS_INPUT.zip') as z:
        for key,file,variant in expected:
            e=get_turbine(key)
            assert hashlib.sha256(z.read('evidencia/sources/'+file)).hexdigest()==e['source']['sha256']
            if variant: assert e['spec']['variant']==variant
    assert 'V47-660/200' not in TURBINE_DB
    assert all('103 dB' not in key for key in TURBINE_DB)


@pytest.mark.parametrize('key', B)
def test_e17_small_power_and_plots_readable(key):
    from wind_app import format_wind_power
    from visualization.wind_plots import plot_catalog_curve
    assert 'kW' in format_wind_power(TURBINE_DB[key]['spec']['rated_power_kw'])
    assert '0,000' not in format_wind_power(TURBINE_DB[key]['spec']['rated_power_kw'])
    fig=plot_catalog_curve(key)
    assert fig.layout.yaxis.title.text=='Potência (kW)'
    np.testing.assert_array_equal(fig.data[0].y, np.asarray(TURBINE_DB[key]['curve']['points'])[:,1])


@pytest.mark.parametrize('key', [*A,*B])
def test_e17_e18_catalog_ui_and_selectors(key):
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('from wind_app import _init_wind_state, _render_catalog\n_init_wind_state()\n_render_catalog()',default_timeout=20)
    app.run();app.selectbox[0].select(key).run()
    assert not app.exception
    assert set(app.selectbox[0].options)==set(TURBINE_DB)
    text=' '.join(str(x.value) for x in app.markdown)
    assert 'Pico documentado' in text
    if key in B:
        assert app.warning and 'Somente análise' in app.warning[0].value
        assert 'Referência documental' in text


@pytest.mark.parametrize('key', [*A, *B])
@pytest.mark.parametrize('field,value', [('manufacturer', 'Outro fabricante'), ('model', 'V47-660/200'),
                                        ('variant', 'OptiSpeed_100_dBA'), ('rotor_diameter_m', 2.0)])
def test_e19_adversarial_identity_is_not_interchangeable(key, field, value):
    from tools.validate_wind_catalog import audit_entry
    entry=get_turbine(key)
    assert audit_entry(key, entry)['errors']==[]
    entry['spec'][field]=value
    assert audit_entry(key, entry)['errors']


@pytest.mark.parametrize('column,value', [('temperature_c', -273.15), ('pressure_hpa', -1.),
                                         ('humidity_pct', np.inf), ('pressure_hpa', 101.)])
def test_adversarial_atmosphere_does_not_silently_fall_back(column,value):
    p=profile([10.]);p['temperature_c']=20.;p['pressure_hpa']=1013.25;p['humidity_pct']=50.
    p[column]=value
    with pytest.raises(ValueError): run_wind_model(p,next(iter(A)))


def test_adversarial_negative_curve_cannot_enter_generation_only_simulator():
    e=get_turbine(next(iter(A)))
    e['curve']['points'][0]=(e['curve']['points'][0][0],-0.01)
    e['curve']['quantity']='net_electrical_exchange'
    assert validate_turbine_entry(e)
    with pytest.raises(ValueError): _strict_power(e,np.array([5.]),np.array([1.225]))


@pytest.mark.parametrize('field,value', [('swept_area_m2', None), ('swept_area_m2', np.nan),
                                        ('cut_out_mps', 1.)])
def test_adversarial_missing_geometry_and_contradictory_controller(field,value):
    e=get_turbine(next(iter(A)));e['spec'][field]=value
    assert validate_turbine_entry(e)
