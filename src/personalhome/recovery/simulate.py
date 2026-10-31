"""Run a bounded, local-only watchdog demonstration against one owned fake UI process."""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time

from trial import SandboxOverlay, Trial, digest

CHILD = '''import json,sys,time
mode=sys.argv[1]
for sequence in range(30):
    if mode=='crash' and sequence==2: sys.exit(7)
    if mode!='missing':
        print(json.dumps({'sequence':sequence,'view_ready':True,'navigation_ok':mode!='broken-input'}),flush=True)
    time.sleep(.05)
'''


def demonstrate(mode):
    with tempfile.TemporaryDirectory(prefix='home-recovery-simulation-') as directory:
        root = Path(directory)
        original, candidate = root / 'original', root / 'candidate'
        original.write_bytes(b'original local simulation')
        candidate.write_bytes(b'candidate local simulation')
        sandbox = root / 'sandbox'
        sandbox.mkdir()
        operations = SandboxOverlay(sandbox, original, candidate)
        trial = Trial(operations, operations.target, digest(original), digest(candidate),
                      timeout=.5, heartbeat_timeout=.15)
        messages = queue.Queue()
        child = subprocess.Popen([sys.executable, '-u', '-c', CHILD, mode],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        def read():
            for line in child.stdout:
                try: messages.put(json.loads(line))
                except ValueError: messages.put({'error': 'invalid-health-message'})
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        started = time.monotonic()
        try:
            trial.start()
            while trial.state != 'rolled_back':
                try:
                    health = messages.get(timeout=.02)
                    trial.heartbeat(health.get('sequence', 0), health.get('view_ready'),
                                    health.get('navigation_ok'), health.get('error'))
                    if trial.state == 'trial': trial.confirm()
                except queue.Empty:
                    pass
                if child.poll() is not None:
                    trial.crash()
                trial.poll()
        finally:
            if child.poll() is None:
                child.terminate()
            try: child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=1)
            child.stdout.close()
            reader.join(timeout=1)
            if trial.state in ('trial', 'confirmed'):
                trial.rollback('simulator-shutdown')
        assert operations.target.read_bytes() == original.read_bytes()
        assert operations.restore_count == operations.restart_count == 1
        return {'mode': mode, 'state': trial.state, 'reason': trial.reason,
                'elapsedMs': round((time.monotonic() - started) * 1000, 2),
                'externalFakeUiProcess': True, 'restoreCount': operations.restore_count,
                'tvRecoveryVerified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['healthy', 'crash', 'missing', 'broken-input', 'all'], default='all')
    args = parser.parse_args()
    modes = ['healthy', 'crash', 'missing', 'broken-input'] if args.mode == 'all' else [args.mode]
    print(json.dumps([demonstrate(mode) for mode in modes], indent=2))
