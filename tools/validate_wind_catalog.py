"""Audit the seven admitted wind datasets without claiming pending certification.

Run from checkout: python -m tools.validate_wind_catalog [--output report.json].
Exit 0 means numerical/catalog integrity; primary-document readiness is separate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from config.wind_turbine_database import TURBINE_DB, validate_turbine_entry

ROOT = Path(__file__).resolve().parents[1]


def audit_entry(key: str, candidate: dict) -> dict:
    """Compare a proposed record against the admitted identity/variant and raw CSV.

    Matching power or geometry alone never establishes identity. This is a
    transcription audit against the admitted record, not new certification.
    """
    accepted = TURBINE_DB[key]
    errors = validate_turbine_entry(candidate)
    for field in ('manufacturer', 'model', 'variant', 'rotor_diameter_m', 'rated_power_kw',
                  'power_rating_basis', 'cut_in_mps', 'cut_out_mps', 'reference_air_density_kg_m3'):
        if candidate['spec'].get(field) != accepted['spec'].get(field):
            errors.append(f'identidade/condição divergente: {field}')
    for field in ('sha256', 'archive_blob_sha', 'archive_commit', 'primary_url', 'url', 'page_pdf', 'document'):
        if candidate['source'].get(field) != accepted['source'].get(field):
            errors.append(f'fonte divergente: {field}')
    curve = candidate['curve']
    if curve['points'] != accepted['curve']['points']:
        errors.append('pontos divergem do CSV admitido')
    if curve['source_type'] != accepted['curve']['source_type']:
        errors.append('tipo de fonte divergente')
    path = ROOT / 'config/wind_curves' / accepted['curve']['csv']
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != curve['csv_sha256']:
        errors.append('SHA-256 do CSV divergente')
    member = ('evidencia/nrel_data/' if accepted['integration_status'] == 'curve_analysis_only'
              else 'curvas_potencia/') + path.name
    with ZipFile(ROOT / 'docs/eolica/evidencia/SEEDS2_CODEX_7_EOLICAS_INPUT.zip') as z:
        if z.read(member) != raw:
            errors.append('CSV diverge dos bytes originais do pacote Work')
    v, p = np.asarray(curve['points']).T
    basis = candidate['spec']['power_rating_basis']
    ref = candidate['spec']['rated_power_kw']
    at_v = float(np.interp(basis['wind_speed_mps'], v, p)) if 'wind_speed_mps' in basis else None
    comparison = at_v if at_v is not None else float(p.max())
    relative_error = abs(comparison - ref) / ref
    return {'key': key, 'errors': errors, 'csv_sha256': hashlib.sha256(raw).hexdigest(),
            'point_count': len(p), 'domain_mps': [float(v[0]), float(v[-1])],
            'minimum_net_power_kw': float(p.min()), 'curve_peak_power_kw': float(p.max()),
            'reference_power_kw': ref, 'rating_basis': basis,
            'interpolated_power_at_reference_speed_kw': at_v, 'relative_reference_error': relative_error,
            'within_numerical_screen_tolerance': relative_error <= basis['relative_tolerance'],
            'reference_approval': ('pending_primary_document' if candidate['integration_status'] == 'curve_analysis_only'
                                   else 'manufacturer_table_verified_against_work'),
            'integration_status': candidate['integration_status']}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = [audit_entry(k, e) for k, e in TURBINE_DB.items() if e.get('schema_version') == 2]
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return int(any(r['errors'] for r in report))


if __name__ == '__main__':
    raise SystemExit(main())
