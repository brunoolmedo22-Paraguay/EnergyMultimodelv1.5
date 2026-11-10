"""Compare solver/no-solver JUnit coverage and validate real CSV downloads.

Usage: python tools/e2e/check_stabilization_results.py GLOBAL.xml NO_SOLVER.xml BROWSER_OUTPUT REPORT_DIR
Opaque object addresses in pytest parameter *names* are normalized for matching;
no scientific values, CSV contents, tolerances or reference fixtures are changed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


def identity(case):
    return re.sub(r'0x[0-9a-f]+', '0xADDR', case.get('classname', '')+'::'+case.get('name', ''))


def main(full_xml, no_solver_xml, browser_output, reports):
    full = ET.parse(full_xml).findall('.//testcase')
    reduced = ET.parse(no_solver_xml).findall('.//testcase')
    normal = {identity(c): c for c in reduced if c.get('classname')}
    modules = {c.get('name'): c.find('skipped').text for c in reduced if not c.get('classname')}
    omissions = []
    for case in full:
        key = identity(case)
        reduced_case = normal.get(key)
        if reduced_case is None:
            module = next((m for m in modules if case.get('classname').startswith(m)), None)
            assert module, f'unexplained collection omission: {key}'
            reason, kind = modules[module], 'not_collected_solver_module'
        elif reduced_case.find('skipped') is not None:
            skip = reduced_case.find('skipped')
            reason = skip.get('message', '')+' '+(skip.text or '')
            kind = 'skipped_test'
        else:
            continue
        assert any(word in reason.lower() for word in ('pyomo', 'highs')), (key, reason)
        omissions.append({'test': key, 'kind': kind, 'reason': reason})
    reports = Path(reports)
    reports.mkdir(parents=True, exist_ok=True)
    result = {'passed': sum(c.find('skipped') is None and c.find('failure') is None and c.find('error') is None for c in reduced),
              'pytest_skip_markers': sum(c.find('skipped') is not None for c in reduced),
              'module_skip_markers': len(modules), 'full_suite_cases_not_executed': len(omissions), 'records': omissions}
    (reports/'omisiones-sin-solver.json').write_text(json.dumps(result, indent=2)+'\n')
    browser_output = Path(browser_output)
    rows = []
    for folder in ('benches', 'wind'):
        for file in sorted((browser_output/folder).glob('*.csv')):
            frame = pd.read_csv(file, sep=None, engine='python')
            assert len(frame) > 2, file
            column = next((c for c in frame if c.lower().startswith('timestamp')), None)
            if column:
                times = pd.to_datetime(frame[column])
                assert times.notna().all() and times.is_monotonic_increasing and not times.duplicated().any(), file
            numbers = frame.select_dtypes(include='number')
            assert not np.isinf(numbers.to_numpy()).any(), file
            rows.append({'file': file.relative_to(browser_output).as_posix(), 'rows': len(frame), 'columns': list(frame),
                         'timestamp_column': column, 'null_numeric_columns': [c for c in numbers if numbers[c].isna().any()],
                         'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
    (reports/'validacion-csv.json').write_text(json.dumps(rows, indent=2)+'\n')
    print(f'All {len(omissions)} omitted full-suite cases require solver dependencies; {len(rows)} downloaded CSVs validated.')


if __name__ == '__main__':
    main(*sys.argv[1:])
