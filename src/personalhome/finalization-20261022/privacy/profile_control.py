"""Reversible native privacy flags; temporary trials restore the same backup."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'privacy-hardening-20261022'))
from analytics_control import Television, ORIGINAL_SHA, flags

GROUPS = {
    'rdxd': {'analyticsLog': False, 'crashLog': False},
    'uploader': {'analyticsLog': False, 'crashLog': False},
    'general': {'adCookie': 'off', 'customizedAd': 'off', 'homePromotion': 'off'},
    'option': {'livePlus': 'off', 'webOSPromotionVideo': 'off',
               'watchedListCollection': 'off', 'turnOnByVoice': 'off'},
    'consents': {k: False for k in ('additionalDataAllowed', 'customAdAllowed', 'customadsAllowed',
                 'thirdPartySharingAllowed', 'acrOnAllowed', 'acrAdAllowed', 'acrAllowed',
                 'voiceAllowed', 'voice2Allowed', 'remoteDiagAllowed', 'cookiesAllowed')},
}
SERVICES = {'rdxd': 'com.webos.rdxd/', 'uploader': 'com.palm.uploadd/'}
ORDER = ('consents', 'rdxd', 'uploader', 'general', 'option')


def read(transport, group):
    if group in SERVICES:
        return flags(transport.luna(SERVICES[group] + 'getLogSettings', {}))
    args = {'keys': ['eulaStatus']} if group == 'consents' else {'category': group, 'keys': list(GROUPS[group])}
    reply = transport.luna('com.webos.settingsservice/getSystemSettings',
                           args)
    if not isinstance(reply, dict) or reply.get('returnValue') is not True:
        raise ValueError('Preference read failed: ' + group)
    value = reply.get('settings')
    if group == 'consents':
        value = value.get('eulaStatus') if isinstance(value, dict) else None
        validate_consents(value)
        return dict(value)
    if not isinstance(value, dict) or any(value.get(k) not in ('on', 'off') for k in GROUPS[group]):
        raise ValueError('Invalid preference type: ' + group)
    return {k: value[k] for k in GROUPS[group]}


def write(transport, group, value):
    if group in SERVICES:
        service, args = SERVICES[group] + 'setLogSettings', value
    elif group == 'consents':
        service, args = 'com.webos.settingsservice/setSystemSettings', {'settings': {'eulaStatus': value}}
    else:
        service, args = 'com.webos.settingsservice/setSystemSettings', {'category': group, 'settings': value}
    reply = transport.luna(service, args)
    if not isinstance(reply, dict) or reply.get('returnValue') is not True:
        raise RuntimeError('Write not acknowledged: ' + group)
    if read(transport, group) != value:
        raise RuntimeError('Readback mismatch: ' + group)


def validate_consents(value):
    if (not isinstance(value, dict) or not set(GROUPS['consents']).issubset(value) or
            not {'networkAllowed', 'generalTermsAllowed'}.issubset(value) or len(value) > 64 or
            any(not isinstance(k, str) or not k or len(k) > 64 or type(v) is not bool for k, v in value.items())):
        raise ValueError('Invalid consent object')


def desired(before):
    wanted = {g: dict(v) for g, v in GROUPS.items()}
    wanted['consents'] = dict(before['consents'], **GROUPS['consents'])
    return wanted


def backup(path, data=None):
    path = Path(path).absolute()
    parent = path.parent.stat()
    if path.parent.resolve() != path.parent or parent.st_uid != os.getuid() or parent.st_mode & 0o022:
        raise ValueError('Unsafe backup parent')
    options = os.O_RDONLY if data is None else os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, options | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, 'r' if data is None else 'w') as stream:
        s = os.fstat(stream.fileno())
        if (not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_nlink != 1 or
                stat.S_IMODE(s.st_mode) != 0o600 or s.st_size > 8192):
            raise ValueError('Unsafe backup file')
        if data is None:
            data = json.loads(stream.read(8193))
        else:
            json.dump(data, stream)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
    if (not isinstance(data, dict) or set(data) != {'schema', 'identity', 'before'} or
            type(data['schema']) is not int or data['schema'] != 1 or
            not isinstance(data['identity'], dict) or
            set(data['identity']) != {'originalSha', 'knownHostsSha'} or
            data['identity']['originalSha'] != ORIGINAL_SHA or
            not isinstance(data['identity']['knownHostsSha'], str) or
            len(data['identity']['knownHostsSha']) != 64 or
            not isinstance(data['before'], dict) or set(data['before']) != set(GROUPS)):
        raise ValueError('Invalid profile backup')
    for group, values in data['before'].items():
        if group == 'consents':
            validate_consents(values)
            continue
        if not isinstance(values, dict) or set(values) != set(GROUPS[group]):
            raise ValueError('Invalid profile backup group')
        if group in SERVICES:
            flags(dict(values, returnValue=True))
        elif any(v not in ('on', 'off') for v in values.values()):
            raise ValueError('Invalid profile backup value')
    return data


def run(transport, mode, path=None, authorized=False):
    if mode not in ('status', 'apply', 'restore'):
        raise ValueError('Invalid operation')
    if mode != 'status' and (not authorized or path is None):
        raise PermissionError('Authorized reversible trial or approved deployment and backup required')
    identity = transport.identity()
    current = {g: read(transport, g) for g in GROUPS}
    if mode == 'status':
        return {'status': 'read-only', 'settings': current}
    if mode == 'apply':
        backup(path, {'schema': 1, 'identity': identity, 'before': current})
    saved = backup(path)
    if saved['identity'] != identity:
        raise ValueError('Backup identity differs')
    applied = desired(saved['before'])
    wanted = applied if mode == 'apply' else saved['before']
    changes = []
    cookie_reset = False
    # Keep completed groups identifiable; the caller restores in finally even on timeout.
    for group in ORDER:
        now = read(transport, group)
        if mode == 'apply' and now != current[group]:
            raise ValueError('Concurrent preference change: ' + group)
        allowed_applied = dict(applied[group], adCookie='on') if group == 'general' and cookie_reset else applied[group]
        if mode == 'restore' and (set(now) != set(saved['before'][group]) or
                any(now[k] not in (saved['before'][group][k], allowed_applied[k]) for k in now)):
            raise ValueError('Restore conflict; preserve unknown setting change: ' + group)
        if now != wanted[group]:
            write(transport, group, dict(wanted[group]))
            changes.append(group)
            if group == 'consents':
                # This firmware resets adCookie to on when eulaStatus changes.
                observed = read(transport, 'general')
                if observed not in (current['general'], dict(current['general'], adCookie='on')):
                    raise ValueError('Unexpected consent side effect: general')
                cookie_reset = observed['adCookie'] == 'on'
                current['general'] = observed
    final = {g: read(transport, g) for g in GROUPS}
    if final != wanted:
        raise RuntimeError('Final profile verification failed')
    return {'status': mode + '-verified', 'changedGroups': changes, 'settings': final,
            'scope': 'native flags; no service stop, network rule, restart, boot hook or packet verification'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['status', 'apply', 'restore'])
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--authorized-trial-or-deployment', action='store_true')
    args = parser.parse_args()
    if args.mode != 'status' and (not args.authorized_trial_or_deployment or args.backup is None):
        parser.error('Authorization and backup are required before any device change')
    print(json.dumps(run(Television(), args.mode, args.backup, args.authorized_trial_or_deployment)))
