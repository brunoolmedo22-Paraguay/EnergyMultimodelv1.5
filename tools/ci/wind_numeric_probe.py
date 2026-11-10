"""CI-01: export complete historical runs without changing physics or fixtures.

Capture: python tools/ci/wind_numeric_probe.py --output DIR [--exercise-solver]
Compare: python tools/ci/wind_numeric_probe.py --compare DIR_A DIR_B --output REPORT
NPZ is authoritative float64 evidence; CSV is a 17-significant-digit view.
The comparison reports differences; it does not relax any regression assertion.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from models import wind_model as W

POWER = ['power_unit_kw', 'power_gross_kw', 'power_net_kw']


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def capture(output, exercise_solver):
    if exercise_solver:
        import pyomo.environ as pe
        model = pe.ConcreteModel()
        model.x = pe.Var(bounds=(0, None))
        model.c = pe.Constraint(expr=model.x >= 1)
        model.o = pe.Objective(expr=model.x)
        pe.SolverFactory('highs').solve(model)
        assert pe.value(model.x) == 1
    base = json.loads((ROOT/'tests/fixtures/wind_historical_v1.json').read_text())
    raw = W.read_wind_csv(ROOT/'Dados_exemplo/perfil_eolico_sintetico_ceara_1_semana_10min.csv')
    cols = W.detect_columns(raw.columns)
    weather = W.prepare_wind_profile(raw, W.WindInputMapping(**{
        key: cols[key] for key in W.WindInputMapping.__annotations__}))
    boundaries = W.prepare_wind_profile(pd.DataFrame({
        't': pd.date_range('2026-01-01', periods=601, freq='10min'),
        'v': np.linspace(0, 30, 601)}), W.WindInputMapping('t', 'v'))
    metadata = {'python': sys.version, 'platform': platform.platform(), 'libc': platform.libc_ver(),
                'git_head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
                'disabled': os.environ.get('NPY_DISABLE_CPU_FEATURES'), 'versions': {}, 'results': {},
                'solver_imported': any(name in sys.modules for name in ('pyomo', 'highspy')),
                'solver_exercised': exercise_solver,
                'cpu_features': np._core._multiarray_umath.__cpu_features__,
                'numpy_binary_sha256': digest(Path(np._core._multiarray_umath.__file__).read_bytes()),
                'environment': {key: os.environ.get(key) for key in (
                    'OPENBLAS_NUM_THREADS', 'OPENBLAS_CORETYPE', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'GLIBC_TUNABLES')}}
    cpuinfo = Path('/proc/cpuinfo')
    metadata['cpu_model'] = next((line.split(':',1)[1].strip() for line in cpuinfo.read_text().splitlines()
                                  if line.startswith('model name')), None) if cpuinfo.exists() else None
    try:
        metadata['fenv_round'] = ctypes.CDLL(None).fegetround()
    except AttributeError:
        metadata['fenv_round'] = None
    for name in ('numpy','scipy','pandas','pyomo','highspy'):
        try:
            metadata['versions'][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            metadata['versions'][name] = None
    source_files = ('models/wind_model.py','config/wind_turbine_database.py',
                    'tests/fixtures/wind_historical_v1.json',
                    'Dados_exemplo/perfil_eolico_sintetico_ceara_1_semana_10min.csv')
    metadata['source_sha256'] = {path: digest((ROOT/path).read_bytes()) for path in source_files}
    arrays = {}
    for mode, profile in (('weather', weather), ('boundaries', boundaries)):
        for i, key in enumerate(base['entries']):
            result, kpis, _ = W.run_wind_model(profile, key, 2, True)
            numeric = result.select_dtypes(include='number')
            power = result[POWER].to_numpy()
            sha = digest(power.tobytes())
            prefix = f'{mode}_{i}'
            arrays[prefix+'_power'] = power
            arrays[prefix+'_all_numeric'] = numeric.to_numpy()
            result[['timestamp', *POWER]].to_csv(output/(prefix+'.csv'), index=False, float_format='%.17g')
            metadata['results'][prefix] = {
                'key': key, 'sha256': sha, 'historical_sha256': base[mode][key]['power_sha256'],
                'matches_history': sha == base[mode][key]['power_sha256'], 'kpis': kpis,
                'kpis_exact': kpis == base[mode][key]['kpis'], 'columns': list(numeric),
                'dtype': power.dtype.str, 'shape': power.shape, 'strides': power.strides,
                'timestep_hours': profile.attrs['timestep_hours'],
                'flags': {'c': power.flags.c_contiguous, 'f': power.flags.f_contiguous}}
        t = profile.temperature_c.to_numpy(float)
        arrays[mode+'_exp_argument'] = (18.678-t/234.5)*(t/(257.14+t))
        arrays[mode+'_vapor_pressure'] = W._saturation_vapor_pressure_hpa(t)
        arrays[mode+'_profile'] = profile.select_dtypes(include='number').to_numpy()
    metadata['ufunc_dispatch'] = np.lib.introspect.opt_func_info(func_name='exp|power', signature='float64')
    config = io.StringIO()
    with contextlib.redirect_stdout(config):
        np.show_config()
        np.show_runtime()
    metadata['numpy_config'] = config.getvalue()
    np.savez_compressed(output/'arrays.npz', **arrays)
    (output/'metadata.json').write_text(json.dumps(metadata, indent=2, allow_nan=False)+'\n')
    print('Historical hashes:', sum(r['matches_history'] for r in metadata['results'].values()), '/ 12;',
          'KPIs:', sum(r['kpis_exact'] for r in metadata['results'].values()), '/ 12')


def metrics(reference, current, step):
    assert reference.dtype == current.dtype == np.dtype('float64')
    assert reference.shape == current.shape
    finite = np.isfinite(reference) & np.isfinite(current)
    bits_a, bits_b = reference.view('u8'), current.view('u8')
    changed = bits_a != bits_b
    diff = current-reference
    magnitude = np.abs(diff[finite])
    nonzero = finite & (reference != 0)
    order = lambda bits: np.where(bits >> 63, ~bits, bits | np.uint64(1 << 63))
    a, b = order(bits_a), order(bits_b)
    ulp = np.maximum(a,b)-np.minimum(a,b)
    return {'samples': len(reference), 'values': reference.size, 'different_values': int(changed.sum()),
            'different_samples': int(changed.any(axis=1).sum()),
            'first_difference': list(map(int,np.argwhere(changed)[0])) if changed.any() else None,
            'max_absolute_kw': float(magnitude.max(initial=0)),
            'max_relative': float(np.max(np.abs(diff[nonzero]/reference[nonzero]), initial=0)),
            'rmse_kw': math.sqrt(math.fsum(float(v)**2 for v in diff[finite])/int(finite.sum())),
            'energy_difference_kwh': [math.fsum(map(float,diff[:,j]))*step for j in range(3)],
            'max_ulp': int(ulp[finite].max(initial=0)),
            'nan_counts': [int(np.isnan(x).sum()) for x in (reference,current)],
            'infinity_counts': [int(np.isinf(x).sum()) for x in (reference,current)],
            'different_signed_zeros': int(((reference==0)&(current==0)&changed).sum()),
            'dtype_reference': reference.dtype.str, 'dtype_current': current.dtype.str}


def compare(paths, output, publish_receipt=False):
    left, right = map(Path, paths)
    meta_a = json.loads((left/'metadata.json').read_text())
    meta_b = json.loads((right/'metadata.json').read_text())
    a, b = np.load(left/'arrays.npz'), np.load(right/'arrays.npz')
    rows = {}
    for name, record in meta_a['results'].items():
        row = metrics(a[name+'_power'], b[name+'_power'], record.get('timestep_hours',1/6))
        row.update(key=record['key'], kpis_exact_between_runs=record['kpis']==meta_b['results'][name]['kpis'],
                   reference_matches_history=record['matches_history'],
                   current_matches_history=meta_b['results'][name]['matches_history'])
        rows[name] = row
    (output/'comparison.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n')
    text = '## CI-01 wind numerical diagnostic\n\nComplete arrays and metadata are in the regression artifact.\n\n'
    text += '| Environment | Python | NumPy / SciPy / pandas | CPU | Disabled features |\n|---|---|---|---|---|\n'
    for label, meta in [('reference', meta_a), ('current', meta_b)]:
        versions = ' / '.join(str(meta['versions'][p]) for p in ('numpy', 'scipy', 'pandas'))
        text += f"| {label} | {meta['python'].split()[0]} | {versions} | {meta['cpu_model']} | {meta['disabled']} |\n"
    text += '\n'
    text += '| Model / weather | Different values | max abs kW | max ULP | KPIs exact |\n|---|---:|---:|---:|---|\n'
    for name,row in rows.items():
        if name.startswith('weather'):
            text += f"| {row['key']} | {row['different_values']} | {row['max_absolute_kw']:.17g} | {row['max_ulp']} | {row['kpis_exact_between_runs']} |\n"
    text += '\n| Current / weather | Actual SHA-256 | Original SHA exact | Original KPIs exact |\n|---|---|---|---|\n'
    for name, record in meta_b['results'].items():
        if name.startswith('weather'):
            text += f"| {record['key']} | `{record['sha256']}` | {record['matches_history']} | {record['kpis_exact']} |\n"
    (output/'comparison.md').write_text(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
            f.write(text)
    print(text)
    if publish_receipt and os.environ.get('GITHUB_ACTIONS') == 'true':
        receipt = {'python': meta_b['python'], 'versions': meta_b['versions'],
                   'cpu': meta_b['cpu_model'], 'ufunc_dispatch': meta_b['ufunc_dispatch'],
                   'numpy_binary_sha256': meta_b['numpy_binary_sha256'],
                   'sources_exact': meta_a['source_sha256'] == meta_b['source_sha256'],
                   'solver_exercised': meta_b['solver_exercised'],
                   'cases': {name: dict(row, actual_sha256=meta_b['results'][name]['sha256'],
                                      kpis_exact=meta_b['results'][name]['kpis_exact'])
                             for name, row in rows.items()}}
        # Public, synthetic scientific evidence only. Annotations are readable
        # without Actions API credentials; no environment variables or secrets.
        message = json.dumps(receipt, separators=(',', ':'), allow_nan=False)
        message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::notice title=CI-01 numerical receipt::'+message)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare', nargs=2)
    parser.add_argument('--exercise-solver', action='store_true')
    parser.add_argument('--publish-receipt', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    compare(args.compare, args.output, args.publish_receipt) if args.compare else capture(args.output,args.exercise_solver)
