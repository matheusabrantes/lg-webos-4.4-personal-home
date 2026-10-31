"""SSH/Luna transport; importing this module never contacts a device."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
_config_path = ROOT / '.local/device/config.json'
_config = json.loads(_config_path.read_text()) if _config_path.is_file() else {}
HOST = os.environ.get('PERSONALHOME_TV_HOST', _config.get('host', ''))
_key = os.environ.get('PERSONALHOME_SSH_KEY', str(ROOT / '.local/device/lg-root-ed25519'))
_known_hosts = os.environ.get('PERSONALHOME_KNOWN_HOSTS', str(ROOT / '.local/device/known_hosts'))
SSH = ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes', '-o',
       'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + _known_hosts,
       '-i', _key]


def target():
    if not HOST:
        raise RuntimeError('Set PERSONALHOME_TV_HOST or a private .local/device/config.json first')
    if not isinstance(HOST, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', HOST):
        raise ValueError('Invalid TV host')
    return 'root@' + HOST


def shell(command, tty=False, raw=False):
    result = subprocess.run(SSH + (['-tt'] if tty else []) + [target(), command],
                            capture_output=True, timeout=40)
    if result.returncode:
        raise RuntimeError('TV command failed')
    return result.stdout if raw else result.stdout.decode(errors='replace')


def luna(service, args):
    output = shell('/usr/bin/luna-send -i -n 1 -w 5000 -f ' +
                   shlex.quote('luna://' + service) + ' ' + shlex.quote(json.dumps(args)), True)
    start = output.find('{')
    if start < 0:
        raise RuntimeError('No TV response')
    return json.JSONDecoder().raw_decode(output[start:])[0]
