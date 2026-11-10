"""Reproduce existing browser protocols with disposable storage and owned servers.

Usage: python tools/e2e/run_stabilization.py [protocol ...]
Requires Playwright's Node package and system Chromium. Never opens user storage.
Every process output, browser error and phase receipt is retained under out/.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'tools/e2e/out/stabilization'
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable
PORT = int(os.environ.get('SEEDS2_E2E_PORT', '8611'))


def run(command, log, env=None):
    with log.open('w') as f:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{command}: exit {result.returncode}; see {log}')


class Server:
    def __init__(self, data, out, tag, sabotage=False, entry='app.py'):
        self.log = (out / f'server-{tag}.log').open('w')
        env = {**os.environ, 'SEEDS2_DATA_DIR': str(data), 'SEEDS2_DEV_MODE': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
        if sabotage:
            env.update(PYTHONPATH=str(ROOT/'tools/e2e/sabotage'), SEEDS2_E2E_ROOT=str(ROOT),
                       SEEDS2_E2E_ENGINE_LOG=str(out/'forbidden-engine.log'))
        self.proc = subprocess.Popen([PY, '-m', 'streamlit', 'run', entry, '--server.headless=true',
                                      f'--server.port={PORT}', '--browser.gatherUsageStats=false'], cwd=ROOT, env=env,
                                     stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(120):
            if self.proc.poll() is not None:
                raise RuntimeError('Streamlit exited; see '+str(out))
            try:
                with urllib.request.urlopen(f'http://localhost:{PORT}/_stcore/health', timeout=1) as r:
                    if r.status == 200:
                        return
            except OSError:
                time.sleep(.5)
        raise RuntimeError('Streamlit health timeout')

    def stop(self, hard=False):
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGKILL if hard else signal.SIGTERM)
            self.proc.wait(timeout=20)
        self.log.close()


def protocol(name):
    if name in ('benches', 'transfer', 'readonly'):
        return acceptance_group(name)
    out = OUT/name
    out.mkdir(exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix=f'seeds2-acceptance-{name}-'))
    receipt = {'protocol': name, 'data_dir': str(data), 'phases': []}
    server = None
    try:
        seed = {'2a':'seed_piso2a.py', '2b':'seed_piso2b.py', 'forecasts':'seed_piso2b.py', '2c':'seed_piso2c.py',
                '2da':'seed_piso2da.py', '2db':'seed_piso2db.py'}.get(name)
        if seed:
            cmd = [PY, str(ROOT/'tools/e2e'/seed), str(data)]
            if name in ('2b', 'forecasts'):
                cmd.append(str(out/'csv'))
            run(cmd, out/'seed.log')
        script, phases = {
            'piso1': ('e2e_piso1_microrrede.js', ['comissionar','reabrir','tablet']),
            'gestor': ('e2e_gestor_microrredes.js', ['multi','reinicio','tablet']),
            '2a': ('e2e_piso2a_centro_operacao.js', ['operar','reinicio','tablet']),
            '2b': ('e2e_piso2b_previsoes.js', ['operar','reinicio','tablet']),
            'forecasts': ('e2e_stabilization_forecasts.js', ['operar','reinicio']),
            '2c': ('e2e_piso2c_execucao.js', ['operar','reinicio','tablet']),
            '2da': ('e2e_piso2da_arquivo.js', ['exportar','importar','reinicio','tablet']),
            '2db': ('e2e_piso2db_relatorios.js', ['local','importar','reinicio','tablet']),
        }[name]
        for phase in phases:
            if server:
                server.stop(hard=(name == '2c' and phase == 'reinicio') or (name == '2db' and phase == 'reinicio'))
            if phase == 'importar':
                data = Path(tempfile.mkdtemp(prefix=f'seeds2-acceptance-{name}-destination-'))
                receipt['destination_data_dir'] = str(data)
            server = Server(data, out, phase, sabotage=name in ('2da','2db') and phase != phases[0])
            env = {**os.environ, 'NODE_OPTIONS': '--require='+str(ROOT/'tools/e2e/chromium_system.cjs'),
                   'E2E_ERRORS_FILE': str(out/f'{phase}-browser.json')}
            args = ['node', str(ROOT/'tools/e2e'/script), f'http://localhost:{PORT}', phase, str(out)]
            if name == 'gestor': args.append(str(data))
            if name == '2b': args.append(str(out/'csv'))
            if name == 'forecasts':
                args = ['node', str(ROOT/'tools/e2e'/script), f'http://localhost:{PORT}', str(out/'csv'), str(out), phase]
            if name == '2da': args.append(str(Path(receipt['data_dir'])/'custo_origem.txt'))
            if name == '2db': args.append(str(Path(receipt['data_dir'])/'e2e_origem.json'))
            start = time.monotonic()
            run(args, out/f'{phase}.log', env)
            receipt['phases'].append({'phase': phase, 'passed': True, 'duration_s': round(time.monotonic()-start, 2)})
            (out/'receipt.json').write_text(json.dumps(receipt, indent=2))
            print(f'{name}/{phase}: PASS', flush=True)
    except Exception as exc:
        receipt['error'] = str(exc)
        (out/'receipt.json').write_text(json.dumps(receipt, indent=2))
        print(f'{name}: FAIL: {exc}', flush=True)
        return False
    finally:
        if server: server.stop()
    return True


def acceptance_group(name):
    out = OUT/name
    out.mkdir(exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix=f'seeds2-acceptance-{name}-'))
    server = None
    try:
        if name != 'readonly':
            run([PY, 'tools/e2e/seed_piso2c.py', str(data)], out/'seed.log')
        else:
            data.chmod(0o555)
        for bench in (['solar','wind','thermal','battery','h2','mix'] if name == 'benches' else [name]):
            if server: server.stop()
            entry = {'mix':'tools/e2e/mix_acceptance_app.py', 'transfer':'tools/e2e/transfer_fault_app.py'}.get(bench, 'app.py')
            server = Server(data, out, bench, entry=entry)
            env = {**os.environ, 'NODE_OPTIONS':'--require='+str(ROOT/'tools/e2e/chromium_system.cjs'),
                   'E2E_ERRORS_FILE':str(out/(bench+'-browser.json'))}
            script = 'e2e_stabilization_benches.js' if name == 'benches' else f'e2e_stabilization_{name}.js'
            args = ['node','tools/e2e/'+script,f'http://localhost:{PORT}']
            if name == 'benches': args.append(bench)
            args.append(str(out))
            run(args, out/(bench+'.log'), env)
            print(name+'/'+bench+': PASS', flush=True)
    except Exception as exc:
        print(name+': FAIL: '+str(exc), flush=True)
        return False
    finally:
        if server: server.stop()
        if name == 'readonly': data.chmod(0o755)
    return True


if __name__ == '__main__':
    results = [protocol(p) for p in (sys.argv[1:] or ['piso1','gestor','2a','2b','2c','2da','2db'])]
    raise SystemExit(0 if all(results) else 1)
