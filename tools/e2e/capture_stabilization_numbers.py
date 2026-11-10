"""Numerical receipt from a detached source tree, using disposable microgrids.

Usage: python this_script.py SOURCE_ROOT OUTPUT.json
Only elapsed execution times and generated identities are excluded. All dispatch
values, balances, SOC, hydrogen, energy and cost remain in the comparison.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile

root, output = map(Path, sys.argv[1:])
sys.path[:0] = [str(root), str(root/'tests')]
import pandas as pd
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.operation import runner, strategy
from seeds2_fixtures import v16_equivalent_config
from test_seeds2_piso2c import ready

receipt = {}
with tempfile.TemporaryDirectory(prefix='seeds2-numerical-acceptance-') as data:
    reg = MicrogridRegistry(data)
    cfg = v16_equivalent_config('Numerical acceptance, synthetic')
    reg.create(cfg, origin='commissioning')
    store = reg.open(cfg['installation']['uid'])
    for algorithm, code in (('GA',1), ('GWO',2), ('NGO',3), ('SQP',0)):
        sg = strategy.default_strategy()
        sg['algorithm'] = code
        sc = ready(store, name=algorithm, duration=12, strategy=sg)
        done = runner.submit(store, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        assert done.state == 'concluida', done.error
        summary = {k: v for k, v in done.summary.items() if k != 'tempo_otimizador_s'}
        frame = runner.load_csv(store, done.run_uid, 'saidas/despacho_ems.csv')
        timing = [c for c in frame if c.startswith(('t_meta', 't_ref', 'tempo_'))]
        values = frame.drop(columns=timing).to_csv(index=False, lineterminator='\n').encode()
        receipt[algorithm] = {'summary': summary, 'series_sha256': hashlib.sha256(values).hexdigest(),
                              'series_rows': len(frame), 'series_columns': list(frame.drop(columns=timing)),
                              'excluded_timing_columns': timing}
output.write_text(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False)+'\n')
