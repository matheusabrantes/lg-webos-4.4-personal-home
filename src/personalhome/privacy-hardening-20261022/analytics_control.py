"""One authorized native preference experiment; no resident service or boot hook."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

ORIGINAL_SHA = '5d2c9872f8b2c918c605cd05a7c49844645a8b683d8c1f8ee55f7bb1be6738e9'
SERVICE = 'com.webos.rdxd/'


def flags(reply):
    if (not isinstance(reply, dict) or reply.get('returnValue') is not True or
            any(type(reply.get(k)) is not bool for k in ('analyticsLog', 'crashLog'))):
        raise ValueError('Invalid log settings response')
    return {k: reply[k] for k in ('analyticsLog', 'crashLog')}


def backup_file(path, value=None):
    path = Path(path).absolute()
    parent = path.parent.stat()
    if (path.parent.resolve() != path.parent or not stat.S_ISDIR(parent.st_mode) or
            parent.st_uid != os.getuid() or parent.st_mode & 0o022):
        raise ValueError('Unsafe backup directory')
    mode = os.O_RDONLY if value is None else os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, mode | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, 'r' if value is None else 'w') as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or info.st_size > 4096):
            raise ValueError('Unsafe backup file')
        if value is not None:
            json.dump(value, handle)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        else:
            value = json.loads(handle.read(4097))
    if (not isinstance(value, dict) or set(value) != {'schema', 'identity', 'before'} or
            type(value['schema']) is not int or value['schema'] != 1 or
            not isinstance(value['identity'], dict) or
            set(value['identity']) != {'originalSha', 'knownHostsSha'} or
            value['identity']['originalSha'] != ORIGINAL_SHA or
            not isinstance(value['identity']['knownHostsSha'], str) or
            len(value['identity']['knownHostsSha']) != 64 or
            not isinstance(value['before'], dict) or
            set(value['before']) != {'analyticsLog', 'crashLog'} or
            any(type(value['before'][k]) is not bool for k in value['before'])):
        raise ValueError('Invalid backup schema')
    return value


def run(transport, mode, backup=None, authorized=False):
    if mode not in ('status', 'apply', 'restore'):
        raise ValueError('Invalid operation')
    if mode != 'status' and (not authorized or backup is None):
        raise ValueError('Explicit device-change authorization and backup required')
    identity = transport.identity()
    current = flags(transport.luna(SERVICE + 'getLogSettings', {}))
    if mode == 'status':
        return {'status': 'read-only', 'settings': current}
    if mode == 'apply':
        saved = backup_file(backup, {'schema': 1, 'identity': identity, 'before': current})
        saved = backup_file(backup)
        if saved['identity'] != identity or saved['before'] != current:
            raise ValueError('Backup verification failed; no write attempted')
        wanted = False
    else:
        saved = backup_file(backup)
        if saved['identity'] != identity:
            raise ValueError('Backup belongs to a different device/SSH trust file')
        wanted = saved['before']['analyticsLog']
    if flags(transport.luna(SERVICE + 'getLogSettings', {})) != current:
        raise ValueError('Settings changed concurrently; no write attempted')
    expected = dict(current, analyticsLog=wanted)
    if expected != current:
        # Both fields are required by the upstream API; preserve the current crash flag.
        ack = transport.luna(SERVICE + 'setLogSettings', expected)
        if not isinstance(ack, dict) or ack.get('returnValue') is not True:
            raise RuntimeError('Write not acknowledged; state uncertain, retain backup and read status')
        if flags(transport.luna(SERVICE + 'getLogSettings', {})) != expected:
            raise RuntimeError('Readback mismatch; state uncertain, retain backup for explicit restore')
    return {'status': mode + '-verified', 'settings': expected,
            'protection': 'preference-only; network and restart persistence unverified'}


class Television:
    def __init__(self):
        self.root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(self.root / 'work/abrantesflix'))
        import tv
        self.tv = tv

    def identity(self):
        digest = self.tv.shell('sha256sum /usr/bin/surface-manager-starfish').split()[0]
        if digest != ORIGINAL_SHA:
            raise ValueError('Unexpected firmware/executable; refusing experiment')
        trust = self.root / 'work/tv-private/known_hosts'
        return {'originalSha': digest, 'knownHostsSha': hashlib.sha256(trust.read_bytes()).hexdigest()}

    def luna(self, method, args):
        return self.tv.luna(method, args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['status', 'apply', 'restore'])
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--authorize-device-change', action='store_true')
    args = parser.parse_args()
    if args.mode != 'status' and (not args.authorize_device_change or args.backup is None):
        parser.error('Device change requires explicit authorization and --backup')
    print(json.dumps(run(Television(), args.mode, args.backup, args.authorize_device_change)))


if __name__ == '__main__':
    main()
