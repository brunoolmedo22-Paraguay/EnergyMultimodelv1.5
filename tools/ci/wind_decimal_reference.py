"""Independent CI-01 calculation of the fixed historical weather experiment.

No model function, NumPy transcendental or NumPy interpolation is used by the
oracle. This diagnostic implements Buck/moist air, original piecewise linear
curves and the historical control/loss convention in 80-digit Decimal arithmetic.
It is restricted to the six historical equipment entries and this weather case.
"""
from __future__ import annotations

import argparse
import bisect
from decimal import Decimal, localcontext
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def weather_power(profile, entry, count=2, grid_loss=True):
    def d(value):
        return Decimal(str(value))

    def interpolate(points, wind):
        points = [tuple(map(d,p)) for p in points]
        j = bisect.bisect_right([p[0] for p in points],wind)
        if j == 0:
            return Decimal(0)
        if j == len(points):
            return points[-1][1]
        x0,y0 = points[j-1]
        x1,y1 = points[j]
        return y0+(wind-x0)*(y1-y0)/(x1-x0)

    assert entry.get('schema_version') != 2, 'historical oracle only'
    curve, spec = entry['curve'], entry['spec']
    rows = []
    with localcontext() as context:
        context.prec = 80
        for v,t,p,rh in zip(profile.wind_speed_mps,profile.temperature_c,profile.pressure_hpa,profile.humidity_pct):
            assert all(math.isfinite(x) for x in (v,t,p,rh))
            v,t,p,rh = map(d,(v,t,p,rh))
            tk = t+d('273.15')
            saturation = d('6.1121')*((d('18.678')-t/d('234.5'))*(t/(d('257.14')+t))).exp()
            vapor = min(max(rh/d(100)*saturation,d(0)),p*d('.2'))
            rho = (p-vapor)*d(100)/(d('287.058')*tk)+vapor*d(100)/(d('461.495')*tk)
            if curve['density_correction'] == 'manufacturer_density_table':
                tables = curve['density_curves']
                densities = sorted(tables)
                j = bisect.bisect_right(list(map(d,densities)),rho)
                assert 0 < j < len(densities), 'outside fixed oracle domain'
                lo,hi = densities[j-1],densities[j]
                a,b = interpolate(tables[lo],v),interpolate(tables[hi],v)
                power = a+(rho-d(lo))/(d(hi)-d(lo))*(b-a)
            else:
                equivalent = v*(rho/d(curve['reference_density_kg_m3']))**(d(1)/d(3))
                power = interpolate(curve['points'],equivalent)
            if v < d(spec['cut_in_mps']) or (spec['cut_out_mps'] is not None and v >= d(spec['cut_out_mps'])):
                power = d(0)
            power = min(max(power,d(0)),d(spec['rated_power_kw']))
            gross = power*count
            rows.append([float(power),float(gross),float(gross*(d('.97') if grid_loss else d(1)))])
    return np.asarray(rows,dtype='float64')


def main(captures, output):
    from models import wind_model as wind
    from config.wind_turbine_database import get_turbine
    base = json.loads((ROOT/'tests/fixtures/wind_historical_v1.json').read_text())
    raw = wind.read_wind_csv(ROOT/'Dados_exemplo/perfil_eolico_sintetico_ceara_1_semana_10min.csv')
    columns = wind.detect_columns(raw.columns)
    profile = wind.prepare_wind_profile(raw,wind.WindInputMapping(**{
        key:columns[key] for key in wind.WindInputMapping.__annotations__}))
    captured = {str(path):np.load(Path(path)/'arrays.npz') for path in captures}
    rows,arrays = {},{}
    for i,key in enumerate(base['entries']):
        reference = weather_power(profile,get_turbine(key))
        arrays[str(i)] = reference
        rows[key] = {}
        for path,values in captured.items():
            actual = values[f'weather_{i}_power']
            delta = actual-reference
            rows[key][path] = {'max_absolute_kw':float(np.max(abs(delta))),
                'max_relative':float(np.max(abs(delta)/reference)),
                'max_ulp':int(np.max(abs(actual.view('i8')-reference.view('i8')))),
                'rmse_kw':math.sqrt(math.fsum(float(v)**2 for v in delta.ravel())/delta.size)}
    output.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(output/'decimal-reference.npz',**arrays)
    (output/'decimal-comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
    print('Independent 80-digit oracle compared',len(rows),'historical models.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--captures',nargs='+',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    main(args.captures,args.output)
